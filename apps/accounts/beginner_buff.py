from datetime import timedelta

from django.utils import timezone


# ビギナーバフの基本設定
BEGINNER_BUFF_DURATION = timedelta(hours=72)
BEGINNER_EXP_MULTIPLIER = 2
BEGINNER_GOLD_MULTIPLIER = 2
BEGINNER_COOLDOWN_MULTIPLIER = 0.5
BEGINNER_DROP_MULTIPLIER = 2


def get_beginner_buff_expires_at(user):
    """ビギナーバフの終了日時を取得する。"""
    return user.date_joined + BEGINNER_BUFF_DURATION


def is_beginner_buff_active(user, now=None):
    """登録から72時間以内か判定する。"""
    if now is None:
        now = timezone.now()

    return (
        user.date_joined
        <= now
        < get_beginner_buff_expires_at(user)
    )


def get_beginner_buff_remaining(user, now=None):
    """ビギナーバフの残り秒数を取得する。"""
    if now is None:
        now = timezone.now()

    remaining = (
        get_beginner_buff_expires_at(user) - now
    ).total_seconds()

    return max(0, int(remaining))
