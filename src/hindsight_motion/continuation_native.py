"""Replace a reference only after an actually executed common prefix."""
import hashlib
import json
from pathlib import Path
import pickle
import random

import joblib
import numpy as np
import torch

from .complete_task import checked
from .complete_task_native import CompleteReferenceCallback


def cpu(value):
    return torch.as_tensor(value).detach().cpu().numpy().copy()


def rng_hashes():
    states = dict(cpu=bytes(torch.get_rng_state().tolist()),
                  numpy=pickle.dumps(np.random.get_state()), python=pickle.dumps(random.getstate()))
    states.update({f"cuda_{i}": bytes(s.cpu().tolist()) for i, s in enumerate(torch.cuda.get_rng_state_all())})
    return {name: hashlib.sha256(value).hexdigest() for name, value in states.items()}


def converted_library(lib, motion_path):
    """Use the resident loader's FK and reordering; no alternate velocity rule."""
    entry = next(iter(joblib.load(motion_path).values()))
    if entry["fps"] != 50 or lib.target_fps != 50 or lib.num_motions() != 1:
        raise ValueError("Only the registered single 50Hz reference is supported")
    pose = torch.as_tensor(entry["pose_aa"]).float()
    trans = torch.as_tensor(entry["root_trans_offset"]).float().clone()
    trans, _ = lib.fix_trans_height(pose, trans, fix_height_mode=lib.fix_height)
    fk = lib.mesh_parsers.fk_batch(pose[None], trans[None], return_full=True,
                                  fps=50, target_fps=50, interpolate_data=True,
                                  use_parallel_fk=lib.use_parallel_fk)
    mapping = {
        "dof_pos": "dof_pos", "dof_vel": "dof_vels", "body_pos_b": "local_rotation",
        "root_linv_vel_w": "global_root_velocity", "root_ang_vel_w": "global_root_angular_velocity",
        "body_pos_w_full": "global_translation", "body_quat_w_full": "global_rotation",
        "body_lin_vel_w_full": "global_velocity", "body_ang_vel_w_full": "global_angular_velocity",
    }
    values = {name: fk[key][0].float().to(lib._device) for name, key in mapping.items()}
    if "mujoco_to_isaaclab_body" not in lib.m_cfg:
        raise ValueError("Expected registered IsaacLab joint/body mapping")
    for name in ["dof_pos", "dof_vel"]:
        values[name] = values[name][:, lib.m_cfg.mujoco_to_isaaclab_dof]
    for name in ["body_pos_w", "body_quat_w", "body_lin_vel_w", "body_ang_vel_w"]:
        full = values[name + "_full"][:, lib.m_cfg.mujoco_to_isaaclab_body]
        if name == "body_quat_w":
            full = torch.cat([full[..., 3:], full[..., :3]], dim=-1)
        values[name + "_full"] = full
        values[name] = full[:, lib.body_indexes]
    if lib.m_cfg.get("zero_root_xy", False):
        # Match the loader before its body-index slicing.
        offset = values["body_pos_w_full"][0, 0, :2].clone()
        values["body_pos_w_full"][..., :2] -= offset
        values["body_pos_w"] = values["body_pos_w_full"][:, lib.body_indexes]
    return values


class ReferenceHandoffCallback(CompleteReferenceCallback):
    def _begin_task(self, env, teacher, task):
        super()._begin_task(env, teacher, task)
        output = Path(self.config["output"])
        k = self.config["handoff_tick"]
        lib, command = env._motion_lib, env.motion_command
        source = checked(task["native_motion"])
        target = checked(self.config["target_motion"])
        before_rng = rng_hashes()
        with torch.random.fork_rng():
            rebuilt = converted_library(lib, source)
            candidate = converted_library(lib, target)
        if rng_hashes() != before_rng:
            raise ValueError("Reference preparation changed RNG")
        errors = {}
        for name, value in rebuilt.items():
            resident = getattr(lib, name)
            if resident.shape != value.shape or not torch.isfinite(value).all():
                raise ValueError(f"Native adapter shape/finite error: {name}")
            errors[name] = float((resident-value).abs().max())
        (output / "adapter.json").write_text(json.dumps(dict(
            continuous_rebuild_max_errors=errors, tolerance=1e-5,
            method=self.config["method"], rng_preserved=True,
            native_anchor=command.cfg.anchor_body, reference_frames=int(lib.dof_pos.shape[0]),
            fields=list(rebuilt)), indent=2) + "\n")
        if max(errors.values()) > 1e-5:
            raise ValueError(f"Continuous native adapter parity failed: {errors}")
        if command.cfg.anchor_body != "pelvis":
            raise ValueError("Unregistered native anchor")
        if self.config["method"] == "continuous":
            candidate = {name: getattr(lib, name).clone() for name in rebuilt}
        self.handoff_previous_step = env.step
        self.handoff_original_inference = teacher.act_inference
        self.handoff_recorded = False
        self.reference_replaced = False
        self.handoff_jump = None

        def step(*args, **kwargs):
            # rows already contains action k-1. Physics still executes that exact
            # action; only subsequent reference observations see the candidate.
            if len(self.rows) == k:
                index = min(int((command.motion_start_time_steps + command.time_steps)[0])+1,
                            len(lib.dof_pos)-1)
                self.handoff_jump = {
                    "reference_index": index,
                    "joint_position_max_rad": float((candidate["dof_pos"][index]-lib.dof_pos[index]).abs().max()),
                    "joint_velocity_max_rad_s": float((candidate["dof_vel"][index]-lib.dof_vel[index]).abs().max()),
                }
                for name, value in candidate.items():
                    setattr(lib, name, value)
                self.reference_replaced = True
            return self.handoff_previous_step(*args, **kwargs)

        def inference(obs_dict, *args, **kwargs):
            if len(self.rows) == k:
                if not self.reference_replaced or self.handoff_recorded:
                    raise ValueError("Invalid reference handoff timing")
                robot = env.env.scene["robot"]
                manager = env.env.action_manager
                action = manager.get_term("joint_pos")
                values = dict(root_state=robot.data.root_state_w, joint_pos=robot.data.joint_pos,
                              joint_vel=robot.data.joint_vel, body_state=robot.data.body_state_w,
                              actor_observation=obs_dict["actor_obs"], current_action=manager.action,
                              previous_action=manager.prev_action, raw_action=action.raw_actions,
                              processed_action=action.processed_actions,
                              cursor=command.time_steps, start_cursor=command.motion_start_time_steps,
                              teacher_steps=np.asarray(teacher.steps))
                values.update({"teacher_buffer_" + name: value
                               for name, value in teacher.obs_dict_buffer.items()})
                np.savez_compressed(output / "handoff-state.npz", **{name: cpu(v) for name, v in values.items()})
                (output / "handoff.json").write_text(json.dumps(dict(
                    tick=k, rng=rng_hashes(), jump=self.handoff_jump,
                    timing="before action k, after k common-prefix steps; no reset",
                    state_fields=list(values)), indent=2) + "\n")
                self.handoff_recorded = True
            return self.handoff_original_inference(obs_dict, *args, **kwargs)

        env.step = step
        teacher.act_inference = inference
        self.handoff_teacher = teacher

    def _complete_task(self, task, score, output):
        self.handoff_teacher.act_inference = self.handoff_original_inference
        self.recording_env.step = self.handoff_previous_step
        super()._complete_task(task, score, output)
        (output / "handoff-status.json").write_text(json.dumps(dict(
            reached=self.handoff_recorded, replaced=self.reference_replaced,
            requested_tick=self.config["handoff_tick"], completed_steps=score["control_steps"]), indent=2) + "\n")
