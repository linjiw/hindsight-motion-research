"""Aggregate complete-task outcomes; no source or executed motion arrays."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
data=json.loads((root/'results/selection_codec.json').read_text())
fig,ax=plt.subplots(figsize=(10,4.7))
colors={'continuous':'#1c6153','linear29':'#bd693c'}
for i,row in enumerate(data['rows']):
    if row['status']=='completed':
        ax.barh(i,row['completion_time_s'],height=.6,color=colors[row['method']])
        status='PASS' if row['success'] else 'FAIL'
        ax.text(row['completion_time_s']+.08,i,f"{status}  {row['completion_time_s']:.2f} s",va='center',fontsize=11)
    else:
        ax.text(.05,i,row['status'].upper(),va='center')
ax.set_yticks(range(4),[('Clear' if r['condition']=='clear' else 'Beam')+' / '+('Continuous' if r['method']=='continuous' else 'Linear29') for r in data['rows']])
ax.set_ylim(3.6,-.6)
ax.set_xlim(0,10.6)
ax.axvline(10,color='#8f958f',ls='--',lw=1)
ax.text(10,-.48,'Deadline',ha='right',fontsize=9,color='#555')
ax.set_xlabel('Complete-task duration from reset (seconds)')
ax.spines[['top','right']].set_visible(False)
fig.suptitle('Selected motion, fixed planner, two reference representations',x=.025,ha='left',fontsize=15,fontweight='bold')
fig.text(.025,.04,f"{data['native_attempts']} native attempts · {data['control_steps']:,} control steps · zero training\n"
         'One familiar ancestry; known map and simulator localization. Continuous planner bank retained in both methods.\n'
         'Timing is descriptive. No held-out robustness, cross-family switching or total-system compression claim.',fontsize=9,color='#43514c')
fig.subplots_adjust(left=.22,right=.98,top=.85,bottom=.27)
fig.savefig(root/'artifacts/selection_codec.png',dpi=180)
plt.close(fig)
