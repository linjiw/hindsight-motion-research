from copy import deepcopy
import pytest
from hindsight_motion.llm_interface import (
    canonical, differences, envelope, fixtures, messages, rule_baseline, score, strict_json, summarize,
)


def test_rule_labels_and_routes():
    for case in fixtures():
        assert rule_baseline(case["actor"]) == case["expected_id"]
        for route in ("relay", "sidecar"):
            response = canonical(envelope(case["actor"], case["expected_id"], route))
            assert score(case, route, response)["interface_success"]
            assert "expected_id" not in canonical(messages(case, route))


@pytest.mark.parametrize("field,value", [("dt_s", 0.2), ("frame", "world"),
    ("desired_support", ["left", "left"]), ("committed_prefix_samples", True),
    ("root_dx_m", [0.0]), ("state_digest", "stale"), ("pelvis_z_m", [0.85, 0.85])])
def test_critical_motion_changes_rejected(field, value):
    case = fixtures()[0]
    out = envelope(case["actor"], case["expected_id"], "relay")
    out["motion"][field] = value
    s = score(case, "relay", canonical(out))
    assert s["choice_correct"] and not s["selected_payload_preserved"]
    assert not s["interface_success"]


def test_task_loss_and_wrong_choice_are_distinct():
    case = fixtures()[0]
    out = envelope(case["actor"], case["expected_id"], "relay")
    del out["task"]["hold_s"]
    assert not score(case, "relay", canonical(out))["task_preserved"]
    wrong = envelope(case["actor"], "m42", "relay")
    s = score(case, "relay", canonical(wrong))
    assert s["selected_payload_preserved"] and not s["choice_correct"]
    assert not score(case, "sidecar", '{"motion_id": "invented", "task_id":"traverse-v1"}')["id_valid"]


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '[]', '```json\n{}\n```', '{'])
def test_no_silent_output_repair(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


def test_missing_null_id_and_bool_do_not_pass():
    case = fixtures()[-1]
    assert not score(case, "sidecar", '{"task_id":"traverse-v1"}')["choice_correct"]
    assert differences(1, True)
    assert not differences(1.0, 1)
    assert summarize([], 12)["relay"]["unrun"] == 12


def test_nuisance_variants_preserve_semantic_labels():
    cases = fixtures()
    for a, b in zip(cases[::2], cases[1::2]):
        def meaning(c):
            return next((m["behavior"] for m in c["actor"]["catalog"]
                         if m["motion"]["motion_id"] == c["expected_id"]), None)
        assert a["actor"]["observation"] == b["actor"]["observation"]
        assert meaning(a) == meaning(b)
