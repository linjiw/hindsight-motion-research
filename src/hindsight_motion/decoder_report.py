"""Audit decoded execution without inflating independent motion/source coverage."""

import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .batch_audit import entry
from .core import sha256
from .critical import PROJECT, RUNTIME, dump
from .critical_present import HTML, box_vertices
from .decoder_execution import METHODS, originals
from .scene_evidence import score_episode

PREFLIGHT = PROJECT / "runs/decoder_preflight_20260915_v1"
MAIN = PROJECT / "runs/decoder_interventions_20260915_v1"
SOURCE = PROJECT / "runs/new_source_preflight_20260915_v1"
OUTPUT = PROJECT / "runs/decoder_validation_20260915_v1"
CONDITIONS = ("critical", "relaxed", "removed", "displaced")


def read(path):
    return json.loads(Path(path).read_text())


def failure_summary(tasks, outcomes, key):
    lookup = {t["task_id"]: t for t in tasks}
    rows = []
    for value in sorted({lookup[r["task_id"]][key] for r in outcomes}):
        group = [r for r in outcomes if lookup[r["task_id"]][key] == value]
        rows.append(
            dict(
                group=value,
                episodes=len(group),
                passes=sum(r["scene_passage_verified"] for r in group),
                failures_by_check={
                    k: sum(not r["checks"][k] for r in group)
                    for k in group[0]["checks"]
                },
                terminated=sum(r["terminated"] for r in group),
                body_error_range_m=[
                    min(r["mean_body_error_m"] for r in group),
                    max(r["mean_body_error_m"] for r in group),
                ],
                root_error_range_m=[
                    min(r["max_root_xy_error_m"] for r in group),
                    max(r["max_root_xy_error_m"] for r in group),
                ],
            )
        )
    return rows


def audit_preflight(run):
    """Recompute task outcomes and check every exported observation/target view."""
    tasks = read(run / "batch.json")["tasks"]
    native = {r["motion_key"]: r for r in read(run / "metrics/preflight-outcomes.json")}
    outcomes = {r["task_id"]: r for r in read(run / "metrics/scene-outcomes.json")}
    for t in tasks:
        folder = run / "metrics" / t["task_id"]
        episode = dict(np.load(run / "metrics" / f"episode-{t['motion_key']}.npz"))
        force = np.load(folder / "environment-contacts.npz")["normal_force_w"]
        result = score_episode(t, episode, native[t["motion_key"]], force)
        assert result["checks"] == outcomes[t["task_id"]]["checks"]
        actor = dict(np.load(folder / "actor-view.npz"))
        teacher = dict(np.load(folder / "teacher-view.npz"))
        targets = dict(np.load(folder / "target-view.npz"))
        assert set(actor) == {
            "proprio",
            "scene_tokens",
            "scene_mask",
            "goal_local_xyz",
            "goal_tolerance_m",
            "complete_known_map",
        }
        assert actor["proprio"].shape == (200, 930)
        assert teacher["future_reference"].shape == (200, 640)
        assert targets["teacher_motor_token"].shape == (200, 64)
        assert targets["teacher_action"].shape == (200, 29)
        assert all(
            np.isfinite(x).all()
            for view in (actor, teacher, targets)
            for x in view.values()
        )
        assert np.all(actor["scene_mask"].sum(1) == 0)
        np.testing.assert_array_equal(
            targets["motor_imitation_support"],
            episode["before_first_native_failure"] & result["scene_passage_verified"],
        )
    isolation = read(run / "metrics/isolation-audit.json")
    assert isolation["maximum_foreign_obstacle_force_n"] == 0
    assert (
        isolation["origins_match_authored_scenes"]
        and isolation["motion_assignment_matches"]
    )
    return dict(
        run=str(run),
        episodes=len(tasks),
        outcomes_recomputed=True,
        views_audited=True,
        isolation=isolation,
    )


