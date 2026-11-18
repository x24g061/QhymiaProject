
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Character
from apps.inventory.models import Item, Equipment, OwnedEquipment
from apps.inventory.services import synthesize_equipments
from apps.shop.models import MarketListing


User = get_user_model()


class SynthesisMarketHistoryTests(TestCase):

    def setUp(self):
        self.user = User.objects.create(
            user_id="synthesis_test",
        )
        self.character = Character.objects.create(
            user=self.user,
            name="合成履歴テスト",
        )

        self.item = Item.objects.create(
            name="合成テスト用の剣",
            category=Item.Category.EQUIPMENT,
        )

        self.equipment = Equipment.objects.create(
            item=self.item,
            rank=Equipment.Rank.F,
            slot=Equipment.Slot.WEAPON,
            style=Equipment.Style.PHYSICAL,
            base_battle_power=11,
        )

        self.materials = [
            OwnedEquipment.objects.create(
                character=self.character,
                equipment=self.equipment,
                enhancement_level=0,
                battle_power=11,
            )
            for _ in range(3)
        ]

    def create_listing(self, status):
        return MarketListing.objects.create(
            seller=self.character,
            item=self.item,
            owned_equipment=self.materials[0],
            quantity=1,
            unit_price=100,
            status=status,
        )

    @patch(
        "apps.inventory.services.determine_synthesis_result",
        return_value="success",
    )
    def test_cancelled_equipment_can_be_synthesized(
        self, mock_result
    ):
        """キャンセル済み装備を合成できる"""

        listing = self.create_listing(
            MarketListing.Status.CANCELLED
        )

        result = synthesize_equipments(
            self.character,
            self.materials,
        )

        self.assertEqual(result["result"], "success")
        self.assertEqual(
            result["equipment"].enhancement_level,
            1,
        )

        # 素材3個は消費される
        for material in self.materials:
            self.assertFalse(
                OwnedEquipment.objects.filter(
                    pk=material.pk
                ).exists()
            )

        # 新しい装備は1個
        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character
            ).count(),
            1,
        )

        # 出品履歴は削除されない
        listing.refresh_from_db()
        self.assertEqual(
            listing.status,
            MarketListing.Status.CANCELLED,
        )
        self.assertIsNone(listing.owned_equipment_id)
        self.assertEqual(listing.item_id, self.item.id)
        self.assertEqual(listing.unit_price, 100)

    def test_listed_equipment_cannot_be_synthesized(self):
        """出品中の装備は合成できず、素材も消えない"""

        listing = self.create_listing(
            MarketListing.Status.LISTED
        )

        with self.assertRaisesMessage(
            ValueError,
            "フリーマーケットに出品中の装備は合成できません。",
        ):
            synthesize_equipments(
                self.character,
                self.materials,
            )

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character
            ).count(),
            3,
        )

        listing.refresh_from_db()
        self.assertEqual(
            listing.status,
            MarketListing.Status.LISTED,
        )
        self.assertEqual(
            listing.owned_equipment_id,
            self.materials[0].id,
        )

    @patch(
        "apps.inventory.services.determine_synthesis_result",
        return_value="failure",
    )
    def test_cancelled_history_survives_failed_synthesis(
        self, mock_result
    ):
        """合成失敗でも履歴が残り、素材が消費される"""

        listing = self.create_listing(
            MarketListing.Status.CANCELLED
        )

        result = synthesize_equipments(
            self.character,
            self.materials,
        )

        self.assertEqual(result["result"], "failure")
        self.assertIsNone(result["equipment"])

        self.assertEqual(
            OwnedEquipment.objects.filter(
                character=self.character
            ).count(),
            0,
        )

        listing.refresh_from_db()
        self.assertIsNone(listing.owned_equipment_id)
        self.assertEqual(
            listing.status,
            MarketListing.Status.CANCELLED,
        )

    def test_cancelled_equipment_appears_on_synthesis_page(self):
        """キャンセル済み装備が合成画面に表示される"""

        self.create_listing(
            MarketListing.Status.CANCELLED
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("inventory:synthesis")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "合成テスト用の剣",
        )

        self.assertEqual(
            len(response.context["synthesis_groups"]),
            1,
        )
