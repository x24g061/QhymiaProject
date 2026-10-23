from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("fishing/", views.fishing, name="fishing"),
]