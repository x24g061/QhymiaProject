"""ランク別の強化境界と、属性成長が実ダメージへ反映される経路。"""
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from apps.accounts.models import User, Character
from apps.accounts.growth import apply_attribute_growth
from apps.inventory.models import Equipment, OwnedEquipment
from apps.inventory.services import calculate_equipment_battle_power
from apps.battle.models import Enemy
from apps.battle.services import BattleEngine

EXPECTED = {
    "F": [11,231,412,9588,11505,13806], "E": [11,209,371,8630,10355,12426],
    "D": [11,187,331,7672,9206,11047], "C": [11,165,291,6714,8056,9667],
    "B": [11,143,251,5757,6907,8288], "A": [11,121,211,4799,5758,6908],
    "S": [11,99,171,3841,4608,5529],
}


class EnhancementBoundaryTests(SimpleTestCase):
    pass


def enhancement(self,rank):
    master=Equipment(rank=rank,base_battle_power=11,strength_rate=55,dexterity_rate=20,
                     agility_rate=10,vitality_rate=10,luck_rate=5)
    previous=0
    for level,expected in zip([0,5,6,11,12,13],EXPECTED[rank]):
        with self.subTest(level=level):
            power=calculate_equipment_battle_power(11,rank,level)
            self.assertEqual(power,expected)
            self.assertGreaterEqual(power,previous);previous=power
            owned=OwnedEquipment(equipment=master,battle_power=power,enhancement_level=level)
            self.assertEqual(owned.get_stat_bonus("strength"),power*55//200)
            self.assertEqual(owned.get_stat_bonus("dexterity"),power*20//200)
            self.assertEqual(owned.get_stat_bonus("intelligence"),0)


for _rank in EXPECTED:
    def test(self,rank=_rank): enhancement(self,rank)
    setattr(EnhancementBoundaryTests,"test_rank_"+_rank+"_thresholds_and_bonuses",test)


class AttributeCombatIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user=User.objects.create_user(user_id="stage2-attribute",email="attribute@example.com",password=None)
        cls.character=Character.objects.create(user=user,name="属性成長")
        cls.enemy=Enemy.objects.create(name="属性対象",floor=1,max_hp=100000,
            intelligence=20,vitality=20,attribute="neutral")


def attribute(self,field):
    for name in ("fire","water","grass","rock","light","dark"):
        setattr(self.character,name,3)
    setattr(self.character,field,5)
    # 最高値=平均×1.5という境界では得意属性にならない。
    self.assertEqual(self.character.get_main_attribute(),"neutral")
    apply_attribute_growth(self.character,field)
    self.assertEqual(getattr(self.character,field),6)
    self.assertEqual(self.character.get_main_attribute(),field)
    for kind,expected in [("physical",1138),("magic",1143)]:
        with self.subTest(kind=kind):
            engine=BattleEngine(self.character,self.enemy)
            before=engine.enemy_hp
            # 命中のみ成功、物理クリティカルは失敗。計算式と装備/種族処理は実処理。
            with patch.object(engine,"roll_percent",side_effect=[True,False] if kind=="physical" else [True]):
                hit=getattr(engine,"player_"+kind+"_skill_hit")(
                    skill_name="属性検証",base_damage=1000,attribute=field)
            self.assertTrue(hit)
            self.assertEqual(before-engine.enemy_hp,expected)


for _field in ("fire","water","grass","rock","light","dark"):
    def test(self,field=_field): attribute(self,field)
    setattr(AttributeCombatIntegrationTests,"test_"+_field+"_growth_reaches_damage_calculation",test)
