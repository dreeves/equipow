#!/usr/bin/env python3
"""Quals for the proof (Fable 5.2, 2026-11-09) that at each order m every sufficiently large length that Divisibility
allows has a (-1)^m-symmetric sequence of order m, so that BGPW's Symmetry Conjecture holds at every sufficiently large
length, at each order: the proof's finite, checkable parts, the numbers its remarks state, and the proof as the page
shows it, in a fold of index.html's Symmetry section (closed at first, its math drawn, its width on a phone, its links).
Run: python3 -B quals/quals_symlarge.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The quals compute sequences, orders and power sums on their own (order, mirror and halves below) and compare them with
proofs/symlarge.py, the code under test.  What they cannot check is the proof's analysis (its sections 4 and 5); of that
they check only its sum-to-max bound, the Chebyshev growth bound and the two cosine bounds, on samples.

Vocabulary, each term defined once here:
  sequence     f_0..f_(n-1), each +1 or -1; its order is the largest k with sum_i f_i i^e = 0 for every e < k
               (equivalently (x - 1)^k divides sum_i f_i x^i).
  s            (-1)^m, for an order m.  s-symmetric: f_(n-1-i) = s f_i.
  half         eps_1..eps_N: the right half of an s-symmetric sequence of length 2N, read outward from the middle.
  mirror       the s-symmetric sequence with that right half: s eps_N, ..., s eps_1, eps_1, ..., eps_N.
  rank(m)      d = floor(m/2): the number of linear conditions that order m puts on a half (the proof's Lemma 1).
  b_k          the proof's basis, k = 0..d-1: C(j+k-1, 2k) for even m, C(j+k, 2k+1) + C(j+k-1, 2k+1) for odd m.
  u(j)         the vector (b_0(j), ..., b_(d-1)(j)); the conditions on a half are sum_j eps_j u(j) = 0.
  period(m)    the least power of 2 above m (quals_symmetry's term); admissible: a length that period(m) divides.
  count        the number of halves of length N whose mirror has order at least m.
  gauss        2^N (2/pi)^(d/2) / sqrt(det M), M = sum_(j=1..N) u(j) u(j)^T: what the proof's Theorem 2 says count is,
               up to a factor that tends to 1, at admissible lengths.
  phase        theta . u(j), for a real vector theta: the proof's F(theta) is the product of cos(pi phase) over j.

History: written in scratch/symlarge-20261109 (git-ignored), red against stubs before proofs/symlarge.py existed, and
moved here with the proof on 2026-11-09 (dreeves: "yes to putting it in index.html attributed clearly to Fable 5.2").

Spec change, 2026-11-10 (dreeves's README, [SYM]: "i think i'd rather have this symlarge proof in index.html, but
default collapsed"): the proof was a page of its own, proofs/symlarge.html, which the Symmetry section linked, and the
last three quals here held that page (q_proof_page_draws_all_its_math, q_proof_page_fits_a_phone,
q_proof_page_links_resolve).  They now hold the proof where it is, the fold <details class="proof-exposition"
id="symlarge"> of index.html, as q_proof_draws_all_its_math, q_proof_fits_a_phone and q_proof_links_resolve, and
q_proof_is_a_closed_fold_of_the_symmetry_section is new.  The proof is in one place: proofs/symlarge.html only sends
its old address to the fold.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, math, time, random, shutil, tempfile, itertools, traceback
from fractions import Fraction
from math import comb

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, os.path.join(HERE, 'proofs'))
import symlarge as sl                         # the code under test
INDEX = os.path.join(HERE, 'index.html')      # the page, whose Symmetry section holds the proof in a fold
FOLD = r'<details class="proof-exposition" id="symlarge">(.*?)</details>'      # the fold, closed: it has no open attribute
OLD = os.path.join(HERE, 'proofs', 'symlarge.html')                            # the proof's page until 2026-11-10


def order(a):
    """Exact order by power sums: the least k with sum_i a_i i^k != 0 (0^0 = 1).  quals_symmetry's definition."""
    k, w = 0, [1] * len(a)
    while sum(x * y for x, y in zip(a, w)) == 0:
        k, w = k + 1, [x * i for i, x in enumerate(w)]
    return k


def mirror(m, eps):
    """The (-1)^m-symmetric sequence whose right half, read outward from the middle, is eps."""
    s = (-1) ** m
    return [s * e for e in reversed(eps)] + list(eps)


def period(m):
    p = 1
    while p <= m:
        p *= 2
    return p


