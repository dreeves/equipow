#!/usr/bin/env python3
"""Quals for index.html's account of BGPW's Symmetry Conjecture through order 11 (dreeves, 2026-11-06, of the result of
2026-11-03: on the page, "attributed to claude as usual"), the section of class symmetry: its codes, the upper bounds it
states, and its claim, which these quals recompute from the page's own sequences and the m*(n) chart's bounds.
Run: python3 -B quals/quals_symmetry.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
They read numbers and math, not wording (dreeves's rule, 2026-10-26: no qual pins prose).

Vocabulary, each term defined once here:
  conjecture   BGPW's Symmetry Conjecture (their §6), C(m) at n: if some sequence of length n has order m, then some
               (-1)^m-symmetric one does (f_(n-1-i) = (-1)^m f_i).
  period(m)    the least power of 2 above m: by BGPW's Divisibility (mstar's two lemma) a length of order m is a
               multiple of it.
  wrap         p v q v s p*, s = (-1)^m, p* the reversal of p, q empty or s-symmetric: s-symmetric, of order at least
               the least of p's and q's, and so (BGPW's Symmetry: an s-symmetric sequence's exact order k has
               (-1)^k = s) at least the bump of that least order, the least k' >= it with (-1)^k' = s.
  closure      the best orders that the page's sequences give, by joins (lo) and by wraps (sym, for each s), each
               length built from shorter ones, every one used built and its order and symmetry checked exactly.
  tail         A, the least multiple of period(m - 1) from which every multiple of it up to 2A has order m - 1; b, the
               least (-1)^m-symmetric length of order m that is an odd multiple of period(m - 1), or 0 when period(m)
               is twice period(m - 1); threshold 2A + b, from which wraps give every multiple of period(m).
  excluded     a multiple of period(m) below the threshold whose upper bound on the chart (mstar.js) is below m.
  own tests    the chart's own proofs of upper bounds: the two lemma, the norm lemma and its residue claims (mstar's
               two, norm and RESIDUE, which mstar.py reruns as it makes mstar.js).
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, time, shutil, tempfile, traceback, subprocess
sys.setrecursionlimit(10000)                  # built()'s recipes nest a join or a wrap per level
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, HERE)                                              # for its modules
import mstar
import quals_index as qi                      # read only: page, blank_comments, mstar_data, copy_page_dir, chrome, DATA, POW2
from math import cos, pi                      # by name: math, below, is the account's formulas
sys.path.insert(0, os.path.join(HERE, 'proofs'))
import symlarge                               # the objects of the proof of every sufficiently large length (2026-11-09)

SECTION = re.compile(r'<section class="symmetry" aria-labelledby="symmetry-title">(.*?)</section>', re.S)
CODE = re.compile(r'<code id="(\d+):(\d+)">([0-9A-F]+)</code>')
MAXM, N = 11, 1600                            # the account's orders, and the closure's lengths (past 1488, its last threshold)


def account(text=None):
    """The account's HTML, from index.html (or text) with its comments blanked: the one section of class symmetry."""
    found = SECTION.findall(qi.blank_comments(qi.page() if text is None else text))
    assert len(found) == 1, f'{len(found)} sections of class symmetry'
    return found[0]


def codes(sec):
    """[(n, m, hex)] for each code of the account, <code id="N:M">."""
    out = [(int(n), int(m), h) for n, m, h in CODE.findall(sec)]
    assert out and len(out) == sec.count('<code'), sec.count('<code')
    return out


def math(sec):
    """The account's math, each \\( ... \\) of it."""
    return re.findall(r'\\\((.*?)\\\)', sec, re.S)


def decode(h, m):
    """The paper's Table 5 code, decoded here on its own: each hex digit's four bits, the most significant first, 1 as
    +1 and 0 as -1, the left half; the right half the left half reversed, times (-1)^m."""
    left = [1 if int(d, 16) >> (3 - j) & 1 else -1 for d in h for j in range(4)]
    return left + [(-1) ** m * t for t in reversed(left)]


def order(a):
    """Exact order by power sums: the least k with sum_i a_i i^k != 0 (0^0 = 1)."""
    k, w = 0, [1] * len(a)
    while sum(x * y for x, y in zip(a, w)) == 0:
        k, w = k + 1, [x * i for i, x in enumerate(w)]
    return k


