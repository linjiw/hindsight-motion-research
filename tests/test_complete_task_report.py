import json

import numpy as np
import pytest

from hindsight_motion.complete_task_report import audit_case


def fake_success(tmp_path):
    """Synthetic audit fixture, never a simulated robot result."""
    out = tmp_path / "task"; out.mkdir()
    task = dict(goal_xyz=[2., 0., .8], goal_tolerance_m=.5, terminal_speed_mps=.1,
                hold_ticks=50, success_profile="synthetic_test",
                duck_contract=dict(recovery_pelvis_height_m=[.75, .85], max_torso_tilt_rad=.3,
                                   clearance_margin_m=.02, recovery_ticks=15,
                                   gate=dict(full_dimensions_xyz=[.35, 2., .2])))
    score = dict(control_steps=70, duck_recover_stop_success=True, fell=False,
                 stop_reason="goal_hold", passage_success=True, recovered=True,
                 ordered_hold_ticks=50, entry_tick=0, clear_tick=1, recovery_tick=19)
    for path, data in [(tmp_path / "task.json", task), (tmp_path / "launch.json", {}),
                       (tmp_path / "exit.json", dict(exit_code=0, elapsed_s=1)),
                       (out / "task-result.json", score)]:
        path.write_text(json.dumps(data))
    np.savez(out / "trace.npz", root_xyz=np.tile([2., 0., .8], (70, 1)), speed=np.zeros(70),
             contact_force_w=np.zeros((280, 1, 1, 3)), body_names=["left_ankle_roll_link"])
    np.savez(out / "duck-features.npz", lower=np.tile([1., 0., 0.], (70, 1)),
             upper=np.tile([2., 1., 1.], (70, 1)), torso_tilt=np.zeros(70))
    np.savez(out / "teacher-episode.npz", query_mask=np.zeros(70, dtype=bool))
    return dict(case_id="synthetic", source_clip="fixture", method="continuous",
                condition="clear", run_dir=str(tmp_path))


def test_success_audit_and_broken_hold(tmp_path):
    case = fake_success(tmp_path)
    assert audit_case(case)["success"]
    path = tmp_path / "task/trace.npz"
    with np.load(path) as f:
        trace = {k: f[k] for k in f.files}
    trace["speed"][-20] = .2
    np.savez(path, **trace)
    with pytest.raises(ValueError, match="terminal/contact"):
        audit_case(case)


def test_audit_rejects_development_training_mask(tmp_path):
    case = fake_success(tmp_path)
    np.savez(tmp_path / "task/teacher-episode.npz", query_mask=np.ones(70, dtype=bool))
    with pytest.raises(ValueError, match="training labels"):
        audit_case(case)
