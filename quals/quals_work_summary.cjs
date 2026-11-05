// Replicata: actual brief/work renderers with work, campaign, Lindy, and unmodeled run fixtures.
// Expectata: work popups report measurements; full chance lines retain probabilities and truthful units.
// Resultata: assertions identify a wrong returned row, measurement value, or hidden variant.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');
const brief = script.match(/  function brief\(run\) \{[\s\S]*?\n  \}/)[0];
const workView = script.match(/  function workView\(box, run\) \{[\s\S]*?\n  \}/)[0];
const chanceLine = html.match(/<p class="progress-chance-line">([\s\S]*?)<\/p>/)[1];
assert.match(chanceLine, /<span data-work-measure="cpu"><b data-chance-spent><\/b> CPU-hours so far\.<\/span>/);
assert.match(chanceLine, /<!-- TODO:[^>]*-->\s*<span data-work-measure="work" hidden>.*data-work-done.*data-work-rate.*<\/span>/);
assert.match(chanceLine, /data-chance-at="6"/);
assert.match(chanceLine, /data-chance-at="24"/);
assert.doesNotMatch(chanceLine, /^<[^>]*hidden/);

function fixture() {
  const fields = Object.fromEntries(['samples', 'done', 'rate', 'source_time'].map(key => [`work-${key}`, [{textContent: ''}, {textContent: ''}]]));
  const eta = {id: 'eta', hidden: true, querySelectorAll: s => (fields[s.slice(6, -1)] || []).slice(0, 1)};
  const cpu = {dataset: {workMeasure: 'cpu'}, hidden: false};
  const measure = {dataset: {workMeasure: 'work'}, hidden: true};
  const chance = {id: 'chance', hidden: false};
  const line = {id: 'chance-line'};
  const box = {
    querySelector: s => ({'[data-work-eta]': eta, '.progress-chance': chance, 'summary h3': {childNodes: ['heading']}, summary: {querySelectorAll: () => []}})[s],
    querySelectorAll: s => ({'[data-work-measure]': [cpu, measure], '[data-work-eta]': [eta], '.progress-chance:not([hidden]) .progress-chance-line': chance.hidden ? [] : [line]})[s] || fields[s.slice(6, -1)] || [],
  };
  return {box, eta, cpu, measure, chance, line, fields};
}
let f = fixture();
const context = {
  template: {content: {firstElementChild: {cloneNode: () => f.box}}},
  document: {createElement: () => ({id: 'heading', append() {}})},
  heading() {}, staleView() {}, chanceChart: (fig, run) => { fig.hidden = !run.chance; },
  dur: x => String(x), tenth: x => x, stamp: t => `stamp:${t}`,
  fill: (el, key, text) => { for (const e of el.querySelectorAll(`[data-${key}]`)) e.textContent = text; },
};
vm.createContext(context);
vm.runInContext(workView + '\n' + brief + '\nthis.draw = brief; this.work = workView;', context);
const run = {so_far: 3600, chance: {cpu_hours: null}, work_eta: {samples: 1024, done: 12345, rate: 678.9, source_time: 123456}};
assert.deepEqual(Array.from(context.draw(run), x => x.id), ['heading', 'eta']);
assert.equal(f.eta.hidden, false);
assert.equal(f.cpu.hidden, true);
assert.equal(f.measure.hidden, false);
assert.equal(f.chance.hidden, false);
for (const x of f.fields['work-done']) assert.equal(x.textContent, '12,345');
for (const x of f.fields['work-rate']) assert.equal(x.textContent, '678.9');
context.work(f.box, {...run, work_eta: {...run.work_eta, done: 23456, rate: 789.1}});
for (const x of f.fields['work-done']) assert.equal(x.textContent, '23,456');
for (const x of f.fields['work-rate']) assert.equal(x.textContent, '789.1');
for (const cpu_hours of [12.5, null]) {
  f = fixture();
  assert.deepEqual(Array.from(context.draw({so_far: 3600, chance: {cpu_hours}}), x => x.id), ['heading', 'chance-line']);
  assert.equal(f.cpu.hidden, false);
  assert.equal(f.measure.hidden, true);
  assert.equal(f.chance.hidden, false);
}
f = fixture();
assert.deepEqual(Array.from(context.draw({so_far: 3600}), x => x.id), ['heading']);
