import random


from apps.battle.engine.calculations import (
    BattleCalculationsMixin,
)
from apps.battle.engine.state import (
    BattleStateMixin,
)
from apps.battle.engine.stats import (
    BattleStatsMixin,
)
from apps.battle.engine.turns import (
    BattleTurnsMixin,
)
from apps.battle.engine.core import (
    BattleCoreMixin,
)
from apps.battle.engine.attacks import (
    BattleAttacksMixin,
)
from apps.battle.engine.action_finish import (
    BattleActionFinishMixin,
)
from apps.battle.engine.skill_executor import (
    BattleSkillExecutorMixin,
)


from apps.battle.engine.skills.grappler import (
    GrapplerSkillsMixin,
)
from apps.battle.engine.skills.warrior import (
    WarriorSkillsMixin,
)
from apps.battle.engine.skills.hunter import (
    HunterSkillsMixin,
)
from apps.battle.engine.skills.wizard import (
    WizardSkillsMixin,
)
from apps.battle.engine.skills.priest import (
    PriestSkillsMixin,
)
from apps.battle.engine.skills.wanderer import (
    WandererSkillsMixin,
)
from apps.battle.engine.skills.assassin import (
    AssassinSkillsMixin,
)

from apps.battle.combatants import (
    PlayerCombatant,
    EnemyCombatant,
)


class BattleEngine(
    BattleCalculationsMixin,
    BattleStateMixin,
    BattleStatsMixin,
    BattleTurnsMixin,
    BattleCoreMixin,
    BattleAttacksMixin,
    BattleActionFinishMixin,
    BattleSkillExecutorMixin,
    GrapplerSkillsMixin,
    WarriorSkillsMixin,
    HunterSkillsMixin,
    WizardSkillsMixin,
    PriestSkillsMixin,
    WandererSkillsMixin,
    AssassinSkillsMixin,
):


    def __init__(
        self,
        character,
        enemies,
        floor=None,
        starting_stamina=100,
    ):

        self.character = character

        # ============================================================
        # プレイヤー
        # ============================================================

        self.player_combatant = PlayerCombatant(
            character,
            starting_stamina=starting_stamina,
        )

        # ============================================================
        # 戦闘に参加する敵
        # ============================================================

        # 既存の1体指定にも対応する
        if not isinstance(
            enemies,
            (list, tuple),
        ):
            enemies = [enemies]

        # 敵は1～3体
        if not 1 <= len(enemies) <= 3:
            raise ValueError(
                "敵の数は1～3体で指定してください。"
            )

        self.enemy_combatants = [
            EnemyCombatant(enemy)
            for enemy in enemies
        ]

        # 最初のターゲット
        self.current_enemy_index = 0


        # ============================================================
        # 今回戦闘している探索階層
        # ============================================================

        if floor is not None:
            self.floor = floor

        else:
            # 既存テストなどでfloorが渡されなかった場合は、
            # 最初の敵の階層を使用する。
            self.floor = (
                self.enemy_combatants[0]
                .enemy
                .floor
            )


        # ========================================
        # 戦闘中の最大HP・MP
        # ========================================

        self.player_max_hp = (
            self.get_player_max_hp()
        )

        self.player_max_mp = (
            self.get_player_max_mp()
        )

        # 戦闘ログ
        self.logs = []

        # プリセットスキルの情報を取得
        self.presets = list(
            character.skill_presets
            .select_related("skill")
            .order_by("slot")
        )

        # プリセットスキルの残り使用回数を管理する辞書
        self.remaining_uses = {
            preset.id: preset.use_count
            for preset in self.presets
            if not preset.skill.is_passive
        }

        # プリセットスキルの現在のスロット位置を管理するインデックス
        self.preset_index = 0


        # ===== 放浪人用の戦闘状態 =====

        # 歩行者の残り有効行動数
        self.walker_turns = 0

        # 行動原理：自由の累積補正
        # 0.02 = +2%
        self.freedom_bonus = 0.0

        # パッシブがプリセットに入っているか
        self.freedom_active = any(
            preset.skill.code == "principle_of_freedom"
            for preset in self.presets
        )

        # 蜃気楼
        # 複数敵戦闘実装時に利用する
        self.mirage_active = False


        # ===== 拳闘士用の戦闘状態 =====

        # 「闘魂」の残り有効行動数
        #
        # 0なら効果なし。
        # 発動すると3になり、
        # その後の自分の行動終了ごとに1ずつ減る。
        self.fighting_spirit_turns = 0


        # ===== 重戦士用の戦闘状態 =====

        # 「一撃必殺」使用後、
        # 次の自分の行動を休む
        self.skip_next_player_action = False

        # 「鋼の体」
        # 次の自分の行動まで物理ダメージ40%軽減
        self.steel_body_turns = 0

        # 「盤石の構え」
        # 次の自分の行動まで被ダメージ20%軽減
        # 味方をかばう処理はパーティ戦実装時に追加
        self.solid_stance_turns = 0

        # 「反撃の構え」
        # 2行動の間有効
        self.counter_stance_turns = 0

        # 1回の発動につき最大3回まで反撃
        self.counter_remaining = 0


        # ===== 狩人用の戦闘状態 =====

        # 「ハンターアイ」
        # 3行動の間 DEX +10%、LUK +5%
        self.hunter_eye_turns = 0

        # 「ハイド」
        # 3行動の間
        # AGI -10%
        # 敵からの命中率 -10%
        self.hide_turns = 0

        # ===== ウィザード用の戦闘状態 =====

        # 「フロストアーマー」
        # 5行動の間有効
        self.frost_armor_turns = 0

        # ===== プリースト用の戦闘状態 =====

        # 「ヒーリングシールド」
        # 3行動の間 VIT +20%
        self.healing_shield_turns = 0

        # 「浄化」
        # 次に受けるデバフを1回無効化
        self.purification_guard = False

        # 「リザレク」
        # 1戦につき1回
        self.resurrection_used = False

        # ===== 暗殺者用の戦闘状態 =====

        # 「ステルス」
        #
        # 効果時間はまだ正式決定していないため、
        # 現段階では戦闘中の有効フラグとして管理する。
        self.stealth_active = False

        # 「シャドウステップ」
        # 発動後3行動の間、被ダメージの40%を反射
        self.shadow_step_turns = 0

        # ===== 種族パッシブ用の戦闘状態 =====

        # エルフ「森の加護」
        #
        # 自分の行動終了ごとにAGI +1%
        # 最大+10%
        self.elf_agility_bonus = 0.0
        