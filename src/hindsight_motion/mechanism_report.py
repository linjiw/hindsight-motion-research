"""Execution, geometry, carrier coverage and attempt accounting for token mechanisms."""

import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .core import sha256
from .critical import PROJECT, RUNTIME, dump
from .critical_present import HTML, box_vertices
from .decoder_report import (
    audit_main,
    audit_preflight,
    failure_summary,
    read,
    reference_diagnostics,
)
from .mechanism import METHODS

PREFLIGHT = PROJECT / "runs/token_mechanism_preflight_20260915_v2"
FAILED = PROJECT / "runs/token_mechanism_preflight_20260915_v1"
CARRIERS = PROJECT / "runs/carrier_screen_20260915_v1"
MAIN = PROJECT / "runs/token_mechanism_interventions_20260915_v1"
GEOMETRY = PROJECT / "runs/token_mechanism_geometry_20260915_v1"
OUTPUT = PROJECT / "runs/token_mechanism_validation_20260915_v1"
LABELS = dict(
    continuous="Continuous",
    linear29="Linear29",
    body9_raw="Body9 · raw",
    body9_smooth="Body9 · smooth",
    body9_legoracle="Body9 · original legs",
    body9_smooth_legoracle="Smooth · original legs",
    body9_leg12="Body9 · 10 Hz legs",
    body9_smooth_leg12="Smooth · 10 Hz legs",
)


def paired_effects(tasks, scores, outcomes):
    index = {
        (t["source_pair_id"], t["variant"], t["perturbation_id"], t["method"]): t[
            "task_id"
        ]
        for t in tasks
    }
    contrasts = [
        ("smooth_with_decoded_legs", "body9_raw", "body9_smooth"),
        ("original_legs_without_smoothing", "body9_raw", "body9_legoracle"),
        ("original_legs_with_smoothing", "body9_smooth", "body9_smooth_legoracle"),
        ("smooth_with_original_legs", "body9_legoracle", "body9_smooth_legoracle"),
        ("leg12_without_smoothing", "body9_raw", "body9_leg12"),
        ("leg12_with_smoothing", "body9_smooth", "body9_smooth_leg12"),
    ]
    rows = []
    for pair, variant, p in sorted({k[:3] for k in index}):
        for contrast, a, b in contrasts:
            first, second = index[pair, variant, p, a], index[pair, variant, p, b]
            sa, sb = scores[first], scores[second]
            pa = (
                outcomes[first]["scene_passage_verified"]
                and sa["original_motion_fidelity_pass"]
            )
            pb = (
                outcomes[second]["scene_passage_verified"]
                and sb["original_motion_fidelity_pass"]
            )
            rows.append(
                dict(
                    source_pair_id=pair,
                    variant=variant,
                    perturbation_id=p,
                    contrast=contrast,
                    before_pass=pa,
                    after_pass=pb,
                    rescued=bool(pb and not pa),
                    regressed=bool(pa and not pb),
                    original_body_error_change_m=sb["original_body_mean_error_m"]
                    - sa["original_body_mean_error_m"],
                )
            )
    summary = []
    for contrast, _, _ in contrasts:
        group = [r for r in rows if r["contrast"] == contrast]
        summary.append(
            dict(
                contrast=contrast,
                paired_trials=len(group),
                rescued=sum(r["rescued"] for r in group),
                regressed=sum(r["regressed"] for r in group),
                mean_original_body_error_change_m=float(
                    np.mean([r["original_body_error_change_m"] for r in group])
                ),
                per_pair={
                    pair: sum(
                        r["rescued"] for r in group if r["source_pair_id"] == pair
                    )
                    for pair in ("arm03", "arm02", "hybrid205")
                },
            )
        )
    result = dict(
        rows=rows,
        summary=summary,
        independence="Three edited pairs, two source groups; paired perturbations and shared carriers are correlated",
        scope="Effects of the implemented smoothing and leg replacement; not an isolated seam-only causal intervention",
    )
    dump(OUTPUT / "paired_mechanism_effects.json", result)
    return result


