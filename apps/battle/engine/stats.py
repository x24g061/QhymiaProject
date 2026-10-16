import math

from apps.battle.engine.character_stats import (
    get_character_combat_stat,
    get_stamina_stat_multiplier as calculate_stamina_stat_multiplier,
)


# ============================================================
# BattleEngine ステータス・種族補正
# ============================================================

class BattleStatsMixin:

    # ========================================================
    # 戦闘中ステータス
    # ========================================================

    def get_player_stat(
        self,
        stat_name,
    ):
        """
        戦闘中の有効ステータスを返す。

        実際の計算は、
        探索・闘技場共通処理へ委譲する。
        """

        return get_character_combat_stat(
            self.character,
            stat_name,

            current_hp=self.player_hp,
            max_hp=self.player_max_hp,

            current_stamina=(
                self.player_stamina
            ),
            max_stamina=(
                self.player_max_stamina
            ),

            elf_agility_bonus=(
                self.elf_agility_bonus
            ),

            fighting_spirit_turns=(
                self.fighting_spirit_turns
            ),

            walker_turns=(
                self.walker_turns
            ),

            freedom_active=(
                self.freedom_active
            ),

            freedom_bonus=(
                self.freedom_bonus
            ),

            hunter_eye_turns=(
                self.hunter_eye_turns
            ),

            hide_turns=(
                self.hide_turns
            ),

            healing_shield_turns=(
                self.healing_shield_turns
            ),
        )

    # ========================================================
    # 得意属性
    # ========================================================

    def get_player_main_attribute(self):
        """
        プレイヤーの得意属性を取得する。
        判定自体はCharacter側で共通化する。
        """

        return (
            self.character
            .get_main_attribute()
        )


    # ========================================================
    # MP消費
    # ========================================================

    def get_skill_mp_cost(self, skill):
        """
        実際に消費するMPを返す。

        ウィッチ「魔力循環」は
        MP消費量が2倍になる。
        """

        mp_cost = skill.mp_cost

        if self.character.race == "witch":
            mp_cost *= 2

        return mp_cost


    # ========================================================
    # 行動開始時の種族パッシブ
    # ========================================================

    def apply_player_turn_start_race_passive(self):
        """
        プレイヤーの行動開始時に発動する
        種族パッシブを処理する。
        """

        # フェアリー「妖精の癒し」
        if self.character.race == "fairy":

            if self.roll_percent(50):

                heal_amount = max(
                    1,
                    int(
                        self.player_max_hp
                        * 0.05
                    ),
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

                if actual_heal > 0:

                    self.logs.append(
                        "妖精の癒し！ "
                        f"{self.character.name}のHPが"
                        f"{actual_heal}回復！"
                    )


    # ========================================================
    # 与ダメージ種族補正
    # ========================================================

    def apply_player_damage_race_bonus(
        self,
        damage,
    ):
        """
        プレイヤーが与えるダメージへの
        種族補正。
        """

        if self.character.race == "demonia":
            damage *= 1.10

        return damage


    # ========================================================
    # 被ダメージ種族補正
    # ========================================================

    def apply_player_received_damage_race_bonus(
        self,
        damage,
    ):
        """
        プレイヤーが受けるダメージへの
        種族補正。
        """

        if self.character.race == "demonia":
            damage *= 1.10

        return damage


    # ========================================================
    # 戦闘中の最大HP
    # ========================================================

    def get_player_max_hp(self):
        """
        戦闘中の最大HPを返す。

        プリースト:
        最大HP +5%
        """

        max_hp = self.character.max_hp

        if self.character.job == "priest":
            max_hp = math.ceil(
                max_hp * 1.05
            )

        return max_hp


    # ========================================================
    # 戦闘中の最大MP
    # ========================================================

    def get_player_max_mp(self):
        """
        戦闘中の最大MPを返す。

        プリースト:
        最大MP +5%
        """

        max_mp = self.character.max_mp

        if self.character.job == "priest":
            max_mp = math.ceil(
                max_mp * 1.05
            )

        return max_mp


    # ========================================================
    # スタミナによる能力補正
    # ========================================================

    def get_stamina_stat_multiplier(self):
        """
        ST疲労補正。

        共通計算処理へ委譲する。
        """

        return calculate_stamina_stat_multiplier(
            self.player_stamina,
            self.player_max_stamina,
        )