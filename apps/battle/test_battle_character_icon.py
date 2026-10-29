
from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.templatetags.static import static

from apps.accounts.models import Character


class BattleCharacterIconTests(SimpleTestCase):

    def render_battle(self, character):
        return render_to_string(
            "battle.html",
            {
                "character": character,
                "selected_floor": 1,
                "battle_result": {
                    "enemies": [],
                    "player_hp": 30,
                    "player_max_hp": 30,
                    "player_stamina": 100,
                    "player_max_stamina": 100,
                    "winner": "draw",
                },
                "battle_logs": [],
                "exp_gained": 0,
            },
        )

    def test_character_image_is_displayed(self):
        """設定したキャラ画像が戦闘画面に表示される。"""

        character = Character(
            name="テスト勇者",
            character_image_id=1,
        )

        html = self.render_battle(character)

        image_url = static("images/characters/001.png")

        self.assertIn(
            f'src="{image_url}"',
            html,
        )

        self.assertIn(
            'class="character-battle-icon"',
            html,
        )

    def test_character_without_image_has_fallback(self):
        """画像未設定でも代替表示される。"""

        character = Character(
            name="テスト勇者",
            character_image_id=None,
        )

        html = self.render_battle(character)

        self.assertIn("<span>テ</span>", html)
        self.assertNotIn(
            'class="character-battle-icon"',
            html,
        )
