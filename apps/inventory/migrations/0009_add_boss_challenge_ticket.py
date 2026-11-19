from django.db import migrations


# ========================================
# ボス挑戦チケットを登録
# ========================================

def create_boss_ticket(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")

    Item.objects.using(schema_editor.connection.alias).update_or_create(
        name="ボス挑戦チケット",
        defaults={
            "description": "使用すると次の探索でボスと確定遭遇する。",
            "category": "system",
            "is_usable": True,
            "npc_purchasable": False,
            "npc_sellable": False,
            "market_sellable": False,
            "buy_price": 0,
            "sell_price": 0,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0008_ownedequipment_special_effect'),
    ]

    operations = [
        migrations.RunPython(
            create_boss_ticket,
            migrations.RunPython.noop,
        ),
    ]