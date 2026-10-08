# ============================================================
# 重戦士スキル
# ============================================================

class WarriorSkillsMixin:

    # ========================================================
    # フレアブレイド
    # ========================================================

    def skill_flare_blade(self):
        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 2.2
        )

        self.player_physical_skill_hit_all(
            skill_name="フレアブレイド",
            base_damage=base_damage,
            attribute="fire",
        )


    # ========================================================
    # 一撃必殺
    # ========================================================

    def skill_one_hit_kill(self):
        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 4.0
        )

        self.player_physical_skill_hit(
            skill_name="一撃必殺",
            base_damage=base_damage,
            attribute="neutral",
        )

        self.skip_next_player_action = True


    # ========================================================
    # 鋼の体
    # ========================================================

    def skill_steel_body(self):
        self.steel_body_turns = 1

        self.logs.append(
            "鋼の体！ "
            "受ける物理ダメージを40%軽減！"
        )


    # ========================================================
    # 盤石の構え
    # ========================================================

    def skill_solid_stance(self):
        self.solid_stance_turns = 1

        self.logs.append(
            "盤石の構え！ "
            "受けるダメージを20%軽減！"
        )


    # ========================================================
    # 反撃の構え
    # ========================================================

    def skill_counter_stance(self):
        self.counter_stance_turns = 2
        self.counter_remaining = 3

        self.logs.append(
            "反撃の構え！ "
            "2行動の間、攻撃を受けると反撃する！"
        )
        