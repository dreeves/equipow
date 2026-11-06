"""Time-ruler geometry and pairing in isolated desktop and phone browser fixtures."""
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
      {to_go:null, so_far:7200, state:'paused'},
      {to_go:null, so_far:7200, state:'ended', outcome:'excluded'},
      {to_go:{lo:0,median:0,hi:0}, so_far:7200},
      {to_go:{lo:1800,median:3600,hi:10800}, so_far:7200, stale:0},
    ];
    const rect = e => {const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
    for (const [i, s] of scenarios.entries()) {
      const run = {...base, state:'running', ...s,
        etas:s.to_go ? [[data.made, s.so_far, s.to_go.median, s.to_go.lo, s.to_go.hi]] : [],
        work_eta: s.coverage ? {coverage:s.coverage, interval:'conditional',samples:1024,done:12000,rate:2500,source_time:data.made} : null};
      window.progressData({made:data.made+i+1,runs:[run]});
      let box=section.querySelector('.progress-run'); box.querySelector('details').open=true;
      await sleep(50);
      box=section.querySelector('.progress-run');
      const bar=box.querySelector('.progress-bar'), fig=box.querySelector('.progress-eta');
      const band=bar.querySelector('[data-bar="band"]'), now=bar.querySelector('[data-bar="now"]');
      const timing=box.querySelector('.progress-time'), ticks=[...bar.querySelectorAll('[data-bar="ticks"] > span')];
      result.cases.push({scenario:s, bar:rect(bar), band:rect(band), now:now ? rect(now) : null,
        median:!!bar.querySelector('[data-bar="median"]'), bandHidden:band.hidden,
        live:box.querySelector('[data-bar-live]')?.hidden, recorded:box.querySelector('[data-bar-recorded]')?.hidden,
        markerLabel:now ? rect(now.querySelector('span')) : null,
        ticks:ticks.map(e=>({text:e.textContent,rect:rect(e),font:parseFloat(getComputedStyle(e).fontSize)})),
        capHeight:parseFloat(getComputedStyle(band,'::after').height),
        paired:!!timing && timing.contains(bar) && timing.contains(fig) && !timing.contains(box.querySelector('canvas')),
        beforeDots:!!(fig.compareDocumentPosition(box.querySelector('canvas'))&Node.DOCUMENT_POSITION_FOLLOWING),
        blue:getComputedStyle(bar.querySelector('[data-bar="so-far"]')).backgroundColor,
        graphBlue:getComputedStyle(fig.querySelector('polyline.spent')).stroke,
        purple:getComputedStyle(band).borderTopColor,
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
        # Spec change authorized by dreeves, 2026-11-06: a time ruler, no median circle/100%-track.
        # Replicata: actual page with broad, narrow, point, zero, absent, stopped and stale estimates.
        # Expectata: one labeled elapsed marker and a separate interval, with readable time ticks beyond it.
        # Resultata: measured geometry identifies a misleading marker, wrong interval, overflow or label collision.
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
                self.assertFalse(c['median'])
                self.assertIsNotNone(c['now'])
                self.assertEqual(c['bandHidden'],g is None)
                self.assertEqual(c['coverage'],not bool(s.get('coverage')))
                live=s.get('state','running')=='running' and s.get('stale') is None
                self.assertEqual(c['live'],not live)
                self.assertEqual(c['recorded'],live)
                self.assertGreaterEqual(c['markerLabel']['x'],0)
                self.assertLessEqual(c['markerLabel']['right'],width)
                ticks=c['ticks']
                self.assertGreaterEqual(len(ticks),2)
                self.assertLessEqual(len(ticks),7)
                value,unit=ticks[-1]['text'].split()
                total=float(value)*{'h':3600,'d':86400,'y':31557600}[unit]
                self.assertGreater(total,s['so_far']+(g['hi'] if g else 0))
                start=c['bar']['x'];scale=c['bar']['width']/total
                self.assertAlmostEqual(c['now']['x'],start+s['so_far']*scale,delta=1)
                for a,b in zip(ticks,ticks[1:]):
                    self.assertLess(a['rect']['right'],b['rect']['x'])
                for t in ticks:
                    self.assertGreaterEqual(t['font'],11)
                    self.assertGreaterEqual(t['rect']['x'],0)
                    self.assertLessEqual(t['rect']['right'],width)
                    self.assertLess(c['markerLabel']['bottom'],t['rect']['y'])
                if g is not None:
                    self.assertAlmostEqual(c['band']['x'],start+(s['so_far']+g['lo'])*scale,delta=1)
                    self.assertAlmostEqual(c['band']['width'],(g['hi']-g['lo'])*scale,delta=1)
                    self.assertGreater(c['capHeight'],5)
                    self.assertLess(c['band']['y'],c['now']['bottom'])

    def test_desktop(self): self.check_width(1280)
    def test_phone(self): self.check_width(390)


if __name__ == '__main__': unittest.main()
