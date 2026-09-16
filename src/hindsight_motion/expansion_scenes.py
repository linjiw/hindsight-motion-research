"""Propose and freeze additional arm and ducking intervention panels."""
import argparse
import json
from pathlib import Path
import time

import numpy as np

from .batch_scene import materialize
from .budget import main_attempts
from .critical import PROJECT,dump
from .interventions import portal,search_portal


def beam(center,axis,underside,displacement=0.,thickness=.16):
    normal=np.array([-axis[1],axis[0],0.]);center=np.asarray(center)+displacement*normal
    yaw=np.arctan2(axis[1],axis[0]);quaternion=[float(np.cos(yaw/2)),0.,0.,float(np.sin(yaw/2))]
    c=center.copy();c[2]=underside+.05
    obstacles=[dict(shape='box',center_xyz=c.tolist(),quaternion_wxyz=quaternion,full_dimensions_xyz=[thickness,1.8,.1])]
    for sign in (-1,1):
        c=center+sign*.95*normal;c[2]=(underside+.1)/2
        obstacles.append(dict(shape='box',center_xyz=c.tolist(),quaternion_wxyz=quaternion,
                              full_dimensions_xyz=[.16,.10,underside+.1]))
    return obstacles


def search_beam(first,proxies,duck_episode,upright_episode,refine=False,extra_pairs=()):
    from gear_sonic.research.scene_distillation.collision_clearance import recorded_bounds,obstacle_separation
    from gear_sonic.research.scene_distillation.critical_pair_calibration import point_distance
    names=json.loads((first/'metrics/episode-contract.json').read_text())['measured_body_names']
    a,b=[dict(np.load(p)) for p in (duck_episode,upright_episode)]
    episodes=[[a,b]]+[[dict(np.load(path)) for path in pair] for pair in extra_pairs]
    bounds=[np.concatenate([recorded_bounds(proxies,dict(body_names=names,body_xyz=pair[v]['body_xyz'],body_wxyz=pair[v]['body_wxyz'])) for pair in episodes]) for v in (0,1)]
    repetitions=len(episodes);frames_per_repeat=len(a['body_xyz'])
    ids=[i for i,p in enumerate(proxies) if p['body']=='torso_link' and p['kind']=='Capsule']
    points=[];radii=[];point_ids=[]
    for i in ids:
        corners=bounds[1][:,i];edges=corners[:,[4,2,1]]-corners[:,0,None]
        lengths=np.linalg.norm(edges,axis=-1);radius=lengths[0].min()/2;axis_id=int(lengths[0].argmax())
        direction=edges[:,axis_id]/lengths[:,axis_id,None]
        extent=max(0.,lengths[0,axis_id]/2-radius)
        for u in (-1.,0.,1.):
            points.append(corners.mean(1)+u*extent*direction);radii.append(radius);point_ids.append(i)
    points=np.stack(points,axis=1);radii=np.asarray(radii)
    root=a['root_state_w'][:,:3]-a['env_origin'];axis=root[-1]-root[0];axis[2]=0;axis/=np.linalg.norm(axis)
    proposals=[]
    for frame in (range(70,131,5) if refine else (70,85,100,115,130)):
        center=root[frame].copy();center[2]=0
        nominal_top=bounds[1][frame,:,:,2].max()
        settings=[]
        if refine:
            # Search height geometrically at several fixed overlap depths.
            # The upper root of the distance constraint places a bar overhead.
            for thickness in (.08,.12,.16,.24):
                for depth in (.0101,.015,.02,.03):
                    lo,hi=nominal_top-.18,nominal_top+.10
                    for _ in range(16):
                        mid=(lo+hi)/2
                        distances=point_distance(points,beam(center,axis,mid,thickness=thickness)[0])-radii
                        distance=float(distances.reshape(repetitions,frames_per_repeat,-1).min((1,2)).max())
                        if distance<-depth:lo=mid
                        else:hi=mid
                    settings.append(((lo+hi)/2,thickness))
        else:settings=[(h,.16) for h in nominal_top+np.arange(-.16,.061,.01)]
        for underside,thickness in settings:
            obstacles=beam(center,axis,float(underside),thickness=thickness)
            clearance=min(float(obstacle_separation(bounds[0],o).min()) for o in obstacles)
            distances=point_distance(points,obstacles[0])-radii
            per_repeat=distances.reshape(repetitions,frames_per_repeat,-1).min((1,2))
            worst_repeat=int(per_repeat.argmax());block=distances[worst_repeat*frames_per_repeat:(worst_repeat+1)*frames_per_repeat]
            index=np.unravel_index(block.argmin(),block.shape);witness=float(per_repeat.max())
            proposals.append(dict(frame=frame,underside_m=float(underside),thickness_m=thickness,center_xyz=center.tolist(),
                axis_xyz=axis.tolist(),obstacles=obstacles,duck_separation_lower_m=clearance,
                upright_inner_distance_upper_m=witness,upright_witness_body=proxies[point_ids[index[1]]]['body'],
                upright_witness_time_s=index[0]*.02,admitted=bool(clearance>=.03 and witness<=-.01),
                measured_repetitions=repetitions,upright_witness_per_repeat_m=per_repeat.tolist(),
                score=min(clearance-.03,-witness-.01)))
    admitted=sorted([r for r in proposals if r['admitted']],key=lambda r:-r['score'])
    return dict(proposals=proposals,selected=admitted[0] if admitted else None,
                measured_empty_scene_geometry=True,continuous_certificate=False,physical_scene_criticality_verified=False)


