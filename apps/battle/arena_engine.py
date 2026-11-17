from types import SimpleNamespace

from apps.battle.services import BattleEngine
from apps.battle.combatants import PlayerCombatant
from apps.battle.timeline import arena_turn_snapshot
from apps.battle.initiative import calculate_gauge_gain, action_priority
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

class ArenaStatus:
    """旧状態辞書APIからCombatantへの参照。二重の状態を保持しない。"""
    fields = {"poison": "poison_turns", "paralysis": "paralysis_turns",
              "dex_down": "equipment_dex_debuff_rate"}

    def __init__(self, combatant):
        self.combatant = combatant

    def __getitem__(self, key):
        value = getattr(self.combatant, self.fields[key])
        return int(bool(value)) if key == "dex_down" else value

    def __setitem__(self, key, value):
        setattr(self.combatant, self.fields[key], 0.01 if key == "dex_down" and value else value)


class ArenaSkillActor(BattleEngine):
    """実キャラクター同士を探索のスキル実行器に接続。run/報酬/DB保存は呼ばない。"""
    def __init__(self, arena, combatant, target):
        self.arena = arena
        self.character = combatant.character
        self.player_combatant = combatant
        self.player_max_hp, self.player_max_mp = combatant.max_hp, combatant.max_mp
        self.enemy_combatants = [target]
        self.current_enemy_index = 0
        self.logs = arena.logs
        self.initialize_presets()
        self.initialize_skill_state()

    @property
    def enemy(self):
        target = self.enemy_combatant.character
        return SimpleNamespace(name=target.name, attribute=target.get_main_attribute())

    def get_player_stat(self, stat_name):
        return self.arena.get_combat_stat(self.character, self.player_combatant, stat_name)

    # 既存の闘技場計算APIは共通関数への委譲を維持する。
    @staticmethod
    def roll_percent(rate):
        return roll_percent(rate)

    @staticmethod
    def calculate_hit_rate(**kwargs):
        return calculate_hit_rate(**kwargs)

    @staticmethod
    def calculate_physical_damage(**kwargs):
        return calculate_physical_damage(**kwargs)

    def apply_player_damage_race_bonus(self, damage):
        return apply_character_damage_race_bonus(self.character, damage)

    def apply_player_received_damage_race_bonus(self, damage):
        return apply_character_received_damage_race_bonus(self.character, damage)

    def get_attack_equipment_multiplier(self, code):
        return get_equipment_special_multiplier(self.character, code)


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
        self.turn_timeline = []

        self.challenger_actor = ArenaSkillActor(self, self.challenger_combatant, self.defender_combatant)
        self.defender_actor = ArenaSkillActor(self, self.defender_combatant, self.challenger_combatant)
        self.challenger_combatant.skill_actor = self.challenger_actor
        self.defender_combatant.skill_actor = self.defender_actor
        # 既存の状態参照APIもCombatantの同じ状態を参照する。
        self.status_effects = {
            challenger.pk: ArenaStatus(self.challenger_combatant),
            defender.pk: ArenaStatus(self.defender_combatant),
        }

    def get_combat_stat(self, character, combatant, stat_name):
        return BattleEngine.get_player_stat(combatant.skill_actor, stat_name)

    def process_status_before_action(self, character, combatant):
        return combatant.skill_actor.process_action_status(combatant)

    def take_turn(self, combatant):
        actor = combatant.skill_actor
        try:
            code = actor.player_turn()
            actor.finish_player_action(code)
            return code
        finally:
            combatant.equipment_dex_debuff_rate = 0.0

    def challenger_turn(self):
        return self.take_turn(self.challenger_combatant)

    def defender_turn(self):
        return self.take_turn(self.defender_combatant)

    def normal_attack(self, attacker, attacker_combatant, defender, defender_combatant):
        """既存の単発通常攻撃API。計算は探索と共通、ゲージは消費しない。"""
        actor = attacker_combatant.skill_actor
        before = defender_combatant.hp
        log_start = len(self.logs)
        if actor.process_action_status(attacker_combatant):
            actor.apply_player_turn_start_race_passive()
            actor.player_normal_attack()
            code = "normal"
        else:
            code = "skip"
        actor.finish_player_action(code)
        attacker_combatant.equipment_dex_debuff_rate = 0.0
        damage = max(0, before - defender_combatant.hp)
        return {"hit": damage > 0, "damage": damage,
                "critical": any("クリティカル" in log for log in self.logs[log_start:])}

    def challenger_normal_attack(self):
        return self.normal_attack(self.challenger, self.challenger_combatant,
                                  self.defender, self.defender_combatant)

    def defender_normal_attack(self):
        return self.normal_attack(self.defender, self.defender_combatant,
                                  self.challenger, self.challenger_combatant)

    @property
    def challenger_hp(self):
        return max(0, self.challenger_combatant.hp)

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
        return max(0, self.defender_combatant.hp)

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
        ・探索共通のプリセット/通常攻撃
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

        # 戦闘開始時の最高AGIを固定
        reference_agi = max(
            1.0,
            self.get_combat_stat(
                self.challenger,
                self.challenger_combatant,
                "agility",
            ),
            self.get_combat_stat(
                self.defender,
                self.defender_combatant,
                "agility",
            ),
        )

        # ========================================
        # 戦闘ループ
        # ========================================

        while (
            self.challenger_hp > 0
            and self.defender_hp > 0
            and tick_count < max_ticks
        ):
            tick_count += 1


            # 全参加者のゲージを更新
            ready = []

            participants = [
                (
                    0, "challenger",
                    self.challenger,
                    self.challenger_combatant,
                ),
                (
                    1, "defender",
                    self.defender,
                    self.defender_combatant,
                ),
            ]

            for order, side, character, combatant in participants:
                effective_agi = self.get_combat_stat(
                    character,
                    combatant,
                    "agility",
                )

                before = combatant.initiative

                gain = calculate_gauge_gain(
                    effective_agi,
                    reference_agi,
                )

                combatant.initiative += gain

                if combatant.initiative >= 100:
                    ready.append((
                        action_priority(
                            before,
                            gain,
                            effective_agi,
                            order,
                        ),
                        side,
                        combatant,
                    ))

            # ゲージ100への到達順で行動
            ready.sort(key=lambda entry: entry[0])

            for _, side, combatant in ready:

                # すでに決着していれば行動しない
                if (
                    self.challenger_hp <= 0
                    or self.defender_hp <= 0
                ):
                    break

                # 1ループ中の行動は最大1回
                # 余剰ゲージは繰り越す
                combatant.initiative -= 100

                log_start = len(self.logs)

                if side == "challenger":
                    self.challenger_turn()

                    self.turn_timeline.append(
                        arena_turn_snapshot(
                            self,
                            "player",
                            self.challenger.name,
                            self.logs[log_start:],
                            len(self.turn_timeline) + 1,
                        )
                    )

                else:
                    self.defender_turn()

                    self.turn_timeline.append(
                        arena_turn_snapshot(
                            self,
                            "enemy",
                            self.defender.name,
                            self.logs[log_start:],
                            len(self.turn_timeline) + 1,
                        )
                    )

                # 毒による自滅も含めて終了判定
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
            "timeline": self.turn_timeline,

            "challenger_hp": max(0, self.challenger_hp),
            "challenger_mp": self.challenger_mp,
            "challenger_stamina": (
                self.challenger_combatant.stamina
            ),

            "defender_hp": max(0, self.defender_hp),
            "defender_mp": self.defender_mp,
            "defender_stamina": (
                self.defender_combatant.stamina
            ),

            "tick_count": tick_count,
        }
