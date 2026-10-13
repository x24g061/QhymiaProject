import random

from apps.battle.engine.calculations import (
    ATTRIBUTE_MULTIPLIERS,
)


# ============================================================
# 放浪人スキル
# ============================================================

class WandererSkillsMixin:

    # ========================================================
    # 核心を突く
    # ========================================================

    def skill_strike_core(self):
        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.get_player_stat(
                "dexterity"
            ),
            defender_agi=self.enemy.agility,
        )

        if not self.roll_percent(hit_rate):

            self.logs.append(
                "核心を突く！ "
                "しかし攻撃は外れた！"
            )

            return

        random_multiplier = random.uniform(
            0.5,
            1.0,
        )

        strength = self.get_player_stat(
            "strength"
        )

        luck = self.get_player_stat(
            "luck"
        )

        base_damage = (
            strength * 1.0
            + luck * 1.2
        )

        base_damage *= random_multiplier

        damage = (
            base_damage
            - self.enemy.vitality * 0.5
        )

        damage = max(
            1,
            damage,
        )

        critical_rate = (
            self.calculate_critical_rate(
                luck,
                self.enemy.luck,
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

        damage *= ATTRIBUTE_MULTIPLIERS[
            "light"
        ][self.enemy.attribute]

        if (
            self.get_player_main_attribute()
            == "light"
        ):
            damage *= 1.15

        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        if is_critical:

            self.logs.append(
                f"核心を突く！ "
                f"クリティカル！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"核心を突く！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )


    # ========================================================
    # 一時休息
    # ========================================================

    def skill_short_rest(self):
        strength = self.get_player_stat(
            "strength"
        )

        heal_amount = max(
            1,
            int(strength * 0.5),
        )

        before_hp = min(
            self.player_hp,
            self.player_max_hp,
        )

        self.player_hp = before_hp

        self.player_hp = min(
            self.player_max_hp,
            self.player_hp + heal_amount,
        )

        actual_heal = max(
            0,
            self.player_hp - before_hp,
        )

        self.logs.append(
            f"一時休息！ "
            f"{self.character.name}のHPが"
            f"{actual_heal}回復！ "
            f"（HP {self.player_hp}"
            f"/{self.player_max_hp}）"
        )


    # ========================================================
    # 歩行者
    # ========================================================

    def skill_walker(self):
        self.walker_turns = 3

        self.logs.append(
            "歩行者！ "
            "3行動の間、"
            "AGI -30%、STR +20%、DEX +5%！"
        )


    # ========================================================
    # 蜃気楼
    # ========================================================

    def skill_mirage(self):
        self.mirage_active = True

        self.logs.append(
            "蜃気楼を発動！ "
            "攻撃が全体化された！"
        )