from django.db import transaction

from apps.battle.models import (
    ArenaFloor,
    ArenaState,
)


@transaction.atomic
def claim_vacant_arena_floor(character):
    """
    現在階の空席を獲得する。

    戦闘は行わず、HP/MPを全回復する。

    戻り値:
        claimed        空席獲得
        occupied       他プレイヤーがマスター
        already_master 自分がマスター
    """

    # 現在階を確認
    state = ArenaState.objects.get(
        character=character,
    )

    # 同時獲得を防ぐため階層をロック
    floor = (
        ArenaFloor.objects
        .select_for_update()
        .get(floor=state.floor_id)
    )

    # 最新の状態をロックして取得
    state = (
        ArenaState.objects
        .select_for_update()
        .get(pk=state.pk)
    )

    # ロック待ちの間に移動していた場合
    if state.floor_id != floor.floor:
        raise ValueError(
            "闘技場の階層が変更されました。再試行してください。"
        )

    # 既にマスターがいる場合
    if floor.master_id is not None:

        if floor.master_id == character.pk:
            return "already_master"

        return "occupied"

    # 他の階のマスターとの重複を防ぐ
    if ArenaFloor.objects.filter(
        master=character,
    ).exists():
        raise ValueError(
            "既に別の階のマスターです。"
        )

    # 空席を獲得
    floor.master = character
    floor.save(
        update_fields=["master"]
    )

    # Arena専用HP/MPを全回復
    state.current_hp = character.max_hp
    state.current_mp = character.max_mp

    state.save(
        update_fields=[
            "current_hp",
            "current_mp",
        ]
    )

    return "claimed"