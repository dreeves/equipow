// Spec change (Claude, 2026-11-06; dreeves: "i don't like how that progress bar looks. can you revamp it in a way that
// makes sense to you? also bring back a subtle tick for the median finish time. bigger picture: should that progress
// bar be measuring amount of work, not time? the ETA graph is for time. we can still have a 90% CI for amount of work
// remaining, right?"): a work bar replaces the time ruler (Astra's of that day, whose quals these were).
// Replicata: the actual bar() of page/progress-section.js with the page's own helpers, without a browser, on a small
// DOM fixture: work models whose totals are wide, narrow, a point (the search complete) and none (stopped short), at
// small and huge scales, at coverages 0.9 and 0.8; a run with no work model; malformed models, one without a total.
// Then the bar's markup in index.html's run template, and the actual workView on a fixture of it.
// Expectata: the blue part's width done / end of the track, the band from lo / end to hi / end, the median tick at
// median / end (percent), the track's end the last of its round ticks: 0 and on in steps of 1, 2 or 5 times a power of
// 10, at least 1, the end at least 1.1 times the larger of done and the total's upper end and less than 1.65 times it
// (PROPERTIES); for these cases exactly the ticks of WANT, labeled compact (500M, 1B); the band, the tick and the
// caption's purple part hidden exactly when the total is none; the caption's nodes checked exact and its other numbers
// compact (lo–hi, median), its percent the coverage's, wherever the page has those fields; malformed models fail loudly.
// The markup: a container with data-work-measure="work", hidden until drawn, holding the track (done, band, median),
// its axis (ticks) and last the caption, which gives the nodes checked and then the rate in its blue part and, in a
// part hidden with the total's marks, the total's range (dreeves's caption since f6d809b, 2026-11-06: "N nodes checked
// / ~lo–hi", its percent, median and the note under it commented out); no field of the samples or the source time in
// the run template; workView shows that container exactly when the run has a work model, and fills the rate in.
// Spec change (Claude, 2026-11-06; dreeves: "1. add nodes/s to the blue/purple line" and "2. kill the whole line with
// number of samples"): the caption's blue part gives the rate too, and the work paragraph (data-work-eta: samples,
// nodes checked, rate and source time), which workView showed with the container until then, is gone.
// Resultata: assertion failures name the case and the part that differs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');   // the repository's root, above quals/
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'page/progress-section.js'), 'utf8');
new vm.Script(script);
const bar = script.match(/  function bar\(box, run\) \{[\s\S]*?\n  \}/);
assert.ok(bar, 'the section must have bar()');
const workView = script.match(/  function workView\(box, run\) \{[\s\S]*?\n  \}/);
assert.ok(workView, 'the section must have workView()');
// the section's helpers, pure definitions from pad to load (formats, ticks, assert, fill)
const helpers = script.slice(script.indexOf('  const pad = '), script.indexOf('  function load() {'));
assert.ok(helpers.includes('const countTicks = ') && helpers.includes('const compact = ') && helpers.includes('const fill = '), 'helpers');

const element = () => ({style: {}, hidden: false, textContent: '', children: [], dataset: {},
                        replaceChildren(...xs) { this.children = xs; }});
const parts = Object.fromEntries(['done', 'band', 'median', 'ticks'].map(k => [k, element()]));
const caption = Object.fromEntries(['bar-done', 'bar-range', 'bar-median', 'bar-percent'].map(k => [k, element()]));
const purple = element();                                 // the caption's purple part
const box = {
  querySelector: s => parts[s.match(/^\[data-bar="([^"]+)"\]$/)[1]],
  querySelectorAll: s => s === '[data-bar-total]' ? [parts.band, parts.median, purple] : [caption[s.match(/^\[data-([^\]]+)\]$/)[1]]],
};
const context = {document: {createElement: element}};
vm.createContext(context);
vm.runInContext(helpers + bar[0] + workView[0] + '\nthis.draw = bar; this.workView = workView; this.compact = compact;', context);
const compact = new Intl.NumberFormat('en-US', {notation: 'compact'});
const close = (a, b, what) => assert.ok(Math.abs(a - b) < 0.0002, `${what}: ${a} against ${b}`);
const percent = s => { assert.match(s, /^-?[0-9.]+%$/); return parseFloat(s); };
const model = (done, total, coverage = 0.9) => ({work_eta: {done, total, coverage, interval: 'conditional', samples: 1024, rate: 1884.1}});

