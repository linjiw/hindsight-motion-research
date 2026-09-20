"""Publish the closed admission's memory receipts without implying native execution."""
import json
from pathlib import Path
import shutil

from hindsight_motion.complete_task import binding
from hindsight_motion.critical import PROJECT, dump


def main():
    packet=PROJECT/'runs/pending_exit_20260920_admission02'
    case=packet/'episodes/farther-beam_linear29'
    aggregate=json.loads((packet/'aggregate.json').read_text())
    if aggregate['new_native_attempts'] != 0 or aggregate['execution_state'] != 'resource_deferred':
        raise ValueError('Expected a closed zero-launch resource admission')
    if (case/'launch.json').exists() or (case/'exit.json').exists():
        raise ValueError('Unexpected native attempt')
    samples=[json.loads(s) for s in (case/'resource_wait.jsonl').read_text().splitlines()]
    public=PROJECT/'results/pending_exit_admission02_queue.json'
    if public.exists():raise FileExistsError('Preserve completed resource evidence')
    files=[Path(__file__),packet/'aggregate.json',packet/'plan.json',packet/'queue.log',
           case/'resource_wait.jsonl',case/'resource_deferred.json']
    result=dict(schema='hindsight_pending_exit_admission02_resources_v1',date='2026-09-20',
        scope='Closed resource admission, no new physical execution',new_native_attempts=0,
        new_control_steps=0,new_physics_samples=0,training_steps=0,retries=0,
        resource_wait_limit_s=300,gpu_threshold_mib=12000,host_threshold_mib=16384,required_consecutive_samples=2,
        sample_count=len(samples),ready_samples=sum(s['ready'] for s in samples),
        maximum_consecutive_ready=max(s['consecutive_ready_samples'] for s in samples),
        recorded_sample_span_s=samples[-1]['unix_s']-samples[0]['unix_s'],
        gpu_free_min_mib=min(s['free_gpu_mib'] for s in samples),gpu_free_max_mib=max(s['free_gpu_mib'] for s in samples),
        host_available_min_mib=min(s['available_host_mib'] for s in samples),host_available_max_mib=max(s['available_host_mib'] for s in samples),
        deferral=json.loads((case/'resource_deferred.json').read_text()),samples=samples,
        distinction='Admission 02 closed normally on its registered resource timeout. Admission 01 retains its separate 143/SIGTERM receipt with unknown sender.',
        provenance=[dict(path=str(p.relative_to(PROJECT)),sha256=binding(p)['sha256']) for p in files])
    shutil.copy2(__file__,packet/'resource-audit-source.py')
    dump(packet/'resource-audit.json',result);dump(public,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','provenance')},indent=2))


if __name__=='__main__':main()