def reference_diagnostics(preflight=PREFLIGHT, output=OUTPUT, methods=METHODS):
    manifest = read(preflight / "manifest.json")
    originals_by_variant = {}
    for row in manifest:
        if row["method"] == "continuous":
            originals_by_variant[row["source_pair_id"], row["variant"]] = np.load(
                row["reference_path"]
            )["qpos"]
    rows = []
    seen = set()
    for r in manifest:
        key = (r["source_pair_id"], r["variant"], r["method"])
        if key in seen:
            continue
        seen.add(key)
        q = np.load(r["reference_path"])["qpos"]
        original = originals_by_variant[key[:2]]
        # Start at 1.2 s: exclude the entry scaffold from reconstruction diagnostics.
        delta = q[60:, 7:] - original[60:, 7:]
        steps = np.diff(q[60:, 7:], axis=0)
        # Old 5-frame RVQ patches meet before frames 65, 70, ... after scaffold.
        boundary = np.arange(61, len(q)) % 5 == 0
        rows.append(
            dict(
                source_pair_id=key[0],
                variant=key[1],
                method=key[2],
                suffix_joint_rmse_rad=float(np.sqrt(np.mean(delta**2))),
                suffix_leg_rmse_rad=float(np.sqrt(np.mean(delta[:, :12] ** 2))),
                max_joint_step_rad=float(abs(steps).max()),
                boundary_step_rms_rad=float(np.sqrt(np.mean(steps[boundary] ** 2))),
                within_patch_step_rms_rad=float(
                    np.sqrt(np.mean(steps[~boundary] ** 2))
                ),
                root_unchanged=bool(np.array_equal(q[:, :7], original[:, :7])),
            )
        )
    assert all(r["root_unchanged"] for r in rows)
    summary = []
    for method in methods:
        group = [r for r in rows if r["method"] == method]
        summary.append(
            dict(
                method=method,
                **{
                    k: float(np.mean([r[k] for r in group]))
                    for k in (
                        "suffix_joint_rmse_rad",
                        "suffix_leg_rmse_rad",
                        "boundary_step_rms_rad",
                        "within_patch_step_rms_rad",
                    )
                },
                maximum_joint_step_rad=max(r["max_joint_step_rad"] for r in group),
            )
        )
    result = dict(
        exploratory=True,
        causal_identification=False,
        interval="1.2 s through end",
        rows=rows,
        summary=summary,
    )
    dump(output / "reference_diagnostics.json", result)
    return result


