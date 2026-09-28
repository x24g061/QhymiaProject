import random


# ============================================================
# レベルアップに必要なEXP
# ============================================================

EXP_PER_LEVEL = 100


# ============================================================
# 職業ごとの成長ウェイト
# ============================================================
#
# 数字が大きい能力ほど
# レベルアップ時に選ばれやすくなる。
#
# 1レベルにつき3回抽選。
# 同じ能力が複数回選ばれることもある。
# ============================================================

JOB_GROWTH_WEIGHTS = {
    "grappler": {
        "hp": 2,
        "mp": 1,
        "strength": 3,
        "intelligence": 1,
        "dexterity": 2,
        "agility": 2,
        "vitality": 2,
        "luck": 1,
    },

    "warrior": {
        "hp": 3,
        "mp": 1,
        "strength": 3,
        "intelligence": 1,
        "dexterity": 1,
        "agility": 1,
        "vitality": 3,
        "luck": 1,
    },

    "hunter": {
        "hp": 1,
        "mp": 2,
        "strength": 2,
        "intelligence": 1,
        "dexterity": 3,
        "agility": 2,
        "vitality": 1,
        "luck": 2,
    },

    "wizard": {
        "hp": 1,
        "mp": 3,
        "strength": 1,
        "intelligence": 4,
        "dexterity": 1,
        "agility": 1,
        "vitality": 1,
        "luck": 1,
    },

    "priest": {
        "hp": 1,
        "mp": 3,
        "strength": 1,
        "intelligence": 3,
        "dexterity": 1,
        "agility": 2,
        "vitality": 2,
        "luck": 2,
    },

    "wanderer": {
        "hp": 2,
        "mp": 1,
        "strength": 2,
        "intelligence": 1,
        "dexterity": 2,
        "agility": 2,
        "vitality": 1,
        "luck": 3,
    },

    "assassin": {
        "hp": 1,
        "mp": 2,
        "strength": 1,
        "intelligence": 1,
        "dexterity": 3,
        "agility": 3,
        "vitality": 2,
        "luck": 1,
    },
}


# ============================================================
# 種族ごとの成長ウェイト
# ============================================================

RACE_GROWTH_WEIGHTS = {
    "human": {
        "hp": 2,
        "mp": 2,
        "strength": 2,
        "intelligence": 1,
        "dexterity": 2,
        "agility": 2,
        "vitality": 1,
        "luck": 3,
    },

    "elf": {
        "hp": 2,
        "mp": 2,
        "strength": 1,
        "intelligence": 3,
        "dexterity": 2,
        "agility": 3,
        "vitality": 1,
        "luck": 1,
    },

    "dwarf": {
        "hp": 3,
        "mp": 1,
        "strength": 2,
        "intelligence": 2,
        "dexterity": 2,
        "agility": 1,
        "vitality": 3,
        "luck": 1,
    },

    "dragonia": {
        "hp": 3,
        "mp": 1,
        "strength": 3,
        "intelligence": 2,
        "dexterity": 1,
        "agility": 2,
        "vitality": 3,
        "luck": 1,
    },

    "witch": {
        "hp": 1,
        "mp": 3,
        "strength": 1,
        "intelligence": 4,
        "dexterity": 3,
        "agility": 1,
        "vitality": 1,
        "luck": 1,
    },

    "fairy": {
        "hp": 1,
        "mp": 2,
        "strength": 1,
        "intelligence": 2,
        "dexterity": 4,
        "agility": 2,
        "vitality": 1,
        "luck": 2,
    },

    "demonia": {
        "hp": 2,
        "mp": 2,
        "strength": 3,
        "intelligence": 3,
        "dexterity": 1,
        "agility": 2,
        "vitality": 1,
        "luck": 1,
    },
}


# ============================================================
# 属性成長
# ============================================================

ATTRIBUTE_DISPLAY_NAMES = {
    "fire": "炎",
    "water": "水",
    "grass": "草",
    "rock": "岩",
    "light": "光",
    "dark": "闇",
}


def get_attribute_growth_weights(character):
    """
    キャラクターごとの
    属性成長ウェイトを取得する。

    初期値は全属性1。

    専用アイテムなどで
    各ウェイトを増加させることで、
    その属性が成長しやすくなる。
    """

    return {
        "fire": character.fire_growth_weight,
        "water": character.water_growth_weight,
        "grass": character.grass_growth_weight,
        "rock": character.rock_growth_weight,
        "light": character.light_growth_weight,
        "dark": character.dark_growth_weight,
    }


def apply_attribute_growth(
    character,
    attribute_name,
):
    """
    選ばれた属性を+1する。
    """

    current_value = getattr(
        character,
        attribute_name,
    )

    setattr(
        character,
        attribute_name,
        current_value + 1,
    )

    display_name = ATTRIBUTE_DISPLAY_NAMES[
        attribute_name
    ]

    return f"{display_name} +1"


def roll_attribute_growth(character):
    """
    1レベル分の属性成長。

    6属性から重み付きで3回抽選する。

    random.choices()なので
    同じ属性が複数回選ばれることもある。
    """

    growth_weights = (
        get_attribute_growth_weights(
            character
        )
    )

    attribute_names = list(
        growth_weights.keys()
    )

    weights = list(
        growth_weights.values()
    )

    # 3回・重複ありで抽選
    selected_attributes = random.choices(
        population=attribute_names,
        weights=weights,
        k=3,
    )

    growth_logs = []

    for attribute_name in selected_attributes:

        result = apply_attribute_growth(
            character,
            attribute_name,
        )

        growth_logs.append(
            result
        )

    return growth_logs


