from __future__ import annotations

import hashlib
from pathlib import Path

import mujoco
import numpy as np
from scipy.cluster.vq import kmeans2, vq
from scipy.spatial.transform import Rotation


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seeded_id(name, seed):
    return int(hashlib.sha256(f'{seed}:{name}'.encode()).hexdigest()[:8], 16)


def source_split(group, seed):
    x = seeded_id(group, seed) / 2**32
    return 'train' if x < .70 else 'development' if x < .85 else 'test'


def yaw(quat_wxyz):
    w, x, y, z = np.moveaxis(quat_wxyz, -1, 0)
    return np.arctan2(2 * (w*z+x*y), 1-2*(y*y+z*z))


def wrap(angle):
    return np.arctan2(np.sin(angle), np.cos(angle))


def load_clip(path, seconds, patch_frames):
    with np.load(path, allow_pickle=False) as z:
        pos = z['body_pos_w'].astype(np.float64)
        quat = z['body_quat_w'].astype(np.float64)
        joints = z['joint_pos'].astype(np.float64)
        fps = float(z['fps'].reshape(-1)[0])
    n = len(joints)
    if joints.shape != (n, 29) or pos.shape != (n, 30, 3) or quat.shape != (n, 30, 4):
        raise ValueError('G1 29-joint/30-link contract mismatch')
    if not all(np.isfinite(a).all() for a in [pos, quat, joints]):
        raise ValueError('nonfinite input')
    if abs(fps-50) > 1e-6:
        raise ValueError(f'expected verified 50 Hz bank, got {fps}')
    norms = np.linalg.norm(quat, axis=-1)
    if np.max(np.abs(norms-1)) > .01:
        raise ValueError('unnormalized quaternions')
    rot = Rotation.from_quat(quat[:, 0, [1, 2, 3, 0]]).as_matrix()
    local = np.einsum('tji,tbj->tbi', rot, pos-pos[:, :1])
    if not (np.median(local[:, 1, 1]) > .02 and
            np.median(local[:, 2, 1]) > .05 and np.median(local[:, 7, 1]) < -.02):
        raise ValueError('body order is not MuJoCo depth-first')
    length = min(n, int(round(seconds*fps)))
    length -= length % patch_frames
    if length < 2*patch_frames:
        raise ValueError('too short')
    starts = np.unique(np.r_[np.arange(0, n-length+1, int(fps)), n-length])
    delta = pos[starts+length-1, 0, :2] - pos[starts, 0, :2]
    start = int(starts[np.argmax(np.linalg.norm(delta, axis=1))])
    sl = slice(start, start+length)
    qpos = np.concatenate([pos[sl, 0], quat[sl, 0], joints[sl]], axis=1)
    qpos[:, 3:7] /= np.linalg.norm(qpos[:, 3:7], axis=-1, keepdims=True)
    return {'qpos': qpos, 'bank_pos': pos[sl], 'fps': fps,
            'start_frame': start, 'end_frame_exclusive': start+length,
            'original_frames': n, 'source_duration_s': n/fps}


class Robot:
    def __init__(self, xml):
        self.model = mujoco.MjModel.from_xml_path(str(xml))
        self.data = mujoco.MjData(self.model)
        m = self.model
        if m.nq != 36 or m.nbody != 31:
            raise ValueError('expected a 29-DOF G1 with free root and 30 links')
        self.geom_ids = np.flatnonzero((m.geom_bodyid > 0) &
                                      ((m.geom_contype != 0) | (m.geom_conaffinity != 0)))
        self.radii = m.geom_rbound[self.geom_ids].copy()
        self.body_ids = m.geom_bodyid[self.geom_ids]-1
        self.names = [m.body(i).name for i in range(1, m.nbody)]

    def fk(self, qpos):
        centers, links, quats = [], [], []
        for q in qpos:
            self.data.qpos[:] = q
            mujoco.mj_kinematics(self.model, self.data)
            centers.append(self.data.geom_xpos[self.geom_ids].copy())
            links.append(self.data.xpos[1:].copy())
            quats.append(self.data.xquat[1:].copy())
        return np.array(centers), np.array(links), np.array(quats)


def sphere_box_clearances(centers, radii, boxes, chunk=16):
    """Minimum surface clearance per AABB, across all frames and all spheres.

    Box = [cx,cy,cz,hx,hy,hz]. Exact signed point/AABB SDF minus radius;
    nonnegative means the enclosing spheres do not touch the box at sampled times.
    """
    boxes = np.asarray(boxes, dtype=float).reshape(-1, 6)
    out = []
    for start in range(0, len(boxes), chunk):
        b = boxes[start:start+chunk]
        delta = np.abs(centers[:, :, None, :] - b[None, None, :, :3]) - b[None, None, :, 3:]
        sdf = np.linalg.norm(np.maximum(delta, 0), axis=-1)
        sdf += np.minimum(np.max(delta, axis=-1), 0)
        out.extend(np.min(sdf-radii[None, :, None], axis=(0, 1)))
    return np.array(out)


