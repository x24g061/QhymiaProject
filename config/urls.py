"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views.
"""

from django.contrib import admin
from django.urls import include, path

from .views import home


urlpatterns = [
    path('admin/', admin.site.urls),

    # ホーム画面
    path('', home, name='home'),

    # ログイン・アカウント関連
    path('', include('apps.accounts.urls')),

    # 戦闘画面
    path('battle/', include('apps.battle.urls')),
]