def halves(N):
    return itertools.product((1, -1), repeat=N)


# BGPW's Table 1 (their Theorems 3.1 and 3.2): the lengths of each order m <= 7, every one with a (-1)^m-symmetric sequence
TABLE1 = {1: lambda n: n >= 2 and n % 2 == 0,
          2: lambda n: n >= 4 and n % 4 == 0,
          3: lambda n: n >= 8 and n % 4 == 0,
          4: lambda n: n >= 16 and n % 8 == 0,
          5: lambda n: n >= 32 and n % 8 == 0,
          6: lambda n: n == 48 or (n >= 64 and n % 8 == 0),
          7: lambda n: n in (96, 112, 128, 144, 160, 176) or (n >= 192 and n % 8 == 0)}


def q_basis_is_integer_symmetric_and_unitriangular():
    # Replicata: for m = 2..24 and each k < rank(m), evaluate sl.b(m, k, j) at j = -40..40.
    # Expectata: integers; b_k(1 - j) = s b_k(j); b_k(j) = 0 for 1 <= j <= k and b_k(k + 1) = 1; degree exactly 2k (m even)
    # or 2k + 1 (m odd), which is at most m - 2: the differences of that order are a nonzero constant.
    for m in range(2, 25):
        s, d = (-1) ** m, m // 2
        assert sl.rank(m) == d, (m, sl.rank(m))
        for k in range(d):
            vals = {j: sl.b(m, k, j) for j in range(-40, 41)}
            assert all(type(v) is int for v in vals.values()), (m, k)
            assert all(vals[1 - j] == s * vals[j] for j in range(-39, 41)), (m, k)
            assert all(vals[j] == 0 for j in range(1, k + 1)) and vals[k + 1] == 1, (m, k)
            deg = 2 * k + (m % 2)
            assert deg <= m - 2, (m, k, deg)
            row = [vals[j] for j in range(-40, 41)]
            for _ in range(deg):
                row = [y - x for x, y in zip(row, row[1:])]
            assert len(set(row)) == 1 and row[0] != 0, (m, k, 'degree is not', deg)
        assert sl.u(m, 5) == tuple(sl.b(m, k, 5) for k in range(d)), m


def q_basis_spans_the_powers_of_matching_parity():
    # Replicata: for m = 2..16 and each e < m with e = m mod 2, solve sum_k c_k b_k(j) = (2j - 1)^e on j = 1..d by forward
    # substitution in exact rationals (the system is unitriangular).
    # Expectata: the same combination equals (2j - 1)^e at every j = -20..40, so the b_k span those d powers.
    for m in range(2, 17):
        d = m // 2
        for e in range(m % 2, m, 2):
            c = []
            for j in range(1, d + 1):         # b_k(j) = 0 for k >= j, b_(j-1)(j) = 1
                c.append(Fraction((2 * j - 1) ** e) - sum(c[k] * sl.b(m, k, j) for k in range(j - 1)))
            for j in range(-20, 41):
                assert sum(c[k] * sl.b(m, k, j) for k in range(d)) == (2 * j - 1) ** e, (m, e, j)


def q_mirror_order_is_the_moment_condition():
    # Replicata: every half of each length N <= 9, for each order m <= 9; build its mirror here and take its order by
    # power sums.
    # Expectata: the mirror is s-symmetric, and its order is at least m exactly when sum_j eps_j u(j) = 0 (Lemma 1).
    for m in range(1, 10):
        s, d = (-1) ** m, m // 2
        for N in range(1, 10):
            us = [sl.u(m, j) for j in range(1, N + 1)]
            for eps in halves(N):
                a = mirror(m, eps)
                assert all(a[2 * N - 1 - i] == s * a[i] for i in range(2 * N)), (m, eps)
                zero = all(sum(e * x[k] for e, x in zip(eps, us)) == 0 for k in range(d))
                assert (order(a) >= m) == zero, (m, N, eps, order(a))


def q_parity_sums_are_binomials_mod_2():
    # Replicata: sigma_k(N) = sum_(j=1..N) b_k(j), summed term by term, for both parities of m, k <= 15, N <= 400.
    # Expectata: sigma_k(N) = C(N + k, 2k + 1) for even m, and has that parity for odd m (Lemma 3's first claim).
    for m in (32, 33):
        for k in range(16):
            total = 0
            for N in range(1, 401):
                total += sl.b(m, k, N)
                want = comb(N + k, 2 * k + 1)
                assert (total == want) if m % 2 == 0 else ((total - want) % 2 == 0), (m, k, N)


