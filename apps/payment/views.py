from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect


# 購入可能なQ
Q_PACKAGES = {
    500: 500,
    1000: 1000,
    3000: 3000,
    5000: 5000,
    10000: 10000,
}


@login_required
@transaction.atomic
def purchase_q(request, amount):
    if request.method != "POST":
        return redirect("shop:npc_shop")

    # 不正な金額を防止
    if amount not in Q_PACKAGES:
        messages.error(
            request,
            "購入できないQが指定されました。",
        )
        return redirect("shop:npc_shop")

    character = getattr(request.user, "character", None)

    if character is None:
        messages.error(
            request,
            "キャラクターを作成してからQを購入してください。",
        )
        return redirect("shop:npc_shop")

    # Qを加算
    character.gold += Q_PACKAGES[amount]
    character.save(
        update_fields=["gold"],
    )

    messages.success(
        request,
        f"{Q_PACKAGES[amount]:,} Qを購入しました。",
    )

    return redirect("shop:npc_shop")