def audit_main(main=MAIN, preflight=PREFLIGHT, output=OUTPUT):
    tasks = read(main / "batch.json")["tasks"]
    episodes = {
        t["task_id"]: dict(np.load(main / "metrics" / f"episode-{t['motion_key']}.npz"))
        for t in tasks
    }
    outcomes = {r["task_id"]: r for r in read(main / "metrics/scene-outcomes.json")}
    fidelity = {r["task_id"]: r for r in read(main / "original_fidelity.json")}
    common = []
    for pair in sorted({t["source_pair_id"] for t in tasks}):
        original_tasks, _ = originals(pair)
        for t in [t for t in tasks if t["source_pair_id"] == pair]:
            base = next(
                b
                for b in original_tasks
                if all(
                    b[k] == t[k] for k in ("condition", "variant", "perturbation_id")
                )
            )
            for field in (
                "obstacles",
                "initial_root_delta_xyz_m",
                "goal_xyz",
                "portal_center_xyz",
                "passage_axis_xyz",
                "goal_tolerance_m",
                "exit_progress_m",
                "maximum_undesired_normal_force_n",
            ):
                assert t[field] == base[field], (t["task_id"], field)
        for perturbation in range(3):
            group = [
                t
                for t in tasks
                if t["source_pair_id"] == pair and t["perturbation_id"] == perturbation
            ]
            entries = [entry(episodes[t["task_id"]]) for t in group]
            differences = {
                k: max(float(abs(e[k] - entries[0][k]).max()) for e in entries)
                for k in entries[0]
            }
            assert max(differences.values()) <= 1e-5
            common.append(
                dict(
                    source_pair_id=pair,
                    perturbation_id=perturbation,
                    differences=differences,
                )
            )
    # Confirm that continuous reference coordinates are identical across preflight and main batching.
    pre = read(preflight / "batch.json")["tasks"]
    reference_errors = []
    for t in tasks:
        if t["method"] != "continuous":
            continue
        p = next(
            p
            for p in pre
            if p["method"] == "continuous"
            and all(
                p[k] == t[k] for k in ("source_pair_id", "variant", "perturbation_id")
            )
        )
        ref = np.load(preflight / "metrics" / f"episode-{p['motion_key']}.npz")[
            "reference_body_pos"
        ]
        reference_errors.append(
            float(abs(ref - episodes[t["task_id"]]["reference_body_pos"]).max())
        )
    assert max(reference_errors) <= 1e-5
    panels = []
    for panel in read(main / "paired_relation_audit.json"):
        group = [
            t
            for t in tasks
            if t["pair_id"] == panel["pair_id"]
            and t["perturbation_id"] == panel["perturbation_id"]
        ]
        negative = "wide" if panel["family"] == "arm_tuck" else "upright"
        preservation_tasks = [
            t for t in group if (t["condition"], t["variant"]) != ("critical", negative)
        ]
        preserved = all(
            fidelity[t["task_id"]]["original_motion_fidelity_pass"]
            for t in preservation_tasks
        )
        panels.append(
            dict(
                **panel,
                source_pair_id=group[0]["source_pair_id"],
                method=group[0]["method"],
                original_motion_preserved_in_positive_and_controls=preserved,
                representation_relation_verified=bool(panel["verified"] and preserved),
            )
        )
    dump(output / "representation_panels.json", panels)
    audit = dict(
        frozen_geometry_and_task_parameters=True,
        common_entry_across_methods_and_conditions=common,
        maximum_continuous_reference_difference_m=max(reference_errors),
        original_fidelity_required_for="Intended critical traversal and all controls; excluded for collision contrast",
        original_fidelity_is_teacher_only=True,
        main_data_audit=read(main / "aggregate.json"),
        native_pairs_field_means="Representation cells, not independent source pairs",
        canonical_base_pairs=len({t["source_pair_id"] for t in tasks}),
        source_groups=len({t["source_group"] for t in tasks}),
        isolation=read(main / "metrics/isolation-audit.json"),
    )
    assert audit["isolation"]["maximum_foreign_obstacle_force_n"] == 0
    dump(output / "execution_audit.json", audit)
    index = []
    (output / "support").mkdir(exist_ok=True)
    for t in tasks:
        folder = main / "metrics" / t["task_id"]
        paths = {k: folder / f"{k}-view.npz" for k in ("actor", "teacher", "target")}
        paths.update(
            raw_episode=main / "metrics" / f"episode-{t['motion_key']}.npz",
            contact=folder / "environment-contacts.npz",
            task=main / "tasks" / f"{t['task_id']}.json",
            outcome=folder / "scene-outcome.json",
        )
        native_support = np.load(paths["target"])["motor_imitation_support"]
        support = (
            native_support & fidelity[t["task_id"]]["original_motion_fidelity_pass"]
        )
        support_path = output / "support" / f"{t['task_id']}.npz"
        np.savez_compressed(
            support_path, original_motion_preserving_imitation_support=support
        )
        paths["representation_support"] = support_path
        panel = next(
            p
            for p in panels
            if p["pair_id"] == t["pair_id"]
            and p["perturbation_id"] == t["perturbation_id"]
        )
        index.append(
            dict(
                episode_id=t["task_id"],
                experiment_role="representation_validation",
                independent_acquisition=False,
                canonical_source_pair_id=t["source_pair_id"],
                method=t["method"],
                source_group=t["source_group"],
                condition=t["condition"],
                variant=t["variant"],
                perturbation_id=t["perturbation_id"],
                split="development",
                scene_passage_verified=outcomes[t["task_id"]]["scene_passage_verified"],
                representation_panel_verified=panel["representation_relation_verified"],
                original_motion_fidelity_pass=fidelity[t["task_id"]][
                    "original_motion_fidelity_pass"
                ],
                supported_motor_rows=int(support.sum()),
                control_rows=len(support),
                files={
                    k: dict(path=str(p), sha256=sha256(p)) for k, p in paths.items()
                },
            )
        )
    (output / "development_representation_episodes.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in index)
    )
    dump(
        output / "dataset-contract.json",
        dict(
            schema="decoded_motion_execution_validation_v1",
            core_acquisition_index=str(
                PROJECT / "runs/critical_dataset_20260915_v3/development_episodes.jsonl"
            ),
            separate_index_reason="Repeated/decoded descendants of existing motion pairs, not independent new tasks",
            actor_fields=[
                "proprio",
                "scene_tokens",
                "scene_mask",
                "goal_local_xyz",
                "goal_tolerance_m",
                "complete_known_map",
            ],
            actor_excludes=[
                "method",
                "source_pair_id",
                "original_fidelity",
                "future_reference",
                "motion_codes",
                "relation_labels",
            ],
            training_support="Native passage support AND original-reference fidelity; panel relation support is separate",
            root_side_channel_bps=11200,
            entry_scaffold="Original motion until 0.6 s, blend until 1.2 s; teacher future reference",
            motion_codes_are_native_motor_tokens=False,
            split="development",
            student_trained=False,
        ),
    )
    return tasks, episodes, outcomes, panels, index


