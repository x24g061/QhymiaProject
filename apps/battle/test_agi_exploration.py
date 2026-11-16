from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.battle.services import BattleEngine
from apps.battle.combatants import EnemyCombatant


class ExplorationAGITests(SimpleTestCase):

    def build_engine(self, player_agi, enemy_agis):
        engine = BattleEngine.__new__(BattleEngine)

        engine.character = SimpleNamespace(name="冒険者")
        engine.player_combatant = SimpleNamespace(
            hp=1000,
            mp=100,
            stamina=100,
            max_stamina=100,
            initiative=0.0,
        )
        engine.player_max_hp = 1000
        engine.player_max_mp = 100
        engine.current_enemy_index = 0
        engine.floor = 1
        engine.logs = []

        engine.enemy_combatants = [
            EnemyCombatant(SimpleNamespace(
                name=f"敵{i + 1}",
                agility=agi,
                max_hp=200,
                max_mp=10,
                attribute="neutral",
            ))
            for i, agi in enumerate(enemy_agis)
        ]

        engine.get_player_stat = lambda name: player_agi
        engine.finish_player_action = lambda code: None

        return engine

    def run_engine(self, engine):
        with (
            patch(
                "apps.battle.engine.core.exploration_turn_snapshot",
                return_value={},
            ),
            patch(
                "apps.battle.engine.state.random.choice",
                side_effect=lambda choices: choices[0],
            ),
        ):
            return engine.run()

    def test_three_enemies_action_order(self):
        """3体の敵とプレイヤーの行動順を確認。"""
        engine = self.build_engine(50, [100, 80, 20])
        actions = []

        def player_turn():
            actions.append("player")
            return "normal"

        def enemy_turn():
            actions.append(
                f"enemy{engine.current_enemy_index}"
            )
            if len(actions) == 5:
                engine.player_hp = 0

        engine.player_turn = player_turn
        engine.enemy_turn = enemy_turn

        result = self.run_engine(engine)

        # 3ループ目はenemy0とplayerが同時到達するため、
        # 有効AGIの高いenemy0が先に行動する。
        self.assertEqual(actions, [
            "enemy0",
            "enemy1",
            "enemy0",
            "player",
            "enemy1",
        ])
        self.assertEqual(result["winner"], "enemy")

    def test_defeated_enemy_cannot_act(self):
        """行動前に倒された敵は攻撃できない。"""
        engine = self.build_engine(100, [100, 40, 30])
        actions = []

        def player_turn():
            actions.append("player")

            if actions.count("player") == 1:
                engine.enemy_combatants[0].hp = 0

            return "normal"

        def enemy_turn():
            actions.append(
                f"enemy{engine.current_enemy_index}"
            )
            engine.player_hp = 0

        engine.player_turn = player_turn
        engine.enemy_turn = enemy_turn

        self.run_engine(engine)

        self.assertEqual(actions, [
            "player",
            "player",
            "enemy1",
        ])
        self.assertEqual(
            engine.enemy_combatants[0].hp, 0
        )
