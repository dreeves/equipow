"""Quals for the paired pruning-width study's progress."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import progress
import quals_search288_progress as prior


def initial():
    records = prior.initial()
    records[0].update(total=14, control_total=2, widths=[0, 0.1], cases=list(range(7)),
                      control_case=2, control_seed=20261026)
    return records


def attempt(records, phase, index, outcome, elapsed=1):
    t = records[-1]['time']
    return records + [dict(event='attempt_start', time=t + 1, pid=123, phase=phase, attempt=index),
                      dict(event='attempt_end', time=t + 2, pid=123, phase=phase, attempt=index,
                           outcome=outcome, elapsed=elapsed)]


def controls(outcomes=('witness', 'witness')):
    records = initial() + [dict(event='phase', time=101, pid=123, phase='calibration')]
    for i, outcome in enumerate(outcomes):
        records = attempt(records, 'calibration', i, outcome)
    return records


def searching():
    return controls() + [dict(event='phase', time=106, pid=123, phase='search')]


def survey(records, now=150, command='pruning288.py', observations=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, 'pruning288_journal.jsonl')
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        procs = [(123, 1, 'SN', '/opt/homebrew/bin/python3 -B ' + command)]
        return progress.survey_pruning288(path, procs, now, observations)


class Pruning288ProgressQuals(unittest.TestCase):
    def test_four_blocks_exist_during_preparation(self):
        # Replicata: the complete initial journal, before calibration.
        # Expectata: one dot per control variant and seven per target variant, elapsed but no ETA.
        run = survey(initial())
        self.assertEqual(run['sea']['keys'], ['240:10 baseline', '240:10 wider',
                                             '288:10 baseline', '288:10 wider'])
        self.assertEqual(run['sea']['groups'], ['3', '3', '3333333', '3333333'])
        self.assertEqual((run['so_far'], run['display']['work']['elapsed']), (50, 50))
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['etas'], {})

    def test_both_controls_are_required_before_target_work(self):
        # Replicata: a search phase after only one successful control, or after one success and one failure.
        # Expectata: both malformed transitions fail; both successes permit search.
        for records in (controls(('witness',)), controls(('witness', 'empty')),
                        controls(('timeout', 'witness'))):
            with self.subTest(records=records), self.assertRaises(AssertionError):
                survey(records + [dict(event='phase', time=106, pid=123, phase='search')])
        self.assertEqual(survey(searching())['display']['phase'], 'search')

    def test_one_failed_control_finishes_calibration_without_starting_target(self):
        # Replicata: both controls finish, with one recovered and one empty or timed out.
        # Expectata: control_failed is valid despite one witness, and all target attempts remain pending.
        for outcomes in (('witness', 'empty'), ('timeout', 'witness'), ('empty', 'timeout')):
            records = controls(outcomes) + [dict(event='finish', time=106, pid=123, outcome='control_failed')]
            run = survey(records)
            self.assertEqual(run['sea']['groups'], ['1', '1', '3333333', '3333333'])
            self.assertEqual(run['display']['outcome'], 'control_failed')
            self.assertEqual(run['display']['work']['attempted'], 0)
        for records in (controls(('empty',)), controls()):
            with self.assertRaises(AssertionError):
                survey(records + [dict(event='finish', time=106, pid=123, outcome='control_failed')])

    def test_target_parity_maps_to_paired_blocks_and_counts(self):
        # Replicata: case 0 baseline empty, wider timed out; case 1 baseline currently running.
        # Expectata: paired columns remain independent and completed elapsed time is per variant.
        records = attempt(searching(), 'search', 0, 'empty', 1.25)
        records = attempt(records, 'search', 1, 'timeout', 30)
        records += [dict(event='attempt_start', time=111, pid=123, phase='search', attempt=2)]
        run = survey(records)
        self.assertEqual(run['sea']['groups'], ['1', '1', '1433333', '1333333'])
        self.assertEqual(run['sea']['counts'], dict(settled=0, open=4, split=0, pending=11, running=1))
        work = run['display']['work']
        self.assertEqual((work['baseline_attempted'], work['wider_attempted']), (1, 1))
        self.assertEqual((work['baseline_empty'], work['wider_timeout']), (1, 1))
        self.assertEqual((work['baseline_seconds'], work['wider_seconds']), (1.25, 30))
        self.assertEqual((work['baseline_control_witnesses'], work['wider_control_witnesses']), (1, 1))

    def test_all_empty_budget_is_unresolved_and_early_witness_is_allowed(self):
        # Replicata: a full empty batch, then a different batch ending at its first target witness.
        # Expectata: budget proves no exclusion; a verified witness may end before all pairs run.
        records = searching()
        for i in range(14):
            records = attempt(records, 'search', i, 'empty')
        run = survey(records + [dict(event='finish', time=135, pid=123, outcome='budget')])
        self.assertEqual(run['sea']['groups'], ['1', '1', '1111111', '1111111'])
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['to_go'])
        records = attempt(searching(), 'search', 0, 'witness')
        found = survey(records + [dict(event='finish', time=109, pid=123, outcome='witness')])
        self.assertEqual(found['display']['work']['baseline_witnesses'], 1)
        self.assertEqual(found['sea']['groups'], ['1', '1', '1333333', '3333333'])
        with self.assertRaises(AssertionError):
            survey(searching() + [dict(event='finish', time=109, pid=123, outcome='budget')])

    def test_header_identifies_exact_paired_design(self):
        # Replicata: unsupported widths, cases, counts or control identity.
        # Expectata: fail rather than silently assign another design's dots to these variants.
        for field, value in (('widths', [0, 0.2]), ('cases', [0, 1]), ('total', 16),
                             ('control_total', 1), ('control_n', 144), ('control_order', 8)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                records = initial()
                records[0][field] = value
                survey(records)

    def test_partial_pair_resume_preserves_variant_and_excludes_pause(self):
        # Replicata: baseline done, wider interrupted, then resumed later.
        # Expectata: only the wider variant is retried; the stopped interval adds no elapsed time.
        records = attempt(searching(), 'search', 0, 'empty', 2)
        records += [dict(event='attempt_start', time=109, pid=123, phase='search', attempt=1)]
        observations = {}
        survey(records, now=120, observations=observations)
        stopped = survey(records, now=130, command='search288.py', observations=observations)
        self.assertEqual((stopped['state'], stopped['so_far']), ('ended', 20))
        records += [dict(event='session', time=200, pid=123),
                    dict(event='phase', time=201, pid=123, phase='search'),
                    dict(event='attempt_start', time=202, pid=123, phase='search', attempt=1)]
        resumed = survey(records, now=205, observations=observations)
        self.assertEqual(resumed['sea']['groups'], ['1', '1', '1333333', '4333333'])
        self.assertEqual(resumed['so_far'], 25)
        self.assertEqual(resumed['display']['work']['baseline_seconds'], 2)

    def test_main_preserves_prior_search_and_adds_paired_study(self):
        # Replicata: both journals exist, with independent runner PIDs.
        # Expectata: both surveys serialize; the paired study adds four blocks without changing the prior one.
        with tempfile.TemporaryDirectory() as directory:
            for name, records in (('search288', prior.initial()), ('pruning288', initial())):
                Path(directory, name + '_journal.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
            dest, cache = Path(directory, 'p.js'), Path(directory, 'c.json')
            with patch.multiple(progress, HERE=directory, RUNS=(), EXTENDED=(), JS=dest, CACHE=cache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=[]), \
                 patch.object(progress.time, 'time', return_value=150):
                progress.main([])
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
            runs = {r['program']: r for r in data['runs']}
            self.assertEqual(set(runs), {'search288.py', 'pruning288.py'})
            self.assertEqual(runs['search288.py']['groups'], ['33', '333'])
            self.assertEqual(runs['pruning288.py']['groups'], ['3', '3', '3333333', '3333333'])
            self.assertEqual(runs['pruning288.py']['etas'], [])

    def test_page_reports_paired_results_without_an_eta(self):
        # Replicata: paired-study templates and renderer, with no browser.
        # Expectata: attributed labels, baseline/wider counts and elapsed time, and unresolved empty results.
        html = Path(progress.HERE, 'index.html').read_text()
        body = re.search(r'<template class="progress-pruning288">(.*?)</template>', html, re.S)
        self.assertIsNotNone(body)
        for text in ('Astra: "', 'baseline', 'wider', 'no completion estimate', 'completed attempts'):
            self.assertIn(text, body[1])
        for field in ('baseline_attempted', 'wider_attempted', 'baseline_empty', 'wider_empty',
                      'baseline_timeout', 'wider_timeout', 'baseline_seconds', 'wider_seconds'):
            self.assertIn('data-attempt-count="' + field + '"', body[1])
        result = subprocess.run(['node', 'quals_pruning288_progress.cjs'], cwd=progress.HERE,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
