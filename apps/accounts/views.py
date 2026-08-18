from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect


def login_view(request):
    error_message = None

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        password = request.POST.get("password")

        user = authenticate(
            request,
            user_id=user_id,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("home")

        error_message = "固有IDまたはパスワードが正しくありません。"

    return render(
        request,
        "login.html",
        {
            "error_message": error_message,
        },
    )