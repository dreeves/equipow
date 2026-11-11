#!/usr/bin/env python3
"""Claude's maker of pin trees, the proofs that proofs/pintree.py checks and whose docstring defines the vocabulary.  It needs numpy, scipy and highspy.  An LP in floating point only suggests: every certificate is checked in
integers as it is made, and the file is then checked from scratch by proofs/pintree.py and proofs/pintree_second.py, neither of which trusts this program.  searches/pintree/README.md explains the method.

    python3 -B searches/pintree/pintree_prove.py prove n:m PROCESSES [CAP]
    python3 -B searches/pintree/pintree_prove.py estimate n:m PROCESSES SECONDS

Each run works in scratch/pintree/n_m/: results are saved per node, so that a stopped run resumes.  prove writes scratch/pintree/pintree_n_m.json.gz, or, when nodes stay open, lists them in scratch/pintree/n_m/open.json.

The tree it makes.  Phase 0 pins the residue sums mod 3, 5, 7 and 4 in turn, closing what it can, one node per orbit of the symmetries.  Phase 1 takes each node left through its vectors mod 8.  Phase 2 takes each node left in turn: the
LP bounds the residue sums of a candidate modulus, the vectors inside those bounds are listed, and the first candidate with at most ENOUGH vectors (else the one with the fewest, at most CAP) splits the node, each child closed or split again.

estimate runs phase 0 and phase 1, then one random path from EACH remaining root, a fixed stratified sample
(Codex, 2026-11-11). It sums Knuth-weighted node counts and process CPU costs for phase 2. SECONDS is a wall-time
deadline for that whole sample, after phase 1; a timeout or an unsplittable open node prevents a runtime projection.
The projections are not bounds: heavy tails and differences in LP state and certificate reuse between a sampled
path and the full proof traversal can make them inaccurate in either direction.
"""
import collections, gzip, hashlib, json, os, random, sys, time
from multiprocessing import Pool
import numpy as np
import highspy

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(HERE, 'proofs'))
from pintree import Weights, effective, freeze, images, vectors

CHAIN = (3, 5, 7, 4, 8)             # the moduli of phases 0 and 1, in order
DEPTH = 4                           # phase 0 ends at this many pins, and symmetry is used down to here
CAP = 20000                         # a candidate modulus with more vectors than this is not used
ENOUGH = 64                         # a candidate with at most this many vectors is used at once
BITS = (16, 24, 32, 48, 64)         # the precisions tried for a certificate's integers
MODELS = 24                         # LP models kept per process
WALK = 3 * 10 ** 6                  # steps allowed to one listing of a candidate's vectors


def candidates(pins):
    """The moduli a node may split on next, in the order they are tried."""
    out = []
    if 3 in pins and 9 not in pins: out.append(9)
    elif 9 in pins and 27 not in pins: out.append(27)
    for p in (11, 13):
        if p not in pins: out.append(p)
    for M in (16, 32, 64):
        if M // 2 in pins and M not in pins: out.append(M); break
    if 5 in pins and 25 not in pins: out.append(25)
    for p in (17, 19, 23):
        if p not in pins: out.append(p)
    return out


def chebyshev_nodes(n, m):
    """m distinct integers near the Chebyshev points of 0..n-1: a choice only, which the file records."""
    xs = []
    for j in range(m):
        x = round((n - 1) * (1 - np.cos(np.pi * (2 * j + 1) / (2 * m))) / 2)
        while x in xs: x += 1
        xs.append(int(x))
    return tuple(sorted(xs))


