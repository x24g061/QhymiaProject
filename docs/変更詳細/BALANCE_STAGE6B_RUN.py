"""改訂Stage6-B。凍結した6-A新成長を用いた単一能力候補の有限測定。"""
import argparse
from collections import defaultdict
import copy
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage6b_previous", HERE / "BALANCE_STAGE6A_RUN.py")
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
ROOT, sim, runner = previous.ROOT, previous.sim, previous.runner
Enemy = previous.Enemy
OUTPUT = HERE / "balance_stage6b"
SOURCE = HERE / "balance_stage6a/confirmed/measurement"
JOBS = tuple(previous.base.SKILL_CODES)
B_TARGET = dict(enumerate((.10, .14, .17, .21, .25, .28, .32, .35, .39, .43, .46, .50), 1))
C_REFERENCE = dict(enumerate((.50, .48, .45, .43, .41, .39, .36, .34, .32, .30, .27, None), 1))
C_RANGE = (.25, .60)
GRID = {8: {"agility": (900, 1800, 2700, 3600), "max_hp": (100000, 150000, 200000)},
        7: {"max_hp": (20000, 24000, 36000), "intelligence": (1000, 1300, 1900)},
        12: {"max_hp": (190000, 220000, 260000), "strength": (6500, 7500), "intelligence": (6500, 7500)}}
SEEDS = {"pilot": 21061120, "screen": 22061120, "confirm": 23061120}
LIMITS = {"pilot": 180, "screen": 600, "confirm": 600}


def candidate_id(floor, field=None, value=None):
    return f"f{floor}-" + (f"{field}{value}" if field else "control")


def candidates():
    result = []
    for floor, fields in GRID.items():
        result.append({"id": candidate_id(floor), "floor": floor, "override": {}})
        for field, values in fields.items():
            result.extend({"id": candidate_id(floor, field, value), "floor": floor, "override": {field: value}}
                          for value in values)
    return result


@lru_cache(maxsize=1)
def profiles():
    # 旧成果物のソースを含めて凍結を確認。6-Aの全体fingerprintは新テスト追加で変わるため使わない。
    fingerprints = json.loads((SOURCE.parents[1] / "final_source_sha256.json").read_text())
    for relative, digest in fingerprints.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f"6-Aの固定ソースと不一致: {relative}")
    result = {}
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    for c in manifest["cases"]:
        row = c["profile"]
        if row["growth_version"] != "new" or row["floor"] not in GRID:
            continue
        key = (row["floor"], row["job"])
        if row["legacy_reincarnation_points"] != 0 or row.get("boss_override"):
            raise ValueError("保護分/ボス変更の混在")
        if key in result and result[key] != row:
            raise ValueError("6-AのB/Cでプロフィールが不一致")
        result[key] = copy.deepcopy(row)
    if set(result) != {(f, j) for f in GRID for j in JOBS}:
        raise ValueError("重点3階×7職の新成長が必要")
    for source in result.values():
        regenerated = previous.regenerate(source, "new")
        if any(regenerated[k] != source[k] for k in previous.REPLAY_FIELDS):
            raise ValueError("6-A新成長の再現不一致")
        previous.base.validate_profile(source)
    return result


def scenarios(phase, trials=5, selected=None):
    variants = candidates()
    if phase == "pilot":
        wanted = {candidate_id(f) for f in GRID} | {
            candidate_id(8, "agility", 3600), candidate_id(8, "max_hp", 200000),
            candidate_id(7, "max_hp", 36000), candidate_id(7, "intelligence", 1900),
            candidate_id(12, "max_hp", 260000), candidate_id(12, "strength", 7500),
            candidate_id(12, "intelligence", 7500)}
        variants = [c for c in variants if c["id"] in wanted]
        trials = 1
    elif phase == "confirm":
        if not selected or len(selected) != 6 or len(set(selected)) != 6:
            raise ValueError("各階2候補、計6候補が必要")
        wanted = set(selected) | {candidate_id(f) for f in GRID}
        variants = [c for c in variants if c["id"] in wanted]
        if len(variants) != 9 or any(sum(c["floor"] == f for c in variants) != 3 for f in GRID):
            raise ValueError("確認候補の階層/件数が不正")
    elif phase != "screen":
        raise ValueError("測定段階が不正")
    result = []
    for candidate in variants:
        for job in JOBS:
            if phase == "pilot" and job not in ("warrior", "wizard"):
                continue
            source = profiles()[candidate["floor"], job]
            for label in ("B", source["selected_c"]):
                row = copy.deepcopy(source)
                row.update(stage6a_profile_id=source["profile_id"], candidate=candidate["id"],
                           profile_id=f"s6b-{candidate['id']}-{job}", evaluation_trials=trials,
                           evaluation_phase=phase, boss_override=copy.deepcopy(candidate["override"]))
                result.append((row, label, 1))
    return result


