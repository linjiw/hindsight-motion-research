"""Budget-explicit motion coding experiment on frozen critical scene candidates."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .core import PatchQuantizer,load_clip,sha256
from .critical import PROJECT,RUNTIME,dump
from .critical_tokens import urdf_fk

BODY_JOINTS=['waist_pitch_joint']+[f'{side}_{joint}_joint' for side in ('left','right')
    for joint in ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow')]
METHODS=['continuous','root_entry_hold','RVQ','RVQ_body9','RVQ_PCA9','linear29']


def interpolate_knots(values,frames):
    knots=np.arange(2,frames,5)
    if len(values)!=len(knots):raise ValueError('One symbol vector per five-frame patch required')
    return np.stack([np.interp(np.arange(frames),knots,values[:,j]) for j in range(values.shape[1])],axis=1)


def quantize12(values,scale):
    raw=np.rint(values/scale*2047)
    symbols=np.clip(raw,-2047,2047).astype(np.int16)
    return symbols,symbols.astype(float)*scale/2047,int(np.count_nonzero(abs(raw)>2047))


def pca(data):
    mean=data.mean(0);_,vectors=np.linalg.eigh(np.cov(data-mean,rowvar=False))
    basis=vectors[:,-9:][:,::-1].copy()
    for j in range(9):
        if basis[np.abs(basis[:,j]).argmax(),j]<0:basis[:,j]*=-1
    return mean,basis


def fit(output,quantizer,joint_names):
    inventory=list(csv.DictReader((PROJECT/'runs/pilot_20260915_v1/inventory.csv').open()))
    # Exclude all three current physical-study source groups from the new fit.
    selected=[r for r in inventory if r['split']=='train' and r['source_group'] not in ('KIT/205','KIT/9','KIT/317')]
    residuals=[];angles=[]
    for row in selected:
        if sha256(row['source_path'])!=row['sha256']:raise ValueError('Training source changed')
        q=load_clip(row['source_path'],4,5)['qpos'][:,7:]
        ids=quantizer.encode(q.reshape(-1,145));decoded=quantizer.decode(ids,2).reshape(-1,29)
        residuals.append((q-decoded)[2::5]);angles.append(q[2::5])
    residuals=np.concatenate(residuals);angles=np.concatenate(angles)
    mean,basis=pca(residuals);coefficients=(residuals-mean)@basis
    indices=np.array([joint_names.index(n) for n in BODY_JOINTS])
    model=dict(mean=mean,basis=basis,body_indices=indices,
               body_scale=np.maximum(abs(residuals[:,indices]).max(0)*1.01,1e-5),
               pca_scale=np.maximum(abs(coefficients).max(0)*1.01,1e-5),
               angle_scale=np.maximum(abs(angles).max(0)*1.01,1e-5))
    np.savez_compressed(output/'residual_model.npz',**model)
    dump(output/'fit_receipt.json',dict(training_motions=len(selected),training_source_groups=len({r['source_group'] for r in selected}),
        training_knots=len(residuals),new_fit_excluded_groups=['KIT/205','KIT/9','KIT/317'],
        existing_RVQ='Frozen original pilot codebook; its historical training split may include study source groups',
        anatomical_prior='Nine fixed waist/shoulder/elbow channels, selected by body anatomy and intended families, not by scene scores',
        files=[dict(path=r['source_path'],sha256=r['sha256'],source_group=r['source_group']) for r in selected]))
    return model


def reconstruct(q,quantizer,model):
    angles=q[:,7:];ids=quantizer.encode(angles.reshape(-1,145));base=quantizer.decode(ids,2).reshape(-1,29)
    residual=(angles-base)[2::5];indices=model['body_indices'];methods={};symbols={};clipped={}
    methods.update(continuous=angles,root_entry_hold=np.repeat(angles[:1],len(q),axis=0),RVQ=base)
    symbols['rvq']=ids
    encoded,decoded,n=quantize12(residual[:,indices],model['body_scale'])
    corrected=base.copy();corrected[:,indices]+=interpolate_knots(decoded,len(q))
    methods['RVQ_body9']=corrected;symbols['body9']=encoded;clipped['RVQ_body9']=n
    coefficients=(residual-model['mean'])@model['basis']
    encoded,decoded,n=quantize12(coefficients,model['pca_scale'])
    methods['RVQ_PCA9']=base+interpolate_knots(decoded@model['basis'].T+model['mean'],len(q))
    symbols['pca9']=encoded;clipped['RVQ_PCA9']=n
    encoded,decoded,n=quantize12(angles[2::5],model['angle_scale'])
    methods['linear29']=interpolate_knots(decoded,len(q));symbols['linear29']=encoded;clipped['linear29']=n
    return methods,symbols,clipped


def cases():
    result=[]
    first=PROJECT/'runs/critical_preflight_20260915_v2'
    manifest={r['motion_key']:r for r in json.loads((first/'manifest.json').read_text())}
    result.append(dict(pair_id='arm03',family='arm_tuck',source_group='KIT/205',
        proposals=json.loads((PROJECT/'runs/critical_interventions_20260915_v1/all_geometry_proposals.json').read_text()),
        records={v:manifest[f'critical_03_{v}'] for v in ('tuck','wide')}))
    for pair in ('arm02','arm07','duck02'):
        folder='expansion_beam_refinement_20260915_v1' if pair=='duck02' else 'expansion_proposals_20260915_v1'
        p=json.loads((PROJECT/'runs'/folder/f'{pair}.json').read_text())
        result.append(dict(pair_id=pair,family=p['family'],source_group=p['source_group'],proposals=p,records=p['records']))
    return result


def inner_points(bounds,proxies,family):
    points=[];radii=[]
    for i,p in enumerate(proxies):
        relevant=any(s in p['body'] for s in ('shoulder','elbow','wrist')) if family=='arm_tuck' else p['body']=='torso_link'
        if not relevant or p['kind'] not in ('Capsule','Sphere','Cube','Cylinder'):continue
        corners=bounds[:,i];edges=corners[:,[4,2,1]]-corners[:,0,None];lengths=np.linalg.norm(edges,axis=-1)
        radius=lengths[0].min()/2;axis=int(lengths[0].argmax());extent=max(0.,lengths[0,axis]/2-radius)
        for u in ((0.,) if family=='arm_tuck' else (-1.,0.,1.)):
            points.append(corners.mean(1)+u*extent*edges[:,axis]/lengths[:,axis,None]);radii.append(radius)
    return np.stack(points,axis=1),np.asarray(radii)


def run(output):
    from gear_sonic.research.scene_distillation.collision_clearance import recorded_bounds,obstacle_separation
    from gear_sonic.research.scene_distillation.critical_pair_calibration import point_distance
    output=Path(output);output.mkdir(parents=True,exist_ok=False);(output/'decoded').mkdir()
    dump(output/'protocol.json',dict(registered_unix_s=time.time(),status='specified_before_fit_and_scoring',methods=METHODS,
        hypotheses=['Compressed anatomy channels may preserve critical clearance better than a same-budget generic PCA residual',
                    'Simple low-rate full-joint interpolation may suffice at a larger bit budget'],
        cases=['arm03','arm02','arm07','duck02'],scene_candidates='All frozen candidates from the four previous physical-study pairs',
        quantization='12-bit signed scalar symbols with per-channel ranges from training only; clipping is counted',
        knots='10 Hz, patch centres, linear interpolation with constant boundary extrapolation',
        joint_payload_bits_per_second=dict(continuous=46400,root_entry_hold=0,RVQ=140,RVQ_body9=1220,RVQ_PCA9=1220,linear29=3480),
        shared_root_side_channel_bits_per_second=11200,
        payload_caveat='Logical coding rates for 50 Hz float32 input. Excludes shared model/codebook and headers; root-entry hold also sends 29 initial float32 values. NPZ files are not a packed codec.',
        anatomical_channels=BODY_JOINTS,scene_thresholds=dict(target_separation_lower_m=.03,contrast_inner_overlap_m=.01),
        no_physical_decoded_execution=True,no_held_out_generalization=True,
        information_boundary='Full future motion is an offline proposer input or target, never a student actor observation'))
    shutil.copy2(__file__,output/'code_snapshot.py')
    initial=PROJECT/'runs/critical_preflight_20260915_v2';contract=json.loads((initial/'metrics/episode-contract.json').read_text())
    proxies=json.loads((initial/'native_collision_proxies.json').read_text());urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    book=np.load(PROJECT/'runs/pilot_20260915_v1/codebook.npz');quantizer=PatchQuantizer([book['level0'],book['level1']])
    example=next(iter(cases()[0]['records'].values()));joint_names=np.load(example['reference_path'])['joint_names'].tolist()
    model=fit(output,quantizer,joint_names);rows=[];pair_rows=[]
    for case in cases():
        proposals=case['proposals']['proposals'];selected=case['proposals']['selected']
        selected_index=next(i for i,p in enumerate(proposals) if p==selected)
        values={};overlaps={};variants=list(case['records'])
        for variant,record in case['records'].items():
            reference=np.load(record['reference_path']);q=reference['qpos'];names=reference['joint_names'].tolist()
            if names!=joint_names:raise ValueError('Joint ordering changed')
            recon,symbols,clips=reconstruct(q,quantizer,model)
            np.savez_compressed(output/'decoded'/f"{case['pair_id']}_{variant}.npz",root_wxyz=q[:,:7],**recon,**{f'code_{k}':v for k,v in symbols.items()})
            for method,angles in recon.items():
                poses=urdf_fk(urdf,q[:,:3],q[:,3:7],angles,names,contract['measured_body_names'])
                bounds=recorded_bounds(proxies,poses);points,radii=inner_points(bounds,proxies,case['family'])
                clear=[];witness=[]
                for p in proposals:
                    clear.append(min(float(obstacle_separation(bounds,o).min()) for o in p['obstacles']))
                    witness.append(min(float((point_distance(points,o)-radii).min()) for o in (p['obstacles'][:1] if case['family']=='duck' else p['obstacles'])))
                clear=np.asarray(clear);witness=np.asarray(witness);values[variant,method]=clear;overlaps[variant,method]=witness
                baseline=values[variant,'continuous'];admit=clear>=.03;truth=baseline>=.03
                rows.append(dict(pair_id=case['pair_id'],source_group=case['source_group'],variant=variant,method=method,
                    joint_angle_rmse_rad=float(np.sqrt(np.mean((angles-q[:,7:])**2))),
                    clearance_mae_m=float(abs(clear-baseline).mean()),clearance_max_error_m=float(abs(clear-baseline).max()),
                    clearance_decision_flips=int(np.count_nonzero(admit!=truth)),false_clearances=int(np.count_nonzero(admit&~truth)),
                    false_rejections=int(np.count_nonzero(~admit&truth)),candidates=len(clear),
                    selected_clearance_lower_m=float(clear[selected_index]),scalar_symbols_clipped=clips.get(method,0),physics_verified=False))
            print(f"Scored {case['pair_id']} {variant}",flush=True)
        positive,negative=variants
        truth=(values[positive,'continuous']>=.03)&(overlaps[negative,'continuous']<=-.01)
        for method in METHODS:
            admit=(values[positive,method]>=.03)&(overlaps[negative,method]<=-.01)
            pair_rows.append(dict(pair_id=case['pair_id'],method=method,candidates=len(admit),
                continuous_reference_admitted=int(truth.sum()),method_admitted=int(admit.sum()),
                pair_decision_flips=int(np.count_nonzero(admit!=truth)),false_admissions=int(np.count_nonzero(admit&~truth)),
                missed_admissions=int(np.count_nonzero(~admit&truth)),selected_reference_admitted=bool(truth[selected_index]),
                selected_method_admitted=bool(admit[selected_index])))
        np.savez_compressed(output/f"{case['pair_id']}_candidate_scores.npz",**{f'clearance_{v}_{m}':x for (v,m),x in values.items()},
                            **{f'witness_{v}_{m}':x for (v,m),x in overlaps.items()})
    summary=[]
    for method in METHODS:
        r=[x for x in rows if x['method']==method];p=[x for x in pair_rows if x['method']==method]
        summary.append(dict(method=method,macro_clearance_mae_m=float(np.mean([x['clearance_mae_m'] for x in r])),
            clearance_decision_flips=sum(x['clearance_decision_flips'] for x in r),motion_scene_evaluations=sum(x['candidates'] for x in r),
            pair_decision_flips=sum(x['pair_decision_flips'] for x in p),pair_scene_evaluations=sum(x['candidates'] for x in p),
            false_pair_admissions=sum(x['false_admissions'] for x in p),scalar_symbols_clipped=sum(x['scalar_symbols_clipped'] for x in r)))
    dump(output/'results.json',dict(summary=summary,motion_rows=rows,pair_rows=pair_rows,
        interpretation='Development kinematic decision preservation, not collision proof or executed decoder utility',
        urdf_sha256=sha256(urdf),codebook_sha256=sha256(PROJECT/'runs/pilot_20260915_v1/codebook.npz')))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();run(a.output.resolve())
