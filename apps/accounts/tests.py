from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Character

from unittest.mock import patch

from .growth import increase_attribute_growth_weight

User = get_user_model()


class CharacterModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id="test_user",
            email="test_user@example.com",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="テストキャラ",
        )

    def test_character_can_be_created(self):
        self.assertEqual(self.character.user, self.user)
        self.assertEqual(self.character.name, "テストキャラ")

    def test_default_growth_values(self):
        self.assertEqual(self.character.level, 1)
        self.assertEqual(self.character.exp, 0)
        self.assertEqual(self.character.reincarnation_count, 0)

    def test_default_hp_and_mp(self):
        self.assertEqual(self.character.max_hp, 30)
        self.assertEqual(self.character.current_hp, 30)
        self.assertEqual(self.character.max_mp, 10)
        self.assertEqual(self.character.current_mp, 10)

    def test_default_basic_stats(self):
        self.assertEqual(self.character.strength, 5)
        self.assertEqual(self.character.intelligence, 5)
        self.assertEqual(self.character.dexterity, 5)
        self.assertEqual(self.character.agility, 5)
        self.assertEqual(self.character.vitality, 5)
        self.assertEqual(self.character.luck, 5)

    def test_default_attribute_values(self):
        self.assertEqual(self.character.fire, 0)
        self.assertEqual(self.character.water, 0)
        self.assertEqual(self.character.grass, 0)
        self.assertEqual(self.character.rock, 0)
        self.assertEqual(self.character.light, 0)
        self.assertEqual(self.character.dark, 0)

    def test_default_possession_and_stamina(self):
        self.assertEqual(self.character.gold, 0)
        self.assertEqual(self.character.max_stamina, 100)
        self.assertEqual(self.character.current_stamina, 100)

    def test_character_string_is_name(self):
        self.assertEqual(str(self.character), "テストキャラ")

    def test_user_cannot_have_multiple_characters(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Character.objects.create(
                    user=self.user,
                    name="2人目のキャラ",
                )

    def test_character_name_must_be_unique(self):
        another_user = User.objects.create(
            user_id="another_user",
            email="another_user@example.com",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Character.objects.create(
                    user=another_user,
                    name="テストキャラ",
                )

    def test_character_is_deleted_with_user(self):
        character_id = self.character.id

        self.user.delete()

        self.assertFalse(
            Character.objects.filter(id=character_id).exists()
        )


class UserManagerTests(TestCase):
    def test_create_user_with_user_id(self):
        user = User.objects.create_user(
            user_id="normal_user",
            password="test-password-123",
        )

        self.assertEqual(user.user_id, "normal_user")
        self.assertTrue(user.check_password("test-password-123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser_with_user_id(self):
        user = User.objects.create_superuser(
            user_id="admin_user",
            password="admin-password-123",
        )

        self.assertEqual(user.user_id, "admin_user")
        self.assertTrue(user.check_password("admin-password-123"))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_user_id_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                user_id="",
                password="test-password-123",
            )
            
class AttributeGrowthWeightTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id="growth_test_user",
            email="growth_test@example.com",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="属性成長テスト",
        )

    def test_only_target_increases_when_no_decrease_candidate(self):
        """
        他属性がすべて1の場合、
        対象属性だけ+1される。
        """

        result = increase_attribute_growth_weight(
            self.character,
            "fire",
        )

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.fire_growth_weight,
            2,
        )

        self.assertEqual(
            self.character.water_growth_weight,
            1,
        )

        self.assertIsNone(
            result["decreased"]
        )

    def test_other_attribute_decreases_by_one(self):
        """
        下げられる属性がある場合、
        対象属性+1、
        他属性1つ-1。
        """

        self.character.water_growth_weight = 3
        self.character.save(
            update_fields=[
                "water_growth_weight",
            ]
        )

        with patch(
            "apps.accounts.growth.random.choice",
            return_value="water",
        ):
            result = increase_attribute_growth_weight(
                self.character,
                "fire",
            )

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.fire_growth_weight,
            2,
        )

        self.assertEqual(
            self.character.water_growth_weight,
            2,
        )

        self.assertEqual(
            result["decreased"],
            "water",
        )

    def test_growth_weight_never_goes_below_one(self):
        """
        下限1の属性は減少候補にならない。
        """

        self.character.water_growth_weight = 1
        self.character.grass_growth_weight = 2

        self.character.save(
            update_fields=[
                "water_growth_weight",
                "grass_growth_weight",
            ]
        )

        with patch(
            "apps.accounts.growth.random.choice",
            return_value="grass",
        ):
            increase_attribute_growth_weight(
                self.character,
                "fire",
            )

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.water_growth_weight,
            1,
        )

        self.assertEqual(
            self.character.grass_growth_weight,
            1,
        )

    def test_cannot_increase_over_fifteen(self):
        """
        対象属性が15なら使用不可。
        """

        self.character.fire_growth_weight = 15
        self.character.save(
            update_fields=[
                "fire_growth_weight",
            ]
        )

        with self.assertRaises(ValueError):
            increase_attribute_growth_weight(
                self.character,
                "fire",
            )