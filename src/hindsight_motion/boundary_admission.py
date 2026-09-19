"""Finish only never-launched cells of the immutable boundary comparison."""
import argparse
import json
from pathlib import Path
import shutil
import time

from .complete_task import binding, checked
from .core import sha256
from .critical import PROJECT, dump
from .selection_boundary import replay, run as frozen_run
from .selection_report import audit_case


def validate_parent(parent, admission):
    parent = Path(parent)
    for name, key in [('registration.json', 'parent_registration_sha256'),
                      ('aggregate.json', 'parent_aggregate_sha256')]:
        if sha256(parent / name) != admission[key]:
            raise ValueError('Parent receipt changed: ' + name)
    plan = json.loads((parent / 'plan.json').read_text())
    summary = json.loads((parent / 'aggregate.json').read_text())
    if summary['execution_state'] != admission['require_parent_execution_state']:
        raise ValueError('Parent is not the registered closed resource deferral')
    rows = {r['case_id']: r for r in summary['rows']}
    pending, attempted = [], 0
    for case in plan['cases']:
        folder = Path(case['run_dir'])
        launched = (folder / 'launch.json').exists()
        row = rows[case['case_id']]
        if launched:
            attempted += 1
            if row['status'] != 'completed' or not (folder / 'exit.json').exists():
                raise ValueError('Parent has an active, failed or unaccounted launch')
            if json.loads((folder / 'exit.json').read_text())['exit_code'] != 0:
                raise ValueError('An infrastructure attempt cannot be replaced')
        else:
            if row['status'] != 'unrun' or (folder / 'exit.json').exists():
                raise ValueError('Parent launch/summary mismatch')
            pending.append(case)
    if attempted != admission['require_parent_native_attempts'] or attempted != summary['native_attempts']:
        raise ValueError('Parent native count changed')
    if [c['case_id'] for c in pending] != admission['case_ids'] or len(pending) != summary['unrun']:
        raise ValueError('Admission must contain exactly the ordered never-launched cases')
    if (len(pending) != admission['maximum_new_native_attempts']
            or attempted + len(pending) != admission['maximum_native_attempts_across_admissions']
            or attempted + len(pending) != plan['registration']['maximum_native_attempts']):
        raise ValueError('Admission cannot enlarge the scientific budget')
    for item in plan['bindings']:
        checked(item)
    for item in summary['provenance']:
        checked(dict(path=str(PROJECT / item['path']), sha256=item['sha256']))
    return plan, summary, pending


def prepare(registration):
    registration = Path(registration).resolve()
    admission = json.loads(registration.read_text())
    parent = PROJECT / admission['parent_packet']
    old, summary, pending = validate_parent(parent, admission)
    if json.loads((PROJECT / admission['scientific_registration']).read_text()) != old['registration']:
        raise ValueError('Scientific registration changed')
    output = PROJECT / admission['successor_packet']
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(registration, output / 'admission.json')
    protocol = PROJECT / 'docs/SELECTION_BOUNDARY_ADMISSION_02.md'
    shutil.copy2(protocol, output / 'protocol-before-execution.md')
    shutil.copy2(__file__, output / 'admission-source.py')
    shutil.copy2(parent / 'offline-audit.json', output / 'offline-audit.json')
    reg = dict(old['registration'], conditions=['lower100-beam', 'farther600-beam'],
               maximum_native_attempts=admission['maximum_new_native_attempts'],
               maximum_control_steps_total=admission['maximum_new_control_steps'],
               maximum_physics_steps_total=admission['maximum_new_physics_samples'])
    for key in ('maximum_wall_seconds_per_attempt', 'resource_wait_seconds_per_attempt', 'retries', 'training_steps'):
        if reg[key] != admission[key]:
            raise ValueError('Frozen limit changed: ' + key)
    if summary['control_steps'] + reg['maximum_control_steps_total'] > old['registration']['maximum_control_steps_total']:
        raise ValueError('Cumulative control-step ceiling exceeded')
    dump(output / 'registration.json', reg)
    bindings = list(old['bindings'])
    links = [binding(parent / n) for n in ('plan.json', 'registration.json', 'aggregate.json', 'execution-start.json')]
    links += [binding(Path(c['run_dir']) / n) for c in old['cases']
              for n in ('launch.json', 'exit.json', 'resource_deferred.json', 'resource_wait.jsonl')
              if (Path(c['run_dir']) / n).exists()]
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
    bindings += links + [binding(registration), binding(protocol), binding(__file__)]
    bindings += [binding(output / n) for n in ('admission.json', 'registration.json', 'protocol-before-execution.md', 'offline-audit.json', 'admission-source.py')]
    bindings = list({b['path']: b for b in bindings}.values())
    for item in bindings:
        checked(item)
    dump(output / 'plan.json', dict(registration=reg, admission=admission, parent_receipts=links,
        previous_native_attempts=summary['native_attempts'], cases=cases, bindings=bindings, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output), prior_attempts=summary['native_attempts'], new_cases=len(cases), bindings=len(bindings))))


