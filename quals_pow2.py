#!/usr/bin/env python3
"""Quals for pow2.py, which computes the bounds on m*(2^k) behind the powers-of-2 chart on index.html and writes
pow2.js.  Run: python3 quals_pow2.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the resultata
(what happened instead).  Where a qual checks pow2.py's arithmetic it does so by an independent route: mstar.js and
pow2.js as node sees them (not pow2.py's parse), the norm lemma's class sizes as n // p + (r < n % p) and against
mstar.norm, lengths multiplied out here, orders of the blocks' sequences by synthetic division, and residue claims
enumerated again.  Quals marked "regression" pin numbers found earlier rather than stating a property.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, math, time, subprocess, traceback, itertools
from functools import lru_cache
import sympy as sp
import mstar
import pow2

HERE = os.path.dirname(os.path.abspath(__file__))
KMAX = 72
F_PARTS = (((112, 7), (320, 9), (320, 9)), ((432, 11), (48, 6), (256, 8)))   # f, as the remarks on index.html give it


def node_global(path, name):
    """The file at path run as a classic script by node in a fresh context: (its text, the enumerable globals it
    created, the value of the global name as JSON)."""
    js = open(path, encoding='utf-8').read()
    code = ("const vm = require('vm'); const ctx = vm.createContext({});"
            "vm.runInContext(require('fs').readFileSync(process.argv[1], 'utf8'), ctx);"
            f"const v = JSON.parse(vm.runInContext('JSON.stringify({name})', ctx));"
            "process.stdout.write(JSON.stringify({keys: Object.keys(ctx), v: v}));")
    out = subprocess.run(['node', '-e', code, path], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    return js, got['keys'], got['v']


@lru_cache(maxsize=None)
def mstar_disk():
    """mstar.js's columns as node sees them, cols[n-1] for n = 1..mstar.NMAX."""
    return node_global(os.path.join(HERE, 'mstar.js'), 'MSTAR')[2]['cols']


@lru_cache(maxsize=None)
def pow2_disk():
    """pow2.js as node sees it: (text, globals, POW2)."""
    return node_global(os.path.join(HERE, 'pow2.js'), 'POW2')


def cols(): return pow2_disk()[2]['cols']


