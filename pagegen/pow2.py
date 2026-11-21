#!/usr/bin/env python3
"""Bounds on m*(2^k) for k = 1..KMAX, for the powers-of-2 chart on index.html: computes them with their reasons and
writes pagedata/pow2.js (this file is in pagegen/ and the data file in pagedata/ since 2026-11-10).  The chart shows them as excesses over Thue-Morse.

mstar.py's docstring defines sequence, order, m*(n), lo, hi, column, join, product, size(M, r), residue sums, chain,
sweep and claim, and states the two lemmas; this file uses them in its sense, and these besides:
  excess   order - log2(length).  Thue-Morse tau_k (length 2^k, order k, Prouhet) has excess 0 at every k; a
           product's excess is the sum of its factors'.
  block    a length and an order known at that length, written [n, m]: a column n <= mstar.NMAX of mstar.js at its
           lo, an explicit sequence of mstar.py longer than that at its order (none from 2026-10-27, when NMAX
           reached 1024: from 2026-10-26, [1024, 11], index.html's p1024, was one; since 2026-11-11 the Symmetry
           section's sequences of order 12 at 2096, 2128 and 2192), or tau_j as [2^j, j].  (Until
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
  hiWhy  ["mstar", why] (2^k <= mstar.NMAX, so k <= 11 since 2026-11-10, when the m*(n) chart came to reach 2048, k <= 10
         from 2026-10-27, k <= 9 before: mstar.js's hiWhy for n = 2^k,
         verbatim); ["residue", [3]] (the residue condition mod 3 in closed form, mstar.residue3, which has no
         admissible residue sums at order hi + 1: since 2026-11-16 the reason of every column past the m*(n) chart,
         as it comes before the norm bound, which it implies; until then ["residue", chain] was a claim RESIDUE[k],
         run through mstar.py's enumeration, at the 32 k where it gave less than the norm bound); ["norm", p] (the
         norm lemma for the odd prime p).
  When reasons tie, the first of each list wins.

Run:   python3 -B pagegen/pow2.py   (writes pagedata/pow2.js)
Quals: python3 -B quals/quals_pow2.py
"""
import sys
sys.dont_write_bytecode = True
# TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
import os, json
from functools import lru_cache
from math import prod
import sympy as sp
import mstar                                 # read only: the residue condition mod 3 (residue3), its lemmas, and the
                                             # explicit sequences longer than mstar.js's columns

KMAX = 72
NORM_PRIMES = tuple(sp.primerange(3, 32))    # the odd primes the norm lemma is tried with (weak_norm: no larger one
                                             # can do better at any 2^k, k >= 10)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above pagegen/ (this file was at the root until 2026-11-10, dreeves's README [REF])
