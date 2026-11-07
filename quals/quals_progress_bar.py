"""The work bar's geometry, in the real page in headless Chrome, at a desktop's and a phone's width.

Spec change (Claude, 2026-11-06; dreeves: "i don't like how that progress bar looks. can you revamp it in a way that
makes sense to you? also bring back a subtle tick for the median finish time. bigger picture: should that progress bar
be measuring amount of work, not time? the ETA graph is for time. we can still have a 90% CI for amount of work
remaining, right?"): a work bar replaces the time ruler, whose quals these were (Astra's, 2026-11-06).
Spec change (Claude, 2026-11-06; dreeves: "1. add nodes/s to the blue/purple line" and "2. kill the whole line with
number of samples"): the caption's blue part gives the work model's rate after the nodes checked, and the work
paragraph (samples, nodes checked, rate and source time), which showed exactly when the bar did, is gone.
Run from the repository's root: python3 -B quals/quals_progress_bar.py.  With PROGRESS_BAR_ARTIFACTS set to a
directory, each width's report and a screenshot of its last case (the live search's numbers of 2026-11-06) go there.
"""
import copy
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

import quals_index as page


def work_eta(done, total, coverage=0.9):
    """A work model's data as formtree_eta.attach gives it (the live 288:10 run's fields of 2026-11-06), its done,
    total and coverage these."""
    return dict(source_time=1792199990, samples=1024, nodes=1.037e9, done=done, rate=1884.1, roots_done=10,
                roots_total=16, model='importance', interval='conditional', discrepancy_factor=2.117,
                root_discrepancy_factor=2.117, rate_log_sd=0.35, coverage=coverage,
                root_log_sd_posterior=dict(lo=0.35, median=0.52, hi=0.83), effective_samples=2273.9,
                forecast_samples=65536, total=total)


# The cases, one run each, in turn: totals wide, narrow, a point (the search complete) and none (stopped short: its
# model's null fields as attach makes them), at small and huge scales, coverage 0.8 once; a run with no work model;
# and last, for the screenshot, the live search's numbers of 2026-11-06 (scratch/progress-bar-20261106/NOTES.md).
LIVE = work_eta(468750102, dict(median=1270000000.0, lo=780000000.0, hi=2500000000.0))
CASES = [work_eta(9.5e8, dict(median=9.9e8, lo=9.6e8, hi=1.05e9)),
         work_eta(1.2e9, dict(median=1.2e9, lo=1.2e9, hi=1.2e9)),
         dict(work_eta(4e8, None), root_log_sd_posterior=None, effective_samples=None, forecast_samples=0),
         work_eta(1234, dict(median=5000, lo=2000, hi=9000), 0.8),
         work_eta(5e10, dict(median=2e11, lo=6e10, hi=9.9e11)),
         None,
         LIVE]

