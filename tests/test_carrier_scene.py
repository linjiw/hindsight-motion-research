import numpy as np
import pytest

from hindsight_motion.carrier_scene import candidate_decision, select_candidate


def test_one_bad_repetition_rejects_even_when_the_mean_passes():
    controls = np.full((2, 2, 3), .1)
    clearances = np.array([.08, .08, .029])
    witnesses = np.array([-.05, -.05, -.05])
    result = candidate_decision(clearances, witnesses, controls)
    assert not result["admitted"] and not result["checks"]["target_clearance"]
    result = candidate_decision([.08] * 3, [-.05, -.05, -.009], controls)
    assert not result["admitted"] and not result["checks"]["contrast_arm_overlap"]
    controls[1, 1, 2] = .029
    result = candidate_decision([.08] * 3, witnesses, controls)
    assert not result["admitted"] and not result["checks"]["control_clearance"]


def test_admission_boundary_finite_evidence_and_no_admitted_selection():
    result = candidate_decision([.03] * 3, [-.01] * 3, np.full((2, 2, 3), .03))
    assert result["admitted"] and result["score"] == 0
    with pytest.raises(ValueError):
        candidate_decision([.04, np.nan, .04], [-.02] * 3, np.ones((2, 2, 3)))
    assert select_candidate([dict(admitted=False, score=100)]) is None
    rows = [dict(admitted=True, score=1, frame=f, gap_m=g) for f, g in ((85, .7), (70, .8), (70, .6))]
    assert select_candidate(rows) == rows[-1]
