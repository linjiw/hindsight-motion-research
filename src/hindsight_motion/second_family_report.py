"""Audited dataset update and scientific figures for repeatable beam traversal."""
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .critical import PROJECT,dump
from .expansion_present import present


def report():
    present(extra_runs=('robust_beam_interventions_20260915_v1',),version=3,prefix='second_family',
            preflight_attempts=134,new_preflight_attempts=36,previous_main=96)
    root=PROJECT/'runs/clearance_tokens_20260915_v1'
    result=json.loads((root/'results.json').read_text());protocol=json.loads((root/'protocol.json').read_text())
    rows=[]
    for summary in result['summary']:
        method=summary['method'];pairs=[r for r in result['pair_rows'] if r['method']==method]
        tp=sum(p['continuous_reference_admitted']-p['missed_admissions'] for p in pairs)
        fp=sum(p['false_admissions'] for p in pairs);fn=sum(p['missed_admissions'] for p in pairs)
        rows.append(dict(**summary,joint_payload_bps=protocol['joint_payload_bits_per_second'][method],
                         true_admissions=tp,false_admissions=fp,missed_admissions=fn,
                         precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None))
    dump(root/'decision_diagnostics.json',dict(rows=rows,gold='Continuous reference geometry, not physical outcomes',
        proposals=643,positive_reference_proposals=111,development_only=True))
    selected=[next(r for r in rows if r['method']==m) for m in ['RVQ','RVQ_PCA9','RVQ_body9','linear29']]
    labels=['RVQ\n140 bit/s','RVQ + PCA9\n1,220 bit/s','RVQ + body9\n1,220 bit/s','Linear 29 joints\n3,480 bit/s']
    colors=['#8291a1','#d5a454','#178c76','#427abc'];x=np.arange(4)
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(14,5.6))
    values=[r['macro_clearance_mae_m']*100 for r in selected]
    axes[0].bar(x,values,color=colors)
    for i,v in enumerate(values):axes[0].text(i,v+.05,f'{v:.3f}',ha='center')
    axes[0].set(title='A. Clearance error relative to continuous motion',ylabel='Macro mean absolute error (cm)',ylim=(0,4.3))
    for i,r in enumerate(selected):
        axes[1].bar(i-.17,r['missed_admissions'],width=.32,color=colors[i])
        axes[1].bar(i+.17,r['false_admissions'],width=.32,color=colors[i],alpha=.35,hatch='//')
    axes[1].set(title='B. Pair-decision errors over 643 candidates',ylabel='Count (solid: misses; hatched: false admissions)')
    axes[2].bar(x,[r['recall']*100 for r in selected],color=colors)
    axes[2].set(title='C. Recall of 111 reference-admitted candidates',ylabel='Recall (%)',ylim=(0,110))
    for ax in axes:ax.set_xticks(x,labels,fontsize=8)
    fig.suptitle('Motion tokens must preserve clearance, not only joint-angle reconstruction',fontsize=16)
    fig.text(.035,.025,'Four development pairs from three source groups; correlated scene candidates. Shared full-rate root adds 11,200 bit/s to every method.\nLogical payloads exclude model and container overhead. Anatomy channels reduce average error but still create false admissions. Decoded motions were not executed.',fontsize=9)
    fig.tight_layout(rect=[0,.14,1,.93]);fig.savefig(PROJECT/'artifacts/clearance_token_comparison.png',dpi=170)
    fig.savefig(PROJECT/'artifacts/clearance_token_comparison.pdf');plt.close(fig)
    print(json.dumps(rows,indent=2))


if __name__=='__main__':report()
