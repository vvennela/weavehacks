(() => {
const root = document.getElementById('demo-player');
if (!root || root.closest('[data-page]').hidden) return;
'use strict';
const totalSeconds = 838.1639053689978;
const measurements = [
  {name:'Baseline', value:771.0464070005401},
  {name:'Prefix cache', value:624.7854280009051},
  {name:'Graphs only', value:764.0717579997727},
  {name:'Cache + graphs', value:618.5879460026626}
];
const rounds = [
  {selected:0, experiment:'Enable prefix caching on baseline', agents:[
    {initial:'Enable prefix caching', final:'Enable prefix caching', feedback:'Repeated warmed prompts support a reuse test. Memory pressure is not established; defer the graph idea.'},
    {initial:'GPU memory allocation → 85%', final:'Enable prefix caching', feedback:'Accept A’s reuse hypothesis. Withdraw the allocation change: zero preemptions and no observed memory constraint.'},
    {initial:'Enable graph execution', final:'Enable graph execution', feedback:'Prefix reuse is plausible. Keep the graph hypothesis for a test; launch overhead is not proven.'}
  ], decision:'Select Agent A. Agent B now proposes the same cache change; one trial tests it. Defer Agent C’s graph proposal.', result:'624.785 ms · <strong>18.969% lower latency than baseline.</strong> Quality: 8/8. The gain clears the 5% progress threshold. Feed the measured cache result into round 2.'},
  {selected:0, experiment:'Enable graph execution on baseline (no prefix cache)', agents:[
    {initial:'Disable chunked prefill', final:'Enable graph execution', feedback:'Accept the peers’ graph test. Small queue time gives little support for a scheduling bottleneck.'},
    {initial:'Enable graph execution', final:'Enable graph execution', feedback:'Test execution strategy with a single change. Graph compatibility and memory use still need measurement.'},
    {initial:'Enable graph execution', final:'Enable graph execution', feedback:'Accept the graph experiment, without claiming its mechanism is proven. Test on baseline to isolate the change.'}
  ], decision:'Select Agent A’s graph-only proposal. All three final proposals describe the same experiment, so they do not need separate GPU trials.', result:'764.072 ms · <strong>Misses the latency target.</strong> Only 0.905% below baseline; slower than the cache result. Quality: 8/8, no generation errors. First round without qualifying progress → run one confirmation round.'},
  {selected:1, experiment:'Enable graph execution on trial-1 (retain prefix caching)', agents:[
    {initial:'Disable chunked prefill', final:'Disable chunked prefill', feedback:'Keep a distinct scheduling test. Graphs alone gave little gain; a cache interaction remains unmeasured.'},
    {initial:'GPU memory allocation → 85%', final:'Combine prefix caching + graphs', feedback:'Accept C’s interaction test on the best parent. Withdraw allocation reduction: no measured memory constraint.'},
    {initial:'Combine prefix caching + graphs', final:'Combine prefix caching + graphs', feedback:'Keep the measured cache advantage and test the graph interaction. Graph-only results temper the prediction.'}
  ], decision:'Select Agent B. Agent C proposes the same combination. Retain trial-1 prefix caching and change only graph execution; measure the interaction.', result:'618.588 ms · <strong>19.773% lower latency than baseline.</strong> Quality: 8/8. This is the best measured result, but only 0.992% better than the prior best: below the 5% progress threshold. Confirmation completes the plateau stop.'}
];
const steps = ['Inspect','Propose','Peer review','Arbiter','GPU trial','Measure','Stop / return'];
const stages = [
  {at:0, phase:'setup', round:-1, step:0, title:'Check provider and measure baseline'},
  ...rounds.flatMap((round,index) => {
    const start = 170 + index * 180;
    return [
      {at:start, phase:'inspect', step:0, title:'Read evidence together'},
      {at:start+16, phase:'propose', step:1, title:'Three independent proposals'},
      {at:start+43, phase:'review', step:2, title:'Review peers and revise'},
      {at:start+65, phase:'arbiter', step:3, title:'Arbiter selects one experiment'},
      {at:start+82, phase:'gpu', step:4, title:'Run the selected GPU experiment'},
      {at:start+149, phase:'result', step:5, title:'Measure, compare, feed back'}
    ].map(stage => ({...stage, round:index}));
  }),
  {at:710, phase:'stop', round:2, step:6, title:'Plateau + one confirmation → stop'},
  {at:785, phase:'cleanup', round:2, step:6, title:'Return best configuration; verify runner'},
  {at:totalSeconds, phase:'complete', round:2, step:6, title:'Runner verified. GPU cleanup complete.'}
];
let elapsed = 0;
let speed = 8;
let playing = false;
let lastFrame = performance.now();
let lastStage = -1;
const element = id => root.querySelector('#' + id);
function formatTime(seconds) { return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2,'0')}`; }
function seek(seconds) {
  elapsed = Math.max(0, Math.min(totalSeconds, seconds));
  if (elapsed >= totalSeconds) playing = false;
  render();
}
function render() {
  element('play').textContent = playing ? 'Ⅱ Pause' : '▶ Play';
  element('scrub').value = elapsed;
  element('clock').textContent = `${formatTime(elapsed)} / ${formatTime(totalSeconds)}`;
  const stageIndex = stages.findLastIndex(stage => stage.at <= elapsed);
  if (stageIndex === lastStage) return;
  lastStage = stageIndex;
  const stage = stages[stageIndex];
  const round = rounds[Math.max(stage.round,0)];
  const afterReview = ['review','arbiter','gpu','result','stop','cleanup','complete'].includes(stage.phase);
  const showProposal = !['setup','inspect'].includes(stage.phase);
  const hasSelection = ['arbiter','gpu','result','stop','cleanup','complete'].includes(stage.phase);
  element('headline').textContent = stage.title;
  element('round').textContent = stage.round < 0 ? 'SETUP' : `ROUND ${stage.round + 1} / 3${stage.round === 2 ? ' · CONFIRMATION' : ''}`;
  element('flow').innerHTML = steps.map((name,index) => `<div class="step ${index===stage.step?'active':index<stage.step?'done':''}" ${index===stage.step?'aria-current="step"':''}><b>0${index+1}</b>${name}</div>`).join('');
  element('agents').innerHTML = round.agents.map((agent,index) => {
    const selected = hasSelection && index === round.selected;
    const active = ['inspect','propose','review'].includes(stage.phase) || selected;
    const changed = agent.initial !== agent.final;
    return `<article class="agent ${active?'active':''} ${selected?'selected':''}"><h3>Agent ${'ABC'[index]}</h3><div class="role">${['Scheduling','Memory & context','Output quality'][index]}</div><div class="label">${showProposal?'Initial proposal':'Shared evidence'}</div><div class="proposal">${showProposal?agent.initial:stage.round<0?'Waiting for baseline':'Prior trial metrics + latency outliers'}</div>${afterReview?`<div class="label">${changed?'↳ Revised after peer review':'After peer review'}</div><div class="proposal ${changed?'changed':''}">${agent.final}</div><p class="feedback">${agent.feedback}</p>`:''}${selected?'<div class="label changed">Selected for one GPU trial</div>':''}</article>`;
  }).join('');
  let detail;
  if (stage.phase === 'setup') detail = '<strong>Before the search</strong><p>Provider checks passed 34/34 requests. Measure the unchanged model: FP8 weights, BF16 KV cache, eager execution, prefix caching off. Baseline: 771.046 ms, 8/8 quality checks. The baseline appears on the chart when the first round begins.</p>';
  else if (stage.phase === 'inspect') detail = `<strong>Same evidence, three views</strong><p>All three investigators read load metrics and latency outliers in parallel. ${stage.round===0?'The baseline is valid; latency rises with load, but the cause is unknown.':stage.round===1?'Prefix caching improved latency. The next proposals can use that measured result.':'Graphs alone missed the target. The cache result remains the best measured parent.'}</p>`;
  else if (stage.phase === 'propose') detail = '<strong>Parallel proposals are hypotheses</strong><p>Each agent suggests a configuration change and its expected effect. None of these proposals is a GPU result. The agents next see peer proposals and decide what to keep or revise.</p>';
  else if (stage.phase === 'review') detail = '<strong>Peer feedback changes the next decision</strong><p>The cards show recorded initial and final recommendations. Mint text marks a changed recommendation. Feedback is a short paraphrase of each agent’s recorded peer review.</p>';
  else if (stage.phase === 'arbiter') detail = `<strong>${round.experiment}</strong><p>${round.decision}</p>`;
  else if (stage.phase === 'gpu') detail = `<strong>One actual experiment: trial-${stage.round+1}</strong><p>${round.experiment}. The GPU runner loads this configuration, warms the workload, checks quality, and measures the fixed loads. Agents do not run separate GPU trials. The result is revealed next.</p>`;
  else if (stage.phase === 'result') detail = `<strong>Recorded trial-${stage.round+1} outcome</strong><p>${round.result}</p>`;
  else if (stage.phase === 'stop') detail = '<strong>Stop: objective-plateau-confirmed</strong><p>Round 2 made no qualifying progress. Round 3 confirmed the plateau: its 0.992% gain over the prior best stayed below the 5% target. Return the best quality-valid result: cache + graphs.</p>';
  else detail = '<strong>Completed run: cache + graphs selected</strong><p>771.046 → 618.588 ms (19.773% lower latency). The returned runner passed a fresh probe: {"answer": 5}. Cleanup passed; the post-cleanup GPU reading was 0 MiB used. Full invocation, including provider checks: 838.164 seconds.</p>';
  element('detail').innerHTML = detail;
  const revealed = stage.round < 0 ? 0 : ['result','stop','cleanup','complete'].includes(stage.phase) ? stage.round+2 : stage.round+1;
  const best = revealed ? Math.min(...measurements.slice(0,revealed).map(item=>item.value)) : null;
  element('best').innerHTML = best === null ? '— <small>ms</small>' : `${best.toFixed(3)} <small>ms</small>`;
  element('gain').textContent = best === null ? 'Awaiting baseline' : `${((1-best/measurements[0].value)*100).toFixed(3)}% below baseline`;
  element('chart').innerHTML = measurements.map((item,index)=>`<g opacity="${index<revealed?1:0.25}"><text x="0" y="${index*48+12}" fill="var(--muted)" font-size="11">${item.name}</text><rect x="0" y="${index*48+20}" width="${index<revealed?item.value/800*204:8}" height="12" rx="3" fill="${item.value===best?'var(--mint)':'var(--bar)'}"/><text x="265" y="${index*48+30}" text-anchor="end" fill="var(--text)" font-size="11">${index<revealed?item.value.toFixed(1):'—'}</text></g>`).join('');
}
element('play').addEventListener('click', () => { if(elapsed>=totalSeconds) seek(0); playing=!playing; lastFrame=performance.now(); render(); });
element('restart').addEventListener('click', () => { playing=false; seek(0); });
element('speed').addEventListener('change', event => { speed=Number(event.target.value); });
element('scrub').addEventListener('input', event => { seek(Number(event.target.value)); lastFrame=performance.now(); });
function tick(now) { if(playing) seek(elapsed+(now-lastFrame)/1000*speed); lastFrame=now; requestAnimationFrame(tick); }
render();
requestAnimationFrame(tick);


root.addEventListener('demo:pause', () => { playing = false; render(); });
})();
