"""Promote a frozen, teacher-qualified carrier to robust scene interventions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .batch_audit import entry
from .budget import main_attempts
from .core import sha256
from .critical import PROJECT, dump
from .interventions import portal

PLAN = PROJECT / "configs/carrier_scene_v1.plan.json"


def candidate_decision(clearances, witnesses, controls):
    """Worst-repetition gate; controls include each nonempty condition/variant."""
    clearances = np.asarray(clearances, dtype=float)
    witnesses = np.asarray(witnesses, dtype=float)
    controls = np.asarray(controls, dtype=float)
    if clearances.shape != (3,) or witnesses.shape != (3,) or controls.shape != (2, 2, 3):
        raise ValueError("Expected three repetitions and two controls × two variants")
    if not all(np.isfinite(a).all() for a in (clearances, witnesses, controls)):
        raise ValueError("Geometry requires finite bounds")
    checks = dict(target_clearance=bool((clearances >= .03).all()),
                  contrast_arm_overlap=bool((witnesses <= -.01).all()),
                  control_clearance=bool((controls >= .03).all()))
    return dict(checks=checks, admitted=all(checks.values()),
                score=float(min(clearances.min() - .03, -witnesses.max() - .01)))


def select_candidate(proposals):
    accepted = [p for p in proposals if p["admitted"]]
    return min(accepted, key=lambda p: (-p["score"], p["frame"], p["gap_m"])) if accepted else None


def propose(output, plan_path=PLAN):
    from gear_sonic.research.scene_distillation.collision_clearance import (
        recorded_bounds, obstacle_separation,
    )
    from gear_sonic.research.scene_distillation.critical_pair_calibration import point_distance

    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    first = PROJECT / plan["preflight_run"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(plan_path, output / "registration.json")
    shutil.copy2(__file__, output / "proposal_code.py")
    shutil.copy2(PROJECT / "src/hindsight_motion/interventions.py", output / "portal_code.py")
    if main_attempts() != plan["main_budget"]["prior_attempts"]:
        raise ValueError("Budget changed since registration")
    qualification = next(r for r in json.loads((first / "carrier_qualification.json").read_text())
                         if r["pair_id"] == plan["eligible_pair"])
    if not qualification["acquisition_ready"] or qualification["source_group"] != plan["source_group"]:
        raise ValueError("Registered carrier is not qualified")
    if json.loads((first / "exit.json").read_text())["exit_code"] != 0:
        raise ValueError("Incomplete parent launch")
    isolation = json.loads((first / "metrics/isolation-audit.json").read_text())
    if isolation["maximum_foreign_obstacle_force_n"] > 1e-6:
        raise ValueError("Parent execution isolation failed")
    tasks = [t for t in json.loads((first / "batch.json").read_text())["tasks"]
             if t["pair_id"] == plan["eligible_pair"]]
    index = {(t["variant"], t["perturbation_id"]): t for t in tasks}
    variants = [plan["positive_variant"], plan["negative_variant"]]
    if set(index) != {(v, p) for v in variants for p in range(3)}:
        raise ValueError("Incomplete paired qualification population")
    manifest = {r["motion_key"]: r for r in json.loads((first / "manifest.json").read_text())}
    outcomes = {r["task_id"]: r for r in json.loads((first / "metrics/scene-outcomes.json").read_text())}
    names = json.loads((first / "metrics/episode-contract.json").read_text())["measured_body_names"]
    proxy_path = PROJECT / "runs/critical_preflight_20260915_v2/native_collision_proxies.json"
    proxies = json.loads(proxy_path.read_text())
    paths = [plan_path, first / "batch.json", first / "manifest.json", first / "exit.json",
             first / "carrier_qualification.json", first / "metrics/scene-outcomes.json",
             first / "metrics/isolation-audit.json", proxy_path,
             first / "teacher_and_runtime_contract.json", first / "metrics/episode-contract.json"]
    episodes, bounds, records = {}, {}, {}
    for variant in variants:
        for p in range(3):
            task = index[variant, p]
            row = manifest[task["motion_key"]]
            for kind in ("motion", "reference", "source"):
                path = Path(row[f"{kind}_path"])
                if sha256(path) != row[f"{kind}_sha256"]:
                    raise ValueError(f"Parent {kind} changed")
                paths.append(path)
            if not outcomes[task["task_id"]]["scene_passage_verified"]:
                raise ValueError("Parent outcome contradicts qualification")
            episode_path = first / "metrics" / f"episode-{task['motion_key']}.npz"
            paths.append(episode_path)
            episode = dict(np.load(episode_path))
            if len(episode["body_xyz"]) != 200 or not episode["before_first_native_failure"].all():
                raise ValueError("Incomplete parent trajectory")
            episodes[variant, p] = episode
            bounds[variant, p] = recorded_bounds(proxies, dict(
                body_names=names, body_xyz=episode["body_xyz"], body_wxyz=episode["body_wxyz"]))
            if p == 0:
                records[variant] = row
    for p in range(3):
        a, b = [entry(episodes[v, p]) for v in variants]
        if max(float(abs(a[k] - b[k]).max()) for k in a) > 1e-5:
            raise ValueError("Preflight entries are not matched")
        if index[variants[0], p]["initial_root_delta_xyz_m"] != index[variants[1], p]["initial_root_delta_xyz_m"]:
            raise ValueError("Preflight perturbations differ")
    # The arm edit is not allowed to hide a root or gait change.
    refs = [np.load(records[v]["reference_path"])["qpos"] for v in variants]
    np.testing.assert_array_equal(refs[0][:, :22], refs[1][:, :22])
    lock = json.loads((first / "teacher_and_runtime_contract.json").read_text())
    if sha256(lock["teacher_checkpoint"]) != lock["teacher_sha256"]:
        raise ValueError("Teacher changed")
    dump(output / "input_receipt.json", dict(
        created_unix_s=time.time(), teacher_sha256=lock["teacher_sha256"],
        files=[dict(path=str(p), sha256=sha256(p)) for p in sorted(set(paths))]))
    inner = [i for i, shape in enumerate(proxies)
             if shape["kind"] in ("Capsule", "Sphere", "Cube", "Cylinder")
             and any(part in shape["body"] for part in ("shoulder", "elbow", "wrist"))]
    if not inner:
        raise ValueError("No analytic arm primitives")
    positive, negative = variants
    points, radii = {}, {}
    for p in range(3):
        bb = bounds[negative, p][:, inner]
        edges = bb[:, :, [4, 2, 1]] - bb[:, :, :1]
        points[p] = bb.mean(axis=-2)
        radii[p] = np.linalg.norm(edges, axis=-1).min(axis=-1) / 2
    episode = episodes[positive, 0]
    root = episode["root_state_w"][:, :3] - episode["env_origin"]
    axis = root[-1] - root[0]
    axis[2] = 0
    axis /= np.linalg.norm(axis)

    def clearance(variant, p, obstacles):
        return min(float(obstacle_separation(bounds[variant, p], o).min()) for o in obstacles)

    proposals = []
    for frame in plan["geometry"]["frames"]:
        center = root[frame].copy()
        center[2] = 0
        for gap in plan["geometry"]["gaps_m"]:
            obstacles = portal(center, axis, gap)
            clearances = [clearance(positive, p, obstacles) for p in range(3)]
            witnesses, details = [], []
            for p in range(3):
                distances = np.stack([point_distance(points[p], o) - radii[p] for o in obstacles], axis=-1)
                where = np.unravel_index(distances.argmin(), distances.shape)
                witnesses.append(float(distances[where]))
                details.append(dict(perturbation=p, body=proxies[inner[where[1]]]["body"],
                                    time_s=float(where[0] * .02), obstacle=int(where[2])))
            controls = []
            for control in (portal(center, axis, gap + .60), portal(center, axis, gap, displacement=2.)):
                controls.append([[clearance(v, p, control) for p in range(3)] for v in variants])
            decision = candidate_decision(clearances, witnesses, controls)
            proposals.append(dict(frame=frame, gap_m=gap, center_xyz=center.tolist(), axis_xyz=axis.tolist(),
                                  obstacles=obstacles, positive_clearance_per_repeat_m=clearances,
                                  negative_inner_witness_per_repeat_m=witnesses, witness_locations=details,
                                  control_clearance_m=controls, **decision))
        print(json.dumps(dict(frame=frame, evaluated=len(proposals), admitted=sum(r["admitted"] for r in proposals))), flush=True)
    selected = select_candidate(proposals)
    result = dict(pair_id=plan.get("output_pair_id", "cmu107_arm_original"), source_group=plan["source_group"], family="arm_tuck",
                  positive_variant=positive, negative_variant=negative, records=records,
                  perturbations=[index[positive, p]["initial_root_delta_xyz_m"] for p in range(3)],
                  proposals=proposals, selected=selected, body_names=names,
                  measured_empty_scene_geometry=True, continuous_certificate=False,
                  physical_scene_criticality_verified=False)
    dump(output / "proposals.json", result)
    summary = dict(candidates=len(proposals), admitted=sum(r["admitted"] for r in proposals),
                   rejected_checks={key: sum(not r["checks"][key] for r in proposals) for key in proposals[0]["checks"]},
                   selected=None if selected is None else {k: selected[k] for k in (
                       "frame", "gap_m", "score", "positive_clearance_per_repeat_m", "negative_inner_witness_per_repeat_m")},
                   best_critical_slack_m=max(r["score"] for r in proposals),
                   completed_unix_s=time.time(), native_episodes=0, split="development")
    dump(output / "geometry_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["propose"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output.resolve())
