import random

from django.db import transaction

from apps.inventory.models import (
    Equipment,
    InventoryItem,
    Item,
    OwnedEquipment,
)

from .models import FloorDropItem


# ============================================================
# 探索ドロップ率
# ============================================================

# 通常探索では1%
EXPLORATION_DROP_RATE = 0.01


def grant_exploration_drop(
    character,
    floor,
    guaranteed=False,
):
    """
    探索勝利時のドロップ抽選。

    通常:
        1%でドロップ

    guaranteed=True:
        抽選を省略して必ずドロップ
        ※将来のボス用

    当選後:
        FloorDropItemのdrop_weightを使って
        その階層の候補から1つ選ぶ。
    """

    # ========================================================
    # この階層の候補取得
    # ========================================================

    candidates = list(
        FloorDropItem.objects
        .filter(
            floor=floor,
        )
        .select_related(
            "item",
        )
    )

    # 候補がなければ何も落ちない
    if not candidates:
        return None


    # ========================================================
    # 1%ドロップ判定
    # ========================================================

    if not guaranteed:

        if random.random() >= EXPLORATION_DROP_RATE:
            return None


    # ========================================================
    # 階層内の候補から重み付き抽選
    # ========================================================

    selected_drop = random.choices(
        candidates,
        weights=[
            max(
                1,
                drop.drop_weight,
            )
            for drop in candidates
        ],
        k=1,
    )[0]

    item = selected_drop.item


    # ========================================================
    # 装備品
    # ========================================================

    if item.category == Item.Category.EQUIPMENT:

        # Itemに対応するEquipmentを取得
        try:
            equipment = item.equipment_data

        except Equipment.DoesNotExist:
            # 装備カテゴリなのにEquipmentデータがない場合
            # 不正データなのでドロップしない
            return None

        with transaction.atomic():

            owned_equipment = (
                OwnedEquipment.objects.create(
                    character=character,
                    equipment=equipment,

                    # ドロップした瞬間は+0
                    enhancement_level=0,

                    # 初期戦闘力
                    battle_power=(
                        equipment.base_battle_power
                    ),

                    is_equipped=False,
                )
            )

        return {
            "kind": "equipment",
            "name": item.name,
            "rank": equipment.rank,
            "slot": (
                equipment.get_slot_display()
            ),
            "battle_power": (
                owned_equipment.battle_power
            ),
        }


    # ========================================================
    # 通常アイテム
    # ========================================================

    with transaction.atomic():

        inventory_item, created = (
            InventoryItem.objects.get_or_create(
                character=character,
                item=item,
                defaults={
                    "quantity": 1,
                },
            )
        )

        # すでに所持していたら+1
        if not created:

            inventory_item.quantity += 1

            inventory_item.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )

    return {
        "kind": "item",
        "name": item.name,
        "quantity": 1,
    }