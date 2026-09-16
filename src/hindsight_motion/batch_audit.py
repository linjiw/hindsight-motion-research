"""Independent audits for separated native scene execution."""
import argparse
import json
from pathlib import Path

import numpy as np

from .critical import dump
from .scene_evidence import score_episode


def entry(episode):
    root=episode['root_state_w'][0].copy();root[:3]-=episode['env_origin'][0]
    return dict(root_state=root,joint_pos=episode['joint_pos'][0],
                joint_vel=episode['joint_vel'][0],proprio=episode['proprio'][0])


def equivalence(output):
    output=Path(output);registration=json.loads((output/'registration.json').read_text())
    baseline=Path(registration['source_baseline']);batch=json.loads((output/'batch.json').read_text())
    limits=registration['acceptance'];rows=[]
    for task in batch['tasks']:
        old=baseline/task['task_id'];old_key=json.loads((old/'manifest.json').read_text())[0]['motion_key']
        a=dict(np.load(old/'metrics'/f'episode-{old_key}.npz'))
        b=dict(np.load(output/'metrics'/f"episode-{task['motion_key']}.npz"))
        first,second=entry(a),entry(b)
        delta={k:float(np.max(abs(first[k]-second[k]))) for k in first}
        oa=json.loads((old/'metrics/scene-outcome.json').read_text())
        ob=json.loads((output/'metrics'/task['task_id']/'scene-outcome.json').read_text())
        rmse=float(np.sqrt(np.mean((a['body_xyz']-b['body_xyz'])**2)))
        # body_xyz is already in each environment's local world frame.
        onset_a=min([e['first_s'] for e in oa['contact_events']],default=None)
        onset_b=min([e['first_s'] for e in ob['contact_events']],default=None)
        onset_delta=abs(onset_a-onset_b) if onset_a is not None and onset_b is not None else None
        checks=dict(entry=max(delta.values())<=limits['common_entry_max_error'],
                    classification=oa['checks']==ob['checks'],
                    successful_trajectory=(not oa['scene_passage_verified'] or rmse<=limits['successful_trajectory_rmse_m']),
                    contact_onset=(onset_a is None and onset_b is None) or
                        (onset_delta is not None and onset_delta<=limits['critical_first_contact_time_difference_s']))
        rows.append(dict(task_id=task['task_id'],entry_error=delta,body_xyz_rmse_m=rmse,
                         contact_onset_difference_s=onset_delta,checks=checks,passed=all(checks.values())))
    isolation=json.loads((output/'metrics/isolation-audit.json').read_text())
    result=dict(passed=all(r['passed'] for r in rows) and
                isolation['maximum_foreign_obstacle_force_n']<=limits['foreign_contact_max_n'],
                episodes=rows,isolation=isolation,acceptance=limits)
    dump(output/'equivalence-audit.json',result);print(json.dumps(result,indent=2))


def analyze(output):
    output=Path(output);batch=json.loads((output/'batch.json').read_text());metrics=output/'metrics'
    outcomes=json.loads((metrics/'scene-outcomes.json').read_text())
    native={r['motion_key']:r for r in json.loads((metrics/'preflight-outcomes.json').read_text())}
    by_id={r['task_id']:r for r in outcomes};tasks=batch['tasks'];audit=[];supported=0
    for task in tasks:
        folder=metrics/task['task_id'];episode=dict(np.load(metrics/f"episode-{task['motion_key']}.npz"))
        forces=np.load(folder/'environment-contacts.npz')['normal_force_w']
        recomputed=score_episode(task,episode,native[task['motion_key']],forces)
        assert recomputed['checks']==by_id[task['task_id']]['checks']
        actor=dict(np.load(folder/'actor-view.npz'));teacher=dict(np.load(folder/'teacher-view.npz'))
        target=dict(np.load(folder/'target-view.npz'))
        assert set(actor)=={'proprio','scene_tokens','scene_mask','goal_local_xyz','goal_tolerance_m','complete_known_map'}
        assert actor['proprio'].shape==(200,930) and teacher['future_reference'].shape==(200,640)
        assert target['teacher_motor_token'].shape==(200,64) and target['teacher_action'].shape==(200,29)
        for view in (actor,teacher,target):
            assert all(np.isfinite(x).all() for x in view.values())
        assert np.all(actor['scene_mask'].sum(1)==len(task['obstacles']))
        expected=episode['before_first_native_failure'] & recomputed['scene_passage_verified']
        np.testing.assert_array_equal(target['motor_imitation_support'],expected)
        supported+=int(expected.sum())
        audit.append(dict(task_id=task['task_id'],entry=entry(episode)))
    panels=[];relations=[]
    for pair in sorted({t['pair_id'] for t in tasks}):
        pair_tasks=[t for t in tasks if t['pair_id']==pair]
        family=pair_tasks[0]['family'];positive,negative=('tuck','wide') if family=='arm_tuck' else ('duck','upright')
        for perturbation in (0,1,2):
            panel_tasks=[t for t in pair_tasks if t['perturbation_id']==perturbation]
            entries=[next(r['entry'] for r in audit if r['task_id']==t['task_id']) for t in panel_tasks]
            differences={k:float(max(np.max(abs(e[k]-entries[0][k])) for e in entries)) for k in entries[0]}
            index={(t['condition'],t['variant']):by_id[t['task_id']] for t in panel_tasks}
            assert len(index)==8
            controls=all(index[c,v]['scene_passage_verified'] for c in ('relaxed','removed','displaced') for v in (positive,negative))
            contrast=index['critical',negative]
            body_parts=('shoulder','elbow','wrist') if family=='arm_tuck' else ('torso','head')
            events=[e for e in contrast['contact_events'] if any(part in e['body'] for part in body_parts)]
            verified=bool(max(differences.values())<=1e-5 and controls and index['critical',positive]['scene_passage_verified']
                          and not contrast['checks']['obstacle_contact_free'] and events)
            panels.append(dict(pair_id=pair,family=family,source_group=pair_tasks[0]['source_group'],
                perturbation_id=perturbation,entry_max_differences=differences,controls_pass=controls,
                positive_critical_pass=index['critical',positive]['scene_passage_verified'],
                negative_mechanism_contact=bool(events),verified=verified))
            if verified:
                relations.extend(dict(pair_id=pair,family=family,perturbation_id=perturbation,
                    supported_behavior=positive,contrast_behavior=negative,target_only=True,
                    evidence='Complete matched critical/relaxed/removed/displaced executed panel',**e) for e in events)
    summary=dict(completed=len(outcomes),scene_passes=sum(r['scene_passage_verified'] for r in outcomes),
        pairs=len({t['pair_id'] for t in tasks}),source_groups=len({t['source_group'] for t in tasks}),
        verified_panels=sum(p['verified'] for p in panels),total_panels=len(panels),
        verified_pairs_all_three_panels=sum(all(p['verified'] for p in panels if p['pair_id']==pair) for pair in {t['pair_id'] for t in tasks}),
        control_rows=sum(r['valid_pre_action_rows'] for r in outcomes),positive_motor_rows=supported,
        data_audit_passed=True,split='development',held_out_generalization=False,student_trained=False)
    dump(output/'paired_relation_audit.json',panels);dump(output/'verified_relation_targets.json',relations)
    dump(output/'aggregate.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['equivalence','analyze']);p.add_argument('output',type=Path)
    a=p.parse_args();globals()[a.command](a.output.resolve())
