#!/usr/bin/env python3
"""symlarge.py: the objects of the proof in proofs/symlarge.html, computed exactly, for quals/quals_symlarge.py.
This file is all Claude (Fable 5.2).

The proof shows that at each order m every sufficiently large admissible length has a (-1)^m-symmetric sequence of
order m.  Vocabulary (the same as quals/quals_symlarge.py's):
  s            (-1)^m.  s-symmetric: f_(n-1-i) = s f_i.
  half         eps_1..eps_N: the right half of an s-symmetric sequence of length 2N, read outward from the middle.
  rank(m)      d = floor(m/2): the number of linear conditions that order m puts on a half (the proof's Lemma 1).
  b_k          the proof's basis, k = 0..d-1: C(j+k-1, 2k) for even m, C(j+k, 2k+1) + C(j+k-1, 2k+1) for odd m.
  u(j)         the vector (b_0(j), ..., b_(d-1)(j)); the conditions on a half are sum_j eps_j u(j) = 0.
  period(m)    the least power of 2 above m; admissible: a length that period(m) divides.
  count        the number of halves of length N with sum_j eps_j u(j) = 0.
  gauss        2^N (2/pi)^(d/2) / sqrt(det M), M = sum_(j=1..N) u(j) u(j)^T (the proof's Theorem 2).
"""
import math
from fractions import Fraction
import numpy as np


def rank(m):
    return m // 2


def period(m):
    p = 1
    while p <= m:
        p *= 2
    return p


def admissible(m, n):
    return n % period(m) == 0


def binom(x, r):
    """C(x, r) = x (x - 1) ... (x - r + 1) / r!, for any integer x and r >= 0."""
    assert r >= 0, r
    num = 1
    for i in range(r):
        num *= x - i
    q, rem = divmod(num, math.factorial(r))
    assert rem == 0, (x, r)
    return q


def b(m, k, j):
    """b_k(j) for the order m: a polynomial in j of degree 2k (m even) or 2k + 1 (m odd), with b_k(1 - j) = s b_k(j)."""
    assert 0 <= k < rank(m), (m, k)
    if m % 2 == 0:
        return binom(j + k - 1, 2 * k)
    return binom(j + k, 2 * k + 1) + binom(j + k - 1, 2 * k + 1)


def u(m, j):
    return tuple(b(m, k, j) for k in range(rank(m)))


def keys(m, N):
    """One integer per j = 1..N that stands for u(j): sum_k u_k(j) w_k, with w_k the product of 2 S_i + 1 over i < k and
    S_i = sum_j |u_i(j)|.  A signed sum of the u(j) is zero exactly when the same signed sum of these integers is
    (balanced mixed radix: each coordinate of a signed sum lies in [-S_k, S_k])."""
    us = [u(m, j) for j in range(1, N + 1)]
    w, ws = 1, []
    for k in range(rank(m)):
        ws.append(w)
        w *= 2 * sum(abs(x[k]) for x in us) + 1
    assert w < 2 ** 62, (m, N, w)             # every signed sum fits an int64
    return [sum(x[k] * ws[k] for k in range(rank(m))) for x in us]


def signed_sums(ks):
    """Every sum of +-k over the list ks, as an int64 array of length 2^len(ks)."""
    out = np.zeros(1, dtype=np.int64)
    for k in ks:
        out = np.concatenate((out + k, out - k))
    return out


