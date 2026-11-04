#!/usr/bin/env python3
"""The tilted search: F = the positions of a central stretch with small tilt; the other signs from a tilted K-best beam; every finisher a coset, enumerated in C++.
Usage: tilted.py n m W th qs K seconds [opts]"""
import sys, time, math, ctypes, argparse, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'pinned'))
import numpy as np, mpmath as mp
from pinned_problem import Problem, default_profiles, exact_order, sequence, hexcode, small_factors
from entropy import Rows
mp.mp.dps = 200
lib = ctypes.CDLL(os.path.join(HERE, 'libtbeam.so')); lib.tbeam.restype = ctypes.c_longlong; lib.batch.restype = ctypes.c_longlong
dp = ctypes.POINTER(ctypes.c_double); u64p = ctypes.POINTER(ctypes.c_uint64); i32p = ctypes.POINTER(ctypes.c_int32); i8p = ctypes.POINTER(ctypes.c_int8); llp = ctypes.POINTER(ctypes.c_longlong); i64p = ctypes.POINTER(ctypes.c_int64)
class Tilted:
    def __init__(self, n, m, W, th, profile, beta=20, log=print, order='x', checkpoint_every=12, lev=1.0):
        self.n, self.m = n, m; t0 = time.time()
        self.R = Rows(n, m, profile); sol = self.R.solve(); assert sol is not None, 'pins infeasible even for real signs'
        self.t = dict(zip(self.R.xs, sol['t'])); self.R.t_arr = sol['t']; self.Sbits = sol['S'] / math.log(2)
        F = [x for x in list(range(1, n, 2))[:W] if abs(self.t[x]) < th]
        if lev < 1.0:
            # positions the rows nearly determine do not belong in F: the Gaussian model is wrong there, and the beam can decide them properly
            F = self.low_leverage(F, profile, lev)
        self.P = P = Problem(n, m, F, profile, beta=beta, log=lambda *x: None)
        assert not P.hard, f'pin rows that F does not touch: {len(P.hard)}'
        self.rho, self.f, self.d = P.rho, P.I.f, P.I.d
        t1 = time.time()
        xs = sorted(P.Fx, reverse=True) if order == 'x' else sorted(P.Fx, key=lambda x: (abs(self.t[x]) < 0.5, -x))
        self.xs = xs; self.L = L = len(xs); rho = self.rho
        self.cols = {x: P.vis_col(x) for x in xs}
        wF = [mp.mpf(1) - mp.mpf(float(self.t[x])) ** 2 for x in F]
        tt = np.array([self.t[x] for x in xs]); w = 1 - tt * tt; sw = np.sqrt(w)
        Sm = mp.matrix(rho, rho)
        for i in range(rho):
            Ai = P.A[i]
            for j in range(i + 1):
                Aj = P.A[j]; v = mp.fsum(Ai[k] * Aj[k] * wF[k] for k in range(self.f) if Ai[k] and Aj[k]); Sm[i, j] = v; Sm[j, i] = v
        Lc = mp.cholesky(Sm); self.logdetSw = float(2 * mp.fsum(mp.log(Lc[i, i], 2) for i in range(rho)))
        # S at each checkpoint, from the inside out; coordinates whitened by S at the start of each segment
        step = checkpoint_every
        cks = list(range(0, L, step))
        Sl = {L: Sm}
        cur = Sm.copy()
        for l in range(L - 1, -1, -1):
            col = self.cols[xs[l]]; wl = mp.mpf(float(w[l]))
            for i in range(rho):
                ci = col[i]
                if ci:
                    t_ = ci * wl
                    for j in range(i + 1):
                        if col[j]:
                            v = t_ * col[j]; cur[i, j] += v
                            if j < i: cur[j, i] += v
            if l in cks: Sl[l] = cur.copy()
        self.g = np.zeros((L, rho)); self.u = np.zeros((L, rho)); self.h = np.zeros(L)
        Ls = {c: mp.cholesky(Sl[c]) for c in cks}; Ls[L] = Lc
        self.cklev = []; Ts = []
        for si, c in enumerate(cks):
            e = cks[si + 1] if si + 1 < len(cks) else L
            Li = mp.inverse(Ls[c]); li = [[Li[i, j] for j in range(i + 1)] for i in range(rho)]
            def wh(col): return [mp.fsum(li[i][j] * col[j] for j in range(i + 1) if col[j]) for i in range(rho)]
            M = [[mp.mpf(int(i == j)) for j in range(rho)] for i in range(rho)]
            for l in range(c, e):
                col = self.cols[xs[l]]; sq = mp.sqrt(mp.mpf(float(w[l])))
                gw = [a_ * sq for a_ in wh(col)]
                uu = [mp.fsum(a_ * b_ for a_, b_ in zip(M[i], gw)) for i in range(rho)]
                q = mp.fsum(a_ * b_ for a_, b_ in zip(gw, uu)); den = 1 - q
                for i in range(rho):
                    ti = uu[i] / den; Mi = M[i]
                    for j in range(i + 1):
                        Mi[j] += ti * uu[j]
                        if j < i: M[j][i] = Mi[j]
                self.g[l] = [float(a_) for a_ in gw]; self.u[l] = [float(a_) for a_ in uu]; self.h[l] = float(q)
            if e < L:
                Tm = Ls[e].T * Li.T
                self.cklev.append(e - 1); Ts.append([[float(Tm[i, j]) for j in range(rho)] for i in range(rho)])
        # the exact starting residual: the tilts meet the rows only to double precision
        allx = list(F) + list(xs)
        r0 = [mp.mpf(0)] * rho
        tv = P.vis_target()
        r0 = [mp.mpf(tv[i]) for i in range(rho)]
        for x in allx:
            col = P.vis_col(x); tx = mp.mpf(float(self.t[x]))
            for i in range(rho):
                if col[i]: r0[i] -= tx * col[i]
        Li0 = mp.inverse(Ls[0])
        p0 = [mp.fsum(Li0[i, j] * r0[j] for j in range(i + 1)) for i in range(rho)]
        self.p0 = np.array([float(v) for v in p0]); self.pi0 = float(mp.fsum(v * v for v in p0))
        self.cklev = np.array(self.cklev, dtype=np.int32); self.T = np.ascontiguousarray(np.array(Ts, dtype=np.float64)) if Ts else np.zeros((0, rho, rho))
        self.ep = (1 - tt) / sw; self.em = (-1 - tt) / sw; self.lp = -2 * np.log((1 + tt) / 2); self.lm = -2 * np.log((1 - tt) / 2)
        self.g = np.ascontiguousarray(self.g); self.u = np.ascontiguousarray(self.u)
        # the coset base point and its increments
        adj, det, U, I = P.adj, P.det, P.U, P.I
        def solve_z(v):
            w_ = [sum(v[i] * adj[i][j] for i in range(rho)) for j in range(rho)]
            assert all(x % det == 0 for x in w_), 'a column outside the lattice: a congruence'
            w_ = [x // det for x in w_]
            z = [2 * sum(w_[k] * U[k][i] for k in range(rho)) for i in range(self.f)]    # as 2z, for Babai by 2K
            # Babai with exact integers, repeated: a float only chooses each coefficient, and the first passes may hold numbers far beyond 2^53
            Bf = I.B.astype(np.float64); sq = np.sqrt(I.rr)
            for _ in range(200):
                af = np.array([float(v) for v in z]); changed = False
                for i in range(I.d - 1, -1, -1):
                    c = float((af / 2) @ I.Q[i]) / sq[i]
                    if abs(c) >= 0.5:
                        c_ = int(round(c)); changed = True
                        z = [v - 2 * c_ * r for v, r in zip(z, I.K[i])]
                        af = af - 2.0 * float(c_) * Bf[i]
                if not changed: break
            assert max(abs(v) for v in z) < 2 ** 62, 'babai did not settle'
            return [x // 2 for x in z]
        tot = [sum(self.cols[x][j] for x in xs) for j in range(rho)]
        v0 = [(t_ - s_ + S_) for t_, s_, S_ in zip(P.vis_target(), tot, P.Sum)]
        assert all(x % 2 == 0 for x in v0), 'parity'
        self.z0 = np.array(solve_z([x // 2 for x in v0]), dtype=np.int64)
        self.zx = np.ascontiguousarray(np.array([solve_z(self.cols[x]) for x in xs], dtype=np.int64))
        # constant of the estimate: log2 E(coset) = constant - Gamma / (2 ln 2)
        self.E0 = self.Sbits - rho / 2 * math.log2(2 * math.pi) + rho + float(mp.log(abs(mp.mpf(det)), 2)) - self.logdetSw / 2
        self.Q = np.ascontiguousarray(I.Q); self.mu = np.ascontiguousarray(I.mu); self.rr = np.ascontiguousarray(I.rr); self.B = np.ascontiguousarray(I.B)
        log(f'Tilted n={n} m={m} W={W} th={th}: f={self.f} rho={rho} d={self.d} L={L}; S {self.Sbits:.1f} bits; entropy on F {sum(self.bern(self.t[x]) for x in F):.1f}; Eceil(plain) {P.log2Eceil:.1f}; E0 {self.E0:.1f}; pi0 {self.pi0:.2e}; det factors {small_factors(abs(det))}; lattice {t1-t0:.1f}s, levels {time.time()-t1:.1f}s')
    def low_leverage(self, F, profile, lev):
        R = self.R; idx = {x: i for i, x in enumerate(R.xs)}
        pinrows = R.F[R.r:]
        F = list(F)
        while True:
            X = np.array(F, dtype=float); X = X / X.max(); I = [idx[x] for x in F]
            mom = np.array([X ** (2 * j + (0 if R.s == 1 else 1)) for j in range(R.r)])
            A = np.vstack([mom, pinrows[:, I]]) if len(pinrows) else mom
            wt = np.sqrt(np.maximum(1 - R.t_arr[I] ** 2, 1e-6))
            Q, Rr = np.linalg.qr((A * wt).T)
            keep = np.abs(np.diag(Rr)) > 1e-9 * np.abs(np.diag(Rr)).max()
            levs = (Q[:, keep] ** 2).sum(axis=1)
            j = int(np.argmax(levs))
            if levs[j] <= lev or len(F) <= R.rho + 5: return F
            F.pop(j)
    @staticmethod
    def bern(t):
        p = (1 + abs(t)) / 2
        return 0.0 if p >= 1 else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    def beam(self, K, Kout, gumbel, seed, Ktop=None, last=None, field=None):
        L = self.L
        if field is None: field = np.zeros(L)
        Ks = np.full(L, K, dtype=np.int64)
        if Ktop is not None:
            Ks[:] = Ktop; Ks[L - last:] = K
        W = (L + 63) // 64; S = np.zeros((Kout, W), dtype=np.uint64); G = np.zeros(Kout); Pi = np.zeros(Kout)
        n = lib.tbeam(ctypes.c_int(L), ctypes.c_int(self.rho), self.g.ctypes.data_as(dp), self.u.ctypes.data_as(dp), self.h.ctypes.data_as(dp), self.ep.ctypes.data_as(dp), self.em.ctypes.data_as(dp), self.lp.ctypes.data_as(dp), self.lm.ctypes.data_as(dp), field.ctypes.data_as(dp),
                      Ks.ctypes.data_as(llp), ctypes.c_int(len(self.cklev)), self.cklev.ctypes.data_as(i32p), self.T.ctypes.data_as(dp), self.p0.ctypes.data_as(dp), ctypes.c_double(self.pi0), ctypes.c_double(gumbel), ctypes.c_ulonglong(seed), ctypes.c_longlong(Kout), S.ctypes.data_as(u64p), G.ctypes.data_as(dp), Pi.ctypes.data_as(dp))
        return S[:n], G[:n], Pi[:n]
    def enum(self, S, floor_, max_nodes, maxsol=64, sag=0.0, tail=0.0):
        out = np.zeros((maxsol, self.f), dtype=np.int8); idx = np.zeros(maxsol, dtype=np.int64); st = np.zeros(4); perp = np.zeros(len(S))
        k = lib.batch(ctypes.c_int(self.L), ctypes.c_int(self.f), ctypes.c_int(self.d), S.ctypes.data_as(u64p), ctypes.c_longlong(len(S)), self.zx.ctypes.data_as(i64p), self.z0.ctypes.data_as(i64p), self.B.ctypes.data_as(i32p),
                      self.mu.ctypes.data_as(dp), self.rr.ctypes.data_as(dp), self.Q.ctypes.data_as(dp), ctypes.c_double(floor_), ctypes.c_double(sag), ctypes.c_double(tail), ctypes.c_longlong(int(max_nodes)), ctypes.c_longlong(maxsol), out.ctypes.data_as(i8p), idx.ctypes.data_as(llp), st.ctypes.data_as(dp), perp.ctypes.data_as(dp))
        return out[:k], idx[:k], st, perp
    def witness(self, row, sg):
        s_ = 1 if self.m % 2 == 0 else -1
        b = {x: (1 if (int(row[l // 64]) >> (l % 64)) & 1 else -1) for l, x in enumerate(self.xs)}
        b.update({x: int(v) for x, v in zip(self.P.F, sg)})
        fs = sequence(self.n, s_, b); o = exact_order(fs); assert o >= self.m, o
        return o, hexcode(fs, self.n)
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int); ap.add_argument('m', type=int); ap.add_argument('W', type=int); ap.add_argument('th', type=float); ap.add_argument('qs'); ap.add_argument('K', type=float); ap.add_argument('seconds', type=float)
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--gumbel', type=float, default=1.0); ap.add_argument('--maxnodes', type=float, default=1e8); ap.add_argument('--floor', type=float, default=1.0); ap.add_argument('--stop', type=int, default=1)
    ap.add_argument('--kout', type=float, default=0); ap.add_argument('--own', default=None); ap.add_argument('--beta', type=int, default=20); ap.add_argument('--every', type=float, default=60); ap.add_argument('--prof', default=None); ap.add_argument('--tail', type=float, default=0.0); ap.add_argument('--lev', type=float, default=1.0); ap.add_argument('--sag', type=float, default=0.0); ap.add_argument('--field', type=float, default=0.0); ap.add_argument('--ktop', type=int, default=0); ap.add_argument('--last', type=int, default=0)
    a = ap.parse_args()
    log = lambda *x: print(time.strftime('%H:%M:%S'), *x, flush=True)
    n, m, K = a.n, a.m, int(a.K); qs = [int(q) for q in a.qs.split(',')]
    if a.own:
        s_ = 1 if m % 2 == 0 else -1
        bits = bin(int(a.own, 16))[2:].zfill(n // 2); left = [1 if b == '1' else -1 for b in bits]; f_ = left + [s_ * v for v in reversed(left)]
        pf = [(q, [sum(f_[r::q]) for r in range(q)]) for q in qs]
    elif a.prof:
        d_ = json.loads(open(a.prof).read().strip().splitlines()[-1]); pf = [(q, d_[str(q)]) for q in qs]
    else:
        pf = default_profiles(n, m, qs, log=lambda *x: None)
    T = Tilted(n, m, a.W, a.th, pf, beta=a.beta, log=log, lev=a.lev)
    BITS = 31; bitmap = np.zeros(1 << (BITS - 3), dtype=np.uint8); seen_tot = seen_dup = 0; rng = np.random.default_rng(a.seed); T0 = time.time(); last = T0; found = []; cosets = nodes = big = trunc = 0; tb = te = 0.0; sumE = 0.0; runs = 0; Kout = int(a.kout) or K
    while time.time() - T0 < a.seconds and not (found and a.stop):
        runs += 1
        t1 = time.time(); S, G, Pi = T.beam(K, Kout, a.gumbel, int(rng.integers(1 << 62)), a.ktop or None, a.last or None, a.field * rng.logistic(0.0, 2.0, size=T.L) if a.field > 0 else None); t2 = time.time(); tb += t2 - t1
        # first sight only: a bitmap over a hash of the signs
        h = np.zeros(len(S), dtype=np.uint64)
        for w_ in range(S.shape[1]): h = (h ^ S[:, w_]) * np.uint64(0x9E3779B97F4A7C15); h ^= h >> np.uint64(29)
        pos = (h >> np.uint64(64 - BITS)).astype(np.int64); byte, bit = pos >> 3, (pos & 7).astype(np.uint8)
        fresh = (bitmap[byte] >> bit) & 1 == 0
        _, first = np.unique(pos, return_index=True); mask = np.zeros(len(S), dtype=bool); mask[first] = True; fresh &= mask
        bitmap[byte[fresh]] |= (np.uint8(1) << bit[fresh])
        seen_tot += len(S); seen_dup += int((~fresh).sum())
        S = S[fresh]; G = G[fresh]; Pi = Pi[fresh]
        if len(S) == 0: continue
        logE = T.E0 - G / 2 / math.log(2); sumE += float(np.sum(2.0 ** logE))
        sols, idx, st, perp = T.enum(S, a.floor, a.maxnodes, sag=a.sag, tail=a.tail); te += time.time() - t2
        cosets += st[0]; nodes += st[1]; big += st[2]; trunc += st[3]
        for sg, i in zip(sols, idx):
            o, code = T.witness(S[i], sg)
            found.append(dict(n=n, m=m, order=o, code=code, t=time.time() - T0, logE=float(logE[i]), perp2=float(perp[i]), Gamma=float(G[i]), W=a.W, th=a.th, seed=a.seed, qs=a.qs))
            log(f'  WITNESS n={n} order={o} logE {logE[i]:.1f} perp2 {perp[i]:.1f} coset rank {i} code={code}')
            open(f'found_{n}_{m}.jsonl', 'a').write(json.dumps(found[-1]) + '\n')
        if time.time() - last > a.every or (found and a.stop):
            last = time.time()
            log(f'runs {runs}: this run log2E top {logE[0]:.1f} median {logE[len(logE)//2]:.1f}, Gamma {G[0]:.1f}, pi {Pi[0]:.1f}, plain perp2 {perp[0]:.1f}..{np.median(perp):.1f}; cosets {cosets:.3g}, nodes/coset {nodes/max(cosets,1):.3g}, reached 1000 nodes {big/max(cosets,1):.2e}, truncated {trunc:.0f}; sum E 2^{math.log2(sumE+1e-300):.1f}; repeats {seen_dup/max(seen_tot,1):.2f}; witnesses {len(found)}; beam {tb:.0f}s enum {te:.0f}s')
    log(f'done: runs {runs}, cosets {cosets:.4g}, nodes {nodes:.4g}, sum E 2^{math.log2(sumE+1e-300):.1f}, witnesses {len(found)}, beam {tb:.0f}s, enumeration {te:.0f}s, {time.time()-T0:.0f}s')
