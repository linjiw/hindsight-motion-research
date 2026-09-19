"""Check the native treatment helper against the separately frozen shadow path."""
import importlib.util
import json
from pathlib import Path

import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_composer import native_reference
from gear_sonic.research.scene_distillation.duck_distance_exit import DistanceExitComposer
from hindsight_motion.complete_task import binding, checked
from hindsight_motion.critical import PROJECT
from hindsight_motion.distance_codec import motor_chunk

script = PROJECT / 'scripts/audit_distance_codec_preflight.py'
spec = importlib.util.spec_from_file_location('frozen_shadow', script)
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)
packet = PROJECT / 'runs/distance_codec_20260919_v1'
plan = json.loads((packet / 'plan.json').read_text())
for item in plan['bindings']:
    checked(item)
rows = []
for case in plan['cases']:
    if case['method'] != 'linear29':
        continue
    config = json.loads((Path(case['run_dir']) / 'config.json').read_text())
    task = json.loads(Path(config['task_path']).read_text())
    decoded, flat = {}, {}
    for family, routes in config['decoded_bank'].items():
        decoded[family] = {}
        for route, record in routes.items():
            with np.load(checked(record)) as data:
                decoded[family][route] = data['joint_position'].copy(), data['joint_velocity'].copy()
                flat[(family, route)] = decoded[family][route]
    composer = None
    with np.load(Path(case['parent_run']) / 'task/pre-action-poses.npz') as pre:
        for i in range(len(pre['time_s'])):
            measured = shadow.measured_row(pre, i)
            if composer is None:
                composer = DistanceExitComposer(checked(config['distance_exit_bank']), measured, task['goal_xyz'], task['obstacles'])
            chunk = composer.reference(measured)
            treated = motor_chunk(chunk, decoded, composer.family, composer.choice, int(composer.last_indices[0]), 'linear29')
            actual = native_reference(treated, rotation_wxyz(measured.root_wxyz),
                native_joint_names=measured.joint_names, native_frame_dt=.1).numpy()
            expected = shadow.packed(composer, chunk, measured, flat, 'linear29')
            np.testing.assert_array_equal(actual, expected)
    rows.append(dict(condition=case['condition'], historical_states=i + 1, adapter_matches_frozen_shadow_exactly=True))
result = dict(scope='Offline adapter consistency on recorded continuous histories, not physical execution',
    native_attempts=0, motor_action_queries=0, teacher_queries=0, rows=rows,
    provenance=[binding(p) for p in (Path(__file__), script, PROJECT / 'src/hindsight_motion/distance_codec.py', packet / 'plan.json')])
with (packet / 'adapter-check.json').open('x') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(json.dumps(result))
