"""width: the lattice directions of certbb's width test (certbb.py defines the width test, a thin direction and a cut).

The exact rows A x = b of a choice (certbb.Lp's independent rows: the moment rows, then the count rows it keeps)
have an integer kernel lattice, the c in Z^N with A c = 0.  For the rows of a run it is the span of the shifts of
one polynomial: c is in it iff c(x) = sum_p c_p x^p is divisible by (x - 1)^order (the moment rows, which span the
polynomials of degree below the order in the position) and by x^M - 1 for each modulus M of the node (the count
rows: the class sums are c(x) mod x^M - 1), that is by their lcm K(x) = (x - 1)^order prod Phi_d over the divisors
d > 1 of the moduli (Phi_d the cyclotomic polynomials); K is monic, so divisibility over Q is divisibility over Z.
directions() builds that basis Q (N - deg K shifts), reduces it by LLL into R = T Q (T unimodular, tracked exactly
through its inverse), and takes for each reduced vector j the direction u_j in Z^N with R u_j = e_j, an integer lift
of the dual basis (the lattice coordinate of Aardal, Hurkens and Lenstra), from j = dim - 1 down: the last reduced
vectors are the longest, and their coordinates vary least over the choice's polytope (the verification's scans found
the thin directions among the last three).  On the LP's affine subspace A x = b, u_j . x = w_j . x + kappa_j with
w_j = u_j - A^T n_j the exact projection of u_j off the row space (n_j rational, by a fraction-free solve of
(A A^T) n_j = A u_j) and kappa_j = n_j . b: w_j is what the LP sees, which keeps its values small, and kappa_j is the
choice's offset.  Nothing here is relied on for soundness (certbb's exact checks of the certificates a direction
leads to are), so the identities are asserted as they are made: every row kills every basis vector, there are deg K
rows and A A^T is nonsingular (so rank + dim = N), the Bareiss divisions are exact, R u_j = e_j, A w_j = 0.  Cached
per (order, moduli, A) in each process; in overnight_v5's runs that is per cascade prefix, once per worker (about 3
CPU-s at the bottom of 240@11).

Vocabulary, each term defined once here:
  kernel polynomial  K(x) as above, kernel_poly(order, moduli), its coefficients lowest degree first.
  kernel basis       Q, kernel_basis(order, moduli, N): row j the coefficients of x^j K(x), j < N - deg K.
  direction          Direction(j, u, num, den, w): u = u_j as a tuple of N ints; num and den (ints, den > 0, coprime
                     with the entries of num) with n_j = num / den; w = w_j as floats, the LP row.
  offset             kappa_j for a choice's right-hand sides b: offset(direction, b) = (floor, frac), kappa_j =
                     floor + frac exactly with frac in [0, 1) as a float, so that u.x = w.x + frac + floor and the LP's
                     value w.x + frac (small) says where u.x lies between integers.
"""
import math
from functools import lru_cache
from collections import namedtuple
import numpy as np
import sympy as sp

DELTA = 0.99                 # LLL's reduction parameter: delta of the Lovasz condition
LIMIT = 2 ** 62              # LLL's int64 guard: an exact bound on every entry a row operation makes stays under it
                             # (asserted), so the int64 arithmetic is exact
SWAPS = 10 ** 6              # LLL stops with an assertion after this many swaps (float Gram-Schmidt could cycle)
Direction = namedtuple('Direction', 'j u num den w')


def kernel_poly(order, moduli):
    """The coefficients, lowest degree first, of K(x) = (x - 1)^order prod_{d > 1, d | some modulus} Phi_d(x)."""
    x = sp.symbols('x')
    ds = sorted({d for M in moduli for d in sp.divisors(M)} - {1})
    K = (x - 1) ** order * sp.prod([sp.cyclotomic_poly(d, x) for d in ds])
    return [int(c) for c in reversed(sp.Poly(sp.expand(K), x).all_coeffs())]


def kernel_basis(order, moduli, n):
    """The kernel basis Q (int64, (n - deg K) x n) and the kernel polynomial's coefficients."""
    K = kernel_poly(order, moduli)
    deg = len(K) - 1
    assert deg < n, (deg, n)
    Q = np.zeros((n - deg, n), dtype=np.int64)
    for j in range(n - deg): Q[j, j:j + deg + 1] = K
    return Q, K


