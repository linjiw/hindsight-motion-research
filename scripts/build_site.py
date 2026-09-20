"""Build the public GitHub Pages artifact from an explicit release allowlist.

No native runtime, motion bank, raw run, or Python research dependency is needed.
"""
from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_site"
SOURCES = ["site/index.html", "site/style.css", "site/app.js", "site/favicon.svg"]
RESULTS = [
    "token_mechanism", "decoder_execution", "mechanism_geometry",
    "foot_reconstruction", "critical_dataset", "mechanism_effects",
    "carrier_scene", "llm_interface", "complete_task", "continuation", "continuation_admission02",
    "selection_codec", "selection_codec_replay",
    "selection_boundary", "selection_boundary_goal",
    "selection_boundary_admission02", "distance_codec_preflight", "distance_codec", "distance_followup",
    "distance_codec_admission02", "endpoint_codec_transfer", "endpoint_controller_sync", "reset_controller_sync", "pending_exit", "pending_exit_queue",
]
FIGURES = ["token_mechanism.png", "carrier_scene_geometry.png", "complete_task.png", "continuation.png", "continuation_admission02.png", "selection_codec.png", "selection_boundary.png", "selection_boundary_admission02.png", "distance_codec.png", "distance_codec_admission02.png", "pending_exit.png"]


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError(f"Duplicate HTML id: {attrs['id']}")
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.links.append(attrs[key])