def figures(qualification, panels, diagnostics):
    fig, axes = plt.subplots(
        1, 3, figsize=(16, 5.8), gridspec_kw={"width_ratios": [1.1, 1, 1.25]}
    )
    cases = ("arm03", "arm02", "hybrid205")
    matrix = np.array(
        [
            [
                sum(
                    next(
                        r["successes"].values()
                        for r in qualification
                        if r["source_pair_id"] == c and r["method"] == m
                    )
                )
                for c in cases
            ]
            for m in METHODS
        ]
    )
    axes[0].imshow(matrix, vmin=0, vmax=6, cmap="YlGn", aspect="auto")
    for (i, j), value in np.ndenumerate(matrix):
        axes[0].text(j, i, f"{value}/6", ha="center", va="center")
    axes[0].set(
        xticks=range(3),
        xticklabels=["Arm 205", "Arm 9", "Beam 205"],
        yticks=range(5),
        yticklabels=METHODS,
        title="A. Empty-scene qualification\nNative passage AND original-motion fidelity",
    )
    cells = [
        "dec_arm03_continuous",
        "dec_arm03_linear29",
        "dec_hybrid205_continuous",
        "dec_hybrid205_linear29",
    ]
    counts = [
        sum(r["representation_relation_verified"] for r in panels if r["pair_id"] == c)
        for c in cells
    ]
    axes[1].barh(range(4), counts, color=["#587890", "#168b72"] * 2)
    axes[1].set(
        yticks=range(4),
        yticklabels=[
            "Arm · continuous",
            "Arm · Linear29",
            "Beam · continuous",
            "Beam · Linear29",
        ],
        xlim=(0, 3.5),
        xticks=range(4),
        xlabel="Verified panels / 3",
        title="B. Frozen-scene preservation\n96 executions; same KIT/205 source",
    )
    axes[1].invert_yaxis()
    x = np.arange(5)
    axes[2].bar(
        x - 0.17,
        [r["boundary_step_rms_rad"] for r in diagnostics["summary"]],
        width=0.34,
        label="5-frame boundary",
        color="#c37e4a",
    )
    axes[2].bar(
        x + 0.17,
        [r["within_patch_step_rms_rad"] for r in diagnostics["summary"]],
        width=0.34,
        label="Within patch",
        color="#587890",
    )
    axes[2].set(
        xticks=x,
        xticklabels=["Continuous", "RVQ", "RVQ\nbody9", "RVQ\nPCA9", "Linear29"],
        ylabel="Mean per-reference joint-step RMS (rad)",
        title="C. Executed-reference discontinuities\nExploratory diagnostic after 1.2 s",
    )
    axes[2].legend(fontsize=8)
    fig.suptitle(
        "Decoded motion must preserve execution and obstacle relevance", fontsize=17
    )
    fig.text(
        0.03,
        0.025,
        "90 decoder preflights + 96 frozen-scene trials. Original entry scaffold and full-rate root retained; these are not student-policy tests.\nAdditional source qualification: 0/24 across three groups; no new scenes promoted. All results are development evidence.",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.12, 1, 0.92])
    for suffix in ("png", "pdf"):
        fig.savefig(PROJECT / f"artifacts/decoder_execution.{suffix}", dpi=170)
    plt.close(fig)


