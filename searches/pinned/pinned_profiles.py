#!/usr/bin/env python3
"""Likely admissible residue vectors for (anti)symmetric sequences of length n and order m.

A class mod M is r = i mod M, D_r the sum of the signs over i = r (mod M), and mirroring takes r to n-1-r with D_mirror = s D_r.
f = (x-1)^m g over Z, and mod 2 f = (x+1)^(t-1) S^t for n = t u (t a power of 2, u odd, S = 1 + x + ... + x^(u-1)), so g = (x+1)^(t-1-m) S^t mod 2
and D lies in rep + 2 L(M, m), rep = (x-1)^m h, h = (x+1)^(t-1-m) S^t mod (2, x^M - 1): the quotient-parity condition of AGENTS.md's 480 notes, here
for every M.  The search for likely vectors is Fincke-Pohst in the orbit coordinates, weighted by 1/pairs.
"""
import sys, math
from math import lgamma, log
import numpy as np
from fpylll import IntegerMatrix, LLL
from pinned_lattice import split_embedded


def sizes(n, M): return [len(range(r, n, M)) for r in range(M)]


def orbits(n, M):
    """Mirror orbits (r, r'), r <= r' = n-1-r mod M."""
    return [(r, (n - 1 - r) % M) for r in range(M) if r <= (n - 1 - r) % M]


def gens(M, m):
    """Generators of L(M, m): coefficient vectors of x^k (x-1)^m mod x^M - 1."""
    poly = [1]
    for _ in range(m): poly = [a - b for a, b in zip([0] + poly, poly + [0])]
    G = []
    for k in range(M):
        v = [0] * M
        for t, c in enumerate(poly): v[(t + k) % M] += c
        G.append(v)
    return G


def polymul_mod(a, b, M):
    out = [0] * M
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                if y: out[(i + j) % M] += x * y
    return out


def polypow_mod(a, e, M):
    r = [1] + [0] * (M - 1)
    while e:
        if e & 1: r = polymul_mod(r, a, M)
        a = polymul_mod(a, a, M)
        e >>= 1
    return r


def representative(n, M, m):
    """rep = (x-1)^m h with h reduced mod (2, x^M - 1): only h mod 2 matters, since 2 (x-1)^m Z[x] lies in 2 L(M, m)."""
    t = n & -n; u = n // t
    assert m <= t - 1, 'order beyond the 2-adic budget'
    def mulmod2(a, b): return [v & 1 for v in polymul_mod(a, b, M)]
    def powmod2(a, e):
        r = [1] + [0] * (M - 1)
        while e:
            if e & 1: r = mulmod2(r, a)
            a = mulmod2(a, a)
            e >>= 1
        return r
    Sm = [0] * M
    for i in range(u): Sm[i % M] ^= 1
    lin = [0] * M
    lin[0] ^= 1; lin[1 % M] ^= 1                       # x + 1 reduced mod x^M - 1
    h = mulmod2(powmod2(lin, t - 1 - m), powmod2(Sm, t))
    minus = [0] * M
    minus[0] += -1; minus[1 % M] += 1                  # x - 1
    return polymul_mod(polypow_mod(minus, m, M), h, M)


def affine_lattice(n, M, m, s):
    """Solutions e (orbit coordinates) of T e - 2 G g = rep: a particular e0 (None if none) and a basis of the homogeneous lattice in e."""
    use = [o for o in orbits(n, M) if not (s == -1 and o[0] == o[1])]
    def Dvec(e):
        D = [0] * M
        for (r, t), v in zip(use, e):
            if r == t: D[r] = v
            else: D[r] = v; D[t] = s * v
        return D
    k = len(use)
    T = [Dvec([int(i == j) for j in range(k)]) for i in range(k)]
    G = gens(M, m)
    rep = representative(n, M, m)
    ncol = k + M
    big = max(max(abs(v) for row in G for v in row), max(abs(v) for v in rep), 1)
    N = 2 ** (big.bit_length() + 90)
    A = IntegerMatrix(ncol + 1, ncol + 1 + M)
    for i in range(k):
        A[i, i] = 1
        for r in range(M): A[i, ncol + 1 + r] = N * T[i][r]
    for j in range(M):
        A[k + j, k + j] = 1
        for r in range(M): A[k + j, ncol + 1 + r] = -2 * N * G[j][r]
    A[ncol, ncol] = 1
    for r in range(M): A[ncol, ncol + 1 + r] = -N * rep[r]
    LLL.reduction(A, delta=0.99)
    zero = [list(A[i]) for i in range(A.nrows) if not any(list(A[i])[ncol + 1:])]
    hom, p = split_embedded(zero, ncol)
    if p is None: return use, Dvec, None, None
    hom = [v[:k] for v in hom if any(v[:k])]
    if not hom: return use, Dvec, p[:k], []
    Em = IntegerMatrix.from_matrix(hom)
    LLL.reduction(Em, delta=0.99)
    return use, Dvec, p[:k], [list(Em[i]) for i in range(Em.nrows) if any(Em[i])]


