from django.urls import path

from .views import (
    admin_delete_post,
    delete_post,
    mini_create_post,
    mini_sns_feed,
    sns_page,
    toggle_favorite,
    toggle_like,
)

urlpatterns = [

    path(
        "",
        sns_page,
        name="sns",
    ),

    path(
        "mini/post/",
        mini_create_post,
        name="mini_create_post",
    ),

    path(
    "mini/feed/",
    mini_sns_feed,
    name="mini_sns_feed",
    ),

    path(
        "admin/delete/<int:post_id>/",
        admin_delete_post,
        name="admin_delete_post",
    ),

    path(
        "like/<int:post_id>/",
        toggle_like,
        name="toggle_like",
    ),

    path(
        "delete/<int:post_id>/",
        delete_post,
        name="delete_post",
    ),

    path(
        "favorite/<int:post_id>/",
        toggle_favorite,
        name="toggle_favorite",
    ),
]