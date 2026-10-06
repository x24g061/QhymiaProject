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

    # 探索した時刻
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