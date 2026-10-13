import random


# ============================================================
# BattleEngine 戦闘状態アクセス
# ============================================================

class BattleStateMixin:

    # ========================================================
    # プレイヤーHP
    # ========================================================

    @property
    def player_hp(self):
        """
        プレイヤーの現在HPを返す。

        実際のHPはPlayerCombatant側で管理する。
        """

        return self.player_combatant.hp


    @player_hp.setter
    def player_hp(self, value):
        """
        プレイヤーHPを変更する。

        既存のBattleEngine側から
        self.player_hpを書き換えても、
        PlayerCombatant.hpへ反映される。
        """

        self.player_combatant.hp = value


    # ========================================================
    # プレイヤーMP
    # ========================================================

    @property
    def player_mp(self):
        """
        プレイヤーの現在MPを返す。

        実際のMPはPlayerCombatant側で管理する。
        """

        return self.player_combatant.mp


    @player_mp.setter
    def player_mp(self, value):
        """
        プレイヤーMPを変更する。

        既存のBattleEngine側から
        self.player_mpを書き換えても、
        PlayerCombatant.mpへ反映される。
        """

        self.player_combatant.mp = value


    # ========================================================
    # プレイヤースタミナ
    # ========================================================

    @property
    def player_stamina(self):
        """現在の戦闘中スタミナを返す。"""

        return (
            self.player_combatant.stamina
        )


    @property
    def player_max_stamina(self):
        """戦闘中の最大スタミナを返す。"""

        return (
            self.player_combatant.max_stamina
        )


    # ========================================================
    # プレイヤーイニシアチブ
    # ========================================================

    @property
    def player_initiative(self):
        """
        プレイヤーの行動ゲージを返す。

        実際の値はPlayerCombatant側で管理する。
        """

        return (
            self.player_combatant.initiative
        )


    @player_initiative.setter
    def player_initiative(
        self,
        value,
    ):
        """
        プレイヤーの行動ゲージを変更する。
        """

        self.player_combatant.initiative = value


    # ========================================================
    # 現在の敵
    # ========================================================

    @property
    def enemy(self):
        """
        現在ターゲット中のEnemyモデルを返す。

        既存コードの
        self.enemy.name
        self.enemy.agility
        などをそのまま使えるようにする。
        """

        return (
            self.enemy_combatant.enemy
        )


    # ========================================================
    # 現在の敵Combatant
    # ========================================================

    @property
    def enemy_combatant(self):
        """
        現在攻撃対象になっている敵を返す。

        既存コードでは
        self.enemy_combatant
        を大量に使用しているため、

        内部をリスト化しても
        今までと同じ書き方で使えるようにする。
        """

        return self.enemy_combatants[
            self.current_enemy_index
        ]


    # ========================================================
    # 生存中の敵
    # ========================================================

    def get_alive_enemy_combatants(self):
        """
        まだ生きている敵だけを返す。
        """

        return [
            enemy
            for enemy
            in self.enemy_combatants
            if enemy.is_alive()
        ]


    # ========================================================
    # ランダムターゲット選択
    # ========================================================

    def select_random_alive_enemy(self):
        """
        現在生存している敵の中から
        ランダムで1体を攻撃対象にする。

        生存敵がいなければFalseを返す。
        """

        alive_indexes = [
            index
            for index, enemy
            in enumerate(
                self.enemy_combatants
            )
            if enemy.is_alive()
        ]

        if not alive_indexes:
            return False

        self.current_enemy_index = (
            random.choice(
                alive_indexes
            )
        )

        return True


    # ========================================================
    # 敵HP
    # ========================================================

    @property
    def enemy_hp(self):
        """
        敵の現在HPを返す。

        実際のHPはEnemyCombatant側で管理する。
        """

        return self.enemy_combatant.hp


    @enemy_hp.setter
    def enemy_hp(self, value):
        """
        敵HPを変更する。

        既存のBattleEngine側から
        self.enemy_hpを書き換えても、
        EnemyCombatant.hpへ反映される。
        """

        self.enemy_combatant.hp = value


    # ========================================================
    # 敵の睡眠
    # ========================================================

    @property
    def enemy_sleep_turns(self):
        """敵の睡眠残りターンを返す。"""

        return (
            self.enemy_combatant.sleep_turns
        )


    @enemy_sleep_turns.setter
    def enemy_sleep_turns(self, value):
        """敵の睡眠残りターンを変更する。"""

        self.enemy_combatant.sleep_turns = value


    # ========================================================
    # 敵の毒
    # ========================================================

    @property
    def enemy_poison_turns(self):
        """敵の毒残りターンを返す。"""

        return (
            self.enemy_combatant.poison_turns
        )


    @enemy_poison_turns.setter
    def enemy_poison_turns(self, value):
        """敵の毒残りターンを変更する。"""

        self.enemy_combatant.poison_turns = value


    # ========================================================
    # 敵の麻痺
    # ========================================================

    @property
    def enemy_paralysis_turns(self):
        """敵の麻痺残りターンを返す。"""

        return (
            self.enemy_combatant.paralysis_turns
        )


    @enemy_paralysis_turns.setter
    def enemy_paralysis_turns(self, value):
        """敵の麻痺残りターンを変更する。"""

        self.enemy_combatant.paralysis_turns = value


    # ========================================================
    # 敵のDEXデバフ
    # ========================================================

    @property
    def enemy_dex_debuff_rate(self):
        """敵のDEX低下率を返す。"""

        return (
            self.enemy_combatant.dex_debuff_rate
        )


    @enemy_dex_debuff_rate.setter
    def enemy_dex_debuff_rate(
        self,
        value,
    ):
        """敵のDEX低下率を変更する。"""

        self.enemy_combatant.dex_debuff_rate = value


    # ========================================================
    # 敵イニシアチブ
    # ========================================================

    @property
    def enemy_initiative(self):
        """
        敵の行動ゲージを返す。

        実際の値はEnemyCombatant側で管理する。
        """

        return (
            self.enemy_combatant.initiative
        )


    @enemy_initiative.setter
    def enemy_initiative(
        self,
        value,
    ):
        """
        敵の行動ゲージを変更する。
        """

        self.enemy_combatant.initiative = value