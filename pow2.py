#!/usr/bin/env python3
"""Bounds on m*(2^k) for k = 1..KMAX, for the powers-of-2 chart on index.html: computes them with their reasons and
writes pow2.js beside this file.  The chart shows them as excesses over Thue-Morse.

mstar.py's docstring defines sequence, order, m*(n), lo, hi, column, join, product, size(M, r), residue sums, chain,
sweep and claim, and states the two lemmas; this file uses them in its sense, and these besides:
  excess   order - log2(length).  Thue-Morse tau_k (length 2^k, order k, Prouhet) has excess 0 at every k; a
           product's excess is the sum of its factors'.
  block    a length and an order known at that length, written [n, m]: a column n <= 1000 of mstar.js at its lo,
           tau_j as [2^j, j], or f as [2^24, 25].
  f        (112 # 320 # 320) v (432 # 48 # tau_8) (index.html's remarks; its set is X_order25_2^24.txt.gz): length
           112 * 320^2 + 432 * 48 * 2^8 = 2^24, order min(7 + 9 + 9, 11 + 6 + 8) = 25 by BGPW's Theorem 4.1
           (Multiplication and Addition), the blocks' orders from mstar.js.  F_PRODUCTS below; f^{#L} is f # ... # f,
           L factors: length 2^(24L), order 25L.

The data contract.  pow2.js is a classic script (no modules, so the page also works from file://) defining one global:
    const POW2 = {"kmax": 72, "etop": E, "cols": [[lo, hi, loWhy, hiWhy], ...]};
cols[k-1] is n = 2^k, k = 1..72.  lo and hi are orders (not excesses), integers with k <= lo <= hi < k + E: lo the
best known order at 2^k, hi the best proven upper bound.  Cell (k, e), e = 1..E, is green when k + e <= lo, gray when
lo < k + e <= hi, and red when k + e > hi; E = max over k of (hi - k) + 1, so row E is red in every column.
  loWhy  ["thue-morse"] (lo = k, tau_k); ["power", L, j] (lo = k + L from f^{#L} # tau_j, k = 24L + j, 0 <= j < 24);
         ["joins", [[[n, m], ...], ...]] (a join of products, each product a list of blocks: 2^k is the sum of the
         products' lengths, and lo the least product order).
  hiWhy  ["mstar", why] (k <= 9: mstar.js's hiWhy for n = 2^k, verbatim); ["norm", p] (the norm lemma for the odd
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
import mstar                                 # read only: the residue enumeration (chain_none) and its lemmas

KMAX = 72
NORM_PRIMES = tuple(sp.primerange(3, 32))    # the odd primes the norm lemma is tried with (weak_norm: no larger one
                                             # can do better at any 2^k, k >= 10)
HERE = os.path.dirname(os.path.abspath(__file__))
MSTAR_JS = os.path.join(HERE, 'mstar.js')
JS = os.path.join(HERE, 'pow2.js')
F = [2 ** 24, 25]
F_PRODUCTS = [[[112, 7], [320, 9], [320, 9]], [[432, 11], [48, 6], [256, 8]]]
RESIDUE_CAP = 10 ** 8                        # nodes allowed to the enumeration of one claim
# RESIDUE[k] = (m, chain, sweep): the claims at n = 2^k, each checked by mstar.chain_none on every run.
RESIDUE = {}
# JOINS[k]: a join of products at 2^k, found by the search in scratch/pow2/, checked here on every run.
JOINS = {}


# ---------- mstar.js ----------

@lru_cache(maxsize=None)
def mstar_text():
    """mstar.js's text: one comment line, then const MSTAR = {...}; with JSON for the object."""
    return open(MSTAR_JS, encoding='utf-8').read()


def mstar_cols():
    """mstar.js's columns, cols[n-1] for n = 1..1000, parsed from its text."""
    head, body = mstar_text().split('const MSTAR = ')
    assert head.startswith('//') and head.count('\n') == 1 and body.endswith('};\n') and body.count(';') == 1, head
    M = json.loads(body[:-2])
    assert M['nmax'] == 1000 == len(M['cols']), M['nmax']
    return M['cols']


@lru_cache(maxsize=None)
def blocks():
    """Every block as (n, m): mstar.js's columns at their lo, tau_j for j = 0..KMAX, and f."""
    return frozenset([(n, c[0]) for n, c in enumerate(mstar_cols(), 1)] + [(2 ** j, j) for j in range(KMAX + 1)]
                     + [tuple(F)])


# ---------- lower bounds ----------

def join_lo(k, products):
    """The order of a join of products at 2^k: asserts that every factor is a block and that the products' lengths
    sum to 2^k exactly; returns the least product order (BGPW's Theorem 4.1)."""
    assert len(products) >= 1 and all(len(p) >= 1 for p in products), products
    assert all(len(b) == 2 and tuple(b) in blocks() for p in products for b in p), products
    assert sum(prod(n for n, _ in p) for p in products) == 2 ** k, (k, products)
    return min(sum(m for _, m in p) for p in products)


def power_products(k, L, j):
    """f^{#L} # tau_j as a join of one product, for k = 24L + j."""
    assert L >= 1 and 0 <= j < 24 and 24 * L + j == k, (k, L, j)
    assert join_lo(24, F_PRODUCTS) == F[1]
    return [[F] * L + [[2 ** j, j]]]


LO_RULES = {'thue-morse': lambda k: [[[2 ** k, k]]], 'power': power_products, 'joins': lambda k, ps: ps}


def lo_of(k, why): return join_lo(k, LO_RULES[why[0]](k, *why[1:]))


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
    """mstar.js's hi at 2^k <= 1000, whose hiWhy must be why."""
    assert 2 ** k <= 1000 and mstar_cols()[2 ** k - 1][3] == why, (k, why)
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
    """[lo, hi, loWhy, hiWhy] for k = 1..KMAX (index k-1): lo the best of Thue-Morse, f^{#L} # tau_j and JOINS[k]; hi
    the least of mstar.js's column 2^k (k <= 9), the norm lemma for each of NORM_PRIMES and the claim RESIDUE[k].
    Asserts k + floor(k/24) <= lo <= hi, that no prime beyond NORM_PRIMES gives a lower norm bound, and lo = hi = k
    = mstar.js's lo and hi for k <= 9."""
    out = []
    for k in range(1, KMAX + 1):
        L, j = divmod(k, 24)
        los = [['thue-morse']] + [['power', L, j]] * (L >= 1) + [['joins', ps] for q, ps in JOINS.items() if q == k]
        his = ([['mstar', c[3]] for n, c in enumerate(mstar_cols(), 1) if n == 2 ** k] + [['norm', p] for p in NORM_PRIMES]
               + [['residue', list(ch)] for q, (_, ch, _) in RESIDUE.items() if q == k])
        lw, hw = max(los, key=lambda w: lo_of(k, w)), min(his, key=lambda w: hi_of(k, w))
        lo, hi = lo_of(k, lw), hi_of(k, hw)
        assert k + L <= lo <= hi < weak_norm(k), (k, lo, hi, lw, hw)
        out.append([lo, hi, lw, hw])
    for k in range(1, 10): assert out[k - 1][:2] == [k, k] == mstar_cols()[2 ** k - 1][:2], k
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
