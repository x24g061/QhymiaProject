from django.db import migrations


# ============================================================
# CT短縮アイテムをNPCショップへ登録
# ============================================================

def add_cooldown_items(apps, schema_editor):

    Item = apps.get_model(
        "inventory",
        "Item",
    )

    ShopStock = apps.get_model(
        "shop",
        "ShopStock",
    )


    # ========================================================
    # 商品マスター
    # ========================================================

    items = [
        {
            "name": "CT短縮時計（1日）",
            "description": (
                "探索・闘技場の戦闘クールタイムを"
                "20秒に短縮する。効果期間：1日"
            ),
            "days": 1,
            "price": 1000,
        },
        {
            "name": "CT短縮時計（7日）",
            "description": (
                "探索・闘技場の戦闘クールタイムを"
                "20秒に短縮する。効果期間：7日"
            ),
            "days": 7,
            "price": 5000,
        },
        {
            "name": "CT短縮時計（30日）",
            "description": (
                "探索・闘技場の戦闘クールタイムを"
                "20秒に短縮する。効果期間：30日"
            ),
            "days": 30,
            "price": 15000,
        },
    ]


    # ========================================================
    # Item / ShopStock 登録
    # ========================================================

    for data in items:

        item, created = Item.objects.update_or_create(
            name=data["name"],
            defaults={
                "description":
                    data["description"],

                "category":
                    "consumable",

                "buy_price":
                    data["price"],

                "is_usable":
                    True,

                "cooldown_reduction_days":
                    data["days"],

                "npc_purchasable":
                    True,

                "npc_sellable":
                    True,

                "market_sellable":
                    True,
            },
        )


        # NPCショップの商品在庫
        ShopStock.objects.update_or_create(
            item=item,
            defaults={
                # 暫定的に十分多め
                "stock": 9999,

                "sale_price":
                    data["price"],

                "is_available":
                    True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "inventory",
            "0004_merge_20261007_1054",
        ),
        (
            "shop",
            "0002_marketlisting",
        ),
    ]

    operations = [
        migrations.RunPython(
            add_cooldown_items,
            migrations.RunPython.noop,
        ),
    ]