def norm_here(n, p):
    """The norm lemma's bound (mstar.py's docstring), computed here: class sizes n // p + (r < n % p), and the largest
    m found from a floating-point estimate, moved down while it fails and up while the next one holds (exact)."""
    rhs = (p * sum((n // p + (r < n % p)) ** 2 for r in range(p))) ** (p - 1)
    ok = lambda m: p ** (2 * m) * (p - 1) ** (p - 1) <= rhs
    m = max(0, int((math.log(rhs) - (p - 1) * math.log(p - 1)) / (2 * math.log(p))))
    while m > 0 and not ok(m): m -= 1
    while ok(m + 1): m += 1
    assert ok(m) or m == 0, (n, p)
    return m


def expect_assertion(f):
    """Run f; it must raise AssertionError.  Returns its message."""
    try:
        f()
    except AssertionError as e:
        return str(e)
    # TODO: error copy; says the expected assertion did not fire
    raise AssertionError('Claude: "the expected assertion did not fire"')


@lru_cache(maxsize=None)
def long_examples():
    """{(n, m)}: index.html's examples longer than mstar.NMAX (none since 2026-10-27, when the m*(n) chart reached the
    one there was, at 1024), each a code block of the remarks, p_n of order m alone,
    decoded here by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by (-1)^m
    symmetry), its length n and its exact order m asserted (synthetic division)."""
    page = open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()
    codes = re.findall(r'<i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n\s*<code>([0-9A-F]+)</code>',
                       page)
    long = [(int(n), int(m), h) for n, m, h in codes if int(n) > mstar.NMAX]
    for n, m, h in long:
        left = [2 * int(b) - 1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and exact_order_div(a) == m, (n, m)
    return {(n, m) for n, m, _ in long}


def block_order(b):
    """The order a block [n, m] stands for, by the data contract, from mstar.js as node sees it: m must be mstar.js's
    lo at n <= mstar.NMAX, or b must be one of the page's long_examples(), tau_j = [2^j, j] or f = [2^24, 25]; asserts that
    it is one of them."""
    n, m = b
    assert type(n) is int and type(m) is int and n >= 1, b
    assert ((n <= mstar.NMAX and mstar_disk()[n - 1][0] == m) or (n, m) in long_examples() or n == 2 ** m
            or (n, m) == (2 ** 24, 25)), b
    return m


def exact_order_div(a):
    """The order of a sequence by synthetic division by x - 1 in exact integers (independent of mstar.order's power
    sums): f = (x-1) g has g_k = -(f_0 + ... + f_k), and the sign is irrelevant."""
    c, m = list(a), 0
    while sum(c) == 0:
        c, m = list(itertools.accumulate(c[:-1])), m + 1
    return m


def length(p):
    out = 1
    for n, _ in p: out *= n
    return out


# ---------- f and the lower bounds ----------

def q_f_arithmetic():
    # Replicata: f = (112 # 320 # 320) v (432 # 48 # tau_8), its blocks' orders from mstar.js's columns 112, 320, 432,
    # 48 (as node sees mstar.js) and tau_8; pow2.F and pow2.F_PRODUCTS.
    # Expectata: 112 * 320^2 + 432 * 48 * 2^8 = 2^24 exactly; the products' orders are 7 + 9 + 9 = 25 and 11 + 6 + 8 =
    # 25, so f has length 2^24 and order 25 (BGPW Theorem 4.1); pow2 states the same f.
    assert 112 * 320 ** 2 + 432 * 48 * 2 ** 8 == 2 ** 24
    assert [sum(block_order(b) for b in p) for p in F_PARTS] == [25, 25]
    assert [mstar_disk()[n - 1][0] for n in (112, 320, 432, 48)] == [7, 9, 11, 6]
    assert pow2.F == [2 ** 24, 25] and pow2.F_PRODUCTS == [[list(b) for b in p] for p in F_PARTS]


def q_every_lo_recomputes():
    # Replicata: every column of pow2.js (as node sees it) and its loWhy, recomputed here from the contract alone.
    # Expectata: ["thue-morse"]: lo = k.  ["power", L, j]: L >= 1, 0 <= j < 24, k = 24L + j, lo = 25L + j (f^{#L} # tau_j
    # has length 2^(24L) 2^j and order 25L + j).  ["joins", products]: every factor is a block (block_order), the
    # products' lengths, multiplied out here, sum to 2^k exactly, and lo is the least product order.
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1):
        kind, args = lw[0], lw[1:]
        if kind == 'thue-morse':
            assert args == [] and lo == k, (k, lw)
        elif kind == 'power':
            L, j = args
            assert L >= 1 and 0 <= j < 24 and 24 * L + j == k and lo == 25 * L + j, (k, lw)
            assert length([[2 ** 24, 25]] * L + [[2 ** j, j]]) == 2 ** k
        else:
            assert kind == 'joins' and len(args) == 1 and len(args[0]) >= 1, (k, lw)
            ps = args[0]
            assert sum(length(p) for p in ps) == 2 ** k, (k, lw)
            assert lo == min(sum(block_order(b) for b in p) for p in ps), (k, lw)


def q_lo_at_least_thue_morse_and_f_powers():
    # Replicata: every column of pow2.js.
    # Expectata: lo >= k + floor(k/24) (f^{#L} # tau_j at k = 24L + j, and Thue-Morse below 24); where loWhy is
    # "thue-morse" or "power", lo is exactly that (a join wins only when it is strictly better).
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1):
        assert lo >= k + k // 24, (k, lo)
        assert lw[0] == 'joins' or lo == k + k // 24, (k, lo, lw)
        assert lw[0] != 'joins' or lo > k + k // 24, (k, lo, lw)


def q_new_lower_bounds():
    # Replicata (regression): pow2.js's lo - k, the excess known at 2^k, for k = 1..72, and the kind of its loWhy.
    # Expectata: 0 by Thue-Morse for k <= 9; 1 for 10..19 (joins from pow2.BASES[10], the example of order 11 at 1024
    # alone); 2 for 20..28 (BASES[20], which beats f # tau_j at 24..26); 3 for 29..36 (BASES[29], with the example of
    # order 12 at 912); 4 for 37..40 (BASES[37]); 5 for 41..47 (BASES[41], with the example at 816, of order 11 and since 2026-10-28 12); 6 for
    # 48..56 (BASES[48]); 7 for 57..64 (BASES[57]); 8 for 65..67 (BASES[65]); 9 for 68..72 (BASES[68]); every lo above
    # Thue-Morse's a join.  The bases are at 2^10 order 11, 2^20 order 22, 2^29 order 32, 2^37 order 41, 2^41 order 46,
    # 2^48 order 54, 2^57 order 64, 2^65 order 73 and 2^68 order 77, each lifted by tau_(k - K0) above.  And lo = hi
    # exactly for k <= 12: m*(2^k) is k up to 9, then 11, 12 and 13.  (Before 912's example of order 12, on 2026-10-28:
    # 2 for 20..29 and 3 from 30, BASES[30].  Before 816's example of order 11, at the end of 2026-10-26: 4 for
    # 37..42 and 5 from 43, BASES[43].  Before the example of order 11 at 1024, later on 2026-10-26: lo = hi only for
    # k <= 9, and 0
    # for k <= 16, and 1 for 17..19 from BASES[17], (112 # 800) v (48 # 432 # tau_1).  Before
    # 2026-10-26's examples of order 10 at 752 and 784 and of order 11 at 832: 5 from 46, 6 from 49 and 9 at 72 alone;
    # before 2026-10-25's examples of order 10 at 592, 608 and 656 and of order 11 at 848, 880, 896, 928, 944, 976 and
    # 992: 1 for 17..26, f # tau_j giving it at 24..26, 2 from 27, 3 from 34, 4 from 38, 6 from 52, 8 from 66 and no 9;
    # before 2026-10-17's example of order 11 at 800: 0 below 18, 1 from 18, 2 from 33, 3 from
    # 41, 4 from 48, 5 from 61 and 6 from 71; before 2026-10-12's of order 10 at 560: 1 from 24 by f, 2 from 33, 3 from
    # 49, 4 from 57 and 5 from 67.)
    want = {k: 0 if k < 10 else 1 if k < 20 else 2 if k < 29 else 3 if k < 37 else 4 if k < 41 else 5 if k < 48 else 6
            if k < 57 else 7 if k < 65 else 8 if k < 68 else 9 for k in range(1, KMAX + 1)}
    kind = {k: 'thue-morse' if k < 10 else 'joins' for k in range(1, KMAX + 1)}
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1): assert (lo - k, lw[0]) == (want[k], kind[k]), (k, lo, lw[0])
    orders = {K0: pow2.join_lo(K0, ps) for K0, ps in pow2.BASES.items()}
    assert orders == {10: 11, 20: 22, 29: 32, 37: 41, 41: 46, 48: 54, 57: 64, 65: 73, 68: 77}, orders
    assert [816, 12] in (b for p in pow2.BASES[41] for b in p), pow2.BASES[41]
    assert [912, 12] in (b for p in pow2.BASES[29] for b in p), pow2.BASES[29]
    assert pow2.BASES[10] == [[[1024, 11]]], pow2.BASES[10]
    # lo = hi through k = 12 (the norm bound for 3 at 2^10, the residue condition mod 3 at 2^11 and 2^12), and not at 13
    assert [k for k, (lo, hi, lw, hw) in enumerate(cols(), 1) if lo == hi] == list(range(1, 13)), cols()[9:13]
    pairs = ((10, 10), (19, 10), (20, 20), (28, 20), (29, 29), (36, 29), (37, 37), (40, 37), (41, 41), (47, 41), (48, 48),
             (56, 48), (57, 57), (64, 57), (65, 65), (67, 65), (68, 68), (72, 68))
    assert [cols()[k - 1][2][1] == pow2.lifted(pow2.BASES[K0], k - K0) for k, K0 in pairs] == [True] * len(pairs)


def q_base_blocks_and_their_sources():
    # Replicata: every block of every product of pow2.BASES other than tau_j: for n <= mstar.NMAX, mstar.js's lo and
    # loWhy at n, mstar's explicit lo (sequences in hand only, no citation), and the order of mstar.build(n), the
    # sequence behind it, by synthetic division here; for longer n, the page's long_examples(); and pow2.blocks()
    # beyond NMAX.
    # Expectata: mstar.js's lo is the block's order at every n <= NMAX, and every longer block is one of the page's
    # examples, decoded here at exactly its order (there are none since 2026-10-27, when NMAX reached 1024: from
    # 2026-10-26, 1024 at order 11, BASES[10], was one); so every block of every base has a sequence in hand of
    # exactly its order (explicit lo and the built sequence's order equal it), and every base is built from sequences
    # in hand by BGPW's Theorem 4.1; and pow2's blocks beyond NMAX, other than tau_j and f, are exactly the page's long
    # examples.  (Until 2026-10-12, BASES[57]'s 352 and 464 and BASES[67]'s 400 were
    # cited as BGPW's examples; mstar.FOUND now holds sequences for them.)
    blocks = {K0: {(n, m) for p in ps for n, m in p if n != 2 ** m} for K0, ps in pow2.BASES.items()}
    short = {K0: {(n, m) for n, m in bs if n <= mstar.NMAX} for K0, bs in blocks.items()}
    assert all(mstar_disk()[n - 1][0] == m for bs in short.values() for n, m in bs), short
    assert set().union(*blocks.values()) - set().union(*short.values()) <= long_examples() == set(), blocks
    assert (1024, 11) in short[10] and mstar.NMAX == 1024
    assert {(n, m) for n, m in pow2.blocks() if n > mstar.NMAX and n != 2 ** m and [n, m] != pow2.F} == long_examples()
    cited = {K0: {(n, m) for n, m in bs if mstar_disk()[n - 1][2] == ['page', 'BGPW']} for K0, bs in short.items()}
    assert cited == {K0: set() for K0 in pow2.BASES}, cited
    for n, m in sorted(set().union(*short.values()) - set().union(*cited.values())):
        a = mstar.build(n)
        assert mstar.explicit_lo()[0][n] == m == exact_order_div(a) and len(a) == n, (n, m)


def q_small_k_agree_with_mstar():
    # Replicata: pow2.js's columns k with 2^k <= mstar.NMAX (k = 1..10 since 2026-10-27, when the m*(n) chart reached
    # 1024; 1..9 before) against mstar.js's columns n = 2^k (both as node sees them).
    # Expectata: the same lo and hi in both, and hiWhy ["mstar", mstar.js's hiWhy for 2^k, verbatim]; lo = hi = k and
    # loWhy ["thue-morse"] for k <= 9; and at 2^10, lo = hi = 11, loWhy the join of one product, the page's example of
    # order 11 at 1024 (["joins", [[[1024, 11]]]]), and mstar.js's hiWhy the norm bound for 3.
    ks = [k for k in range(1, KMAX + 1) if 2 ** k <= mstar.NMAX]
    assert ks == list(range(1, 11)), ks
    for k in ks:
        lo, hi, lw, hw = mstar_disk()[2 ** k - 1]
        assert cols()[k - 1][:2] == [lo, hi] and cols()[k - 1][3] == ['mstar', hw], (k, cols()[k - 1], mstar_disk()[2 ** k - 1])
        assert k == 10 or (lo == hi == k and cols()[k - 1][2] == ['thue-morse']), (k, lo, hi)
    assert cols()[9] == [11, 11, ['joins', [[[1024, 11]]]], ['mstar', ['norm', 3]]], cols()[9]


# ---------- the upper bounds ----------

def q_norm_matches_mstar_norm():
    # Replicata: pow2.norm(2^k, p) for k = 1..60 and every odd prime p <= 31 (mstar.norm's len(range(...)) runs only
    # below 2^63); then pow2.norm against norm_here for k = 1..72, and on n = 2^k +- 1, 3 * 2^k for k up to 72 where
    # p does not divide n; and pow2.norm(9, 3).
    # Expectata: equal to mstar.norm, and to norm_here, everywhere; AssertionError for 9 and 3 (3 divides 9).
    for p in pow2.NORM_PRIMES:
        for k in range(1, 61): assert pow2.norm(2 ** k, p) == mstar.norm(2 ** k, p), (k, p)
        for k in range(1, KMAX + 1):
            for n in (2 ** k, 2 ** k - 1, 2 ** k + 1, 3 * 2 ** k):
                if n % p: assert pow2.norm(n, p) == norm_here(n, p), (n, p)
    assert pow2.NORM_PRIMES == tuple(sp.primerange(3, 32))
    expect_assertion(lambda: pow2.norm(9, 3))


def q_every_hi_recomputes():
    # Replicata: every column of pow2.js and its hiWhy, recomputed here.
    # Expectata: ["mstar", why] exactly for 2^k <= mstar.NMAX (k <= 10 since 2026-10-27, when the m*(n) chart reached
    # 1024; k <= 9 before), with mstar.js's hi and hiWhy at 2^k; ["norm", p]: p an odd prime <= 31
    # and hi = norm_here(2^k, p), the least over those primes (ties to the least p); ["residue", chain]: the claim
    # pow2.RESIDUE[k] = (hi + 1, chain, sweep), its order below every norm bound (it lowers hi), and its chain run by
    # q_residue_claims.
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1):
        norms = [(norm_here(2 ** k, p), p) for p in pow2.NORM_PRIMES]
        assert (hw[0] == 'mstar') == (2 ** k <= mstar.NMAX), (k, hw)
        if hw[0] == 'mstar':
            assert [hi, hw[1]] == [mstar_disk()[2 ** k - 1][1], mstar_disk()[2 ** k - 1][3]], (k, hw)
        elif hw[0] == 'norm':
            assert len(hw) == 2 and (hi, hw[1]) == min(norms), (k, hw, min(norms))
            assert k not in pow2.RESIDUE, k
        else:
            assert hw[0] == 'residue' and len(hw) == 2, (k, hw)
            m, chain, sweep = pow2.RESIDUE[k]
            assert m == hi + 1 and list(chain) == hw[1] and hi < min(norms)[0], (k, hw, pow2.RESIDUE[k])


