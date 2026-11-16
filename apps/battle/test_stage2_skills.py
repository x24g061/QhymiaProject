"""全35スキルの共通行動契約と実装済み効果。未完成効果の正当化はしない。"""
from unittest.mock import patch
from django.test import TestCase
from apps.accounts.models import User, Character
from apps.battle.models import Skill, SkillPreset, Enemy
from apps.battle.services import BattleEngine
from apps.battle.boss_simulation import seeded_random

SKILLS = {
    "grappler": "double_punch shock_wave rapid_barrage fighting_spirit true_fist",
    "warrior": "flare_blade one_hit_kill steel_body solid_stance counter_stance",
    "hunter": "rapid_shot sleep_arrow hunter_eye hide poison_arrow",
    "wizard": "stella fire megido explosion frost_armor",
    "priest": "judgement healing_shield purification resurrection anti_jail",
    "wanderer": "strike_core mirage short_rest walker principle_of_freedom",
    "assassin": "surprise_attack poison_dagger stealth shadow_step flashbang",
}
INCOMPLETE = {"frost_armor", "purification", "resurrection"}
TIMERS = {"fighting_spirit":3,"steel_body":1,"solid_stance":1,"counter_stance":2,
          "hunter_eye":3,"hide":3,"healing_shield":3,"walker":3,"shadow_step":3}


class SkillContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user(user_id="stage2-skills",password=None)
        cls.character=Character.objects.create(user=cls.user,name="スキル検証",max_hp=10000,
            current_hp=3000,max_mp=10000,current_mp=10000,strength=200,intelligence=200,
            dexterity=200,agility=200,vitality=200,luck=200)
        cls.enemy=Enemy.objects.create(name="スキル対象",floor=1,max_hp=10000000,
            max_mp=10000,strength=20,intelligence=20,dexterity=20,agility=20,vitality=20,luck=20)

    def engine(self, code, race="human"):
        skill=Skill.objects.get(code=code)
        self.character.job=skill.job
        self.character.race=race
        SkillPreset.objects.filter(character=self.character).delete()
        first=SkillPreset.objects.create(character=self.character,skill=skill,slot=1,use_count=2)
        SkillPreset.objects.create(character=self.character,skill=skill,slot=2,use_count=3)
        return BattleEngine(self.character,self.enemy),skill,first


def success(self, code):
    engine,skill,preset=self.engine(code)
    hp,mp,enemy_hp=engine.player_hp,engine.player_mp,engine.enemy_hp
    if not skill.is_passive:
        self.assertEqual(skill.activation_rate,80)
    with seeded_random(20261116),patch.object(engine,"roll_percent",return_value=True):
        action=engine.player_turn()
    if skill.is_passive:
        self.assertEqual(action,"normal")
        self.assertEqual(engine.player_mp,mp)
        self.assertNotIn(preset.pk,engine.remaining_uses)
        self.assertTrue(engine.freedom_active)
        for _ in range(7): engine.finish_player_action("normal")
        self.assertAlmostEqual(engine.freedom_bonus,0.10)
        self.assertEqual(preset.use_count,2)
        return
    self.assertEqual(action,code)
    self.assertEqual(engine.player_mp,mp-skill.mp_cost)
    self.assertEqual(engine.remaining_uses[preset.pk],1)
    self.assertEqual(engine.preset_index,1)
    if skill.skill_type in ("physical","magic"):
        self.assertLess(engine.enemy_hp,enemy_hp)
    if code in TIMERS:
        self.assertEqual(getattr(engine,code+"_turns"),TIMERS[code])
        engine.finish_player_action(code)
        self.assertEqual(getattr(engine,code+"_turns"),TIMERS[code])
        for _ in range(TIMERS[code]): engine.finish_player_action("normal")
        self.assertEqual(getattr(engine,code+"_turns"),0)
    if code in ("short_rest","healing_shield"):
        self.assertGreater(engine.player_hp,hp)
        self.assertLessEqual(engine.player_hp,engine.player_max_hp)
    if code in ("mirage","stealth"):
        self.assertTrue(getattr(engine,code+"_active"))
    if code in ("poison_arrow","poison_dagger"):
        self.assertEqual(engine.enemy_poison_turns,5)
    if code=="sleep_arrow": self.assertEqual(engine.enemy_sleep_turns,3)
    if code=="judgement": self.assertEqual(engine.enemy_paralysis_turns,5)
    if code=="flashbang": self.assertTrue(1 <= engine.enemy_paralysis_turns <= 3)
    if code=="poison_dagger": self.assertEqual(engine.enemy_dex_debuff_rate,0.03)
    if code=="one_hit_kill":
        uses=dict(engine.remaining_uses)
        self.assertEqual(engine.player_turn(),"skip")
        self.assertEqual(engine.remaining_uses,uses)
    # INCOMPLETEの3技はMP/回数/スロットの契約だけを検証。効果の完成は主張しない。


def blocked(self, code):
    reasons=("sleep",) if code=="principle_of_freedom" else ("activation","mp","sleep","exhausted","witch_cost")
    for reason in reasons:
        with self.subTest(reason=reason):
            engine,skill,preset=self.engine(code,race="witch" if reason=="witch_cost" else "human")
            if skill.is_passive:
                engine.player_combatant.sleep_turns=1
                with patch.object(engine,"player_normal_attack") as normal:
                    self.assertEqual(engine.player_turn(),"skip")
                normal.assert_not_called()
                self.assertNotIn(preset.pk,engine.remaining_uses)
                continue
            if reason=="witch_cost":
                self.assertEqual(engine.get_skill_mp_cost(skill),skill.mp_cost*2)
                engine.player_mp=skill.mp_cost*2-1
            if reason=="mp": engine.player_mp=skill.mp_cost-1
            if reason=="sleep": engine.player_combatant.sleep_turns=1
            if reason=="exhausted":
                engine.remaining_uses={pk:0 for pk in engine.remaining_uses}
            before=(engine.player_mp,dict(engine.remaining_uses),engine.preset_index)
            with patch.object(engine,"roll_percent",return_value=False) as roll,patch.object(engine,"player_normal_attack") as normal:
                action=engine.player_turn()
            if reason=="activation":
                roll.assert_called_once_with(80)
            else:
                roll.assert_not_called()
            self.assertEqual(action,"skip" if reason=="sleep" else "normal")
            self.assertEqual(normal.call_count,0 if reason=="sleep" else 1)
            self.assertEqual((engine.player_mp,engine.remaining_uses),(before[0],before[1]))
            if reason!="exhausted": self.assertEqual(engine.preset_index,before[2])
            preset.refresh_from_db()
            self.assertEqual(preset.use_count,2)


for _job,_codes in SKILLS.items():
    for _code in _codes.split():
        for _label,_run in [("success",success),("blocked",blocked)]:
            def test(self,code=_code,run=_run): run(self,code)
            test.__name__="test_"+_job+"_"+_code+"_"+_label
            setattr(SkillContractTests,test.__name__,test)
