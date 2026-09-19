"""Rebuild issued references from recorded public states; no physics or motor query."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
from gear_sonic.research.scene_distillation.duck_motion_bank import load_bank,PublicMotionSelector
from gear_sonic.research.scene_distillation.reference_layout import unpack_reference
from hindsight_motion.complete_task import binding,checked
from hindsight_motion.critical import PROJECT,dump
from hindsight_motion.selection_codec import gather_reference

packet=PROJECT/'runs/selection_codec_20260919_v1'
target=packet/'reference-replay-audit.json'
public=PROJECT/'results/selection_codec_replay.json'
if target.exists() or public.exists():raise FileExistsError('Preserve completed replay audit')
plan=json.loads((packet/'plan.json').read_text())
rows=[];parents=[binding(packet/'aggregate.json'),binding(__file__)]
for case in plan['cases']:
    folder=Path(case['run_dir']);config=json.loads((folder/'config.json').read_text())
    task=json.loads((folder/'task.json').read_text());selector=None;qmax=vmax=0.
    parents += [binding(folder/'task/selection.npz'),binding(folder/'task/pre-action-poses.npz')]
    with np.load(folder/'task/selection.npz') as recorded,np.load(folder/'task/pre-action-poses.npz') as pre:
        for i in range(len(pre['time_s'])):
            measured=MeasuredComposerState(pre['root_xyz'][i],pre['root_wxyz'][i],pre['joint_pos'][i],pre['joint_vel'][i],tuple(pre['joint_names']),float(pre['time_s'][i]))
            if selector is None:
                selector=PublicMotionSelector(load_bank(checked(config['selection']['bank'])),measured,task['goal_xyz'],task['obstacles'])
                with np.load(checked(config['decoded_bank'][selector.candidate.name])) as data:
                    q,v=data['joint_position'].copy(),data['joint_velocity'].copy()
            chunk=selector.reference(measured)
            if case['method']=='linear29':
                joint,velocity=gather_reference(q,v,selector.source_indices[selector.consumed-1:])
                qmax=max(qmax,float(np.max(abs(joint-chunk.joint_position))))
                vmax=max(vmax,float(np.max(abs(velocity-chunk.joint_velocity))))
                chunk=replace(chunk,joint_position=joint,joint_velocity=velocity)
            reference=native_reference(chunk,rotation_wxyz(measured.root_wxyz),native_joint_names=measured.joint_names,native_frame_dt=.1)
            np.testing.assert_array_equal(reference.numpy(),recorded['reference'][i])
            np.testing.assert_array_equal(selector.last_source_indices,recorded['reference_source_indices'][i])
            assert selector.candidate.name==str(recorded['candidate'][i])
            assert selector.last_source_indices[0]==recorded['candidate_cursor'][i]
        receipt=json.loads((folder/'task/selection.json').read_text())
        assert all(receipt[k]==getattr(selector,k) for k in ('replans','retimed','support_rejections'))
        rows.append(dict(case_id=case['case_id'],states=len(pre['time_s']),issued_reference_exact=True,
                         source_indices_exact=True,selector_counters_exact=True,
                         dense_planned_joint_change_max_rad=qmax,dense_planned_velocity_change_max_rad_s=vmax))
result=dict(schema='hindsight_selection_codec_replay_audit_v1',date='2026-09-19',rows=rows,
            native_attempts=0,training_steps=0,scope='Exact reference/choice/index replay on actual histories; no new motor-action or physics evaluation',
            provenance=[dict(path=str(Path(b['path']).relative_to(PROJECT)),sha256=b['sha256']) for b in parents])
dump(target,result);dump(public,result)
print(json.dumps(rows,indent=2))
