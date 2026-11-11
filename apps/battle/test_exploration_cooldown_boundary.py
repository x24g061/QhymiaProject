from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.accounts.models import Character


class ExplorationCooldownBoundaryTests(SimpleTestCase):
    def test_fractional_second_is_not_reported_as_zero(self):
        now = timezone.now()
        character = Character(exploration_cooldown_until=now + timedelta(milliseconds=200))
        with patch("apps.accounts.models.timezone.now", return_value=now):
            self.assertEqual(character.get_exploration_cooldown_remaining(), 1)

    def test_more_than_one_second_rounds_up(self):
        now = timezone.now()
        character = Character(exploration_cooldown_until=now + timedelta(seconds=1, milliseconds=200))
        with patch("apps.accounts.models.timezone.now", return_value=now):
            self.assertEqual(character.get_exploration_cooldown_remaining(), 2)

    def test_completed_cooldown_is_zero(self):
        now = timezone.now()
        character = Character(exploration_cooldown_until=now)
        with patch("apps.accounts.models.timezone.now", return_value=now):
            self.assertEqual(character.get_exploration_cooldown_remaining(), 0)
