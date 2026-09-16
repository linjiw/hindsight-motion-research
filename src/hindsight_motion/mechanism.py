"""Registered temporal-decoder × leg-information intervention with frozen teacher."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import numpy as np

from .batch_scene import materialize
from .budget import main_attempts
from .clearance_tokens import reconstruct
from .core import PatchQuantizer, sha256
from .critical import PROJECT, RUNTIME, dump, launch
from .decoder_execution import execution_reference, originals, qualify, fidelity

PLAN = PROJECT / "configs/token_mechanism_v1.plan.json"
METHODS = (
    "continuous",
    "linear29",
    "body9_raw",
    "body9_smooth",
    "body9_legoracle",
    "body9_smooth_legoracle",
    "body9_leg12",
    "body9_smooth_leg12",
)


def smooth_angles(angles):
    padded = np.pad(angles, ((2, 2), (0, 0)), mode="edge")
    return (
        sum(w * padded[i : i + len(angles)] for i, w in enumerate((1, 4, 6, 4, 1))) / 16
    )


def factorial_angles(q, decoded):
    raw = decoded["RVQ_body9"].copy()
    smooth = smooth_angles(raw)
    result = dict(
        continuous=q[:, 7:].copy(),
        linear29=decoded["linear29"].copy(),
        body9_raw=raw,
        body9_smooth=smooth,
    )
    for label, base in [("body9", raw), ("body9_smooth", smooth)]:
        for legs, values in [
            ("legoracle", q[:, 7:19]),
            ("leg12", decoded["linear29"][:, :12]),
        ]:
            x = base.copy()
            x[:, :12] = values
            result[f"{label}_{legs}"] = x
    return result


def construction_folder(output):
    folder = Path(output).with_name(Path(output).name + "_construction")
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "references").mkdir()
    (folder / "motions").mkdir()
    shutil.copy2(PLAN, folder / "registration.json")
    shutil.copy2(__file__, folder / "mechanism_code.py")
    return folder


def save_reference(folder, key, q, names, source, **metadata):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        qpos_to_sonic_motion_entry,
        sonic_motion_entry_to_qpos,
        save_sonic_motion_file,
    )

    reference = folder / "references" / f"{key}.npz"
    np.savez_compressed(reference, qpos=q, joint_names=names)
    motion = qpos_to_sonic_motion_entry(
        q, source_fps=50, canonicalize_horizontal_origin=False
    )
    if np.max(abs(sonic_motion_entry_to_qpos(motion) - q)) > 1e-6:
        raise ValueError("Native motion roundtrip failed")
    path = folder / "motions" / f"{key}.pkl"
    save_sonic_motion_file(path, motion_key=key, motion_entry=motion)
    row = deepcopy(source)
    row.update(
        motion_key=key,
        motion_path=str(path),
        motion_sha256=sha256(path),
        reference_path=str(reference),
        reference_sha256=sha256(reference),
        frames=len(q),
        split="development",
        **metadata,
    )
    return row


def prepare(output):
    output = Path(output)
    folder = construction_folder(output)
    book = np.load(PROJECT / "runs/pilot_20260915_v1/codebook.npz")
    quantizer = PatchQuantizer([book["level0"], book["level1"]])
    model = dict(
        np.load(PROJECT / "runs/clearance_tokens_20260915_v1/residual_model.npz")
    )
    xml = ET.parse(
        RUNTIME / "gear_sonic/data/assets/robot_description/urdf/g1/main.urdf"
    ).getroot()
    limits = {
        j.attrib["name"]: [float(j.find("limit").attrib[k]) for k in ("lower", "upper")]
        for j in xml.findall("joint")
        if j.attrib["type"] == "revolute"
    }
    tasks, records, audits = [], [], []
    for pair in ("arm03", "arm02", "hybrid205"):
        base_tasks, base_records = originals(pair)
        for variant, original in base_records.items():
            reference = np.load(original["reference_path"])
            q, names = reference["qpos"], reference["joint_names"].tolist()
            decoded, _, _ = reconstruct(q, quantizer, model)
            methods = factorial_angles(q, decoded)
            for method in METHODS:
                adapted, audit = execution_reference(
                    q, methods[method], np.array([limits[n] for n in names])
                )
                if method == "continuous":
                    adapted = q.copy()
                key = f"mech_{pair}_{method}_{variant}"
                row = save_reference(
                    folder,
                    key,
                    adapted,
                    names,
                    original,
                    method=method,
                    source_pair_id=pair,
                    original_reference_path=original["reference_path"],
                    execution_adapter=audit,
                    oracle_leg_information="legoracle" in method,
                )
                audits.append(
                    dict(source_pair_id=pair, variant=variant, method=method, **audit)
                )
                for p in range(3):
                    task = deepcopy(
                        next(
                            t
                            for t in base_tasks
                            if t["variant"] == variant
                            and t["condition"] == "removed"
                            and t["perturbation_id"] == p
                        )
                    )
                    task.update(
                        task_id=f"mech_{pair}_{method}_removed_{variant}_p{p}",
                        pair_id=f"mech_{pair}_{method}",
                        source_pair_id=pair,
                        method=method,
                        preflight_only=True,
                    )
                    tasks.append(task)
                    records.append(row)
    dump(folder / "adapter_audit.json", audits)
    materialize(
        tasks,
        records,
        output,
        dict(
            purpose="Factorial temporal smoothing and leg information preflight",
            budget_parent=str(PLAN),
            budget_role="preflight",
            counts_as_preflight=True,
            planned_episodes=144,
            new_preflight_launch=1,
            split="development",
            methods=list(METHODS),
            original_fidelity_required=True,
            oracle_methods_are_compression_results=False,
        ),
    )


def prepare_scenes(preflight, output):
    preflight, output = Path(preflight), Path(output)
    rows = json.loads((preflight / "decoder_qualification.json").read_text())
    reference_tasks = json.loads((preflight / "batch.json").read_text())["tasks"]
    manifest = {
        r["motion_key"]: r
        for r in json.loads((preflight / "manifest.json").read_text())
    }
    priority = ["body9_raw", "body9_smooth", "body9_leg12", "body9_smooth_leg12"]
    selected, tasks, records = [], [], []
    for pair in ("arm03", "hybrid205"):
        qualified = {
            r["method"]: r
            for r in rows
            if r["source_pair_id"] == pair and r["qualified"]
        }
        candidate = next((m for m in priority if m in qualified), None)
        if candidate is None or "continuous" not in qualified:
            continue
        for method in ("continuous", candidate):
            r = qualified[method]
            selected.append(r)
            original_tasks, _ = originals(pair)
            for t in original_tasks:
                template = next(
                    x
                    for x in reference_tasks
                    if x["source_pair_id"] == pair
                    and x["method"] == method
                    and x["variant"] == t["variant"]
                    and x["perturbation_id"] == t["perturbation_id"]
                )
                task = deepcopy(t)
                task.update(
                    task_id=f"{r['pair_id']}_{t['condition']}_{t['variant']}_p{t['perturbation_id']}",
                    pair_id=r["pair_id"],
                    source_pair_id=pair,
                    method=method,
                    representation_test=True,
                )
                tasks.append(task)
                records.append(manifest[template["motion_key"]])
    dump(
        preflight / "main_selection.json",
        dict(fixed_priority=priority, selected=selected, planned_episodes=len(tasks)),
    )
    if not tasks:
        print("No practical method qualified; no main simulation required.")
        return
    previous = main_attempts()
    if len(tasks) > 96 or previous + len(tasks) > 480:
        raise ValueError("Registered main experiment budget exceeded")
    materialize(
        tasks,
        records,
        output,
        dict(
            purpose="Frozen-scene mechanism-informed representation validation",
            budget_role="main",
            budget_parent=str(PLAN),
            main_study_previous_episodes=previous,
            preflight=str(preflight),
            selected=selected,
            frozen_geometry=True,
            split="development",
            representation_cells_are_new_source_groups=False,
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["prepare", "launch", "qualify", "prepare_scenes", "fidelity"],
    )
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    globals()[args.command](*[p.resolve() for p in args.paths])
