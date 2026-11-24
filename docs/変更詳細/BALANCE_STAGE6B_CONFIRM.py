"""行動機会を確認したレビュー済み6候補だけを追加seedで測定。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage6b_confirm_study", HERE / "BALANCE_STAGE6B_RUN.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=study.OUTPUT)
    args = parser.parse_args()
    selection_file = args.output / "selection_reviewed.json"
    selected = json.loads(selection_file.read_text())["selected"]
    screen = study.records(args.output / "screen/runs.jsonl")
    for trials in (15, 10, 9, 8, 5):
        rows = study.scenarios("confirm", trials=trials, selected=selected)
        plan = study.estimate(rows, screen=screen)
        if plan["estimated_total_seconds"] <= study.LIMITS["confirm"]:
            break
    plan.update(trials_per_condition=trials, selection_file=selection_file.name,
                selection_sha256=hashlib.sha256(selection_file.read_bytes()).hexdigest(),
                confirm_driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    study.previous.write_json(args.output / "confirm_plan_final.json", plan)
    print(json.dumps(plan, ensure_ascii=False), flush=True)
    if plan["estimated_total_seconds"] > study.LIMITS["confirm"]:
        raise RuntimeError("確認5seedでも上限超過")
    study.execute(args.output / "confirm", rows, "confirm")


if __name__ == "__main__":
    main()
