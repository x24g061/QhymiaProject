from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from .forms import SignUpForm
from .models import Character, User
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from pathlib import Path
from django.conf import settings
import random

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

def get_available_character_images():
    character_dir = (
        Path(settings.BASE_DIR)
        / "static"
        / "images"
        / "characters"
    )

    characters = []

    if not character_dir.exists():
        return characters

    for image_file in character_dir.glob("*.png"):
        # 001.png → 1
        if not image_file.stem.isdigit():
            continue

        number = int(image_file.stem)

        characters.append({
            "number": number,
            "image": (
                f"images/characters/"
                f"{number:03d}.png"
            ),
        })

    characters.sort(
        key=lambda character: character["number"]
    )

    return characters

@login_required
def character_create_view(request):
    # すでにキャラクターを持っている場合
    if Character.objects.filter(
        user=request.user
    ).exists():
        return redirect("home")

    error_message = None

    available_characters = (
        get_available_character_images()
    )

    available_numbers = {
        character["number"]
        for character in available_characters
    }

    # ランダム表示用
    random_characters = random.sample(
        available_characters,
        min(8, len(available_characters))
    )

    selected_character = (
        random_characters[0]
        if random_characters
        else None
    )

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

        character_image_id = request.POST.get(
            "character_image_id",
            ""
        ).strip()

        try:
            character_image_id = int(
                character_image_id
            )
        except (TypeError, ValueError):
            character_image_id = None

        if not character_name:
            error_message = (
                "キャラクター名を入力してください。"
            )

        elif Character.objects.filter(
            name=character_name
        ).exists():
            error_message = (
                "そのキャラクター名は"
                "既に使用されています。"
            )

        elif (
            character_image_id
            not in available_numbers
        ):
            error_message = (
                "存在するキャラクター画像を"
                "選択してください。"
            )

        else:
            Character.objects.create(
                user=request.user,
                name=character_name,
                race=race,
                job=job,
                character_image_id=character_image_id,
            )

            return redirect("home")

    return render(
        request,
        "character_create.html",
        {
            "error_message": error_message,
            "available_characters":
                available_characters,
            "random_characters":
                random_characters,
            "selected_character":
                selected_character,
            "available_numbers": [
                character["number"]
                for character
                in available_characters
            ],
        },
    )
@login_required
def character_list_view(request):
    characters = []

    for number in range(1, 101):
        image_path = f"images/characters/{number:03d}.png"

        # 画像が存在するか確認
        image_exists = finders.find(image_path) is not None

        characters.append({
            "number": number,
            "image": image_path if image_exists else None,
        })

    return render(
        request,
        "character_list.html",
        {
            "characters": characters,
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
    from_page = request.GET.get("from")

    if from_page == "login":
        back_url_name = "accounts:login"
        back_text = "＜ ログイン画面に戻る"
    else:
        back_url_name = "accounts:signup"
        back_text = "＜ 新規登録画面に戻る"

    return render(
        request,
        "terms.html",
        {
            "back_url_name": back_url_name,
            "back_text": back_text,
        },
    )


# 特定商取引法
def tokushoho_view(request):
    from_page = request.GET.get("from")

    if from_page == "login":
        back_url_name = "accounts:login"
        back_text = "＜ ログイン画面に戻る"
    else:
        back_url_name = "accounts:signup"
        back_text = "＜ 新規登録画面に戻る"

    return render(
        request,
        "tokushoho.html",
        {
            "back_url_name": back_url_name,
            "back_text": back_text,
        },
    )


# プライバシーポリシー
def privacy_view(request):
    from_page = request.GET.get("from")

    if from_page == "login":
        back_url_name = "accounts:login"
        back_text = "＜ ログイン画面に戻る"
    else:
        back_url_name = "accounts:signup"
        back_text = "＜ 新規登録画面に戻る"

    return render(
        request,
        "privacy.html",
        {
            "back_url_name": back_url_name,
            "back_text": back_text,
        },
    )