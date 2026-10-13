# ============================================================
# BattleEngine ターン処理
# ============================================================

class BattleTurnsMixin:

    # ========================================================
    # 次に使うプリセット
    # ========================================================

    def get_next_preset(self):
        """
        現在使用するアクティブスキルを取得する。

        パッシブ・使用回数0のスキルは飛ばす。
        """

        if not self.presets:
            return None

        checked = 0

        while checked < len(self.presets):

            preset = self.presets[
                self.preset_index
            ]

            skill = preset.skill

            # パッシブは行動として使用しない
            if skill.is_passive:
                self.advance_preset()
                checked += 1
                continue

            remaining = self.remaining_uses.get(
                preset.id,
                0,
            )

            # 使用回数が残っている
            if remaining > 0:
                return preset

            # 使い切ったスキルは飛ばす
            self.advance_preset()
            checked += 1

        # 全アクティブスキルを使い切った
        return None


    # ========================================================
    # プリセットを次へ
    # ========================================================

    def advance_preset(self):
        """次のプリセットスロットへ進む。"""

        if not self.presets:
            return

        self.preset_index += 1

        if self.preset_index >= len(
            self.presets
        ):
            self.preset_index = 0


    # ========================================================
    # プレイヤーターン
    # ========================================================

    def player_turn(self):
        """
        プリセットに従って
        プレイヤーを自動行動させる。
        """

        # ===== 行動開始時の種族パッシブ =====

        self.apply_player_turn_start_race_passive()

        # ===== 一撃必殺の反動 =====

        if self.skip_next_player_action:

            self.skip_next_player_action = False

            self.logs.append(
                f"{self.character.name}は"
                "一撃必殺の反動で行動できない！"
            )

            return "skip"

        preset = self.get_next_preset()

        # 全スキルを使い切った場合
        if preset is None:
            self.player_normal_attack()
            return "normal"

        skill = preset.skill

        # 種族パッシブ込みの実際のMP消費量
        mp_cost = self.get_skill_mp_cost(
            skill
        )

        # ===== MP不足 =====

        if self.player_mp < mp_cost:

            self.logs.append(
                f"{self.character.name}は"
                f"「{skill.name}」を使おうとしたが"
                "MPが足りない！"
            )

            # 次回も同じスキルを試すので
            # preset_indexは進めない
            self.player_normal_attack()

            return "normal"

        # ===== スキル発動率 =====

        activation_rate = (
            skill.activation_rate
        )

        # シャドウステップは
        # ステルス中なら確定発動
        if (
            skill.code == "shadow_step"
            and self.stealth_active
        ):
            activation_rate = 100

        if not self.roll_percent(
            activation_rate
        ):

            self.logs.append(
                f"{self.character.name}の"
                f"「{skill.name}」は発動しなかった！"
            )

            # 次回も同じスキルを試す
            self.player_normal_attack()

            return "normal"

        # ===== 発動成功 =====

        self.player_mp -= mp_cost

        self.remaining_uses[
            preset.id
        ] -= 1

        self.logs.append(
            f"{self.character.name}は"
            f"「{skill.name}」を発動！ "
            f"MP -{mp_cost} "
            f"（残り {self.player_mp}）"
        )

        self.execute_player_skill(
            skill
        )

        self.advance_preset()

        return skill.code


    # ========================================================
    # 敵ターン
    # ========================================================

    def enemy_turn(self):
        """
        敵の1行動を処理する。

        順番:
        1. 毒ダメージ
        2. 睡眠判定
        3. 麻痺判定
        4. 通常攻撃
        """

        # ============================
        # 毒
        # ============================

        if self.enemy_poison_turns > 0:

            poison_damage = max(
                1,
                int(
                    self.enemy.max_hp
                    * 0.10
                ),
            )

            self.enemy_hp -= poison_damage

            self.enemy_poison_turns -= 1

            self.logs.append(
                f"{self.enemy.name}は"
                f"毒で{poison_damage}ダメージ！"
            )

            # 毒ではHP0になれる
            if self.enemy_hp <= 0:
                return

        # ============================
        # 睡眠
        # ============================

        if self.enemy_sleep_turns > 0:

            self.enemy_sleep_turns -= 1

            self.logs.append(
                f"{self.enemy.name}は"
                "眠っていて行動できない！"
            )

            return

        # ============================
        # 麻痺
        # ============================

        if self.enemy_paralysis_turns > 0:

            self.enemy_paralysis_turns -= 1

            if self.roll_percent(50):

                self.logs.append(
                    f"{self.enemy.name}は"
                    "麻痺していて行動できない！"
                )

                return

            if (
                self.enemy_paralysis_turns
                == 0
            ):

                self.logs.append(
                    f"{self.enemy.name}の"
                    "麻痺が解けた！"
                )

        # ============================
        # 通常攻撃
        # ============================

        self.enemy_attack()