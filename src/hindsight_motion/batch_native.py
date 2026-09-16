"""Batched static-scene instrumentation with explicit environment/contact indexing."""
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import torch
from isaaclab.sensors import ContactSensorCfg
from isaaclab.terrains import TerrainImporterCfg

from gear_sonic.envs.manager_env.modular_tracking_env_cfg import ModularTrackingEnvCfg
from .native import CriticalPreflightCallback
from .scene_evidence import score_episode
from .scene_native import export_views


class SeparatedSceneEnvCfg(ModularTrackingEnvCfg):
    def __init__(self,config,**kwargs):
        # Construct normal plane configuration, then replace the terrain with a
        # deliberately authored world containing disjoint per-environment scenes.
        super().__init__(config,**kwargs)
        batch=json.loads(Path(config['scene_batch_path']).read_text())
        self.scene.terrain=TerrainImporterCfg(prim_path='/World/ground',terrain_type='usd',
            usd_path=batch['world_scene_path'],env_spacing=batch['env_spacing_m'],collision_group=-1,debug_vis=False)
        self.sim.physics_material=self.scene.terrain.physics_material
        paths=['/World/ground/terrain/Structure/Floor']+[
            f'/World/ground/terrain/Obstacles/obstacle_{i+1}' for i in range(batch['world_obstacle_count'])]
        for name in batch['tasks'][0]['body_names']:
            setattr(self.scene,f'batch_contact_{name}',ContactSensorCfg(
                prim_path=f'{{ENV_REGEX_NS}}/Robot/{name}',filter_prim_paths_expr=paths,
                update_period=0.,history_length=0,track_air_time=False,force_threshold=0.))


