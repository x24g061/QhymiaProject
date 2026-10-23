from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def fishing(request):
    return render(request, "fishing.html")