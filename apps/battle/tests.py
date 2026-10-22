from unittest.mock import patch
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Character, User
from apps.accounts.growth import apply_exploration_exp
from apps.accounts.growth import apply_character_exp
from apps.battle.models import Enemy
from apps.battle.services import BattleEngine
from apps.battle.combatants import (
    PlayerCombatant,
    EnemyCombatant,
)
from apps.inventory.models import (
    Equipment,
    InventoryItem,
    Item,
    OwnedEquipment,
)
from apps.battle.models import (
    Enemy,
    FloorDropItem,
    FloorProgress,
)
from apps.battle.progression import (
    get_max_unlocked_floor,
    should_encounter_boss,
)
from apps.battle.drops import (
    grant_exploration_drop,
)
from apps.battle.arena_engine import (
    ArenaBattleEngine,
)
from apps.battle.models import (
    ArenaFloor,
    ArenaState,
)
from apps.battle.arena_services import (
    claim_vacant_arena_floor,
)
from apps.battle.arena_services import challenge_arena_master
from apps.battle.models import ArenaBattleHistory


class PlayerCombatantArenaTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="arena_combatant_user",
            email="arena_combatant@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="闘技場戦士",
            race="human",
            job="wanderer",
            max_hp=100,
            current_hp=80,
            max_mp=50,
            current_mp=40,
        )

    def test_arena_starting_hp_and_mp_override_character_values(self):
        """
        闘技場用HP / MPを指定した場合、
        Character.current_hp / current_mpではなく
        指定値から戦闘を開始する。
        """

        combatant = PlayerCombatant(
            self.character,
            starting_stamina=100,
            starting_hp=25,
            starting_mp=12,
        )

        self.assertEqual(
            combatant.hp,
            25,
        )

        self.assertEqual(
            combatant.mp,
            12,
        )

        self.assertEqual(
            combatant.stamina,
            100,
        )

    def test_default_starting_hp_and_mp_still_use_character_values(self):
        """
        闘技場用HP / MPを指定しない場合は、
        従来通りCharacterの値を使用する。
        """

        combatant = PlayerCombatant(
            self.character,
        )

        self.assertEqual(
            combatant.hp,
            80,
        )

        self.assertEqual(
            combatant.mp,
            40,
        )


