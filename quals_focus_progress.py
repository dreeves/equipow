"""Quals for live snapshots of the focused all-sign proof searches."""
import copy
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import progress


def initial():
    return [dict(event='header', version=1, n=480, order=14, total=2, code='qual', time=100),
            dict(event='session', time=100, pid=123),
            dict(event='update', time=105, pid=123, lp=20, closed=8,
                 split=12, pending=5, case=0, completed=[])]


def one():
    """initial() with one root case only: root 0 running from 100 s, 20 LP solves on record at 105 s."""
    return [dict(initial()[0], total=1)] + initial()[1:]


def probe(case, mean, se, **kw):
    """A probe record (see fanout.py's vocabulary) of root case case at 106 s, its least as defined from mean and se:
    floor(2^(mean - 1.645 se + 1)) - 1."""
    return dict(dict(event='probe', time=106, pid=123, case=case, paths=300, mean=mean, se=se,
                     least=math.floor(2 ** (mean - 1.645 * se + 1)) - 1, witnesses=[]), **kw)


def survey(records, now=110, alive=True, observations=None, procs=None, launches=None):
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'journal.jsonl')
        with open(path, 'w') as f:
            f.writelines(json.dumps(r) + '\n' for r in records)
        procs = [(123, 1, 'S', '/opt/homebrew/bin/python3 -B focus.py 480')] * alive if procs is None else procs
        return progress.survey_focus(path, procs, now, observations, launches)


