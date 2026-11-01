#!/usr/bin/env python3
"""Exhaustive search: is there a +-1 sequence of length 240 whose power sums vanish up to order 11 (240 in L_11)?

Split into cases by the residue discrepancy vectors d_4 and d_7 (how the +1's are distributed mod 4 and mod 7),
then solve each case with CP-SAT using all cores. Each case model contains
  * the exact moment equations  sum_p a_p C(p-120, k) = 0,  k = 0..order-1   (a_p = +-1),
  * the fixed counts mod 4 and mod 7 for the case,
  * residue-lattice cuts mod 27, 25, 32, 11, 13 (implied by the exact equations, included to help the solver).
If every case comes back INFEASIBLE, no such sequence exists. If any case is FEASIBLE, the witness is verified
with exact integer power sums and saved, and the run stops.

Usage:   pip install ortools sympy
         python3 overnight_240.py                      # defaults: order 11, 1200 s per case, all cores
         python3 overnight_240.py --minutes 30         # more time per case
Results are checkpointed in overnight_240_state.json, so the run can be stopped and restarted; finished cases are
skipped. The log is overnight_240.log.
"""
import os, sys, json, time, argparse
from math import comb
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form
from ortools.sat.python import cp_model

N = 240
WITNESS_240_10 = "C394E65AB989457A86B7D0D921636E"     # published symmetric LP of length 240 and order 10


def log(msg, fh=None):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    if fh: fh.write(line + '\n'); fh.flush()


def gbinom(q, k):                                       # C(q, k) for any integer q
    return comb(q, k) if q >= 0 else (-1) ** k * comb(k - q - 1, k)


def lattice_basis(M, m, b):
    """Columns spanning {coefficient vectors of (x-1)^m (x+1)^b g(x) mod x^M - 1}."""
    poly = [1]
    for root, times in ((1, m), (-1, b)):
        for _ in range(times):
            poly = [(poly[i - 1] if i > 0 else 0) - root * (poly[i] if i < len(poly) else 0) for i in range(len(poly) + 1)]
    G = []
    for k in range(M):
        v = [0] * M
        for t, c in enumerate(poly): v[(t + k) % M] += c
        G.append(v)
    H = hermite_normal_form(sp.Matrix(G).T)
    return [[int(H[r, j]) for j in range(H.shape[1])] for r in range(M)]


def add_lattice(md, dvec, B, tag):
    """Constrain the integer-expression vector dvec to lie in the lattice spanned by the columns of B."""
    M, K = len(B), (len(B[0]) if B and B[0] else 0)
    mx = max([abs(e) for row in B for e in row] + [1])
    zb = (2 ** 58) // (mx * M * 4)
    z = [md.NewIntVar(-zb, zb, f'{tag}_{j}') for j in range(K)]
    for r in range(M):
        md.Add(dvec[r] == sum(B[r][j] * z[j] for j in range(K) if B[r][j]))


def size(M, r): return len(range(r, N, M))


