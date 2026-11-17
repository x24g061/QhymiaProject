"""実BattleEngineの観測・構成再現。計算式/乱数/ゲームDBを書き換えない。"""
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from apps.accounts.models import Character, User
from apps.inventory.models import Equipment, OwnedEquipment
from apps.battle.models import Skill, SkillPreset
from apps.battle.combatants import Combatant
from apps.battle.services import BattleEngine
from apps.battle.boss_simulation import seeded_random
from apps.battle.initiative import calculate_gauge_gain

SCHEMA = 2
AUTHORIZED_DATABASES = set()
ROOT = Path(settings.BASE_DIR)
PROFILE_FILE = ROOT / "docs/変更詳細/BOSS_BASELINE_STAGE1.json"
STAT_FIELDS = ("max_hp", "max_mp", "strength", "intelligence", "dexterity", "agility", "vitality", "luck")
ATTRIBUTES = ("fire", "water", "grass", "rock", "light", "dark")
# 固定の比較用戦術。最適化済み/正式推奨ではない。未完成3効果は利用しない。
TACTICS = {
    "grappler": {
        "B": [("fighting_spirit", 2), ("double_punch", 4), ("true_fist", 4)],
        "C": [("true_fist", 8), ("rapid_barrage", 4), ("double_punch", 4)],
        "D": [("fighting_spirit", 4), ("shock_wave", 3), ("true_fist", 3)],
    },
    "warrior": {
        "B": [("steel_body", 3), ("flare_blade", 5), ("counter_stance", 3)],
        "C": [("one_hit_kill", 6), ("flare_blade", 8)],
        "D": [("solid_stance", 4), ("counter_stance", 4), ("steel_body", 4), ("flare_blade", 3)],
    },
    "hunter": {
        "B": [("hunter_eye", 2), ("poison_arrow", 3), ("rapid_shot", 5)],
        "C": [("rapid_shot", 10), ("poison_arrow", 4)],
        "D": [("sleep_arrow", 4), ("hide", 3), ("poison_arrow", 4), ("hunter_eye", 2)],
    },
    "wizard": {
        "B": [("fire", 4), ("stella", 4), ("megido", 2)],
        "C": [("stella", 8), ("explosion", 4)],
        "D": [("megido", 4), ("fire", 4)],
    },
    "priest": {
        "B": [("judgement", 4), ("healing_shield", 3), ("anti_jail", 3)],
        "C": [("anti_jail", 8), ("judgement", 5)],
        "D": [("healing_shield", 6), ("judgement", 4)],
    },
    "wanderer": {
        "B": [("principle_of_freedom", 1), ("walker", 2), ("strike_core", 4), ("short_rest", 3)],
        "C": [("principle_of_freedom", 1), ("strike_core", 10), ("walker", 3)],
        "D": [("principle_of_freedom", 1), ("short_rest", 6), ("walker", 3), ("strike_core", 3)],
    },
    "assassin": {
        "B": [("stealth", 1), ("poison_dagger", 4), ("shadow_step", 3)],
        "C": [("surprise_attack", 6), ("poison_dagger", 6)],
        "D": [("stealth", 1), ("shadow_step", 5), ("flashbang", 4), ("poison_dagger", 3)],
    },
}
TACTIC_NOTES = {
    "wizard:D": "完成済みの防御・回復技がないため真の耐久戦術は成立しない。防御無視/低MPの代用比較。",
    "grappler:D": "回復・防御技なし。STRバフ中心の補助構成という限定的比較。",
    "hunter:D": "回復なし。状態異常/命中低下中心。",
    "counts": "回数は比較用の有限予算。最適化済みではない。--use-scaleでアクティブ回数だけを変更可能。",
}


def require_isolation():
    name = connection.settings_dict["NAME"]
    if name not in AUTHORIZED_DATABASES or not str(name).startswith("test_qhymia_simv2_"):
        raise RuntimeError("専用テストDB以外でのVer.2測定を拒否しました")
    if connection.vendor != "postgresql":
        raise RuntimeError("測定はPostgreSQL専用です")


