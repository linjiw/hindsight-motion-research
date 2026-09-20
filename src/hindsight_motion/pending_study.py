"""Prepare, execute and audit the registered four-case pending-exit comparison."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .complete_task import binding, checked, launch_case
from .core import sha256
from .critical import PROJECT, dump
from .distance_report import audit_case, goal_contrast
from .distance_study import nested_bindings, qualify
from .resource_queue import run as resource_run
from .pending_exit import prefix_contract
from .selection_study import parent_parity


def load_decoded(config):
    decoded = {}
    for family, routes in config['decoded_bank'].items():
        decoded[family] = {}
        for route, record in routes.items():
            with np.load(checked(record)) as data:
                decoded[family][route] = data['joint_position'].copy(), data['joint_velocity'].copy()
    return decoded


def contract_for(config):
    from gear_sonic.research.scene_distillation.duck_motion_bank import MotionCandidate
    bank = json.loads(checked(config['distance_exit_bank']).read_text())
    pairs = {family: tuple(MotionCandidate(spec[k]) for k in ('short', 'loop'))
             for family, spec in bank['families'].items()}
    return prefix_contract(pairs, load_decoded(config), bank['decision_tick'])


def replay(folder, contract, *, enabled, require_exact):
    """Imposed-state wrapper replay; manually rebuild the motor joint arrays."""
    from gear_sonic.research.hindsight_training.observations import rotation_wxyz
    from gear_sonic.research.scene_distillation.duck_composer import native_reference
    from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
    from .pending_composer import PendingExitComposer
    folder = Path(folder)
    config = json.loads((folder / 'config.json').read_text())
    task = json.loads((folder / 'task.json').read_text())
    decoded = load_decoded(config)
    composer, first_changed, changed = None, None, 0
    choices, margins = [], []
    with np.load(folder / 'task/pre-action-poses.npz') as pre, np.load(folder / 'task/selection.npz') as old:
        if len(pre['time_s']) != len(old['reference']):
            raise ValueError('Incomplete reference/state history')
        for i in range(len(pre['time_s'])):
            measured = MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
                pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))
            if composer is None:
                composer = PendingExitComposer(checked(config['distance_exit_bank']), measured,
                    task['goal_xyz'], task['obstacles'], decoded=decoded, contract=contract, enabled=enabled)
            chunk = composer.reference(measured)
            if config['representation_method'] == 'linear29':
                q, v = decoded[composer.family]['loop' if composer.choice else 'short']
                dense = np.minimum(i + np.arange(60), len(q) - 1)
                chunk = replace(chunk, joint_position=q[dense], joint_velocity=v[dense])
            ref = native_reference(chunk, rotation_wxyz(measured.root_wxyz),
                native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()
            different = not np.array_equal(ref, old['reference'][i])
            changed += int(different)
            if different and first_changed is None:
                first_changed = i
            if require_exact:
                np.testing.assert_array_equal(ref, old['reference'][i])
                np.testing.assert_array_equal(composer.last_indices, old['reference_source_indices'][i])
                if (composer.family != str(old['candidate'][i]) or composer.choice != int(old['loop_choice'][i])
                        or composer.last_indices[0] != old['candidate_cursor'][i]):
                    raise ValueError('Recorded choice/index mismatch')
            choices.append(composer.choice)
            # Independent gate arithmetic/schedule, without PendingRequest.observe.
            if contract['decision_tick'] <= i <= contract['latest_accept_tick']:
                _, _, bounds = composer.fk.forward(measured)
                clear = True
                for obstacle in task['obstacles']:
                    local = (bounds - obstacle['center_xyz']) @ rotation_wxyz(obstacle['quaternion_wxyz'])
                    clear &= bool(local[..., 0].min() >= obstacle['full_dimensions_xyz'][0] / 2 + .02)
                margins.append((i, bool(clear)))
        initial = composer.decision
        if initial is None:
            raise ValueError('Decision was never reached')
        accepted = None
        if initial['requested']:
            eligible = margins if enabled else margins[:1]
            accepted = next((tick for tick, clear in eligible if clear), None)
        expected = np.array([int(accepted is not None and i >= accepted) for i in range(len(choices))])
        np.testing.assert_array_equal(choices, expected)
        receipt = json.loads((folder / 'task/distance-exit.json').read_text())
        if receipt['decision'] != initial or receipt['family'] != composer.family:
            raise ValueError('Original request/predictor changed')
        if require_exact and (folder / 'task/pending-exit.json').exists():
            native = json.loads((folder / 'task/pending-exit.json').read_text())
            if native['request_lifecycle'] != composer.pending.receipt() or native['actual_final_choice'] != composer.choice:
                raise ValueError('Native lifecycle audit failed')
    return dict(states=len(choices), issued_reference_exact=changed == 0,
        first_changed_reference_tick=first_changed, changed_reference_rows=changed,
        family=composer.family, original_decision=initial, request_lifecycle=composer.pending.receipt(),
        actual_final_choice=composer.choice, independent_schedule_exact=True,
        composed_indices_exact=True if require_exact else None)


def prepare(output):
    output = Path(output).resolve()
    registration = PROJECT / 'configs/pending_exit_v1.plan.json'
    protocol = PROJECT / 'docs/PENDING_EXIT_PROTOCOL.md'
    reg = json.loads(registration.read_text())
    parent = PROJECT / reg['parent_packet']
    old = json.loads((parent / 'plan.json').read_text())
    summary = json.loads((parent / 'aggregate.json').read_text())
    if summary['native_attempts'] != 4 or summary['execution_state'] != 'complete':
        raise ValueError('Expected complete four-case incumbent packet')
    if sha256(parent / 'aggregate.json') != reg['parent_aggregate_sha256']:
        raise ValueError('Incumbent evidence changed')
    bindings = list(old['bindings']) + list(nested_bindings(summary))
    for item in bindings:
        path = Path(item['path'])
        if not path.is_absolute():
            item['path'] = str(PROJECT / path)
        checked(item)
    config = json.loads((Path(old['cases'][0]['run_dir']) / 'config.json').read_text())
    contract = contract_for(config)
    if contract['latest_accept_tick'] != reg['latest_accept_tick']:
        raise ValueError('Registration differs from actual-array commitment proof')
    output.mkdir(parents=True, exist_ok=False)
    for source, name in [(registration, 'registration.json'), (protocol, 'protocol-before-execution.md')]:
        shutil.copy2(source, output / name)
    dump(output / 'commitment.json', contract)
    cases, offline = [], []
    for original in old['cases']:
        source = Path(original['run_dir'])
        disabled = replay(source, contract, enabled=False, require_exact=True)
        unchanged = original['case_id'] != 'farther-beam_linear29'
        enabled = replay(source, contract, enabled=True, require_exact=unchanged)
        if not unchanged and (enabled['first_changed_reference_tick'] != 134
                              or enabled['request_lifecycle']['accepted_tick'] != 134):
            raise ValueError('Recorded-history pending prediction differs; review before registration')
        offline.append(dict(case_id=original['case_id'], disabled=disabled, enabled_shadow=enabled,
            scope='Recorded incumbent histories; changed forecasts are not physical continuations'))
        folder = output / 'episodes' / original['case_id']
        folder.mkdir(parents=True)
        shutil.copy2(source / 'task.json', folder / 'task.json')
        config = json.loads((source / 'config.json').read_text())
        config.update(task_path=str(folder / 'task.json'), output=str(folder / 'task'),
            pending_contract=binding(output / 'commitment.json'))
        dump(folder / 'config.json', config)
        command = [a.replace(str(source), str(folder)) for a in json.loads((source / 'command.json').read_text())]
        command = [a.replace('hindsight_motion.distance_codec_native.DistanceCodecCallback',
                             'hindsight_motion.pending_native.PendingExitCallback') for a in command]
        dump(folder / 'command.json', command)
        cases.append(dict(original, run_dir=str(folder), parent_run=str(source)))
        bindings += [binding(folder / name) for name in ('task.json', 'config.json', 'command.json')]
    dump(output / 'offline-audit.json', dict(native_attempts=0, training_steps=0, motor_queries=0,
        disabled_replay_states=sum(r['disabled']['states'] for r in offline), rows=offline))
    sources = [PROJECT / ('src/hindsight_motion/' + name + '.py') for name in
        ('pending_exit','pending_composer','pending_native','pending_study')]
    snapshot = output / 'source'; snapshot.mkdir()
    for source in sources:
        shutil.copy2(source, snapshot / source.name)
        bindings += [binding(source), binding(snapshot / source.name)]
    bindings += [binding(p) for p in (registration, protocol, parent / 'plan.json', parent / 'aggregate.json')]
    bindings += [binding(output / name) for name in ('registration.json','protocol-before-execution.md',
                                                   'commitment.json','offline-audit.json')]
    bindings = list({b['path']:b for b in bindings}.values())
    for item in bindings:
        checked(item)
    dump(output / 'plan.json', dict(registration=reg, cases=cases, bindings=bindings, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output), bindings=len(bindings), cases=len(cases),
                         latest_accept_tick=contract['latest_accept_tick'], offline_replay_states=1660)), flush=True)


def run(output):
    output = Path(output).resolve()
    plan = json.loads((output / 'plan.json').read_text())
    with (output / 'execution-start.json').open('x') as f:
        json.dump(dict(unix_s=time.time(), plan_sha256=sha256(output / 'plan.json')), f)
    try:
        for i, case in enumerate(plan['cases']):
            folder = Path(case['run_dir'])
            resource_run([folder], timeout_s=plan['registration']['resource_wait_seconds_per_attempt'], launcher=launch_case)
            if not (folder / 'launch.json').exists():
                break
            valid = qualify(case, plan['cases'][i-1] if i else None)
            if valid and case['case_id'] == 'original-beam_linear29':
                retention = parent_parity(case['parent_run'], folder)
                dump(folder / 'retention-parity.json', retention)
                valid = retention['matched']
            score = json.loads((folder / 'task/task-result.json').read_text())
            print(json.dumps(dict(case=case['case_id'], qualification=valid,
                                  success=score['duck_recover_stop_success'])), flush=True)
            if not valid:
                dump(output / 'stopped.json', dict(reason='control_or_pair_qualification_failed', case=case['case_id']))
                break
    except Exception as error:
        dump(output / 'stopped.json', dict(reason=type(error).__name__, detail=str(error)))
        raise


def analyze(output):
    output = Path(output).resolve()
    public = PROJECT / 'results/pending_exit.json'
    if public.exists() or (output / 'aggregate.json').exists():
        raise FileExistsError('Preserve completed pending-exit analysis')
    plan = json.loads((output / 'plan.json').read_text())
    for record in plan['bindings']:
        checked(record)
    contract = json.loads((output / 'commitment.json').read_text())
    folders = [Path(c['run_dir']) for c in plan['cases']]
    if any((p / 'launch.json').exists() and not (p / 'exit.json').exists() for p in folders):
        raise ValueError('Native queue still running')
    exits = [json.loads((p / 'exit.json').read_text()) for p in folders if (p / 'exit.json').exists()]
    deferred = any((p / 'resource_deferred.json').exists() for p in folders)
    if len(exits) != 4 and not (deferred or (output / 'stopped.json').exists()):
        raise ValueError('Queue has no terminal receipt')
    incumbent = json.loads((PROJECT / plan['registration']['parent_packet'] / 'aggregate.json').read_text())
    rows, comparisons, replays = [], [], []
    for case in plan['cases']:
        row = audit_case(case)
        if row['status'] == 'completed':
            folder = Path(case['run_dir'])
            receipt = json.loads((folder / 'task/pending-exit.json').read_text())
            row['request_lifecycle'] = receipt['request_lifecycle']
            row['actual_final_choice'] = receipt['actual_final_choice']
            row['final_goal_margin_3d_m'] = .5 - row['final_goal_distance_3d_m']
            replays.append(dict(case_id=case['case_id'], **replay(folder, contract, enabled=True, require_exact=True)))
            old = next(r for r in incumbent['rows'] if r['case_id'] == case['case_id'])
            parity = None
            if case['case_id'] != 'farther-beam_linear29':
                parity = parent_parity(case['parent_run'], folder)
                if not parity['matched']:
                    raise ValueError('Previously retained path changed: ' + case['case_id'])
            comparisons.append(dict(case_id=case['case_id'], incumbent_success=old['success'],
                pending_success=row['success'], task_gain=int(row['success'] and not old['success']),
                task_regression=int(old['success'] and not row['success']), unchanged_path_audit=parity,
                actual_trajectory_contrast=goal_contrast(case['parent_run'], folder)))
        rows.append(row)
    contrasts=[]
    for method in plan['registration']['methods']:
        group=[c for c in plan['cases'] if c['method']==method]
        if all(next(r for r in rows if r['case_id']==c['case_id'])['status']=='completed' for c in group):
            contrasts.append(dict(method=method,differences=goal_contrast(group[0]['run_dir'],group[1]['run_dir'])))
    files=[output/n for n in ('plan.json','registration.json','protocol-before-execution.md','commitment.json','offline-audit.json','execution-start.json')]
    for p in folders:
        files += [p/n for n in ('launch.json','exit.json','resource_admission.json','resource_deferred.json',
            'resource_wait.jsonl','parent-parity.json','pair-audit.json','retention-parity.json','task/task-result.json','task/distance-exit.json',
            'task/pending-exit.json','task/codec-entry.json','task/selection.npz','task/pre-action-poses.npz',
            'task/trace.npz','task/robot-poses.npz','task/initial-state.npz','task/dynamics-entry.npz') if (p/n).exists()]
    result=dict(schema='hindsight_pending_exit_results_v1',date='2026-09-20',
        scope='Four development native simulations of bounded pending admission; fixed original endpoint predictor and codec',
        source_ancestries=1,seed=96161,development_only=True,heldout=False,
        execution_state='resource_deferred' if deferred else ('stopped' if (output/'stopped.json').exists() else 'complete'),
        scheduled_cases=4,native_attempts=sum((p/'launch.json').exists() for p in folders),reused_incumbent_cases=4,
        unrun=sum(r['status']=='unrun' for r in rows),infrastructure_failures=sum(e['exit_code']!=0 for e in exits),
        retries=0,training_steps=0,teacher_action_queries=0,historical_main_attempts_consumed=0,
        control_steps=sum(r.get('control_steps',0) for r in rows),physics_samples=sum(r.get('physics_samples',0) for r in rows),
        native_wall_seconds=sum(e['elapsed_s'] for e in exits),rows=rows,incumbent_comparisons=comparisons,
        reference_replay=replays,free_running_goal_contrasts=contrasts,commitment=contract,
        provenance=[dict(path=str(p.relative_to(PROJECT)),sha256=sha256(p)) for p in files],
        incumbent_summary=binding(PROJECT / plan['registration']['parent_packet'] / 'aggregate.json'))
    dump(output / 'aggregate.json',result);dump(public,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','provenance','reference_replay','commitment','incumbent_comparisons')},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run','analyze']);parser.add_argument('output',type=Path)
    args=parser.parse_args();globals()[args.command](args.output)