def refine_beams(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    earlier=PROJECT/'runs/expansion_proposals_20260915_v1'
    dump(output/'registration.json',dict(registered_unix_s=time.time(),parent=str(earlier),
        reason='Initial beam grid missed the unchanged geometry margins by 1-2 mm',
        minimum_positive_clearance_m=.03,minimum_negative_inner_overlap_m=.01,
        frames=list(range(70,131,5)),thicknesses_m=[.08,.12,.16,.24],
        target_inner_depths_m=[.0101,.015,.02,.03],height_bisection_iterations=16,
        physical_beam_outcomes_seen=0,no_relaxed_acceptance=True,split='development'))
    first=PROJECT/'runs/expansion_preflight_20260915_v1'
    proxies=json.loads((PROJECT/'runs/critical_preflight_20260915_v2/native_collision_proxies.json').read_text())
    accepted=[]
    for pair in ('duck00','duck02'):
        old=json.loads((earlier/f'{pair}.json').read_text());carrier=old['records']['duck']['carrier_id']
        result=search_beam(first,proxies,PROJECT/f'runs/expansion_ducks_20260915_v1/metrics/episode-expand_{carrier:02d}_duck.npz',
            first/f'metrics/episode-expand_{carrier:02d}_tuck.npz',refine=True)
        result.update({k:old[k] for k in ('pair_id','family','source_group','records')})
        dump(output/f'{pair}.json',result)
        if result['selected'] is not None:accepted.append(pair)
        print(json.dumps(dict(pair=pair,admitted=sum(r['admitted'] for r in result['proposals']),selected=result['selected'])),flush=True)
    dump(output/'accepted_pairs.json',accepted)


def propose(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    arm=PROJECT/'runs/expansion_preflight_20260915_v1';duck=PROJECT/'runs/expansion_ducks_20260915_v1'
    proxies=json.loads((PROJECT/'runs/critical_preflight_20260915_v2/native_collision_proxies.json').read_text())
    manifest={r['motion_key']:r for run in (arm,duck) for r in json.loads((run/'manifest.json').read_text())}
    outcomes={r['motion_key']:r for run in (arm,duck) for r in json.loads((run/'metrics/preflight-outcomes.json').read_text())}
    candidates=[('arm02','arm_tuck',2),('arm07','arm_tuck',7),('duck00','duck',0),('duck02','duck',2)]
    dump(output/'registration.json',dict(registered_unix_s=time.time(),candidate_pairs=candidates,
        geometry_only_selection=True,no_physical_outcomes_used=True,minimum_positive_clearance_m=.03,
        minimum_negative_inner_overlap_m=.01,max_new_pairs=4,main_study_global_ceiling=480))
    accepted=[]
    for pair,family,carrier in candidates:
        keys={v:f'expand_{carrier:02d}_{v}' for v in ('tuck','wide')} if family=='arm_tuck' else dict(duck=f'expand_{carrier:02d}_duck',upright=f'expand_{carrier:02d}_tuck')
        assert all(outcomes[k]['empty_scene_tracking_qualified'] for k in keys.values())
        episodes=[outcomes[k]['episode_path'] for k in keys.values()]
        result=(search_portal if family=='arm_tuck' else search_beam)(arm,proxies,*episodes)
        result.update(pair_id=pair,family=family,source_group=manifest[next(iter(keys.values()))]['source_group'],
                      records={v:manifest[k] for v,k in keys.items()})
        dump(output/f'{pair}.json',result)
        print(json.dumps(dict(pair=pair,admitted=sum(r['admitted'] for r in result['proposals']),selected=result['selected'])),flush=True)
        if result['selected'] is not None:accepted.append(pair)
    dump(output/'accepted_pairs.json',accepted)


def prepare(proposals,output):
    eq=PROJECT/'runs/batch_equivalence_20260915_v1/equivalence-audit.json'
    if not json.loads(eq.read_text())['passed']:raise ValueError('Instrument not qualified')
    proposals=Path(proposals);tasks=[];records=[]
    body_names=json.loads((PROJECT/'runs/expansion_preflight_20260915_v1/metrics/episode-contract.json').read_text())['measured_body_names']
    for pair in json.loads((proposals/'accepted_pairs.json').read_text()):
        p=json.loads((proposals/f'{pair}.json').read_text());s=p['selected'];family=p['family'];axis=np.asarray(s['axis_xyz'])
        normal=np.array([-axis[1],axis[0],0.]);rows=p['records'];root=np.load(next(iter(rows.values()))['reference_path'])['qpos'][:,:3]
        for perturbation,offset in enumerate((0.,-.015,.015)):
            for condition in ('critical','relaxed','removed','displaced'):
                displacement=2. if condition=='displaced' else 0.
                obstacles=portal(s['center_xyz'],axis,s['gap_m']+(.60 if condition=='relaxed' else 0.),displacement=displacement) if family=='arm_tuck' else beam(s['center_xyz'],axis,s['underside_m']+(.30 if condition=='relaxed' else 0.),displacement=displacement,thickness=s.get('thickness_m',.16))
                if condition=='removed':obstacles=[]
                for variant,row in rows.items():
                    tasks.append(dict(schema='hindsight_critical_traversal_task_v1',task_id=f'{pair}_{condition}_{variant}_p{perturbation}',
                        pair_id=pair,family=family,variant=variant,condition=condition,perturbation_id=perturbation,
                        initial_root_delta_xyz_m=(offset*normal).tolist(),split='development',source_group=row['source_group'],
                        obstacles=obstacles,body_names=body_names,start_xyz=root[0].tolist(),goal_xyz=root[-1].tolist(),
                        portal_center_xyz=s['center_xyz'],passage_axis_xyz=axis.tolist(),goal_tolerance_m=.25,exit_progress_m=.20,
                        terminal_requirement='Moving arrival through portal; no stop/hold claim',maximum_undesired_normal_force_n=1.,
                        control_deadline_steps=200,construction='Native measured execution geometry; fixed pre-execution selection',
                        scene_criticality_verified=False))
                    records.append(row)
    if not tasks:raise ValueError('No admitted scenes')
    previous=main_attempts()
    if previous+len(tasks)>480:raise ValueError('Main study would exceed registered episode ceiling')
    materialize(tasks,records,output,dict(purpose='Additional source groups and ducking mechanism intervention panels',
        proposals=str(proposals),instrument_equivalence=str(eq),split='development',main_study_previous_episodes=previous,
        main_study_global_ceiling=480,perturbation_offsets_m=[0.,-.015,.015],
        no_replacement=True,no_automatic_retries=True,qualification_thresholds_unchanged=True,
        relation_criterion='All six controls succeed, positive critical succeeds, negative makes mechanism-specific contact, matched measured entry',
        selection='Two qualified new-source arm pairs and two qualified duck pairs, restricted to geometry-admitted proposals'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['propose','prepare','refine_beams']);p.add_argument('paths',nargs='+',type=Path)
    a=p.parse_args();globals()[a.command](*[x.resolve() for x in a.paths])
