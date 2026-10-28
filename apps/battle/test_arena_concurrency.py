from queue import Queue
from threading import Barrier, Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase

from apps.accounts.models import Character

from .arena_services import (
    challenge_arena_master,
    claim_vacant_arena_floor,
)
from .models import ArenaBattleHistory, ArenaFloor, ArenaState


User = get_user_model()


class ArenaConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.floor, _ = ArenaFloor.objects.get_or_create(
            floor=10,
        )

        # 勝利時に旧フロアマスターが
        # 10階 → 11階へ移動するため用意する。
        self.next_floor, _ = ArenaFloor.objects.get_or_create(
            floor=11,
        )

        self.floor.master = None
        self.floor.save(
            update_fields=["master"],
        )

        self.user1 = User.objects.create_user(
            user_id="arena_concurrent_1",
            email="arena-concurrent-1@example.com",
            password="testpass123",
        )

        self.user2 = User.objects.create_user(
            user_id="arena_concurrent_2",
            email="arena-concurrent-2@example.com",
            password="testpass123",
        )

        self.character1 = Character.objects.create(
            user=self.user1,
            name="同時挑戦者1",
            max_hp=100,
            max_mp=40,
        )

        self.character2 = Character.objects.create(
            user=self.user2,
            name="同時挑戦者2",
            max_hp=100,
            max_mp=40,
        )

        ArenaState.objects.create(
            character=self.character1,
            floor=self.floor,
            current_hp=100,
            current_mp=40,
        )

        ArenaState.objects.create(
            character=self.character2,
            floor=self.floor,
            current_hp=100,
            current_mp=40,
        )

    def _claim_worker(
        self,
        character_id,
        barrier,
        results,
    ):
        close_old_connections()

        try:
            character = Character.objects.get(
                pk=character_id,
            )

            # 2スレッドをできるだけ同時に開始
            barrier.wait()

            result = claim_vacant_arena_floor(
                character,
            )

            results.put(
                ("ok", character_id, result)
            )

        except Exception as error:
            results.put(
                ("error", character_id, repr(error))
            )

        finally:
            close_old_connections()

    def test_two_players_cannot_claim_same_floor_at_same_time(
        self,
    ):
        barrier = Barrier(2)
        results = Queue()

        thread1 = Thread(
            target=self._claim_worker,
            args=(
                self.character1.pk,
                barrier,
                results,
            ),
        )

        thread2 = Thread(
            target=self._claim_worker,
            args=(
                self.character2.pk,
                barrier,
                results,
            ),
        )

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        received = [
            results.get(),
            results.get(),
        ]

        # スレッド内で例外が起きていない
        self.assertTrue(
            all(
                result[0] == "ok"
                for result in received
            ),
            received,
        )

        statuses = sorted(
            result[2]
            for result in received
        )

        # 片方だけ獲得し、もう片方はoccupiedになる
        self.assertEqual(
            statuses,
            [
                "claimed",
                "occupied",
            ],
        )

        self.floor.refresh_from_db()

        # 最終的なマスターは必ず1人だけ
        self.assertIn(
            self.floor.master_id,
            {
                self.character1.pk,
                self.character2.pk,
            },
        )


    def _challenge_worker(
        self,
        character_id,
        barrier,
        results,
    ):
        close_old_connections()

        try:
            character = Character.objects.get(
                pk=character_id,
            )

            barrier.wait()

            result = challenge_arena_master(
                character,
            )

            results.put(
                (
                    "ok",
                    character_id,
                    result,
                )
            )

        except Exception as error:
            results.put(
                (
                    "error",
                    character_id,
                    repr(error),
                )
            )

        finally:
            close_old_connections()


    def test_two_players_challenging_same_master_are_serialized(
        self,
    ):
        # 既存2人とは別にフロアマスターを用意
        master_user = User.objects.create_user(
            user_id="arena_master",
            email="arena-concurrent-master@example.com",
            password="testpass123",
        )

        master = Character.objects.create(
            user=master_user,
            name="同時対戦マスター",
            max_hp=100,
            max_mp=40,
        )

        ArenaState.objects.create(
            character=master,
            floor=self.floor,
            current_hp=100,
            current_mp=40,
        )

        self.floor.master = master
        self.floor.save(
            update_fields=["master"],
        )

        barrier = Barrier(2)
        results = Queue()

        battle_result = {
            "winner": "challenger",
            "logs": ["同時対戦テスト"],
            "challenger_hp": 50,
            "challenger_mp": 20,
            "defender_hp": 0,
            "defender_mp": 10,
        }

        with patch(
            "apps.battle.arena_services.ArenaBattleEngine.run",
            return_value=battle_result,
        ), patch(
            "apps.battle.arena_services.random.randint",
            return_value=13,
        ), patch(
            "apps.battle.drops.random.random",
            return_value=1.0,
        ):

            thread1 = Thread(
                target=self._challenge_worker,
                args=(
                    self.character1.pk,
                    barrier,
                    results,
                ),
            )

            thread2 = Thread(
                target=self._challenge_worker,
                args=(
                    self.character2.pk,
                    barrier,
                    results,
                ),
            )

            thread1.start()
            thread2.start()

            thread1.join()
            thread2.join()

        received = [
            results.get(),
            results.get(),
        ]

        # どちらの処理も異常終了していない
        self.assertTrue(
            all(
                result[0] == "ok"
                for result in received
            ),
            received,
        )

        # 戦闘は2回だけ
        self.assertEqual(
            ArenaBattleHistory.objects.count(),
            2,
        )

        # 元のマスターと実際に戦ったのは1人だけ。
        # もう1人は、その戦闘後の新マスターと戦う。
        self.assertEqual(
            ArenaBattleHistory.objects.filter(
                defender=master,
            ).count(),
            1,
        )

        self.floor.refresh_from_db()

        # 最後のマスターも必ず1人
        self.assertIn(
            self.floor.master_id,
            {
                self.character1.pk,
                self.character2.pk,
            },
        )

        # 各挑戦者に報酬が二重付与されていない
        self.character1.refresh_from_db()
        self.character2.refresh_from_db()

        self.assertEqual(
            self.character1.exp,
            13,
        )

        self.assertEqual(
            self.character2.exp,
            13,
        )