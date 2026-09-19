"""Audit immutable complete-task runs; publish aggregate development evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .complete_task import paired_entry
from .core import sha256
from .critical import PROJECT, dump


def audit_case(case):
    run = Path(case["run_dir"])
    if not (run / "launch.json").exists():
        reason = json.loads((run / "not-run.json").read_text()) if (run / "not-run.json").exists() else {}
        return dict(case_id=case["case_id"], source_clip=case["source_clip"], method=case["method"],
                    condition=case["condition"], status="unrun", reason=reason)
    if not (run / "exit.json").exists():
        raise ValueError("Native process is still running or has no exit receipt")
    exit_record = json.loads((run / "exit.json").read_text())
    if exit_record["exit_code"] != 0:
        return dict(case_id=case["case_id"], source_clip=case["source_clip"], method=case["method"],
                    condition=case["condition"], status="infrastructure_failure", exit=exit_record)
    task = json.loads((run / "task.json").read_text())
    score = json.loads((run / "task/task-result.json").read_text())
    with np.load(run / "task/trace.npz") as d:
        trace = {k: d[k] for k in d.files}
    with np.load(run / "task/duck-features.npz") as d:
        features = {k: d[k] for k in d.files}
    with np.load(run / "task/teacher-episode.npz") as d:
        if d["query_mask"].any():
            raise ValueError("Development run exposes positive training labels")
    n = len(trace["root_xyz"])
    if n != score["control_steps"] or len(trace["contact_force_w"]) != 4*n:
        raise ValueError("Missing aligned control/physics records")
    for array in [trace["root_xyz"], trace["speed"], trace["contact_force_w"], *features.values()]:
        if not np.isfinite(array).all():
            raise ValueError("Nonfinite physical evidence")
    names = trace["body_names"].tolist()
    nonfeet = [i for i, name in enumerate(names) if name not in
               ("left_ankle_roll_link", "right_ankle_roll_link")]
    force = np.linalg.norm(trace["contact_force_w"], axis=-1)
    obstacle_peak = float(force[:, :, 1:].max(initial=0))
    floor_peak = float(force[:, nonfeet, 0].max(initial=0))
    duck = task["duck_contract"]
    goal = np.linalg.norm(trace["root_xyz"] - task["goal_xyz"], axis=-1)
    upright = ((trace["root_xyz"][:, 2] >= duck["recovery_pelvis_height_m"][0])
               & (trace["root_xyz"][:, 2] <= duck["recovery_pelvis_height_m"][1])
               & (features["torso_tilt"] <= duck["max_torso_tilt_rad"]))
    beyond = features["lower"][:, 0] >= duck["gate"]["full_dimensions_xyz"][0]/2 + duck["clearance_margin_m"]
    terminal = (goal <= task["goal_tolerance_m"]) & (trace["speed"] <= task["terminal_speed_mps"]) & upright & beyond
    # Independent success-tail check; runtime must complete after 15 recovery
    # frames and 50 further hold frames, with contacts checked over the whole run.
    if score["duck_recover_stop_success"]:
        required = task["hold_ticks"] + duck["recovery_ticks"]
        if (n < required or not terminal[-task["hold_ticks"]:].all()
                or not (upright[-required:] & beyond[-required:]).all()
                or max(obstacle_peak, floor_peak) > 1 or score["fell"]
                or score["stop_reason"] != "goal_hold"):
            raise ValueError("Success does not have the measured ordered terminal/contact evidence")
    row = dict(case_id=case["case_id"], source_clip=case["source_clip"], method=case["method"],
               condition=case["condition"], status="completed", success=score["duck_recover_stop_success"],
               stop_reason=score["stop_reason"], control_steps=n, physics_samples=4*n,
               elapsed_s=exit_record["elapsed_s"], completion_time_s=n*.02,
               passage=score["passage_success"], recovered=score["recovered"],
               ordered_hold_ticks=score["ordered_hold_ticks"], fell=score["fell"],
               final_goal_distance_m=float(goal[-1]), final_speed_mps=float(trace["speed"][-1]),
               max_obstacle_force_n=obstacle_peak, max_nonfoot_floor_force_n=floor_peak,
               final_torso_tilt_rad=float(features["torso_tilt"][-1]),
               final_pelvis_height_m=float(trace["root_xyz"][-1, 2]),
               goal025_last50_observed=bool(n >= 50 and (terminal[-50:] & (goal[-50:] <= .25)).all()),
               entry_tick=score["entry_tick"], clear_tick=score["clear_tick"],
               recovery_tick=score["recovery_tick"], task_profile=task["success_profile"])
    contacts = []
    for body, name in enumerate(names):
        for obstacle in range(1, force.shape[2]):
            ticks = np.flatnonzero(force[:, body, obstacle] > 1)
            if len(ticks):
                contacts.append(dict(body=name, obstacle=obstacle-1, first_s=(int(ticks[0])+1)*.005,
                                     peak_n=float(force[:, body, obstacle].max())))
    row["obstacle_contacts"] = contacts
    return row


def analyze(output, public_path=None):
    output = Path(output).resolve()
    if (output / "aggregate.json").exists():
        raise FileExistsError("Do not overwrite the completed audit")
    plan = json.loads((output / "plan.json").read_text())
    rows = [audit_case(c) for c in plan["cases"]]
    pairs = []
    for clip in plan["registration"]["source_clips"]:
        for condition in ("clear", "beam"):
            group = [c for c in plan["cases"] if c["source_clip"] == clip and c["condition"] == condition]
            scores = [next(r for r in rows if r["case_id"] == c["case_id"]) for c in group]
            complete = all(r["status"] == "completed" for r in scores)
            pair = dict(source_clip=clip, condition=condition, compared=complete)
            if complete:
                pair.update(entry=paired_entry(*[c["run_dir"] for c in group]),
                            continuous_success=scores[0]["success"], linear29_success=scores[1]["success"],
                            success_difference_linear_minus_continuous=int(scores[1]["success"])-int(scores[0]["success"]))
            pairs.append(pair)
    audit = json.loads((output / "codec-audit.json").read_text())
    scale_path = PROJECT / "runs/clearance_tokens_20260915_v1/residual_model.npz"
    scale = np.load(scale_path)["angle_scale"]
    for a in audit:
        with np.load(output / "references" / f"{a['source_clip']}_continuous/reference.npz") as d:
            q, names = d["qpos"], d["joint_names"]
            clipped = (abs(np.rint(q[2::5, 7:]/scale*2047)) > 2047).sum(0)
            a["clipped_by_joint"] = [dict(joint=str(names[i]), knots=int(clipped[i]), scale_rad=float(scale[i]))
                                      for i in range(29) if clipped[i]]
            a["continuous_total_bits"] = int(len(q)*36*32)
            a["linear29_total_bits"] = a["joint_payload_bits"] + a["common_root_bits"] + a["reset_anchor_bits"]
            a["linear29_total_bits_per_s"] = a["linear29_total_bits"]/(len(q)*.02)
    files = [output / "registration.json", output / "plan.json", output / "codec-audit.json"]
    for c in plan["cases"]:
        p = Path(c["run_dir"])
        files += [f for f in [p / "launch.json", p / "exit.json", p / "task/task-result.json",
                             p / "task/initial-state.npz", p / "task/trace.npz", p / "task/duck-features.npz"] if f.exists()]
    summary = dict(schema="hindsight_complete_task_results_v1", date="2026-09-18",
                   scope=plan["registration"]["scope"], task_profile=plan["registration"]["task_profile"],
                   goal_tolerance_m=.5, reference_assisted=True, autonomous=False,
                   independent_ancestry_established=False, source_clips=2,
                   scheduled_cases=8, native_attempts=sum(r["status"] != "unrun" for r in rows),
                   completed_episodes=sum(r["status"] == "completed" for r in rows),
                   infrastructure_failures=sum(r["status"] == "infrastructure_failure" for r in rows),
                   unrun=sum(r["status"] == "unrun" for r in rows),
                   control_steps=sum(r.get("control_steps", 0) for r in rows),
                   physics_samples=sum(r.get("physics_samples", 0) for r in rows),
                   historical_main_attempts_consumed=0, training_steps=0,
                   rows=rows, pairs=pairs, codec_audit=audit,
                   provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=sha256(p)) for p in files],
                   analysis_source_sha256=sha256(__file__))
    dump(output / "aggregate.json", summary)
    if public_path is not None:
        public_path = Path(public_path)
        if public_path.exists():
            raise FileExistsError("Public summary already exists")
        dump(public_path, summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "codec_audit", "provenance")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--public-path", type=Path)
    args = parser.parse_args()
    analyze(args.output, args.public_path)
