from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """user_idをログインIDとして扱うユーザー管理クラス。"""

    use_in_migrations = True

    def create_user(self, user_id, password=None, **extra_fields):
        if not user_id:
            raise ValueError("user_idは必須です")

        user = self.model(
            user_id=user_id,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, user_id, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("スーパーユーザーはis_staff=Trueが必要です")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError(
                "スーパーユーザーはis_superuser=Trueが必要です"
            )

        return self.create_user(
            user_id=user_id,
            password=password,
            **extra_fields,
        )


# ===== ユーザー情報 =====


class User(AbstractUser):
    username = None

    user_id = models.CharField(
        max_length=20,
        unique=True,
        help_text="ログイン用の固有ID",
    )

    USERNAME_FIELD = "user_id"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.user_id


# ===== キャラクター情報 =====

class Character(models.Model):

    # ユーザーとキャラクターを1対1で紐づける
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="character",
    )

    # ゲーム内で表示されるキャラクター名
    name = models.CharField(
        max_length=20,
        unique=True,
    )

        # ===== 成長情報 =====

    level = models.PositiveIntegerField(
        default=1,
        help_text="キャラクターの現在レベル"
    )

    exp = models.PositiveIntegerField(
        default=0,
        help_text="現在保持している経験値"
    )

    reincarnation_count = models.PositiveIntegerField(
        default=0,
        help_text="転生した回数"
    )

    # ===== HP・MP =====

    max_hp = models.PositiveIntegerField(
        default=30,
        help_text="キャラクターの最大HP"
    )

    current_hp = models.PositiveIntegerField(
        default=30,
        help_text="キャラクターの現在HP"
    )

    max_mp = models.PositiveIntegerField(
        default=10,
        help_text="キャラクターの最大MP"
    )

    current_mp = models.PositiveIntegerField(
        default=10,
        help_text="キャラクターの現在MP"
    )

    # ===== 基本能力値 =====

    strength = models.PositiveIntegerField(
        default=5,
        help_text="筋力（STR）"
    )

    intelligence = models.PositiveIntegerField(
        default=5,
        help_text="知力（INT）"
    )

    dexterity = models.PositiveIntegerField(
        default=5,
        help_text="器用さ（DEX）"
    )

    agility = models.PositiveIntegerField(
        default=5,
        help_text="素早さ（AGI）"
    )

    vitality = models.PositiveIntegerField(
        default=5,
        help_text="体力（VIT）"
    )

    luck = models.PositiveIntegerField(
        default=5,
        help_text="運（LUK）"
    )

    # ===== 属性 =====

    fire = models.PositiveIntegerField(
        default=0,
        help_text="火属性値"
    )

    water = models.PositiveIntegerField(
        default=0,
        help_text="水属性値"
    )

    grass = models.PositiveIntegerField(
        default=0,
        help_text="草属性値"
    )

    rock = models.PositiveIntegerField(
        default=0,
        help_text="岩属性値"
    )

    light = models.PositiveIntegerField(
        default=0,
        help_text="光属性値"
    )

    dark = models.PositiveIntegerField(
        default=0,
        help_text="闇属性値"
    )

    # ===== 所持情報 =====

    gold = models.PositiveIntegerField(
        default=0,
        help_text="現在の所持金"
    )

    # ===== スタミナ =====

    max_stamina = models.PositiveIntegerField(
        default=100,
        help_text="キャラクターの最大スタミナ"
    )

    current_stamina = models.PositiveIntegerField(
        default=100,
        help_text="キャラクターの現在スタミナ"
    )

    # ===== システム情報 =====

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="キャラクター作成日時"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="キャラクター情報更新日時"
    )

    def __str__(self):
        return self.name