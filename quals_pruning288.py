"""Replicata: drive the paired study with deterministic worker outcomes.
Expectata: both controls gate target work; paired geometry stays fixed; resume
never repeats completed attempts. Resultata initially: no paired runner exists.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import overnight_v5 as ov
import pruning288 as P


class Quals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        work = Path(self.tmp.name)
        for name, value in [('WORK', work), ('JOURNAL', work / 'pruning288_journal.jsonl')]:
            p = patch.object(P, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.control = ov.from_hex(ov.EXAMPLES[240, 10], 10)
        self.geometries = {phase: [dict(attempt=i, seed=20261024+i, basis_hash='basis'+str(i),
                                      geometry_hash='geometry'+str(i), pruning=[1., .3],
                                      basis=[[2, 0], [0, 2]])
                                  for i in indices]
                           for phase, indices in [('calibration', [2]), ('search', range(7))]}

    def answer(self, outcome='empty'):
        answer = dict(outcome=outcome, elapsed=.01, enumeration_seconds=.001, nodes=1)
        if outcome == 'witness':
            answer['sequence'] = self.control
        return answer

    def run_with(self, answers):
        with patch.object(P, 'prepare', side_effect=lambda phase: self.geometries[phase]) as prep, \
                patch.object(P, 'bounded', side_effect=answers) as work, redirect_stdout(io.StringIO()):
            P.run()
        return prep, work, P.read_journal()

    def test_both_controls_are_required(self):
        for answers in ([self.answer('witness'), self.answer()], [self.answer(), self.answer('witness')]):
            with self.subTest(answers=answers):
                P.JOURNAL.unlink(missing_ok=True)
                prep, work, rows = self.run_with(answers)
                self.assertEqual(work.call_count, 2)
                self.assertEqual([c.args[0] for c in prep.call_args_list], ['calibration'])
                self.assertEqual(rows[-1]['outcome'], 'control_failed')

    def test_paired_targets_share_geometry_and_never_claim_exclusion(self):
        prep, work, rows = self.run_with([self.answer('witness')]*2 + [self.answer()]*14)
        self.assertEqual(rows[-1]['outcome'], 'budget')
        self.assertEqual(work.call_count, 16)
        for a, b in zip(work.call_args_list[::2], work.call_args_list[1::2]):
            self.assertIs(a.args[0], b.args[0])
            self.assertEqual((a.args[1], b.args[1]), (0, .1))
        self.assertEqual([c.args[0] for c in prep.call_args_list], ['calibration', 'search'])
        self.assertEqual(P.completed(rows, 'search'), set(range(14)))

    def test_invalid_witness_is_rejected(self):
        wrong = dict(self.answer('witness'), sequence=[1]*240)
        with self.assertRaises(AssertionError):
            self.run_with([wrong])

    def test_completed_batch_is_not_repeated(self):
        self.run_with([self.answer()]*2)
        before = P.JOURNAL.read_bytes()
        prep, work, _ = self.run_with([])
        prep.assert_not_called()
        work.assert_not_called()
        self.assertEqual(P.JOURNAL.read_bytes(), before)

    def test_interrupted_attempt_resumes_without_repeating_completed_pairs(self):
        with self.assertRaises(RuntimeError):
            self.run_with([self.answer('witness')]*2 + [self.answer()]*2 + [RuntimeError('stop')])
        _, work, rows = self.run_with([self.answer()]*12)
        self.assertEqual(work.call_count, 12)
        self.assertEqual(work.call_args_list[0].args[0]['attempt'], 1)
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_changed_input_or_paired_geometry_is_rejected(self):
        self.run_with([self.answer('witness')]*2 + [self.answer()]*14)
        original = P.JOURNAL.read_text()
        rows = [json.loads(line) for line in original.splitlines()]
        rows[0]['input'] = 'changed'
        P.JOURNAL.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaises(AssertionError):
            P.read_journal()
        rows = [json.loads(line) for line in original.splitlines()]
        next(r for r in rows if r['event']=='attempt_start' and r['phase']=='search' and r['attempt']==1)['geometry_hash'] = 'changed'
        P.JOURNAL.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaises(AssertionError):
            P.read_journal()

    def test_timeout_keeps_comparison_identity_without_inventing_nodes(self):
        frozen = self.geometries['calibration'][0]
        with patch.object(P.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 30)):
            result = P.bounded(frozen, .1)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertIsNone(result['nodes'])
        self.assertIsNone(result['enumeration_seconds'])
        self.assertGreaterEqual(result['elapsed'], 0)

    def test_initial_publication_is_atomic_and_lock_is_exclusive(self):
        replace = P.os.replace
        def publish(src, dst):
            self.assertFalse(P.JOURNAL.exists())
            rows = [json.loads(line) for line in Path(src).read_text().splitlines()]
            self.assertEqual([r['event'] for r in rows], ['header', 'session', 'phase'])
            replace(src, dst)
        with patch.object(P.os, 'replace', side_effect=publish) as atomic, redirect_stdout(io.StringIO()):
            P.initialize()
        atomic.assert_called_once()
        with P.lock_run():
            with self.assertRaises(BlockingIOError):
                with P.lock_run():
                    pass


if __name__ == '__main__':
    unittest.main()
