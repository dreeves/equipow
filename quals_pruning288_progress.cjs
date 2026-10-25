// Replicata: the actual paired-study renderer with a small DOM fixture, without a browser.
// Expectata: independent baseline/wider counts and states, elapsed time, and no completion estimate.
// Resultata: assertion failures identify the field or behavior that differs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html', 'utf8');
const script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(x => x[1]).find(x => x.includes('window.progressView'));
new vm.Script(script);
const source = html.match(/  function attemptView\(box, run, templateName, hintName\) \{[\s\S]*?\n  \}/);
assert.ok(source, 'the paired-study renderer must exist');
const body = html.match(/<template class="progress-pruning288">([\s\S]*?)<\/template>/)[1];
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
  'template.progress-pruning288': {content: {cloneNode() { return display; }}},
  'template.progress-pruning-hint': {content: hint},
}[s]; }};
const box = {querySelector(s) { return {
  '.progress-status': status, '.progress-key': key, '.progress-eta': eta,
  '[data-readout]': readout, canvas,
}[s]; }};
const context = {section, duration: seconds => 'duration:' + seconds};
vm.createContext(context);
vm.runInContext(source[0] + '\nthis.draw = attemptView;', context);
const work = {baseline_control_witnesses: 1, wider_control_witnesses: 1,
  baseline_attempted: 4, wider_attempted: 3, variant_total: 7,
  baseline_empty: 3, wider_empty: 2, baseline_timeout: 1, wider_timeout: 0,
  baseline_witnesses: 0, wider_witnesses: 1, baseline_seconds: 45.25, wider_seconds: 18.5};
for (const outcome of [null, 'budget', 'control_failed', 'witness', 'failed']) {
  const run = {work, phase: 'search', outcome, state: 'running', so_far: 125};
  context.draw(box, run, 'progress-pruning288', 'progress-pruning-hint');
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
