# ============================================================
# 狩人スキル
# ============================================================

class HunterSkillsMixin:

    # ========================================================
    # ラピッドショット
    # ========================================================

    def skill_rapid_shot(self):
        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.5
        )

        self.player_physical_skill_hit(
            skill_name="ラピッドショット",
            base_damage=base_damage,
            attribute="neutral",
            guaranteed_hit=True,
        )


    # ========================================================
    # 睡眠矢
    # ========================================================

    def skill_sleep_arrow(self):
        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.8
        )

        hit = self.player_physical_skill_hit(
            skill_name="睡眠矢",
            base_damage=base_damage,
            attribute="water",
        )

        if not hit:
            return

        if self.enemy_hp <= 0:
            return

        if self.roll_percent(35):

            self.enemy_sleep_turns = 3

            self.logs.append(
                f"{self.enemy.name}は"
                "睡眠状態になった！"
            )


    # ========================================================
    # ハンターアイ
    # ========================================================

    def skill_hunter_eye(self):
        self.hunter_eye_turns = 3

        self.logs.append(
            "ハンターアイ！ "
            "3行動の間、"
            "DEX +10%、LUK +5%！"
        )


    # ========================================================
    # ハイド
    # ========================================================

    def skill_hide(self):
        self.hide_turns = 3

        self.logs.append(
            "ハイド！ "
            "3行動の間、"
            "AGI -10%、"
            "敵の命中率 -10%！"
        )


    # ========================================================
    # 毒矢
    # ========================================================

    def skill_poison_arrow(self):
        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.5
        )

        hit = self.player_physical_skill_hit(
            skill_name="毒矢",
            base_damage=base_damage,
            attribute="dark",
        )

        if not hit:
            return

        if self.enemy_hp <= 0:
            return

        if self.roll_percent(50):

            self.enemy_poison_turns = 5

            self.logs.append(
                f"{self.enemy.name}は"
                "毒状態になった！"
            )