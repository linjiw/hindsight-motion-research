import json

import pytest

from hindsight_motion.core import sha256
from hindsight_motion.distance_admission import validate


def packet(tmp_path):
    folder = tmp_path / 'pending'
    folder.mkdir()
    registration = dict(maximum_native_attempts=1, maximum_control_steps_total=500,
        maximum_physics_steps_total=2000, maximum_wall_seconds_per_attempt=600,
        resource_wait_seconds_per_attempt=300, retries=0, training_steps=0)
    plan = dict(cases=[dict(case_id='pending', run_dir=str(folder))], bindings=[], registration=registration)
    summary = dict(rows=[dict(case_id='pending', status='unrun')], native_attempts=0,
        unrun=1, execution_state='resource_deferred', provenance=[])
    for name, data in [('plan.json', plan), ('aggregate.json', summary), ('registration.json', registration)]:
        (tmp_path / name).write_text(json.dumps(data))
    return dict(parent_plan_sha256=sha256(tmp_path / 'plan.json'),
        parent_registration_sha256=sha256(tmp_path / 'registration.json'),
        parent_aggregate_sha256=sha256(tmp_path / 'aggregate.json'), require_parent_native_attempts=0,
        require_parent_execution_state='resource_deferred', case_ids=['pending'], maximum_new_native_attempts=1,
        maximum_native_attempts_across_admissions=1, maximum_new_control_steps=500, maximum_new_physics_samples=2000,
        maximum_wall_seconds_per_attempt=600, resource_wait_seconds_per_attempt=300, retries=0, training_steps=0)


def test_zero_launch_parent_cannot_gain_an_attempt(tmp_path):
    admission = packet(tmp_path)
    assert len(validate(tmp_path, admission)[2]) == 1
    (tmp_path / 'pending/launch.json').write_text('{}')
    with pytest.raises(ValueError, match='active, failed or unaccounted'):
        validate(tmp_path, admission)


def test_limits_and_parent_plan_stay_frozen(tmp_path):
    admission = packet(tmp_path)
    admission['resource_wait_seconds_per_attempt'] = 600
    with pytest.raises(ValueError, match='Frozen limit changed'):
        validate(tmp_path, admission)
    admission['resource_wait_seconds_per_attempt'] = 300
    (tmp_path / 'plan.json').write_text('{}')
    with pytest.raises(ValueError, match='Original distance plan changed'):
        validate(tmp_path, admission)
