"""旧HEADと現行成長Ver.2を未保存Characterで比較。SQL禁止・旧成果物は更新しない。"""
import argparse
import ast
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.db import connection
from apps.accounts.models import Character
from apps.accounts.growth import calculate_growth_count, calculate_initial_points, level_up_once
from config.views import calculate_reincarnation_stats, generate_reincarnation_bonus

OLD_HEAD = "caf9664"
SEED = 20261119
COUNTS = [0, 50, 100, 150, 151, 154, 200, 500]
LEVELS = [1, 50, 100]
STATS = ["max_hp", "max_mp", "strength", "intelligence", "dexterity", "agility", "vitality", "luck"]
ATTRS = ["fire", "water", "grass", "rock", "light", "dark"]


def no_sql(execute, sql, params, many, context):
    raise AssertionError("新旧成長比較ではすべてのSQLを禁止")


def old_module():
    """固定した変更前コミットの実コードを再生。旧式を手で近似しない。"""
    module = types.ModuleType("growth_before_v2")
    growth_source = subprocess.check_output(
        ["git", "show", f"{OLD_HEAD}:apps/accounts/growth.py"], cwd=ROOT, text=True,
    )
    exec(compile(growth_source, "old_growth.py", "exec"), module.__dict__)
    view_source = subprocess.check_output(
        ["git", "show", f"{OLD_HEAD}:config/views.py"], cwd=ROOT, text=True,
    )
    functions = [n for n in ast.parse(view_source).body if isinstance(n, ast.FunctionDef)
                 and n.name in ("generate_reincarnation_bonus", "calculate_reincarnation_stats")]
    exec(compile(ast.Module(body=functions, type_ignores=[]), "old_reincarnation.py", "exec"), module.__dict__)
    module.source_sha256 = hashlib.sha256(growth_source.encode()).hexdigest()
    return module


def display_power():
    """現在のホーム表示式をASTから取得（装備なし）。戦闘式は変更しない。"""
    tree = ast.parse((ROOT / "config/views.py").read_text())
    home = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "home")
    expr = next(n.value for n in ast.walk(home) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "battle_power" for t in n.targets)
                and isinstance(n.value, ast.BinOp))
    return compile(ast.Expression(expr), "config/views.py:home:battle_power", "eval")


