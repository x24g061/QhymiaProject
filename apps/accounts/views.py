import random

from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.utils import timezone

from apps.battle.models import (
    ArenaFloor,
    ArenaState,
)
from pathlib import Path
from .forms import SignUpForm
from .models import (
    Character,
    User,
    UserSettings,
)

from .debug_mode import (
    disable_debug_mode,
    get_debug_drop_rate,
    set_debug_drop_rate,
    is_debug_mode,
)

from PIL import Image, UnidentifiedImageError



def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@login_required
def settings_view(request):

    # ========================================
    # ユーザー設定取得
    # ========================================

    user_settings, _ = (
        UserSettings.objects.get_or_create(
            user=request.user
        )
    )


    # ========================================
    # 設定保存
    # ========================================

    if request.method == "POST":

        action = request.POST.get(
            "action",
            "save",
        )

        synthesis_sns_prompt_enabled = (
            request.POST.get(
                "synthesis_sns_prompt_enabled"
            )
            == "on"
        )


        # ========================================
        # 背景をデフォルトに戻す
        # ========================================

        if action == "remove_background":

            old_background = (
                user_settings.background_image
                if user_settings.background_image
                else None
            )

            user_settings.background_image = ""

            user_settings.synthesis_sns_prompt_enabled = (
                synthesis_sns_prompt_enabled
            )

            user_settings.save(
                update_fields=[
                    "background_image",
                    "synthesis_sns_prompt_enabled",
                    "updated_at",
                ]
            )

            # 古い画像ファイルを削除
            if old_background:

                old_background.delete(
                    save=False
                )

            messages.success(
                request,
                "背景をデフォルトに戻しました。",
            )

            return redirect(
                "accounts:settings"
            )


        # ========================================
        # 背景画像アップロード
        # ========================================

        background_image = (
            request.FILES.get(
                "background_image"
            )
        )

        old_background_name = None


        if background_image:

            # ====================================
            # 最大5MB
            # ====================================

            if (
                background_image.size
                > 5 * 1024 * 1024
            ):

                messages.error(
                    request,
                    "背景画像は5MB以下にしてください。",
                )

                return redirect(
                    "accounts:settings"
                )


            # ====================================
            # 使用可能な画像形式
            # ====================================

            allowed_types = {
                "image/jpeg",
                "image/png",
                "image/webp",
            }

            if (
                background_image.content_type
                not in allowed_types
            ):

                messages.error(
                    request,
                    (
                        "背景画像はPNG・JPG・"
                        "WebP形式を使用してください。"
                    ),
                )

                return redirect(
                    "accounts:settings"
                )


            # ====================================
            # 本当に画像か確認
            # ====================================

            try:

                image = Image.open(
                    background_image
                )

                image.verify()

                background_image.seek(0)

            except (
                UnidentifiedImageError,
                OSError,
            ):

                messages.error(
                    request,
                    "正しい画像ファイルを選択してください。",
                )

                return redirect(
                    "accounts:settings"
                )


            # ====================================
            # 古い背景を記録
            # ====================================

            if user_settings.background_image:

                old_background_name = (
                    user_settings
                    .background_image
                    .name
                )


            # ====================================
            # 新しい背景を設定
            # ====================================

            user_settings.background_image = (
                background_image
            )


        # ========================================
        # SNS設定
        # ========================================

        user_settings.synthesis_sns_prompt_enabled = (
            synthesis_sns_prompt_enabled
        )


        update_fields = [
            "synthesis_sns_prompt_enabled",
            "updated_at",
        ]


        if background_image:

            update_fields.append(
                "background_image"
            )


        user_settings.save(
            update_fields=update_fields
        )


        # ========================================
        # 古い背景画像を削除
        # ========================================

        if (
            background_image
            and
            old_background_name
            and
            old_background_name
            != user_settings.background_image.name
        ):

            user_settings.background_image.storage.delete(
                old_background_name
            )


        if not synthesis_sns_prompt_enabled:

            request.session.pop(
                "synthesis_sns_share",
                None,
            )


        messages.success(
            request,
            "設定を保存しました。",
        )


        return redirect(
            "accounts:settings"
        )


    return render(
        request,
        "settings.html",
        {
            "game_settings":
                user_settings,
        },
    )


