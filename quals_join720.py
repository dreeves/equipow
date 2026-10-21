#!/usr/bin/env python3
"""Replicata: run this file. Expectata: exact joined models, affine geometry,
and durable bounded-search contracts hold. Resultata before implementation:
join720 cannot be imported.
"""
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import sympy as sp
import mstar
import join720 as J


class JoinQuals(unittest.TestCase):
    def test_control_model_contains_the_known_528_witness(self):
        model = J.model('calibration')
        q = mstar.explicit()[336, 'index.html q336']
        self.assertEqual((len(model['p']), model['q_n'], model['m']), (192, 336, 9))
        self.assertTrue(J.verify(model, q[:168]))
        self.assertEqual(sp.Matrix(model['A']).rank(), 5)
        self.assertNotEqual(model['c'][-1], 0)

    def test_target_model_has_186_free_dimensions(self):
        model = J.model('search')
        self.assertEqual((len(model['p']), model['q_n'], model['m']), (336, 384, 10))
        self.assertEqual(len(model['A']), 6)
        self.assertEqual(sp.Matrix(model['A']).rank(), 6)
        self.assertEqual(model['c'][-1], 15087804481008)
        self.assertEqual(mstar.order(model['p']), 10)

    def test_exact_check_rejects_wrong_moment_and_non_signs(self):
        model = J.model('calibration')
        q = mstar.explicit()[336, 'index.html q336']
        half = q[:168]
        self.assertTrue(J.verify(model, half))
        bad = list(half); bad[0] *= -1
        self.assertFalse(J.verify(model, bad))
        self.assertFalse(J.verify(model, [0] * 168))
        self.assertFalse(J.verify(model, half[:-1]))

    def test_actual_enumerator_finds_an_affine_toy(self):
        model = J.join_model([-1, 1], 6, 1)
        prepared = J.prepare_model(model)
        radius = sp.Rational(prepared['radius2'])
        self.assertEqual(radius, sp.Rational(104, 35))
        self.assertLess(radius, 3)
        result = J.enumerate_job(prepared, 0)
        self.assertEqual(result['outcome'], 'witness')
        self.assertTrue(J.valid(result['sequence'], 2))
        self.assertGreater(result['nodes'], 0)

    def test_dense_affine_search_stops_after_first_witness(self):
        # Replicata: search a dense affine control with many valid witnesses.
        # Expectata: return a verified witness within 100 enumeration nodes.
        # Resultata before the correction: optimizing the best solution took 439.
        model = J.join_model([-1, 1], 34, 1)
        prepared = J.prepare_model(model)
        result = J.enumerate_job(prepared, 0)
        self.assertEqual(result['outcome'], 'witness')
        self.assertTrue(J.valid(result['sequence'], 2))
        self.assertLessEqual(result['nodes'], 100)

    def test_large_affine_representative_is_recentered_with_sufficient_precision(self):
        # Replicata: translate a valid affine representative by 2^450 lattice steps.
        # Expectata: recover a small odd representative in the same exact coset.
        # Resultata at fixed 212-bit precision: the nearest-plane bound fails.
        model = J.join_model([-1, 1], 6, 1)
        prepared = J.prepare_model(model)
        B = J.IntegerMatrix.from_matrix(prepared['basis'])
        J.LLL.reduction(B)
        target = [x + 2 ** 450 * int(y) for x, y in zip(prepared['target'], B[0])]
        perpendicular2 = 3 - sp.Rational(prepared['radius2'])
        _, small = J.recenter(B, target, perpendicular2)
        self.assertGreater(J.working_precision(prepared['basis'], target), 450)
        self.assertLess(max(abs(x).bit_length() for x in small), 64)
        self.assertEqual(sp.Matrix(model['A']) * sp.Matrix(small), sp.Matrix(model['c']))
        self.assertTrue(all(x % 2 for x in small))

    def events(self):
        control = J.model('calibration')['p'] + mstar.explicit()[336, 'index.html q336']
        return [dict(event='header', version=J.VERSION, n=720, order=11,
                     total=J.TOTAL, control_total=J.CONTROL_TOTAL, seconds=J.SECONDS,
                     code=J.CODE, libraries=J.LIBRARIES, time=1, pid=1),
                dict(event='session', time=1, pid=1),
                dict(event='phase', phase='calibration', time=1, pid=1),
                dict(event='attempt_start', phase='calibration', attempt=0, time=2, pid=1),
                dict(event='attempt_end', phase='calibration', attempt=0, time=3, pid=1,
                     outcome='witness', sequence=control, elapsed=1, nodes=2),
                dict(event='phase', phase='search', time=4, pid=1),
                dict(event='attempt_start', phase='search', attempt=0, time=5, pid=1),
                dict(event='attempt_end', phase='search', attempt=0, time=6, pid=1,
                     outcome='timeout', elapsed=1),
                dict(event='attempt_start', phase='search', attempt=1, time=7, pid=1)]

    def test_resume_keeps_completed_attempts_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'journal.jsonl'
            events = self.events()
            path.write_text(''.join(json.dumps(e) + '\n' for e in events))
            got = J.read_journal(path)
            self.assertEqual(J.completed(got, 'search'), {0})
            self.assertTrue(J.calibrated(got))
            events += [dict(event='session', time=8, pid=2),
                       dict(event='phase', phase='search', time=9, pid=2),
                       dict(event='attempt_start', phase='search', attempt=1, time=10, pid=2)]
            path.write_text(''.join(json.dumps(e) + '\n' for e in events))
            self.assertEqual(J.completed(J.read_journal(path), 'search'), {0})

    def test_bad_records_fail_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'journal.jsonl'
            events = self.events()
            for change in (dict(outcome='excluded'), dict(attempt=16),
                           dict(sequence=[1] * 528), dict(elapsed=-1)):
                broken = [dict(e) for e in events]
                broken[4].update(change)
                path.write_text(''.join(json.dumps(e) + '\n' for e in broken))
                with self.assertRaises(AssertionError):
                    J.read_journal(path)
            path.write_text(''.join(json.dumps(e) + '\n' for e in events) + '{')
            with self.assertRaises(AssertionError):
                J.read_journal(path)
            broken = events[:2] + events[5:]
            path.write_text(''.join(json.dumps(e) + '\n' for e in broken))
            with self.assertRaises(AssertionError):
                J.read_journal(path)

    def test_timeout_is_unresolved_and_no_control_blocks_search(self):
        with tempfile.TemporaryDirectory() as d, patch.object(J, 'WORK', Path(d)), \
                patch.object(J, 'JOURNAL', Path(d) / 'journal.jsonl'), \
                patch.object(J, 'prepare', return_value={}), \
                patch.object(J, 'bounded', return_value=dict(outcome='timeout', elapsed=0)):
            J.run()
            events = J.read_journal(J.JOURNAL)
            self.assertEqual(events[-1]['outcome'], 'control_failed')
            self.assertFalse(J.completed(events, 'search'))
            self.assertEqual(len(J.completed(events, 'calibration')), J.CONTROL_TOTAL)

    def test_worker_timeout_covers_reduction_and_enumeration(self):
        with tempfile.TemporaryDirectory() as d, patch.object(J, 'WORK', Path(d)), \
                patch.object(J.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', J.SECONDS)) as run:
            result = J.bounded({}, 0)
            self.assertEqual(result['outcome'], 'timeout')
            self.assertEqual(run.call_args.kwargs['timeout'], J.SECONDS)
            self.assertGreaterEqual(result['elapsed'], 0)

    def test_duplicate_runner_fails_before_creating_a_journal(self):
        with tempfile.TemporaryDirectory() as d, patch.object(J, 'WORK', Path(d)), \
                patch.object(J, 'JOURNAL', Path(d) / 'journal.jsonl'):
            with J.lock_run(), self.assertRaises(BlockingIOError):
                J.main()
            self.assertFalse(J.JOURNAL.exists())

    def test_terminal_witness_resume_does_no_more_search(self):
        events = [dict(event='attempt_end', phase='search', attempt=0, outcome='witness')]
        with tempfile.TemporaryDirectory() as d, patch.object(J, 'WORK', Path(d)), \
                patch.object(J, 'JOURNAL', Path(d) / 'journal.jsonl'), \
                patch.object(J, 'read_journal', return_value=events), \
                patch.object(J, 'record') as record, patch.object(J, 'prepare') as prepare:
            J.JOURNAL.touch()
            J.run()
            prepare.assert_not_called()
            self.assertEqual(record.call_args.args, ('finish',))
            self.assertEqual(record.call_args.kwargs, dict(outcome='witness'))


if __name__ == '__main__':
    unittest.main()