class SeparatedSceneCallback(CriticalPreflightCallback):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.batch=json.loads(Path(self.contract['scene_batch_path']).read_text())
        self.contacts=[];self.foreign_peaks=[]

    def _pre_evaluate_policy(self,reset_env=True):
        super()._pre_evaluate_policy(reset_env)
        n=self.env.num_envs;device=self.env.device
        if n!=len(self.batch['tasks']):raise ValueError('Batch size mismatch')
        if hashlib.sha256(Path(self.batch['world_scene_path']).read_bytes()).hexdigest()!=self.batch['world_scene_sha256']:
            raise ValueError('World changed')
        origins=self.env.env.scene.env_origins.cpu().numpy()
        np.testing.assert_allclose(origins,self.batch['env_origins'],atol=0,rtol=0)
        keys=list(self.env._motion_lib.curr_motion_keys)
        if keys!=[t['motion_key'] for t in self.batch['tasks']]:raise ValueError('Scene/motion assignment mismatch')
        self.body_names=list(self.env.env.scene['robot'].body_names)
        if self.body_names!=self.batch['tasks'][0]['body_names']:raise ValueError('Body order mismatch')
        filters=1+self.batch['world_obstacle_count'];slots=1+self.batch['max_objects']
        gather=np.zeros((n,slots),dtype=int);mask=np.zeros((n,slots),dtype=bool)
        allowed=np.zeros((n,filters),dtype=bool);self.sensor_order=[];self.sensors=[];mapping=[]
        for i,task in enumerate(self.batch['tasks']):
            ids=[0]+task['world_obstacle_filter_indices']
            gather[i,:len(ids)]=ids;mask[i,:len(ids)]=True;allowed[i,ids]=True
        self.gather=torch.tensor(gather,device=device)
        self.slot_mask=torch.tensor(mask,device=device)
        self.foreign_mask=torch.tensor(~allowed,device=device)
        for name in self.body_names:
            sensor=self.env.env.scene.sensors[f'batch_contact_{name}']
            if sensor.contact_physx_view.filter_count!=filters:raise ValueError('Filter count mismatch')
            paths=list(sensor.body_physx_view.prim_paths)
            env_indices=[int(re.search(r'/env_(\d+)/',path)[1]) for path in paths]
            if sorted(env_indices)!=list(range(n)):raise ValueError('Ambiguous sensor environment indexing')
            order=np.argsort(env_indices)
            self.sensor_order.append(torch.tensor(order,device=device));self.sensors.append(sensor)
            mapping.append(dict(body=name,body_paths=paths,row_environment_indices=env_indices,
                                reorder_to_environment_index=order.tolist(),filter_paths=list(sensor.cfg.filter_prim_paths_expr)))
        output=Path(self.output_dir);output.mkdir(parents=True,exist_ok=True)
        (output/'contact-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
        self.original_step=self.env.env.sim.step
        def step(*args,**kwargs):
            result=self.original_step(*args,**kwargs)
            all_forces=torch.stack([s.contact_physx_view.get_contact_force_matrix(dt=.005)
                .reshape(n,filters,3)[order] for s,order in zip(self.sensors,self.sensor_order)],dim=1)
            foreign=all_forces*self.foreign_mask[:,None,:,None]
            self.foreign_peaks.append(float(torch.linalg.vector_norm(foreign,dim=-1).max()))
            own=torch.gather(all_forces,2,self.gather[:,None,:,None].expand(-1,len(self.body_names),-1,3))
            own=own*self.slot_mask[:,None,:,None]
            self.contacts.append(own.cpu().numpy().copy())
            return result
        self.env.env.sim.step=step

    def _pre_eval_env_step(self,actor_state):
        if not self.rows:
            robot=self.env.env.scene['robot'];state=robot.data.root_state_w.clone()
            state[:,:3]+=torch.tensor([t['initial_root_delta_xyz_m'] for t in self.batch['tasks']],device=state.device)
            robot.write_root_state_to_sim(state);self.env.env.scene.update(0.)
            self.env.env.observation_manager.reset()
            obs=self.env.env.observation_manager.compute(update_history=True)
            actor_state['obs']=self.env.process_raw_obs(obs,flatten_dict_obs=True)
            self.model.policy.init_rollout()
        return super()._pre_eval_env_step(actor_state)

    def _post_evaluate_policy(self,eval_res):
        self.env.env.sim.step=self.original_step
        result=super()._post_evaluate_policy(eval_res)
        output=Path(self.output_dir);forces=np.asarray(self.contacts)
        if forces.shape[0]!=4*len(self.rows):raise ValueError('Missing physics samples')
        if max(self.foreign_peaks)>1e-6:raise ValueError('Foreign environment contact invalidates batch isolation')
        outcomes={r['motion_key']:r for r in json.loads((output/'preflight-outcomes.json').read_text())}
        scores=[]
        for i,task in enumerate(self.batch['tasks']):
            episode=dict(np.load(output/f"episode-{task['motion_key']}.npz"))
            local=forces[:,i,:,:len(task['obstacles'])+1]
            score=score_episode(task,episode,outcomes[task['motion_key']],local)
            score.update(teacher_sha256=self.contract['teacher_sha256'],world_scene_sha256=self.batch['world_scene_sha256'])
            task_output=output/task['task_id'];task_output.mkdir()
            np.savez_compressed(task_output/'environment-contacts.npz',normal_force_w=local,
                                body_names=self.body_names,physics_dt_s=.005)
            (task_output/'scene-outcome.json').write_text(json.dumps(score,indent=2)+'\n')
            export_views(task_output,episode,task,score['scene_passage_verified'],max_objects=max(2,self.batch['max_objects']))
            scores.append(score)
        (output/'scene-outcomes.json').write_text(json.dumps(scores,indent=2)+'\n')
        (output/'isolation-audit.json').write_text(json.dumps(dict(
            maximum_foreign_obstacle_force_n=max(self.foreign_peaks),physics_samples=len(forces),
            origins_match_authored_scenes=True,motion_assignment_matches=True,
            per_body_sensor_order_resolved=True,world_scene_sha256=self.batch['world_scene_sha256']),indent=2)+'\n')
        return result
