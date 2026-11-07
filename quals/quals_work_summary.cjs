// Replicata: the actual brief and workView renderers on a small DOM fixture, with a work run, runs with no work model
// (a campaign target's, with odds, and an overnight run's), and a stale one.
// Expectata: a work run's popup rows are its summary line and its bar's caption, its numbers drawn into the brief's box
// by bar and workView as on the page; every other run's its summary line and its status line, filled by statusLine at
// the snapshot's time; each row's numbers the run's own.
// Spec change (Claude, 2026-11-06; dreeves: "1. add nodes/s to the blue/purple line" and "2. kill the whole line with
// number of samples"): a work run's popup row is its bar's caption (the nodes checked, the rate and the total's range),
// its numbers drawn into the brief's box by bar as on the page, in place of the work paragraph (data-work-eta), which
// is gone.
// Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good argument for
// salvaging anything. the up-to-date probability that a bipartition exists is great."; the coordinator: "Make every
// other run brief its status line (time so far + to go), with no new branch beyond a selector map like workView's"):
// every other run's row is its status line, in place of a campaign target's chance line (its probabilities and units,
// which this qual checked) and no row for the others; brief takes the snapshot's time for it.
// Resultata: assertions identify a wrong returned row, measurement value, or the time a status line was filled at.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');
const brief = script.match(/  function brief\(run, made\) \{[\s\S]*?\n  \}/)[0];
const workView = script.match(/  function workView\(box, run\) \{[\s\S]*?\n  \}/)[0];
assert.ok(script.includes("here.flatMap(run => brief(run, data.made))"), 'the brief of each run at the snapshot\'s time');
assert.doesNotMatch(html.replace(/<!--[\s\S]*?-->/g, ''), /progress-chance/, 'the chance line, gone');

// a run's box: the work fields (the bar's caption's rate), the bar's caption, the bar's container (the one part with a
// basis), and the status line
function fixture() {
  const fields = Object.fromEntries(['done', 'rate'].map(key => [`work-${key}`, [{textContent: ''}]]));
  const caption = {id: 'caption'}, status = {id: 'status'};
  const measure = {dataset: {workMeasure: 'work'}, hidden: true};
  const box = {
    querySelector: s => ({'summary h3': {childNodes: ['heading']}, summary: {querySelectorAll: () => []}})[s],
    querySelectorAll: s => ({'[data-work-measure]': [measure], '[data-work-measure="work"] .progress-bar-caption': [caption],
                             '.progress-status': [status]})[s] || fields[s.slice(6, -1)] || [],
  };
  return {box, caption, status, measure, fields};
}
let f = fixture();
const drawn = [], lines = [];                           // the boxes and runs bar drew, and the status lines filled
const context = {
  template: {content: {firstElementChild: {cloneNode: () => f.box}}},
  document: {createElement: () => ({id: 'heading', append() {}})},
  heading() {}, staleView() {},
  statusLine: (box, run, made) => { lines.push([box, run, made]); },
  bar: (box, run) => { drawn.push([box, run]); },
  dur: x => String(x), tenth: x => x, stamp: t => `stamp:${t}`,
  fill: (el, key, text) => { for (const e of el.querySelectorAll(`[data-${key}]`)) e.textContent = text; },
};
vm.createContext(context);
vm.runInContext(workView + '\n' + brief + '\nthis.draw = brief; this.work = workView;', context);
const run = {so_far: 3600, work_eta: {samples: 1024, done: 12345, rate: 678.9, source_time: 123456}};
assert.deepEqual(Array.from(context.draw(run, 1792200000), x => x.id), ['heading', 'caption']);
assert.ok(drawn.some(([box, r]) => box === f.box && r === run), 'the bar drawn into the brief\'s box, for its caption\'s numbers');
assert.ok(lines.some(([box, r, made]) => box === f.box && r === run && made === 1792200000), 'the status line filled at the snapshot\'s time');
assert.equal(f.measure.hidden, false);
for (const x of f.fields['work-done']) assert.equal(x.textContent, '12,345');
for (const x of f.fields['work-rate']) assert.equal(x.textContent, '678.9');
context.work(f.box, {...run, work_eta: {...run.work_eta, done: 23456, rate: 789.1}});
for (const x of f.fields['work-done']) assert.equal(x.textContent, '23,456');
for (const x of f.fields['work-rate']) assert.equal(x.textContent, '789.1');
for (const other of [{so_far: 3600, odds: {prior: 0.3, since: 1, exists: []}}, {so_far: 3600}, {so_far: 3600, work_eta: null, stale: 1792100000}]) {
  f = fixture();
  assert.deepEqual(Array.from(context.draw(other, 1792200000), x => x.id), ['heading', 'status']);
  assert.equal(f.measure.hidden, true);
  assert.ok(lines.some(([box, r, made]) => box === f.box && r === other && made === 1792200000), JSON.stringify(other));
}
