"""Quals for the joined 720:11 witness search's live progress."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import progress


def initial():
    return [dict(event='header', version=1, n=720, order=11, total=16,
                 seconds=45, control_total=4, code='qual', libraries={}, time=100, pid=123),
            dict(event='session', time=100, pid=123),
            dict(event='phase', time=100, pid=123, phase='preparation')]


def control():
    return initial() + [dict(event='phase', time=110, pid=123, phase='calibration'),
                        dict(event='attempt_start', time=111, pid=123,
                             phase='calibration', attempt=0),
                        dict(event='attempt_end', time=112, pid=123,
                             phase='calibration', attempt=0, outcome='witness', elapsed=1)]


def searching():
    return control() + [dict(event='phase', time=113, pid=123, phase='search'),
                        dict(event='attempt_start', time=114, pid=123, phase='search', attempt=0),
                        dict(event='attempt_end', time=115, pid=123, phase='search', attempt=0,
                             outcome='empty', elapsed=1),
                        dict(event='attempt_start', time=116, pid=123, phase='search', attempt=1)]


def survey(records, now=120, alive=True, observations=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, 'join720_journal.jsonl')
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        procs = [(123, 1, 'SN', '/opt/homebrew/bin/python3 -B join720.py')] * alive
        return progress.survey_join(path, procs, now, observations)


class JoinProgressQuals(unittest.TestCase):
    def test_header_budgets_determine_counts_and_terminal_completeness(self):
        # Replicata: two control attempts, two target attempts, and a 90.5-second
        # cap instead of the original 4/16/45 configuration.
        # Expectata: both terminal checks use the header's counts; the target
        # batch remains unresolved and never acquires a completion estimate.
        records = searching() + [dict(event='attempt_end', time=117, pid=123, phase='search',
                                     attempt=1, outcome='timeout', elapsed=1),
                                 dict(event='finish', time=118, pid=123, outcome='budget')]
        records[0].update(control_total=2, total=2, seconds=90.5)
        run = survey(records)
        self.assertEqual(run['display']['outcome'], 'budget')
        self.assertEqual(run['display']['work']['control_total'], 2)
        self.assertEqual(run['display']['work']['total'], 2)
        self.assertEqual(run['display']['work']['attempted'], 2)
        self.assertEqual(run['sea']['groups'], ['11'])
        self.assertIsNone(run['to_go'])
        records = initial() + [dict(event='phase', time=110, pid=123, phase='calibration')]
        records[0].update(control_total=2, total=2, seconds=90.5)
        for i in range(2):
            records += [dict(event='attempt_start', time=111 + 2*i, pid=123, phase='calibration', attempt=i),
                        dict(event='attempt_end', time=112 + 2*i, pid=123, phase='calibration', attempt=i,
                             outcome='timeout', elapsed=1)]
        run = survey(records + [dict(event='finish', time=115, pid=123, outcome='control_failed')])
        self.assertEqual(run['display']['outcome'], 'control_failed')
        self.assertEqual(run['display']['work']['control_attempted'], 2)
        self.assertEqual(run['sea']['groups'], ['33'])

    def test_invalid_header_counts_and_time_caps_are_rejected(self):
        # Replicata: nonpositive, nonfinite, boolean, or nonnumeric budgets;
        # counts additionally include floating-point values such as 16.0.
        # Expectata: assertion failures, without truncation or type coercion.
        common = (0, -1, True, False, float('inf'), float('-inf'), float('nan'), '45', None)
        for field in ('total', 'control_total'):
            for value in common + (2.5, 4.0, 16.0):
                with self.subTest(field=field, value=value), self.assertRaises(AssertionError):
                    records = initial()
                    records[0][field] = value
                    survey(records)
        for value in common:
            with self.subTest(field='seconds', value=value), self.assertRaises(AssertionError):
                records = initial()
                records[0]['seconds'] = value
                survey(records)

    def test_nondefault_budget_retains_target_and_format_identity(self):
        # Replicata: a valid nondefault budget paired with another format version,
        # length, or order, or an attempt outside its two-target budget.
        # Expectata: retain the exact version-1 720:11 contract and attempt limits.
        for field, value in (('version', 2), ('n', 528), ('order', 10)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                records = initial()
                records[0].update(control_total=2, total=2, seconds=90.5)
                records[0][field] = value
                survey(records)
        records = control() + [dict(event='phase', time=113, pid=123, phase='search'),
                               dict(event='attempt_start', time=114, pid=123, phase='search', attempt=2)]
        records[0].update(control_total=2, total=2, seconds=90.5)
        with self.assertRaises(AssertionError):
            survey(records)

    def test_preparation_is_visible_before_any_attempt(self):
        # Replicata: the atomic initial journal, before basis preparation ends.
        # Expectata: a running preparation phase, elapsed time, zero attempts,
        # sixteen pending target dots, and no completion estimate.
        run = survey(initial())
        self.assertEqual((run['state'], run['display']['phase']), ('running', 'preparation'))
        self.assertEqual(run['display']['work']['elapsed'], 20)
        self.assertEqual(run['display']['work']['attempted'], 0)
        self.assertEqual(run['sea']['groups'], ['3' * 16])
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['etas'], {})

    def test_control_and_target_attempts_are_separate(self):
        # Replicata: a recovered control, one empty target attempt and one active.
        # Expectata: the control does not count as a target witness or exclusion.
        run = survey(searching())
        self.assertEqual(run['display']['work'], dict(control_attempted=1, control_total=4,
                         control_witnesses=1, attempted=1, total=16, empty=1, timeout=0, elapsed=20))
        self.assertEqual(run['sea']['groups'], ['14' + '3' * 14])
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['display']['outcome'])

    def test_target_cannot_start_without_a_control_witness(self):
        # Replicata: preparation followed directly by a target phase.
        # Expectata: malformed history raises instead of implying calibration passed.
        records = initial() + [dict(event='phase', time=110, pid=123, phase='search')]
        with self.assertRaises(AssertionError):
            survey(records)

    def test_failed_or_budget_runs_remain_unresolved(self):
        # Replicata: a target timeout followed by each unfinished terminal outcome.
        # Expectata: completed attempts stay open, with no settled cases or ETA.
        records = searching() + [dict(event='attempt_end', time=117, pid=123, phase='search',
                                     attempt=1, outcome='timeout', elapsed=1)]
        rest = []
        for i in range(2, 16):
            rest += [dict(event='attempt_start', time=114 + 2*i, pid=123, phase='search', attempt=i),
                     dict(event='attempt_end', time=115 + 2*i, pid=123, phase='search', attempt=i,
                          outcome='timeout', elapsed=1)]
        for outcome, extra, codes in (('failed', [], '11' + '3' * 14), ('budget', rest, '1' * 16)):
            run = survey(records + extra + [dict(event='finish', time=146, pid=123, outcome=outcome)], now=150)
            self.assertEqual((run['state'], run['display']['outcome']), ('ended', outcome))
            self.assertEqual(run['sea']['groups'], [codes])
            self.assertEqual(run['sea']['counts']['settled'], 0)
            self.assertIsNone(run['to_go'])
        records = initial() + [dict(event='phase', time=110, pid=123, phase='calibration')]
        for i in range(4):
            records += [dict(event='attempt_start', time=111 + 2*i, pid=123, phase='calibration', attempt=i),
                        dict(event='attempt_end', time=112 + 2*i, pid=123, phase='calibration', attempt=i,
                             outcome='timeout', elapsed=1)]
        failed = survey(records + [dict(event='finish', time=119, pid=123, outcome='control_failed')])
        self.assertEqual(failed['display']['work']['attempted'], 0)
        self.assertEqual(failed['sea']['counts']['settled'], 0)

    def test_witness_finish_requires_a_target_witness(self):
        # Replicata: a finish claiming a target witness, backed first only by a control.
        # Expectata: reject the unsupported claim; accept a recorded target witness.
        finish = dict(event='finish', time=118, pid=123, outcome='witness')
        with self.assertRaises(AssertionError):
            survey(control() + [finish])
        records = searching() + [dict(event='attempt_end', time=117, pid=123, phase='search',
                                     attempt=1, outcome='witness', elapsed=1), finish]
        run = survey(records)
        self.assertEqual(run['display']['outcome'], 'witness')
        self.assertEqual(run['sea']['counts']['settled'], 0)

    def test_budget_and_control_failure_require_the_complete_attempt_batch(self):
        # Replicata: terminal budget or calibration-failure events before their
        # attempt batches have completed, including a budget without calibration.
        # Expectata: reject these unsupported terminal claims, matching the runner.
        for records, outcome in ((initial(), 'budget'), (searching(), 'budget'),
                                 (initial(), 'control_failed')):
            with self.assertRaises(AssertionError):
                survey(records + [dict(event='finish', time=118, pid=123, outcome=outcome)])

    def test_resume_keeps_counts_and_excludes_time_between_sessions(self):
        # Replicata: a crash during target attempt 1, then resume at time 200.
        # Expectata: completed attempt 0 persists; attempt 1 can be retried;
        # observed elapsed time cannot fall backwards or include the pause.
        observations = {}
        first = survey(searching(), observations=observations)
        gone = survey(searching(), now=130, alive=False, observations=observations)
        self.assertEqual(first['so_far'], gone['so_far'])
        records = searching() + [dict(event='session', time=200, pid=123),
                    dict(event='phase', time=201, pid=123, phase='search'),
                    dict(event='attempt_start', time=202, pid=123, phase='search', attempt=1)]
        resumed = survey(records, now=205, observations=observations)
        self.assertEqual(resumed['so_far'], 25)
        self.assertEqual(resumed['display']['work']['attempted'], 1)
        self.assertEqual(resumed['sea']['groups'], ['14' + '3' * 14])

    def test_duplicate_completions_and_wrong_phase_are_rejected(self):
        # Replicata: a duplicate completed attempt, or an end from another phase.
        # Expectata: fail loudly instead of double-counting or mixing controls.
        with self.assertRaises(AssertionError):
            survey(searching()[:-1] + [dict(event='attempt_start', time=116, pid=123,
                                           phase='search', attempt=0)])
        wrong = dict(event='attempt_end', time=117, pid=123, phase='calibration',
                     attempt=1, outcome='empty', elapsed=1)
        with self.assertRaises(AssertionError):
            survey(searching() + [wrong])

    def test_clock_follows_the_complete_journal_read(self):
        # Replicata: a journal can acquire a new complete event during its read.
        # Expectata: sample the snapshot clock afterwards, avoiding future events.
        calls = []
        def lines(path):
            calls.append('read')
            return [json.dumps(r) for r in initial()]
        def clock():
            calls.append('clock')
            return 120
        with patch.object(progress, 'complete_lines', lines), patch.object(progress.time, 'time', clock):
            progress.survey_join('qual', [], observations={})
        self.assertEqual(calls, ['read', 'clock'])

    def test_main_does_not_display_the_finished_joined_search(self):
        # Replicata: a one-shot snapshot with only a joined-search journal in its directory (dreeves, 2026-10-23:
        # clean up the search progress section; the 720 batch ended 2026-10-21).
        # Expectata: the data file has no run: the joined search's adapter stays, but main no longer reads it.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'join720_journal.jsonl')
            path.write_text(''.join(json.dumps(r) + '\n' for r in initial()))
            dest, cache = Path(directory, 'p.js'), Path(directory, 'c.json')
            with patch.multiple(progress, HERE=directory, RUNS=(), EXTENDED=(), JS=dest, CACHE=cache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=[]), \
                 patch.object(progress.time, 'time', return_value=120):
                progress.main([])
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
            self.assertEqual(data['runs'], [])


if __name__ == '__main__':
    unittest.main()
