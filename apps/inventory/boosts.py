from django.utils import timezone

from apps.accounts.beginner_buff import (
    is_beginner_buff_active,
    get_beginner_buff_expires_at,
    get_beginner_buff_remaining,
)


# ========================================
# ブースト定義
# ========================================

BOOST_DEFINITIONS = [
    {
        "key": "exploration_cooldown_reduction",
        "name": "探索CT短縮",
        "description": "探索クールタイムが20秒になります。",
        "expires_field": "exploration_cooldown_reduced_until",
        "icon": "⌛",
    },
]


# ========================================
# 現在有効なブースト取得
# ========================================

def get_active_boosts(character):

    now = timezone.now()

    active_boosts = []

    if is_beginner_buff_active(character.user, now):
        active_boosts.append({
            "key": "beginner_buff",
            "name": "ビギナーバフ",
            "description": (
                "獲得経験値2倍・探索CT50%短縮・"
                "装備ドロップ率2倍"
            ),
            "icon": "🔰",
            "expires_at": get_beginner_buff_expires_at(
                character.user
            ),
            "remaining_seconds": get_beginner_buff_remaining(
                character.user, now
            ),
        })


    for boost in BOOST_DEFINITIONS:

        expires_at = getattr(
            character,
            boost["expires_field"],
            None,
        )


        if not expires_at:
            continue


        if expires_at <= now:
            continue


        active_boosts.append(
            {
                **boost,
                "description": (
                    f"探索クールタイムが"
                    f"{character.get_exploration_cooldown_seconds()}秒になります。"
                    if boost["key"] == "exploration_cooldown_reduction"
                    else boost["description"]
                ),
                "expires_at": expires_at,
            }
        )


    return active_boosts