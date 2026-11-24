"""Stage6-B成果物の全戦・固定条件・単一能力・旧ファイル保持を照合。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage6b_check_report", HERE / "BALANCE_STAGE6B_REPORT.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
study = report.study


def validate(root):
    frozen = json.loads((study.SOURCE / "official_catalog.json").read_text())
    formal = {b["floor"]: b for b in frozen["bosses"]}
    result = {"phases": {}}
    all_keys = set()
    for phase in ("pilot", "screen", "confirm"):
        path = root / phase
        manifest = json.loads((path / "manifest.json").read_text())
        assert json.loads((path / "official_catalog.json").read_text()) == frozen
        assert json.loads((path / "official_catalog_unchanged.json").read_text())["unchanged"]
        meta = json.loads((path / "study_metadata.json").read_text())
        assert meta["c_at_12_is_range_not_target"]
        assert meta["crossing_is_separate_not_selection_requirement"]
        assert meta["wrapper_sha256"] == hashlib.sha256((HERE / "BALANCE_STAGE6B_RUN.py").read_bytes()).hexdigest()
        cases = {}
        for c in manifest["cases"]:
            row, label = c["profile"], c["tactic"]
            cases[f"{row['profile_id']}-{label}-u{c['use_scale']}"] = row
            original = study.profiles()[row["floor"], row["job"]]
            for field in study.previous.FIXED+study.previous.REPLAY_FIELDS+("tactics",):
                assert row[field] == original[field]
            assert row["legacy_reincarnation_points"] == 0
            assert len(row["boss_override"]) <= 1
        counts = Counter()
        records = study.records(path / "runs.jsonl")
        for r in records:
            key = (r["case"], r["seed"])
            assert key not in all_keys
            all_keys.add(key)
            row = cases[r["case"]]
            counts[r["case"]] += 1
            assert not r["exception"]
            assert study.SEEDS[phase] <= r["seed"] < study.SEEDS[phase]+row["evaluation_trials"]
            assert r["evaluation_full_boss"] == formal[row["floor"]] | row["boss_override"]
            assert r["profile_stats"] == row["stats"]
            assert r["profile_attributes"] == row["attributes"]
            assert r["combat_start"] == row["combat_start"]
            assert r["display_power"] == row["power"]
            assert r["permanent_skill_codes"] == sorted(row["permanent_skill_codes"])
            assert all(n == 1 for n in Counter((a["side"], a["tick"]) for a in r["actions"]).values())
            for side in ("player", "boss"):
                initial, final = r["initial"][side], r["final"][side]
                taken = sum(e["amount"] for e in r["hp_events"] if e["target"] == side and e["kind"] != "heal")
                heal = sum(e["amount"] for e in r["hp_events"] if e["target"] == side and e["kind"] == "heal")
                assert initial["hp"]+heal-taken == final["hp"]
                assert taken == sum(r[side]["damage_taken"].values())
                assert heal == sum(r[side]["healing"].values())
                moves = [a for a in r["actions"] if a["side"] == side]
                assert len(moves) == r[side]["actions"]
                assert final["st"] == max(0, initial["st"]-5*sum(a["code"] not in ("skip", "status_skip") for a in moves))
            assert r["initial"]["player"]["hp"] == row["combat_start"]["max_hp"]
            assert r["initial"]["player"]["mp"] == row["combat_start"]["max_mp"]
        assert all(counts[k] == row["evaluation_trials"] for k, row in cases.items())
        result["phases"][phase] = {"conditions": len(cases), "runs": len(records), "exceptions": 0, "missing": 0,
            "loop_limits": sum(r["termination"] == "loop_limit" for r in records),
            "draws": sum(r["winner"] == "draw" for r in records),
            "source_fingerprint": manifest["source_sha256"]}
    assert result["phases"]["screen"]["source_fingerprint"] == result["phases"]["confirm"]["source_fingerprint"] == study.runner.fingerprint()
    selection = json.loads((root / "selection.json").read_text())
    screen = report.phase_summary(root / "screen")
    assert selection["selected"] == study.choose_candidates(screen["candidates"])["selected"]
    reviewed = json.loads((root / "selection_reviewed.json").read_text())
    assert set(reviewed["selected"]) == (set(selection["selected"])-{"f8-agility1800"}) | {"f8-agility3600"}
    confirmed = {c["profile"]["candidate"] for c in json.loads((root / "confirm/manifest.json").read_text())["cases"]}
    assert confirmed == set(reviewed["selected"]) | {study.candidate_id(f) for f in study.GRID}
    before = json.loads((root / "before.json").read_text())["files"]
    changes, missing = [], []
    for relative, digest in before.items():
        path = study.ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            changes.append(relative)
    assert not missing, missing
    assert set(changes) <= {"AGENTS.md"}, changes
    result.update(unique_case_seeds=len(all_keys), original_files=len(before), original_changed=changes,
                  original_deleted=missing, selected_candidates=reviewed["selected"],
                  branch=subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
                  all_profiles_and_hp_st_ledgers_match=True,
                  stage6a_and_backups_preserved=True, production_logic_unchanged=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=study.OUTPUT)
    parser.add_argument("--output", type=Path, default=study.OUTPUT / "validation.json")
    args = parser.parse_args()
    result = validate(args.source)
    study.previous.write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
