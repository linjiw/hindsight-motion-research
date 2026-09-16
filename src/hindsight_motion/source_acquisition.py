"""Deterministic new-source selection followed by repeated teacher qualification."""

import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.spatial.transform import Rotation

from .batch_audit import entry
from .batch_scene import materialize
from .contact_edit import duck_preserving_feet
from .core import load_clip, sha256
from .critical import PROJECT, RUNTIME, dump, edit_motion, launch
from .expansion_scenes import search_beam, prepare as prepare_scenes
from .robust_duck import bend_waist


def describe(q):
    velocity = np.diff(q[:, :3], axis=0) * 50
    rotations = Rotation.from_quat(q[:-1, [4, 5, 6, 3]])
    local = rotations.apply(velocity, inverse=True)
    delta = q[-1, :2] - q[0, :2]
    distance = float(np.linalg.norm(delta))
    path = float(np.linalg.norm(np.diff(q[:, :2], axis=0), axis=1).sum())
    feature = np.r_[
        q[:, 7:19].mean(0),
        q[:, 7:19].std(0),
        q[:, 19:22].mean(0),
        q[:, 19:22].std(0),
        np.median(q[:, 2]),
        q[:, 2].std(),
        local[:, :2].mean(0),
    ]
    eligible = bool(
        0.6 <= distance <= 2.2
        and local[:, 0].mean() > 0.10
        and abs(local[:, 1].mean()) < 0.1
        and q[:, 2].std() < 0.05
        and distance / max(path, 1e-9) > 0.85
    )
    return feature, dict(
        eligible=eligible,
        translation_m=distance,
        path_m=path,
        root_height_std_m=float(q[:, 2].std()),
        mean_body_forward_speed_mps=float(local[:, 0].mean()),
        mean_body_lateral_speed_mps=float(local[:, 1].mean()),
    )


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        KIMODO_G1_JOINT_NAMES,
        qpos_to_sonic_motion_entry,
        sonic_motion_entry_to_qpos,
        save_sonic_motion_file,
    )

    output = Path(output)
    construction = output.with_name(output.name + "_construction")
    construction.mkdir(parents=True, exist_ok=False)
    (construction / "motions").mkdir()
    (construction / "references").mkdir()
    shutil.copy2(
        PROJECT / "configs/decoder_execution_v1.plan.json",
        construction / "registration.json",
    )
    inventory = list(
        csv.DictReader((PROJECT / "runs/pilot_20260915_v1/inventory.csv").open())
    )
    seen = set()
    for folder in (
        "critical_preflight_20260915_v1",
        "critical_preflight_20260915_v2",
        "expansion_preflight_20260915_v1",
    ):
        seen.update(
            r["source_group"]
            for r in json.loads(
                (PROJECT / "runs" / folder / "manifest.json").read_text()
            )
        )
    candidates = []
    rejected = []
    clips = {}
    for r in inventory:
        if r["source_group"] in seen or "walk" not in r["motion_id"].lower():
            continue
        clip = load_clip(r["source_path"], 4, 5)
        q = clip["qpos"]
        if len(q) != 200:
            continue
        f, a = describe(q)
        if a["eligible"]:
            candidates.append(dict(**r, feature=f.tolist(), screen=a))
            clips[r["motion_id"]] = clip
        else:
            rejected.append(
                dict(motion_id=r["motion_id"], source_group=r["source_group"], **a)
            )
    if not candidates:
        raise ValueError("No eligible unseen walking sources")
    values = np.array([r["feature"] for r in candidates])
    scale = np.maximum(values.std(0), 0.05)
    anchors = []
    for carrier in (0, 2):
        q = np.load(
            PROJECT
            / f"runs/expansion_preflight_20260915_v1/references/expand_{carrier:02d}_original.npz"
        )["qpos"]
        anchors.append(describe(q)[0])
    for r in candidates:
        r["similarity_distance"] = float(
            np.min(np.linalg.norm((np.asarray(r["feature"]) - anchors) / scale, axis=1))
        )
    selected = []
    groups = set()
    for r in sorted(
        candidates, key=lambda r: (r["similarity_distance"], r["motion_id"])
    ):
        if r["source_group"] in groups:
            continue
        selected.append(r)
        groups.add(r["source_group"])
        if len(selected) == 6:
            break
    dump(
        construction / "selection.json",
        dict(
            excluded_previously_examined_groups=sorted(seen),
            candidates=candidates,
            rejected=rejected,
            selected=selected,
            rule="Per-source best standardized Euclidean descriptor distance to either of two supported carriers, at most six new groups",
        ),
    )
    names = list(KIMODO_G1_JOINT_NAMES)
    urdf = RUNTIME / "gear_sonic/data/assets/robot_description/urdf/g1/main.urdf"
    body_names = json.loads(
        (
            PROJECT
            / "runs/expansion_preflight_20260915_v1/metrics/episode-contract.json"
        ).read_text()
    )["measured_body_names"]
    tasks = []
    records = []
    trials = []
    for i, source in enumerate(selected):
        if sha256(source["source_path"]) != source["sha256"]:
            raise ValueError("Source hash changed")
        clip = clips[source["motion_id"]]
        q = clip["qpos"].copy()
        q[:, :2] -= q[0, :2].copy()
        q = edit_motion(q, "tuck")[0]
        variants = {"upright": q, "bend": bend_waist(q, names, 0.50)[0]}
        try:
            lowered, _, audit = duck_preserving_feet(q, names, urdf, depth=0.04)
            variants["hybrid"] = bend_waist(lowered, names, 0.35)[0]
            trials.append(
                dict(
                    source_id=source["motion_id"],
                    variant="hybrid",
                    admitted=True,
                    **audit,
                )
            )
        except ValueError as exc:
            trials.append(
                dict(
                    source_id=source["motion_id"],
                    variant="hybrid",
                    admitted=False,
                    reason=str(exc),
                )
            )
        axis = q[-1, :3] - q[0, :3]
        axis[2] = 0
        axis /= np.linalg.norm(axis)
        normal = np.array([-axis[1], axis[0], 0.0])
        for variant, pose in variants.items():
            key = f"source{i:02d}_{variant}"
            reference = construction / "references" / f"{key}.npz"
            np.savez_compressed(reference, qpos=pose, joint_names=names)
            motion = qpos_to_sonic_motion_entry(
                pose, source_fps=50, canonicalize_horizontal_origin=False
            )
            if np.max(abs(pose - sonic_motion_entry_to_qpos(motion))) > 1e-6:
                raise ValueError("Native roundtrip failed")
            path = construction / "motions" / f"{key}.pkl"
            save_sonic_motion_file(path, motion_key=key, motion_entry=motion)
            row = dict(
                motion_key=key,
                carrier_id=i,
                source_id=source["motion_id"],
                source_group=source["source_group"],
                variant=variant,
                split="development",
                source_path=source["source_path"],
                source_sha256=source["sha256"],
                source_start_frame=clip["start_frame"],
                source_end_frame_exclusive=clip["end_frame_exclusive"],
                motion_path=str(path),
                motion_sha256=sha256(path),
                reference_path=str(reference),
                reference_sha256=sha256(reference),
                frames=200,
            )
            for p, offset in enumerate((0.0, -0.015, 0.015)):
                tasks.append(
                    dict(
                        schema="hindsight_critical_traversal_task_v1",
                        task_id=f"source{i:02d}_removed_{variant}_p{p}",
                        pair_id=f"source{i:02d}",
                        family="duck",
                        variant=variant,
                        condition="removed",
                        perturbation_id=p,
                        initial_root_delta_xyz_m=(offset * normal).tolist(),
                        split="development",
                        source_group=source["source_group"],
                        obstacles=[],
                        body_names=body_names,
                        start_xyz=q[0, :3].tolist(),
                        goal_xyz=q[-1, :3].tolist(),
                        portal_center_xyz=q[100, :3].tolist(),
                        passage_axis_xyz=axis.tolist(),
                        goal_tolerance_m=0.25,
                        exit_progress_m=0.20,
                        maximum_undesired_normal_force_n=1.0,
                        control_deadline_steps=200,
                        terminal_requirement="Moving arrival; source qualification only",
                        preflight_only=True,
                        scene_criticality_verified=False,
                    )
                )
                records.append(row)
    dump(construction / "construction_trials.json", trials)
    shutil.copy2(__file__, construction / "preparation_code.py")
    materialize(
        tasks,
        records,
        output,
        dict(
            purpose="Kinematically selected unseen-source beam-traversal preflight",
            budget_parent=str(PROJECT / "configs/decoder_execution_v1.plan.json"),
            new_preflight_launch=2,
            maximum_episodes=54,
            selected_source_groups=sorted(groups),
            split="development",
            held_out_claim=False,
        ),
    )


