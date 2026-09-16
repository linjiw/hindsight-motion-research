import numpy as np

from hindsight_motion.clearance_tokens import interpolate_knots,quantize12,reconstruct
from hindsight_motion.core import PatchQuantizer
from hindsight_motion.robust_duck import bend_waist


def test_scalar_code_roundtrip_resolution_and_out_of_range_accounting():
    scale=np.array([1.,2.,3.]);x=np.array([[-1.,-.17,2.9],[1.2,-2.1,0.]])
    symbols,decoded,clipped=quantize12(x,scale)
    assert symbols.dtype==np.int16 and np.max(abs(symbols))<=2047
    assert clipped==2
    valid=abs(x)<=scale
    assert np.all(abs(x-decoded)[valid]<=(np.broadcast_to(scale,x.shape)/4094+1e-12)[valid])


def test_linear_tokens_preserve_affine_motion_between_knots():
    t=np.arange(2,50,5);values=np.c_[.2*t+1,-.3*t+4]
    reconstructed=interpolate_knots(values,50)
    np.testing.assert_allclose(reconstructed[2:48],np.c_[.2*np.arange(2,48)+1,-.3*np.arange(2,48)+4])
    np.testing.assert_array_equal(reconstructed[:2],np.repeat(values[:1],2,axis=0))


def test_body_residual_channels_leave_other_rvq_channels_unchanged():
    q=np.zeros((50,36));q[:,3]=1;q[:,7:]=np.linspace(-.5,.5,29)
    quantizer=PatchQuantizer([np.zeros((1,145)),np.zeros((1,145))])
    indices=np.arange(9)
    model=dict(body_indices=indices,body_scale=np.ones(9),mean=np.zeros(29),basis=np.eye(29)[:,:9],
               pca_scale=np.ones(9),angle_scale=np.ones(29))
    methods,_,_=reconstruct(q,quantizer,model)
    np.testing.assert_array_equal(methods['RVQ_body9'][:,9:],methods['RVQ'][:,9:])
    assert np.max(abs(methods['RVQ_body9'][:,:9]-q[:,7:16]))<=1/4094
    np.testing.assert_array_equal(q[:,3],np.ones(50))


def test_waist_edit_preserves_root_legs_and_shared_entry_exit():
    names=[f'joint_{i}' for i in range(29)];names[14]='waist_pitch_joint'
    q=np.random.default_rng(4).normal(scale=.1,size=(200,36));q[:,3:7]=[1,0,0,0]
    edited,weight=bend_waist(q,names,.5)
    np.testing.assert_array_equal(edited[:,:21],q[:,:21])
    np.testing.assert_array_equal(edited[:,22:],q[:,22:])
    np.testing.assert_array_equal(edited[weight==0],q[weight==0])
    np.testing.assert_allclose(edited[weight==1,21],.5)
