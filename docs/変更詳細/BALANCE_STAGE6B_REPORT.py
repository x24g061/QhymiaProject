"""Stage6-B: B中心距離/C許容帯/交差/職業格差を分離した集計と図。"""
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
study = load("stage6b_report_study", HERE / "BALANCE_STAGE6B_RUN.py")
prior = load("stage6b_prior_report", HERE / "BALANCE_STAGE6A_REPORT.py")
JOBS = prior.JOBS


def csv_rows(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)


def phase_summary(source, extra=None):
    """欠測・例外は別計上。選択後の合算と独立確認標本は別の呼出しにする。"""
    manifests = [json.loads((p / "manifest.json").read_text()) for p in [source]+list(extra or [])]
    runs = [json.loads(line) for p in [source]+list(extra or []) for line in (p / "runs.jsonl").open()]
    cases, planned, grouped = {}, Counter(), defaultdict(list)
    manifest_keys = []
    for manifest in manifests:
        phase_keys = set()
        for case in manifest["cases"]:
            row, label = case["profile"], case["tactic"]
            key = f"{row['profile_id']}-{label}-u{case['use_scale']}"
            if key in cases:
                old = cases[key][0]
                for field in study.previous.FIXED+study.previous.REPLAY_FIELDS+("tactics", "boss_override"):
                    if old[field] != row[field]:
                        raise ValueError("測定段階で固定条件が変わっています")
            cases[key] = (row, label)
            planned[key] += row["evaluation_trials"]
            phase_keys.add(key)
        manifest_keys.append(phase_keys)
    if extra:
        # 追加確認されなかった5seed候補を14seed対照と比較しない。
        # 合算は両段階に共通する候補/対照条件だけ、全員同じseed集合に限定。
        common = set.intersection(*manifest_keys)
        cases = {key: value for key, value in cases.items() if key in common}
        planned = Counter({key: value for key, value in planned.items() if key in common})
        runs = [r for r in runs if r["case"] in common]
    seen = set()
    for r in runs:
        key = (r["case"], r["seed"])
        if key in seen or r["case"] not in cases:
            raise ValueError("戦闘の重複またはmanifest外条件")
        seen.add(key)
        grouped[r["case"]].append(r)
    summaries, indexed, variants = [], {}, {}
    for key, (row, label) in cases.items():
        summary = {"candidate": row["candidate"], "floor": row["floor"], "job": row["job"], "tactic": label,
                   "override": row["boss_override"], **prior.aggregate(grouped[key], planned[key])}
        valid = [r for r in grouped[key] if not r.get("exception")]
        for side in ("player", "boss"):
            summary[side+"_all_active_exhausted"] = sum(r["diagnostics"][side]["all_active_exhausted"] for r in valid)
            by_skill = Counter()
            for r in valid:
                for event in r["hp_events"]:
                    if event["source"] == side and event["target"] != side and event["kind"] != "heal":
                        by_skill[event["skill"] or event["kind"]] += event["amount"]
            summary[side+"_opponent_damage_by_skill"] = {k: v/len(valid) for k, v in by_skill.items()} if valid else {}
        summaries.append(summary)
        indexed[row["candidate"], row["job"], label] = (summary, grouped[key])
        variants[row["candidate"]] = row
    metrics, comparisons = [], []
    for candidate, row in variants.items():
        cells = [s for s in summaries if s["candidate"] == candidate]
        metric = {"candidate": candidate, "floor": row["floor"], "override": row["boss_override"],
                  "control": not row["boss_override"], "complete": len(cells) == 14 and all(s["complete"] for s in cells)}
        for label in ("B", "C"):
            selected = [s for s in cells if (s["tactic"] == "B") == (label == "B")]
            n, wins = sum(s["valid"] for s in selected), sum(s["wins"] for s in selected)
            rates = [s["win_rate"] for s in selected if s["win_rate"] is not None]
            metric.update({label+"_wins": wins, label+"_valid": n, label+"_rate": wins/n if n else None,
                           label+"_gap": max(rates)-min(rates) if len(rates) == 7 else None,
                           label+"_zero_jobs": [s["job"] for s in selected if s["complete"] and s["wins"] == 0],
                           label+"_all_win_jobs": [s["job"] for s in selected if s["complete"] and s["wins"] == s["valid"]],
                           label+"_job_wins": {s["job"]: s["wins"] for s in selected},
                           label+"_job_trials": {s["job"]: s["valid"] for s in selected}})
            # 候補の7職は等試行。以下は条件等重みの記述平均で、poolのWilsonを作らない。
            for field in ("player_mean_actions", "boss_mean_actions", "mean_loops", "player_damage_to_opponent",
                          "player_damage_taken_total", "player_healing_total", "player_normal_attacks",
                          "player_skills_total", "player_mp_shortages"):
                values = [s[field] for s in selected if s.get(field) is not None]
                metric[label+"_"+field] = statistics.mean(values) if values else None
            for field in ("player_reached_healing_shield", "player_all_active_exhausted", "both_hp_zero"):
                metric[label+"_"+field] = sum(s.get(field, 0) for s in selected)
        if metric["B_rate"] is not None and metric["C_rate"] is not None and metric["complete"]:
            metric.update(study.selection_metrics(row["floor"], metric["B_rate"], metric["C_rate"],
                len(metric["B_zero_jobs"])+len(metric["C_zero_jobs"]), max(metric["B_gap"], metric["C_gap"]),
                statistics.mean(s["boss_mean_actions"] for s in cells)))
        else:
            metric.update(b_center_distance=None, c_band_distance=None, c_band_descriptive=None,
                          rate_penalty=None, zero_job_cells=None, max_job_gap=None,
                          boss_mean_actions=None, crossing_b_minus_c=None)
        reference = study.C_REFERENCE[row["floor"]]
        metric["c_reference_delta"] = metric["C_rate"]-reference if reference is not None and metric["C_rate"] is not None else None
        metric["jobs_b_above_c"] = sum(indexed[candidate, j, "B"][0]["win_rate"] >
            indexed[candidate, j, study.profiles()[row["floor"], j]["selected_c"]][0]["win_rate"]
            for j in JOBS) if metric["complete"] else None
        metrics.append(metric)
        control = study.candidate_id(row["floor"])
        for job in JOBS:
            for label in ("B", study.profiles()[row["floor"], job]["selected_c"]):
                target, target_runs = indexed[candidate, job, label]
                baseline, baseline_runs = indexed[control, job, label]
                comparisons.append({"candidate": candidate, "floor": row["floor"], "job": job, "tactic": label,
                    "control_wins": baseline["wins"], "control_valid": baseline["valid"], "control_rate": baseline["win_rate"],
                    "candidate_wins": target["wins"], "candidate_valid": target["valid"], "candidate_rate": target["win_rate"],
                    "candidate_wilson95": target["wilson95"], "control_wilson95": baseline["wilson95"],
                    "delta_pp": (target["win_rate"]-baseline["win_rate"])*100 if target["valid"] and baseline["valid"] else None,
                    "complete": target["complete"] and baseline["complete"], **prior.paired(baseline_runs, target_runs)})
    return {"candidates": metrics, "conditions": summaries, "comparison": comparisons,
            "planned": sum(planned.values()), "completed": len(runs),
            "exceptions": sum(s["exceptions"] for s in summaries), "missing": sum(s["missing"] for s in summaries),
            "draws": sum(s["draws"] for s in summaries), "loop_limits": sum(s["loop_limits"] for s in summaries),
            "battle_seconds": sum(r["elapsed_seconds"] for r in runs)}


