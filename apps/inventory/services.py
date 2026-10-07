from django.db import transaction

from .models import OwnedEquipment


@transaction.atomic
def equip_item(
    character,
    owned_equipment,
):
    """
    所持装備を装着する。

    同じ部位には1つしか装備できないため、
    すでに同部位の装備があれば先に外す。
    """

    # 他人の装備は装着できない
    if (
        owned_equipment.character_id
        != character.id
    ):
        raise ValueError(
            "この装備は所持していません。"
        )

    slot = (
        owned_equipment
        .equipment
        .slot
    )

    # ========================================
    # 同じ部位の装備を解除
    # ========================================

    same_slot_equipments = (
        OwnedEquipment.objects
        .filter(
            character=character,
            is_equipped=True,
            equipment__slot=slot,
        )
        .exclude(
            id=owned_equipment.id,
        )
    )

    same_slot_equipments.update(
        is_equipped=False,
    )

    # ========================================
    # 指定装備を装着
    # ========================================

    owned_equipment.is_equipped = True

    owned_equipment.save(
        update_fields=[
            "is_equipped",
            "updated_at",
        ]
    )

    return owned_equipment


@transaction.atomic
def unequip_item(
    character,
    owned_equipment,
):
    """
    装備を外す。
    """

    if (
        owned_equipment.character_id
        != character.id
    ):
        raise ValueError(
            "この装備は所持していません。"
        )

    owned_equipment.is_equipped = False

    owned_equipment.save(
        update_fields=[
            "is_equipped",
            "updated_at",
        ]
    )

    return owned_equipment