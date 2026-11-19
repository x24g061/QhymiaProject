from django.utils import timezone


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
                "expires_at": expires_at,
            }
        )


    return active_boosts