from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from apps.accounts.beginner_buff import (
    is_beginner_buff_active,
    get_beginner_buff_remaining,
)


class BeginnerBuffTests(SimpleTestCase):

    def setUp(self):
        self.now = timezone.now()

    def make_user(self, elapsed):
        return SimpleNamespace(
            date_joined=self.now - elapsed
        )

    def test_new_user(self):
        user = self.make_user(timedelta(seconds=0))
        self.assertTrue(
            is_beginner_buff_active(user, self.now)
        )

    def test_before_expiration(self):
        user = self.make_user(
            timedelta(hours=71, minutes=59, seconds=59)
        )
        self.assertTrue(
            is_beginner_buff_active(user, self.now)
        )

    def test_exact_expiration(self):
        user = self.make_user(timedelta(hours=72))
        self.assertFalse(
            is_beginner_buff_active(user, self.now)
        )

    def test_expired_user(self):
        user = self.make_user(timedelta(days=4))
        self.assertFalse(
            is_beginner_buff_active(user, self.now)
        )

    def test_remaining_time(self):
        user = self.make_user(timedelta(hours=24))
        self.assertEqual(
            get_beginner_buff_remaining(user, self.now),
            172800,
        )

    def test_expired_remaining_time(self):
        user = self.make_user(timedelta(days=4))
        self.assertEqual(
            get_beginner_buff_remaining(user, self.now),
            0,
        )


class BeginnerCooldownTests(SimpleTestCase):

    def make_character(self, beginner, item_active):
        from apps.accounts.models import User, Character

        now = timezone.now()

        user = User(
            date_joined=now - timedelta(
                hours=1 if beginner else 100
            )
        )

        return Character(
            user=user,
            exploration_cooldown_reduced_until=(
                now + timedelta(days=1)
                if item_active else None
            ),
        )

    def test_normal_cooldown(self):
        character = self.make_character(False, False)
        self.assertEqual(
            character.get_exploration_cooldown_seconds(),
            40,
        )

    def test_beginner_cooldown(self):
        character = self.make_character(True, False)
        self.assertEqual(
            character.get_exploration_cooldown_seconds(),
            20,
        )

    def test_item_cooldown(self):
        character = self.make_character(False, True)
        self.assertEqual(
            character.get_exploration_cooldown_seconds(),
            20,
        )

    def test_combined_cooldown(self):
        character = self.make_character(True, True)
        self.assertEqual(
            character.get_exploration_cooldown_seconds(),
            10,
        )


class BeginnerBoostDisplayTests(SimpleTestCase):

    def make_character(self, hours):
        from apps.accounts.models import User, Character

        return Character(
            user=User(
                date_joined=timezone.now() - timedelta(hours=hours)
            )
        )

    def test_beginner_boost_is_displayed(self):
        from apps.inventory.boosts import get_active_boosts

        character = self.make_character(1)
        boosts = get_active_boosts(character)

        self.assertIn(
            "beginner_buff",
            [boost["key"] for boost in boosts],
        )

    def test_expired_boost_is_not_displayed(self):
        from apps.inventory.boosts import get_active_boosts

        character = self.make_character(73)
        boosts = get_active_boosts(character)

        self.assertNotIn(
            "beginner_buff",
            [boost["key"] for boost in boosts],
        )

    def test_beginner_and_clock_boosts_are_displayed(self):
        from apps.inventory.boosts import get_active_boosts

        character = self.make_character(1)

        character.exploration_cooldown_reduced_until = (
            timezone.now() + timedelta(days=1)
        )

        boosts = get_active_boosts(character)
        keys = [boost["key"] for boost in boosts]

        self.assertIn("beginner_buff", keys)
        self.assertIn("exploration_cooldown_reduction", keys)