def lll(B):
    """LLL on the rows of B (int64): the reduced basis R = T B, the columns of T^-1 as lists of Python ints (so that
    T^-1 e_j is column j), and the Gram-Schmidt norms of R.  Gram-Schmidt in float64 steers the reduction; the row
    operations on B are exact in int64 under the LIMIT guard: rowmax[i] bounds |B[i]|, and a pass over row k asserts,
    before each operation B[k] -= q B[j], that its bound rowmax[k] + sum |q| rowmax[j] so far stays under LIMIT."""
    B = B.copy()
    n = len(B)
    rowmax = [int(np.abs(B[i]).max()) for i in range(n)]
    assert max(rowmax) < LIMIT
    Bf = B.astype(float)
    Bs = np.zeros_like(Bf)
    mu = np.zeros((n, n))
    nrm = np.zeros(n)
    Tinv = [[int(i == j) for i in range(n)] for j in range(n)]       # Tinv[j] is column j

    def gs_row(k):
        v = Bf[k].copy()
        if k:
            mu[k, :k] = (Bf[k] @ Bs[:k].T) / nrm[:k]
            v -= mu[k, :k] @ Bs[:k]
        Bs[k] = v
        nrm[k] = v @ v
        mu[k, k] = 1.0

    for k in range(n): gs_row(k)
    k, swaps = 1, 0
    while k < n:
        gs_row(k)
        acc = rowmax[k]
        for j in range(k - 1, -1, -1):
            q = round(mu[k, j])
            if q:
                acc += abs(q) * rowmax[j]
                assert acc < LIMIT, acc
                B[k] -= q * B[j]
                mu[k, :j + 1] -= q * mu[j, :j + 1]
                cj, ck = Tinv[j], Tinv[k]
                Tinv[j] = [a + q * b for a, b in zip(cj, ck)]          # row op on T  <=>  column op on T^-1
        rowmax[k] = int(np.abs(B[k]).max())
        Bf[k] = B[k]
        gs_row(k)
        if nrm[k] >= (DELTA - mu[k, k - 1] ** 2) * nrm[k - 1]:
            k += 1
        else:
            B[[k - 1, k]] = B[[k, k - 1]]
            Bf[[k - 1, k]] = Bf[[k, k - 1]]
            Tinv[k - 1], Tinv[k] = Tinv[k], Tinv[k - 1]
            rowmax[k - 1], rowmax[k] = rowmax[k], rowmax[k - 1]
            gs_row(k - 1); gs_row(k)
            if k + 1 < n:
                mu[k + 1:, k - 1] = (Bf[k + 1:] @ Bs[k - 1]) / nrm[k - 1]
                mu[k + 1:, k] = (Bf[k + 1:] @ Bs[k]) / nrm[k]
            swaps += 1
            assert swaps < SWAPS
            k = max(k - 1, 1)
    return B, Tinv, np.sqrt(nrm)


def bareiss(G, C):
    """For the nonsingular integer matrix G and the integer matrix C: den = +-det G and the integer matrix Z with
    G Z = den C, by fraction-free elimination (Bareiss: every division is exact, asserted, as is a pivot at each
    step, which a singular G lacks) and back substitution scaled by den (exact divisions, asserted; Z = den G^-1 C is
    integral by Cramer's rule)."""
    n, m = len(G), len(C[0])
    M = [list(g) + list(c) for g, c in zip(G, C, strict=True)]
    prev = 1
    for k in range(n):
        piv = next((i for i in range(k, n) if M[i][k]), None)
        assert piv is not None, 'G is singular'
        M[k], M[piv] = M[piv], M[k]
        for i in range(k + 1, n):
            Mik, Mkk, rowi, rowk = M[i][k], M[k][k], M[i], M[k]
            for j in range(k + 1, n + m):
                q, r = divmod(Mkk * rowi[j] - Mik * rowk[j], prev)
                assert r == 0
                rowi[j] = q
            rowi[k] = 0
        prev = M[k][k]
    den = M[n - 1][n - 1]
    Z = [[0] * m for _ in range(n)]
    for i in range(n - 1, -1, -1):
        for t in range(m):
            q, r = divmod(den * M[i][n + t] - sum(M[i][j] * Z[j][t] for j in range(i + 1, n)), M[i][i])
            assert r == 0
            Z[i][t] = q
    return den, Z


@lru_cache(maxsize=None)
def directions(order, moduli, A):
    """The directions of the rows A (a tuple of tuples of ints: the moment rows of the order, then the count rows
    certbb.Lp keeps for the moduli), in the order j = dim - 1 down to 0.  Asserts that A is what the kernel
    polynomial describes: every row kills every kernel basis vector and there are deg K rows (so the rows span the
    rational row space whose integer kernel the shifts of K span: the lattice is exact)."""
    n = len(A[0])
    Q, K = kernel_basis(order, moduli, n)
    deg, dim = len(K) - 1, len(Q)
    assert len(A) == deg and all(len(row) == n for row in A), (len(A), deg)
    assert all(sum(a * q for a, q in zip(row, Qj)) == 0 for row in A for Qj in Q.tolist())
    R, Tinv, _ = lll(Q)
    U = []
    for j in range(dim):
        z, u = Tinv[j], [0] * n                                  # Q u = T^-1 e_j by back substitution through K
        for i in range(dim):
            u[i + deg] = z[i] - sum(K[t] * u[i + t] for t in range(deg))
        U.append(tuple(u))
    Rl = R.tolist()
    assert all(sum(a * b for a, b in zip(Rl[i], U[j])) == int(i == j) for i in range(dim) for j in range(dim))
    G = [[sum(x * y for x, y in zip(r1, r2)) for r2 in A] for r1 in A]       # A A^T
    C = [[sum(a * t for a, t in zip(row, u)) for u in U] for row in A]       # A U^T
    den, Z = bareiss(G, C)
    out = []
    for j in range(dim - 1, -1, -1):
        col = [Z[i][j] for i in range(deg)]
        g = math.gcd(den, *col) * (1 if den > 0 else -1)
        num, dj = [t // g for t in col], den // g
        W = [dj * t for t in U[j]]
        for row, z in zip(A, num, strict=True):
            for p, c in enumerate(row): W[p] -= z * c
        assert all(sum(c * w for c, w in zip(row, W)) == 0 for row in A), j
        out.append(Direction(j, U[j], num, dj, np.array([t / dj for t in W])))
    return tuple(out)


def offset(direction, b):
    """(floor, frac) of kappa = num . b / den for the right-hand sides b of the direction's rows (see 'offset')."""
    num = sum(z * t for z, t in zip(direction.num, b, strict=True))
    floor, rem = divmod(num, direction.den)
    return floor, rem / direction.den
