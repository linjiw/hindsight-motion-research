"""Recorded-state reference replay and independent distance-task scoring."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from .complete_task import checked
from .core import sha256
from .critical import PROJECT, dump


def replay(folder, method, decoded_paths):
    from gear_sonic.research.hindsight_training.observations import rotation_wxyz
    from gear_sonic.research.scene_distillation.duck_composer import native_reference
    from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
    from gear_sonic.research.scene_distillation.duck_distance_exit import DistanceExitComposer
    folder = Path(folder)
    config = json.loads((folder / 'config.json').read_text())
    task = json.loads(Path(config['task_path']).read_text())
    decoded = {}
    for family, routes in decoded_paths.items():
        decoded[family] = {}
        for route, item in routes.items():
            with np.load(checked(item)) as data:
                decoded[family][route] = data['joint_position'].copy(), data['joint_velocity'].copy()
    composer = None
    qmax = vmax = 0.
    with np.load(folder / 'task/pre-action-poses.npz') as pre, np.load(folder / 'task/selection.npz') as recorded:
        if len(pre['time_s']) != len(recorded['reference']):
            raise ValueError('Incomplete pre-action reference history')
        for i in range(len(pre['time_s'])):
            measured = MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
                pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))
            if composer is None:
                composer = DistanceExitComposer(checked(config['distance_exit_bank']), measured,
                    task['goal_xyz'], task['obstacles'])
            chunk = composer.reference(measured)
            if method == 'linear29':
                q, v = decoded[composer.family]['loop' if composer.choice else 'short']
                # Rebuild independently of the native treatment helper.
                cursor = min(i, len(q) - 1)
                dense = np.minimum(cursor + np.arange(60), len(q) - 1)
                qmax = max(qmax, float(np.max(abs(q[dense] - chunk.joint_position))))
                vmax = max(vmax, float(np.max(abs(v[dense] - chunk.joint_velocity))))
                chunk = replace(chunk, joint_position=q[dense], joint_velocity=v[dense])
            elif method != 'continuous':
                raise ValueError('Unknown replay representation')
            reference = native_reference(chunk, rotation_wxyz(measured.root_wxyz),
                native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()
            np.testing.assert_array_equal(reference, recorded['reference'][i])
            np.testing.assert_array_equal(composer.last_indices, recorded['reference_source_indices'][i])
            if (composer.family != str(recorded['candidate'][i])
                    or composer.choice != int(recorded['loop_choice'][i])
                    or composer.last_indices[0] != recorded['candidate_cursor'][i]):
                raise ValueError('Composed label replay mismatch')
        receipt = json.loads((folder / 'task/distance-exit.json').read_text())
        if receipt['decision'] != composer.decision or receipt['family'] != composer.family:
            raise ValueError('Measured-state decision replay mismatch')
    return dict(states=i + 1, issued_reference_exact=True, composed_indices_exact=True,
        family_choice_decision_exact=True, dense_joint_change_max_rad=qmax,
        dense_velocity_change_max_rad_s=vmax, family=composer.family, decision=composer.decision)


def audit_case(case):
    from gear_sonic.research.scene_distillation.collision_clearance import recorded_bounds
    from gear_sonic.research.scene_distillation.duck_task import envelope_features, score_duck_task
    folder = Path(case['run_dir'])
    row = {k: case[k] for k in ('case_id', 'condition', 'method', 'source_clip')}
    if not (folder / 'launch.json').exists():
        return dict(row, status='unrun')
    exit_record = json.loads((folder / 'exit.json').read_text())
    if exit_record['exit_code'] != 0:
        return dict(row, status='infrastructure_failure', exit_code=exit_record['exit_code'])
    task = json.loads((folder / 'task.json').read_text())
    score = json.loads((folder / 'task/task-result.json').read_text())
    receipt = json.loads((folder / 'task/distance-exit.json').read_text())
    proxies = json.loads(checked(task['duck_contract']['collision_bounds']).read_text())['proxies']
    with np.load(folder / 'task/trace.npz') as trace, np.load(folder / 'task/robot-poses.npz') as poses:
        bounds = recorded_bounds(proxies, {k: poses[k] for k in poses.files})
        torso = list(poses['body_names']).index('torso_link')
        features = envelope_features(bounds, poses['body_wxyz'][:, torso], task)
        n = len(trace['root_xyz'])
        if len(trace['contact_force_w']) != 4 * n:
            raise ValueError('Missing substep contacts')
        for key in ('root_xyz', 'speed', 'contact_force_w'):
            if not np.isfinite(trace[key]).all():
                raise ValueError('Nonfinite physical evidence')
        forces = np.linalg.norm(trace['contact_force_w'], axis=-1).reshape(n, 4, len(trace['body_names']), -1)
        nonfeet = [i for i, name in enumerate(trace['body_names']) if name not in ('left_ankle_roll_link', 'right_ankle_roll_link')]
        floor = forces[:, :, nonfeet, 0].max(axis=(1, 2))
        obstacle = forces[:, :, :, 1:].max(axis=(1, 2, 3)) if forces.shape[-1] > 1 else np.zeros(n)
        undesired = np.maximum(floor, obstacle)
        np.testing.assert_array_equal(undesired, trace['undesired_force'])
        recomputed = score_duck_task(task, trace['root_xyz'], trace['speed'], undesired, features,
            fell=bool((trace['root_xyz'][:, 2] < .25).any()))
        for key, value in recomputed.items():
            if value != score[key]:
                raise ValueError('Independent scorer mismatch: ' + key)
        delta = trace['root_xyz'][-1] - np.asarray(task['goal_xyz'])
        with np.load(folder / 'task/pre-action-poses.npz') as pre:
            direction = np.asarray(task['goal_xyz'])[:2] - pre['root_xyz'][0, :2]
        direction /= np.linalg.norm(direction)
        row.update(status='completed', success=score['duck_recover_stop_success'], control_steps=n,
            physics_samples=4 * n, elapsed_control_time_s=n * .02, stop_reason=score['stop_reason'],
            fell=score['fell'], max_obstacle_force_n=float(obstacle.max()), max_nonfoot_floor_force_n=float(floor.max()),
            final_goal_distance_3d_m=float(np.linalg.norm(delta)), final_goal_error_xy_m=float(np.linalg.norm(delta[:2])),
            final_signed_route_error_m=float(delta[:2] @ direction),
            final_goal_margin_xy_m=.50 - float(np.linalg.norm(delta[:2])),
            final_speed_mps=float(trace['speed'][-1]), independent_score_exact=True,
            task_components={k: score[k] for k in ('passage_success', 'duck_observed', 'recovered',
                'entry_tick', 'clear_tick', 'recovery_tick', 'ordered_hold_ticks', 'stable_stop_success')})
    row.update(family=receipt['family'], decision=receipt['decision'], teacher_queries=receipt['teacher_queries'],
        optimizer_updates=receipt['optimizer_updates'])
    for name, key in [('parent-parity.json', 'parent_parity'), ('pair-audit.json', 'pair_audit')]:
        if (folder / name).exists():
            row[key] = json.loads((folder / name).read_text())
    return row


def goal_contrast(first, second):
    """Actual free-running goal contrasts, not shadow outputs on imposed histories."""
    differences = {}
    for file, keys in [('selection.npz', ('reference', 'tokens', 'actions', 'loop_choice')),
                       ('pre-action-poses.npz', ('root_xyz', 'joint_pos'))]:
        with np.load(Path(first) / 'task' / file) as a, np.load(Path(second) / 'task' / file) as b:
            n = min(len(a[keys[0]]), len(b[keys[0]]))
            for key in keys:
                changed = np.flatnonzero(np.any((a[key][:n] != b[key][:n]).reshape(n, -1), axis=1))
                differences[key] = dict(common_length=n, first_changed_tick=int(changed[0]) if len(changed) else None,
                    changed_rows=len(changed))
    return differences


def analyze(output):
    output = Path(output).resolve()
    public = PROJECT / 'results/distance_codec.json'
    if (output / 'aggregate.json').exists() or public.exists():
        raise FileExistsError('Preserve completed analysis')
    plan = json.loads((output / 'plan.json').read_text())
    for item in plan['bindings']:
        checked(item)
    folders = [Path(c['run_dir']) for c in plan['cases']]
    if any((p / 'launch.json').exists() and not (p / 'exit.json').exists() for p in folders):
        raise ValueError('Native queue running')
    exits = [json.loads((p / 'exit.json').read_text()) for p in folders if (p / 'exit.json').exists()]
    deferred = any((p / 'resource_deferred.json').exists() for p in folders)
    if len(exits) != 4 and not (deferred or (output / 'stopped.json').exists()):
        raise ValueError('Queue lacks a terminal receipt')
    rows = [audit_case(case) for case in plan['cases']]
    replays, pairs, contrasts = [], [], []
    for case, row in zip(plan['cases'], rows):
        if row['status'] == 'completed':
            config = json.loads((Path(case['run_dir']) / 'config.json').read_text())
            replays.append(dict(case_id=case['case_id'], **replay(case['run_dir'], case['method'], config['decoded_bank'])))
    for condition in plan['registration']['conditions']:
        pair = [r for r in rows if r['condition'] == condition]
        if all(r['status'] == 'completed' for r in pair):
            a, b = pair
            pairs.append(dict(condition=condition, continuous_success=a['success'], linear29_success=b['success'],
                task_gain=int(b['success'] and not a['success']), task_regression=int(a['success'] and not b['success']),
                both_reached_decision=a['decision'] is not None and b['decision'] is not None,
                same_family=a['family'] == b['family'], same_chosen_exit=(a['decision'] or {}).get('chosen') == (b['decision'] or {}).get('chosen')))
    for method in plan['registration']['methods']:
        group = [c for c in plan['cases'] if c['method'] == method]
        if all(next(r for r in rows if r['case_id'] == c['case_id'])['status'] == 'completed' for c in group):
            contrasts.append(dict(method=method, differences=goal_contrast(group[0]['run_dir'], group[1]['run_dir'])))
    files = [output / n for n in ('registration.json', 'protocol-before-execution.md', 'plan.json', 'execution-start.json', 'offline-audit.json')]
    for p in folders:
        files += [p / n for n in ('launch.json', 'exit.json', 'resource_admission.json', 'resource_deferred.json',
            'resource_wait.jsonl', 'parent-parity.json', 'pair-audit.json', 'task/task-result.json', 'task/distance-exit.json',
            'task/selection.npz', 'task/trace.npz', 'task/robot-poses.npz', 'task/pre-action-poses.npz',
            'task/dynamics-entry.npz', 'task/initial-state.npz', 'task/codec-entry.json') if (p / n).exists()]
    result = dict(schema='hindsight_distance_codec_results_v1', date='2026-09-19',
        scope=plan['registration']['scope'], development_only=True, heldout=False, source_ancestries=1, seed=96161,
        execution_state='resource_deferred' if deferred else ('stopped' if (output / 'stopped.json').exists() else 'complete'),
        scheduled_cases=4, native_attempts=sum((p / 'launch.json').exists() for p in folders),
        completed_episodes=sum(r['status'] == 'completed' for r in rows), unrun=sum(r['status'] == 'unrun' for r in rows),
        infrastructure_failures=sum(e['exit_code'] != 0 for e in exits), retries=0, training_steps=0, teacher_action_queries=0,
        control_steps=sum(r.get('control_steps', 0) for r in rows), physics_samples=sum(r.get('physics_samples', 0) for r in rows),
        native_wall_seconds=sum(e['elapsed_s'] for e in exits), historical_main_attempts_consumed=0,
        rows=rows, pairs=pairs, reference_replay=replays, free_running_goal_contrasts=contrasts,
        offline_audit=json.loads((output / 'offline-audit.json').read_text()),
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=sha256(p)) for p in files])
    dump(output / 'aggregate.json', result)
    dump(public, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('provenance', 'offline_audit', 'rows')}, indent=2))
