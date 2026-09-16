"""Acquire one robustly proposed overhead constraint per qualified source group."""
import argparse
import json
from pathlib import Path
import shutil
import time

from .critical import PROJECT,dump
from .expansion_scenes import search_beam,prepare


def propose(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    first=PROJECT/'runs/robust_duck_preflight_20260915_v1'
    qualification=json.loads((first/'repeat_qualification.json').read_text())
    tasks=json.loads((first/'batch.json').read_text())['tasks'];manifest={r['motion_key']:r for r in json.loads((first/'manifest.json').read_text())}
    proxies=json.loads((PROJECT/'runs/critical_preflight_20260915_v2/native_collision_proxies.json').read_text())
    dump(output/'registration.json',dict(registered_unix_s=time.time(),preflight=str(first),
        eligible_pairs=[r['pair_id'] for r in qualification if r['qualified']],
        geometry_thresholds=dict(positive_clearance_m=.03,negative_inner_overlap_m=.01),
        robust_gate='Every measured empty-scene repetition must satisfy its side of the contrast',
        selection='At most one admitted pair per source group, largest worst-side slack, tie by pair ID',
        maximum_new_pairs=2,maximum_new_main_episodes=48,main_study_previous_episodes=96,main_study_ceiling=480,
        no_physical_beam_outcomes_used=True,split='development'))
    passing=[]
    for r in qualification:
        if not r['qualified']:continue
        pair=r['pair_id'];index={(t['variant'],t['perturbation_id']):t for t in tasks if t['pair_id']==pair}
        paths=[tuple(first/'metrics'/f"episode-{index[v,p]['motion_key']}.npz" for v in ('duck','upright')) for p in range(3)]
        result=search_beam(first,proxies,*paths[0],refine=True,extra_pairs=paths[1:])
        result.update(pair_id=pair,family='duck',source_group=r['source_group'],
                      records={v:manifest[index[v,0]['motion_key']] for v in ('duck','upright')})
        dump(output/f'{pair}.json',result)
        if result['selected'] is not None:passing.append(result)
        print(json.dumps(dict(pair=pair,admitted=sum(p['admitted'] for p in result['proposals']),selected=result['selected'])),flush=True)
    accepted=[]
    for group in sorted({r['source_group'] for r in passing}):
        candidates=sorted([r for r in passing if r['source_group']==group],key=lambda r:(-r['selected']['score'],r['pair_id']))
        accepted.append(candidates[0]['pair_id'])
    dump(output/'accepted_pairs.json',accepted);shutil.copy2(__file__,output/'code_snapshot.py')
    shutil.copy2(PROJECT/'src/hindsight_motion/expansion_scenes.py',output/'geometry_code_snapshot.py')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['propose','prepare']);p.add_argument('paths',nargs='+',type=Path)
    a=p.parse_args();globals()[a.command](*[x.resolve() for x in a.paths])
