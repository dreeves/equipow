"""Time-bar geometry and pairing in isolated desktop and phone browser fixtures."""
import copy
import html
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

import quals_index as page


HARNESS = r"""<script>
(async () => {
  const result = {cases: []}, sleep = ms => new Promise(r => setTimeout(r, ms));
  try {
    const section = document.querySelector('section.progress');
    section.querySelector('details').open = true;
    // Opening a remembered fold can queue both its initial load and its toggle load.
    // Drain both before the fixture starts publishing its own snapshots.
    let quiet=0;
    for (let n=0; quiet<2 && n<80; n++) {
      await sleep(50);
      quiet=window.progressView.data && !document.head.querySelector('script[src^="progress.js?"]') ? quiet+1 : 0;
    }
    if (quiet<2) throw Error('snapshot');
    const data = JSON.parse(JSON.stringify(window.progressView.data)), base = data.runs[0];
    const scenarios = [
      {to_go: {lo:1800, median:3600, hi:10800}, so_far:7200, coverage:.9},
      {to_go: {lo:1800, median:3600, hi:10800}, so_far:360000},
      {to_go: {lo:12947400, median:27000000, hi:203045040}, so_far:51120},
      {to_go: {lo:3600, median:3600, hi:3600}, so_far:7200},
      {to_go: {lo:0, median:0, hi:0}, so_far:0},
      {to_go:null, so_far:7200},
      {to_go:null, so_far:0},
    ];
    const rect = e => {const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
    for (const [i, s] of scenarios.entries()) {
      const run = {...base, so_far:s.so_far, to_go:s.to_go,
        etas:s.to_go ? [[data.made, s.so_far, s.to_go.median, s.to_go.lo, s.to_go.hi]] : [],
        work_eta: s.coverage ? {coverage:s.coverage, interval:'conditional',samples:1024,done:12000,rate:2500,source_time:data.made} : null};
      window.progressData({made:data.made+i+1,runs:[run]});
      let box=section.querySelector('.progress-run'); box.querySelector('details').open=true;
      await sleep(50);
      box=section.querySelector('.progress-run');
      const bar=box.querySelector('.progress-bar'), fig=box.querySelector('.progress-eta');
      const band=bar.querySelector('[data-bar="band"]'), median=bar.querySelector('[data-bar="median"]');
      const brace=bar.querySelector('.progress-brace'), timing=box.querySelector('.progress-time');
      result.cases.push({scenario:s, bar:rect(bar), band:rect(band), median:rect(median),
        brace:brace ? rect(brace) : null, medianHidden:median.hidden, bandHidden:band.hidden,
        paired:!!timing && timing.contains(bar) && timing.contains(fig) && !timing.contains(box.querySelector('canvas')),
        beforeDots:!!(fig.compareDocumentPosition(box.querySelector('canvas'))&Node.DOCUMENT_POSITION_FOLLOWING),
        blue:getComputedStyle(bar.querySelector('[data-bar="so-far"]')).backgroundColor,
        graphBlue:getComputedStyle(fig.querySelector('polyline.spent')).stroke,
        purple:brace ? getComputedStyle(brace).stroke : null,
        graphPurple:getComputedStyle(fig.querySelector('polyline.total')).stroke,
        coverage:box.querySelector('[data-bar-coverage]')?.hidden,
        documentWidth:document.documentElement.scrollWidth, viewport:innerWidth,
        caption:rect(box.querySelector('.progress-bar-caption')), graph:rect(fig)});
    }
    window.progressData({made:data.made+100,runs:[{...base,work_eta:{coverage:.9,interval:'conditional',samples:1024,done:12000,rate:2500,source_time:data.made}}]});
    section.querySelector('.progress-run details').open=true;
    section.scrollIntoView();
    await sleep(50);
  } catch(e) {result.error=String(e.stack||e);}
  parent.postMessage(JSON.stringify(result),'*');
})();
</script>"""


def render(width):
    artifacts = os.environ.get('PROGRESS_BAR_ARTIFACTS')
    with tempfile.TemporaryDirectory(prefix='progress-bar-quals-') as d:
        source = page.page().replace('<head>\n', '<head>\n' + page.PROGRESS_REMEMBERED)
        source = source.replace('</body>', HARNESS + '</body>')
        Path(d, 'index.html').write_text(source)
        page.copy_page_dir(d)
        shutil.copy(page.DATA, Path(d, 'mstar.js'))
        shutil.copy(page.POW2, Path(d, 'pow2.js'))
        Path(d, 'progress.js').write_text('progressData('+json.dumps(copy.deepcopy(page.PROGRESS_DATA))+');\n')
        Path(d, 'host.html').write_text(page.HOST.replace('__WIDTH__', str(width)))
        args = [f'--window-size={max(width,500)+40},1100', '--force-device-scale-factor=1',
                '--virtual-time-budget=10000', '--dump-dom']
        if artifacts:
            Path(artifacts).mkdir(parents=True, exist_ok=True)
            args.append('--screenshot='+str(Path(artifacts, f'bar-{width}.png').resolve()))
        dom = page.chrome(d, args+['file://'+str(Path(d,'host.html'))])
        found = re.search(r'<pre id="harness-out">(.*?)</pre>',dom,re.S)
        assert found, dom[-2000:]
        result = json.loads(html.unescape(found[1]))
        if artifacts: Path(artifacts,f'bar-{width}.json').write_text(json.dumps(result,indent=2))
        return result


class ProgressBar(unittest.TestCase):
    def check_width(self, width):
        # Replicata: actual page with broad, narrow, point, zero and absent estimates.
        # Expectata: the bar pairs with the graph, encodes the same durations and colors, and fits its viewport.
        # Resultata: measured geometry identifies a missing mark, wrong interval, overflow or unsupported label.
        result = render(width)
        self.assertNotIn('error',result,result.get('error'))
        for c in result['cases']:
            with self.subTest(width=width,scenario=c['scenario']):
                s,g=c['scenario'],c['scenario']['to_go']
                self.assertTrue(c['paired'])
                self.assertTrue(c['beforeDots'])
                self.assertEqual(c['blue'],c['graphBlue'])
                self.assertEqual(c['purple'],c['graphPurple'])
                self.assertLessEqual(c['documentWidth'],width+1)
                self.assertLessEqual(c['caption']['right'],width)
                self.assertLessEqual(c['graph']['right'],width)
                self.assertEqual(c['medianHidden'],g is None)
                self.assertEqual(c['bandHidden'],g is None)
                self.assertEqual(c['coverage'],not bool(s.get('coverage')))
                if g is not None:
                    total=s['so_far']+g['hi'] or 1
                    start=c['bar']['x'];scale=c['bar']['width']/total
                    self.assertAlmostEqual(c['band']['x'],start+(s['so_far']+g['lo'])*scale,delta=1)
                    self.assertAlmostEqual(c['band']['width'],(g['hi']-g['lo'])*scale,delta=1)
                    self.assertAlmostEqual(c['median']['x']+c['median']['width']/2,start+(s['so_far']+g['median'])*scale,delta=1)
                    self.assertIsNotNone(c['brace'])
                    self.assertAlmostEqual(c['brace']['width'],c['band']['width'],delta=1)
                    self.assertGreater(c['median']['width'],8)
                    self.assertGreater(c['median']['height'],8)

    def test_desktop(self): self.check_width(1280)
    def test_phone(self): self.check_width(390)


if __name__ == '__main__': unittest.main()