def snapshots(job, race, count, variant, old, power):
    rng_state = random.getstate()
    random.seed(SEED)
    try:
        c = Character(job=job, race=race)
        if count:
            c.reincarnation_count = count - 1
            generator = old.generate_reincarnation_bonus if variant == "old" else generate_reincarnation_bonus
            for key, value in calculate_reincarnation_stats(generator(c)).items():
                setattr(c, key, value)
            c.current_hp, c.current_mp = c.max_hp, c.max_mp
        c.reincarnation_count = count
        records = []
        draws = 0
        while True:
            if c.level in LEVELS:
                power_value = eval(power, {}, {
                    "character": c, "main_attribute_value": max(getattr(c, a) for a in ATTRS),
                    "equipment_battle_power": 0,
                })
                records.append({
                    "job": job, "race": race, "reincarnations": count, "level": c.level,
                    "variant": variant, "seed": SEED,
                    **{s: getattr(c, s) for s in STATS + ATTRS},
                    "battle_power": power_value,
                    "initial_points": count*125 if variant == "old" else calculate_initial_points(count),
                    "stat_growth_draws": draws, "attribute_growth_draws": 3*(c.level-1),
                })
            if c.level == 100:
                break
            expected = 3 if variant == "old" else calculate_growth_count(count, c.level)
            grow = old.level_up_once if variant == "old" else level_up_once
            result = grow(c)
            assert len(result["stat_growths"]) == expected
            assert len(result["attribute_growths"]) == 3
            draws += expected
        assert draws == (297 if variant == "old" else 495 + 25*max(count-150, 0))
        return records
    finally:
        random.setstate(rng_state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("growth_v2_comparison"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("既存成果物を保持するため、未使用の出力先を指定してください。")
    old, power = old_module(), display_power()
    records, pairs = [], []
    state_before = random.getstate()
    with connection.execute_wrapper(no_sql):
        for count in COUNTS:
            for job, _ in Character.JOB_CHOICES:
                for race, _ in Character.RACE_CHOICES:
                    before = snapshots(job, race, count, "old", old, power)
                    after = snapshots(job, race, count, "v2_new", old, power)
                    records.extend(before + after)
                    for a, b in zip(before, after):
                        row = {k: a[k] for k in ["job", "race", "reincarnations", "level", "seed"]}
                        for key in STATS + ATTRS + ["battle_power", "initial_points", "stat_growth_draws", "attribute_growth_draws"]:
                            row.update({f"old_{key}": a[key], f"new_{key}": b[key], f"delta_{key}": b[key]-a[key]})
                        pairs.append(row)
    assert random.getstate() == state_before
    assert len(pairs) == 8*7*7*3
    summary = []
    for r in COUNTS:
        for lv in LEVELS:
            group = [p for p in pairs if p["reincarnations"] == r and p["level"] == lv]
            summary.append({"reincarnations": r, "level": lv, "pairs": len(group), **{
                key: {"delta_min": min(p[f"delta_{key}"] for p in group),
                      "delta_max": max(p[f"delta_{key}"] for p in group),
                      "decreased_pairs": sum(p[f"delta_{key}"] < 0 for p in group)}
                for key in STATS + ATTRS + ["battle_power"]
            }})
    args.output.mkdir(parents=True)
    metadata = {
        "old_head": OLD_HEAD, "old_growth_sha256": old.source_sha256,
        "new_growth_sha256": hashlib.sha256((ROOT / "apps/accounts/growth.py").read_bytes()).hexdigest(),
        "seed": SEED, "pairs": len(pairs), "snapshots": len(records),
        "method": "全7職業×全7種族、装備なし、属性ウェイト全1、最後の回帰の直接再生。SQL全禁止。",
        "limitations": "旧/新は同じ初期seedだが抽選数が異なるため乱数消費位置は変わる。新規育成サイクル比較であり、既存キャラクターの途中移行・遡及補填・育成所要時間・勝率を示さない。",
        "records": records,
    }
    (args.output / "SNAPSHOTS.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    (args.output / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with (args.output / "COMPARISON.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    lines = ["# 成長Ver.2 新旧比較（2026-11-19）", "", metadata["method"], "", metadata["limitations"], "",
             "全1,176組・2,352スナップショットの14能力値・戦闘力・抽選回数はCOMPARISON.csv / SNAPSHOTS.json参照。",
             "差の範囲は49職業・種族組合せの記述値。期待値や信頼区間ではない。", "",
             "| 回帰 | Lv | HP差の範囲 | MP差の範囲 | 戦闘力差の範囲 | 戦闘力低下組数/49 |", "|---:|---:|---:|---:|---:|---:|"]
    for row in summary:
        fmt = lambda k: f'{row[k]["delta_min"]:+,}〜{row[k]["delta_max"]:+,}'
        lines.append(f'| {row["reincarnations"]} | {row["level"]} | {fmt("max_hp")} | {fmt("max_mp")} | {fmt("battle_power")} | {row["battle_power"]["decreased_pairs"]} |')
    lines += ["", "## ヒューマン・職業別の実測", "", "旧→新で表記。ほか6種族の全数値はCSVに収録。", "",
              "| 回帰 | Lv | 職業 | HP | MP | 戦闘力 | 基本成長回数 |", "|---:|---:|---|---:|---:|---:|---:|"]
    for p in pairs:
        if p["race"] == "human":
            fmt = lambda k: f'{p["old_"+k]:,}→{p["new_"+k]:,}'
            lines.append(f'| {p["reincarnations"]} | {p["level"]} | {p["job"]} | {fmt("max_hp")} | {fmt("max_mp")} | {fmt("battle_power")} | {fmt("stat_growth_draws")} |')
    (args.output / "TABLES.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: metadata[k] for k in ["pairs", "snapshots", "seed"]}, ensure_ascii=False))
    print("出力先:", args.output)


if __name__ == "__main__":
    main()
