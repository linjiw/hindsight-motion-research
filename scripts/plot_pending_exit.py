"""Visualize recorded outcomes and admission events; never infer unrun success."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
x=json.loads((root/'results/pending_exit.json').read_text())
old=json.loads((root/'results/distance_codec_admission02.json').read_text())
fig,(left,right)=plt.subplots(1,2,figsize=(14,6.3),gridspec_kw={'width_ratios':[1.2,1]})
left.axis('off')
rows=[]
for r in x['rows']:
    a=next(v for v in old['rows'] if v['case_id']==r['case_id'])
    outcome=('PASS' if r['success'] else r['stop_reason'].upper()) if r['status']=='completed' else r['status'].upper()
    rows.append(['Original' if r['condition']=='original-beam' else '+0.60 m',
        'Continuous' if r['method']=='continuous' else 'Linear29',
        'PASS' if a['success'] else 'DEADLINE',outcome,
        f"{r['final_goal_distance_3d_m']:.3f} m" if r['status']=='completed' else '—'])
table=left.table(cellText=rows,colLabels=['Goal','Reference','One-time gate','Pending gate','3D goal error'],
    cellLoc='center',colWidths=[.14,.20,.23,.23,.20],bbox=[0,.43,1,.46])
table.auto_set_font_size(False);table.set_fontsize(9)
for (i,j),cell in table.get_celld().items():
    cell.set_edgecolor('#cbd1c9');cell.set_facecolor('#e8ede3' if i==0 else '#f7f6f0')
left.text(0,.97,'Complete-task outcome · same four development cases',fontsize=13,weight='bold')
left.text(0,.33,'Three complete incumbent histories are reproduced exactly.\nLegal pending window: ticks 126–162; five frames committed.\nOffline shadow accepts at 134, without physical qualification.',va='top',fontsize=10.5,linespacing=1.7)
queue=json.loads((root/'results/pending_exit_queue.json').read_text())
samples=queue['final_case_resource_samples'];start=samples[0]['unix_s']
elapsed=[r['unix_s']-start for r in samples]
right.plot(elapsed,[100*r['free_gpu_mib']/12000 for r in samples],marker='o',ms=3,color='#216457',label='GPU free / 12,000 MiB')
right.plot(elapsed,[100*r['available_host_mib']/16384 for r in samples],marker='o',ms=3,color='#bd693c',label='Host available / 16,384 MiB')
right.axhline(100,color='#768177',ls='--',lw=1)
right.set_title('Final case: recorded memory admission wait',loc='left',fontsize=12,weight='bold')
right.text(.03,.97,'Both must reach 100% twice, 20 s apart.\nOnly one sample qualified; no launch.',transform=right.transAxes,va='top',fontsize=10)
right.set_xlim(-5,300);right.set_ylim(20,155)
right.set_xlabel('Seconds since the final case began waiting')
right.set_ylabel('Memory as a percentage of its required threshold')
right.spines[['top','right']].set_visible(False);right.legend(loc='lower right',frameon=False,fontsize=9)
title='Three controls retained; the decisive case is still unrun'
fig.suptitle(title,x=.03,ha='left',fontsize=17,weight='bold')
fig.text(.03,.90,'Native simulation outcomes + recorded resource wait · queue received SIGTERM; sender unknown',fontsize=11)
fig.text(.03,.055,f"{x['native_attempts']} new attempts · {x['control_steps']:,} control steps · {x['physics_samples']:,} physics samples · {x['unrun']} unrun · zero training/retries\n"
    'One ancestry, seed and familiar reset. This temporal-interface intervention does not isolate a codec component or establish generalization.\n'
    'The original four-case failure remains unchanged. Success uses 3D goal distance; endpoint prediction uses XY.',fontsize=10,color='#43514c')
fig.subplots_adjust(left=.03,right=.98,top=.78,bottom=.25,wspace=.23)
fig.savefig(root/'artifacts/pending_exit.png',dpi=180);plt.close(fig)
