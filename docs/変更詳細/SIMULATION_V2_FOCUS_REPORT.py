"""既存予備・重点測定を別標本として再集計する。DB接続なし、既存資料の上書きなし。"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent / "simulation_v2"
OLD = ("pilot_standard", "pilot_tactics", "pilot_ranges", "pilot_comparisons", "pilot_uses")
JOBS = {"grappler": "拳闘士", "warrior": "重戦士", "hunter": "狩人", "wizard": "ウィザード",
        "priest": "プリースト", "wanderer": "放浪人", "assassin": "暗殺者"}


def interval(w, n):
    z = 1.959963984540054
    c = (w/n+z*z/(2*n))/(1+z*z/n)
    d = z*math.sqrt(w/n*(1-w/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0, c-d), min(1, c+d)]


def load(name):
    return [json.loads(line) for line in (ROOT / name / "runs.jsonl").open()]


def stats(runs):
    valid = [r for r in runs if not r.get("exception")]
    assert valid
    mean = lambda f: statistics.mean(f(r) for r in valid)
    w = sum(r["winner"] == "player" for r in valid)
    result = {"n": len(valid), "wins": w, "win_rate": w/len(valid), "wilson95": interval(w, len(valid)),
              "exceptions": len(runs)-len(valid), "loop_limits": sum(r["reached_1000"] for r in valid),
              "double_ko_wins": sum(r["winner"] == "player" and r["final"]["player"]["hp"] == 0 for r in valid),
              "loops": mean(lambda r: r["loops"])}
    for side in ("player", "boss"):
        for key in ("actions", "normal_attacks", "skips", "mp_shortages", "activation_failures"):
            result[side+"_"+key] = mean(lambda r: r[side][key])
        for key in ("damage_taken", "healing", "skills", "status_active_actions", "status_transitions"):
            totals = sum((Counter(r[side][key]) for r in valid), Counter())
            result[side+"_"+key] = {k: v/len(valid) for k,v in totals.items()}
        for resource in ("hp", "mp", "st"):
            result[side+"_final_"+resource] = mean(lambda r: r["final"][side][resource])
        result[side+"_st_zero_count"] = sum(r[side]["st_empty"] for r in valid)
        result[side+"_mp_used"] = mean(lambda r: r["initial"][side]["mp"]-r["final"][side]["mp"])
        wins = [r for r in valid if r["winner"] == "player"]
        result[side+"_hp_on_player_win"] = statistics.mean(r["final"][side]["hp"] for r in wins) if wins else None
    return result


def md_table(rows, columns):
    return "\n".join(["|"+"|".join(title for _,title in columns)+"|",
                      "|"+"|".join("---" for _ in columns)+"|"] +
                     ["|"+"|".join(str(row[key]) for key,_ in columns)+"|" for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default="focus_3c_confirmed")
    parser.add_argument("--output", default="focus_3c_analysis")
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise RuntimeError("既存集計を上書きしません。--outputで別名を指定してください")
    old, duplicates = {}, 0
    profiles, hashes = {}, {}
    groups = defaultdict(list)
    for name in OLD:
        for p in (ROOT/name).iterdir():
            if p.is_file():
                hashes[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest = json.loads((ROOT/name/"manifest.json").read_text())
        for case in manifest["cases"]:
            p = case["profile"]
            if p["profile_id"] in profiles:
                assert profiles[p["profile_id"]] == p
            profiles[p["profile_id"]] = p
        for r in load(name):
            key = (r["case"], r["seed"])
            if key in old:
                assert old[key]["digest"] == r["digest"]
                duplicates += 1
                continue
            old[key] = r
            groups[("旧予備", r["case"])].append(r)
    assert len(old) == 6210 and duplicates == 240
    new = {}
    for phase in ("primary", "equipment", "pathway"):
        name = args.input_root+"/"+phase
        manifest = json.loads((ROOT/name/"manifest.json").read_text())
        for case in manifest["cases"]:
            p = case["profile"]
            if p["profile_id"] in profiles:
                assert profiles[p["profile_id"]] == p
            profiles[p["profile_id"]] = p
        for r in load(name):
            key = (r["case"], r["seed"])
            assert key not in old and key not in new
            new[key] = r
            groups[("新確認", r["case"])].append(r)
    traces = load(args.input_root+"/traces")
    overlap = 0
    diagnostics = []
    for r in traces:
        key = (r["case"], r["seed"])
        if key in new:
            assert r["digest"] == new[key]["digest"]
            overlap += 1
        a = r["actions"]
        d = {"case": r["case"], "seed": r["seed"], "winner": r["winner"]}
        for side in ("player", "boss"):
            moves = [x for x in a if x["side"] == side]
            d[side+"_sequence"] = [x["code"] for x in moves]
            d[side+"_gauges"] = [x["gauge"] | {"tick": x["tick"], "st_before": x["before"]["st"]} for x in moves]
        # 状態遷移とHPイベントは元のtraceに保持。反実仮想の勝率は作らない。
        diagnostics.append(d)
    results, table = [], []
    for (source, case), runs in groups.items():
        first = runs[0]
        p = profiles[first["profile_id"]]
        row = {"source": source, **{k:first[k] for k in ("case", "floor", "job", "tactic", "variant")},
               "profile": p, **stats(runs)}
        results.append(row)
        lo, hi = row["wilson95"]
        table.append({"source":source, "case":case, "floor":row["floor"], "job":JOBS[row["job"]],
                      "tactic":row["tactic"], "power":p["power"], "wins":f'{row["wins"]}/{row["n"]}',
                      "ci":f'{row["win_rate"]:.1%} [{lo:.1%}, {hi:.1%}]',
                      "actions":f'{row["player_actions"]:.1f}/{row["boss_actions"]:.1f}',
                      "hp":f'{row["player_final_hp"]:.1f}',
                      "damage":f'{sum(v for k,v in row["boss_damage_taken"].items() if k!="recoil"):.1f}',
                      "taken":f'{sum(row["player_damage_taken"].values()):.1f}',
                      "poison":f'{row["player_damage_taken"].get("poison",0):.1f}',
                      "heal":f'{sum(row["player_healing"].values()):.1f}',
                      "mp":f'{row["player_final_mp"]:.1f}', "skips":f'{row["player_skips"]:.1f}'})
    output.mkdir(parents=True)
    metadata = {"old_unique":len(old), "old_duplicates":duplicates, "new_statistical":len(new),
                "traces":len(traces), "trace_overlap_with_new":overlap,
                "new_battle_seconds":sum(r["elapsed_seconds"] for r in list(new.values())+traces),
                "new_exceptions":sum(bool(r.get("exception")) for r in list(new.values())+traces),
                "new_loop_limits":sum(bool(r.get("reached_1000")) for r in list(new.values())+traces)}
    (output/"analysis.json").write_text(json.dumps({"metadata":metadata,"conditions":results,"trace_diagnostics":diagnostics},ensure_ascii=False,indent=2)+"\n")
    (output/"old_artifact_sha256.json").write_text(json.dumps(hashes,indent=2)+"\n")
    with (output/"conditions.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    columns=[("source","標本"),("case","条件"),("job","職業"),("tactic","戦術"),("wins","勝/戦"),("ci","勝率 [Wilson95%]"),
             ("actions","行動P/B"),("hp","終了HP"),("damage","与ダメ"),("taken","被ダメ"),("poison","被毒"),("heal","回復"),("mp","残MP")]
    representative={c["profile"]["profile_id"] for c in json.loads((ROOT/"pilot_standard/manifest.json").read_text())["cases"]}
    text=["# ステップ3-C前半：条件別集計（自動生成）", "", "新旧を合算しない。旧は30戦、新は100戦。与ダメはボスの自傷を除く実HP減少。終了HPは敗北の0を含む全戦平均。", ""]
    for floor in (1,5,6,7,8,9,10,12):
        subset=[row for row,res in zip(table,results) if row["floor"]==floor and
                (res["profile"]["profile_id"] in representative or row["source"]=="新確認")]
        text += [f"## {floor}階", "", md_table(subset,columns), ""]
    (output/"TABLES.md").write_text("\n".join(text)+"\n")
    print(json.dumps(metadata,ensure_ascii=False))


if __name__ == "__main__":
    main()
