"""Stage 6-A: 保存済み条件を固定し、旧/新成長だけを対応比較する。"""
import argparse
from collections import Counter, defaultdict
import copy
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.management import call_command
from django.db import connection
from apps.accounts import growth
from apps.accounts.models import Character
from apps.battle import balance_stage5 as base, balance_stage5b, simulation_v2 as sim
from apps.battle.management.commands import simulate_boss_v2 as runner
from apps.battle.models import Enemy, Skill
from config.views import generate_reincarnation_bonus, calculate_reincarnation_stats

OUTPUT = HERE / "balance_stage6a"
MAIN_SEED, PILOT_SEED = 11061120, 12061121
MAX_SECONDS, PILOT_SECONDS = 600, 180
ARCHIVE = HERE / "balance_stage5a/analysis/profiles.json"
FIXED = ("floor", "job", "race", "reincarnations", "level", "equipment", "equipment_bonuses",
         "permanent_skill_codes", "inheritance_history", "inheritance_remaining", "inheritance_mode",
         "seed", "attribute_weights", "max_st", "start_st")
REPLAY_FIELDS = ("stats", "attributes", "combat_start", "power")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, data):
    with path.open("x") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


@lru_cache(maxsize=1)
def legacy():
    return load_module("stage6_growth_comparison", HERE / "GROWTH_V2_COMPARE.py").old_module()


def regenerate(source, version):
    """最後の回帰を直接再生。モデル保存なし・全SQL禁止・乱数状態復元。"""
    if version not in ("old", "new"):
        raise ValueError("成長方式が不正")
    module, old = sim.baseline_module(), legacy()
    before = random.getstate()
    random.seed(source["seed"])
    c = Character(job=source["job"], race=source["race"], legacy_reincarnation_points=0,
                  max_stamina=source["max_st"], current_stamina=source["start_st"])
    for key, value in source["attribute_weights"].items():
        setattr(c, key + "_growth_weight", value)
    count = source["reincarnations"]
    draws = 0
    try:
        with connection.execute_wrapper(module.no_sql):
            if count:
                c.reincarnation_count = count - 1
                generator = old.generate_reincarnation_bonus if version == "old" else generate_reincarnation_bonus
                calculator = old.calculate_reincarnation_stats if version == "old" else calculate_reincarnation_stats
                for key, value in calculator(generator(c)).items():
                    setattr(c, key, value)
            c.reincarnation_count = count
            while c.level < source["level"]:
                n = c.level
                result = (old.level_up_once if version == "old" else growth.level_up_once)(c)
                expected = 3 if version == "old" else growth.calculate_growth_count(count, n)
                if len(result["stat_growths"]) != expected or len(result["attribute_growths"]) != 3:
                    raise AssertionError("成長抽選数の契約違反")
                draws += expected
            c.current_hp, c.current_mp = c.max_hp, c.max_mp
            gear = (copy.deepcopy(source["equipment"]), copy.deepcopy(source["equipment_bonuses"]),
                    sum(e["power"] for e in source["equipment"]))
            calculated = module.profile(source["floor"], c, source["seed"], source["variant"], gear, source["target_power"])
    finally:
        random.setstate(before)
    row = copy.deepcopy(source)
    for field in REPLAY_FIELDS:
        row[field] = calculated[field]
    if version == "old":
        for field in REPLAY_FIELDS:
            if row[field] != source[field]:
                raise ValueError(f"旧プロフィール再現不一致: {source['profile_id']} {field}")
    row.update(growth_version=version, legacy_reincarnation_points=0,
               initial_points=count*125 if version == "old" else growth.calculate_initial_points(count),
               stat_growth_draws=draws, attribute_growth_draws=3*(c.level-1),
               original_profile_id=source["profile_id"], profile_id=f"s6a-f{source['floor']}-{source['job']}-{version}")
    for key in FIXED:
        if row[key] != source[key]:
            raise AssertionError(f"固定条件の変更: {key}")
    return row


