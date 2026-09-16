"""Reproducible, bounded native-teacher preflight for critical motion decisions."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import shutil
import time

import joblib
import numpy as np
from scipy.spatial.transform import Rotation

from .core import load_clip, sha256

RUNTIME = Path(os.environ.get('HINDSIGHT_RUNTIME', '/home/linjiw/groot-wbc-sonic-sim-trackb'))
PROJECT = Path(os.environ.get('HINDSIGHT_PROJECT', Path(__file__).resolve().parents[2]))
TEACHER = Path(os.environ.get('HINDSIGHT_TEACHER', '/home/linjiw/research-data/m2s-sonic-qualification-20260912/release/checkpoint.pt'))
SOURCES = [
    'KIT_11_WalkingStraightForwards02_poses_100_jpos',
    'KIT_167_walking_slow02_poses_100_jpos',
    'KIT_183_walking_slow02_poses_100_jpos',
    'KIT_205_walking_slow02_poses_100_jpos',
    'KIT_314_walking_medium03_poses_100_jpos',
    'KIT_359_walking_slow04_poses_100_jpos',
]


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def edit_motion(qpos, variant, fps=50):
    """Candidate interventions, never interpreted as physically valid a priori.

    Shared 0.6 s entry/exit, 0.6 s quintic ramps. Root/legs are identical
    for arm edits; the yaw edit intentionally changes body-vs-travel heading.
    """
    q = np.asarray(qpos, dtype=float).copy()
    t = np.arange(len(q)) / fps
    u = np.clip(np.minimum(t - .6, t[-1] - .6 - t) / .6, 0, 1)
    weight = u**3 * (10 - 15*u + 6*u*u)
    if variant in ('tuck', 'wide'):
        target = np.zeros((len(q), 14))
        # MJ arms: shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw.
        target[:, 0] = -.12
        target[:, 7] = -.12
        target[:, 1] = .10 if variant == 'tuck' else .85
        target[:, 8] = -.10 if variant == 'tuck' else -.85
        target[:, 3] = 1.25 if variant == 'tuck' else .55
        target[:, 10] = 1.25 if variant == 'tuck' else .55
        q[:, 22:36] += weight[:, None] * (target - q[:, 22:36])
    elif variant == 'side':
        turn = Rotation.from_rotvec(np.c_[np.zeros((len(q), 2)), weight*np.pi/2])
        root = Rotation.from_quat(q[:, [4, 5, 6, 3]])
        q[:, 3:7] = (turn * root).as_quat()[:, [3, 0, 1, 2]]
    elif variant != 'original':
        raise ValueError(variant)
    return q, weight


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        qpos_to_sonic_motion_entry, sonic_motion_entry_to_qpos, save_sonic_motion_file,
        KIMODO_G1_JOINT_NAMES, G1_ISAACLAB_JOINT_NAMES,
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'motions').mkdir()
    (output/'references').mkdir()
    inventory = {r['motion_id']: r for r in csv.DictReader(
        (PROJECT/'runs/pilot_20260915_v1/inventory.csv').open())}
    checkpoint_hash = sha256(TEACHER)
    records, metadata = [], {}
    for source_idx, name in enumerate(SOURCES):
        row = inventory[name]
        if sha256(row['source_path']) != row['sha256']:
            raise ValueError('Source changed since pilot')
        clip = load_clip(row['source_path'], seconds=4., patch_frames=5)
        original = clip['qpos'].copy()
        original[:, :2] -= original[0, :2].copy()
        for variant in ('original', 'tuck', 'wide', 'side'):
            key = f'critical_{source_idx:02d}_{variant}'
            q, weight = edit_motion(original, variant)
            entry = qpos_to_sonic_motion_entry(q, source_fps=50,
                                              canonicalize_horizontal_origin=False)
            recovered = sonic_motion_entry_to_qpos(entry)
            roundtrip = float(np.max(np.abs(q-recovered)))
            if roundtrip > 1e-6:
                raise ValueError('Native reference roundtrip failed')
            path = output/'motions'/f'{key}.pkl'
            save_sonic_motion_file(path, motion_key=key, motion_entry=entry)
            ref = output/'references'/f'{key}.npz'
            np.savez_compressed(ref, qpos=q, edit_weight=weight,
                                time_s=np.arange(len(q))/50, joint_names=KIMODO_G1_JOINT_NAMES)
            metadata[key] = {'length': len(q), 'fps': 50}
            records.append(dict(motion_key=key, variant=variant, carrier_id=source_idx,
                                source_id=name, source_group=row['source_group'],
                                source_path=row['source_path'], source_sha256=row['sha256'],
                                source_start_frame=clip['start_frame'],
                                source_end_frame_exclusive=clip['end_frame_exclusive'],
                                split='development', historical_pilot_split=row['split'],
                                motion_path=str(path), motion_sha256=sha256(path),
                                reference_path=str(ref), reference_sha256=sha256(ref),
                                frames=len(q), roundtrip_max_error=roundtrip,
                                same_reference_entry=True, same_simulator_entry_verified=False,
                                empty_scene_execution_verified=False))
    joblib.dump(metadata, output/'motions/metadata.pkl')
    dump(output/'manifest.json', records)
    contract = dict(schema='hindsight_native_teacher_preflight_v1',
                    teacher_checkpoint=str(TEACHER), teacher_sha256=checkpoint_hash,
                    teacher_config_sha256=sha256(TEACHER.with_name('config.yaml')),
                    runtime_root=str(RUNTIME), precision='fp32', max_control_steps=220,
                    max_root_xy_m=.25, max_body_mean_m=.10,
                    native_joint_names=list(G1_ISAACLAB_JOINT_NAMES),
                    reference_joint_names=list(KIMODO_G1_JOINT_NAMES),
                    actor_proprio_width=930, teacher_motor_token_width=64,
                    teacher_action_width=29, teacher_future_reference_width=640,
                    mocap_tokens_are_motor_tokens=False,
                    reference_fps=50, control_dt_s=.02, physics_dt_s=.005,
                    motion_manifest=str(output/'manifest.json'),
                    scope='Empty-plane teacher support; no scene or causal labels yet')
    dump(output/'teacher_and_runtime_contract.json', contract)
    dump(output/'preflight_registration.json', dict(
        status='registered_before_execution', created_unix_s=time.time(),
        maximum_preflight_launches=2, maximum_scheduled_motion_episodes=48,
        first_batch_episodes=len(records), first_batch_seed=20260915,
        maximum_wall_seconds_per_launch=1200,
        selection='Six explicitly listed KIT walking carriers from six source groups',
        candidate_edits='Original, smooth arm tuck, wide arms, +90 degree root yaw',
        adaptation='Second batch may address measured failures; freeze its own manifest first',
        exclusions='Development only; excluded from future frozen evaluation',
        main_study_attempts_consumed=0,
        launch_failures='Retain stderr/exit and planned episode count; no unlogged retries',
        qualification='No native termination, mean tracked body error <= .10 m, max root XY error <= .25 m',
        mechanism_status='Candidate physical continuations; common entry state must be verified separately'))
    print(json.dumps({'prepared':str(output), 'episodes':len(records)}))


def launch(output):
    output = Path(output)
    manifest = json.loads((output/'manifest.json').read_text())
    if (output/'launch.json').exists():
        raise FileExistsError('Run directory already launched; never overwrite attempts')
    contract = output/'teacher_and_runtime_contract.json'
    lock = json.loads(contract.read_text())
    if sha256(lock['teacher_checkpoint']) != lock['teacher_sha256']:
        raise ValueError('Teacher checkpoint changed')
    for row in manifest:
        if sha256(row['motion_path']) != row['motion_sha256']:
            raise ValueError('Native motion changed')
    n = len(manifest)
    argv = [str(RUNTIME/'.venv_isaaclab/bin/python'), 'gear_sonic/eval_agent_trl.py',
            f"checkpoint={lock['teacher_checkpoint']}", '++headless=true', f'++num_envs={n}',
            '++seed=20260915', '++use_wandb=false', '++use_encoder=g1',
            f'++eval_output_dir={output}/metrics', f'++eval_base_dir={output}/hydra',
            '++eval_callbacks=[im_eval]', '++run_eval_loop=false', '++trainer.schedule_dict=null',
            '++manager_env.config.terrain_type=plane', '++manager_env.config.env_spacing=8.0',
            '++manager_env.config.render_results=false', '++manager_env.config.render_ego=false',
            '++manager_env.commands.motion.debug_vis=false',
            f'++manager_env.commands.motion.motion_lib_cfg.motion_file={output}/motions',
            f'++manager_env.commands.motion.motion_lib_cfg.override_num_motions_to_load={n}',
            '++manager_env.commands.motion.motion_lib_cfg.sort_motion_keys=true',
            '++manager_env.commands.motion.motion_lib_cfg.multi_thread=false',
            '++manager_env.commands.motion.motion_lib_cfg.adaptive_sampling.enable=false',
            '++manager_env.commands.motion.cat_upper_body_poses=false',
            '++manager_env.commands.motion.freeze_frame_aug=false',
            '++callbacks.im_eval._target_=hindsight_motion.native.CriticalPreflightCallback',
            f'++callbacks.im_eval.collection_contract={contract}',
            '++callbacks.im_eval.max_eval_steps=null']
    argv.extend(lock.get('runtime_overrides', []))
    env = os.environ.copy()
    env['PYTHONPATH'] = str(PROJECT/'src') + ':' + str(RUNTIME) + ':' + env.get('PYTHONPATH', '')
    env['WANDB_MODE'] = 'disabled'
    start = time.time()
    snapshot = output/'code_snapshot'
    snapshot.mkdir(exist_ok=True)
    source_receipt = []
    for file in ('critical.py', 'native.py', 'core.py', 'interventions.py', 'scene_native.py',
                 'batch_native.py', 'batch_scene.py', 'scene_evidence.py'):
        source = PROJECT/'src/hindsight_motion'/file
        if not source.exists():
            continue
        shutil.copy2(source, snapshot/file)
        source_receipt.append(dict(path=str(source), sha256=sha256(source)))
    dump(output/'code_receipt.json', source_receipt)
    dump(output/'launch.json', dict(argv=argv, cwd=str(RUNTIME), start_unix_s=start,
                                    planned_episodes=n, timeout_s=1200))
    with (output/'evaluation.log').open('w') as log:
        try:
            result = subprocess.run(argv, cwd=RUNTIME, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=1200)
            status = dict(exit_code=result.returncode, timed_out=False)
        except subprocess.TimeoutExpired:
            status = dict(exit_code=None, timed_out=True)
    status.update(elapsed_s=time.time()-start, completed_unix_s=time.time())
    dump(output/'exit.json', status)
    print(json.dumps(status))


def prepare_controlled(output):
    """Second registered preflight: remove independent nuisance randomization."""
    first = PROJECT/'runs/critical_preflight_20260915_v1'
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(first/'motions', output/'motions')
    manifest = json.loads((first/'manifest.json').read_text())
    for row in manifest:
        row['motion_path'] = str(output/'motions'/Path(row['motion_path']).name)
    dump(output/'manifest.json', manifest)
    lock = json.loads((first/'teacher_and_runtime_contract.json').read_text())
    lock['motion_manifest'] = str(output/'manifest.json')
    lock['runtime_overrides'] = [
        '++manager_env.observations.policy.enable_corruption=false',
        '++manager_env.observations.tokenizer.enable_corruption=false',
        *[f'++manager_env.events.{event}=null' for event in (
            'physics_material', 'add_joint_default_pos', 'base_com', 'randomize_rigid_body_mass', 'push_robot')]]
    lock['scope'] = 'Nominal robot, noiseless sensor preflight; common state/history and native geometry audit'
    dump(output/'teacher_and_runtime_contract.json', lock)
    dump(output/'preflight_registration.json', dict(
        parent_registration=str(first/'preflight_registration.json'),
        prior_scheduled_episodes=24, this_batch_episodes=24,
        maximum_total_preflight_episodes=48, prior_native_launches=1,
        reason='First batch shares root/joint state but independent sensor noise and startup DR change proprioception/dynamics',
        hypothesis='Removing these nuisance differences enables controlled motion-scene comparisons',
        selection='All original 24 candidates retained; no success-based replacement',
        status='registered_before_execution', created_unix_s=time.time(),
        main_study_attempts_consumed=0))
    print(json.dumps({'prepared':str(output), 'episodes':len(manifest)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'prepare_controlled', 'launch'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    globals()[args.command](args.output.resolve())
