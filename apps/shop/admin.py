from django.contrib import admin

from .models import ShopStock


@admin.register(ShopStock)
class ShopStockAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "stock",
        "display_price",
        "is_available",
        "updated_at",
    )

    list_filter = (
        "is_available",
        "item__category",
    )

    search_fields = (
        "item__name",
    )

    list_select_related = (
        "item",
    )

    @admin.display(description="販売価格")
    def display_price(self, obj):
        return obj.price