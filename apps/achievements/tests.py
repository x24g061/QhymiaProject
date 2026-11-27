from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from apps.accounts.models import Character
from apps.battle.models import FloorProgress

from .models import (
    Achievement,
    AchievementStats,
    CharacterAchievement,
    CharacterTitle,
)

from .services import (
    unlock_achievements,
    get_achievement_progress,
    equip_title,
    unequip_title,
    record_exploration,
    record_synthesis,
    record_fishing,
    get_public_title,
    get_public_title_data,
    preload_public_titles,
)


class AchievementTests(TestCase):

    @classmethod
    def setUpTestData(cls):

        cls.user = get_user_model().objects.create_user(
            user_id="achievement_test",
            email="achievement@example.com",
            password="testpass123",
        )

        cls.character = Character.objects.create(
            user=cls.user,
            name="実績テスト",
        )

        cls.other_user = get_user_model().objects.create_user(
            user_id="achievement_other",
            email="achievement-other@example.com",
            password="testpass123",
        )

        cls.other_character = Character.objects.create(
            user=cls.other_user,
            name="他人の実績テスト",
        )

    def get_achievement(self, code):
        return Achievement.objects.get(code=code)

    def has_achievement(self, code):
        return CharacterAchievement.objects.filter(
            character=self.character,
            achievement__code=code,
        ).exists()

    def unlock_level_100(self):
        self.character.level = 100
        self.character.save(update_fields=["level"])
        unlock_achievements(self.character)
        return self.get_achievement("level_100")

    def get_stats(self):
        return AchievementStats.objects.get(
            character=self.character,
        )

    # 01: 実績マスター
    def test_achievement_master_count(self):
        self.assertEqual(
            Achievement.objects.count(),
            47,
        )

    # 02: 条件達成
    def test_unlock_level_100(self):
        self.unlock_level_100()
        self.assertTrue(
            self.has_achievement("level_100")
        )

    # 03: 条件未達成
    def test_cannot_unlock_before_target(self):
        self.character.level = 99
        self.character.save(update_fields=["level"])

        unlock_achievements(self.character)

        self.assertFalse(
            self.has_achievement("level_100")
        )

    # 04: 二重獲得防止
    def test_no_duplicate_unlock(self):
        achievement = self.unlock_level_100()

        newly_unlocked = unlock_achievements(
            self.character
        )

        self.assertEqual(newly_unlocked, [])

        self.assertEqual(
            CharacterAchievement.objects.filter(
                character=self.character,
                achievement=achievement,
            ).count(),
            1,
        )

    # 05: 称号装着
    def test_equip_unlocked_title(self):
        achievement = self.unlock_level_100()

        equip_title(
            self.character,
            achievement.pk,
        )

        title = CharacterTitle.objects.get(
            character=self.character,
        )

        self.assertEqual(
            title.achievement_id,
            achievement.pk,
        )

    # 06: 未獲得称号の装着防止
    def test_cannot_equip_locked_title(self):
        achievement = self.get_achievement("level_100")

        with self.assertRaises(ValueError):
            equip_title(
                self.character,
                achievement.pk,
            )

    # 07: 称号解除
    def test_unequip_title(self):
        achievement = self.unlock_level_100()

        equip_title(
            self.character,
            achievement.pk,
        )

        unequip_title(self.character)

        self.assertIsNone(
            get_public_title(self.character)
        )

    # 08: 探索回数
    def test_exploration_count(self):
        for _ in range(3):
            record_exploration(self.character)

        unlock_achievements(self.character)

        self.assertEqual(
            self.get_stats().exploration_count,
            3,
        )

        self.assertTrue(
            self.has_achievement("explore_1")
        )

    # 09: 既存探索回数の引き継ぎ
    def test_existing_exploration_count(self):
        FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=50,
        )

        record_exploration(self.character)

        self.assertEqual(
            self.get_stats().exploration_count,
            51,
        )

    # 10: ボス戦後の探索回数保持
    def test_exploration_count_survives_reset(self):
        progress = FloorProgress.objects.create(
            character=self.character,
            floor=1,
            exploration_count=99,
        )

        record_exploration(self.character)

        progress.exploration_count = 0
        progress.save(update_fields=["exploration_count"])

        unlock_achievements(self.character)

        self.assertEqual(
            self.get_stats().exploration_count,
            100,
        )

        self.assertTrue(
            self.has_achievement("explore_100")
        )

    # 11: 回帰後の実績保持
    def test_achievement_survives_reincarnation(self):
        achievement = self.unlock_level_100()

        equip_title(
            self.character,
            achievement.pk,
        )

        self.character.level = 1
        self.character.reincarnation_count = 1

        self.character.save(update_fields=[
            "level",
            "reincarnation_count",
        ])

        unlock_achievements(self.character)

        self.assertTrue(
            self.has_achievement("level_100")
        )

        self.assertTrue(
            self.has_achievement("reincarnation_1")
        )

        self.assertEqual(
            get_public_title(self.character).achievement_id,
            achievement.pk,
        )

    # 12: 合成成功
    def test_synthesis_success(self):
        record_synthesis(
            self.character,
            "success",
            1,
        )

        stats = self.get_stats()

        self.assertEqual(stats.synthesis_count, 1)
        self.assertEqual(stats.synthesis_success_count, 1)
        self.assertEqual(stats.synthesis_super_count, 0)

    # 13: 合成失敗
    def test_synthesis_failure(self):
        record_synthesis(
            self.character,
            "failure",
        )

        stats = self.get_stats()

        self.assertEqual(stats.synthesis_count, 1)
        self.assertEqual(stats.synthesis_success_count, 0)
        self.assertEqual(stats.synthesis_super_count, 0)

    # 14: 超大成功
    def test_synthesis_super_success(self):
        record_synthesis(
            self.character,
            "super_success",
            3,
        )

        stats = self.get_stats()

        self.assertEqual(stats.synthesis_count, 1)
        self.assertEqual(stats.synthesis_success_count, 1)
        self.assertEqual(stats.synthesis_super_count, 1)

        self.assertTrue(
            self.has_achievement("synthesis_super_1")
        )

    # 15: 最大強化値の保持
    def test_max_enhancement_is_preserved(self):
        record_synthesis(
            self.character,
            "success",
            10,
        )

        record_synthesis(
            self.character,
            "success",
            1,
        )

        self.assertEqual(
            self.get_stats().max_enhancement_level,
            10,
        )

        self.assertTrue(
            self.has_achievement("equipment_10")
        )

    # 16: 釣り実績
    def test_fishing_count(self):
        record_fishing(self.character)
        record_fishing(self.character)

        self.assertEqual(
            self.get_stats().fishing_count,
            2,
        )

        self.assertTrue(
            self.has_achievement("fishing_1")
        )

    # 17: ロールバック
    def test_achievement_rollback(self):
        with self.assertRaises(RuntimeError):

            with transaction.atomic():

                record_fishing(self.character)

                raise RuntimeError("強制ロールバック")

        self.assertFalse(
            self.has_achievement("fishing_1")
        )

        self.assertFalse(
            AchievementStats.objects.filter(
                character=self.character,
                fishing_count__gt=0,
            ).exists()
        )

    # 18: 称号一括取得
    def test_preload_public_titles(self):
        achievement = self.unlock_level_100()

        equip_title(
            self.character,
            achievement.pk,
        )

        characters = [
            self.character,
            self.other_character,
        ]

        with self.assertNumQueries(1):

            preload_public_titles(characters)

            first = get_public_title_data(
                self.character
            )

            second = get_public_title_data(
                self.other_character
            )

        self.assertEqual(
            first["title_name"],
            achievement.title_name,
        )

        self.assertEqual(second["title_name"], "")

    # 19: 無効な称号の非公開
    def test_inactive_title_is_not_public(self):
        achievement = self.unlock_level_100()

        equip_title(
            self.character,
            achievement.pk,
        )

        achievement.is_active = False
        achievement.save(update_fields=["is_active"])

        self.assertIsNone(
            get_public_title(self.character)
        )

    # 20: 他人の獲得実績による称号装着防止
    def test_cannot_use_other_characters_title(self):
        achievement = self.unlock_level_100()

        with self.assertRaises(ValueError):
            equip_title(
                self.other_character,
                achievement.pk,
            )
