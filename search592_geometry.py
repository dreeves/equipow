#!/usr/bin/env python3
"""Shared exact kernels and streamed fixed-orbit placements for symmetric witnesses.

A cursor [k,j] identifies prefix k in an affine permutation and completion j
in its compatible last-orbit bucket. It contains all scheduling state.
The construction follows scratch/lower24-design/batch1/go560/go560f.py;
pruned empty results establish no exclusion.
"""
from copy import deepcopy
from itertools import combinations, accumulate
from math import comb, gcd, prod
import hashlib
import json
import random
import time

import numpy as np
import sympy as sp
from fpylll import (IntegerMatrix, LLL, BKZ, GSO, Enumeration, EnumerationError,
                   EvaluatorStrategy, FPLLL)
from join720 import recenter, working_precision
from lattice288 import valid
from overnight_v5 import gbinom

SHAPE = (.3, 1.5, 1.)
SOURCES = ('search592_geometry.py', 'join720.py', 'lattice288.py',
           'overnight_v5.py', 'mstar.py', 'certbb.py', 'width.py')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def shape_vector(d):
    floor, alpha, beta = SHAPE
    curve = [max(floor, min(1., beta * (1 - i / d) ** alpha)) for i in range(d)]
    curve[0] = 1.
    assert all(0 < x <= 1 for x in curve)
    assert all(a >= b for a, b in zip(curve, curve[1:]))
    return curve


def candidate_rows(profile):
    n, order = profile['n'], profile['order']
    half = n // 2
    rows = [([gbinom(p - half, k) + gbinom(n - 1 - p - half, k)
              for p in range(half)], 0) for k in range(order)]
    for modulus, D in [[profile['modulus'], profile['D']]] + profile['extra']:
        assert type(modulus) is int and modulus > 0 and len(D) == modulus
        assert all(type(d) is int for d in D)
        assert all(D[r] == D[(n - 1 - r) % modulus] for r in range(modulus))
        rows.extend(([int(p % modulus == r) + int((n - 1 - p) % modulus == r)
                      for p in range(half)], D[r])
                    for r in range(modulus) if r <= (n - 1 - r) % modulus)
    return rows


def column_lattice(A):
    r, h = len(A), len(A[0])
    B = IntegerMatrix.from_matrix([[A[k][p] for k in range(r)] for p in range(h)])
    LLL.reduction(B)
    nonzero = [list(B[i]) for i in range(h) if any(B[i])]
    assert len(nonzero) == r
    C = sp.Matrix(nonzero).T
    det = int(C.det())
    assert det != 0
    adj = C.inv() * det
    assert all(x.q == 1 for x in adj)
    return [[int(x) for x in row] for row in adj.tolist()], det


