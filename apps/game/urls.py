from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("fishing/", views.fishing, name="fishing"),
    path("fishing/start/", views.start_fishing, name="fishing_start"),
    path("fishing/finish/", views.finish_fishing, name="fishing_finish"),
]