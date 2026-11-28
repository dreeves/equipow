#!/usr/bin/env python3
"""The tilted search as a sweep (Fable 5.2, 2026-11-27): a profile's K best cosets, in order of the estimate, each enumerated once.
Usage: sweep.py n m W qs PROF K COUNT LOG FOUND --floor F --sag S --cap C

tilted.py draws its cosets with a random field, so a later run mostly draws an earlier run's cosets again, and gives each the same
node budget.  Here one beam call with no noise and no field lists the K best cosets by the estimate (log2 E = E0 - Gamma / (2 ln 2));
cosets 0 to COUNT - 1 of that list are enumerated in that order, CHUNK at a time, with --cap nodes each.  At 528:12, W = 190,
floor 4, sag 0.4, a coset's pruned tree ends within 1.5e8 nodes, so --cap 1e9 enumerates every tree to its end: of 71 planted
solutions the enumerator found 19 within 1e7 nodes and 68 within 1e9 (scratch/rethink528-20261127/NOTES.md).

  PROF   a file of the pins: JSON, {modulus: its class sums}, as tilted.py's --prof.
  LOG    JSON lines, one a chunk, appended: the list (digest of its signs, K), COUNT, the profile's whole mass (total: the sum of E
         over every coset, its leading Gaussian count), the chunk's first and last coset, its nodes, how many cosets met the cap, the
         sum of E over its cosets (mass), its CPU seconds, the time, and the codes found in it.  A run goes on from the log's last
         chunk, so a stopped sweep is restarted by the same command, and a larger COUNT extends it.  A log of another list stops it,
         and so does a log that another sweep holds: a sweep keeps its log locked while it runs.
  FOUND  JSON lines, one a witness, appended: each checked by the search's own exact order and by verify_witness.py.

Every coset of the list is enumerated, witness or not, so the witnesses found measure the estimate.  Quals: quals_tilted.py.
"""
import sys, os, json, math, time, fcntl, hashlib, argparse, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np, mpmath as mp
from tilted import Tilted

CHUNK = 250          # cosets to a call of the enumerator, and to a line of the log


def whole_bits(t):
    """log2 of the sum of E over every coset of t's profile: E0 with the covariance of all positions in place of the free set's."""
    S = mp.matrix(t.rho, t.rho)
    for x in list(t.P.F) + list(t.xs):
        col = [(i, c) for i, c in enumerate(t.P.vis_col(x)) if c]
        w = 1 - mp.mpf(float(t.t[x])) ** 2
        for i, ci in col:
            for j, cj in col:
                S[i, j] += w * ci * cj
    L = mp.cholesky(S)
    return t.E0 + t.logdetSw / 2 - float(mp.fsum(mp.log(L[i, i], 2) for i in range(t.rho)))


def checked(n, m, code):
    """The code, once verify_witness.py has found its order to be at least m by its three counts."""
    r = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'verify_witness.py'), str(n), str(m), code], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and f'>= {m}' in r.stdout.splitlines()[-1], (code, r.stdout, r.stderr)
    return code


if __name__ == '__main__':
    assert __debug__
    ap = argparse.ArgumentParser()
    for name in ('n', 'm', 'W'): ap.add_argument(name, type=int)
    ap.add_argument('qs'); ap.add_argument('prof'); ap.add_argument('K', type=int); ap.add_argument('count', type=int); ap.add_argument('log'); ap.add_argument('found')
    ap.add_argument('--floor', type=float, required=True); ap.add_argument('--sag', type=float, required=True); ap.add_argument('--cap', type=float, required=True)
    a = ap.parse_args()
    assert 0 < a.count <= a.K and a.K * 700 < 3 << 30, 'the beam holds about 700 bytes a candidate'
    prof = json.load(open(a.prof))
    t = Tilted(a.n, a.m, a.W, 1.1, [(int(q), prof[q]) for q in a.qs.split(',')], log=lambda *x: None)
    S, G, _ = t.beam(a.K, a.K, 0.0, 1)
    assert len(S) == a.K, f'the beam has {len(S)} finishers'
    order = np.argsort(G, kind='stable'); S = np.ascontiguousarray(S[order]); G = G[order]
    assert len({row.tobytes() for row in S}) == a.K, 'a coset is in the list twice'
    digest = hashlib.sha256(S.tobytes()).hexdigest()[:16]
    E = 2.0 ** (t.E0 - G / (2 * math.log(2))); total = 2.0 ** whole_bits(t)
    with open(a.log, 'a+') as log:
        fcntl.flock(log, fcntl.LOCK_EX | fcntl.LOCK_NB)        # one sweep a log: a second one on this list stops here
        log.seek(0); rows = [json.loads(line) for line in log]
        assert all((r['digest'], r['K']) == (digest, a.K) for r in rows), 'the log is of another list'
        starts = [0] + [r['last'] + 1 for r in rows]
        assert [r['first'] for r in rows] == starts[:-1], 'the log skips or repeats cosets'
        for first in range(starts[-1], a.count, CHUNK):
            block = S[first:min(first + CHUNK, a.count)]; c0 = time.process_time()
            sols, idx, st, _ = t.enum(block, a.floor, a.cap, maxsol=CHUNK, sag=a.sag)       # the enumerator stops a coset at its first solution
            assert st[0] == len(block)
            wits = [dict(zip(('order', 'code'), t.witness(block[i], sg)), coset=first + int(i), logE=float(math.log2(E[first + i]))) for sg, i in zip(sols, idx)]
            with open(a.found, 'a') as found:
                for w in wits:
                    print(json.dumps(dict(w, n=a.n, m=a.m, W=a.W, qs=a.qs, K=a.K, digest=digest, code=checked(a.n, a.m, w['code']), time=time.time())), file=found, flush=True)
            print(json.dumps(dict(digest=digest, K=a.K, count=a.count, total=total, first=first, last=first + len(block) - 1, nodes=int(st[1]), capped=int(st[3]),
                                  mass=float(E[first:first + len(block)].sum()), cpu_s=round(time.process_time() - c0, 3), time=time.time(), found=[w['code'] for w in wits])), file=log, flush=True)
