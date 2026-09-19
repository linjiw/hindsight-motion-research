"""Publish scalar resource admission and separately attributed sibling evidence."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
packet = root / 'runs/distance_codec_20260919_v1'
sync_path = packet / 'sibling-sync.json'
sync = json.loads(sync_path.read_text())
analysis_path = Path(sync['source_records'][1]['path'])
analysis = json.loads(analysis_path.read_text())
for record in sync['source_records']:
    if hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('Sibling source changed after read')
ledger = packet / 'episodes/original-beam_continuous/resource_wait.jsonl'
samples = [json.loads(line) for line in ledger.read_text().splitlines()]
deferred = json.loads(ledger.with_name('resource_deferred.json').read_text())
native = json.loads((root / 'results/distance_codec.json').read_text())
assert native['execution_state'] == 'resource_deferred' and native['native_attempts'] == 0
rows = [{k: row[k] for k in ('case', 'context', 'role', 'arm', 'scene', 'goal_offset_mm', 'reused',
    'success', 'steps', 'reason', 'final_goal_distance_m', 'final_forward_error_m', 'goal_radius_margin_m',
    'deadline_censored', 'family')} for row in analysis['rows']]
result = dict(schema='hindsight_distance_followup_v1', date='2026-09-19',
    native_admission=dict(native_attempts=0, unrun=4, wait_limit_seconds=deferred['timeout_s'],
        required_gpu_mib=12000, required_host_mib=16384, required_consecutive_ready_samples=2,
        sample_interval_seconds=20, samples=[dict(elapsed_seconds=r['unix_s'] - samples[0]['unix_s'],
            free_gpu_mib=r['free_gpu_mib'], available_host_mib=r['available_host_mib'], ready=r['ready'],
            consecutive_ready_samples=r['consecutive_ready_samples']) for r in samples]),
    sibling_envelope=dict(local_commit=sync['sibling_head'], scope='Separate sibling continuous-controller experiment; not our codec results',
        summary=analysis['summary'], costs=analysis['costs'], rows=rows, pairs=analysis['pairs'],
        endpoint_calibration_status='Post-result offline hypothesis only; no calibrated-controller execution claimed'),
    provenance=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in (Path(__file__), sync_path, ledger, ledger.with_name('resource_deferred.json'), root / 'results/distance_codec.json')],
    sibling_sources=sync['source_records'])
target = root / 'results/distance_followup.json'
with target.open('x') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(json.dumps(dict(resource_samples=len(samples), simultaneously_ready_samples=sum(r['ready'] for r in samples),
    sibling_summary=analysis['summary'])))
