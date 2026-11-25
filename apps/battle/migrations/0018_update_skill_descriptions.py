from django.db import migrations


SKILL_DESCRIPTIONS = {
    # 拳闘士
    "double_punch": "敵に連続して物理攻撃を行う。",
    "shock_wave": "衝撃波を放ち、敵全体に物理攻撃を行う。",
    "rapid_barrage": "敵にランダムな回数の連続攻撃を行う。",
    "fighting_spirit": "一定期間、自身のSTRを上昇させる。",
    "true_fist": "STRとLUKに応じた強力な物理攻撃を行う。",

    # 重戦士
    "flare_blade": "炎の力を宿した攻撃で敵全体にダメージを与える。",
    "one_hit_kill": "強力な物理攻撃を行うが、次の行動ができなくなる。",
    "steel_body": "一定期間、受ける物理ダメージを軽減する。",
    "solid_stance": "味方への単体攻撃を代わりに受け、自身の被ダメージを軽減する。",
    "counter_stance": "一定期間、攻撃を受けると物理攻撃で反撃する。反撃回数には上限がある。",

    # 狩人
    "rapid_shot": "必ず命中する物理攻撃を行う。",
    "sleep_arrow": "物理攻撃を行い、一定確率で敵を眠らせる。",
    "hunter_eye": "一定期間、自身のDEXとLUKを上昇させる。",
    "hide": "一定期間、自身のAGIが低下する代わりに敵の攻撃が命中しにくくなる。",
    "poison_arrow": "物理攻撃を行い、命中時に一定確率で毒を付与する。",

    # ウィザード
    "stella": "敵に連続して魔法攻撃を行う。",
    "fire": "炎の魔法で敵にダメージを与える。",
    "megido": "敵のINTによる防御を無視する魔法攻撃を行う。",
    "explosion": "爆発を引き起こし、敵全体に魔法攻撃を行う。",
    "frost_armor": "一定期間、魔法ダメージを軽減する。属性有利時は効果が高まる。",

    # プリースト
    "judgement": "魔法攻撃を行い、一定確率で麻痺を付与する。",
    "healing_shield": "VITに応じてHPを回復し、一定期間VITを上昇させる。",
    "purification": "ランダムな弱体効果を解除し、次に受ける弱体効果を無効化する。",
    "resurrection": "戦闘不能の味方を復活させる。戦闘中の使用回数には制限がある。",
    "anti_jail": "敵に連続して魔法攻撃を行う。",

    # 放浪人
    "strike_core": "STRとLUKに応じた物理攻撃を行う。",
    "mirage": "攻撃の対象を敵全体に変更する。",
    "short_rest": "STRに応じてHPを回復する。",
    "walker": "一定期間、AGIが低下する代わりにSTRとDEXを上昇させる。",
    "principle_of_freedom": "プリセット中は常時発動し、行動するたびに有効ステータスが上昇する。上昇量には上限がある。",

    # 暗殺者
    "surprise_attack": "成功すると強力な物理攻撃を行う。失敗すると自身がダメージを受ける。",
    "poison_dagger": "物理攻撃を行い、命中時に一定確率で毒を付与し、敵のDEXを低下させる。",
    "stealth": "自身の回避率を上昇させる。回避率には上限がある。",
    "shadow_step": "一定期間、受けたダメージの一部を反射する。自身もダメージを受ける。ステルス中は必ず発動する。",
    "flashbang": "敵全体に一定確率で麻痺を付与する。",
}


def update_skill_descriptions(apps, schema_editor):
    Skill = apps.get_model("battle", "Skill")
    db_alias = schema_editor.connection.alias

    for code, description in SKILL_DESCRIPTIONS.items():
        Skill.objects.using(db_alias).filter(
            code=code
        ).update(
            description=description
        )


class Migration(migrations.Migration):

    dependencies = [
        ("battle", "0017_boss_balance_v1"),
    ]

    operations = [
        migrations.RunPython(
            update_skill_descriptions,
        ),
    ]