def login_view(request):
    error_message = None



    # ========================================
    # ログイン画面ランキング
    # ========================================
    #
    # 優先順位
    # 1. 回帰数が多い
    # 2. 回帰数が同じならレベルが高い
    # 3. それも同じならID順
    # ========================================

    ranking = (
        Character.objects
        .order_by(
            "-reincarnation_count",
            "-level",
            "id",
        )[:3]
    )


    if request.method == "POST":
        login_id = request.POST.get(
            "user_id",
            "",
        ).strip()

        password = request.POST.get(
            "password"
        )

        # メールアドレスで入力された場合
        if "@" in login_id:
            user_obj = (
                User.objects
                .filter(
                    email__iexact=login_id
                )
                .first()
            )

            if user_obj:
                login_id = (
                    user_obj.user_id
                )

        user = authenticate(
            request,
            user_id=login_id,
            password=password,
        )

        if user is not None:
            login(
                request,
                user,
            )

            if not Character.objects.filter(
                user=user
            ).exists():

                return redirect(
                    "accounts:character_create"
                )

            next_url = request.GET.get(
                "next"
            )

            if next_url:
                return redirect(
                    next_url
                )

            return redirect(
                "home"
            )

        error_message = (
            "固有ID・メールアドレスまたは"
            "パスワードが正しくありません。"
        )


    return render(
        request,
        "login.html",
        {
            "error_message":
                error_message,

            "ranking":
                ranking,
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


    # ========================================
    # 選択中キャラクター
    # ========================================

    selected_character = (
        random_characters[0]
        if random_characters
        else None
    )


    # キャラクター一覧から選択された番号
    selected_number = request.GET.get(
        "character"
    )

    try:
        selected_number = int(
            selected_number
        )

    except (TypeError, ValueError):
        selected_number = None


    # 実在する画像なら選択状態にする
    if selected_number in available_numbers:

        selected_character = next(
            (
                character
                for character
                in available_characters
                if character["number"]
                == selected_number
            ),
            selected_character,
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
            # ========================================================
            # キャラクター作成
            # ========================================================
            #
            # CharacterとArenaStateはセットで作成する。
            #
            # 途中でArenaStateの作成に失敗した場合、
            # Characterだけが残らないようtransaction.atomic()を使う。
            # ========================================================

            with transaction.atomic():

                # アカウントをロックして二重配布を防止
                user = (
                    User.objects
                    .select_for_update()
                    .get(pk=request.user.pk)
                )

                # ロック取得後にキャラクターの存在を再確認
                if Character.objects.filter(user=user).exists():
                    return redirect("home")

                # 初回登録特典
                signup_bonus = (
                    300 if user.signup_bonus_pending else 0
                )

                character = Character.objects.create(
                    user=user,
                    name=character_name,
                    race=race,
                    job=job,
                    character_image_id=character_image_id,
                    gold=signup_bonus,
                )

                if signup_bonus:
                    user.signup_bonus_pending = False
                    user.save(
                        update_fields=["signup_bonus_pending"]
                    )

                # ================================================
                # 闘技場初期状態
                # ================================================
                #
                # 新規キャラクターは必ず1階から開始。
                #
                # 通常HP / MPとは別に、
                # 闘技場専用HP / MPを最大値で初期化する。
                # ================================================

                arena_floor = ArenaFloor.objects.get(
                    floor=1,
                )

                ArenaState.objects.create(
                    character=character,
                    floor=arena_floor,
                    current_hp=character.max_hp,
                    current_mp=character.max_mp,
                )

            if signup_bonus:
                messages.success(
                    request,
                    f"初回登録特典として{signup_bonus}Qを獲得しました！",
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
    # パッシブ詳細画面
@login_required
def passive_detail_view(request):

    return render(
        request,
        "passive_detail.html",
    )
# キャラクター画像変更
@login_required
def character_image_change_view(request):

    CHARACTER_IMAGE_CHANGE_COST = 50

    character = getattr(
        request.user,
        "character",
        None,
    )

    if character is None:
        return redirect(
            "accounts:character_create"
        )

    available_characters = (
        get_available_character_images()
    )

    available_numbers = {
        item["number"]
        for item in available_characters
    }


    # ========================================
    # キャラクター画像変更
    # ========================================

    if request.method == "POST":

        character_image_id = request.POST.get(
            "character_image_id"
        )

        try:
            character_image_id = int(
                character_image_id
            )

        except (TypeError, ValueError):
            character_image_id = None


        # ========================================
        # 存在しない画像
        # ========================================

        if (
            character_image_id
            not in available_numbers
        ):

            messages.error(
                request,
                "存在するキャラクター画像を選択してください。",
            )

            return redirect(
                "accounts:character_image_change"
            )


        # ========================================
        # DB更新
        # ========================================

        with transaction.atomic():

            # 二重クリック・同時送信対策
            character = (
                Character.objects
                .select_for_update()
                .get(pk=character.pk)
            )


            # ====================================
            # 現在と同じ画像
            # ====================================

            if (
                character.character_image_id
                == character_image_id
            ):

                messages.info(
                    request,
                    "現在使用しているキャラクター画像です。",
                )

                return redirect(
                    "accounts:character_image_change"
                )


            # ====================================
            # Q不足
            # ====================================

            if (
                character.gold
                < CHARACTER_IMAGE_CHANGE_COST
            ):

                messages.error(
                    request,
                    "キャラクター画像の変更には50Q必要です。",
                )

                return redirect(
                    "accounts:character_image_change"
                )


            # ====================================
            # 50Q消費
            # ====================================

            character.gold -= (
                CHARACTER_IMAGE_CHANGE_COST
            )


            # ====================================
            # キャラクター画像変更
            # ====================================

            character.character_image_id = (
                character_image_id
            )


            character.save(
                update_fields=[
                    "gold",
                    "character_image_id",
                ]
            )


        messages.success(
            request,
            "キャラクター画像を変更しました。",
        )

        return redirect(
            "accounts:character_image_change"
        )


    return render(
        request,
        "character_image_change.html",
        {
            "character": character,
            "available_characters":
                available_characters,
            "character_image_change_cost":
                CHARACTER_IMAGE_CHANGE_COST,
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

    
# 手相
@login_required
def palm_view(request):
    character = getattr(
        request.user,
        "character",
        None,
    )

    if character is None:
        return redirect(
            "accounts:character_create"
        )


    # ========================================
    # 手相占い設定
    # ========================================

    PALM_READING_COST = 10
    PALM_UNLOCK_HOURS = 24

    now = timezone.now()

    palm_error = None


    # ========================================
    # 現在閲覧可能か
    # ========================================

    palm_is_unlocked = (
        character.palm_unlocked_until
        and
        character.palm_unlocked_until > now
    )


    # ========================================
    # 10Qを消費して24時間解放
    # ========================================

    if request.method == "POST":

        action = request.POST.get(
            "action"
        )


        if action == "unlock":

            with transaction.atomic():

                # 二重クリックなどで
                # Qが二重に減ることを防ぐ
                character = (
                    Character.objects
                    .select_for_update()
                    .get(pk=character.pk)
                )

                now = timezone.now()

                palm_is_unlocked = (
                    character.palm_unlocked_until
                    and
                    character.palm_unlocked_until
                    > now
                )


                # すでに閲覧可能なら
                # 再課金しない
                if palm_is_unlocked:

                    return redirect(
                        "accounts:palm"
                    )


                # Q不足
                if (
                    character.gold
                    < PALM_READING_COST
                ):

                    palm_error = (
                        "手相を見るには"
                        "10Q必要です。"
                    )


                else:

                    character.gold -= (
                        PALM_READING_COST
                    )

                    character.palm_unlocked_until = (
                        now
                        + timedelta(
                            hours=PALM_UNLOCK_HOURS
                        )
                    )

                    character.save(
                        update_fields=[
                            "gold",
                            "palm_unlocked_until",
                        ]
                    )

                    return redirect(
                        "accounts:palm"
                    )


    # ========================================
    # 最新状態で再判定
    # ========================================

    now = timezone.now()

    palm_is_unlocked = (
        character.palm_unlocked_until
        and
        character.palm_unlocked_until > now
    )


    # ========================================
    # 手相データ
    #
    # 未解放時には成長ウェイト自体を
    # テンプレートへ送らない
    # ========================================

    palm_labels = []
    palm_values = []
    palm_items = []


    if palm_is_unlocked:

        palm_labels = [
            "火",
            "水",
            "草",
            "岩",
            "光",
            "闇",
        ]

        palm_values = [
            character.fire_growth_weight,
            character.water_growth_weight,
            character.grass_growth_weight,
            character.rock_growth_weight,
            character.light_growth_weight,
            character.dark_growth_weight,
        ]

        palm_items = [
            {
                "name": "火",
                "key": "fire",
                "value":
                    character.fire_growth_weight,
            },
            {
                "name": "水",
                "key": "water",
                "value":
                    character.water_growth_weight,
            },
            {
                "name": "草",
                "key": "grass",
                "value":
                    character.grass_growth_weight,
            },
            {
                "name": "岩",
                "key": "rock",
                "value":
                    character.rock_growth_weight,
            },
            {
                "name": "光",
                "key": "light",
                "value":
                    character.light_growth_weight,
            },
            {
                "name": "闇",
                "key": "dark",
                "value":
                    character.dark_growth_weight,
            },
        ]

    # ========================================
    # 手相で使用できる属性成長アイテム
    # ========================================

    growth_seed_names = [
        "火の種",
        "水の種",
        "草の種",
        "岩の種",
        "光の種",
        "闇の種",
    ]

    palm_growth_items = (
        character.inventory_items
        .filter(
            item__name__in=growth_seed_names,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__name",
        )
    )


    return render(
        request,
        "palm.html",
        {
            "character": character,

            "palm_labels":
                palm_labels,

            "palm_values":
                palm_values,

            "palm_items":
                palm_items,

            "palm_is_unlocked":
                palm_is_unlocked,

            "palm_unlocked_until":
                character.palm_unlocked_until,

            "palm_reading_cost":
                PALM_READING_COST,

            "palm_error":
                palm_error,

            "palm_growth_items":
                palm_growth_items,
        },
    )
@login_required
def disable_debug_mode_view(request):

    if request.method != "POST":
        return redirect("home")

    disable_debug_mode(request)

    messages.success(
        request,
        "デバッグモードを解除しました。",
    )

    return redirect("home")

@login_required
def update_debug_drop_rate_view(request):

    if request.method != "POST":
        return redirect("home")

    if not is_debug_mode(request):
        messages.warning(
            request,
            "デバッグモードが有効ではありません。",
        )
        return redirect("home")

    drop_rate = request.POST.get(
        "debug_drop_rate",
        "100",
    )

    try:
        drop_rate = int(drop_rate)

    except (TypeError, ValueError):
        messages.error(
            request,
            "ドロップ率は0〜100の整数で入力してください。",
        )
        return redirect("home")

    drop_rate = set_debug_drop_rate(
        request,
        drop_rate,
    )

    messages.success(
        request,
        f"デバッグ用ドロップ率を{drop_rate}%に変更しました。",
    )

    return redirect("home")

@login_required
def debug_settings_view(request):

    if not is_debug_mode(request):
        messages.warning(
            request,
            "デバッグモードが有効ではありません。",
        )
        return redirect("home")

    if request.method == "POST":

        drop_rate = request.POST.get(
            "debug_drop_rate",
            "100",
        )

        try:
            drop_rate = int(drop_rate)

        except (TypeError, ValueError):

            messages.error(
                request,
                "ドロップ率は0〜100の整数で入力してください。",
            )

            return redirect(
                "accounts:debug_settings"
            )

        drop_rate = set_debug_drop_rate(
            request,
            drop_rate,
        )

        messages.success(
            request,
            f"ドロップ率を{drop_rate}%に変更しました。",
        )

        return redirect(
            "accounts:debug_settings"
        )

    return render(
        request,
        "debug_settings.html",
        {
            "debug_drop_rate":
                get_debug_drop_rate(request),
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