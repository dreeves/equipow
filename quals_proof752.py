"""Quals for Claude's exact proof that m*(752) <= 10.

Replicata: run the proof; derive its count vectors independently; plant a solution in each
full-size 752 profile; give it known order-11 sequences and their one-swap neighbours; run its
relaxation on cases decided elsewhere (384:11 by proof384, 496:10, and small lengths by trying
every sign vector); compare its meet in the middle with brute force; damage its certificates.
Expectata: no 752 survivor in either profile, every planted or genuine solution survives, the
decided cases come out as decided, and damaged evidence is rejected loudly.
Resultata before implementation: proof752 does not exist, so these quals are red.
"""

from collections import defaultdict
from fractions import Fraction
from itertools import combinations, product
from math import comb, prod
from pathlib import Path
import random
import subprocess
import sys
import unittest

import mstar
import proof384
import proof752 as proof


SIDE = comb(251, 4)


def power_sums(signs, m):
    """Plain integer power sums sum_p a_p p^k for k = 0..m-1, with 0^0 = 1."""
    return tuple(sum(a * p ** k for p, a in enumerate(signs)) for k in range(m))


def from_hex(h, m):
    """BGPW's Table 5 code: the hex bits are the left half (1 -> +1), and the right half is
    (-1)^m times the left half reversed."""
    left = [2 * int(bit) - 1 for bit in bin(int(h, 16))[2:].zfill(4 * len(h))]
    return left + [(-1) ** m * a for a in reversed(left)]


