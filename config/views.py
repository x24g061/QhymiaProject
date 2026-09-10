from django.shortcuts import render
from apps.accounts.models import Character
import random

def home(request):
    return render(request, 'home.html')

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

def again(request):
    character = Character.objects.filter(user=request.user).first()

    can_reincarnate = False
    bonus_points = None
    reincarnation_stats = None
    total_points = 0

    if character and character.level >= 100:
        can_reincarnate = True

        # 今回の転生で使用する総ポイント
        total_points = (character.reincarnation_count + 1) * 125

        # 14種類へランダム配分
        bonus_points = generate_reincarnation_bonus(character)

        # 配分ポイントから実際の能力値を計算
        reincarnation_stats = calculate_reincarnation_stats(
            bonus_points
        )

    context = {
        "character": character,
        "can_reincarnate": can_reincarnate,
        "total_points": total_points,
        "bonus_points": bonus_points,
        "reincarnation_stats": reincarnation_stats,
    }

    return render(request, "again.html", context)