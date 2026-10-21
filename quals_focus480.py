"""Quals for complete, exactly checked preparation of the 480:14 search."""
import copy
import itertools
import unittest

import certbb
import focus
import focus480
import mstar
import sympy as sp


class Focus480Quals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.equations, cls.cases = focus480.prepare()
        cls.proof = focus480._proof()
        cls.profiles = set(itertools.product(focus480._counts7(), focus480.vectors()))

    def test_affine_family_is_complete(self):
        # Replicata: compare the derived lattice with an independent finite box.
        # Expectata: precisely the 625 documented profiles, without omissions.
        expected = {head + tuple(60 - t for t in head)
                    for head in itertools.product(range(6, 61, 8), repeat=4)
                    if (head[0] - head[2]) % 16 == (head[1] - head[3]) % 16 == 0}
        actual = focus480.vectors()
        self.assertEqual(len(actual), 625)
        self.assertEqual(set(actual), expected)
        offset, basis = focus480._affine(14)
        for vector in actual:
            coordinates, free = basis.gauss_jordan_solve(sp.Matrix([a - b for a, b in zip(vector, offset)]))
            self.assertEqual(free.rows, 0)
            self.assertTrue(all(t.q == 1 for t in coordinates))

    def test_preparation_has_all_exact_equations(self):
        # Replicata: request the complete preparation through its production API.
        # Expectata: 195 representative cases, order14, plus the forced derivative.
        self.assertEqual((self.equations.N, self.equations.order, len(self.equations.W)), (480, 14, 15))
        self.assertEqual(self.equations.W[-1], tuple(p * (-1) ** ((p - 1) % 2) for p in range(480)))
        self.assertEqual(self.equations.rhs[-1], 120)
        self.assertEqual(len(self.cases), 195)
        self.assertTrue(all(tuple(M for M, _ in case) == (3, 5, 7, 8) for case in self.cases))
        self.assertTrue(all(case[:2] == ((3, (80,) * 3), (5, (48,) * 5)) for case in self.cases))

    def test_exact_exclusions_and_orbits_cover_every_profile(self):
        # Replicata: replay the stored separators and expand every representative.
        # Expectata: 496 excluded plus754 retained cases cover all1,250 profiles.
        kept = focus480._retained(self.equations, self.profiles, self.proof)
        representatives = {tuple((tuple(case[2][1]), tuple(case[3][1]))) for case in self.cases}
        covered = {z for representative in representatives for z in focus480._orbit(representative)}
        self.assertEqual(len(kept), 754)
        self.assertEqual(covered, kept)
        self.assertEqual(sum(len(focus480._orbit(z)) for z in representatives), 754)
        excluded = {(tuple(a), tuple(b)) for a, b, _ in self.proof['profiles']}
        self.assertEqual(len(excluded), 496)
        self.assertFalse(excluded & kept)
        self.assertEqual(excluded | kept, self.profiles)

    def test_zero_separator_is_rejected(self):
        # Replicata: replace a real separator with an all-zero coefficient vector.
        # Expectata: exact verification fails rather than dropping that profile.
        proof = copy.deepcopy(self.proof)
        j = proof['profiles'][0][2]
        proof['certificates'][j] = [0] * len(proof['certificates'][j])
        with self.assertRaises(AssertionError):
            focus480._retained(self.equations, self.profiles, proof)

    def test_missing_profile_is_rejected(self):
        # Replicata: delete one certified profile from the stored preparation.
        # Expectata: the claimed partition cannot silently lose a case.
        proof = copy.deepcopy(self.proof)
        proof['profiles'].pop()
        with self.assertRaises(AssertionError):
            focus480._retained(self.equations, self.profiles, proof)

    def test_duplicate_profile_is_rejected(self):
        # Replicata: repeat one excluded case in place of another.
        # Expectata: duplicate coverage is rejected.
        proof = copy.deepcopy(self.proof)
        proof['profiles'][1] = proof['profiles'][0]
        with self.assertRaises(AssertionError):
            focus480._retained(self.equations, self.profiles, proof)

    def test_known_witness_survives_affine_representation(self):
        # Replicata: put the actual order12 length480 witness through the same
        # forced-factor and global-parity calculation at its own order.
        # Expectata: exact polynomial division and integer lattice membership.
        witness = mstar.build(480)
        self.assertEqual(mstar.order(witness), 12)
        factor = focus480._polynomial(12)
        remainder = list(witness)
        quotient = [0] * (len(witness) - len(factor) + 1)
        for k in reversed(range(len(quotient))):
            quotient[k] = remainder[k + len(factor) - 1]
            for j, a in enumerate(factor):
                remainder[k + j] -= quotient[k] * a
        self.assertEqual(remainder, [0] * 480)
        self.assertEqual(focus480._multiply(factor, quotient), witness)
        offset, basis = focus480._affine(12)
        counts = tuple(sum((a + 1) // 2 for a in witness[r::8]) for r in range(8))
        coordinates, free = basis.gauss_jordan_solve(sp.Matrix([a - b for a, b in zip(counts, offset)]))
        self.assertEqual(free.rows, 0)
        self.assertTrue(all(t.q == 1 for t in coordinates))
        rows = focus.moments(480, 12)
        derivative = self.equations.W[-1]
        equations = certbb.Moments(rows.W, rows.rhs, ((derivative,), (120,)))
        self.assertIsNone(certbb.point_certificate(equations.sparse, [(a + 1) // 2 for a in witness]))


if __name__ == '__main__':
    unittest.main()
