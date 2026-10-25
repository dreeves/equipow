"""Replicata: run this file. Expectata: exact, reflected residue profiles for
the 560 control and 592 pilot, with no imported witness coordinates.
Resultata before implementation: residue592 is absent.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import mstar
import residue592 as R


class ResidueQuals(unittest.TestCase):
    def test_control_reproduces_archived_profile_and_fixed_orbits(self):
        p = R.control()
        oldpath = Path(__file__).parent / 'scratch/lower24-design/batch1/go560/go560f.py'
        spec = importlib.util.spec_from_file_location('old560_qual', oldpath)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        self.assertEqual(p['D'], list(old.d27(0)))
        self.assertEqual(p['fixed_orbits'], [list(o) for o in old.FIX])
        self.assertEqual(p['extra'], [[M, list(D)] for M, D in old.EXTRA])
        fixed = {tuple(x) for x in p['fixed_orbits']}
        self.assertEqual(sum(len(o['positions']) for o in p['orbits']
                             if tuple(o['residues']) in fixed), 135)
        R.validate(p)

    def test_target_refines_the_specified_modulo_nine_profile(self):
        p = R.target()
        self.assertEqual((p['n'], p['order'], p['modulus']), (592, 10, 27))
        self.assertEqual(tuple(sum(p['D'][r] for r in range(q, 27, 9))
                               for q in range(9)),
                         (54, -24, -30, 54, -30, -24, 54, -27, -27))
        self.assertEqual([M for M, D in p['extra']], [5, 7])
        self.assertTrue(all(any(D) for M, D in p['extra']))
        fixed = {tuple(x) for x in p['fixed_orbits']}
        free = 296 - sum(len(o['positions']) for o in p['orbits']
                         if tuple(o['residues']) in fixed)
        self.assertTrue(130 <= free <= 155)
        self.assertEqual(len(fixed), len(p['fixed_orbits']))
        R.validate(p)

    def test_no_witness_lookup_and_no_mutable_shared_profiles(self):
        with patch.object(mstar, 'explicit', side_effect=AssertionError('witness lookup')), \
                patch.object(mstar, 'build', side_effect=AssertionError('witness lookup')):
            a, b = R.control(), R.target()
            R.validate(a)
            R.validate(b)
        a['D'][0] += 2
        b['extra'][0][1][0] += 2
        R.validate(R.control())
        R.validate(R.target())

    def test_malformed_profiles_fail_exactly(self):
        p = R.target()
        bad = []
        a = deepcopy(p); a['D'][0] += 2; bad.append(a)
        a = deepcopy(p); a['D'][0] = float(a['D'][0]); bad.append(a)
        a = deepcopy(p); a['orbits'][0]['plus'] += 1; bad.append(a)
        a = deepcopy(p); a['orbits'][0]['positions'].pop(); bad.append(a)
        a = deepcopy(p); a['fixed_orbits'].append(a['fixed_orbits'][0]); bad.append(a)
        a = deepcopy(p); a['extra'][0][1][0] += 2; bad.append(a)
        for a in bad:
            with self.subTest(profile=a), self.assertRaises(AssertionError):
                R.validate(a)


if __name__ == '__main__':
    unittest.main()
