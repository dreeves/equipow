// Replicata: the actual work-model renderer (workView) and existing basis loop, with a small DOM fixture; and
// index.html's markup.
// Expectata: work measurements update; legacy visibility and all three probability charts remain; no field of the
// samples or the source time anywhere on the page, the rate in the work bar's caption; the work note's prior a field,
// no number typed into it.
// Spec change (Claude, 2026-11-06; dreeves: "1. add nodes/s to the blue/purple line" and "2. kill the whole line with
// number of samples"): the work paragraph (data-work-eta: samples, nodes checked, rate and source time), whose fields
// this qual checked, is gone; the rate is in the bar's caption, after its nodes checked, and workView shows the bar
// (data-work-measure="work") for a work run and the CPU-hours variant (data-work-measure="cpu") for the others.
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
const caption = live.match(/<div class="progress-work" data-work-measure="work" hidden>[\s\S]*?<p class="progress-bar-caption">([\s\S]*?)<\/p>/);
assert.ok(caption);
assert.match(caption[1], /<span class="spent">[^<]*<b data-bar-done><\/b>[^<]*<b data-work-rate><\/b>[^<]*<\/span>/);
const basisNote = html.match(/<p[^>]*data-odds-basis="work"[^>]*>([\s\S]*?)<\/p>/);
assert.ok(basisNote);
// Spec change (Claude, 2026-11-06; dreeves, of 288:10's prior 0.01, typed into this note: "that sounds dumb. let's start
// with an ignorant prior (50%) and let it fall naturally as the search progresses"): the note's prior is a field that
// the page fills from the run's odds (data-odds-prior), so that it states the run's actual prior; no number is typed in.
assert.match(basisNote[1], /<span data-odds-prior><\/span>/);
assert.doesNotMatch(basisNote[1], /\d/);
const oddsMarkup = html.slice(html.indexOf('<div class="progress-odds"'), html.indexOf('</details>', html.indexOf('<div class="progress-odds"')));
assert.equal((oddsMarkup.match(/<svg /g) || []).length, 3);
assert.ok(oddsMarkup.indexOf('data-exists-') < oddsMarkup.indexOf('data-found-'));
assert.ok(oddsMarkup.indexOf('data-found-') < oddsMarkup.indexOf('data-chance-'));
const basisLoop = script.match(/    for \(const e of fig\.querySelectorAll\('\[data-odds-basis\]'\)\) e\.hidden = e\.dataset\.oddsBasis !== basis;/);
assert.ok(basisLoop);
const lindyLine = script.match(/      box\.querySelector\('\[data-lindy\]'\)\.hidden = !run\.lindy;/);
assert.ok(lindyLine);
const fields = Object.fromEntries(['done', 'rate'].map(key => [`work-${key}`, {textContent: ''}]));
const bar = {dataset: {workMeasure: 'work'}, hidden: true}, cpu = {dataset: {workMeasure: 'cpu'}, hidden: false};
const lindy = {hidden: true};
const box = {
  querySelector: s => ({'[data-lindy]': lindy})[s],
  querySelectorAll: s => s === '[data-work-measure]' ? [bar, cpu] : [fields[s.slice(6, -1)]].filter(Boolean),
};
const notes = ['lindy', 'campaign', 'work'].map(oddsBasis => ({dataset: {oddsBasis}, hidden: true}));
const fig = {querySelectorAll: () => notes};
const context = {stamp: t => `stamp:${t}`, fill: (el, key, text) => { for (const e of el.querySelectorAll(`[data-${key}]`)) e.textContent = text; }};
vm.createContext(context);
vm.runInContext(source[0] + `\nthis.draw = (box, run, fig, basis) => { workView(box, run); ${lindyLine[0]} ${basisLoop[0]} };`, context);
const run = {lindy: false, work_eta: {source_time: 123456, samples: 1024, nodes: 1e9, done: 12345, rate: 678.9, roots_done: 4, roots_total: 16, model: 'importance', interval: 'conditional', discrepancy_factor: 4, rate_log_sd: .35}};
context.draw(box, run, fig, 'work');
assert.equal(bar.hidden, false);
assert.equal(cpu.hidden, true);
assert.equal(lindy.hidden, true);
assert.deepEqual(notes.filter(e => !e.hidden).map(e => e.dataset.oddsBasis), ['work']);
assert.equal(fields['work-done'].textContent, '12,345');
assert.equal(fields['work-rate'].textContent, '678.9');
context.draw(box, {...run, work_eta: {...run.work_eta, samples: 2048, done: 23456, rate: 789.1, source_time: 123999}}, fig, 'work');
assert.equal(fields['work-done'].textContent, '23,456');
assert.equal(fields['work-rate'].textContent, '789.1');
for (const [legacy, basis] of [[{lindy: true}, 'lindy'], [{lindy: false}, 'campaign'], [{}, 'campaign'], [{work_eta: null}, 'lindy']]) {
  context.draw(box, legacy, fig, basis);
  assert.equal(bar.hidden, true);
  assert.equal(cpu.hidden, false);
  assert.equal(lindy.hidden, !legacy.lindy);
  assert.deepEqual(notes.filter(e => !e.hidden).map(e => e.dataset.oddsBasis), [basis]);
}
context.draw(box, run, fig, 'work');
assert.equal(bar.hidden, false);
assert.equal(fields['work-done'].textContent, '12,345');
