from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone


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