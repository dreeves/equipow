"""Replicata: open the typeset proofs in desktop and phone Chrome viewports.
Expectata: no vertical equation scrollbars, unclipped notation, horizontal scrolling.
Resultata: measured bounds identify the offending formula and viewport.

Run outside the workspace sandbox as AGENTS.md requires for Chrome quals.
"""
import unittest
from unittest.mock import patch

import quals_codes as qc


MEASURE = r'''async () => {
  document.querySelectorAll('.proof-exposition').forEach(d => d.open = true);
  await document.fonts.ready;
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const rows = [...document.querySelectorAll('.proof-body .proof-equation')].map(p => {
    const b = p.getBoundingClientRect(), s = getComputedStyle(p), boxes = [];
    const walk = document.createTreeWalker(p.querySelector('.katex-html'), NodeFilter.SHOW_TEXT);
    for (let t = walk.nextNode(); t; t = walk.nextNode()) {
      if (!t.data.replace(/\s|\u200b/g, '')) continue;
      const r = document.createRange(); r.selectNodeContents(t);
      boxes.push(...r.getClientRects());
    }
    // Text ranges cover glyph boxes; these cover drawn rules and SVG notation.
    p.querySelectorAll('.katex-html .frac-line, .katex-html .overline-line, .katex-html svg')
      .forEach(e => boxes.push(e.getBoundingClientRect()));
    const result = {
      tex: p.querySelector('annotation').textContent,
      overflowX: s.overflowX, overflowY: s.overflowY,
      clientHeight: p.clientHeight, scrollHeight: p.scrollHeight,
      clientWidth: p.clientWidth, scrollWidth: p.scrollWidth,
      top: Math.min(...boxes.map(r => r.top - b.top)),
      bottom: Math.max(...boxes.map(r => r.bottom - b.top))
    };
    p.scrollLeft = p.scrollWidth;
    result.end = p.scrollLeft;
    p.scrollLeft = 0;
    return result;
  });
  return {rows, width: innerWidth, scrollWidth: document.documentElement.scrollWidth};
}'''


class ProofLayout(unittest.TestCase):
    def test_equations_fit_and_scroll_only_horizontally(self):
        # The shared harness normally hides scrollbars; this qual must allow them.
        with patch.object(qc, 'DRIVER', qc.DRIVER.replace("'--hide-scrollbars', ", '')):
            for viewport in (qc.DESKTOP, qc.PHONE):
                with self.subTest(width=viewport['width']):
                    report = qc.drive(viewport, [['load'], ['js', MEASURE]])
                    self.assertNotIn('error', report)
                    self.assertEqual(report['errors'], [])
                    self.assertTrue(report['steps'][0]['katex'])
                    measured = report['steps'][-1]
                    self.assertLessEqual(measured['scrollWidth'], measured['width'])
                    self.assertTrue(measured['rows'])
                    for r in measured['rows']:
                        with self.subTest(tex=r['tex']):
                            vertical = (r['overflowY'] in ('auto', 'scroll') and
                                        r['scrollHeight'] > r['clientHeight'])
                            self.assertFalse(vertical, r)
                            # A pixel allows CSSOM's integer rounding, not clipping.
                            self.assertGreaterEqual(r['top'], -1, r)
                            self.assertLessEqual(r['bottom'], r['clientHeight'] + 1, r)
                            self.assertEqual(r['overflowX'], 'auto', r)
                            self.assertAlmostEqual(r['end'], r['scrollWidth'] - r['clientWidth'], delta=1)
                    if viewport == qc.PHONE:
                        self.assertTrue(any(r['end'] > 0 for r in measured['rows']))


if __name__ == '__main__':
    unittest.main()
