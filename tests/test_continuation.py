import json

import numpy as np
import pytest

from hindsight_motion.continuation import array_errors, pair_audit, prefix_audit, select_states


def test_phase_selection_frozen_from_qualified_parent():
    score = dict(duck_recover_stop_success=True, entry_tick=41, clear_tick=78, control_steps=246)
    assert select_states(score) == dict(pre_entry=26, entry=42, exit=79, pre_hold=186)
    with pytest.raises(ValueError, match="support"):
        select_states(dict(score, duck_recover_stop_success=False))
    with pytest.raises(ValueError, match="ordered"):
        select_states(dict(score, control_steps=100))


def test_prefix_cannot_be_shortened_or_hide_nonfinite_values():
    with pytest.raises(ValueError, match="Incomplete"):
        array_errors({'x':np.zeros((3, 2))}, {'x':np.zeros((2, 2))}, ['x'], 3)
    with pytest.raises(ValueError, match="nonfinite"):
        array_errors({'x':np.zeros(2)}, {'x':np.array([0.,np.nan])}, ['x'])


def make_pair(tmp_path):
    paths = [tmp_path / name for name in ['a', 'b']]
    for path in paths:
        t=path / 'task'; t.mkdir(parents=True)
        np.savez(t/'initial-state.npz', root=np.zeros(13), proprio=np.zeros(930))
        np.savez(t/'dynamics-entry.npz', masses=np.ones(30))
        (t/'depth-source.json').write_text(json.dumps({'first_physics_step_torch_rng_sha256':'reset'}))
        np.savez(t/'teacher-episode.npz',teacher_actions=np.zeros((8,29)),proprio=np.zeros((8,930)),future_reference=np.zeros((8,640)))
        np.savez(t/'pre-action-poses.npz',**{k:np.zeros((8,3)) for k in ['root_xyz','root_wxyz','joint_pos','joint_vel','body_xyz','body_wxyz']})
        np.savez(t/'trace.npz',root_xyz=np.zeros((8,3)),speed=np.zeros(8),contact_force_w=np.zeros((32,2,1,3)))
        np.savez(t/'handoff-state.npz',joint_pos=np.zeros(29),joint_vel=np.zeros(29),previous_action=np.zeros(29),teacher_buffer_actor=np.zeros(930))
        (t/'handoff.json').write_text(json.dumps({'rng':{'torch':'at_handoff'}}))
    return paths


def test_same_pose_with_different_action_history_is_not_matched(tmp_path):
    a,b=make_pair(tmp_path)
    assert pair_audit(a,b,4)['matched']
    path=b/'task/handoff-state.npz'
    with np.load(path) as d:arrays={k:d[k] for k in d.files}
    arrays['previous_action'][0]=.1
    np.savez(path,**arrays)
    assert not pair_audit(a,b,4)['matched']


def test_future_difference_allowed_but_prefix_leakage_rejected(tmp_path):
    a,b=make_pair(tmp_path)
    path=b/'task/teacher-episode.npz'
    with np.load(path) as d:arrays={k:d[k] for k in d.files}
    arrays['future_reference'][4:]=1
    np.savez(path,**arrays)
    assert prefix_audit(a,b,4)['matched']
    arrays['future_reference'][3]=1
    np.savez(path,**arrays)
    assert not prefix_audit(a,b,4)['matched']


def test_matching_also_requires_rng_state(tmp_path):
    a,b=make_pair(tmp_path)
    (b/'task/handoff.json').write_text(json.dumps({'rng':{'torch':'different'}}))
    assert not pair_audit(a,b,4)['matched']
