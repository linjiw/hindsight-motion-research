"""Frozen distance-exit composer with continuous or raw Linear29 motor references."""
import json

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState, execute_packed_reference
from gear_sonic.research.scene_distillation.duck_distance_exit import DistanceExitComposer
from gear_sonic.research.scene_distillation.duck_distance_runtime import DuckDistanceCallback

from .complete_task import checked
from .continuation_native import cpu, rng_hashes
from .distance_codec import motor_chunk, validate_commitment


class DistanceCodecCallback(DuckDistanceCallback):
    def _begin_task(self, env, teacher, task):
        super()._begin_task(env, teacher, task)
        self.method = self.config['representation_method']
        if self.mode != 'public_selection' or self.config.get('intervention'):
            raise ValueError('Only unsupplied public distance choice is registered')
        if self.method not in ('continuous', 'linear29'):
            raise ValueError('Unknown representation')
        self.decoded = {}
        for family, routes in self.config['decoded_bank'].items():
            self.decoded[family] = {}
            for route, item in routes.items():
                with np.load(checked(item)) as data:
                    self.decoded[family][route] = (data['joint_position'].copy(), data['joint_velocity'].copy())
        bank = json.loads(checked(self.config['distance_exit_bank']).read_text())
        validate_commitment(self.decoded, bank['decision_tick'])
        robot, manager = env.env.scene['robot'], env.env.action_manager
        action = manager.get_term('joint_pos')
        self.initial_state = dict(root_state_w=cpu(robot.data.root_state_w[0]),
            joint_pos=cpu(robot.data.joint_pos[0]), joint_vel=cpu(robot.data.joint_vel[0]),
            current_action=cpu(manager.action), previous_action=cpu(manager.prev_action),
            raw_action=cpu(action.raw_actions), processed_action=cpu(action.processed_actions))

    def _student_action(self, student, env, teacher, observation, task, noise):
        robot = env.env.scene['robot']
        d = robot.data
        measured = MeasuredComposerState(cpu(d.root_link_pos_w[0] - env.env.scene.env_origins[0]),
            cpu(d.root_link_quat_w[0]), cpu(d.joint_pos[0]), cpu(d.joint_vel[0]),
            tuple(robot.joint_names), len(self.selection_rows) * .02)
        if self.exit_composer is None:
            self.initial_state['proprio'] = cpu(observation['actor_obs'][0])
            self.entry_rng = rng_hashes()
            self.exit_composer = DistanceExitComposer(checked(self.config['distance_exit_bank']),
                measured, task['goal_xyz'], task['obstacles'])
        chunk = self.exit_composer.reference(measured)
        indices = self.exit_composer.last_indices
        chunk = motor_chunk(chunk, self.decoded, self.exit_composer.family,
                            self.exit_composer.choice, int(indices[0]), self.method)
        reference = native_reference(chunk, rotation_wxyz(measured.root_wxyz),
            native_joint_names=measured.joint_names, native_frame_dt=.1).to(env.device)[None]
        proprio = observation['actor_obs']
        if teacher.running_mean_std is not None:
            proprio = teacher.running_mean_std(proprio)
        tokens, actions = execute_packed_reference(student.motor, student.decoder, reference, proprio)
        self.selection_rows.append(dict(proprio=cpu(proprio[0]), reference=cpu(reference[0]),
            tokens=cpu(tokens[0]), actions=cpu(actions[0]), candidate=np.asarray(self.exit_composer.family),
            candidate_cursor=np.asarray(indices[0]), reference_source_indices=indices.copy(),
            loop_choice=np.asarray(self.exit_composer.choice),
            measured_joint_position=measured.joint_position.copy(),
            measured_joint_velocity=measured.joint_velocity.copy()))
        return actions

    def _score_task(self, task, roots, speeds, forces, fell):
        score = super()._score_task(task, roots, speeds, forces, fell)
        score['execution_profile'] = 'distance_exit_' + self.method + '_motor_reference_v1'
        return score

    def _complete_task(self, task, score, output):
        super()._complete_task(task, score, output)
        np.savez_compressed(output / 'initial-state.npz', **self.initial_state)
        with (output / 'codec-entry.json').open('x') as f:
            json.dump(dict(method=self.method, rng=self.entry_rng,
                initial_family=self.exit_composer.family, initial_costs=self.exit_composer.initial_costs,
                positive_student_training_authorized=False, planner_bank='continuous_in_both_arms'), f, indent=2)
            f.write('\n')
