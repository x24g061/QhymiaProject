"""5-B：新旧を合算せず、共通seed部分だけで候補を比較する。DB接続なし。"""
import argparse
from collections import Counter, defaultdict
import csv
import json
import os
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from apps.battle import simulation_v2 as sim, balance_stage5b as study

JOBS={"grappler":"拳闘士","warrior":"重戦士","hunter":"狩人","wizard":"ウィザード",
      "priest":"プリースト","wanderer":"放浪人","assassin":"暗殺者"}
CORE=("job","race","level","reincarnations","stats","attributes","equipment",
      "attribute_weights","permanent_skill_codes","combat_start")


def aggregate(runs):
    result=sim.summarize(runs)
    valid=[r for r in runs if not r.get("exception")]
    mean=lambda f:statistics.mean(f(r) for r in valid) if valid else None
    for side in ("player","boss"):
        for key in ("actions","normal_attacks","skips","mp_shortages","activation_failures"):
            result[side+"_"+key]=mean(lambda r:r[side][key])
        for key in ("damage_taken","healing","skills","status_active_actions","status_transitions"):
            totals=sum((Counter(r[side][key]) for r in valid),Counter())
            result[side+"_"+key]={k:v/len(valid) for k,v in totals.items()}
        for key in ("hp","mp","st"):
            result[side+"_final_"+key]=mean(lambda r:r["final"][side][key])
        result[side+"_mp_consumed"]=mean(lambda r:r["initial"][side]["mp"]-r["final"][side]["mp"])
    result["damage_to_boss"]=mean(lambda r:sum(v for k,v in r["boss"]["damage_taken"].items() if k!="recoil"))
    result["damage_to_player"]=mean(lambda r:sum(v for k,v in r["player"]["damage_taken"].items() if k!="recoil"))
    result["player_healed"]=mean(lambda r:sum(r["player"]["healing"].values()))
    return result


def display(row):
    if not row or not row["valid"]:
        return "未測定/有効0"
    low,high=row["wilson95"]
    return f"{row['wins']}/{row['valid']} ({row['win_rate']:.1%}; {low:.1%}〜{high:.1%})"


