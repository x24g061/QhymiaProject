"""ボスを行動者として、既存のプレイヤースキル実行器へ接続する。"""
from types import SimpleNamespace

from apps.battle.models import Skill
from apps.battle.services import BattleEngine


class EnemySkillActor(BattleEngine):
    """状態は敵Combatantに、スキル倍率・条件は既存Mixinに委譲する。

    run()やDB保存は行わない。親の探索エンジンが行動順と勝敗を管理する。
    """

    def __init__(self, battle, combatant):
        self.battle = battle
        self.player_combatant = combatant
        self.character = SimpleNamespace(name=combatant.name, race="")
        self.player_max_hp = combatant.max_hp
        self.player_max_mp = combatant.max_mp
        self.enemy_combatants = [battle.player_combatant]
        self.current_enemy_index = 0
        self.logs = battle.logs
        codes = list(combatant.enemy.skill_codes)
        skills = Skill.objects.in_bulk(codes, field_name="code") if codes else {}
        missing = set(codes) - skills.keys()
        if missing:
            raise ValueError(f"ボスのスキルが未登録です: {', '.join(sorted(missing))}")
        self.presets = [
            SimpleNamespace(id=slot, slot=slot, skill=skills[code], use_count=99)
            for slot, code in enumerate(codes, 1)
        ]
        self.remaining_uses = {
            preset.id: preset.use_count for preset in self.presets
            if not preset.skill.is_passive
        }
        self.preset_index = 0
        self.initialize_skill_state()

    @property
    def enemy(self):
        return SimpleNamespace(
            name=self.battle.character.name,
            attribute=self.battle.get_player_main_attribute(),
        )

    def get_player_base_stat(self, stat_name):
        return getattr(self.player_combatant.enemy, stat_name)

    def get_enemy_stat(self, stat_name, combatant=None):
        return self.battle.get_player_stat(stat_name)

    def get_player_main_attribute(self):
        # 数値フィールドを持たない無属性には得意属性補正を付与しない。
        attribute = self.player_combatant.enemy.attribute
        return attribute if attribute not in ("neutral", "none") else None

    def get_attack_equipment_multiplier(self, effect_code):
        return 1.0

    def apply_equipment_status_effects(self):
        pass

    def get_target_skill_actor(self):
        return self.battle

    def process_action_status(self, combatant):
        # 親エンジンの_enemy_turn_implで一度だけ処理する。
        return True
