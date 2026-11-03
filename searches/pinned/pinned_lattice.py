#!/usr/bin/env python3
"""The integer kernel of a free set's rows, its Gram-Schmidt data, and enumeration of the +-1 vectors in a coset of it (pinned_enum.cpp)."""
import ctypes, os
from math import sqrt
import numpy as np
from fpylll import IntegerMatrix, LLL, BKZ

lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libpinned_enum.so'))
lib.enum_cvp.restype = ctypes.c_longlong
dp = ctypes.POINTER(ctypes.c_double); i32p = ctypes.POINTER(ctypes.c_int32); i64p = ctypes.POINTER(ctypes.c_int64)
i8p = ctypes.POINTER(ctypes.c_int8); llp = ctypes.POINTER(ctypes.c_longlong)


def split_embedded(rows, idx):
    """Rows of an embedded LLL whose tail is zero, split into a homogeneous basis (0 at the embedding coordinate idx) and one particular row (+1 there, or
    None): a reduced basis can carry the embedding coordinate on every row, so a Euclidean step is needed before anything can be read off."""
    rows = [list(r) for r in rows]
    active = [r for r in rows if r[idx] != 0]
    hom = [r for r in rows if r[idx] == 0]
    while len(active) > 1:
        active.sort(key=lambda r: abs(r[idx]))
        p = active[0]
        rest = []
        for r in active[1:]:
            q = r[idx] // p[idx]
            r2 = [a - q * b for a, b in zip(r, p)]
            if r2[idx] == 0: hom.append(r2)
            else: rest.append(r2)
        active = [p] + rest
    if not active or abs(active[0][idx]) != 1: return hom, None
    p = active[0]
    return hom, ([-a for a in p] if p[idx] == -1 else p)


def kernel(rows, f):
    """Integer kernel basis of the rows (lists of f integers), by LLL on [I | N rows^T]."""
    t = max(abs(v) for row in rows for v in row)
    N = 2 ** (t.bit_length() + 120)
    M = IntegerMatrix(f, f + len(rows))
    for i in range(f):
        M[i, i] = 1
        for j, row in enumerate(rows): M[i, f + j] = N * row[i]
    LLL.reduction(M, delta=0.99)
    return [list(M[i])[:f] for i in range(f) if not any(list(M[i])[f:])]


class Lattice:
    """A reduced basis K of a kernel (rows of integers), its Gram-Schmidt data, Babai reduction and enumeration."""
    def __init__(self, K, beta=20):
        B = IntegerMatrix.from_matrix(K)
        LLL.reduction(B, delta=0.99)
        if beta: BKZ.reduction(B, BKZ.Param(block_size=beta, max_loops=8, flags=BKZ.MAX_LOOPS | BKZ.AUTO_ABORT))
        self.K = [list(B[i]) for i in range(B.nrows)]
        self.B = np.array(self.K, dtype=np.int32)
        Bf = self.B.astype(np.float64)
        self.d, self.f = Bf.shape
        Q = np.zeros((self.d, self.f)); rr = np.zeros(self.d); mu = np.zeros((self.d, self.d))
        for i in range(self.d):
            v = Bf[i].copy()
            if i:
                c = Q[:i] @ v; v -= c @ Q[:i]
                c2 = Q[:i] @ v; v -= c2 @ Q[:i]
            rr[i] = v @ v
            Q[i] = v / sqrt(rr[i])
        for i in range(self.d): mu[i, :i] = (Q[:i] @ Bf[i]) / np.sqrt(rr[:i])
        self.Q, self.rr, self.mu = Q, rr, mu

    def babai(self, a1):
        """Reduce a1 by 2K so that it stays small: exact integers on a1, floats only to choose the coefficients."""
        a = list(a1)
        Bf = self.B.astype(np.float64)
        for _ in range(8):
            af = np.array([float(w) for w in a])
            changed = False
            for i in range(self.d - 1, -1, -1):
                c = round(float((af / 2) @ self.Q[i]) / sqrt(self.rr[i]))
                if c:
                    changed = True
                    a = [w - 2 * c * r for w, r in zip(a, self.K[i])]
                    af = af - 2.0 * c * Bf[i]
            if not changed: break
        assert max(abs(w) for w in a) < 2 ** 40, 'babai did not settle'
        return a

    def cvp(self, a1, bound_fn=None, max_nodes=10 ** 9, maxsol=1000):
        """All a = a1 + 2z, z in K, with a in {+-1}^f within the bounds: (signs array, nodes, R2, count).  R2 is the coset's budget, f/4 less the squared
        norm of a1/2 outside the span of K."""
        a1 = np.array(a1, dtype=np.int64)
        d, f = self.d, self.f
        proj = (a1 / 2.0) @ self.Q.T
        tau = proj / np.sqrt(self.rr)
        R2 = f / 4.0 - ((a1 @ a1) / 4.0 - proj @ proj)
        bound = np.full(d, R2 + 1e-6) if bound_fn is None else np.array([min(R2 + 1e-6, bound_fn(k + 1, d, R2)) for k in range(d)])
        out = np.zeros((maxsol, f), dtype=np.int8)
        nodes = ctypes.c_longlong(0)
        ns = lib.enum_cvp(ctypes.c_int(d), ctypes.c_int(f), self.mu.ctypes.data_as(dp), self.rr.ctypes.data_as(dp), tau.ctypes.data_as(dp),
                          bound.ctypes.data_as(dp), self.B.ctypes.data_as(i32p), a1.ctypes.data_as(i64p), ctypes.c_longlong(max_nodes),
                          ctypes.c_longlong(maxsol), out.ctypes.data_as(i8p), ctypes.byref(nodes), None)
        return out[:min(ns, maxsol)], nodes.value, R2, ns


def bound_fn(c, floor):
    """The pruning bound on the partial squared norm over the last k Gram-Schmidt directions: a solution's in-span norm R2 spreads evenly on average, so
    the mean is (k/d) R2.  c = 0 and floor 1 or 2 found every result here; on the 1440:14 control every tighter shape found nothing."""
    return lambda k, d, R2: (k / d) * R2 * (1 + c * sqrt(2.0 / k)) + floor