def residue_vectors(M, order, normalize):
    """All d_M = (#A - #B per class mod M) allowed by the residue-lattice condition (and |A| = |B|)."""
    b = 1 if N < 2 ** order else 0
    B = lattice_basis(M, order, b)
    md = cp_model.CpModel()
    c = [md.NewIntVar(0, size(M, r), f'c{r}') for r in range(M)]
    md.Add(sum(c) == N // 2)
    add_lattice(md, [2 * c[r] - size(M, r) for r in range(M)], B, 'z')
    if normalize: md.Add(2 * c[0] - size(M, 0) >= 0)      # A <-> B switch, used once
    out = []
    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(s): super().__init__()
        def on_solution_callback(s): out.append(tuple(2 * s.Value(c[r]) - size(M, r) for r in range(M)))
    sv = cp_model.CpSolver(); sv.parameters.enumerate_all_solutions = True; sv.parameters.num_workers = 1
    st = sv.Solve(md, CB())
    assert st == cp_model.OPTIMAL, 'enumeration did not finish'
    return sorted(set(out))


def joint_ok(d4, d7, order):
    """Are d_4 and d_7 compatible as counts mod 28 (with the mod-4 and mod-7 lattice conditions)?"""
    md = cp_model.CpModel()
    c = [md.NewIntVar(0, size(28, r), f'c{r}') for r in range(28)]
    for q in range(4): md.Add(sum(2 * c[r] - size(28, r) for r in range(28) if r % 4 == q) == d4[q])
    for q in range(7): md.Add(sum(2 * c[r] - size(28, r) for r in range(28) if r % 7 == q) == d7[q])
    sv = cp_model.CpSolver(); sv.parameters.num_workers = 1; sv.parameters.max_time_in_seconds = 60
    return sv.Solve(md) != cp_model.INFEASIBLE      # keep the case unless provably incompatible


def build_model(order, d4, d7, cut_moduli, fix=None):
    b = 1 if N < 2 ** order else 0
    md = cp_model.CpModel()
    x = [md.NewBoolVar(f'x{p}') for p in range(N)]                     # a_p = 2 x_p - 1
    for k in range(order):                                               # exact moment equations
        w = [gbinom(p - N // 2, k) for p in range(N)]
        md.Add(sum(2 * w[p] * x[p] for p in range(N) if w[p]) == sum(w))
    for M, d in ((4, d4), (7, d7)):                                      # the case
        for r in range(M):
            md.Add(sum(x[p] for p in range(r, N, M)) == (size(M, r) + d[r]) // 2)
    for M in cut_moduli:                                                 # implied residue cuts
        add_lattice(md, [sum(2 * x[p] for p in range(r, N, M)) - size(M, r) for r in range(M)],
                    lattice_basis(M, order, b), f'cut{M}')
    if fix is not None:
        for p in range(N): md.Add(x[p] == fix[p])
    return md, x


def exact_order(a):
    k = 0
    while sum(a[i] * i ** k for i in range(len(a))) == 0: k += 1
    return k


def from_hex(h, m):
    bits = bin(int(h, 16))[2:].zfill(4 * len(h)); l = [1 if ch == '1' else -1 for ch in bits]
    return l + [(-1) ** m * v for v in reversed(l)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--order', type=int, default=11)
    ap.add_argument('--minutes', type=float, default=20.0, help='time limit per case')
    ap.add_argument('--workers', type=int, default=0, help='CP-SAT workers per case (0 = all cores)')
    ap.add_argument('--cuts', default='27,25,32,11,13')
    args = ap.parse_args()
    workers = args.workers or (os.cpu_count() or 8)
    cuts = [int(v) for v in args.cuts.split(',') if v]
    tag = f'overnight_{N}_order{args.order}'
    fh = open(f'{tag}.log', 'a')
    state_file = f'{tag}_state.json'
    state = json.load(open(state_file)) if os.path.exists(state_file) else {}

    log(f'start: n={N}, order={args.order}, {workers} workers, {args.minutes} min per case, cuts mod {cuts}', fh)

    # Control: the published order-10 witness must satisfy the order-10 version of the same model.
    w = from_hex(WITNESS_240_10, 10)
    wx = [(v + 1) // 2 for v in w]
    wd4 = tuple(sum(w[p] for p in range(r, N, 4)) for r in range(4))
    wd7 = tuple(sum(w[p] for p in range(r, N, 7)) for r in range(7))
    md, _ = build_model(10, wd4, wd7, cuts, fix=wx)
    sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = 60
    ok = sv.Solve(md) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    log(f'control (known order-10 witness accepted by the order-10 model): {ok}', fh)
    if not ok: log('CONTROL FAILED - stopping; the model is wrong.', fh); sys.exit(1)

    d7s = residue_vectors(7, args.order, normalize=True)
    d4s = residue_vectors(4, args.order, normalize=False)
    cases = [(d4, d7) for d7 in d7s for d4 in d4s if joint_ok(d4, d7, args.order)]
    log(f'{len(d7s)} d_7 vectors (after the A<->B switch), {len(d4s)} d_4 vectors, {len(cases)} compatible cases', fh)

    for i, (d4, d7) in enumerate(cases, 1):
        key = f'd4={list(d4)} d7={list(d7)}'
        if state.get(key, {}).get('status') in ('INFEASIBLE', 'FEASIBLE'):
            log(f'case {i}/{len(cases)} {key}: already {state[key]["status"]}, skipping', fh); continue
        md, x = build_model(args.order, d4, d7, cuts)
        sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = 60 * args.minutes; sv.parameters.num_workers = workers
        t0 = time.time(); st = sv.Solve(md); dt = time.time() - t0
        name = sv.StatusName(st)
        state[key] = {'status': name, 'seconds': round(dt)}
        json.dump(state, open(state_file, 'w'), indent=1)
        log(f'case {i}/{len(cases)} {key}: {name} ({dt:.0f} s)', fh)
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            a = [2 * sv.Value(v) - 1 for v in x]
            eo = exact_order(a)
            X = [p + 1 for p in range(N) if a[p] == 1]
            json.dump({'n': N, 'exact_order': eo, 'X_1based': X}, open(f'{tag}_WITNESS.json', 'w'))
            log(f'*** WITNESS FOUND: exact order {eo}; saved to {tag}_WITNESS.json ***', fh)
            return

    done = [k for k, v in state.items() if v['status'] == 'INFEASIBLE']
    open_cases = [k for k, v in state.items() if v['status'] not in ('INFEASIBLE', 'FEASIBLE')]
    log(f'summary: {len(done)} of {len(cases)} cases INFEASIBLE, {len(open_cases)} without a verdict', fh)
    if len(done) == len(cases):
        log(f'ALL CASES INFEASIBLE: no +-1 sequence of length {N} has order >= {args.order}.', fh)
    else:
        log('Not finished. Rerun (optionally with a larger --minutes) to retry the open cases.', fh)


if __name__ == '__main__':
    main()
