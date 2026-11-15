#!/usr/bin/env python3
"""Quals for retrospective ETA scoring. Run: python3 -B quals/quals_eta_replay.py."""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'searchwatch'))


def band(m, lo=None, hi=None):
    return dict(median=m, lo=m if lo is None else lo, hi=m if hi is None else hi)


def snapshot(t=12, done=4, rate=2, total=None, to_go=None):
    return dict(time=t, done=done, rate=rate, total=total, to_go=to_go or band(26, 10, 30))


def verdict(start, nodes, spills=()):
    return dict(start=start, nodes=nodes, spills=list(spills), ok=True, open=0)


class Replay(unittest.TestCase):
    # Each qual's first clause is the replicata, second the expectata. The assertion's
    # actual result is the resultata; before implementation all imports fail.
    def test_optimized_python_is_rejected(self):
        # Python -O would erase input assertions: importing the evaluator must fail.
        result = subprocess.run([sys.executable, '-B', '-O', '-c', 'import eta_replay'],
                                cwd=ROOT/'searchwatch', capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_active_clock_unions_overlap_and_omits_pauses(self):
        # Overlapping runs with a pause: 25 active seconds, 13 remaining at t=12.
        import eta_replay as e
        self.assertEqual(e.active_seconds([[0, 10], [8, 15], [30, 40]], 0), 25)
        self.assertEqual(e.active_seconds([[0, 10], [8, 15], [30, 40]], 12), 13)

    def test_spilled_roots_are_counted_once(self):
        # A five-node task spills a seven-node child: exactly 11 expanded nodes.
        import eta_replay as e
        self.assertEqual(e.exact_total([verdict('r', 5, ['c']), verdict('c', 7)], ['r']), 11)

    def test_unfinished_or_inconsistent_proof_is_rejected(self):
        # Missing, orphaned, shared, duplicate, and rejected tasks must not supply truth.
        import eta_replay as e
        for rows in ([verdict('r', 5, ['c'])], [verdict('r', 5), verdict('o', 7)],
                     [verdict('r', 5, ['c', 'c']), verdict('c', 7)],
                     [verdict('r', 5), verdict('r', 5)], [dict(verdict('r', 5), ok=False)]):
            with self.assertRaises(AssertionError): e.exact_total(rows, ['r'])

    def test_errors_keep_work_rate_and_time_separate(self):
        # Work is overestimated 2x, time 2x, rate has its own future-average denominator.
        import eta_replay as e
        s = snapshot(total=band(18, 10, 20))
        r = e.score(s, 11, [[0, 10], [8, 15], [30, 40]])
        self.assertEqual(r['actual'], dict(work=7, seconds=13, rate=7/13))
        self.assertEqual(r['work']['factor'], 2)
        self.assertEqual(r['total']['factor'], 18/11)
        self.assertEqual(r['total']['error'], r['work']['error'])
        self.assertEqual(r['work']['error'], 7)
        self.assertEqual(r['work']['width'], 10)
        self.assertTrue(r['work']['hit'])
        self.assertEqual(r['seconds']['factor'], 2)
        self.assertEqual(r['rate']['factor'], 26/7)

    def test_unavailable_work_bands_remain_unavailable(self):
        # A legacy time forecast with no total-work band: do not manufacture one.
        import eta_replay as e
        r = e.score(snapshot(), 11, [[0, 40]])
        self.assertIsNone(r['work'])
        self.assertEqual(r['seconds']['error'], -2)

    def test_truth_does_not_rewrite_forecasts(self):
        # Replaying against two outcomes changes truth only, never the saved input.
        import eta_replay as e
        s = snapshot(total=band(18, 10, 20)); before = copy.deepcopy(s)
        a, b = [e.score(s, n, [[0, 40]]) for n in (11, 15)]
        self.assertEqual(s, before)
        self.assertEqual(a['forecast'], b['forecast'])
        a['forecast']['done'] = 0
        self.assertEqual(s, before)

    def test_zero_denominators_are_null(self):
        # An exact forecast at completion: zero errors, undefined multiplicative errors.
        import eta_replay as e
        r = e.score(snapshot(t=40, done=11, total=band(11), to_go=band(0)), 11, [[0, 40]])
        self.assertEqual(r['work']['error'], 0)
        self.assertEqual(r['seconds']['error'], 0)
        self.assertIsNone(r['work']['factor'])
        self.assertIsNone(r['seconds']['factor'])
        self.assertIsNone(r['actual']['rate'])
        self.assertIsNone(r['rate'])

    def test_cleanup_time_can_follow_exact_work(self):
        # All work reported before process cleanup: retain seconds but omit from summary.
        import eta_replay as e
        r = e.score(snapshot(t=39, done=11, total=band(11), to_go=band(0)), 11, [[0, 40]])
        self.assertEqual(r['actual']['seconds'], 1)
        self.assertEqual(e.summarize([r])['forecasts'], 0)

    def test_correlated_snapshots_are_summarized_per_search(self):
        # Two identical forecasts and an exact terminal snapshot: count only the first two.
        import eta_replay as e
        r = e.score(snapshot(), 11, [[0, 40]])
        terminal = e.score(snapshot(t=40, done=11, to_go=band(0)), 11, [[0, 40]])
        summary = e.summarize([r, r, terminal])
        self.assertEqual(summary['forecasts'], 2)
        self.assertEqual(summary['seconds']['median_absolute_error'], 2)
        self.assertEqual(summary['seconds']['band_hits'], 2)
        self.assertIsNone(summary['work'])

    def test_invalid_forecasts_and_clocks_fail(self):
        # Bad numbers, work beyond the exact result, incomplete clocks: assert immediately.
        import eta_replay as e
        for s in (snapshot(done=12), snapshot(rate=0), snapshot(t=-1), snapshot(t=41),
                  snapshot(done=float('nan')), snapshot(rate=float('inf')),
                  snapshot(to_go=band(-1)), snapshot(total=band(3)), snapshot(t=40)):
            with self.assertRaises(AssertionError): e.score(s, 11, [[0, 40]])
        for spans in ([], [[0, None]], [[10, 0]], [[0, float('inf')]]):
            with self.assertRaises(AssertionError): e.active_seconds(spans, 0)

    def test_forecast_units_must_agree(self):
        # A seconds-work forecast fed to a nodes replay must fail, even with valid numbers.
        import eta_replay as e
        with self.assertRaises(AssertionError):
            e.score(dict(snapshot(), unit='seconds'), 11, [[0, 40]])

    def test_manifest_checks_sources_and_prefix_work(self):
        # A complete small archive is reproducible; altered sources or prefix counts fail.
        import eta_replay as e
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v = root/'v.jsonl'; f = root/'f.jsonl'
            v.write_text('\n'.join(map(json.dumps, [verdict('r', 5, ['c']), verdict('c', 7)]))+'\n')
            f.write_text(json.dumps(dict(snapshot(total=band(18, 10, 20)), finished=1))+'\n')
            hashes = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (v, f)}
            run = dict(name='small', target='16:2', unit='nodes', roots=['r'], verdicts=v.name,
                       forecasts=f.name, spans=[[0, 40]], expected_total=11, source_hashes=hashes(),
                       model_sources={}, band_quantiles=None, notes=[])
            manifest = dict(version=1, runs=[run])
            report = e.replay(manifest, root)
            self.assertEqual(report['runs'][0]['total'], 11)
            self.assertEqual(report['runs'][0]['summary']['forecasts'], 1)
            with self.assertRaises(AssertionError):
                e.replay(dict(version=1, runs=[run | dict(expected_finished=99)]), root)
            f.write_text(json.dumps(dict(snapshot(), target='32:3', finished=1))+'\n')
            run['source_hashes'] = hashes()
            with self.assertRaises(AssertionError): e.replay(manifest, root)
            f.write_text(json.dumps(dict(snapshot(done=5), finished=1))+'\n')
            with self.assertRaises(AssertionError): e.replay(manifest, root)
            run['source_hashes'] = hashes()
            with self.assertRaises(AssertionError): e.replay(manifest, root)
            for change in (dict(unit='seconds'), dict(target='wrong'), dict(expected_total=12)):
                with self.assertRaises(AssertionError): e.replay(dict(version=1, runs=[run | change]), root)


if __name__ == '__main__': unittest.main()