class ArenaBattleEngineTests(TestCase):

    def setUp(self):
        self.challenger_user = User.objects.create_user(
            user_id="arena_challenger",
            email="arena_challenger@example.com",
            password="testpass123",
        )

        self.defender_user = User.objects.create_user(
            user_id="arena_defender",
            email="arena_defender@example.com",
            password="testpass123",
        )

        self.challenger = Character.objects.create(
            user=self.challenger_user,
            name="挑戦者",
            max_hp=100,
            current_hp=100,
            max_mp=50,
            current_mp=50,
        )

        self.defender = Character.objects.create(
            user=self.defender_user,
            name="防衛者",
            max_hp=120,
            current_hp=120,
            max_mp=60,
            current_mp=60,
        )

        self.floor = ArenaFloor.objects.get(
            floor=1,
        )

        self.challenger_state = ArenaState.objects.create(
            character=self.challenger,
            floor=self.floor,
            current_hp=35,
            current_mp=20,
        )

        self.defender_state = ArenaState.objects.create(
            character=self.defender,
            floor=self.floor,
            current_hp=70,
            current_mp=15,
        )

    def test_arena_engine_uses_arena_hp_and_mp(self):
        engine = ArenaBattleEngine(
            challenger=self.challenger,
            defender=self.defender,
            challenger_state=self.challenger_state,
            defender_state=self.defender_state,
        )

        self.assertEqual(
            engine.challenger_hp,
            35,
        )

        self.assertEqual(
            engine.challenger_mp,
            20,
        )

        self.assertEqual(
            engine.defender_hp,
            70,
        )

        self.assertEqual(
            engine.defender_mp,
            15,
        )

    def test_arena_stamina_always_starts_at_100(self):
        engine = ArenaBattleEngine(
            challenger=self.challenger,
            defender=self.defender,
            challenger_state=self.challenger_state,
            defender_state=self.defender_state,
        )

        self.assertEqual(
            engine.challenger_combatant.stamina,
            100,
        )

        self.assertEqual(
            engine.defender_combatant.stamina,
            100,
        )

    def test_cannot_battle_against_self(self):
        with self.assertRaises(ValueError):
            ArenaBattleEngine(
                challenger=self.challenger,
                defender=self.challenger,
                challenger_state=self.challenger_state,
                defender_state=self.challenger_state,
            )


    # ========================================
    # PvP通常攻撃：ミス
    # ========================================

    def test_challenger_normal_attack_miss(self):
        engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        with patch(
            "apps.battle.arena_engine.roll_percent",
            return_value=False,
        ):
            result = engine.challenger_normal_attack()

        self.assertFalse(result["hit"])
        self.assertEqual(result["damage"], 0)

        # 防衛者のHPは減らない
        self.assertEqual(engine.defender_hp, 70)

        # ミスしてもSTは5消費
        self.assertEqual(
            engine.challenger_combatant.stamina,
            95,
        )


    # ========================================
    # PvP通常攻撃：命中
    # ========================================

    def test_challenger_normal_attack_hit(self):
        engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        # 命中成功・クリティカル失敗
        with patch(
            "apps.battle.arena_engine.roll_percent",
            side_effect=[True, False],
        ):
            result = engine.challenger_normal_attack()

        self.assertTrue(result["hit"])
        self.assertFalse(result["critical"])
        self.assertGreater(result["damage"], 0)

        self.assertEqual(
            engine.defender_hp,
            max(0, 70 - result["damage"]),
        )

        self.assertEqual(
            engine.challenger_combatant.stamina,
            95,
        )


    # ========================================
    # PvP通常攻撃：防衛者も攻撃できる
    # ========================================

    def test_defender_normal_attack(self):
        engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        with patch(
            "apps.battle.arena_engine.roll_percent",
            side_effect=[True, False],
        ):
            result = engine.defender_normal_attack()

        self.assertTrue(result["hit"])
        self.assertGreater(result["damage"], 0)

        # 挑戦者がダメージを受ける
        self.assertEqual(
            engine.challenger_hp,
            max(0, 35 - result["damage"]),
        )

        # 防衛者のSTが減る
        self.assertEqual(
            engine.defender_combatant.stamina,
            95,
        )


    # ========================================
    # PvP通常攻撃：クリティカル
    # ========================================

    def test_critical_attack_increases_damage(self):
        normal_engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        critical_engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        # 通常命中
        with patch(
            "apps.battle.arena_engine.roll_percent",
            side_effect=[True, False],
        ):
            normal_result = (
                normal_engine.challenger_normal_attack()
            )

        # クリティカル命中
        with patch(
            "apps.battle.arena_engine.roll_percent",
            side_effect=[True, True],
        ):
            critical_result = (
                critical_engine.challenger_normal_attack()
            )

        self.assertTrue(critical_result["critical"])

        self.assertGreater(
            critical_result["damage"],
            normal_result["damage"],
        )


    # ========================================
    # 自動戦闘：挑戦者の勝利
    # ========================================

    def test_run_challenger_wins(self):

        self.challenger.agility = 100
        self.defender.agility = 100

        engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        engine.defender_hp = 1

        with patch(
            "apps.battle.arena_engine.roll_percent",
            return_value=True,
        ):
            result = engine.run(max_ticks=5)

        self.assertEqual(
            result["winner"],
            "challenger",
        )

        self.assertEqual(
            engine.defender_hp,
            0,
        )

        # 倒された防衛者は行動しない
        self.assertEqual(
            engine.defender_combatant.stamina,
            100,
        )


    # ========================================
    # 自動戦闘：防衛者の勝利
    # ========================================

    def test_run_defender_wins(self):

        self.challenger.agility = 0
        self.defender.agility = 100

        engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        engine.challenger_hp = 1

        with patch(
            "apps.battle.arena_engine.roll_percent",
            return_value=True,
        ):
            result = engine.run(max_ticks=5)

        self.assertEqual(
            result["winner"],
            "defender",
        )

        self.assertEqual(
            engine.challenger_hp,
            0,
        )


    # ========================================
    # 自動戦闘：引き分け
    # ========================================

    def test_run_draw(self):

        engine = ArenaBattleEngine(
            self.challenger,
            self.defender,
            self.challenger_state,
            self.defender_state,
        )

        result = engine.run(max_ticks=1)

        self.assertEqual(
            result["winner"],
            "draw",
        )

        self.assertGreater(
            engine.challenger_hp,
            0,
        )

        self.assertGreater(
            engine.defender_hp,
            0,
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


    def test_enemy_initiative_is_managed_by_combatant(self):
        """
        敵のイニシアチブが
        EnemyCombatant側で管理されることを確認。
        """

        # BattleEngine側から変更
        self.engine.enemy_initiative += 25

        self.assertEqual(
            self.engine.enemy_initiative,
            25,
        )

        self.assertEqual(
            self.engine.enemy_combatant.initiative,
            25,
        )

        # EnemyCombatant側から変更しても
        # BattleEngine側から確認できる
        self.engine.enemy_combatant.initiative = 80

        self.assertEqual(
            self.engine.enemy_initiative,
            80,
        )


    def test_player_initiative_is_managed_by_combatant(self):
        """
        プレイヤーのイニシアチブが
        PlayerCombatant側で管理されることを確認。
        """

        # BattleEngine側から変更
        self.engine.player_initiative += 30

        self.assertEqual(
            self.engine.player_initiative,
            30,
        )

        self.assertEqual(
            self.engine.player_combatant.initiative,
            30,
        )

        # PlayerCombatant側から変更
        self.engine.player_combatant.initiative = 75

        self.assertEqual(
            self.engine.player_initiative,
            75,
        )


    def test_enemy_combatants_are_managed_as_list(self):
        """
        敵がリストで管理され、
        現在の敵も正しく取得できることを確認。
        """

        # 現在は1体だけ
        self.assertEqual(
            len(self.engine.enemy_combatants),
            1,
        )

        # 現在の敵はリストの先頭
        self.assertEqual(
            self.engine.enemy_combatant,
            self.engine.enemy_combatants[0],
        )

        # 生存している敵は1体
        alive_enemies = (
            self.engine
            .get_alive_enemy_combatants()
        )

        self.assertEqual(
            len(alive_enemies),
            1,
        )

        # HPを0にする
        self.engine.enemy_hp = 0

        # 生存敵が0体になる
        alive_enemies = (
            self.engine
            .get_alive_enemy_combatants()
        )

        self.assertEqual(
            len(alive_enemies),
            0,
        )


    def test_select_random_alive_enemy(self):
        """
        生存している敵の中から
        ランダムでターゲットを選べることを確認。
        """

        second_enemy_data = Enemy.objects.create(
            name="2体目スライム",
            max_hp=40,
            max_mp=0,
            strength=6,
            intelligence=3,
            dexterity=5,
            agility=5,
            vitality=5,
            luck=3,
            attribute="grass",
            exp_min=7,
            exp_max=12,
        )

        second_enemy = EnemyCombatant(
            second_enemy_data
        )

        self.engine.enemy_combatants.append(
            second_enemy
        )

        # ランダム選択結果を
        # 2体目(index=1)に固定する
        with patch(
            "apps.battle.services.random.choice",
            return_value=1,
        ):
            result = (
                self.engine
                .select_random_alive_enemy()
            )

        self.assertTrue(result)

        self.assertEqual(
            self.engine.current_enemy_index,
            1,
        )

        self.assertEqual(
            self.engine.enemy.name,
            "2体目スライム",
        )

        self.assertEqual(
            self.engine.enemy_hp,
            40,
        )


    def test_battle_with_two_enemies(self):
        """
        敵が2体いる場合、
        1体倒しても戦闘が終了せず、
        全員倒すまで戦闘が続くことを確認。
        """

        second_enemy_data = Enemy.objects.create(
            name="2体目スライム",
            max_hp=1,
            max_mp=0,
            strength=1,
            intelligence=1,
            dexterity=1,
            agility=1,
            vitality=1,
            luck=1,
            attribute="grass",
            exp_min=7,
            exp_max=12,
        )

        second_enemy = EnemyCombatant(
            second_enemy_data
        )

        self.engine.enemy_combatants.append(
            second_enemy
        )

        # 1体目もすぐ倒せるようにする
        self.engine.enemy_combatants[0].hp = 1

        # プレイヤーを十分強くする
        self.character.strength = 100
        self.character.dexterity = 100
        self.character.agility = 100

        # 命中判定などを成功固定
        with patch.object(
            BattleEngine,
            "roll_percent",
            return_value=True,
        ):
            result = self.engine.run()

        self.assertEqual(
            result["winner"],
            "player",
        )

        # 2体とも倒れている
        self.assertEqual(
            len(
                self.engine
                .get_alive_enemy_combatants()
            ),
            0,
        )


    def test_battle_engine_accepts_three_enemies(self):
        """
        BattleEngineが最大3体の敵を
        受け取れることを確認。
        """

        enemy2 = Enemy.objects.create(
            name="テストゴブリン",
            max_hp=30,
            max_mp=0,
            strength=5,
            intelligence=3,
            dexterity=5,
            agility=5,
            vitality=5,
            luck=3,
            attribute="neutral",
            exp_min=7,
            exp_max=12,
        )

        enemy3 = Enemy.objects.create(
            name="テストウルフ",
            max_hp=30,
            max_mp=0,
            strength=5,
            intelligence=3,
            dexterity=5,
            agility=7,
            vitality=4,
            luck=4,
            attribute="grass",
            exp_min=7,
            exp_max=12,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
                enemy3,
            ],
        )

        self.assertEqual(
            len(engine.enemy_combatants),
            3,
        )

        self.assertEqual(
            engine.enemy_combatants[0].name,
            self.enemy.name,
        )

        self.assertEqual(
            engine.enemy_combatants[1].name,
            "テストゴブリン",
        )

        self.assertEqual(
            engine.enemy_combatants[2].name,
            "テストウルフ",
        )


    def test_physical_all_attack_hits_all_enemies(self):
        """
        物理全体攻撃が
        生存している敵全員に当たることを確認。
        """

        enemy2 = Enemy.objects.create(
            name="敵2",
            max_hp=30,
            max_mp=0,
            vitality=4,
            agility=4,
            luck=3,
            attribute="grass",
        )

        enemy3 = Enemy.objects.create(
            name="敵3",
            max_hp=30,
            max_mp=0,
            vitality=4,
            agility=4,
            luck=3,
            attribute="grass",
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
                enemy3,
            ],
        )

        # 命中・クリティカル判定を成功固定
        with patch.object(
            engine,
            "roll_percent",
            return_value=True,
        ):
            engine.player_physical_skill_hit_all(
                skill_name="テスト全体攻撃",
                base_damage=10,
                attribute="neutral",
            )

        for enemy in engine.enemy_combatants:
            self.assertLess(
                enemy.hp,
                enemy.max_hp,
            )


    def test_flashbang_targets_all_enemies(self):
        """
        フラッシュバングが
        生存敵全員へ麻痺判定することを確認。
        """

        enemy2 = Enemy.objects.create(
            name="敵2",
            max_hp=30,
            max_mp=0,
        )

        enemy3 = Enemy.objects.create(
            name="敵3",
            max_hp=30,
            max_mp=0,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
                enemy3,
            ],
        )

        with (
            patch.object(
                engine,
                "roll_percent",
                return_value=True,
            ),
            patch(
                "apps.battle.services.random.randint",
                return_value=2,
            ),
        ):
            engine.skill_flashbang()

        for enemy in engine.enemy_combatants:
            self.assertEqual(
                enemy.paralysis_turns,
                2,
            )


    def test_mirage_makes_normal_attack_hit_all_enemies(self):
        """
        蜃気楼の次の通常攻撃が
        敵全体攻撃になることを確認する。
        """

        enemy2 = Enemy.objects.create(
            name="敵2",
            max_hp=30,
            max_mp=0,
            vitality=4,
            agility=4,
            luck=3,
        )

        enemy3 = Enemy.objects.create(
            name="敵3",
            max_hp=30,
            max_mp=0,
            vitality=4,
            agility=4,
            luck=3,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
                enemy3,
            ],
        )

        engine.mirage_active = True

        with patch.object(
            engine,
            "roll_percent",
            return_value=True,
        ):
            engine.player_normal_attack()

        # 全員ダメージを受けている
        for enemy in engine.enemy_combatants:

            self.assertLess(
                enemy.hp,
                enemy.max_hp,
            )

        # 1回使ったので解除される
        self.assertFalse(
            engine.mirage_active
        )


    def test_battle_starts_with_100_stamina(self):
        """
        探索戦闘はDB上のSTに関係なく
        100STから始まることを確認する。
        """

        self.character.current_stamina = 30
        self.character.save(
            update_fields=[
                "current_stamina",
            ]
        )

        engine = BattleEngine(
            self.character,
            self.enemy,
        )

        self.assertEqual(
            engine.player_stamina,
            100,
        )


    def test_stamina_reduces_battle_stats(self):
        """
        ST低下によって
        DEX・AGI・VIT・LUKが低下することを確認する。
        """

        engine = BattleEngine(
            self.character,
            self.enemy,
        )

        target_stats = (
            "dexterity",
            "agility",
            "vitality",
            "luck",
        )

        # ST100時の値
        full_stats = {
            stat: engine.get_player_stat(
                stat
            )
            for stat in target_stats
        }

        # ST50
        engine.player_combatant.stamina = 50

        for stat in target_stats:

            self.assertAlmostEqual(
                engine.get_player_stat(stat),
                full_stats[stat] * 0.75,
            )

        # ST0
        engine.player_combatant.stamina = 0

        for stat in target_stats:

            self.assertAlmostEqual(
                engine.get_player_stat(stat),
                full_stats[stat] * 0.50,
            )


    def test_player_action_consumes_stamina_without_saving_db(self):
        """
        1行動で5ST消費するが、
        CharacterのDB上のSTは変更されないことを確認。
        """

        self.character.current_stamina = 100
        self.character.save(
            update_fields=[
                "current_stamina",
            ]
        )

        engine = BattleEngine(
            self.character,
            self.enemy,
        )

        engine.finish_player_action(
            "normal"
        )

        # 戦闘中は5減る
        self.assertEqual(
            engine.player_stamina,
            95,
        )

        # DBには保存しない
        self.character.refresh_from_db()

        self.assertEqual(
            self.character.current_stamina,
            100,
        )


    def test_enemy_statuses_are_independent(self):
        """
        複数敵の状態異常が
        敵ごとに独立していることを確認する。
        """

        enemy2 = Enemy.objects.create(
            name="状態異常テスト敵2",
            max_hp=30,
            max_mp=0,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
            ],
        )

        # 敵1だけに状態異常を付与
        engine.current_enemy_index = 0

        engine.enemy_poison_turns = 5
        engine.enemy_sleep_turns = 3
        engine.enemy_paralysis_turns = 2

        # 敵2へ切り替える
        engine.current_enemy_index = 1

        # 敵2には影響していない
        self.assertEqual(
            engine.enemy_poison_turns,
            0,
        )

        self.assertEqual(
            engine.enemy_sleep_turns,
            0,
        )

        self.assertEqual(
            engine.enemy_paralysis_turns,
            0,
        )


    def test_sleep_only_stops_affected_enemy(self):
        """
        睡眠状態の敵だけが行動不能になり、
        他の敵は通常通り行動できることを確認する。
        """

        enemy2 = Enemy.objects.create(
            name="睡眠テスト敵2",
            max_hp=30,
            max_mp=0,
            strength=5,
            dexterity=5,
            agility=5,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
            ],
        )

        # 敵1だけ睡眠
        engine.current_enemy_index = 0
        engine.enemy_sleep_turns = 1

        before_hp = engine.player_hp

        # 敵1は眠っているので攻撃できない
        engine.enemy_turn()

        self.assertEqual(
            engine.player_hp,
            before_hp,
        )

        # 敵2へ変更
        engine.current_enemy_index = 1

        # 命中を確定させる
        with patch.object(
            engine,
            "roll_percent",
            return_value=True,
        ):
            engine.enemy_turn()

        # 敵2は普通に攻撃できる
        self.assertLess(
            engine.player_hp,
            before_hp,
        )


    def test_shadow_step_reflects_to_attacking_enemy(self):
        """
        複数敵戦闘でシャドウステップの反射が
        実際に攻撃してきた敵へ返ることを確認する。
        """

        enemy2 = Enemy.objects.create(
            name="反射テスト敵2",
            max_hp=30,
            max_mp=0,
            strength=5,
            dexterity=5,
            agility=5,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
            ],
        )

        engine.shadow_step_turns = 3

        # 敵2が攻撃する
        engine.current_enemy_index = 1

        with patch.object(
            engine,
            "roll_percent",
            return_value=True,
        ):
            engine.enemy_attack()

        # 攻撃していない敵1には反射されない
        self.assertEqual(
            engine.enemy_combatants[0].hp,
            engine.enemy_combatants[0].max_hp,
        )

        # 攻撃した敵2だけ反射ダメージ
        self.assertLess(
            engine.enemy_combatants[1].hp,
            engine.enemy_combatants[1].max_hp,
        )


    def test_counter_hits_attacking_enemy(self):
        """
        複数敵戦闘で反撃が
        実際に攻撃してきた敵へ当たることを確認する。
        """

        enemy2 = Enemy.objects.create(
            name="反撃テスト敵2",
            max_hp=30,
            max_mp=0,
            strength=5,
            dexterity=5,
            agility=5,
            vitality=5,
            luck=3,
        )

        engine = BattleEngine(
            self.character,
            [
                self.enemy,
                enemy2,
            ],
        )

        engine.counter_stance_turns = 2
        engine.counter_remaining = 3

        # 敵2が攻撃する
        engine.current_enemy_index = 1

        with patch.object(
            engine,
            "roll_percent",
            return_value=True,
        ):
            engine.enemy_attack()

        # 敵1は無傷
        self.assertEqual(
            engine.enemy_combatants[0].hp,
            engine.enemy_combatants[0].max_hp,
        )

        # 攻撃した敵2に反撃
        self.assertLess(
            engine.enemy_combatants[1].hp,
            engine.enemy_combatants[1].max_hp,
        )

        # 反撃可能回数も3 → 2
        self.assertEqual(
            engine.counter_remaining,
            2,
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

    def test_equipment_bonus_is_added_to_battle_stat(
        self,
    ):
        """
        装備補正が戦闘ステータスへ
        加算されることを確認。
        """

        item = Item.objects.create(
            name="戦闘テスト鉄の剣",
            category=Item.Category.EQUIPMENT,
        )

        equipment = Equipment.objects.create(
            item=item,
            rank=Equipment.Rank.E,
            slot=Equipment.Slot.WEAPON,
            style=Equipment.Style.PHYSICAL,
            base_battle_power=120,

            strength_rate=60,
            intelligence_rate=0,
            dexterity_rate=20,
            agility_rate=10,
            vitality_rate=0,
            luck_rate=10,
        )

        OwnedEquipment.objects.create(
            character=self.character,
            equipment=equipment,
            battle_power=120,
            is_equipped=True,
        )

        # 元STR5
        # 装備補正+36
        # = 41
        #
        # テストキャラがwandererなので
        # STRには職業補正なし。

        engine = BattleEngine(
            self.character,
            self.enemy,
        )

        self.assertEqual(
            engine.get_player_stat(
                "strength"
            ),
            41,
        )


class ExplorationDropTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            user_id="drop_test_user",
            email="drop@example.com",
            password="testpass123",
        )

        self.character = (
            Character.objects.create(
                user=self.user,
                name="ドロップテスト",
            )
        )


    def test_no_drop_when_roll_fails(self):
        """
        1%抽選に外れた場合、
        何も獲得しない。
        """

        item = Item.objects.create(
            name="テスト素材",
            category=Item.Category.MATERIAL,
        )

        FloorDropItem.objects.create(
            floor=1,
            item=item,
            drop_weight=100,
        )

        with patch(
            "apps.battle.drops.random.random",
            return_value=0.50,
        ):

            result = (
                grant_exploration_drop(
                    self.character,
                    1,
                )
            )

        self.assertIsNone(result)

        self.assertFalse(
            InventoryItem.objects.filter(
                character=self.character,
                item=item,
            ).exists()
        )


    def test_normal_item_drop(self):
        """
        通常アイテムが当選した場合、
        InventoryItemへ追加される。
        """

        item = Item.objects.create(
            name="テスト素材",
            category=Item.Category.MATERIAL,
        )

        FloorDropItem.objects.filter(
        floor=1
        ).delete()

        FloorDropItem.objects.create(
            floor=1,
            item=item,
            drop_weight=100,
        )

        with patch(
            "apps.battle.drops.random.random",
            return_value=0.0,
        ):

            result = (
                grant_exploration_drop(
                    self.character,
                    1,
                )
            )

        inventory = (
            InventoryItem.objects.get(
                character=self.character,
                item=item,
            )
        )

        self.assertEqual(
            inventory.quantity,
            1,
        )

        self.assertEqual(
            result["kind"],
            "item",
        )


    def test_equipment_drop_creates_owned_equipment(
        self,
    ):
        """
        装備品が当選した場合、
        OwnedEquipmentを1つ生成する。
        """

        item = Item.objects.create(
            name="鉄の剣",
            category=Item.Category.EQUIPMENT,
        )

        equipment = Equipment.objects.create(
            item=item,
            rank=Equipment.Rank.E,
            slot=Equipment.Slot.WEAPON,
            style=Equipment.Style.PHYSICAL,

            base_battle_power=120,

            strength_rate=60,
            intelligence_rate=0,
            dexterity_rate=20,
            agility_rate=10,
            vitality_rate=0,
            luck_rate=10,
        )

        FloorDropItem.objects.filter(
            floor=1
        ).delete()


        FloorDropItem.objects.create(
            floor=1,
            item=item,
            drop_weight=100,
        )

        with patch(
            "apps.battle.drops.random.random",
            return_value=0.0,
        ):

            result = (
                grant_exploration_drop(
                    self.character,
                    1,
                )
            )

        owned = (
            OwnedEquipment.objects.get(
                character=self.character,
                equipment=equipment,
            )
        )

        self.assertEqual(
            owned.enhancement_level,
            0,
        )

        self.assertEqual(
            owned.battle_power,
            120,
        )

        self.assertEqual(
            result["kind"],
            "equipment",
        )

        self.assertEqual(
            result["rank"],
            "E",
        )