@contextmanager
def authorized_database(name):
    """ランナー/契約テストが生成・確認した専用DBだけを一時許可する。"""
    if connection.settings_dict["NAME"] != name or not str(name).startswith("test_qhymia_simv2_"):
        raise RuntimeError("DB名が専用テストDBと一致しません")
    AUTHORIZED_DATABASES.add(name)
    try:
        require_isolation()
        yield
    finally:
        AUTHORIZED_DATABASES.discard(name)


def reject_writes(execute, sql, params, many, context):
    if not sql.lstrip().upper().startswith("SELECT"):
        raise RuntimeError("測定中のSELECT以外のSQLを拒否しました")
    return execute(sql, params, many, context)


def baseline_module():
    spec = importlib.util.spec_from_file_location("simulation_v2_baseline", PROFILE_FILE.with_suffix(".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_profiles(comparisons=False):
    rows = json.loads(PROFILE_FILE.read_text())["records"]
    if len(rows) != 336:
        raise ValueError("第1段階の336構成が必要です")
    for index, row in enumerate(rows):
        row = dict(row)
        row["profile_id"] = f"p{index:03d}"
        yield row
    if comparisons:
        module = baseline_module()
        for index, row in enumerate(rows):
            if row["floor"] > 6 or row["seed"] != 20261116:
                continue
            for label, level in [("weaker", max(1, row["level"]-10)),
                                 ("stronger", min(100, row["level"]+10))]:
                character = module.path(row["job"], row["race"], row["reincarnations"], row["seed"])[level-1]
                gear = ([], dict.fromkeys(STAT_FIELDS[2:], 0), 0) if label == "weaker" else module.equipment(
                    row["job"], [2 if row["floor"] < 6 else 8]*5)
                extra = module.profile(row["floor"], character, row["seed"], "comparison-"+label, gear)
                extra["profile_id"] = f"s{index:03d}-{label}"
                extra["comparison_only"] = True
                yield extra


def tactic(job, label, use_scale=1):
    if label == "A":
        return []
    if use_scale < 1:
        raise ValueError("use-scaleは1以上です")
    return [(code, uses if code == "principle_of_freedom" else uses * use_scale)
            for code, uses in TACTICS[job][label]]


def prepare_profile(row, label, use_scale=1):
    require_isolation()
    user, _ = User.objects.get_or_create(user_id="sim-v2", defaults={"email": "sim-v2@example.invalid"})
    character, _ = Character.objects.get_or_create(user=user, defaults={"name": "Ver2測定者"})
    for field, value in (row["stats"] | row["attributes"]).items():
        setattr(character, field, value)
    character.job, character.race = row["job"], row["race"]
    character.level, character.reincarnation_count = row["level"], row["reincarnations"]
    character.current_hp, character.current_mp = character.max_hp, character.max_mp
    character.max_stamina, character.current_stamina = row["max_st"], row["start_st"]
    for field, value in row["attribute_weights"].items():
        setattr(character, field + "_growth_weight", value)
    character.save()
    character.owned_equipments.all().delete()
    for entry in row["equipment"]:
        equipment = Equipment.objects.get(item__name=entry["name"])
        from apps.inventory.services import calculate_equipment_battle_power
        expected = calculate_equipment_battle_power(equipment.base_battle_power, equipment.rank, entry["enhancement"])
        if expected != entry["power"]:
            raise ValueError("装備マスター/強化値が第1段階と一致しません")
        OwnedEquipment.objects.create(character=character, equipment=equipment,
            enhancement_level=entry["enhancement"], battle_power=expected, is_equipped=True,
            special_effect=entry["special_effect"] or "")
    character.skill_presets.all().delete()
    for slot, (code, uses) in enumerate(tactic(character.job, label, use_scale), 1):
        skill = Skill.objects.get(code=code, job=character.job)
        SkillPreset.objects.create(character=character, skill=skill, slot=slot, use_count=uses)
    module = baseline_module()
    if module.power(character, sum(e["power"] for e in row["equipment"])) != row["power"]:
        raise ValueError("表示戦闘力が一致しません")
    from apps.battle.engine.character_stats import get_character_base_combat_stat, get_character_battle_max_resource
    actual = {key: get_character_base_combat_stat(character, key) for key in STAT_FIELDS[2:]}
    actual.update({"max_hp": get_character_battle_max_resource(character, "hp"),
                   "max_mp": get_character_battle_max_resource(character, "mp")})
    if actual != row["combat_start"]:
        raise ValueError("戦闘開始補正値が一致しません")
    return character


COMBATANT_STATES = ("poison_turns", "sleep_turns", "paralysis_turns", "dex_debuff_rate", "equipment_dex_debuff_rate")
ACTOR_STATES = ("walker_turns", "fighting_spirit_turns", "steel_body_turns", "solid_stance_turns",
                "counter_stance_turns", "counter_remaining", "hunter_eye_turns", "hide_turns",
                "shadow_step_turns", "stealth_active", "mirage_active", "freedom_bonus", "elf_agility_bonus")


def measure(character, boss, seed, *, observe=True, detail=False):
    require_isolation()
    if not boss.is_boss:
        raise ValueError("ボスが必要です")
    actions, events, state_events, gains = [], [], [], []
    totals = {side: defaultdict(Counter) for side in ("player", "boss")}
    contexts = []
    gauge_calls = 0
    actors = {}
    objects = {}
    last_gain = {}

    def side_of(obj):
        return objects.get(id(obj))

    def category():
        return contexts[-1] if contexts else (None, "unclassified", None)

    def assign(obj, name, value):
        old = getattr(obj, name, None)
        object.__setattr__(obj, name, value)
        side = side_of(obj)
        if side is None or old is None:
            return
        source, kind, code = category()
        if name == "hp" and value != old:
            if value < old:
                amount = max(0, old) - max(0, value)
                actual_kind = "reflection" if kind.startswith("delivery:") and source == side else kind.removeprefix("delivery:")
                if actual_kind == "skill" and source == side:
                    actual_kind = "recoil"
                attacker = source if source != side else ("boss" if side == "player" else "player")
                if actual_kind == "poison":
                    attacker = "boss" if side == "player" else "player"
                if actual_kind == "recoil":
                    attacker = side
                totals[side]["damage_taken"][actual_kind] += amount
                if attacker:
                    totals[attacker]["damage_dealt"][actual_kind] += amount
                event = {"tick": gauge_calls // 2, "target": side, "kind": actual_kind,
                         "source": attacker, "skill": code, "amount": amount, "raw_delta": old-value}
            else:
                amount = max(0, value) - max(0, old)
                totals[side]["healing"][kind] += amount
                event = {"tick": gauge_calls // 2, "target": side, "kind": "heal", "source": source,
                         "skill": code, "amount": amount}
            events.append(event)
        elif name in COMBATANT_STATES and (old != value or value):
            transition = "apply" if not old and value else "clear" if old and not value else "refresh" if old == value else "change"
            state_events.append({"tick": gauge_calls // 2, "side": side, "state": name,
                                 "before": old, "after": value, "transition": transition})

    def snapshot(actor):
        return {key: getattr(actor, key) for key in ACTOR_STATES}

    def wrap_context(actor, method, kind):
        original = getattr(actor, method)
        def invoke(*args, **kwargs):
            side = side_of(actor.player_combatant)
            selected = kind
            code = None
            if method == "execute_player_skill":
                code = args[0].code
            if method == "player_physical_skill_hit":
                selected = "counter" if kwargs.get("skill_name") == "反撃" else category()[1]
                code = "counter" if selected == "counter" else category()[2]
            if method == "deal_target_damage":
                selected = "delivery:" + category()[1]
                code = category()[2]
            if method == "process_action_status":
                side = side_of(args[0])
            before = snapshot(actor)
            contexts.append((side, selected, code))
            try:
                return original(*args, **kwargs)
            finally:
                contexts.pop()
                after = snapshot(actor)
                for key in before:
                    if before[key] != after[key]:
                        state_events.append({"tick": gauge_calls // 2, "side": side, "state": key,
                            "before": before[key], "after": after[key],
                            "transition": "apply" if not before[key] else "clear" if not after[key] else "change"})
                if method == "finish_player_action" and actions and actions[-1]["side"] == side:
                    actions[-1]["after"] = {"hp": actor.player_hp, "mp": actor.player_mp, "st": actor.player_stamina}
        return invoke

    with seeded_random(seed), connection.execute_wrapper(reject_writes), ExitStack() as stack:
        engine = BattleEngine(character, boss, floor=boss.floor, starting_stamina=100)
        actor = engine.enemy_combatant.skill_actor
        actors.update(player=engine, boss=actor)
        objects.update({id(engine.player_combatant): "player", id(engine.enemy_combatant): "boss"})
        initial = {s: {"hp": a.player_hp, "mp": a.player_mp, "st": a.player_stamina,
                        "max_hp": a.player_max_hp, "max_mp": a.player_max_mp, "max_st": a.player_max_stamina}
                   for s, a in actors.items()}

        def gain(agi, reference):
            nonlocal gauge_calls
            side = "player" if gauge_calls % 2 == 0 else "boss"
            gauge_calls += 1
            value = calculate_gauge_gain(agi, reference)
            last_gain[side] = {"agi": agi, "reference": reference, "gain": value,
                               "before": actors[side].player_initiative}
            return value

        def turn(side, original):
            def invoke():
                current = actors[side]
                active = {key: getattr(current.player_combatant, key) for key in COMBATANT_STATES}
                active.update(snapshot(current))
                before = {"hp": current.player_hp, "mp": current.player_mp, "st": current.player_stamina}
                log_start = len(engine.logs)
                if side == "boss":
                    boss_action[0] = "status_skip"
                code = original()
                if side == "boss":
                    code = boss_action[0]
                logs = engine.logs[log_start:]
                actions.append({"side": side, "tick": gauge_calls // 2, "code": code,
                    "before": before, "after": {"hp": current.player_hp, "mp": current.player_mp, "st": current.player_stamina},
                    "gauge": dict(last_gain[side]), "after_consumption": current.player_initiative,
                    "active_states": active,
                    # 失敗理由はエンジンがコードとして返さないためログの定型文を補助利用する。
                    "failed": sum("は発動しなかった" in log for log in logs),
                    "mp_shortage": sum("MPが足りない" in log for log in logs)})
                return code
            return invoke

        boss_action = ["status_skip"]
        original_boss_player_turn = actor.player_turn
        def boss_player_turn():
            boss_action[0] = original_boss_player_turn()
            return boss_action[0]

        if observe:
            stack.enter_context(patch.object(Combatant, "__setattr__", assign))
            for current in actors.values():
                for method, kind in [("player_normal_attack", "normal"), ("execute_player_skill", "skill"),
                    ("player_physical_skill_hit", "skill"), ("deal_target_damage", "delivery"),
                    ("apply_player_turn_start_race_passive", "race_passive"),
                    ("finish_player_action", "finish")]:
                    stack.enter_context(patch.object(current, method, wrap_context(current, method, kind)))
            stack.enter_context(patch.object(engine, "process_action_status", wrap_context(engine, "process_action_status", "poison")))
            stack.enter_context(patch.object(actor, "player_turn", boss_player_turn))
            stack.enter_context(patch.object(engine, "player_turn", turn("player", engine.player_turn)))
            stack.enter_context(patch.object(engine, "enemy_turn", turn("boss", engine.enemy_turn)))
        stack.enter_context(patch("apps.battle.engine.core.calculate_gauge_gain", side_effect=gain))
        result = engine.run()

    loops = gauge_calls // 2
    final = {s: {"hp": max(0, a.player_hp), "raw_hp": a.player_hp, "mp": a.player_mp, "st": a.player_stamina}
             for s, a in actors.items()}
    core = {"winner": result["winner"], "loops": loops, "final": final,
            "remaining_uses": {s: {p.skill.code+":"+str(p.slot): a.remaining_uses.get(p.id)
                for p in a.presets} for s, a in actors.items()},
            "logs": result["logs"], "timeline": result["timeline"]}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    output = {"seed": seed, "winner": result["winner"], "loops": loops,
        "termination": "loop_limit" if result["winner"] == "draw" and loops == 1000 else "draw" if result["winner"] == "draw" else "defeat",
        "reached_1000": loops == 1000, "exception": None, "digest": digest,
        "initial": initial, "final": final, "remaining_uses": core["remaining_uses"]}
    if observe:
        if any(n != 1 for n in Counter((a["side"], a["tick"]) for a in actions).values()):
            raise AssertionError("1ループ1行動に違反")
        for event in actions:
            g = event["gauge"]
            if not math.isclose(event["after_consumption"], g["before"]+g["gain"]-100):
                raise AssertionError("ゲージ100消費に違反")
        for side in actors:
            moves = [a for a in actions if a["side"] == side]
            st = initial[side]["st"]
            for event in moves:
                expected = st if event["code"] in ("skip", "status_skip") else max(0, st-5)
                st = expected
            if final[side]["st"] != st:
                raise AssertionError("ST消費の整合性エラー")
            damage = sum(totals[side]["damage_taken"].values())
            healing = sum(totals[side]["healing"].values())
            if initial[side]["hp"] + healing - damage != final[side]["hp"]:
                raise AssertionError("HP台帳が不一致")
            output[side] = {"actions": len(moves), "normal_attacks": sum(a["code"] == "normal" for a in moves),
                "skills": dict(Counter(a["code"] for a in moves if a["code"] not in ("normal", "skip", "status_skip"))),
                "activation_failures": sum(a["failed"] for a in moves),
                "mp_shortages": sum(a["mp_shortage"] for a in moves),
                "skips": sum(a["code"] in ("skip", "status_skip") for a in moves),
                "damage_dealt": dict(totals[side]["damage_dealt"]), "damage_taken": dict(totals[side]["damage_taken"]),
                "healing": dict(totals[side]["healing"]), "mp_empty": final[side]["mp"] == 0,
                "st_empty": final[side]["st"] == 0,
                "status_transitions": dict(Counter(e["state"]+":"+e["transition"] for e in state_events if e["side"] == side)),
                "status_active_actions": dict(Counter(k for a in moves for k,v in a["active_states"].items() if v))}
        output["action_difference"] = output["player"]["actions"]-output["boss"]["actions"]
        if detail:
            output.update(actions=actions, hp_events=events, state_events=state_events)
    return output


def wilson(wins, n):
    if not n:
        return None
    z = 1.959963984540054
    p = wins/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    radius = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0, center-radius), min(1, center+radius)]


def summarize(runs):
    valid = [r for r in runs if not r.get("exception")]
    wins = sum(r["winner"] == "player" for r in valid)
    return {"trials": len(runs), "valid": len(valid), "exceptions": len(runs)-len(valid),
        "wins": wins, "losses": sum(r["winner"] == "enemy" for r in valid),
        "draws": sum(r["winner"] == "draw" for r in valid),
        "win_rate": wins/len(valid) if valid else None, "wilson95": wilson(wins, len(valid)),
        "mean_loops": statistics.mean(r["loops"] for r in valid) if valid else None,
        "median_loops": statistics.median(r["loops"] for r in valid) if valid else None,
        "loop_limits": sum(r["termination"] == "loop_limit" for r in valid),
        "player_mean_actions": statistics.mean(r["player"]["actions"] for r in valid) if valid else None,
        "boss_mean_actions": statistics.mean(r["boss"]["actions"] for r in valid) if valid else None,
        "mean_action_difference": statistics.mean(r["action_difference"] for r in valid) if valid else None}