def order_div(a):
    """Exact order by synthetic division of sum_i a_i x^i by x - 1, the remainder being the sum of the coefficients."""
    c, k = list(a), 0
    while sum(c) == 0:
        acc, q = 0, [0] * (len(c) - 1)
        for i in range(len(c) - 1, 0, -1):
            acc += c[i]
            q[i - 1] = acc
        c, k = q, k + 1
    return k


def holds(a, m):
    """Whether a has order at least m: sum_i a_i i^k = 0 for every k < m (0^0 = 1)."""
    return all(sum(t * i ** k for i, t in enumerate(a)) == 0 for k in range(m))


def symmetry(a):
    """+1 if a is symmetric, -1 if antisymmetric, 0 if neither."""
    return next((s for s in (1, -1) if all(a[-1 - i] == s * t for i, t in enumerate(a))), 0)


def period(m): return 1 << m.bit_length()


def bump(k, s): return k if (-1) ** k == s else k + 1


def sources(text=None):
    """[(label, signs, order)]: Thue-Morse; the examples of BGPW's Tables 4 and 5 (mstar's copies, and the published
    Table 5's rows that overnight_v5.EXAMPLES holds); every code of the page (code blocks and sentences, the account's
    among them, decoded as page/codes.js decodes them); and the page's joins.  Each asserted of exactly its order."""
    text = qi.blank_comments(qi.page() if text is None else text)
    out = [(f'tau_{k}', mstar.thue_morse(k), k) for k in range(1, N.bit_length())]
    out += [(f'BGPW T4 {n}:{m}', mstar.from_rp(h, m, n), m) for m, ns, h in mstar.BGPW_T4 for n in ns]
    out += [(f'BGPW T5 {n}:{m}', mstar.from_rp(h, m, n), m) for m, n, h in mstar.BGPW_T5]
    out += [(f'BGPW T5 {n}:{m}', mstar.v5.from_hex(h, m), m) for (n, m), h in mstar.v5.EXAMPLES.items()
            if mstar.EXAMPLE_LABELS[n, m] == 'BGPW Table 5']
    coded = {f'{n}:{m}': decode(h, int(m)) for n, m, h in CODE.findall(text)}
    out += [(f'page {key}', a, int(key.split(':')[1])) for key, a in coded.items()]
    out += [(f'page join {ids}', [t for i in ids.split(' ') for t in coded[i]], int(m))
            for ids, m in re.findall(r'<span data-join="([^"]*)" data-order="(\d+)">', text)]
    bad = [(label, len(a), m) for label, a, m in out if order(a) != m]
    assert not bad, bad
    return out


