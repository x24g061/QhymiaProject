from django.db import migrations, models


def preserve_legacy_points(apps, schema_editor):
    Character = apps.get_model("accounts", "Character")
    # 履歴の逆算や能力値の再計算をせず、移行時の旧125ポイント分を保持。
    Character.objects.using(schema_editor.connection.alias).filter(
        reincarnation_count__gt=150,
    ).update(legacy_reincarnation_points=(models.F("reincarnation_count") - 150) * 25)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0022_character_next_exploration_boss_guaranteed")]

    operations = [
        migrations.AddField(
            model_name="character",
            name="legacy_reincarnation_points",
            field=models.PositiveBigIntegerField(
                default=0, editable=False,
                help_text="成長Ver.2移行前に取得済みの初期配分差分。以後の回帰でも保持する。",
            ),
        ),
        migrations.RunPython(preserve_legacy_points, migrations.RunPython.noop),
    ]
