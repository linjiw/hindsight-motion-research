import json

import pytest

from hindsight_motion.complete_task import binding
from hindsight_motion.continuation_admission import validate_parent


def parent_fixture(tmp_path):
    run = tmp_path / "episode"; run.mkdir()
    source = tmp_path / "input"; source.write_text("frozen")
    (tmp_path / "plan.json").write_text(json.dumps(dict(cases=[dict(run_dir=str(run))],bindings=[binding(source)])))
    (tmp_path / "aggregate.json").write_text(json.dumps(dict(execution_state="resource_deferred",native_attempts=0,unrun=1)))
    return run, source


def test_admission_rejects_any_actual_launch(tmp_path):
    run, _ = parent_fixture(tmp_path)
    assert len(validate_parent(tmp_path)["cases"]) == 1
    (run / "launch.json").write_text("{}")
    with pytest.raises(ValueError, match="existing launch"):
        validate_parent(tmp_path)


def test_admission_rejects_changed_inputs(tmp_path):
    _, source = parent_fixture(tmp_path)
    source.write_text("changed")
    with pytest.raises(ValueError, match="Changed bound input"):
        validate_parent(tmp_path)


def test_admission_requires_closed_zero_attempt_parent(tmp_path):
    parent_fixture(tmp_path)
    (tmp_path / "aggregate.json").write_text(json.dumps(dict(execution_state="stopped",native_attempts=1,unrun=0)))
    with pytest.raises(ValueError, match="zero native"):
        validate_parent(tmp_path)
