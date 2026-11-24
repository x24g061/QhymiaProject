"""全試行・詳細観測・因子格子・固定技能・過去成果物保持を独立照合する。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage6c_check_analysis", HERE / "analyze.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
study = analysis.study


def validate(root):
    original = json.loads((study.base.SOURCE / "official_catalog.json").read_text())
    formal = next(b for b in original["bosses"] if b["floor"] == 8)
    seen, result, fingerprints = set(), {}, []
    phases = [p for p in ("pilot", "screen", "refine", "confirm") if (root / p).exists()]
    for phase in phases:
        path = root / phase
        manifest = json.loads((path / "manifest.json").read_text())
        assert json.loads((path / "official_catalog.json").read_text()) == original
        assert json.loads((path / "official_catalog_unchanged.json").read_text())["unchanged"]
        metadata = json.loads((path / "study_metadata.json").read_text())
        assert metadata["fixed_skill_order"] == study.SKILLS
        assert metadata["fixed_skill_uses"] == 99
        source = path / "run_source.py" if phase == "pilot" else HERE / "run.py"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == metadata["script_sha256"]["run.py"]
        assert hashlib.sha256((HERE / "observe.py").read_bytes()).hexdigest() == metadata["script_sha256"]["observe.py"]
        cases, counts = {}, Counter()
        for c in manifest["cases"]:
            row, label = c["profile"], c["tactic"]
            key = f"{row['profile_id']}-{label}-u{c['use_scale']}"
            assert key not in cases
            cases[key] = row
            for field in study.base.previous.FIXED+study.base.previous.REPLAY_FIELDS+("tactics",):
                assert row[field] == study.profiles()[row["job"]][field]
            assert row["legacy_reincarnation_points"] == 0
            assert set(row["boss_override"]) == {"max_hp", "agility"}
            assert 50000 <= row["boss_override"]["max_hp"] <= 200000
            assert 180 <= row["boss_override"]["agility"] <= 3600
        runs = study.records(path / "runs.jsonl")
        for r in runs:
            key = (r["case"], r["seed"])
            assert key not in seen
            seen.add(key)
            row = cases[r["case"]]
            counts[r["case"]] += 1
            assert not r["exception"]
            assert study.SEEDS[phase] <= r["seed"] < study.SEEDS[phase]+row["evaluation_trials"]
            assert r["evaluation_full_boss"] == formal | row["boss_override"]
            assert r["profile_stats"] == row["stats"]
            assert r["profile_attributes"] == row["attributes"]
            assert r["combat_start"] == row["combat_start"]
            assert r["display_power"] == row["power"]
            assert r["permanent_skill_codes"] == sorted(row["permanent_skill_codes"])
            frames, contexts = r["skill_trace"]["frames"], r["skill_trace"]["hp_contexts"]
            assert len(frames) == len(r["actions"])
            assert len(contexts) == len(r["hp_events"])
            assert all(n == 1 for n in Counter((a["side"], a["tick"]) for a in r["actions"]).values())
            for side in ("player", "boss"):
                taken = sum(e["amount"] for e in r["hp_events"] if e["target"] == side and e["kind"] != "heal")
                heal = sum(e["amount"] for e in r["hp_events"] if e["target"] == side and e["kind"] == "heal")
                assert r["initial"][side]["hp"]+heal-taken == r["final"][side]["hp"]
                moves = [a for a in r["actions"] if a["side"] == side]
                assert len(moves) == r[side]["actions"]
                assert r["final"][side]["st"] == max(0, r["initial"][side]["st"]-5*sum(a["code"] not in ("skip", "status_skip") for a in moves))
                for code, cnt in r["titan_analysis"]["skill_attempts"][side].items():
                    assert cnt["attempts"] == sum(cnt.get(k, 0) for k in ("success", "activation_failure", "mp_shortage"))
                    assert cnt.get("success", 0) == r[side]["skills"].get(code, 0)
            for frame, action in zip(frames, r["actions"]):
                assert frame["side"] == action["side"]
                assert "finished" in frame
            assert r["titan_analysis"]["player_healing_shield_actions"] == r["player"]["skills"].get("healing_shield", 0)
            assert r["titan_analysis"]["boss_threatening_direct_actions"] <= r["titan_analysis"]["boss_direct_attack_actions"]
            assert r["initial"]["player"]["hp"] == row["combat_start"]["max_hp"]
            assert r["initial"]["player"]["mp"] == row["combat_start"]["max_mp"]
        assert all(counts[key] == row["evaluation_trials"] for key, row in cases.items())
        if phase != "pilot":
            fingerprints.append(manifest["source_sha256"])
        if phase == "screen":
            assert len(cases) == 280
            assert {(r["boss_override"]["max_hp"], r["boss_override"]["agility"]) for r in cases.values()} == {(h, a) for h in study.HPS for a in study.AGIS}
            details, table = analysis.interaction_rows(runs)
            n = next(iter(cases.values()))["evaluation_trials"]
            assert len(details) == 12*14*n and len(table) == 24
        result[phase] = {"conditions": len(cases), "runs": len(runs), "exceptions": 0, "missing": 0,
                         "draws": sum(r["winner"] == "draw" for r in runs),
                         "loop_limits": sum(r["termination"] == "loop_limit" for r in runs),
                         "battle_seconds": sum(r["elapsed_seconds"] for r in runs)}
    assert set(fingerprints) == {study.runner.fingerprint()}
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
    return {"phases": result, "unique_case_seeds": len(seen), "original_files": len(before),
            "original_changed": changed, "original_deleted": missing,
            "all_profiles_hp_st_skill_attempts_match": True, "formal_catalog_unchanged": True,
            "production_source_fingerprint_matches": True,
            "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE)
    parser.add_argument("--output", type=Path, default=HERE / "validation.json")
    args = parser.parse_args()
    value = validate(args.source)
    study.write_json(args.output, value)
    print(json.dumps(value, ensure_ascii=False))
