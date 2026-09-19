"""Frozen Linear29 compatibility with composed exits; offline evidence only."""
from dataclasses import replace
import json
from pathlib import Path
import shutil

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_composer_state import MeasuredComposerState
from gear_sonic.research.scene_distillation.duck_distance_exit import DistanceExitComposer
from hindsight_motion.complete_task import binding, checked
from hindsight_motion.critical import PROJECT, RUNTIME, dump
from hindsight_motion.selection_codec import decode_candidate, gather_reference, native_velocity


def first_difference(a, b):
    indices = np.flatnonzero(np.any(a[:min(len(a), len(b))] != b[:min(len(a), len(b))], axis=1))
    return int(indices[0]) if len(indices) else None


def packed(composer, chunk, measured, decoded, method):
    if method == 'linear29':
        q, v = decoded[(composer.family, 'loop' if composer.choice else 'short')]
        dense = np.minimum(int(composer.last_indices[0]) + np.arange(60), len(q) - 1)
        q, v = gather_reference(q, v, dense)
        chunk = replace(chunk, joint_position=q, joint_velocity=v)
    return native_reference(chunk, rotation_wxyz(measured.root_wxyz),
                            native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()


def measured_row(pre, i):
    return MeasuredComposerState(pre['root_xyz'][i], pre['root_wxyz'][i], pre['joint_pos'][i],
        pre['joint_vel'][i], tuple(pre['joint_names']), float(pre['time_s'][i]))


def main():
    reg_path = PROJECT / 'configs/distance_codec_preflight_v1.plan.json'
    reg = json.loads(reg_path.read_text())
    parent, output = Path(reg['parent_packet']), PROJECT / reg['output']
    public = PROJECT / 'results/distance_codec_preflight.json'
    if public.exists():
        raise FileExistsError('Preserve completed preflight')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(reg_path, output / 'registration.json')
    shutil.copy2(__file__, output / 'source.py')
    bank_path = parent / 'exit-bank.json'
    bank = json.loads(bank_path.read_text())
    scale_path = PROJECT / 'runs/clearance_tokens_20260915_v1/residual_model.npz'
    names_path = PROJECT / 'runs/complete_task_20260918_v1/references/00976_continuous/reference.npz'
    bindings = [binding(p) for p in (reg_path, Path(__file__), bank_path, parent / 'analysis.json', scale_path, names_path)]
    sources = [PROJECT / 'src/hindsight_motion/selection_codec.py'] + [RUNTIME / ('gear_sonic/research/scene_distillation/' + n + '.py')
        for n in ('duck_distance_exit', 'duck_composer', 'duck_composer_state', 'duck_motion_bank')]
    bindings += [binding(p) for p in sources]
    with np.load(scale_path) as f:
        scale = f['angle_scale'].copy()
    with np.load(names_path) as f:
        names = tuple(f['joint_names'])
    decoded, arrays, audits = {}, {}, []
    for family, spec in bank['families'].items():
        for route in ('short', 'loop'):
            file = checked(spec[route]['data'])
            bindings.append(binding(file))
            with np.load(file) as d:
                data = {k: d[k].copy() for k in d.files}
            arrays[(family, route)] = data
            q, v, audit = decode_candidate(data['joint_position'], data['joint_names'], scale, names)
            decoded[(family, route)] = q, v
            np.savez_compressed(output / (family + '_' + route + '.npz'), joint_position=q, joint_velocity=v)
            gap = native_velocity(data['joint_position']) - data['joint_velocity']
            changed = np.flatnonzero(np.any(gap != 0, axis=1))
            synthetic = data.get('synthetic_bridge', np.zeros(len(q), bool))
            if data['support_observation_valid'][synthetic].any():
                raise ValueError('Synthetic bridge gained observed-support validity')
            audits.append(dict(family=family, route=route, **audit,
                provided_velocity_fd_max_difference_rad_s=float(np.max(abs(gap))),
                provided_velocity_fd_changed_rows=len(changed), first_velocity_convention_difference=int(changed[0]) if len(changed) else None,
                synthetic_rows=int(synthetic.sum()), synthetic_observed_support_valid=False))
    prefixes = []
    for family in bank['families']:
        short, loop = [arrays[(family, route)] for route in ('short', 'loop')]
        sq, sv = decoded[(family, 'short')]
        lq, lv = decoded[(family, 'loop')]
        visible_end = bank['decision_tick'] - 1 + 45
        commitment_end = bank['decision_tick'] + 5
        prefixes.append(dict(family=family,
            continuous_q_first_difference=first_difference(short['joint_position'], loop['joint_position']),
            continuous_qdot_first_difference=first_difference(short['joint_velocity'], loop['joint_velocity']),
            linear_q_first_difference=first_difference(sq, lq), linear_qdot_first_difference=first_difference(sv, lv),
            last_predecision_visible_index=visible_end,
            visible_prefix_joint_max_difference_rad=float(np.max(abs(sq[:visible_end + 1] - lq[:visible_end + 1]))),
            visible_prefix_velocity_max_difference_rad_s=float(np.max(abs(sv[:visible_end + 1] - lv[:visible_end + 1]))),
            committed_prefix_q_exact=bool(np.array_equal(sq[:commitment_end], lq[:commitment_end])),
            committed_prefix_qdot_exact=bool(np.array_equal(sv[:commitment_end], lv[:commitment_end]))))
    histories = []
    contrasts = []
    for context in reg['public_contexts']:
        folder = parent / 'evaluation' / (context + '-public_selection') / 'attempt-01'
        task = json.loads((parent / (context + '.json')).read_text())
        bindings += [binding(p) for p in (parent / (context + '.json'), folder / 'task/selection.npz', folder / 'task/pre-action-poses.npz')]
        with np.load(folder / 'task/pre-action-poses.npz') as pre, np.load(folder / 'task/selection.npz') as recorded:
            composer = None
            changed = 0
            for i in range(len(pre['time_s'])):
                measured = measured_row(pre, i)
                if composer is None:
                    composer = DistanceExitComposer(bank_path, measured, task['goal_xyz'], task['obstacles'])
                chunk = composer.reference(measured)
                continuous = packed(composer, chunk, measured, decoded, 'continuous')
                np.testing.assert_array_equal(continuous, recorded['reference'][i])
                np.testing.assert_array_equal(composer.last_indices, recorded['reference_source_indices'][i])
                if composer.family != str(recorded['candidate'][i]) or composer.choice != int(recorded['loop_choice'][i]):
                    raise ValueError('Composed choice changed')
                changed += int(not np.array_equal(continuous, packed(composer, chunk, measured, decoded, 'linear29')))
            histories.append(dict(context=context, states=i + 1, continuous_reference_indices_choice_exact=True,
                shadow_linear_changed_reference_rows=changed, loop_choice=composer.choice))
            if context.startswith('original'):
                other = json.loads((parent / (context.replace('original', 'farther') + '.json')).read_text())
                bindings.append(binding(parent / (context.replace('original', 'farther') + '.json')))
                controllers = None
                first = dict(continuous=None, linear29=None)
                counts = dict(continuous=0, linear29=0)
                for i in range(len(pre['time_s'])):
                    measured = measured_row(pre, i)
                    if controllers is None:
                        controllers = [DistanceExitComposer(bank_path, measured, t['goal_xyz'], task['obstacles']) for t in (task, other)]
                    chunks = [c.reference(measured) for c in controllers]
                    for method in counts:
                        refs = [packed(c, ch, measured, decoded, method) for c, ch in zip(controllers, chunks)]
                        if not np.array_equal(*refs):
                            counts[method] += 1
                            if first[method] is None:
                                first[method] = i
                contrasts.append(dict(context=context, common_history_states=i + 1,
                    first_changed_reference_tick=first, changed_reference_rows=counts,
                    choices=[c.choice for c in controllers], decision_tick=bank['decision_tick']))
    for record in bindings:
        checked(record)
    dump(output / 'bindings.json', bindings)
    result = dict(schema=reg['schema'], date='2026-09-19', native_attempts=0, teacher_action_queries=0, training_steps=0,
        scope=reg['scope'], candidates=audits, prefix_audit=prefixes, recorded_history_replay=histories,
        goal_response=contrasts, support_masks_modified=False,
        limitations='Linear29 references are shadow outputs on continuous histories; no codec motor-action or physical result. Nominal loop remains physically unqualified.',
        provenance=[dict(path=str(p.relative_to(PROJECT)), sha256=binding(p)['sha256']) for p in (reg_path, Path(__file__), output / 'registration.json', output / 'bindings.json')])
    dump(output / 'aggregate.json', result)
    dump(public, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'provenance'}, indent=2))


if __name__ == '__main__':
    main()
