"""5-Aの条件・旧結果・新結果を別標本として集計。既存成果物は上書きしない。"""
import csv
import ast
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
import statistics

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from apps.battle import balance_stage5 as study, simulation_v2 as sim

OUT = ROOT / "docs/変更詳細/balance_stage5a/analysis"
OLD = ROOT / "docs/変更詳細/simulation_v2"
NEW = ROOT / "docs/変更詳細/balance_stage5a/screen_confirmed"
JOBS = {"grappler":"拳闘士", "warrior":"重戦士", "hunter":"狩人", "wizard":"ウィザード",
        "priest":"プリースト", "wanderer":"放浪人", "assassin":"暗殺者"}


def dump(path, value):
    with path.open("x") as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=OUT)
    OUT=parser.parse_args().output
    if OUT.exists():
        raise RuntimeError("既存集計を上書きしません")
    profiles = list(study.profiles())
    for row in profiles:
        study.validate_profile(row)
    manifest = json.loads((NEW/"manifest.json").read_text())
    metadata = {}
    for case in manifest["cases"]:
        row = case["profile"]
        metadata[f"{row['profile_id']}-{case['tactic']}-u1"] = row
        assert case["slots"] == [list(x) for x in row["tactics"][case["tactic"]]]
    runs = [json.loads(line) for line in (NEW/"runs.jsonl").open()]
    assert len({(r["case"],r["seed"]) for r in runs}) == len(runs)
    groups = defaultdict(list)
    for r in runs:
        groups[r["case"]].append(r)
    conditions=[]
    for case, trials in groups.items():
        profile = metadata[case]
        label = trials[0]["tactic"]
        row = {"case":case,"profile_id":profile["profile_id"],"floor":profile["floor"],
               "job":profile["job"],"mode":profile["inheritance_mode"],"tactic":label,
               "power":profile["power"],"inherited":profile["permanent_skill_codes"], **sim.summarize(trials)}
        valid=[r for r in trials if not r.get("exception")]
        for side in ("player","boss"):
            for resource in ("hp","mp","st"):
                row[f"{side}_final_{resource}"]=statistics.mean(r["final"][side][resource] for r in valid) if valid else None
            for kind in ("normal","skill","poison","reflection","counter","recoil"):
                row[f"{side}_taken_{kind}"]=statistics.mean(r[side]["damage_taken"].get(kind,0) for r in valid) if valid else None
            row[f"{side}_healing"]=statistics.mean(sum(r[side]["healing"].values()) for r in valid) if valid else None
        row["gap_percentage_points"]=(row["win_rate"]-({"B":0.10,"C":0.50}[label]))*100 if row["win_rate"] is not None else None
        conditions.append(row)
    paired=defaultdict(dict)
    for case, profile in metadata.items():
        paired[profile["profile_id"]][case.split("-")[-2]]=profile
    for labels in paired.values():
        assert labels["B"] == labels["C"]  # プリセット以外の全条件を厳密に一致させる
    old_unique={}
    duplicates=0
    for name in ("pilot_standard","pilot_tactics","pilot_ranges","pilot_comparisons","pilot_uses"):
        for line in (OLD/name/"runs.jsonl").open():
            r=json.loads(line);key=(r["case"],r["seed"])
            if key in old_unique:
                assert r["digest"]==old_unique[key]["digest"]
                duplicates+=1
            else:
                old_unique[key]=r
    assert len(old_unique)==6210 and duplicates==240
    assert not {r["seed"] for r in runs} & {r["seed"] for r in old_unique.values()}
    old_groups=defaultdict(list)
    for r in old_unique.values():
        old_groups[r["case"]].append(r)
    old_summary=[{"case":case,"floor":rs[0]["floor"],"job":rs[0]["job"],"tactic":rs[0]["tactic"],
                  **sim.summarize(rs)} for case,rs in old_groups.items()]
    stat={"new_battles":len(runs),"new_conditions":len(conditions),
          "exceptions":sum(bool(r.get("exception")) for r in runs),
          "loop_limits":sum(bool(r.get("reached_1000")) for r in runs),
          "battle_seconds":sum(r["elapsed_seconds"] for r in runs),"old_unique":len(old_unique),"old_duplicates":duplicates}
    OUT.mkdir(parents=True)
    dump(OUT/"profiles.json",profiles)
    focus=json.loads((OLD/"focus_3c_analysis/analysis.json").read_text())
    dump(OUT/"conditions.json",{"metadata":stat,"new_conditions":conditions,"old_conditions":old_summary,
                                  "old_focus_conditions":[r for r in focus["conditions"] if r["source"]=="新確認"]})
    tree=ast.parse((ROOT/"apps/battle/migrations/0002_add_initial_skills.py").read_text())
    assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="skills" for t in n.targets))
    catalog=ast.literal_eval(assignment.value)
    dump(OUT/"skill_catalog.json",catalog)
    with (OUT/"conditions.csv").open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(conditions[0]));writer.writeheader();writer.writerows(conditions)
    with (OUT/"growth.csv").open("x",newline="") as f:
        writer=csv.writer(f);writer.writerow(["floor","job","level","reincarnations","power","equipment","inheritance_count","inheritance_codes","stats","attributes"])
        for r in profiles:
            if r["recommendation_eligible"]:
                writer.writerow([r["floor"],r["job"],r["level"],r["reincarnations"],r["power"],
                                 json.dumps(r["equipment"],ensure_ascii=False),len(r["permanent_skill_codes"]),
                                 json.dumps(r["permanent_skill_codes"]),json.dumps(r["stats"]),json.dumps(r["attributes"])])
    lines=["# ステップ5-A：条件別表", "", "各条件5戦の探索的測定。旧結果と合算しない。noneは回帰済みなら旧仕様対照、trainedは合法履歴を持つ評価候補。", ""]
    lookup={(r["floor"],r["job"],r["mode"],r["tactic"]):r for r in conditions}
    for floor in (1,5,6,7,8,12):
        lines += [f"## {floor}階", "", "|職業|継承なしB|継承なしC|継承ありB|継承ありC|", "|---|---|---|---|---|"]
        for job,name in JOBS.items():
            cells=[]
            for mode,label in (("none","B"),("none","C"),("trained","B"),("trained","C")):
                r=lookup.get((floor,job,mode,label))
                if not r:
                    cells.append("対象外/未測定");continue
                if r["wilson95"] is None:
                    cells.append(f"有効0/{r['trials']}");continue
                lo,hi=r["wilson95"]
                cells.append(f"{r['wins']}/{r['valid']} ({r['win_rate']:.0%}; {lo:.1%}〜{hi:.1%})")
            lines.append("|"+"|".join([name]+cells)+"|")
        lines.append("")
    lines += ["## 推奨条件候補（職業別の最小〜最大）", "", "|階|Lv|回帰|戦闘力|装備|永久習得|", "|---|---|---|---|---|---|"]
    for floor in range(1,13):
        selected=[r for r in profiles if r["floor"]==floor and r["recommendation_eligible"]]
        ranges=lambda key:f"{min(r[key] for r in selected)}〜{max(r[key] for r in selected)}"
        equipment="装備なし" if not selected[0]["equipment"] else "F " + "/".join(sorted({str(e["enhancement"]) for r in selected for e in r["equipment"]}))
        lines.append(f"|{floor}|{ranges('level')}|{ranges('reincarnations')}|{ranges('power')}|{equipment}|{len(selected[0]['permanent_skill_codes'])}種類|")
    lines += ["", "## B/C戦術（順序と回数）", "", "|職業|継承条件|B|C|", "|---|---|---|---|"]
    names={s["code"]:s["name"] for s in catalog}
    for job,name in JOBS.items():
        for mode,codes in (("なし",[]),("2職業各5回",study.inheritance(job,10)[0])):
            tactics=study.slots(job,codes)
            fmt=lambda label:" → ".join(f"{names[code]}×{n}" for code,n in tactics[label])
            lines.append(f"|{name}|{mode}|{fmt('B')}|{fmt('C')}|")
    (OUT/"TABLES.md").write_text("\n".join(lines)+"\n")
    ids={c["profile"]["profile_id"] for c in json.loads((OLD/"pilot_standard/manifest.json").read_text())["cases"]}
    old_lines=["# 旧ステップ3：代表B・職業別再集計", "",
               "各職業30戦。旧ソース・旧装備・旧戦術・継承なしの結果。新条件と合算しない。各条件Wilson区間はconditions.jsonのold_conditionsに保持。", "",
               "|階|拳闘士|重戦士|狩人|ウィザード|プリースト|放浪人|暗殺者|", "|---|---|---|---|---|---|---|---|"]
    for floor in range(1,13):
        by_job={r["job"]:r for r in old_summary if r["floor"]==floor and r["case"].endswith("-B-u1") and r["case"].split("-")[0] in ids}
        old_lines.append("|"+str(floor)+"|"+"|".join(f"{by_job[j]['wins']}/{by_job[j]['valid']}" for j in JOBS)+"|")
    (OUT/"OLD_TABLES.md").write_text("\n".join(old_lines)+"\n")
    proposals=[{"profile_id":p["profile_id"],"status":"proposal_unmeasured","B":p["tactics"]["B"],
                "C2":[["principle_of_freedom",1],["anti_jail",12],["judgement",8]],
                "permanent_skill_codes":p["permanent_skill_codes"],
                "reason":"C1のステラ/メギド混在を外し、単体戦で高倍率の攻撃へ寄せる。Bを弱くしない。"}
               for p in profiles if p["job"] in ("wizard","priest") and p["inheritance_mode"]=="trained" and p["reincarnations"]>=10]
    dump(OUT/"C2_PROPOSAL_UNMEASURED.json",proposals)
    # 旧成果物の監査索引。新出力以外への書込みなし。
    dump(OUT/"old_sha256.json", {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in OLD.rglob("*") if p.is_file() and p.suffix in (".json",".jsonl",".csv",".md")})
    print(json.dumps(stat))


if __name__ == "__main__":
    main()
