#!/usr/bin/env python3
"""A free set F at length n and order m: its rows (moments and pinned residue sums), its lattice, the congruences its coset imposes on the fixed signs."""
import time, math
from fractions import Fraction
from math import log2
import mpmath as mp
from fpylll import IntegerMatrix, LLL
from pinned_model import moment_col
from pinned_lattice import Lattice, kernel, bound_fn
import pinned_profiles
mp.mp.dps = 300


def pin_table(n, q, s, D):
    """Rows (per pair x, f(X = x) = a_x and f(X = -x) = s a_x) and targets for the residue sums mod q with the vector D (indexed by i mod q, X = 2i - n + 1)."""
    xs = list(range(1, n, 2))
    Q = 2 * q if q % 2 == 0 else q
    inv2 = None if q % 2 == 0 else pow(2, -1, q)
    def iclass(c): return ((c + n - 1) // 2) % q if q % 2 == 0 else ((c + n - 1) * inv2) % q
    seen, out = set(), []
    for c in sorted({x % Q for x in xs} | {(-x) % Q for x in xs}):
        if c in seen: continue
        seen |= {c, (-c) % Q}
        row = {}
        for x in xs:
            v = (1 if x % Q == c else 0) + (s if (-x) % Q == c else 0)
            if v: row[x] = v
        if not row: continue
        target = D[iclass(c)]
        if c == (-c) % Q:
            assert s == 1 and set(row.values()) == {2}
            row = {x: 1 for x in row}
            assert target % 2 == 0
            target //= 2
        out.append(dict(q=q, c=c, row=row, target=target))
    return out


def independent_rows(rows, prime=(1 << 61) - 1):
    """Indices of a maximal independent subset of integer rows (rank mod a large prime)."""
    basis, keep = [], []
    for idx, row in enumerate(rows):
        v = [a % prime for a in row]
        for piv, b in basis:
            if v[piv]:
                t = v[piv]
                v = [(a - t * c) % prime for a, c in zip(v, b)]
        piv = next((j for j, a in enumerate(v) if a), None)
        if piv is None: continue
        inv = pow(v[piv], -1, prime)
        basis.append((piv, [a * inv % prime for a in v])); keep.append(idx)
    return keep


def int_adj(M):
    """det and adjugate (M^-1 = adj/det, so that x M = v has x = v adj / det), by exact elimination."""
    n = len(M)
    A = [[Fraction(v) for v in row] + [Fraction(int(i == j)) for j in range(n)] for i, row in enumerate(M)]
    det = Fraction(1)
    for c in range(n):
        p = next(i for i in range(c, n) if A[i][c] != 0)
        if p != c: A[c], A[p] = A[p], A[c]; det = -det
        det *= A[c][c]
        inv = 1 / A[c][c]
        A[c] = [v * inv for v in A[c]]
        for i in range(n):
            if i != c and A[i][c] != 0:
                t = A[i][c]
                A[i] = [a - t * b for a, b in zip(A[i], A[c])]
    assert det.denominator == 1
    d = int(det)
    adj = [[A[i][n + j] * d for j in range(n)] for i in range(n)]
    assert all(v.denominator == 1 for row in adj for v in row)
    return d, [[int(v) for v in row] for row in adj]


def small_factors(N):
    out = {}
    for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]:
        while N % p == 0:
            out[p] = out.get(p, 0) + 1; N //= p
    if N > 1: out['rest'] = N
    return out


def default_profiles(n, m, qs, log=print):
    """The least-cost admissible vector mod each q."""
    s = 1 if m % 2 == 0 else -1
    out = []
    for q in qs:
        use, Dvec, good = pinned_profiles.enumerate_profiles(n, q, m, s)
        assert good, f'no admissible vector mod {q} at n = {n}, order {m}, symmetry {s}'
        out.append((q, Dvec(good[0][1])))
        log(f' profile mod {q}: {out[-1][1]}')
    return out


