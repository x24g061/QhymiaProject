"""Stage6-Cの固定格子・メモリ限定候補・詳細観測の不介入契約。"""
import copy
import importlib.util
from pathlib import Path
import random
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from apps.battle import test_simulation_v2 as contracts
from apps.battle.models import Enemy

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/変更詳細/balance_stage6c"
spec = importlib.util.spec_from_file_location("stage6c_contract", DIRECTORY / "run.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class Stage6CConditionsTests(SimpleTestCase):
    def test_full_factorial_and_frozen_players(self):
        self.assertEqual(len(study.grid()), 20)
        self.assertEqual({(v["hp"], v["agi"]) for v in study.grid()}, {(h, a) for h in study.HPS for a in study.AGIS})
        for n in (3, 5):
            rows = study.scenarios("screen", trials=n)
            self.assertEqual((len(rows), sum(r["evaluation_trials"] for r, _, _ in rows)), (280, 280*n))
            for row, label, scale in rows:
                original = study.profiles()[row["job"]]
                for field in study.base.previous.FIXED+study.base.previous.REPLAY_FIELDS+("tactics",):
                    self.assertEqual(row[field], original[field])
                self.assertEqual(row["legacy_reincarnation_points"], 0)
                self.assertEqual(scale, 1)
                self.assertIn(label, ("B", original["selected_c"]))
        self.assertEqual(len(study.scenarios("pilot")), 80)

    def test_extra_fields_other_floors_and_unregistered_values_are_rejected(self):
        boss = Enemy(floor=8, is_boss=True, skill_codes=list(study.SKILLS))
        for value in ({"max_hp": 50000}, {"max_hp": 50000, "agility": 180, "strength": 999},
                      {"max_hp": 125000, "agility": 180}, {"max_hp": True, "agility": 180}):
            with self.assertRaises(ValueError):
                study.evaluation_boss(boss, value)
        boss.floor = 7
        with self.assertRaises(ValueError):
            study.evaluation_boss(boss, study.CONTROL)
        boss.floor = 8
        boss.skill_codes.reverse()
        with self.assertRaises(ValueError):
            study.evaluation_boss(boss, study.CONTROL)

    def test_registered_intermediate_is_memory_only(self):
        boss = Enemy(floor=8, is_boss=True, max_hp=50000, agility=180, strength=950, skill_codes=list(study.SKILLS))
        before = copy.deepcopy({f.attname: getattr(boss, f.attname) for f in boss._meta.concrete_fields})
        variant = {"id": study.cid(125000, 2250), "hp": 125000, "agi": 2250}
        clone = study.evaluation_boss(boss, {"max_hp": 125000, "agility": 2250}, [variant])
        for f in boss._meta.concrete_fields:
            self.assertEqual(getattr(boss, f.attname), before[f.attname])
            if f.attname not in ("max_hp", "agility"):
                self.assertEqual(getattr(clone, f.attname), before[f.attname])

    def test_c_band_has_no_preference_for_25_or_reference_34(self):
        analysis = study.load("stage6c_stats_contract", DIRECTORY / "analyze.py")
        for rate in (.25, .34, .45, .60):
            self.assertEqual(analysis.score(.35, rate), 0)
        self.assertAlmostEqual(analysis.score(.35, .70), .10)

    def test_shortlist_does_not_fall_back_to_distant_all_wins(self):
        analysis = study.load("stage6c_select_contract", DIRECTORY / "analyze.py")
        def metric(name, penalty, gap):
            return {"candidate": name, "hp": 100000, "agi": 1800, "control": False, "complete": True,
                    "rate_penalty": penalty, "zero_job_cells": 0, "max_gap": gap, "exhaustion_mean": 0,
                    "no_threat_mean": 0}
        selected = analysis.shortlist([metric("near", .05, .7), metric("far_all_win", 1.05, 0)])
        self.assertEqual([v["id"] for v in selected["variants"]], ["near"])


class Stage6CObservationTests(TestCase):
    def test_trace_preserves_engine_result_rng_and_formal_records(self):
        helper = contracts.ObservationContractTests()
        with helper.isolated():
            for job, hp, agi in (("warrior", 50000, 180), ("priest", 200000, 180),
                                 ("hunter", 100000, 2700), ("wizard", 150000, 3600)):
                row = study.profiles()[job]
                c = study.sim.prepare_profile(row, row["selected_c"])
                boss = Enemy.objects.get(is_boss=True, floor=8)
                before = Enemy.objects.values().get(pk=boss.pk)
                clone = study.evaluation_boss(boss, {"max_hp": hp, "agility": agi})
                state = random.getstate()
                with patch.object(Enemy, "save", side_effect=AssertionError("正式ボス保存禁止")):
                    observed = study.trace.measure(study.sim, c, clone, 35061120)
                    plain = study.sim.measure(c, clone, 35061120, observe=False)
                self.assertEqual(observed["digest"], plain["digest"])
                self.assertEqual(observed["final"], plain["final"])
                self.assertEqual(random.getstate(), state)
                self.assertEqual(Enemy.objects.values().get(pk=boss.pk), before)
                self.assertEqual(len(observed["skill_trace"]["frames"]), len(observed["actions"]))
                self.assertEqual(len(observed["skill_trace"]["hp_contexts"]), len(observed["hp_events"]))

    def test_attempt_reasons_successes_and_effect_lifetimes_are_observed(self):
        with contracts.ObservationContractTests().isolated():
            row = study.profiles()["warrior"]
            c = study.sim.prepare_profile(row, "B")
            boss = study.evaluation_boss(Enemy.objects.get(is_boss=True, floor=8), {"max_hp": 150000, "agility": 3600})
            r = study.trace.measure(study.sim, c, boss, 35061121)
            successes = r["boss"]["skills"]
            for code, counts in r["titan_analysis"]["skill_attempts"]["boss"].items():
                self.assertEqual(counts["attempts"], sum(counts.get(k, 0) for k in ("success", "activation_failure", "mp_shortage")))
                self.assertEqual(counts.get("success", 0), successes.get(code, 0))
            self.assertTrue(r["titan_analysis"]["boss_first_five"])
            steel = [f for f in r["skill_trace"]["frames"] if f["side"] == "boss" and f["code"] == "steel_body"]
            self.assertTrue(steel)
            for frame in steel:
                self.assertEqual(frame["skill_peaks"][-1]["after_skill"]["boss"]["steel_body_turns"], 1)
                self.assertEqual(frame["finished"]["boss"]["steel_body_turns"], 1)
            self.assertLessEqual(r["titan_analysis"]["boss_threatening_direct_actions"], r["titan_analysis"]["boss_direct_attack_actions"])

    def test_damage_context_has_buff_state_at_each_actual_hp_change(self):
        with contracts.ObservationContractTests().isolated():
            row = study.profiles()["grappler"]
            c = study.sim.prepare_profile(row, "B")
            boss = study.evaluation_boss(Enemy.objects.get(is_boss=True, floor=8), {"max_hp": 100000, "agility": 1800})
            r = study.trace.measure(study.sim, c, boss, 35061122)
            for event, context in zip(r["hp_events"], r["skill_trace"]["hp_contexts"]):
                self.assertEqual(event["target"], context["target"])
                self.assertEqual(set(context["states"]["boss"]), set(study.trace.BUFFS))
            self.assertEqual(r["titan_analysis"]["player_healing_shield_actions"], r["player"]["skills"].get("healing_shield", 0))
