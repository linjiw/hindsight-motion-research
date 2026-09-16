"""Scientific figures and a standalone viewer of measured native interventions."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from .core import Robot
from .critical import PROJECT


def read_run(root,condition,variant,perturbation=0):
    run=root/f'arm03_{condition}_{variant}_p{perturbation}'
    task=json.loads((run/'task.json').read_text())
    manifest=json.loads((run/'manifest.json').read_text())[0]
    episode=dict(np.load(run/'metrics'/f"episode-{manifest['motion_key']}.npz"))
    force=np.load(run/'metrics/environment-contacts.npz')['normal_force_w']
    outcome=json.loads((run/'metrics/scene-outcome.json').read_text())
    names=json.loads((run/'metrics/episode-contract.json').read_text())['measured_body_names']
    return dict(task=task,episode=episode,force=force,outcome=outcome,names=names)


def box_vertices(obstacle):
    points=np.array([[i,j,k] for i in [-.5,.5] for j in [-.5,.5] for k in [-.5,.5]])
    r=Rotation.from_quat(np.asarray(obstacle['quaternion_wxyz'])[[1,2,3,0]]).as_matrix()
    return (points*np.asarray(obstacle['full_dimensions_xyz']))@r.T+obstacle['center_xyz']


HTML=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Executed critical motion scenes</title>
<style>body{margin:0;background:#0b1522;color:#e5edf6;font:15px system-ui}main{max-width:1250px;margin:auto;padding:28px}h1{font-size:28px;margin:0 0 8px}p{color:#b2c1d3;line-height:1.5}.row{display:flex;gap:15px;align-items:center;flex-wrap:wrap}select,button{background:#192b40;color:white;padding:10px;border:1px solid #425a73;border-radius:8px}canvas{width:100%;height:540px;background:#101f30;border-radius:14px;margin:16px 0}input{flex:1;min-width:160px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px}.card{background:#17293d;padding:18px;border-radius:10px;line-height:1.6}.muted{color:#a9bbcf;font-size:13px}</style>
<main><h1>Does the obstacle make the arm motion useful?</h1><p>Measured SONIC / IsaacLab rollouts · One mocap carrier, two executable arm continuations, four scene interventions.<br>Green: tucked arms. Orange: wide arms. These traces show the robot’s simulated motion.</p>
<div class="row"><label>Scene <select id="scene"></select></label><label>Initial lateral offset <select id="perturb"><option value="0">0 cm</option><option value="1">−1.5 cm</option><option value="2">+1.5 cm</option></select></label><button id="play">Pause</button><input type="range" id="time" min="0" value="0"><span id="stamp"></span></div><canvas id="canvas"></canvas><div class="cards"><div class="card" id="tight"></div><div class="card" id="wide"></div></div><p class="muted">Drag to rotate. Display: 25 Hz. Contact measurements: 200 Hz. Passage success requires tracking, no obstacle/non-foot floor contact above 1 N, and moving arrival beyond the gap. No stopping, held-out generalization, or student-policy performance is claimed.</p></main>
<script>const DATA=__DATA__,PARENTS=__PARENTS__;const $=id=>document.getElementById(id),c=$('canvas'),ctx=c.getContext('2d');let frame=0,playing=true,last=0,az=.7,el=.48,drag=null,current;
['critical','relaxed','removed','displaced'].forEach(k=>{$('scene').add(new Option(k[0].toUpperCase()+k.slice(1),k))});
function select(){current=DATA.find(d=>d.condition===$('scene').value&&d.perturbation===+$('perturb').value);if(!current)return;frame=0;$('time').max=current.tuck.length-1;for(let k of ['tuck','wide']){let r=current.outcomes[k];$(k==='tuck'?'tight':'wide').innerHTML=`<b style="color:${k==='tuck'?'#63ddba':'#f4a16a'}">${k==='tuck'?'Tucked':'Wide'} arms · ${r.scene_passage_verified?'PASS':'FAIL'}</b><br>Peak obstacle force: ${r.max_obstacle_normal_force_n.toFixed(1)} N<br>Final goal error: ${(100*r.final_goal_distance_m).toFixed(1)} cm<br>Mean body tracking error: ${(100*r.mean_body_error_m).toFixed(1)} cm`}}
$('scene').onchange=select;$('perturb').onchange=select;$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'Pause':'Play'};$('time').oninput=()=>{frame=+$('time').value;playing=false;$('play').textContent='Play'};
c.onpointerdown=e=>{drag=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId)};c.onpointerup=()=>drag=null;c.onpointermove=e=>{if(drag){az+=(e.clientX-drag[0])*.008;el=Math.max(.08,Math.min(1.3,el+(e.clientY-drag[1])*.006));drag=[e.clientX,e.clientY]}};
function render(now){if(!current){requestAnimationFrame(render);return}if(playing&&now-last>40){frame=(frame+1)%current.tuck.length;last=now}let w=c.clientWidth,h=c.clientHeight,d=devicePixelRatio||1;if(c.width!==w*d||c.height!==h*d){c.width=w*d;c.height=h*d}ctx.setTransform(d,0,0,d,0,0);ctx.clearRect(0,0,w,h);let mid=current.center,scale=Math.min(w/4,h/2.6);
function proj(p){let x=p[0]-mid[0],y=p[1]-mid[1],z=p[2]-.65;let u=x*Math.cos(az)-y*Math.sin(az),v=x*Math.sin(az)+y*Math.cos(az);return[w/2+u*scale,h*.53+(v*Math.sin(el)-z*Math.cos(el))*scale]}
function line(a,b,color,width=2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...proj(a));ctx.lineTo(...proj(b));ctx.stroke()}
for(let i=-5;i<=5;i++){line([mid[0]+i*.4,mid[1]-2,0],[mid[0]+i*.4,mid[1]+2,0],'#263c50',1);line([mid[0]-2,mid[1]+i*.4,0],[mid[0]+2,mid[1]+i*.4,0],'#263c50',1)}
for(let box of current.boxes){for(let i=0;i<8;i++)for(let bit of [1,2,4])if(!(i&bit))line(box[i],box[i|bit],'#b4c4d4',2)}
for(let k of ['wide','tuck']){let color=k==='tuck'?'#63ddba':'#f4a16a';let points=current[k][frame];for(let j=1;j<points.length;j++)line(points[j],points[PARENTS[j]],color,3);for(let p of points){ctx.fillStyle=color;ctx.beginPath();ctx.arc(...proj(p),3,0,7);ctx.fill()}for(let t=1;t<current[k].length;t++)line(current[k][t-1][0],current[k][t][0],color+'65',1)}
ctx.fillStyle='#bdcde0';ctx.font='14px system-ui';ctx.fillText('Measured native dynamics · common initial state and history',18,27);$('time').value=frame;$('stamp').textContent=(frame/25).toFixed(2)+' s';requestAnimationFrame(render)}select();requestAnimationFrame(render);</script></html>'''


def present(root):
    root=Path(root);out=PROJECT/'artifacts';out.mkdir(exist_ok=True)
    a=read_run(root,'critical','tuck');b=read_run(root,'critical','wide')
    robot=Robot(PROJECT/'../lucid/GR00T-WholeBodyControl/gear_sonic_deploy/g1/g1_29dof.xml')
    name_parent={name:robot.model.body(int(robot.model.body_parentid[i+1])).name for i,name in enumerate(robot.names)}
    names=a['names'];parents=[names.index(name_parent[n]) if name_parent[n] in names else 0 for n in names]
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':11})
    fig=plt.figure(figsize=(13,8.5));gs=fig.add_gridspec(2,2,hspace=.4,wspace=.32)
    ax=fig.add_subplot(gs[0,0],projection='3d')
    frame=65
    for values,color,label in [(a,'#168b72','Tucked'),(b,'#d97936','Wide')]:
        p=values['episode']['body_xyz'][frame]
        for i in range(1,len(names)):ax.plot(*p[[i,parents[i]]].T,color=color,lw=2)
        ax.plot([],[],[],color=color,label=label)
    for obstacle in a['task']['obstacles']:
        vertices=box_vertices(obstacle)
        for i in range(8):
            for bit in [1,2,4]:
                if not i&bit:ax.plot(*vertices[[i,i|bit]].T,color='#6b7e94',alpha=.55)
    ax.set(title='A. Executed arm contrast at 1.30 s',xlabel='World X (m)',ylabel='World Y (m)',zlabel='Height (m)')
    ax.set_box_aspect([1,1,1]);ax.view_init(20,35);ax.legend(fontsize=9)
    ax=fig.add_subplot(gs[0,1])
    for values,color,label in [(a,'#168b72','Tucked'),(b,'#d97936','Wide')]:
        force=np.linalg.norm(values['force'][:,:,1:],axis=-1).max(axis=(1,2))
        ax.plot((np.arange(len(force))+1)*.005,force,color=color,label=label)
    ax.set(title='B. Critical passage: measured obstacle contact',xlabel='Time (s)',ylabel='Maximum normal force (N)');ax.legend()
    ax=fig.add_subplot(gs[1,0]);conditions=['critical','relaxed','removed','displaced'];x=np.arange(4)
    for variant,color,shift in [('tuck','#168b72',-.17),('wide','#d97936',.17)]:
        values=[]
        for c in conditions:
            r=[read_run(root,c,variant,p)['outcome']['scene_passage_verified'] for p in range(3)]
            values.append(sum(r))
        ax.bar(x+shift,values,width=.32,color=color,label=variant)
    ax.set(xticks=x,xticklabels=[c.capitalize() for c in conditions],ylim=(0,3.5),yticks=[0,1,2,3],
           ylabel='Passing initial perturbations / 3',title='C. All 24 registered scene executions');ax.legend()
    ax=fig.add_subplot(gs[1,1])
    for variant,color in [('tuck','#168b72'),('wide','#d97936')]:
        for j,c in enumerate(conditions):
            values=[read_run(root,c,variant,p)['outcome']['final_goal_distance_m']*100 for p in range(3)]
            ax.scatter(np.full(3,j)+(-.1 if variant=='tuck' else .1),values,color=color,
                       label=variant if j==0 else None,s=45)
    ax.axhline(25,color='#a24249',ls='--',label='Goal tolerance')
    ax.set(xticks=x,xticklabels=[c.capitalize() for c in conditions],ylabel='Final goal distance (cm)',
           title='D. Task outcome beyond staying upright');ax.legend(fontsize=9)
    fig.suptitle('Hindsight scene interventions | measured SONIC / IsaacLab pilot',fontsize=17,y=.98)
    fig.text(.06,.01,'One source group and one edited motion pair. Initial lateral offsets: 0, −1.5, +1.5 cm. Nominal robot; no sensor noise.\nMoving arrival only. Development evidence; no held-out policy generalization or learned scene-generator claim.',fontsize=10)
    fig.subplots_adjust(bottom=.12,top=.91)
    fig.savefig(out/'critical_interventions.png',dpi=170);fig.savefig(out/'critical_interventions.pdf');plt.close(fig)
    dataset=[]
    for c in conditions:
        for p in range(3):
            tight=read_run(root,c,'tuck',p);wide=read_run(root,c,'wide',p)
            dataset.append(dict(condition=c,perturbation=p,
                tuck=tight['episode']['body_xyz'][::2].round(5).tolist(),
                wide=wide['episode']['body_xyz'][::2].round(5).tolist(),
                boxes=[box_vertices(o).round(5).tolist() for o in tight['task']['obstacles']],
                center=tight['task']['portal_center_xyz'],
                outcomes={'tuck':tight['outcome'],'wide':wide['outcome']}))
    (out/'critical_viewer.html').write_text(HTML.replace('__DATA__',json.dumps(dataset)).replace('__PARENTS__',json.dumps(parents)))
    print(out/'critical_viewer.html')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args();present(args.output)
