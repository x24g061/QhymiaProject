import random


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

            # ====================================================
            # イニシアチブ加算
            # ====================================================

            # プレイヤー
            self.player_initiative += (
                self.get_player_stat(
                    "agility"
                )
            )

            # 生存している敵全員
            for enemy_combatant in (
                self.get_alive_enemy_combatants()
            ):

                enemy_combatant.initiative += (
                    enemy_combatant
                    .enemy
                    .agility
                )

            # ====================================================
            # プレイヤー行動
            # ====================================================

            if self.player_initiative >= 100:

                self.player_initiative -= 100

                # 生存敵からランダムで
                # 今回のターゲットを選択
                if not self.select_random_alive_enemy():
                    break

                target_name = (
                    self.enemy.name
                )

                action_code = (
                    self.player_turn()
                )

                self.finish_player_action(
                    action_code
                )

                # 今回狙った敵を倒した場合
                if self.enemy_hp <= 0:

                    self.logs.append(
                        f"{target_name}を倒した！"
                    )

                # 敵が全滅したら終了
                if not (
                    self.get_alive_enemy_combatants()
                ):
                    break

            # ====================================================
            # 敵行動
            # ====================================================

            for index, enemy_combatant in enumerate(
                self.enemy_combatants
            ):

                # 倒れている敵は行動しない
                if not enemy_combatant.is_alive():
                    continue

                # 行動ゲージが100未満なら
                # まだ行動できない
                if enemy_combatant.initiative < 100:
                    continue

                # この敵を現在敵として設定
                self.current_enemy_index = index

                enemy_combatant.initiative -= 100

                # 行動前は生存していたか
                was_alive = (
                    enemy_combatant.is_alive()
                )

                self.enemy_turn()

                # 毒などで自分のターン開始時に
                # 倒れた場合
                if (
                    was_alive
                    and not enemy_combatant.is_alive()
                ):
                    self.logs.append(
                        f"{enemy_combatant.name}"
                        "を倒した！"
                    )

                # プレイヤーが倒れたら終了
                if self.player_hp <= 0:
                    break

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