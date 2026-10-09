# ============================================================
# BattleEngine プレイヤー行動終了処理
# ============================================================

class BattleActionFinishMixin:

    def finish_player_action(self, action_code):
        """プレイヤーの1行動終了時処理。"""

        # ===== 行動原理：自由 =====

        if (
            self.freedom_active
            and self.freedom_bonus < 0.10
        ):
            self.freedom_bonus = min(
                0.10,
                self.freedom_bonus + 0.02,
            )

            percent = int(
                self.freedom_bonus * 100
            )

            self.logs.append(
                "「行動原理：自由」 "
                f"全能力補正が+{percent}%になった！"
            )

        # ===== 歩行者 =====

        if (
            self.walker_turns > 0
            and action_code != "walker"
        ):
            self.walker_turns -= 1

            if self.walker_turns == 0:
                self.logs.append(
                    "「歩行者」の効果が切れた。"
                )

        # ===== 闘魂 =====

        if (
            self.fighting_spirit_turns > 0
            and action_code != "fighting_spirit"
        ):
            self.fighting_spirit_turns -= 1

            if self.fighting_spirit_turns == 0:
                self.logs.append(
                    "「闘魂」の効果が切れた。"
                )

        # ===== 鋼の体 =====

        if (
            self.steel_body_turns > 0
            and action_code != "steel_body"
        ):
            self.steel_body_turns -= 1

            if self.steel_body_turns == 0:
                self.logs.append(
                    "「鋼の体」の効果が切れた。"
                )

        # ===== 盤石の構え =====

        if (
            self.solid_stance_turns > 0
            and action_code != "solid_stance"
        ):
            self.solid_stance_turns -= 1

            if self.solid_stance_turns == 0:
                self.logs.append(
                    "「盤石の構え」の効果が切れた。"
                )

        # ===== 反撃の構え =====

        if (
            self.counter_stance_turns > 0
            and action_code != "counter_stance"
        ):
            self.counter_stance_turns -= 1

            if self.counter_stance_turns == 0:
                self.counter_remaining = 0

                self.logs.append(
                    "「反撃の構え」の効果が切れた。"
                )

        # ===== ハンターアイ =====

        if (
            self.hunter_eye_turns > 0
            and action_code != "hunter_eye"
        ):
            self.hunter_eye_turns -= 1

            if self.hunter_eye_turns == 0:
                self.logs.append(
                    "「ハンターアイ」の効果が切れた。"
                )

        # ===== ハイド =====

        if (
            self.hide_turns > 0
            and action_code != "hide"
        ):
            self.hide_turns -= 1

            if self.hide_turns == 0:
                self.logs.append(
                    "「ハイド」の効果が切れた。"
                )

        # ===== フロストアーマー =====

        if (
            self.frost_armor_turns > 0
            and action_code != "frost_armor"
        ):
            self.frost_armor_turns -= 1

            if self.frost_armor_turns == 0:
                self.logs.append(
                    "「フロストアーマー」の"
                    "効果が切れた。"
                )

        # ===== ヒーリングシールド =====

        if (
            self.healing_shield_turns > 0
            and action_code != "healing_shield"
        ):
            self.healing_shield_turns -= 1

            if self.healing_shield_turns == 0:
                self.logs.append(
                    "「ヒーリングシールド」の"
                    "VIT上昇効果が切れた。"
                )

        # ===== シャドウステップ =====

        if (
            self.shadow_step_turns > 0
            and action_code != "shadow_step"
        ):
            self.shadow_step_turns -= 1

            if self.shadow_step_turns == 0:
                self.logs.append(
                    "「シャドウステップ」の"
                    "効果が切れた。"
                )

        # ===== エルフ「森の加護」 =====

        if (
            self.character.race == "elf"
            and self.elf_agility_bonus < 0.10
        ):
            self.elf_agility_bonus = min(
                0.10,
                self.elf_agility_bonus + 0.01,
            )

            percent = int(
                round(
                    self.elf_agility_bonus
                    * 100
                )
            )

            self.logs.append(
                "森の加護！ "
                f"AGI補正が+{percent}%になった！"
            )

        # ============================
        # スタミナ消費
        # ============================

        if action_code != "skip":
            self.player_combatant.consume_stamina(
                5
            )
            