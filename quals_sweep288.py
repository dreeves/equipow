#!/usr/bin/env python3
"""Replicata: run this file. Expectata: one persistent checked worker, bounded
attempts, exact witness gating and resumable journals. Initially sweep288 is absent.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import sweep288 as S


class RunnerQuals(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        for name, value in [('WORK', self.work), ('JOURNAL', self.work/'journal'), ('TOTAL', 3)]:
            p = patch.object(S, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.control = S.ov.from_hex(S.ov.EXAMPLES[240, 10], 10)

    def answer(self, phase, attempt, outcome='empty'):
        result = dict(S.metadata(phase, attempt), outcome=outcome, nodes=1,
                      enumeration_seconds=.001, elapsed=.01,
                      basis_hash='a'*64, geometry_hash='b'*64)
        if outcome == 'witness':
            result['sequence'] = self.control
        return result

    def drive(self, answers):
        with patch.object(S, 'Worker') as factory, redirect_stdout(io.StringIO()):
            worker = factory.return_value
            worker.execute.side_effect = answers
            S.run()
        return worker, S.read_journal()

    def test_control_gates_targets_and_completed_batch_does_not_repeat(self):
        worker, rows = self.drive([self.answer('calibration', 0)])
        self.assertEqual(worker.execute.call_count, 1)
        self.assertEqual(rows[-1]['outcome'], 'control_failed')
        before = S.JOURNAL.read_bytes()
        worker, _ = self.drive([])
        self.assertEqual(S.JOURNAL.read_bytes(), before)
        worker.ready.assert_not_called()

    def test_control_success_runs_every_case_and_replays_only_once(self):
        answers = [self.answer('calibration', 0, 'witness')]
        answers += [self.answer('search', i) for i in range(3)]
        with patch.object(S, 'read_journal', wraps=S.read_journal) as read:
            worker, rows = self.drive(answers)
        self.assertLessEqual(read.call_count, 2)
        self.assertEqual(worker.execute.call_count, 4)
        self.assertEqual(S.completed(rows, 'search'), {0, 1, 2})
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_incomplete_attempt_retries_but_completed_attempt_does_not(self):
        with redirect_stdout(io.StringIO()):
            S.initialize()
            S.record('phase', phase='calibration')
            S.record('attempt_start', phase='calibration', attempt=0, **S.metadata('calibration', 0))
            S.record('attempt_end', phase='calibration', attempt=0, **self.answer('calibration', 0, 'witness'))
            S.record('phase', phase='search')
            S.record('attempt_start', phase='search', attempt=0, **S.metadata('search', 0))
            S.record('attempt_end', phase='search', attempt=0, **self.answer('search', 0))
            S.record('attempt_start', phase='search', attempt=1, **S.metadata('search', 1))
        worker, rows = self.drive([self.answer('search', i) for i in (1, 2)])
        self.assertEqual(worker.execute.call_args_list[0].args, ('search', 1))
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_changed_identity_and_bad_witness_are_rejected(self):
        self.drive([self.answer('calibration', 0)])
        rows = [json.loads(line) for line in S.JOURNAL.read_text().splitlines()]
        rows[0]['input'] = {}
        S.JOURNAL.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaises(AssertionError):
            S.read_journal()
        bad = self.answer('calibration', 0, 'witness')
        bad['sequence'] = [1]*240
        with self.assertRaises(AssertionError):
            S.check_answer('calibration', 0, bad)

    def test_witness_coordinates_must_be_integers_not_bools_or_floats(self):
        # Replicata: replace one +1 in an exact tiny witness with True or 1.0.
        # Expectata: reject both before any purported exact power-sum check.
        # Resultata before repair: bools and floats satisfy valid's set equality.
        with patch.dict(S.QUESTIONS, search=(16, 4)):
            for value in (True, 1.0):
                answer = self.answer('search', 0, 'witness')
                answer['sequence'] = [(-1)**i.bit_count() for i in range(16)]
                answer['sequence'][0] = answer['sequence'][-1] = value
                with self.assertRaises(AssertionError):
                    S.check_answer('search', 0, answer)

    def test_target_witness_finishes_and_resume_after_witness_needs_no_worker(self):
        # Replicata: stop after recording a target witness but before its finish.
        # Expectata: resume writes only the finish; a finished run stays untouched.
        # Resultata without this path: a recovered witness could trigger more work.
        target = self.answer('search', 0, 'witness')
        target['sequence'] = [(-1)**i.bit_count() for i in range(16)]
        with patch.dict(S.QUESTIONS, search=(16, 4)):
            worker, rows = self.drive([self.answer('calibration', 0, 'witness'), target])
            self.assertEqual(worker.execute.call_count, 2)
            self.assertEqual(rows[-1]['outcome'], 'witness')
            S.JOURNAL.write_text(''.join(json.dumps(r)+'\n' for r in rows[:-1]))
            worker, rows = self.drive([])
            worker.ready.assert_not_called()
            worker.execute.assert_not_called()
            self.assertEqual(rows[-1]['outcome'], 'witness')
            before = S.JOURNAL.read_bytes()
            worker, _ = self.drive([])
            self.assertEqual(S.JOURNAL.read_bytes(), before)
            worker.ready.assert_not_called()

    def test_atomic_initialization_and_exclusive_lock(self):
        replace = S.os.replace
        def publish(src, dst):
            self.assertFalse(S.JOURNAL.exists())
            self.assertEqual([json.loads(x)['event'] for x in Path(src).read_text().splitlines()],
                             ['header', 'session', 'phase'])
            replace(src, dst)
        with patch.object(S.os, 'replace', side_effect=publish), redirect_stdout(io.StringIO()):
            S.initialize()
        with S.lock_run():
            with self.assertRaises(BlockingIOError):
                with S.lock_run():
                    pass


class WorkerQuals(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def script(self, body):
        path = self.work/'child.py'
        path.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0, '+repr(str(S.ROOT))+')\n'+body)
        return [sys.executable, '-B', str(path)]

    def test_two_real_tiny_jobs_reuse_the_same_worker(self):
        command = self.script("import sweep288 as S\n"
            "tiny=S.G.G.prepare_models([S.G.G.model(16,4,[])])[0]\n"
            "S.load_cases=lambda: {'calibration':[tiny]*3,'search':[tiny]*2}\n"
            "S.references=lambda: {}\nS.QUESTIONS.update(calibration=(16,4),search=(16,4))\nS.worker()\n")
        with patch.dict(S.QUESTIONS, calibration=(16,4), search=(16,4)):
            worker = S.Worker(command)
            self.addCleanup(worker.close)
            worker.ready()
            pid = worker.process.pid
            a = worker.execute('search', 0)
            b = worker.execute('search', 1)
            self.assertEqual(worker.process.pid, pid)
            self.assertEqual((a['outcome'], b['outcome']), ('witness', 'witness'))
            self.assertTrue(S.valid(a['sequence'],4) and S.valid(b['sequence'],4))

    def test_timeout_reaps_old_worker_and_replacement_can_succeed(self):
        marker = self.work/'started'
        command = self.script("import json,time\nimport sweep288 as S\n"
            f"p=Path({str(marker)!r})\nfirst=not p.exists()\np.touch()\n"
            "print(json.dumps(S.ready_message()),flush=True)\n"
            "for line in sys.stdin:\n"
            " job=json.loads(line)\n"
            " if first: sys.stdout.write('{');sys.stdout.flush();time.sleep(5)\n"
            " answer=dict(S.metadata(job['phase'],job['attempt']),outcome='empty',nodes=1,enumeration_seconds=0,basis_hash='a'*64,geometry_hash='b'*64)\n"
            " print(json.dumps(dict(code=S.CODE,input=S.INPUT,**job,answer=answer)),flush=True)\n")
        worker = S.Worker(command)
        self.addCleanup(worker.close)
        worker.ready()
        old = worker.process
        with patch.object(S, 'SECONDS', .1):
            result = worker.execute('search', 0)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertIsNone(result['nodes'])
        self.assertIsNotNone(old.poll())
        self.assertIsNone(worker.process)
        worker.ready()
        self.assertNotEqual(worker.process.pid, old.pid)
        self.assertEqual(worker.execute('search', 1)['outcome'], 'empty')

    def test_crash_and_changed_worker_hash_fail_without_restart(self):
        for body in ("import json,os\nimport sweep288 as S\nprint(json.dumps(S.ready_message()),flush=True)\nsys.stdin.readline()\nos._exit(7)\n",
                     "import json,time\nimport sweep288 as S\nr=S.ready_message();r['code']='changed'\nprint(json.dumps(r),flush=True)\ntime.sleep(5)\n"):
            worker = S.Worker(self.script(body))
            with self.assertRaises(AssertionError):
                worker.ready()
                worker.execute('search', 0)
            pid = worker.process.pid
            self.assertEqual(worker.process.pid, pid)
            worker.close()


if __name__ == '__main__':
    unittest.main()
