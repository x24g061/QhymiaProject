from django.db import migrations


def add_floor_4_to_12_enemies(
    apps,
    schema_editor,
):
    """
    4～12階に出現する通常敵を登録する。

    各階層3種類ずつ、
    合計27種類の通常敵を追加する。
    """

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    enemies = [

        # ========================================================
        # 4階：洞窟
        # ========================================================

        {
            "name": "ケイブバット",
            "floor": 4,
            "max_hp": 48,
            "max_mp": 0,
            "strength": 8,
            "intelligence": 3,
            "dexterity": 10,
            "agility": 11,
            "vitality": 4,
            "luck": 7,
            "attribute": "dark",
        },
        {
            "name": "ストーンリザード",
            "floor": 4,
            "max_hp": 62,
            "max_mp": 0,
            "strength": 10,
            "intelligence": 3,
            "dexterity": 6,
            "agility": 5,
            "vitality": 11,
            "luck": 4,
            "attribute": "rock",
        },
        {
            "name": "ケイブゴブリン",
            "floor": 4,
            "max_hp": 55,
            "max_mp": 0,
            "strength": 10,
            "intelligence": 4,
            "dexterity": 8,
            "agility": 7,
            "vitality": 8,
            "luck": 5,
            "attribute": "neutral",
        },

        # ========================================================
        # 5階：火山
        # ========================================================

        {
            "name": "フレイムスライム",
            "floor": 5,
            "max_hp": 66,
            "max_mp": 0,
            "strength": 9,
            "intelligence": 8,
            "dexterity": 6,
            "agility": 6,
            "vitality": 10,
            "luck": 5,
            "attribute": "fire",
        },
        {
            "name": "サラマンダー",
            "floor": 5,
            "max_hp": 72,
            "max_mp": 0,
            "strength": 11,
            "intelligence": 7,
            "dexterity": 9,
            "agility": 10,
            "vitality": 9,
            "luck": 6,
            "attribute": "fire",
        },
        {
            "name": "ファイアオーク",
            "floor": 5,
            "max_hp": 80,
            "max_mp": 0,
            "strength": 13,
            "intelligence": 4,
            "dexterity": 7,
            "agility": 6,
            "vitality": 12,
            "luck": 5,
            "attribute": "fire",
        },

        # ========================================================
        # 6階：湖沼
        # ========================================================

        {
            "name": "アクアスライム",
            "floor": 6,
            "max_hp": 78,
            "max_mp": 0,
            "strength": 9,
            "intelligence": 10,
            "dexterity": 7,
            "agility": 7,
            "vitality": 12,
            "luck": 6,
            "attribute": "water",
        },
        {
            "name": "リザードマン",
            "floor": 6,
            "max_hp": 84,
            "max_mp": 0,
            "strength": 13,
            "intelligence": 6,
            "dexterity": 10,
            "agility": 9,
            "vitality": 11,
            "luck": 6,
            "attribute": "water",
        },
        {
            "name": "マッドクラブ",
            "floor": 6,
            "max_hp": 95,
            "max_mp": 0,
            "strength": 11,
            "intelligence": 4,
            "dexterity": 6,
            "agility": 5,
            "vitality": 15,
            "luck": 4,
            "attribute": "water",
        },

        # ========================================================
        # 7階：密林
        # ========================================================

        {
            "name": "ポイズンフロッグ",
            "floor": 7,
            "max_hp": 82,
            "max_mp": 10,
            "strength": 10,
            "intelligence": 11,
            "dexterity": 10,
            "agility": 12,
            "vitality": 8,
            "luck": 8,
            "attribute": "dark",
        },
        {
            "name": "ジャングルハンター",
            "floor": 7,
            "max_hp": 88,
            "max_mp": 0,
            "strength": 14,
            "intelligence": 6,
            "dexterity": 13,
            "agility": 12,
            "vitality": 9,
            "luck": 8,
            "attribute": "grass",
        },
        {
            "name": "マンドラゴラ",
            "floor": 7,
            "max_hp": 100,
            "max_mp": 15,
            "strength": 10,
            "intelligence": 13,
            "dexterity": 8,
            "agility": 7,
            "vitality": 14,
            "luck": 7,
            "attribute": "grass",
        },

        # ========================================================
        # 8階：雪原
        # ========================================================

        {
            "name": "アイスウルフ",
            "floor": 8,
            "max_hp": 96,
            "max_mp": 0,
            "strength": 15,
            "intelligence": 6,
            "dexterity": 13,
            "agility": 15,
            "vitality": 10,
            "luck": 9,
            "attribute": "water",
        },
        {
            "name": "スノーゴーレム",
            "floor": 8,
            "max_hp": 120,
            "max_mp": 0,
            "strength": 14,
            "intelligence": 5,
            "dexterity": 7,
            "agility": 5,
            "vitality": 18,
            "luck": 5,
            "attribute": "rock",
        },
        {
            "name": "フロストメイジ",
            "floor": 8,
            "max_hp": 88,
            "max_mp": 25,
            "strength": 8,
            "intelligence": 17,
            "dexterity": 12,
            "agility": 11,
            "vitality": 9,
            "luck": 10,
            "attribute": "water",
        },

        # ========================================================
        # 9階：古代遺跡
        # ========================================================

        {
            "name": "エンシェントガーディアン",
            "floor": 9,
            "max_hp": 130,
            "max_mp": 0,
            "strength": 16,
            "intelligence": 8,
            "dexterity": 9,
            "agility": 8,
            "vitality": 19,
            "luck": 6,
            "attribute": "rock",
        },
        {
            "name": "カースドナイト",
            "floor": 9,
            "max_hp": 118,
            "max_mp": 10,
            "strength": 18,
            "intelligence": 8,
            "dexterity": 13,
            "agility": 12,
            "vitality": 16,
            "luck": 9,
            "attribute": "dark",
        },
        {
            "name": "古代魔導兵",
            "floor": 9,
            "max_hp": 105,
            "max_mp": 30,
            "strength": 10,
            "intelligence": 18,
            "dexterity": 14,
            "agility": 12,
            "vitality": 12,
            "luck": 10,
            "attribute": "light",
        },

        # ========================================================
        # 10階：闇の森
        # ========================================================

        {
            "name": "ダークウルフ",
            "floor": 10,
            "max_hp": 115,
            "max_mp": 0,
            "strength": 19,
            "intelligence": 7,
            "dexterity": 15,
            "agility": 18,
            "vitality": 12,
            "luck": 11,
            "attribute": "dark",
        },
        {
            "name": "ナイトメア",
            "floor": 10,
            "max_hp": 125,
            "max_mp": 20,
            "strength": 17,
            "intelligence": 17,
            "dexterity": 14,
            "agility": 16,
            "vitality": 13,
            "luck": 13,
            "attribute": "dark",
        },
        {
            "name": "デモンメイジ",
            "floor": 10,
            "max_hp": 110,
            "max_mp": 35,
            "strength": 9,
            "intelligence": 21,
            "dexterity": 14,
            "agility": 13,
            "vitality": 11,
            "luck": 12,
            "attribute": "dark",
        },

        # ========================================================
        # 11階：天空
        # ========================================================

        {
            "name": "ウィンドハーピー",
            "floor": 11,
            "max_hp": 120,
            "max_mp": 10,
            "strength": 18,
            "intelligence": 10,
            "dexterity": 18,
            "agility": 21,
            "vitality": 12,
            "luck": 13,
            "attribute": "light",
        },
        {
            "name": "ライトガーディアン",
            "floor": 11,
            "max_hp": 150,
            "max_mp": 15,
            "strength": 20,
            "intelligence": 13,
            "dexterity": 13,
            "agility": 11,
            "vitality": 22,
            "luck": 9,
            "attribute": "light",
        },
        {
            "name": "スカイドラゴン",
            "floor": 11,
            "max_hp": 145,
            "max_mp": 20,
            "strength": 22,
            "intelligence": 15,
            "dexterity": 16,
            "agility": 17,
            "vitality": 18,
            "luck": 12,
            "attribute": "light",
        },

        # ========================================================
        # 12階：終焉
        # ========================================================

        {
            "name": "アビスナイト",
            "floor": 12,
            "max_hp": 160,
            "max_mp": 15,
            "strength": 24,
            "intelligence": 12,
            "dexterity": 17,
            "agility": 16,
            "vitality": 22,
            "luck": 12,
            "attribute": "dark",
        },
        {
            "name": "カオスビースト",
            "floor": 12,
            "max_hp": 175,
            "max_mp": 0,
            "strength": 26,
            "intelligence": 10,
            "dexterity": 15,
            "agility": 18,
            "vitality": 23,
            "luck": 14,
            "attribute": "neutral",
        },
        {
            "name": "ヴォイドメイジ",
            "floor": 12,
            "max_hp": 145,
            "max_mp": 40,
            "strength": 10,
            "intelligence": 27,
            "dexterity": 18,
            "agility": 17,
            "vitality": 15,
            "luck": 16,
            "attribute": "dark",
        },
    ]

    for enemy_data in enemies:

        name = enemy_data["name"]
        floor = enemy_data["floor"]

        defaults = {
            key: value
            for key, value
            in enemy_data.items()
            if key not in (
                "name",
                "floor",
            )
        }

        # 今回追加するのはすべて通常敵
        defaults["is_boss"] = False

        # 現在のBattleEngineの
        # 階層EXP帯に合わせる
        if floor <= 4:
            defaults["exp_min"] = 7
            defaults["exp_max"] = 12

        elif floor <= 8:
            defaults["exp_min"] = 8
            defaults["exp_max"] = 14

        else:
            defaults["exp_min"] = 10
            defaults["exp_max"] = 16

        Enemy.objects.update_or_create(
            name=name,
            floor=floor,
            defaults=defaults,
        )


