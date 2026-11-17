"""戦術画面・保存・探索戦闘の共通スキル認可。"""
import random

from django.db.models import Q

from .models import Skill


def available_skills(character):
    return Skill.objects.filter(
        Q(job=character.job) | Q(permanent_learners=character)
    ).distinct().order_by("id")


def inherit_skill(character, previous_job):
    """呼出元でCharacterを行ロックし、回帰と同じatomic内で呼ぶ。"""
    candidates = list(Skill.objects.filter(job=previous_job).exclude(
        permanent_learners=character
    ).order_by("id"))
    if not candidates:
        return None
    skill = random.choice(candidates)
    character.permanent_skills.add(skill)
    return skill
