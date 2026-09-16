from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def battle(request):
    return render(request, "battle.html")