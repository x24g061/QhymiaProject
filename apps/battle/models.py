from django.db import models

from apps.accounts.models import Character

from apps.inventory.models import Item


class Skill(models.Model):

    # ===== 属性 =====

    ATTRIBUTE_CHOICES = [
        ("fire", "炎"),
        ("water", "水"),
        ("grass", "草"),
        ("rock", "岩"),
        ("light", "光"),
        ("dark", "闇"),
        ("neutral", "無"),
        ("none", "なし"),
    ]

    # ===== スキル種別 =====

    TYPE_CHOICES = [
        ("physical", "物理"),
        ("magic", "魔法"),
        ("support", "補助"),
        ("heal", "回復"),
        ("physical_support", "物理/補助"),
        ("heal_support", "回復/補助"),
        ("passive", "パッシブ"),
    ]

    # スキルを識別する内部コード
    code = models.CharField(
        max_length=50,
        unique=True,
    )

    # 表示名
    name = models.CharField(
        max_length=50,
    )

    # 使用可能職業
    job = models.CharField(
        max_length=20,
        choices=Character.JOB_CHOICES,
    )

    # 属性
    attribute = models.CharField(
        max_length=20,
        choices=ATTRIBUTE_CHOICES,
        default="neutral",
    )

    # 種別
    skill_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
    )

    # MP消費量
    mp_cost = models.PositiveIntegerField(
        default=0,
    )

    # 発動率
    # 80 = 80%
    activation_rate = models.PositiveSmallIntegerField(
        default=80,
    )

    # パッシブスキルか
    is_passive = models.BooleanField(
        default=False,
    )

    # 画面表示用の説明
    description = models.TextField(
        blank=True,
    )

    def __str__(self):
        return self.name


class SkillPreset(models.Model):

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="skill_presets",
    )

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="presets",
    )

    # 1～5のプリセット位置
    slot = models.PositiveSmallIntegerField()

    # 戦闘中に使用できる回数
    # パッシブの場合は使用しない
    use_count = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        ordering = ["slot"]

        constraints = [
            models.UniqueConstraint(
                fields=["character", "slot"],
                name="unique_character_skill_slot",
            ),
        ]

    def __str__(self):
        return (
            f"{self.character.name} "
            f"{self.slot}: {self.skill.name}"
        )


class Enemy(models.Model):

    ATTRIBUTE_CHOICES = Skill.ATTRIBUTE_CHOICES

    #==== 名前 =====

    name = models.CharField(
        max_length=50,
    )

    # ===== 出現階層 =====

    floor = models.PositiveIntegerField(
        default=1,
        help_text="出現する探索階層",
    )

    # ===== ボス判定 =====

    is_boss = models.BooleanField(
        default=False,
    )

    # ===== レベル =====

    level = models.PositiveIntegerField(
        default=1,
    )

    # ===== HP・MP =====

    max_hp = models.PositiveIntegerField(
        default=30,
    )

    max_mp = models.PositiveIntegerField(
        default=10,
    )

    # ===== 基本能力 =====

    strength = models.PositiveIntegerField(
        default=5,
    )

    intelligence = models.PositiveIntegerField(
        default=5,
    )

    dexterity = models.PositiveIntegerField(
        default=5,
    )

    agility = models.PositiveIntegerField(
        default=5,
    )

    vitality = models.PositiveIntegerField(
        default=5,
    )

    luck = models.PositiveIntegerField(
        default=5,
    )

    # ===== 属性 =====

    attribute = models.CharField(
        max_length=20,
        choices=ATTRIBUTE_CHOICES,
        default="neutral",
    )

    # ===== 経験値報酬 =====

    exp_min = models.PositiveIntegerField(
        default=7,
    )

    exp_max = models.PositiveIntegerField(
        default=12,
    )

    def __str__(self):
        return self.name


class FloorProgress(models.Model):
    """
    キャラクターごとの探索階層進行状況。

    各階層について、
    ・探索回数
    ・ボス撃破済みか
    を保存する。
    """

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="floor_progresses",
    )

    floor = models.PositiveIntegerField(
        help_text="探索階層",
    )

    exploration_count = models.PositiveIntegerField(
        default=0,
        help_text="この階層を探索した回数",
    )

    boss_defeated = models.BooleanField(
        default=False,
        help_text="この階層のボスを撃破済みか",
    )

    class Meta:
        ordering = [
            "character",
            "floor",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "character",
                    "floor",
                ],
                name="unique_character_floor_progress",
            ),
        ]

    def __str__(self):
        return (
            f"{self.character.name} "
            f"{self.floor}階 "
            f"探索{self.exploration_count}回"
        )


