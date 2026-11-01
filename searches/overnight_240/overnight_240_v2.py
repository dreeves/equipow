#!/usr/bin/env python3
"""240 in L_11?  (Is there a +-1 sequence of length 240 whose power sums vanish through exponent 10?)

Pipeline:
  0. control: the published order-10 witness passes every exact test of the order-10 version, and satisfies its model.
  1. cases: all compatible (d_4, d_7) residue vectors (counts of +1's mod 4 and mod 7), from a complete enumeration.
  2. exact filter: drop cases where the 11 moment equations + the counts have no integer solution at all.
  3. short CP-SAT pass on each remaining case.
  4. each case still open is split by its counts mod 8; sub-cases failing the exact filter are dropped;
     each surviving sub-case gets a CP-SAT run. Progress, verdicts and an ETA are logged after every sub-case.
All verdicts are checkpointed in overnight_240_v2_state.json; rerunning skips finished work.
If every case/sub-case ends INFEASIBLE, there is no such sequence (CP-SAT is the only non-exact component).

Usage:  pip install ortools sympy
        python3 overnight_240_v2.py                         # defaults: 2 min per case, 5 min per sub-case, all cores
        python3 overnight_240_v2.py --sub-minutes 15        # longer per sub-case (e.g. for a second pass)
"""
import os, sys, json, time, argparse
from math import comb
from fractions import Fraction
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form
from ortools.sat.python import cp_model

N = 240
WITNESS_240_10 = "C394E65AB989457A86B7D0D921636E"
TAG = 'overnight_240_v2'


