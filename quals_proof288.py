"""Quals for Claude's finite, exact proof that m*(288) <= 10.

Replicata: run the proof; enumerate the residue sums of every balanced sign
sequence of length 12, 14 and 16; decode known witnesses; compare with mstar;
try every plus count in every cell; damage the proof's table of overfull
cells; and give it impossible inputs.
Expectata: the enumeration contains every real profile and agrees with mstar,
no sign sequence has an overfull cell, each of the 16 cases at 288:11 has one,
and damaged or incomplete tables and impossible inputs are rejected loudly.
Resultata before implementation: proof288 does not exist, so these quals are red.
"""

from itertools import combinations, product
from pathlib import Path
import random
import subprocess
import sys
import unittest

import proof288 as proof


# (n, m, hex) of known witnesses, copied as data from overnight_v5.EXAMPLES
# (192, 240, 384, 432) and mstar.PAGE_CODES (336, 480, 560, 800). In their
# convention the hex bits are the left half (1 -> +1) and the right half is
# (-1)^m times the left half reversed. Each exact order is checked here.
WITNESSES = (
    (192, 9, 'C1BE1E21CD63D295A7887A59'),
    (240, 10, 'C394E65AB989457A86B7D0D921636E'),
    (336, 10, 'C87695B43E0ED258AB29C7793D8521DB227C0B746D'),
    (384, 10, 'C1BE1E21CD63D295A7887A5965A1EE1A56B4394C7B87827C'),
    (432, 11, '5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46'),
    (480, 12, 'B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3'),
    (560, 10, '34D2E9F0DA19EC92492D966936ABCA25FAD924D26F2591EB64926924925D6E1A4BFE92'),
    (800, 11, '966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2'
              'CD6E960B243A59A592DB2DB6D9'),
)

# (n, M, m) compared with mstar.residue_vectors: the proof's own moduli at
# 288:11 and 288:10, mod 3, composite moduli, and witnesses' lengths.
MSTAR_CASES = ((288, 5, 11), (288, 7, 11), (288, 3, 11), (288, 4, 11),
               (288, 5, 10), (288, 7, 10), (432, 5, 11), (384, 5, 10),
               (240, 7, 10), (192, 7, 9), (48, 4, 6), (24, 5, 4), (16, 4, 4),
               (16, 8, 4))

# The 35 cells (r, s) of the table of classes r mod 5 and s mod 7.
ALL_CELLS = tuple(product(range(5), range(7)))


def from_hex(code, m):
    left = [2 * int(bit) - 1 for bit in bin(int(code, 16))[2:].zfill(4 * len(code))]
    return left + [(-1) ** m * t for t in reversed(left)]


def power_sum(a, k):
    """sum_p a_p*p^k over positions p = 0,...,len(a)-1, in plain integers (0^0 = 1)."""
    return sum(t * p ** k for p, t in enumerate(a))


def order(a):
    k = 0
    while power_sum(a, k) == 0:
        k += 1
    return k


def residue_sums(a, M):
    return tuple(sum(a[r::M]) for r in range(M))


def fillable(n, D5, D7, r, s):
    """Can the cell's positions be signed within its classes' plus and minus
    counts? Tries every number y of plus signs in the cell, independently of
    proof288.overfull."""
    cell = len([p for p in range(n) if p % 5 == r and p % 7 == s])
    size5, size7 = len(range(r, n, 5)), len(range(s, n, 7))
    plus5, plus7 = (size5 + D5[r]) // 2, (size7 + D7[s]) // 2
    return any(y <= plus5 and y <= plus7
               and cell - y <= size5 - plus5 and cell - y <= size7 - plus7
               for y in range(cell + 1))


