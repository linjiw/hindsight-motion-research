"""Aggregate-only publication of the registered carrier acquisition follow-up."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .budget import main_attempts
from .core import sha256
from .critical import PROJECT, dump

PROPOSALS = PROJECT / "runs/carrier_scene_proposals_20260916_v1"
PREFLIGHT = PROJECT / "runs/carrier_contrast_preflight_20260916_v1"
MAIN = PROJECT / "runs/carrier_contrast_interventions_20260916_v1"


def report():
    original = json.loads((PROPOSALS / "proposals.json").read_text())
    geometry = json.loads((PROPOSALS / "geometry_summary.json").read_text())
    rows = original["proposals"]
    if len(rows) != 145 or geometry["admitted"] != 0 or original["selected"] is not None:
        raise ValueError("Original dated acquisition result changed; review report interpretation")
    best = max(rows, key=lambda r: r["score"])
    safe = [r for r in rows if r["checks"]["target_clearance"]]
    overlap = [r for r in rows if r["checks"]["original_arm_overlap"]]
    launched = (PREFLIGHT / "launch.json").exists()
    recorded_path = PREFLIGHT / "metrics/scene-outcomes.json"
    recorded = json.loads(recorded_path.read_text()) if recorded_path.exists() else []
    qualification_path = PREFLIGHT / "carrier_qualification.json"
    qualification = json.loads(qualification_path.read_text())[0] if qualification_path.exists() else None
    status = "prepared_waiting_resources"
    if (PREFLIGHT / "resource_deferred.json").exists():
        status = "deferred_resources"
    if launched:
        status = "running"
    if (PREFLIGHT / "exit.json").exists():
        exit_status = json.loads((PREFLIGHT / "exit.json").read_text())
        status = "completed_pending_audit" if exit_status["exit_code"] == 0 else "infrastructure_failure"
    if qualification is not None:
        status = "qualified" if qualification["acquisition_ready"] else "qualification_failed"
    resource_path = PREFLIGHT / "resource_wait.jsonl"
    samples = [json.loads(line) for line in resource_path.read_text().splitlines()] if resource_path.exists() else []
    main_summary = json.loads((MAIN / "aggregate.json").read_text()) if (MAIN / "aggregate.json").exists() else None
    current_main = main_attempts()
    summary = dict(
        evidence_date="2026-09-16", scope="Development-only; selected CMU/107 carrier",
        original_tuck_geometry=dict(
            candidates=geometry["candidates"], admitted=geometry["admitted"],
            target_clearance_passes=len(safe), original_overlap_passes=len(overlap),
            control_clearance_passes=sum(r["checks"]["control_clearance"] for r in rows),
            both_critical_gates_pass=sum(r["checks"]["target_clearance"] and r["checks"]["original_arm_overlap"] for r in rows),
            best_critical_slack_m=geometry["best_critical_slack_m"],
            best_candidate=dict(frame=best["frame"], gap_m=best["gap_m"],
                                worst_target_clearance_m=min(best["positive_clearance_per_repeat_m"]),
                                worst_original_inner_distance_m=max(best["original_inner_witness_per_repeat_m"])),
            registered_native_main_episodes=24, launched_native_main_episodes=0,
            interpretation="No robust original/tuck portal admitted in the fixed grid; not proof that no scene exists."),
        fixed_wide_tuck_followup=dict(status=status, registered_preflight_maximum=6,
            scheduled_preflight_slots=6 if launched else 0, recorded_preflight_episodes=len(recorded),
            qualification=qualification,
            resource_checks=len(samples), last_resource_sample=samples[-1] if samples else None),
        new_main=main_summary,
        cumulative_recorded_preflight_episodes=440 + len(recorded),
        cumulative_scheduled_preflight_slots=584 + (6 if launched else 0),
        cumulative_main_attempts=current_main, main_remaining_budget=480 - current_main,
        canonical_scene_pairs=5 + (1 if main_summary else 0),
        canonical_scene_source_groups=3 + (1 if main_summary else 0),
        split="development", held_out_generalization=False, student_trained=False,
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=sha256(p)) for p in (
            PROPOSALS / "registration.json", PROPOSALS / "geometry_summary.json",
            PROPOSALS / "proposals.json", PROJECT / "configs/carrier_contrast_v1.plan.json")],
    )
    dump(PROJECT / "results/carrier_scene.json", summary)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), gridspec_kw={"width_ratios": [1.35, 1]})
    x = np.array([min(r["positive_clearance_per_repeat_m"]) * 100 for r in rows])
    y = np.array([-max(r["original_inner_witness_per_repeat_m"]) * 100 for r in rows])
    times = np.array([r["frame"] * .02 for r in rows])
    points = axes[0].scatter(x, y, c=times, cmap="viridis", s=25, alpha=.8)
    axes[0].axvline(3, color="#264c3d", linestyle="--", linewidth=1)
    axes[0].axhline(1, color="#264c3d", linestyle="--", linewidth=1)
    axes[0].fill_between([3, max(4, float(x.max()) + 1)], 1, max(3, float(y.max()) + 1), color="#d8e5cc", alpha=.6)
    axes[0].set(xlabel="Worst-repeat tucked-body clearance lower bound (cm)",
                ylabel="Worst-repeat original-arm overlap witness (cm)",
                title="A. No candidate enters the joint admissible region")
    fig.colorbar(points, ax=axes[0], label="Portal placement frame / 50 (s)", fraction=.045)
    axes[1].barh(["Tuck clearance ≥3 cm", "Original overlap ≥1 cm", "Both critical gates", "Both + control geometry"],
                 [len(safe), len(overlap), summary["original_tuck_geometry"]["both_critical_gates_pass"], geometry["admitted"]], color=["#789568", "#b8754e", "#264c3d", "#264c3d"])
    axes[1].invert_yaxis()
    for i, value in enumerate([len(safe), len(overlap), 0, 0]):
        axes[1].text(value + 1, i, f"{value}/145", va="center")
    axes[1].set(xlim=(0, 80), xlabel="Correlated candidate portals", title="B. Individual gates do not imply a valid contrast")
    fig.suptitle("CMU/107: teacher-supported motions do not yet supply a robust scene contrast", fontsize=14)
    fig.text(.055, .025, "Fixed 145-portal grid; all three recorded empty-plane perturbations. Sampled native collision bounds, not obstacle executions.\nOriginal-versus-tuck study: 0 new native episodes. No threshold relaxation or post-outcome portal search.", fontsize=9)
    fig.tight_layout(rect=[0, .12, 1, .94])
    fig.savefig(PROJECT / "artifacts/carrier_scene_geometry.png", dpi=170)
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    report()
