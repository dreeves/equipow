# prof.py -- residue-class profiles that a +-1 sequence of order >= k must have.
#
# Jargon (defined once, used everywhere in this directory):
#   profile mod m of a +-1 sequence a_0..a_{n-1}: the vector S in Z^m with
#     S_r = sum of a_i over i = r (mod m).  "Class r" means {i : i = r mod m};
#     its size is n_r.
#   allowed profiles A(n,k,m): the profiles S with |S_r| <= n_r, S_r = n_r
#     (mod 2), and S in the lattice L(m,k) below.
#
# Theorem (why every solution's profile is allowed).  Let f(x) = sum a_i x^i.
# "Order >= k" means (x-1)^k divides f, i.e. f = (x-1)^k g with g in Z[x]
# (division by a monic integer polynomial stays in Z[x]).  Reducing modulo
# x^m - 1, the profile polynomial F(x) = sum_r S_r x^r = f mod (x^m - 1) equals
# (x-1)^k g mod (x^m - 1) = sum_t g'_t [(x-1)^k x^t mod (x^m - 1)] with g'
# the integer vector g mod (x^m - 1).  So S lies in L(m,k), the Z-span of the
# m vectors (x-1)^k x^t mod (x^m - 1), t = 0..m-1.  The bounds and parities
# hold because S_r is a sum of n_r terms +-1.  So S is in A(n,k,m).
#
# allowed() enumerates A(n,k,m) through a Hermite normal form of L(m,k);
# member_q() is an independent membership test (Gaussian elimination over Q)
# used by the quals to check allowed() against brute force over the box.
import sys, itertools
from fractions import Fraction
from math import comb

def xm1k(k):
    """coefficients of (x-1)^k, lowest degree first"""
    c = [1]
    for _ in range(k):
        c = [(c[i - 1] if i > 0 else 0) - (c[i] if i < len(c) else 0) for i in range(len(c) + 1)]
    return c

def generators(m, k):
    base = xm1k(k)
    rows = []
    for t in range(m):
        r = [0] * m
        for i, x in enumerate(base): r[(i + t) % m] += x
        rows.append(r)
    return rows

def hnf(rows):
    """Row-style Hermite normal form over Z by unimodular row operations.
    Returns (H, piv): H in echelon form with positive pivots H[i][piv[i]] and
    entries above each pivot reduced into [0, pivot)."""
    A = [list(r) for r in rows]
    m = len(A[0])
    out, piv = [], []
    for col in range(m):
        while True:
            nz = [r for r in A if r[col] != 0]
            if len(nz) <= 1: break
            p = min(nz, key=lambda r: abs(r[col]))
            for r in nz:
                if r is not p:
                    q = r[col] // p[col]
                    for c in range(m): r[c] -= q * p[c]
        nz = [r for r in A if r[col] != 0]
        if not nz: continue
        p = nz[0]
        A = [r for r in A if r is not p]
        if p[col] < 0: p = [-x for x in p]
        out.append(p); piv.append(col)
    assert all(all(x == 0 for x in r) for r in A)          # nothing left over
    for i in range(len(out)):
        for j in range(i):
            q = out[j][piv[i]] // out[i][piv[i]]
            if q: out[j] = [a - q * b for a, b in zip(out[j], out[i])]
    return out, piv

def reduce_hnf(v, H, piv):
    """residual of v after peeling off the echelon rows; zero iff v in span"""
    v = list(v)
    for row, c in zip(H, piv):
        if v[c] % row[c]: return None
        q = v[c] // row[c]
        v = [a - q * b for a, b in zip(v, row)]
    return v

_LAT = {}
def lattice(m, k):
    if (m, k) not in _LAT:
        gens = generators(m, k)
        H, piv = hnf(gens)
        # the echelon rows span exactly the generators' lattice: each generator
        # peels to zero (span(H) contains gens) and H came from gens by
        # unimodular row operations (span(gens) contains H)
        for g in gens: assert reduce_hnf(g, H, piv) == [0] * m
        _LAT[(m, k)] = (H, piv)
    return _LAT[(m, k)]

def sizes(n, m): return [len(range(r, n, m)) for r in range(m)]

def allowed(n, k, m):
    """all S in L(m,k) with |S_r| <= n_r and S_r = n_r mod 2, as tuples"""
    H, piv = lattice(m, k)
    nr = sizes(n, m)
    rowof = {c: i for i, c in enumerate(piv)}
    out, S = [], [0] * m
    def rec(r, resid):
        if r == m:
            out.append(tuple(S)); return
        for s in range(-nr[r], nr[r] + 1, 2):
            v = s - resid[r]
            if r in rowof:
                h = H[rowof[r]]
                if v % h[r]: continue
                q = v // h[r]
                new = [resid[t] + q * h[t] if t > r else resid[t] for t in range(m)]
            else:
                if v != 0: continue
                new = resid
            S[r] = s
            rec(r + 1, new)
    rec(0, [0] * m)
    for S in out: assert reduce_hnf(S, H, piv) == [0] * m
    return out

def box(n, m):
    nr = sizes(n, m)
    return itertools.product(*[range(-x, x + 1, 2) for x in nr])

_MQ = {}
def _mq_setup(m, k):
    # columns: generators t = 0..m-2 (generator m-1 dropped: the kernel of
    # g -> (x-1)^k g mod (x^m-1) is the line through (1,...,1), so an integer
    # solution can be shifted to have g_{m-1} = 0 and is then unique)
    gens = generators(m, k)
    M = [[Fraction(gens[t][r]) for t in range(m - 1)] + [Fraction(int(r == c)) for c in range(m)] for r in range(m)]
    rows, cols = m, m - 1
    pr = 0
    for c in range(cols):
        p = next(i for i in range(pr, rows) if M[i][c] != 0)
        M[pr], M[p] = M[p], M[pr]
        inv = 1 / M[pr][c]
        M[pr] = [x * inv for x in M[pr]]
        for i in range(rows):
            if i != pr and M[i][c] != 0:
                f = M[i][c]
                M[i] = [a - f * b for a, b in zip(M[i], M[pr])]
        pr += 1
    assert pr == m - 1
    E = [row[cols:] for row in M]          # g = E[:m-1] S, consistency E[m-1] S = 0
    return E

def member_q(S, k):
    m = len(S)
    if (m, k) not in _MQ: _MQ[(m, k)] = _mq_setup(m, k)
    E = _MQ[(m, k)]
    if sum(e * s for e, s in zip(E[m - 1], S)) != 0: return False
    return all(sum(e * s for e, s in zip(E[i], S)).denominator == 1 for i in range(m - 1))

def profile(s, m):
    S = [0] * m
    for i, ch in enumerate(s): S[i % m] += 1 if ch == '+' else -1
    return tuple(S)

def write(n, k, m, path, rows=None):
    rows = allowed(n, k, m) if rows is None else rows
    with open(path, 'w') as f:
        f.write(f'{m} {len(rows)}\n')
        for S in rows: f.write(' '.join(map(str, S)) + '\n')
    return rows

if __name__ == '__main__':
    n, k = int(sys.argv[1]), int(sys.argv[2])
    for m in map(int, sys.argv[3:]):
        A = allowed(n, k, m)
        tot = sum(__import__('math').prod(comb(x, (x + s) // 2) for s, x in zip(S, sizes(n, m))) for S in A)
        # TODO: one line per modulus; says the modulus, how many profiles are allowed, and log2 of how many +-1 sequences have an allowed profile (none when no profile is allowed)
        print(f'Claude: "m={m}: {len(A)} allowed profiles, log2(sequences with an allowed profile) = {__import__("math").log2(tot) if tot else None}"')
