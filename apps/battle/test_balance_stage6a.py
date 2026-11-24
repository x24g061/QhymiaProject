"""Stage 6-Aの再生成・対応条件・隔離観測の契約。勝率目標は固定しない。"""
import copy
import importlib.util
import random
from pathlib import Path
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from apps.accounts import growth
from apps.battle import simulation_v2 as sim
from apps.battle.models import Enemy
from apps.battle import test_simulation_v2 as contracts

PATH = Path(__file__).resolve().parents[2] / "docs/変更詳細/BALANCE_STAGE6A_RUN.py"
spec = importlib.util.spec_from_file_location("stage6a_contract", PATH)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class Stage6ARebuildTests(SimpleTestCase):
    def test_saved_profiles_replay_exactly_and_all_pairs_fix_non_growth_conditions(self):
        before = random.getstate()
        pairs = study.profile_pairs()
        self.assertEqual(len(pairs), 84)
        self.assertEqual(random.getstate(), before)
        self.assertEqual({a["floor"] for a, _ in pairs}, set(range(1, 13)))
        for old, new in pairs:
            for key in study.FIXED:
                self.assertEqual(old[key], new[key], (old["profile_id"], key))
            self.assertEqual(old["tactics"], new["tactics"])
            self.assertEqual(new["legacy_reincarnation_points"], 0)
            r, n = new["reincarnations"], new["level"]-1
            self.assertEqual(new["initial_points"], 125*min(r, 150)+100*max(r-150, 0))
            self.assertEqual(new["stat_growth_draws"], 5*n+25*max(r-150, 0)*n//99)
            self.assertEqual(new["attribute_growth_draws"], 3*n)
            self.assertEqual(old["stat_growth_draws"], 3*n)
            self.assertNotEqual(new["stats"], old["stats"])

    def test_336_conditions_pair_same_seed_and_c2_requires_all_skills(self):
        rows = study.scenarios()
        self.assertEqual(len(rows), 336)
        self.assertEqual(sum(r["evaluation_trials"] for r, _, _ in rows), 1680)
        for i in range(0, len(rows), 2):
            (old, label, scale), (new, other, other_scale) = rows[i:i+2]
            self.assertEqual((label, scale), (other, other_scale))
            self.assertEqual((old["floor"], old["job"]), (new["floor"], new["job"]))
            self.assertEqual((old["growth_version"], new["growth_version"]), ("old", "new"))
            self.assertNotIn("boss_override", old)
            if label == "C2":
                allowed = set(study.base.SKILL_CODES[old["job"]]) | set(old["permanent_skill_codes"])
                self.assertTrue(all(c in allowed for c, _ in study.balance_stage5b.C2))
                self.assertIn(old["job"], ("wizard", "priest"))
            if old["floor"] <= 2:
                self.assertNotEqual(label, "C2")
        self.assertEqual(len(study.scenarios(pilot=True)), 48)
        self.assertEqual(sum(r["evaluation_trials"] for r, _, _ in study.scenarios(3)), 1008)
        with self.assertRaises(ValueError):
            study.scenarios(1)

    def test_tampered_legacy_snapshot_is_rejected(self):
        source = copy.deepcopy(study.profile_pairs()[0][0])
        source["stats"]["max_hp"] += 1
        with self.assertRaisesRegex(ValueError, "再現不一致"):
            study.regenerate(source, "old")

    def test_normal_database_catalog_is_rejected(self):
        with self.assertRaises(RuntimeError):
            study.catalog()


class Stage6AExecutionTests(TestCase):
    def test_new_growth_cannot_issue_even_select_queries(self):
        source = study.profile_pairs()[0][0]
        def forbidden_growth(c):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        with patch.object(growth, "level_up_once", forbidden_growth):
            with self.assertRaisesRegex(AssertionError, "DB操作を禁止"):
                study.regenerate(source, "new")

    def test_formal_boss_and_skill_catalog_rejects_candidate_values(self):
        with contracts.ObservationContractTests().isolated():
            catalog = study.catalog()
            self.assertEqual(len(catalog["bosses"]), 12)
            boss = Enemy.objects.get(is_boss=True, floor=8)
            boss.max_hp += 1
            boss.save(update_fields=["max_hp"])
            with self.assertRaisesRegex(ValueError, "正式migration"):
                study.catalog()

    def test_new_high_reincarnation_profile_observation_preserves_engine_result(self):
        helper = contracts.ObservationContractTests()
        with helper.isolated():
            for floor in (8, 12):
                old, new = next(pair for pair in study.profile_pairs()
                                if pair[0]["floor"] == floor and pair[0]["job"] == "wizard")
                for row in (old, new):
                    character = sim.prepare_profile(row, row["selected_c"])
                    self.assertEqual(character.legacy_reincarnation_points, 0)
                    boss = Enemy.objects.get(is_boss=True, floor=floor)
                    before = Enemy.objects.values().get(pk=boss.pk)
                    observed = sim.measure(character, boss, 13061120, detail=True)
                    plain = sim.measure(character, boss, 13061120, observe=False)
                    self.assertEqual(observed["digest"], plain["digest"])
                    self.assertEqual(observed["final"], plain["final"])
                    self.assertEqual(Enemy.objects.values().get(pk=boss.pk), before)
                    diagnostic = study.diagnostic(observed)
                    self.assertIn("first_heal_action", diagnostic["player"])
                    self.assertTrue(observed["hp_events"])


class Stage6AStatisticsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        spec = importlib.util.spec_from_file_location("stage6_statistics", PATH.with_name("BALANCE_STAGE6A_REPORT.py"))
        cls.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.report)

    def test_missing_and_exceptions_are_not_counted_as_losses(self):
        empty = self.report.aggregate([], 5)
        self.assertEqual((empty["planned"], empty["missing"], empty["valid"], empty["losses"]), (5, 5, 0, 0))
        self.assertIsNone(empty["win_rate"])
        self.assertIn("未測定", self.report.rate(empty))
        failed = self.report.aggregate([{"exception": "example", "winner": None}], 5)
        self.assertEqual((failed["exceptions"], failed["missing"], failed["losses"]), (1, 4, 0))
        self.assertIsNone(failed["win_rate"])

    def test_flips_only_compare_successful_matching_seeds(self):
        old = [{"seed": 1, "winner": "enemy"}, {"seed": 2, "winner": "player"},
               {"seed": 3, "winner": "player"}, {"seed": 4, "winner": "enemy"}]
        new = [{"seed": 1, "winner": "player"}, {"seed": 2, "winner": "enemy"},
               {"seed": 3, "exception": "example"}, {"seed": 5, "winner": "player"}]
        paired = self.report.paired(old, new)
        self.assertEqual(paired["paired_valid_seeds"], [1, 2])
        self.assertEqual((paired["loss_to_win"], paired["win_to_loss"]), (1, 1))
