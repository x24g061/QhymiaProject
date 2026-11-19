"""5-C前半。既存隔離ランナーへ有限条件と観測の後処理だけを接続する。"""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.management import call_command
from apps.battle import balance_stage5 as base, balance_stage5b as previous, simulation_v2 as sim
from apps.battle.management.commands import simulate_boss_v2 as runner

SEED = 80361118
C3 = list(previous.C2) + [("healing_shield", 1)]
# すべて現行値を対照に1能力だけ変更。AGI900は5-Bの行動/実ダメージを新seedで確認。
VARIANTS = {"base": {}, "hp100000": {"max_hp": 100000},
            "hp200000": {"max_hp": 200000}, "str6000": {"strength": 6000},
            "str12000": {"strength": 12000}, "agi900": {"agility": 900}}
CORE = ("job", "race", "level", "reincarnations", "stats", "attributes", "equipment",
        "attribute_weights", "permanent_skill_codes", "combat_start", "inheritance_history",
        "inheritance_remaining", "max_st", "start_st")


def scenarios():
    profiles = {(r["floor"], r["job"]): r for r in base.profiles() if r["recommendation_eligible"]}
    rows = []
    def add(floor, job, label, variant, trials):
        row = copy.deepcopy(profiles[floor, job])
        row["original_profile_id"] = row["profile_id"]
        row["profile_id"] = f"v5c-f{floor}-{job}-{variant}"
        row["tactics"] = {"B": row["tactics"]["B"], "C1": row["tactics"]["C"]}
        if job in ("wizard", "priest"):
            row["tactics"].update(C2=list(previous.C2), C3=list(C3))
        row.update(evaluation_trials=trials, boss_override=copy.deepcopy(VARIANTS[variant]),
                   evaluation_variant=variant)
        base.validate_profile(row)
        rows.append((row, label, 1))
    # 優先順。8階84条件420戦、7階16条件380戦、12階6条件180戦。
    for job in base.SKILL_CODES:
        for label in ("B", "C2" if job in ("wizard", "priest") else "C1"):
            for variant in VARIANTS:
                add(8, job, label, variant, 5)
    for job in base.SKILL_CODES:
        for label in (("B", "C2", "C3") if job in ("wizard", "priest") else ("B", "C1")):
            add(7, job, label, "base", 30 if job in ("wizard", "priest") else 20)
    for job in ("wizard", "priest"):
        for label in ("B", "C2", "C3"):
            add(12, job, label, "base", 30)
    return rows


def evaluation_boss(boss, overrides):
    """既存関数への一時接続。許可値を限定し、モデル保存は呼ばない。"""
    if not boss.is_boss or (overrides and (boss.floor != 8 or overrides not in VARIANTS.values())):
        raise ValueError("5-Cの単一能力候補以外は拒否")
    candidate = copy.copy(boss)
    for key, value in overrides.items():
        setattr(candidate, key, value)
    return candidate


