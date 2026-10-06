from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Character

from .models import (
    InventoryItem,
    Item,
    Equipment,
    OwnedEquipment,
)

from .services import (
    equip_item,
    unequip_item,
)


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


class EquipmentModelTests(TestCase):

    def setUp(self):

        self.user = (
            User.objects.create(
                user_id="equipment_user",
            )
        )

        self.character = (
            Character.objects.create(
                user=self.user,
                name="装備テスト",
            )
        )

        self.item = Item.objects.create(
            name="鉄の剣",
            category=Item.Category.EQUIPMENT,
        )

        self.equipment = (
            Equipment.objects.create(
                item=self.item,
                rank=Equipment.Rank.E,
                slot=Equipment.Slot.WEAPON,
                style=(
                    Equipment.Style.PHYSICAL
                ),
                base_battle_power=120,

                strength_rate=60,
                intelligence_rate=0,
                dexterity_rate=20,
                agility_rate=10,
                vitality_rate=0,
                luck_rate=10,
            )
        )


    def test_equipment_stat_bonus(self):
        """
        戦闘力120の鉄の剣が
        指定した割合でステータスを
        上昇させることを確認する。
        """

        owned = (
            OwnedEquipment.objects.create(
                character=self.character,
                equipment=self.equipment,
                battle_power=120,
            )
        )

        self.assertEqual(
            owned.get_stat_bonus(
                "strength"
            ),
            36,
        )

        self.assertEqual(
            owned.get_stat_bonus(
                "intelligence"
            ),
            0,
        )

        self.assertEqual(
            owned.get_stat_bonus(
                "dexterity"
            ),
            12,
        )

        self.assertEqual(
            owned.get_stat_bonus(
                "agility"
            ),
            6,
        )

        self.assertEqual(
            owned.get_stat_bonus(
                "vitality"
            ),
            0,
        )

        self.assertEqual(
            owned.get_stat_bonus(
                "luck"
            ),
            6,
        )


    def test_equipment_has_unlimited_enhancement_level(
        self,
    ):
        """
        +値にゲーム上の上限を設けないことを確認。
        """

        owned = (
            OwnedEquipment.objects.create(
                character=self.character,
                equipment=self.equipment,
                enhancement_level=150,
                battle_power=500,
            )
        )

        self.assertEqual(
            owned.enhancement_level,
            150,
        )


    def test_only_one_equipment_per_slot(
        self,
    ):
        """
        同じ部位には
        1つしか装備できないことを確認。
        """

        sword1 = OwnedEquipment.objects.create(
            character=self.character,
            equipment=self.equipment,
            battle_power=120,
        )

        item2 = Item.objects.create(
            name="鋼の剣",
            category=Item.Category.EQUIPMENT,
        )

        equipment2 = Equipment.objects.create(
            item=item2,
            rank=Equipment.Rank.D,
            slot=Equipment.Slot.WEAPON,
            style=Equipment.Style.PHYSICAL,
            base_battle_power=150,

            strength_rate=60,
            intelligence_rate=0,
            dexterity_rate=20,
            agility_rate=10,
            vitality_rate=0,
            luck_rate=10,
        )

        sword2 = OwnedEquipment.objects.create(
            character=self.character,
            equipment=equipment2,
            battle_power=150,
        )

        equip_item(
            self.character,
            sword1,
        )

        equip_item(
            self.character,
            sword2,
        )

        sword1.refresh_from_db()
        sword2.refresh_from_db()

        self.assertFalse(
            sword1.is_equipped
        )

        self.assertTrue(
            sword2.is_equipped
        )

def test_equip_view_equips_owned_equipment(
    self,
):
    """
    倉庫画面から装備できることを確認。
    """

    owned = OwnedEquipment.objects.create(
        character=self.character,
        equipment=self.equipment,
        battle_power=120,
    )

    self.client.force_login(
        self.user
    )

    response = self.client.post(
        reverse(
            "inventory:equip_equipment",
            args=[owned.id],
        )
    )

    self.assertEqual(
        response.status_code,
        302,
    )

    owned.refresh_from_db()

    self.assertTrue(
        owned.is_equipped
    )


def test_unequip_view_removes_equipment(
    self,
):
    """
    倉庫画面から装備を外せることを確認。
    """

    owned = OwnedEquipment.objects.create(
        character=self.character,
        equipment=self.equipment,
        battle_power=120,
        is_equipped=True,
    )

    self.client.force_login(
        self.user
    )

    response = self.client.post(
        reverse(
            "inventory:unequip_equipment",
            args=[owned.id],
        )
    )

    self.assertEqual(
        response.status_code,
        302,
    )

    owned.refresh_from_db()

    self.assertFalse(
        owned.is_equipped
    )