def q_larger_primes_weaker():
    # Replicata: pow2.weak_norm(k), a lower bound on the norm lemma's bound at 2^k for every prime p >= 37, for
    # k = 1..72; checked against the exact bound norm_here(2^k, p) for every prime 37 <= p < 400 and k = 1..72, and
    # against pow2.js's hi.
    # Expectata: weak_norm(k) <= norm_here(2^k, p) for each such p (the lemma in pow2.weak_norm's docstring), and
    # weak_norm(k) > hi for k >= 10, so no prime beyond 31 can lower hi.
    for p in sp.primerange(37, 400):
        for k in range(1, KMAX + 1): assert pow2.weak_norm(k) <= norm_here(2 ** k, p), (k, p)
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1):
        assert k <= 9 or pow2.weak_norm(k) > hi, (k, hi, pow2.weak_norm(k))


def q_norm_never_below_a_known_order():
    # Replicata: every column's lo in pow2.js, against the norm bound for every odd prime p <= 31 (norm_here) and
    # pow2.weak_norm for larger ones; and every block of every join, against its own norm bounds.
    # Expectata: lo <= every bound (a known order above a proven bound would be a contradiction, so a bug).
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1):
        assert all(lo <= norm_here(2 ** k, p) for p in pow2.NORM_PRIMES) and lo <= pow2.weak_norm(k), (k, lo)
        for p in (lw[1] if lw[0] == 'joins' else []):
            for n, m in p:
                assert all(m <= norm_here(n, q) for q in pow2.NORM_PRIMES if n % q), (k, n, m)