def qualify(output):
    output = Path(output)
    tasks = json.loads((output / "batch.json").read_text())["tasks"]
    outcomes = {
        r["task_id"]: r
        for r in json.loads((output / "metrics/scene-outcomes.json").read_text())
    }
    rows = []
    for pair in sorted({t["pair_id"] for t in tasks}):
        group = [t for t in tasks if t["pair_id"] == pair]
        common = []
        for p in range(3):
            entries = [
                entry(
                    dict(np.load(output / "metrics" / f"episode-{t['motion_key']}.npz"))
                )
                for t in group
                if t["perturbation_id"] == p
            ]
            difference = max(
                float(np.max(abs(e[k] - entries[0][k])))
                for e in entries
                for k in entries[0]
            )
            common.append(difference)
        counts = {
            v: sum(
                outcomes[t["task_id"]]["scene_passage_verified"]
                for t in group
                if t["variant"] == v
            )
            for v in {t["variant"] for t in group}
        }
        rows.append(
            dict(
                pair_id=pair,
                source_group=group[0]["source_group"],
                successes=counts,
                entry_max_error=max(common),
                qualified_variants=[
                    v
                    for v in ("hybrid", "bend")
                    if counts.get(v) == 3
                    and counts["upright"] == 3
                    and max(common) <= 1e-5
                ],
            )
        )
    dump(output / "source_qualification.json", rows)
    print(json.dumps(rows, indent=2))


