from datetime import timedelta
import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.growth import apply_exploration_exp

from .models import Enemy, Skill, SkillPreset
from .services import BattleEngine
from .drops import grant_exploration_drop


from apps.inventory.models import Item, InventoryItem


# ========================================
# 探索
# ========================================

@login_required
@require_POST
def battle(request):
    """
    探索を1回実行する。

    探索1クリック
    ↓
    敵を1体選択
    ↓
    自動戦闘を1回実行
    ↓
    戦闘ログを表示
    ↓
    勝利ならEXP獲得
    ↓
    必要ならレベルアップ
    ↓
    HP / MP全回復
    """

    character = request.user.character
    now = timezone.now()

    # ========================================================
    # 探索クールタイム確認
    # ========================================================

    if (
        character.exploration_cooldown_until
        and character.exploration_cooldown_until > now
    ):
        remaining = (
            character.get_exploration_cooldown_remaining()
        )

        messages.warning(
            request,
            f"探索クールタイム中です。"
            f"あと約{remaining}秒です。",
        )

        return redirect("home")


    # ========================================================
    # 探索階層を取得
    # ========================================================

    try:
        selected_floor = int(
            request.POST.get(
                "floor",
                1,
            )
        )

    except (TypeError, ValueError):
        selected_floor = 1


    # 今は1～3階を自由に探索可能
    if selected_floor not in (1, 2, 3):

        messages.error(
            request,
            "存在しない探索階層です。",
        )

        return redirect("home")


    # ========================================================
    # 選択階層の通常敵を取得
    # ========================================================

    enemy_candidates = list(
        Enemy.objects.filter(
            floor=selected_floor,
            is_boss=False,
        )
    )


    if not enemy_candidates:

        messages.error(
            request,
            "この階層には敵が登録されていません。",
        )

        return redirect("home")


    # ========================================================
    # 出現数を1～3体からランダム決定
    # ========================================================

    enemy_count = random.randint(
        1,
        min(
            3,
            len(enemy_candidates),
        ),
    )


    # 同じ戦闘では同じ敵種類を重複させず選ぶ
    enemies = random.sample(
        enemy_candidates,
        enemy_count,
    )


    # ========================================================
    # 探索クールタイム設定
    # ========================================================

    cooldown_seconds = (
        character.get_exploration_cooldown_seconds()
    )

    # 探索した時刻を保存
    character.last_explored_at = now

    # 次に探索できる時刻
    character.exploration_cooldown_until = (
        now
        + timedelta(
            seconds=cooldown_seconds
        )
    )

    character.save(
        update_fields=[
            "last_explored_at",
            "exploration_cooldown_until",
            "updated_at",
        ]
    )


    # ========================================================
    # 自動戦闘
    # ========================================================

    engine = BattleEngine(
        character,
        enemies,
        floor=selected_floor,
    )

    battle_result = engine.run()

    # ========================================================
    # 探索ドロップ
    # ========================================================

    drop_result = None

    # 敵を倒した場合だけドロップ抽選
    if battle_result["winner"] == "player":

        drop_result = (
            grant_exploration_drop(
                character=character,
                floor=selected_floor,
            )
        )


    # ========================================================
    # EXP / レベルアップ
    # ========================================================

    growth_result = None

    # 勝利・敗北を問わず、
    # EXPがある場合は成長処理を実行する
    if battle_result["exp_gained"] > 0:

        growth_result = apply_exploration_exp(
            character,
            battle_result["exp_gained"],
        )

    else:
        # 引き分けなどEXPがない場合も
        # 探索終了時にHP / MPを全回復する

        character.current_hp = (
            character.max_hp
        )

        character.current_mp = (
            character.max_mp
        )

        character.save(
            update_fields=[
                "current_hp",
                "current_mp",
                "updated_at",
            ]
        )

    # ========================================================
    # 戦闘画面表示
    # ========================================================

    return render(
        request,
        "battle.html",
        {
            "character": character,

            # 既存画面との互換用
            "enemy": enemies[0],

            # 今回出現した敵全部
            "enemies": enemies,

            # 探索した階層
            "selected_floor": selected_floor,

            # BattleEngineの結果全部
            "battle_result": battle_result,

            # テンプレートで扱いやすいよう
            # ログも単独で渡す
            "battle_logs": battle_result["logs"],

            # EXP
            "exp_gained": battle_result["exp_gained"],

            # レベルアップ情報
            "growth_result": growth_result,

            # クールタイム
            "cooldown_seconds": cooldown_seconds,


            # ドロップ結果
            "drop_result": drop_result,
        },
    )


