#!/usr/bin/env python3
"""Bounds on m*(n) for every n = 1..NMAX, for the chart on index.html: computes them with their reasons and writes
mstar.js beside this file.

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
    const MSTAR = {"nmax": 1000, "mtop": T, "cols": [[lo, hi, loWhy, hiWhy], ...]};
cols[n-1] is column n.  0 <= lo <= hi < T = max hi + 1.  Cell (n, m), m = 1..T, is green when m <= lo, gray when
lo < m <= hi, and red when m > hi; row T is red in every column.
  loWhy  ["none"] (lo = 0, n odd); ["example", label] (an explicit sequence of length n, label saying where it is
         from); ["join", a, b] (the sequence for a, then the one for b; lo is the lesser of theirs); ["product", a, b]
         (f_a(x) f_b(x^a); lo is the sum of theirs); ["table2"] (BGPW's Table 2, cited); ["page", who] (the page's new
         results, cited; who found the example, as the page's remarks credit it: EXAMPLE_BY).  Every example, join and
         product is a sequence built here from explicit sequences only and checked with exact power sums; a join's or
         product's parts are themselves columns with such reasons.
  hiWhy  ["odd"] (n odd: hi = 0); ["two"]; ["norm", p]; ["residue", M] (the claim in RESIDUE: no admissible vector mod
         M at order hi + 1); ["table2"]; ["page", who] (who proved it: that cell's title).
  When sources tie, a reason checked here wins over a citation, and the simpler one among those: example, join,
  product; odd, two, norm (the least p), residue.

Run:   python3 mstar.py   (writes mstar.js)
Quals: python3 quals_mstar.py
"""
import sys
sys.dont_write_bytecode = True
import os, re, json
from functools import lru_cache
from operator import mul
import numpy as np
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form
import overnight_v5 as v5                    # read only: EXAMPLES and from_hex

NMAX = 1000
BRUTE_MAX = 32                               # brute force decides m*(n) for n up to this
PRIMES = tuple(sp.primerange(2, 32))         # the norm lemma's primes (the least prime not dividing a given n <= 1000
                                             # is at most 11)
RESIDUE_CAP = 10 ** 7                        # nodes allowed to the enumeration of one claim (the largest, 624 mod 25,
                                             # takes about 670000)
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, 'index.html')
JS = os.path.join(HERE, 'mstar.js')


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


def from_set(S, n):
    """The sequence of length n that is +1 exactly on the set S of positions 0..n-1."""
    assert S <= set(range(n)), n
    return [1 if i in S else -1 for i in range(n)]


# ---------- citations and sequences on index.html ----------
# Hand copies of the page, which page_sources() must match exactly: TABLE2[n] = (lo, hi) for BGPW's Table 2, hi None
# for "≥"; NEW[n] = (lo, hi, who) for the new results, who the cell's title.
TABLE2 = {8: (3, 3), 16: (4, 4), 24: (4, 4), 32: (5, 5), 40: (5, 5), 48: (6, 6), 56: (5, 5), 64: (6, 6), 72: (6, 6),
          80: (6, 6), 88: (6, 6), 96: (7, 7), 104: (6, 6), 112: (7, 7), 120: (6, 6), 128: (7, 7),
          136: (6, 6), 144: (8, 8), 152: (6, 6), 160: (7, 7), 168: (6, 6), 176: (7, 7), 184: (6, 6), 192: (9, 9),
          200: (7, 7), 208: (8, 8), 216: (7, 7), 224: (8, 8), 232: (7, 7),
          240: (10, 11), 248: (7, 7), 256: (8, 8), 264: (7, 7), 272: (8, 8), 280: (7, 7), 288: (9, 10), 296: (7, 7),
          304: (8, 9), 2 ** 51: (52, None)}
