
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class MarketNotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    フリーマーケットのリアルタイム売却通知。

    ・ログイン済みユーザーだけ接続可能
    ・ユーザーごとに専用グループを作成
    ・出品者本人にだけ売却通知を送信
    """

    # ========================================================
    # WebSocket接続
    # ========================================================

    async def connect(self):

        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close(code=4401)
            return

        # キャラクター名ではなくユーザーIDで識別
        self.group_name = f"sale_user_{user.pk}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

    # ========================================================
    # WebSocket切断
    # ========================================================

    async def disconnect(self, close_code):

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    # ========================================================
    # 売却通知をブラウザに送信
    # ========================================================

    async def sale_notification(self, event):

        await self.send_json({
            "type": "sale_notification",
            "notification_id": event["notification_id"],
            "message": event["message"],
            "created_at": event["created_at"],
        })
