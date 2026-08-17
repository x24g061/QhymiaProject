from django.db import models
from django.conf import settings


class Character(models.Model):

    # 1対1の関係にし、削除したらもう片方も削除するように紐づける
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "character",
    )

    # ゲーム内で表示されるキャラクター名(重複不可)
    name = models.CharField(
        max_length = 20,
        unique = True,
    )

    # ===== 成長情報 =====

    # キャラクターのレベル
    level = models.PositiveIntegerField(
        default = 1,
        help_text = "キャラクターの現在レベル"
    )

    # 現在の経験値
    exp = models.PositiveIntegerField(
        default = 0,
        help_text = "現在保持している経験値"
    )

    # 転生回数
    reincarnation_count = models.PositiveIntegerField(
        default = 0,
        help_text = "転生した回数"
    )

    # ===== HP・MP =====

    # 最大HP
    max_hp = models.PositiveIntegerField(
        default = 30,
        help_text = "キャラクターの最大HP"
    )

    # 現在HP
    current_hp = models.PositiveIntegerField(
        default = 30,
        help_text = "キャラクターの現在HP"
    )

    # 最大MP
    max_mp = models.PositiveIntegerField(
        default = 10,
        help_text = "キャラクターの最大MP"
    )

    # 現在MP
    current_mp = models.PositiveIntegerField(
        default = 10,
        help_text = "キャラクターの現在MP"
    )

    # ===== 基本能力値 =====

    # 筋力（物理攻撃）
    strength = models.PositiveIntegerField(
        default = 5,
        help_text = "筋力（STR）"
    )

    # 知力（魔法攻撃・魔法防御）
    intelligence = models.PositiveIntegerField(
        default = 5,
        help_text = "知力（INT）"
    )

    # 器用さ（命中率など）
    dexterity = models.PositiveIntegerField(
        default = 5,
        help_text = "器用さ（DEX）"
    )

    # 素早さ（行動速度・回避率）
    agility = models.PositiveIntegerField(
        default = 5,
        help_text = "素早さ（AGI）"
    )

    # 体力（防御力・HP補正）
    vitality = models.PositiveIntegerField(
        default = 5,
        help_text = "体力（VIT）"
    )

    # 運（クリティカル）
    luck = models.PositiveIntegerField(
        default = 5,
        help_text = "運（LUK）"
    )

    # ===== 属性 =====

    # 火属性
    fire = models.PositiveIntegerField(
        default = 0,
        help_text = "火属性値"
    )

    # 水属性
    water = models.PositiveIntegerField(
        default = 0,
        help_text = "水属性値"
    )

    # 草属性
    grass = models.PositiveIntegerField(
        default = 0,
        help_text = "草属性値"
    )

    # 岩属性
    rock = models.PositiveIntegerField(
        default = 0,
        help_text = "岩属性値"
    )

    # 光属性
    light = models.PositiveIntegerField(
        default = 0,
        help_text = "光属性値"
    )

    # 闇属性
    dark = models.PositiveIntegerField(
        default = 0,
        help_text = "闇属性値"
    )

    # ===== 所持情報 =====

    # 所持金
    gold = models.PositiveIntegerField(
        default = 0,
        help_text = "現在の所持金"
    )

    # ===== スタミナ =====

    # 最大スタミナ
    max_stamina = models.PositiveIntegerField(
        default = 100,
        help_text = "キャラクターの最大スタミナ"
    )

    # 現在のスタミナ
    current_stamina = models.PositiveIntegerField(
        default = 100,
        help_text = "キャラクターの現在スタミナ"
    )

    # ===== システム情報 =====

    # キャラクター作成日時
    created_at = models.DateTimeField(
        auto_now_add = True,
        help_text = "キャラクター作成日時"
    )

    # キャラクター更新日時
    updated_at = models.DateTimeField(
        auto_now = True,
        help_text = "キャラクター情報更新日時"
    )

    # 文字列として表示される名前
    def __str__(self):
        return self.name