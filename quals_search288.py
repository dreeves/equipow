"""Replicata: drive the revised 288 search with deterministic worker outcomes.
Expectata: a checked 240:10 control gates target work, journals resume exactly,
and a completed experiment is never silently repeated. Initially no runner exists.
"""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import search288 as S
import overnight_v5 as ov


class Quals(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        for name, value in [('WORK', self.work), ('JOURNAL', self.work / 'journal.jsonl'),
                            ('CONTROL_TOTAL', 2), ('TOTAL', 3)]:
            p = patch.object(S, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.control = ov.from_hex(ov.EXAMPLES[240, 10], 10)

    def run_with(self, answers):
        with patch.object(S, 'prepare', return_value=[{}]) as prep, \
                patch.object(S, 'bounded', side_effect=answers) as worker, \
                redirect_stdout(io.StringIO()):
            S.run()
        return prep, worker, S.read_journal()

    def witness(self):
        return dict(outcome='witness', sequence=self.control, nodes=1, elapsed=.01)

    def empty(self):
        return dict(outcome='empty', nodes=1, elapsed=.01)

    def test_failed_calibration_never_starts_target(self):
        prep, worker, rows = self.run_with([self.empty()] * 2)
        self.assertEqual([c.args[0] for c in prep.call_args_list], ['calibration'])
        self.assertEqual(worker.call_count, 2)
        self.assertEqual(rows[-1]['outcome'], 'control_failed')
        self.assertNotIn('search', [r.get('phase') for r in rows])

    def test_initial_journal_is_published_with_its_session(self):
        # Replicata: inspect the journal immediately before atomic publication.
        # Expectata: readers see either no journal or a complete initial session.
        # Resultata before repair: header and session were separate visible writes.
        replace = S.os.replace
        def publish(src, dst):
            self.assertFalse(S.JOURNAL.exists())
            rows = [json.loads(line) for line in Path(src).read_text().splitlines()]
            self.assertEqual([r['event'] for r in rows], ['header', 'session', 'phase'])
            replace(src, dst)
        with patch.object(S.os, 'replace', side_effect=publish) as atomic, \
                redirect_stdout(io.StringIO()):
            S.initialize()
        atomic.assert_called_once()
        self.assertEqual(S.read_journal()[-1]['phase'], 'preparation')

    def test_checked_control_unlocks_target_without_claiming_exclusion(self):
        prep, worker, rows = self.run_with([self.witness()] + [self.empty()] * 3)
        self.assertEqual([c.args[0] for c in prep.call_args_list], ['calibration', 'search'])
        self.assertEqual(worker.call_count, 4)
        self.assertEqual(rows[-1]['outcome'], 'budget')
        self.assertEqual(S.completed(rows, 'search'), {0, 1, 2})

    def test_invalid_control_is_rejected(self):
        bad = dict(self.witness(), sequence=[1] * 240)
        with self.assertRaises(AssertionError):
            self.run_with([bad])

    def test_completed_batch_is_not_repeated(self):
        self.run_with([self.empty()] * 2)
        before = S.JOURNAL.read_bytes()
        prep, worker, _ = self.run_with([])
        self.assertEqual(S.JOURNAL.read_bytes(), before)
        prep.assert_not_called()
        worker.assert_not_called()

    def test_interrupted_attempt_is_retried_but_completed_attempt_is_not(self):
        with redirect_stdout(io.StringIO()):
            S.initialize()
            S.record('phase', phase='calibration')
            S.record('attempt_start', phase='calibration', attempt=0)
            S.record('attempt_end', phase='calibration', attempt=0, **self.empty())
            S.record('attempt_start', phase='calibration', attempt=1)
        _, worker, rows = self.run_with([self.witness()] + [self.empty()] * 3)
        self.assertEqual(worker.call_args_list[0].args[1], 1)
        self.assertEqual(S.completed(rows, 'calibration'), {0, 1})
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_changed_source_and_truncated_journal_are_rejected(self):
        self.run_with([self.empty()] * 2)
        data = S.JOURNAL.read_text()
        rows = [json.loads(line) for line in data.splitlines()]
        rows[0]['code'] = 'changed'
        S.JOURNAL.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        with self.assertRaises(AssertionError):
            S.read_journal()
        S.JOURNAL.write_text(data.rstrip('\n'))
        with self.assertRaises(AssertionError):
            S.read_journal()

    def test_wall_timeout_stays_unresolved(self):
        with patch.object(S.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 30)):
            result = S.bounded([{}], 0)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertGreaterEqual(result['elapsed'], 0)

    def test_exclusive_lock_refuses_a_duplicate_runner(self):
        with S.lock_run():
            with self.assertRaises(BlockingIOError):
                with S.lock_run():
                    pass


if __name__ == '__main__':
    unittest.main()
