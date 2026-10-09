import random
import math


from apps.battle.engine.calculations import (
    ATTRIBUTE_MULTIPLIERS,
    calculate_hit_rate,
    calculate_physical_damage,
    roll_percent,
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
    BattleStateMixin,
    BattleStatsMixin,
    BattleTurnsMixin,
    BattleCoreMixin,
    BattleAttacksMixin,
    BattleActionFinishMixin,
    GrapplerSkillsMixin,
    WarriorSkillsMixin,
    HunterSkillsMixin,
    WizardSkillsMixin,
    PriestSkillsMixin,
    WandererSkillsMixin,
    AssassinSkillsMixin,
):


    def get_player_max_hp(self):
        """
        戦闘中の最大HPを返す。

        プリースト:
        最大HP +5%
        """

        max_hp = self.character.max_hp

        if self.character.job == "priest":
            max_hp = math.ceil(
                max_hp * 1.05
            )

        return max_hp


    def get_player_max_mp(self):
        """
        戦闘中の最大MPを返す。

        プリースト:
        最大MP +5%
        """

        max_mp = self.character.max_mp

        if self.character.job == "priest":
            max_mp = math.ceil(
                max_mp * 1.05
            )

        return max_mp


    def get_stamina_stat_multiplier(self):
        """
        現在STから疲労による能力補正を返す。

        100ST → 1.00倍
         50ST → 0.75倍
          0ST → 0.50倍

        0STでも能力値の50%は残る。
        """

        if self.player_max_stamina <= 0:
            return 0.50

        stamina_ratio = (
            self.player_stamina
            / self.player_max_stamina
        )

        stamina_ratio = min(
            1.0,
            max(
                0.0,
                stamina_ratio,
            ),
        )

        return (
            0.50
            + stamina_ratio * 0.50
        )


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


    def get_floor_exp_range(self):
        """
        探索階層に応じた
        1戦闘あたりのEXP範囲を返す。
        """

        if self.floor <= 4:
            return 7, 12

        if self.floor <= 8:
            return 8, 14

        return 10, 16
        

    def execute_player_skill(self, skill):
        """プレイヤーのスキル効果を実行する。"""


        # ========================================================
        # 蜃気楼
        # ========================================================
        #
        # 次に発動する「単体攻撃スキル」1回を
        # 敵全体へ拡張する。
        #
        # 補助・回復スキルでは消費しない。
        # もともと全体攻撃のスキルでも消費しない。
        # ========================================================

        already_all_target = {
            "shock_wave",
            "flare_blade",
            "explosion",
        }

        is_attack_skill = (
            skill.skill_type
            in (
                "physical",
                "magic",
            )
        )

        if (
            self.mirage_active
            and is_attack_skill
            and skill.code
            not in already_all_target
        ):

            # 現在のターゲットを保存
            original_index = (
                self.current_enemy_index
            )

            # 攻撃開始時点で生きている敵
            target_indexes = (
                self.get_alive_enemy_indexes()
            )

            # 先に解除する。
            # execute_player_skillを再度呼ぶため、
            # ここでFalseにしないと無限ループになる。
            self.mirage_active = False

            self.logs.append(
                "蜃気楼の効果！ "
                "攻撃対象が敵全体になった！"
            )

            for index in target_indexes:

                # 途中で倒れていた場合は飛ばす
                if not (
                    self.enemy_combatants[index]
                    .is_alive()
                ):
                    continue

                self.current_enemy_index = index

                # 同じスキルをこの敵へ実行
                self.execute_player_skill(
                    skill
                )

            # 元のターゲットへ戻す
            self.current_enemy_index = (
                original_index
            )

            return


        # ============================
        # 拳闘士
        # ============================

        if skill.code == "double_punch":
            self.skill_double_punch()
            return

        if skill.code == "shock_wave":
            self.skill_shock_wave()
            return

        if skill.code == "rapid_barrage":
            self.skill_rapid_barrage()
            return

        if skill.code == "fighting_spirit":
            self.skill_fighting_spirit()
            return

        if skill.code == "true_fist":
            self.skill_true_fist()
            return

        # ============================
        # 重戦士
        # ============================

        if skill.code == "flare_blade":
            self.skill_flare_blade()
            return

        if skill.code == "one_hit_kill":
            self.skill_one_hit_kill()
            return

        if skill.code == "steel_body":
            self.skill_steel_body()
            return

        if skill.code == "solid_stance":
            self.skill_solid_stance()
            return

        if skill.code == "counter_stance":
            self.skill_counter_stance()
            return

        # ============================
        # 狩人
        # ============================

        if skill.code == "rapid_shot":
            self.skill_rapid_shot()
            return

        if skill.code == "sleep_arrow":
            self.skill_sleep_arrow()
            return

        if skill.code == "hunter_eye":
            self.skill_hunter_eye()
            return

        if skill.code == "hide":
            self.skill_hide()
            return

        if skill.code == "poison_arrow":
            self.skill_poison_arrow()
            return

        # ============================
        # ウィザード
        # ============================

        if skill.code == "stella":
            self.skill_stella()
            return

        if skill.code == "fire":
            self.skill_fire()
            return

        if skill.code == "megido":
            self.skill_megido()
            return

        if skill.code == "explosion":
            self.skill_explosion()
            return

        if skill.code == "frost_armor":
            self.skill_frost_armor()
            return

        # ============================
        # プリースト
        # ============================

        if skill.code == "judgement":
            self.skill_judgement()
            return

        if skill.code == "healing_shield":
            self.skill_healing_shield()
            return

        if skill.code == "purification":
            self.skill_purification()
            return

        if skill.code == "resurrection":
            self.skill_resurrection()
            return

        if skill.code == "anti_jail":
            self.skill_anti_jail()
            return

        # ============================
        # 放浪人
        # ============================

        if skill.code == "strike_core":
            self.skill_strike_core()
            return

        if skill.code == "mirage":
            self.skill_mirage()
            return

        if skill.code == "short_rest":
            self.skill_short_rest()
            return

        if skill.code == "walker":
            self.skill_walker()
            return

        # ============================
        # 暗殺者
        # ============================

        if skill.code == "surprise_attack":
            self.skill_surprise_attack()
            return

        if skill.code == "poison_dagger":
            self.skill_poison_dagger()
            return

        if skill.code == "stealth":
            self.skill_stealth()
            return

        if skill.code == "shadow_step":
            self.skill_shadow_step()
            return

        if skill.code == "flashbang":
            self.skill_flashbang()
            return

        # ============================
        # 未実装スキル
        # ============================

        self.logs.append(
            f"「{skill.name}」の効果は"
            "まだ実装されていません。"
        )


    @staticmethod
    def calculate_hit_rate(
        attacker_dex,
        defender_agi,
    ):
        """
        命中率
        60 + 39 × DEX / (DEX + 敵AGI)
        """

        return calculate_hit_rate(
            attacker_dex,
            defender_agi,
        )


    @staticmethod
    def calculate_physical_damage(
        strength,
        defender_vit,
    ):
        return calculate_physical_damage(
            strength,
            defender_vit,
        )


    @staticmethod
    def roll_percent(rate):
        return roll_percent(rate)