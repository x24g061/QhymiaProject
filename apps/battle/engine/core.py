import random

from apps.battle.timeline import exploration_turn_snapshot
from apps.battle.initiative import calculate_gauge_gain, action_priority


# ============================================================
# BattleEngine 戦闘進行
# ============================================================

class BattleCoreMixin:

    def run(self):
        """
        戦闘を最後まで自動実行する。

        プレイヤー:
        ・行動するたびに生存敵から
          ランダムで1体をターゲットする。

        敵:
        ・生存している敵それぞれが
          個別のイニシアチブを持つ。

        戦闘終了:
        ・プレイヤーHPが0
        ・敵が全滅
        ・最大ループ数到達
        """

        # ========================================================
        # 戦闘開始ログ
        # ========================================================

        enemy_names = ", ".join(
            enemy.enemy.name
            for enemy in self.enemy_combatants
        )

        self.logs.append(
            f"{self.character.name} VS {enemy_names}"
        )

        self.logs.append(
            "戦闘開始！"
        )

        turn_timeline = []

        reference_agi = max(
            [1.0, self.get_player_stat("agility")]
            + [
                enemy.enemy.agility
                for enemy in self.get_alive_enemy_combatants()
            ]
        )

        # 無限ループ防止
        loop_count = 0
        max_loop = 1000

        # ========================================================
        # 戦闘ループ
        # ========================================================

        while (
            self.player_hp > 0
            and self.get_alive_enemy_combatants()
            and loop_count < max_loop
        ):

            loop_count += 1


            # 全員のゲージを加算し、行動可能者を集める
            ready = []

            player_agi = self.get_player_stat("agility")
            player_before = self.player_initiative
            player_gain = calculate_gauge_gain(
                player_agi, reference_agi
            )
            self.player_initiative += player_gain

            if self.player_initiative >= 100:
                ready.append((
                    action_priority(
                        player_before, player_gain, player_agi, 0
                    ),
                    "player",
                    None,
                ))

            for index, enemy in enumerate(self.enemy_combatants):
                if not enemy.is_alive():
                    continue

                enemy_agi = enemy.enemy.agility
                before = enemy.initiative
                gain = calculate_gauge_gain(
                    enemy_agi, reference_agi
                )
                enemy.initiative += gain

                if enemy.initiative >= 100:
                    ready.append((
                        action_priority(
                            before, gain, enemy_agi, index + 1
                        ),
                        "enemy",
                        index,
                    ))

            # ゲージ到達時刻の早い順に行動
            ready.sort(key=lambda entry: entry[0])

            for _, side, index in ready:

                if self.player_hp <= 0:
                    break

                if not self.get_alive_enemy_combatants():
                    break

                if side == "player":
                    self.player_initiative -= 100

                    if not self.select_random_alive_enemy():
                        break

                    target_name = self.enemy.name
                    log_start = len(self.logs)

                    action_code = self.player_turn()
                    self.finish_player_action(action_code)

                    if self.enemy_hp <= 0:
                        self.logs.append(
                            f"{target_name}を倒した！"
                        )

                    turn_timeline.append(
                        exploration_turn_snapshot(
                            self,
                            "player",
                            self.character.name,
                            self.logs[log_start:],
                            len(turn_timeline) + 1,
                        )
                    )

                else:
                    enemy = self.enemy_combatants[index]

                    # 先の行動で倒された敵は行動しない
                    if not enemy.is_alive():
                        continue

                    self.current_enemy_index = index
                    enemy.initiative -= 100

                    was_alive = enemy.is_alive()
                    log_start = len(self.logs)

                    self.enemy_turn()

                    if was_alive and not enemy.is_alive():
                        self.logs.append(
                            f"{enemy.name}を倒した！"
                        )

                    turn_timeline.append(
                        exploration_turn_snapshot(
                            self,
                            "enemy",
                            enemy.name,
                            self.logs[log_start:],
                            len(turn_timeline) + 1,
                        )
                    )

            if self.player_hp <= 0:
                break

        # ========================================================
        # 戦闘報酬
        # ========================================================

        # 1戦につきEXPは1回だけ
        exp_gained = 0

        # ========================================================
        # 勝敗
        # ========================================================

        if not self.get_alive_enemy_combatants():

            winner = "player"

            self.logs.append(
                "敵をすべて倒した！"
            )

            # ----------------------------------------------------
            # EXP
            # ----------------------------------------------------

            exp_min, exp_max = (
                self.get_floor_exp_range()
            )

            exp_gained = random.randint(
                exp_min,
                exp_max,
            )

            self.logs.append(
                f"{exp_gained}EXPを獲得！"
            )

        elif self.player_hp <= 0:

            winner = "enemy"

            # 敗北時は階層に関係なく
            # 8EXPを獲得する
            exp_gained = 8

            self.logs.append(
                f"{self.character.name}"
                "は倒れた……"
            )

            self.logs.append(
                "敗北したが8EXPを獲得した！"
            )

        else:

            winner = "draw"

            self.logs.append(
                "戦闘が長引いたため終了しました。"
            )

        # ========================================================
        # 戦闘結果
        # ========================================================

        return {

            "winner": winner,
            "timeline": turn_timeline,

            "logs": self.logs,

            "player_hp": max(
                0,
                self.player_hp,
            ),

            "player_max_hp": (
                self.player_max_hp
            ),

            "player_max_mp": (
                self.player_max_mp
            ),

            # 今までの画面との互換用
            "enemy_hp": max(
                0,
                self.enemy_hp,
            ),

            "exp_gained": exp_gained,

            # 今回戦った敵全員の最終状態
            "enemies": [
                {
                    "name": enemy.name,
                    "hp": max(
                        0,
                        enemy.hp,
                    ),
                    "max_hp": enemy.max_hp,
                    "mp": max(
                        0,
                        enemy.mp,
                    ),
                    "max_mp": enemy.max_mp,
                    "attribute": (
                        enemy.enemy.attribute
                    ),
                }
                for enemy
                in self.enemy_combatants
            ],

            "player_stamina": (
                self.player_stamina
            ),

            "player_max_stamina": (
                self.player_max_stamina
            ),
        }


    # ========================================================
    # 階層別EXP
    # ========================================================

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