class Canvas:
    def __init__(self, width, height):
        from PIL import Image, ImageDraw, ImageFont
        self.image = Image.new("RGB", (width, height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s) for s in (12, 15, 20)}
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                    '<rect width="100%" height="100%" fill="white"/>']
    def text(self, x, y, text, size=12, color="#222222"):
        self.draw.text((x, y), str(text), font=self.fonts[size], fill=color)
        self.svg.append(f'<text x="{x}" y="{y+size}" font-family="DejaVu Sans,sans-serif" font-size="{size}" fill="{color}">{escape(str(text))}</text>')
    def line(self, x, y, xx, yy, color="#aaaaaa", width=1):
        self.draw.line((x, y, xx, yy), fill=color, width=width)
        self.svg.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{color}" stroke-width="{width}"/>')
    def rect(self, x, y, xx, yy, color):
        self.draw.rectangle((x, y, xx, yy), fill=color)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{xx-x}" height="{yy-y}" fill="{color}"/>')
    def point(self, x, y, color):
        self.draw.ellipse((x-4, y-4, x+4, y+4), fill=color)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    def save(self, directory, name):
        self.image.save(directory / (name+".png"))
        with (directory / (name+".svg")).open("x") as f:
            f.write("\n".join(self.svg+["</svg>"]))


