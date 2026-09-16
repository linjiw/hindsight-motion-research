"""Offline foot reconstruction diagnostics; no inferred physical contact labels."""

import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .critical import PROJECT, RUNTIME, dump
from .critical_tokens import urdf_fk
from .mechanism import METHODS


def run():
    pre = PROJECT / "runs/token_mechanism_preflight_20260915_v2"
    output = PROJECT / "runs/token_mechanism_validation_20260915_v1"
    output.mkdir(exist_ok=True)
    names = ["left_ankle_roll_link", "right_ankle_roll_link"]
    urdf = RUNTIME / "gear_sonic/data/assets/robot_description/urdf/g1/main.urdf"
    records = {}
    for r in json.loads((pre / "manifest.json").read_text()):
        records[r["source_pair_id"], r["variant"], r["method"]] = r
    poses = {}
    for key, row in records.items():
        ref = np.load(row["reference_path"])
        q = ref["qpos"]
        assert all(
            any(part in n for part in ("hip", "knee", "ankle"))
            for n in ref["joint_names"][:12]
        )
        poses[key] = urdf_fk(
            urdf, q[:, :3], q[:, 3:7], q[:, 7:], ref["joint_names"].tolist(), names
        )
    rows = []
    for (pair, variant, method), pose in poses.items():
        base = poses[pair, variant, "continuous"]
        position = pose["body_xyz"][60:]
        original = base["body_xyz"][60:]
        velocity = np.diff(position, axis=0) * 50
        original_velocity = np.diff(original, axis=0) * 50
        qa = pose["body_wxyz"][60:, :, [1, 2, 3, 0]].reshape(-1, 4)
        qb = base["body_wxyz"][60:, :, [1, 2, 3, 0]].reshape(-1, 4)
        angle = (Rotation.from_quat(qb).inv() * Rotation.from_quat(qa)).magnitude()
        rows.append(
            dict(
                source_pair_id=pair,
                variant=variant,
                method=method,
                foot_position_rmse_m=float(
                    np.sqrt(np.mean(np.sum((position - original) ** 2, axis=-1)))
                ),
                foot_velocity_rmse_mps=float(
                    np.sqrt(
                        np.mean(np.sum((velocity - original_velocity) ** 2, axis=-1))
                    )
                ),
                foot_orientation_rms_rad=float(np.sqrt(np.mean(angle**2))),
            )
        )
    result = dict(
        exploratory=True,
        offline_only=True,
        physics_verified=False,
        scope="Executed-reference FK after 1.2 s; ankle-link position/orientation, no contact or slip labels",
        rows=rows,
        summary=[
            dict(
                method=m,
                **{
                    k: float(np.mean([r[k] for r in rows if r["method"] == m]))
                    for k in (
                        "foot_position_rmse_m",
                        "foot_velocity_rmse_mps",
                        "foot_orientation_rms_rad",
                    )
                }
            )
            for m in METHODS
        ],
    )
    dump(output / "foot_reconstruction.json", result)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    run()
