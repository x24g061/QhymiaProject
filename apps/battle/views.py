from datetime import timedelta
import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.inventory.models import Item, InventoryItem


# ========================================
# 探索
# ========================================

@login_required
def battle(request):
    character = request.user.character
    now = timezone.now()

    # 現在クールタイム中なら探索させない
    if (
        character.exploration_cooldown_until
        and character.exploration_cooldown_until > now
    ):
        remaining = character.get_exploration_cooldown_remaining()

        messages.warning(
            request,
            f"探索クールタイム中です。あと約{remaining}秒です。"
        )

        return redirect("home")

    # ========================================
    # 現在適用されるCTを取得
    # ========================================

    cooldown_seconds = (
        character.get_exploration_cooldown_seconds()
    )

    # 探索した時刻を保存
    character.last_explored_at = now

    # CT終了時刻を設定
    character.exploration_cooldown_until = (
        now + timedelta(seconds=cooldown_seconds)
    )

    character.save(
        update_fields=[
            "last_explored_at",
            "exploration_cooldown_until",
            "updated_at",
        ]
    )

    # ========================================
    # アイテムドロップ判定
    # ========================================

    # 基本1%
    # 闘技場の連勝数1につき +1%
    # 最大10%
    item_drop_rate = min(
        1 + character.arena_win_streak,
        10
    )

    dropped_item = None

    # 1～100の乱数でドロップ判定
    roll = random.randint(1, 100)

    if roll <= item_drop_rate:

        # 現在は素材カテゴリからランダム取得
        dropped_item = (
            Item.objects
            .filter(category=Item.Category.MATERIAL)
            .order_by("?")
            .first()
        )

        # ドロップ対象アイテムが存在する場合
        if dropped_item:

            inventory_item, created = (
                InventoryItem.objects.get_or_create(
                    character=character,
                    item=dropped_item,
                    defaults={
                        "quantity": 1
                    }
                )
            )

            # すでに持っている場合は個数を増やす
            if not created:
                inventory_item.quantity += 1

                inventory_item.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

    # ========================================
    # 探索結果画面表示
    # ========================================

    return render(
        request,
        "battle.html",
        {
            "character": character,
            "cooldown_seconds": cooldown_seconds,
            "item_drop_rate": item_drop_rate,
            "dropped_item": dropped_item,
        }
    )


# ========================================
# 闘技場の勝敗結果を保存
#
# 現在はテスト用。
# 今後、本戦処理で勝敗を自動判定するようになったら
# 削除・統合する予定。
# ========================================

@login_required
def arena_result(request, result):
    character = request.user.character

    # ========================================
    # 勝利
    # ========================================

    if result == "win":

        character.arena_win_streak += 1
        character.arena_last_result = "win"

        messages.success(
            request,
            f"闘技場で勝利しました！現在{character.arena_win_streak}連勝中です。"
        )

        character.save(
            update_fields=[
                "arena_win_streak",
                "arena_last_result",
                "updated_at",
            ]
        )

    # ========================================
    # 敗北
    # ========================================

    elif result == "loss":

        # 連勝数リセット
        character.arena_win_streak = 0

        # 直近結果を敗北にする
        character.arena_last_result = "loss"

        # 次の階への挑戦を解禁
        character.arena_next_floor_unlocked = True

        character.save(
            update_fields=[
                "arena_win_streak",
                "arena_last_result",
                "arena_next_floor_unlocked",
                "updated_at",
            ]
        )

    # ========================================
    # 不正な値
    # ========================================

    else:
        messages.error(
            request,
            "不正な闘技場結果です。"
        )

        return redirect("home")

    return redirect("home")


# ========================================
# 次の闘技場階へ進む
# ========================================

@login_required
def arena_next_floor(request):
    character = request.user.character

    # ========================================
    # 次の階が解禁されているか確認
    # ========================================

    if not character.arena_next_floor_unlocked:

        messages.warning(
            request,
            "まだ次の階には挑戦できません。"
        )

        return redirect("home")

    # 現在の最上階
    arena_max_floor = 100

    # ========================================
    # 最上階チェック
    # ========================================

    if character.arena_floor >= arena_max_floor:

        messages.warning(
            request,
            "これ以上上の階には進めません。"
        )

        return redirect("home")

    # ========================================
    # 次の階へ進む
    # ========================================

    character.arena_floor += 1

    # 進んだら次階挑戦を再ロック
    character.arena_next_floor_unlocked = False

    character.save(
        update_fields=[
            "arena_floor",
            "arena_next_floor_unlocked",
            "updated_at",
        ]
    )

    return redirect("home")


