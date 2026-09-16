import mujoco
import numpy as np

from hindsight_motion.validate import interpolate, minimum_distance


def test_quaternion_interpolation_handles_antipodal_equivalence():
    q = np.zeros((2, 36)); q[0, 3] = 1; q[1, 3] = -1; q[1, 0] = 2
    result = interpolate(q)
    assert result.shape == (3, 36)
    assert np.allclose(result[:, 0], [0, 1, 2])
    assert np.allclose(np.linalg.norm(result[:, 3:7], axis=1), 1)
    assert np.allclose(np.abs(result[:, 3]), 1)


def test_model_distance_sees_mid_trajectory_collision():
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <geom name="obstacle" type="box" size="0.2 0.2 0.2"/>
      <body name="robot"><freejoint/><geom name="body" type="sphere" size="0.1" mass="1"/></body>
    </worldbody></mujoco>''')
    data=mujoco.MjData(model)
    q=np.array([[1,0,0,1,0,0,0], [0,0,0,1,0,0,0], [-1,0,0,1,0,0,0]],dtype=float)
    d,body,t,_=minimum_distance(model,data,q,[model.geom('body').id],[model.geom('obstacle').id])
    assert abs(d + .3) < 1e-6
    assert body=='robot' and t==1


def test_model_distance_positive_clearance():
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <geom name="obstacle" type="box" size="0.2 0.2 0.2"/>
      <body name="robot"><freejoint/><geom name="body" type="sphere" size="0.1" mass="1"/></body>
    </worldbody></mujoco>''')
    data=mujoco.MjData(model)
    q=np.array([[1,0,0,1,0,0,0]],dtype=float)
    d,_,_,_=minimum_distance(model,data,q,[model.geom('body').id],[model.geom('obstacle').id])
    assert abs(d-.7)<1e-6
