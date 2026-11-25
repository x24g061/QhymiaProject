"""成長Ver.2の境界・移行・実画面経由の保存契約。通常DBは操作しない。"""
import random
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.growth import (
    JOB_GROWTH_WEIGHTS, RACE_GROWTH_WEIGHTS, apply_character_exp,
    apply_exploration_exp, apply_stat_growth, calculate_growth_count,
    calculate_initial_points, get_growth_weights, level_up_once,
    next_reincarnation_points,
)
from apps.accounts.models import Character, User
from apps.battle.models import ArenaFloor, ArenaState, FloorProgress, Skill
from config.views import calculate_reincarnation_stats, generate_reincarnation_bonus

STATS = ["max_hp", "max_mp", "strength", "intelligence", "dexterity", "agility", "vitality", "luck"]
ATTRS = ["fire", "water", "grass", "rock", "light", "dark"]


def fixed_choices(population, weights, k):
    return [population[0]] * k


class GrowthFormulaTests(SimpleTestCase):
    def test_initial_allocation_boundaries(self):
        for r, expected in [(0, 0), (100, 12500), (149, 18625), (150, 18750),
                            (151, 18850), (152, 18950), (154, 19150), (160, 19750), (200, 23750)]:
            with self.subTest(r=r):
                self.assertEqual(calculate_initial_points(r), expected)

    def test_all_99_levels_sum_and_even_distribution(self):
        for r in [0, 50, 100, 149, 150, 151, 152, 153, 154, 158, 160, 200, 500]:
            with self.subTest(r=r):
                counts = [calculate_growth_count(r, n) for n in range(1, 100)]
                extra = 25 * max(r - 150, 0)
                self.assertEqual(sum(counts), 495 + extra)
                self.assertLessEqual(max(counts) - min(counts), 1)
                for n in range(1, 100):
                    self.assertEqual(sum(counts[:n]) - 5*n, extra*n//99)

    def test_invalid_level_up_number_does_not_modify_character(self):
        for level in [0, 100]:
            c = Character(level=level)
            with self.assertRaises(ValueError):
                level_up_once(c)
            self.assertEqual(c.level, level)

    def test_hp_and_mp_growth_keep_current_resource_rules(self):
        c = Character(current_hp=4, current_mp=2)
        self.assertEqual(apply_stat_growth(c, "hp"), "HP +8")
        self.assertEqual((c.max_hp, c.current_hp), (38, 12))
        self.assertEqual(apply_stat_growth(c, "mp"), "MP +3")
        self.assertEqual((c.max_mp, c.current_mp), (13, 2))

    def test_each_of_six_basic_stats_grows_by_one(self):
        c = Character()
        for stat in STATS[2:]:
            apply_stat_growth(c, stat)
            self.assertEqual(getattr(c, stat), 6)

    def test_zero_reincarnations_five_repeated_stats_and_three_attributes(self):
        c = Character()
        with patch("apps.accounts.growth.random.choices", side_effect=fixed_choices) as draws:
            result = level_up_once(c)
        self.assertEqual([call.kwargs["k"] for call in draws.call_args_list], [5, 3])
        self.assertEqual((c.level, c.max_hp, c.current_hp, c.fire), (2, 70, 70, 3))
        self.assertEqual(len(result["stat_growths"]), 5)
        self.assertEqual(len(result["attribute_growths"]), 3)

    def test_job_race_and_attribute_weights_are_passed_unchanged(self):
        for job in JOB_GROWTH_WEIGHTS:
            for race in RACE_GROWTH_WEIGHTS:
                c = Character(job=job, race=race, fire_growth_weight=15, water_growth_weight=4)
                expected = {s: JOB_GROWTH_WEIGHTS[job][s] + RACE_GROWTH_WEIGHTS[race][s]
                            for s in JOB_GROWTH_WEIGHTS[job]}
                with patch("apps.accounts.growth.random.choices", side_effect=fixed_choices) as draws:
                    level_up_once(c)
                self.assertEqual(get_growth_weights(c), expected)
                self.assertEqual(draws.call_args_list[0].kwargs["weights"], list(expected.values()))
                self.assertEqual(draws.call_args_list[1].kwargs["weights"], [15, 4, 1, 1, 1, 1])
                self.assertEqual(draws.call_args_list[1].kwargs["population"], ATTRS)

    def test_reincarnation_still_uses_fourteen_uniform_targets_and_old_units(self):
        for r in [149, 150, 151, 152, 154, 160, 200]:
            c = Character(reincarnation_count=r)
            rng = random.Random(20261119)
            with patch("config.views.random.choice", side_effect=rng.choice) as draws:
                points = generate_reincarnation_bonus(c)
            self.assertEqual(set(points), set(STATS + ATTRS))
            self.assertEqual(draws.call_count, calculate_initial_points(r+1))
            self.assertEqual(sum(points.values()), calculate_initial_points(r+1))
            self.assertEqual(draws.call_args.args[0], STATS + ATTRS)
            stats = calculate_reincarnation_stats(points)
            self.assertEqual(stats["max_hp"], 30 + 5*points["max_hp"])
            self.assertEqual(stats["max_mp"], 10 + 2*points["max_mp"])
            for s in STATS[2:]:
                self.assertEqual(stats[s], 5 + points[s])
            for s in ATTRS:
                self.assertEqual(stats[s], points[s])


class GrowthPersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            user_id="growth-v2",
            password=None,
            date_joined=timezone.now() - timedelta(days=7),
        )
        self.c = Character.objects.create(user=self.user, name="成長Ver2", level=50,
                                          reincarnation_count=154, current_hp=7, current_mp=2)
        self.client.force_login(self.user)

    def test_existing_level_50_gets_only_number_50_growth(self):
        with patch("apps.accounts.growth.random.choices", side_effect=fixed_choices):
            result = apply_character_exp(self.c, 100)
        self.c.refresh_from_db()
        expected = calculate_growth_count(154, 50)
        self.assertEqual(len(result["level_ups"][0]["growths"]), expected)
        self.assertEqual(self.c.max_hp, 30 + 8*expected)
        self.assertEqual((self.c.level, self.c.fire), (51, 3))
        self.assertEqual((self.c.current_hp, self.c.current_mp), (7, 2))

    def test_multiple_level_ups_each_use_their_own_number(self):
        with patch("apps.accounts.growth.random.choices", side_effect=fixed_choices):
            result = apply_exploration_exp(self.c, 350)
        self.c.refresh_from_db()
        expected = [calculate_growth_count(154, n) for n in [50, 51, 52]]
        self.assertEqual([len(u["growths"]) for u in result["level_ups"]], expected)
        self.assertEqual(self.c.max_hp, 30 + 8*sum(expected))
        self.assertEqual((self.c.level, self.c.exp, self.c.fire), (53, 50, 9))
        self.assertEqual((self.c.current_hp, self.c.current_mp), (self.c.max_hp, self.c.max_mp))

    def test_all_99_level_ups_apply_exact_total_and_cap(self):
        for r in [149, 150, 151, 152, 154, 160, 200]:
            with self.subTest(r=r):
                self.c.level, self.c.exp, self.c.reincarnation_count = 1, 0, r
                self.c.max_hp, self.c.fire = 30, 0
                with patch("apps.accounts.growth.random.choices", side_effect=fixed_choices):
                    result = apply_character_exp(self.c, 10000)
                self.c.refresh_from_db()
                self.assertEqual((self.c.level, self.c.exp), (100, 100))
                self.assertEqual(self.c.max_hp, 30 + 8*(495 + 25*max(r-150, 0)))
                self.assertEqual(self.c.fire, 297)
                self.assertEqual(result["level_up_count"], 99)
                with patch("apps.accounts.growth.random.choices") as draws:
                    apply_character_exp(self.c, 100)
                draws.assert_not_called()

    def test_exp_without_level_up_never_grants_retroactive_growth(self):
        before = {s: getattr(self.c, s) for s in STATS + ATTRS}
        apply_character_exp(self.c, 99)
        self.c.refresh_from_db()
        self.assertEqual({s: getattr(self.c, s) for s in before}, before)

    def test_exploration_and_boss_routes_use_common_growth_and_recovery(self):
        for boss in [False, True]:
            with self.subTest(boss=boss):
                Character.objects.filter(pk=self.c.pk).update(
                    level=50, exp=99, max_hp=30, current_hp=7, current_mp=2,
                    exploration_cooldown_until=None,
                )
                with (
                    patch("apps.battle.views.should_encounter_boss", return_value=boss),
                    patch("apps.battle.views.BattleEngine.run", return_value={
                        "winner": "player", "exp_gained": 1, "logs": [],
                    }),
                    patch("apps.battle.views.grant_exploration_drop", return_value=None),
                    patch("apps.accounts.growth.random.choices", side_effect=fixed_choices),
                ):
                    response = self.client.post(reverse("battle:battle"), {"floor": "1"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["boss_encounter"], boss)
                self.c.refresh_from_db()
                self.assertEqual(self.c.max_hp, 30 + 8*calculate_growth_count(154, 50))
                self.assertEqual((self.c.level, self.c.current_hp, self.c.current_mp),
                                 (51, self.c.max_hp, self.c.max_mp))
                if boss:
                    self.assertTrue(FloorProgress.objects.get(character=self.c, floor=1).boss_defeated)

    def test_beginner_exploration_grants_double_exp(self):
        self.user.date_joined = (
            timezone.now() - timedelta(hours=1)
        )
        self.user.save(update_fields=["date_joined"])

        self.c.exp = 0
        self.c.save(update_fields=["exp"])

        with (
            patch(
                "apps.battle.views.should_encounter_boss",
                return_value=False,
            ),
            patch(
                "apps.battle.views.BattleEngine.run",
                return_value={
                    "winner": "player",
                    "exp_gained": 10,
                    "logs": [],
                },
            ),
            patch(
                "apps.battle.views.grant_exploration_drop",
                return_value=None,
            ),
        ):
            response = self.client.post(
                reverse("battle:battle"),
                {"floor": "1"},
            )

        self.assertEqual(response.status_code, 200)

        self.c.refresh_from_db()

        self.assertEqual(self.c.exp, 20)
        self.assertEqual(response.context["exp_gained"], 20)
        self.assertEqual(response.context["cooldown_seconds"], 20)

    def test_arena_route_grows_without_healing_normal_resources(self):
        other_user = User.objects.create_user(user_id="growth-defender", email="gd@example.invalid", password=None)
        defender = Character.objects.create(user=other_user, name="成長防衛者")
        floor = ArenaFloor.objects.get(pk=1)
        floor.master = defender
        floor.save()
        state = ArenaState.objects.create(character=self.c, floor=floor, current_hp=7, current_mp=2)
        ArenaState.objects.create(character=defender, floor=floor, current_hp=30, current_mp=10)
        self.c.exp = 99
        self.c.save()
        with (
            patch("apps.battle.arena_services.ArenaBattleEngine.run", return_value={
                "winner": "challenger", "logs": [], "challenger_hp": 1, "challenger_mp": 1,
                "defender_hp": 0, "defender_mp": 0,
            }),
            patch("apps.battle.arena_services.random.randint", return_value=13),
            patch("apps.battle.arena_services.grant_arena_drop", return_value=None),
            patch("apps.accounts.growth.random.choices", side_effect=fixed_choices),
        ):
            response = self.client.post(reverse("battle:arena_battle"))
        self.assertEqual(response.status_code, 302)
        self.c.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual((self.c.level, self.c.exp, self.c.max_hp),
                         (51, 12, 30 + 8*calculate_growth_count(154, 50)))
        self.assertEqual((self.c.current_hp, self.c.current_mp), (7, 2))
        self.assertEqual((state.current_hp, state.current_mp), (self.c.max_hp, self.c.max_mp))

    def test_legacy_high_reincarnation_points_persist_across_two_cycles(self):
        self.c.level, self.c.job, self.c.reincarnation_count = 100, "wizard", 160
        self.c.legacy_reincarnation_points = 250
        self.c.save()
        for target in [161, 162]:
            rng = random.Random(target)
            with patch("config.views.random.choice", side_effect=rng.choice):
                preview = self.client.get(reverse("again"))
            self.assertEqual(preview.context["total_points"], 20000 + 100*(target-160))
            points = preview.context["bonus_points"]
            self.assertEqual(sum(points.values()), preview.context["total_points"])
            expected = calculate_reincarnation_stats(points)
            self.assertEqual(self.client.post(reverse("again")).status_code, 302)
            self.c.refresh_from_db()
            self.assertEqual((self.c.reincarnation_count, self.c.level, self.c.exp, self.c.job),
                             (target, 1, 0, "wanderer"))
            self.assertEqual(self.c.legacy_reincarnation_points, 250)
            self.assertEqual({s: getattr(self.c, s) for s in STATS + ATTRS}, expected)
            self.assertEqual(self.c.current_hp, self.c.max_hp)
            self.assertEqual(self.c.current_mp, self.c.max_mp)
            self.assertEqual(self.c.permanent_skills.count(), target-160)
            self.c.level = 100
            self.c.save()

    def test_old_preview_is_invalidated_before_it_can_reincarnate(self):
        self.c.level = 100
        self.c.save()
        session = self.client.session
        session["reincarnation_preview_version"] = [self.c.pk, self.c.reincarnation_count]
        session["reincarnation_bonus_points"] = dict.fromkeys(STATS + ATTRS, 999)
        session.save()
        response = self.client.post(reverse("again"))
        self.assertEqual(response.status_code, 200)
        self.c.refresh_from_db()
        self.assertEqual((self.c.level, self.c.reincarnation_count), (100, 154))
        self.assertEqual(sum(response.context["bonus_points"].values()), next_reincarnation_points(self.c))
        self.assertEqual(self.c.permanent_skills.count(), 0)


class GrowthMigrationTests(TransactionTestCase):
    def test_real_migration_preserves_all_existing_fields_and_skills(self):
        old = [("accounts", "0022_character_next_exploration_boss_guaranteed")]
        new = [("accounts", "0023_character_legacy_reincarnation_points")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        try:
            state = executor.loader.project_state(old).apps
            OldUser = state.get_model("accounts", "User")
            OldCharacter = state.get_model("accounts", "Character")
            # 全通常フィールドを移行前後で照合。Lv2以上にも補填しない。
            rows = []
            skill = Skill.objects.create(code="migration-growth-skill", name="移行確認", job="wizard")
            for r in [0, 149, 150, 151, 152, 154, 160, 200]:
                user = OldUser.objects.create(user_id=f"migration-{r}", email=f"m{r}@example.invalid")
                c = OldCharacter.objects.create(
                    user=user, name=f"移行{r}", reincarnation_count=r, level=50, exp=67,
                    max_hp=9000+r, current_hp=18, max_mp=500+r, current_mp=4,
                    strength=999, intelligence=811, fire=357,
                )
                c.permanent_skills.add(skill.pk)
                rows.append(OldCharacter.objects.filter(pk=c.pk).values().get())
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            for before in rows:
                c = Character.objects.get(pk=before["id"])
                after = Character.objects.filter(pk=c.pk).values().get()
                self.assertEqual(after.pop("legacy_reincarnation_points"), 25*max(c.reincarnation_count-150, 0))
                self.assertEqual(after, before)
                self.assertEqual(list(c.permanent_skills.values_list("pk", flat=True)), [skill.pk])
                self.assertEqual(next_reincarnation_points(c),
                                 125*c.reincarnation_count + (125 if c.reincarnation_count < 150 else 100))
            fresh = Character.objects.create(
                user=User.objects.create(user_id="post-migration", email="post@example.invalid"), name="移行後新規",
            )
            self.assertEqual(fresh.legacy_reincarnation_points, 0)
        finally:
            # 後続テストに影響しないよう、
            # 全アプリの最新マイグレーションへ復元する。
            executor = MigrationExecutor(connection)
            executor.migrate(
                executor.loader.graph.leaf_nodes()
            )
