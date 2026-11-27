from django.db import transaction
from django.db.models import Max, Sum, Q

from apps.accounts.models import Character
from apps.battle.models import (
    FloorProgress,
    ArenaBattleHistory,
)
from apps.inventory.models import OwnedEquipment

from .models import (
    Achievement,
    CharacterAchievement,
    AchievementStats,
    CharacterTitle,
)


# ========================================
# 実績の進捗状況を取得
# ========================================

def initialize_exploration_count(character, stats):

    if not stats.exploration_initialized:

        current_count = (
            FloorProgress.objects
            .filter(character=character)
            .aggregate(total=Sum("exploration_count"))
            ["total"] or 0
        )

        stats.exploration_count = max(
            current_count,
            stats.exploration_count,
        )

        stats.exploration_initialized = True

        stats.save(update_fields=[
            "exploration_count",
            "exploration_initialized",
        ])

    return stats.exploration_count


@transaction.atomic
def record_exploration(character):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )

    stats, _ = AchievementStats.objects.get_or_create(
        character=character,
    )

    initialize_exploration_count(character, stats)

    stats.exploration_count += 1

    stats.save(update_fields=[
        "exploration_count",
    ])


@transaction.atomic
def get_achievement_progress(character):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )


    stats, _ = AchievementStats.objects.get_or_create(
        character=character,
    )

    # 実績専用の累計探索回数
    exploration_count = initialize_exploration_count(
        character,
        stats,
    )

    # 討伐済みボス
    defeated_bosses = set(
        FloorProgress.objects.filter(
            character=character,
            boss_defeated=True,
        ).values_list("floor", flat=True)
    )

    # 闘技場勝利数
    # 挑戦者としての勝利と防衛側としての勝利
    arena_wins = ArenaBattleHistory.objects.filter(
        Q(
            challenger=character,
            result=ArenaBattleHistory.Result.WIN,
        )
        |
        Q(
            defender=character,
            result=ArenaBattleHistory.Result.LOSS,
        )
    ).count()

    # 所持装備の最高強化値
    max_enhancement = (
        OwnedEquipment.objects
        .filter(character=character)
        .aggregate(value=Max("enhancement_level"))
        ["value"] or 0
    )

    # 回帰済みなら過去にLv.100に到達したと判定
    highest_level = (
        100
        if character.reincarnation_count > 0
        else character.level
    )

    return {
        "level": highest_level,
        "reincarnation": character.reincarnation_count,

        "exploration_count": exploration_count,

        "defeated_bosses": defeated_bosses,

        "arena_wins": max(
            arena_wins,
            stats.arena_wins,
        ),

        "arena_win_streak": max(
            character.arena_win_streak,
            stats.max_arena_win_streak,
        ),

        "enhancement_level": max(
            max_enhancement,
            stats.max_enhancement_level,
        ),

        "synthesis_count": stats.synthesis_count,
        "synthesis_success": stats.synthesis_success_count,
        "synthesis_super": stats.synthesis_super_count,
        "fishing_count": stats.fishing_count,
        "gold": character.gold,
    }


# ========================================
# 個別実績の進捗値
# ========================================

def get_progress_value(achievement, progress):

    if achievement.condition_type == "boss_defeated":
        return (
            achievement.target_value
            if achievement.target_value
            in progress["defeated_bosses"]
            else 0
        )

    return progress.get(
        achievement.condition_type,
        0,
    )


# ========================================
# 実績の自動解除
# ========================================

@transaction.atomic
def unlock_achievements(character):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )

    progress = get_achievement_progress(character)

    achievements = Achievement.objects.filter(
        is_active=True,
    )

    unlocked_ids = set(
        CharacterAchievement.objects.filter(
            character=character,
        ).values_list("achievement_id", flat=True)
    )

    newly_unlocked = []

    for achievement in achievements:

        if achievement.pk in unlocked_ids:
            continue

        current_value = get_progress_value(
            achievement,
            progress,
        )

        if current_value < achievement.target_value:
            continue

        record, created = (
            CharacterAchievement.objects.get_or_create(
                character=character,
                achievement=achievement,
            )
        )

        if created:
            newly_unlocked.append(achievement)

    # 現在までの最高記録を保存
    AchievementStats.objects.filter(
        character=character,
    ).update(
        exploration_count=progress["exploration_count"],
        arena_wins=progress["arena_wins"],
        max_arena_win_streak=progress["arena_win_streak"],
        max_enhancement_level=progress["enhancement_level"],
    )

    return newly_unlocked


