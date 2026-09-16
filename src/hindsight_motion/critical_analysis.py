"""Audit complete intervention panels before assigning critical-relation labels."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .core import PatchQuantizer, sha256
from .critical import PROJECT, dump

CONDITIONS=('critical','relaxed','removed','displaced')


def relation_gate(rows, entry_equal):
    """A contact alone is insufficient: require both executable controls and common entry."""
    index={(r['condition'],r['variant']):r for r in rows}
    expected={(c,v) for c in CONDITIONS for v in ('tuck','wide')}
    if set(index)!=expected:
        return dict(verified=False,reason='incomplete intervention panel')
    if not entry_equal:
        return dict(verified=False,reason='unmatched measured entry state or history')
    controls=all(index[c,v]['scene_passage_verified'] for c in CONDITIONS[1:] for v in ('tuck','wide'))
    tight=index['critical','tuck'];wide=index['critical','wide']
    arm_contact=any(any(part in e['body'] for part in ('shoulder','elbow','wrist'))
                    for e in wide['contact_events'])
    verified=bool(controls and tight['scene_passage_verified'] and
                  not wide['checks']['obstacle_contact_free'] and arm_contact)
    return dict(verified=verified,controls_pass=controls,tucked_critical_pass=tight['scene_passage_verified'],
                wide_arm_contact=arm_contact,reason='verified within this matched panel' if verified
                else 'intervention outcomes do not establish the planned arm-clearance mechanism')


def entry_arrays(run):
    manifest=json.loads((run/'manifest.json').read_text())[0]
    episode=np.load(run/'metrics'/f"episode-{manifest['motion_key']}.npz")
    root=episode['root_state_w'][0].copy();root[:3]-=episode['env_origin'][0]
    return dict(root_state=root,joint_pos=episode['joint_pos'][0],joint_vel=episode['joint_vel'][0],
                proprio=episode['proprio'][0])


def analyze(output):
    output=Path(output)
    tasks=json.loads((output/'tasks.json').read_text())
    rows=[]
    for task in tasks:
        run=Path(task['run_dir']);f=run/'metrics/scene-outcome.json'
        status='not_attempted'
        if (run/'launch.json').exists():
            status='infrastructure_failure' if (run/'exit.json').exists() else 'running'
        record=dict(task_id=task['task_id'],condition=task['condition'],variant=task['variant'],
                    perturbation_id=task['perturbation_id'],run_dir=str(run),status=status)
        if f.exists():
            record.update(json.loads(f.read_text()));record['status']='completed'
        rows.append(record)
    dump(output/'all_attempts_and_outcomes.json',rows)
    fields=['task_id','condition','variant','perturbation_id','status','scene_passage_verified',
            'max_obstacle_normal_force_n','max_nonfoot_floor_normal_force_n','mean_body_error_m',
            'max_root_xy_error_m','final_goal_distance_m','terminated','valid_pre_action_rows']
    with (output/'all_attempts_and_outcomes.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    panels=[]
    for perturbation in [0,1,2]:
        panel=[r for r in rows if r['perturbation_id']==perturbation and r['status']=='completed']
        differences={}
        if len(panel)==8:
            entries=[entry_arrays(Path(r['run_dir'])) for r in panel]
            differences={k:float(max(np.max(np.abs(e[k]-entries[0][k])) for e in entries)) for k in entries[0]}
        equal=bool(differences and max(differences.values())<1e-6)
        gate=relation_gate(panel,equal)
        panels.append(dict(perturbation_id=perturbation,entry_max_differences=differences,**gate))
    dump(output/'paired_relation_audit.json',panels)
    native=PROJECT/'runs/critical_preflight_20260915_v2'
    proposals=json.loads((output/'all_geometry_proposals.json').read_text())
    admitted=[r for r in proposals['proposals'] if r['admitted']]
    intervals=[]
    for frame in sorted({r['frame'] for r in admitted}):
        gaps=[r['gap_m'] for r in admitted if r['frame']==frame]
        intervals.append(dict(anchor_time_s=frame*.02,sampled_admitted_gap_min_m=min(gaps),
                              sampled_admitted_gap_max_m=max(gaps),grid_step_m=.02))
    dump(output/'critical_parameter_intervals.json',dict(
        geometric_samples=intervals,physical_tested_gap_m=proposals['selected']['gap_m'],
        physical_continuous_interval_verified=False,initial_lateral_perturbations_m=[0.,-.015,.015]))
    # Motion codes remain reference-derived targets, separate from the teacher motor space.
    codebook=np.load(PROJECT/'runs/pilot_20260915_v1/codebook.npz')
    quantizer=PatchQuantizer([codebook['level0'],codebook['level1']])
    for variant in ('tuck','wide'):
        key=f'critical_03_{variant}'
        manifest={r['motion_key']:r for r in json.loads((native/'manifest.json').read_text())}
        reference=np.load(manifest[key]['reference_path'])['qpos']
        codes=quantizer.encode(reference[:,7:].reshape(-1,145))
        np.savez_compressed(output/f'motion-codes-{variant}.npz',rvq_codes=codes,
                            root_wxyz_side_channel=reference[:,:7],code_interval_s=.1,
                            training_target_only=True)
    relations=[]
    for panel in panels:
        if not panel['verified']:continue
        wide=next(r for r in rows if r['condition']=='critical' and r['variant']=='wide'
                  and r['perturbation_id']==panel['perturbation_id'])
        for event in wide['contact_events']:
            if not any(part in event['body'] for part in ('shoulder','elbow','wrist')):continue
            relations.append(dict(pair_id='arm03',family='arm_tuck',**event,
                perturbation_id=panel['perturbation_id'],critical_scene_id=wide['task_id'],
                supported_behavior='tuck',contrast_behavior='wide',
                evidence='paired executed critical/relaxed/removed/displaced panel',
                teacher_reference_phase_is_actor_input=False,target_only=True,
                scope='This edited pair, passage and initial perturbation only'))
    dump(output/'verified_relation_targets.json',relations)
    complete=[r for r in rows if r['status']=='completed']
    summary=dict(registered=24,completed=len(complete),infrastructure_failures=sum(r['status']=='infrastructure_failure' for r in rows),
        passage_passes=sum(r['scene_passage_verified'] for r in complete),
        source_groups=1,motion_pairs=1,families=['arm_tuck'],
        verified_perturbation_panels=sum(p['verified'] for p in panels),
        relation_target_count=len(relations),main_study_attempts_used=sum(r['status']!='not_attempted' for r in rows),
        preflight_attempts_separate=48,
        conditions={c:{v:dict(passes=sum(r['scene_passage_verified'] for r in complete if r['condition']==c and r['variant']==v),
                               completed=sum(r['condition']==c and r['variant']==v for r in complete))
                        for v in ('tuck','wide')} for c in CONDITIONS},
        interpretation='Within-pair exploratory mechanism test; no held-out generalization or BFM utility result')
    dump(output/'aggregate.json',summary)
    evidence=[]
    for task in tasks:
        run=Path(task['run_dir'])
        for f in ['task.json','exit.json','metrics/scene-outcome.json','metrics/actor-view.npz',
                  'metrics/teacher-view.npz','metrics/target-view.npz','metrics/environment-contacts.npz']:
            p=run/f
            if p.exists():evidence.append(dict(path=str(p),sha256=sha256(p)))
    dump(output/'evidence_receipt.json',evidence)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    analyze(args.output.resolve())
