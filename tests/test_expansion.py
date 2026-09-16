"""Mechanistic regressions for the expansion's geometry and evidence gates."""
import json

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from hindsight_motion.batch_scene import grid_origins
from hindsight_motion.contact_edit import LegChain,duck_preserving_feet
from hindsight_motion.critical import PROJECT,RUNTIME
from hindsight_motion.scene_evidence import score_episode


def test_separated_scene_grid_order_and_distance():
    np.testing.assert_array_equal(grid_origins(1),[[0,0,0]])
    expected=[[12,-4,0],[12,4,0],[4,-4,0],[4,4,0],[-4,-4,0],[-4,4,0],[-12,-4,0],[-12,4,0]]
    np.testing.assert_array_equal(grid_origins(8),expected)
    for count in (6,8,24,48,96):
        origin=grid_origins(count)
        assert origin.shape==(count,3)
        d=np.linalg.norm(origin[:,None]-origin[None],axis=-1);np.fill_diagonal(d,np.inf)
        assert d.min()==8


def test_duck_inverse_kinematics_preserves_world_feet_and_common_entry():
    path=PROJECT/'runs/expansion_preflight_20260915_v1/references/expand_00_tuck.npz'
    urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    if not path.exists() or not urdf.exists():
        pytest.skip('Integration test requires local licensed motion and native G1 URDF')
    ref=np.load(path);names=list(ref['joint_names'])
    # A short stationary carrier isolates the edit from gait tracking errors.
    q=np.repeat(ref['qpos'][100:101],17,axis=0)
    urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    edited,weight,_=duck_preserving_feet(q,names,urdf,depth=.04,fps=5)
    np.testing.assert_array_equal(edited[weight==0],q[weight==0])
    np.testing.assert_array_equal(edited[:,:2],q[:,:2])
    assert np.max(q[:,2]-edited[:,2])>.039
    for side in ('left','right'):
        chain=LegChain(urdf,side);indices=[7+names.index(n) for n in chain.names]
        for old,new in zip(q,edited):
            positions=[];rotations=[]
            for pose in (old,new):
                p,r=chain.fk(pose[indices]);root=Rotation.from_quat(pose[[4,5,6,3]]).as_matrix()
                positions.append(pose[:3]+root@p);rotations.append(root@r)
            assert np.linalg.norm(positions[0]-positions[1])<=.002
            assert Rotation.from_matrix(rotations[0].T@rotations[1]).magnitude()<=.02


def test_native_contact_evidence_censors_after_failure_and_exempts_only_floor_feet():
    task=dict(body_names=['torso_link','left_ankle_roll_link'],obstacles=[{}],goal_xyz=[0,0,1],
        portal_center_xyz=[-1,0,0],passage_axis_xyz=[1,0,0],maximum_undesired_normal_force_n=1.,
        goal_tolerance_m=.25,exit_progress_m=.2,task_id='x',pair_id='x',family='duck',variant='duck',
        condition='critical',perturbation_id=0,terminal_requirement='moving',scene_sha256='fixture')
    episode=dict(before_first_native_failure=np.array([True,False]),proprio=np.zeros((2,930)),
                 root_state_w=np.array([[0,0,1],[20,0,0]]),env_origin=np.zeros((2,3)))
    native=dict(empty_scene_tracking_qualified=False,terminated=True,native_progress=.5,
                mean_body_error_m=.2,max_root_xy_error_m=.3)
    forces=np.zeros((8,2,2,3));forces[:,1,0,2]=100;forces[4:,0,1,0]=200
    score=score_episode(task,episode,native,forces)
    assert score['max_obstacle_normal_force_n']==0 and score['max_nonfoot_floor_normal_force_n']==0
    assert not score['scene_passage_verified'] and score['contact_events']==[]
    forces[2,1,1,0]=2
    score=score_episode(task,episode,native,forces)
    assert not score['checks']['obstacle_contact_free']
    assert score['contact_events'][0]['first_s']==.015
