from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Character
from apps.inventory.models import (
    Equipment,
    InventoryItem,
    Item,
    OwnedEquipment,
)
from apps.inventory.services import synthesize_equipments


class SynthesisGuaranteeTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            user_id="guarantee_test",
            password="test_password_123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="保証書テスト",
            gold=1000,
        )

        self.item = Item.objects.create(
            name="保証書テスト用武器",
            category=Item.Category.EQUIPMENT,
        )

        self.equipment = Equipment.objects.create(
            item=self.item,
            rank=Equipment.Rank.F,
            slot=Equipment.Slot.WEAPON,
            style=Equipment.Style.PHYSICAL,
            base_battle_power=11,
        )

        self.guarantee_item = Item.objects.get(
            name="合成成功保証書"
        )

    def create_materials(self):
        return [
            OwnedEquipment.objects.create(
                character=self.character,
                equipment=self.equipment,
                enhancement_level=0,
                battle_power=11,
            )
            for _ in range(3)
        ]

    @patch(
        "apps.inventory.services.determine_synthesis_result",
        return_value="failure",
    )
    def test_guarantee_forces_success(self, mock_result):
        inventory = InventoryItem.objects.create(
            character=self.character,
            item=self.guarantee_item,
            quantity=2,
        )

        result = synthesize_equipments(
            self.character,
            self.create_materials(),
            use_guarantee=True,
        )

        self.assertEqual(result["result"], "success")
        self.assertEqual(
            result["equipment"].enhancement_level,
            1,
        )

        inventory.refresh_from_db()
        self.assertEqual(inventory.quantity, 1)
        mock_result.assert_not_called()

    def test_guarantee_missing_rejects_synthesis(self):
        materials = self.create_materials()

        with self.assertRaisesMessage(
            ValueError,
            "合成成功保証書を所持していません。",
        ):
            synthesize_equipments(
                self.character,
                materials,
                use_guarantee=True,
            )

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character
            ).count(),
            3,
        )

    @patch(
        "apps.inventory.services.determine_synthesis_result",
        return_value="failure",
    )
    def test_without_guarantee_uses_normal_result(self, mock_result):
        inventory = InventoryItem.objects.create(
            character=self.character,
            item=self.guarantee_item,
            quantity=2,
        )

        result = synthesize_equipments(
            self.character,
            self.create_materials(),
            use_guarantee=False,
        )

        self.assertEqual(result["result"], "failure")

        inventory.refresh_from_db()
        self.assertEqual(inventory.quantity, 2)
        mock_result.assert_called_once()


class SynthesisReplayTests(SynthesisGuaranteeTests):

    @patch(
        "apps.inventory.services.determine_synthesis_result",
        return_value="success",
    )
    def test_same_materials_cannot_be_reused(self, mock_result):
        InventoryItem.objects.create(
            character=self.character,
            item=self.guarantee_item,
            quantity=2,
        )

        materials = self.create_materials()

        first = synthesize_equipments(
            self.character,
            materials,
            use_guarantee=True,
        )

        self.assertEqual(first["result"], "success")

        with self.assertRaisesMessage(
            ValueError,
            "選択した装備はすでに消費されたか、所持していません。",
        ):
            synthesize_equipments(
                self.character,
                materials,
                use_guarantee=True,
            )

        remaining = InventoryItem.objects.get(
            character=self.character,
            item=self.guarantee_item,
        )

        self.assertEqual(remaining.quantity, 1)
