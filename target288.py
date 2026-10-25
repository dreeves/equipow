"""Exact validation and reuse of the earlier 288:10 witness-search cases.

The stored lattice is checked to have the full real kernel span, which fixes
the exact perpendicular distance. This is preparation for a heuristic witness
search, not an exclusion proof or a claim to cover every symmetric profile.
"""
from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path

import numpy as np
import sympy as sp

import lattice288


ROOT = Path(__file__).resolve().parent
PREPARED = ROOT / '.lattice288_prepared.json'
SOURCES = ('lattice288.py', 'overnight_v5.py', 'certbb.py')


def source_hash():
    return sha256(b''.join((ROOT / name).read_bytes() for name in SOURCES)).hexdigest()


def independent(rows):
    """A square integer minor invertible modulo 65521 is nonsingular over Q."""
    prime = 65521
    a = np.array([[int(t) % prime for t in row] for row in rows], dtype=np.int64)
    assert a.shape[0] == a.shape[1]
    for j in range(len(a)):
        candidates = np.flatnonzero(a[j:, j])
        assert len(candidates)
        p = j + int(candidates[0])
        a[[j, p]] = a[[p, j]]
        factors = a[j + 1:, j] * pow(int(a[j, j]), -1, prime) % prime
        a[j + 1:] = (a[j + 1:] - factors[:, None] * a[j]) % prime


def target_cases():
    return checked(json.loads(PREPARED.read_text()))


def checked(prepared):
    """Check the saved source identity, every exact coset, and every radius."""
    assert set(prepared) == {'code', 'basis', 'free', 'fixed', 'cases'}
    assert prepared['code'] == source_hash()
    free, fixed, basis, cases = (prepared[k] for k in ('free', 'fixed', 'basis', 'cases'))
    assert fixed == list(range(1, 144, 5))
    assert free == [p for p in range(144) if p not in fixed]
    assert len(cases) == 2736 and len(basis) == 105
    assert all(len(row) == 115 and all(type(x) is int and x % 2 == 0 for x in row) for row in basis)
    assert all(set(case) == {'profile', 'pair', 'target', 'radius'} for case in cases)
    assert all(len(case['profile']) == 7 and all(type(x) is int for x in case['profile']) for case in cases)
    assert all(len(case['pair']) == 2 and case['pair'] == sorted(set(case['pair']))
               and set(case['pair']) <= set(fixed) for case in cases)
    assert len({(tuple(case['profile']), tuple(case['pair'])) for case in cases}) == len(cases)
    assert all(len(case['target']) == 115 and all(type(x) is int and x % 2 == 1 for x in case['target'])
               for case in cases)

    rows = lattice288.moment_rows(288, 10) + sum((lattice288.count_rows(288, m) for m in (5, 3, 7)), [])
    A = [[row[p] for p in free] for row in rows]
    keep = list(sp.Matrix(A).T.rref()[1])
    assert len(keep) == 10
    W = [A[i] for i in keep]
    matrix = np.array(A, dtype=object)
    assert not np.any(matrix @ np.array(basis, dtype=object).T)
    pivots = sp.Matrix(W).rref()[1]
    chart = [j for j in range(115) if j not in pivots]
    assert len(chart) == 105
    independent([[row[j] for j in chart] for row in basis])

    head = [sum(row) // 2 for row in rows[:5]] + [29, 4, 29, 41, 41] + [48] * 3
    assert all(sum(row) % 2 == 0 for row in rows[:5])
    rhs = [[2 * (t - sum(row[p] for p in case['pair'])) - sum(a)
            for row, a, t in zip(rows, A, head + case['profile'], strict=True)] for case in cases]
    assert np.array_equal(matrix @ np.array([case['target'] for case in cases], dtype=object).T,
                          np.array(rhs, dtype=object).T)
    signed = [[c[i] for i in keep] for c in rhs]
    gram = (sp.Matrix(W) * sp.Matrix(W).T).inv()
    den = lcm(*(x.q for x in gram))
    Q = np.array(den * gram, dtype=object)
    c = np.array(signed, dtype=object)
    norms = np.sum((c @ Q) * c, axis=1)
    radii = [Fraction(115 * den - int(cost), den) for cost in norms]
    assert all(r >= 0 and r == Fraction(case['radius']) for r, case in zip(radii, cases, strict=True))
    return [dict(n=288, order=10, free=free,
                 fixed=[[p, 2 * int(p in case['pair']) - 1] for p in fixed],
                 A=W, c=c, basis=basis, target=case['target'], radius2=str(radius))
            for case, c, radius in zip(cases, signed, radii, strict=True)]
