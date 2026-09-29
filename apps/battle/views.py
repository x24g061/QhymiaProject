from datetime import timedelta
import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.inventory.models import Item, InventoryItem


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

    # ========================================
    # アイテムドロップ判定
    # ========================================

    # 基本1%
    # 闘技場の連勝数1につき +1%
    # 最大20%
    item_drop_rate = min(
        1 + character.arena_win_streak,
        10
    )

    dropped_item = None

    roll = random.randint(1, 100)

    if roll <= item_drop_rate:
        dropped_item = (
            Item.objects
            .filter(category=Item.Category.MATERIAL)
            .order_by("?")
            .first()
        )

        if dropped_item:
            inventory_item, created = (
                InventoryItem.objects.get_or_create(
                    character=character,
                    item=dropped_item,
                    defaults={
                        "quantity": 1
                    }
                )
            )

            if not created:
                inventory_item.quantity += 1
                inventory_item.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

    return render(
        request,
        "battle.html",
        {
            "character": character,
            "cooldown_seconds": cooldown_seconds,
            "item_drop_rate": item_drop_rate,
            "dropped_item": dropped_item,
        }
    )


# ========================================
# 闘技場の勝敗結果を保存
# ========================================

@login_required
def arena_result(request, result):
    character = request.user.character

    if result == "win":
        character.arena_win_streak += 1
        character.arena_last_result = "win"

        messages.success(
            request,
            f"闘技場で勝利しました！現在{character.arena_win_streak}連勝中です。"
        )

    elif result == "loss":
        character.arena_win_streak = 0
        character.arena_last_result = "loss"
        character.arena_next_floor_unlocked = True

    else:
        messages.error(
            request,
            "不正な闘技場結果です。"
        )

        return redirect("home")

    character.save(
        update_fields=[
            "arena_win_streak",
            "arena_last_result",
            "updated_at",
        ]
    )

    return redirect("home")

@login_required
def arena_next_floor(request):
    character = request.user.character

    # 次の階がまだ解禁されていない
    if not character.arena_next_floor_unlocked:
        messages.warning(
            request,
            "まだ次の階には挑戦できません。"
        )
        return redirect("home")

    # 最上階チェック
    arena_max_floor = 100

    if character.arena_floor >= arena_max_floor:
        messages.warning(
            request,
            "これ以上上の階には進めません。"
        )
        return redirect("home")

    # 次の階へ進む
    character.arena_floor += 1

    # 進んだら再びロック
    character.arena_next_floor_unlocked = False

    character.save(
        update_fields=[
            "arena_floor",
            "arena_next_floor_unlocked",
            "updated_at",
        ]
    )

    return redirect("home")


@login_required
def arena_battle(request):
    character = request.user.character
    now = timezone.now()

    # 探索・闘技場共通CT
    if (
        character.exploration_cooldown_until
        and character.exploration_cooldown_until > now
    ):
        remaining = character.get_exploration_cooldown_remaining()

        messages.warning(
            request,
            f"クールタイム中です。あと約{remaining}秒です。"
        )

        return redirect("home")

    cooldown_seconds = (
        character.get_exploration_cooldown_seconds()
    )

    character.exploration_cooldown_until = (
        now + timedelta(seconds=cooldown_seconds)
    )

    character.save(
        update_fields=[
            "exploration_cooldown_until",
            "updated_at",
        ]
    )

    return redirect("home")