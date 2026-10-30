"""Small deterministic quals; no solver work, journal writes, or split generation."""
import unittest
from unittest.mock import patch

import numpy as np

import progress

def phase(nodes=(), **changes):
    out = dict(n=288, order=10, budgets=[100, 100, 100], moduli=[3, 5],
               pool_budget=1, shuffled=False, nodes=list(nodes))
    out.update(changes)
    return out


def job(key, cost):
    return dict(key=key, solve=cost, split=0.0)


def fixture(restarted, count=100, partial=False):
    """The same finished donor subtrees before and after a zero-cost replay."""
    root = progress.Node('', None, 0)
    root.state = 'done'
    records, old, current, donors = {}, [], [], []
    for i in range(count):
        key = f'3:[{i}]'
        donor = progress.Node(key, root, 1)
        donor.state, donor.cost = 'done', 0.0 if restarted else 10.0
        child = progress.Node(key + ' 5:[0]', donor, 2)
        child.state = 'skipped' if restarted else 'done'
        child.cost, child.fresh = (0.0, False) if restarted else (100.0, True)
        donor.kids = [child]
        root.kids.append(donor)
        donors.append(donor)
        old.extend((job(key, 10.0), job(child.key, 100.0)))
        current.append(job(key, donor.cost))
        records[key] = dict(verdict='UNKNOWN', budget=100)
        if restarted:
            records[child.key] = dict(verdict='INFEASIBLE', budget=100)
    pending = progress.Node(f'3:[{count}]', root, 1)
    root.kids.append(pending)
    stack = [pending]
    if partial:
        leaf = progress.Node(donors[-1].key + ' 5:[1]', donors[-1], 2)
        donors[-1].kids.append(leaf)
        stack.append(leaf)
    passes = [phase(old), phase(current)] if restarted else [phase(old)]
    state = dict(t=1000.0, label='restart fixture', passes=passes, processes=1,
                 budgets=[100, 100, 100], final_at_start=records, records=[], cache={})
    return state, (root, stack, []), donors, pending


def estimate(state, tree):
    implementation = progress.estimate
    with patch.dict(implementation.__globals__, replay=lambda _: tree, speed=lambda _: 1.0):
        parts = {}
        draws = implementation(state, parts)
    return draws, parts


