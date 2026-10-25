#!/usr/bin/env python3
"""Exact symmetric witness models and randomized, pruned lattice attempts.

Fixed coordinates are JSON-safe [position, sign] pairs in the first half.
An empty attempt discards possible solutions and establishes no exclusion.
"""
from math import gcd
import random

from fpylll import (IntegerMatrix, LLL, BKZ, Enumeration, EnumerationError,
                   EvaluatorStrategy, FPLLL)
import sympy as sp
import mstar
import overnight_v5 as ov
from lattice288 import IntegerSystem, moment_rows, count_rows, valid
from join720 import recenter, pruning_curve

SEED = 20261024


def model(n, order, fixed):
    """Independent moment equations on the unfixed half-sign coordinates."""
    assert type(n) is int and n > 0 and n % 2 == 0
    assert type(order) is int and order > 0 and order % 2 == 0
    assert type(fixed) is list and all(type(pair) is list and len(pair) == 2
                                     for pair in fixed)
    assert all(type(p) is int and 0 <= p < n // 2 and a in (-1, 1)
               for p, a in fixed)
    pins = dict(fixed)
    assert len(pins) == len(fixed)
    free = [p for p in range(n // 2) if p not in pins]
    rows = moment_rows(n, order)
    A = [[row[p] for p in free] for row in rows]
    c = [-sum(row[p] * a for p, a in fixed) for row in rows]
    assert sp.Matrix(A).rank() == len(A) < len(free)
    return dict(n=n, order=order, free=free, fixed=[list(pair) for pair in fixed], A=A, c=c)


def residue_cases(model, modulus):
    """Every necessary residue vector compatible with the affine sign model."""
    n, order = model['n'], model['order']
    rows = count_rows(n, modulus)
    W = [[row[p] for p in model['free']] for row in rows]
    fixed = [sum(row[p] * a for p, a in model['fixed']) for row in rows]
    span = [sum(map(abs, row)) for row in W]
    step = [max(1, 2 * gcd(*row)) for row in W]
    profiles = mstar.residue_vectors(n, modulus, order, None,
                                    mstar.Budget(1000000), 'natural')
    rhs = [list(model['c']) + [d - f for d, f in zip(D, fixed)] for D in profiles
           if all(abs(d - f) <= S and (d - f - S) % g == 0
                  for d, f, S, g in zip(D, fixed, span, step))]
    A = [list(row) for row in model['A']] + W
    keep = list(sp.Matrix(A).T.rref()[1])
    exact = ov.ExactSystem(A)
    # Integer solvability also checks every relation among discarded rows.
    assert all((c + sum(row)) % 2 == 0 for cs in rhs for row, c in zip(A, cs))
    cases = [dict(model, A=[A[i] for i in keep], c=[cs[i] for i in keep])
             for cs in rhs
             if exact.solvable([(c + sum(row)) // 2 for row, c in zip(A, cs)])]
    assert cases, (n, order, modulus)
    return cases


def calibration_models():
    """Derive every symmetric 240:10 case modulo 3, 5, and 7, without hints."""
    cases = [model(240, 10, [])]
    for modulus in (3, 5, 7):
        cases = [child for parent in cases for child in residue_cases(parent, modulus)]
    return cases


def prepare_models(models):
    """One saturated integer kernel and exact coset/radius for every RHS."""
    assert models
    A = models[0]['A']
    assert all(m['A'] == A for m in models)
    system = IntegerSystem(A)
    B = IntegerMatrix.from_matrix([[2 * a for a in row] for row in system.kernel])
    LLL.reduction(B)
    basis = [list(B[i]) for i in range(B.nrows)]
    assert sp.Matrix(A) * sp.Matrix(basis).T == sp.zeros(len(A), len(basis))
    prepared = []
    for m in models:
        c, free, fixed = m['c'], m['free'], dict(m['fixed'])
        assert len(free) == system.A.cols and len(c) == len(A)
        assert set(free).isdisjoint(fixed) and len(fixed) == len(m['fixed'])
        assert set(free) | set(fixed) == set(range(m['n'] // 2))
        assert all(a in (-1, 1) for a in fixed.values())
        assert all((v + sum(row)) % 2 == 0 for row, v in zip(A, c))
        b = [(v + sum(row)) // 2 for row, v in zip(A, c)]
        target = [2 * a - 1 for a in system.particular(b)]
        radius = system.radius2(c)
        assert 0 <= radius <= len(free)
        _, target = recenter(B, target, len(free) - radius)
        assert sp.Matrix(A) * sp.Matrix(target) == sp.Matrix(c)
        assert all(a % 2 for a in target)
        prepared.append(dict(m, basis=basis, target=target, radius2=str(radius)))
    return prepared


def enumerate_job(prepared, attempt):
    """One randomized basis and first-solution attempt, verified in integers."""
    assert type(attempt) is int and attempt >= 0
    seed = SEED + attempt
    FPLLL.set_random_seed(seed)
    FPLLL.set_precision(212)
    rng = random.Random(seed)
    rows = [list(row) for row in prepared['basis']]
    rng.shuffle(rows)
    d = len(rows)
    assert d >= 2
    for i in range(d):
        j = (i + 1 + rng.randrange(d - 1)) % d
        sign = rng.choice((-1, 1))
        rows[i] = [a + sign * b for a, b in zip(rows[i], rows[j])]
    B = IntegerMatrix.from_matrix(rows)
    LLL.reduction(B)
    BKZ.reduction(B, BKZ.Param(block_size=min(20, d), max_loops=8,
                              flags=BKZ.AUTO_ABORT | BKZ.MAX_LOOPS))
    free, fixed = prepared['free'], dict(prepared['fixed'])
    assert len(free) == len(prepared['target']) == B.ncols
    assert len(set(free)) == len(free) and len(fixed) == len(prepared['fixed'])
    assert set(free).isdisjoint(fixed)
    assert set(free) | set(fixed) == set(range(prepared['n'] // 2))
    assert all(a in (-1, 1) for a in fixed.values())
    radius2 = sp.Rational(prepared['radius2'])
    assert 0 <= radius2 <= len(free)
    M, target = recenter(B, prepared['target'], len(free) - radius2)
    tau = M.from_canonical([-a for a in target])
    radius = float(radius2) + 0.5
    pruning = pruning_curve(M, tau, radius)
    enum = Enumeration(M, nr_solutions=1, strategy=EvaluatorStrategy.FIRST_N_SOLUTIONS)
    try:
        solutions = enum.enumerate(0, d, radius, 0, target=tau, pruning=pruning)
    except EnumerationError as error:
        assert str(error) == 'No solution found.', str(error)
        solutions = []
    answer = dict(outcome='empty', nodes=enum.get_nodes())
    for distance, coefficients in solutions:
        assert all(abs(a - round(a)) < 1e-6 for a in coefficients)
        v = B.multiply_left([round(a) for a in coefficients])
        signs = [a + b for a, b in zip(target, v)]
        assert all(abs(a) == 1 for a in signs), (distance, signs)
        assert sp.Matrix(prepared['A']) * sp.Matrix(signs) == sp.Matrix(prepared['c'])
        half = fixed | dict(zip(free, signs))
        sequence = [half[p] for p in range(prepared['n'] // 2)]
        sequence += sequence[::-1]
        assert valid(sequence, prepared['order'])
        answer.update(outcome='witness', sequence=sequence)
    return answer
