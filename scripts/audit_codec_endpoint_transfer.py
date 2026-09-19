"""Exploratory offline endpoint compatibility after the frozen codec comparison.

No calibration fit, controller change, motor query or new native execution.
"""
import json
from pathlib import Path
import shutil

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
from gear_sonic.research.scene_distillation.duck_endpoint_model import ExecutedEndpointComposer
from hindsight_motion.complete_task import binding, checked
from hindsight_motion.critical import PROJECT, RUNTIME, dump
from hindsight_motion.distance_study import nested_bindings


def measured(pre, i):
    return MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
        pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))


def main():
    packet = PROJECT / 'runs/distance_codec_20260919_admission02'
    source = json.loads((packet / 'aggregate.json').read_text())
    if source['execution_state'] != 'complete' or source['completed_episodes'] != 4:
        raise ValueError('Complete the registered four-case comparison first')
    output = PROJECT / 'runs/endpoint_codec_transfer_20260919_v1'
    public = PROJECT / 'results/endpoint_codec_transfer.json'
    if public.exists():
        raise FileExistsError('Preserve exploratory analysis')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output / 'source.py')
    plan = json.loads((packet / 'plan.json').read_text())
    sibling = Path('/home/linjiw/research-data/m2s-duck-endpoint-calibration-20260919-v1')
    model_path = sibling / 'endpoint-model.json'
    model = json.loads(model_path.read_text())
    sibling_analysis = json.loads((sibling / 'analysis.json').read_text())
    bindings = [binding(p) for p in (Path(__file__), packet / 'aggregate.json', packet / 'plan.json',
        model_path, sibling / 'analysis.json', RUNTIME / 'gear_sonic/research/scene_distillation/duck_endpoint_model.py')]
    bindings += list(nested_bindings(model))
    rows, shadows, gates = [], [], []
    for case in plan['cases']:
        folder = Path(case['run_dir'])
        config = json.loads((folder / 'config.json').read_text())
        task = json.loads((folder / 'task.json').read_text())
        score = next(r for r in source['rows'] if r['case_id'] == case['case_id'])
        bindings += [binding(folder / n) for n in ('config.json', 'task.json', 'task/pre-action-poses.npz', 'task/trace.npz')]
        with np.load(folder / 'task/pre-action-poses.npz') as pre, np.load(folder / 'task/trace.npz') as trace:
            controller = ExecutedEndpointComposer(checked(config['distance_exit_bank']), measured(pre, 0),
                task['goal_xyz'], task['obstacles'], endpoint_path=model_path)
            if len(task['obstacles']) != 1 or task['obstacles'][0]['shape'] != 'beam':
                raise ValueError('Gate audit expects the frozen single beam')
            obstacle = task['obstacles'][0]
            rotation = rotation_wxyz(obstacle['quaternion_wxyz'])
            curves, first_open, at_decision = [], None, None
            for i in range(len(pre['time_s'])):
                _, _, bounds = controller.fk.forward(measured(pre, i))
                local = (bounds - obstacle['center_xyz']) @ rotation
                margin = local[..., 0].min() - obstacle['full_dimensions_xyz'][0] / 2 - .02
                limiting_proxy = int(np.argmin(local[..., 0]) // 8)
                body_index = controller.fk.proxies[limiting_proxy][0]
                record = dict(tick=i, clearance_gate_margin_m=float(margin),
                    limiting_body=controller.fk.body_names[body_index])
                if margin >= 0 and first_open is None:
                    first_open = i
                if i == model['decision_tick']:
                    at_decision = record
                if 110 <= i <= 150:
                    curves.append(record)
            if bool(at_decision['clearance_gate_margin_m'] >= 0) != score['decision']['measured_clear']:
                raise ValueError('Independent clearance gate disagrees with recorded choice')
            gates.append(dict(case_id=case['case_id'], method=case['method'], condition=case['condition'],
                decision=at_decision, first_measured_gate_open_tick=first_open,
                fixed_decision_tick=model['decision_tick'], gate_margin_curve=curves,
                scope='Measured-state FK gate audit; later opening is not an executed retry or qualified transition'))
            if score['decision'] is None:
                rows.append(dict(case_id=case['case_id'], endpoint_audit='no recorded decision'))
                continue
            tick = score['decision']['tick']
            displacement = (controller.executed_loop_displacement if score['decision']['chosen']
                            else controller.short_displacement)
            predicted = pre['root_xyz'][tick] + displacement
            actual_mean = trace['root_xyz'][-50:].mean(axis=0)
            residual = predicted - actual_mean
            route = np.asarray(task['goal_xyz'])[:2] - pre['root_xyz'][0, :2]
            route /= np.linalg.norm(route)
            rows.append(dict(case_id=case['case_id'], method=case['method'], condition=case['condition'],
                chosen_exit=score['decision']['chosen'], complete_task_success=score['success'],
                endpoint_window='mean of final 50 post-action root frames',
                final_window_is_successful_hold=bool(score['success'] and score['task_components']['ordered_hold_ticks'] == 50),
                calibrated_model_residual_xy_m=float(np.linalg.norm(residual[:2])),
                signed_prediction_minus_actual_route_m=float(residual[:2] @ route),
                original_predictor_goal_errors_xy_m=score['decision']['predicted_terminal_xy_errors'],
                final_goal_margin_xy_m=score['final_goal_margin_xy_m']))
            if case['condition'] != 'original-beam':
                continue
            for item in sibling_analysis['rows']:
                if item['scene'] != 'beam' or item['arm'] != 'calibrated':
                    continue
                target_path = checked(item['task'])
                target = json.loads(target_path.read_text())
                if (target['obstacles'] != task['obstacles']
                        or binding(target['scene_usd_path']) != binding(task['scene_usd_path'])):
                    raise ValueError('Shadow requests must share fixed scene geometry')
                bindings.append(binding(target_path))
                shadow = ExecutedEndpointComposer(checked(config['distance_exit_bank']), measured(pre, 0),
                    target['goal_xyz'], target['obstacles'], endpoint_path=model_path)
                for i in range(model['decision_tick'] + 1):
                    shadow.reference(measured(pre, i))
                decision = shadow.decision
                shadows.append(dict(method=case['method'], goal_offset_mm=item['goal_offset_mm'],
                    history='imposed original-goal actual history through decision; no new physical continuation',
                    measured_clear=decision['measured_clear'], requested=decision['requested'], chosen=decision['chosen'],
                    predicted_terminal_xy_errors=decision['predicted_terminal_xy_errors'],
                    loop_minus_short_predicted_error_m=decision['predicted_terminal_xy_errors'][1] - decision['predicted_terminal_xy_errors'][0]))
    bindings = list({b['path']: b for b in bindings}.values())
    for item in bindings:
        checked(item)
    dump(output / 'bindings.json', bindings)
    result = dict(schema='hindsight_endpoint_codec_transfer_audit_v1', date='2026-09-19', exploratory=True,
        scope='Post-result endpoint-model compatibility and imposed-history choice audit; not calibrated Linear29 execution',
        new_native_attempts=0, teacher_action_queries=0, motor_action_queries=0, training_steps=0, fitted_endpoint_vectors=0,
        actual_history_endpoint_audit=rows, measured_gate_audit=gates, calibrated_choice_shadows=shadows,
        limitations='One ancestry/reset/seed. Continuous calibration reuses familiar stopping behavior. Final-window residuals are not final-position errors, uncertainty bounds or independent samples. Shadow requests do not establish complete-task success.',
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=binding(p)['sha256'])
            for p in (Path(__file__), output / 'source.py', output / 'bindings.json', packet / 'aggregate.json')])
    dump(output / 'aggregate.json', result)
    dump(public, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
