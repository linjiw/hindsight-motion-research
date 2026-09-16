"""Teacher coverage screen with unedited carrier controls, independent of filenames."""

import argparse
import csv
import json
from pathlib import Path
import shutil

import numpy as np

from .batch_audit import entry
from .batch_scene import materialize
from .core import load_clip, sha256
from .critical import PROJECT, dump, edit_motion, launch
from .mechanism import PLAN, construction_folder, save_reference
from .source_acquisition import describe


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        KIMODO_G1_JOINT_NAMES,
    )

    output = Path(output)
    folder = construction_folder(output)
    shutil.copy2(__file__, folder / "carrier_screen_code.py")
    seen = set()
    for path in (PROJECT / "runs").glob("*/manifest.json"):
        if (path.parent / "launch.json").exists():
            seen.update(
                r["source_group"]
                for r in json.loads(path.read_text())
                if "source_group" in r
            )
    inventory = list(
        csv.DictReader((PROJECT / "runs/pilot_20260915_v1/inventory.csv").open())
    )
    candidates, rejects, clips = [], [], {}
    for r in inventory:
        if r["source_group"] in seen:
            continue
        clip = load_clip(r["source_path"], 4, 5)
        q = clip["qpos"]
        if len(q) != 200:
            rejects.append(
                dict(
                    motion_id=r["motion_id"],
                    source_group=r["source_group"],
                    reason="Shorter than 4 seconds",
                )
            )
            continue
        feature, screen = describe(q)
        if screen["eligible"]:
            candidates.append(dict(**r, feature=feature.tolist(), screen=screen))
            clips[r["motion_id"]] = clip
        else:
            rejects.append(
                dict(motion_id=r["motion_id"], source_group=r["source_group"], **screen)
            )
    selected = []
    if candidates:
        scale = np.maximum(np.array([r["feature"] for r in candidates]).std(0), 0.05)
        anchors = [
            describe(
                np.load(
                    PROJECT
                    / f"runs/expansion_preflight_20260915_v1/references/expand_{i:02d}_original.npz"
                )["qpos"]
            )[0]
            for i in (0, 2)
        ]
        for r in candidates:
            r["distance"] = float(
                np.min(
                    np.linalg.norm((np.asarray(r["feature"]) - anchors) / scale, axis=1)
                )
            )
        groups = set()
        for r in sorted(candidates, key=lambda r: (r["distance"], r["motion_id"])):
            if r["source_group"] in groups:
                continue
            selected.append(r)
            groups.add(r["source_group"])
            if len(selected) == 8:
                break
    dump(
        folder / "selection.json",
        dict(
            excluded_groups=sorted(seen),
            candidates=candidates,
            rejected=rejects,
            selected=selected,
            filename_filter=False,
            original_carrier_control=True,
            no_retiming=True,
        ),
    )
    if not selected:
        print("No eligible new carriers; no native launch.")
        return
    names = list(KIMODO_G1_JOINT_NAMES)
    body_names = json.loads(
        (
            PROJECT
            / "runs/expansion_preflight_20260915_v1/metrics/episode-contract.json"
        ).read_text()
    )["measured_body_names"]
    tasks, records = [], []
    for i, source in enumerate(selected):
        assert sha256(source["source_path"]) == source["sha256"]
        clip = clips[source["motion_id"]]
        q = clip["qpos"].copy()
        q[:, :2] -= q[0, :2].copy()
        axis = q[-1, :3] - q[0, :3]
        axis[2] = 0
        axis /= np.linalg.norm(axis)
        normal = np.array([-axis[1], axis[0], 0.0])
        for variant in ("original", "tuck"):
            pose = edit_motion(q, variant)[0]
            source_row = dict(
                source_group=source["source_group"],
                source_id=source["motion_id"],
                source_path=source["source_path"],
                source_sha256=source["sha256"],
                source_start_frame=clip["start_frame"],
                source_end_frame_exclusive=clip["end_frame_exclusive"],
                historical_pilot_split=source["split"],
                variant=variant,
                carrier_id=i,
            )
            row = save_reference(
                folder, f"carrier{i:02d}_{variant}", pose, names, source_row
            )
            for p, offset in enumerate((0.0, -0.015, 0.015)):
                task = dict(
                    schema="hindsight_critical_traversal_task_v1",
                    task_id=f"carrier{i:02d}_removed_{variant}_p{p}",
                    pair_id=f"carrier{i:02d}",
                    family="carrier_screen",
                    variant=variant,
                    condition="removed",
                    perturbation_id=p,
                    initial_root_delta_xyz_m=(offset * normal).tolist(),
                    source_group=source["source_group"],
                    split="development",
                    obstacles=[],
                    body_names=body_names,
                    start_xyz=q[0, :3].tolist(),
                    goal_xyz=q[-1, :3].tolist(),
                    portal_center_xyz=q[100, :3].tolist(),
                    passage_axis_xyz=axis.tolist(),
                    goal_tolerance_m=0.25,
                    exit_progress_m=0.20,
                    maximum_undesired_normal_force_n=1.0,
                    control_deadline_steps=200,
                    terminal_requirement="Moving arrival; unedited carrier qualification only",
                    preflight_only=True,
                    scene_criticality_verified=False,
                )
                tasks.append(task)
                records.append(row)
    materialize(
        tasks,
        records,
        output,
        dict(
            purpose="Unedited and arm-tuck teacher coverage on new source groups",
            budget_role="preflight",
            budget_parent=str(PLAN),
            counts_as_preflight=True,
            new_preflight_launch=2,
            maximum_episodes=48,
            planned_episodes=len(tasks),
            split="development",
        ),
    )


def qualify(output):
    output = Path(output)
    tasks = json.loads((output / "batch.json").read_text())["tasks"]
    outcomes = {
        r["task_id"]: r
        for r in json.loads((output / "metrics/scene-outcomes.json").read_text())
    }
    rows = []
    for pair in dict.fromkeys(t["pair_id"] for t in tasks):
        group = [t for t in tasks if t["pair_id"] == pair]
        errors = []
        for p in range(3):
            states = [
                entry(
                    dict(np.load(output / "metrics" / f"episode-{t['motion_key']}.npz"))
                )
                for t in group
                if t["perturbation_id"] == p
            ]
            errors.append(
                max(
                    float(abs(x[k] - states[0][k]).max())
                    for x in states
                    for k in states[0]
                )
            )
        counts = {
            v: sum(
                outcomes[t["task_id"]]["scene_passage_verified"]
                for t in group
                if t["variant"] == v
            )
            for v in ("original", "tuck")
        }
        rows.append(
            dict(
                pair_id=pair,
                source_group=group[0]["source_group"],
                successes=counts,
                entry_max_error=max(errors),
                original_supported=counts["original"] == 3,
                acquisition_ready=all(x == 3 for x in counts.values())
                and max(errors) <= 1e-5,
            )
        )
    dump(output / "carrier_qualification.json", rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "launch", "qualify"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output.resolve())
