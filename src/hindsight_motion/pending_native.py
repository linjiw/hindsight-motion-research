"""Native pending-exit experiment; reuse the original recorder and motor path."""
import json

from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState

from .complete_task import checked
from .continuation_native import cpu, rng_hashes
from .distance_codec_native import DistanceCodecCallback
from .pending_composer import PendingExitComposer


class PendingExitCallback(DistanceCodecCallback):
    def _student_action(self, student, env, teacher, observation, task, noise):
        if self.exit_composer is None:
            robot = env.env.scene['robot']
            d = robot.data
            measured = MeasuredComposerState(cpu(d.root_link_pos_w[0] - env.env.scene.env_origins[0]),
                cpu(d.root_link_quat_w[0]), cpu(d.joint_pos[0]), cpu(d.joint_vel[0]),
                tuple(robot.joint_names), len(self.selection_rows) * .02)
            self.initial_state['proprio'] = cpu(observation['actor_obs'][0])
            self.entry_rng = rng_hashes()
            contract = json.loads(checked(self.config['pending_contract']).read_text())
            self.exit_composer = PendingExitComposer(checked(self.config['distance_exit_bank']),
                measured, task['goal_xyz'], task['obstacles'], decoded=self.decoded, contract=contract)
        return super()._student_action(student, env, teacher, observation, task, noise)

    def _complete_task(self, task, score, output):
        super()._complete_task(task, score, output)
        with (output / 'pending-exit.json').open('x') as f:
            json.dump(dict(schema='hindsight_pending_exit_execution_v1',
                request_lifecycle=self.exit_composer.pending.receipt(),
                actual_final_choice=self.exit_composer.choice,
                contract=self.config['pending_contract'],
                original_decision=self.exit_composer.decision,
                complete_task_success=score['duck_recover_stop_success'],
                controller_profile='latched_request_five_control_tick_commitment_v1'), f, indent=2)
            f.write('\n')
