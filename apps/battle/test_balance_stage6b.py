"""Stage6-Bの単一能力・凍結条件・C許容帯・非永続化の契約。"""
import copy
import importlib.util
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from apps.battle import simulation_v2 as sim, test_simulation_v2 as contracts
from apps.battle.models import Enemy

PATH = Path(__file__).resolve().parents[2] / "docs/変更詳細/BALANCE_STAGE6B_RUN.py"
spec = importlib.util.spec_from_file_location("stage6b_contract", PATH)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class Stage6BPlanTests(SimpleTestCase):
    def test_all_new_profiles_tactics_and_inheritance_are_frozen(self):
        profiles = study.profiles()
        self.assertEqual(len(profiles), 21)
        rows = study.scenarios("screen")
        self.assertEqual((len(rows), sum(r["evaluation_trials"] for r, _, _ in rows)), (322, 1610))
        for row, label, scale in rows:
            source = profiles[row["floor"], row["job"]]
            for key in study.previous.FIXED + study.previous.REPLAY_FIELDS + ("tactics",):
                self.assertEqual(row[key], source[key])
            self.assertEqual(row["growth_version"], "new")
            self.assertEqual(row["legacy_reincarnation_points"], 0)
            self.assertLessEqual(len(row["boss_override"]), 1)
            self.assertIn(label, ("B", source["selected_c"]))
            self.assertEqual(scale, 1)

    def test_unique_candidates_and_agi_before_hp(self):
        candidates = study.candidates()
        self.assertEqual(len(candidates), 23)
        self.assertEqual(len({c["id"] for c in candidates}), 23)
        eight = [c for c in candidates if c["floor"] == 8]
        self.assertTrue(all("agility" in c["override"] for c in eight[1:5]))
        self.assertTrue(all("max_hp" in c["override"] for c in eight[5:]))
        self.assertEqual(len(study.scenarios("pilot")), 40)

    def test_c_inside_band_is_not_rewarded_for_being_near_25(self):
        a = study.selection_metrics(12, .50, .25, 0, .2, 5)
        b = study.selection_metrics(12, .50, .45, 0, .2, 5)
        self.assertEqual(a["rate_penalty"], b["rate_penalty"])
        self.assertEqual(a["c_band_distance"], 0)
        self.assertNotEqual(a["crossing_b_minus_c"], b["crossing_b_minus_c"])
        for c in (.25, .34, .45, .60):
            self.assertEqual(study.range_distance(c), 0)
        self.assertAlmostEqual(study.range_distance(.70), .10)

    def test_confirm_covers_all_jobs_and_shared_control_with_distinct_seeds(self):
        selected = []
        for f in study.GRID:
            selected += [c["id"] for c in study.candidates() if c["floor"] == f and c["override"]][:2]
        rows = study.scenarios("confirm", trials=15, selected=selected)
        self.assertEqual((len(rows), sum(r["evaluation_trials"] for r, _, _ in rows)), (126, 1890))
        self.assertEqual(len({(r["profile_id"], label) for r, label, _ in rows}), 126)
        self.assertTrue(set(range(study.SEEDS["screen"], study.SEEDS["screen"]+5)).isdisjoint(
            range(study.SEEDS["confirm"], study.SEEDS["confirm"]+15)))
        with self.assertRaises(ValueError):
            study.scenarios("confirm", selected=selected[:2])

    def test_selection_records_rate_and_fairness_without_crossing_preference(self):
        metrics = []
        for floor in study.GRID:
            for i, c in enumerate((.25, .45, .60)):
                metrics.append({"floor": floor, "candidate": f"f{floor}-test{i}", "control": False,
                                "complete": True, **study.selection_metrics(floor, study.B_TARGET[floor], c, 0, .2, 5)})
        selected = study.choose_candidates(metrics)
        self.assertEqual(len(selected["selected"]), 6)
        self.assertTrue(all(r["screen_metrics"]["rate_penalty"] == 0 for r in selected["reasons"]))


class Stage6BIsolationTests(TestCase):
    def test_every_candidate_only_changes_one_memory_field(self):
        for c in study.candidates():
            if not c["override"]:
                continue
            boss = Enemy.objects.get(is_boss=True, floor=c["floor"])
            before = copy.deepcopy(boss.__dict__)
            clone = study.evaluation_boss(boss, c["override"])
            self.assertIsNot(clone, boss)
            for f in boss._meta.concrete_fields:
                self.assertEqual(getattr(clone, f.attname), c["override"].get(f.attname, before[f.attname]))
                self.assertEqual(getattr(boss, f.attname), before[f.attname])

    def test_multi_field_and_unregistered_candidates_are_rejected(self):
        boss = Enemy.objects.get(is_boss=True, floor=8)
        for override in ({}, {"strength": 1000}, {"agility": 901}, {"agility": 1800, "max_hp": 150000}):
            with self.assertRaises(ValueError):
                study.evaluation_boss(boss, override)
        with self.assertRaises(ValueError):
            study.evaluation_boss(Enemy.objects.get(is_boss=True, floor=3), {"max_hp": 2000})

    def test_observed_candidate_preserves_results_and_formal_boss(self):
        helper = contracts.ObservationContractTests()
        with helper.isolated():
            for floor, override in ((8, {"agility": 2700}), (7, {"intelligence": 1300}), (12, {"max_hp": 220000})):
                row = study.profiles()[floor, "wizard"]
                character = sim.prepare_profile(row, row["selected_c"])
                boss = Enemy.objects.get(is_boss=True, floor=floor)
                before = Enemy.objects.values().get(pk=boss.pk)
                clone = study.evaluation_boss(boss, override)
                with patch.object(Enemy, "save", side_effect=AssertionError("ボス保存禁止")):
                    observed = sim.measure(character, clone, 24061120, detail=True)
                    plain = sim.measure(character, clone, 24061120, observe=False)
                self.assertEqual(observed["digest"], plain["digest"])
                self.assertEqual(Enemy.objects.values().get(pk=boss.pk), before)