def evaluation_boss(boss, overrides):
    if not boss.is_boss or boss.floor not in GRID or len(overrides) != 1:
        raise ValueError("重点3階の単一能力候補だけ許可")
    field, value = next(iter(overrides.items()))
    if field not in GRID[boss.floor] or value not in GRID[boss.floor][field] or isinstance(value, bool):
        raise ValueError("事前登録外の能力値")
    clone = copy.copy(boss)
    setattr(clone, field, value)
    return clone


def range_distance(value):
    return max(C_RANGE[0]-value, 0, value-C_RANGE[1])


def selection_metrics(floor, b_rate, c_rate, zero_jobs, gap, boss_actions):
    """C帯内の距離は常に0。交差傾向をこの順位へ混ぜない。"""
    return {"b_center_distance": abs(b_rate-B_TARGET[floor]),
            "c_band_distance": range_distance(c_rate), "c_band_descriptive": C_RANGE[0] <= c_rate <= C_RANGE[1],
            "rate_penalty": abs(b_rate-B_TARGET[floor])+range_distance(c_rate),
            "zero_job_cells": zero_jobs, "max_job_gap": gap, "boss_mean_actions": boss_actions,
            "crossing_b_minus_c": b_rate-c_rate}


def choose_candidates(metrics):
    """各階、率の距離が最小の1候補＋20pt以内で格差を重視する1候補。"""
    selected, reasons = [], []
    for floor in GRID:
        pool = [m for m in metrics if m["floor"] == floor and not m["control"] and m["complete"]]
        if len(pool) < 2:
            raise ValueError("完了した候補が不足")
        first = min(pool, key=lambda m: (m["rate_penalty"], m["zero_job_cells"], m["max_job_gap"], m["candidate"]))
        nearby = [m for m in pool if m is not first and m["rate_penalty"] <= first["rate_penalty"]+.20+1e-9]
        if not nearby:
            nearby = [m for m in pool if m is not first]
        second = min(nearby, key=lambda m: (m["zero_job_cells"], m["max_job_gap"], m["rate_penalty"], m["candidate"]))
        for item, purpose in ((first, "B中心距離+C帯外距離の最小候補"),
                              (second, "最良率候補から20pt以内を優先した職業格差候補")):
            selected.append(item["candidate"])
            reasons.append({"candidate": item["candidate"], "purpose": purpose, "screen_metrics": item})
    return {"selected": selected, "reasons": reasons,
            "policy": "C25〜60%はすべて帯外距離0。C参考線と交差傾向は順位から除外。全敗職と最大格差を別評価。"}


def seed_check():
    wanted = {SEEDS["pilot"]} | set(range(SEEDS["screen"], SEEDS["screen"]+5)) | set(range(SEEDS["confirm"], SEEDS["confirm"]+15))
    count = 0
    for path in HERE.rglob("runs.jsonl"):
        if OUTPUT in path.parents:
            continue
        count += 1
        for line in path.open():
            if line.strip() and json.loads(line)["seed"] in wanted:
                raise ValueError(f"過去seedと重複: {path}")
    return {"searched_journals": count, "unused_seeds": sorted(wanted)}


