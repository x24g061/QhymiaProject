
import os

from django.core.asgi import get_asgi_application


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)


# ========================================
# Django HTTP
# ========================================

django_asgi_application = (
    get_asgi_application()
)


# Django初期化後にChannels関連を読み込む
from channels.auth import AuthMiddlewareStack
from channels.routing import (
    ProtocolTypeRouter,
    URLRouter,
)

# オープンチャット
from apps.chat.routing import (
    websocket_urlpatterns as chat_websocket_patterns,
)

# ショップのリアルタイム通知
from apps.shop.routing import (
    websocket_urlpatterns as shop_websocket_patterns,
)


# ========================================
# ASGI
# ========================================

application = ProtocolTypeRouter(
    {
        # 通常のHTTP通信
        "http":
            django_asgi_application,

        # WebSocket通信
        "websocket":
            AuthMiddlewareStack(
                URLRouter(
                    chat_websocket_patterns
                    + shop_websocket_patterns
                )
            ),
    }
)
