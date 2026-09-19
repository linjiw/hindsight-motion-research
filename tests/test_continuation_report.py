import json

import pytest

from hindsight_motion import continuation_report


def test_resource_deferral_is_not_a_failed_physical_trial(tmp_path, monkeypatch):
    monkeypatch.setattr(continuation_report, 'PROJECT', tmp_path)
    packet=tmp_path/'packet'; packet.mkdir()
    cases=[]
    for method in ['continuous','linear29']:
        p=packet/method;p.mkdir()
        cases.append(dict(case_id=method,source_clip='synthetic',condition='beam',state='entry',
                          handoff_tick=5,method=method,run_dir=str(p),parent_run=str(p)))
    registration=dict(scope='synthetic report fixture',methods=['continuous','linear29'])
    (packet/'registration.json').write_text(json.dumps(registration))
    (packet/'plan.json').write_text(json.dumps(dict(registration=registration,cases=cases)))
    (packet/'execution-start.json').write_text('{}')
    with pytest.raises(ValueError,match='premature'):
        continuation_report.analyze(packet)
    (packet/'continuous/resource_deferred.json').write_text('{"timeout_s":300}')
    continuation_report.analyze(packet)
    result=json.loads((packet/'aggregate.json').read_text())
    assert result['native_attempts']==result['completed_episodes']==result['infrastructure_failures']==0
    assert result['unrun']==2 and result['execution_state']=='resource_deferred'
    assert result['qualified_pairs']==0 and result['control_steps']==result['physics_samples']==0
    assert all(r['status']=='unrun' and 'resource_gate' in r['reason'] for r in result['rows'])
    with pytest.raises(FileExistsError):
        continuation_report.analyze(packet)
