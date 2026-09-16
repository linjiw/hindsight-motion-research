"""Materialize separated static scenes on the native environment-origin grid."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time

import joblib
import numpy as np

from .core import sha256
from .critical import PROJECT,dump,launch


def grid_origins(count,spacing=8.):
    rows=int(np.ceil(count/int(np.sqrt(count))));columns=int(np.ceil(count/rows))
    i,j=np.meshgrid(np.arange(rows),np.arange(columns),indexing='ij')
    return np.c_[-(i.ravel()[:count]-(rows-1)/2)*spacing,
                  (j.ravel()[:count]-(columns-1)/2)*spacing,np.zeros(count)]


def materialize(tasks,records,output,registration):
    from gear_sonic.research.scene_distillation.tasks import write_collision_scene
    if not tasks or len(tasks)!=len(records):
        raise ValueError('Every scene task requires exactly one motion record')
    if len({task['task_id'] for task in tasks})!=len(tasks):
        raise ValueError('Scene task IDs must be unique')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'motions').mkdir();(output/'tasks').mkdir()
    origins=grid_origins(len(tasks));world_obstacles=[];metadata={};manifest=[];bound_tasks=[]
    for i,(task,source) in enumerate(zip(tasks,records)):
        task=deepcopy(task);row=deepcopy(source);key=f'batch_{i:04d}_motion'
        motion=next(iter(joblib.load(row['motion_path']).values()))
        path=output/'motions'/f'{key}.pkl';joblib.dump({key:motion},path,compress=3)
        row.update(motion_key=key,motion_path=str(path),motion_sha256=sha256(path),batch_index=i)
        manifest.append(row);metadata[key]=dict(length=row['frames'],fps=50)
        indices=[]
        for obstacle in task['obstacles']:
            global_obstacle=deepcopy(obstacle)
            global_obstacle['center_xyz']=(np.asarray(obstacle['center_xyz'])+origins[i]).tolist()
            world_obstacles.append(global_obstacle);indices.append(len(world_obstacles))
        local_scene=output/'tasks'/f"{task['task_id']}.usda"
        write_collision_scene(local_scene,task['obstacles'],task['start_xyz'],task['goal_xyz'])
        task.update(scene_path=str(local_scene),scene_sha256=sha256(local_scene),motion_key=key,
                    batch_index=i,env_origin=origins[i].tolist(),world_obstacle_filter_indices=indices)
        dump(output/'tasks'/f"{task['task_id']}.json",task);bound_tasks.append(task)
    world=output/'world.usda'
    write_collision_scene(world,world_obstacles,origins.min(0),origins.max(0))
    batch=dict(schema='separated_native_scene_batch_v1',tasks=bound_tasks,
               env_origins=origins.tolist(),world_scene_path=str(world),world_scene_sha256=sha256(world),
               world_obstacle_count=len(world_obstacles),max_objects=max(len(t['obstacles']) for t in tasks),
               env_spacing_m=8.,measured_entry_tolerance=1e-5,
               isolation='Global static obstacles separated by 8 m environment centres; every foreign contact audited')
    dump(output/'batch.json',batch);dump(output/'manifest.json',manifest)
    joblib.dump(metadata,output/'motions/metadata.pkl')
    lock=json.loads((PROJECT/'runs/critical_preflight_20260915_v2/teacher_and_runtime_contract.json').read_text())
    lock.update(motion_manifest=str(output/'manifest.json'),scene_batch_path=str(output/'batch.json'))
    lock['runtime_overrides'] += [
        '++manager_env._target_=hindsight_motion.batch_native.SeparatedSceneEnvCfg',
        f'++manager_env.config.scene_batch_path={output}/batch.json',
        '++callbacks.im_eval._target_=hindsight_motion.batch_native.SeparatedSceneCallback']
    dump(output/'teacher_and_runtime_contract.json',lock)
    dump(output/'registration.json',{'registered_unix_s':time.time(),'planned_episodes':len(tasks),
                                    **registration,'materialized_unix_s':time.time()})
    print(json.dumps(dict(output=str(output),episodes=len(tasks),world_obstacles=len(world_obstacles))))


def prepare_equivalence(output):
    source=PROJECT/'runs/critical_interventions_20260915_v1'
    entries=json.loads((source/'tasks.json').read_text())
    tasks=[];records=[]
    for entry in entries:
        if entry['perturbation_id']!=0:continue
        run=Path(entry['run_dir']);tasks.append(json.loads((run/'task.json').read_text()))
        records.append(json.loads((run/'manifest.json').read_text())[0])
    materialize(tasks,records,output,dict(purpose='Instrument equivalence to the earlier eight single-scene executions',
        budget_parent=str(PROJECT/'runs/expansion_preflight_20260915_v1/registration.json'),
        counts_as_new_preflight=True,counts_as_new_independent_pairs=False,
        expected_outcomes='Exactly the previous critical/relaxed/removed/displaced success pattern',
        acceptance=dict(common_entry_max_error=1e-5,successful_trajectory_rmse_m=.02,
                        critical_first_contact_time_difference_s=.05,foreign_contact_max_n=1e-6),
        source_baseline=str(source),failure_policy='Retain failure and do not use unvalidated batch results for new claims'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare_equivalence','launch'])
    parser.add_argument('output',type=Path);a=parser.parse_args();globals()[a.command](a.output.resolve())
