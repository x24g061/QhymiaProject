from datetime import timedelta

from collections import defaultdict
from apps.shop.models import MarketListing
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import (
    Character,
    UserSettings,
)
from apps.accounts.growth import increase_attribute_growth_weight

from .models import (
    Equipment,
    InventoryItem,
    OwnedEquipment,
)
from .services import (
    equip_item,
    synthesize_equipments,
    unequip_item,
)

from apps.accounts.debug_mode import (
    enable_debug_mode,
    is_debug_mode,
)


# ============================================================
# 倉庫画面
# ============================================================

@login_required
def inventory(request):
    """
    倉庫画面。

    ・現在装備中の5部位
    ・所持装備
    ・通常アイテム

    を表示する。
    """

    character = request.user.character

    # ========================================================
    # 所持装備
    # ========================================================

    owned_equipments = list(
        OwnedEquipment.objects
        .filter(
            character=character,
        )
        .select_related(
            "equipment",
            "equipment__item",
        )
        .order_by(
            "equipment__slot",
            "equipment__rank",
            "equipment__item__name",
        )
    )

    # ========================================================
    # 倉庫表示用に装備をまとめる
    #
    # ・特殊能力あり → 個別表示
    # ・装備中 → 個別表示
    # ・特殊能力なし / 未装備
    #   → 同じ装備・同じ強化値・同じ戦闘力ならまとめる
    # ========================================================

    equipment_display_rows = []

    grouped_equipments = {}

    for owned in owned_equipments:

        # 特殊能力付き、または装備中は必ず個別表示
        if (
            owned.special_effect
            or owned.is_equipped
        ):

            equipment_display_rows.append(
                {
                    "owned": owned,
                    "quantity": 1,
                }
            )

            continue


        # 通常装備をまとめるためのキー
        group_key = (
            owned.equipment_id,
            owned.enhancement_level,
            owned.battle_power,
        )


        if group_key not in grouped_equipments:

            row = {
                # このグループを代表する装備個体
                "owned": owned,

                # これから加算
                "quantity": 0,
            }

            grouped_equipments[
                group_key
            ] = row

            equipment_display_rows.append(
                row
            )


        grouped_equipments[
            group_key
        ]["quantity"] += 1

    # ========================================================
    # 通常アイテム
    # ========================================================

    inventory_items = list(
        InventoryItem.objects
        .filter(
            character=character,
        )
        .select_related(
            "item",
        )
        .order_by(
            "item__category",
            "item__name",
        )
    )


    # ========================================================
    # 現在装備している装備
    # ========================================================

    equipped_by_slot = {
        owned.equipment.slot: owned
        for owned in owned_equipments
        if owned.is_equipped
    }


    # ========================================================
    # 5部位を必ず表示
    # ========================================================

    equipment_slots = []

    for slot_value, slot_label in (
        Equipment.Slot.choices
    ):

        equipment_slots.append(
            {
                "value": slot_value,
                "label": slot_label,
                "owned": (
                    equipped_by_slot.get(
                        slot_value
                    )
                ),
            }
        )


    # ========================================================
    # 所持品総数
    # ========================================================

    normal_item_count = sum(
        inventory_item.quantity
        for inventory_item
        in inventory_items
    )

    equipment_count = len(
        owned_equipments
    )

    inventory_count = (
        normal_item_count
        + equipment_count
    )


    return render(
        request,
        "inventory.html",
        {
            "character": character,

            "equipment_slots":
                equipment_slots,
                

            "owned_equipments":
                owned_equipments,

            "equipment_display_rows":
                equipment_display_rows,

            "inventory_items":
                inventory_items,

            "inventory_count":
                inventory_count,

            # main側テンプレートとの互換用
            "total_item_count":
                inventory_count,
        },
    )


# ============================================================
# 装備合成
# ============================================================

