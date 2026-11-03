#!/usr/bin/env python3
"""The pinned search with the free set F = a central block of f pairs.  No congruences arise, since a contiguous block's columns generate the whole moment
lattice; instead F's target must be tiny in real terms.  The fixed signs are annealed ring by ring, outermost first, so that the remaining target stays near the
center of what the inner positions can still reach, in the metric of those inner positions.  The lattice depends only on f, m and the pins, not on n."""
import sys, time, math, json, argparse, ctypes, os
import numpy as np
import mpmath as mp
from pinned_problem import Problem, Congruence, default_profiles, exact_order, sequence, hexcode
from pinned_lattice import bound_fn
core = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libpinned_anneal.so'))
core.anneal.restype = ctypes.c_double
dp = ctypes.POINTER(ctypes.c_double); ip = ctypes.POINTER(ctypes.c_int); i8p = ctypes.POINTER(ctypes.c_int8)


class Rings:
    def __init__(self, P, ratio, seed, log=print):
        self.P = P
        self.rng = np.random.default_rng(seed)
        t0 = time.time()
        C = Congruence(P)
        self.cols = {x: P.vis_col(x) for x in P.Fx}
        tot = [sum(self.cols[x][j] for x in P.Fx) + P.Sum[j] for j in range(P.rho)]
        tv = P.vis_target()
        assert all((t + w) % 2 == 0 for t, w in zip(tv, tot)), 'parity of totals on the visible rows'
        C.split([self.cols[x] for x in P.Fx], [(t + w) // 2 for t, w in zip(tv, tot)])
        assert not C.rows, 'the block has congruences that vary on Fx'
        assert not P.hard, 'hard rows on Fx'
        xmin = max(P.F) + 2
        xs = sorted(P.Fx)
        J = max(1, int(math.ceil(math.log(P.n / xmin) / math.log(ratio))))
        edges = [xmin * (P.n / xmin) ** (i / J) for i in range(J + 1)]
        self.rings = []
        for i in range(J - 1, -1, -1):
            ring = [x for x in xs if edges[i] <= x < edges[i + 1] or (i == J - 1 and x >= edges[i])]
            if not ring: continue
            inner = [x for x in xs if x < edges[i]] + list(P.F)
            A = mp.matrix([[P.vis_col(x)[j] for x in inner] for j in range(P.rho)])
            Linv = mp.inverse(mp.cholesky(A * A.T))
            Gm = Linv * mp.matrix([self.cols[x] for x in ring]).T
            self.rings.append(dict(xs=ring, Linv=Linv, G=np.ascontiguousarray(np.array([[float(Gm[a, b]) for b in range(len(ring))] for a in range(P.rho)]).T)))
        log(f'Rings: {len(self.rings)} rings, sizes {[len(r["xs"]) for r in self.rings]}; setup {time.time()-t0:.1f}s')

    def run(self, flips, swaps):
        """One assignment of the fixed signs: (signs, F's exact target, the penalty after each ring; the last is F's own perp2)."""
        tau = list(self.P.vis_target())
        signs, Qs = {}, []
        for r in self.rings:
            G = r['G']
            n_, rho = G.shape
            v = r['Linv'] * mp.matrix(tau)
            y0 = np.array([float(v[i]) for i in range(rho)])
            a = self.rng.choice([-1, 1], size=n_).astype(np.int8)
            y = y0 - a.astype(np.float64) @ G
            g2 = float(np.mean((G * G).sum(axis=1)))
            orb = np.zeros(n_, dtype=np.int32); chi = np.ones(n_, dtype=np.int8); e = np.zeros(1, dtype=np.int32)
            core.anneal(ctypes.c_int(n_), ctypes.c_int(rho), G.ctypes.data_as(dp), a.ctypes.data_as(i8p), y.ctypes.data_as(dp), orb.ctypes.data_as(ip), chi.ctypes.data_as(i8p),
                        ctypes.c_int(1), e.ctypes.data_as(ip), ctypes.c_longlong(flips), ctypes.c_longlong(swaps), ctypes.c_double(4 * g2), ctypes.c_double(0.3 * g2), ctypes.c_double(0.0),
                        ctypes.c_ulonglong(int(self.rng.integers(1 << 62))))
            y = y0 - a.astype(np.float64) @ G
            Qs.append(float(y @ y))
            for x, sgn in zip(r['xs'], a):
                signs[x] = int(sgn)
                tau = [t - int(sgn) * w for t, w in zip(tau, self.cols[x])]
        return signs, tau, Qs


def search(a, log):
    n, m = a.n, a.m
    s = 1 if m % 2 == 0 else -1
    pf = default_profiles(n, m, [int(q) for q in a.qs.split(',')], log=log)
    P = Problem(n, m, list(range(1, n, 2))[:a.f], pf, log=log)
    R = Rings(P, a.ratio, a.seed, log=log)
    t0 = time.time(); rounds = passed = nodes_all = 0; found = []
    while time.time() - t0 < a.tlimit and not (found and a.stop):
        rounds += 1
        dct, tau, Qs = R.run(int(a.flips), int(a.swaps))
        Q = Qs[-1]
        if Q > a.qgate: continue
        a1 = P.coset_base(tau)
        assert a1 is not None, 'not in the coset'
        sols, nodes, R2, ns = P.I.cvp(P.I.babai(a1), bound_fn=bound_fn(a.c, a.floor), max_nodes=int(a.maxnodes), maxsol=1000)
        nodes_all += nodes; passed += nodes > 1000
        perp2 = P.I.f - 4 * R2
        assert abs(perp2 - Q) < 1e-2, (perp2, Q)
        if nodes > 1000 or ns: log(f'  round {rounds}: perp2={perp2:.2f} log2E={P.log2Eceil - perp2 / 2 / math.log(2):.1f} nodes={nodes:.3g} sols={ns}')
        for row in sols:
            b = dict(dct)
            b.update({x: int(v) for x, v in zip(P.F, row)})
            fseq = sequence(n, s, b)
            o = exact_order(fseq)
            assert o >= m, o
            found.append(dict(n=n, m=m, order=o, code=hexcode(fseq, n), seed=a.seed, t=time.time() - t0, perp2=perp2))
            log(f'  WITNESS n={n} order={o} code={found[-1]["code"]}')
    log(f'done: rounds {rounds} passed {passed} nodes {nodes_all:.3g} witnesses {len(found)} time {time.time()-t0:.0f}s')
    return found


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int); ap.add_argument('m', type=int); ap.add_argument('f', type=int); ap.add_argument('qs')
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--ratio', type=float, default=1.05)
    ap.add_argument('--c', type=float, default=0.0); ap.add_argument('--floor', type=float, default=1.0); ap.add_argument('--maxnodes', type=float, default=2e9)
    ap.add_argument('--tlimit', type=float, default=3600); ap.add_argument('--qgate', type=float, default=1e9); ap.add_argument('--stop', type=int, default=1)
    ap.add_argument('--flips', type=float, default=3e4); ap.add_argument('--swaps', type=float, default=6e4); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    def log(*x): print(time.strftime('%H:%M:%S'), *x, flush=True)
    found = search(a, log)
    if a.out:
        with open(a.out, 'a') as fh:
            for w in found: fh.write(json.dumps(w) + '\n')
