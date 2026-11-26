from django.db import migrations


# ========================================
# デ・バーガーを登録
# ========================================

def create_debug_burger(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")

    Item.objects.using(
        schema_editor.connection.alias
    ).update_or_create(
        name="デ・バーガー",
        defaults={
            "description": (
                "使用するとログアウトするまで"
                "デバッグモードになる。"
            ),
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
        (
        "inventory",
        "0011_merge_20261124_0959",
        ),
    ]

    operations = [
        migrations.RunPython(
            create_debug_burger,
            migrations.RunPython.noop,
        ),
    ]