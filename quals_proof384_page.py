"""Quals for the independently checkable publication of m*(384) = 10.

Replicata: read the witness, counts, and certificates from proof384.html.
Expectata: exact arithmetic proves the lower bound and excludes every
order-11 case using the data actually displayed to the reader.
Resultata before publication: proof384.html is absent, so these quals are red.
"""

from html import unescape
from itertools import product
from math import comb
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent
N = 384
SIZES = (77, 77, 77, 77, 76)


def text(fragment):
    return unescape(re.sub(r'<[^>]*>', '', fragment)).strip()


def table(page, name):
    """Read displayed data cells, excluding the table's header rows."""
    body, = re.findall(
        rf'<table\b[^>]*\bid="{name}"[^>]*>(.*?)</table>', page, re.S)
    rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', body, re.S)
    cells = [re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S) for row in rows]
    return [tuple(text(cell) for cell in row) for row in cells if row]


def necessary_counts():
    """Derive a necessary superset, independently of proof384.py."""
    generator = tuple(sum((-1) ** (11 - k) * comb(11, k)
                          for k in range(r, 12, 5)) for r in range(5))

    def admissible(d):
        return (sum(d) == 0
                and all(v % 25 == 0 for v in d)
                and (d[2] - 4 * d[0] - 2 * d[1]) % 125 == 0
                and (d[3] - 3 * d[0] - 3 * d[1]) % 125 == 0)

    assert generator == (450, -450, 275, 0, -275)
    assert all(admissible(generator[r:] + generator[:r]) for r in range(5))
    choices = [tuple(d for d in range(-size, size + 1, 2) if d % 25 == 0)
               for size in SIZES]
    return {tuple((d + size) // 2 for d, size in zip(vector, SIZES))
            for vector in product(*choices) if admissible(vector)}


class Proof384PageQuals(unittest.TestCase):
    def setUp(self):
        self.page = (ROOT / 'proof384.html').read_text()

    def test_sources_and_reproduction_commands_are_published(self):
        for target in ('index.html', 'proof384.py', 'quals_proof384.py',
                       'quals_proof384_page.py'):
            self.assertRegex(self.page, rf'href="{re.escape(target)}"')
            self.assertTrue((ROOT / target).is_file())
        visible = text(self.page)
        self.assertIn('href="proof384.html"', (ROOT / 'index.html').read_text())
        self.assertIn('python3 proof384.py', visible)
        self.assertIn('python3 -m unittest quals_proof384 quals_proof384_page',
                      visible)

    def test_published_witness_proves_the_lower_bound(self):
        encoded, = re.findall(r'<code\b[^>]*\bid="witness"[^>]*>(.*?)</code>',
                              self.page, re.S)
        encoded = text(encoded)
        self.assertRegex(encoded, r'\A[0-9A-F]{48}\Z')
        half = tuple(2 * int(bit) - 1
                     for digit in encoded for bit in f'{int(digit, 16):04b}')
        signs = half + half[::-1]
        self.assertEqual(len(signs), N)
        tenth, = re.findall(r'<code\b[^>]*\bid="moment10"[^>]*>(.*?)</code>',
                            self.page, re.S)
        for offset in (0, 1):
            moments = tuple(sum(sign * (p + offset) ** k
                                for p, sign in enumerate(signs))
                            for k in range(11))
            self.assertEqual(moments[:10], (0,) * 10)
            self.assertNotEqual(moments[10], 0)
            self.assertEqual(moments[10], int(text(tenth)))

    def test_published_counts_cover_every_possible_order11_solution(self):
        rows = [tuple(map(int, row)) for row in table(self.page, 'counts')]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(len(row) == 7 for row in rows))
        self.assertEqual({row[:5] for row in rows}, necessary_counts())
        for *counts, r, s in rows:
            self.assertEqual((counts[r], counts[s]), (1, 76))
            self.assertEqual((SIZES[r], SIZES[s]), (77, 77))

    def test_published_certificates_exclude_every_position_pair(self):
        rows = table(self.page, 'certificates')
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(len(row) == 4 for row in rows))
        certificates = {}
        for first, second, modulus, vector in rows:
            pair = (int(first), int(second))
            coefficients = tuple(map(int, vector.strip('()').split(',')))
            self.assertEqual(len(coefficients), 16)
            self.assertIn(int(modulus), (25, 125, 625))
            certificates.setdefault(pair, []).append((int(modulus), coefficients))
        self.assertEqual(set(certificates), {(0, 3), (1, 2)})
        self.assertTrue(all(len(group) == 4 for group in certificates.values()))

        published = [tuple(map(int, row)) for row in table(self.page, 'survivors')]
        self.assertEqual(len(published), 4)
        self.assertTrue(all(len(row) == 6 for row in published))
        levels = {row[:2]: row[2:] for row in published}
        self.assertEqual(len(levels), 4)
        last_rows = [tuple(map(int, row))
                     for row in table(self.page, 'last-cases')]
        self.assertEqual(len(last_rows), 4)
        self.assertTrue(all(len(row) == 6 for row in last_rows))
        last_cases = {row[:2]: row[2:] for row in last_rows}
        self.assertEqual(set(last_cases), set(levels))
        moment_sums = tuple(comb(N, k + 1) for k in range(11))
        self.assertTrue(all(value % 2 == 0 for value in moment_sums))

        checked = 0
        seen = set()
        for counts in sorted(necessary_counts()):
            r, s = counts.index(1), counts.index(76)
            seen.add((r, s))
            rhs = tuple(value // 2 for value in moment_sums) + counts
            candidates = set(product(range(77), repeat=2))
            actual_levels = []
            history = []
            for modulus, coefficients in certificates[tuple(sorted((r, s)))]:
                # Evaluate the published integer polynomial plus its count row.
                values = tuple(sum(coefficients[k] * comb(p, k)
                                   for k in range(11)) + coefficients[11 + p % 5]
                               for p in range(N))
                free = tuple(p for p in range(N) if p % 5 not in (r, s))
                self.assertEqual(len(free), 230)
                self.assertTrue(all(values[p] % modulus == 0 for p in free))
                residual = (sum(a * b for a, b in zip(coefficients, rhs))
                            - sum(values[p] for p in range(s, N, 5)))
                candidates = {(i, j) for i, j in candidates
                              if (residual - values[r + 5 * i]
                                  + values[s + 5 * j]) % modulus == 0}
                actual_levels.append(len(candidates))
                history.append(candidates)
            self.assertEqual(tuple(actual_levels), levels[(r, s)])
            self.assertEqual(tuple(actual_levels), (1187, 45, 9, 0))
            self.assertFalse(candidates)
            i0, j0, lifts, remainder = last_cases[(r, s)]
            self.assertTrue(0 <= i0 < 25 and 0 <= j0 < 25)
            self.assertEqual(history[-2], set(product(range(i0, 77, 25),
                                                      range(j0, 77, 25))))
            self.assertEqual(len(history[-2]), lifts)
            self.assertEqual(modulus, 625)
            final_residues = {(residual - values[r + 5 * i]
                               + values[s + 5 * j]) % modulus
                              for i, j in history[-2]}
            self.assertEqual(final_residues, {remainder})
            self.assertNotEqual(remainder, 0)
            checked += 77 ** 2
        self.assertEqual(seen, set(levels))
        self.assertEqual(checked, 23716)

    def test_reduced_polynomials_match_every_raw_certificate_residual(self):
        rows = table(self.page, 'reduced')
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(len(row) == 5 for row in rows))

        def polynomial(expression):
            # Interpret the displayed integer-polynomial notation, never eval.
            expression = re.sub(r'\s+', '', expression).replace('−', '-')
            term = r'\d+(?:B\([ij]\)|[ij])?'
            self.assertRegex(expression, rf'\A[+-]?{term}(?:[+-]{term})*\Z')
            parts = re.findall(r'([+-]?\d+)(B\([ij]\)|[ij])?', expression)
            self.assertEqual(len(parts), len({basis for _, basis in parts}))
            coefficients = {basis: int(value) for value, basis in parts}
            return tuple(coefficients.get(basis, 0)
                         for basis in ('', 'i', 'j', 'B(i)', 'B(j)'))

        reduced = {(int(r), int(s)): tuple(polynomial(e) for e in expressions)
                   for r, s, *expressions in rows}
        units = {(0, 3): 1, (2, 1): 3, (1, 2): 2, (3, 0): 4}
        self.assertEqual(set(reduced), set(units))
        certificates = {}
        for r, s, modulus, vector in table(self.page, 'certificates'):
            certificates.setdefault((int(r), int(s)), []).append(
                (int(modulus), tuple(map(int, vector.strip('()').split(',')))))

        for counts in necessary_counts():
            r, s = counts.index(1), counts.index(76)
            rhs = tuple(comb(N, k + 1) // 2 for k in range(11)) + counts
            raw = []
            for modulus, coefficients in certificates[tuple(sorted((r, s)))]:
                values = tuple(sum(coefficients[k] * comb(p, k)
                                   for k in range(11)) + coefficients[11 + p % 5]
                               for p in range(N))
                constant = (sum(a * b for a, b in zip(coefficients, rhs))
                            - sum(values[p] for p in range(s, N, 5)))
                raw.append((modulus, constant, values))
            self.assertEqual(tuple(modulus for modulus, _, _ in raw),
                             (25, 125, 125, 625))
            for i, j in product(range(77), repeat=2):
                residuals = tuple(constant - values[r + 5 * i]
                                  + values[s + 5 * j]
                                  for _, constant, values in raw)
                self.assertTrue(all(value % 5 == 0 for value in residuals[:3]))
                basis = (1, i, j, comb(i, 2), comb(j, 2))
                q2, q3, last = (sum(a * b for a, b in zip(coefficients, basis))
                                for coefficients in reduced[(r, s)])
                actual = (residuals[0] // 5 % 5, residuals[1] // 5 % 25,
                          residuals[2] // 5 % 25, residuals[3] % 625)
                expected = (units[(r, s)] * (i + j - 1) % 5,
                            q2 % 25, q3 % 25, last % 625)
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
