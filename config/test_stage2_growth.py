"""育成・表示の基準テスト。勝率や推奨回帰回数は固定しない。"""
import csv
import importlib.util
import itertools
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import Character, User
from apps.accounts.growth import (
    level_up_once, get_growth_weights, roll_attribute_growth, calculate_initial_points,
)
from apps.inventory.models import Equipment, OwnedEquipment
from config.views import generate_reincarnation_bonus, calculate_reincarnation_stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/変更詳細"
spec = importlib.util.spec_from_file_location("stage1_baseline", DATA / "BOSS_BASELINE_STAGE1.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
RECORDS = json.loads((DATA / "BOSS_BASELINE_STAGE1.json").read_text())["records"]
# 基準版の成長ウェイト。順序 HP MP STR INT DEX AGI VIT LUK。
JOBS = {
    "grappler": (2,1,3,1,2,2,2,1), "warrior": (3,1,3,1,1,1,3,1),
    "hunter": (1,2,2,1,3,2,1,2), "wizard": (1,3,1,4,1,1,1,1),
    "priest": (1,3,1,3,1,2,2,2), "wanderer": (2,1,2,1,2,2,1,3),
    "assassin": (1,2,1,1,3,3,2,1),
}
RACES = {
    "human": (2,2,2,1,2,2,1,3), "elf": (2,2,1,3,2,3,1,1),
    "dwarf": (3,1,2,2,2,1,3,1), "dragonia": (3,1,3,2,1,2,3,1),
    "witch": (1,3,1,4,3,1,1,1), "fairy": (1,2,1,2,4,2,1,2),
    "demonia": (2,2,3,3,1,2,1,1),
}
NAMES = ["hp", "mp", *baseline.STATS[2:]]


def named_cases(cls, cases, run):
    """各意味のある構成を個別のunittestとして発見可能にする。"""
    for label, value in cases:
        def test(self, value=value):
            run(self, value)
        test.__name__ = "test_" + label
        setattr(cls, test.__name__, test)
    return cls


class GrowthMatrixTests(SimpleTestCase):
    pass


def growth_case(self, pair):
    job, race = pair
    character = Character(job=job, race=race)
    expected = dict(zip(NAMES, [a+b for a,b in zip(JOBS[job], RACES[race])]))
    self.assertEqual(get_growth_weights(character), expected)
    with patch("apps.accounts.growth.random.choices", side_effect=[
        ["hp", "mp", "strength", "strength", "agility"], ["fire", "fire", "water"],
    ]) as draws:
        level_up_once(character)
    self.assertEqual(draws.call_count, 2)
    self.assertEqual(draws.call_args_list[0].kwargs["weights"], list(expected.values()))
    self.assertEqual(draws.call_args_list[0].kwargs["k"], 5)
    self.assertEqual(draws.call_args_list[1].kwargs["k"], 3)
    self.assertEqual((character.level,character.max_hp,character.max_mp,character.strength), (2,38,13,7))
    self.assertEqual((character.fire,character.water,character.grass), (2,1,0))
    self.assertEqual((character.agility,character.dexterity,character.vitality,character.luck), (6,5,5,5))


def job_growth_case(self, job):
    for race in RACES:
        with self.subTest(race=race):
            growth_case(self,(job,race))


named_cases(GrowthMatrixTests, [(j,j) for j in JOBS], job_growth_case)


class GrowthReplayTests(SimpleTestCase):
    def test_csv_json_match_every_profile(self):
        with (DATA / "BOSS_BASELINE_STAGE1.csv").open() as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 336)
        for csv_row, row in zip(rows, RECORDS):
            with self.subTest(job=row["job"], floor=row["floor"], variant=row["variant"]):
                self.assertEqual(int(csv_row["power"]), row["power"])
                self.assertEqual(json.loads(csv_row["equipment"]), row["equipment"])
                for field in baseline.STATS + baseline.ATTRS:
                    self.assertEqual(int(csv_row[field]), (row["stats"] | row["attributes"])[field])


