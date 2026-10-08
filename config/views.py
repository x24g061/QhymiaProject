from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.conf import settings
from apps.accounts.models import Character
from apps.sns.models import Post

import random

# ========================================
# プレイヤー検索 / 管理者コマンド入口
# ========================================
@login_required
def player_search(request):
    if request.method != "POST":
        return redirect("home")

    query = request.POST.get("query", "").strip()

    if not query:
        messages.error(
            request,
            "検索内容を入力してください。",
        )
        return redirect("home")

    # 管理者モード起動コマンド
    if query == "/admin":
        return redirect("admin_mode_login")

    # 管理者モード解除コマンド
    if query == "/adminoff":
        request.session["admin_mode"] = False

        messages.success(
            request,
            "管理者モードを解除しました。",
        )

        return redirect("home")

    # 通常のプレイヤー検索
    character = Character.objects.filter(
        name__iexact=query
    ).first()

    if character is None:
        messages.error(
            request,
            "プレイヤーが見つかりませんでした。",
        )
        return redirect("home")

    messages.success(
        request,
        (
            f"{character.name} / "
            f"Lv.{character.level} / "
            f"{character.gold}Q"
        ),
    )

    return redirect("home")


# ========================================
# 管理者モード認証
# ========================================
@login_required
def admin_mode_login(request):
    if request.method == "POST":
        password = request.POST.get(
            "password",
            "",
        )

        if password == settings.ADMIN_MODE_PASSWORD:
            request.session["admin_mode"] = True

            messages.success(
                request,
                "管理者モードを有効にしました。",
            )

            return redirect("home")

        messages.error(
            request,
            "管理者パスワードが違います。",
        )

    return render(
        request,
        "admin_mode_login.html",
    )

@login_required
def admin_panel(request):

    # 管理者モードでなければ入れない
    if not request.session.get("admin_mode"):
        messages.error(
            request,
            "管理者モードを有効にしてください。",
        )
        return redirect("home")

    # 検索文字列
    query = request.GET.get("q", "").strip()

    characters = (
        Character.objects
        .select_related("user")
        .order_by("name")
    )

    # 名前で部分一致検索
    if query:
        characters = characters.filter(
            name__icontains=query
        )

    posts = (
            Post.objects
            .select_related(
                "user",
                "user__character",
            )
            .order_by("-created_at")
        )


    return render(
    request,
    "admin_panel.html",
    {
        "characters": characters,
        "query": query,
        "posts": posts,
    },
)

    

@login_required
def admin_player_edit(request, character_id):

    # 管理者モードでなければ拒否
    if not request.session.get("admin_mode"):
        messages.error(
            request,
            "管理者モードを有効にしてください。",
        )
        return redirect("home")

    character = Character.objects.filter(
        id=character_id
    ).first()

    if character is None:
        messages.error(
            request,
            "対象プレイヤーが見つかりません。",
        )
        return redirect("admin_panel")

    if request.method == "POST":

        try:
            character.level = int(
                request.POST.get(
                    "level",
                    character.level,
                )
            )

            character.exp = int(
                request.POST.get(
                    "exp",
                    character.exp,
                )
            )

            character.gold = int(
                request.POST.get(
                    "gold",
                    character.gold,
                )
            )

            character.max_hp = int(
                request.POST.get(
                    "max_hp",
                    character.max_hp,
                )
            )

            character.current_hp = min(
                character.current_hp,
                character.max_hp,
            )

            character.max_mp = int(
                request.POST.get(
                    "max_mp",
                    character.max_mp,
                )
            )

            character.current_mp = min(
                character.current_mp,
                character.max_mp,
            )

            character.strength = int(
                request.POST.get(
                    "strength",
                    character.strength,
                )
            )

            character.intelligence = int(
                request.POST.get(
                    "intelligence",
                    character.intelligence,
                )
            )

            character.dexterity = int(
                request.POST.get(
                    "dexterity",
                    character.dexterity,
                )
            )

            character.agility = int(
                request.POST.get(
                    "agility",
                    character.agility,
                )
            )

            character.vitality = int(
                request.POST.get(
                    "vitality",
                    character.vitality,
                )
            )

            character.luck = int(
                request.POST.get(
                    "luck",
                    character.luck,
                )
            )

            character.save()

            messages.success(
                request,
                f"{character.name}の情報を更新しました。",
            )

            return redirect("admin_panel")

        except ValueError:
            messages.error(
                request,
                "数値項目には数字を入力してください。",
            )

    return render(
        request,
        "admin_player_edit.html",
        {
            "character": character,
        },
    )

@login_required
def admin_mode_logout(request):

    if request.method != "POST":
        return redirect("admin_panel")

    request.session["admin_mode"] = False

    messages.success(
        request,
        "管理者モードを解除しました。",
    )

    return redirect("home")

