from django.db import migrations


ACHIEVEMENTS = [
    ("synthesis_10", "見習い錬成師", "装備を累計10回合成する。", "equipment", "F", "synthesis_count", 10),
    ("synthesis_100", "錬成の探求者", "装備を累計100回合成する。", "equipment", "E", "synthesis_count", 100),
    ("synthesis_1000", "大錬成師", "装備を累計1000回合成する。", "equipment", "C", "synthesis_count", 1000),
    ("synthesis_10000", "万物を紡ぐ者", "装備を累計10000回合成する。", "equipment", "S", "synthesis_count", 10000),
    ("synthesis_super_1", "奇跡の一手", "合成で超大成功を1回達成する。", "equipment", "D", "synthesis_super", 1),
    ("synthesis_super_100", "奇跡を操る者", "合成で超大成功を100回達成する。", "equipment", "A", "synthesis_super", 100),
    ("fishing_1", "釣り人", "釣りを累計1回プレイする。", "fishing", "F", "fishing_count", 1),
    ("fishing_100", "水辺の常連", "釣りを累計100回プレイする。", "fishing", "E", "fishing_count", 100),
    ("fishing_1000", "水域の支配者", "釣りを累計1000回プレイする。", "fishing", "C", "fishing_count", 1000),
    ("fishing_10000", "深海の賢者", "釣りを累計10000回プレイする。", "fishing", "S", "fishing_count", 10000),
]


def seed_achievements(apps, schema_editor):

    Achievement = apps.get_model(
        "achievements",
        "Achievement",
    )

    db = schema_editor.connection.alias

    for index, row in enumerate(ACHIEVEMENTS, start=1):

        code, title, description, category, rank, condition, target = row

        Achievement.objects.using(db).get_or_create(
            code=code,
            defaults={
                "name": title,
                "title_name": title,
                "description": description,
                "category": category,
                "rank": rank,
                "condition_type": condition,
                "target_value": target,
                "display_order": 1000 + index,
                "is_active": True,
                "is_hidden": False,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("achievements", "0003_achievementstats_exploration_initialized"),
    ]

    operations = [
        migrations.RunPython(
            seed_achievements,
            migrations.RunPython.noop,
        ),
    ]
