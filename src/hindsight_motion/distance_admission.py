"""Separate zero-launch successor admission; preserve the frozen distance study."""
import argparse
import json
from pathlib import Path
import shutil
import time

from .boundary_admission import validate_parent
from .complete_task import binding, checked
from .core import sha256
from .critical import PROJECT, dump
from .distance_report import audit_case, goal_contrast, replay
from .distance_study import run as frozen_run


def validate(parent, admission):
    parent = Path(parent)
    if sha256(parent / 'plan.json') != admission['parent_plan_sha256']:
        raise ValueError('Original distance plan changed')
    plan, summary, pending = validate_parent(parent, admission)
    if summary['native_attempts'] != 0 or any(r['status'] != 'unrun' for r in summary['rows']):
        raise ValueError('This admission requires a zero-launch parent')
    for field, key in [('maximum_control_steps_total', 'maximum_new_control_steps'),
                       ('maximum_physics_steps_total', 'maximum_new_physics_samples'),
                       ('maximum_wall_seconds_per_attempt', 'maximum_wall_seconds_per_attempt'),
                       ('resource_wait_seconds_per_attempt', 'resource_wait_seconds_per_attempt'),
                       ('retries', 'retries'), ('training_steps', 'training_steps')]:
        if plan['registration'][field] != admission[key]:
            raise ValueError('Frozen limit changed: ' + field)
    return plan, summary, pending


def prepare(registration):
    registration = Path(registration).resolve()
    admission = json.loads(registration.read_text())
    parent = PROJECT / admission['parent_packet']
    old, summary, pending = validate(parent, admission)
    if json.loads((PROJECT / admission['scientific_registration']).read_text()) != old['registration']:
        raise ValueError('Scientific registration changed')
    output = PROJECT / admission['successor_packet']
    output.mkdir(parents=True, exist_ok=False)
    protocol = PROJECT / 'docs/DISTANCE_CODEC_ADMISSION_02.md'
    for source, name in [(registration, 'admission.json'), (protocol, 'protocol-before-execution.md'),
                         (Path(__file__), 'admission-source.py'), (parent / 'registration.json', 'registration.json'),
                         (parent / 'offline-audit.json', 'offline-audit.json')]:
        shutil.copy2(source, output / name)
    bindings = list(old['bindings'])
    parent_files = [parent / n for n in ('plan.json', 'registration.json', 'aggregate.json', 'execution-start.json', 'adapter-check.json')]
    parent_files += [Path(c['run_dir']) / n for c in old['cases']
        for n in ('resource_deferred.json', 'resource_wait.jsonl') if (Path(c['run_dir']) / n).exists()]
    links = [binding(p) for p in parent_files]
    cases = []
    for original in pending:
        previous = Path(original['run_dir'])
        folder = output / 'episodes' / original['case_id']
        folder.mkdir(parents=True)
        shutil.copy2(previous / 'task.json', folder / 'task.json')
        config = json.loads((previous / 'config.json').read_text())
        config.update(task_path=str(folder / 'task.json'), output=str(folder / 'task'))
        dump(folder / 'config.json', config)
        command = [arg.replace(str(previous), str(folder)) for arg in json.loads((previous / 'command.json').read_text())]
        dump(folder / 'command.json', command)
        bindings += [binding(folder / n) for n in ('task.json', 'config.json', 'command.json')]
        cases.append(dict(original, run_dir=str(folder), previous_unrun_dir=str(previous)))
    bindings += links + [binding(p) for p in (registration, protocol, Path(__file__), PROJECT / 'src/hindsight_motion/boundary_admission.py')]
    bindings += [binding(output / n) for n in ('admission.json', 'registration.json', 'protocol-before-execution.md', 'offline-audit.json', 'admission-source.py')]
    bindings = list({b['path']: b for b in bindings}.values())
    for item in bindings:
        checked(item)
    dump(output / 'plan.json', dict(registration=old['registration'], admission=admission,
        parent_receipts=links, previous_native_attempts=summary['native_attempts'],
        cases=cases, bindings=bindings, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output), bindings=len(bindings), new_cases=len(cases), prior_attempts=0)))


def run(output):
    output = Path(output).resolve()
    plan = json.loads((output / 'plan.json').read_text())
    validate(PROJECT / plan['admission']['parent_packet'], plan['admission'])
    frozen_run(output)


def analyze(output):
    output = Path(output).resolve()
    public = PROJECT / 'results/distance_codec_admission02.json'
    if (output / 'aggregate.json').exists() or public.exists():
        raise FileExistsError('Preserve completed admission analysis')
    plan = json.loads((output / 'plan.json').read_text())
    parent = PROJECT / plan['admission']['parent_packet']
    validate(parent, plan['admission'])
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
    files = [output / n for n in ('admission.json', 'registration.json', 'protocol-before-execution.md', 'plan.json', 'execution-start.json', 'offline-audit.json')]
    for p in folders:
        files += [p / n for n in ('launch.json', 'exit.json', 'resource_admission.json', 'resource_deferred.json',
            'resource_wait.jsonl', 'parent-parity.json', 'pair-audit.json', 'task/task-result.json', 'task/distance-exit.json',
            'task/selection.npz', 'task/trace.npz', 'task/robot-poses.npz', 'task/pre-action-poses.npz',
            'task/dynamics-entry.npz', 'task/initial-state.npz', 'task/codec-entry.json') if (p / n).exists()]
    result = dict(schema='hindsight_distance_codec_admission_results_v1', date='2026-09-19', admission='02',
        scope=plan['registration']['scope'], development_only=True, heldout=False, source_ancestries=1, seed=96161,
        execution_state='resource_deferred' if deferred else ('stopped' if (output / 'stopped.json').exists() else 'complete'),
        scheduled_cases=4, native_attempts=sum((p / 'launch.json').exists() for p in folders), previous_native_attempts=0,
        completed_episodes=sum(r['status'] == 'completed' for r in rows), unrun=sum(r['status'] == 'unrun' for r in rows),
        infrastructure_failures=sum(e['exit_code'] != 0 for e in exits), retries=0, training_steps=0, teacher_action_queries=0,
        control_steps=sum(r.get('control_steps', 0) for r in rows), physics_samples=sum(r.get('physics_samples', 0) for r in rows),
        native_wall_seconds=sum(e['elapsed_s'] for e in exits), historical_main_attempts_consumed=0,
        rows=rows, pairs=pairs, reference_replay=replays, free_running_goal_contrasts=contrasts,
        parent_summary=dict(path=str((parent / 'aggregate.json').relative_to(PROJECT)), sha256=sha256(parent / 'aggregate.json')),
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=sha256(p)) for p in files])
    dump(output / 'aggregate.json', result)
    dump(public, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('provenance', 'rows')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'analyze'])
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    globals()[args.command](args.path)
