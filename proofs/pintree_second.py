#!/usr/bin/env python3
"""Claude's second check of a pin tree, sharing no code with proofs/pintree.py, whose docstring states the proof and the file.  Python's standard library only.
python3 -B -S proofs/pintree_second.py FILE [PROCESSES]

What differs on purpose:
  the enumeration: its own row reduction, each generator shift then checked to reduce to zero; its own coordinate order; and every vector it finds tested for membership by repeated synthetic division, as proofs/proof288.py does,
    the parity coset by division too.
  the polynomial part: pintree.py uses integer Lagrange tables.  Here g is evaluated in exact fractions by Newton's divided differences, and g's degree is tested: its m-th finite difference over 0, ..., n-1 must vanish.
With more than one process, pintree.py's fast replay first says which tokens belong to each node at depth sym_depth.  That is only a hint: this program's own walk decides which nodes must be closed, and each is replayed here with every
check, and must close using exactly the tokens of its range, so that a wrong hint can only make the check fail.  432:12 takes about 5 minutes on 6 processes, 816:13 about an hour on 12.
"""
import gzip, json, os, sys, time
from fractions import Fraction
from multiprocessing import Pool

sys.setrecursionlimit(100000)


def require(ok, what):
    if not ok: raise ValueError(what)


def sizes(n, M):
    return [n // M + (1 if r < n % M else 0) for r in range(M)]


def poly_times(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b): out[i + j] += x * y
    return out


def wrap(a, M):
    out = [0] * M
    for i, x in enumerate(a): out[i % M] += x
    return out


def divides_x_minus_1(y, M, k):
    """Is y in (x-1)^k Z[x]/(x^M-1)?  By proof288.py's steps: y(1) = 0; z with (x-1) z = y; M | z(1); recurse on z - (z(1)/M) Phi."""
    y = list(y)
    for j in range(k, 0, -1):
        if sum(y) != 0: return False
        if j == 1: return True
        z, c = [0] * M, 0
        for r in range(M):           # (x - 1) z = y in R: z_(r-1) - z_r = y_r, so z_r = z_(r-1) - y_r, with z_(-1) = z_(M-1) free: take z_(-1) = 0
            c -= y[r]; z[r] = c
        s = sum(z)
        if s % M: return False
        q = s // M
        y = [t - q for t in z]
    return True


def in_lattice(y, M, m, e):
    """Is y in (x-1)^m (x+1)^e Z[x]/(x^M-1)?"""
    if not e: return divides_x_minus_1(y, M, m)
    if M % 2:
        # x + 1 is invertible on the part of R where x - 1 acts: (x+1) w = y solves uniquely up to the constant part; for odd M the factor x+1 only doubles the value at 1, which is 0 here
        # solve w = y (x+1)^(-1) over Q by the linear recurrence, and accept the integer solution with w(1) = 0
        total = sum(y)
        if total != 0: return False
        w = [Fraction(0)] * M
        # (x+1) w = y: w_r + w_(r-1) = y_r; alternating sum around the odd cycle gives w_0
        a = Fraction(0)
        for r in range(1, M): a = y[r] - a
        # w_(M-1) = a + (-1)^(M-1) * w_0 * ... by recurrence w_r = y_r - w_(r-1): w_(M-1) = a + w_0 (M odd), and y_0 = w_0 + w_(M-1)
        w0 = (y[0] - a) / 2
        w[0] = w0
        for r in range(1, M): w[r] = y[r] - w[r - 1]
        if any(t.denominator != 1 for t in w): return False
        return divides_x_minus_1([int(t) for t in w], M, m)
    # M even: (x+1) w = y needs y(-1) = 0; the solutions differ by c * alt, alt = (1, -1, 1, ...), and (x-1) alt = -2 alt, so that 2^m alt lies in (x-1)^m R and only c mod 2^m matters.
    # A member w + c alt has value at -1 divisible by 2^m, and alt(-1) = M, which fixes c modulo 2^m / gcd(M, 2^m): try those c.
    if sum((-1) ** r * y[r] for r in range(M)): return False
    w = [0] * M
    for r in range(1, M): w[r] = y[r] - w[r - 1]
    alt = [(-1) ** r for r in range(M)]
    wm = sum((-1) ** r * w[r] for r in range(M))
    mod = 2 ** m
    for c in range(mod):
        if (wm + c * M) % mod: continue
        if divides_x_minus_1([a + c * b for a, b in zip(w, alt)], M, m): return True
    return False


class Cursor:
    """The tokens, with their place."""
    def __init__(self, tokens, i=0): self.t, self.i = tokens, i
    def next(self):
        self.i += 1
        return self.t[self.i - 1]


class Check:
    """Replays a proof with every check; raises on anything that does not hold."""
    def __init__(self, data):
        self.n, self.m, self.xs = data['n'], data['m'], data['nodes']
        self.table = data['table']
        self.sym_depth = data['sym_depth']
        self.e = 1 if self.n < 2 ** self.m else 0
        self.closed, self.closers, self.bases = set(), {}, {}
        self.stats = {'closed': 0, 'splits': 0, 'vectors': 0, 'skipped': 0, 'bounds': 0}
        self.hints, self.jobs = None, []
        require(len(self.xs) == self.m and len(set(self.xs)) == self.m, 'the nodes')

    def g_values(self, values):
        """g at every position, in exact fractions, by divided differences; and a test that g has degree < m."""
        xs, m, n = self.xs, self.m, self.n
        c = [Fraction(v) for v in values]
        for j in range(1, m):
            for i in range(m - 1, j - 1, -1):
                c[i] = (c[i] - c[i - 1]) / (xs[i] - xs[i - j])
        out = []
        for p in range(n):
            v = c[m - 1]
            for j in range(m - 2, -1, -1): v = v * (p - xs[j]) + c[j]
            out.append(v)
        d = out[:]
        for _ in range(m): d = [b - a for a, b in zip(d, d[1:])]
        require(not any(d), 'g has degree >= m')
        return out

    def full(self, c):
        """A certificate's classes, w, sum of |w| and T."""
        values, classes, T = self.table[c]
        require(len(values) == self.m and T > 0, 'the form of a certificate')
        g = self.g_values(values)
        cl = {int(M): w for M, w in classes.items()}
        w = [g[p] + sum(x[p % M] for M, x in cl.items()) for p in range(self.n)]
        return cl, w, sum(abs(t) for t in w), T

    def closer(self, c):
        if c not in self.closers:
            cl, w, tot, T = self.full(c)
            if len(self.closers) > 50000: self.closers.clear()
            self.closers[c] = (cl, tot)
        return self.closers[c]

    def finest(self, pins):
        return sorted(M for M in pins if not any(Q != M and Q % M == 0 for Q in pins))

    def K(self, cl, pins):
        require(sorted(cl) == self.finest(pins), 'a certificate on other moduli than the pins')
        return sum(a * b for M in cl for a, b in zip(cl[M], pins[M]))

    def rep(self, M):
        n, m, e = self.n, self.m, self.e
        t = 0
        while (n >> t) % 2 == 0: t += 1
        u = n >> t
        require(2 ** t - 1 >= m + e, 'the two lemma already rules this order out')
        S = [0] * M
        for i in range(u): S[(i * 2 ** t) % M] ^= 1
        h = [1]
        for _ in range(2 ** t - 1 - m - e): h = [c % 2 for c in poly_times(h, [1, 1])]
        h = [c % 2 for c in wrap(poly_times(wrap(h, M), S), M)]
        for _ in range(m): h = wrap(poly_times(h, [-1, 1]), M)
        for _ in range(e): h = wrap(poly_times(h, [1, 1]), M)
        return h

    def echelon(self, M, order):
        """A basis of L(M) by its own row reduction, coordinates in the given order: rows ending at distinct coordinates, every generator shift then reducing to zero (checked)."""
        key = (M, tuple(order))
        if key in self.bases: return self.bases[key]
        gen = [1]
        for _ in range(self.m): gen = poly_times(gen, [-1, 1])
        for _ in range(self.e): gen = poly_times(gen, [1, 1])
        gen = wrap(gen, M)
        shifts = [[gen[(r - k) % M] for r in order] for k in range(M)]
        rows = {}
        for v in shifts:
            v = v[:]
            while any(v):
                c = max(i for i in range(M) if v[i])
                if c not in rows:
                    rows[c] = v[:] if v[c] > 0 else [-x for x in v]; break
                u = rows[c]
                q = v[c] // u[c]
                w = [x - q * y for x, y in zip(v, u)]
                if v[c] % u[c] == 0: v = w
                else:                     # Euclid on the pivot entries
                    rows[c] = w if w[c] > 0 else [-x for x in w]
                    v = u
        for v in shifts:              # the reduction lost nothing
            v = v[:]
            while any(v):
                c = max(i for i in range(M) if v[i])
                require(c in rows and v[c] % rows[c][c] == 0, 'the row reduction lost a generator')
                q = v[c] // rows[c][c]
                v = [x - q * y for x, y in zip(v, rows[c])]
        self.bases[key] = rows
        return rows

    def admissible(self, M, pins, lo, hi):
        """All vectors meeting the conditions, walking the coordinates from last to first, sorted by (r mod parent, r); each result tested by division as well."""
        n, m = self.n, self.m
        sz = sizes(n, M)
        P = max((Q for Q in pins if Q != M and M % Q == 0), default=None)
        lows = [-s for s in sz] if lo is None else [max(-s, a) for s, a in zip(sz, lo)]
        highs = list(sz) if hi is None else [min(s, b) for s, b in zip(sz, hi)]
        if any(a > b for a, b in zip(lows, highs)): return []
        two = M & (M - 1) == 0
        R = self.rep(M) if two else [0] * M
        order = sorted(range(M), key=lambda r: (r % P if P else 0, r))
        rows = self.echelon(M, order)
        step = 2 if two else 1
        target = pins[P] if P else None
        out, coef = [], {}
        def walk(i, D):
            if i < 0:
                V = [0] * M
                for k, r in enumerate(order): V[r] = D[k]
                if P and any(sum(V[r] for r in range(q, M, P)) != target[q] for q in range(P)): return
                if two:
                    d = [a - b for a, b in zip(V, R)]
                    require(not any(x % 2 for x in d) and in_lattice([x // 2 for x in d], M, m, self.e), 'a walked vector is not in the coset')
                else:
                    require(in_lattice(V, M, m, self.e), 'a walked vector is not in the lattice')
                out.append(tuple(V))
                return
            r = order[i]
            base = R[r] + step * sum(rows[c][i] * z for c, z in coef.items() if c > i)
            def take(v):
                if not lows[r] <= v <= highs[r] or (v - sz[r]) % 2: return
                if P:
                    q = r % P
                    done = v + sum(D[k] for k in range(i + 1, M) if order[k] % P == q)
                    left = [k for k in range(i) if order[k] % P == q]
                    if not sum(lows[order[k]] for k in left) <= target[q] - done <= sum(highs[order[k]] for k in left): return
                D[i] = v
                walk(i - 1, D)
            if i in rows:
                h = step * rows[i][i]
                z = -((base - lows[r]) // h)
                while base + h * z <= highs[r]:
                    coef[i] = z
                    take(base + h * z)
                    z += 1
                coef.pop(i, None)
            else:
                take(base)
        walk(M - 1, [0] * M)
        return sorted(out)

    def image_keys(self, pins):
        n = self.n
        r = {M: tuple(D[(n - 1 - s) % M] for s in range(M)) for M, D in pins.items()}
        def key(p): return tuple(sorted(p.items()))
        def neg(p): return {M: tuple(-x for x in D) for M, D in p.items()}
        return [key(pins), key(neg(pins)), key(r), key(neg(r))]

    def node(self, pins):
        tok = self.cursor.next()
        if tok[0] == 'L':
            cl, tot = self.closer(tok[1])
            require(abs(self.K(cl, pins)) > tot, f'certificate {tok[1]} does not close its node')
            self.stats['closed'] += 1
        else:
            require(tok[0] == 'S', f'unknown token {tok[0]}')
            M, bounds = tok[1], tok[2]
            require(M not in pins, f'{M} is pinned already')
            lo, hi = None, None
            if bounds is not None:
                require(len(bounds) == M, 'a bound per class')
                lo, hi = [], []
                for r, (ca, cb) in enumerate(bounds):
                    for s, c in ((-1, ca), (1, cb)):
                        cl, w, tot, T = self.full(c)
                        K = self.K(cl, pins)
                        # T s D_r = sum_p (T s 1_{p = r} - w(p)) a_p + K
                        v = (sum(abs(T * s * (p % M == r) - w[p]) for p in range(self.n)) + K) / T
                        v = v.numerator // v.denominator
                        if s == 1: hi.append(v)
                        else: lo.append(-v)
                    self.stats['bounds'] += 2
            self.stats['splits'] += 1
            for v in self.admissible(M, pins, lo, hi):
                self.stats['vectors'] += 1
                child = {**pins, M: v}
                if len(child) <= self.sym_depth and any(k in self.closed for k in self.image_keys(child)):
                    self.stats['skipped'] += 1
                    continue
                if self.hints is not None and len(child) == self.sym_depth:
                    key = tuple(sorted(child.items()))
                    start, end = self.hints[key]
                    require(start == self.cursor.i, 'a hint does not start where the walk stands')
                    self.jobs.append((start, end, {str(k): list(x) for k, x in child.items()}))
                    self.cursor.i = end
                    self.closed.add(key)
                    continue
                self.node(child)
        if len(pins) <= self.sym_depth: self.closed.add(tuple(sorted(pins.items())))


DATA = None


def initialize(data):
    """Give each worker the proof explicitly, including under spawn."""
    global DATA
    DATA = data


def subtree(job):
    start, end, pins = job
    C = Check(DATA)
    C.cursor = Cursor(DATA['tokens'], start)
    C.sym_depth = -1           # below sym_depth no node skips by symmetry, as in the proof
    C.node({int(k): tuple(v) for k, v in pins.items()})
    require(C.cursor.i == end, 'a subtree did not use exactly its tokens')
    return C.stats


def hints(data):
    """(pins) -> (first token, one past its last), from pintree.py's fast replay: only a hint."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pintree
    found = {}
    class Marked(pintree.Replay):
        def node(self, pins):
            at = self.tokens.i
            super().node(pins)
            if len(pins) == self.sym_depth: found[tuple(sorted(pins.items()))] = (at, self.tokens.i)
    class Stream(Cursor):
        def __iter__(self): return self
        def __next__(self):
            if self.i >= len(self.t): raise StopIteration
            return self.next()
    R = Marked(data['n'], data['m'], data['nodes'], [tuple(c) for c in data['table']], data['tokens'], data['sym_depth'])
    R.tokens = Stream(data['tokens'])
    R.node({})
    return found


if __name__ == '__main__':
    t0 = time.time()
    with gzip.open(sys.argv[1], 'rt', encoding='utf-8') as f: DATA = json.load(f)
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    top = Check(DATA)
    top.cursor = Cursor(DATA['tokens'])
    if procs > 1: top.hints = hints(DATA)
    top.node({})
    require(top.cursor.i == len(DATA['tokens']), 'tokens left over')
    totals = dict(top.stats)
    if top.jobs:
        print(f'Claude: "the top of the tree holds; {len(top.jobs)} subtrees to replay [{time.time()-t0:.0f} s]"', flush=True)
        with Pool(procs, initializer=initialize, initargs=(DATA,)) as pool:
            for st in pool.imap_unordered(subtree, sorted(top.jobs, key=lambda j: j[0] - j[1]), chunksize=1):
                for k, v in st.items(): totals[k] += v
    print(f'Claude: "VERIFIED by the second check: no sequence of length {DATA["n"]} has order {DATA["m"]}.  {totals} [{time.time()-t0:.0f} s]"', flush=True)
