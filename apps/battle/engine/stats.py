import math

from apps.battle.engine.character_stats import (
    get_character_combat_stat,
    get_stamina_stat_multiplier as calculate_stamina_stat_multiplier,
    apply_character_damage_race_bonus,
    apply_character_received_damage_race_bonus,
    get_character_battle_max_resource,
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

        value = get_character_combat_stat(
            self.character,
            stat_name,

            base_value=self.get_player_base_stat(stat_name),
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

        if stat_name == "dexterity":
            value *= 1.0 - max(
                getattr(self.player_combatant, "dex_debuff_rate", 0.0),
                getattr(self.player_combatant, "equipment_dex_debuff_rate", 0.0),
            )
        return value

    def get_player_base_stat(self, stat_name):
        # Noneなら共通関数が従来どおり装備・職業・種族を計算する。
        return None

    def get_enemy_stat(self, stat_name, combatant=None):
        combatant = combatant or self.enemy_combatant
        actor = getattr(combatant, "skill_actor", None)
        if actor is not None:
            return actor.get_player_stat(stat_name)
        return getattr(combatant.enemy, stat_name)

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
        与ダメージ種族補正。
        共通処理へ委譲する。
        """

        return apply_character_damage_race_bonus(
            self.character,
            damage,
        )


    # ========================================================
    # 被ダメージ種族補正
    # ========================================================

    def apply_player_received_damage_race_bonus(
        self,
        damage,
    ):
        """
        被ダメージ種族補正。
        共通処理へ委譲する。
        """

        return apply_character_received_damage_race_bonus(
            self.character,
            damage,
        )


    # ========================================================
    # 戦闘中の最大HP
    # ========================================================

    def get_player_max_hp(self):
        """戦闘中の最大HPを取得する。"""

        return get_character_battle_max_resource(
            self.character,
            "hp",
        )

    # ========================================================
    # 戦闘中の最大MP
    # ========================================================

    def get_player_max_mp(self):
        """戦闘中の最大MPを取得する。"""

        return get_character_battle_max_resource(
            self.character,
            "mp",
        )

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