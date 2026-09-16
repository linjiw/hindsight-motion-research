"""Audit the stored simulator evidence and canonical BFM-facing data interfaces."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .core import sha256
from .critical import dump


def validate(root):
    root=Path(root)
    tasks=json.loads((root/'tasks.json').read_text())
    expected_actor={'proprio','scene_tokens','scene_mask','goal_local_xyz','goal_tolerance_m','complete_known_map'}
    expected_teacher={'future_reference','privileged_state','reference_body_pos'}
    count,positive_rows=0,0
    receipts=[]
    for row in tasks:
        run=Path(row['run_dir']);task=json.loads((run/'task.json').read_text())
        if sha256(run/'task.json')!=row['task_sha256'] or sha256(task['scene_path'])!=task['scene_sha256']:
            raise ValueError('Task/scene receipt mismatch')
        if json.loads((run/'exit.json').read_text())['exit_code']!=0:
            raise ValueError('Unsuccessful native runtime')
        record=json.loads((run/'metrics/scene-outcome.json').read_text())
        manifest=json.loads((run/'manifest.json').read_text())[0]
        if sha256(manifest['source_path'])!=manifest['source_sha256']:
            raise ValueError('Original source motion changed')
        raw=np.load(run/'metrics'/f"episode-{manifest['motion_key']}.npz")
        actor=np.load(run/'metrics/actor-view.npz');teacher=np.load(run/'metrics/teacher-view.npz')
        target=np.load(run/'metrics/target-view.npz')
        assert set(actor.files)==expected_actor and set(teacher.files)==expected_teacher
        n=len(actor['proprio']);assert n==200
        assert actor['proprio'].shape==(n,930) and actor['scene_tokens'].shape==(n,2,13)
        assert target['teacher_action'].shape==(n,29) and target['teacher_motor_token'].shape==(n,64)
        assert teacher['future_reference'].shape==(n,640)
        assert teacher['privileged_state'].shape==(n,1645)
        for data in [actor,teacher,target]:
            assert all(np.isfinite(data[k]).all() for k in data.files)
        np.testing.assert_array_equal(actor['proprio'],raw['proprio'])
        np.testing.assert_array_equal(target['teacher_action'],raw['teacher_action'])
        np.testing.assert_array_equal(target['teacher_motor_token'],raw['teacher_motor_token'])
        expected_support=raw['before_first_native_failure'] & record['scene_passage_verified']
        np.testing.assert_array_equal(target['motor_imitation_support'],expected_support)
        # Reconstruct map/goal from actor-local tokens and measured current pose.
        rotation=Rotation.from_quat(raw['root_state_w'][:,[4,5,6,3]]).as_matrix()
        position=raw['root_state_w'][:,:3]-raw['env_origin']
        goal_world=np.einsum('tij,tj->ti',rotation,actor['goal_local_xyz'])+position
        np.testing.assert_allclose(goal_world,np.tile(task['goal_xyz'],(n,1)),atol=2e-6)
        for i,obstacle in enumerate(task['obstacles']):
            center=np.einsum('tij,tj->ti',rotation,actor['scene_tokens'][:,i,:3])+position
            np.testing.assert_allclose(center,np.tile(obstacle['center_xyz'],(n,1)),atol=2e-6)
            assert actor['scene_mask'][:,i].all()
        assert not actor['scene_mask'][:,len(task['obstacles']):].any()
        forces=np.load(run/'metrics/environment-contacts.npz')['normal_force_w']
        assert forces.shape==(4*n,len(task['body_names']),len(task['obstacles'])+1,3)
        peak=float(np.linalg.norm(forces[:,:,1:],axis=-1).max(initial=0))
        assert abs(peak-record['max_obstacle_normal_force_n'])<1e-5
        count+=n;positive_rows+=int(expected_support.sum())
        receipts.append(dict(task_id=row['task_id'],rows=n,passed=True))
    panels=json.loads((root/'paired_relation_audit.json').read_text())
    for p in panels:
        assert p['entry_max_differences'] and max(p['entry_max_differences'].values())<1e-6
    for variant in ['tuck','wide']:
        z=np.load(root/f'motion-codes-{variant}.npz')
        assert z['rvq_codes'].shape==(40,2) and np.all((z['rvq_codes']>=0)&(z['rvq_codes']<128))
    for receipt in json.loads((root/'runtime_dependency_receipt.json').read_text()):
        assert sha256(receipt['path'])==receipt['sha256'],'Runtime dependency changed during study'
    result=dict(passed=True,episodes=len(tasks),control_rows=count,
                scene_supported_motor_rows=positive_rows,development_only=True,
                source_and_scene_hashes_valid=True,actor_key_whitelist_pass=True,
                actor_map_goal_reconstruction_pass=True,same_state_teacher_target_alignment_pass=True,
                contact_shape_and_peak_recomputation_pass=True,matched_entry_panels=len(panels),
                runtime_dependency_hashes_unchanged=True,per_episode=receipts)
    dump(root/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='per_episode'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);a=parser.parse_args();validate(a.output)
