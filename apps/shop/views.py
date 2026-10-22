from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Character
from apps.inventory.models import (
    InventoryItem,
    OwnedEquipment,
)

from .models import (
    ShopStock,
    MarketListing,
)


# ============================================================
# フリーマーケット画面
# ============================================================

def shop(request):

    character = None
    inventory_items = []
    owned_equipments = []

    # ========================================================
    # ログイン中キャラクター
    # ========================================================

    if request.user.is_authenticated:

        character = getattr(
            request.user,
            "character",
            None,
        )

        if character:

            # =================================================
            # フリマへ出品可能な通常アイテム
            # =================================================

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

            # =================================================
            # フリマへ出品可能な装備
            #
            # ・自分の装備
            # ・現在未装備
            # ・フリマ出品可能
            # ・現在出品中ではない
            # =================================================

            owned_equipments = (
                OwnedEquipment.objects
                .filter(
                    character=character,
                    is_equipped=False,
                    equipment__item__market_sellable=True,
                )
                .exclude(
                    market_listings__status=(
                        MarketListing.Status.LISTED
                    ),
                )
                .select_related(
                    "equipment",
                    "equipment__item",
                )
                .order_by(
                    "equipment__rank",
                    "equipment__slot",
                    "equipment__item__name",
                    "enhancement_level",
                )
            )

    # ========================================================
    # 現在販売中の商品
    # ========================================================

    market_listings = (
        MarketListing.objects
        .filter(
            status=MarketListing.Status.LISTED,
        )
        .select_related(
            "item",
            "seller",
            "owned_equipment",
            "owned_equipment__equipment",
            "owned_equipment__equipment__item",
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
            "owned_equipments": owned_equipments,
            "market_listings": market_listings,
        },
    )


# ============================================================
# フリーマーケット
# 通常アイテム出品
# ============================================================

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

    # ========================================================
    # キャラクター取得
    # ========================================================

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
    # 所持アイテム取得・ロック
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

    if item.category == "equipment":

        messages.error(
            request,
            "装備品は装備出品画面から出品してください。",
        )

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # 出品数・単価取得
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

    except (TypeError, ValueError):

        messages.error(
            request,
            "個数と価格には数字を入力してください。",
        )

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # 入力チェック
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
    # 出品作成
    # ========================================================

    MarketListing.objects.create(
        seller=character,
        item=item,
        quantity=quantity,
        unit_price=unit_price,
        status=MarketListing.Status.LISTED,
    )

    # ========================================================
    # 所持数を減らす
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


# ============================================================
# フリーマーケット
# 装備出品
# ============================================================