// each case: [its run, the track's ticks]; the totals the live run's of 2026-11-06 and around it
const WANT = [
  [model(468750102, {lo: 7.8e8, median: 1.27e9, hi: 2.5e9}), [0, 1e9, 2e9, 3e9]],
  [model(9.5e8, {lo: 9.6e8, median: 9.9e8, hi: 1.05e9}), [0, 5e8, 1e9, 1.5e9]],
  [model(1.2e9, {lo: 1.2e9, median: 1.2e9, hi: 1.2e9}), [0, 5e8, 1e9, 1.5e9]],      // complete: the total exact
  [model(4e8, null), [0, 1e8, 2e8, 3e8, 4e8, 5e8]],                                   // stopped short: no forecast
  [model(1234, {lo: 2000, median: 5000, hi: 9000}, 0.8), [0, 2000, 4000, 6000, 8000, 10000]],
  [model(5e10, {lo: 6e10, median: 2e11, hi: 9.9e11}), [0, 5e11, 1e12, 1.5e12]],
  [model(0, {lo: 10, median: 20, hi: 40}), [0, 10, 20, 30, 40, 50]],
  [{}, [0, 1]],                                                                        // no work model: drawn empty, hidden
];
for (const [run, want] of WANT) {
  const what = JSON.stringify(run);
  context.draw(box, run);
  const {done, total, coverage} = run.work_eta ?? {done: 0, total: null, coverage: null};
  const t = total ?? {lo: done, median: done, hi: done};
  const ticks = parts.ticks.children, end = want.at(-1);
  assert.deepEqual(ticks.map(e => e.textContent), want.map(v => compact.format(v)), what);
  ticks.forEach((e, i) => close(percent(e.style.left), 100 * want[i] / end, `${what} tick ${i}`));
  // PROPERTIES: round steps from 0, the end past the larger of done and hi by at least 1.1 and less than 1.65 times
  const step = want[1], scale = 10 ** Math.floor(Math.log10(step));
  assert.ok([1, 2, 5].some(m => Math.abs(step - m * scale) < 1e-9 * step) && step >= 1, `${what} step ${step}`);
  assert.ok(want.every((v, i) => Math.abs(v - i * step) < 1e-9 * end), `${what} ticks ${want}`);
  const top = Math.max(done, t.hi);
  assert.ok(end >= Math.max(1, 1.1 * top) && end < 1.65 * Math.max(1, top), `${what} end ${end} for ${top}`);
  close(percent(parts.done.style.width), 100 * done / end, `${what} done`);
  close(percent(parts.band.style.left), 100 * t.lo / end, `${what} band left`);
  close(percent(parts.band.style.width), 100 * (t.hi - t.lo) / end, `${what} band width`);
  close(percent(parts.median.style.left), 100 * t.median / end, `${what} median`);
  for (const e of [parts.band, parts.median, purple]) assert.equal(e.hidden, total === null, what);
  // spec change (dreeves, 2026-11-06: "479M nodes checked" above and "479,017,754 nodes checked" below, "the exact
  // number seems better"): the bar's count exact, as the work paragraph's is
  assert.equal(caption['bar-done'].textContent, done.toLocaleString('en-US'), what);
  assert.equal(caption['bar-range'].textContent, `${compact.format(t.lo)}–${compact.format(t.hi)}`, what);
  assert.equal(caption['bar-median'].textContent, compact.format(t.median), what);
  assert.equal(caption['bar-percent'].textContent, coverage === null ? '' : `${Math.round(100 * coverage)}%`, what);
}
// malformed models fail loudly, before anything is drawn from them
const good = {lo: 7.8e8, median: 1.27e9, hi: 2.5e9};
for (const run of [model(-1, good), model(NaN, good), model('5', good), model(9e8, good), model(1e8, {...good, lo: 1.3e9}),
                   model(1e8, {...good, median: 2.6e9}), model(1e8, {...good, hi: Infinity}), model(1e8, {...good, lo: '7'}),
                   model(1e8, good, 1), model(1e8, good, 0), model(1e8, good, 1.1), model(1e8, good, '0.9'), model(1e8, good, NaN),
                   {work_eta: {...model(1e8, good).work_eta, interval: 'confidence'}},
                   // a model's data without a total: null says it makes no forecast, an absent total breaks the contract
                   {work_eta: (({total, ...rest}) => rest)(model(1e8, good).work_eta)}]) {
  assert.throws(() => context.draw(box, run), /^Error: \[/, JSON.stringify(run));   // the page's assert: its message the JSON of what failed
}

// The markup: index.html's run template, its comments left out (retired captions are kept verbatim in them).
// Spec change (Claude, 2026-11-06): dreeves's f6d809b made the caption "N nodes checked / ~lo–hi" and commented out
// its percent, its median and the note under it, so the markup's checks ask only for the fields it shows.
const template = html.match(/<template class="progress-run">([\s\S]*?)<\/template>/)[1].replace(/<!--[\s\S]*?-->/g, '');
const container = template.match(/<div class="progress-work" data-work-measure="work" hidden>([\s\S]*?)<p class="progress-bar-caption">([\s\S]*?)<\/p>\s*<\/div>/);
assert.ok(container, 'the bar\'s container, with its caption last');
assert.match(container[1], /<div class="progress-bar" aria-hidden="true"><span data-bar="done"><\/span><span data-bar="band" data-bar-total><\/span><i data-bar="median" data-bar-total><\/i><\/div>/);
assert.match(container[1], /<div class="progress-bar-axis" aria-hidden="true" data-bar="ticks"><\/div>/);
assert.match(container[2], /<span class="spent">[^]*<b data-bar-done><\/b>[^]*<\/span>\s*<span class="total" data-bar-total>[^]*<b data-bar-range><\/b>[^]*<\/span>/);
// the blue part (up to its own end tag: it holds no span): the nodes checked, then the rate
const blue = container[2].match(/<span class="spent">([^]*?)<\/span>/)[1];
assert.ok(blue.includes('<b data-bar-done></b>') && blue.indexOf('<b data-bar-done></b>') < blue.indexOf('<b data-work-rate></b>'), blue);
assert.doesNotMatch(template, /data-work-(eta|samples|source_time)\b/, 'a field of the work paragraph, its samples or its source time');
// Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good argument for
// salvaging anything. the up-to-date probability that a bipartition exists is great.", and "for anti-magic i don't want
// to conditionally include or exclude graphs"): the bar's container is the template's one part with a basis
// (data-work-measure); the chance line's work figures went with that line, and the sea's and the runs line's basis,
// which hid them for a run with a work model, went the same night.
assert.equal((template.match(/data-work-measure=/g) || []).length, 1, 'the bar\'s container, the one part with a basis');
assert.equal((template.match(/data-work-measure="work"/g) || []).length, 1, 'the bar\'s container');
// workView shows the container exactly when the run has a work model, and fills the model's rate in (the box holds no
// work paragraph: workView queried one until 2026-11-06)
const shown = {dataset: {workMeasure: 'work'}, hidden: true};
const rate = {textContent: ''};
const fields = {querySelectorAll: s => s === '[data-work-rate]' ? [rate] : []};
const viewBox = {querySelector: s => undefined,
                 querySelectorAll: s => s === '[data-work-measure]' ? [shown] : fields.querySelectorAll(s)};
for (const run of [model(468750102, good), {}, {work_eta: null}, model(4e8, null)]) {
  rate.textContent = '';
  context.workView(viewBox, run);
  assert.equal(shown.hidden, !run.work_eta, JSON.stringify(run));
  assert.equal(rate.textContent, run.work_eta ? '1,884.1' : '', JSON.stringify(run));   // model()'s rate, 1884.1
}
// and fills the model's numbers into their fields with no number among its fields null, as a model makes them for a
// search stopped short (total, root_log_sd_posterior and effective_samples null; formtree_eta.attach): workView
// called each value's toLocaleString until 2026-11-06, which threw on null and stopped the section's drawing
const number = {textContent: ''}, filled = {querySelectorAll: s => s === '[data-work-done]' ? [number] : []};
const stopped = {work_eta: {...model(4e8, null).work_eta, root_log_sd_posterior: null, effective_samples: null, forecast_samples: 0, source_time: 1}};
context.workView({querySelector: viewBox.querySelector, querySelectorAll: s => s === '[data-work-measure]' ? [shown] : filled.querySelectorAll(s)}, stopped);
assert.equal(number.textContent, '400,000,000');
