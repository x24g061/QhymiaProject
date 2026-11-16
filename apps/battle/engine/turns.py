
# ============================================================
# Qhymia BattleEngine
# ターン処理
# ============================================================
#
# このファイルでは以下の処理を管理する。
#
# 1. プリセットスキルの取得
# 2. プリセットの切り替え
# 3. プレイヤーの行動
# 4. 敵の行動
# 5. 敵の状態異常処理
# 6. 装備特殊能力「衰弱」の解除
#
# ============================================================


class BattleTurnsMixin:

    # ========================================================
    # 次に使うプリセットを取得
    # ========================================================

    def get_next_preset(self):
        """
        現在使用するアクティブスキルを取得する。

        ・パッシブスキルは使用しない
        ・使用回数が0のスキルは飛ばす
        ・使用可能なスキルがなければNoneを返す
        """

        if not self.presets:
            return None

        checked = 0

        while checked < len(self.presets):

            preset = self.presets[
                self.preset_index
            ]

            skill = preset.skill

            # ========================================
            # パッシブスキルはスキップ
            # ========================================

            if skill.is_passive:

                self.advance_preset()

                checked += 1

                continue

            # ========================================
            # スキルの残り使用回数
            # ========================================

            remaining = self.remaining_uses.get(
                preset.id,
                0,
            )

            if remaining > 0:
                return preset

            # 使用回数がない場合は次へ
            self.advance_preset()

            checked += 1

        # 使用できるアクティブスキルがない
        return None

    # ========================================================
    # プリセットを次のスロットへ進める
    # ========================================================

    def advance_preset(self):
        """
        次のプリセットスロットへ移動する。

        最後のスロットまで進んだら
        最初のスロットへ戻る。
        """

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
        プリセットに従ってプレイヤーを自動行動させる。

        行動順:
        1. 種族パッシブ
        2. 行動不能チェック
        3. プリセット取得
        4. MP確認
        5. スキル発動判定
        6. スキル実行
        """

        # ========================================
        # 行動開始時の種族パッシブ
        # ========================================

        if not self.process_action_status(self.player_combatant):
            return "skip"

        self.apply_player_turn_start_race_passive()

        # ========================================
        # 一撃必殺の反動
        # ========================================

        if self.skip_next_player_action:

            self.skip_next_player_action = False

            self.logs.append(
                f"{self.character.name}は"
                "一撃必殺の反動で行動できない！"
            )

            return "skip"

        # ========================================
        # 使用するプリセットを取得
        # ========================================

        preset = self.get_next_preset()

        if preset is None:

            # 使用可能なスキルがなければ通常攻撃
            self.player_normal_attack()

            return "normal"

        skill = preset.skill

        # ========================================
        # MP消費量を取得
        # ========================================

        mp_cost = self.get_skill_mp_cost(
            skill
        )

        # ========================================
        # MP不足
        # ========================================

        if self.player_mp < mp_cost:

            self.logs.append(
                f"{self.character.name}は"
                f"「{skill.name}」を使おうとしたが"
                "MPが足りない！"
            )

            # MP不足時は通常攻撃
            # プリセットは次へ進めない
            self.player_normal_attack()

            return "normal"

        # ========================================
        # スキル発動率
        # ========================================

        activation_rate = (
            skill.activation_rate
        )

        # シャドウステップは
        # ステルス中なら発動率100%
        if (
            skill.code == "shadow_step"
            and self.stealth_active
        ):
            activation_rate = 100

        # ========================================
        # スキル発動判定
        # ========================================

        if not self.roll_percent(
            activation_rate
        ):

            self.logs.append(
                f"{self.character.name}の"
                f"「{skill.name}」は発動しなかった！"
            )

            # 発動失敗時は通常攻撃
            # 次回も同じスキルを試す
            self.player_normal_attack()

            return "normal"

        # ========================================
        # スキル発動成功
        # ========================================

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

        # スキル実行
        self.execute_player_skill(
            skill
        )

        # 次のプリセットへ進む
        self.advance_preset()

        return skill.code

    # ========================================================
    # 敵ターン：実際の行動処理
    # ========================================================

    def _enemy_turn_impl(self):
        """
        敵の1行動を処理する。

        行動順:
        1. 毒ダメージ
        2. 睡眠判定
        3. 麻痺判定
        4. 通常攻撃

        状態異常は現在対象となっている敵にのみ適用。
        """

        actor = getattr(self.enemy_combatant, "skill_actor", None)
        if not self.process_action_status(self.enemy_combatant):
            if actor is not None:
                actor.finish_player_action("skip")
            return
        if actor is None:
            self.enemy_attack()
        else:
            # 状態異常はここで処理済み。スキル本体・MP・スロット進行は共通。
            action_code = actor.player_turn()
            actor.finish_player_action(action_code)

    def process_action_status(self, combatant):
        """自分の行動開始時に毒・睡眠・麻痺を処理する。"""
        # ========================================
        # 毒ダメージ
        # ========================================

        if combatant.poison_turns > 0:

            poison_damage = max(
                1,
                int(
                    combatant.max_hp
                    * 0.10
                ),
            )

            combatant.hp -= poison_damage

            # 毒の残りターンを減らす
            combatant.poison_turns -= 1

            self.logs.append(
                f"{combatant.name}は"
                f"毒で{poison_damage}ダメージ！"
            )

            # 毒ダメージで倒れた場合は
            # そのターンの行動を終了
            if combatant.hp <= 0:
                return False

        # ========================================
        # 睡眠
        # ========================================

        if combatant.sleep_turns > 0:

            combatant.sleep_turns -= 1

            self.logs.append(
                f"{combatant.name}は"
                "眠っていて行動できない！"
            )

            return False

        # ========================================
        # 麻痺
        # ========================================

        if combatant.paralysis_turns > 0:

            combatant.paralysis_turns -= 1

            # 麻痺中は50%の確率で行動不能
            if self.roll_percent(50):

                self.logs.append(
                    f"{combatant.name}は"
                    "麻痺していて行動できない！"
                )

                return False

            # 麻痺の残りターンが0になった場合
            if combatant.paralysis_turns == 0:

                self.logs.append(
                    f"{combatant.name}の"
                    "麻痺が解けた！"
                )

        return True

    # ========================================================
    # 敵ターン：衰弱の解除処理
    # ========================================================

    def enemy_turn(self):
        """
        敵の1行動を処理する。

        装備特殊能力「衰弱」の効果:
        ・DEX -1%
        ・敵の次の1行動だけ有効
        ・行動終了後に解除
        ・睡眠や麻痺で行動できなかった場合も解除
        """

        try:

            # 敵の行動を実行
            return self._enemy_turn_impl()

        finally:

            # ========================================
            # 装備特殊能力「衰弱」を解除
            # ========================================
            #
            # 敵ごとのCombatantに保存されている
            # 一時的なDEX低下率を初期化する。
            #
            # 既存のポイズンダガーのDEX -3%は
            # 別の変数なので影響しない。
            # ========================================

            self.enemy_combatant.equipment_dex_debuff_rate = 0.0
