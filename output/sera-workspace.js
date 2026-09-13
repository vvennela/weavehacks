(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const path = location.pathname.replace(/\/$/, '');
  const view = path === '/notebook' ? 'workflow' : path === '/lab/trials' ? 'trials' : 'overview';
  const pages = {
    overview: ['Demo overview', 'The baseline, the selected configuration, and the measured improvement.'],
    workflow: ['The agent loop', 'Watch the recorded experiment or open the notebook to run your own.'],
    trials: ['Every experiment, recorded', 'Agent proposals, measured outcomes, and the decisions behind this demo.'],
  };
  const names = {baseline: 'Baseline', 'trial-1': 'Prefix caching', 'trial-2': 'Graph execution', 'trial-3': 'Prefix caching + graphs'};
  const roles = {scheduling: 'Scheduling', memory_context: 'Memory / context', output_quality: 'Output quality'};
  const number = value => Number.isFinite(value) ? value.toLocaleString(undefined, {maximumFractionDigits: 2}) : 'Not recorded';
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function section(parent, title, text) {
    parent.append(element('h3', title), element('p', text || 'Not recorded'));
  }
  $('page-title').textContent = pages[view][0];
  $('page-description').textContent = pages[view][1];
  document.title = pages[view][0] + ' — Sera';
  document.querySelector('.breadcrumb').textContent = '/ ' + pages[view][0];
  document.querySelectorAll('[data-page]').forEach(node => { node.hidden = node.dataset.page !== view; });
  document.querySelectorAll('[data-view]').forEach(node => {
    const active = node.dataset.view === view;
    node.classList.toggle('active', active);
    if (active) node.setAttribute('aria-current', 'page');
  });
  let notebookRequested = false;
  async function loadNotebook() {
    if (notebookRequested) return;
    notebookRequested = true;
    try {
      const response = await fetch('/api/config');
      if (!response.ok) throw new Error('Notebook connection unavailable.');
      const config = await response.json();
      if (!config.molab_url) throw new Error('The live demo embed is not configured here. Open your own clone above.');
      const url = new URL(config.molab_url);
      // The published Molab /app export is not the live GPU notebook.
      if (url.protocol !== 'https:' || url.hostname === 'molab.marimo.io' || url.username || url.password || url.search || url.hash) {
        throw new Error('The live demo embed is not configured here. Open your own clone above.');
      }
      $('live-notebook').src = url.href;
      $('live-notebook').hidden = false;
      $('notebook-status').textContent = 'Opening the configured hosted notebook. Use your own clone for API keys.';
    } catch (error) { $('notebook-status').textContent = error.message; }
  }
  function selectTab(selected) {
    for (const name of ['replay', 'notebook']) {
      const active = name === selected;
      $(name + '-tab').setAttribute('aria-selected', String(active));
      $(name + '-tab').tabIndex = active ? 0 : -1;
      $(name + '-panel').hidden = !active;
    }
    if (selected === 'notebook') {
      $('demo-player').dispatchEvent(new Event('demo:pause'));
      loadNotebook();
    }
  }
  for (const name of ['replay', 'notebook']) {
    $(name + '-tab').addEventListener('click', () => selectTab(name));
    $(name + '-tab').addEventListener('keydown', event => {
      if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const next = event.key === 'Home' ? 'replay' : event.key === 'End' ? 'notebook' : name === 'replay' ? 'notebook' : 'replay';
        selectTab(next); $(next + '-tab').focus();
      }
    });
  }
  function outcome(trial, data) {
    return trial.trial_id === 'baseline' ? 'Reference' : trial.trial_id === data.decision.selected ? 'Selected winner' : 'Measured · not selected';
  }
  function showTrial(trial, data) {
    $('detail-title').textContent = names[trial.trial_id] || trial.trial_id;
    const content = $('detail-content'); content.replaceChildren();
    section(content, 'Measured result', `${number(trial.reduced.p95_latency_ms)} ms p95 · ${number(trial.reduced.output_tokens_per_second)} output tokens/s · ${outcome(trial, data)}`);
    section(content, 'Answer checks', `${trial.task_quality.per_prompt.filter(p => p.score === 1).length} / ${trial.task_quality.per_prompt.length} passed · floor ${trial.task_quality.floor * 100}% · ${trial.reduced.generation_errors} generation errors`);
    const round = data.rounds.find(item => item.trial_ids.includes(trial.trial_id));
    if (round) {
      section(content, 'Arbiter decision · round ' + round.round, round.arbiter.reason);
      for (const agent of round.proposals) {
        const detail = element('details');
        detail.append(element('summary', roles[agent.investigator] || agent.investigator));
        const proposal = agent.proposal || {};
        section(detail, 'Recorded proposal after review', proposal.changed_lever ? `${proposal.changed_lever} → ${JSON.stringify(proposal.proposed_value)}` : proposal.action);
        section(detail, 'Reason', proposal.reason);
        section(detail, 'Prediction', proposal.predicted_metric_change);
        section(detail, 'What would refute it', proposal.falsification_condition);
        const reads = round.reads.filter(read => read.investigator === agent.investigator);
        section(detail, 'Weave inspections', reads.map(read => `${read.query}: ${read.returned} returned records`).join('; '));
        content.append(detail);
      }
    } else section(content, 'Reference configuration', 'Measured before the three investigator rounds.');
    content.append(element('h3', 'Configuration'), element('pre', JSON.stringify(trial.configuration, null, 2)));
    $('trial-detail').showModal();
  }
  $('close-detail').addEventListener('click', () => $('trial-detail').close());
  async function loadDemo() {
    try {
      const response = await fetch('/demo-run.json');
      if (!response.ok) throw new Error('Could not load the saved demo record.');
      const data = await response.json();
      const baseline = data.trials.find(trial => trial.trial_id === 'baseline');
      const winner = data.trials.find(trial => trial.trial_id === data.decision.selected);
      if (!baseline || !winner || data.source !== 'measured GPU recording') throw new Error('The demo record is incomplete.');
      $('run-label').textContent = `${data.run_id} · ${data.source} · ${data.rounds.length} search rounds`;
      const gain = (1 - winner.reduced.p95_latency_ms / baseline.reduced.p95_latency_ms) * 100;
      const metrics = [
        ['Lower p95 latency', number(gain) + '%', 'Selected configuration versus this run’s baseline'],
        ['Baseline → winner', number(baseline.reduced.p95_latency_ms) + ' → ' + number(winner.reduced.p95_latency_ms), 'Milliseconds · worst p95 across concurrency 1/2/4/8'],
        ['Answer checks', winner.task_quality.per_prompt.filter(p => p.score === 1).length + ' / ' + winner.task_quality.per_prompt.length, 'Exact-answer JSON tasks · 99% floor'],
        ['Search rounds', String(data.rounds.length), 'Three investigators per round · one selected experiment'],
      ];
      for (const [label, value, note] of metrics) {
        const card = element('article', undefined, 'metric');
        card.append(element('div', label, 'metric-label'), element('div', value, 'metric-value'), element('div', note, 'metric-note'));
        $('demo-metrics').append(card);
      }
      const maximum = Math.max(...data.trials.map(trial => trial.reduced.p95_latency_ms));
      for (const trial of data.trials) {
        const bar = element('div'), title = element('p');
        title.append(element('span', names[trial.trial_id]), element('strong', number(trial.reduced.p95_latency_ms) + ' ms'));
        const track = element('div', undefined, 'bar-track'), fill = element('i');
        fill.style.width = trial.reduced.p95_latency_ms / maximum * 100 + '%'; track.append(fill); bar.append(title, track); $('demo-bars').append(bar);
        const row = element('tr'), cell = element('td'), button = element('button', names[trial.trial_id], 'trial-link');
        button.addEventListener('click', () => showTrial(trial, data)); cell.append(button); row.append(cell);
        for (const value of [number(trial.reduced.p95_latency_ms) + ' ms', number(trial.reduced.output_tokens_per_second), trial.task_quality.per_prompt.filter(p => p.score === 1).length + ' / ' + trial.task_quality.per_prompt.length, outcome(trial, data)]) row.append(element('td', value));
        $('demo-trials').append(row);
      }
      const trace = new URL(data.weave_url);
      if (trace.protocol === 'https:' && trace.hostname === 'wandb.ai') document.querySelectorAll('.run-trace').forEach(link => { link.href = trace.href; link.hidden = false; });
      const exceptionCount = Array.isArray(data.weave_exceptions) ? data.weave_exceptions.length : data.weave_exceptions;
      $('weave-summary').textContent = `${data.weave_calls} recorded Weave calls · ${exceptionCount} call exceptions. Calls are not GPU trial counts.`;
    } catch (error) { $('error').textContent = error.message; $('error').hidden = false; }
  }
  loadDemo();
})();
