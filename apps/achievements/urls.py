from django.urls import path

from . import views

app_name = "achievements"

urlpatterns = [
    path(
        "",
        views.achievement_list,
        name="list",
    ),
    path(
        "title/",
        views.change_title,
        name="change_title",
    ),
]
