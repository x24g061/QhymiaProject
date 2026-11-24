
import random

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Character
from apps.inventory.models import Item, InventoryItem

from .models import FishingSession


# ========================================
# 魚のレアリティと出現確率
# ========================================

FISH_RARITIES = [
    ("コモン", 60),
    ("レア", 25),
    ("エピック", 12),
    ("レジェンド", 3),
]

FISH_ITEM_NAMES = {
    "コモン": "コモンの魚",
    "レア": "レアの魚",
    "エピック": "エピックの魚",
    "レジェンド": "レジェンドの魚",
}


# ========================================
# 釣り画面
# ========================================

@login_required
def fishing(request):
    return render(request, "fishing.html")


# ========================================
# 釣り開始
# ========================================

@login_required
@require_POST
@transaction.atomic
def start_fishing(request):

    # 同じキャラクターの開始処理を直列化
    character = (
        Character.objects
        .select_for_update()
        .filter(user=request.user)
        .first()
    )

    if character is None:
        return JsonResponse(
            {"error": "キャラクターが存在しません。"},
            status=400,
        )

    # 未終了の釣りは失敗扱いにする
    FishingSession.objects.filter(
        user=request.user,
        status=FishingSession.Status.PLAYING,
    ).update(
        status=FishingSession.Status.FAILED,
        finished_at=timezone.now(),
    )

    # レアリティをサーバー側で抽選
    rarity = random.choices(
        [name for name, weight in FISH_RARITIES],
        weights=[weight for name, weight in FISH_RARITIES],
        k=1,
    )[0]

    # 釣りセッションを作成
    session = FishingSession.objects.create(
        user=request.user,
        rarity=rarity,
    )

    return JsonResponse({
        "session_id": session.id,
        "rarity": rarity,
    })


# ========================================
# 釣り終了・報酬受け取り
# ========================================

@login_required
@require_POST
@transaction.atomic
def finish_fishing(request):

    # ====================================
    # セッションIDの確認
    # ====================================

    try:
        session_id = int(
            request.POST.get("session_id", 0)
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "セッションIDが不正です。"},
            status=400,
        )

    # ====================================
    # キャラクター取得・ロック
    # ====================================

    character = (
        Character.objects
        .select_for_update()
        .filter(user=request.user)
        .first()
    )

    if character is None:
        return JsonResponse(
            {"error": "キャラクターが存在しません。"},
            status=400,
        )

    # ====================================
    # 釣りセッション取得・ロック
    # ====================================

    session = (
        FishingSession.objects
        .select_for_update()
        .filter(
            id=session_id,
            user=request.user,
        )
        .first()
    )

    if session is None:
        return JsonResponse(
            {"error": "釣り記録が見つかりません。"},
            status=404,
        )

    # ====================================
    # 二重受け取り防止
    # ====================================

    if session.status != FishingSession.Status.PLAYING:
        return JsonResponse(
            {"error": "この釣りはすでに終了しています。"},
            status=400,
        )

    if session.reward_claimed:
        return JsonResponse(
            {"error": "報酬はすでに受け取り済みです。"},
            status=400,
        )

    # ====================================
    # プレイ時間チェック
    # ====================================

    now = timezone.now()

    elapsed = (
        now - session.started_at
    ).total_seconds()

    # 8秒未満の釣り成功申告は禁止
    if elapsed < 8:
        return JsonResponse(
            {"error": "釣り終了までの時間が短すぎます。"},
            status=400,
        )

    # 120秒経過したセッションは失効
    if elapsed > 120:
        session.status = FishingSession.Status.FAILED
        session.finished_at = now

        session.save(
            update_fields=[
                "status",
                "finished_at",
            ]
        )

        return JsonResponse(
            {"error": "釣りの有効時間が過ぎました。"},
            status=400,
        )

    # ====================================
    # 釣り結果の確認
    # ====================================

    success = (
        request.POST.get("success") == "true"
    )

    # 釣り失敗
    if not success:
        session.status = FishingSession.Status.FAILED
        session.finished_at = now

        session.save(
            update_fields=[
                "status",
                "finished_at",
            ]
        )

        return JsonResponse({
            "success": False,
            "message": "魚は釣れませんでした。",
        })

    # ====================================
    # サーバー側で魚アイテムを決定
    # ====================================

    fish_name = FISH_ITEM_NAMES.get(
        session.rarity
    )

    if fish_name is None:
        return JsonResponse(
            {"error": "魚の種類が不正です。"},
            status=400,
        )

    fish_item = (
        Item.objects
        .filter(name=fish_name)
        .first()
    )

    if fish_item is None:
        return JsonResponse(
            {"error": "魚アイテムが登録されていません。"},
            status=500,
        )

    # ====================================
    # 魚を倉庫に1匹追加
    # ====================================

    inventory_item, created = (
        InventoryItem.objects.get_or_create(
            character=character,
            item=fish_item,
            defaults={
                "quantity": 1,
            },
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

    # ====================================
    # セッション終了・受け取り済みに変更
    # ====================================

    session.status = FishingSession.Status.SUCCESS
    session.finished_at = now
    session.reward_claimed = True

    session.save(
        update_fields=[
            "status",
            "finished_at",
            "reward_claimed",
        ]
    )

    # ====================================
    # 結果を返す
    # ====================================

    return JsonResponse({
        "success": True,
        "fish_name": fish_name,
        "quantity": inventory_item.quantity,
        "message": f"{fish_name}を1匹獲得しました！",
    })
