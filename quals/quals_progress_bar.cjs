// Spec change authorized by dreeves, 2026-11-06: replace the misleading median circle with a labeled time ruler.
// Replicata: the actual ruler renderer with ordinary, narrow, point, zero and absent forecasts.
// Expectata: one elapsed marker, a separate exact finish interval, labeled time ticks extending past its upper end.
// Resultata: assertions identify old median/100%-track semantics, wrong geometry or unsupported coverage labels.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');
const source = script.match(/  function bar\(box, run\) \{[\s\S]*?\n  \}/)[0];
assert.ok(!/data-bar="median"/.test(html), 'no median current-position lookalike');
assert.ok(/data-bar="now"/.test(html), 'elapsed marker');
const element = () => ({style: {}, hidden: false, textContent: '', children: [], replaceChildren(...xs) {this.children = xs;}});
const parts = Object.fromEntries(['so-far', 'band', 'now', 'ticks'].map(k => [k, element()]));
const coverage = element(), percent = element(), live = element(), recorded = element();
const box = {querySelector(s) {
  const known = {'[data-bar-coverage]':coverage, '[data-bar-live]':live, '[data-bar-recorded]':recorded};
  return known[s] || parts[s.match(/data-bar="([^"]+)"/)[1]];
}};
const context = {assert, document:{createElement:element}, fill: (_, key, value) => {assert.equal(key, 'bar-percent'); percent.textContent = value;}};
vm.createContext(context);
const helpers = script.match(/  const UNITS = .*\n  const unitOf = .*\n/)[0] + script.slice(script.indexOf('  const num ='), script.indexOf('  const assert ='));
vm.runInContext(helpers + source + '\nthis.draw = bar;', context);
const close = (a,b) => assert.ok(Math.abs(a-b)<.0002,[a,b]);
const cases = [
  [7200,{lo:1800,median:3600,hi:10800},21600,'h'],
  [360000,{lo:1800,median:3600,hi:10800},518400,'d'],
  [51120,{lo:12947400,median:27000000,hi:203045040},252460800,'y'],
  [7200,{lo:3600,median:3600,hi:3600},14400,'h'],
  [0,{lo:0,median:0,hi:0},3600,'h'],
  [7200,null,9000,'h'], [0,null,3600,'h'],
];
for (const [elapsed,g,total,unit] of cases) {
  context.draw(box,{so_far:elapsed,to_go:g,state:'running'});
  assert.ok(total>elapsed+(g?.hi??0));
  close(parseFloat(parts['so-far'].style.width),100*elapsed/total);
  close(parseFloat(parts.now.style.left),100*elapsed/total);
  close(parseFloat(parts.band.style.left),100*(elapsed+(g?.lo??0))/total);
  close(parseFloat(parts.band.style.width),100*((g?.hi??0)-(g?.lo??0))/total);
  assert.equal(parts.band.hidden,!g);
  assert.equal(coverage.hidden,true);
  assert.equal(live.hidden,false);
  assert.equal(recorded.hidden,true);
  const ticks=parts.ticks.children;
  assert.ok(ticks.length>=2 && ticks.length<=7);
  assert.equal(ticks[0].textContent,'0');
  assert.ok(ticks.at(-1).textContent.endsWith('\u202f'+unit));
  assert.equal(parseFloat(ticks.at(-1).style.left),100);
}
for (const state of ['paused','frozen','ended']) {
  context.draw(box,{so_far:7200,to_go:null,state});
  assert.equal(live.hidden,true); assert.equal(recorded.hidden,false);
}
for (const stale of [0,12345]) {
  context.draw(box,{so_far:7200,to_go:null,state:'running',stale});
  assert.equal(live.hidden,true); assert.equal(recorded.hidden,false);
}
const g={lo:1800,median:3600,hi:10800};
for (const c of [.8,.9]) {
  context.draw(box,{so_far:7200,to_go:g,state:'running',work_eta:{interval:'conditional',coverage:c}});
  assert.equal(coverage.hidden,false); assert.equal(parseFloat(percent.textContent),c*100);
}
context.draw(box,{so_far:7200,to_go:null,work_eta:{interval:'conditional',coverage:.9}});
assert.equal(coverage.hidden,true);
for (const coverage of [0,1,-.1,1.1,'0.9',NaN,Infinity]) {
  assert.throws(()=>context.draw(box,{so_far:7200,to_go:g,work_eta:{interval:'conditional',coverage}}));
}
assert.throws(()=>context.draw(box,{so_far:7200,to_go:g,work_eta:{interval:'confidence',coverage:.9}}));