# ========================================
# 称号を装着
# ========================================

@transaction.atomic
def equip_title(character, achievement_id):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )

    unlocked = (
        CharacterAchievement.objects
        .select_related("achievement")
        .filter(
            character=character,
            achievement_id=achievement_id,
            achievement__is_active=True,
        )
        .first()
    )

    if unlocked is None:
        raise ValueError(
            "獲得していない称号は装着できません。"
        )

    title, _ = CharacterTitle.objects.update_or_create(
        character=character,
        defaults={
            "achievement": unlocked.achievement,
        },
    )

    return title


# ========================================
# 称号を解除
# ========================================

@transaction.atomic
def unequip_title(character):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )

    CharacterTitle.objects.filter(
        character=character,
    ).update(
        achievement=None,
    )


# ========================================
# 公開用の装着中称号を取得
# ========================================

def get_public_title(character):

    if character is None:
        return None

    if hasattr(character, "_preloaded_public_title"):
        return character._preloaded_public_title

    return (
        CharacterTitle.objects
        .select_related("achievement")
        .filter(
            character=character,
            achievement__is_active=True,
            achievement__unlocked_characters__character=character,
        )
        .first()
    )


def get_public_title_data(character):

    title = get_public_title(character)

    if title is None:
        return {
            "title_name": "",
            "title_rank": "",
        }

    return {
        "title_name": title.achievement.title_name,
        "title_rank": title.achievement.rank,
    }


# ========================================
# 実績の獲得と通知
# ========================================

def unlock_and_notify(request, character):

    from django.contrib import messages

    newly_unlocked = unlock_achievements(character)

    if newly_unlocked:

        def notify():
            for achievement in newly_unlocked:
                messages.success(
                    request,
                    f"🏆 実績獲得！ "
                    f"【{achievement.rank}】"
                    f"{achievement.title_name}",
                )

        transaction.on_commit(notify)

    return newly_unlocked


# ========================================
# 合成実績の記録
# ========================================

@transaction.atomic
def record_synthesis(character, result, new_level=None):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )

    stats, _ = AchievementStats.objects.get_or_create(
        character=character,
    )

    stats.synthesis_count += 1

    if result in {
        "success",
        "great_success",
        "super_success",
    }:
        stats.synthesis_success_count += 1

    if result == "super_success":
        stats.synthesis_super_count += 1

    if new_level is not None:
        stats.max_enhancement_level = max(
            stats.max_enhancement_level,
            new_level,
        )

    stats.save(update_fields=[
        "synthesis_count",
        "synthesis_success_count",
        "synthesis_super_count",
        "max_enhancement_level",
        "updated_at",
    ])

    return unlock_achievements(character)


# ========================================
# 獲得済み実績の通知
# ========================================

def notify_achievements(request, achievements):

    from django.contrib import messages

    # 同じ実績の重複通知を防止
    unique_achievements = {
        achievement.pk: achievement
        for achievement in achievements
    }

    def notify():
        for achievement in unique_achievements.values():
            messages.success(
                request,
                f"🏆 実績獲得！ "
                f"【{achievement.rank}】"
                f"{achievement.title_name}",
            )

    if unique_achievements:
        transaction.on_commit(notify)


# ========================================
# 釣り実績の記録
# ========================================

@transaction.atomic
def record_fishing(character):

    character = (
        Character.objects
        .select_for_update()
        .get(pk=character.pk)
    )

    stats, _ = AchievementStats.objects.get_or_create(
        character=character,
    )

    stats.fishing_count += 1

    stats.save(update_fields=[
        "fishing_count",
        "updated_at",
    ])

    return unlock_achievements(character)


# ========================================
# 公開称号の一括取得
# ========================================

def preload_public_titles(characters):

    from django.db.models import Exists, OuterRef

    characters = [
        character
        for character in characters
        if character is not None
    ]

    character_ids = {
        character.pk
        for character in characters
    }

    if not character_ids:
        return

    unlocked = CharacterAchievement.objects.filter(
        character_id=OuterRef("character_id"),
        achievement_id=OuterRef("achievement_id"),
    )

    titles = (
        CharacterTitle.objects
        .select_related("achievement")
        .filter(
            character_id__in=character_ids,
            achievement__is_active=True,
        )
        .filter(Exists(unlocked))
    )

    title_map = {
        title.character_id: title
        for title in titles
    }

    for character in characters:
        character._preloaded_public_title = title_map.get(
            character.pk
        )