def every_sequence(n, m):
    """Every sign vector of length n with zero power sums below degree m: all 2^(n/2) halves on
    each side, joined where their power sums cancel."""
    def halves(positions):
        out = [((), (0,) * m)]
        for p in positions:
            out = [(signs + (a,), tuple(x + a * p ** k for k, x in enumerate(sums)))
                   for signs, sums in out for a in (1, -1)]
        return out
    lefts = defaultdict(list)
    for signs, sums in halves(range(n // 2)):
        lefts[sums].append(signs)
    return [left + right for right, sums in halves(range(n // 2, n))
            for left in lefts[tuple(-x for x in sums)]]


def plus_counts(signs, M=3):
    return tuple(sum(a == 1 for a in signs[r::M]) for r in range(M))


def placement(case, signs):
    """A sequence's exceptional positions: in each exceptional class, the signs equal to its
    exceptional sign (+1 for plus signs among minus signs)."""
    return tuple(tuple(p for p in cls if signs[p] == sign)
                 for cls, sign in zip(case.classes, case.signs))


def one_swaps(case, own):
    """Every placement differing from own by moving one exceptional position within its class."""
    for i, (cls, chosen) in enumerate(zip(case.classes, own)):
        for old, new in product(chosen, sorted(set(cls) - set(chosen))):
            moved = tuple(sorted(set(chosen) - {old} | {new}))
            yield own[:i] + (moved,) + own[i + 1:]


def in_span(d, generator):
    """Whether d is an integer combination of the cyclic shifts of a sum-zero generator mod x^3-1:
    the third shift is minus the sum of the first two, whose coefficients Cramer's rule gives."""
    s, t = generator, generator[2:] + generator[:2]
    det = s[0] * t[1] - t[0] * s[1]
    a = Fraction(d[0] * t[1] - t[0] * d[1], det)
    b = Fraction(s[0] * d[1] - d[0] * s[1], det)
    return (a.denominator == b.denominator == 1
            and all(a * x + b * y == z for x, y, z in zip(s, t, d)))


def packed(values, moduli):
    """The mixed-radix integer of reduced values, the first value least significant."""
    return sum(v * prod(moduli[:i]) for i, v in enumerate(values))


class Quals(unittest.TestCase):
    def test_complete_cover(self):
        result = proof.verify_all()
        self.assertEqual(result['vectors'], ((4, 247, 125), (247, 4, 125)))
        self.assertEqual(result['subsets'], ((SIDE, SIDE), (SIDE, SIDE)))
        self.assertEqual(result['placements'], 2 * SIDE ** 2)
        self.assertEqual(result['survivors'], 0)

    def test_count_vectors_independently(self):
        # Replicata: every signed class sum in the parity box, kept when it is an integer combination
        # of the cyclic shifts of (x-1)^m mod x^3-1. Expectata: the proof's count vectors exactly.
        for n, m, expected in ((752, 11, ((4, 247, 125), (247, 4, 125))),
                               (496, 10, ((2, 123, 123), (164, 42, 42)))):
            sizes = tuple(len(range(r, n, 3)) for r in range(3))
            generator = tuple(sum((-1) ** (m - k) * comb(m, k) for k in range(r, m + 1, 3))
                              for r in range(3))
            found = tuple(sorted(
                tuple((d + s) // 2 for d, s in zip((d0, d1, -d0 - d1), sizes))
                for d0 in range(-sizes[0], sizes[0] + 1, 2)
                for d1 in range(-sizes[1], sizes[1] + 1, 2)
                if abs(d0 + d1) <= sizes[2] and (d0 + d1 + sizes[2]) % 2 == 0
                and in_span((d0, d1, -d0 - d1), generator)))
            with self.subTest(n=n, m=m):
                self.assertEqual(found, expected)
                self.assertEqual(proof.count_vectors(n, m, 3), expected)
        self.assertEqual(proof.count_vectors(), ((4, 247, 125), (247, 4, 125)))
        self.assertEqual(proof.count_vectors(384, 11, 5), tuple(sorted(proof384.count_vectors())))

    def test_planted_placements_are_found(self):
        # Replicata: in each 752 profile, choose four exceptional positions per class at random and
        # make their own signed keys the target. Expectata: the full-size search returns that
        # placement and nothing else.
        for counts, seed in zip(proof.count_vectors(), (752, 20261025)):
            case = proof.Case(752, 11, 3, counts, (0, 1))
            rng = random.Random(seed)
            planted = tuple(tuple(sorted(rng.sample(cls, 4))) for cls in case.classes)
            target = tuple(sum(sign * case.keys[p][i] for sign, chosen in zip(case.signs, planted)
                               for p in chosen) % mu for i, mu in enumerate(case.moduli))
            found = proof.search(case, target)
            with self.subTest(counts=counts):
                self.assertEqual(found['subsets'], (SIDE, SIDE))
                self.assertEqual(found['survivors'], [planted])

    def test_known_order11_sequences(self):
        # Replicata: the page's order-11 sequence of length 800 and Thue-Morse of length 2048.
        # Expectata: exact order 11, a count vector the proof allows, and an own placement meeting
        # every certificate; every one-swap neighbour of the 800 placement fails.
        code, = (h for label, m, h in mstar.PAGE_CODES if label == 'index.html p800')
        p800 = from_hex(code, 11)
        thue_morse = [(-1) ** bin(p).count('1') for p in range(2048)]
        for signs in (p800, thue_morse):
            n = len(signs)
            sums = power_sums(signs, 12)
            counts = plus_counts(signs)
            case = proof.Case(n, 11, 3, counts, (0, 1))
            with self.subTest(n=n):
                self.assertEqual(sums[:11], (0,) * 11)
                self.assertNotEqual(sums[11], 0)
                self.assertIn(counts, proof.count_vectors(n, 11, 3))
                self.assertTrue(case.holds(placement(case, signs), case.target))
        case = proof.Case(800, 11, 3, plus_counts(p800), (0, 1))
        own = placement(case, p800)
        self.assertEqual(plus_counts(p800), (255, 12, 133))
        self.assertEqual(case.minority, (12, 12))
        swaps = list(one_swaps(case, own))
        self.assertEqual(len(swaps), 2 * 12 * 255)
        self.assertFalse(any(case.holds(swap, case.target) for swap in swaps))

    def test_384_order11_as_proof384_decides(self):
        # Replicata: proof384's four count vectors, their two singleton classes enumerated and the
        # other three relaxed. Expectata: none of the 23,716 placements survives.
        tried = 0
        for counts in proof384.count_vectors():
            case = proof.Case(384, 11, 5, counts,
                              tuple(sorted((counts.index(1), counts.index(76)))))
            found = proof.brute(case, case.target)
            with self.subTest(counts=counts):
                self.assertEqual(case.minority, (1, 1))
                self.assertEqual(found['survivors'], [])
            tried += found['placements']
        self.assertEqual(tried, 4 * 77 ** 2)

    def test_496_order10(self):
        # Replicata: both mod-3 count vectors of 496:10, class 0 enumerated, classes 1 and 2 relaxed.
        # Expectata: none of the C(166,2) placements of either survives.
        for counts in proof.count_vectors(496, 10, 3):
            case = proof.Case(496, 10, 3, counts, (0,))
            found = proof.brute(case, case.target)
            with self.subTest(counts=counts):
                self.assertEqual(case.minority, (2,))
                self.assertEqual(found['placements'], comb(166, 2))
                self.assertEqual(found['survivors'], [])

    def test_four_subsets_exactly_once(self):
        # Replicata: random keys on small sides, every bucket generated. Expectata: each 4-subset
        # exactly once, its exact packed key, and bucket sizes equal to brute-force counts and to
        # the proof's subset-sum recursion.
        rng = random.Random(4)
        for m, moduli, buckets in ((4, (3, 9, 27), 1), (5, (2, 4, 6), 3), (9, (3, 9, 27), 9),
                                   (13, (5, 25, 125), 25), (16, (3, 9, 81), 27),
                                   (20, (7, 11, 13), 13)):
            keys = [tuple(rng.randrange(mu) for mu in moduli) for _ in range(m)]
            constant = tuple(rng.randrange(mu) for mu in moduli)
            side = proof.Side(keys, constant, moduli, buckets)
            seen, sizes = {}, []
            for q in range(buckets):
                key, low, high = side.bucket(q)
                sizes.append(len(key))
                for k, i, j in zip(key.tolist(), low.tolist(), high.tolist()):
                    subset = side.subset(i, j)
                    self.assertNotIn(subset, seen)
                    seen[subset] = k
            exact = {s: packed(tuple((c + sum(keys[e][i] for e in s)) % mu
                                     for i, (c, mu) in enumerate(zip(constant, moduli))), moduli)
                     for s in combinations(range(m), 4)}
            counts = [sum((v // prod(moduli[:-1])) % buckets == q for v in exact.values())
                      for q in range(buckets)]
            with self.subTest(m=m, moduli=moduli, buckets=buckets):
                self.assertEqual(seen, exact)
                self.assertEqual(sizes, counts)
                self.assertEqual(proof.bucket_counts([k[-1] for k in keys], constant[-1],
                                                     buckets), counts)

    def test_meet_equals_brute_force(self):
        # Replicata: random small sides whose keys collide often, including moduli that are not
        # prime powers. Expectata: the matched pairs are exactly brute force's.
        rng = random.Random(5)
        for m, moduli, buckets in ((6, (2, 3, 4), 2), (9, (3, 3, 9), 3), (10, (2, 4, 6), 6),
                                   (12, (3, 9, 27), 27), (11, (5, 5, 25), 5)):
            left = [tuple(rng.randrange(mu) for mu in moduli) for _ in range(m)]
            right = [tuple(rng.randrange(mu) for mu in moduli) for _ in range(m + 1)]
            constant = tuple(rng.randrange(mu) for mu in moduli)

            def key(keys, c, s):
                return tuple((x + sum(keys[e][i] for e in s)) % mu
                             for i, (x, mu) in enumerate(zip(c, moduli)))
            by_key = defaultdict(list)
            for s in combinations(range(m), 4):
                by_key[key(left, constant, s)].append(s)
            expected = sorted((s, t) for t in combinations(range(m + 1), 4)
                              for s in by_key[key(right, (0,) * 3, t)])
            found = proof.meet(left, constant, right, moduli, buckets)
            with self.subTest(m=m, moduli=moduli, buckets=buckets):
                self.assertEqual(found['subsets'], (comb(m, 4), comb(m + 1, 4)))
                self.assertGreater(len(expected), 0)
                self.assertEqual(sorted(found['pairs']), expected)

    def test_small_lengths_against_every_sign_vector(self):
        # Replicata: every sign vector of a few small lengths, against the method of the proof:
        # count vectors mod 3, classes 0 and 1 enumerated, class 2 relaxed. Expectata: every
        # genuine sequence survives, and where nothing survives no sequence exists.
        decided = {(16, 5), (24, 6), (32, 6)}
        for n, m in ((16, 4), (16, 5), (24, 4), (24, 5), (24, 6), (32, 5), (32, 6)):
            sequences = every_sequence(n, m)
            cases = {counts: proof.Case(n, m, 3, counts, (0, 1))
                     for counts in proof.count_vectors(n, m, 3)}
            survivors = {counts: set(proof.brute(case, case.target)['survivors'])
                         for counts, case in cases.items()}
            with self.subTest(n=n, m=m):
                self.assertTrue(all(power_sums(s, m) == (0,) * m for s in sequences))
                for signs in sequences:
                    counts = plus_counts(signs)
                    self.assertIn(counts, cases)
                    self.assertIn(placement(cases[counts], signs), survivors[counts])
                self.assertEqual(not any(survivors.values()), (n, m) in decided)
                self.assertEqual(sequences == [], (n, m) in decided or (n, m) == (24, 5))

    def test_small_meet_in_the_middle_equals_brute_force(self):
        # Replicata: length 24, whose only count vector (4,4,4) has four exceptions in each of
        # classes 0 and 1, searched both ways. Expectata: the same survivors, none at order 6.
        for m, chosen, buckets in ((4, (1, 2, 3), 9), (5, (2, 3, 4), 27), (6, (3, 4, 5), 27)):
            self.assertEqual(proof.count_vectors(24, m, 3), ((4, 4, 4),))
            case = proof.Case(24, m, 3, (4, 4, 4), (0, 1))
            found = proof.search(case, case.target, chosen, buckets)
            brute = proof.brute(case, case.target)['survivors']
            with self.subTest(m=m):
                self.assertEqual(found['subsets'], (comb(8, 4), comb(8, 4)))
                self.assertEqual(sorted(found['survivors']), sorted(brute))
                self.assertEqual(brute == [], m == 6)

    def test_damaged_certificates_rejected(self):
        # Replicata: each nontrivial 752 certificate with its modulus tripled, or with one
        # coefficient raised where every class-2 column has a 1. Expectata: the check rejects
        # each loudly. (The first certificate, modulus 1, has only zero coefficients.)
        case = proof.Case(752, 11, 3, (4, 247, 125), (0, 1))
        proof.verify_certificates(case.certificates, case.free_columns)
        self.assertEqual(case.moduli, (1, 3, 3 ** 2, 3 ** 4, 3 ** 5, 3 ** 6, 3 ** 8, 3 ** 9,
                                       3 ** 10, 3 ** 13, 3 ** 14))
        self.assertEqual(case.certificates[0], (1, (0,) * 11))
        self.assertEqual(len(case.free_columns), 250)
        self.assertTrue(all(column[0] == 1 for column in case.free_columns))
        damaged = ([(3 * mu, w) for mu, w in case.certificates[1:]]
                   + [(mu, (w[0] + 1,) + w[1:]) for mu, w in case.certificates[1:]])
        for certificate in damaged:
            with self.subTest(certificate=certificate):
                with self.assertRaises(ValueError):
                    proof.verify_certificates([certificate], case.free_columns)

    def test_cli_and_optimized_python(self):
        path = Path(proof.__file__).resolve()
        # The full proof under -O: its checks must not depend on assert statements.
        result = subprocess.run((sys.executable, '-O', str(path)),
                                capture_output=True, text=True, check=True)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn('Claude: "m*(752) <= 10:', result.stdout)
        self.assertIn(f'{2 * SIDE ** 2:,}', result.stdout)
        self.assertEqual(result.stderr, '')
        for flags in ((), ('-O',)):
            result = subprocess.run(
                (sys.executable, *flags, '-c',
                 'import proof752; proof752.verify_certificates([(3, (1,))], [(1,)])'),
                cwd=path.parent, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ValueError', result.stderr)


if __name__ == '__main__':
    unittest.main()
