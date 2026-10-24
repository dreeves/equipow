"""Quals for the progress section's survey of fanout.py's journals (progress.survey_fanout)."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import progress

PID = 41


def head(**kw):
    return dict(dict(event='header', time=100, pid=PID, version=1, n=672, order=13, workers=2, budget=10, roots=2,
                     root_cases=[1, 0], root_depths=[0, 1], prefix_lp=3600, prefix_case=0, code='qual'), **kw)


def ev(kind, t, **kw):
    return dict(event=kind, time=t, pid=PID, **kw)


def survey(records, now=200, alive=True, observations=None, launches=None):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'fanout_672_journal.jsonl')
        Path(path).write_text(''.join(json.dumps(r) + '\n' for r in records))
        procs = [(PID, 1, 'SN', '/opt/homebrew/bin/python3 -B fanout.py 672')] * alive
        return progress.survey_fanout(path, procs, now, {} if observations is None else observations,
                                      {} if launches is None else launches)


def started():
    """A session at 100 s; root 1 (case 0) started at 110 s and done at 120 s after 10 LP solves in 5 s, leaving 2
    boxes open; root 0 (case 1) and one of root 1's open boxes started at 120 s."""
    return [head(), ev('session', 100),
            ev('job_start', 110, job='a', case=0, depth=1, root=1),
            ev('job_end', 120, job='a', case=0, root=1, lps=10, seconds=5.0, open=2),
            ev('job_start', 120, job='b', case=1, depth=0, root=0),
            ev('job_start', 120, job='c', case=0, depth=2, root=1)]


