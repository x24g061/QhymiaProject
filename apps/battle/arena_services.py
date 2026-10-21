from django.db import transaction

from apps.battle.arena_engine import ArenaBattleEngine
from apps.battle.models import (
    ArenaBattleHistory,
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


# ========================================================
# 闘技場PvP：マスターとの対戦・階層移動
# ========================================================

@transaction.atomic
def challenge_arena_master(challenger):
    """
    現在階のマスターに挑戦する。

    勝利：
        挑戦者がマスターになる。
        旧マスターは階層番号+1へ移動。
        両者HP/MP全回復。

    敗北・引き分け：
        挑戦者は階層番号+2へ移動。
        挑戦者HP/MP全回復。
        防衛者は残HP/MPを引き継ぐ。

    EXP、ドロップ、CTは後で実装する。
    """

    # 現在階を一旦取得
    initial_state = ArenaState.objects.get(
        character=challenger,
    )

    # 対象フロアをロック
    floor = (
        ArenaFloor.objects
        .select_for_update()
        .get(pk=initial_state.floor_id)
    )

    if floor.master_id is None:
        raise ValueError(
            "現在階は空席です。"
        )

    if floor.master_id == challenger.pk:
        raise ValueError(
            "自分自身には挑戦できません。"
        )

    defender = floor.master

    # 両者のArenaStateを一定の順番でロック
    states = {
        state.character_id: state
        for state in (
            ArenaState.objects
            .select_for_update()
            .filter(
                character_id__in=[
                    challenger.pk,
                    defender.pk,
                ],
            )
            .order_by("character_id")
        )
    }

    if (
        challenger.pk not in states
        or defender.pk not in states
    ):
        raise ValueError(
            "闘技場の状態が見つかりません。"
        )

    challenger_state = states[challenger.pk]
    defender_state = states[defender.pk]

    # ロック待ちの間に状態が変わっていないか確認
    if challenger_state.floor_id != floor.floor:
        raise ValueError(
            "挑戦者の階層が変更されました。"
        )

    if defender_state.floor_id != floor.floor:
        raise ValueError(
            "マスターの階層が一致しません。"
        )

    # 他の階のマスターからの挑戦は現段階では禁止
    if ArenaFloor.objects.filter(
        master_id=challenger.pk,
    ).exists():
        raise ValueError(
            "既に別の階のマスターです。"
        )

    # ========================================
    # PvP自動戦闘
    # ========================================

    engine = ArenaBattleEngine(
        challenger,
        defender,
        challenger_state,
        defender_state,
    )

    result = engine.run()
    winner = result["winner"]

    if winner not in {
        "challenger",
        "defender",
        "draw",
    }:
        raise ValueError(
            "不正な戦闘結果です。"
        )

    # ========================================
    # 戦闘直後のHP/MPを保持
    # ========================================

    battle_hp_mp = {
        "challenger_hp": result["challenger_hp"],
        "challenger_mp": result["challenger_mp"],
        "defender_hp": result["defender_hp"],
        "defender_mp": result["defender_mp"],
    }

    # ========================================
    # 挑戦者勝利
    # ========================================

    if winner == "challenger":

        floor.master = challenger
        floor.save(
            update_fields=["master"]
        )

        # 挑戦者は現在階のマスター
        challenger_state.current_hp = challenger.max_hp
        challenger_state.current_mp = challenger.max_mp

        # 旧マスターは1階層下へ
        defender_state.floor_id = min(
            100,
            floor.floor + 1,
        )

        defender_state.current_hp = defender.max_hp
        defender_state.current_mp = defender.max_mp

        history_result = ArenaBattleHistory.Result.WIN

    # ========================================
    # 挑戦者敗北・引き分け
    # ========================================

    else:

        # 挑戦者は2階層下へ
        challenger_state.floor_id = min(
            100,
            floor.floor + 2,
        )

        challenger_state.current_hp = challenger.max_hp
        challenger_state.current_mp = challenger.max_mp

        # 防衛者は階層を維持し、HP/MPを引き継ぐ
        defender_state.current_hp = max(
            0,
            result["defender_hp"],
        )

        defender_state.current_mp = max(
            0,
            result["defender_mp"],
        )

        if winner == "defender":
            history_result = ArenaBattleHistory.Result.LOSS
        else:
            history_result = ArenaBattleHistory.Result.DRAW

    # ========================================
    # ArenaStateを保存
    # ========================================

    challenger_state.save(
        update_fields=[
            "floor",
            "current_hp",
            "current_mp",
            "updated_at",
        ]
    )

    defender_state.save(
        update_fields=[
            "floor",
            "current_hp",
            "current_mp",
            "updated_at",
        ]
    )

    # ========================================
    # 対戦履歴
    # ========================================

    history = ArenaBattleHistory.objects.create(
        challenger=challenger,
        defender=defender,
        floor=floor.floor,
        result=history_result,
        battle_logs=result["logs"],
        challenger_hp_after=battle_hp_mp["challenger_hp"],
        challenger_mp_after=battle_hp_mp["challenger_mp"],
        defender_hp_after=battle_hp_mp["defender_hp"],
        defender_mp_after=battle_hp_mp["defender_mp"],
        challenger_floor_after=challenger_state.floor_id,
        defender_floor_after=defender_state.floor_id,
    )

    return {
        "winner": winner,
        "history_id": history.pk,
        "challenger_floor": challenger_state.floor_id,
        "defender_floor": defender_state.floor_id,
    }