# ============================================================
# 職業 + 種族の成長ウェイトを作る
# ============================================================

def get_growth_weights(character):
    """
    キャラクターの

    職業ウェイト
    +
    種族ウェイト

    を合算して返す。
    """

    job_weights = JOB_GROWTH_WEIGHTS[
        character.job
    ]

    race_weights = RACE_GROWTH_WEIGHTS[
        character.race
    ]

    combined_weights = {}

    for stat_name in job_weights:
        combined_weights[stat_name] = (
            job_weights[stat_name]
            + race_weights[stat_name]
        )

    return combined_weights


# ============================================================
# 1回分の能力成長
# ============================================================

def apply_stat_growth(character, stat_name):
    """
    抽選された能力を1回成長させる。

    HP:
        最大HP +5
        現在HP +5

    MP:
        最大MP +3

    その他:
        +1
    """

    # ===== HP =====

    if stat_name == "hp":

        character.max_hp += 5
        character.current_hp += 5

        return "HP +5"

    # ===== MP =====

    if stat_name == "mp":

        character.max_mp += 3

        return "MP +3"

    # ===== その他の能力 =====

    current_value = getattr(
        character,
        stat_name,
    )

    setattr(
        character,
        stat_name,
        current_value + 1,
    )

    # ログ表示用
    display_names = {
        "strength": "STR",
        "intelligence": "INT",
        "dexterity": "DEX",
        "agility": "AGI",
        "vitality": "VIT",
        "luck": "LUK",
    }

    return (
        f"{display_names[stat_name]} +1"
    )


# ============================================================
# 1レベル分の成長
# ============================================================

def level_up_once(character):
    """
    1レベルアップさせる。

    1レベルにつき、

    ・基礎能力を3回抽選
    ・属性を3回抽選

    どちらも重複抽選あり。
    """

    # ===== レベル +1 =====

    character.level += 1


    # ========================================================
    # 基礎能力成長
    # ========================================================

    growth_weights = get_growth_weights(
        character
    )

    stat_names = list(
        growth_weights.keys()
    )

    weights = list(
        growth_weights.values()
    )

    # 3回・重複あり
    selected_stats = random.choices(
        population=stat_names,
        weights=weights,
        k=3,
    )

    stat_growth_logs = []

    for stat_name in selected_stats:

        result = apply_stat_growth(
            character,
            stat_name,
        )

        stat_growth_logs.append(
            result
        )


    # ========================================================
    # 属性成長
    # ========================================================

    attribute_growth_logs = (
        roll_attribute_growth(
            character
        )
    )


    # ========================================================
    # 今回のレベルアップ結果
    # ========================================================

    return {
        "stat_growths": stat_growth_logs,
        "attribute_growths": attribute_growth_logs,
    }


    # ========================================================
    # 3回抽選
    # ========================================================
    #
    # choicesなので重複あり。
    #
    # 例:
    # STR
    # STR
    # HP
    #
    # のような結果も発生する。
    # ========================================================

    selected_stats = random.choices(
        population=stat_names,
        weights=weights,
        k=3,
    )

    growth_logs = []

    for stat_name in selected_stats:

        result = apply_stat_growth(
            character,
            stat_name,
        )

        growth_logs.append(
            result
        )

    return growth_logs


# ============================================================
# 探索終了時のEXP処理
# ============================================================

def apply_exploration_exp(
    character,
    gained_exp,
):
    """
    探索終了時にEXPをまとめて加算し、
    必要ならレベルアップする。

    必要EXPは常に100。

    EXPが200以上あれば
    一度に複数レベル上がる。
    """

    character.exp += gained_exp

    level_up_results = []

    # ========================================================
    # EXP100以上ある限り繰り返す
    # ========================================================

    while character.exp >= EXP_PER_LEVEL:

        # EXPを100消費
        character.exp -= EXP_PER_LEVEL

        # 1レベル成長
        growth_result = level_up_once(
            character
        )

        level_up_results.append({
            "level": character.level,

            # 基礎能力3回
            "growths": (
                growth_result[
                    "stat_growths"
                ]
            ),

            # 属性3回
            "attribute_growths": (
                growth_result[
                    "attribute_growths"
                ]
            ),
        })

    # ========================================================
    # 探索から帰還したので
    # HP / MPを全回復
    # ========================================================

    character.current_hp = (
        character.max_hp
    )

    character.current_mp = (
        character.max_mp
    )

    # DBへ保存
    character.save()

    return {
        "gained_exp": gained_exp,
        "level_up_count": len(
            level_up_results
        ),
        "level_ups": level_up_results,
        "current_level": character.level,
        "remaining_exp": character.exp,
    }

#将来の属性ウェイト増加用
def increase_attribute_growth_weight(
    character,
    attribute_name,
    amount=1,
):
    """
    属性成長ウェイトを増加させる。

    将来、
    属性成長アイテムを使用したときに使う。

    例:
    炎ウェイト 1
    ↓
    アイテム使用
    ↓
    炎ウェイト 2
    """

    field_name = (
        f"{attribute_name}_growth_weight"
    )

    # 存在しない属性名を防止
    if attribute_name not in ATTRIBUTE_DISPLAY_NAMES:
        raise ValueError(
            "存在しない属性です。"
        )

    current_weight = getattr(
        character,
        field_name,
    )

    setattr(
        character,
        field_name,
        current_weight + amount,
    )

    character.save(
        update_fields=[
            field_name,
        ]
    )

    return getattr(
        character,
        field_name,
    )