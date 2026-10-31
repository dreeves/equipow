#!/usr/bin/env python3
"""Replicata: run this file. Expectata: necessary residue rows strengthen a
matched join without losing solutions or selecting an ambiguous profile.
Resultata before implementation: join720.residue_model is absent.
"""
from copy import deepcopy
from itertools import product
import unittest
from unittest.mock import patch

import sympy as sp
import mstar
import join720 as J


def radius2(model):
    A, c = sp.Matrix(model['A']), sp.Matrix(model['c'])
    return model['q_n'] // 2 - (c.T * (A * A.T).inv() * c)[0]


def satisfies(model, half):
    return all(sum(a * x for a, x in zip(row, half)) == rhs
               for row, rhs in zip(model['A'], model['c']))


class ResidueQuals(unittest.TestCase):
    def test_small_complete_sign_cubes_keep_every_joined_solution(self):
        # Replicata: enumerate every half-sign vector in two small joins.
        # Expectata: residue strengthening preserves exactly their valid joins.
        # Resultata without the helper: the strengthened model is unavailable.
        for m in (2, 3):
            raw = J.join_model(mstar.thue_morse(m), 2 ** m, m)
            strong = J.residue_model(raw)
            halves = list(product((-1, 1), repeat=raw['q_n'] // 2))
            actual = {x for x in halves if J.verify(raw, x)}
            retained = {x for x in halves if satisfies(strong, x)}
            self.assertTrue(actual)
            self.assertEqual(retained, actual)

    def test_control_keeps_known_witness_and_shrinks_exact_affine_radius(self):
        # Replicata: strengthen the fixed-prefix 528 control before enumeration.
        # Expectata: its known witness remains and four forced directions vanish.
        # Resultata without the helper: the 163-dimensional geometry remains.
        raw = J.model('calibration')
        strong = J.residue_model(raw)
        q = mstar.explicit()[336, 'equipow q336']
        self.assertTrue(satisfies(strong, q[:168]))
        self.assertTrue(J.verify(strong, q[:168]))
        self.assertEqual(sp.Matrix(strong['A']).rank(), 9)
        self.assertEqual(len(strong['A']), 9)
        self.assertLess(radius2(strong), radius2(raw))
        self.assertLess(sp.Rational(149), radius2(strong))
        self.assertLess(radius2(strong), sp.Rational(150))

    def test_target_has_three_additional_forced_directions(self):
        # Replicata: strengthen the 720 target using only its fixed prefix.
        # Expectata: three independent residue equations leave dimension 183.
        # Resultata without the helper: the raw six-row model is unstrengthened.
        raw = J.model('search')
        strong = J.residue_model(raw)
        self.assertEqual(sp.Matrix(strong['A']).rank(), 9)
        self.assertEqual(len(strong['A']), 9)
        self.assertEqual(192 - len(strong['A']), 183)
        self.assertLess(radius2(strong), radius2(raw))
        self.assertLess(sp.Rational(175), radius2(strong))
        self.assertLess(radius2(strong), sp.Rational(176))

    def test_strengthening_uses_only_the_supplied_prefix_and_preserves_input(self):
        # Replicata: deny witness lookup and candidate checking during preparation.
        # Expectata: exact residue preparation succeeds without those operations.
        # Resultata without the helper: preparation cannot be performed.
        raw = J.model('calibration')
        before = deepcopy(raw)
        with patch.object(mstar, 'explicit', side_effect=AssertionError('witness lookup')), \
                patch.object(mstar, 'build', side_effect=AssertionError('witness lookup')), \
                patch.object(J, 'verify', side_effect=AssertionError('candidate hint')), \
                patch.object(J, 'joined', side_effect=AssertionError('candidate hint')):
            strong = J.residue_model(raw)
        self.assertEqual(raw, before)
        self.assertEqual(strong['p'], raw['p'])
        self.assertEqual((strong['q_n'], strong['m']), (raw['q_n'], raw['m']))
        self.assertGreater(len(strong['A']), len(raw['A']))

    def test_ambiguous_residue_profiles_fail_without_pinning_the_first(self):
        # Replicata: use a valid small affine join with several mod-2 profiles.
        # Expectata: ambiguity raises; it must not silently select one profile.
        # Resultata without the helper: AttributeError replaces the required assert.
        raw = J.join_model([-1, 1], 6, 1)
        self.assertTrue(any(J.verify(raw, x) for x in product((-1, 1), repeat=3)))
        with self.assertRaises(AssertionError):
            J.residue_model(raw)


class ResidueCaseQuals(unittest.TestCase):
    def test_complete_small_case_union_preserves_every_joined_solution(self):
        # Replicata: enumerate both reflection parities, including ambiguous profiles.
        # Expectata: the union of all residue cases equals every valid sign solution.
        # Resultata before implementation: residue_cases is absent.
        examples = [([-1, 1], 6, 1, 2), (mstar.thue_morse(2), 12, 2, 5)]
        for p, b, m, modulus in examples:
            raw = J.join_model(p, b, m)
            cases = J.residue_cases(raw, modulus)
            halves = list(product((-1, 1), repeat=b // 2))
            actual = {x for x in halves if J.verify(raw, x)}
            retained = {x for x in halves if any(satisfies(c, x) for c in cases)}
            self.assertTrue(actual)
            self.assertEqual(retained, actual)
            self.assertTrue(all(sum(satisfies(c, x) for c in cases) == 1 for x in actual))

    def test_all_seven_control_cases_keep_the_witness_in_exactly_one(self):
        # Replicata: partition the strengthened 528 control by its mod-7 sums.
        # Expectata: all seven alternatives survive; exactly one contains known q.
        # Resultata before implementation: there is no complete case family.
        model = J.residue_model(J.model('calibration'))
        cases = J.residue_cases(model, 7)
        q = mstar.explicit()[336, 'equipow q336'][:168]
        self.assertEqual(len(cases), 7)
        self.assertEqual(sum(satisfies(c, q) for c in cases), 1)
        self.assertTrue(all(len(c['A']) == sp.Matrix(c['A']).rank() == 12 for c in cases))
        self.assertTrue(all(radius2(c) < radius2(model) for c in cases))

    def test_both_target_cases_have_180_free_dimensions(self):
        # Replicata: partition the strengthened 720 target by its mod-7 sums.
        # Expectata: two alternatives each add three independent equations.
        # Resultata before implementation: the family is unavailable.
        model = J.residue_model(J.model('search'))
        cases = J.residue_cases(model, 7)
        self.assertEqual(len(cases), 2)
        self.assertTrue(all(len(c['A']) == sp.Matrix(c['A']).rank() == 12 for c in cases))
        self.assertTrue(all(c['q_n'] // 2 - len(c['A']) == 180 for c in cases))

    def test_family_construction_uses_no_witnesses_or_mutation(self):
        # Replicata: deny witness lookup and candidate checking during partitioning.
        # Expectata: all alternatives derive from the supplied equations and prefix.
        # Resultata before implementation: residue_cases is absent.
        model = J.residue_model(J.model('calibration'))
        before = deepcopy(model)
        with patch.object(mstar, 'explicit', side_effect=AssertionError('witness lookup')), \
                patch.object(mstar, 'build', side_effect=AssertionError('witness lookup')), \
                patch.object(J, 'verify', side_effect=AssertionError('candidate hint')), \
                patch.object(J, 'joined', side_effect=AssertionError('candidate hint')):
            cases = J.residue_cases(model, 7)
        self.assertEqual(model, before)
        self.assertEqual(len(cases), 7)
        self.assertTrue(all((c['p'], c['q_n'], c['m']) ==
                            (model['p'], model['q_n'], model['m']) for c in cases))


if __name__ == '__main__':
    unittest.main()
