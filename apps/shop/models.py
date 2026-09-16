from django.db import models

from apps.accounts.models import Character
from apps.inventory.models import Item


class ShopStock(models.Model):
    """ショップで販売するアイテムと在庫情報。"""

    item = models.OneToOneField(
        Item,
        on_delete=models.CASCADE,
        related_name="shop_stock",
    )

    stock = models.PositiveIntegerField(
        default=0,
        help_text="現在の在庫数",
    )

    sale_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ショップ専用価格。未設定ならItem.buy_priceを使用",
    )

    is_available = models.BooleanField(
        default=True,
        help_text="ショップで販売中か",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["item__category", "item__name"]

    @property
    def price(self):
        """販売価格を返す。sale_price未設定時はItem.buy_priceを使う。"""
        if self.sale_price is not None:
            return self.sale_price

        return self.item.buy_price

    def __str__(self):
        return f"{self.item.name} - 在庫 {self.stock}"


class MarketListing(models.Model):

    class Status(models.TextChoices):
        LISTED = "listed", "出品中"
        SOLD = "sold", "売却済み"
        CANCELLED = "cancelled", "キャンセル"

    seller = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="market_listings",
    )

    buyer = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="market_purchases",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="market_listings",
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    unit_price = models.PositiveIntegerField(
        help_text="1個あたりの販売価格",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LISTED,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    sold_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return (
            f"{self.item.name} ×{self.quantity} "
            f"- {self.unit_price}Q"
        )