"""ステップ5-Aの評価条件。ゲームの能力値・計算式を変更しない。"""
import copy
import random

from django.db import connection
from apps.accounts.models import Character
from apps.battle import simulation_v2 as sim

SKILL_CODES = {
    "grappler": "double_punch shock_wave rapid_barrage fighting_spirit true_fist".split(),
    "warrior": "flare_blade one_hit_kill steel_body solid_stance counter_stance".split(),
    "hunter": "rapid_shot sleep_arrow hunter_eye hide poison_arrow".split(),
    "wizard": "stella fire megido explosion frost_armor".split(),
    "priest": "judgement healing_shield purification resurrection anti_jail".split(),
    "wanderer": "strike_core mirage short_rest walker principle_of_freedom".split(),
    "assassin": "surprise_attack poison_dagger stealth shadow_step flashbang".split(),
}
# Bも攻撃を主軸とし、防御で意図的に時間を浪費しない。Cは補助枠を火力へ配分する。
NATIVE = {
    "grappler": {"B": [("fighting_spirit", 2), ("true_fist", 6), ("double_punch", 6)],
                 "C": [("true_fist", 8), ("double_punch", 8)]},
    "warrior": {"B": [("flare_blade", 8), ("one_hit_kill", 5), ("counter_stance", 2)],
                "C": [("one_hit_kill", 8), ("flare_blade", 8)]},
    "hunter": {"B": [("poison_arrow", 4), ("rapid_shot", 8), ("hunter_eye", 2)],
               "C": [("rapid_shot", 10), ("poison_arrow", 4)]},
    "wizard": {"B": [("megido", 5), ("stella", 8), ("explosion", 4)],
               "C": [("stella", 10), ("explosion", 6), ("megido", 4)]},
    "priest": {"B": [("anti_jail", 8), ("judgement", 5), ("healing_shield", 2)],
               "C": [("anti_jail", 10), ("judgement", 6)]},
    "wanderer": {"B": [("principle_of_freedom", 1), ("strike_core", 10), ("short_rest", 2)],
                 "C": [("principle_of_freedom", 1), ("strike_core", 14)]},
    "assassin": {"B": [("stealth", 1), ("poison_dagger", 6), ("shadow_step", 5)],
                 "C": [("surprise_attack", 8), ("poison_dagger", 6)]},
}


def origins(job):
    if job == "wizard":
        return ["priest", "wanderer"]
    if job == "priest":
        return ["wizard", "wanderer"]
    return ["grappler", "priest"]


def inheritance(job, count, seed=50361117):
    """取得職業履歴を先に固定。引いたスキルで選別しない。"""
    rng = random.Random(seed)
    owned, history = set(), []
    for source in origins(job):
        for _ in range(min(5, count-len(history))):
            candidates = sorted(set(SKILL_CODES[source])-owned)
            code = rng.choice(candidates)
            owned.add(code)
            history.append({"reincarnation": len(history)+1, "previous_job": source, "acquired": code})
    rest = count-len(history)
    # 残りは既に5種習得済みの職業で回帰し、追加なしという合法な経路。
    return sorted(owned), history, {"count": rest, "previous_job": origins(job)[0], "acquired": None}


def slots(job, learned):
    result = copy.deepcopy(NATIVE[job])
    allowed = set(SKILL_CODES[job]) | set(learned)
    if learned:
        if job in ("wizard", "priest"):
            result = {
                "B": [("principle_of_freedom", 1), ("anti_jail", 8), ("judgement", 5), ("healing_shield", 2)],
                "C": [("principle_of_freedom", 1), ("anti_jail", 10), ("stella", 8), ("megido", 4)],
            }
        else:
            # 物理職に魔法火力を強制しない。真拳/闘魂でSTR・LUKを使う。
            result["B"] = [("fighting_spirit", 2), ("true_fist", 6), ("double_punch", 6), ("healing_shield", 2)]
            result["C"] = [("true_fist", 8), ("double_punch", 8)]
            if job == "wanderer":
                result["B"].insert(0, ("principle_of_freedom", 1))
                result["C"].insert(0, ("principle_of_freedom", 1))
            if job == "warrior":
                result["C"].append(("one_hit_kill", 5))
            if job == "hunter":
                result["C"].append(("poison_arrow", 4))
            if job == "assassin":
                result["C"].append(("poison_dagger", 4))
    # 低回帰の部分取得ではまだ使えない候補を混ぜない。現職戦術へ戻す。
    return {label: sequence if all(code in allowed for code,_ in sequence) else copy.deepcopy(NATIVE[job][label])
            for label, sequence in result.items()}


def profiles():
    module = sim.baseline_module()
    rows = [r for r in sim.load_profiles() if r["seed"] == 20261116
            and (r["floor"] < 7 or r["variant"].startswith("mid-"))]
    with connection.execute_wrapper(module.no_sql):
        for source in rows:
            row = copy.deepcopy(source)
            floor, job = row["floor"], row["job"]
            enhancement = 3 if floor == 5 else 5 if floor >= 7 else None
            if enhancement is not None:
                character = Character(job=job, race=row["race"], level=row["level"],
                                      reincarnation_count=row["reincarnations"], **row["stats"], **row["attributes"])
                row.update(module.profile(floor, character, row["seed"], f"F+{enhancement}",
                                          module.equipment(job, [enhancement]*5), row["target_power"]))
            for mode in (["none"] if row["reincarnations"] == 0 else ["none", "trained"]):
                profile = copy.deepcopy(row)
                learned, history, rest = inheritance(job, row["reincarnations"])
                profile.update(profile_id=f"v5-{source['profile_id']}-{mode}",
                               inheritance_mode=mode, permanent_skill_codes=learned if mode == "trained" else [],
                               inheritance_history=history if mode == "trained" else [],
                               inheritance_remaining=rest if mode == "trained" else None,
                               recommendation_eligible=mode == "trained" or row["reincarnations"] == 0,
                               origin_profile_id=source["profile_id"])
                profile["tactics"] = slots(job, profile["permanent_skill_codes"])
                yield profile


def validate_profile(row):
    codes = row["permanent_skill_codes"]
    if len(codes) > row["reincarnations"] or len(codes) != len(set(codes)):
        raise ValueError("回帰数と取得数が不整合")
    if row["inheritance_mode"] == "trained":
        owned = set()
        for event in row["inheritance_history"]:
            code = event["acquired"]
            if code not in SKILL_CODES[event["previous_job"]] or code in owned:
                raise ValueError("回帰前職業/未習得条件違反")
            owned.add(code)
        if owned != set(codes):
            raise ValueError("履歴と習得が不一致")
        rest = row["inheritance_remaining"]
        if len(owned)+rest["count"] != row["reincarnations"]:
            raise ValueError("回帰履歴数が不一致")
        if rest["count"] and not set(SKILL_CODES[rest["previous_job"]]) <= owned:
            raise ValueError("追加習得なしの履歴が不正")
    allowed = set(SKILL_CODES[row["job"]]) | set(codes)
    for sequence in row["tactics"].values():
        if len(sequence) > 5 or any(code not in allowed or n < 1 for code,n in sequence):
            raise ValueError("戦術の資格/5枠/回数違反")
        if any(code in ("frost_armor", "purification", "resurrection") for code,_ in sequence):
            raise ValueError("未完成スキル")
