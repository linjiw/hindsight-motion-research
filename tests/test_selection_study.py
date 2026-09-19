import numpy as np

from hindsight_motion.selection_study import parent_parity


def test_parent_control_gate_requires_exact_physical_and_reference_replay(tmp_path):
    folders=[tmp_path/'old',tmp_path/'new']
    keys={
        'selection.npz':['reference','proprio','tokens','actions'],
        'pre-action-poses.npz':['root_xyz','root_wxyz','joint_pos','joint_vel','body_xyz','body_wxyz'],
        'trace.npz':['root_xyz','speed','contact_force_w'],
        'dynamics-entry.npz':['mass'],
        'duck-features.npz':['lower'],
    }
    for folder in folders:
        (folder/'task').mkdir(parents=True)
        for file,names in keys.items():
            np.savez(folder/'task'/file,**{n:np.zeros((3,2)) for n in names})
    assert parent_parity(*folders)['matched']
    changed={n:np.zeros((3,2)) for n in keys['selection.npz']}
    changed['reference'][1,0]=1e-8
    np.savez(folders[1]/'task/selection.npz',**changed)
    assert not parent_parity(*folders)['matched']
    changed['reference']=np.zeros((4,2))
    np.savez(folders[1]/'task/selection.npz',**changed)
    assert 'shape changed' in parent_parity(*folders)['reason']
