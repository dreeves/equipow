"""Reject non-integer proof arithmetic before it can exclude a planted witness.

Replicata: call the second checker with a six-sign order-one witness and
floating certificate values near 2**53. Expectata: reject non-integer input.
Resultata before the fix: cancellation gives K=-4, total=0 and closes the witness.
"""
import copy
from fractions import Fraction
import importlib.util
import io
import json
import os
from pathlib import Path
import gzip
import subprocess
import sys
import tempfile
import unittest

TARGET = Path(os.environ.get('PIN_SECOND', str(Path(__file__).resolve().parents[1] / 'proofs/pintree_second.py')))
spec = importlib.util.spec_from_file_location('second_under_qualification', TARGET)
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

BAD = (1.0, 1.5, True, False, float('nan'), float('inf'), -float('inf'), Fraction(1), Fraction(3, 2))
PINS = {7: (1, 1, 1, -1, -1, -1, 0)}


def data(v=0):
    return dict(n=6, m=1, nodes=[0], sym_depth=0,
                table=[([v], {'7': [-v] * 7}, 1)], tokens=[['L', 0]])


def closes(d):
    c = C.Check(d)
    cl, _, total, _ = c.full(0)
    return abs(c.K(cl, PINS)) > total


class NumberQuals(unittest.TestCase):
    def test_integer_cancellation_preserves_the_witness(self):
        for v in (0, 10**16 + 2, 10**100 + 3, -(10**100 + 3)):
            self.assertFalse(closes(data(v)))

    def test_float_cancellation_cannot_close_the_witness(self):
        with self.assertRaises(ValueError):
            closes(data(1e16 + 2))

    def test_header_numbers_are_exact_integers(self):
        for key in ('n', 'm', 'sym_depth', 'nodes'):
            for bad in BAD:
                with self.subTest(key=key, bad=repr(bad)):
                    d = data()
                    d[key] = [bad] if key == 'nodes' else bad
                    with self.assertRaises(ValueError): C.Check(d)

    def test_direct_polynomial_values_are_integers(self):
        c = C.Check(data())
        for bad in BAD:
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError): c.g_values([bad])

    def test_certificates_reject_noninteger_values_weights_and_scale(self):
        for where in ('values', 'weights', 'scale'):
            for bad in BAD:
                with self.subTest(where=where, bad=repr(bad)):
                    d = data()
                    d['table'] = [[[bad] if where == 'values' else [0],
                                   {'7': [bad] * 7 if where == 'weights' else [0] * 7},
                                   bad if where == 'scale' else 1]]
                    with self.assertRaises(ValueError): C.Check(d).full(0)

    def test_certificate_moduli_do_not_coerce_float_or_bool_keys(self):
        for key in (7.0, True, Fraction(7)):
            d = data()
            d['table'][0][1].clear()
            d['table'][0][1][key] = [0] * 7
            with self.subTest(key=repr(key)):
                with self.assertRaises(ValueError): C.Check(d).full(0)

    def test_certificate_modulus_strings_are_canonical_and_positive(self):
        for key in ('1_6', ' 7', '7 ', '+7', '07', '0', '-7', 0, -7):
            d = data()
            d['table'][0][1].clear()
            d['table'][0][1][key] = [0] * 7
            with self.subTest(key=repr(key)):
                with self.assertRaises(ValueError): C.Check(d).full(0)

    def test_positive_builtin_integer_modulus_keys_remain_supported(self):
        d = data()
        row = d['table'][0][1].pop('7')
        d['table'][0][1][7] = row
        c = C.Check(d)
        cl, _, total, _ = c.full(0)
        self.assertEqual(c.K(cl, PINS), 0)
        self.assertEqual(total, 0)

    def test_direct_K_rejects_noninteger_weights_and_pins(self):
        c = C.Check(data())
        for where in ('weights', 'pins'):
            for bad in BAD:
                with self.subTest(where=where, bad=repr(bad)):
                    cl = {7: [bad] * 7 if where == 'weights' else [0] * 7}
                    pins = {7: [bad] * 7 if where == 'pins' else PINS[7]}
                    with self.assertRaises(ValueError): c.K(cl, pins)

    def test_direct_K_moduli_are_integers(self):
        c = C.Check(data())
        for bad in (7.0, True, Fraction(7)):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError): c.K({bad: [0] * 7}, {bad: PINS[7]})

    def test_mutated_table_is_checked_when_used(self):
        c = C.Check(data())
        c.table[0][1]['7'][0] = 0.0
        with self.assertRaises(ValueError): c.full(0)

    def test_full_weights_survive_caller_mutation_of_certificate_rows(self):
        for value in (1, 1.0, True):
            with self.subTest(value=repr(value)):
                d = data()
                c = C.Check(d)
                cl, w, total, _ = c.full(0)
                d['table'][0][1]['7'][0] = value
                self.assertEqual(c.K(cl, PINS), 0)
                self.assertEqual(sum(a * b for a, b in zip(w, PINS[7])), 0)
                self.assertFalse(abs(c.K(cl, PINS)) > total)

    def test_cached_closure_survives_caller_mutation_of_certificate_rows(self):
        for value in (1, 1.0, True):
            with self.subTest(value=repr(value)):
                d = data()
                c = C.Check(d)
                c.closer(0)
                d['table'][0][1]['7'][0] = value
                cl, total = c.closer(0)
                self.assertEqual(c.K(cl, PINS), 0)
                self.assertFalse(abs(c.K(cl, PINS)) > total)

    def test_certificate_indices_reject_bool_even_when_cached(self):
        d = data()
        d['table'].append(copy.deepcopy(d['table'][0]))
        c = C.Check(d)
        c.closer(1)
        for method in (c.full, c.closer):
            with self.assertRaises(ValueError): method(True)

    def test_direct_admissible_rejects_noninteger_bounds_and_pins(self):
        c = C.Check(data())
        for bad in BAD:
            for lo, hi, pins in (([bad] * 3, None, {}),
                                 (None, [bad] * 3, {}),
                                 (None, None, {1: [bad]})):
                with self.subTest(bad=repr(bad), lo=lo, hi=hi):
                    with self.assertRaises(ValueError): c.admissible(3, pins, lo, hi)

    def test_direct_admissible_modulus_rejects_bool(self):
        with self.assertRaises(ValueError): C.Check(data()).admissible(True, {}, None, None)

    def test_cursor_index_rejects_bool(self):
        with self.assertRaises(ValueError): C.Cursor([['L', 0]], True)

    def test_split_modulus_rejects_bool(self):
        d = data()
        d['tokens'] = [['S', True, None]]
        c = C.Check(d)
        c.cursor = C.Cursor(d['tokens'])
        with self.assertRaises(ValueError): c.node({})

    def test_json_rejects_noninteger_numbers_anywhere(self):
        for literal in ('1.0', '1e0', 'NaN', 'Infinity', '-Infinity', 'true', 'false'):
            for raw in (literal, '{"extra": [' + literal + ']}', '{"nested": {"items": [0, ' + literal + ']}}'):
                with self.subTest(raw=raw):
                    with self.assertRaises(ValueError): C.load(io.StringIO(raw))

    def test_json_preserves_integer_strings_and_null_bounds(self):
        d = dict(n=3, m=1, nodes=[0], sym_depth=0, table=[], tokens=[['S', 3, None]])
        self.assertEqual(C.load(io.StringIO(json.dumps(d))), d)

    def test_tiny_complete_integer_exclusion(self):
        d = dict(n=3, m=1, nodes=[0], sym_depth=0, table=[], tokens=[['S', 3, None]])
        c = C.Check(d)
        c.cursor = C.Cursor(d['tokens'])
        c.node({})
        self.assertEqual(c.cursor.i, 1)
        self.assertEqual(c.stats, dict(closed=0, splits=1, vectors=0, skipped=0, bounds=0))

    def test_integer_witness_remains_in_admissible_vectors(self):
        d = dict(n=4, m=2, nodes=[0, 3], sym_depth=0, table=[], tokens=[])
        c = C.Check(d)
        f = (1, -1, -1, 1)
        for M in (2, 3, 4, 5):
            v = tuple(sum(f[r::M]) for r in range(M))
            self.assertEqual(c.admissible(M, {}, v, v), [v])

    def test_cli_uses_strict_decoding_even_with_optimization(self):
        for bad in (True, 1.0, float('nan')):
            d = dict(n=3, m=1, nodes=[0], sym_depth=0, table=[],
                     tokens=[['S', 3, None]], unused=bad)
            with self.subTest(bad=repr(bad)), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'proof.json.gz'
                with gzip.open(p, 'wt') as f: json.dump(d, f)
                run = subprocess.run([sys.executable, '-B', '-O', str(TARGET), str(p)],
                                     capture_output=True, text=True, timeout=5)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('Numeri integri requiruntur.', run.stderr)

    def test_cli_accepts_complete_integer_proof(self):
        d = dict(n=3, m=1, nodes=[0], sym_depth=0, table=[], tokens=[['S', 3, None]])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'proof.json.gz'
            with gzip.open(p, 'wt') as f: json.dump(d, f)
            run = subprocess.run([sys.executable, '-B', str(TARGET), str(p)],
                                 capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('VERIFIED by the second check', run.stdout)


if __name__ == '__main__': unittest.main()