def viewer(tasks, episodes, outcomes, panels):
    dataset = []
    for pair in dict.fromkeys(t["pair_id"] for t in tasks):
        group = [t for t in tasks if t["pair_id"] == pair]
        first = group[0]
        positive, negative = (
            ("tuck", "wide") if first["family"] == "arm_tuck" else ("duck", "upright")
        )
        verified = sum(
            p["representation_relation_verified"]
            for p in panels
            if p["pair_id"] == pair
        )
        label = f"{first['source_pair_id']} · {first['method']} · panels {verified}/3"
        for condition in CONDITIONS:
            for p in range(3):
                a, b = [
                    next(
                        t
                        for t in group
                        if t["condition"] == condition
                        and t["perturbation_id"] == p
                        and t["variant"] == v
                    )
                    for v in (positive, negative)
                ]
                dataset.append(
                    dict(
                        pair=pair,
                        pair_label=label,
                        labels=dict(
                            tuck=positive.capitalize(), wide=negative.capitalize()
                        ),
                        condition=condition,
                        perturbation=p,
                        tuck=episodes[a["task_id"]]["body_xyz"][::2].round(5).tolist(),
                        wide=episodes[b["task_id"]]["body_xyz"][::2].round(5).tolist(),
                        boxes=[
                            box_vertices(o).round(5).tolist() for o in a["obstacles"]
                        ],
                        center=a["portal_center_xyz"],
                        outcomes=dict(
                            tuck=outcomes[a["task_id"]], wide=outcomes[b["task_id"]]
                        ),
                    )
                )
    names = tasks[0]["body_names"]
    xml = ET.parse(
        RUNTIME / "gear_sonic/data/assets/robot_description/urdf/g1/main.urdf"
    ).getroot()
    parent = {
        j.find("child").attrib["link"]: j.find("parent").attrib["link"]
        for j in xml.findall("joint")
    }
    parents = []
    for name in names:
        p = parent.get(name)
        while p is not None and p not in names:
            p = parent.get(p)
        parents.append(names.index(p) if p in names else 0)
    html = HTML.replace(
        "Does the obstacle make the arm motion useful?",
        "Can decoded motion preserve a critical traversal?",
    )
    html = html.replace(
        "One mocap carrier, two executable arm continuations, four scene interventions.",
        "96 frozen-scene executions: two existing KIT/205 pairs × continuous/Linear29 × four interventions × three offsets.",
    )
    html = html.replace(
        "Green: tucked arms. Orange: wide arms.",
        "Green: intended traversal. Orange: contrast continuation.",
    )
    html = html.replace(
        '<div class="row"><label>Scene',
        '<div class="row"><label>Representation cell <select id="pair"></select></label><label>Scene',
    )
    html = html.replace(
        "['critical','relaxed','removed','displaced'].forEach",
        "[...new Map(DATA.map(d=>[d.pair,d.pair_label]))].forEach(([k,v])=>$('pair').add(new Option(v,k)));\n['critical','relaxed','removed','displaced'].forEach",
    )
    html = html.replace(
        "d.condition===$('scene').value&&",
        "d.pair===$('pair').value&&d.condition===$('scene').value&&",
    )
    html = html.replace("${k==='tuck'?'Tucked':'Wide'} arms", "${current.labels[k]}")
    html = html.replace(
        "$('scene').onchange=select;",
        "$('pair').onchange=select;$('scene').onchange=select;",
    )
    html = html.replace(
        "function select(){",
        "$('pair').value=new URL(location.href).searchParams.get('pair')||'dec_hybrid205_linear29';\nfunction select(){",
    )
    # Keep the evidence summary self-contained; no external JavaScript or network assets.
    header = """<div class="card"><b>What passed</b> · Continuous and Linear29: 12/12 complete panels; all intended traversals and controls pass.<br>
<b>What failed</b> · RVQ, RVQ+body9 and RVQ+PCA9: 0/54 empty-scene qualifications. Linear29: 17/18; arm02 misses one.<br>
<b>Coverage limit</b> · Three additional source groups: 0/24 preflights, no new scene pairs. These four representation cells reuse two existing KIT/205 pairs.<br>
<span class="muted">Common original entry until 0.6 s, transition until 1.2 s, then decoded joints. Full-rate root retained. All development; no student trained.</span></div>"""
    html = html.replace(
        '<div class="row"><label>Representation',
        header + '<div class="row"><label>Representation',
    )
    html = html.replace("__DATA__", json.dumps(dataset)).replace(
        "__PARENTS__", json.dumps(parents)
    )
    (PROJECT / "artifacts/decoder_viewer.html").write_text(html)


