# ============================================================
# キャラクター共通ステータス計算
# ============================================================
#
# 探索・闘技場の両方で使用する、
# Character由来の基本的な戦闘ステータスを計算する。
#
# 戦闘中に変化するバフ・デバフや
# STによる疲労補正などはここでは扱わない。
# ============================================================


JOB_STAT_MULTIPLIERS = {
    "grappler": {
        "strength": 1.10,
    },
    "warrior": {
        "vitality": 1.10,
    },
    "hunter": {
        "dexterity": 1.10,
    },
    "wizard": {
        "intelligence": 1.10,
    },
    "wanderer": {
        "luck": 1.10,
    },
    "assassin": {
        "agility": 1.10,
    },
}


def get_equipment_stat_bonus(
    character,
    stat_name,
):
    """
    装備中アイテムによる
    ステータス補正値の合計を返す。
    """

    equipped_items = (
        character
        .owned_equipments
        .filter(
            is_equipped=True,
        )
        .select_related(
            "equipment",
        )
    )

    return sum(
        owned.get_stat_bonus(
            stat_name
        )
        for owned in equipped_items
    )


def get_character_base_combat_stat(
    character,
    stat_name,
):
    """
    Characterの基本戦闘ステータスを返す。

    対象:
    ・素のステータス
    ・装備補正
    ・職業補正
    ・常時発動型の種族補正

    戦闘中に変化する補正は含めない。
    """

    value = getattr(
        character,
        stat_name,
    )

    # ========================================
    # 装備補正
    # ========================================

    value += get_equipment_stat_bonus(
        character,
        stat_name,
    )

    # ========================================
    # 職業補正
    # ========================================

    job_modifiers = (
        JOB_STAT_MULTIPLIERS.get(
            character.job,
            {},
        )
    )

    value *= job_modifiers.get(
        stat_name,
        1.0,
    )

    # ========================================
    # 常時発動型の種族補正
    # ========================================

    # ヒューマン「努力家」
    if (
        character.race == "human"
        and stat_name == "luck"
    ):
        value *= 1.15

    # ウィッチ「魔力循環」
    if (
        character.race == "witch"
        and stat_name == "intelligence"
    ):
        value *= 1.05

    return value
    