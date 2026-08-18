from django.db import models

from apps.accounts.models import Character


class Item(models.Model):
    """ゲーム内に存在するアイテムのマスターデータ。"""

    class Category(models.TextChoices):
        CONSUMABLE = "consumable", "消耗品"
        EQUIPMENT = "equipment", "装備品"
        MATERIAL = "material", "素材"
        KEY_ITEM = "key_item", "重要アイテム"

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