#!/usr/bin/env python3
"""Quals for lattice288.py's live progress adapter. Run with Homebrew Python; 'browser' launches Chrome."""
import sys
sys.dont_write_bytecode = True
import html, json, os, re, shutil, tempfile, unittest
import progress

HERE = os.path.dirname(os.path.abspath(__file__))
PID = 12345


def event(kind, t, **fields):
    return dict(event=kind, time=t, pid=PID, **fields)


def initial():
    return [event('header', 100, version=1, n=288, order=10, total=2736, seconds=30),
            event('session', 100), event('phase', 101, phase='preparation')]


def survey(records, now=120, stat='S', etas=None):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'journal.jsonl')
        with open(path, 'w') as f:
            f.writelines(json.dumps(r) + '\n' for r in records)
        procs = [(records[-1]['pid'], 1, stat, 'python3 -B lattice288.py')][:int(bool(stat))]
        return progress.survey_lattice(path, procs, now, etas=etas)


def data(records, now=120, stat='S', etas=None):
    return json.loads(progress.js_text([survey(records, now, stat, etas)], now)[len('progressData('):-3])


def completed(durations):
    """A sequential search with given observed attempt durations, after preparation ends at t=105."""
    records = initial() + [event('phase', 105, phase='search')]
    t = 105
    for i, duration in enumerate(durations):
        records += [event('case_start', t, case=i, profile=[0] * 7, pair=[0, 1]),
                    event('case_end', t + duration, case=i, outcome='empty', elapsed=duration)]
        t += duration
    return records


