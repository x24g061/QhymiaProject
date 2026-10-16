import math

from apps.battle.engine.character_stats import (
    get_character_base_combat_stat,
)


# ============================================================
# BattleEngine ステータス・種族補正
# ============================================================

class BattleStatsMixin:

    # ========================================================
    # 戦闘中ステータス
    # ========================================================

    def get_player_stat(self, stat_name):
        """
        戦闘中の有効ステータスを返す。

        対象:
        strength
        intelligence
        dexterity
        agility
        vitality
        luck
        """
        

        value = get_character_base_combat_stat(
            self.character,
            stat_name,
        )


        # ドラゴニア「竜血覚醒」
        if (
            self.character.race == "dragonia"
            and self.player_hp
            <= self.player_max_hp * 0.50
            and stat_name in (
                "strength",
                "vitality",
            )
        ):
            value *= 1.10

        # エルフ「森の加護」
        if (
            self.character.race == "elf"
            and stat_name == "agility"
        ):
            value *= (
                1.0
                + self.elf_agility_bonus
            )

        # ============================
        # スキル・バフ補正
        # ============================

        # 闘魂
        if (
            self.fighting_spirit_turns > 0
            and stat_name == "strength"
        ):
            value *= 1.10

        # 歩行者
        if self.walker_turns > 0:

            if stat_name == "agility":
                value *= 0.70

            elif stat_name == "strength":
                value *= 1.20

            elif stat_name == "dexterity":
                value *= 1.05

        # 行動原理：自由
        if self.freedom_active:
            value *= (
                1.0
                + self.freedom_bonus
            )

        # ハンターアイ
        if self.hunter_eye_turns > 0:

            if stat_name == "dexterity":
                value *= 1.10

            elif stat_name == "luck":
                value *= 1.05

        # ハイド
        if (
            self.hide_turns > 0
            and stat_name == "agility"
        ):
            value *= 0.90

        # ヒーリングシールド
        if (
            self.healing_shield_turns > 0
            and stat_name == "vitality"
        ):
            value *= 1.20

        # ============================
        # スタミナによる戦闘疲労
        # ============================

        if stat_name in (
            "dexterity",
            "agility",
            "vitality",
            "luck",
        ):
            value *= (
                self.get_stamina_stat_multiplier()
            )

        return value


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
    # クリティカル率
    # ========================================================

    @staticmethod
    def calculate_critical_rate(
        attacker_luck,
        defender_luck,
    ):
        denominator = (
            attacker_luck
            + defender_luck
        )

        if denominator <= 0:
            return 5

        return (
            5
            + 45
            * attacker_luck
            / denominator
        )


    # ========================================================
    # クリティカル倍率
    # ========================================================

    @staticmethod
    def calculate_critical_multiplier(luck):
        return (
            1.5
            + (
                luck
                / (luck + 1000)
            )
            * 1.5
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
        現在STから疲労による能力補正を返す。

        100ST → 1.00倍
         50ST → 0.75倍
          0ST → 0.50倍

        0STでも能力値の50%は残る。
        """

        if self.player_max_stamina <= 0:
            return 0.50

        stamina_ratio = (
            self.player_stamina
            / self.player_max_stamina
        )

        stamina_ratio = min(
            1.0,
            max(
                0.0,
                stamina_ratio,
            ),
        )

        return (
            0.50
            + stamina_ratio * 0.50
        )