MSTAR_JS = os.path.join(HERE, 'pagedata', 'mstar.js')   # the page's data files are in pagedata/ since 2026-11-10 ([REF])
JS = os.path.join(HERE, 'pagedata', 'pow2.js')
# The residue condition mod 3 at n = 2^k is mstar.residue3's closed form since 2026-11-16 (dreeves, of Stan Wagon's
# "standard mod-3 argument" for m*(1024) <= 11: "ok, go ahead with breaking ties in favor of the mod-3 argument"), and
# it comes before the norm bound, as in mstar.py.  Until then RESIDUE[k] = (m, chain, sweep) held 32 claims of the
# chain (3), each run through mstar.chain_none (found by the verification of 2026-10-12's update,
# scratch/w560/verify/upper/): at k = 11, 12, 14, 15, 18, 19, 20, 22, 23, 26, 30, 31, 33, 34, 37, 38, 39, 41, 42, 45,
# 49, 50, 53, 56, 57, 58, 60, 61, 64, 68, 69 and 72 the condition leaves no admissible vector at m = norm(2^k, 3), the
# order the norm bound for 3 allows, so hi is one less there; at every other k it gives the norm bound's own value.
# quals_pow2's q_residue_condition_mod_3_matches_the_enumeration still enumerates each column.
# Tried (scratch/pow2/res/) at 1024, order 11 (the norm bound for 3 allows 11): the chains (3), (3, 9), (4, 8),
# (4, 8, 16), (5), (7), (11) and (13) each have an admissible vector (mod 3 exactly +-(0, 243, -243), which is
# x^2 (x-1)^11 mod x^3 - 1); (3, 9, 27) in the sweep 'digits' passed 3 * 10^7 nodes unfinished (660654 admissible
# vectors mod 9, and each of the first 58 of them alone passed 3 * 10^5 nodes mod 27); (31) and (5, 25) passed
# 2 * 10^6 nodes unfinished.
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
# e = 9, 67.  The examples of 2026-11-03 (order 10 at 544, 12 at 576 and 624, 13 at 912 and 1008, 15 at 960; searches/pinned/) moved the first K0 for e = 3 from 29
# to 28, for e = 4 from 37 to 36 and for e = 6 from 48 to 47: BASES[28], BASES[36] and BASES[47], which lifted match the superseded BASES[29], BASES[37] and
# BASES[48] at every k above them.  searches/pinned/coins, this search over those blocks, those of excess below -0.2 left out for speed, finds no K <= 27 reaching e
# = 3, no K <= 35 reaching e = 4, no K <= 46 reaching e = 6 and no K <= 55 reaching e = 7; K = 56 at e = 7 and 58, 60 and 62 at e = 8 were not decided in 15 minutes
# each; at e = 8 it finds nothing at K = 56, and at e = 9, tried only at K = 61 and 64, nothing there.  Later that day the
# docstring's search over all of mstar.js's blocks (scratch/w11-624-576/firsts_now.py through scratch/wish5/wish5.py;
# firsts_now_afterpinned.json there) moved the first K0 for e = 7 from 57 to 56 and for e = 8 from 65 to 58: BASES[56] and
# BASES[58], which lifted match the superseded BASES[57] and BASES[65] at every k above them.  wish5 adds 1008 at order 12;
# rerun with 1008 at its order 13 (scratch/firsts-56-58/firsts.json), the search finds the first K0 of each e <= 8 again,
# no K below it reaching e, and no K <= 67 reaching e = 9, exhaustively, with nothing undecided; at e = 10 no K <= 72 has a
# coin whose odd part is prime to 3, and 1008, a multiple of 3, adds none.  Each new base has four products, the fewest
# that joins of products of the search's atoms allow at its K (scratch/firsts-56-58/fewer.py: none of three), and keeps two
# products of the search's witness (scratch/firsts-56-58/NOTES.md).
# The sequences of 2026-11-11 (of order 12 at 1504, 14 at 1488 and 15 at 1632, the tilted search's, in the page's
# Symmetry section) moved the first K0 for e = 4 from 36 to 30: BASES[30], which lifted matches the superseded
# BASES[36], (960^2 # 480 # tau_2) v (960^2 # 480) v (912 # 576 # 816 # tau_3) v (800^2 # 880 # 112), at every
# k >= 36.  searches/pinned/coins over the 57 atoms of 2026-11-06 and the example columns past 1024
# (scratch/q1920-20261111/firsts/) finds no K <= 29 reaching e = 4, and the firsts of e = 1, 2, 3, 5 and 6 again.
# An exact check written apart from it (k29.py there: every column of mstar.js a block, the coins by a walk over
# products, then one subset sum) agrees: 2^29 is no join of products of order 33 or more, 2^30 is one of order 34,
# and its controls give the firsts of e = 1, 2 and 3.  Below 2^29 no product of blocks prime to 3 has the ratio
# order / log2(length) that e = 4 needs (the best is 800's, 11 / log2 800), and a join summing to 2^K needs such a
# product.  BASES[30] has three products, the fewest that joins of products of the page's example columns allow at
# 2^30 (base30.py there: none of two, three of three), and keeps two products of coins' witness.
# Later that day the same search, with the day's sequences of order 12 at 1504, 1520 and 1808 and of order 15 at
# 1728, moved the first K0 for e = 7 from 56 to 51: BASES[51], which lifted gives 2^56 and 2^57 the orders that the
# superseded BASES[56] gave them, (832 # 800^4 # 208) v (992 # 960^2 # 832 # 800) v (912^2 # 672 # 576^2 # tau_1) v
# (960^2 # 848 # 576 # 432) and its lift.  coins found a join at 2^51 (17 equal products and four more).  An exact
# check written apart from it (decide.py there) splits a sum of coins equal to 2^K into its coins prime to 3, of
# which there is at least one since 2^K is prime to 3 and every other coin a multiple of 3, and the rest.  For e = 7
# no product of blocks prime to 3 has order K + 7 within 2^K at any K <= 50: none at K <= 49 by the ratio alone (the
# best is 800's, 11 / log2 800 = 1.14062 < 56/49), none at K = 50 by its walk over all 677 such blocks of the chart
# (1024 at its order 11 and 2048 at 12 among them, and the walk's cuts decided in integers: Codex's review of that
# day, whose own integer-only checks agree at 2^50 and 2^51 and on the fewest products).
# So 51 is the first.  The same check keeps the firsts of e = 4, 5, 6 and 8 with that day's blocks (2^29: the one
# rest that is a multiple of 3 is no sum of coins; K = 36 to 38, 43 to 46, 56 and 57: no product prime to 3).
# BASES[51] has three products, the fewest that joins of products of the page's example columns allow at 2^51
# (fewest.py and decide.py there: none of two, one of three).
# The antisymmetric sequences of order 13 at 2528, 2608, 2800 and 2992, past the chart (the tilted search's of 2026-11-11, in
# the Symmetry section since 2026-11-19), moved the first K0 for e = 3, 5, 6, 7, 8 and 9 from 28, 39, 47, 51, 58 and 68 to 22, 35, 42, 50, 55 and 63 and gave e = 10 its first,
# 68: BASES[22], [35], [42], [50], [55], [63], [68],
# which lifted match the superseded BASES[28], [39], [47], [51], [58], [68] at every k above them.  2^K is not a multiple of 3, so a
# join that sums to it has a product whose blocks are all prime to 3, and 13 / log2 2528 = 1.150 is more than any of the chart's
# lengths prime to 3 allows, 800's 11 / log2 800 = 1.141 being the best.  quals_pow2.excess_reached, over the chart's blocks and
# those four, says no at the power of 2 just below each new first (scratch/rethink-20261119/firsts/fast2.py and heads.py).  The
# joins at 2^22, 2^35 and 2^42 have the fewest products over the page's example columns and the four (decomp.py there), those at
# 2^50 and 2^55 are one sum read back from the exact decider's bit set (witness.py), fewer products not sought, and those at 2^63
# and 2^68 are Astra's (scratch/codex-omg-20261119/verify_joins.py).  The sequence at 2^22,
# built in full, has order 25 by its power sums (build22.py).
# Two more of that kind, at 2480 and 2512 (the tilted search's of 2026-11-21, in the Symmetry section since), moved the first K0 for
# e = 5 from 35 to 34: BASES[34], which lifted matches the superseded BASES[35] (2608 2528^2 2 + 768 672^2 2 + 1440 960 240) at every k
# above it.  quals_pow2.excess_reached says no at 2^33 (no coin prime to 3 fits); the join is witness5.py's in
# scratch/next-20261120/firsts, one sum read back from the exact decider's bit set, fewer products not sought.
# And the one at 2480 moved the first for e = 10 from 68 to 67: BASES[67], which lifted matches the superseded BASES[68] (Astra's
# 2608^2 2528^4 + 2608^2 960^2 832^2 + 1648 1632 1568^2 1504 960 + 2016 1728 1632 848^3) at every k above it.  No coin prime to 3
# fits at 2^66.  The join is the one that Astra's search for joins of few products (scratch/codex-omg-20261119/e10short.py, run as
# firsts/e10short_b.py 67 40 3 10 there with the two new blocks) found, its 1920 and 864 written as 960 2 and 432 2.
# Later on 2026-11-21: an antisymmetric sequence of order 15 at 8192 = 2^13 (the tilted search's, W 340; m*(2^13) = 15 by the residue
# condition mod 3) and one of order 13 at 2432, both in the Symmetry section.  With them the firsts K0 for e = 2, 4, 6, 7, 8, 9, 10 are
# 13, 26, 39, 47, 52, 60, 65 (20, 30, 42, 50, 55, 63, 67 until then): BASES[13], [26], [39], [52] and [65] are the powers of the
# sequence at 2^13; [47] and [60] were found by Astra's search for joins of few products (scratch/next-20261120/firsts/
# e10short_d.py 47 40 3 7 and 60 40 3 9), 1536 written as 768 2.  Below each: no coin prime to 3, or none whose rest is a multiple
# of 3 (heads.py there); 2^21 for e = 3 stays a no (layers.py).  The superseded BASES[20], [30], [42], [50], [55], [63], [67] are
# matched or beaten at every k by the lifts of these.
# That morning (2026-11-21): an antisymmetric sequence of order 15 at 7936 (the tilted search's, W 340), with the best ratio of a length
# prime to 3, 15 / log2 7936 = 1.158, gave e = 11 its first, K0 = 71: BASES[71], found by Astra's search for joins of few products
# (scratch/next-20261120/firsts/e10short_e.py 71 40 3 11; its 1536 written 768 2).  No coin prime to 3 fits at 2^70.
# Later that morning (2026-11-21): the antisymmetric sequence of order 15 at 7712 (the tilted search's; in the Symmetry section) moved
# the first K0 for e = 9 from 60 to 59 and e = 10 from 65 to 63: BASES[59] (scratch/next-20261120/firsts/e10short_f.py 59 40 3 9, its 1248 written 624 2) and BASES[63] (scratch/next-20261120/firsts/e10short_f.py 63 40 3 10, its 1920 written 960 2),
# found by Astra's search for joins of few products.  2^58 is an exact no (layers.py: 4 rests) and no coin prime to 3 fits at 2^57 or at 2^62.  The superseded BASES[60] and BASES[65] are matched or beaten at every k by the lifts of these.
# At 08:02 (2026-11-21): the antisymmetric sequences of order 13 at 2368 and of order 15 at 7744 (the tilted search's; in the Symmetry section) moved
# the first K0 for e = 7 from 47 to 45, e = 8 from 52 to 50, e = 9 from 59 to 58 and e = 11 from 71 to 69:
# BASES[45] (e10short_g.py 45 40 3 7, its 1248 written 624 2 and its 1920 as 960 2), BASES[50] (e10short_g.py 50 40 3 8, its 1536 written 768 2 and its 1920 as 960 2), BASES[58] (e10short_g.py 58 40 3 9, likewise) and BASES[69] (e10short_g.py 69 40 3 11, likewise),
# found by Astra's search for joins of few products (scratch/next-20261120/firsts).  Below them no coin prime to 3 fits (2^44, 2^49, 2^57, 2^68); (3, 21) and (5, 33) have heads and are exact noes (layers.py), and excess 12 has no coin prime to 3 up to 2^72.
# The superseded BASES[47], BASES[52], BASES[59] and BASES[71] are matched or beaten at every k by the lifts of these.
# (The examples of order 10 at 592, 608 and 656 and of order 11 at 848, 880, 896, 928, 944, 976 and 992, 2026-10-25,
# had moved the first K0 for e = 2 from 27 to 20 (BASES[20] is 848 # 992 joined to 240 # 432 # tau_1), for e = 3 from
# 34 to 30, for e = 4 from 38 to 37, for e = 6 from 52 to 49 and for e = 8 from 66 to 65, and given e = 9 at 72; the
# example of order 11 at 800, 2026-10-17, had moved the first K0 for e = 1 from 18 to 17, for e = 2 from 33 to 27, for
# e = 3 from 41 to 34, for e = 4 from 48 to 38, for e = 5 from 61 to 46 and for e = 6 from 71 to 52, and given e = 7
# at 57 and e = 8 at 66; the example of order 10 at 560, 2026-10-12, had moved e = 1 from 24, where f reaches it, to
# 18, e = 3 from 49 to 41, e = 4 from 57 to 48 and e = 5 from 67 to 61, and given e = 6 at 71.)
BASES = {10: [[[1024, 11]]],
         13: [[[8192, 15]]],
         22: [[[2528, 13], [1568, 12]],
              [[960, 15], [240, 10]]],
         26: [[[8192, 15], [8192, 15]]],
         34: [[[2512, 13], [2480, 13], [2480, 13]],
              [[1968, 14], [1296, 14], [528, 11]],
              [[960, 15], [960, 15], [208, 8], [2, 1]]],
         39: [[[8192, 15], [8192, 15], [8192, 15]]],
         45: [[[2528, 13], [2368, 13], [2368, 13], [2368, 13]],
              [[1728, 15], [1632, 15], [624, 12], [192, 9], [2, 1]],
              [[960, 15], [960, 15], [800, 11], [800, 11]],
              [[1488, 14], [960, 15], [960, 15], [256, 8]]],
         50: [[[7744, 15], [7712, 15], [7712, 15], [2368, 13]],
              [[7712, 15], [2368, 13], [960, 15], [960, 15]],
              [[2016, 15], [1632, 15], [1584, 14], [768, 13], [4, 2]],
              [[1440, 16], [960, 15], [960, 15], [912, 13], [2, 1]]],
         58: [[[7744, 15], [2368, 13], [2368, 13], [2368, 13], [2368, 13]],
              [[2432, 13], [2368, 13], [2368, 13], [2368, 13], [960, 15]],
              [[1776, 14], [1632, 15], [1504, 12], [960, 15], [768, 13], [4, 2]],
              [[7744, 15], [960, 15], [960, 15], [960, 15], [128, 7]]],
         63: [[[7712, 15], [7712, 15], [7712, 15], [7712, 15], [2528, 13]],
              [[7712, 15], [7712, 15], [2432, 13], [960, 15], [960, 15]],
              [[1440, 16], [1008, 13], [912, 13], [912, 13], [336, 10], [240, 10]],
              [[7936, 15], [2480, 13], [1392, 14], [960, 15], [960, 15], [2, 1]]],
         69: [[[7712, 15], [2368, 13], [2368, 13], [2368, 13], [2368, 13], [2368, 13]],
              [[2432, 13], [2368, 13], [2368, 13], [960, 15], [960, 15], [800, 11]],
              [[1968, 14], [1632, 15], [1392, 14], [1056, 13], [768, 13], [768, 13], [2, 1]],
              [[2096, 12], [960, 15], [960, 15], [960, 15], [960, 15], [256, 8]]]}


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


