#!/usr/bin/env python3
"""Driver of the pin engine (pe.cpp)."""
import ctypes, json, os, random, sys, time
import numpy as np
lib = ctypes.CDLL(os.path.abspath(os.environ.get('PE_LIB', 'libpex.so')))
dp = ctypes.POINTER(ctypes.c_double); ip = ctypes.POINTER(ctypes.c_int)
lib.pe_set.argtypes = [ctypes.c_int] * 7 + [ctypes.c_double]
def moment_rows(n, m):
    import mpmath as mp
    """Orthonormal polynomials of degree < m on 0..n-1, in mp, by Gram-Schmidt on the binomials: Q (m x n floats) and U with Q_j(p) = sum_t U_jt C(p, t)."""
    mp.mp.dps = 150
    from math import comb
    V = [[mp.mpf(comb(p, t)) for p in range(n)] for t in range(m)]
    Q = []; U = []
    for t in range(m):
        v = list(V[t]); u = [mp.mpf(0)] * m; u[t] = mp.mpf(1)
        for _ in range(2):
            for j in range(len(Q)):
                c = mp.fsum(a * b for a, b in zip(v, Q[j]))
                v = [a - c * b for a, b in zip(v, Q[j])]
                u = [a - c * b for a, b in zip(u, U[j])]
        nr = mp.sqrt(mp.fsum(a * a for a in v))
        Q.append([a / nr for a in v]); U.append([a / nr for a in u])
    return np.array([[float(a) for a in row] for row in Q]), U
def write_config(n, m, mods, path, wmax=200):
    import mpmath as mp
    from cellconfig import problem, is2, size, dual_forms
    out = [f'{n} {m} {len(mods)}']
    for M in mods:
        B, piv, order, R = problem(n, m, M); nb = len(piv); mult = 2 if is2(M) else 1
        out.append(f'{M} {nb} {mult}')
        out.append(' '.join(str(R[r]) for r in order))
        out.append(' '.join(str(size(n, M, r)) for r in range(M)))
        out.append(' '.join(map(str, order)))
        out.append(' '.join(map(str, piv)))
        for i in range(M): out.append(' '.join(str(B[i][c]) for c in range(nb)))
        W = dual_forms(n, m, M)[:wmax]
        out.append(str(len(W)))
        for w in W: out.append(' '.join(map(str, map(int, w))))
    Q, U = moment_rows(n, m)
    for row in U: out.append(' '.join(mp.nstr(a, 30) for a in row))
    open(path, 'w').write('\n'.join(out) + '\n')
    np.save(path + '.Q.npy', Q)
def init(n, m, mods, want, path=None, cap=100000, tests=8, feas=2, wide=3, deep=300, retry=2, sample=3000, enodes=1e6):
    path = path or f'pex_{n}_{m}_{"_".join(map(str, mods))}.cfg'
    if not os.path.exists(path): write_config(n, m, mods, path)
    Q = np.ascontiguousarray(np.load(path + '.Q.npy'))
    lib.pe_init(path.encode(), Q.ctypes.data_as(dp))
    lib.pe_set(cap, tests, feas, wide, deep, retry, sample, enodes)
    w = np.array(want, dtype=np.int32); lib.pe_want(ctypes.c_int(len(w)), w.ctypes.data_as(ip))
def run(node, limit=1e9, dive=False, seed=1, log=None):
    pins = []
    for k, v in node.items(): pins += [int(k)] + [int(x) for x in v]
    a = np.array(pins, dtype=np.int32); st = np.zeros(17)
    lib.pe_run(ctypes.c_int(len(node)), a.ctypes.data_as(ip), ctypes.c_double(limit), ctypes.c_int(int(dive)), ctypes.c_ulonglong(seed), st.ctypes.data_as(dp), (log or '').encode())
    return dict(zip('nodes closed open splits cuts lps iters maxdepth seconds est cost timedout tfilter tsplit tenum capped rayfail'.split(), st.tolist()))

def witness(a):
    w = np.array(a, dtype=np.int32); lib.pe_witness(ctypes.c_int(len(w)), w.ctypes.data_as(ip))
lib.pe_wit_err.restype = ctypes.c_longlong; lib.pe_wit_nodes.restype = ctypes.c_longlong

def run_file(path, limit, log=None, spill=None):
    st = np.zeros(25); rc = lib.pe_run_file(path.encode(), ctypes.c_double(limit), st.ctypes.data_as(dp), (log or '').encode(), (spill or '').encode())
    r = dict(zip('nodes closed open splits cuts lps iters maxdepth seconds est cost timedout tfilter tsplit tenum capped rayfail spilled exactfail tbase thull tcopy dclosed dfixed dsplit'.split(), st.tolist())); r['rc'] = rc; return r
def split_file(path, prefix, log=None):
    return lib.pe_split_file(path.encode(), prefix.encode(), (log or '').encode())
def start_file(node, path):
    pins = []
    for k, v in node.items(): pins += [int(k)] + [int(x) for x in v]
    a = np.array(pins, dtype=np.int32); return lib.pe_start_file(ctypes.c_int(len(node)), a.ctypes.data_as(ip), path.encode())

lib.pe_exact_ok.restype = ctypes.c_longlong; lib.pe_exact_fail.restype = ctypes.c_longlong

lib.pe_sym_removed.restype = ctypes.c_longlong

def run_settings():
    """The settings of the real run, in one place."""
    L = lib
    L.pe_longstep(0); L.pe_pull(3, ctypes.c_double(0.7)); L.pe_restore(1); L.pe_pool(256); L.pe_direct(3, 2); L.pe_skipimplied(1)
    L.pe_prop(1, 1); L.pe_s7first(4); L.pe_s7nopp(1); L.pe_scan(7); L.pe_s7.argtypes = [ctypes.c_double, ctypes.c_double]; L.pe_s7(0.55, 0.9); L.pe_s7early(1); L.pe_symform(8); L.pe_symlate(0)
    L.pe_rtnear(1); L.pe_rtub(1); L.pe_tiles(1); L.pe_incrow(1); L.pe_refreq(500); L.pe_nowt(1); L.pe_dropdep(1); L.pe_sibrest(2); L.pe_skipdone(1); L.pe_tilef(1)
RUN_INIT = dict(tests=8, feas=2, retry=12)