def diagnostics(record):
    """実HP変化・実行順の集計。乱数/行動選択へ介入しない。"""
    result = {}
    physical = {"normal", "true_fist", "double_punch", "shock_wave", "poison_arrow", "sleep_arrow",
                "flare_blade", "one_hit_kill", "rapid_shot", "counter"}
    magic = {"stella", "anti_jail", "judgement", "megido", "explosion", "fire"}
    support = {"fighting_spirit", "healing_shield", "steel_body", "solid_stance", "counter_stance", "frost_armor"}
    for side in ("player", "boss"):
        moves = [a for a in record["actions"] if a["side"] == side]
        events = [e for e in record["hp_events"] if e["target"] != side and e["source"] == side and e["kind"] != "heal"]
        direct = [e for e in events if e["kind"] in ("normal", "skill")]
        counts = Counter(a["code"] for a in moves)
        damage_by_skill = Counter()
        for e in events:
            damage_by_skill[e["skill"] or e["kind"]] += e["amount"]
        heals = [e for e in record["hp_events"] if e["target"] == side and e["kind"] == "heal" and e["skill"] == "healing_shield"]
        first = next((a for a in moves if a["code"] == "healing_shield"), None)
        result[side] = {
            "direct_attack_actions": sum(v for k, v in counts.items() if k in physical | magic - {"counter"}),
            "support_actions": sum(v for k, v in counts.items() if k in support),
            "physical_attack_actions": sum(v for k, v in counts.items() if k in physical - {"counter"}),
            "magic_attack_actions": sum(v for k, v in counts.items() if k in magic),
            "direct_damage": sum(e["amount"] for e in direct),
            "physical_damage": sum(e["amount"] for e in direct if e["skill"] in physical or e["kind"] == "normal"),
            "magic_damage": sum(e["amount"] for e in direct if e["skill"] in magic),
            "direct_hit_events": len(direct), "damage_by_skill": dict(damage_by_skill),
            "first_six": [a["code"] for a in moves[:6]],
            "healing_shield_executed": bool(first),
            "first_heal_action": moves.index(first)+1 if first else None,
            "first_heal_tick": first["tick"] if first else None,
            "shield_actual_heal": sum(e["amount"] for e in heals),
            "first_heal_hp_before": first["before"]["hp"] if first else None,
        }
    return result


def plan():
    rows = scenarios()
    source = ROOT / "docs/変更詳細/balance_stage5b/screen_confirmed"
    timing = defaultdict(list)
    old = [json.loads(line) for line in (source / "runs.jsonl").open()]
    for r in old:
        if r["floor"] != 8 or r["evaluation_boss"]["agility"] == 180:
            timing[r["floor"], r["job"], r["tactic"]].append(r["elapsed_seconds"])
    # HP増加による長期化/回数枯渇を余裕を持って見積もる。
    factors = {"base": 1, "hp100000": 4, "hp200000": 12,
               "str6000": 1, "str12000": 1, "agi900": 1.5}
    estimate = sum(statistics.mean(timing[r["floor"], r["job"], "C2" if label == "C3" else label])
                   * r["evaluation_trials"] * factors[r["evaluation_variant"]] * 1.5
                   for r, label, _ in rows)
    assert len({(r["profile_id"], label) for r, label, _ in rows}) == len(rows)
    assert not set(range(SEED, SEED+30)) & {r["seed"] for r in old}
    return rows, {"conditions": len(rows), "battles": sum(r["evaluation_trials"] for r, _, _ in rows),
                  "estimated_battle_seconds": round(estimate, 3), "setup_allowance_seconds": 15,
                  "max_seconds": 270, "seed_base": SEED, "max_trials_per_condition": 30,
                  "cost_factors": factors, "detail": "全戦からdiagnosticsを抽出、先頭seedのみ完全詳細を保存"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/変更詳細/balance_stage5c/screen")
    args = parser.parse_args()
    rows, estimate = plan()
    print(json.dumps(estimate, ensure_ascii=False), flush=True)
    if args.plan:
        return
    if estimate["estimated_battle_seconds"] + 15 > 300:
        raise RuntimeError("5分を超える計画は実行しません。優先度順に削減が必要")
    args.output.mkdir(parents=True, exist_ok=False)
    estimate["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (args.output / "selection.json").open("x") as f:
        json.dump(estimate, f, ensure_ascii=False, indent=2)
    original = sim.measure
    def observed(character, boss, seed, **kwargs):
        record = original(character, boss, seed, detail=True)
        record["diagnostics"] = diagnostics(record)
        if seed != SEED:
            for key in ("actions", "hp_events", "state_events"):
                record.pop(key)
        return record
    with patch.object(runner, "cases", return_value=iter(rows)), \
         patch.object(previous, "evaluation_boss", evaluation_boss), \
         patch.object(sim, "measure", observed):
        call_command("simulate_boss_v2", isolated_test_db=True, output=str(args.output),
                     trials=5, seed_base=SEED, max_battles=estimate["battles"], max_seconds=270,
                     plan=False, seconds_per_battle=None)


if __name__ == "__main__":
    main()
