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


def survey(records, now=120, stat='S'):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'journal.jsonl')
        with open(path, 'w') as f:
            f.writelines(json.dumps(r) + '\n' for r in records)
        procs = [(records[-1]['pid'], 1, stat, 'python3 -B lattice288.py')][:int(bool(stat))]
        return progress.survey_lattice(path, procs, now)


def data(records, now=120, stat='S'):
    return json.loads(progress.js_text([survey(records, now, stat)], now)[len('progressData('):-3])


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


def browser():
    # Replicata: the real page receives preparation, calibration, running-case and attempted-case snapshots.
    # Expectata: visible scope/phases and dot counts change, ETA remains absent, no JavaScript errors.
    import quals_index as q
    records = initial()
    snapshots = [data(records, 102)]
    for record in [event('phase', 103, phase='calibration'), event('phase', 104, phase='search'),
                   event('case_start', 105, case=0, profile=[0] * 7, pair=[0, 1]),
                   event('case_end', 106, case=0, outcome='timeout', elapsed=1)]:
        records.append(record)
        snapshots.append(data(records, record['time']))
    harness = '''<script>
const observations = [], failures = [];
addEventListener('error', e => failures.push(e.message));
for (const snapshot of SNAPSHOTS) {
  progressData(snapshot);
  const box = document.querySelector('.progress-runs .progress-run');
  observations.push({phase: [...box.querySelectorAll('[data-phase]')].filter(e => !e.hidden).map(e => e.textContent),
    scope: box.querySelector('[data-scope]').textContent, counts: Object.fromEntries([...box.querySelectorAll('[data-count]')].map(e => [e.dataset.count, e.textContent])),
    eta: box.querySelector('.progress-eta').hidden});
}
const out = document.createElement('pre'); out.id = 'lattice-qual'; out.textContent = JSON.stringify({observations, failures}); document.body.appendChild(out);
</script>'''.replace('SNAPSHOTS', json.dumps(snapshots))
    with tempfile.TemporaryDirectory(prefix='lattice-progress-qual-') as d:
        text = open(os.path.join(HERE, 'index.html')).read().replace('</body>', harness + '</body>')
        open(os.path.join(d, 'index.html'), 'w').write(text)
        for name in ('mstar.js', 'pow2.js'):
            shutil.copy(os.path.join(HERE, name), os.path.join(d, name))
        dom = q.chrome(d, ['--window-size=1000,1100', '--virtual-time-budget=5000', '--dump-dom',
                           'file://' + os.path.join(d, 'index.html')])
        match = re.search(r'<pre id="lattice-qual">(.*?)</pre>', dom, re.S)
        assert match, dom[-2000:]
        got = json.loads(html.unescape(match[1]))
    assert got['failures'] == [], got
    obs = got['observations']
    # The page's copy was translated during the live verification (2026-10-20).
    # Preserve those edits exactly, including "Prepration.".
    assert [r['phase'] for r in obs] == [['Prepration.'], ['Calibration against a known search.'], ['Search.'], ['Search.'], ['Search.']], obs
    assert all('symmetric witness search' in r['scope'] and 'do not exclude solutions' in r['scope'] and r['eta'] for r in obs), obs
    assert obs[-2]['counts']['running'] == '1' and obs[-1]['counts']['running'] == '0', obs
    assert obs[-1]['counts']['open'] == '1' and obs[-1]['counts']['settled'] == '0', obs
    print('browser: OK')


if __name__ == '__main__':
    if sys.argv[1:] == ['browser']:
        browser()
    else:
        unittest.main()
