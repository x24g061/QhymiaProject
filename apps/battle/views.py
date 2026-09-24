from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from .models import Skill, SkillPreset
from django.db import transaction


@login_required
def battle(request):
    character = request.user.character
    now = timezone.now()

    # 現在クールタイム中なら探索させない
    if (
        character.exploration_cooldown_until
        and character.exploration_cooldown_until > now
    ):
        remaining = character.get_exploration_cooldown_remaining()

        messages.warning(
            request,
            f"探索クールタイム中です。あと約{remaining}秒です。"
        )

        return redirect("home")

    # 現在適用されるCT
    cooldown_seconds = (
        character.get_exploration_cooldown_seconds()
    )

    # 探索した時刻
    character.last_explored_at = now

    # CT終了時刻
    character.exploration_cooldown_until = (
        now + timedelta(seconds=cooldown_seconds)
    )

    character.save(
        update_fields=[
            "last_explored_at",
            "exploration_cooldown_until",
            "updated_at",
        ]
    )

    return render(
        request,
        "battle.html",
        {
            "character": character,
            "cooldown_seconds": cooldown_seconds,
        }
    )

@login_required
def tactics(request):
    character = request.user.character

    # 現在の職業で使用できるスキルだけ取得
    available_skills = (
        Skill.objects
        .filter(job=character.job)
        .order_by("id")
    )

    error_message = None

    if request.method == "POST":

        # 保存前に5枠すべてチェックする
        new_presets = []

        for slot in range(1, 6):

            skill_id = request.POST.get(
                f"skill_{slot}"
            )

            use_count_value = request.POST.get(
                f"use_count_{slot}",
                "1",
            )

            # スキル未選択なら空きスロット
            if not skill_id:
                new_presets.append(
                    {
                        "slot": slot,
                        "skill": None,
                        "use_count": 1,
                    }
                )
                continue

            # 他職業のスキルをPOSTで送られても使用不可
            skill = available_skills.filter(
                id=skill_id
            ).first()

            if skill is None:
                error_message = (
                    f"SLOT {slot} に使用できない"
                    "スキルが指定されています。"
                )
                break

            # パッシブは使用回数を使わない
            if skill.is_passive:
                use_count = 1

            else:
                try:
                    use_count = int(use_count_value)

                except (TypeError, ValueError):
                    error_message = (
                        f"SLOT {slot} の使用回数が"
                        "正しくありません。"
                    )
                    break

                if use_count < 1:
                    error_message = (
                        f"SLOT {slot} の使用回数は"
                        "1以上にしてください。"
                    )
                    break

            new_presets.append(
                {
                    "slot": slot,
                    "skill": skill,
                    "use_count": use_count,
                }
            )

        # エラーがなければDBへ保存
        if error_message is None:

            with transaction.atomic():

                for data in new_presets:

                    slot = data["slot"]
                    skill = data["skill"]

                    # 空きスロットなら既存設定を削除
                    if skill is None:

                        SkillPreset.objects.filter(
                            character=character,
                            slot=slot,
                        ).delete()

                        continue

                    SkillPreset.objects.update_or_create(
                        character=character,
                        slot=slot,
                        defaults={
                            "skill": skill,
                            "use_count": data["use_count"],
                        },
                    )

            messages.success(
                request,
                "スキルプリセットを保存しました。",
            )

            return redirect("battle:tactics")

    # 現在保存されているプリセット
    preset_dict = {
        preset.slot: preset
        for preset in SkillPreset.objects.filter(
            character=character
        ).select_related("skill")
    }

    # SLOT1～5を必ず画面に表示する
    preset_slots = []

    for slot in range(1, 6):
        preset_slots.append(
            {
                "slot": slot,
                "preset": preset_dict.get(slot),
            }
        )

    return render(
        request,
        "tactics.html",
        {
            "character": character,
            "available_skills": available_skills,
            "preset_slots": preset_slots,
            "error_message": error_message,
        },
    )