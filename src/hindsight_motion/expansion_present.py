"""Consolidate real episodes, retain failures, and render the expanded study."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .core import sha256
from .critical import PROJECT,RUNTIME,dump
from .critical_present import HTML,box_vertices


def collect(extra_runs=()):
    rows=[];panels=[]
    old=PROJECT/'runs/critical_interventions_20260915_v1'
    for r in json.loads((old/'tasks.json').read_text()):
        run=Path(r['run_dir']);task=json.loads((run/'task.json').read_text());folder=run/'metrics'
        key=json.loads((run/'manifest.json').read_text())[0]['motion_key']
        rows.append(dict(task=task,task_path=run/'task.json',folder=folder,episode_path=folder/f'episode-{key}.npz',
                         outcome=json.loads((folder/'scene-outcome.json').read_text())))
    panels.extend(dict(pair_id='arm03',family='arm_tuck',source_group='KIT/205',**p)
                  for p in json.loads((old/'paired_relation_audit.json').read_text()))
    for name in ('expansion_interventions_20260915_v1','expansion_duck_interventions_20260915_v1')+tuple(extra_runs):
        run=PROJECT/'runs'/name
        for task in json.loads((run/'batch.json').read_text())['tasks']:
            folder=run/'metrics'/task['task_id']
            rows.append(dict(task=task,task_path=run/'tasks'/f"{task['task_id']}.json",folder=folder,episode_path=run/'metrics'/f"episode-{task['motion_key']}.npz",
                             outcome=json.loads((folder/'scene-outcome.json').read_text())))
        panels.extend(json.loads((run/'paired_relation_audit.json').read_text()))
    return rows,panels


def threshold_sensitivity(rows,panels,output):
    """Post-hoc diagnostic only; never edits the registered outcome/support labels."""
    results=[]
    for threshold in (.10,.105,.11,.12):
        for pair in sorted({r['task']['pair_id'] for r in rows}):
            group=[r for r in rows if r['task']['pair_id']==pair]
            positive,negative=('duck','upright') if group[0]['task']['family']=='duck' else ('tuck','wide')
            verified=[]
            for perturbation in range(3):
                panel=next(p for p in panels if p['pair_id']==pair and p['perturbation_id']==perturbation)
                entry_equal=max(panel['entry_max_differences'].values())<=1e-5
                index={(r['task']['condition'],r['task']['variant']):r['outcome'] for r in group if r['task']['perturbation_id']==perturbation}
                def success(r):
                    return not r['terminated'] and r['mean_body_error_m']<=threshold and r['max_root_xy_error_m']<=.25 and all(v for k,v in r['checks'].items() if k!='tracking')
                parts=('torso','head') if positive=='duck' else ('shoulder','elbow','wrist')
                contact=any(any(p in e['body'] for p in parts) for e in index['critical',negative]['contact_events'])
                passed=entry_equal and all(success(index[c,v]) for c in ('relaxed','removed','displaced') for v in (positive,negative)) and success(index['critical',positive]) and contact
                if threshold==.10:assert passed==panel['verified']
                verified.append(passed)
            results.append(dict(body_tracking_threshold_m=threshold,pair_id=pair,verified_panels=sum(verified)))
    dump(output/'posthoc_threshold_sensitivity.json',dict(primary_threshold_m=.10,exploratory_only=True,
         changes_primary_labels=False,other_thresholds_unchanged=True,results=results))


def present(extra_runs=(),version=2,prefix='expansion',preflight_attempts=98,new_preflight_attempts=50,previous_main=24):
    rows,panels=collect(extra_runs);output=PROJECT/f'runs/critical_dataset_20260915_v{version}';output.mkdir(exist_ok=True)
    threshold_sensitivity(rows,panels,output)
    index=[]
    for r in rows:
        task=r['task'];outcome=r['outcome'];folder=r['folder']
        paths={name:folder/f'{name}-view.npz' for name in ('actor','teacher','target')}
        paths.update(raw_episode=r['episode_path'],contact=folder/'environment-contacts.npz',
                     task=r['task_path'],outcome=folder/'scene-outcome.json')
        support=np.load(paths['target'])['motor_imitation_support']
        qualified=next(p['verified'] for p in panels if p['pair_id']==task['pair_id'] and p['perturbation_id']==task['perturbation_id'])
        index.append(dict(episode_id=task['task_id'],pair_id=task['pair_id'],family=task['family'],
            source_group=task['source_group'],condition=task['condition'],variant=task['variant'],
            perturbation_id=task['perturbation_id'],split='development',scene_passage_verified=outcome['scene_passage_verified'],
            panel_relation_verified=qualified,positive_motor_rows=int(support.sum()),
            control_rows=len(support),scene_sha256=task['scene_sha256'],
            files={k:dict(path=str(p),sha256=sha256(p)) for k,p in paths.items()}))
    (output/'development_episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in index))
    pairs=list(dict.fromkeys(r['task']['pair_id'] for r in rows));pair_rows=[]
    for pair in pairs:
        part=[r for r in rows if r['task']['pair_id']==pair];family=part[0]['task']['family']
        positive,negative=('tuck','wide') if family=='arm_tuck' else ('duck','upright')
        scores={condition:{v:sum(r['outcome']['scene_passage_verified'] for r in part if r['task']['condition']==condition and r['task']['variant']==v)
                for v in (positive,negative)} for condition in ('critical','relaxed','removed','displaced')}
        pair_rows.append(dict(pair_id=pair,source_group=part[0]['task']['source_group'],family=family,
            positive=positive,negative=negative,outcomes=scores,verified_panels=sum(p['verified'] for p in panels if p['pair_id']==pair)))
    summary=dict(episodes=len(rows),scene_passes=sum(r['scene_passage_verified'] for r in index),
        control_rows=sum(r['control_rows'] for r in index),positive_motor_rows=sum(r['positive_motor_rows'] for r in index),
        motion_pairs=len(pairs),source_groups=len({r['source_group'] for r in index}),
        tested_families=['arm_tuck','duck'],verified_families=sorted({p['family'] for p in panels if p['verified']}),
        verified_panels=sum(p['verified'] for p in panels),total_panels=len(panels),
        pairs_verified_all_three_panels=sum(p['verified_panels']==3 for p in pair_rows),pairs=pair_rows,
        main_study_attempts=len(rows),main_study_ceiling=480,preflight_attempts=preflight_attempts,
        new_preflight_attempts=new_preflight_attempts,new_main_attempts=len(rows)-previous_main,split='development',student_trained=False,
        counting='Eight batch-equivalence episodes count only as preflight; not duplicated in dataset',
        independence='Paired perturbations and scenes descended from one mocap source are correlated')
    dump(output/'aggregate.json',summary);dump(output/'paired_relation_audit.json',panels)
    dump(output/'dataset-contract.json',dict(schema=f'critical_motion_scene_development_v{version}',
        teacher_checkpoint_sha256=json.loads((PROJECT/'runs/critical_preflight_20260915_v2/teacher_and_runtime_contract.json').read_text())['teacher_sha256'],
        actor_fields=['proprio','scene_tokens','scene_mask','goal_local_xyz','goal_tolerance_m','complete_known_map'],
        teacher_fields=['future_reference','privileged_state','reference_body_pos'],
        scene_padding='Variable object count: collators pad to batch maximum with false mask; all present maps are complete',
        motor_space='64D continuous SONIC decoder latent; distinct from reference-motion RVQ indices',
        imitation_support='Only per-episode scene-pass rows before native failure; relation support is a separate panel flag',
        failure_use='Retain for outcome/contact prediction; never positive motor imitation',
        multimodality='Both arm continuations can be valid in controls with the same actor entry; do not average incompatible targets',
        provenance_only=['source_group','pair_id','episode_id','reference_phase','panel_relation_verified'],
        split='All development. No IID frame split or held-out generalization claim',
        future_derived_relation_is_actor_input=False))
    artifacts=PROJECT/'artifacts';plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    fig,axes=plt.subplots(len(pairs),2,figsize=(12,3.25*len(pairs)),gridspec_kw={'width_ratios':[1,1.25]})
    dataset=[]
    for i,pair in enumerate(pair_rows):
        part=[r for r in rows if r['task']['pair_id']==pair['pair_id']]
        colors=['#168b72','#ce6b2e'];conditions=['critical','relaxed','removed','displaced'];x=np.arange(4)
        for j,v in enumerate((pair['positive'],pair['negative'])):
            axes[i,0].bar(x+(j-.5)*.33,[pair['outcomes'][c][v] for c in conditions],width=.32,color=colors[j],label=v)
            for perturbation in range(3):
                r=next(r for r in part if r['task']['condition']=='critical' and r['task']['variant']==v and r['task']['perturbation_id']==perturbation)
                f=np.load(r['folder']/'environment-contacts.npz')['normal_force_w']
                force=np.linalg.norm(f[:,:,1:],axis=-1).max(axis=(1,2))
                axes[i,1].plot((np.arange(len(force))+1)*.005,force,color=colors[j],alpha=.6,label=v if perturbation==0 else None)
        title=f"{pair['source_group']} · {pair['family']} · verified panels {pair['verified_panels']}/3"
        axes[i,0].set(title=title,xticks=x,xticklabels=conditions,ylim=(0,3.6),yticks=[0,1,2,3],ylabel='Passing trials / 3')
        axes[i,1].set(title='Critical scene: all three initial perturbations',xlabel='Time (s)',ylabel='Max obstacle normal force (N)')
        axes[i,0].legend(loc='upper right',ncol=2,fontsize=8);axes[i,1].legend(fontsize=8)
        for condition in conditions:
            for perturbation in range(3):
                matches=[next(r for r in part if r['task']['condition']==condition and r['task']['variant']==v and r['task']['perturbation_id']==perturbation) for v in (pair['positive'],pair['negative'])]
                task=matches[0]['task'];labels=dict(tuck=pair['positive'].capitalize(),wide=pair['negative'].capitalize())
                dataset.append(dict(pair=pair['pair_id'],pair_label=title,labels=labels,condition=condition,perturbation=perturbation,
                    tuck=np.load(matches[0]['episode_path'])['body_xyz'][::2].round(5).tolist(),
                    wide=np.load(matches[1]['episode_path'])['body_xyz'][::2].round(5).tolist(),
                    boxes=[box_vertices(o).round(5).tolist() for o in task['obstacles']],center=task['portal_center_xyz'],
                    outcomes=dict(tuck=matches[0]['outcome'],wide=matches[1]['outcome'])))
    fig.suptitle(f"Critical-scene expansion | {len(rows)} native scene executions, {summary['source_groups']} source groups",fontsize=17)
    fig.text(.07,.012,f'Development evidence. {len(pairs)} edited pairs; two tested mechanisms. Strict qualification thresholds unchanged.\nA collision contrast alone does not verify criticality: controls and the intended traversal must also pass. Perturbations are correlated.',fontsize=10)
    fig.tight_layout(rect=[0,.055,1,.965]);fig.savefig(artifacts/f'{prefix}_interventions.png',dpi=160);fig.savefig(artifacts/f'{prefix}_interventions.pdf');plt.close(fig)
    names=rows[0]['task']['body_names'];xml=ET.parse(RUNTIME/'gear_sonic/data/assets/robot_description/urdf/g1/main.urdf').getroot()
    parent={j.find('child').attrib['link']:j.find('parent').attrib['link'] for j in xml.findall('joint')}
    parents=[]
    for name in names:
        p=parent.get(name)
        while p is not None and p not in names:p=parent.get(p)
        parents.append(names.index(p) if p in names else 0)
    html=HTML.replace('Does the obstacle make the arm motion useful?','Which body adjustments does the scene make useful?')
    html=html.replace('One mocap carrier, two executable arm continuations, four scene interventions.',f"{len(pairs)} edited pairs from {summary['source_groups']} mocap source groups; {len(rows)} executed scene interventions.")
    html=html.replace('Green: tucked arms. Orange: wide arms.','Green: intended traversal. Orange: contrast motion.')
    html=html.replace('<div class="row"><label>Scene','<div class="row"><label>Pair <select id="pair"></select></label><label>Scene')
    html=html.replace("['critical','relaxed','removed','displaced'].forEach", "[...new Map(DATA.map(d=>[d.pair,d.pair_label]))].forEach(([k,v])=>$('pair').add(new Option(v,k)));\n['critical','relaxed','removed','displaced'].forEach")
    html=html.replace("d.condition===$('scene').value&&", "d.pair===$('pair').value&&d.condition===$('scene').value&&")
    html=html.replace("${k==='tuck'?'Tucked':'Wide'} arms", "${current.labels[k]}")
    html=html.replace("$('scene').onchange=select;", "$('pair').onchange=select;$('scene').onchange=select;")
    default_pair=pairs[-1] if extra_runs else 'arm02'
    html=html.replace("function select(){", f"$('pair').value=new URL(location.href).searchParams.get('pair')||'{default_pair}';\nfunction select(){{")
    html=html.replace('__DATA__',json.dumps(dataset)).replace('__PARENTS__',json.dumps(parents))
    (artifacts/f'{prefix}_viewer.html').write_text(html)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':present()
