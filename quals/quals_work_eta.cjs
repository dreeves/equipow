// Replicata: the actual work-note renderer and existing basis loop, with a small DOM fixture.
// Expectata: work measurements update; legacy visibility and all three probability charts remain.
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
// sentence, and by his rule since 2026-10-26 no qual checks wording, TODO comments or attribution; so the note's
// fields and the prior's number are checked, not its words.
const note = html.match(/<p[^>]*data-work-eta[^>]*>([\s\S]*?)<\/p>/);
assert.ok(note);
for (const key of ['samples', 'done', 'rate', 'source_time']) assert.ok(note[1].includes(`data-work-${key}`));
const basisNote = html.match(/<p[^>]*data-odds-basis="work"[^>]*>([\s\S]*?)<\/p>/);
assert.ok(basisNote);
assert.match(basisNote[1], /0\.01/);
const oddsMarkup = html.slice(html.indexOf('<div class="progress-odds"'), html.indexOf('</details>', html.indexOf('<div class="progress-odds"')));
assert.equal((oddsMarkup.match(/<svg /g) || []).length, 3);
assert.ok(oddsMarkup.indexOf('data-exists-') < oddsMarkup.indexOf('data-found-'));
assert.ok(oddsMarkup.indexOf('data-found-') < oddsMarkup.indexOf('data-chance-'));
const basisLoop = script.match(/    for \(const e of fig\.querySelectorAll\('\[data-odds-basis\]'\)\) e\.hidden = e\.dataset\.oddsBasis !== basis;/);
assert.ok(basisLoop);
const lindyLine = script.match(/      box\.querySelector\('\[data-lindy\]'\)\.hidden = !run\.lindy;/);
assert.ok(lindyLine);
const fields = Object.fromEntries(['samples', 'done', 'rate', 'source_time'].map(key => [`work-${key}`, {textContent: ''}]));
const work = {hidden: true, querySelectorAll: s => [fields[s.slice(6, -1)]].filter(Boolean)};
const lindy = {hidden: true};
const box = {
  querySelector: s => ({'[data-work-eta]': work, '[data-lindy]': lindy})[s],
  querySelectorAll: s => s === '[data-work-eta]' ? [work] : [fields[s.slice(6, -1)]].filter(Boolean),
};
const notes = ['lindy', 'campaign', 'work'].map(oddsBasis => ({dataset: {oddsBasis}, hidden: true}));
const fig = {querySelectorAll: () => notes};
const context = {stamp: t => `stamp:${t}`, fill: (el, key, text) => { for (const e of el.querySelectorAll(`[data-${key}]`)) e.textContent = text; }};
vm.createContext(context);
vm.runInContext(source[0] + `\nthis.draw = (box, run, fig, basis) => { workView(box, run); ${lindyLine[0]} ${basisLoop[0]} };`, context);
const run = {lindy: false, work_eta: {source_time: 123456, samples: 1024, nodes: 1e9, done: 12345, rate: 678.9, roots_done: 4, roots_total: 16, model: 'importance', interval: 'conditional', discrepancy_factor: 4, rate_log_sd: .35}};
context.draw(box, run, fig, 'work');
assert.equal(work.hidden, false);
assert.equal(lindy.hidden, true);
assert.deepEqual(notes.filter(e => !e.hidden).map(e => e.dataset.oddsBasis), ['work']);
assert.equal(fields['work-samples'].textContent, '1,024');
assert.equal(fields['work-done'].textContent, '12,345');
assert.equal(fields['work-rate'].textContent, '678.9');
assert.equal(fields['work-source_time'].textContent, 'stamp:123456');
context.draw(box, {...run, work_eta: {...run.work_eta, samples: 2048, done: 23456, rate: 789.1, source_time: 123999}}, fig, 'work');
assert.equal(fields['work-samples'].textContent, '2,048');
assert.equal(fields['work-done'].textContent, '23,456');
assert.equal(fields['work-rate'].textContent, '789.1');
assert.equal(fields['work-source_time'].textContent, 'stamp:123999');
for (const [legacy, basis] of [[{lindy: true}, 'lindy'], [{lindy: false}, 'campaign'], [{}, 'campaign'], [{work_eta: null}, 'lindy']]) {
  context.draw(box, legacy, fig, basis);
  assert.equal(work.hidden, true);
  assert.equal(lindy.hidden, !legacy.lindy);
  assert.deepEqual(notes.filter(e => !e.hidden).map(e => e.dataset.oddsBasis), [basis]);
}
context.draw(box, run, fig, 'work');
assert.equal(work.hidden, false);
assert.equal(fields['work-samples'].textContent, '1,024');
