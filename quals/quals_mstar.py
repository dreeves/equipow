#!/usr/bin/env python3
"""Quals for mstar.py, which computes the bounds on m*(n) behind the chart on index.html and writes mstar.js.
Run: python3 quals/quals_mstar.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the resultata
(what happened instead).  Where a qual checks mstar.py's arithmetic it does so by an independent route: orders by
synthetic division instead of power sums, the two lemma by polynomial division over GF(2), the norm lemma by exact
determinants in Z[zeta], the residue enumeration against overnight_v5.admissible, and brute force against plain
enumeration of every sequence.  Quals marked "regression" pin numbers found earlier rather than stating a property.

Spec change (dreeves, 2026-11-09, after his rename of Claude to Opus 5.5 on the page stopped mstar.py: "probably yes to
the decoupling"): mstar.NEW's credits and mstar.js's ["page", who] are the classes of the page's cells, c (the model
alone, as the comments here written before say "Claude alone"), j (with BGPW), ca (with Astra), a (Astra alone) and s
(BGPW), and no qual here spells out a word of a title or of the legend, which are the page's alone
(q_credits_are_the_cells_classes_not_their_words).
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, random, itertools, subprocess, tempfile, traceback, math
from functools import lru_cache
import sympy as sp
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, os.path.join(HERE, 'pagegen'))   # mstar.py's directory since 2026-11-10 ([REF]); the root until then
ENGINE = os.path.join(HERE, 'engine')                                 # the engine's, since [FAC] stage 3b (2026-11-04)
sys.path.insert(0, ENGINE)                                            # for its modules
import mstar
import overnight_v5 as v5

EXPLICIT = ('example', 'join', 'product', 'none')        # loWhy kinds backed by a sequence built here
CHECKED_HI = ('odd', 'two', 'norm', 'residue', 'proof', 'prop44')   # hiWhy kinds proved here ('proof' since 2026-11-10: mstar.PROOFS; 'prop44' since 2026-11-11: mstar.prop44)
# The gray columns of the user's count (multiples of 16 whose m* the sources here leave open), and 1008, the one gray
# column of the lengths the chart gained on 2026-10-27, when it reached 1024
USER_GRAY = (240, 288, 384, 432, 480) + tuple(range(528, 993, 16)) + (1008,)
# The gray columns past 1024, since 2026-11-10, when the chart came to reach 2048 (dreeves's README: "[BOU] Let's try
# having Figure 1 go up to 2048"): 31 multiples of 16, those of the 60 columns there whose two and norm bound exceeds
# their explicit lo that neither the chart's residue tests (the claims of mstar.RESIDUE past 1024, found by
# scratch/bou-20261110/search.py), nor the page's Symmetry section's sequences (1040, 1072, 1136 and 1168, at 11), nor
# the page's proof at 1456 (mstar.PROOFS: q_1456_is_settled_by_its_proof) settle.
# Less 1584 and 1776 since 2026-11-11, settled at 14 by symmetric sequences of order 14 that the pinned search found
# (scratch/sym12-20261110/; the page's Symmetry section lists them): 29 were left.
# Less 23 more since that day's second round (scratch/q1920-20261111/; the Symmetry section's third list): the 14
# lengths prime to 3 from 1504 to 2032, settled at 12 by symmetric sequences of order 12 that the tilted search found;
# 1200, 1296, 1392, 1488, 1680, 1872 and 1968, settled at 14 by symmetric sequences of order 14 (the upper bound 14 at
# all but 1296 is BGPW's Proposition 4.4, q_proposition_44_keeps_odd_multiples_of_16_at_14_or_less); and 1632 and
# 1728, settled at 15 by antisymmetric sequences of order 15.  Six are left.
PAST_GRAY = (1056, 1104, 1248, 1440, 1920, 2016)


@lru_cache(maxsize=None)
def cols():
    """mstar.py's columns, computed once per run of the quals."""
    return mstar.columns()


