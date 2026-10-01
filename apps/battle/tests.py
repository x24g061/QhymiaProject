from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Character, User
from apps.accounts.growth import apply_exploration_exp
from apps.battle.models import Enemy
from apps.battle.services import BattleEngine
from apps.battle.combatants import (
    PlayerCombatant,
    EnemyCombatant,
)


class BattleEngineTests(TestCase):

    def setUp(self):
        """
        各テストで使う
        プレイヤーと敵を作成する。
        """

        self.user = User.objects.create_user(
            user_id="battle_test_user",
            email="battle@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="テスト勇者",
            race="human",
            job="wanderer",
        )

        self.enemy = Enemy.objects.create(
            name="テストスライム",
            max_hp=30,
            max_mp=0,
            strength=5,
            intelligence=3,
            dexterity=4,
            agility=4,
            vitality=4,
            luck=3,
            attribute="grass",
            exp_min=7,
            exp_max=12,
        )

        self.engine = BattleEngine(
            self.character,
            self.enemy,
        )


    def test_hit_rate(self):
        """
        命中率計算が仕様通りか確認する。

        DEX=10
        AGI=10

        60 + 39 × 10 / 20
        = 79.5
        """

        hit_rate = (
            self.engine.calculate_hit_rate(
                attacker_dex=10,
                defender_agi=10,
            )
        )

        self.assertAlmostEqual(
            hit_rate,
            79.5,
        )


    def test_critical_rate(self):
        """
        クリティカル率計算が仕様通りか確認する。

        LUK=10
        敵LUK=10

        5 + 45 × 10 / 20
        = 27.5
        """

        critical_rate = (
            self.engine.calculate_critical_rate(
                attacker_luck=10,
                defender_luck=10,
            )
        )

        self.assertAlmostEqual(
            critical_rate,
            27.5,
        )


    def test_physical_damage(self):
        """
        通常の物理ダメージ計算を確認する。

        STR=10
        敵VIT=4

        10 - (4 × 0.5)
        = 8
        """

        damage = (
            self.engine.calculate_physical_damage(
                strength=10,
                defender_vit=4,
            )
        )

        self.assertEqual(
            damage,
            8,
        )


    def test_main_attribute_is_neutral_when_all_zero(self):
        """
        全属性0なら無属性になることを確認。
        """

        self.assertEqual(
            self.character.get_main_attribute(),
            "neutral",
        )


    def test_main_attribute_is_fire(self):
        """
        炎だけ十分高い場合、
        得意属性が炎になることを確認。
        """

        self.character.fire = 10

        self.character.water = 1
        self.character.grass = 1
        self.character.rock = 1
        self.character.light = 1
        self.character.dark = 1

        self.assertEqual(
            self.character.get_main_attribute(),
            "fire",
        )

    def test_win_gives_exp(self):
        """
        戦闘に勝利した場合、
        敵に設定された範囲のEXPを取得できることを確認。
        """

        # 敵を倒した状態にして
        # 戦闘終了時の報酬処理だけ確認する
        self.engine.enemy_hp = 0

        # randintの結果を10に固定する
        # ランダムのままだとテスト結果が毎回変わるため
        with patch(
            "apps.battle.services.random.randint",
            return_value=10,
        ):
            result = self.engine.run()

        self.assertEqual(
            result["winner"],
            "player",
        )

        self.assertEqual(
            result["exp_gained"],
            10,
        )


    def test_level_up_with_100_exp(self):
        """
        EXPが100に到達したとき、
        1レベル上がることを確認。
        """

        # あと1EXPでレベルアップする状態
        self.character.exp = 99

        # 回復処理も確認するため減らしておく
        self.character.current_hp = 1
        self.character.current_mp = 1

        result = apply_exploration_exp(
            self.character,
            1,
        )

        # Lv1 → Lv2
        self.assertEqual(
            self.character.level,
            2,
        )

        # 100EXPを使ったので残り0
        self.assertEqual(
            self.character.exp,
            0,
        )

        # レベルアップ回数
        self.assertEqual(
            result["level_up_count"],
            1,
        )

        # 探索終了時に全回復する
        self.assertEqual(
            self.character.current_hp,
            self.character.max_hp,
        )

        self.assertEqual(
            self.character.current_mp,
            self.character.max_mp,
        )


    def test_multiple_level_up(self):
        """
        大量のEXPを獲得した場合、
        複数レベルアップできることを確認。

        250EXP
        ↓
        100EXP消費 → Lv2
        100EXP消費 → Lv3
        残り50EXP
        """

        result = apply_exploration_exp(
            self.character,
            250,
        )

        self.assertEqual(
            self.character.level,
            3,
        )

        self.assertEqual(
            self.character.exp,
            50,
        )

        self.assertEqual(
            result["level_up_count"],
            2,
        )

        self.assertEqual(
            result["remaining_exp"],
            50,
        )


    def test_priest_max_hp_and_mp_bonus(self):
        """
        プリーストは戦闘中、
        最大HP・MPが5%上昇することを確認。
        """

        self.character.job = "priest"

        self.character.max_hp = 100
        self.character.current_hp = 100

        self.character.max_mp = 100
        self.character.current_mp = 100

        engine = BattleEngine(
            self.character,
            self.enemy,
        )

        # 100 × 1.05 = 105
        self.assertEqual(
            engine.player_max_hp,
            105,
        )

        self.assertEqual(
            engine.player_hp,
            105,
        )

        self.assertEqual(
            engine.player_max_mp,
            105,
        )

        self.assertEqual(
            engine.player_mp,
            105,
        )


    def test_battle_engine_has_combatants(self):
        """
        BattleEngine生成時に
        プレイヤーと敵の戦闘用オブジェクトが
        正しく作られることを確認する。
        """

        self.assertEqual(
            self.engine.player_combatant.character,
            self.character,
        )

        self.assertEqual(
            self.engine.enemy_combatant.enemy,
            self.enemy,
        )

        self.assertEqual(
            self.engine.player_combatant.hp,
            self.engine.player_hp,
        )

        self.assertEqual(
            self.engine.enemy_combatant.hp,
            self.engine.enemy_hp,
        )


    def test_player_hp_is_managed_by_combatant(self):
        """
        BattleEngineのplayer_hpが
        PlayerCombatantのHPと同期していることを確認。
        """

        # BattleEngine側からHPを変更
        self.engine.player_hp -= 10

        self.assertEqual(
            self.engine.player_hp,
            20,
        )

        self.assertEqual(
            self.engine.player_combatant.hp,
            20,
        )

        # PlayerCombatant側から変更しても
        # BattleEngine側に反映される
        self.engine.player_combatant.hp = 15

        self.assertEqual(
            self.engine.player_hp,
            15,
        )


    def test_player_mp_is_managed_by_combatant(self):
        """
        BattleEngineのplayer_mpが
        PlayerCombatantのMPと同期していることを確認。
        """

        # BattleEngine側からMPを変更
        self.engine.player_mp -= 3

        self.assertEqual(
            self.engine.player_mp,
            7,
        )

        self.assertEqual(
            self.engine.player_combatant.mp,
            7,
        )

        # PlayerCombatant側から変更しても
        # BattleEngine側に反映される
        self.engine.player_combatant.mp = 5

        self.assertEqual(
            self.engine.player_mp,
            5,
        )


    def test_enemy_hp_is_managed_by_combatant(self):
        """
        BattleEngineのenemy_hpが
        EnemyCombatantのHPと同期していることを確認。
        """

        # BattleEngine側からダメージ
        self.engine.enemy_hp -= 10

        self.assertEqual(
            self.engine.enemy_hp,
            20,
        )

        self.assertEqual(
            self.engine.enemy_combatant.hp,
            20,
        )

        # EnemyCombatant側から変更しても
        # BattleEngine側へ反映される
        self.engine.enemy_combatant.hp = 5

        self.assertEqual(
            self.engine.enemy_hp,
            5,
        )


    def test_enemy_status_is_managed_by_combatant(self):
        """
        敵の状態異常が
        EnemyCombatant側で管理されることを確認。
        """

        # BattleEngine側から変更
        self.engine.enemy_sleep_turns = 2
        self.engine.enemy_poison_turns = 5
        self.engine.enemy_paralysis_turns = 3
        self.engine.enemy_dex_debuff_rate = 0.03

        # EnemyCombatant側にも反映されている
        self.assertEqual(
            self.engine.enemy_combatant.sleep_turns,
            2,
        )

        self.assertEqual(
            self.engine.enemy_combatant.poison_turns,
            5,
        )

        self.assertEqual(
            self.engine.enemy_combatant.paralysis_turns,
            3,
        )

        self.assertEqual(
            self.engine.enemy_combatant.dex_debuff_rate,
            0.03,
        )

        # EnemyCombatant側から変更しても
        # BattleEngine側から確認できる
        self.engine.enemy_combatant.poison_turns = 1

        self.assertEqual(
            self.engine.enemy_poison_turns,
            1,
        )


class CombatantTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            user_id="combatant_test_user",
            email="combatant@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="戦闘テスト",
            race="human",
            job="wanderer",
        )

        self.enemy = Enemy.objects.create(
            name="戦闘用スライム",
            max_hp=30,
            max_mp=0,
            strength=5,
            intelligence=3,
            dexterity=4,
            agility=4,
            vitality=4,
            luck=3,
            attribute="grass",
            exp_min=7,
            exp_max=12,
        )


    def test_enemy_combatant(self):
        """
        敵の戦闘用オブジェクトが
        正しく作られることを確認する。
        """

        enemy = EnemyCombatant(
            self.enemy
        )

        self.assertEqual(
            enemy.hp,
            30,
        )

        self.assertTrue(
            enemy.is_alive()
        )

        enemy.take_damage(10)

        self.assertEqual(
            enemy.hp,
            20,
        )


    def test_priest_combatant_bonus(self):
        """
        プリーストのHP・MP補正を確認する。
        """

        self.character.job = "priest"

        self.character.max_hp = 100
        self.character.current_hp = 100

        self.character.max_mp = 100
        self.character.current_mp = 100

        player = PlayerCombatant(
            self.character
        )

        self.assertEqual(
            player.max_hp,
            105,
        )

        self.assertEqual(
            player.hp,
            105,
        )

        self.assertEqual(
            player.max_mp,
            105,
        )

        self.assertEqual(
            player.mp,
            105,
        )