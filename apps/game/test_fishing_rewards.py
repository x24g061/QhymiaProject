from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Character
from apps.game.models import FishingSession
from apps.inventory.models import InventoryItem, Item


class FishingRewardSecurityTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            user_id="fish_sec_test",
            email="fishing_security@example.com",
            password="test_password_123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="釣り検証キャラ",
        )

        self.client.force_login(self.user)

        self.fish = Item.objects.get(
            name="コモンの魚",
        )

        self.session = FishingSession.objects.create(
            user=self.user,
            rarity="コモン",
        )

        # auto_now_add の影響を受けないようDB上で時刻を設定
        FishingSession.objects.filter(
            pk=self.session.pk,
        ).update(
            started_at=timezone.now() - timedelta(seconds=10),
        )

        self.url = reverse("game:fishing_finish")

    def finish(self, session_id=None, success="true"):
        return self.client.post(
            self.url,
            {
                "session_id": (
                    self.session.pk
                    if session_id is None
                    else session_id
                ),
                "success": success,
            },
        )

    def fish_count(self):
        return (
            InventoryItem.objects.filter(
                character=self.character,
                item=self.fish,
            )
            .values_list("quantity", flat=True)
            .first()
            or 0
        )

    def test_success_grants_one_fish(self):
        response = self.finish()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fish_count(), 1)

    def test_same_session_cannot_claim_twice(self):
        first = self.finish()
        second = self.finish()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(self.fish_count(), 1)

    def test_failure_grants_no_fish(self):
        response = self.finish(success="false")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fish_count(), 0)

    def test_early_finish_is_rejected(self):
        FishingSession.objects.filter(
            pk=self.session.pk,
        ).update(
            started_at=timezone.now(),
        )

        response = self.finish()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.fish_count(), 0)

    def test_expired_session_is_rejected(self):
        FishingSession.objects.filter(
            pk=self.session.pk,
        ).update(
            started_at=timezone.now() - timedelta(seconds=121),
        )

        response = self.finish()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.fish_count(), 0)

    def test_other_users_session_is_rejected(self):
        User = get_user_model()

        other_user = User.objects.create_user(
            user_id="other_fish_test",
            email="other_fishing_security@example.com",
            password="test_password_123",
        )

        other_session = FishingSession.objects.create(
            user=other_user,
            rarity="コモン",
            started_at=timezone.now() - timedelta(seconds=10),
        )

        response = self.finish(
            session_id=other_session.pk,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.fish_count(), 0)
