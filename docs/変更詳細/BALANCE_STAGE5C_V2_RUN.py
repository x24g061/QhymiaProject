"""ユーザー指定ボス能力値Ver.2の全変更階層比較。正式値には保存しない。"""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.management import call_command
from apps.battle import balance_stage5 as base, balance_stage5b as previous, simulation_v2 as sim
from apps.battle.management.commands import simulate_boss_v2 as runner
from apps.battle.models import Enemy

SEED = 90361118
FLOORS = (1, 2, 5, 6, 7, 8, 11, 12)
FIELDS = ("max_hp", "max_mp", "strength", "intelligence", "dexterity", "agility", "vitality", "luck", "max_stamina")
CATALOG_FIELDS = ("floor", "name", "attribute", *FIELDS, "skill_codes")
CORE = ("job", "race", "level", "reincarnations", "stats", "attributes", "equipment", "attribute_weights",
        "permanent_skill_codes", "combat_start", "inheritance_history", "inheritance_remaining", "max_st", "start_st")
TABLE = [
    (1, "キングスライム", "water", 80, 10, 15, 8, 12, 15, 10, 6, 100),
    (2, "グレートウルフ", "neutral", 390, 0, 30, 8, 55, 75, 10, 21, 130),
    (3, "グランドゴーレム", "rock", 1060, 0, 90, 15, 30, 17, 115, 13, 160),
    (4, "ケイブドラゴン", "dark", 2000, 150, 135, 85, 82, 65, 110, 65, 180),
    (5, "イフリート", "fire", 4600, 220, 300, 125, 130, 100, 150, 90, 200),
    (6, "リヴァイアサン", "water", 9600, 500, 999, 900, 420, 150, 530, 260, 240),
    (7, "アルラウネ", "grass", 29000, 7000, 580, 2000, 630, 500, 750, 470, 270),
    (8, "タイタン", "rock", 59000, 4600, 1286, 670, 600, 900, 3100, 380, 310),
    (9, "イグニス", "fire", 67777, 15000, 2600, 1800, 1850, 2150, 1650, 1280, 320),
    (10, "アビスデーモン", "dark", 114514, 28000, 3900, 4100, 2400, 1800, 2200, 1750, 340),
    (11, "セレスティア", "light", 135672, 41000, 3200, 6000, 2950, 2150, 2800, 7777, 370),
    (12, "アポカリプス", "neutral", 166666, 66666, 6666, 6666, 4150, 3400, 4500, 3450, 400),
]
NEW = {r[0]: dict(zip(CATALOG_FIELDS[:-1], r)) for r in TABLE}


def scenarios(trials=5):
    """旧/新を隣接させ、時間上限時も早期に対応比較を得る。"""
    profiles = {(r["floor"], r["job"]): r for r in base.profiles() if r["recommendation_eligible"]}
    result = []
    for floor in FLOORS:
        for job in base.SKILL_CODES:
            source = profiles[floor, job]
            allowed = set(base.SKILL_CODES[job]) | set(source["permanent_skill_codes"])
            legal_c2 = job in ("wizard", "priest") and all(code in allowed for code, _ in previous.C2)
            for label in ("B", "C2" if legal_c2 else "C1"):
                for version in ("old", "v2"):
                    row = copy.deepcopy(source)
                    row["original_profile_id"] = row["profile_id"]
                    row.update(profile_id=f"v5cv2-f{floor}-{job}-{version}", evaluation_version=version,
                               evaluation_trials=trials,
                               boss_override={k: NEW[floor][k] for k in ("attribute", *FIELDS)} if version == "v2" else {})
                    row["tactics"] = {"B": source["tactics"]["B"], "C1": source["tactics"]["C"]}
                    if legal_c2:
                        row["tactics"]["C2"] = list(previous.C2)
                    base.validate_profile(row)
                    result.append((row, label, 1))
    return result


def compare_catalog(actual):
    """実DBの全12体を照合。想定外なら戦闘を開始しない。"""
    old = {r["floor"]: r for r in actual}
    if len(actual) != 12 or set(old) != set(NEW):
        raise ValueError("隔離DBのボス階層/件数が想定と異なります")
    differences = {floor: {key: {"old": old[floor][key], "v2": value}
                          for key, value in NEW[floor].items() if old[floor][key] != value}
                   for floor in NEW}
    changed = [floor for floor, diff in differences.items() if diff]
    expected = importlib.import_module("apps.battle.migrations.0017_boss_balance_v1").BOSSES
    unexpected = {floor: {k: {"expected": v, "actual": old[floor][k]} for k, v in expected[floor].items()
                         if old[floor][k] != v} for floor in old}
    ok = changed == list(FLOORS) and not any(unexpected.values())
    ok = ok and all(old[f][k] == NEW[f][k] for f in NEW for k in ("name", "attribute", "max_stamina"))
    return {"status": "matched" if ok else "unexpected_difference", "old": actual,
            "new": list(NEW.values()), "differences": differences, "changed_floors": changed,
            "unexpected_baseline": unexpected}