HARNESS = r"""<script>
(async () => {
  const result = {cases: []}, sleep = ms => new Promise(r => setTimeout(r, ms));
  try {
    const section = document.querySelector('section.progress');
    section.querySelector('details').open = true;
    // Opening a remembered fold can queue both its initial load and its toggle load: both drained first.
    let quiet = 0;
    for (let n = 0; quiet < 2 && n < 80; n++) {
      await sleep(50);
      quiet = window.progressView.data && !document.head.querySelector('script[src^="progress.js?"]') ? quiet + 1 : 0;
    }
    if (quiet < 2) throw Error('snapshot');
    const data = JSON.parse(JSON.stringify(window.progressView.data)), base = data.runs[0];
    const compact = new Intl.NumberFormat('en-US', {notation: 'compact'});
    const rect = e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom}; };
    for (const [i, work] of __CASES__.entries()) {
      window.progressData({made: data.made + i + 1, runs: [{...base, program: 'ftree.py', n: 288, order: 10, work_eta: work}]});
      section.querySelector('.progress-run details').open = true;
      await sleep(50);
      const box = section.querySelector('.progress-run'), q = s => box.querySelector(s);
      const fig = q('.progress-eta'), part = name => q(`[data-bar="${name}"]`);
      const visible = e => e.checkVisibility();
      const rate = q('.progress-bar-caption .spent [data-work-rate]');
      result.cases.push({work, shown: visible(q('.progress-work')),
        rateAfterDone: !!(q('.progress-bar-caption .spent [data-bar-done]').compareDocumentPosition(rate) & Node.DOCUMENT_POSITION_FOLLOWING),
        unshown: box.querySelectorAll('[data-work-eta], [data-work-samples], [data-work-source_time]').length,
        bar: rect(q('.progress-bar')), done: rect(part('done')), band: rect(part('band')), median: rect(part('median')),
        bandShown: visible(part('band')), medianShown: visible(part('median')), purpleShown: visible(q('.progress-bar-caption .total')),
        ticks: [...q('[data-bar="ticks"]').children].map(e => ({text: e.textContent, rect: rect(e), font: parseFloat(getComputedStyle(e).fontSize)})),
        caption: rect(q('.progress-bar-caption')), captionText: q('.progress-bar-caption').textContent,
        fields: {...Object.fromEntries(['bar-done', 'bar-range'].map(f => [f, q(`[data-${f}]`).textContent])), 'work-rate': rate.textContent},
        // spec change (dreeves, 2026-11-06: "479M nodes checked" above and "479,017,754 nodes checked" below, "the
        // exact number seems better"): the bar's count exact, as the work paragraph's was; and (dreeves, 2026-11-06: "1.
        // add nodes/s to the blue/purple line") the rate after it, as workView writes the model's numbers
        want: work && {done: work.done.toLocaleString('en-US'), rate: work.rate.toLocaleString('en-US', {maximumFractionDigits: 1}),
                       range: work.total && `${compact.format(work.total.lo)}–${compact.format(work.total.hi)}`},
        colors: {done: getComputedStyle(part('done')).backgroundColor, spent: getComputedStyle(fig.querySelector('polyline.spent')).stroke,
                 band: getComputedStyle(part('band')).backgroundColor, bandTotal: getComputedStyle(fig.querySelector('polygon.band.total')).fill,
                 median: getComputedStyle(part('median')).backgroundColor, total: getComputedStyle(fig.querySelector('polyline.total')).stroke,
                 captionSpent: getComputedStyle(q('.progress-bar-caption .spent')).color,
                 captionTotal: getComputedStyle(q('.progress-bar-caption .total')).color},
        beforeChart: !!(q('.progress-work').compareDocumentPosition(fig) & Node.DOCUMENT_POSITION_FOLLOWING),
        documentWidth: document.documentElement.scrollWidth, viewport: innerWidth});
    }
    section.querySelector('.progress-run').scrollIntoView();
    await sleep(50);
  } catch (e) { result.error = String(e.stack || e); }
  parent.postMessage(JSON.stringify(result), '*');
})();
</script>"""


def render(width):
    """The harness's report on the page at width (CSS px), in an iframe (page.HOST), at one device px per CSS px."""
    artifacts = os.environ.get('PROGRESS_BAR_ARTIFACTS')
    with tempfile.TemporaryDirectory(prefix='progress-bar-quals-') as d:
        source = page.page().replace('<head>\n', '<head>\n' + page.PROGRESS_REMEMBERED)
        source = source.replace('</body>', HARNESS.replace('__CASES__', json.dumps(CASES)) + '</body>')
        Path(d, 'index.html').write_text(source)
        page.copy_page_dir(d)
        shutil.copy(page.DATA, Path(d, 'mstar.js'))
        shutil.copy(page.POW2, Path(d, 'pow2.js'))
        Path(d, 'progress.js').write_text('progressData(' + json.dumps(copy.deepcopy(page.PROGRESS_DATA)) + ');\n')
        Path(d, 'host.html').write_text(page.HOST.replace('__WIDTH__', str(width)))
        args = [f'--window-size={max(width, 500) + 40},1100', '--force-device-scale-factor=1', '--virtual-time-budget=10000', '--dump-dom']
        if artifacts:
            Path(artifacts).mkdir(parents=True, exist_ok=True)
            args.append('--screenshot=' + str(Path(artifacts, f'bar-{width}.png').resolve()))
        dom = page.chrome(d, args + ['file://' + str(Path(d, 'host.html'))])
        found = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert found, dom[-2000:]
        result = json.loads(html.unescape(found[1]))
        if artifacts: Path(artifacts, f'bar-{width}.json').write_text(json.dumps(result, indent=2))
        return result