@lru_cache(maxsize=1)
def profile_pairs():
    saved = json.loads(ARCHIVE.read_text())
    eligible = [r for r in saved if r["recommendation_eligible"]]
    current = {r["profile_id"]: r for r in base.profiles()}
    if len(eligible) != 84 or {(r["floor"], r["job"]) for r in eligible} != {
        (f, j) for f in range(1, 13) for j in base.SKILL_CODES
    }:
        raise ValueError("全12階×7職業の保存済み条件が必要")
    # 旧manifestとも照合。旧実績を今回の勝敗として流用しない。
    for filename in ("balance_stage5a/screen_confirmed/manifest.json",
                     "balance_stage5b/screen_confirmed/manifest.json",
                     "balance_stage5c_v2/screen_confirmed/manifest.json"):
        for case in json.loads((HERE / filename).read_text())["cases"]:
            r = case["profile"]
            original = r.get("original_profile_id", r["profile_id"])
            if original in current:
                for key in FIXED + REPLAY_FIELDS:
                    if r[key] != current[original][key]:
                        raise ValueError(f"旧manifestの固定条件不一致: {filename} {key}")
    pairs = []
    for source in sorted(eligible, key=lambda r: (r["floor"], list(base.SKILL_CODES).index(r["job"]))):
        if source != current[source["profile_id"]]:
            # JSONはtupleをlistへ変換するため正規化して比較する。
            if source != json.loads(json.dumps(current[source["profile_id"]])):
                raise ValueError("保存プロフィールと現評価条件が不一致")
        old, new = regenerate(source, "old"), regenerate(source, "new")
        allowed = set(base.SKILL_CODES[source["job"]]) | set(source["permanent_skill_codes"])
        legal_c2 = source["job"] in ("wizard", "priest") and all(c in allowed for c, _ in balance_stage5b.C2)
        for row in (old, new):
            row["tactics"] = {"B": source["tactics"]["B"], "C1": source["tactics"]["C"]}
            if legal_c2:
                row["tactics"]["C2"] = list(balance_stage5b.C2)
            row["selected_c"] = "C2" if legal_c2 else "C1"
            base.validate_profile(row)
        pairs.append((old, new))
    return pairs


def scenarios(trials=5, pilot=False):
    if trials not in (3, 5):
        raise ValueError("全条件で均等に3または5seedを使用")
    result = []
    for old, new in profile_pairs():
        if pilot and not (old["floor"] in (7, 8, 9, 10, 11, 12) and old["job"] in ("warrior", "wizard")):
            continue
        for label in ("B", old["selected_c"]):
            for source in (old, new):
                row = copy.deepcopy(source)
                row["evaluation_trials"] = 1 if pilot else trials
                result.append((row, label, 1))
    return result


def assert_unused_seeds():
    wanted = set(range(MAIN_SEED, MAIN_SEED+5)) | {PILOT_SEED}
    files, used = 0, set()
    for filename in HERE.rglob("runs.jsonl"):
        if OUTPUT in filename.parents:
            continue
        files += 1
        with filename.open() as f:
            for line in f:
                if line.strip():
                    seed = json.loads(line)["seed"]
                    if seed in wanted:
                        used.add(seed)
    if used:
        raise ValueError(f"過去の戦闘seedと重複: {sorted(used)}")
    return {"searched_run_files": files, "unused_seeds": sorted(wanted)}


def historical_timing():
    timing = defaultdict(list)
    for directory in ("balance_stage5a/screen_confirmed", "balance_stage5b/screen_confirmed",
                      "balance_stage5c_v2/screen_confirmed", "simulation_v2/pilot_standard"):
        for line in (HERE / directory / "runs.jsonl").open():
            r = json.loads(line)
            if r.get("exception"):
                continue
            timing[r["floor"], r["job"], "B" if r["tactic"] == "B" else "C"].append(r["elapsed_seconds"])
    return timing


