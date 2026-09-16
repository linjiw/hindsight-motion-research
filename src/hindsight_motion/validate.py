from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .core import load_clip, sha256
from .pilot import write_csv, write_json


def interpolate(q):
    t = np.arange(len(q), dtype=float)
    ti = np.arange(2*len(q)-1, dtype=float)/2
    expanded = np.stack([np.interp(ti,t,q[:,i]) for i in range(q.shape[1])],axis=1)
    rot = Rotation.from_quat(q[:,3:7][:,[1,2,3,0]])
    expanded[:,3:7] = Slerp(t,rot)(ti).as_quat()[:,[3,0,1,2]]
    return expanded


def minimum_distance(model, data, qpos, robot_ids, obstacle_ids):
    robot_ids = np.asarray(robot_ids); obstacle_ids = np.asarray(obstacle_ids)
    best = 10.; best_link = None; frame = None; queries = 0
    segment = np.empty(6)
    for t,q in enumerate(qpos):
        data.qpos[:] = q; mujoco.mj_kinematics(model,data)
        # Both robot and obstacle bounding spheres enclose their collision shapes.
        dist = np.linalg.norm(data.geom_xpos[robot_ids,None]-data.geom_xpos[None,obstacle_ids],axis=-1)
        lower = dist-model.geom_rbound[robot_ids,None]-model.geom_rbound[None,obstacle_ids]
        for ri,oi in np.argwhere(lower < best):
            g = int(robot_ids[ri]); o = int(obstacle_ids[oi])
            value = mujoco.mj_geomDistance(model,data,g,o,best,segment)
            queries += 1
            if value < best:
                best = float(value); best_link = model.body(int(model.geom_bodyid[g])).name; frame = t
    return best,best_link,frame,queries


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((a.pilot/'config.json').read_text())
    scenes=[s for s in map(json.loads,(a.pilot/'scenes.jsonl').read_text().splitlines()) if s['split']=='test']
    neutral=np.load(a.pilot/'codebook.npz')['neutral_joints']
    rows=[]
    for i,s in enumerate(scenes):
        spec=mujoco.MjSpec.from_file(cfg['robot_xml'])
        for k,b in enumerate(s['boxes']):
            spec.worldbody.add_geom(name=f'hindsight_box_{k}',type=mujoco.mjtGeom.mjGEOM_BOX,
                                   pos=b[:3],size=b[3:],contype=1,conaffinity=1)
        model=spec.compile();data=mujoco.MjData(model)
        robot_ids=np.flatnonzero((model.geom_bodyid>0)&((model.geom_contype!=0)|(model.geom_conaffinity!=0)))
        obstacles=[model.geom(f'hindsight_box_{k}').id for k in range(len(s['boxes']))]
        clip=load_clip(s['source_path'],cfg['window_seconds'],cfg['patch_frames'])
        q=interpolate(clip['qpos']); rigid=q.copy();rigid[:,7:]=neutral
        d,body,t,queries=minimum_distance(model,data,q,robot_ids,obstacles)
        r,rbody,rt,rqueries=minimum_distance(model,data,rigid,robot_ids,obstacles)
        rows.append({'motion_id':s['motion_id'],'source_group':s['source_group'],'candidate_id':s['candidate_id'],
                     'original_model_clearance_m':d,'rigid_model_clearance_m':r,
                     'original_proxy_clearance_m':s['full_body_proxy_clearance_m'],
                     'rigid_proxy_clearance_m':s['rigid_pose_proxy_clearance_m'],
                     'original_closest_body':body,'original_closest_frame_100hz':t,
                     'rigid_closest_body':rbody,'rigid_closest_frame_100hz':rt,
                     'sampled_frames':len(q),'distance_queries':queries+rqueries,
                     'physics_verified':False,'continuous_time_certified':False})
        if (i+1)%12==0:print(f'model geometry checked {i+1}/{len(scenes)}',flush=True)
    write_csv(a.output/'per_scene.csv',rows)
    summary={'scenes':len(rows),'motions':len({r['motion_id'] for r in rows}),
             'original_model_collision_count':sum(r['original_model_clearance_m']<0 for r in rows),
             'original_model_margin_pass_count':sum(r['original_model_clearance_m']>=cfg['clearance_margin_m'] for r in rows),
             'original_min_model_clearance_m':min(r['original_model_clearance_m'] for r in rows),
             'rigid_proxy_overlap_scenes':sum(r['rigid_proxy_clearance_m']<0 for r in rows),
             'rigid_model_overlap_scenes':sum(r['rigid_model_clearance_m']<0 for r in rows),
             'proxy_witnesses_confirmed':sum(r['rigid_proxy_clearance_m']<0 and r['rigid_model_clearance_m']<0 for r in rows),
             'temporal_sampling_hz':100,'physics_verified':False,'continuous_time_certified':False,
             'source_sha256':sha256(__file__),'scene_input_sha256':sha256(a.pilot/'scenes.jsonl'),
             'protocol_sha256':sha256(Path(__file__).parents[2]/'docs/GEOMETRY_VALIDATION_PROTOCOL.md')}
    write_json(a.output/'aggregate.json',summary);print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
