from .models import FloorProgress


# ============================================================
# 探索階層
# ============================================================

MAX_EXPLORATION_FLOOR = 12


def get_max_unlocked_floor(character):
    """
    キャラクターが現在探索できる
    最大階層を返す。

    1階は最初から解放。

    1階ボス撃破
    → 2階解放

    2階ボス撃破
    → 3階解放

    という形で順番に解放する。
    """

    # 1階は最初から探索可能
    max_unlocked_floor = 1

    progresses = {
        progress.floor: progress
        for progress
        in FloorProgress.objects.filter(
            character=character,
            floor__gte=1,
            floor__lt=MAX_EXPLORATION_FLOOR,
        )
    }

    for floor in range(
        1,
        MAX_EXPLORATION_FLOOR,
    ):

        progress = progresses.get(
            floor
        )

        # その階の進行データがない
        # またはボス未撃破なら
        # そこから先は未解放
        if (
            progress is None
            or not progress.boss_defeated
        ):
            break

        max_unlocked_floor = (
            floor + 1
        )

    return max_unlocked_floor


def is_floor_unlocked(
    character,
    floor,
):
    """
    指定された階層が
    探索可能か判定する。
    """

    if not (
        1
        <= floor
        <= MAX_EXPLORATION_FLOOR
    ):
        return False

    return (
        floor
        <= get_max_unlocked_floor(
            character
        )
    )