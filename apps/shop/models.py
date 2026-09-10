from django.db import models

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