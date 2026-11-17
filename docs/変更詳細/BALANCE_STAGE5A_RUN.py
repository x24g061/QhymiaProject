"""5-A：条件計画と既存隔離ランナーによる小規模実行。"""
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
from apps.battle import balance_stage5 as study
from apps.battle.management.commands import simulate_boss_v2 as runner

DEST = ROOT / "docs/変更詳細/balance_stage5a"


def selection():
    for row in study.profiles():
        study.validate_profile(row)
        if row["floor"] in (1, 5, 6, 7, 8, 12):
            for label in "BC":
                yield row, label, 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", action="store_true")
    p.add_argument("--output", type=Path, default=DEST / "screen")
    args = p.parse_args()
    rows = list(selection())
    timing = defaultdict(list)
    for line in (ROOT / "docs/変更詳細/simulation_v2/pilot_standard/runs.jsonl").open():
        r = json.loads(line)
        timing[(r["floor"], r["job"])].append(r["elapsed_seconds"])
    seconds = sum(sum(timing[(r["floor"],r["job"])])/len(timing[(r["floor"],r["job"])])*1.5*5 for r,_,_ in rows)
    plan = {"conditions":len(rows), "trials":5, "battles":len(rows)*5,
            "estimated_battle_seconds":round(seconds,1), "setup_allowance_seconds":15,
            "seed_base":50361117, "max_seconds":270,
            "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    print(json.dumps(plan,ensure_ascii=False),flush=True)
    if not args.plan:
        if seconds+15 > 300:
            raise RuntimeError("計画が5分を超えるため条件削減が必要")
        if args.output.exists():
            raise RuntimeError("既存出力は保持します。新しい出力先が必要")
        args.output.mkdir(parents=True)
        (args.output/"selection.json").write_text(json.dumps(plan,indent=2)+"\n")
    with patch.object(runner,"cases",return_value=iter(rows)):
        call_command("simulate_boss_v2", isolated_test_db=True, output=str(args.output),
                     trials=5, seed_base=50361117, max_battles=1000, max_seconds=270,
                     plan=args.plan, seconds_per_battle=None)


if __name__ == "__main__":
    main()