def plan(trials=5, pilot_records=None):
    timing = historical_timing()
    observed = defaultdict(list)
    for r in pilot_records or []:
        if not r.get("exception"):
            observed[r["floor"], r["job"], r["tactic"], r["growth_version"]].append(r["elapsed_seconds"])
    estimated = 0
    estimates = defaultdict(float)
    fallbacks = set()
    for row, label, _ in scenarios(trials):
        samples = observed[row["floor"], row["job"], label, row["growth_version"]]
        if samples:
            cost = max(samples) * 2  # 一試行しかないpilotには2倍の余裕。
        else:
            values = timing[row["floor"], row["job"], "B" if label == "B" else "C"]
            if not values:
                values = timing[row["floor"], row["job"], "B"]
                fallbacks.add((row["floor"], row["job"], label, "同階/職業の旧予備B実測×追加1.5"))
                if not values:
                    raise ValueError("時間予測の参照測定がありません")
                values = [v * 1.5 for v in values]
            cost = statistics.mean(values) * (2 if row["growth_version"] == "new" else 1.5)
        estimated += cost * trials
        estimates[row["floor"]] += cost * trials
    return {"conditions": 336, "trials": trials, "battles": 336*trials,
            "estimated_battle_seconds": round(estimated, 3), "setup_allowance_seconds": 40,
            "estimated_total_seconds": round(estimated+40, 3), "max_seconds": MAX_SECONDS,
            "estimated_seconds_by_floor": dict(estimates), "pilot_observations": len(pilot_records or []),
            "timing_fallbacks": sorted(fallbacks),
            "seed_base": MAIN_SEED, "pilot_seed": PILOT_SEED,
            "time_limit_note": "既存ランナーの戦闘間上限。単一戦闘は既存1000ループ上限。DB破棄時間は別。",
            "legacy_reincarnation_points": 0}


def catalog():
    sim.require_isolation()
    bosses = list(Enemy.objects.filter(is_boss=True).order_by("floor").values())
    if len(bosses) != 12 or [b["floor"] for b in bosses] != list(range(1, 13)):
        raise ValueError("正式ボス12体が必要")
    # 正式migrationとの一致。前回の未採用Ver.2案はインポートしない。
    import importlib
    official = importlib.import_module("apps.battle.migrations.0017_boss_balance_v1").BOSSES
    for b in bosses:
        for key, value in official[b["floor"]].items():
            if b[key] != value:
                raise ValueError(f"正式migrationと隔離DBの不一致: {b['floor']} {key}")
    return {"bosses": bosses, "skills": list(Skill.objects.order_by("code").values())}


def diagnostic(record):
    result = {}
    for side in ("player", "boss"):
        moves = [a for a in record["actions"] if a["side"] == side]
        healing = [e for e in record["hp_events"] if e["kind"] == "heal" and e["target"] == side]
        first = next((a for a in moves if a["code"] == "healing_shield"), None)
        result[side] = {"healing_actions": sum(a["code"] in ("healing_shield", "short_rest") for a in moves),
                        "actual_healing_events": len(healing),
                        "first_heal_action": moves.index(first)+1 if first else None,
                        "first_heal_tick": first["tick"] if first else None,
                        "first_heal_hp": first["before"]["hp"] if first else None,
                        "exhausted_slots": [k for k, v in record["remaining_uses"][side].items() if v == 0],
                        "first_six": [a["code"] for a in moves[:6]]}
    result["both_hp_zero"] = all(record["final"][s]["hp"] == 0 for s in ("player", "boss"))
    return result


class Tee:
    def __init__(self, file):
        self.file = file
    def write(self, value):
        sys.stdout.write(value)
        self.file.write(value)
        self.flush()
    def flush(self):
        sys.stdout.flush()
        self.file.flush()
    def isatty(self):
        return False


