from django.db import migrations


ACHIEVEMENTS = [
    # ========================================
    # 回帰・成長
    # ========================================
    ("level_100", "成長の証", "growth", "F", "level", 100, "Lv.100に到達する"),

    ("reincarnation_1", "輪廻の始まり", "growth", "F", "reincarnation", 1, "初めて回帰する"),
    ("reincarnation_10", "幾度目の人生", "growth", "E", "reincarnation", 10, "回帰10回に到達する"),
    ("reincarnation_30", "輪廻の旅人", "growth", "D", "reincarnation", 30, "回帰30回に到達する"),
    ("reincarnation_50", "転生の超越者", "growth", "C", "reincarnation", 50, "回帰50回に到達する"),
    ("reincarnation_100", "百世の記憶", "growth", "B", "reincarnation", 100, "回帰100回に到達する"),
    ("reincarnation_150", "輪廻の支配者", "growth", "A", "reincarnation", 150, "回帰150回に到達する"),
    ("reincarnation_300", "永劫を歩む者", "growth", "S", "reincarnation", 300, "回帰300回に到達する"),
    ("reincarnation_500", "神域の到達者", "growth", "S", "reincarnation", 500, "回帰500回に到達する"),
    ("reincarnation_1000", "永遠の観測者", "growth", "S", "reincarnation", 1000, "回帰1000回に到達する"),

    # ========================================
    # ボス討伐
    # ========================================
    ("boss_1", "最初の試練", "exploration", "F", "boss_defeated", 1, "キングスライムを討伐する"),
    ("boss_2", "獣王を討つ者", "exploration", "F", "boss_defeated", 2, "グレートウルフを討伐する"),
    ("boss_3", "巨岩の破壊者", "exploration", "E", "boss_defeated", 3, "グランドゴーレムを討伐する"),
    ("boss_4", "竜を狩る者", "exploration", "E", "boss_defeated", 4, "ケイブドラゴンを討伐する"),
    ("boss_5", "業火を越えし者", "exploration", "D", "boss_defeated", 5, "イフリートを討伐する"),
    ("boss_6", "深海の征服者", "exploration", "C", "boss_defeated", 6, "リヴァイアサンを討伐する"),
    ("boss_7", "翠緑の解放者", "exploration", "C", "boss_defeated", 7, "アルラウネを討伐する"),
    ("boss_8", "巨神を砕く者", "exploration", "B", "boss_defeated", 8, "タイタンを討伐する"),
    ("boss_9", "焔帝を超えし者", "exploration", "B", "boss_defeated", 9, "イグニスを討伐する"),
    ("boss_10", "深淵の征服者", "exploration", "A", "boss_defeated", 10, "アビスデーモンを討伐する"),
    ("boss_11", "天界を越えし者", "exploration", "A", "boss_defeated", 11, "セレスティアを討伐する"),
    ("boss_12", "終焉を越えし者", "exploration", "S", "boss_defeated", 12, "アポカリプスを討伐する"),

    # ========================================
    # 探索
    # ========================================
    ("explore_1", "駆け出しの冒険者", "exploration", "F", "exploration_count", 1, "探索を1回行う"),
    ("explore_100", "探索者", "exploration", "E", "exploration_count", 100, "累計探索100回"),
    ("explore_1000", "熟練の冒険者", "exploration", "C", "exploration_count", 1000, "累計探索1000回"),
    ("explore_10000", "未知を踏破する者", "exploration", "A", "exploration_count", 10000, "累計探索10000回"),

    # ========================================
    # 闘技場
    # ========================================
    ("arena_win_1", "闘士", "arena", "F", "arena_wins", 1, "闘技場で初勝利する"),
    ("arena_win_100", "歴戦の闘士", "arena", "C", "arena_wins", 100, "闘技場で累計100勝する"),
    ("arena_win_1000", "闘技場の伝説", "arena", "S", "arena_wins", 1000, "闘技場で累計1000勝する"),
    ("arena_streak_5", "連戦の猛者", "arena", "E", "arena_win_streak", 5, "闘技場で5連勝する"),
    ("arena_streak_10", "無敗の剣", "arena", "C", "arena_win_streak", 10, "闘技場で10連勝する"),
    ("arena_streak_30", "戦場の支配者", "arena", "A", "arena_win_streak", 30, "闘技場で30連勝する"),
    ("arena_streak_50", "戦神", "arena", "S", "arena_win_streak", 50, "闘技場で50連勝する"),

    # ========================================
    # 装備強化
    # ========================================
    ("equipment_5", "熟練の職人", "equipment", "D", "enhancement_level", 5, "+5以上の装備を獲得する"),
    ("equipment_10", "神匠", "equipment", "A", "enhancement_level", 10, "+10以上の装備を獲得する"),
    ("equipment_15", "神器の創造者", "equipment", "S", "enhancement_level", 15, "+15以上の装備を獲得する"),
    ("equipment_20", "神をも鍛える者", "equipment", "S", "enhancement_level", 20, "+20以上の装備を獲得する"),
]


def seed_achievements(apps, schema_editor):
    Achievement = apps.get_model("achievements", "Achievement")

    for order, data in enumerate(ACHIEVEMENTS, start=1):
        code, title, category, rank, condition, target, description = data

        Achievement.objects.using(
            schema_editor.connection.alias
        ).get_or_create(
            code=code,
            defaults={
                "name": title,
                "title_name": title,
                "category": category,
                "rank": rank,
                "condition_type": condition,
                "target_value": target,
                "description": description,
                "display_order": order,
                "is_hidden": False,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("achievements", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_achievements,
            migrations.RunPython.noop,
        ),
    ]
