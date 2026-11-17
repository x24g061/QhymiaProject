"""少数の観測契約のみ。勝率・難易度目標はassertしない。"""
from contextlib import contextmanager
import io
import random
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.test import TestCase, SimpleTestCase
from apps.accounts.models import Character
from apps.battle.models import Enemy
from apps.battle import simulation_v2 as sim


class IsolationAndStatisticsTests(SimpleTestCase):
    def test_normal_database_is_rejected_before_query(self):
        with self.assertRaises(RuntimeError):
            sim.require_isolation()

    def test_command_requires_explicit_isolation(self):
        with patch("apps.battle.management.commands.simulate_boss_v2.setup_databases") as setup:
            with self.assertRaises(CommandError):
                call_command("simulate_boss_v2", output="/tmp/not-created-v2", stdout=io.StringIO())
            setup.assert_not_called()

    def test_wilson_includes_zero_and_all_wins(self):
        self.assertEqual(sim.wilson(0, 30)[0], 0)
        self.assertAlmostEqual(sim.wilson(30, 30)[1], 1)
        low, high = sim.wilson(30, 300)
        self.assertTrue(0.07 < low < 0.08)
        self.assertTrue(0.13 < high < 0.14)
        self.assertIsNone(sim.wilson(0, 0))


class ObservationContractTests(TestCase):
    def test_permanent_inventory_is_explicit_and_does_not_leak_between_profiles(self):
        with self.isolated():
            row = self.row()
            inherited = row | {"permanent_skill_codes": ["steel_body", "principle_of_freedom"]}
            boss = Enemy.objects.get(floor=row["floor"], is_boss=True)
            for label in "BC":
                character = sim.prepare_profile(inherited, label)
                run = sim.measure(character, boss, 123)
                self.assertEqual(run["permanent_skill_count"], 2)
                self.assertEqual(run["permanent_skill_codes"], ["principle_of_freedom", "steel_body"])
            character = sim.prepare_profile(row, "B")
            self.assertEqual(character.permanent_skills.count(), 0)

    @contextmanager
    def isolated(self):
        # 通常のDjangoテストDB接続を既に開いていることを検証してから、名前ガードだけをテストする。
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if not cursor.fetchone()[0].startswith("test_"):
                raise RuntimeError("テストDB以外では契約テストを実行できません")
        name = "test_qhymia_simv2_contract"
        with patch.dict(connection.settings_dict, {"NAME": name}), sim.authorized_database(name):
            yield

    def row(self, floor=7, job="wizard", seed=20261117):
        return next(r for r in sim.load_profiles() if r["floor"] == floor and r["job"] == job
                    and r["seed"] == seed and (floor < 7 or r["variant"].startswith("mid-")))

    def test_all_tactics_are_legal_and_exclude_unfinished_effects(self):
        from apps.battle.models import Skill
        for job in sim.TACTICS:
            for label in "ABCD":
                slots = sim.tactic(job, label)
                self.assertLessEqual(len(slots), 5)
                for code, uses in slots:
                    self.assertNotIn(code, ("frost_armor", "purification", "resurrection"))
                    skill = Skill.objects.get(code=code, job=job)
                    self.assertGreaterEqual(uses, 1)
                    if skill.is_passive:
                        self.assertEqual(uses, 1)

    def test_observation_preserves_result_and_random_state(self):
        with self.isolated():
            for floor, job in [(1, "wanderer"), (7, "wizard"), (12, "assassin")]:
                row = self.row(floor, job)
                character = sim.prepare_profile(row, "B")
                boss = Enemy.objects.get(floor=floor, is_boss=True)
                before = random.getstate()
                observed = sim.measure(character, boss, 20261117, detail=True)
                plain = sim.measure(character, boss, 20261117, observe=False)
                repeated = sim.measure(character, boss, 20261117, detail=True)
                self.assertEqual(random.getstate(), before)
                self.assertEqual(observed, repeated)
                self.assertEqual(observed["digest"], plain["digest"])
                self.assertEqual(observed["final"], plain["final"])
                self.assertEqual(observed["initial"], plain["initial"])

    def test_readonly_guard_rejects_writes_during_battle(self):
        with self.isolated():
            character = sim.prepare_profile(self.row(), "B")
            original = character.max_hp
            boss = Enemy.objects.get(floor=7, is_boss=True)
            def illegal_run(engine):
                Character.objects.filter(pk=character.pk).update(max_hp=1)
            with patch.object(sim.BattleEngine, "run", illegal_run):
                with self.assertRaisesRegex(RuntimeError, "SQL"):
                    with transaction.atomic():
                        sim.measure(character, boss, 7)
            character.refresh_from_db()
            self.assertEqual(character.max_hp, original)

    def test_profile_and_boss_records_remain_unchanged(self):
        with self.isolated():
            character = sim.prepare_profile(self.row(6, "warrior"), "D")
            boss = Enemy.objects.get(floor=6, is_boss=True)
            before = (Character.objects.values().get(pk=character.pk), list(character.owned_equipments.values()),
                      list(character.skill_presets.values()), Enemy.objects.values().get(pk=boss.pk))
            run = sim.measure(character, boss, 123, detail=True)
            self.assertIn(run["winner"], ("player", "enemy", "draw"))
            self.assertEqual(before, (Character.objects.values().get(pk=character.pk), list(character.owned_equipments.values()),
                            list(character.skill_presets.values()), Enemy.objects.values().get(pk=boss.pk)))
            for side in ("player", "boss"):
                self.assertEqual(run["initial"][side]["hp"] + sum(run[side]["healing"].values())
                                 - sum(run[side]["damage_taken"].values()), run["final"][side]["hp"])
