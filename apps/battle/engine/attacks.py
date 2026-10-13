from apps.battle.engine.calculations import (
    ATTRIBUTE_MULTIPLIERS,
)


# ============================================================
# BattleEngine 攻撃処理
# ============================================================

class BattleAttacksMixin:

    def player_normal_attack(self):
        """プレイヤー通常攻撃。"""


        # ========================================================
        # 蜃気楼：通常攻撃
        # ========================================================

        if self.mirage_active:

            original_index = (
                self.current_enemy_index
            )

            target_indexes = (
                self.get_alive_enemy_indexes()
            )

            self.mirage_active = False

            self.logs.append(
                "蜃気楼の効果！ "
                "通常攻撃が敵全体になった！"
            )

            for index in target_indexes:

                if not (
                    self.enemy_combatants[index]
                    .is_alive()
                ):
                    continue

                self.current_enemy_index = index

                self.player_normal_attack()

            self.current_enemy_index = (
                original_index
            )

            return


        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.get_player_stat(
                "dexterity"
            ),
            defender_agi=self.enemy.agility,
        )

        if not self.roll_percent(hit_rate):

            self.logs.append(
                f"{self.character.name}の攻撃！ "
                "しかし外れた！"
            )

            return

        damage = self.calculate_physical_damage(
            strength=self.get_player_stat(
                "strength"
            ),
            defender_vit=self.enemy.vitality,
        )

        # ===== クリティカル =====

        critical_rate = (
            self.calculate_critical_rate(
                attacker_luck=self.get_player_stat("luck"),
                defender_luck=self.enemy.luck,
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            critical_multiplier = (
                self.calculate_critical_multiplier(
                    self.get_player_stat("luck")
                )
            )

            damage *= critical_multiplier

        # ===== 属性相性 =====
        # 通常攻撃は無属性

        skill_attribute = "neutral"

        attribute_multiplier = (
            ATTRIBUTE_MULTIPLIERS[
                skill_attribute
            ][
                self.enemy.attribute
            ]
        )

        damage *= attribute_multiplier

        # ===== 得意属性補正 =====

        main_attribute = (
            self.get_player_main_attribute()
        )

        if (
            skill_attribute
            == main_attribute
        ):
            damage *= 1.15

        # ===== 睡眠中の被ダメージ補正 =====
        #
        # 睡眠中に通常攻撃を受けた場合も
        # ダメージ1.2倍。
        #
        # 攻撃後に睡眠解除。

        was_sleeping = (
            self.enemy_sleep_turns > 0
        )

        if was_sleeping:
            damage *= 1.20

        # ===== 種族による与ダメージ補正 =====

        damage = (
            self.apply_player_damage_race_bonus(
                damage
            )
        )

        # 最終的に整数化
        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        # ===== 睡眠解除 =====

        if was_sleeping:

            self.enemy_sleep_turns = 0

            self.logs.append(
                f"{self.enemy.name}は"
                "攻撃を受けて目を覚ました！"
            )

        if is_critical:

            self.logs.append(
                f"{self.character.name}の攻撃！ "
                f"クリティカル！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{self.character.name}の攻撃！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

    def player_physical_skill_hit(
        self,
        skill_name,
        base_damage,
        attribute,
        hit_label=None,
        guaranteed_hit=False,
    ):
        """
        プレイヤーの物理スキル
        「1ヒット分」を処理する共通関数。

        処理内容:
        1. 命中判定
        2. 敵VITによる物理防御
        3. クリティカル判定
        4. 属性相性
        5. 得意属性補正
        6. 最終ダメージ
        """

        # すでに敵を倒していた場合は何もしない
        if self.enemy_hp <= 0:
            return False

        # ログに表示する攻撃名
        #
        # hit_labelが指定されている場合、
        # 「ダブルパンチ 1撃目」などを表示できる。
        attack_name = (
            hit_label
            if hit_label is not None
            else skill_name
        )

        # ===== 命中判定 =====

        if not guaranteed_hit:

            hit_rate = self.calculate_hit_rate(
                attacker_dex=self.get_player_stat(
                    "dexterity"
                ),
                defender_agi=self.enemy.agility,
            )

            if not self.roll_percent(hit_rate):

                self.logs.append(
                    f"{attack_name}！ "
                    "しかし攻撃は外れた！"
                )

                return False

        # ===== 物理防御 =====
        #
        # 物理ダメージ:
        #
        # 基礎ダメージ
        # - 敵VIT ×0.5

        damage = (
            base_damage
            - self.enemy.vitality * 0.5
        )

        damage = max(
            1,
            damage,
        )

        # ===== クリティカル =====

        luck = self.get_player_stat(
            "luck"
        )

        critical_rate = (
            self.calculate_critical_rate(
                attacker_luck=luck,
                defender_luck=self.enemy.luck,
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            damage *= (
                self.calculate_critical_multiplier(
                    luck
                )
            )

        # ===== 属性相性 =====

        damage *= ATTRIBUTE_MULTIPLIERS[
            attribute
        ][
            self.enemy.attribute
        ]

        # ===== 得意属性補正 =====
        #
        # スキル属性と得意属性が一致したら
        # 最終ダメージ ×1.15

        if (
            self.get_player_main_attribute()
            == attribute
        ):
            damage *= 1.15

        # ===== 睡眠中の被ダメージ補正 =====
        #
        # 睡眠中に直接攻撃を受けた場合、
        # その攻撃のダメージは1.2倍。
        #
        # ダメージを受けた後に睡眠解除。

        was_sleeping = (
            self.enemy_sleep_turns > 0
        )

        if was_sleeping:
            damage *= 1.20

        # ===== 種族による与ダメージ補正 =====

        damage = (
            self.apply_player_damage_race_bonus(
                damage
            )
        )

        # ===== 最終ダメージ =====

        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        # ===== 戦闘ログ =====

        if is_critical:

            self.logs.append(
                f"{attack_name}！ "
                f"クリティカル！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{attack_name}！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        # ===== 睡眠解除 =====

        if was_sleeping:

            self.enemy_sleep_turns = 0

            self.logs.append(
                f"{self.enemy.name}は"
                "攻撃を受けて目を覚ました！"
            )

        # 攻撃が命中したことを返す
        return True


    def player_magic_skill_hit(
        self,
        skill_name,
        base_damage,
        attribute,
        hit_label=None,
        ignore_magic_defense=False,
    ):
        """
        プレイヤーの魔法スキル
        「1ヒット分」を処理する共通関数。

        処理内容:
        1. 命中判定
        2. 敵INTによる魔法防御
        3. 属性相性
        4. 得意属性補正
        5. 睡眠中のダメージ補正
        6. 最終ダメージ

        魔法攻撃は現時点では
        クリティカル判定を行わない。
        """

        # すでに敵を倒していた場合
        if self.enemy_hp <= 0:
            return False

        # ログ表示名
        attack_name = (
            hit_label
            if hit_label is not None
            else skill_name
        )

        # ============================
        # 命中判定
        # ============================

        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.get_player_stat(
                "dexterity"
            ),
            defender_agi=self.enemy.agility,
        )

        if not self.roll_percent(hit_rate):

            self.logs.append(
                f"{attack_name}！ "
                "しかし攻撃は外れた！"
            )

            return False

        # ============================
        # 魔法防御
        # ============================
        #
        # 通常の魔法:
        #
        # 基礎ダメージ
        # - 敵INT ×0.3
        #
        # メギドなど、
        # 防御無視スキルの場合は引かない。

        damage = base_damage

        if not ignore_magic_defense:
            damage -= (
                self.enemy.intelligence
                * 0.3
            )

        damage = max(
            1,
            damage,
        )

        # ============================
        # 属性相性
        # ============================

        damage *= ATTRIBUTE_MULTIPLIERS[
            attribute
        ][
            self.enemy.attribute
        ]

        # ============================
        # 得意属性補正
        # ============================

        if (
            self.get_player_main_attribute()
            == attribute
        ):
            damage *= 1.15

        # ============================
        # 睡眠中
        # ============================
        #
        # 睡眠中に攻撃された場合
        # ダメージ1.2倍。
        #
        # 攻撃後に目を覚ます。

        was_sleeping = (
            self.enemy_sleep_turns > 0
        )

        if was_sleeping:
            damage *= 1.20

        # ===== 種族による与ダメージ補正 =====

        damage = (
            self.apply_player_damage_race_bonus(
                damage
            )
        )

        # ============================
        # 最終ダメージ
        # ============================

        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        self.logs.append(
            f"{attack_name}！ "
            f"{self.enemy.name}に"
            f"{damage}ダメージ！"
        )

        # 睡眠解除
        if was_sleeping:

            self.enemy_sleep_turns = 0

            self.logs.append(
                f"{self.enemy.name}は"
                "攻撃を受けて目を覚ました！"
            )

        return True


    #=== 敵行動実装 ===

    def enemy_attack(self):
        """敵の通常攻撃。"""

        # ===== 敵の有効DEX =====

        enemy_dexterity = (
            self.enemy.dexterity
        )

        # ポイズンダガーによるDEX -3%
        if self.enemy_dex_debuff_rate > 0:

            enemy_dexterity *= (
                1.0
                - self.enemy_dex_debuff_rate
            )

        # ===== 命中率 =====

        hit_rate = self.calculate_hit_rate(
            attacker_dex=enemy_dexterity,
            defender_agi=self.get_player_stat(
                "agility"
            ),
        )

        # ===== ハイド =====
        #
        # ハイド中は敵の命中率を10%低下。

        if self.hide_turns > 0:
            hit_rate *= 0.90

        # ===== ステルス =====
        #
        # 回避率+10%
        # ＝敵の命中率を10ポイント低下。
        #
        # 最終回避率は最大50%なので、
        # 命中率は最低50%まで。

        if self.stealth_active:

            hit_rate -= 10

            hit_rate = max(
                50,
                hit_rate,
            )

        #===== 命中判定 =====
        if not self.roll_percent(hit_rate):

            self.logs.append(
                f"{self.enemy.name}の攻撃！ "
                "しかし外れた！"
            )

            return

        damage = self.calculate_physical_damage(
            strength=self.enemy.strength,
            defender_vit=self.get_player_stat(
                "vitality"
            ),
        )

        critical_rate = (
            self.calculate_critical_rate(
                attacker_luck=self.enemy.luck,
                defender_luck=self.get_player_stat("luck"),
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            damage *= (
                self.calculate_critical_multiplier(
                    self.enemy.luck
                )
            )

        # ===== 鋼の体 =====
        #
        # 敵の通常攻撃は物理なので
        # 40%軽減する。

        if self.steel_body_turns > 0:

            damage *= 0.60

            self.logs.append(
                "「鋼の体」で"
                "物理ダメージを40%軽減！"
            )

        # ===== 盤石の構え =====

        if self.solid_stance_turns > 0:

            damage *= 0.80

            self.logs.append(
                "「盤石の構え」で"
                "ダメージを20%軽減！"
            )

        # ===== 種族による被ダメージ補正 =====

        damage = (
            self.apply_player_received_damage_race_bonus(
                damage
            )
        )

        damage = max(
            1,
            int(damage),
        )

        self.player_hp -= damage

        # ===== シャドウステップ =====
        #
        # 自分は通常通りダメージを受ける。
        # そのダメージの40%を敵へ返す。

        if (
            self.shadow_step_turns > 0
            and self.enemy_hp > 0
        ):

            reflect_damage = max(
                1,
                int(
                    damage * 0.40
                ),
            )

            self.enemy_hp -= (
                reflect_damage
            )

            self.logs.append(
                "シャドウステップ！ "
                f"{self.enemy.name}に"
                f"{reflect_damage}反射ダメージ！"
            )

        # ===== 反撃の構え =====

        should_counter = (
            self.player_hp > 0
            and self.counter_stance_turns > 0
            and self.counter_remaining > 0
        )

        if is_critical:

            self.logs.append(
                f"{self.enemy.name}の攻撃！ "
                f"クリティカル！ "
                f"{self.character.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{self.enemy.name}の攻撃！ "
                f"{self.character.name}に"
                f"{damage}ダメージ！"
            )

        if should_counter:

            self.counter_remaining -= 1

            strength = self.get_player_stat(
                "strength"
            )

            base_damage = (
                strength * 1.3
            )

            self.logs.append(
                f"{self.character.name}が反撃！"
            )

            self.player_physical_skill_hit(
                skill_name="反撃",
                base_damage=base_damage,
                attribute="neutral",
            )


    # ========================================================
    # 生存中の敵index
    # ========================================================

    def get_alive_enemy_indexes(self):
        """
        生存している敵のindex一覧を返す。
        """

        return [
            index
            for index, enemy
            in enumerate(
                self.enemy_combatants
            )
            if enemy.is_alive()
        ]


    # ========================================================
    # 物理全体攻撃
    # ========================================================

    def player_physical_skill_hit_all(
        self,
        skill_name,
        base_damage,
        attribute,
    ):
        """
        生存している敵全員へ
        物理スキルを1回ずつ当てる。
        """

        original_index = (
            self.current_enemy_index
        )

        alive_indexes = (
            self.get_alive_enemy_indexes()
        )

        for index in alive_indexes:

            self.current_enemy_index = index

            self.player_physical_skill_hit(
                skill_name=skill_name,
                base_damage=base_damage,
                attribute=attribute,
            )

        # 元々狙っていた敵へ戻す
        self.current_enemy_index = (
            original_index
        )


    # ========================================================
    # 魔法全体攻撃
    # ========================================================

    def player_magic_skill_hit_all(
        self,
        skill_name,
        base_damage,
        attribute,
    ):
        """
        生存している敵全員へ
        魔法スキルを1回ずつ当てる。
        """

        original_index = (
            self.current_enemy_index
        )

        alive_indexes = (
            self.get_alive_enemy_indexes()
        )

        for index in alive_indexes:

            self.current_enemy_index = index

            self.player_magic_skill_hit(
                skill_name=skill_name,
                base_damage=base_damage,
                attribute=attribute,
            )

        self.current_enemy_index = (
            original_index
        )