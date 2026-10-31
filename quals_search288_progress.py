"""Quals for the revised 288:10 search's journal and progress display."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import progress


def initial():
    return [dict(event='header', version=1, n=288, order=10, control_n=240,
                 control_order=10, total=3, control_total=2, seconds=30,
                 code='qual', libraries={}, time=100, pid=123),
            dict(event='session', time=100, pid=123),
            dict(event='phase', time=100, pid=123, phase='preparation')]


def control():
    return initial() + [dict(event='phase', time=110, pid=123, phase='calibration'),
                        dict(event='attempt_start', time=111, pid=123, phase='calibration', attempt=0),
                        dict(event='attempt_end', time=112, pid=123, phase='calibration', attempt=0,
                             outcome='witness', elapsed=1)]


def searching():
    return control() + [dict(event='phase', time=113, pid=123, phase='search'),
                        dict(event='attempt_start', time=114, pid=123, phase='search', attempt=0),
                        dict(event='attempt_end', time=115, pid=123, phase='search', attempt=0,
                             outcome='empty', elapsed=1),
                        dict(event='attempt_start', time=116, pid=123, phase='search', attempt=1)]


def survey(records, now=120, command='search288.py', observations=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, 'search288_journal.jsonl')
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        procs = [(123, 1, 'SN', '/opt/homebrew/bin/python3 -B ' + command)]
        return progress.survey_search288(path, procs, now, observations)


class Search288ProgressQuals(unittest.TestCase):
    def test_preparation_and_calibration_have_separate_dots_and_elapsed_time(self):
        # Replicata: preparation, then one active calibration attempt.
        # Expectata: two labeled blocks, no target progress or completion estimate.
        run = survey(initial())
        self.assertEqual(run['sea']['keys'], ['240:10', '288:10'])
        self.assertEqual(run['sea']['groups'], ['33', '333'])
        self.assertEqual(run['display']['work']['elapsed'], 20)
        self.assertEqual(run['so_far'], 20)
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['etas'], {})
        active = survey(control()[:-1])
        self.assertEqual(active['sea']['groups'], ['43', '333'])
        self.assertEqual(active['display']['work']['attempted'], 0)

    def test_control_and_target_counts_remain_distinct(self):
        # Replicata: one recovered control, one empty target, one active target.
        # Expectata: the control is not a target result, and no attempt is an exclusion.
        run = survey(searching())
        self.assertEqual(run['program'], 'search288.py')
        self.assertEqual((run['n'], run['order']), (288, 10))
        self.assertEqual(run['sea']['groups'], ['13', '143'])
        self.assertEqual(run['sea']['counts'], dict(settled=0, open=2, split=0, pending=2, running=1))
        self.assertEqual(run['display']['work'], dict(control_attempted=1, control_total=2,
                         control_witnesses=1, control_empty=0, control_timeout=0,
                         attempted=1, total=3, empty=1, timeout=0, elapsed=20))

    def test_header_counts_are_flexible_but_identity_is_exact(self):
        # Replicata: changed attempt budgets, followed by wrong target/control identities.
        # Expectata: use header counts without accepting another search or format.
        records = initial()
        records[0].update(total=16, control_total=8, seconds=45.5)
        self.assertEqual(survey(records)['sea']['groups'], ['3' * 8, '3' * 16])
        for field, value in (('version', 2), ('n', 720), ('order', 11),
                             ('control_n', 144), ('control_order', 8), ('total', 3.0)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                records = initial()
                records[0][field] = value
                survey(records)

    def test_failed_control_keeps_target_pending(self):
        # Replicata: both controls finish empty or timed out, without a witness.
        # Expectata: calibration failure leaves every target pending and no ETA.
        records = control()
        records[-1]['outcome'] = 'empty'
        records += [dict(event='attempt_start', time=113, pid=123, phase='calibration', attempt=1),
                    dict(event='attempt_end', time=114, pid=123, phase='calibration', attempt=1,
                         outcome='timeout', elapsed=1),
                    dict(event='finish', time=115, pid=123, outcome='control_failed')]
        run = survey(records)
        self.assertEqual(run['state'], 'ended')
        self.assertEqual(run['sea']['groups'], ['11', '333'])
        self.assertEqual(run['display']['work']['control_empty'], 1)
        self.assertEqual(run['display']['work']['control_timeout'], 1)
        self.assertIsNone(run['to_go'])
        with self.assertRaises(AssertionError):
            survey(records[:-1] + [dict(event='phase', time=115, pid=123, phase='search')])

    def test_budget_is_unresolved_and_witness_requires_target_evidence(self):
        # Replicata: a completed target batch with only empty/time-limited attempts.
        # Expectata: no settled dots or ETA; a claimed witness must have target evidence.
        records = searching()
        records[0]['total'] = 2
        records += [dict(event='attempt_end', time=117, pid=123, phase='search', attempt=1,
                         outcome='timeout', elapsed=1)]
        run = survey(records + [dict(event='finish', time=118, pid=123, outcome='budget')])
        self.assertEqual(run['display']['outcome'], 'budget')
        self.assertEqual(run['sea']['groups'], ['13', '11'])
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['to_go'])
        with self.assertRaises(AssertionError):
            survey(records + [dict(event='finish', time=118, pid=123, outcome='witness')])
        records[-1]['outcome'] = 'witness'
        self.assertEqual(survey(records + [dict(event='finish', time=118, pid=123,
                                              outcome='witness')])['display']['outcome'], 'witness')

    def test_process_matching_and_resume_exclude_the_pause(self):
        # Replicata: the revised search stops; a different runner occupies its PID; it resumes later.
        # Expectata: do not count that runner as live, nor include the gap in elapsed time.
        observations = {}
        survey(searching(), observations=observations)
        stopped = survey(searching(), now=130, command='lattice288.py', observations=observations)
        self.assertEqual((stopped['state'], stopped['so_far']), ('ended', 20))
        records = searching() + [dict(event='session', time=200, pid=123),
                    dict(event='phase', time=201, pid=123, phase='search'),
                    dict(event='attempt_start', time=202, pid=123, phase='search', attempt=1)]
        self.assertEqual(survey(records, now=205, observations=observations)['so_far'], 25)

    def test_main_registers_only_the_revised_journal(self):
        # Replicata: a snapshot directory with a revised journal and an old joined journal.
        # Expectata: the revised search alone appears, with both dot blocks and elapsed time.
        with tempfile.TemporaryDirectory() as directory:
            for name in ('search288_journal.jsonl', 'join720_journal.jsonl'):
                Path(directory, name).write_text(''.join(json.dumps(r) + '\n' for r in initial()))
            dest, cache = Path(directory, 'p.js'), Path(directory, 'c.json')
            with patch.multiple(progress, HERE=directory, RUNS=(), EXTENDED=(), JS=dest, CACHE=cache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=[(123, 1, 'S', 'python3 -B search288.py')]), \
                 patch.object(progress.time, 'time', return_value=120):
                progress.main([])
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
            self.assertEqual(len(data['runs']), 1)
            self.assertEqual(data['runs'][0]['program'], 'search288.py')
            self.assertEqual(data['runs'][0]['groups'], ['33', '333'])
            self.assertEqual(data['runs'][0]['so_far'], 20)
            self.assertEqual(data['runs'][0]['etas'], [])

    def test_page_distinguishes_attempts_and_attributes_new_copy(self):
        # Replicata: the revised-search templates and their actual JS renderer, without a browser.
        # Expectata: separate counts, all terminal states, elapsed time, no ETA, attributed English.
        html = Path(progress.HERE, 'index.html').read_text()
        templates = dict(re.findall(r'<template class="(progress-search288|progress-attempt-hint)">(.*?)</template>',
                                    html, re.S))
        self.assertEqual(set(templates), {'progress-search288', 'progress-attempt-hint'})
        self.assertIn('240:10 calibration', templates['progress-search288'])
        self.assertIn('288:10 search', templates['progress-search288'])
        self.assertIn('no completion estimate', templates['progress-search288'])
        self.assertIn('Astra: “', templates['progress-attempt-hint'])
        self.assertEqual(set(re.findall(r'data-attempt-outcome="([^"]*)"', templates['progress-search288'])),
                         {'null', 'control_failed', 'budget', 'witness', 'failed'})
        self.assertIn('if (run.program === \'search288.py\') search288View(box, run);', html)
        result = subprocess.run(['node', 'quals_search288_progress.cjs'], cwd=progress.HERE,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
