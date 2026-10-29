
import time
from queue import Queue
from threading import Event, Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import close_old_connections
from django.test import RequestFactory, TransactionTestCase

from apps.accounts.models import Character

from .models import Enemy, FloorProgress, ArenaFloor, ArenaState
from .arena_services import (
    claim_vacant_arena_floor,
    _start_arena_cooldown,
)
from .views import battle


User = get_user_model()


class ExplorationConcurrencyTests(TransactionTestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            user_id="exploration_test",
            email="exploration-concurrent@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.user,
            name="同時探索テスト",
        )

        Enemy.objects.create(
            name="テスト用モンスター",
            floor=1,
            is_boss=False,
        )

    def _explore(self, results):
        close_old_connections()

        try:
            request = RequestFactory().post(
                "/battle/",
                {"floor": "1"},
            )

            request.user = User.objects.get(
                pk=self.user.pk,
            )
            request.session = {}
            request._messages = FallbackStorage(request)

            response = battle(request)

            results.put(("ok", response.status_code))

        except Exception as error:
            results.put(("error", repr(error)))

        finally:
            close_old_connections()

    def test_same_account_cannot_explore_twice(self):
        results = Queue()
        battle_started = Event()
        allow_battle_to_finish = Event()

        def fake_battle_run(engine):
            battle_started.set()

            if not allow_battle_to_finish.wait(timeout=10):
                raise TimeoutError("戦闘待機がタイムアウトしました")

            return {
                "winner": "player",
                "exp_gained": 10,
                "logs": ["テスト戦闘"],
                "player_hp": 30,
                "player_max_hp": 30,
                "player_stamina": 100,
                "player_max_stamina": 100,
                "enemies": [
                    {
                        "name": "テスト用モンスター",
                        "hp": 0,
                        "max_hp": 30,
                        "mp": 0,
                        "max_mp": 10,
                    }
                ],
            }

        with (
            patch(
                "apps.battle.views.BattleEngine.run",
                new=fake_battle_run,
            ),
            patch(
                "apps.battle.views.should_encounter_boss",
                return_value=False,
            ),
            patch(
                "apps.battle.views.grant_exploration_drop",
                return_value=None,
            ) as mock_drop,
        ):
            thread1 = Thread(
                target=self._explore,
                args=(results,),
            )
            thread2 = Thread(
                target=self._explore,
                args=(results,),
            )

            try:
                thread1.start()

                # 1回目の戦闘が処理中の状態を作る
                self.assertTrue(
                    battle_started.wait(timeout=10),
                    "1回目の戦闘が開始されませんでした",
                )

                # 同じアカウントから2回目の探索
                thread2.start()

                # 2回目にDBロックを取得する機会を与える
                time.sleep(0.2)

            finally:
                allow_battle_to_finish.set()

                for thread in (thread1, thread2):
                    if thread.ident is not None:
                        thread.join(timeout=15)

        self.assertFalse(thread1.is_alive())
        self.assertFalse(thread2.is_alive())

        received = [
            results.get_nowait(),
            results.get_nowait(),
        ]

        self.assertEqual(
            sorted(received),
            [("ok", 200), ("ok", 302)],
        )

        self.character.refresh_from_db()

        # EXPが1回分しか増えていない
        self.assertEqual(self.character.exp, 10)

        # 探索回数も1回だけ
        progress = FloorProgress.objects.get(
            character=self.character,
            floor=1,
        )
        self.assertEqual(progress.exploration_count, 1)

        # ドロップ抽選も1回だけ
        self.assertEqual(mock_drop.call_count, 1)

        # クールタイムが設定されている
        self.assertIsNotNone(
            self.character.exploration_cooldown_until,
        )



    def test_exploration_and_arena_share_cooldown(self):
        """探索中に同じキャラが闘技場の空席を獲得できない。"""

        floor, _ = ArenaFloor.objects.get_or_create(
            floor=1,
        )

        ArenaState.objects.create(
            character=self.character,
            floor=floor,
            current_hp=self.character.max_hp,
            current_mp=self.character.max_mp,
        )

        exploration_started = Event()
        release_exploration = Event()
        exploration_results = Queue()
        arena_results = Queue()

        def fake_battle_run(engine):
            exploration_started.set()

            if not release_exploration.wait(timeout=10):
                raise TimeoutError("探索処理がタイムアウトしました")

            return {
                "winner": "player",
                "exp_gained": 10,
                "logs": ["探索・闘技場競合テスト"],
                "player_hp": 30,
                "player_max_hp": 30,
                "player_stamina": 100,
                "player_max_stamina": 100,
                "enemies": [
                    {
                        "name": "テスト用モンスター",
                        "hp": 0,
                        "max_hp": 30,
                        "mp": 0,
                        "max_mp": 10,
                    }
                ],
            }

        def arena_worker():
            close_old_connections()

            try:
                character = Character.objects.get(
                    pk=self.character.pk,
                )

                result = claim_vacant_arena_floor(character)
                arena_results.put(("ok", result))

            except ValueError as error:
                arena_results.put(("rejected", str(error)))

            except Exception as error:
                arena_results.put(("error", repr(error)))

            finally:
                close_old_connections()

        with (
            patch(
                "apps.battle.views.BattleEngine.run",
                new=fake_battle_run,
            ),
            patch(
                "apps.battle.views.should_encounter_boss",
                return_value=False,
            ),
            patch(
                "apps.battle.views.grant_exploration_drop",
                return_value=None,
            ),
        ):
            exploration_thread = Thread(
                target=self._explore,
                args=(exploration_results,),
            )

            arena_thread = Thread(
                target=arena_worker,
            )

            try:
                exploration_thread.start()

                self.assertTrue(
                    exploration_started.wait(timeout=10),
                    "探索が開始されませんでした",
                )

                arena_thread.start()
                time.sleep(0.2)

            finally:
                release_exploration.set()

                for thread in (exploration_thread, arena_thread):
                    if thread.ident is not None:
                        thread.join(timeout=15)

        self.assertFalse(exploration_thread.is_alive())
        self.assertFalse(arena_thread.is_alive())

        # 探索は成功する
        self.assertEqual(
            exploration_results.get_nowait(),
            ("ok", 200),
        )

        # 闘技場は共通クールタイムで拒否される
        arena_status, arena_message = arena_results.get_nowait()

        self.assertEqual(arena_status, "rejected")
        self.assertIn("クールタイム", arena_message)

        # 闘技場の空席は獲得されていない
        floor.refresh_from_db()
        self.assertIsNone(floor.master_id)

        # 探索報酬は1回分
        self.character.refresh_from_db()
        self.assertEqual(self.character.exp, 10)

        progress = FloorProgress.objects.get(
            character=self.character,
            floor=1,
        )
        self.assertEqual(progress.exploration_count, 1)



    def test_arena_claim_prevents_parallel_exploration(self):
        """闘技場の空席獲得中に探索を二重実行できない。"""

        floor, _ = ArenaFloor.objects.get_or_create(
            floor=1,
        )
        floor.master = None
        floor.save(update_fields=["master"])

        ArenaState.objects.create(
            character=self.character,
            floor=floor,
            current_hp=self.character.max_hp,
            current_mp=self.character.max_mp,
        )

        arena_started = Event()
        allow_arena_finish = Event()

        arena_results = Queue()
        exploration_results = Queue()

        def delayed_arena_cooldown(character):
            # 実際のクールタイム設定を実行
            _start_arena_cooldown(character)

            # トランザクション確定前で一時停止
            arena_started.set()

            if not allow_arena_finish.wait(timeout=10):
                raise TimeoutError(
                    "闘技場処理がタイムアウトしました"
                )

        def arena_worker():
            close_old_connections()

            try:
                character = Character.objects.get(
                    pk=self.character.pk,
                )

                result = claim_vacant_arena_floor(
                    character
                )

                arena_results.put(("ok", result))

            except Exception as error:
                arena_results.put(("error", repr(error)))

            finally:
                close_old_connections()

        with (
            patch(
                "apps.battle.arena_services._start_arena_cooldown",
                side_effect=delayed_arena_cooldown,
            ),
            patch(
                "apps.battle.views.BattleEngine.run",
            ) as mock_battle_run,
        ):
            arena_thread = Thread(
                target=arena_worker,
            )

            exploration_thread = Thread(
                target=self._explore,
                args=(exploration_results,),
            )

            try:
                # 闘技場を先に開始
                arena_thread.start()

                self.assertTrue(
                    arena_started.wait(timeout=10),
                    "闘技場処理が開始されませんでした",
                )

                # 闘技場の処理中に探索を開始
                exploration_thread.start()

                time.sleep(0.2)

            finally:
                allow_arena_finish.set()

                for thread in (
                    arena_thread,
                    exploration_thread,
                ):
                    if thread.ident is not None:
                        thread.join(timeout=15)

        self.assertFalse(arena_thread.is_alive())
        self.assertFalse(exploration_thread.is_alive())

        # 闘技場の空席獲得は成功
        self.assertEqual(
            arena_results.get_nowait(),
            ("ok", "claimed"),
        )

        # 探索はクールタイムで拒否
        self.assertEqual(
            exploration_results.get_nowait(),
            ("ok", 302),
        )

        # 探索の戦闘処理は実行されていない
        mock_battle_run.assert_not_called()

        # 闘技場のマスターになっている
        floor.refresh_from_db()
        self.assertEqual(
            floor.master_id,
            self.character.pk,
        )

        # EXPは増えていない
        self.character.refresh_from_db()
        self.assertEqual(self.character.exp, 0)

        # 探索回数は増えていない
        self.assertFalse(
            FloorProgress.objects.filter(
                character=self.character,
                floor=1,
            ).exists()
        )

        # 共通クールタイムは設定されている
        self.assertIsNotNone(
            self.character.exploration_cooldown_until
        )

