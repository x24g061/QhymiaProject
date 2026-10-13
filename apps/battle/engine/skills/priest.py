import random


# ============================================================
# プリーストスキル
# ============================================================

class PriestSkillsMixin:

    # ========================================================
    # ジャッジメント
    # ========================================================

    def skill_judgement(self):
        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.75,
            1.0,
        )

        base_damage = (
            intelligence
            * 2.0
            * random_multiplier
        )

        hit = self.player_magic_skill_hit(
            skill_name="ジャッジメント",
            base_damage=base_damage,
            attribute="fire",
        )

        if not hit:
            return

        if self.enemy_hp <= 0:
            return

        if self.roll_percent(50):

            self.enemy_paralysis_turns = 5

            self.logs.append(
                f"{self.enemy.name}は"
                "麻痺状態になった！"
            )


    # ========================================================
    # ヒーリングシールド
    # ========================================================

    def skill_healing_shield(self):
        vitality = self.get_player_stat(
            "vitality"
        )

        heal_amount = max(
            1,
            int(vitality * 1.0),
        )

        before_hp = self.player_hp

        self.player_hp = min(
            self.player_max_hp,
            self.player_hp + heal_amount,
        )

        actual_heal = (
            self.player_hp
            - before_hp
        )

        self.healing_shield_turns = 3

        self.logs.append(
            f"ヒーリングシールド！ "
            f"HPが{actual_heal}回復！ "
            "3行動の間、VIT +20%！"
        )


    # ========================================================
    # 浄化
    # ========================================================

    def skill_purification(self):
        self.purification_guard = True

        self.logs.append(
            "浄化！ "
            "デバフを解除し、"
            "次に受けるデバフを1回無効化！"
        )


    # ========================================================
    # リザレク
    # ========================================================

    def skill_resurrection(self):
        if self.resurrection_used:

            self.logs.append(
                "リザレクはこの戦闘では"
                "すでに使用している！"
            )

            return

        self.resurrection_used = True

        self.logs.append(
            "リザレク！ "
            "現在は蘇生対象となる味方がいない。"
        )


    # ========================================================
    # アンチジェイル
    # ========================================================

    def skill_anti_jail(self):
        intelligence = self.get_player_stat(
            "intelligence"
        )

        if self.enemy_hp > 0:

            self.player_magic_skill_hit(
                skill_name="アンチジェイル",
                base_damage=(
                    intelligence * 1.8
                ),
                attribute="neutral",
                hit_label="アンチジェイル 1撃目",
            )

        if self.enemy_hp > 0:

            self.player_magic_skill_hit(
                skill_name="アンチジェイル",
                base_damage=(
                    intelligence * 2.2
                ),
                attribute="neutral",
                hit_label="アンチジェイル 2撃目",
            )