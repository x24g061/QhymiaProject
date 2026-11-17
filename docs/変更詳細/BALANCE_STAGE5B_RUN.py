"""5-B有限測定。既存隔離ランナーに条件だけを渡す。"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.core.management import call_command
from apps.battle import balance_stage5b as study
from apps.battle.management.commands import simulate_boss_v2 as runner


def plan():
    rows=study.scenarios()
    source=ROOT/"docs/変更詳細/balance_stage5a/screen_confirmed"
    manifest=json.loads((source/"manifest.json").read_text())
    eligible={c["profile"]["profile_id"] for c in manifest["cases"] if c["profile"]["recommendation_eligible"]}
    timing=defaultdict(list)
    for line in (source/"runs.jsonl").open():
        r=json.loads(line)
        if r["profile_id"] in eligible:
            timing[(r["floor"],r["job"],r["tactic"])].append(r["elapsed_seconds"])
    seconds=0
    for row,label,_ in rows:
        values=timing[(row["floor"],row["job"],"B" if label=="B" else "C")]
        seconds+=sum(values)/len(values)*row["evaluation_trials"]*1.5
    result={"conditions":len(rows),"battles":sum(r["evaluation_trials"] for r,_,_ in rows),
            "estimated_battle_seconds":round(seconds,1),"setup_allowance_seconds":15,
            "max_seconds":270,"seed_base":70361117,
            "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return rows,result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",action="store_true")
    parser.add_argument("--output",type=Path,default=ROOT/"docs/変更詳細/balance_stage5b/screen")
    args=parser.parse_args()
    rows,estimated=plan()
    print(json.dumps(estimated,ensure_ascii=False),flush=True)
    if not args.plan:
        if estimated["estimated_battle_seconds"]+15>300:
            raise RuntimeError("5分を超える計画です。条件削減が必要")
        if args.output.exists():
            raise RuntimeError("既存成果物は保持します。別の出力先が必要")
        args.output.mkdir(parents=True)
        (args.output/"selection.json").write_text(json.dumps(estimated,indent=2)+"\n")
    with patch.object(runner,"cases",return_value=iter(rows)):
        call_command("simulate_boss_v2",isolated_test_db=True,output=str(args.output),
                     trials=5,seed_base=70361117,max_battles=2500,max_seconds=270,
                     plan=args.plan,seconds_per_battle=None)


if __name__=="__main__":
    main()