@login_required
def tactics(request):
    character = request.user.character

    # 現在の職業で使用できるスキルだけ取得
    available_skills = (
        Skill.objects
        .filter(job=character.job)
        .order_by("id")
    )

    error_message = None

    if request.method == "POST":

        # 保存前に5枠すべてチェックする
        new_presets = []

        for slot in range(1, 6):

            skill_id = request.POST.get(
                f"skill_{slot}"
            )

            use_count_value = request.POST.get(
                f"use_count_{slot}",
                "1",
            )

            # スキル未選択なら空きスロット
            if not skill_id:
                new_presets.append(
                    {
                        "slot": slot,
                        "skill": None,
                        "use_count": 1,
                    }
                )
                continue

            # 他職業のスキルをPOSTで送られても使用不可
            skill = available_skills.filter(
                id=skill_id
            ).first()

            if skill is None:
                error_message = (
                    f"SLOT {slot} に使用できない"
                    "スキルが指定されています。"
                )
                break

            # パッシブは使用回数を使わない
            if skill.is_passive:
                use_count = 1

            else:
                try:
                    use_count = int(
                        use_count_value
                    )

                except (TypeError, ValueError):
                    error_message = (
                        f"SLOT {slot} の使用回数が"
                        "正しくありません。"
                    )
                    break

                if use_count < 1:
                    error_message = (
                        f"SLOT {slot} の使用回数は"
                        "1以上にしてください。"
                    )
                    break

            new_presets.append(
                {
                    "slot": slot,
                    "skill": skill,
                    "use_count": use_count,
                }
            )

        # エラーがなければDBへ保存
        if error_message is None:

            with transaction.atomic():

                for data in new_presets:

                    slot = data["slot"]
                    skill = data["skill"]

                    # 空きスロットなら既存設定を削除
                    if skill is None:

                        SkillPreset.objects.filter(
                            character=character,
                            slot=slot,
                        ).delete()

                        continue

                    SkillPreset.objects.update_or_create(
                        character=character,
                        slot=slot,
                        defaults={
                            "skill": skill,
                            "use_count": data["use_count"],
                        },
                    )

            messages.success(
                request,
                "スキルプリセットを保存しました。",
            )

            return redirect(
                "battle:tactics"
            )

    # 現在保存されているプリセット
    preset_dict = {
        preset.slot: preset
        for preset in SkillPreset.objects.filter(
            character=character
        ).select_related("skill")
    }

    # SLOT1～5を必ず画面に表示する
    preset_slots = []

    for slot in range(1, 6):
        preset_slots.append(
            {
                "slot": slot,
                "preset": preset_dict.get(
                    slot
                ),
            }
        )

    return render(
        request,
        "tactics.html",
        {
            "character": character,
            "available_skills": available_skills,
            "preset_slots": preset_slots,
            "error_message": error_message,
        },
    )

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
    #
    # 探索または闘技場を実行してCT中の場合、
    # 新しく闘技場戦闘を開始できない。
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

    # 同じ階に相手がいなければ戦闘しない
    if opponent is None:
        messages.warning(
            request,
            "この階には対戦相手がいません。"
        )

        return redirect("home")

    # ========================================
    # 戦闘用一時HP
    #
    # DB上の current_hp はまだ変更しない。
    #
    # この闘技場戦闘の中だけで使用するHP。
    # ========================================

    character_battle_hp = character.current_hp
    opponent_battle_hp = opponent.current_hp

    # ========================================
    # 先攻判定
    #
    # AGIが高い方を先攻にする。
    #
    # AGIが同じ場合だけランダム。
    # ========================================

    if character.agility > opponent.agility:

        first_attacker = character
        second_attacker = opponent

    elif character.agility < opponent.agility:

        first_attacker = opponent
        second_attacker = character

    else:

        if random.choice([True, False]):

            first_attacker = character
            second_attacker = opponent

        else:

            first_attacker = opponent
            second_attacker = character

    # ========================================
    # 戦闘ログ
    #
    # 各攻撃結果をリストに保存して、
    # 最後にHTMLへ渡す。
    #
    # 例：
    #
    # 1ターン目
    # test の攻撃
    # 命中
    # 3ダメージ
    #
    # ArenaTwo の攻撃
    # ミス
    # ========================================

    battle_logs = []

    # ========================================
    # ターン設定
    #
    # 1ターン目から開始。
    #
    # 万が一、お互い倒れない状態になっても
    # 無限ループしないよう最大100ターン。
    # ========================================

    turn = 1
    max_turns = 100

    # ========================================
    # 戦闘ループ
    #
    # 自分と相手のHPが両方残っている間、
    # ターンを繰り返す。
    # ========================================

    while (
        character_battle_hp > 0
        and opponent_battle_hp > 0
        and turn <= max_turns
    ):

        # ====================================
        # 先攻側の命中率計算
        #
        # 基本命中率 80%
        #
        # ＋ 攻撃側DEX
        # － 防御側DEX
        #
        # 最低10%
        # 最大95%
        # ====================================

        first_hit_rate = 80 + (
            first_attacker.dexterity
            - second_attacker.dexterity
        )

        first_hit_rate = max(
            10,
            min(
                95,
                first_hit_rate
            )
        )

        # ====================================
        # 先攻側の命中判定
        # ====================================

        first_attack_hit = (
            random.randint(1, 100)
            <= first_hit_rate
        )

        # ミスした場合は0ダメージ
        first_damage = 0

        # ====================================
        # 先攻側のダメージ計算
        #
        # STR - VIT
        #
        # 命中時は最低1ダメージ保証。
        # ====================================

        if first_attack_hit:

            first_damage = max(
                1,
                (
                    first_attacker.strength
                    - second_attacker.vitality
                )
            )

            # =================================
            # 攻撃対象が自分の場合
            # =================================

            if second_attacker == character:

                character_battle_hp = max(
                    0,
                    character_battle_hp
                    - first_damage
                )

            # =================================
            # 攻撃対象が相手の場合
            # =================================

            else:

                opponent_battle_hp = max(
                    0,
                    opponent_battle_hp
                    - first_damage
                )

        # ====================================
        # 先攻側の攻撃結果をログへ保存
        # ====================================

        battle_logs.append(
            {
                "turn": turn,
                "attacker": first_attacker.name,
                "hit": first_attack_hit,
                "hit_rate": first_hit_rate,
                "damage": first_damage,
                "character_hp": character_battle_hp,
                "opponent_hp": opponent_battle_hp,
            }
        )

        # ====================================
        # 先攻側の攻撃だけで決着した場合
        #
        # HP0のキャラクターは反撃できないため、
        # ここで戦闘ループを終了する。
        # ====================================

        if (
            character_battle_hp <= 0
            or opponent_battle_hp <= 0
        ):
            break

        # ====================================
        # 後攻側の命中率計算
        # ====================================

        second_hit_rate = 80 + (
            second_attacker.dexterity
            - first_attacker.dexterity
        )

        second_hit_rate = max(
            10,
            min(
                95,
                second_hit_rate
            )
        )

        # ====================================
        # 後攻側の命中判定
        # ====================================

        second_attack_hit = (
            random.randint(1, 100)
            <= second_hit_rate
        )

        second_damage = 0

        # ====================================
        # 後攻側のダメージ計算
        # ====================================

        if second_attack_hit:

            second_damage = max(
                1,
                (
                    second_attacker.strength
                    - first_attacker.vitality
                )
            )

            # =================================
            # 攻撃対象が自分の場合
            # =================================

            if first_attacker == character:

                character_battle_hp = max(
                    0,
                    character_battle_hp
                    - second_damage
                )

            # =================================
            # 攻撃対象が相手の場合
            # =================================

            else:

                opponent_battle_hp = max(
                    0,
                    opponent_battle_hp
                    - second_damage
                )

        # ====================================
        # 後攻側の攻撃結果をログへ保存
        # ====================================

        battle_logs.append(
            {
                "turn": turn,
                "attacker": second_attacker.name,
                "hit": second_attack_hit,
                "hit_rate": second_hit_rate,
                "damage": second_damage,
                "character_hp": character_battle_hp,
                "opponent_hp": opponent_battle_hp,
            }
        )

        # ====================================
        # 次のターンへ
        # ====================================

        turn += 1

    # ========================================