def evaluation_boss(boss, overrides):
    expected = {k: NEW[boss.floor][k] for k in ("attribute", *FIELDS)} if boss.floor in FLOORS else None
    if not boss.is_boss or not overrides or overrides != expected:
        raise ValueError("ユーザー指定Ver.2の完全値以外を拒否")
    result = copy.copy(boss)
    for field, value in overrides.items():
        setattr(result, field, value)
    return result


def diagnostic(record):
    attack_codes = {"normal", "double_punch", "shock_wave", "rapid_barrage", "true_fist", "flare_blade",
                    "one_hit_kill", "rapid_shot", "sleep_arrow", "poison_arrow", "stella", "fire", "megido",
                    "explosion", "judgement", "anti_jail", "strike_core", "surprise_attack", "poison_dagger"}
    result = {}
    for side in ("player", "boss"):
        moves = [a for a in record["actions"] if a["side"] == side]
        counts = Counter(a["code"] for a in moves)
        events = [e for e in record["hp_events"] if e["source"] == side and e["target"] != side and e["kind"] != "heal"]
        damage = Counter()
        for e in events:
            damage[e["skill"] or e["kind"]] += e["amount"]
        result[side] = {"direct_attack_actions": sum(v for k, v in counts.items() if k in attack_codes),
                        "support_actions": sum(v for k, v in counts.items() if k not in attack_codes | {"skip", "status_skip"}),
                        "direct_damage": sum(e["amount"] for e in events if e["kind"] in ("normal", "skill")),
                        "damage_by_skill": dict(damage), "first_six": [a["code"] for a in moves[:6]]}
    first_player = next((i for i, a in enumerate(record["actions"]) if a["side"] == "player"), len(record["actions"]))
    result["boss_actions_before_player_first"] = sum(a["side"] == "boss" for a in record["actions"][:first_player])
    result["both_hp_zero"] = all(record["final"][s]["hp"] == 0 for s in ("player", "boss"))
    return result


def plan(trials=5):
    rows = scenarios(trials)
    timing = defaultdict(list)
    a = ROOT / "docs/変更詳細/balance_stage5a/screen_confirmed"
    eligible = {c["profile"]["profile_id"] for c in json.loads((a / "manifest.json").read_text())["cases"] if c["profile"]["recommendation_eligible"]}
    for line in (a / "runs.jsonl").open():
        r = json.loads(line)
        if r["profile_id"] in eligible:
            timing[r["floor"], r["job"], "B" if r["tactic"] == "B" else "C1"].append(r["elapsed_seconds"])
    # C2は5-Bの元値測定を優先し、C1の時間からの推測を避ける。
    b = ROOT / "docs/変更詳細/balance_stage5b/screen_confirmed"
    bm = json.loads((b / "manifest.json").read_text())
    controls = {c["profile"]["profile_id"] for c in bm["cases"] if not c["profile"]["boss_override"]}
    for line in (b / "runs.jsonl").open():
        r = json.loads(line)
        if r["tactic"] == "C2" and r["profile_id"] in controls:
            timing[r["floor"], r["job"], "C2"].append(r["elapsed_seconds"])
    fallbacks = set()
    pilot = defaultdict(list)
    for line in (ROOT / "docs/変更詳細/simulation_v2/pilot_standard/runs.jsonl").open():
        r = json.loads(line)
        pilot[r["floor"], r["job"]].append(r["elapsed_seconds"])
    def cost(row, label):
        values = timing[row["floor"], row["job"], label]
        extra = 1
        if not values and label == "C2" and timing[row["floor"], row["job"], "C1"]:
            values = timing[row["floor"], row["job"], "C1"]
            extra = 1.25
            fallbacks.add((row["floor"], row["job"], "C1実測×1.25"))
        if not values:
            values = pilot[row["floor"], row["job"]]
            extra = 1.5
            fallbacks.add((row["floor"], row["job"], "旧予備B実測×1.5（今回の戦術/継承とは別条件、時間参考のみ）"))
        return statistics.mean(values) * extra
    estimate = sum(cost(r, label) * trials * (1.5 if r["evaluation_version"] == "v2" else 1) * 1.5
                   for r, label, _ in rows)
    return rows, {"conditions": len(rows), "battles": len(rows)*trials, "trials": trials,
                  "seed_base": SEED, "estimated_battle_seconds": round(estimate, 3),
                  "setup_allowance_seconds": 15, "estimated_total_seconds": round(estimate+15, 3),
                  "v2_cost_factor": 1.5, "safety_factor": 1.5, "max_seconds": 270,
                  "c2_timing_fallbacks": sorted(fallbacks),
                  "detail": "全戦を観測、各条件の先頭seedだけ完全詳細を保存"}


