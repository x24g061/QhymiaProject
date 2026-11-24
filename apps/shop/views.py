from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Character
from apps.inventory.models import (
    Item,
    InventoryItem,
    OwnedEquipment,
)

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import (
    ShopStock,
    MarketListing,
    MarketSaleNotification,
)

from django.db.models import (
    Case,
    When,
    Value,
    IntegerField,
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

    if listing.item.category != Item.Category.EQUIPMENT:

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
    # 購入者ロック
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
    # 出品状態確認
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
    # 購入個数
    # ========================================================

    try:

        purchase_quantity = int(
            request.POST.get(
                "quantity",
                1,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        messages.error(
            request,
            "購入個数が正しくありません。",
        )

        return redirect(
            "shop:shop"
        )


    if purchase_quantity < 1:

        messages.error(
            request,
            "購入個数は1個以上にしてください。",
        )

        return redirect(
            "shop:shop"
        )


    # ========================================================
    # 装備か通常アイテムか
    # ========================================================

    is_equipment = (
        listing.owned_equipment_id
        is not None
    )


    # 装備品は必ず1個
    if is_equipment:

        if purchase_quantity != 1:

            messages.error(
                request,
                "装備品は1個ずつ購入してください。",
            )

            return redirect(
                "shop:shop"
            )


    # 通常アイテム
    else:

        if purchase_quantity > listing.quantity:

            messages.error(
                request,
                (
                    "出品されている個数を超えて"
                    "購入することはできません。"
                    f"現在の在庫は{listing.quantity}個です。"
                ),
            )

            return redirect(
                "shop:shop"
            )


    # ========================================================
    # 合計価格
    # ========================================================

    total_price = (
        listing.unit_price
        * purchase_quantity
    )


    # ========================================================
    # 所持Q確認
    # ========================================================

    if buyer.gold < total_price:

        messages.error(
            request,
            (
                f"{purchase_quantity}個購入するには"
                f"{total_price}Q必要です。"
                "所持Qが足りません。"
            ),
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

    owned_equipment = None


    # --------------------------------------------------------
    # 装備
    # --------------------------------------------------------

    if is_equipment:

        owned_equipment = (
            OwnedEquipment.objects
            .select_for_update()
            .get(
                id=listing.owned_equipment_id,
                character=seller,
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
    # 通常アイテム
    # --------------------------------------------------------

    else:

        inventory_item, created = (
            InventoryItem.objects
            .get_or_create(
                character=buyer,
                item=listing.item,
                defaults={
                    "quantity":
                        purchase_quantity,
                },
            )
        )


        if not created:

            inventory_item.quantity += (
                purchase_quantity
            )

            inventory_item.save(
                update_fields=[
                    "quantity",
                ]
            )


    # ========================================================
    # 出品残数更新
    # ========================================================

    if is_equipment:

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


    else:

        listing.quantity -= (
            purchase_quantity
        )


        # ================================================
        # 全部売れた
        # ================================================

        if listing.quantity == 0:

            listing.buyer = buyer

            listing.status = (
                MarketListing.Status.SOLD
            )

            listing.sold_at = (
                timezone.now()
            )

            listing.save(
                update_fields=[
                    "quantity",
                    "buyer",
                    "status",
                    "sold_at",
                ]
            )


        # ================================================
        # まだ残っている
        # ================================================

        else:

            listing.save(
                update_fields=[
                    "quantity",
                ]
            )


    # ========================================================
    # 売却通知
    # ========================================================

    if is_equipment:

        item_name = (
            f"{listing.item.name} "
            f"+{owned_equipment.enhancement_level}"
        )

        sale_message = (
            f"{item_name}が"
            f"{total_price}Qで売れました！"
        )


    else:

        sale_message = (
            f"{listing.item.name}が"
            f"{purchase_quantity}個、"
            f"{total_price}Qで売れました！"
        )


        if listing.quantity > 0:

            sale_message += (
                f" 残り{listing.quantity}個です。"
            )


    # ========================================================
    # 通知保存
    # ========================================================

    notification = (
        MarketSaleNotification.objects
        .create(
            recipient=seller,
            listing=listing,
            message=sale_message,
        )
    )


    # ========================================================
    # WebSocket通知
    # ========================================================

    channel_layer = (
        get_channel_layer()
    )


    if channel_layer is not None:

        group_name = (
            f"sale_user_{seller.user_id}"
        )

        event = {
            "type":
                "sale.notification",

            "notification_id":
                notification.id,

            "message":
                notification.message,

            "created_at":
                notification.created_at.isoformat(),
        }


        def send_sale_notification():

            async_to_sync(
                channel_layer.group_send
            )(
                group_name,
                event,
            )


        transaction.on_commit(
            send_sale_notification,
            robust=True,
        )


    # ========================================================
    # 購入完了メッセージ
    # ========================================================

    if is_equipment:

        messages.success(
            request,
            (
                f"{listing.item.name} "
                f"+{owned_equipment.enhancement_level}を"
                f"{total_price}Qで購入しました。"
            ),
        )


    else:

        messages.success(
            request,
            (
                f"{listing.item.name}を"
                f"{purchase_quantity}個、"
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
        .annotate(
            display_order=Case(

                # ========================================
                # 種族変更アイテム
                # ========================================

                When(
                    item__name="ヒューマンの種族変更証",
                    then=Value(100),
                ),
                When(
                    item__name="エルフの種族変更証",
                    then=Value(101),
                ),
                When(
                    item__name="ドワーフの種族変更証",
                    then=Value(102),
                ),
                When(
                    item__name="ドラゴニアの種族変更証",
                    then=Value(103),
                ),
                When(
                    item__name="ウィッチの種族変更証",
                    then=Value(104),
                ),
                When(
                    item__name="フェアリーの種族変更証",
                    then=Value(105),
                ),
                When(
                    item__name="デモニアの種族変更証",
                    then=Value(106),
                ),

                # ========================================
                # 職業変更アイテム
                # ========================================

                When(
                    item__name="拳闘士の職業変更証",
                    then=Value(200),
                ),
                When(
                    item__name="重戦士の職業変更証",
                    then=Value(201),
                ),
                When(
                    item__name="狩人の職業変更証",
                    then=Value(202),
                ),
                When(
                    item__name="ウィザードの職業変更証",
                    then=Value(203),
                ),
                When(
                    item__name="プリーストの職業変更証",
                    then=Value(204),
                ),
                When(
                    item__name="放浪人の職業変更証",
                    then=Value(205),
                ),
                When(
                    item__name="暗殺者の職業変更証",
                    then=Value(206),
                ),

                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "display_order",
            "item__name",
        )
    )

    character = None

    if request.user.is_authenticated:

        character = getattr(
            request.user,
            "character",
            None,
        )

    fish_inventory = []

    if character is not None:
        fish_inventory = (
            InventoryItem.objects
            .filter(
                character=character,
                item__name__in=[
                    "コモンの魚",
                    "レアの魚",
                    "エピックの魚",
                    "レジェンドの魚",
                ],
                item__category=Item.Category.MATERIAL,
                item__npc_sellable=True,
            )
            .select_related("item")
            .order_by("item__sell_price")
        )

    return render(
        request,
        "npc_shop.html",
        {
            "shop_stocks": shop_stocks,
            "fish_inventory": fish_inventory,
            "character": character,
        },
    )

    character = None




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
    # 購入個数取得
    # ========================================================

    try:

        quantity = int(
            request.POST.get(
                "quantity",
                1,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        messages.error(
            request,
            "購入個数が正しくありません。",
        )

        return redirect(
            "shop:npc_shop"
        )


    if quantity < 1:

        messages.error(
            request,
            "購入個数は1個以上にしてください。",
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

    unit_price = stock.price

    total_price = (
        unit_price
        * quantity
    )


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


    # ========================================================
    # 在庫数チェック
    # ========================================================

    if quantity > stock.stock:

        messages.error(
            request,
            (
                "在庫数を超えて購入することは"
                "できません。"
            ),
        )

        return redirect(
            "shop:npc_shop"
        )


    # ========================================================
    # 所持Qチェック
    # ========================================================

    if character.gold < total_price:

        messages.error(
            request,
            (
                f"{quantity}個購入するには"
                f"{total_price}Q必要です。"
                "所持Qが足りません。"
            ),
        )

        return redirect(
            "shop:npc_shop"
        )


    # ========================================================
    # 所持Qを減らす
    # ========================================================

    character.gold -= (
        total_price
    )

    character.save(
        update_fields=[
            "gold",
        ]
    )


    # ========================================================
    # NPCショップ在庫を減らす
    # ========================================================

    stock.stock -= (
        quantity
    )

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
                "quantity":
                    quantity,
            },
        )
    )


    if not created:

        inventory_item.quantity += (
            quantity
        )

        inventory_item.save(
            update_fields=[
                "quantity",
            ]
        )


    # ========================================================
    # 購入完了
    # ========================================================

    messages.success(
        request,
        (
            f"{item.name}を"
            f"{quantity}個、"
            f"{total_price}Qで購入しました。"
        ),
    )


    return redirect(
        "shop:npc_shop"
    )

# ============================================================
# NPCショップ：魚の売却
# ============================================================

from django.views.decorators.http import require_POST

FISH_SELL_PRICES = {
    "コモンの魚": 2,
    "レアの魚": 5,
    "エピックの魚": 10,
    "レジェンドの魚": 30,
}


@login_required
@require_POST
@transaction.atomic
def sell_fish(request, inventory_item_id):

    # 売却個数の確認
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        messages.error(request, "売却個数が正しくありません。")
        return redirect("shop:npc_shop")

    if quantity < 1:
        messages.error(request, "売却個数は1個以上にしてください。")
        return redirect("shop:npc_shop")

    # キャラクターをロック
    character = (
        Character.objects
        .select_for_update()
        .filter(user=request.user)
        .first()
    )

    if character is None:
        messages.error(request, "キャラクターが見つかりません。")
        return redirect("shop:npc_shop")

    # 自分の所持アイテムのみロックして取得
    inventory_item = (
        InventoryItem.objects
        .select_for_update()
        .select_related("item")
        .filter(
            pk=inventory_item_id,
            character=character,
        )
        .first()
    )

    if inventory_item is None:
        messages.error(request, "売却するアイテムが見つかりません。")
        return redirect("shop:npc_shop")

    item = inventory_item.item

    # 魚以外の売却を禁止
    if (
        item.name not in FISH_SELL_PRICES
        or item.category != Item.Category.MATERIAL
        or not item.npc_sellable
    ):
        messages.error(request, "このアイテムは売却できません。")
        return redirect("shop:npc_shop")

    if quantity > inventory_item.quantity:
        messages.error(request, "所持数を超えて売却できません。")
        return redirect("shop:npc_shop")

    # 固定売却価格
    unit_price = FISH_SELL_PRICES[item.name]
    total_price = unit_price * quantity

    # 魚を消費
    if inventory_item.quantity == quantity:
        inventory_item.delete()
    else:
        inventory_item.quantity -= quantity
        inventory_item.save(update_fields=["quantity"])

    # Qを加算
    character.gold += total_price
    character.save(update_fields=["gold"])

    messages.success(
        request,
        f"{item.name}を{quantity}個売却し、"
        f"{total_price}Qを獲得しました。",
    )

    return redirect("shop:npc_shop")