def replay_case(self, pair):
    job, seed = pair
    selected = [r for r in RECORDS if r["job"]==job and r["seed"]==seed and r["floor"]<=5]
    self.assertEqual(len(selected), 5)
    import random
    before = random.getstate()
    for row in selected:
        # 旧測定成果物は旧成長式で再現する。現行Ver.2はtest_growth_v2で別途検証。
        with patch.object(baseline, "level_up_once", side_effect=legacy_level_up_once):
            first = baseline.path(job,row["race"],row["reincarnations"],seed)[row["level"]-1]
            second = baseline.path(job,row["race"],row["reincarnations"],seed)[row["level"]-1]
        for field in baseline.STATS + baseline.ATTRS:
            value = (row["stats"] | row["attributes"])[field]
            self.assertEqual(getattr(first,field), value)
            self.assertEqual(getattr(first,field),getattr(second,field))
    self.assertEqual(random.getstate(), before)


def legacy_level_up_once(character):
    """保存済み2026-11-16データ専用の旧3抽選・HP+5再生。"""
    import random
    character.level += 1
    weights = get_growth_weights(character)
    for stat in random.choices(list(weights), weights=list(weights.values()), k=3):
        if stat == "hp":
            character.max_hp += 5
            character.current_hp += 5
        elif stat == "mp":
            character.max_mp += 3
        else:
            setattr(character, stat, getattr(character, stat) + 1)
    roll_attribute_growth(character)


named_cases(GrowthReplayTests, [(j+"_seed"+str(s),(j,s)) for j in JOBS for s in [20261116,20261117]], replay_case)


class ReincarnationBoundaryTests(SimpleTestCase):
    pass


def reincarnation_case(self, previous):
    character = Character(reincarnation_count=previous, max_hp=999999, strength=999999, fire=999999)
    names = baseline.STATS + baseline.ATTRS
    with patch("config.views.random.choice", side_effect=itertools.cycle(names)) as draw:
        points = generate_reincarnation_bonus(character)
    self.assertEqual(draw.call_count, calculate_initial_points(previous+1))
    self.assertEqual(sum(points.values()), calculate_initial_points(previous+1))
    stats = calculate_reincarnation_stats(points)
    self.assertEqual(stats["max_hp"],30+5*points["max_hp"])
    self.assertEqual(stats["max_mp"],10+2*points["max_mp"])
    for field in baseline.STATS[2:]:
        self.assertEqual(stats[field],5+points[field])
    for field in baseline.ATTRS:
        self.assertEqual(stats[field],points[field])
    self.assertEqual(character.strength,999999)  # プレビュー自体は保存値を変更しない。


named_cases(ReincarnationBoundaryTests, [("previous_"+str(r),r) for r in [0,1,2,4,9,19,99,599]], reincarnation_case)


class HomePowerIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user(user_id="stage2-home",password=None)
        cls.character=Character.objects.create(user=cls.user,name="表示統合")


def home_case(self, pair):
    job,seed=pair
    self.client.force_login(self.user)
    selected=[r for r in RECORDS if r["job"]==job and r["seed"]==seed]
    for row in selected:
        with self.subTest(floor=row["floor"],variant=row["variant"]):
            OwnedEquipment.objects.filter(character=self.character).delete()
            Character.objects.filter(pk=self.character.pk).update(
                **row["stats"], **row["attributes"], level=row["level"],
                job=job,race=row["race"],reincarnation_count=row["reincarnations"])
            for entry in row["equipment"]:
                master=Equipment.objects.get(item__name=entry["name"])
                OwnedEquipment.objects.create(character=self.character,equipment=master,
                    battle_power=entry["power"],enhancement_level=entry["enhancement"],is_equipped=True)
            response=self.client.get(reverse("home"))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context["battle_power"],row["power"])
            current=response.context["character"]
            self.assertEqual(baseline.power(current,sum(e["power"] for e in row["equipment"])),row["power"])
            from apps.battle.engine.character_stats import get_character_base_combat_stat, get_character_battle_max_resource
            for field in baseline.STATS[2:]:
                self.assertAlmostEqual(get_character_base_combat_stat(current,field),row["combat_start"][field])
            for resource in ["hp","mp"]:
                self.assertEqual(get_character_battle_max_resource(current,resource),row["combat_start"]["max_"+resource])


named_cases(HomePowerIntegrationTests, [(j+"_seed"+str(s),(j,s)) for j in JOBS for s in [20261116,20261117]],home_case)
