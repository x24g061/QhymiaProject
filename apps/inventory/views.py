from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Character

from .models import InventoryItem


# ========================================
# 倉庫画面
# ========================================
@login_required
def inventory(request):
    character = request.user.character

    # 実際に所持しているアイテムを取得
    inventory_items = (
        InventoryItem.objects
        .filter(character=character)
        .select_related("item")
    )

    # アイテムの合計所持数
    total_item_count = sum(
        inventory_item.quantity
        for inventory_item in inventory_items
    )

    return render(
        request,
        "inventory.html",
        {
            "character": character,
            "inventory_items": inventory_items,
            "total_item_count": total_item_count,
        },
    )


# ========================================
# アイテム使用処理
# ========================================
@login_required
@transaction.atomic
def use_item(request, inventory_item_id):

    # POST以外では使用できない
    if request.method != "POST":
        return redirect("inventory:inventory")

    # キャラクターをロックして取得
    character = Character.objects.select_for_update().get(
        user=request.user
    )

    # 自分の所持アイテムだけ取得できる
    try:
        inventory_item = (
            InventoryItem.objects
            .select_for_update()
            .select_related("item")
            .get(
                pk=inventory_item_id,
                character=character,
            )
        )
    except InventoryItem.DoesNotExist:
        messages.error(
            request,
            "アイテムが見つかりません。",
        )
        return redirect("inventory:inventory")

    item = inventory_item.item

    # ========================================
    # 使用可能チェック
    # ========================================
    if not item.is_usable:
        messages.error(
            request,
            "このアイテムは使用できません。",
        )
        return redirect("inventory:inventory")

    # 今回はCT短縮時計のみ使用処理を実装
    if not item.cooldown_reduction_days:
        messages.error(
            request,
            "このアイテムの使用効果はまだ実装されていません。",
        )
        return redirect("inventory:inventory")

    now = timezone.now()

    # ========================================
    # 時計の効果期間を追加
    # ========================================

    # すでにCT短縮効果中かどうか
    already_active = (
        character.exploration_cooldown_reduced_until
        and
        character.exploration_cooldown_reduced_until > now
    )

    if already_active:
        # すでに効果中なら、現在の終了日時から日数を加算
        character.exploration_cooldown_reduced_until += timedelta(
            days=item.cooldown_reduction_days
        )

    else:
        # 効果がない場合は現在時刻から開始
        character.exploration_cooldown_reduced_until = (
            now
            + timedelta(days=item.cooldown_reduction_days)
        )

        # ========================================
        # 初回使用時だけ
        # 現在進行中の戦闘CTを20秒短縮
        # ========================================
        if (
            character.exploration_cooldown_until
            and
            character.exploration_cooldown_until > now
        ):
            shortened_until = (
                character.exploration_cooldown_until
                - timedelta(seconds=20)
            )

            # 20秒以下しか残っていない場合は即時解除
            if shortened_until <= now:
                character.exploration_cooldown_until = now
            else:
                character.exploration_cooldown_until = shortened_until

    character.save(
        update_fields=[
            "exploration_cooldown_reduced_until",
            "exploration_cooldown_until",
            "updated_at",
        ]
    )

    # ========================================
    # 使用したアイテムを1個消費
    # ========================================
    if inventory_item.quantity <= 1:
        inventory_item.delete()
    else:
        inventory_item.quantity -= 1
        inventory_item.save(
            update_fields=["quantity"],
        )

    messages.success(
        request,
        (
            f"{item.name}を使用しました。"
            f"戦闘クールタイムが20秒になります。"
        ),
    )

    return redirect("inventory:inventory")