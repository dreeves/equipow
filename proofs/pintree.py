#!/usr/bin/env python3
"""Claude's exact check of a pin tree: a proof that no sequence of length n has order m.  Python's standard library only: integers, no floats, no solver.  python3 -B -I -S proofs/pintree.py FILE

The claim.  No signs a_p in {-1, 1}, p = 0, ..., n-1, have sum_p a_p p^k = 0 for k = 0, ..., m-1.

Suppose some do, and let F(x) = sum_p a_p x^p.  Then (x-1)^m divides F in Z[x].  If n < 2^m then F(-1) = 0 as well, since 2^m divides F(-1) and |F(-1)| <= n.  Put e = 1 then and e = 0 otherwise, so that
(x-1)^m (x+1)^e divides F.

Vocabulary.
  residue sums  D^(M)_r = sum_{p = r mod M} a_p, r = 0, ..., M-1: the coefficients of F mod x^M - 1.
  L(M)          { (x-1)^m (x+1)^e g mod x^M - 1 : g in Z[x] }, the residue lattice.
  pins          a set {M: D} of residue sums taken as given: a node of the tree, standing for the sequences with those residue sums.
  certificate   integer weights on the positions that show some pins impossible, or bound a residue sum under them: below.
  pin tree      a tree of pins, from none at the root, every leaf closed by a certificate: the proof.

What residue sums must satisfy, for any M = p^k:
  (a) D^(M) lies in L(M);
  (b) |D^(M)_r| <= size(M, r), the number of positions p = r mod M, and D^(M)_r = size(M, r) mod 2;
  (c) if P divides M, the sum of D^(M)_r over r = q mod P is D^(P)_q;
  (d) the parity coset: if M = 2^k, D^(M) lies in rep(M) + 2 L(M).  Every a_p is 1 mod 2, so F = S = (x^n - 1)/(x - 1) mod 2: mod 2 every sequence of length n is the same polynomial.  With n = 2^t u, u odd,
      S = (x+1)^(2^t - 1) Psi(x)^(2^t) mod 2, where Psi = (x^u - 1)/(x - 1), and Psi(x)^(2^t) = Psi(x^(2^t)) mod 2.  Write F = (x-1)^m (x+1)^e H with H in Z[x].  As F_2[x] is a domain, H = h mod 2, where
      h = (x+1)^(2^t - 1 - m - e) Psi(x^(2^t)).  Reducing mod x^M - 1, H = h + 2 H_1, with h now its 0/1 reduction.  So D^(M) = rep(M) + 2 (x-1)^m (x+1)^e H_1, with rep(M) = (x-1)^m (x+1)^e h.
vectors() lists every integer vector meeting (a) to (d) inside given bounds, by a walk down a triangular basis of L(M).

Certificates.  A certificate is (values, classes, T): a polynomial g of degree < m by its integer values at the m nodes that the file names, integer weights classes[M][r] on the classes of the moduli that effective(pins) gives, and a
positive integer T.  With w(p) = g(p) + sum_M classes[M][p mod M], every sequence of order >= m with the pins has
    sum_p w(p) a_p = K,  where K = sum_M sum_r classes[M][r] D^(M)_r,
since g has degree < m, so that sum_p g(p) a_p = 0.  Then:
  to close a node: |K| > sum_p |w(p)| contradicts |sum_p w(p) a_p| <= sum_p |w(p)|, so no sequence has the pins;
  to bound a residue sum at a further modulus M': for s = +-1, T s D^(M')_r = sum_p (T s 1_{p = r mod M'} - w(p)) a_p + K <= sum_p |T s 1_{p = r mod M'} - w(p)| + K.
All of it is multiplied through by Den, the common denominator of the Lagrange basis at the nodes, so that every number is an integer.

The tree.  A stream of tokens, depth first from the root.  ['L', c] closes the node with certificate c of the file's table.  ['S', M, bounds] splits it: every vector of vectors() at M, inside the class bounds that bounds proves
(a pair of table indices per class, lower then upper; None for only (b)), is a child in turn, and the tokens of each child follow.  A child is skipped when an image of it under the symmetries is closed already, as far down as sym_depth
pins: F -> -F and F -> x^(n-1) F(1/x) keep the order and act on pins as neg and rev below.  When the root closes with no tokens left, no sequence has order m, so m*(n) < m.

The file.  gzipped JSON: {"n", "m", "nodes", "sym_depth", "table": [[values, {M: weights}, T], ...], "tokens": [...]}.  searches/pintree/ makes these files, a floating-point LP suggesting the certificates; nothing here trusts it.
proofs/pintree_second.py is a second check of the same file that shares no code with this one.
"""
import gzip, json, sys
from functools import lru_cache
from math import gcd


