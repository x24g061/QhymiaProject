from django.contrib import admin
from django.urls import include, path

from .views import again,home

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', home, name='home'),
    
    path('again/', again, name='again'),

    # Qhymiaアカウント
    path('', include('apps.accounts.urls')),

    # Googleログインなど django-allauth
    path('accounts/', include('allauth.urls')),

    # 戦闘画面
    path('battle/', include('apps.battle.urls')),
]