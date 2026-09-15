from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect

from .forms import SignUpForm
from .models import Character

from django.contrib.auth.decorators import login_required


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


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

            if Character.objects.filter(user=user).exists():
                return redirect("home")
            else:
                return redirect("accounts:character_create")

        error_message = "固有IDまたはパスワードが正しくありません。"

    return render(
        request,
        "login.html",
        {
            "error_message": error_message,
        },
    )


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()

            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

            return redirect("accounts:character_create")

    else:
        form = SignUpForm()

    return render(
        request,
        "signup.html",
        {
            "form": form,
        },
    )


@login_required
def character_create_view(request):
    # すでにキャラクターを持っている場合
    if Character.objects.filter(user=request.user).exists():
        return redirect("home")

    error_message = None

    if request.method == "POST":
        character_name = request.POST.get(
            "character_name",
            ""
        ).strip()

        if not character_name:
            error_message = "キャラクター名を入力してください。"

        elif Character.objects.filter(
            name=character_name
        ).exists():
            error_message = "そのキャラクター名は既に使用されています。"

        else:
            Character.objects.create(
                user=request.user,
                name=character_name,
            )

            return redirect("home")

    return render(
        request,
        "character_create.html",
        {
            "error_message": error_message,
        },
    )