def report():
    OUTPUT.mkdir(exist_ok=True)
    qualification = read(PREFLIGHT / "decoder_qualification.json")
    preflight_audits = [audit_preflight(p) for p in (PREFLIGHT, SOURCE)]
    dump(OUTPUT / "preflight_data_audit.json", preflight_audits)
    tasks, episodes, outcomes, panels, index = audit_main()
    diagnostics = reference_diagnostics()
    attempts = []
    for run, role in [
        (PREFLIGHT, "decoder_preflight"),
        (SOURCE, "source_preflight"),
        (MAIN, "representation_intervention"),
    ]:
        lookup = {t["task_id"]: t for t in read(run / "batch.json")["tasks"]}
        for o in read(run / "metrics/scene-outcomes.json"):
            t = lookup[o["task_id"]]
            attempts.append(
                dict(
                    role=role,
                    run=str(run),
                    task_id=t["task_id"],
                    pair_id=t["pair_id"],
                    method=t.get("method", "continuous"),
                    source_group=t["source_group"],
                    condition=t["condition"],
                    variant=t["variant"],
                    perturbation_id=t["perturbation_id"],
                    passed=o["scene_passage_verified"],
                    terminated=o["terminated"],
                    body_error_m=o["mean_body_error_m"],
                    root_error_m=o["max_root_xy_error_m"],
                    goal_error_m=o["final_goal_distance_m"],
                )
            )
    with (OUTPUT / "all_native_attempts.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(attempts[0]))
        writer.writeheader()
        writer.writerows(attempts)
    cells = []
    for pair in dict.fromkeys(t["pair_id"] for t in tasks):
        group = [t for t in tasks if t["pair_id"] == pair]
        positive, negative = (
            ("tuck", "wide")
            if group[0]["family"] == "arm_tuck"
            else ("duck", "upright")
        )
        cells.append(
            dict(
                pair_id=pair,
                canonical_source_pair_id=group[0]["source_pair_id"],
                method=group[0]["method"],
                outcomes={
                    c: {
                        v: sum(
                            outcomes[t["task_id"]]["scene_passage_verified"]
                            for t in group
                            if t["condition"] == c and t["variant"] == v
                        )
                        for v in (positive, negative)
                    }
                    for c in CONDITIONS
                },
                verified_panels=sum(
                    p["representation_relation_verified"]
                    for p in panels
                    if p["pair_id"] == pair
                ),
            )
        )
    summary = dict(
        new_preflight_episodes=114,
        new_preflight_launches=2,
        new_representation_main_episodes=96,
        new_acquisition_main_episodes=0,
        cumulative_preflight_episodes=248,
        cumulative_main_episodes=216,
        cumulative_native_episodes=464,
        main_remaining_budget=264,
        canonical_acquisition_motion_pairs=5,
        canonical_acquisition_source_groups=3,
        fully_verified_canonical_pairs=3,
        canonical_verified_panels=10,
        canonical_total_panels=15,
        representation_cells=4,
        representation_base_pairs=2,
        representation_source_groups=1,
        representation_verified_panels=sum(
            p["representation_relation_verified"] for p in panels
        ),
        representation_total_panels=len(panels),
        representation_control_rows=sum(r["control_rows"] for r in index),
        representation_supported_motor_rows=sum(
            r["supported_motor_rows"] for r in index
        ),
        decoder_preflight=qualification,
        representation_cells_results=cells,
        decoder_failures=failure_summary(
            read(PREFLIGHT / "batch.json")["tasks"],
            read(PREFLIGHT / "metrics/scene-outcomes.json"),
            "method",
        ),
        source_qualification=read(SOURCE / "source_qualification.json"),
        source_failures=failure_summary(
            read(SOURCE / "batch.json")["tasks"],
            read(SOURCE / "metrics/scene-outcomes.json"),
            "source_group",
        ),
        split="development",
        held_out_generalization=False,
        student_trained=False,
    )
    dump(OUTPUT / "aggregate.json", summary)
    figures(qualification, panels, diagnostics)
    viewer(tasks, episodes, outcomes, panels)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    report()