def enumerate_profiles(n, M, m, s, maxout=2000, slack=8.0):
    """Admissible vectors of least cost (sum e^2 / pairs), least first, as (use, Dvec, [(cost, e), ...])."""
    use, Dvec, rep, sub = affine_lattice(n, M, m, s)
    if rep is None: return use, Dvec, []
    sz = sizes(n, M)
    if not sub:
        D = Dvec(rep)
        ok = all(abs(D[r]) <= sz[r] and (D[r] - sz[r]) % 2 == 0 for r in range(M))
        return use, Dvec, ([(0.0, rep)] if ok else [])
    wt = []
    for (r, t) in use:
        pairs = sz[r] if r != t else sz[r] // 2
        wt.append(1.0 / (pairs if r != t else 4 * pairs))
    w = np.sqrt(np.array(wt))
    d = len(sub)
    Bf = np.array(sub, dtype=float) * w
    rf = np.array(rep, dtype=float) * w
    Q = np.zeros_like(Bf); rr = np.zeros(d); mu = np.zeros((d, d))
    for i in range(d):
        v = Bf[i].copy()
        for j in range(i):
            mu[i, j] = (Bf[i] @ Q[j]) / rr[j]
            v -= mu[i, j] * Q[j]
        Q[i] = v; rr[i] = v @ v
    tau = np.array([(rf @ Q[i]) / rr[i] for i in range(d)])
    subo = np.array(sub, dtype=np.int64); repo = np.array(rep, dtype=np.int64)
    results = []
    def try_bound(R2):
        results.clear()
        x = np.zeros(d, dtype=np.int64)
        def rec(i, part):
            if len(results) >= maxout * 3: return
            c = -(tau[i] + sum(x[l] * mu[l, i] for l in range(i + 1, d)))
            rad = math.sqrt(max(R2 - part, 0) / rr[i])
            for v in range(math.ceil(c - rad), math.floor(c + rad) + 1):
                p = part + (v - c) ** 2 * rr[i]
                if p > R2: continue
                x[i] = v
                if i == 0: results.append((p, [int(t) for t in repo + x @ subo]))
                else: rec(i - 1, p)
            x[i] = 0
        rec(d - 1, 0.0)
    def collect():
        good = []
        for p, e in results:
            D = Dvec(e)
            if all(abs(D[r]) <= sz[r] and (D[r] - sz[r]) % 2 == 0 for r in range(M)): good.append((p, e))
        return good
    R2 = 0.25; good = []
    while True:                                         # the smallest bound that admits a vector: the true minimum
        try_bound(R2)
        good = collect()
        if good or R2 > 40000: break
        R2 *= 1.15
    if good:
        try_bound(min(p for p, e in good) + slack)
        more = collect()
        if len(more) >= len(good): good = more
    good.sort(key=lambda t: t[0])
    return use, Dvec, good[:maxout]


def in_coset(n, M, m, s, D):
    """Is the residue vector D, of symmetry s, in rep + 2 L(M, m)?  A sequence of length n, order >= m and symmetry s must have this."""
    use, Dvec, rep, sub = affine_lattice(n, M, m, s)
    e = [D[r] for r, t in use]
    assert Dvec(e) == list(D), 'not of symmetry s'
    if rep is None: return False
    diff = [a - b for a, b in zip(e, rep)]
    if not any(diff): return True
    if not sub: return False
    rows = sub + [diff]
    A = IntegerMatrix.from_matrix(rows)
    LLL.reduction(A, delta=0.99)
    rank = sum(1 for i in range(A.nrows) if any(A[i]))
    if rank > len(sub): return False                    # outside the span
    # exact membership by Hermite-style elimination on the basis
    M_ = [list(v) for v in sub]
    x = list(diff)
    col = 0
    for row in range(len(M_)):
        while col < len(x):
            piv = [r for r in range(row, len(M_)) if M_[r][col]]
            if piv: break
            if x[col]: return False
            col += 1
        if col == len(x): break
        while True:
            piv = [r for r in range(row, len(M_)) if M_[r][col]]
            piv.sort(key=lambda r: abs(M_[r][col]))
            M_[row], M_[piv[0]] = M_[piv[0]], M_[row]
            rest = [r for r in range(row + 1, len(M_)) if M_[r][col]]
            if not rest: break
            for r in rest:
                q = M_[r][col] // M_[row][col]
                M_[r] = [a - q * b for a, b in zip(M_[r], M_[row])]
        if x[col] % M_[row][col]: return False
        q = x[col] // M_[row][col]
        x = [a - q * b for a, b in zip(x, M_[row])]
        col += 1
    return not any(x)


if __name__ == '__main__':
    n, m = int(sys.argv[1]), int(sys.argv[2])
    s = 1 if m % 2 == 0 else -1
    for M in [int(q) for q in sys.argv[3].split(',')]:
        use, Dvec, good = enumerate_profiles(n, M, m, s)
        print(f'n={n} m={m} M={M}: {len(good)} vectors')
        for p, e in good[:3]: print(f'   cost {p:7.2f} D={Dvec(e)}')
