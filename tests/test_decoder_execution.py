import json
import numpy as np
import pytest

from hindsight_motion.decoder_execution import (
    execution_reference,
    original_fidelity_score,
)
from hindsight_motion.source_acquisition import describe
from hindsight_motion.budget import main_attempts


def test_execution_adapter_preserves_entry_root_and_projects_only_decoded_suffix():
    q = np.zeros((200, 36))
    q[:, 3] = 1
    q[:, 0] = np.linspace(0, 1, 200)
    angles = np.full((200, 29), 2.0)
    limits = np.tile([-1.0, 1.0], (29, 1))
    decoded, audit = execution_reference(q, angles, limits)
    np.testing.assert_array_equal(decoded[:31], q[:31])
    np.testing.assert_array_equal(decoded[:, :7], q[:, :7])
    np.testing.assert_allclose(decoded[60:, 7:], 1.0)
    assert np.all(np.diff(decoded[:, 7]) >= -1e-12)
    assert audit["projected_scalar_count"] == 200 * 29
    assert audit["maximum_projection_rad"] == 1.0


def test_original_fidelity_rejects_perfect_tracking_of_distorted_reference():
    original = np.zeros((200, 14, 3))
    distorted = original.copy()
    distorted[:, :, 0] = 0.3
    assert original_fidelity_score(distorted, distorted, 200)[
        "original_motion_fidelity_pass"
    ]
    assert not original_fidelity_score(distorted, original, 200)[
        "original_motion_fidelity_pass"
    ]
    assert not original_fidelity_score(original, original, 199)[
        "original_motion_fidelity_pass"
    ]
    assert not original_fidelity_score(original, original, 0)[
        "original_motion_fidelity_pass"
    ]
    with pytest.raises(ValueError):
        original_fidelity_score(np.full_like(original, np.nan), original, 200)


def test_source_screen_rejects_backward_sideways_and_out_and_back_motion():
    q = np.zeros((200, 36))
    q[:, 3] = 1
    q[:, 2] = 0.8
    q[:, 0] = np.linspace(0, 1.2, 200)
    feature, screen = describe(q)
    assert screen["eligible"] and feature.shape == (34,)
    backward = q.copy()
    backward[:, 0] *= -1
    assert not describe(backward)[1]["eligible"]
    sideways = q.copy()
    sideways[:, 1] = sideways[:, 0]
    sideways[:, 0] = 0
    assert not describe(sideways)[1]["eligible"]
    reversal = q.copy()
    reversal[:, 0] = np.r_[np.linspace(0, 2, 100), np.linspace(2, 1.2, 100)]
    assert not describe(reversal)[1]["eligible"]


def test_main_budget_counts_failed_decoder_launches_and_excludes_preflight(tmp_path):
    cases = [
        (
            "acquisition",
            "Additional source groups and ducking mechanism intervention panels",
            24,
            True,
        ),
        ("decoder", "Frozen-scene decoded-reference interventions", 96, True),
        ("pending", "Frozen-scene decoded-reference interventions", 96, False),
        ("preflight", "Decoded motion repeated empty-scene qualification", 90, True),
    ]
    for name, purpose, count, launched in cases:
        run = tmp_path / "runs" / name
        run.mkdir(parents=True)
        (run / "batch.json").write_text(json.dumps({"tasks": [{}] * count}))
        (run / "registration.json").write_text(json.dumps({"purpose": purpose}))
        if launched:
            (run / "launch.json").write_text("{}")
            # A failed native attempt still consumes the registered budget.
            (run / "exit.json").write_text('{"exit_code": 1}')
    assert main_attempts(tmp_path) == 120
