import json

import pytest

from hindsight_motion.boundary_admission import validate_parent
from hindsight_motion.core import sha256


def parent_packet(tmp_path):
    cases, rows = [], []
    for name in ('done', 'pending'):
        folder = tmp_path / name
        folder.mkdir()
        cases.append(dict(case_id=name, run_dir=str(folder)))
        rows.append(dict(case_id=name, status='completed' if name == 'done' else 'unrun'))
    (tmp_path / 'done/launch.json').write_text('{}')
    (tmp_path / 'done/exit.json').write_text('{"exit_code":0}')
    plan = dict(cases=cases, bindings=[], registration={'maximum_native_attempts': 2})
    summary = dict(rows=rows, native_attempts=1, unrun=1, execution_state='resource_deferred', provenance=[])
    for name, data in [('plan.json', plan), ('aggregate.json', summary), ('registration.json', plan['registration'])]:
        (tmp_path / name).write_text(json.dumps(data))
    return dict(parent_registration_sha256=sha256(tmp_path / 'registration.json'),
        parent_aggregate_sha256=sha256(tmp_path / 'aggregate.json'), require_parent_execution_state='resource_deferred',
        require_parent_native_attempts=1, case_ids=['pending'], maximum_new_native_attempts=1,
        maximum_native_attempts_across_admissions=2)


def test_reuse_only_never_launched_cases(tmp_path):
    registration = parent_packet(tmp_path)
    _, _, pending = validate_parent(tmp_path, registration)
    assert [c['case_id'] for c in pending] == ['pending']
    (tmp_path / 'pending/launch.json').write_text('{}')
    with pytest.raises(ValueError, match='active, failed or unaccounted'):
        validate_parent(tmp_path, registration)


def test_reject_budget_expansion(tmp_path):
    registration = parent_packet(tmp_path)
    registration['maximum_native_attempts_across_admissions'] = 3
    with pytest.raises(ValueError, match='scientific budget'):
        validate_parent(tmp_path, registration)


def test_reject_changed_parent_evidence(tmp_path):
    registration = parent_packet(tmp_path)
    (tmp_path / 'aggregate.json').write_text('{}')
    with pytest.raises(ValueError, match='Parent receipt changed'):
        validate_parent(tmp_path, registration)