def residue_hi(k, chain):
    """hi from the residue condition of the chain, which must be the single modulus 3: mstar.residue3 at 2^k, the
    closed form (since 2026-11-16; a claim of RESIDUE, enumerated, until then)."""
    assert chain == [3], (k, chain)
    return mstar.residue3(2 ** k)


HI_RULES = {'mstar': mstar_hi, 'residue': residue_hi, 'norm': lambda k, p: norm(2 ** k, p)}


def hi_of(k, why): return HI_RULES[why[0]](k, *why[1:])


# ---------- the columns ----------

@lru_cache(maxsize=None)
def columns():
    """[lo, hi, loWhy, hiWhy] for k = 1..KMAX (index k-1): lo the best of Thue-Morse and BASES lifted; hi the least of
    mstar.js's column 2^k (2^k <= mstar.NMAX), the residue condition mod 3 (mstar.residue3) and the norm lemma for
    each of NORM_PRIMES, the first of them in that order.
    Asserts k <= lo <= hi, that no prime beyond NORM_PRIMES gives a lower norm bound, lo =
    hi = k for k <= 9, and lo and hi equal to mstar.js's wherever 2^k is one of its columns."""
    out = []
    for k in range(1, KMAX + 1):
        los = [['thue-morse']] + [['joins', lifted(ps, k - K0)] for K0, ps in BASES.items() if K0 <= k]
        his = ([['mstar', c[3]] for n, c in enumerate(mstar_cols(), 1) if n == 2 ** k] + [['residue', [3]]]
               + [['norm', p] for p in NORM_PRIMES])
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
    better = [k for k, c in enumerate(cols, 1) if c[2][0] == 'joins' or c[1] < norm(2 ** k, 3)]
    # TODO: summary line; says pow2.js was written, its top row, and the columns whose lo is a join or whose hi is below the norm bound for 3
    print(f'Claude: "wrote pow2.js: etop {max(c[1] - k for k, c in enumerate(cols, 1)) + 1}; joins or below the norm bound for 3 at k = {better}"')


if __name__ == '__main__':
    main()
