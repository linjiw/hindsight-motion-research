"""Create measured figures and a self-contained local motion/scene viewer."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .core import Robot, load_clip
from .pilot import write_json


HTML = r'''<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motion → Scene · Local research viewer</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0d1422;color:#e7edf5;font:15px system-ui,sans-serif}
main{max-width:1280px;margin:auto;padding:28px}h1{font-size:30px;margin:0 0 8px}p{color:#abb9cc;line-height:1.7}
.bar{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:18px 0}select,button{background:#1d2b40;color:#e7edf5;border:1px solid #3b516d;padding:10px;border-radius:8px}select{max-width:100%}button{cursor:pointer}
canvas{display:block;background:#121e30;border:1px solid #293d56;border-radius:16px;width:100%;height:560px;touch-action:none}
.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:20px}.card{border:1px solid #293d56;border-radius:12px;padding:18px;overflow:auto}pre{white-space:pre-wrap;font-size:12px;color:#9cddcc}.tag{padding:4px 10px;border:1px solid #54736c;border-radius:20px;color:#65dabc;font-size:12px}
input[type=range]{flex:1;min-width:180px}label{white-space:nowrap}@media(max-width:700px){main{padding:14px}.grid{grid-template-columns:1fr}canvas{height:410px}}
</style><main><span class="tag">本地真实 mocap · 离线运动学回放</span>
<h1 style="margin-top:16px">从身体动作到障碍场景</h1>
<p>绿色：原始关节动作，经固定 G1 模型计算。橙色：同一路径与根部朝向、固定关节姿态。蓝色：单层 VQ 重建。拖动画面旋转视角。</p>
<div class="bar"><select id="choice" aria-label="Motion example"></select><label><input type="checkbox" id="rigid" checked> 固定姿态</label><label><input type="checkbox" id="vq"> VQ 重建</label></div>
<canvas id="canvas" aria-label="Interactive 3D motion and obstacles"></canvas>
<div class="bar"><button id="play">暂停</button><input type="range" id="time" min="0" value="0" aria-label="Motion frame"><span id="stamp"></span></div>
<div class="grid"><div class="card"><h3>场景验证</h3><div id="details"></div><p>图中绘制关节连线，不能当作机器人完整碰撞表面。模型几何核验以报告中的 MuJoCo 碰撞模型为准。固定姿态不是经过验证的可执行反事实。</p><p>本页面没有策略输出、动态仿真或真实导航成功率。场景对应选中的动作时间窗。</p></div><div class="card"><h3>动作事件</h3><pre id="event"></pre></div></div></main>
<script>const DATA=__DATA__;const PARENTS=__PARENTS__;
const $=id=>document.getElementById(id),canvas=$('canvas'),ctx=canvas.getContext('2d');let current=0,frame=0,playing=true,az=.7,el=.38,last=0;
DATA.forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=s.motion_id+' / scene '+s.candidate_id;$('choice').append(o)});
function select(){current=Number($('choice').value);frame=0;$('time').max=DATA[current].links.length-1;let s=DATA[current];$('details').innerHTML='<p>来源：'+s.source_group+' · '+s.split+'</p><p>原动作最小间距：<b>'+s.original_clearance_text+'</b></p><p>固定姿态最小间距：<b>'+s.rigid_clearance_text+'</b></p><p>证据类型：'+s.verification+'</p>';$('event').textContent=JSON.stringify(s.events.slice(0,4),null,2);}
$('choice').onchange=select;$('time').oninput=()=>{frame=Number($('time').value);playing=false;$('play').textContent='播放'};$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'暂停':'播放'};
let drag=null;canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};canvas.onpointerup=()=>drag=null;canvas.onpointermove=e=>{if(drag){az+=(e.clientX-drag[0])*.008;el=Math.max(.05,Math.min(1.25,el+(e.clientY-drag[1])*.005));drag=[e.clientX,e.clientY]}};
function render(now){if(playing&&now-last>40){frame=(frame+1)%DATA[current].links.length;last=now}let s=DATA[current];let dpr=devicePixelRatio||1,w=canvas.clientWidth,h=canvas.clientHeight;if(canvas.width!==w*dpr||canvas.height!==h*dpr){canvas.width=w*dpr;canvas.height=h*dpr}ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
let min=[Infinity,Infinity,0],max=[-Infinity,-Infinity,1.5];s.links.forEach(f=>f.forEach(p=>p.forEach((v,j)=>{min[j]=Math.min(min[j],v);max[j]=Math.max(max[j],v)})));let mid=min.map((v,j)=>(v+max[j])/2),scale=Math.min(w,h)*.65/Math.max(2,max[0]-min[0],max[1]-min[1]);
function project(p){let x=p[0]-mid[0],y=p[1]-mid[1],z=p[2]-mid[2];let u=x*Math.cos(az)-y*Math.sin(az),v=x*Math.sin(az)+y*Math.cos(az);return[w/2+u*scale,h*.53+(v*Math.sin(el)-z*Math.cos(el))*scale]}
function line(a,b,color,width=2){let p=project(a),q=project(b);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...q);ctx.stroke()}
for(let i=-4;i<=4;i++){line([mid[0]+i*.5,mid[1]-2,0],[mid[0]+i*.5,mid[1]+2,0],'#20364c',1);line([mid[0]-2,mid[1]+i*.5,0],[mid[0]+2,mid[1]+i*.5,0],'#20364c',1)}
s.boxes.forEach(b=>{let pts=[];for(let i=0;i<8;i++)pts.push([b[0]+(i&1?1:-1)*b[3],b[1]+(i&2?1:-1)*b[4],b[2]+(i&4?1:-1)*b[5]]);for(let i=0;i<8;i++)for(let k of [1,2,4])if(!(i&k))line(pts[i],pts[i|k],'#e5b86b',2)});
for(let i=1;i<s.links.length;i++)line(s.links[i-1][0],s.links[i][0],'#295b68',1);
function skeleton(points,color,width){for(let i=1;i<points.length;i++)line(points[i],points[PARENTS[i]],color,width);points.forEach(p=>{let q=project(p);ctx.fillStyle=color;ctx.beginPath();ctx.arc(q[0],q[1],width,0,7);ctx.fill()})}
if($('rigid').checked)skeleton(s.rigid_links[frame],'#e79555',2);if($('vq').checked)skeleton(s.vq_links[frame],'#629fec',2);skeleton(s.links[frame],'#61dfba',3);
ctx.fillStyle='#abb9cc';ctx.font='13px system-ui';ctx.fillText('25 Hz display · axes and distances in meters · kinematic replay',18,28);$('time').value=frame;$('stamp').textContent=(frame/25).toFixed(2)+' s';requestAnimationFrame(render)}select();requestAnimationFrame(render);
</script></html>'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args()
    pilot=a.root/'runs/pilot_20260915_v1';prop=a.root/'runs/proposer_20260915_v1';geom=a.root/'runs/geometry_20260915_v1'
    p=json.loads((pilot/'aggregate.json').read_text());r=json.loads((prop/'aggregate.json').read_text());g=json.loads((geom/'aggregate.json').read_text())
    out=a.root/'artifacts';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
    fig,axes=plt.subplots(2,2,figsize=(13,8.5));fig.subplots_adjust(hspace=.50,wspace=.32,top=.90,bottom=.12)
    methods=['rigid_pose','vq','rvq'];labels=['Rigid posture','VQ 128','RVQ 128 x 2'];colors=['#bd763e','#477ec0','#218474']
    vals=[p['test_representation'][m]['clearance_mae_m']['mean_motion_weighted']*100 for m in methods]
    axes[0,0].bar(labels,vals,color=colors);axes[0,0].axhline(3,color='#aa3c3c',ls='--',label='Placement margin: 3 cm')
    axes[0,0].set(ylabel='Mean absolute clearance error (cm)',title='A. Compression loses placement precision');axes[0,0].legend(frameon=False,fontsize=9)
    vals=[p['test_representation'][m]['collision_disagreement']['mean_motion_weighted']*100 for m in methods]
    axes[0,1].bar(labels,vals,color=colors);axes[0,1].set(ylabel='Collision-decision disagreement (%)',title='B. 6,912 boxes from a separate probe sampler')
    for i,v in enumerate(vals):axes[0,1].text(i,v+.15,f'{v:.2f}%',ha='center')
    positions=np.arange(3)
    for seed,color in [(0,'#477ec0'),(1,'#218474')]:
        vals=[r['metrics'][m][str(seed)]['precision_at_10']['mean_motion_weighted']*100 for m in ['root','root_events','root_tokens']]
        axes[1,0].bar(positions+(seed-.5)*.32,vals,width=.30,color=color,label=f'Training seed {seed}')
    random=r['metrics']['random_order']['-1']['precision_at_10']['mean_motion_weighted']*100
    axes[1,0].axhline(random,color='#aa3c3c',ls='--',label=f'Random order: {random:.1f}%')
    axes[1,0].set(xticks=positions,xticklabels=['Root','Root + events','Root + tokens'],ylabel='Valid candidates among top 10 (%)',title='C. Tokens do not improve this small ranker',ylim=(0,65));axes[1,0].legend(frameon=False,fontsize=8)
    axes[1,1].bar(['Sphere proxy','Model geometry'],[g['rigid_proxy_overlap_scenes'],g['rigid_model_overlap_scenes']],color=['#bd763e','#218474'])
    axes[1,1].set(ylabel='Scenes overlapping rigid-pose diagnostic',title='D. Most proxy witnesses do not survive',ylim=(0,32))
    for i,v in enumerate([g['rigid_proxy_overlap_scenes'],g['rigid_model_overlap_scenes']]):axes[1,1].text(i,v+.6,str(v),ha='center')
    fig.suptitle('Hindsight motion research | measured offline pilot',fontsize=19)
    fig.text(.05,.025,'Representation: 144 test motions / 31 source groups. Scene/ranker: 28 translating test motions / 16 source groups.\n84 original scenes clear model geometry at 100 Hz. Rigid posture is not an executable counterfactual; no policy evaluation.',fontsize=10,color='#444444')
    fig.savefig(out/'pilot_summary.png',dpi=170);fig.savefig(out/'pilot_summary.pdf');plt.close(fig)
    cfg=json.loads((pilot/'config.json').read_text());robot=Robot(cfg['robot_xml'])
    checked=list(csv.DictReader((geom/'per_scene.csv').open()))
    scene_map={(s['motion_id'],str(s['candidate_id'])):s for s in map(json.loads,(pilot/'scenes.jsonl').read_text().splitlines())}
    selected=sorted(checked,key=lambda r:(float(r['rigid_model_clearance_m'])>=0,float(r['rigid_model_clearance_m'])))[:10]
    neutral=np.load(pilot/'codebook.npz')['neutral_joints']
    from .core import PatchQuantizer, extract_events
    z=np.load(pilot/'codebook.npz');quantizer=PatchQuantizer([z['level0'],z['level1']])
    dataset=[]
    for row in selected:
        s=scene_map[row['motion_id'],row['candidate_id']];c=load_clip(s['source_path'],cfg['window_seconds'],5)
        q=c['qpos'];rigid=q.copy();rigid[:,7:]=neutral
        codes=quantizer.encode(q[:,7:].reshape(-1,145));vq=q.copy();vq[:,7:]=quantizer.decode(codes,1).reshape(-1,29)
        _,links,quats=robot.fk(q)
        dataset.append({'motion_id':s['motion_id'],'source_group':s['source_group'],'split':s['split'],'candidate_id':s['candidate_id'],
            'links':links[::2].round(4).tolist(),'rigid_links':robot.fk(rigid)[1][::2].round(4).tolist(),
            'vq_links':robot.fk(vq)[1][::2].round(4).tolist(),'boxes':s['boxes'],
            'events':extract_events(c,links,quats,codes),
            'original_clearance_text':f'{float(row["original_model_clearance_m"])*100:.2f} cm',
            'rigid_clearance_text':f'{float(row["rigid_model_clearance_m"])*100:.2f} cm',
            'verification':'MuJoCo collision geometry, 100 Hz kinematic poses; dynamics unverified'})
    parents=(robot.model.body_parentid[1:]-1).tolist();parents[0]=0
    html=HTML.replace('__DATA__',json.dumps(dataset,ensure_ascii=False).replace('</','<\\/')).replace('__PARENTS__',json.dumps(parents))
    (out/'viewer.html').write_text(html)
    write_json(out/'viewer_manifest.json',{'examples':[(d['motion_id'],d['candidate_id']) for d in dataset],
               'selection':'all 3 model-geometry rigid-overlap witnesses first, then nearest nonoverlap examples; illustration only',
               'display_fps':25,'verification_fps':100})
    print(out)


if __name__=='__main__':main()
