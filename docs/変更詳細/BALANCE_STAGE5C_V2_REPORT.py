"""Ver.2全変更階層の対応比較。DB接続なし、未完条件を区別する。"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


study = load("v2_study", HERE / "BALANCE_STAGE5C_V2_RUN.py")
old_report = load("stage5b_report", HERE / "BALANCE_STAGE5B_REPORT.py")
JOBS = old_report.JOBS


def write_json(path, value):
    with path.open("x") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def csv_rows(path, rows):
    with path.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)


def aggregate(runs):
    valid = [r for r in runs if not r.get("exception")]
    if not valid:
        return study.sim.summarize(runs)
    result = old_report.aggregate(runs)
    mean = lambda f: statistics.mean(f(r) for r in valid)
    for side in ("player", "boss"):
        for field in ("direct_attack_actions", "support_actions", "direct_damage"):
            result[side+"_"+field] = mean(lambda r: r["diagnostics"][side][field])
        totals = sum((Counter(r["diagnostics"][side]["damage_by_skill"]) for r in valid), Counter())
        result[side+"_damage_by_skill"] = {k: v/len(valid) for k, v in totals.items()}
        result[side+"_critical_hit_events"] = mean(lambda r: r["critical_hit_events"].get(side, 0))
        result[side+"_survival_rate"] = mean(lambda r: r["final"][side]["hp"] > 0)
        result[side+"_initial"] = valid[0]["initial"][side]
    result["boss_actions_before_player_first"] = mean(lambda r: r["diagnostics"]["boss_actions_before_player_first"])
    result["both_hp_zero"] = sum(r["diagnostics"]["both_hp_zero"] for r in valid)
    return result


def rate(value):
    if value is None or not value.get("valid"):
        return "未測定"
    low, high = value["wilson95"]
    return f"{value['wins']}/{value['valid']}、{value['win_rate']:.0%} [{low:.1%}〜{high:.1%}]"


def charts(output, comparisons):
    """同じ座標データから独立SVGとPNGを描画する。外部依存/通信なし。"""
    from PIL import Image, ImageDraw, ImageFont
    width, height = 2160, 930
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    titlefont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>']
    def text(x, y, value, size=13, fill="#222222"):
        svg.append(f'<text x="{x}" y="{y+size}" font-family="DejaVu Sans,sans-serif" font-size="{size}" fill="{fill}">{escape(value)}</text>')
        draw.text((x, y), value, font=titlefont if size > 16 else font, fill=fill)
    def rect(x, y, w, h, fill):
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>')
        draw.rectangle((x, y, x+w, y+h), fill=fill)
    def line(x1, y1, x2, y2, color, stroke=1):
        svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{stroke}"/>')
        draw.line((x1, y1, x2, y2), fill=color, width=stroke)
    def point(x, y, color, square=False):
        if square:
            rect(x-4, y-4, 8, 8, color)
        else:
            svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
            draw.ellipse((x-4, y-4, x+4, y+4), fill=color)
    text(20, 12, "Qhymia boss stats V2: paired win rates by floor, job and tactic", 21)
    text(20, 43, "Blue circle = current; orange square = V2; pale band = target (B 5-15%, C 40-60%).")
    text(20, 65, "n=5 per version; screening only. Wilson 95% intervals are in TABLES.md / comparison.csv. Shared seeds across cells.")
    for index, floor in enumerate(study.FLOORS):
        x0, y0 = 15+(index % 4)*540, 110+(index // 4)*400
        text(x0+6, y0, f"Floor {floor}", 21)
        xplot, plotwidth = x0+133, 285
        values = [c for c in comparisons if c["floor"] == floor]
        for n, c in enumerate(values):
            y = y0+47+n*22
            lo, hi = (.05, .15) if c["tactic"] == "B" else (.4, .6)
            rect(xplot+plotwidth*lo, y-7, plotwidth*(hi-lo), 14, "#edf4e7")
            text(x0+6, y-9, f"{c['job'].capitalize()} {c['tactic']}")
            for tick in (0, .5, 1):
                line(xplot+plotwidth*tick, y-8, xplot+plotwidth*tick, y+8, "#e2e2e2")
            if c["old"]["valid"] and c["new"]["valid"]:
                a, b = c["old"]["win_rate"], c["new"]["win_rate"]
                line(xplot+plotwidth*a, y, xplot+plotwidth*b, y, "#999999", 2)
                point(xplot+plotwidth*a, y, "#2468a2")
                point(xplot+plotwidth*b, y, "#d65b18", True)
                text(x0+430, y-9, f"{a:.0%} > {b:.0%}")
            else:
                text(x0+430, y-9, "missing")
        for tick in (0, .5, 1):
            text(xplot+plotwidth*tick-10, y0+362, f"{tick:.0%}")
    svg.append('</svg>')
    with (output / "win_rate_comparison.svg").open("x") as f:
        f.write("\n".join(svg)+"\n")
    image.save(output / "win_rate_comparison.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "balance_stage5c_v2/screen_confirmed")
    parser.add_argument("--output", type=Path, default=HERE / "balance_stage5c_v2/analysis")
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("既存の集計は上書きしません")
    manifest = json.loads((args.input / "manifest.json").read_text())
    selection = json.loads((args.input / "selection.json").read_text())
    catalog = json.loads((args.input / "catalog_comparison.json").read_text())
    assert catalog["status"] == "matched"
    assert selection["source_sha256"] == manifest["source_sha256"] == study.runner.fingerprint()
    assert selection["script_sha256"] == hashlib.sha256((HERE / "BALANCE_STAGE5C_V2_RUN.py").read_bytes()).hexdigest()
    before = json.loads((HERE / "balance_stage5c_v2/before.json").read_text())
    for path, digest in before["sha256"].items():
        assert hashlib.sha256((study.ROOT / path).read_bytes()).hexdigest() == digest, path
    old_bosses = {b["floor"]: b for b in catalog["old"]}
    expected_plan = {(r["profile_id"], label): r for r, label, _ in study.scenarios(selection["trials"])}
    profiles = {}
    for c in manifest["cases"]:
        row, label = c["profile"], c["tactic"]
        assert row == json.loads(json.dumps(expected_plan[row["profile_id"], label]))
        assert c["slots"] == [list(s) for s in study.sim.profile_tactic(row, label)]
        profiles[f"{row['profile_id']}-{label}-u1"] = row
    path = args.input / "runs.jsonl"
    runs = [json.loads(line) for line in path.open()] if path.exists() else []
    assert len({(r["case"], r["seed"]) for r in runs}) == len(runs)
    groups = defaultdict(list)
    for r in runs:
        row = profiles[r["case"]]
        assert r["seed"] in range(study.SEED, study.SEED+selection["trials"])
        expected = old_bosses[r["floor"]] | row["boss_override"]
        if not r.get("exception"):
            assert r["evaluation_full_boss"] == expected
            assert r["initial"]["player"]["hp"] == row["combat_start"]["max_hp"]
            assert r["permanent_skill_codes"] == sorted(row["permanent_skill_codes"])
            assert not r["critical_hit_events"].get("unattributed", 0)
            for side in ("player", "boss"):
                assert r["initial"][side]["hp"] + sum(r[side]["healing"].values()) - sum(r[side]["damage_taken"].values()) == r["final"][side]["hp"]
        groups[r["case"]].append(r)
    conditions, lookup = [], {}
    for case, row in profiles.items():
        rs = groups[case]
        label = case.rsplit("-", 2)[1]
        state = "complete" if len(rs) == selection["trials"] else "partial" if rs else "unmeasured"
        result = {"case": case, "floor": row["floor"], "job": row["job"], "tactic": label,
                  "version": row["evaluation_version"], "completion": state,
                  "planned_trials": selection["trials"], **aggregate(rs)}
        result["gap_percentage_points"] = (result["win_rate"]-(.1 if label == "B" else .5))*100 if result["valid"] else None
        conditions.append(result)
        lookup[row["floor"], row["job"], label, row["evaluation_version"]] = rs
    comparisons, brief = [], []
    for floor in study.FLOORS:
        for job in JOBS:
            labels = [c["tactic"] for c in conditions if c["floor"] == floor and c["job"] == job and c["version"] == "old"]
            for label in labels:
                old = {r["seed"]: r for r in lookup[floor, job, label, "old"] if not r.get("exception")}
                new = {r["seed"]: r for r in lookup[floor, job, label, "v2"] if not r.get("exception")}
                shared = sorted(old.keys() & new.keys())
                a, b = aggregate([old[s] for s in shared]), aggregate([new[s] for s in shared])
                delta = (b["win_rate"]-a["win_rate"])*100 if shared else None
                target = .1 if label == "B" else .5
                gap_old = (a["win_rate"]-target)*100 if shared else None
                gap_new = (b["win_rate"]-target)*100 if shared else None
                verdict = "未比較"
                if shared:
                    difference = abs(gap_new)-abs(gap_old)
                    verdict = "目標へ接近（点推定）" if difference < -1e-7 else "目標から離れる（点推定）" if difference > 1e-7 else "目標距離同等（点推定）"
                state = "complete" if len(shared) == selection["trials"] else "partial" if shared else "unmeasured"
                result = {"floor": floor, "job": job, "tactic": label, "completion": state,
                          "shared_seeds": shared, "old": a, "new": b, "delta_percentage_points": delta,
                          "target": target, "old_gap_percentage_points": gap_old, "new_gap_percentage_points": gap_new,
                          "old_win_new_loss": sum(old[s]["winner"] == "player" and new[s]["winner"] != "player" for s in shared),
                          "old_loss_new_win": sum(old[s]["winner"] != "player" and new[s]["winner"] == "player" for s in shared),
                          "evaluation": verdict}
                comparisons.append(result)
                brief.append({k: v for k, v in result.items() if k not in ("old", "new")} | {"old_wins": a["wins"], "new_wins": b["wins"], "n": len(shared),
                             "old_win_rate": a["win_rate"], "new_win_rate": b["win_rate"], "old_wilson95": a["wilson95"], "new_wilson95": b["wilson95"]})
    floors = []
    for floor in study.FLOORS:
        for tactic_type in ("B", "C"):
            cs = [c for c in comparisons if c["floor"] == floor and (c["tactic"] == "B") == (tactic_type == "B")]
            valid = [c for c in cs if c["old"]["valid"] and c["new"]["valid"]]
            result = {"floor": floor, "tactic_type": tactic_type, "jobs_compared": len(valid)}
            for version in ("old", "new"):
                rates = [c[version]["win_rate"] for c in valid]
                result[version+"_job_rate_range"] = [min(rates), max(rates)] if rates else None
                result[version+"_max_job_gap_pp"] = (max(rates)-min(rates))*100 if rates else None
                result[version+"_equal_job_mean"] = statistics.mean(rates) if rates else None
                result[version+"_mean_absolute_target_gap_pp"] = statistics.mean(abs(r-(.1 if tactic_type == "B" else .5))*100 for r in rates) if rates else None
            floors.append(result)
    report = {"selection": selection, "battles": len(runs), "planned_battles": selection["battles"],
              "complete_conditions": sum(c["completion"] == "complete" for c in conditions),
              "partial_conditions": sum(c["completion"] == "partial" for c in conditions),
              "unmeasured_conditions": sum(c["completion"] == "unmeasured" for c in conditions),
              "battle_seconds": sum(r["elapsed_seconds"] for r in runs),
              "exceptions": sum(bool(r.get("exception")) for r in runs), "loop_limits": sum(r.get("reached_1000", False) for r in runs),
              "full_detail_runs": sum("actions" in r for r in runs), "protected_files": len(before["sha256"]),
              "conditions": conditions, "comparisons": comparisons, "floors": floors}
    args.output.mkdir(parents=True)
    write_json(args.output / "results.json", report)
    csv_rows(args.output / "conditions.csv", conditions)
    csv_rows(args.output / "comparison.csv", brief)
    csv_rows(args.output / "floors.csv", floors)
    lines = ["# Ver.2 全変更階層の職業別対応比較", "", "旧/新で共通の有効seedだけを比較。区間はWilson95%。5戦はスクリーニングであり、評価欄は点推定の目標距離だけを表す。", "",
             "|階層|職業|戦術|旧勝率（勝/試行・95%区間）|新勝率（勝/試行・95%区間）|差|評価|", "|---|---|---|---|---|---|---|"]
    for c in comparisons:
        delta = f"{c['delta_percentage_points']:+.0f}pt" if c["delta_percentage_points"] is not None else "—"
        lines.append(f"|{c['floor']}|{JOBS[c['job']]}|{c['tactic']}|{rate(c['old'])}|{rate(c['new'])}|{delta}|{c['evaluation']}・{c['completion']}|")
    with (args.output / "TABLES.md").open("x") as f:
        f.write("\n".join(lines)+"\n")
    charts(args.output, comparisons)
    print(json.dumps({k: v for k, v in report.items() if k not in ("selection", "conditions", "comparisons", "floors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
