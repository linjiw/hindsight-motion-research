"""Reuse the pinned complete-task recorder without modifying the external runtime."""
import json
from pathlib import Path

import numpy as np

from gear_sonic.research.scene_distillation.duck_runtime import DuckTeacherCallback


class CompleteReferenceCallback(DuckTeacherCallback):
    def _begin_task(self, env, teacher, task):
        # The external recorder restricts its label hook to the train transport
        # split. Our bound task and all released evidence remain development.
        super()._begin_task(env, teacher, dict(task, split="train"))
        robot = env.env.scene["robot"]
        self.initial_state = {
            "root_state_w": robot.data.root_state_w[0].detach().cpu().numpy().copy(),
            "joint_pos": robot.data.joint_pos[0].detach().cpu().numpy().copy(),
            "joint_vel": robot.data.joint_vel[0].detach().cpu().numpy().copy(),
        }

    def _complete_task(self, task, score, output):
        super()._complete_task(task, score, output)
        np.savez_compressed(output / "initial-state.npz", **self.initial_state,
                            proprio=self.rows[0]["proprio"])
        episode_path = output / "teacher-episode.npz"
        with np.load(episode_path) as f:
            data = {k: f[k] for k in f.files}
        data["diagnostic_task_support"] = data["query_mask"].copy()
        data["query_mask"] = np.zeros(len(data["query_mask"]), dtype=bool)
        np.savez_compressed(episode_path, **data)
        # Replace the inherited collection manifest with our explicit no-training
        # contract after closing the file; raw targets remain local diagnostics.
        (output / "collection.json").write_text(json.dumps({
            "schema": "hindsight_complete_task_diagnostic_v1",
            "split": "development", "positive_student_training_authorized": False,
            "episodes": [], "diagnostic_rows": len(data["query_mask"]),
            "task_success": bool(score["duck_recover_stop_success"]),
            "reason": "Supplied-reference support test, not a student training release",
        }, indent=2) + "\n")
