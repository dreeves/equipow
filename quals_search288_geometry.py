#!/usr/bin/env python3
"""Replicata: run this file. Expectata: exact symmetric witness geometry,
complete calibration profiles, and independently discovered small controls.
Resultata before implementation: search288_geometry cannot be imported.
"""
from copy import deepcopy
from itertools import product
import json
import unittest
from unittest.mock import patch

import sympy as sp
import search288_geometry as G


def satisfies(model, signs):
    return all(sum(a * x for a, x in zip(row, signs)) == rhs
               for row, rhs in zip(model['A'], model['c']))


class GeometryQuals(unittest.TestCase):
    def test_small_control_is_discovered_and_stops_at_first_solution(self):
        # Replicata: search the symmetric 16:4 model without witness hints.
        # Expectata: an exact witness, using first-solution enumeration.
        # Resultata before implementation: no new enumeration kernel exists.
        prepared = G.prepare_models([G.model(16, 4, [])])[0]
        with patch.object(G, 'Enumeration', wraps=G.Enumeration) as enum:
            result = G.enumerate_job(prepared, 0)
        self.assertEqual(result['outcome'], 'witness')
        self.assertGreater(result['nodes'], 0)
        self.assertEqual(len(result['sequence']), 16)
        self.assertEqual(result['sequence'], result['sequence'][::-1])
        self.assertTrue(G.valid(result['sequence'], 4))
        self.assertEqual(enum.call_args.kwargs['strategy'],
                         G.EvaluatorStrategy.FIRST_N_SOLUTIONS)

    def test_shared_preparation_preserves_fixed_coordinates_and_exact_cosets(self):
        # Replicata: prepare both signs at position zero, then roundtrip JSON.
        # Expectata: one saturated kernel, exact affine radii, both valid witnesses.
        # Resultata before implementation: this shared preparation is unavailable.
        models = [G.model(16, 4, [[0, sign]]) for sign in (-1, 1)]
        before = deepcopy(models)
        with patch.object(G, 'IntegerSystem', wraps=G.IntegerSystem) as system:
            prepared = G.prepare_models(models)
        self.assertEqual(system.call_count, 1)
        self.assertEqual(models, before)
        self.assertEqual(prepared[0]['basis'], prepared[1]['basis'])
        for model, part in zip(models, json.loads(json.dumps(prepared))):
            A, c = sp.Matrix(model['A']), sp.Matrix(model['c'])
            self.assertEqual(A * sp.Matrix(part['target']), c)
            self.assertTrue(all(a % 2 for a in part['target']))
            self.assertEqual(A * sp.Matrix(part['basis']).T,
                             sp.zeros(A.rows, len(part['basis'])))
            radius = A.cols - (c.T * (A * A.T).inv() * c)[0]
            self.assertEqual(sp.Rational(part['radius2']), radius)
            self.assertLess(radius, A.cols)
            result = G.enumerate_job(part, 1)
            self.assertEqual(result['outcome'], 'witness')
            self.assertEqual(result['sequence'][0], model['fixed'][0][1])
            self.assertTrue(G.valid(result['sequence'], 4))

    def test_residue_case_union_keeps_every_small_symmetric_witness(self):
        # Replicata: compare every symmetric 16-sign sequence with each partition.
        # Expectata: every exact witness belongs to exactly one residue case.
        # Resultata before implementation: complete residue cases are unavailable.
        raw = G.model(16, 4, [])
        halves = list(product((-1, 1), repeat=8))
        actual = {x for x in halves if G.valid(list(x) + list(x[::-1]), 4)}
        self.assertTrue(actual)
        for modulus in (3, 5, 7):
            cases = G.residue_cases(raw, modulus)
            retained = {x for x in halves if any(satisfies(c, x) for c in cases)}
            self.assertEqual(retained, actual)
            self.assertTrue(all(sum(satisfies(c, x) for c in cases) == 1
                                for x in actual))

    def test_calibration_derives_all_six_profiles_without_witness_lookup(self):
        # Replicata: prohibit known-witness access while deriving 240:10 models.
        # Expectata: all six symmetric mod-7 profiles, no fixed coordinates.
        # Resultata before implementation: no matched calibration models exist.
        with patch.object(G.mstar, 'explicit', side_effect=AssertionError), \
                patch.object(G.mstar, 'build', side_effect=AssertionError), \
                patch.object(G.ov, 'from_hex', side_effect=AssertionError), \
                patch.object(G, 'valid', side_effect=AssertionError):
            models = G.calibration_models()
        self.assertEqual(len(models), 6)
        self.assertTrue(all((m['n'], m['order']) == (240, 10) for m in models))
        self.assertTrue(all(m['fixed'] == [] and m['free'] == list(range(120))
                            for m in models))
        self.assertTrue(all(m['A'] == models[0]['A'] for m in models))
        self.assertEqual(len({tuple(m['c']) for m in models}), 6)
        self.assertEqual(sp.Matrix(models[0]['A']).rank(), len(models[0]['A']))
        # A known witness is used only here, after independent model derivation.
        f = G.ov.from_hex(G.ov.EXAMPLES[240, 10], 10)
        self.assertEqual(sum(satisfies(m, f[:120]) for m in models), 1)

    def test_malformed_fixed_coordinates_fail_immediately(self):
        # Replicata: supply duplicate, out-of-range, or nonsign fixed entries.
        # Expectata: every malformed model raises before preparation/search.
        # Resultata before implementation: model construction is unavailable.
        for fixed in ([[0, 1], [0, -1]], [[8, 1]], [[0, 0]], [['0', 1]]):
            with self.assertRaises(AssertionError):
                G.model(16, 4, fixed)


if __name__ == '__main__':
    unittest.main()
