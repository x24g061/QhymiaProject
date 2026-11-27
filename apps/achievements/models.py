from django.db import models


# ========================================
# 実績・称号マスター
# ========================================

class Achievement(models.Model):

    class Category(models.TextChoices):
        GROWTH = "growth", "回帰・成長"
        EXPLORATION = "exploration", "探索・戦闘"
        ARENA = "arena", "闘技場"
        EQUIPMENT = "equipment", "装備・合成"
        FISHING = "fishing", "釣り"
        ECONOMY = "economy", "経済"
        OTHER = "other", "その他"

    class Rank(models.TextChoices):
        F = "F", "F"
        E = "E", "E"
        D = "D", "D"
        C = "C", "C"
        B = "B", "B"
        A = "A", "A"
        S = "S", "S"

    class Condition(models.TextChoices):
        LEVEL = "level", "レベル"
        REINCARNATION = "reincarnation", "回帰回数"
        EXPLORATION_COUNT = "exploration_count", "探索回数"
        BOSS_DEFEATED = "boss_defeated", "ボス討伐"
        ARENA_WINS = "arena_wins", "闘技場勝利数"
        ARENA_WIN_STREAK = "arena_win_streak", "闘技場連勝数"
        SYNTHESIS_COUNT = "synthesis_count", "合成回数"
        SYNTHESIS_SUCCESS = "synthesis_success", "合成成功数"
        SYNTHESIS_SUPER = "synthesis_super", "超大成功回数"
        ENHANCEMENT_LEVEL = "enhancement_level", "装備強化値"
        FISHING_COUNT = "fishing_count", "釣り回数"
        GOLD = "gold", "所持Q"

    code = models.SlugField(
        max_length=80,
        unique=True,
    )

    name = models.CharField(
        max_length=80,
        verbose_name="実績名",
    )

    title_name = models.CharField(
        max_length=80,
        verbose_name="称号名",
    )

    description = models.CharField(
        max_length=300,
        verbose_name="獲得条件の説明",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )

    rank = models.CharField(
        max_length=1,
        choices=Rank.choices,
        default=Rank.F,
    )

    condition_type = models.CharField(
        max_length=40,
        choices=Condition.choices,
    )

    target_value = models.PositiveBigIntegerField(
        default=1,
    )

    is_hidden = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "実績"
        verbose_name_plural = "実績マスター"

    def __str__(self):
        return f"[{self.rank}] {self.title_name}"


# ========================================
# キャラクターの獲得済み実績
# ========================================

class CharacterAchievement(models.Model):

    character = models.ForeignKey(
        "accounts.Character",
        on_delete=models.CASCADE,
        related_name="unlocked_achievements",
    )

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.PROTECT,
        related_name="unlocked_characters",
    )

    unlocked_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-unlocked_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["character", "achievement"],
                name="unique_character_achievement",
            ),
        ]

        verbose_name = "獲得済み実績"
        verbose_name_plural = "獲得済み実績"

    def __str__(self):
        return (
            f"{self.character.name}："
            f"{self.achievement.title_name}"
        )


# ========================================
# 累計プレイ記録
# ========================================

class AchievementStats(models.Model):

    character = models.OneToOneField(
        "accounts.Character",
        on_delete=models.CASCADE,
        related_name="achievement_stats",
    )

    exploration_initialized = models.BooleanField(default=False)

    exploration_count = models.PositiveBigIntegerField(
        default=0,
    )

    arena_wins = models.PositiveBigIntegerField(
        default=0,
    )

    max_arena_win_streak = models.PositiveIntegerField(
        default=0,
    )

    synthesis_count = models.PositiveBigIntegerField(
        default=0,
    )

    synthesis_success_count = models.PositiveBigIntegerField(
        default=0,
    )

    synthesis_super_count = models.PositiveBigIntegerField(
        default=0,
    )

    fishing_count = models.PositiveBigIntegerField(
        default=0,
    )

    max_enhancement_level = models.PositiveIntegerField(
        default=0,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "累計プレイ記録"
        verbose_name_plural = "累計プレイ記録"

    def __str__(self):
        return f"{self.character.name}のプレイ記録"


# ========================================
# 装着中の称号
# ========================================

class CharacterTitle(models.Model):

    character = models.OneToOneField(
        "accounts.Character",
        on_delete=models.CASCADE,
        related_name="equipped_title",
    )

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipped_characters",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "装着中の称号"
        verbose_name_plural = "装着中の称号"

    def __str__(self):
        title = (
            self.achievement.title_name
            if self.achievement
            else "称号なし"
        )

        return f"{self.character.name}：{title}"
