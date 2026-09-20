"""Admit only the never-launched pending case; retain three completed controls."""
import argparse
import json
from pathlib import Path
import shutil
import time

from .boundary_admission import validate_parent
from .complete_task import binding, checked, launch_case
from .core import sha256
from .critical import PROJECT, dump
from .distance_report import audit_case, goal_contrast
from .distance_study import qualify
from .pending_study import replay
from .resource_queue import run as resource_run


def validate(parent, admission):
    parent = Path(parent)
    for name, key in [('plan.json', 'parent_plan_sha256'),
                      ('stopped.json', 'parent_stopped_sha256'),
                      ('queue-interruption.json', 'parent_interruption_sha256')]:
        if sha256(parent / name) != admission[key]:
            raise ValueError('Closed parent changed: ' + name)
    old, summary, pending = validate_parent(parent, admission)
    if (admission['case_ids'] != ['farther-beam_linear29']
            or summary['native_attempts'] != 3 or summary['unrun'] != 1):
        raise ValueError('Only the fourth never-launched case is eligible')
    stop = json.loads((parent / 'stopped.json').read_text())
    if stop['supervisor_exit_code'] != 143 or stop['native_attempts'] != 3:
        raise ValueError('Unexpected parent interruption')
    for field in ('maximum_control_steps_per_attempt', 'maximum_wall_seconds_per_attempt',
                  'resource_wait_seconds_per_attempt', 'retries', 'training_steps'):
        if old['registration'][field] != admission[field]:
            raise ValueError('Frozen limit changed: ' + field)
    if (admission['maximum_new_control_steps'] != 500
            or admission['maximum_new_physics_samples'] != 2000
            or summary['control_steps'] + 500 > old['registration']['maximum_control_steps_total']
            or summary['physics_samples'] + 2000 > old['registration']['maximum_physics_steps_total']):
        raise ValueError('Cumulative step budget would change')
    controls = [r for r in summary['rows'] if r['status'] == 'completed']
    if len(controls) != 3 or not all(r['success'] for r in controls):
        raise ValueError('Require three successful retained controls')
    contrasts = summary['incumbent_comparisons']
    if len(contrasts) != 3 or not all(r['unchanged_path_audit']['matched'] for r in contrasts):
        raise ValueError('Full control retention is not qualified')
    return old, summary, pending


def prepare(registration):
    registration = Path(registration).resolve()
    admission = json.loads(registration.read_text())
    parent = PROJECT / admission['parent_packet']
    old, summary, pending = validate(parent, admission)
    if json.loads((PROJECT / admission['scientific_registration']).read_text()) != old['registration']:
        raise ValueError('Scientific registration changed')
    output = PROJECT / admission['successor_packet']
    output.mkdir(parents=True, exist_ok=False)
    protocol = PROJECT / 'docs/PENDING_EXIT_ADMISSION_02.md'
    for source, name in [(registration, 'admission.json'), (protocol, 'protocol-before-execution.md'),
                         (Path(__file__), 'admission-source.py'), (parent / 'commitment.json', 'commitment.json'),
                         (parent / 'offline-audit.json', 'offline-audit.json')]:
        shutil.copy2(source, output / name)
    reg = dict(old['registration'], maximum_native_attempts=1, maximum_control_steps_total=500,
               maximum_physics_steps_total=2000, conditions=['farther-beam'], methods=['linear29'])
    dump(output / 'registration.json', reg)
    links = [binding(parent / n) for n in ('plan.json', 'registration.json', 'aggregate.json',
        'execution-start.json', 'stopped.json', 'queue-interruption.json', 'queue.log')]
    links += [dict(path=str(PROJECT / p['path']), sha256=p['sha256']) for p in summary['provenance']]
    previous = Path(pending[0]['run_dir'])
    links += [binding(previous / 'resource_wait.jsonl')]
    folder = output / 'episodes' / pending[0]['case_id']
    folder.mkdir(parents=True)
    shutil.copy2(previous / 'task.json', folder / 'task.json')
    config = json.loads((previous / 'config.json').read_text())
    # The bound original commitment is deliberately reused byte-for-byte.
    config.update(task_path=str(folder / 'task.json'), output=str(folder / 'task'))
    dump(folder / 'config.json', config)
    command = [a.replace(str(previous), str(folder)) for a in json.loads((previous / 'command.json').read_text())]
    dump(folder / 'command.json', command)
    case = dict(pending[0], run_dir=str(folder), previous_unrun_dir=str(previous))
    control = next(c for c in old['cases'] if c['case_id'] == 'farther-beam_continuous')
    bindings = old['bindings'] + links
    bindings += [binding(p) for p in (registration, protocol, Path(__file__), PROJECT / 'src/hindsight_motion/boundary_admission.py')]
    bindings += [binding(output / n) for n in ('admission.json', 'registration.json', 'protocol-before-execution.md',
        'admission-source.py', 'commitment.json', 'offline-audit.json')]
    bindings += [binding(folder / n) for n in ('task.json', 'config.json', 'command.json')]
    bindings = list({b['path']: b for b in bindings}.values())
    for record in bindings:
        checked(record)
    dump(output / 'plan.json', dict(registration=reg, admission=admission, cases=[case],
        reused_pair_control=control, bindings=bindings, previous_native_attempts=3, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output), bindings=len(bindings), new_cases=1, reused_controls=3)), flush=True)


