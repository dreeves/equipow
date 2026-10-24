"""Quals for reflection reuse, resumable splicing, and sibling LP warm starts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import certbb
import fanout
import focus
import reflection
from quals_fanout import events, finish, stopped


def paired():
    equations = focus.moments(20, 5)
    source = ((3, (2, 4, 4)),)
    return equations, (source, reflection.choice(equations, source))


class FanoutSpeedQuals(unittest.TestCase):
    def test_only_one_reflected_case_is_searched_and_both_are_checked(self):
        # Replicata: two reflected impossible cases, stopped after one LP.
        # Expectata: only case 0 uses workers; its proof reflected closes case 1.
        # Resultata before the change: both equivalent cases use workers.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = paired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            with patch.object(fanout, 'CHUNK', 2):
                outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            self.assertEqual({e['case'] for e in events(own) if e['event'] == 'job_start'}, {0})
            records = [r for p in sorted(run.glob('chunk-*.json.gz')) for r in fanout.read(p)['records']]
            proofs = [[tuple(r['token']) for r in records if r['case'] == c] for c in (0, 1)]
            self.assertEqual(proofs[1], [reflection.token(prepared[0], prepared[1][0], t) for t in proofs[0]])
            replayed = focus.replay(run, *prepared, focus.fingerprint())
            self.assertEqual((replayed.completed, replayed.frontier), ([0, 1], []))

    def test_a_partial_splice_resumes_without_repeating_finished_jobs(self):
        # Replicata: interruption immediately after a durable splice chunk.
        # Expectata: resume checks that prefix, then appends its remaining proof.
        # Resultata before the change: the original-frontier assertion fails.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = paired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            real_commit = focus.commit
            def interrupted(*args):
                real_commit(*args)
                raise KeyboardInterrupt
            with patch.object(fanout, 'CHUNK', 2), patch.object(focus, 'commit', interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    finish(tmp, run, journal, prepared, 20, 5)
            own = Path(tmp, 'fanout.jsonl')
            before = [e for e in events(own) if e['event'] == 'job_start']
            with patch.object(fanout, 'CHUNK', 2):
                outcome, _, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            self.assertEqual(before, [e for e in events(own) if e['event'] == 'job_start'])
            self.assertEqual(focus.replay(run, *prepared, focus.fingerprint()).completed, [0, 1])

    def test_partial_target_is_not_replaced(self):
        # Replicata: the reflected target has already been partly spliced.
        # Expectata: only an untouched full root can be replaced by reflection.
        # Resultata before the change: no reflection-selection contract exists.
        prepared = paired()
        self.assertEqual(fanout.reflections(prepared, [(1, ()), (0, ((0, 1),))]), {1: 0})
        self.assertEqual(fanout.reflections(prepared, [(1, ((0, 1),))]), {})

    def test_unpaired_cases_with_extra_equations_remain_searchable(self):
        # Replicata: extra equations, as in 480:14, and no reflected case pair.
        # Expectata: no reflection is requested, so no reflection mapping is required.
        # Resultata before the change: checking count profiles asserts on extra rows.
        equations = certbb.Moments(((1, 1, 1, 1),), (2,), (((1, 0, 0, 0),), (0,)))
        cases = (((4, (0, 0, 1, 1)),), ((4, (0, 1, 0, 1)),))
        self.assertEqual(fanout.reflections((equations, cases), [(1, ()), (0, ())]), {})

    def test_chained_reflections_are_rejected_before_search(self):
        # Replicata: duplicated source profiles would make one reflected case another's source.
        # Expectata: reject a chain rather than request proof files for skipped jobs.
        # Resultata before the change: selection returned the unsupported chain.
        equations, cases = paired()
        with self.assertRaises(AssertionError):
            fanout.reflections((equations, cases + cases[:1]), [(2, ()), (1, ()), (0, ())])

    def test_restart_inside_reflection_and_after_its_final_commit(self):
        # Replicata: interruption after a reflected chunk, or its final excluded chunk.
        # Expectata: exact replay completes; a finished splice appends no extra chunks.
        for terminal in (False, True):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as tmp:
                prepared = paired()
                run, journal = stopped(tmp, prepared, 20, 5, 1)
                real_commit = focus.commit
                def interrupted(directory, state, records, code):
                    real_commit(directory, state, records, code)
                    during = state.case == 1 and any(r['case'] == 1 for r in records)
                    if (state.outcome == 'excluded') if terminal else during:
                        raise KeyboardInterrupt
                with patch.object(fanout, 'CHUNK', 2), patch.object(focus, 'commit', interrupted):
                    with self.assertRaises(KeyboardInterrupt):
                        finish(tmp, run, journal, prepared, 20, 5)
                before = len(list(run.glob('chunk-*.json.gz')))
                with patch.object(fanout, 'CHUNK', 2):
                    outcome, _, _ = finish(tmp, run, journal, prepared, 20, 5)
                self.assertEqual(outcome, 'excluded')
                self.assertEqual(focus.replay(run, *prepared, focus.fingerprint()).completed, [0, 1])
                if terminal:
                    self.assertEqual(len(list(run.glob('chunk-*.json.gz'))), before)

    def test_workers_restore_a_parent_basis_and_still_prove_the_box(self):
        # Replicata: depth-first search of the impossible length-20 order-5 box.
        # Expectata: returning to siblings restores saved parent LP bases.
        # Resultata before the change: every sibling inherits its last descendant's basis.
        prepared = focus.moments(20, 5), ((),)
        fanout.lp_for.cache_clear()
        fanout.init(prepared, 10000, 8)
        lp = fanout.lp_for(0)
        native = lp.H
        lp.H = Mock(wraps=native)
        result = fanout.work((0, ()))
        self.assertIsNone(result['witness'])
        self.assertEqual(result['open'], [])
        certbb.verify(prepared[0], (), result['tokens'])
        self.assertGreater(lp.H.setBasis.call_count, 0)
        fanout.lp_for.cache_clear()


if __name__ == '__main__':
    unittest.main()
