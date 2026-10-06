from django.db import models
from django.core.exceptions import ValidationError

from apps.accounts.models import Character


class Item(models.Model):
    """ゲーム内に存在するアイテムのマスターデータ。"""

    class Category(models.TextChoices):
        CONSUMABLE = "consumable", "消耗品"
        EQUIPMENT = "equipment", "装備品"
        MATERIAL = "material", "素材"
        KEY_ITEM = "key_item", "重要アイテム"
        SYSTEM = "system", "システム"

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="アイテム名",
    )

    description = models.TextField(
        blank=True,
        help_text="アイテムの説明",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        help_text="アイテムの種類",
    )

    buy_price = models.PositiveIntegerField(
        default=0,
        help_text="購入価格",
    )

    sell_price = models.PositiveIntegerField(
        default=0,
        help_text="売却価格",
    )

    is_usable = models.BooleanField(
        default=False,
        help_text="使用可能なアイテムか",
    )

    npc_purchasable = models.BooleanField(
    default=False,
    help_text="NPCショップから購入できるか",
    )

    npc_sellable = models.BooleanField(
    default=True,
    help_text="NPCショップへ売却できるか",
    )

    market_sellable = models.BooleanField(
    default=True,
    help_text="フリマへ出品できるか",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    """キャラクターが所持しているアイテムと個数。"""

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="inventory_items",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="inventory_entries",
    )

    quantity = models.PositiveIntegerField(
        default=1,
        help_text="所持数",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["item__category", "item__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "item"],
                name="unique_character_item",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="inventory_quantity_gte_1",
            ),
        ]

    def __str__(self):
        return f"{self.character.name} - {self.item.name} × {self.quantity}"


# ============================================================
# 装備マスター
# ============================================================

class Equipment(models.Model):
    """
    ゲーム内に存在する装備のマスターデータ。

    Item:
        アイテム共通情報

    Equipment:
        装備固有情報
    """

    # ===== 装備ランク =====

    class Rank(models.TextChoices):
        E = "E", "E"
        D = "D", "D"
        C = "C", "C"
        B = "B", "B"
        A = "A", "A"
        S = "S", "S"


    # ===== 装備部位 =====

    class Slot(models.TextChoices):
        WEAPON = "weapon", "武器"
        HEAD = "head", "頭具"
        ARMOR = "armor", "防具"
        FEET = "feet", "足具"
        ACCESSORY = "accessory", "アクセサリー"


    # ===== 装備傾向 =====

    class Style(models.TextChoices):
        PHYSICAL = "physical", "物理型"
        MAGIC = "magic", "魔法型"


    # Itemマスターと1対1
    item = models.OneToOneField(
        Item,
        on_delete=models.CASCADE,
        related_name="equipment_data",
    )

    rank = models.CharField(
        max_length=1,
        choices=Rank.choices,
        default=Rank.E,
    )

    slot = models.CharField(
        max_length=20,
        choices=Slot.choices,
    )

    style = models.CharField(
        max_length=20,
        choices=Style.choices,
        help_text="物理型または魔法型",
    )

    # +0時点の戦闘力
    base_battle_power = (
        models.PositiveIntegerField(
            help_text="未強化時の装備戦闘力",
        )
    )


    # ========================================================
    # ステータス補正割合
    #
    # 合計100%を基本とする。
    #
    # 例:
    # STR60 / INT0 / DEX20 /
    # AGI10 / VIT0 / LUK10
    # ========================================================

    strength_rate = models.PositiveSmallIntegerField(
        default=0
    )

    intelligence_rate = models.PositiveSmallIntegerField(
        default=0
    )

    dexterity_rate = models.PositiveSmallIntegerField(
        default=0
    )

    agility_rate = models.PositiveSmallIntegerField(
        default=0
    )

    vitality_rate = models.PositiveSmallIntegerField(
        default=0
    )

    luck_rate = models.PositiveSmallIntegerField(
        default=0
    )


    def clean(self):
        """
        ステータス補正割合の合計が
        100%になっていることを確認する。
        """

        total = (
            self.strength_rate
            + self.intelligence_rate
            + self.dexterity_rate
            + self.agility_rate
            + self.vitality_rate
            + self.luck_rate
        )

        if total != 100:
            raise ValidationError(
                "装備のステータス補正割合は"
                "合計100%にしてください。"
            )


    def get_stat_rate(
        self,
        stat_name,
    ):
        """
        指定したステータスの
        補正割合を返す。
        """

        rates = {
            "strength": self.strength_rate,
            "intelligence":
                self.intelligence_rate,
            "dexterity": self.dexterity_rate,
            "agility": self.agility_rate,
            "vitality": self.vitality_rate,
            "luck": self.luck_rate,
        }

        return rates.get(
            stat_name,
            0,
        )


    def __str__(self):
        return (
            f"[{self.rank}] "
            f"{self.item.name}"
        )


# ============================================================
# プレイヤー所持装備
# ============================================================

class OwnedEquipment(models.Model):
    """
    キャラクターが実際に所持している装備。

    同じ装備でも、
    +値や現在戦闘力が違うため
    1個ずつ別レコードとして管理する。
    """

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="owned_equipments",
    )

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name="owned_instances",
    )

    # 強化値
    # 上限なし
    enhancement_level = (
        models.PositiveIntegerField(
            default=0,
        )
    )

    # 現在の装備戦闘力
    #
    # +0ならbase_battle_power。
    # 合成成功時にここを上昇させる。
    battle_power = (
        models.PositiveIntegerField()
    )

    # 現在装備しているか
    is_equipped = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )


    def get_stat_bonus(
        self,
        stat_name,
    ):
        """
        この装備による
        ステータス加算値を返す。

        装備戦闘力 ÷ 2
        × 補正割合
        """

        rate = (
            self.equipment
            .get_stat_rate(
                stat_name
            )
        )

        bonus = (
            (self.battle_power / 2)
            * (rate / 100)
        )

        # ステータスは整数で扱うため
        # 小数点以下は切り捨て
        return int(bonus)


    def __str__(self):

        return (
            f"{self.character.name} - "
            f"{self.equipment.item.name} "
            f"+{self.enhancement_level}"
        )