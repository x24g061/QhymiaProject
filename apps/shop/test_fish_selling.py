from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Character
from apps.inventory.models import Item, InventoryItem


class FishSellingTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            user_id="fish_sell_test",
            email="fish_sell_test@example.com",
            password="test_password_123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="魚売却テスト",
            gold=100,
        )

        self.fish = Item.objects.get(name="コモンの魚")

        self.inventory = InventoryItem.objects.create(
            character=self.character,
            item=self.fish,
            quantity=3,
        )

        self.client.force_login(self.user)

    def sell(self, quantity):
        return self.client.post(
            reverse("shop:sell_fish", args=[self.inventory.pk]),
            {"quantity": quantity},
        )

    def test_sell_one_fish(self):
        response = self.sell(1)

        self.assertEqual(response.status_code, 302)

        self.character.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(self.character.gold, 102)
        self.assertEqual(self.inventory.quantity, 2)

    def test_sell_all_fish(self):
        self.sell(3)

        self.character.refresh_from_db()

        self.assertEqual(self.character.gold, 106)
        self.assertFalse(
            InventoryItem.objects.filter(pk=self.inventory.pk).exists()
        )

    def test_cannot_sell_more_than_owned(self):
        self.sell(4)

        self.character.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(self.character.gold, 100)
        self.assertEqual(self.inventory.quantity, 3)

    def test_cannot_sell_zero_fish(self):
        self.sell(0)

        self.character.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(self.character.gold, 100)
        self.assertEqual(self.inventory.quantity, 3)

    def test_cannot_sell_other_players_fish(self):
        User = get_user_model()

        other_user = User.objects.create_user(
            user_id="other_fish_test",
            email="other_fish_test@example.com",
            password="test_password_123",
        )
        other_character = Character.objects.create(
            user=other_user,
            name="別プレイヤー",
        )
        other_inventory = InventoryItem.objects.create(
            character=other_character,
            item=self.fish,
            quantity=2,
        )

        response = self.client.post(
            reverse("shop:sell_fish", args=[other_inventory.pk]),
            {"quantity": 1},
        )

        self.assertEqual(response.status_code, 302)

        other_inventory.refresh_from_db()
        self.character.refresh_from_db()

        self.assertEqual(other_inventory.quantity, 2)
        self.assertEqual(self.character.gold, 100)

    def test_cannot_sell_non_fish_item(self):
        other_item = Item.objects.create(
            name="売却禁止テストアイテム",
            category=Item.Category.SYSTEM,
        )

        other_inventory = InventoryItem.objects.create(
            character=self.character,
            item=other_item,
            quantity=1,
        )

        self.client.post(
            reverse("shop:sell_fish", args=[other_inventory.pk]),
            {"quantity": 1},
        )

        self.assertTrue(
            InventoryItem.objects.filter(pk=other_inventory.pk).exists()
        )
        self.character.refresh_from_db()
        self.assertEqual(self.character.gold, 100)
