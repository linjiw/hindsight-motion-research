"""Frozen-candidate geometry comparison for the new decoder interventions."""

import argparse
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .clearance_tokens import cases, inner_points, reconstruct
from .core import PatchQuantizer, sha256
from .critical import PROJECT, RUNTIME, dump
from .critical_tokens import urdf_fk
from .mechanism import METHODS, factorial_angles


def run(output):
    from gear_sonic.research.scene_distillation.collision_clearance import (
        recorded_bounds,
        obstacle_separation,
    )
    from gear_sonic.research.scene_distillation.critical_pair_calibration import (
        point_distance,
    )

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    dump(
        output / "registration.json",
        dict(
            registered_unix_s=time.time(),
            purpose="Fixed-candidate geometry for temporal and leg reconstruction interventions",
            parent=str(PROJECT / "configs/token_mechanism_v1.plan.json"),
            methods=list(METHODS),
            candidates="All 643 prior arm03/arm02/arm07/duck02 candidates; unchanged",
            continuous_reference_is_geometric_truth_only=True,
            target_clearance_m=0.03,
            negative_inner_overlap_m=0.01,
            fit="None; frozen codebook and residual/scalar model",
            reference="Full decoded reference with original root; no native entry scaffold. Offline proposer diagnostic.",
            split="development",
            physics_verified=False,
            extra_physics_budget=0,
        ),
    )
    shutil.copy2(__file__, output / "analysis_code.py")
    first = PROJECT / "runs/critical_preflight_20260915_v2"
    names = json.loads((first / "metrics/episode-contract.json").read_text())[
        "measured_body_names"
    ]
    proxies = json.loads((first / "native_collision_proxies.json").read_text())
    urdf = RUNTIME / "gear_sonic/data/assets/robot_description/urdf/g1/main.urdf"
    book = np.load(PROJECT / "runs/pilot_20260915_v1/codebook.npz")
    quantizer = PatchQuantizer([book["level0"], book["level1"]])
    model_path = PROJECT / "runs/clearance_tokens_20260915_v1/residual_model.npz"
    model = dict(np.load(model_path))
    rows, pairs = [], []
    for case in cases():
        values, witnesses = {}, {}
        proposals = case["proposals"]["proposals"]
        for variant, record in case["records"].items():
            reference = np.load(record["reference_path"])
            q, joint_names = reference["qpos"], reference["joint_names"].tolist()
            methods = factorial_angles(q, reconstruct(q, quantizer, model)[0])
            for method in METHODS:
                pose = urdf_fk(
                    urdf, q[:, :3], q[:, 3:7], methods[method], joint_names, names
                )
                bounds = recorded_bounds(proxies, pose)
                points, radii = inner_points(bounds, proxies, case["family"])
                clear, witness = [], []
                for p in proposals:
                    clear.append(
                        min(
                            float(obstacle_separation(bounds, o).min())
                            for o in p["obstacles"]
                        )
                    )
                    witness.append(
                        min(
                            float((point_distance(points, o) - radii).min())
                            for o in (
                                p["obstacles"][:1]
                                if case["family"] == "duck"
                                else p["obstacles"]
                            )
                        )
                    )
                values[variant, method] = np.asarray(clear)
                witnesses[variant, method] = np.asarray(witness)
                baseline = values[variant, "continuous"]
                rows.append(
                    dict(
                        pair_id=case["pair_id"],
                        variant=variant,
                        method=method,
                        candidates=len(clear),
                        clearance_mae_m=float(abs(np.asarray(clear) - baseline).mean()),
                    )
                )
            print(f"Geometry scored {case['pair_id']} {variant}", flush=True)
        positive, negative = list(case["records"])
        truth = (values[positive, "continuous"] >= 0.03) & (
            witnesses[negative, "continuous"] <= -0.01
        )
        for method in METHODS:
            admit = (values[positive, method] >= 0.03) & (
                witnesses[negative, method] <= -0.01
            )
            pairs.append(
                dict(
                    pair_id=case["pair_id"],
                    method=method,
                    candidates=len(truth),
                    reference_admitted=int(truth.sum()),
                    method_admitted=int(admit.sum()),
                    false_admissions=int((admit & ~truth).sum()),
                    missed_admissions=int((truth & ~admit).sum()),
                )
            )
        np.savez_compressed(
            output / f"{case['pair_id']}_scores.npz",
            **{f"clearance_{v}_{m}": x for (v, m), x in values.items()},
            **{f"witness_{v}_{m}": x for (v, m), x in witnesses.items()},
        )
    summary = []
    for method in METHODS:
        group = [r for r in pairs if r["method"] == method]
        summary.append(
            dict(
                method=method,
                macro_clearance_mae_m=float(
                    np.mean(
                        [r["clearance_mae_m"] for r in rows if r["method"] == method]
                    )
                ),
                **{
                    k: sum(r[k] for r in group)
                    for k in (
                        "candidates",
                        "reference_admitted",
                        "method_admitted",
                        "false_admissions",
                        "missed_admissions",
                    )
                },
            )
        )
    dump(
        output / "results.json",
        dict(
            summary=summary,
            motion_rows=rows,
            pair_rows=pairs,
            frozen_model_sha256=sha256(model_path),
            urdf_sha256=sha256(urdf),
            physics_verified=False,
        ),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    run(p.parse_args().output.resolve())
