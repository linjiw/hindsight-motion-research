import numpy as np
import pytest

from hindsight_motion.selection_codec import decode_candidate, gather_reference, native_velocity


def test_scale_conversion_respects_joint_names():
    names = tuple(f'j{i}' for i in range(29))
    q = np.full((499, 29), .2, dtype=np.float32)
    scale = np.linspace(.1, 1, 29)
    a, _, audit = decode_candidate(q, names, scale, names)
    b, _, _ = decode_candidate(q[:, ::-1], names[::-1], scale, names)
    np.testing.assert_array_equal(a, b[:, ::-1])
    np.testing.assert_array_equal(a[:2], q[:2])
    assert audit['knots'] == 100 and audit['clipped_symbols'] > 0


def test_native_endpoint_is_penultimate_difference():
    q = np.array([[0], [1], [3], [7]], dtype=np.float32)
    np.testing.assert_array_equal(native_velocity(q).ravel(), [50, 100, 200, 100])


def test_committed_prefix_is_not_inferred_from_tail_cursor():
    q = np.repeat(np.arange(100, dtype=np.float32)[:, None], 29, axis=1)
    indices = np.r_[np.arange(10, 15), np.arange(20, 75)]
    actual, _ = gather_reference(q, q, indices)
    np.testing.assert_array_equal(actual[:5, 0], [10, 11, 12, 13, 14])
    assert actual[5, 0] == 20
    with pytest.raises(ValueError, match='horizon'):
        gather_reference(q, q, indices[:45])


def test_unknown_joint_or_nonfinite_scale_is_rejected():
    names = tuple(f'j{i}' for i in range(29))
    for scale, source in [(np.ones(29), names[:-1]+('other',)), (np.full(29, np.nan), names)]:
        with pytest.raises(ValueError):
            decode_candidate(np.zeros((50, 29)), names, scale, source)