# ============================================================
# 探索ボス進行テスト
# ============================================================

class ExplorationBossProgressionTests(TestCase):

    def setUp(self):
        """
        ボス探索テスト用の
        ユーザー・キャラクター・ボスを作成する。
        """

        self.user = User.objects.create_user(
            user_id="boss_test_user",
            email="boss_test@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="ボステスト勇者",
            race="human",
            job="wanderer",
        )

        # 1階ボス
        self.boss = Enemy.objects.create(
            name="テストキングスライム",
            floor=1,
            is_boss=True,
            max_hp=150,
            max_mp=20,
            strength=10,
            intelligence=10,
            dexterity=10,
            agility=10,
            vitality=10,
            luck=10,
            attribute="grass",
            exp_min=7,
            exp_max=12,
        )

        self.client.force_login(
            self.user
        )


    def test_boss_appears_with_05_percent_roll(self):
        """
        探索200回未満でも、
        0.5%抽選に当選すれば
        ボスが出現することを確認する。
        """

        progress = FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=1,
        )

        # 0.0049 = 0.49%
        # 0.5%未満なので当選
        with patch(
            "apps.battle.progression.random.random",
            return_value=0.0049,
        ):

            result = should_encounter_boss(
                progress
            )

        self.assertTrue(
            result
        )


    def test_boss_is_guaranteed_at_200_explorations(self):
        """
        0.5%抽選に外れる値でも、
        200回探索していれば
        ボスが確定出現することを確認する。
        """

        progress = FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=200,
        )

        with patch(
            "apps.battle.progression.random.random",
            return_value=0.999,
        ):

            result = should_encounter_boss(
                progress
            )

        self.assertTrue(
            result
        )


    def test_defeated_boss_does_not_reappear(self):
        """
        すでに撃破済みのボスは、
        200回以上探索していても
        再出現しないことを確認する。
        """

        progress = FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=200,
            boss_defeated=True,
        )

        with patch(
            "apps.battle.progression.random.random",
            return_value=0.0,
        ):

            result = should_encounter_boss(
                progress
            )

        self.assertFalse(
            result
        )


    def test_boss_win_unlocks_next_floor(self):
        """
        ボス撃破時に
        boss_defeated=Trueとなり、
        次の階が解放されることを確認する。
        """

        progress = FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=50,
        )

        battle_result = {
            "winner": "player",
            "logs": [],
            "exp_gained": 0,
        }

        with patch(
            "apps.battle.views.should_encounter_boss",
            return_value=True,
        ), patch(
            "apps.battle.views.BattleEngine"
        ) as mock_engine, patch(
            "apps.battle.views.grant_exploration_drop",
            return_value=None,
        ):

            mock_engine.return_value.run.return_value = (
                battle_result
            )

            response = self.client.post(
                reverse(
                    "battle:battle"
                ),
                {
                    "floor": 1,
                },
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        progress.refresh_from_db()

        self.assertTrue(
            progress.boss_defeated
        )

        self.assertEqual(
            get_max_unlocked_floor(
                self.character
            ),
            2,
        )


    def test_boss_loss_resets_exploration_count(self):
        """
        ボス戦に負けた場合、
        その階層の探索回数が
        0へ戻ることを確認する。
        """

        progress = FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=199,
        )

        battle_result = {
            "winner": "enemy",
            "logs": [],
            "exp_gained": 0,
        }

        with patch(
            "apps.battle.views.should_encounter_boss",
            return_value=True,
        ), patch(
            "apps.battle.views.BattleEngine"
        ) as mock_engine:

            mock_engine.return_value.run.return_value = (
                battle_result
            )

            response = self.client.post(
                reverse(
                    "battle:battle"
                ),
                {
                    "floor": 1,
                },
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        progress.refresh_from_db()

        self.assertEqual(
            progress.exploration_count,
            0,
        )

        self.assertFalse(
            progress.boss_defeated
        )


class ArenaVacantClaimTests(TestCase):
    """
    闘技場の空席マスター獲得テスト。
    """

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="arena_claim_user",
            email="arena_claim@example.com",
            password="testpass123",
        )

        self.other_user = User.objects.create_user(
            user_id="arena_claim_other",
            email="arena_claim_other@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="空席挑戦者",
            max_hp=100,
            max_mp=50,
        )

        self.other = Character.objects.create(
            user=self.other_user,
            name="空席先客",
        )

        self.floor = ArenaFloor.objects.get(
            floor=1,
        )

        self.state = ArenaState.objects.create(
            character=self.character,
            floor=self.floor,
            current_hp=20,
            current_mp=10,
        )

    # ========================================
    # 空席獲得成功
    # ========================================

    def test_claim_vacant_floor(self):

        result = claim_vacant_arena_floor(
            self.character
        )

        self.assertEqual(result, "claimed")

        self.floor.refresh_from_db()
        self.state.refresh_from_db()

        self.assertEqual(
            self.floor.master,
            self.character,
        )

        self.assertEqual(
            self.state.current_hp,
            100,
        )

        self.assertEqual(
            self.state.current_mp,
            50,
        )

    # ========================================
    # 既に他プレイヤーがマスター
    # ========================================

    def test_cannot_claim_occupied_floor(self):

        self.floor.master = self.other
        self.floor.save()

        result = claim_vacant_arena_floor(
            self.character
        )

        self.assertEqual(result, "occupied")

        self.floor.refresh_from_db()
        self.state.refresh_from_db()

        self.assertEqual(
            self.floor.master,
            self.other,
        )

        self.assertEqual(
            self.state.current_hp,
            20,
        )

    # ========================================
    # 自分がマスターの場合の再取得禁止
    # ========================================

    def test_already_master_does_not_heal(self):

        claim_vacant_arena_floor(
            self.character
        )

        self.state.current_hp = 5
        self.state.current_mp = 2
        self.state.save()

        result = claim_vacant_arena_floor(
            self.character
        )

        self.state.refresh_from_db()

        self.assertEqual(
            result,
            "already_master",
        )

        self.assertEqual(
            self.state.current_hp,
            5,
        )

        self.assertEqual(
            self.state.current_mp,
            2,
        )

    # ========================================
    # 複数階のマスターになることを防止
    # ========================================

    def test_cannot_master_multiple_floors(self):

        claim_vacant_arena_floor(
            self.character
        )

        floor2 = ArenaFloor.objects.get(
            floor=2,
        )

        self.state.floor = floor2
        self.state.save(
            update_fields=["floor"]
        )

        with self.assertRaises(ValueError):
            claim_vacant_arena_floor(
                self.character
            )

        floor2.refresh_from_db()

        self.assertIsNone(
            floor2.master
        )


    def test_claim_starts_cooldown(self):
        result = claim_vacant_arena_floor(
            self.character
        )

        self.assertEqual(result, "claimed")

        self.character.refresh_from_db()

        remaining = (
            self.character.exploration_cooldown_until
            - timezone.now()
        ).total_seconds()

        self.assertGreater(remaining, 35)
        self.assertLessEqual(remaining, 40)


    def test_cannot_claim_during_cooldown(self):
        self.character.exploration_cooldown_until = (
            timezone.now() + timedelta(seconds=60)
        )
        self.character.save(
            update_fields=["exploration_cooldown_until"]
        )

        with self.assertRaisesRegex(
            ValueError,
            "クールタイム中",
        ):
            claim_vacant_arena_floor(
                self.character
            )

        self.floor.refresh_from_db()
        self.assertIsNone(self.floor.master)


    def test_reduced_claim_cooldown_is_20_seconds(self):
        self.character.exploration_cooldown_reduced_until = (
            timezone.now() + timedelta(days=1)
        )
        self.character.save(
            update_fields=["exploration_cooldown_reduced_until"]
        )

        claim_vacant_arena_floor(self.character)

        self.character.refresh_from_db()

        remaining = (
            self.character.exploration_cooldown_until
            - timezone.now()
        ).total_seconds()

        self.assertGreater(remaining, 15)
        self.assertLessEqual(remaining, 20)