NEW = {304: (8, 8, 'Claude alone'), 320: (9, 9, 'BGPW'), 336: (10, 10, 'Claude and BGPW'), 352: (9, 9, 'BGPW'),
       368: (9, 9, 'BGPW'), 400: (9, 9, 'BGPW'), 416: (9, 9, 'BGPW'), 432: (11, 12, 'Claude alone'),
       448: (9, 9, 'Claude alone'), 464: (9, 9, 'BGPW'), 480: (12, 14, 'Claude alone'),
       496: (9, 9, 'Claude and BGPW'), 512: (9, 9, 'Claude alone'), 528: (10, 12, 'Claude and BGPW'),
       576: (10, 12, 'Claude alone'),
       384: (10, 11, 'Claude alone'),
       544: (9, 10, 'Claude alone'),
       560: (9, 10, 'Claude alone'),
       592: (9, 10, 'Claude alone'),
       608: (9, 10, 'Claude alone'),
       624: (10, 12, 'Claude alone'),
       640: (10, 10, 'Claude alone'),
       656: (9, 10, 'Claude alone'),
       672: (11, 13, 'Claude alone'),
       688: (9, 10, 'Claude alone'),
       704: (10, 10, 'Claude alone'),
       720: (10, 14, 'Claude alone'),
       736: (10, 10, 'Claude alone'),
       752: (9, 11, 'Claude alone'),
       768: (11, 13, 'Claude alone'),
       784: (9, 10, 'Claude alone'),
       800: (10, 11, 'Claude alone'),
       816: (10, 14, 'Claude alone'),
       832: (10, 11, 'Claude alone'),
       848: (9, 11, 'Claude alone'),
       864: (12, 14, 'Claude alone'),
       880: (10, 11, 'Claude alone'),
       896: (10, 11, 'Claude alone'),
       912: (11, 13, 'Claude alone'),
       928: (10, 11, 'Claude alone'),
       944: (10, 11, 'Claude alone'),
       960: (13, 15, 'Claude alone'),
       976: (10, 11, 'Claude alone'),
       992: (10, 11, 'Claude alone'),
       2 ** 24: (25, 29, 'Claude and BGPW'), 2 ** 33: (35, 41, 'Claude alone'),
       2 ** 49: (52, 61, 'Claude alone'), 2 ** 51: (54, 63, 'Claude and BGPW'),
       2 ** 57: (61, 71, 'Claude alone'), 2 ** 67: (72, 83, 'Claude alone')}
# EXAMPLE_BY[n]: who found the example of order NEW[n][0] at n, as the page's remarks credit it, for each n whose lo
# is that cited value (no sequence of that order is here; columns() asserts that these are exactly those n).  A cited
# lo's ["page", who] names whose example it is, and a cited hi's whose proof, the cell's title.  At 496 they differ:
# the title is 'Claude and BGPW', for the proof of the upper bound, and the remark reads "An example of order 9 found
# by BGPW."  Empty since 2026-10-12: FOUND made every such lo explicit (352, 368, 400, 464 and 496 had been cited).
EXAMPLE_BY = {}
# CITED[n]: the page's values at n as (lo, hi, hiWhy), Table 2's first, then the new results'
CITED = {}
for _n, (_lo, _hi) in TABLE2.items(): CITED.setdefault(_n, []).append((_lo, _hi, ['table2']))
for _n, (_lo, _hi, _who) in NEW.items(): CITED.setdefault(_n, []).append((_lo, _hi, ['page', _who]))
# The hex codes in the page's remarks, in page order, as (label, m, hex) in the paper's Table 5 convention
# (overnight_v5.from_hex).  The label names the page and the code's name there.
PAGE_CODES = (('index.html BGPW 352', 9, 'A4DB4926DB4D36584B26936D2CFA54B6F04B2C13D4A2'),
              ('index.html BGPW 368', 9, '96C965925B75B0CB249E583CF26B2E836C31DAC874B67D'),
              ('index.html BGPW 400', 9, '34DB69269A69269A6D379A8D1C57459C5B45E5100DBAF7EAAA'),
              ('index.html BGPW 464', 9, '93C96596CB2586DB1C965964E69975A207755BE209CE5E28F2C35A92BA'),
              ('index.html p320', 9, 'B24B649ED92CD2C36496CB2DB6295D974138BA41'),
              ('index.html BGPW 336', 10, 'C87695B43E0ED258AB29C7793D8521DB227C0B746D'),
              ('index.html p336', 9, '9C5479E2669C97071E731A62EBC06F28E87B4961DF'),
              ('index.html p432', 11, '5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46'),
              ('index.html p448', 9, 'A5994DB29B45A0FA5D26B24D665A5A66B24D64BA5F05A2D94DB299A5'),
              ('index.html p480', 12, 'B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3'),
              ('index.html BGPW 496', 9, 'C96992D92DB24B7596496D1A530DB5994EA699A9ACE072BDC57403B339A4CE'),
              ('index.html p192', 9, 'C1BE1E21CD63D295A7887A59'),
              ('index.html p112', 7, 'A5994DB29B45A0'),
              ('index.html p48', 6, 'C27D8C'))