def main():
    mechanism = json.loads((ROOT / "results/token_mechanism.json").read_text())
    # The prose is an explicitly dated snapshot. Fail if it needs editorial review.
    expected = {
        "cumulative_recorded_preflight_episodes": 440,
        "cumulative_main_attempts": 312,
        "canonical_scene_pairs": 5,
        "canonical_scene_source_groups": 3,
        "new_failed_preflight_scheduled_slots": 144,
        "main_budget_remaining": 168,
        "student_trained": False,
    }
    for key, value in expected.items():
        if mechanism[key] != value:
            raise ValueError(f"Evidence snapshot changed: review page prose for {key}")
    acquisition = json.loads((ROOT / "results/carrier_scene.json").read_text())
    canonical = json.loads((ROOT / "results/critical_dataset.json").read_text())
    if acquisition["original_tuck_geometry"]["admitted"] != 0 or acquisition["original_tuck_geometry"]["candidates"] != 145:
        raise ValueError("Acquisition evidence changed: review the research narrative")
    if canonical["pairs_verified_all_three_panels"] != 3 or canonical["source_groups"] != 3:
        raise ValueError("Canonical coverage changed: review the research narrative")
    llm = json.loads((ROOT / "results/llm_interface.json").read_text())
    if (llm["generations"] != 24 or llm["native_attempts"] != 0
            or llm["model_summary"]["relay"]["interface_success"] != 0
            or llm["model_summary"]["sidecar"]["interface_success"] != 2):
        raise ValueError("LLM probe changed: review its separate synthetic evidence narrative")
    complete = json.loads((ROOT / "results/complete_task.json").read_text())
    if (complete["native_attempts"] != 8 or complete["control_steps"] != 2079
            or complete["physics_samples"] != 8316
            or sum(r.get("success", False) for r in complete["rows"]) != 8
            or not all(p["entry"]["matched"] for p in complete["pairs"])):
        raise ValueError("Complete-task pilot changed: review the scoped page narrative")
    continuation = json.loads((ROOT / "results/continuation.json").read_text())
    if (continuation["execution_state"] != "resource_deferred"
            or continuation["native_attempts"] != 0 or continuation["unrun"] != 16
            or continuation["qualified_pairs"] != 0
            or len(continuation["offline_input_diagnostics"]["rows"]) != 8):
        raise ValueError("Continuation status changed: review the planned/offline/physical distinction")
    admitted = json.loads((ROOT / "results/continuation_admission02.json").read_text())
    if (admitted["execution_state"] != "complete" or admitted["native_attempts"] != 16
            or admitted["qualified_pairs"] != 8 or admitted["control_steps"] != 4136
            or admitted["physics_samples"] != 16544 or admitted["unrun"] != 0
            or any(admitted["method_summary"][m]["success"] != 8 for m in ("continuous", "linear29"))
            or not all(p["audit"]["matched"] for p in admitted["pairs"])
            or any(max(errors.values()) != 0 for p in admitted["pairs"]
                   for errors in (p["audit"]["incoming_max_errors"],
                                  p["audit"]["initial"]["max_errors"],
                                  p["audit"]["prefix"]["max_errors"]))
            or any(max(r["adapter"]["continuous_rebuild_max_errors"].values()) != 0
                   or r["max_obstacle_force_n"] != 0 or r["max_nonfoot_floor_force_n"] != 0
                   for r in admitted["rows"])):
        raise ValueError("Continuation admission 02 changed: review the physical result narrative")
    selection = json.loads((ROOT / "results/selection_codec.json").read_text())
    replay = json.loads((ROOT / "results/selection_codec_replay.json").read_text())
    if (selection["native_attempts"] != 4 or selection["control_steps"] != 1451
            or selection["physics_samples"] != 5804 or selection["unrun"] != 0
            or not all(r["success"] and r["independent_score_exact"] for r in selection["rows"])
            or sum(r["states"] for r in replay["rows"]) != 1451
            or not all(r["issued_reference_exact"] and r["source_indices_exact"] for r in replay["rows"])):
        raise ValueError("Selection-codec evidence changed: review the familiar-controller narrative")
    boundary = json.loads((ROOT / "results/selection_boundary.json").read_text())
    goal = json.loads((ROOT / "results/selection_boundary_goal.json").read_text())
    if (boundary["execution_state"] != "resource_deferred" or boundary["scheduled_cases"] != 6
            or boundary["native_attempts"] != 2 or boundary["unrun"] != 4
            or boundary["control_steps"] != 719 or boundary["physics_samples"] != 2876
            or sum(r.get("success", False) for r in boundary["rows"]) != 2
            or sum(r["states"] for r in boundary["reference_replay"]) != 719
            or sum(r["recorded_states"] for r in goal["rows"]) != 719
            or any(r["changed_candidate_rows"] or r["changed_index_rows"]
                   or any(r["changed_reference_rows"].values()) for r in goal["rows"])):
        raise ValueError("Boundary evidence changed: review completed/unrun/offline distinctions")
    finished = json.loads((ROOT / "results/selection_boundary_admission02.json").read_text())
    preflight = json.loads((ROOT / "results/distance_codec_preflight.json").read_text())
    if (finished["execution_state"] != "complete" or finished["native_attempts"] != 6
            or finished["new_native_attempts"] != 4 or finished["reused_native_attempts"] != 2
            or finished["unrun"] != 0 or finished["control_steps"] != 1867
            or finished["new_control_steps"] != 1148 or finished["physics_samples"] != 7468
            or sum(r.get("success", False) for r in finished["rows"]) != 2
            or sum(r["states"] for r in finished["reference_replay"]) != 1867
            or not all(r["independent_score_exact"] for r in finished["rows"])):
        raise ValueError("Completed boundary screen changed: review paired failures and cumulative costs")
    if (preflight["native_attempts"] != 0
            or sum(r["states"] for r in preflight["recorded_history_replay"]) != 1528
            or preflight["goal_response"][0]["first_changed_reference_tick"] != {"continuous": 127, "linear29": 126}
            or not all(r["committed_prefix_q_exact"] and r["committed_prefix_qdot_exact"] for r in preflight["prefix_audit"])):
        raise ValueError("Distance-codec preflight changed: preserve offline/physical distinction")
    distance = json.loads((ROOT / "results/distance_codec.json").read_text())
    followup = json.loads((ROOT / "results/distance_followup.json").read_text())
    if (distance["execution_state"] != "resource_deferred" or distance["native_attempts"] != 0
            or distance["unrun"] != 4 or distance["control_steps"] != 0
            or sum(r["states"] for r in distance["offline_audit"]["rows"]) != 792
            or len(followup["native_admission"]["samples"]) != 15
            or any(r["ready"] for r in followup["native_admission"]["samples"])
            or followup["sibling_envelope"]["summary"] != {
                "short_successes": 5, "public_successes": 9, "requests": 10,
                "gains": 5, "regressions": 1, "nominal_loop_support_success": True}):
        raise ValueError("Distance comparison status changed: review unrun/offline/sibling distinctions")
    distance_done = json.loads((ROOT / "results/distance_codec_admission02.json").read_text())
    endpoint = json.loads((ROOT / "results/endpoint_codec_transfer.json").read_text())
    sync = json.loads((ROOT / "results/endpoint_controller_sync.json").read_text())
    if (distance_done["execution_state"] != "complete" or distance_done["native_attempts"] != 4
            or distance_done["unrun"] != 0 or distance_done["infrastructure_failures"] != 0
            or distance_done["control_steps"] != 1660 or distance_done["physics_samples"] != 6640
            or sum(r["success"] for r in distance_done["rows"]) != 3
            or sum(p["task_regression"] for p in distance_done["pairs"]) != 1
            or sum(r["states"] for r in distance_done["reference_replay"]) != 1660
            or not all(r["issued_reference_exact"] and r["composed_indices_exact"]
                       and r["family_choice_decision_exact"] for r in distance_done["reference_replay"])
            or not all(r["independent_score_exact"] and not r["fell"]
                       and r["max_obstacle_force_n"] == r["max_nonfoot_floor_force_n"] == 0
                       for r in distance_done["rows"])):
        raise ValueError("Distance admission 02 changed: review completed outcomes and audits")
    far = next(r for r in distance_done["rows"] if r["case_id"] == "farther-beam_linear29")
    gates = [r for r in endpoint["measured_gate_audit"] if r["method"] == "linear29"]
    shadows = [r for r in endpoint["calibrated_choice_shadows"] if r["method"] == "linear29"]
    if (far["success"] or far["decision"]["requested"] != 1 or far["decision"]["chosen"] != 0
            or far["decision"]["measured_clear"] or far["stop_reason"] != "deadline"
            or not endpoint["exploratory"] or endpoint["new_native_attempts"] != 0
            or len(gates) != 2 or len(shadows) != 6
            or any(r["first_measured_gate_open_tick"] != 134
                   or abs(r["decision"]["clearance_gate_margin_m"] + .0010692763277444055) > 1e-12
                   for r in gates)
            or any(r["chosen"] != 0 or r["measured_clear"] for r in shadows)):
        raise ValueError("Clearance diagnosis changed: review request/gate and shadow scope")
    if (sync["summary"]["calibrated_successes"] != 12 or sync["summary"]["incumbent_successes"] != 11
            or sync["summary"]["requests"] != 12 or sync["summary"]["gains"] != 1
            or sync["summary"]["regressions"] != 0 or sync["costs"]["new_native_attempts"] != 16
            or sync["costs"]["reused_conditions"] != 8):
        raise ValueError("Sibling calibration changed: review its separate controller ledger")
    reset_sync = json.loads((ROOT / "results/reset_controller_sync.json").read_text())
    if (reset_sync["summary"]["beam_successes"] != 5 or reset_sync["summary"]["clear_successes"] != 6
            or reset_sync["summary"]["contexts_per_scene"] != 6
            or reset_sync["summary"]["fragile_primary_successes"] != 2
            or reset_sync["costs"]["new_native_attempts"] != 14
            or reset_sync["costs"]["new_control_steps"] != 5619
            or reset_sync["failure_gate"]["first_measured_pre_action_clear_tick"] != 138):
        raise ValueError("Sibling reset screen changed: review separate outcomes and timing diagnosis")
    pending = json.loads((ROOT / "results/pending_exit.json").read_text())
    queue = json.loads((ROOT / "results/pending_exit_queue.json").read_text())
    if (pending["execution_state"] != "stopped" or pending["native_attempts"] != 3
            or pending["unrun"] != 1 or pending["control_steps"] != 1160 or pending["physics_samples"] != 4640
            or pending["infrastructure_failures"] != 0
            or sum(r.get("success", False) for r in pending["rows"]) != 3
            or pending["rows"][-1]["status"] != "unrun"
            or not all(c["unchanged_path_audit"]["matched"] for c in pending["incumbent_comparisons"])
            or sum(r["states"] for r in pending["reference_replay"]) != 1160
            or not all(r["issued_reference_exact"] and r["independent_schedule_exact"]
                       and r["composed_indices_exact"] for r in pending["reference_replay"])
            or pending["commitment"]["latest_accept_tick"] != 162):
        raise ValueError("Pending-exit partial results changed: preserve the unrun decisive case")
    interruption = queue["queue_interruption"]
    if (interruption["supervisor_exit_code"] != 143 or interruption["final_gate_samples"] != 15
            or interruption["ready_samples"] != 1 or interruption["consecutive_ready_max"] != 1
            or queue["shadow"]["actual_pending_case_launched"]
            or queue["shadow"]["accepted_tick"] != 134 or queue["new_native_attempts"] != 0
            or queue["shadow"]["revised_physical_forecast_samples"]["joint_position"]["changed_physical_sample_indices"] != [7,8,9]):
        raise ValueError("Pending-exit interruption/shadow changed: review the evidence distinction")
    if OUTPUT.is_symlink():
        raise ValueError("Refusing a symlinked build directory")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    (OUTPUT / "data").mkdir()
    (OUTPUT / "assets").mkdir()
    files = [(source, Path(source).name) for source in SOURCES]
    files += [(f"results/{name}.json", f"data/{name}.json") for name in RESULTS]
    files += [(f"artifacts/{name}", f"assets/{name}") for name in FIGURES]
    provenance = []
    for source, target in files:
        path = ROOT / source
        if path.is_symlink():
            raise ValueError(f"Public assets must be regular files: {source}")
        shutil.copyfile(path, OUTPUT / target)
        provenance.append({"source": source, "published": target,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUTPUT / "data/provenance.json").write_text(json.dumps({
        "evidence_date": "2026-09-16", "mechanism_evidence_date": "2026-09-15",
        "complete_task_evidence_date": "2026-09-18", "llm_interface_evidence_date": "2026-09-18", "page_date": "2026-09-20", "research_review_date": "2026-09-18",
        "selection_codec_evidence_date": "2026-09-19", "selection_codec_native_attempts": 4,
        "selection_boundary_evidence_date": "2026-09-19",
        "selection_boundary_native_attempts": 2, "selection_boundary_unrun": 4,
        "selection_boundary_admission02_date": "2026-09-19", "selection_boundary_cumulative_attempts": 6,
        "selection_boundary_admission02_new_attempts": 4, "selection_boundary_cumulative_unrun": 0,
        "distance_codec_preflight_native_attempts": 0,
        "distance_codec_execution_state": "resource_deferred", "distance_codec_native_attempts": 0,
        "distance_codec_unrun": 4, "distance_codec_registration_date": "2026-09-19",
        "distance_codec_admission02_date": "2026-09-19",
        "distance_codec_admission02_execution_state": "complete",
        "distance_codec_cumulative_attempts": 4, "distance_codec_cumulative_unrun": 0,
        "distance_codec_continuous_successes": 2, "distance_codec_linear29_successes": 1,
        "endpoint_transfer_audit_native_attempts": 0,
        "endpoint_controller_sync_scope": "Separate sibling continuous-controller calibration",
        "pending_exit_evidence_date": "2026-09-20", "pending_exit_native_attempts": 3,
        "pending_exit_unrun": 1, "pending_exit_execution_state": "stopped",
        "pending_exit_queue_signal": "SIGTERM", "pending_exit_shadow_native_attempts": 0,
        "continuation_registration_date": "2026-09-18", "continuation_native_attempts": 16,
        "continuation_evidence_date": "2026-09-18", "continuation_admission": "02",
        "continuation_original_deferred_attempts": 0, "continuation_qualified_pairs": 8,
        "scope": "Development-only aggregate evidence; no raw motion or controller assets.",
        "files": provenance,
    }, indent=2) + "\n")
    (OUTPUT / ".nojekyll").touch()
    page = PageLinks()
    page.feed((OUTPUT / "index.html").read_text())
    for link in page.links:
        parsed = urlsplit(link)
        if parsed.scheme:
            prefix = "https://github.com/linjiw/hindsight-motion-research/"
            if link.startswith(prefix):
                parts = unquote(parsed.path).split("/")
                if len(parts) > 5 and parts[3] in ("blob", "tree"):
                    if not (ROOT / "/".join(parts[5:])).exists():
                        raise ValueError(f"Broken repository link: {link}")
            continue
        if parsed.path and not (OUTPUT / unquote(parsed.path)).is_file():
            raise ValueError(f"Missing public asset: {link}")
        if not parsed.path and parsed.fragment and parsed.fragment not in page.ids:
            raise ValueError(f"Broken section anchor: {link}")
    print(f"Built {len(files) + 2} public files; validated {len(page.links)} links in _site/")


if __name__ == "__main__":
    main()
