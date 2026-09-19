import json

import numpy as np
import pytest

from hindsight_motion.complete_task import decode_linear29, paired_entry
from hindsight_motion import resource_queue


def test_linear_retains_root_and_common_reset_but_not_original_entry():
    q = np.zeros((100, 36))
    q[:, 3] = 1
    q[:, :2] = np.arange(100)[:, None] * 0.01
    q[:, 7:] = np.sin(np.arange(100)[:, None] * 0.09) * 0.4
    decoded, audit = decode_linear29(q, np.ones(29))
    np.testing.assert_array_equal(decoded[:, :7], q[:, :7])
    np.testing.assert_array_equal(decoded[:2], q[:2])
    assert np.max(abs(decoded[2:30, 7:] - q[2:30, 7:])) > 1e-4
    assert audit["joint_payload_bits"] == 20 * 29 * 12
    assert audit["reset_anchor_bits"] == 2 * 29 * 32
    assert audit["common_root_bits"] == 100 * 7 * 32


def test_linear_clipping_and_invalid_inputs():
    q = np.zeros((10, 36)); q[:, 7:] = 2
    decoded, audit = decode_linear29(q, np.ones(29))
    assert audit["clipped_symbols"] == 58
    assert (decoded[2:, 7:] == 1).all()
    with pytest.raises(ValueError):
        decode_linear29(q, np.zeros(29))
    with pytest.raises(ValueError):
        decode_linear29(q[:9], np.ones(29))


def test_matching_includes_velocity_history_dynamics_and_rng(tmp_path):
    paths = [tmp_path / x for x in ("a", "b")]
    for p in paths:
        (p / "task").mkdir(parents=True)
        np.savez(p / "task/initial-state.npz", joint_pos=np.zeros(29),
                 joint_vel=np.zeros(29), proprio=np.zeros(930))
        np.savez(p / "task/dynamics-entry.npz", masses=np.ones(30))
        (p / "task/depth-source.json").write_text(json.dumps({
            "first_physics_step_torch_rng_sha256": {"cpu": "same"}}))
    assert paired_entry(*paths)["matched"]
    np.savez(paths[1] / "task/initial-state.npz", joint_pos=np.zeros(29),
             joint_vel=np.ones(29) * .1, proprio=np.zeros(930))
    assert not paired_entry(*paths)["matched"]


def test_resource_gate_serial_custom_launcher(tmp_path, monkeypatch):
    runs = [tmp_path / "one", tmp_path / "two"]
    for path in runs:
        path.mkdir()
    events = []
    monkeypatch.setattr(resource_queue, "resources", lambda: dict(free_gpu_mib=13000, available_host_mib=20000))
    monkeypatch.setattr(resource_queue.time, "sleep", lambda _: None)
    def launch(path):
        events.append(path.name)
        assert (path / "resource_admission.json").exists()
        (path / "launch.json").write_text("{}")
        (path / "exit.json").write_text('{"exit_code":0}')
    resource_queue.run(runs, launcher=launch)
    assert events == ["one", "two"]
    assert len((runs[0] / "resource_wait.jsonl").read_text().splitlines()) == 2
    with pytest.raises(FileExistsError):
        resource_queue.run(runs, launcher=launch)


def test_resource_gate_stops_on_infrastructure_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(resource_queue, "resources", lambda: dict(free_gpu_mib=13000, available_host_mib=20000))
    monkeypatch.setattr(resource_queue.time, "sleep", lambda _: None)
    def fail(path):
        (path / "exit.json").write_text('{"exit_code":1}')
    with pytest.raises(RuntimeError):
        resource_queue.run([tmp_path], launcher=fail)