def q_parity_condition_is_divisibility():
    # Replicata: for m = 1..70 and N = 1..2200, whether sigma_k(N) is even for every k < rank(m), the sums taken term
    # by term.
    # Expectata: exactly when period(m) divides 2N (Lemma 3), and sl.admissible(m, 2N) says the same.
    top = 35
    odd = {}                                  # (m mod 2, N) -> the least k < top with sigma_k(N) odd, or top
    for par in (0, 1):
        m = 70 + par                          # rank(m) = top, so b(m, k, .) is defined for every k < top
        sums = [0] * top
        for N in range(1, 2201):
            for k in range(top):
                sums[k] += sl.b(m, k, N)
            odd[par, N] = next((k for k in range(top) if sums[k] % 2), top)
    for m in range(1, 71):
        for N in range(1, 2201):
            even = odd[m % 2, N] >= m // 2
            assert even == ((2 * N) % period(m) == 0), (m, N)
            assert sl.admissible(m, 2 * N) == even, (m, N)


def q_count_is_brute_force():
    # Replicata: for m = 1..9 and N = 1..12, count the halves whose mirror, built here, has order >= m by power sums.
    # Expectata: sl.count(m, N), a meet in the middle on u, gives the same number.
    for m in range(1, 10):
        for N in range(1, 13):
            want = sum(order(mirror(m, eps)) >= m for eps in halves(N))
            assert sl.count(m, N) == want, (m, N, sl.count(m, N), want)


def q_dense_count_is_the_meet_in_the_middle():
    # Replicata: sl.count_dense(m, N), a table over every value of the partial sums, for m = 2, 3, 4 and N <= 40.
    # Expectata: equals sl.count(m, N) exactly.
    for m in (2, 3, 4):
        for N in list(range(1, 25)) + [28, 32, 36, 40]:
            assert sl.count_dense(m, N) == sl.count(m, N), (m, N, sl.count_dense(m, N), sl.count(m, N))


def q_inadmissible_lengths_have_none():
    # Replicata: sl.count(m, N) for m = 2..7 and every N <= 30 with period(m) not dividing 2N.
    # Expectata: 0 (Lemma 3's necessity).
    for m in range(2, 8):
        for N in range(1, 31):
            if (2 * N) % period(m):
                assert sl.count(m, N) == 0, (m, N, sl.count(m, N))