def design_chart(output):
    c = Canvas(1120, 570)
    c.text(20, 12, "Stage6-B design: B center / C reference / C permitted band", 20)
    c.text(20, 45, "C reference is directional; floor12 has a 25-60% BAND, not a 25% point target.", 15)
    xp, yp, width, height = 80, 100, 980, 360
    x = lambda f: xp+(f-1)*width/11
    y = lambda rate: yp+height*(1-rate)
    c.rect(x(7)-15, y(.60), x(12)+15, y(.25), "#e1f0dd")
    for tick in (0, .25, .5, .6, .75, 1):
        c.line(xp, y(tick), xp+width, y(tick), "#dddddd")
        c.text(27, y(tick)-7, f"{tick:.0%}")
    for f in range(1, 13):
        c.text(x(f)-5, yp+height+10, f)
        c.point(x(f), y(study.B_TARGET[f]), "#2166ac")
        if f > 1:
            c.line(x(f-1), y(study.B_TARGET[f-1]), x(f), y(study.B_TARGET[f]), "#2166ac", 3)
        ref = study.C_REFERENCE[f]
        if ref is not None:
            c.point(x(f), y(ref), "#d95f02")
            if f > 1:
                c.line(x(f-1), y(study.C_REFERENCE[f-1]), x(f), y(ref), "#d95f02", 2)
    c.line(x(12), y(.60), x(12), y(.25), "#d95f02", 4)
    c.text(75, 510, "Blue: B center. Orange: C reference (1-11). Green: C band applied to focus floors 7/8/12.", 15)
    c.text(75, 538, "Design lines cross between floor7 and floor8. Actual B>C is assessed separately, never forced.")
    c.save(output, "target_design")


def short_name(metric):
    if metric["control"]:
        return "control"
    field, value = next(iter(metric["override"].items()))
    return {"max_hp": "HP", "agility": "AGI", "strength": "STR", "intelligence": "INT"}[field]+str(value)


def candidate_chart(output, data, name, title):
    c = Canvas(1680, 1110)
    c.text(20, 12, title, 20)
    c.text(20, 43, "B blue / C orange; pale green=C 25-60%. Lines: B center (blue), C reference (orange, absent at floor12).", 15)
    c.text(20, 69, "Left: descriptive equal-job win rates. Right: max-min job gap; counts show observed zero-win job/tactic cells.")
    for i, floor in enumerate(study.GRID):
        rows = [m for m in data["candidates"] if m["floor"] == floor]
        y0, xp, width = 120+i*320, 190, 570
        c.text(20, y0, f"Floor {floor}", 20)
        y = lambda r: y0+240*(1-r)
        c.rect(xp-20, y(.60), xp+width+20, y(.25), "#e1f0dd")
        for r in (0, .25, .5, .75, 1):
            c.line(xp-20, y(r), xp+width+20, y(r), "#dddddd")
            c.text(115, y(r)-7, f"{r:.0%}")
        c.line(xp-20, y(study.B_TARGET[floor]), xp+width+20, y(study.B_TARGET[floor]), "#2166ac", 2)
        if study.C_REFERENCE[floor] is not None:
            c.line(xp-20, y(study.C_REFERENCE[floor]), xp+width+20, y(study.C_REFERENCE[floor]), "#d95f02", 1)
        for k, row in enumerate(rows):
            x = xp+k*width/max(1, len(rows)-1)
            if not row["complete"]:
                continue
            c.point(x-5, y(row["B_rate"]), "#2166ac")
            c.point(x+5, y(row["C_rate"]), "#d95f02")
            c.text(x-32, y0+250, short_name(row))
            yy = y0+10+k*27
            c.text(850, yy-6, short_name(row))
            c.line(990, yy, 990+row["B_gap"]*420, yy, "#2166ac", 7)
            c.line(990, yy+8, 990+row["C_gap"]*420, yy+8, "#d95f02", 7)
            c.text(1430, yy-6, f"{row['B_gap']:.0%}/{row['C_gap']:.0%}; zero {row['zero_job_cells']}")
    c.save(output, name)


