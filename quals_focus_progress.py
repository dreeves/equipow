"""Quals for live snapshots of the focused all-sign proof searches."""
import json
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


def survey(records, now=110, alive=True, observations=None):
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'journal.jsonl')
        with open(path, 'w') as f:
            f.writelines(json.dumps(r) + '\n' for r in records)
        procs = [(123, 1, 'S', '/opt/homebrew/bin/python3 -B focus.py 480')] * alive
        return progress.survey_focus(path, procs, now, observations)


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

    def test_page_exposes_actual_work_without_a_fabricated_eta(self):
        # Replicata: the page template for the new journal's scope.
        # Expectata: cumulative node work has live fields, with each terminal
        # outcome distinct and no conversion of node counts into an ETA.
        page = Path(__file__).with_name('index.html').read_text()
        body = page.split('<template data-scope="focused-proof">')[1].split('</template>')[0]
        for name in ('lp', 'closed', 'split', 'pending'):
            self.assertIn(f'data-work="{name}"', body)
        for name in ('excluded', 'witness', 'budget'):
            self.assertIn(f'data-outcome="{name}"', body)
        self.assertIn("box.querySelectorAll('[data-work]')", page)

    def test_running_counts_do_not_pretend_a_profile_is_closed(self):
        # Replicata: twenty LP solves and eight certified leaves, first root case active.
        # Expectata: two root cases still unresolved; actual node work is shown separately.
        run = survey(initial())
        self.assertEqual(run['sea']['groups'], ['43'])
        self.assertEqual(run['display']['work'], dict(lp=20, closed=8, split=12, pending=5))
        self.assertEqual(run['sea']['counts']['settled'], 0)
        self.assertIsNone(run['to_go'])
        self.assertEqual(run['etas'], {})

    def test_budget_stop_and_resumption_preserve_completed_work(self):
        # Replicata: the first root closed, budget exhausted, then a resumed session.
        # Expectata: only that root is settled, the other is open; no exclusion or ETA.
        stop = dict(initial()[-1], event='finish', time=120, lp=100, closed=51,
                    split=49, pending=1, case=None, completed=[0], outcome='budget')
        records = initial() + [stop]
        run = survey(records, now=130)
        self.assertEqual((run['state'], run['display']['outcome']), ('ended', 'budget'))
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

    def test_regressing_work_is_rejected(self):
        # Replicata: a later snapshot reports fewer cumulative LP solves.
        # Expectata: malformed history raises, rather than silently resetting work.
        with self.assertRaises(AssertionError):
            survey(initial() + [dict(initial()[-1], time=109, lp=19)])


if __name__ == '__main__':
    unittest.main()
