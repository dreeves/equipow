// Replicata: the actual full-sweep renderer with a small DOM fixture, without a browser.
// Expectata: one control and 2,736 independent target counts and states, elapsed time, and no completion estimate.
// Resultata: assertion failures identify the field or behavior that differs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');   // the repository's root, above quals/
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');   // the section's script, in index.html until 2026-10-31
new vm.Script(script);
const source = script.match(/  function search288View\(box, run\) \{[\s\S]*?\n  \}/);
assert.ok(source, 'the full-sweep renderer must exist');
const common = script.match(/  function attemptView\(box, run, templateName, hintName\) \{[\s\S]*?\n  \}/);
assert.ok(common, 'the common attempt renderer must exist');
assert.ok(script.includes("if (run.program === 'sweep288.py') search288View(box, run);"), 'the sweep must use the attempt renderer');
const body = html.match(/<template class="progress-search288">([\s\S]*?)<\/template>/)[1];
const fields = [...body.matchAll(/data-attempt-count="([^"]+)"/g)].map(([, work]) => ({dataset: {attemptCount: work}}));
const phases = [...body.matchAll(/data-attempt-phase="([^"]+)"/g)].map(([, phase]) => ({dataset: {attemptPhase: phase}}));
const outcomes = [...body.matchAll(/data-attempt-outcome="([^"]+)"/g)].map(([, outcome]) => ({dataset: {attemptOutcome: outcome}}));
const elapsed = {}, state = {}, status = {replaceChildren(x) { this.child = x; }}, key = {}, eta = {};
const readout = {replaceChildren(x) { this.child = x; }};
const canvas = {setAttribute(k, v) { this[k] = v; }};
const display = {
  querySelectorAll(s) { return {'[data-attempt-count]': fields, '[data-attempt-phase]': phases, '[data-attempt-outcome]': outcomes, '[data-elapsed]': [elapsed]}[s]; },
  querySelector(s) { return {'[data-search-state]': state}[s]; },
};
const hint = {textContent: 'Astra: "One dot per attempt."', cloneNode() { return this; }};
const section = {querySelector(s) { return {
  'template.progress-search288': {content: {cloneNode() { return display; }}},
  'template.progress-attempt-hint': {content: hint},
}[s]; }};
const box = {querySelector(s) { return {
  '.progress-status': status, '.progress-key': key, '.progress-eta': eta,
  '[data-readout]': readout, canvas,
}[s]; }};
// Fixture change (Claude, 2026-11-07; dreeves: "redundant elapsed time here. let's keep the one in blue and nix the
// one in black", and "show elapsed time with full granularity like so: 3d 4h 5m 6s"): the renderer writes the
// elapsed time with the page's own fill (run here from its source), through hms, in place of duration, since a
// tracked search's counts, from the same renderer, have none.
const fill = script.match(/  const fill = \(el, field, text\) => \{[^\n]*\};/)[0];
const context = {section, hms: seconds => 'hms:' + seconds};
vm.createContext(context);
vm.runInContext(fill + '\n' + common[0] + source[0] + '\nthis.draw = search288View;', context);
const work = {control_attempted: 1, control_total: 1, control_empty: 0, control_timeout: 0,
  control_witnesses: 1, attempted: 2736, total: 2736, empty: 2551, timeout: 185};
for (const outcome of [null, 'budget', 'control_failed', 'witness', 'failed']) {
  const run = {work, phase: 'search', outcome, state: 'running', so_far: 125};
  context.draw(box, run);
  for (const field of fields) assert.equal(field.textContent, work[field.dataset.attemptCount].toLocaleString('en-US'));
  assert.deepEqual(phases.filter(x => !x.hidden).map(x => x.dataset.attemptPhase), ['search']);
  assert.deepEqual(outcomes.filter(x => !x.hidden).map(x => x.dataset.attemptOutcome), [String(outcome)]);
  assert.equal(elapsed.textContent, 'hms:125');
  assert.equal(state.textContent, 'running');
  // the ETA chart left as every run's, shown (dreeves, 2026-11-04: "shouldn't there always be an ETA graph, even when
  // it's just based on the lindy effect? death to if-statements, remember?"); until then hidden
  assert.equal(eta.hidden, undefined);
  assert.equal(key.hidden, true);
  assert.equal(status.child, display);
  assert.equal(readout.child, hint);
  assert.equal(canvas['aria-label'], hint.textContent);
}
