import random

from django.db import transaction

from apps.accounts.beginner_buff import (
    is_beginner_buff_active,
    BEGINNER_DROP_MULTIPLIER,
)

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

# 通常探索では2.5%
EXPLORATION_DROP_RATE = 0.025


def grant_exploration_drop(
    character,
    floor,
    guaranteed=False,
    debug_drop_rate=None,
):
    """
    探索勝利時のドロップ抽選。

    通常:
        2.5%でドロップ

    ビギナーバフ:
        通常抽選に加えて装備品の追加抽選あり

    DEBUG MODE:
        debug_drop_rate に指定された
        0～100%の確率でドロップする。
        通常率・ビギナーバフより優先する。

    guaranteed=True:
        抽選を省略して必ずドロップ。

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
    # ドロップ判定
    # ========================================================

    equipment_bonus_only = False

    if not guaranteed:

        roll = random.random()

        # ====================================================
        # DEBUG MODE
        # ====================================================

        if debug_drop_rate is not None:

            debug_drop_rate = max(
                0,
                min(
                    100,
                    int(debug_drop_rate),
                ),
            )

            effective_drop_rate = (
                debug_drop_rate / 100
            )

            if roll >= effective_drop_rate:
                return None

        # ====================================================
        # 通常モード
        # ====================================================

        else:

            if roll >= EXPLORATION_DROP_RATE:

                if not is_beginner_buff_active(
                    character.user
                ):
                    return None

                boosted_rate = min(
                    1.0,
                    (
                        EXPLORATION_DROP_RATE
                        * BEGINNER_DROP_MULTIPLIER
                    ),
                )

                if roll >= boosted_rate:
                    return None

                equipment_bonus_only = True


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
    # ビギナーバフの追加抽選では装備品のみ対象
    # ========================================================

    if (
        equipment_bonus_only
        and item.category != Item.Category.EQUIPMENT
    ):
        return None


    # ========================================================
    # 装備品
    # ========================================================

    if item.category == Item.Category.EQUIPMENT:

        try:
            equipment = item.equipment_data

        except Equipment.DoesNotExist:
            return None

        with transaction.atomic():

            owned_equipment = (
                OwnedEquipment.objects.create(
                    character=character,
                    equipment=equipment,
                    enhancement_level=0,
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

# ============================================================
# 闘技場ドロップ
# ============================================================

ARENA_BASE_DROP_RATE = 0.025
ARENA_STREAK_BONUS_RATE = 0.0075
ARENA_MAX_DROP_RATE = 0.10

def grant_arena_drop(
    character,
    win_streak,
    guaranteed=False,
):
    """
    闘技場勝利時の素材ドロップ。

    基本2.5%。
    戦闘開始前の連勝数1回につき+0.75%。
    最大10%。

    guaranteed=True の場合は抽選を省略する。
    """

    # 釣り専用の魚は闘技場でドロップさせない
    fishing_items = [
        "コモンの魚",
        "レアの魚",
        "エピックの魚",
        "レジェンドの魚",
    ]

    candidates = list(
        Item.objects.filter(
            category=Item.Category.MATERIAL,
        ).exclude(
            name__in=fishing_items,
        )
    )

    # 素材アイテムが存在しない場合
    if not candidates:
        return None

    drop_rate = min(
        ARENA_BASE_DROP_RATE
        + (
            max(0, win_streak)
            * ARENA_STREAK_BONUS_RATE
        ),
        ARENA_MAX_DROP_RATE,
    )

    # ドロップ判定
    if not guaranteed:
        if random.random() >= drop_rate:
            return None

    item = random.choice(candidates)

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
        "drop_rate": drop_rate,
    }