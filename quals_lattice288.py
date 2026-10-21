#!/usr/bin/env python3
"""Replicata: run this file. Expectata: exact geometry, enumeration, and resume
contracts hold. Resultata before implementation: lattice288 cannot be imported.
"""
import itertools
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import sympy as sp
import lattice288 as L


class LatticeQuals(unittest.TestCase):
    def test_integer_coset_and_saturated_kernel(self):
        A = [[2, 4, 6, 8], [1, 0, 1, 0]]
        s = L.IntegerSystem(A)
        b = [10, 1]
        y = s.particular(b)
        self.assertEqual(sp.Matrix(A) * sp.Matrix(y), sp.Matrix(b))
        self.assertEqual(len(s.kernel), 2)
        K = sp.Matrix(s.kernel).T
        for x in itertools.product(range(-2, 3), repeat=4):
            if sp.Matrix(A) * sp.Matrix(x) == sp.Matrix(b):
                z = K.gauss_jordan_solve(sp.Matrix(x) - sp.Matrix(y))[0]
                self.assertTrue(all(t.q == 1 for t in z))
        with self.assertRaises(AssertionError):
            s.particular([1, 0])

    def test_perpendicular_component_is_removed(self):
        s = L.IntegerSystem([[1, 1, 1]])
        self.assertEqual(s.radius2([1]), sp.Rational(8, 3))
        self.assertEqual(s.radius2([3]), 0)
        # A nonzero perpendicular component must actually reduce the radius.
        self.assertLess(s.radius2([1]), 3)

    def test_small_control_is_discovered(self):
        A = L.moment_rows(16, 4)
        s = L.IntegerSystem(A)
        y = s.particular([sum(row) // 2 for row in A])
        result = L.enumerate_case(s.reduced(), [2 * x - 1 for x in y],
                                  s.radius2([0] * len(A)), 16, 4,
                                  list(range(8)), {}, 1)
        self.assertEqual(result['outcome'], 'witness')
        self.assertGreater(result['nodes'], 0)
        seq = result['sequence']
        self.assertEqual(len(seq), 16)
        self.assertEqual(seq, seq[::-1])
        self.assertTrue(L.valid(seq, 4))

    def test_witness_check_uses_every_exact_moment(self):
        f = [(-1) ** i.bit_count() for i in range(16)]
        self.assertTrue(L.valid(f, 4))
        self.assertFalse(L.valid(f, 5))
        f[0] *= -1
        self.assertFalse(L.valid(f, 4))
        self.assertFalse(L.valid([0] * 16, 4))

    def test_144_control_is_discovered_without_a_supplied_witness(self):
        job = L.calibration_job()
        self.assertEqual((job['n'], job['order']), (144, 8))
        job['radius2'] = sp.Rational(job['radius2'])
        result = L.enumerate_case(**job)
        self.assertEqual(result['outcome'], 'witness')
        self.assertTrue(L.valid(result['sequence'], 8))

    def test_fixed_coordinate_control_with_nonzero_perpendicular_part(self):
        rows = L.moment_rows(48, 6)
        A = [row[1:] for row in rows]
        c = [-row[0] for row in rows]
        s = L.IntegerSystem(A)
        b = [(t + sum(row)) // 2 for row, t in zip(A, c)]
        target = [2 * x - 1 for x in s.particular(b)]
        self.assertEqual(s.radius2(c), sp.Rational(721408, 32637))
        result = L.enumerate_case(s.reduced(), target, s.radius2(c), 48, 6,
                                  list(range(1, 24)), {0: 1}, L.SEED)
        self.assertEqual(result['outcome'], 'witness')
        self.assertEqual(result['sequence'][0], 1)
        self.assertTrue(L.valid(result['sequence'], 6))

    def test_known_240_witness_belongs_to_the_exact_coset_and_radius(self):
        f = L.ov.from_hex(L.ov.EXAMPLES[240, 10], 10)
        self.assertTrue(L.valid(f, 10))
        self.assertFalse(L.valid(f, 11))
        rows = L.moment_rows(240, 10) + L.count_rows(240, 7)
        keep = list(sp.Matrix(rows).T.rref()[1])
        A = [rows[i] for i in keep]
        a = sp.Matrix(f[:120])
        c = sp.Matrix(A) * a
        s = L.IntegerSystem(A)
        b = [(int(t) + sum(row)) // 2 for row, t in zip(A, c)]
        target = sp.Matrix([2 * x - 1 for x in s.particular(b)])
        z = sp.Matrix(s.kernel).T.gauss_jordan_solve((a - target) / 2)[0]
        self.assertTrue(all(t.q == 1 for t in z))
        perp = sp.Matrix(A).T * s.gram_inverse * c
        projected = a - perp
        self.assertEqual((projected.T * projected)[0], s.radius2(c))
        self.assertLess(s.radius2(c), 120)

    def test_preparation_keeps_2736_cases_and_one_kernel(self):
        prepared = L.prepare()
        self.assertEqual(len(prepared['cases']), 2736)
        self.assertEqual(len(prepared['basis']), 105)
        self.assertEqual(len(prepared['free']), 115)
        first = {tuple(c['profile']) for c in prepared['cases'][:7]}
        self.assertEqual(len(first), 7)
        self.assertTrue(all(len(c['pair']) == 2 for c in prepared['cases']))

    def test_resume_only_skips_completed_attempts(self):
        events = [dict(event='header', version=L.VERSION, n=288, order=10,
                       total=2736, seconds=L.SECONDS, seed=L.SEED, time=1, pid=1),
                  dict(event='session', time=1, pid=1),
                  dict(event='phase', phase='search', time=1, pid=1),
                  dict(event='case_start', case=0, time=2, pid=1),
                  dict(event='case_end', case=0, outcome='timeout', time=3,
                       pid=1, elapsed=1),
                  dict(event='case_start', case=1, time=4, pid=1)]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'journal.jsonl'
            p.write_text(''.join(json.dumps(x) + '\n' for x in events))
            self.assertEqual(L.completed(L.read_journal(p)), {0})
            for change in (dict(case=2736), dict(outcome='infeasible'), dict(case=1),
                           dict(outcome='witness', sequence=[1] * 288)):
                damaged = [dict(e) for e in events]
                damaged[4].update(change)
                p.write_text(''.join(json.dumps(x) + '\n' for x in damaged))
                with self.assertRaises(AssertionError):
                    L.read_journal(p)
            p.write_text(''.join(json.dumps(x) + '\n' for x in events))
            with p.open('a') as f:
                f.write('{"event":')
            with self.assertRaises(AssertionError):
                L.read_journal(p)

    def test_duplicate_runner_fails_before_touching_the_journal(self):
        with tempfile.TemporaryDirectory() as d, patch.object(L, 'WORK', Path(d)):
            with L.lock_run():
                code = ("from pathlib import Path\nimport lattice288 as L\n"
                        f"L.WORK=Path({d!r})\nL.JOURNAL=L.WORK/'journal'\n"
                        "L.PREPARED=L.WORK/'prepared'\nL.main()\n")
                p = subprocess.run([sys.executable, '-B', '-c', code],
                                   capture_output=True, text=True, timeout=5)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn('BlockingIOError', p.stderr)
                self.assertFalse((Path(d) / 'journal').exists())


if __name__ == '__main__':
    unittest.main()
