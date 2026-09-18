from django.urls import path

from . import views


app_name = "payment"

urlpatterns = [
    path(
        "purchase/<int:amount>/",
        views.purchase_q,
        name="purchase_q",
    ),

    path(
        "tokushoho/",
        views.kakin_tokushoho,
        name="kakin_tokushoho",
    ),
]