@login_required
def synthesis(request):
    """
    装備合成画面。

    GET:
        合成に使用できる装備を表示する。

    POST:
        選択された3つの装備を合成する。
    """

    character = request.user.character

    # ========================================
    # ユーザー設定
    # ========================================

    user_settings, _ = (
        UserSettings.objects.get_or_create(
            user=request.user
        )
    )

    # ========================================================
    # 合成実行
    # ========================================================

    if request.method == "POST":

        selected_ids = request.POST.getlist(
            "equipment_ids"
        )

        # カード1枚の選択から素材3個のIDを受け取る
        selected_materials = request.POST.getlist(
            "selected_materials"
        )

        # 一括合成
        if request.POST.get("bulk_synthesis") == "1":
            try:
                count = int(request.POST.get("synthesis_count", "1"))

                if not 1 <= count <= 10:
                    raise ValueError("合成回数は1〜10回で指定してください。")

                if len(selected_materials) != 1 or selected_ids:
                    raise ValueError("装備の選択が不正です。")

                raw_ids = selected_materials[0].split(",")

                if (
                    len(raw_ids) > 30
                    or any(
                        not value.isascii()
                        or not value.isdecimal()
                        or len(value) > 19
                        or not 0 < int(value) < 2**63
                        for value in raw_ids
                    )
                ):
                    raise ValueError("装備の選択が不正です。")

                material_ids = [
                    int(value)
                    for value in raw_ids[:count * 3]
                ]

                if (
                    len(material_ids) != count * 3
                    or len(set(material_ids)) != count * 3
                ):
                    raise ValueError("合成素材が不足しています。")

                use_guarantee = (
                    request.POST.get("use_guarantee") == "on"
                )

                results = []

                with transaction.atomic():
                    locked_character = (
                        Character.objects
                        .select_for_update()
                        .get(pk=character.pk)
                    )

                    materials = list(
                        OwnedEquipment.objects
                        .select_for_update()
                        .select_related("equipment", "equipment__item")
                        .filter(
                            character=locked_character,
                            pk__in=material_ids,
                            is_equipped=False,
                        )
                    )

                    if len(materials) != count * 3:
                        raise ValueError("合成可能な素材が不足しています。")

                    if MarketListing.objects.filter(
                        owned_equipment_id__in=material_ids,
                        status=MarketListing.Status.LISTED,
                    ).exists():
                        raise ValueError("出品中の装備は合成できません。")

                    groups = {
                        (item.equipment_id, item.enhancement_level)
                        for item in materials
                    }

                    if len(groups) != 1:
                        raise ValueError("同じ装備・同じ強化値を選択してください。")

                    locked_character.reset_daily_synthesis_count_if_needed()

                    free_count = max(
                        0,
                        3 - locked_character.daily_synthesis_count,
                    )

                    total_cost = max(0, count - free_count) * 10

                    if locked_character.gold < total_cost:
                        raise ValueError("合成に必要なQが不足しています。")

                    if use_guarantee:
                        guarantee = (
                            InventoryItem.objects
                            .select_for_update()
                            .filter(
                                character=locked_character,
                                item__name="合成成功保証書",
                            )
                            .first()
                        )

                        if not guarantee or guarantee.quantity < count:
                            raise ValueError("合成成功保証書が不足しています。")

                    material_map = {
                        item.pk: item for item in materials
                    }

                    # 画面表示時に確定した素材だけを使用する
                    for index in range(count):
                        batch_ids = material_ids[index * 3:index * 3 + 3]

                        batch = [
                            material_map[pk]
                            for pk in batch_ids
                        ]

                        result = synthesize_equipments(
                            locked_character,
                            batch,
                            use_guarantee=use_guarantee,
                        )

                        results.append(result)

                result_counts = {
                    "success": 0,
                    "great_success": 0,
                    "super_success": 0,
                    "failure": 0,
                }

                for result in results:
                    result_counts[result["result"]] += 1

                messages.success(
                    request,
                    f"{count}回の合成が完了しました。"
                    f" 成功：{result_counts['success']}回"
                    f" ／ 大成功：{result_counts['great_success']}回"
                    f" ／ 超大成功：{result_counts['super_success']}回"
                    f" ／ 失敗：{result_counts['failure']}回"
                    f" ／ 消費Q：{total_cost}Q"
                )

                # SNS共有候補が複数ある場合は
                # 最も強化値の高い装備を選択する
                share_candidates = [
                    result["equipment"]
                    for result in results
                    if result.get("equipment") is not None
                    and (
                        result["result"] in {
                            "great_success", "super_success"
                        }
                        or result["equipment"].enhancement_level >= 7
                    )
                ]

                if (
                    share_candidates
                    and user_settings.synthesis_sns_prompt_enabled
                ):
                    equipment = max(
                        share_candidates,
                        key=lambda item: item.enhancement_level,
                    )

                    equipment_name = equipment.equipment.item.name
                    level = equipment.enhancement_level
                    rank = equipment.equipment.rank

                    request.session["synthesis_sns_share"] = {
                        "text": (
                            f"装備合成に成功！"
                            f"【{rank}】{equipment_name}"
                            f"+{level}を獲得した！"
                        ),
                        "equipment_name": equipment_name,
                        "level": level,
                    }

            except ValueError as error:
                messages.error(request, str(error))

            return redirect("inventory:synthesis")

        if selected_materials:
            if len(selected_materials) != 1 or selected_ids:
                messages.error(request, "装備の選択が不正です。")
                return redirect("inventory:synthesis")

            selected_ids = selected_materials[0].split(",")

            if (
                len(selected_ids) != 3
                or any(
                    not value.isascii()
                    or not value.isdecimal()
                    or len(value) > 19
                    or not 0 < int(value) < 2**63
                    for value in selected_ids
                )
            ):
                messages.error(request, "装備の選択が不正です。")
                return redirect("inventory:synthesis")

            selected_ids = [int(value) for value in selected_ids]

        # 3つ選択されているか確認
        if len(selected_ids) != 3:

            messages.error(
                request,
                "合成する装備を3つ選んでください。",
            )

            return redirect(
                "inventory:synthesis"
            )


        # ====================================================
        # 自分が所持している装備だけ取得
        # ====================================================

        equipments = list(
            OwnedEquipment.objects
            .filter(
                id__in=selected_ids,
                character=character,
            )
            .select_related(
                "equipment",
                "equipment__item",
            )
        )


        # 不正なIDなどで3つ取得できなかった場合
        if len(equipments) != 3:

            messages.error(
                request,
                "選択された装備を確認できませんでした。",
            )

            return redirect(
                "inventory:synthesis"
            )


        # ====================================================
        # 合成処理
        # ====================================================

        try:

            result = synthesize_equipments(
                character,
                equipments,
                use_guarantee=(
                    request.POST.get("use_guarantee") == "on"
                ),
            )

        except ValueError as error:

            messages.error(
                request,
                str(error),
            )

            return redirect(
                "inventory:synthesis"
            )


        # ====================================================
        # 合成結果メッセージ
        # ====================================================

        if result["result"] == "failure":

            messages.error(
                request,
                "合成に失敗しました。装備3つを失いました。",
            )

        elif result["result"] == "success":

            messages.success(
                request,
                "合成成功！ +1強化されました。",
            )

        elif result["result"] == "great_success":

            messages.success(
                request,
                "大成功！ +2強化されました。",
            )

        elif result["result"] == "super_success":

            messages.success(
                request,
                "超大成功！ +3強化されました。",
            )


        # ====================================================
        # SNS共有候補
        # ====================================================

        new_equipment = result.get(
            "equipment"
        )


        if new_equipment is not None:

            result_type = result["result"]

            new_level = (
                new_equipment.enhancement_level
            )

            equipment_name = (
                new_equipment
                .equipment
                .item
                .name
            )

            equipment_rank = (
                new_equipment
                .equipment
                .rank
            )


            # ================================================
            # SNS共有対象
            # ================================================
            #
            # ・大成功
            # ・超大成功
            # ・完成後+7以上
            #
            # ================================================

            should_share = (
                result_type
                in {
                    "great_success",
                    "super_success",
                }
                or
                new_level >= 7
            )


            # ================================================
            # デバッグ
            # ================================================

            # print(
            #     "SNS SHARE DEBUG:",
            #     {
            #         "result_type":
            #             result_type,

            #         "new_level":
            #             new_level,

            #         "should_share":
            #             should_share,

            #         "setting":
            #             user_settings
            #             .synthesis_sns_prompt_enabled,
            #     }
            # )


            # ================================================
            # 設定がONの場合のみ投稿確認を表示
            # ================================================

            if (
                should_share
                and
                user_settings.synthesis_sns_prompt_enabled
            ):

                # print(
                #     "SNS SHARE SESSION SAVE"
                # )

                if (
                    result_type
                    == "super_success"
                ):

                    share_text = (
                        f"超大成功！"
                        f"【{equipment_rank}】"
                        f"{equipment_name}の合成に成功して"
                        f"+{new_level}になった！"
                    )

                elif (
                    result_type
                    == "great_success"
                ):

                    share_text = (
                        f"大成功！"
                        f"【{equipment_rank}】"
                        f"{equipment_name}の合成に成功して"
                        f"+{new_level}になった！"
                    )

                else:

                    share_text = (
                        f"【{equipment_rank}】"
                        f"{equipment_name}の合成に成功して"
                        f"+{new_level}になった！"
                    )


                request.session[
                    "synthesis_sns_share"
                ] = {
                    "text":
                        share_text,

                    "equipment_name":
                        equipment_name,

                    "level":
                        new_level,
                }


        return redirect(
            "inventory:synthesis"
        )


    
    # ========================================================
    # 合成可能な装備を種類・強化値ごとにまとめる
    # ========================================================


    # ========================================================
    # 合成候補の装備を取得
    # 出品中の装備は候補から除外
    # ========================================================

    owned_equipments = list(
        OwnedEquipment.objects
        .filter(
            character=character,
            is_equipped=False,
        )
        .exclude(
            market_listings__status=MarketListing.Status.LISTED,
        )        
        .select_related(
            "equipment",
            "equipment__item",
        )
        .order_by(
            "equipment__rank",
            "equipment__item__name",
            "enhancement_level",
            "id",
        )
        .distinct()
    )

    # 同じ装備・同じ強化値で分類
    grouped_equipments = defaultdict(list)

    for owned in owned_equipments:
        key = (
            owned.equipment_id,
            owned.enhancement_level,
        )

        grouped_equipments[key].append(owned)

    
    # ========================================================
    # 3個以上あるグループだけを表示
    # ========================================================

    synthesis_groups = []

    for (equipment_id, level), group in grouped_equipments.items():

        # 3個未満は合成できないため除外
        if len(group) < 3:
            continue

        equipment = group[0].equipment

        # 特殊能力なしを優先し、戦闘力が低いものから選択
        materials = sorted(
            group,
            key=lambda owned: (
                bool(owned.special_effect),
                owned.battle_power,
                owned.pk,
            ),
        )[:30]

        selected_material_ids = ",".join(
            str(owned.pk) for owned in materials
        )

        selected_effects = [
            owned.get_special_effect_display()
            for owned in materials
            if owned.special_effect
        ]

        synthesis_groups.append({
            "max_synthesis_count": min(10, len(group) // 3),
            "normal_material_count": sum(
                1 for owned in materials
                if not owned.special_effect
            ),
            "selected_material_ids": selected_material_ids,
            "selected_effects": selected_effects,
            "equipment_id": equipment_id,
            "equipment": equipment,
            "level": level,
            "count": len(group),
            "owned_ids": [owned.id for owned in group],
            "owned_items": group,
        })



    # ========================================================
    # 次回の合成料金
    # ========================================================

    synthesis_cost = (
        character.get_synthesis_cost()
    )

    # ========================================================
    # SNS共有確認
    # ========================================================

    synthesis_sns_share = (
        request.session.pop(
            "synthesis_sns_share",
            None,
        )
    )


    # print(
    #     "SNS SHARE GET DEBUG:",
    #     synthesis_sns_share,
    # )

    # 合成成功保証書の所持数
    guarantee_inventory = (
        InventoryItem.objects
        .filter(
            character=character,
            item__name="合成成功保証書",
        )
        .first()
    )

    guarantee_quantity = (
        guarantee_inventory.quantity
        if guarantee_inventory
        else 0
    )

    return render(
        request,
        "synthesis.html",
        {
            "character":
                character,

            "owned_equipments":
                owned_equipments,

            "synthesis_groups":
                synthesis_groups,

            "synthesis_cost":
                synthesis_cost,

            "guarantee_quantity":
                guarantee_quantity,

            "synthesis_sns_share":
                synthesis_sns_share,
        },
    )

# ============================================================
# 装備する
# ============================================================

@login_required
@require_POST
def equip_equipment(
    request,
    owned_equipment_id,
):
    """
    所持装備を装備する。
    """

    character = request.user.character

    owned_equipment = (
        get_object_or_404(
            OwnedEquipment.objects
            .select_related(
                "equipment",
                "equipment__item",
            ),
            id=owned_equipment_id,
            character=character,
        )
    )

    equip_item(
        character,
        owned_equipment,
    )

    messages.success(
        request,
        (
            f"{owned_equipment.equipment.item.name}"
            "を装備しました。"
        ),
    )

    return redirect(
        "inventory:inventory"
    )


# ============================================================
# 装備を外す
# ============================================================

@login_required
@require_POST
def unequip_equipment(
    request,
    owned_equipment_id,
):
    """
    現在の装備を外す。
    """

    character = request.user.character

    owned_equipment = (
        get_object_or_404(
            OwnedEquipment.objects
            .select_related(
                "equipment",
                "equipment__item",
            ),
            id=owned_equipment_id,
            character=character,
        )
    )

    unequip_item(
        character,
        owned_equipment,
    )

    messages.success(
        request,
        (
            f"{owned_equipment.equipment.item.name}"
            "を外しました。"
        ),
    )

    return redirect(
        "inventory:inventory"
    )


# ============================================================
# アイテム使用
# ============================================================

@login_required
@transaction.atomic
def use_item(
    request,
    inventory_item_id,
):
    """
    所持アイテムを使用する。

    対応:
    ・CT短縮時計
    ・属性成長の種
    """

    # POST以外では使用できない
    if request.method != "POST":

        return redirect(
            "inventory:inventory"
        )


    # ========================================================
    # キャラクター取得
    # ========================================================

    character = (
        Character.objects
        .select_for_update()
        .get(
            user=request.user
        )
    )


    # ========================================================
    # 自分の所持アイテム取得
    # ========================================================

    try:

        inventory_item = (
            InventoryItem.objects
            .select_for_update()
            .select_related(
                "item"
            )
            .get(
                pk=inventory_item_id,
                character=character,
            )
        )

    except InventoryItem.DoesNotExist:

        messages.error(
            request,
            "アイテムが見つかりません。",
        )

        return redirect(
            "inventory:inventory"
        )


    item = inventory_item.item


    # ========================================================
    # 使用可能チェック
    # ========================================================

    if not item.is_usable:

        messages.error(
            request,
            "このアイテムは使用できません。",
        )

        return redirect(
            "inventory:inventory"
        )

    # ========================================================
    # デ・バーガー
    # ========================================================

    if item.name == "デ・バーガー":

        # すでにデバッグモード中なら消費しない
        if is_debug_mode(request):

            messages.warning(
                request,
                "すでにデバッグモードが有効です。",
            )

            return redirect(
                "inventory:inventory"
            )


        # ================================================
        # デバッグモードON
        # ================================================

        enable_debug_mode(request)


        # ================================================
        # アイテムを1個消費
        # ================================================

        if inventory_item.quantity <= 1:

            inventory_item.delete()

        else:

            inventory_item.quantity -= 1

            inventory_item.save(
                update_fields=[
                    "quantity",
                ]
            )


        messages.success(
            request,
            "デ・バーガーを使用しました。"
            "デバッグモードが有効になりました。",
        )


        return redirect(
            "inventory:inventory"
        )
    # ========================================
    # ボス挑戦チケット
    # ========================================

    if item.name == "ボス挑戦チケット":

        if character.next_exploration_boss_guaranteed:
            messages.warning(
                request,
                "すでに次回のボス遭遇が確定しています。",
            )
            return redirect("inventory:inventory")

        character.next_exploration_boss_guaranteed = True
        character.save(
            update_fields=["next_exploration_boss_guaranteed"]
        )

        if inventory_item.quantity == 1:
            inventory_item.delete()
        else:
            inventory_item.quantity -= 1
            inventory_item.save(update_fields=["quantity"])

        messages.success(
            request,
            "ボス挑戦チケットを使用しました！"
            "次の探索でボスが確定出現します。",
        )

        return redirect("inventory:inventory")

    # ========================================================
    # 種族変更アイテム
    # ========================================================

    race_change_items = {
        "ヒューマンの種族変更証":
            "human",

        "エルフの種族変更証":
            "elf",

        "ドワーフの種族変更証":
            "dwarf",

        "ドラゴニアの種族変更証":
            "dragonia",

        "ウィッチの種族変更証":
            "witch",

        "フェアリーの種族変更証":
            "fairy",

        "デモニアの種族変更証":
            "demonia",
    }


    if item.name in race_change_items:

        new_race = (
            race_change_items[
                item.name
            ]
        )


        # ================================================
        # 現在と同じ種族なら使用しない
        # ================================================

        if character.race == new_race:

            messages.error(
                request,
                "すでにこの種族です。",
            )

            return redirect(
                "inventory:inventory"
            )


        # ================================================
        # 種族変更
        # ================================================

        character.race = new_race

        character.save(
            update_fields=[
                "race",
                "updated_at",
            ]
        )


        # ================================================
        # アイテムを1個消費
        # ================================================

        if inventory_item.quantity <= 1:

            inventory_item.delete()

        else:

            inventory_item.quantity -= 1

            inventory_item.save(
                update_fields=[
                    "quantity",
                ]
            )


        messages.success(
            request,
            (
                f"{item.name}を使用しました。"
                f"種族が"
                f"{character.get_race_display()}"
                "に変更されました。"
            ),
        )


        return redirect(
            "inventory:inventory"
        )


    # ========================================================
    # 職業変更アイテム
    # ========================================================

    job_change_items = {
        "拳闘士の職業変更証":
            "grappler",

        "重戦士の職業変更証":
            "warrior",

        "狩人の職業変更証":
            "hunter",

        "ウィザードの職業変更証":
            "wizard",

        "プリーストの職業変更証":
            "priest",

        "放浪人の職業変更証":
            "wanderer",

        "暗殺者の職業変更証":
            "assassin",
    }


    if item.name in job_change_items:

        new_job = (
            job_change_items[
                item.name
            ]
        )


        # ================================================
        # 現在と同じ職業なら使用しない
        # ================================================

        if character.job == new_job:

            messages.error(
                request,
                "すでにこの職業です。",
            )

            return redirect(
                "inventory:inventory"
            )


        # ================================================
        # 職業変更
        # ================================================

        character.job = new_job

        character.save(
            update_fields=[
                "job",
                "updated_at",
            ]
        )


        # ================================================
        # 旧職業のスキルプリセットを削除
        # ================================================

        from apps.battle.models import (
            SkillPreset,
        )

        SkillPreset.objects.filter(
            character=character
        ).delete()


        # ================================================
        # アイテムを1個消費
        # ================================================

        if inventory_item.quantity <= 1:

            inventory_item.delete()

        else:

            inventory_item.quantity -= 1

            inventory_item.save(
                update_fields=[
                    "quantity",
                ]
            )


        messages.success(
            request,
            (
                f"{item.name}を使用しました。"
                f"職業が"
                f"{character.get_job_display()}"
                "に変更されました。"
                "スキルプリセットはリセットされました。"
            ),
        )


        return redirect(
            "inventory:inventory"
        )

    # ========================================================
    # 属性成長の種
    # ========================================================

    seed_attributes = {
        "火の種": "fire",
        "水の種": "water",
        "草の種": "grass",
        "岩の種": "rock",
        "光の種": "light",
        "闇の種": "dark",
    }

    attribute_display_names = {
        "fire": "火",
        "water": "水",
        "grass": "草",
        "rock": "岩",
        "light": "光",
        "dark": "闇",
    }


    if item.name in seed_attributes:

        attribute_name = (
            seed_attributes[
                item.name
            ]
        )

        try:

            result = (
                increase_attribute_growth_weight(
                    character,
                    attribute_name,
                )
            )

        except ValueError as error:

            # 上限15などで使用できなかった場合
            # アイテムは消費しない
            messages.error(
                request,
                str(error),
            )

            return redirect(
                "inventory:inventory"
            )


        # ====================================================
        # 種を1個消費
        # ====================================================

        if inventory_item.quantity <= 1:

            inventory_item.delete()

        else:

            inventory_item.quantity -= 1

            inventory_item.save(
                update_fields=[
                    "quantity",
                ]
            )


        increased_name = (
            attribute_display_names[
                result["increased"]
            ]
        )

        decreased_attribute = (
            result["decreased"]
        )


        # 他属性が下がった場合
        if decreased_attribute:

            decreased_name = (
                attribute_display_names[
                    decreased_attribute
                ]
            )

            messages.success(
                request,
                (
                    f"{item.name}を使用しました。"
                    f"{increased_name}属性の成長値が+1、"
                    f"{decreased_name}属性の成長値が-1されました。"
                ),
            )

        # 全属性が下限1で、
        # 下げられる属性が無かった場合
        else:

            messages.success(
                request,
                (
                    f"{item.name}を使用しました。"
                    f"{increased_name}属性の成長値が+1されました。"
                ),
            )


        return redirect(
            "inventory:inventory"
        )


    # ========================================================
    # CT短縮時計
    # ========================================================

    if not item.cooldown_reduction_days:

        messages.error(
            request,
            (
                "このアイテムの使用効果は"
                "まだ実装されていません。"
            ),
        )

        return redirect(
            "inventory:inventory"
        )


    now = timezone.now()


    # ========================================================
    # CT短縮時計の効果期間
    # ========================================================

    already_active = (
        character.exploration_cooldown_reduced_until
        and
        character.exploration_cooldown_reduced_until
        > now
    )


    if already_active:

        # 効果中なら現在の終了日時へ加算
        character.exploration_cooldown_reduced_until += (
            timedelta(
                days=item.cooldown_reduction_days
            )
        )

    else:

        # 効果適用前のCTを取得
        cooldown_before = (
            character.get_exploration_cooldown_seconds()
        )

        # 新しく効果開始
        character.exploration_cooldown_reduced_until = (
            now
            + timedelta(
                days=item.cooldown_reduction_days
            )
        )


        # ====================================================
        # 初回使用時だけ
        # 現在進行中の探索CTを短縮
        cooldown_after = (
            character.get_exploration_cooldown_seconds()
        )

        reduction_seconds = max(
            0, cooldown_before - cooldown_after
        )
        # ====================================================

        if (
            character.exploration_cooldown_until
            and
            character.exploration_cooldown_until > now
        ):

            shortened_until = (
                character.exploration_cooldown_until
                - timedelta(
                    seconds=reduction_seconds
                )
            )

            # 残り時間が短縮量以下なら即探索可能
            if shortened_until <= now:

                character.exploration_cooldown_until = now

            else:

                character.exploration_cooldown_until = (
                    shortened_until
                )


    character.save(
        update_fields=[
            "exploration_cooldown_reduced_until",
            "exploration_cooldown_until",
            "updated_at",
        ]
    )


    # ========================================================
    # 使用アイテムを1個消費
    # ========================================================

    if inventory_item.quantity <= 1:

        inventory_item.delete()

    else:

        inventory_item.quantity -= 1

        inventory_item.save(
            update_fields=[
                "quantity",
            ]
        )


    messages.success(
        request,
        (
            f"{item.name}を使用しました。"
            f"戦闘クールタイムが"
            f"{character.get_exploration_cooldown_seconds()}秒になります。"
        ),
    )

    return redirect(
        "inventory:inventory"
    )

    # ============================================================
# 手相画面から属性成長アイテムを使用
# ============================================================

@login_required
@require_POST
@transaction.atomic
def use_palm_growth_item(request):
    """
    手相画面から属性成長の種を1個使用する。
    """

    character = (
        Character.objects
        .select_for_update()
        .get(
            user=request.user
        )
    )


    # ========================================
    # 手相が解放中か確認
    # ========================================

    now = timezone.now()

    palm_is_unlocked = (
        character.palm_unlocked_until
        and
        character.palm_unlocked_until > now
    )


    if not palm_is_unlocked:

        messages.error(
            request,
            "手相を確認できる期間が終了しています。",
        )

        return redirect(
            "accounts:palm"
        )


    # ========================================
    # 使用アイテム取得
    # ========================================

    inventory_item_id = request.POST.get(
        "inventory_item_id"
    )


    try:

        inventory_item = (
            InventoryItem.objects
            .select_for_update()
            .select_related(
                "item"
            )
            .get(
                pk=inventory_item_id,
                character=character,
            )
        )

    except (
        InventoryItem.DoesNotExist,
        ValueError,
        TypeError,
    ):

        messages.error(
            request,
            "使用するアイテムを確認できませんでした。",
        )

        return redirect(
            "accounts:palm"
        )


    item = inventory_item.item


    # ========================================
    # 使用可能な属性の種
    # ========================================

    seed_attributes = {
        "火の種": "fire",
        "水の種": "water",
        "草の種": "grass",
        "岩の種": "rock",
        "光の種": "light",
        "闇の種": "dark",
    }


    attribute_display_names = {
        "fire": "火",
        "water": "水",
        "grass": "草",
        "rock": "岩",
        "light": "光",
        "dark": "闇",
    }


    if item.name not in seed_attributes:

        messages.error(
            request,
            "このアイテムは手相では使用できません。",
        )

        return redirect(
            "accounts:palm"
        )


    if not item.is_usable:

        messages.error(
            request,
            "このアイテムは使用できません。",
        )

        return redirect(
            "accounts:palm"
        )


    attribute_name = (
        seed_attributes[
            item.name
        ]
    )


    # ========================================
    # 属性成長ウェイト変更
    # ========================================

    try:

        result = (
            increase_attribute_growth_weight(
                character,
                attribute_name,
            )
        )

    except ValueError as error:

        messages.error(
            request,
            str(error),
        )

        return redirect(
            "accounts:palm"
        )


    # ========================================
    # アイテムを1個消費
    # ========================================

    if inventory_item.quantity <= 1:

        inventory_item.delete()

    else:

        inventory_item.quantity -= 1

        inventory_item.save(
            update_fields=[
                "quantity",
            ]
        )


    # ========================================
    # 結果メッセージ
    # ========================================

    increased_name = (
        attribute_display_names[
            result["increased"]
        ]
    )

    decreased_attribute = (
        result["decreased"]
    )


    if decreased_attribute:

        decreased_name = (
            attribute_display_names[
                decreased_attribute
            ]
        )

        messages.success(
            request,
            (
                f"{item.name}を使用しました。"
                f"{increased_name}属性の成長値が+1、"
                f"{decreased_name}属性の成長値が-1されました。"
            ),
        )

    else:

        messages.success(
            request,
            (
                f"{item.name}を使用しました。"
                f"{increased_name}属性の成長値が+1されました。"
            ),
        )


    return redirect(
        "accounts:palm"
    )