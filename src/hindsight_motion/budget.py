"""Count launched native main-study attempts, including representation descendants."""

import json
from pathlib import Path

from .critical import PROJECT

MAIN_PURPOSES = {
    "Additional source groups and ducking mechanism intervention panels",
    "Frozen-scene decoded-reference interventions",
}


def main_attempts(project=PROJECT):
    runs = Path(project) / "runs"
    old = runs / "critical_interventions_20260915_v1/tasks.json"
    count = 0
    if old.exists():
        count += sum(
            (Path(t["run_dir"]) / "launch.json").exists()
            for t in json.loads(old.read_text())
        )
    for path in runs.glob("*/batch.json"):
        run = path.parent
        if (
            not (run / "launch.json").exists()
            or not (run / "registration.json").exists()
        ):
            continue
        registration = json.loads((run / "registration.json").read_text())
        if (
            registration.get("budget_role") == "main"
            or registration.get("purpose") in MAIN_PURPOSES
        ):
            count += len(json.loads(path.read_text())["tasks"])
    return count
