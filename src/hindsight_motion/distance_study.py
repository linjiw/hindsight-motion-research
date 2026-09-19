"""Prepare and run the separately registered four-case distance-codec study."""
import argparse
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .complete_task import binding, checked, launch_case, paired_entry
from .core import sha256
from .critical import PROJECT, RUNTIME, dump
from .distance_codec import validate_commitment
from .distance_report import analyze, replay
from .resource_queue import run as resource_run
from .selection_codec import decode_candidate
from .selection_study import parent_parity


def nested_bindings(value):
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            yield dict(path=value['path'], sha256=value['sha256'])
        for item in value.values():
            yield from nested_bindings(item)
    elif isinstance(value, list):
        for item in value:
            yield from nested_bindings(item)


def prepare(output):
    output = Path(output).resolve()
    reg_path = PROJECT / 'configs/distance_codec_v1.plan.json'
    protocol = PROJECT / 'docs/DISTANCE_CODEC_PROTOCOL.md'
    reg = json.loads(reg_path.read_text())
    parent, preflight = Path(reg['parent_packet']), PROJECT / reg['preflight_packet']
    bindings = json.loads((preflight / 'bindings.json').read_text())
    for item in bindings:
        checked(item)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(reg_path, output / 'registration.json')
    shutil.copy2(protocol, output / 'protocol-before-execution.md')
    bank_path = parent / 'exit-bank.json'
    bank = json.loads(bank_path.read_text())
    bindings += list(nested_bindings(bank))
    bindings += [binding(p) for p in (reg_path, protocol, bank_path, preflight / 'aggregate.json', preflight / 'bindings.json')]
    scale_path = PROJECT / 'runs/clearance_tokens_20260915_v1/residual_model.npz'
    names_path = PROJECT / 'runs/complete_task_20260918_v1/references/00976_continuous/reference.npz'
    with np.load(scale_path) as data:
        scale = data['angle_scale'].copy()
    with np.load(names_path) as data:
        names = tuple(data['joint_names'])
    decoded, paths, audits = {}, {}, []
    for family, routes in bank['families'].items():
        decoded[family], paths[family] = {}, {}
        for route in ('short', 'loop'):
            with np.load(checked(routes[route]['data'])) as original:
                q, v, audit = decode_candidate(original['joint_position'], original['joint_names'], scale, names)
                mask = original.get('synthetic_bridge', np.zeros(len(q), bool))
                if original['support_observation_valid'][mask].any():
                    raise ValueError('Synthetic bridge has observed-support validity')
            file = preflight / (family + '_' + route + '.npz')
            with np.load(file) as old:
                np.testing.assert_array_equal(q, old['joint_position'])
                np.testing.assert_array_equal(v, old['joint_velocity'])
            paths[family][route] = binding(file)
            bindings.append(binding(file))
            decoded[family][route] = q, v
            audits.append(dict(family=family, route=route, **audit, preflight_arrays_exact=True))
    validate_commitment(decoded, bank['decision_tick'])
    offline, cases, tasks = [], [], []
    for condition in reg['conditions']:
        old = parent / 'evaluation' / (condition + '-public_selection') / 'attempt-01'
        config = json.loads((old / 'config.json').read_text())
        if config['max_steps'] != 500 or config['actor_profile'] != 'public_selection' or config['intervention']:
            raise ValueError('Parent execution contract differs')
        offline.append(dict(condition=condition, **replay(old, 'continuous', paths)))
        task_path = Path(config['task_path'])
        task = json.loads(task_path.read_text())
        if task.get('positive_student_training_authorized', False):
            raise ValueError('No positive training admission')
        tasks.append(task)
        for method in reg['methods']:
            name = condition + '_' + method
            folder = output / 'episodes' / name
            folder.mkdir(parents=True)
            shutil.copy2(task_path, folder / 'task.json')
            new_config = dict(config, task_path=str(folder / 'task.json'), output=str(folder / 'task'),
                representation_method=method, decoded_bank=paths)
            dump(folder / 'config.json', new_config)
            replacements = {'++callbacks.im_eval._target_': 'hindsight_motion.distance_codec_native.DistanceCodecCallback',
                '++callbacks.im_eval.stage_config': str(folder / 'config.json'),
                '++manager_env.config.navigation_task_path': str(folder / 'task.json'),
                '++eval_output_dir': str(folder / 'unused'), '++eval_base_dir': str(folder / 'hydra')}
            command = [a.split('=', 1)[0] + '=' + replacements[a.split('=', 1)[0]]
                if a.split('=', 1)[0] in replacements else a for a in json.loads((old / 'command.json').read_text())]
            if '++seed=96161' not in command:
                raise ValueError('Seed mismatch')
            dump(folder / 'command.json', command)
            bindings += [binding(folder / n) for n in ('task.json', 'config.json', 'command.json')]
            cases.append(dict(case_id=name, condition=condition, method=method, source_clip='00976',
                run_dir=str(folder), parent_run=str(old)))
        bindings += [binding(old / n) for n in ('config.json', 'command.json')]
        bindings += [binding(f) for f in (old / 'task').iterdir() if f.is_file()]
        bindings += [binding(task_path), binding(task['scene_usd_path'])] + list(nested_bindings(task))
        for key in ('teacher_checkpoint', 'student_checkpoint', 'motor_checkpoint'):
            if sha256(Path(config[key])) != config[key.replace('_checkpoint', '_sha256')]:
                raise ValueError('Parent checkpoint changed')
            bindings.append(binding(config[key]))
        bindings.append(binding(Path(config['teacher_checkpoint']).with_name('config.yaml')))
    if (sha256(Path(tasks[0]['scene_usd_path'])) != sha256(Path(tasks[1]['scene_usd_path']))
            or tasks[0]['obstacles'] != tasks[1]['obstacles']):
        raise ValueError('Goal contexts must share exact scene geometry')
    proxy = json.loads(checked(bank['collision_bounds']).read_text())
    bindings.append(dict(path=proxy['asset'], sha256=proxy['asset_sha256']))
    sources = list((RUNTIME / 'gear_sonic/research/scene_distillation').glob('*.py'))
    sources += list((RUNTIME / 'gear_sonic/research/hindsight_training').glob('*.py'))
    sources += [RUNTIME / p for p in ('gear_sonic/eval_agent_trl.py', 'gear_sonic/utils/motion_lib/torch_humanoid_batch.py',
        'gear_sonic/envs/wrapper/manager_env_wrapper.py', 'gear_sonic/envs/manager_env/mdp/commands.py',
        'gear_sonic/envs/manager_env/mdp/observations.py', 'gear_sonic/dataset_generation/kimodo_motion_adapter.py')]
    sources += [PROJECT / f'src/hindsight_motion/{name}.py' for name in ('distance_codec', 'distance_codec_native',
        'distance_report', 'distance_study', 'selection_codec', 'selection_study', 'complete_task',
        'continuation_native', 'complete_task_native', 'resource_queue', 'critical', 'core')]
    snapshot = output / 'code_snapshot'
    snapshot.mkdir()
    for i, source in enumerate(sources):
        shutil.copy2(source, snapshot / f'{i:03d}_{source.name}')
        bindings.append(binding(source))
    dump(output / 'offline-audit.json', dict(rows=offline, codecs=audits, native_attempts=0,
        decoded_five_frame_commitment_exact=True, same_scene_bytes=True, full_continuous_bank_retained=True))
    bindings += [binding(output / n) for n in ('registration.json', 'protocol-before-execution.md', 'offline-audit.json')]
    bindings = list({b['path']: b for b in bindings}.values())
    for item in bindings:
        checked(item)
    dump(output / 'plan.json', dict(registration=reg, cases=cases, bindings=bindings, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output), bindings=len(bindings), offline=offline)), flush=True)