def log(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    with open(TAG + '.log', 'a') as fh: fh.write(line + '\n')


def gbinom(q, k): return comb(q, k) if q >= 0 else (-1) ** k * comb(k - q - 1, k)
def size(M, r): return len(range(r, N, M))


def lattice_basis(M, m, b):
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
    M, K = len(B), (len(B[0]) if B and B[0] else 0)
    mx = max([abs(e) for row in B for e in row] + [1]); zb = (2 ** 58) // (mx * M * 4)
    z = [md.NewIntVar(-zb, zb, f'{tag}_{j}') for j in range(K)]
    for r in range(M): md.Add(dvec[r] == sum(B[r][j] * z[j] for j in range(K) if B[r][j]))


def enumerate_counts(M, order, normalize=False, parent=None):
    """All count vectors c (mod M) allowed by the residue-lattice condition; optionally refining counts `parent`
    (a vector mod M//2 with c[r] + c[r + M//2] = parent[r])."""
    b = 1 if N < 2 ** order else 0
    md = cp_model.CpModel()
    c = [md.NewIntVar(0, size(M, r), f'c{r}') for r in range(M)]
    md.Add(sum(c) == N // 2)
    add_lattice(md, [2 * c[r] - size(M, r) for r in range(M)], lattice_basis(M, order, b), 'z')
    if normalize: md.Add(2 * c[0] - size(M, 0) >= 0)
    if parent is not None:
        h = M // 2
        for r in range(h): md.Add(c[r] + c[r + h] == parent[r])
    out = []
    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(s): super().__init__()
        def on_solution_callback(s): out.append(tuple(s.Value(v) for v in c))
    sv = cp_model.CpSolver(); sv.parameters.enumerate_all_solutions = True; sv.parameters.num_workers = 1
    assert sv.Solve(md, CB()) == cp_model.OPTIMAL, 'enumeration did not finish'
    return sorted(set(out))


class IntegerSystem:
    """Exact test: does A x = b have an integer solution?  (A fixed, b varies.)"""
    def __init__(self, A):
        H = hermite_normal_form(sp.Matrix(A))                 # columns: basis of the lattice spanned by A's columns
        self.H = [[int(v) for v in H.row(i)] for i in range(H.rows)]
        Hm = sp.Matrix(self.H); P = (Hm.T * Hm).inv() * Hm.T
        self.P = [[Fraction(int(v.p), int(v.q)) for v in P.row(i)] for i in range(P.rows)]
    def solvable(self, b):
        y = [sum(p * bj for p, bj in zip(row, b)) for row in self.P]
        if any(v.denominator != 1 for v in y): return False
        return all(sum(h * int(v) for h, v in zip(hrow, y)) == bi for hrow, bi in zip(self.H, b))


def moment_rows(order):
    rows, rhs = [], []
    for k in range(order):
        w = [gbinom(p - N // 2, k) for p in range(N)]
        rows.append([2 * v for v in w]); rhs.append(sum(w))
    return rows, rhs
def count_rows(M): return [[1 if p % M == r else 0 for p in range(N)] for r in range(M)]


def build_model(order, counts, cuts, fix=None):
    """counts: dict M -> count vector (number of +1's per class mod M)."""
    b = 1 if N < 2 ** order else 0
    md = cp_model.CpModel()
    x = [md.NewBoolVar(f'x{p}') for p in range(N)]
    rows, rhs = moment_rows(order)
    for w, r in zip(rows, rhs): md.Add(sum(w[p] * x[p] for p in range(N) if w[p]) == r)
    for M, c in counts.items():
        for r in range(M): md.Add(sum(x[p] for p in range(r, N, M)) == c[r])
    for M in cuts:
        add_lattice(md, [sum(2 * x[p] for p in range(r, N, M)) - size(M, r) for r in range(M)],
                    lattice_basis(M, order, b), f'cut{M}')
    if fix is not None:
        for p in range(N): md.Add(x[p] == fix[p])
    return md, x


def solve(md, minutes, workers):
    sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = 60 * minutes; sv.parameters.num_workers = workers
    t0 = time.time(); st = sv.Solve(md)
    return sv, st, time.time() - t0


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
    ap.add_argument('--case-minutes', type=float, default=2.0)
    ap.add_argument('--sub-minutes', type=float, default=5.0)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--cuts', default='27,25,32,11,13')
    ap.add_argument('--max-sub', type=int, default=0, help='debug: stop after this many sub-cases')
    args = ap.parse_args()
    workers = args.workers or (os.cpu_count() or 8)
    cuts = [int(v) for v in args.cuts.split(',') if v]
    order = args.order
    state_file = TAG + '_state.json'
    state = json.load(open(state_file)) if os.path.exists(state_file) else {}
    def save(): json.dump(state, open(state_file, 'w'), indent=1)
    log(f'start: n={N}, order={order}, {workers} workers, {args.case_minutes} min per case, {args.sub_minutes} min per sub-case')

    # 0. control on the known order-10 witness
    w = from_hex(WITNESS_240_10, 10); wx = [(v + 1) // 2 for v in w]
    wc = {M: [sum(wx[p] for p in range(r, N, M)) for r in range(M)] for M in (4, 7, 8)}
    r10, h10 = moment_rows(10)
    ok1 = IntegerSystem(r10 + count_rows(4) + count_rows(7)).solvable(h10 + wc[4] + wc[7])
    ok2 = IntegerSystem(r10 + count_rows(7) + count_rows(8)).solvable(h10 + wc[7] + wc[8])
    md, _ = build_model(10, {4: wc[4], 7: wc[7], 8: wc[8]}, cuts, fix=wx)
    sv, st, _ = solve(md, 1, 1)
    ok3 = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    log(f'control: witness passes the exact tests {ok1}, {ok2}; satisfies the order-10 model {ok3}')
    if not (ok1 and ok2 and ok3): log('CONTROL FAILED - stopping.'); sys.exit(1)

    # 1. cases
    c7s = enumerate_counts(7, order, normalize=True); c4s = enumerate_counts(4, order)
    rows, rhs = moment_rows(order)
    cases = [(c4, c7) for c7 in c7s for c4 in c4s]
    # 2. exact filter
    S1 = IntegerSystem(rows + count_rows(4) + count_rows(7))
    live = [(c4, c7) for (c4, c7) in cases if S1.solvable(rhs + list(c4) + list(c7))]
    log(f'cases: {len(c7s)} mod-7 x {len(c4s)} mod-4 count vectors = {len(cases)}; {len(cases) - len(live)} have no integer solution; {len(live)} remain')

    # 3. short pass on each remaining case
    open_cases = []
    for c4, c7 in live:
        key = f'case c4={list(c4)} c7={list(c7)}'
        if state.get(key) == 'INFEASIBLE': log(f'{key}: already INFEASIBLE'); continue
        md, x = build_model(order, {4: c4, 7: c7}, cuts)
        sv, st, dt = solve(md, args.case_minutes, workers)
        state[key] = sv.StatusName(st); save()
        log(f'{key}: {state[key]} ({dt:.0f} s)')
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            a = [2 * sv.Value(v) - 1 for v in x]
            log(f'*** WITNESS FOUND, exact order {exact_order(a)}: X = {[p + 1 for p in range(N) if a[p] == 1]}'); return
        if st != cp_model.INFEASIBLE: open_cases.append((c4, c7))

    # 4. refine open cases by counts mod 8
    S2 = IntegerSystem(rows + count_rows(7) + count_rows(8))
    subs = []
    for c4, c7 in open_cases:
        c8s = enumerate_counts(8, order, parent=c4)
        keep = [c8 for c8 in c8s if S2.solvable(rhs + list(c7) + list(c8))]
        log(f'case c4={list(c4)} c7={list(c7)}: {len(c8s)} mod-8 sub-cases, {len(keep)} with an integer solution')
        subs += [(c4, c7, c8) for c8 in keep]
    todo = [s for s in subs if state.get(f'sub c7={list(s[1])} c8={list(s[2])}') != 'INFEASIBLE']
    if args.max_sub: todo = todo[:args.max_sub]
    t_used, n_done = 0.0, 0
    for i, (c4, c7, c8) in enumerate(todo, 1):
        key = f'sub c7={list(c7)} c8={list(c8)}'
        md, x = build_model(order, {7: c7, 8: c8}, cuts)
        sv, st, dt = solve(md, args.sub_minutes, workers)
        state[key] = sv.StatusName(st); save()
        t_used += dt; n_done += 1
        eta = (len(todo) - i) * t_used / n_done
        log(f'[{i}/{len(todo)}] {key}: {state[key]} ({dt:.0f} s); ETA {eta / 3600:.1f} h')
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            a = [2 * sv.Value(v) - 1 for v in x]
            log(f'*** WITNESS FOUND, exact order {exact_order(a)}: X = {[p + 1 for p in range(N) if a[p] == 1]}'); return

    # summary
    sub_keys = [f'sub c7={list(s[1])} c8={list(s[2])}' for s in subs]
    n_inf = sum(1 for k in sub_keys if state.get(k) == 'INFEASIBLE')
    log(f'summary: {len(cases) - len(live)} cases excluded exactly; {len(live) - len(open_cases)} cases INFEASIBLE by CP-SAT; '
        f'{n_inf} of {len(subs)} sub-cases INFEASIBLE; {len(subs) - n_inf} sub-cases still open')
    if not open_cases or n_inf == len(subs):
        if not args.max_sub: log(f'ALL CASES CLOSED: no +-1 sequence of length {N} has order >= {order}.')
    else:
        log('Not finished. Rerun with a larger --sub-minutes to retry the open sub-cases.')


if __name__ == '__main__':
    main()