class FanoutProgressQuals(unittest.TestCase):
    def test_sea_has_a_dot_per_job_grouped_by_root(self):
        # Replicata: started(), the driver alive at 200 s.
        # Expectata: two groups, root 0 (case 1) and root 1 (case 0), keyed case:depth; root 0 one running job; root 1
        # its split first job, one running and one pending box; so 4 dots in all.
        run = survey(started())
        self.assertEqual(run['program'], 'fanout.py')
        self.assertEqual(run['sea']['keys'], ['1:0', '0:1'])
        self.assertEqual(run['sea']['groups'], ['4', '243'])
        self.assertEqual(run['sea']['counts'], dict(settled=0, open=0, split=1, pending=1, running=2))
        self.assertEqual((run['state'], run['so_far']), ('running', 100))

    def test_eta_is_lindy_on_the_cases_work_at_the_pool_s_rate(self):
        # Replicata: started() at 200 s, then again at 300 s.
        # Expectata: the cases' work in LP solves: case 0 the run's 3600 before fanout plus 10, case 1 none yet, so
        # pending; the pool's rate the jobs' 10 solves in 5 s per worker, times 2 workers, 4 a second; no case done, so
        # Lindy: the median more than case 0's 3610 solves over 4 a second, about 0.25 h, and the estimate recorded
        # while running.
        observations = {}
        run = survey(started(), observations=observations)
        self.assertIsNotNone(run['to_go'])
        self.assertGreater(run['to_go']['median'], 3610 / 4)
        self.assertLess(run['to_go']['lo'], run['to_go']['median'])
        self.assertEqual(list(observations), ['200.0'])

    def test_no_eta_before_a_job_ends(self):
        # Replicata: a header and a session only, the driver alive.
        # Expectata: no rate, so no estimate; every root a pending dot.
        run = survey([head(), ev('session', 100)])
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['sea']['groups'], ['3', '3'])

    def test_an_ended_driver_leaves_its_jobs_pending(self):
        # Replicata: started(), the driver gone at 200 s.
        # Expectata: ended, no estimate; the two jobs it was running pending again (fanout reruns them).
        run = survey(started(), alive=False)
        self.assertEqual((run['state'], run['to_go']), ('ended', None))
        self.assertEqual(run['sea']['groups'], ['3', '233'])

    def test_a_finish_is_ended_with_its_outcome(self):
        # Replicata: started() with every job done and a finish, excluded, at 150 s; the driver gone.
        # Expectata: ended with outcome excluded; every dot settled or split.
        records = started() + [ev('job_end', 130, job='b', case=1, root=0, lps=3, seconds=1.0, open=0),
                               ev('job_end', 130, job='c', case=0, root=1, lps=3, seconds=1.0, open=0),
                               ev('job_start', 130, job='d', case=0, depth=2, root=1),
                               ev('job_end', 140, job='d', case=0, root=1, lps=3, seconds=1.0, open=0),
                               ev('finish', 150, outcome='excluded', witness=None)]
        run = survey(records, alive=False)
        self.assertEqual((run['state'], run['outcome']), ('ended', 'excluded'))
        self.assertEqual(run['sea']['groups'], ['0', '200'])

    def test_a_shell_mentioning_the_command_is_not_the_driver(self):
        # Replicata: started(), with the driver alive and a shell whose command line launched it: "/bin/bash -c ... nohup
        # nice -n 15 /opt/homebrew/bin/python3 -B fanout.py 672 >> fanout_672.log".
        # Expectata (2026-10-23: such a shell crashed the watcher, which found two drivers): one driver, running.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'fanout_672_journal.jsonl')
            Path(path).write_text(''.join(json.dumps(r) + '\n' for r in started()))
            procs = [(PID, 1, 'SN', '/opt/homebrew/bin/python3 -B fanout.py 672'),
                     (99, 1, 'S', "/bin/bash -c 'nohup nice -n 15 /opt/homebrew/bin/python3 -B fanout.py 672 >> fanout_672.log &'")]
            run = progress.survey_fanout(path, procs, 200, {}, {})
        self.assertEqual(run['state'], 'running')

    def test_a_job_of_an_earlier_driver_is_pending_not_running(self):
        # Replicata: a session of driver 41 starting job a (root 1), then a session of driver 42, alive, starting job b
        # (root 0); a never ended.
        # Expectata (2026-10-23: a snapshot showed 8 jobs running on 5 workers): b running; a pending, as fanout reruns it.
        records = [head(), ev('session', 100), ev('job_start', 110, job='a', case=0, depth=1, root=1),
                   dict(ev('session', 150), pid=42), dict(ev('job_start', 151, job='b', case=1, depth=0, root=0), pid=42)]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'fanout_672_journal.jsonl')
            Path(path).write_text(''.join(json.dumps(r) + '\n' for r in records))
            run = progress.survey_fanout(path, [(42, 1, 'SN', 'python3 -B fanout.py 672')], 200, {}, {})
        self.assertEqual(run['sea']['groups'], ['4', '3'])

    def test_reflection_leaves_the_target_open_without_independent_eta_work(self):
        # Replicata: a restarted driver will reflect case 0's proof into case 1.
        # Expectata: case 1 stays open, while only case 0's remaining LP work enters Lindy.
        # Resultata before the fix: case 1 was pending independent work and inflated the estimate.
        from unittest.mock import patch
        records = [dict(r, pid=40) for r in started()] + [
            ev('session', 150, reflections={'1': 0}),
            ev('job_start', 151, job='c', case=0, depth=2, root=1)]
        with patch.object(progress, 'lindy_work', return_value=[1, 0.5, 2]) as estimate:
            run = survey(records)
        estimate.assert_called_once_with([], [3610], 0, 4.0)
        self.assertEqual(run['sea']['groups'], ['1', '243'])
        self.assertEqual(run['sea']['counts'], dict(settled=0, open=1, split=1, pending=1, running=1))
        self.assertEqual((run['state'], run['outcome']), ('running', None))

    def test_reflection_waits_for_the_checked_finish_after_source_jobs_end(self):
        # Replicata: case 0's jobs finish, but the reflected proof has not completed its final replay.
        # Expectata: no independent LP work remains; case 1 is open and the run has no exclusion verdict.
        # Resultata before the fix: the target was still estimated as an independent pending case.
        from unittest.mock import patch
        records = started() + [
            ev('job_end', 130, job='c', case=0, root=1, lps=3, seconds=1.0, open=0),
            ev('job_start', 130, job='d', case=0, depth=2, root=1),
            ev('job_end', 140, job='d', case=0, root=1, lps=3, seconds=1.0, open=0),
            ev('session', 150, reflections={'1': 0})]
        with patch.object(progress, 'lindy_work') as estimate:
            run = survey(records)
        estimate.assert_not_called()
        self.assertEqual((run['state'], run['outcome'], run['to_go']), ('running', None, None))
        self.assertEqual(run['sea']['groups'], ['1', '200'])
        records.append(ev('finish', 180, outcome='excluded', witness=None))
        done = survey(records, alive=False)
        self.assertEqual((done['state'], done['outcome'], done['to_go']), ('ended', 'excluded', None))
        self.assertEqual(done['sea']['groups'], ['0', '200'])

    def test_a_legacy_session_has_no_reflection_mapping(self):
        # Replicata: a reflection session followed by a legacy session with no mapping field.
        # Expectata: the latest session supplies the scheduling policy; legacy means independent cases.
        # Resultata: retaining an older mapping would conceal work that the current driver schedules.
        records = [head(), ev('session', 100, reflections={'1': 0}), ev('session', 150)]
        run = survey(records)
        self.assertEqual(run['sea']['groups'], ['3', '3'])

    def test_invalid_reflection_mappings_fail_loudly(self):
        # Replicata: a session names a nonexistent case, itself, a later source, or a noninteger source.
        # Expectata: malformed scheduling evidence cannot alter the progress estimate.
        # Resultata before the fix: all mappings were ignored.
        for mapping in ({'2': 0}, {'1': 2}, {'1': 1}, {'0': 1}, {'1': False}, {'01': 0}):
            with self.subTest(mapping=mapping), self.assertRaises(AssertionError):
                survey([head(), ev('session', 100, reflections=mapping)])

    def test_main_surveys_fanout_journals(self):
        # Replicata: a one-shot snapshot of a directory holding a fanout journal only.
        # Expectata: the data file has its run, as fanout.py with n 672 and order 13.
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'fanout_672_journal.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in started()))
            dest, cache = Path(d, 'p.js'), Path(d, 'c.json')
            with patch.multiple(progress, HERE=d, RUNS=(), EXTENDED=(), JS=dest, CACHE=cache), \
                 patch.object(progress.os, 'nice', return_value=15), \
                 patch.object(progress, 'processes', return_value=[]), \
                 patch.object(progress.time, 'time', return_value=200):
                progress.main([])
            data = json.loads(dest.read_text().removeprefix('progressData(').removesuffix(');\n'))
            self.assertEqual([(r['program'], r['n'], r['order']) for r in data['runs']], [('fanout.py', 672, 13)])


if __name__ == '__main__':
    unittest.main()