def write_json(path,value):
    with path.open("x") as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,default=ROOT/"docs/変更詳細/balance_stage5b/screen_confirmed")
    p.add_argument("--output",type=Path,default=ROOT/"docs/変更詳細/balance_stage5b/analysis")
    args=p.parse_args()
    if args.output.exists():
        raise RuntimeError("既存集計を上書きしません")
    manifest=json.loads((args.input/"manifest.json").read_text())
    profiles={}
    for case in manifest["cases"]:
        row=case["profile"]
        key=f"{row['profile_id']}-{case['tactic']}-u1"
        assert case["slots"]==[list(s) for s in sim.profile_tactic(row,case["tactic"])]
        profiles[key]=row
    runs=[json.loads(line) for line in (args.input/"runs.jsonl").open()]
    assert len({(r["case"],r["seed"]) for r in runs})==len(runs)
    base_boss={}
    by_character={}
    for r in runs:
        row=profiles[r["case"]]
        key=(row["floor"],row["job"])
        core={k:row[k] for k in CORE}
        if key in by_character:assert by_character[key]==core
        by_character[key]=core
        if not row["boss_override"]:
            observed=r["evaluation_boss"]
            if row["floor"] in base_boss:assert base_boss[row["floor"]]==observed
            base_boss[row["floor"]]=observed
    for r in runs:
        row=profiles[r["case"]]
        expected=base_boss[row["floor"]] | row["boss_override"]
        assert r["evaluation_boss"]==expected
    groups=defaultdict(list)
    for r in runs:groups[r["case"]].append(r)
    conditions=[]
    lookup={}
    for case,rs in groups.items():
        row=profiles[case]
        field,values=study.CANDIDATES.get(row["floor"],(None,[None]))
        value=row["boss_override"].get(field,values[0])
        result={"case":case,"floor":row["floor"],"job":row["job"],"tactic":rs[0]["tactic"],
                "field":field,"value":value,"planned_trials":row["evaluation_trials"],
                "experiments":row["experiments"],**aggregate(rs)}
        target=0.10 if result["tactic"]=="B" else 0.50
        result["gap_percentage_points"]=(result["win_rate"]-target)*100 if result["win_rate"] is not None else None
        conditions.append(result)
        lookup[(row["floor"],row["job"],rs[0]["tactic"],value)]=rs
    # 能力値比較は全候補の共通seed集合へ制限。7階の30戦対照を5戦と誤合算しない。
    sensitivity=[]
    paired=[]
    for floor,(field,values) in study.CANDIDATES.items():
        for job in JOBS:
            label_c="C2" if job in ("wizard","priest") and floor!=1 else "C1"
            for label in ("B",label_c):
                sets=[{r["seed"] for r in lookup.get((floor,job,label,v),[])} for v in values]
                shared=set.intersection(*sets)
                for value in values:
                    rs=[r for r in lookup.get((floor,job,label,value),[]) if r["seed"] in shared]
                    result={"floor":floor,"job":job,"tactic":label,"field":field,"value":value,
                            "shared_seeds":sorted(shared),**aggregate(rs)}
                    result["gap_percentage_points"]=(result["win_rate"]-(0.1 if label=="B" else 0.5))*100 if result["win_rate"] is not None else None
                    sensitivity.append(result)
                baseline={r["seed"]:r for r in lookup.get((floor,job,label,values[0]),[]) if r["seed"] in shared}
                for value in values[1:]:
                    candidate={r["seed"]:r for r in lookup.get((floor,job,label,value),[]) if r["seed"] in shared}
                    paired.append({"floor":floor,"job":job,"tactic":label,"candidate":value,"n":len(shared),
                                   "control_win_candidate_loss":sum(baseline[s]["winner"]=="player" and candidate[s]["winner"]!="player" for s in shared),
                                   "control_loss_candidate_win":sum(baseline[s]["winner"]!="player" and candidate[s]["winner"]=="player" for s in shared)})
    focus=[r for r in conditions if "C2_focus" in r["experiments"]]
    old_path=ROOT/"docs/変更詳細/balance_stage5a/screen_confirmed"
    old_manifest=json.loads((old_path/"manifest.json").read_text())
    old_profiles={c["profile"]["profile_id"]:c["profile"] for c in old_manifest["cases"]}
    old_runs=[json.loads(line) for line in (old_path/"runs.jsonl").open()]
    assert not {r["seed"] for r in runs}&{r["seed"] for r in old_runs}
    for (floor,job),core in by_character.items():
        source=next(r for r in old_profiles.values() if r["floor"]==floor and r["job"]==job and r["recommendation_eligible"])
        assert core=={k:source[k] for k in CORE}
    planned=sum(c["profile"]["evaluation_trials"] for c in manifest["cases"])
    metadata={"planned_battles":planned,"completed_battles":len(runs),"measured_conditions":len(conditions),
              "planned_conditions":len(manifest["cases"]),"battle_seconds":sum(r["elapsed_seconds"] for r in runs),
              "exceptions":sum(bool(r.get("exception")) for r in runs),
              "loop_limits":sum(bool(r.get("reached_1000")) for r in runs),"seed_base":manifest["seed_base"]}
    args.output.mkdir(parents=True)
    write_json(args.output/"results.json",{"metadata":metadata,"conditions":conditions,"focus":focus,
                                           "sensitivity_common_seeds":sensitivity,"paired_candidate_outcomes":paired,
                                           "original_boss_values":base_boss})
    for name,rows in (("conditions",conditions),("sensitivity_common_seeds",sensitivity)):
        with (args.output/(name+".csv")).open("x",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
            writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
    lines=["# ステップ5-B：条件別の測定結果", "", "勝/有効試行（勝率; Wilson95%）。旧データと合算しない。", "",
           "## C2重点比較（元のボス値、各30戦計画）", "", "|階・職業|B|C1|C2|", "|---|---|---|---|"]
    for floor in (7,12):
        for job in ("wizard","priest"):
            rows=[next((r for r in focus if r["floor"]==floor and r["job"]==job and r["tactic"]==t),None) for t in ("B","C1","C2")]
            lines.append("|"+"|".join([f"{floor}階 {JOBS[job]}"]+[display(r) for r in rows])+"|")
    for floor,(field,values) in study.CANDIDATES.items():
        lines += ["",f"## {floor}階 {field}（全候補共通seedのみ）", "", "|職業・戦術|"+"|".join(str(v) for v in values)+"|", "|---|"+"|".join("---" for _ in values)+"|"]
        for job in JOBS:
            for label in ("B","C2" if job in ("wizard","priest") and floor!=1 else "C1"):
                selected=[next((r for r in sensitivity if (r["floor"],r["job"],r["tactic"],r["value"])==(floor,job,label,v)),None) for v in values]
                lines.append("|"+"|".join([JOBS[job]+" "+label]+[display(r) for r in selected])+"|")
    (args.output/"TABLES.md").write_text("\n".join(lines)+"\n")
    print(json.dumps(metadata,ensure_ascii=False))


if __name__=="__main__":
    main()
