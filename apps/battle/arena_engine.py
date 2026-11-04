from apps.battle.combatants import PlayerCombatant
from apps.inventory.services import get_equipment_special_multiplier

from apps.battle.engine.calculations import (
    calculate_hit_rate,
    calculate_physical_damage,
    calculate_critical_rate,
    calculate_critical_multiplier,
    roll_percent,
)

from apps.battle.engine.character_stats import (
    get_character_combat_stat,
    apply_character_damage_race_bonus,
    apply_character_received_damage_race_bonus,
)

class ArenaBattleEngine:
    """
    闘技場専用のPvP戦闘エンジン。

    通常探索の

        PlayerCombatant vs EnemyCombatant

    とは異なり、

        PlayerCombatant vs PlayerCombatant

    で戦闘する。

    HP / MPはCharacter本体ではなく、
    ArenaStateに保存された値から開始する。

    STは闘技場戦ごとに100から開始する。
    """

    def __init__(
        self,
        challenger,
        defender,
        challenger_state,
        defender_state,
    ):
        # ========================================
        # 自分自身とは戦えない
        # ========================================

        if challenger.pk == defender.pk:
            raise ValueError(
                "自分自身とは闘技場で対戦できません。"
            )

        self.challenger = challenger
        self.defender = defender

        self.challenger_state = challenger_state
        self.defender_state = defender_state

        # ========================================
        # 挑戦者
        # ========================================

        self.challenger_combatant = PlayerCombatant(
            challenger,

            # STは毎戦100から開始
            starting_stamina=100,

            # ArenaStateのHP / MPを使用
            starting_hp=challenger_state.current_hp,
            starting_mp=challenger_state.current_mp,
        )

        # ========================================
        # 防衛者
        # ========================================

        self.defender_combatant = PlayerCombatant(
            defender,

            # 防衛者もSTは毎戦100
            starting_stamina=100,

            # 前回防衛戦の残HP / MPを引き継ぐ
            starting_hp=defender_state.current_hp,
            starting_mp=defender_state.current_mp,
        )

        # 戦闘ログ
        self.logs = []

        # ========================================
        # 闘技場：状態異常
        # ========================================

        self.status_effects = {
            challenger.pk: {
                "poison": 0,
                "paralysis": 0,
                "dex_down": 0,
            },
            defender.pk: {
                "poison": 0,
                "paralysis": 0,
                "dex_down": 0,
            },
        }

    # ========================================================
    # 戦闘中ステータス
    # ========================================================

    def get_combat_stat(
        self,
        character,
        combatant,
        stat_name,
    ):
        """
        探索と同じ共通計算を使って、
        闘技場での有効ステータスを取得する。
        """

        return get_character_combat_stat(
            character,
            stat_name,

            current_hp=combatant.hp,
            max_hp=combatant.max_hp,

            current_stamina=combatant.stamina,
            max_stamina=combatant.max_stamina,
        )


    # ========================================================
    # 闘技場：装備特殊能力の状態異常付与
    # ========================================================

    def apply_equipment_status_effects(
        self,
        attacker,
        defender,
    ):
        """
        攻撃命中時に装備特殊能力を抽選する。

        毒牙：2%
        痺れ刃：0.5%
        衰弱：2%

        状態異常は防御者にのみ付与する。
        """

        from apps.inventory.models import OwnedEquipment

        effects = set(
            OwnedEquipment.objects.filter(
                character=attacker,
                is_equipped=True,
                special_effect__in=[
                    "poison",
                    "paralysis",
                    "dex_down",
                ],
            ).values_list(
                "special_effect",
                flat=True,
            )
        )

        status = self.status_effects[defender.pk]

        if (
            "poison" in effects
            and roll_percent(2)
        ):
            status["poison"] = max(
                status["poison"],
                1,
            )

            self.logs.append(
                f"{defender.name}は毒状態になった！"
            )

        if (
            "paralysis" in effects
            and roll_percent(0.5)
        ):
            status["paralysis"] = max(
                status["paralysis"],
                1,
            )

            self.logs.append(
                f"{defender.name}は麻痺状態になった！"
            )

        if (
            "dex_down" in effects
            and roll_percent(2)
        ):
            status["dex_down"] = max(
                status["dex_down"],
                1,
            )

            self.logs.append(
                f"{defender.name}は衰弱状態になった！"
            )

    # ========================================================
    # 闘技場：行動開始時の状態異常
    # ========================================================

    def process_status_before_action(
        self,
        character,
        combatant,
    ):
        """
        毒・麻痺を処理する。

        戻り値：
        True  = 行動可能
        False = 行動不能
        """

        status = self.status_effects[character.pk]

        # ===== 毒 =====

        if status["poison"] > 0:

            poison_damage = max(
                1,
                int(combatant.max_hp * 0.10),
            )

            combatant.take_damage(poison_damage)
            status["poison"] -= 1

            self.logs.append(
                f"{character.name}は毒で"
                f"{poison_damage}ダメージ！"
            )

            if not combatant.is_alive():
                return False

        # ===== 麻痺 =====

        if status["paralysis"] > 0:

            status["paralysis"] -= 1

            self.logs.append(
                f"{character.name}は麻痺して行動できない！"
            )

            return False

        return True



    # ========================================================
    # PvP通常攻撃
    # ========================================================

    def normal_attack(
        self,
        attacker,
        attacker_combatant,
        defender,
        defender_combatant,
    ):
        """
        プレイヤー同士の通常攻撃。

        探索と同じ

        ・命中率
        ・物理ダメージ
        ・クリティカル
        ・種族補正
        ・ST補正

        を使用する。
        """

        # ========================================
        # 状態異常：行動開始時
        # ========================================

        if not self.process_status_before_action(
            attacker,
            attacker_combatant,
        ):
            return {
                "hit": False,
                "critical": False,
                "damage": 0,
            }

        # ========================================
        # 命中率
        # ========================================

        attacker_dex = self.get_combat_stat(
        attacker,
        attacker_combatant,
        "dexterity",
        )

        # ===== 衰弱 =====

        attacker_status = self.status_effects[attacker.pk]

        if attacker_status["dex_down"] > 0:
            attacker_dex *= 0.99
            attacker_status["dex_down"] -= 1

        defender_agi = self.get_combat_stat(
            defender,
            defender_combatant,
            "agility",
        )

        hit_rate = calculate_hit_rate(
            attacker_dex=attacker_dex,
            defender_agi=defender_agi,
        )

        # ========================================
        # 命中判定
        # ========================================

        if not roll_percent(hit_rate):

            self.logs.append(
                f"{attacker.name}の攻撃！ "
                "しかし外れた！"
            )

            # 攻撃したのでSTは消費
            attacker_combatant.consume_stamina(
                5
            )

            return {
                "hit": False,
                "critical": False,
                "damage": 0,
            }

        # ========================================
        # 物理ダメージ
        # ========================================

        attacker_strength = (
            self.get_combat_stat(
                attacker,
                attacker_combatant,
                "strength",
            )
        )

        defender_vitality = (
            self.get_combat_stat(
                defender,
                defender_combatant,
                "vitality",
            )
        )

        damage = calculate_physical_damage(
            strength=attacker_strength,
            defender_vit=defender_vitality,
        )

        # ========================================
        # クリティカル
        # ========================================

        attacker_luck = self.get_combat_stat(
            attacker,
            attacker_combatant,
            "luck",
        )

        defender_luck = self.get_combat_stat(
            defender,
            defender_combatant,
            "luck",
        )

        critical_rate = calculate_critical_rate(
            attacker_luck=attacker_luck,
            defender_luck=defender_luck,
        )

        is_critical = roll_percent(
            critical_rate
        )

        if is_critical:

            damage *= (
                calculate_critical_multiplier(
                    attacker_luck
                )
            )

        # ========================================
        # 種族による与ダメージ補正
        # ========================================

        damage = apply_character_damage_race_bonus(
            attacker,
            damage,
        )

        # ========================================
        # 種族による被ダメージ補正
        # ========================================

        damage = (
            apply_character_received_damage_race_bonus(
                defender,
                damage,
            )
        )

        # ========================================
        # 装備特殊能力：猛攻（攻撃者の物理ダメージ+1%）
        # ========================================

        damage *= get_equipment_special_multiplier(
            attacker,
            "physical_damage",
        )

        # ========================================
        # 装備特殊能力：堅守（防御者の被ダメージ-1%）
        # ========================================

        damage *= get_equipment_special_multiplier(
            defender,
            "damage_reduction",
        )

        # ========================================
        # 最終ダメージ
        # ========================================

        damage = max(
            1,
            int(damage),
        )

        defender_combatant.take_damage(
            damage
        )

        # ========================================
        # 攻撃命中時：装備特殊能力
        # ========================================

        if defender_combatant.is_alive():
            self.apply_equipment_status_effects(
                attacker,
                defender,
            )

        # ========================================
        # ログ
        # ========================================

        if is_critical:

            self.logs.append(
                f"{attacker.name}の攻撃！ "
                "クリティカル！ "
                f"{defender.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{attacker.name}の攻撃！ "
                f"{defender.name}に"
                f"{damage}ダメージ！"
            )

        # ========================================
        # ST消費
        # ========================================

        attacker_combatant.consume_stamina(
            5
        )

        return {
            "hit": True,
            "critical": is_critical,
            "damage": damage,
        }


    # ========================================================
    # 挑戦者 → 防衛者
    # ========================================================

    def challenger_normal_attack(self):

        return self.normal_attack(
            attacker=self.challenger,
            attacker_combatant=(
                self.challenger_combatant
            ),
            defender=self.defender,
            defender_combatant=(
                self.defender_combatant
            ),
        )


    # ========================================================
    # 防衛者 → 挑戦者
    # ========================================================

    def defender_normal_attack(self):

        return self.normal_attack(
            attacker=self.defender,
            attacker_combatant=(
                self.defender_combatant
            ),
            defender=self.challenger,
            defender_combatant=(
                self.challenger_combatant
            ),
        )


    @property
    def challenger_hp(self):
        return self.challenger_combatant.hp

    @challenger_hp.setter
    def challenger_hp(
        self,
        value,
    ):
        self.challenger_combatant.hp = max(
            0,
            min(
                value,
                self.challenger_combatant.max_hp,
            ),
        )

    @property
    def challenger_mp(self):
        return self.challenger_combatant.mp

    @challenger_mp.setter
    def challenger_mp(
        self,
        value,
    ):
        self.challenger_combatant.mp = max(
            0,
            min(
                value,
                self.challenger_combatant.max_mp,
            ),
        )

    @property
    def defender_hp(self):
        return self.defender_combatant.hp

    @defender_hp.setter
    def defender_hp(
        self,
        value,
    ):
        self.defender_combatant.hp = max(
            0,
            min(
                value,
                self.defender_combatant.max_hp,
            ),
        )

    @property
    def defender_mp(self):
        return self.defender_combatant.mp

    @defender_mp.setter
    def defender_mp(
        self,
        value,
    ):
        self.defender_combatant.mp = max(
            0,
            min(
                value,
                self.defender_combatant.max_mp,
            ),
        )


    # ========================================================
    # PvP自動戦闘
    # ========================================================

    def run(self, max_ticks=1000):
        """
        闘技場の戦闘を最後まで自動実行する。

        ・AGIによる行動ゲージ
        ・通常攻撃
        ・ST消費
        ・HPによる勝敗判定
        ・最大ループ到達時は引き分け

        DB保存、EXP、階層移動はここでは行わない。
        """

        self.logs.append(
            f"{self.challenger.name} VS "
            f"{self.defender.name}"
        )
        self.logs.append("闘技場戦闘開始！")

        tick_count = 0

        # ========================================
        # 戦闘ループ
        # ========================================

        while (
            self.challenger_hp > 0
            and self.defender_hp > 0
            and tick_count < max_ticks
        ):
            tick_count += 1

            # ====================================
            # AGIを取得
            # ====================================

            challenger_agi = self.get_combat_stat(
                self.challenger,
                self.challenger_combatant,
                "agility",
            )

            defender_agi = self.get_combat_stat(
                self.defender,
                self.defender_combatant,
                "agility",
            )

            # ====================================
            # 行動ゲージ加算
            # ====================================

            self.challenger_combatant.initiative += max(
                0,
                challenger_agi,
            )

            self.defender_combatant.initiative += max(
                0,
                defender_agi,
            )

            # ====================================
            # 挑戦者の行動
            # ====================================

            if (
                self.challenger_combatant.initiative
                >= 100
            ):
                self.challenger_combatant.initiative -= 100

                self.challenger_normal_attack()

                                # 毒による自滅も含めて戦闘終了を判定
                if (
                    self.challenger_hp <= 0
                    or self.defender_hp <= 0
                ):
                    break

            # ====================================
            # 防衛者の行動
            # ====================================

            if (
                self.defender_combatant.initiative
                >= 100
            ):
                self.defender_combatant.initiative -= 100

                self.defender_normal_attack()

                # 毒による自滅も含めて戦闘終了を判定
                if (
                    self.challenger_hp <= 0
                    or self.defender_hp <= 0
                ):
                    break

        # ========================================
        # 勝敗判定
        # ========================================

        if self.defender_hp <= 0:
            winner = "challenger"

            self.logs.append(
                f"{self.challenger.name}の勝利！"
            )

        elif self.challenger_hp <= 0:
            winner = "defender"

            self.logs.append(
                f"{self.defender.name}の勝利！"
            )

        else:
            winner = "draw"

            self.logs.append(
                "決着がつかず引き分けとなった。"
            )

        # ========================================
        # 戦闘結果
        # ========================================

        return {
            "winner": winner,
            "logs": list(self.logs),

            "challenger_hp": self.challenger_hp,
            "challenger_mp": self.challenger_mp,
            "challenger_stamina": (
                self.challenger_combatant.stamina
            ),

            "defender_hp": self.defender_hp,
            "defender_mp": self.defender_mp,
            "defender_stamina": (
                self.defender_combatant.stamina
            ),

            "tick_count": tick_count,
        }