#!/usr/bin/env python3
"""The tilted (saddle point) estimate of the number of (anti)symmetric solutions with given pins: S = max entropy over a in [-1,1]^L with the rows met, dual Newton on sum ln 2cosh(A' lam) - lam . b.
log2 E = S / ln 2 - (rho/2) log2(2 pi) - (1/2) log2 det(A diag(1-t^2) A') + log2 det(Lambda).  Compare the Gaussian estimate, with t = 0."""
import sys, os, math, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pinned'))
import numpy as np, mpmath as mp
from pinned_model import moment_col
from pinned_problem import pin_table, independent_rows, default_profiles
mp.mp.dps = 120
class Rows:
    def __init__(self, n, m, profiles):
        self.n, self.m = n, m
        self.r, self.s = m // 2, (1 if m % 2 == 0 else -1)
        self.xs = list(range(1, n, 2)); self.L = len(self.xs)
        self.q = [q for q, D in profiles]
        pins = []
        for q, D in profiles: pins += pin_table(n, q, self.s, D)
        self.pins = pins
        # integer rows
        mom = [moment_col(x, self.r, self.s) for x in self.xs]
        A = [[mom[i][j] for i in range(self.L)] for j in range(self.r)] + [[p['row'].get(x, 0) for x in self.xs] for p in pins]
        keep = independent_rows(A)
        self.keep = keep; self.A = [A[i] for i in keep]; self.rho = len(keep)
        self.b = [0 if i < self.r else pins[i - self.r]['target'] for i in keep]
        # a float basis of the same row space: Legendre-like moment rows, orthonormalised, then the pins
        X = np.array(self.xs, dtype=float) / n
        polys = np.array([X ** (2 * j + (0 if self.s == 1 else 1)) for j in range(self.r)])
        Q, _ = np.linalg.qr(polys.T)
        pinrows = np.array([[float(v) for v in self.A[i]] for i in range(self.r, self.rho)]) if self.rho > self.r else np.zeros((0, self.L))
        self.F = np.vstack([Q.T, pinrows]); self.fb = np.array([0.0] * self.r + [float(t) for t in self.b[self.r:]])
    def solve(self, tol=1e-9, maxit=200):
        lam = np.zeros(self.rho); F = self.F; b = self.fb
        def phi(l):
            x = F.T @ l
            return float(np.sum(np.logaddexp(x, -x))) - float(l @ b)
        cur = phi(lam)
        for it in range(maxit):
            x = F.T @ lam; t = np.tanh(x); g = F @ t - b
            if np.linalg.norm(g) < tol: break
            w = 1 - t * t
            H = (F * w) @ F.T + 1e-12 * np.eye(self.rho)
            step = np.linalg.solve(H, -g)
            a = 1.0
            while a > 1e-8:
                new = phi(lam + a * step)
                if new < cur + 1e-4 * a * (g @ step): break
                a /= 2
            if a <= 1e-8: break
            lam = lam + a * step; cur = phi(lam)
            if cur < -1e9 or abs(lam).max() > 1e6: return None
        x = F.T @ lam; t = np.tanh(x); g = np.linalg.norm(F @ t - b)
        if g > 1e-5: return None
        return dict(S=cur, t=t, lam=lam, resid=g)
    def logdet(self, w=None):
        """log2 det(A diag(w) A') over the integer rows"""
        Am = mp.matrix(self.A)
        W = [mp.mpf(1)] * self.L if w is None else [mp.mpf(float(v)) for v in w]
        rho = self.rho
        Sm = mp.matrix(rho, rho)
        Arows = self.A
        for i in range(rho):
            for j in range(i + 1):
                v = mp.fsum((Arows[i][k] * Arows[j][k] * W[k] for k in range(self.L) if Arows[i][k] and Arows[j][k]))
                Sm[i, j] = v; Sm[j, i] = v
        L = mp.cholesky(Sm)
        return float(2 * mp.fsum(mp.log(L[i, i], 2) for i in range(rho)))
def estimate(R, logdetLam, sol=None):
    sol = sol or R.solve()
    if sol is None: return None
    t = sol['t']
    tilted = sol['S'] / math.log(2) - R.rho / 2 * math.log2(2 * math.pi) - R.logdet(np.maximum(1 - t * t, 1e-12)) / 2 + logdetLam
    return tilted, sol
def gaussian(R, logdetLam):
    Am = mp.matrix(R.A); b = mp.matrix(R.b)
    S = Am * Am.T
    q = (b.T * mp.lu_solve(S, b))[0]
    return R.L - R.rho / 2 * math.log2(2 * math.pi) - R.logdet() / 2 + logdetLam - float(q) / 2 / math.log(2), float(q)
if __name__ == '__main__':
    from pinned_problem import Problem
    n, m = int(sys.argv[1]), int(sys.argv[2]); code = sys.argv[3]; qs = [int(q) for q in sys.argv[4].split(',')]
    s_ = 1 if m % 2 == 0 else -1
    bits = bin(int(code, 16))[2:].zfill(n // 2); left = [1 if b == '1' else -1 for b in bits]
    f = left + [s_ * v for v in reversed(left)]
    own = [(q, [sum(f[r::q]) for r in range(q)]) for q in qs]
    pf = default_profiles(n, m, qs, log=lambda *x: None)
    P = Problem(n, m, list(range(1, n, 2))[:140], own, beta=0, log=lambda *x: None)
    ldl = math.log2(abs(P.det)) if False else float(mp.log(abs(mp.mpf(P.det)), 2))
    for name, prof in (('witness', own), ('default', pf)):
        R = Rows(n, m, prof)
        g, q = gaussian(R, ldl); e = estimate(R, ldl)
        if e is None: print(name, 'LP infeasible or no convergence; gaussian', g, q); continue
        tilted, sol = e; t = sol['t']
        print(f'{name}: rho {R.rho}, L {R.L}; Gaussian log2E {g:.1f} (penalty {q:.1f}); tilted log2E {tilted:.1f}; S {sol["S"]/math.log(2):.1f} bits of {R.L}; |t| mean {np.abs(t).mean():.3f}, quantiles 10,50,90,99%: {np.round(np.quantile(np.abs(t),[.1,.5,.9,.99]),3)}; solve resid {sol["resid"]:.1e}', flush=True)
        if name == 'witness':
            a = np.array([f[(x + n - 1) // 2] for x in R.xs], dtype=float)
            agree = float(np.mean(np.sign(t) == a))
            ll = float(np.sum(np.log((1 + a * t) / 2)))
            print(f'  the witness against its own tilts: sign agreement {agree:.3f}; log2 probability {ll/math.log(2):.1f} (fair coins: {-R.L}); by |t| bin:', [(round(lo, 1), round(float(np.mean(np.sign(t)[(abs(t) >= lo) & (abs(t) < lo + .2)] == a[(abs(t) >= lo) & (abs(t) < lo + .2)])), 2), int(((abs(t) >= lo) & (abs(t) < lo + .2)).sum())) for lo in (0, .2, .4, .6, .8)], flush=True)
