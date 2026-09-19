"""Registered actual-prefix continuous/Linear29 continuation study."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .complete_task import binding, checked, launch_case, paired_entry
from .core import sha256
from .critical import PROJECT, RUNTIME, dump
from .resource_queue import run as resource_run


def select_states(score, hold_ticks=50):
    if not score["duck_recover_stop_success"]:
        raise ValueError("Parent complete-task support is required")
    states = dict(pre_entry=max(1, score["entry_tick"] - 15),
                  entry=score["entry_tick"] + 1, exit=score["clear_tick"] + 1,
                  pre_hold=score["control_steps"] - hold_ticks - 10)
    values = list(states.values())
    if values != sorted(set(values)) or values[-1] >= score["control_steps"]:
        raise ValueError("Registered phase proxies are not ordered distinct incoming states")
    return states


def array_errors(a, b, keys, count=None):
    errors = {}
    for key in keys:
        x, y = a[key], b[key]
        if count is not None:
            if len(x) < count or len(y) < count:
                raise ValueError("Incomplete executed prefix")
            x, y = x[:count], y[:count]
        if x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError(f"Unmatched or nonfinite field: {key}")
        errors[key] = float(np.max(abs(x.astype(float) - y.astype(float)), initial=0))
    return errors


def prefix_audit(first, second, k):
    errors = {}
    specifications = {
        "teacher-episode.npz": (["teacher_actions", "proprio", "future_reference"], k),
        "pre-action-poses.npz": (["root_xyz", "root_wxyz", "joint_pos", "joint_vel", "body_xyz", "body_wxyz"], k),
        "trace.npz": (["root_xyz", "speed"], k),
    }
    for filename, (keys, count) in specifications.items():
        with np.load(Path(first) / "task" / filename) as a, np.load(Path(second) / "task" / filename) as b:
            errors.update({filename + ":" + key: value
                           for key, value in array_errors(a, b, keys, count).items()})
    with np.load(Path(first) / "task/trace.npz") as a, np.load(Path(second) / "task/trace.npz") as b:
        errors.update(array_errors(a, b, ["contact_force_w"], 4*k))
    return dict(max_errors=errors, matched=max(errors.values()) <= 1e-5)


def pair_audit(first, second, k):
    first, second = Path(first), Path(second)
    initial = paired_entry(first, second)
    prefix = prefix_audit(first, second, k)
    with np.load(first / "task/handoff-state.npz") as a, np.load(second / "task/handoff-state.npz") as b:
        if set(a.files) != set(b.files):
            raise ValueError("Handoff state schemas differ")
        incoming = array_errors(a, b, a.files)
    receipts = [json.loads((p / "task/handoff.json").read_text()) for p in (first, second)]
    rng = receipts[0]["rng"] == receipts[1]["rng"]
    matched = initial["matched"] and prefix["matched"] and max(incoming.values()) <= 1e-5 and rng
    return dict(matched=matched, initial=initial, prefix=prefix,
                incoming_max_errors=incoming, incoming_rng_matched=rng)


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    registration_path = PROJECT / "configs/continuation_v1.plan.json"
    registration = json.loads(registration_path.read_text())
    shutil.copy2(registration_path, output / "registration.json")
    parent = PROJECT / registration["parent_packet"]
    old = json.loads((parent / "plan.json").read_text())
    # Reuse bound data/assets, but pin the actual runtime for this new study.
    bindings = [b for b in old["bindings"] if not b["path"].endswith(".py")]
    bindings += [binding(registration_path), binding(parent / "plan.json")]
    for b in bindings:
        checked(b)
    cases = []
    for clip in registration["source_clips"]:
        parent_run = parent / "episodes" / f"{clip}_beam_continuous"
        score_path = parent_run / "task/task-result.json"
        score = json.loads(score_path.read_text())
        task = json.loads((parent_run / "task.json").read_text())
        states = select_states(score, task["hold_ticks"])
        for filename in ["task-result.json", "teacher-episode.npz", "trace.npz", "pre-action-poses.npz"]:
            bindings.append(binding(parent_run / "task" / filename))
        for state, k in states.items():
            for method in registration["methods"]:
                name = f"{clip}_{state}_{method}"
                path = output / "episodes" / name
                path.mkdir(parents=True)
                new_task = dict(task, task_id=name, research_protocol=registration["schema"],
                                research_method=method)
                dump(path / "task.json", new_task)
                config = json.loads((parent_run / "config.json").read_text())
                target = next((parent / "references" / f"{clip}_{method}" / "motions").glob("*.pkl"))
                config.update(task_path=str(path / "task.json"), output=str(path / "task"),
                              actor_profile="privileged_same_phase_continuation_diagnostic",
                              handoff_tick=k, method=method, target_motion=binding(target),
                              parent_run=str(parent_run))
                dump(path / "config.json", config)
                command = json.loads((parent_run / "command.json").read_text())
                replacements = {
                    "++callbacks.im_eval._target_": "hindsight_motion.continuation_native.ReferenceHandoffCallback",
                    "++callbacks.im_eval.stage_config": str(path / "config.json"),
                    "++manager_env.config.navigation_task_path": str(path / "task.json"),
                    "++eval_output_dir": str(path / "unused"), "++eval_base_dir": str(path / "hydra"),
                }
                command = [a.split("=", 1)[0] + "=" + replacements[a.split("=", 1)[0]]
                           if a.split("=", 1)[0] in replacements else a for a in command]
                dump(path / "command.json", command)
                for f in ["task.json", "config.json", "command.json"]:
                    bindings.append(binding(path / f))
                bindings.append(binding(target))
                cases.append(dict(case_id=name, source_clip=clip, condition="beam", state=state,
                                  method=method, handoff_tick=k, run_dir=str(path), parent_run=str(parent_run)))
    # Pin the execution path, including policy, observation and native conversion.
    scene_modules = ["duck_runtime", "duck_task", "collision_clearance", "motor_runtime",
                     "navigation_depth_collection", "navigation_recovery", "render_navigation_comparison",
                     "stopping_teacher", "direct_scene_runtime", "direct_context", "tasks", "scene_env",
                     "collect", "navigation_localization", "reference_layout", "navigation_motor_runtime"]
    sources = [RUNTIME / f"gear_sonic/research/scene_distillation/{name}.py" for name in scene_modules]
    sources += [RUNTIME / name for name in [
        "gear_sonic/research/hindsight_training/runtime.py", "gear_sonic/eval_agent_trl.py",
        "gear_sonic/envs/wrapper/manager_env_wrapper.py", "gear_sonic/envs/manager_env/mdp/commands.py",
        "gear_sonic/envs/manager_env/mdp/observations.py", "gear_sonic/utils/motion_lib/motion_lib_base.py",
        "gear_sonic/utils/motion_lib/motion_lib_robot.py", "gear_sonic/isaac_utils/rotations.py",
        "gear_sonic/trl/utils/torch_transform.py",
        "gear_sonic/utils/motion_lib/torch_humanoid_batch.py", "gear_sonic/trl/modules/actor_critic_modules.py",
        "gear_sonic/trl/modules/universal_token_modules.py"]]
    sources += [Path("/home/linjiw/IsaacLab/source/isaaclab/isaaclab") / name for name in
                ["managers/action_manager.py", "managers/observation_manager.py", "envs/mdp/actions/joint_actions.py"]]
    sources += [PROJECT / f"src/hindsight_motion/{name}.py" for name in
                ["continuation", "continuation_native", "complete_task", "complete_task_native", "resource_queue"]]
    for i, source in enumerate(sources):
        destination = output / "code_snapshot" / f"{i:03d}_{source.name}"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source, destination)
        bindings.append(binding(source))
    dump(output / "plan.json", dict(registration=registration, created_unix_s=time.time(), cases=cases,
                                    bindings=list({b["path"]: b for b in bindings}.values())))
    print(json.dumps(dict(prepared=str(output), cases=len(cases), states=[(c["case_id"],c["handoff_tick"]) for c in cases])))


def run(output):
    output = Path(output).resolve()
    plan = json.loads((output / "plan.json").read_text())
    with (output / "execution-start.json").open("x") as f:
        json.dump(dict(start_unix_s=time.time(), plan_sha256=sha256(output / "plan.json")), f)
    for index, case in enumerate(plan["cases"]):
        path = Path(case["run_dir"])
        resource_run([path], timeout_s=plan["registration"]["resource_wait_seconds_per_attempt"], launcher=launch_case)
        if not (path / "launch.json").exists():
            break
        score = json.loads((path / "task/task-result.json").read_text())
        if case["method"] == "continuous":
            audit = prefix_audit(case["parent_run"], path, case["handoff_tick"])
            dump(path / "parent-prefix-audit.json", audit)
            if not audit["matched"] or not score["duck_recover_stop_success"]:
                dump(output / "stopped.json", dict(reason="continuous_qualification_failed", case=case["case_id"]))
                break
        else:
            previous = plan["cases"][index-1]
            audit = pair_audit(previous["run_dir"], path, case["handoff_tick"])
            dump(path / "pair-audit.json", audit)
            if not audit["matched"]:
                dump(output / "stopped.json", dict(reason="incoming_pair_mismatch", case=case["case_id"]))
                break
        print(json.dumps(dict(case=case["case_id"], handoff=case["handoff_tick"],
                              success=score["duck_recover_stop_success"], steps=score["control_steps"])), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output)
