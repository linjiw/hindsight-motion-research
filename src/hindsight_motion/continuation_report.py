"""Publish aggregate same-phase handoff evidence without motion descendants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .complete_task_report import audit_case
from .continuation import pair_audit, prefix_audit
from .core import sha256
from .critical import PROJECT, dump


def analyze(output, public_path=None):
    output = Path(output).resolve()
    if (output / "aggregate.json").exists() or (public_path and Path(public_path).exists()):
        raise FileExistsError("Do not overwrite a completed continuation analysis")
    plan = json.loads((output / "plan.json").read_text())
    paths = [Path(c["run_dir"]) for c in plan["cases"]]
    if any((p / "launch.json").exists() and not (p / "exit.json").exists() for p in paths):
        raise ValueError("Native attempt still running or missing its exit receipt")
    deferred = [p for p in paths if (p / "resource_deferred.json").exists()]
    exits = [json.loads((p / "exit.json").read_text()) for p in paths if (p / "exit.json").exists()]
    if len(exits) != len(paths) and not (deferred or (output / "stopped.json").exists() or any(e["exit_code"] for e in exits)):
        raise ValueError("Queue has no completed or stopped evidence; analysis is premature")
    rows, files = [], [output / name for name in ["registration.json", "plan.json", "execution-start.json"]]
    for case in plan["cases"]:
        run = Path(case["run_dir"])
        row = audit_case(case)
        row.update(state=case["state"], handoff_tick=case["handoff_tick"], handoff_time_s=case["handoff_tick"]*.02)
        if row["status"] == "unrun" and deferred:
            row["reason"] = "resource_gate_timeout; remaining queue deferred without native launch"
        if row["status"] == "completed":
            status = json.loads((run / "task/handoff-status.json").read_text())
            row["handoff_reached"] = status["reached"]
            row["adapter"] = json.loads((run / "task/adapter.json").read_text())
            if status["reached"]:
                receipt = json.loads((run / "task/handoff.json").read_text())
                row["reference_jump"] = receipt["jump"]
            if case["method"] == "continuous":
                row["parent_prefix"] = prefix_audit(case["parent_run"], run, case["handoff_tick"])
        for name in ["launch.json", "exit.json", "resource_wait.jsonl", "resource_admission.json", "resource_deferred.json", "task/task-result.json", "task/adapter.json",
                     "task/handoff.json", "task/handoff-state.npz", "task/trace.npz", "task/duck-features.npz",
                     "task/teacher-episode.npz", "task/pre-action-poses.npz", "task/dynamics-entry.npz"]:
            if (run / name).exists():
                files.append(run / name)
        rows.append(row)
    pairs = []
    for index in range(0, len(rows), 2):
        a, b = rows[index:index+2]
        pair = dict(source_clip=a["source_clip"], state=a["state"], handoff_tick=a["handoff_tick"],
                    compared=a["status"] == b["status"] == "completed" and a.get("handoff_reached",False) and b.get("handoff_reached",False))
        if pair["compared"]:
            audit = pair_audit(plan["cases"][index]["run_dir"], plan["cases"][index+1]["run_dir"], a["handoff_tick"])
            pair.update(audit=audit, continuous_success=a["success"], linear29_success=b["success"],
                        qualified=audit["matched"] and a["parent_prefix"]["matched"] and a["success"],
                        completion_time_difference_s=b["completion_time_s"]-a["completion_time_s"])
        pairs.append(pair)
    summaries = {}
    for method in plan["registration"]["methods"]:
        group = [r for r in rows if r["method"] == method]
        summaries[method] = dict(scheduled=len(group), completed=sum(r["status"]=="completed" for r in group),
                                 success=sum(bool(r.get("success")) for r in group),
                                 unrun=sum(r["status"]=="unrun" for r in group))
    offline_path = output / "offline-input-diagnostics.json"
    offline = json.loads(offline_path.read_text()) if offline_path.exists() else None
    if offline:
        files.append(offline_path)
        offline = {k:v for k,v in offline.items() if k != "parents"}
    summary = dict(schema="hindsight_continuation_results_v1", date="2026-09-18",
                   execution_state="resource_deferred" if deferred else ("complete" if len(exits)==len(paths) else "stopped"),
                   scope=plan["registration"]["scope"], autonomous=False, perturbed=False,
                   reference_assisted=True, independent_ancestry_established=False, source_clips=2,
                   scheduled_cases=len(rows), native_attempts=sum(r["status"]!="unrun" for r in rows),
                   completed_episodes=sum(r["status"]=="completed" for r in rows),
                   infrastructure_failures=sum(r["status"]=="infrastructure_failure" for r in rows),
                   unrun=sum(r["status"]=="unrun" for r in rows),
                   control_steps=sum(r.get("control_steps",0) for r in rows),
                   physics_samples=sum(r.get("physics_samples",0) for r in rows),
                   training_steps=0, historical_main_attempts_consumed=0,
                   method_summary=summaries, rows=rows, pairs=pairs, offline_input_diagnostics=offline,
                   qualified_pairs=sum(bool(p.get("qualified")) for p in pairs),
                   stopping_receipt=json.loads((output / "stopped.json").read_text()) if (output / "stopped.json").exists() else None,
                   provenance=[dict(path=str(p.relative_to(PROJECT)),sha256=sha256(p)) for p in files],
                   analysis_source_sha256=sha256(__file__))
    dump(output / "aggregate.json", summary)
    if public_path:
        dump(Path(public_path), summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ["rows","pairs","provenance"]},indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    parser.add_argument("--public-path",type=Path)
    args=parser.parse_args()
    analyze(args.output,args.public_path)
