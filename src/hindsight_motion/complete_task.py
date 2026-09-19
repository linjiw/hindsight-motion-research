"""Bounded continuous/Linear29 complete-task development pilot, matrix row 1."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import numpy as np

from .clearance_tokens import interpolate_knots, quantize12
from .core import sha256
from .critical import PROJECT, RUNTIME, dump
from .resource_queue import run as resource_run


def binding(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def checked(item):
    path = Path(item["path"])
    if sha256(path) != item["sha256"]:
        raise ValueError(f"Changed bound input: {path}")
    return path


def decode_linear29(qpos, scale, anchor_frames=2):
    q = np.asarray(qpos, dtype=float)
    scale = np.asarray(scale)
    if (q.ndim != 2 or q.shape[1] != 36 or len(q) < 5 or len(q) % 5
            or scale.shape != (29,) or not np.isfinite(q).all()
            or not np.isfinite(scale).all() or (scale <= 0).any() or anchor_frames != 2):
        raise ValueError("Expected finite 50Hz whole-body frames and frozen 29D scale")
    symbols, knots, clipped = quantize12(q[2::5, 7:], scale)
    decoded = q.copy()
    decoded[:, 7:] = interpolate_knots(knots, len(q))
    decoded[:anchor_frames, 7:] = q[:anchor_frames, 7:]
    return decoded, dict(
        clipped_symbols=clipped, frames=len(q), knot_count=len(knots),
        joint_payload_bits=int(symbols.size * 12),
        common_root_bits=int(len(q) * 7 * 32),
        reset_anchor_bits=anchor_frames * 29 * 32,
        joint_rmse_rad=float(np.sqrt(np.mean((decoded[:, 7:] - q[:, 7:]) ** 2))),
        joint_max_error_rad=float(np.max(abs(decoded[:, 7:] - q[:, 7:]))),
        common_reset_anchor_frames=anchor_frames, original_entry_bridge=False,
    )


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        qpos_to_sonic_motion_entry, sonic_motion_entry_to_qpos, save_sonic_motion_file,
        KIMODO_G1_JOINT_NAMES,
    )
    from gear_sonic.research.scene_distillation.tasks import validate_task
    plan_path = PROJECT / "configs/complete_task_v1.plan.json"
    plan = json.loads(plan_path.read_text())
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(plan_path, output / "registration.json")
    source_panel, beam_panel = Path(plan["source_panel"]), Path(plan["beam_panel"])
    source_plan = json.loads((source_panel / "plan.json").read_text())
    scale_path = PROJECT / "runs/clearance_tokens_20260915_v1/residual_model.npz"
    scale = np.load(scale_path)["angle_scale"]
    teacher = source_plan["teacher"]
    checked(teacher)
    template = json.loads(checked(source_plan["command_template"]).read_text())
    all_bindings = [binding(plan_path), binding(source_panel / "plan.json"),
                    binding(scale_path), teacher, source_plan["command_template"],
                    binding(Path(teacher["path"]).with_name("config.yaml"))]
    cases, audits = [], []
    for clip in plan["source_clips"]:
        source = next(s for s in source_plan["sources"] if s["source_motion_id"] == clip)
        reference_path = checked(source["variants"]["local_duck"]["reference"])
        all_bindings.append(binding(reference_path))
        with np.load(reference_path) as f:
            original = {k: f[k] for k in f.files}
        q = original["qpos"]
        if original["joint_names"].tolist() != list(KIMODO_G1_JOINT_NAMES):
            raise ValueError("Reference and frozen scale joint orders differ")
        linear, audit = decode_linear29(q, scale)
        audits.append(dict(source_clip=clip, **audit))
        for method, pose in (("continuous", q), ("linear29", linear)):
            method_dir = output / "references" / f"{clip}_{method}"
            method_dir.mkdir(parents=True)
            ref = method_dir / "reference.npz"
            np.savez_compressed(ref, **dict(original, qpos=pose))
            motion_id = f"complete_{clip}_{method}"
            motion_path = method_dir / "motions" / f"hindsight_{motion_id}.pkl"
            motion = qpos_to_sonic_motion_entry(pose, source_fps=50,
                                                canonicalize_horizontal_origin=False)
            if np.max(abs(sonic_motion_entry_to_qpos(motion) - pose)) > 1e-6:
                raise ValueError("Native serialization roundtrip failed")
            save_sonic_motion_file(motion_path, motion_key=f"hindsight_{motion_id}", motion_entry=motion)
            for condition in plan["conditions"]:
                parent = (source_panel / "tasks" / f"{clip}-clear-early-teacher.json"
                          if condition == "clear" else
                          beam_panel / f"{clip}-swept_margin_005mm-teacher.json")
                task = json.loads(parent.read_text())
                all_bindings.append(binding(parent))
                for key in ["source_scene"]:
                    all_bindings.append(task[key])
                all_bindings += [binding(task["scene_usd_path"]), task["duck_contract"]["collision_bounds"]]
                name = f"{clip}_{condition}_{method}"
                run = output / "episodes" / name
                run.mkdir(parents=True)
                task.update(task_id=name, motion_id=motion_id, split="development",
                            source_group="shared_acquisition_unresolved_ancestry",
                            reference=binding(ref), native_motion=binding(motion_path),
                            research_protocol=plan["schema"], research_method=method,
                            positive_student_training_authorized=False)
                validate_task(task)
                task_path = run / "task.json"
                dump(task_path, task)
                config = dict(teacher_checkpoint=teacher["path"], teacher_sha256=teacher["sha256"],
                              task_path=str(task_path), output=str(run / "task"),
                              max_steps=plan["maximum_control_steps_per_attempt"], teacher_mode=True,
                              student_checkpoint=None, actor_profile="privileged_full_reference_diagnostic")
                dump(run / "config.json", config)
                replacements = {
                    "++seed": str(plan["seed"]),
                    "++callbacks.im_eval._target_": "hindsight_motion.complete_task_native.CompleteReferenceCallback",
                    "++callbacks.im_eval.stage_config": str(run / "config.json"),
                    "++eval_output_dir": str(run / "unused"), "++eval_base_dir": str(run / "hydra"),
                    "++manager_env.commands.motion.motion_lib_cfg.motion_file": str(motion_path.parent),
                    "++manager_env.config.scene_usd_path": task["scene_usd_path"],
                    "++manager_env.config.navigation_task_path": str(task_path),
                }
                command = [a.split("=", 1)[0] + "=" + replacements[a.split("=", 1)[0]]
                           if a.split("=", 1)[0] in replacements else a for a in template]
                dump(run / "command.json", command)
                all_bindings += [binding(task_path), binding(run / "config.json"),
                                 binding(run / "command.json"), binding(ref), binding(motion_path)]
                cases.append(dict(case_id=name, source_clip=clip, method=method,
                                  condition=condition, run_dir=str(run)))
    # Pin the actual dirty runtime contents; never merge or edit the sibling repo.
    sources = list((RUNTIME / "gear_sonic/research/scene_distillation").glob("*.py"))
    sources += list((RUNTIME / "gear_sonic/research/hindsight_training").glob("*.py"))
    sources += [RUNTIME / "gear_sonic/dataset_generation/kimodo_motion_adapter.py",
                RUNTIME / "gear_sonic/eval_agent_trl.py", Path(__file__).resolve(),
                PROJECT / "src/hindsight_motion/complete_task_native.py",
                PROJECT / "src/hindsight_motion/resource_queue.py"]
    for i, source in enumerate(sources):
        destination = output / "code_snapshot" / f"{i:03d}_{source.name}"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source, destination)
        all_bindings.append(binding(source))
    proxy = json.loads(Path(task["duck_contract"]["collision_bounds"]["path"]).read_text())
    all_bindings.append(dict(path=proxy["asset"], sha256=proxy["asset_sha256"]))
    cases.sort(key=lambda c: (plan["conditions"].index(c["condition"]),
                             plan["source_clips"].index(c["source_clip"]),
                             plan["methods"].index(c["method"])))
    dump(output / "plan.json", dict(registration=plan, created_unix_s=time.time(), cases=cases,
                                    bindings=list({b["path"]: b for b in all_bindings}.values())))
    dump(output / "codec-audit.json", audits)
    print(json.dumps(dict(prepared=str(output), cases=len(cases), codec_audit=audits)))


def paired_entry(first, second):
    errors = {}
    for filename in ("initial-state.npz", "dynamics-entry.npz"):
        with np.load(Path(first) / "task" / filename) as a, np.load(Path(second) / "task" / filename) as b:
            if set(a.files) != set(b.files):
                raise ValueError("Entry fields differ")
            for key in a.files:
                if a[key].shape != b[key].shape or not np.isfinite(a[key]).all() or not np.isfinite(b[key]).all():
                    raise ValueError("Invalid matched entry")
                errors[f"{filename}:{key}"] = float(np.max(abs(a[key] - b[key])))
    rngs = [json.loads((Path(p) / "task/depth-source.json").read_text())[
        "first_physics_step_torch_rng_sha256"] for p in (first, second)]
    return dict(max_errors=errors, torch_rng_matched=rngs[0] == rngs[1],
                matched=max(errors.values()) <= 1e-5 and rngs[0] == rngs[1])


def launch_case(run):
    run = Path(run)
    output = run.parent.parent
    plan = json.loads((output / "plan.json").read_text())
    if (run / "launch.json").exists():
        raise FileExistsError("Already attempted; no retries")
    launched = sum((Path(c["run_dir"]) / "launch.json").exists() for c in plan["cases"])
    if launched >= plan["registration"]["maximum_native_attempts"]:
        raise ValueError("New study budget exhausted")
    for item in plan["bindings"]:
        checked(item)
    command = json.loads((run / "command.json").read_text())
    start = time.monotonic()
    timeout = plan["registration"]["maximum_wall_seconds_per_attempt"]
    with (run / "evaluation.log").open("x") as log:
        dump(run / "launch.json", dict(planned_episodes=1, start_unix_s=time.time(),
                                        command=command, timeout_s=timeout))
        process = subprocess.Popen(command, cwd=RUNTIME, start_new_session=True,
            env=dict(os.environ, PYTHONPATH=f"{PROJECT / 'src'}:{RUNTIME}",
                     OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", WANDB_MODE="disabled"),
            stdout=log, stderr=subprocess.STDOUT)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
        dump(run / "exit.json", dict(exit_code=code, timed_out=timed_out,
                                      elapsed_s=time.monotonic() - start))
    print(json.dumps(dict(case=run.name, exit_code=code, elapsed_s=time.monotonic()-start)), flush=True)


def run(output):
    output = Path(output).resolve()
    plan = json.loads((output / "plan.json").read_text())
    # One invocation per packet, including deferred/failed attempts. A separate
    # registration is required to replace or extend a stopped pilot.
    with (output / "execution-start.json").open("x") as f:
        json.dump(dict(start_unix_s=time.time(), plan_sha256=sha256(output / "plan.json")), f)
    for case in plan["cases"]:
        path = Path(case["run_dir"])
        if case["condition"] == "beam":
            clear = [c for c in plan["cases"] if c["source_clip"] == case["source_clip"]
                     and c["condition"] == "clear"]
            a, b = [Path(c["run_dir"]) for c in clear]
            success = json.loads((a / "task/task-result.json").read_text())["duck_recover_stop_success"]
            audit = paired_entry(a, b)
            if not success or not audit["matched"]:
                dump(path / "not-run.json", dict(reason="continuous_clear_or_matched_entry_gate_failed",
                                                 continuous_clear_success=success, entry=audit))
                continue
        resource_run([path], timeout_s=plan["registration"]["resource_wait_seconds_per_attempt"],
                     launcher=launch_case)
        if not (path / "launch.json").exists():
            break
        result = json.loads((path / "task/task-result.json").read_text())
        print(json.dumps(dict(case=case["case_id"], success=result["duck_recover_stop_success"],
                               reason=result["stop_reason"], hold=result["ordered_hold_ticks"])), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output)
