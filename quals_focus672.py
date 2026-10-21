"""Quals for the complete exact reduction behind the672:13 proof search."""
import unittest
from unittest.mock import patch

import certbb
import focus672


class Focus672Quals(unittest.TestCase):
    def test_complete_reduction_retains_both_complementary_parents(self):
        # Replicata: enumerate every parent and every admissible mod4 profile.
        # Expectata: exact exclusions force balance without assuming symmetric signs.
        equations, cases, proof = focus672.reduce()
        self.assertEqual((equations.N, equations.order), (672, 13))
        self.assertEqual(proof, dict(parents=2, profiles=50, integer=32, lp=16))
        self.assertEqual(len(cases), 2)
        self.assertEqual({dict(c)[5] for c in cases},
                         {(130, 5, 67, 67, 67), (5, 130, 67, 67, 67)})
        self.assertTrue(all(dict(c)[4] == (84, 84, 84, 84) for c in cases))
        self.assertTrue(all(tuple(M for M, _ in c) == (2, 3, 5, 7, 4) for c in cases))

    def test_corrupt_integer_annihilator_is_rejected(self):
        # Replicata: change a modular equation so that it rejects a matrix column.
        # Expectata: the positive column controls catch the corrupted certificate.
        original = focus672.ExactSystem
        def corrupted(A):
            system = original(A)
            system.F[0][0] += 1
            return system
        with patch.object(focus672, 'ExactSystem', side_effect=corrupted):
            with self.assertRaises(AssertionError):
                focus672.reduce()

    def test_unverified_numerical_infeasibility_cannot_close_a_case(self):
        # Replicata: a numerical ray is replaced by all-zero integer multipliers.
        # Expectata: the exact verifier rejects it, and preparation fails.
        with patch.object(certbb.Lp, 'multipliers', lambda self, ray: [0] * self.rows_total):
            with self.assertRaises(certbb.ProofError):
                focus672.reduce()

    def test_public_prepare_returns_verified_equations_and_cases(self):
        # Replicata: invoke the runner's public preparation contract.
        # Expectata: it returns the complete verified two-root family.
        equations, cases = focus672.prepare()
        self.assertEqual((equations.N, equations.order, len(cases)), (672, 13, 2))


if __name__ == '__main__':
    unittest.main()
