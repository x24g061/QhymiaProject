from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from apps.inventory.models import InventoryItem

from .models import ShopStock


# =========================
# フリーマーケット画面
# =========================
def shop(request):
    character = None

    if request.user.is_authenticated:
        character = getattr(request.user, "character", None)

    return render(
        request,
        "shop.html",
        {
            "character": character,
        },
    )


# =========================
# NPCショップ画面
# =========================
def npc_shop(request):
    shop_stocks = (
        ShopStock.objects
        .filter(
            is_available=True,
            item__npc_purchasable=True,
        )
        .exclude(
            item__category="equipment",
        )
        .select_related("item")
    )

    character = None

    if request.user.is_authenticated:
        character = getattr(request.user, "character", None)

    return render(
        request,
        "npc_shop.html",
        {
            "shop_stocks": shop_stocks,
            "character": character,
        },
    )


# =========================
# NPCショップ購入処理
# =========================
@login_required
@transaction.atomic
def buy_item(request, stock_id):
    if request.method != "POST":
        return redirect("shop:npc_shop")

    character = getattr(request.user, "character", None)

    if character is None:
        messages.error(
            request,
            "キャラクターを作成してから購入してください。",
        )
        return redirect("shop:npc_shop")

    stock = (
        ShopStock.objects
        .select_for_update()
        .select_related("item")
        .get(pk=stock_id)
    )

    item = stock.item
    price = stock.price

    if not stock.is_available:
        messages.error(
            request,
            "現在この商品は購入できません。",
        )
        return redirect("shop:npc_shop")

    if not item.npc_purchasable:
        messages.error(
            request,
            "この商品はNPCショップでは購入できません。",
        )
        return redirect("shop:npc_shop")

    if item.category == "equipment":
        messages.error(
            request,
            "装備品はNPCショップでは購入できません。",
        )
        return redirect("shop:npc_shop")

    if stock.stock <= 0:
        messages.error(
            request,
            "この商品は売り切れています。",
        )
        return redirect("shop:npc_shop")

    if character.gold < price:
        messages.error(
            request,
            "所持Qが足りません。",
        )
        return redirect("shop:npc_shop")

    character.gold -= price
    character.save(
        update_fields=["gold"],
    )

    stock.stock -= 1
    stock.save(
        update_fields=["stock"],
    )

    inventory_item, created = (
        InventoryItem.objects.get_or_create(
            character=character,
            item=item,
            defaults={
                "quantity": 1,
            },
        )
    )

    if not created:
        inventory_item.quantity += 1
        inventory_item.save(
            update_fields=["quantity"],
        )

    messages.success(
        request,
        f"{item.name}を1個購入しました。",
    )

    return redirect("shop:npc_shop")