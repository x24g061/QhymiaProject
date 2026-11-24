"""Stage6-C集計・候補選択・因子間相互作用・スキル構成引継ぎ。DB接続なし。"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
study = load("stage6c_analyze_study", HERE / "run.py")
prior = load("stage6c_prior_report", HERE.parent / "BALANCE_STAGE6A_REPORT.py")
graphics = load("stage6c_graphics", HERE.parent / "BALANCE_STAGE6B_REPORT.py")
JOBS = prior.JOBS


def csv_rows(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def score(b, c):
    return abs(b-.35)+max(.25-c, 0, c-.60)


def phase_summary(path):
    manifest = json.loads((path / "manifest.json").read_text())
    runs = study.records(path / "runs.jsonl")
    grouped, cases, seen = defaultdict(list), {}, set()
    for c in manifest["cases"]:
        r, label = c["profile"], c["tactic"]
        cases[f"{r['profile_id']}-{label}-u{c['use_scale']}"] = (r, label)
    for r in runs:
        key = (r["case"], r["seed"])
        if key in seen or r["case"] not in cases:
            raise ValueError("戦闘重複/manifest外条件")
        seen.add(key)
        grouped[r["case"]].append(r)
    conditions, indexed, variants = [], {}, {}
    for key, (row, label) in cases.items():
        records = grouped[key]
        valid = [r for r in records if not r.get("exception")]
        summary = {"candidate": row["candidate"], "hp": row["boss_override"]["max_hp"],
                   "agi": row["boss_override"]["agility"], "job": row["job"], "tactic": label,
                   **prior.aggregate(records, row["evaluation_trials"])}
        mean = lambda fn: statistics.mean(fn(r) for r in valid) if valid else None
        for field in ("boss_direct_attack_actions", "boss_attack_skill_actions", "boss_threatening_direct_actions",
                      "boss_support_actions", "boss_died_before_attack_skill", "boss_died_before_any_direct_attack",
                      "boss_died_without_threatening_direct_action", "counter_damage", "player_direct_damage_in_support_windows"):
            summary[field] = mean(lambda r: r["titan_analysis"][field])
        for side in ("player", "boss"):
            summary[side+"_all_exhausted_rate"] = mean(lambda r: r["titan_analysis"]["all_active_exhausted"][side])
            summary[side+"_initial_hp"] = valid[0]["initial"][side]["hp"] if valid else None
            summary[side+"_initial_mp"] = valid[0]["initial"][side]["mp"] if valid else None
        for field in ("first_attack_skill_boss_ordinal", "first_attack_skill_tick"):
            values = [r["titan_analysis"][field] for r in valid if r["titan_analysis"][field] is not None]
            summary[field+"_conditional_mean"] = statistics.mean(values) if values else None
            summary[field+"_reached_count"] = len(values)
        total_heals = sum(r["titan_analysis"]["player_healing_shield_actions"] for r in valid)
        full_heals = sum(r["titan_analysis"]["player_healing_shield_at_full"] for r in valid)
        summary.update(shield_uses=total_heals, shield_at_full=full_heals,
                       shield_full_fraction=full_heals/total_heals if total_heals else None)
        summary["boss_skill_attempts"] = {}
        for code in study.SKILLS:
            summary["boss_skill_attempts"][code] = dict(sum((Counter(r["titan_analysis"]["skill_attempts"]["boss"].get(code, {})) for r in valid), Counter()))
        summary["boss_damage_by_skill"] = {k: v/len(valid) for k, v in sum((Counter(r["titan_analysis"]["boss_damage_by_skill"]) for r in valid), Counter()).items()} if valid else {}
        summary["poison_damage_to_boss"] = mean(lambda r: r["player"]["damage_dealt"].get("poison", 0))
        summary["incoming_overlap_damage"] = mean(lambda r: r["titan_analysis"]["boss_incoming_overlap"].get("damage", 0))
        conditions.append(summary)
        indexed[row["candidate"], row["job"], label] = (summary, records)
        variants[row["candidate"]] = row
    metrics, comparisons = [], []
    for candidate, row in variants.items():
        cells = [s for s in conditions if s["candidate"] == candidate]
        m = {"candidate": candidate, "hp": row["boss_override"]["max_hp"], "agi": row["boss_override"]["agility"],
             "control": row["boss_override"] == study.CONTROL, "complete": len(cells) == 14 and all(s["complete"] for s in cells)}
        for label in ("B", "C"):
            group = [s for s in cells if (s["tactic"] == "B") == (label == "B")]
            valid, wins = sum(s["valid"] for s in group), sum(s["wins"] for s in group)
            rates = [s["win_rate"] for s in group if s["win_rate"] is not None]
            m.update({label+"_wins": wins, label+"_valid": valid, label+"_rate": wins/valid if valid else None,
                      label+"_gap": max(rates)-min(rates) if len(rates) == 7 else None,
                      label+"_zero_jobs": [s["job"] for s in group if s["complete"] and not s["wins"]],
                      label+"_all_win_jobs": [s["job"] for s in group if s["complete"] and s["wins"] == s["valid"]],
                      label+"_job_wins": {s["job"]: s["wins"] for s in group}})
            for field in ("mean_loops", "player_mean_actions", "boss_mean_actions", "player_damage_to_opponent",
                "player_damage_taken_total", "player_healing_total", "player_initial_hp", "boss_direct_attack_actions",
                "boss_threatening_direct_actions", "boss_attack_skill_actions", "boss_support_actions",
                "boss_died_before_attack_skill", "boss_died_before_any_direct_attack", "boss_died_without_threatening_direct_action",
                "poison_damage_to_boss", "player_all_exhausted_rate", "player_mp_shortages", "counter_damage",
                "player_direct_damage_in_support_windows", "incoming_overlap_damage"):
                values = [s[field] for s in group if s.get(field) is not None]
                m[label+"_"+field] = statistics.mean(values) if values else None
            uses, full = sum(s["shield_uses"] for s in group), sum(s["shield_at_full"] for s in group)
            m[label+"_shield_uses"], m[label+"_shield_full"] = uses, full
            m[label+"_shield_full_fraction"] = full/uses if uses else None
        if m["complete"]:
            m.update(b_center_distance=abs(m["B_rate"]-.35), c_band_distance=max(.25-m["C_rate"], 0, m["C_rate"]-.60),
                     c_band_descriptive=.25 <= m["C_rate"] <= .60, b_minus_c=m["B_rate"]-m["C_rate"],
                     rate_penalty=score(m["B_rate"], m["C_rate"]), zero_job_cells=len(m["B_zero_jobs"])+len(m["C_zero_jobs"]),
                     max_gap=max(m["B_gap"], m["C_gap"]),
                     exhaustion_mean=(m["B_player_all_exhausted_rate"]+m["C_player_all_exhausted_rate"])/2,
                     no_threat_mean=(m["B_boss_died_without_threatening_direct_action"]+m["C_boss_died_without_threatening_direct_action"])/2)
        else:
            m.update(b_center_distance=None, c_band_distance=None, c_band_descriptive=None, b_minus_c=None,
                     rate_penalty=None, zero_job_cells=None, max_gap=None, exhaustion_mean=None, no_threat_mean=None)
        metrics.append(m)
        for job in JOBS:
            for label in ("B", study.profiles()[job]["selected_c"]):
                target, tr = indexed[candidate, job, label]
                control, cr = indexed[study.cid(50000, 180), job, label]
                comparisons.append({"candidate": candidate, "job": job, "tactic": label,
                    "control_wins": control["wins"], "control_valid": control["valid"], "control_rate": control["win_rate"],
                    "candidate_wins": target["wins"], "candidate_valid": target["valid"], "candidate_rate": target["win_rate"],
                    "wilson95": target["wilson95"], "control_wilson95": control["wilson95"],
                    "delta_pp": (target["win_rate"]-control["win_rate"])*100 if target["valid"] and control["valid"] else None,
                    **prior.paired(cr, tr)})
    return {"candidates": metrics, "conditions": conditions, "comparisons": comparisons,
            "planned": sum(r["evaluation_trials"] for r, _ in cases.values()), "completed": len(runs),
            "exceptions": sum(s["exceptions"] for s in conditions), "missing": sum(s["missing"] for s in conditions),
            "draws": sum(s["draws"] for s in conditions), "loop_limits": sum(s["loop_limits"] for s in conditions),
            "battle_seconds": sum(r["elapsed_seconds"] for r in runs)}


def shortlist(metrics):
    eligible = [m for m in metrics if m["complete"] and not m["control"]]
    if not eligible:
        raise ValueError("完了した非対照候補がありません")
    first = min(eligible, key=lambda m: (m["rate_penalty"], m["zero_job_cells"], m["max_gap"], m["exhaustion_mean"], m["candidate"]))
    pool = [m for m in eligible if m["rate_penalty"] <= first["rate_penalty"]+.20+1e-9]
    picks = [(first, "率の距離を重視")]
    for key, reason in ((lambda m: (m["zero_job_cells"], m["max_gap"], m["rate_penalty"], m["candidate"]), "職業格差を重視"),
                        (lambda m: (m["exhaustion_mean"], m["no_threat_mean"], m["rate_penalty"], m["candidate"]), "枯渇と脅威攻撃到達を重視")):
        other = [m for m in pool if m["candidate"] not in {p[0]["candidate"] for p in picks}]
        if other:
            picks.append((min(other, key=key), reason))
    return {"variants": [{"id": m["candidate"], "hp": m["hp"], "agi": m["agi"]} for m, _ in picks],
            "reasons": [{"candidate": m["candidate"], "reason": reason, "metrics": m} for m, reason in picks],
            "policy": "C帯内距離0、B中心距離と帯外距離を参照。最良から20pt以内のみで格差/戦闘内容を比較。交差は加点しない。"}


def select(data):
    if len(data["candidates"]) != 20 or not all(m["complete"] for m in data["candidates"]):
        raise ValueError("20組のスクリーニング完了が必要")
    final = shortlist(data["candidates"])
    lookup = {(m["hp"], m["agi"]): m for m in data["candidates"]}
    hp_pairs, agi_pairs = [], []
    def crosses(a, b):
        return (a["B_rate"]-.35)*(b["B_rate"]-.35) <= 0 or (a["C_rate"]-.60)*(b["C_rate"]-.60) <= 0
    for agi in study.AGIS:
        for lo, hi in zip(study.HPS, study.HPS[1:]):
            a, b = lookup[lo, agi], lookup[hi, agi]
            if crosses(a, b):
                hp_pairs.append((min(a["rate_penalty"], b["rate_penalty"]), (lo+hi)//2, agi, [a["candidate"], b["candidate"]]))
    for hp in study.HPS:
        for lo, hi in zip(study.AGIS, study.AGIS[1:]):
            a, b = lookup[hp, lo], lookup[hp, hi]
            if crosses(a, b):
                agi_pairs.append((min(a["rate_penalty"], b["rate_penalty"]), hp, (lo+hi)//2, [a["candidate"], b["candidate"]]))
    new, evidence = [], []
    for sequence, axis in ((hp_pairs, "HP"), (agi_pairs, "AGI")):
        for penalty, hp, agi, parents in sorted(sequence)[:2]:
            variant = {"id": study.cid(hp, agi), "hp": hp, "agi": agi}
            if variant["id"] not in {v["id"] for v in new}:
                new.append(variant)
                evidence.append({"candidate": variant["id"], "axis": axis, "parents": parents,
                                 "endpoint_min_rate_penalty": penalty, "reason": "実測のB中心またはC上限を挟む隣接点の中間"})
    anchors = [{"id": study.cid(50000, 180), "hp": 50000, "agi": 180}, final["variants"][0]]
    variants = list({v["id"]: v for v in anchors+new}.values()) if new else []
    return {"grid_shortlist": final, "refine_variants": variants, "new_midpoints": new, "evidence": evidence,
            "note": "追加候補はscreen後の実測選択。点推定を正式採用の確定根拠にしない。"}


def interaction_rows(runs):
    valid = [r for r in runs if not r.get("exception")]
    lookup = {(r["evaluation_full_boss"]["max_hp"], r["evaluation_full_boss"]["agility"],
               r["job"], r["tactic"], r["seed"]): r for r in valid}
    seeds = sorted({r["seed"] for r in valid})
    rows = []
    for h0, h1 in zip(study.HPS, study.HPS[1:]):
        for a0, a1 in zip(study.AGIS, study.AGIS[1:]):
            for job in JOBS:
                for label in ("B", study.profiles()[job]["selected_c"]):
                    for seed in seeds:
                        keys = [(h, a, job, label, seed) for h, a in ((h0, a0), (h0, a1), (h1, a0), (h1, a1))]
                        if any(k not in lookup for k in keys):
                            continue
                        r00, r01, r10, r11 = [lookup[k] for k in keys]
                        w00, w01, w10, w11 = [int(r["winner"] == "player") for r in (r00, r01, r10, r11)]
                        rows.append({"hp_low": h0, "hp_high": h1, "agi_low": a0, "agi_high": a1,
                            "job": job, "tactic": label, "seed": seed,
                            "win_h0a0": w00, "win_h0a1": w01, "win_h1a0": w10, "win_h1a1": w11,
                            "agi_delta_low_hp": w01-w00, "agi_delta_high_hp": w11-w10,
                            "hp_delta_low_agi": w10-w00, "hp_delta_high_agi": w11-w01,
                            "interaction": (w11-w10)-(w01-w00),
                            "boss_actions_interaction": r11["boss"]["actions"]-r10["boss"]["actions"]-r01["boss"]["actions"]+r00["boss"]["actions"],
                            "loops_interaction": r11["loops"]-r10["loops"]-r01["loops"]+r00["loops"]})
    groups = defaultdict(list)
    for r in rows:
        groups[r["hp_low"], r["hp_high"], r["agi_low"], r["agi_high"], "B" if r["tactic"] == "B" else "C"].append(r)
    summary = []
    for key, values in groups.items():
        m = dict(zip(("hp_low", "hp_high", "agi_low", "agi_high", "tactic"), key))
        m.update(paired_job_seeds=len(values), positive_interactions=sum(v["interaction"] > 0 for v in values),
                 negative_interactions=sum(v["interaction"] < 0 for v in values))
        for field in ("agi_delta_low_hp", "agi_delta_high_hp", "hp_delta_low_agi", "hp_delta_high_agi", "interaction"):
            m[field+"_pp"] = statistics.mean(v[field] for v in values)*100
        m["boss_actions_interaction_mean"] = statistics.mean(v["boss_actions_interaction"] for v in values)
        m["loops_interaction_mean"] = statistics.mean(v["loops_interaction"] for v in values)
        summary.append(m)
    return rows, summary


def effect_windows(runs):
    result = []
    fields = {"steel_body": "steel_body_turns", "solid_stance": "solid_stance_turns", "counter_stance": "counter_stance_turns"}
    for r in runs:
        if r.get("exception"):
            continue
        boss = [f for f in r["skill_trace"]["frames"] if f["side"] == "boss"]
        for i, frame in enumerate(boss):
            if frame["code"] not in fields:
                continue
            field = fields[frame["code"]]
            end = next((j for j in range(i+1, len(boss)) if boss[j]["finished"]["boss"][field] == 0), None)
            result.append({"candidate": r["candidate"], "job": r["job"], "tactic": r["tactic"], "seed": r["seed"],
                           "skill": frame["code"], "start_tick": frame["tick"], "start_boss_ordinal": i+1,
                           "end_tick": boss[end]["tick"] if end is not None else None,
                           "own_actions_until_clear": end-i if end is not None else None,
                           "censored_by_battle_end": end is None,
                           "after_cast_turns": frame["skill_peaks"][-1]["after_skill"]["boss"][field],
                           "after_cast_finish_turns": frame["finished"]["boss"][field]})
    return result


def heatmaps(output, metrics):
    c = graphics.Canvas(1300, 700)
    c.text(20, 10, "Titan AGI x HP: actual screening win rates", 20)
    c.text(20, 43, "All 20 combinations use the same new seeds. C 25-60% is a permitted band; 25% is not a point target.", 15)
    c.text(20, 70, "Counts pool seven fixed jobs descriptively. Job-specific Wilson intervals and extreme cells are in TABLES.md.")
    for panel, label in enumerate(("B", "C")):
        x0 = 20+panel*650
        c.text(x0+235, 105, label+(" center 35%" if label == "B" else " band 25-60%"), 20)
        for col, hp in enumerate(study.HPS):
            c.text(x0+130+col*125, 150, f"HP {hp//1000}k")
        for row, agi in enumerate(study.AGIS):
            yy = 190+row*90
            c.text(x0, yy+27, f"AGI {agi}", 15)
            for col, hp in enumerate(study.HPS):
                m = next(v for v in metrics if v["hp"] == hp and v["agi"] == agi)
                value = m[label+"_rate"]
                xx = x0+120+col*125
                color = "#eeeeee" if value is None else "#"+"".join(f"{int(a+(b-a)*value):02x}" for a, b in ((247, 110), (229, 178), (220, 220)))
                c.rect(xx, yy, xx+118, yy+78, color)
                c.text(xx+20, yy+13, "missing" if value is None else f"{value:.1%}", 20)
                c.text(xx+25, yy+45, f"{m[label+'_wins']}/{m[label+'_valid']}")
    c.save(output, "agi_hp_heatmaps")


def rate_chart(output, data, name, title):
    rows = data["candidates"]
    c = graphics.Canvas(1500, 650)
    c.text(20, 10, title, 20)
    c.text(20, 43, "Blue=B; orange=C. B center=35%; pale green=C band 25-60%. Shared seeds across fixed jobs.", 15)
    xp, yp, width, height = 90, 110, 1330, 360
    y = lambda rate: yp+height*(1-rate)
    c.rect(xp-10, y(.60), xp+width+10, y(.25), "#e1f0dd")
    for tick in (0, .25, .35, .50, .60, .75, 1):
        c.line(xp-10, y(tick), xp+width+10, y(tick), "#dddddd")
        c.text(25, y(tick)-7, f"{tick:.0%}")
    c.line(xp-10, y(.35), xp+width+10, y(.35), "#2166ac", 2)
    for i, m in enumerate(rows):
        xx = xp+i*width/max(1, len(rows)-1)
        if not m["complete"]:
            continue
        c.point(xx-4, y(m["B_rate"]), "#2166ac")
        c.point(xx+4, y(m["C_rate"]), "#d95f02")
        c.text(xx-26, 487, str(m["hp"]//1000)+"k")
        c.text(xx-26, 510, str(m["agi"]))
        if len(rows) <= 5:
            c.text(xx-26, 540, f"{m['B_rate']:.1%}/{m['C_rate']:.1%}")
            c.text(xx-26, 565, f"gap {m['B_gap']:.0%}/{m['C_gap']:.0%}")
    c.text(20, 603, "Labels: HP / AGI. Maximum job gaps are reported separately; crossing is descriptive, never required.")
    c.save(output, name)


def combat_chart(output, data):
    rows = [(m, label) for m in data["candidates"] for label in ("B", "C")]
    c = graphics.Canvas(1450, 150+len(rows)*65)
    c.text(20, 10, "Titan action opportunity vs actual threatening direct attacks", 20)
    c.text(20, 43, "Green=support successes; orange=nominal direct actions; gray=status skips; black dot=positive direct-damage actions.", 15)
    c.text(20, 70, "Counter damage is a reaction during the player's action, reported separately. A nominal attack can miss.")
    maximum = max(m[label+"_boss_mean_actions"] for m, label in rows)
    for i, (m, label) in enumerate(rows):
        yy = 120+i*65
        c.text(15, yy, f"HP{m['hp']//1000}k AGI{m['agi']} {label}", 15)
        support, direct = m[label+"_boss_support_actions"], m[label+"_boss_direct_attack_actions"]
        total = m[label+"_boss_mean_actions"]
        scale, start = 650/max(1, maximum), 325
        for n, color in ((support, "#74a68d"), (direct, "#e9a46b"), (max(0, total-support-direct), "#b7b7b7")):
            c.rect(start, yy, start+n*scale, yy+22, color)
            start += n*scale
        c.point(325+m[label+"_boss_threatening_direct_actions"]*scale, yy+11, "#111111")
        c.text(1010, yy, f"actions {total:.1f}; threat {m[label+'_boss_threatening_direct_actions']:.1f}")
        c.text(1010, yy+22, f"loops {m[label+'_mean_loops']:.1f}; exhaust {m[label+'_player_all_exhausted_rate']:.0%}")
    c.save(output, "confirm_combat")


def skill_handoff(output, runs):
    lines = ["# Stage 6-D用：現行スキル構成の観測", "",
             "順序はsteel_body → solid_stance → counter_stance → shock_wave → true_fist、各99回を全戦固定。以下は構成変更の効果を示す試験ではない。", "",
             "主資料は独立confirm。最初の5行動はゲージによる行動機会順で、失敗の通常攻撃・状態異常skipも含む。", "",
             "|候補|戦術|試行|攻撃スキル到達|初攻撃スキルの自身行動番号（到達戦のみ）|攻撃スキル前に死亡/全戦|同/ボス死亡戦|通常・技能直接行動平均|脅威直接行動平均|補助平均|",
             "|---|---|---:|---|---|---|---|---:|---:|---:|"]
    attempts, actions, lifecycle = [], [], []
    grouped = defaultdict(list)
    for r in runs:
        if not r.get("exception"):
            grouped[r["candidate"], "B" if r["tactic"] == "B" else "C"].append(r)
    windows = effect_windows(runs)
    for (candidate, label), values in grouped.items():
        mean = lambda fn: statistics.mean(fn(r) for r in values)
        reached = [r["titan_analysis"]["first_attack_skill_boss_ordinal"] for r in values
                   if r["titan_analysis"]["first_attack_skill_boss_ordinal"] is not None]
        died = sum(r["titan_analysis"]["boss_died_before_attack_skill"] for r in values)
        deaths = sum(r["final"]["boss"]["hp"] == 0 for r in values)
        ordinal = f"{statistics.mean(reached):.2f} ({min(reached)}〜{max(reached)})" if reached else "未到達"
        lines.append(f"|{candidate}|{label}|{len(values)}|{len(reached)}/{len(values)}|{ordinal}|{died}/{len(values)}|{died}/{deaths}|"
            f"{mean(lambda r:r['titan_analysis']['boss_direct_attack_actions']):.2f}|"
            f"{mean(lambda r:r['titan_analysis']['boss_threatening_direct_actions']):.2f}|"
            f"{mean(lambda r:r['titan_analysis']['boss_support_actions']):.2f}|")
        counts = {code: sum((Counter(r["titan_analysis"]["skill_attempts"]["boss"].get(code, {})) for r in values), Counter())
                  for code in study.SKILLS}
        for code, cnt in counts.items():
            attempts.append({"candidate": candidate, "tactic": label, "skill": code, "battles": len(values),
                **{k: cnt[k] for k in ("attempts", "success", "activation_failure", "mp_shortage")},
                "actual_damage_to_player": sum(r["titan_analysis"]["boss_damage_by_skill"].get(code, 0) for r in values)})
        actions.append({"candidate": candidate, "tactic": label, "battles": len(values),
            "counter_damage": sum(r["titan_analysis"]["counter_damage"] for r in values),
            "support_window_player_direct_damage": sum(r["titan_analysis"]["player_direct_damage_in_support_windows"] for r in values),
            "incoming_overlap_damage": sum(r["titan_analysis"]["boss_incoming_overlap"].get("damage", 0) for r in values),
            "incoming_overlap_hits": sum(r["titan_analysis"]["boss_incoming_overlap"].get("hit_events", 0) for r in values),
            "shield_successes": sum(r["titan_analysis"]["player_healing_shield_actions"] for r in values),
            "shield_at_full": sum(r["titan_analysis"]["player_healing_shield_at_full"] for r in values),
            "all_skills_exhausted": sum(r["titan_analysis"]["all_active_exhausted"]["player"] for r in values),
            "mp_shortages": sum(r["player"]["mp_shortages"] for r in values)})
        for code in study.trace.SUPPORT:
            selected = [w for w in windows if w["candidate"] == candidate and (w["tactic"] == "B") == (label == "B") and w["skill"] == code]
            durations = [w["own_actions_until_clear"] for w in selected if not w["censored_by_battle_end"]]
            lifecycle.append({"candidate": candidate, "tactic": label, "skill": code, "applications": len(selected),
                "closed_intervals": len(durations), "battle_end_censored": len(selected)-len(durations),
                "own_actions_until_clear_mean": statistics.mean(durations) if durations else None,
                "own_actions_until_clear_min": min(durations) if durations else None,
                "own_actions_until_clear_max": max(durations) if durations else None})
    csv_rows(output / "confirm_skill_attempt_totals.csv", attempts)
    csv_rows(output / "confirm_skill_actions.csv", actions)
    csv_rows(output / "confirm_effect_lifetimes.csv", lifecycle)
    lines += ["", "## 解釈上の区別", "",
        "直接行動は通常攻撃/衝撃波/真拳一殺。脅威直接行動は、その行動中にプレイヤーのHPを通常/技能で実際に1以上減らしたもの。反撃はプレイヤー行動中の反応であり、独立したボス行動には数えない。", "",
        "試行は実際にget_skill_mp_costへ到達した選択スキルだけ。状態異常skipは試行に入れず、発動失敗・MP不足と区別する。成功数は実実行コードと照合した。", "",
        "継続表は実際にカウンタが0になるまでの自身の行動数。戦闘終了による未観測区間を打切りとして分離する。発動直後に2種のフラグが立っても、終了処理で片方が消える場合がある。被弾時に実際に重複していたかはHP変化ごとの状態を使う。", "",
        "補助行動中の被害は、直前の成功した補助行動から次の非skipボス行動までに受けたプレイヤー通常/技能の実損傷。軽減されなかった仮想損傷との差を測ったものではない。", "",
        "ヒーリングシールド満タン消費の分母は実際の成功使用回数。全技能枯渇は、パッシブを除くすべてのアクティブ枠が0になった戦闘数。", "",
        "## 次段階の候補（いずれも今回未測定）", "",
        "現行を対照として維持し、攻撃スキルを前へ置く/攻防を交互に置く/防御順だけを変える/補助枠を減らす/完成済み攻撃スキルへ置換する案を、必要性と職業差を見ながら少数ずつ比較する。今回これらの並びや技能を一度も戦闘へ渡していない。改善効果は未証明。", "",
        "最初に調べる問題は、開幕3補助と自身行動での効果切れが、攻撃到達・被弾時の防御被覆・反撃依存にどう結び付いているか。HP/AGIを固定した構成比較が必要で、今回のHP/AGI差と混同しない。"]
    with (output / "STAGE6D_SKILL_HANDOFF.md").open("x") as f:f.write("\n".join(lines)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE)
    parser.add_argument("--output", type=Path, default=HERE / "analysis")
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    result = {}
    lines = ["# Stage6-C 全職業の勝率・Wilson95%", "", "主評価は独立confirm。screen/refineは選択用。各職業セルにWilson95%、多重比較補正なし。", "",
             "7職業合計は固定キャラと共通seedによる記述合計。独立二項標本として区間・適合確定を行わない。", ""]
    candidate_lines = ["# AGI×HP候補の比較", "", "B中心35%、C25〜60%は帯内を公平に扱う。交差は別指標。", ""]
    skill_rows, sequence_rows = [], []
    for phase in ("screen", "refine", "confirm"):
        if not (args.source / phase).exists():
            continue
        data = phase_summary(args.source / phase)
        result[phase] = data
        for key in ("conditions", "candidates", "comparisons"):
            csv_rows(out / f"{phase}_{key}.csv", data[key])
        runs = study.records(args.source / phase / "runs.jsonl")
        csv_rows(out / f"{phase}_effect_windows.csv", effect_windows(runs))
        lines += [f"## {phase}", "", "|候補|職業|戦術|勝/試行・Wilson95%|予定/欠測/例外|", "|---|---|---|---|---|"]
        for s in data["conditions"]:
            lines.append(f"|{s['candidate']}|{JOBS[s['job']]}|{s['tactic']}|{prior.rate(s)}|{s['planned']}/{s['missing']}/{s['exceptions']}|")
            for code, counts in s["boss_skill_attempts"].items():
                skill_rows.append({"phase": phase, "candidate": s["candidate"], "job": s["job"], "tactic": s["tactic"],
                                   "skill": code, **{k: counts.get(k, 0) if s["valid"] else None for k in ("attempts", "success", "activation_failure", "mp_shortage")}})
        candidate_lines += [f"## {phase}", "", "|HP|AGI|B勝/試行|C勝/試行|B中心差pt|C帯外距離pt|B−C pt|職業差B/C|全敗セル|全枯渇B/C|", "|---:|---:|---|---|---:|---:|---:|---|---:|---|"]
        for m in data["candidates"]:
            if not m["complete"]:
                candidate_lines.append(f"|{m['hp']}|{m['agi']}|未完|未完|||||||")
                continue
            candidate_lines.append(f"|{m['hp']}|{m['agi']}|{m['B_wins']}/{m['B_valid']}|{m['C_wins']}/{m['C_valid']}|"
                f"{m['b_center_distance']*100:.1f}|{m['c_band_distance']*100:.1f}|{m['b_minus_c']*100:+.1f}|"
                f"{m['B_gap']:.0%}/{m['C_gap']:.0%}|{m['zero_job_cells']}|{m['B_player_all_exhausted_rate']:.0%}/{m['C_player_all_exhausted_rate']:.0%}|")
        sequences = Counter((r["candidate"], r["job"], r["tactic"], tuple(f["code"] for f in r["titan_analysis"]["boss_first_five"]))
                            for r in runs if not r.get("exception"))
        sequence_rows.extend({"phase": phase, "candidate": key[0], "job": key[1], "tactic": key[2], "first_five": list(key[3]), "battles": count}
                             for key, count in sequences.items())
    interactions, interaction_summary = interaction_rows(study.records(args.source / "screen/runs.jsonl"))
    csv_rows(out / "interaction_runs.csv", interactions)
    csv_rows(out / "interactions.csv", interaction_summary)
    csv_rows(out / "skill_attempts.csv", skill_rows)
    csv_rows(out / "first_five_sequences.csv", sequence_rows)
    for name, content in (("TABLES.md", lines), ("CANDIDATES.md", candidate_lines)):
        with (out / name).open("x") as f:f.write("\n".join(content)+"\n")
    study.write_json(out / "results.json", result)
    heatmaps(out, result["screen"]["candidates"])
    rate_chart(out, result["screen"], "screen_bc", "Screening: all 20 actual combinations")
    rate_chart(out, result["confirm"], "confirm_bc", "Independent confirmation: selected candidates and formal control")
    combat_chart(out, result["confirm"])
    skill_handoff(out, study.records(args.source / "confirm/runs.jsonl"))
    source_files = [HERE / name for name in ("run.py", "observe.py", "analyze.py", "check.py")]
    source_files += [args.source / phase / name for phase in result for name in ("runs.jsonl", "manifest.json", "study_metadata.json")]
    study.write_json(out / "source_sha256.json", {str(p.relative_to(study.ROOT)) if p.is_relative_to(study.ROOT) else str(p):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files})
    print(json.dumps({p: {k: d[k] for k in ("planned", "completed", "exceptions", "missing", "draws", "loop_limits", "battle_seconds")}
                      for p, d in result.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