def remove_floor_4_to_12_enemies(
    apps,
    schema_editor,
):
    """
    migrationを戻した場合、
    今回追加した通常敵だけ削除する。
    """

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    enemy_names = [
        "ケイブバット",
        "ストーンリザード",
        "ケイブゴブリン",
        "フレイムスライム",
        "サラマンダー",
        "ファイアオーク",
        "アクアスライム",
        "リザードマン",
        "マッドクラブ",
        "ポイズンフロッグ",
        "ジャングルハンター",
        "マンドラゴラ",
        "アイスウルフ",
        "スノーゴーレム",
        "フロストメイジ",
        "エンシェントガーディアン",
        "カースドナイト",
        "古代魔導兵",
        "ダークウルフ",
        "ナイトメア",
        "デモンメイジ",
        "ウィンドハーピー",
        "ライトガーディアン",
        "スカイドラゴン",
        "アビスナイト",
        "カオスビースト",
        "ヴォイドメイジ",
    ]

    Enemy.objects.filter(
        name__in=enemy_names,
        floor__gte=4,
        floor__lte=12,
        is_boss=False,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "battle",
            "0007_floorprogress",
        ),
    ]

    operations = [
        migrations.RunPython(
            add_floor_4_to_12_enemies,
            remove_floor_4_to_12_enemies,
        ),
    ]