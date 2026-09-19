import json

import pytest

from hindsight_motion import selection_boundary as study


def test_reproduced_behavioral_failure_is_not_censored(tmp_path, monkeypatch):
    folder = tmp_path / 'continuous'
    (folder / 'task').mkdir(parents=True)
    (folder / 'task/task-result.json').write_text(json.dumps({'duck_recover_stop_success': False}))
    monkeypatch.setattr(study, 'parent_parity', lambda *args: {'matched': True})
    assert study.qualify({'method': 'continuous', 'run_dir': str(folder), 'parent_run': 'old'})


def test_mismatched_failed_control_still_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'parent_parity', lambda *args: {'matched': False})
    assert not study.qualify({'method': 'continuous', 'run_dir': str(tmp_path), 'parent_run': 'old'})


def test_closed_queue_cannot_be_relaunched(tmp_path):
    (tmp_path / 'plan.json').write_text(json.dumps({'cases': []}))
    (tmp_path / 'execution-start.json').write_text('{}')
    with pytest.raises(FileExistsError):
        study.run(tmp_path)
