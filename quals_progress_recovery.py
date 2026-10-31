"""Historical replay-cache recovery quals."""
import copy
import unittest
from unittest.mock import patch
import numpy as np
import progress
import quals_progress

selected = progress.resplits


class RecoveryQuals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        progress.v5.configure(64, 7)
        journal, log = quals_progress.tiny('open')
        cls.R = progress.read_run(journal, log)
        previous = cls.R['passes'][0]
        for nd in previous['nodes']:
            nd['solve'] = 1.0
            nd['split'] = 0.0
        p = dict(previous, nodes=[], opens=[], outcome=None, start=previous['last'] + 10,
                 last=previous['last'] + 10, budgets=[1, 1, 10])
        cls.R['passes'].append(p)
        cls.R['bounds'].append(len(cls.R['records']))
        cls.known = {}
        start = {r['key']: r for r in cls.R['records']}
        for key, r in start.items():
            if (r['verdict'] == 'UNKNOWN' and len(key.split()) < len(p['budgets']) - 1
                    and r['budget'] >= progress.budget_of(key, p['budgets'])):
                cls.known[key] = [progress.v5.node_key(c)
                                  for c in progress.v5.split(7, progress.parse_key(key))]
        cls.state = dict(t=p['start'], label='qual', passes=cls.R['passes'], processes=p['processes'],
                         budgets=p['budgets'], records=cls.R['records'],
                         final_at_start={r['key']:r for r in cls.R['records']}, cache=cls.known, pauses=())
        cls.expected = progress.estimate(cls.state)
        assert len(cls.expected) and np.ptp(cls.expected) > 0

    def test_complete_previous_pass_needs_no_repeated_split_and_preserves_draws(self):
        # Replicata: two passes, complete old child observations, and an empty replay cache.
        # Expectata: recover the exact original order without split(), retaining every uncertainty draw.
        with patch.object(progress.v5, 'split', side_effect=AssertionError('redundant enumeration')):
            got = selected(copy.deepcopy(self.R), 7, {})
        self.assertEqual(got, self.known)
        np.testing.assert_array_equal(progress.estimate(dict(self.state, cache=got)), self.expected)

    def test_incomplete_observations_still_request_the_real_split(self):
        # Replicata: remove one direct child's only line from the first pass.
        # Expectata: the helper cannot invent a complete split from an incomplete prefix.
        R = copy.deepcopy(self.R)
        R['passes'][0]['nodes'] = R['passes'][0]['nodes'][:1]
        with patch.object(progress.v5, 'split', side_effect=AssertionError('required enumeration')):
            with self.assertRaisesRegex(AssertionError, 'required enumeration'):
                selected(R, 7, {})

    def test_no_explicit_pool_declines_recovery(self):
        # Replicata: a complete-looking observation has no distinguishable pool key.
        # Expectata: a singleton pool's position is not guessed from sorted vector keys.
        R = copy.deepcopy(self.R)
        for nd in R['passes'][0]['nodes']:
            nd['key'] = nd['key'].replace('#0:f9065fa7389750e16fe00d7ba36748f61d3e0df6', '[0,0,0]')
        with patch.object(progress.v5, 'split', side_effect=AssertionError('required enumeration')):
            with self.assertRaisesRegex(AssertionError, 'required enumeration'):
                selected(R, 7, {})

    def test_later_partition_conflict_is_refused(self):
        # Replicata: a later pass observes a child outside an earlier complete partition.
        # Expectata: contradictory partitions fail, rather than being unioned or silently preferred.
        R = copy.deepcopy(self.R)
        later = copy.deepcopy(R['passes'][0])
        child = next(nd for nd in later['nodes'] if nd['key'] and '#' not in nd['key'])
        up = progress.parent_key(child['key'])
        modulus = child['key'].split()[-1].split(':')[0]
        child['key'] = (up + ' ' if up else '') + modulus + ':[999,0,0]'
        R['passes'].insert(1, later)
        R['bounds'].insert(1, len(R['records']))
        with patch.object(progress.v5, 'split', return_value=[]):
            with self.assertRaises(AssertionError):
                selected(R, 7, {})


