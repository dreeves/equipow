#!/usr/bin/env python3
"""Local-limit model of the number of sign vectors on a free set F: the preflight of the pinned search.

Pairs (x, -x) with x odd positive.  s=+1 symmetric (order m=2r), s=-1 antisymmetric (order m=2r+1).
Moment rows use the integer-valued unimodular basis C(u+j,2j) (s=+1) or (2u+1)C(u+j,2j)/(2j+1) (s=-1), u=(x-1)/2,
so that a contiguous block has column lattice Z^r.
log2 E = f + rho - (rho/2) log2(2 pi) - (1/2) log2 det(A A^T) + log2 covol(column lattice).
"""
import math, sys
from math import comb, log2, pi
import numpy as np
from fpylll import IntegerMatrix, LLL
import mpmath as mp
mp.mp.dps = 400

def moment_col(x, r, s):
    u = (x - 1) // 2
    out = []
    for j in range(r):
        c = comb(u + j, 2 * j)
        if s == -1:
            v = (2 * u + 1) * c
            assert v % (2 * j + 1) == 0
            c = v // (2 * j + 1)
        out.append(c)
    return out

def pin_rows(xs, q, s):
    """Rows of class sums of X mod q (q odd) or of X mod 2q (q a power of 2, classes of i mod q)."""
    Q = 2 * q if q % 2 == 0 else q
    seen, rows = set(), []
    classes = sorted({x % Q for x in xs} | {(-x) % Q for x in xs})
    for c in classes:
        if c in seen: continue
        seen |= {c, (-c) % Q}
        row = []
        for x in xs:
            v = 0
            if x % Q == c: v += 1
            if (-x) % Q == c: v += s
            row.append(v)
        if any(row):
            if c == (-c) % Q:
                assert all(v in (0, 2) for v in row), (q, c)
                row = [v // 2 for v in row]
            rows.append(row)
    return rows

def int_rank_basis(cols):
    B = IntegerMatrix.from_matrix(cols)
    LLL.reduction(B)
    return [list(B[i]) for i in range(B.nrows) if any(B[i])]

def log2_covol(basis):
    """log2 sqrt(det(B B^T)) of a full-row-rank integer matrix."""
    M = mp.matrix(basis)
    G = M * M.T
    return float(mp.log(mp.det(G), 2)) / 2

def log2E(xs, r, s, pins=()):
    A = [moment_col(x, r, s) for x in xs]              # columns, one per pair
    extra = []
    for q in pins: extra += pin_rows(xs, q, s)
    cols = [A[i] + [row[i] for row in extra] for i in range(len(xs))]
    basis = int_rank_basis(cols)
    rho = len(basis)
    # keep independent rows only, to compute det(A A^T) on the span
    M = mp.matrix(cols)                                # f x (r+s)
    G = M.T * M
    # det on the span: use the basis: covol(Lambda) known; sqrt det Sigma on the span via Q = Sigma restricted
    B = mp.matrix(basis)                               # rho x (r+s)
    # coefficients of the columns in the basis of Lambda: integer matrix C (f x rho) with cols = C B
    BBt = B * B.T
    C = M * B.T * mp.inverse(BBt)
    S = C.T * C                                        # Sigma in lattice coordinates: covol there is 1
    logdet = float(mp.log(mp.det(S), 2))
    f = len(xs)
    return f + rho - (rho / 2) * log2(2 * pi) - logdet / 2, f - rho, rho

def block(f): return [2 * u + 1 for u in range(f)]

if __name__ == '__main__':
    print('no pins: smallest f with log2E>=0, and values')
    for m in range(9, 17):
        r, s = (m // 2, 1) if m % 2 == 0 else (m // 2, -1)
        lo = None
        for f in range(r + 2, 500, 2):
            e, d, rho = log2E(block(f), r, s)
            if e >= 0: lo = (f, round(e, 1), d); break
        print(f'm={m:2d} r={r} s={s:+d} f_min={lo}')
