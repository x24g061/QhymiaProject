from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


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

    email = models.EmailField(
        unique=True,
    )

    USERNAME_FIELD = "user_id"
    REQUIRED_FIELDS = ["email"]

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

    # ===== 種族・職業 =====

    RACE_CHOICES = [
        ("human", "ヒューマン"),
        ("elf", "エルフ"),
        ("dwarf", "ドワーフ"),
        ("dragonia", "ドラゴニア"),
        ("witch", "ウィッチ"),
        ("fairy", "フェアリー"),
        ("demonia", "デモニア"),
    ]

    JOB_CHOICES = [
        ("grappler", "拳闘士"),
        ("warrior", "重戦士"),
        ("hunter", "狩人"),
        ("wizard", "ウィザード"),
        ("priest", "プリースト"),
        ("wanderer", "放浪人"),
        ("assassin", "暗殺者"),
    ]

    race = models.CharField(
        max_length=20,
        choices=RACE_CHOICES,
        default="human",
        help_text="キャラクターの種族",
    )

    job = models.CharField(
        max_length=20,
        choices=JOB_CHOICES,
        default="wanderer",
        help_text="キャラクターの職業",
    )

    # ===== キャラクター画像 =====

    character_image_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="使用するキャラクター画像番号",
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

    # 属性成長ウェイト
    # 値が高い属性ほど、
    # レベルアップ時に成長しやすくなる。
    fire_growth_weight = models.PositiveIntegerField(default=1)
    water_growth_weight = models.PositiveIntegerField(default=1)
    grass_growth_weight = models.PositiveIntegerField(default=1)
    rock_growth_weight = models.PositiveIntegerField(default=1)
    light_growth_weight = models.PositiveIntegerField(default=1)
    dark_growth_weight = models.PositiveIntegerField(default=1)

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

    # ===== 探索クールタイム =====

    last_explored_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="最後に探索した日時"
    )

    exploration_cooldown_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="現在の探索クールタイム終了日時"
    )

    exploration_cooldown_reduced_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="探索クールタイム短縮効果の終了日時"
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

       # ===== 闘技場 =====

    # 現在いる闘技場の階層
    arena_floor = models.PositiveIntegerField(
        default=1,
        help_text="現在の闘技場階層"
    )
    
    # 現在の連勝数
    arena_win_streak = models.PositiveIntegerField(
        default=0,
        help_text="闘技場での現在の連勝数"
    )

    # 直近の闘技場対戦結果
    ARENA_RESULT_CHOICES = [
        ("none", "対戦なし"),
        ("win", "勝利"),
        ("loss", "敗北"),
        ("draw", "引き分け"),
    ]

    arena_last_result = models.CharField(
        max_length=10,
        choices=ARENA_RESULT_CHOICES,
        default="none",
        help_text="直近の闘技場対戦結果"
    )

    arena_next_floor_unlocked = models.BooleanField(
        default=False,
        help_text="次の闘技場階層への挑戦が解禁されているか"
 )
    


    # ===== 探索クールタイム処理 =====

    def is_exploration_cooldown_reduced(self):
        """探索CT短縮効果が現在有効か判定する。"""
        if not self.exploration_cooldown_reduced_until:
            return False

        return (
            self.exploration_cooldown_reduced_until
            > timezone.now()
        )

    def get_exploration_cooldown_seconds(self):
        """現在適用される探索CT秒数を返す。"""
        if self.is_exploration_cooldown_reduced():
            return 20

        return 40

    def get_exploration_cooldown_remaining(self):
        """現在の探索CT残り秒数を返す。"""
        if not self.exploration_cooldown_until:
            return 0

        remaining = (
            self.exploration_cooldown_until
            - timezone.now()
        ).total_seconds()

        return max(0, int(remaining))

    def __str__(self):
        return self.name

    @property
    def character_image_path(self):
        if not self.character_image_id:
            return None

        return (
            f"images/characters/"
            f"{self.character_image_id:03d}.png"
        )

    def get_main_attribute(self):
        """
        キャラクターの得意属性を返す。

        条件:
        ・6属性の中で最高値が1つだけ
        ・その最高値が平均値×1.5を超えている

        条件を満たさない場合は無属性。
        """

        attributes = {
            "fire": self.fire,
            "water": self.water,
            "grass": self.grass,
            "rock": self.rock,
            "light": self.light,
            "dark": self.dark,
        }

        values = list(
            attributes.values()
        )

        average = (
            sum(values)
            / len(values)
        )

        max_value = max(values)

        # 最高値の属性を全部取得
        max_attributes = [
            attribute
            for attribute, value
            in attributes.items()
            if value == max_value
        ]

        # 最高値が複数なら無属性
        if len(max_attributes) != 1:
            return "neutral"

        # 平均値×1.5を超えていなければ無属性
        if max_value <= average * 1.5:
            return "neutral"

        return max_attributes[0]


    def get_main_attribute_display(self):
        """
        得意属性を日本語表示で返す。
        """

        display_names = {
            "fire": "火",
            "water": "水",
            "grass": "草",
            "rock": "岩",
            "light": "光",
            "dark": "闇",
            "neutral": "無",
        }

        return display_names[
            self.get_main_attribute()
        ]

    def get_equipment_fusion_multiplier(self):
        """
        装備合成成功率に掛ける
        種族補正を返す。

        ドワーフ:
        成功率 ×1.5
        """

        if self.race == "dwarf":
            return 1.5

        return 1.0