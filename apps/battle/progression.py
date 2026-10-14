from .models import FloorProgress
import random


# ============================================================
# ボス出現設定
# ============================================================

BOSS_ENCOUNTER_RATE = 0.005

BOSS_GUARANTEE_COUNT = 200


def should_encounter_boss(
    floor_progress,
):
    """
    ボスと遭遇するか判定する。

    条件:
    ・すでにボス撃破済みなら出現しない
    ・探索200回以上で確定出現
    ・それ未満でも0.5%で出現
    """

    # 撃破済みボスは再出現しない
    if floor_progress.boss_defeated:
        return False

    # 200回到達で確定
    if (
        floor_progress.exploration_count
        >= BOSS_GUARANTEE_COUNT
    ):
        return True

    # 通常時は0.5%
    return (
        random.random()
        < BOSS_ENCOUNTER_RATE
    )


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