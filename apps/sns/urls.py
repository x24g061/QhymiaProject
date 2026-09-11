from django.urls import path

from .views import sns_page, toggle_like


urlpatterns = [
    path("", sns_page, name="sns"),
    path("like/<int:post_id>/", toggle_like, name="toggle_like"),
]