def run(output):
    output = Path(output).resolve()
    plan = json.loads((output / 'plan.json').read_text())
    validate(PROJECT / plan['admission']['parent_packet'], plan['admission'])
    for record in plan['bindings']:
        checked(record)
    with (output / 'execution-start.json').open('x') as f:
        json.dump(dict(unix_s=time.time(), plan_sha256=sha256(output / 'plan.json')), f)
    case = plan['cases'][0]
    folder = Path(case['run_dir'])
    try:
        resource_run([folder], timeout_s=plan['registration']['resource_wait_seconds_per_attempt'], launcher=launch_case)
        if (folder / 'launch.json').exists():
            valid = qualify(case, plan['reused_pair_control'])
            if not valid:
                dump(output / 'stopped.json', dict(reason='reused_pair_qualification_failed', case=case['case_id']))
            print(json.dumps(dict(case=case['case_id'], qualification=valid)), flush=True)
    except Exception as error:
        dump(output / 'stopped.json', dict(reason=type(error).__name__, detail=str(error)))
        raise


def analyze(output):
    output = Path(output).resolve()
    public = PROJECT / 'results/pending_exit_admission02.json'
    if public.exists() or (output / 'aggregate.json').exists():
        raise FileExistsError('Preserve completed admission analysis')
    plan = json.loads((output / 'plan.json').read_text())
    parent = PROJECT / plan['admission']['parent_packet']
    old_plan, old, _ = validate(parent, plan['admission'])
    for record in plan['bindings']:
        checked(record)
    case = plan['cases'][0]
    folder = Path(case['run_dir'])
    launched = (folder / 'launch.json').exists()
    deferred = (folder / 'resource_deferred.json').exists()
    stopped = (output / 'stopped.json').exists()
    if launched and not (folder / 'exit.json').exists():
        raise ValueError('Native execution has no exit receipt')
    if not launched and not (deferred or stopped):
        raise ValueError('Queue has no terminal receipt')
    row = audit_case(case)
    replays, comparisons = [], list(old['incumbent_comparisons'])
    if row['status'] == 'completed':
        receipt = json.loads((folder / 'task/pending-exit.json').read_text())
        row.update(request_lifecycle=receipt['request_lifecycle'], actual_final_choice=receipt['actual_final_choice'],
                   final_goal_margin_3d_m=.5-row['final_goal_distance_3d_m'])
        replays.append(dict(case_id=case['case_id'], **replay(folder, old['commitment'], enabled=True, require_exact=True)))
        contrast = goal_contrast(case['parent_run'], folder)
        accepted = row['request_lifecycle']['accepted_tick']
        for key, difference in contrast.items():
            first = difference['first_changed_tick']
            earliest = accepted + int(key in ('root_xyz', 'joint_pos')) if accepted is not None else None
            if first is not None and (earliest is None or first < earliest):
                raise ValueError('Trajectory changed before admitted treatment: ' + key)
        incumbent = json.loads(checked(old['incumbent_summary']).read_text())
        before = next(r for r in incumbent['rows'] if r['case_id'] == case['case_id'])
        comparisons.append(dict(case_id=case['case_id'], incumbent_success=before['success'],
            pending_success=row['success'], task_gain=int(row['success'] and not before['success']),
            task_regression=int(before['success'] and not row['success']), unchanged_path_audit=None,
            actual_trajectory_contrast=contrast))
    rows = [dict(row, admission='02') if r['case_id'] == case['case_id'] else dict(r, admission='01') for r in old['rows']]
    contrasts = list(old['free_running_goal_contrasts'])
    if row['status'] == 'completed':
        original = next(c for c in old_plan['cases'] if c['case_id'] == 'original-beam_linear29')
        contrasts.append(dict(method='linear29', differences=goal_contrast(original['run_dir'], folder)))
    files = [output / n for n in ('plan.json','admission.json','registration.json','protocol-before-execution.md',
        'admission-source.py','commitment.json','offline-audit.json','execution-start.json','stopped.json') if (output/n).exists()]
    files += [folder/n for n in ('launch.json','exit.json','resource_admission.json','resource_deferred.json',
        'resource_wait.jsonl','pair-audit.json','task/task-result.json','task/distance-exit.json','task/pending-exit.json',
        'task/codec-entry.json','task/selection.npz','task/pre-action-poses.npz','task/trace.npz','task/robot-poses.npz',
        'task/initial-state.npz','task/dynamics-entry.npz') if (folder/n).exists()]
    wall = json.loads((folder/'exit.json').read_text())['elapsed_s'] if launched else 0
    result = dict(schema='hindsight_pending_exit_admission_results_v1', date='2026-09-20', admission='02',
        scope='Same four-case pending study across two admissions; three completed controls reused without execution',
        development_only=True, heldout=False, source_ancestries=1, seed=96161,
        execution_state='resource_deferred' if deferred else ('stopped' if stopped else 'complete'),
        scheduled_cases=4, native_attempts=old['native_attempts']+int(launched), new_native_attempts=int(launched),
        reused_native_attempts=3, reused_incumbent_cases=4, unrun=sum(r['status']=='unrun' for r in rows),
        completed_episodes=sum(r['status']=='completed' for r in rows),
        infrastructure_failures=sum(r['status']=='infrastructure_failure' for r in rows),
        previous_queue_interruptions=1, retries=0, training_steps=0, teacher_action_queries=0, historical_main_attempts_consumed=0,
        control_steps=sum(r.get('control_steps',0) for r in rows), new_control_steps=row.get('control_steps',0),
        physics_samples=sum(r.get('physics_samples',0) for r in rows), new_physics_samples=row.get('physics_samples',0),
        native_wall_seconds=old['native_wall_seconds']+wall, new_native_wall_seconds=wall,
        rows=rows, incumbent_comparisons=comparisons, reference_replay=old['reference_replay']+replays,
        new_reference_replay=replays, free_running_goal_contrasts=contrasts, commitment=old['commitment'],
        parent_summary=binding(parent/'aggregate.json'), incumbent_summary=old['incumbent_summary'],
        provenance=[dict(path=str(p.relative_to(PROJECT)),sha256=sha256(p)) for p in files])
    dump(output/'aggregate.json',result)
    dump(public,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','provenance','reference_replay','new_reference_replay',
        'commitment','incumbent_comparisons')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','run','analyze'])
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    globals()[args.command](args.path)
