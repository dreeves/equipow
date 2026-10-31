"""Quals for the full wider-pruning sweep and its immutable-progress watcher wrapper."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import progress
import quals_search288_progress as prior


def initial():
    records = prior.initial()
    records[0].update(total=2736, control_total=1, width=0.1)
    return records


def control(outcome='witness'):
    records = prior.control()
    records[0] = initial()[0]
    records[-1]['outcome'] = outcome
    return records


def searching():
    records = prior.searching()
    records[0] = initial()[0]
    return records


def write(path, records):
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))


class Sweep288ProgressQuals(unittest.TestCase):
    def setUp(self):
        self.sweep = importlib.import_module('sweep288_progress')

    def survey(self, records, now=120, command='sweep288.py', observations=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'sweep288_journal.jsonl')
            write(path, records)
            procs = [(123, 1, 'SN', '/opt/homebrew/bin/python3 -B ' + command)]
            return self.sweep.survey(path, procs, now, observations)

    def test_preparation_control_and_target_are_distinct_without_eta(self):
        # Replicata: initial preparation, then a recovered control, empty target and active next target.
        # Expectata: one control dot and 2,736 target dots; elapsed time and no exclusion or ETA.
        run = self.survey(initial())
        self.assertEqual((run['program'], run['display']['scope']), ('sweep288.py', 'wider-witness'))
        self.assertEqual(run['sea']['keys'], ['240:10', '288:10'])
        self.assertEqual(run['sea']['groups'], ['3', '3' * 2736])
        self.assertEqual(run['so_far'], 20)
        run = self.survey(searching())
        self.assertEqual(run['sea']['groups'], ['1', '14' + '3' * 2734])
        self.assertEqual(run['display']['work']['control_witnesses'], 1)
        self.assertEqual(run['display']['work']['attempted'], 1)
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['etas'], {})

    def test_calibration_failure_and_early_target_witness(self):
        # Replicata: failed control, then a separate calibrated run finding an early witness.
        # Expectata: no target starts after failure; a target witness may end the sweep immediately.
        records = control('timeout') + [dict(event='finish', time=113, pid=123, outcome='control_failed')]
        run = self.survey(records)
        self.assertEqual(run['display']['work']['control_timeout'], 1)
        self.assertEqual(run['sea']['groups'], ['1', '3' * 2736])
        with self.assertRaises(AssertionError):
            self.survey(control('empty') + [dict(event='phase', time=113, pid=123, phase='search')])
        records = searching() + [dict(event='attempt_end', time=117, pid=123, phase='search', attempt=1,
                                     outcome='witness', elapsed=1),
                                 dict(event='finish', time=118, pid=123, outcome='witness')]
        self.assertEqual(self.survey(records)['display']['outcome'], 'witness')

    def test_full_empty_batch_is_unresolved(self):
        # Replicata: all 2,736 pruned attempts finish empty.
        # Expectata: budget is valid but the question remains open, without a completion estimate.
        records = control() + [dict(event='phase', time=113, pid=123, phase='search')]
        for i in range(2736):
            records += [dict(event='attempt_start', time=114 + 2*i, pid=123, phase='search', attempt=i),
                        dict(event='attempt_end', time=115 + 2*i, pid=123, phase='search', attempt=i,
                             outcome='empty', elapsed=1)]
        run = self.survey(records + [dict(event='finish', time=5586, pid=123, outcome='budget')], now=5600)
        self.assertEqual(run['sea']['groups'], ['1', '1' * 2736])
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['to_go'])
        with self.assertRaises(AssertionError):
            self.survey(searching() + [dict(event='finish', time=118, pid=123, outcome='budget')])

    def test_failed_terminal_preserves_only_completed_attempts(self):
        # Replicata: a failed finish while target attempt 1 was active.
        # Expectata: attempt 0 stays completed, interrupted work stays pending, and no ETA appears.
        run = self.survey(searching() + [dict(event='finish', time=118, pid=123, outcome='failed')])
        self.assertEqual((run['state'], run['display']['outcome']), ('ended', 'failed'))
        self.assertEqual(run['sea']['groups'], ['1', '1' + '3' * 2735])
        self.assertEqual(run['display']['work']['attempted'], 1)
        self.assertIsNone(run['to_go'])

    def test_header_identifies_exact_sweep(self):
        # Replicata: another width, target/control identity or attempt count.
        # Expectata: refuse to label another design as this sweep.
        for field, value in (('width', 0), ('total', 14), ('control_total', 2),
                             ('control_n', 144), ('control_order', 8), ('n', 720)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                records = initial()
                records[0][field] = value
                self.survey(records)

    def test_resume_keeps_completed_work_and_excludes_gap(self):
        # Replicata: interrupted target, then another process occupies the PID, followed by resumption.
        # Expectata: preserve completed work without counting the stopped interval.
        observations = {}
        self.survey(searching(), observations=observations)
        stopped = self.survey(searching(), now=130, command='search288.py', observations=observations)
        self.assertEqual((stopped['state'], stopped['so_far']), ('ended', 20))
        records = searching() + [dict(event='session', time=200, pid=123),
                    dict(event='phase', time=201, pid=123, phase='search'),
                    dict(event='attempt_start', time=202, pid=123, phase='search', attempt=1)]
        self.assertEqual(self.survey(records, now=205, observations=observations)['so_far'], 25)

    def test_wrapper_preserves_old_surveys_and_writes_one_combined_snapshot(self):
        # Replicata: both prior and sweep journals, with the sweep read later than main's initial clock.
        # Expectata: one combined snapshot, separate persisted caches, later timestamp, unchanged progress.py; one
        # process list for the whole snapshot (2026-10-30: the sweep is a unit of progress.main's snapshot, no longer a
        # wrapper of progress.js_text that read its own).
        before = hashlib.sha256(Path(progress.__file__).read_bytes()).hexdigest()
        original = progress.js_text
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory, 'search288_journal.jsonl'), prior.initial())
            write(Path(directory, 'sweep288_journal.jsonl'), searching())
            dest, oldcache = Path(directory, 'p.js'), Path(directory, 'old.json')
            newcache = Path(directory, 'sweep', 'observations.json')
            writes = []
            realwrite = progress.write_atomic
            def record(path, value):
                writes.append(str(path))
                return realwrite(path, value)
            with patch.multiple(progress, HERE=directory, RUNS=(), EXTENDED=(), JS=dest, CACHE=oldcache), \
                 patch.object(self.sweep, 'CACHE', newcache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=[(123, 1, 'S', 'python3 -B sweep288.py')]) as processes, \
                 patch.object(progress.time, 'time', side_effect=[120, 120, 125]), \
                 patch.object(progress, 'write_atomic', record):
                self.sweep.main([])
                self.assertEqual(processes.call_count, 1)  # the snapshot's, which the sweep's unit shares
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
            self.assertEqual(data['made'], 125)
            self.assertEqual([r['program'] for r in data['runs']], ['search288.py', 'sweep288.py'])
            self.assertEqual(data['runs'][0]['groups'], ['33', '333'])
            self.assertEqual(data['runs'][1]['so_far'], 25)
            self.assertEqual(writes.count(str(dest)), 1)
            cache = progress.load_cache(newcache)
            self.assertEqual(cache['sweep288_qual_100_observations'], {'125.0': None})
            self.assertFalse(any(k.startswith('sweep288_') for k in progress.load_cache(oldcache)))
        self.assertIs(progress.js_text, original)
        self.assertEqual(hashlib.sha256(Path(progress.__file__).read_bytes()).hexdigest(), before)

    def test_persisted_sweep_cache_survives_watcher_restart_without_mutating_old_list(self):
        # Replicata: the sweep's unit (see progress.snapshot) run while its process lives, then again, as after a
        # watcher restart, once its process disappeared.
        # Expectata: one run each time, as sweep288.py 288 10; the second reloads the saved observation and keeps its
        # elapsed time.
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory, 'sweep288_journal.jsonl'), searching())
            cache = Path(directory, 'cache.json')
            with patch.object(progress, 'HERE', directory), patch.object(self.sweep, 'CACHE', cache), \
                 patch.object(progress.time, 'time', return_value=120):
                (identity, thunk), = self.sweep.units([(123, 1, 'S', 'python3 -B sweep288.py')], 120)
                first = thunk()
            with patch.object(progress, 'HERE', directory), patch.object(self.sweep, 'CACHE', cache), \
                 patch.object(progress.time, 'time', return_value=130):
                (_, thunk), = self.sweep.units([], 130)
                second = thunk()
            self.assertEqual(identity, ('sweep288.py', 288, 10))
            self.assertEqual((len(first), first[0]['state']), (1, 'running'))
            self.assertEqual((second[0]['state'], second[0]['so_far']), ('ended', 20))

    def test_absent_sweep_does_not_read_processes_or_create_side_cache(self):
        # Replicata: the sweep's units with no sweep journal.
        # Expectata: none, with no process lookup or side-cache write.
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory, 'new', 'cache.json')
            with patch.object(progress, 'HERE', directory), patch.object(self.sweep, 'CACHE', cache), \
                 patch.object(progress, 'processes', side_effect=AssertionError('unexpected process read')):
                self.assertEqual(self.sweep.units([], 120), [])
            self.assertFalse(cache.exists())

    def test_wrapper_restores_serializer_after_failure(self):
        # Replicata: a malformed journal makes the underlying main fail.
        # Expectata: the imported serializer is restored, avoiding recursion in subsequent calls.
        original = progress.js_text
        with patch.object(progress, 'main', side_effect=AssertionError('qual')):
            with self.assertRaises(AssertionError):
                self.sweep.main([])
        self.assertIs(progress.js_text, original)

    def test_page_reuses_attributed_attempt_display_without_eta(self):
        # Replicata: the sweep UI dispatch and actual common renderer, without a browser.
        # Expectata: counts of 1 and 2,736, terminal states and elapsed time, with no ETA.
        html = Path(progress.HERE, 'index.html').read_text()
        self.assertIn("if (run.program === 'sweep288.py') search288View(box, run);", html)
        result = subprocess.run(['node', 'quals_sweep288_progress.cjs'], cwd=progress.HERE,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
