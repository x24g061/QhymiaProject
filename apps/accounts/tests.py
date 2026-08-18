from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Character


User = get_user_model()


class CharacterModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(user_id="test_user")
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
        another_user = User.objects.create(user_id="another_user")

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