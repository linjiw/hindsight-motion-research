"""Small supervised proposal-ranking modules with a common geometric verifier."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from scipy.spatial.transform import Rotation
from torch import nn

from .core import (Robot, evaluate_scenes, load_clip, propose_scenes,
                   seeded_id, sha256, wrap, yaw)
from .pilot import grouped_ci, write_csv, write_json


def features(clip, links, quats, codes, scenes, size):
    q = clip['qpos']; anchor = np.r_[q[0, :2], 0.]
    steps = np.linspace(0, len(q)-1, 8).astype(int)
    rotations = Rotation.from_quat(q[steps, 3:7][:, [1, 2, 3, 0]]).as_matrix()[:, :, :2]
    root = np.r_[(q[steps, :3]-anchor).ravel(), rotations.ravel(),
                 np.linalg.norm(np.diff(q[:, :2], axis=0), axis=1).sum(),
                 np.linalg.norm(q[-1, :2]-q[0, :2]), len(q)/clip['fps']]
    raw_event = np.c_[wrap(yaw(quats[:, 15])-yaw(q[:, 3:7])),
                      links[:, 6, 2], links[:, 12, 2],
                      np.linalg.norm(links[:, 22]-links[:, 29], axis=1), q[:, 2]]
    event = np.concatenate([np.r_[p.mean(0), p.std(0)] for p in np.array_split(raw_event, 4)])
    token = np.concatenate([np.concatenate([np.bincount(p[:, j], minlength=size)/len(p)
                             for j in range(2)]) for p in np.array_split(codes, 4)])
    rows = []
    for s in scenes:
        box = np.zeros((3, 6)); present = np.zeros(3)
        for i, b in enumerate(s['boxes']):
            box[i] = b; box[i, :3] -= anchor; present[i] = 1
        candidate = np.r_[box.ravel(), present]
        rows.append(np.r_[root, candidate, event, token])
    shared_end = len(root)+21
    return np.array(rows, dtype=np.float32), shared_end, shared_end+len(event)


def metric_rows(pred, y, meta, method, seed):
    rows = []
    for i, m in enumerate(meta):
        order = np.argsort(-pred[i], kind='stable')[:10]
        rows.append(dict(m, method=method, seed=seed,
                    precision_at_10=float(y[i, order].mean()),
                    found_valid_at_10=float(y[i, order].any()),
                    candidate_prevalence=float(y[i].mean()),
                    brier=float(np.mean((pred[i]-y[i])**2))))
    return rows


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--pilot', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    out = args.output; out.mkdir(parents=True, exist_ok=False)
    (out/'models').mkdir()
    cfg = json.loads((args.pilot/'config.json').read_text())
    inventory = list(csv.DictReader((args.pilot/'inventory.csv').open()))
    tokens = {r['motion_id']: r for r in map(json.loads, (args.pilot/'tokens.jsonl').read_text().splitlines())}
    robot = Robot(cfg['robot_xml'])
    xs, ys, meta = [], [], []
    for row in inventory:
        if float(row['translation_m']) < cfg['minimum_translation_m']:
            continue
        clip = load_clip(row['source_path'], cfg['window_seconds'], cfg['patch_frames'])
        centers, links, quats = robot.fk(clip['qpos'])
        scenes = propose_scenes(clip['qpos'], cfg['scene_candidates_per_motion'],
             np.random.default_rng(seeded_id(row['motion_id']+':scene', cfg['seed'])))
        x, shared_end, event_end = features(clip, links, quats, np.array(tokens[row['motion_id']]['codes']),
                                           scenes, cfg['codebook_size'])
        label = evaluate_scenes(centers, robot.radii, scenes) >= cfg['clearance_margin_m']
        xs.append(x); ys.append(label)
        meta.append({k: row[k] for k in ['motion_id', 'source_group', 'split']})
        if len(meta)%100 == 0: print(f'prepared {len(meta)} proposal groups', flush=True)
    x = np.array(xs); y = np.array(ys, dtype=np.float32)
    splits = np.array([m['split'] for m in meta])
    np.savez_compressed(out/'proposal_training_data.npz', x=x, y=y, splits=splits)
    write_json(out/'motion_groups.json', meta)
    write_json(out/'receipt.json', {'pilot_receipt_sha256': sha256(args.pilot/'input_receipt.json'),
       'inventory_sha256': sha256(args.pilot/'inventory.csv'),
       'codebook_sha256': sha256(args.pilot/'codebook.npz'), 'source_sha256': sha256(__file__),
       'protocol_sha256': sha256(Path(__file__).parents[2]/'docs/PROPOSER_PROTOCOL.md'),
       'model': 'MLP(width,64,64,1), ReLU', 'updates': 400, 'batch_size': 256,
       'seeds': [0, 1], 'learning_rate': .001, 'device': 'cpu',
       'feature_width': int(x.shape[-1]), 'shared_end': shared_end, 'event_end': event_end,
       'motion_counts': {s: int(sum(splits==s)) for s in ['train', 'development', 'test']},
       'label': 'full-body enclosing-sphere clearance >=30mm', 'torch': torch.__version__})
    torch.set_num_threads(2)
    train = x[splits=='train'].reshape(-1, x.shape[-1]); target = y[splits=='train'].reshape(-1)
    mean = train.mean(0); std = np.maximum(train.std(0), .05)
    np.savez(out/'normalization.npz', mean=mean, std=std)
    all_normalized = (x-mean)/std
    test_meta = [m for m in meta if m['split']=='test']; test_y = y[splits=='test']
    results, curves, allpred = [], [], {}
    for method in ['root', 'root_events', 'root_tokens']:
        data = all_normalized.copy()
        if method=='root': data[:, :, shared_end:] = 0
        elif method=='root_events': data[:, :, event_end:] = 0
        else: data[:, :, shared_end:event_end] = 0
        tx = torch.from_numpy(data[splits=='train'].reshape(-1, x.shape[-1]))
        ty = torch.from_numpy(target)
        ex = torch.from_numpy(data[splits=='test'].reshape(-1, x.shape[-1]))
        for seed in [0, 1]:
            torch.manual_seed(seed)
            model = nn.Sequential(nn.Linear(x.shape[-1],64), nn.ReLU(), nn.Linear(64,64), nn.ReLU(), nn.Linear(64,1))
            optimizer = torch.optim.Adam(model.parameters(), lr=.001)
            for update in range(400):
                ids = torch.randint(len(tx), (256,))
                logits = model(tx[ids]).squeeze(-1)
                loss = nn.functional.binary_cross_entropy_with_logits(logits, ty[ids])
                optimizer.zero_grad(); loss.backward(); optimizer.step()
                if update%25==0:
                    curves.append({'method':method,'seed':seed,'update':update,'batch_bce':float(loss.detach())})
            model.eval()
            with torch.no_grad():
                pred = model(ex).sigmoid().numpy().reshape(test_y.shape)
            torch.save(model.state_dict(), out/'models'/f'{method}_seed{seed}.pt')
            allpred[f'{method}_seed{seed}'] = pred
            results.extend(metric_rows(pred, test_y, test_meta, method, seed))
            print(f'fitted {method} seed {seed}: test top10 validity {np.mean([r["precision_at_10"] for r in results if r["method"]==method and r["seed"]==seed]):.3f}', flush=True)
    # Stable original candidate order is the seeded random sampler's order.
    random_order = np.broadcast_to(np.linspace(1,0,test_y.shape[1]), test_y.shape)
    results.extend(metric_rows(random_order, test_y, test_meta, 'random_order', -1))
    results.extend(metric_rows(test_y, test_y, test_meta, 'label_oracle', -1))
    # Brier scores of rank-only/oracle comparators have no calibrated prediction interpretation.
    for r in results:
        if r['method'] in ['random_order','label_oracle']: r['brier'] = None
    write_csv(out/'per_motion_metrics.csv', results); write_csv(out/'training_curve.csv', curves)
    np.savez_compressed(out/'test_predictions.npz', y=test_y, **allpred)
    summary = {}
    for method in ['root','root_events','root_tokens','random_order','label_oracle']:
        summary[method] = {}
        for seed in ([0,1] if method in ['root','root_events','root_tokens'] else [-1]):
            rr = [r for r in results if r['method']==method and r['seed']==seed]
            summary[method][str(seed)] = {k: grouped_ci(rr,k,cfg['seed']) for k in ['precision_at_10','found_valid_at_10']}
            if seed>=0: summary[method][str(seed)]['brier'] = float(np.mean([r['brier'] for r in rr]))
    paired = {}
    for method in ['root_events','root_tokens']:
        for seed in [0,1]:
            a = [r for r in results if r['method']==method and r['seed']==seed]
            b = {r['motion_id']:r for r in results if r['method']=='root' and r['seed']==seed}
            diff = [dict(r, improvement=r['precision_at_10']-b[r['motion_id']]['precision_at_10']) for r in a]
            paired[f'{method}_minus_root_seed{seed}'] = grouped_ci(diff,'improvement',cfg['seed'])
    write_json(out/'aggregate.json', {'metrics':summary,'paired_precision_differences':paired,
               'test_motions':len(test_y), 'test_scene_candidates':int(test_y.size),
               'test_label_prevalence':float(test_y.mean()),
               'test_motions_without_valid_candidate':int(np.sum(test_y.sum(1)==0)),
               'test_motions_all_candidates_valid':int(np.sum(test_y.sum(1)==test_y.shape[1])),
               'claim':'Offline learned proposal ranking; all selected scenes still need geometric verification.'})


if __name__=='__main__': main()
