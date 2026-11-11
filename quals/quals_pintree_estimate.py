"""Known-tree quals for the pin-tree cost estimator; no LP or proof search."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'searches' / 'pintree'))
import pintree_prove as pp


class Clock:
    def __init__(self):
        self.cpu = self.wall = 0.0

    def advance(self, cpu):
        self.cpu += cpu
        self.wall += 10 * cpu


def toy(clock, children, costs):
    class Prover:
        def __init__(self, *args):
            pass

        def close(self, pins):
            node = pins[1][0]
            clock.advance(costs[node])
            return None if children[node] is None or children[node] else 0

        def split_choice(self, pins):
            nodes = children[pins[1][0]]
            return None if nodes is None else (1, [(n,) for n in nodes], [])
    return Prover


class Estimate(unittest.TestCase):
    def dive(self, children, costs, choice=(0,), limit=10000):
        clock = Clock()
        rng = mock.Mock()
        choices = iter(choice)
        rng.choice.side_effect = lambda xs: xs[next(choices)]
        with mock.patch.object(pp, 'Prover', toy(clock, children, costs)), \
             mock.patch.object(pp.random, 'Random', return_value=rng), \
             mock.patch.object(pp.time, 'time', side_effect=lambda: clock.wall), \
             mock.patch.object(pp.time, 'monotonic', side_effect=lambda: clock.wall), \
             mock.patch.object(pp.time, 'process_time', side_effect=lambda: clock.cpu):
            return pp.dive((16, 3, (), 20, {1: (0,)}, 1, limit))

    def test_completed_paths_count_closed_children_and_weight_cpu_cost(self):
        # Replicata: a root costing 1 CPU-second and two leaves costing 1 and 100;
        # run both equally likely paths. Wall time is ten times CPU time.
        # Expectata: mean tree size 3 and mean CPU cost 102, the exact totals.
        # Resultata before: sibling filtering reports size 1 and wall time 1020.
        results = [self.dive({0: [1, 2], 1: [], 2: []}, {0: 1, 1: 1, 2: 100}, (i,)) for i in (0, 1)]
        self.assertEqual([r[0] for r in results], [3, 3])
        self.assertEqual([r[1] for r in results], [0, 0])
        self.assertEqual([r[2] for r in results], [2, 2])
        self.assertEqual(sum(r[3] for r in results) / 2, 102)

    def test_unfinished_path_never_returns_a_complete_estimate(self):
        # Replicata: the root consumes the deadline before its child is expanded.
        # Expectata: an explicit timeout; a partial weighted count is not a sample.
        # Resultata before: the loop silently returns its partial count.
        with self.assertRaises(TimeoutError):
            self.dive({0: [1], 1: [2], 2: []}, {0: 1, 1: 1, 2: 1}, limit=5)

    def test_unsplittable_node_remains_open(self):
        # Replicata: a feasible root with no usable splitting modulus.
        # Expectata: its open-node estimate is 1, not an exclusion.
        self.assertEqual(self.dive({0: None}, {0: 2})[:3], (1, 1, 1))

    def test_weights_compound_at_unequal_depths(self):
        # Replicata: a root with one leaf and one three-leaf subtree; each node
        # costs 1. Enumerate all four paths, of probability 1/2,1/6,1/6,1/6.
        # Expectata: weighted mean size and CPU cost both equal the exact 6.
        children = {0: [1, 2], 1: [], 2: [3, 4, 5], 3: [], 4: [], 5: []}
        results = [self.dive(children, dict.fromkeys(children, 1), path)
                   for path in ((0,), (1, 0), (1, 1), (1, 2))]
        for field in (0, 3):
            self.assertEqual((3 * results[0][field] + sum(r[field] for r in results[1:])) / 6, 6)

    def test_empty_split_is_a_closed_terminal(self):
        # Replicata: an LP-feasible node whose lattice enumeration has no
        # children. Expectata: size 1, no OPEN leaf, and its CPU cost retained.
        clock = Clock()
        prover = mock.Mock()
        prover.close.side_effect = lambda pins: clock.advance(3)
        prover.split_choice.return_value = (1, [], [])
        with mock.patch.object(pp, 'Prover', return_value=prover), \
             mock.patch.object(pp.time, 'monotonic', side_effect=lambda: clock.wall), \
             mock.patch.object(pp.time, 'process_time', side_effect=lambda: clock.cpu):
            self.assertEqual(pp.dive((16, 3, (), 20, {1: (0,)}, 1, 100)), (1, 0, 1, 3))

    def estimate(self, samples, timed_out=False):
        jobs = []
        result = mock.Mock()
        result.get.side_effect = TimeoutError('batch deadline') if timed_out else None
        result.get.return_value = samples
        pool = mock.MagicMock()
        pool.__enter__.return_value = pool
        pool.map.return_value = ['phase1']
        def submit(function, cohort, chunksize=None):
            jobs.extend(cohort)
            return result
        pool.map_async.side_effect = submit
        roots = [{1: (i,)} for i in range(len(samples))]
        with mock.patch.object(pp, 'Pool', return_value=pool), \
             mock.patch.object(pp, 'chebyshev_nodes', return_value=()), \
             mock.patch.object(pp, 'workdir', return_value='/unused'), \
             mock.patch.object(pp, 'top_of_the_tree', return_value=(None, None, [])), \
             mock.patch.object(pp, 'load', return_value={'left': roots}), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            pp.estimate(16, 3, 2, 20)
        return jobs, output.getvalue(), result

    def test_fixed_cohort_covers_every_root_and_sums_weighted_costs(self):
        # Replicata: two roots with weighted costs 3 and 201 CPU seconds.
        # Expectata: both roots submitted before results, total 204 CPU seconds;
        # the sum does not depend on completion order or per-path node counts.
        samples = [(3, 0, 2, 3.0), (3, 0, 2, 201.0)]
        jobs, output, result = self.estimate(samples)
        self.assertEqual([j[4] for j in jobs], [{1: (0,)}, {1: (1,)}])
        result.get.assert_called_once_with(timeout=20)
        self.assertIn('204', output)

    def test_batch_timeout_and_open_leaf_refuse_a_runtime_projection(self):
        # Replicata: a censored batch, or a completed dive reaching an OPEN node.
        # Expectata: fail loudly instead of printing a proof-completion time.
        with self.assertRaises(TimeoutError):
            self.estimate([(1, 0, 1, 1)], timed_out=True)
        with self.assertRaises(AssertionError):
            self.estimate([(1, 1, 1, 1)])

    def test_empty_frontier_has_zero_remaining_work(self):
        # Replicata: phase 1 closes every root. Expectata: zero remaining work,
        # without random selection from an empty list or division by zero.
        jobs, output, result = self.estimate([])
        self.assertEqual(jobs, [])
        self.assertIn('0', output)


if __name__ == '__main__':
    unittest.main()