def q_small_orders_match_bgpw_table_1():
    # Replicata: sl.count(m, n/2) for m = 1..7 and every even n <= 96 (n <= 64 for m <= 3).
    # Expectata: positive exactly at the lengths of BGPW's Table 1, each of which has a (-1)^m-symmetric sequence by
    # their Theorem 3.2; and exactly 2 at n = 48, m = 6, where Boyd's sequence is unique up to sign (BGPW, section 4).
    for m in range(1, 8):
        for n in range(2, (64 if m <= 3 else 96) + 1, 2):
            c = sl.count(m, n // 2)
            assert (c > 0) == TABLE1[m](n), (m, n, c)
    assert sl.count(6, 24) == 2, sl.count(6, 24)


def q_gauss_closed_forms_at_rank_1():
    # Replicata: sl.gauss(m, N) for m = 2 and 3, N = 4..400.
    # Expectata: 2^N sqrt(2 / (pi N)) for m = 2 (M = N), and 2^N sqrt(2 / pi) / sqrt(N (4 N^2 - 1) / 3) for m = 3
    # (M = sum of the squares of the first N odd numbers), to 12 digits.
    for N in range(4, 401, 4):
        a, b = sl.gauss(2, N), 2.0 ** N * math.sqrt(2 / (math.pi * N))
        assert abs(a / b - 1) < 1e-12, (N, a, b)
        a, b = sl.gauss(3, N), 2.0 ** N * math.sqrt(2 / math.pi) / math.sqrt(N * (4 * N * N - 1) / 3)
        assert abs(a / b - 1) < 1e-12, (N, a, b)
    assert sl.gram_det(4, 3) == 3 * (0 + 1 + 9) - (0 + 1 + 3) ** 2, sl.gram_det(4, 3)   # u = (1, C(j, 2)), j = 1, 2, 3


def q_count_approaches_gauss():
    # Replicata: the ratio count / gauss at two admissible half-lengths N1 < N2 for m = 2, 3, 4: 64 and 128 for
    # m = 2, 3 (rank 1), 32 and 64 for m = 4 (rank 2), from the dense table.
    # Expectata: Theorem 2 says the ratio tends to 1.  A wrong count of major arcs would put it near 2 or 1/2, so:
    # within a factor sqrt(2) of 1 at N1, within 10% of 1 at N2, and nearer 1 at N2 than at N1.
    # Spec change, 2026-11-09, by Claude, of a qual written the same hour in scratch (not yet seen by dreeves): the first version
    # also asked this of m = 5 at N = 32 and 48, and was red there with a ratio of 2.07 at N = 48.  The expectation was
    # wrong, not the count: Theorem 2 gives no rate, and at m = 5 a minor arc decays only like cos(pi/16)^N
    # (q_order_5_has_a_slow_minor_arc), so no length a meet in the middle reaches is near the limit.
    for m, N1, N2 in ((2, 64, 128), (3, 64, 128), (4, 32, 64)):
        assert sl.admissible(m, 2 * N1) and sl.admissible(m, 2 * N2), (m, N1, N2)
        r1, r2 = sl.count_dense(m, N1) / sl.gauss(m, N1), sl.count_dense(m, N2) / sl.gauss(m, N2)
        assert 2 ** -0.5 < r1 < 2 ** 0.5, (m, N1, r1)
        assert 0.9 < r2 < 1.1, (m, N2, r2)
        assert abs(math.log(r2)) < abs(math.log(r1)), (m, r1, r2)


def q_order_5_has_a_slow_minor_arc():
    # Replicata: m = 5 and theta = (-1/16, 1/4), in exact rationals: the phases theta . u(j) for j = 1..4000.
    # Expectata: every phase is at distance exactly 1/16 from an integer, so the Fourier product there has absolute
    # value cos(pi/16)^N: 0.39 at N = 48 and still 0.02 at N = 200.  And 1/16 is 2^-(D+1) for m = 5 (D = 3), twice
    # Lemma 5's delta: the lemma's proof works up to that value of delta (the difference it bounds is then below 1),
    # and this example shows it works no further.
    th = (Fraction(-1, 16), Fraction(1, 4))
    for j in range(1, 4001):
        x = sum(t * v for t, v in zip(th, sl.u(5, j)))
        assert abs(x - round(x)) == Fraction(1, 16), (j, x)
    assert abs(math.cos(math.pi / 16) ** 48 - 0.394) < 1e-3 and 0.02 < math.cos(math.pi / 16) ** 200 < 0.021


def q_fourier_integral_is_the_count():
    # Replicata: F(theta) = prod_(j=1..N) cos(pi theta . u(j)), averaged over a uniform grid of [0, 2)^d with
    # S_k + 1 points along coordinate k (S_k = sum_j |u_k(j)|; the grid averages a trigonometric polynomial of those
    # degrees exactly), and, at admissible lengths, over the grid's part in [0, 1)^d with S_k / 2 + 1 points.
    # Expectata (Lemma 4): 2^N times the first average is the count at every length, admissible or not; 2^N times the
    # second is the count at admissible lengths.  The count is taken here by brute force (N <= 12).
    import numpy as np
    for m, N in ((2, 6), (2, 7), (3, 8), (3, 9), (4, 8), (4, 10), (4, 12), (5, 8), (5, 10), (5, 12),
                 (6, 8), (6, 10), (6, 12), (7, 8), (7, 6)):
        d = m // 2
        us = [sl.u(m, j) for j in range(1, N + 1)]
        want = sum(order(mirror(m, eps)) >= m for eps in halves(N))
        S = [sum(abs(x[k]) for x in us) for k in range(d)]
        for span in ((2, 1) if (2 * N) % period(m) == 0 else (2,)):
            if span == 1:
                assert all(s % 2 == 0 for s in S), (m, N, S)
            G = [s + 1 if span == 2 else s // 2 + 1 for s in S]
            assert math.prod(G) <= 2 * 10 ** 7, (m, N, G)          # 160 MB a table at most
            axes = np.meshgrid(*[span * np.arange(g) / g for g in G], indexing='ij', sparse=True)
            F = np.ones(G)
            for x in us:
                F = F * np.cos(np.pi * sum(t * v for t, v in zip(axes, x)))
            got = 2.0 ** N * F.mean()
            assert abs(got - want) < 1e-6 * max(1, want), (m, N, span, got, want)


def q_order_7_has_a_slow_minor_arc():
    # Replicata: m = 7 and theta = (-1/32, 1/8, 1/2), in exact rationals: the phases for j = 1..4000.
    # Expectata (the proof's Remark 2): every phase is at distance exactly 1/32 from an integer, so the Fourier
    # product there has absolute value cos(pi/32)^N: still 0.38 at N = 200.
    th = (Fraction(-1, 32), Fraction(1, 8), Fraction(1, 2))
    for j in range(1, 4001):
        x = sum(t * v for t, v in zip(th, sl.u(7, j)))
        assert abs(x - round(x)) == Fraction(1, 32), (j, x)
    assert abs(math.cos(math.pi / 32) ** 200 - 0.381) < 1e-3


def q_counts_swing_around_gauss_at_orders_5_and_6():
    # Replicata: count / gauss at every admissible half-length N from 16 to 48 for m = 5, and at every admissible N
    # from 24 to 48 with a sequence for m = 6.
    # Expectata (the proof's Remark 2, and the main page's account): for m = 5 the ratio lies between 0.55 and 3.6,
    # and not between 0.56 and 3.5; for m = 6 between 0.04 and 2.5, and not between 0.05 and 2.4.
    r5 = [sl.count(5, N) / sl.gauss(5, N) for N in range(16, 49, 4)]
    assert all(sl.admissible(5, 2 * N) for N in range(16, 49, 4)) and len(r5) == 9, r5
    assert 0.55 <= min(r5) < 0.56 and 3.5 < max(r5) <= 3.6, r5
    c6 = {N: sl.count(6, N) for N in range(24, 49, 4)}
    r6 = [c / sl.gauss(6, N) for N, c in c6.items() if c]
    assert [N for N, c in c6.items() if not c] == [28], c6
    assert 0.04 <= min(r6) < 0.05 and 2.4 < max(r6) <= 2.5, r6


def q_proof_s_conditions_hold_from_the_stated_sizes():
    # Replicata: sl.threshold_log2(m), the least L such that the conditions of the proof's section 5 hold at every
    # N >= 2^L, for m = 2, 5 and 12; and those conditions recomputed here at N = 2^L and 2^(L - 1) for m = 2, where
    # D = 0, d = 1, C_m = 2^7 and B_m = 1.
    # Expectata (the proof's Remark 1): 31, 221 and 1062, so that the proof gives a (-1)^m-symmetric sequence at every
    # admissible n from 2^32, 2^222 and 2^1063 on; at m = 2 the binding condition is eta <= 1/4, true at 2^31 and
    # false at 2^30.
    assert [sl.threshold_log2(m) for m in (2, 5, 12)] == [31, 221, 1062], [sl.threshold_log2(m) for m in (2, 5, 12)]
    eta = lambda L: 2 ** 7 * (4 * L * math.log(2)) / math.sqrt(2.0 ** L)     # C_m K^(D+1) / sqrt(N) at m = 2
    assert eta(31) <= 1 / 4 < eta(30), (eta(31), eta(30))


def q_exact_order_is_a_difference_of_counts():
    # Replicata: for m = 1..7 and N = 1..11, the halves whose mirror, built here, has order exactly m by power sums.
    # Expectata: their number is sl.count(m, N) - sl.count(m + 2, N): a (-1)^m-symmetric sequence of order at least
    # m + 1 has order at least m + 2 (the proof, Remark 5's first step).
    for m in range(1, 8):
        for N in range(1, 12):
            want = sum(order(mirror(m, eps)) == m for eps in halves(N))
            assert sl.count(m, N) - sl.count(m + 2, N) == want, (m, N, want)


def q_one_more_basis_polynomial_grows_the_determinant():
    # Replicata: det M for m and for m + 2 (the same basis and one more polynomial, of degree e = 2d for even m and
    # 2d + 1 for odd m, d = rank(m)), exactly, for m = 1..10 and N = 1..80.
    # Expectata: det M(m + 2, N) >= det M(m, N) floor(N / (e + 1)) / 4^e, Remark 5's bound, which makes the sequences
    # of order at least m + 2 a vanishing fraction of those of order at least m.
    for m in range(1, 11):
        e = 2 * (m // 2) + m % 2
        for N in range(1, 81):
            assert sl.gram_det(m + 2, N) * 4 ** e >= sl.gram_det(m, N) * (N // (e + 1)), (m, N)
            assert (sl.gram_det(m, N) > 0) == (N >= m // 2), (m, N)


def q_markov_bound_between_sum_of_squares_and_maximum():
    # Replicata: 400 random real polynomials R of each degree D = 1..8 (random coefficients in a Chebyshev basis scaled
    # to the interval), on runs of L consecutive integers with L - 1 >= 8 D^2, S the sum of R(j)^2 over the run.
    # Expectata: max |R| over the run's interval (on a grid of 4001 points) is at most 4 sqrt(2) D sqrt(S / (L - 1)),
    # the proof's sum-to-max bound, which it gets from Markov's inequality.
    rng = random.Random(20261109)
    for D in range(1, 9):
        for _ in range(400):
            L = 8 * D * D + 1 + rng.randrange(0, 200)
            a = rng.randrange(-500, 500)
            coef = [rng.gauss(0, 1) * rng.choice((1, 1, 1e-3, 1e3)) for _ in range(D + 1)]

            def R(x):
                t = (2 * (x - a) - (L - 1)) / (L - 1)            # the run's interval [a, a + L - 1] as [-1, 1]
                return sum(c * math.cos(i * math.acos(max(-1.0, min(1.0, t)))) for i, c in enumerate(coef))
            S = sum(R(a + j) ** 2 for j in range(L))
            M = max(abs(R(a + (L - 1) * g / 4000)) for g in range(4001))
            assert M <= 4 * math.sqrt(2) * D * math.sqrt(S / (L - 1)) * (1 + 1e-9), (D, L, M, S)


def q_chebyshev_growth_outside_an_interval():
    # Replicata: 300 random real polynomials R of each degree D = 0..8 with max |R| = M on [-1, 1] (grid of 4001
    # points, so M is slightly underestimated; the margin below covers it), evaluated at 50 points xi with
    # 1 <= |xi| <= 40.
    # Expectata: |R(xi)| <= M (2 |xi|)^D, the growth bound the proof's Lemma 5 uses to leave a run.
    rng = random.Random(20261110)
    for D in range(0, 9):
        for _ in range(300):
            coef = [rng.gauss(0, 1) for _ in range(D + 1)]

            def R(x):
                return sum(c * x ** i for i, c in enumerate(coef))
            M = max(abs(R(-1 + g / 2000)) for g in range(4001))
            for _ in range(50):
                xi = rng.choice((-1, 1)) * rng.uniform(1, 40)
                assert abs(R(xi)) <= M * (2 * abs(xi)) ** D * 1.01, (D, xi, R(xi), M)


def q_log_cosine_bounds():
    # Replicata: z on a grid of 100,001 points of [0, pi/2), and of [0, pi/4].
    # Expectata: log cos z <= -z^2 / 2 on the first; log cos z >= -z^2 / 2 - z^4 / 6 on the second (the two bounds on
    # each factor cos(pi x) that the proof's section 5 uses).
    for g in range(100001):
        z = (math.pi / 2) * g / 100001
        assert math.log(math.cos(z)) <= -z * z / 2 + 1e-15, z
        z = (math.pi / 4) * g / 100000
        assert math.log(math.cos(z)) >= -z * z / 2 - z ** 4 / 6 - 1e-15, z


# ---------------------------------------------------------------------------------------------------------------------
# The proof's page

# Headless Chrome's window is at least 500 px wide, so the page runs in an iframe of the width asked for and posts its
# report to this host page, which writes it into its own DOM for --dump-dom (quals_index's HOST, with this report).
HOST = """<!doctype html>
<html><head><meta charset="utf-8"></head><body style="margin: 0">
<iframe src="index.html" style="display: block; border: 0; width: __WIDTH__px; height: 1000px"></iframe>
<script>
addEventListener('message', e => {
  const pre = document.createElement('pre'); pre.id = 'symlarge-out'; pre.textContent = e.data; document.body.append(pre);
});
</script>
</body></html>
"""
# In the page, once its fonts are in and KaTeX has drawn: whether the proof's fold is open as the page loads and how
# tall the fold is then; then, with the fold opened: its height, the formulas drawn in the fold, KaTeX's errors
# there, any \( or \) left in its text, the window's and the document's widths, and the fold's paragraphs, list items,
# headings, summary and drawn pieces of formulas (KaTeX's .base spans, between which a line may break) outside a
# displayed formula that reach past the window, the number of its displayed formulas, and, for each of its lists, the
# least space between one item's bottom and the next one's top
LOOK = """<script>
addEventListener('load', () => document.fonts.ready.then(() => setTimeout(() => {
  const fold = document.getElementById('symlarge');
  const openAtLoad = fold.open, closedHeight = fold.getBoundingClientRect().height;
  fold.open = true;
  setTimeout(() => {
    const reach = e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1;
    parent.postMessage(JSON.stringify({
      openAtLoad, closedHeight, openHeight: fold.getBoundingClientRect().height,
      drawn: fold.querySelectorAll('.katex').length,
      errors: [...fold.querySelectorAll('.katex-error')].map(e => e.textContent.slice(0, 80)),
      raw: (fold.textContent.match(/\\\\[()]/g) || []).length,
      innerW: innerWidth, scrollW: document.documentElement.scrollWidth,
      past: [...fold.querySelectorAll('p, li, h4, summary, .katex-html .base')].filter(e => reach(e) && !e.closest('.proof-equation')).length,
      equations: fold.querySelectorAll('.proof-equation').length,
      listGaps: [...fold.querySelectorAll('ul, ol')].map(list => [list.tagName, Math.min(...[...list.children].slice(1).map(
        item => item.getBoundingClientRect().top - item.previousElementSibling.getBoundingClientRect().bottom))]),
      fonts: getComputedStyle(fold.querySelector('p')).fontFamily,
    }), '*');
  }, 400);
}, 800)));
</script>
"""
LOOKS = {}                                    # the page's report by width, made once per process


def page_text():
    return open(INDEX, encoding='utf-8').read()


def proof_text():
    """The proof as index.html holds it: the inside of its fold, of which the page has exactly one."""
    found = re.findall(FOLD, page_text(), re.S)
    assert len(found) == 1, f'index.html has {len(found)} folds of the proof'
    return found[0]


def look(width):
    """The proof's fold as headless Chrome draws it in the page, in a frame width px wide, beside copies of page/ and
    of the charts' data."""
    if width not in LOOKS:
        import quals_index as qi              # read only: copy_page_dir and chrome
        proof_text()                          # no fold, no look
        d = tempfile.mkdtemp(prefix='symlarge-quals-')
        try:
            text = page_text()
            assert text.count('</body>') == 1
            open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text.replace('</body>', LOOK + '</body>'))
            qi.copy_page_dir(d)
            for data in ('mstar.js', 'pow2.js'): shutil.copy(os.path.join(HERE, data), d)
            open(os.path.join(d, 'host.html'), 'w').write(HOST.replace('__WIDTH__', str(width)))
            dom = qi.chrome(d, [f'--window-size={max(width, 500) + 40},1100', '--virtual-time-budget=10000', '--dump-dom',
                                'file://' + os.path.join(d, 'host.html')])
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="symlarge-out">(.*?)</pre>', dom, re.S)
        assert m, dom[-2000:]
        LOOKS[width] = json.loads(html.unescape(m.group(1)))
    return LOOKS[width]


def q_proof_is_a_closed_fold_of_the_symmetry_section():
    # Replicata: index.html: its Symmetry section, the block quotes there and the proof's fold; proofs/symlarge.html,
    # the proof's page until 2026-11-10; and the page in headless Chrome 1280 px wide, as it loads and with the fold
    # then opened.
    # Expectata (dreeves's README, [SYM], 2026-11-10: "i think i'd rather have this symlarge proof in index.html, but
    # default collapsed"): the page holds the proof once, in a <details class="proof-exposition" id="symlarge"> with no
    # open attribute, inside one block quote of the Symmetry section: a summary, then a <div class="proof-body"> whose
    # only headings are seven h4, with the ids symlarge-s0 to symlarge-s6 in that order (the proof's sections 0 to 6);
    # as the page loads the fold is closed and under 100 px tall, and opened it is over 1000 px tall; and the proof's
    # old address still leads to it: proofs/symlarge.html sends its reader to ../index.html#symlarge, by a refresh at
    # once and by a link.
    # Resultata before: the Symmetry section linked the proof, a page of its own, and index.html had no such fold.
    # (Two checks written with this qual were cut the same day: that the page link no symlarge.html, and that the old
    # page hold no formula.  Each could only fail by something done on purpose, and dreeves, of another such check:
    # "the point of quals ... it's to prevent regressions that could happen accidentally".)
    text = page_text()
    sec = re.search(r'<section class="symmetry" aria-labelledby="symmetry-title">(.*?)</section>', text, re.S)
    assert sec, 'no Symmetry section'
    fold = proof_text()
    quotes = [q for q in re.findall(r'<blockquote class="claude">(.*?)</blockquote>', sec.group(1), re.S) if 'id="symlarge"' in q]
    assert len(quotes) == 1 and len(re.findall(FOLD, quotes[0], re.S)) == 1 and text.count('id="symlarge"') == 1, (len(quotes), text.count('id="symlarge"'))
    assert re.match(r'\s*<summary>[^<]+</summary>\s*<div class="proof-body">', fold), fold[:300]
    assert re.findall(r'<h(\d)\b', fold) == ['4'] * 7, re.findall(r'<h\d[^>]*>', fold)
    assert re.findall(r'<h4 id="([^"]*)">', fold) == [f'symlarge-s{k}' for k in range(7)], re.findall(r'<h4[^>]*>', fold)
    old = re.sub(r'<!--.*?-->', '', open(OLD, encoding='utf-8').read(), flags=re.S)
    assert '<meta http-equiv="refresh" content="0; url=../index.html#symlarge">' in old and 'href="../index.html#symlarge"' in old, old[:600]
    R = look(1280)
    assert R['openAtLoad'] is False and R['closedHeight'] < 100 and R['openHeight'] > 1000, R


def q_proof_draws_all_its_math():
    # Replicata: index.html beside page/ and the charts' data, in headless Chrome 1280 px wide, once KaTeX has drawn it
    # and the proof's fold is opened.
    # Expectata: in the fold, KaTeX reports no error; it has drawn as many formulas as the fold's source has \( outside
    # its comments; no \( or \) is left in its text; and there are more than 300 of them (the proof is there, not a stub).
    R = look(1280)
    want = len(re.findall(r'\\\(', re.sub(r'<!--.*?-->', '', proof_text(), flags=re.S)))
    assert R['errors'] == [] and R['raw'] == 0, R
    assert R['drawn'] == want > 300, (R['drawn'], want)


def q_proof_fits_a_phone():
    # Replicata: the same page in a frame 390 px wide, the proof's fold opened.
    # Expectata: the frame is 390 px wide; the page is no wider than it; nothing of the fold outside a displayed formula
    # reaches past it (a displayed formula wider than a phone scrolls sideways alone, in its own paragraph, of class
    # proof-equation, as the page's other inline proofs have them); and the fold has as many such paragraphs drawn as
    # its source has, more than 10.
    R = look(390)
    assert R['innerW'] == 390 and R['scrollW'] <= R['innerW'] and R['past'] == 0, R
    assert R['errors'] == [], R
    assert R['equations'] == proof_text().count('<p class="proof-equation">') > 10, (R['equations'], proof_text().count('<p class="proof-equation">'))


def q_proof_s_lists_space_their_items():
    # Replicata: the page 1280 px wide, the proof's fold opened: each list of the fold (a ul in section 4, the ol of
    # the remarks), and the space between each of its items and the next.
    # Expectata: the fold has both lists, and in each the items stand at least 8 px apart, as the Symmetry section's
    # other lists do (0.6rem, 9.6 px) and as both did on the proof's own page.
    # Resultata before (2026-11-10, the proof just moved into the fold): the remarks' items ran together, 0 px apart,
    # since the section's stylesheet spaced only a ul.
    R = look(1280)
    assert sorted(tag for tag, _ in R['listGaps']) == ['OL', 'UL'] and all(gap >= 8 for _, gap in R['listGaps']), R['listGaps']


def q_proof_links_resolve():
    # Replicata: every href and src of the proof's fold, outside its comments.
    # Expectata: each link into github.com/dreeves/equipow names a file of the repository, and each link into the page
    # an id it has.  (Until 2026-11-10 this also refused any other link and asked for two links to be there: bans on
    # what is only done on purpose, cut with the others of that day.)
    text = re.sub(r'<!--.*?-->', '', proof_text(), flags=re.S)
    refs = re.findall(r'\b(?:href|src)="([^"]+)"', text)
    assert refs, 'no links'
    hub, page = 'https://github.com/dreeves/equipow/blob/main/', page_text()
    files = [ref[len(hub):] for ref in refs if ref.startswith(hub)]
    ids = [ref[1:] for ref in refs if ref.startswith('#')]
    assert all(os.path.isfile(os.path.join(HERE, f)) for f in files), files
    assert all(f'id="{i}"' in page for i in ids), ids


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0, c0 = time.time(), time.process_time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds and this process's CPU seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds and this process's CPU seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
