from django.urls import path
from . import views


app_name = "battle"

urlpatterns = [
    path(
        "",
        views.battle,
        name="battle",
    ),

    path(
        "arena/result/<str:result>/",
        views.arena_result,
        name="arena_result",
    ),

    path(
    "arena/",
    views.arena_battle,
    name="arena_battle",
    ),
    path(
        "arena/next-floor/",
        views.arena_next_floor,
        name="arena_next_floor",
    ),
]