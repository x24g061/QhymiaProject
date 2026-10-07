from django.urls import path
from . import views


app_name = "battle"

urlpatterns = [
    path("", views.battle, name="battle"),

    path(
        "tactics/",
        views.tactics,
        name="tactics",
    ),
    path(
        "",
        views.battle,
        name="battle",
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