def execute(output, rows, seed, max_seconds):
    output.mkdir(parents=True, exist_ok=False)
    original_prepare, original_measure, original_teardown = sim.prepare_profile, sim.measure, runner.teardown_databases
    initial_catalog = None
    active = None
    isolated_name = None

    def prepare(row, label, scale):
        nonlocal initial_catalog, active, isolated_name
        if row.get("boss_override"):
            raise ValueError("ボス上書き禁止")
        if initial_catalog is None:
            isolated_name = connection.settings_dict["NAME"]
            initial_catalog = catalog()
            write_json(output / "official_catalog.json", initial_catalog)
        active = row
        character = original_prepare(row, label, scale)
        if character.legacy_reincarnation_points != 0:
            raise AssertionError("保護ポイントの混在")
        return character

    def measure(character, boss, battle_seed, **kwargs):
        record = original_measure(character, boss, battle_seed, detail=True)
        record.update(growth_version=active["growth_version"],
                      diagnostics=diagnostic(record),
                      evaluation_full_boss=next(b for b in initial_catalog["bosses"] if b["floor"] == boss.floor),
                      profile_stats=active["stats"], profile_attributes=active["attributes"],
                      combat_start=active["combat_start"], display_power=active["power"])
        return record

    def teardown(*args, **kwargs):
        try:
            if initial_catalog is not None:
                # 既存ランナーはauthorized_databaseを抜けてからteardownを呼ぶ。
                # 準備時に記録した専用DBと接続先が一致する場合だけ再認可する。
                with sim.authorized_database(isolated_name):
                    unchanged = catalog() == initial_catalog
                write_json(output / "official_catalog_unchanged.json", {"unchanged": unchanged})
                if not unchanged:
                    raise AssertionError("正式ボス/スキルDBが変更された")
        finally:
            original_teardown(*args, **kwargs)

    write_json(output / "study_metadata.json", {
        "started_jst": "2026-11-20", "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "main_verified_sha": "28a2d22b4d9e3bfd7221f221708d1e1980849ab9", "old_head": "caf9664",
        "legacy_growth_sha256": legacy().source_sha256,
        "archive": str(ARCHIVE.relative_to(ROOT)), "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "growth_scope": "新規育成・legacy=0。最後の回帰と最終周の固定職業Lv成長の直接再生。過去周の育成時間は対象外。",
        "observation": "全戦のactions/hp_events/state_eventsを保存。戦闘中SELECT以外を拒否。",
        "fixed_fields": FIXED, "seed_check": assert_unused_seeds(),
    })
    began = time.perf_counter()
    with (output / "execution.log").open("x") as log, \
         patch.object(runner, "cases", return_value=iter(rows)), \
         patch.object(sim, "prepare_profile", prepare), patch.object(sim, "measure", measure), \
         patch.object(runner, "teardown_databases", teardown):
        try:
            call_command("simulate_boss_v2", isolated_test_db=True, output=str(output), trials=5,
                         seed_base=seed, max_battles=1680, max_seconds=max_seconds,
                         plan=False, seconds_per_battle=None, detail=True, stdout=Tee(log))
        finally:
            write_json(output / "elapsed.json", {"wall_seconds_including_teardown": time.perf_counter()-began})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--pilot-name", default="pilot_confirmed")
    args = parser.parse_args()
    if sum((args.plan, args.pilot, args.run)) != 1:
        parser.error("--plan / --pilot / --runのいずれか一つを指定")
    if args.plan:
        args.output.mkdir(parents=True, exist_ok=True)
        result = plan() | {"seed_check": assert_unused_seeds(), "pilot_conditions": 48, "pilot_battles": 48,
                           "pilot_max_seconds": PILOT_SECONDS}
        write_json(args.output / "initial_plan.json", result)
        print(json.dumps(result, ensure_ascii=False))
    elif args.pilot:
        if not (args.output / "initial_plan.json").exists():
            raise RuntimeError("先に--planを実行")
        execute(args.output / args.pilot_name, scenarios(pilot=True), PILOT_SEED, PILOT_SECONDS)
    else:
        pilot = [json.loads(line) for line in (args.output / args.pilot_name / "runs.jsonl").open()]
        if len(pilot) != 48 or any(r.get("exception") for r in pilot):
            raise RuntimeError("pilotが未完了/例外あり。計画の再確認が必要")
        result = plan(pilot_records=pilot)
        if result["estimated_total_seconds"] > MAX_SECONDS:
            result = plan(trials=3, pilot_records=pilot)
        write_json(args.output / "execution_plan.json", result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if result["estimated_total_seconds"] > MAX_SECONDS:
            raise RuntimeError("均等3seedでも上限超過")
        execute(args.output / "measurement", scenarios(result["trials"]), MAIN_SEED, MAX_SECONDS)


if __name__ == "__main__":
    main()