@login_required
def home(request):
    character = Character.objects.filter(
        user=request.user
    ).first()

    previous_arena_character = None
    next_arena_character = None

    main_attribute_name = "-"
    main_attribute_value = 0

    # 装備戦闘力
    equipment_battle_power = 0

    # 総合戦闘力
    battle_power = 0

    exploration_cooldown_remaining = 0
    exploration_cooldown_reduced = False

    arena_max_floor = 100

    previous_arena_character = None
    next_arena_character = None
    equipment_battle_power = 0
    if character:

        # ========================================
        # 闘技場：前の階の相手を取得
        # ========================================

        if character.arena_floor > 1:

            previous_arena_character = (
                Character.objects
                .filter(
                    arena_floor=(
                        character.arena_floor - 1
                    )
                )
                .exclude(
                    id=character.id
                )
                .first()
            )


        # ========================================
        # 闘技場：次の階の相手を取得
        # ========================================

        if character.arena_floor < arena_max_floor:

            next_arena_character = (
                Character.objects
                .filter(
                    arena_floor=(
                        character.arena_floor + 1
                    )
                )
                .exclude(
                    id=character.id
                )
                .first()
            )


        # ========================================
        # 得意属性
        # ========================================

        main_attribute_name = (
            character.get_main_attribute_display()
        )

        main_attribute_value = max(
            character.fire,
            character.water,
            character.grass,
            character.rock,
            character.light,
            character.dark,
        )


        # ========================================
        # 装備戦闘力
        # ========================================

        equipment_battle_power = sum(
            owned.battle_power
            for owned
            in character.owned_equipments.filter(
                is_equipped=True
            )
        )


        # ========================================
        # 総合戦闘力
        # ========================================

        battle_power = (
            character.max_hp
            + character.max_mp
            + character.strength
            + character.intelligence
            + character.dexterity
            + character.agility
            + character.vitality
            + character.luck
            + main_attribute_value
            + equipment_battle_power
        )


        # ========================================
        # 探索CT
        # ========================================

        exploration_cooldown_remaining = (
            character
            .get_exploration_cooldown_remaining()
        )

        exploration_cooldown_reduced = (
            character
            .is_exploration_cooldown_reduced()
        )


    context = {
        "character": character,

        "main_attribute_name":
            main_attribute_name,

        "main_attribute_value":
            main_attribute_value,

        "battle_power":
            battle_power,

        "exploration_cooldown_remaining":
            exploration_cooldown_remaining,

        "exploration_cooldown_reduced":
            exploration_cooldown_reduced,

        "arena_max_floor":
            arena_max_floor,

        "previous_arena_character":
            previous_arena_character,

        "next_arena_character":
            next_arena_character,
    }

    return render(
        request,
        "home.html",
        context,
    )

    

def generate_reincarnation_bonus(character):
    total_points = (character.reincarnation_count + 1) * 125

    stat_names = [
        "max_hp",
        "max_mp",
        "strength",
        "intelligence",
        "dexterity",
        "agility",
        "vitality",
        "luck",
        "fire",
        "water",
        "grass",
        "rock",
        "light",
        "dark",
    ]

    bonus_points = {stat: 0 for stat in stat_names}

    for _ in range(total_points):
        selected_stat = random.choice(stat_names)
        bonus_points[selected_stat] += 1

    return bonus_points

def calculate_reincarnation_stats(bonus_points):
    return {
        "max_hp": 30 + bonus_points["max_hp"] * 5,
        "max_mp": 10 + bonus_points["max_mp"] * 2,

        "strength": 5 + bonus_points["strength"],
        "intelligence": 5 + bonus_points["intelligence"],
        "dexterity": 5 + bonus_points["dexterity"],
        "agility": 5 + bonus_points["agility"],
        "vitality": 5 + bonus_points["vitality"],
        "luck": 5 + bonus_points["luck"],

        "fire": bonus_points["fire"],
        "water": bonus_points["water"],
        "grass": bonus_points["grass"],
        "rock": bonus_points["rock"],
        "light": bonus_points["light"],
        "dark": bonus_points["dark"],
    }

@login_required
def again(request):
    character = Character.objects.filter(user=request.user).first()

    can_reincarnate = False
    total_points = 0
    bonus_points = None
    reincarnation_stats = None

    if character and character.level >= 100:
        can_reincarnate = True
        total_points = (character.reincarnation_count + 1) * 125

        # POST = 回帰確定
        if request.method == "POST":
            bonus_points = request.session.get("reincarnation_bonus_points")

            if bonus_points:
                reincarnation_stats = calculate_reincarnation_stats(
                    bonus_points
                )

                # 回帰後の基礎ステータスを保存
                character.max_hp = reincarnation_stats["max_hp"]
                character.current_hp = reincarnation_stats["max_hp"]

                character.max_mp = reincarnation_stats["max_mp"]
                character.current_mp = reincarnation_stats["max_mp"]

                character.strength = reincarnation_stats["strength"]
                character.intelligence = reincarnation_stats["intelligence"]
                character.dexterity = reincarnation_stats["dexterity"]
                character.agility = reincarnation_stats["agility"]
                character.vitality = reincarnation_stats["vitality"]
                character.luck = reincarnation_stats["luck"]

                character.fire = reincarnation_stats["fire"]
                character.water = reincarnation_stats["water"]
                character.grass = reincarnation_stats["grass"]
                character.rock = reincarnation_stats["rock"]
                character.light = reincarnation_stats["light"]
                character.dark = reincarnation_stats["dark"]

                # 回帰処理
                character.level = 1
                character.exp = 0
                character.reincarnation_count += 1

                character.save()

                # 使用済み抽選結果を削除
                request.session.pop(
                    "reincarnation_bonus_points",
                    None,
                )

                # 回帰成功メッセージを表示
                messages.success(
                    request,
                    f"回帰が完了しました！回帰回数：{character.reincarnation_count}回",
                )

                return redirect("home")

        # GET = 回帰結果のプレビュー
        bonus_points = request.session.get(
            "reincarnation_bonus_points"
        )

        # まだ抽選していない場合だけ新しく生成
        if bonus_points is None:
            bonus_points = generate_reincarnation_bonus(character)

            request.session["reincarnation_bonus_points"] = (
                bonus_points
            )

        reincarnation_stats = calculate_reincarnation_stats(
            bonus_points
        )

    else:
        # Lv100未満なら古い抽選結果を消す
        request.session.pop(
            "reincarnation_bonus_points",
            None,
        )

    context = {
        "character": character,
        "can_reincarnate": can_reincarnate,
        "total_points": total_points,
        "bonus_points": bonus_points,
        "reincarnation_stats": reincarnation_stats,
    }

    return render(request, "again.html", context)