from django.db import migrations


def add_initial_skills(apps, schema_editor):
    Skill = apps.get_model("battle", "Skill")

    skills = [
        # ==============================
        # 拳闘士
        # ==============================
        {
            "code": "double_punch",
            "name": "ダブルパンチ",
            "job": "grappler",
            "attribute": "neutral",
            "skill_type": "physical",
            "mp_cost": 7,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×2.0 の2回攻撃",
        },
        {
            "code": "shock_wave",
            "name": "衝撃波",
            "job": "grappler",
            "attribute": "light",
            "skill_type": "physical",
            "mp_cost": 12,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×1.5 の全体攻撃",
        },
        {
            "code": "rapid_barrage",
            "name": "怒涛連打",
            "job": "grappler",
            "attribute": "fire",
            "skill_type": "physical",
            "mp_cost": 15,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×0.5 を1～10回攻撃",
        },
        {
            "code": "fighting_spirit",
            "name": "闘魂",
            "job": "grappler",
            "attribute": "fire",
            "skill_type": "support",
            "mp_cost": 7,
            "activation_rate": 80,
            "is_passive": False,
            "description": "3行動の間STRを1.10倍にする",
        },
        {
            "code": "true_fist",
            "name": "真拳一殺",
            "job": "grappler",
            "attribute": "neutral",
            "skill_type": "physical",
            "mp_cost": 10,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×2.0 + LUK ×1.5",
        },

        # ==============================
        # 重戦士
        # ==============================
        {
            "code": "flare_blade",
            "name": "フレアブレイド",
            "job": "warrior",
            "attribute": "fire",
            "skill_type": "physical",
            "mp_cost": 5,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×2.2 の全体攻撃",
        },
        {
            "code": "one_hit_kill",
            "name": "一撃必殺",
            "job": "warrior",
            "attribute": "neutral",
            "skill_type": "physical",
            "mp_cost": 7,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×4.0。使用後、次回行動不能",
        },
        {
            "code": "steel_body",
            "name": "鋼の体",
            "job": "warrior",
            "attribute": "rock",
            "skill_type": "support",
            "mp_cost": 5,
            "activation_rate": 80,
            "is_passive": False,
            "description": "1行動の間、物理ダメージを40%軽減",
        },
        {
            "code": "solid_stance",
            "name": "盤石の構え",
            "job": "warrior",
            "attribute": "rock",
            "skill_type": "support",
            "mp_cost": 16,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "1行動の間、味方への単体攻撃を代わりに受ける。"
                "その間、自身の被ダメージを20%軽減"
            ),
        },
        {
            "code": "counter_stance",
            "name": "反撃の構え",
            "job": "warrior",
            "attribute": "neutral",
            "skill_type": "physical_support",
            "mp_cost": 18,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "2行動の間、攻撃を受けた際にSTR ×1.3で反撃。"
                "最大3回"
            ),
        },

        # ==============================
        # 狩人
        # ==============================
        {
            "code": "rapid_shot",
            "name": "ラピッドショット",
            "job": "hunter",
            "attribute": "neutral",
            "skill_type": "physical",
            "mp_cost": 9,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×1.5。確定命中",
        },
        {
            "code": "sleep_arrow",
            "name": "睡眠矢",
            "job": "hunter",
            "attribute": "water",
            "skill_type": "physical",
            "mp_cost": 8,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×1.8。35%で睡眠を付与",
        },
        {
            "code": "hunter_eye",
            "name": "ハンターアイ",
            "job": "hunter",
            "attribute": "neutral",
            "skill_type": "support",
            "mp_cost": 6,
            "activation_rate": 80,
            "is_passive": False,
            "description": "3行動の間、DEX +10%、LUK +5%",
        },
        {
            "code": "hide",
            "name": "ハイド",
            "job": "hunter",
            "attribute": "grass",
            "skill_type": "support",
            "mp_cost": 9,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "3行動の間、AGIを10%低下させ、"
                "敵からの命中率を10%低下させる"
            ),
        },
        {
            "code": "poison_arrow",
            "name": "毒矢",
            "job": "hunter",
            "attribute": "dark",
            "skill_type": "physical",
            "mp_cost": 10,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×1.5。命中時50%で毒を付与",
        },

        # ==============================
        # ウィザード
        # ==============================
        {
            "code": "stella",
            "name": "ステラ",
            "job": "wizard",
            "attribute": "neutral",
            "skill_type": "magic",
            "mp_cost": 15,
            "activation_rate": 80,
            "is_passive": False,
            "description": "INT ×0.7 を4～5回攻撃",
        },
        {
            "code": "fire",
            "name": "ファイヤー",
            "job": "wizard",
            "attribute": "fire",
            "skill_type": "magic",
            "mp_cost": 9,
            "activation_rate": 80,
            "is_passive": False,
            "description": "INT ×1.5 ×(1.0～0.75)",
        },
        {
            "code": "megido",
            "name": "メギド",
            "job": "wizard",
            "attribute": "dark",
            "skill_type": "magic",
            "mp_cost": 13,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "INT ×1.1 ×(1.0～0.5)。"
                "敵INT ×0.3による防御を無視"
            ),
        },
        {
            "code": "explosion",
            "name": "エクスプロージョン",
            "job": "wizard",
            "attribute": "rock",
            "skill_type": "magic",
            "mp_cost": 14,
            "activation_rate": 80,
            "is_passive": False,
            "description": "INT ×2.5 ×(1.0～0.5) の全体攻撃",
        },
        {
            "code": "frost_armor",
            "name": "フロストアーマー",
            "job": "wizard",
            "attribute": "water",
            "skill_type": "support",
            "mp_cost": 9,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "5行動の間、魔法ダメージを30%軽減。"
                "属性有利なら40%軽減"
            ),
        },

        # ==============================
        # プリースト
        # ==============================
        {
            "code": "judgement",
            "name": "ジャッジメント",
            "job": "priest",
            "attribute": "fire",
            "skill_type": "magic",
            "mp_cost": 16,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "INT ×2.0 ×(1.0～0.75)。"
                "50%で麻痺を付与"
            ),
        },
        {
            "code": "healing_shield",
            "name": "ヒーリングシールド",
            "job": "priest",
            "attribute": "grass",
            "skill_type": "heal_support",
            "mp_cost": 12,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "VIT ×1.0分HPを回復し、"
                "3行動の間VIT +20%"
            ),
        },
        {
            "code": "purification",
            "name": "浄化",
            "job": "priest",
            "attribute": "water",
            "skill_type": "support",
            "mp_cost": 6,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "ランダムなデバフを解除し、"
                "次のデバフを1回無効化"
            ),
        },
        {
            "code": "resurrection",
            "name": "リザレク",
            "job": "priest",
            "attribute": "light",
            "skill_type": "heal",
            "mp_cost": 22,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "戦闘不能の味方1人をHP10%で復活。"
                "1戦1回"
            ),
        },
        {
            "code": "anti_jail",
            "name": "アンチジェイル",
            "job": "priest",
            "attribute": "neutral",
            "skill_type": "magic",
            "mp_cost": 13,
            "activation_rate": 80,
            "is_passive": False,
            "description": "INT ×1.8、INT ×2.2 の2回攻撃",
        },

        # ==============================
        # 放浪人
        # ==============================
        {
            "code": "strike_core",
            "name": "核心を突く",
            "job": "wanderer",
            "attribute": "light",
            "skill_type": "physical",
            "mp_cost": 10,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "(STR ×1.0 + LUK ×1.2) "
                "×(1.0～0.5)"
            ),
        },
        {
            "code": "mirage",
            "name": "蜃気楼",
            "job": "wanderer",
            "attribute": "neutral",
            "skill_type": "support",
            "mp_cost": 17,
            "activation_rate": 80,
            "is_passive": False,
            "description": "攻撃を全体化する",
        },
        {
            "code": "short_rest",
            "name": "一時休息",
            "job": "wanderer",
            "attribute": "neutral",
            "skill_type": "heal",
            "mp_cost": 8,
            "activation_rate": 80,
            "is_passive": False,
            "description": "STR ×0.5分HPを回復",
        },
        {
            "code": "walker",
            "name": "歩行者",
            "job": "wanderer",
            "attribute": "water",
            "skill_type": "support",
            "mp_cost": 8,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "3行動の間、AGI -30%、"
                "STR +20%、DEX +5%"
            ),
        },
        {
            "code": "principle_of_freedom",
            "name": "行動原理：自由",
            "job": "wanderer",
            "attribute": "none",
            "skill_type": "passive",
            "mp_cost": 0,
            "activation_rate": 100,
            "is_passive": True,
            "description": (
                "プリセット中は常時発動。"
                "自分の行動終了ごとに全有効ステータス+2%。"
                "最大+10%"
            ),
        },

        # ==============================
        # 暗殺者
        # ==============================
        {
            "code": "surprise_attack",
            "name": "奇襲",
            "job": "assassin",
            "attribute": "neutral",
            "skill_type": "physical",
            "mp_cost": 12,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "発動後40%で成功。"
                "成功時STR ×4.5 ×(1.2～0.8)。"
                "失敗時は自分の現在HPの10%ダメージ"
            ),
        },
        {
            "code": "poison_dagger",
            "name": "ポイズンダガー",
            "job": "assassin",
            "attribute": "grass",
            "skill_type": "physical",
            "mp_cost": 14,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "STR ×1.2。"
                "命中時60%で毒を付与し、DEXを3%低下"
            ),
        },
        {
            "code": "stealth",
            "name": "ステルス",
            "job": "assassin",
            "attribute": "dark",
            "skill_type": "support",
            "mp_cost": 8,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "回避率を10%上昇。"
                "最終回避率は50%を超えない"
            ),
        },
        {
            "code": "shadow_step",
            "name": "シャドウステップ",
            "job": "assassin",
            "attribute": "dark",
            "skill_type": "support",
            "mp_cost": 10,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "3行動の間、受けた攻撃ダメージの40%を反射。"
                "自身は通常通りダメージを受ける。"
                "ステルス中は確定発動"
            ),
        },
        {
            "code": "flashbang",
            "name": "フラッシュバング",
            "job": "assassin",
            "attribute": "light",
            "skill_type": "support",
            "mp_cost": 10,
            "activation_rate": 80,
            "is_passive": False,
            "description": (
                "敵全体に50%で麻痺を付与。"
                "持続1～3行動"
            ),
        },
    ]

    for skill_data in skills:
        Skill.objects.update_or_create(
            code=skill_data["code"],
            defaults=skill_data,
        )


def remove_initial_skills(apps, schema_editor):
    Skill = apps.get_model("battle", "Skill")

    codes = [
        "double_punch",
        "shock_wave",
        "rapid_barrage",
        "fighting_spirit",
        "true_fist",
        "flare_blade",
        "one_hit_kill",
        "steel_body",
        "solid_stance",
        "counter_stance",
        "rapid_shot",
        "sleep_arrow",
        "hunter_eye",
        "hide",
        "poison_arrow",
        "stella",
        "fire",
        "megido",
        "explosion",
        "frost_armor",
        "judgement",
        "healing_shield",
        "purification",
        "resurrection",
        "anti_jail",
        "strike_core",
        "mirage",
        "short_rest",
        "walker",
        "principle_of_freedom",
        "surprise_attack",
        "poison_dagger",
        "stealth",
        "shadow_step",
        "flashbang",
    ]

    Skill.objects.filter(
        code__in=codes
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("battle", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            add_initial_skills,
            remove_initial_skills,
        ),
    ]