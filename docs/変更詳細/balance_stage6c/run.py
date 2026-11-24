"""Stage6-C: タイタンのAGI×HP実測。スキル構成は固定、値はメモリ上コピー限定。"""
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
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base = load("stage6c_base", HERE.parent / "BALANCE_STAGE6B_RUN.py")
trace = load("stage6c_trace", HERE / "observe.py")
ROOT, sim, runner, Enemy = base.ROOT, base.sim, base.runner, base.Enemy
AGIS, HPS = (180, 900, 1800, 2700, 3600), (50000, 100000, 150000, 200000)
CONTROL = {"max_hp": 50000, "agility": 180}
SKILLS = ["steel_body", "solid_stance", "counter_stance", "shock_wave", "true_fist"]
SEEDS = {"pilot": 31061120, "screen": 32061120, "refine": 33061120, "confirm": 34061120}
LIMITS = {"pilot": 180, "screen": 660, "refine": 360, "confirm": 600}
JOBS = base.JOBS


def cid(hp, agi):
    return f"hp{hp}-agi{agi}"


def grid():
    return [{"id": cid(h, a), "hp": h, "agi": a} for a in AGIS for h in HPS]


def write_json(path, data):
    base.previous.write_json(path, data)


@lru_cache(maxsize=1)
def profiles():
    return {job: copy.deepcopy(base.profiles()[8, job]) for job in JOBS}


def scenarios(phase, trials=5, variants=None):
    variants = variants if variants is not None else grid()
    result = []
    for variant in variants:
        for job, source in profiles().items():
            if phase == "pilot" and job not in ("warrior", "priest"):
                continue
            for label in ("B", source["selected_c"]):
                row = copy.deepcopy(source)
                row.update(stage6a_profile_id=source["profile_id"], candidate=variant["id"],
                           profile_id=f"s6c-{variant['id']}-{job}", evaluation_phase=phase,
                           evaluation_trials=1 if phase == "pilot" else trials,
                           boss_override={"max_hp": variant["hp"], "agility": variant["agi"]})
                result.append((row, label, 1))
    return result


def evaluation_boss(boss, overrides, variants=None):
    allowed = {(v["hp"], v["agi"]) for v in (grid() if variants is None else variants)}
    if not boss.is_boss or boss.floor != 8 or set(overrides) != {"max_hp", "agility"}:
        raise ValueError("タイタンのHP/AGIの完全指定だけ許可")
    values = (overrides["max_hp"], overrides["agility"])
    if any(isinstance(v, bool) or not isinstance(v, int) for v in values) or values not in allowed:
        raise ValueError("事前計画外の組合せ")
    clone = copy.copy(boss)
    for k, value in overrides.items():
        setattr(clone, k, value)
    if clone.skill_codes != SKILLS:
        raise ValueError("スキル構成/順序が固定値と異なります")
    return clone


def seed_check():
    wanted = {SEEDS["pilot"]}
    for phase, n in (("screen", 5), ("refine", 5), ("confirm", 15)):
        wanted.update(range(SEEDS[phase], SEEDS[phase]+n))
    searched = 0
    for p in HERE.parent.rglob("runs.jsonl"):
        if HERE in p.parents:
            continue
        searched += 1
        for line in p.open():
            if line.strip() and json.loads(line)["seed"] in wanted:
                raise ValueError(f"過去のseedと重複: {p}")
    return {"searched_journals": searched, "unused_seeds": sorted(wanted)}


def records(path):
    return [json.loads(line) for line in path.open()]


def estimate(rows, observed=()):
    times, combo = defaultdict(list), defaultdict(list)
    for r in observed:
        if not r.get("exception"):
            times[r["candidate"], r["job"], r["tactic"]].append(r["elapsed_seconds"])
            combo[r["candidate"]].append(r["elapsed_seconds"])
    old = defaultdict(list)
    for r in records(base.OUTPUT / "screen/runs.jsonl"):
        if r["floor"] == 8 and not r.get("exception"):
            old[r["job"], r["tactic"]].append(r["elapsed_seconds"])
    total, by_combo = 0, defaultdict(float)
    for row, label, _ in rows:
        exact = times[row["candidate"], row["job"], label]
        if exact:
            cost = max(exact)*2
        elif combo[row["candidate"]]:
            cost = max(combo[row["candidate"]])*2
        else:
            # 過去の時間だけを参考にする。勝率の加算/推定には使わない。
            cost = statistics.mean(old[row["job"], label])*2.5
        value = cost*row["evaluation_trials"]
        total += value
        by_combo[row["candidate"]] += value
    return {"conditions": len(rows), "battles": sum(r["evaluation_trials"] for r, _, _ in rows),
            "estimated_battle_seconds": round(total, 3), "setup_allowance_seconds": 40,
            "estimated_total_seconds": round(total+40, 3), "by_combination_seconds": dict(by_combo),
            "policy": "同条件実測最大×2、未測定職は同組合せpilot最大×2。実測なしは6-Bタイタン実測時間×2.5。"}


