"""Link one new admission to a closed, zero-launch continuation packet."""
import argparse
import json
from pathlib import Path
import shutil

from .complete_task import binding, checked
from .continuation import prepare
from .critical import PROJECT, dump


def validate_parent(parent):
    parent = Path(parent)
    summary = json.loads((parent / "aggregate.json").read_text())
    plan = json.loads((parent / "plan.json").read_text())
    if (summary["execution_state"] != "resource_deferred" or summary["native_attempts"] != 0
            or summary["unrun"] != len(plan["cases"])):
        raise ValueError("Admission requires a closed resource deferral with zero native attempts")
    if any((Path(c["run_dir"]) / "launch.json").exists() for c in plan["cases"]):
        raise ValueError("An existing launch cannot be replaced by admission renewal")
    for item in plan["bindings"]:
        checked(item)
    return plan


def prepare_admission(registration_path):
    registration_path = Path(registration_path).resolve()
    admission = json.loads(registration_path.read_text())
    parent = PROJECT / admission["parent_packet"]
    old = validate_parent(parent)
    if old["registration"]["maximum_native_attempts"] != admission["maximum_native_attempts_across_admissions"]:
        raise ValueError("An admission cannot enlarge the scientific budget")
    scientific = PROJECT / admission["scientific_registration"]
    if json.loads(scientific.read_text()) != old["registration"]:
        raise ValueError("Scientific registration changed")
    output = PROJECT / admission["successor_packet"]
    prepare(output)
    plan = json.loads((output / "plan.json").read_text())
    fields = ["case_id", "source_clip", "condition", "state", "method", "handoff_tick", "parent_run"]
    if [[c[k] for k in fields] for c in plan["cases"]] != [[c[k] for k in fields] for c in old["cases"]]:
        raise ValueError("Successor changed the registered panel")
    shutil.copy2(registration_path, output / "admission.json")
    shutil.copy2(parent / "offline-input-diagnostics.json", output / "offline-input-diagnostics.json")
    links = [binding(parent / name) for name in ["registration.json", "plan.json", "aggregate.json", "execution-start.json"]]
    links += [binding(Path(c["run_dir"]) / "resource_deferred.json") for c in old["cases"]
              if (Path(c["run_dir"]) / "resource_deferred.json").exists()]
    links += [binding(registration_path), binding(__file__)]
    plan["admission"] = dict(registration=admission, parents=links, previous_native_attempts=0)
    plan["bindings"] += links
    dump(output / "plan.json", plan)
    print(json.dumps(dict(admission=str(output), prior_native_attempts=0, maximum_family_attempts=16)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registration", type=Path)
    prepare_admission(parser.parse_args().registration)
