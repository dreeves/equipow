#!/usr/bin/env python3
"""Replicata: run this file. Expectata: paired curves search identical exact
geometry and preserve the prior baseline. Resultata before implementation:
pruning288_geometry cannot be imported.
"""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

import sympy as sp
import search288_geometry as G
import pruning288_geometry as P


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


class GeometryQuals(unittest.TestCase):
    def test_frozen_baseline_matches_the_prior_kernel(self):
        # Replicata: freeze the same small model and seed used by the prior kernel.
        # Expectata: identical reduced basis, centered target, curve, and witness.
        # Resultata before implementation: no independently reusable geometry exists.
        prepared = G.prepare_models([G.model(16, 4, [])])[0]
        before = deepcopy(prepared)
        captured = {}
        recenter, pruning = G.recenter, G.pruning_curve
        def center(B, target, perpendicular):
            M, target = recenter(B, target, perpendicular)
            captured.update(basis=[list(B[i]) for i in range(B.nrows)], target=list(target))
            return M, target
        def curve(M, tau, radius):
            values = pruning(M, tau, radius)
            captured['pruning'] = list(values)
            return values
        with patch.object(G, 'recenter', side_effect=center), \
                patch.object(G, 'pruning_curve', side_effect=curve):
            old = G.enumerate_job(prepared, 0)
        frozen = P.freeze(prepared, 0)
        self.assertEqual(prepared, before)
        self.assertEqual({k: frozen[k] for k in captured}, captured)
        actual = P.enumerate_frozen(frozen, 0)
        self.assertEqual({k: actual[k] for k in old}, old)
        self.assertEqual(actual['curve'], frozen['pruning'])
        self.assertGreaterEqual(actual['enumeration_seconds'], 0)

    def test_freezing_preserves_the_exact_integer_lattice_coset_and_radius(self):
        # Replicata: freeze a model with a nonzero fixed-coordinate contribution.
        # Expectata: an unchanged integer lattice, exact affine coset and radius.
        # Resultata before implementation: geometry cannot be frozen and checked.
        prepared = G.prepare_models([G.model(16, 4, [[0, 1]])])[0]
        frozen = P.freeze(prepared, 1)
        A, c = sp.Matrix(frozen['A']), sp.Matrix(frozen['c'])
        B, old = sp.Matrix(frozen['basis']), sp.Matrix(prepared['basis'])
        transform = old.T.gauss_jordan_solve(B.T)[0]
        self.assertTrue(all(a.q == 1 for a in transform))
        self.assertEqual(abs(transform.det()), 1)
        self.assertEqual(A * B.T, sp.zeros(A.rows, B.rows))
        self.assertEqual(A * sp.Matrix(frozen['target']), c)
        shift = old.T.gauss_jordan_solve(sp.Matrix(frozen['target'])
                                        - sp.Matrix(prepared['target']))[0]
        self.assertTrue(all(a.q == 1 for a in shift))
        radius = A.cols - (c.T * (A * A.T).inv() * c)[0]
        self.assertEqual(sp.Rational(frozen['radius2']), radius)
        self.assertEqual(frozen['seed'], G.SEED + 1)
        self.assertEqual(frozen['attempt'], 1)
        self.assertEqual(frozen['basis_hash'], digest(frozen['basis']))

    def test_paired_json_roundtrip_uses_identical_geometry_and_nested_curves(self):
        # Replicata: serialize frozen geometry and run both approved widths.
        # Expectata: both exact controls, immutable geometry, pointwise widening.
        # Resultata before implementation: each attempt rebuilds a different basis.
        frozen = P.freeze(G.prepare_models([G.model(16, 4, [])])[0], 0)
        frozen = json.loads(json.dumps(frozen))
        before = deepcopy(frozen)
        results = [P.enumerate_frozen(frozen, width) for width in (0, .10)]
        self.assertEqual(frozen, before)
        self.assertTrue(all(r['outcome'] == 'witness' and G.valid(r['sequence'], 4)
                            for r in results))
        self.assertEqual(results[0]['curve'], frozen['pruning'])
        self.assertEqual(results[1]['curve'], [.10 + .90 * x for x in frozen['pruning']])
        self.assertEqual(P.curve(frozen, 0), results[0]['curve'])
        self.assertEqual(P.curve(frozen, .10), results[1]['curve'])
        self.assertTrue(all(b >= a for a, b in zip(results[0]['curve'], results[1]['curve'])))
        for result, width in zip(results, (0, .10)):
            self.assertEqual(result['width'], width)
            self.assertEqual(result['curve'][0], 1.)
            for field in ('basis_hash', 'geometry_hash', 'seed'):
                self.assertEqual(result[field], frozen[field])
            self.assertEqual(result['seed_attempt'], frozen['attempt'])
            self.assertNotIn('attempt', result)
        unhashed = dict(frozen)
        self.assertEqual(unhashed.pop('geometry_hash'), digest(unhashed))

    def test_recomputed_baseline_must_equal_the_stored_curve(self):
        # Replicata: change the stored baseline and recompute its file identity.
        # Expectata: independent GSO reconstruction rejects the changed curve.
        # Resultata before implementation: no frozen-curve integrity check exists.
        frozen = P.freeze(G.prepare_models([G.model(16, 4, [])])[0], 0)
        frozen['pruning'][-1] *= .5
        frozen.pop('geometry_hash')
        frozen['geometry_hash'] = digest(frozen)
        with patch.object(P, 'Enumeration', side_effect=AssertionError('enumeration reached')) as enum:
            with self.assertRaises(AssertionError):
                P.enumerate_frozen(frozen, 0)
        enum.assert_not_called()

    def test_only_the_two_approved_widths_are_accepted(self):
        # Replicata: ask for another width or corrupt frozen geometry.
        # Expectata: rejection before enumeration, without modifying inputs.
        # Resultata before implementation: the fixed paired-study contract is absent.
        frozen = P.freeze(G.prepare_models([G.model(16, 4, [])])[0], 0)
        for width in (-.1, .01, .25, 1, True, '0.1'):
            with self.assertRaises(AssertionError):
                P.enumerate_frozen(frozen, width)
        damaged = deepcopy(frozen)
        damaged['target'][0] += 2
        with self.assertRaises(AssertionError):
            P.enumerate_frozen(damaged, 0)


if __name__ == '__main__':
    unittest.main()
