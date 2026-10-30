// Replicata: index.html's progress section without a browser: the run template's stale mark, the renderer's staleView
// on a run whose data are fresh (stale null) and on one whose data are stale (stale a time), and the status line's time.
// Expectata (2026-10-30, progress.py's snapshot keeps a run's last good data, marked stale with their time): the mark,
// Claude: "stale" with a TODO above it, hidden for the fresh run (and for a run of an older data file, which has no
// stale field) and shown for the stale one, with that time as the section's stamp writes it; the status line given the
// run's own time, its stale time or else the snapshot's.
// Resultata: an assertion failure names the part that differs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html', 'utf8');
const template = html.match(/<template class="progress-run">([\s\S]*?)<\/template>/);
assert.ok(template, 'the run template must exist');
assert.match(template[1], /<!-- TODO: [^>]*stale[^>]*--><span class="progress-stale" data-stale hidden>Claude: "stale" \(<span data-stale-at><\/span>\)<\/span><\/summary>/,
  'the stale mark must close the run heading, attributed, after its TODO');
const source = html.match(/  function staleView\(box, run\) \{[\s\S]*?\n  \}/);
assert.ok(source, 'the renderer must have staleView');
assert.ok(html.includes("      staleView(box, run);\n      snapshot(box.querySelector('.progress-status'), run.stale ?? data.made, run.so_far, run.to_go);"),
  'each run must be marked, its status line at its own data\'s time');
const context = {stamp: t => `stamp:${t}`};
vm.createContext(context);
vm.runInContext(source[0] + '\nthis.mark = staleView;', context);
for (const run of [{stale: null}, {stale: 1793352940}, {}]) {      // the last as a data file before 2026-10-30 gives it
  const at = {textContent: 'unset'}, mark = {hidden: 'unset', querySelector: s => ({'[data-stale-at]': at})[s]};
  const box = {querySelector: s => ({'[data-stale]': mark})[s]};
  context.mark(box, run);
  assert.equal(mark.hidden, !run.stale);
  assert.equal(at.textContent, run.stale ? `stamp:${run.stale}` : '');
}
console.log('stale mark ok');
