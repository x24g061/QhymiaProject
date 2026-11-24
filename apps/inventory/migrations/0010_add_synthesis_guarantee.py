from django.db import migrations


def create_guarantee_item(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")

    Item.objects.using(
        schema_editor.connection.alias
    ).update_or_create(
        name="合成成功保証書",
        defaults={
            "description": (
                "装備合成時に使用すると、"
                "必ず通常成功（+1）になる。"
                "合成1回につき1個消費する。"
            ),
            "category": "system",
            "is_usable": False,
            "npc_purchasable": False,
            "npc_sellable": False,
            "market_sellable": False,
            "buy_price": 0,
            "sell_price": 0,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_add_boss_challenge_ticket"),
    ]

    operations = [
        migrations.RunPython(
            create_guarantee_item,
            migrations.RunPython.noop,
        ),
    ]
