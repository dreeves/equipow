"""Quals for the calibrated 592:10 pilot and its chained progress watcher."""
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import progress
import sweep288_progress
import quals_search288_progress as prior
import quals_sweep288_progress as sweep


def initial():
    records = prior.initial()
    records[0].update(n=592, control_n=560, total=32, control_total=32)
    return [dict(r, pid=456) for r in records]


def control():
    records = [dict(r, pid=456) for r in prior.control()]
    records[0] = initial()[0]
    return records


def searching():
    records = [dict(r, pid=456) for r in prior.searching()]
    records[0] = initial()[0]
    return records


def write(path, records):
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))


class Search592ProgressQuals(unittest.TestCase):
    def setUp(self):
        self.pilot = importlib.import_module('search592_progress')

    def survey(self, records, now=120, command='search592.py', observations=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'search592_journal.jsonl')
            write(path, records)
            procs = [(456, 1, 'SN', '/opt/homebrew/bin/python3 -B ' + command)]
            return self.pilot.survey(path, procs, now, observations)

    def test_preparation_and_attempts_distinguish_control_and_target(self):
        # Replicata: preparation, then a recovered 560 control and empty/active 592 attempts.
        # Expectata: separate correctly labeled blocks, elapsed time, no settled dots or ETA.
        run = self.survey(initial())
        self.assertEqual((run['program'], run['n'], run['order']), ('search592.py', 592, 10))
        self.assertEqual(run['sea']['keys'], ['560:10', '592:10'])
        self.assertEqual(run['sea']['groups'], ['3' * 32, '3' * 32])
        self.assertEqual(run['so_far'], 20)
        run = self.survey(searching())
        self.assertEqual(run['sea']['groups'], ['1' + '3' * 31, '14' + '3' * 30])
        self.assertEqual(run['display']['work']['control_witnesses'], 1)
        self.assertEqual(run['display']['work']['attempted'], 1)
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['etas'], {})

    def test_header_counts_are_flexible_but_identity_is_exact(self):
        # Replicata: another valid budget, then wrong target/control identities and invalid counts.
        # Expectata: use header budgets without accepting another search or coercing invalid values.
        records = initial()
        records[0].update(control_total=2, total=5, seconds=45.5)
        self.assertEqual(self.survey(records)['sea']['groups'], ['33', '33333'])
        for field, value in (('n', 288), ('order', 11), ('control_n', 240), ('control_order', 9),
                             ('total', 0), ('control_total', 2.0), ('seconds', float('inf'))):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                records = initial()
                records[0][field] = value
                self.survey(records)

    def test_control_failure_and_target_gating(self):
        # Replicata: two control attempts end empty and timed out, without a recovered witness.
        # Expectata: control_failed is valid only after both; no target work is allowed.
        records = control()
        records[0]['control_total'] = 2
        records[-1]['outcome'] = 'empty'
        with self.assertRaises(AssertionError):
            self.survey(records + [dict(event='phase', time=113, pid=456, phase='search')])
        with self.assertRaises(AssertionError):
            self.survey(records + [dict(event='finish', time=113, pid=456, outcome='control_failed')])
        records += [dict(event='attempt_start', time=113, pid=456, phase='calibration', attempt=1),
                    dict(event='attempt_end', time=114, pid=456, phase='calibration', attempt=1,
                         outcome='timeout', elapsed=1),
                    dict(event='finish', time=115, pid=456, outcome='control_failed')]
        run = self.survey(records)
        self.assertEqual((run['state'], run['display']['outcome']), ('ended', 'control_failed'))
        self.assertEqual(run['sea']['groups'], ['11', '3' * 32])
        self.assertEqual(run['display']['work']['control_empty'], 1)
        self.assertEqual(run['display']['work']['control_timeout'], 1)

    def test_budget_failure_and_early_witness_remain_distinct(self):
        # Replicata: a full two-attempt empty/time-limited batch, a crash, and an early witness.
        # Expectata: only recorded target evidence supports witness; all other outcomes remain unresolved.
        records = searching()
        records[0]['total'] = 2
        records += [dict(event='attempt_end', time=117, pid=456, phase='search', attempt=1,
                         outcome='timeout', elapsed=1)]
        budget = self.survey(records + [dict(event='finish', time=118, pid=456, outcome='budget')])
        self.assertEqual(budget['display']['outcome'], 'budget')
        self.assertEqual(budget['sea']['groups'][1], '11')
        self.assertEqual(budget['sea']['counts']['settled'], 0)
        self.assertIsNone(budget['to_go'])
        with self.assertRaises(AssertionError):
            self.survey(records + [dict(event='finish', time=118, pid=456, outcome='witness')])
        failed = self.survey(searching() + [dict(event='finish', time=118, pid=456, outcome='failed')])
        self.assertEqual(failed['display']['outcome'], 'failed')
        self.assertEqual(failed['sea']['groups'][1], '1' + '3' * 31)
        records[0]['total'] = 32
        records[-1]['outcome'] = 'witness'
        found = self.survey(records + [dict(event='finish', time=118, pid=456, outcome='witness')])
        self.assertEqual(found['display']['outcome'], 'witness')

    def test_process_matching_and_resume_preserve_elapsed_without_pause(self):
        # Replicata: interrupted target, vanished process, then a new session.
        # Expectata: preserve completed work and observed elapsed time while excluding the pause.
        observations = {}
        self.survey(searching(), observations=observations)
        gone = self.survey(searching(), now=130, command='sweep288.py', observations=observations)
        self.assertEqual((gone['state'], gone['so_far']), ('ended', 20))
        records = searching() + [dict(event='session', time=200, pid=456),
                    dict(event='phase', time=201, pid=456, phase='search'),
                    dict(event='attempt_start', time=202, pid=456, phase='search', attempt=1)]
        self.assertEqual(self.survey(records, now=205, observations=observations)['so_far'], 25)

    def test_chained_watcher_preserves_both_older_sources_and_all_surveys(self):
        # Replicata: the old search, wider sweep and 592 pilot, read at successively later times.
        # Expectata: three surveys, one progress.js write, separate caches and unchanged historical source bytes; one
        # process list for the whole snapshot (2026-10-30: the sweep and the pilot are units of progress.main's
        # snapshot, no longer wrappers of progress.js_text that read their own).
        paths = [Path(progress.__file__), Path(sweep288_progress.__file__)]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        serialize = progress.js_text
        with tempfile.TemporaryDirectory() as directory:
            for name, records in (('search288', prior.initial()), ('sweep288', sweep.searching()),
                                  ('search592', searching())):
                write(Path(directory, name + '_journal.jsonl'), records)
            dest, oldcache = Path(directory, 'p.js'), Path(directory, 'old.json')
            sweepcache, newcache = Path(directory, 'sweep.json'), Path(directory, 'pilot', 'cache.json')
            writes = []
            realwrite = progress.write_atomic
            def record(path, value):
                writes.append(str(path))
                return realwrite(path, value)
            procs = [(123, 1, 'S', 'python3 -B sweep288.py'), (456, 1, 'S', 'python3 -B search592.py')]
            with patch.multiple(progress, HERE=directory, RUNS=(), EXTENDED=(), JS=dest, CACHE=oldcache), \
                 patch.object(sweep288_progress, 'CACHE', sweepcache), patch.object(self.pilot, 'CACHE', newcache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=procs) as processes, \
                 patch.object(progress.time, 'time', side_effect=[120, 120, 123, 125]), \
                 patch.object(progress, 'write_atomic', record):
                self.pilot.main([])
                self.assertEqual(processes.call_count, 1)
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
            self.assertEqual(data['made'], 125)
            self.assertEqual([r['program'] for r in data['runs']], ['search288.py', 'sweep288.py', 'search592.py'])
            self.assertEqual([r['so_far'] for r in data['runs'][1:]], [23, 25])
            self.assertEqual(writes.count(str(dest)), 1)
            self.assertEqual(progress.load_cache(newcache), {'search592_qual_100_observations': {'125.0': None}})
            self.assertEqual(progress.load_cache(sweepcache), {'sweep288_qual_100_observations': {'123.0': None}})
            self.assertFalse(any(k.startswith('search592_') for k in progress.load_cache(oldcache)))
        self.assertIs(progress.js_text, serialize)
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in paths], before)

    def test_side_cache_survives_restart_and_input_list_is_not_mutated(self):
        # Replicata: the pilot's unit (see progress.snapshot) run while its process lives, then again, as after a
        # watcher restart, once the process disappeared.
        # Expectata: one run each time, as search592.py 592 10; the second reloads the pilot's observation and retains
        # its elapsed time.
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory, 'search592_journal.jsonl'), searching())
            cache = Path(directory, 'cache.json')
            with patch.object(progress, 'HERE', directory), patch.object(self.pilot, 'CACHE', cache), \
                 patch.object(progress.time, 'time', return_value=120):
                (identity, thunk), = self.pilot.units([(456, 1, 'S', 'python3 -B search592.py')], 120)
                first = thunk()
            with patch.object(progress, 'HERE', directory), patch.object(self.pilot, 'CACHE', cache), \
                 patch.object(progress.time, 'time', return_value=130):
                (_, thunk), = self.pilot.units([], 130)
                second = thunk()
            self.assertEqual(identity, ('search592.py', 592, 10))
            self.assertEqual((len(first), first[0]['state']), (1, 'running'))
            self.assertEqual((second[0]['state'], second[0]['so_far']), ('ended', 20))

    def test_absent_pilot_adds_no_process_lookup_or_side_cache(self):
        # Replicata: the pilot's units before its journal exists.
        # Expectata: none, without a process lookup or cache write.
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory, 'cache.json')
            with patch.object(progress, 'HERE', directory), patch.object(self.pilot, 'CACHE', cache), \
                 patch.object(progress, 'processes', side_effect=AssertionError('unexpected process lookup')):
                self.assertEqual(self.pilot.units([], 120), [])
            self.assertFalse(cache.exists())

    def test_nested_wrappers_restore_original_serializer_after_failure(self):
        # Replicata: the original watcher fails inside both wrappers.
        # Expectata: both finally blocks restore the original serializer, without recursion on the next call.
        serialize = progress.js_text
        with patch.object(progress, 'main', side_effect=AssertionError('qual')):
            with self.assertRaises(AssertionError):
                self.pilot.main([])
        self.assertIs(progress.js_text, serialize)

    def test_page_labels_and_renderer_use_560_and_592_without_eta(self):
        # Replicata: the new templates and actual attempt renderer, without a browser.
        # Expectata: attributed 560/592 labels, counts, elapsed and all terminal states, with no ETA.
        html = Path(progress.HERE, 'index.html').read_text()
        templates = dict(re.findall(r'<template class="(progress-search592|progress-592-hint)">(.*?)</template>', html, re.S))
        self.assertEqual(set(templates), {'progress-search592', 'progress-592-hint'})
        for body in templates.values():
            self.assertIn('Astra: “', body)
            self.assertIn('560:10', body)
            self.assertIn('592:10', body)
        self.assertIn('no completion estimate', templates['progress-search592'])
        result = subprocess.run(['node', 'quals_search592_progress.cjs'], cwd=progress.HERE,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
