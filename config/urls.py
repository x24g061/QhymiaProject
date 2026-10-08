from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import (
    admin_mode_login,
    admin_mode_logout,
    admin_panel,
    admin_player_edit,
    again,
    home,
    player_search,
)
urlpatterns = [
    path('admin/', admin.site.urls),

    path('', home, name='home'),
    path('player_search/', player_search, name='player_search'),
    path('admin_panel/', admin_panel, name='admin_panel'),
    # 管理者モードログイン
    path('admin_mode_login/', admin_mode_login, name='admin_mode_login'),
    path('again/', again, name='again'),
    path(
    "admin-panel/player/<int:character_id>/edit/",
    admin_player_edit,
    name="admin_player_edit",
    ),
    path(
    "admin-mode/logout/",
    admin_mode_logout,
    name="admin_mode_logout",
),
    # SNS
    path('sns/', include('apps.sns.urls')),

    # Qhymiaアカウント
    path('', include('apps.accounts.urls')),

    # Googleログインなど django-allauth
    path('accounts/', include('allauth.urls')),

    # 戦闘画面
    path('battle/', include('apps.battle.urls')),

    #SHOP画面
    path("shop/", include("apps.shop.urls")),

    # Inventory画面
    path("inventory/", include("apps.inventory.urls")),

     # Payment
    path("payment/", include("apps.payment.urls")),
    # Open Chat
        path("chat/", include("apps.chat.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )