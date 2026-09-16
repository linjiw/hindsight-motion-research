"""Registered expansion of executable arm and ducking motion pairs."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import time

import joblib
import numpy as np

from .contact_edit import duck_preserving_feet
from .core import load_clip,sha256
from .critical import PROJECT,RUNTIME,dump,edit_motion,launch

SOURCES=[
 'KIT_205_walking_slow02_poses_100_jpos',
 'KIT_424_walking_slow10_poses_100_jpos',
 'KIT_9_walking_slow10_poses_100_jpos',
 'KIT_3_walking_slow07_poses_100_jpos',
 'Eyes_Japan_Dataset_shiono_walk-03-sneak-shiono_poses_120_jpos',
 'KIT_348_walking_slow08_poses_100_jpos',
 'KIT_425_walking_slow05_poses_100_jpos',
 'KIT_317_step_over_gap05_poses_100_jpos',
 'KIT_183_walking_slow02_poses_100_jpos',
 'KIT_167_walking_slow02_poses_100_jpos',
 'KIT_11_WalkingStraightForwards02_poses_100_jpos',
 'KIT_359_walking_slow04_poses_100_jpos',
]


def prepare(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        qpos_to_sonic_motion_entry,sonic_motion_entry_to_qpos,save_sonic_motion_file,KIMODO_G1_JOINT_NAMES)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'motions').mkdir();(output/'references').mkdir()
    inventory={r['motion_id']:r for r in csv.DictReader((PROJECT/'runs/pilot_20260915_v1/inventory.csv').open())}
    dump(output/'registration.json',dict(schema='critical_expansion_registration_v1',
        registered_unix_s=time.time(),source_ids=SOURCES,source_group_count=12,
        first_batch_episodes=48,maximum_new_preflight_episodes=96,
        previous_preflight_episodes=48,maximum_new_preflight_launches=4,
        allocation='48 candidate qualifications; up to 8 batched-scene equivalence episodes; remaining 40 reserved for documented follow-up',
        candidate_variants=['original','tuck','wide','duck'],duck_depth_m=.14,
        selection='One explicit clip per named source group, including prior carrier 205 as an anchor',
        qualification='Unchanged no-termination, <=10 cm mean body and <=25 cm maximum root XY error',
        main_study_previous_episodes=24,main_study_global_ceiling=480,
        new_scene_target='At most four additional pairs, preferentially two new-source arm pairs and two duck pairs',
        candidate_failures_retained=True,split='development',
        claims='New source groups are experimental expansion, not a frozen held-out benchmark'))
    rows=[];metadata={};failures=[]
    urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    for carrier,source_id in enumerate(SOURCES):
        source=inventory[source_id]
        if sha256(source['source_path'])!=source['sha256']:raise ValueError('Source changed')
        clip=load_clip(source['source_path'],4.,5)
        if len(clip['qpos'])!=200:raise ValueError('Expansion requires 200-frame carriers')
        q=clip['qpos'].copy();q[:,:2]-=q[0,:2].copy()
        tuck,weight=edit_motion(q,'tuck')
        candidates=[('original',q,{}),('tuck',tuck,{}),('wide',edit_motion(q,'wide')[0],{})]
        try:
            duck,_,audit=duck_preserving_feet(tuck,KIMODO_G1_JOINT_NAMES,urdf)
            candidates.append(('duck',duck,audit))
        except ValueError as exc:
            failures.append(dict(carrier_id=carrier,variant='duck',reason=str(exc)))
        for variant,reference,audit in candidates:
            key=f'expand_{carrier:02d}_{variant}'
            entry=qpos_to_sonic_motion_entry(reference,source_fps=50,canonicalize_horizontal_origin=False)
            roundtrip=float(np.max(abs(reference-sonic_motion_entry_to_qpos(entry))))
            if roundtrip>1e-6:raise ValueError('Roundtrip mismatch')
            path=output/'motions'/f'{key}.pkl'
            save_sonic_motion_file(path,motion_key=key,motion_entry=entry)
            ref=output/'references'/f'{key}.npz'
            np.savez_compressed(ref,qpos=reference,time_s=np.arange(200)/50,
                                edit_weight=weight,joint_names=KIMODO_G1_JOINT_NAMES)
            row=dict(motion_key=key,carrier_id=carrier,variant=variant,source_id=source_id,
                     source_group=source['source_group'],split='development',
                     source_path=source['source_path'],source_sha256=source['sha256'],
                     source_start_frame=clip['start_frame'],source_end_frame_exclusive=clip['end_frame_exclusive'],
                     motion_path=str(path),motion_sha256=sha256(path),reference_path=str(ref),
                     reference_sha256=sha256(ref),frames=200,roundtrip_max_error=roundtrip,edit_audit=audit)
            rows.append(row);metadata[key]=dict(length=200,fps=50)
        print(f'Prepared carrier {carrier}: {source_id}',flush=True)
    dump(output/'manifest.json',rows);dump(output/'construction_failures.json',failures)
    joblib.dump(metadata,output/'motions/metadata.pkl')
    lock=json.loads((PROJECT/'runs/critical_preflight_20260915_v2/teacher_and_runtime_contract.json').read_text())
    lock['motion_manifest']=str(output/'manifest.json')
    lock['scope']='Registered source and contact-consistent ducking expansion, nominal dynamics'
    dump(output/'teacher_and_runtime_contract.json',lock)
    snapshot=output/'preparation_code';snapshot.mkdir()
    for name in ['expansion.py','contact_edit.py']:
        shutil.copy2(PROJECT/'src/hindsight_motion'/name,snapshot/name)
    print(json.dumps(dict(prepared_episodes=len(rows),construction_failures=len(failures))))


def prepare_ducks(output):
    from gear_sonic.dataset_generation.kimodo_motion_adapter import (
        qpos_to_sonic_motion_entry,sonic_motion_entry_to_qpos,save_sonic_motion_file)
    first=PROJECT/'runs/expansion_preflight_20260915_v1'
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'motions').mkdir();(output/'references').mkdir()
    dump(output/'registration.json',dict(parent=str(first/'registration.json'),
        registered_unix_s=time.time(),previous_new_preflight_episodes=36,
        candidate_count=12,depth_grid_m=[.12,.10,.08,.06],
        adaptation='0.14 m edits exceeded ankle limits while preserving foot orientation; select deepest smaller geometrically valid edit before physical execution',
        geometry_thresholds=dict(max_foot_position_m=.002,max_foot_orientation_rad=.02),
        no_failed_physical_duck_replacements=True,split='development'))
    manifest=json.loads((first/'manifest.json').read_text())
    rows=[];metadata={};trials=[]
    urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    for original in [r for r in manifest if r['variant']=='tuck']:
        ref=np.load(original['reference_path']);q=ref['qpos'];names=ref['joint_names'].tolist()
        for depth in [.12,.10,.08,.06]:
            try:
                candidate,weight,audit=duck_preserving_feet(q,names,urdf,depth=depth)
                trials.append(dict(carrier_id=original['carrier_id'],depth=depth,admitted=True,**audit))
            except ValueError as exc:
                trials.append(dict(carrier_id=original['carrier_id'],depth=depth,admitted=False,reason=str(exc)))
                continue
            row=original.copy();key=f"expand_{row['carrier_id']:02d}_duck"
            entry=qpos_to_sonic_motion_entry(candidate,source_fps=50,canonicalize_horizontal_origin=False)
            error=float(np.max(abs(candidate-sonic_motion_entry_to_qpos(entry))))
            if error>1e-6:raise ValueError('Native roundtrip failure')
            path=output/'motions'/f'{key}.pkl';save_sonic_motion_file(path,motion_key=key,motion_entry=entry)
            reference=output/'references'/f'{key}.npz'
            np.savez_compressed(reference,qpos=candidate,edit_weight=weight,time_s=np.arange(200)/50,joint_names=names)
            row.update(motion_key=key,variant='duck',motion_path=str(path),motion_sha256=sha256(path),
                       reference_path=str(reference),reference_sha256=sha256(reference),edit_audit=audit,
                       baseline_motion_key=original['motion_key'],roundtrip_max_error=error)
            rows.append(row);metadata[key]=dict(length=200,fps=50)
            print(f"Prepared carrier {row['carrier_id']} duck depth {depth} m",flush=True)
            break
    dump(output/'geometry_trials.json',trials);dump(output/'manifest.json',rows)
    joblib.dump(metadata,output/'motions/metadata.pkl')
    lock=json.loads((first/'teacher_and_runtime_contract.json').read_text())
    lock['motion_manifest']=str(output/'manifest.json');dump(output/'teacher_and_runtime_contract.json',lock)
    snapshot=output/'preparation_code';snapshot.mkdir()
    for name in ['expansion.py','contact_edit.py']:shutil.copy2(PROJECT/'src/hindsight_motion'/name,snapshot/name)
    print(json.dumps(dict(prepared_episodes=len(rows),geometric_trials=len(trials))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','prepare_ducks','launch'])
    parser.add_argument('output',type=Path);a=parser.parse_args();globals()[a.command](a.output.resolve())
