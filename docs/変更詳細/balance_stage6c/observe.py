"""既存sim.measureへ読取り専用トレースを重ねる。乱数・行動判断を変更しない。"""
from collections import Counter, defaultdict
from contextlib import ExitStack
from unittest.mock import patch

BUFFS = ("steel_body_turns", "solid_stance_turns", "counter_stance_turns", "counter_remaining", "healing_shield_turns")
ATTACKS = {"normal", "shock_wave", "true_fist"}
SUPPORT = {"steel_body", "solid_stance", "counter_stance"}


def measure(sim, character, boss, seed):
    original_run = sim.BattleEngine.run
    frames, hp_contexts = [], []

    def traced_run(engine):
        actors = {"player": engine, "boss": engine.enemy_combatant.skill_actor}
        sides = {id(a.player_combatant): side for side, a in actors.items()}
        current = [None]
        def snapshot():
            return {s: {k: getattr(a, k) for k in BUFFS} for s, a in actors.items()}
        def turn(side, original):
            def invoke():
                frame = {"id": len(frames), "side": side, "before": snapshot(), "attempts": [], "skill_peaks": []}
                frames.append(frame)
                current[0] = frame
                result = original()
                frame["after_turn"] = snapshot()
                return result
            return invoke
        def cost(side, original):
            def invoke(skill):
                value = original(skill)
                if current[0] is None or current[0]["side"] != side:
                    raise AssertionError("MP費用観測の行動対応が不正")
                current[0]["attempts"].append({"code": skill.code, "cost": value,
                                               "mp_before": actors[side].player_mp})
                return value
            return invoke
        def execute(side, original):
            def invoke(skill):
                result = original(skill)
                current[0]["skill_peaks"].append({"side": side, "code": skill.code, "after_skill": snapshot()})
                return result
            return invoke
        def finish(side, original):
            def invoke(code):
                result = original(code)
                if current[0] is None or current[0]["side"] != side:
                    raise AssertionError("終了観測の行動対応が不正")
                current[0]["finished"] = snapshot()
                return result
            return invoke
        original_assign = sim.Combatant.__setattr__
        def assign(obj, name, value):
            old = getattr(obj, name, None)
            side = sides.get(id(obj))
            context = None
            if name == "hp" and side is not None and old is not None and old != value:
                context = {"frame": current[0]["id"] if current[0] is not None else None,
                           "target": side, "before_hp": old, "after_hp": value, "states": snapshot()}
            original_assign(obj, name, value)
            if context is not None:
                hp_contexts.append(context)
        with ExitStack() as stack:
            stack.enter_context(patch.object(engine, "player_turn", turn("player", engine.player_turn)))
            stack.enter_context(patch.object(engine, "enemy_turn", turn("boss", engine.enemy_turn)))
            for side, actor in actors.items():
                stack.enter_context(patch.object(actor, "get_skill_mp_cost", cost(side, actor.get_skill_mp_cost)))
                stack.enter_context(patch.object(actor, "execute_player_skill", execute(side, actor.execute_player_skill)))
                stack.enter_context(patch.object(actor, "finish_player_action", finish(side, actor.finish_player_action)))
            stack.enter_context(patch.object(sim.Combatant, "__setattr__", assign))
            return original_run(engine)

    with patch.object(sim.BattleEngine, "run", traced_run):
        record = sim.measure(character, boss, seed, detail=True)
    if len(frames) != len(record["actions"]) or len(hp_contexts) != len(record["hp_events"]):
        raise AssertionError("詳細観測と既存台帳の件数不一致")
    for frame, action in zip(frames, record["actions"]):
        if frame["side"] != action["side"] or len(frame["attempts"]) > 1:
            raise AssertionError("行動/スキル試行の対応不一致")
        frame.update(tick=action["tick"], code=action["code"])
        for attempt in frame["attempts"]:
            if action["code"] == attempt["code"]:
                result = "success"
            elif action["mp_shortage"]:
                result = "mp_shortage"
            elif action["failed"]:
                result = "activation_failure"
            else:
                raise AssertionError("未分類のスキル試行")
            attempt["result"] = result
    for context, event in zip(hp_contexts, record["hp_events"]):
        if context["target"] != event["target"]:
            raise AssertionError("HP観測の対象不一致")
        raw = context["before_hp"]-context["after_hp"]
        expected = max(0, context["before_hp"])-max(0, context["after_hp"]) if raw > 0 else -raw
        if expected != event["amount"]:
            raise AssertionError("HP観測の実損傷不一致")
    record["skill_trace"] = {"frames": frames, "hp_contexts": hp_contexts}
    record["titan_analysis"] = summarize(record)
    return record


