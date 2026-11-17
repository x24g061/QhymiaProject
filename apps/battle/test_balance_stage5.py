"""5-A条件の合法性と実測器の職業横断プリセット契約。"""
import copy
from django.test import SimpleTestCase, TestCase
from apps.battle import balance_stage5 as study, simulation_v2 as sim
from apps.battle import test_simulation_v2 as contracts
from apps.battle.models import Skill


class Stage5ConditionTests(SimpleTestCase):
    def test_all_profiles_have_legal_history_and_pairable_tactics(self):
        rows=list(study.profiles())
        self.assertEqual(len(rows),154)
        for row in rows:
            study.validate_profile(row)
            self.assertEqual(set(row["tactics"]), {"B","C"})
            if row["reincarnations"] >= 10 and row["inheritance_mode"] == "trained":
                self.assertEqual(len(row["permanent_skill_codes"]),10)

    def test_complete_job_training_is_guaranteed_across_seeds(self):
        for job in study.SKILL_CODES:
            for seed in (1,2,3,20261117):
                codes,history,rest=study.inheritance(job,10,seed)
                expected=set().union(*(study.SKILL_CODES[j] for j in study.origins(job)))
                self.assertSetEqual(set(codes), expected)
                self.assertEqual(len(history),10)
                self.assertEqual(rest["count"],0)

    def test_partial_training_does_not_exceed_reincarnations(self):
        for count in (0,1,2,5,9,10,20,657):
            codes,history,rest=study.inheritance("wizard",count)
            self.assertEqual(len(codes),min(count,10))
            self.assertEqual(len(history)+rest["count"],count)

    def test_invalid_history_and_six_slots_are_rejected(self):
        row=next(r for r in study.profiles() if r["inheritance_mode"]=="trained")
        invalid=copy.deepcopy(row)
        invalid["inheritance_history"][0]["previous_job"]="assassin"
        with self.assertRaises(ValueError):
            study.validate_profile(invalid)
        for uses in (0,-1,True):
            with self.assertRaises(ValueError):
                sim.profile_tactic({"tactics":{"B":[("fire",uses)]}},"B")
        with self.assertRaises(ValueError):
            sim.profile_tactic({"tactics":{"B":[("fire",1)]*6}},"B")


class Stage5ExecutionTests(TestCase):
    def test_custom_slots_use_inheritance_and_record_actual_tactic(self):
        helper=contracts.ObservationContractTests()
        with helper.isolated():
            row=helper.row() | {"permanent_skill_codes":["true_fist"],
                                "tactics":{"B":[("true_fist",2)],"C":[("fire",3)]}}
            for label,code in (("B","true_fist"),("C","fire")):
                character=sim.prepare_profile(row,label)
                preset=character.skill_presets.get()
                self.assertEqual(preset.skill.code,code)
                self.assertEqual(character.permanent_skills.count(),1)
            row["permanent_skill_codes"]=[]
            with self.assertRaises(Skill.DoesNotExist):
                sim.prepare_profile(row,"B")

    def test_condition_catalog_matches_database(self):
        for job,codes in study.SKILL_CODES.items():
            self.assertSetEqual(set(codes),set(Skill.objects.filter(job=job).values_list("code",flat=True)))
