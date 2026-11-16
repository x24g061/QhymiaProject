"""テストDBのみで代表ボスを測定。出力先・件数は環境変数で指定できる。"""
from collections import Counter
import json
import os
from pathlib import Path
import statistics

from django.test import TestCase

from apps.accounts.models import Character, User
from apps.battle.boss_simulation import measure_battle
from apps.battle.models import Enemy, Skill, SkillPreset


STATS = ("max_hp", "max_mp", "strength", "intelligence", "dexterity", "agility", "vitality", "luck")
# 測定用固定値。育成シミュレーションや推奨ビルドの確定値ではない。
BASELINES = {
    1: (60, 25, 14, 14, 14, 14, 14, 10),
    6: (2400, 900, 500, 500, 200, 150, 200, 150),
    7: (6000, 2000, 1200, 1200, 700, 500, 500, 400),
    12: (40000, 12000, 7000, 7000, 5000, 4000, 4500, 3000),
}
PRESETS = {
    "warrior": ["flare_blade", "steel_body", "one_hit_kill", "solid_stance", "counter_stance"],
    "wizard": ["stella", "fire", "megido", "explosion", "frost_armor"],
}


class BossSimulationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(user_id="simulation", email="simulation@example.com", password=None)
        cls.character = Character.objects.create(user=user, name="測定プレイヤー", race="human")

    def configure(self, floor, job, scale):
        character = self.character
        character.job = job
        # レベル・回帰回数はこの測定では能力値の代わりに推定しない。
        character.level = 1
        character.reincarnation_count = 0
        for key, value in zip(STATS, BASELINES[floor]):
            setattr(character, key, max(1, int(value * scale)))
        character.current_hp = character.max_hp
        character.current_mp = character.max_mp
        character.save()
        character.skill_presets.all().delete()
        for slot, code in enumerate(PRESETS[job], 1):
            SkillPreset.objects.create(character=character, skill=Skill.objects.get(code=code),
                                       slot=slot, use_count=99)
        return character

    def validate_run(self, run):
        self.assertIn(run["winner"], ("player", "enemy", "draw"))
        self.assertGreater(run["ticks"], 0)
        self.assertLessEqual(run["ticks"], 1000)
        counts = Counter((a["side"], a["tick"]) for a in run["actions"])
        self.assertTrue(all(count <= 1 for count in counts.values()))
        for side in ("player", "boss"):
            current = run[side]
            self.assertTrue(0 <= current["hp"] <= current["max_hp"])
            self.assertTrue(0 <= current["mp"] <= current["max_mp"])
            self.assertTrue(0 <= current["st"] <= current["max_st"])
            consuming_actions = sum(a["side"] == side and a["code"] not in ("skip", "status_skip")
                                    for a in run["actions"])
            self.assertEqual(current["st"], max(0, (100 if side == "player" else current["max_st"]) - consuming_actions * 5))
        if run["winner"] == "player":
            self.assertEqual(run["boss"]["hp"], 0)
        elif run["winner"] == "enemy":
            self.assertEqual(run["player"]["hp"], 0)

    def test_seed_is_reproducible_and_database_values_do_not_change(self):
        import random
        character = self.configure(7, "wizard", 1.0)
        boss = Enemy.objects.get(floor=7, is_boss=True)
        before = (Character.objects.values().get(pk=character.pk),
                  list(character.skill_presets.values()), Enemy.objects.values().get(pk=boss.pk))
        state = random.getstate()
        first = measure_battle(character, boss, 20261113)
        self.assertEqual(random.getstate(), state)
        second = measure_battle(character, boss, 20261113)
        self.assertEqual(first, second)
        self.assertEqual(before, (Character.objects.values().get(pk=character.pk),
                                 list(character.skill_presets.values()), Enemy.objects.values().get(pk=boss.pk)))
        self.validate_run(first)

    def test_representative_boss_matrix(self):
        trials = int(os.environ.get("QHYMIA_SIM_TRIALS", "1"))
        if not 1 <= trials <= 1000:
            raise ValueError("試行数は1〜1000で指定してください")
        records, groups, profiles = [], [], []
        for floor in BASELINES:
            boss = Enemy.objects.get(floor=floor, is_boss=True)
            for job in PRESETS:
                for label, scale in (("low", 0.75), ("baseline", 1.0), ("high", 1.25)):
                    character = self.configure(floor, job, scale)
                    case = f"{floor}-{job}-{label}"
                    profiles.append({"case": case, "stats": {key: getattr(character, key) for key in STATS},
                                     "raw_power": sum(getattr(character, key) for key in STATS),
                                     "race": character.race, "job": job, "attribute": "neutral",
                                     "equipment": [], "skill_codes": PRESETS[job], "slot_uses": 99,
                                     "level": character.level, "reincarnation_count": character.reincarnation_count})
                    runs = []
                    for trial in range(trials):
                        with self.subTest(case=case, trial=trial):
                            run = measure_battle(character, boss, 20261113 + trial)
                            self.validate_run(run)
                            run["case"] = case
                            records.append(run)
                            runs.append(run)
                    wins = Counter(run["winner"] for run in runs)
                    groups.append({"case": case, "trials": trials, "wins": wins["player"],
                                   "losses": wins["enemy"], "draws": wins["draw"],
                                   "win_rate": wins["player"] / trials,
                                   "mean_ticks": statistics.mean(r["ticks"] for r in runs),
                                   "median_ticks": statistics.median(r["ticks"] for r in runs),
                                   "loop_limits": sum(r["loop_limit"] for r in runs),
                                   "player_mean_actions": statistics.mean(r["player"]["actions"] for r in runs),
                                   "boss_mean_actions": statistics.mean(r["boss"]["actions"] for r in runs)})
        output = os.environ.get("QHYMIA_SIM_REPORT")
        if output:
            report = {"schema_version": 1, "seed_base": 20261113, "trials_per_case": trials,
                      "description": "仮の固定能力値・装備なし。育成到達性・推奨難易度の検証ではない。",
                      "profiles": profiles, "summary": groups, "runs": records}
            Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
