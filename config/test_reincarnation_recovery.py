
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User, Character
from apps.battle.models import ArenaFloor, ArenaState


class ReincarnationRecoveryTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="reinc_hp_test",
            email="reinc-hp@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="回帰HPテスト",
            level=100,
            exp=67,
            max_hp=140,
            current_hp=7,
            max_mp=80,
            current_mp=2,
        )

        self.floor, _ = ArenaFloor.objects.get_or_create(
            floor=3,
        )

        self.state = ArenaState.objects.create(
            character=self.character,
            floor=self.floor,
            current_hp=3,
            current_mp=1,
        )

        # 初回回帰の125ポイント
        bonus_points = {
            "max_hp": 5,
            "max_mp": 4,
            "strength": 116,
            "intelligence": 0,
            "dexterity": 0,
            "agility": 0,
            "vitality": 0,
            "luck": 0,
            "fire": 0,
            "water": 0,
            "grass": 0,
            "rock": 0,
            "light": 0,
            "dark": 0,
        }

        self.client.force_login(self.user)

        session = self.client.session
        session["reincarnation_bonus_points"] = bonus_points
        session.save()

    def test_reincarnation_recovers_all_hp_and_mp(self):
        """回帰後、通常HPと闘技場HPが全回復する。"""

        self.floor.master = self.character
        self.floor.save(update_fields=["master"])

        response = self.client.post(reverse("again"))

        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )

        self.character.refresh_from_db()
        self.state.refresh_from_db()
        self.floor.refresh_from_db()

        # 回帰後の新しい最大値
        self.assertEqual(self.character.max_hp, 55)
        self.assertEqual(self.character.max_mp, 18)

        # 通常HP・MP
        self.assertEqual(self.character.current_hp, 55)
        self.assertEqual(self.character.current_mp, 18)

        # 闘技場HP・MP
        self.assertEqual(self.state.current_hp, 55)
        self.assertEqual(self.state.current_mp, 18)

        # 階層とフロアマスターは維持
        self.assertEqual(self.state.floor_id, 3)
        self.assertEqual(
            self.floor.master_id,
            self.character.pk,
        )

        # 回帰回数・レベル・EXP
        self.assertEqual(self.character.reincarnation_count, 1)
        self.assertEqual(self.character.level, 1)
        self.assertEqual(self.character.exp, 0)

    def test_reincarnation_creates_missing_arena_state(self):
        """ArenaStateがなくても回帰時に補完される。"""

        self.state.delete()

        response = self.client.post(reverse("again"))
        self.assertEqual(response.status_code, 302)

        self.character.refresh_from_db()

        state = ArenaState.objects.get(
            character=self.character
        )

        self.assertEqual(state.floor_id, 1)
        self.assertEqual(state.current_hp, 55)
        self.assertEqual(state.current_mp, 18)

    def test_reincarnation_rolls_back_on_arena_error(self):
        """闘技場の更新に失敗したら通常ステータスも戻す。"""

        with patch(
            "config.views.get_arena_state",
            side_effect=RuntimeError("テスト用の更新失敗"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("again"))

        self.character.refresh_from_db()
        self.state.refresh_from_db()

        # 通常ステータスが回帰前のまま
        self.assertEqual(self.character.level, 100)
        self.assertEqual(self.character.exp, 67)
        self.assertEqual(self.character.reincarnation_count, 0)
        self.assertEqual(self.character.max_hp, 140)
        self.assertEqual(self.character.current_hp, 7)
        self.assertEqual(self.character.max_mp, 80)
        self.assertEqual(self.character.current_mp, 2)

        # 闘技場ステータスも変更されない
        self.assertEqual(self.state.current_hp, 3)
        self.assertEqual(self.state.current_mp, 1)