# Claude's own examples of order 9 at the lengths where the page credits BGPW's (352, 368, 400, 464 and 496), found on
# 2026-10-12 by a CP-SAT search (scratch/lower24-design/wider/), as (n, m, hex) in overnight_v5.from_hex's convention;
# BGPW's examples came first, as the page says, and since 2026-10-12 the page shows theirs (PAGE_CODES), which win
# the tie, so these are an independent check.  Their label is 'found here', as brute force's.
FOUND = ((352, 9, '969E4C06F693B61B683699E934D241A6DB4936D7CDA6'),
         (368, 9, 'B449E6A1DB4AB5A123D2DB84B7592CB2496596DB64B4C9'),
         (400, 9, 'A70B2F45D60B4BE22CD2DE51B49B4924DB6D26D349A6926DB4'),
         (464, 9, '8EA4DC62B3DF10709957C395683E3A4D369A6F30DA6984D36D86934C26'),
         (496, 9, 'C2BAD83D5017FA285E3D82ED96135DA2394EB48A6D349E6994D349B6D34DA7'))
# The sets of the page's section "Claude's examples as sets", as (m, n) for SClaude[m][n], in page order
PAGE_SET_KEYS = ((9, 320), (9, 336), (11, 432), (9, 448), (12, 480), (10, 528))


def page_n(s):
    """An n cell of the page's tables: digits, or 2<sup>k</sup>."""
    m = re.fullmatch(r'(\d+)|2<sup>(\d+)</sup>', s)
    assert m, s
    return int(m[1]) if m[1] else 2 ** int(m[2])


def page_value(s):
    """A value cell: v, "a or b", "≥ a" or "a–b", as (lo, hi), hi None when open."""
    for pat, f in ((r'(\d+)', lambda g: (int(g[0]), int(g[0]))), (r'(\d+) or (\d+)', lambda g: (int(g[0]), int(g[1]))),
                   (r'≥ (\d+)', lambda g: (int(g[0]), None)), (r'(\d+)–(\d+)', lambda g: (int(g[0]), int(g[1])))):
        m = re.fullmatch(pat, s)
        if m: return f(m.groups())
    raise AssertionError(s)


PAPER = 'The published paper (2021)'      # the legend's label, and the title, of the paper's values


