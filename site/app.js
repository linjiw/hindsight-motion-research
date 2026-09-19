'use strict';
const $ = (s) => document.querySelector(s);
const methods = {
  continuous: {title:'The original reference is the anchor.', description:'Continuous joint angles establish the reference qualification rate. This is the information-rich control.', rate:46400, pass:18},
  linear29: {title:'A strong, simple execution baseline.', description:'Quantize all 29 joints at 10 Hz, then interpolate to 50 Hz. The latest repeat qualifies 16/18 episodes; the earlier decoder study recorded 17/18.', rate:3480, pass:16},
  body9_raw: {title:'Upper-body precision is not enough.', description:'Two RVQ codes plus nine torso/arm residual channels improve geometry, but none of these preflights qualify for execution.', rate:1220, pass:0},
  body9_smooth: {title:'Smoother does not mean executable.', description:'A five-frame binomial filter softens discontinuities. Qualification remains 0/18; poor leg reconstruction persists.', rate:1220, pass:0},
  body9_leg12: {title:'Preserve the legs. Recover execution.', description:'Replace twelve leg channels with 10 Hz, 12-bit angle knots. Qualification rises to 15/18; all six selected arm/beam panels are preserved.', rate:2660, pass:15},
  body9_smooth_leg12: {title:'Smoothing adds no pass here.', description:'Smoothing plus leg12 also qualifies 15/18 episodes. The leg correction is applied after smoothing.', rate:2660, pass:15},
  body9_legoracle: {title:'An oracle diagnoses information loss.', description:'Original 50 Hz leg angles raise qualification to 15/18. This extra original information makes the oracle an unfair compression comparator.', rate:20420, pass:15},
  body9_smooth_legoracle: {title:'An upper bound, with extra information.', description:'Smoothing plus original legs qualifies 17/18 episodes. It is diagnostic evidence, not a deployable compressed-leg result.', rate:20420, pass:17}
};
let evidence;
function renderLab(){
 const key=$('#method').value,m=methods[key];
 $('#method-title').textContent=m.title; $('#method-description').textContent=m.description;
 const row=evidence?.mechanism.methods.find(r=>r.method===key);
 $('#method-pass').textContent=`${row?.joint_passes ?? m.pass} / 18`;
 $('#method-rate').textContent=`${m.rate.toLocaleString('en-US')} bit/s`;
 const patch=Number($('#scrub').value); $('#patch-output').textContent=`Patch ${patch+1} / 20`;
 const signal=(x)=>.6*Math.sin(x*.087)+.15*Math.sin(x*.21);
 const reconstructed=(x)=>{
  if(key==='continuous'||key.includes('oracle'))return signal(x);
  if(key.includes('leg12')||key==='linear29'){const lo=Math.floor(x/5)*5;return signal(lo)+(signal(lo+5)-signal(lo))*(x-lo)/5;}
  const center=Math.floor(x/5)*5+2;
  const raw=signal(center)+.27*Math.sin(Math.floor(x/5)*1.6);
  return key==='body9_smooth'?.65*raw+.35*signal(x):raw;
 };
 const path=(fn)=>Array.from({length:101},(_,i)=>`${i?'L':'M'}${35+i*6.1},${110-fn(i)*75}`).join(' ');
 $('#signal').innerHTML=`<rect x="${35+patch*30.5}" y="20" width="30.5" height="170" fill="#edf0e5"/><g stroke="#e0e5dc"><path d="M35 40H645M35 110H645M35 180H645"/>${Array.from({length:21},(_,i)=>`<path d="M${35+i*30.5} 20V190" stroke-dasharray="2 4"/>`).join('')}</g><path d="${path(signal)}" fill="none" stroke="#153c35" stroke-width="2.5"/><path d="${path(reconstructed)}" fill="none" stroke="#bb592e" stroke-width="2" stroke-dasharray="${key==='continuous'?'4 5':'none'}"/><g fill="#637064" font-size="10" font-family="monospace"><text x="35" y="214">0 s</text><text x="324" y="214">1 s</text><text x="621" y="214">2 s</text><text x="35" y="12">illustrative leg angle · arbitrary units</text></g>`;
 $('#patches').innerHTML=Array.from({length:20},(_,i)=>`<span class="${i===patch?'active':''}"></span>`).join('');
}
$('#method').addEventListener('change',renderLab); $('#scrub').addEventListener('input',renderLab); renderLab();
const labels={continuous:'Continuous',linear29:'Linear29',body9_raw:'RVQ + body9',body9_smooth:'+ smoothing',body9_leg12:'+ leg12',body9_smooth_leg12:'+ smoothing + leg12',body9_legoracle:'+ original legs (oracle)',body9_smooth_legoracle:'+ smooth + original legs'};
const chartMethods=['continuous','linear29','body9_raw','body9_smooth','body9_leg12','body9_smooth_leg12'];
const metricConfig={
 passes:{unit:'/18',max:18,note:'Joint qualification = native passage AND fidelity to the original reference. Three edited pairs × two continuations × three perturbations. Correlated development trials, not independent success probabilities.'},
 foot:{unit:'cm',max:12,note:'Mean foot-position reconstruction RMSE over six related continuations, after the 1.2 s entry transition. Ankle-link FK error, not observed slip. Lower is better.'},
 clearance:{unit:'cm',max:1.2,note:'Clearance MAE against the continuous-reference geometry across 643 candidates and four existing pairs. Leg12 leaves these arm/beam clearance scores unchanged despite improving execution.'},
 total_rate:{unit:'bit/s',max:57600,note:'Joint + common root logical rate. The hybrid uses 13,860 bit/s versus Linear29 at 14,680: 5.6% less. Original entry, model/codebook and container costs remain additional; no packed-codec claim.'},
 rate:{unit:'bit/s',max:46400,note:'Logical joint information rate only. Every method additionally retains 11,200 bit/s root state plus original entry, model/codebook and container overhead. Not a packed-file measurement.'}
};
function valueFor(key,metric){
 if(metric==='passes')return evidence.mechanism.methods.find(r=>r.method===key).joint_passes;
 if(metric==='foot')return evidence.foot.summary.find(r=>r.method===key).foot_position_rmse_m*100;
 if(metric==='clearance')return evidence.geometry.summary.find(r=>r.method===key).macro_clearance_mae_m*100;
 return methods[key].rate + (metric==='total_rate'?11200:0);
}
function renderComparison(){
 const metric=$('#metric').value,c=metricConfig[metric];
 $('#comparison').innerHTML=chartMethods.map(key=>{const v=valueFor(key,metric),s=metric==='passes'?`${v}/18`:['rate','total_rate'].includes(metric)?`${v.toLocaleString('en-US')} ${c.unit}`:`${v.toFixed(3)} ${c.unit}`;return `<div class="bar-row ${key==='body9_leg12'?'featured':''}"><span class="bar-label">${labels[key]}</span><div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:${v/c.max*100}%"></div></div><span class="bar-value">${s}</span></div>`;}).join('');
 $('#metric-note').textContent=c.note;
 $('#comparison-table').innerHTML=evidence.mechanism.methods.map(r=>`<tr><th scope="row">${labels[r.method]}</th><td>${r.joint_passes}</td><td>${r.fully_qualified_pairs}</td><td>${valueFor(r.method,'foot').toFixed(3)}</td><td>${valueFor(r.method,'clearance').toFixed(4)}</td><td>${methods[r.method].rate.toLocaleString('en-US')}</td></tr>`).join('');
}
let condition='critical';
const conditions={critical:['The obstacle makes the adjustment useful.','The adjusted motion passes; the alternative fails the registered contact-free passage score.'],relaxed:['Relax the constraint. Both choices work.','The relevant clearance is increased. Both continuations pass all three paired perturbations.'],removed:['Remove the obstacle. Recover the alternative.','Both motions remain executable without the constraining obstacle. This control checks the alternative’s basic capability.'],displaced:['Keep an obstacle. Remove its relevance.','Moving the obstacle away from the decisive region lets both continuations pass. Obstacle presence alone does not explain the preference.']};
function renderScene(){
 const family=$('#family').value,arm=family==='arm03';
 const cell=evidence.decoder.representation_cells_results.find(r=>r.canonical_source_pair_id===family&&r.method==='linear29');
 $('#condition-title').textContent=conditions[condition][0];$('#condition-description').textContent=conditions[condition][1];
 $('#scene-scores').innerHTML=Object.entries(cell.outcomes[condition]).map(([name,n])=>`<div class="score"><span>${name==='duck'?'Duck + bend':name[0].toUpperCase()+name.slice(1)}</span><strong>${n} / 3</strong></div>`).join('');
 const displaced=condition==='displaced',relaxed=condition==='relaxed',removed=condition==='removed';
 let shapes='';
 if(arm){
 const gap=relaxed?145:76,x=displaced?450:275;
 shapes=`<rect x="50" y="72" width="465" height="110" fill="#bb592e" fill-opacity=".08" stroke="#bb592e" stroke-dasharray="5 5"/><rect x="50" y="100" width="465" height="54" fill="#b8cba6" fill-opacity=".6" stroke="#638352"/>${removed?'':`<g fill="#9aab97" stroke="#6c8065"><rect x="${x}" y="25" width="35" height="${displaced?30:102-gap/2}"/><rect x="${x}" y="${displaced?200:127+gap/2}" width="35" height="${displaced?30:102-gap/2}"/></g>`}<path d="M35 127H550" stroke="#153c35" stroke-dasharray="4 5"/><text x="60" y="65">wide envelope</text><text x="60" y="120" fill="#153c35">tuck envelope</text><text x="30" y="246">TOP VIEW · shared progression →</text>`;
 }else{
 const y=relaxed?28:81,x=displaced?440:200;
 shapes=`<path d="M30 220H550" stroke="#819178"/><rect x="165" y="60" width="75" height="160" fill="#bb592e" fill-opacity=".08" stroke="#bb592e" stroke-dasharray="5 5"/><rect x="165" y="110" width="110" height="110" fill="#b8cba6" fill-opacity=".5" stroke="#638352"/>${removed?'':`<rect x="${x}" y="${y}" width="${displaced?75:125}" height="20" fill="#9aab97" stroke="#6c8065"/>`}<path d="M290 200H420" stroke="#153c35" stroke-dasharray="4 5"/><text x="35" y="65">upright</text><text x="35" y="130" fill="#153c35">duck + bend</text><text x="30" y="246">SIDE VIEW · progression → · schematic key poses</text>`;
 }
 $('#scene-diagram').innerHTML=`<g font-family="monospace" font-size="11" fill="#687665">${shapes}<text x="370" y="16">${removed?'no obstacle':displaced?'obstacle displaced':relaxed?'clearance relaxed':'critical constraint'}</text></g>`;
 document.querySelectorAll('[data-condition]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.condition===condition)));
}
const interfaces={
 motion:{title:'A short motion chunk is the exchange format.',status:'Existing codecs are measured; the general chunk API is proposed.',body:'Compare continuous or Linear29 references, a learned temporal codec, and a native motor route. Preserve support, clearance and transitions. Human priors and robot-specific execution remain distinct; part-wise codes must keep whole-body coordination.',schema:'Proposed motion chunk\nembodiment + adapter version\nlocal root + joint/link schema\nclock + duration + incoming state\ncontact intent + validity mask'},
 scene:{title:'Represent what occupies space—and what is unknown.',status:'Primitive geometry exists; learned scene tokens proposed.',body:'Use metric object sets before richer depth, point, or sparse 3D encoders. Preserve the transform from event-relative to world coordinates. A sensor student sees only its available map or observation history.',schema:'Proposed scene interface\nshape + position + orientation\ndimensions + coordinate frame\nobserved / empty / unknown\nexact geometry for verification'},
 relation:{title:'Encode why a choice changes with the scene.',status:'Intervention labels exist; learned relation tokens proposed.',body:'Body part, critical interval, clearance change and supported alternatives can supervise representations. Future-derived relations stay in the training view. A deployed relation predictor must operate causally.',schema:'Relation supervision\nbody part + interval\nscene intervention\nmeasured outcomes by behavior\nvalidity + uncertainty'},
 motor:{title:'The native motor route is a strong comparator.',status:'64D decoder inputs recorded; causal predictor and portability unproved.',body:'The recorder stores floating-point motor vectors. SONIC uses quantization in its published design; audit the pinned encoder and config before assigning a native coding rate. A new checkpoint can change token meaning even at the same dimension.',schema:'Motor contract\ncheckpoint + quantizer + normalization\njoint order + action scale\ncausal decoder history + clock\nvalidated 64D motor input'},
 feedback:{title:'An agent needs measured completion and failure.',status:'Proposed agent interface; complete-task policy not implemented here.',body:'Report progress, active, blocked, replan, unsupported or complete. Completion means the declared physical terminal condition. A clip ending does not prove stopping; a stop fallback also requires support from the current state.',schema:'Proposed execution feedback\nrequest + chunk ID + timestamp\nmeasured progress + task components\nobservation validity + failure reason\ncomplete only after the terminal gate'},
 language:{title:'Ground instructions in choices that can be executed.',status:'Synthetic 0.6B interface probe completed; no language controller trained.',body:'The first local probe found valid JSON but lost task fields and incorrect motion choices. Compare full-record relay with selection plus a lossless sidecar. Physical retention and task execution remain separate future gates.',schema:'Proposed language interface\ninstruction → grounded goal\nobserved scene + constraints\ncausal behavior policy\nvalidated motor execution'}
};
function renderInterface(key){const d=interfaces[key];$('#interface-detail').innerHTML=`<div><h3>${d.title}</h3><p>${d.body}</p><p><strong>${d.status}</strong></p></div><code>${d.schema}</code>`;document.querySelectorAll('[data-interface]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.interface===key)));}
renderInterface('motion');
$('#metric').addEventListener('change',()=>{if(evidence)renderComparison();});
$('#family').addEventListener('change',()=>{if(evidence)renderScene();});
for(const button of document.querySelectorAll('[data-condition]'))button.addEventListener('click',()=>{condition=button.dataset.condition;if(evidence)renderScene();});
for(const button of document.querySelectorAll('[data-interface]'))button.addEventListener('click',()=>renderInterface(button.dataset.interface));
async function loadEvidence(){
 try{
  const names={mechanism:'token_mechanism',geometry:'mechanism_geometry',foot:'foot_reconstruction',decoder:'decoder_execution',acquisition:'carrier_scene',llm:'llm_interface'};
  const entries=await Promise.all(Object.entries(names).map(async([key,file])=>{const r=await fetch(`data/${file}.json`);if(!r.ok)throw Error(`${file}: ${r.status}`);return [key,await r.json()];}));
  evidence=Object.fromEntries(entries);renderLab();renderComparison();renderScene();renderDecision(selectedDecision);renderProbe(probeRoute);
  const followup=evidence.acquisition.fixed_wide_tuck_followup;
  const statusText={prepared_waiting_resources:'The six fixed wide/tuck preflights are prepared and waiting for the registered resource gate.',deferred_resources:'The six fixed wide/tuck preflights are prepared. The registered resource wait expired without a launch; no additional episodes were consumed.',running:'The fixed wide/tuck preflight has launched; qualification is not yet established.',completed_pending_audit:'The fixed wide/tuck preflight completed; qualification is awaiting audit.',infrastructure_failure:'The fixed wide/tuck launch failed. Scheduled attempts are retained; no automatic retry is authorized.',qualified:'The fixed wide/tuck pair passed all six preflights. Obstacle qualification remains a separate gate.',qualification_failed:'The fixed wide/tuck pair did not pass every preflight. It is not admitted to obstacle acquisition.'};
  $('#acquisition-status').textContent=statusText[followup.status]||'Consult the recorded follow-up status.';
 }catch(error){$('#comparison').innerHTML='<p class="data-error">Result data could not load. Reload this page or use the linked source reports.</p>';$('#scene-scores').textContent='Recorded outcomes unavailable; consult the source report.';$('#probe-detail').textContent='LLM probe data unavailable; consult the linked report.';console.error('Evidence load failed:',error);}
}
loadEvidence();

// A decision guide: measured evidence and future tests are kept in separate fields.
let selectedDecision='execution';
const decisions={
 execution:{title:'Both reference routes finish after public selection.',evidence:'Supplied-reference pilot: 4/4 per method; same-phase handoffs: 8/8. New known-map selector: 2/2 per method from reset. One familiar ancestry; the full continuous planning bank remains in both arms.',question:'Does this support survive new beam placements while the planner and codec stay fixed?',test:'Register fixed forward/backward beam shifts and a shared clear control. Preserve all outcomes and compare continuous versus Linear29. Incoming-state, velocity and disturbance variation remain separate conditions.',pivot:'If both routes fail, inspect obstacle-relative timing and library support first. If only Linear29 fails, diagnose representation loss. Keep the simple baseline until a more complex codec earns a task or learning benefit.'},
 choice:{title:'A useful adjustment may still need no learned selector.',evidence:'Three of five canonical edited pairs pass every intervention panel. No navigation student has been trained here.',question:'Does scene context change the best complete behavior under a declared task cost?',test:'Compare the scene-conditioned planner with conservative crouch with recovery/stop, ordinary walking and a full-body geometry rule.',pivot:'If one constant behavior solves everything at comparable cost, broaden the task choices or keep the simpler controller.'},
 transfer:{title:'Generalization needs a named axis and new evidence.',evidence:'Canonical acquisition spans three source groups. Representation repeats add zero independent pairs.',question:'Does the representation help on new motion ancestry, layouts, incoming states or combinations?',test:'Freeze whole-group and scene-first splits. Compare two output interfaces using the same learner, data and backend.',pivot:'If only familiar replay improves, retain a development claim. If the new codec has no useful task/cost advantage, keep the baseline.'},
 perception:{title:'The robot must see enough, early enough, to choose.',evidence:'Current actor records assume a complete known map and exact localization. Sensor-based traversal is not established here.',question:'Can the causal sensor history support a choice before its last viable execution time?',test:'Replace the known map with depth/LiDAR, explicit unknown space and memory; test ceiling occlusion and latency.',pivot:'If observations cannot distinguish the choices in time, improve sensing or a qualified inspect/replan behavior before more imitation.'}
};
function renderDecision(key){
 selectedDecision=key;const d=decisions[key];
 $('#decision-detail').innerHTML=`<div><span class="stage-label">CURRENT EVIDENCE</span><h3>${d.title}</h3><p>${d.evidence}</p></div><div><span class="stage-label">PROPOSED DISCRIMINATING TEST</span><h4>${d.question}</h4><p>${d.test}</p><p class="decision-rule"><strong>Change course when:</strong> ${d.pivot}</p></div>`;
 document.querySelectorAll('[data-decision]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.decision===key)));
}
for(const button of document.querySelectorAll('[data-decision]'))button.addEventListener('click',()=>renderDecision(button.dataset.decision));
renderDecision(selectedDecision);

// Recorded synthetic language-interface evidence, distinct from robot outcomes.
let probeRoute='relay';
function renderProbe(route){
 probeRoute=route;if(!evidence?.llm)return;
 const model=evidence.llm.model_summary[route],rule=evidence.llm.rule_summary[route];
 const relay=route==='relay';
 $('#probe-detail').innerHTML=`<div><span class="stage-label">QWEN3-0.6B · ${relay?'FULL RECORD':'ID + SIDECAR'}</span><h3>${model.interface_success} / ${model.completed} interface successes</h3><p>Valid JSON: ${model.json_valid}/${model.completed}. Correct choices: ${model.choice_correct}/${model.completed}. No-LLM rule baseline: ${rule.interface_success}/${rule.completed}.</p><p>${relay?'Task fields survived intact in 0/12. Valid JSON concealed missing task and motion content.':'The wrapper preserved the selected record in 12/12. The model chose hold in every state, so only the two hold cases passed.'}</p></div><div><span class="stage-label">INTERPRETATION · SYNTHETIC ONLY</span><h3>${relay?'Copying and choosing are separate failures.':'Exact numbers can accompany a wrong choice.'}</h3><p>${relay?'Candidate order, IDs and instruction wording changed together. Responses are consistent with position bias, but this probe cannot isolate the cause.':'Sidecar integrity belongs to deterministic code, not to the LLM. Unknown geometry and unsupported entry states still require correct rejection.'}</p><p class="decision-rule">Next: a separately registered compact interface and 1.7B comparison. Real-motion retention and physical execution remain untested.</p></div>`;
 document.querySelectorAll('[data-probe]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.probe===route)));
}
for(const button of document.querySelectorAll('[data-probe]'))button.addEventListener('click',()=>renderProbe(button.dataset.probe));
