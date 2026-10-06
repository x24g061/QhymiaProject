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
from apps.inventory.models import (
    Equipment,
    InventoryItem,
    Item,
    OwnedEquipment,
)

from apps.battle.models import (
    Enemy,
    FloorDropItem,
)

from apps.battle.drops import (
    grant_exploration_drop,
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