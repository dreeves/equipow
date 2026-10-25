"""Quals for reuse of the independently checked 288 target cosets."""
import copy
import json
from pathlib import Path
import unittest

import target288


class TargetQuals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared = json.loads(Path('.lattice288_prepared.json').read_text())

    def test_existing_cases_have_the_geometry_contract(self):
        # Replicata: the archived preparation used by the completed 288 batch.
        # Expectata: every saved coset validates, with explicit exact geometry.
        # Resultata before implementation: no target adapter exists.
        models = target288.target_cases()
        self.assertEqual(len(models), 2736)
        for model, original in zip(models, self.prepared['cases']):
            self.assertEqual(set(model), {'n', 'order', 'free', 'fixed', 'A', 'c',
                                          'basis', 'target', 'radius2'})
            self.assertEqual((model['n'], model['order']), (288, 10))
            self.assertEqual((len(model['A']), len(model['free']), len(model['basis'])), (10, 115, 105))
            self.assertEqual(model['target'], original['target'])
            self.assertEqual([p for p, s in model['fixed'] if s == 1], original['pair'])

    def test_wrong_source_identity_is_rejected(self):
        # Replicata: preparation claiming an unrelated source fingerprint.
        # Expectata: rejection before any numerical search.
        data = copy.deepcopy(self.prepared)
        data['code'] = '0' * 64
        with self.assertRaises(AssertionError):
            target288.checked(data)

    def test_wrong_kernel_is_rejected(self):
        # Replicata: an even perturbation of one stored lattice row.
        # Expectata: the exact kernel equations reject it.
        data = copy.deepcopy(self.prepared)
        data['basis'][0][0] += 2
        with self.assertRaises(AssertionError):
            target288.checked(data)

    def test_dependent_kernel_is_rejected(self):
        # Replicata: duplicate kernel rows, still satisfying all equations.
        # Expectata: the rank guard rejects the incomplete real span.
        data = copy.deepcopy(self.prepared)
        data['basis'][0] = data['basis'][1][:]
        with self.assertRaises(AssertionError):
            target288.checked(data)

    def test_wrong_case_fields_are_rejected(self):
        # Replicata: perturb an odd target, its fixed plus pair, or its radius.
        # Expectata: the full moment/residue equations or exact radius reject it.
        variants = (('target', lambda case: case['target'].__setitem__(0, case['target'][0] + 2)),
                    ('pair', lambda case: case.__setitem__('pair', [1, 6])),
                    ('radius', lambda case: case.__setitem__('radius', '0')))
        for field, change in variants:
            with self.subTest(field=field):
                data = copy.deepcopy(self.prepared)
                change(data['cases'][0])
                with self.assertRaises(AssertionError):
                    target288.checked(data)


if __name__ == '__main__':
    unittest.main()