class LatticeProgressQuals(unittest.TestCase):
    def test_preparation_and_calibration_are_visible_before_any_case(self):
        # Replicata: the initial journal, then a calibration phase, with the process live.
        # Expectata: every case pending, explicit phases and symmetric scope, no invented ETA.
        for phase in ('preparation', 'calibration'):
            run = data(initial() + [event('phase', 110, phase=phase)])['runs'][0]
            self.assertEqual((run['scope'], run['phase'], run['state']), ('symmetric-witness', phase, 'running'))
            self.assertEqual(run['counts'], dict(settled=0, open=0, split=0, pending=2736, running=0))
            self.assertIsNone(run['to_go'])
            self.assertEqual(run['etas'], [])

    def test_attempts_change_snapshots_without_certifying_nonexistence(self):
        # Replicata: a running case followed by each possible completion, with a new snapshot.
        # Expectata: pending -> running -> open, never settled, including an empty enumeration.
        records = initial() + [event('phase', 105, phase='search'),
                               event('case_start', 110, case=2, profile=[0] * 7, pair=[0, 1])]
        before = data(records)['runs'][0]
        self.assertEqual(before['groups'][0][2], '4')
        for outcome in ('empty', 'timeout', 'witness'):
            after = data(records + [event('case_end', 115, case=2, outcome=outcome, elapsed=5)])['runs'][0]
            self.assertEqual(after['groups'][0][2], '1')
            self.assertEqual(after['counts'], dict(settled=0, open=1, split=0, pending=2735, running=0))
            self.assertNotEqual(before, after)

    def test_stopped_or_gone_process_does_not_show_a_running_case(self):
        # Replicata: an unfinished case, with its process stopped or absent.
        # Expectata: frozen/ended run; the unfinished case pending, elapsed pinned to last event.
        records = initial() + [event('phase', 105, phase='search'),
                               event('case_start', 110, case=2, profile=[0] * 7, pair=[0, 1])]
        for stat, state in [('T', 'frozen'), ('', 'ended')]:
            run = data(records, stat=stat)['runs'][0]
            self.assertEqual(run['state'], state)
            self.assertEqual(run['counts']['running'], 0)
            self.assertEqual(run['counts']['pending'], 2736)
            self.assertEqual(run['so_far'], 10)

    def test_resumed_session_excludes_the_gap_and_retries_interrupted_case(self):
        # Replicata: an interrupted first session and a resumed one under a new PID.
        # Expectata: the stopped interval is excluded, and the interrupted case is pending.
        records = initial() + [event('phase', 105, phase='search'),
                               event('case_start', 110, case=2, profile=[0] * 7, pair=[0, 1]),
                               dict(event='session', time=1000, pid=23456),
                               dict(event='phase', time=1001, pid=23456, phase='preparation')]
        run = data(records, now=1010)['runs'][0]
        self.assertEqual(run['so_far'], 20)
        self.assertEqual(run['counts']['pending'], 2736)

    def test_finish_and_malformed_journal_are_unambiguous(self):
        # Replicata: failed calibration; and an unknown event or a case ending before it starts.
        # Expectata: failure ends the run even before process exit; malformed records raise.
        run = data(initial() + [event('finish', 110, outcome='failed')])['runs'][0]
        self.assertEqual((run['state'], run['outcome']), ('ended', 'failed'))
        for bad in [event('mystery', 110), event('case_end', 110, case=0, outcome='empty', elapsed=1)]:
            with self.assertRaises(AssertionError):
                survey(initial() + [bad])

    def test_eta_records_only_snapshots_actually_requested(self):
        # Replicata: two completed attempts before the first survey, then another completion and survey.
        # Expectata: no backfilled points; each actual snapshot uses only its then-available durations.
        etas = {}
        first = data(completed([10, 20]), now=135, etas=etas)['runs'][0]
        self.assertEqual(first['to_go'], dict(median=2734 * 15, lo=0, hi=2734 * 30))
        self.assertEqual([p[0] for p in first['etas']], [135])
        second = data(completed([10, 20, 30]), now=165, etas=etas)['runs'][0]
        self.assertEqual(second['to_go']['median'], 2733 * 20)
        self.assertEqual(second['etas'][0], first['etas'][0])
        self.assertEqual([p[0] for p in second['etas']], [135, 165])

    def test_eta_band_is_a_cap_scenario_not_a_shrinking_confidence_interval(self):
        # Replicata: identical 10-second durations, with two versus twenty observations; one cap overrun.
        # Expectata: range stays 0..30 seconds per remaining attempt, and observed overruns extend it.
        for durations in ([10] * 2, [10] * 20, [10, 31]):
            run = data(completed(durations), now=105 + sum(durations))['runs'][0]
            remaining = 2736 - len(durations)
            self.assertEqual(run['to_go']['lo'], 0)
            self.assertEqual(run['to_go']['hi'], remaining * max(30, *durations))

    def test_running_attempt_uses_conditional_remaining_time(self):
        # Replicata: previous attempts took 10 and 30 seconds; the current one has already taken 20.
        # Expectata: its estimated remainder is 10, from the surviving 30-second observation, not zero.
        records = completed([10, 30]) + [event('case_start', 145, case=2, profile=[0] * 7, pair=[0, 1])]
        run = data(records, now=165)['runs'][0]
        self.assertEqual(run['to_go'], dict(median=2733 * 20 + 10, lo=0, hi=2733 * 30 + 10))

    def test_eta_history_survives_process_exit_and_resumption_without_time_reversal(self):
        # Replicata: snapshot at 145, process gone at 200, resumed at 1000, then another snapshot.
        # Expectata: exit does not invent extra running time; resume preserves the earlier curve's x coordinates.
        records, etas = completed([10, 20]), {}
        first = data(records, now=145, etas=etas)['runs'][0]
        stopped = data(records, now=200, stat='', etas=etas)['runs'][0]
        self.assertEqual(stopped['so_far'], first['so_far'])
        self.assertEqual(stopped['etas'], first['etas'])
        records += [dict(event='session', time=1000, pid=23456),
                    dict(event='phase', time=1001, pid=23456, phase='preparation')]
        resumed = data(records, now=1010, etas=etas)['runs'][0]
        self.assertIsNone(resumed['to_go'])
        self.assertEqual(resumed['etas'], first['etas'])
        self.assertEqual(resumed['so_far'], first['so_far'] + 10)

    def test_vanished_worker_requires_a_full_retry_of_its_unfinished_attempt(self):
        # Replicata: an active attempt has run 20 seconds after completed durations 10 and 30, then disappears.
        # Expectata: its next launch must repeat the whole attempt; the previous live estimate remains recorded.
        records = completed([10, 30]) + [event('case_start', 145, case=2, profile=[0] * 7, pair=[0, 1])]
        etas = {}
        live = data(records, now=165, etas=etas)['runs'][0]
        gone = data(records, now=200, stat='', etas=etas)['runs'][0]
        self.assertEqual(gone['to_go'], dict(median=2734 * 20, lo=0, hi=2734 * 30))
        self.assertEqual(gone['etas'], live['etas'])

    def test_first_survey_of_stopped_run_does_not_backdate_an_eta(self):
        # Replicata: mature journal first inspected after its process has stopped or disappeared.
        # Expectata: remaining work can be estimated now, but no estimate is invented at a past runtime timestamp.
        for stat in ('T', ''):
            run = data(completed([10, 20]), now=200, stat=stat)['runs'][0]
            self.assertIsNotNone(run['to_go'])
            self.assertEqual(run['etas'], [])

    def test_successful_finish_sets_eta_zero_but_failure_keeps_work_remaining(self):
        # Replicata: a mature search ending by witness or failure; a fully exhausted batch.
        # Expectata: witness/exhaustion have zero remaining time; a failure retains estimated unfinished work.
        for outcome in ('witness', 'failed'):
            run = data(completed([10, 20]) + [event('finish', 136, outcome=outcome)], now=140)['runs'][0]
            expected = 0 if outcome == 'witness' else 2734 * 15
            self.assertEqual(run['to_go']['median'], expected)
        records = completed([1] * 2736)
        run = data(records + [event('finish', 2842, outcome='exhausted')], now=2843)['runs'][0]
        self.assertEqual(run['to_go'], dict(median=0, lo=0, hi=0))


