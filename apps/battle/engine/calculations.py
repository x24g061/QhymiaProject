import random


# ============================================================
# 属性倍率
# ============================================================

ATTRIBUTE_MULTIPLIERS = {
    "fire": {
        "fire": 1.0,
        "water": 0.8,
        "grass": 1.2,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "water": {
        "fire": 1.2,
        "water": 1.0,
        "grass": 0.8,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "grass": {
        "fire": 0.8,
        "water": 1.2,
        "grass": 1.0,
        "rock": 1.2,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "rock": {
        "fire": 1.2,
        "water": 1.0,
        "grass": 0.8,
        "rock": 0.8,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "light": {
        "fire": 1.0,
        "water": 1.0,
        "grass": 1.0,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.2,
        "neutral": 1.0,
    },
    "dark": {
        "fire": 1.0,
        "water": 1.0,
        "grass": 1.0,
        "rock": 1.0,
        "light": 1.2,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "neutral": {
        "fire": 1.0,
        "water": 1.0,
        "grass": 1.0,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
}


# ============================================================
# 命中率
# ============================================================

def calculate_hit_rate(
    attacker_dex,
    defender_agi,
):
    denominator = (
        attacker_dex
        + defender_agi
    )

    if denominator <= 0:
        return 60

    hit_rate = (
        60
        + 39
        * attacker_dex
        / denominator
    )

    return min(
        99,
        max(
            0,
            hit_rate,
        ),
    )


# ============================================================
# 通常物理ダメージ
# ============================================================

def calculate_physical_damage(
    strength,
    defender_vit,
):
    base_damage = (
        strength
        * 1.0
    )

    damage = (
        base_damage
        - defender_vit
        * 0.5
    )

    return max(
        1,
        int(damage),
    )


# ============================================================
# 確率判定
# ============================================================

def roll_percent(rate):
    roll = random.uniform(
        0,
        100,
    )

    return roll < rate