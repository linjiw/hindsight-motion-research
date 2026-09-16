"""One registered fixed wide/tuck contrast; no search over edit parameters."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .batch_audit import entry
from .batch_scene import materialize
from .budget import main_attempts
from .core import sha256
from .critical import PROJECT, dump, edit_motion
from .mechanism import save_reference

PLAN = PROJECT / "configs/carrier_contrast_v1.plan.json"


def prepare(output):
    plan = json.loads(PLAN.read_text())
    parent = PROJECT / "runs/carrier_screen_20260915_v1"
    tasks = json.loads((parent / "batch.json").read_text())["tasks"]
    manifest = {r["motion_key"]: r for r in json.loads((parent / "manifest.json").read_text())}
    original = next(t for t in tasks if t["pair_id"] == "carrier00" and t["variant"] == "original" and t["perturbation_id"] == 0)
    source = manifest[original["motion_key"]]
    reference = PROJECT / plan["source_reference"]
    if sha256(reference) != source["reference_sha256"]:
        raise ValueError("Frozen carrier reference changed")
    ref = np.load(reference)
    q, names = ref["qpos"], list(ref["joint_names"])
    output = Path(output)
    folder = output.with_name(output.name + "_construction")
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "references").mkdir()
    (folder / "motions").mkdir()
    shutil.copy2(PLAN, folder / "registration.json")
    shutil.copy2(__file__, folder / "code_snapshot.py")
    shutil.copy2(PROJECT / "src/hindsight_motion/critical.py", folder / "edit_code_snapshot.py")
    created, records = [], []
    for variant in ("tuck", "wide"):
        pose, weight = edit_motion(q, variant)
        np.testing.assert_array_equal(pose[:, :22], q[:, :22])
        np.testing.assert_array_equal(pose[weight == 0], q[weight == 0])
        row = save_reference(folder, f"cmu107_{variant}", pose, names, source,
                             variant=variant, parent_reference_sha256=sha256(reference))
        if variant == "tuck":
            previous = next(r for r in manifest.values() if r["source_group"] == "CMU/107" and r["variant"] == "tuck")
            np.testing.assert_array_equal(pose, np.load(previous["reference_path"])["qpos"])
        for p in range(3):
            base = next(t for t in tasks if t["pair_id"] == "carrier00" and t["variant"] == "original" and t["perturbation_id"] == p)
            task = {k: deepcopy(v) for k, v in base.items() if k not in (
                "scene_path", "scene_sha256", "motion_key", "batch_index", "env_origin", "world_obstacle_filter_indices")}
            task.update(task_id=f"cmu107_arm_wide_removed_{variant}_p{p}", pair_id="cmu107_arm_wide",
                        family="arm_tuck", variant=variant,
                        terminal_requirement="Moving arrival; fixed wide/tuck contrast preflight only")
            created.append(task)
            records.append(row)
    if len(created) != plan["preflight_budget"]["maximum_episodes"]:
        raise ValueError("Preflight allocation differs from registration")
    materialize(created, records, output, dict(
        purpose="CMU/107 fixed wide/tuck contrast qualification", budget_role="preflight",
        budget_parent=str(PLAN), maximum_episodes=6, maximum_launches=1,
        no_automatic_retries=True, split="development", parent_preflight=str(parent)))
    dump(folder / "construction_receipt.json", dict(
        created_unix_s=time.time(), source_reference_sha256=sha256(reference),
        original_root_waist_and_legs_preserved=True, common_entry_and_exit_preserved=True,
        tuck_equals_previously_qualified_reference=True, planned_preflight_episodes=6))


def qualify(output):
    output = Path(output)
    if json.loads((output / "exit.json").read_text())["exit_code"] != 0:
        raise ValueError("Native launch did not complete")
    tasks = json.loads((output / "batch.json").read_text())["tasks"]
    outcomes = {r["task_id"]: r for r in json.loads((output / "metrics/scene-outcomes.json").read_text())}
    counts = {v: sum(outcomes[t["task_id"]]["scene_passage_verified"]
                    and outcomes[t["task_id"]]["valid_pre_action_rows"] == 200
                    for t in tasks if t["variant"] == v)
              for v in ("tuck", "wide")}
    errors = []
    for p in range(3):
        states = [entry(dict(np.load(output / "metrics" / f"episode-{t['motion_key']}.npz")))
                  for t in tasks if t["perturbation_id"] == p]
        errors.append(max(float(abs(states[0][k] - states[1][k]).max()) for k in states[0]))
    result = dict(pair_id="cmu107_arm_wide", source_group="CMU/107", successes=counts,
                  entry_max_error=max(errors), acquisition_ready=all(n == 3 for n in counts.values()) and max(errors) <= 1e-5)
    dump(output / "carrier_qualification.json", [result])
    print(json.dumps(result, indent=2))


def propose(output):
    from .carrier_scene import propose as search

    preflight = PROJECT / "runs/carrier_contrast_preflight_20260916_v1"
    qualification = json.loads((preflight / "carrier_qualification.json").read_text())[0]
    if not qualification["acquisition_ready"]:
        raise ValueError("Fixed contrast failed qualification; no scene search")
    plan = json.loads((PROJECT / "configs/carrier_scene_v1.plan.json").read_text())
    plan.update(registered_unix_s=time.time(), preflight_run=str(preflight.relative_to(PROJECT)),
                eligible_pair="cmu107_arm_wide", output_pair_id="cmu107_arm_wide", negative_variant="wide",
                parent_registration=str(PLAN),
                question="Does the frozen fixed-wide/tuck contrast support robust scenes?",
                hypothesis="Tuck passes critical passage while the fixed wide edit makes arm contact; both pass all controls.",
                preflight_reuse="The fixed wide and tuck references must each pass all three new paired preflights.",
                source_registration_sha256=sha256(PLAN))
    scene_plan = preflight / "scene_registration.json"
    with scene_plan.open("x") as f:
        json.dump(plan, f, indent=2)
    search(output, scene_plan)


def prepare_main(output):
    from .interventions import portal

    proposals = PROJECT / "runs/carrier_contrast_proposals_20260916_v1"
    proposal = json.loads((proposals / "proposals.json").read_text())
    selected = proposal["selected"]
    if selected is None:
        raise ValueError("No admitted geometry; no native scene launch")
    plan = json.loads(PLAN.read_text())
    if main_attempts() != plan["main_budget"]["prior_attempts"]:
        raise ValueError("Budget changed since registration")
    for item in json.loads((proposals / "input_receipt.json").read_text())["files"]:
        if sha256(item["path"]) != item["sha256"]:
            raise ValueError("Frozen scene-search input changed")
    if not json.loads((PROJECT / "runs/batch_equivalence_20260915_v1/equivalence-audit.json").read_text())["passed"]:
        raise ValueError("Batch instrument not qualified")
    tasks, records = [], []
    root = np.load(proposal["records"]["tuck"]["reference_path"])["qpos"][:, :3]
    axis = np.asarray(selected["axis_xyz"])
    for perturbation, delta in enumerate(proposal["perturbations"]):
        for condition in ("critical", "relaxed", "removed", "displaced"):
            obstacles = [] if condition == "removed" else portal(
                selected["center_xyz"], axis,
                selected["gap_m"] + (.60 if condition == "relaxed" else 0),
                displacement=2. if condition == "displaced" else 0.)
            for variant, row in proposal["records"].items():
                tasks.append(dict(
                    schema="hindsight_critical_traversal_task_v1",
                    task_id=f"cmu107_arm_wide_{condition}_{variant}_p{perturbation}",
                    pair_id="cmu107_arm_wide", family="arm_tuck", variant=variant,
                    condition=condition, perturbation_id=perturbation,
                    initial_root_delta_xyz_m=delta, split="development", source_group="CMU/107",
                    obstacles=obstacles, body_names=proposal["body_names"],
                    start_xyz=root[0].tolist(), goal_xyz=root[-1].tolist(),
                    portal_center_xyz=selected["center_xyz"], passage_axis_xyz=axis.tolist(),
                    goal_tolerance_m=.25, exit_progress_m=.20,
                    terminal_requirement="Moving arrival through portal; no stop/hold claim",
                    maximum_undesired_normal_force_n=1., control_deadline_steps=200,
                    construction="Frozen robust geometry over three measured empty-scene repetitions",
                    scene_criticality_verified=False))
                records.append(row)
    if len(tasks) != 24 or main_attempts() + len(tasks) > 480:
        raise ValueError("Main attempt budget exceeded")
    materialize(tasks, records, output, dict(
        purpose="CMU/107 fixed wide/tuck critical-scene acquisition", budget_role="main",
        budget_parent=str(PLAN), maximum_episodes=24, maximum_launches=1,
        main_study_previous_episodes=312, main_study_global_ceiling=480,
        proposals=str(proposals), proposals_sha256=sha256(proposals / "proposals.json"),
        no_automatic_retries=True, no_replacement=True, split="development"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "qualify", "propose", "prepare_main"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output.resolve())