class ObservationQuals(unittest.TestCase):
    def setUp(self):
        pool = '3:#0:f9065fa7389750e16fe00d7ba36748f61d3e0df6'
        self.keys = ['3:[-2,9,0]', '3:[10,2,0]', pool]
        nodes = [dict(key='', verdict='UNKNOWN', waiting=3, running=0, closed=0)]
        nodes += [dict(key=k, verdict='UNKNOWN', waiting=2-i, running=0, closed=0)
                  for i, k in enumerate(reversed(self.keys[:2]))]
        nodes.append(dict(key=pool, verdict='INFEASIBLE', waiting=0, running=0, closed=1))
        p = dict(n=64, order=7, moduli=[3], pool_budget=3, budgets=[1, 10], nodes=nodes)
        self.R = dict(passes=[p, dict(p, nodes=[])], bounds=[0, 1],
                      records=[dict(key='', verdict='UNKNOWN', budget=1)])

    def test_numeric_vector_order_and_explicit_pool_last(self):
        # Replicata: completion order differs from numeric split order.
        # Expectata: recover numeric vector order, followed by the distinguishable pool.
        with patch.object(progress.v5, 'split', side_effect=AssertionError('redundant enumeration')):
            self.assertEqual(selected(self.R, 7, {}), {'': self.keys})

    def test_incomplete_passes_are_never_unioned(self):
        # Replicata: two incomplete passes cover all children only when combined.
        # Expectata: neither pass proves completeness; request the actual split.
        p = self.R['passes'][0]
        later = copy.deepcopy(p)
        p['nodes'].pop(1)
        later['nodes'].pop(2)
        self.R['passes'].insert(1, later)
        self.R['bounds'].insert(1, 1)
        with patch.object(progress.v5, 'split', side_effect=AssertionError('required enumeration')):
            with self.assertRaisesRegex(AssertionError, 'required enumeration'):
                selected(self.R, 7, {})

    def test_unknown_explicit_pool_does_not_certify_completeness(self):
        # Replicata: the explicit pool was UNKNOWN and could expand at the same key depth.
        # Expectata: do not mistake its members for original sibling observations.
        self.R['passes'][0]['nodes'][-1]['verdict'] = 'UNKNOWN'
        with patch.object(progress.v5, 'split', side_effect=AssertionError('required enumeration')):
            with self.assertRaisesRegex(AssertionError, 'required enumeration'):
                selected(self.R, 7, {})

    def test_conflicting_child_counts_fail(self):
        # Replicata: a later compatible pass reports a different split size.
        # Expectata: the contradiction is reported before invoking the solver.
        later = copy.deepcopy(self.R['passes'][0])
        later['nodes'][0]['waiting'] += 1
        self.R['passes'].insert(1, later)
        self.R['bounds'].insert(1, 1)
        with patch.object(progress.v5, 'split', return_value=[]):
            with self.assertRaises(AssertionError):
                selected(self.R, 7, {})

    def test_existing_cache_must_match_recovered_order(self):
        # Replicata: a cache holds all children in the wrong original order.
        # Expectata: refuse the contradiction instead of silently keeping or replacing it.
        with self.assertRaises(AssertionError):
            selected(self.R, 7, {'': list(reversed(self.keys))})

    def test_incompatible_cascade_is_not_reused(self):
        # Replicata: the complete prior observations used a different cascade.
        # Expectata: the current cascade requires its own split.
        self.R['passes'][0]['moduli'] = [5]
        with patch.object(progress.v5, 'split', side_effect=AssertionError('required enumeration')):
            with self.assertRaisesRegex(AssertionError, 'required enumeration'):
                selected(self.R, 7, {})


if __name__ == '__main__':
    unittest.main()
