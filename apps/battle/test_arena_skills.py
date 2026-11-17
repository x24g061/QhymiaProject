"""PvPから探索共通スキル実行器への接続と保存の回帰契約。"""
from collections import Counter
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Character, User
from apps.battle.arena_engine import ArenaBattleEngine
from apps.battle.arena_services import challenge_arena_master
from apps.battle.boss_simulation import seeded_random
from apps.battle.initiative import calculate_gauge_gain
from apps.battle.models import ArenaFloor, ArenaState, ArenaBattleHistory, Skill, SkillPreset


class ArenaSkillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Character.objects.create(
            user=User.objects.create_user(user_id="arena-skill-a", email="a@arena.invalid", password=None),
            name="挑戦スキル", job="wizard", max_hp=10000, current_hp=4000,
            max_mp=10000, current_mp=4000, strength=200, intelligence=200,
            dexterity=200, agility=200, vitality=100, luck=100)
        cls.b = Character.objects.create(
            user=User.objects.create_user(user_id="arena-skill-b", email="b@arena.invalid", password=None),
            name="防衛スキル", job="warrior", max_hp=10000, current_hp=4000,
            max_mp=10000, current_mp=4000, strength=200, intelligence=200,
            dexterity=200, agility=200, vitality=100, luck=100)
        cls.floor = ArenaFloor.objects.get(floor=3)
        cls.floor.master = cls.b
        cls.floor.save()
        cls.sa = ArenaState.objects.create(character=cls.a, floor=cls.floor, current_hp=5000, current_mp=3000)
        cls.sb = ArenaState.objects.create(character=cls.b, floor=cls.floor, current_hp=5000, current_mp=3000)

    def slot(self, character, code, slot=1, uses=2, inherit=False):
        skill = Skill.objects.get(code=code)
        if inherit:
            character.permanent_skills.add(skill)
        return SkillPreset.objects.create(character=character, skill=skill, slot=slot, use_count=uses)

    def engine(self):
        return ArenaBattleEngine(self.a, self.b, self.sa, self.sb)

    def test_both_sides_use_own_native_skills_and_resources(self):
        pa = self.slot(self.a, "fire")
        pb = self.slot(self.b, "flare_blade")
        engine = self.engine()
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            self.assertEqual(engine.challenger_turn(), "fire")
            self.assertEqual(engine.defender_turn(), "flare_blade")
        self.assertEqual(engine.challenger_mp, 3000-pa.skill.mp_cost)
        self.assertEqual(engine.defender_mp, 3000-pb.skill.mp_cost)
        self.assertLess(engine.challenger_hp, 5000)
        self.assertLess(engine.defender_hp, 5000)
        self.assertEqual((engine.challenger_combatant.stamina, engine.defender_combatant.stamina), (95, 95))
        self.sa.refresh_from_db()
        self.assertEqual(self.sa.current_mp, 3000)  # エンジン単体は保存しない

    def test_inherited_skills_passive_and_independent_budgets(self):
        for character in (self.a, self.b):
            self.slot(character, "principle_of_freedom", inherit=True)
            self.slot(character, "anti_jail", slot=2, inherit=True)
        engine = self.engine()
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            self.assertEqual(engine.challenger_turn(), "anti_jail")
            self.assertEqual(engine.defender_turn(), "anti_jail")
        for actor in (engine.challenger_actor, engine.defender_actor):
            self.assertAlmostEqual(actor.freedom_bonus, 0.02)
            self.assertNotIn(actor.presets[0].pk, actor.remaining_uses)
            self.assertEqual(actor.remaining_uses[actor.presets[1].pk], 1)

    def test_unauthorized_and_sixth_slot_are_not_executed(self):
        for character in (self.a, self.b):
            self.slot(character, "rapid_shot")
            self.slot(character, "principle_of_freedom", slot=6, inherit=True)
        engine = self.engine()
        self.assertEqual(engine.challenger_actor.presets, [])
        self.assertEqual(engine.defender_actor.presets, [])
        self.assertFalse(engine.challenger_actor.freedom_active)

    def test_failure_and_mp_shortage_keep_slot_and_budget(self):
        pa = self.slot(self.a, "fire")
        pb = self.slot(self.b, "flare_blade")
        engine = self.engine()
        with patch("apps.battle.arena_engine.roll_percent", return_value=False):
            self.assertEqual(engine.challenger_turn(), "normal")
        engine.defender_mp = 0
        with patch.object(engine.defender_actor, "execute_player_skill") as skill:
            self.assertEqual(engine.defender_turn(), "normal")
        skill.assert_not_called()
        for actor, preset in ((engine.challenger_actor, pa), (engine.defender_actor, pb)):
            self.assertEqual(actor.preset_index, 0)
            self.assertEqual(actor.remaining_uses[preset.pk], 2)
        self.assertEqual(engine.challenger_mp, 3000)

    def test_exhausted_slots_fall_back_without_modifying_presets(self):
        preset = self.slot(self.a, "fire", uses=1)
        engine = self.engine()
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            self.assertEqual(engine.challenger_turn(), "fire")
            self.assertEqual(engine.challenger_turn(), "normal")
        self.assertEqual(engine.challenger_actor.remaining_uses[preset.pk], 0)
        preset.refresh_from_db()
        self.assertEqual(preset.use_count, 1)

    def test_poison_sleep_and_dex_debuff_target_opponent(self):
        self.slot(self.a, "poison_dagger", inherit=True)
        self.slot(self.b, "sleep_arrow", inherit=True)
        engine = self.engine()
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            engine.challenger_turn()
            self.assertEqual(engine.defender_combatant.poison_turns, 5)
            self.assertEqual(engine.defender_combatant.dex_debuff_rate, 0.03)
            before = engine.defender_hp
            engine.defender_turn()
        self.assertEqual(engine.defender_hp, before-1000)
        self.assertEqual(engine.defender_combatant.poison_turns, 4)  # 一度だけ処理
        self.assertEqual(engine.challenger_combatant.sleep_turns, 3)
        mp, st = engine.challenger_mp, engine.challenger_combatant.stamina
        self.assertEqual(engine.challenger_turn(), "skip")
        self.assertEqual((engine.challenger_mp, engine.challenger_combatant.stamina), (mp, st))

    def test_paralysis_uses_common_fifty_percent_rule_on_both_sides(self):
        for side in ("challenger", "defender"):
            engine = self.engine()
            combatant = getattr(engine, side+"_combatant")
            combatant.paralysis_turns = 1
            with patch("apps.battle.arena_engine.roll_percent", return_value=True) as roll:
                self.assertEqual(getattr(engine, side+"_turn")(), "skip")
            roll.assert_called_once_with(50)
            self.assertEqual(combatant.stamina, 100)
            combatant.paralysis_turns = 1
            with patch("apps.battle.arena_engine.roll_percent", return_value=False):
                self.assertEqual(getattr(engine, side+"_turn")(), "normal")
            self.assertEqual(combatant.stamina, 95)

    def test_poison_death_before_skill_does_not_consume_mp_or_budget(self):
        preset = self.slot(self.b, "flare_blade")
        engine = self.engine()
        engine.defender_hp = 1
        engine.defender_combatant.poison_turns = 1
        engine.defender_combatant.initiative = 100
        with patch.object(engine.defender_actor, "execute_player_skill") as skill:
            result = engine.run(max_ticks=1)
        skill.assert_not_called()
        self.assertEqual(result["winner"], "challenger")
        self.assertEqual(result["defender_mp"], 3000)
        self.assertEqual(engine.defender_actor.remaining_uses[preset.pk], 2)

    def test_healing_and_buff_use_arena_resources_on_both_sides(self):
        for character in (self.a, self.b):
            self.slot(character, "healing_shield", inherit=True)
        engine = self.engine()
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            engine.challenger_turn()
            engine.defender_turn()
        self.assertGreater(engine.challenger_hp, 5000)
        self.assertGreater(engine.defender_hp, 5000)
        self.assertEqual(engine.challenger_actor.healing_shield_turns, 3)
        self.a.refresh_from_db()
        self.assertEqual(self.a.current_hp, 4000)

    def test_reflection_counter_and_defense_work_symmetrically_without_chaining(self):
        for reverse in (False, True):
            engine = self.engine()
            source, target = (engine.challenger_actor, engine.defender_actor)
            if reverse:
                source, target = target, source
            target.steel_body_turns = 1
            target.shadow_step_turns = 2
            target.counter_stance_turns = 2
            target.counter_remaining = 3
            source.counter_stance_turns = 2
            source.counter_remaining = 3
            with patch("apps.battle.arena_engine.roll_percent", side_effect=lambda rate: rate >= 60):
                self.assertEqual(source.deal_target_damage(100), 60)
            self.assertEqual(target.player_hp, 4940)
            self.assertLess(source.player_hp, 4976)  # 反射24＋反撃
            self.assertEqual(target.counter_remaining, 2)
            self.assertEqual(source.counter_remaining, 3)  # 再反撃なし

    def test_double_ko_keeps_existing_challenger_priority(self):
        self.slot(self.a, "fire")
        engine = self.engine()
        engine.challenger_hp = engine.defender_hp = 1
        engine.defender_actor.shadow_step_turns = 2
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            result = engine.run(max_ticks=5)
        self.assertEqual((result["challenger_hp"], result["defender_hp"]), (0, 0))
        self.assertEqual(result["winner"], "challenger")

    def test_gauge_uses_dynamic_buff_fixed_reference_and_one_action_per_loop(self):
        self.slot(self.a, "walker", inherit=True)
        engine = self.engine()
        engine.challenger_combatant.initiative = 1200
        engine.defender_combatant.initiative = 1200
        events, gains = [], []
        calls = 0
        def gain(agi, reference):
            nonlocal calls
            calls += 1
            gains.append((agi, reference))
            return calculate_gauge_gain(agi, reference)
        for side in ("challenger", "defender"):
            original = getattr(engine, side+"_turn")
            def turn(side=side, original=original):
                events.append((side, calls//2))
                return original()
            setattr(engine, side+"_turn", turn)
        with patch("apps.battle.arena_engine.calculate_gauge_gain", side_effect=gain), patch("apps.battle.arena_engine.roll_percent", return_value=True):
            engine.run(max_ticks=5)
        self.assertTrue(all(n == 1 for n in Counter(events).values()))
        self.assertEqual(len(set(reference for _,reference in gains)), 1)
        self.assertLess(gains[2][0], gains[0][0])  # 歩行者と疲労

    def test_all_35_skills_use_shared_dispatch_on_both_sides(self):
        for skill in Skill.objects.order_by("id"):
            with self.subTest(skill=skill.code):
                for character in (self.a, self.b):
                    character.skill_presets.all().delete()
                    character.permanent_skills.add(skill)
                    self.slot(character, skill.code)
                engine = self.engine()
                with seeded_random(20261117), patch("apps.battle.arena_engine.roll_percent", return_value=True):
                    for side in ("challenger", "defender"):
                        combatant = getattr(engine, side+"_combatant")
                        combatant.poison_turns = combatant.sleep_turns = combatant.paralysis_turns = 0
                        expected = "normal" if skill.is_passive else skill.code
                        self.assertEqual(getattr(engine, side+"_turn")(), expected)

    def test_real_service_defense_saves_remaining_mp_and_history(self):
        self.slot(self.b, "flare_blade")
        self.a.strength = 1
        self.a.save()
        self.sa.current_hp = 1
        self.sa.save()
        with patch("apps.battle.arena_engine.roll_percent", return_value=True):
            challenge_arena_master(self.a)
        self.sa.refresh_from_db()
        self.sb.refresh_from_db()
        self.floor.refresh_from_db()
        self.assertEqual(self.floor.master_id, self.b.pk)
        self.assertEqual(self.sa.floor_id, 1)
        self.assertEqual(self.sa.current_mp, self.a.max_mp)
        self.assertLess(self.sb.current_mp, 3000)
        history = ArenaBattleHistory.objects.get(challenger=self.a)
        self.assertTrue(history.battle_timeline)
