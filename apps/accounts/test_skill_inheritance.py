"""回帰・永久習得・スキル認可の回帰契約。通常DBへの書込みなし。"""
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import Character, User
from apps.battle.models import ArenaState, Enemy, Skill, SkillPreset
from apps.battle.services import BattleEngine
from apps.battle.skill_access import available_skills
from config.views import calculate_reincarnation_stats


class InheritanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(user_id="inherit", password=None)
        self.character = Character.objects.create(user=self.user, name="継承", job="wizard", level=100)
        self.client.force_login(self.user)
        self.url = reverse("again")

    def preview(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.context["bonus_points"]

    def test_new_and_existing_characters_start_without_permanent_skills(self):
        self.assertEqual(self.character.permanent_skills.count(), 0)
        self.assertEqual(available_skills(self.character).count(), 5)

    def test_all_jobs_have_exactly_five_skills(self):
        for job, _ in Character.JOB_CHOICES:
            self.assertEqual(Skill.objects.filter(job=job).count(), 5)

    def test_reincarnation_draws_previous_job_and_restores_resources(self):
        bonus = self.preview()
        expected = calculate_reincarnation_stats(bonus)
        skills = list(Skill.objects.filter(job="wizard").order_by("id"))
        with patch("apps.battle.skill_access.random.choice", return_value=skills[2]) as choice:
            response = self.client.post(self.url)
        self.assertRedirects(response, reverse("home"))
        self.assertEqual([s.pk for s in choice.call_args.args[0]], [s.pk for s in skills])
        self.character.refresh_from_db()
        self.assertEqual(self.character.job, "wanderer")
        self.assertEqual((self.character.level, self.character.exp, self.character.reincarnation_count), (1, 0, 1))
        for key, value in expected.items():
            self.assertEqual(getattr(self.character, key), value)
        self.assertEqual(self.character.current_hp, self.character.max_hp)
        self.assertEqual(self.character.current_mp, self.character.max_mp)
        arena = ArenaState.objects.get(character=self.character)
        self.assertEqual((arena.current_hp, arena.current_mp), (self.character.max_hp, self.character.max_mp))
        self.assertEqual(list(self.character.permanent_skills.all()), [skills[2]])

    def test_seeded_draw_is_reproducible_and_only_unlearned_candidates(self):
        skills = list(Skill.objects.filter(job="wizard").order_by("id"))
        self.character.permanent_skills.add(skills[0])
        self.preview()
        rng = random.Random(20261117)
        expected = random.Random(20261117).choice(skills[1:])
        with patch("apps.battle.skill_access.random.choice", side_effect=rng.choice):
            self.client.post(self.url)
        self.assertSetEqual(set(self.character.permanent_skills.values_list("pk", flat=True)), {skills[0].pk, expected.pk})

    def test_all_five_learned_still_reincarnates(self):
        self.character.permanent_skills.add(*Skill.objects.filter(job="wizard"))
        self.preview()
        with patch("apps.battle.skill_access.random.choice") as choice:
            self.client.post(self.url)
        choice.assert_not_called()
        self.character.refresh_from_db()
        self.assertEqual(self.character.reincarnation_count, 1)
        self.assertEqual(self.character.job, "wanderer")
        self.assertEqual(self.character.permanent_skills.count(), 5)

    def test_no_ownership_cap_and_duplicate_relation_is_unique(self):
        self.character.permanent_skills.add(*Skill.objects.all())
        skill = Skill.objects.first()
        self.character.permanent_skills.add(skill)
        self.assertEqual(self.character.permanent_skills.count(), 35)
        through = Character.permanent_skills.through
        with self.assertRaises(IntegrityError), transaction.atomic():
            through.objects.create(character_id=self.character.pk, skill_id=skill.pk)

    def test_duplicate_post_and_stale_preview_do_not_award_again(self):
        self.preview()
        old = dict(self.client.session)
        self.client.post(self.url)
        self.client.post(self.url)
        # 古いフォームを次のLv100時点で再送しても回帰しない。
        Character.objects.filter(pk=self.character.pk).update(level=100)
        session = self.client.session
        session.update(old)
        session.save()
        self.client.post(self.url)
        self.character.refresh_from_db()
        self.assertEqual(self.character.reincarnation_count, 1)
        self.assertEqual(self.character.permanent_skills.count(), 1)

    def test_exception_rolls_back_award_job_stats_and_arena(self):
        self.preview()
        with patch("config.views.get_arena_state", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url)
        self.character.refresh_from_db()
        self.assertEqual((self.character.job, self.character.level, self.character.reincarnation_count), ("wizard", 100, 0))
        self.assertFalse(self.character.permanent_skills.exists())
        self.assertEqual(self.character.max_hp, 30)
        self.assertFalse(ArenaState.objects.filter(character=self.character).exists())

    def test_low_level_and_post_without_preview_cannot_inherit(self):
        self.client.post(self.url)
        self.assertFalse(self.character.permanent_skills.exists())
        self.character.level = 99
        self.character.save()
        self.client.post(self.url)
        self.assertFalse(self.character.permanent_skills.exists())

    def test_job_change_keeps_learned_and_replaces_native_access(self):
        fire = Skill.objects.get(code="fire")
        self.character.permanent_skills.add(fire)
        self.character.job = "warrior"
        self.character.save()
        available = available_skills(self.character)
        self.assertEqual(available.count(), 6)
        self.assertIn(fire, available)
        self.assertNotIn(Skill.objects.get(code="stella"), available)

    def test_tactics_accepts_native_and_inherited_and_shows_origin(self):
        inherited = Skill.objects.get(code="steel_body")
        self.character.permanent_skills.add(inherited)
        response = self.client.post(reverse("battle:tactics"), {"skill_1": inherited.pk, "skill_2": Skill.objects.get(code="fire").pk})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("battle:tactics"))
        self.assertContains(response, "永久習得：1種類")
        self.assertEqual(SkillPreset.objects.filter(character=self.character).count(), 2)

    def test_unauthorized_skill_from_another_character_is_rejected_atomically(self):
        user = User.objects.create_user(user_id="other-inherit", email="other-inherit@example.invalid", password=None)
        other = Character.objects.create(user=user, name="別人")
        stolen = Skill.objects.get(code="steel_body")
        other.permanent_skills.add(stolen)
        original = SkillPreset.objects.create(character=self.character, skill=Skill.objects.get(code="fire"), slot=1)
        response = self.client.post(reverse("battle:tactics"), {"skill_1": Skill.objects.get(code="stella").pk, "skill_2": stolen.pk})
        self.assertContains(response, "使用できない")
        original.refresh_from_db()
        self.assertEqual(original.skill.code, "fire")
        self.assertEqual(self.character.skill_presets.count(), 1)

    def test_malformed_ids_rejected_and_only_five_slots_saved(self):
        for value in ("abc", "-1", "999999999999999999999999999999999"):
            response = self.client.post(reverse("battle:tactics"), {"skill_1": value})
            self.assertContains(response, "正しくありません")
        self.client.post(reverse("battle:tactics"), {"skill_6": Skill.objects.get(code="fire").pk})
        self.assertFalse(self.character.skill_presets.exists())

    def test_inherited_attack_and_passive_work_outside_original_job(self):
        self.character.job = "warrior"
        self.character.permanent_skills.add(*Skill.objects.filter(code__in=["fire", "principle_of_freedom"]))
        for slot, code in enumerate(["principle_of_freedom", "fire"], 1):
            SkillPreset.objects.create(character=self.character, skill=Skill.objects.get(code=code), slot=slot, use_count=2)
        engine = BattleEngine(self.character, Enemy.objects.filter(is_boss=True, floor=1).get())
        with patch.object(engine, "roll_percent", return_value=True):
            action = engine.player_turn()
        self.assertEqual(action, "fire")
        self.assertTrue(engine.freedom_active)
        self.assertEqual(len(engine.presets), 2)

    def test_stale_unlearned_presets_and_extra_slots_do_not_execute(self):
        SkillPreset.objects.create(character=self.character, skill=Skill.objects.get(code="steel_body"), slot=1)
        SkillPreset.objects.create(character=self.character, skill=Skill.objects.get(code="fire"), slot=6)
        engine = BattleEngine(self.character, Enemy.objects.get(is_boss=True, floor=1))
        self.assertEqual(engine.presets, [])

    def test_anonymous_and_csrf_requests_are_rejected(self):
        self.assertEqual(Client().post(self.url).status_code, 302)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        self.assertEqual(csrf_client.post(reverse("battle:tactics")).status_code, 403)


class ConcurrentReincarnationTests(TransactionTestCase):
    def test_two_sessions_can_only_reincarnate_once(self):
        user = User.objects.create_user(user_id="parallel-inherit", password=None)
        character = Character.objects.create(user=user, name="同時回帰", job="wizard", level=100)
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(user)
            client.get(reverse("again"))
        barrier = Barrier(2)

        def post(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(reverse("again")).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(post, clients))
        self.assertTrue(all(code in (200, 302) for code in statuses))
        character.refresh_from_db()
        self.assertEqual(character.reincarnation_count, 1)
        self.assertEqual(character.permanent_skills.count(), 1)
