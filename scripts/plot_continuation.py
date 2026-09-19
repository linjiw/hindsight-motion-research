"""Aggregate execution status and offline reference jumps; no motion trajectories."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--summary',default='results/continuation.json')
parser.add_argument('--output',default='artifacts/continuation.png')
args=parser.parse_args()
data=json.loads((ROOT/args.summary).read_text())
offline=data['offline_input_diagnostics']['rows']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(13,5.7),gridspec_kw={'width_ratios':[1,1.4]})
labels=[f"{r['source_clip']} / {r['state'].replace('_',' ')}" for r in offline]
colors={'pass':'#1c6153','fail':'#bb592e','unrun':'#dfe4de','invalid':'#be943e'}
for i,row in enumerate(offline):
    for j,method in enumerate(['continuous','linear29']):
        outcome=next(r for r in data['rows'] if r['source_clip']==row['source_clip'] and r['state']==row['state'] and r['method']==method)
        status=('pass' if outcome['success'] else 'fail') if outcome['status']=='completed' else ('unrun' if outcome['status']=='unrun' else 'invalid')
        axes[0].add_patch(plt.Rectangle((j-.42,i-.38),.84,.76,color=colors[status]))
        label=status.upper()
        if outcome['status']=='completed':label+=f"\n{outcome['completion_time_s']:.2f} s"
        axes[0].text(j,i,label,ha='center',va='center',fontsize=9,color='white' if status in ['pass','fail'] else '#263f38')
axes[0].set(xlim=(-.6,1.6),ylim=(len(offline)-.5,-.5))
axes[0].set_xticks([0,1],['Continuous','Linear29'])
axes[0].set_yticks(np.arange(len(offline)),labels)
axes[0].set_title('Task outcomes · time from reset',loc='left',pad=16)
for spine in axes[0].spines.values():spine.set_visible(False)
axes[0].tick_params(length=0)
y=np.arange(len(offline))
axes[1].barh(y-.16,[r['input_joint_max_rad'] for r in offline],.3,color='#1c6153',label='All joints')
axes[1].barh(y+.16,[r['nonwrist_input_joint_max_rad'] for r in offline],.3,color='#bb592e',label='Excluding four clipped wrist channels')
axes[1].set_yticks(y,[f"{r['handoff_time_s']:.2f} s" for r in offline])
axes[1].set_ylim(len(offline)-.5,-.5)
axes[1].set_xlabel('Maximum input joint-reference change (rad)')
axes[1].set_title('Offline jump at each planned handoff',loc='left',pad=16)
axes[1].legend(frameon=False,fontsize=8,loc='upper right')
status='Native execution deferred' if data['execution_state']=='resource_deferred' else 'Matched-prefix continuation'
fig.suptitle(status+' · two development clips',x=.025,ha='left',fontsize=16,fontweight='bold')
fig.text(.025,.025,f"{data['native_attempts']} native attempts / {data['scheduled_cases']} planned cells · {data['qualified_pairs']} qualified pairs · {data['unrun']} unrun\n"
         'Offline differences are not task failures. Supplied prefix, phase, root and future remain; no perturbation or generalization claim.',fontsize=9,color='#4a5651')
fig.subplots_adjust(left=.18,right=.98,top=.84,bottom=.18,wspace=.35)
fig.savefig(ROOT/args.output,dpi=180)
plt.close(fig)
