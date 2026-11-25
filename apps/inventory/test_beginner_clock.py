from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, Character
from apps.inventory.models import Item, InventoryItem
from apps.inventory.boosts import get_active_boosts


class BeginnerClockTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="beginner-clock-test",
            email="beginner-clock@example.invalid",
            password="testpass123",
            date_joined=timezone.now() - timedelta(days=7),
        )

        self.character = Character.objects.create(
            user=self.user,
            name="時計テスト",
        )

        self.item = Item.objects.create(
            name="テスト用CT短縮時計",
            category="consumable",
            is_usable=True,
            cooldown_reduction_days=1,
        )

        self.inventory = InventoryItem.objects.create(
            character=self.character,
            item=self.item,
            quantity=2,
        )

        self.client.force_login(self.user)

    def set_beginner(self):
        self.user.date_joined = (
            timezone.now() - timedelta(hours=1)
        )
        self.user.save(update_fields=["date_joined"])

    def set_cooldown(self, seconds):
        deadline = timezone.now() + timedelta(seconds=seconds)

        self.character.exploration_cooldown_until = deadline
        self.character.save(
            update_fields=["exploration_cooldown_until"]
        )

        return deadline

    def use_clock(self):
        response = self.client.post(
            reverse(
                "inventory:use_item",
                args=[self.inventory.pk],
            )
        )

        self.assertEqual(response.status_code, 302)
        self.character.refresh_from_db()

        return response

    def test_normal_user_first_clock(self):
        deadline = self.set_cooldown(40)

        self.use_clock()

        self.assertEqual(
            self.character.get_exploration_cooldown_seconds(),
            20,
        )

        self.assertEqual(
            self.character.exploration_cooldown_until,
            deadline - timedelta(seconds=20),
        )

    def test_beginner_first_clock(self):
        self.set_beginner()
        deadline = self.set_cooldown(20)

        self.use_clock()

        self.assertEqual(
            self.character.get_exploration_cooldown_seconds(),
            10,
        )

        self.assertEqual(
            self.character.exploration_cooldown_until,
            deadline - timedelta(seconds=10),
        )

    def test_normal_clock_extension(self):
        self.use_clock()
        expires = self.character.exploration_cooldown_reduced_until
        deadline = self.set_cooldown(20)

        self.use_clock()

        self.assertEqual(
            self.character.exploration_cooldown_reduced_until,
            expires + timedelta(days=1),
        )

        self.assertEqual(
            self.character.exploration_cooldown_until,
            deadline,
        )

    def test_beginner_clock_extension(self):
        self.set_beginner()
        self.use_clock()

        expires = self.character.exploration_cooldown_reduced_until
        deadline = self.set_cooldown(10)

        self.use_clock()

        self.assertEqual(
            self.character.exploration_cooldown_reduced_until,
            expires + timedelta(days=1),
        )

        self.assertEqual(
            self.character.exploration_cooldown_until,
            deadline,
        )

    def test_short_remaining_cooldown(self):
        self.set_beginner()
        self.set_cooldown(5)

        self.use_clock()

        self.assertLessEqual(
            self.character.exploration_cooldown_until,
            timezone.now(),
        )

    def test_clock_consumes_one_item(self):
        self.use_clock()
        self.inventory.refresh_from_db()

        self.assertEqual(self.inventory.quantity, 1)

    def test_last_clock_is_deleted(self):
        self.use_clock()
        self.use_clock()

        self.assertFalse(
            InventoryItem.objects.filter(
                pk=self.inventory.pk
            ).exists()
        )

    def test_beginner_expiration_with_clock(self):
        self.set_beginner()
        self.use_clock()

        self.user.date_joined = (
            timezone.now() - timedelta(hours=73)
        )
        self.user.save(update_fields=["date_joined"])

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.get_exploration_cooldown_seconds(),
            20,
        )

    def test_both_buffs_expired(self):
        self.character.exploration_cooldown_reduced_until = (
            timezone.now() - timedelta(seconds=1)
        )
        self.character.save(
            update_fields=[
                "exploration_cooldown_reduced_until"
            ]
        )

        self.assertEqual(
            self.character.get_exploration_cooldown_seconds(),
            40,
        )

    def test_combined_boost_description(self):
        self.set_beginner()
        self.use_clock()

        boosts = get_active_boosts(self.character)

        clock = next(
            boost for boost in boosts
            if boost["key"] == "exploration_cooldown_reduction"
        )

        self.assertEqual(
            clock["description"],
            "探索クールタイムが10秒になります。",
        )
