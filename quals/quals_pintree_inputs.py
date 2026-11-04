"""Replicata: noninteger proof arithmetic inputs and an exact integer control.
Expectata: malformed numbers fail before arithmetic; the integer controls hold.
Resultata before: floats and booleans pass, and floating weights can exclude a witness.
"""
import copy
import gzip
import importlib.util
import json
import os
from pathlib import Path
import random
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = Path(os.environ.get('PIN_FIRST', str(ROOT / 'proofs/pintree.py')))
spec = importlib.util.spec_from_file_location('first', SOURCE)
first = importlib.util.module_from_spec(spec)
spec.loader.exec_module(first)
BAD = (0.0, True, float('nan'), float('inf'), float('-inf'))
ERRORS = (AssertionError, ValueError, TypeError)
A = (1, 1, 1, -1, -1, -1)
PINS = {7: A + (0,)}
CERT = ([0], {'7': [0] * 7}, 1)
PROOF = {'n': 40, 'm': 6, 'nodes': list(range(6)), 'table': [],
         'tokens': [['S', 5, None], ['S', 3, None]], 'sym_depth': 1}

class ValidationQuals(unittest.TestCase):
    def test_original_floating_false_closure_is_rejected(self):
        v = 1e16 + 2
        with self.assertRaises(ERRORS):
            first.Weights(6, (0,), ([v], {'7': [-v] * 7}, 1)).closes(PINS)

    def test_certificate_numbers_reject_float_bool_and_nonfinite(self):
        for value in BAD:
            for where in ('values', 'classes', 'T'):
                with self.subTest(value=value, where=where), self.assertRaises(ERRORS):
                    c = copy.deepcopy(CERT)
                    if where == 'values': c[0][0] = value
                    elif where == 'classes': c[1]['7'][0] = value
                    else: c = (c[0], c[1], value)
                    first.Weights(6, (0,), c)

    def test_node_coordinates_and_length_reject_nonintegers(self):
        for value in BAD:
            with self.subTest(value=value, where='node'), self.assertRaises(ERRORS):
                first.Weights(6, (value,), CERT)
            with self.subTest(value=value, where='length'), self.assertRaises(ERRORS):
                first.Weights(value, (0,), CERT)

    def test_class_moduli_are_canonical_integer_strings(self):
        for key in (7.0, True, '+7', '07', ' 7'):
            with self.subTest(key=key), self.assertRaises(ERRORS):
                first.Weights(6, (0,), ([0], {key: [0] * int(key)}, 1))

    def test_direct_pins_reject_nonintegers(self):
        w = first.Weights(6, (0,), CERT)
        for value in BAD:
            with self.subTest(value=value), self.assertRaises(ERRORS):
                w.closes({7: (value,) + PINS[7][1:]})
        for key in (7.0, True):
            with self.subTest(key=key), self.assertRaises(ERRORS):
                w.K({key: (0,) * int(key)})

    def test_bound_indices_and_sign_are_integers(self):
        w = first.Weights(6, (0,), CERT)
        for args in ((7.0, 0, 1), (7, 0.0, 1), (7, 0, 1.0), (7, False, 1), (7, 0, True)):
            with self.subTest(args=args), self.assertRaises(ERRORS):
                w.bound(PINS, *args)

    def test_replay_metadata_rejects_nonintegers(self):
        for field in ('n', 'm', 'sym_depth'):
            for value in (True, 1.0):
                with self.subTest(field=field, value=value), self.assertRaises(ERRORS):
                    d = copy.deepcopy(PROOF)
                    d[field] = value
                    first.Replay(d['n'], d['m'], d['nodes'], d['table'], d['tokens'], d['sym_depth'])
        with self.assertRaises(ERRORS):
            first.Replay(40, 6, [0.0, 1, 2, 3, 4, 5], [], [], 1)

    def test_references_are_nonnegative_integer_indices(self):
        R = first.Replay(6, 1, [0], [CERT, CERT], [], 1)
        for index in (-1, True, 0.0):
            with self.subTest(index=index), self.assertRaises(ERRORS):
                R.weights(index)

    def test_class_and_pin_vectors_have_the_named_length(self):
        with self.assertRaises(ERRORS):
            first.Weights(6, (0,), ([0], {'7': [0] * 8}, 1))
        with self.assertRaises(ERRORS):
            first.Weights(6, (0,), CERT).K({7: PINS[7] + (0,)})

    def test_json_rejects_all_floats_and_nonfinite_constants(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory) / 'proof.gz'
            for value in (0.0, 1.0, 1e100, float('nan'), float('inf'), float('-inf')):
                with self.subTest(value=value), self.assertRaises(ERRORS):
                    d = {**PROOF, 'unused': value}
                    with gzip.open(path, 'wt') as f: json.dump(d, f)
                    first.verify(path)

    def test_integer_witness_control(self):
        rng = random.Random(864)
        for _ in range(30):
            cert = ([rng.randrange(-100, 101)], {'7': [rng.randrange(-100, 101) for _ in range(7)]}, rng.randrange(1, 50))
            w = first.Weights(6, (0,), cert)
            self.assertEqual(sum(a * b for a, b in zip(w.w, A)), w.Den * w.K(PINS))
            self.assertFalse(w.closes(PINS))
            for M in (3, 4, 7):
                for r in range(M):
                    D = sum(A[r::M])
                    self.assertLessEqual(D, w.bound(PINS, M, r, 1))
                    self.assertLessEqual(-D, w.bound(PINS, M, r, -1))

        a = tuple((-1) ** p.bit_count() for p in range(64))
        pins = {M: tuple(sum(a[r::M]) for r in range(M)) for M in (3, 5, 7, 8)}
        cert = ([(-1) ** k * (2 ** (100 + k) + k) for k in range(6)],
                {str(M): [2 ** 80 + r for r in range(M)] for M in pins}, 2 ** 64)
        w = first.Weights(64, tuple(range(6)), cert)
        self.assertEqual(sum(x * y for x, y in zip(w.w, a)), w.Den * w.K(pins))
        self.assertFalse(w.closes(pins))
        for r in range(9):
            self.assertLessEqual(sum(a[r::9]), w.bound(pins, 9, r, 1))
            self.assertLessEqual(-sum(a[r::9]), w.bound(pins, 9, r, -1))

    def test_caller_mutation_cannot_change_a_prepared_certificate(self):
        for replacement in (1, 0.5, True):
            with self.subTest(replacement=replacement):
                row = [0] * 7
                w = first.Weights(6, (0,), ([0], {'7': row}, 1))
                self.assertFalse(w.closes(PINS))
                row[0] = replacement
                self.assertEqual(w.K(PINS), 0)
                self.assertFalse(w.closes(PINS))
                self.assertEqual(w.total, 0)

    def test_tiny_complete_integer_proof(self):
        d = PROOF
        result = first.Replay(d['n'], d['m'], d['nodes'], [], d['tokens'], d['sym_depth']).run()
        self.assertEqual(result, {'closed by certificate': 0, 'splits': 2, 'skipped by symmetry': 0, 'vectors': 1, 'bounds': 0})

if __name__ == '__main__':
    unittest.main()