def value(label):
    """A compact tick label's number: 0, 500M, 1.5B, 2K, 1T."""
    m = re.fullmatch(r'([0-9.]+)([KMBT]?)', label)
    assert m, label
    return float(m[1]) * {'': 1, 'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}[m[2]]


class ProgressBar(unittest.TestCase):
    def check_width(self, width):
        # Replicata: the page at width with each of CASES in turn as the one run, a form-tree search's, its fold open.
        # Expectata: the bar shown for every case with a work model and not without; no field of the samples or the
        # source time in the run's box, nor the work paragraph (dreeves, 2026-11-06: "2. kill the whole line with number
        # of samples"; the bar was shown exactly when that paragraph was until then); the caption's blue part giving
        # the rate after the nodes checked (dreeves, 2026-11-06: "1. add nodes/s to the blue/purple line"), as the
        # model's numbers are written (a tenth at most, grouped); for each shown, the track's end the last tick's
        # number, at least 1.1 times the larger of done and the total's upper end and less than 1.65 times it; the
        # blue part as wide as done / end of the track, the
        # band from lo / end to hi / end, the median tick centered at median / end (each to a CSS px); the band, the
        # tick and the caption's purple part shown exactly when there is a total; the ticks from 0 in round steps,
        # the first flush with the track's left end, the last with its right, the rest centered on theirs, none
        # overlapping, none past the page's edges, at 11 px or more; the caption's nodes checked exact and the total's
        # range compact (dreeves's caption since f6d809b, 2026-11-06, its percent, median and the note under it
        # commented out); blue, the band and the tick in the ETA chart's colors (its elapsed line's, its band's of elapsed +
        # ETA, its line of elapsed + ETA), and the caption's parts too; the bar above the ETA chart; the caption within
        # the page; and no sideways scroll (dreeves, 2026-10-29: a phone shows no wider page).
        # Resultata: the measured geometry, colors or visibility that differ.
        result = render(width)
        self.assertNotIn('error', result, result.get('error'))
        self.assertEqual(len(result['cases']), len(CASES))
        for c in result['cases']:
            work = c['work']
            with self.subTest(width=width, work=work):
                self.assertEqual(c['shown'], work is not None)
                self.assertEqual(c['unshown'], 0)
                self.assertTrue(c['rateAfterDone'])
                self.assertLessEqual(c['documentWidth'], width)
                if work is None: continue
                self.assertEqual(c['fields']['work-rate'], c['want']['rate'])
                done, total = work['done'], work['total']
                t = total or dict(lo=done, median=done, hi=done)
                ticks = [value(k['text']) for k in c['ticks']]
                end, top = ticks[-1], max(done, t['hi'])
                self.assertGreaterEqual(end, max(1, 1.1 * top))
                self.assertLess(end, 1.65 * max(1, top))
                step = ticks[1]
                self.assertEqual(ticks, [i * step for i in range(len(ticks))])
                self.assertIn(round(step / 10 ** math.floor(math.log10(step)), 9), (1, 2, 5))
                x0, W = c['bar']['x'], c['bar']['width']
                at = lambda v: x0 + W * v / end
                self.assertAlmostEqual(c['done']['x'], x0, delta=1)
                self.assertAlmostEqual(c['done']['right'], at(done), delta=1)
                self.assertEqual(c['bandShown'], total is not None)
                self.assertEqual(c['medianShown'], total is not None)
                self.assertEqual(c['purpleShown'], total is not None)
                if total is not None:
                    self.assertAlmostEqual(c['band']['x'], at(t['lo']), delta=1)
                    self.assertAlmostEqual(c['band']['right'], at(t['hi']), delta=1)
                    self.assertAlmostEqual((c['median']['x'] + c['median']['right']) / 2, at(t['median']), delta=1)
                    self.assertLess(c['median']['y'], c['bar']['y'])
                    self.assertGreater(c['median']['bottom'], c['bar']['bottom'])
                    self.assertEqual(c['fields']['bar-range'], c['want']['range'])
                self.assertEqual(c['fields']['bar-done'], c['want']['done'])
                rects = [k['rect'] for k in c['ticks']]
                self.assertAlmostEqual(rects[0]['x'], x0, delta=1)
                self.assertAlmostEqual(rects[-1]['right'], x0 + W, delta=1)
                for v, r in zip(ticks[1:-1], rects[1:-1]):
                    self.assertAlmostEqual((r['x'] + r['right']) / 2, at(v), delta=1)
                for a, b in zip(rects, rects[1:]):
                    self.assertLess(a['right'], b['x'])
                for k in c['ticks']:
                    self.assertGreaterEqual(k['font'], 11)
                    self.assertGreaterEqual(k['rect']['x'], 0)
                    self.assertLessEqual(k['rect']['right'], width)
                    self.assertGreater(k['rect']['y'], c['bar']['bottom'])
                colors = c['colors']
                self.assertEqual(colors['done'], colors['spent'])
                self.assertEqual(colors['band'], colors['bandTotal'])
                self.assertEqual(colors['median'], colors['total'])
                self.assertEqual(colors['captionSpent'], colors['spent'])
                self.assertEqual(colors['captionTotal'], colors['total'])
                self.assertTrue(c['beforeChart'])
                self.assertGreaterEqual(c['caption']['x'], 0)
                self.assertLessEqual(c['caption']['right'], width)

    def test_desktop(self): self.check_width(1280)
    def test_phone(self): self.check_width(390)


if __name__ == '__main__': unittest.main()