class Oracle:
    """A warm-started HiGHS model of the moment rows and the class rows of a set of moduli.  Only the right sides and the costs change between solves."""
    def __init__(self, n, m, xs, mods):
        self.n, self.m, self.mods, self.xs = n, m, mods, list(xs)
        x = (2.0 * np.arange(n) - n + 1) / (n - 1)
        Q, _ = np.linalg.qr(np.polynomial.legendre.legvander(x, m - 1))
        rows = [Q.T]
        for M in mods:
            R = np.zeros((M, n))
            for r in range(M): R[r, r::M] = 1.0
            rows.append(R)
        A = np.vstack(rows)
        self.norms = np.linalg.norm(A, axis=1)
        self.A = A / self.norms[:, None]
        k = A.shape[0]; self.k = k
        h = highspy.Highs(); h.setOptionValue('output_flag', False); h.setOptionValue('threads', 1); h.setOptionValue('presolve', 'off')
        lp = highspy.HighsLp(); lp.num_col_, lp.num_row_ = n, k
        lp.col_cost_ = np.zeros(n); lp.col_lower_ = -np.ones(n); lp.col_upper_ = np.ones(n)
        lp.row_lower_ = np.zeros(k); lp.row_upper_ = np.zeros(k)
        lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
        lp.a_matrix_.start_ = np.arange(0, k * n + 1, n, dtype=np.int32)
        lp.a_matrix_.index_ = np.tile(np.arange(n, dtype=np.int32), k)
        lp.a_matrix_.value_ = self.A.ravel()
        h.passModel(lp); self.h = h
        self.idx = np.arange(k, dtype=np.int32); self.cols = np.arange(n, dtype=np.int32)

    def rhs(self, pins):
        b = np.zeros(self.k); pos = self.m
        for M in self.mods:
            b[pos:pos + M] = pins[M]; pos += M
        return b / self.norms

    def run(self):
        """True (optimal), False (infeasible) or None (the solver failed, which claims nothing)."""
        for attempt in range(3):
            if attempt == 1: self.h.clearSolver()
            if attempt == 2:
                self.h.clearSolver(); self.h.setOptionValue('presolve', 'on')
            self.h.run()
            st = self.h.getModelStatus()
            if attempt == 2: self.h.setOptionValue('presolve', 'off')
            if st == highspy.HighsModelStatus.kInfeasible: return False
            if st == highspy.HighsModelStatus.kOptimal: return True
        return None

    def set(self, pins, cost=None):
        b = self.rhs(pins)
        self.h.changeRowsBounds(self.k, self.idx, b, b)
        self.h.changeColsCost(self.n, self.cols, np.zeros(self.n) if cost is None else cost)

    def integers(self, y, bits, reference):
        """Integer weights from row multipliers y, scaled by 2^bits over reference: (values, classes)."""
        scale = 2.0 ** bits / reference
        poly = self.A[:self.m].T @ y[:self.m]
        values = [int(round(float(poly[p]) * scale)) for p in self.xs]
        classes, pos = {}, self.m
        for M in self.mods:
            classes[str(M)] = [int(round(float(y[pos + r] / self.norms[pos + r]) * scale)) for r in range(M)]
            pos += M
        return values, classes

    def ray(self):
        """The solver's dual ray after an infeasible solve, or None."""
        r = self.h.getDualRay()
        return np.array(r[2]) if r[1] else None

    def phase_one(self, pins):
        """Row multipliers of the least infeasibility, solved from scratch, or None."""
        from scipy.optimize import linprog
        k, n = self.k, self.n
        c = np.concatenate([np.zeros(n), np.ones(2 * k)])
        res = linprog(c, A_eq=np.hstack([self.A, np.eye(k), -np.eye(k)]), b_eq=self.rhs(pins), bounds=[(-1, 1)] * n + [(0, None)] * (2 * k), method='highs')
        return np.array(res.eqlin.marginals) if res.status == 0 and res.fun >= 1e-10 else None


ORACLES = collections.OrderedDict()


