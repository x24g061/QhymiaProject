from django.db import migrations


# ============================================================
# 種族・職業変更アイテム
# ============================================================

CHANGE_ITEMS = [

    # ========================================================
    # 種族変更
    # ========================================================

    (
        "ヒューマンの種族変更証",
        "使用すると種族をヒューマンに変更する。",
    ),
    (
        "エルフの種族変更証",
        "使用すると種族をエルフに変更する。",
    ),
    (
        "ドワーフの種族変更証",
        "使用すると種族をドワーフに変更する。",
    ),
    (
        "ドラゴニアの種族変更証",
        "使用すると種族をドラゴニアに変更する。",
    ),
    (
        "ウィッチの種族変更証",
        "使用すると種族をウィッチに変更する。",
    ),
    (
        "フェアリーの種族変更証",
        "使用すると種族をフェアリーに変更する。",
    ),
    (
        "デモニアの種族変更証",
        "使用すると種族をデモニアに変更する。",
    ),


    # ========================================================
    # 職業変更
    # ========================================================

    (
        "拳闘士の職業変更証",
        "使用すると職業を拳闘士に変更する。",
    ),
    (
        "重戦士の職業変更証",
        "使用すると職業を重戦士に変更する。",
    ),
    (
        "狩人の職業変更証",
        "使用すると職業を狩人に変更する。",
    ),
    (
        "ウィザードの職業変更証",
        "使用すると職業をウィザードに変更する。",
    ),
    (
        "プリーストの職業変更証",
        "使用すると職業をプリーストに変更する。",
    ),
    (
        "放浪人の職業変更証",
        "使用すると職業を放浪人に変更する。",
    ),
    (
        "暗殺者の職業変更証",
        "使用すると職業を暗殺者に変更する。",
    ),
]


def add_character_change_items(
    apps,
    schema_editor,
):

    Item = apps.get_model(
        "inventory",
        "Item",
    )

    ShopStock = apps.get_model(
        "shop",
        "ShopStock",
    )


    for name, description in CHANGE_ITEMS:

        item, _ = Item.objects.update_or_create(
            name=name,
            defaults={
                "description":
                    description,

                "category":
                    "consumable",

                "buy_price":
                    1000,

                "sell_price":
                    0,

                "is_usable":
                    True,

                "npc_purchasable":
                    True,

                # 特殊なシステムアイテムなので
                # 売却・フリマ出品は不可
                "npc_sellable":
                    False,

                "market_sellable":
                    False,
            },
        )


        ShopStock.objects.update_or_create(
            item=item,
            defaults={
                "stock":
                    9999,

                "sale_price":
                    1000,

                "is_available":
                    True,
            },
        )


def remove_character_change_items(
    apps,
    schema_editor,
):

    Item = apps.get_model(
        "inventory",
        "Item",
    )

    item_names = [
        name
        for name, _
        in CHANGE_ITEMS
    ]

    Item.objects.filter(
        name__in=item_names
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "inventory",
            "0008_ownedequipment_special_effect",
        ),
        (
            "shop",
            "0006_marketsalenotification",
        ),
    ]

    operations = [
        migrations.RunPython(
            add_character_change_items,
            remove_character_change_items,
        ),
    ]