def summarize(record):
    frames = record["skill_trace"]["frames"]
    boss = [f for f in frames if f["side"] == "boss"]
    player = [f for f in frames if f["side"] == "player"]
    events = list(zip(record["hp_events"], record["skill_trace"]["hp_contexts"]))
    by_frame = defaultdict(list)
    for e, c in events:
        by_frame[c["frame"]].append(e)
    trials = {s: defaultdict(Counter) for s in ("player", "boss")}
    for frame in frames:
        for a in frame["attempts"]:
            trials[frame["side"]][a["code"]]["attempts"] += 1
            trials[frame["side"]][a["code"]][a["result"]] += 1
    nominal = [f for f in boss if f["code"] in ATTACKS]
    attack_skill = [f for f in boss if f["code"] in ATTACKS-{"normal"}]
    threat = [f for f in boss if any(e["source"] == "boss" and e["target"] == "player" and
        e["kind"] in ("normal", "skill") and e["amount"] > 0 for e in by_frame[f["id"]])]
    first = attack_skill[0] if attack_skill else None
    heals = [f for f in player if f["code"] == "healing_shield"]
    full_heals = [f for f in heals if record["actions"][f["id"]]["before"]["hp"] == record["initial"]["player"]["max_hp"]]
    damage = Counter()
    coverage, overlap = Counter(), Counter()
    support_window_damage = 0
    preceding_boss_code, last_code = {}, None
    for frame in frames:
        preceding_boss_code[frame["id"]] = last_code
        if frame["side"] == "boss" and frame["code"] not in ("skip", "status_skip"):
            last_code = frame["code"]
    for e, c in events:
        if e["source"] == "boss" and e["target"] == "player" and e["kind"] != "heal":
            damage[e["skill"] or e["kind"]] += e["amount"]
        if e["source"] != "player" or e["target"] != "boss" or e["kind"] not in ("normal", "skill"):
            continue
        state = c["states"]["boss"]
        active = [k for k in BUFFS[:3] if state[k] > 0]
        for key in active:
            coverage[key] += e["amount"]
        if len(active) > 1:
            overlap["damage"] += e["amount"]
            overlap["hit_events"] += 1
        # 最後に成功したボス行動が補助である間の、実際のプレイヤー直接損傷。
        if preceding_boss_code.get(c["frame"]) in SUPPORT:
            support_window_damage += e["amount"]
    uses = {s: [v for v in record["remaining_uses"][s].values() if v is not None] for s in ("player", "boss")}
    return {
        "boss_first_five": [{"tick": f["tick"], "code": f["code"], "attempt": f["attempts"]} for f in boss[:5]],
        "first_attack_skill_boss_ordinal": boss.index(first)+1 if first else None,
        "first_attack_skill_tick": first["tick"] if first else None,
        "boss_direct_attack_actions": len(nominal), "boss_attack_skill_actions": len(attack_skill),
        "boss_threatening_direct_actions": len(threat),
        "boss_support_actions": sum(f["code"] in SUPPORT for f in boss),
        "boss_damage_by_skill": dict(damage),
        "counter_damage": sum(e["amount"] for e in record["hp_events"] if e["source"] == "boss" and e["target"] == "player" and e["kind"] == "counter"),
        "boss_died_before_attack_skill": record["final"]["boss"]["hp"] == 0 and not attack_skill,
        "boss_died_before_any_direct_attack": record["final"]["boss"]["hp"] == 0 and not nominal,
        "boss_died_without_threatening_direct_action": record["final"]["boss"]["hp"] == 0 and not threat,
        "boss_direct_damage_while_effect_active": dict(coverage),
        "boss_incoming_overlap": dict(overlap), "player_direct_damage_in_support_windows": support_window_damage,
        "skill_attempts": {s: {k: dict(v) for k, v in values.items()} for s, values in trials.items()},
        "player_healing_shield_actions": len(heals), "player_healing_shield_at_full": len(full_heals),
        "all_active_exhausted": {s: bool(v) and all(n == 0 for n in v) for s, v in uses.items()},
    }