# 勝敗判定
#
# 相手HPが0
# → 挑戦者の勝利
#
# 自分HPが0
# → 挑戦者の敗北
#
# 100ターン以内に決着しなかった場合も
# 挑戦者の敗北とする。
# ========================================

    if (
    character_battle_hp > 0
    and opponent_battle_hp <= 0
):

        battle_result = "win"

    else:

    # 自分のHPが0になった場合
    # または
    # 100ターンで決着しなかった場合
        battle_result = "loss"

      # ========================================
      # 闘技場報酬
      # ========================================

    if battle_result == "win":
        gained_exp = random.randint(9, 12)
    else:
        gained_exp = 7

    character.exp += gained_exp

    item_drop_rate = min(
        1 + character.arena_win_streak,
        10
    )

    dropped_item = None

    roll = random.randint(1, 100)

    if roll <= item_drop_rate:

        dropped_item = (
            Item.objects
            .filter(category=Item.Category.MATERIAL)
            .order_by("?")
            .first()
        )

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

        if not created:
            inventory_item.quantity += 1

            inventory_item.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )
        # ========================================
# 闘技場戦績更新
#
# 勝利：
# ・連勝数 +1
# ・直近結果を win
#
# 敗北：
# ・連勝数を0に戻す
# ・直近結果を loss
# ・次の階への挑戦を解禁
# ========================================

    if battle_result == "win":

        character.arena_win_streak += 1
        character.arena_last_result = "win"

    else:

        character.arena_win_streak = 0
        character.arena_last_result = "loss"
        character.arena_next_floor_unlocked = True
    # ========================================
    # 共通CT開始
    #
    # 闘技場を1回実行したので、
    # 探索と共通のCTを開始する。
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
        "exp",
        "arena_win_streak",
        "arena_last_result",
        "arena_next_floor_unlocked",
        "exploration_cooldown_until",
        "updated_at",
    ]
)
   # ========================================
# 闘技場画面表示
#
# HTMLへ戦闘結果を渡す。
# ========================================

    return render(
    request,
    "arena_battle.html",
    {
        "character": character,
        "opponent": opponent,

        # 最初に誰が先攻だったか
        "first_attacker": first_attacker,

        # 全ターンの戦闘ログ
        "battle_logs": battle_logs,

        # win / loss
        "battle_result": battle_result,

        # 戦闘終了時の自分HP
        "character_battle_hp": character_battle_hp,

        # 戦闘終了時の相手HP
        "opponent_battle_hp": opponent_battle_hp,

        # 最終ターン数
        "turn_count": turn,

        # 共通CT
        "cooldown_seconds": cooldown_seconds,

        # 獲得経験値
        "gained_exp": gained_exp,

        # アイテムドロップ率
        "item_drop_rate": item_drop_rate,

        # 実際に落ちたアイテム
        "dropped_item": dropped_item,
    }
)
