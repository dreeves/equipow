"""The residue enumeration of the proof searches (focus.py, focus432.py, focus480.py and focus672.py), moved here
verbatim from mstar.py on 2026-10-26 (dreeves: "if that's what you recommend, sure"): focus.fingerprint covers this
file in place of mstar.py, whose tables NEW, PAGE_CODES and RESIDUE change with each new result, so that recording one
cannot stop a run.  mstar.py imports all of it back, for its claims and its other callers.

mstar.py's docstring defines the vocabulary used here: size(M, r), residue sums, the residue lattice L(M, m), L+(M, m)
(with the proof that it has the same admissible vectors when n < 2^m), parent, admissible, node and sweep.
quals_mstar.py checks this code through mstar's names, and quals_focus432.py checks that it is mstar.py's, moved.
"""
from functools import lru_cache
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form


def digits(M):
    """The classes r mod M = p^k by the base-p digits of r, lowest first, so that the members of each class mod p^j,
    j < k, are contiguous (those of a class mod M/p are p in a row).  For a prime M it is 0, 1, ..., M-1."""
    p = min(q for q in range(2, M + 1) if M % q == 0)
    k = 0
    while p ** k < M: k += 1
    assert p ** k == M, M
    return tuple(sorted(range(M), key=lambda r: [r // p ** i % p for i in range(k)]))


# SWEEPS[sweep](M): the classes mod M in the order of the sweep.
SWEEPS = {'natural': lambda M: tuple(range(M)), 'digits': digits}


@lru_cache(maxsize=None)
def lattice(M, m, plus):
    """L(M, m), or L+(M, m) when plus, as the columns of sympy's Hermite normal form of its generators, the coefficient
    vectors of x^k (x-1)^m mod x^M - 1, k = 0..M-1, each times x + 1 when plus."""
    poly = [1]
    for root in [1] * m + [-1] * plus: poly = [a - root * b for a, b in zip([0] + poly, poly + [0])]   # lowest first
    G = [[0] * M for _ in range(M)]
    for k in range(M):
        for t, c in enumerate(poly): G[k][(t + k) % M] += c
    return hermite_normal_form(sp.Matrix(G).T)


@lru_cache(maxsize=None)
def basis(M, m, sweep, plus):
    """Columns spanning lattice(M, m, plus) in Hermite normal form with the coordinates in the order
    SWEEPS[sweep](M), and each column's pivot (its last nonzero row): the pivots increase and their entries are
    positive (asserted), as residue_vectors needs.  It is the Hermite normal form of lattice(M, m, plus)'s rows so
    reordered: the same lattice, and for some sweeps far faster than from the generators (L(25, 13) in 'digits':
    0.01 s against 126 s)."""
    H = lattice(M, m, plus)
    H = hermite_normal_form(sp.Matrix([[H[r, j] for j in range(H.shape[1])] for r in SWEEPS[sweep](M)]))
    B = tuple(tuple(int(H[i, j]) for j in range(H.shape[1])) for i in range(M))
    piv = tuple(max(i for i in range(M) if B[i][j]) for j in range(len(B[0])))
    assert list(piv) == sorted(set(piv)) and all(B[piv[j]][j] > 0 for j in range(len(piv))), (M, m)
    return B, piv


class Capped(Exception):
    """An enumeration ran out of its Budget, so it proves nothing."""


class Budget:
    def __init__(self, limit): self.limit, self.used = limit, 0

    def spend(self):
        self.used += 1
        if self.used > self.limit: raise Capped(self.limit)


def residue_vectors(n, M, m, parent, budget, sweep):
    """Yield every admissible vector of residue sums mod M at order m >= 1 (under parent = (P, W), or None), by
    back substitution in basis(M, m, sweep, n < 2^m) (L+(M, m) when n < 2^m, which has the same admissible vectors),
    as overnight_v5.admissible does (in the sweep 'natural'): going down the rows, a pivot row i of column j takes
    d_i = base + B[i][j] z_j for each z_j that keeps d_i in range, and any other row is determined by the coefficients
    already chosen.  A row is kept only if d_i meets the size and parity conditions and the rows still to come in its
    class mod P can still reach the parent's sum.  Each call of climb spends a node of the budget."""
    assert m >= 1 and M >= 2
    B, piv = basis(M, m, sweep, n < 2 ** m)
    cls = SWEEPS[sweep](M)                              # row i holds the residue sum of the class cls[i] mod M
    s = [(n - r + M - 1) // M for r in cls]            # len(range(r, n, M)), which overflows past 2^63
    P, W = parent or (1, (0,))                          # without a parent, sum_r D_r = f(1) = 0
    assert M % P == 0 and len(W) == P, (M, parent)
    room = [sum(s[t] for t in range(i) if cls[t] % P == cls[i] % P) for i in range(M)]   # the classmates below row i
    part = [0] * P
    z, d = [0] * len(piv), [0] * M

    def place(i, j, di):                                # set d_i = di if it fits, then go on down
        q = cls[i] % P
        rest = W[q] - part[q] - di
        if abs(di) <= s[i] and (di - s[i]) % 2 == 0 and abs(rest) <= room[i] and (rest - room[i]) % 2 == 0:
            d[i] = di
            part[q] += di
            yield from climb(i - 1, j)
            part[q] -= di

    def climb(i, j):                                    # rows above i are placed; columns above j are chosen
        budget.spend()
        if i < 0:
            assert part == list(W)
            D = [0] * M
            for k, r in enumerate(cls): D[r] = d[k]
            yield tuple(D)
            return
        base = sum(B[i][c] * z[c] for c in range(j + 1, len(piv)))
        if j >= 0 and piv[j] == i:                      # a pivot row: choose the coefficient z_j
            h = B[i][j]
            for t in range(-((s[i] + base) // h), (s[i] - base) // h + 1):
                z[j] = t
                yield from place(i, j - 1, base + h * t)
        else:                                           # a row determined by the coefficients already chosen
            yield from place(i, j, base)

    yield from climb(M - 1, len(piv) - 1)
