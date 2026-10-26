"""Quals for reflection reuse, restartable assembly (resumable splicing before tree-only storage, 2026-10-25), and
sibling LP warm starts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import certbb
import fanout
import focus
import reflection
import reprove
from quals_fanout import events, finish, stopped


def paired():
    equations = focus.moments(20, 5)
    source = ((3, (2, 4, 4)),)
    return equations, (source, reflection.choice(equations, source))


def whole(run, work, case):
    """case's whole tree in depth-first order, as the splice once streamed its tokens: the run's chunks' tokens of case,
    each L's certificate dropped, then the trees of its roots' jobs, last root first, a job's tree before its open
    boxes' jobs, last first."""
    records = [r for p in sorted(Path(run).glob('chunk-*.json.gz')) for r in fanout.read(p)['records']]
    tree = [['B', r['token'][1]] if r['token'][0] == 'B' else ['L'] for r in records if r['case'] == case]
    todo = [b for b in fanout.roots(run, work, focus.fingerprint()) if b[0] == case]
    while todo:
        data = fanout.read(Path(work, 'jobs', f'{fanout.jid(todo.pop())}.json.gz'))
        tree += data['tree']
        todo += [fanout.key(case, p) for p in data['open']]
    return tree


class FanoutSpeedQuals(unittest.TestCase):
    def test_only_one_reflected_case_is_searched_and_both_are_closed(self):
        # Replicata: two reflected impossible cases, stopped after one LP; then case 0's whole tree, reflected (each
        # B position p made 19 - p), reproven from scratch on case 1's own LP by reprove.walk.
        # Expectata: only case 0 uses workers, and assembly walks only case 0's jobs, case 1 closing with case 0
        # (reversal maps case 1's solutions onto case 0's, reflection.mapping checking the rows exactly); excluded;
        # and the reflected tree a complete tree on case 1's box, every leaf of it proven by an exact certificate.
        # Resultata before the change: both equivalent cases use workers.  Before tree-only storage (2026-10-25,
        # this qual then named test_only_one_reflected_case_is_searched_and_both_are_checked): case 0's proof,
        # reflected token by token, was spliced and replayed as case 1's.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = paired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            self.assertEqual({e['case'] for e in events(own) if e['event'] == 'job_start'}, {0})
            code = focus.fingerprint()
            roots = fanout.roots(run, work, code)
            self.assertIn((1, ()), roots)
            walked = fanout.assemble(run, work, own, prepared, code, roots, fanout.finished(work))
            self.assertEqual({case for case, _ in walked}, {0})
            reflected = [['B', 19 - t[1]] if t[0] == 'B' else t for t in whole(run, work, 0)]
            self.assertEqual(fanout.frontier(20, [], reflected), [])
            reprove.init(prepared)
            proof = reprove.walk((1, ()), reflected)
            self.assertEqual((proof['nodes'], proof['leaves']), (len(reflected), reflected.count(['L'])))

    def test_an_interrupted_assembly_starts_no_job_again(self):
        # Replicata: fanout on two reflected impossible cases, stopped after one LP, interrupted inside its assembly
        # (fanout.frontier raising on its third call), then run again.
        # Expectata: excluded, the second session starting no job: assembly writes nothing, so a restart simply
        # assembles again from the job files, all kept; one finish, after the second session.
        # Resultata before tree-only storage (2026-10-25, this qual then named
        # test_a_partial_splice_resumes_without_repeating_finished_jobs): the splice committed chunks, and a restart
        # replayed and compared those before appending the rest.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = paired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            real_frontier, calls = fanout.frontier, []
            def interrupted(*args):
                calls.append(1)
                if len(calls) == 3: raise KeyboardInterrupt
                return real_frontier(*args)
            with patch.object(fanout, 'frontier', interrupted), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            own = Path(tmp, 'fanout.jsonl')
            before = [e for e in events(own) if e['event'] == 'job_start']
            self.assertTrue(before)
            self.assertNotIn('finish', [e['event'] for e in events(own)])
            outcome, _, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            log = events(own)
            self.assertEqual(before, [e for e in log if e['event'] == 'job_start'])
            self.assertEqual([e['event'] for e in log].count('finish'), 1)
            self.assertEqual([e['event'] for e in log][-1], 'finish')

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

    def test_fanout_writes_none_of_the_run_s_chunks(self):
        # Replicata: two reflected impossible cases stopped after one LP, the bytes of the run's chunks recorded; fanout
        # to its finish; then its assembly once more.
        # Expectata: excluded; the run's chunks byte for byte as they were, none added, and their replay still ending
        # at fanout's roots; assembly again walking the same jobs.
        # Resultata before tree-only storage (2026-10-25, this qual then named
        # test_restart_inside_reflection_and_after_its_final_commit): the splice appended chunks, and a restart inside
        # its reflected part, or after its final commit, had to replay them exactly.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = paired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            chunks = {p.name: p.read_bytes() for p in run.glob('chunk-*.json.gz')}
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            self.assertEqual({p.name: p.read_bytes() for p in run.glob('chunk-*.json.gz')}, chunks)
            code = focus.fingerprint()
            roots = fanout.roots(run, work, code)
            self.assertEqual([fanout.key(*b) for b in focus.replay(run, *prepared, code).frontier], roots)
            walked = [fanout.assemble(run, work, own, prepared, code, roots, fanout.finished(work)) for _ in range(2)]
            self.assertEqual(walked[0], walked[1])
            self.assertEqual(sorted(map(fanout.jid, walked[0])),
                             sorted(e['job'] for e in events(own) if e['event'] == 'job_end'))

    def test_workers_restore_a_parent_basis_and_still_prove_the_box(self):
        # Replicata: depth-first search of the impossible length-20 order-5 box.
        # Expectata: returning to siblings restores saved parent LP bases; the job's tree a complete tree on the box,
        # every leaf of it proven again from scratch by reprove.walk (before tree-only storage, 2026-10-25:
        # certbb.verify of the job's tokens, which no longer leave the worker).
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
        self.assertEqual(fanout.frontier(20, [], result['tree']), [])
        reprove.init(prepared)
        self.assertEqual(reprove.walk((0, ()), result['tree'])['leaves'], result['tree'].count(['L']))
        self.assertGreater(lp.H.setBasis.call_count, 0)
        fanout.lp_for.cache_clear()


if __name__ == '__main__':
    unittest.main()
