#!/usr/bin/env python3
"""Bounds on m*(n) for every n = 1..NMAX, for the chart on index.html: computes them with their reasons and writes
pagedata/mstar.js (this file is in pagegen/ and the data file in pagedata/ since 2026-11-10; both were at the root).

The question is that of Buhler, Golan, Pratt and Wagon (BGPW), "Littlewood polynomials, spectral-null codes, and
equipowerful partitions", Math. Comp. 90 (2021) 1435-1453, arXiv:1912.03491: how large can the order of a +-1
sequence of length n be?

Vocabulary used throughout this file, each term defined once here:
  sequence       signs e_0..e_{n-1}, each +1 or -1; n is its length, and f(x) = sum_i e_i x^i.
  order          the number of leading exponents j = 0, 1, ... whose power sums sum_i e_i i^j vanish (0^0 = 1).
                 Order >= m exactly when (x-1)^m divides f; order m implies order m - 1.
  m*(n)          the largest order of a sequence of length n.
  lo, hi         the best lower bound on m*(n) known here, and the best upper bound proved or cited here.
  column         [lo, hi, loWhy, hiWhy] for one n, as mstar.js has it (the data contract below).
  explicit       a sequence in hand, from one of the sources below, its order checked here by exact power sums.
  join           a then b: f_a(x) + x^len(a) f_b(x), the paper's ∨; its order is at least the lesser of theirs.
  product        f_a(x) f_b(x^len(a)), the paper's #; its order is the sum of theirs.
  citation       a value read off index.html (BGPW's Table 2, or the block of new results), with no sequence or
                 proof here.
  size(M, r)     the number of positions i in 0..n-1 with i = r (mod M).
  residue sums   D_r = the sum of e_i over the positions i = r (mod M), r = 0..M-1; so |D_r| <= size(M, r) and
                 D_r = size(M, r) (mod 2).
  residue lattice  L(M, m), the coefficient vectors of (x-1)^m g(x) mod x^M - 1 for g in Z[x].  A sequence of order
                 >= m has its residue sums mod M in L(M, m): f = (x-1)^m g with g in Z[x], since (x-1)^m is monic.
  L+(M, m)       the coefficient vectors of (x-1)^m (x+1) g(x) mod x^M - 1 for g in Z[x], inside L(M, m).  When n < 2^m,
                 every D in L(M, m) with |D_r| <= size(M, r) for all r is in L+(M, m), so residue_vectors enumerates
                 L+(M, m) instead, as overnight_v5.lattice_poly does: the same vectors, found far sooner (720 at order
                 15 mod 16 takes one node, where L(16, 15) passes 10^6).  Proof: D(x) = (x-1)^m g(x) + (x^M - 1) q(x)
                 with g, q in Z[x].  If M is even, x = -1 gives D(-1) = (-2)^m g(-1), a multiple of 2^m, while
                 |D(-1)| <= sum_r size(M, r) = n < 2^m; so D(-1) = 0, so g(-1) = 0, so g = (x+1) h with h in Z[x]
                 (x + 1 is monic), and D is in L+(M, m).  If M is odd, L+(M, m) = L(M, m) for m >= 1: with
                 Phi = 1 + x + ... + x^(M-1) = (x+1) s(x) + Phi(-1), s in Z[x] and Phi(-1) = 1,
                 (x-1)^m = (x-1)^(m-1) (x^M - 1) - (x+1) (x-1)^m s(x), which lies in L+(M, m).
  parent         (P, W): residue sums W mod P, for P dividing M.  The vectors mod M under it are those whose sums
                 over the classes r = q (mod P) are the W_q; a sequence's residue sums mod M sum this way to its own
                 residue sums mod P.
  admissible     residue sums mod M in L(M, m) that meet the size and parity conditions, and the parent's sums.
  chain          moduli M_1 | M_2 | ..., enumerated in turn, each level under each admissible vector of the level
                 before.  No admissible vector at the last level means no sequence of order >= m (every sequence's
                 residue sums are admissible at every level).
  node           one step of residue_vectors' enumeration; a Budget caps the nodes of one test.
  sweep          the order in which residue_vectors meets the classes mod M: 'natural' (0, 1, ..., M-1) or 'digits'
                 (see digits).  A sweep decides only how soon the enumeration prunes, never what it finds.
  claim          (m, chain, sweep) in RESIDUE: the enumeration through the chain at order m, in that sweep, run to
                 the end, finds no admissible vector, so m*(n) <= m - 1.

The two lemmas behind hi (each checked against brute force by quals_mstar.py):
  two   m*(n) <= 2^v - 1, v the exponent of 2 in n (BGPW's Divisibility).  Mod 2, f = 1 + x + ... + x^(n-1) =
        (x^n + 1)/(x + 1), and with n = 2^v u, u odd, x^n + 1 = (x^u + 1)^(2^v) over GF(2), where x + 1 divides
        x^u + 1 exactly once (its derivative x^(u-1) is 1 at x = 1).  So (x+1)^m, the image of (x-1)^m, divides
        f mod 2 only for m <= 2^v - 1.
  norm  For a prime p not dividing n: p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1).  The class sizes mod p
        take two consecutive values, so the residue sums S_r (S_r = size(p, r) mod 2) are not all equal, and f(z) =
        sum_r S_r z^r != 0 for z a primitive p-th root of unity (the only rational relation among 1, z, ..., z^(p-1)
        is their sum).  With f = (x-1)^m g, g in Z[x], the norm N = prod_(a=1..p-1) f(z^a) is a nonzero integer
        divisible by (prod_a (z^a - 1))^m = p^m.  By Parseval, sum_(a=1..p-1) |f(z^a)|^2 = p sum_r S_r^2 - f(1)^2
        <= p sum_r size(p, r)^2 (f(1) = 0 for m >= 1), and by AM-GM, N^2 <= (p sum_r size(p, r)^2 / (p-1))^(p-1).

The data contract.  mstar.js is a classic script (no modules, so the page also works from file://) defining one global:
    const MSTAR = {"nmax": 2048, "mtop": T, "mtopAt": [N, ...], "past": [[n, lo, hi, loWhy, hiWhy], ...], "ifsym": [[n, hi, file], ...], "examples": [[n, code, source], ...], "cols": [[lo, hi, loWhy, hiWhy], ...]};
cols[n-1] is column n.  0 <= lo <= hi < T = max hi + 1.  Cell (n, m), m = 1..T, is green when m <= lo, gray when
lo < m <= hi, and red when m > hi; row T is red in every column.  mtopAt lists, for each order from T to MMAX (T's
alone where T is past MMAX), the
least n past nmax that the chart's own upper-bound tests leave open at that order (mtop_at; T's alone, a number, from
2026-11-03, a list since 2026-11-04), even integers above nmax that never fall: the table of smallest lengths' least n
not ruled out at those orders.  past (since 2026-11-04) lists the lengths of the explicit sequences longer than nmax,
which the chart has no column for, rising in n: the table of smallest lengths' lengths known past the chart, and since
2026-11-19 (dreeves: "yes, full anti-magic, add the new entries") the appendix's lengths past it but the powers of 2,
each with its entry; each [n, lo, hi, loWhy, hiWhy], its row as a column's (rows), [n, m, label] until then, m the exact
order of the sequence.
ifsym (since 2026-11-11; dreeves's README, [SYC]: "a different styling on the chart ... for cells for which we know they're
red conditional on the Symmetry Conjecture being true, i.e., we've proven there's no symmetric or antisymmetric
bipartition") lists the columns whose upper bound is lower if BGPW's Symmetry Conjecture holds, each [n, hi, file], rising
in n: m*(n) <= hi then, hi from the column's lo to one below its own hi, by the proofs that the program file checks
(ifsym_of).  The cells (n, m) with that hi < m <= the column's own hi are the page's fourth kind: open, and red if the
conjecture holds.
examples (since 2026-11-18; dreeves: "there should be no "found here". what does "here" mean? totally ambiguous. show
the expandable hex code for everything"; codes, [n, code], until his point 10 of that night) lists [n, code, source] for
each column whose loWhy is an example, and since 2026-11-19 each row of past's, rising in n: the code of its sequence (to_hex), which is (-1)^lo-symmetric, in
BGPW's Table 5 convention: the bits of its left half, 1 = +1, padded on the right with 0 to whole hex digits, ceil(n/8)
of them, which page/codes.js expands; and where it comes from, to which its label links (source_of).
  loWhy  ["none"] (lo = 0, n odd); ["example", label] (an explicit sequence of length n, label saying where it is
         from); ["join", a, b, ...] (the sequences for a, b, ... one after the other; lo is the least of theirs; since
         2026-11-18 a, b, a, whose sequence is (-1)^lo-symmetric when theirs are, and a, b until then); ["product", a, b]
         (f_a(x) f_b(x^a); lo is the sum of theirs); ["table2"] (BGPW's Table 2, cited); ["page", who] (the page's new
         results, cited; who the credit for the example, a class of the page's cells, c, cf, j, ca, a or s: EXAMPLE_BY).  Every example, join and
         product is a sequence built here from explicit sequences only and checked with exact power sums, and since
         2026-11-18 asserted (-1)^lo-symmetric; a join's or product's parts are themselves columns with such reasons.
  hiWhy  ["odd"] (n odd: hi = 0); ["two"]; ["norm", p]; ["residue", M] (no admissible vector mod M at order hi + 1:
         for M = 3, since 2026-11-16, by the residue condition mod 3 in closed form, residue3, at any even n that 3
         does not divide; for any other M, the claim in RESIDUE, whose chain ends at M); ["proof", file] (PROOFS: a program of proofs/ that checks a proof of its own that no
         sequence of length n has order hi + 1, at a length outside the page's tables; since 2026-11-10, 1456's);
         ["prop44"] (since 2026-11-11: BGPW's Proposition 4.4, prop44(n): hi + 1 is the power of 2 in n less 1, an
         order at which the alternating sum would be 2^(hi + 1) or more, which is more than n);
         ["table2"]; ["page", who] (who the credit for the proof: that cell's class).
  When sources tie, a reason checked here wins over a citation, and the simpler one among those: example, join,
  product; odd, two, residue 3 (the closed form), norm (the least p), residue (a claim), proof, prop44 (last, as the
  newest: it gives no column a reason that an older test gave it).  The residue condition mod 3 comes before the norm
  bound since 2026-11-16 (dreeves, of Stan Wagon's "standard mod-3 argument" that m*(1024) <= 11, which needs no root
  of unity: "ok, go ahead with breaking ties in favor of the mod-3 argument"): in closed form it is a check by hand,
  and at p = 3 it implies the norm bound, so it took the 32 columns that the norm bound for 3 held, 1024 among them.

Run:   python3 -B pagegen/mstar.py   (writes pagedata/mstar.js)
Quals: python3 -B quals/quals_mstar.py
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, runpy
from functools import lru_cache, reduce
from operator import mul
import numpy as np
import sympy as sp
# the engine's modules, overnight_v5 and residues, in engine/ since [FAC] stage 3b (2026-11-04)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'engine'))
import overnight_v5 as v5                    # read only: EXAMPLES and from_hex
# The residue enumeration, moved verbatim to residues.py on 2026-10-26 so that focus.fingerprint, the proof
# searches' continuation identity, covers it and not this file (see residues.py); imported back for the claims
# below and for the other callers of mstar.residue_vectors.
from residues import digits, SWEEPS, lattice, basis, Capped, Budget, residue_vectors

NMAX = 2048                                  # 1000 until 2026-10-27 (dreeves, relaying Stan Wagon: "could the table and
                                             # the chart go up to 1024 as the natural stopping point, instead of 1000?"),
                                             # then 1024 until 2026-11-10 (dreeves's README: "[BOU] Let's try having
                                             # Figure 1 go up to 2048"); the page's tables stay at 1024 (UPPER)
BRUTE_MAX = 32                               # brute force decides m*(n) for n up to this
PRIMES = tuple(sp.primerange(2, 32))         # the norm lemma's primes (the least prime not dividing a given n <= NMAX
                                             # is at most 11, since 2 * 3 * 5 * 7 * 11 = 2310)
RESIDUE_CAP = 10 ** 7                        # nodes allowed to the enumeration of one claim (the largest, 624 mod 25,
                                             # takes about 670000)
CHAINS = ((3,), (4,), (5,), (7,), (3, 9), (4, 8), (11,), (13,), (4, 8, 16), (5, 25), (3, 9, 27), (7, 49),
          (4, 8, 16, 32))                    # the residue chains of scratch/mstar/residue_search.py, which found RESIDUE
MTOP_CAP = 300000                            # nodes per chain past NMAX (mtop_at): that search's first pass
MMAX = 17                                    # the table of smallest lengths' last order, so mstar.js's mtopAt runs
                                             # from mtop to it (dreeves's README, 2026-11-04: "[M17] Let's add m=17 to
                                             # the "smallest length known" table; no need for much search, just
                                             # whatever bounds we can find quickly"; the table stopped at mtop before),
                                             # or to mtop alone where mtop is past it, as since 2026-11-10 (mtop 19)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above pagegen/ (this file was at the root until 2026-11-10, dreeves's README [REF])
PAGE = os.path.join(HERE, 'index.html')
JS = os.path.join(HERE, 'pagedata', 'mstar.js')   # the page's data files are in pagedata/ since 2026-11-10 ([REF])


# ---------- sequences ----------

def order(a):
    """The exact order of a sequence, by power sums sum_i e_i i^j, j = 0, 1, ... (0^0 = 1)."""
    assert len(a) >= 1 and set(a) <= {1, -1}, a
    k, w = 0, [1] * len(a)                   # w[i] = i^k
    while sum(map(mul, a, w)) == 0:
        k, w = k + 1, [x * i for i, x in enumerate(w)]
    return k


def join(a, b): return a + b


def product(a, b): return [s * t for t in b for s in a]          # block j is a times b_j: f_a(x) f_b(x^len(a))


def thue_morse(k): return [(-1) ** bin(i).count('1') for i in range(2 ** k)]


def from_rp(h, m, n):
    """A sequence of length n from a hex code in BGPW's convention: the code's bits (1 = +1), padded on the right to a
    multiple of 4, begin the left half; the first n/2 of them are the left half, and (-1)^m symmetry gives the rest.
    For a Table 5 code n/2 is all the bits; a Table 4 pair codes two lengths in one string."""
    bits = bin(int(h, 16))[2:].zfill(4 * len(h))
    assert n % 2 == 0 and 0 < n // 2 <= len(bits), (h, n)
    left = [2 * int(b) - 1 for b in bits[:n // 2]]
    return left + [(-1) ** m * t for t in reversed(left)]


def to_hex(a, m):
    """The code of a sequence a of length n and order m that is (-1)^m-symmetric (2026-11-18, for mstar.js's codes):
    the bits of its left half, 1 for +1, padded on the right with 0 to whole hex digits, ceil(n/8) of them, as from_rp
    reads them; from_rp of the code asserted to give a back, which holds exactly when a is (-1)^m-symmetric."""
    n = len(a)
    bits = ''.join('1' if t == 1 else '0' for t in a[:n // 2])
    bits += '0' * (-len(bits) % 4)
    h = ''.join(f'{int(bits[i:i + 4], 2):X}' for i in range(0, len(bits), 4))
    assert len(h) == -(-n // 8) and from_rp(h, m, n) == a, (n, m)
    return h


# ---------- citations and sequences on index.html ----------
# Hand copies of the page, which page_sources() must match exactly: TABLE2[n] = (lo, hi) for BGPW's Table 2, hi None
# for "≥"; NEW[n] = (lo, hi, who) for the new results, who the cell's credit: its class on the page, c, cf, j, ca, a or s
# (the classes of the legend's keys, in the legend's order: c, cf, a, ca, j, s; cf, Opus 5.5 and Fable 5.2, since
# 2026-11-11: the cells of powers of 2 whose lower bounds are joins of Fable 5.2's sequences of that day, five then, 19 since 2026-11-19).  What a class is called is the page's
# alone, in its legend and its cells' titles: no word of those is here, in mstar.js or in the chart scripts, which look
# the legend's label up (page/shared.js's credit).  Until 2026-11-09 who was the title's words; when dreeves renamed
# Claude to Opus 5.5 on the page, page_sources stopped at its assertion and mstar.js could not be made ("it seems dumb
# that me tweaking the prose in index.html has yielded this much work from you").
TABLE2 = {8: (3, 3), 16: (4, 4), 24: (4, 4), 32: (5, 5), 40: (5, 5), 48: (6, 6), 56: (5, 5), 64: (6, 6), 72: (6, 6),
          80: (6, 6), 88: (6, 6), 96: (7, 7), 104: (6, 6), 112: (7, 7), 120: (6, 6), 128: (7, 7),
          136: (6, 6), 144: (8, 8), 152: (6, 6), 160: (7, 7), 168: (6, 6), 176: (7, 7), 184: (6, 6), 192: (9, 9),
          200: (7, 7), 208: (8, 8), 216: (7, 7), 224: (8, 8), 232: (7, 7),
          240: (10, 11), 248: (7, 7), 256: (8, 8), 264: (7, 7), 272: (8, 8), 280: (7, 7), 288: (9, 10), 296: (7, 7),
          304: (8, 9), 2 ** 51: (52, None)}
NEW = {240: (10, 10, 'c'), 288: (9, 9, 'j'),
       304: (8, 8, 'c'), 320: (9, 9, 's'), 336: (10, 10, 'j'), 352: (9, 9, 's'),
       368: (9, 9, 's'), 400: (9, 9, 's'), 416: (9, 9, 's'), 432: (11, 11, 'c'),
       448: (9, 9, 'c'), 464: (9, 9, 's'), 480: (12, 13, 'cf'),   # 12 to 14 (c) until 2026-11-17, when the unconditional form tree at 480:14 closed (searches/formtree/cells/480_14): Fable 5.2's run of Opus 5.5's method
       496: (9, 9, 'j'), 512: (9, 9, 'c'), 528: (11, 12, 'c'),
       576: (12, 12, 'c'),
       384: (10, 10, 'a'),
       544: (10, 10, 'c'),
       560: (10, 10, 'c'),
       592: (10, 10, 'ca'),
       608: (10, 10, 'ca'),
       624: (12, 12, 'c'),
       640: (10, 10, 'c'),
       656: (10, 10, 'ca'),
       672: (13, 13, 'c'),
       688: (10, 10, 'c'),
       704: (10, 10, 'c'),
       720: (13, 14, 'c'),
       736: (10, 10, 'c'),
       752: (10, 10, 'ca'),
       768: (13, 13, 'c'),
       784: (10, 10, 'ca'),
       800: (11, 11, 'c'),
       816: (12, 12, 'c'),
       832: (11, 11, 'c'),
       848: (11, 11, 'c'),
       864: (12, 14, 'c'),
       880: (11, 11, 'c'),
       896: (11, 11, 'c'),
       912: (13, 13, 'c'),
       928: (11, 11, 'c'),
       944: (11, 11, 'c'),
       960: (15, 15, 'c'),
       976: (11, 11, 'c'),
       992: (11, 11, 'c'),
       1008: (13, 13, 'c'),
       # (2^24, 2^27, 2^36, 2^37, 2^38, 2^43, 2^46, 2^56, 2^57, 2^65, 2^66, 2^67, 2^68, 2^71 and 2^72: lows one less until 2026-11-19, 2^24 of class j and the others c, when the sequences
       # of order 13 past the chart made 2^22, 2^35, 2^42, 2^50, 2^55, 2^63 and 2^68 the firsts for excesses 3, 5, 6, 7, 8, 9 and 10, 2^22, 2^35, 2^42, 2^50, 2^55 and 2^63
       # with cells since; of class ca those whose lows come from Astra's joins at 2^63 and 2^68: 2^63, 2^65, 2^66, 2^67, 2^68, 2^71 and 2^72)
       # (Later on 2026-11-21, Fable 5.2: 2^13, 2^26 and 2^60 have cells, firsts since that day, 2^14 and 2^15 too, settled that day, and the lows of the cells from 2^17 to 2^66 that the
       # sequences of that day at 2^13 and 2432 raise are one more; of class ca those under the firsts at 2^47 and 2^60, whose joins Astra's search found.)
       # (Later that morning, 2026-11-21, Fable 5.2: 2^59 has a cell, a first since then; the lows of the cells among 2^59, 2^63 and 2^64 are one more, by the sequence of that day at 7712.)
       # (At 08:02, 2026-11-21, Fable 5.2: 2^45 and 2^69 have cells, a first since then; the lows of the cells among 2^45, 2^46, 2^50, 2^51, 2^58, 2^69 and 2^70 are one more, by the sequences of that day at 2368 and 7744.)
       # (At 03:57, 2026-11-23, Opus 5.5: the lows of the cells among 2^37, 2^38, 2^61 and 2^62 are one more, by the sequence of that day at 7360.)
       2 ** 10: (11, 11, 'c'), 2 ** 11: (12, 12, 'c'), 2 ** 12: (13, 13, 'c'), 2 ** 13: (15, 15, 'cf'), 2 ** 14: (16, 16, 'cf'), 2 ** 15: (17, 17, 'cf'),
       2 ** 17: (19, 20, 'cf'), 2 ** 18: (20, 21, 'cf'),
       2 ** 20: (22, 23, 'c'), 2 ** 22: (25, 26, 'cf'), 2 ** 24: (27, 29, 'cf'), 2 ** 26: (30, 31, 'cf'),
       2 ** 27: (31, 33, 'cf'), 2 ** 28: (32, 34, 'cf'), 2 ** 29: (33, 35, 'cf'),
       2 ** 30: (34, 36, 'cf'),               # 33 to 36 until 2026-11-11, when that day's sequences made 2^30 the first power of 2 known to beat Thue-Morse by 4
       2 ** 33: (37, 40, 'cf'), 2 ** 34: (39, 41, 'cf'), 2 ** 35: (40, 43, 'cf'), 2 ** 36: (41, 44, 'cf'),   # 2^33 and 2^34: 36 and 37 below until then; 2^34: 38 until 2026-11-21, when it became the first for excess 5
       2 ** 37: (43, 45, 'ca'), 2 ** 38: (44, 46, 'ca'),
       2 ** 39: (45, 47, 'cf'),
       2 ** 41: (47, 50, 'cf'), 2 ** 42: (48, 51, 'cf'), 2 ** 43: (49, 53, 'cf'), 2 ** 45: (52, 55, 'ca'),
       2 ** 46: (53, 57, 'ca'), 2 ** 47: (54, 58, 'ca'), 2 ** 48: (55, 59, 'ca'),
       2 ** 49: (56, 60, 'ca'), 2 ** 50: (58, 61, 'ca'), 2 ** 51: (59, 63, 'ca'),               # 57 to 63 until later on 2026-11-11, when that day's sequences made 2^51 the first power of 2 known to beat Thue-Morse by 7
       2 ** 52: (60, 64, 'cf'), 2 ** 55: (63, 68, 'cf'), 2 ** 56: (64, 69, 'cf'), 2 ** 57: (65, 70, 'cf'),   # 2^52: 58 below until then
       2 ** 58: (67, 71, 'ca'), 2 ** 59: (68, 73, 'ca'), 2 ** 60: (69, 74, 'ca'), 2 ** 61: (71, 75, 'ca'), 2 ** 63: (73, 78, 'ca'), 2 ** 65: (75, 81, 'cf'),
       2 ** 66: (76, 82, 'cf'), 2 ** 67: (77, 83, 'ca'),   # 2^67: 76 until 2026-11-21, when it became the first for excess 10
       2 ** 68: (78, 84, 'ca'), 2 ** 69: (80, 85, 'ca'), 2 ** 71: (82, 88, 'ca'),   # 81 until the morning of 2026-11-21, when 2^71 became the first for excess 11 (2^72: 82 until then)
       2 ** 72: (83, 89, 'ca'),
       # (Opus 5.5, 2026-11-23: the firsts for excess 12 to 20, once Figure 2 reaches 2^128, each a product of two lower columns' joins)
       2 ** 74: (86, 92, 'ca'), 2 ** 82: (95, 102, 'ca'), 2 ** 87: (101, 108, 'ca'), 2 ** 95: (110, 118, 'ca'), 2 ** 98: (114, 122, 'ca'), 2 ** 106: (123, 132, 'ca'), 2 ** 111: (129, 139, 'ca'), 2 ** 119: (138, 149, 'ca'), 2 ** 122: (142, 152, 'ca'),
       # (Opus 5.5, 2026-11-24: 2^103 and 2^116, the firsts for excess 17 and 19 since then, by the join of three products of that day at 2^103 and its product with 2^13's; 2^106 and 2^119, firsts until then, keep their cells, and the lows of 2^104, 2^105, 2^117 and 2^118, which have none, are one more)
       2 ** 103: (120, 128, 'cf'), 2 ** 116: (135, 145, 'cf')}
# EXAMPLE_BY[n]: who found the example of order NEW[n][0] at n, as the page's remarks credit it, for each n whose lo
# is that cited value (no sequence of that order is here; columns() asserts that these are exactly those n).  A cited
# lo's ["page", who] names whose example it is, and a cited hi's whose proof, the cell's class.  At 496 they differ:
# the class is j, for the proof of the upper bound, and the remark credits the example of order 9 to BGPW (class s).  Empty since 2026-10-12: FOUND made every such lo explicit (352, 368, 400, 464 and 496 had been cited).
EXAMPLE_BY = {}
# CITED[n]: the page's values at n as (lo, hi, hiWhy), Table 2's first, then the new results'
CITED = {}
for _n, (_lo, _hi) in TABLE2.items(): CITED.setdefault(_n, []).append((_lo, _hi, ['table2']))
for _n, (_lo, _hi, _who) in NEW.items(): CITED.setdefault(_n, []).append((_lo, _hi, ['page', _who]))
# The hex codes in the page's code blocks, in page order (since 2026-11-18 the appendix's entries in order of their
# lengths, and so this list), as (label, m, hex) in the paper's Table 5 convention
# (overnight_v5.from_hex).  The label names the page and the code's name there.  It names the page by its site,
# equipow.dreev.es, since the chart's readout shows it (dreeves's README, 2026-10-31: "[IND] ... we should never refer to
# "index.html" in user-facing copy ... If that doesn't work for hovertext, we could just say "equipow p320" instead of
# "index.html p320""); "index.html" until then.  On the page each code is <code id="N:M">, N its length and M its order.
PAGE_CODES = (('equipow p1440', 16, '9E21C6F54B340E3CAF46C59F362A518761CD3896A8DAB346DC58D731D72B46AC9A3630DAA94E91D235364CD316F68A7B8AF8E336A449B12CD9E0D6D51AA55C49AC65CCCB90F2D5EA2A166DB9936D0369D05CF5A95CA006EF87B2'),
              ('equipow p320', 9, 'B24B649ED92CD2C36496CB2DB6295D974138BA41'),
              ('equipow BGPW 336', 10, 'C87695B43E0ED258AB29C7793D8521DB227C0B746D'),
              ('equipow q336', 9, '9C5479E2669C97071E731A62EBC06F28E87B4961DF'),
              ('equipow BGPW 352', 9, 'A4DB4926DB4D36584B26936D2CFA54B6F04B2C13D4A2'),
              ('equipow BGPW 368', 9, '96C965925B75B0CB249E583CF26B2E836C31DAC874B67D'),
              ('equipow BGPW 400', 9, '34DB69269A69269A6D379A8D1C57459C5B45E5100DBAF7EAAA'),
              ('equipow p432', 11, '5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46'),
              ('equipow p448', 9, 'A5994DB29B45A0FA5D26B24D665A5A66B24D64BA5F05A2D94DB299A5'),
              ('equipow BGPW 464', 9, '93C96596CB2586DB1C965964E69975A207755BE209CE5E28F2C35A92BA'),
              ('equipow p480', 12, 'B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3'),
              ('equipow BGPW 496', 9, 'C96992D92DB24B7596496D1A530DB5994EA699A9ACE072BDC57403B339A4CE'),
              ('equipow p192', 9, 'C1BE1E21CD63D295A7887A59'),
              ('equipow p528', 10, 'D920BDA31A6FDC8423BEC528AE51365BB4A6C36E419CCEF94C45BB00D13EE1EAA5'),
              ('equipow p528', 11, '9CA5A87A325DAF0ACC5936B5E14A70858F78E1DA867AADD8939CB718429D151737'),
              ('equipow p544', 10, '936976914B665A49A4F8E93CD6F9248349AE9349269B5DE486693CFECD24D2D924B2'),
              ('equipow p560', 10, '34D2E9F0DA19EC92492D966936ABCA25FAD924D26F2591EB64926924925D6E1A4BFE92'),
              ('equipow p576', 11, '9A4D54D7952F107A62ACE35B02B6A76B2B4EDE8C0968F255A481BA53F0B7E54B5DD08C39'),
              ('equipow p576', 12, 'E4272B599D2669CC47DAD42928E293EF770C121A76FD494E1D9CB1AC42338EA10FD3F8C5'),
              ('equipow p592', 10, '93CC6790EA26876D2DDA793492C92EB24C3B934525B66DADF25926920BA79E4D21B2CB359A'),
              ('equipow p608', 10, 'AC965934D659969A4CE792CD6492D72C836BE49E193612E97792C9AAB265AC867BAE921924D7'),
              ('equipow p624', 11, '8F5508E59DDE388857B94A274173BA87E1DA2F19563A50E398A0F9DC6295E65B9E06B09E398F54'),
              ('equipow p624', 12, '95AE444B9EF58585519694BD6A7BF40311C6399A5399EA5356D2AFC56392B48816726C63E4AC7B'),
              ('equipow p656', 10, 'C32DA6E924AED161B6D94216DB6CBE4A4932FD4996135826A94DF6CA6CB4DA1EB4D90D92134D82F8EE'),
              ('equipow p672', 12, 'A9D2518FC721CF719C870CD87698C3A1EEE1C5C739CC62983F91646AA8EF30EE2791C5AA4F470CCD05EE'),
              ('equipow p672', 13, '94E71B4AB0A5E5785A33AC2F58C2778C2D699A17D467584AD5B4297A4EB48D2BCAD2B3C5255AE612A567'),
              ('equipow p688', 10, 'D609A6FA4D82B3217696DF35964D0CA3453DB3C145B8DD259279308669FE96DDE4F249A212296FBA493457'),
              ('equipow p720', 12, 'D508EE7A682A54DC2FCCC5DEAEC42DD200500E3FD2F9BBA0E66FEE28F1A983831A12C69D5181FC6CBDA6B9703C'),
              ('equipow p720', 13, 'AC98B16ECCCACE4C4CD952CCCF94AC4C95ECC54D9BCC5AB1408CED96ECDCBA49C40ACA1EFDA95A8DC34E0C5C5D'),
              ('equipow p752', 10, 'D1C7951270B6456FBEC039A7FA05A459E422DB6416E76D06DB2D90D32FD010FBB30A6DB6D80DBAC3059EDB5826CB4C'),
              ('equipow p768', 12, 'AB5186723E74399FC150E3179F7008E728787ABA4678EAF3C4C73E033113ADA98C721D7131CE439DA5FECD734DE50904'),
              ('equipow p768', 13, '959CE12B46B3BC272BC27489A56ACED0B5657AC652AC2B714AD49E2B8D5E35AC305B4E35D5A5235893AD277894A4FDEF'),
              ('equipow p784', 10, 'B24F643A19DC1B49FC831C2FF25926F80B24FFC1B423C92E933B25304F60FA2B341F59FFB668379251243048E2BE6BA89F'),
              ('equipow p800', 11, '966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9'),
              ('equipow p816', 12, '9DA92A11F804FDEB7EBC4021CB6722C67D282BD35624BCF238A1E1DD66DC9D496BC238EF6CB84018A2D7854A72C535DDF61A9C'),
              ('equipow p832', 11, 'B49969329E6934CB4DB69B4D34924C359B4926DB69A4DB49369F69261A4D36D6499A926D2C9B68B4D369A4D2DDB6904936DA69B4'),
              ('equipow p848', 11, '96B905B25BADB2496D32C924B74B6C96596CF25964B28925B25B6DAA5B6D96C965164B14B2C92F52D12596C97CB6CBEC86592CB2C9'),
              ('equipow p880', 11, 'C965B1C92D925B6C92D964BE4D2FB20B6592492D16D9259ADB6FD64926964925A64B6E62EF60D2CB24B6D925B2CB05960B6CB6CB75B74F'),
              ('equipow p896', 11, 'B25B2D92512CD65BA5B2DB2514CD65B8CB698E6364E65905B6196D12C82CBADB3DB6E32C9659ACB6D96512492C9ECB2196DB2C92D944B259'),
              ('equipow p912', 12, 'CC89A4F3BCE43B44239C97C2E14F0BA7BB0F72385611B5C017EDB6E00B8BE67C9C6A7D4932882758827785E78ECF3D0CE8FC8777896911C683'),
              ('equipow p912', 13, '9CA178CEDC15EC48CC9784AF5D4F62844F4ACEF28CAC69CA9688C5EBCAD39469CCD6941CE548CEAC9E3D45CC45ADEBD8075C8D296C5A90B865'),
              ('equipow p928', 11, '869B4DEE9A60A4D14BA2D35DA4DA6D14F349E65B4C27926C54D36D268358369F29B6936DA6BA69269A65259349A4D86D765349B49A69BA9F65B4'),
              ('equipow p944', 11, 'B2D920F6C32D8A4A75B6E965D2D964B44968F291A432D97C96F964B2586CB47B64965B2DBE4934929B4C125B6D93494F92CB2DBA436596896D7ADA'),
              ('equipow p960', 15, '9725C8B86EC3C3B435D8B91E458B1D0E1FCD60E5CB463A599D60ADAB329C5C65B2C73312DC259A6AD8ABB02A7B33E9EDA1643E0624D6F93D11C49414'),
              ('equipow p976', 11, 'A69A48B5DB6B269A6D14CA1936324D74DB6833DB6DB4DB4134921D949A68E6986F25DA6D348F4994935D86BB49E69ACC27D067268769B4D219B67249A4'),
              ('equipow p992', 11, '94E96372496EB6496DB2D364864B2D902967B24E2DBF7B71908D6D92DA44905B4EF2CD2596CB7192D944B2C8ECB60967B24E25B2DB24BA5F2D96DB859749'),
              ('equipow p1008', 12, 'E5154C71ABE24D5C4FB0A2B9CB519E2C7CA61813D6DCC264974FBB8DB408B511DE62BC3738CE671CE23696059CE54D0CD2B085F5EFABC2A3B1AE172FF12850'),
              ('equipow p1008', 13, 'E181F56CCED68481CACADC8FEC6C5C158C6D7B5AC6C409888F729E5D1C5E97A86D0B4E8E6DEB78C270962448CEB9C9E518CAD4ECA54E9CB59CE748DA4D9C3D'),
              ('equipow p1024', 11, 'C8ECB0E96876C9A4A6C937B2556D97493CB06969965365B8D924B21B2D9ADA35854B2FD64B25B7C91892DD653A4979B0A96C16CB25B2CB6696196D1EC93C97CB'),
              ('equipow p112', 7, 'A5994DB29B45A0'),
              ('equipow p48', 6, 'C27D8C'))
# Claude's own examples of order 9 at the lengths where the page credits BGPW's (352, 368, 400, 464 and 496), found on
# 2026-10-12 by a CP-SAT search (scratch/lower24-design/wider/), as (n, m, hex) in overnight_v5.from_hex's convention;
# BGPW's examples came first, as the page says, and since 2026-10-12 the page shows theirs (PAGE_CODES), which win
# the tie, so these are an independent check.  Their label is pagegen/mstar.py, this file, as brute force's ('found
# here' until 2026-11-18; dreeves: "there should be no "found here". what does "here" mean? totally ambiguous").
FOUND = ((352, 9, '969E4C06F693B61B683699E934D241A6DB4936D7CDA6'),
         (368, 9, 'B449E6A1DB4AB5A123D2DB84B7592CB2496596DB64B4C9'),
         (400, 9, 'A70B2F45D60B4BE22CD2DE51B49B4924DB6D26D349A6926DB4'),
         (464, 9, '8EA4DC62B3DF10709957C395683E3A4D369A6F30DA6984D36D86934C26'),
         (496, 9, 'C2BAD83D5017FA285E3D82ED96135DA2394EB48A6D349E6994D349B6D34DA7'),
         # Since 2026-11-18 (dreeves, of every witness made (-1)^lo-symmetric: "making all witnesses conforming sounds
         # great"), the six columns that products and joins p_a v p_b v p_a of conforming columns leave one order short
         # (scratch/witness-20261118/): each the Symmetry section's p v q v s p*, here p_a v p_b v -p_a, of order
         # min(lo(a), lo(b)) and, by BGPW's Symmetry (Theorem 4.1), one more; each code that sequence's, made by
         # scratch/witness-20261118/six.py, as an example, so that the page's constructions need no minus sign and no
         # parity step.
         (136, 6, '96696996998EAA3C5'),                    # p_32 v p_72 v -p_32
         (152, 6, '9669699696C362DE4A3'),                  # p_32 v p_88 v -p_32
         (1328, 11, 'C394E65AB989457A86B7D0D921636E76C6849B0BED615EA2919D5A6729C396B905B25BADB2496D32C924B74B6C96596CF25964B28925B25B6DAA5B6D96C965164B14B2C92F52D12596C97CB6CBEC86592CB2C9'),   # p_240 v p_848 v -p_240
         (1360, 11, 'C394E65AB989457A86B7D0D921636E76C6849B0BED615EA2919D5A6729C3C965B1C92D925B6C92D964BE4D2FB20B6592492D16D9259ADB6FD64926964925A64B6E62EF60D2CB24B6D925B2CB05960B6CB6CB75B74F'),   # p_240 v p_880 v -p_240
         (1424, 11, 'C394E65AB989457A86B7D0D921636E76C6849B0BED615EA2919D5A6729C3B2D920F6C32D8A4A75B6E965D2D964B44968F291A432D97C96F964B2586CB47B64965B2DBE4934929B4C125B6D93494F92CB2DBA436596896D7ADA'),   # p_240 v p_944 v -p_240
         (1456, 11, 'C394E65AB989457A86B7D0D921636E76C6849B0BED615EA2919D5A6729C3A69A48B5DB6B269A6D14CA1936324D74DB6833DB6DB4DB4134921D949A68E6986F25DA6D348F4994935D86BB49E69ACC27D067268769B4D219B67249A4'))   # p_240 v p_976 v -p_240
# The joins of the page's codes, in page order, as (label, m, ids): each <span data-join="IDS" data-order="M"> of a code
# block, IDS the ids N:M of codes of the code blocks, separated by spaces, whose signs one after the other are the
# join's (join() above, the paper's ∨), and M its order.  The label names the page and the join as the page writes it.
# Since 2026-10-31, when the section "Claude's examples as sets" left the page (dreeves: "every bipartition we give
# should be presented the same way as an expandable hex code"): the 528 entry's f = p192 ∨ q336, neither symmetric nor
# antisymmetric, so that no code in the paper's form can hold it, was that section's SClaude[10][528].
PAGE_JOINS = (('equipow p192 ∨ q336', 10, ('192:9', '336:9')),)


def page_n(s):
    """An n cell of the page's tables: digits, or \\(2^{k}\\) (LaTeX since 2026-10-28; a one-digit k unbraced)."""
    m = re.fullmatch(r'(\d+)|\\\(2\^\{?(\d+)\}?\\\)', s)
    assert m, s
    return int(m[1]) if m[1] else 2 ** int(m[2])


def page_value(s):
    """A value cell: v, "a or b", "\\(\\ge a\\)" or "a–b", as (lo, hi), hi None when open."""
    for pat, f in ((r'(\d+)', lambda g: (int(g[0]), int(g[0]))), (r'(\d+) or (\d+)', lambda g: (int(g[0]), int(g[1]))),
                   (r'\\\(\\ge (\d+)\\\)', lambda g: (int(g[0]), None)), (r'(\d+)–(\d+)', lambda g: (int(g[0]), int(g[1])))):
        m = re.fullmatch(pat, s)
        if m: return f(m.groups())
    raise AssertionError(s)


# The lengths of the new results' upper rows, in order, since 2026-10-27, when the block came to subsume Table 2
# (dreeves: "how about making our color-coded table totally subsume the BGPW table?"; Stan Wagon, by dreeves: the upper
# part "should include 256, 512, and 1024 for completeness"; dreeves: "multiples of 16 with one-sentence explanation
# sounds good"): Table 2's, every multiple of 8 up to 304, then every multiple of 16 up to NMAX.  An odd multiple of 8
# has order at most 7 (the two lemma), and from 200 on every one has 7, so past 304 none has anything to show.
UPPER = tuple(range(8, 305, 8)) + tuple(range(320, 1025, 16))   # to 1024, the chart's NMAX until 2026-11-10 ([BOU])


def page_sources(html):
    """Table 2, the new results, the codes and the joins, parsed out of index.html and asserted equal to the hand
    copies above.  Returns {'table2': {n: (lo, hi)}, 'new': {n: (lo, hi, who)}, 'codes': [(m, hex)],
    'joins': [(m, ids)]}.  The page's tables of class "block" are Table 2's three, then the new results', which since
    2026-10-27 subsume Table 2: their upper rows, of the lengths UPPER in order, written in digits, then their powers
    of 2, written \\(2^{k}\\), k rising from 3.  Every cell of the new results has a title, whose words are the page's
    alone and are not read; a cell with no class copies Table 2's entry at its n, and every entry of Table 2
    that is not a new result is so copied; every other cell has a class, its value cell the same class, and is a new
    result, the class its credit (who).  A length shown twice, in the upper rows and as a power of 2 (8 to 1024), is the same cell both times.  Each
    code of a code block is <code id="N:M">, an anchor that the page's names of it link to, N its length and M its order
    (2026-10-31, [IND]), the ids distinct; each join of a code block, <span data-join="IDS" data-order="M"> (since
    2026-10-31, when the page's sets left it), joins codes of the code blocks, IDS their ids, M its order; and each code
    or join has its block's labels' (m = M) in order, one for each."""
    tables = re.findall(r'<table class="block">(.*?)</table>', html, re.S)
    rows = []
    for t in tables:
        ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">(.*?)</tr>', t, re.S)[1])
        vals = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="vals">(.*?)</tr>', t, re.S)[1])
        assert len(ns) == len(vals) >= 1, (ns, vals)
        rows.append([(c, page_n(c), attr, va, v) for (attr, c), (va, v) in zip(ns, vals)])
    table2 = {n: page_value(v) for row in rows[:3] for c, n, attr, va, v in row}
    assert all(attr == '' and va == ' lang="en"' * (' or ' in v) for row in rows[:3] for c, n, attr, va, v in row)
    assert len(table2) == sum(map(len, rows[:3])) == 39
    upper = [row for row in rows[3:] if all(re.fullmatch(r'\d+', c) for c, *_ in row)]
    pows = rows[3 + len(upper):]
    assert rows[3:3 + len(upper)] == upper and all(re.fullmatch(r'\\\(2\^\{?\d+\}?\\\)', c) for row in pows for c, *_ in row)
    assert tuple(n for row in upper for c, n, *_ in row) == UPPER
    ks = [n.bit_length() - 1 for row in pows for c, n, *_ in row]
    assert ks and ks[0] == 3 and ks == sorted(set(ks)), ks
    cells = [cell for row in rows[3:] for cell in row]
    for n in {n for c, n, *_ in cells}:
        assert len({(attr, va, v) for c, m, attr, va, v in cells if m == n}) == 1, n
    titled = [re.fullmatch(r'( class="(\w+)")? title=\'[^\']+\'', attr) for c, n, attr, va, v in cells]
    assert all(t and va == (t[1] or '') for t, (c, n, attr, va, v) in zip(titled, cells)), [cell for t, cell in zip(titled, cells) if not (t and cell[3] == (t[1] or ''))]
    copies = {n: page_value(v) for t, (c, n, attr, va, v) in zip(titled, cells) if not t[2]}
    assert set(copies) <= set(table2) and all(table2[n] == v for n, v in copies.items()), copies
    new = {n: page_value(v) + (t[2],) for t, (c, n, attr, va, v) in zip(titled, cells) if t[2]}
    assert set(table2) - set(new) == set(copies), set(table2) - set(new) - set(copies)
    codes, ids, joins = [], [], []
    for block in re.findall(r'<p class="code">(.*?)</p>', html, re.S):
        ms = [int(m) for m in re.findall(r'\\\(\(m = (\d+)\)\\\)', block)]
        tags = re.findall(r'<code id="(\d+):(\d+)">([0-9A-F]+)</code>|<span data-join="([\d: ]+)" data-order="(\d+)">', block)
        assert len(ms) == len(tags) == block.count('<code') + block.count(' data-join=') >= 1, block
        coded = [(m, int(n), int(k), h) for m, (n, k, h, _, _) in zip(ms, tags) if h]               # its codes
        joined = [(m, int(order), parts) for m, (_, _, h, parts, order) in zip(ms, tags) if not h]   # its joins
        assert all((n, k) == (len(v5.from_hex(h, m)), m) for m, n, k, h in coded), block
        assert all(order == m for m, order, _ in joined), block
        codes += [(m, h) for m, _, _, h in coded]
        ids += [f'{n}:{k}' for _, n, k, _ in coded]
        joins += [(m, tuple(parts.split(' '))) for m, _, parts in joined]
    assert len(set(ids)) == len(ids), ids
    assert all(set(parts) <= set(ids) for _, parts in joins), joins
    assert table2 == TABLE2, table2
    assert new == NEW, new
    assert codes == [(m, h) for _, m, h in PAGE_CODES], codes
    assert joins == [(m, parts) for _, m, parts in PAGE_JOINS], joins
    return {'table2': table2, 'new': new, 'codes': codes, 'joins': joins}


# ---------- explicit sequences from elsewhere ----------
# BGPW_T4: the paper's Table 4, "RPs that suffice, asymptotically, to give all witnessing sets" (arXiv:1912.03491v1,
# p. 13): (m, (length, length), hex), from_rp giving each length.  Copied from the PDF's text; every member's order is
# checked exactly in explicit().
BGPW_T4 = ((3, (12, 20), 'A3C'), (4, (24, 32), '995C'), (5, (48, 64), 'A4DD233C'), (5, (56, 72), '96A371999'),
           (6, (104, 120), 'C32F8696687E155'), (6, (112, 128), '936D342C73B58A0F'),
           (7, (208, 224), 'A55A9936CCA5363A65E41B6CC35A'),
           (7, (200, 328), '9559B51655655553755459555A31ED24F651A6C0F'),
           (7, (216, 344), '953D547143575D547554D551077417ED3C9A6982C37'),
           (7, (232, 360), '95555D95510D77154D75994531D714F238C7EB8831D1D'),
           (7, (248, 376), 'C557185D75534395571D14715DC7534EC412F9C933CB199'),
           (7, (264, 392), 'D29535559352D575954B549555A54B555C968936B1BDC6538'),
           (7, (280, 408), 'A8ADA3CAE2B88E2B9AC32CAE2B8EE2B8AC347D930FE4826A3C7'),
           (7, (296, 424), '9996356B5496555555555E925945DA7532555477C255A9AA6587A'),
           (7, (312, 440), 'A56A69555555B59550965AD5B71515554E56725A64EA946FB10D563'))
# BGPW_T5: the paper's Table 5, "Sporadic examples" (arXiv:1912.03491v1, p. 13): (m, n, hex).
BGPW_T5 = ((5, 40, 'C1EC9'), (6, 48, 'C27D8C'), (6, 72, '998EAA3C5'), (6, 88, '96C362DE4A3'),
           (8, 144, 'A962D5AF05357231CD'), (8, 208, 'C5A2CB6B945B28BC43ADB6586C'),
           (8, 240, '8DE3424EBD39684AD636AD8932C4F9'), (8, 272, 'D0EC315B66B4DE6110D339D63B4CD61BC4'),
           (8, 304, 'A9E21ACCB5C96794C56D9C4255B4336DEAD8A4'), (8, 336, '92D6F430CB2AD476994F60DEB609EA1158973CA7D2'),
           (8, 368, 'B4D121ABDED920EAF02CE76086B55BA6995ABE9A43247A'), (9, 192, 'C1BE1E21CD63D295A7887A59'),
           (9, 240, '9666995C93C3AA5935E81CB7C2938D'))
# Where each of overnight_v5.EXAMPLES comes from, by its comments there: the published paper's Table 5, the page, or
# Thue-Morse; the rest were found with CP-SAT for overnight_v5's quals.
# (Those CP-SAT ones labeled 'overnight_v5 EXAMPLES' until 2026-11-18, then by the file that holds them.)
EXAMPLE_LABELS = {(240, 10): 'BGPW Table 5', (432, 11): 'equipow p432', (192, 9): 'BGPW Table 5',
                  (384, 10): 'engine/overnight_v5.py',
                  (320, 9): 'equipow p320', (336, 9): 'equipow q336', (48, 6): 'BGPW Table 5',
                  (112, 7): 'BGPW Table 5', (304, 8): 'BGPW Table 5', (64, 6): 'Thue–Morse',
                  (40, 5): 'engine/overnight_v5.py', (48, 5): 'engine/overnight_v5.py', (56, 5): 'engine/overnight_v5.py',
                  (104, 6): 'engine/overnight_v5.py'}


def mitm(n, m):
    """A sequence of length n and order >= m, or None: meet in the middle on the two halves' power sums j < m, in
    int64 (each |sum| < n^m, asserted below 2^62), matched exactly as tuples."""
    assert n ** m < 2 ** 62
    h = n // 2
    def half(lo, k):
        signs = 1 - 2 * ((np.arange(2 ** k)[:, None] >> np.arange(k)[None, :]) & 1)
        powers = np.arange(lo, lo + k, dtype=np.int64)[:, None] ** np.arange(m, dtype=np.int64)[None, :]
        return signs, signs @ powers
    sl, left = half(0, h)
    sr, right = half(h, n - h)
    seen = {tuple(row): i for i, row in enumerate(left.tolist())}
    for j, row in enumerate(right.tolist()):
        i = seen.get(tuple(-x for x in row))
        if i is not None: return [int(t) for t in sl[i]] + [int(t) for t in sr[j]]
    return None


@lru_cache(maxsize=None)
def brute(n):
    """m*(n) and a witness of that order, for n <= BRUTE_MAX, by meet in the middle for m = 1, 2, ... until none."""
    assert 1 <= n <= BRUTE_MAX, n
    m, best = 0, [1] * n
    while (a := mitm(n, m + 1)) is not None: m, best = m + 1, a
    return m, best


@lru_cache(maxsize=None)
def symmetric(n):
    """A (-1)^m-symmetric sequence of length n and order m = m*(n) (brute), for even n <= BRUTE_MAX, so that it has a
    code (to_hex; 2026-11-18: brute's own witness need not be symmetric): of the 2^(n/2) left halves, each read as a
    binary number, f_0 its first bit, 1 for +1, the greatest whose sequence has order m.  One exists: BGPW's Symmetry
    Conjecture holds through order 11 (the page's Symmetry section)."""
    m, h = brute(n)[0], n // 2
    assert n % 2 == 0 and m >= 1 and 2 ** h * n * 8 <= 2 ** 27, n            # the arrays below: 16 MiB at n = 32
    x = np.arange(2 ** h - 1, -1, -1, dtype=np.int64)[:, None]
    left = 2 * ((x >> np.arange(h - 1, -1, -1, dtype=np.int64)[None, :]) & 1) - 1
    full = np.concatenate([left, (-1) ** m * left[:, ::-1]], axis=1)
    sums = full @ (np.arange(n, dtype=np.int64)[:, None] ** np.arange(m, dtype=np.int64)[None, :])
    found = np.flatnonzero((sums == 0).all(axis=1))
    assert len(found) > 0, (n, m)
    a = [int(t) for t in full[found[0]]]
    assert order(a) == m, (n, m)
    return a


def symmetry_codes(html):
    """The codes of the page's Symmetry section, as [(n, m, hex)] in page order: each <code id="N:M">HEX</code> of its
    section of class symmetry, where a code is a sequence's (quals_symmetry), of length N and order M, in
    overnight_v5.from_hex's convention.  Sources of the chart since 2026-11-10, when it came to reach the lengths of
    six of them ([BOU]): 1040, 1072, 1136 and 1168 have their lower bound, 11, from theirs, which settles them."""
    [sec] = re.findall(r'<section class="symmetry"[^>]*>.*?</section>', html, re.S)
    found = [(int(n), int(m), h) for n, m, h in re.findall(r'<code id="(\d+):(\d+)">([0-9A-F]+)</code>', sec)]
    assert found and len(found) == sec.count('<code') and all(len(v5.from_hex(h, m)) == n for n, m, h in found), sec.count('<code')
    return found


@lru_cache(maxsize=None)
def explicit():
    """Every explicit sequence, as {(n, label): sequence}, in this order of preference: Thue-Morse, BGPW's Table 4,
    BGPW's Table 5 (arXiv v1, and the published one through overnight_v5.EXAMPLES), the page's codes, the page's joins
    of them, the codes of the page's Symmetry section (symmetry_codes), the rest of overnight_v5.EXAMPLES, brute
    force's orders with a symmetric sequence of each (symmetric, order >= 1 only) and FOUND, both labeled
    pagegen/mstar.py, the file that makes or holds them ("found here" until 2026-11-18).  Each sequence's exact order is
    asserted equal to what its source says; at a repeated (n, label) the one of higher order stays."""
    html = open(PAGE, encoding='utf-8').read()
    page_sources(html)                                      # the page as PAGE_CODES and PAGE_JOINS have it
    coded = {f'{len(v5.from_hex(h, m))}:{m}': v5.from_hex(h, m) for _, m, h in PAGE_CODES}   # by the codes' ids
    v5_bgpw = [(k, h) for k, h in v5.EXAMPLES.items() if EXAMPLE_LABELS[k] == 'BGPW Table 5']
    v5_rest = [(k, h) for k, h in v5.EXAMPLES.items() if EXAMPLE_LABELS[k] != 'BGPW Table 5']
    assert set(EXAMPLE_LABELS) == set(v5.EXAMPLES)
    for m, ns, h in BGPW_T4: assert set(bin(int(h, 16))[2:].zfill(4 * len(h))[max(ns) // 2:]) <= {'0'}, h
    entries = ([('Thue–Morse', k, thue_morse(k)) for k in range(1, NMAX.bit_length())]
               + [('BGPW Table 4', m, from_rp(h, m, n)) for m, ns, h in BGPW_T4 for n in ns]
               + [('BGPW Table 5', m, from_rp(h, m, n)) for m, n, h in BGPW_T5]
               + [('BGPW Table 5', m, v5.from_hex(h, m)) for (n, m), h in v5_bgpw]
               + [(label, m, v5.from_hex(h, m)) for label, m, h in PAGE_CODES]
               + [(label, m, reduce(join, (coded[i] for i in ids))) for label, m, ids in PAGE_JOINS]
               + [(f'equipow p{n}', m, v5.from_hex(h, m)) for n, m, h in symmetry_codes(html)]
               + [(EXAMPLE_LABELS[n, m], m, v5.from_hex(h, m)) for (n, m), h in v5_rest]
               + [('pagegen/mstar.py', brute(n)[0], symmetric(n)) for n in range(1, BRUTE_MAX + 1) if brute(n)[0] >= 1]
               + [('pagegen/mstar.py', m, v5.from_hex(h, m)) for n, m, h in FOUND])
    assert all(len(v5.from_hex(h, m)) == n for n, m, h in FOUND)
    out, orders = {}, {}
    for label, m, a in entries:
        assert order(a) == m, (label, len(a), m)
        key = (len(a), label)
        if m > orders.get(key, -1): out[key], orders[key] = a, m
    return out


# ---------- upper bounds ----------

def two(n): return 2 ** ((n & -n).bit_length() - 1) - 1


def prop44(n):
    """BGPW's Proposition 4.4 as a bound (2026-11-11): with t the power of 2 in n, a sequence of length n and order
    t - 1 has |f(-1)| >= 2^(t-1), f(-1) being its alternating sum (mod 2, f is (x - 1)^(t-1) S^t with S = 1 + x + ... +
    x^(n/t - 1), odd at 1, so f/(x - 1)^(t-1) is odd at -1 and f(-1) an odd multiple of 2^(t-1)).  As |f(-1)| <= n,
    order t - 1, the most that two(n) allows, needs n >= 2^(t-1): t - 2 below that, t - 1 from there on.  At t = 16
    that is 14 for every odd multiple of 16 below 32784."""
    t = n & -n
    return t - 2 if n < 2 ** (t - 1) else t - 1


def norm(n, p):
    """The norm lemma's bound for the prime p, which must not divide n: the largest m >= 0 with
    p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1)."""
    assert sp.isprime(p) and n % p, (n, p)
    rhs = (p * sum(len(range(r, n, p)) ** 2 for r in range(p))) ** (p - 1)
    m = 0
    while p ** (2 * m + 2) * (p - 1) ** (p - 1) <= rhs: m += 1
    return m


def residue_sums3(n, m):
    """The admissible residue sums mod 3 of length n at order m >= 1, (D_0, D_1, D_2), by the closed form of residue3:
    of zero sum, D_r = size(3, r) mod 2 and |D_r| <= size(3, r), D_0 = D_1 = D_2 mod 3^floor(m/2), and every D_r a
    multiple of 3^floor((m - 1)/2), which are tried in turn."""
    assert m >= 1, m
    q, Q = 3 ** ((m - 1) // 2), 3 ** (m // 2)
    s = [(n - r + 2) // 3 for r in range(3)]                # size(3, r); len(range(r, n, 3)) overflows past 2^63
    d0s, d1s = ([d for d in range(-(x // q) * q, x + 1, q) if (d - x) % 2 == 0] for x in s[:2])
    return [(d0, d1, -d0 - d1) for d0 in d0s for d1 in d1s
            if abs(d0 + d1) <= s[2] and (d0 + d1 - s[2]) % 2 == 0 and (d0 - d1) % Q == 0 and (d0 + 2 * d1) % Q == 0]


def residue3(n):
    """The residue condition mod 3 as a bound, in closed form (Fable 5.2, 2026-11-16; dreeves: "yes to mod-3 boxes",
    then "ok, go ahead with breaking ties in favor of the mod-3 argument"), for an even n that 3 does not divide (an
    odd n has no sums at all, the sizes' sum being odd): the largest m >= 1 at which admissible residue sums mod 3
    exist (residue_sums3), so that m*(n) <= it.
    The closed form: L(3, m) is the vectors D of zero sum with D_0 = D_1 = D_2 mod 3^floor(m/2) and every D_r a
    multiple of 3^floor((m - 1)/2).  For (x - 1)^2 = (1 + x + x^2) - 3x, and mod x^3 - 1 the first term times x - 1 is
    0 and times x is itself: so (x - 1)^(2k) = (-3)^(k-1) (1 + x + x^2) + (-3)^k x^k and (x - 1)^(2k+1) =
    (-3x)^k (x - 1) there, whose multiples are the zero-sum vectors that are equal mod 3^k, or multiples of 3^k.  (At
    an even m the divisibility follows from the congruence and the zero sum, at an odd m the congruence from the
    divisibility; both are tested, as the page's box states both.)  This is BGPW's Proposition 4.3 at p = 3, with
    Proposition 4.2's sizes, parities and zero sum; quals_mstar's q_residue_condition_mod_3_has_its_closed_form holds
    it to the lattice by brute force and to residue_vectors' enumeration.
    It implies the norm bound for 3: admissible D have D_0 + D_1 w + D_2 w^2 (w a primitive cube root of 1) a nonzero
    multiple of (1 - w)^m, of norm 3^m at least, and that norm is at most the norm lemma's cap.  So residue3(n) <=
    norm(n, 3), and it comes before it among a column's reasons.
    No admissible sums exist once 3^floor((m - 1)/2) exceeds every class size: all three would be 0, and since 3 does
    not divide n the sizes are two consecutive numbers, one of them odd, whose sum is odd.  Order m implies order
    m - 1, so the bound is the first m below that with sums, going down."""
    assert n >= 2 and n % 2 == 0 and n % 3, n
    m = 1
    while 3 ** ((m - 1) // 2) <= (n + 2) // 3: m += 1      # (n + 2) // 3 is size(3, 0), the largest class
    assert residue_sums3(n, m) == [], (n, m)
    while not residue_sums3(n, m): m -= 1                  # ends at 1 or above: an even n has sums at order 1
    return m


def chain_none(n, m, chain, sweep, cap):
    """Is there no admissible vector at order m mod chain[-1], each level enumerated (in the given sweep) under each
    admissible vector of the level before?  True only on a finished enumeration; False as soon as one is found; Capped
    past cap nodes."""
    assert all(b % a == 0 for a, b in zip(chain, chain[1:])), chain
    budget = Budget(cap)

    def go(i, parent):
        for D in residue_vectors(n, chain[i], m, parent, budget, sweep):
            if i == len(chain) - 1 or go(i + 1, (chain[i], D)): return True
        return False
    return not go(0, None)


# RESIDUE[n] = (m, chain, sweep): the claims, each checked by chain_none on every run.  Found by
# scratch/mstar/residue_search.py: for every even n whose two and norm bounds exceed the explicit lo, orders from that
# bound down, the chains (3), (4), (5), (7), (3, 9), (4, 8), (11), (13), (4, 8, 16), (5, 25), (3, 9, 27), (7, 49),
# (4, 8, 16, 32) in the sweep 'natural', each capped at 300000 nodes; a column's claim is the least order killed.  Then
# again with larger caps, and in the sweep 'digits', where CP-SAT (as a guide only) found no vector or the page cites a
# proof by residues: 120 and 136 mod 8, 624 at order 13 mod 25, 512 mod 27.  720's, at order 15 mod 16, is BGPW's
# Prop. 4.4 (q = 4) in residue form, from the check of mstar.js; it settles at once in L+(16, 15).  Each claim's sweep
# up to 1024 is 'digits' (the same as 'natural' for a prime) but 624's, which takes 670000 nodes in 'natural' and 3.1
# million in 'digits'.  Claims that do not set hi (where a citation is lower: 96, 240, 288, and 480 since 2026-11-17, whose claim at order 15 mod 7 the form-tree proof of order 14 replaced) are left out.  1008's, at order 14 mod
# 5, by scratch/upto1024/residue1008.py when the chart reached 1024 (2026-10-27), in both sweeps; at order 13 the
# chains (5, 25), (7, 49) and (4, 8, 16, 32) capped there at 300000 nodes, and at 10^7 too in both sweeps
# (scratch/upto1024/order13.py), and every other chain found an admissible vector.
# Since 2026-11-16 no claim has the chain (3): the residue condition mod 3 is computed in closed form (residue3) at
# every n that 3 does not divide, with no enumeration, and comes before the norm bound.  The 44 claims that had it
# (40, 128, 208, 224, 352, 368, 400, 416, 448, 464, 608, 640, 656, 688, 704, and 29 past 1024) gave the same bounds.
RESIDUE = {24: (5, (5, 25), 'digits'), 48: (7, (5, 25), 'digits'), 72: (7, (4, 8), 'digits'),
           80: (7, (3, 9), 'digits'), 88: (7, (3, 9), 'digits'), 104: (7, (4, 8), 'digits'),
           120: (7, (4, 8), 'digits'), 136: (7, (4, 8), 'digits'), 160: (8, (3, 9), 'digits'),
           192: (10, (5,), 'digits'), 256: (9, (3, 9), 'digits'), 336: (11, (5,), 'digits'),
           384: (12, (5,), 'digits'), 432: (13, (5,), 'digits'),
           496: (10, (3, 9), 'digits'), 512: (10, (3, 9, 27), 'digits'), 528: (13, (5,), 'digits'),
           576: (13, (5,), 'digits'), 624: (13, (5, 25), 'natural'), 672: (14, (5,), 'digits'),
           720: (15, (16,), 'digits'), 736: (11, (3, 9), 'digits'), 768: (14, (5,), 'digits'),
           784: (11, (3, 9, 27), 'digits'), 864: (15, (5,), 'digits'), 912: (14, (5,), 'digits'),
           960: (16, (7,), 'digits'), 1008: (14, (5,), 'digits'),
           # Past 1024 (2026-11-10, [BOU]; scratch/bou-20261110/search.py): for each of the 60 even n from 1026 to 2048
           # whose two and norm bound exceeds its explicit lo, the orders from that bound down, each chain of CHAINS
           # in each sweep of SWEEPS, capped at MTOP_CAP nodes, which are mtop_at's tests; the claim is the least order
           # killed, in the sweep that killed it.  The other 16 of the 60 keep their two and norm bound.  (29 of these
           # claims had the chain (3) and left on 2026-11-16, for residue3.)
           1056: (15, (5,), 'natural'), 1104: (15, (5,), 'natural'), 1152: (14, (5,), 'natural'),
           1296: (15, (5,), 'natural'), 1344: (15, (5,), 'natural'), 1440: (18, (7,), 'natural'),
           1472: (12, (3, 9), 'natural'), 1536: (15, (5,), 'natural'), 1584: (15, (5,), 'natural'),
           1632: (16, (5,), 'natural'), 1728: (16, (5,), 'natural'), 1776: (15, (5,), 'natural'),
           1824: (15, (5,), 'natural'), 1920: (19, (7,), 'natural'), 2016: (16, (5,), 'natural'),
           # Past the chart (found by Fable 5.2 on 2026-11-21, recorded by Opus 5.5 on 2026-11-22 at dreeves's word): 2192, whose row
           # comes from the Symmetry section's code of order 12 there.  At order 13 the residue condition mod 3 leaves the sums
           # +-(729, -729, 0), and under each no vector mod 9 is admissible (both sweeps, at once): m*(2192) = 12.  (2224, which has
           # no row, falls the same way; from 2240 to 2416 the chain (3, 9) finds a vector: scratch/next-20261120/NOTES.md.)
           2192: (13, (3, 9), 'natural')}


# PROOFS[n] = (hi, file): the upper bounds that a program of proofs/ proves with a proof of its own, at lengths outside
# the page's tables, whose bounds are citations (the block of new results).  Since 2026-11-10, when the chart came to
# reach 1456 (dreeves's README, [BOU]) and showed it open at order 12, which the two and norm lemmas allow and no chain
# of CHAINS kills within MTOP_CAP nodes, against the page's m*(1456) = 11 of 2026-11-07 (dreeves: "first get the chart
# in sync with all the known results").  columns() runs each one (proved).
# 1248 since 2026-11-11: Codex's proof that no sequence of length 1248 has order 14 (three certificates, one for each
# pair of residue profiles mod 5 that order 14 allows; checked again by Codex's review programs and by Fable 5.2's
# scratch/rec1248-20261111/check14.py), which with the product tau_1 # p624 settles m*(1248) = 13.  The norm bound for 5
# had left orders 14 and 15 open there.
PROOFS = {1248: (13, 'proofs/proof1248.py'), 1456: (11, 'proofs/proof1456.py')}


def proved(n, hi, file):
    """Runs the program file, of the repository, as the proof that no sequence of length n has order hi + 1: its
    length N and order M are those, and its check of its certificate PSI, which asserts every step, passes."""
    proof = runpy.run_path(os.path.join(HERE, file))
    assert (proof['N'], proof['M']) == (n, hi + 1), (n, hi, proof['N'], proof['M'])
    proof['check'](proof['PSI'])


# The symmetric-only proofs (2026-11-11; dreeves's README, [SYC]).  BGPW's Symmetry Conjecture: if some sequence of
# length n has exact order k, then some (-1)^k-symmetric one has (symmetric for even k, antisymmetric for odd k).  A
# kept proof of proofs/symtree.py says that no (-1)^m-symmetric sequence of length n has order m; such a sequence has
# an exact order of m's parity (BGPW's symmetry lemma), so the proof rules out the (-1)^k-symmetric sequences of exact
# order k = m, m + 2, m + 4, ....  ifsym: the name of the conditional bound here and in mstar.js, "if the Symmetry
# Conjecture holds" (Fable 5.2's, 2026-11-11, for dreeves to rename).
SYMTREE = 'proofs/symtree.py'                # the program that lists the kept symmetric-only proofs (TREES) and checks one


@lru_cache(maxsize=None)
def symtrees():
    """The cells (n, m) of the kept proofs that SYMTREE lists, each checked here by its check: no (-1)^m-symmetric
    sequence of length n has order m."""
    st = runpy.run_path(os.path.join(HERE, SYMTREE))
    return frozenset(st['check'](os.path.join(HERE, d))[:2] for d in st['TREES'])


def ifsym_of(cols, trees):
    """mstar.js's ifsym for the columns cols and the cells trees, each (n, m) a proof that no (-1)^m-symmetric sequence
    of length n has order m: [n, h, SYMTREE] for each length n of trees whose h is below its column's hi, rising in n,
    h being the least order from the column's lo up such that every exact order k from h + 1 to hi is ruled out for
    (-1)^k-symmetric sequences, so that m*(n) <= h if BGPW's Symmetry Conjecture holds.  A sequence of order lo is
    known, so proofs that rule out the (-1)^lo-symmetric sequences of exact order lo would refute the conjecture, or
    be wrong: that is no bound, and the assertion fails."""
    out = []
    for n in sorted({n for n, _ in trees}):
        lo, hi = cols[n - 1][:2]
        ruled = lambda k: any(t == n and m <= k and (k - m) % 2 == 0 for t, m in trees)
        # TODO: error copy; says the kept proofs leave no (-1)^lo-symmetric sequence of exact order lo at length n, where a sequence of order lo is known: BGPW's Symmetry Conjecture would be refuted there, or a proof is wrong
        assert not ruled(lo), f'Fable 5.2: "the Symmetry Conjecture fails at n = {n}, order {lo}, or a symmetric-only proof is wrong"'
        h = next(k for k in range(hi, lo - 1, -1) if not ruled(k))       # the largest order not ruled out: lo at the least
        out += [[n, h, SYMTREE]] * (h < hi)
    return out


def ruled_out(n, m, chain, sweep):
    """Does chain_none finish with no admissible vector at order m, within MTOP_CAP nodes?  A capped enumeration rules
    nothing out."""
    try: return chain_none(n, m, chain, sweep, MTOP_CAP)
    except Capped: return False


@lru_cache(maxsize=None)
def mtop_at(m):
    """The least n past NMAX that the chart's own upper-bound tests leave open at order m: two(n) and norm(n, p) for
    the primes of PRIMES not dividing n, then each chain of CHAINS in each sweep (ruled_out); its values at the orders
    from mtop to MMAX are mstar.js's mtopAt (open_past), the table of smallest lengths' least n not ruled out at the
    orders past the chart (dreeves's README, 2026-11-03: "[LIN] Add one more line for m=16 to the "smallest length
    known for each order" table", then "yes, 1440 instead of ">1024" if that's all we know so far. we don't need to
    spend serious effort tightening that").  A citation or a longer search could rule its n out yet, as for the
    chart's own columns."""
    n = NMAX + 2
    while (min([two(n)] + [norm(n, p) for p in PRIMES if n % p]) < m
           or any(ruled_out(n, m, chain, sweep) for sweep in SWEEPS for chain in CHAINS)):
        n += 2
    return n


def open_past(T):
    """mstar.js's mtopAt: mtop_at(m) for each order m from T, the chart's top row, to MMAX (since 2026-11-04, [M17]; T's
    alone from 2026-11-03, and again where T is past MMAX, as since 2026-11-10, [BOU]: the top row keeps its row in
    the table of smallest lengths).  Order m + 1 at n has order m there, so the list cannot fall."""
    at = [mtop_at(m) for m in range(T, max(T, MMAX) + 1)]
    assert at and at == sorted(at), at
    return at


# ---------- the columns ----------

@lru_cache(maxsize=None)
def explicit_lo():
    """lo and loWhy from explicit sequences alone, for n = 1..NMAX (index n; index 0 unused), and on to the longest
    explicit sequence (since 2026-11-19, when the lengths past the chart got rows, rows: a row of such a length is
    found as a column's is, its joins' and its products' parts from the lengths below it): the best of the examples
    at n, the products a b (a, b >= 2) and the joins a + b + a whose parts' lo have one parity, each part valued at its
    own explicit lo; the first best in that order, so an example beats a product and a product a join, the least a
    first, and ["none"] (lo 0) stays only when nothing beats it, which is exactly at odd n.  A column whose explicit lo
    a citation beats (its final lo is the citation's, with no sequence behind it) is no part of any join or product.
    So every column's sequence is (-1)^lo-symmetric, as BGPW's Symmetry Conjecture has them (since 2026-11-18; dreeves:
    "making all witnesses conforming sounds great"; until then the joins a + b, neither symmetric nor antisymmetric):
    an example's is its code's, a product of such sequences is one, of its order's parity, and a join p_a v p_b v p_a
    whose parts are of one symmetry is of it too, its order the least of theirs."""
    ex = explicit()
    orders = {key: order(a) for key, a in ex.items()}
    top = max(NMAX, *(n for n, _ in ex))
    lo, why, part = [0] * (top + 1), [['none']] * (top + 1), [False] * (top + 1)
    for n in range(1, top + 1):
        cands = ([(0, ['none'])] + [(o, ['example', label]) for (k, label), o in orders.items() if k == n]
                 + [(lo[a] + lo[n // a], ['product', a, n // a]) for a in range(2, n // 2 + 1)
                    if n % a == 0 and part[a] and part[n // a]]
                 + [(min(lo[a], lo[n - 2 * a]), ['join', a, n - 2 * a, a]) for a in range(1, (n - 1) // 2 + 1)
                    if part[a] and part[n - 2 * a] and (lo[a] - lo[n - 2 * a]) % 2 == 0])
        lo[n], why[n] = max(cands, key=lambda c: c[0])
        part[n] = all(c[0] <= lo[n] for c in CITED.get(n, []))
    return tuple(lo), tuple(map(tuple, why))


@lru_cache(maxsize=None)
def build(n):
    """The sequence behind column n's explicit lo, built from the explicit sequences by its joins and products."""
    why = explicit_lo()[1][n]
    rule = {'none': lambda: [1] * n, 'example': lambda: explicit()[n, why[1]],
            'join': lambda: reduce(join, map(build, why[1:])),
            'product': lambda: product(build(why[1]), build(why[2]))}
    return rule[why[0]]()


def row(n):
    """[lo, hi, loWhy, hiWhy] of the length n: lo the best of its explicit lo, Table 2's and the new results', hi the
    least of the upper bounds that its tests, claims, proofs and citations give, each with its reason, the first of the
    best in that order; asserting its built sequence's length and order, that the sequence is (-1)^lo-symmetric, lo <=
    hi, and the page's exact values and ranges (CITED).  A column's (columns' loop until 2026-11-19), and since then a
    length's past the chart that has an explicit sequence (rows)."""
    lo_x, why_x = explicit_lo()
    a = build(n)
    assert len(a) == n and order(a) >= lo_x[n], n
    assert all(a[-1 - i] == (-1) ** lo_x[n] * t for i, t in enumerate(a)), n      # (-1)^lo-symmetric (2026-11-18)
    cited = CITED.get(n, [])
    lo, lw = max([(lo_x[n], list(why_x[n]))] + [(v[0], ['table2']) for k, v in TABLE2.items() if k == n]
                 + [(NEW[k][0], ['page', who]) for k, who in EXAMPLE_BY.items() if k == n], key=lambda c: c[0])
    his = ([(0, ['odd'])] * (n % 2) + [(two(n), ['two'])]
           + [(residue3(n), ['residue', 3]) for _ in [0] if n % 2 == 0 and n % 3]
           + [(norm(n, p), ['norm', p]) for p in PRIMES if n % p]
           + [(m - 1, ['residue', chain[-1]]) for k, (m, chain, _) in RESIDUE.items() if k == n]
           + [(hi, ['proof', file]) for k, (hi, file) in PROOFS.items() if k == n]
           + [(prop44(n), ['prop44'])]
           + [(c[1], c[2]) for c in cited if c[1] is not None])
    hi, hw = min(his, key=lambda c: c[0])
    assert lo <= hi, (n, lo, hi, lw, hw)
    assert all(c[0] <= lo <= hi <= (hi if c[1] is None else c[1]) for c in cited), (n, cited, lo, hi)
    return [lo, hi, lw, hw]


@lru_cache(maxsize=None)
def rows():
    """{n: row(n)} for every length of the chart's data, in rising order: each column, n = 1..NMAX, then each length
    past the chart that has an explicit sequence, far (since 2026-11-19; dreeves: "yes, full anti-magic, add the new
    entries", so that each has its entry in the appendix and every p_N of a derivation links to N's entry), asserting
    along the way: every claim of RESIDUE, every proof of PROOFS, each row's own (row), brute force, that no join or
    product leans on a length whose lo is a citation or that has no row, and that EXAMPLE_BY names exactly the lengths
    whose lo is the new results'."""
    _, why_x = explicit_lo()
    for n, (m, chain, sweep) in RESIDUE.items(): assert chain_none(n, m, chain, sweep, RESIDUE_CAP), (n, m, chain)
    for n, (hi, file) in PROOFS.items(): proved(n, hi, file)
    out = {n: row(n) for n in [*range(1, NMAX + 1), *far()]}
    for n, (lo, hi, lw, hw) in out.items():
        assert lw[0] not in ('join', 'product') or all(out[k][2] == list(why_x[k]) for k in lw[1:]), n
        assert n > BRUTE_MAX or lo == hi == brute(n)[0], n
    assert {n for n, c in out.items() if c[2][0] == 'page'} == set(EXAMPLE_BY), EXAMPLE_BY
    return out


def far():
    """The lengths past the chart that have an explicit sequence, rising: 2096, 2128, 2192, 2528, 2608, 2800 and 2992
    on 2026-11-19, the Symmetry section's codes longer than NMAX."""
    return sorted({n for n, _ in explicit() if n > NMAX})


@lru_cache(maxsize=None)
def columns():
    """[lo, hi, loWhy, hiWhy] for n = 1..NMAX (index n-1): rows' columns (each found here until 2026-11-19)."""
    return tuple(rows()[n] for n in range(1, NMAX + 1))


def past():
    """mstar.js's past: [n, lo, hi, loWhy, hiWhy] for each length of far(), rising in n, its row as a column's
    (since 2026-11-19; [n, m, label] until then, m the exact order of the sequence and label its example's)."""
    return [[n, *rows()[n]] for n in far()]


# Where the examples of each label not of this page come from (2026-11-18, dreeves's point 10: every source linked):
# BGPW's Tables 4 and 5 in the paper, Thue–Morse in the OEIS, and the files of this repository that make or hold theirs.
SOURCES = {'BGPW Table 4': 'https://arxiv.org/html/1912.03491v1#S6.T4', 'BGPW Table 5': 'https://arxiv.org/html/1912.03491v1#S6.T5',
           'Thue–Morse': 'https://oeis.org/A010060',
           'pagegen/mstar.py': 'https://github.com/dreeves/equipow/blob/main/pagegen/mstar.py',
           'engine/overnight_v5.py': 'https://github.com/dreeves/equipow/blob/main/engine/overnight_v5.py'}


def source_of(n, label):
    """Where the example of the length n, labeled label, comes from: SOURCES's page for the label, or, for an example
    of this page (every other label, equipow ...), its entry in the appendix, #entry-n, which every n not of a class of
    lengths (odd, or 2 mod 4) has as its own (its code there, #n:lo, until later that night: a link to a code is the
    code's name in math, dreeves's rule of 2026-11-07)."""
    href = SOURCES.get(label, f'#entry-{n}')
    assert href in SOURCES.values() or n % 4 == 0, (n, label)
    return href


def examples_of(rows):
    """mstar.js's examples (2026-11-18): [n, code, source] for each row (n, [lo, hi, loWhy, hiWhy]) of rows, rising in
    n, whose lower bound is an example, a column's and since 2026-11-19 past's: the code of the sequence behind it
    (build), which to_hex asserts (-1)^lo-symmetric, and where it comes from."""
    return [[n, to_hex(build(n), lo), source_of(n, lw[1])] for n, (lo, _, lw, _) in rows if lw[0] == 'example']


def js_text(cols):
    """mstar.js: a comment line, then const MSTAR = {...}; with one example and one column per line."""
    T = max(c[1] for c in cols) + 1
    lines, far_rows = ',\n'.join(json.dumps(c) for c in cols), past()
    examples = ',\n'.join(json.dumps(c, ensure_ascii=False) for c in examples_of([*enumerate(cols, 1), *((n, c) for n, *c in far_rows)]))
    return ('// Generated by mstar.py from index.html and the sources it names; edit mstar.py, not this file.\n'
            f'const MSTAR = {{"nmax": {NMAX}, "mtop": {T}, "mtopAt": {json.dumps(open_past(T))}, "past": {json.dumps(far_rows)}, '
            f'"ifsym": {json.dumps(ifsym_of(cols, symtrees()))}, "examples": [\n{examples}\n], "cols": [\n{lines}\n]}};\n')


def main():
    # TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
    if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
    cols = columns()
    open(JS, 'w', encoding='utf-8').write(js_text(cols))
    settled = sum(c[0] == c[1] for c in cols)
    gray = [n for n, c in enumerate(cols, 1) if c[0] < c[1]]
    # TODO: summary line; says mstar.js was written: how many of the columns are settled (lo = hi), the gray columns, the top row, and where each order from it to MMAX is first open
    T = max(c[1] for c in cols) + 1
    print(f'Claude: "wrote mstar.js: {settled} of {NMAX} columns settled; gray: {gray}; mtop {T}, first open at {open_past(T)}"')


if __name__ == '__main__':
    main()
