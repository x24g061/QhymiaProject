# ============================================================
# BattleEngine スキル振り分け処理
# ============================================================

class BattleSkillExecutorMixin:

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

            original_index = (
                self.current_enemy_index
            )

            target_indexes = (
                self.get_alive_enemy_indexes()
            )

            # 再帰する前に解除して
            # 無限ループを防ぐ
            self.mirage_active = False

            self.logs.append(
                "蜃気楼の効果！ "
                "攻撃対象が敵全体になった！"
            )

            for index in target_indexes:

                if not (
                    self.enemy_combatants[index]
                    .is_alive()
                ):
                    continue

                self.current_enemy_index = index

                self.execute_player_skill(
                    skill
                )

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