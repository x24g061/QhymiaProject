"""敵アイコンと戦闘画面の表示回帰テスト。"""
from django.test import SimpleTestCase
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.templatetags.static import static

from apps.accounts.models import Character
from apps.battle.enemy_icons import AVAILABLE_ICON_STEMS, enemy_image_path


class EnemyBattleIconTests(SimpleTestCase):
    def test_all_48_image_files_exist(self):
        self.assertEqual(len(AVAILABLE_ICON_STEMS), 48)
        for stem in AVAILABLE_ICON_STEMS:
            with self.subTest(stem=stem):
                self.assertIsNotNone(
                    finders.find(f"images/enemies/{stem}.png")
                )

    def test_regular_and_boss_images(self):
        self.assertEqual(
            enemy_image_path(1, "草原スライム"),
            "images/enemies/1_草原スライム.png",
        )
        self.assertEqual(
            enemy_image_path(1, "キングスライム", True),
            "images/enemies/1_boss_キングスライム.png",
        )

    def test_renamed_assets_match_enemy_master(self):
        self.assertEqual(
            enemy_image_path(5, "ファイアオーク"),
            "images/enemies/5_ファイアオーク.png",
        )
        self.assertEqual(
            enemy_image_path(7, "ポイズンフロッグ"),
            "images/enemies/7_ポイズンフロッグ.png",
        )
        self.assertEqual(
            enemy_image_path(11, "ウィンドハーピー"),
            "images/enemies/11_ウィンドハーピー.png",
        )

    def _battle_html(self, image_path, hp=15):
        return render_to_string("battle.html", {
            "character": Character(name="テスト勇者"),
            "selected_floor": 1,
            "boss_encounter": False,
            "battle_result": {
                "winner": "draw",
                "player_hp": 30,
                "player_max_hp": 30,
                "player_stamina": 100,
                "player_max_stamina": 100,
                "enemies": [{
                    "name": "草原スライム",
                    "image_path": image_path,
                    "hp": hp,
                    "max_hp": 30,
                    "mp": 0,
                    "max_mp": 0,
                }],
            },
            "battle_logs": [],
            "exp_gained": 0,
        })

    def test_enemy_image_renders_in_battle(self):
        path = enemy_image_path(1, "草原スライム")
        html = self._battle_html(path)
        self.assertIn(f'src="{static(path)}"', html)
        self.assertIn('class="enemy-battle-icon"', html)
        self.assertNotIn("敵アイコン", html)

    def test_unknown_enemy_uses_fallback(self):
        self.assertIsNone(enemy_image_path(1, "未知の敵"))
        html = self._battle_html(None)
        self.assertIn('class="enemy-icon-fallback"', html)
        self.assertNotIn('class="enemy-battle-icon"', html)

    def test_defeated_enemy_has_visual_state(self):
        html = self._battle_html(enemy_image_path(1, "草原スライム"), hp=0)
        self.assertIn("is-defeated", html)
