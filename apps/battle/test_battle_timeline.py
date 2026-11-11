from django.test import SimpleTestCase
from django.template.loader import render_to_string
from apps.accounts.models import Character
from apps.battle.timeline import prepare_timeline, _status


class BattleTimelineTests(SimpleTestCase):
    def test_hp_mp_percentages_are_clamped(self):
        self.assertEqual(_status("X", 200, 100, 0, 0)["hp_percent"], 100)
        self.assertEqual(_status("X", 0, 0, 0, 0)["mp_percent"], 0)

    def test_damage_is_marked_for_highlight(self):
        turns = prepare_timeline([{
            "turn": 1, "actor": "勇者", "side": "player",
            "player": _status("勇者", 30, 30, 10, 10),
            "opponents": [_status("スライム", 0, 30, 0, 0)],
            "logs": ["勇者の攻撃！ スライムに12ダメージ！"],
        }])
        self.assertTrue(any(x["damage"] and x["text"] == "12"
                            for x in turns[0]["messages"][0]["parts"]))

    def test_shared_timeline_template(self):
        turns = prepare_timeline([{
            "turn": 1, "actor": "勇者", "side": "player",
            "player": _status("勇者", 30, 30, 10, 10),
            "opponents": [_status("スライム", 0, 30, 0, 0)],
            "logs": ["勇者の攻撃！ スライムに12ダメージ！"],
        }])
        html = render_to_string("components/battle_turn_timeline.html", {
            "timeline": turns, "character": Character(name="勇者"),
        })
        self.assertIn("1 ターン", html)
        self.assertIn("qh-damage", html)
        self.assertIn("スライム", html)

    def test_legacy_arena_log_has_fallback(self):
        html = render_to_string("components/battle_turn_timeline.html", {
            "timeline": [], "battle_logs": ["過去の対戦記録"],
        })
        self.assertIn("過去の対戦記録", html)
