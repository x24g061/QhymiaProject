from django.urls import path

from .views import delete_post, sns_page, toggle_favorite, toggle_like

urlpatterns = [
    path("", sns_page, name="sns"),
    path("like/<int:post_id>/", toggle_like, name="toggle_like"),
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