#!/usr/bin/env python3
"""The pin vectors chosen by the tilted estimate rather than by energy: coordinate descent over each modulus's cheapest admissible vectors.  Usage: profsearch.py n m qs [per-modulus candidates] > best profile as JSON on the last line"""
import sys, os, math, time, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pinned'))
from entropy import *
import pinned_profiles
n, m = int(sys.argv[1]), int(sys.argv[2]); qs = [int(q) for q in sys.argv[3].split(',')]; top = int(sys.argv[4]) if len(sys.argv) > 4 else 64
s = 1 if m % 2 == 0 else -1
cands = {}
for q in qs:
    use, Dvec, good = pinned_profiles.enumerate_profiles(n, q, m, s, maxout=4000, slack=30.0)
    vs = []
    for c, e in good:
        D = Dvec(e)
        vs.append((c, list(D)))
    cands[q] = vs[:top]
    print(f'mod {q}: {len(good)} vectors within the slack, costs {good[0][0]:.1f}..{good[-1][0]:.1f}', flush=True)
def score(prof):
    R = Rows(n, m, prof)
    sol = R.solve()
    if sol is None: return None
    t = sol['t']; w = np.maximum(1 - t * t, 1e-12)
    sign, ld = np.linalg.slogdet((R.F * w) @ R.F.T)
    return sol['S'] / math.log(2) - ld / 2 / math.log(2), sol['S'] / math.log(2)
cur = {q: cands[q][0][1] for q in qs}
best = score([(q, cur[q]) for q in qs]); print('start, the cheapest vectors:', best, flush=True)
start = best
for sweep in range(4):
    changed = False
    for q in qs:
        bv, bs = cur[q], best
        for c, D in cands[q]:
            if D == cur[q]: continue
            sc = score([(p, D if p == q else cur[p]) for p in qs])
            if sc is not None and (bs is None or sc[0] > bs[0] + 1e-6): bs, bv = sc, D
        if bv != cur[q]:
            print(f' sweep {sweep} mod {q}: score {bs[0]:.2f} (S {bs[1]:.1f}) {bv}', flush=True); cur[q] = bv; best = bs; changed = True
    if not changed: break
print(f'{n}:{m}: tilted score from {start[0] if start else None} to {best[0]:.2f}, gain {best[0] - (start[0] if start else 0):.1f} bits', flush=True)
print(json.dumps({str(q): cur[q] for q in qs}))
