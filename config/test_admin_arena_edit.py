
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import (
    User,
    Character,
    AdminChangeLog,
)
from apps.battle.models import ArenaFloor, ArenaState


class AdminArenaEditTests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            user_id="admin_edit_test",
            email="admin-edit@example.com",
            password="testpass123",
        )

        self.player_user = User.objects.create_user(
            user_id="arena_edit_user",
            email="arena-edit@example.com",
            password="testpass123",
        )

        self.character = Character.objects.create(
            user=self.player_user,
            name="階層編集テスト",
            level=50,
            reincarnation_count=1,
            max_hp=100,
            current_hp=40,
            max_mp=40,
            current_mp=12,
        )

        self.floor1 = ArenaFloor.objects.get(floor=1)
        self.floor3 = ArenaFloor.objects.get(floor=3)
        self.floor4 = ArenaFloor.objects.get(floor=4)
        self.floor5 = ArenaFloor.objects.get(floor=5)

        self.state = ArenaState.objects.create(
            character=self.character,
            floor=self.floor3,
            current_hp=18,
            current_mp=7,
        )

        self.client.force_login(self.admin_user)

        session = self.client.session
        session["admin_mode"] = True
        session.save()

        self.url = reverse(
            "admin_player_edit",
            args=[self.character.pk],
        )

    def post_edit(self, floor, count):
        return self.client.post(
            self.url,
            {
                "edit_type": "arena_reincarnation",
                "arena_floor": floor,
                "reincarnation_count": count,
            },
        )

    def test_change_floor_and_reincarnation_count(self):
        """階層と回帰回数を同時に変更できる。"""

        response = self.post_edit(5, 3)

        self.assertEqual(response.status_code, 302)

        self.state.refresh_from_db()
        self.character.refresh_from_db()

        self.assertEqual(self.state.floor_id, 5)
        self.assertEqual(self.character.reincarnation_count, 3)

        # 通常HP/MPと闘技場HP/MPは維持
        self.assertEqual(self.character.current_hp, 40)
        self.assertEqual(self.character.current_mp, 12)
        self.assertEqual(self.state.current_hp, 18)
        self.assertEqual(self.state.current_mp, 7)

        log = AdminChangeLog.objects.get(
            target_character=self.character,
        )

        self.assertEqual(
            log.changes["arena_floor"]["before"], 3
        )
        self.assertEqual(
            log.changes["arena_floor"]["after"], 5
        )
        self.assertEqual(
            log.changes["reincarnation_count"]["after"], 3
        )

    def test_master_is_released_when_moving(self):
        """フロアマスター移動時は元の席を解放する。"""

        self.floor3.master = self.character
        self.floor3.save(update_fields=["master"])

        self.post_edit(5, 1)

        self.floor3.refresh_from_db()
        self.floor5.refresh_from_db()
        self.state.refresh_from_db()

        self.assertIsNone(self.floor3.master_id)
        self.assertIsNone(self.floor5.master_id)
        self.assertEqual(self.state.floor_id, 5)

        log = AdminChangeLog.objects.get(
            target_character=self.character,
        )
        self.assertIn("arena_master", log.changes)

    def test_same_floor_keeps_master(self):
        """階層を変えなければマスターを維持する。"""

        self.floor3.master = self.character
        self.floor3.save(update_fields=["master"])

        self.post_edit(3, 4)

        self.floor3.refresh_from_db()
        self.character.refresh_from_db()

        self.assertEqual(
            self.floor3.master_id,
            self.character.pk,
        )
        self.assertEqual(
            self.character.reincarnation_count, 4
        )

    def test_destination_master_is_not_overwritten(self):
        """移動先のフロアマスターを上書きしない。"""

        other_user = User.objects.create_user(
            user_id="other_master",
            email="other-master@example.com",
            password="testpass123",
        )
        other = Character.objects.create(
            user=other_user,
            name="移動先マスター",
        )

        ArenaState.objects.create(
            character=other,
            floor=self.floor4,
            current_hp=other.max_hp,
            current_mp=other.max_mp,
        )

        self.floor4.master = other
        self.floor4.save(update_fields=["master"])

        self.post_edit(4, 1)

        self.floor4.refresh_from_db()
        self.state.refresh_from_db()

        self.assertEqual(self.state.floor_id, 4)
        self.assertEqual(self.floor4.master_id, other.pk)

    def test_invalid_values_are_rejected(self):
        """範囲外・不正な数値は保存しない。"""

        cases = [
            (0, 1),
            (101, 1),
            ("abc", 1),
            (3, -1),
            (3, 1001),
        ]

        for floor, count in cases:
            with self.subTest(floor=floor, count=count):
                response = self.post_edit(floor, count)
                self.assertEqual(response.status_code, 302)

                self.state.refresh_from_db()
                self.character.refresh_from_db()

                self.assertEqual(self.state.floor_id, 3)
                self.assertEqual(
                    self.character.reincarnation_count, 1
                )

        self.assertEqual(AdminChangeLog.objects.count(), 0)

    def test_no_changes_does_not_create_log(self):
        """変更がない場合は操作履歴を増やさない。"""

        self.post_edit(3, 1)

        self.assertEqual(AdminChangeLog.objects.count(), 0)

    def test_admin_mode_is_required(self):
        """管理者モードでない場合は変更できない。"""

        session = self.client.session
        session["admin_mode"] = False
        session.save()

        response = self.post_edit(5, 10)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

        self.state.refresh_from_db()
        self.character.refresh_from_db()

        self.assertEqual(self.state.floor_id, 3)
        self.assertEqual(self.character.reincarnation_count, 1)

    def test_missing_arena_state_is_created(self):
        """闘技場状態がないキャラも編集できる。"""

        self.state.delete()

        response = self.post_edit(5, 2)
        self.assertEqual(response.status_code, 302)

        state = ArenaState.objects.get(
            character=self.character,
        )

        self.assertEqual(state.floor_id, 5)
        self.assertEqual(state.current_hp, 100)
        self.assertEqual(state.current_mp, 40)

    def test_failure_rolls_back_master_release(self):
        """保存失敗時にマスター解除も元に戻す。"""

        self.floor3.master = self.character
        self.floor3.save(update_fields=["master"])

        with patch.object(
            ArenaState,
            "save",
            side_effect=RuntimeError("テスト用保存失敗"),
        ):
            with self.assertRaises(RuntimeError):
                self.post_edit(5, 3)

        self.floor3.refresh_from_db()
        self.state.refresh_from_db()
        self.character.refresh_from_db()

        self.assertEqual(
            self.floor3.master_id,
            self.character.pk,
        )
        self.assertEqual(self.state.floor_id, 3)
        self.assertEqual(
            self.character.reincarnation_count, 1
        )
        self.assertEqual(AdminChangeLog.objects.count(), 0)