class HistoryQuals(unittest.TestCase):
    def test_replayed_donors_cannot_erase_their_positive_costs(self):
        # Replicata: 100 completed costly donors replay for zero seconds; one wholly fresh subtree waits.
        # Expectata: their historical 110-second costs remain in the central forecast interval.
        state, tree, donors, pending = fixture(True)
        after, parts = estimate(state, tree)
        np.testing.assert_array_equal(np.quantile(after * progress.HOUR, [.05, .5, .95]), [110.0] * 3)
        self.assertEqual(parts['urns'][1].m, len(donors))

    def test_restart_does_not_collapse_an_unchanged_work_forecast(self):
        # Replicata: identical finished donors and pending work, observed continuously or after restart.
        # Expectata: the median and central 90% interval agree; a restart cannot erase observations.
        continuous = fixture(False)
        resumed = fixture(True)
        a, _ = estimate(*continuous[:2])
        b, _ = estimate(*resumed[:2])
        np.testing.assert_array_equal(np.quantile(a, [.05, .5, .95]), np.quantile(b, [.05, .5, .95]))

    def test_historical_work_is_not_charged_to_an_existing_branch(self):
        # Replicata: one old donor still has one unseen leaf, beside a wholly fresh subtree.
        # Expectata: the old branch owes only that leaf, while donor predictions include its completed history.
        state, tree, donors, pending = fixture(True, count=1, partial=True)
        draws, parts = estimate(state, tree)
        donor, leaf = donors[0], donors[0].kids[-1]
        self.assertEqual(parts['sofar'][donor], 0.0)
        np.testing.assert_array_equal(parts['rem'][donor], parts['rem'][leaf])
        np.testing.assert_allclose(parts['urns'][1].M[:, 0], 110.0 + parts['rem'][leaf])
        np.testing.assert_allclose(parts['work'], parts['rem'][leaf] + parts['rem'][pending])
        np.testing.assert_allclose(draws * progress.HOUR, parts['work'])

    def test_first_pass_has_no_historical_credit(self):
        # Replicata: a first pass with completed donors and unfinished work.
        # Expectata: no historical credit; each finished donor still supplies its measured 110 seconds.
        state, tree, donors, _ = fixture(False, count=5)
        self.assertEqual(progress.history_costs(state), ({}, {}))
        draws, parts = estimate(state, tree)
        np.testing.assert_array_equal(parts['urns'][1].M[:, :len(donors)], 110.0)
        np.testing.assert_allclose(draws * progress.HOUR, parts['work'])

    def test_history_stops_at_the_first_incompatible_phase(self):
        # Replicata: matching old budgets separated from the present phase by different budgets.
        # Expectata: only the immediately preceding compatible phase contributes, never the older matching one.
        state, _, _, _ = fixture(True, count=1)
        state['passes'] = [phase([job('3:[0]', 900.0)]),
                           phase([job('3:[0]', 800.0)], budgets=[100, 100, 200]),
                           phase([job('3:[0]', 7.0)]), phase()]
        own, total = progress.history_costs(state)
        self.assertEqual(own, {'3:[0]': 7.0})
        self.assertEqual(total, {'': 7.0, '3:[0]': 7.0})

    def test_other_search_identity_changes_also_end_the_phase(self):
        # Replicata: equal budgets with a different length, order, moduli, or pool budget.
        # Expectata: each mismatch prevents silently borrowing incompatible costs.
        state, _, _, _ = fixture(True, count=1)
        for changes in (dict(n=240), dict(order=9), dict(moduli=[3, 7]), dict(pool_budget=2)):
            with self.subTest(changes=changes):
                state['passes'] = [phase([job('3:[0]', 900.0)], **changes), phase()]
                self.assertEqual(progress.history_costs(state), ({}, {}))

    def test_duplicate_resplits_do_not_become_new_observations(self):
        # Replicata: the same completed jobs followed by another zero-cost replay and a later restart.
        # Expectata: each key contributes its first cost once; maps retain only above-bottom donor keys.
        state, _, _, _ = fixture(True, count=1)
        state['passes'].insert(1, phase([job('3:[0]', 0.0), job('3:[0] 5:[0]', 0.0)]))
        own, total = progress.history_costs(state)
        self.assertEqual(own, {'3:[0]': 10.0})
        self.assertEqual(total, {'': 110.0, '3:[0]': 110.0})

    def test_fresh_ball_uses_the_first_own_job_not_a_replay_charge(self):
        # Replicata: an old ten-second own job now incurs a tiny resplit charge.
        # Expectata: the fresh-ball own-cost input is the ten-second observation, not their sum.
        state, tree, donors, _ = fixture(True, count=1)
        donors[0].cost = 0.2
        original, captured = progress.fresh_ball, []
        def recording(rng, own, kids, below):
            captured.append(own.copy())
            return original(rng, own, kids, below)
        with patch.dict(progress.estimate.__globals__, fresh_ball=recording):
            estimate(state, tree)
        np.testing.assert_array_equal(captured[0], [10.0])

    def test_nonzero_replay_cost_does_not_inflate_a_donor(self):
        # Replicata: both an earlier replay and this replay charge for already measured jobs.
        # Expectata: a donor still represents its first 110 seconds, irrespective of restart count.
        state, tree, donors, _ = fixture(True, count=100)
        replayed = [job(n.key, .2) for n in donors]
        state['passes'].insert(1, phase(replayed))
        state['passes'][-1]['nodes'] = replayed
        for donor in donors:
            donor.cost = .2
        draws, parts = estimate(state, tree)
        np.testing.assert_array_equal(np.quantile(draws * progress.HOUR, [.05, .5, .95]), [110.0] * 3)
        np.testing.assert_array_equal(parts['urns'][1].M[:, :len(donors)], 110.0)
        self.assertEqual(parts['sofar'][donors[0]], .2)

    def test_zero_first_job_stays_zero_after_a_charged_replay(self):
        # Replicata: previously zero-cost jobs now incur a nonzero replay charge.
        # Expectata: donor observations stay zero; accounting still retains current execution cost.
        state, tree, donors, _ = fixture(True, count=1)
        state['passes'][0]['nodes'] = [job('3:[0]', 0.0), job('3:[0] 5:[0]', 0.0)]
        state['passes'][-1]['nodes'] = [job('3:[0]', .2)]
        donors[0].cost = .2
        _, parts = estimate(state, tree)
        np.testing.assert_array_equal(parts['urns'][1].M[:, 0], 0.0)
        self.assertEqual(parts['sofar'][donors[0]], .2)

    def test_cached_pending_resplit_expands_without_solving(self):
        # Replicata: a pending parent has a prior UNKNOWN verdict and one cached child.
        # Expectata: the estimator expands it and charges only the child, without generating a split.
        state, tree, _, pending = fixture(True, count=1)
        state['final_at_start'][pending.key] = dict(verdict='UNKNOWN', budget=100)
        state['cache'][pending.key] = [pending.key + ' 5:[0]']
        _, parts = estimate(state, tree)
        self.assertEqual([n.key for n in pending.kids], state['cache'][pending.key])
        np.testing.assert_array_equal(parts['rem'][pending], parts['rem'][pending.kids[0]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
