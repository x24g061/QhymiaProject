from django.urls import path

from . import views


app_name = "shop"


urlpatterns = [
    path("", views.shop, name="shop"),

    path(
        "npc/",
        views.npc_shop,
        name="npc_shop",
    ),

    path(
        "npc/buy/<int:stock_id>/",
        views.buy_item,
        name="buy_item",
    ),
]