import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_GET, require_POST

from apps.achievements.services import (
    get_public_title_data,
    preload_public_titles,
)

from .models import ChatMessage


@require_GET
@login_required
def get_messages(request):
    messages = (
        ChatMessage.objects
        .select_related("character")
        .order_by("-created_at")[:50]
    )

    preload_public_titles(
        chat.character
        for chat in messages
    )

    data = [
        {
            "id": chat.id,

            # プレイヤー詳細画面へのリンク用
            "character_id": chat.character.id,

            "character_name": chat.character.name,

            **get_public_title_data(chat.character),

            "character_image_url": (
                static(
                    chat.character.character_image_path
                )
                if chat.character.character_image_path
                else None
            ),

            "message": chat.message,

            # 例: 2026/11/26/10:35:03
            "created_at": (
                chat.created_at.strftime(
                    "%Y/%m/%d/%H:%M:%S"
                )
            ),
        }
        for chat in reversed(messages)
    ]

    return JsonResponse({
        "messages": data
    })


@require_POST
@login_required
def send_message(request):
    try:
        data = json.loads(
            request.body
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "error":
                    "送信データが正しくありません"
            },
            status=400,
        )

    if not isinstance(
        data,
        dict,
    ):
        return JsonResponse(
            {
                "error":
                    "送信データが正しくありません"
            },
            status=400,
        )

    message = data.get(
        "message",
        "",
    )

    if not isinstance(
        message,
        str,
    ):
        return JsonResponse(
            {
                "error":
                    "送信データが正しくありません"
            },
            status=400,
        )

    message = message.strip()

    if not message:
        return JsonResponse(
            {
                "error":
                    "メッセージを入力してください"
            },
            status=400,
        )

    if len(message) > 200:
        return JsonResponse(
            {
                "error":
                    "メッセージは200文字以内で入力してください"
            },
            status=400,
        )

    try:
        character = (
            request.user.character
        )

    except Exception:
        return JsonResponse(
            {
                "error":
                    "キャラクターが作成されていません"
            },
            status=400,
        )

    chat = (
        ChatMessage.objects.create(
            character=character,
            message=message,
        )
    )

    return JsonResponse({
        "success": True,

        "message": {
            "id": chat.id,

            # プレイヤー詳細画面へのリンク用
            "character_id": character.id,

            "character_name":
                character.name,

            **get_public_title_data(character),

            "character_image_url": (
                static(
                    character.character_image_path
                )
                if character.character_image_path
                else None
            ),

            "message":
                chat.message,

            # 例: 2026/11/26/10:35:03
            "created_at": (
                chat.created_at.strftime(
                    "%Y/%m/%d/%H:%M:%S"
                )
            ),
        }
    })


# ========================================
# オープンチャット利用規約
# ========================================

@login_required
def chat_terms(request):

    return render(
        request,
        "chat_terms.html",
    )