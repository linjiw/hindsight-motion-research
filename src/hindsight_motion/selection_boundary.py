"""Registered six-case support-boundary comparison; frozen codec and native runtime."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .complete_task import binding, checked, launch_case, paired_entry
from .core import sha256
from .critical import PROJECT, dump
from .resource_queue import run as resource_run
from .selection_codec import gather_reference
from .selection_report import audit_case
from .selection_study import parent_parity


def replay(folder, method, decoded):
    """Reconstruct actual public histories without physics or motor queries."""
    from gear_sonic.research.hindsight_training.observations import rotation_wxyz
    from gear_sonic.research.scene_distillation.duck_composer import native_reference
    from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
    from gear_sonic.research.scene_distillation.duck_motion_bank import load_bank, PublicMotionSelector

    folder = Path(folder)
    config = json.loads((folder / 'config.json').read_text())
    task = json.loads(Path(config['task_path']).read_text())
    selector = None
    qmax = vmax = 0.
    with np.load(folder / 'task/selection.npz') as recorded, np.load(folder / 'task/pre-action-poses.npz') as pre:
        for i in range(len(pre['time_s'])):
            measured = MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
                pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))
            if selector is None:
                selector = PublicMotionSelector(load_bank(checked(config['selection']['bank'])),
                                                measured, task['goal_xyz'], task['obstacles'])
                with np.load(checked(decoded[selector.candidate.name])) as data:
                    q, v = data['joint_position'].copy(), data['joint_velocity'].copy()
            chunk = selector.reference(measured)
            if method == 'linear29':
                joint, velocity = gather_reference(q, v, selector.source_indices[selector.consumed - 1:])
                qmax = max(qmax, float(np.max(abs(joint - chunk.joint_position))))
                vmax = max(vmax, float(np.max(abs(velocity - chunk.joint_velocity))))
                chunk = replace(chunk, joint_position=joint, joint_velocity=velocity)
            reference = native_reference(chunk, rotation_wxyz(measured.root_wxyz),
                native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()
            np.testing.assert_array_equal(reference, recorded['reference'][i])
            np.testing.assert_array_equal(selector.last_source_indices, recorded['reference_source_indices'][i])
            if selector.candidate.name != str(recorded['candidate'][i]) or selector.last_source_indices[0] != recorded['candidate_cursor'][i]:
                raise ValueError('Candidate/index replay mismatch')
        receipt = json.loads((folder / 'task/selection.json').read_text())
        if not all(receipt[k] == getattr(selector, k) for k in ('replans', 'retimed', 'support_rejections')):
            raise ValueError('Selector counters changed')
    return dict(states=i + 1, issued_reference_exact=True, source_indices_exact=True,
                selector_counters_exact=True, dense_planned_joint_change_max_rad=qmax,
                dense_planned_velocity_change_max_rad_s=vmax)


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    reg_path = PROJECT / 'configs/selection_boundary_v1.plan.json'
    reg = json.loads(reg_path.read_text())
    parent, codec = Path(reg['parent_packet']), PROJECT / reg['codec_packet']
    inherited = json.loads((codec / 'plan.json').read_text())
    bindings = list(inherited['bindings'])
    for item in bindings:
        checked(item)
    template = json.loads((Path(inherited['cases'][0]['run_dir']) / 'config.json').read_text())
    decoded = template['decoded_bank']
    shutil.copy2(reg_path, output / 'registration.json')
    protocol = PROJECT / 'docs/SELECTION_BOUNDARY_PROTOCOL.md'
    shutil.copy2(protocol, output / 'protocol-before-execution.md')
    for path in (reg_path, protocol, Path(__file__), PROJECT / 'src/hindsight_motion/selection_report.py',
                 parent / 'plan.json', parent / 'analysis.json', parent / 'geometry-screen.json',
                 parent / 'goal-length-diagnosis.json', codec / 'aggregate.json'):
        bindings.append(binding(path))
    snapshot = output / 'code_snapshot'
    snapshot.mkdir()
    for path in (Path(__file__), PROJECT / 'src/hindsight_motion/selection_report.py'):
        shutil.copy2(path, snapshot / path.name)
    offline, cases = [], []
    for condition in reg['conditions']:
        old = parent / 'evaluation' / (condition + '-public_selection') / 'attempt-01'
        original = json.loads((old / 'config.json').read_text())
        if original['max_steps'] != reg['maximum_control_steps_per_attempt']:
            raise ValueError('Inherited deadline differs from registration')
        offline.append(dict(condition=condition, **replay(old, 'continuous', decoded)))
        for method in reg['methods']:
            name = condition + '_' + method
            folder = output / 'episodes' / name
            folder.mkdir(parents=True)
            task = json.loads(Path(original['task_path']).read_text())
            task.update(task_id=name, split='development', positive_student_training_authorized=False)
            dump(folder / 'task.json', task)
            config = dict(original, task_path=str(folder / 'task.json'), output=str(folder / 'task'),
                          representation_method=method, decoded_bank=decoded)
            dump(folder / 'config.json', config)
            replacements = {
                '++callbacks.im_eval._target_': 'hindsight_motion.selection_codec_native.SelectionCodecCallback',
                '++callbacks.im_eval.stage_config': str(folder / 'config.json'),
                '++manager_env.config.navigation_task_path': str(folder / 'task.json'),
                '++eval_output_dir': str(folder / 'unused'), '++eval_base_dir': str(folder / 'hydra')}
            command = [a.split('=', 1)[0] + '=' + replacements[a.split('=', 1)[0]]
                       if a.split('=', 1)[0] in replacements else a
                       for a in json.loads((old / 'command.json').read_text())]
            dump(folder / 'command.json', command)
            bindings += [binding(folder / n) for n in ('task.json', 'config.json', 'command.json')]
            bindings += [binding(task['scene_usd_path']), task['duck_contract']['collision_bounds'],
                         binding(original['task_path'])]
            cases.append(dict(case_id=name, source_clip='00976', condition=condition, method=method,
                              run_dir=str(folder), parent_run=str(old)))
        bindings += [binding(old / n) for n in ('config.json', 'command.json')]
        bindings += [binding(f) for f in (old / 'task').iterdir() if f.is_file()]
    dump(output / 'offline-audit.json', dict(rows=offline, native_attempts=0))
    bindings += [binding(output / n) for n in ('registration.json', 'protocol-before-execution.md', 'offline-audit.json')]
    bindings = list({b['path']: b for b in bindings}.values())
    for item in bindings:
        checked(item)
    dump(output / 'plan.json', dict(registration=reg, cases=cases, bindings=bindings, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output), bindings=len(bindings), offline=offline)), flush=True)


def qualify(case, previous=None):
    folder = Path(case['run_dir'])
    if case['method'] == 'continuous':
        audit = parent_parity(case['parent_run'], folder)
        dump(folder / 'parent-parity.json', audit)
        # A reproduced task failure is a valid control, not an exclusion rule.
        return audit['matched']
    previous = Path(previous['run_dir'])
    audit = paired_entry(previous, folder)
    rng = [json.loads((p / 'task/codec-entry.json').read_text())['rng'] for p in (previous, folder)]
    audit['all_rng_matched'] = rng[0] == rng[1]
    selections = [json.loads((p / 'task/selection.json').read_text()) for p in (previous, folder)]
    audit['same_initial_choice'] = all(selections[0][k] == selections[1][k] for k in ('selected_candidate', 'initial_costs'))
    qualified = audit['matched'] and max(audit['max_errors'].values()) == 0 and audit['all_rng_matched'] and audit['same_initial_choice']
    dump(folder / 'pair-audit.json', audit)
    return qualified


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
            qualified = qualify(case, plan['cases'][i - 1] if i else None)
            score = json.loads((folder / 'task/task-result.json').read_text())
            print(json.dumps(dict(case=case['case_id'], success=score['duck_recover_stop_success'], qualification=qualified)), flush=True)
            if not qualified:
                dump(output / 'stopped.json', dict(reason='control_or_pair_qualification_failed', case=case['case_id']))
                break
    except Exception as error:
        dump(output / 'stopped.json', dict(reason=type(error).__name__, detail=str(error)))
        raise


def analyze(output):
    output = Path(output).resolve()
    public = PROJECT / 'results/selection_boundary.json'
    if (output / 'aggregate.json').exists() or public.exists():
        raise FileExistsError('Preserve completed analysis')
    plan = json.loads((output / 'plan.json').read_text())
    rows = [audit_case(c) for c in plan['cases']]
    folders = [Path(c['run_dir']) for c in plan['cases']]
    exits = [json.loads((p / 'exit.json').read_text()) for p in folders if (p / 'exit.json').exists()]
    deferred = any((p / 'resource_deferred.json').exists() for p in folders)
    if len(exits) != 6 and not (deferred or (output / 'stopped.json').exists()):
        raise ValueError('Queue has no terminal receipt')
    replays = []
    for case, row in zip(plan['cases'], rows):
        if row['status'] == 'completed':
            config = json.loads((Path(case['run_dir']) / 'config.json').read_text())
            replays.append(dict(case_id=case['case_id'], **replay(case['run_dir'], case['method'], config['decoded_bank'])))
    files = [output / n for n in ('registration.json', 'plan.json', 'execution-start.json', 'offline-audit.json')]
    for folder in folders:
        files += [folder / n for n in ('launch.json', 'exit.json', 'resource_admission.json', 'resource_deferred.json',
            'parent-parity.json', 'pair-audit.json', 'task/task-result.json', 'task/selection.json', 'task/selection.npz',
            'task/trace.npz', 'task/robot-poses.npz', 'task/pre-action-poses.npz', 'task/dynamics-entry.npz',
            'task/initial-state.npz', 'task/codec-entry.json') if (folder / n).exists()]
    summary = dict(schema='hindsight_selection_boundary_results_v1', date='2026-09-19',
        scope=plan['registration']['scope'], development_only=True, heldout=False, source_ancestries=1, seed=96161,
        scheduled_cases=6, native_attempts=sum((p / 'launch.json').exists() for p in folders),
        completed_episodes=sum(r['status'] == 'completed' for r in rows),
        infrastructure_failures=sum(r['status'] == 'infrastructure_failure' for r in rows),
        unrun=sum(r['status'] == 'unrun' for r in rows),
        execution_state='resource_deferred' if deferred else ('complete' if len(exits) == 6 else 'stopped'),
        control_steps=sum(r.get('control_steps', 0) for r in rows),
        physics_samples=sum(r.get('physics_samples', 0) for r in rows),
        native_wall_seconds=sum(e['elapsed_s'] for e in exits), retries=0, training_steps=0,
        historical_main_attempts_consumed=0, rows=rows, reference_replay=replays,
        offline_parent_replay=json.loads((output / 'offline-audit.json').read_text()),
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=sha256(p)) for p in files],
        analysis_source_sha256=sha256(__file__))
    dump(output / 'aggregate.json', summary)
    dump(public, summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'provenance'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'analyze'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output)
