#!/usr/bin/env python3
"""Freeze exact lattice geometry for a paired comparison of pruning curves.

Only the allowed squared-radius fractions change between paired attempts.
Empty results and timeouts establish no exclusion.
"""
from copy import deepcopy
import hashlib
import json
import random
import time

from fpylll import GSO, Enumeration, EnumerationError, EvaluatorStrategy
import search288_geometry as G
from join720 import working_precision


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def gso(frozen):
    """Reconstruct GSO at its original precision without changing the target."""
    G.FPLLL.set_precision(frozen['precision'])
    B = G.IntegerMatrix.from_matrix(frozen['basis'])
    M = GSO.Mat(B, float_type='mpfr')
    assert M.update_gso()
    tau = M.from_canonical([-a for a in frozen['target']])
    return M, tau, float(G.sp.Rational(frozen['radius2'])) + .5


def curve(frozen, width):
    """The two approved nested pruning curves, as squared-radius fractions."""
    assert type(width) in (int, float) and width in (0, .10)
    baseline = frozen['pruning']
    values = [width + (1 - width) * p for p in baseline]
    assert len(values) == len(frozen['basis']) and values[0] == 1.
    assert all(0 < p <= q <= 1 for p, q in zip(baseline, values))
    assert all(a >= b for a, b in zip(values, values[1:]))
    return values


def freeze(prepared, attempt):
    """Reproduce the prior kernel's randomized basis and affine recentering."""
    assert type(attempt) is int and attempt >= 0
    free, fixed = prepared['free'], dict(prepared['fixed'])
    assert len(set(free)) == len(free) and len(fixed) == len(prepared['fixed'])
    assert set(free).isdisjoint(fixed)
    assert set(free) | set(fixed) == set(range(prepared['n'] // 2))
    assert all(a in (-1, 1) for a in fixed.values())
    A, c = G.sp.Matrix(prepared['A']), G.sp.Matrix(prepared['c'])
    assert A.cols == len(free) == len(prepared['target'])
    assert A * G.sp.Matrix(prepared['target']) == c
    assert all(type(a) is int and a % 2 for a in prepared['target'])
    radius2 = G.sp.Rational(prepared['radius2'])
    assert 0 <= radius2 <= len(free)
    assert radius2 == len(free) - (c.T * (A * A.T).inv() * c)[0]

    seed = G.SEED + attempt
    G.FPLLL.set_random_seed(seed)
    G.FPLLL.set_precision(212)
    rng = random.Random(seed)
    rows = [list(row) for row in prepared['basis']]
    rng.shuffle(rows)
    d = len(rows)
    assert d >= 2
    for i in range(d):
        j = (i + 1 + rng.randrange(d - 1)) % d
        sign = rng.choice((-1, 1))
        rows[i] = [a + sign * b for a, b in zip(rows[i], rows[j])]
    B = G.IntegerMatrix.from_matrix(rows)
    G.LLL.reduction(B)
    G.BKZ.reduction(B, G.BKZ.Param(block_size=min(20, d), max_loops=8,
                                  flags=G.BKZ.AUTO_ABORT | G.BKZ.MAX_LOOPS))
    basis = [list(B[i]) for i in range(B.nrows)]
    assert all(type(a) is int and a % 2 == 0 for row in basis for a in row)
    assert A * G.sp.Matrix(basis).T == G.sp.zeros(A.rows, d)
    precision = working_precision(basis, prepared['target'])
    M, target = G.recenter(B, prepared['target'], len(free) - radius2)
    assert A * G.sp.Matrix(target) == c and all(a % 2 for a in target)
    tau = M.from_canonical([-a for a in target])
    pruning = G.pruning_curve(M, tau, float(radius2) + .5)
    frozen = dict(deepcopy(prepared), basis=basis, target=target,
                  radius2=str(radius2), attempt=attempt, seed=seed,
                  precision=precision, pruning=pruning, basis_hash=digest(basis))
    M, tau, radius = gso(frozen)
    assert G.pruning_curve(M, tau, radius) == pruning
    frozen['geometry_hash'] = digest(frozen)
    return frozen


def enumerate_frozen(frozen, width):
    """Search an unchanged coset/basis with one of the two approved curves."""
    identity = dict(frozen)
    expected = identity.pop('geometry_hash')
    assert digest(identity) == expected
    assert digest(frozen['basis']) == frozen['basis_hash']
    pruning = curve(frozen, width)
    M, tau, radius = gso(frozen)
    assert G.pruning_curve(M, tau, radius) == frozen['pruning']
    enum = Enumeration(M, nr_solutions=1, strategy=EvaluatorStrategy.FIRST_N_SOLUTIONS)
    started = time.monotonic()
    try:
        solutions = enum.enumerate(0, M.d, radius, 0, target=tau, pruning=pruning)
    except EnumerationError as error:
        assert str(error) == 'No solution found.', str(error)
        solutions = []
    elapsed = time.monotonic() - started
    answer = dict(outcome='empty', nodes=enum.get_nodes(), enumeration_seconds=elapsed,
                  width=width, curve=pruning, basis_hash=frozen['basis_hash'],
                  geometry_hash=frozen['geometry_hash'], seed=frozen['seed'],
                  seed_attempt=frozen['attempt'])
    for distance, coefficients in solutions:
        assert len(coefficients) == M.d
        assert all(abs(a - round(a)) < 1e-6 for a in coefficients)
        v = M.B.multiply_left([round(a) for a in coefficients])
        signs = [a + b for a, b in zip(frozen['target'], v)]
        assert all(abs(a) == 1 for a in signs), (distance, signs)
        assert G.sp.Matrix(frozen['A']) * G.sp.Matrix(signs) == G.sp.Matrix(frozen['c'])
        half = dict(frozen['fixed']) | dict(zip(frozen['free'], signs))
        sequence = [half[p] for p in range(frozen['n'] // 2)]
        sequence += sequence[::-1]
        assert G.valid(sequence, frozen['order'])
        answer.update(outcome='witness', sequence=sequence)
    return answer
