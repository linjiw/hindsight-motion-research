"""Exploratory clearance audit of existing RVQ codes on the executed arm contrast."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

from .core import PatchQuantizer,sha256
from .critical import PROJECT,RUNTIME,dump


def urdf_fk(urdf,root_xyz,root_wxyz,joints,joint_names,body_names):
    """Vectorized link-frame FK; no dynamics or collision approximation is added here."""
    robot=ET.parse(urdf).getroot();pending=list(robot.findall('joint'))
    children={j.find('child').attrib['link'] for j in pending}
    roots={l.attrib['name'] for l in robot.findall('link')}-children
    if roots!={'pelvis'}:raise ValueError('Unexpected native URDF root')
    n=len(root_xyz);rot={'pelvis':Rotation.from_quat(root_wxyz[:,[1,2,3,0]]).as_matrix()}
    xyz={'pelvis':root_xyz};joint_index={name:i for i,name in enumerate(joint_names)}
    def vector(element,key,default):
        return np.fromstring(element.attrib.get(key,default) if element is not None else default,sep=' ')
    while pending:
        ready=[j for j in pending if j.find('parent').attrib['link'] in rot]
        if not ready:raise ValueError('Disconnected URDF kinematic tree')
        for joint in ready:
            parent=joint.find('parent').attrib['link'];child=joint.find('child').attrib['link']
            origin=joint.find('origin');translation=vector(origin,'xyz','0 0 0')
            origin_rotation=Rotation.from_euler('xyz',vector(origin,'rpy','0 0 0')).as_matrix()
            xyz[child]=xyz[parent]+np.einsum('tij,j->ti',rot[parent],translation)
            r=rot[parent]@origin_rotation
            if joint.attrib['type'] in ['revolute','continuous']:
                axis=vector(joint.find('axis'),'xyz','1 0 0')
                angle=joints[:,joint_index[joint.attrib['name']]]
                r=r@Rotation.from_rotvec(angle[:,None]*axis).as_matrix()
            elif joint.attrib['type']!='fixed':raise ValueError('Unsupported URDF joint type')
            rot[child]=r;pending.remove(joint)
    positions=np.stack([xyz[name] for name in body_names],axis=1)
    rotations=np.stack([rot[name] for name in body_names],axis=1)
    quats=Rotation.from_matrix(rotations.reshape(-1,3,3)).as_quat().reshape(n,len(body_names),4)[:,:,[3,0,1,2]]
    return dict(body_names=body_names,body_xyz=positions,body_wxyz=quats)


def audit(study):
    from gear_sonic.research.scene_distillation.collision_clearance import recorded_bounds,obstacle_separation
    study=Path(study);out=study/'token_clearance_audit';out.mkdir(exist_ok=False)
    dump(out/'protocol.json',dict(status='specified_before_computation',
        scope='Exploratory kinematic reconstruction on one already-selected arm contrast, not a held-out test',
        methods=['continuous_reference','VQ128','RVQ128x2'],
        validation='URDF FK must match both measured native empty-plane body traces within 0.1 mm',
        metric='Clearance lower-bound errors over all 145 proposed passages; selected-passage separation',
        physics='Decoded motions receive no physical execution label',
        no_new_teacher_rollouts=True))
    pre=PROJECT/'runs/critical_preflight_20260915_v2'
    contract=json.loads((pre/'metrics/episode-contract.json').read_text())
    proxies=json.loads((pre/'native_collision_proxies.json').read_text())
    urdf=RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf'
    codebook=np.load(PROJECT/'runs/pilot_20260915_v1/codebook.npz')
    quantizer=PatchQuantizer([codebook['level0'],codebook['level1']])
    manifest={r['motion_key']:r for r in json.loads((pre/'manifest.json').read_text())}
    proposals=json.loads((study/'all_geometry_proposals.json').read_text())
    selected=proposals['selected'];rows=[];fk_checks=[]
    for variant in ['tuck','wide']:
        episode=dict(np.load(pre/f'metrics/episode-critical_03_{variant}.npz'))
        poses=urdf_fk(urdf,episode['root_state_w'][:,:3]-episode['env_origin'],
                      episode['root_state_w'][:,3:7],episode['joint_pos'],
                      contract['measured_joint_names'],contract['measured_body_names'])
        error=float(np.linalg.norm(poses['body_xyz']-episode['body_xyz'],axis=-1).max())
        fk_checks.append(dict(variant=variant,max_native_position_error_m=error))
        if error>1e-4:raise ValueError(f'Native FK validation failed: {error}')
        reference=np.load(manifest[f'critical_03_{variant}']['reference_path'])
        q=reference['qpos'];codes=quantizer.encode(q[:,7:].reshape(-1,145))
        scores={}
        for method,angles in [('continuous_reference',q[:,7:]),
                              ('VQ128',quantizer.decode(codes,1).reshape(-1,29)),
                              ('RVQ128x2',quantizer.decode(codes,2).reshape(-1,29))]:
            decoded=urdf_fk(urdf,q[:,:3],q[:,3:7],angles,reference['joint_names'].tolist(),contract['measured_body_names'])
            bounds=recorded_bounds(proxies,decoded)
            clearance=lambda obstacles:min(float(obstacle_separation(bounds,o).min()) for o in obstacles)
            values=np.array([clearance(p['obstacles']) for p in proposals['proposals']])
            scores[method]=values
            rows.append(dict(variant=variant,method=method,
                selected_passage_clearance_lower_m=clearance(selected['obstacles']),
                selected_passage_certifies_3cm_sampled_separation=clearance(selected['obstacles'])>=.03,
                mean_clearance_bound_error_m=float(abs(values-scores['continuous_reference']).mean()),
                max_clearance_bound_error_m=float(abs(values-scores['continuous_reference']).max()),
                three_cm_decision_disagreements=int(((values>=.03)!=(scores['continuous_reference']>=.03)).sum()),
                evaluated_correlated_proposals=len(values),physics_verified=False))
    dump(out/'results.json',dict(rows=rows,native_fk_checks=fk_checks,
        urdf_sha256=sha256(urdf),codebook_sha256=sha256(PROJECT/'runs/pilot_20260915_v1/codebook.npz'),
        interpretation='Negative separation bounds do not prove collision; no decoder dynamics or generalization test'))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);a=parser.parse_args();audit(a.output)