class Problem:
    """The rows on F, with the targets of the pins, the reduced kernel (self.I), the column lattice Lambda_F and the whitening of Sigma_F = A A^T."""
    def __init__(self, n, m, F, profiles, beta=20, log=print):
        self.n, self.m = n, m
        self.r, self.s = (m // 2, 1) if m % 2 == 0 else (m // 2, -1)
        self.xs = list(range(1, n, 2))
        self.F = list(F); Fset = set(F)
        self.Fx = [x for x in self.xs if x not in Fset]
        self.mom = {x: moment_col(x, self.r, self.s) for x in self.xs}
        self.pins = []
        for q, D in profiles: self.pins += pin_table(n, q, self.s, D)
        for p in self.pins:
            onF, onX = any(x in p['row'] for x in self.F), any(x in p['row'] for x in self.Fx)
            p['kind'] = 'shared' if onF and onX else ('F' if onF else 'X')
        self.hard = [p for p in self.pins if p['kind'] == 'X']       # rows only the fixed signs can meet
        Fvis = [p for p in self.pins if p['kind'] != 'X']
        A = [[self.mom[x][j] for x in self.F] for j in range(self.r)] + [[p['row'].get(x, 0) for x in self.F] for p in Fvis]
        keep = independent_rows(A)
        assert keep[:self.r] == list(range(self.r))
        vis = [(j, None) for j in range(self.r)] + [(None, p) for p in Fvis]
        self.vis = [vis[i] for i in keep]
        self.A = [A[i] for i in keep]
        self.rho = len(self.A)
        f = len(self.F)
        t0 = time.time()
        self.I = Lattice(kernel(self.A, f), beta=beta)
        assert self.I.d == f - self.rho
        # the column lattice: a basis with its transform (each basis vector a combination U of the columns)
        big = 2 ** 200
        Ms = IntegerMatrix(f, self.rho + f)
        for i in range(f):
            for j in range(self.rho): Ms[i, j] = self.A[j][i] * big
            Ms[i, self.rho + i] = 1
        LLL.reduction(Ms, delta=0.99)
        basis, self.U = [], []
        for i in range(f):
            v = list(Ms[i])
            if any(v[:self.rho]):
                basis.append([w // big for w in v[:self.rho]]); self.U.append(v[self.rho:])
        assert len(basis) == self.rho
        self.det, self.adj = int_adj(basis)
        self.Sum = [sum(row) for row in self.A]
        Am = mp.matrix(self.A)
        S = Am * Am.T
        self.Linv = mp.inverse(mp.cholesky(S))
        self.log2Eceil = f + self.rho - (self.rho / 2) * log2(2 * math.pi) - float(mp.log(mp.det(S), 2)) / 2 + float(mp.log(abs(mp.mpf(self.det)), 2))
        log(f'Problem n={n} m={m} f={f} rho={self.rho} d={self.I.d} |Fx|={len(self.Fx)} hard rows={len(self.hard)} det(Lambda_F) factors {small_factors(abs(self.det))} log2Eceil={self.log2Eceil:.1f} setup {time.time()-t0:.1f}s')

    def vis_col(self, x):
        return [self.mom[x][j] if p is None else p['row'].get(x, 0) for j, p in self.vis]

    def vis_target(self):
        return [0 if p is None else p['target'] for j, p in self.vis]

    def coset_base(self, tau):
        """tau: the exact target of F on the visible rows.  An odd vector a1 with A a1 = tau, or None if tau is not in the coset."""
        v = [t + s for t, s in zip(tau, self.Sum)]
        if any(w % 2 for w in v): return None
        v = [w // 2 for w in v]
        w = [sum(v[i] * self.adj[i][j] for i in range(self.rho)) for j in range(self.rho)]
        if any(t % self.det for t in w): return None
        w = [t // self.det for t in w]
        return [2 * sum(w[k] * self.U[k][i] for k in range(self.rho)) - 1 for i in range(self.I.f)]


def valp(x, p, E):
    if x == 0: return E
    k = 0
    while x % p == 0: x //= p; k += 1
    return k


def echelon_rows(adj, det, p, n):
    """Rows (vec, e): x is in the lattice with inverse adj/det, at p, iff vec . x = 0 mod p^e for every row."""
    d = abs(det); E = 0
    while d % p == 0: d //= p; E += 1
    if E == 0: return []
    mod = p ** E
    uinv = pow((det // p ** E) % mod, -1, mod)
    rows = [[adj[i][j] * uinv % mod for i in range(n)] for j in range(n)]
    cols_left = list(range(n)); out = []
    while rows:
        best = None
        for i, r in enumerate(rows):
            for c in cols_left:
                v = valp(r[c], p, E)
                if best is None or v < best[0]: best = (v, i, c)
        if best is None or best[0] >= E: break
        a, i, c = best
        piv = rows.pop(i)
        pinv = pow(piv[c] // p ** a, -1, mod)
        piv = [x * pinv % mod for x in piv]
        for r in rows:
            t = r[c] // p ** a
            if t:
                for j in range(n): r[j] = (r[j] - t * piv[j]) % mod
        cols_left.remove(c)
        assert all(x % p ** a == 0 for x in piv), 'pivot valuation'
        out.append(([x // p ** a for x in piv], E - a))
    return out


class Congruence:
    """The condition v in Lambda_F as rows psi . v = 0 mod p^e, per prime p dividing det(Lambda_F).  Rows constant on Fx are checked once (they depend only
    on the profile); the others are what the fixed signs must satisfy."""
    def __init__(self, P):
        self.rows_all = []
        for p in small_factors(abs(P.det)):
            assert p != 'rest', 'det has a large prime factor'
            self.rows_all += [(p, vec, e) for vec, e in echelon_rows(P.adj, P.det, p, P.rho)]

    def split(self, Fx_cols, v0):
        self.rows = []
        for p, vec, e in self.rows_all:
            mod = p ** e
            vals = [sum(a * b for a, b in zip(vec, col)) % mod for col in Fx_cols]
            g = min(valp(w, p, e) for w in vals)
            c0 = sum(a * b for a, b in zip(vec, v0)) % mod
            if g >= e:
                assert c0 == 0, f'profile inconsistent at prime {p}: constant row is {c0} mod {mod}'
                continue
            assert c0 % p ** g == 0, f'profile inconsistent at prime {p}: target {c0} not divisible by {p}^{g}'
            self.rows.append((p, vec, e, g))
        self.bits = sum((e - g) * log2(p) for p, vec, e, g in self.rows)

    def apply(self, v):
        out = []
        for p, vec, e, g in self.rows:
            w = sum(a * b for a, b in zip(vec, v)) % p ** e
            assert w % p ** g == 0
            out.append(w // p ** g)
        return out

    def moduli(self):
        return [p ** (e - g) for p, vec, e, g in self.rows]


def exact_order(f):
    k = 0
    while sum(a * i ** k for i, a in enumerate(f)) == 0: k += 1
    return k


def sequence(n, s, a):
    f = [0] * n
    for x, v in a.items():
        f[(x + n - 1) // 2] = v
        f[(-x + n - 1) // 2] = s * v
    assert all(v in (-1, 1) for v in f)
    return f


def hexcode(f, n):
    """The page's code of f: the left half's bits, 1 = +1; f's sign chosen so that f_0 = +1."""
    bits = ''.join('1' if v == f[0] else '0' for v in f[:n // 2])
    return format(int(bits, 2), '0%dX' % (len(bits) // 4))
