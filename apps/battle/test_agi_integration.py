from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.battle.arena_engine import ArenaBattleEngine


class ArenaAGIIntegrationTests(SimpleTestCase):

    def build_engine(self, challenger_agi, defender_agi):
        """
        実際の闘技場run()を使用する。
        攻撃ダメージだけ無効化し、
        行動順と回数を検証する。
        """
        engine = ArenaBattleEngine.__new__(
            ArenaBattleEngine
        )

        engine.challenger = SimpleNamespace(
            name="挑戦者",
            agility=challenger_agi,
        )

        engine.defender = SimpleNamespace(
            name="防衛者",
            agility=defender_agi,
        )

        engine.challenger_combatant = SimpleNamespace(
            hp=10000,
            mp=100,
            stamina=100,
            initiative=0.0,
        )

        engine.defender_combatant = SimpleNamespace(
            hp=10000,
            mp=100,
            stamina=100,
            initiative=0.0,
        )

        engine.logs = []
        engine.turn_timeline = []

        engine.get_combat_stat = (
            lambda character, combatant, stat_name:
            character.agility
        )

        actions = []

        engine.challenger_normal_attack = (
            lambda: actions.append("challenger")
        )

        engine.defender_normal_attack = (
            lambda: actions.append("defender")
        )

        return engine, actions

    def run_engine(self, engine, loops):
        with patch(
            "apps.battle.arena_engine.arena_turn_snapshot",
            return_value={},
        ):
            return engine.run(max_ticks=loops)

    def test_agi_three_to_one(self):
        engine, actions = self.build_engine(3000, 1000)

        result = self.run_engine(engine, 20)

        self.assertEqual(
            actions.count("challenger"), 18
        )
        self.assertEqual(
            actions.count("defender"), 6
        )
        self.assertEqual(result["tick_count"], 20)

    def test_equal_agi(self):
        engine, actions = self.build_engine(1000, 1000)

        self.run_engine(engine, 20)

        self.assertEqual(
            actions.count("challenger"), 18
        )
        self.assertEqual(
            actions.count("defender"), 18
        )

    def test_faster_defender_acts_first(self):
        engine, actions = self.build_engine(70, 100)

        self.run_engine(engine, 2)

        self.assertEqual(
            actions,
            ["defender", "challenger"],
        )

    def test_maximum_one_action_per_loop(self):
        engine, actions = self.build_engine(100, 100)

        # 大量の余剰ゲージを持たせる
        engine.challenger_combatant.initiative = 250

        self.run_engine(engine, 1)

        self.assertEqual(
            actions.count("challenger"), 1
        )
        self.assertEqual(
            actions.count("defender"), 0
        )

        # 250 + 90 - 100 = 240
        self.assertEqual(
            engine.challenger_combatant.initiative,
            240,
        )

    def test_reference_agi_stays_fixed(self):
        engine, actions = self.build_engine(100, 50)

        def challenger_attack():
            actions.append("challenger")

            # 行動後にAGIが低下
            engine.challenger.agility = 20

        engine.challenger_normal_attack = challenger_attack

        self.run_engine(engine, 3)

        # 基準AGIは開始時の100のまま
        self.assertEqual(
            actions,
            ["challenger", "defender"],
        )

        self.assertAlmostEqual(
            engine.challenger_combatant.initiative,
            98.0,
        )
        self.assertAlmostEqual(
            engine.defender_combatant.initiative,
            35.0,
        )

    def test_stamina_reduces_action_frequency(self):
        """疲労によって行動回数が減少する。"""
        from apps.battle.engine.character_stats import (
            get_stamina_stat_multiplier,
        )

        engine, actions = self.build_engine(100, 100)

        def effective_stat(character, combatant, stat_name):
            return character.agility * get_stamina_stat_multiplier(
                combatant.stamina, 100
            )

        engine.get_combat_stat = effective_stat

        def fatigued_attack():
            actions.append("challenger")
            engine.challenger_combatant.stamina = max(
                0,
                engine.challenger_combatant.stamina - 10,
            )

        engine.challenger_normal_attack = fatigued_attack

        self.run_engine(engine, 20)

        self.assertEqual(actions.count("challenger"), 12)
        self.assertEqual(actions.count("defender"), 18)
        self.assertEqual(engine.challenger_combatant.stamina, 0)

    def test_agility_buff_keeps_reference_fixed(self):
        """AGI上昇後も基準AGIを更新しない。"""
        engine, actions = self.build_engine(100, 50)

        def buff_attack():
            actions.append("challenger")
            engine.challenger.agility = 1000

        engine.challenger_normal_attack = buff_attack

        self.run_engine(engine, 5)

        self.assertEqual(actions.count("challenger"), 4)
        self.assertEqual(actions.count("defender"), 2)

        # 基準100のまま、バフ後の増加量は上限95
        self.assertAlmostEqual(
            engine.challenger_combatant.initiative,
            65.0,
        )
        self.assertAlmostEqual(
            engine.defender_combatant.initiative,
            25.0,
        )
