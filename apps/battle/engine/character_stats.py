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


# ============================================================
# スタミナによる能力補正
# ============================================================

def get_stamina_stat_multiplier(
    current_stamina,
    max_stamina,
):
    """
    現在STから疲労による能力補正を返す。

    100% → 1.00倍
     50% → 0.75倍
      0% → 0.50倍
    """

    if max_stamina <= 0:
        return 0.50

    stamina_ratio = (
        current_stamina
        / max_stamina
    )

    stamina_ratio = min(
        1.0,
        max(
            0.0,
            stamina_ratio,
        ),
    )

    return (
        0.50
        + stamina_ratio * 0.50
    )


# ============================================================
# 戦闘中の有効ステータス
# ============================================================

def get_character_combat_stat(
    character,
    stat_name,
    *,
    current_hp=None,
    max_hp=None,
    current_stamina=None,
    max_stamina=None,
    elf_agility_bonus=0.0,
    fighting_spirit_turns=0,
    walker_turns=0,
    freedom_active=False,
    freedom_bonus=0.0,
    hunter_eye_turns=0,
    hide_turns=0,
    healing_shield_turns=0,
):
    """
    探索・闘技場共通の
    戦闘中有効ステータスを返す。

    Character本体の能力値に加えて、

    ・装備
    ・職業
    ・種族
    ・戦闘中バフ
    ・ST疲労

    を反映する。
    """

    value = get_character_base_combat_stat(
        character,
        stat_name,
    )

    # ========================================
    # 種族パッシブ
    # ========================================

    # ドラゴニア「竜血覚醒」
    if (
        character.race == "dragonia"
        and current_hp is not None
        and max_hp is not None
        and current_hp <= max_hp * 0.50
        and stat_name in (
            "strength",
            "vitality",
        )
    ):
        value *= 1.10

    # エルフ「森の加護」
    if (
        character.race == "elf"
        and stat_name == "agility"
    ):
        value *= (
            1.0
            + elf_agility_bonus
        )

    # ========================================
    # 戦闘中バフ
    # ========================================

    # 闘魂
    if (
        fighting_spirit_turns > 0
        and stat_name == "strength"
    ):
        value *= 1.10

    # 歩行者
    if walker_turns > 0:

        if stat_name == "agility":
            value *= 0.70

        elif stat_name == "strength":
            value *= 1.20

        elif stat_name == "dexterity":
            value *= 1.05

    # 行動原理：自由
    if freedom_active:
        value *= (
            1.0
            + freedom_bonus
        )

    # ハンターアイ
    if hunter_eye_turns > 0:

        if stat_name == "dexterity":
            value *= 1.10

        elif stat_name == "luck":
            value *= 1.05

    # ハイド
    if (
        hide_turns > 0
        and stat_name == "agility"
    ):
        value *= 0.90

    # ヒーリングシールド
    if (
        healing_shield_turns > 0
        and stat_name == "vitality"
    ):
        value *= 1.20

    # ========================================
    # ST疲労
    # ========================================

    if (
        stat_name in (
            "dexterity",
            "agility",
            "vitality",
            "luck",
        )
        and current_stamina is not None
        and max_stamina is not None
    ):
        value *= get_stamina_stat_multiplier(
            current_stamina,
            max_stamina,
        )

    return value