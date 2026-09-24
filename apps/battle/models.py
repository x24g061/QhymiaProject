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

    name = models.CharField(
        max_length=50,
    )

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


class FloorDropItem(models.Model):
    """探索階層ごとの装備品ドロップ候補。"""

    floor = models.PositiveIntegerField(
        help_text="探索階層",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="floor_drops",
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