def q_mod3_residue_lowers_hi_at_32_columns():
    # Replicata (regression): pow2.RESIDUE and pow2.js's hiWhy and hi.
    # Expectata: the residue condition mod 3 at the order the norm bound for 3 allows, pow2.norm(2^k, 3), leaves no
    # admissible vector at exactly these 32 k (found by the verification of the 2026-10-12 update; q_residue_claims
    # enumerates each), so there hi is one less, with hiWhy ["residue", [3]]; elsewhere past the m*(n) chart's columns
    # (2^k > mstar.NMAX) it stays the norm bound.
    K = (11, 12, 14, 15, 18, 19, 20, 22, 23, 26, 30, 31, 33, 34, 37, 38, 39, 41, 42, 45, 49, 50, 53, 56, 57, 58, 60, 61,
         64, 68, 69, 72)
    assert sorted(pow2.RESIDUE) == list(K), sorted(pow2.RESIDUE)
    assert all(pow2.RESIDUE[k] == (pow2.norm(2 ** k, 3), (3,), 'digits') for k in K)
    for k, (lo, hi, lw, hw) in enumerate(cols(), 1):
        if 2 ** k <= mstar.NMAX: continue
        assert (hw, hi) == ((['residue', [3]], pow2.norm(2 ** k, 3) - 1) if k in K else (['norm', 3], pow2.norm(2 ** k, 3))), (k, hw, hi)


