"""Stage 6-Aの全条件・対応反転・行動台帳をDB接続なしで集計する。"""
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
spec = importlib.util.spec_from_file_location("stage6_report_study", HERE / "BALANCE_STAGE6A_RUN.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
JOBS = {"grappler": "拳闘士", "warrior": "重戦士", "hunter": "狩人", "wizard": "ウィザード",
        "priest": "プリースト", "wanderer": "放浪人", "assassin": "暗殺者"}


def csv_rows(path, rows):
    with path.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def aggregate(runs, planned):
    result = study.sim.summarize(runs)
    valid = [r for r in runs if not r.get("exception")]
    result.update(planned=planned, missing=max(0, planned-len(runs)),
                  complete=len(runs) == planned and not result["exceptions"])
    if not valid:
        return result
    mean = lambda fn: statistics.mean(fn(r) for r in valid)
    for side in ("player", "boss"):
        for field in ("actions", "normal_attacks", "activation_failures", "mp_shortages", "skips"):
            result[side+"_"+field] = mean(lambda r: r[side][field])
        for field in ("damage_dealt", "damage_taken", "healing", "skills", "status_transitions", "status_active_actions"):
            counts = sum((Counter(r[side][field]) for r in valid), Counter())
            result[side+"_"+field] = {k: v/len(valid) for k, v in counts.items()}
            result[side+"_"+field+"_total"] = sum(counts.values())/len(valid)
        for field in ("hp", "mp", "st"):
            result[side+"_final_"+field] = mean(lambda r: r["final"][side][field])
        result[side+"_survived"] = sum(r["final"][side]["hp"] > 0 for r in valid)
        result[side+"_healing_actions"] = mean(lambda r: r["diagnostics"][side]["healing_actions"])
        result[side+"_damage_to_opponent"] = mean(lambda r: sum(e["amount"] for e in r["hp_events"]
            if e["source"] == side and e["target"] != side and e["kind"] != "heal"))
        result[side+"_self_damage"] = mean(lambda r: sum(e["amount"] for e in r["hp_events"]
            if e["source"] == side and e["target"] == side and e["kind"] != "heal"))
        result[side+"_reached_healing_shield"] = sum(r["diagnostics"][side]["first_heal_action"] is not None for r in valid)
        result[side+"_exhausted_battles"] = sum(bool(r["diagnostics"][side]["exhausted_slots"]) for r in valid)
        result[side+"_exhausted_slots"] = dict(sum((Counter(r["diagnostics"][side]["exhausted_slots"]) for r in valid), Counter()))
    result["both_hp_zero"] = sum(r["diagnostics"]["both_hp_zero"] for r in valid)
    return result


def paired(old, new):
    a = {r["seed"]: r for r in old if not r.get("exception")}
    b = {r["seed"]: r for r in new if not r.get("exception")}
    common = sorted(a.keys() & b.keys())
    return {"paired_valid_seeds": common,
            "loss_to_win": sum(a[s]["winner"] != "player" and b[s]["winner"] == "player" for s in common),
            "win_to_loss": sum(a[s]["winner"] == "player" and b[s]["winner"] != "player" for s in common),
            "winner_changes": [{"seed": s, "old": a[s]["winner"], "new": b[s]["winner"]}
                               for s in common if a[s]["winner"] != b[s]["winner"]]}


def rate(summary):
    if not summary["valid"]:
        return f"未測定（予定{summary['planned']}・例外{summary['exceptions']}）"
    lo, hi = summary["wilson95"]
    suffix = "" if summary["complete"] else " 未完"
    return f"{summary['wins']}/{summary['valid']} ({summary['win_rate']:.0%}; {lo:.1%}〜{hi:.1%}){suffix}"


def charts(output, comparisons, delta=False):
    """Pillowと同じ座標からPNG/SVGを保存。各点の区間は表に記載。"""
    from PIL import Image, ImageDraw, ImageFont
    width, height = 1800, 1730
    bitmap = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(bitmap)
    fonts = {size: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size) for size in (12, 16, 22)}
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>']
    def text(x, y, value, size=12, fill="#222222"):
        draw.text((x, y), str(value), font=fonts[size], fill=fill)
        svg.append(f'<text x="{x}" y="{y+size}" font-family="DejaVu Sans,sans-serif" font-size="{size}" fill="{fill}">{escape(str(value))}</text>')
    def line(x, y, xx, yy, color="#cccccc", stroke=1):
        draw.line((x, y, xx, yy), fill=color, width=stroke)
        svg.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{color}" stroke-width="{stroke}"/>')
    def rect(x, y, xx, yy, color):
        draw.rectangle((x, y, xx, yy), fill=color)
        svg.append(f'<rect x="{x}" y="{y}" width="{xx-x}" height="{yy-y}" fill="{color}"/>')
    def point(x, y, color):
        draw.ellipse((x-4, y-4, x+4, y+4), fill=color)
        svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    text(20, 10, "Growth V2: paired win-rate changes" if delta else "Growth V2: old / new paired win rates", 22)
    text(20, 43, "Fixed official bosses, equipment, level, inheritance and seeds. n=5; exploratory only. Wilson intervals: TABLES.md", 16)
    text(20, 72, "Delta = new - old, percentage points." if delta else "Blue=old; orange=new. Pale green=B 5-15%, C 40-60%. Shared seeds across jobs; no pooled binomial inference.")
    for index, floor in enumerate(range(1, 13)):
        x0, y0 = 15+index%3*595, 110+index//3*400
        text(x0+5, y0, f"Floor {floor}", 22)
        xp, span = x0+145, 280
        for tick in ((-100, -50, 0, 50, 100) if delta else (0, 25, 50, 75, 100)):
            x = xp+(tick+100)/200*span if delta else xp+tick/100*span
            line(x, y0+38, x, y0+355)
            text(x-10, y0+358, str(tick))
        rows = [r for r in comparisons if r["floor"] == floor]
        for n, row in enumerate(rows):
            y = y0+48+n*22
            text(x0+4, y-7, f"{row['job'].title()[:10]} {row['tactic']}")
            if row["delta_pp"] is None:
                text(xp+80, y-6, "missing")
                continue
            if delta:
                zero, value = xp+span/2, xp+(row["delta_pp"]+100)/200*span
                line(zero, y, value, y, "#2e8b57" if value >= zero else "#b04b59", 7)
                text(xp+span+10, y-7, f"{row['delta_pp']:+.0f}")
            else:
                lo, hi = (5, 15) if row["tactic"] == "B" else (40, 60)
                rect(xp+lo/100*span, y-8, xp+hi/100*span, y+8, "#e0f0dd")
                a, b = xp+row["old_rate"]*span, xp+row["new_rate"]*span
                line(a, y, b, y, "#888888", 2)
                point(a, y, "#2166ac")
                point(b, y, "#d95f02")
                text(xp+span+10, y-7, f"{row['old_wins']}->{row['new_wins']}")
    svg.append("</svg>")
    name = "win_rate_delta" if delta else "win_rate_comparison"
    bitmap.save(output / (name+".png"))
    with (output / (name+".svg")).open("x") as f:
        f.write("\n".join(svg))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=study.OUTPUT / "confirmed/measurement")
    parser.add_argument("--output", type=Path, default=study.OUTPUT / "analysis_final")
    args = parser.parse_args()
    manifest = json.loads((args.source / "manifest.json").read_text())
    records = [json.loads(line) for line in (args.source / "runs.jsonl").open()]
    grouped = defaultdict(list)
    keys = set()
    for r in records:
        key = (r["case"], r["seed"])
        if key in keys:
            raise ValueError("戦闘の重複")
        keys.add(key)
        grouped[r["case"]].append(r)
    args.output.mkdir(parents=True, exist_ok=False)
    summaries, indexed, profiles = [], {}, {}
    for case in manifest["cases"]:
        row, tactic = case["profile"], case["tactic"]
        name = f"{row['profile_id']}-{tactic}-u{case['use_scale']}"
        summary = {"floor": row["floor"], "job": row["job"], "tactic": tactic,
                   "growth_version": row["growth_version"], "case": name,
                   **aggregate(grouped[name], row["evaluation_trials"])}
        summaries.append(summary)
        indexed[row["floor"], row["job"], tactic, row["growth_version"]] = (summary, grouped[name])
        profiles[row["floor"], row["job"], row["growth_version"]] = row
    unknown = set(grouped) - {s["case"] for s in summaries}
    if unknown:
        raise ValueError(f"manifestにない条件: {unknown}")
    comparisons, stats, floors = [], [], []
    lines = ["# Stage 6-A 全7職業・対応比較", "", "旧/新とも今回の現行エンジン実測。表の区間はWilson95%。5seed・補正なし。", "",
             "階層合計は異なる7職業の記述合計であり、独立35試行として区間や適合判定をしない。", ""]
    for floor in range(1, 13):
        lines += [f"## {floor}階", "", "|職業|戦術|旧 勝/試行・率・95%区間|新 勝/試行・率・95%区間|差pt|負→勝 / 勝→負|",
                  "|---|---|---|---|---:|---|"]
        for job in JOBS:
            old, new = profiles[floor, job, "old"], profiles[floor, job, "new"]
            stat = {"floor": floor, "job": job, "race": old["race"], "level": old["level"],
                    "reincarnations": old["reincarnations"], "growth_seed": old["seed"], "legacy_points": 0,
                    "equipment": old["equipment"], "permanent_skill_codes": old["permanent_skill_codes"],
                    "inheritance_history": old["inheritance_history"], "inheritance_remaining": old["inheritance_remaining"],
                    "tactics": old["tactics"], "attribute_weights": old["attribute_weights"],
                    "max_st": old["max_st"], "start_st": old["start_st"]}
            for field in ("stats", "attributes", "combat_start"):
                for key in old[field]:
                    stat.update({f"old_{field}_{key}": old[field][key], f"new_{field}_{key}": new[field][key],
                                 f"delta_{field}_{key}": new[field][key]-old[field][key]})
            for key in ("power", "initial_points", "stat_growth_draws", "attribute_growth_draws"):
                stat.update({"old_"+key: old[key], "new_"+key: new[key], "delta_"+key: new[key]-old[key]})
            stats.append(stat)
            for label in ("B", old["selected_c"]):
                a, ar = indexed[floor, job, label, "old"]
                b, br = indexed[floor, job, label, "new"]
                delta = (b["win_rate"]-a["win_rate"])*100 if a["valid"] and b["valid"] else None
                comparison = {"floor": floor, "job": job, "tactic": label,
                              "old_wins": a["wins"], "old_valid": a["valid"], "old_rate": a["win_rate"], "old_wilson95": a["wilson95"],
                              "new_wins": b["wins"], "new_valid": b["valid"], "new_rate": b["win_rate"], "new_wilson95": b["wilson95"],
                              "delta_pp": delta, "complete": a["complete"] and b["complete"], **paired(ar, br)}
                comparisons.append(comparison)
                lines.append(f"|{JOBS[job]}|{label}|{rate(a)}|{rate(b)}|{delta:+.0f}" if delta is not None else f"|{JOBS[job]}|{label}|{rate(a)}|{rate(b)}|未測定")
                lines[-1] += f"|{comparison['loss_to_win']} / {comparison['win_to_loss']}|"
        for tactic in ("B", "C"):
            row = {"floor": floor, "tactic": tactic}
            for version in ("old", "new"):
                selected = [s for s in summaries if s["floor"] == floor and s["growth_version"] == version
                            and (s["tactic"] == "B") == (tactic == "B")]
                wins, valid = sum(s["wins"] for s in selected), sum(s["valid"] for s in selected)
                rates = [s["win_rate"] for s in selected if s["valid"]]
                row.update({version+"_wins": wins, version+"_valid": valid, version+"_rate": wins/valid if valid else None,
                            version+"_gap_pp": (max(rates)-min(rates))*100 if len(rates) == 7 else None,
                            version+"_all_win_jobs": [s["job"] for s in selected if s["complete"] and s["wins"] == s["valid"]],
                            version+"_zero_win_jobs": [s["job"] for s in selected if s["complete"] and not s["wins"]]})
            row["delta_pp"] = (row["new_rate"]-row["old_rate"])*100 if row["new_valid"] and row["old_valid"] else None
            floors.append(row)
    for name, rows in (("conditions", summaries), ("comparison", comparisons), ("status_comparison", stats), ("floors", floors)):
        csv_rows(args.output / (name+".csv"), rows)
    with (args.output / "TABLES.md").open("x") as f:
        f.write("\n".join(lines)+"\n")
    result = {"conditions": summaries, "comparison": comparisons, "floors": floors,
              "planned": sum(s["planned"] for s in summaries), "completed": len(records),
              "exceptions": sum(s["exceptions"] for s in summaries), "missing": sum(s["missing"] for s in summaries),
              "draws": sum(s["draws"] for s in summaries), "loop_limits": sum(s["loop_limits"] for s in summaries),
              "both_hp_zero": sum(s.get("both_hp_zero", 0) for s in summaries),
              "battle_seconds": sum(r["elapsed_seconds"] for r in records),
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (args.source/"runs.jsonl", args.source/"manifest.json", Path(__file__))}}
    study.write_json(args.output / "results.json", result)
    charts(args.output, comparisons)
    charts(args.output, comparisons, delta=True)
    print(json.dumps({k: result[k] for k in ("planned", "completed", "exceptions", "missing", "draws", "loop_limits", "both_hp_zero", "battle_seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