class ArenaMasterChallengeTests(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(
            user_id="arena_master_test1",
            email="arena_master1@example.com",
            password="testpass123",
        )

        self.user2 = User.objects.create_user(
            user_id="arena_master_test2",
            email="arena_master2@example.com",
            password="testpass123",
        )

        self.challenger = Character.objects.create(
            user=self.user1,
            name="マスター挑戦者",
            max_hp=100,
            max_mp=50,
        )

        self.defender = Character.objects.create(
            user=self.user2,
            name="マスター防衛者",
            max_hp=80,
            max_mp=30,
        )

        self.floor = ArenaFloor.objects.get(floor=1)
        self.floor.master = self.defender
        self.floor.save(update_fields=["master"])

        self.challenger_state = ArenaState.objects.create(
            character=self.challenger,
            floor=self.floor,
            current_hp=40,
            current_mp=20,
        )

        self.defender_state = ArenaState.objects.create(
            character=self.defender,
            floor=self.floor,
            current_hp=70,
            current_mp=25,
        )

    # ========================================
    # 挑戦者勝利：マスター交代
    # ========================================

    def test_challenger_win_changes_master(self):

        fake_result = {
            "winner": "challenger",
            "logs": ["挑戦者の勝利"],
            "challenger_hp": 30,
            "challenger_mp": 10,
            "defender_hp": 0,
            "defender_mp": 5,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ):
            result = challenge_arena_master(
                self.challenger
            )

        self.floor.refresh_from_db()
        self.challenger_state.refresh_from_db()
        self.defender_state.refresh_from_db()

        # 勝者がマスターになる
        self.assertEqual(
            self.floor.master,
            self.challenger,
        )

        # 挑戦者は1階を維持
        self.assertEqual(
            self.challenger_state.floor_id,
            1,
        )

        # 旧マスターは2階へ移動
        self.assertEqual(
            self.defender_state.floor_id,
            2,
        )

        # 両者の闘技場HP/MPが全回復
        self.assertEqual(
            self.challenger_state.current_hp,
            100,
        )

        self.assertEqual(
            self.challenger_state.current_mp,
            50,
        )

        self.assertEqual(
            self.defender_state.current_hp,
            80,
        )

        self.assertEqual(
            self.defender_state.current_mp,
            30,
        )

        # 勝敗結果と履歴を確認
        self.assertEqual(
            result["winner"],
            "challenger",
        )

        history = ArenaBattleHistory.objects.get(
            pk=result["history_id"],
        )

        self.assertEqual(history.result, "win")
        self.assertEqual(history.floor, 1)
        self.assertEqual(
            history.defender_hp_after,
            0,
        )


    # ========================================
    # 挑戦者敗北：2階層下へ移動
    # ========================================

    def test_challenger_loss(self):

        fake_result = {
            "winner": "defender",
            "logs": ["防衛者の勝利"],
            "challenger_hp": 0,
            "challenger_mp": 5,
            "defender_hp": 35,
            "defender_mp": 15,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ):
            result = challenge_arena_master(
                self.challenger
            )

        self.floor.refresh_from_db()
        self.challenger_state.refresh_from_db()
        self.defender_state.refresh_from_db()

        # マスターは変更されない
        self.assertEqual(
            self.floor.master,
            self.defender,
        )

        # 挑戦者は1階から3階へ
        self.assertEqual(
            self.challenger_state.floor_id,
            3,
        )

        # 挑戦者のHP/MPは全回復
        self.assertEqual(
            self.challenger_state.current_hp,
            100,
        )
        self.assertEqual(
            self.challenger_state.current_mp,
            50,
        )

        # 防衛者は残りHP/MPを引き継ぐ
        self.assertEqual(
            self.defender_state.current_hp,
            35,
        )
        self.assertEqual(
            self.defender_state.current_mp,
            15,
        )

        self.assertEqual(result["winner"], "defender")

        history = ArenaBattleHistory.objects.get(
            pk=result["history_id"]
        )
        self.assertEqual(history.result, "loss")


    # ========================================
    # 引き分け：挑戦者は2階層下へ
    # ========================================

    def test_challenger_draw(self):

        fake_result = {
            "winner": "draw",
            "logs": ["引き分け"],
            "challenger_hp": 20,
            "challenger_mp": 10,
            "defender_hp": 40,
            "defender_mp": 20,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ):
            result = challenge_arena_master(
                self.challenger
            )

        self.floor.refresh_from_db()
        self.challenger_state.refresh_from_db()
        self.defender_state.refresh_from_db()

        # マスターを維持
        self.assertEqual(
            self.floor.master,
            self.defender,
        )

        # 挑戦者は3階へ
        self.assertEqual(
            self.challenger_state.floor_id,
            3,
        )

        # 防衛者のHP/MPは引き継ぎ
        self.assertEqual(
            self.defender_state.current_hp,
            40,
        )
        self.assertEqual(
            self.defender_state.current_mp,
            20,
        )

        self.assertEqual(result["winner"], "draw")

        history = ArenaBattleHistory.objects.get(
            pk=result["history_id"]
        )
        self.assertEqual(history.result, "draw")

    # ========================================
    # 100階：マスター交代の境界確認
    # ========================================

    def test_win_at_floor_100(self):

        floor100 = ArenaFloor.objects.get(floor=100)

        # 既存の1階マスターを解除
        self.floor.master = None
        self.floor.save(update_fields=["master"])

        # 100階にマスターを設定
        floor100.master = self.defender
        floor100.save(update_fields=["master"])

        self.challenger_state.floor = floor100
        self.challenger_state.save(
            update_fields=["floor"]
        )

        self.defender_state.floor = floor100
        self.defender_state.save(
            update_fields=["floor"]
        )

        fake_result = {
            "winner": "challenger",
            "logs": ["100階で勝利"],
            "challenger_hp": 20,
            "challenger_mp": 10,
            "defender_hp": 0,
            "defender_mp": 5,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ):
            challenge_arena_master(
                self.challenger
            )

        floor100.refresh_from_db()
        self.challenger_state.refresh_from_db()
        self.defender_state.refresh_from_db()

        # 新マスターが誕生
        self.assertEqual(
            floor100.master,
            self.challenger,
        )

        # 100階を超えない
        self.assertEqual(
            self.challenger_state.floor_id,
            100,
        )
        self.assertEqual(
            self.defender_state.floor_id,
            100,
        )

        # 旧マスターは席を失う
        self.assertFalse(
            ArenaFloor.objects.filter(
                master=self.defender
            ).exists()
        )


    def test_win_grants_exp_and_starts_cooldown(self):
        fake_result = {
            "winner": "challenger",
            "logs": ["勝利"],
            "challenger_hp": 20,
            "challenger_mp": 10,
            "defender_hp": 0,
            "defender_mp": 5,
        }

        original_hp = self.challenger.current_hp
        original_mp = self.challenger.current_mp

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ), patch(
            "apps.battle.arena_services.random.randint",
            return_value=13,
        ):
            result = challenge_arena_master(
                self.challenger
            )

        self.challenger.refresh_from_db()

        self.assertEqual(result["gained_exp"], 13)
        self.assertEqual(self.challenger.exp, 13)

        # 通常HP/MPは変化しない
        self.assertEqual(
            self.challenger.current_hp,
            original_hp,
        )
        self.assertEqual(
            self.challenger.current_mp,
            original_mp,
        )

        self.assertGreater(
            self.challenger.exploration_cooldown_until,
            timezone.now(),
        )


    def test_loss_grants_eight_exp(self):
        fake_result = {
            "winner": "defender",
            "logs": ["敗北"],
            "challenger_hp": 0,
            "challenger_mp": 5,
            "defender_hp": 30,
            "defender_mp": 10,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ):
            result = challenge_arena_master(
                self.challenger
            )

        self.challenger.refresh_from_db()

        self.assertEqual(result["gained_exp"], 8)
        self.assertEqual(self.challenger.exp, 8)


    def test_draw_grants_eight_exp(self):
        fake_result = {
            "winner": "draw",
            "logs": ["引き分け"],
            "challenger_hp": 20,
            "challenger_mp": 10,
            "defender_hp": 30,
            "defender_mp": 10,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=fake_result,
        ):
            result = challenge_arena_master(
                self.challenger
            )

        self.challenger.refresh_from_db()

        self.assertEqual(result["gained_exp"], 8)
        self.assertEqual(self.challenger.exp, 8)


    def test_cannot_battle_during_cooldown(self):
        self.challenger.exploration_cooldown_until = (
            timezone.now() + timedelta(seconds=60)
        )
        self.challenger.save(
            update_fields=["exploration_cooldown_until"]
        )

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run"
        ) as mocked_run:

            with self.assertRaisesRegex(
                ValueError,
                "クールタイム中",
            ):
                challenge_arena_master(
                    self.challenger
                )

            mocked_run.assert_not_called()

        self.assertEqual(
            ArenaBattleHistory.objects.count(),
            0,
        )


class ArenaExpGrowthTests(TestCase):

    def test_arena_exp_does_not_heal_normal_hp_mp(self):

        user = User.objects.create_user(
            user_id="arena_exp_user",
            email="arena_exp@example.com",
            password="testpass123",
        )

        character = Character.objects.create(
            user=user,
            name="闘技場EXPテスト",
            exp=99,
            current_hp=10,
            current_mp=5,
        )

        # HP成長を3回発生させる
        with patch(
            "apps.accounts.growth.random.choices",
            side_effect=[
                ["hp", "hp", "hp"],
                ["fire", "water", "grass"],
            ],
        ):
            result = apply_character_exp(
                character,
                8,
            )

        character.refresh_from_db()

        # 99 + 8 = 107なのでレベルアップ
        self.assertEqual(character.level, 2)
        self.assertEqual(character.exp, 7)

        # 闘技場では通常HP/MPが回復しない
        self.assertEqual(character.current_hp, 10)
        self.assertEqual(character.current_mp, 5)
        # 最大HPは正常に成長している
        self.assertEqual(character.max_hp, 45)

        self.assertEqual(result["gained_exp"], 8)
        self.assertEqual(result["level_up_count"], 1)