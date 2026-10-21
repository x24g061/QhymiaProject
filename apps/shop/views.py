from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from apps.accounts.models import Character
from apps.inventory.models import InventoryItem

from .models import (
    ShopStock,
    MarketListing,
)

# =========================
# フリーマーケット画面
# =========================
def shop(request):

    character = None
    inventory_items = []

    if request.user.is_authenticated:

        character = getattr(
            request.user,
            "character",
            None,
        )

        if character:

            inventory_items = (
                InventoryItem.objects
                .filter(
                    character=character,
                    item__market_sellable=True,
                )
                .exclude(
                    item__category="equipment",
                )
                .select_related(
                    "item",
                )
                .order_by(
                    "item__category",
                    "item__name",
                )
            )

    market_listings = (
        MarketListing.objects
        .filter(
            status=MarketListing.Status.LISTED,
        )
        .select_related(
            "item",
            "seller",
        )
        .order_by(
            "-created_at",
        )
    )

    return render(
        request,
        "shop.html",
        {
            "character": character,
            "inventory_items": inventory_items,
            "market_listings": market_listings,
        },
    )

# =========================
# フリーマーケット出品処理
# =========================
@login_required
@transaction.atomic
def create_market_listing(
    request,
    inventory_item_id,
):

    if request.method != "POST":
        return redirect(
            "shop:shop"
        )

    character = getattr(
        request.user,
        "character",
        None,
    )

    if character is None:

        messages.error(
            request,
            "キャラクターを作成してから利用してください。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 所持アイテム取得
    # ========================================================

    try:

        inventory_item = (
            InventoryItem.objects
            .select_for_update()
            .select_related(
                "item",
            )
            .get(
                id=inventory_item_id,
                character=character,
            )
        )

    except InventoryItem.DoesNotExist:

        messages.error(
            request,
            "アイテムが見つかりません。",
        )

        return redirect(
            "shop:shop"
        )


    item = inventory_item.item


    # ========================================================
    # 出品可能チェック
    # ========================================================

    if not item.market_sellable:

        messages.error(
            request,
            "このアイテムはフリーマーケットへ出品できません。",
        )

        return redirect(
            "shop:shop"
        )


    # 今回は通常アイテムのみ対応
    if item.category == "equipment":

        messages.error(
            request,
            "装備品の出品にはまだ対応していません。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 個数・価格取得
    # ========================================================

    try:

        quantity = int(
            request.POST.get(
                "quantity",
                0,
            )
        )

        unit_price = int(
            request.POST.get(
                "unit_price",
                0,
            )
        )

    except ValueError:

        messages.error(
            request,
            "個数と価格には数字を入力してください。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 入力値チェック
    # ========================================================

    if quantity < 1:

        messages.error(
            request,
            "出品数は1個以上にしてください。",
        )

        return redirect(
            "shop:shop"
        )


    if unit_price < 1:

        messages.error(
            request,
            "価格は1Q以上にしてください。",
        )

        return redirect(
            "shop:shop"
        )


    if quantity > inventory_item.quantity:

        messages.error(
            request,
            "所持数を超えて出品することはできません。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # フリーマーケットへ出品
    # ========================================================

    MarketListing.objects.create(
        seller=character,
        item=item,
        quantity=quantity,
        unit_price=unit_price,
        status=MarketListing.Status.LISTED,
    )


    # ========================================================
    # 所持アイテムを減らす
    # ========================================================

    if inventory_item.quantity == quantity:

        inventory_item.delete()

    else:

        inventory_item.quantity -= quantity

        inventory_item.save(
            update_fields=[
                "quantity",
            ]
        )


    messages.success(
        request,
        (
            f"{item.name}を"
            f"{quantity}個、"
            f"1個{unit_price}Qで出品しました。"
        ),
    )

    return redirect(
        "shop:shop"
    )

# =========================
# フリーマーケット購入処理
# =========================
@login_required
@transaction.atomic
def buy_market_listing(
    request,
    listing_id,
):

    if request.method != "POST":
        return redirect(
            "shop:shop"
        )

    buyer = getattr(
        request.user,
        "character",
        None,
    )

    if buyer is None:

        messages.error(
            request,
            "キャラクターを作成してから利用してください。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 出品取得
    # ========================================================

    try:

        listing = (
            MarketListing.objects
            .select_for_update()
            .select_related(
                "item",
                "seller",
            )
            .get(
                id=listing_id,
            )
        )

    except MarketListing.DoesNotExist:

        messages.error(
            request,
            "出品情報が見つかりません。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 出品状態チェック
    # ========================================================

    if listing.status != MarketListing.Status.LISTED:

        messages.error(
            request,
            "この商品はすでに販売終了しています。",
        )

        return redirect(
            "shop:shop"
        )


    # 自分の商品は購入不可
    if listing.seller_id == buyer.id:

        messages.error(
            request,
            "自分が出品した商品は購入できません。",
        )

        return redirect(
            "shop:shop"
        )


    total_price = (
        listing.quantity
        * listing.unit_price
    )


    # ========================================================
    # 所持Qチェック
    # ========================================================

    if buyer.gold < total_price:

        messages.error(
            request,
            "所持Qが足りません。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 購入者Qを減らす
    # ========================================================

    buyer.gold -= total_price

    buyer.save(
        update_fields=[
            "gold",
        ]
    )


    # ========================================================
    # 出品者へQを加算
    # ========================================================

    seller = Character.objects.select_for_update().get(
        id=listing.seller_id
    )

    seller.gold += total_price

    seller.save(
        update_fields=[
            "gold",
        ]
    )


    # ========================================================
    # 購入者へアイテム追加
    # ========================================================

    inventory_item, created = (
        InventoryItem.objects.get_or_create(
            character=buyer,
            item=listing.item,
            defaults={
                "quantity": listing.quantity,
            },
        )
    )

    if not created:

        inventory_item.quantity += (
            listing.quantity
        )

        inventory_item.save(
            update_fields=[
                "quantity",
            ]
        )


    # ========================================================
    # 出品を売却済みに変更
    # ========================================================

    from django.utils import timezone

    listing.buyer = buyer
    listing.status = (
        MarketListing.Status.SOLD
    )
    listing.sold_at = (
        timezone.now()
    )

    listing.save(
        update_fields=[
            "buyer",
            "status",
            "sold_at",
        ]
    )


    messages.success(
        request,
        (
            f"{listing.item.name}を"
            f"{listing.quantity}個、"
            f"{total_price}Qで購入しました。"
        ),
    )

    return redirect(
        "shop:shop"
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