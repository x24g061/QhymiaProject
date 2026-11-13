"""
探索・闘技場共通のAGI行動ゲージ計算。
"""

GAUGE_THRESHOLD = 100.0


def calculate_gauge_gain(effective_agi, reference_agi):
    """
    1ループあたりのゲージ増加量。

    reference_agi:
        戦闘開始時の最高AGI。戦闘中は固定する。

    effective_agi:
        現在の有効AGI。疲労やバフを反映可能。
    """
    reference = max(1.0, float(reference_agi))
    agility = max(0.0, float(effective_agi))

    gain = 90.0 * agility / reference

    return min(95.0, max(1.0, gain))


def action_priority(
    gauge_before,
    gauge_gain,
    effective_agi,
    stable_order=0,
):
    """
    同じループで行動可能な参加者の優先順位。

    1. ゲージ100への到達が早い
    2. 同時到達なら有効AGIが高い
    3. 完全同値なら固定順

    戻り値が小さい参加者から行動する。
    """
    if gauge_gain <= 0:
        raise ValueError("ゲージ増加量は正の値が必要です")

    arrival = max(
        0.0,
        (GAUGE_THRESHOLD - gauge_before) / gauge_gain,
    )

    return (
        arrival,
        -float(effective_agi),
        stable_order,
    )
