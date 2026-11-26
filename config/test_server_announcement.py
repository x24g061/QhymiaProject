from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User, AdminModeAuthorizedUser
from apps.game.models import ServerAnnouncement


class ServerAnnouncementTests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            user_id="notice_admin",
            email="notice-admin@example.com",
            password="testpass123",
        )

        AdminModeAuthorizedUser.objects.create(
            user=self.admin_user
        )

        self.player_user = User.objects.create_user(
            user_id="notice_player",
            email="notice-player@example.com",
            password="testpass123",
        )

        self.edit_url = reverse("admin_server_announcement")
        self.api_url = reverse("server_announcement_api")

        self.client.force_login(self.admin_user)

        session = self.client.session
        session["admin_mode"] = True
        session.save()

    def save_announcement(self, message="再起動テスト", active=True):
        data = {"message": message}

        if active:
            data["is_active"] = "on"

        return self.client.post(self.edit_url, data)

    def test_admin_can_save_announcement(self):
        response = self.save_announcement()

        self.assertEqual(response.status_code, 302)

        announcement = ServerAnnouncement.objects.get(pk=1)

        self.assertEqual(announcement.message, "再起動テスト")
        self.assertTrue(announcement.is_active)
        self.assertEqual(announcement.updated_by, self.admin_user)

    def test_admin_can_update_announcement(self):
        self.save_announcement("変更前")
        self.save_announcement("変更後")

        self.assertEqual(ServerAnnouncement.objects.count(), 1)

        announcement = ServerAnnouncement.objects.get(pk=1)
        self.assertEqual(announcement.message, "変更後")

    def test_admin_can_disable_announcement(self):
        self.save_announcement("再起動テスト")
        self.save_announcement("再起動テスト", active=False)

        announcement = ServerAnnouncement.objects.get(pk=1)

        self.assertFalse(announcement.is_active)
        self.assertEqual(announcement.message, "再起動テスト")

    def test_player_cannot_edit_announcement(self):
        self.save_announcement("変更前")

        self.client.force_login(self.player_user)

        # セッションだけ管理者状態でも権限がなければ拒否
        session = self.client.session
        session["admin_mode"] = True
        session.save()

        self.save_announcement("不正な変更")

        announcement = ServerAnnouncement.objects.get(pk=1)
        self.assertEqual(announcement.message, "変更前")

    def test_admin_mode_required(self):
        session = self.client.session
        session["admin_mode"] = False
        session.save()

        self.save_announcement()

        self.assertFalse(
            ServerAnnouncement.objects.exists()
        )

    def test_message_over_300_characters_rejected(self):
        self.save_announcement("変更前")
        self.save_announcement("あ" * 301)

        announcement = ServerAnnouncement.objects.get(pk=1)
        self.assertEqual(announcement.message, "変更前")

    def test_message_300_characters_accepted(self):
        self.save_announcement("あ" * 300)

        announcement = ServerAnnouncement.objects.get(pk=1)
        self.assertEqual(len(announcement.message), 300)

    def test_empty_active_message_rejected(self):
        self.save_announcement("   ")

        self.assertFalse(
            ServerAnnouncement.objects.exists()
        )

    def test_api_returns_active_announcement(self):
        self.save_announcement("メンテナンス予告")

        self.client.force_login(self.player_user)

        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "is_active": True,
                "message": "メンテナンス予告",
            },
        )

    def test_api_hides_inactive_announcement(self):
        self.save_announcement("停止中", active=False)

        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "is_active": False,
                "message": "",
            },
        )

    def test_api_without_announcement(self):
        response = self.client.get(self.api_url)

        self.assertEqual(
            response.json(),
            {
                "is_active": False,
                "message": "",
            },
        )

    def test_anonymous_user_cannot_access_api(self):
        self.client.logout()

        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_edit(self):
        self.client.logout()
        self.save_announcement()

        self.assertFalse(
            ServerAnnouncement.objects.exists()
        )

    def test_get_cannot_edit_announcement(self):
        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 405)

        self.assertFalse(
            ServerAnnouncement.objects.exists()
        )

    def test_edit_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin_user)

        session = client.session
        session["admin_mode"] = True
        session.save()

        response = client.post(
            self.edit_url,
            {
                "message": "CSRFテスト",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            ServerAnnouncement.objects.exists()
        )

    def test_api_is_not_cached(self):
        response = self.client.get(self.api_url)

        self.assertIn(
            "no-store",
            response.headers.get("Cache-Control", ""),
        )
