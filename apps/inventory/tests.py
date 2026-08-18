from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.models import Character

from .models import InventoryItem, Item


User = get_user_model()


class ItemModelTests(TestCase):
    def test_item_can_be_created(self):
        item = Item.objects.create(
            name="回復薬",
            description="HPを回復する薬",
            category=Item.Category.CONSUMABLE,
            buy_price=100,
            sell_price=50,
            is_usable=True,
        )

        self.assertEqual(item.name, "回復薬")
        self.assertEqual(item.category, Item.Category.CONSUMABLE)
        self.assertEqual(item.buy_price, 100)
        self.assertEqual(item.sell_price, 50)
        self.assertTrue(item.is_usable)

    def test_item_string_is_name(self):
        item = Item.objects.create(
            name="鉄鉱石",
            category=Item.Category.MATERIAL,
        )

        self.assertEqual(str(item), "鉄鉱石")

    def test_item_name_must_be_unique(self):
        Item.objects.create(
            name="回復薬",
            category=Item.Category.CONSUMABLE,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Item.objects.create(
                    name="回復薬",
                    category=Item.Category.CONSUMABLE,
                )


class InventoryItemModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(user_id="inventory_user")
        self.character = Character.objects.create(
            user=self.user,
            name="所持品テスト",
        )
        self.item = Item.objects.create(
            name="回復薬",
            category=Item.Category.CONSUMABLE,
            is_usable=True,
        )

    def test_inventory_item_can_be_created(self):
        inventory_item = InventoryItem.objects.create(
            character=self.character,
            item=self.item,
            quantity=3,
        )

        self.assertEqual(inventory_item.character, self.character)
        self.assertEqual(inventory_item.item, self.item)
        self.assertEqual(inventory_item.quantity, 3)

    def test_default_quantity_is_one(self):
        inventory_item = InventoryItem.objects.create(
            character=self.character,
            item=self.item,
        )

        self.assertEqual(inventory_item.quantity, 1)

    def test_inventory_item_string(self):
        inventory_item = InventoryItem.objects.create(
            character=self.character,
            item=self.item,
            quantity=3,
        )

        self.assertEqual(
            str(inventory_item),
            "所持品テスト - 回復薬 × 3",
        )

    def test_same_item_cannot_be_duplicated_for_character(self):
        InventoryItem.objects.create(
            character=self.character,
            item=self.item,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryItem.objects.create(
                    character=self.character,
                    item=self.item,
                )

    def test_quantity_must_be_at_least_one(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryItem.objects.create(
                    character=self.character,
                    item=self.item,
                    quantity=0,
                )

    def test_inventory_is_deleted_with_character(self):
        inventory_item = InventoryItem.objects.create(
            character=self.character,
            item=self.item,
        )
        inventory_item_id = inventory_item.id

        self.character.delete()

        self.assertFalse(
            InventoryItem.objects.filter(id=inventory_item_id).exists()
        )

    def test_owned_item_cannot_be_deleted(self):
        InventoryItem.objects.create(
            character=self.character,
            item=self.item,
        )

        with self.assertRaises(ProtectedError):
            self.item.delete()