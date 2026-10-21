"""Quals for the exact integer combinations used to scale proof-search moments."""
import unittest

import numpy as np
import certbb
from focus import moments
import overnight_v5 as v5


class MomentTransformQuals(unittest.TestCase):
    def test_high_order_rows_remain_independent_and_well_scaled(self):
        # Replicata: the moment rows for both newly requested proof runs.
        # Expectata: all equations survive integer rounding, with nearly
        # orthonormal rows; Lp accepts them without a rank assertion.
        for n, m in ((480, 14), (672, 13)):
            with self.subTest(n=n, m=m):
                lp = certbb.Lp(moments(n, m), ())
                self.assertEqual(np.linalg.matrix_rank(lp.A), m)
                self.assertLess(np.max(np.abs(lp.A @ lp.A.T - np.eye(m))), 1e-8)

    def test_known_witness_survives_the_scaled_equations(self):
        # Replicata: the existing order-12 length-480 witness, with every
        # position fixed to its known value.
        # Expectata: the actual LP accepts it and the original exact moments
        # vanish; the scaling does not remove a valid partition.
        code = 'B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3'
        a = v5.from_hex(code, 12)
        self.assertEqual((len(a), v5.exact_order(a)), (480, 12))
        x = [(s + 1) // 2 for s in a]
        md = moments(480, 12)
        self.assertTrue(all(sum(t * s for t, s in zip(row, a)) == 0 for row in md.W))
        lp = certbb.Lp(md, ())
        status, point = lp.solve(x, x)
        self.assertEqual(status, 'Optimal')
        self.assertTrue(np.array_equal(point, x))

    def test_integer_separator_still_verifies_against_original_rows(self):
        # Replicata: the same witness is pinned while order 14 is required.
        # Expectata: infeasibility has an integer separator whose exact
        # bound is positive, and the independent proof checker accepts it.
        code = 'B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3'
        x = [(s + 1) // 2 for s in v5.from_hex(code, 12)]
        md = moments(480, 14)
        lp = certbb.Lp(md, ())
        status, ray = lp.solve(x, x)
        self.assertEqual(status, 'Infeasible')
        coefficients = lp.multipliers(ray)
        self.assertGreater(certbb.lower_bound(md.sparse, x, x, coefficients), 0)
        certbb.verify(md, (), [('L', coefficients)], lo=x, hi=x)


if __name__ == '__main__':
    unittest.main()