def size(n, M, r): return len(range(r, n, M))


def prime_power(M):
    """(p, k) with M = p^k."""
    p = next(q for q in range(2, M + 1) if M % q == 0)
    k, x = 0, 1
    while x < M: x *= p; k += 1
    if x != M: raise ValueError(f'{M} is not a prime power')
    return p, k


def digits_order(M):
    """The classes mod M by their base-p digits, lowest first, so that a parent's classes are contiguous."""
    p, k = prime_power(M)
    return tuple(sorted(range(M), key=lambda r: [r // p ** i % p for i in range(k)]))


def polymul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, u in enumerate(a):
        for j, v in enumerate(b): out[i + j] += u * v
    return out


def reduced(poly, M):
    out = [0] * M
    for i, c in enumerate(poly): out[i % M] += c
    return out


def generator(m, e):
    """The coefficients of (x-1)^m (x+1)^e, lowest first."""
    g = [1]
    for _ in range(m): g = polymul(g, [-1, 1])
    for _ in range(e): g = polymul(g, [1, 1])
    return g


@lru_cache(maxsize=None)
def triangular(M, m, e):
    """A basis of L(M) in the coordinates of digits_order(M): vectors with increasing last nonzero coordinate (the pivot), positive there."""
    order = digits_order(M)
    g = reduced(generator(m, e), M)
    vs = [[g[(r - s) % M] for r in order] for s in range(M)]
    basis = []
    for c in reversed(range(M)):
        while True:
            live = [v for v in vs if v[c]]
            if len(live) <= 1: break
            pivot = min(live, key=lambda v: abs(v[c]))
            for v in live:
                if v is not pivot:
                    q = v[c] // pivot[c]
                    for i in range(M): v[i] -= q * pivot[i]
        live = [v for v in vs if v[c]]
        if live:
            v = live[0]
            vs = [w for w in vs if w is not v]
            basis.append((c, [-x for x in v] if v[c] < 0 else v))
    if any(any(v) for v in vs): raise ArithmeticError('the reduction lost a generator')
    basis.reverse()                # pivots increasing
    return tuple((c, tuple(v)) for c, v in basis)


def val2(n):
    t = 0
    while n % 2 == 0: n //= 2; t += 1
    return t


@lru_cache(maxsize=None)
def coset_rep(n, M, m, e):
    """rep(M) of (d), M a power of 2, in natural coordinates."""
    t = val2(n); u = n >> t
    if 2 ** t - 1 < m + e: raise ValueError('then the two lemma rules order m out at once')
    h = [1]
    for _ in range(2 ** t - 1 - m - e): h = [c % 2 for c in polymul(h, [1, 1])]
    h = reduced(h, M)
    psi = [0] * M
    for i in range(u): psi[(i << t) % M] ^= 1
    product = [c % 2 for c in reduced(polymul(h, psi), M)]
    return tuple(reduced(polymul(generator(m, e), product), M))


def parent_of(M, pins):
    """The largest pinned proper divisor of M, or None: for a prime power M, the same prime's nearest lower power."""
    c = [P for P in pins if P != M and M % P == 0]
    return max(c) if c else None


def vectors(n, m, M, pins, lo=None, hi=None, limit=None):
    """Every vector D meeting (a), (b), (c) for the pinned parent, and (d), with lo_r <= D_r <= hi_r, in increasing order."""
    e = 1 if n < 2 ** m else 0
    order = digits_order(M)
    p, _ = prime_power(M)
    sizes = [size(n, M, r) for r in order]
    lows = [-s for s in sizes] if lo is None else [max(-size(n, M, r), lo[r]) for r in order]
    highs = list(sizes) if hi is None else [min(size(n, M, r), hi[r]) for r in order]
    if any(l > h for l, h in zip(lows, highs)): return []
    mult, rep = (2, coset_rep(n, M, m, e)) if p == 2 else (1, (0,) * M)
    rep = [rep[r] for r in order]
    basis = triangular(M, m, e)
    P = parent_of(M, pins)
    W = pins[P] if P else (0,)
    P = P or 1
    cls = [r % P for r in order]
    room_lo, room_hi = [0] * M, [0] * M
    for i in range(M):
        for t in range(i):
            if cls[t] == cls[i]: room_lo[i] += lows[t]; room_hi[i] += highs[t]
    part, d, z, out = [0] * P, [0] * M, [0] * len(basis), []
    walked = [0]

    def down(i, j):
        walked[0] += 1
        if limit is not None and walked[0] > limit: raise OverflowError('the walk passed its limit')
        if i < 0:
            D = [0] * M
            for k, r in enumerate(order): D[r] = d[k]
            if any(part[q] != W[q] for q in range(P)): raise ArithmeticError('a parent sum is not met')
            out.append(tuple(D))
            return
        base = rep[i] + mult * sum(basis[c][1][i] * z[c] for c in range(j + 1, len(basis)))
        if j >= 0 and basis[j][0] == i:
            h = mult * basis[j][1][i]
            for t in range(-((base - lows[i]) // h), (highs[i] - base) // h + 1):
                z[j] = t
                place(i, j - 1, base + h * t)
            z[j] = 0
        else:
            place(i, j, base)

    def place(i, j, v):
        if not lows[i] <= v <= highs[i] or (v - sizes[i]) % 2: return
        q = cls[i]
        rest = W[q] - part[q] - v
        if not room_lo[i] <= rest <= room_hi[i]: return
        d[i] = v; part[q] += v
        down(i - 1, j)
        part[q] -= v

    down(M - 1, len(basis) - 1)
    return sorted(out)


def effective(pins):
    """The moduli whose classes the certificates weigh: a pinned modulus dividing another pinned one adds nothing, by (c)."""
    return tuple(M for M in sorted(pins) if not any(Q != M and Q % M == 0 for Q in pins))


@lru_cache(maxsize=None)
def lagrange(n, xs):
    """Den and the integers Den * L_j(p), for the Lagrange basis L_j at the m distinct integers xs (any such nodes will do: the proof file names them), p = 0, ..., n-1."""
    m = len(xs)
    if len(set(xs)) != m: raise ValueError('the nodes must be distinct')
    dens = []
    for j in range(m):
        d = 1
        for k in range(m):
            if k != j: d *= xs[j] - xs[k]
        dens.append(d)
    Den = 1
    for d in dens: Den = Den * abs(d) // gcd(Den, abs(d))
    table = []
    for p in range(n):
        row = []
        for j in range(m):
            num = 1
            for k in range(m):
                if k != j: num *= p - xs[k]
            q, rem = divmod(num * Den, dens[j])
            if rem: raise ArithmeticError('Den is not a common denominator')
            row.append(q)
        table.append(row)
    return Den, table


class Weights:
    """A certificate's w(p), multiplied by Den, once."""
    def __init__(self, n, xs, cert):
        values, classes, T = cert
        assert type(n) is int and n > 0
        assert xs and all(type(x) is int for x in xs)
        assert all(type(v) is int for v in values) and type(T) is int
        assert all(type(M) is str and M == str(int(M)) and int(M) > 0 for M in classes)
        assert all(len(c) == int(M) and all(type(v) is int for v in c) for M, c in classes.items())
        self.classes = {int(M): tuple(c) for M, c in classes.items()}
        self.T = T
        Den, table = lagrange(n, xs)
        self.Den = Den
        if len(values) != len(xs) or T <= 0: raise ValueError('a certificate needs a value per node and T > 0')
        self.w = []
        for p in range(n):
            v = sum(a * b for a, b in zip(table[p], values))
            for M, c in self.classes.items(): v += Den * c[p % M]
            self.w.append(v)
        self.total = sum(abs(v) for v in self.w)

    def K(self, pins):
        assert all(type(M) is int and M > 0 for M in pins)
        assert all(len(D) == M and all(type(d) is int for d in D) for M, D in pins.items())
        if sorted(self.classes) != list(effective(pins)): raise ValueError(f'a certificate on {sorted(self.classes)} for pins on {effective(pins)}')
        return sum(c * d for M, cs in self.classes.items() for c, d in zip(cs, pins[M]))

    def closes(self, pins):
        return abs(self.Den * self.K(pins)) > self.total

    def bound(self, pins, M, r, s):
        """The greatest integer that s * D^(M)_r can be under the pins, by this certificate."""
        assert all(type(x) is int for x in (M, r, s))
        assert M > 0 and 0 <= r < M and s in (-1, 1)
        total = 0
        for p, v in enumerate(self.w):
            total += abs(self.Den * self.T * s * (p % M == r) - v)
        return (total + self.Den * self.K(pins)) // (self.Den * self.T)


def neg(pins): return {M: tuple(-x for x in D) for M, D in pins.items()}
def rev(pins, n): return {M: tuple(D[(n - 1 - r) % M] for r in range(M)) for M, D in pins.items()}
def freeze(pins): return tuple(sorted(pins.items()))
def images(pins, n):
    r = rev(pins, n)
    return [freeze(pins), freeze(neg(pins)), freeze(r), freeze(neg(r))]


class Replay:
    """Replays the tokens of a proof, raising on anything that does not hold.  stats: what was checked."""
    def __init__(self, n, m, xs, table, tokens, sym_depth):
        assert type(n) is int and n > 0 and type(m) is int and m > 0
        assert type(sym_depth) is int and sym_depth >= 0
        assert all(type(x) is int for x in xs)
        if len(xs) != m: raise ValueError('a node per order')
        self.n, self.m, self.xs, self.table, self.sym_depth = n, m, tuple(xs), table, sym_depth
        self.tokens = iter(tokens)
        self.cache = {}
        self.closed = set()
        self.stats = {'closed by certificate': 0, 'splits': 0, 'skipped by symmetry': 0, 'vectors': 0, 'bounds': 0}

    def weights(self, c):
        assert type(c) is int and 0 <= c < len(self.table)
        if c not in self.cache: self.cache[c] = Weights(self.n, self.xs, self.table[c])
        return self.cache[c]

    def node(self, pins):
        token = next(self.tokens)
        if token[0] == 'L':
            if not self.weights(token[1]).closes(pins): raise ValueError(f'certificate {token[1]} does not close {pins}')
            self.stats['closed by certificate'] += 1
        elif token[0] == 'S':
            M, bounds = token[1], token[2]
            assert type(M) is int and M > 1
            if M in pins: raise ValueError(f'{M} is pinned already')
            prime_power(M)
            lo, hi = None, None
            if bounds is not None:
                if len(bounds) != M: raise ValueError('a bound per class')
                lo, hi = [0] * M, [0] * M
                for r, (cl, ch) in enumerate(bounds):
                    hi[r] = self.weights(ch).bound(pins, M, r, 1)
                    lo[r] = -self.weights(cl).bound(pins, M, r, -1)
                    self.stats['bounds'] += 2
            self.stats['splits'] += 1
            for v in vectors(self.n, self.m, M, pins, lo, hi):
                self.stats['vectors'] += 1
                child = {**pins, M: v}
                if len(child) <= self.sym_depth and any(i in self.closed for i in images(child, self.n)):
                    self.stats['skipped by symmetry'] += 1
                    continue
                self.node(child)
        else:
            raise ValueError(f'unknown token {token[0]}')
        if len(pins) <= self.sym_depth: self.closed.add(freeze(pins))

    def run(self):
        self.node({})
        if next(self.tokens, None) is not None: raise ValueError('tokens left over')
        if freeze({}) not in self.closed: raise ValueError('the root is not closed')
        return self.stats


def reject_number(value):
    raise ValueError


def verify(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f: data = json.load(f, parse_float=reject_number, parse_constant=reject_number)
    n, m = data['n'], data['m']
    sys.setrecursionlimit(100000)
    table = [(c[0], c[1], c[2]) for c in data['table']]
    stats = Replay(n, m, data['nodes'], table, data['tokens'], data['sym_depth']).run()
    return n, m, stats, len(table)


if __name__ == '__main__':
    n, m, stats, k = verify(sys.argv[1])
    print(f'Claude: "VERIFIED: no sequence of length {n} has order {m}.  {k} certificates in the table; {stats}"')
