"""第1段階の育成到達例。DB接続・戦闘・保存はしない。リポジトリ直下から実行。"""
import ast
import copy
import importlib
import itertools
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection
from apps.accounts.models import Character
from apps.accounts.growth import level_up_once, JOB_GROWTH_WEIGHTS
from config.views import generate_reincarnation_bonus, calculate_reincarnation_stats
from apps.inventory.models import Equipment, OwnedEquipment
from apps.inventory.services import calculate_equipment_battle_power
from apps.battle.engine.character_stats import (
    get_character_base_combat_stat, get_character_battle_max_resource,
)

STATS = ["max_hp", "max_mp", "strength", "intelligence", "dexterity", "agility", "vitality", "luck"]
ATTRS = ["fire", "water", "grass", "rock", "light", "dark"]
SEED = 20261116
MASTERS = importlib.import_module("apps.inventory.migrations.0006_add_equipment_master_data").EQUIPMENT_DATA
RACES = {"grappler": "dragonia", "warrior": "dwarf", "hunter": "elf", "wizard": "witch",
         "priest": "witch", "wanderer": "fairy", "assassin": "elf"}

# ホームの正式表示式をASTから取得する。コピーした独自の戦闘力式を使わない。
tree = ast.parse((ROOT / "config/views.py").read_text())
home = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "home")
power_expr = next(n.value for n in ast.walk(home) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "battle_power" for t in n.targets)
                  and isinstance(n.value, ast.BinOp))
POWER = compile(ast.Expression(power_expr), "config/views.py:home:battle_power", "eval")


def equipment(job, levels):
    style = "magic" if job in ("wizard", "priest") else "physical"
    result, bonuses, total = [], dict.fromkeys(STATS[2:], 0), 0
    for data, enhancement in zip([d for d in MASTERS if d[1] == "F" and d[3] == style], levels):
        name, rank, slot, style, base, *rates = data
        master = Equipment(rank=rank, slot=slot, style=style, base_battle_power=base,
                           **{key + "_rate": value for key, value in zip(STATS[2:], rates)})
        power = calculate_equipment_battle_power(base, rank, enhancement)
        owned = OwnedEquipment(equipment=master, battle_power=power, enhancement_level=enhancement)
        for key in bonuses:
            bonuses[key] += owned.get_stat_bonus(key)
        total += power
        result.append({"name": name, "rank": rank, "slot": slot, "style": style,
                       "enhancement": enhancement, "power": power, "special_effect": None})
    return result, bonuses, total


def power(character, gear_power):
    return eval(POWER, {}, {"character": character,
                           "main_attribute_value": max(getattr(character, a) for a in ATTRS),
                           "equipment_battle_power": gear_power})


def path(job, race, reincarnations, seed):
    state = random.getstate()
    random.seed(seed)
    try:
        character = Character(job=job, race=race)
        if reincarnations:
            # 以前の能力値を引き継がないため、最後の回帰を直接再生して等価な初期値を得る。
            character.reincarnation_count = reincarnations - 1
            values = calculate_reincarnation_stats(generate_reincarnation_bonus(character))
            for key, value in values.items():
                setattr(character, key, value)
        character.reincarnation_count = reincarnations
        snapshots = [copy.copy(character)]
        for _ in range(99):
            level_up_once(character)
            snapshots.append(copy.copy(character))
        return snapshots
    finally:
        random.setstate(state)


