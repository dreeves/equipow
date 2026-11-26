"""Replicata: open the residue proof for 2^128 in the appendix, chart column and cell.
Expectata: the hand proof fits, and opening its details shows the complete runnable check.
Resultata before: desktop justification stretched the line, and the full enumeration was inline.
"""
import unittest

import quals_codes as qc


MEASURE = r'''async () => {
  const frame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const entry = n => document.getElementById('entry-' + n).closest('li');
  const reason = '[data-why^="proof-"]';
  const direct = name => document.querySelector('#pow2-panel ' + name + ' ' + reason);
  const inspect = async proof => {
    const fold = proof.querySelector('details'), summary = fold?.querySelector('summary');
    const code = proof.querySelector('code[data-slot="line"]');
    const visible = e => !!e?.getBoundingClientRect().width && e.checkVisibility();
    const closed = {fold: !!fold, shut: !fold?.open, summary: visible(summary),
      formulas: [...proof.querySelectorAll('.katex')].filter(visible)
        .map(k => k.querySelector('annotation').textContent), text: proof.innerText,
      code: visible(code), align: getComputedStyle(proof.querySelector('p') ?? proof).textAlign};
    summary?.click();
    await frame();
    const codeBox = code?.getBoundingClientRect(), box = proof.getBoundingClientRect();
    const expanded = {open: !!fold?.open, shown: visible(code), text: proof.innerText,
      code: code?.textContent, alignment: code && getComputedStyle(code).textAlign,
      display: code && getComputedStyle(code).display,
      fits: !!codeBox && codeBox.left >= box.left - 1 && codeBox.right <= box.right + 1 &&
        code.scrollWidth <= code.clientWidth + 1 && code.scrollHeight <= code.clientHeight + 1,
      mathErrors: proof.querySelectorAll('.katex-error').length};
    summary?.click();
    await frame();
    return {closed, expanded, reclosed: !fold?.open && !visible(code)};
  };
  const appendix = await inspect(entry(2n ** 128n).querySelector(reason));
  const small = await inspect(entry(64).querySelector(reason));
  const even = entry(40).querySelector(reason);
  const fallback = {kind: even.dataset.why, hasFold: !!even.querySelector('details'),
    visibleCode: even.querySelector('code[data-slot="line"]')?.checkVisibility()};
  const stan = entry(1024).querySelector(reason);
  const control = {kind: stan.dataset.why, math: stan.querySelectorAll('.katex').length,
    hasCode: !!stan.querySelector('code'), hasFold: !!stan.querySelector('details')};
  const chart = [];
  for (const [hash, selector] of [['#k128', '[data-panel-entries]'], ['#k128d33', '[data-panel-body]']]) {
    location.hash = hash;
    await frame();
    chart.push(await inspect(direct(selector)));
  }
  return {proofs: [appendix, ...chart], small, fallback, control};
}'''


class ResidueLayout(unittest.TestCase):
    def check_compact_math(self, closed, order):
        math = ''.join(closed['formulas']).replace(' ', '')
        power = f'3^{{{(order - 1)//2}}}'
        self.assertIn(r'D_1\equiv', math)
        self.assertIn(r'\equiv1\pmod2', math)
        self.assertIn(power + r'\midD_1', math)
        self.assertIn(r'0<|D_1|\le', math)
        self.assertIn('<' + power, math)

    def test_long_residue_proof_folds_its_numeric_check(self):
        for viewport in (qc.DESKTOP, qc.PHONE):
            with self.subTest(width=viewport['width']):
                report = qc.drive(viewport, [['load'], ['js', MEASURE]])
                self.assertEqual(report['errors'], [])
                self.assertTrue(report['steps'][0]['katex'])
                result = report['steps'][1]
                self.assertEqual(result['control']['kind'], 'proof-stan')
                self.assertGreater(result['control']['math'], 0)
                self.assertFalse(result['control']['hasCode'])
                self.assertFalse(result['control']['hasFold'])
                self.assertEqual(result['fallback'], dict(kind='proof-residue', hasFold=False,
                                                         visibleCode=True))
                small = result['small']
                self.check_compact_math(small['closed'], 7)
                self.assertTrue(small['closed']['shut'] and small['expanded']['shown'] and small['reclosed'])
                self.assertIn('22, 21, 21', small['expanded']['code'])
                for source, proof in zip(('appendix', 'column', 'cell'), result['proofs']):
                    with self.subTest(source=source):
                        c, e = proof['closed'], proof['expanded']
                        self.assertTrue(c['fold'], 'the full arithmetic is displayed inline')
                        self.assertTrue(c['shut'] and c['summary'] and not c['code'])
                        self.check_compact_math(c, 161)
                        self.assertNotRegex(c['text'].replace(',', ''), r'\d{21,}')
                        self.assertIn(c['align'], ('start', 'left'))
                        self.assertTrue(e['open'] and e['shown'] and proof['reclosed'])
                        n = 2**128
                        sizes = [(n + 2 - r)//3 for r in range(3)]
                        self.assertIn(', '.join(map(str, sizes)), e['code'])
                        self.assertIn(f'{3**80:,}', e['text'])
                        self.assertIn('Select[', e['code'])
                        self.assertIn(e['alignment'], ('start', 'left'))
                        self.assertEqual(e['display'], 'block')
                        self.assertTrue(e['fits'])
                        self.assertEqual(e['mathErrors'], 0)


if __name__ == '__main__':
    unittest.main()
