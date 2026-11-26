"""Quals for the constructive symmetry proof, its certificate, and the published threshold."""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'proofs'))


class SymmetryConstruction(unittest.TestCase):
    def test_witness_from_its_literal_signs(self):
        # Replicata: reconstruct the published sequence and undo its first mirror pair as a control.
        # Expectata: the normalized witness has exact order 15 and the control loses it.
        # Resultata before: the witness program lived only in scratch.
        import sym15
        word = sym15.witness()
        self.assertEqual(len(word), 795280)
        self.assertEqual(word[0], 1)
        self.assertTrue(all(a == -b for a, b in zip(word, reversed(word))))
        jet = sym15.moments(word, 15)
        self.assertEqual(jet[:15], [0] * 15)
        self.assertNotEqual(jet[15], 0)
        word[0], word[-1] = -word[0], -word[-1]
        self.assertNotEqual(sym15.moments(word, 1)[1], 0)

    def test_transport_on_literal_words(self):
        # Replicata: construct both possible symmetries and undo a mirror pair.
        # Expectata: all moments through degree m-1 vanish only before the change.
        # Resultata before: the general construction had no checker in the repository.
        import symtransport
        for m in (2, 3, 4):
            half = symtransport.right_half(m)
            word = [(-1)**m * a for a in reversed(half)] + half
            self.assertEqual(len(word), symtransport.seed_length(m))
            self.assertEqual(len(word) % (2 << m.bit_length()), 1 << m.bit_length())
            def moments():
                return [sum(a * math.comb(i, k) for i, a in enumerate(word)) for k in range(m)]
            self.assertEqual(moments(), [0]*m)
            word[0] *= -1
            word[-1] *= -1
            self.assertNotEqual(moments(), [0]*m)

    def test_transport_coordinates_and_bounds(self):
        # Replicata: decompose the initial half's defect and calculate its size at order 15.
        # Expectata: exact integral coefficients, including the signs and all 8192 summands.
        # Resultata before: the page only gave thresholds from the Fourier estimate.
        import symtransport
        self.assertEqual(symtransport.coordinates(15), [3218, -2502, 1502, -682, 228, -52, 8])
        for m in range(2, 33):
            L = symtransport.seed_length(m)
            T = 1 << m.bit_length()
            self.assertEqual(L % (2*T), T)
            self.assertLess(L, 2**(8*m))

    def test_cutoff_has_all_sixty_side_lengths(self):
        # Replicata: build the 60 order-14 sides in the seed proof from the page's own codes.
        # Expectata: the actual signs have the required moments; 960 is a repeatable block.
        # Resultata before: neither this cutoff nor its order-15 center had a public certificate.
        import quals_symmetry as qs
        import sym15
        lengths = range(6128, 6128 + 960, 16)
        _, _, build = qs.closure(qs.sources(N=lengths[-1]), N=lengths[-1])
        for n in lengths:
            a = build(None, n)
            self.assertEqual(len(a), n)
            self.assertTrue(qs.holds(a, 14), n)
        self.assertTrue(qs.holds(build(None, 960), 15))
        self.assertEqual(len(sym15.witness()) + 2*lengths.start, 807536)


if __name__ == '__main__':
    unittest.main()
