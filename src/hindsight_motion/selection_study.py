"""Prepare, verify and execute a four-case public-selector codec comparison."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .complete_task import binding, checked, launch_case, paired_entry
from .core import sha256
from .critical import PROJECT, RUNTIME, dump
from .resource_queue import run as resource_run
from .selection_codec import decode_candidate, gather_reference, native_velocity


def parent_parity(parent, current):
    errors = {}
    for file, keys in {
        'selection.npz': ['reference', 'proprio', 'tokens', 'actions'],
        'pre-action-poses.npz': ['root_xyz', 'root_wxyz', 'joint_pos', 'joint_vel', 'body_xyz', 'body_wxyz'],
        'trace.npz': ['root_xyz', 'speed', 'contact_force_w'],
        'dynamics-entry.npz': None,
        'duck-features.npz': None,
    }.items():
        with np.load(Path(parent)/'task'/file) as a, np.load(Path(current)/'task'/file) as b:
            for key in (a.files if keys is None else keys):
                if a[key].shape != b[key].shape:
                    return dict(matched=False, reason=f'{file}:{key} shape changed')
                if not np.isfinite(a[key]).all() or not np.isfinite(b[key]).all():
                    raise ValueError('Nonfinite parity evidence')
                errors[file+':'+key] = float(np.max(abs(a[key].astype(float)-b[key].astype(float)), initial=0))
    return dict(matched=max(errors.values()) == 0, max_errors=errors)


def offline_audit(parent, bank_path, decoded):
    from gear_sonic.research.hindsight_training.observations import rotation_wxyz
    from gear_sonic.research.scene_distillation.duck_composer import native_reference
    from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
    from gear_sonic.research.scene_distillation.duck_motion_bank import load_bank, PublicMotionSelector
    rows = []
    for condition in ('clear', 'shift_earlier_100mm'):
        run = parent/'evaluation'/f'{condition}-public_selection'/'attempt-01'
        config = json.loads((run/'config.json').read_text())
        task = json.loads(Path(config['task_path']).read_text())
        correction = parent/f'{condition}-public_selection-reference-indices-v2.npz'
        with np.load(run/'task/pre-action-poses.npz') as pre, np.load(run/'task/selection.npz') as old, np.load(correction) as corrected:
            selector, largest, changed = None, 0., 0
            for i in range(len(pre['time_s'])):
                measured = MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
                    pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))
                if selector is None:
                    selector = PublicMotionSelector(load_bank(bank_path), measured, task['goal_xyz'], task['obstacles'])
                chunk = selector.reference(measured)
                ref = native_reference(chunk, rotation_wxyz(measured.root_wxyz), native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()
                np.testing.assert_array_equal(ref, old['reference'][i])
                np.testing.assert_array_equal(selector.last_source_indices, corrected['reference_source_indices'][i])
                dense = selector.source_indices[selector.consumed-1:]
                q, v = gather_reference(*decoded[selector.candidate.name], dense)
                coded = native_reference(replace(chunk, joint_position=q, joint_velocity=v), rotation_wxyz(measured.root_wxyz), native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()
                largest = max(largest, float(np.max(abs(ref-coded))))
                changed += int(not np.array_equal(ref, coded))
            rows.append(dict(condition=condition, recorded_states=len(pre['time_s']), continuous_reference_exact=True,
                committed_indices_exact=True, linear_reference_changed_states=changed,
                mixed_unit_reference_max_difference=largest, selected_candidate=selector.candidate.name))
    return dict(rows=rows, scope='Offline reference parity and changes; no new physics or motor-action result')


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    reg_path = PROJECT/'configs/selection_codec_v1.plan.json'
    reg = json.loads(reg_path.read_text())
    parent = Path(reg['parent_packet'])
    bank_path = parent/'bank.json'
    bank = json.loads(bank_path.read_text())
    shutil.copy2(reg_path, output/'registration.json')
    scale_path = PROJECT/'runs/clearance_tokens_20260915_v1/residual_model.npz'
    names_path = PROJECT/'runs/complete_task_20260918_v1/references/00976_continuous/reference.npz'
    with np.load(scale_path) as f: scale=f['angle_scale'].copy()
    with np.load(names_path) as f: scale_names=tuple(f['joint_names'])
    bindings=[binding(reg_path),binding(bank_path),binding(parent/'plan.json'),binding(scale_path),binding(names_path)]
    decoded, decoded_files, audits = {}, {}, []
    for candidate in bank['candidates']:
        data_path=checked(candidate['data'])
        bindings += [binding(data_path), candidate['source_reference'], candidate['native_motion'], candidate['contact_comparator'], candidate['comparator_receipt']]
        with np.load(data_path) as d:
            np.testing.assert_array_equal(native_velocity(d['joint_position']), d['joint_velocity'])
            q,v,audit=decode_candidate(d['joint_position'],d['joint_names'],scale,scale_names)
        target=output/(candidate['name']+'_linear29.npz')
        np.savez_compressed(target,joint_position=q,joint_velocity=v)
        decoded[candidate['name']] = q,v
        decoded_files[candidate['name']] = binding(target)
        bindings.append(binding(target))
        audits.append(dict(candidate=candidate['name'],**audit))
    dump(output/'codec-audit.json',audits)
    offline=offline_audit(parent,bank_path,decoded)
    dump(output/'offline-audit.json',offline)
    cases=[]
    for condition in reg['conditions']:
        old=parent/'evaluation'/f'{condition}-public_selection'/'attempt-01'
        original=json.loads((old/'config.json').read_text())
        for method in reg['methods']:
            name=f'{condition}_{method}'
            run=output/'episodes'/name
            run.mkdir(parents=True)
            task=json.loads(Path(original['task_path']).read_text())
            task.update(task_id=name,split='development',positive_student_training_authorized=False)
            dump(run/'task.json',task)
            config=dict(original,task_path=str(run/'task.json'),output=str(run/'task'),
                        representation_method=method,decoded_bank=decoded_files)
            dump(run/'config.json',config)
            replacements={
                '++callbacks.im_eval._target_':'hindsight_motion.selection_codec_native.SelectionCodecCallback',
                '++callbacks.im_eval.stage_config':str(run/'config.json'),
                '++manager_env.config.navigation_task_path':str(run/'task.json'),
                '++eval_output_dir':str(run/'unused'),'++eval_base_dir':str(run/'hydra')}
            command=[a.split('=',1)[0]+'='+replacements[a.split('=',1)[0]] if a.split('=',1)[0] in replacements else a
                     for a in json.loads((old/'command.json').read_text())]
            dump(run/'command.json',command)
            for f in ('task.json','config.json','command.json'):bindings.append(binding(run/f))
            for key in ('teacher_checkpoint','student_checkpoint','motor_checkpoint'):
                bindings.append(binding(config[key]))
            bindings += [binding(task['scene_usd_path']), task['duck_contract']['collision_bounds'], binding(original['task_path'])]
            cases.append(dict(case_id=name,source_clip='00976',condition=condition,method=method,run_dir=str(run),parent_run=str(old)))
        for f in (old/'task').glob('*'):
            if f.is_file():bindings.append(binding(f))
        bindings += [binding(old/'config.json'),binding(old/'command.json'),binding(parent/f'{condition}-public_selection-reference-indices-v2.npz')]
    proxy=json.loads(checked(bank['collision_bounds']).read_text())
    bindings += [bank['collision_bounds'],dict(path=proxy['asset'],sha256=proxy['asset_sha256'])]
    # Bind current corrected runtime separately from the old v1 execution snapshots.
    sources=list((RUNTIME/'gear_sonic/research/scene_distillation').glob('*.py'))
    sources+=list((RUNTIME/'gear_sonic/research/hindsight_training').glob('*.py'))
    sources += [RUNTIME/p for p in ('gear_sonic/eval_agent_trl.py','gear_sonic/utils/motion_lib/torch_humanoid_batch.py',
        'gear_sonic/envs/wrapper/manager_env_wrapper.py','gear_sonic/envs/manager_env/mdp/commands.py','gear_sonic/envs/manager_env/mdp/observations.py')]
    sources += [PROJECT/f'src/hindsight_motion/{n}.py' for n in ('selection_study','selection_codec','selection_codec_native','complete_task','continuation_native','complete_task_native','resource_queue')]
    for i,source in enumerate(sources):
        dest=output/'code_snapshot'/f'{i:03d}_{source.name}';dest.parent.mkdir(exist_ok=True)
        shutil.copy2(source,dest);bindings.append(binding(source))
    bindings += [binding(output/'offline-audit.json'),binding(output/'codec-audit.json')]
    bindings=list({b['path']:b for b in bindings}.values())
    for item in bindings:checked(item)
    dump(output/'plan.json',dict(registration=reg,cases=cases,bindings=bindings,created_unix_s=time.time()))
    print(json.dumps(dict(prepared=str(output),offline=offline,codec=audits),indent=2))


def run(output):
    output=Path(output).resolve();plan=json.loads((output/'plan.json').read_text())
    with (output/'execution-start.json').open('x') as f:json.dump(dict(unix_s=time.time(),plan_sha256=sha256(output/'plan.json')),f)
    for i,case in enumerate(plan['cases']):
        folder=Path(case['run_dir'])
        resource_run([folder],timeout_s=plan['registration']['resource_wait_seconds_per_attempt'],launcher=launch_case)
        if not (folder/'launch.json').exists():break
        score=json.loads((folder/'task/task-result.json').read_text())
        if case['method']=='continuous':
            audit=parent_parity(case['parent_run'],folder)
            dump(folder/'parent-parity.json',audit)
            qualified=audit['matched'] and score['duck_recover_stop_success']
        else:
            previous=Path(plan['cases'][i-1]['run_dir'])
            audit=paired_entry(previous,folder)
            rng=[json.loads((p/'task/codec-entry.json').read_text())['rng'] for p in (previous,folder)]
            audit['all_rng_matched']=rng[0]==rng[1]
            selection=[json.loads((p/'task/selection.json').read_text()) for p in (previous,folder)]
            audit['same_initial_choice']=selection[0]['selected_candidate']==selection[1]['selected_candidate'] and selection[0]['initial_costs']==selection[1]['initial_costs']
            qualified=audit['matched'] and max(audit['max_errors'].values())==0 and audit['all_rng_matched'] and audit['same_initial_choice']
            dump(folder/'pair-audit.json',audit)
        print(json.dumps(dict(case=case['case_id'],success=score['duck_recover_stop_success'],qualification=qualified)),flush=True)
        if not qualified:
            dump(output/'stopped.json',dict(reason='control_or_pair_qualification_failed',case=case['case_id']))
            break


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run']);parser.add_argument('output',type=Path)
    args=parser.parse_args();globals()[args.command](args.output)
