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

    path(
    "market/list/<int:inventory_item_id>/",
    views.create_market_listing,
    name="create_market_listing",
    ),

    path(
    "market/buy/<int:listing_id>/",
    views.buy_market_listing,
    name="buy_market_listing",
    ),
]