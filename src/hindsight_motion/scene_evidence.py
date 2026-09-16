"""Shared outcome computation for recorded native scene episodes."""
import numpy as np


def score_episode(task,episode,outcome,forces):
    n=int(episode['before_first_native_failure'].sum())
    if n<1 or len(forces)!=4*len(episode['proprio']) or not np.isfinite(forces).all():
        raise ValueError('Missing finite native contact evidence')
    norm=np.linalg.norm(forces[:4*n],axis=-1)
    nonfeet=[i for i,name in enumerate(task['body_names'])
             if name not in ['left_ankle_roll_link','right_ankle_roll_link']]
    obstacle_peak=float(norm[:,:,1:].max(initial=0));floor_peak=float(norm[:,nonfeet,0].max(initial=0))
    root=episode['root_state_w'][:n,:3]-episode['env_origin'][:n]
    goal=float(np.linalg.norm(root[-1]-task['goal_xyz']))
    progress=float((root[-1]-task['portal_center_xyz'])@task['passage_axis_xyz'])
    checks=dict(tracking=outcome['empty_scene_tracking_qualified'],
        obstacle_contact_free=obstacle_peak<=task['maximum_undesired_normal_force_n'],
        nonfoot_floor_contact_free=floor_peak<=task['maximum_undesired_normal_force_n'],
        moving_goal_reached=goal<=task['goal_tolerance_m'],portal_exit_reached=progress>=task['exit_progress_m'])
    events=[]
    for i,name in enumerate(task['body_names']):
        for j in range(1,len(task['obstacles'])+1):
            ticks=np.flatnonzero(norm[:,i,j]>1.)
            if len(ticks):events.append(dict(body=name,obstacle_index=j-1,
                first_s=float((ticks[0]+1)*.005),last_s=float((ticks[-1]+1)*.005),
                contact_samples=len(ticks),peak_normal_force_n=float(norm[:,i,j].max())))
    return dict(task_id=task['task_id'],pair_id=task['pair_id'],family=task['family'],
        variant=task['variant'],condition=task['condition'],perturbation_id=task['perturbation_id'],
        checks=checks,scene_passage_verified=all(checks.values()),terminated=outcome['terminated'],
        native_progress=outcome['native_progress'],valid_pre_action_rows=n,
        max_obstacle_normal_force_n=obstacle_peak,max_nonfoot_floor_normal_force_n=floor_peak,
        final_goal_distance_m=goal,exit_progress_m=progress,mean_body_error_m=outcome['mean_body_error_m'],
        max_root_xy_error_m=outcome['max_root_xy_error_m'],contact_events=events,
        contact_dt_s=.005,normal_force_only=True,task_success_profile=task['terminal_requirement'],
        scene_sha256=task['scene_sha256'])
