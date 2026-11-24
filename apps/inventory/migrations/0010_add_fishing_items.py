from django.db import migrations


# ========================================
# 釣りアイテムのマスターデータ
# ========================================

FISH_ITEMS = [
    ("コモンの魚", 2),
    ("レアの魚", 5),
    ("エピックの魚", 10),
    ("レジェンドの魚", 30),
]


def create_fishing_items(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")

    db_alias = schema_editor.connection.alias

    for name, price in FISH_ITEMS:
        Item.objects.using(db_alias).update_or_create(
            name=name,
            defaults={
                "description": "釣りで獲得した魚。NPCショップで売却できる。",
                "category": "material",
                "buy_price": 0,
                "sell_price": price,
                "is_usable": False,
                "npc_purchasable": False,
                "npc_sellable": True,
                "market_sellable": False,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_add_boss_challenge_ticket"),
    ]

    operations = [
        migrations.RunPython(
            create_fishing_items,
            migrations.RunPython.noop,
        ),
    ]