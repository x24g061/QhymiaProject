from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ShopStock


@login_required
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