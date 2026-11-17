"""候補値の非永続化・単一能力・条件共有の契約。"""
import copy
from unittest.mock import patch
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from apps.battle import balance_stage5b as study, simulation_v2 as sim
from apps.battle import test_simulation_v2 as contracts
from apps.battle.management.commands.simulate_boss_v2 import trial_count
from apps.battle.models import Enemy


class Stage5BPlanTests(SimpleTestCase):
    def test_scenarios_are_unique_and_controls_are_shared(self):
        rows=study.scenarios()
        keys=[(r["profile_id"],label) for r,label,_ in rows]
        self.assertEqual(len(keys),len(set(keys)))
        for r,label,_ in rows:
            self.assertLessEqual(len(r["boss_override"]),1)
            if "C2_focus" in r["experiments"]:
                self.assertEqual(r["evaluation_trials"],30)
            if len(r["experiments"])==2:
                self.assertEqual((r["floor"],r["boss_override"]),(7,{}))

    def test_trial_count_validation_and_legacy_default(self):
        self.assertEqual(trial_count({},5),5)
        self.assertEqual(trial_count({"evaluation_trials":30},5),30)
        for n in (0,-1,True,3.5):
            with self.assertRaises(CommandError):
                trial_count({"evaluation_trials":n},5)


class Stage5BBossTests(TestCase):
    def test_candidate_changes_only_one_field_and_never_database(self):
        for floor,(field,values) in study.CANDIDATES.items():
            original=Enemy.objects.get(is_boss=True,floor=floor)
            snapshot=copy.deepcopy(original.__dict__)
            for value in values:
                candidate=study.evaluation_boss(original,{field:value})
                self.assertIsNot(original,candidate)
                self.assertEqual(getattr(candidate,field),value)
                for model_field in original._meta.concrete_fields:
                    if model_field.attname != field:
                        self.assertEqual(getattr(candidate,model_field.attname),snapshot[model_field.attname])
            original.refresh_from_db()
            self.assertEqual(getattr(original,field),values[0])

    def test_invalid_overrides_are_rejected(self):
        boss=Enemy.objects.get(is_boss=True,floor=8)
        for invalid in ({"max_hp":50000},{"agility":541},{"agility":540,"max_hp":50000}):
            with self.assertRaises(ValueError):
                study.evaluation_boss(boss,invalid)

    def test_c2_uses_same_inventory_and_candidate_measurement_preserves_boss(self):
        helper=contracts.ObservationContractTests()
        row=next(r for r,label,_ in study.scenarios() if r["floor"]==7 and r["job"]=="wizard" and label=="C2" and not r["boss_override"])
        with helper.isolated():
            character=sim.prepare_profile(row,"C2")
            self.assertEqual(list(character.skill_presets.values_list("skill__code","use_count")),study.C2)
            boss=Enemy.objects.get(is_boss=True,floor=7)
            before=Enemy.objects.values().get(pk=boss.pk)
            candidate=study.evaluation_boss(boss,{"intelligence":1280})
            with patch.object(Enemy,"save",side_effect=AssertionError("DB保存禁止")):
                sim.measure(character,candidate,70361117)
            self.assertEqual(Enemy.objects.values().get(pk=boss.pk),before)
