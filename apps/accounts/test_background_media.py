from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Character, User, UserSettings


@override_settings(DEBUG=False)
class BackgroundMediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            user_id="background-owner", email="owner@example.invalid"
        )
        cls.other_user = User.objects.create_user(
            user_id="background-other", email="other@example.invalid"
        )
        cls.user_settings = UserSettings.objects.create(user=cls.owner)

    def setUp(self):
        media_root = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=media_root))
        self.client.force_login(self.owner)

    @staticmethod
    def image_bytes(image_format):
        with Image.new("RGB", (4, 4), "blue") as image, BytesIO() as buffer:
            image.save(buffer, format=image_format)
            return buffer.getvalue()

    def save_background(self, filename, content):
        background = self.user_settings.background_image
        background.save(filename, ContentFile(content))
        return background

    def assert_served_image(self, url, data, content_type):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(response.headers["Content-Type"], content_type)
        self.assertEqual(response.headers["Content-Length"], str(len(data)))
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("private", response.headers["Cache-Control"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(b"".join(response.streaming_content), data)

    def test_serves_existing_jpeg_png_and_webp_with_actual_content_type(self):
        formats = [
            ("garukura.jpg", "JPEG", "image/jpeg"),
            ("背景画像.jpg", "PNG", "image/png"),
            ("background.webp", "WEBP", "image/webp"),
        ]
        for filename, image_format, content_type in formats:
            with self.subTest(image_format=image_format):
                data = self.image_bytes(image_format)
                background = self.save_background(filename, data)
                self.assertEqual(
                    background.url,
                    reverse("user_background_image", kwargs={"filename": filename}),
                )
                self.assert_served_image(background.url, data, content_type)
                self.user_settings.refresh_from_db()
                self.assertEqual(
                    self.user_settings.background_image.name,
                    f"user_backgrounds/{filename}",
                )

    def test_anonymous_and_other_users_cannot_get_background(self):
        background = self.save_background("owner.png", self.image_bytes("PNG"))
        anonymous = Client()
        self.assertRedirects(
            anonymous.get(background.url),
            f"{reverse('accounts:login')}?next={background.url}",
            fetch_redirect_response=False,
        )
        other = Client()
        other.force_login(self.other_user)
        self.assertEqual(other.get(background.url).status_code, 404)
        self.assertFalse(UserSettings.objects.filter(user=self.other_user).exists())
        UserSettings.objects.create(user=self.other_user)
        self.assertEqual(other.get(background.url).status_code, 404)

    def test_missing_and_unassigned_files_return_404(self):
        self.user_settings.background_image = "user_backgrounds/missing.png"
        self.user_settings.save(update_fields=["background_image"])
        self.assertEqual(
            self.client.get("/media/user_backgrounds/missing.png").status_code, 404
        )

        other_path = default_storage.save(
            "user_backgrounds/unassigned.png", ContentFile(self.image_bytes("PNG"))
        )
        self.assertEqual(self.client.get(f"/media/{other_path}").status_code, 404)

    def test_rejects_invalid_paths_without_opening_storage(self):
        paths = [
            "/media/user_backgrounds/%2e%2e",
            "/media/user_backgrounds/%2e%2e/sns/other.png",
            "/media/user_backgrounds/%2e%2e%5csns%5cother.png",
            "/media/user_backgrounds/other%00.png",
            "/media/sns/other.png",
        ]
        with patch.object(default_storage, "open") as open_file:
            for path in paths:
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 404)
            open_file.assert_not_called()

    def test_rejects_disallowed_and_invalid_image_content(self):
        png = self.image_bytes("PNG")
        # PNGシグネチャ、IHDR、IENDだけを残す。
        png_without_image_data = png[:33] + png[-12:]
        samples = {
            "html.jpg": b"<!doctype html><title>Invalid background</title>",
            "svg.png": b'<svg xmlns="http://www.w3.org/2000/svg"/>',
            "gif.webp": self.image_bytes("GIF"),
            "truncated.png": png[:40],
            "missing-image-data.png": png_without_image_data,
        }
        for filename, content in samples.items():
            with self.subTest(filename=filename):
                background = self.save_background(filename, content)
                self.assertEqual(self.client.get(background.url).status_code, 404)

    def test_background_appears_on_existing_pages(self):
        Character.objects.create(user=self.owner, name="背景確認")
        data = self.image_bytes("PNG")
        background = self.save_background("pages.png", data)
        for name in ("home", "accounts:palm", "accounts:settings"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), background.url)

        response = self.client.post(reverse("battle:battle"), {"floor": 1})
        self.assertTemplateUsed(response, "battle.html")
        self.assertContains(response, background.url)
        self.assert_served_image(background.url, data, "image/png")

    def test_upload_change_and_remove_through_settings(self):
        settings_url = reverse("accounts:settings")
        previous_url = None
        for filename, image_format, content_type in (
            ("first.jpg", "JPEG", "image/jpeg"),
            ("new.png", "PNG", "image/png"),
        ):
            data = self.image_bytes(image_format)
            upload = SimpleUploadedFile(filename, data, content_type=content_type)
            response = self.client.post(settings_url, {"background_image": upload})
            self.assertRedirects(response, settings_url, fetch_redirect_response=False)
            self.user_settings.refresh_from_db()
            url = self.user_settings.background_image.url
            self.assertContains(self.client.get(settings_url), url)
            self.assert_served_image(url, data, content_type)
            if previous_url:
                self.assertEqual(self.client.get(previous_url).status_code, 404)
            previous_url = url

        response = self.client.post(settings_url, {"action": "remove_background"})
        self.assertRedirects(response, settings_url, fetch_redirect_response=False)
        self.user_settings.refresh_from_db()
        self.assertFalse(self.user_settings.background_image)
        self.assertNotContains(self.client.get(settings_url), previous_url)
        self.assertEqual(self.client.get(previous_url).status_code, 404)
