from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Character
from apps.battle.drops import grant_arena_drop
from .models import ArenaBattleHistory, ArenaFloor, ArenaState
from apps.inventory.models import Item, InventoryItem


User = get_user_model()


class ArenaScreenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            user_id="arena_screen", email="arena-screen@example.com", password="testpass123",
        )
        cls.other_user = User.objects.create_user(
            user_id="arena_defender", email="arena-defender@example.com", password="testpass123",
        )
        cls.character = Character.objects.create(
            user=cls.user, name="画面の挑戦者", max_hp=100, max_mp=40,
            current_hp=7, current_mp=3, arena_floor=99,
        )
        cls.defender = Character.objects.create(
            user=cls.other_user, name="画面のマスター", max_hp=100, max_mp=40,
            current_hp=5, current_mp=2,
        )
        cls.floor = ArenaFloor.objects.get(pk=10)
        cls.floor.master = cls.defender
        cls.floor.save(update_fields=["master"])
        cls.state = ArenaState.objects.create(
            character=cls.character, floor=cls.floor, current_hp=62, current_mp=19,
        )
        cls.defender_state = ArenaState.objects.create(
            character=cls.defender, floor=cls.floor, current_hp=77, current_mp=29,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("battle:arena_battle")

    def battle_result(self, winner="challenger", logs=None):
        return {
            "winner": winner,
            "logs": logs if logs is not None else ["保存された戦闘ログ"],
            "challenger_hp": 22 if winner != "defender" else 0,
            "challenger_mp": 12,
            "defender_hp": 0 if winner == "challenger" else 30,
            "defender_mp": 14,
        }

    def challenge(self, winner="challenger", follow=True, logs=None):
        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=self.battle_result(winner, logs),
        ), patch("apps.battle.arena_services.random.randint", return_value=13):
            return self.client.post(self.url, follow=follow)

    def test_challenge_requires_login(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
        self.assertFalse(ArenaBattleHistory.objects.exists())

    def test_challenge_get_does_not_start_battle(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertFalse(ArenaBattleHistory.objects.exists())
        self.state.refresh_from_db()
        self.assertEqual(self.state.current_hp, 62)

    def test_challenge_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.assertFalse(ArenaBattleHistory.objects.exists())

    def test_home_shows_arena_state_and_actual_master(self):
        Character.objects.filter(
            pk=self.defender.pk,
        ).update(
            arena_win_streak=5,
            arena_last_result="win",
        )
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["arena_state"].floor_id, 10)
        self.assertEqual([card["floor"] for card in response.context["arena_cards"]], [9, 10, 11])
        self.assertEqual(response.context["arena_master"], self.defender)
        self.assertContains(response, "画面のマスター")
        self.assertContains(response, 'data-current="77"')
        self.assertContains(response, "あなたの闘技場HP：62 / 100")
        self.assertContains(response, f'action="{self.url}"')
        self.assertContains(
            response,
            "連勝数：5連勝",
        )

        self.assertContains(
            response,
            "直近結果：勝利",
        )
        self.assertNotContains(response, f'href="{self.url}"')

    def test_home_does_not_heal_existing_arena_state(self):
        for _ in range(2):
            self.client.get(reverse("home"))
        self.state.refresh_from_db()
        self.character.refresh_from_db()
        self.assertEqual((self.state.current_hp, self.state.current_mp), (62, 19))
        self.assertEqual((self.character.current_hp, self.character.current_mp), (7, 3))

    def test_home_handles_first_and_last_floor(self):
        for floor, expected in [(1, [False, True, True]), (100, [True, True, False])]:
            with self.subTest(floor=floor):
                ArenaState.objects.filter(pk=self.state.pk).update(floor_id=floor)
                response = self.client.get(reverse("home"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual([c["exists"] for c in response.context["arena_cards"]], expected)

    def test_missing_state_is_initialized_once(self):
        self.state.delete()
        self.client.get(reverse("home"))
        state = ArenaState.objects.get(character=self.character)
        self.assertEqual((state.floor_id, state.current_hp, state.current_mp), (1, 100, 40))
        state.current_hp = 17
        state.save(update_fields=["current_hp"])
        self.client.get(reverse("home"))
        state.refresh_from_db()
        self.assertEqual(state.current_hp, 17)

    def test_vacant_claim_from_screen_starts_cooldown_without_exp(self):
        ArenaFloor.objects.filter(pk=10).update(master=None)
        response = self.client.post(self.url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.floor.refresh_from_db()
        self.state.refresh_from_db()
        self.character.refresh_from_db()
        self.assertEqual(self.floor.master_id, self.character.pk)
        self.assertEqual((self.state.current_hp, self.state.current_mp), (100, 40))
        self.assertEqual(self.character.exp, 0)
        self.assertEqual((self.character.current_hp, self.character.current_mp), (7, 3))
        self.assertGreater(self.character.exploration_cooldown_until, timezone.now())
        self.assertFalse(ArenaBattleHistory.objects.exists())
        self.assertContains(response, "空席のフロアマスターになりました")
        self.assertNotContains(response, f'action="{self.url}"')

    def test_already_master_cannot_heal_or_battle(self):
        ArenaFloor.objects.filter(pk=10).update(master=self.character)
        self.client.post(self.url)
        self.state.refresh_from_db()
        self.character.refresh_from_db()
        self.assertEqual(self.state.current_hp, 62)
        self.assertEqual(self.character.exp, 0)
        self.assertIsNone(self.character.exploration_cooldown_until)
        self.assertFalse(ArenaBattleHistory.objects.exists())

    def test_win_redirects_to_saved_result_and_awards_exp_once(self):
        response = self.challenge()
        history = ArenaBattleHistory.objects.get()
        self.assertRedirects(response, reverse("battle:arena_result", args=[history.pk]))
        self.assertEqual(history.gained_exp, 13)
        self.assertEqual(history.challenger_floor_after, 10)
        self.assertEqual(history.defender_floor_after, 11)
        self.assertContains(response, "闘技場の結果：勝利")
        self.assertContains(response, "保存された戦闘ログ")
        self.assertContains(response, "獲得経験値：13 EXP")
        self.character.refresh_from_db()
        self.assertEqual(self.character.exp, 13)
        self.assertEqual(
            self.character.arena_win_streak,
            1,
        )
        self.assertEqual(
            self.character.arena_last_result,
            "win",
        )
        self.assertEqual((self.character.current_hp, self.character.current_mp), (7, 3))

    def test_win_streak_is_incremented(self):
        Character.objects.filter(
            pk=self.character.pk,
        ).update(
            arena_win_streak=5,
            arena_last_result="win",
        )

        self.challenge(
            winner="challenger",
        )

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.arena_win_streak,
            6,
        )

        self.assertEqual(
            self.character.arena_last_result,
            "win",
        )

    def test_loss_shows_eight_exp_and_new_floor(self):
        Character.objects.filter(
            pk=self.character.pk,
        ).update(
            arena_win_streak=5,
            arena_last_result="win",
        )
        response = self.challenge("defender")

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.arena_win_streak,
            0,
        )
        self.assertEqual(
            self.character.arena_last_result,
            "loss",
        )
        history = ArenaBattleHistory.objects.get()
        self.assertEqual((history.result, history.gained_exp), ("loss", 8))
        self.assertContains(response, "闘技場の結果：敗北")
        self.assertContains(response, "獲得経験値：8 EXP")
        self.assertEqual(response.context["arena_state"].floor_id, 8)
        self.defender_state.refresh_from_db()
        self.assertEqual(self.defender_state.current_hp, 30)

    def _assert_loss_floor_move(
        self,
        start_floor,
        expected_floor,
    ):
        """
        指定階層でフロアマスターに敗北した場合、
        正しい階層へ移動することを確認する。
        """

        # 既存のフロアマスター設定を解除
        ArenaFloor.objects.filter(
            master=self.defender,
        ).update(
            master=None,
        )

        # 対象階層を取得
        floor = ArenaFloor.objects.get(
            pk=start_floor,
        )

        # 対象階層のフロアマスターを設定
        floor.master = self.defender
        floor.save(
            update_fields=["master"]
        )

        # 挑戦者と防衛者を同じ階層へ移動
        ArenaState.objects.filter(
            pk=self.state.pk,
        ).update(
            floor_id=start_floor,
        )

        ArenaState.objects.filter(
            pk=self.defender_state.pk,
        ).update(
            floor_id=start_floor,
        )

        # 挑戦者敗北
        self.challenge(
            winner="defender",
        )

        # 最新状態を取得
        self.state.refresh_from_db()

        # 想定階層へ移動していること
        self.assertEqual(
            self.state.floor_id,
            expected_floor,
        )


    def test_loss_on_floor_1_stays_on_floor_1(self):
        self._assert_loss_floor_move(
            start_floor=1,
            expected_floor=1,
        )


    def test_loss_on_floor_2_moves_to_floor_1(self):
        self._assert_loss_floor_move(
            start_floor=2,
            expected_floor=1,
        )


    def test_loss_on_floor_3_moves_to_floor_1(self):
        self._assert_loss_floor_move(
            start_floor=3,
            expected_floor=1,
        )


    def test_loss_on_floor_4_moves_to_floor_2(self):
        self._assert_loss_floor_move(
            start_floor=4,
            expected_floor=2,
        )


    def test_loss_on_floor_5_moves_to_floor_3(self):
        self._assert_loss_floor_move(
            start_floor=5,
            expected_floor=3,
        )

    def test_draw_is_distinct_from_loss(self):
        Character.objects.filter(
            pk=self.character.pk,
        ).update(
            arena_win_streak=5,
            arena_last_result="win",
        )
        response = self.challenge("draw")

        self.character.refresh_from_db()

        self.assertEqual(
            self.character.arena_win_streak,
            0,
        )
        self.assertEqual(
            self.character.arena_last_result,
            "draw",
        )
        self.assertContains(response, "闘技場の結果：引き分け")
        self.assertContains(response, "獲得経験値：8 EXP")
        self.assertEqual(ArenaBattleHistory.objects.get().result, "draw")

    def test_refresh_after_cooldown_does_not_repeat_battle_or_rewards(self):
        response = self.challenge(follow=False)
        Character.objects.filter(pk=self.character.pk).update(
            exploration_cooldown_until=timezone.now() - timedelta(seconds=1),
        )
        with patch("apps.battle.arena_services.ArenaBattleEngine.run") as run:
            for _ in range(2):
                self.assertEqual(self.client.get(response.url).status_code, 200)
            run.assert_not_called()
        self.character.refresh_from_db()
        self.assertEqual(self.character.exp, 13)
        self.assertEqual(ArenaBattleHistory.objects.count(), 1)

    def test_other_player_cannot_open_challenger_result(self):
        response = self.challenge(follow=False)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(response.url).status_code, 404)

    def test_nonexistent_result_is_404(self):
        self.assertEqual(self.client.get(reverse("battle:arena_result", args=[999999])).status_code, 404)

    def test_cooldown_blocks_challenge_without_mutation(self):
        Character.objects.filter(pk=self.character.pk).update(
            exploration_cooldown_until=timezone.now() + timedelta(seconds=40),
        )
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "クールタイム中です")
        self.assertFalse(ArenaBattleHistory.objects.exists())
        self.state.refresh_from_db()
        self.assertEqual((self.state.floor_id, self.state.current_hp), (10, 62))

    def test_cooldown_blocks_vacant_claim(self):
        ArenaFloor.objects.filter(pk=10).update(master=None)
        Character.objects.filter(pk=self.character.pk).update(
            exploration_cooldown_until=timezone.now() + timedelta(seconds=40),
        )
        self.client.post(self.url)
        self.floor.refresh_from_db()
        self.state.refresh_from_db()
        self.assertIsNone(self.floor.master_id)
        self.assertEqual(self.state.current_hp, 62)

    def test_win_level_up_heals_arena_to_new_maxima_only(self):
        def grow(character):
            character.level += 1
            character.max_hp += 5
            character.max_mp += 5
            return {"stat_growths": [], "attribute_growths": []}

        Character.objects.filter(pk=self.character.pk).update(exp=99)
        with patch("apps.accounts.growth.level_up_once", side_effect=grow):
            self.challenge()
        self.character.refresh_from_db()
        self.state.refresh_from_db()
        self.assertEqual((self.character.level, self.character.exp), (2, 12))
        self.assertEqual((self.state.current_hp, self.state.current_mp), (105, 45))
        self.assertEqual((self.character.current_hp, self.character.current_mp), (7, 3))

    def test_old_manual_floor_route_cannot_change_state(self):
        url = reverse("battle:arena_next_floor")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("home"))
        self.state.refresh_from_db()
        self.assertEqual(self.state.floor_id, 10)

    def test_missing_character_redirects_to_creation(self):
        self.character.delete()
        for method, url in [
            (self.client.get, reverse("home")),
            (self.client.post, self.url),
            (self.client.get, reverse("battle:arena_result", args=[1])),
        ]:
            with self.subTest(url=url):
                self.assertRedirects(method(url), reverse("accounts:character_create"), fetch_redirect_response=False)

    def test_result_escapes_log_content(self):
        response = self.challenge(logs=['<script>alert("test")</script>'])
        self.assertNotContains(response, '<script>alert("test")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_legacy_history_with_unknown_exp_can_be_displayed(self):
        response = self.challenge(follow=False)
        ArenaBattleHistory.objects.update(gained_exp=None)
        result = self.client.get(response.url)
        self.assertEqual(result.status_code, 200)
        self.assertNotContains(result, "None EXP")

    def test_screen_can_run_real_pvp_engine(self):
        response = self.client.post(self.url, follow=True)
        self.assertEqual(response.status_code, 200)
        history = ArenaBattleHistory.objects.get()
        self.assertIn(history.result, ["win", "loss", "draw"])
        self.assertTrue(history.battle_logs)
        self.assertIn(history.gained_exp, range(8, 14))


    def test_win_can_grant_arena_material_drop(self):
        item = Item.objects.create(
            name="闘技場テスト素材",
            category=Item.Category.MATERIAL,
        )

        with patch(
            "apps.battle.drops.random.random",
            return_value=0.0,
        ):
            self.challenge(
                winner="challenger",
            )

        inventory_item = (
            InventoryItem.objects.get(
                character=self.character,
                item=item,
            )
        )

        self.assertEqual(
            inventory_item.quantity,
            1,
        )


    def test_loss_does_not_grant_arena_drop(self):
        item = Item.objects.create(
            name="敗北時テスト素材",
            category=Item.Category.MATERIAL,
        )

        with patch(
            "apps.battle.drops.random.random",
            return_value=0.0,
        ):
            self.challenge(
                winner="defender",
            )

        self.assertFalse(
            InventoryItem.objects.filter(
                character=self.character,
                item=item,
            ).exists()
        )


    def test_arena_drop_rate_increases_with_streak_and_caps_at_ten_percent(self):
        Item.objects.create(
            name="ドロップ率テスト素材",
            category=Item.Category.MATERIAL,
        )

        cases = [
            (0, 0.01),
            (1, 0.02),
            (5, 0.06),
            (9, 0.10),
            (20, 0.10),
        ]

        for win_streak, expected_rate in cases:
            with self.subTest(
                win_streak=win_streak,
            ):
                result = grant_arena_drop(
                    character=self.character,
                    win_streak=win_streak,
                    guaranteed=True,
                )

                self.assertAlmostEqual(
                    result["drop_rate"],
                    expected_rate,
                    places=6,
                )


    def test_result_page_keeps_saved_arena_drop_after_refresh(self):
        item = Item.objects.create(
            name="結果表示テスト素材",
            category=Item.Category.MATERIAL,
        )

        with patch(
            "apps.battle.drops.random.random",
            return_value=0.0,
        ):
            response = self.challenge(
                winner="challenger",
                follow=False,
            )

        history = ArenaBattleHistory.objects.get()

        self.assertIsNotNone(
            history.drop_result,
        )
        self.assertEqual(
            history.drop_result["name"],
            "結果表示テスト素材",
        )

        result_response = self.client.get(
            response.url,
        )

        self.assertContains(
            result_response,
            "アイテム獲得：",
        )
        self.assertContains(
            result_response,
            "結果表示テスト素材",
        )

        # 再読込しても同じ履歴を表示できる
        second_response = self.client.get(
            response.url,
        )

        self.assertContains(
            second_response,
            "結果表示テスト素材",
        )

        # 再読込でアイテムが増殖しない
        inventory_item = InventoryItem.objects.get(
            character=self.character,
            item=item,
        )

        self.assertEqual(
            inventory_item.quantity,
            1,
        )