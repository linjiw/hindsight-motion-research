"""Fixed public selector with a separately versioned motor-reference treatment."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState, execute_packed_reference
from gear_sonic.research.scene_distillation.duck_motion_bank import PublicMotionSelector
from gear_sonic.research.scene_distillation.duck_selection_runtime import DuckSelectionCallback

from .complete_task import checked
from .continuation_native import cpu, rng_hashes
from .selection_codec import gather_reference


class SelectionCodecCallback(DuckSelectionCallback):
    def _begin_task(self, env, teacher, task):
        super()._begin_task(env, teacher, task)
        if self.mode != 'public_selection':
            raise ValueError('Only the registered public selector is supported')
        self.method = self.config['representation_method']
        if self.method not in ('continuous', 'linear29'):
            raise ValueError('Unknown representation')
        self.decoded = {}
        for name, item in self.config['decoded_bank'].items():
            with np.load(checked(item)) as d:
                self.decoded[name] = (d['joint_position'].copy(), d['joint_velocity'].copy())
        robot, manager = env.env.scene['robot'], env.env.action_manager
        action = manager.get_term('joint_pos')
        self.initial_state = dict(root_state_w=cpu(robot.data.root_state_w[0]),
                                  joint_pos=cpu(robot.data.joint_pos[0]), joint_vel=cpu(robot.data.joint_vel[0]),
                                  current_action=cpu(manager.action), previous_action=cpu(manager.prev_action),
                                  raw_action=cpu(action.raw_actions), processed_action=cpu(action.processed_actions))

    def _student_action(self, student, env, teacher, observation, task, noise):
        data = env.env.scene['robot'].data
        names = tuple(env.env.scene['robot'].joint_names)
        measured = MeasuredComposerState(
            cpu(data.root_link_pos_w[0]-env.env.scene.env_origins[0]), cpu(data.root_link_quat_w[0]),
            cpu(data.joint_pos[0]), cpu(data.joint_vel[0]), names, len(self.selection_rows)*.02)
        if self.selector is None:
            self.initial_state['proprio'] = cpu(observation['actor_obs'][0])
            self.entry_rng = rng_hashes()
            self.selector = PublicMotionSelector(self.candidates, measured, task['goal_xyz'], task['obstacles'])
        chunk = self.selector.reference(measured)
        start = self.selector.consumed-1
        dense = self.selector.source_indices[start:].copy()
        if len(dense) != len(chunk.joint_position):
            raise ValueError('Commitment provenance length mismatch')
        if self.method == 'linear29':
            q, v = gather_reference(*self.decoded[self.selector.candidate.name], dense)
            chunk = replace(chunk, joint_position=q, joint_velocity=v)
        reference = native_reference(chunk, rotation_wxyz(measured.root_wxyz),
                                     native_joint_names=names, native_frame_dt=.1).to(env.device)[None]
        proprio = observation['actor_obs']
        if teacher.running_mean_std is not None:
            proprio = teacher.running_mean_std(proprio)
        tokens, actions = execute_packed_reference(student.motor, student.decoder, reference, proprio)
        self.selection_rows.append(dict(
            proprio=cpu(proprio[0]), reference=cpu(reference[0]), tokens=cpu(tokens[0]), actions=cpu(actions[0]),
            candidate=np.asarray(self.selector.candidate.name),
            candidate_cursor=np.asarray(self.selector.last_source_indices[0]),
            reference_source_indices=self.selector.last_source_indices.copy(),
            measured_joint_position=measured.joint_position.copy(), measured_joint_velocity=measured.joint_velocity.copy()))
        return actions

    def _score_task(self, task, roots, speeds, forces, fell):
        score = super()._score_task(task, roots, speeds, forces, fell)
        score['execution_profile'] = 'public_selection_'+self.method+'_motor_reference_v1'
        return score

    def _complete_task(self, task, score, output):
        super()._complete_task(task, score, output)
        np.savez_compressed(output/'initial-state.npz', **self.initial_state)
        (output/'codec-entry.json').write_text(json.dumps(dict(method=self.method, rng=self.entry_rng,
            positive_student_training_authorized=False, planner_bank='continuous_in_both_arms'), indent=2)+'\n')
