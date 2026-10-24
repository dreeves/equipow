"""Scratch quals for exact reversal of existing B/L/W certificates."""
import unittest

import certbb
import focus
import reflection as reflect


def complete(equations, choice):
    state = focus.State(equations, (choice,))
    lp = certbb.Lp(equations, tuple(M for M, _ in choice))
    lp.set_counts(choice)
    proof = []
    while state.frontier and state.witness is None:
        value = focus.step(lp, equations, choice, *state.box())
        state.feed(dict(case=0, token=value))
        proof.append(value)
    return state, proof


class ReflectionQuals(unittest.TestCase):
    def test_both_cases_finish_in_the_unmodified_state(self):
        # Replicata: an impossible (20,5) case, with unequal mod-3 counts.
        # Expectata: its full proof and reflected proof close both cases exactly.
        # Resultata before implementation: reflection is unimplemented.
        equations = focus.moments(20, 5)
        source = ((3, (2, 4, 4)),)
        target = reflect.choice(equations, source)
        self.assertEqual(target, ((3, (4, 2, 4)),))
        original, proof = complete(equations, source)
        self.assertIsNone(original.witness)
        self.assertTrue(any(t[0] == 'B' for t in proof))
        reflected = [reflect.token(equations, source, t) for t in proof]
        state = focus.State(equations, (source, target))
        for value in proof:
            state.feed(dict(case=0, token=value))
        for value in reflected:
            state.feed(dict(case=1, token=value))
        self.assertEqual(state.completed, [0, 1])
        self.assertEqual(state.frontier, [])
        self.assertEqual([reflect.token(equations, target, t) for t in reflected], proof)

    def test_positive_control_reverses_the_exact_witness(self):
        # Replicata: concatenate two order-3 length-8 Thue-Morse sequences.
        # Expectata: reversal is accepted by the target case's exact State.
        # Resultata before implementation: reflection is unimplemented.
        equations = focus.moments(16, 3)
        x = [p.bit_count() % 2 for p in range(8)] * 2
        source = ((5, tuple(sum(x[r::5]) for r in range(5))),)
        target = reflect.choice(equations, source)
        state = focus.State(equations, (target,))
        value = reflect.token(equations, source, ('W', x))
        state.feed(dict(case=0, token=value))
        self.assertEqual(state.witness, x[::-1])
        self.assertEqual(reflect.token(equations, target, value), ('W', x))

    def test_production_rows_and_profiles_map_exactly(self):
        # Replicata: the current 672:13 rows and both retained count profiles.
        # Expectata: reversal preserves every equation, by explicit integer rows.
        # Resultata before implementation: reflection is unimplemented.
        equations = focus.moments(672, 13)
        source = ((2, (168, 168)), (3, (112, 112, 112)),
                  (5, (130, 5, 67, 67, 67)), (7, (48,) * 7), (4, (84,) * 4))
        target = source[:2] + ((5, (5, 130, 67, 67, 67)),) + source[3:]
        self.assertEqual(reflect.choice(equations, source), target)
        rows = certbb.node_rows(equations, source)
        other = certbb.node_rows(equations, target)
        for i, (row, rhs) in enumerate(rows):
            basis = [int(j == i) for j in range(len(rows))]
            transformed = reflect.token(equations, source, ('L', basis))[1]
            dense = [0] * equations.N
            beta = 0
            for (a, b), multiplier in zip(other, transformed):
                beta += multiplier * b
                for p, c in a:
                    dense[p] += multiplier * c
            expected = [0] * equations.N
            for p, c in row:
                expected[equations.N - 1 - p] = c
            self.assertEqual((dense, beta), (expected, rhs))

    def test_partial_box_and_frontier_reflect(self):
        # Replicata: a prefix ending with several open boxes.
        # Expectata: each target open box is precisely the source reversal.
        # Resultata before implementation: reflection is unimplemented.
        equations = focus.moments(20, 5)
        source = ((3, (2, 4, 4)),)
        a = focus.State(equations, (source,))
        b = focus.State(equations, (reflect.choice(equations, source),))
        for value in [('B', 0), ('B', 19), ('B', 1)]:
            a.feed(dict(case=0, token=value))
            b.feed(dict(case=0, token=reflect.token(equations, source, value)))
        self.assertEqual(b.frontier, [(0, reflect.path(equations, p)) for _, p in a.frontier])

    def test_bad_rows_fail_immediately(self):
        # Replicata: a non-reversible extra equation passed to the transformer.
        # Expectata: an assertion rejects it before it can manufacture a token.
        # Resultata before implementation: reflection is unimplemented.
        equations = certbb.Moments(((1, 1),), (1,), (((1, 0),), (0,)))
        with self.assertRaises(AssertionError):
            reflect.token(equations, (), ('L', [1, 0]))


if __name__ == '__main__':
    unittest.main()
