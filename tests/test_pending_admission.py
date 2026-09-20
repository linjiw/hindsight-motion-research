import json

import pytest

from hindsight_motion.core import sha256
from hindsight_motion.pending_admission import validate


def packet(tmp_path):
    registration = dict(maximum_native_attempts=4, maximum_control_steps_total=2000,
        maximum_physics_steps_total=8000, maximum_control_steps_per_attempt=500,
        maximum_wall_seconds_per_attempt=600, resource_wait_seconds_per_attempt=300, retries=0, training_steps=0)
    cases, rows, contrasts = [], [], []
    for name in ('original-beam_continuous','original-beam_linear29','farther-beam_continuous','farther-beam_linear29'):
        folder = tmp_path/name
        folder.mkdir()
        cases.append(dict(case_id=name,run_dir=str(folder)))
        done = name != 'farther-beam_linear29'
        rows.append(dict(case_id=name,status='completed' if done else 'unrun',success=done))
        if done:
            (folder/'launch.json').write_text('{}')
            (folder/'exit.json').write_text('{"exit_code":0}')
            contrasts.append(dict(case_id=name,unchanged_path_audit=dict(matched=True)))
    plan = dict(registration=registration,cases=cases,bindings=[])
    summary = dict(rows=rows,native_attempts=3,unrun=1,execution_state='stopped',provenance=[],
                   control_steps=1160,physics_samples=4640,incumbent_comparisons=contrasts)
    stop = dict(supervisor_exit_code=143,native_attempts=3)
    for name,data in [('plan.json',plan),('registration.json',registration),('aggregate.json',summary),
                      ('stopped.json',stop),('queue-interruption.json',stop)]:
        (tmp_path/name).write_text(json.dumps(data))
    a = dict(require_parent_native_attempts=3,require_parent_execution_state='stopped',case_ids=['farther-beam_linear29'],
        maximum_new_native_attempts=1,maximum_native_attempts_across_admissions=4,maximum_new_control_steps=500,
        maximum_new_physics_samples=2000,maximum_control_steps_per_attempt=500,maximum_wall_seconds_per_attempt=600,
        resource_wait_seconds_per_attempt=300,retries=0,training_steps=0)
    for name,key in [('plan.json','parent_plan_sha256'),('registration.json','parent_registration_sha256'),
                     ('aggregate.json','parent_aggregate_sha256'),('stopped.json','parent_stopped_sha256'),
                     ('queue-interruption.json','parent_interruption_sha256')]:
        a[key] = sha256(tmp_path/name)
    return a


def test_only_unlaunched_case_and_three_controls(tmp_path):
    admission = packet(tmp_path)
    assert [c['case_id'] for c in validate(tmp_path,admission)[2]] == ['farther-beam_linear29']
    (tmp_path/'farther-beam_linear29/launch.json').write_text('{}')
    with pytest.raises(ValueError,match='active, failed or unaccounted'):
        validate(tmp_path,admission)


@pytest.mark.parametrize('field,value', [('retries',1),('resource_wait_seconds_per_attempt',600),
    ('maximum_control_steps_per_attempt',501),('maximum_new_control_steps',501),
    ('maximum_new_physics_samples',2004),('maximum_native_attempts_across_admissions',5)])
def test_no_budget_expansion(tmp_path,field,value):
    admission = packet(tmp_path)
    admission[field] = value
    with pytest.raises(ValueError):
        validate(tmp_path,admission)


def test_interruption_receipt_cannot_be_rewritten(tmp_path):
    admission = packet(tmp_path)
    (tmp_path/'queue-interruption.json').write_text('{}')
    with pytest.raises(ValueError,match='Closed parent changed'):
        validate(tmp_path,admission)


def test_a_failed_control_is_not_reusable(tmp_path):
    admission = packet(tmp_path)
    path = tmp_path/'aggregate.json'
    summary = json.loads(path.read_text())
    summary['rows'][0]['success'] = False
    path.write_text(json.dumps(summary))
    admission['parent_aggregate_sha256'] = sha256(path)
    with pytest.raises(ValueError,match='successful retained controls'):
        validate(tmp_path,admission)
