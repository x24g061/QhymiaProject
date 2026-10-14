from django.db import migrations


def double_boss_hp(
    apps,
    schema_editor,
):
    """
    1～12階のボスHPを2倍にする。

    他の能力値や通常敵には影響させない。
    """

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    bosses = Enemy.objects.filter(
        is_boss=True,
        floor__gte=1,
        floor__lte=12,
    )

    for boss in bosses:
        boss.max_hp *= 2

        boss.save(
            update_fields=[
                "max_hp",
            ]
        )


def restore_boss_hp(
    apps,
    schema_editor,
):
    """
    migrationを戻した場合、
    ボスHPを元の値へ戻す。
    """

    Enemy = apps.get_model(
        "battle",
        "Enemy",
    )

    bosses = Enemy.objects.filter(
        is_boss=True,
        floor__gte=1,
        floor__lte=12,
    )

    for boss in bosses:
        boss.max_hp //= 2

        boss.save(
            update_fields=[
                "max_hp",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "battle",
            "0009_add_floor_bosses",
        ),
    ]

    operations = [
        migrations.RunPython(
            double_boss_hp,
            restore_boss_hp,
        ),
    ]