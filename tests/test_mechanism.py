import numpy as np

from hindsight_motion.mechanism import factorial_angles, smooth_angles


def test_symmetric_filter_preserves_constant_and_affine_interior_and_reduces_jump():
    constant = np.ones((40, 29)) * 0.37
    np.testing.assert_allclose(smooth_angles(constant), constant)
    affine = np.arange(40.0)[:, None] * np.ones((1, 29))
    np.testing.assert_allclose(smooth_angles(affine)[2:-2], affine[2:-2])
    step = np.zeros((40, 29))
    step[20:] = 1
    smoothed = smooth_angles(step)
    assert np.diff(smoothed, axis=0).max() == 6 / 16
    assert smoothed.min() >= 0 and smoothed.max() <= 1


def test_leg_interventions_only_replace_registered_twelve_joints_after_smoothing():
    rng = np.random.default_rng(27)
    q = rng.normal(size=(200, 36))
    base = rng.normal(size=(200, 29))
    linear = rng.normal(size=(200, 29))
    methods = factorial_angles(q, {"RVQ_body9": base, "linear29": linear})
    for prefix, comparison in [("body9", base), ("body9_smooth", smooth_angles(base))]:
        np.testing.assert_array_equal(
            methods[prefix + "_legoracle"][:, :12], q[:, 7:19]
        )
        np.testing.assert_array_equal(
            methods[prefix + "_leg12"][:, :12], linear[:, :12]
        )
        for suffix in ("legoracle", "leg12"):
            np.testing.assert_array_equal(
                methods[prefix + "_" + suffix][:, 12:], comparison[:, 12:]
            )
    np.testing.assert_array_equal(methods["body9_raw"], base)
    assert not np.shares_memory(methods["body9_legoracle"], base)
