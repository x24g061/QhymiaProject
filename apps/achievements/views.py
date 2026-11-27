from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import Character

from .models import (
    Achievement,
    CharacterAchievement,
    CharacterTitle,
)

from .services import (
    unlock_achievements,
    get_achievement_progress,
    get_progress_value,
    equip_title,
    unequip_title,
)


@login_required
@require_GET
def achievement_list(request):

    character = Character.objects.filter(
        user=request.user,
    ).first()

    if character is None:
        return redirect("home")

    # 既存の達成条件から実績を獲得
    newly_unlocked = unlock_achievements(character)

    if newly_unlocked:
        messages.success(
            request,
            f"新しい実績を{len(newly_unlocked)}種類獲得しました！",
        )

    progress = get_achievement_progress(character)

    unlocked_records = {
        record.achievement_id: record
        for record in CharacterAchievement.objects.filter(
            character=character,
        )
    }

    equipped = (
        CharacterTitle.objects
        .filter(
            character=character,
            achievement__is_active=True,
            achievement_id__in=unlocked_records.keys(),
        )
        .select_related("achievement")
        .first()
    )

    equipped_id = (
        equipped.achievement_id
        if equipped else None
    )

    achievements = list(
        Achievement.objects.filter(is_active=True)
    )

    rows = []

    for achievement in achievements:

        record = unlocked_records.get(achievement.pk)

        if achievement.is_hidden and record is None:
            continue

        current = get_progress_value(
            achievement,
            progress,
        )

        target = achievement.target_value

        if record is not None:
            current = target

        percent = (
            min(100, int(current * 100 / target))
            if target > 0 else 100
        )

        rows.append({
            "achievement": achievement,
            "unlocked": record is not None,
            "unlocked_at": (
                record.unlocked_at if record else None
            ),
            "equipped": achievement.pk == equipped_id,
            "current": min(current, target),
            "target": target,
            "percent": percent,
        })

    total = len(achievements)

    unlocked_count = sum(
        achievement.pk in unlocked_records
        for achievement in achievements
    )

    completion = (
        round(unlocked_count / total * 100, 1)
        if total else 0
    )

    return render(
        request,
        "achievements.html",
        {
            "character": character,
            "achievement_rows": rows,
            "equipped_title": equipped,
            "total": total,
            "unlocked_count": unlocked_count,
            "completion": completion,
        },
    )


@login_required
@require_POST
def change_title(request):

    character = Character.objects.filter(
        user=request.user,
    ).first()

    if character is None:
        return redirect("home")

    action = request.POST.get("action")

    if action == "unequip":
        unequip_title(character)
        messages.success(request, "称号を解除しました。")

    elif action == "equip":

        try:
            achievement_id = int(
                request.POST.get("achievement_id", "")
            )

            if not 0 < achievement_id < 2**63:
                raise ValueError("称号の指定が不正です。")

            title = equip_title(
                character,
                achievement_id,
            )

            messages.success(
                request,
                f"称号「{title.achievement.title_name}」を装着しました。",
            )

        except (ValueError, TypeError):
            messages.error(
                request,
                "指定された称号は装着できません。",
            )

    else:
        messages.error(request, "無効な操作です。")

    return redirect("achievements:list")
