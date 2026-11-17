from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0020_adminmodeauthorizeduser"),
        ("battle", "0017_boss_balance_v1"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="permanent_skills",
            field=models.ManyToManyField(
                blank=True,
                help_text="回帰で永久習得したスキル。現在の職業に関係なく使用可能。",
                related_name="permanent_learners",
                to="battle.skill",
            ),
        ),
    ]
