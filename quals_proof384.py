"""Quals for Astra's finite certificate of m*(384) = 10.

Replicata: run the proof, enumerate residue counts independently, and damage its
certificates. Expectata: exhaustive rejection of order 11, acceptance of the
known order-10 witness, and loud rejection of damaged or incomplete evidence.
Resultata before implementation: proof384 does not exist, so these quals are red.
"""

from itertools import product
from math import comb
from pathlib import Path
import subprocess
import sys
import unittest

import proof384 as proof


class Quals(unittest.TestCase):
    def test_complete_cover(self):
        result = proof.verify_all()
        self.assertEqual(result['vectors'], 4)
        self.assertEqual(result['cases'], 23716)
        self.assertEqual(result['survivors'], 0)
        self.assertTrue(result['order10_control'])
        self.assertEqual(tuple(level[-1] for level in result['levels']),
                         (0, 0, 0, 0))

    def test_count_enumeration_is_complete(self):
        # Generate every possible signed count divisible by 25 directly from
        # the class sizes; independently check the two linear congruences.
        sizes = tuple(len(range(r, 384, 5)) for r in range(5))
        choices = tuple(tuple(d for d in range(-s, s + 1, 2) if d % 25 == 0)
                        for s in sizes)
        expected = tuple(
            tuple((d + s) // 2 for d, s in zip(ds, sizes))
            for ds in product(*choices)
            if sum(ds) == 0
            and (ds[2] - 4 * ds[0] - 2 * ds[1]) % 125 == 0
            and (ds[3] - 3 * ds[0] - 3 * ds[1]) % 125 == 0
        )
        self.assertEqual(proof.count_vectors(), expected)
        self.assertEqual(expected, ((1, 26, 51, 76, 38),
                                    (26, 76, 1, 51, 38),
                                    (51, 1, 76, 26, 38),
                                    (76, 51, 26, 1, 38)))

    def test_actual_order10_witness(self):
        rows = tuple(tuple(comb(p, k) for p in range(384)) for k in range(11))
        witness = proof.order10_control(rows)
        self.assertEqual(len(witness), 384)
        self.assertEqual(set(witness), {0, 1})
        # Shift to the original problem's positions 1..384, independently of
        # the proof's zero-based binomial rows.
        moments = tuple(sum((2 * bit - 1) * (p + 1) ** k
                            for p, bit in enumerate(witness))
                        for k in range(11))
        self.assertEqual(moments[:10], (0,) * 10)
        self.assertNotEqual(moments[10], 0)

    def test_damaged_certificate_rejected(self):
        for key, certificates in proof.CERTIFICATES.items():
            for i, (modulus, coefficients) in enumerate(certificates):
                changed = list(certificates)
                changed[i] = (modulus, (coefficients[0] + 1,) + coefficients[1:])
                bad = dict(proof.CERTIFICATES)
                bad[key] = tuple(changed)
                with self.subTest(key=key, certificate=i):
                    with self.assertRaises(ValueError):
                        proof.verify_all(bad)

    def test_damaged_modulus_rejected(self):
        for key, certificates in proof.CERTIFICATES.items():
            for i, (modulus, coefficients) in enumerate(certificates):
                for wrong in (0, modulus + 1):
                    changed = list(certificates)
                    changed[i] = (wrong, coefficients)
                    bad = dict(proof.CERTIFICATES)
                    bad[key] = tuple(changed)
                    with self.subTest(key=key, certificate=i, modulus=wrong):
                        with self.assertRaises(ValueError):
                            proof.verify_all(bad)

    def test_missing_coverage_rejected(self):
        for key, certificates in proof.CERTIFICATES.items():
            absent = dict(proof.CERTIFICATES)
            del absent[key]
            empty = dict(proof.CERTIFICATES)
            empty[key] = ()
            incomplete = dict(proof.CERTIFICATES)
            incomplete[key] = certificates[:-1]
            for bad in (absent, empty, incomplete):
                with self.subTest(key=key, certificates=bad):
                    with self.assertRaises(ValueError):
                        proof.verify_all(bad)

    def test_cli_and_optimized_python(self):
        path = Path(proof.__file__).resolve()
        for flags in ((), ('-O',)):
            result = subprocess.run((sys.executable, *flags, str(path)),
                                    capture_output=True, text=True, check=True)
            self.assertIn('Astra: "m*(384) = 10;', result.stdout)
            self.assertIn('23716', result.stdout)
            self.assertEqual(result.stderr, '')
            # Optimization must never disable rejection of false evidence.
            result = subprocess.run(
                (sys.executable, *flags, '-c',
                 'import proof384; proof384.verify_all({})'),
                cwd=path.parent, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ValueError', result.stderr)


if __name__ == '__main__':
    unittest.main()
