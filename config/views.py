from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.accounts.models import Character

import random

@login_required
def home(request):
    character = Character.objects.filter(
        user=request.user
    ).first()

    main_attribute_name = "-"
    main_attribute_value = 0
    battle_power = 0

    if character:
        attributes = {
            "火": character.fire,
            "水": character.water,
            "草": character.grass,
            "岩": character.rock,
            "光": character.light,
            "闇": character.dark,
        }

        main_attribute_name = max(
            attributes,
            key=attributes.get
        )

        main_attribute_value = attributes[
            main_attribute_name
        ]

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
        )

    context = {
        "character": character,
        "main_attribute_name": main_attribute_name,
        "main_attribute_value": main_attribute_value,
        "battle_power": battle_power,
    }

    return render(request, "home.html", context)

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