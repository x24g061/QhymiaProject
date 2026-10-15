from apps.battle.combatants import PlayerCombatant


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