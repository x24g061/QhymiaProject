"""Ver.2評価専用の事前契約。DB接続なしで実行する。"""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("study_v2", HERE / "BALANCE_STAGE5C_V2_RUN.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class EvaluationContracts(unittest.TestCase):
    def test_plan_preserves_profiles_and_uses_legal_c2(self):
        rows = study.scenarios()
        self.assertEqual(len(rows), 224)
        self.assertEqual(sum(r["evaluation_trials"] for r, _, _ in rows), 1120)
        self.assertEqual(len({(r["profile_id"], label) for r, label, _ in rows}), len(rows))
        originals = {r["profile_id"]: r for r in study.base.profiles()}
        for row, label, _ in rows:
            source = originals[row["original_profile_id"]]
            self.assertEqual({k: row[k] for k in study.CORE}, {k: source[k] for k in study.CORE})
            self.assertEqual(row["tactics"]["B"], source["tactics"]["B"])
            if row["floor"] in (1, 2):
                self.assertNotEqual(label, "C2")
            if label == "C2":
                self.assertEqual(row["tactics"][label], study.previous.C2)

    def test_full_candidate_is_copy_and_preserves_every_other_field(self):
        for floor in study.FLOORS:
            values = study.NEW[floor]
            boss = SimpleNamespace(**values, is_boss=True, skill_codes=["example"], experience=100)
            before = copy.deepcopy(vars(boss))
            overrides = {k: values[k] for k in ("attribute", *study.FIELDS)}
            candidate = study.evaluation_boss(boss, overrides)
            self.assertIsNot(candidate, boss)
            self.assertEqual(vars(candidate), before | overrides)
            self.assertEqual(vars(boss), before)
            for invalid in ({}, {"strength": values["strength"]}, overrides | {"agility": -1}):
                with self.assertRaises(ValueError):
                    study.evaluation_boss(boss, invalid)

    def test_unexpected_catalog_is_rejected(self):
        old = study.importlib.import_module("apps.battle.migrations.0017_boss_balance_v1").BOSSES
        actual = [{"floor": floor, **copy.deepcopy(values)} for floor, values in old.items()]
        self.assertEqual(study.compare_catalog(actual)["status"], "matched")
        for field, value, index in (("max_hp", 1, 2), ("attribute", "dark", 0), ("skill_codes", [], 10)):
            changed = copy.deepcopy(actual)
            changed[index][field] = value
            self.assertEqual(study.compare_catalog(changed)["status"], "unexpected_difference")

    def test_normal_database_is_not_authorized(self):
        with self.assertRaises(RuntimeError):
            study.sim.require_isolation()


if __name__ == "__main__":
    unittest.main()
