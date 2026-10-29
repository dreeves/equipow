#!/usr/bin/env python3
"""Bounds on m*(2^k) for k = 1..KMAX, for the powers-of-2 chart on index.html: computes them with their reasons and
writes pow2.js beside this file.  The chart shows them as excesses over Thue-Morse.

mstar.py's docstring defines sequence, order, m*(n), lo, hi, column, join, product, size(M, r), residue sums, chain,
sweep and claim, and states the two lemmas; this file uses them in its sense, and these besides:
  excess   order - log2(length).  Thue-Morse tau_k (length 2^k, order k, Prouhet) has excess 0 at every k; a
           product's excess is the sum of its factors'.
  block    a length and an order known at that length, written [n, m]: a column n <= mstar.NMAX of mstar.js at its
           lo, an explicit sequence of mstar.py longer than that at its order (none since 2026-10-27, when NMAX
           reached 1024: from 2026-10-26, [1024, 11], index.html's p1024, was one), or tau_j as [2^j, j].  (Until
           2026-10-29 f, the 2^24 construction (320 # 320 # 112) v (432 # 48 # tau_8) of index.html's remarks, of
           order 25, was one too, with the reason f^{#L} # tau_j; no lower bound had used f since 2026-10-25.)
  atom     a block (n, lo(n)), n <= mstar.NMAX, that no single join or product of shorter columns' closure values
           reaches (closure: the best orders that joins and products of the columns reach, length by length), or a
           block of an explicit sequence longer than NMAX, which none reaches ([1024, 11] while NMAX was 1000).
  search   scratch/pow2/verify/p2v_search.py (not run here; rerun as scratch/w560/rescan.py once 560 reached order
           10), which found BASES: for an excess e and a K, is 2^K a join of products of blocks, each of order >= K +
           e?  By distributivity (a # (b v c) and (b v c) # a have the lengths and orders of (a # b) v (a # c)), any
           expression in joins and products of blocks is matched, length for length and with orders at least as high,
           by a join of products of atoms.  Such a product is a core (its atoms other than tau_1) times
           tau_1^j; its order >= K + e and length <= 2^K make the core's excess >= e; the shortest such product with a
           given core has length L 2^max(0, K + e - O) (its coin; L and O the core's length and order), and any longer
           one is 2^i times as long, the length of 2^i coins.  So 2^K is such a join exactly when it is a sum of coins
           (each any number of times), which shortest paths on residues modulo the least coin decide exactly; the
           search enumerates every core with L <= 2^K and excess >= e.

The data contract.  pow2.js is a classic script (no modules, so the page also works from file://) defining one global:
    const POW2 = {"kmax": 72, "etop": E, "cols": [[lo, hi, loWhy, hiWhy], ...]};
cols[k-1] is n = 2^k, k = 1..72.  lo and hi are orders (not excesses), integers with k <= lo <= hi < k + E: lo the
best known order at 2^k, hi the best proven upper bound.  Cell (k, e), e = 1..E, is green when k + e <= lo, gray when
lo < k + e <= hi, and red when k + e > hi; E = max over k of (hi - k) + 1, so row E is red in every column.
  loWhy  ["thue-morse"] (lo = k, tau_k); ["joins", [[[n, m], ...], ...]] (a join of products, each product a list of blocks: 2^k is the sum of the
         products' lengths, and lo the least product order).
  hiWhy  ["mstar", why] (2^k <= mstar.NMAX, so k <= 10 since 2026-10-27, k <= 9 before: mstar.js's hiWhy for n = 2^k,
         verbatim); ["norm", p] (the norm lemma for the odd
         prime p); ["residue", chain] (the claim RESIDUE[k]: mstar.py's exhaustive enumeration through the chain of
         moduli finds no admissible vector at order hi + 1).
  When reasons tie, the first of each list wins.

Run:   python3 pow2.py   (writes pow2.js)
Quals: python3 quals_pow2.py
"""
import sys
sys.dont_write_bytecode = True
# TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
import os, json
from functools import lru_cache
from math import prod
import sympy as sp
import mstar                                 # read only: the residue enumeration (chain_none), its lemmas, and the
                                             # explicit sequences longer than mstar.js's columns

