"""Contact-consistent candidate edits; execution support must still be measured."""
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


class LegChain:
    def __init__(self, urdf, side):
        xml = ET.parse(urdf).getroot()
        joints = {j.find('child').attrib['link']: j for j in xml.findall('joint')}
        link = f'{side}_ankle_roll_link'
        chain = []
        while link != 'pelvis':
            joint = joints[link]
            chain.append(joint)
            link = joint.find('parent').attrib['link']
        self.names, self.origins, self.rotations, self.axes, self.bounds = [], [], [], [], []
        for joint in reversed(chain):
            if joint.attrib['type'] != 'revolute':
                raise ValueError('Expected six actuated leg joints')
            origin = joint.find('origin')
            self.names.append(joint.attrib['name'])
            self.origins.append(np.fromstring(origin.attrib.get('xyz', '0 0 0'), sep=' '))
            self.rotations.append(Rotation.from_euler('xyz', np.fromstring(
                origin.attrib.get('rpy', '0 0 0'), sep=' ')).as_matrix())
            self.axes.append(np.fromstring(joint.find('axis').attrib['xyz'], sep=' '))
            limit = joint.find('limit')
            self.bounds.append([float(limit.attrib['lower']), float(limit.attrib['upper'])])
        self.bounds = np.asarray(self.bounds).T

    def fk(self, angles):
        position, rotation = np.zeros(3), np.eye(3)
        for origin, orientation, axis, angle in zip(self.origins, self.rotations, self.axes, angles):
            position += rotation @ origin
            rotation = rotation @ orientation @ Rotation.from_rotvec(axis * angle).as_matrix()
        return position, rotation

    def solve(self, desired_position, desired_rotation, initial):
        def residual(angles):
            position, rotation = self.fk(angles)
            error = Rotation.from_matrix(desired_rotation.T @ rotation).as_rotvec()
            return np.r_[10*(position-desired_position), error]
        result = least_squares(residual, np.clip(initial, *self.bounds), bounds=self.bounds,
                               max_nfev=50, ftol=1e-10, xtol=1e-10, gtol=1e-10)
        p, r = self.fk(result.x)
        return result.x, np.linalg.norm(p-desired_position), np.linalg.norm(
            Rotation.from_matrix(desired_rotation.T @ r).as_rotvec())


def duck_preserving_feet(qpos, joint_names, urdf, depth=.14, fps=50):
    q = np.asarray(qpos, dtype=float).copy()
    t = np.arange(len(q))/fps
    u = np.clip(np.minimum(t-.6, t[-1]-.6-t)/.6, 0, 1)
    weight = u**3*(10-15*u+6*u*u)
    q[:, 2] -= depth*weight
    root_rotation = Rotation.from_quat(q[:, [4,5,6,3]]).as_matrix()
    metrics = []
    for side in ['left','right']:
        chain = LegChain(urdf,side)
        indices = np.asarray([7+list(joint_names).index(n) for n in chain.names])
        previous = q[0,indices].copy()
        for i, amount in enumerate(depth*weight):
            if amount == 0:
                previous=q[i,indices].copy()
                continue
            position, orientation=chain.fk(qpos[i,indices])
            position += root_rotation[i].T @ np.array([0,0,amount])
            seed=qpos[i,indices] + previous-qpos[max(0,i-1),indices]
            angles, distance, angle=chain.solve(position,orientation,seed)
            q[i,indices]=angles;previous=angles
            metrics.append([distance,angle])
    errors=np.asarray(metrics)
    audit=dict(max_foot_position_error_m=float(errors[:,0].max(initial=0)),
               max_foot_orientation_error_rad=float(errors[:,1].max(initial=0)),
               root_lowering_m=depth,root_xy_preserved=bool(np.array_equal(q[:,:2],qpos[:,:2])),
               common_entry_exit_preserved=bool(np.array_equal(q[weight==0],qpos[weight==0])),
               physics_verified=False)
    if audit['max_foot_position_error_m']>.002 or audit['max_foot_orientation_error_rad']>.02:
        raise ValueError(f'Foot preservation failed: {audit}')
    return q,weight,audit