def q_residue_claims():
    # Replicata: every claim (m, chain, sweep) of pow2.RESIDUE at n = 2^k, enumerated by mstar.chain_none to the end
    # (cap 10^9 nodes): the 32 claims mod 3 of q_mod3_residue_lowers_hi_at_32_columns, since 2026-10-12.
    # Expectata: no admissible vector at the last modulus; m - 1 >= lo.
    for k, (m, chain, sweep) in pow2.RESIDUE.items():
        assert sweep in mstar.SWEEPS and mstar.chain_none(2 ** k, m, chain, sweep, 10 ** 9), (k, m, chain)
        assert m - 1 >= cols()[k - 1][0], k


# ---------- the file ----------

def q_pow2_js_is_current():
    # Replicata: pow2.js on disk, and pow2.js_text(pow2.columns()) generated now.
    # Expectata: the same text, and node sees the same columns.
    js, keys, P = pow2_disk()
    assert js == pow2.js_text(pow2.columns())
    assert P['cols'] == pow2.columns()


def q_schema():
    # Replicata: pow2.js on disk: its text, and the file run as a classic script by node.
    # Expectata: one comment line, then the single statement "const POW2 = {...};" whose object is JSON, so the file
    # defines exactly one global (node sees no enumerable one); keys kmax, etop, cols in that order; kmax = 72; 72
    # columns [lo, hi, loWhy, hiWhy] with integers k <= lo <= hi < k + etop; etop = max over k of (hi - k) + 1, so row
    # etop is red in every column and some column reaches row etop - 1; each reason in its contract form.
    js, keys, P = pow2_disk()
    lines = js.splitlines(True)
    assert lines[0].startswith('//') and all(not l.startswith('//') for l in lines[1:]), lines[0]
    body = ''.join(lines[1:])
    assert body.startswith('const POW2 = ') and body.endswith('};\n') and body.count(';') == 1, body[:80]
    assert json.loads(body[len('const POW2 = '):-2]) == P and keys == [], keys
    assert list(P) == ['kmax', 'etop', 'cols'] and P['kmax'] == KMAX and len(P['cols']) == KMAX
    E = P['etop']
    assert type(E) is int and E == max(c[1] - k for k, c in enumerate(P['cols'], 1)) + 1, E
    forms_lo = {'thue-morse': (), 'power': (int, int), 'joins': (list,)}
    forms_hi = {'mstar': (list,), 'norm': (int,), 'residue': (list,)}
    for k, c in enumerate(P['cols'], 1):
        assert len(c) == 4, k
        lo, hi, lw, hw = c
        assert type(lo) is int and type(hi) is int and k <= lo <= hi < k + E, (k, c)
        assert k + E > hi, k                                         # row E is red
        for why, forms in ((lw, forms_lo), (hw, forms_hi)):
            assert type(why) is list and why and why[0] in forms, (k, why)
            assert tuple(type(x) for x in why[1:]) == forms[why[0]], (k, why)
        assert hw[0] != 'residue' or (all(type(M) is int for M in hw[1]) and hw[1][0] >= 2
                                      and all(b % a == 0 and b > a for a, b in zip(hw[1], hw[1][1:]))), (k, hw)
        assert lw[0] != 'joins' or all(type(p) is list and p and all(type(b) is list and len(b) == 2 for b in p)
                                        for p in lw[1]), (k, lw)


