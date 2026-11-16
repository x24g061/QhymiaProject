"""ボスの実スキル・疲労・状態異常・移行復元を検証する。"""
from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import TestCase

from apps.accounts.models import Character, User
from apps.battle.models import Enemy
from apps.battle.services import BattleEngine


migration = import_module("apps.battle.migrations.0017_boss_balance_v1")


class BossBalanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(user_id="boss_spec", email="boss@example.com",
                                        password="testpass123")
        cls.character = Character.objects.create(
            user=user, name="ボス検証", race="human", job="warrior",
            max_hp=1000000, current_hp=1000000, max_mp=100000,
            current_mp=100000, strength=100, intelligence=100,
            dexterity=100, agility=100, vitality=100, luck=100,
        )

    def engine(self, floor=7):
        boss = Enemy.objects.get(floor=floor, is_boss=True)
        engine = BattleEngine(self.character, boss)
        actor = engine.enemy_combatant.skill_actor
        # 命中・発動は成功、クリティカルと状態異常の抽選は失敗。
        actor.roll_percent = lambda rate: rate >= 60
        engine.roll_percent = lambda rate: rate >= 60
        return engine, actor

    def act(self, engine):
        engine.enemy_turn()

    def test_all_twelve_bosses_have_workbook_stats(self):
        self.assertEqual(set(migration.BOSSES), set(range(1, 13)))
        for floor, data in migration.BOSSES.items():
            with self.subTest(floor=floor):
                boss = Enemy.objects.get(floor=floor, is_boss=True)
                for key, value in data.items():
                    self.assertEqual(getattr(boss, key), value)
                self.assertIsNotNone(boss.balance_before_v1)
                self.assertEqual(len(boss.skill_codes), 5 if floor >= 7 else 0)

    def test_migration_restores_individual_values_without_changing_mobs_or_exp(self):
        editor = type("Editor", (), {"connection": connection})()
        migration.restore_balance(apps, editor)
        boss = Enemy.objects.get(floor=7, is_boss=True)
        boss.max_hp = 12345
        boss.agility = 987
        boss.exp_min = 33
        boss.exp_max = 44
        boss.save()
        before = list(Enemy.objects.order_by("pk").values())
        migration.apply_balance(apps, editor)
        self.assertEqual(Enemy.objects.get(pk=boss.pk).max_hp, 29000)
        for row in before:
            current = Enemy.objects.get(pk=row["id"])
            self.assertEqual((current.exp_min, current.exp_max),
                             (row["exp_min"], row["exp_max"]))
            if not row["is_boss"]:
                self.assertEqual(Enemy.objects.filter(pk=row["id"]).values().get(), row)
        migration.restore_balance(apps, editor)
        self.assertEqual(list(Enemy.objects.order_by("pk").values()), before)

    def test_slots_use_existing_skill_records_and_99_uses(self):
        engine, actor = self.engine()
        self.assertEqual([p.skill.code for p in actor.presets],
                         ["stella", "poison_arrow", "healing_shield", "sleep_arrow", "frost_armor"])
        self.assertEqual(list(actor.remaining_uses.values()), [99] * 5)
        skill = actor.presets[0].skill
        with patch("apps.battle.engine.skills.wizard.random.randint", return_value=4):
            self.act(engine)
        self.assertEqual(engine.enemy_combatant.mp, 7000 - skill.mp_cost)
        self.assertEqual(actor.remaining_uses[1], 98)
        self.assertEqual(actor.preset_index, 1)
        self.assertTrue(any("ステラ" in log for log in engine.logs))

    def test_failed_activation_retries_same_slot_without_spending_mp_or_uses(self):
        engine, actor = self.engine()
        actor.roll_percent = lambda rate: False
        self.act(engine)
        self.assertEqual(actor.preset_index, 0)
        self.assertEqual(actor.player_mp, 7000)
        self.assertEqual(actor.remaining_uses[1], 99)
        self.assertEqual(actor.player_stamina, 265)

    def test_insufficient_mp_uses_normal_attack_and_keeps_slot(self):
        engine, actor = self.engine()
        actor.player_mp = 0
        with patch.object(actor, "player_normal_attack") as attack:
            self.act(engine)
        attack.assert_called_once()
        self.assertEqual(actor.remaining_uses[1], 99)
        self.assertEqual(actor.preset_index, 0)

    def test_exhausted_slot_is_skipped_and_last_slot_wraps(self):
        engine, actor = self.engine()
        actor.remaining_uses[1] = 0
        self.act(engine)
        self.assertEqual(actor.preset_index, 2)
        actor.preset_index = 4
        self.act(engine)
        self.assertEqual(actor.preset_index, 0)

    def test_passive_is_not_consumed_and_stamina_zero_still_allows_actions(self):
        engine, actor = self.engine(12)
        actor.preset_index = 4
        actor.player_combatant.stamina = 0
        self.act(engine)
        self.assertEqual(actor.preset_index, 1)
        self.assertNotIn(5, actor.remaining_uses)
        self.assertEqual(actor.presets[4].use_count, 99)
        self.assertAlmostEqual(actor.freedom_bonus, 0.02)
        self.assertEqual(actor.player_stamina, 0)

    def test_stamina_affects_both_attacking_and_defending_stats(self):
        engine, actor = self.engine()
        actor.player_combatant.stamina = 135
        for name in ("dexterity", "agility", "vitality", "luck"):
            with self.subTest(name=name):
                expected = getattr(actor.player_combatant.enemy, name) * 0.75
                self.assertEqual(actor.get_player_stat(name), expected)
                self.assertEqual(engine.get_enemy_stat(name), expected)
        self.assertEqual(actor.get_player_stat("strength"), 580)
        self.assertEqual(actor.get_player_stat("intelligence"), 1600)

    def test_stella_reuses_player_multiplier_and_hits_real_player(self):
        engine, actor = self.engine()
        before = engine.player_hp
        expected = int(1600 * 0.7 - engine.get_player_stat("intelligence") * 0.3)
        with patch("apps.battle.engine.skills.wizard.random.randint", return_value=4):
            self.act(engine)
        self.assertEqual(before - engine.player_hp, 4 * expected)
        self.assertEqual(engine.player_mp, 100000)
        self.assertEqual(actor.player_stamina, 265)

    def test_guaranteed_hit_rapid_shot_uses_shared_physical_multiplier(self):
        engine, actor = self.engine(12)
        actor.preset_index = 3
        actor.roll_percent = lambda rate: rate == actor.presets[3].skill.activation_rate
        before = engine.player_hp
        expected = int(5600 * 1.5 - engine.get_player_stat("vitality") * 0.5)
        self.act(engine)
        self.assertEqual(before - engine.player_hp, expected)
        self.assertEqual(actor.preset_index, 4)

    def test_healing_buff_is_local_and_expires_after_three_following_actions(self):
        engine, actor = self.engine()
        actor.preset_index = 2
        actor.player_hp -= 5000
        self.act(engine)
        self.assertEqual(actor.player_hp, 24000 + 1300)
        self.assertEqual(actor.healing_shield_turns, 3)
        actor.remaining_uses = {key: 0 for key in actor.remaining_uses}
        for _ in range(3):
            self.act(engine)
        self.assertEqual(actor.healing_shield_turns, 0)
        self.assertEqual(engine.healing_shield_turns, 0)

    def test_one_hit_kill_skips_next_action_without_advancing_or_spending(self):
        engine, actor = self.engine(10)
        actor.preset_index = 1
        self.act(engine)
        self.assertTrue(actor.skip_next_player_action)
        mp, stamina = actor.player_mp, actor.player_stamina
        with patch.object(actor, "execute_player_skill") as execute:
            self.act(engine)
        execute.assert_not_called()
        self.assertEqual(actor.player_mp, mp)
        self.assertEqual(actor.player_stamina, stamina)
        self.assertEqual(actor.preset_index, 2)

    def test_sleep_arrow_stops_player_and_damage_wakes_player(self):
        engine, actor = self.engine()
        actor.roll_percent = lambda rate: True
        actor.skill_sleep_arrow()
        self.assertEqual(engine.player_combatant.sleep_turns, 3)
        self.assertEqual(engine.player_turn(), "skip")
        self.assertEqual(engine.player_combatant.sleep_turns, 2)
        actor.player_normal_attack()
        self.assertEqual(engine.player_combatant.sleep_turns, 0)

    def test_poison_death_prevents_player_skill(self):
        engine, actor = self.engine()
        actor.roll_percent = lambda rate: True
        actor.skill_poison_arrow()
        self.assertEqual(engine.player_combatant.poison_turns, 5)
        engine.player_hp = 1
        with patch.object(engine, "execute_player_skill") as execute:
            self.assertEqual(engine.player_turn(), "skip")
        execute.assert_not_called()
        self.assertLessEqual(engine.player_hp, 0)

    def test_judgement_paralysis_prevents_player_action(self):
        engine, actor = self.engine(11)
        actor.roll_percent = lambda rate: True
        actor.skill_judgement()
        self.assertEqual(engine.player_combatant.paralysis_turns, 5)
        engine.roll_percent = lambda rate: True
        self.assertEqual(engine.player_turn(), "skip")
        self.assertEqual(engine.player_combatant.paralysis_turns, 4)

    def test_poison_dagger_reduces_player_dex(self):
        engine, actor = self.engine(10)
        before = engine.get_player_stat("dexterity")
        actor.roll_percent = lambda rate: True
        actor.skill_poison_dagger()
        self.assertEqual(engine.get_player_stat("dexterity"), before * 0.97)

    def test_poison_killed_boss_cannot_attack_or_spend_mp(self):
        engine, actor = self.engine()
        actor.player_combatant.poison_turns = 1
        actor.player_hp = 1
        with patch.object(actor, "player_turn") as turn:
            self.act(engine)
        turn.assert_not_called()
        self.assertEqual(actor.player_mp, 7000)

    def test_boss_steel_body_reduces_physical_damage_only(self):
        engine, actor = self.engine(8)
        actor.steel_body_turns = 1
        before = actor.player_hp
        engine.deal_target_damage(100)
        self.assertEqual(before - actor.player_hp, 60)
        before = actor.player_hp
        engine.deal_target_damage(100, magic=True)
        self.assertEqual(before - actor.player_hp, 100)

    def test_boss_counter_and_reflection_are_bounded_and_target_player(self):
        engine, actor = self.engine(10)
        actor.shadow_step_turns = 3
        actor.counter_stance_turns = 2
        actor.counter_remaining = 3
        engine.counter_stance_turns = 2
        engine.counter_remaining = 3
        before = engine.player_hp
        engine.deal_target_damage(100)
        self.assertLessEqual(engine.player_hp, before - 40)
        self.assertEqual(actor.counter_remaining, 2)
        self.assertEqual(engine.counter_remaining, 3)

    def test_reflection_death_stops_remaining_stella_hits(self):
        engine, actor = self.engine()
        engine.shadow_step_turns = 3
        actor.player_hp = 1
        before = engine.player_hp
        with patch("apps.battle.engine.skills.wizard.random.randint", return_value=5):
            actor.skill_stella()
        self.assertLessEqual(actor.player_hp, 0)
        expected = int(1600 * 0.7 - engine.get_player_stat("intelligence") * 0.3)
        self.assertEqual(before - engine.player_hp, expected)

    def test_missing_skill_is_reported(self):
        boss = Enemy.objects.get(floor=7, is_boss=True)
        boss.skill_codes = ["missing_skill"]
        with self.assertRaisesMessage(ValueError, "未登録"):
            BattleEngine(self.character, boss)

    def test_normal_enemy_retains_legacy_action_and_no_fatigue(self):
        mob = Enemy.objects.filter(floor=1, is_boss=False).first()
        engine = BattleEngine(self.character, mob)
        self.assertIsNone(engine.enemy_combatant.skill_actor)
        self.assertIsNone(engine.enemy_combatant.stamina)
        with patch.object(engine, "enemy_attack") as attack:
            engine.enemy_turn()
        attack.assert_called_once()

    def test_all_boss_skills_execute_against_player_without_db_writes(self):
        for floor in range(7, 13):
            engine, actor = self.engine(floor)
            for preset in actor.presets:
                if preset.skill.is_passive:
                    continue
                with self.subTest(floor=floor, skill=preset.skill.code):
                    # Every assigned skill must be executable, including support and reactions.
                    actor.execute_player_skill(preset.skill)
            self.assertTrue(engine.logs)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_hp, 1000000)
        self.assertEqual(self.character.current_mp, 100000)

    def test_run_records_boss_skill_mp_in_timeline_and_keeps_db_unchanged(self):
        self.character.max_hp = self.character.current_hp = 2000
        self.character.strength = 1
        engine, actor = self.engine()
        with patch("apps.battle.engine.skills.wizard.random.randint", return_value=4):
            result = engine.run()
        self.assertEqual(result["winner"], "enemy")
        turns = [turn for turn in result["timeline"] if turn["side"] == "enemy"]
        self.assertTrue(turns)
        self.assertEqual(turns[0]["opponents"][0]["mp"],
                         7000 - actor.presets[0].skill.mp_cost)
        self.assertTrue(any("ステラ" in log for log in turns[0]["logs"]))
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_hp, 1000000)
        boss = Enemy.objects.get(floor=7, is_boss=True)
        self.assertEqual(boss.max_mp, 7000)

    def test_early_boss_uses_normal_attack_and_its_specified_stamina(self):
        engine, actor = self.engine(2)
        self.assertEqual(actor.presets, [])
        with patch.object(actor, "player_normal_attack") as attack:
            self.act(engine)
        attack.assert_called_once()
        self.assertEqual(actor.player_stamina, 125)
        self.assertEqual(actor.player_mp, 0)

    def test_shadow_step_activation_is_guaranteed_during_stealth(self):
        engine, actor = self.engine(10)
        actor.preset_index = 2
        actor.stealth_active = True
        rates = []
        actor.roll_percent = lambda rate: rates.append(rate) or True
        self.act(engine)
        self.assertEqual(rates, [100])
        self.assertEqual(actor.shadow_step_turns, 3)
        self.assertEqual(actor.preset_index, 3)

    def test_boss_status_skip_ticks_buffs_once_without_spending_stamina(self):
        engine, actor = self.engine()
        actor.player_combatant.sleep_turns = 2
        actor.fighting_spirit_turns = 3
        self.act(engine)
        self.assertEqual(actor.player_combatant.sleep_turns, 1)
        self.assertEqual(actor.fighting_spirit_turns, 2)
        self.assertEqual(actor.player_stamina, 270)
        self.assertEqual(actor.preset_index, 0)