def browser():
    # Replicata: the real page receives preparation, calibration, running-case and attempted-case snapshots.
    # Expectata: dot counts change (no scope or phase prose since 2026-10-23); the chart always shows, its elapsed time even
    # with no ETA yet, then observed snapshots produce the blue elapsed, red remaining and purple total curves, with no JavaScript errors.
    import quals_index as q
    records, etas = initial(), {}
    snapshots = [data(records, 102, etas=etas)]
    for record in [event('phase', 103, phase='calibration'), event('phase', 104, phase='search'),
                   event('case_start', 105, case=0, profile=[0] * 7, pair=[0, 1]),
                   event('case_end', 106, case=0, outcome='timeout', elapsed=1)]:
        records.append(record)
        snapshots.append(data(records, record['time'], etas=etas))
    for i, duration in enumerate((10, 20), 1):
        start = records[-1]['time'] + 1
        records += [event('case_start', start, case=i, profile=[0] * 7, pair=[0, 1]),
                    event('case_end', start + duration, case=i, outcome='empty', elapsed=duration)]
        snapshots.append(data(records, start + duration, etas=etas))
    harness = '''<script>
const observations = [], failures = [];
addEventListener('error', e => failures.push(e.message));
for (const snapshot of SNAPSHOTS) {
  progressData(snapshot);
  const box = document.querySelector('.progress-runs .progress-run');
  observations.push({counts: Object.fromEntries([...box.querySelectorAll('[data-count]')].map(e => [e.dataset.count, e.textContent])),
    eta: box.querySelector('.progress-eta').hidden,
    curves: ['spent', 'togo', 'total'].map(name => { const e = box.querySelector('.progress-eta polyline.' + name);
      return {name, points: e.getAttribute('points'), color: getComputedStyle(e).stroke}; })});
}
const out = document.createElement('pre'); out.id = 'lattice-qual'; out.textContent = JSON.stringify({observations, failures}); document.body.appendChild(out);
</script>'''.replace('SNAPSHOTS', json.dumps(snapshots))
    with tempfile.TemporaryDirectory(prefix='lattice-progress-qual-') as d:
        text = open(os.path.join(HERE, 'index.html')).read().replace('</body>', harness + '</body>')
        open(os.path.join(d, 'index.html'), 'w').write(text)
        for name in ('mstar.js', 'pow2.js'):
            shutil.copy(os.path.join(HERE, name), os.path.join(d, name))
        q.copy_page_dir(d)
        dom = q.chrome(d, ['--window-size=1000,1100', '--virtual-time-budget=5000', '--dump-dom',
                           'file://' + os.path.join(d, 'index.html')])
        match = re.search(r'<pre id="lattice-qual">(.*?)</pre>', dom, re.S)
        assert match, dom[-2000:]
        got = json.loads(html.unescape(match[1]))
    assert got['failures'] == [], got
    obs = got['observations']
    assert not any(r['eta'] for r in obs), obs   # the chart always shows (dreeves, 2026-10-23)
    assert obs[3]['counts']['running'] == '1' and obs[4]['counts']['running'] == '0', obs
    assert obs[4]['counts']['open'] == '1' and obs[4]['counts']['settled'] == '0', obs
    curves = obs[-1]['curves']
    assert [c['name'] for c in curves] == ['spent', 'togo', 'total'], curves
    assert all(len(c['points'].split()) == 2 for c in curves), curves
    assert [c['color'] for c in curves] == ['rgb(42, 120, 214)', 'rgb(227, 73, 72)', 'rgb(123, 31, 162)'], curves
    print('browser: OK')


if __name__ == '__main__':
    if sys.argv[1:] == ['browser']:
        browser()
    else:
        unittest.main()
