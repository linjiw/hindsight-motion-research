"""Exact single-scene interventions with native pair-resolved contact recording."""
import json
from pathlib import Path

import numpy as np
import torch
from scipy.spatial.transform import Rotation
from isaaclab.sensors import ContactSensorCfg

from gear_sonic.envs.manager_env.modular_tracking_env_cfg import ModularTrackingEnvCfg
from .native import CriticalPreflightCallback


class CriticalSceneEnvCfg(ModularTrackingEnvCfg):
    def __init__(self,config,**kwargs):
        super().__init__(config,**kwargs)
        task=json.loads(Path(config['critical_task_path']).read_text())
        paths=['/World/ground/terrain/Structure/Floor']+[
            f'/World/ground/terrain/Obstacles/obstacle_{i+1}' for i in range(len(task['obstacles']))]
        for name in task['body_names']:
            setattr(self.scene,f'critical_contact_{name}',ContactSensorCfg(
                prim_path=f'/World/envs/env_0/Robot/{name}',filter_prim_paths_expr=paths,
                update_period=0.,history_length=0,track_air_time=False,force_threshold=0.))


class CriticalSceneCallback(CriticalPreflightCallback):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.task=json.loads(Path(self.contract['scene_task_path']).read_text())
        self.contact_rows=[]

    def _pre_evaluate_policy(self,reset_env=True):
        super()._pre_evaluate_policy(reset_env)
        if self.env.num_envs != 1:
            raise ValueError('Single-scene collision isolation is required')
        names=list(self.env.env.scene['robot'].body_names)
        if names != self.task['body_names']:
            raise ValueError('Contact body order mismatch')
        self.sensors=[self.env.env.scene.sensors[f'critical_contact_{name}'] for name in names]
        for sensor in self.sensors:
            if sensor.contact_physx_view.filter_count!=len(self.task['obstacles'])+1:
                raise ValueError('Contact filter mapping mismatch')
        self.original_step=self.env.env.sim.step
        def step(*args,**kwargs):
            result=self.original_step(*args,**kwargs)
            forces=np.stack([s.contact_physx_view.get_contact_force_matrix(dt=.005)
                             .cpu().numpy().reshape(-1,3).copy() for s in self.sensors])
            self.contact_rows.append(forces)
            return result
        self.env.env.sim.step=step

    def _pre_eval_env_step(self,actor_state):
        if not self.rows:
            robot=self.env.env.scene['robot']
            state=robot.data.root_state_w.clone()
            state[:,:3] += torch.tensor(self.task['initial_root_delta_xyz_m'],device=state.device)
            robot.write_root_state_to_sim(state)
            self.env.env.scene.update(0.)
            # Rebuild causal history from the perturbed measured entry without a physics step.
            self.env.env.observation_manager.reset()
            obs=self.env.env.observation_manager.compute(update_history=True)
            actor_state['obs']=self.env.process_raw_obs(obs,flatten_dict_obs=True)
            self.model.policy.init_rollout()
        return super()._pre_eval_env_step(actor_state)

    def _post_evaluate_policy(self,eval_res):
        self.env.env.sim.step=self.original_step
        result=super()._post_evaluate_policy(eval_res)
        output=Path(self.output_dir)
        key=self.manifest[0]['motion_key']
        episode=dict(np.load(output/f'episode-{key}.npz'))
        outcome=json.loads((output/'preflight-outcomes.json').read_text())[0]
        forces=np.asarray(self.contact_rows)
        if len(forces)!=4*len(self.rows) or not np.isfinite(forces).all():
            raise ValueError('Contact records do not cover every native physics step')
        valid=episode['before_first_native_failure']
        n=int(valid.sum())
        norm=np.linalg.norm(forces[:4*n],axis=-1)
        nonfeet=[i for i,name in enumerate(self.task['body_names'])
                 if name not in ['left_ankle_roll_link','right_ankle_roll_link']]
        obstacle_peak=float(norm[:,:,1:].max(initial=0))
        floor_peak=float(norm[:,nonfeet,0].max(initial=0))
        root=episode['root_state_w'][:n,:3]-episode['env_origin'][:n]
        goal_distance=float(np.linalg.norm(root[-1]-self.task['goal_xyz']))
        exit_progress=float((root[-1]-self.task['portal_center_xyz'])@self.task['passage_axis_xyz'])
        checks=dict(tracking=outcome['empty_scene_tracking_qualified'],
                    obstacle_contact_free=obstacle_peak<=self.task['maximum_undesired_normal_force_n'],
                    nonfoot_floor_contact_free=floor_peak<=self.task['maximum_undesired_normal_force_n'],
                    moving_goal_reached=goal_distance<=self.task['goal_tolerance_m'],
                    portal_exit_reached=exit_progress>=self.task['exit_progress_m'])
        passed=all(checks.values())
        contacts_path=output/'environment-contacts.npz'
        np.savez_compressed(contacts_path,normal_force_w=forces,body_names=self.task['body_names'],
                            physics_dt_s=.005)
        contact_events=[]
        for body,name in enumerate(self.task['body_names']):
            for obstacle in range(1,len(self.task['obstacles'])+1):
                ticks=np.flatnonzero(norm[:,body,obstacle]>1.)
                if len(ticks):
                    contact_events.append(dict(body=name,obstacle_index=obstacle-1,
                        first_s=float((ticks[0]+1)*.005),last_s=float((ticks[-1]+1)*.005),
                        contact_samples=len(ticks),peak_normal_force_n=float(norm[:,body,obstacle].max())))
        record=dict(task_id=self.task['task_id'],pair_id=self.task['pair_id'],variant=self.task['variant'],
                    condition=self.task['condition'],perturbation_id=self.task['perturbation_id'],
                    checks=checks,scene_passage_verified=passed,terminated=outcome['terminated'],
                    native_progress=outcome['native_progress'],valid_pre_action_rows=n,
                    max_obstacle_normal_force_n=obstacle_peak,max_nonfoot_floor_normal_force_n=floor_peak,
                    final_goal_distance_m=goal_distance,exit_progress_m=exit_progress,
                    mean_body_error_m=outcome['mean_body_error_m'],max_root_xy_error_m=outcome['max_root_xy_error_m'],
                    contact_events=contact_events,contact_dt_s=.005,normal_force_only=True,
                    task_success_profile=self.task['terminal_requirement'],
                    scene_sha256=self.task['scene_sha256'],teacher_sha256=self.contract['teacher_sha256'])
        (output/'scene-outcome.json').write_text(json.dumps(record,indent=2)+'\n')
        mapping=[dict(body_paths=list(s.body_physx_view.prim_paths),
                      filter_paths=list(s.cfg.filter_prim_paths_expr),
                      filter_count=int(s.contact_physx_view.filter_count)) for s in self.sensors]
        (output/'contact-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
        export_views(output,episode,self.task,passed)
        return result


def export_views(output,episode,task,passed,max_objects=2):
    """Public map/goal tokens are computed only from the current measured root."""
    count=len(episode['proprio'])
    root=episode['root_state_w'][:,:3]-episode['env_origin']
    rotations=Rotation.from_quat(episode['root_state_w'][:,[4,5,6,3]]).as_matrix()
    max_objects=max(max_objects,len(task['obstacles']))
    tokens=np.zeros((count,max_objects,13),dtype=np.float32)
    mask=np.zeros((count,max_objects),dtype=bool)
    for i,o in enumerate(task['obstacles']):
        delta=np.asarray(o['center_xyz'])-root
        tokens[:,i,:3]=np.einsum('tji,tj->ti',rotations,delta)
        object_rotation=Rotation.from_quat(np.asarray(o['quaternion_wxyz'])[[1,2,3,0]]).as_matrix()
        local=np.einsum('tji,jk->tik',rotations,object_rotation)
        tokens[:,i,3:9]=local[:,:,:2].reshape(count,6)
        tokens[:,i,9:12]=o['full_dimensions_xyz']
        tokens[:,i,12]=1. # box type code
        mask[:,i]=True
    goal=np.einsum('tji,tj->ti',rotations,np.asarray(task['goal_xyz'])-root)
    np.savez_compressed(output/'actor-view.npz',proprio=episode['proprio'],
                        scene_tokens=tokens,scene_mask=mask,goal_local_xyz=goal,
                        goal_tolerance_m=np.full(count,task['goal_tolerance_m'],np.float32),
                        complete_known_map=np.ones(count,dtype=bool))
    np.savez_compressed(output/'teacher-view.npz',**{k:episode[k] for k in
                        ['future_reference','privileged_state','reference_body_pos']})
    np.savez_compressed(output/'target-view.npz',teacher_action=episode['teacher_action'],
                        teacher_motor_token=episode['teacher_motor_token'],
                        motor_imitation_support=episode['before_first_native_failure'] & passed,
                        passage_support=np.full(count,passed,dtype=bool),
                        before_first_native_failure=episode['before_first_native_failure'])
    (output/'view-contract.json').write_text(json.dumps(dict(
        actor='Measured causal proprioception, complete known map, current local goal only',
        scene_token='13 floats: local center(3), rotation first two columns row-major(6), full size(3), box type(1)',
        scene_padding=f'At most {max_objects} objects; mask false is known absent in this complete-map experiment',
        unknown_space='No partial-observation claim; complete_known_map is true',
        teacher='Privileged state and future reference; never actor input',
        targets='Same-state queried/executed native actions and 64D continuous motor tokens',
        split='development',positive_student_training_authorized=False,
        limitation='Passage-specific support; critical relation requires paired intervention analysis'
    ),indent=2)+'\n')