class Prover:
    """Makes the tokens and the table of a subtree."""
    def __init__(self, n, m, xs, cap, sym_depth):
        self.n, self.m, self.xs, self.cap, self.sym_depth = n, m, tuple(xs), cap, sym_depth
        self.table, self.tokens, self.weights, self.recent, self.closed = [], [], {}, {}, set()
        self.stats = {'lp': 0, 'new': 0, 'reused': 0, 'splits': 0, 'open': 0, 'bounds': 0}
        self.open = []

    def oracle(self, mods):
        key = (self.n, self.m, mods)
        if key in ORACLES: ORACLES.move_to_end(key)
        else:
            ORACLES[key] = Oracle(self.n, self.m, self.xs, mods)
            while len(ORACLES) > MODELS: ORACLES.popitem(last=False)
        return ORACLES[key]

    def add(self, cert):
        self.table.append(json.dumps([cert[0], cert[1], cert[2]], separators=(',', ':')))
        return len(self.table) - 1

    def close(self, pins):
        """A table index of a certificate closing pins, or None.  One already made is tried first, most recent first: most nodes close that way."""
        mods = effective(pins)
        recent = self.recent.setdefault(mods, [])
        for pos, i in enumerate(recent):
            if self.weights[i].closes(pins):
                recent.insert(0, recent.pop(pos))
                self.stats['reused'] += 1
                return i
        O = self.oracle(mods)
        O.set(pins); self.stats['lp'] += 1
        if O.run() is not False: return None
        for y in (O.ray(), 'phase one'):
            if y is None: continue
            if isinstance(y, str):
                y = O.phase_one(pins)
                if y is None: return None
            if not np.all(np.isfinite(y)): continue
            top = max(1e-300, float(np.max(np.abs(O.A.T @ y))))
            for bits in BITS:
                values, classes = O.integers(y, bits, top)
                W = Weights(self.n, self.xs, (values, classes, 1))
                if W.closes(pins):
                    j = self.add((values, classes, 1))
                    W.w = None                                  # closes() needs only the classes and the total
                    self.weights[j] = W
                    recent.insert(0, j)
                    while len(recent) > 400: del self.weights[recent.pop()]
                    self.stats['new'] += 1
                    return j
        return None

    def bound_cert(self, pins, O, M, r, s):
        """(B, certificate) proving s * D^(M)_r <= B, the least B found, or None."""
        c = np.zeros(self.n); c[r::M] = -s * 1.0            # minimize -s * sum, that is, maximize s * sum
        O.set(pins, c); self.stats['lp'] += 1
        if O.run() is not True: return None
        sol = O.h.getSolution()
        y = -np.array(sol.row_dual)
        if not np.all(np.isfinite(y)): return None
        target = int(np.floor(float(-c @ np.array(sol.col_value)) + 1e-6))
        best = None
        for sign in (1, -1):
            for bits in BITS:
                values, classes = O.integers(sign * y, bits, 1.0)
                cert = (values, classes, 2 ** bits)
                B = Weights(self.n, self.xs, cert).bound(pins, M, r, s)
                if best is None or B < best[0]: best = (B, cert)
                if B == target: return best
        return best

    def split_choice(self, pins):
        """(M, vectors, bounds' certificates) of the split to make, or None when no candidate serves."""
        O = self.oracle(effective(pins))
        best = None
        for M in candidates(pins):
            lo, hi, refs, ok = [0] * M, [0] * M, [], True
            for r in range(M):
                a = self.bound_cert(pins, O, M, r, -1)
                b = self.bound_cert(pins, O, M, r, 1)
                if a is None or b is None: ok = False; break
                lo[r], hi[r] = -a[0], b[0]
                refs.append((a[1], b[1]))
                if lo[r] > hi[r]: break
            if not ok: continue
            if any(lo[r] > hi[r] for r in range(len(refs))):
                vs = []
            else:
                try: vs = vectors(self.n, self.m, M, pins, lo, hi, limit=WALK)
                except OverflowError: continue
                if len(vs) > self.cap: continue
            if best is None or len(vs) < len(best[1]): best = (M, vs, refs)
            if len(vs) <= ENOUGH: break
        O.set(pins)
        return best

    def node(self, pins):
        """The tokens of a node below phase 1."""
        i = self.close(pins)
        if i is not None:
            self.tokens.append(['L', i])
            return
        ch = self.split_choice(pins)
        if ch is None:
            self.stats['open'] += 1
            self.open.append({str(k): list(v) for k, v in pins.items()})
            self.tokens.append(['OPEN'])
            return
        M, vs, refs = ch
        bounds = [[self.add(a), self.add(b)] for a, b in refs]
        while len(bounds) < M: bounds.append(bounds[-1])     # a class with lo > hi ended the bounds early; any certificate bounds the other classes validly
        self.stats['bounds'] += 2 * M
        self.tokens.append(['S', M, bounds])
        self.stats['splits'] += 1
        for v in vs: self.node({**pins, M: v})


def save(path, obj):
    tmp = path + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f: json.dump(obj, f, separators=(',', ':'))
    os.replace(tmp, path)


