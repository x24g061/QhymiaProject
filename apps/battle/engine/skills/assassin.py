import random


# ============================================================
# 暗殺者スキル
# ============================================================

class AssassinSkillsMixin:
    

    # ============================
    # 奇襲
    # ============================

    def skill_surprise_attack(self):
        """
        奇襲

        無属性・物理

        スキル発動成功後、
        さらに40%で奇襲成功。

        成功:
        STR ×4.5
        × ランダム補正0.8～1.2

        失敗:
        現在HPの10%を失う。
        最低1ダメージ。
        """

        # ===== 奇襲成功判定 =====

        if not self.roll_percent(40):

            # 現在HPの10%
            self_damage = max(
                1,
                int(
                    self.player_hp
                    * 0.10
                ),
            )

            self.player_hp -= (
                self_damage
            )

            self.logs.append(
                "奇襲失敗！ "
                f"{self.character.name}は"
                f"反動で{self_damage}ダメージ！"
            )

            return

        # ===== 奇襲成功 =====

        strength = self.get_player_stat(
            "strength"
        )

        random_multiplier = random.uniform(
            0.8,
            1.2,
        )

        base_damage = (
            strength
            * 4.5
            * random_multiplier
        )

        self.logs.append(
            "奇襲成功！"
        )

        self.player_physical_skill_hit(
            skill_name="奇襲",
            base_damage=base_damage,
            attribute="neutral",
        )


    # ============================
    # ポイズンダガー
    # ============================

    def skill_poison_dagger(self):
        """
        ポイズンダガー

        草属性・物理
        STR ×1.2

        命中時:
        ・60%で毒
        ・DEX -3%
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.2
        )

        hit = self.player_physical_skill_hit(
            skill_name="ポイズンダガー",
            base_damage=base_damage,
            attribute="grass",
        )

        # 外れた場合は
        # 追加効果なし
        if not hit:
            return

        if self.enemy_hp <= 0:
            return

        # ===== DEX -3% =====
        #
        # 同じ効果は重複させない。

        self.enemy_dex_debuff_rate = 0.03

        self.logs.append(
            f"{self.enemy.name}の"
            "DEXが3%低下！"
        )

        # ===== 毒判定 =====

        if self.roll_percent(60):

            self.enemy_poison_turns = 5

            self.logs.append(
                f"{self.enemy.name}は"
                "毒状態になった！"
            )


    # ============================
    # ステルス
    # ============================

    def skill_stealth(self):
        """
        ステルス

        闇属性・補助

        回避率+10%。

        最終回避率は最大50%。

        持続時間はまだ正式決定していないため、
        現段階では戦闘中有効として扱う。
        """

        self.stealth_active = True

        self.logs.append(
            "ステルス！ "
            "回避率が10%上昇！"
        )


    # ============================
    # シャドウステップ
    # ============================

    def skill_shadow_step(self):
        """
        シャドウステップ

        闇属性・補助

        3行動の間、
        受けた攻撃ダメージの40%を反射。

        自分自身は
        通常通り全ダメージを受ける。

        ステルス中なら
        スキル発動率100%。
        """

        self.shadow_step_turns = 3

        self.logs.append(
            "シャドウステップ！ "
            "3行動の間、"
            "被ダメージの40%を反射！"
        )


    # ============================
    # フラッシュバング
    # ============================

    def skill_flashbang(self):
        """
        フラッシュバング

        光属性・補助

        生存している敵全員に対して
        それぞれ50%で麻痺を付与する。

        麻痺時間:
        1～3行動
        """

        original_index = (
            self.current_enemy_index
        )

        alive_indexes = (
            self.get_alive_enemy_indexes()
        )

        for index in alive_indexes:

            self.current_enemy_index = index

            enemy_name = (
                self.enemy.name
            )

            # 敵ごとに50%判定
            if not self.roll_percent(50):

                self.logs.append(
                    "フラッシュバング！ "
                    f"{enemy_name}には"
                    "効かなかった！"
                )

                continue

            # 敵ごとに1～3行動
            paralysis_turns = (
                random.randint(
                    1,
                    3,
                )
            )

            self.enemy_paralysis_turns = (
                paralysis_turns
            )

            self.logs.append(
                "フラッシュバング！ "
                f"{enemy_name}は"
                f"{paralysis_turns}行動の間、"
                "麻痺状態になった！"
            )

        self.current_enemy_index = (
            original_index
        )