def estimate(rows, pilot=None, screen=None):
    observed = defaultdict(list)
    for r in pilot or []:
        if not r.get("exception"):
            observed[r["candidate"], r["job"], r["tactic"]].append(r["elapsed_seconds"])
    for r in screen or []:
        if not r.get("exception"):
            observed[r["candidate"], r["job"], r["tactic"]].append(r["elapsed_seconds"])
    old = defaultdict(list)
    for line in (SOURCE / "runs.jsonl").open():
        r = json.loads(line)
        if r.get("growth_version") == "new" and not r.get("exception"):
            old[r["floor"], r["job"], r["tactic"]].append(r["elapsed_seconds"])
    total = 0
    for row, label, _ in rows:
        actual = observed[row["candidate"], row["job"], label]
        if actual:
            seconds = max(actual)*2
        else:
            factor = max(2, row["boss_override"].get("max_hp", {8: 50000, 7: 29000, 12: 156924}[row["floor"]]) /
                         {8: 50000, 7: 29000, 12: 156924}[row["floor"]]*2)
            if "agility" in row["boss_override"]:
                factor = max(factor, 4)
            seconds = statistics.mean(old[row["floor"], row["job"], label])*factor*1.25
        total += seconds*row["evaluation_trials"]
    return {"conditions": len(rows), "battles": sum(r["evaluation_trials"] for r, _, _ in rows),
            "estimated_battle_seconds": round(total, 3), "setup_allowance_seconds": 40,
            "estimated_total_seconds": round(total+40, 3),
            "cost_policy": "同候補実測の最大値×2を優先。未測定は6-A新成長実測×HP比/AGI余裕係数。"}


def execute(output, rows, phase):
    output.mkdir(parents=True, exist_ok=False)
    original_prepare, original_measure, original_teardown = sim.prepare_profile, sim.measure, runner.teardown_databases
    catalog, db_name, active = None, None, None
    def prepare(row, label, scale):
        nonlocal catalog, db_name, active
        sim.require_isolation()
        if catalog is None:
            catalog = previous.catalog()
            frozen = json.loads((SOURCE / "official_catalog.json").read_text())
            if catalog != frozen:
                raise ValueError("6-Aの正式ボス/技能カタログと不一致")
            db_name = sim.connection.settings_dict["NAME"]
            previous.write_json(output / "official_catalog.json", catalog)
        active = row
        character = original_prepare(row, label, scale)
        if character.legacy_reincarnation_points != 0:
            raise ValueError("保護分の混在")
        return character
    def measure(character, boss, seed, **kwargs):
        record = original_measure(character, boss, seed, detail=True)
        diagnostics = previous.diagnostic(record)
        for side in ("player", "boss"):
            uses = [v for v in record["remaining_uses"][side].values() if v is not None]
            diagnostics[side]["all_active_exhausted"] = bool(uses) and all(v == 0 for v in uses)
        record.update(candidate=active["candidate"], phase=phase, growth_version="new", diagnostics=diagnostics,
                      evaluation_full_boss={f.attname: getattr(boss, f.attname) for f in Enemy._meta.concrete_fields},
                      profile_stats=active["stats"], profile_attributes=active["attributes"],
                      combat_start=active["combat_start"], display_power=active["power"])
        return record
    def teardown(*args, **kwargs):
        try:
            if catalog is not None:
                with sim.authorized_database(db_name):
                    unchanged = previous.catalog() == catalog
                previous.write_json(output / "official_catalog_unchanged.json", {"unchanged": unchanged})
                if not unchanged:
                    raise AssertionError("正式ボス/スキルが変更された")
        finally:
            original_teardown(*args, **kwargs)
    previous.write_json(output / "study_metadata.json", {
        "phase": phase, "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "source_stage6a": str(SOURCE.relative_to(ROOT)),
        "source_stage6a_manifest_sha256": hashlib.sha256((SOURCE / "manifest.json").read_bytes()).hexdigest(),
        "wrapper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "legacy_reincarnation_points": 0, "b_targets": B_TARGET, "c_reference": C_REFERENCE,
        "c_permitted_band_focus_floors": C_RANGE, "c_at_12_is_range_not_target": True,
        "crossing_is_separate_not_selection_requirement": True,
        "seed_check": seed_check(), "candidates": candidates(), "max_seconds": LIMITS[phase],
    })
    started = time.perf_counter()
    with (output / "execution.log").open("x") as log, \
         patch.object(runner, "cases", return_value=iter(rows)), \
         patch.object(previous.balance_stage5b, "evaluation_boss", evaluation_boss), \
         patch.object(sim, "prepare_profile", prepare), patch.object(sim, "measure", measure), \
         patch.object(runner, "teardown_databases", teardown):
        try:
            previous.call_command("simulate_boss_v2", isolated_test_db=True, output=str(output), trials=5,
                                  seed_base=SEEDS[phase], max_battles=4000, max_seconds=LIMITS[phase],
                                  plan=False, seconds_per_battle=None, detail=True, stdout=previous.Tee(log))
        finally:
            previous.write_json(output / "elapsed.json", {"wall_seconds": time.perf_counter()-started})


