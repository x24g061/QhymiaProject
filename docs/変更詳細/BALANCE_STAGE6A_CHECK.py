"""保存済みStage6-A全戦の対応・台帳・正式値・旧成果物保持を検証。"""
from collections import Counter
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage6_check_study", HERE / "BALANCE_STAGE6A_RUN.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def validate():
    root = study.OUTPUT
    source = root / "confirmed/measurement"
    manifest = json.loads((source / "manifest.json").read_text())
    records = [json.loads(line) for line in (source / "runs.jsonl").open()]
    catalog = json.loads((source / "official_catalog.json").read_text())
    assert json.loads((source / "official_catalog_unchanged.json").read_text())["unchanged"]
    assert json.loads((root / "confirmed/pilot_final/official_catalog_unchanged.json").read_text())["unchanged"]
    bosses = {b["floor"]: b for b in catalog["bosses"]}
    assert set(bosses) == set(range(1, 13))
    expected, profiles = {}, {}
    for c in manifest["cases"]:
        row = c["profile"]
        key = f"{row['profile_id']}-{c['tactic']}-u{c['use_scale']}"
        assert key not in expected
        expected[key] = (row, c["tactic"])
        profiles[row["floor"], row["job"], row["growth_version"]] = row
        assert not row.get("boss_override")
        assert row["legacy_reincarnation_points"] == 0
    assert len(expected) == 336
    counts = Counter()
    seen = set()
    for r in records:
        row, label = expected[r["case"]]
        assert (r["case"], r["seed"]) not in seen
        seen.add((r["case"], r["seed"]))
        assert manifest["seed_base"] <= r["seed"] < manifest["seed_base"]+row["evaluation_trials"]
        counts[r["case"]] += 1
        assert not r["exception"], (r["case"], r["exception"])
        assert r["winner"] in ("player", "enemy", "draw")
        assert r["evaluation_full_boss"] == bosses[row["floor"]]
        assert r["profile_stats"] == row["stats"]
        assert r["profile_attributes"] == row["attributes"]
        assert r["combat_start"] == row["combat_start"]
        assert r["display_power"] == row["power"]
        assert r["permanent_skill_codes"] == sorted(row["permanent_skill_codes"])
        assert all(n == 1 for n in Counter((a["side"], a["tick"]) for a in r["actions"]).values())
        for side in ("player", "boss"):
            initial, final = r["initial"][side], r["final"][side]
            assert initial["st"] == (100 if side == "player" else bosses[row["floor"]]["max_stamina"])
            taken = sum(e["amount"] for e in r["hp_events"] if e["target"] == side and e["kind"] != "heal")
            healed = sum(e["amount"] for e in r["hp_events"] if e["target"] == side and e["kind"] == "heal")
            assert initial["hp"] + healed - taken == final["hp"]
            assert taken == sum(r[side]["damage_taken"].values())
            assert healed == sum(r[side]["healing"].values())
            moves = [a for a in r["actions"] if a["side"] == side]
            assert len(moves) == r[side]["actions"]
            consumed = sum(a["code"] not in ("skip", "status_skip") for a in moves)*5
            assert final["st"] == max(0, initial["st"]-consumed)
        assert r["initial"]["player"]["hp"] == row["combat_start"]["max_hp"]
        assert r["initial"]["player"]["mp"] == row["combat_start"]["max_mp"]
    assert all(counts[k] == row["evaluation_trials"] for k, (row, _) in expected.items())
    for old, new in study.profile_pairs():
        for row in (old, new):
            saved = profiles[row["floor"], row["job"], row["growth_version"]]
            for field in study.FIXED + study.REPLAY_FIELDS:
                assert row[field] == saved[field]
    before = json.loads((root / "before.json").read_text())["files"]
    changed, missing = [], []
    for relative, digest in before.items():
        path = study.ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            changed.append(relative)
    assert not missing, missing
    assert set(changed) <= {"AGENTS.md"}, changed
    assert study.runner.fingerprint() == manifest["source_sha256"], "戦闘測定後に対象ソースが変わっています"
    return {"conditions": len(expected), "records": len(records), "unique_case_seeds": len(seen),
            "profile_pairs_replayed": 84, "official_bosses": 12, "all_detailed_hp_st_ledgers_valid": True,
            "missing": 0, "exceptions": 0, "loop_limits": sum(r["termination"] == "loop_limit" for r in records),
            "draws": sum(r["winner"] == "draw" for r in records),
            "old_file_fingerprints": len(before), "old_files_changed": changed, "old_files_deleted": missing,
            "battle_source_fingerprint_matches": True,
            "final_branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=study.OUTPUT / "validation_final.json")
    args = parser.parse_args()
    result = validate()
    study.write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
