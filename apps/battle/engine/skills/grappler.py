import random


# ============================================================
# 拳闘士スキル
# ============================================================

class GrapplerSkillsMixin:

    # ========================================================
    # ダブルパンチ
    # ========================================================

    def skill_double_punch(self):
        strength = self.get_player_stat(
            "strength"
        )

        for hit_number in range(1, 3):

            if self.enemy_hp <= 0:
                break

            base_damage = (
                strength * 2.0
            )

            self.player_physical_skill_hit(
                skill_name="ダブルパンチ",
                base_damage=base_damage,
                attribute="neutral",
                hit_label=(
                    f"ダブルパンチ "
                    f"{hit_number}撃目"
                ),
            )


    # ========================================================
    # 衝撃波
    # ========================================================

    def skill_shock_wave(self):
        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.5
        )

        self.player_physical_skill_hit_all(
            skill_name="衝撃波",
            base_damage=base_damage,
            attribute="light",
        )


    # ========================================================
    # 怒涛連打
    # ========================================================

    def skill_rapid_barrage(self):
        strength = self.get_player_stat(
            "strength"
        )

        hit_count = random.randint(
            1,
            10,
        )

        self.logs.append(
            f"怒涛連打！ "
            f"{hit_count}回攻撃！"
        )

        for hit_number in range(
            1,
            hit_count + 1,
        ):

            if self.enemy_hp <= 0:
                break

            base_damage = (
                strength * 0.5
            )

            self.player_physical_skill_hit(
                skill_name="怒涛連打",
                base_damage=base_damage,
                attribute="fire",
                hit_label=(
                    f"怒涛連打 "
                    f"{hit_number}撃目"
                ),
            )


    # ========================================================
    # 闘魂
    # ========================================================

    def skill_fighting_spirit(self):
        self.fighting_spirit_turns = 3

        self.logs.append(
            "闘魂！ "
            "3行動の間、STRが10%上昇！"
        )


    # ========================================================
    # 真拳一殺
    # ========================================================

    def skill_true_fist(self):
        strength = self.get_player_stat(
            "strength"
        )

        luck = self.get_player_stat(
            "luck"
        )

        base_damage = (
            strength * 2.0
            + luck * 1.5
        )

        self.player_physical_skill_hit(
            skill_name="真拳一殺",
            base_damage=base_damage,
            attribute="neutral",
        )