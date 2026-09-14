from django.urls import path

from .views import (
    character_create_view,
    login_view,
    signup_view,
)


app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),

    path(
        "character/create/",
        character_create_view,
        name="character_create",
    ),
]