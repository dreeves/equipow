// Replicata: the actual 592-pilot renderer with a small DOM fixture, without a browser.
// Expectata: independent 560-control/592-target counts and states, elapsed time, and no completion estimate.
// Resultata: assertion failures identify the field or behavior that differs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html', 'utf8');
const script = fs.readFileSync('page/progress-section.js', 'utf8');   // the section's script, in index.html until 2026-10-31
new vm.Script(script);
const source = script.match(/  function attemptView\(box, run, templateName, hintName\) \{[\s\S]*?\n  \}/);
assert.ok(source, 'the 592-pilot renderer must exist');
assert.ok(script.includes("if (run.program === 'search592.py') attemptView(box, run, 'progress-search592', 'progress-592-hint');"),
  'the pilot must use its own attempt templates');
const body = html.match(/<template class="progress-search592">([\s\S]*?)<\/template>/)[1];
const fields = [...body.matchAll(/data-attempt-count="([^"]+)"/g)].map(([, work]) => ({dataset: {attemptCount: work}}));
const phases = [...body.matchAll(/data-attempt-phase="([^"]+)"/g)].map(([, phase]) => ({dataset: {attemptPhase: phase}}));
const outcomes = [...body.matchAll(/data-attempt-outcome="([^"]+)"/g)].map(([, outcome]) => ({dataset: {attemptOutcome: outcome}}));
const elapsed = {}, state = {}, status = {replaceChildren(x) { this.child = x; }}, key = {}, eta = {};
const readout = {replaceChildren(x) { this.child = x; }};
const canvas = {setAttribute(k, v) { this[k] = v; }};
const display = {
  querySelectorAll(s) { return {'[data-attempt-count]': fields, '[data-attempt-phase]': phases, '[data-attempt-outcome]': outcomes}[s]; },
  querySelector(s) { return {'[data-elapsed]': elapsed, '[data-search-state]': state}[s]; },
};
const hint = {textContent: 'Astra: "One dot per attempt."', cloneNode() { return this; }};
const section = {querySelector(s) { return {
  'template.progress-search592': {content: {cloneNode() { return display; }}},
  'template.progress-592-hint': {content: hint},
}[s]; }};
const box = {querySelector(s) { return {
  '.progress-status': status, '.progress-key': key, '.progress-eta': eta,
  '[data-readout]': readout, canvas,
}[s]; }};
const context = {section, duration: seconds => 'duration:' + seconds};
vm.createContext(context);
vm.runInContext(source[0] + '\nthis.draw = attemptView;', context);
const work = {control_attempted: 2, control_total: 32, control_empty: 0, control_timeout: 1,
  control_witnesses: 1, attempted: 5, total: 32, empty: 2, timeout: 3};
for (const outcome of [null, 'budget', 'control_failed', 'witness', 'failed']) {
  const run = {work, phase: 'search', outcome, state: 'running', so_far: 125};
  context.draw(box, run, 'progress-search592', 'progress-592-hint');
  for (const field of fields) assert.equal(field.textContent, work[field.dataset.attemptCount].toLocaleString('en-US'));
  assert.deepEqual(phases.filter(x => !x.hidden).map(x => x.dataset.attemptPhase), ['search']);
  assert.deepEqual(outcomes.filter(x => !x.hidden).map(x => x.dataset.attemptOutcome), [String(outcome)]);
  assert.equal(elapsed.textContent, 'duration:125');
  assert.equal(state.textContent, 'running');
  assert.equal(eta.hidden, true);
  assert.equal(key.hidden, true);
  assert.equal(status.child, display);
  assert.equal(readout.child, hint);
  assert.equal(canvas['aria-label'], hint.textContent);
}