def run(output):
    output = Path(output).resolve()
    plan = json.loads((output / 'plan.json').read_text())
    validate_parent(PROJECT / plan['admission']['parent_packet'], plan['admission'])
    frozen_run(output)


def analyze(output):
    output = Path(output).resolve()
    public = PROJECT / 'results/selection_boundary_admission02.json'
    if (output / 'aggregate.json').exists() or public.exists():
        raise FileExistsError('Preserve completed analysis')
    plan = json.loads((output / 'plan.json').read_text())
    parent = PROJECT / plan['admission']['parent_packet']
    old_plan, old, _ = validate_parent(parent, plan['admission'])
    folders = [Path(c['run_dir']) for c in plan['cases']]
    new_rows = [audit_case(c) for c in plan['cases']]
    exits = [json.loads((p / 'exit.json').read_text()) for p in folders if (p / 'exit.json').exists()]
    deferred = any((p / 'resource_deferred.json').exists() for p in folders)
    if len(exits) != len(folders) and not (deferred or (output / 'stopped.json').exists()):
        raise ValueError('Queue has no terminal receipt')
    replays = []
    for case, row in zip(plan['cases'], new_rows):
        if row['status'] != 'completed':
            continue
        config = json.loads((Path(case['run_dir']) / 'config.json').read_text())
        replays.append(dict(case_id=case['case_id'], **replay(case['run_dir'], case['method'], config['decoded_bank'])))
        score = json.loads((Path(case['run_dir']) / 'task/task-result.json').read_text())
        row['task_components'] = {k: score[k] for k in ('passage_success', 'duck_observed', 'recovered',
            'entry_tick', 'clear_tick', 'recovery_tick', 'ordered_hold_ticks', 'stable_stop_success')}
    replacements = {r['case_id']: dict(r, admission='02') for r in new_rows}
    rows = [replacements.get(r['case_id'], dict(r, admission='01')) for r in old['rows']]
    files = [output / n for n in ('admission.json', 'registration.json', 'plan.json', 'execution-start.json', 'offline-audit.json')]
    for folder in folders:
        files += [folder / n for n in ('launch.json', 'exit.json', 'resource_admission.json', 'resource_deferred.json',
            'resource_wait.jsonl', 'parent-parity.json', 'pair-audit.json', 'task/task-result.json',
            'task/selection.json', 'task/selection.npz', 'task/trace.npz', 'task/robot-poses.npz',
            'task/pre-action-poses.npz', 'task/dynamics-entry.npz', 'task/initial-state.npz', 'task/codec-entry.json')
            if (folder / n).exists()]
    new_attempts = sum((p / 'launch.json').exists() for p in folders)
    summary = dict(schema='hindsight_selection_boundary_admission_results_v1', date='2026-09-19', admission='02',
        development_only=True, heldout=False, source_ancestries=1, seed=96161,
        scope='Same frozen six-case study across two resource admissions; prior two successes reused without execution',
        execution_state='resource_deferred' if deferred else ('stopped' if (output / 'stopped.json').exists() else 'complete'),
        scheduled_cases=6, native_attempts=old['native_attempts'] + new_attempts,
        new_native_attempts=new_attempts, reused_native_attempts=old['native_attempts'],
        completed_episodes=sum(r['status'] == 'completed' for r in rows),
        infrastructure_failures=sum(r['status'] == 'infrastructure_failure' for r in rows),
        unrun=sum(r['status'] == 'unrun' for r in rows),
        control_steps=sum(r.get('control_steps', 0) for r in rows),
        new_control_steps=sum(r.get('control_steps', 0) for r in new_rows),
        physics_samples=sum(r.get('physics_samples', 0) for r in rows),
        new_physics_samples=sum(r.get('physics_samples', 0) for r in new_rows),
        native_wall_seconds=old['native_wall_seconds'] + sum(e['elapsed_s'] for e in exits),
        new_native_wall_seconds=sum(e['elapsed_s'] for e in exits), retries=0, training_steps=0,
        historical_main_attempts_consumed=0, rows=rows, reference_replay=old['reference_replay'] + replays,
        new_reference_replay=replays, parent_summary=dict(path=str((parent / 'aggregate.json').relative_to(PROJECT)), sha256=sha256(parent / 'aggregate.json')),
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=sha256(p)) for p in files],
        analysis_source_sha256=sha256(__file__))
    dump(output / 'aggregate.json', summary)
    dump(public, summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ('provenance', 'rows')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'analyze'])
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    globals()[args.command](args.path)
