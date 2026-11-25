from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_usersettings_background_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="signup_bonus_pending",
            field=models.BooleanField(
                default=False,
                editable=False,
                help_text="初回登録特典300Qの受取権利",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="signup_bonus_pending",
            field=models.BooleanField(
                default=True,
                editable=False,
                help_text="初回登録特典300Qの受取権利",
            ),
        ),
    ]
