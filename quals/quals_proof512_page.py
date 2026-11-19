"""Quals for the joint proof of m*(512) = m*(496) = 9 in index.html.

Replicata: take the exceptional-index congruences from the displayed proof.
Expectata: the residue profiles force four or two exceptions, respectively;
their displayed moment targets agree with direct sums and have no solutions.
Resultata before the revision: the proof used binomial moments and did not
display the square and cube targets for the exceptional indices.
"""

from itertools import combinations_with_replacement, product
from math import comb
from pathlib import Path
import re
import unittest


PAGE = Path(__file__).resolve().parents[1] / 'index.html'


def proof_math():
    fold, = re.findall(r'<details\b[^>]*\bid="proof512-exposition"[^>]*>(.*?)</details>',
                       PAGE.read_text(), re.S)
    fragments = re.findall(r'\\\((.*?)\\\)|\\\[(.*?)\\\]', fold, re.S)
    return [re.sub(r'\s+|\\[,;:!]', '', a+b).replace('−', '-') for a, b in fragments]


def displayed_moments():
    # Equations in one display can share its last modulus. Read each display
    # separately so interchanging the two lengths' cube targets is detected.
    displays = []
    for formula in proof_math():
        targets = []
        for m in re.finditer(r'\^\{?([23])\}?\\equiv(-?\d+)', formula):
            modulus = re.search(r'\\pmod\{?(\d+)\}?', formula[m.end():])
            if modulus:
                mod = int(modulus[1])
                targets.append((int(m[1]), int(m[2]) % mod, mod))
        if targets:
            displays.append(targets)
    return displays


def exceptional_count(start, n):
    sizes = [len(range(start + (r - start) % 3, start + n, 3)) for r in range(3)]
    # The three rotations of (x-1)^10 have equal coefficients mod 243.
    # They generate the cyclic coefficient sums of every multiple.
    generator = [sum((-1)**(10-k) * comb(10, k) for k in range(r, 11, 3))
                 for r in range(3)]
    assert generator == [81, 81, -162]
    choices = [range(-s, s+1, 2) for s in sizes]
    profiles = [(a, b, -a-b) for a, b in product(*choices[:2])
                if -a-b in choices[2] and (a-b) % 243 == (2*a+b) % 243 == 0]
    assert profiles == [(-162, 81, 81), (162, -81, -81)]
    return (sizes[0] + profiles[0][0]) // 2


class Proof512PageQuals(unittest.TestCase):
    def test_displayed_class_difference_on_generators(self):
        subscript = r'[A-Za-z]_\{?([012])\}?'
        identity = subscript + '-' + subscript + r'=(?:.*?=)?(-?\d+)(?:\\cdot)?' + subscript
        matches = [m for line in proof_math() for m in re.findall(identity, line)]
        self.assertEqual(len(matches), 1)
        first, second, coeff, r = map(int, matches[0])
        self.assertEqual(({first, second}, r), ({1, 2}, 0))
        kernel = [(-1)**(9-k) * comb(9, k) for k in range(10)]
        # g(1)=0 makes g an integer sum of x^j-1. Three successive j suffice
        # for the coefficient classes. Check the displayed identity on each.
        for j in range(1, 4):
            sums = [sum(c for k, c in enumerate(kernel) if (k+j) % 3 == s)
                    - sum(kernel[s::3]) for s in range(3)]
            self.assertEqual(sums[first] - sums[second], coeff * ((j % 3 == r) - (r == 0)))
        # The signed square and cube sums on class 0 are therefore zero mod 9
        # when G_0 is zero. Check their dependence on G_0 on every monomial
        # g=x^j: shifting j by 27 shifts t by 9 and preserves both residues.
        for j in range(27):
            moments = [sum(c * ((k+j)//3)**p for k, c in enumerate(kernel) if (k+j) % 3 == 0)
                       % 9 for p in (2, 3)]
            self.assertEqual(moments, [0, 6 * (j % 3 == 0)])

    def test_four_exceptional_squares_and_cubes_at_512(self):
        count = exceptional_count(1, 512)
        self.assertEqual(count, 4)
        targets = tuple(5 * sum(t**k for t in range(1, 171)) % 9 for k in (2, 3))
        self.assertEqual(targets, (3, 0))
        self.assertIn([(2, targets[0], 9), (3, targets[1], 9)], displayed_moments())
        # Every multiset of four residues occurs: 1..170 contains at least
        # four copies of each residue. Each congruence alone allows solutions.
        moments = {tuple(sum(t**k for t in residues) % 9 for k in (2, 3))
                   for residues in combinations_with_replacement(range(9), count)}
        self.assertIn(targets[0], {s for s, c in moments})
        self.assertIn(targets[1], {c for s, c in moments})
        self.assertNotIn(targets, moments)

    def test_two_exceptional_cubes_at_496(self):
        count = exceptional_count(3, 496)
        self.assertEqual(count, 2)
        target = 5 * sum(t**3 for t in range(1, 167)) % 9
        self.assertEqual(target, 5)
        self.assertIn([(3, target, 9)], displayed_moments())
        sums = {sum(t**3 for t in residues) % 9
                for residues in combinations_with_replacement(range(9), count)}
        self.assertEqual(sums, {0, 1, 2, 7, 8})
        self.assertNotIn(target, sums)


if __name__ == '__main__':
    unittest.main()
