from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.templatetags.static import static

from apps.accounts.models import Character

from .models import ChatMessage


class ChatConsumer(
    AsyncJsonWebsocketConsumer
):

    # Qhymiaではチャットルームは1つだけ
    group_name = "global_chat"


    # ========================================
    # WebSocket接続
    # ========================================

    async def connect(self):

        user = self.scope["user"]

        # 未ログインユーザーは接続させない
        if not user.is_authenticated:
            await self.close(
                code=4401
            )
            return


        # 全ユーザー共通チャットへ参加
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )


        # WebSocket接続を許可
        await self.accept()


    # ========================================
    # WebSocket切断
    # ========================================

    async def disconnect(
        self,
        close_code,
    ):

        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )


    # ========================================
    # ユーザーからメッセージ受信
    # ========================================

    async def receive_json(
        self,
        content,
        **kwargs,
    ):

        message = str(
            content.get(
                "message",
                ""
            )
        ).strip()


        # 空メッセージ
        if not message:

            await self.send_json(
                {
                    "type": "error",
                    "error":
                        "メッセージを入力してください。",
                }
            )

            return


        # 200文字制限
        if len(message) > 200:

            await self.send_json(
                {
                    "type": "error",
                    "error":
                        "メッセージは200文字以内で入力してください。",
                }
            )

            return


        # DBへ保存
        chat_data = (
            await self.create_chat_message(
                self.scope["user"].pk,
                message,
            )
        )


        # キャラクターがない場合
        if "error" in chat_data:

            await self.send_json(
                {
                    "type": "error",
                    "error":
                        chat_data["error"],
                }
            )

            return


        # ========================================
        # 接続中の全ユーザーへ一斉送信
        # ========================================

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type":
                    "chat.message",

                "message":
                    chat_data,
            },
        )


    # ========================================
    # 全ユーザーへチャットを送信
    # ========================================

    async def chat_message(
        self,
        event,
    ):

        await self.send_json(
            {
                "type":
                    "chat_message",

                "message":
                    event["message"],
            }
        )


    # ========================================
    # DBへチャット保存
    # ========================================

    @database_sync_to_async
    def create_chat_message(
        self,
        user_id,
        message,
    ):

        character = (
            Character.objects
            .filter(
                user_id=user_id
            )
            .first()
        )


        if not character:

            return {
                "error":
                    "キャラクターが作成されていません。"
            }


        chat = (
            ChatMessage.objects.create(
                character=character,
                message=message,
            )
        )


        return {
            "id":
                chat.id,

            "character_name":
                character.name,

            "character_image_url": (
                static(
                    character.character_image_path
                )
                if
                character.character_image_path
                else None
            ),

            "message":
                chat.message,

            "created_at":
                chat.created_at.strftime(
                    "%H:%M"
                ),
        }