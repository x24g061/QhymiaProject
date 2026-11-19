"""5-Cの職業別集計・対応seed比較・旧資料不変を検証する。戦闘/DB操作なし。"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


study = load_module("stage5c", HERE / "BALANCE_STAGE5C_RUN.py")
previous_report = load_module("stage5b_report", HERE / "BALANCE_STAGE5B_REPORT.py")
JOBS = previous_report.JOBS


def aggregate(runs):
    result = previous_report.aggregate(runs)
    valid = [r for r in runs if not r.get("exception")]
    for side in ("player", "boss"):
        diag = [r["diagnostics"][side] for r in valid]
        keys = ("direct_attack_actions", "support_actions", "physical_attack_actions", "magic_attack_actions",
                "direct_damage", "physical_damage", "magic_damage", "direct_hit_events", "shield_actual_heal")
        result[side+"_diagnostics"] = {k: statistics.mean(d[k] for d in diag) for k in keys}
        d = result[side+"_diagnostics"]
        d["damage_per_direct_attack"] = d["direct_damage"]/d["direct_attack_actions"] if d["direct_attack_actions"] else None
        d["healing_executed_runs"] = sum(r["healing_shield_executed"] for r in diag)
        for key in ("first_heal_action", "first_heal_tick", "first_heal_hp_before"):
            values = [r[key] for r in diag if r[key] is not None]
            d[key] = statistics.mean(values) if values else None
        d["first_six_patterns"] = dict(Counter(" → ".join(r["first_six"]) for r in diag))
        total = sum((Counter(r["damage_by_skill"]) for r in diag), Counter())
        d["damage_by_skill"] = {k: v/len(valid) for k, v in total.items()}
    return result


def write_json(path, value):
    with path.open("x") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def csv_rows(path, rows):
    with path.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in r.items()} for r in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "balance_stage5c/screen_confirmed")
    parser.add_argument("--output", type=Path, default=HERE / "balance_stage5c/analysis")
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("既存分析を保持します。別出力先を指定してください")
    manifest = json.loads((args.input / "manifest.json").read_text())
    selected = json.loads((args.input / "selection.json").read_text())
    assert selected["script_sha256"] == hashlib.sha256((HERE / "BALANCE_STAGE5C_RUN.py").read_bytes()).hexdigest()
    assert manifest["source_sha256"] == study.runner.fingerprint()
    profiles = {f"{c['profile']['profile_id']}-{c['tactic']}-u1": c["profile"] for c in manifest["cases"]}
    expected_plan = {(r["profile_id"], label): r for r, label, _ in study.scenarios()}
    for c in manifest["cases"]:
        row = c["profile"]
        assert row == json.loads(json.dumps(expected_plan[row["profile_id"], c["tactic"]]))
        assert c["slots"] == [list(x) for x in study.sim.profile_tactic(row, c["tactic"])]
    runs = [json.loads(line) for line in (args.input / "runs.jsonl").open()]
    assert len(runs) == selected["battles"]
    assert not any(r["exception"] or r["reached_1000"] for r in runs)
    assert len({(r["case"], r["seed"]) for r in runs}) == len(runs)
    before = json.loads((HERE / "balance_stage5c/before.json").read_text())
    for path, digest in before["sha256"].items():
        assert hashlib.sha256((study.ROOT / path).read_bytes()).hexdigest() == digest, path
    old_cases = json.loads((HERE / "balance_stage5b/screen_confirmed/manifest.json").read_text())["cases"]
    old_core = {(c["profile"]["floor"], c["profile"]["job"]): {k: c["profile"][k] for k in study.CORE} for c in old_cases}
    bosses = {b["floor"]: {k: v for k, v in b.items() if k not in ("name", "attribute")} for b in json.loads((args.input / "summary.json").read_text())["bosses"]}
    groups = defaultdict(list)
    for r in runs:
        row = profiles[r["case"]]
        assert {k: row[k] for k in study.CORE} == old_core[row["floor"], row["job"]]
        assert r["evaluation_boss"] == bosses[r["floor"]] | row["boss_override"]
        assert r["initial"]["player"]["hp"] == row["combat_start"]["max_hp"]
        assert r["permanent_skill_codes"] == sorted(row["permanent_skill_codes"])
        for side in ("player", "boss"):
            assert r["initial"][side]["hp"] + sum(r[side]["healing"].values()) - sum(r[side]["damage_taken"].values()) == r["final"][side]["hp"]
        groups[r["case"]].append(r)
    conditions, lookup = [], {}
    for case, rs in groups.items():
        row = profiles[case]
        assert len(rs) == row["evaluation_trials"]
        assert {r["seed"] for r in rs} == set(range(study.SEED, study.SEED+row["evaluation_trials"]))
        summary = {"case": case, "floor": row["floor"], "job": row["job"], "tactic": rs[0]["tactic"],
                   "variant": row["evaluation_variant"], "override": row["boss_override"], **aggregate(rs)}
        summary["gap_percentage_points"] = (summary["win_rate"]-(.1 if summary["tactic"] == "B" else .5))*100
        conditions.append(summary)
        lookup[row["floor"], row["job"], rs[0]["tactic"], row["evaluation_variant"]] = rs
    paired = []
    for floor, job, label, variant in lookup:
        if variant == "base" and label != "C3":
            continue
        reference = "C2" if label == "C3" else label
        control = {r["seed"]: r for r in lookup[floor, job, reference, "base"]}
        candidate = {r["seed"]: r for r in lookup[floor, job, label, variant]}
        assert control.keys() == candidate.keys()
        seeds = sorted(control)
        paired.append({"floor": floor, "job": job, "tactic": label, "variant": variant,
                       "reference": reference, "n": len(seeds), "seeds": seeds,
                       "control_win_candidate_loss": sum(control[s]["winner"] == "player" and candidate[s]["winner"] != "player" for s in seeds),
                       "control_loss_candidate_win": sum(control[s]["winner"] != "player" and candidate[s]["winner"] == "player" for s in seeds),
                       "identical_digests": sum(control[s]["digest"] == candidate[s]["digest"] for s in seeds)})
    report = {"plan": selected, "conditions": conditions, "paired": paired,
              "battles": len(runs), "battle_seconds": sum(r["elapsed_seconds"] for r in runs),
              "exceptions": sum(bool(r["exception"]) for r in runs),
              "loop_limits": sum(r["reached_1000"] for r in runs),
              "full_detail_runs": sum("actions" in r for r in runs),
              "protected_files": len(before["sha256"]), "validation": "全記録の実能力値/育成/技能/seed/HP台帳/指紋一致"}
    args.output.mkdir(parents=True)
    write_json(args.output / "results.json", report)
    csv_rows(args.output / "conditions.csv", conditions)
    csv_rows(args.output / "paired.csv", paired)
    lines = ["# 5-C職業別表", "", "各行の勝率区間はWilson95%。新規980戦のみ。7階魔法条件はC3比較と職業分析で共用し、加算しない。", ""]
    for floor in (8, 7, 12):
        lines += [f"## {floor}階", "", "|職業・戦術・候補|勝/試行 (率; Wilson95%)|ループ|行動P/Boss|ボス直接攻撃/補助|与ダメ/被ダメ|", "|---|---|---:|---|---|---|"]
        for c in conditions:
            if c["floor"] != floor:
                continue
            d = c["boss_diagnostics"]
            lines.append(f"|{JOBS[c['job']]} {c['tactic']} {c['variant']}|{previous_report.display(c)}|{c['mean_loops']:.1f}|{c['player_actions']:.1f}/{c['boss_actions']:.1f}|{d['direct_attack_actions']:.1f}/{d['support_actions']:.1f}|{c['damage_to_boss']:.0f}/{c['damage_to_player']:.0f}|")
        lines.append("")
    with (args.output / "TABLES.md").open("x") as f:
        f.write("\n".join(lines))
    print(json.dumps({k: v for k, v in report.items() if k not in ("conditions", "paired", "plan")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
