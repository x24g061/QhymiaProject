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

        "equipment/<int:owned_equipment_id>/equip/",
        views.equip_equipment,
        name="equip_equipment",
    ),

    path(
        "equipment/<int:owned_equipment_id>/unequip/",
        views.unequip_equipment,
        name="unequip_equipment",
    ),

    path(
        "use/<int:inventory_item_id>/",
        views.use_item,
        name="use_item",
    ),

]