"""テスト用の1対1測定器。戦闘計算・乱数判定・DB更新を代替しない。"""
from collections import Counter
from contextlib import contextmanager
import random
from unittest.mock import patch

from django.db import connection

from apps.battle.initiative import calculate_gauge_gain
from apps.battle.services import BattleEngine


@contextmanager
def seeded_random(seed):
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


def measure_battle(character, boss, seed):
    """実エンジンを測定する。呼出元はテストDBとキャラクターを用意する。"""
    if not boss.is_boss:
        raise ValueError("ボスを指定してください")
    actions = []
    gauge_calls = 0

    def reject_writes(execute, sql, params, many, context):
        if not sql.lstrip().upper().startswith("SELECT"):
            raise AssertionError("戦闘中にSELECT以外のDB操作を検出しました")
        return execute(sql, params, many, context)

    def gain(*args, **kwargs):
        nonlocal gauge_calls
        gauge_calls += 1
        return calculate_gauge_gain(*args, **kwargs)

    with seeded_random(seed), connection.execute_wrapper(reject_writes):
        engine = BattleEngine(character, boss)
        actor = engine.enemy_combatant.skill_actor
        original_player_turn = engine.player_turn
        original_enemy_turn = engine.enemy_turn
        original_boss_turn = actor.player_turn
        boss_code = "status_skip"

        def record(side, action):
            current = engine if side == "player" else actor
            mp, st = current.player_mp, current.player_stamina
            log_start = len(engine.logs)
            code = action()
            actions.append({
                "side": side, "tick": gauge_calls // 2, "code": code,
                "mp_before": mp, "mp_after": current.player_mp,
                # 行動終了処理は外側で実行されるのでST減少は最終状態でも確認する。
                "st_before": st, "logs": engine.logs[log_start:],
            })
            return code

        def boss_turn():
            nonlocal boss_code
            boss_code = original_boss_turn()
            return boss_code

        def enemy_turn():
            nonlocal boss_code
            boss_code = "status_skip"
            def invoke():
                original_enemy_turn()
                return boss_code
            return record("boss", invoke)

        actor.player_turn = boss_turn
        engine.player_turn = lambda: record("player", original_player_turn)
        engine.enemy_turn = enemy_turn
        with patch("apps.battle.engine.core.calculate_gauge_gain", side_effect=gain):
            result = engine.run()

    def summary(side, current):
        events = [a for a in actions if a["side"] == side]
        uses = Counter()
        for preset in current.presets:
            if not preset.skill.is_passive:
                uses[preset.skill.code] += preset.use_count - current.remaining_uses[preset.id]
        logs = [log for event in events for log in event["logs"]]
        return {
            "actions": len(events), "hp": max(0, current.player_hp),
            "mp": current.player_mp, "st": current.player_stamina,
            "max_hp": current.player_max_hp, "max_mp": current.player_max_mp,
            "max_st": current.player_max_stamina,
            "skill_uses": dict(uses),
            "activation_failures": sum("は発動しなかった" in log for log in logs),
            "mp_shortages": sum("MPが足りない" in log for log in logs),
        }

    return {
        "seed": seed, "floor": boss.floor, "boss_name": boss.name,
        "winner": result["winner"], "ticks": gauge_calls // 2,
        "loop_limit": gauge_calls // 2 == 1000,
        "player": summary("player", engine), "boss": summary("boss", actor),
        "actions": actions, "timeline": result["timeline"],
    }