class Tee:
    def __init__(self, destination):
        self.destination = destination
    def write(self, value):
        sys.stdout.write(value)
        self.destination.write(value)
        self.flush()
    def flush(self):
        sys.stdout.flush()
        self.destination.flush()
    def isatty(self):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/変更詳細/balance_stage5c_v2/screen")
    args = parser.parse_args()
    rows, estimate = plan()
    # 削減が必要なら全階層/職業/戦術/旧新を残し、全条件の試行数を等しく減らす。
    for trials in (4, 3, 2, 1):
        if estimate["estimated_total_seconds"] <= 270:
            break
        rows, estimate = plan(trials)
    print(json.dumps(estimate, ensure_ascii=False), flush=True)
    if args.plan:
        return
    if estimate["estimated_total_seconds"] > 270:
        raise RuntimeError("最低限の対応比較も上限に収まりません")
    args.output.mkdir(parents=True, exist_ok=False)
    estimate.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    source_sha256=runner.fingerprint())
    (args.output / "selection.json").write_text(json.dumps(estimate, ensure_ascii=False, indent=2)+"\n")
    original_prepare, original_measure, original_run = sim.prepare_profile, sim.measure, sim.BattleEngine.run
    catalog = None

    def prepare(row, label, scale):
        nonlocal catalog
        sim.require_isolation()
        if catalog is None:
            catalog = list(Enemy.objects.filter(is_boss=True).order_by("floor").values(*CATALOG_FIELDS))
            comparison = compare_catalog(catalog)
            with (args.output / "catalog_comparison.json").open("x") as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2)
            if comparison["status"] != "matched":
                raise RuntimeError("隔離DBと想定に差異があります。catalog_comparison.jsonを確認してください")
        return original_prepare(row, label, scale)

    def measure(character, boss, seed, **kwargs):
        critical = Counter()
        def counted_run(engine):
            result = original_run(engine)
            for log in result["logs"]:
                if "クリティカル！" in log:
                    side = "player" if f"{boss.name}に" in log else "boss" if f"{character.name}に" in log else "unattributed"
                    critical[side] += 1
            return result
        with patch.object(sim.BattleEngine, "run", counted_run):
            record = original_measure(character, boss, seed, detail=True)
        record["diagnostics"] = diagnostic(record)
        record["critical_hit_events"] = dict(critical)
        record["evaluation_full_boss"] = {k: getattr(boss, k) for k in CATALOG_FIELDS}
        if seed != SEED:
            for key in ("actions", "hp_events", "state_events"):
                record.pop(key)
        return record

    def teardown(*args_, **kwargs):
        if catalog is not None:
            after = list(Enemy.objects.filter(is_boss=True).order_by("floor").values(*CATALOG_FIELDS))
            with (args.output / "boss_database_unchanged.json").open("x") as f:
                json.dump({"unchanged": after == catalog}, f)
            if after != catalog:
                raise AssertionError("隔離DBの正式ボスが変更されています")
        return original_teardown(*args_, **kwargs)

    original_teardown = runner.teardown_databases
    began = time.perf_counter()
    with (args.output / "execution.log").open("x") as log, \
         patch.object(runner, "cases", return_value=iter(rows)), \
         patch.object(previous, "evaluation_boss", evaluation_boss), \
         patch.object(sim, "prepare_profile", prepare), patch.object(sim, "measure", measure), \
         patch.object(runner, "teardown_databases", teardown):
        try:
            call_command("simulate_boss_v2", isolated_test_db=True, output=str(args.output), trials=5,
                         seed_base=SEED, max_battles=1120, max_seconds=270,
                         plan=False, seconds_per_battle=None, stdout=Tee(log))
        finally:
            with (args.output / "elapsed.json").open("x") as f:
                json.dump({"runner_wall_seconds_including_teardown": time.perf_counter()-began}, f)


if __name__ == "__main__":
    main()