def page_sources(html):
    """Table 2, the new results, the codes and the sets, parsed out of index.html and asserted equal to the hand
    copies above.  Returns {'table2': {n: (lo, hi)}, 'new': {n: (lo, hi, who)}, 'codes': [(m, hex)],
    'sets': [(m, n, set)]}.  The page's tables of class "block" are Table 2's three, then the new results' five (every
    multiple of 16 from 304 to 992 in four rows of 11, then the powers of 2)."""
    tables = re.findall(r'<table class="block">(.*?)</table>', html, re.S)
    assert len(tables) == 8, len(tables)
    rows = []
    for t in tables:
        ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">(.*?)</tr>', t, re.S)[1])
        vals = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="vals">(.*?)</tr>', t, re.S)[1])
        assert len(ns) == len(vals), (ns, vals)
        rows.append([(page_n(c), re.search(r"title='([^']*)'", attr), page_value(v)) for (attr, c), v in zip(ns, vals)])
    table2 = {n: v for row in rows[:3] for n, title, v in row}
    assert all(title is None for row in rows[:3] for _, title, _ in row)
    assert len(table2) == sum(map(len, rows[:3])) == 39
    # The final row copies Table 2's powers of 2, uncolored and titled as the legend's "The published paper (2021)":
    # each must equal Table 2's entry, and they are no new results.
    copies = [(n, v) for row in rows[3:] for n, title, v in row if title[1] == PAPER]
    assert copies and all(table2[n] == v for n, v in copies), copies
    new = {n: v + (title[1],) for row in rows[3:] for n, title, v in row if title[1] != PAPER}
    assert len(new) + len(copies) == sum(map(len, rows[3:]))
    codes = []
    for block in re.findall(r'<p class="code">(.*?)</p>', html, re.S):
        ms = [int(m) for m in re.findall(r'\(<i>m</i> = (\d+)\)', block)]
        hs = re.findall(r'<code>([0-9A-F]+)</code>', block)
        assert len(ms) == len(hs) >= 1, block
        codes += list(zip(ms, hs))
    sets = [(int(m), int(n), {int(t) for t in body.split(',')})
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', html)]
    assert table2 == TABLE2, table2
    assert new == NEW, new
    assert codes == [(m, h) for _, m, h in PAGE_CODES], codes
    assert [(m, n) for m, n, _ in sets] == list(PAGE_SET_KEYS), sets
    return {'table2': table2, 'new': new, 'codes': codes, 'sets': sets}


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
EXAMPLE_LABELS = {(240, 10): 'BGPW Table 5', (432, 11): 'index.html p432', (192, 9): 'BGPW Table 5',
                  (320, 9): 'index.html p320', (336, 9): 'index.html p336', (48, 6): 'BGPW Table 5',
                  (112, 7): 'BGPW Table 5', (304, 8): 'BGPW Table 5', (64, 6): 'Thue–Morse',
                  (40, 5): 'overnight_v5 EXAMPLES', (48, 5): 'overnight_v5 EXAMPLES', (56, 5): 'overnight_v5 EXAMPLES',
                  (104, 6): 'overnight_v5 EXAMPLES'}


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
def explicit():
    """Every explicit sequence, as {(n, label): sequence}, in this order of preference: Thue-Morse, BGPW's Table 4,
    BGPW's Table 5 (arXiv v1, and the published one through overnight_v5.EXAMPLES), the page's codes, the page's sets,
    the rest of overnight_v5.EXAMPLES, brute force ("found here", order >= 1 only) and FOUND ("found here").  Each
    sequence's exact order is asserted equal to what its source says; at a repeated (n, label) the one of higher order
    stays."""
    src = page_sources(open(PAGE, encoding='utf-8').read())
    v5_bgpw = [(k, h) for k, h in v5.EXAMPLES.items() if EXAMPLE_LABELS[k] == 'BGPW Table 5']
    v5_rest = [(k, h) for k, h in v5.EXAMPLES.items() if EXAMPLE_LABELS[k] != 'BGPW Table 5']
    assert set(EXAMPLE_LABELS) == set(v5.EXAMPLES)
    for m, ns, h in BGPW_T4: assert set(bin(int(h, 16))[2:].zfill(4 * len(h))[max(ns) // 2:]) <= {'0'}, h
    entries = ([('Thue–Morse', k, thue_morse(k)) for k in range(1, NMAX.bit_length())]
               + [('BGPW Table 4', m, from_rp(h, m, n)) for m, ns, h in BGPW_T4 for n in ns]
               + [('BGPW Table 5', m, from_rp(h, m, n)) for m, n, h in BGPW_T5]
               + [('BGPW Table 5', m, v5.from_hex(h, m)) for (n, m), h in v5_bgpw]
               + [(label, m, v5.from_hex(h, m)) for label, m, h in PAGE_CODES]
               + [(f'index.html SClaude[{m}][{n}]', m, from_set(S, n)) for m, n, S in src['sets']]
               + [(EXAMPLE_LABELS[n, m], m, v5.from_hex(h, m)) for (n, m), h in v5_rest]
               + [('found here', *brute(n)) for n in range(1, BRUTE_MAX + 1) if brute(n)[0] >= 1]
               + [('found here', m, v5.from_hex(h, m)) for n, m, h in FOUND])
    assert all(len(v5.from_hex(h, m)) == n for n, m, h in FOUND)
    out, orders = {}, {}
    for label, m, a in entries:
        assert order(a) == m, (label, len(a), m)
        key = (len(a), label)
        if m > orders.get(key, -1): out[key], orders[key] = a, m
    return out


# ---------- upper bounds ----------

def two(n): return 2 ** ((n & -n).bit_length() - 1) - 1


def norm(n, p):
    """The norm lemma's bound for the prime p, which must not divide n: the largest m >= 0 with
    p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1)."""
    assert sp.isprime(p) and n % p, (n, p)
    rhs = (p * sum(len(range(r, n, p)) ** 2 for r in range(p))) ** (p - 1)
    m = 0
    while p ** (2 * m + 2) * (p - 1) ** (p - 1) <= rhs: m += 1
    return m


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
    s = [len(range(r, n, M)) for r in cls]
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
# is 'digits' (the same as 'natural' for a prime) but 624's, which takes 670000 nodes in 'natural' and 3.1 million in
# 'digits'.  Claims that do not set hi (where a citation is lower: 96, 240, 288) are left out.
RESIDUE = {24: (5, (5, 25), 'digits'), 40: (6, (3,), 'digits'), 48: (7, (5, 25), 'digits'),
           72: (7, (4, 8), 'digits'), 80: (7, (3, 9), 'digits'), 88: (7, (3, 9), 'digits'), 104: (7, (4, 8), 'digits'),
           120: (7, (4, 8), 'digits'), 128: (8, (3,), 'digits'), 136: (7, (4, 8), 'digits'),
           160: (8, (3, 9), 'digits'), 192: (10, (5,), 'digits'), 208: (9, (3,), 'digits'), 224: (9, (3,), 'digits'),
           256: (9, (3, 9), 'digits'), 336: (11, (5,), 'digits'), 352: (10, (3,), 'digits'),
           368: (10, (3,), 'digits'), 384: (12, (5,), 'digits'), 400: (10, (3,), 'digits'), 416: (10, (3,), 'digits'),
           432: (13, (5,), 'digits'), 448: (10, (3,), 'digits'), 464: (10, (3,), 'digits'), 480: (15, (7,), 'digits'),
           496: (10, (3, 9), 'digits'), 512: (10, (3, 9, 27), 'digits'), 528: (13, (5,), 'digits'),
           576: (13, (5,), 'digits'), 608: (11, (3,), 'digits'), 624: (13, (5, 25), 'natural'),
           640: (11, (3,), 'digits'), 656: (11, (3,), 'digits'), 672: (14, (5,), 'digits'), 688: (11, (3,), 'digits'),
           704: (11, (3,), 'digits'), 720: (15, (16,), 'digits'), 736: (11, (3, 9), 'digits'),
           768: (14, (5,), 'digits'), 784: (11, (3, 9, 27), 'digits'), 864: (15, (5,), 'digits'),
           912: (14, (5,), 'digits'), 960: (16, (7,), 'digits')}


# ---------- the columns ----------

@lru_cache(maxsize=None)
def explicit_lo():
    """lo and loWhy from explicit sequences alone, for n = 1..NMAX (index n; index 0 unused): the best of the examples
    at n, the joins a + b and the products a b (a, b >= 2), each part valued at its own explicit lo; the first best in
    that order, so an example beats a join and a join a product, the least a first, and ["none"] (lo 0) stays only
    when nothing beats it, which is exactly at odd n.  A column whose explicit lo a citation beats (its final lo is
    the citation's, with no sequence behind it) is no part of any join or product."""
    ex = explicit()
    orders = {key: order(a) for key, a in ex.items()}
    lo, why, part = [0] * (NMAX + 1), [['none']] * (NMAX + 1), [False] * (NMAX + 1)
    for n in range(1, NMAX + 1):
        cands = ([(0, ['none'])] + [(o, ['example', label]) for (k, label), o in orders.items() if k == n]
                 + [(min(lo[a], lo[n - a]), ['join', a, n - a]) for a in range(1, n) if part[a] and part[n - a]]
                 + [(lo[a] + lo[n // a], ['product', a, n // a]) for a in range(2, n // 2 + 1)
                    if n % a == 0 and part[a] and part[n // a]])
        lo[n], why[n] = max(cands, key=lambda c: c[0])
        part[n] = all(c[0] <= lo[n] for c in CITED.get(n, []))
    return tuple(lo), tuple(map(tuple, why))


@lru_cache(maxsize=None)
def build(n):
    """The sequence behind column n's explicit lo, built from the explicit sequences by its joins and products."""
    why = explicit_lo()[1][n]
    rule = {'none': lambda: [1] * n, 'example': lambda: explicit()[n, why[1]],
            'join': lambda: join(build(why[1]), build(why[2])),
            'product': lambda: product(build(why[1]), build(why[2]))}
    return rule[why[0]]()


@lru_cache(maxsize=None)
def columns():
    """[lo, hi, loWhy, hiWhy] for n = 1..NMAX (index n-1), asserting along the way: every claim of RESIDUE, every
    built sequence's order, lo <= hi, the page's exact values and ranges, brute force, that no join or product
    leans on a column whose lo is a citation, and that EXAMPLE_BY names exactly the columns whose lo is the new
    results'."""
    lo_x, why_x = explicit_lo()
    for n, (m, chain, sweep) in RESIDUE.items(): assert chain_none(n, m, chain, sweep, RESIDUE_CAP), (n, m, chain)
    out = []
    for n in range(1, NMAX + 1):
        a = build(n)
        assert len(a) == n and order(a) >= lo_x[n], n
        cited = CITED.get(n, [])
        lo, lw = max([(lo_x[n], list(why_x[n]))] + [(v[0], ['table2']) for k, v in TABLE2.items() if k == n]
                     + [(NEW[k][0], ['page', who]) for k, who in EXAMPLE_BY.items() if k == n], key=lambda c: c[0])
        his = ([(0, ['odd'])] * (n % 2) + [(two(n), ['two'])] + [(norm(n, p), ['norm', p]) for p in PRIMES if n % p]
               + [(m - 1, ['residue', chain[-1]]) for k, (m, chain, _) in RESIDUE.items() if k == n]
               + [(c[1], c[2]) for c in cited if c[1] is not None])
        hi, hw = min(his, key=lambda c: c[0])
        assert lo <= hi, (n, lo, hi, lw, hw)
        assert all(c[0] <= lo <= hi <= (hi if c[1] is None else c[1]) for c in cited), (n, cited, lo, hi)
        out.append([lo, hi, lw, hw])
    for n, (lo, hi, lw, hw) in enumerate(out, 1):
        assert lw[0] not in ('join', 'product') or all(out[k - 1][2] == list(why_x[k]) for k in lw[1:]), n
        assert n > BRUTE_MAX or lo == hi == brute(n)[0], n
    assert {n for n, c in enumerate(out, 1) if c[2][0] == 'page'} == set(EXAMPLE_BY), EXAMPLE_BY
    return tuple(out)


def js_text(cols):
    """mstar.js: a comment line, then const MSTAR = {...}; with one column per line."""
    T = max(c[1] for c in cols) + 1
    rows = ',\n'.join(json.dumps(c) for c in cols)
    return ('// Generated by mstar.py from index.html and the sources it names; edit mstar.py, not this file.\n'
            f'const MSTAR = {{"nmax": {NMAX}, "mtop": {T}, "cols": [\n{rows}\n]}};\n')


def main():
    # TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
    if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
    cols = columns()
    open(JS, 'w', encoding='utf-8').write(js_text(cols))
    settled = sum(c[0] == c[1] for c in cols)
    gray = [n for n, c in enumerate(cols, 1) if c[0] < c[1]]
    # TODO: summary line; says mstar.js was written: how many of the columns are settled (lo = hi), the gray columns, and the top row
    print(f'Claude: "wrote mstar.js: {settled} of {NMAX} columns settled; gray: {gray}; mtop {max(c[1] for c in cols) + 1}"')


if __name__ == '__main__':
    main()
