from django.urls import path

from django.urls import path

from .views import (
    character_create_view,
    character_list_view,
    character_image_change_view,
    palm_view,
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

        # 手相
    path(
        "palm/",
        palm_view,
        name="palm",
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

    # キャラクター一覧
    path(
        "character/list/",
        character_list_view,
        name="character_list",
    ),

        # キャラクター画像変更
    path(
        "character/image/change/",
        character_image_change_view,
        name="character_image_change",
    ),
]