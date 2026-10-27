"""Quals for the progress section's survey of fanout.py's journals (progress.survey_fanout)."""
import json
import math
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


def alone():
    """started() with one root only, case 0's, at depth 0: a session at 100 s; job a done at 120 s after 10 LP solves in
    5 s, leaving 2 boxes open, one of which, job c, started at 120 s."""
    return [head(roots=1, root_cases=[0], root_depths=[0]), ev('session', 100),
            ev('job_start', 110, job='a', case=0, depth=0, root=0),
            ev('job_end', 120, job='a', case=0, root=0, lps=10, seconds=5.0, open=2),
            ev('job_start', 120, job='c', case=0, depth=1, root=0)]


def probe(case, mean, se, **kw):
    """A probe record (see fanout.py's vocabulary) of case at 105 s, its least as defined from mean and se:
    floor(2^(mean - 1.645 se + 1)) - 1."""
    return ev('probe', 105, **dict(dict(case=case, paths=300, mean=mean, se=se,
                                        least=math.floor(2 ** (mean - 1.645 * se + 1)) - 1, witnesses=[]), **kw))


def probed(records, *probes):
    """records with probes inserted after their first session record, before any job, where fanout.py writes them."""
    return records[:2] + list(probes) + records[2:]


def drawing(pool, samples, running=(), n=672, probes=()):
    """A journal of a session that drew at random (seed 1, 2 workers) at 100 s, its pool record at 101 s (pool, [depth,
    count] pairs), then probes (records, given times from 102 s on); then each sample (depth, LP solves, its open boxes'
    depths) a job started and done in turn, 1 s apart, taking lps / 2 seconds, so the pool's rate is 4 LP solves a
    second; then each running depth a job started.  Each job is a root of its own (case 0), so the sea's dots stay
    consistent whatever the samples, and one more root, of case 1, is pending: the run's prefix (3600 LP solves) is
    case 0's work."""
    jobs = [*samples, *((d, None, None) for d in running)]
    records = [head(n=n, roots=len(jobs) + 1, root_cases=[0] * len(jobs) + [1],
                    root_depths=[d for d, _, _ in jobs] + [0]),
               ev('session', 100, seed=1, workers=2), ev('pool', 101, depths=[list(p) for p in pool])]
    records += [dict(p, time=102 + i / 10) for i, p in enumerate(probes)]
    for i, (d, lps, opened) in enumerate(samples):
        records += [ev('job_start', 110 + 2 * i, job=f'j{i}', case=0, depth=d, root=i),
                    ev('job_end', 111 + 2 * i, job=f'j{i}', case=0, root=i, lps=lps, seconds=lps / 2, open=len(opened),
                       open_depths=opened)]
    for i, d in enumerate(running, len(samples)):
        records.append(ev('job_start', 110 + 2 * i, job=f'j{i}', case=0, depth=d, root=i))
    return records


def drawn():
    """drawing: a pool record of 3 boxes at depth 1; job a (depth 1) done after 10 LP solves leaving 2 boxes at depth 5,
    job b (depth 5) done after 5 leaving none; jobs c (depth 5) and d (depth 1) running.  So the pool now holds 2 boxes
    at depth 1 and 1 at depth 5 (c and d among them), and E[T(5)] = 5, E[T(1)] = 10 + 2 x 5 = 20: 45 LP solves, 11.25 s
    at 4 a second."""
    return drawing([(1, 3)], [(1, 10, [5, 5]), (5, 5, [])], running=(5, 1))


