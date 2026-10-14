from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User, Character
from apps.inventory.models import (
    Item,
    Equipment,
    OwnedEquipment,
)


class AdminEquipmentGrantTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="ADMINTEST001",
            email="admintest@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="管理テスト",
        )

        self.item = Item.objects.create(
            name="管理テスト剣",
            category=Item.Category.EQUIPMENT,
        )

        self.equipment = Equipment.objects.create(
            item=self.item,
            rank=Equipment.Rank.E,
            slot=Equipment.Slot.WEAPON,
            style=Equipment.Style.PHYSICAL,
            base_battle_power=100,
            strength_rate=100,
            intelligence_rate=0,
            dexterity_rate=0,
            agility_rate=0,
            vitality_rate=0,
            luck_rate=0,
        )

        self.client.force_login(
            self.user
        )

        session = self.client.session
        session["admin_mode"] = True
        session.save()


    def test_admin_can_grant_equipment(
        self,
    ):
        """
        管理者画面から、
        指定した装備を指定個数・指定+値で
        付与できることを確認。
        """

        response = self.client.post(
            reverse(
                "admin_player_edit",
                args=[self.character.id],
            ),
            {
                "level": self.character.level,
                "exp": self.character.exp,
                "gold": self.character.gold,
                "max_hp": self.character.max_hp,
                "max_mp": self.character.max_mp,
                "strength": self.character.strength,
                "intelligence": self.character.intelligence,
                "dexterity": self.character.dexterity,
                "agility": self.character.agility,
                "vitality": self.character.vitality,
                "luck": self.character.luck,

                "grant_equipment_id":
                    self.equipment.id,

                "grant_quantity":
                    3,

                "grant_enhancement_level":
                    2,
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        equipments = (
            OwnedEquipment.objects
            .filter(
                character=self.character,
                equipment=self.equipment,
            )
        )

        self.assertEqual(
            equipments.count(),
            3,
        )

        for owned in equipments:
            self.assertEqual(
                owned.enhancement_level,
                2,
            )

            self.assertEqual(
                owned.battle_power,
                225,
            )
    def test_admin_update_without_equipment_grant(
        self,
    ):
        """
        装備を選択していない場合は、
        プレイヤー情報だけ更新され、
        装備は付与されないことを確認。
        """

        response = self.client.post(
            reverse(
                "admin_player_edit",
                args=[self.character.id],
            ),
            {
                "level": 10,
                "exp": 50,
                "gold": 999,
                "max_hp": self.character.max_hp,
                "max_mp": self.character.max_mp,
                "strength": self.character.strength,
                "intelligence": self.character.intelligence,
                "dexterity": self.character.dexterity,
                "agility": self.character.agility,
                "vitality": self.character.vitality,
                "luck": self.character.luck,

                "grant_equipment_id": "",
                "grant_quantity": 1,
                "grant_enhancement_level": 0,
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.level,
            10,
        )

        self.assertEqual(
            self.character.exp,
            50,
        )

        self.assertEqual(
            self.character.gold,
            999,
        )

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character,
            ).count(),
            0,
        )

    def test_admin_rejects_zero_quantity(
        self,
    ):
        """
        付与個数が0の場合、
        装備を付与しないことを確認。
        """

        response = self.client.post(
            reverse(
                "admin_player_edit",
                args=[self.character.id],
            ),
            {
                "level": self.character.level,
                "exp": self.character.exp,
                "gold": self.character.gold,
                "max_hp": self.character.max_hp,
                "max_mp": self.character.max_mp,
                "strength": self.character.strength,
                "intelligence": self.character.intelligence,
                "dexterity": self.character.dexterity,
                "agility": self.character.agility,
                "vitality": self.character.vitality,
                "luck": self.character.luck,

                "grant_equipment_id":
                    self.equipment.id,

                "grant_quantity":
                    0,

                "grant_enhancement_level":
                    0,
            },
        )

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character,
            ).count(),
            0,
        )


    def test_admin_rejects_negative_enhancement_level(
        self,
    ):
        """
        +値がマイナスの場合、
        装備を付与しないことを確認。
        """

        response = self.client.post(
            reverse(
                "admin_player_edit",
                args=[self.character.id],
            ),
            {
                "level": self.character.level,
                "exp": self.character.exp,
                "gold": self.character.gold,
                "max_hp": self.character.max_hp,
                "max_mp": self.character.max_mp,
                "strength": self.character.strength,
                "intelligence": self.character.intelligence,
                "dexterity": self.character.dexterity,
                "agility": self.character.agility,
                "vitality": self.character.vitality,
                "luck": self.character.luck,

                "grant_equipment_id":
                    self.equipment.id,

                "grant_quantity":
                    1,

                "grant_enhancement_level":
                    -1,
            },
        )

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character,
            ).count(),
            0,
        )


    def test_admin_rejects_nonexistent_equipment(
        self,
    ):
        """
        存在しない装備IDの場合、
        装備を付与しないことを確認。
        """

        response = self.client.post(
            reverse(
                "admin_player_edit",
                args=[self.character.id],
            ),
            {
                "level": self.character.level,
                "exp": self.character.exp,
                "gold": self.character.gold,
                "max_hp": self.character.max_hp,
                "max_mp": self.character.max_mp,
                "strength": self.character.strength,
                "intelligence": self.character.intelligence,
                "dexterity": self.character.dexterity,
                "agility": self.character.agility,
                "vitality": self.character.vitality,
                "luck": self.character.luck,

                "grant_equipment_id":
                    999999,

                "grant_quantity":
                    1,

                "grant_enhancement_level":
                    0,
            },
        )

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character,
            ).count(),
            0,
        )