def count(m, N):
    """The number of halves eps of length N with sum_j eps_j u(j) = 0, by a meet in the middle: the signed sums over
    j <= N/2, sorted, against the negated signed sums over the rest."""
    ks = keys(m, N)
    assert N <= 50, N                         # 2^25 sums a side at most
    left, right = signed_sums(ks[:N // 2]), signed_sums(ks[N // 2:])
    left.sort()
    total = 0
    for i in range(0, len(right), 1 << 20):
        x = -right[i:i + (1 << 20)]
        total += int((np.searchsorted(left, x, 'right') - np.searchsorted(left, x, 'left')).sum())
    return total


def count_dense(m, N):
    """The same number for rank 1 or 2, from a table over every value of the partial sums.  An int when every entry is
    below 2^53, so that float64 holds it exactly (N <= 52); a float beyond."""
    d = rank(m)
    assert 1 <= d <= 2, m
    us = [u(m, j) for j in range(1, N + 1)]
    assert all(x[k] >= 0 for x in us for k in range(d))
    S = [sum(x[k] for x in us) for k in range(d)]
    shape = tuple(2 * s + 1 for s in S)
    assert math.prod(shape) <= 4 * 10 ** 7, shape
    A = np.zeros(shape, dtype=np.float64)
    A[tuple(S)] = 1.0                         # the empty sum, at the middle of the table
    for x in us:
        up = tuple(slice(t, None) for t in x)                       # an index and the index t below it
        down = tuple(slice(0, n - t) for n, t in zip(shape, x))
        B = np.zeros_like(A)
        B[up] += A[down]
        B[down] += A[up]
        A = B
    c = float(A[tuple(S)])
    return int(round(c)) if N <= 52 else c


def gram(m, N):
    us = [u(m, j) for j in range(1, N + 1)]
    return [[sum(x[i] * x[k] for x in us) for k in range(rank(m))] for i in range(rank(m))]


def det(M):
    """The determinant of a square matrix of integers, exactly, by elimination in rationals."""
    A = [[Fraction(v) for v in row] for row in M]
    out = Fraction(1)
    for i in range(len(A)):
        p = next((r for r in range(i, len(A)) if A[r][i] != 0), None)
        if p is None:
            return 0
        if p != i:
            A[i], A[p] = A[p], A[i]
            out = -out
        out *= A[i][i]
        for r in range(i + 1, len(A)):
            f = A[r][i] / A[i][i]
            A[r] = [x - f * y for x, y in zip(A[r], A[i])]
    assert out.denominator == 1
    return int(out)


def gram_det(m, N):
    return det(gram(m, N))


def gauss(m, N):
    """2^N (2/pi)^(d/2) / sqrt(det M): Theorem 2's count, up to a factor that tends to 1."""
    D = gram_det(m, N)
    assert D > 0 and N <= 1000, (m, N, D)
    e = max(0, D.bit_length() - 1000) // 2 * 2                      # sqrt(D) = sqrt(D / 2^e) 2^(e/2), e even
    root = math.sqrt(D >> e) * 2.0 ** (e // 2)
    return 2.0 ** N * (2 / math.pi) ** (rank(m) / 2) / root


def leverages(m, N):
    """h_j = u(j)^T M^-1 u(j), j = 1..N, exactly; they sum to rank(m)."""
    d = rank(m)
    M = [[Fraction(v) for v in row] for row in gram(m, N)]
    out = []
    for j in range(1, N + 1):
        x = [Fraction(v) for v in u(m, j)]
        A = [row[:] + [x[i]] for i, row in enumerate(M)]            # solve M y = x
        for i in range(d):
            p = next(r for r in range(i, d) if A[r][i] != 0)
            A[i], A[p] = A[p], A[i]
            A[i] = [v / A[i][i] for v in A[i]]
            for r in range(d):
                if r != i:
                    A[r] = [v - A[r][i] * w for v, w in zip(A[r], A[i])]
        out.append(sum(x[i] * A[i][d] for i in range(d)))
    assert sum(out) == d, sum(out)
    return out


def threshold_log2(m):
    """The least integer L such that the conditions of the proof's section 5 hold at every N >= 2^L, so that every
    admissible n >= 2^(L + 1) has a (-1)^m-symmetric sequence of order at least m (the proof's Remark 1).  The
    conditions: K = m^2 ln N >= 1; N >= max(d, 8 D'^2 + 1); eta = C_m K^(D+1) / sqrt(N) <= 1/4; B_m eta < 1/2; and
    the major arc's lower bound, e^(-(pi^2/2)(1 + pi^2/48)) omega_d 2^(-m^2/2) N^(-m(m-1)/4) (omega_d the volume of
    the unit ball in d dimensions), above the minor arcs' N^(-pi^2 m^2 / 2).  Each holds from some N on once
    ln N >= 2 (D + 1), where eta starts to fall, so that is asked too."""
    assert m >= 2, m
    d, D = rank(m), m - 2
    Dp = max(D, 1)
    ln_C = (2 * D * D + 11 * D + 7) * math.log(2) + math.log(Dp)
    ln_B = (d - 1) * math.log(1 + max(abs(b(m, k, j)) for k in range(d) for j in range(1, d + 1)))

    def holds(L):
        ln_N = L * math.log(2)
        K = m * m * ln_N
        ln_eta = ln_C + (D + 1) * math.log(K) - ln_N / 2
        ln_major = (-(math.pi ** 2 / 2) * (1 + math.pi ** 2 / 48) + (d / 2) * math.log(math.pi) - math.lgamma(d / 2 + 1)
                    - (m * m / 2) * math.log(2) - (m * (m - 1) / 4) * ln_N)
        return (K >= 1 and ln_N >= math.log(max(d, 8 * Dp * Dp + 1)) and ln_N >= 2 * (D + 1)
                and ln_eta <= math.log(1 / 4) and ln_B + ln_eta < math.log(1 / 2)
                and ln_major > -(math.pi ** 2 * m * m / 2) * ln_N)
    L = 1
    while not holds(L):
        L += 1
    return L
