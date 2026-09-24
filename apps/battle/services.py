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

        preset = self.get_next_preset()

        # 全スキルを使い切った場合
        if preset is None:
            self.player_normal_attack()
            return "normal"

        skill = preset.skill

        # ===== MP不足 =====

        if self.player_mp < skill.mp_cost:

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

        if not self.roll_percent(
            skill.activation_rate
        ):

            self.logs.append(
                f"{self.character.name}の"
                f"「{skill.name}」は発動しなかった！"
            )

            # 次回も同じスキルを試す
            self.player_normal_attack()
            return "normal"

        # ===== 発動成功 =====

        self.player_mp -= skill.mp_cost

        self.remaining_uses[preset.id] -= 1

        self.logs.append(
            f"{self.character.name}は"
            f"「{skill.name}」を発動！ "
            f"MP -{skill.mp_cost} "
            f"（残り {self.player_mp}）"
        )

        self.execute_player_skill(skill)

        self.advance_preset()

        return skill.code

        # 成功したので次のスロットへ
        self.advance_preset()


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

                self.enemy_attack()

                if self.player_hp <= 0:
                    break

        # ===== 勝敗 =====

        if self.enemy_hp <= 0:

            self.logs.append(
                f"{self.enemy.name}を倒した！"
            )

            winner = "player"

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
                    self.character.luck
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

        # 最終的に整数化
        damage = max(
            1,
            int(damage),
        )

        self.enemy_hp -= damage

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


    def execute_player_skill(self, skill):
        """プレイヤーのスキル効果を実行する。"""

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

        self.logs.append(
            f"「{skill.name}」の効果は"
            "まだ実装されていません。"
        )


#==== プレイヤースキル実装 ===
#==== 放浪人スキル ====
    #核心を突く
    def skill_strike_core(self):
        """
        核心を突く

        (STR ×1.0 + LUK ×1.2)
        × (1.0～0.5)

        光属性・物理
        """

        # ===== 命中判定 =====

        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.character.dexterity,
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

    #一時休息
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

        before_hp = self.player_hp

        self.player_hp = min(
            self.character.max_hp,
            self.player_hp + heal_amount,
        )

        actual_heal = (
            self.player_hp
            - before_hp
        )

        self.logs.append(
            f"一時休息！ "
            f"{self.character.name}のHPが"
            f"{actual_heal}回復！ "
            f"（HP {self.player_hp}"
            f"/{self.character.max_hp}）"
        )

    #歩行者
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

    #蜃気楼
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



    #=== 敵行動実装 ===
    def enemy_attack(self):
        """敵の通常攻撃。"""

        hit_rate = self.calculate_hit_rate(
            attacker_dex=self.enemy.dexterity,
            defender_agi=self.get_player_stat(
                "agility"
            ),
        )

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

        damage = max(
            1,
            int(damage),
        )

        self.player_hp -= damage

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