// Replicata: the actual work-model renderer (workView) with the Lindy note's line, on a small DOM fixture; and
// index.html's markup.
// Expectata: work measurements update; the bar shown exactly for a run with a work model and the Lindy note exactly
// for a run on Lindy's rule; no field of the samples or the source time anywhere on the page, the rate in the work bar's
// caption; every run's odds' figure one graph, P(exists), after a line stating the prior, a field (data-odds-prior)
// with no number typed into it, and nothing after the graph: no basis note, no second or third graph.
// Spec change (Claude, 2026-11-06; dreeves: "1. add nodes/s to the blue/purple line" and "2. kill the whole line with
// number of samples"): the work paragraph (data-work-eta: samples, nodes checked, rate and source time), whose fields
// this qual checked, is gone; the rate is in the bar's caption, after its nodes checked, and workView shows the bar
// (data-work-measure="work") for a work run and the CPU-hours variant (data-work-measure="cpu") for the others.
// Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good argument for
// salvaging anything. the up-to-date probability that a bipartition exists is great."; "for anti-magic i don't want to
// conditionally include or exclude graphs."; "after the ETA graph, explicitly state the prior probability a
// bipartition exists. we can go back to 1% or whatever makes sense for 288:10. then show the first probability graph,
// even though for 288:10 it's uninteresting. then kill everything below that."): the odds' figure holds one graph, after
// the prior's line, in place of three graphs and the basis notes (the work note stating the prior among them), whose
// loop this qual ran; and no part has the CPU-hours basis (data-work-measure="cpu"), which went with the chance line,
// the sea and the runs line no longer hidden for a run with a work model.
// Resultata: the focused assertions report the differing field or visibility state, without a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');
new vm.Script(script);
const source = script.match(/  function workView\(box, run\) \{[\s\S]*?\n  \}/);
assert.ok(source);
assert.ok(script.includes('      workView(box, run);'));
// Spec change (Claude, 2026-11-05): dreeves rewrote the work note in his own words, with no TODO comment and no 90%
// sentence, and by his rule since 2026-10-26 no qual checks wording, TODO comments or attribution; so the fields and the
// prior's number are checked, not the words.
const live = html.replace(/<!--[\s\S]*?-->/g, '');                    // what the page shows: its comments left out
assert.doesNotMatch(live, /data-work-(eta|samples|source_time)\b/, 'a field of the work paragraph, its samples or its source time');
assert.doesNotMatch(live, /data-work-measure="cpu"/, 'a part on the CPU-hours basis');
const caption = live.match(/<div class="progress-work" data-work-measure="work" hidden>[\s\S]*?<p class="progress-bar-caption">([\s\S]*?)<\/p>/);
assert.ok(caption);
assert.match(caption[1], /<span class="spent">[^<]*<b data-bar-done><\/b>[^<]*<b data-work-rate><\/b>[^<]*<\/span>/);
// the odds' figure, its comments left out: the prior's line, a field with no number typed in, then the graph's title
// and the graph, the figure's last
const odds = live.match(/<div class="progress-odds">([\s\S]*?)<\/div>/);
assert.ok(odds, 'the odds\' figure, shown for every run (no hidden attribute)');
const parts = odds[1].trim().split(/\n\s*/);
assert.equal((odds[1].match(/<svg /g) || []).length, 1);
assert.match(parts[0], /^<p>[^<\d]*<b data-odds-prior><\/b><\/p>$/);
assert.match(parts[1], /^<p class="progress-odds-title">/);
assert.match(parts[2], /^<svg [^>]*>$/);
assert.equal(parts[parts.length - 1], '</svg>');
assert.doesNotMatch(live, /data-odds-basis|data-found-|data-chance-/);
const lindyLine = script.match(/      box\.querySelector\('\[data-lindy\]'\)\.hidden = !run\.lindy;/);
assert.ok(lindyLine);
const fields = Object.fromEntries(['done', 'rate'].map(key => [`work-${key}`, {textContent: ''}]));
const bar = {dataset: {workMeasure: 'work'}, hidden: true};
const lindy = {hidden: true};
const box = {
  querySelector: s => ({'[data-lindy]': lindy})[s],
  querySelectorAll: s => s === '[data-work-measure]' ? [bar] : [fields[s.slice(6, -1)]].filter(Boolean),
};
const context = {stamp: t => `stamp:${t}`, fill: (el, key, text) => { for (const e of el.querySelectorAll(`[data-${key}]`)) e.textContent = text; }};
vm.createContext(context);
vm.runInContext(source[0] + `\nthis.draw = (box, run) => { workView(box, run); ${lindyLine[0]} };`, context);
const run = {lindy: false, work_eta: {source_time: 123456, samples: 1024, nodes: 1e9, done: 12345, rate: 678.9, roots_done: 4, roots_total: 16, model: 'importance', interval: 'conditional', discrepancy_factor: 4, rate_log_sd: .35}};
context.draw(box, run);
assert.equal(bar.hidden, false);
assert.equal(lindy.hidden, true);
assert.equal(fields['work-done'].textContent, '12,345');
assert.equal(fields['work-rate'].textContent, '678.9');
context.draw(box, {...run, work_eta: {...run.work_eta, samples: 2048, done: 23456, rate: 789.1, source_time: 123999}});
assert.equal(fields['work-done'].textContent, '23,456');
assert.equal(fields['work-rate'].textContent, '789.1');
for (const legacy of [{lindy: true}, {lindy: false}, {}, {work_eta: null}]) {
  context.draw(box, legacy);
  assert.equal(bar.hidden, true);
  assert.equal(lindy.hidden, !legacy.lindy);
}
context.draw(box, run);
assert.equal(bar.hidden, false);
assert.equal(fields['work-done'].textContent, '12,345');