@lru_cache(maxsize=None)
def disk():
    """mstar.js on disk, as the page's script sees it: run as a classic script by node in a fresh context; returns
    the file's text and {'keys': the enumerable globals it created, 'm': MSTAR}."""
    path = os.path.join(HERE, 'pagedata', 'mstar.js')
    js = open(path, encoding='utf-8').read()
    code = ("const vm = require('vm'); const ctx = vm.createContext({});"
            "vm.runInContext(require('fs').readFileSync(process.argv[1], 'utf8'), ctx);"
            "const m = JSON.parse(vm.runInContext('JSON.stringify(MSTAR)', ctx));"
            "process.stdout.write(JSON.stringify({keys: Object.keys(ctx), m: m}));")
    out = subprocess.run(['node', '-e', code, path], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return js, json.loads(out.stdout)


def divides_order(a, m):
    """Is (x-1)^m a divisor of sum_i a_i x^i?  Synthetic division by x-1, m times, in exact integers (independent of
    mstar.order's power sums)."""
    c = list(a)
    for _ in range(m):
        if sum(c) != 0: return False
        c = list(itertools.accumulate(c[:-1]))           # f = (x-1) g: g_k = -(f_0 + ... + f_k); the sign is irrelevant
    return True


def exact_order_div(a):
    m = 0
    while divides_order(a, m + 1): m += 1
    return m


def v2(n): return (n & -n).bit_length() - 1


def expect_assertion(f):
    """Run f; it must raise AssertionError.  Returns its message."""
    try:
        f()
    except AssertionError as e:
        return str(e)
    # TODO: error copy; says the expected assertion did not fire
    raise AssertionError('Claude: "the expected assertion did not fire"')


def rebuild(n, cs, ex):
    """Column n's sequence from the columns cs alone (mstar.js's data), with mstar's explicit sequences for examples."""
    lo, hi, why, _ = cs[n - 1]
    kind = why[0]
    assert kind in EXPLICIT, (n, why)
    if kind == 'none': return [1] * n
    if kind == 'example': return ex[n, why[1]]
    a, b = why[1], why[2]
    if kind == 'join': return rebuild(a, cs, ex) + rebuild(b, cs, ex)
    fa, fb = rebuild(a, cs, ex), rebuild(b, cs, ex)
    return [s * t for t in fb for s in fa]


# ---------- sequences and their orders ----------

def q_order_by_power_sums():
    # Replicata: mstar.order on [1], [1, 1], [1, -1], the page's {1, 4} | {2, 3} as [+1, -1, -1, +1], Thue-Morse of
    # lengths 8 and 64, and 100 random sequences of lengths 2..40; then on [1, 0], [] and [1, 2].
    # Expectata: 0, 0, 1, 2, 3, 6, and on the random ones the order found by synthetic division; then AssertionError
    # for each of the last three (not a +-1 sequence).
    assert [mstar.order(a) for a in ([1], [1, 1], [1, -1], [1, -1, -1, 1])] == [0, 0, 1, 2]
    assert mstar.order(mstar.thue_morse(3)) == 3 and mstar.order(mstar.thue_morse(6)) == 6
    rng = random.Random(1)
    for _ in range(100):
        a = [rng.choice((1, -1)) for _ in range(rng.randrange(2, 41))]
        assert mstar.order(a) == exact_order_div(a), a
    for bad in ([1, 0], [], [1, 2]): expect_assertion(lambda: mstar.order(bad))


def q_join_and_product_rules():
    # Replicata: every pair of Thue-Morse sequences tau_1..tau_5 and brute-force witnesses of lengths 8..24, joined
    # (a then b) and multiplied (f_a(x) f_b(x^len a)).
    # Expectata: the join has length len a + len b and order at least the lesser order; the product has length
    # len a * len b, entries +-1, and order exactly the sum of the orders (f_b(x^a) = (x-1)^s (1+...+x^(a-1))^s H(x^a)
    # is nonzero at 1 after removing (x-1)^s).
    pieces = [mstar.thue_morse(k) for k in range(1, 6)] + [mstar.brute(n)[1] for n in (8, 12, 16, 20, 24)]
    for a, b in itertools.product(pieces, repeat=2):
        oa, ob = exact_order_div(a), exact_order_div(b)
        j, p = mstar.join(a, b), mstar.product(a, b)
        assert len(j) == len(a) + len(b) and exact_order_div(j) >= min(oa, ob)
        assert len(p) == len(a) * len(b) and set(p) <= {1, -1} and exact_order_div(p) == oa + ob


def q_brute_force_small_n():
    # Replicata: mstar.brute(n) for n = 1..BRUTE_MAX; and, for n <= 16, plain enumeration of all 2^n sequences with
    # orders by synthetic division.
    # Expectata: m*(n) = 0 for odd n, 1 for n = 2 mod 4, 2 at n = 4, 3 for n = 4 mod 8 from 12 on, and Table 2's
    # 3, 4, 4, 5 at n = 8, 16, 24, 32; each witness has length n and exact order m*(n); plain enumeration agrees.
    assert mstar.BRUTE_MAX >= 32
    want = {n: 0 if n % 2 else 1 if n % 4 == 2 else 3 for n in range(1, 33)} | {4: 2, 8: 3, 16: 4, 24: 4, 32: 5}
    for n in range(1, mstar.BRUTE_MAX + 1):
        m, a = mstar.brute(n)
        assert len(a) == n and exact_order_div(a) == m, n
        assert n > 32 or m == want[n], (n, m, want[n])
        if n <= 16:
            assert m == max(exact_order_div(s) for s in itertools.product((1, -1), repeat=n)), n


# ---------- the two lemmas ----------

def q_two_lemma():
    # Replicata: for n = 1..NMAX, the multiplicity of x+1 in (x^n - 1)/(x - 1) over GF(2), by repeated division of
    # bit-packed polynomials; and for n <= 16, the orders of all 2^n sequences.
    # Expectata: the multiplicity is 2^v - 1, v the exponent of 2 in n, which is mstar.two(n); no sequence of
    # length n <= 16 has order above two(n).
    def mult(n):
        f, k = (1 << n) - 1, 0                            # bit i is the coefficient of x^i: 1 + x + ... + x^(n-1)
        while bin(f).count('1') % 2 == 0:                 # f(1) = 0 mod 2: x + 1 divides f
            q, acc = 0, 0
            for i in range(f.bit_length() - 1, 0, -1):    # divide by x + 1 from the top: q_(i-1) = sum_(j>=i) f_j
                acc ^= (f >> i) & 1
                q |= acc << (i - 1)
            f, k = q, k + 1
        return k
    for n in range(1, mstar.NMAX + 1):
        assert mult(n) == 2 ** v2(n) - 1 == mstar.two(n), n
    for n in range(1, 17):
        assert max(exact_order_div(s) for s in itertools.product((1, -1), repeat=n)) <= mstar.two(n), n


def norm_of(S, p):
    """The norm from Q(zeta_p) to Q of sum_r S_r zeta^r: the product of its p - 1 conjugates sum_r S_r zeta^(a r),
    multiplied out in Z[x]/(x^p - 1); the product h is fixed by every conjugation, so h_1 = ... = h_(p-1) and the
    norm is h(zeta) = h_0 - h_1 (asserted)."""
    h = [1] + [0] * (p - 1)
    for a in range(1, p):
        g = [0] * p
        for r in range(p): g[a * r % p] += S[r]
        h = [sum(h[i] * g[(k - i) % p] for i in range(p)) for k in range(p)]
    assert len(set(h[1:])) <= 1, h
    return h[0] - h[-1]


def q_norm_lemma():
    # Replicata: for n = 2..12 and every sequence of order >= 1, each prime p <= 7 not dividing n: N, the norm of
    # f(zeta_p), computed exactly from the residue sums S_r as the product of the conjugates; and the same for every
    # explicit sequence of mstar.explicit() of order >= 1, p in 3, 5, 7 not dividing its length.
    # Expectata: N != 0, p^order divides N, and N^2 (p-1)^(p-1) <= (p sum_r size_r^2)^(p-1), so order <= norm(n, p).
    def check(a, p):
        n, o = len(a), exact_order_div(a)
        N = norm_of([sum(a[r::p]) for r in range(p)], p)
        sizes = [len(range(r, n, p)) for r in range(p)]
        assert N != 0 and N % p ** o == 0, (n, p, o, N)
        assert N * N * (p - 1) ** (p - 1) <= (p * sum(s * s for s in sizes)) ** (p - 1), (n, p)
        assert o <= mstar.norm(n, p), (n, p, o)
    assert norm_of([1, 0, 0], 3) == 1 and norm_of([1, -1, 0], 3) == 3 and norm_of([2, 0, 0, 0, 0], 5) == 16
    for n in range(2, 13):
        for s in itertools.product((1, -1), repeat=n):
            if sum(s) == 0:
                for p in (2, 3, 5, 7):
                    if n % p: check(list(s), p)
    for (n, label), a in mstar.explicit().items():
        if mstar.order(a) >= 1:
            for p in (3, 5, 7):
                if n % p: check(a, p)


def q_norm_formula():
    # Replicata: mstar.norm(n, p) for n = 1..NMAX and every prime p <= 31 not dividing n.
    # Expectata: the largest m >= 0 with p^(2m) (p-1)^(p-1) <= (p sum_r size_r^2)^(p-1), found by a separate search
    # from above; PRIMES are the primes up to 31.
    assert mstar.PRIMES == tuple(sp.primerange(2, 32))
    for n in range(1, mstar.NMAX + 1):
        for p in mstar.PRIMES:
            if n % p:
                rhs = (p * sum(len(range(r, n, p)) ** 2 for r in range(p))) ** (p - 1)
                m = 64
                while p ** (2 * m) * (p - 1) ** (p - 1) > rhs: m -= 1
                assert m == mstar.norm(n, p), (n, p)


# ---------- the page and the other sources ----------

def q_page_parse():
    # Replicata: mstar.page_sources on index.html as it is.
    # Expectata: Table 2 and the new-results block exactly as hand-copied into mstar.py (TABLE2, NEW, with each new
    # cell's title), the codes and the joins with their orders; Table 2 has the paper's 39 entries and NEW 70 (17 until
    # 2026-10-12, when 2^33, 2^49, 2^57 and 2^67 joined the powers of 2 and every multiple of 16 up to 992 the rest, and
    # then 2^18, 2^41, 2^48, 2^61 and 2^71, once 560 reached order 10; 55 until 2026-10-17, when 2^17, 2^27, 2^34, 2^38,
    # 2^46, 2^52 and 2^66 joined them, once 800 reached order 11; 63 from 2026-10-20, when 240 joined them, settled
    # at 10 by the search overnight_v5.py and boxsplit.py made; 68 from 2026-10-25, when 2^20, 2^30, 2^37, 2^65 and
    # 2^72 joined them, once 592, 608 and 656 reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11;
    # 70 from 2026-10-26, when 2^43 and 2^68 joined them, once 752 and 784 reached order 10 and 832 order 11; 73 from
    # later that day, when 2^10, 2^11 and 2^12 joined them, settled at 11, 12 and 13 by Claude's example of order 11
    # at 1024; 74 from 2026-10-27, when 1008 joined them, as the chart and the table reached 1024; 75 from 2026-10-28,
    # when 2^29 joined them, once 912 reached order 12; 76 from that evening, when 2^39 joined them, once 768 reached
    # order 12; 79 from 2026-11-03, when 2^28, 2^36 and 2^47 joined them, once that day's examples moved their firsts;
    # 81 from later that day, when 2^56 and 2^58 joined them, once the search found firsts there among those examples;
    # 82 since 2026-11-08, when 288 joined them, settled at 9 by the form-tree proof).
    src = mstar.page_sources(open(os.path.join(HERE, 'index.html'), encoding='utf-8').read())
    assert src['table2'] == mstar.TABLE2 and len(mstar.TABLE2) == 39
    assert src['new'] == mstar.NEW and len(mstar.NEW) == 82
    assert set(who for _, _, who in mstar.NEW.values()) == {'s', 'c', 'j', 'a', 'ca'}
    assert [(m, h) for _, m, h in mstar.PAGE_CODES] == [(m, h) for m, h in src['codes']]
    # since 2026-10-31 the joins of codes, in place of the section "Claude's examples as sets" (dreeves: "every
    # bipartition we give should be presented the same way as an expandable hex code"): the 528 entry's f = p192 ∨
    # q336, explicit()'s sequence p192's signs then q336's, of order exactly 10, neither symmetric nor antisymmetric
    assert src['joins'] == [(m, ids) for _, m, ids in mstar.PAGE_JOINS] == [(10, ('192:9', '336:9'))], src['joins']
    hexes = {(label, m): h for label, m, h in mstar.PAGE_CODES}
    f = mstar.explicit()[528, 'equipow p192 ∨ q336']
    assert f == v5.from_hex(hexes['equipow p192', 9], 9) + v5.from_hex(hexes['equipow q336', 9], 9), f[:8]
    assert exact_order_div(f) == 10 and f != f[::-1] and f != [-t for t in reversed(f)], f[:8]
    # and the page's symmetric p528 of order 10 (since 2026-10-27; dreeves: "sure to the additional 528 bipartition"),
    # from PAGE_CODES: since 2026-10-31 the label also names the order-11 p528, which mstar.explicit keeps at that label
    p528 = [h for label, m, h in mstar.PAGE_CODES if (label, m) == ('equipow p528', 10)]
    sym = v5.from_hex(p528[0], 10)
    assert len(p528) == 1 and sym == sym[::-1] and exact_order_div(sym) == 10


def q_credits_are_the_cells_classes_not_their_words():
    # Replicata: index.html, and index.html reworded (quals_index.reworded: every title of the new results' cells and
    # every label of their legend, each word's letters reversed), each given to mstar.page_sources; mstar.NEW; and
    # mstar.js's columns.
    # Expectata (dreeves, 2026-11-09, after his rename of Claude to Opus 5.5 on the page stopped mstar.py: "it seems
    # dumb that me tweaking the prose in index.html has yielded this much work from you", then "probably yes to the
    # decoupling"): the reworded page gives the same sources as the page, so that no word of a title or of the legend
    # is data; NEW's credits are the classes of the cells (quals_index.CREDITS), each that of its cell on the page;
    # and each ["page", who] of mstar.js is NEW's credit at its n.
    # Resultata before: NEW held the titles' words, page_sources asserted them equal to the page's and told the
    # paper's cells by the words of their title, and mstar.js carried the words as ["page", who].
    import quals_index as qi              # read only: reworded, CREDITS
    text = open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()
    assert mstar.page_sources(qi.reworded(text)) == mstar.page_sources(text)
    cells = re.findall(r'<td class="(\w+)" title=\'[^\']*\'>(\d+|\\\(2\^\{?\d+\}?\\\))</td>', text)
    classes = {mstar.page_n(c): k for k, c in cells}
    assert {n: who for n, (_, _, who) in mstar.NEW.items()} == classes and set(classes.values()) == set(qi.CREDITS), classes
    _, got = disk()
    cited = [(n, w) for n, c in enumerate(got['m']['cols'], 1) for w in c[2:] if w[0] == 'page']
    assert cited and all(w == ['page', mstar.NEW[n][2]] for n, w in cited), cited


def q_384_settled_by_astra():
    # Replicata: the page's hand-copied result and its generated chart column after Astra's exact mod-5 proof.
    # Expectata: 384 is settled at 10, with the new upper bound attributed to Astra; 432 is the first length whose
    # upper bound still permits order 11, and it has a verified construction of that order.
    assert mstar.NEW[384] == (10, 10, 'a'), mstar.NEW[384]
    _, got = disk()
    cols = got['m']['cols']
    assert cols[383][:2] == [10, 10] and cols[383][3] == ['page', 'a'], cols[383]
    assert next(n for n, col in enumerate(cols, 1) if col[1] >= 11) == 432
    assert cols[431][0] == 11, cols[431]


def q_page_parse_is_strict():
    # Replicata: index.html with one change each: Table 2's 136 -> 7 (the first value of its block); 496's "9" (class j) ->
    # "9–10" (528's "10–12" -> "10–11" until 2026-10-31, when 528's cell became 11–12, class c, like 576's and 624's);
    # 320's title BGPW -> Claude alone; the code C27D8C -> C27D8D; that code's anchor id 48:6, its length and order
    # (2026-10-31, dreeves's README, [IND]: "make the "p320" or whatever be a hyperlink / anchor link"), dropped, -> 48:7
    # and -> 49:6; the first block table dropped.
    # Expectata: AssertionError from mstar.page_sources for each (the parse must equal the hand copy).
    html = open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()
    # (496's "9" found beside 512's since 2026-11-08, when 288's cell became a class j 9 too.)
    for old, new in (('<td class="j">9</td><td class="c">9</td>', '<td class="j">9–10</td><td class="c">9</td>'),
                     ('<code id="48:6">C27D8C</code>', '<code id="48:6">C27D8D</code>'),
                     ('<code id="48:6">C27D8C</code>', '<code>C27D8C</code>'),
                     ('<code id="48:6">C27D8C</code>', '<code id="48:7">C27D8C</code>'),
                     ('<code id="48:6">C27D8C</code>', '<code id="49:6">C27D8C</code>')):
        assert html.count(old) == 1, old
        expect_assertion(lambda: mstar.page_sources(html.replace(old, new)))
    # 320's credit, the class of its cell, s -> c (its title's words changed, until 2026-11-09, when the credits became
    # the classes and the titles' words the page's alone: q_credits_are_the_cells_classes_not_their_words)
    recolored, count = re.subn(r'<td class="s"( title=\'[^\']*\'>320</td>)', r'<td class="c"\1', html)
    assert count == 1, count
    expect_assertion(lambda: mstar.page_sources(recolored))
    i = html.index('<tr class="vals">', html.index('<td>136</td>'))
    j = html.index('</tr>', i)
    assert html[i:j].count('<td>6</td>') >= 1
    expect_assertion(lambda: mstar.page_sources(html[:i] + html[i:j].replace('<td>6</td>', '<td>7</td>', 1) + html[j:]))
    k = html.index('<table class="block">')
    expect_assertion(lambda: mstar.page_sources(html[:k] + html[html.index('</table>', k) + len('</table>'):]))
    # And in the new results' table, which subsumes Table 2 since 2026-10-27 (dreeves: "how about making our
    # color-coded table totally subsume the BGPW table?"): Table 2's copy of 136 -> 7; 256 dropped; 512's value -> 10,
    # 2^9's left at 9; 312 inserted after 304; 1008 dropped; the copy of 288 colored c and titled Claude alone; 2^3
    # moved after 2^4.  (288's cell is no copy since 2026-11-08, but the class j's 9 of the new results: that edit now
    # retitles it Claude alone and widens it to 9–10, which page_sources must refuse all the same.)
    paper = "<td title='any words'>"          # a cell with no class copies Table 2, whatever its title says
    for n, f in (('136', lambda ps, i: ps[:i] + [(ps[i][0], '<td>7</td>')] + ps[i + 1:]),
                 ('256', lambda ps, i: ps[:i] + ps[i + 1:]),
                 ('512', lambda ps, i: ps[:i] + [(ps[i][0], '<td class="c">10</td>')] + ps[i + 1:]),
                 ('304', lambda ps, i: ps[:i + 1] + [(f'{paper}312</td>', '<td>7</td>')] + ps[i + 1:]),
                 ('1008', lambda ps, i: ps[:i] + ps[i + 1:]),
                 ('288', lambda ps, i: ps[:i] + [("<td class=\"c\" title='any words'>288</td>", '<td class="c">9–10</td>')]
                  + ps[i + 1:]),
                 ('\\(2^3\\)', lambda ps, i: ps[:i] + [ps[i + 1], ps[i]] + ps[i + 2:])):
        edited = edit_cells(html, n, f)
        expect_assertion(lambda: mstar.page_sources(edited))
    assert mstar.page_sources(html)
    # and the join of the 528 entry (since 2026-10-31, when the joins took the sets' place): its order 10 -> 11, in its
    # data-order alone, and in it and in its label's (m = 10) both; its second code 336:9 -> 336:8, an id no code has;
    # its codes swapped; and its tag without them
    join, label = '<span data-join="192:9 336:9" data-order="10">', '<span>\\(f\\) \\((m = 10)\\):</span>'
    for edits in (((join, join.replace('"10"', '"11"')),),
                  ((join, join.replace('"10"', '"11"')), (label, label.replace('10', '11'))),
                  ((join, join.replace('336:9', '336:8')),),
                  ((join, join.replace('192:9 336:9', '336:9 192:9')),),
                  ((join, '<span>'),)):
        edited = html
        for old, new in edits:
            assert edited.count(old) == 1, old
            edited = edited.replace(old, new)
        expect_assertion(lambda: mstar.page_sources(edited))


def edit_cells(html, n, f):
    """html with the row of the new results' cell n (as the page writes it: digits, or \\(2^{k}\\)) rewritten from
    f(pairs, i): the row's (n cell, value cell) pairs, i the index of n's."""
    a = html.index('<div class="new-block">')
    for m in re.finditer(r'<table class="block">.*?</table>', html[a:], re.S):
        t = m.group(0)
        ns = re.findall(r'<td[^>]*>.*?</td>', re.search(r'<tr class="ns">(.*?)</tr>', t, re.S)[1])
        vs = re.findall(r'<td[^>]*>.*?</td>', re.search(r'<tr class="vals">(.*?)</tr>', t, re.S)[1])
        hits = [i for i, c in enumerate(ns) if re.fullmatch(rf'<td[^>]*>{re.escape(n)}</td>', c)]
        if not hits: continue
        i, = hits
        pairs = f(list(zip(ns, vs)), i)
        rows = re.sub(r'(<tr class="ns"><th[^>]*>.*?</th>).*?</tr>', lambda r: r[1] + ''.join(c for c, _ in pairs) + '</tr>',
                      t, count=1, flags=re.S)
        rows = re.sub(r'(<tr class="vals"><th[^>]*>.*?</th>).*?</tr>', lambda r: r[1] + ''.join(v for _, v in pairs) + '</tr>',
                      rows, count=1, flags=re.S)
        assert rows != t, n
        return html[:a + m.start()] + rows + html[a + m.end():]
    raise AssertionError(f'no cell {n} in the new results')


def q_explicit_sources_exact():
    # Replicata: mstar.explicit(), every explicit sequence with its label; and each source list on its own.
    # Expectata: every sequence is +-1 of its key's length; Thue-Morse tau_k has order k; BGPW's Table 4 pairs give
    # both lengths at their m; BGPW's Table 5, the page's codes and joins (its sets until 2026-10-31), and
    # overnight_v5.EXAMPLES have exactly their stated orders (by synthetic division); every EXAMPLES entry has a label;
    # no label names Stan (BGPW includes him).
    ex = mstar.explicit()
    for (n, label), a in ex.items():
        assert len(a) == n and set(a) <= {1, -1}, (n, label)
        assert 'Stan' not in label, label
    for k in range(1, 10): assert exact_order_div(mstar.thue_morse(k)) == k
    for m, ns, h in mstar.BGPW_T4:
        for n in ns: assert exact_order_div(mstar.from_rp(h, m, n)) == m, (m, n)
    for m, n, h in mstar.BGPW_T5: assert exact_order_div(mstar.from_rp(h, m, n)) == m, (m, n)
    for label, m, h in mstar.PAGE_CODES: assert exact_order_div(v5.from_hex(h, m)) == m, label
    codes = {f'{len(v5.from_hex(h, m))}:{m}': v5.from_hex(h, m) for _, m, h in mstar.PAGE_CODES}
    for label, m, ids in mstar.PAGE_JOINS: assert exact_order_div([t for i in ids for t in codes[i]]) == m, label
    assert set(mstar.EXAMPLE_LABELS) == set(v5.EXAMPLES)
    for (n, m), h in v5.EXAMPLES.items(): assert exact_order_div(v5.from_hex(h, m)) == m, (n, m)


# ---------- the columns ----------

def q_schema():
    # Replicata: mstar.js on disk: its text, and the file run as a classic script by node.
    # Expectata: comment lines, then the single statement "const MSTAR = {...};" whose object is JSON, so the file
    # defines exactly one global (node sees no other); keys nmax, mtop, mtopAt (since 2026-11-03, README [LIN]), past (since 2026-11-04: the
    # explicit sequences longer than nmax, for the table of smallest lengths, q_past_lists_the_example_of_order_16_at_1440), cols;
    # mtopAt a list of even integers above nmax, one per order from mtop on, never falling (an integer, mtop's alone, from
    # 2026-11-03 until 2026-11-04, README [M17]); nmax = 1024 (1000 until 2026-10-27, when
    # the chart reached 1024 at dreeves's and Stan Wagon's request); 1024 columns, each
    # [lo, hi, loWhy, hiWhy] with integers 0 <= lo <= hi < mtop = max hi + 1 (so row mtop is red in every column);
    # every reason has its contract form; ["none"] and ["odd"] exactly at odd n.
    js, got = disk()
    body = ''.join(line for line in js.splitlines(True) if not line.startswith('//'))
    assert body.startswith('const MSTAR = ') and body.endswith('};\n') and body.count(';') == 1, body[:80]
    assert json.loads(body[len('const MSTAR = '):-2]) == got['m'] and got['keys'] == [], got['keys']
    M = got['m']
    # nmax: 2048 since 2026-11-10 ([BOU]), 1024 from 2026-10-27 until then
    assert list(M) == ['nmax', 'mtop', 'mtopAt', 'past', 'cols'] and M['nmax'] == 2048 == mstar.NMAX and len(M['cols']) == 2048
    assert all(type(n) is int and n > M['nmax'] and type(m) is int and type(label) is str for n, m, label in M['past']), M['past']
    at = M['mtopAt']
    assert type(at) is list and at and all(type(n) is int and n > M['nmax'] and n % 2 == 0 for n in at), at
    assert at == sorted(at), at                  # order m + 1 at n has order m there
    T = M['mtop']
    assert type(T) is int and T == max(c[1] for c in M['cols']) + 1
    forms_lo = {'none': (), 'example': (str,), 'join': (int, int), 'product': (int, int), 'table2': (),
                'page': (str,)}
    forms_hi = {'odd': (), 'two': (), 'norm': (int,), 'residue': (int,), 'proof': (str,), 'prop44': (), 'table2': (), 'page': (str,)}   # proof: since 2026-11-10 (mstar.PROOFS); prop44: since 2026-11-11 (mstar.prop44)
    for n, c in enumerate(M['cols'], 1):
        assert len(c) == 4, n
        lo, hi, lw, hw = c
        assert type(lo) is int and type(hi) is int and 0 <= lo <= hi < T, (n, c)
        for why, forms in ((lw, forms_lo), (hw, forms_hi)):
            assert type(why) is list and why and why[0] in forms, (n, why)
            assert tuple(type(x) for x in why[1:]) == forms[why[0]], (n, why)
        assert (lw == ['none']) == (n % 2 == 1) == (hw == ['odd']), (n, c)
        assert lw[0] != 'page' or lw[1] in ('s', 'c', 'j', 'a', 'ca'), (n, lw)
        assert hw[0] != 'page' or hw[1] in ('s', 'c', 'j', 'a', 'ca'), (n, hw)


def q_mstar_js_is_current():
    # Replicata: mstar.js on disk, and mstar.js_text(mstar.columns()) generated now.
    # Expectata: the same text, which is "const MSTAR = " + the JSON object + ";" (and a comment line).
    js, got = disk()
    assert js == mstar.js_text(cols())
    assert got['m']['cols'] == [list(c) for c in cols()]


def q_columns_rebuilt():
    # Replicata: every column whose loWhy is example, join, product or none, rebuilt from mstar.js's columns alone
    # (a join from its parts' columns, recursively), with mstar.explicit() for the examples.
    # Expectata: a +-1 sequence of length n divisible by (x-1)^lo (synthetic division); a join's parts sum to n and a
    # product's multiply to n, both parts' loWhy are themselves explicit, and lo is the lesser (join) or the sum
    # (product) of the parts' lo; an example's label is in mstar.explicit() at length n.
    _, got = disk()
    cs, ex = got['m']['cols'], mstar.explicit()
    for n in range(1, mstar.NMAX + 1):
        lo, hi, why, _ = cs[n - 1]
        if why[0] not in EXPLICIT: continue
        a = rebuild(n, cs, ex)
        assert len(a) == n and set(a) <= {1, -1} and divides_order(a, lo), (n, why)
        if why[0] in ('join', 'product'):
            x, y = why[1], why[2]
            assert cs[x - 1][2][0] in EXPLICIT and cs[y - 1][2][0] in EXPLICIT, (n, why)
            rule = {'join': (x + y, min(cs[x - 1][0], cs[y - 1][0])), 'product': (x * y, cs[x - 1][0] + cs[y - 1][0])}
            assert rule[why[0]] == (n, lo), (n, why)


def q_lo_reasons():
    # Replicata: every column's lo and loWhy, against the page's values and the explicit sources.
    # Expectata: a table2 or page lo equals the cited lower value, a page lo's who is mstar.EXAMPLE_BY's (whose
    # example the page's remarks credit), and the best explicit construction there is lower (else the checked one
    # would be preferred); an example's lo equals that sequence's exact order.
    _, got = disk()
    cs, ex = got['m']['cols'], mstar.explicit()
    for n, (lo, hi, why, _) in enumerate(cs, 1):
        if why[0] == 'table2': assert mstar.TABLE2[n][0] == lo, n
        if why[0] == 'page': assert mstar.NEW[n][0] == lo and mstar.EXAMPLE_BY[n] == why[1], n
        if why[0] in ('table2', 'page'): assert mstar.explicit_lo()[0][n] < lo, n
        if why[0] == 'example': assert exact_order_div(ex[n, why[1]]) == lo, n


def page_remarks():
    """{n: the rest of the page's remark (its <li> under "Where the new results come from") whose entry lists n}, for
    the n the entries write in digits."""
    html = open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()
    section = re.search(r'<section class="remarks">(.*?)</section>', html, re.S)[1]
    out = {}
    for ns, body in re.findall(r'<p class="entry">\\\(n = ([\d, ]+)\\\):(.*?)</li>', section, re.S):
        for n in ns.split(', '): out[int(n)] = body
    return out


def q_cited_lo_credits_whose_example():
    # Replicata: every column of mstar.js whose loWhy is ["page", who], and the page's remark whose entry lists its n.
    # Expectata: none since 2026-10-12, when mstar.FOUND made the cited lows at 352, 368, 400, 464 and 496 explicit
    # (EXAMPLE_BY is empty to match); should one come back, its remark credits the example to who, saying "example(s)
    # of order lo found by who." (a cited lo's who names whose example it is; a cited hi's, whose proof, the title).
    _, got = disk()
    remarks = page_remarks()
    cited = {n: c for n, c in enumerate(got['m']['cols'], 1) if c[2][0] == 'page'}
    assert sorted(cited) == sorted(mstar.EXAMPLE_BY) == [], sorted(cited)
    for n, (lo, hi, why, _) in cited.items():
        assert re.search(rf'\b[Ee]xamples? of order {lo} found by {re.escape(why[1])}\.', remarks[n]), (n, why, remarks[n])


def q_hi_reasons():
    # Replicata: every column's hi and hiWhy.
    # Expectata: odd at odd n with hi 0; two with hi = 2^v - 1; norm p with p prime, p not dividing n and hi =
    # norm(n, p); residue M with mstar.RESIDUE[n] = (hi + 1, a chain ending at M, a sweep); proof FILE with
    # mstar.PROOFS[n] = (hi, FILE) (since 2026-11-10: q_1456_is_settled_by_its_proof); prop44 with hi = prop44(n),
    # one less than two(n), at an n below 2^two(n) (since 2026-11-11, a spec change of that day, Fable 5.2's, on
    # dreeves's "first get the chart in sync with all the known results": BGPW's Proposition 4.4, which the chart did
    # not apply; q_proposition_44_keeps_odd_multiples_of_16_at_14_or_less); a citation equal to the
    # cited upper value; and hi is the least of all these candidates, the reason the first least in the order odd,
    # two, norm (by p), residue, proof, prop44, table2, page (so a checked one wins every tie with a citation, and
    # prop44, the newest, takes no column from an older test).
    _, got = disk()
    for n, (lo, hi, _, why) in enumerate(got['m']['cols'], 1):
        ranked = ([(0, ['odd'])] * (n % 2) + [(mstar.two(n), ['two'])]
                  + [(mstar.norm(n, p), ['norm', p]) for p in mstar.PRIMES if n % p]
                  + [(m - 1, ['residue', ch[-1]]) for k, (m, ch, _) in mstar.RESIDUE.items() if k == n]
                  + [(h, ['proof', file]) for k, (h, file) in mstar.PROOFS.items() if k == n]
                  + [(mstar.prop44(n), ['prop44'])]
                  + [(h, ['table2']) for k, (_, h) in mstar.TABLE2.items() if k == n and h is not None]
                  + [(h, ['page', who]) for k, (_, h, who) in mstar.NEW.items() if k == n and h is not None])
        assert hi == min(h for h, _ in ranked) and why == next(w for h, w in ranked if h == hi), (n, why, ranked)
        k = why[0]
        if k == 'odd': assert n % 2 and hi == 0
        if k == 'two': assert hi == 2 ** v2(n) - 1
        if k == 'norm': assert sp.isprime(why[1]) and n % why[1] and hi == mstar.norm(n, why[1])
        if k == 'residue': assert mstar.RESIDUE[n][0] == hi + 1 and mstar.RESIDUE[n][1][-1] == why[1], n
        if k == 'proof': assert mstar.PROOFS[n] == (hi, why[1]), n
        if k == 'prop44': assert hi == mstar.prop44(n) == 2 ** v2(n) - 2 and n < 2 ** (2 ** v2(n) - 1), n
        if k == 'table2': assert mstar.TABLE2[n][1] == hi
        if k == 'page': assert mstar.NEW[n][1] == hi and mstar.NEW[n][2] == why[1]


def q_page_agrees():
    # Replicata: every entry of Table 2 and of the new-results block with n <= NMAX, against mstar.js.
    # Expectata: an exact value v gives lo = hi = v; a range a..b (b open for "≥") contains [lo, hi].
    _, got = disk()
    cs = got['m']['cols']
    for table in (mstar.TABLE2, {n: v[:2] for n, v in mstar.NEW.items()}):
        for n, (a, b) in table.items():
            if n > mstar.NMAX: continue
            lo, hi = cs[n - 1][:2]
            assert a <= lo <= hi <= (b if b is not None else hi), (n, a, b, lo, hi)
            assert a != b or lo == hi == a, n


def q_brute_force_in_bounds():
    # Replicata: brute-forced m*(n) for n = 1..BRUTE_MAX, against mstar.js.
    # Expectata: lo = hi = m*(n) at every such n (the bounds are tight there).
    _, got = disk()
    for n in range(1, mstar.BRUTE_MAX + 1):
        assert got['m']['cols'][n - 1][:2] == [mstar.brute(n)[0]] * 2, n


def q_known_shape():
    # Replicata: mstar.js's columns, by n mod 16.
    # Expectata: odd n: lo = hi = 0; n = 2 mod 4: 1; n = 4: 2; n = 4 mod 8 from 12: 3; n = 8 mod 16: lo = hi, and 7 from
    # 200 on; every gray column (lo < hi) is among the user's 35 multiples of 16, or is 1008 (since 2026-10-27, when the
    # chart reached 1024), or one of PAST_GRAY (since 2026-11-10, when it reached 2048).
    _, got = disk()
    cs = got['m']['cols']
    for n, (lo, hi, _, _) in enumerate(cs, 1):
        if n % 2: assert lo == hi == 0, n
        elif n % 4 == 2: assert lo == hi == 1, n
        elif n % 8 == 4: assert lo == hi == (2 if n == 4 else 3), n
        elif n % 16 == 8: assert lo == hi and (n < 200 or lo == 7), n
        else: assert lo == hi or n in USER_GRAY + PAST_GRAY, n


def q_gray_columns():
    # Replicata (regression): the gray columns of mstar.js.
    # Expectata: the user's 35 less 640, which the residue condition mod 3 settles at 10 (lo 10 from 2 x 320), less
    # 704 and 736, settled at 10 on 2026-10-12 (lo 10 from 2 x 352 and 2 x 368, mstar.FOUND's; hi by mod 3 and mod 9),
    # and less 560, settled at 10 the same day (lo 10 from the page's p560, found by a lattice search; hi by the norm
    # bound mod 3), and less 800, settled at 11 on 2026-10-17 (lo 11 from the page's p800, found by a lattice search;
    # hi by the norm bound mod 3), and less 240, settled at 10 on 2026-10-20 (lo 10 from the paper's Table 5 example; hi
    # by the certified search, overnight_v5.py and then boxsplit.py by 17 and 19, the page's new result), and less
    # 384, settled at 10 by Astra's exact modular certificate (2026-10-20, proof384.py), and less 592, 608 and 656,
    # settled at 10, and 848, 880, 896, 928, 944, 976 and 992, settled at 11, on 2026-10-25 (lo from the page's
    # examples p592 to p992; hi by the norm bound mod 3, or the residue condition mod 3 at 608 and 656), and less 752
    # and 784, settled at 10, and 832, settled at 11, on 2026-10-26 (lo from the page's examples p752, p784 and p832;
    # hi by proof752.py at 752, the page's, the residue condition mod 27 at 784 and the norm bound mod 3 at 832); and
    # since 2026-10-27, when the chart reached 1024, 1008 last, at 10 to 13 (lo from 240 + 768, a join; hi by the
    # residue condition mod 5 at order 14), at 11 to 13 from that night (lo from the page's example p1008 of order 11,
    # found by w11.py: q_examples_at_720_and_1008_raise_their_lo), and at 12 to 13 since 2026-10-28 (lo from the
    # symmetric example of order 12 that replaced it as p1008, found by w12.py); and less 688, settled at 10 on
    # 2026-11-01 (lo from the page's example p688, found by w10s.py: q_example_at_688_settles_it; hi by the residue
    # condition mod 3); and less 544, settled at 10, 576 and 624 at 12, 912 and 1008 at 13 and 960 at 15 on 2026-11-03 (lo from the page's examples, found by
    # searches/pinned/: q_results_of_2026_11_03; hi as before); and less 432, settled at 11, and 816, settled at 12, later that day (lo as before; hi by their pin trees: q_pin_trees_settle_432_and_816).
    _, got = disk()
    # Since 2026-11-10 the chart reaches 2048 ([BOU]): up to 1024 the gray columns are as before, and past it PAST_GRAY.
    grays = tuple(n for n, c in enumerate(got['m']['cols'], 1) if c[0] < c[1])
    gray = tuple(n for n in grays if n <= 1024)
    assert tuple(n for n in grays if n > 1024) == PAST_GRAY, grays
    tens, elevens = (592, 608, 656, 688, 752, 784), (832, 848, 880, 896, 928, 944, 976, 992)
    # 768 settled at 13 on 2026-11-03 (the beam campaign's plan 6), and left the gray columns.
    # 672 settled at 13 on 2026-11-04 (searches/tilted/: q_example_at_672_reaches_order_13), and left them too.
    # 288 settled at 9 on 2026-11-08 (the form-tree proof: q_288_is_settled_at_9), and left them too.
    assert gray == tuple(n for n in USER_GRAY if n not in (240, 384, 560, 640, 704, 736, 800) + tens + elevens + (288, 432, 544, 576, 624, 672, 768, 816, 912, 960, 1008)), gray
    assert [got['m']['cols'][n - 1][:2] for n in (240, 384, 560, 640, 704, 736, 800)] == [[10, 10]] * 6 + [[11, 11]]
    assert [got['m']['cols'][n - 1][:3] for n in tens + elevens] == [[10, 10, ['example', f'equipow p{n}']] for n in tens] \
        + [[11, 11, ['example', f'equipow p{n}']] for n in elevens]
    assert got['m']['cols'][240 - 1][2:] == [['example', 'BGPW Table 5'], ['page', 'c']]
    assert got['m']['cols'][560 - 1][2] == ['example', 'equipow p560']
    assert got['m']['cols'][800 - 1][2:] == [['example', 'equipow p800'], ['norm', 3]]
    assert gray[-1] == 864 and got['m']['cols'][1008 - 1] == [13, 13, ['example', 'equipow p1008'], ['residue', 5]]   # 1008 the last, at 12 to 13, until 2026-11-03


def q_results_of_2026_10_25():
    # Replicata (regression): mstar.NEW and mstar.js's columns at the n that 2026-10-25's results changed.
    # Expectata: 592, 608 and 656 settled at 10 and credited to Claude and Astra; 848, 880, 896, 928, 944, 976 and 992
    # settled at 11, Claude alone; each lo from its example on the page (["example", "equipow p" + n]); 752's hi 10,
    # Claude and Astra's, the page's (proof752.py), ["page", "ca"]; 288 still Table 2's 9 to 10.  (Until
    # 2026-10-26, when 752 reached order 10 and 832 order 11, q_results_of_2026_10_26's, 752's lo was 9, the join 192 +
    # 560, and 832's the join 240 + 592, which tied the doubling 2 x 416 and came first.)
    _, got = disk()
    cs = got['m']['cols']
    for n in (592, 608, 656): assert mstar.NEW[n] == (10, 10, 'ca') and cs[n - 1][2] == ['example', f'equipow p{n}'], n
    for n in (848, 880, 896, 928, 944, 976, 992):
        assert mstar.NEW[n] == (11, 11, 'c') and cs[n - 1][2] == ['example', f'equipow p{n}'], n
    assert mstar.NEW[752][1:] == (10, 'ca') and cs[752 - 1][1::2] == [10, ['page', 'ca']]
    # Spec change (Claude, 2026-11-08): no clause for 288, which the form-tree proof settled at 9 that day
    # (q_288_is_settled_at_9); until then this qual held it at Table 2's 9 to 10.


def q_results_of_2026_10_26():
    # Replicata (regression): mstar.NEW and mstar.js's columns at the n that 2026-10-26's results changed, and at the
    # two that stay in their grouped remark.
    # Expectata: 752 and 784 settled at 10 and credited to Claude and Astra, 832 settled at 11, Claude alone; each lo
    # from its example on the page (["example", "equipow p" + n]); each hi as before: 752's the page's (proof752.py),
    # 784's the residue condition mod 27 and 832's the norm bound mod 3 (544, 9 to 10 by the join 192 + 352 until 2026-11-03, is settled at 10 by its example:
    # q_results_of_2026_11_03; 688, 9 to 10 by the join 192 + 496 until 2026-11-01, is settled at 10 by its example: q_example_at_688_settles_it).
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[752] == (10, 10, 'ca') and cs[752 - 1] == [10, 10, ['example', 'equipow p752'], ['page', 'ca']]
    assert mstar.NEW[784] == (10, 10, 'ca') and cs[784 - 1] == [10, 10, ['example', 'equipow p784'], ['residue', 27]]
    assert mstar.NEW[832] == (11, 11, 'c') and cs[832 - 1] == [11, 11, ['example', 'equipow p832'], ['norm', 3]]


def q_example_at_1024_is_checked():
    # Replicata: mstar.explicit()'s sequences of length 1024, mstar.NEW's entry for 2^10, and mstar.js's column 1024
    # (beyond NMAX until 2026-10-27, when the chart reached 1024).
    # Expectata (2026-10-26: Claude's lattice search found an example of order 11 at 1024, which with m*(2^9) = 9 makes
    # 2^10 the first power of 2 beyond Thue-Morse): explicit() has the page's code p1024 (until 2026-10-31 also its set
    # SClaude[11][1024], the same sequence), antisymmetric, of order exactly 11 by synthetic division here, +1 at 0,
    # and Thue-Morse tau_10; NEW[2^10] is (11, 11, 'c'), the norm bound for 3 capping it at 11, and so is
    # mstar.js's column 1024, [11, 11, ["example", "equipow p1024"], ["norm", 3]]; and doubled once and twice it
    # settles 2^11 and 2^12, NEW[2^11] (12, 12, 'c') and NEW[2^12] (13, 13, 'c').
    ex = {label: a for (n, label), a in mstar.explicit().items() if n == 1024}
    assert set(ex) == {'equipow p1024', 'Thue–Morse'}, sorted(ex)
    assert ex['Thue–Morse'] == mstar.thue_morse(10) and exact_order_div(ex['Thue–Morse']) == 10
    assert disk()[1]['m']['cols'][1024 - 1] == [11, 11, ['example', 'equipow p1024'], ['norm', 3]]
    a = ex['equipow p1024']
    assert exact_order_div(a) == 11 and a[0] == 1, a[:8]
    assert all(a[1023 - i] == -a[i] for i in range(1024))
    assert mstar.NEW[2 ** 10] == (11, 11, 'c') and mstar.norm(1024, 3) == 11, mstar.NEW.get(2 ** 10)
    assert [mstar.NEW.get(2 ** k) for k in (11, 12)] == [(12, 12, 'c'), (13, 13, 'c')]


def q_lengths_from_1002_to_1024():
    # Replicata (regression): mstar.js's columns 1002 to 1024, which the chart gained on 2026-10-27 (dreeves, relaying
    # Stan Wagon: "could the table and the chart go up to 1024 as the natural stopping point, instead of 1000?"), and
    # mstar.RESIDUE's claim at 1008.
    # Expectata: n = 2 mod 4 is 1 and n = 4 mod 8 is 3, by joins and the two lemma; 1016 is 7, the most the two lemma
    # allows an odd multiple of 8; 1024 is 11, its example and the norm bound for 3; and 1008 is 13 (since 2026-11-03: 13 from the page's example of order 13,
    # searches/pinned/; 12 to 13 before), 12 from the page's example p1008 (2026-10-28, w12.py's symmetric example of order 12; 11 from 2026-10-27 night, w11.py's
    # antisymmetric one, and 10 before, from the join 240 + 768, the least of its two parts, 10 and 11), and order 14
    # ruled out by the residue condition mod 5 (the
    # claim (14, (5,), 'digits'), found by scratch/upto1024/residue1008.py in both sweeps, where orders 15 and 14 die
    # mod 5 at once), as at 672, 768 and 912; the two lemma and the norm bound for 5 allow 15.
    cs = disk()[1]['m']['cols']
    want = {n: [1, 1] if n % 4 == 2 else [3, 3] if n % 8 == 4 else None for n in range(1002, 1025, 2)}
    assert all(cs[n - 1][:2] == v for n, v in want.items() if v), [(n, cs[n - 1]) for n in want]
    assert cs[1016 - 1][:2] == [7, 7] and cs[1016 - 1][3] == ['two'], cs[1016 - 1]
    assert cs[1024 - 1][:2] == [11, 11] and cs[1008 - 1] == [13, 13, ['example', 'equipow p1008'], ['residue', 5]], cs[1008 - 1]
    assert [cs[n - 1][0] for n in (240, 768)] == [10, 13]          # 768's lo 11, the join's other part, until 2026-10-28; 12 until 2026-11-03
    assert mstar.RESIDUE[1008] == (14, (5,), 'digits') and mstar.two(1008) == mstar.norm(1008, 5) == 15
    assert mstar.NEW[1008] == (13, 13, 'c'), mstar.NEW.get(1008)


def q_example_at_816_raises_its_lo():
    # Replicata: mstar.NEW and mstar.js's column at 816, and mstar.NEW at 2^41.
    # Expectata (2026-10-26: Claude's lattice search, w11.py at 816 without go800f's last-orbit table, found an
    # antisymmetric example of order 11 there; 2026-10-28: w12.py found a symmetric example of order 12 there, which
    # replaced it as p816): 816 is 12, Claude alone, its lo the page's example
    # (["example", "equipow p816"]) and its hi, since 2026-11-03, its pin tree (q_pin_trees_settle_432_and_816: 12 to 14 until then, its hi the norm bound for the residue sums mod 5); and 2^41 is 46 to 50
    # (45 to 50 before), 816 being among the blocks of the first power of 2 known to beat Thue-Morse by 5.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[816] == (12, 12, 'c') and cs[816 - 1] == [12, 12, ['example', 'equipow p816'], ['page', 'c']], cs[816 - 1]
    assert mstar.NEW[2 ** 41] == (46, 50, 'c'), mstar.NEW[2 ** 41]


def q_examples_at_720_and_1008_raise_their_lo():
    # Replicata: mstar.NEW and mstar.js's columns at 720 and 1008.
    # Expectata (2026-10-27: Claude's lattice search, w11.py at 720 and at 1008 (scratch/w1008), found antisymmetric
    # examples of order 11 there; 2026-10-28: w12.py found a symmetric example of order 12 at 1008, which replaced its
    # order-11 one as p1008; that evening Astra's faster w12 found one at 720, which replaced its order-11 one as p720;
    # 2026-11-03: searches/pinned/ found an antisymmetric example of order 13 at 1008, 12 to 13 until then, and the beam
    # campaign (scratch/beam-campaign-20261103/) one at 720, 12 to 14 until then: q_example_at_720_reaches_order_13):
    # 720 is 13 to 14 and 1008 is 13, Claude alone, each lo the page's example
    # (["example", "equipow p720"], ["example", "equipow p1008"]) and each hi still its residue claim (order 15
    # mod 16 at 720, order 14 mod 5 at 1008).
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[720] == (13, 14, 'c') and cs[720 - 1] == [13, 14, ['example', 'equipow p720'], ['residue', 16]], cs[720 - 1]
    assert mstar.NEW[1008] == (13, 13, 'c') and cs[1008 - 1] == [13, 13, ['example', 'equipow p1008'], ['residue', 5]], cs[1008 - 1]


def q_example_at_768_raises_its_lo():
    # Replicata: mstar.NEW and mstar.js's column at 768.
    # Expectata (2026-10-28 evening: Claude's lattice search w12.py found symmetric examples of order 12 at 768, seeds 1
    # and 3): 768 is 12 to 13, Claude alone, its lo the page's example (["example", "equipow p768"]; 11 before, by
    # doubling 384) and its hi still the residue condition mod 5 at order 14.
    _, got = disk()
    cs = got['m']['cols']
    # Since 2026-11-03, 13 to 13: the beam campaign's plan 6 found an example of order 13 (q_example_at_768_reaches_order_13).
    assert mstar.NEW[768] == (13, 13, 'c') and cs[768 - 1] == [13, 13, ['example', 'equipow p768'], ['residue', 5]], cs[768 - 1]


def q_example_at_912_raises_its_lo():
    # Replicata: mstar.NEW and mstar.js's column at 912.
    # Expectata (2026-10-28: Claude's lattice search w12.py, the symmetric order-12 port of w11.py, found a symmetric
    # example of order 12 at 912; 2026-11-03: searches/pinned/ found an antisymmetric example of order 13 there, 12 to 13 until then): 912 is 13, Claude alone,
    # its lo the page's example (["example", "equipow p912"]) and its hi still the residue condition mod 5 at order 14.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[912] == (13, 13, 'c') and cs[912 - 1] == [13, 13, ['example', 'equipow p912'], ['residue', 5]], cs[912 - 1]


def q_examples_at_576_and_624_raise_their_lo():
    # Replicata: mstar.NEW and mstar.js's columns at 576 and 624.
    # Expectata (2026-10-31: Claude's lattice search scratch/w11-624-576/w11.py, scratch/w13/w13.py at antisymmetric
    # order 11 with its ranked pool kept to configurations whose exact q is below h, found antisymmetric examples of
    # order 11 at 576 and 624; 2026-11-03: searches/pinned/ found symmetric examples of order 12 there, 11 to 12 until then): each is 12, Claude alone, its lo the
    # page's example (["example", "equipow p<n>"]) and its hi still the residue condition at order 13 (mod 5 at 576, mod 25 at 624).
    # Resultata before: 576 was 10 to 12, its lo the join 240 + 336, 624 was 10 to 12, its lo the join 240 + 384.
    _, got = disk()
    cs = got['m']['cols']
    for n, M in ((576, 5), (624, 25)):
        assert mstar.NEW[n] == (12, 12, 'c'), (n, mstar.NEW[n])
        assert cs[n - 1] == [12, 12, ['example', f'equipow p{n}'], ['residue', M]], (n, cs[n - 1])


def q_example_at_528_raises_its_lo():
    # Replicata: mstar.NEW and mstar.js's column at 528.
    # Expectata (2026-10-31: Claude's lattice search scratch/w11-624-576/w11.py, at antisymmetric order 11, found
    # seven antisymmetric examples of order 11 at 528, one per seed of its first batch): 528 is 11 to 12, Claude alone
    # (both bounds Claude's), its lo the page's example ["example", "equipow p528"] (the order-11 code, which
    # mstar.explicit keeps over the order-10 p528 of the same label) and its hi still the residue condition at order
    # 13 mod 5.
    # Resultata before: 528 was 10 to 12, Claude and BGPW, its lo the symmetric example p528 of order 10.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[528] == (11, 12, 'c'), mstar.NEW[528]
    assert cs[527] == [11, 12, ['example', 'equipow p528'], ['residue', 5]], cs[527]


def q_example_at_672_raises_its_lo():
    # Replicata: mstar.NEW and mstar.js's column at 672.
    # Expectata (2026-11-01: Claude's lattice search scratch/w11-624-576/w12/w12.py found a symmetric example of order
    # 12 at 672): 672 is 12 to 13, Claude alone, its lo the page's example (["example", "equipow p672"]) and its
    # hi still the residue condition at order 14 mod 5.
    # Resultata before: 672 was 11 to 13, its lo the product 2 * 336.
    _, got = disk()
    cs = got['m']['cols']
    # Since 2026-11-04, 13 to 13: searches/tilted/ found an example of order 13 (q_example_at_672_reaches_order_13).
    assert mstar.NEW[672] == (13, 13, 'c'), mstar.NEW[672]
    assert cs[671] == [13, 13, ['example', 'equipow p672'], ['residue', 5]], cs[671]


def q_example_at_688_settles_it():
    # Replicata: mstar.NEW and mstar.js's column at 688.
    # Expectata (2026-11-01: Claude's lattice search scratch/w11-624-576/w10s/w10s.py found a symmetric example of order
    # 10 at 688): 688 is settled at 10, Claude alone, its lo the page's example (["example", "equipow p688"]) and its hi
    # still the residue condition at order 11 mod 3.
    # Resultata before: 688 was 9 to 10, its lo the join 192 + 496.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[688] == (10, 10, 'c'), mstar.NEW[688]
    assert cs[687] == [10, 10, ['example', 'equipow p688'], ['residue', 3]], cs[687]


def q_results_of_2026_11_03():
    # Replicata: mstar.NEW and mstar.js's columns at the n of 2026-11-03's examples, found by the pinned search (searches/pinned/).
    # Expectata: each is settled, Claude alone, its lo the page's example (["example", "equipow p<n>"]) and its hi as before: 544 at 10 (the norm bound for 3,
    # order 11), 576 at 12 (order 13 mod 5), 624 at 12 (order 13 mod 25), 912 at 13 (order 14 mod 5), 960 at 15 (order 16 mod 7), 1008 at 13 (order 14 mod 5).
    # Resultata before: 544 was 9 to 10 (the join 192 + 352), 576 and 624 were 11 to 12, 912 and 1008 were 12 to 13, and 960 was 13 to 15 (2 * 480).
    _, got = disk()
    cs = got['m']['cols']
    for n, m, hw in ((544, 10, ['norm', 3]), (576, 12, ['residue', 5]), (624, 12, ['residue', 25]), (912, 13, ['residue', 5]),
                     (960, 15, ['residue', 7]), (1008, 13, ['residue', 5])):
        assert mstar.NEW[n] == (m, m, 'c'), (n, mstar.NEW[n])
        assert cs[n - 1] == [m, m, ['example', f'equipow p{n}'], hw], (n, cs[n - 1])


def q_example_at_720_reaches_order_13():
    # Replicata: mstar.NEW and mstar.js's column at 720.
    # Expectata (2026-11-03: the beam campaign's lattice search, scratch/beam-campaign-20261103/, pinned_beam.py of scratch/pinned-fast-20261103/,
    # found an antisymmetric example of order 13 at 720): 720 is 13 to 14, Claude alone, its lo the page's example (["example", "equipow p720"]) and
    # its hi as before (['residue', 16]).
    # Resultata before: 720 was 12 to 14, its lo the page's example of order 12.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[720] == (13, 14, 'c') and cs[720 - 1] == [13, 14, ['example', 'equipow p720'], ['residue', 16]], cs[720 - 1]


def q_pin_trees_settle_432_and_816():
    # Replicata: mstar.NEW and mstar.js's columns at 432 and 816, and the proof files that the page cites for their upper bounds.
    # Expectata (2026-11-03: proofs/pintree_432_12.json.gz and proofs/pintree_816_13.json.gz, which proofs/pintree.py and proofs/pintree_second.py check: quals_pintree): 432 is settled at 11 and 816 at 12, Claude alone, each lo still the
    # page's example, each hi the page's proof; every n below 480 then has hi below 12, so that 480, which has an example of order 12, is the smallest length of order 12.
    # Resultata before: 432 was 11 to 12, its hi the residue condition mod 5 at order 13; 816 was 12 to 14, its hi the norm bound mod 5 at order 15.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[432] == (11, 11, 'c') and cs[432 - 1] == [11, 11, ['example', 'equipow p432'], ['page', 'c']], cs[432 - 1]
    assert mstar.NEW[816] == (12, 12, 'c') and cs[816 - 1] == [12, 12, ['example', 'equipow p816'], ['page', 'c']], cs[816 - 1]
    assert next(n for n, c in enumerate(cs, 1) if c[1] >= 12) == 480 and cs[480 - 1][0] == 12
    for name in ('pintree_432_12.json.gz', 'pintree_816_13.json.gz'): assert os.path.exists(os.path.join(HERE, 'proofs', name)), name


def q_example_at_768_reaches_order_13():
    # Replicata: mstar.NEW and mstar.js's column at 768.
    # Expectata (2026-11-03: the beam campaign's lattice search, scratch/beam-campaign-20261103/, pinned_beam.py of scratch/pinned-fast-20261103/,
    # found an antisymmetric example of order 13 at 768): 768 is 13 to 13, Claude alone, its lo the page's example (["example", "equipow p768"]) and
    # its hi as before (['residue', 5]).
    # Resultata before: 768 was 12 to 13, its lo the page's example of order 12.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[768] == (13, 13, 'c') and cs[768 - 1] == [13, 13, ['example', 'equipow p768'], ['residue', 5]], cs[768 - 1]


def q_example_at_672_reaches_order_13():
    # Replicata: mstar.NEW and mstar.js's column at 672.
    # Expectata (2026-11-04: the tilted search, searches/tilted/, found an antisymmetric example of order 13 at 672): 672 is 13 to 13,
    # Claude alone, its lo the page's example (["example", "equipow p672"]) and its hi as before (['residue', 5]).
    # Resultata before: 672 was 12 to 13, its lo the page's example of order 12.
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[672] == (13, 13, 'c') and cs[672 - 1] == [13, 13, ['example', 'equipow p672'], ['residue', 5]], cs[672 - 1]


def q_288_is_settled_at_9():
    # Replicata: mstar.NEW and mstar.js's column at 288.
    # Expectata (2026-11-08: the form-tree proof, searches/formtree/ and proofs/formtree.py, finished with no open
    # node, and proofs/formtree.py assemble accepted its verdicts: no sequence of length 288 has order 10): 288 is 9 to
    # 9, Claude and BGPW, its lo as before (the product 2 · 144 of BGPW's example, ['product', 2, 144]) and its hi the
    # page's (['page', 'j']).
    # Resultata before: 288 was 9 to 10, not among the new results, its hi BGPW's Table 2 (['table2']).
    _, got = disk()
    cs = got['m']['cols']
    assert mstar.NEW[288] == (9, 9, 'j') and cs[288 - 1] == [9, 9, ['product', 2, 144], ['page', 'j']], cs[288 - 1]


def q_1456_is_settled_by_its_proof():
    # Replicata: mstar.PROOFS, mstar.js's column 1456, and proofs/proof1456.py.
    # Expectata (dreeves, 2026-11-10, when the chart had come to reach 1456 and showed it open at order 12, against the
    # page's m*(1456) = 11 of 2026-11-07: "first get the chart in sync with all the known results"): PROOFS gives 1456
    # the upper bound 11 by proofs/proof1456.py, a file here whose length and order are 1456 and 12 and whose check of
    # its certificate passes (mstar.proved, which columns() runs); mstar.js's column 1456 is [11, 11, ["join", 432,
    # 1024], ["proof", "proofs/proof1456.py"]]; and proved refuses the same file for another length or bound.
    # Resultata before: [11, 12, ["join", 432, 1024], ["norm", 3]]: the chart knew no proof outside the page's tables.
    _, got = disk()
    assert mstar.PROOFS == {1456: (11, 'proofs/proof1456.py')}, mstar.PROOFS
    assert all(os.path.isfile(os.path.join(HERE, file)) for _, file in mstar.PROOFS.values())
    assert got['m']['cols'][1455] == [11, 11, ['join', 432, 1024], ['proof', 'proofs/proof1456.py']], got['m']['cols'][1455]
    mstar.proved(1456, 11, 'proofs/proof1456.py')
    for n, hi in ((1456, 10), (1472, 11)):
        try: mstar.proved(n, hi, 'proofs/proof1456.py')
        except AssertionError: continue
        raise AssertionError((n, hi))


def q_proposition_44_keeps_odd_multiples_of_16_at_14_or_less():
    # 2026-11-11 (Fable 5.2).
    # Replicata: mstar.prop44 at lengths n = t u, t the power of 2 in n and u odd; mstar.js's columns at the odd
    # multiples of 16; every explicit sequence whose order is t - 1.
    # Expectata: BGPW's Proposition 4.4 (their section 4; from Berend and Golan): a sequence of length n and order
    # t - 1 has |f(-1)| >= 2^(t-1), f(-1) its alternating sum, which is at most n; so order t - 1 needs n >= 2^(t-1),
    # and prop44(n) is t - 2 below that and t - 1, Divisibility's bound, from there on: 2 at 4 and 3 at 12; 6 at 8, 24
    # and 120, and 7 at 136; 14 at 16, 1200 and 32752, and 15 at 32784, the least odd multiple of 16 that could have
    # order 15.  No column of an odd multiple of 16 has hi above 14, and the six where no other test gives 14 (1200,
    # 1392, 1488, 1680, 1872 and 1968) have hi 14 with the reason ["prop44"].  What the proposition rests on is seen in
    # every explicit sequence of order t - 1 (orders 1, 3 and 7 here; none of order 15): f(-1) is an odd multiple of
    # 2^(t-1).
    # Resultata before: mstar.py had no prop44, and those six columns were [13, 15, ..., ["two"]]: the chart left order
    # 15 open where the paper it cites rules it out.
    want = {2: 1, 6: 1, 4: 2, 12: 3, 8: 6, 24: 6, 120: 6, 136: 7, 16: 14, 1200: 14, 32752: 14, 32784: 15}
    assert {n: mstar.prop44(n) for n in want} == want
    assert all(mstar.prop44(n) in (mstar.two(n) - 1, mstar.two(n)) for n in range(2, 4097, 2))
    cols = disk()[1]['m']['cols']
    odd16 = range(16, mstar.NMAX + 1, 32)
    assert all(cols[n - 1][1] <= 14 for n in odd16), [(n, cols[n - 1]) for n in odd16 if cols[n - 1][1] > 14]
    by = [n for n, c in enumerate(cols, 1) if c[3] == ['prop44']]
    assert by == [1200, 1392, 1488, 1680, 1872, 1968] and all(cols[n - 1][1] == 14 for n in by), by
    seen = set()
    for (n, label), a in mstar.explicit().items():
        t = n & -n
        if mstar.order(a) == t - 1:
            alt = sum(v if i % 2 == 0 else -v for i, v in enumerate(a))
            assert alt % 2 ** (t - 1) == 0 and (alt // 2 ** (t - 1)) % 2 == 1 and n >= 2 ** (t - 1), (n, label, alt)
            seen.add(t - 1)
    assert seen == {1, 3, 7}, seen


def q_past_lists_the_example_of_order_16_at_1440():
    # Replicata: mstar.js's past, its mtop and mtopAt, and mstar.explicit()'s sequences past NMAX.
    # Expectata (2026-11-04: the tilted search, searches/tilted/, found a symmetric example of order 16 at 1440, the least n past the chart
    # that its tests leave open at order 16, so a(15) = 1440 in OEIS A323395): past is [[1440, 16, "equipow p1440"]], one row [n, m, label] for
    # each explicit sequence longer than NMAX, whose exact order is m; mtop and mtopAt as before, 16 and 1440, so the least n known
    # to reach order mtop is the least n not ruled out.
    # Resultata before: mstar.js had no past, and the page's least n known to reach order 16 was the product 1920 = 960 * 2.
    # Since 2026-11-10 the chart reaches 2048 ([BOU]): 1440 is one of its columns, the example its lower bound, and no
    # explicit sequence is longer than NMAX, so past is empty; the least n known to reach order 16 is still the least
    # not ruled out, as columns now: no column before 1440 allows order 16.
    # Since 2026-11-11 (the day's second round) the page's Symmetry section has symmetric sequences of order 12 at
    # 2096, 2128 and 2192, the lengths prime to 3 past the chart that BGPW's conjecture at order 12 still owed; each is
    # longer than NMAX, so past lists those three.
    _, got = disk()
    M = got['m']
    assert M['past'] == [[2096, 12, 'equipow p2096'], [2128, 12, 'equipow p2128'], [2192, 12, 'equipow p2192']], M['past']
    assert M['cols'][1439][:3] == [16, 17, ['example', 'equipow p1440']], M['cols'][1439]
    assert max(c[1] for c in M['cols'][:1439]) == 15, max(c[1] for c in M['cols'][:1439])
    far = {key: a for key, a in mstar.explicit().items() if key[0] > mstar.NMAX}
    assert [[n, mstar.order(a), label] for (n, label), a in far.items()] == M['past'], list(far)
    at = [a for (n, label), a in mstar.explicit().items() if (n, label) == (1440, 'equipow p1440')]
    assert len(at) == 1 and all(mstar.order(a) == 16 and len(a) == 1440 and a == a[::-1] for a in at), len(at)


# ---------- residue tests ----------

def counts(n, P, W): return tuple((W[r] + len(range(r, n, P))) // 2 for r in range(P))     # +1's per class mod P


def v5_admissible(n, order, M, fixed):
    """overnight_v5.admissible at length n (its N set only for this call), as residue sums D = 2c - size."""
    saved = v5.N
    v5.N = n
    for f in v5.CACHED: f.cache_clear()
    try:
        out = v5.admissible(order, M, fixed)
        return sorted(tuple(2 * c[r] - len(range(r, n, M)) for r in range(M)) for c in out)
    finally:
        v5.N = saved
        for f in v5.CACHED: f.cache_clear()


def q_mtop_is_open_first_at_1440_past_the_chart():
    # Replicata: mstar.js's mtop and mtopAt, and mstar.mtop_at(16) computed now.
    # Expectata (dreeves's README, 2026-11-03: "[LIN] Add one more line for m=16 to the "smallest length known for each
    # order" table", then "yes, 1440 instead of ">1024" if that's all we know so far. we don't need to spend serious
    # effort tightening that"): mtopAt is the least n past NMAX that the chart's own upper-bound tests leave open at
    # order mtop = 16: two(n) and norm(n, p) for the primes of PRIMES not dividing n, then every chain of CHAINS in both
    # sweeps through chain_none at MTOP_CAP nodes, where a capped enumeration rules nothing out.  That n is 1440
    # (scratch/lin16-20261103/, 2026-11-03).  Below it: norm mod 5 rules out 1056, 1152 and 1248, and 1344 passes two
    # and norm but no vector mod 5 is admissible; at 1440, two and norm allow order 16.
    # Resultata before: mstar.js had no mtopAt, and the table's order-16 row read "> 1024".
    _, got = disk()
    M = got['m']
    # (mtopAt is a list since 2026-11-04, [M17], mtop's first: q_order_17_is_open_first_at_1440.)
    # Since 2026-11-10 the chart reaches 2048 ([BOU]) and the columns say it: none before 1440 allows order 16, 1440
    # does, and mtop is 19, the order that no n up to 2048 allows, first left open at 2400, past the chart, as
    # mtop_at(19) finds it (mtop_at searches past NMAX, so no longer from 1026).
    assert max(c[1] for c in M['cols'][:1439]) == 15 and M['cols'][1439][1] >= 16, M['cols'][1439]
    assert M['mtop'] == 19 and M['mtopAt'] == [2400] == [mstar.mtop_at(19)], (M['mtop'], M['mtopAt'])
    tests = lambda n: min([mstar.two(n)] + [mstar.norm(n, p) for p in mstar.PRIMES if n % p])
    assert [mstar.norm(n, 5) for n in (1056, 1152, 1248)] == [15, 15, 15]
    assert tests(1344) >= 16 and mstar.chain_none(1344, 16, (5,), 'digits', mstar.MTOP_CAP)
    assert tests(1440) >= 16


def q_order_17_is_open_first_at_1440():
    # Replicata: mstar.js's mtop and mtopAt, mstar.MMAX, and mstar.mtop_at(16) and mstar.mtop_at(17) computed now.
    # Expectata (dreeves's README, 2026-11-04: "[M17] Let's add m=17 to the "smallest length known" table; no need for
    # much search, just whatever bounds we can find quickly"): the table runs through order MMAX = 17, and mtopAt gives
    # the least n past NMAX that the chart's own upper-bound tests leave open at each order from mtop = 16 to MMAX, as
    # mtop_at finds it: 1440 at both.  So every even n from 1026 to 1438 fails order 17 as it fails order 16, and at
    # 1440 two and norm allow order 17 (m*(1440) is 16 or 17).
    # Resultata before: mtopAt was 1440 alone, mtop's, and the table stopped at order 16.
    _, got = disk()
    M = got['m']
    # Since 2026-11-10 the chart reaches 2048 ([BOU]), so order 17 is one of its rows: no column before 1440 allows
    # order 16, and so none order 17, and 1440's upper bound is 17 (order 18 falls to the residue condition mod 7).
    assert mstar.MMAX == 17 and M['mtop'] == 19, (mstar.MMAX, M['mtop'])
    assert max(c[1] for c in M['cols'][:1439]) == 15 and M['cols'][1439][1] == 17, M['cols'][1439]
    assert min([mstar.two(1440)] + [mstar.norm(1440, p) for p in mstar.PRIMES if 1440 % p]) >= 17


def q_digits_order():
    # Replicata: mstar.digits(M) for the prime powers M up to 49 and for 6.
    # Expectata: a permutation of 0..M-1 in which, for M = p^k, the members of each class mod p^j (j < k) are
    # contiguous, the identity for a prime; AssertionError for 6.
    for M in (2, 3, 4, 5, 7, 8, 9, 11, 13, 16, 25, 27, 32, 49):
        p = min(q for q in range(2, M + 1) if M % q == 0)
        order_ = mstar.digits(M)
        assert sorted(order_) == list(range(M)) and (order_ == tuple(range(M))) == (p == M), M
        j = 1
        while p ** j < M:
            runs = [r % p ** j for r in order_]
            assert all(len(set(runs[i:i + M // p ** j])) == 1 for i in range(0, M, M // p ** j)), (M, j)
            j += 1
    expect_assertion(lambda: mstar.digits(6))


def q_residue_vectors_match_v5():
    # Replicata: mstar.residue_vectors (all of them), in each sweep of mstar.SWEEPS, and overnight_v5.admissible on
    # (n, order, M): (304, 9, 3), (512, 10, 3), (240, 11, 5), (240, 11, 7), (64, 6, 8), (48, 6, 9), (40, 5, 7),
    # (480, 13, 7); and through a parent: 304@9 mod 9 under each vector mod 3, 240@11 mod 8 under each vector mod 4,
    # 48@6 and 24@4 mod 25 under each vector mod 5, 40@5 mod 27 under each vector mod 9.
    # Expectata: the same vectors, in every sweep.
    def ours(n, m, M, parent, sweep):
        return sorted(mstar.residue_vectors(n, M, m, parent, mstar.Budget(10 ** 8), sweep))
    assert set(mstar.SWEEPS) == {'natural', 'digits'}
    for sweep in mstar.SWEEPS:
        for n, m, M in ((304, 9, 3), (512, 10, 3), (240, 11, 5), (240, 11, 7), (64, 6, 8), (48, 6, 9), (40, 5, 7),
                        (480, 13, 7)):
            assert ours(n, m, M, None, sweep) == v5_admissible(n, m, M, ()), (n, m, M, sweep)
        for n, m, P, M in ((304, 9, 3, 9), (240, 11, 4, 8), (48, 6, 5, 25), (24, 4, 5, 25), (40, 5, 9, 27)):
            for W in v5_admissible(n, m, P, ()):
                assert ours(n, m, M, (P, W), sweep) == v5_admissible(n, m, M, ((P, counts(n, P, W)),)), (n, M, W, sweep)


def q_residue_controls():
    # Replicata: (a) every claim (m, chain, sweep) of mstar.RESIDUE at a column settled at lo = m - 1 with an explicit
    # loWhy, but 512's (at order 9 the enumeration mod 27 under Thue-Morse's own vector mod 9 passes 10^8 nodes) and,
    # since 2026-10-26, when its example of order 10 settled it, 784's (at order 10 the enumeration mod 9 under the
    # example's own vector mod 3 reaches that vector only after 2,008,362 nodes, and mod 27 under its vector mod 9
    # passes 2*10^8 nodes: scratch/record-20261025/page2/control784.py), and
    # the sequence mstar builds for that column, at order m - 1; (b) every explicit sequence of length at most 32 and
    # order m >= 3, at order m, along every chain and sweep of mstar.RESIDUE.  Each time, the sequence's residue vector
    # at each level of the chain is looked for among the enumeration in the sweep under the sequence's own vector of the
    # level before, stopping when found, at most 2*10^6 nodes per level; but at 624 mod 25, since 2026-11-03, when its example of order 12 settled it, where at order 12 the
    # enumeration under the example's own vector mod 5 passes 2*10^8 nodes with no vector listed (measured that day), each row's tests are made along the example's own
    # vector alone (walk).
    # Expectata: found at every level (so an enumeration that missed admissible vectors would fail here); at least 15
    # controls of kind (a).
    _, got = disk()
    def control(a, m, chain, sweep):
        parent = None
        for M in chain:
            D = tuple(sum(a[r::M]) for r in range(M))
            budget = mstar.Budget(2 * 10 ** 6)
            assert any(v == D for v in mstar.residue_vectors(len(a), M, m, parent, budget, sweep)), (len(a), chain, M)
            parent = (M, D)
    def walk(a, m, M, P, sweep):                 # residue_vectors' tree, followed along a's own vector mod M under its own vector mod P: climb's and place's tests
        n, D, W = len(a), [sum(a[r::M]) for r in range(M)], [sum(a[r::P]) for r in range(P)]
        B, piv = mstar.basis(M, m, sweep, n < 2 ** m)
        cls = mstar.SWEEPS[sweep](M)
        s = [(n - r + M - 1) // M for r in cls]
        room = [sum(s[t] for t in range(i) if cls[t] % P == cls[i] % P) for i in range(M)]
        part, z, j = [0] * P, [0] * len(piv), len(piv) - 1
        for i in reversed(range(M)):
            di, q = D[cls[i]], cls[i] % P
            base = sum(B[i][c] * z[c] for c in range(j + 1, len(piv)))
            if j >= 0 and piv[j] == i:
                h = B[i][j]
                z[j] = (di - base) // h
                assert base + h * z[j] == di and -((s[i] + base) // h) <= z[j] <= (s[i] - base) // h, (n, M, i)
                j -= 1
            assert base + (B[i][j + 1] * z[j + 1] if j + 1 < len(piv) and piv[j + 1] == i else 0) == di, (n, M, i)
            rest = W[q] - part[q] - di
            assert abs(di) <= s[i] and (di - s[i]) % 2 == 0 and abs(rest) <= room[i] and (rest - room[i]) % 2 == 0, (n, M, i)
            part[q] += di
        assert part == W and j == -1, (n, M, part, j)
    done = 0
    for n, (m, chain, sweep) in mstar.RESIDUE.items():
        lo, hi, why, _ = got['m']['cols'][n - 1]
        # 1472 (since 2026-11-10, [BOU]): at order 11 the enumeration mod 9 under its join's own vector mod 3 passes
        # 2*10^6 nodes (measured that day); the other 27 claims past 1024 at settled columns find theirs within 18 nodes
        if [lo, hi] != [m - 1, m - 1] or why[0] not in EXPLICIT or n in (512, 784, 1472): continue
        assert mstar.order(mstar.build(n)) >= m - 1, n
        control(mstar.build(n), m - 1, chain[:1] if n == 624 else chain, sweep)
        if n == 624: walk(mstar.build(n), m - 1, 25, 5, sweep)
        done += 1
    assert done >= 15, done
    for chain, sweep in sorted(set((chain, sweep) for _, chain, sweep in mstar.RESIDUE.values())):
        for (n, label), a in mstar.explicit().items():
            if n <= 32 and mstar.order(a) >= 3: control(a, mstar.order(a), chain, sweep)


def q_residue_claims():
    # Replicata: every claim (m, chain, sweep) of mstar.RESIDUE at its n, enumerated through its chain to the end with
    # no cap, by mstar.chain_none; and, independently, by overnight_v5.admissible level by level (every vector of each
    # level under every vector of the level before), for every claim but 512's and 784's, both through (3, 9, 27), where
    # v5's sweep, 'natural', runs past 5*10^6 nodes (past 3 CPU-hours at 784): the two proofs in the page's 512 entry,
    # proof512.txt and proof512_short.txt (by hand), prove 512's, and 784's was re-proved on 2026-10-12 by two other
    # enumerations, scratch/lower24-design/onecell2/full27.py (none of the 1320 admissible vectors mod 9 has a refinement
    # mod 27) and judge/chain784.py.
    # Expectata: no admissible vector at the last modulus, by both; the claim lowers hi below two and norm (none is
    # dead weight); m - 1 >= lo (a claim at or below a known example's order would be a bug).
    _, got = disk()
    assert mstar.RESIDUE[512] == (10, (3, 9, 27), 'digits')
    for n, (m, chain, sweep) in mstar.RESIDUE.items():
        assert sweep in mstar.SWEEPS and mstar.chain_none(n, m, chain, sweep, 10 ** 8), (n, m, chain)
        level = v5_admissible(n, m, chain[0], ()) if n not in (512, 784) else []
        for P, M in zip(chain, chain[1:]):
            level = [D for W in level for D in v5_admissible(n, m, M, ((P, counts(n, P, W)),))]
        assert level == [], (n, m, chain)
        assert m - 1 < min([mstar.two(n)] + [mstar.norm(n, p) for p in mstar.PRIMES if n % p]), n
        assert m - 1 >= got['m']['cols'][n - 1][0], n


def box_in_plain_lattice(n, M, m):
    """Brute force: every vector D of the box (|D_r| <= size(M, r), D_r = size(M, r) mod 2, sum_r D_r = 0) that lies
    in the plain lattice L(M, m), tested exactly by overnight_v5.ExactSystem on its generators x^k (x-1)^m mod
    x^M - 1 (no factor x + 1 at any n); sorted."""
    poly = [1]
    for _ in range(m): poly = [a - b for a, b in zip([0] + poly, poly + [0])]          # (x-1)^m, lowest first
    G = [[0] * M for _ in range(M)]                       # G[r][k]: coordinate r of x^k (x-1)^m mod x^M - 1
    for k in range(M):
        for t, c in enumerate(poly): G[(t + k) % M][k] += c
    es = v5.ExactSystem(G)
    sizes = [len(range(r, n, M)) for r in range(M)]
    return sorted(D for D in itertools.product(*[range(-s, s + 1, 2) for s in sizes]) if sum(D) == 0 and es.solvable(D))


def q_plus_lattice_keeps_every_vector():
    # Replicata: small cases (n, M), M a prime power, at orders m = 1..7: the brute-force box vectors in the plain
    # lattice L(M, m) (box_in_plain_lattice), against mstar.residue_vectors in each sweep, which enumerates L+(M, m)
    # (the factor x + 1 more) when n < 2^m; for M >= 4 even, also under each such vector mod M/2 as a parent.  And
    # mstar.lattice(M, m, plus) with plus False and True, M in 2, 3, 4, 5, 8, 9, 16.
    # Expectata: the same vectors every time: the refinement never removes a vector that L(M, m) admits within the box.
    # The cases have teeth: at least 3 with M even and n < 2^m hold vectors, and at least 3 with n >= 2^m hold a vector
    # with D(-1) != 0, which L+ lacks (so the condition n < 2^m matters).  L+ = L for odd M; for even M, L+ is a proper
    # sublattice, of rank M - 2 against M - 1.
    held = lost = 0
    for n, M in ((8, 2), (8, 4), (12, 4), (12, 8), (16, 4), (16, 8), (16, 16), (10, 5), (12, 3), (14, 7), (18, 9),
                 (20, 4), (24, 8)):
        for m in range(1, 8):
            want = box_in_plain_lattice(n, M, m)
            under = {}                                    # want by its sums over the classes mod M/2
            for D in want: under.setdefault(tuple(sum(D[q::M // 2]) for q in range(M // 2)), []).append(D)
            parents = box_in_plain_lattice(n, M // 2, m) if M % 2 == 0 and M >= 4 else []
            for sweep in mstar.SWEEPS:
                got = sorted(mstar.residue_vectors(n, M, m, None, mstar.Budget(10 ** 7), sweep))
                assert got == want, (n, M, m, sweep, len(got), len(want))
                for W in parents:
                    got = sorted(mstar.residue_vectors(n, M, m, (M // 2, W), mstar.Budget(10 ** 7), sweep))
                    assert got == under.get(W, []), (n, M, m, W, sweep)
            held += M % 2 == 0 and n < 2 ** m and want != []
            lost += any(sum(d * (-1) ** r for r, d in enumerate(D)) for D in want) and M % 2 == 0
    assert held >= 3 and lost >= 3, (held, lost)
    for M in (2, 3, 4, 5, 8, 9, 16):
        for m in range(1, 8):
            A, B = mstar.lattice(M, m, False), mstar.lattice(M, m, True)
            assert A.shape[1] == M - 1 and B.shape[1] == M - 1 - (M % 2 == 0) and (A == B) == (M % 2 == 1), (M, m)


def q_720_order_15_is_ruled_out():
    # Replicata: column 720 of mstar.js (720 = 16 * 45); mstar.RESIDUE[720], enumerated by chain_none with a cap of 10
    # nodes; the generators x^k (x-1)^15 mod x^16 - 1 of L(16, 15), and the class sizes of 720 mod 16.
    # Expectata: hi = 14 with hiWhy ["residue", 16], from the claim (15, (16,), a sweep), which the enumeration settles
    # within the 10 nodes (it uses L+, as 720 < 2^15).  Independently, BGPW's Prop. 4.4 (q = 4) in residue form: every
    # generator is odd in every coordinate and is +-2^15 at x = -1, and every class has 45 elements, so in an
    # admissible D = sum_k z_k g_k every D_r is odd, so sum_k z_k is odd, so |D(-1)| = 2^15 |sum_k +-z_k| >= 2^15 > 720,
    # while |D(-1)| <= sum_r size(16, r) = 720: there is none.
    _, got = disk()
    lo, hi, _, why = got['m']['cols'][720 - 1]
    assert (hi, why) == (14, ['residue', 16]), (lo, hi, why)
    m, chain, sweep = mstar.RESIDUE[720]
    assert (m, chain) == (15, (16,)) and mstar.chain_none(720, m, chain, sweep, 10) is True
    poly = [1]
    for _ in range(15): poly = [a - b for a, b in zip([0] + poly, poly + [0])]
    G = [[poly[(r - k) % 16] for r in range(16)] for k in range(16)]          # G[k]: x^k (x-1)^15 mod x^16 - 1
    assert all(x % 2 for g in G for x in g) and {sum(x * (-1) ** r for r, x in enumerate(g)) for g in G} == {2 ** 15, -2 ** 15}
    assert {len(range(r, 720, 16)) for r in range(16)} == {45} and 2 ** 15 > 720


def q_chain_none_fails_loudly():
    # Replicata: chain_none on 240@11 mod 13 with a cap of 10 nodes, in each sweep; and on 432@11 mod 5 (where p432
    # lives).
    # Expectata: Capped (never a silent False or True on a partial enumeration); then False with a large cap.
    for sweep in mstar.SWEEPS:
        try:
            mstar.chain_none(240, 11, (13,), sweep, 10)
        except mstar.Capped:
            pass
        else:
            # TODO: error copy; says a capped enumeration did not raise Capped
            raise AssertionError('Claude: "a capped enumeration did not raise Capped"')
        assert mstar.chain_none(432, 11, (5,), sweep, 10 ** 7) is False


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