def load(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f: return json.load(f)


def pinkey(pins): return hashlib.sha1(json.dumps(sorted(pins.items())).encode()).hexdigest()


def phase1(args):
    """A node with pins mod 3, 5, 7 and 4: closed, or its children mod 8, each closed or left for phase 2."""
    n, m, xs, cap, pins, d = args
    pins = {int(k): tuple(v) for k, v in pins.items()}
    path = f'{d}/one_{pinkey(pins)}.json.gz'
    if os.path.exists(path): return path
    P = Prover(n, m, xs, cap, DEPTH)
    segments, left = [], []
    i = P.close(pins)
    if i is not None:
        segments.append(['L', i])
    else:
        segments.append(['S', 8, None])
        for v in vectors(n, m, 8, pins):
            child = {**pins, 8: v}
            i = P.close(child)
            if i is not None: segments.append(['L', i])
            else:
                c = {str(k): list(x) for k, x in child.items()}
                segments.append(['LEFT', c]); left.append(c)
    save(path, {'table': [json.loads(c) for c in P.table], 'segments': segments, 'left': left, 'stats': P.stats})
    return path


def phase2(args):
    n, m, xs, cap, pins, d = args
    p = {int(k): tuple(v) for k, v in pins.items()}
    path = f'{d}/two_{pinkey(p)}.json.gz'
    if os.path.exists(path):
        r = load(path)
        return r['stats'], r['open'], True
    P = Prover(n, m, xs, cap, DEPTH)
    sys.setrecursionlimit(100000)
    P.node(p)
    save(path, {'table': [json.loads(c) for c in P.table], 'tokens': P.tokens, 'stats': P.stats, 'open': P.open})
    return P.stats, P.open, False


def top_of_the_tree(n, m, xs, cap, d):
    """Phase 0: the tokens down to DEPTH pins, one node per orbit of the symmetries, and the nodes left at DEPTH."""
    top = Prover(n, m, xs, cap, DEPTH)
    segments, jobs = [], []
    def walk(pins, level):
        if len(pins) == DEPTH:
            jobs.append((n, m, xs, cap, {str(k): list(v) for k, v in pins.items()}, d))
            segments.append(('job', len(jobs) - 1))
            top.closed.add(freeze(pins))
            return
        if pins:
            i = top.close(pins)
            if i is not None:
                segments.append(('token', ['L', i])); top.closed.add(freeze(pins)); return
        M = CHAIN[level]
        segments.append(('token', ['S', M, None]))
        for v in vectors(n, m, M, pins):
            child = {**pins, M: v}
            if any(x in top.closed for x in images(child, n)): continue
            walk(child, level + 1)
        top.closed.add(freeze(pins))
    walk({}, 0)
    return top, segments, jobs


def workdir(n, m):
    d = os.path.join(HERE, 'scratch', 'pintree', f'{n}_{m}')
    os.makedirs(d, exist_ok=True)
    return d


def prove(n, m, procs, cap):
    xs = chebyshev_nodes(n, m)
    t0 = time.time()
    d = workdir(n, m)
    sys.setrecursionlimit(100000)
    top, segments, jobs = top_of_the_tree(n, m, xs, cap, d)
    print(f'Claude: "{n}:{m}: {len(jobs)} nodes after phase 0 [{time.time()-t0:.0f} s]"', flush=True)
    with Pool(procs, maxtasksperchild=20) as pool:
        paths = pool.map(phase1, jobs, chunksize=1)
        left = [c for path in paths for c in load(path)['left']]
        print(f'Claude: "{len(left)} nodes after phase 1 [{time.time()-t0:.0f} s]"', flush=True)
        left.sort(key=lambda c: hashlib.sha1(json.dumps(c, sort_keys=True).encode()).hexdigest())     # a fair sample as it goes, for the ETA
        done, opened, totals, fresh, t1, last = 0, [], collections.Counter(), 0, time.time(), time.time()
        for stats, op, cached in pool.imap_unordered(phase2, [(n, m, xs, cap, c, d) for c in left]):
            done += 1; fresh += not cached; totals.update(stats); opened += op
            if time.time() - last > 60 or done == len(left):
                last = time.time()
                rate = fresh / max(1e-9, last - t1)
                print(f'Claude: "phase 2: {done}/{len(left)} nodes, {len(opened)} open, {dict(totals)}, {rate*3600:.0f} nodes an hour, {(len(left)-done)/max(rate,1e-9)/3600:.1f} h to go [{last-t0:.0f} s]"', flush=True)
                with open(f'{d}/open.json', 'w') as f: json.dump(opened, f)
    if opened:
        print(f'Claude: "no proof: {len(opened)} nodes stay open, listed in {d}/open.json"', flush=True)
        return
    table = [json.loads(c) for c in top.table]; tokens = []
    for kind, x in segments:
        if kind == 'token':
            tokens.append(x)
            continue
        one = load(paths[x]); off = len(table); table += one['table']
        for s in one['segments']:
            if s[0] == 'L': tokens.append(['L', s[1] + off])
            elif s[0] == 'S': tokens.append(s)
            else:
                two = load(f'{d}/two_{pinkey({int(k): tuple(v) for k, v in s[1].items()})}.json.gz')
                base = len(table); table += two['table']
                for t in two['tokens']:
                    if t[0] == 'L': tokens.append(['L', t[1] + base])
                    else: tokens.append(['S', t[1], [[a + base, b + base] for a, b in t[2]]])
    path = os.path.join(HERE, 'scratch', 'pintree', f'pintree_{n}_{m}.json.gz')
    save(path, {'n': n, 'm': m, 'nodes': list(xs), 'sym_depth': DEPTH, 'table': table, 'tokens': tokens})
    print(f'Claude: "wrote {path}: {len(table)} certificates, {len(tokens)} tokens, {time.time()-t0:.0f} s"', flush=True)


def dive(args):
    """Weighted node count, open leaves, visited nodes and CPU seconds for one full random path.

    Every child, including an immediately closed one, can be sampled. A node with inverse path probability w
    contributes w to the size and w times its measured process CPU cost. An unfinished path is never a sample.
    """
    n, m, xs, cap, pins, seed, limit = args
    rng = random.Random(seed)
    deadline, started = time.monotonic() + limit, time.process_time()
    P = Prover(n, m, xs, cap, DEPTH)
    pins = {int(k): tuple(v) for k, v in pins.items()}
    size, weight, opened, nodes, cpu = 0.0, 1.0, 0.0, 0, time.process_time() - started
    while time.monotonic() < deadline:
        size += weight
        nodes += 1
        started = time.process_time()
        try:
            if P.close(pins) is not None: break
            ch = P.split_choice(pins)
            if ch is None:
                opened = weight
                break
            M, vs, _ = ch
            if not vs: break
        finally:
            cpu += weight * (time.process_time() - started)
        weight *= len(vs)
        pins = {**pins, M: rng.choice(vs)}
    else:
        # TODO: says this path exceeded its deadline and no complete estimate is available.
        raise TimeoutError('Iter imperfectum: tempus exhaustum; aestimatio nulla.')
    return size, opened, nodes, cpu


def estimate(n, m, procs, seconds, cap=CAP):
    # TODO: says the worker count and wall-time limit must both be positive.
    assert procs > 0 and seconds > 0, 'Processus et tempus positiva sint.'
    xs = chebyshev_nodes(n, m)
    d = workdir(n, m)
    sys.setrecursionlimit(100000)
    _, _, jobs = top_of_the_tree(n, m, xs, cap, d)
    with Pool(procs) as pool:
        paths = pool.map(phase1, jobs, chunksize=1)
        left = [c for path in paths for c in load(path)['left']]
        rng = random.Random(n * 1000 + m)
        cohort = [(n, m, xs, cap, c, rng.randrange(10 ** 9), seconds) for c in left]
        res = pool.map_async(dive, cohort, chunksize=1).get(timeout=seconds)
    # TODO: says every root must have a completed sample, and no sampled leaf may remain open.
    assert len(res) == len(left) and all(r[1] == 0 for r in res), 'Radix imperfecta vel folium apertum; aestimatio nulla.'
    size, cpu = sum(r[0] for r in res), sum(r[3] for r in res)
    # TODO: reports the fixed number of roots/paths, projected phase-2 nodes and CPU cost; these are guesses, not bounds.
    print(f'{n}:{m}: radices {len(left)}; itinera {len(res)}; nodi {size:.6g}; '
          f'CPU secunda {cpu:.6g}; CPU horae {cpu/3600:.6g} (coniectura, non terminus).', flush=True)


if __name__ == '__main__':
    what = sys.argv[1]
    n, m = map(int, sys.argv[2].split(':'))
    if what == 'prove': prove(n, m, int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else CAP)
    elif what == 'estimate': estimate(n, m, int(sys.argv[3]), float(sys.argv[4]))
    else: raise ValueError(f'unknown command {what}')
