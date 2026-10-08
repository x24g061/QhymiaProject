import random


# ============================================================
# ウィザードスキル
# ============================================================

class WizardSkillsMixin:

    # ========================================================
    # ステラ
    # ========================================================

    def skill_stella(self):
        intelligence = self.get_player_stat(
            "intelligence"
        )

        hit_count = random.randint(
            4,
            5,
        )

        self.logs.append(
            f"ステラ！ "
            f"{hit_count}回攻撃！"
        )

        for hit_number in range(
            1,
            hit_count + 1,
        ):

            if self.enemy_hp <= 0:
                break

            base_damage = (
                intelligence * 0.7
            )

            self.player_magic_skill_hit(
                skill_name="ステラ",
                base_damage=base_damage,
                attribute="neutral",
                hit_label=(
                    f"ステラ "
                    f"{hit_number}撃目"
                ),
            )


    # ========================================================
    # ファイヤー
    # ========================================================

    def skill_fire(self):
        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.75,
            1.0,
        )

        base_damage = (
            intelligence
            * 1.5
            * random_multiplier
        )

        self.player_magic_skill_hit(
            skill_name="ファイヤー",
            base_damage=base_damage,
            attribute="fire",
        )


    # ========================================================
    # メギド
    # ========================================================

    def skill_megido(self):
        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.5,
            1.0,
        )

        base_damage = (
            intelligence
            * 1.1
            * random_multiplier
        )

        self.player_magic_skill_hit(
            skill_name="メギド",
            base_damage=base_damage,
            attribute="dark",
            ignore_magic_defense=True,
        )


    # ========================================================
    # エクスプロージョン
    # ========================================================

    def skill_explosion(self):
        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.5,
            1.0,
        )

        base_damage = (
            intelligence
            * 2.5
            * random_multiplier
        )

        self.player_magic_skill_hit_all(
            skill_name="エクスプロージョン",
            base_damage=base_damage,
            attribute="rock",
        )


    # ========================================================
    # フロストアーマー
    # ========================================================

    def skill_frost_armor(self):
        self.frost_armor_turns = 5

        self.logs.append(
            "フロストアーマー！ "
            "5行動の間、"
            "魔法ダメージを軽減！"
        )