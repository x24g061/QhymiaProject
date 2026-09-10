from django.shortcuts import render

from .models import ShopStock


def shop(request):
    shop_stocks = (
        ShopStock.objects
        .filter(is_available=True)
        .select_related("item")
    )

    return render(
        request,
        "shop.html",
        {
            "shop_stocks": shop_stocks,
        },
    )