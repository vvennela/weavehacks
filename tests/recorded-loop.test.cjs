// Run with: node --test tests/recorded-loop.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function openReplay() {
  const html = fs.readFileSync(path.join(__dirname, '../demos/recorded-loop.html'), 'utf8');
  const nodes = new Map();
  const document = { getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, { innerHTML: '', textContent: '', value: '', style: {}, setAttribute() {}, addEventListener(type, handler) { this[type] = handler; } });
    return nodes.get(id);
  }};
  const context = vm.createContext({ document, performance: { now: () => 0 }, requestAnimationFrame() {}, matchMedia: () => ({ matches: false }) });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  return { context, nodes, html, run: code => vm.runInContext(code, context) };
}

test('three rounds expose revisions, one selected experiment, and measured outcomes', () => {
  const replay = openReplay();
  assert.equal(replay.run('rounds.length'), 3);
  assert.equal(replay.run('rounds[0].agents[1].initial'), 'GPU memory allocation → 85%');
  assert.equal(replay.run('rounds[0].agents[1].final'), 'Enable prefix caching');
  assert.equal(replay.run('rounds[1].selected'), 0);
  assert.equal(replay.run('rounds[2].selected'), 1);
  assert.equal(replay.run('measurements[3].value'), 618.5879460026626);
  assert.equal(replay.run('totalSeconds'), 838.1639053689978);
  for (let round = 0; round < 3; round++) {
    replay.run(`seek(stages.find(stage => stage.round === ${round} && stage.phase === 'result').at)`);
    assert.match(replay.nodes.get('detail').innerHTML, /8\/8/);
  }
});

test('play, pause, restart, speed and scrub operate offline', () => {
  const replay = openReplay();
  assert.equal(replay.run('speed'), 8);
  replay.nodes.get('play').click();
  assert.equal(replay.run('playing'), true);
  replay.run('tick(1000)');
  assert.equal(replay.run('elapsed'), 8);
  replay.nodes.get('play').click();
  assert.equal(replay.run('playing'), false);
  replay.nodes.get('scrub').input({ target: { value: '838.1639053689978' } });
  assert.match(replay.nodes.get('headline').textContent, /Runner verified/);
  assert.equal(replay.run('playing'), false);
  replay.nodes.get('speed').change({ target: { value: '16' } });
  assert.equal(replay.run('speed'), 16);
  replay.nodes.get('restart').click();
  assert.equal(replay.run('elapsed'), 0);
  assert.doesNotMatch(replay.html, /<script[^>]+src=|fetch\(|XMLHttpRequest|WebSocket/);
  assert.match(replay.html, /Schematic pacing/);
});
