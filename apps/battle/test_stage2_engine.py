"""実run()の極端値・ゲージ繰越・途中決着。攻撃だけを置き換えて行動を観測する。"""
from collections import Counter
from unittest.mock import patch
from django.test import SimpleTestCase
from apps.battle import test_agi_exploration as exploration_helpers
from apps.battle import test_agi_integration as arena_helpers
from apps.battle.initiative import calculate_gauge_gain


class EngineBoundaryTests(SimpleTestCase):
    pass


def run_case(self,case):
    mode,label=case
    agis={"zero":(0,0),"tiny":(1e-12,1e-12),"scale":(1e12,5e11),
          "burst":(100,100),"death":(100,100),"buff_debuff":(100,50)}
    a,b=agis[label]
    events=[];gains=[];calls=0
    if mode=="exploration":
        helper=exploration_helpers.ExplorationAGITests()
        engine=helper.build_engine(a,[b,b,b])
        participants=4
        gauge_target="apps.battle.engine.core.calculate_gauge_gain"
        if label=="burst":
            engine.player_initiative=1200
            for enemy in engine.enemy_combatants: enemy.initiative=1200

        def player():
            events.append(("player",calls//participants))
            if label=="death":
                for enemy in engine.enemy_combatants: enemy.hp=0
            if label=="buff_debuff":
                engine.get_player_stat=lambda name: 1000 if sum(s=="player" for s,t in events)==1 else 0
            return "normal"

        def enemy(): events.append(("enemy"+str(engine.current_enemy_index),calls//participants))
        engine.player_turn=player;engine.enemy_turn=enemy
        engine.get_floor_exp_range=lambda:(7,7)
    else:
        helper=arena_helpers.ArenaAGIIntegrationTests()
        engine,_=helper.build_engine(a,b)
        participants=2
        gauge_target="apps.battle.arena_engine.calculate_gauge_gain"
        if label=="burst":
            engine.challenger_combatant.initiative=1200
            engine.defender_combatant.initiative=1200

        def player():
            events.append(("player",calls//participants))
            if label=="death": engine.defender_combatant.hp=0
            if label=="buff_debuff":
                engine.challenger.agility=1000 if sum(s=="player" for s,t in events)==1 else 0

        engine.challenger_turn=player
        engine.defender_turn=lambda:events.append(("enemy0",calls//participants))

    def gain(agi,reference):
        nonlocal calls
        calls+=1
        value=calculate_gauge_gain(agi,reference)
        gains.append((agi,reference,value))
        return value

    with patch(gauge_target,side_effect=gain):
        result=helper.run_engine(engine) if mode=="exploration" else helper.run_engine(engine,1000)
    counts=Counter(side for side,tick in events)
    self.assertTrue(all(value==1 for value in Counter(events).values()))
    self.assertTrue(all(1<=g<=95 for a,r,g in gains))
    self.assertTrue(all(r==max(1,a,b) for _,r,_ in gains))
    if label=="death":
        self.assertEqual(events,[("player",2)])
        self.assertEqual(result["winner"],"player" if mode=="exploration" else "challenger")
        if mode=="exploration": self.assertEqual(result["exp_gained"],7)
    else:
        self.assertEqual(result["winner"],"draw")
        self.assertEqual(calls//participants,1000)
        if mode=="exploration": self.assertEqual(result["exp_gained"],0)
        if label in ("zero","tiny"):
            self.assertEqual(counts["player"],10)
            self.assertEqual(counts["enemy0"],10)
        if label=="scale":
            self.assertEqual(counts["player"],900)
            self.assertEqual(counts["enemy0"],450)
        if label=="burst":
            self.assertEqual(counts["player"],912)
            self.assertEqual(counts["enemy0"],912)
        if label=="buff_debuff":
            self.assertTrue(any(g==95 for _,_,g in gains))
            self.assertTrue(any(g==1 for _,_,g in gains))
            self.assertLess(counts["player"],counts["enemy0"])


for _mode in ("exploration","arena"):
    for _label in ("zero","tiny","scale","burst","death","buff_debuff"):
        def test(self,case=(_mode,_label)): run_case(self,case)
        setattr(EngineBoundaryTests,"test_"+_mode+"_"+_label,test)
