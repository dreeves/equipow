"""Runner and JSON-line transport quals; no production geometry is prepared."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib
import io
import json
from pathlib import Path
import tempfile
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import call, patch

import overnight_v5 as ov


class RunnerQuals(unittest.TestCase):
    def setUp(self):
        self.S = importlib.import_module('search592')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        for name, value in (('WORK', self.work), ('JOURNAL', self.work / 'journal'),
                            ('CONTROL_TOTAL', 2), ('TOTAL', 3)):
            context = patch.object(self.S, name, value)
            context.start()
            self.addCleanup(context.stop)
        context = patch.object(self.S.shutil, 'disk_usage', return_value=SimpleNamespace(free=1 << 40))
        context.start()
        self.addCleanup(context.stop)
        # Known 560 witness is confined to this qual; it must never seed production preparation.
        self.control = ov.from_hex('34D2E9F0DA19EC92492D966936ABCA25FAD924D26F2591EB64926924925D6E1A4BFE92', 10)

    def identity(self, phase):
        return dict(basis_hash='b' * 64, profile_hash=self.S.INPUT[phase], plan_hash='c' * 64)

    def fields(self, phase, attempt):
        settings = self.S.SETTINGS[phase]
        return dict(case=attempt, **settings, **self.identity(phase),
                    placement=dict(prefix=attempt, choices=[0],
                                   cursor=[settings['slice_index'] + settings['nslices'] * attempt, 0]),
                    shape=list(self.S.G.SHAPE))

    def answer(self, phase, attempt, outcome='empty'):
        result = dict(self.fields(phase, attempt), outcome=outcome, nodes=1, raw_nodes=1,
                      node_levels=[1], enumeration_seconds=.001, elapsed=.01,
                      geometry_hash='d' * 64, radius2='16')
        if outcome == 'witness':
            result['sequence'] = self.control
        if outcome == 'timeout':
            result.update(nodes=None, raw_nodes=None, node_levels=None, enumeration_seconds=None,
                          geometry_hash=None, radius2=None)
        return result

    def drive(self, answers):
        with patch.object(self.S, 'Worker') as factory, redirect_stdout(io.StringIO()):
            worker = factory.return_value
            worker.ready.side_effect = self.identity
            worker.fields.side_effect = self.fields
            worker.execute.side_effect = answers
            self.S.run()
        return worker, self.S.read_journal()

    def test_failed_control_batch_never_starts_target_and_completion_is_noop(self):
        # Replicata: both controls fail, one empty and one timed out; invoke the completed run again.
        # Expectata: no target work; a control_failed finish; the next invocation changes no journal bytes.
        worker, rows = self.drive([self.answer('calibration', 0), self.answer('calibration', 1, 'timeout')])
        self.assertEqual(worker.execute.call_args_list, [call('calibration', 0), call('calibration', 1)])
        self.assertTrue(all(c.args == ('calibration',) for c in worker.ready.call_args_list))
        self.assertEqual(rows[-1]['outcome'], 'control_failed')
        before = self.S.JOURNAL.read_bytes()
        worker, _ = self.drive([])
        self.assertEqual(self.S.JOURNAL.read_bytes(), before)
        worker.ready.assert_not_called()
        worker.execute.assert_not_called()

    def test_control_witness_skips_remaining_controls_and_runs_target_batch(self):
        # Replicata: the first control succeeds, followed by the three allowed target attempts.
        # Expectata: skip unused controls, record phase/attempt identities, and replay only once before work.
        answers = [self.answer('calibration', 0, 'witness')] + [self.answer('search', i) for i in range(3)]
        with patch.object(self.S, 'read_journal', wraps=self.S.read_journal) as read:
            worker, rows = self.drive(answers)
        self.assertLessEqual(read.call_count, 2)
        self.assertEqual(worker.execute.call_args_list,
                         [call('calibration', 0)] + [call('search', i) for i in range(3)])
        self.assertEqual(self.S.completed(rows, 'calibration'), {0})
        self.assertEqual(self.S.completed(rows, 'search'), {0, 1, 2})
        self.assertEqual(rows[-1]['outcome'], 'budget')
        for row in rows:
            if row['event'] == 'phase' and row['phase'] in ('calibration', 'search'):
                self.assertTrue(all(row[k] == v for k, v in self.identity(row['phase']).items()))
            if row['event'] in ('attempt_start', 'attempt_end'):
                self.assertTrue(all(row[k] == v for k, v in self.fields(row['phase'], row['attempt']).items()))

    def test_later_control_witness_still_unlocks_targets(self):
        # Replicata: first control empty, second recovered.
        # Expectata: only the verified recovery unlocks all target attempts.
        answers = [self.answer('calibration', 0), self.answer('calibration', 1, 'witness')]
        answers += [self.answer('search', i) for i in range(3)]
        worker, rows = self.drive(answers)
        self.assertEqual(worker.execute.call_count, 5)
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_incomplete_target_retries_without_repeating_completed_work(self):
        # Replicata: saved control recovery, completed target 0, and an interrupted target 1.
        # Expectata: resume only targets 1 and 2, preserving the recorded phase identity.
        with redirect_stdout(io.StringIO()):
            self.S.initialize()
            self.S.record('phase', phase='calibration', **self.identity('calibration'))
            self.S.record('attempt_start', phase='calibration', attempt=0, **self.fields('calibration', 0))
            self.S.record('attempt_end', phase='calibration', attempt=0, **self.answer('calibration', 0, 'witness'))
            self.S.record('phase', phase='search', **self.identity('search'))
            self.S.record('attempt_start', phase='search', attempt=0, **self.fields('search', 0))
            self.S.record('attempt_end', phase='search', attempt=0, **self.answer('search', 0))
            self.S.record('attempt_start', phase='search', attempt=1, **self.fields('search', 1))
        worker, rows = self.drive([self.answer('search', 1, 'timeout'), self.answer('search', 2)])
        self.assertEqual(worker.execute.call_args_list, [call('search', 1), call('search', 2)])
        self.assertTrue(all(c.args == ('search',) for c in worker.ready.call_args_list))
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_target_witness_ends_early_and_crash_before_finish_is_recoverable(self):
        # Replicata: a tiny exact target witness, then remove only its finish record and resume.
        # Expectata: no later attempt runs; resume adds finish without preparing a worker; completion is a no-op.
        target = self.answer('search', 0, 'witness')
        target['sequence'] = [(-1) ** i.bit_count() for i in range(16)]
        with patch.dict(self.S.QUESTIONS, search=(16, 4)):
            worker, rows = self.drive([self.answer('calibration', 0, 'witness'), target])
            self.assertEqual(worker.execute.call_args_list, [call('calibration', 0), call('search', 0)])
            self.assertEqual(rows[-1]['outcome'], 'witness')
            self.S.JOURNAL.write_text(''.join(json.dumps(r) + '\n' for r in rows[:-1]))
            worker, rows = self.drive([])
            worker.ready.assert_not_called()
            worker.execute.assert_not_called()
            self.assertEqual(rows[-1]['outcome'], 'witness')
            before = self.S.JOURNAL.read_bytes()
            worker, _ = self.drive([])
            self.assertEqual(self.S.JOURNAL.read_bytes(), before)
            worker.ready.assert_not_called()

    def test_worker_error_records_failure_closes_worker_and_can_resume(self):
        # Replicata: a worker fails before returning its first control result.
        # Expectata: record failed, close it, then retry that incomplete control on a later invocation.
        with patch.object(self.S, 'Worker') as factory, redirect_stdout(io.StringIO()):
            worker = factory.return_value
            worker.ready.side_effect = self.identity
            worker.fields.side_effect = self.fields
            worker.execute.side_effect = RuntimeError('qual')
            with self.assertRaises(RuntimeError):
                self.S.run()
            worker.close.assert_called_once()
        self.assertEqual(self.S.read_journal()[-1]['outcome'], 'failed')
        answers = [self.answer('calibration', 0, 'witness')] + [self.answer('search', i) for i in range(3)]
        worker, rows = self.drive(answers)
        self.assertEqual(worker.execute.call_args_list[0], call('calibration', 0))
        self.assertEqual(rows[-1]['outcome'], 'budget')

    def test_atomic_initialization_and_exclusive_lock(self):
        # Replicata: publish the initial journal and attempt to acquire its lock twice.
        # Expectata: readers first see header/session/preparation together; a second holder is refused.
        replace = self.S.os.replace
        def publish(src, dst):
            self.assertFalse(self.S.JOURNAL.exists())
            self.assertEqual([json.loads(x)['event'] for x in Path(src).read_text().splitlines()],
                             ['header', 'session', 'phase'])
            replace(src, dst)
        with patch.object(self.S.os, 'replace', side_effect=publish), redirect_stdout(io.StringIO()):
            self.S.initialize()
        with self.S.lock_run():
            with self.assertRaises(BlockingIOError):
                with self.S.lock_run():
                    pass

    def test_journal_rejects_changed_inputs_and_attempt_identity(self):
        # Replicata: a completed valid journal with one header, phase, start, or end field corrupted.
        # Expectata: replay rejects each corruption instead of accepting a different prepared computation.
        _, rows = self.drive([self.answer('calibration', 0, 'witness')]
                             + [self.answer('search', i) for i in range(3)])
        phase = next(i for i, r in enumerate(rows) if r['event'] == 'phase' and r['phase'] == 'search')
        start = next(i for i, r in enumerate(rows) if r['event'] == 'attempt_start' and r['phase'] == 'search')
        end = next(i for i, r in enumerate(rows) if r['event'] == 'attempt_end' and r['phase'] == 'search')
        for index, key, value in ((0, 'input', {}), (0, 'code', 'changed'),
                                  (phase, 'basis_hash', 'e' * 64), (start, 'seed', -1),
                                  (end, 'plan_hash', 'e' * 64), (end, 'profile_hash', 'f' * 64),
                                  (end, 'placement', dict(prefix=999, choices=[0], cursor=[0, 0]))):
            with self.subTest(index=index, key=key):
                broken = deepcopy(rows)
                broken[index][key] = value
                self.S.JOURNAL.write_text(''.join(json.dumps(r) + '\n' for r in broken))
                with self.assertRaises(AssertionError):
                    self.S.read_journal()
        self.S.JOURNAL.write_text(''.join(json.dumps(r) + '\n' for r in rows).rstrip('\n'))
        with self.assertRaises(AssertionError):
            self.S.read_journal()

    def test_answer_is_bound_to_expected_fields_and_shape(self):
        # Replicata: a valid empty answer with one prepared identity, placement, setting or shape changed.
        # Expectata: the optional expected_fields signature binds every attempt to its start record.
        expected = self.fields('search', 0)
        answer = self.answer('search', 0)
        self.S.check_answer('search', 0, answer, expected)
        for key, value in (('basis_hash', 'e' * 64), ('plan_hash', 'f' * 64), ('case', 1),
                           ('shape', [0.4, 1.5, 1.]), ('seed', -1),
                           ('placement', dict(prefix=9, choices=[0], cursor=[0, 0]))):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.S.check_answer('search', 0, dict(answer, **{key: value}), expected)

    def test_exact_sign_types_and_invalid_witness_are_rejected(self):
        # Replicata: invalid 560 witness, then a valid tiny target with one sign replaced by bool/float.
        # Expectata: reject all before treating any answer as a certified witness.
        bad = self.answer('calibration', 0, 'witness')
        bad['sequence'] = [1] * 560
        with self.assertRaises(AssertionError):
            self.S.check_answer('calibration', 0, bad)
        with patch.dict(self.S.QUESTIONS, search=(16, 4)):
            for value in (True, 1.0):
                answer = self.answer('search', 0, 'witness')
                answer['sequence'] = [(-1) ** i.bit_count() for i in range(16)]
                answer['sequence'][0] = answer['sequence'][-1] = value
                with self.assertRaises(AssertionError):
                    self.S.check_answer('search', 0, answer)

    def test_empty_counter_sentinel_and_timeout_identity_are_distinct(self):
        # Replicata: empty enumeration with an invalid per-level counter, and an attempt timeout.
        # Expectata: only the empty sentinel case permits unknown nodes; timeout retains prepared identity.
        answer = self.answer('search', 0)
        answer.update(nodes=None, raw_nodes=9, node_levels=[2 ** 64 - 1, 10])
        self.S.check_answer('search', 0, answer, self.fields('search', 0))
        answer['node_levels'] = [9]
        with self.assertRaises(AssertionError):
            self.S.check_answer('search', 0, answer)
        timed = self.answer('search', 0, 'timeout')
        self.S.check_answer('search', 0, timed, self.fields('search', 0))
        for key in ('basis_hash', 'profile_hash', 'plan_hash'):
            broken = dict(timed, **{key: None})
            with self.assertRaises(AssertionError):
                self.S.check_answer('search', 0, broken, self.fields('search', 0))

    def test_replacement_preparation_cannot_change_recorded_identity(self):
        # Replicata: a timed-out control is followed by preparation of a different basis.
        # Expectata: stop before issuing another attempt and record the failed restart.
        with patch.object(self.S, 'Worker') as factory, redirect_stdout(io.StringIO()):
            worker = factory.return_value
            worker.ready.side_effect = [self.identity('calibration'),
                                       dict(self.identity('calibration'), basis_hash='e' * 64)]
            worker.fields.side_effect = self.fields
            worker.execute.return_value = self.answer('calibration', 0, 'timeout')
            with self.assertRaises(AssertionError):
                self.S.run()
            worker.execute.assert_called_once_with('calibration', 0)
            worker.close.assert_called_once()
        self.assertEqual(self.S.read_journal()[-1]['outcome'], 'failed')


class TransportQuals(unittest.TestCase):
    def setUp(self):
        self.S = importlib.import_module('search592')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        for name, value in (('WORK', self.work), ('JOURNAL', self.work / 'journal'),
                            ('CONTROL_TOTAL', 2), ('TOTAL', 2), ('SECONDS', .15),
                            ('PREP_SECONDS', .3)):
            context = patch.object(self.S, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.config = self.work / 'config.json'
        self.child = self.work / 'child.py'
        self.child.write_text('''import json, os, sys, time
from pathlib import Path
c = json.loads(Path(sys.argv[1]).read_text())
mode = c['mode']
if mode == 'prep_timeout':
    sys.stdout.write('{"event":')
    sys.stdout.flush()
    time.sleep(60)
if mode == 'prep_stderr':
    print('qual', file=sys.stderr, flush=True)
    time.sleep(60)
if mode == 'prep_crash':
    os._exit(7)
print(json.dumps(c['ready']), flush=True)
for line in sys.stdin:
    i = json.loads(line)['attempt']
    if mode == 'partial':
        sys.stdout.write('{"code":')
        sys.stdout.flush()
        time.sleep(60)
    if mode == 'crash':
        os._exit(9)
    print(json.dumps(c['answers'][i]), flush=True)
''')
        self.worker = self.S.Worker((sys.executable, '-B', str(self.child), str(self.config)))
        self.addCleanup(self.worker.close)

    def protocol(self, mode='empty'):
        S = self.S
        phase = 'calibration'
        settings = S.SETTINGS[phase]
        plan = [dict(case=dict(prefix=i, choices=[0],
                               cursor=[settings['slice_index'] + settings['nslices'] * i, 0]),
                     next_cursor=[settings['slice_index'] + settings['nslices'] * (i + 1), 0])
                for i in range(2)]
        summary = dict(n=560, order=10, **settings,
                       basis_hash='b' * 64, profile_hash=S.INPUT[phase])
        ready = dict(event='ready', phase=phase, code=S.CODE, input=S.INPUT,
                     summary=summary, plan=plan, plan_hash=S.G.digest(plan))
        answers = [dict(code=S.CODE, input=S.INPUT, phase=phase, attempt=i,
                        plan_hash=ready['plan_hash'],
                        answer=dict(outcome='empty', seed=settings['seed'], shape=list(S.G.SHAPE),
                                    basis_hash=summary['basis_hash'], nodes=1, raw_nodes=1,
                                    node_levels=[1], enumeration_seconds=0,
                                    geometry_hash='d' * 64, radius2='16')) for i in range(2)]
        return dict(mode=mode, ready=ready, answers=answers)

    def configure(self, protocol):
        self.config.write_text(json.dumps(protocol))

    def test_worker_reuses_preparation_and_preserves_attempt_fields(self):
        # Replicata: two real pipe requests use the same prepared child.
        # Expectata: one process, stable identity, and distinct journal-ready placements.
        self.configure(self.protocol())
        identity = self.worker.ready('calibration')
        process = self.worker.process
        for i in range(2):
            self.assertEqual(self.worker.ready('calibration'), identity)
            answer = self.worker.execute('calibration', i)
            self.assertEqual(answer['case'], i)
            self.assertEqual(answer['placement']['prefix'], i)
            self.assertEqual(answer['outcome'], 'empty')
            self.assertIs(self.worker.process, process)
        self.worker.close()
        self.assertIsNotNone(process.poll())

    def test_partial_line_timeout_reaps_child_before_replacement(self):
        # Replicata: enumeration sends an unfinished JSON line, then stops responding.
        # Expectata: deadline is effective, timeout retains identity, and a fresh child has a clean buffer.
        self.configure(self.protocol('partial'))
        identity = self.worker.ready('calibration')
        process = self.worker.process
        start = time.monotonic()
        answer = self.worker.execute('calibration', 0)
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(answer['outcome'], 'timeout')
        self.assertTrue(all(answer[k] == v for k, v in identity.items()))
        self.assertIsNotNone(process.poll())
        self.assertIsNone(self.worker.process)
        self.assertEqual(self.worker.buffer, b'')
        self.configure(self.protocol())
        self.assertEqual(self.worker.ready('calibration'), identity)
        self.assertNotEqual(self.worker.process.pid, process.pid)
        self.assertEqual(self.worker.execute('calibration', 1)['outcome'], 'empty')

    def test_preparation_timeout_stderr_and_eof_fail_and_are_reaped_by_run(self):
        # Replicata: preparation hangs on a partial line, reports stderr, or crashes.
        # Expectata: run records failed, closes/reaps its child, and never records an attempt.
        for mode, exception in (('prep_timeout', TimeoutError), ('prep_stderr', AssertionError),
                                ('prep_crash', AssertionError)):
            with self.subTest(mode=mode):
                self.S.JOURNAL.unlink(missing_ok=True)
                self.configure(self.protocol(mode))
                processes = []
                close = self.worker.close
                def tracked_close():
                    processes.append(self.worker.process)
                    close()
                start = time.monotonic()
                with patch.object(self.S, 'Worker', return_value=self.worker), \
                     patch.object(self.worker, 'close', side_effect=tracked_close), \
                     patch.object(self.S.shutil, 'disk_usage', return_value=SimpleNamespace(free=1 << 40)), \
                     redirect_stdout(io.StringIO()), self.assertRaises(exception):
                    self.S.run()
                self.assertLess(time.monotonic() - start, 3)
                self.assertEqual(len(processes), 1)
                self.assertIsNotNone(processes[0].poll())
                self.assertIsNone(self.worker.process)
                rows = self.S.read_journal()
                self.assertEqual(rows[-1]['outcome'], 'failed')
                self.assertFalse(any(r['event'] == 'attempt_start' for r in rows))

    def test_crashed_enumeration_is_failure_and_is_reaped(self):
        # Replicata: a prepared child exits before answering an attempt.
        # Expectata: reject EOF as failure rather than a timeout or empty result, then reap it.
        self.configure(self.protocol('crash'))
        self.worker.ready('calibration')
        process = self.worker.process
        with self.assertRaises(AssertionError):
            self.worker.execute('calibration', 0)
        self.worker.close()
        self.assertEqual(process.poll(), 9)

    def test_preparation_and_result_fingerprints_are_checked(self):
        # Replicata: one source/input/plan fingerprint in a real child's JSON response is changed.
        # Expectata: reject every mismatch; no corrupted answer enters the journal.
        for stage, key, value in (('ready', 'code', 'e' * 64), ('ready', 'input', {}),
                                  ('ready', 'plan_hash', 'e' * 64),
                                  ('answer', 'code', 'e' * 64), ('answer', 'input', {}),
                                  ('answer', 'plan_hash', 'e' * 64), ('answer', 'attempt', 1),
                                  ('answer', 'phase', 'search')):
            with self.subTest(stage=stage, key=key):
                protocol = self.protocol()
                row = protocol['ready'] if stage == 'ready' else protocol['answers'][0]
                row[key] = value
                self.configure(protocol)
                with self.assertRaises(AssertionError):
                    self.worker.ready('calibration')
                    self.worker.execute('calibration', 0)
                process = self.worker.process
                self.worker.close()
                self.assertIsNotNone(process.poll())


if __name__ == '__main__':
    unittest.main()
