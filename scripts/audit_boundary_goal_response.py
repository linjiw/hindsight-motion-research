"""Exploratory goal response on completed shift/farther histories; no physics."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
from gear_sonic.research.scene_distillation.duck_motion_bank import load_bank, PublicMotionSelector
from hindsight_motion.complete_task import binding, checked
from hindsight_motion.critical import PROJECT, dump
from hindsight_motion.selection_codec import gather_reference


def main():
    packet = PROJECT / 'runs/selection_boundary_20260919_v1'
    local, public = packet / 'goal-response.json', PROJECT / 'results/selection_boundary_goal.json'
    if local.exists() or public.exists():
        raise FileExistsError('Preserve completed diagnostic')
    plan = json.loads((packet / 'plan.json').read_text())
    aggregate = json.loads((packet / 'aggregate.json').read_text())
    completed = {r['case_id'] for r in aggregate['rows'] if r['status'] == 'completed'}
    # Bind the completed outcomes: this analysis is explicitly post-result.
    parents = [binding(packet / 'aggregate.json'), binding(__file__)]
    original = PROJECT / 'runs/selection_codec_20260919_v1/episodes/shift_earlier_100mm_continuous/task.json'
    base_task = json.loads(original.read_text())
    parents.append(binding(original))
    farther = next(c for c in plan['cases'] if c['condition'] == 'farther600-beam')
    farther_path = Path(farther['run_dir']) / 'task.json'
    farther_goal = json.loads(farther_path.read_text())['goal_xyz']
    parents.append(binding(farther_path))
    rows = []
    for case in plan['cases']:
        if case['condition'] not in ('earlier200-beam', 'farther600-beam') or case['case_id'] not in completed:
            continue
        folder = Path(case['run_dir'])
        task = json.loads((folder / 'task.json').read_text())
        goals = [base_task['goal_xyz'], farther_goal]
        actual_goal_index = 1 if case['condition'] == 'farther600-beam' else 0
        np.testing.assert_array_equal(task['goal_xyz'], goals[actual_goal_index])
        config = json.loads((folder / 'config.json').read_text())
        parents += [binding(folder / n) for n in ('config.json', 'task.json', 'task/selection.npz', 'task/pre-action-poses.npz')]
        with np.load(folder / 'task/pre-action-poses.npz') as pre, np.load(folder / 'task/selection.npz') as recorded:
            selectors = None
            different = dict(continuous=0, linear29=0)
            maximum = dict(continuous=0., linear29=0.)
            changed_candidates = changed_indices = 0
            for i in range(len(pre['time_s'])):
                measured = MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
                    pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))
                if selectors is None:
                    selectors = [PublicMotionSelector(load_bank(checked(config['selection']['bank'])), measured,
                                 goal, task['obstacles']) for goal in goals]
                    decoded = {}
                    for name, item in config['decoded_bank'].items():
                        with np.load(checked(item)) as data:
                            decoded[name] = data['joint_position'].copy(), data['joint_velocity'].copy()
                chunks = [s.reference(measured) for s in selectors]
                changed_candidates += int(selectors[0].candidate.name != selectors[1].candidate.name)
                changed_indices += int(not np.array_equal(selectors[0].last_source_indices, selectors[1].last_source_indices))
                for method in ('continuous', 'linear29'):
                    references = []
                    for selector, chunk in zip(selectors, chunks):
                        if method == 'linear29':
                            q, v = gather_reference(*decoded[selector.candidate.name], selector.source_indices[selector.consumed - 1:])
                            chunk = replace(chunk, joint_position=q, joint_velocity=v)
                        references.append(native_reference(chunk, rotation_wxyz(measured.root_wxyz),
                            native_joint_names=measured.joint_names, native_frame_dt=.1).numpy())
                    different[method] += int(not np.array_equal(*references))
                    maximum[method] = max(maximum[method], float(np.max(abs(references[0] - references[1]))))
                    if method == case['method']:
                        np.testing.assert_array_equal(references[actual_goal_index], recorded['reference'][i])
            rows.append(dict(history=case['case_id'], recorded_states=i + 1, methods_tested=['continuous', 'linear29'],
                changed_candidate_rows=changed_candidates, changed_index_rows=changed_indices,
                changed_reference_rows=different,
                reference_max_abs_difference=maximum, actual_method_actual_goal_reference_exact=True,
                goal_displacement_m=float(np.linalg.norm(np.asarray(goals[1]) - goals[0]))))
    if not rows:
        raise ValueError('No completed shift/farther histories')
    result = dict(schema='hindsight_boundary_goal_response_v1', date='2026-09-19',
        analysis='Exploratory after the registered native results; original and farther goal on identical actual histories and map',
        scope='Reference response only. Alternate-goal physics and alternate-method physics on these same states were not executed.',
        native_attempts=0, teacher_action_queries=0, training_steps=0, rows=rows,
        provenance=[dict(path=str(Path(p['path']).relative_to(PROJECT)), sha256=p['sha256']) for p in parents])
    dump(local, result)
    dump(public, result)
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
