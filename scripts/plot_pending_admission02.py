"""Plot the recorded one-case admission, retaining old failure and reused controls."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
packet = ROOT/'runs/pending_exit_20260920_admission02'
result = json.loads((ROOT/'results/pending_exit_admission02.json').read_text())
case = json.loads((packet/'plan.json').read_text())['cases'][0]
folder, old = Path(case['run_dir']), Path(case['parent_run'])
row = result['rows'][-1]
fig, axes = plt.subplots(2,2,figsize=(13,8.8))
table_ax, goal_ax, gate_ax, speed_ax = axes.flat
table_ax.axis('off')
cells=[]
for r in result['rows']:
    outcome = ('PASS' if r['success'] else r['stop_reason'].upper()) if r['status']=='completed' else r['status'].upper()
    cells.append(['Original' if r['condition']=='original-beam' else '+0.60 m',
        'Continuous' if r['method']=='continuous' else 'Linear29',outcome,
        'reused' if r['admission']=='01' else 'new' if r['status']=='completed' else 'no launch'])
table=table_ax.table(cellText=cells,colLabels=['Goal','Reference','Pending outcome','This admission'],
    cellLoc='center',colWidths=[.16,.24,.30,.30],bbox=[0,.35,1,.57])
table.auto_set_font_size(False);table.set_fontsize(9)
for (i,j),cell in table.get_celld().items():
    cell.set_edgecolor('#cbd1c9');cell.set_facecolor('#e8ede3' if i==0 else '#f7f6f0')
table_ax.set_title('Same four registered development cases',loc='left',fontweight='bold',fontsize=12)
table_ax.text(0,.24,'The original farther Linear29 still records DEADLINE.\nThree completed controls are reused, never rerun.\nTask success requires passage, recovery and a 1 s stop hold.',fontsize=10,va='top',linespacing=1.5)
samples=[json.loads(s) for s in (folder/'resource_wait.jsonl').read_text().splitlines()]
gate_ax.plot([s['unix_s']-samples[0]['unix_s'] for s in samples],
    [100*s['free_gpu_mib']/12000 for s in samples],'-o',ms=3,color='#216457',label='GPU free / 12,000 MiB')
gate_ax.plot([s['unix_s']-samples[0]['unix_s'] for s in samples],
    [100*s['available_host_mib']/16384 for s in samples],'-o',ms=3,color='#bd693c',label='Host available / 16,384 MiB')
gate_ax.axhline(100,ls='--',color='#777');gate_ax.set_ylabel('Required memory threshold (%)')
gate_ax.set_xlabel('Seconds since admission 02 began waiting')
gate_ax.set_title('Recorded resource admission',loc='left',fontweight='bold',fontsize=12)
gate_ax.legend(frameon=False,fontsize=9)
task=json.loads((folder/'task.json').read_text())
for path,label,color,ls in [(old,'Incumbent Linear29','#a44c3f','--')]+(
    [(folder,'Pending Linear29','#216457','-')] if row['status']=='completed' else []):
    with np.load(path/'task/trace.npz') as trace:
        time=(np.arange(len(trace['root_xyz']))+1)*.02
        distance=np.linalg.norm(trace['root_xyz']-np.asarray(task['goal_xyz']),axis=1)
        goal_ax.plot(time,distance,label=label,color=color,ls=ls)
        speed_ax.plot(time,trace['speed'],label=label,color=color,ls=ls)
goal_ax.axhline(.5,color='#777',ls=':',label='Frozen 0.50 m 3D radius')
speed_ax.axhline(.1,color='#777',ls=':',label='Frozen 0.10 m/s stop speed')
goal_ax.set_title('Farther goal: measured post-action error',loc='left',fontweight='bold',fontsize=12)
speed_ax.set_title('Farther goal: measured speed',loc='left',fontweight='bold',fontsize=12)
goal_ax.set_ylabel('3D root-to-goal distance (m)');speed_ax.set_ylabel('Speed (m/s)')
for ax in (goal_ax,speed_ax):
    ax.set_xlabel('Elapsed control time (s)');ax.legend(frameon=False,fontsize=8)
    if row['status']=='completed' and row['request_lifecycle']['accepted_tick'] is not None:
        ax.axvline(.02*row['request_lifecycle']['accepted_tick'],color='#216457',alpha=.5,ls=':')
for ax in (goal_ax,gate_ax,speed_ax):ax.spines[['top','right']].set_visible(False)
completed=row['status']=='completed'
title=('Delayed admission completes the farther Linear29 task' if completed and row['success'] else
       'Delayed admission: recorded task failure' if completed else 'Resource admission closed without the decisive launch')
subtitle=(f"Request 126 → accepted {row['request_lifecycle']['accepted_tick']} · final 3D error {row['final_goal_distance_3d_m']:.3f} m"
          if completed else 'Only the incumbent physical trajectory is shown; no pending outcome is inferred.')
fig.suptitle(title,x=.05,ha='left',fontsize=17,fontweight='bold')
fig.text(.05,.925,subtitle,fontsize=11)
fig.text(.05,.025,f"Admission 02: {result['new_native_attempts']} new native attempt · {result['new_control_steps']} control steps · "
    f"{result['new_physics_samples']} physics samples. Combined: {result['native_attempts']} attempts / {result['control_steps']} steps.\n"
    'One ancestry, seed and familiar reset. No training, retry, generalization or isolated quantization claim. Prior SIGTERM receipt remains unchanged.',fontsize=9.5)
fig.subplots_adjust(left=.07,right=.98,bottom=.12,top=.86,hspace=.50,wspace=.30)
fig.savefig(ROOT/'artifacts/pending_exit_admission02.png',dpi=180)
plt.close(fig)