def records(path):
    return [json.loads(line) for line in path.open()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "pilot", "screen", "select", "confirm"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    out = args.output
    if args.mode == "plan":
        out.mkdir(parents=True, exist_ok=True)
        plan = {"screen": estimate(scenarios("screen")), "pilot": estimate(scenarios("pilot")),
                "confirm_max_conditions": 126, "confirm_max_battles": 1890,
                "confirm_trials": 15, "screen_trials": 5, "limits": LIMITS, "seeds": SEEDS,
                "seed_check": seed_check(), "candidates": candidates(), "b_targets": B_TARGET,
                "c_reference": C_REFERENCE, "c_band_focus": C_RANGE,
                "selection_policy": "率距離最良1候補+率距離20pt以内を優先した格差1候補/階。C帯内は距離0。交差を点数化しない。"}
        previous.write_json(out / "initial_plan.json", plan)
        print(json.dumps(plan, ensure_ascii=False), flush=True)
    elif args.mode == "pilot":
        if not (out / "initial_plan.json").exists():
            raise RuntimeError("先にplanを実行")
        execute(out / "pilot", scenarios("pilot"), "pilot")
    elif args.mode == "screen":
        pilot = records(out / "pilot/runs.jsonl")
        if len(pilot) != 40 or any(r.get("exception") for r in pilot):
            raise RuntimeError("pilot未完了/例外")
        rows = scenarios("screen")
        plan = estimate(rows, pilot=pilot)
        if plan["estimated_total_seconds"] > LIMITS["screen"]:
            rows = scenarios("screen", trials=3)
            plan = estimate(rows, pilot=pilot)
        previous.write_json(out / "screen_plan.json", plan)
        print(json.dumps(plan, ensure_ascii=False), flush=True)
        if plan["estimated_total_seconds"] > LIMITS["screen"]:
            raise RuntimeError("均等3seedでも上限超過")
        execute(out / "screen", rows, "screen")
    elif args.mode == "select":
        report = previous.load_module("stage6b_select_report", HERE / "BALANCE_STAGE6B_REPORT.py")
        data = report.phase_summary(out / "screen")
        selection = choose_candidates(data["candidates"])
        previous.write_json(out / "selection.json", selection)
        print(json.dumps(selection, ensure_ascii=False), flush=True)
    else:
        selection = json.loads((out / "selection.json").read_text())["selected"]
        screen = records(out / "screen/runs.jsonl")
        trials = 15
        rows = scenarios("confirm", trials=trials, selected=selection)
        plan = estimate(rows, screen=screen)
        if plan["estimated_total_seconds"] > LIMITS["confirm"]:
            trials = 10
            rows = scenarios("confirm", trials=trials, selected=selection)
            plan = estimate(rows, screen=screen)
        plan["trials_per_condition"] = trials
        previous.write_json(out / "confirm_plan.json", plan)
        print(json.dumps(plan, ensure_ascii=False), flush=True)
        if plan["estimated_total_seconds"] > LIMITS["confirm"]:
            raise RuntimeError("確認10seedでも時間上限超過")
        execute(out / "confirm", rows, "confirm")


if __name__ == "__main__":
    main()
