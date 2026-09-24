from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from .forms import SignUpForm
from .models import Character, User
from django.contrib.auth.decorators import login_required


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def login_view(request):
    error_message = None

    if request.method == "POST":
        login_id = request.POST.get("user_id", "").strip()
        password = request.POST.get("password")

        # メールアドレスで入力された場合
        if "@" in login_id:
            user_obj = User.objects.filter(
                email__iexact=login_id
            ).first()

            if user_obj:
                login_id = user_obj.user_id

        user = authenticate(
            request,
            user_id=login_id,
            password=password,
        )

        if user is not None:
            login(request, user)

            if not Character.objects.filter(user=user).exists():
                return redirect("accounts:character_create")

            next_url = request.GET.get("next")

            if next_url:
                return redirect(next_url)

            return redirect("home")

        error_message = "固有ID・メールアドレスまたはパスワードが正しくありません。"

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
        race = request.POST.get(
            "race",
            ""
        ).strip()
        job = request.POST.get(
            "job",
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
                race=race,
                job=job,
            )

            return redirect("home")

    return render(
        request,
        "character_create.html",
        {
            "error_message": error_message,
        },
    )


# プロフィール
@login_required
def profile_view(request):
    character = getattr(
        request.user,
        "character",
        None,
    )

    return render(
        request,
        "profile.html",
        {
            "character": character,
        },
    )


# 利用規約
def terms_view(request):
    return render(request, "terms.html")


# 特定商取引法
def tokushoho_view(request):
    return render(request, "tokushoho.html")


# プライバシーポリシー
def privacy_view(request):
    return render(request, "privacy.html")