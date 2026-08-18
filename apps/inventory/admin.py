from django.contrib import admin

from .models import InventoryItem, Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "buy_price",
        "sell_price",
        "is_usable",
    )
    list_filter = (
        "category",
        "is_usable",
    )
    search_fields = (
        "name",
        "description",
    )


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "character",
        "item",
        "quantity",
        "updated_at",
    )
    list_filter = (
        "item__category",
    )
    search_fields = (
        "character__name",
        "item__name",
    )
    list_select_related = (
        "character",
        "item",
    )