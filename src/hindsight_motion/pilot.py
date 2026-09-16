"""Run the reproducible offline pilot; refuses to overwrite an existing run."""
from __future__ import annotations

import argparse
import collections
import csv
import json
import platform
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import scipy

from .core import (PatchQuantizer, Robot, evaluate_scenes, extract_events,
                   load_clip, propose_scenes, random_probes, seeded_id,
                   sha256, source_split, sphere_box_clearances)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def grouped_ci(rows, key, seed, draws=1000):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r['source_group']].append(float(r[key]))
    arrays = list(groups.values())
    if not arrays:
        return None
    sums = np.array([sum(a) for a in arrays]); counts = np.array([len(a) for a in arrays])
    idx = np.random.default_rng(seed).integers(0, len(arrays), (draws, len(arrays)))
    boot = sums[idx].sum(1)/counts[idx].sum(1)
    return {'mean_motion_weighted': float(sums.sum()/counts.sum()),
            'source_group_bootstrap_95pct': np.quantile(boot, [.025, .975]).tolist(),
            'motions': int(counts.sum()), 'source_groups': len(arrays)}


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    out = args.output; out.mkdir(parents=True, exist_ok=False)
    (out/'examples').mkdir()
    write_json(out/'config.json', cfg)
    started = time.time()
    provenance = list(csv.DictReader(open(cfg['provenance']), delimiter='\t'))
    robot = Robot(cfg['robot_xml'])
    assets = [Path(cfg['robot_xml'])]
    xml = ET.parse(cfg['robot_xml']).getroot()
    meshdir = xml.find('compiler').get('meshdir', '.')
    for mesh in xml.findall('.//asset/mesh'):
        if mesh.get('file'):
            assets.append(Path(cfg['robot_xml']).parent / meshdir / mesh.get('file'))
    input_receipt = {'config_sha256': sha256(args.config),
                     'source_tsv_sha256': sha256(cfg['provenance']),
                     'robot_assets': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in assets],
                     'python': sys.version, 'platform': platform.platform(),
                     'numpy': np.__version__, 'scipy': scipy.__version__, 'mujoco': mujoco.__version__,
                     'code': {str(p): sha256(p) for p in Path(__file__).parent.glob('*.py')},
                     'protocol_sha256': sha256(Path(__file__).parents[2]/'docs/PILOT_PROTOCOL.md')}
    write_json(out/'input_receipt.json', input_receipt)
    write_json(out/'robot_geometry.json', {'body_names': robot.names,
               'collision_geom_ids': robot.geom_ids.tolist(),
               'collision_geom_body_indices': robot.body_ids.tolist(),
               'bounding_sphere_radii_m': robot.radii.tolist(), 'units': 'meters',
               'geometry': 'enclosing spheres from MuJoCo collision model',
               'continuous_time_certified': False})
    clips, inventory, rejected = [], [], []
    for i, row in enumerate(provenance):
        p = Path(cfg['bank'])/(row['climb_g1_stem']+'.npz')
        group = '/'.join(row['hf_path'].split('/')[1:-1])
        identity = {'motion_id': p.stem, 'source_group': group,
                    'collection': row['hf_path'].split('/')[1],
                    'source_path': str(p), 'retarget_source': row['hf_path'],
                    'historic_split': row['split'], 'split': source_split(group, cfg['seed']),
                    'sha256': sha256(p)}
        try:
            clip = load_clip(p, cfg['window_seconds'], cfg['patch_frames'])
        except (ValueError, KeyError) as e:
            rejected.append(dict(identity, reason=str(e))); continue
        identity.update({k: clip[k] for k in ['fps', 'start_frame', 'end_frame_exclusive',
                                             'original_frames', 'source_duration_s']})
        identity['translation_m'] = float(np.linalg.norm(clip['qpos'][-1, :2]-clip['qpos'][0, :2]))
        identity['retained_frames'] = len(clip['qpos'])
        clip.update(identity); clips.append(clip); inventory.append(identity)
        if (i+1) % 150 == 0:
            print(f'loaded {i+1}/{len(provenance)}', flush=True)
    write_csv(out/'inventory.csv', inventory); write_json(out/'rejected_inputs.json', rejected)
    write_json(out/'data_split.json', {s: sorted({r['source_group'] for r in inventory if r['split']==s})
                                     for s in ['train', 'development', 'test']})
    patch = cfg['patch_frames']
    train = np.concatenate([c['qpos'][:, 7:].reshape(-1, patch*29) for c in clips if c['split']=='train'])
    neutral = np.median(train.reshape(-1, 29), axis=0)
    rng = np.random.default_rng(cfg['seed'])
    if len(train) > cfg['max_training_patches']:
        train = train[rng.choice(len(train), cfg['max_training_patches'], replace=False)]
    print(f'fitting two residual codebooks on {len(train)} training patches', flush=True)
    quantizer = PatchQuantizer.fit(train, cfg['codebook_size'], cfg['kmeans_iterations'], cfg['seed'])
    np.savez(out/'codebook.npz', level0=quantizer.centers[0], level1=quantizer.centers[1],
             neutral_joints=neutral, patch_frames=patch)
    print('codebooks fitted; evaluating geometry and scene candidates', flush=True)
    metrics, scene_metrics, selections, summaries = [], [], [], []
    example_pool = []
    with (out/'tokens.jsonl').open('w') as tokfile, (out/'events.jsonl').open('w') as eventfile:
        for i, c in enumerate(clips):
            q = c['qpos']; x = q[:, 7:].reshape(-1, patch*29)
            codes = quantizer.encode(x)
            variants = {'continuous': q, 'rigid_pose': q.copy(), 'vq': q.copy(), 'rvq': q.copy()}
            variants['rigid_pose'][:, 7:] = neutral
            for method, levels in [('vq', 1), ('rvq', 2)]:
                variants[method][:, 7:] = quantizer.decode(codes, levels).reshape(-1, 29)
            geometry = {method: robot.fk(v) for method, v in variants.items()}
            centers, links, quats = geometry['continuous']
            discrepancy = float(np.max(np.linalg.norm(links-c['bank_pos'], axis=-1)))
            idrow = {k: c[k] for k in ['motion_id', 'source_group', 'collection', 'split']}
            probes = random_probes(q, cfg['probe_boxes_per_motion'],
                                   np.random.default_rng(seeded_id(c['motion_id']+':probe', cfg['seed'])))
            clearances = {method: sphere_box_clearances(g[0], robot.radii, probes)
                          for method, g in geometry.items()}
            truth = clearances['continuous']
            for method in variants:
                pred = clearances[method]; original_bad = truth < 0; predicted_bad = pred < 0
                error = np.linalg.norm(geometry[method][1]-links, axis=-1)
                metrics.append(dict(idrow, method=method,
                    link_origin_mpjpe_m=float(error.mean()), link_origin_error_p95_m=float(np.quantile(error, .95)),
                    clearance_mae_m=float(np.abs(pred-truth).mean()),
                    collision_disagreement=float(np.mean(original_bad != predicted_bad)),
                    false_safe_count=int(np.sum(original_bad & ~predicted_bad)),
                    true_collision_count=int(original_bad.sum()), probe_count=len(probes),
                    false_blocked_count=int(np.sum(~original_bad & predicted_bad)),
                    bank_fk_max_error_m=discrepancy))
            events = extract_events(c, links, quats, codes)
            tokfile.write(json.dumps(dict(idrow, codes=codes.tolist(), patch_frames=patch, fps=c['fps'],
                start_frame=c['start_frame'], source_path=c['source_path'], sha256=c['sha256'],
                continuous_sidecar=['root_position_xyz', 'root_quaternion_wxyz'],
                terminal_speed_mps=float(np.linalg.norm(q[-1, :2]-q[-2, :2])*c['fps']),
                clip_end_is_stop=False))+'\n')
            for ev in events:
                eventfile.write(json.dumps(dict(idrow, **ev))+'\n')
            summary = dict(idrow, translation_m=c['translation_m'], bank_fk_max_error_m=discrepancy,
                           events=len(events), geometry_scene_eligible=c['translation_m'] >= cfg['minimum_translation_m'])
            if summary['geometry_scene_eligible']:
                scenes = propose_scenes(q, cfg['scene_candidates_per_motion'],
                       np.random.default_rng(seeded_id(c['motion_id']+':scene', cfg['seed'])))
                scores = {name: evaluate_scenes(geometry[name][0], robot.radii, scenes)
                          for name in ['continuous', 'rigid_pose']}
                margin = cfg['clearance_margin_m']; k = cfg['max_scenes_per_motion']
                valid = np.flatnonzero(scores['continuous'] >= margin)
                witness = valid[scores['rigid_pose'][valid] < 0]
                order = sorted(valid, key=lambda n: (scores['rigid_pose'][n] >= 0, scores['continuous'][n]))
                picks = {'random_filtered': valid[:k], 'full_body_ranked': order[:k],
                         'rigid_pose_filtered': np.flatnonzero(scores['rigid_pose'] >= margin)[:k]}
                for method, chosen in picks.items():
                    chosen = np.asarray(chosen, dtype=int)
                    row = dict(idrow, method=method, candidates=len(scenes), retained=len(chosen),
                       full_body_margin_pass=int(np.sum(scores['continuous'][chosen] >= margin)),
                       full_body_collision_count=int(np.sum(scores['continuous'][chosen] < 0)),
                       rigid_pose_overlap_count=int(np.sum(scores['rigid_pose'][chosen] < 0)),
                       all_full_body_valid_candidates=len(valid), all_rigid_overlap_candidates=len(witness))
                    scene_metrics.append(row)
                for idx in picks['full_body_ranked']:
                    scene = dict(idrow, **scenes[idx], source_path=c['source_path'],
                        source_sha256=c['sha256'], start_frame=c['start_frame'], end_frame_exclusive=c['end_frame_exclusive'],
                        full_body_proxy_clearance_m=float(scores['continuous'][idx]),
                        rigid_pose_proxy_clearance_m=float(scores['rigid_pose'][idx]),
                        status='geometry_candidate', physics_verified=False,
                        functional_counterfactual_verified=False, continuous_time_certified=False)
                    selections.append(scene)
                summary.update(valid_candidates=len(valid), rigid_overlap_candidates=len(witness))
                if len(picks['full_body_ranked']):
                    best = int(picks['full_body_ranked'][0])
                    # At most twelve visual examples; prefer test-source witnesses.
                    priority = (c['split']=='test', len(witness)>0, -float(scores['continuous'][best]))
                    example_pool.append((priority, c['motion_id'], scenes[best], links.astype(np.float32),
                                         geometry['rigid_pose'][1].astype(np.float32),
                                         geometry['vq'][1].astype(np.float32), events, idrow,
                                         float(scores['continuous'][best]), float(scores['rigid_pose'][best])))
                    example_pool.sort(key=lambda item: item[0], reverse=True)
                    example_pool = example_pool[:12]
            summaries.append(summary)
            if (i+1)%50 == 0:
                print(f'evaluated {i+1}/{len(clips)}; scenes retained {len(selections)}; elapsed {time.time()-started:.1f}s', flush=True)
    write_csv(out/'representation_metrics.csv', metrics)
    write_csv(out/'scene_metrics.csv', scene_metrics)
    write_json(out/'motion_summaries.json', summaries)
    with (out/'scenes.jsonl').open('w') as f:
        for scene in selections: f.write(json.dumps(scene)+'\n')
    examples = []
    for _, name, scene, links, rigid, vqpos, events, ids, clear, rigid_clear in example_pool:
        np.savez_compressed(out/'examples'/(name+'.npz'), links=links, rigid_links=rigid,
                            vq_links=vqpos, boxes=scene['boxes'], fps=50)
        examples.append(dict(ids, file=name+'.npz', events=events, scene=scene,
                             full_body_proxy_clearance_m=clear, rigid_pose_proxy_clearance_m=rigid_clear))
    write_json(out/'examples'/'index.json', examples)
    test = [r for r in metrics if r['split']=='test']
    representation_summary = {}
    for method in variants:
        subset = [r for r in test if r['method']==method]
        representation_summary[method] = {key: grouped_ci(subset, key, cfg['seed']) for key in
             ['link_origin_mpjpe_m', 'clearance_mae_m', 'collision_disagreement']}
        representation_summary[method]['false_safe_count'] = sum(r['false_safe_count'] for r in subset)
        representation_summary[method]['true_collision_count'] = sum(r['true_collision_count'] for r in subset)
        representation_summary[method]['probe_count'] = sum(r['probe_count'] for r in subset)
    scene_summary = {}
    for split in ['train', 'development', 'test', 'all']:
        scene_summary[split] = {}
        for method in ['random_filtered', 'full_body_ranked', 'rigid_pose_filtered']:
            rows = [r for r in scene_metrics if r['method']==method and (split=='all' or r['split']==split)]
            scene_summary[split][method] = {'eligible_motions': len(rows),
                  **{key: sum(r[key] for r in rows) for key in ['candidates', 'retained', 'full_body_margin_pass',
                       'full_body_collision_count', 'rigid_pose_overlap_count']},
                  'motions_with_scene': sum(r['retained']>0 for r in rows)}
    aggregate = {'status': 'completed_offline_exploratory_pilot', 'input_count': len(provenance),
        'valid_motion_count': len(clips), 'invalid_motion_count': len(rejected),
        'split_motion_counts': dict(collections.Counter(c['split'] for c in clips)),
        'split_group_counts': {s: len({c['source_group'] for c in clips if c['split']==s}) for s in ['train','development','test']},
        'collection_counts': dict(collections.Counter(c['collection'] for c in clips)),
        'source_total_hours': sum(c['source_duration_s'] for c in clips)/3600,
        'retained_window_hours': sum(len(c['qpos'])/c['fps'] for c in clips)/3600,
        'training_patches': len(train), 'events': sum(r['events'] for r in summaries),
        'model_bank_fk_max_discrepancy_m': max(r['bank_fk_max_error_m'] for r in summaries),
        'test_representation': representation_summary, 'scene_generation': scene_summary,
        'exported_scene_count': len(selections), 'elapsed_seconds': time.time()-started,
        'limitations': ['sphere proxies, not exact mesh clearance', '50 Hz samples, not continuous collision checking',
                        'rigid-pose comparator is not an executable counterfactual',
                        'no dynamics rollouts or navigation training in this pilot',
                        'previously used source corpus; grouped split is exploratory',
                        'continuous root side channel is shared and uncompressed']}
    write_json(out/'aggregate.json', aggregate)
    print(json.dumps(aggregate, indent=2), flush=True)


if __name__ == '__main__':
    main()
