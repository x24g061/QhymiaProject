from django.urls import path

from . import views


app_name = "payment"

urlpatterns = [
    path("purchase/<int:amount>/", views.purchase_q, name="purchase_q"),
]