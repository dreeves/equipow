"""Quals for the sparse search on mirror pairs. Run with a Python that has OR-Tools."""
from itertools import combinations
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'searches' / 'sparseflips'))


def q_profiles():
    # Replicata: the alternating baseline at 33360 and the mod-seven endpoint proof.
    # Expectata: six distinct signed profiles, with these distances from the baseline.
    import sparseflips as f
    profiles = f.seven_profiles()
    baseline = (0, 0, 0, 0, 0, -1, 1)
    assert len(set(profiles)) == 6
    assert sorted(sum(abs(x-y) for x,y in zip(row, baseline)) for row in profiles) == [
        292, 296, 488, 488, 492, 492]


def q_model_equals_direct_moments():
    # Replicata: try every single flipped pair at 12:3 as the entire solver pool.
    # Expectata: the feasible pools are exactly those with zero ordinary moments.
    import sparseflips as f
    for (i,) in combinations(range(6), 1):
        word = [(-1)**j * (1-2*(j in (i,11-i))) for j in range(12)]
        result, flips, _ = f.solve(12, 3, [i], {}, 3)
        valid = all(sum(a*j**k for j,a in enumerate(word)) == 0 for k in range(3))
        assert (result == 'OPTIMAL') == valid, (i,result,valid)
        assert flips == ([i] if valid else [])


def q_published_control():
    # Replicata: BGPW Table 4's first 100 bits at 200:7, oriented at -1.
    # Expectata: recover the exact 18 flipped pairs when other positions stay alternating.
    # Altering one class sum must make that same pool infeasible.
    import sparseflips as f
    h = '9559B51655655553755459555A31ED24F651A6C0F'
    left = [2*int(x)-1 for x in format(int(h, 16), f'0{len(h)*4}b')[:100]]
    alignment = sum(a*(-1)**i for i,a in enumerate(left))
    assert abs(alignment) == 64
    left = [a * (alignment // abs(alignment)) for a in left]
    word = left + [-a for a in reversed(left)]
    flips = [i for i,a in enumerate(left) if a != (-1)**i]
    assert len(flips) == 18
    profile = [sum(word[r::7]) for r in range(7)]
    status, found, _ = f.solve(200, 7, flips, {7:profile}, 5)
    assert status == 'OPTIMAL' and found == flips
    assert f.verify(200, 7, found) == word
    profile[0] += 2
    assert f.solve(200, 7, flips, {7:profile}, 5)[0] == 'INFEASIBLE'
    # Now free every pair. Supply just the five class-sum profiles, with no position hints.
    profiles = {p:[sum(word[r::p]) for r in range(p)] for p in (3,5,7,11,13)}
    status, found, _ = f.solve(200, 7, list(range(100)), profiles, 60)
    assert status == 'OPTIMAL'
    recovered = f.verify(200, 7, found)
    assert all(sum(recovered[r::p]) == v for p,rows in profiles.items()
               for r,v in enumerate(rows))


def q_signed_carries():
    # Replicata: a dot product beyond CP-SAT's int64, with both signs and cancellation.
    # Expectata: every prescribed pair of bits satisfies exactly its integer target.
    import sparseflips as f
    weights = [2**105+259, -(2**105+517), 2**89-1, -(2**92-257)]
    for pair in combinations(range(4), 2):
        target = sum(weights[i] for i in pair)
        for delta in (-1, 0, 1):
            model = f.cp_model.CpModel()
            bits = [model.new_bool_var('') for i in weights]
            for i,b in enumerate(bits):
                model.add(b == int(i in pair))
            f.equation(model, bits, weights, target + delta, 2)
            solver = f.cp_model.CpSolver()
            solver.parameters.num_workers = 1
            expected = f.cp_model.INFEASIBLE if delta else f.cp_model.OPTIMAL
            assert solver.solve(model) == expected, (pair,delta)


if __name__ == '__main__':
    for q in (q_profiles, q_model_equals_direct_moments, q_published_control, q_signed_carries):
        q()
