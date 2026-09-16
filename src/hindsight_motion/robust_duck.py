"""Registered repeated qualification of modest crouch and waist-bending recipes."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time
import xml.etree.ElementTree as ET

import numpy as np

from .batch_audit import entry
from .batch_scene import materialize
from .contact_edit import duck_preserving_feet
from .core import sha256
from .critical import PROJECT,RUNTIME,dump,launch


def bend_waist(qpos,joint_names,target):
    """Keep root/legs and shared entry/exit; blend to an absolute waist pitch."""
    q=qpos.copy();t=np.arange(len(q))/50
    u=np.clip(np.minimum(t-.6,t[-1]-.6-t)/.6,0,1);w=u**3*(10-15*u+6*u*u)
    j=7+list(joint_names).index('waist_pitch_joint')
    q[:,j]=(1-w)*q[:,j]+w*target
    return q,w


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import qpos_to_sonic_motion_entry,sonic_motion_entry_to_qpos,save_sonic_motion_file
    output=Path(output);construction=output.with_name(output.name+'_construction')
    construction.mkdir(parents=True,exist_ok=False);(construction/'motions').mkdir();(construction/'references').mkdir()
    recipes=[('anchor205',0,.06,None),('anchor9',2,.06,None),
             ('hybrid205',0,.04,.35),('hybrid9',2,.04,.35),('hybrid359',11,.04,.35),
             ('bend205',0,0.,.50),('bend9',2,0.,.50)]
    registration=dict(registered_unix_s=time.time(),purpose='Repeated empty-scene qualification of lower-body versus waist-bending recipes',
        parent=str(PROJECT/'runs/expansion_preflight_20260915_v1/registration.json'),
        maximum_episodes=42,previous_expansion_preflight_episodes=50,maximum_expansion_preflight_episodes=96,
        expansion_preflight_launch_number=4,maximum_expansion_preflight_launches=4,
        recipes=[dict(pair_id=p,carrier_id=c,pelvis_drop_m=d,waist_pitch_target_rad=b) for p,c,d,b in recipes],
        selection='Two prior duck anchors plus five anatomically modest recipes on previously examined carriers; not seven independent source groups',
        natural_motion_screen='Translating sneak reference previously failed strict tracking; available squat/bending references are mostly stationary; duck-named GRAB objects are not labeled duck-under motions',
        qualification='Both continuations pass all three explicit perturbations in empty scenes and share measured entry',
        perturbation_offsets_m=[0.,-.015,.015],unchanged_tracking_limits=dict(mean_body_error_m=.10,max_root_xy_m=.25),
        label='Development preflight, excluded from main scene dataset',no_replacements=True)
    dump(construction/'registration.json',registration)
    source=PROJECT/'runs/expansion_preflight_20260915_v1'
    manifests={r['motion_key']:r for r in json.loads((source/'manifest.json').read_text())}
    old_ducks={r['carrier_id']:r for r in json.loads((PROJECT/'runs/expansion_ducks_20260915_v1/manifest.json').read_text())}
    names=json.loads((source/'metrics/episode-contract.json').read_text())['measured_body_names']
    urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    limits={j.attrib['name']:(float(j.find('limit').attrib['lower']),float(j.find('limit').attrib['upper'])) for j in ET.parse(urdf).getroot().findall('joint') if j.attrib['type']=='revolute'}
    tasks=[];records=[];trials=[]
    for pair,carrier,depth,target in recipes:
        base=manifests[f'expand_{carrier:02d}_tuck'];ref=np.load(base['reference_path']);q=ref['qpos'];joint_names=ref['joint_names'].tolist()
        try:
            if target is None:
                candidate=np.load(old_ducks[carrier]['reference_path'])['qpos'];audit=old_ducks[carrier]['edit_audit']
            else:
                candidate,audit=q.copy(),{}
                if depth:candidate,_,audit=duck_preserving_feet(q,joint_names,urdf,depth=depth)
                candidate,weight=bend_waist(candidate,joint_names,target)
                audit.update(waist_pitch_target_rad=target,root_xy_preserved=bool(np.array_equal(candidate[:,:2],q[:,:2])))
            for j,name in enumerate(joint_names):
                if np.any(candidate[:,j+7]<limits[name][0]-1e-6) or np.any(candidate[:,j+7]>limits[name][1]+1e-6):
                    raise ValueError(f'Joint limit violation: {name}')
            np.testing.assert_array_equal(candidate[:30],q[:30]);np.testing.assert_array_equal(candidate[-30:],q[-30:])
        except (ValueError,AssertionError) as exc:
            trials.append(dict(pair_id=pair,admitted=False,reason=str(exc)));continue
        trials.append(dict(pair_id=pair,admitted=True,**audit))
        pair_records={}
        for variant,pose in [('duck',candidate),('upright',q)]:
            key=f'{pair}_{variant}';motion=qpos_to_sonic_motion_entry(pose,source_fps=50,canonicalize_horizontal_origin=False)
            error=float(np.max(abs(pose-sonic_motion_entry_to_qpos(motion))))
            if error>1e-6:raise ValueError('Native roundtrip failed')
            path=construction/'motions'/f'{key}.pkl';save_sonic_motion_file(path,motion_key=key,motion_entry=motion)
            reference=construction/'references'/f'{key}.npz';np.savez_compressed(reference,qpos=pose,joint_names=joint_names,time_s=np.arange(200)/50)
            row=deepcopy(base);row.update(motion_key=key,variant=variant,pair_id=pair,motion_path=str(path),motion_sha256=sha256(path),
                reference_path=str(reference),reference_sha256=sha256(reference),edit_audit=audit if variant=='duck' else {},roundtrip_max_error=error)
            pair_records[variant]=row
        axis=q[-1,:3]-q[0,:3];axis[2]=0;axis/=np.linalg.norm(axis);normal=np.array([-axis[1],axis[0],0.])
        for p,offset in enumerate((0.,-.015,.015)):
            for variant,row in pair_records.items():
                task=dict(schema='hindsight_critical_traversal_task_v1',task_id=f'{pair}_removed_{variant}_p{p}',pair_id=pair,
                    family='duck',variant=variant,condition='removed',perturbation_id=p,initial_root_delta_xyz_m=(offset*normal).tolist(),
                    split='development',source_group=row['source_group'],obstacles=[],body_names=names,start_xyz=q[0,:3].tolist(),goal_xyz=q[-1,:3].tolist(),
                    portal_center_xyz=q[100,:3].tolist(),passage_axis_xyz=axis.tolist(),goal_tolerance_m=.25,exit_progress_m=.20,
                    terminal_requirement='Moving arrival, empty-scene qualification only',maximum_undesired_normal_force_n=1.,control_deadline_steps=200,
                    scene_criticality_verified=False,preflight_only=True)
                tasks.append(task);records.append(row)
    dump(construction/'construction_trials.json',trials)
    shutil.copy2(__file__,construction/'preparation_code.py')
    materialize(tasks,records,output,registration)


def analyze(output):
    output=Path(output);batch=json.loads((output/'batch.json').read_text());outcomes={r['task_id']:r for r in json.loads((output/'metrics/scene-outcomes.json').read_text())}
    rows=[]
    for pair in sorted({t['pair_id'] for t in batch['tasks']}):
        tasks=[t for t in batch['tasks'] if t['pair_id']==pair];common=[]
        for perturbation in range(3):
            entries=[entry(dict(np.load(output/'metrics'/f"episode-{t['motion_key']}.npz"))) for t in tasks if t['perturbation_id']==perturbation]
            difference={k:float(np.max(abs(entries[0][k]-entries[1][k]))) for k in entries[0]}
            common.append(dict(perturbation_id=perturbation,max_differences=difference,matched=max(difference.values())<=1e-5))
        support={v:sum(outcomes[t['task_id']]['scene_passage_verified'] for t in tasks if t['variant']==v) for v in ('duck','upright')}
        rows.append(dict(pair_id=pair,source_group=tasks[0]['source_group'],successes=support,entry_audit=common,
                         qualified=all(r['matched'] for r in common) and all(n==3 for n in support.values())))
    dump(output/'repeat_qualification.json',rows);print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','launch','analyze']);p.add_argument('output',type=Path)
    a=p.parse_args();globals()[a.command](a.output.resolve())
