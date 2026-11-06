
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
    装備戦闘力を計算する。

    +0～+11：既存の強化テーブル
    +12以降：1段階ごとに1.20倍

    ランク別の強化係数も適用する。
    """

    if enhancement_level < 0:
        raise ValueError(
            "強化値は0以上にしてください。"
        )

    if rank not in RANK_ENHANCEMENT_RATE:
        raise ValueError(
            "未対応の装備ランクです。"
        )

    # +0～+11は既存テーブルを使用
    if enhancement_level < len(
        ENHANCEMENT_POWER_TABLE
    ):
        reference_power = (
            ENHANCEMENT_POWER_TABLE[enhancement_level]
        )

    else:
        # +11の基準戦闘力から開始
        reference_power = (
            ENHANCEMENT_POWER_TABLE[-1]
        )

        # +12以降は1段階につき1.20倍
        for _ in range(
            11,
            enhancement_level,
        ):
            reference_power = (
                reference_power * 6 // 5
            )

    rate = RANK_ENHANCEMENT_RATE[rank]

    # ランク別補正を適用
    return (
        base_battle_power
        * (110 + (reference_power - 11) * rate)
        // 110
    )

# ========================================
# 特殊能力の抽選
# ========================================

SPECIAL_EFFECT_CHANCE = 1 / 3  # 約33.3%

def determine_special_effect(
    equipments,
    new_level,
):
    """
    合成後の特殊能力を決定する。

    ・既存の特殊能力は引き継ぐ
    ・複数種類ある場合は1種類だけ選ぶ
    ・未付与なら+6以上で0.1%抽選
    """

    existing_effects = sorted({
        equipment.special_effect
        for equipment in equipments
        if equipment.special_effect
    })

    if existing_effects:
        return random.choice(existing_effects)

    if new_level < 6:
        return ""

    if random.random() >= SPECIAL_EFFECT_CHANCE:
        return ""

    return random.choice(
        list(OwnedEquipment.SpecialEffect.values)
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
    special_effect = ""

    # ========================================
    # 合成成功時の強化値を計算
    # ========================================

    if result != "failure":

        new_level = (
            current_level
            + enhancement_increase[result]
        )

        # Qや素材を消費する前に検証する
        new_battle_power = (
            calculate_equipment_battle_power(
                equipment_master.base_battle_power,
                rank,
                new_level,
            )
        )
            # 特殊能力の引き継ぎ・抽選
        special_effect = determine_special_effect(
            equipments,
            new_level,
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
            special_effect=special_effect,
            is_equipped=False,
        )
    )

    return {
        "result": result,
        "equipment": new_equipment,
    }
# ========================================
# 戦闘用：装備特殊能力の倍率
# ========================================

SPECIAL_EFFECT_MULTIPLIERS = {
    "physical_damage": 1.01,
    "magic_damage": 1.01,
    "damage_reduction": 0.99,
}


def get_equipment_special_multiplier(
    character,
    effect_code,
):
    """
    装備中アイテムの特殊能力による
    ダメージ倍率を取得する。

    所持しているだけの装備は対象外。
    同じ能力が複数ある場合は効果を重ねる。
    """

    if effect_code not in SPECIAL_EFFECT_MULTIPLIERS:
        return 1.0

    effect_count = OwnedEquipment.objects.filter(
        character=character,
        is_equipped=True,
        special_effect=effect_code,
    ).count()

    return SPECIAL_EFFECT_MULTIPLIERS[effect_code] ** effect_count