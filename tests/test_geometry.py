import numpy as np
from hindsight_motion.core import sphere_box_clearances, source_split, PatchQuantizer


def test_surface_clearance_and_tangent():
    boxes = np.array([[0, 0, 0, 1, 1, 1]])
    assert np.allclose(sphere_box_clearances(np.array([[[2., 0, 0]]]), np.array([.25]), boxes), .75)
    assert np.allclose(sphere_box_clearances(np.array([[[1.25, 0, 0]]]), np.array([.25]), boxes), 0)
    assert np.allclose(sphere_box_clearances(np.array([[[0., 0, 0]]]), np.array([.25]), boxes), -1.25)


def test_full_sequence_collision_cannot_be_hidden_by_first_frame():
    trajectory = np.array([[[3., 0, 0]], [[0., 0, 0]]])
    assert sphere_box_clearances(trajectory, np.array([.1]), [[0, 0, 0, 1, 1, 1]])[0] < 0


def test_common_translation_preserves_clearance():
    c = np.array([[[2., .2, .4]], [[1.4, 2., .1]]]); r = np.array([.3])
    b = np.array([[0., 0., 0., .3, .4, .5]])
    translated = b.copy(); translated[:, :3] += [12, -7, 3]
    assert np.allclose(sphere_box_clearances(c, r, b), sphere_box_clearances(c+[12, -7, 3], r, translated))


def test_group_assignment_reuses_identical_source():
    assignments = [source_split('CMU/76', 20260915) for _ in range(20)]
    assert len(set(assignments)) == 1


def test_residual_code_reconstruction():
    model = PatchQuantizer([np.array([[0., 0.], [2., 2.]]), np.array([[0., 0.], [.1, -.1]])])
    x = np.array([[2.1, 1.9]])
    assert np.allclose(model.decode(model.encode(x), 2), x)
