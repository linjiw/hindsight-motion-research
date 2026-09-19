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
]
FIGURES = ["token_mechanism.png", "carrier_scene_geometry.png", "complete_task.png", "continuation.png", "continuation_admission02.png"]


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
        "complete_task_evidence_date": "2026-09-18", "llm_interface_evidence_date": "2026-09-18", "page_date": "2026-09-18", "research_review_date": "2026-09-18",
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