def closure(src):
    """(lo, sym, built): lo[n] the best order of the sources and their joins at n (wraps included, a symmetric
    sequence being a sequence), sym[s][n] that of the s-symmetric ones by sources and wraps, -1 when none; and
    built(kind, n), the sequence behind lo (kind None) or sym (kind s), built from its recipe."""
    at = {}
    for i, (label, a, m) in enumerate(src): at.setdefault(len(a), []).append(i)
    lo, rlo = [0] * (N + 1), [('ones',)] * (N + 1)
    sym, rsym = {1: [-1] * (N + 1), -1: [-1] * (N + 1)}, {1: [None] * (N + 1), -1: [None] * (N + 1)}
    for n in range(1, N + 1):
        for s in (1, -1):
            cands = ([(src[i][2], ('src', i)) for i in at.get(n, []) if symmetry(src[i][1]) == s]
                     + [(bump(min(lo[(n - q) // 2], sym[s][q] if q else 10 ** 9), s), ('wrap', (n - q) // 2, q))
                        for q in range(n % 2, n - 1, 2) if q == 0 or sym[s][q] >= 0])
            sym[s][n], rsym[s][n] = max(cands, key=lambda c: c[0], default=(-1, None))
        cands = ([(0, ('ones',))] + [(src[i][2], ('src', i)) for i in at.get(n, [])]
                 + [(min(lo[a], lo[n - a]), ('join', a, n - a)) for a in range(1, n // 2 + 1)]
                 + [(sym[s][n], ('sym', s)) for s in (1, -1)])
        lo[n], rlo[n] = max(cands, key=lambda c: c[0])
    memo = {}
    def built(kind, n):
        if (kind, n) not in memo:
            r = rlo[n] if kind is None else rsym[kind][n]
            rule = {'ones': lambda: [1] * n, 'src': lambda: src[r[1]][1],
                    'join': lambda: built(None, r[1]) + built(None, r[2]), 'sym': lambda: built(r[1], n),
                    'wrap': lambda: built(None, r[1]) + (built(kind, r[2]) if r[2] else [])
                                    + [kind * t for t in reversed(built(None, r[1]))]}
            memo[kind, n] = rule[r[0]]()
        return memo[kind, n]
    return lo, sym, built


def own_hi(n):
    """The chart's own upper bound at n, without its citations: two, norm and the RESIDUE claim at n."""
    return min([mstar.two(n)] + [mstar.norm(n, p) for p in mstar.PRIMES if n % p]
               + [m - 1 for k, (m, _, _) in mstar.RESIDUE.items() if k == n])


def reduction(text=None):
    """For each m from 1 to MAXM: (A, b, threshold, uncovered, needed), uncovered the multiples of period(m) below the
    threshold with neither a (-1)^m-symmetric sequence of order m in the closure (each one built and checked) nor a
    chart bound below m, and needed the (n, hi) of the excluded ones whose bound is not the chart's own (own_hi);
    the sequences of order m - 1 from A to 2A, and every multiple of period(m) from the threshold to N, built by the
    closure too, and checked."""
    cols = qi.mstar_data()['cols']
    lo, sym, built = closure(sources(text))
    out = {}
    for m in range(1, MAXM + 1):
        s, g0, g = (-1) ** m, period(m - 1), period(m)
        A = next(A for A in range(g0, N // 2, g0) if all(lo[n] >= m - 1 for n in range(A, 2 * A, g0)))
        b = 0 if g == 2 * g0 else next(b for b in range(g0, N, 2 * g0) if sym[s][b] >= m)
        for n in range(A, 2 * A, g0):                    # the tail's p: a sequence of order m - 1 at each length
            a = built(None, n)
            assert len(a) == n and holds(a, m - 1), (m, n)
        uncovered, needed = [], []
        for n in range(g, N + 1, g):
            if sym[s][n] >= m:
                a = built(s, n)
                assert len(a) == n and symmetry(a) == s and holds(a, m), (m, n)
                continue
            hi = cols[n - 1][1] if n <= mstar.NMAX else own_hi(n)
            if hi >= m: uncovered.append(n)
            elif own_hi(n) >= m: needed.append((n, hi))
        assert all(n < 2 * A + b for n in uncovered), (m, A, b, uncovered)
        out[m] = (A, b, 2 * A + b, uncovered, needed)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The quals

def q_symmetry_codes_have_their_orders_and_symmetries():
    # Replicata: each code of the account, <code id="N:M">, decoded here on its own (decode) and by overnight_v5.from_hex,
    # as mstar.py reads the page's codes; and every id of the page.
    # Expectata (the review of 2026-11-03, scratch/symreview-20261103: "A write-up must publish" the sequences the claim
    # needs): the two decodings agree; each code has N/8 hex digits and its sequence N signs; its exact order is M by power
    # sums and by synthetic division (equal sums below M, unequal at M); it is (-1)^M-symmetric; N is a multiple of
    # period(M) (BGPW's Divisibility); and its id is no other element's.
    # Resultata before: the page had no section of class symmetry.
    page_ids = re.findall(r'\sid="([^"]+)"', qi.blank_comments(qi.page()))
    for n, m, h in codes(account()):
        a = decode(h, m)
        assert a == mstar.v5.from_hex(h, m) and 8 * len(h) == n == len(a), (n, m)
        assert order(a) == m == order_div(a), (n, m, order(a), order_div(a))
        assert symmetry(a) == (-1) ** m and n % period(m) == 0, (n, m)
        assert page_ids.count(f'{n}:{m}') == 1, (n, m)


def q_symmetry_bounds_agree_with_the_chart():
    # Replicata: the account's math: each upper bound m^*(N) \le K and each range m^*(N) \in \{a, b\} it states; its
    # codes; and mstar.js's column [lo, hi] at each N up to 1024, or past it mstar's own two and norm lemmas.
    # Expectata (the task of 2026-11-06: "the account's stated bounds agree with mstar.js where they overlap"): each
    # stated bound is the chart's hi at N, each range [lo, hi]; and each code's order M is at most lo at its length (no
    # code shows the chart a stale lower bound) and, past 1024, at most two and norm there.
    # Resultata before: the page had no section of class symmetry.
    sec, cols = account(), qi.mstar_data()['cols']
    said = math(sec)
    les = [(int(n), int(k)) for f in said for n, k in re.findall(r'm\^\*\((\d+)\) \\le (\d+)', f)]
    ins = [(int(n), int(a), int(b)) for f in said for n, a, b in re.findall(r'm\^\*\((\d+)\) \\in \\\{(\d+), (\d+)\\\}', f)]
    assert les and all(n <= mstar.NMAX for n, _ in les), les
    assert [(n, k) for n, k in les if cols[n - 1][1] != k] == [], [(n, k, cols[n - 1][:2]) for n, k in les]
    assert [(n, a, b) for n, a, b in ins if cols[n - 1][:2] != [a, b]] == [], ins
    within = [(n, m) for n, m, _ in codes(sec)
              if not (m <= cols[n - 1][0] if n <= mstar.NMAX else m <= own_hi(n))]
    assert within == [], within


def q_symmetry_conjecture_holds_through_order_11():
    # Replicata: the reduction (reduction()) from the page's own sequences, Thue-Morse and BGPW's Tables 4 and 5 (the
    # closure, by joins and wraps, every claim built and checked), and the chart's upper bounds; and the account's math:
    # its A = ..., b = ..., n \ge ... and its stated upper bounds.
    # Expectata (the claim of 2026-11-03, scratch/sym2-20261103, confirmed by the review, scratch/symreview-20261103):
    # for every m <= 11, every multiple of period(m) below the threshold 2A + b has a (-1)^m-symmetric sequence of order m
    # or a chart bound below m, but for 288 at m = 10, and none past it lacks one; the account's A, b and thresholds are
    # those of orders 9 to 11; and the upper bounds it states are exactly the ones the reduction takes beyond the chart's
    # own tests (own_hi), at their chart values.
    # Resultata before: the page had no section of class symmetry; the reduction alone left 560 and 592 at order 9, 432
    # and 848 at order 10, and 816, 1040, 1072, 1136, 1168, 1232 and 1264 at order 11 (q_symmetry_red_cases).
    # Spec change (Claude, 2026-11-08; until then this qual was q_symmetry_conjecture_holds_through_order_11_but_at_288_10):
    # no case uncovered, not even 288 at m = 10, since the chart's upper bound there is 9 by the form-tree proof
    # (quals_mstar's q_288_is_settled_at_9), a bound the account now states.
    sec = account()
    got = reduction()
    open_ = [(n, m) for m, (*_, uncovered, _) in got.items() for n in uncovered]
    assert open_ == [], open_
    said = math(sec)
    tails = [got[m] for m in range(9, MAXM + 1)]
    assert sorted({int(x) for f in said for x in re.findall(r'^A = (\d+)$', f.strip())}) == sorted({A for A, *_ in tails}), said
    assert sorted({int(x) for f in said for x in re.findall(r'^b = (\d+)$', f.strip())}) == sorted({b for _, b, *_ in tails}), said
    assert sorted({int(x) for f in said for x in re.findall(r'^n \\ge (\d+)$', f.strip())}) == sorted({t for _, _, t, *_ in tails}), said
    stated = {(int(n), int(k)) for f in said for n, k in re.findall(r'm\^\*\((\d+)\) \\le (\d+)', f)}
    needed = {bound for *_, needed in got.values() for bound in needed}
    assert stated == needed, (sorted(stated - needed), sorted(needed - stated))


def q_symmetry_red_cases():
    # Replicata: the reduction of q_symmetry_conjecture_holds_through_order_11 on the page with the account's codes left
    # out (each <code id> of the section dropped from the page's text): its positive control.
    # Expectata: the reduction finds the cases those codes fill and only those: each code's (n, m) uncovered without
    # it, so that no code of the account is idle, and the reduction can fail.
    # Spec change (Claude, 2026-11-08): no longer besides 288 at m = 10, which the chart's upper bound 9 covers since
    # the form-tree proof.
    text = qi.page()
    sec = account(text)
    keys = [(n, m) for n, m, _ in codes(sec)]
    bare = SECTION.sub(lambda x: CODE.sub('', x.group(0)), text)
    got = reduction(bare)
    open_ = sorted((n, m) for m, (*_, uncovered, _) in got.items() for n in uncovered)
    assert open_ == sorted(keys), (open_, keys)


# In the page, as it loads: for each code of the account, [its id, its computed hyphens, and its paragraph's computed
# text-align and hyphens], written into the DOM that --dump-dom returns
LOOK = """<script>
addEventListener('load', () => setTimeout(() => {
  const style = e => getComputedStyle(e);
  const out = [...document.querySelectorAll('section.symmetry code[id]')].map(c =>
    [c.id, style(c).hyphens, style(c.closest('p')).textAlign, style(c.closest('p')).hyphens]);
  document.body.append(Object.assign(document.createElement('pre'), {id: 'symmetry-out', textContent: JSON.stringify(out)}));
}, 500));
</script>
"""


def q_symmetry_code_lines_are_ragged_and_unhyphenated():
    # Replicata: index.html with page/, mstar.js and pow2.js beside it, in headless Chrome 1280 px wide (justified
    # prose, from 40rem up), as it loads: each code of the account, its computed hyphens, and its paragraph's computed
    # text-align and hyphens.
    # Expectata: as the code blocks' lines are (p.code: "the code lines ... stay ragged", page/style.css), each code's
    # line is ragged (text-align start) and nothing in it is hyphenated (hyphens manual), so that no hyphen is drawn
    # inside a code where it wraps, and its label is not spread across the line when the code wraps to the next.
    # Resultata before (2026-11-06, the account's screenshots): text-align justify and hyphens auto, and the drawn codes
    # had hyphens inside them ("…C92C92D-" at 1040), their labels spread across the line ("n = 1040,   m = 11:").
    d = tempfile.mkdtemp(prefix='symmetry-quals-')
    try:
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(qi.page().replace('</body>', LOOK + '</body>'))
        qi.copy_page_dir(d)
        for src, name in ((qi.DATA, 'mstar.js'), (qi.POW2, 'pow2.js')): shutil.copy(src, os.path.join(d, name))
        dom = qi.chrome(d, ['--window-size=1280,1000', '--virtual-time-budget=10000', '--dump-dom',
                            'file://' + os.path.join(d, 'index.html')])
    finally:
        shutil.rmtree(d)
    m = re.search(r'<pre id="symmetry-out">(.*?)</pre>', dom, re.S)
    assert m, dom[-2000:]
    looks = json.loads(html.unescape(m.group(1)))
    assert [i for i, *_ in looks] == [f'{n}:{k}' for n, k, _ in codes(account())], looks
    bad = [look for look in looks if look[1:] != ['manual', 'start', 'manual']]
    assert bad == [], bad


CELLS = re.compile(r'href="https://github\.com/dreeves/equipow/tree/main/searches/formtree/cells/(\d+)_(\d+)"')


def q_symmetry_cited_bounds_have_form_tree_proofs():
    # Replicata: the account's links to form-tree proofs of single cells (searches/formtree/cells/N_M), each linked
    # directory's top and verdicts in the repository, proofs/formtree.py assemble run on them, and mstar.js's columns.
    # Expectata (dreeves, 2026-11-09, of the form-tree proofs of the bounds the account cites: "you're getting all this
    # recorded in index.html?"): the account links a proof for exactly the cells 96:8, 144:9, 176:8, 272:9 and 752:11
    # (m*(96) <= 7, m*(144) <= 8, m*(176) <= 7, m*(272) <= 8 and m*(752) <= 10, until then taken from earlier work, from
    # BGPW's integer linear programs and from a meet in the middle with no certificate); each assembles to "VERIFIED: no
    # sequence of length N has order M"; every task in it was read by the Python checker as well as by fkernel (each
    # verdict's py is true); and each proves the chart's upper bound at N, M - 1.
    # Resultata before: the account linked no such proof, and the proofs were in scratch/certify-20261109/ alone.
    # Spec change (dreeves, 2026-11-09: "sounds good, certify 168 and 184 next"): also 152:7, 168:7 and 184:7, by
    # tops whose chain starts with modulus 4 (the parity coset pins f(-1) = +-128); 168 and 184 were BGPW's last two
    # integer-linear-program bounds, and 152's, which Berend and Golan proved by hand, gets a second proof.
    # Resultata before that: the account linked the five cells above alone.
    sec, cols = account(), qi.mstar_data()['cols']
    cells = sorted((int(n), int(m)) for n, m in set(CELLS.findall(sec)))
    assert cells == [(96, 8), (144, 9), (152, 7), (168, 7), (176, 8), (184, 7), (272, 9), (752, 11)], cells
    for n, m in cells:
        d = os.path.join(HERE, 'searches', 'formtree', 'cells', f'{n}_{m}')
        top, verdicts = os.path.join(d, f'top_{n}_{m}.json.gz'), os.path.join(d, 'verdicts.jsonl')
        out = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(HERE, 'proofs', 'formtree.py'), 'assemble', top, verdicts],
                             capture_output=True, text=True, timeout=600)
        assert f'VERIFIED: no sequence of length {n} has order {m}.' in out.stdout, (n, m, out.stdout[-300:], out.stderr[-300:])
        lines = [json.loads(line) for line in open(verdicts) if line.strip()]
        assert all(v['py'] is True for v in lines), (n, m, [v['start'] for v in lines if v['py'] is not True])
        assert cols[n - 1][1] == m - 1, (n, m, cols[n - 1])


# The theorem on every sufficiently large length (Fable 5.2, 2026-11-09): its proof, a fold of the account's block
# quote since 2026-11-10 (until then a page of its own, proofs/symlarge.html, which the quote linked), and the
# repository's files as the page links them.  quals_symlarge holds the fold itself.
FOLD = r'<details class="proof-exposition" id="symlarge">.*?</details>'
HUB = 'https://github.com/dreeves/equipow/blob/main/'


def large_lengths(sec):
    """The account's block quote that holds the proof of the theorem on every sufficiently large length, of which there
    is exactly one, without the proof's fold: the statement and what is said about it."""
    found = [q for q in re.findall(r'<blockquote class="claude">(.*?)</blockquote>', sec, re.S) if re.search(FOLD, q, re.S)]
    assert len(found) == 1, len(found)
    return re.sub(FOLD, '', found[0], flags=re.S)


def q_symmetry_large_lengths_holds_its_proof():
    # Replicata: the account's block quote that holds the proof's fold, and its links outside the fold.
    # Expectata (dreeves, 2026-11-09, of Fable 5.2's theorem that at each order m every sufficiently large length that
    # Divisibility allows has a (-1)^m-symmetric sequence of order m: "yes to putting it in index.html attributed
    # clearly to Fable 5.2"): one block quote of the account holds the proof, in its fold; and each of the quote's
    # links into github.com/dreeves/equipow names a file of the repository, of which there is at least one.
    # Spec change, 2026-11-10 (dreeves's README, [SYM]: "i think i'd rather have this symlarge proof in index.html,
    # but default collapsed"): until then this qual, q_symmetry_large_lengths_links_its_proof, asked that the quote link
    # the proof's page, proofs/symlarge.html, and that the page link back to the account's title.
    # Resultata before: the account had no such block quote, and the proof was in scratch/symlarge-20261109/ alone.
    quote = large_lengths(account())
    linked = re.findall('href="' + re.escape(HUB) + '([^"#]+)"', quote)
    assert linked and all(os.path.isfile(os.path.join(HERE, path)) for path in linked), linked


def q_symmetry_large_lengths_states_the_proof_s_numbers():
    # Replicata: that block quote's math outside the proof's fold: each bound n_0(M) \le 2^{E} it states, and each decimal number; and
    # proofs/symlarge.py: threshold_log2(M), the least L such that the conditions of the proof's section 5 hold at
    # every N >= 2^L, and count and gauss at order 5.
    # Expectata: each stated bound is the proof's, E = threshold_log2(M) + 1 (a length n = 2N with N >= 2^L); and each
    # decimal is one of three: 0.55 and 3.6, which bracket count / gauss at order 5 at every admissible N from 16 to 48
    # (n from 32 to 96) while 0.56 and 3.5 do not, and 0.39, cos(pi/16)^48 to two places.  It asks for none of them to
    # be there (a number dreeves cuts turns nothing red).
    # Resultata before: the account had no such block quote.
    said = math(large_lengths(account()))
    bounds = [(int(m), int(e)) for f in said for m, e in re.findall(r'n_0\((\d+)\) \\le 2\^\{(\d+)\}', f)]
    assert all(e == symlarge.threshold_log2(m) + 1 for m, e in bounds), bounds
    ratios = [symlarge.count(5, n) / symlarge.gauss(5, n) for n in range(16, 49, 4)]
    assert 0.55 <= min(ratios) < 0.56 and 3.5 < max(ratios) <= 3.6, ratios
    allowed = {'0.55', '3.6', f'{cos(pi / 16) ** 48:.2f}'}
    decimals = [x for f in said for x in re.findall(r'\d+\.\d+', f)]
    assert set(decimals) <= allowed, (decimals, allowed)


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