def propose(preflight, output):
    preflight = Path(preflight)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tasks = json.loads((preflight / "batch.json").read_text())["tasks"]
    manifest = {
        r["motion_key"]: r
        for r in json.loads((preflight / "manifest.json").read_text())
    }
    quals = json.loads((preflight / "source_qualification.json").read_text())
    proxies = json.loads(
        (
            PROJECT
            / "runs/critical_preflight_20260915_v2/native_collision_proxies.json"
        ).read_text()
    )
    dump(
        output / "registration.json",
        dict(
            preflight=str(preflight),
            budget_parent=str(PROJECT / "configs/decoder_execution_v1.plan.json"),
            maximum_selected_source_groups=2,
            selection="Same all-repeat beam gate; best worst-side slack per source, then top two sources",
            geometry_only=True,
            split="development",
        ),
    )
    passing = []
    for row in quals:
        for variant in row["qualified_variants"]:
            group = [t for t in tasks if t["pair_id"] == row["pair_id"]]
            index = {(t["variant"], t["perturbation_id"]): t for t in group}
            paths = [
                tuple(
                    preflight / "metrics" / f"episode-{index[v,p]['motion_key']}.npz"
                    for v in (variant, "upright")
                )
                for p in range(3)
            ]
            result = search_beam(
                preflight, proxies, *paths[0], refine=True, extra_pairs=paths[1:]
            )
            pair = f"{row['pair_id']}_{variant}"
            records = {
                v: deepcopy(manifest[index[native_v, 0]["motion_key"]])
                for v, native_v in [("duck", variant), ("upright", "upright")]
            }
            for v, r in records.items():
                r["source_variant"] = r["variant"]
                r["variant"] = v
            result.update(
                pair_id=pair,
                family="duck",
                source_group=row["source_group"],
                records=records,
            )
            dump(output / f"{pair}.json", result)
            if result["selected"] is not None:
                passing.append(result)
            print(
                json.dumps(
                    dict(
                        pair=pair,
                        admitted=sum(p["admitted"] for p in result["proposals"]),
                        selected=result["selected"],
                    )
                ),
                flush=True,
            )
    selected = []
    groups = set()
    for r in sorted(passing, key=lambda r: (-r["selected"]["score"], r["pair_id"])):
        if r["source_group"] in groups:
            continue
        groups.add(r["source_group"])
        selected.append(r["pair_id"])
        if len(selected) == 2:
            break
    dump(output / "accepted_pairs.json", selected)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "command", choices=["prepare", "launch", "qualify", "propose", "prepare_scenes"]
    )
    p.add_argument("paths", nargs="+", type=Path)
    a = p.parse_args()
    globals()[a.command](*[x.resolve() for x in a.paths])