class FloorDropItem(models.Model):
    """
    探索階層ごとのドロップ候補。

    装備品・通常アイテムの両方を登録できる。
    """

    floor = models.PositiveIntegerField(
        help_text="探索階層",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="floor_drops",
    )

    drop_weight = (
        models.PositiveIntegerField(
            default=100,
            help_text=(
                "ドロップ候補内での抽選重み。"
                "小さいほど出にくい。"
            ),
        )
    )


class Meta:
    ordering = [
        "floor",
        "item__name",
    ]

    constraints = [
        models.UniqueConstraint(
            fields=["floor", "item"],
            name="unique_floor_drop_item",
        ),
    ]

    def __str__(self):
        return (
            f"{self.floor}階層 - "
            f"{self.item.name}"
        )

# ============================================================
# 闘技場
# ============================================================

class ArenaFloor(models.Model):
    """
    闘技場の各階層を管理する。
    """

    floor = models.PositiveSmallIntegerField(
        primary_key=True,
        help_text="闘技場階層",
    )

    master = models.OneToOneField(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mastered_arena_floor",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(floor__gte=1)
                    & models.Q(floor__lte=100)
                ),
                name="arena_floor_between_1_and_100",
            ),
        ]

    def __str__(self):
        if self.master:
            return (
                f"闘技場{self.floor}階 "
                f"- {self.master.name}"
            )

        return (
            f"闘技場{self.floor}階 "
            "- 空席"
        )


class ArenaState(models.Model):
    """
    キャラクターごとの闘技場状態。

    Character.current_hp / current_mp とは別管理。

    闘技場からHOMEへ戻っても回復せず、
    フロアマスターの防衛戦では
    HP・MPを次の戦闘へ持ち越す。
    """

    character = models.OneToOneField(
        Character,
        on_delete=models.CASCADE,
        related_name="arena_state",
    )

    # 現在いる闘技場階層。
    #
    # ArenaFloorを直接参照することで、
    # 存在しない階に移動できないようにする。
    floor = models.ForeignKey(
        ArenaFloor,
        on_delete=models.PROTECT,
        related_name="players",
    )

    # 通常キャラクターとは別の
    # 闘技場専用HP / MP。
    current_hp = models.PositiveIntegerField(
        default=0,
    )

    current_mp = models.PositiveIntegerField(
        default=0,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return (
            f"{self.character.name} "
            f"- 闘技場{self.floor_id}階"
        )


class ArenaBattleHistory(models.Model):
    """
    闘技場の対戦履歴。

    挑戦者視点で勝敗を保存する。
    """

    class Result(models.TextChoices):
        WIN = "win", "勝利"
        LOSS = "loss", "敗北"
        DRAW = "draw", "引き分け"

    challenger = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="arena_challenge_histories",
    )

    defender = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="arena_defense_histories",
    )

    # 戦闘が行われた階層。
    floor = models.PositiveSmallIntegerField()

    # 挑戦者視点の結果。
    result = models.CharField(
        max_length=10,
        choices=Result.choices,
    )

    # BattleEngineが生成したログを
    # そのまま保存できるようJSONFieldを使う。
    battle_logs = models.JSONField(
        default=list,
        blank=True,
    )

    # 旧履歴は付与量を保存していないため、未記録をNULLで表す。
    gained_exp = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # 戦闘終了時の闘技場HP / MP。
    #
    # 後から戦歴を見返した時にも
    # 当時の状態が分かるよう保存する。
    challenger_hp_after = models.PositiveIntegerField(
        default=0,
    )

    challenger_mp_after = models.PositiveIntegerField(
        default=0,
    )

    defender_hp_after = models.PositiveIntegerField(
        default=0,
    )

    defender_mp_after = models.PositiveIntegerField(
        default=0,
    )

    # 挑戦後に両者がどの階へ移動したか。
    challenger_floor_after = models.PositiveSmallIntegerField()

    defender_floor_after = models.PositiveSmallIntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return (
            f"{self.floor}階 "
            f"{self.challenger.name} "
            f"vs {self.defender.name} "
            f"({self.get_result_display()})"
        )


