"""Complete-task outcomes beside measured clearance-gate timing."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'results/distance_codec_admission02.json').read_text())
audit = json.loads((root / 'results/endpoint_codec_transfer.json').read_text())
fig, (left, right) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={'width_ratios': [1.2, 1]})
left.axis('off')
left.text(0, .95, 'Complete task: continuous 2/2 · Linear29 1/2', va='top', fontsize=13, weight='bold')
cells=[]
for r in data['rows']:
    cells.append(['Original' if r['condition'] == 'original-beam' else '+0.60 m',
        'Continuous' if r['method'] == 'continuous' else 'Linear29',
        'PASS' if r['success'] else 'DEADLINE', f"{r['elapsed_control_time_s']:.2f} s",
        f"{r['final_goal_distance_3d_m']:.3f} m", 'Loop' if r['decision']['chosen'] else 'Short'])
table = left.table(cellText=cells, colLabels=['Goal', 'Interface', 'Outcome', 'Elapsed', '3D error', 'Exit'],
    cellLoc='center', colWidths=[.15,.22,.20,.14,.15,.14], bbox=[0,.42,1,.42])
table.auto_set_font_size(False); table.set_fontsize(9)
for (i,j), cell in table.get_celld().items():
    cell.set_edgecolor('#cbd1c9'); cell.set_facecolor('#e8ede3' if i == 0 else '#f7f6f0')
    if i == 4: cell.get_text().set_color('#994c31')
left.text(0,.33, 'Farther-goal Linear29 requests the loop at tick 126.\nThe clearance gate blocks it; short remains selected.\nPassage/recovery complete, but no goal hold occurs.',
          va='top', fontsize=11, linespacing=1.6)
left.text(0,.05, 'Goal success uses 3D distance ≤0.50 m.\nAll four runs have zero measured forbidden contact.',
          va='bottom', fontsize=10, color='#43514c')
colors={'continuous':'#1c6153','linear29':'#bd693c'}
for row in audit['measured_gate_audit']:
    if row['condition'] != 'farther-beam': continue
    curve=row['gate_margin_curve']
    right.plot([r['tick'] for r in curve], [100*r['clearance_gate_margin_m'] for r in curve],
        color=colors[row['method']], label='Continuous' if row['method']=='continuous' else 'Linear29', lw=2)
    d=row['decision'];right.scatter(d['tick'],100*d['clearance_gate_margin_m'],s=45,color=colors[row['method']],zorder=5)
right.axhline(0,color='#777d74',ls='--',lw=1)
right.axvline(126,color='#777d74',ls=':',lw=1)
right.axvline(134,color='#bd693c',ls=':',lw=1)
right.set_xlim(118,138)
right.set_ylim(-6,8)
right.set_xticks([118,122,126,130,134,138])
right.set_xlabel('Pre-action control tick')
right.set_ylabel('Margin beyond the required 2 cm clearance (cm)')
right.set_title('A missed decision, despite later clearance',loc='left',fontsize=13,weight='bold')
right.legend(loc='upper left',frameon=False)
right.spines[['top','right']].set_visible(False)
right.annotate('Fixed decision: 126\nLinear29 misses by 1.07 mm',xy=(126,-.1069276328),xytext=(118.5,-2),
    fontsize=10,arrowprops={'arrowstyle':'->','color':'#725b4d'})
right.annotate('Gate first opens: 134\nNo second check',xy=(134,0),xytext=(127,-4.5),
    fontsize=10,arrowprops={'arrowstyle':'->','color':'#725b4d'})
fig.suptitle('Linear29 retains the original task, but loses the farther-goal exit choice',x=.03,ha='left',fontsize=16,weight='bold')
fig.text(.03,.90,'Measured native simulation · unchanged controller, decoder, scene, thresholds and seed',fontsize=11)
fig.text(.03,.05,f"{data['native_attempts']} new attempts · {data['control_steps']:,} control steps · {data['physics_samples']:,} physics samples · zero training/retries\n"
    'One ancestry and two development requests. The limiting proxy is the left ankle; this does not isolate which codec component caused the delay.\n'
    'Later gate opening is an offline observation, not a demonstrated delayed-switch repair.',fontsize=10,color='#43514c')
fig.subplots_adjust(left=.03,right=.98,top=.80,bottom=.25,wspace=.22)
fig.savefig(root/'artifacts/distance_codec_admission02.png',dpi=180)
plt.close(fig)