def profile(floor, character, seed, label, gear, target=None):
    items, bonuses, gear_power = gear
    # 装備なし特殊効果なしのDB問い合わせ結果をメモリ上の装備構成へ置換。
    # 能力値の職業・種族補正式は本体関数で計算する。
    with (
        patch("apps.battle.engine.character_stats.get_equipment_stat_bonus",
              side_effect=lambda c, key: bonuses[key]),
        patch.object(OwnedEquipment.objects, "filter") as effects,
    ):
        effects.return_value.count.return_value = 0
        combat = {key: get_character_base_combat_stat(character, key) for key in STATS[2:]}
        combat.update({"max_hp": get_character_battle_max_resource(character, "hp"),
                       "max_mp": get_character_battle_max_resource(character, "mp")})
    return {"floor": floor, "variant": label, "job": character.job, "race": character.race,
            "reincarnations": character.reincarnation_count, "level": character.level,
            "seed": seed, "target_power": target, "power": power(character, gear_power),
            "stats": {k: getattr(character, k) for k in STATS},
            "attributes": {k: getattr(character, k) for k in ATTRS},
            "combat_start": combat, "max_st": character.max_stamina, "start_st": 100,
            "equipment": items, "equipment_bonuses": bonuses,
            "attribute_weights": dict.fromkeys(ATTRS, 1), "skills": "not_selected_stage1"}


def no_sql(execute, sql, params, many, context):
    raise AssertionError("第1段階の育成算出ではDB操作を禁止")


def main():
    records, six_unarmed = [], []
    empty = ([], dict.fromkeys(STATS[2:], 0), 0)
    with connection.execute_wrapper(no_sql):
        for job in JOB_GROWTH_WEIGHTS:
            for variant in range(2):
                race = "human" if variant == 0 else RACES[job]
                seed = SEED + variant
                for floor, count, level in [(1, 0, 20), (2, 0, 70), (3, 2, 50), (4, 5, 80), (5, 10, 80)]:
                    character = path(job, race, count, seed)[level - 1]
                    gear = empty if variant == 0 else equipment(job, [0]*5)
                    records.append(profile(floor, character, seed, "unarmed" if variant == 0 else "F+0", gear))
                snapshots = path(job, race, 20, seed)
                six_unarmed.append(profile(6, snapshots[-1], seed, "unarmed-Lv100", empty))
                candidates = []
                # 20回帰を固定し、LvとF装備5部位の+値を検索する（同ランク合成で到達可）。
                for enhancements in itertools.product(range(5, 8), repeat=5):
                    gear = equipment(job, enhancements)
                    for character in snapshots:
                        candidates.append((abs(power(character, gear[2])-5000), character, gear))
                _, character, gear = min(candidates, key=lambda c: c[0])
                records.append(profile(6, character, seed, "searched-F-set", gear, 5000))

                for floor, low, high in [(7,10000,15000),(8,23000,28000),(9,32000,37000),
                                         (10,49000,54000),(11,60000,65000),(12,80000,85000)]:
                    gear = empty if variant == 0 else equipment(job, [8]*5)
                    for point, target in [("low",low+200),("mid",(low+high)//2),("high",high-200)]:
                        estimate = max(0, round((target-gear[2]-400)/125))
                        candidates = []
                        for count in range(max(0, estimate-3), estimate+4):
                            for character in path(job, race, count, seed):
                                value = power(character, gear[2])
                                if low <= value <= high:
                                    candidates.append((abs(value-target), character))
                        if not candidates:
                            raise ValueError((floor, job, race, target))
                        _, character = min(candidates, key=lambda c: c[0])
                        records.append(profile(floor, character, seed,
                            point + ("-unarmed" if variant == 0 else "-F+8"), gear, target))
    output = {"commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "python": sys.version,
              "seed_base": SEED, "description": "育成到達例。勝率測定・推奨ビルド確定・所要時間保証ではない。",
              "reincarnation_replay": "最後の回帰の直接再生。過去の各周Lv100到達・EXP/素材獲得の所要時間は未測定。",
              "records": records, "floor6_unarmed_lv100": six_unarmed}
    dest = Path(__file__).with_name("BOSS_BASELINE_STAGE1.json")
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    for floor in range(1,13):
        group = [r for r in records if r["floor"]==floor]
        print(floor, "power", min(r["power"] for r in group), max(r["power"] for r in group),
              "R", min(r["reincarnations"] for r in group), max(r["reincarnations"] for r in group),
              "Lv", min(r["level"] for r in group), max(r["level"] for r in group))
    print("profiles", len(records), "floor6 unarmed range", min(r["power"] for r in six_unarmed),max(r["power"] for r in six_unarmed))


if __name__ == "__main__":
    main()
