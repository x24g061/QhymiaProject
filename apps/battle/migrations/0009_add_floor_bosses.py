from django.db import migrations


# ============================================================
# 各階層ボスの想定転生回数
# ============================================================

TARGET_REINCARNATIONS = {
    1: 1,
    2: 2,
    3: 4,
    4: 6,
    5: 8,
    6: 12,
    7: 50,
    8: 100,
    9: 210,
    10: 430,
    11: 650,
    12: 1000,
}


# ============================================================
# ボス情報
# ============================================================

BOSSES = {
    1: {
        "name": "キングスライム",
        "attribute": "grass",
    },
    2: {
        "name": "グレートウルフ",
        "attribute": "grass",
    },
    3: {
        "name": "グランドゴーレム",
        "attribute": "rock",
    },
    4: {
        "name": "ケイブドラゴン",
        "attribute": "neutral",
    },
    5: {
        "name": "イフリート",
        "attribute": "fire",
    },

    # ========================================================
    # 6～11階：六属性ボス
    # ========================================================

    6: {
        "name": "リヴァイアサン",
        "attribute": "water",
    },
    7: {
        "name": "アルラウネ",
        "attribute": "grass",
    },
    8: {
        "name": "タイタン",
        "attribute": "rock",
    },
    9: {
        "name": "イグニス",
        "attribute": "fire",
    },
    10: {
        "name": "アビスデーモン",
        "attribute": "dark",
    },
    11: {
        "name": "セレスティア",
        "attribute": "light",
    },

    # ========================================================
    # 最終階層
    # ========================================================

    12: {
        "name": "アポカリプス",
        "attribute": "neutral",
    },
}


# ============================================================
# 通常敵タイプ
#
# 基本はボスの約50%。
# 敵ごとの個性を出すため、
# 能力配分だけ多少変化させる。
# ============================================================

MOB_PROFILES = {

    # 平均型
    "balanced": {
        "max_hp": 50,
        "max_mp": 0,
        "strength": 50,
        "intelligence": 45,
        "dexterity": 50,
        "agility": 50,
        "vitality": 50,
        "luck": 50,
    },

    # 高速型
    "speed": {
        "max_hp": 42,
        "max_mp": 0,
        "strength": 45,
        "intelligence": 40,
        "dexterity": 60,
        "agility": 65,
        "vitality": 38,
        "luck": 55,
    },

    # 防御型
    "tank": {
        "max_hp": 60,
        "max_mp": 0,
        "strength": 50,
        "intelligence": 40,
        "dexterity": 42,
        "agility": 35,
        "vitality": 65,
        "luck": 40,
    },

    # 魔法型
    "magic": {
        "max_hp": 45,
        "max_mp": 50,
        "strength": 35,
        "intelligence": 65,
        "dexterity": 52,
        "agility": 50,
        "vitality": 42,
        "luck": 55,
    },

    # 火力型
    "power": {
        "max_hp": 55,
        "max_mp": 0,
        "strength": 65,
        "intelligence": 35,
        "dexterity": 45,
        "agility": 42,
        "vitality": 55,
        "luck": 45,
    },

    # 万能型
    "hybrid": {
        "max_hp": 50,
        "max_mp": 40,
        "strength": 50,
        "intelligence": 55,
        "dexterity": 52,
        "agility": 55,
        "vitality": 48,
        "luck": 55,
    },
}


# ============================================================
# 各通常敵にタイプを割り当てる
# ============================================================

NORMAL_ENEMIES = {

    1: [
        ("草原スライム", "tank"),
        ("ワイルドラット", "speed"),
        ("ゴブリンチビ兵", "balanced"),
    ],

    2: [
        ("フォレストウルフ", "speed"),
        ("ポイズンスライム", "tank"),
        ("ゴブリンファイター", "power"),
    ],

    3: [
        ("ロックゴーレム", "tank"),
        ("森の呪術師", "magic"),
        ("シャドウウルフ", "speed"),
    ],

    4: [
        ("ケイブバット", "speed"),
        ("ストーンリザード", "tank"),
        ("ケイブゴブリン", "balanced"),
    ],

    5: [
        ("フレイムスライム", "magic"),
        ("サラマンダー", "speed"),
        ("ファイアオーク", "power"),
    ],

    6: [
        ("アクアスライム", "tank"),
        ("リザードマン", "balanced"),
        ("マッドクラブ", "tank"),
    ],

    7: [
        ("ポイズンフロッグ", "speed"),
        ("ジャングルハンター", "speed"),
        ("マンドラゴラ", "magic"),
    ],

    8: [
        ("アイスウルフ", "speed"),
        ("スノーゴーレム", "tank"),
        ("フロストメイジ", "magic"),
    ],

    9: [
        ("エンシェントガーディアン", "tank"),
        ("カースドナイト", "power"),
        ("古代魔導兵", "magic"),
    ],

    10: [
        ("ダークウルフ", "speed"),
        ("ナイトメア", "hybrid"),
        ("デモンメイジ", "magic"),
    ],

    11: [
        ("ウィンドハーピー", "speed"),
        ("ライトガーディアン", "tank"),
        ("スカイドラゴン", "hybrid"),
    ],

    12: [
        ("アビスナイト", "power"),
        ("カオスビースト", "power"),
        ("ヴォイドメイジ", "magic"),
    ],
}


