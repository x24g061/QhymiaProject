import math


# ============================================================
# 戦闘参加者の共通クラス
# ============================================================

class Combatant:
    """
    戦闘に参加するキャラクターの共通クラス。

    プレイヤーと敵の両方が持つ、

    ・名前
    ・HP
    ・MP
    ・イニシアチブ

    をここで管理する。
    """

    def __init__(
        self,
        name,
        max_hp,
        max_mp,
        hp=None,
        mp=None,
    ):
        self.name = name

        self.max_hp = max_hp
        self.max_mp = max_mp

        # HPが指定されていなければ最大HPから開始
        if hp is None:
            hp = max_hp

        # MPが指定されていなければ最大MPから開始
        if mp is None:
            mp = max_mp

        # 最大値を超えないようにする
        self.hp = min(
            max(0, hp),
            max_hp,
        )

        self.mp = min(
            max(0, mp),
            max_mp,
        )

        # 行動順を決めるためのゲージ
        self.initiative = 0


    def is_alive(self):
        """
        生存しているか判定する。
        """

        return self.hp > 0


    def take_damage(self, damage):
        """
        ダメージを受ける。
        HPは0未満にならない。
        """

        damage = max(
            0,
            int(damage),
        )

        self.hp = max(
            0,
            self.hp - damage,
        )

        return damage


    def heal(self, amount):
        """
        HPを回復する。
        最大HPを超えない。
        """

        amount = max(
            0,
            int(amount),
        )

        before_hp = self.hp

        self.hp = min(
            self.max_hp,
            self.hp + amount,
        )

        # 実際に回復した量を返す
        return (
            self.hp
            - before_hp
        )


# ============================================================
# プレイヤー
# ============================================================

class PlayerCombatant(Combatant):
    """
    戦闘中のプレイヤーを表すクラス。
    """

    def __init__(
        self,
        character,
        starting_stamina=100,
    ):

        self.character = character

        # ========================================
        # 戦闘中の最大HP・MP
        # ========================================

        max_hp = character.max_hp
        max_mp = character.max_mp

        # プリースト
        # 最大HP・最大MP +5%
        if character.job == "priest":

            max_hp = math.ceil(
                max_hp * 1.05
            )

            max_mp = math.ceil(
                max_mp * 1.05
            )

        # ========================================
        # 戦闘開始時HP
        # ========================================

        # DB上で全回復状態なら、
        # 職業補正後の最大HPから開始する。
        if (
            character.current_hp
            >= character.max_hp
        ):
            current_hp = max_hp

        else:
            current_hp = min(
                character.current_hp,
                max_hp,
            )

        # ========================================
        # 戦闘開始時MP
        # ========================================

        if (
            character.current_mp
            >= character.max_mp
        ):
            current_mp = max_mp

        else:
            current_mp = min(
                character.current_mp,
                max_mp,
            )

        # 共通クラスの初期化
        super().__init__(
            name=character.name,
            max_hp=max_hp,
            max_mp=max_mp,
            hp=current_hp,
            mp=current_mp,
        )

        # ========================================
        # 戦闘中スタミナ
        # ========================================
        #
        # 探索戦闘では100STから開始する。
        #
        # DB上のcurrent_staminaは直接変更せず、
        # 今回の戦闘中だけこの値を使用する。
        #
        # starting_staminaを外から渡せるようにしておくことで、
        # 将来の闘技場では前戦のSTを引き継げる。
        # ========================================

        self.max_stamina = (
            character.max_stamina
        )

        self.stamina = min(
            self.max_stamina,
            max(
                0,
                starting_stamina,
            ),
        )


    def consume_stamina(
        self,
        amount,
    ):
        """
        戦闘中スタミナを消費する。

        0未満にはならない。
        """

        self.stamina = max(
            0,
            self.stamina - amount,
        )


# ============================================================
# 敵
# ============================================================

class EnemyCombatant(Combatant):
    """
    戦闘中の敵1体を表すクラス。

    Enemyモデルは敵の基本データ。
    EnemyCombatantは、
    「今回の戦闘に出てきた敵」を表す。
    """

    def __init__(self, enemy):

        self.enemy = enemy

        super().__init__(
            name=enemy.name,
            max_hp=enemy.max_hp,
            max_mp=enemy.max_mp,
        )

        # ========================================
        # 状態異常
        # ========================================

        # 睡眠
        self.sleep_turns = 0

        # 毒
        self.poison_turns = 0

        # 麻痺
        self.paralysis_turns = 0

        # DEX低下
        self.dex_debuff_rate = 0.0