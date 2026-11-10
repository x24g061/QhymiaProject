from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("battle", "0015_arenabattlehistory_drop_result")]
    operations = [
        migrations.AddField(
            model_name="arenabattlehistory",
            name="battle_timeline",
            field=models.JSONField(default=list, blank=True),
        ),
    ]
