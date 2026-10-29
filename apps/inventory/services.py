
from django.db import transaction

from .models import OwnedEquipment
import random


# ========================================
# 装備強化バランス
# ========================================
# 基礎戦闘力11を基準とした強化テーブル
# +0 ～ +11
ENHANCEMENT_POWER_TABLE = [
    11, 23, 43, 76, 132, 231,
    412, 757, 1413, 2647, 5240, 9588,
]

# ランク別の強化係数
# 10 = 100%
RANK_ENHANCEMENT_RATE = {
    "F": 10,
    "E": 9,
    "D": 8,
    "C": 7,
    "B": 6,
    "A": 5,
    "S": 4,
}


def calculate_equipment_battle_power(
    base_battle_power,
    rank,
    enhancement_level,
):
    """
    装備の基礎戦闘力・ランク・強化値から
    強化後の装備戦闘力を計算する。

    現在の対応範囲:
        +0 ～ +11

    ステータスへの反映は
    OwnedEquipment.get_stat_bonus() で行う。
    """

    if not 0 <= enhancement_level < len(
        ENHANCEMENT_POWER_TABLE
    ):
        raise ValueError(
            "未対応の装備強化値です。"
        )

    if rank not in RANK_ENHANCEMENT_RATE:
        raise ValueError(
            "未対応の装備ランクです。"
        )

    reference_power = (
        ENHANCEMENT_POWER_TABLE[enhancement_level]
    )

    rate = RANK_ENHANCEMENT_RATE[rank]

    # ========================================
    # ランク別の強化計算
    #
    # 基準値11からの成長量に
    # ランク別係数を適用する。
    #
    # 整数計算で小数点以下を切り捨てる。
    # ========================================

    return (
        base_battle_power
        * (110 + (reference_power - 11) * rate)
        // 110
    )


# ========================================
# 装備する
# ========================================

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


# ========================================
# 装備を外す
# ========================================

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


# ========================================
# 合成条件の確認
# ========================================

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

    # 同じ所持装備を重複選択できない
    equipment_instance_ids = [
        equipment.id
        for equipment in equipments
    ]

    if len(set(equipment_instance_ids)) != 3:
        return False, "異なる所持装備を3つ選んでください。"

    # 装備中の装備は素材にできない
    if any(
        equipment.is_equipped
        for equipment in equipments
    ):
        return False, "装備中の装備は合成できません。"

    # 3つとも同じ種類の装備か確認
    equipment_ids = {
        equipment.equipment_id
        for equipment in equipments
    }

    if len(equipment_ids) != 1:
        return False, "同じ装備を3つ選んでください。"

    # 3つとも同じ強化値か確認
    enhancement_levels = {
        equipment.enhancement_level
        for equipment in equipments
    }

    if len(enhancement_levels) != 1:
        return False, "同じ+値の装備を3つ選んでください。"

    return True, ""


# ========================================
# 合成失敗率
# ========================================

def get_synthesis_failure_rate(
    rank,
    enhancement_level,
):
    """
    装備ランクと強化値から
    合成失敗率を返す。

    既存の合成確率を維持する。
    """

    # 強化値による基本失敗率
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


# ========================================
# 合成結果の抽選
# ========================================

def determine_synthesis_result(
    rank,
    enhancement_level,
):
    """
    装備合成の結果を抽選する。

    failure:
        失敗

    success:
        成功（+1）

    great_success:
        大成功（+2）

    super_success:
        超大成功（+3）
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


# ========================================
# 装備合成処理
# ========================================

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

    合成成功時の装備戦闘力には
    新しいランク別強化テーブルを適用する。

    未対応の強化値になった場合、
    素材とQを消費する前に中断する。
    """

    # ========================================
    # 合成条件の確認
    # ========================================

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

    # ========================================
    # 合成料金の確認
    # ========================================

    synthesis_cost = (
        character.get_synthesis_cost()
    )

    if character.gold < synthesis_cost:
        raise ValueError(
            "合成に必要なQが不足しています。"
        )

    # ========================================
    # 合成元の装備情報
    # ========================================

    source_equipment = equipments[0]

    equipment_master = (
        source_equipment.equipment
    )

    current_level = (
        source_equipment.enhancement_level
    )

    rank = equipment_master.rank

    # ========================================
    # 強化値の対応範囲を確認
    # ========================================

    max_level = (
        len(ENHANCEMENT_POWER_TABLE) - 1
    )

    if current_level >= max_level:
        raise ValueError(
            "現在の強化仕様では"
            f"+{max_level}以上の装備を"
            "合成できません。"
        )

    # ========================================
    # 合成結果を抽選
    # ========================================

    result = determine_synthesis_result(
        rank,
        current_level,
    )

    enhancement_increase = {
        "success": 1,
        "great_success": 2,
        "super_success": 3,
    }

    new_level = None
    new_battle_power = None

    # ========================================
    # 合成成功時の強化値を計算
    # ========================================

    if result != "failure":

        new_level = (
            current_level
            + enhancement_increase[result]
        )

        # +12以降はまだ未対応
        # Qや素材を消費する前に検証する
        new_battle_power = (
            calculate_equipment_battle_power(
                equipment_master.base_battle_power,
                rank,
                new_level,
            )
        )

    # ========================================
    # 必要Qを消費
    # ========================================

    if synthesis_cost > 0:

        character.gold -= synthesis_cost

        character.save(
            update_fields=[
                "gold",
            ]
        )

    # ========================================
    # 素材3つを消費
    # ========================================

    equipment_ids = [
        equipment.id
        for equipment in equipments
    ]

    OwnedEquipment.objects.filter(
        id__in=equipment_ids
    ).delete()

    # ========================================
    # 合成回数を記録
    # ========================================

    character.record_synthesis_attempt()

    # ========================================
    # 合成失敗
    # ========================================

    if result == "failure":
        return {
            "result": result,
            "equipment": None,
        }

    # ========================================
    # 合成成功・新しい装備を作成
    # ========================================

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
