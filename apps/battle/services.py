import random

ATTRIBUTE_MULTIPLIERS = {
    "fire": {
        "fire": 1.0,
        "water": 0.8,
        "grass": 1.2,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "water": {
        "fire": 1.2,
        "water": 1.0,
        "grass": 0.8,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "grass": {
        "fire": 0.8,
        "water": 1.2,
        "grass": 1.0,
        "rock": 1.2,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "rock": {
        "fire": 1.2,
        "water": 1.0,
        "grass": 0.8,
        "rock": 0.8,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "light": {
        "fire": 1.0,
        "water": 1.0,
        "grass": 1.0,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.2,
        "neutral": 1.0,
    },
    "dark": {
        "fire": 1.0,
        "water": 1.0,
        "grass": 1.0,
        "rock": 1.0,
        "light": 1.2,
        "dark": 1.0,
        "neutral": 1.0,
    },
    "neutral": {
        "fire": 1.0,
        "water": 1.0,
        "grass": 1.0,
        "rock": 1.0,
        "light": 1.0,
        "dark": 1.0,
        "neutral": 1.0,
    },
}


class BattleEngine:

    def __init__(self, character, enemy):
        self.character = character
        self.enemy = enemy

        # 戦闘中だけ使うHP
        self.player_hp = character.current_hp
        self.enemy_hp = enemy.max_hp

        # イニシアチブ
        self.player_initiative = 0
        self.enemy_initiative = 0

        # 戦闘ログ
        self.logs = []

        # プレイヤーのMPも戦闘中だけ使う
        self.player_mp = character.current_mp

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

        # ===== 敵の状態異常 =====

        # 睡眠
        # 行動不能。最大3行動。
        # 直接攻撃を受けると解除。
        self.enemy_sleep_turns = 0

        # 毒
        # 最大HPの10%ダメージ。
        # 5行動持続。
        self.enemy_poison_turns = 0

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

        # ===== 敵の麻痺状態 =====

        # 最大5行動。
        # 行動時50%で動けない。
        self.enemy_paralysis_turns = 0

        # ===== 暗殺者用の戦闘状態 =====

        # 「ステルス」
        #
        # 効果時間はまだ正式決定していないため、
        # 現段階では戦闘中の有効フラグとして管理する。
        self.stealth_active = False

        # 「シャドウステップ」
        # 発動後3行動の間、被ダメージの40%を反射
        self.shadow_step_turns = 0

        # 「ポイズンダガー」のDEX低下
        #
        # DEX -3%。
        # 持続時間はまだ正式決定していないため、
        # 現段階では戦闘中フラグとして扱う。
        self.enemy_dex_debuff_rate = 0.0


        # ===== 種族パッシブ用の戦闘状態 =====

        # エルフ「森の加護」
        #
        # 自分の行動終了ごとにAGI +1%
        # 最大+10%
        self.elf_agility_bonus = 0.0


    def get_player_stat(self, stat_name):
        """
        戦闘中の有効ステータスを返す。

        対象:
        strength
        intelligence
        dexterity
        agility
        vitality
        luck
        """

        value = getattr(
            self.character,
            stat_name,
        )

        # ===== 職業補正 =====

        job_bonus = {
            "grappler": {
                "strength": 1.10,
            },
            "warrior": {
                "vitality": 1.10,
            },
            "hunter": {
                "dexterity": 1.10,
            },
            "wizard": {
                "intelligence": 1.10,
            },
            "wanderer": {
                "luck": 1.10,
            },
            "assassin": {
                "agility": 1.10,
            },
        }

        job_modifiers = job_bonus.get(
            self.character.job,
            {},
        )

        value *= job_modifiers.get(
            stat_name,
            1.0,
        )


        # ============================
        # 種族パッシブ
        # ============================

        # ===== ヒューマン「努力家」 =====
        #
        # LUK ×1.15

        if (
            self.character.race == "human"
            and stat_name == "luck"
        ):
            value *= 1.15


        # ===== ウィッチ「魔力循環」 =====
        #
        # INT ×1.05
        # MP消費2倍はplayer_turn側で処理する。

        if (
            self.character.race == "witch"
            and stat_name == "intelligence"
        ):
            value *= 1.05


        # ===== ドラゴニア「竜血覚醒」 =====
        #
        # HPが最大HPの50%以下になると
        # STR / VIT ×1.10

        if (
            self.character.race == "dragonia"
            and self.player_hp
            <= self.character.max_hp * 0.50
            and stat_name in (
                "strength",
                "vitality",
            )
        ):
            value *= 1.10


        # ===== エルフ「森の加護」 =====
        #
        # 行動するたびAGIが1%ずつ上昇。
        # 最大10%。

        if (
            self.character.race == "elf"
            and stat_name == "agility"
        ):
            value *= (
                1.0
                + self.elf_agility_bonus
            )


        # ===== 闘魂 =====
        # 効果中はSTRをさらに1.10倍する。
        # 拳闘士自身の職業補正
        # STR ×1.10
        # とは別の補正として掛ける。

        if (
            self.fighting_spirit_turns > 0
            and stat_name == "strength"
        ):
            value *= 1.10        

        # ===== 歩行者 =====

        if self.walker_turns > 0:

            if stat_name == "agility":
                value *= 0.70

            elif stat_name == "strength":
                value *= 1.20

            elif stat_name == "dexterity":
                value *= 1.05

        # ===== 行動原理：自由 =====

        if self.freedom_active:
            value *= (
                1.0
                + self.freedom_bonus
            )

        # ===== ハンターアイ =====

        if self.hunter_eye_turns > 0:

            # DEX +10%
            if stat_name == "dexterity":
                value *= 1.10

            # LUK +5%
            elif stat_name == "luck":
                value *= 1.05


        # ===== ハイド =====

        if (
            self.hide_turns > 0
            and stat_name == "agility"
        ):
            # AGI -10%
            value *= 0.90

        # ===== ヒーリングシールド =====

        if (
            self.healing_shield_turns > 0
            and stat_name == "vitality"
        ):
            value *= 1.20

        return value


    def get_player_main_attribute(self):
        attributes = {
            "fire": self.character.fire,
            "water": self.character.water,
            "grass": self.character.grass,
            "rock": self.character.rock,
            "light": self.character.light,
            "dark": self.character.dark,
        }

        values = list(attributes.values())

        average = sum(values) / len(values)

        max_value = max(values)

        # 最高値の属性を全部取得
        max_attributes = [
            key
            for key, value in attributes.items()
            if value == max_value
        ]

        # 最高値が複数なら無属性
        if len(max_attributes) != 1:
            return "neutral"

        # 平均値 ×1.5 を超えていなければ無属性
        if max_value <= average * 1.5:
            return "neutral"

        return max_attributes[0]

    @staticmethod
    def calculate_critical_rate(
        attacker_luck,
        defender_luck,
    ):
        denominator = (
            attacker_luck
            + defender_luck
        )

        if denominator <= 0:
            return 5

        return (
            5
            + 45
            * attacker_luck
            / denominator
        )


    @staticmethod
    def calculate_critical_multiplier(luck):
        return (
            1.5
            + (
                luck
                / (luck + 1000)
            )
            * 1.5
        )

    def get_skill_mp_cost(self, skill):
        """
        実際に消費するMPを返す。

        ウィッチ「魔力循環」は
        MP消費量が2倍になる。
        """

        mp_cost = skill.mp_cost

        if self.character.race == "witch":
            mp_cost *= 2

        return mp_cost


    def apply_player_turn_start_race_passive(self):
        """
        プレイヤーの行動開始時に発動する
        種族パッシブを処理する。
        """

        # ===== フェアリー「妖精の癒し」 =====
        #
        # 自分の行動開始時、
        # 50%で最大HPの5%回復。

        if self.character.race == "fairy":

            if self.roll_percent(50):

                heal_amount = max(
                    1,
                    int(
                        self.character.max_hp
                        * 0.05
                    ),
                )

                before_hp = self.player_hp

                self.player_hp = min(
                    self.character.max_hp,
                    self.player_hp + heal_amount,
                )

                actual_heal = (
                    self.player_hp
                    - before_hp
                )

                # HP満タン時はログを出さない
                if actual_heal > 0:

                    self.logs.append(
                        "妖精の癒し！ "
                        f"{self.character.name}のHPが"
                        f"{actual_heal}回復！"
                    )


    def apply_player_damage_race_bonus(
        self,
        damage,
    ):
        """
        プレイヤーが与えるダメージへの
        種族補正。
        """

        # デモニア「魔血暴走」
        # 与ダメージ +10%
        if self.character.race == "demonia":
            damage *= 1.10

        return damage


    def apply_player_received_damage_race_bonus(
        self,
        damage,
    ):
        """
        プレイヤーが受けるダメージへの
        種族補正。
        """

        # デモニア「魔血暴走」
        # 被ダメージ +10%
        if self.character.race == "demonia":
            damage *= 1.10

        return damage


    def get_next_preset(self):
        """
        現在使用するアクティブスキルを取得する。

        パッシブ・使用回数0のスキルは飛ばす。
        """

        if not self.presets:
            return None

        checked = 0

        while checked < len(self.presets):

            preset = self.presets[self.preset_index]
            skill = preset.skill

            # パッシブは行動として使用しない
            if skill.is_passive:
                self.advance_preset()
                checked += 1
                continue

            remaining = self.remaining_uses.get(
                preset.id,
                0,
            )

            # 使用回数が残っている
            if remaining > 0:
                return preset

            # 使い切ったスキルは飛ばす
            self.advance_preset()
            checked += 1

        # 全アクティブスキルを使い切った
        return None


    def advance_preset(self):
        """次のプリセットスロットへ進む。"""

        if not self.presets:
            return

        self.preset_index += 1

        if self.preset_index >= len(self.presets):
            self.preset_index = 0


    def player_turn(self):
        """プリセットに従ってプレイヤーを自動行動させる。"""

        # ===== 行動開始時の種族パッシブ =====

        self.apply_player_turn_start_race_passive()

        # ===== 一撃必殺の反動 =====
        #
        # 一撃必殺を使った次の行動は
        # 何もせず終了する。
        #
        # スキル使用回数やMPは消費しない。

        if self.skip_next_player_action:

            self.skip_next_player_action = False

            self.logs.append(
                f"{self.character.name}は"
                "一撃必殺の反動で行動できない！"
            )

            return "skip"

        preset = self.get_next_preset()

        # 全スキルを使い切った場合
        if preset is None:
            self.player_normal_attack()
            return "normal"

        skill = preset.skill

        # 種族パッシブ込みの実際のMP消費量
        mp_cost = self.get_skill_mp_cost(
            skill
        )

        # ===== MP不足 =====

        if self.player_mp < mp_cost:

            self.logs.append(
                f"{self.character.name}は"
                f"「{skill.name}」を使おうとしたが"
                "MPが足りない！"
            )

            # 次回も同じスキルを試すので
            # preset_indexは進めない
            self.player_normal_attack()
            return "normal"

        # ===== スキル発動率 =====

        activation_rate = (
            skill.activation_rate
        )

        # シャドウステップは
        # ステルス中なら確定発動
        if (
            skill.code == "shadow_step"
            and self.stealth_active
        ):
            activation_rate = 100

        if not self.roll_percent(
            activation_rate
        ):

            self.logs.append(
                f"{self.character.name}の"
                f"「{skill.name}」は発動しなかった！"
            )

            # 次回も同じスキルを試す
            self.player_normal_attack()
            return "normal"

        # ===== 発動成功 =====

        self.player_mp -= mp_cost

        self.remaining_uses[preset.id] -= 1

        self.logs.append(
            f"{self.character.name}は"
            f"「{skill.name}」を発動！ "
            f"MP -{mp_cost} "
            f"（残り {self.player_mp}）"
        )

        self.execute_player_skill(skill)

        self.advance_preset()

        return skill.code


    def enemy_turn(self):
        """
        敵の1行動を処理する。

        順番:
        1. 毒ダメージ
        2. 睡眠判定
        3. 通常攻撃
        """

        # ============================
        # 毒
        # ============================

        if self.enemy_poison_turns > 0:

            # 最大HPの10%
            poison_damage = max(
                1,
                int(
                    self.enemy.max_hp
                    * 0.10
                ),
            )

            self.enemy_hp -= poison_damage

            self.enemy_poison_turns -= 1

            self.logs.append(
                f"{self.enemy.name}は"
                f"毒で{poison_damage}ダメージ！"
            )

            # 毒ではHP0になれる
            if self.enemy_hp <= 0:
                return


        # ============================
        # 睡眠
        # ============================

        if self.enemy_sleep_turns > 0:

            self.enemy_sleep_turns -= 1

            self.logs.append(
                f"{self.enemy.name}は"
                "眠っていて行動できない！"
            )

            return


        # ============================
        # 麻痺
        # ============================
        #
        # 最大5行動持続。
        # 行動するたびに残り回数を1減らす。
        #
        # その行動は50%の確率で失敗する。

        if self.enemy_paralysis_turns > 0:

            self.enemy_paralysis_turns -= 1

            if self.roll_percent(50):

                self.logs.append(
                    f"{self.enemy.name}は"
                    "麻痺していて行動できない！"
                )

                return

            # 最後の行動まで来たら解除
            if self.enemy_paralysis_turns == 0:

                self.logs.append(
                    f"{self.enemy.name}の"
                    "麻痺が解けた！"
                )


        # ============================
        # 通常攻撃
        # ============================

        self.enemy_attack()


    def run(self):
        """戦闘を最後まで自動実行する。"""

        self.logs.append(
            f"{self.character.name} VS {self.enemy.name}"
        )

        self.logs.append("戦闘開始！")

        # 無限ループ防止
        loop_count = 0
        max_loop = 1000

        while (
            self.player_hp > 0
            and self.enemy_hp > 0
            and loop_count < max_loop
        ):
            loop_count += 1

            # AGI分イニシアチブを加算
            self.player_initiative += (
                self.get_player_stat("agility")
            )

            self.enemy_initiative += (
                self.enemy.agility
            )

            # プレイヤー行動
            if self.player_initiative >= 100:

                self.player_initiative -= 100

                action_code = self.player_turn()

                self.finish_player_action(
                    action_code
                )

                if self.enemy_hp <= 0:
                    break

            # 敵行動
            if self.enemy_initiative >= 100:

                self.enemy_initiative -= 100

                self.enemy_turn()

                if (
                    self.player_hp <= 0
                    or self.enemy_hp <= 0
                ):
                    break

        # ===== 戦闘報酬 =====
        #
        # 戦闘終了時に返すEXP。
        # 敗北・引き分けの場合は0。
        exp_gained = 0

        # ===== 勝敗 =====

        if self.enemy_hp <= 0:

            self.logs.append(
                f"{self.enemy.name}を倒した！"
            )

            winner = "player"

            # ========================================
            # EXP報酬
            # ========================================
            #
            # 敵ごとに設定された
            # exp_min ～ exp_max の範囲から
            # ランダムで獲得する。
            #
            # ここではCharacter.expへ直接加算しない。
            #
            # 探索中に獲得EXPを貯めて、
            # 探索終了時にまとめて成長処理するため。

            exp_gained = random.randint(
                self.enemy.exp_min,
                self.enemy.exp_max,
            )

            self.logs.append(
                f"{exp_gained}EXPを獲得！"
            )

        elif self.player_hp <= 0:

            self.logs.append(
                f"{self.character.name}は倒れた……"
            )

            winner = "enemy"

        else:
            self.logs.append(
                "戦闘が長引いたため終了しました。"
            )

            winner = "draw"

        return {
            "winner": winner,
            "logs": self.logs,
            "player_hp": max(
                0,
                self.player_hp,
            ),
            "enemy_hp": max(
                0,
                self.enemy_hp,
            ),
            #　今回の戦闘で獲得したEXP
            "exp_gained": exp_gained,
        }


    def finish_player_action(self, action_code):
        """プレイヤーの1行動終了時処理。"""

        # ===== 行動原理：自由 =====

        if (
            self.freedom_active
            and self.freedom_bonus < 0.10
        ):
            self.freedom_bonus = min(
                0.10,
                self.freedom_bonus + 0.02,
            )

            percent = int(
                self.freedom_bonus * 100
            )

            self.logs.append(
                "「行動原理：自由」 "
                f"全能力補正が+{percent}%になった！"
            )

        # ===== 歩行者 =====
        #
        # 発動した行動そのものは
        # 3行動の残り回数に含めない

        if (
            self.walker_turns > 0
            and action_code != "walker"
        ):
            self.walker_turns -= 1

            if self.walker_turns == 0:
                self.logs.append(
                    "「歩行者」の効果が切れた。"
                )

        # ===== 闘魂 =====
        #
        # 闘魂を発動した行動そのものでは
        # 残り行動数を減らさない。
        #
        # 発動後の次の行動から
        # 3回分STRアップが有効になる。

        if (
            self.fighting_spirit_turns > 0
            and action_code != "fighting_spirit"
        ):
            self.fighting_spirit_turns -= 1

            # 0になったら効果終了
            if self.fighting_spirit_turns == 0:

                self.logs.append(
                    "「闘魂」の効果が切れた。"
                )

        # ===== 鋼の体 =====
        #
        # 発動した行動では減らさず、
        # 次の自分の行動終了時に解除する。

        if (
            self.steel_body_turns > 0
            and action_code != "steel_body"
        ):

            self.steel_body_turns -= 1

            if self.steel_body_turns == 0:

                self.logs.append(
                    "「鋼の体」の効果が切れた。"
                )


        # ===== 盤石の構え =====

        if (
            self.solid_stance_turns > 0
            and action_code != "solid_stance"
        ):

            self.solid_stance_turns -= 1

            if self.solid_stance_turns == 0:

                self.logs.append(
                    "「盤石の構え」の効果が切れた。"
                )


        # ===== 反撃の構え =====
        #
        # 発動後の自分の行動を
        # 2回終えるまで有効。

        if (
            self.counter_stance_turns > 0
            and action_code != "counter_stance"
        ):

            self.counter_stance_turns -= 1

            if self.counter_stance_turns == 0:

                self.counter_remaining = 0

                self.logs.append(
                    "「反撃の構え」の効果が切れた。"
                )


        # ===== ハンターアイ =====

        if (
            self.hunter_eye_turns > 0
            and action_code != "hunter_eye"
        ):

            self.hunter_eye_turns -= 1

            if self.hunter_eye_turns == 0:

                self.logs.append(
                    "「ハンターアイ」の効果が切れた。"
                )


        # ===== ハイド =====

        if (
            self.hide_turns > 0
            and action_code != "hide"
        ):

            self.hide_turns -= 1

            if self.hide_turns == 0:

                self.logs.append(
                    "「ハイド」の効果が切れた。"
                )

        # ===== フロストアーマー =====

        if (
            self.frost_armor_turns > 0
            and action_code != "frost_armor"
        ):

            self.frost_armor_turns -= 1

            if self.frost_armor_turns == 0:

                self.logs.append(
                    "「フロストアーマー」の"
                    "効果が切れた。"
                )

        # ===== ヒーリングシールド =====

        if (
            self.healing_shield_turns > 0
            and action_code != "healing_shield"
        ):

            self.healing_shield_turns -= 1

            if self.healing_shield_turns == 0:

                self.logs.append(
                    "「ヒーリングシールド」の"
                    "VIT上昇効果が切れた。"
                )

        # ===== シャドウステップ =====

        if (
            self.shadow_step_turns > 0
            and action_code != "shadow_step"
        ):

            self.shadow_step_turns -= 1

            if self.shadow_step_turns == 0:

                self.logs.append(
                    "「シャドウステップ」の"
                    "効果が切れた。"
                )

        # ===== エルフ「森の加護」 =====
        #
        # 自分の行動終了ごとに
        # AGI +1%。
        #
        # 最大+10%。

        if (
            self.character.race == "elf"
            and self.elf_agility_bonus < 0.10
        ):

            self.elf_agility_bonus = min(
                0.10,
                self.elf_agility_bonus + 0.01,
            )

            percent = int(
                round(
                    self.elf_agility_bonus
                    * 100
                )
            )

            self.logs.append(
                "森の加護！ "
                f"AGI補正が+{percent}%になった！"
            )


    def player_normal_attack(self):
        """プレイヤー通常攻撃。"""

        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.get_player_stat(
                "dexterity"
            ),
            defender_agi=self.enemy.agility,
        )

        if not self.roll_percent(hit_rate):

            self.logs.append(
                f"{self.character.name}の攻撃！ "
                "しかし外れた！"
            )

            return

        damage = self.calculate_physical_damage(
            strength=self.get_player_stat(
                "strength"
            ),
            defender_vit=self.enemy.vitality,
        )

        # ===== クリティカル =====

        critical_rate = (
            self.calculate_critical_rate(
                attacker_luck=self.get_player_stat("luck"),
                defender_luck=self.enemy.luck,
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            critical_multiplier = (
                self.calculate_critical_multiplier(
                    self.get_player_stat("luck")
                )
            )

            damage *= critical_multiplier

        # ===== 属性相性 =====
        # 通常攻撃は無属性

        skill_attribute = "neutral"

        attribute_multiplier = (
            ATTRIBUTE_MULTIPLIERS[
                skill_attribute
            ][
                self.enemy.attribute
            ]
        )

        damage *= attribute_multiplier

        # ===== 得意属性補正 =====

        main_attribute = (
            self.get_player_main_attribute()
        )

        if (
            skill_attribute
            == main_attribute
        ):
            damage *= 1.15

        # ===== 睡眠中の被ダメージ補正 =====
        #
        # 睡眠中に通常攻撃を受けた場合も
        # ダメージ1.2倍。
        #
        # 攻撃後に睡眠解除。

        was_sleeping = (
            self.enemy_sleep_turns > 0
        )

        if was_sleeping:
            damage *= 1.20

        # ===== 種族による与ダメージ補正 =====

        damage = (
            self.apply_player_damage_race_bonus(
                damage
            )
        )

        # 最終的に整数化
        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        # ===== 睡眠解除 =====

        if was_sleeping:

            self.enemy_sleep_turns = 0

            self.logs.append(
                f"{self.enemy.name}は"
                "攻撃を受けて目を覚ました！"
            )

        if is_critical:

            self.logs.append(
                f"{self.character.name}の攻撃！ "
                f"クリティカル！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{self.character.name}の攻撃！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

    def player_physical_skill_hit(
        self,
        skill_name,
        base_damage,
        attribute,
        hit_label=None,
        guaranteed_hit=False,
    ):
        """
        プレイヤーの物理スキル
        「1ヒット分」を処理する共通関数。

        処理内容:
        1. 命中判定
        2. 敵VITによる物理防御
        3. クリティカル判定
        4. 属性相性
        5. 得意属性補正
        6. 最終ダメージ
        """

        # すでに敵を倒していた場合は何もしない
        if self.enemy_hp <= 0:
            return False

        # ログに表示する攻撃名
        #
        # hit_labelが指定されている場合、
        # 「ダブルパンチ 1撃目」などを表示できる。
        attack_name = (
            hit_label
            if hit_label is not None
            else skill_name
        )

        # ===== 命中判定 =====

        if not guaranteed_hit:

            hit_rate = self.calculate_hit_rate(
                attacker_dex=self.get_player_stat(
                    "dexterity"
                ),
                defender_agi=self.enemy.agility,
            )

            if not self.roll_percent(hit_rate):

                self.logs.append(
                    f"{attack_name}！ "
                    "しかし攻撃は外れた！"
                )

                return False

        # ===== 物理防御 =====
        #
        # 物理ダメージ:
        #
        # 基礎ダメージ
        # - 敵VIT ×0.5

        damage = (
            base_damage
            - self.enemy.vitality * 0.5
        )

        damage = max(
            1,
            damage,
        )

        # ===== クリティカル =====

        luck = self.get_player_stat(
            "luck"
        )

        critical_rate = (
            self.calculate_critical_rate(
                attacker_luck=luck,
                defender_luck=self.enemy.luck,
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            damage *= (
                self.calculate_critical_multiplier(
                    luck
                )
            )

        # ===== 属性相性 =====

        damage *= ATTRIBUTE_MULTIPLIERS[
            attribute
        ][
            self.enemy.attribute
        ]

        # ===== 得意属性補正 =====
        #
        # スキル属性と得意属性が一致したら
        # 最終ダメージ ×1.15

        if (
            self.get_player_main_attribute()
            == attribute
        ):
            damage *= 1.15

        # ===== 睡眠中の被ダメージ補正 =====
        #
        # 睡眠中に直接攻撃を受けた場合、
        # その攻撃のダメージは1.2倍。
        #
        # ダメージを受けた後に睡眠解除。

        was_sleeping = (
            self.enemy_sleep_turns > 0
        )

        if was_sleeping:
            damage *= 1.20

        # ===== 種族による与ダメージ補正 =====

        damage = (
            self.apply_player_damage_race_bonus(
                damage
            )
        )

        # ===== 最終ダメージ =====

        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        # ===== 戦闘ログ =====

        if is_critical:

            self.logs.append(
                f"{attack_name}！ "
                f"クリティカル！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{attack_name}！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        # ===== 睡眠解除 =====

        if was_sleeping:

            self.enemy_sleep_turns = 0

            self.logs.append(
                f"{self.enemy.name}は"
                "攻撃を受けて目を覚ました！"
            )

        # 攻撃が命中したことを返す
        return True


    def player_magic_skill_hit(
        self,
        skill_name,
        base_damage,
        attribute,
        hit_label=None,
        ignore_magic_defense=False,
    ):
        """
        プレイヤーの魔法スキル
        「1ヒット分」を処理する共通関数。

        処理内容:
        1. 命中判定
        2. 敵INTによる魔法防御
        3. 属性相性
        4. 得意属性補正
        5. 睡眠中のダメージ補正
        6. 最終ダメージ

        魔法攻撃は現時点では
        クリティカル判定を行わない。
        """

        # すでに敵を倒していた場合
        if self.enemy_hp <= 0:
            return False

        # ログ表示名
        attack_name = (
            hit_label
            if hit_label is not None
            else skill_name
        )

        # ============================
        # 命中判定
        # ============================

        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.get_player_stat(
                "dexterity"
            ),
            defender_agi=self.enemy.agility,
        )

        if not self.roll_percent(hit_rate):

            self.logs.append(
                f"{attack_name}！ "
                "しかし攻撃は外れた！"
            )

            return False

        # ============================
        # 魔法防御
        # ============================
        #
        # 通常の魔法:
        #
        # 基礎ダメージ
        # - 敵INT ×0.3
        #
        # メギドなど、
        # 防御無視スキルの場合は引かない。

        damage = base_damage

        if not ignore_magic_defense:
            damage -= (
                self.enemy.intelligence
                * 0.3
            )

        damage = max(
            1,
            damage,
        )

        # ============================
        # 属性相性
        # ============================

        damage *= ATTRIBUTE_MULTIPLIERS[
            attribute
        ][
            self.enemy.attribute
        ]

        # ============================
        # 得意属性補正
        # ============================

        if (
            self.get_player_main_attribute()
            == attribute
        ):
            damage *= 1.15

        # ============================
        # 睡眠中
        # ============================
        #
        # 睡眠中に攻撃された場合
        # ダメージ1.2倍。
        #
        # 攻撃後に目を覚ます。

        was_sleeping = (
            self.enemy_sleep_turns > 0
        )

        if was_sleeping:
            damage *= 1.20

        # ===== 種族による与ダメージ補正 =====

        damage = (
            self.apply_player_damage_race_bonus(
                damage
            )
        )

        # ============================
        # 最終ダメージ
        # ============================

        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        self.logs.append(
            f"{attack_name}！ "
            f"{self.enemy.name}に"
            f"{damage}ダメージ！"
        )

        # 睡眠解除
        if was_sleeping:

            self.enemy_sleep_turns = 0

            self.logs.append(
                f"{self.enemy.name}は"
                "攻撃を受けて目を覚ました！"
            )

        return True


    def execute_player_skill(self, skill):
        """プレイヤーのスキル効果を実行する。"""

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


#==== プレイヤースキル実装 ===


#==== 拳闘士スキル ====

    # ============================
    # ダブルパンチ
    # ============================

    def skill_double_punch(self):
        """
        ダブルパンチ

        無属性・物理

        STR ×2.0 の攻撃を
        2回行う。

        各攻撃ごとに
        命中・クリティカル判定を行う。
        """

        strength = self.get_player_stat(
            "strength"
        )

        # 2回攻撃
        for hit_number in range(1, 3):

            # 1撃目で敵を倒した場合、
            # 2撃目は発生させない。
            if self.enemy_hp <= 0:
                break

            base_damage = (
                strength * 2.0
            )

            self.player_physical_skill_hit(
                skill_name="ダブルパンチ",
                base_damage=base_damage,
                attribute="neutral",
                hit_label=(
                    f"ダブルパンチ "
                    f"{hit_number}撃目"
                ),
            )

    # ============================
    # 衝撃波
    # ============================

    def skill_shock_wave(self):
        """
        衝撃波

        光属性・物理

        STR ×1.5

        本来は全体攻撃。
        現在のBattleEngineは1対1なので、
        今は現在の敵1体へ攻撃する。

        複数敵戦闘を実装した際に
        全敵へ処理するよう拡張する。
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.5
        )

        self.player_physical_skill_hit(
            skill_name="衝撃波",
            base_damage=base_damage,
            attribute="light",
        )

    # ============================
    # 怒涛連打
    # ============================

    def skill_rapid_barrage(self):
        """
        怒涛連打

        炎属性・物理

        STR ×0.5 の攻撃を
        ランダムで1～10回行う。

        各ヒットごとに
        命中・クリティカル判定を行う。
        """

        strength = self.get_player_stat(
            "strength"
        )

        # 攻撃回数を1～10回から決定
        hit_count = random.randint(
            1,
            10,
        )

        self.logs.append(
            f"怒涛連打！ "
            f"{hit_count}回攻撃！"
        )

        for hit_number in range(
            1,
            hit_count + 1,
        ):

            # 途中で敵を倒した場合は終了
            if self.enemy_hp <= 0:
                break

            base_damage = (
                strength * 0.5
            )

            self.player_physical_skill_hit(
                skill_name="怒涛連打",
                base_damage=base_damage,
                attribute="fire",
                hit_label=(
                    f"怒涛連打 "
                    f"{hit_number}撃目"
                ),
            )

    # ============================
    # 闘魂
    # ============================

    def skill_fighting_spirit(self):
        """
        闘魂

        炎属性・補助

        次の3行動の間、
        STR ×1.10。

        同じ効果は重複させず、
        再使用した場合は
        残り行動数を3へ戻す。
        """

        self.fighting_spirit_turns = 3

        self.logs.append(
            "闘魂！ "
            "3行動の間、STRが10%上昇！"
        )

    # ============================
    # 真拳一殺
    # ============================

    def skill_true_fist(self):
        """
        真拳一殺

        無属性・物理

        基礎ダメージ:
        STR ×2.0
        + LUK ×1.5
        """

        strength = self.get_player_stat(
            "strength"
        )

        luck = self.get_player_stat(
            "luck"
        )

        base_damage = (
            strength * 2.0
            + luck * 1.5
        )

        self.player_physical_skill_hit(
            skill_name="真拳一殺",
            base_damage=base_damage,
            attribute="neutral",
        )


#==== 重戦士スキル ====

    # ============================
    # フレアブレイド
    # ============================

    def skill_flare_blade(self):
        """
        フレアブレイド

        炎属性・物理
        STR ×2.2

        本来は全体攻撃。
        現在は1対1なので敵1体に攻撃する。
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 2.2
        )

        self.player_physical_skill_hit(
            skill_name="フレアブレイド",
            base_damage=base_damage,
            attribute="fire",
        )


    # ============================
    # 一撃必殺
    # ============================

    def skill_one_hit_kill(self):
        """
        一撃必殺

        無属性・物理
        STR ×4.0

        使用後、
        次の自分の行動は行動不能。
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 4.0
        )

        self.player_physical_skill_hit(
            skill_name="一撃必殺",
            base_damage=base_damage,
            attribute="neutral",
        )

        # 次の自分の行動を休む
        self.skip_next_player_action = True


    # ============================
    # 鋼の体
    # ============================

    def skill_steel_body(self):
        """
        鋼の体

        岩属性・補助

        次の自分の行動まで、
        受ける物理ダメージを40%軽減する。
        """

        self.steel_body_turns = 1

        self.logs.append(
            "鋼の体！ "
            "受ける物理ダメージを40%軽減！"
        )


    # ============================
    # 盤石の構え
    # ============================

    def skill_solid_stance(self):
        """
        盤石の構え

        岩属性・補助

        次の自分の行動まで
        被ダメージを20%軽減。

        本来は味方への単体攻撃を
        自分が代わりに受ける。

        現在は1対1なので、
        ダメージ軽減部分のみ実装する。
        """

        self.solid_stance_turns = 1

        self.logs.append(
            "盤石の構え！ "
            "受けるダメージを20%軽減！"
        )


    # ============================
    # 反撃の構え
    # ============================

    def skill_counter_stance(self):
        """
        反撃の構え

        無属性・補助

        2行動の間、
        敵から攻撃を受けると反撃する。

        反撃:
        STR ×1.3

        最大3回まで。
        """

        self.counter_stance_turns = 2

        self.counter_remaining = 3

        self.logs.append(
            "反撃の構え！ "
            "2行動の間、攻撃を受けると反撃する！"
        )


#==== 狩人スキル ====

    # ============================
    # ラピッドショット
    # ============================

    def skill_rapid_shot(self):
        """
        ラピッドショット

        無属性・物理
        STR ×1.5

        この攻撃は必ず命中する。
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.5
        )

        self.player_physical_skill_hit(
            skill_name="ラピッドショット",
            base_damage=base_damage,
            attribute="neutral",

            # 命中判定を行わない
            guaranteed_hit=True,
        )


    # ============================
    # 睡眠矢
    # ============================

    def skill_sleep_arrow(self):
        """
        睡眠矢

        水属性・物理
        STR ×1.8

        命中時35%で睡眠。

        睡眠:
        ・行動不能
        ・最大3行動
        ・被ダメージ1.2倍
        ・直接攻撃を受けると解除
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.8
        )

        hit = self.player_physical_skill_hit(
            skill_name="睡眠矢",
            base_damage=base_damage,
            attribute="water",
        )

        # 攻撃が外れた場合は
        # 睡眠判定をしない
        if not hit:
            return

        # 敵を倒した場合も付与しない
        if self.enemy_hp <= 0:
            return

        # ===== 睡眠付与判定 =====

        if self.roll_percent(35):

            self.enemy_sleep_turns = 3

            self.logs.append(
                f"{self.enemy.name}は"
                "睡眠状態になった！"
            )


    # ============================
    # ハンターアイ
    # ============================

    def skill_hunter_eye(self):
        """
        ハンターアイ

        無属性・補助

        3行動の間
        DEX +10%
        LUK +5%

        同じ効果は重複させない。
        再使用時は3行動へ戻す。
        """

        self.hunter_eye_turns = 3

        self.logs.append(
            "ハンターアイ！ "
            "3行動の間、"
            "DEX +10%、LUK +5%！"
        )


    # ============================
    # ハイド
    # ============================

    def skill_hide(self):
        """
        ハイド

        草属性・補助

        3行動の間
        AGI -10%

        その代わり、
        敵からの命中率を10%低下。
        """

        self.hide_turns = 3

        self.logs.append(
            "ハイド！ "
            "3行動の間、"
            "AGI -10%、"
            "敵の命中率 -10%！"
        )


    # ============================
    # 毒矢
    # ============================

    def skill_poison_arrow(self):
        """
        毒矢

        闇属性・物理
        STR ×1.5

        命中時50%で毒。

        毒:
        ・敵最大HPの10%ダメージ
        ・5行動持続
        ・毒ダメージでHP0になれる
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.5
        )

        hit = self.player_physical_skill_hit(
            skill_name="毒矢",
            base_damage=base_damage,
            attribute="dark",
        )

        # 命中しなければ毒判定なし
        if not hit:
            return

        # 敵を倒した場合も不要
        if self.enemy_hp <= 0:
            return

        # ===== 毒付与判定 =====

        if self.roll_percent(50):

            # 毒は5行動
            self.enemy_poison_turns = 5

            self.logs.append(
                f"{self.enemy.name}は"
                "毒状態になった！"
            )


#==== ウィザードスキル ====

    # ============================
    # ステラ
    # ============================

    def skill_stella(self):
        """
        ステラ

        無属性・魔法

        INT ×0.7 の攻撃を
        ランダムで4～5回行う。
        """

        intelligence = self.get_player_stat(
            "intelligence"
        )

        # 4～5回からランダム
        hit_count = random.randint(
            4,
            5,
        )

        self.logs.append(
            f"ステラ！ "
            f"{hit_count}回攻撃！"
        )

        for hit_number in range(
            1,
            hit_count + 1,
        ):

            # 途中で敵を倒した場合は終了
            if self.enemy_hp <= 0:
                break

            base_damage = (
                intelligence * 0.7
            )

            self.player_magic_skill_hit(
                skill_name="ステラ",
                base_damage=base_damage,
                attribute="neutral",
                hit_label=(
                    f"ステラ "
                    f"{hit_number}撃目"
                ),
            )


    # ============================
    # ファイヤー
    # ============================

    def skill_fire(self):
        """
        ファイヤー

        炎属性・魔法

        INT ×1.5
        × ランダム補正0.75～1.0
        """

        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.75,
            1.0,
        )

        base_damage = (
            intelligence
            * 1.5
            * random_multiplier
        )

        self.player_magic_skill_hit(
            skill_name="ファイヤー",
            base_damage=base_damage,
            attribute="fire",
        )


    # ============================
    # メギド
    # ============================

    def skill_megido(self):
        """
        メギド

        闇属性・魔法

        INT ×1.1
        × ランダム補正0.5～1.0

        敵INT ×0.3の
        魔法防御を無視する。
        """

        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.5,
            1.0,
        )

        base_damage = (
            intelligence
            * 1.1
            * random_multiplier
        )

        self.player_magic_skill_hit(
            skill_name="メギド",
            base_damage=base_damage,
            attribute="dark",

            # 魔法防御を無視
            ignore_magic_defense=True,
        )


    # ============================
    # エクスプロージョン
    # ============================

    def skill_explosion(self):
        """
        エクスプロージョン

        岩属性・魔法

        INT ×2.5
        × ランダム補正0.5～1.0

        本来は全体攻撃。
        現在は敵1体に適用する。
        """

        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.5,
            1.0,
        )

        base_damage = (
            intelligence
            * 2.5
            * random_multiplier
        )

        self.player_magic_skill_hit(
            skill_name="エクスプロージョン",
            base_damage=base_damage,
            attribute="rock",
        )


    # ============================
    # フロストアーマー
    # ============================

    def skill_frost_armor(self):
        """
        フロストアーマー

        水属性・補助

        5行動の間、
        受ける魔法ダメージを30%軽減。

        属性有利の場合は40%軽減。

        現在、敵は通常攻撃のみなので
        状態だけ保持する。
        敵魔法実装時に軽減処理を使用する。
        """

        self.frost_armor_turns = 5

        self.logs.append(
            "フロストアーマー！ "
            "5行動の間、"
            "魔法ダメージを軽減！"
        )


#==== プリーストスキル ====

    # ============================
    # ジャッジメント
    # ============================

    def skill_judgement(self):
        """
        ジャッジメント

        炎属性・魔法

        INT ×2.0
        × ランダム補正0.75～1.0

        命中時50%で麻痺。
        """

        intelligence = self.get_player_stat(
            "intelligence"
        )

        random_multiplier = random.uniform(
            0.75,
            1.0,
        )

        base_damage = (
            intelligence
            * 2.0
            * random_multiplier
        )

        hit = self.player_magic_skill_hit(
            skill_name="ジャッジメント",
            base_damage=base_damage,
            attribute="fire",
        )

        # 外れたら麻痺判定なし
        if not hit:
            return

        # 倒していたら状態異常不要
        if self.enemy_hp <= 0:
            return

        # ===== 麻痺付与 =====

        if self.roll_percent(50):

            self.enemy_paralysis_turns = 5

            self.logs.append(
                f"{self.enemy.name}は"
                "麻痺状態になった！"
            )


    # ============================
    # ヒーリングシールド
    # ============================

    def skill_healing_shield(self):
        """
        ヒーリングシールド

        草属性・回復 / 補助

        VIT ×1.0分HPを回復。

        さらに3行動の間
        VIT +20%。
        """

        vitality = self.get_player_stat(
            "vitality"
        )

        # ===== HP回復 =====

        heal_amount = max(
            1,
            int(vitality * 1.0),
        )

        before_hp = self.player_hp

        self.player_hp = min(
            self.character.max_hp,
            self.player_hp + heal_amount,
        )

        actual_heal = (
            self.player_hp
            - before_hp
        )

        # ===== VITバフ =====

        # 重複せず、
        # 再使用時は3行動へ戻す。
        self.healing_shield_turns = 3

        self.logs.append(
            f"ヒーリングシールド！ "
            f"HPが{actual_heal}回復！ "
            "3行動の間、VIT +20%！"
        )


    # ============================
    # 浄化
    # ============================

    def skill_purification(self):
        """
        浄化

        水属性・補助

        自分のデバフを1つ解除し、
        次に受けるデバフを1回無効化する。

        現在はプレイヤー側の状態異常が
        まだ本格実装されていないため、
        デバフ無効化フラグを先に実装する。
        """

        self.purification_guard = True

        self.logs.append(
            "浄化！ "
            "デバフを解除し、"
            "次に受けるデバフを1回無効化！"
        )


    # ============================
    # リザレク
    # ============================

    def skill_resurrection(self):
        """
        リザレク

        光属性・回復

        戦闘不能の味方1人を
        最大HP10%で復活。

        1戦につき1回。

        現在は1対1戦闘なので、
        パーティ戦用の状態のみ管理する。
        """

        # すでに使用済み
        if self.resurrection_used:

            self.logs.append(
                "リザレクはこの戦闘では"
                "すでに使用している！"
            )

            return

        self.resurrection_used = True

        self.logs.append(
            "リザレク！ "
            "現在は蘇生対象となる味方がいない。"
        )


    # ============================
    # アンチジェイル
    # ============================

    def skill_anti_jail(self):
        """
        アンチジェイル

        無属性・魔法

        1撃目:
        INT ×1.8

        2撃目:
        INT ×2.2
        """

        intelligence = self.get_player_stat(
            "intelligence"
        )

        # ===== 1撃目 =====

        if self.enemy_hp > 0:

            self.player_magic_skill_hit(
                skill_name="アンチジェイル",
                base_damage=(
                    intelligence * 1.8
                ),
                attribute="neutral",
                hit_label="アンチジェイル 1撃目",
            )

        # ===== 2撃目 =====

        if self.enemy_hp > 0:

            self.player_magic_skill_hit(
                skill_name="アンチジェイル",
                base_damage=(
                    intelligence * 2.2
                ),
                attribute="neutral",
                hit_label="アンチジェイル 2撃目",
            )


#==== 放浪人スキル ====

    # ============================
    # 核心を突く
    # ============================
    
    def skill_strike_core(self):
        """
        核心を突く

        (STR ×1.0 + LUK ×1.2)
        × (1.0～0.5)

        光属性・物理
        """

        # ===== 命中判定 =====

        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.get_player_stat(
                "dexterity"
            ),
            defender_agi=self.enemy.agility,
        )

        if not self.roll_percent(hit_rate):

            self.logs.append(
                "核心を突く！ "
                "しかし攻撃は外れた！"
            )

            return

        # ===== 基礎ダメージ =====

        random_multiplier = random.uniform(
            0.5,
            1.0,
        )

        strength = self.get_player_stat(
            "strength"
        )

        luck = self.get_player_stat(
            "luck"
        )

        base_damage = (
            strength * 1.0
            + luck * 1.2
        )

        base_damage *= random_multiplier

        # ===== 物理防御 =====

        damage = (
            base_damage
            - self.enemy.vitality * 0.5
        )

        damage = max(
            1,
            damage,
        )

        # ===== クリティカル =====

        critical_rate = (
            self.calculate_critical_rate(
                luck,
                self.enemy.luck,
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            damage *= (
                self.calculate_critical_multiplier(
                    luck
                )
            )

        # ===== 属性相性 =====

        damage *= ATTRIBUTE_MULTIPLIERS[
            "light"
        ][self.enemy.attribute]

        # ===== 得意属性補正 =====

        if (
            self.get_player_main_attribute()
            == "light"
        ):
            damage *= 1.15

        # ===== 最終ダメージ =====

        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

        if is_critical:

            self.logs.append(
                f"核心を突く！ "
                f"クリティカル！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"核心を突く！ "
                f"{self.enemy.name}に"
                f"{damage}ダメージ！"
            )

    # ============================
    # 一時休息
    # ============================
    def skill_short_rest(self):
        """
        一時休息
        STR ×0.5 HP回復
        """

        strength = self.get_player_stat(
            "strength"
        )

        heal_amount = max(
            1,
            int(strength * 0.5),
        )

        # 現在HPが最大HPを超えていた場合も
        # 念のため最大HPまで補正する
        before_hp = min(
            self.player_hp,
            self.character.max_hp,
        )

        self.player_hp = before_hp

        # 最大HPを超えないように回復
        self.player_hp = min(
            self.character.max_hp,
            self.player_hp + heal_amount,
        )

        # 実際に回復した量
        actual_heal = max(
            0,
            self.player_hp - before_hp,
        )

        self.logs.append(
            f"一時休息！ "
            f"{self.character.name}のHPが"
            f"{actual_heal}回復！ "
            f"（HP {self.player_hp}"
            f"/{self.character.max_hp}）"
        )

    # ============================
    # 歩行者
    # ============================
    def skill_walker(self):
        """
        歩行者

        3行動の間
        AGI -30%
        STR +20%
        DEX +5%
        """

        # 重複はしない。
        # 再使用した場合は持続時間を3に戻す。
        self.walker_turns = 3

        self.logs.append(
            "歩行者！ "
            "3行動の間、"
            "AGI -30%、STR +20%、DEX +5%！"
        )

    # ============================
    # 蜃気楼
    # ============================
    def skill_mirage(self):
        """
        蜃気楼

        攻撃を全体化する。
        現在は1対1戦闘なので、
        複数敵実装用のフラグのみ保持する。
        """

        self.mirage_active = True

        self.logs.append(
            "蜃気楼を発動！ "
            "攻撃が全体化された！"
        )


#==== 暗殺者スキル ====

    # ============================
    # 奇襲
    # ============================

    def skill_surprise_attack(self):
        """
        奇襲

        無属性・物理

        スキル発動成功後、
        さらに40%で奇襲成功。

        成功:
        STR ×4.5
        × ランダム補正0.8～1.2

        失敗:
        現在HPの10%を失う。
        最低1ダメージ。
        """

        # ===== 奇襲成功判定 =====

        if not self.roll_percent(40):

            # 現在HPの10%
            self_damage = max(
                1,
                int(
                    self.player_hp
                    * 0.10
                ),
            )

            self.player_hp -= (
                self_damage
            )

            self.logs.append(
                "奇襲失敗！ "
                f"{self.character.name}は"
                f"反動で{self_damage}ダメージ！"
            )

            return

        # ===== 奇襲成功 =====

        strength = self.get_player_stat(
            "strength"
        )

        random_multiplier = random.uniform(
            0.8,
            1.2,
        )

        base_damage = (
            strength
            * 4.5
            * random_multiplier
        )

        self.logs.append(
            "奇襲成功！"
        )

        self.player_physical_skill_hit(
            skill_name="奇襲",
            base_damage=base_damage,
            attribute="neutral",
        )


    # ============================
    # ポイズンダガー
    # ============================

    def skill_poison_dagger(self):
        """
        ポイズンダガー

        草属性・物理
        STR ×1.2

        命中時:
        ・60%で毒
        ・DEX -3%
        """

        strength = self.get_player_stat(
            "strength"
        )

        base_damage = (
            strength * 1.2
        )

        hit = self.player_physical_skill_hit(
            skill_name="ポイズンダガー",
            base_damage=base_damage,
            attribute="grass",
        )

        # 外れた場合は
        # 追加効果なし
        if not hit:
            return

        if self.enemy_hp <= 0:
            return

        # ===== DEX -3% =====
        #
        # 同じ効果は重複させない。

        self.enemy_dex_debuff_rate = 0.03

        self.logs.append(
            f"{self.enemy.name}の"
            "DEXが3%低下！"
        )

        # ===== 毒判定 =====

        if self.roll_percent(60):

            self.enemy_poison_turns = 5

            self.logs.append(
                f"{self.enemy.name}は"
                "毒状態になった！"
            )


    # ============================
    # ステルス
    # ============================

    def skill_stealth(self):
        """
        ステルス

        闇属性・補助

        回避率+10%。

        最終回避率は最大50%。

        持続時間はまだ正式決定していないため、
        現段階では戦闘中有効として扱う。
        """

        self.stealth_active = True

        self.logs.append(
            "ステルス！ "
            "回避率が10%上昇！"
        )


    # ============================
    # シャドウステップ
    # ============================

    def skill_shadow_step(self):
        """
        シャドウステップ

        闇属性・補助

        3行動の間、
        受けた攻撃ダメージの40%を反射。

        自分自身は
        通常通り全ダメージを受ける。

        ステルス中なら
        スキル発動率100%。
        """

        self.shadow_step_turns = 3

        self.logs.append(
            "シャドウステップ！ "
            "3行動の間、"
            "被ダメージの40%を反射！"
        )


    # ============================
    # フラッシュバング
    # ============================

    def skill_flashbang(self):
        """
        フラッシュバング

        光属性・補助

        50%で敵を麻痺。

        麻痺時間は
        ランダムで1～3行動。

        本来は敵全体対象。
        現在は1対1なので敵1体へ適用。
        """

        # ===== 麻痺判定 =====

        if not self.roll_percent(50):

            self.logs.append(
                "フラッシュバング！ "
                f"{self.enemy.name}には"
                "効かなかった！"
            )

            return

        # 1～3行動
        paralysis_turns = (
            random.randint(
                1,
                3,
            )
        )

        self.enemy_paralysis_turns = (
            paralysis_turns
        )

        self.logs.append(
            "フラッシュバング！ "
            f"{self.enemy.name}は"
            f"{paralysis_turns}行動の間、"
            "麻痺状態になった！"
        )


    #=== 敵行動実装 ===
    def enemy_attack(self):
        """敵の通常攻撃。"""

        # ===== 敵の有効DEX =====

        enemy_dexterity = (
            self.enemy.dexterity
        )

        # ポイズンダガーによるDEX -3%
        if self.enemy_dex_debuff_rate > 0:

            enemy_dexterity *= (
                1.0
                - self.enemy_dex_debuff_rate
            )

        # ===== 命中率 =====

        hit_rate = self.calculate_hit_rate(
            attacker_dex=enemy_dexterity,
            defender_agi=self.get_player_stat(
                "agility"
            ),
        )

        # ===== ハイド =====
        #
        # ハイド中は敵の命中率を10%低下。

        if self.hide_turns > 0:
            hit_rate *= 0.90

        # ===== ステルス =====
        #
        # 回避率+10%
        # ＝敵の命中率を10ポイント低下。
        #
        # 最終回避率は最大50%なので、
        # 命中率は最低50%まで。

        if self.stealth_active:

            hit_rate -= 10

            hit_rate = max(
                50,
                hit_rate,
            )

        #===== 命中判定 =====
        if not self.roll_percent(hit_rate):

            self.logs.append(
                f"{self.enemy.name}の攻撃！ "
                "しかし外れた！"
            )

            return

        damage = self.calculate_physical_damage(
            strength=self.enemy.strength,
            defender_vit=self.get_player_stat(
                "vitality"
            ),
        )

        critical_rate = (
            self.calculate_critical_rate(
                attacker_luck=self.enemy.luck,
                defender_luck=self.get_player_stat("luck"),
            )
        )

        is_critical = self.roll_percent(
            critical_rate
        )

        if is_critical:

            damage *= (
                self.calculate_critical_multiplier(
                    self.enemy.luck
                )
            )

        # ===== 鋼の体 =====
        #
        # 敵の通常攻撃は物理なので
        # 40%軽減する。

        if self.steel_body_turns > 0:

            damage *= 0.60

            self.logs.append(
                "「鋼の体」で"
                "物理ダメージを40%軽減！"
            )

        # ===== 盤石の構え =====

        if self.solid_stance_turns > 0:

            damage *= 0.80

            self.logs.append(
                "「盤石の構え」で"
                "ダメージを20%軽減！"
            )

        # ===== 種族による被ダメージ補正 =====

        damage = (
            self.apply_player_received_damage_race_bonus(
                damage
            )
        )

        damage = max(
            1,
            int(damage),
        )

        self.player_hp -= damage

        # ===== シャドウステップ =====
        #
        # 自分は通常通りダメージを受ける。
        # そのダメージの40%を敵へ返す。

        if (
            self.shadow_step_turns > 0
            and self.enemy_hp > 0
        ):

            reflect_damage = max(
                1,
                int(
                    damage * 0.40
                ),
            )

            self.enemy_hp -= (
                reflect_damage
            )

            self.logs.append(
                "シャドウステップ！ "
                f"{self.enemy.name}に"
                f"{reflect_damage}反射ダメージ！"
            )

        # ===== 反撃の構え =====

        should_counter = (
            self.player_hp > 0
            and self.counter_stance_turns > 0
            and self.counter_remaining > 0
        )

        if is_critical:

            self.logs.append(
                f"{self.enemy.name}の攻撃！ "
                f"クリティカル！ "
                f"{self.character.name}に"
                f"{damage}ダメージ！"
            )

        else:

            self.logs.append(
                f"{self.enemy.name}の攻撃！ "
                f"{self.character.name}に"
                f"{damage}ダメージ！"
            )

        if should_counter:

            self.counter_remaining -= 1

            strength = self.get_player_stat(
                "strength"
            )

            base_damage = (
                strength * 1.3
            )

            self.logs.append(
                f"{self.character.name}が反撃！"
            )

            self.player_physical_skill_hit(
                skill_name="反撃",
                base_damage=base_damage,
                attribute="neutral",
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

        denominator = (
            attacker_dex
            + defender_agi
        )

        if denominator <= 0:
            return 60

        hit_rate = (
            60
            + 39
            * attacker_dex
            / denominator
        )

        return min(
            99,
            max(
                0,
                hit_rate,
            ),
        )

    @staticmethod
    def calculate_physical_damage(
        strength,
        defender_vit,
    ):
        """
        通常攻撃
        STR ×1.0

        最終ダメージ
        基礎ダメージ - 敵VIT ×0.5
        """

        base_damage = (
            strength
            * 1.0
        )

        damage = (
            base_damage
            - defender_vit
            * 0.5
        )

        # 通常攻撃は最低1ダメージ
        return max(
            1,
            int(damage),
        )

    @staticmethod
    def roll_percent(rate):
        """%判定。"""

        roll = random.uniform(
            0,
            100,
        )

        return roll < rate