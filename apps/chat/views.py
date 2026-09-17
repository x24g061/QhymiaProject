import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import ChatMessage


@require_GET
@login_required
def get_messages(request):
    messages = (
        ChatMessage.objects
        .select_related("character")
        .order_by("-created_at")[:50]
    )

    data = [
        {
            "id": chat.id,
            "character_name": chat.character.name,
            "message": chat.message,
            "created_at": chat.created_at.strftime("%H:%M"),
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
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "送信データが正しくありません"},
            status=400
        )

    message = data.get("message", "").strip()

    if not message:
        return JsonResponse(
            {"error": "メッセージを入力してください"},
            status=400
        )

    if len(message) > 200:
        return JsonResponse(
            {"error": "メッセージは200文字以内で入力してください"},
            status=400
        )

    try:
        character = request.user.character
    except Exception:
        return JsonResponse(
            {"error": "キャラクターが作成されていません"},
            status=400
        )

    chat = ChatMessage.objects.create(
        character=character,
        message=message
    )

    return JsonResponse({
        "success": True,
        "message": {
            "id": chat.id,
            "character_name": character.name,
            "message": chat.message,
            "created_at": chat.created_at.strftime("%H:%M"),
        }
    })