class FocusProgressQuals(unittest.TestCase):
    def test_clock_is_sampled_after_reading_concurrent_appends(self):
        # Replicata: a live journal read can include an append made during I/O.
        # Expectata: the snapshot clock is read after the journal, so that a
        # valid new event cannot look like an event from the future.
        calls = []
        def lines(path):
            calls.append('read')
            return [json.dumps(r) for r in initial()]
        def clock():
            calls.append('clock')
            return 110
        with patch.object(progress, 'complete_lines', lines), patch.object(progress.time, 'time', clock):
            progress.survey_focus('qual', [], observations={})
        self.assertEqual(calls, ['read', 'clock'])

    def test_page_section_has_no_scope_prose(self):
        # Replicata: the page's "Search progress" section (dreeves, 2026-10-23: "i don't want a bunch of prose and
        # numbers, i want the blue/red/purple graphs").
        # Expectata: no per-search prose templates or work counters remain, only the shared run template.
        page = Path(__file__).with_name('index.html').read_text()
        section = page.split('<section class="progress"')[1].split('</section>')[0]
        for attribute in ('data-scope', 'data-work', 'data-phase', 'data-outcome'):
            self.assertNotIn(attribute, section)
        self.assertNotIn("[data-work]", page)
        self.assertNotIn("[data-scope]", page)

    def test_running_counts_do_not_pretend_a_profile_is_closed(self):
        # Replicata: twenty LP solves and eight certified leaves, first root case active.
        # Expectata: two root cases still unresolved; actual node work is shown separately.
        run = survey(initial())
        self.assertEqual(run['sea']['groups'], ['43'])
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertNotIn('display', run)

    def test_zero_progress_is_lindy(self):
        # Replicata: one root case, running 10 s, then the same journal surveyed 10 s later (dreeves, 2026-10-23:
        # "if a search starts and has made 0 progress, that should mean go with lindy, even though that means the
        # ETA will steadily grow until progress is nonzero").
        # Expectata: Gott's rule: the median to go is about the age, 10 s, and doubles exactly when the age doubles.
        records = [dict(initial()[0], total=1)] + initial()[1:]
        at10, at20 = survey(records, now=110), survey(records, now=120)
        self.assertAlmostEqual(at10['to_go']['median'], 10, delta=1.5)
        self.assertAlmostEqual(at20['to_go']['median'], 2 * at10['to_go']['median'], places=6)
        self.assertLess(at10['to_go']['lo'], at10['to_go']['median'])
        self.assertLess(at10['to_go']['median'], at10['to_go']['hi'])

    def test_pending_roots_add_to_the_running_one(self):
        # Replicata: the initial journal: root 0 running 10 s, root 1 pending.
        # Expectata: more to go than for root 0 alone, as each pending root is drawn from the urn, Lindy tail above
        # the longest time seen.
        alone = survey([dict(initial()[0], total=1)] + initial()[1:])
        both = survey(initial())
        self.assertGreater(both['to_go']['median'], alone['to_go']['median'])

    def test_etas_are_recorded_only_while_running(self):
        # Replicata: a running snapshot with an observations dict, then the process gone.
        # Expectata: the running snapshot records its ETA (hours: median, lo, hi); the ended one has no estimate
        # and records nothing, keeping the history.
        observations = {}
        live = survey(initial(), observations=observations)
        self.assertEqual(list(observations), ['110.0'])
        for h, k in zip(observations['110.0'], ('median', 'lo', 'hi')):
            self.assertAlmostEqual(h, live['to_go'][k] / progress.HOUR, places=9)
        gone = survey(initial(), now=130, alive=False, observations=observations)
        self.assertIsNone(gone['to_go'])
        self.assertEqual(list(observations), ['110.0'])

    def test_budget_stop_and_resumption_preserve_completed_work(self):
        # Replicata: the first root closed, budget exhausted, then a resumed session.
        # Expectata: only that root is settled, the other is open; no exclusion.
        stop = dict(initial()[-1], event='finish', time=120, lp=100, closed=51,
                    split=49, pending=1, case=None, completed=[0], outcome='budget')
        records = initial() + [stop]
        run = survey(records, now=130)
        self.assertEqual((run['state'], run['outcome']), ('ended', 'budget'))
        self.assertEqual(run['sea']['groups'], ['01'])
        records += [dict(event='session', time=200, pid=123),
                    dict(stop, event='update', time=201, case=1, outcome=None)]
        resumed = survey(records, now=205)
        self.assertEqual(resumed['sea']['groups'], ['04'])
        self.assertEqual(resumed['so_far'], 25)

    def test_complete_exclusion_requires_every_root_closed(self):
        # Replicata: a claimed exclusion, first missing a root and then complete.
        # Expectata: the incomplete claim crashes; the complete claim settles both roots.
        final = dict(initial()[-1], event='finish', time=120, case=None,
                     pending=0, completed=[0], outcome='excluded')
        with self.assertRaises(AssertionError):
            survey(initial() + [final], now=125)
        final['completed'] = [0, 1]
        run = survey(initial() + [final], now=125)
        self.assertEqual(run['sea']['groups'], ['00'])

    def test_disappeared_process_has_no_running_case_or_time_reversal(self):
        # Replicata: a live observation at 110, then the process disappears.
        # Expectata: elapsed time is preserved, with an unresolved case and no running dot.
        observations = {}
        live = survey(initial(), observations=observations)
        gone = survey(initial(), now=130, alive=False, observations=observations)
        self.assertEqual(live['so_far'], gone['so_far'])
        self.assertEqual(gone['sea']['counts']['running'], 0)

    def test_reloading_process_runs_from_its_launch(self):
        # Replicata: a pass stopped at its budget at 120 s; a new focus.py 480 (pid 456) first seen at 200 s, still
        # replaying its certificates (no session record yet), surveyed at 200 and 260 s (dreeves, 2026-10-23: "the
        # search progress section should always be clear about what's been running for how long").
        # Expectata: running, its time from its first sighting on: 20 s + 0 s, then 20 s + 60 s; with an ETA, root 0
        # being 80 s old.
        stop = dict(initial()[-1], event='finish', time=120, outcome='budget')
        procs, launches = [(456, 1, 'SN', '/opt/homebrew/bin/python3 -B focus.py 480 --seconds 43200')], {}
        first = survey(initial() + [stop], now=200, procs=procs, launches=launches)
        later = survey(initial() + [stop], now=260, procs=procs, launches=launches)
        self.assertEqual((first['state'], first['so_far']), ('running', 20))
        self.assertEqual((later['state'], later['so_far']), ('running', 80))
        alone = survey([dict(initial()[0], total=1)] + initial()[1:] + [stop], now=260, procs=procs, launches=dict(launches))
        self.assertAlmostEqual(alone['to_go']['median'], 80, delta=12)

    def test_session_after_a_reload_keeps_its_launch(self):
        # Replicata: as above, then pid 456's session record at 300 s and an update at 305 s, surveyed at 310 s, and
        # after the process is gone, at 400 s.
        # Expectata: one span from the launch, 200 s, on: 20 s + 110 s, and still 130 s once it ended, as it was last
        # seen at 310 s.
        stop = dict(initial()[-1], event='finish', time=120, outcome='budget')
        procs, launches = [(456, 1, 'SN', '/opt/homebrew/bin/python3 -B focus.py 480')], {}
        survey(initial() + [stop], now=200, procs=procs, launches=launches)
        records = initial() + [stop, dict(event='session', time=300, pid=456),
                               dict(initial()[-1], time=305, pid=456, lp=30)]
        live = survey(records, now=310, procs=procs, launches=launches)
        self.assertEqual((live['state'], live['so_far']), ('running', 130))
        gone = survey(records, now=400, procs=[], launches=launches, observations={})
        self.assertEqual((gone['state'], gone['so_far']), ('ended', 130))

    def test_a_process_gone_before_its_session_keeps_its_time(self):
        # Replicata: the budget-stopped pass; pid 456 seen replaying at 200 and 260 s, gone by 300 s without a session
        # record; pid 789 seen at 400 s, its session record at 500 s and an update at 505 s, surveyed at 510 s.
        # Expectata: 456's 60 s stay, a span of their own: 20 + 60 s, ended, at 300 s; then 20 + 60 + 110 s, running,
        # in three spans, root 0 190 s old.
        stop = dict(initial()[-1], event='finish', time=120, outcome='budget')
        launches = {}
        p456 = [(456, 1, 'RN', '/opt/homebrew/bin/python3 -B focus.py 480')]
        survey(initial() + [stop], now=200, procs=p456, launches=launches)
        survey(initial() + [stop], now=260, procs=p456, launches=launches)
        gone = survey(initial() + [stop], now=300, procs=[], launches=launches)
        self.assertEqual((gone['state'], gone['so_far']), ('ended', 80))
        p789 = [(789, 1, 'RN', '/opt/homebrew/bin/python3 -B focus.py 480')]
        survey(initial() + [stop], now=400, procs=p789, launches=launches)
        records = initial() + [stop, dict(event='session', time=500, pid=789),
                               dict(initial()[-1], time=505, pid=789, lp=30)]
        alone = survey([dict(initial()[0], total=1)] + records[1:], now=510, procs=p789,
                       launches=copy.deepcopy(launches))
        live = survey(records, now=510, procs=p789, launches=launches)
        self.assertEqual((live['state'], live['so_far']), ('running', 190))
        self.assertEqual(live['passes'], [[100, 120], [200, 260], [400, 510]])
        self.assertAlmostEqual(alone['to_go']['median'], 190, delta=25)

    def test_a_probe_far_above_gotts_band_moves_the_median_to_twice_its_least(self):
        # Replicata: one() at 110 s, root 0 10 s old, its run's 20 LP solves in 10 s of running (0.5 s each), then the
        # same with a probe of root 0 whose least is 1,214,318,730 LP solves (mean 30, standard error 0.5), or
        # 607,159,365 s at the run's 0.5 s per LP solve, far above Gott's band (to go 9.4 s at the median, 174 s at the
        # 95% point).
        # Expectata: the running root is drawn above its least, Gott's rule given total >= least: the median to go
        # within 10% of 2 x 607,159,365 s, every draw at least that least less the 10 s done, the 95% point within 10%
        # of 20 x 607,159,365 s.
        # Resultata before probes: an AssertionError, the probe record being of no known event.
        least = 0.5 * probe(0, 30.0, 0.5)['least']
        self.assertEqual(least, 607159365)
        self.assertLess(survey(one())['to_go']['hi'], 200)
        go = survey(one() + [probe(0, 30.0, 0.5)])['to_go']
        self.assertAlmostEqual(go['median'] / (2 * least), 1, delta=0.1)
        self.assertGreaterEqual(go['lo'], least - 10)
        self.assertAlmostEqual(go['hi'] / (20 * least), 1, delta=0.1)

    def test_with_no_probe_the_estimate_is_unchanged(self):
        # Replicata: one() and initial() at 110 s, journals with no probe, as every journal before 2026-10-25.
        # Expectata: to go exactly lindy_urn's on root 0's 10 s on one worker, initial()'s root 1 pending, and exactly
        # what the code before probes gave (recorded 2026-10-25).
        before = {0: dict(median=9.394155108210814, lo=0.5251321194851291, hi=173.906597671673),
                  1: dict(median=35.234254010697285, lo=12.161240756887707, hi=374.9650206487719)}
        for records, pending in ((one(), 0), (initial(), 1)):
            go = survey(records)['to_go']
            self.assertEqual(go, progress.to_go_of(progress.lindy_urn([], [10.0], pending, 1)))
            self.assertEqual(go, before[pending])

    def test_a_least_below_the_age_changes_nothing(self):
        # Replicata: one() at 110 s with a probe of root 0 whose least, 3 LP solves (mean 2, standard error 0.5), is 1.5
        # s at the run's 0.5 s per LP solve, below the root's 10 s of running.
        # Expectata: the estimate exactly as with no probe.
        self.assertEqual(probe(0, 2.0, 0.5)['least'], 3)
        self.assertEqual(survey(one() + [probe(0, 2.0, 0.5)])['to_go'], survey(one())['to_go'])

    def test_malformed_probes_fail_loudly(self):
        # Replicata: one() with a probe record that lacks least, has an extra field, names no root case or a case that
        # is not an int, has fewer than 2 paths or paths not an int, a negative, NaN or infinite mean or standard error,
        # a least one more than its definition gives or a float, a witness not a 0/1 list of the run's length, or a pid
        # other than its session's; then a well-formed probe while no LP solve is on record, so that its least has no
        # seconds per LP solve to convert it.
        # Expectata: AssertionError, each.
        good = probe(0, 30.0, 0.5)
        bad = [{k: v for k, v in good.items() if k != 'least'}, dict(good, extra=1), dict(good, case=1),
               dict(good, case=True), dict(good, case='0'), probe(0, 30.0, 0.5, paths=1),
               probe(0, 30.0, 0.5, paths=300.0), probe(0, -1.0, 0.5), dict(good, mean=float('nan')),
               probe(0, 30.0, float('inf')), probe(0, 30.0, -0.5), dict(good, least=good['least'] + 1),
               dict(good, least=float(good['least'])), dict(good, witnesses=[[0] * 479]),
               dict(good, witnesses=[[2] * 480]), dict(good, witnesses=None), dict(good, witnesses=[[True] * 480]),
               dict(good, pid=124)]
        self.assertIsNotNone(survey(one() + [good])['to_go'])
        for record in bad:
            with self.subTest(record=record), self.assertRaises(AssertionError):
                survey(one() + [record])
        with self.assertRaises(AssertionError):
            survey(one()[:2] + [dict(one()[2], lp=0), good])

    def test_regressing_work_is_rejected(self):
        # Replicata: a later snapshot reports fewer cumulative LP solves.
        # Expectata: malformed history raises, rather than silently resetting work.
        with self.assertRaises(AssertionError):
            survey(initial() + [dict(initial()[-1], time=109, lp=19)])


if __name__ == '__main__':
    unittest.main()