def to_go(records, now=300):
    """survey's to_go of records, the driver alive."""
    return survey(records, now=now)['to_go']


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

    def test_eta_is_the_pool_estimate_at_the_pool_s_rate(self):
        # Replicata: drawn() surveyed at 200 s, the driver alive.
        # Expectata (dreeves, 2026-10-26: "sure", to an ETA from the pool's random draws, replacing Gott's rule on the
        # cases' LP solves, which knew nothing of the pool): the pool estimate (see progress.py's vocabulary), from the
        # samples a and b, each the only one of its band, so every bootstrap replicate the same: E[T(5)] = 5 and E[T(1)]
        # = 10 + 2 x 5 = 20 LP solves, the pool 2 boxes at depth 1 and 1 at depth 5, 45 LP solves; at the pool's rate, 4
        # a second, 11.25 s to go at the median, low and high; and the estimate recorded while running.
        # Resultata before: Gott's rule on case 0's 3615 LP solves, above 900 s at the median.
        observations = {}
        run = survey(drawn(), observations=observations)
        for k in ('median', 'lo', 'hi'): self.assertAlmostEqual(run['to_go'][k], 11.25, places=9)
        self.assertEqual(list(observations), ['200.0'])

    def test_a_depth_with_no_sample_takes_the_nearest_band_s_the_deeper_on_a_tie(self):
        # Replicata: drawing with samples at depth 1 (10 LP solves, none open) and depth 9 (7 LP solves, none open), and
        # a pool record of 1 box at depth 1, 1 at 5 and 1 at 9, besides the two sampled: the bands are 4 levels (0-3,
        # 4-7, 8-11), and depth 5's band, 1, has no sample, at distance 1 from bands 0 and 2.
        # Expectata: depth 5 takes the deeper band's samples, depth 9's: E[T(5)] = 7; so 10 + 7 + 7 = 24 LP solves, 6 s.
        records = drawing([(1, 2), (5, 1), (9, 2)], [(1, 10, []), (9, 7, [])])
        for k in ('median', 'lo', 'hi'): self.assertAlmostEqual(to_go(records)[k], 6.0, places=9)

    def test_the_band_comes_from_resampling_each_band_s_samples(self):
        # Replicata: drawing with 20 samples at depth 1, half of 1 LP solve and half of 9, none open, and a pool record
        # of 1,000 boxes at depth 1 besides them.
        # Expectata: the median near the samples' mean, 5 LP solves a box, 5,000 in all, 1,250 s; the band from BOOT
        # bootstrap replicates of the band's mean, so its low end below the median and its high end above, each within
        # 3 standard errors of the mean (a standard error of 0.92 LP solves a box, 229 s for the 1,000 boxes).
        records = drawing([(1, 1020)], [(1, 1, [])] * 10 + [(1, 9, [])] * 10)
        go = to_go(records)
        self.assertAlmostEqual(go['median'] / 1250, 1, delta=0.15)
        self.assertTrue(1250 - 3 * 229 < go['lo'] < go['median'] < go['hi'] < 1250 + 3 * 229, go)

    def test_no_estimate_without_a_pool_record_or_a_sample(self):
        # Replicata: started(), a session that recorded no pool and jobs that recorded no open boxes' depths, as before
        # 2026-10-26; and drawing with a pool record but no job done yet.
        # Expectata: no estimate either way: without the pool's depths or a random draw the pool estimate has nothing
        # to stand on, and Gott's rule on the cases' work, the estimate before, is no longer made.
        self.assertIsNone(survey(started())['to_go'])
        self.assertIsNone(to_go(drawing([(1, 3)], [], running=(1,))))

    def test_malformed_pool_records_and_open_depths_fail_loudly(self):
        # Replicata: drawn() with its pool record's depths not [depth, count] pairs of ints, ascending, counts from 1;
        # a second pool record in the session; a job_end's open_depths of another length than its open count, or with a
        # box no deeper than its job's; open_depths in a session with no seed (no random draws); and a pool count gone
        # below 0 (a box done at a depth the pool never held).
        # Expectata: AssertionError, each: a malformed record cannot move the estimate.
        good = drawn()
        def pooled(depths): return good[:2] + [ev('pool', 101, depths=depths)] + good[3:]
        bad = [pooled([[1, 0]]), pooled([[1, 3.0]]), pooled([[5, 1], [1, 3]]), pooled([[1, 3], [1, 1]]), pooled([1, 3]),
               good[:3] + [ev('pool', 102, depths=[[1, 3]])] + good[3:],
               [dict(r, open_depths=[5]) if r.get('job') == 'j0' and r['event'] == 'job_end' else r for r in good],
               [dict(r, open_depths=[5, 1]) if r.get('job') == 'j0' and r['event'] == 'job_end' else r for r in good],
               [dict(r, seed=None) if r['event'] == 'session' else r for r in good],
               pooled([[5, 1]])]
        self.assertAlmostEqual(to_go(good)['median'], 11.25, places=9)
        for records in bad:
            with self.subTest(records=[r for r in records if r['event'] in ('pool', 'session')]), \
                    self.assertRaises(AssertionError):
                to_go(records)

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
        # Replicata: a restarted driver will reflect case 0's proof into case 1: its session (seed 1) and pool record,
        # which holds case 0's box at depth 2 only (fanout's walk does not walk a reflected case's root), then job c
        # (depth 2) done after 4 LP solves in 2 s leaving a box at depth 3, which job e has started.
        # Expectata: case 1 stays open, and only the pool record's boxes enter the pool estimate (since 2026-10-26; Lindy
        # on the cases' work before): pool_estimate called once, with c's sample, the pool's box at depth 3, n 672, the
        # rate (10 + 4) LP solves in (5 + 2) s times 2 workers, 4 a second, and no probe's floor.
        # Resultata before the fix: case 1 was pending independent work and inflated the estimate.
        from unittest.mock import patch
        records = [dict(r, pid=40) for r in started()] + [
            ev('session', 150, reflections={'1': 0}, seed=1), ev('pool', 150.5, depths=[[2, 1]]),
            ev('job_start', 151, job='c', case=0, depth=2, root=1),
            ev('job_end', 155, job='c', case=0, root=1, lps=4, seconds=2.0, open=1, open_depths=[3]),
            ev('job_start', 155, job='e', case=0, depth=3, root=1)]
        with patch.object(progress, 'pool_estimate', return_value=[1, 0.5, 2]) as estimate:
            run = survey(records)
        estimate.assert_called_once_with([(2, 4, [3])], {3: 1}, 672, 4.0, 0)
        self.assertEqual(run['sea']['groups'], ['1', '2243'])
        self.assertEqual(run['sea']['counts'], dict(settled=0, open=1, split=2, pending=1, running=1))
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
        with patch.object(progress, 'pool_estimate') as estimate:
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

    def test_a_probe_s_least_above_the_pool_estimate_is_its_floor(self):
        # Replicata: drawn(), case 0's work 3615 LP solves (the prefix's 3600 and its jobs' 15), with a probe of case 0
        # whose paths' depths have mean 30 and standard error 0.5, so least = 1,214,318,730 LP solves, far above the pool
        # estimate's 45.
        # Expectata (2026-10-25: random dives put 672:13 at >= 1e13 LP solves when the page said 17 h to go; since
        # 2026-10-26 the floor of the pool estimate, as of Lindy's before): every draw at least the least less the case's
        # work so far, so median, low and high all (least - 3615) / 4 seconds.
        least = probe(0, 30.0, 0.5)['least']
        self.assertEqual(least, 1214318730)
        go = to_go(drawing([(1, 3)], [(1, 10, [5, 5]), (5, 5, [])], running=(5, 1), probes=[probe(0, 30.0, 0.5)]))
        for k in ('median', 'lo', 'hi'): self.assertAlmostEqual(go[k], (least - 3615) / 4, delta=1e-3)

    def test_a_least_below_the_work_done_changes_nothing(self):
        # Replicata: drawn() with a probe of case 0 whose least, 35 LP solves (mean 5, standard error 0.5), is below the
        # case's work so far, 3615.
        # Expectata: the estimate exactly as with no probe: the work done already exceeds the least.
        self.assertEqual(probe(0, 5.0, 0.5)['least'], 35)
        with_probe = drawing([(1, 3)], [(1, 10, [5, 5]), (5, 5, [])], running=(5, 1), probes=[probe(0, 5.0, 0.5)])
        self.assertEqual(to_go(with_probe), to_go(drawn()))

    def test_a_pending_case_is_drawn_above_its_least(self):
        # Replicata: drawn(), case 1 pending (no LP solves of its own done), with a probe of case 1 whose least is
        # 1,214,318,730 LP solves.
        # Expectata: every draw at least case 1's least, so the low end at least least / 4 seconds; without the probe,
        # 11.25 s.
        least = probe(1, 30.0, 0.5)['least']
        go = to_go(drawing([(1, 3)], [(1, 10, [5, 5]), (5, 5, [])], running=(5, 1), probes=[probe(1, 30.0, 0.5)]))
        self.assertGreaterEqual(go['lo'], least / 4)
        self.assertAlmostEqual(to_go(drawn())['median'], 11.25, places=9)

    def test_the_latest_probe_of_a_case_counts(self):
        # Replicata: drawn() with two probes of case 0, of least 1,214,318,730 then of least 35; then the two swapped.
        # Expectata: the latest counts: the first journal's estimate exactly drawn()'s, the second's median over 1e8 s.
        far, near = probe(0, 30.0, 0.5), probe(0, 5.0, 0.5)
        records = lambda probes: drawing([(1, 3)], [(1, 10, [5, 5]), (5, 5, [])], running=(5, 1), probes=probes)
        self.assertEqual(to_go(records([far, near])), to_go(drawn()))
        self.assertGreater(to_go(records([near, far]))['median'], 1e8)

    def test_malformed_probes_fail_loudly(self):
        # Replicata: alone() with a probe record that lacks least, has an extra field, names no root's case or a case
        # that is not an int, has fewer than 2 paths or paths not an int, a negative, NaN or infinite mean or standard
        # error, a least one more than its definition gives or a float, a witness not a 0/1 list of the run's length,
        # or a pid other than its session's driver's.
        # Expectata: AssertionError, each: a malformed probe cannot move the estimate.
        good = probe(0, 30.0, 0.5)
        bad = [{k: v for k, v in good.items() if k != 'least'}, dict(good, extra=1), dict(good, case=5),
               dict(good, case=True), dict(good, case='0'), probe(0, 30.0, 0.5, paths=1),
               probe(0, 30.0, 0.5, paths=300.0), probe(0, -1.0, 0.5), dict(good, mean=float('nan')),
               probe(0, 30.0, float('inf')), probe(0, 30.0, -0.5), dict(good, least=good['least'] + 1),
               dict(good, least=float(good['least'])), dict(good, witnesses=[[0] * 671]),
               dict(good, witnesses=[[2] * 672]), dict(good, witnesses=None), dict(good, witnesses=[[True] * 672]),
               dict(good, pid=PID + 1)]
        records = lambda p: drawing([(1, 3)], [(1, 10, [5, 5]), (5, 5, [])], running=(5, 1), probes=[p])
        self.assertIsNotNone(to_go(records(good)))           # a pool estimate, the probe well formed (since 2026-10-26)
        for record in bad:
            with self.subTest(record=record), self.assertRaises(AssertionError):
                to_go(records(record))

    def test_a_switch_is_a_moment_between_sessions(self):
        # Replicata: alone() (pid 41's session from 100 s to its last record at 120 s), then a switch record at 130 s
        # by pid 43, then a session of pid 42 at 150 s, alive, surveyed at 200 s; and the same journal without the
        # switch record.
        # Expectata (2026-10-26: fanout.py's switch, written between sessions, dreeves: "ok, good, yeah"): the switch a
        # span of no length, so passes [[100, 120], [130, 130], [150, 200]] and 70 s so far; running; and the estimate
        # exactly the journal's without the switch, whose passes are [[100, 120], [150, 200]].
        # Resultata before: AssertionError, a switch being of no known event.
        def run(records):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, 'fanout_672_journal.jsonl')
                Path(path).write_text(''.join(json.dumps(r) + '\n' for r in records))
                return progress.survey_fanout(path, [(42, 1, 'SN', 'python3 -B fanout.py 672')], 200, {}, {})
        second = [dict(ev('session', 150), pid=42)]
        switch = [dict(ev('switch', 130, **{'from': 'a' * 64, 'to': 'b' * 64}), pid=43)]
        got, plain = run(alone() + switch + second), run(alone() + second)
        self.assertEqual((got['passes'], got['so_far'], got['state']), ([[100, 120], [130, 130], [150, 200]], 70, 'running'))
        self.assertEqual((plain['passes'], plain['so_far']), ([[100, 120], [150, 200]], 70))
        self.assertEqual(got['to_go'], plain['to_go'])

    def test_a_probe_s_depths_give_its_mean_and_se(self):
        # Replicata: alone() with a probe of case 0 whose depths are 150 29s and 150 31s, its mean and standard error
        # theirs; then the same probe with 299 depths, a float depth, a negative one, or depths whose standard error is
        # not the record's (150 28s and 150 32s).
        # Expectata (2026-10-26: probes record each dive's depth, for Knuth's estimate): the first read exactly as the
        # same probe without depths; each other AssertionError.
        depths = [29] * 150 + [31] * 150
        mean = sum(depths) / 300
        se = math.sqrt(sum((x - mean) ** 2 for x in depths) / 299 / 300)
        good = probe(0, mean, se, depths=depths)
        self.assertEqual(survey(probed(alone(), good))['to_go'], survey(probed(alone(), probe(0, mean, se)))['to_go'])
        for bad in (dict(good, depths=depths[:-1]), dict(good, depths=[29.0] + depths[1:]),
                    dict(good, depths=[-1] + depths[1:]), dict(good, depths=[28] * 150 + [32] * 150)):
            with self.subTest(depths=bad['depths'][:2]), self.assertRaises(AssertionError):
                survey(probed(alone(), bad))

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
