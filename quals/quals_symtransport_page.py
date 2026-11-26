"""Quals for the constructive symmetry proof, its order-15 witness and the first candidate.

Replicata: read the proofs as displayed in the Symmetry section of index.html.
Expectata: the constructive bound, witness and endpoint have their mathematical steps, arithmetic,
and references to their sources. Resultata before: Table 5's only general bound was Fourier's.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
HUB = 'https://github.com/dreeves/equipow/blob/main/'


def fold(name):
    page = re.sub(r'<!--.*?-->', '', (ROOT / 'index.html').read_text(), flags=re.S)
    section, = re.findall(r'<section class="symmetry".*?</section>', page, re.S)
    # A fragment inside a closed fold reveals it when followed, including from a chart row.
    # With the id on <details> itself Chrome scrolled to the closed summary.
    bodies = re.findall(r'<details class="ai"[^>]*>(.*?)</details>', section, re.S)
    body, = [body for body in bodies if f'id="{name}"' in body.partition('</summary>')[2]]
    return body


def math(body):
    """The typeset expressions, without their grouping commas and spaces."""
    return '\n'.join(re.findall(r'\\\((.*?)\\\)', body, re.S)).replace('{,}', '').replace(' ', '')


class SymmetryExposition(unittest.TestCase):
    def test_general_construction_and_exact_order(self):
        body = fold('symtransport')
        formulas = math(body)
        for step in (r'2^{Cm}', r'Q\le(m/2)2^{5m/2}', r'h_\ell=(d+1)(KQ+\ell)',
                     r'L\equivT\pmod{2T}', r'L+2LH/T+2H'):
            self.assertIn(step, formulas)
        for href in ('#symlarge-s2', HUB + 'proofs/symtransport.py',
                     'https://ronny.cswp.cs.technion.ac.il/wp-content/uploads/sites/54/2016/05/spect.pdf'):
            self.assertIn(f'href="{href}"', body)

    def test_witness_length_and_tail(self):
        body = fold('sym15')
        formulas = math(body)
        side, center, length = map(int, re.search(r'2\\cdot(\d+)\+(\d+)=(\d+)', formulas).groups())
        self.assertEqual((side, center, 2*side + center), (397280, 720, length))
        start, second, end = map(int, re.search(r'(\d+),(\d+),\\ldots,(\d+)', formulas).groups())
        self.assertEqual((start, second), (6128, start+16))
        self.assertEqual((end - start) // 16 + 1, 960 // 16)
        self.assertIn(f'{length}+2\\cdot{start}={length + 2*start}', formulas)
        self.assertIn(f'href="{HUB}proofs/sym15.py"', body)

    def test_endpoint_and_mirror_pairs(self):
        body = fold('sym33360')
        formulas = math(body)
        n = 33360
        for cost in (2*3**7-3, 6*5**3-5, 6*7**2-7):
            self.assertIn(str(cost), formulas)
        self.assertIn(str(n), formulas)
        self.assertIn(str((n - 2**15)//4), formulas)
        self.assertIn(str(n//2), formulas)
        self.assertIn('292,296,488,488,492,492', formulas)
        self.assertIn('href="#entry-528"', body)
        self.assertIn('href="#progress-title"', body)


if __name__ == '__main__':
    unittest.main()
