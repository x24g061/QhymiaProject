from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Character, User
from apps.accounts.growth import apply_exploration_exp
from apps.battle.models import Enemy
from apps.battle.services import BattleEngine


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