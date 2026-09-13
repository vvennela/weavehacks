(()=>{
const $=id=>document.getElementById(id), esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=0)=>Number.isFinite(v)?v.toLocaleString(undefined,{maximumFractionDigits:d}):'—';
let trials=[],selected=[],shown=[];
const page=({'/lab/performance':'performance','/lab/models':'models','/lab/trials':'trials'})[location.pathname.replace(/\/$/,'')]||'overview';
const pageInfo={overview:['Overview','Metrics overview','A clear view of performance, resources, and the latest recorded decisions.'],performance:['Performance','Performance metrics','Compare p95 latency and trial outcomes across your saved runs.'],models:['Models','Model performance','Inspect the best quality-valid solo configurations and their measured results.'],trials:['Trial ledger','Every decision, recorded','Search trials, investigate rollbacks, and export the evidence.']}[page];
document.title=pageInfo[0]+' — Sera';document.querySelector('h1').textContent=pageInfo[1];document.querySelector('.subtitle').textContent=pageInfo[2]+' This page reads a saved ledger, not a live demo feed. Use the notebook report or Weave trace for the current run.';document.querySelector('.breadcrumb').textContent='/ '+pageInfo[0];
document.querySelectorAll('[data-pages]').forEach(section=>section.hidden=!section.dataset.pages.split(' ').includes(page));
document.querySelectorAll('.sidebar nav a').forEach(link=>{const active=link.getAttribute('href')===(page==='overview'?'/lab':'/lab/'+page);link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page')});
let feedbackTimer;
function feedback(message){clearTimeout(feedbackTimer);$('feedback').className='notice success';$('feedback').textContent='✓ '+message;$('feedback').hidden=false;feedbackTimer=setTimeout(()=>$('feedback').hidden=true,6000)}

/* Provenance. A trial measured on real hardware and a trial produced by the analytic
   simulator never carry the same label, and nothing in this file averages the two. */
const LIVE=r=>!!r&&r.substrate==='vllm';
const srcKey=r=>LIVE(r)?'live':'sim';
const srcName=r=>LIVE(r)?'Measured GPU':'Simulator';
const srcHint=r=>LIVE(r)?'Measured on real GPU hardware through vLLM (substrate: vllm).':'Analytic simulator output (substrate: '+((r&&r.substrate)||'unknown')+'). Not a measured result.';
const srcTag=r=>`<span class="source-tag ${srcKey(r)}" title="${esc(srcHint(r))}"><i aria-hidden="true"></i>${srcName(r)}</span>`;
/* Live rows carry no top-level metrics: every number lives inside measurement, which is
   null on a failed trial. Read defensively and never turn a missing number into a zero. */
const mval=(r,key)=>{const m=r&&r.measurement,v=m?m[key]:undefined;return Number.isFinite(v)?v:NaN};
const gated=r=>Number.isFinite(r.quality_score)&&Number.isFinite(r.quality_floor);
const qualityPass=r=>!gated(r)||r.quality_score>=r.quality_floor;
/* A headline winner was accepted, actually measured, and cleared its own quality floor.
   A fast trial that failed its gate is not a winner. */
const validWinner=r=>r.verdict==='accepted'&&Number.isFinite(mval(r,'p95_latency_ms'))&&qualityPass(r);
const bestOf=rows=>rows.filter(validWinner).reduce((a,b)=>!a||mval(b,'p95_latency_ms')<mval(a,'p95_latency_ms')?b:a,null);
const label=v=>String(v||'baseline').replaceAll('_',' ');
const lever=v=>v?String(v).replaceAll('_',' '):'reference';

function notifications(){
 const accepted=selected.filter(r=>r.verdict==='accepted').length;
 const reverted=selected.filter(r=>r.verdict.startsWith('reverted')).length;
 const failed=selected.filter(r=>r.verdict==='failed').length;
 const live=selected.filter(LIVE).length, sim=selected.length-live;
 const notices=[];
 if(live&&sim)notices.push(['warning','!',`Mixed sources · ${live} live GPU, ${sim} simulator`,'Measured GPU trials and analytic simulator trials are listed together. They are not comparable and are never combined into one number. Filter by source to read one at a time.']);
 else if(live)notices.push(['success','●',`${live} live GPU trial${live===1?'':'s'}`,'Every trial in this selection was measured on real GPU hardware through vLLM.']);
 if(failed)notices.push(['danger','!',`${failed} trial${failed===1?'':'s'} failed`,'Recorded execution failures require investigation. A failed trial has no measurement.']);
 if(reverted)notices.push(['danger','!',`${reverted} configuration${reverted===1?' was':'s were'} reverted`,'Latency or quality gates rejected these trials. Review the recorded evidence.']);
 if(accepted)notices.push(['success','✓',`${accepted} trial${accepted===1?'':'s'} accepted`,'These recorded configurations passed their trial gates.']);
 if(!selected.length)notices.push(['warning','!','No trials in this selection','Choose another model, phase, or source, or refresh after a run has completed.']);
 $('notifications').innerHTML=notices.map(([kind,icon,title,body])=>`<article class="notice ${kind}"><span class="notice-icon" aria-hidden="true">${icon}</span><div><strong>${esc(title)}</strong><p>${esc(body)}</p></div>${kind==='danger'?'<a href="/lab/trials?outcome='+ (title.includes('failed')?'failed':'reverted') +'">Review trials →</a>':''}</article>`).join('');
}

function metric(title,value,unit,note){return `<article class="metric"><div class="metric-label">${title}</div><div class="metric-value">${value} <small>${unit}</small></div><div class="metric-note">${note}</div></article>`}
function render(){
const src=$('source-filter')?$('source-filter').value:'all';
selected=trials.filter(r=>($('model-filter').value==='all'||r.models.includes($('model-filter').value))&&($('phase-filter').value==='all'||String(r.phase)===$('phase-filter').value)&&(src==='all'||srcKey(r)===src));
notifications();
const measured=selected.filter(r=>Number.isFinite(mval(r,'p95_latency_ms')));
const accepted=selected.filter(r=>r.verdict==='accepted');
const live=selected.filter(LIVE).length, sim=selected.length-live;
/* Headline: the best quality-valid configuration, with latency, throughput and memory all
   read from that same trial rather than from three unrelated ones. */
const best=bestOf(selected), bestP95=best?mval(best,'p95_latency_ms'):NaN;
const skipped=measured.filter(r=>!validWinner(r)&&mval(r,'p95_latency_ms')<bestP95).length;
const bound=best?`${srcTag(best)}<span class="metric-trial">${esc(best.trial_id)}</span>`:'';
$('metrics').innerHTML=metric('Best quality-valid p95',best?num(bestP95):'—','ms',best?`${bound}Quality ${num(best.quality_score,3)} ≥ floor ${num(best.quality_floor,3)}${skipped?` · ${skipped} faster trial${skipped===1?'':'s'} excluded for failing a gate`:''}`:'No accepted trial in this selection cleared its quality floor. A rejected trial is never promoted to a headline result.')
+metric('Throughput at that setting',best?num(mval(best,'throughput_rps'),2):'—','req/s',best?`${bound}Same trial as the headline result`:'Awaiting a quality-valid trial')
+metric('Memory at that setting',best?num(mval(best,'footprint_gb'),2):'—','GB',best?`${bound}Same trial as the headline result`:'Awaiting a quality-valid trial')
+metric('Accepted trials',accepted.length,'/ '+selected.length,`${selected.length?Math.round(accepted.length/selected.length*100):0}% of selected trials accepted${live&&sim?` · ${live} live GPU, ${sim} simulator`:live?' · all live GPU':''}`);
const colors=['var(--mint)','var(--lilac)','#96814b','#547e85'];const models=[...new Set(measured.flatMap(r=>r.models))];
const modelSrc=m=>[...new Set(measured.filter(r=>r.models.includes(m)).map(srcName))].join(' + ');
if(!measured.length){$('latency-chart').innerHTML='<p class="muted">No measurements in this selection.</p>';$('legend').innerHTML='';}else{
const lat=measured.map(r=>mval(r,'p95_latency_ms'));
const max=Math.max(...lat,1)*1.1,W=620,H=215,left=48,right=12,top=15,bottom=28,x=i=>left+i*(W-left-right)/Math.max(measured.length-1,1),y=v=>H-bottom-v/max*(H-top-bottom);
const mark=(cx,cy,fill,isLive,title)=>isLive?`<rect x="${cx-4.4}" y="${cy-4.4}" width="8.8" height="8.8" transform="rotate(45 ${cx} ${cy})" fill="${fill}" stroke="var(--surface)" stroke-width="1.2">${title}</rect>`:`<circle cx="${cx}" cy="${cy}" r="3.5" fill="${fill}">${title}</circle>`;
let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="p95 latency by recorded trial, in milliseconds; diamonds are live GPU trials and circles are simulator trials">`;
for(let i=0;i<5;i++){const v=max*i/4;svg+=`<line x1="${left}" x2="${W-right}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${left-8}" y="${y(v)+3}" text-anchor="end">${num(v/1000,1)}k</text>`}
models.forEach((model,mi)=>{const pts=measured.map((r,i)=>({r,i})).filter(p=>p.r.models.includes(model));svg+=`<polyline fill="none" stroke="${colors[mi%colors.length]}" stroke-width="2" points="${pts.map(p=>`${x(p.i)},${y(mval(p.r,'p95_latency_ms'))}`).join(' ')}"/>`;pts.forEach(p=>svg+=mark(x(p.i),y(mval(p.r,'p95_latency_ms')),colors[mi%colors.length],LIVE(p.r),`<title>${esc(model)} · ${esc(p.r.trial_id)} · ${srcName(p.r)} · ${num(mval(p.r,'p95_latency_ms'))} ms · ${esc(label(p.r.verdict))}</title>`))});
const bi=best?measured.indexOf(best):-1;if(bi>=0)svg+=`<circle cx="${x(bi)}" cy="${y(bestP95)}" r="9" fill="none" stroke="var(--mint)" stroke-width="1.5" opacity=".6"><title>Best quality-valid configuration</title></circle>`;
svg+=`<text x="${left}" y="${H-5}">Trial 1</text><text x="${W-right}" y="${H-5}" text-anchor="end">Trial ${measured.length}</text></svg>`;$('latency-chart').innerHTML=svg;
$('legend').innerHTML=models.map((m,i)=>`<span><i style="background:${colors[i%colors.length]}"></i>${esc(m)} · ${esc(modelSrc(m))}</span>`).join('')+'<span class="legend-shape"><i class="shape-live"></i>Live GPU trial</span><span class="legend-shape"><i class="shape-sim"></i>Simulator trial</span>';}
const counts=new Map();selected.forEach(r=>counts.set(r.verdict,(counts.get(r.verdict)||0)+1));$('outcomes').innerHTML=`<div class="outcome-total">${selected.length}</div><div class="outcome-caption">recorded trials in this selection${live&&sim?` · ${live} live GPU · ${sim} simulator`:live?' · all live GPU':''}</div>`+[...counts].map(([v,n])=>`<div class="outcome-row"><span>${esc(label(v))}</span><strong>${n}</strong></div><div class="bar-track"><i style="width:${100*n/selected.length}%;${v!=='accepted'?'background:var(--danger)':''}"></i></div>`).join('');
const names=[...new Set(selected.flatMap(r=>r.models))];$('model-cards').innerHTML=names.map(name=>{const rows=selected.filter(r=>r.phase===1&&r.models.includes(name));const r=bestOf(rows);if(!r){const any=rows[rows.length-1];return `<article class="model-card"><div class="model-title"><strong>${esc(name)}</strong>${any?srcTag(any):''}</div><p class="muted">No quality-valid solo configuration in this selection.${any&&any.reason?' Last note: '+esc(any.reason):''}</p></article>`}const c=r.config;return `<article class="model-card"><div class="model-title"><strong>${esc(name)}</strong>${srcTag(r)}<span class="badge">Accepted</span></div><div class="model-stats"><div><span>p95 latency · ms</span><strong>${num(mval(r,'p95_latency_ms'))}</strong></div><div><span>Throughput · req/s</span><strong>${num(mval(r,'throughput_rps'),2)}</strong></div><div><span>Memory · GB</span><strong>${num(mval(r,'footprint_gb'),2)}</strong></div></div><div class="model-config">${esc(c.weight_dtype)} weights · ${esc(c.kv_cache_dtype)} KV · TP ${esc(c.tensor_parallel_size)} · lever ${esc(lever(r.lever))}<br>Quality score ${num(r.quality_score,3)} / floor ${num(r.quality_floor,3)} · ${esc(srcName(r))} · ${esc(r.trial_id)}</div></article>`}).join('')||'<p class="muted">No model data available.</p>';renderTable();}
function renderTable(){const q=$('search').value.toLowerCase(),v=$('verdict-filter').value;shown=selected.filter(r=>(v==='all'||(v==='reverted'?r.verdict.startsWith('reverted'):r.verdict===v))&&[r.trial_id,...r.models,r.proposing_specialist,r.lever,r.substrate,srcName(r),r.reason].join(' ').toLowerCase().includes(q)).slice().reverse();$('trial-count').textContent=shown.length;$('empty').hidden=shown.length>0;$('trial-rows').innerHTML=shown.map((r,i)=>`<tr><td><button class="trial-link" data-trial="${i}">${esc(r.models.join(' + '))}<small>${esc(r.trial_id)}</small></button></td><td>${srcTag(r)}</td><td>${esc(label(r.proposing_specialist))}</td><td>${esc(lever(r.lever))}</td><td>${r.phase===1?'Solo':'Joint'}</td><td>${num(mval(r,'p95_latency_ms'))} ms</td><td>${num(mval(r,'throughput_rps'),2)} req/s</td><td>${num(mval(r,'footprint_gb'),2)} GB</td><td><span class="badge ${r.verdict==='accepted'?'':'danger'}">${esc(label(r.verdict))}</span></td></tr>`).join('');}
$('trial-rows').addEventListener('click',e=>{const b=e.target.closest('[data-trial]');if(!b)return;const r=shown[Number(b.dataset.trial)];const q=gated(r)?`${num(r.quality_score,3)} against a floor of ${num(r.quality_floor,3)} — ${qualityPass(r)?'passed':'failed'}`:'No quality score recorded for this trial.';
$('detail-content').innerHTML=`<p><strong>${esc(r.models.join(' + '))}</strong><br><span class="muted">${esc(r.trial_id)}</span></p><p class="detail-tags">${srcTag(r)}<span class="badge ${r.verdict==='accepted'?'':'danger'}">${esc(label(r.verdict))}</span></p><p class="muted detail-source">${esc(srcHint(r))}</p><h3>Decision</h3><p>Lever: <strong>${esc(lever(r.lever))}</strong> · proposed by ${esc(label(r.proposing_specialist))}<br>${esc(r.reason||'No additional decision note recorded.')}</p><h3>Quality gate</h3><p>${esc(q)}</p><h3>Configuration</h3><pre>${esc(JSON.stringify(r.config,null,2))}</pre><h3>Measurements</h3>${r.measurement?`<pre>${esc(JSON.stringify(r.measurement,null,2))}</pre>`:'<p class="muted">No measurement was recorded for this trial. Missing numbers are shown as — and are never treated as zero.</p>'}<p class="muted">Source: ${esc(srcName(r))} (substrate ${esc(r.substrate)}) · ${new Date(r.timestamp*1000).toLocaleString()}</p>`;$('trial-detail').showModal()});
$('close-detail').addEventListener('click',()=>$('trial-detail').close());['model-filter','phase-filter','source-filter'].forEach(id=>{const el=$(id);if(el)el.addEventListener('change',render)});$('search').addEventListener('input',renderTable);$('verdict-filter').addEventListener('change',renderTable);
$('export').addEventListener('click',()=>{const rows=[['trial_id','models','source','substrate','specialist','lever','phase','p95_latency_ms','throughput_rps','footprint_gb','quality_score','quality_floor','quality_valid','verdict'],...shown.map(r=>[r.trial_id,r.models.join(' + '),srcName(r),r.substrate,r.proposing_specialist||'baseline',r.lever||'reference',r.phase,r.measurement?.p95_latency_ms,r.measurement?.throughput_rps,r.measurement?.footprint_gb,r.quality_score,r.quality_floor,validWinner(r),r.verdict])];const csv=rows.map(row=>row.map(v=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"').join(',')).join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='sera-trials.csv';a.click();URL.revokeObjectURL(url);feedback('CSV export prepared for '+shown.length+' trials.')});
async function load(manual=false){const button=$('refresh');button.disabled=true;button.textContent='Refreshing…';$('error').hidden=true;try{const response=await fetch('/api/metrics');if(response.status===401){location.assign('/sign-in');return}const data=await response.json();if(!response.ok)throw new Error(data.error);trials=Array.isArray(data.trials)?data.trials.filter(r=>r&&Array.isArray(r.models)):[];const current=$('model-filter').value;$('model-filter').innerHTML='<option value="all">All models</option>'+[...new Set(trials.flatMap(r=>r.models))].map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join('');if([...$('model-filter').options].some(o=>o.value===current))$('model-filter').value=current;
const live=trials.filter(LIVE).length, sim=trials.length-live;
const parts=[];if(live)parts.push(`${live} live GPU trial${live===1?'':'s'} (vLLM)`);if(sim)parts.push(`${sim} simulator trial${sim===1?'':'s'}`);
$('source-status').innerHTML=trials.length?parts.join(' · ')+' · '+esc(data.source||'saved ledger'):'No run data yet';
$('source-status').className=live&&sim?'mixed':live?'live':'';
$('updated').textContent=data.updated?'Saved ledger updated '+new Date(data.updated*1000).toLocaleString():'No saved ledger available';render();if(manual)feedback('Saved ledger reloaded. This does not import demo runs.')}catch(e){$('error').textContent='Unable to refresh metrics. '+(e.message||'Please try again.');$('error').hidden=false;$('source-status').textContent='Metrics unavailable'}finally{button.disabled=false;button.textContent='↻  Refresh data'}}
document.querySelectorAll('.sidebar nav a').forEach(link=>link.addEventListener('click',()=>{document.querySelectorAll('.sidebar nav a').forEach(a=>a.classList.toggle('active',a===link));}));
const params=new URLSearchParams(location.search);const outcome=params.get('outcome');if(['accepted','reverted','failed'].includes(outcome))$('verdict-filter').value=outcome;
const wantSource=params.get('source');if($('source-filter')&&['live','sim'].includes(wantSource))$('source-filter').value=wantSource;
$('refresh').addEventListener('click',()=>load(true));load();
})();
