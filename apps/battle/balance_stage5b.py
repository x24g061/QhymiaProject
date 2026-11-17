"""5-B評価条件。正式ボス値・旧戦術を変更しない。"""
import copy
from apps.battle import balance_stage5 as previous

C2 = [("principle_of_freedom", 1), ("anti_jail", 12), ("judgement", 8)]
CANDIDATES = {8: ("agility", [180, 540, 900]),
              1: ("max_hp", [64, 80, 96, 128]),
              6: ("max_hp", [9600, 11520, 13440]),
              7: ("intelligence", [1600, 1440, 1280])}


def evaluation_boss(boss, overrides):
    """許可された単一能力だけをメモリ上で変更。保存は行わない。"""
    candidate = copy.copy(boss)
    if not overrides:
        return candidate
    if boss.floor not in CANDIDATES or len(overrides) != 1 or not boss.is_boss:
        raise ValueError("評価用ボス条件が不正")
    field, values = CANDIDATES[boss.floor]
    if set(overrides) != {field} or overrides[field] not in values:
        raise ValueError("許可されていない能力/候補値")
    setattr(candidate, field, overrides[field])
    return candidate


def scenarios():
    profiles = { (r["floor"], r["job"]): r for r in previous.profiles()
                 if r["recommendation_eligible"] }
    chosen = {}

    def add(floor, job, label, value, trials, experiment):
        base = profiles[(floor, job)]
        row = copy.deepcopy(base)
        row["tactics"] = {"B": base["tactics"]["B"], "C1": base["tactics"]["C"]}
        if job in ("wizard", "priest") and floor >= 5:
            row["tactics"]["C2"] = list(C2)
        field, values = CANDIDATES.get(floor, (None, [None]))
        overrides = {} if value == values[0] else {field: value}
        key = (floor, job, label, value)
        if key in chosen:
            existing = chosen[key][0]
            existing["evaluation_trials"] = max(trials, existing["evaluation_trials"])
            existing["experiments"].append(experiment)
            return
        row.update(profile_id=f"v5b-f{floor}-{job}-{field or 'base'}{value or 0}",
                   evaluation_trials=trials, boss_override=overrides, experiments=[experiment],
                   original_profile_id=base["profile_id"])
        previous.validate_profile(row)
        chosen[key] = (row, label, 1)

    for floor in (7, 12):
        for job in ("wizard", "priest"):
            for label in ("B", "C1", "C2"):
                add(floor, job, label, CANDIDATES.get(floor, (None,[None]))[1][0], 30, "C2_focus")
    for floor in (8, 1, 6, 7):
        for job in previous.SKILL_CODES:
            for label in ("B", "C2" if job in ("wizard", "priest") and floor != 1 else "C1"):
                for value in CANDIDATES[floor][1]:
                    add(floor, job, label, value, 10 if floor in (8,1) else 5, "sensitivity")
    return list(chosen.values())
