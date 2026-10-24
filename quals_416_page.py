"""Quals for the displayed construction and proof of m*(416) = 9.

Replicata: read the seed, constructed witness, and residue data from index.html.
Expectata: the displayed signs have exact order 9 and the displayed necessary
residue conditions exclude order 10. Resultata before the edit: no 416 proof.
"""

from html import unescape
from math import comb
from pathlib import Path
import re
import unittest


PAGE = Path(__file__).with_name('index.html')


def field(page, name):
    value, = re.findall(rf'<[^>]+ id="{name}"[^>]*>(.*?)</[^>]+>', page, re.S)
    return unescape(re.sub(r'<[^>]*>', '', value)).strip()


def signs(code, order):
    half = [2 * int(bit) - 1 for digit in code
            for bit in f'{int(digit, 16):04b}']
    return half + [(-1) ** order * x for x in reversed(half)]


class Quals(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text()

    def test_published_seed_has_exact_order_eight(self):
        seed = signs(field(self.page, 'seed416'), 8)
        self.assertEqual(len(seed), 208)
        moments = [sum(s * i ** k for i, s in enumerate(seed))
                   for k in range(9)]
        self.assertEqual(moments[:8], [0] * 8)
        self.assertNotEqual(moments[8], 0)

    def test_displayed_witness_is_the_construction_and_has_order_nine(self):
        seed = signs(field(self.page, 'seed416'), 8)
        witness = signs(field(self.page, 'witness416'), 9)
        self.assertEqual(len(witness), 416)
        self.assertEqual(witness, seed + [-s for s in seed])
        for offset in (0, 1):
            moments = [sum(s * (i + offset) ** k
                           for i, s in enumerate(witness)) for k in range(10)]
            self.assertEqual(moments[:9], [0] * 9)
            self.assertNotEqual(moments[9], 0)

    def test_displayed_residue_conditions_exclude_every_candidate(self):
        sizes = tuple(map(int, field(self.page, 'sizes416').split(', ')))
        modulus = int(field(self.page, 'modulus416'))
        self.assertEqual(sizes, tuple(len(range(r, 416, 3)) for r in range(3)))
        # Reduce (x-1)^10 modulo x^2+x+1 independently of mstar's lattice.
        remainder = [0, 0]
        powers = ((1, 0), (0, 1), (-1, -1))
        for k in range(11):
            for j in range(2):
                remainder[j] += (-1) ** (10-k) * comb(10, k) * powers[k % 3][j]
        self.assertEqual(remainder, [modulus, modulus])
        candidates = [(a, b, -a-b)
                      for a in range(-sizes[0], sizes[0]+1, 2)
                      for b in range(-sizes[1], sizes[1]+1, 2)
                      if abs(a+b) <= sizes[2]
                      and (-a-b-sizes[2]) % 2 == 0
                      and (2*a+b) % modulus == 0
                      and (a+2*b) % modulus == 0]
        self.assertEqual(candidates, [])

    def test_proof_links_the_primary_source_and_preserves_seed_credit(self):
        proof, = re.findall(r'<div id="proof416"[^>]*>(.*?)</div>', self.page, re.S)
        self.assertIn('https://arxiv.org/html/1912.03491v1#S6.T5', proof)
        self.assertIn('BGPW', proof)
        self.assertIn('lang="en"', self.page[self.page.index('<div id="proof416"'):][:60])
        self.assertIn('TODO:', proof)

    def test_english_prose_is_quoted_and_attributed_to_astra(self):
        # Replicata: read every paragraph in the 416 proof after translation.
        # Expectata (dreeves, 2026-10-24): model-written English is explicitly
        # quoted with Astra: prepended; the earlier Latin is gone.
        proof, = re.findall(r'<div id="proof416"[^>]*>(.*?)</div>\s*</li>',
                            self.page, re.S)
        paragraphs = re.findall(r'<p>(.*?)</p>', proof, re.S)
        self.assertTrue(paragraphs)
        for paragraph in paragraphs:
            words = unescape(re.sub(r'<[^>]*>', '', paragraph)).strip()
            self.assertTrue(words.startswith('Astra: "'), words)
            self.assertTrue(words.endswith('"'), words)
        for latin in ('Ad ordinem', 'Sit ζ radix', 'Differentia', 'Itaque'):
            self.assertNotIn(latin, proof)


if __name__ == '__main__':
    unittest.main()
