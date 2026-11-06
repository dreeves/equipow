// Replicata: the actual time-bar renderer with ordinary, narrow, point and absent forecasts.
// Expectata: preserve the time scale, mark its finish interval and median, and label coverage only when supplied.
// Resultata: assertions identify missing marks, incorrect coordinates or unsupported probability labels.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');
const source = script.match(/  function bar\(box, run\) \{[\s\S]*?\n  \}/)[0];
assert.ok(/data-bar="band"[^>]*>\s*<svg[^>]*class="progress-brace"/.test(html), 'finish-interval brace');
assert.ok(/data-bar-coverage/.test(html), 'explicit model coverage field');
const parts = Object.fromEntries(['so-far', 'lo', 'band', 'median'].map(k => [k, {style: {}, hidden: false}]));
const coverage = {hidden: false}, percent = {textContent: ''};
const box = {querySelector(s) {
  if (s === '[data-bar-coverage]') return coverage;
  return parts[s.match(/data-bar="([^"]+)"/)[1]];
}};
const context = {assert, pct: x => `${100*x}%`, fill: (_, key, value) => {assert.equal(key, 'bar-percent'); percent.textContent = value;}};
vm.createContext(context);
vm.runInContext(source + '\nthis.draw = bar;', context);
for (const [elapsed, g, expected] of [
  [2, {lo: .5, median: 1, hi: 3}, [40, 10, 50, 60]],
  [100, {lo: .5, median: 1, hi: 3}, [10000/103, 50/103, 250/103, 10100/103]],
  [2, {lo: 1, median: 1, hi: 1}, [200/3, 100/3, 0, 100]],
  [0, {lo: 0, median: 0, hi: 0}, [0, 0, 0, 0]],
  [2, null, [100, 0, 0, 0]],
  [0, null, [0, 0, 0, 0]],
]) {
  context.draw(box, {so_far: elapsed, to_go: g});
  const actual = ['so-far', 'lo', 'band'].map(k => parseFloat(parts[k].style.width)).concat(parseFloat(parts.median.style.left));
  actual.forEach((v, i) => assert.ok(Math.abs(v-expected[i]) < 1e-10, [v, expected[i]]));
  assert.equal(parts.median.hidden, !g);
  assert.equal(parts.band.hidden, !g);
  assert.equal(coverage.hidden, true);
}
const g = {lo: .5, median: 1, hi: 3};
for (const c of [.8, .9]) {
  context.draw(box, {so_far: 2, to_go: g, work_eta: {interval: 'conditional', coverage: c}});
  assert.equal(coverage.hidden, false);
  assert.equal(parseFloat(percent.textContent), c*100);
}
context.draw(box, {so_far: 2, to_go: null, work_eta: {interval: 'conditional', coverage: .9}});
assert.equal(coverage.hidden, true);
for (const coverage of [0, 1, -.1, 1.1, '0.9', NaN, Infinity]) {
  assert.throws(() => context.draw(box, {so_far: 2, to_go: g, work_eta: {interval: 'conditional', coverage}}));
}
assert.throws(() => context.draw(box, {so_far: 2, to_go: g, work_eta: {interval: 'confidence', coverage: .9}}));
