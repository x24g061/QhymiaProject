from django.db import models

# Create your models here.

from django.db import models
from django.conf import settings


class FishingSession(models.Model):
    """
    釣り1回分のプレイ情報。
    魚の二重受け取りを防ぐために使用する。
    """

    class Status(models.TextChoices):
        PLAYING = "playing", "釣り中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失敗"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fishing_sessions",
    )

    rarity = models.CharField(
        max_length=20,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PLAYING,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    reward_claimed = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return f"{self.user} - {self.rarity} - {self.status}"
