"""Native IsaacLab instrumentation; imported only after SimulationApp startup."""
import json
from pathlib import Path

import numpy as np
import torch

from gear_sonic.research.hindsight_training.qualify import TrackingQualificationCallback


class CriticalPreflightCallback(TrackingQualificationCallback):
    def __init__(self, *args, collection_contract, **kwargs):
        super().__init__(*args, **kwargs)
        self.contract_path = Path(collection_contract)
        self.contract = json.loads(self.contract_path.read_text())
        self.manifest = json.loads(Path(self.contract['motion_manifest']).read_text())
        self.rows, self.handles, self.captured = [], [], {}

    def _pre_evaluate_policy(self, reset_env=True):
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        super()._pre_evaluate_policy(reset_env)
        if self.num_total_env_eval_loops != 1:
            raise ValueError('Exactly one complete resident batch required')
        self.alive = torch.ones(self.env.num_envs, dtype=torch.bool, device=self.env.device)
        module = self.model.policy.actor_module
        for name, layer in [('future_reference', module.encoders['g1'].module[0]),
                            ('decoder_input', module.decoders['g1_dyn'].module[0])]:
            def capture(_module, inputs, name=name):
                self.captured[name] = inputs[0].detach().reshape(self.env.num_envs, -1).clone()
            self.handles.append(layer.register_forward_pre_hook(capture))

    def _pre_eval_env_step(self, actor_state):
        if len(self.rows) >= self.contract['max_control_steps']:
            raise RuntimeError('Registered control-step ceiling reached')
        self.captured.clear()
        result = super()._pre_eval_env_step(actor_state)
        inputs = self.captured['decoder_input']
        robot = self.env.env.scene['robot']
        command = self.env.motion_command
        origins = self.env.env.scene.env_origins
        values = dict(proprio=inputs[:, 64:], teacher_motor_token=inputs[:, :64],
                      teacher_action=result['actions'],
                      privileged_state=actor_state['obs']['critic_obs'],
                      future_reference=self.captured['future_reference'],
                      root_state_w=robot.data.root_state_w,
                      env_origin=origins, joint_pos=robot.data.joint_pos,
                      joint_vel=robot.data.joint_vel,
                      body_xyz=robot.data.body_pos_w - origins[:, None],
                      body_wxyz=robot.data.body_quat_w,
                      reference_body_pos=command.body_pos_w - origins[:, None],
                      tracked_body_pos=command.robot_body_pos_w - origins[:, None],
                      before_first_native_failure=self.alive)
        for name, width in [('proprio',930), ('teacher_motor_token',64),
                            ('teacher_action',29), ('future_reference',640)]:
            if values[name].shape != (self.env.num_envs, width):
                raise ValueError(f'Native contract shape mismatch: {name}')
        if not all(torch.isfinite(v).all() for v in values.values()):
            raise ValueError('Nonfinite native record')
        self.rows.append({k:v.detach().cpu().numpy().copy() for k,v in values.items()})
        return result

    def _post_eval_env_step(self, actor_state):
        # Record failure before the base callback mutates dones in-place.
        failure = actor_state['dones'].bool() & ~actor_state['extras']['time_outs'].bool()
        self.alive &= ~failure
        return super()._post_eval_env_step(actor_state)

    def _post_evaluate_policy(self, eval_res):
        result = super()._post_evaluate_policy(eval_res)
        output = Path(self.output_dir)
        arrays = {k:np.stack([r[k] for r in self.rows]) for k in self.rows[0]}
        metrics = eval_res['all_metrics_dict']
        manifest = {r['motion_key']:r for r in self.manifest}
        rows = []
        for i, key in enumerate(metrics['motion_keys']):
            record = manifest[key]
            count = min(record['frames'], len(self.rows))
            episode = {k:v[:count,i] for k,v in arrays.items()}
            # All pre-action records before the first failure are retained, never reset tails.
            valid = episode['before_first_native_failure']
            pred, ref = episode['tracked_body_pos'][valid], episode['reference_body_pos'][valid]
            root_max = float(np.linalg.norm(pred[:,0,:2]-ref[:,0,:2],axis=-1).max())
            body_mean = float(np.linalg.norm(pred-ref,axis=-1).mean())
            terminated = bool(metrics['terminated'][i])
            qualified = (not terminated and root_max <= self.contract['max_root_xy_m']
                         and body_mean <= self.contract['max_body_mean_m'])
            episode['motor_imitation_support'] = valid & qualified
            # These references have no stop/hold requirement and no scene test yet.
            episode['scene_relation_support'] = np.zeros(count, dtype=bool)
            episode['navigation_task_support'] = np.zeros(count, dtype=bool)
            path = output/f'episode-{key}.npz'
            np.savez_compressed(path, **episode)
            rows.append(dict(motion_key=key, carrier_id=record['carrier_id'],
                             source_id=record['source_id'], source_group=record['source_group'],
                             variant=record['variant'], split='development',
                             terminated=terminated, native_progress=float(metrics['progress'][i]),
                             valid_pre_action_rows=int(valid.sum()),
                             mean_body_error_m=body_mean, max_root_xy_error_m=root_max,
                             empty_scene_tracking_qualified=qualified, episode_path=str(path),
                             common_entry_sim_state_verified=False, scene_qualified=False))
        for h in self.handles:
            h.remove()
        (output/'preflight-outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
        (output/'episode-contract.json').write_text(json.dumps(dict(
            schema='hindsight_teacher_episode_preflight_v1', control_dt_s=.02,
            tracked_body_names=list(self.env.motion_command.cmd_body_names),
            measured_joint_names=list(self.env.env.scene['robot'].joint_names),
            measured_body_names=list(self.env.env.scene['robot'].body_names),
            timestamps='Pre-action state and teacher query from the same control tick',
            actor_fields=['proprio'],
            teacher_only_fields=['future_reference','privileged_state','reference_body_pos'],
            target_fields=['teacher_action','teacher_motor_token'],
            provenance_fields=['root_state_w','env_origin','joint_pos','joint_vel'],
            split='development', positive_student_training_authorized=False,
            no_scene_or_task_success_labels=True,
            rows=len(self.rows), environment_transitions=len(self.rows)*self.env.num_envs,
        ),indent=2)+'\n')
        return result
