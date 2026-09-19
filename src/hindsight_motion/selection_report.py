"""Independent scoring and public scalar evidence for the selected-reference pilot."""
import argparse
import json
from pathlib import Path

import numpy as np

from .core import sha256
from .critical import PROJECT, dump


def audit_case(case):
    from gear_sonic.research.scene_distillation.collision_clearance import recorded_bounds
    from gear_sonic.research.scene_distillation.duck_task import envelope_features, score_duck_task
    run=Path(case['run_dir'])
    row={k:case[k] for k in ('case_id','condition','method','source_clip')}
    if not (run/'launch.json').exists():return dict(row,status='unrun')
    if not (run/'exit.json').exists():raise ValueError('Native process not closed')
    exit_record=json.loads((run/'exit.json').read_text())
    if exit_record['exit_code']!=0:return dict(row,status='infrastructure_failure',exit_code=exit_record['exit_code'])
    task=json.loads((run/'task.json').read_text())
    score=json.loads((run/'task/task-result.json').read_text())
    selection=json.loads((run/'task/selection.json').read_text())
    proxies=json.loads(Path(task['duck_contract']['collision_bounds']['path']).read_text())['proxies']
    with np.load(run/'task/trace.npz') as trace,np.load(run/'task/robot-poses.npz') as poses:
        bounds=recorded_bounds(proxies,{k:poses[k] for k in poses.files})
        torso=list(poses['body_names']).index('torso_link')
        features=envelope_features(bounds,poses['body_wxyz'][:,torso],task)
        n=len(trace['root_xyz'])
        if len(trace['contact_force_w'])!=4*n:raise ValueError('Missing substep contacts')
        for key in ('root_xyz','speed','contact_force_w'):
            if not np.isfinite(trace[key]).all():raise ValueError('Nonfinite physical evidence')
        forces=np.linalg.norm(trace['contact_force_w'],axis=-1).reshape(n,4,len(trace['body_names']),-1)
        nonfeet=[i for i,name in enumerate(trace['body_names']) if name not in ('left_ankle_roll_link','right_ankle_roll_link')]
        floor=forces[:,:,nonfeet,0].max(axis=(1,2))
        obstacle=forces[:,:,:,1:].max(axis=(1,2,3)) if forces.shape[-1]>1 else np.zeros(n)
        undesired=np.maximum(floor,obstacle)
        np.testing.assert_array_equal(undesired,trace['undesired_force'])
        recomputed=score_duck_task(task,trace['root_xyz'],trace['speed'],undesired,features,
                                  fell=bool((trace['root_xyz'][:,2]<.25).any()))
        for key,value in recomputed.items():
            if value!=score[key]:raise ValueError('Independent scorer mismatch: '+key)
        row.update(status='completed',success=score['duck_recover_stop_success'],control_steps=n,
            physics_samples=4*n,completion_time_s=n*.02,stop_reason=score['stop_reason'],
            fell=score['fell'],recovered=score['recovered'],ordered_hold_ticks=score['ordered_hold_ticks'],
            max_obstacle_force_n=float(obstacle.max()),max_nonfoot_floor_force_n=float(floor.max()),
            final_goal_distance_m=float(np.linalg.norm(trace['root_xyz'][-1]-task['goal_xyz'])),
            final_speed_mps=float(trace['speed'][-1]),independent_score_exact=True)
    row.update({k:selection[k] for k in ('selected_candidate','replans','retimed','support_rejections','teacher_queries','optimizer_updates')})
    for file,key in [('parent-parity.json','parent_parity'),('pair-audit.json','pair_audit')]:
        if (run/file).exists():row[key]=json.loads((run/file).read_text())
    return row


def analyze(output,public_path):
    output=Path(output).resolve();public_path=Path(public_path)
    if (output/'aggregate.json').exists() or public_path.exists():raise FileExistsError('Preserve completed analysis')
    plan=json.loads((output/'plan.json').read_text())
    folders=[Path(c['run_dir']) for c in plan['cases']]
    if any((p/'launch.json').exists() and not (p/'exit.json').exists() for p in folders):raise ValueError('Queue running')
    deferred=any((p/'resource_deferred.json').exists() for p in folders)
    exited=[json.loads((p/'exit.json').read_text()) for p in folders if (p/'exit.json').exists()]
    if len(exited)!=4 and not (deferred or (output/'stopped.json').exists() or any(e['exit_code']!=0 for e in exited)):
        raise ValueError('Queue has no terminal receipt')
    rows=[audit_case(c) for c in plan['cases']]
    offline=json.loads((output/'offline-audit.json').read_text())
    # Mixed-unit internal diagnostic is not a physical quantity to chart or rank.
    for row in offline['rows']:row.pop('mixed_unit_reference_max_difference',None)
    files=[output/n for n in ('registration.json','plan.json','execution-start.json','offline-audit.json','codec-audit.json')]
    for p in folders:
        files += [p/n for n in ('launch.json','exit.json','resource_admission.json','resource_deferred.json',
            'parent-parity.json','pair-audit.json','task/task-result.json','task/selection.json','task/selection.npz',
            'task/trace.npz','task/robot-poses.npz','task/pre-action-poses.npz','task/dynamics-entry.npz',
            'task/initial-state.npz','task/codec-entry.json') if (p/n).exists()]
    summary=dict(schema='hindsight_selection_codec_results_v1',date='2026-09-19',
        scope=plan['registration']['scope'],source_ancestries=1,known_map=True,development_only=True,
        autonomous_from_reset=True,heldout=False,planner_uses_continuous_bank=True,
        execution_state='resource_deferred' if deferred else ('complete' if len(exited)==4 else 'stopped'),
        scheduled_cases=4,native_attempts=sum(r['status']!='unrun' for r in rows),
        completed_episodes=sum(r['status']=='completed' for r in rows),
        infrastructure_failures=sum(r['status']=='infrastructure_failure' for r in rows),
        unrun=sum(r['status']=='unrun' for r in rows),control_steps=sum(r.get('control_steps',0) for r in rows),
        physics_samples=sum(r.get('physics_samples',0) for r in rows),training_steps=0,historical_main_attempts_consumed=0,
        rows=rows,offline_reference_audit=offline,codec_audit=json.loads((output/'codec-audit.json').read_text()),
        provenance=[dict(path=str(p.relative_to(PROJECT)),sha256=sha256(p)) for p in files],
        analysis_source_sha256=sha256(__file__))
    dump(output/'aggregate.json',summary);dump(public_path,summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('provenance','offline_reference_audit','codec_audit')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('--public-path',required=True,type=Path)
    args=parser.parse_args();analyze(args.output,args.public_path)