KMAX = 72
NORM_PRIMES = tuple(sp.primerange(3, 32))    # the odd primes the norm lemma is tried with (weak_norm: no larger one
                                             # can do better at any 2^k, k >= 10)
HERE = os.path.dirname(os.path.abspath(__file__))
MSTAR_JS = os.path.join(HERE, 'mstar.js')
JS = os.path.join(HERE, 'pow2.js')
RESIDUE_CAP = 10 ** 8                        # nodes allowed to the enumeration of one claim
# RESIDUE[k] = (m, chain, sweep): the claims at n = 2^k, each checked by mstar.chain_none on every run.  Since
# 2026-10-12 (found by the verification of that day's update, scratch/w560/verify/upper/): at these 32 k the residue
# condition mod 3 leaves no admissible vector at m = norm(2^k, 3), the order the norm bound for 3 allows, so hi is one
# less there.
# Tried (scratch/pow2/res/) at 1024, order 11 (the norm bound for 3 allows 11): the chains (3), (3, 9), (4, 8),
# (4, 8, 16), (5), (7), (11) and (13) each have an admissible vector (mod 3 exactly +-(0, 243, -243), which is
# x^2 (x-1)^11 mod x^3 - 1); (3, 9, 27) in the sweep 'digits' passed 3 * 10^7 nodes unfinished (660654 admissible
# vectors mod 9, and each of the first 58 of them alone passed 3 * 10^5 nodes mod 27); (31) and (5, 25) passed
# 2 * 10^6 nodes unfinished.
RESIDUE = {11: (13, (3,), 'digits'), 12: (14, (3,), 'digits'), 14: (17, (3,), 'digits'), 15: (18, (3,), 'digits'),
           18: (22, (3,), 'digits'), 19: (23, (3,), 'digits'), 20: (24, (3,), 'digits'), 22: (27, (3,), 'digits'),
           23: (28, (3,), 'digits'), 26: (32, (3,), 'digits'), 30: (37, (3,), 'digits'), 31: (38, (3,), 'digits'),
           33: (41, (3,), 'digits'), 34: (42, (3,), 'digits'), 37: (46, (3,), 'digits'), 38: (47, (3,), 'digits'),
           39: (48, (3,), 'digits'), 41: (51, (3,), 'digits'), 42: (52, (3,), 'digits'), 45: (56, (3,), 'digits'),
           49: (61, (3,), 'digits'), 50: (62, (3,), 'digits'), 53: (66, (3,), 'digits'), 56: (70, (3,), 'digits'),
           57: (71, (3,), 'digits'), 58: (72, (3,), 'digits'), 60: (75, (3,), 'digits'), 61: (76, (3,), 'digits'),
           64: (80, (3,), 'digits'), 68: (85, (3,), 'digits'), 69: (86, (3,), 'digits'), 72: (90, (3,), 'digits')}
