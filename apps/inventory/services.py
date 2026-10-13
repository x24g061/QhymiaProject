from django.db import transaction

from .models import OwnedEquipment
import random

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

def validate_synthesis_equipments(
    equipments,
):
    """
    装備合成に使う3つの装備が
    合成条件を満たしているか確認する。
    """

    # 合成には3つちょうど必要
    if len(equipments) != 3:
        return False, "合成には装備が3つ必要です。"

    # 装備中の装備は素材にできない
    if any(
        equipment.is_equipped
        for equipment in equipments
    ):
        return False, "装備中の装備は合成できません。"

    # 3つとも同じ装備か確認
    equipment_ids = {
        equipment.equipment_id
        for equipment in equipments
    }

    if len(equipment_ids) != 1:
        return False, "同じ装備を3つ選んでください。"

    # 3つとも同じ+値か確認
    enhancement_levels = {
        equipment.enhancement_level
        for equipment in equipments
    }

    if len(enhancement_levels) != 1:
        return False, "同じ+値の装備を3つ選んでください。"

    return True, ""

def get_synthesis_failure_rate(
    rank,
    enhancement_level,
):
    """
    装備ランクと+値から
    合成失敗率を返す。
    """

    # +値による基本失敗率
    if enhancement_level <= 2:
        base_failure_rate = 5
    elif enhancement_level <= 5:
        base_failure_rate = 15
    elif enhancement_level <= 9:
        base_failure_rate = 30
    elif enhancement_level <= 14:
        base_failure_rate = 45
    else:
        base_failure_rate = 60

    # 装備ランクによる失敗率補正
    rank_bonus = {
        "F": 0,
        "E": 3,
        "D": 6,
        "C": 9,
        "B": 12,
        "A": 15,
        "S": 20,
    }

    failure_rate = (
        base_failure_rate
        + rank_bonus.get(rank, 0)
    )

    return failure_rate
def determine_synthesis_result(
    rank,
    enhancement_level,
):
    """
    装備合成の結果を抽選する。

    結果:
    ・failure       失敗
    ・success       成功
    ・great_success 大成功
    ・super_success 超大成功
    """

    failure_rate = get_synthesis_failure_rate(
        rank,
        enhancement_level,
    )

    super_success_rate = 5
    great_success_rate = 12

    success_rate = (
        100
        - failure_rate
        - super_success_rate
        - great_success_rate
    )

    roll = random.uniform(
        0,
        100,
    )

    if roll < failure_rate:
        return "failure"

    if roll < (
        failure_rate
        + success_rate
    ):
        return "success"

    if roll < (
        failure_rate
        + success_rate
        + great_success_rate
    ):
        return "great_success"

    return "super_success"

@transaction.atomic
def synthesize_equipments(
    character,
    equipments,
):
    """
    3つの同一装備を合成する。

    成功:
        +1

    大成功:
        +2

    超大成功:
        +3

    失敗:
        素材3つ消失
    """

    is_valid, message = (
        validate_synthesis_equipments(
            equipments
        )
    )

    if not is_valid:
        raise ValueError(message)

    # 他人の装備が混ざっていないか確認
    if any(
        equipment.character_id
        != character.id
        for equipment in equipments
    ):
        raise ValueError(
            "この装備は所持していません。"
        )

    synthesis_cost = (
        character.get_synthesis_cost()
    )

    # 4回目以降でQ不足なら合成不可
    if character.gold < synthesis_cost:
        raise ValueError(
            "合成に必要なQが不足しています。"
        )

    source_equipment = equipments[0]

    equipment_master = (
        source_equipment.equipment
    )

    current_level = (
        source_equipment.enhancement_level
    )

    rank = equipment_master.rank

    result = determine_synthesis_result(
        rank,
        current_level,
    )

    # 必要Qを消費
    if synthesis_cost > 0:
        character.gold -= synthesis_cost

        character.save(
            update_fields=[
                "gold",
            ]
        )

    # 素材3つを消費
    equipment_ids = [
        equipment.id
        for equipment in equipments
    ]

    OwnedEquipment.objects.filter(
        id__in=equipment_ids
    ).delete()

    # 合成回数を記録
    character.record_synthesis_attempt()

    # 失敗なら装備は生成しない
    if result == "failure":
        return {
            "result": result,
            "equipment": None,
        }

    enhancement_increase = {
        "success": 1,
        "great_success": 2,
        "super_success": 3,
    }

    new_level = (
        current_level
        + enhancement_increase[result]
    )

    new_battle_power = int(
        equipment_master.base_battle_power
        * (1.5 ** new_level)
    )

    new_equipment = (
        OwnedEquipment.objects.create(
            character=character,
            equipment=equipment_master,
            enhancement_level=new_level,
            battle_power=new_battle_power,
            is_equipped=False,
        )
    )

    return {
        "result": result,
        "equipment": new_equipment,
    }