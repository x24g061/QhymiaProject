
from django.urls import path

from .consumers import MarketNotificationConsumer


websocket_urlpatterns = [
    path(
        "ws/market-notifications/",
        MarketNotificationConsumer.as_asgi(),
    ),
]
