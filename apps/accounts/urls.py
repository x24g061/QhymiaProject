from django.urls import path

from .views import (
    character_create_view,
    login_view,
    logout_view,
    signup_view,
    profile_view,
    terms_view,
    tokushoho_view,
    privacy_view,
)


app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),

    # プロフィール
    path(
        "profile/",
        profile_view,
        name="profile",
    ),

    # 利用規約
    path("terms/", terms_view, name="terms"),

    # 特定商取引法に基づく表記
    path(
        "tokushoho/",
        tokushoho_view,
        name="tokushoho",
    ),

    # プライバシーポリシー
    path(
        "privacy/",
        privacy_view,
        name="privacy",
    ),

    # キャラクター作成
    path(
        "character/create/",
        character_create_view,
        name="character_create",
    ),
]