def execute(output, rows, phase, variants):
    output.mkdir(parents=True, exist_ok=False)
    original_prepare, original_measure, original_teardown = sim.prepare_profile, sim.measure, runner.teardown_databases
    catalog, name, active = None, None, None
    def prepare(row, label, scale):
        nonlocal catalog, name, active
        sim.require_isolation()
        if catalog is None:
            catalog = base.previous.catalog()
            if catalog != json.loads((base.SOURCE / "official_catalog.json").read_text()):
                raise ValueError("6-A/Bの正式カタログと不一致")
            name = sim.connection.settings_dict["NAME"]
            write_json(output / "official_catalog.json", catalog)
        active = row
        c = original_prepare(row, label, scale)
        if c.legacy_reincarnation_points != 0:
            raise ValueError("保護分の混在")
        return c
    def measure(c, boss, seed, **kwargs):
        # 再帰を避け、既存sim.measureを元関数へ一時接続した状態で詳細観測する。
        with patch.object(sim, "measure", original_measure):
            r = trace.measure(sim, c, boss, seed)
        r.update(candidate=active["candidate"], phase=phase, growth_version="new",
                 diagnostics=base.previous.diagnostic(r),
                 evaluation_full_boss={f.attname: getattr(boss, f.attname) for f in Enemy._meta.concrete_fields},
                 profile_stats=active["stats"], profile_attributes=active["attributes"],
                 combat_start=active["combat_start"], display_power=active["power"])
        return r
    def teardown(*args, **kwargs):
        try:
            if catalog is not None:
                with sim.authorized_database(name):
                    unchanged = base.previous.catalog() == catalog
                write_json(output / "official_catalog_unchanged.json", {"unchanged": unchanged})
                if not unchanged:
                    raise AssertionError("正式ボス/技能が変更された")
        finally:
            original_teardown(*args, **kwargs)
    write_json(output / "study_metadata.json", {
        "phase": phase, "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "seed_check": seed_check(), "variants": variants, "fixed_skill_order": SKILLS,
        "fixed_skill_uses": 99, "b_center": .35, "c_permitted": [.25, .60],
        "c_reference_not_point_target": True, "c_inside_band_has_zero_distance": True,
        "legacy_reincarnation_points": 0, "max_seconds": LIMITS[phase],
        "source_stage6a_sha256": hashlib.sha256((base.SOURCE / "manifest.json").read_bytes()).hexdigest(),
        "source_stage6b_screen_sha256": hashlib.sha256((base.OUTPUT / "screen/runs.jsonl").read_bytes()).hexdigest(),
        "source_stage6b_confirm_sha256": hashlib.sha256((base.OUTPUT / "confirm/runs.jsonl").read_bytes()).hexdigest(),
        "script_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), HERE / "observe.py")}})
    began = time.perf_counter()
    with (output / "execution.log").open("x") as log, \
         patch.object(runner, "cases", return_value=iter(rows)), \
         patch.object(base.previous.balance_stage5b, "evaluation_boss", side_effect=lambda b, o: evaluation_boss(b, o, variants)), \
         patch.object(sim, "prepare_profile", prepare), patch.object(sim, "measure", measure), \
         patch.object(runner, "teardown_databases", teardown):
        try:
            base.previous.call_command("simulate_boss_v2", isolated_test_db=True, output=str(output), trials=5,
                seed_base=SEEDS[phase], max_battles=4000, max_seconds=LIMITS[phase],
                plan=False, seconds_per_battle=None, detail=True, stdout=base.previous.Tee(log))
        finally:
            write_json(output / "elapsed.json", {"wall_seconds": time.perf_counter()-began})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "pilot", "screen", "select", "refine", "confirm"))
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    out = args.output
    if args.mode == "plan":
        out.mkdir(parents=True, exist_ok=True)
        value = {"grid": grid(), "pilot": estimate(scenarios("pilot")), "screen": estimate(scenarios("screen")),
                 "limits": LIMITS, "seeds": SEEDS, "seed_check": seed_check(),
                 "refine_limit": "実測に基づく中間値は最大4点。正式値と比較基準1点を同じseedで併測。",
                 "confirm_limit": "最大3候補＋正式値、全職・B/C共通。15/12/10/9/8/5追加seedから時間内の最大を選ぶ。",
                 "selection": "B中心距離+C帯外距離、帯内Cは同点。最良から20pt以内で全敗職/最大格差/全枯渇/脅威攻撃到達を別に比較。交差を強制しない。"}
        write_json(out / "initial_plan.json", value)
        print(json.dumps(value, ensure_ascii=False), flush=True)
        return
    if args.mode == "pilot":
        if not (out / "initial_plan.json").exists():
            raise RuntimeError("先にplanを実行")
        execute(out / "pilot", scenarios("pilot"), "pilot", grid())
        return
    if args.mode == "screen":
        pilot = records(out / "pilot/runs.jsonl")
        if len(pilot) != 80 or any(r.get("exception") for r in pilot):
            raise RuntimeError("pilot未完了/例外")
        for n in (5, 3):
            rows = scenarios("screen", trials=n)
            value = estimate(rows, pilot)
            if value["estimated_total_seconds"] <= LIMITS["screen"]:
                break
        value["trials"] = n
        write_json(out / "screen_plan_final.json", value)
        print(json.dumps(value, ensure_ascii=False), flush=True)
        if value["estimated_total_seconds"] > LIMITS["screen"]:
            raise RuntimeError("均等3seedでも時間上限超過")
        execute(out / "screen", rows, "screen", grid())
        return
    analysis = load("stage6c_analysis", HERE / "analyze.py")
    if args.mode == "select":
        data = analysis.phase_summary(out / "screen")
        selection = analysis.select(data)
        write_json(out / "selection.json", selection)
        print(json.dumps(selection, ensure_ascii=False), flush=True)
        return
    selection = json.loads((out / "selection.json").read_text())
    if args.mode == "refine":
        variants = selection["refine_variants"]
        if not variants:
            write_json(out / "refine_skipped.json", {"reason": "実測に基づく追加中間候補なし"})
            return
        observed = records(out / "screen/runs.jsonl")
        for n in (5, 3):
            rows = scenarios("refine", trials=n, variants=variants)
            value = estimate(rows, observed)
            if value["estimated_total_seconds"] <= LIMITS["refine"]:
                break
        value["trials"] = n
        write_json(out / "refine_plan.json", value)
        print(json.dumps(value, ensure_ascii=False), flush=True)
        if value["estimated_total_seconds"] > LIMITS["refine"]:
            raise RuntimeError("中間候補の均等3seedでも上限超過")
        execute(out / "refine", rows, "refine", variants)
        return
    data = analysis.phase_summary(out / "screen")
    metrics = list(data["candidates"])
    observed = records(out / "screen/runs.jsonl")
    if (out / "refine").exists():
        refined = analysis.phase_summary(out / "refine")
        # 参考点の新seed結果も保持するが、候補順位は同一段階内の記述値として扱う。
        metrics = [m for m in metrics if m["candidate"] not in {v["candidate"] for v in refined["candidates"]}]+refined["candidates"]
        observed += records(out / "refine/runs.jsonl")
    final = analysis.shortlist(metrics)
    write_json(out / "confirm_selection.json", final)
    variants = [{"id": cid(50000, 180), "hp": 50000, "agi": 180}]+final["variants"]
    for n in (15, 12, 10, 9, 8, 5):
        rows = scenarios("confirm", trials=n, variants=variants)
        value = estimate(rows, observed)
        if value["estimated_total_seconds"] <= LIMITS["confirm"]:
            break
    value.update(trials=n, candidate_count=len(final["variants"]), selection_sha256=hashlib.sha256((out / "confirm_selection.json").read_bytes()).hexdigest())
    write_json(out / "confirm_plan.json", value)
    print(json.dumps(value, ensure_ascii=False), flush=True)
    if value["estimated_total_seconds"] > LIMITS["confirm"]:
        raise RuntimeError("確認5seedでも上限超過")
    execute(out / "confirm", rows, "confirm", variants)


if __name__ == "__main__":
    main()
