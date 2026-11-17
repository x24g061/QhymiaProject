"""通常DBを使用しない、有限件数のVer.2測定ランナー。"""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import setup_databases, teardown_databases

from apps.battle.models import Enemy
from apps.battle import simulation_v2 as sim


def fingerprint():
    files = sorted((sim.ROOT / "apps/battle").rglob("*.py"))
    files += [sim.ROOT / "apps/accounts/growth.py", sim.ROOT / "apps/accounts/models.py",
              sim.ROOT / "apps/inventory/services.py", sim.ROOT / "apps/inventory/models.py",
              sim.ROOT / "config/views.py", sim.PROFILE_FILE.with_suffix(".py"), sim.PROFILE_FILE]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(sim.ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def cases(options):
    rows = list(sim.load_profiles(comparisons=options.get("comparisons", "none") != "none"))
    for row in rows:
        if options.get("comparisons") == "only" and not row.get("comparison_only"):
            continue
        if options["floors"] and row["floor"] not in options["floors"]:
            continue
        if options["jobs"] and row["job"] not in options["jobs"]:
            continue
        if options["profiles"] and row["profile_id"] not in options["profiles"]:
            continue
        if options["variants"] and row["variant"] not in options["variants"]:
            continue
        if options["smoke"] and (row["seed"] != 20261116 or (row["floor"] >= 7 and not row["variant"].startswith("mid-"))):
            continue
        for tactic in options["tactics"]:
            for scale in options["use_scales"]:
                if tactic == "A" and scale != 1:
                    continue
                yield row, tactic, scale


class Command(BaseCommand):
    help = "隔離PostgreSQLテストDBでのみボス戦を測定する（通常DB操作なし）"
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--isolated-test-db", action="store_true")
        parser.add_argument("--output", required=True)
        parser.add_argument("--trials", type=int, default=3)
        parser.add_argument("--seed-base", type=int, default=20261117)
        parser.add_argument("--floors", type=int, nargs="+")
        parser.add_argument("--jobs", nargs="+", choices=list(sim.TACTICS))
        parser.add_argument("--profiles", nargs="+")
        parser.add_argument("--variants", nargs="+")
        parser.add_argument("--tactics", nargs="+", choices=list("ABCD"), default=["B"])
        parser.add_argument("--use-scales", nargs="+", type=int, default=[1])
        parser.add_argument("--smoke", action="store_true")
        parser.add_argument("--comparisons", choices=["none", "include", "only"], default="none")
        parser.add_argument("--plan", action="store_true")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--detail", action="store_true")
        parser.add_argument("--max-battles", type=int, default=20000)
        parser.add_argument("--seconds-per-battle", type=float)

    def handle(self, *args, **options):
        if not options["isolated_test_db"]:
            raise CommandError("--isolated-test-dbが必須です。通常DBでの実行を拒否しました")
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQLのみ対応します")
        if not 1 <= options["trials"] <= 100000 or any(s < 1 for s in options["use_scales"]):
            raise CommandError("trials/use-scalesが範囲外です")
        selected = list(cases(options))
        if not selected:
            raise CommandError("測定対象がありません")
        total = len(selected)*options["trials"]
        self.stdout.write(f"conditions={len(selected)} battles={total}")
        if options["seconds_per_battle"]:
            self.stdout.write(f"estimated_seconds={total*options['seconds_per_battle']:.1f}")
        if options["plan"]:
            return
        if total > options["max_battles"]:
            raise CommandError("max-battlesを超過。先に--planで規模を確認してください")

        output = Path(options["output"])
        output.mkdir(parents=True, exist_ok=True)
        journal = output / "runs.jsonl"
        manifest_path = output / "manifest.json"
        config = {"schema": sim.SCHEMA, "source_sha256": fingerprint(),
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=sim.ROOT).strip(),
            "engine": "apps.battle.services.BattleEngine", "postgresql": True,
            "profile_sha256": hashlib.sha256(sim.PROFILE_FILE.read_bytes()).hexdigest(),
            "trials": options["trials"], "seed_base": options["seed_base"], "detail": options["detail"],
            "cases": [{"profile": row, "tactic": tactic, "use_scale": scale,
                       "slots": sim.tactic(row["job"], tactic, scale)} for row, tactic, scale in selected],
            "notes": sim.TACTIC_NOTES}
        completed = []
        if manifest_path.exists():
            if not options["resume"]:
                raise CommandError("既存出力は上書きしません。--resumeまたは別の出力先を指定してください")
            if json.loads(manifest_path.read_text()) != json.loads(json.dumps(config)):
                raise CommandError("ソース/条件が異なるため再開を拒否しました")
            if journal.exists():
                # 不完全な行は変更・削除せず、復旧が必要であることを報告する。
                for line in journal.read_text().splitlines():
                    try:
                        completed.append(json.loads(line))
                    except json.JSONDecodeError:
                        raise CommandError("JSONLに不完全行があります。出力を保持して別ディレクトリで再実行してください")
        else:
            if journal.exists():
                raise CommandError("manifestのない既存JSONLを検出しました")
            manifest_path.write_text(json.dumps(config, ensure_ascii=False, indent=2)+"\n")
        keys = {(r["case"], r["seed"]) for r in completed}
        if len(keys) != len(completed):
            raise CommandError("JSONLのcase/seedが重複しています")
        name = "test_qhymia_simv2_" + uuid.uuid4().hex
        previous_test_name = connection.settings_dict.get("TEST", {}).get("NAME")
        connection.settings_dict["TEST"]["NAME"] = name
        old_config = None
        start = time.perf_counter()
        try:
            # postgresの管理接続で名前の衝突だけ確認。既存DBは削除・再利用しない。
            with connection._nodb_cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name])
                if cursor.fetchone():
                    raise CommandError("専用DB名が既存DBと衝突しました")
            old_config = setup_databases(verbosity=0, interactive=False, aliases={"default"})
            with sim.authorized_database(name), journal.open("a") as destination:
                bosses = list(Enemy.objects.filter(is_boss=True).order_by("floor").values(
                    "name", "floor", "attribute", "max_hp", "max_mp", "strength", "intelligence",
                    "dexterity", "agility", "vitality", "luck", "max_stamina", "skill_codes"))
                for index, (row, tactic, scale) in enumerate(selected):
                    case = f"{row['profile_id']}-{tactic}-u{scale}"
                    character = sim.prepare_profile(row, tactic, scale)
                    boss = Enemy.objects.get(floor=row["floor"], is_boss=True)
                    for trial in range(options["trials"]):
                        seed = options["seed_base"]+trial
                        if (case, seed) in keys:
                            continue
                        began = time.perf_counter()
                        try:
                            record = sim.measure(character, boss, seed, detail=options["detail"])
                        except Exception as error:
                            record = {"seed": seed, "exception": type(error).__name__+": "+str(error), "winner": None}
                        record.update(case=case, profile_id=row["profile_id"], floor=row["floor"], job=row["job"],
                                      variant=row["variant"], tactic=tactic, use_scale=scale,
                                      elapsed_seconds=time.perf_counter()-began)
                        destination.write(json.dumps(record, ensure_ascii=False)+"\n")
                        destination.flush()
                        completed.append(record)
                    if (index+1) % 7 == 0 or index+1 == len(selected):
                        self.stdout.write(f"{index+1}/{len(selected)} conditions; {len(completed)} runs; {time.perf_counter()-start:.1f}s", ending="\n")
                        self.stdout.flush()
        finally:
            if old_config is not None:
                teardown_databases(old_config, verbosity=0)
            connection.settings_dict["TEST"]["NAME"] = previous_test_name

        groups = defaultdict(list)
        for run in completed:
            groups[run["case"]].append(run)
        summaries = []
        for case, runs in groups.items():
            row = {k: runs[0][k] for k in ("case", "profile_id", "floor", "job", "variant", "tactic", "use_scale")}
            summaries.append(row | sim.summarize(runs))
        aggregates = {}
        for dimension in ("floor", "job", "tactic", "variant", "use_scale"):
            grouped = defaultdict(list)
            for run in completed:
                grouped[str(run[dimension])].append(run)
            aggregates[dimension] = {key: sim.summarize(runs) for key, runs in grouped.items()}
        job_rates = [s["win_rate"] for s in aggregates["job"].values() if s["win_rate"] is not None]
        report = {"conditions": summaries, "aggregates": aggregates, "bosses": bosses, "pooled": sim.summarize(completed),
                  "equal_job_mean": sum(job_rates)/7 if len(job_rates) == 7 else None,
                  "seconds": sum(r["elapsed_seconds"] for r in completed),
                  "battles_per_second": len(completed)/sum(r["elapsed_seconds"] for r in completed)}
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
        with (output / "summary.csv").open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows(summaries)
        with (output / "runs.csv").open("w", newline="") as target:
            fields = ["case", "seed", "floor", "job", "variant", "tactic", "use_scale", "winner", "loops", "termination", "exception", "action_difference", "player", "boss", "initial", "final"]
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            for run in completed:
                writer.writerow({k: json.dumps(run[k], ensure_ascii=False) if isinstance(run.get(k), dict) else run.get(k) for k in fields})
        self.stdout.write(json.dumps(report["pooled"], ensure_ascii=False))
        self.stdout.write(f"battles_per_second={report['battles_per_second']:.3f}")
