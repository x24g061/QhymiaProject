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

from apps.chat.routing import (
    websocket_urlpatterns,
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
                    websocket_urlpatterns
                )
            ),
    }
)