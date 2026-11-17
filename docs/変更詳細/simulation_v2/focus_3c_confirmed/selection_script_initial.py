"""ステップ3-C前半の有限選択。戦闘実装を変更せず既存の隔離ランナーを使う。"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.management import call_command
from django.db import connection
from apps.battle import simulation_v2 as sim
from apps.battle.management.commands import simulate_boss_v2 as runner

DEST = ROOT / "docs/変更詳細/simulation_v2/focus_3c"
SEED = 30361117  # 既存20261117系列と重ならない確認用系列


def selections(phase):
    rows = list(sim.load_profiles())
    representative = [r for r in rows if r["seed"] == 20261116
                      and (r["floor"] < 7 or r["variant"].startswith("mid-"))]
    if phase == "primary":
        for row in representative:
            labels = ("AB" if row["floor"] == 1 and row["job"] == "assassin" else
                      ("BC" if row["job"] in ("warrior", "wizard") else "C") if row["floor"] == 5 else
                      "BC" if row["floor"] == 7 and row["job"] == "warrior" else
                      "ABC" if row["floor"] == 8 and row["job"] == "grappler" else "")
            for label in labels:
                yield row, label, 1
    elif phase == "equipment":
        module = sim.baseline_module()
        # 算出器もSQL禁止。元の種族/seed/回帰/Lv/素値/属性を固定する。
        with connection.execute_wrapper(module.no_sql):
            row = next(r for r in representative if r["floor"] == 5 and r["job"] == "warrior")
            character = module.path(row["job"], row["race"], row["reincarnations"], row["seed"])[row["level"]-1]
            extra = module.profile(5, character, row["seed"], "paired-F+8", module.equipment(row["job"], [8]*5))
            assert all(extra[k] == row[k] for k in ("stats", "attributes", "race", "seed", "reincarnations", "level", "attribute_weights"))
            extra["profile_id"] = row["profile_id"] + "-paired-F8"
            for label in "C":
                yield extra, label, 1
    else:
        for row in representative:
            if (row["floor"], row["job"]) in ((6, "warrior"), (6, "wizard"), (6, "priest"), (8, "grappler"), (8, "warrior")):
                for label in ("ABC" if row["floor"] == 8 else "BC"):
                    yield row, label, 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("primary", "equipment", "traces"), required=True)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--output-root", type=Path, default=DEST)
    args = parser.parse_args()
    selected = list(selections(args.phase))
    trials = 1 if args.phase == "traces" else 100
    # 予備の条件別処理時間を再利用。未測定戦術にはBの時間×1.5（8階Aは×3）。
    timing = defaultdict(list)
    for name in ("pilot_standard", "pilot_tactics"):
        for line in (DEST.parent / name / "runs.jsonl").open():
            run = json.loads(line)
            timing[(run["floor"], run["job"], run["tactic"])].append(run["elapsed_seconds"])
    seconds = 0
    for row, label, _ in selected:
        values = timing.get((row["floor"], row["job"], label))
        factor = 1
        if not values:
            values = timing[(row["floor"], row["job"], "B")]
            factor = 3 if row["floor"] == 8 and label == "A" else 1.5
        seconds += trials * sum(values)/len(values) * factor
    plan = {"phase": args.phase, "conditions": len(selected), "battles": trials*len(selected),
            "estimated_battle_seconds": round(seconds, 1), "setup_allowance_seconds": 10,
            "seed_base": SEED, "trials": trials,
            "selection_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    print(json.dumps(plan, ensure_ascii=False), flush=True)
    output = args.output_root / args.phase
    if not args.plan:
        if output.exists():
            raise RuntimeError("既存成果物を保持します。別の測定先が必要です")
        output.mkdir(parents=True)
        (output / "selection.json").write_text(json.dumps(plan, indent=2)+"\n")
    # 差し替えるのは条件列挙だけ。既存runnerのDB隔離/書込み拒否/保存をそのまま使う。
    with patch.object(runner, "cases", return_value=iter(selected)):
        call_command("simulate_boss_v2", isolated_test_db=True, output=str(output),
                     trials=trials, seed_base=SEED, detail=args.phase == "traces",
                     max_battles=2500, plan=args.plan, seconds_per_battle=None)


if __name__ == "__main__":
    main()