def render(data, names, path, title, subtitle, summary, conditions):
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
    html = HTML.replace("Does the obstacle make the arm motion useful?", title)
    html = html.replace(
        "One mocap carrier, two executable arm continuations, four scene interventions.",
        subtitle,
    )
    html = html.replace(
        "Green: tucked arms. Orange: wide arms.",
        "Colors and labels identify the two executed continuations below.",
    )
    html = html.replace(
        '<div class="row"><label>Scene',
        summary
        + '<div class="row"><label>Case <select id="pair"></select></label><label>Condition',
    )
    html = html.replace(
        "['critical','relaxed','removed','displaced'].forEach",
        "[...new Map(DATA.map(d=>[d.pair,d.pair_label]))].forEach(([k,v])=>$('pair').add(new Option(v,k)));\n"
        + json.dumps(conditions)
        + ".forEach",
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
        f"$('pair').value={json.dumps(data[-1]['pair'])};\nfunction select(){{",
    )
    html = html.replace("__DATA__", json.dumps(data)).replace(
        "__PARENTS__", json.dumps(parents)
    )
    Path(path).write_text(html)


def viewers(summary, main_results):
    tasks = read(PREFLIGHT / "batch.json")["tasks"]
    outcomes = {
        r["task_id"]: r for r in read(PREFLIGHT / "metrics/scene-outcomes.json")
    }
    episodes = {
        t["task_id"]: np.load(PREFLIGHT / "metrics" / f"episode-{t['motion_key']}.npz")[
            "body_xyz"
        ][::2]
        .round(5)
        .tolist()
        for t in tasks
    }
    data = []
    for t in tasks:
        baseline = next(
            b
            for b in tasks
            if b["method"] == "continuous"
            and all(
                b[k] == t[k] for k in ("source_pair_id", "variant", "perturbation_id")
            )
        )
        data.append(
            dict(
                pair=f"{t['source_pair_id']}_{t['variant']}",
                pair_label=f"{t['source_pair_id']} · {t['variant']}",
                labels=dict(tuck="Continuous", wide=LABELS[t["method"]]),
                condition=LABELS[t["method"]],
                perturbation=t["perturbation_id"],
                tuck=episodes[baseline["task_id"]],
                wide=episodes[t["task_id"]],
                boxes=[],
                center=t["portal_center_xyz"],
                outcomes=dict(
                    tuck=outcomes[baseline["task_id"]], wide=outcomes[t["task_id"]]
                ),
            )
        )
    counts = " · ".join(
        f"{LABELS[r['method']]}: {r['joint_passes']}/18" for r in summary["methods"]
    )
    note = f'<div class="card">{counts}<br><span class="muted">Original entry and root retained. Original-leg methods are privileged diagnostics. All development; no student trained.</span></div>'
    render(
        data,
        tasks[0]["body_names"],
        PROJECT / "artifacts/mechanism_preflight_viewer.html",
        "Which reconstruction change restores tracking?",
        "144 recorded mechanism trials; continuous reference versus selected method.",
        note,
        [LABELS[m] for m in METHODS],
    )
    if main_results is None:
        return
    tasks, episodes, outcomes, panels, _ = main_results
    data = []
    for pair in dict.fromkeys(t["pair_id"] for t in tasks):
        group = [t for t in tasks if t["pair_id"] == pair]
        positive, negative = (
            ("tuck", "wide")
            if group[0]["family"] == "arm_tuck"
            else ("duck", "upright")
        )
        count = sum(
            p["representation_relation_verified"]
            for p in panels
            if p["pair_id"] == pair
        )
        for condition in ("critical", "relaxed", "removed", "displaced"):
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
                data.append(
                    dict(
                        pair=pair,
                        pair_label=f"{a['source_pair_id']} · {LABELS[a['method']]} · {count}/3 panels",
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
    note = f"""<div class="card"><b>{summary['verified_representation_panels']}/{summary['representation_panels']} complete panels</b> · Frozen geometry, shared entry, original-motion fidelity audited.<br>
    New carrier screen: {summary['acquisition_ready_carriers']}/{summary['screened_carrier_groups']} groups pass all original + tuck prechecks. These are not yet new obstacle-qualified pairs.<br>
    <a style="color:#63ddba" href="mechanism_preflight_viewer.html">Inspect all decoder preflights</a> · <span class="muted">All development. Full-rate root and original entry retained; no student trained.</span></div>"""
    render(
        data,
        tasks[0]["body_names"],
        PROJECT / "artifacts/mechanism_viewer.html",
        "Does the repaired representation preserve critical traversal?",
        f"{len(tasks)} frozen-scene executions on existing KIT/205 pairs.",
        note,
        ["critical", "relaxed", "removed", "displaced"],
    )


def figure(summary, geometry, effects):
    fig, axes = plt.subplots(
        1, 3, figsize=(17, 6), gridspec_kw={"width_ratios": [1.2, 1.2, 1]}
    )
    q = summary["qualification"]
    cases = ("arm03", "arm02", "hybrid205")
    matrix = np.array(
        [
            [
                sum(
                    next(
                        r["successes"].values()
                        for r in q
                        if r["source_pair_id"] == p and r["method"] == m
                    )
                )
                for p in cases
            ]
            for m in METHODS
        ]
    )
    axes[0].imshow(matrix, vmin=0, vmax=6, cmap="YlGn", aspect="auto")
    for (i, j), v in np.ndenumerate(matrix):
        axes[0].text(
            j,
            i,
            f"{v}/6",
            ha="center",
            va="center",
            color="white" if v >= 4 else "black",
        )
    axes[0].set(
        xticks=range(3),
        xticklabels=["Arm 205", "Arm 9", "Beam 205"],
        yticks=range(8),
        yticklabels=[LABELS[m] for m in METHODS],
        title="A. Executable original-motion preservation",
    )
    contrasts = effects["summary"]
    axes[1].barh(
        range(len(contrasts)), [r["rescued"] for r in contrasts], color="#178c76"
    )
    axes[1].set(
        yticks=range(6),
        yticklabels=[
            "Smooth / decoded legs",
            "Original legs / raw",
            "Original legs / smooth",
            "Smooth / original legs",
            "10 Hz legs / raw",
            "10 Hz legs / smooth",
        ],
        xlim=(0, 19),
        xlabel="Paired failures changed to passes / 18",
        title="B. Which intervention rescues execution?",
    )
    axes[1].invert_yaxis()
    chosen = [
        r
        for r in geometry["summary"]
        if r["method"]
        in (
            "body9_raw",
            "body9_smooth",
            "body9_leg12",
            "body9_smooth_leg12",
            "linear29",
        )
    ]
    axes[2].bar(
        range(5),
        [r["macro_clearance_mae_m"] * 100 for r in chosen],
        color=["#b57752", "#bb975c", "#348d78", "#55aa98", "#5a7ea0"],
    )
    axes[2].set(
        xticks=range(5),
        xticklabels=["Body9", "Smooth", "Leg12", "Smooth\nLeg12", "Linear29"],
        ylabel="Clearance MAE (cm)",
        title="C. Independent geometry diagnostic\n643 previously frozen scene candidates",
    )
    # Preserve the requested fixed order rather than the method registry order.
    axes[2].set_xticklabels(
        [
            {
                "body9_raw": "Body9",
                "body9_smooth": "Smooth",
                "body9_leg12": "Leg12",
                "body9_smooth_leg12": "Smooth\nLeg12",
                "linear29": "Linear29",
            }[r["method"]]
            for r in chosen
        ]
    )
    fig.suptitle(
        "Motion representation: temporal smoothing, leg fidelity, and critical scenes",
        fontsize=17,
    )
    fig.text(
        0.03,
        0.023,
        f"{summary['new_recorded_preflight_episodes']} recorded preflights + {summary['new_main_episodes']} main episodes. Separate infrastructure failure: 144 scheduled slots, zero recorded episodes.\nOriginal-leg input is an oracle; smoothing also changes within-patch motion. All development; correlated source/scene descendants, no student-policy claim.",
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0.12, 1, 0.93])
    for ext in ("png", "pdf"):
        fig.savefig(PROJECT / f"artifacts/token_mechanism.{ext}", dpi=170)
    plt.close(fig)


def report():
    OUTPUT.mkdir(exist_ok=True)
    q = read(PREFLIGHT / "decoder_qualification.json")
    tasks = read(PREFLIGHT / "batch.json")["tasks"]
    scores = {r["task_id"]: r for r in read(PREFLIGHT / "original_fidelity.json")}
    outcomes = {
        r["task_id"]: r for r in read(PREFLIGHT / "metrics/scene-outcomes.json")
    }
    audits = [audit_preflight(r) for r in (PREFLIGHT, CARRIERS)]
    dump(OUTPUT / "preflight_data_audit.json", audits)
    effects = paired_effects(tasks, scores, outcomes)
    reference_diagnostics(PREFLIGHT, OUTPUT, METHODS)
    methods = []
    for m in METHODS:
        rows = [r for r in q if r["method"] == m]
        methods.append(
            dict(
                method=m,
                joint_passes=sum(sum(r["successes"].values()) for r in rows),
                native_passes=sum(r["native_passes"] for r in rows),
                fidelity_passes=sum(r["fidelity_passes"] for r in rows),
                fully_qualified_pairs=sum(r["qualified"] for r in rows),
            )
        )
    carriers = read(CARRIERS / "carrier_qualification.json")
    main_results = (
        audit_main(MAIN, PREFLIGHT, OUTPUT)
        if (MAIN / "aggregate.json").exists()
        else None
    )
    main_n = len(main_results[0]) if main_results else 0
    main_panels = main_results[3] if main_results else []
    main_index = main_results[4] if main_results else []
    failed = read(FAILED / "exit.json")
    assert failed["exit_code"] != 0 and not list(
        (FAILED / "metrics").glob("episode-*.npz")
    )
    carrier_n = len(read(CARRIERS / "batch.json")["tasks"])
    preflight_n = len(tasks) + carrier_n
    summary = dict(
        methods=methods,
        qualification=q,
        new_recorded_preflight_episodes=preflight_n,
        new_failed_preflight_scheduled_slots=144,
        new_preflight_scheduled_attempts=preflight_n + 144,
        new_main_episodes=main_n,
        cumulative_preflight_scheduled_attempts=248 + preflight_n + 144,
        cumulative_recorded_preflight_episodes=248 + preflight_n,
        cumulative_main_attempts=216 + main_n,
        cumulative_recorded_native_episodes=464 + preflight_n + main_n,
        main_budget_remaining=480 - 216 - main_n,
        representation_panels=len(main_panels),
        verified_representation_panels=sum(
            r["representation_relation_verified"] for r in main_panels
        ),
        representation_control_rows=sum(r["control_rows"] for r in main_index),
        representation_supported_motor_rows=sum(
            r["supported_motor_rows"] for r in main_index
        ),
        carrier_qualification=carriers,
        screened_carrier_groups=len(carriers),
        original_supported_carriers=sum(r["original_supported"] for r in carriers),
        acquisition_ready_carriers=sum(r["acquisition_ready"] for r in carriers),
        canonical_scene_pairs=5,
        canonical_scene_source_groups=3,
        new_obstacle_qualified_source_pairs=0,
        split="development",
        held_out_generalization=False,
        student_trained=False,
    )
    dump(OUTPUT / "aggregate.json", summary)
    dump(
        OUTPUT / "preflight_failure_summary.json",
        dict(
            mechanisms=failure_summary(tasks, list(outcomes.values()), "method"),
            carriers=failure_summary(
                read(CARRIERS / "batch.json")["tasks"],
                read(CARRIERS / "metrics/scene-outcomes.json"),
                "source_group",
            ),
        ),
    )
    attempts = []
    for run, role in [
        (PREFLIGHT, "mechanism_preflight"),
        (CARRIERS, "carrier_preflight"),
    ] + ([(MAIN, "representation_intervention")] if main_results else []):
        lookup = {t["task_id"]: t for t in read(run / "batch.json")["tasks"]}
        for o in read(run / "metrics/scene-outcomes.json"):
            t = lookup[o["task_id"]]
            attempts.append(
                dict(
                    run=str(run),
                    role=role,
                    task_id=t["task_id"],
                    method=t.get("method", "continuous"),
                    source_group=t["source_group"],
                    variant=t["variant"],
                    condition=t["condition"],
                    perturbation_id=t["perturbation_id"],
                    native_pass=o["scene_passage_verified"],
                    body_error_m=o["mean_body_error_m"],
                    root_error_m=o["max_root_xy_error_m"],
                )
            )
    with (OUTPUT / "recorded_native_episodes.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(attempts[0]))
        writer.writeheader()
        writer.writerows(attempts)
    dump(
        OUTPUT / "launch_ledger.json",
        [
            dict(
                run=str(r),
                scheduled_slots=len(read(r / "manifest.json")),
                recorded_episodes=len(list((r / "metrics").glob("episode-*.npz"))),
                exit=read(r / "exit.json"),
                launch_sha256=sha256(r / "launch.json"),
            )
            for r in (FAILED, PREFLIGHT, CARRIERS) + ((MAIN,) if main_results else ())
        ],
    )
    geometry = read(GEOMETRY / "results.json")
    figure(summary, geometry, effects)
    viewers(summary, main_results)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    report()