class Quals(unittest.TestCase):
    def test_complete_cover(self):
        self.assertEqual(proof.verify_all(),
                         dict(candidates=(108, 326592), vectors=(2, 8),
                              cases=16, survivors=0))

    def test_residue_vectors_at_288(self):
        # Replicata: enumerate the admissible order-11 vectors mod 5 and mod 7.
        # Expectata: exactly these 2 and 8, and CELLS covers their 16 pairs.
        V5 = proof.admissible(288, 5, 11)
        V7 = proof.admissible(288, 7, 11)
        self.assertEqual(V5, ((-50, 0, 50, -25, 25), (50, 0, -50, 25, -25)))
        self.assertEqual(V7, ((-42, 7, 7, 7, 7, 7, 7),
                              (0, -35, -21, -7, 7, 21, 35),
                              (0, -21, 7, 35, -35, -7, 21),
                              (0, -7, 35, -21, 21, -35, 7),
                              (0, 7, -35, 21, -21, 35, -7),
                              (0, 21, -7, -35, 35, 7, -21),
                              (0, 35, 21, 7, -7, -21, -35),
                              (42, -7, -7, -7, -7, -7, -7)))
        self.assertEqual(len(proof.CELLS), 16)
        self.assertEqual(set(proof.CELLS), set(product(V5, V7)))

    def test_enumeration_contains_every_small_sequence(self):
        # Replicata: every balanced sign sequence of length 12, 14 and 16,
        # with its exact order from plain power sums.
        # Expectata: at every order m from 1 to its own, its residue sums mod
        # 2, 3, 4, 5, 7 and 8 are among proof288.admissible(n, M, m), and the
        # orders reach m*(12) = 3, m*(14) = 1 and m*(16) = 4.
        for n, top in ((12, 3), (14, 1), (16, 4)):
            found = {}
            for plus in combinations(range(n), n // 2):
                a = [2 * (p in plus) - 1 for p in range(n)]
                for m in range(1, order(a) + 1):
                    for M in (2, 3, 4, 5, 7, 8):
                        found.setdefault((M, m), set()).add(residue_sums(a, M))
            self.assertEqual(max(m for _, m in found), top)
            for (M, m), profiles in found.items():
                with self.subTest(n=n, M=M, m=m):
                    self.assertLessEqual(profiles, set(proof.admissible(n, M, m)))

    def test_agrees_with_mstar(self):
        # Replicata: mstar.residue_vectors, imported read only, in both sweeps.
        # Expectata: exactly proof288.admissible's vectors in every case.
        import mstar
        for n, M, m in MSTAR_CASES:
            for sweep in ('natural', 'digits'):
                with self.subTest(n=n, M=M, m=m, sweep=sweep):
                    theirs = mstar.residue_vectors(n, M, m, None,
                                                   mstar.Budget(10 ** 7), sweep)
                    self.assertEqual(sorted(theirs),
                                     list(proof.admissible(n, M, m)))

    def test_lattice_membership_on_combinations_of_generators(self):
        # Replicata: multiply 1 by x - 1 up to 12 times mod x^M - 1,
        # independently of proof288.generator, and take pseudorandom integer
        # combinations of the M cyclic shifts of each product.
        # Expectata: proof288.generator agrees; each combination is in L(M, k)
        # for k = 1,...,m; adding 1 takes it out of L(M, m); adding 1 - x
        # leaves it in L(M, 1) but takes it out of L(M, k) for k >= 2.
        rng = random.Random(11)
        for M in (2, 3, 4, 5, 7, 8, 9):
            g = (1,) + (0,) * (M - 1)
            for m in range(1, 13):
                g = tuple(g[r - 1] - g[r] for r in range(M))
                self.assertEqual(proof.generator(M, m), g)
                for _ in range(3):
                    c = [rng.randint(-10 ** 6, 10 ** 6) for _ in range(M)]
                    D = tuple(sum(c[j] * g[(r - j) % M] for j in range(M))
                              for r in range(M))
                    one = (D[0] + 1,) + D[1:]
                    with self.subTest(M=M, m=m, D=D):
                        self.assertTrue(proof.in_lattice(D, m))
                        self.assertFalse(proof.in_lattice(one, m))
                        self.assertEqual(
                            [proof.in_lattice(D, k) for k in range(1, m + 1)],
                            [True] * m)
                        self.assertEqual(
                            [proof.in_lattice((one[0], one[1] - 1) + one[2:], k)
                             for k in range(1, m + 1)],
                            [True] + [False] * (m - 1))

    def test_known_witnesses_pass_every_check_at_their_own_order(self):
        # Replicata: decode each known witness and check its exact order m and
        # its sizes with plain power sums.
        # Expectata: its residue sums mod 3, 5 and 7 meet both conditions of
        # proof288.admissible(n, M, m) (choices and L(M, m)), and none of its
        # 35 cells is overfull.
        for n, m, code in WITNESSES:
            a = from_hex(code, m)
            with self.subTest(n=n, m=m):
                self.assertEqual(len(a), n)
                self.assertEqual(a.count(1), n // 2)
                self.assertEqual(order(a), m)
                for M in (3, 5, 7):
                    D = residue_sums(a, M)
                    self.assertTrue(all(d in c for d, c in
                                        zip(D, proof.choices(n, M, m))))
                    self.assertTrue(proof.in_lattice(D, m))
                D5, D7 = residue_sums(a, 5), residue_sums(a, 7)
                self.assertEqual([proof.overfull(n, D5, D7, r, s) for r, s in ALL_CELLS],
                                 [False] * 35)

    def test_no_sign_sequence_has_an_overfull_cell(self):
        # Replicata: 200 pseudorandom sign sequences of length 288 with plus
        # fractions from 0 to 1, and the sequences that are plus exactly on
        # one class mod 5, mod 7 or mod 35 (one class mod 5 or mod 7 makes
        # several cells meet the bound with equality).
        # Expectata: no cell of any of them is overfull, whatever its order.
        rng = random.Random(288)
        sequences = [[2 * (rng.random() < i / 199) - 1 for _ in range(288)]
                     for i in range(200)]
        sequences += [[2 * (p % M == r) - 1 for p in range(288)]
                      for M in (5, 7, 35) for r in range(M)]
        for a in sequences:
            D5, D7 = residue_sums(a, 5), residue_sums(a, 7)
            self.assertEqual([proof.overfull(288, D5, D7, r, s) for r, s in ALL_CELLS],
                             [False] * 35)
            self.assertEqual([fillable(288, D5, D7, r, s) for r, s in ALL_CELLS],
                             [True] * 35)

    def test_overfull_agrees_with_trying_every_plus_count(self):
        # Replicata: 400 pseudorandom pairs of residue sums mod 5 and mod 7 at
        # length 288 that meet the size and parity conditions, unrelated
        # otherwise, and the 16 pairs of the proof.
        # Expectata: proof288.overfull holds exactly where no number of plus
        # signs fits the cell, and both outcomes occur.
        rng = random.Random(35)
        pairs = [tuple(tuple(rng.randrange(-s, s + 1, 2) for s in proof.sizes(288, M))
                       for M in (5, 7)) for _ in range(400)]
        outcomes = []
        for D5, D7 in pairs + list(proof.CELLS):
            mine = [not fillable(288, D5, D7, r, s) for r, s in ALL_CELLS]
            self.assertEqual([proof.overfull(288, D5, D7, r, s) for r, s in ALL_CELLS],
                             mine)
            outcomes += mine
        self.assertEqual(set(outcomes), {False, True})

    def test_listed_cells_are_the_first_overfull_ones(self):
        # Replicata: try every number of plus signs in each of the 35 cells of
        # each of the 16 cases.
        # Expectata: each listed cell is the first, in the order (0, 0), (0, 1),
        # ..., (4, 6), that no number fits.
        for (D5, D7), cell in proof.CELLS.items():
            stuck = [c for c in ALL_CELLS if not fillable(288, D5, D7, *c)]
            with self.subTest(D5=D5, D7=D7):
                self.assertEqual(cell, stuck[0])

    def test_damaged_cells_rejected(self):
        # Replicata: put each of the 35 cells, and malformed ones, in place of
        # each case's listed cell.
        # Expectata: verify_all accepts exactly the overfull cells (so it checks
        # rather than compares), and rejects every fillable, out-of-range or
        # non-integer cell with ValueError.
        for key, (r, s) in proof.CELLS.items():
            D5, D7 = key
            stuck = [c for c in ALL_CELLS if not fillable(288, D5, D7, *c)]
            loose = [c for c in ALL_CELLS if fillable(288, D5, D7, *c)]
            self.assertEqual(len(stuck) + len(loose), 35)
            for cell in stuck:
                self.assertEqual(proof.verify_all({**proof.CELLS, key: cell})['survivors'], 0)
            malformed = [(r - 5, s), (r, s - 7), (r + 5, s), (r, s + 7),
                         (float(r), s), (r, float(s)), (str(r), s)]
            for cell in loose + malformed:
                with self.subTest(key=key, cell=cell):
                    with self.assertRaises(ValueError):
                        proof.verify_all({**proof.CELLS, key: cell})
        # A bool equals 0 or 1 but is no position class.
        zeros = [key for key, cell in proof.CELLS.items() if cell == (0, 0)]
        self.assertEqual(len(zeros), 2)
        for key in zeros:
            for cell in ((False, 0), (0, False), (False, False)):
                with self.subTest(key=key, cell=cell):
                    with self.assertRaises(ValueError):
                        proof.verify_all({**proof.CELLS, key: cell})

    def test_impossible_inputs_rejected(self):
        # Replicata: give overfull residue sums of the wrong parity, beyond a
        # class's size, of the wrong length (with or without a parity fault
        # for that length) or in the wrong order; ask in_lattice about order 0
        # and choices about modulus 1.
        # Expectata: ValueError every time, never a verdict.
        D5, D7 = ((-50, 0, 50, -25, 25), (0, -35, -21, -7, 7, 21, 35))
        pairs = [((D5[0] + 1,) + D5[1:], D7), ((-60,) + D5[1:], D7),
                 (D5, (D7[0] + 1,) + D7[1:]), (D5, (44,) + D7[1:]),
                 (D5[:4], D7), (D5, D7 + (0,)), ((0,) * 4, D7), (D5, (0,) * 8),
                 (D7, D5)]
        for bad5, bad7 in pairs:
            with self.subTest(D5=bad5, D7=bad7):
                with self.assertRaises(ValueError):
                    proof.overfull(288, bad5, bad7, 0, 0)
        with self.assertRaises(ValueError):
            proof.in_lattice((1, -1, 0), 0)
        with self.assertRaises(ValueError):
            proof.choices(288, 1, 11)

    def test_missing_or_extra_cases_rejected(self):
        # Replicata: drop each case, add a pair that is not admissible, or list
        # no cases at all.
        # Expectata: every such table is rejected with ValueError.
        extra = ((-50, 0, 50, 25, -25), (-42, 7, 7, 7, 7, 7, 7))
        self.assertNotIn(extra, proof.CELLS)
        tables = [{k: v for k, v in proof.CELLS.items() if k != key}
                  for key in proof.CELLS]
        tables += [{**proof.CELLS, extra: (0, 0)}, {}]
        for table in tables:
            with self.subTest(cases=len(table)):
                with self.assertRaises(ValueError):
                    proof.verify_all(table)

    def test_cli_and_optimized_python(self):
        path = Path(proof.__file__).resolve()
        for flags in ((), ('-O',)):
            result = subprocess.run((sys.executable, '-B', *flags, str(path)),
                                    capture_output=True, text=True, check=True)
            self.assertIn('Claude: "m*(288) <= 10;', result.stdout)
            self.assertIn('16 casus', result.stdout)
            self.assertEqual(result.stderr, '')
            # Optimization must never disable rejection of false evidence.
            result = subprocess.run(
                (sys.executable, '-B', *flags, '-c',
                 'import proof288; proof288.verify_all({})'),
                cwd=path.parent, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ValueError', result.stderr)


if __name__ == '__main__':
    unittest.main()
