#!/usr/bin/env python3
"""Replicata: run this file. Expectata: exact streamed lattice attempts.
Resultata before implementation: search592_geometry cannot be imported.
"""
from copy import deepcopy
from itertools import product
import json
import unittest
from unittest.mock import patch

import sympy as sp
import search592_geometry as G


def tiny(order=4):
    n, modulus = 32, 7
    signs = [(-1) ** ((p % 16).bit_count()) for p in range(n)]
    D = [sum(signs[r::modulus]) for r in range(modulus)]
    orbits = []
    for r in range(modulus):
        s = (n - 1 - r) % modulus
        if r <= s:
            positions = [p for p in range(n // 2) if p % modulus in (r, s)]
            orbits.append(dict(residues=[r, s], positions=positions,
                               plus=sum(signs[p] == 1 for p in positions)))
    return dict(n=n, order=order, modulus=modulus, D=D, orbits=orbits,
                fixed_orbits=[[0, 3], [4, 6]], extra=[])


def stream(instance):
    cursor = [instance.slice_index, 0]
    out = []
    while True:
        selection = instance.next_case(cursor)
        if selection is None:
            return out
        out.append(selection)
        cursor = selection['next_cursor']


class GeometryQuals(unittest.TestCase):
    def test_stream_exactly_covers_integer_consistent_placements_and_slices(self):
        profile = tiny()
        before = deepcopy(profile)
        whole = G.Instance(profile, seed=6, slice_index=0, nslices=1)
        selections = stream(whole)
        cfgs = {tuple(s['case']['choices']) for s in selections}
        expected = {cfg for cfg in product(*(range(len(c)) for c in whole.choices))
                    if whole.consistent(whole.u_of(cfg))}
        self.assertEqual(cfgs, expected)
        self.assertEqual(len(cfgs), len(selections))
        sliced = [stream(G.Instance(profile, 6, i, 3)) for i in range(3)]
        self.assertEqual({tuple(s['case']['choices']) for group in sliced for s in group}, cfgs)
        self.assertEqual(sum(map(len, sliced)), len(cfgs))
        self.assertEqual(profile, before)
        self.assertEqual(json.loads(json.dumps(selections)), selections)
        for selected in selections:
            self.assertEqual(whole.next_case(selected['case']['cursor']), selected)

    def test_lifts_full_rows_exact_radii_and_shared_basis(self):
        instance = G.Instance(tiny(), 6, 0, 1)
        basis = deepcopy(instance.basis)
        for selection in stream(instance):
            case = selection['case']
            u = instance.u_of(case['choices'])
            y = instance.particular(u)
            self.assertEqual(sp.Matrix(instance.A) * sp.Matrix(y), sp.Matrix(instance.b_of(u)))
            model = instance.model(case)
            A, c = sp.Matrix(model['A']), sp.Matrix(model['c'])
            self.assertEqual(A * sp.Matrix(model['target']), c)
            self.assertTrue(all(a % 2 for a in model['target']))
            self.assertEqual(A * sp.Matrix(model['basis']).T, sp.zeros(A.rows, len(basis)))
            self.assertEqual(sp.Rational(model['radius2']), A.cols - (c.T * (A * A.T).inv() * c)[0])
            self.assertEqual(model['basis'], basis)

    def test_small_control_exact_first_solution_and_fixed_shape(self):
        # The initial seed6 fixture returned empty; seed2 independently recovers
        # this small control with the unchanged production pruning shape.
        instance = G.Instance(tiny(), 2, 0, 1)
        found = []
        with patch.object(G, 'Enumeration', wraps=G.Enumeration) as enum:
            for selection in stream(instance):
                result = instance.enumerate_case(selection['case'])
                if result['outcome'] == 'witness':
                    found.append(result)
        self.assertTrue(found)
        self.assertEqual(enum.call_args.kwargs['strategy'], G.EvaluatorStrategy.FIRST_N_SOLUTIONS)
        for result in found:
            self.assertTrue(G.valid(result['sequence'], 4))
            self.assertTrue(all(type(a) is int for a in result['sequence']))
            self.assertEqual(result['sequence'], result['sequence'][::-1])
            self.assertEqual(result['curve'], G.shape_vector(len(instance.basis)))
            self.assertEqual(result['basis_hash'], instance.summary()['basis_hash'])
            self.assertGreaterEqual(result['nodes'], 1)
            self.assertGreaterEqual(result['enumeration_seconds'], 0)

    def test_large_exact_coset_shift_is_recentered_without_cancellation(self):
        instance = G.Instance(tiny(2), 6, 0, 1)
        case = instance.next_case([0, 0])['case']
        ordinary = instance.particular
        def huge(u):
            return [y + 10 ** 100 * k for y, k in zip(ordinary(u), instance.K[0])]
        with patch.object(instance, 'particular', side_effect=huge):
            model = instance.model(case)
            result = instance.enumerate_case(case)
        self.assertGreater(model['precision'], 400)
        self.assertLess(max(map(abs, model['target'])), 1000)
        self.assertEqual(result['outcome'], 'witness')
        self.assertTrue(G.valid(result['sequence'], 2))

    def test_deterministic_metadata_and_malformed_cases_fail(self):
        instance = G.Instance(tiny(), 6, 0, 1)
        repeat = G.Instance(tiny(), 6, 0, 1)
        self.assertEqual(instance.summary(), repeat.summary())
        selection = instance.next_case([0, 0])
        self.assertEqual(selection, repeat.next_case([0, 0]))
        self.assertEqual(instance.model(selection['case']), repeat.model(selection['case']))
        for cursor in ([-1, 0], [0, -1], [0.0, 0], [0], [0, 1000]):
            with self.assertRaises(AssertionError):
                instance.next_case(cursor)
        broken = deepcopy(selection['case'])
        broken['prefix'] += 1
        with self.assertRaises(AssertionError):
            instance.model(broken)
        broken = tiny()
        broken['orbits'][0]['plus'] += 1
        with self.assertRaises(AssertionError):
            G.Instance(broken, 6, 0, 1)

    def test_negative_exact_radius_skips_enumeration(self):
        instance = G.Instance(tiny(), 6, 0, 1)
        selected = next(s for s in stream(instance)
                        if sp.Rational(instance.model(s['case'])['radius2']) < 0)
        with patch.object(G, 'Enumeration', side_effect=AssertionError):
            result = instance.enumerate_case(selected['case'])
        self.assertEqual(result['outcome'], 'empty')
        self.assertEqual(result['nodes'], 0)
        self.assertEqual(result['enumeration_seconds'], 0.)

    def test_immediate_empty_counter_sentinel_is_not_reported_as_work(self):
        instance = G.Instance(tiny(), 6, 0, 1)
        result = instance.enumerate_case(instance.next_case([0, 0])['case'])
        self.assertEqual(result['outcome'], 'empty')
        self.assertEqual(result['raw_nodes'], 2 ** 64 - 1)
        self.assertIn(2 ** 64 - 1, result['node_levels'])
        self.assertIsNone(result['nodes'])


if __name__ == '__main__':
    unittest.main()
