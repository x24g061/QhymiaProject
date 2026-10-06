from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from .models import (
    Equipment,
    InventoryItem,
    OwnedEquipment,
)
from .services import (
    equip_item,
    unequip_item,
)


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
        },
    )


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