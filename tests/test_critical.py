from copy import deepcopy
import numpy as np

from hindsight_motion.critical import edit_motion
from hindsight_motion.critical_analysis import relation_gate, CONDITIONS


def test_arm_candidate_preserves_common_entry_root_and_gait():
    # A nonconstant carrier catches accidental overwrites of root/leg trajectories.
    q=np.random.default_rng(3).normal(size=(200,36));q[:,3:7]=[1,0,0,0]
    a,w=edit_motion(q,'tuck');b,_=edit_motion(q,'wide')
    np.testing.assert_array_equal(a[:,:22],q[:,:22])
    np.testing.assert_array_equal(b[:,:22],q[:,:22])
    np.testing.assert_array_equal(a[w==0],b[w==0])
    assert np.max(abs(a[w==1,22:]-b[w==1,22:]))>.5


def panel():
    rows=[dict(condition=c,variant=v,scene_passage_verified=True,
               checks={'obstacle_contact_free':True},contact_events=[])
          for c in CONDITIONS for v in ['tuck','wide']]
    r=next(r for r in rows if r['condition']=='critical' and r['variant']=='wide')
    r.update(scene_passage_verified=False,checks={'obstacle_contact_free':False},
             contact_events=[{'body':'left_elbow_link'}])
    return rows


def test_critical_relation_requires_successful_controls_and_matched_entry():
    good=panel()
    assert relation_gate(good,True)['verified']
    assert not relation_gate(good,False)['verified']
    assert not relation_gate(good[:-1],True)['verified']
    failed=deepcopy(good)
    next(r for r in failed if r['condition']=='removed' and r['variant']=='wide')['scene_passage_verified']=False
    assert not relation_gate(failed,True)['verified']


def test_leg_contact_does_not_establish_arm_mechanism():
    rows=panel()
    next(r for r in rows if r['condition']=='critical' and r['variant']=='wide')['contact_events']=[{'body':'left_knee_link'}]
    assert not relation_gate(rows,True)['verified']