def job_chart(output, data):
    rows = data["conditions"]
    c = Canvas(1250, 110+len(rows)//7*39)
    c.text(20, 10, "Independent confirmation: job-specific wins/trials", 20)
    c.text(20, 42, "Cells are observed proportions, not proven population win rates. Wilson intervals: TABLES.md.")
    for j, job in enumerate(JOBS):
        c.text(380+j*118, 75, job.title()[:10])
    groups = list(dict.fromkeys((r["candidate"], "B" if r["tactic"] == "B" else "C") for r in rows))
    for i, (candidate, label) in enumerate(groups):
        yy = 106+i*39
        c.text(20, yy+8, candidate+" "+label, 15)
        for j, job in enumerate(JOBS):
            r = next(r for r in rows if r["candidate"] == candidate and r["job"] == job and (r["tactic"] == "B") == (label == "B"))
            rate = r["win_rate"]
            color = "#eeeeee" if rate is None else "#"+"".join(f"{int(a+(b-a)*rate):02x}" for a, b in ((247, 112), (229, 180), (220, 220)))
            xx = 370+j*118
            c.rect(xx, yy, xx+110, yy+32, color)
            c.text(xx+20, yy+8, f"{r['wins']}/{r['valid']}")
    c.save(output, "confirm_jobs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=study.OUTPUT)
    parser.add_argument("--output", type=Path, default=study.OUTPUT / "analysis")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    result = {"screen": phase_summary(args.source / "screen"), "confirm": phase_summary(args.source / "confirm"),
              "combined_exploratory": phase_summary(args.source / "screen", [args.source / "confirm"])}
    lines = ["# Stage6-B 重点3階・全7職業の勝率表", "", "主評価は追加seedのconfirm。screenとの合算は選択後の探索的補助集計。", "",
             "各職業セルはWilson95%、多重比較補正なし。階層合計は記述値で独立二項標本として区間を付けない。", ""]
    candidate_lines = ["# ボス候補の比較", "", "C帯内は帯外距離0。C参考線との差やB/C交差を不合格基準へ混ぜない。", ""]
    for phase, data in result.items():
        for name in ("conditions", "candidates", "comparison"):
            csv_rows(output / f"{phase}_{name}.csv", data[name])
        candidate_lines += [f"## {phase}", "", "|階|候補|B勝/試行|C勝/試行|B中心差pt|C帯外距離pt|C帯内（記述）|B−C pt|B/C職業最大差|全敗職セル数|",
                            "|---:|---|---:|---:|---:|---:|---|---:|---|---:|"]
        for m in data["candidates"]:
            if not m["complete"]:
                candidate_lines.append(f"|{m['floor']}|{m['candidate']}|未完|未完|||||||")
                continue
            candidate_lines.append(f"|{m['floor']}|{m['candidate']}|{m['B_wins']}/{m['B_valid']}|{m['C_wins']}/{m['C_valid']}|"
                f"{m['b_center_distance']*100:.1f}|{m['c_band_distance']*100:.1f}|{m['c_band_descriptive']}|"
                f"{m['crossing_b_minus_c']*100:+.1f}|{m['B_gap']:.0%}/{m['C_gap']:.0%}|{m['zero_job_cells']}|")
        lines += [f"## {phase}", "", "|階|候補|職業|戦術|勝/試行・Wilson95%|予定/欠測/例外|", "|---:|---|---|---|---|---|"]
        for s in data["conditions"]:
            lines.append(f"|{s['floor']}|{s['candidate']}|{JOBS[s['job']]}|{s['tactic']}|{prior.rate(s)}|"
                         f"{s['planned']}/{s['missing']}/{s['exceptions']}|")
    for filename, content in (("TABLES.md", lines), ("CANDIDATES.md", candidate_lines)):
        with (output / filename).open("x") as f:
            f.write("\n".join(content)+"\n")
    result["source_sha256"] = {str(p.relative_to(study.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), HERE / "BALANCE_STAGE6B_RUN.py", args.source / "selection.json", args.source / "selection_reviewed.json",
                  args.source / "screen/runs.jsonl", args.source / "confirm/runs.jsonl")}
    study.previous.write_json(output / "results.json", result)
    design_chart(output)
    candidate_chart(output, result["screen"], "screen_candidates", "Screening: all preregistered single-stat candidates")
    candidate_chart(output, result["confirm"], "confirm_candidates", "Independent added seeds: selected candidates and shared controls")
    job_chart(output, result["confirm"])
    print(json.dumps({phase: {k: data[k] for k in ("planned", "completed", "missing", "exceptions", "draws", "loop_limits", "battle_seconds")}
                      for phase, data in result.items() if phase != "source_sha256"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
