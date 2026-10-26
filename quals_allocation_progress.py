"""Quals for the approved eight-worker allocation and recorded focus pauses."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fanout
import progress
from quals_fanout_progress import ev, head, started, survey
from quals_focus_progress import initial


def pause(event, time, **changes):
    return dict(dict(event=event, time=time, pid=123, start='Thu Oct 22 12:00:00 2026',
                     command='/opt/homebrew/bin/python3 -B focus.py 480'), **changes)


def focus(records, pauses, now=200, state='TN', observations=None, launches=None, pid=123):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, 'focus_480_journal.jsonl')
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        procs = [(pid, 1, state, '/opt/homebrew/bin/python3 -B focus.py 480')]
        return progress.survey_focus(path, procs, now, observations, launches, pauses=pauses)


class AllocationProgressQuals(unittest.TestCase):
    def test_default_workers_and_each_session_record_the_approved_count(self):
        # Replicata: two mocked runner invocations, first with five workers and then eight.
        # Expectata: the default is eight; the immutable header keeps five and each session records its own count.
        # Resultata before the fix: the default and header were the only worker-count evidence.
        self.assertEqual(fanout.WORKERS, 8)
        with tempfile.TemporaryDirectory() as directory:
            run, work, journal = [Path(directory, n) for n in ('run', 'work', 'fanout.jsonl')]
            run.mkdir()
            prepared = object()
            # unmoved (the run's replay at each session's start, 2026-10-25 review) stood in for, as taken is
            with patch.object(fanout.focus, 'prepare', return_value=prepared), \
                 patch.object(fanout.focus, 'fingerprint', return_value='qual'), \
                 patch.object(fanout, 'taken', return_value=dict(frontier=[[0, []]], lp=3, case=0)), \
                 patch.object(fanout, 'unmoved'), \
                 patch.object(fanout, 'reflections', return_value={}), \
                 patch.object(fanout, 'farm', return_value=[1]):
                for workers in (5, 8):
                    with patch.object(fanout, 'WORKERS', workers):
                        fanout.run(run, work, journal, 672, 13)
            records = [json.loads(s) for s in journal.read_text().splitlines()]
        self.assertEqual(records[0]['workers'], 5)
        self.assertEqual([r['workers'] for r in records if r['event'] == 'session'], [5, 8])

    def test_five_to_eight_migration_uses_latest_count_and_keeps_rate_history(self):
        # Replicata: a five-worker header, completed work, then an eight-worker session with no completed new job.
        # Expectata: the accumulated two LP/s per worker becomes sixteen LP/s; the public snapshot includes eight.
        # Resultata before the fix: the header's five workers kept the estimate at ten LP/s.
        records = [dict(r, workers=5) if r['event'] == 'header' else r for r in started()]
        records += [ev('session', 150, workers=8)]
        with patch.object(progress, 'lindy_work', return_value=[1, 0.5, 2]) as estimate:
            run = survey(records)
        estimate.assert_called_once_with([], [3610], 1, 16.0)
        self.assertEqual(run['workers'], 8)
        data = json.loads(progress.js_text([run], 200).removeprefix('progressData(').removesuffix(');\n'))
        self.assertEqual(data['runs'][0]['workers'], 8)

    def test_legacy_sessions_use_the_header_count(self):
        # Replicata: a modern count followed by an old-format session without that field.
        # Expectata: the explicit legacy format uses the immutable header, rather than retaining a previous session.
        # Resultata before the fix: no session count was exposed.
        records = started() + [ev('session', 140, workers=8), ev('session', 150)]
        with patch.object(progress, 'lindy_work', return_value=[1, 0.5, 2]) as estimate:
            run = survey(records)
        estimate.assert_called_once_with([], [3610], 1, 4.0)
        self.assertEqual(run['workers'], 2)

    def test_invalid_worker_counts_fail_loudly(self):
        # Replicata: malformed session worker counts.
        # Expectata: counts must be positive integers; they cannot silently change the ETA.
        # Resultata before the fix: these fields were ignored.
        for workers in (0, -1, False, 2.5, '8', None):
            with self.subTest(workers=workers), self.assertRaises(AssertionError):
                survey([head(), ev('session', 100, workers=workers)])

    def test_stopped_focus_excludes_open_pause_and_keeps_history(self):
        # Replicata: 480 runs until 110, is recorded paused, and remains stopped at 200 and 300.
        # Expectata: ten seconds elapsed, paused state, no ETA or running dot, and unchanged historical observations.
        # Resultata before the fix: stopped-process sightings continued increasing elapsed time.
        observations, launches = {'110.0': [1, 0.5, 2]}, {}
        pauses = [pause('pause', 110)]
        for now in (200, 300):
            run = focus(initial(), pauses, now=now, observations=observations, launches=launches)
            self.assertEqual((run['state'], run['so_far'], run['to_go']), ('paused', 10, None))
            self.assertEqual(run['sea']['groups'], ['33'])
            self.assertEqual(list(observations), ['110.0'])
            self.assertEqual(sum(b - a for a, b in run['passes']), 10)
            self.assertAlmostEqual(progress.eta_records(run)[0][1], 10 / progress.HOUR)

    def test_resumption_excludes_past_pause_from_case_age_and_eta_coordinates(self):
        # Replicata: pause 110..150, resumed process observed at 200.
        # Expectata: sixty active seconds and both old/new ETA coordinates on active time.
        # Resultata before the fix: forty seconds of stopped time could enter the case age.
        observations = {'110.0': [1, 0.5, 2]}
        with patch.object(progress, 'lindy_urn', return_value=[1, 0.5, 2]) as estimate:
            run = focus(initial(), [pause('pause', 110), pause('resume', 150)], state='RN',
                        observations=observations)
        estimate.assert_called_once_with([], [60.0], 1, 1)
        self.assertEqual((run['state'], run['so_far']), ('running', 60))
        self.assertEqual([p for p in run['passes'] if p[0] < p[1]], [[100, 110], [150, 200]])
        self.assertEqual([round(r[1] * progress.HOUR) for r in progress.eta_records(run)], [10, 60])

    def test_old_pause_is_preserved_across_focus_restart(self):
        # Replicata: pause 110..150, old session ends at 160, then a fresh process starts at 200.
        # Expectata: twenty prior active seconds plus ten new ones; no restart erases the pause history.
        # Resultata before the fix: the old forty-second pause remained in elapsed time.
        stop = dict(initial()[-1], event='finish', time=160, outcome='budget')
        records = initial() + [stop, dict(event='session', time=200, pid=456),
                               dict(initial()[-1], time=205, pid=456, lp=30)]
        run = focus(records, [pause('pause', 110), pause('resume', 150)], now=210, state='RN', pid=456)
        self.assertEqual(run['so_far'], 30)
        self.assertEqual([p for p in run['passes'] if p[0] < p[1]], [[100, 110], [150, 160], [200, 210]])

    def test_process_state_and_journal_append_races_do_not_assert(self):
        # Replicata: a stale running process snapshot with a new pause record, then T after a resume record.
        # Expectata: actual sampled state controls the label; observations inside the pause have flat elapsed time.
        # Resultata before the fix: stopped time entered progress, and the new argument was unsupported.
        running = focus(initial(), [pause('pause', 110)], state='RN')
        self.assertEqual((running['state'], running['so_far']), ('running', 10))
        self.assertAlmostEqual(progress.eta_records(running)[0][1], 10 / progress.HOUR)
        stopped = focus(initial(), [pause('pause', 110), pause('resume', 150)])
        self.assertEqual((stopped['state'], stopped['to_go']), ('paused', None))
        unlogged = focus(initial(), [])
        self.assertEqual((unlogged['state'], unlogged['to_go']), ('paused', None))

    def test_pause_records_are_strict(self):
        # Replicata: malformed identities, order, timestamps, events or fields in the durable pause journal.
        # Expectata: every malformed journal fails loudly, before changing elapsed-time evidence.
        # Resultata before the fix: no pause journal was consumed.
        invalid = [[pause('resume', 110)], [pause('pause', 110), pause('pause', 120)],
                   [pause('pause', 110), pause('resume', 109)],
                   [pause('pause', 110), pause('resume', 120, pid=456)],
                   [pause('pause', 110), pause('resume', 120, start='different')],
                   [pause('pause', 110), pause('resume', 120, command='python3 focus.py 672')],
                   [pause('pause', 201)], [pause('pause', float('nan'))],
                   [pause('pause', 110, pid=True)], [pause('pause', 110, start='')],
                   [pause('pause', 110, command='python3 other.py')], [pause('pause', 110, extra=1)]]
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(AssertionError):
                focus(initial(), records)

    def test_main_reads_pause_journal_and_ignores_its_partial_last_line(self):
        # Replicata: a complete pause and an incomplete appended resume beside a focus journal.
        # Expectata: the generated snapshot remains paused at ten active seconds.
        # Resultata before the fix: main never loaded the pause journal.
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'focus_480_journal.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in initial()))
            Path(directory, 'focus_480_pauses.jsonl').write_text(json.dumps(pause('pause', 110)) + '\n{"event":')
            dest, cache = Path(directory, 'p.js'), Path(directory, 'c.json')
            with patch.multiple(progress, HERE=directory, RUNS=(), EXTENDED=(), JS=dest, CACHE=cache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=[(123, 1, 'TN', 'python3 -B focus.py 480')]), \
                 patch.object(progress.time, 'time', return_value=200):
                progress.main([])
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
        run = data['runs'][0]
        self.assertEqual((run['state'], run['so_far'], run['to_go']), ('paused', 10, None))


if __name__ == '__main__':
    unittest.main()
