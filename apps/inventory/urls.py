from django.urls import path

from . import views


app_name = "inventory"

urlpatterns = [
    path(
        "",
        views.inventory,
        name="inventory",
    ),

    path(
        "use/<int:inventory_item_id>/",
        views.use_item,
        name="use_item",
    ),
]