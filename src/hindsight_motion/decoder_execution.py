"""Decode-then-track experiments with frozen scenes and explicit entry scaffolding."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import numpy as np

from .batch_audit import entry
from .batch_scene import materialize
from .budget import main_attempts
from .clearance_tokens import reconstruct
from .core import PatchQuantizer, sha256
from .critical import PROJECT, RUNTIME, dump, launch

METHODS = ("continuous", "RVQ", "RVQ_body9", "RVQ_PCA9", "linear29")
STUDIES = {
    "arm03": "critical_interventions_20260915_v1",
    "arm02": "expansion_interventions_20260915_v1",
    "hybrid205": "robust_beam_interventions_20260915_v1",
}


def originals(pair):
    study = PROJECT / "runs" / STUDIES[pair]
    if pair == "arm03":
        tasks = [
            json.loads((Path(t["run_dir"]) / "task.json").read_text())
            for t in json.loads((study / "tasks.json").read_text())
        ]
        records = {}
        for t in tasks:
            records[t["variant"]] = json.loads(
                (study / t["task_id"] / "manifest.json").read_text()
            )[0]
    else:
        tasks = [
            t
            for t in json.loads((study / "batch.json").read_text())["tasks"]
            if t["pair_id"] == pair
        ]
        manifest = {
            r["motion_key"]: r
            for r in json.loads((study / "manifest.json").read_text())
        }
        records = {t["variant"]: manifest[t["motion_key"]] for t in tasks}
    return tasks, records


def execution_reference(q, angles, limits):
    projected = np.clip(angles, limits[:, 0], limits[:, 1])
    difference = projected - angles
    t = np.arange(len(q)) / 50
    u = np.clip((t - 0.6) / 0.6, 0, 1)
    weight = u**3 * (10 - 15 * u + 6 * u * u)
    result = q.copy()
    result[:, 7:] = q[:, 7:] + weight[:, None] * (projected - q[:, 7:])
    return result, dict(
        projected_scalar_count=int(np.count_nonzero(abs(difference) > 1e-7)),
        maximum_projection_rad=float(abs(difference).max()),
        bridge_first_s=0.6,
        fully_decoded_from_s=1.2,
        bridge_joint_rms_rad=float(
            np.sqrt(np.mean((result[:60, 7:] - projected[:60]) ** 2))
        ),
        root_reference_unchanged=bool(np.array_equal(result[:, :7], q[:, :7])),
    )


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        qpos_to_sonic_motion_entry,
        sonic_motion_entry_to_qpos,
        save_sonic_motion_file,
    )

    output = Path(output)
    construction = output.with_name(output.name + "_construction")
    construction.mkdir(parents=True, exist_ok=False)
    (construction / "motions").mkdir()
    (construction / "references").mkdir()
    plan = PROJECT / "configs/decoder_execution_v1.plan.json"
    shutil.copy2(plan, construction / "registration.json")
    book = np.load(PROJECT / "runs/pilot_20260915_v1/codebook.npz")
    quantizer = PatchQuantizer([book["level0"], book["level1"]])
    model = dict(
        np.load(PROJECT / "runs/clearance_tokens_20260915_v1/residual_model.npz")
    )
    urdf = ET.parse(
        RUNTIME / "gear_sonic/data/assets/robot_description/urdf/g1/main.urdf"
    ).getroot()
    bounds = {
        j.attrib["name"]: [
            float(j.find("limit").attrib["lower"]),
            float(j.find("limit").attrib["upper"]),
        ]
        for j in urdf.findall("joint")
        if j.attrib["type"] == "revolute"
    }
    tasks = []
    records = []
    audits = []
    for pair in STUDIES:
        base_tasks, base_records = originals(pair)
        for variant, original in base_records.items():
            ref = np.load(original["reference_path"])
            q = ref["qpos"]
            names = ref["joint_names"].tolist()
            methods, _, clipped = reconstruct(q, quantizer, model)
            limits = np.array([bounds[n] for n in names])
            for method in METHODS:
                adapted, audit = execution_reference(q, methods[method], limits)
                if method == "continuous":
                    adapted = q.copy()
                key = f"dec_{pair}_{method}_{variant}"
                reference = construction / "references" / f"{key}.npz"
                np.savez_compressed(
                    reference,
                    qpos=adapted,
                    joint_names=names,
                    raw_decoded_angles=methods[method],
                )
                motion = qpos_to_sonic_motion_entry(
                    adapted, source_fps=50, canonicalize_horizontal_origin=False
                )
                error = float(np.max(abs(sonic_motion_entry_to_qpos(motion) - adapted)))
                if error > 1e-6:
                    raise ValueError("Native roundtrip failure")
                path = construction / "motions" / f"{key}.pkl"
                save_sonic_motion_file(path, motion_key=key, motion_entry=motion)
                row = deepcopy(original)
                row.update(
                    motion_key=key,
                    motion_path=str(path),
                    motion_sha256=sha256(path),
                    reference_path=str(reference),
                    reference_sha256=sha256(reference),
                    method=method,
                    source_pair_id=pair,
                    original_reference_path=original["reference_path"],
                    execution_adapter=audit,
                )
                audits.append(
                    dict(
                        source_pair_id=pair,
                        variant=variant,
                        method=method,
                        clipped_symbols=clipped.get(method, 0),
                        **audit,
                    )
                )
                for perturbation in range(3):
                    task = deepcopy(
                        next(
                            t
                            for t in base_tasks
                            if t["variant"] == variant
                            and t["condition"] == "removed"
                            and t["perturbation_id"] == perturbation
                        )
                    )
                    task.update(
                        task_id=f"dec_{pair}_{method}_removed_{variant}_p{perturbation}",
                        pair_id=f"dec_{pair}_{method}",
                        source_pair_id=pair,
                        method=method,
                        preflight_only=True,
                    )
                    tasks.append(task)
                    records.append(row)
    dump(construction / "adapter_audit.json", audits)
    shutil.copy2(__file__, construction / "preparation_code.py")
    materialize(
        tasks,
        records,
        output,
        dict(
            purpose="Decoded motion repeated empty-scene qualification",
            budget_parent=str(plan),
            planned_episodes=90,
            counts_as_preflight=True,
            new_preflight_launch=1,
            split="development",
            methods=list(METHODS),
            source_pairs=list(STUDIES),
            entry_scaffold="Original prefix to .6 s; quintic blend to decoded by 1.2 s",
            compare_to_original_reference=True,
        ),
    )


def original_fidelity_score(actual, reference, valid_rows, expected_rows=200):
    """Keep original-motion preservation separate from decoded-reference tracking."""
    if valid_rows < 1:
        return dict(
            original_body_mean_error_m=None,
            original_root_xy_max_error_m=None,
            original_motion_fidelity_pass=False,
        )
    actual = np.asarray(actual)[:valid_rows]
    reference = np.asarray(reference)[:valid_rows]
    if (
        actual.shape != reference.shape
        or not np.isfinite(actual).all()
        or not np.isfinite(reference).all()
    ):
        raise ValueError("Missing or invalid original-motion fidelity evidence")
    body = float(np.linalg.norm(actual - reference, axis=-1).mean())
    root = float(np.linalg.norm(actual[:, 0, :2] - reference[:, 0, :2], axis=-1).max())
    return dict(
        original_body_mean_error_m=body,
        original_root_xy_max_error_m=root,
        original_motion_fidelity_pass=body <= 0.1
        and root <= 0.25
        and valid_rows == expected_rows,
    )


def fidelity(output, preflight):
    output = Path(output)
    preflight = Path(preflight)
    batch = json.loads((output / "batch.json").read_text())
    base = json.loads((preflight / "batch.json").read_text())
    original = {}
    for t in base["tasks"]:
        if t["method"] == "continuous":
            original[t["source_pair_id"], t["variant"], t["perturbation_id"]] = np.load(
                preflight / "metrics" / f"episode-{t['motion_key']}.npz"
            )["reference_body_pos"]
    rows = []
    for t in batch["tasks"]:
        e = dict(np.load(output / "metrics" / f"episode-{t['motion_key']}.npz"))
        n = int(e["before_first_native_failure"].sum())
        ref = original[t["source_pair_id"], t["variant"], t["perturbation_id"]][:n]
        actual = e["tracked_body_pos"][:n]
        rows.append(
            dict(
                task_id=t["task_id"],
                source_pair_id=t["source_pair_id"],
                pair_id=t["pair_id"],
                method=t["method"],
                variant=t["variant"],
                condition=t["condition"],
                perturbation_id=t["perturbation_id"],
                **original_fidelity_score(actual, ref, n),
            )
        )
    dump(output / "original_fidelity.json", rows)
    return rows


def qualify(output):
    output = Path(output)
    scores = {r["task_id"]: r for r in fidelity(output, output)}
    outcomes = {
        r["task_id"]: r
        for r in json.loads((output / "metrics/scene-outcomes.json").read_text())
    }
    tasks = json.loads((output / "batch.json").read_text())["tasks"]
    source_pairs = list(dict.fromkeys(t["source_pair_id"] for t in tasks))
    methods = list(dict.fromkeys(t["method"] for t in tasks))
    common = []
    for source_pair in source_pairs:
        for perturbation in range(3):
            selected = [
                t
                for t in tasks
                if t["source_pair_id"] == source_pair
                and t["perturbation_id"] == perturbation
            ]
            entries = [
                entry(
                    dict(np.load(output / "metrics" / f"episode-{t['motion_key']}.npz"))
                )
                for t in selected
            ]
            difference = {
                k: float(max(np.max(abs(e[k] - entries[0][k])) for e in entries))
                for k in entries[0]
            }
            common.append(
                dict(
                    source_pair_id=source_pair,
                    perturbation_id=perturbation,
                    maximum_differences=difference,
                    matched=max(difference.values()) <= 1e-5,
                )
            )
    rows = []
    for pair in source_pairs:
        for method in methods:
            selected = [
                t
                for t in tasks
                if t["source_pair_id"] == pair and t["method"] == method
            ]
            entry_ok = all(c["matched"] for c in common if c["source_pair_id"] == pair)
            valid = {
                v: sum(
                    outcomes[t["task_id"]]["scene_passage_verified"]
                    and scores[t["task_id"]]["original_motion_fidelity_pass"]
                    for t in selected
                    if t["variant"] == v
                )
                for v in {t["variant"] for t in selected}
            }
            rows.append(
                dict(
                    source_pair_id=pair,
                    method=method,
                    pair_id=selected[0]["pair_id"],
                    successes=valid,
                    native_passes=sum(
                        outcomes[t["task_id"]]["scene_passage_verified"]
                        for t in selected
                    ),
                    fidelity_passes=sum(
                        scores[t["task_id"]]["original_motion_fidelity_pass"]
                        for t in selected
                    ),
                    qualified=entry_ok and all(n == 3 for n in valid.values()),
                )
            )
    dump(output / "common_entry_audit.json", common)
    dump(output / "decoder_qualification.json", rows)
    print(json.dumps(rows, indent=2))


def prepare_scenes(preflight, output):
    preflight = Path(preflight)
    qual = json.loads((preflight / "decoder_qualification.json").read_text())
    eligible = [
        r
        for r in qual
        if r["qualified"] and r["source_pair_id"] in ("arm03", "hybrid205")
    ]
    reference_tasks = json.loads((preflight / "batch.json").read_text())["tasks"]
    manifest = {
        r["motion_key"]: r
        for r in json.loads((preflight / "manifest.json").read_text())
    }
    tasks = []
    records = []
    for r in eligible:
        base, _ = originals(r["source_pair_id"])
        for t in base:
            template = next(
                x
                for x in reference_tasks
                if x["source_pair_id"] == r["source_pair_id"]
                and x["method"] == r["method"]
                and x["variant"] == t["variant"]
                and x["perturbation_id"] == t["perturbation_id"]
            )
            task = deepcopy(t)
            task.update(
                task_id=f"{r['pair_id']}_{t['condition']}_{t['variant']}_p{t['perturbation_id']}",
                pair_id=r["pair_id"],
                source_pair_id=r["source_pair_id"],
                method=r["method"],
                representation_test=True,
            )
            tasks.append(task)
            records.append(manifest[template["motion_key"]])
    if not tasks:
        raise ValueError("No qualified decoder/reference cells")
    if len(tasks) > 240:
        raise ValueError("Registered decoder main budget exceeded")
    previous = main_attempts()
    if previous + len(tasks) > 480:
        raise ValueError("Main study would exceed registered episode ceiling")
    materialize(
        tasks,
        records,
        output,
        dict(
            purpose="Frozen-scene decoded-reference interventions",
            budget_parent=str(PROJECT / "configs/decoder_execution_v1.plan.json"),
            preflight=str(preflight),
            qualified_cells=eligible,
            planned_episodes=len(tasks),
            main_study_previous_episodes=previous,
            budget_role="main",
            frozen_geometry=True,
            representation_cells_are_new_source_groups=False,
            split="development",
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=["prepare", "launch", "qualify", "prepare_scenes", "fidelity"],
    )
    p.add_argument("paths", nargs="+", type=Path)
    a = p.parse_args()
    globals()[a.command](*[x.resolve() for x in a.paths])
