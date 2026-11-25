from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import Character
from apps.battle.models import ArenaState


User = get_user_model()


class SignupBonusTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="signup-bonus-test",
            email="bonus@example.invalid",
            password="TestPassword123",
        )

        self.client.force_login(self.user)

    def create_character(self, name="特典テスト"):
        with patch(
            "apps.accounts.views.get_available_character_images",
            return_value=[
                {
                    "number": 1,
                    "image": "images/characters/001.png",
                }
            ],
        ):
            return self.client.post(
                reverse("accounts:character_create"),
                {
                    "character_name": name,
                    "race": "human",
                    "job": "wanderer",
                    "character_image_id": "1",
                },
            )

    def test_normal_signup_has_bonus_right(self):
        self.client.logout()

        response = self.client.post(
            reverse("accounts:signup"),
            {
                "user_id": "new-bonus-user",
                "email": "new-bonus@example.invalid",
                "password1": "WelcomeGame123",
                "password2": "WelcomeGame123",
            },
        )

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(user_id="new-bonus-user")
        self.assertTrue(user.signup_bonus_pending)

    def test_first_character_receives_300q(self):
        response = self.create_character()

        self.assertEqual(response.status_code, 302)

        character = Character.objects.get(user=self.user)

        self.assertEqual(character.gold, 300)
        self.assertTrue(
            ArenaState.objects.filter(
                character=character
            ).exists()
        )

    def test_bonus_right_is_consumed(self):
        self.create_character()
        self.user.refresh_from_db()

        self.assertFalse(
            self.user.signup_bonus_pending
        )

    def test_existing_account_receives_no_bonus(self):
        self.user.signup_bonus_pending = False

        self.user.save(
            update_fields=["signup_bonus_pending"]
        )

        self.create_character()

        character = Character.objects.get(user=self.user)

        self.assertEqual(character.gold, 0)

    def test_recreated_character_receives_no_bonus(self):
        self.create_character()

        Character.objects.get(
            user=self.user
        ).delete()

        self.create_character("再作成テスト")

        character = Character.objects.get(user=self.user)

        self.assertEqual(character.gold, 0)

    def test_duplicate_request_does_not_grant_bonus(self):
        self.create_character()
        self.create_character("二重送信テスト")

        characters = Character.objects.filter(
            user=self.user
        )

        self.assertEqual(characters.count(), 1)
        self.assertEqual(characters.get().gold, 300)

    def test_invalid_character_keeps_bonus_right(self):
        response = self.create_character("")

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertTrue(self.user.signup_bonus_pending)

        self.assertFalse(
            Character.objects.filter(
                user=self.user
            ).exists()
        )

    def test_arena_creation_failure_rolls_back_bonus(self):
        with patch(
            "apps.accounts.views.ArenaState.objects.create",
            side_effect=RuntimeError("テスト用エラー"),
        ):
            with self.assertRaises(RuntimeError):
                self.create_character()

        self.user.refresh_from_db()

        self.assertTrue(self.user.signup_bonus_pending)

        self.assertFalse(
            Character.objects.filter(
                user=self.user
            ).exists()
        )

    def test_passwordless_account_receives_bonus(self):
        # Google登録後を想定したパスワードなしの
        # アカウントで共通配布処理を確認する。
        user = User.objects.create_user(
            user_id="social-bonus-test",
            email="social-bonus@example.invalid",
            password=None,
        )

        self.client.force_login(user)
        self.create_character("Google特典テスト")

        character = Character.objects.get(user=user)

        self.assertEqual(character.gold, 300)

        user.refresh_from_db()
        self.assertFalse(user.signup_bonus_pending)


class SignupBonusMigrationTests(TransactionTestCase):

    def test_existing_users_are_excluded(self):
        old = [
            ("accounts", "0024_usersettings_background_image")
        ]

        new = [
            ("accounts", "0025_user_signup_bonus_pending")
        ]

        executor = MigrationExecutor(connection)

        try:
            executor.migrate(old)

            old_apps = executor.loader.project_state(
                old
            ).apps

            OldUser = old_apps.get_model(
                "accounts", "User"
            )

            OldCharacter = old_apps.get_model(
                "accounts", "Character"
            )

            old_user = OldUser.objects.create(
                user_id="old-bonus-user",
                email="old-bonus@example.invalid",
            )

            OldCharacter.objects.create(
                user=old_user,
                name="既存キャラクター",
                gold=1500,
            )

            MigrationExecutor(connection).migrate(new)

            user = User.objects.get(pk=old_user.pk)

            self.assertFalse(user.signup_bonus_pending)

            self.assertEqual(
                Character.objects.get(user=user).gold,
                1500,
            )

            new_user = User.objects.create_user(
                user_id="new-migration-user",
                email="migration-new@example.invalid",
                password=None,
            )

            self.assertTrue(
                new_user.signup_bonus_pending
            )

        finally:
            # 後続テストに影響しないように
            # 最新のマイグレーション状態へ復元する。
            executor = MigrationExecutor(connection)

            executor.migrate(
                executor.loader.graph.leaf_nodes()
            )