# ========================================
# 闘技場戦闘
# ========================================

@login_required
def arena_battle(request):
    character = request.user.character
    now = timezone.now()

    # ========================================
    # 探索・闘技場共通CTチェック
    # ========================================

    if (
        character.exploration_cooldown_until
        and character.exploration_cooldown_until > now
    ):
        remaining = character.get_exploration_cooldown_remaining()

        messages.warning(
            request,
            f"クールタイム中です。あと約{remaining}秒です。"
        )

        return redirect("home")

    # ========================================
    # 対戦相手取得
    #
    # 自分と同じ闘技場階にいる
    # 別キャラクターをランダムで1人取得する。
    # ========================================

    opponent = (
        character.__class__.objects
        .filter(
            arena_floor=character.arena_floor
        )
        .exclude(
            id=character.id
        )
        .order_by("?")
        .first()
    )

    # 相手がいない場合
    if opponent is None:

        messages.warning(
            request,
            "この階には対戦相手がいません。"
        )

        return redirect("home")

    # ========================================
    # 先攻判定
    #
    # AGIが高い方が先攻。
    #
    # AGIが同じ場合はランダム。
    # ========================================

    if character.agility > opponent.agility:

        first_attacker = character
        second_attacker = opponent

    elif character.agility < opponent.agility:

        first_attacker = opponent
        second_attacker = character

    else:

        # AGIが同じ場合
        if random.choice([True, False]):

            first_attacker = character
            second_attacker = opponent

        else:

            first_attacker = opponent
            second_attacker = character

    # ========================================
    # 命中率計算
    #
    # 基本命中率：80%
    #
    # 攻撃側DEX
    # －
    # 防御側DEX
    #
    # を補正として加える。
    # ========================================

    hit_rate = 80 + (
        first_attacker.dexterity
        - second_attacker.dexterity
    )

    # ========================================
    # 命中率の上限・下限
    #
    # 最低10%
    # 最大95%
    # ========================================

    hit_rate = max(
        10,
        min(
            95,
            hit_rate
        )
    )

    # ========================================
    # 命中判定
    #
    # 1～100の乱数を生成。
    #
    # 命中率以下なら命中。
    # ========================================

    hit_roll = random.randint(
        1,
        100
    )

    attack_hit = (
        hit_roll <= hit_rate
    )

    # ========================================
    # ダメージ計算
    #
    # 現在の計算式：
    #
    # 攻撃側STR
    # －
    # 防御側VIT
    #
    # 攻撃が外れた場合は0。
    # ========================================

    damage = 0

    if attack_hit:

        damage = (
            first_attacker.strength
            - second_attacker.vitality
        )

        # ====================================
        # 最低1ダメージ保証
        #
        # VITがSTRより高くても
        # 命中した場合は最低1ダメージ入る。
        # ====================================

        damage = max(
            1,
            damage
        )

    # ========================================
    # HP減少計算
    #
    # 現在はDBのHPを書き換えず、
    # 「攻撃後なら何HPになるか」
    # だけ計算する。
    #
    # これは開発途中で安全に確認するため。
    # ========================================

    remaining_hp = (
        second_attacker.current_hp
    )

    # 攻撃が命中した場合だけHPを減らす
    if attack_hit:

        remaining_hp = max(
            0,
            (
                second_attacker.current_hp
                - damage
            )
        )

    # ========================================
    # 共通CT開始
    #
    # 闘技場を実行した場合も、
    # 探索と同じCTを開始する。
    # ========================================

    cooldown_seconds = (
        character.get_exploration_cooldown_seconds()
    )

    character.exploration_cooldown_until = (
        now
        + timedelta(
            seconds=cooldown_seconds
        )
    )

    character.save(
        update_fields=[
            "exploration_cooldown_until",
            "updated_at",
        ]
    )

    # ========================================
    # 闘技場画面表示
    #
    # 計算した値を
    # arena_battle.html に渡す。
    # ========================================

    return render(
        request,
        "arena_battle.html",
        {
            "character": character,
            "opponent": opponent,

            "cooldown_seconds":
                cooldown_seconds,

            "first_attacker":
                first_attacker,

            "second_attacker":
                second_attacker,

            "hit_rate":
                hit_rate,

            "attack_hit":
                attack_hit,

            "damage":
                damage,

            "remaining_hp":
                remaining_hp,
        }
    )