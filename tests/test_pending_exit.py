from types import SimpleNamespace

import numpy as np
import pytest

from hindsight_motion.pending_exit import PendingRequest, prefix_contract, first_difference


def test_request_waits_until_clear_and_is_not_recomputed():
    p = PendingRequest(126, 162)
    assert p.observe(125, requested=1, clear=True) == 0
    assert p.observe(126, requested=1, clear=False) == 0
    for tick in range(127, 134):
        assert p.observe(tick, clear=False) == 0
    assert p.observe(134, clear=True) == 1
    assert p.accepted_tick == 134
    assert p.observe(135, requested=0, clear=False) == 1
    assert len(p.events) == 9


@pytest.mark.parametrize('open_tick,accepted', [(126,126), (162,162), (163,None), (999,None)])
def test_legal_window_boundary(open_tick, accepted):
    p = PendingRequest(126,162)
    for tick in range(126,165):
        p.observe(tick, requested=1 if tick==126 else None, clear=tick>=open_tick)
    assert p.accepted_tick == accepted
    assert p.status == ('accepted' if accepted else 'expired')
    assert p.expired_tick == (None if accepted else 163)


def test_short_and_disabled_requests_never_switch():
    for request, enabled, status in [(0,True,'selected_short'),(1,False,'rejected')]:
        p=PendingRequest(126,162,enabled)
        p.observe(126,requested=request,clear=False)
        assert p.observe(134,clear=True)==0
        assert p.status==status
    p=PendingRequest(126,162)
    p.observe(126,requested=1,clear=False)
    with pytest.raises(ValueError,match='clock'):
        p.observe(128,clear=True)


def candidates():
    a=np.zeros((180,29));b=a.copy();b[172:]=1
    pairs={'duck':tuple(SimpleNamespace(names=('joint',)*29,dt=.02,length=len(q),arrays={
        'joint_position':q, 'joint_velocity':q.copy(), 'support_observation_valid':np.ones((180,2),bool)
    }) for q in (a,b))}
    q=b.copy();q[168:]=1
    v=b.copy();v[167:]=1
    return pairs,{'duck':{'short':(a.copy(),a.copy()),'loop':(q,v)}}


def test_contract_uses_velocity_and_all_support_fields():
    pairs,decoded=candidates()
    c=prefix_contract(pairs,decoded,126)
    assert c['latest_accept_tick']==162
    pairs['duck'][1].arrays['support_observation_valid'][130]=False
    with pytest.raises(ValueError,match='No legal'):
        prefix_contract(pairs,decoded,126)


def test_clock_nonfinite_and_padding_cannot_extend_commitment():
    assert first_difference(np.zeros((5,2)),np.zeros((8,2))) == 5
    pairs,decoded=candidates()
    pairs['duck'][1].dt=.1
    with pytest.raises(ValueError,match='clock'):
        prefix_contract(pairs,decoded,126)
    pairs['duck'][1].dt=.02
    decoded['duck']['loop'][0][150,0]=np.nan
    with pytest.raises(ValueError,match='Nonfinite'):
        prefix_contract(pairs,decoded,126)


def test_donor_metadata_is_part_of_the_committed_prefix():
    pairs, decoded = candidates()
    loop = pairs['duck'][1]
    loop.arrays['base_source_family'] = np.full(180, 'duck')
    assert prefix_contract(pairs, decoded, 126)['latest_accept_tick'] == 162
    loop.arrays['base_source_family'][129] = 'else'
    with pytest.raises(ValueError, match='No legal'):
        prefix_contract(pairs, decoded, 126)
