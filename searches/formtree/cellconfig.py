#!/usr/bin/env python3
"""What the prover needs to know about a cell n:m, for pex.write_config: each modulus's lattice and coset, and its list of forms.  None of it is trusted: the checkers recompute every grid from the lattice themselves.
Needs numpy, sympy (through engine/residues.py) and fpylll.  Moved here 2026-11-06 from Claude's scratch (adapt.py, filt2.py, dualforms.py), only the parts the configuration uses.
    python3 -B cellconfig.py n:m        writes pex_n_m_<moduli>.cfg here, for the moduli of run.sh"""
import math, os, sys
from fractions import Fraction
from functools import lru_cache
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'engine'))
from residues import basis, SWEEPS


def is2(M): return M & (M - 1) == 0
def size(n, M, r): return len(range(r, n, M))


def val2(n):
    t = 0
    while n % 2 == 0: n //= 2; t += 1
    return t


def polymul(a, b, M, mod=None):
    out = [0] * M
    for i, u in enumerate(a):
        if u:
            for j, v in enumerate(b):
                if v: out[(i + j) % M] += u * v
    return [c % mod for c in out] if mod else out


def polypow(a, e, M, mod=None):
    r = [1] + [0] * (M - 1)
    for _ in range(e): r = polymul(r, a, M, mod)
    return r


def rep(n, M, m, plus):
    """(x-1)^m (x+1)^plus h, h = S / ((x-1)^m (x+1)^plus) mod 2 reduced mod x^M - 1, S = (x^n - 1)/(x - 1) = (x+1)^(2^t-1) Psi^(2^t) mod 2: the parity coset's representative, M a power of 2."""
    t = val2(n); u = n >> t
    assert 2 ** t - 1 >= m + plus, (n, m, plus)
    lin = [1, 1] + [0] * (M - 2) if M > 2 else [2 % 2, 0]
    P = [0] * M
    for i in range(u): P[(i << t) % M] ^= 1
    h = polymul(polypow(lin, 2 ** t - 1 - m - plus, M, 2), P, M, 2)
    minus = [-1, 1] + [0] * (M - 2)
    return polymul(polymul(polypow(minus, m, M), polypow([1, 1] + [0] * (M - 2), plus, M), M), h, M)


def problem(n, m, M):
    """A basis of L(M) in the digits order of the classes, its pivots, that order, and rep(M) (0 for odd M, whose parity the prover handles itself)."""
    plus = n < 2 ** m
    B, piv = basis(M, m, 'digits', plus)
    order = SWEEPS['digits'](M)
    R = rep(n, M, m, plus) if is2(M) else [0] * M
    return B, piv, order, R


@lru_cache(maxsize=None)
def dual_forms(n, m, M, extra=True):
    """Short vectors of the dual of L(M): forms the lattice puts on a coarse grid, by LLL on the exact dual basis, with sums and differences of pairs; shortest first."""
    import numpy as np
    from fpylll import IntegerMatrix, LLL
    B, piv, order, R = problem(n, m, M)
    nb = len(piv)
    if nb == 0: return np.zeros((0, M), dtype=np.int64)
    Bm = [[Fraction(B[i][c]) for i in range(M)] for c in range(nb)]
    G = [[sum(a * b for a, b in zip(x, y)) for y in Bm] for x in Bm]
    A = [row[:] + [Fraction(int(i == j)) for j in range(nb)] for i, row in enumerate(G)]
    for c in range(nb):
        p = next(i for i in range(c, nb) if A[i][c] != 0); A[c], A[p] = A[p], A[c]
        iv = 1 / A[c][c]; A[c] = [v * iv for v in A[c]]
        for i in range(nb):
            if i != c and A[i][c] != 0:
                f = A[i][c]; A[i] = [a - f * b for a, b in zip(A[i], A[c])]
    Ginv = [row[nb:] for row in A]
    Dual = [[sum(Ginv[i][k] * Bm[k][j] for k in range(nb)) for j in range(M)] for i in range(nb)]
    den = 1
    for row in Dual:
        for v in row: den = den * v.denominator // math.gcd(den, v.denominator)
    I = IntegerMatrix(nb, M)
    for i in range(nb):
        for j in range(M): I[i, j] = int(Dual[i][j] * den)
    LLL.reduction(I, delta=0.99)
    rows = [[int(I[i, j]) for j in range(M)] for i in range(nb)]
    out = {}
    def add(v):
        g = 0
        for x in v: g = math.gcd(g, abs(int(x)))
        if g == 0: return
        v = tuple(x // g for x in v)
        s = next((1 if x > 0 else -1) for x in v if x)
        out[tuple(s * x for x in v)] = True
    for r in rows: add(r)
    if extra:
        for i in range(nb):
            for j in range(i + 1, nb):
                add([a + b for a, b in zip(rows[i], rows[j])]); add([a - b for a, b in zip(rows[i], rows[j])])
    return np.array(sorted(out, key=lambda v: sum(x * x for x in v)), dtype=np.int64)


if __name__ == '__main__':
    import pex
    n, m = map(int, sys.argv[1].split(':'))
    mods = [3, 4, 5, 7, 8, 9, 11, 13, 16, 17, 19, 23, 25, 27, 29, 31, 37]
    path = f'pex_{n}_{m}_{"_".join(map(str, mods))}.cfg'
    pex.write_config(n, m, mods, path)
    print(path)