def q_assertions_fire():
    # Replicata: pow2.join_lo and pow2.lo_of on broken reasons: a join whose lengths sum to 2^k - 1 or 2^k + 1 at k =
    # 10; a block at the wrong order ([480, 13], [256, 9], [2^24, 26], and [1024, 12] beside the page's [1024, 11]);
    # an empty join and an empty product; power with 24L + j != k, with j = 24 and with L = 0; and pow2.hi_of on
    # ["mstar", why] at k = 11, past the m*(n) chart's columns (at k = 10 until 2026-10-27, when that chart reached
    # 1024), ["norm", 2] and ["norm", 9], and ["residue", chain] at a k with no claim.
    # Expectata: AssertionError for each; and the unbroken forms give their orders, ["mstar", ["norm", 3]] at k = 10
    # among them.
    assert pow2.join_lo(10, [[[1024, 10]]]) == 10 and pow2.join_lo(10, [[[512, 9]], [[512, 9]]]) == 9
    assert pow2.join_lo(10, [[[1024, 11]]]) == 11 and pow2.join_lo(11, [[[1024, 11], [2, 1]]]) == 12
    for ps in ([[[512, 9]], [[511, 0]]], [[[512, 9]], [[513, 0]]], [[[480, 13], [2, 1]], [[64, 6]]], [[[256, 9], [4, 2]]],
               [], [[]], [[[2 ** 24, 26]]], [[[1024, 12]]]):
        expect_assertion(lambda: pow2.join_lo(10 if ps != [[[2 ** 24, 26]]] else 24, ps))
    assert pow2.lo_of(25, ['power', 1, 1]) == 26
    for w in (['power', 1, 2], ['power', 0, 25], ['power', 2, -23], ['power', 1, 24]):
        expect_assertion(lambda: pow2.lo_of(25 if w[1:] != [1, 24] else 48, w))
    assert pow2.hi_of(10, ['mstar', ['norm', 3]]) == 11
    expect_assertion(lambda: pow2.hi_of(11, ['mstar', ['norm', 3]]))
    expect_assertion(lambda: pow2.hi_of(10, ['norm', 2]))
    expect_assertion(lambda: pow2.hi_of(10, ['norm', 9]))
    k = min(set(range(10, KMAX + 1)) - set(pow2.RESIDUE))
    expect_assertion(lambda: pow2.hi_of(k, ['residue', [3, 9, 27]]))


def q_refuses_without_assertions():
    # Replicata: python3 -O pow2.py, in a copy of the repo's pow2.py run from a scratch directory.
    # Expectata: it exits with an error naming the refusal and writes no pow2.js there.
    with __import__('tempfile').TemporaryDirectory() as d:
        src = open(os.path.join(HERE, 'pow2.py'), encoding='utf-8').read()
        open(os.path.join(d, 'pow2.py'), 'w', encoding='utf-8').write(src)
        out = subprocess.run([sys.executable, '-O', '-B', os.path.join(d, 'pow2.py')], capture_output=True, text=True,
                             timeout=600, cwd=d, env={**os.environ, 'PYTHONPATH': HERE})
        assert out.returncode != 0 and 'refusing to run without assertions' in out.stderr, (out.returncode, out.stderr)
        assert not os.path.exists(os.path.join(d, 'pow2.js'))


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