# BASES[K0]: for each excess e = 1..9, a join of products at 2^K0, each product a list of blocks, of order K0 + e, at
# the first K0 known to reach e: the docstring's search, over all of mstar.js's blocks (each with a sequence in hand),
# finds that no K below K0 reaches e = 1..7, exhaustively (scratch/record-20261025/page2/pow2/rescan_e*.out,
# 2026-10-26).  Equal products in a join are written once per binary digit of their count, times tau of that digit
# (two copies of P have the length of P # tau_1 and a lower order).  BASES[65], for e = 8, and BASES[68], for e = 9,
# are joins that a constructive variant of the search (scratch/record-20261025/page2/pow2/constructive.py) finds: no K
# <= 58 reaches e = 8, exhaustively, nor 60, and at 59 and 61..64 the search and its constructive variant are both
# undecided; no K <= 66 reaches e = 9, exhaustively (at 58 and 62..66 because no coin there has a length prime to 3,
# which a join summing to 2^K needs, 3 not dividing 2^K), and at 67 both are undecided.  No K <= 72 reaches e = 10,
# exhaustively (at 61..72 because no coin there has a length prime to 3;
# scratch/record-20261025/page2/pow2/rescan_e10.out).  At every k >= K0 the same join, each product times
# tau_(k - K0), is a candidate for lo (lifted); join_lo checks it on every run.  The examples of order 10 at 752 and
# 784 and of order 11 at 832 (2026-10-26) moved the first K0 for e = 5 from 46 to 43, for e = 6 from 49 to 48 and for
# e = 9 from 72 to 68, each new base with 832 among its blocks; the superseded bases, at 46, 49 and 72, are gone, the
# new ones lifted matching them at every k.  The example of order 11 at 1024 (later on 2026-10-26) moved the first K0
# for e = 1 from 17 to 10: BASES[10] is that block alone, which lifted matches the superseded BASES[17], (112 # 800) v
# (48 # 432 # tau_1), at every k >= 17; with that block among the others, the search
# (scratch/wish2/results/base_e*.json) moves no other first K0, and leaves the same K undecided at e = 8 and 9.  The
# example of order 11 at 816 (at the end of 2026-10-26) moved the first K0 for e = 5 from 43 to 41: BASES[41] has 816
# among its blocks, and lifted it matches the superseded BASES[43] at every k >= 43; with 816 and 1024 among the
# blocks, the search (scratch/wish2/results/wish_n816_m11.json) finds no K <= 40 reaching e = 5, exhaustively, and
# moves no other first K0.  Rerun as a baseline that night (scratch/wish3/results/base_e*.json), it finds every first
# K0 for e <= 7 again with nothing undecided below, and at e = 8 it leaves 58 undecided as well (too big, with a coin
# prime to 3), where the search over the blocks before 1024 and 816 had found no K; at e = 9 it leaves 67 and 68.
# The example of order 12 at 912 (2026-10-28) moved the first K0 for e = 3 from 30 to 29: BASES[29] has 912 among its
# blocks, and lifted it matches the superseded BASES[30], (848 # 896 # 928) v (192 # 480^2 # tau_2) v
# (112 # 480^2 # tau_2) v (192 # 480^2 # tau_1), at every k >= 30; with 912 among the blocks, the search
# (scratch/wish4/results/wish_n912_m12.json) finds no K <= 28 reaching e = 3, exhaustively, and moves no other first
# K0; at e = 8 it leaves 58 to 64 undecided, 60 among them, and at e = 9, 67.  The example of order 12 at 816
# (2026-10-28) raised BASES[41]'s product 432^3 # 816 # tau_2 from order 46 to 47; the join's order stays 46.
# With 816 at order 12 among the blocks, the search (scratch/wish5/results/wish_n816_m12.json) moves no first K0; at
# e = 8 it leaves 58 to 64 undecided, and at e = 9, 67.  The example of order 12 at 768 (that evening) moved the
# first K0 for e = 5 from 41 to 39: BASES[39] has 768 among its blocks, and lifted it matches the superseded
# BASES[41], (800^2 # 832 # 848 # tau_2) v (432^3 # 816 # tau_2) v (480^3 # 784) v (432^2 # 480^2), at every
# k >= 41; with 768 at order 12 among the blocks, the search (scratch/wish5/results/wish_n768_m12.json) finds no
# K <= 38 reaching e = 5, exhaustively, and moves no other first K0; at e = 8 it leaves 58 to 64 undecided, and at
# e = 9, 67.
# (The examples of order 10 at 592, 608 and 656 and of order 11 at 848, 880, 896, 928, 944, 976 and 992, 2026-10-25,
# had moved the first K0 for e = 2 from 27 to 20 (BASES[20] is 848 # 992 joined to 240 # 432 # tau_1), for e = 3 from
# 34 to 30, for e = 4 from 38 to 37, for e = 6 from 52 to 49 and for e = 8 from 66 to 65, and given e = 9 at 72; the
# example of order 11 at 800, 2026-10-17, had moved the first K0 for e = 1 from 18 to 17, for e = 2 from 33 to 27, for
# e = 3 from 41 to 34, for e = 4 from 48 to 38, for e = 5 from 61 to 46 and for e = 6 from 71 to 52, and given e = 7
# at 57 and e = 8 at 66; the example of order 10 at 560, 2026-10-12, had moved e = 1 from 24, where f reaches it, to
# 18, e = 3 from 49 to 41, e = 4 from 57 to 48 and e = 5 from 67 to 61, and given e = 6 at 71.)
BASES = {10: [[[1024, 11]]],
         20: [[[848, 11], [992, 11]],
              [[240, 10], [432, 11], [2, 1]]],
         29: [[[608, 10], [800, 11], [800, 11]],
              [[336, 10], [336, 10], [912, 12]],
              [[240, 10], [432, 11], [432, 11]]],
         37: [[[208, 8], [800, 11], [800, 11], [848, 11]],
              [[192, 9], [192, 9], [432, 11], [432, 11], [2, 1]],
              [[48, 6], [480, 12], [480, 12], [976, 11]]],
         39: [[[800, 11], [832, 11], [832, 11], [832, 11]],
              [[192, 9], [432, 11], [432, 11], [768, 12], [2, 1]],
              [[48, 6], [480, 12], [480, 12], [768, 12], [4, 2]]],
         48: [[[560, 10], [800, 11], [800, 11], [800, 11], [832, 11]],
              [[336, 10], [336, 10], [432, 11], [432, 11], [432, 11], [2, 1]],
              [[48, 6], [480, 12], [480, 12], [480, 12], [928, 11], [2, 1]],
              [[240, 10], [336, 10], [432, 11], [432, 11], [480, 12]],
              [[48, 6], [480, 12], [480, 12], [480, 12], [480, 12], [2, 1]],
              [[48, 6], [480, 12], [480, 12], [480, 12], [480, 12]]],
         57: [[[352, 9], [800, 11], [800, 11], [800, 11], [800, 11], [800, 11]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [512, 9]],
              [[432, 11], [432, 11], [432, 11], [432, 11], [432, 11], [496, 9]],
              [[144, 8], [368, 9], [432, 11], [480, 12], [480, 12], [480, 12]],
              [[240, 10], [240, 10], [432, 11], [432, 11], [432, 11], [432, 11]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [64, 6]],
              [[240, 10], [240, 10], [240, 10], [432, 11], [432, 11], [480, 12]],
              [[48, 6], [336, 10], [480, 12], [480, 12], [480, 12], [480, 12]]],
         65: [[[112, 7], [800, 11], [800, 11], [800, 11], [800, 11], [800, 11], [928, 11]],
              [[480, 12], [480, 12], [480, 12], [848, 11], [896, 11], [896, 11], [16, 4]],
              [[192, 9], [336, 10], [336, 10], [432, 11], [432, 11], [432, 11], [432, 11]],
              [[48, 6], [432, 11], [432, 11], [432, 11], [480, 12], [480, 12], [592, 10]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [16, 4]],
              [[432, 11], [432, 11], [480, 12], [480, 12], [480, 12], [480, 12], [8, 3]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [4, 2]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [2, 1]]],
         68: [[[800, 11], [800, 11], [800, 11], [800, 11], [800, 11], [800, 11], [832, 11]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [2048, 11]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [1024, 10]],
              [[208, 8], [480, 12], [480, 12], [480, 12], [800, 11], [800, 11], [832, 11]],
              [[192, 9], [432, 11], [432, 11], [432, 11], [432, 11], [432, 11], [896, 11], [4, 2]],
              [[192, 9], [192, 9], [432, 11], [432, 11], [432, 11], [432, 11], [480, 12], [8, 3]],
              [[192, 9], [336, 10], [336, 10], [432, 11], [432, 11], [480, 12], [480, 12], [4, 2]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [256, 8]],
              [[192, 9], [192, 9], [480, 12], [480, 12], [480, 12], [480, 12], [896, 11]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [128, 7]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [64, 6]],
              [[12, 3], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [4, 2]],
              [[480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [480, 12], [32, 5]]]}


# ---------- mstar.js ----------

@lru_cache(maxsize=None)
def mstar_text():
    """mstar.js's text: one comment line, then const MSTAR = {...}; with JSON for the object."""
    return open(MSTAR_JS, encoding='utf-8').read()


def mstar_cols():
    """mstar.js's columns, cols[n-1] for n = 1..mstar.NMAX, parsed from its text."""
    head, body = mstar_text().split('const MSTAR = ')
    assert head.startswith('//') and head.count('\n') == 1 and body.endswith('};\n') and body.count(';') == 1, head
    M = json.loads(body[:-2])
    assert M['nmax'] == mstar.NMAX == len(M['cols']), M['nmax']
    return M['cols']


@lru_cache(maxsize=None)
def blocks():
    """Every block as (n, m): mstar.js's columns at their lo, mstar.explicit()'s sequences longer than mstar.NMAX at
    their orders (explicit() asserts each one's), and tau_j for j = 0..KMAX."""
    return frozenset([(n, c[0]) for n, c in enumerate(mstar_cols(), 1)]
                     + [(n, mstar.order(a)) for (n, _), a in mstar.explicit().items() if n > mstar.NMAX]
                     + [(2 ** j, j) for j in range(KMAX + 1)])


# ---------- lower bounds ----------

def join_lo(k, products):
    """The order of a join of products at 2^k: asserts that every factor is a block and that the products' lengths
    sum to 2^k exactly; returns the least product order (BGPW's Theorem 4.1)."""
    assert len(products) >= 1 and all(len(p) >= 1 for p in products), products
    assert all(len(b) == 2 and tuple(b) in blocks() for p in products for b in p), products
    assert sum(prod(n for n, _ in p) for p in products) == 2 ** k, (k, products)
    return min(sum(m for _, m in p) for p in products)


def lifted(products, j):
    """A join of products with each product times tau_j, the tau factors of each merged into one (tau_a # tau_b =
    tau_(a+b): lengths 2^a 2^b, orders a + b) and tau_0, of length 1, left out."""
    out = []
    for p in products:
        t = j + sum(m for n, m in p if n == 2 ** m)
        out.append([b for b in p if b[0] != 2 ** b[1]] + [[2 ** t, t]] * (t > 0))
    return out


LO_RULES = {'thue-morse': lambda k: [[[2 ** k, k]]], 'joins': lambda k, ps: ps}


def lo_of(k, why):
    assert why[0] in LO_RULES, why
    return join_lo(k, LO_RULES[why[0]](k, *why[1:]))


# ---------- upper bounds ----------

def norm(n, p):
    """mstar.norm, with each class size computed as ceil((n - r) / p), since mstar.norm's len(range(r, n, p))
    overflows past 2^63: the largest m >= 0 with p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1)."""
    assert sp.isprime(p) and n % p, (n, p)
    rhs = (p * sum(((n - r + p - 1) // p) ** 2 for r in range(p))) ** (p - 1)
    m = 0
    while p ** (2 * m + 2) * (p - 1) ** (p - 1) <= rhs: m += 1
    return m


def weak_norm(k):
    """A lower bound on norm(2^k, p) for every prime p >= 37: the largest m with 37^(2m) <= (2^k)^36.  Lemma: for any
    odd prime p and n >= 1, norm(n, p) >= the largest m with p^(2m) <= n^(p-1).  If p - 1 <= n: sum_r size(p, r)^2 >=
    n^2 / p (Cauchy-Schwarz), so the right side is >= n^(2(p-1)) >= p^(2m) n^(p-1) >= p^(2m) (p-1)^(p-1).  If p > n:
    every class holds at most one position, sum_r size(p, r)^2 = n, and (pn)^(p-1) > n^(p-1) (p-1)^(p-1) >=
    p^(2m) (p-1)^(p-1).  And that m is floor((p-1) ln n / (2 ln p)), which does not decrease as p grows ((p-1) / ln p
    increases for p >= 2), so p = 37 gives the least."""
    m = 0
    while 37 ** (2 * m + 2) <= 2 ** (36 * k): m += 1
    return m


def mstar_hi(k, why):
    """mstar.js's hi at 2^k <= mstar.NMAX, whose hiWhy must be why."""
    assert 2 ** k <= mstar.NMAX and mstar_cols()[2 ** k - 1][3] == why, (k, why)
    return mstar_cols()[2 ** k - 1][1]


@lru_cache(maxsize=None)
def residue_hi(k, chain):
    """hi from the claim RESIDUE[k], whose chain must be chain: asserts that the enumeration finds no admissible
    vector, and returns its order minus 1."""
    assert k in RESIDUE, k
    m, ch, sweep = RESIDUE[k]
    assert ch == chain and mstar.chain_none(2 ** k, m, chain, sweep, RESIDUE_CAP), (k, m, chain)
    return m - 1


HI_RULES = {'mstar': mstar_hi, 'norm': lambda k, p: norm(2 ** k, p), 'residue': lambda k, chain: residue_hi(k, tuple(chain))}


def hi_of(k, why): return HI_RULES[why[0]](k, *why[1:])


# ---------- the columns ----------

@lru_cache(maxsize=None)
def columns():
    """[lo, hi, loWhy, hiWhy] for k = 1..KMAX (index k-1): lo the best of Thue-Morse and BASES lifted; hi the least of
    mstar.js's column 2^k (2^k <= mstar.NMAX), the norm lemma for each of NORM_PRIMES and the claim RESIDUE[k].
    Asserts k <= lo <= hi, that no prime beyond NORM_PRIMES gives a lower norm bound, lo =
    hi = k for k <= 9, and lo and hi equal to mstar.js's wherever 2^k is one of its columns."""
    out = []
    for k in range(1, KMAX + 1):
        los = [['thue-morse']] + [['joins', lifted(ps, k - K0)] for K0, ps in BASES.items() if K0 <= k]
        his = ([['mstar', c[3]] for n, c in enumerate(mstar_cols(), 1) if n == 2 ** k] + [['norm', p] for p in NORM_PRIMES]
               + [['residue', list(ch)] for q, (_, ch, _) in RESIDUE.items() if q == k])
        lw, hw = max(los, key=lambda w: lo_of(k, w)), min(his, key=lambda w: hi_of(k, w))
        lo, hi = lo_of(k, lw), hi_of(k, hw)
        assert k <= lo <= hi < weak_norm(k), (k, lo, hi, lw, hw)
        out.append([lo, hi, lw, hw])
    for k in range(1, 10): assert out[k - 1][:2] == [k, k], k
    for k in range(1, mstar.NMAX.bit_length()): assert out[k - 1][:2] == mstar_cols()[2 ** k - 1][:2], k   # 2^k <= NMAX
    return out


def js_text(cols):
    """pow2.js: a comment line, then const POW2 = {...}; with one column per line."""
    E = max(c[1] - k for k, c in enumerate(cols, 1)) + 1
    rows = ',\n'.join(json.dumps(c) for c in cols)
    return ('// Generated by pow2.py from mstar.js and the constructions and claims it names; edit pow2.py, not this '
            f'file.\nconst POW2 = {{"kmax": {KMAX}, "etop": {E}, "cols": [\n{rows}\n]}};\n')


def main():
    cols = columns()
    open(JS, 'w', encoding='utf-8').write(js_text(cols))
    better = [k for k, c in enumerate(cols, 1) if c[2][0] == 'joins' or c[3][0] == 'residue']
    # TODO: summary line; says pow2.js was written, its top row, and the columns whose lo is a join or whose hi a residue claim
    print(f'Claude: "wrote pow2.js: etop {max(c[1] - k for k, c in enumerate(cols, 1)) + 1}; joins or residue at k = {better}"')


if __name__ == '__main__':
    main()
