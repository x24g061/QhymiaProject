from django.db import migrations


def add_initial_enemies(apps, schema_editor):
    """
    1～3階に出現する通常敵を登録する。

    データマイグレーションにしておくことで、
    別PCでも migrate を実行すれば
    同じ敵データを登録できる。
    """

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    enemies = [
        # ========================================================
        # 1階
        # ========================================================
        {
            "name": "草原スライム",
            "floor": 1,
            "max_hp": 30,
            "max_mp": 0,
            "strength": 5,
            "intelligence": 3,
            "dexterity": 4,
            "agility": 4,
            "vitality": 4,
            "luck": 3,
            "attribute": "grass",
        },
        {
            "name": "ワイルドラット",
            "floor": 1,
            "max_hp": 24,
            "max_mp": 0,
            "strength": 5,
            "intelligence": 2,
            "dexterity": 6,
            "agility": 7,
            "vitality": 3,
            "luck": 4,
            "attribute": "neutral",
        },
        {
            "name": "ゴブリンチビ兵",
            "floor": 1,
            "max_hp": 32,
            "max_mp": 0,
            "strength": 6,
            "intelligence": 3,
            "dexterity": 5,
            "agility": 4,
            "vitality": 5,
            "luck": 3,
            "attribute": "neutral",
        },

        # ========================================================
        # 2階
        # ========================================================
        {
            "name": "フォレストウルフ",
            "floor": 2,
            "max_hp": 36,
            "max_mp": 0,
            "strength": 7,
            "intelligence": 3,
            "dexterity": 7,
            "agility": 8,
            "vitality": 4,
            "luck": 5,
            "attribute": "grass",
        },
        {
            "name": "ポイズンスライム",
            "floor": 2,
            "max_hp": 42,
            "max_mp": 0,
            "strength": 5,
            "intelligence": 5,
            "dexterity": 5,
            "agility": 4,
            "vitality": 7,
            "luck": 4,
            "attribute": "dark",
        },
        {
            "name": "ゴブリンファイター",
            "floor": 2,
            "max_hp": 40,
            "max_mp": 0,
            "strength": 8,
            "intelligence": 3,
            "dexterity": 6,
            "agility": 5,
            "vitality": 7,
            "luck": 4,
            "attribute": "fire",
        },

        # ========================================================
        # 3階
        # ========================================================
        {
            "name": "ロックゴーレム",
            "floor": 3,
            "max_hp": 58,
            "max_mp": 0,
            "strength": 8,
            "intelligence": 3,
            "dexterity": 4,
            "agility": 3,
            "vitality": 10,
            "luck": 2,
            "attribute": "rock",
        },
        {
            "name": "森の呪術師",
            "floor": 3,
            "max_hp": 42,
            "max_mp": 15,
            "strength": 5,
            "intelligence": 10,
            "dexterity": 7,
            "agility": 6,
            "vitality": 5,
            "luck": 6,
            "attribute": "dark",
        },
        {
            "name": "シャドウウルフ",
            "floor": 3,
            "max_hp": 46,
            "max_mp": 0,
            "strength": 9,
            "intelligence": 3,
            "dexterity": 9,
            "agility": 10,
            "vitality": 5,
            "luck": 7,
            "attribute": "dark",
        },
    ]

    for enemy_data in enemies:

        name = enemy_data["name"]
        floor = enemy_data["floor"]

        # name と floor は検索用なので
        # defaultsから除外する
        defaults = {
            key: value
            for key, value in enemy_data.items()
            if key not in (
                "name",
                "floor",
            )
        }

        # 通常敵
        defaults["is_boss"] = False

        # 1～3階は現在すべて
        # 1戦につき7～12EXP
        defaults["exp_min"] = 7
        defaults["exp_max"] = 12

        Enemy.objects.update_or_create(
            name=name,
            floor=floor,
            defaults=defaults,
        )


def remove_initial_enemies(
    apps,
    schema_editor,
):
    """
    このマイグレーションを戻した場合、
    今回追加した敵だけ削除する。
    """

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    enemy_names = [
        "草原スライム",
        "ワイルドラット",
        "ゴブリンチビ兵",
        "フォレストウルフ",
        "ポイズンスライム",
        "ゴブリンファイター",
        "ロックゴーレム",
        "森の呪術師",
        "シャドウウルフ",
    ]

    Enemy.objects.filter(
        name__in=enemy_names,
        floor__in=[1, 2, 3],
        is_boss=False,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "battle",
            "0004_enemy_floor_enemy_is_boss",
        ),
    ]

    operations = [
        migrations.RunPython(
            add_initial_enemies,
            remove_initial_enemies,
        ),
    ]