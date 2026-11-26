from django.urls import path

from .views import (
    character_create_view,
    character_list_view,
    character_image_change_view,
    passive_detail_view,
    palm_view,
    login_view,
    logout_view,
    signup_view,
    settings_view,
    profile_view,
    terms_view,
    tokushoho_view,
    privacy_view,
    disable_debug_mode_view,
    update_debug_drop_rate_view,
    debug_settings_view,
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

    # 設定画面
    path(
        "settings/",
        settings_view,
        name="settings",
    ),

    # 手相
    path(
        "palm/",
        palm_view,
        name="palm",
    ),

    # デバッグモード
    path(
        "debug-mode/disable/",
        disable_debug_mode_view,
        name="disable_debug_mode",
    ),
    path(
        "debug-mode/drop-rate/",
        update_debug_drop_rate_view,
        name="update_debug_drop_rate",
    ),
    path(
        "debug-mode/settings/",
        debug_settings_view,
        name="debug_settings",
    ),
    # 利用規約
    path(
        "terms/",
        terms_view,
        name="terms",
    ),

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

    # 種族パッシブ詳細
    path(
        "character/passive/",
        passive_detail_view,
        name="passive_detail",
    ),

    # キャラクター画像変更
    path(
        "character/image/change/",
        character_image_change_view,
        name="character_image_change",
    ),
]