def qualify(case, previous):
    folder = Path(case['run_dir'])
    if case['method'] == 'continuous':
        audit = parent_parity(case['parent_run'], folder)
        receipts = [json.loads((Path(p) / 'task/distance-exit.json').read_text()) for p in (case['parent_run'], folder)]
        audit['same_family_and_decision'] = all(receipts[0][k] == receipts[1][k] for k in ('family', 'decision'))
        audit['matched'] &= audit['same_family_and_decision']
        dump(folder / 'parent-parity.json', audit)
        return audit['matched']
    previous = Path(previous['run_dir'])
    audit = paired_entry(previous, folder)
    entries = [json.loads((p / 'task/codec-entry.json').read_text()) for p in (previous, folder)]
    audit['all_rng_matched'] = entries[0]['rng'] == entries[1]['rng']
    audit['same_initial_choice_and_costs'] = all(entries[0][k] == entries[1][k] for k in ('initial_family', 'initial_costs'))
    audit['matched'] = bool(audit['matched'] and max(audit['max_errors'].values()) == 0
        and audit['all_rng_matched'] and audit['same_initial_choice_and_costs'])
    dump(folder / 'pair-audit.json', audit)
    return audit['matched']


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
            print(json.dumps(dict(case=case['case_id'], qualification=qualified,
                success=score['duck_recover_stop_success'])), flush=True)
            if not qualified:
                dump(output / 'stopped.json', dict(reason='control_or_pair_qualification_failed', case=case['case_id']))
                break
    except Exception as error:
        dump(output / 'stopped.json', dict(reason=type(error).__name__, detail=str(error)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'analyze'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output)