# ============================================================
# 転生回数から基準ステータスを作る
# ============================================================

def build_reincarnation_baseline(
    reincarnation_count,
):
    """
    現在の回帰仕様：

    1転生につき125ポイント。

    HP / MP
    STR / INT / DEX / AGI / VIT / LUK
    6属性

    合計14項目へランダム配分される。

    そのため、
    125 × 転生回数 ÷ 14
    を平均的な1項目あたりの
    成長ポイントとして使用する。
    """

    average_points = round(
        (
            125
            * reincarnation_count
        )
        / 14
    )

    return {

        # HPは1ポイントにつき+5
        "max_hp": (
            30
            + average_points * 5
        ),

        # MPは1ポイントにつき+2
        "max_mp": (
            10
            + average_points * 2
        ),

        # 基本ステータスは
        # 1ポイントにつき+1
        "strength": (
            5
            + average_points
        ),

        "intelligence": (
            5
            + average_points
        ),

        "dexterity": (
            5
            + average_points
        ),

        "agility": (
            5
            + average_points
        ),

        "vitality": (
            5
            + average_points
        ),

        "luck": (
            5
            + average_points
        ),
    }


# ============================================================
# 通常敵用ステータス
# ============================================================

def build_normal_enemy_stats(
    boss_stats,
    profile_name,
):
    """
    ボスステータスを基準にして、
    通常敵用ステータスを作る。

    各プロフィールはおおよそ
    ボスの50%前後。
    """

    profile = MOB_PROFILES[
        profile_name
    ]

    result = {}

    for stat_name, percentage in (
        profile.items()
    ):

        # MPを持たないタイプ
        if (
            stat_name == "max_mp"
            and percentage == 0
        ):
            result[stat_name] = 0
            continue

        value = round(
            boss_stats[stat_name]
            * percentage
            / 100
        )

        # HP・能力値は最低1
        result[stat_name] = max(
            1,
            value,
        )

    return result


# ============================================================
# EXP表示用
#
# 現在のBattleEngineでは実際のEXPは
# 階層基準で計算するため、
# ここはEnemyデータ上の値。
# ============================================================

def get_exp_range(floor):

    if floor <= 4:
        return 7, 12

    if floor <= 8:
        return 8, 14

    return 10, 16


# ============================================================
# データ登録
# ============================================================

def add_floor_bosses_and_rebalance_enemies(
    apps,
    schema_editor,
):

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    # ========================================================
    # 通常敵を各階ボスの約1/2へ調整
    # ========================================================

    for floor, enemy_list in (
        NORMAL_ENEMIES.items()
    ):

        reincarnation_count = (
            TARGET_REINCARNATIONS[
                floor
            ]
        )

        boss_stats = (
            build_reincarnation_baseline(
                reincarnation_count
            )
        )

        exp_min, exp_max = (
            get_exp_range(
                floor
            )
        )

        for (
            enemy_name,
            profile_name,
        ) in enemy_list:

            enemy_stats = (
                build_normal_enemy_stats(
                    boss_stats,
                    profile_name,
                )
            )

            Enemy.objects.filter(
                name=enemy_name,
                floor=floor,
                is_boss=False,
            ).update(
                **enemy_stats,
                exp_min=exp_min,
                exp_max=exp_max,
            )

    # ========================================================
    # ボス登録
    # ========================================================

    for floor, boss_data in (
        BOSSES.items()
    ):

        reincarnation_count = (
            TARGET_REINCARNATIONS[
                floor
            ]
        )

        boss_stats = (
            build_reincarnation_baseline(
                reincarnation_count
            )
        )

        exp_min, exp_max = (
            get_exp_range(
                floor
            )
        )

        defaults = {
            **boss_stats,

            "attribute":
                boss_data[
                    "attribute"
                ],

            "is_boss":
                True,

            # Enemyモデル上のEXP値。
            # 実際のボスEXP処理は
            # ボス戦実装時に別途行う。
            "exp_min":
                exp_min,

            "exp_max":
                exp_max,
        }

        Enemy.objects.update_or_create(
            name=boss_data["name"],
            floor=floor,
            defaults=defaults,
        )


# ============================================================
# ボスだけ削除
#
# 通常敵の再バランス値は
# このmigration以降の基準値として扱う。
# ============================================================

def remove_floor_bosses(
    apps,
    schema_editor,
):

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    boss_names = [
        data["name"]
        for data
        in BOSSES.values()
    ]

    Enemy.objects.filter(
        name__in=boss_names,
        is_boss=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "battle",
            "0008_add_floor_4_to_12_enemies",
        ),
    ]

    operations = [
        migrations.RunPython(
            add_floor_bosses_and_rebalance_enemies,
            remove_floor_bosses,
        ),
    ]