def short_particular(A, b):
    """An exact particular solution from the archived augmented embedding."""
    r, h = len(A), len(A[0])
    scale = 2 ** (40 + max(abs(a) for row in A for a in row).bit_length() // 4)
    rows = [[int(i == j) for j in range(h)] + [0]
            + [scale * A[k][i] for k in range(r)] for i in range(h)]
    rows.append([0] * h + [1] + [-scale * v for v in b])
    B = IntegerMatrix.from_matrix(rows)
    LLL.reduction(B)
    candidates = [row for row in (list(B[i]) for i in range(B.nrows))
                  if not any(row[h + 1:]) and abs(row[h]) == 1]
    assert candidates
    row = candidates[0]
    y = [int(x * row[h]) for x in row[:h]]
    assert all(sum(a * x for a, x in zip(arow, y)) == bi for arow, bi in zip(A, b))
    return y


class Instance:
    """One profile, one shared reduced basis, and exact affine integer lifts."""
    def __init__(self, profile, seed=6, slice_index=2, nslices=4):
        self.profile = deepcopy(profile)
        self.n, self.order = profile['n'], profile['order']
        assert type(self.n) is int and self.n > 0 and self.n % 2 == 0
        assert type(self.order) is int and self.order > 0 and self.order % 2 == 0
        assert type(seed) is int and seed >= 0
        assert type(slice_index) is int and type(nslices) is int and 0 <= slice_index < nslices
        self.seed, self.slice_index, self.nslices = seed, slice_index, nslices
        modulus, D = profile['modulus'], profile['D']
        assert type(modulus) is int and modulus > 0 and len(D) == modulus
        orbits = profile['orbits']
        assert len({tuple(o['residues']) for o in orbits}) == len(orbits)
        assert sorted(p for o in orbits for p in o['positions']) == list(range(self.n // 2))
        for orbit in orbits:
            r, s = orbit['residues']
            ps, plus = orbit['positions'], orbit['plus']
            assert type(r) is int and type(s) is int and 0 <= r <= s < modulus
            assert s == (self.n - 1 - r) % modulus
            assert ps == [p for p in range(self.n // 2) if p % modulus in (r, s)]
            assert type(plus) is int and 0 <= plus <= len(ps)
            assert D[r] == D[s] == (1 + int(r == s)) * (2 * plus - len(ps))
        lookup = {tuple(o['residues']): o for o in orbits}
        selected = [lookup[tuple(pair)] for pair in profile['fixed_orbits']]
        assert selected and len({tuple(o['residues']) for o in selected}) == len(selected)
        self.const = {p: 2 * int(o['plus'] != 0) - 1 for o in selected
                      if o['plus'] in (0, len(o['positions'])) for p in o['positions']}
        self.corbits = [(o['positions'], o['plus']) for o in selected
                        if 0 < o['plus'] < len(o['positions'])]
        assert self.corbits
        self.qpairs = [p for ps, plus in self.corbits for p in ps]
        fixed = set(self.const) | set(self.qpairs)
        self.free = [p for p in range(self.n // 2) if p not in fixed]
        self.h = len(self.free)
        allrows = candidate_rows(profile)
        Araw = sp.Matrix([[cf[p] for p in self.free] for cf, rhs in allrows])
        keep = list(Araw.T.rref()[1])
        self.A = [[int(x) for x in Araw.row(i)] for i in keep]
        self.r = len(self.A)
        assert 0 < self.r < self.h
        rows = [allrows[i] for i in keep]
        self.G = [[cf[p] for p in self.qpairs] for cf, rhs in rows]
        numerators = [rhs - sum(cf[p] * v for p, v in self.const.items())
                      + sum(cf[p] for p in self.qpairs) + sum(arow)
                      for (cf, rhs), arow in zip(rows, self.A)]
        assert all(x % 2 == 0 for x in numerators)
        self.b0 = [x // 2 for x in numerators]
        self.check_relations(allrows, Araw)
        self.adj, self.det = column_lattice(self.A)
        self.congruence()
        self.tables()
        self.multiplier = int(self.P * .6180339887) | 1
        while gcd(self.multiplier, self.P) != 1:
            self.multiplier += 2
        self.offset = 7919 % self.P
        reference = self.next_case([slice_index, 0])
        assert reference is not None
        self.uref = self.u_of(reference['case']['choices'])
        self.lifts()
        self.gram_inverse = (sp.Matrix(self.A) * sp.Matrix(self.A).T).inv()
        self.reduce_basis()

    def check_relations(self, rows, Araw):
        """Discarded rows agree for every allowed fixed-orbit placement."""
        A = sp.Matrix(self.A)
        coefficients = Araw * A.T * (A * A.T).inv()
        assert coefficients * A == Araw
        Graw = sp.Matrix([[cf[p] for p in self.qpairs] for cf, rhs in rows])
        raw0 = sp.Matrix([sp.Rational(rhs - sum(cf[p] * v for p, v in self.const.items())
                                      + sum(cf[p] for p in self.qpairs) + sum(Araw.row(i)), 2)
                          for i, (cf, rhs) in enumerate(rows)])
        residual = Graw - coefficients * sp.Matrix(self.G)
        constant = raw0 - coefficients * sp.Matrix(self.b0)
        starts = list(accumulate([0] + [len(ps) for ps, plus in self.corbits]))
        for i in range(len(rows)):
            assert all(residual[i, q] == residual[i, starts[o]]
                       for o, (ps, plus) in enumerate(self.corbits)
                       for q in range(starts[o], starts[o + 1]))
            assert constant[i] == sum(residual[i, starts[o]] * plus
                                      for o, (ps, plus) in enumerate(self.corbits))

    def b_of(self, u):
        return [b - sum(g * x for g, x in zip(row, u)) for b, row in zip(self.b0, self.G)]

    def consistent(self, u):
        b = self.b_of(u)
        return all(sum(a * x for a, x in zip(row, b)) % self.det == 0 for row in self.adj)

    def congruence(self):
        T = [[sum(a * self.G[k][q] for k, a in enumerate(row))
              for q in range(len(self.qpairs))] for row in self.adj]
        beta = [sum(a * b for a, b in zip(row, self.b0)) for row in self.adj]
        starts = list(accumulate([0] + [len(ps) for ps, plus in self.corbits]))
        W, mods, target = [], [], []
        for row, bi in zip(T, beta):
            differences = [row[q] - row[starts[o]] for o, (ps, plus) in enumerate(self.corbits)
                           for q in range(starts[o], starts[o + 1])]
            g = gcd(self.det, *differences)
            constant = bi - sum(row[starts[o]] * plus for o, (ps, plus) in enumerate(self.corbits))
            assert constant % g == 0
            modulus = abs(self.det) // g
            if modulus > 1:
                W.append([(x // g) % modulus for x in differences])
                mods.append(modulus)
                target.append((constant // g) % modulus)
        assert max(mods, default=1) < 2 ** 30
        assert len(self.qpairs) * max(mods, default=1) < 2 ** 62
        self.W = np.array(W, dtype=np.int64).reshape(len(W), len(self.qpairs))
        self.mods, self.target = np.array(mods, dtype=np.int64), np.array(target, dtype=np.int64)

    def tables(self):
        self.choices, self.contrib = [], []
        start = 0
        for ps, plus in self.corbits:
            assert comb(len(ps), plus) <= 10000
            choices = [list(c) for c in combinations(range(start, start + len(ps)), plus)]
            U = np.zeros((len(choices), len(self.qpairs)), dtype=np.int64)
            for j, c in enumerate(choices):
                U[j, c] = 1
            self.choices.append(choices)
            self.contrib.append((U @ self.W.T) % self.mods)
            start += len(ps)
        self.radix = [len(c) for c in self.choices[:-1]]
        self.P = prod(self.radix)
        self.buckets = {}
        for j, row in enumerate(self.contrib[-1]):
            self.buckets.setdefault(tuple(int(x) for x in row), []).append(j)

    def prefix(self, x):
        out = []
        for radix in self.radix:
            out.append(x % radix)
            x //= radix
        assert x == 0
        return out

    def completions(self, x):
        prefix = self.prefix(x)
        total = sum((self.contrib[o][c] for o, c in enumerate(prefix)),
                    np.zeros(len(self.mods), dtype=np.int64)) % self.mods
        need = tuple(int(x) for x in (self.target - total) % self.mods)
        return [prefix + [j] for j in self.buckets.get(need, [])]

    def next_case(self, cursor):
        assert type(cursor) is list and len(cursor) == 2
        assert all(type(x) is int and x >= 0 for x in cursor)
        k, j = cursor
        assert k % self.nslices == self.slice_index
        while k < self.P:
            prefix = (self.multiplier * k + self.offset) % self.P
            completions = self.completions(prefix)
            assert j == 0 or j < len(completions)
            if completions:
                case = dict(prefix=prefix, choices=completions[j], cursor=[k, j])
                step, offset = divmod(j + 1, len(completions))
                return dict(case=case, next_cursor=[k + self.nslices * step, offset])
            k += self.nslices
        return None

    def u_of(self, cfg):
        assert len(cfg) == len(self.choices)
        assert all(type(j) is int and 0 <= j < len(c) for j, c in zip(cfg, self.choices))
        u = [0] * len(self.qpairs)
        for o, j in enumerate(cfg):
            for q in self.choices[o][j]:
                u[q] = 1
        return u

    def lifts(self):
        """The same scaled kernel/lift embedding as the historical control."""
        h, nq = self.h, len(self.qpairs)
        starts = list(accumulate([0] + [len(ps) for ps, plus in self.corbits]))
        S = [[int(starts[o] <= q < starts[o + 1]) for q in range(nq)]
             for o in range(len(self.corbits))]
        constraints = [a + g for a, g in zip(self.A, self.G)] + [[0] * h + row for row in S]
        weight = 2 ** 24
        bits = max(abs(x) for row in constraints for x in row).bit_length()
        scale = 2 ** (24 + 40 + bits // 4)
        rows = [[int(i == j) * weight ** int(i >= h) for j in range(h + nq)]
                + [scale * row[i] for row in constraints] for i in range(h + nq)]
        B = IntegerMatrix.from_matrix(rows)
        LLL.reduction(B)
        zero = [row for row in (list(B[i]) for i in range(B.nrows)) if not any(row[h + nq:])]
        self.K = [row[:h] for row in zero if not any(row[h:h + nq])]
        lifts = [row for row in zero if any(row[h:h + nq])]
        assert len(self.K) == h - self.r and len(lifts) == nq - len(S)
        assert all(x % weight == 0 for row in lifts for x in row[h:h + nq])
        Y = [row[:h] for row in lifts]
        L = [[x // weight for x in row[h:h + nq]] for row in lifts]
        assert all(sum(a * x for a, x in zip(arow, k)) == 0 for arow in self.A for k in self.K)
        assert all(sum(a * x for a, x in zip(arow, y)) + sum(g * v for g, v in zip(grow, du)) == 0
                   for y, du in zip(Y, L) for arow, grow in zip(self.A, self.G))
        assert all(sum(a * x for a, x in zip(srow, du)) == 0 for srow in S for du in L)
        assert max(abs(x) for row in Y for x in row) < 2 ** 40
        assert max(abs(x) for row in L for x in row) < 2 ** 20
        self.Y, self.L = np.array(Y, dtype=np.int64), np.array(L, dtype=np.int64)
        self.Lpinv = np.linalg.pinv(self.L.astype(float))
        self.yref = np.array(short_particular(self.A, self.b_of(self.uref)), dtype=np.int64)

    def particular(self, u):
        du = np.array(u, dtype=np.int64) - np.array(self.uref, dtype=np.int64)
        coefficients = np.rint(du @ self.Lpinv).astype(np.int64)
        bound = max(abs(int(c)) for c in coefficients) * len(coefficients)
        assert bound * max(abs(int(x)) for x in self.L.flat) < 2 ** 62
        assert np.array_equal(coefficients @ self.L, du)
        assert bound * max(abs(int(x)) for x in self.Y.flat) + max(abs(int(x)) for x in self.yref) < 2 ** 62
        y = [int(x) for x in self.yref + coefficients @ self.Y]
        assert all(sum(a * x for a, x in zip(row, y)) == b for row, b in zip(self.A, self.b_of(u)))
        return y

    def reduce_basis(self):
        FPLLL.set_random_seed(self.seed)
        rng = random.Random(self.seed)
        rows = [[2 * x for x in row] for row in self.K]
        rng.shuffle(rows)
        for i in range(len(rows)):
            j = rng.randrange(len(rows))
            if i != j:
                sign = rng.choice((1, -1))
                rows[i] = [a + sign * b for a, b in zip(rows[i], rows[j])]
        self.B = IntegerMatrix.from_matrix(rows)
        LLL.reduction(self.B)
        BKZ.reduction(self.B, BKZ.Param(block_size=min(20, self.B.nrows), max_loops=8,
                                       flags=BKZ.AUTO_ABORT | BKZ.MAX_LOOPS))
        self.basis = [list(self.B[i]) for i in range(self.B.nrows)]
        assert all(x % 2 == 0 for row in self.basis for x in row)
        assert sp.Matrix(self.A) * sp.Matrix(self.basis).T == sp.zeros(self.r, len(self.basis))

    def summary(self):
        return dict(n=self.n, order=self.order, seed=self.seed, slice_index=self.slice_index,
                    nslices=self.nslices, free=self.h, rows=self.r, dimension=len(self.basis),
                    prefixes=self.P, radices=self.radix, last_choices=len(self.choices[-1]),
                    multiplier=self.multiplier, offset=self.offset, shape=list(SHAPE),
                    profile_hash=digest(self.profile), basis_hash=digest(self.basis))

    def model(self, case):
        assert self.next_case(case['cursor'])['case'] == case
        u = self.u_of(case['choices'])
        assert self.consistent(u)
        y = self.particular(u)
        c = [2 * b - sum(row) for row, b in zip(self.A, self.b_of(u))]
        target = [2 * x - 1 for x in y]
        cv = sp.Matrix(c)
        perpendicular = (cv.T * self.gram_inverse * cv)[0]
        radius = self.h - perpendicular
        precision = working_precision(self.basis, target)
        M, target = recenter(self.B, target, perpendicular)
        assert sp.Matrix(self.A) * sp.Matrix(target) == cv
        assert all(type(x) is int and x % 2 for x in target)
        fixed = self.const | {p: 2 * u[q] - 1 for q, p in enumerate(self.qpairs)}
        return dict(n=self.n, order=self.order, A=self.A, c=c, free=self.free,
                    fixed=[[p, fixed[p]] for p in sorted(fixed)], basis=self.basis,
                    target=target, radius2=str(radius), precision=precision)

    def enumerate_case(self, case):
        prepared = self.model(case)
        radius = sp.Rational(prepared['radius2'])
        curve = shape_vector(len(self.basis))
        result = dict(outcome='empty', seed=self.seed, shape=list(SHAPE), curve=curve,
                      basis_hash=digest(self.basis), geometry_hash=digest(prepared),
                      radius2=str(radius), nodes=0, raw_nodes=0, node_levels=[],
                      enumeration_seconds=0.)
        if radius < 0:
            return result
        FPLLL.set_precision(prepared['precision'])
        M = GSO.Mat(self.B, float_type='mpfr')
        assert M.update_gso()
        target = prepared['target']
        tau = M.from_canonical([-x for x in target])
        enum = Enumeration(M, nr_solutions=1, strategy=EvaluatorStrategy.FIRST_N_SOLUTIONS)
        started = time.monotonic()
        try:
            solutions = enum.enumerate(0, len(self.basis), float(radius) + .5, 0,
                                       target=tau, pruning=curve)
        except EnumerationError as error:
            assert str(error) == 'No solution found.', str(error)
            solutions = []
        elapsed = time.monotonic() - started
        raw_nodes = enum.get_nodes()
        # An immediately pruned root can leave fplll's counter at unsigned -1.
        node_levels = [enum.get_nodes(i) for i in range(len(self.basis))]
        counts_valid = all(x != 2 ** 64 - 1 for x in node_levels)
        nodes = raw_nodes if counts_valid else None
        result.update(nodes=nodes, raw_nodes=raw_nodes, node_levels=node_levels,
                      enumeration_seconds=elapsed)
        for distance, coefficients in solutions:
            assert all(abs(x - round(x)) < 1e-6 for x in coefficients)
            v = self.B.multiply_left([round(x) for x in coefficients])
            signs = [x + y for x, y in zip(target, v)]
            assert all(type(x) is int and abs(x) == 1 for x in signs)
            assert all(sum(a * x for a, x in zip(row, signs)) == c for row, c in zip(self.A, prepared['c']))
            half = dict(prepared['fixed']) | dict(zip(self.free, signs))
            sequence = [half[p] for p in range(self.n // 2)]
            sequence += sequence[::-1]
            assert valid(sequence, self.order)
            assert all(sum(a * sequence[p] for p, a in enumerate(row)) == rhs
                       for row, rhs in candidate_rows(self.profile))
            result.update(outcome='witness', sequence=sequence)
        return result
