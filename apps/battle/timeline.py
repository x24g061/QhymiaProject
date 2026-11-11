"""戦闘結果画面用の時系列スナップショット。戦闘計算には関与しない。"""
import re


def _status(name, hp, max_hp, mp, max_mp):
    hp = max(0, int(hp))
    mp = max(0, int(mp))
    max_hp = max(0, int(max_hp))
    max_mp = max(0, int(max_mp))
    return {
        "name": name,
        "hp": hp,
        "max_hp": max_hp,
        "mp": mp,
        "max_mp": max_mp,
        "hp_percent": min(100, round(hp * 100 / max_hp)) if max_hp else 0,
        "mp_percent": min(100, round(mp * 100 / max_mp)) if max_mp else 0,
    }


def exploration_turn_snapshot(engine, side, actor, logs, number):
    return {
        "turn": number,
        "side": side,
        "actor": actor,
        "player": _status(engine.character.name, engine.player_hp,
                          engine.player_max_hp, engine.player_mp, engine.player_max_mp),
        "opponents": [
            _status(enemy.name, enemy.hp, enemy.max_hp, enemy.mp, enemy.max_mp)
            for enemy in engine.enemy_combatants
        ],
        "logs": list(logs),
    }


def arena_turn_snapshot(engine, side, actor, logs, number):
    return {
        "turn": number,
        "side": side,
        "actor": actor,
        "player": _status(engine.challenger.name, engine.challenger_hp,
                          engine.challenger_combatant.max_hp, engine.challenger_mp,
                          engine.challenger_combatant.max_mp),
        "opponents": [
            _status(engine.defender.name, engine.defender_hp,
                    engine.defender_combatant.max_hp, engine.defender_mp,
                    engine.defender_combatant.max_mp),
        ],
        "logs": list(logs),
    }


_NORMAL_ATTACK = re.compile(
    r"^(.+?)の攻撃！\s*(クリティカル！\s*)?(.+?)に(\d+)ダメージ！$"
)
_DAMAGE_NUMBER = re.compile(r"(\d+)(?=\s*(?:の)?ダメージ)")


def _present_log(raw):
    match = _NORMAL_ATTACK.fullmatch(raw.strip())
    if match:
        attacker, critical, target, amount = match.groups()
        text = f"{attacker}は{target}を攻撃した。 "
        if critical:
            text += "会心の一撃！ "
        text += f"{amount} のダメージ。"
    else:
        text = str(raw).replace("EXPを獲得！", " EXPを獲得！")
    chunks = _DAMAGE_NUMBER.split(text)
    parts = []
    for i, chunk in enumerate(chunks):
        if chunk:
            parts.append({"text": chunk, "damage": i % 2 == 1})
    return {"parts": parts, "critical": "会心" in text or "クリティカル" in text}


def prepare_timeline(timeline):
    """DB JSON と当該リクエストの辞書をテンプレート用に変換する。"""
    prepared = []
    for turn in timeline or []:
        event = dict(turn)
        event["messages"] = [_present_log(log) for log in event.get("logs", [])]
        # 古いレコードやテストの最小データでもレンダリング可能にする
        event.setdefault("opponents", [])
        event.setdefault("player", {})
        prepared.append(event)
    return prepared