@login_required
@transaction.atomic
def create_equipment_listing(
    request,
    owned_equipment_id,
):

    if request.method != "POST":

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # キャラクター取得
    # ========================================================

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
    # 所持装備取得・ロック
    # ========================================================

    try:

        owned_equipment = (
            OwnedEquipment.objects
            .select_for_update()
            .select_related(
                "equipment",
                "equipment__item",
            )
            .get(
                id=owned_equipment_id,
                character=character,
            )
        )

    except OwnedEquipment.DoesNotExist:

        messages.error(
            request,
            "装備が見つかりません。",
        )

        return redirect(
            "shop:shop"
        )

    item = owned_equipment.equipment.item

    # ========================================================
    # 出品可能チェック
    # ========================================================

    if owned_equipment.is_equipped:

        messages.error(
            request,
            "装備中の装備は出品できません。",
        )

        return redirect(
            "shop:shop"
        )

    if not item.market_sellable:

        messages.error(
            request,
            "この装備はフリーマーケットへ出品できません。",
        )

        return redirect(
            "shop:shop"
        )

    if MarketListing.objects.filter(
        owned_equipment=owned_equipment,
        status=MarketListing.Status.LISTED,
    ).exists():

        messages.error(
            request,
            "この装備はすでに出品中です。",
        )

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # 価格取得
    # ========================================================

    try:

        unit_price = int(
            request.POST.get(
                "unit_price",
                0,
            )
        )

    except (TypeError, ValueError):

        messages.error(
            request,
            "価格には数字を入力してください。",
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

    # ========================================================
    # 出品作成
    # ========================================================

    MarketListing.objects.create(
        seller=character,
        item=item,
        owned_equipment=owned_equipment,
        quantity=1,
        unit_price=unit_price,
        status=MarketListing.Status.LISTED,
    )

    messages.success(
        request,
        (
            f"{item.name} "
            f"+{owned_equipment.enhancement_level}を"
            f"{unit_price}Qで出品しました。"
        ),
    )

    return redirect(
        "shop:shop"
    )


# ============================================================
# フリーマーケット
# 出品キャンセル
# ============================================================

@login_required
@transaction.atomic
def cancel_market_listing(
    request,
    listing_id,
):

    if request.method != "POST":

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # キャラクター取得
    # ========================================================

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
    # 自分の出品を取得・ロック
    #
    # owned_equipment は NULL の可能性があるため、
    # select_for_update と一緒に select_related しない
    # ========================================================

    try:

        listing = (
            MarketListing.objects
            .select_for_update()
            .select_related(
                "item",
            )
            .get(
                id=listing_id,
                seller=character,
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
            "この出品はキャンセルできません。",
        )

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # 通常アイテムなら所持品へ返却
    #
    # 装備の場合はOwnedEquipment自体を削除していないので、
    # LISTEDではなくなることで再び手持ち一覧へ戻る
    # ========================================================

    if listing.owned_equipment is None:

        inventory_item, created = (
            InventoryItem.objects.get_or_create(
                character=character,
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
    # キャンセル状態へ変更
    # ========================================================

    listing.status = (
        MarketListing.Status.CANCELLED
    )

    listing.save(
        update_fields=[
            "status",
        ]
    )

    messages.success(
        request,
        (
            f"{listing.item.name}の"
            f"出品をキャンセルしました。"
        ),
    )

    return redirect(
        "shop:shop"
    )


# ============================================================
# フリーマーケット
# 購入処理
# ============================================================

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

    # ========================================================
    # 購入者取得
    # ========================================================

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
    # 購入者をロック
    # ========================================================

    buyer = (
        Character.objects
        .select_for_update()
        .get(
            id=buyer.id
        )
    )

    # ========================================================
    # 出品取得・ロック
    #
    # owned_equipment は NULL の可能性があるため、
    # select_for_update と一緒に select_related しない
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

    if listing.seller_id == buyer.id:

        messages.error(
            request,
            "自分が出品した商品は購入できません。",
        )

        return redirect(
            "shop:shop"
        )

    # ========================================================
    # 合計価格
    # ========================================================

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
    # 出品者取得・ロック
    # ========================================================

    seller = (
        Character.objects
        .select_for_update()
        .get(
            id=listing.seller_id
        )
    )

    # ========================================================
    # Q移動
    # ========================================================

    buyer.gold -= total_price

    buyer.save(
        update_fields=[
            "gold",
        ]
    )

    seller.gold += total_price

    seller.save(
        update_fields=[
            "gold",
        ]
    )

    # ========================================================
    # 商品移動
    # ========================================================

    # --------------------------------------------------------
    # 装備の場合
    # --------------------------------------------------------

    if listing.owned_equipment:

        owned_equipment = (
            OwnedEquipment.objects
            .select_for_update()
            .get(
                id=listing.owned_equipment_id
            )
        )

        owned_equipment.character = buyer
        owned_equipment.is_equipped = False

        owned_equipment.save(
            update_fields=[
                "character",
                "is_equipped",
            ]
        )

    # --------------------------------------------------------
    # 通常アイテムの場合
    # --------------------------------------------------------

    else:

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

    # ========================================================
    # 購入完了メッセージ
    # ========================================================

    if listing.owned_equipment:

        messages.success(
            request,
            (
                f"{listing.item.name} "
                f"+{listing.owned_equipment.enhancement_level}を"
                f"{total_price}Qで購入しました。"
            ),
        )

    else:

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


# ============================================================
# NPCショップ画面
# ============================================================

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
        .select_related(
            "item",
        )
    )

    character = None

    if request.user.is_authenticated:

        character = getattr(
            request.user,
            "character",
            None,
        )

    return render(
        request,
        "npc_shop.html",
        {
            "shop_stocks": shop_stocks,
            "character": character,
        },
    )


# ============================================================
# NPCショップ購入処理
# ============================================================

@login_required
@transaction.atomic
def buy_item(
    request,
    stock_id,
):

    if request.method != "POST":

        return redirect(
            "shop:npc_shop"
        )

    # ========================================================
    # キャラクター取得
    # ========================================================

    character = getattr(
        request.user,
        "character",
        None,
    )

    if character is None:

        messages.error(
            request,
            "キャラクターを作成してから購入してください。",
        )

        return redirect(
            "shop:npc_shop"
        )

    # ========================================================
    # 購入キャラクターをロック
    # ========================================================

    character = (
        Character.objects
        .select_for_update()
        .get(
            id=character.id
        )
    )

    # ========================================================
    # NPCショップ在庫をロック
    # ========================================================

    stock = (
        ShopStock.objects
        .select_for_update()
        .select_related(
            "item",
        )
        .get(
            pk=stock_id
        )
    )

    item = stock.item
    price = stock.price

    # ========================================================
    # 購入可能チェック
    # ========================================================

    if not stock.is_available:

        messages.error(
            request,
            "現在この商品は購入できません。",
        )

        return redirect(
            "shop:npc_shop"
        )

    if not item.npc_purchasable:

        messages.error(
            request,
            "この商品はNPCショップでは購入できません。",
        )

        return redirect(
            "shop:npc_shop"
        )

    if item.category == "equipment":

        messages.error(
            request,
            "装備品はNPCショップでは購入できません。",
        )

        return redirect(
            "shop:npc_shop"
        )

    if stock.stock <= 0:

        messages.error(
            request,
            "この商品は売り切れています。",
        )

        return redirect(
            "shop:npc_shop"
        )

    if character.gold < price:

        messages.error(
            request,
            "所持Qが足りません。",
        )

        return redirect(
            "shop:npc_shop"
        )

    # ========================================================
    # 所持Qを減らす
    # ========================================================

    character.gold -= price

    character.save(
        update_fields=[
            "gold",
        ]
    )

    # ========================================================
    # NPCショップ在庫を減らす
    # ========================================================

    stock.stock -= 1

    stock.save(
        update_fields=[
            "stock",
        ]
    )

    # ========================================================
    # アイテムを所持品へ追加
    # ========================================================

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
            update_fields=[
                "quantity",
            ]
        )

    messages.success(
        request,
        f"{item.name}を1個購入しました。",
    )

    return redirect(
        "shop:npc_shop"
    )