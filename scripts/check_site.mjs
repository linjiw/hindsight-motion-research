// Non-browser smoke check: exercise the static app against its published evidence.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html=fs.readFileSync(path.join(root,'_site/index.html'),'utf8');
const nodes=new Map();
function node(value=''){return {value,textContent:'',innerHTML:'',dataset:{},attributes:{},handlers:{},addEventListener(event,fn){this.handlers[event]=fn;},setAttribute(key,val){this.attributes[key]=val;}};}
for(const match of html.matchAll(/id="([^"]+)"/g))nodes.set(`#${match[1]}`,node());
nodes.get('#method').value='body9_leg12'; nodes.get('#scrub').value='5';
nodes.get('#metric').value='passes'; nodes.get('#family').value='arm03';
const buttons={};
for(const key of ['condition','interface'])buttons[`[data-${key}]`]=[...html.matchAll(new RegExp(`data-${key}="([^"]+)"`,'g'))].map(m=>Object.assign(node(),{dataset:{[key]:m[1]}}));
const errors=[];
const context=vm.createContext({console:{error:(...args)=>errors.push(args)},document:{
 querySelector(selector){assert(nodes.has(selector),`Unknown selector ${selector}`);return nodes.get(selector);},
 querySelectorAll(selector){assert(buttons[selector],`Unknown button group ${selector}`);return buttons[selector];}
},fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'_site',url),'utf8'))})});
vm.runInContext(fs.readFileSync(path.join(root,'_site/app.js'),'utf8'),context);
await new Promise(resolve=>setImmediate(resolve));
assert.equal(errors.length,0,'Evidence loading or render failed');
const run=source=>vm.runInContext(source,context);
const evidence=JSON.parse(fs.readFileSync(path.join(root,'results/token_mechanism.json')));
for(const method of evidence.methods){
 nodes.get('#method').value=method.method;nodes.get('#method').handlers.change();
 assert.equal(nodes.get('#method-pass').textContent,`${method.joint_passes} / 18`);
 assert(!nodes.get('#signal').innerHTML.includes('NaN'));
}
for(const patch of [0,19]){nodes.get('#scrub').value=String(patch);nodes.get('#scrub').handlers.input();assert.equal(nodes.get('#patch-output').textContent,`Patch ${patch+1} / 20`);}
for(const metric of ['passes','foot','clearance','rate']){nodes.get('#metric').value=metric;nodes.get('#metric').handlers.change();const chart=nodes.get('#comparison').innerHTML;assert.equal((chart.match(/class="bar-row/g)||[]).length,6);assert(!chart.includes('NaN'));}
for(const family of ['arm03','hybrid205']){
 nodes.get('#family').value=family;nodes.get('#family').handlers.change();
 for(const button of buttons['[data-condition]']){
  button.handlers.click();assert.equal(button.attributes['aria-pressed'],'true');
  const scores=nodes.get('#scene-scores').innerHTML;
  assert.equal((scores.match(/3 \/ 3/g)||[]).length,button.dataset.condition==='critical'?1:2);
  assert(!nodes.get('#scene-diagram').innerHTML.includes('NaN'));
 }
}
for(const button of buttons['[data-interface]']){button.handlers.click();assert.equal(button.attributes['aria-pressed'],'true');assert(nodes.get('#interface-detail').innerHTML.length>300);}
// Missing evidence must show an explicit error, never an empty success chart.
context.fetch=async()=>({ok:false,status:503});
await run('loadEvidence()');
assert(nodes.get('#comparison').innerHTML.includes('could not load'));
assert(nodes.get('#scene-scores').textContent.includes('unavailable'));
console.log('Passed: 8 methods, 4 metrics, 8 intervention states, 5 interfaces, scrub endpoints and data-load failure.');