class PatchQuantizer:
    def __init__(self, centers):
        self.centers = [np.asarray(c, dtype=np.float64) for c in centers]

    @classmethod
    def fit(cls, x, size, iterations, seed):
        residue = np.asarray(x, dtype=np.float64).copy()
        centers = []
        for level in range(2):
            c, _ = kmeans2(residue, size, iter=iterations, minit='++',
                           seed=np.random.default_rng(seed+level))
            ids, _ = vq(residue, c)
            residue -= c[ids]
            centers.append(c)
        return cls(centers)

    def encode(self, x):
        residue = np.asarray(x, dtype=np.float64).copy()
        ids = []
        for c in self.centers:
            i, _ = vq(residue, c)
            residue -= c[i]
            ids.append(i)
        return np.stack(ids, axis=1)

    def decode(self, ids, levels):
        return sum(self.centers[l][ids[:, l]] for l in range(levels))


def random_probes(qpos, count, rng):
    t = rng.integers(0, len(qpos), count)
    center = qpos[t, :3].copy()
    center[:, :2] += rng.uniform(-.85, .85, (count, 2))
    center[:, 2] = rng.uniform(.10, 1.55, count)
    size = rng.uniform(.06, .24, (count, 3))
    return np.c_[center, size]


def propose_scenes(qpos, count, rng):
    """Supported 1- or 3-box scenes with no dimensions fitted to body geometry."""
    scenes = []
    for i in range(count):
        t = int(rng.integers(max(1, len(qpos)//5), max(2, 4*len(qpos)//5)))
        c = qpos[t, :2] + rng.uniform(-.70, .70, 2)
        if i % 3 == 0:
            h = float(rng.uniform(.85, 1.48))
            halfwidth = float(rng.uniform(.38, .85))
            boxes = [[c[0], c[1], h+.06, .10, halfwidth+.08, .06],
                     [c[0], c[1]-halfwidth-.04, h/2, .10, .04, h/2],
                     [c[0], c[1]+halfwidth+.04, h/2, .10, .04, h/2]]
            kind = 'portal'
        else:
            h = float(rng.uniform(.08, .26) if i % 3 == 1 else rng.uniform(.45, 1.45))
            boxes = [[c[0], c[1], h/2, float(rng.uniform(.07, .22)),
                      float(rng.uniform(.07, .22)), h/2]]
            kind = 'low_block' if i % 3 == 1 else 'pillar'
        scenes.append({'candidate_id': i, 'kind': kind, 'boxes': boxes})
    return scenes


def evaluate_scenes(centers, radii, scenes):
    sizes = [len(s['boxes']) for s in scenes]
    flat = [b for s in scenes for b in s['boxes']]
    scores = sphere_box_clearances(centers, radii, flat)
    edges = np.r_[0, np.cumsum(sizes)]
    return np.array([scores[a:b].min() for a, b in zip(edges[:-1], edges[1:])])


def extract_events(clip, links, quats, codes):
    q = clip['qpos']; fps = clip['fps']
    heading = np.unwrap(yaw(q[:, 3:7]))
    torso_yaw = yaw(quats[:, 15])
    speed = np.linalg.norm(np.gradient(q[:, :2], 1/fps, axis=0), axis=1)
    high_pelvis = float(np.percentile(q[:, 2], 95))
    # Boundaries respond to changes in coarse labels, with 0.3 s minimum and 1 s maximum.
    turn = np.gradient(heading, 1/fps)
    flags = np.stack([speed > .15, turn > .25, turn < -.25,
                      q[:, 2] < high_pelvis-.10,
                      np.abs(wrap(torso_yaw-heading)) > .25], axis=1)
    boundaries = [0]
    for i in range(1, len(q)):
        since = (i-boundaries[-1])/fps
        if since >= 1.0 or (since >= .3 and np.any(flags[i] != flags[i-1])):
            boundaries.append(i)
    boundaries.append(len(q))
    events = []
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        if b-a < 2:
            continue
        s = slice(a, b)
        displacement = q[b-1, :3]-q[a, :3]
        angle = float(heading[b-1]-heading[a])
        tags = ['translate' if np.linalg.norm(displacement[:2]) > .10 else 'in_place']
        if abs(angle) > .12:
            tags.append('turn_left' if angle > 0 else 'turn_right')
        if np.median(q[s, 2]) < high_pelvis-.10:
            tags.append('pelvis_lowered')
        travel = np.arctan2(displacement[1], displacement[0])
        side = float(wrap(np.mean(heading[s])-travel))
        if np.linalg.norm(displacement[:2]) > .10 and .6 < abs(side) < 2.5:
            tags.append('sideways_body_heading')
        hand_span = np.linalg.norm(links[s, 22]-links[s, 29], axis=1)
        events.append({'start_s': (clip['start_frame']+a)/fps,
                       'end_exclusive_s': (clip['start_frame']+b)/fps,
                       'tags': tags, 'root_delta_m': displacement.tolist(),
                       'pelvis_yaw_change_rad': angle,
                       'torso_relative_yaw_mean_rad': float(np.mean(wrap(torso_yaw[s]-heading[s]))),
                       'body_heading_vs_travel_rad': side,
                       'pelvis_height_min_m': float(q[s, 2].min()),
                       'hand_span_min_max_m': [float(hand_span.min()), float(hand_span.max())],
                       'left_foot_height_range_m': [float(links[s, 6, 2].min()), float(links[s, 6, 2].max())],
                       'right_foot_height_range_m': [float(links[s, 12, 2].min()), float(links[s, 12, 2].max())],
                       'code_patch_range': [a//5, (b+4)//5],
                       'semantics_source': 'deterministic_kinematic_rules',
                       'intent_label': None})
    return events
