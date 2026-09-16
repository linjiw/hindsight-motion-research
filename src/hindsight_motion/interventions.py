"""Native-geometry scene proposals and registered physical scene interventions."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time

import joblib
import numpy as np

from .core import sha256
from .critical import PROJECT, dump, launch


def portal(center, axis, gap, *, displacement=0.):
    normal = np.array([-axis[1], axis[0], 0.])
    yaw = np.arctan2(axis[1], axis[0])
    center = np.asarray(center) + displacement*normal
    obstacles = []
    for sign in [-1, 1]:
        c = center + sign*(gap/2 + .30)*normal
        c[2] = .70
        obstacles.append(dict(shape='box', center_xyz=c.tolist(),
                              quaternion_wxyz=[float(np.cos(yaw/2)),0.,0.,float(np.sin(yaw/2))],
                              full_dimensions_xyz=[.16,.60,1.40]))
    return obstacles


def search_portal(first, proxies, tight_episode, wide_episode):
    from gear_sonic.research.scene_distillation.collision_clearance import recorded_bounds, obstacle_separation
    from gear_sonic.research.scene_distillation.critical_pair_calibration import point_distance
    names = json.loads((first/'metrics/episode-contract.json').read_text())['measured_body_names']
    a, b = map(lambda p:dict(np.load(p)), [tight_episode, wide_episode])
    bounds = []
    for poses in [a,b]:
        bounds.append(recorded_bounds(proxies, dict(body_names=names,
                         body_xyz=poses['body_xyz'], body_wxyz=poses['body_wxyz'])))
    # Inner balls are used only inside analytic shapes, never inside mesh bounds.
    inner = [i for i,p in enumerate(proxies) if p['kind'] in ['Capsule','Sphere','Cube','Cylinder']
             and any(s in p['body'] for s in ['elbow','shoulder','wrist'])]
    bb = bounds[1][:,inner]
    edges = bb[:,:, [4,2,1]] - bb[:,:,:1]
    radii = np.linalg.norm(edges,axis=-1).min(axis=-1)/2
    points = bb.mean(axis=-2)
    root = a['root_state_w'][:,:3] - a['env_origin']
    axis = root[-1]-root[0];axis[2]=0;axis /= np.linalg.norm(axis)
    proposals = []
    for frame in [70,85,100,115,130]:
        center = root[frame].copy();center[2]=0
        for gap in np.arange(.44,1.011,.02):
            obstacles = portal(center,axis,gap)
            clearance = min(float(obstacle_separation(bounds[0],o).min()) for o in obstacles)
            distances = np.stack([point_distance(points,o)-radii for o in obstacles],axis=-1)
            witness_index = np.unravel_index(distances.argmin(), distances.shape)
            witness = float(distances[witness_index])
            score = min(clearance-.03, -witness-.01)
            proposals.append(dict(frame=frame, gap_m=float(gap), center_xyz=center.tolist(),
                                  axis_xyz=axis.tolist(), obstacles=obstacles,
                                  tuck_separation_lower_m=clearance,
                                  wide_inner_distance_upper_m=witness,
                                  wide_witness_body=proxies[inner[witness_index[1]]]['body'],
                                  wide_witness_time_s=witness_index[0]*.02,
                                  admitted=bool(clearance>=.03 and witness<=-.01),score=score))
    passing = sorted([p for p in proposals if p['admitted']], key=lambda p:-p['score'])
    return dict(proposals=proposals, selected=passing[0] if passing else None,
                measured_empty_scene_geometry=True, continuous_certificate=False,
                physical_scene_criticality_verified=False)


def prepare(output):
    from gear_sonic.research.scene_distillation.tasks import write_collision_scene
    first = PROJECT/'runs/critical_preflight_20260915_v2'
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    proxies = json.loads((first/'native_collision_proxies.json').read_text())
    metrics = first/'metrics'
    keys = dict(tuck='critical_03_tuck', wide='critical_03_wide')
    outcomes = {r['motion_key']:r for r in json.loads((metrics/'preflight-outcomes.json').read_text())}
    if not all(outcomes[k]['empty_scene_tracking_qualified'] for k in keys.values()):
        raise ValueError('Both alternatives must qualify before scene construction')
    proposal = search_portal(first,proxies,*(metrics/f'episode-{k}.npz' for k in keys.values()))
    dump(output/'all_geometry_proposals.json',proposal)
    selected = proposal['selected']
    if selected is None:
        raise ValueError('No admitted portal; retain proposal failures')
    manifest = {r['motion_key']:r for r in json.loads((first/'manifest.json').read_text())}
    body_names = json.loads((metrics/'episode-contract.json').read_text())['measured_body_names']
    root = np.load(manifest[keys['tuck']]['reference_path'])['qpos'][:,:3]
    axis = np.asarray(selected['axis_xyz']); normal=np.array([-axis[1],axis[0],0.])
    tasks = []
    for perturbation in [0,1,2]:
        # Common explicit perturbations, not random seeds mistaken for changed states.
        delta = [0.,-.015,.015][perturbation]*normal
        for condition in ['critical','relaxed','removed','displaced']:
            gap = selected['gap_m'] + (.60 if condition=='relaxed' else 0.)
            obstacles = [] if condition=='removed' else portal(
                selected['center_xyz'],axis,gap,displacement=2. if condition=='displaced' else 0.)
            for variant,key in keys.items():
                task_id = f'arm03_{condition}_{variant}_p{perturbation}'
                run = output/task_id;run.mkdir();(run/'motions').mkdir()
                row=deepcopy(manifest[key]); source=Path(row['motion_path'])
                shutil.copy2(source,run/'motions'/source.name)
                row['motion_path']=str(run/'motions'/source.name)
                dump(run/'manifest.json',[row])
                joblib.dump({key:dict(length=row['frames'],fps=50)},run/'motions/metadata.pkl')
                scene=run/'scene.usda'
                write_collision_scene(scene,obstacles,root[0],root[-1])
                task=dict(schema='hindsight_critical_traversal_task_v1', task_id=task_id,
                          pair_id='arm03', family='arm_tuck',variant=variant,condition=condition,
                          perturbation_id=perturbation,initial_root_delta_xyz_m=delta.tolist(),
                          split='development', source_group=row['source_group'],
                          obstacles=obstacles, body_names=body_names,
                          scene_path=str(scene),scene_sha256=sha256(scene),
                          start_xyz=root[0].tolist(),goal_xyz=root[-1].tolist(),
                          portal_center_xyz=selected['center_xyz'],passage_axis_xyz=axis.tolist(),
                          goal_tolerance_m=.25,exit_progress_m=.20,
                          terminal_requirement='Moving arrival through portal; no stop/hold claim',
                          maximum_undesired_normal_force_n=1., control_deadline_steps=row['frames'],
                          construction='Native collision bounds of measured empty-plane executions',
                          scene_criticality_verified=False)
                dump(run/'task.json',task)
                lock=json.loads((first/'teacher_and_runtime_contract.json').read_text())
                lock['motion_manifest']=str(run/'manifest.json')
                lock['scene_task_path']=str(run/'task.json')
                lock['runtime_overrides'] += [
                    '++manager_env.config.terrain_type=scene_usd',
                    '++manager_env._target_=hindsight_motion.scene_native.CriticalSceneEnvCfg',
                    f'++manager_env.config.scene_usd_path={scene}',
                    f'++manager_env.config.critical_task_path={run}/task.json',
                    '++callbacks.im_eval._target_=hindsight_motion.scene_native.CriticalSceneCallback']
                dump(run/'teacher_and_runtime_contract.json',lock)
                tasks.append(dict(task_id=task_id,run_dir=str(run),task_path=str(run/'task.json'),
                                  task_sha256=sha256(run/'task.json'),condition=condition,
                                  variant=variant,perturbation_id=perturbation))
    dump(output/'tasks.json',tasks)
    dump(output/'registration.json',dict(schema='hindsight_critical_intervention_registration_v1',
        status='registered_before_execution',created_unix_s=time.time(),pair_count=1,
        independent_source_group_count=1,planned_episode_attempts=len(tasks),
        maximum_episode_attempts=len(tasks),main_study_global_ceiling=480,
        preflight_episodes_separate=48,
        hypothesis='Both alternatives pass controls; only wide arms contact the critical passage',
        primary_outcomes=['native_tracking','pair_resolved_contacts','moving_goal_and_exit'],
        common_state='Identical native root, joints and causal history, with paired lateral perturbation',
        perturbation_offsets_m=[0.,-.015,.015],robot='Nominal dynamics; sensor noise off',
        selection='Carrier 03 supported both preflights, largest explicit arm-width contrast',
        uncertainty='One source group; no population generalization or learned proposer claim',
        no_replacement=True,no_automatic_retries=True))
    print(json.dumps({'prepared':str(output),'tasks':len(tasks),'gap_m':selected['gap_m'],
                      'tuck_clearance_m':selected['tuck_separation_lower_m'],
                      'wide_inner_witness_m':selected['wide_inner_distance_upper_m']}))


def run(output):
    output=Path(output)
    tasks=json.loads((output/'tasks.json').read_text())
    for index,row in enumerate(tasks):
        task=Path(row['task_path'])
        if sha256(task)!=row['task_sha256']:
            raise ValueError('Registered task changed')
        run_dir=Path(row['run_dir'])
        if (run_dir/'launch.json').exists():
            continue  # Resume only unattempted tasks; retain all earlier failures.
        launch(run_dir)
        print(json.dumps({'completed_attempt':index+1,'total':len(tasks),'task':row['task_id']}),flush=True)
        if not (run_dir/'metrics/scene-outcome.json').exists():
            raise RuntimeError(f'Infrastructure failure in {row["task_id"]}; inspect before launching further attempts')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run'])
    parser.add_argument('output',type=Path);args=parser.parse_args()
    globals()[args.command](args.output.resolve())
