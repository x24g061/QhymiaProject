from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Character

from .models import (
    Equipment,
    InventoryItem,
    OwnedEquipment,
)
from .services import (
    equip_item,
    unequip_item,
)


# ============================================================
# 倉庫画面
# ============================================================

@login_required
def inventory(request):
    """
    倉庫画面。

    ・現在装備中の5部位
    ・所持装備
    ・通常アイテム

    を表示する。
    """

    character = request.user.character

    # ========================================================
    # 所持装備
    # ========================================================

    owned_equipments = list(
        OwnedEquipment.objects
        .filter(
            character=character,
        )
        .select_related(
            "equipment",
            "equipment__item",
        )
        .order_by(
            "equipment__slot",
            "equipment__rank",
            "equipment__item__name",
        )
    )


    # ========================================================
    # 通常アイテム
    # ========================================================

    inventory_items = list(
        InventoryItem.objects
        .filter(
            character=character,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__category",
            "item__name",
        )
    )


    # ========================================================
    # 現在装備している装備
    # ========================================================

    equipped_by_slot = {
        owned.equipment.slot: owned
        for owned in owned_equipments
        if owned.is_equipped
    }


    # ========================================================
    # 5部位を必ず表示
    # ========================================================

    equipment_slots = []

    for slot_value, slot_label in (
        Equipment.Slot.choices
    ):

        equipment_slots.append(
            {
                "value": slot_value,
                "label": slot_label,
                "owned": (
                    equipped_by_slot.get(
                        slot_value
                    )
                ),
            }
        )


    # ========================================================
    # 所持品総数
    # ========================================================

    normal_item_count = sum(
        inventory_item.quantity
        for inventory_item
        in inventory_items
    )

    equipment_count = len(
        owned_equipments
    )

    inventory_count = (
        normal_item_count
        + equipment_count
    )


    return render(
        request,
        "inventory.html",
        {
            "character": character,

            "equipment_slots":
                equipment_slots,

            "owned_equipments":
                owned_equipments,

            "inventory_items":
                inventory_items,

            "inventory_count":
                inventory_count,

            # main側テンプレートとの互換用
            "total_item_count":
                inventory_count,
        },
    )


# ============================================================
# 装備する
# ============================================================

@login_required
@require_POST
def equip_equipment(
    request,
    owned_equipment_id,
):
    """
    所持装備を装備する。
    """

    character = request.user.character

    owned_equipment = (
        get_object_or_404(
            OwnedEquipment.objects
            .select_related(
                "equipment",
                "equipment__item",
            ),
            id=owned_equipment_id,
            character=character,
        )
    )

    equip_item(
        character,
        owned_equipment,
    )

    messages.success(
        request,
        (
            f"{owned_equipment.equipment.item.name}"
            "を装備しました。"
        ),
    )

    return redirect(
        "inventory:inventory"
    )


# ============================================================
# 装備を外す
# ============================================================

@login_required
@require_POST
def unequip_equipment(
    request,
    owned_equipment_id,
):
    """
    現在の装備を外す。
    """

    character = request.user.character

    owned_equipment = (
        get_object_or_404(
            OwnedEquipment.objects
            .select_related(
                "equipment",
                "equipment__item",
            ),
            id=owned_equipment_id,
            character=character,
        )
    )

    unequip_item(
        character,
        owned_equipment,
    )

    messages.success(
        request,
        (
            f"{owned_equipment.equipment.item.name}"
            "を外しました。"
        ),
    )

    return redirect(
        "inventory:inventory"
    )


# ============================================================
# アイテム使用
# ============================================================

@login_required
@transaction.atomic
def use_item(
    request,
    inventory_item_id,
):
    """
    所持アイテムを使用する。

    現在はCT短縮時計の効果を実装。
    """

    # POST以外では使用できない
    if request.method != "POST":

        return redirect(
            "inventory:inventory"
        )


    # ========================================================
    # キャラクター取得
    # ========================================================

    character = (
        Character.objects
        .select_for_update()
        .get(
            user=request.user
        )
    )


    # ========================================================
    # 自分の所持アイテム取得
    # ========================================================

    try:

        inventory_item = (
            InventoryItem.objects
            .select_for_update()
            .select_related(
                "item"
            )
            .get(
                pk=inventory_item_id,
                character=character,
            )
        )

    except InventoryItem.DoesNotExist:

        messages.error(
            request,
            "アイテムが見つかりません。",
        )

        return redirect(
            "inventory:inventory"
        )


    item = inventory_item.item


    # ========================================================
    # 使用可能チェック
    # ========================================================

    if not item.is_usable:

        messages.error(
            request,
            "このアイテムは使用できません。",
        )

        return redirect(
            "inventory:inventory"
        )


    # 現在はCT短縮時計のみ対応
    if not item.cooldown_reduction_days:

        messages.error(
            request,
            (
                "このアイテムの使用効果は"
                "まだ実装されていません。"
            ),
        )

        return redirect(
            "inventory:inventory"
        )


    now = timezone.now()


    # ========================================================
    # CT短縮時計の効果期間
    # ========================================================

    already_active = (
        character.exploration_cooldown_reduced_until
        and
        character.exploration_cooldown_reduced_until
        > now
    )


    if already_active:

        # 効果中なら現在の終了日時へ加算
        character.exploration_cooldown_reduced_until += (
            timedelta(
                days=item.cooldown_reduction_days
            )
        )

    else:

        # 新しく効果開始
        character.exploration_cooldown_reduced_until = (
            now
            + timedelta(
                days=item.cooldown_reduction_days
            )
        )


        # ====================================================
        # 初回使用時だけ
        # 現在進行中の探索CTを20秒短縮
        # ====================================================

        if (
            character.exploration_cooldown_until
            and
            character.exploration_cooldown_until > now
        ):

            shortened_until = (
                character.exploration_cooldown_until
                - timedelta(
                    seconds=20
                )
            )

            # 残り20秒以下なら即探索可能
            if shortened_until <= now:

                character.exploration_cooldown_until = now

            else:

                character.exploration_cooldown_until = (
                    shortened_until
                )


    character.save(
        update_fields=[
            "exploration_cooldown_reduced_until",
            "exploration_cooldown_until",
            "updated_at",
        ]
    )


    # ========================================================
    # 使用アイテムを1個消費
    # ========================================================

    if inventory_item.quantity <= 1:

        inventory_item.delete()

    else:

        inventory_item.quantity -= 1

        inventory_item.save(
            update_fields=[
                "quantity",
            ]
        )


    messages.success(
        request,
        (
            f"{item.name}を使用しました。"
            "戦闘クールタイムが20秒になります。"
        ),
    )

    return redirect(
        "inventory:inventory"
    )