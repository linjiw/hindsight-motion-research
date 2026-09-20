"""Recorded-history packing audit and queue-interruption summary; no new physics."""
from dataclasses import replace
import json
from pathlib import Path
import shutil

import numpy as np
import torch

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
from gear_sonic.research.scene_distillation.reference_layout import unpack_reference
from hindsight_motion.complete_task import binding, checked
from hindsight_motion.critical import PROJECT, dump
from hindsight_motion.pending_composer import PendingExitComposer
from hindsight_motion.pending_study import load_decoded


def main():
    packet=PROJECT/'runs/pending_exit_20260920_v1'
    plan=json.loads((packet/'plan.json').read_text());aggregate=json.loads((packet/'aggregate.json').read_text())
    final=plan['cases'][-1];current=Path(final['run_dir']);old=Path(final['parent_run'])
    if aggregate['native_attempts']!=3 or (current/'launch.json').exists():
        raise ValueError('This snapshot describes three completed runs and one never-launched case')
    public=PROJECT/'results/pending_exit_queue.json'
    if public.exists():raise FileExistsError('Preserve completed queue/packing audit')
    config=json.loads((old/'config.json').read_text());task=json.loads((old/'task.json').read_text())
    contract=json.loads((packet/'commitment.json').read_text());decoded=load_decoded(config)
    with np.load(old/'task/pre-action-poses.npz') as pre,np.load(old/'task/selection.npz') as original:
        def state(i):
            return MeasuredComposerState(pre['root_xyz'][i],pre['root_wxyz'][i],pre['joint_pos'][i],pre['joint_vel'][i],tuple(pre['joint_names']),float(pre['time_s'][i]))
        composer=PendingExitComposer(checked(config['distance_exit_bank']),state(0),task['goal_xyz'],task['obstacles'],decoded=decoded,contract=contract)
        for tick in range(135):composer.reference(state(tick))
        if composer.pending.accepted_tick!=134:raise ValueError('Shadow acceptance changed')
        chunks=[];packed=[]
        for i,route in enumerate(('short','loop')):
            chunk=composer.pair[i].chunk(134);q,v=decoded[composer.family][route]
            dense=np.minimum(134+np.arange(60),len(q)-1)
            chunk=replace(chunk,joint_position=q[dense],joint_velocity=v[dense]);chunks.append(chunk)
            packed.append(native_reference(chunk,rotation_wxyz(pre['root_wxyz'][134]),native_joint_names=tuple(pre['joint_names']),native_frame_dt=.1).numpy())
        for key in ('joint_position','joint_velocity','root_xyz','root_velocity','root_rotation_world','support'):
            np.testing.assert_array_equal(getattr(chunks[0],key)[:5],getattr(chunks[1],key)[:5])
        np.testing.assert_array_equal(packed[0],original['reference'][134])
        frames=[unpack_reference(torch.from_numpy(p)).numpy() for p in packed]
        changes={}
        for key,sl in [('joint_position',slice(0,29)),('joint_velocity',slice(29,58)),('relative_orientation',slice(58,64))]:
            indices=np.flatnonzero(np.any(frames[0][:,sl]!=frames[1][:,sl],axis=1))
            changes[key]=dict(changed_physical_sample_indices=indices.tolist(),changed_composed_indices=(134+5*indices).tolist(),
                first_offset_s=float(indices[0]*.1) if len(indices) else None)
    output=PROJECT/'runs/pending_exit_shadow_20260920_v1';output.mkdir(exist_ok=False);shutil.copy2(__file__,output/'source.py')
    files=[Path(__file__),packet/'aggregate.json',packet/'offline-audit.json',packet/'commitment.json',packet/'stopped.json',
           packet/'queue-interruption.json',packet/'queue.log',current/'resource_wait.jsonl',old/'task/pre-action-poses.npz',old/'task/selection.npz']
    result=dict(schema='hindsight_pending_exit_queue_and_shadow_v1',date='2026-09-20',new_native_attempts=0,motor_queries=0,training_steps=0,
        queue_interruption=json.loads((packet/'queue-interruption.json').read_text()),
        final_case_resource_samples=[json.loads(l) for l in (current/'resource_wait.jsonl').read_text().splitlines()],
        shadow=dict(scope='Imposed incumbent farther-Linear29 history only; no executed pending continuation',
            accepted_tick=134,actual_pending_case_launched=False,five_dense_committed_frames_exact=True,
            old_short_reference_exact=True,revised_physical_forecast_samples=changes,
            packing_note='Native 640D blocks are not physical frames; use official unpack_reference to recover q/qdot and relative orientation. Changed forecast samples do not establish changed actions or success.'),
        provenance=[dict(path=str(p.relative_to(PROJECT)),sha256=binding(p)['sha256']) for p in files])
    dump(output/'aggregate.json',result);dump(public,result)
    print(json.dumps(dict(shadow=result['shadow'],queue_interruption=result['queue_interruption']),indent=2))


if __name__=='__main__':main()
