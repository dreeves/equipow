#!/usr/bin/env python3
"""Quals for mstar.py, which computes the bounds on m*(n) behind the chart on index.html and writes mstar.js.
Run: python3 quals_mstar.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the resultata
(what happened instead).  Where a qual checks mstar.py's arithmetic it does so by an independent route: orders by
synthetic division instead of power sums, the two lemma by polynomial division over GF(2), the norm lemma by exact
determinants in Z[zeta], the residue enumeration against overnight_v5.admissible, and brute force against plain
enumeration of every sequence.  Quals marked "regression" pin numbers found earlier rather than stating a property.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, random, itertools, subprocess, tempfile, traceback, math
from functools import lru_cache
import sympy as sp
import mstar
import overnight_v5 as v5

HERE = os.path.dirname(os.path.abspath(__file__))
EXPLICIT = ('example', 'join', 'product', 'none')        # loWhy kinds backed by a sequence built here
CHECKED_HI = ('odd', 'two', 'norm', 'residue')            # hiWhy kinds proved here
# The gray columns of the user's count (multiples of 16 whose m* the sources here leave open)
USER_GRAY = (240, 288, 384, 432, 480) + tuple(range(528, 993, 16))


@lru_cache(maxsize=None)
def cols():
    """mstar.py's columns, computed once per run of the quals."""
    return mstar.columns()


@lru_cache(maxsize=None)
def disk():
    """mstar.js on disk, as the page's script sees it: run as a classic script by node in a fresh context; returns
    the file's text and {'keys': the enumerable globals it created, 'm': MSTAR}."""
    path = os.path.join(HERE, 'mstar.js')
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
    # cell's title), the codes and the sets with their orders; Table 2 has the paper's 39 entries and NEW 62 (17 until
    # 2026-10-12, when 2^33, 2^49, 2^57 and 2^67 joined the powers of 2 and every multiple of 16 up to 992 the rest, and
    # then 2^18, 2^41, 2^48, 2^61 and 2^71, once 560 reached order 10; 55 until 2026-10-17, when 2^17, 2^27, 2^34, 2^38,
    # 2^46, 2^52 and 2^66 joined them, once 800 reached order 11; 63 since 2026-10-20, when 240 joined them, settled
    # at 10 by the search overnight_v5.py and boxsplit.py made).
    src = mstar.page_sources(open(os.path.join(HERE, 'index.html'), encoding='utf-8').read())
    assert src['table2'] == mstar.TABLE2 and len(mstar.TABLE2) == 39
    assert src['new'] == mstar.NEW and len(mstar.NEW) == 63
    assert set(who for _, _, who in mstar.NEW.values()) == {'BGPW', 'Claude alone', 'Claude and BGPW'}
    assert [(m, h) for _, m, h in mstar.PAGE_CODES] == [(m, h) for m, h in src['codes']]
    assert sorted((m, n) for m, n, _ in src['sets']) == sorted(mstar.PAGE_SET_KEYS)


def q_page_parse_is_strict():
    # Replicata: index.html with one change each: Table 2's 136 -> 7 (the first value of its block); 528's "10–12" (class j) ->
    # "10–11"; 320's title BGPW -> Claude alone; the code C27D8C -> C27D8D; the first block table dropped.
    # Expectata: AssertionError from mstar.page_sources for each (the parse must equal the hand copy).
    html = open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()
    for old, new in (('<td class="j">10–12</td>', '<td class="j">10–11</td>'),
                     ("<td class=\"s\" title='BGPW'>320</td>", "<td class=\"s\" title='Claude alone'>320</td>"),
                     ('<code>C27D8C</code>', '<code>C27D8D</code>')):
        assert html.count(old) == 1, old
        expect_assertion(lambda: mstar.page_sources(html.replace(old, new)))
    i = html.index('<tr class="vals">', html.index('<td>136</td>'))
    j = html.index('</tr>', i)
    assert html[i:j].count('<td>6</td>') >= 1
    expect_assertion(lambda: mstar.page_sources(html[:i] + html[i:j].replace('<td>6</td>', '<td>7</td>', 1) + html[j:]))
    k = html.index('<table class="block">')
    expect_assertion(lambda: mstar.page_sources(html[:k] + html[html.index('</table>', k) + len('</table>'):]))


def q_explicit_sources_exact():
    # Replicata: mstar.explicit(), every explicit sequence with its label; and each source list on its own.
    # Expectata: every sequence is +-1 of its key's length; Thue-Morse tau_k has order k; BGPW's Table 4 pairs give
    # both lengths at their m; BGPW's Table 5, the page's codes and sets, and overnight_v5.EXAMPLES have exactly their
    # stated orders (by synthetic division); every EXAMPLES entry has a label; no label names Stan (BGPW includes him).
    ex = mstar.explicit()
    for (n, label), a in ex.items():
        assert len(a) == n and set(a) <= {1, -1}, (n, label)
        assert 'Stan' not in label, label
    for k in range(1, 10): assert exact_order_div(mstar.thue_morse(k)) == k
    for m, ns, h in mstar.BGPW_T4:
        for n in ns: assert exact_order_div(mstar.from_rp(h, m, n)) == m, (m, n)
    for m, n, h in mstar.BGPW_T5: assert exact_order_div(mstar.from_rp(h, m, n)) == m, (m, n)
    for label, m, h in mstar.PAGE_CODES: assert exact_order_div(v5.from_hex(h, m)) == m, label
    assert set(mstar.EXAMPLE_LABELS) == set(v5.EXAMPLES)
    for (n, m), h in v5.EXAMPLES.items(): assert exact_order_div(v5.from_hex(h, m)) == m, (n, m)


# ---------- the columns ----------

def q_schema():
    # Replicata: mstar.js on disk: its text, and the file run as a classic script by node.
    # Expectata: comment lines, then the single statement "const MSTAR = {...};" whose object is JSON, so the file
    # defines exactly one global (node sees no other); keys nmax, mtop, cols; nmax = 1000; 1000 columns, each
    # [lo, hi, loWhy, hiWhy] with integers 0 <= lo <= hi < mtop = max hi + 1 (so row mtop is red in every column);
    # every reason has its contract form; ["none"] and ["odd"] exactly at odd n.
    js, got = disk()
    body = ''.join(line for line in js.splitlines(True) if not line.startswith('//'))
    assert body.startswith('const MSTAR = ') and body.endswith('};\n') and body.count(';') == 1, body[:80]
    assert json.loads(body[len('const MSTAR = '):-2]) == got['m'] and got['keys'] == [], got['keys']
    M = got['m']
    assert list(M) == ['nmax', 'mtop', 'cols'] and M['nmax'] == 1000 == mstar.NMAX and len(M['cols']) == 1000
    T = M['mtop']
    assert type(T) is int and T == max(c[1] for c in M['cols']) + 1
    forms_lo = {'none': (), 'example': (str,), 'join': (int, int), 'product': (int, int), 'table2': (),
                'page': (str,)}
    forms_hi = {'odd': (), 'two': (), 'norm': (int,), 'residue': (int,), 'table2': (), 'page': (str,)}
    for n, c in enumerate(M['cols'], 1):
        assert len(c) == 4, n
        lo, hi, lw, hw = c
        assert type(lo) is int and type(hi) is int and 0 <= lo <= hi < T, (n, c)
        for why, forms in ((lw, forms_lo), (hw, forms_hi)):
            assert type(why) is list and why and why[0] in forms, (n, why)
            assert tuple(type(x) for x in why[1:]) == forms[why[0]], (n, why)
        assert (lw == ['none']) == (n % 2 == 1) == (hw == ['odd']), (n, c)
        assert lw[0] != 'page' or lw[1] in ('BGPW', 'Claude alone', 'Claude and BGPW'), (n, lw)
        assert hw[0] != 'page' or hw[1] in ('BGPW', 'Claude alone', 'Claude and BGPW'), (n, hw)


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
    for n in range(1, 1001):
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
    for ns, body in re.findall(r'<p class="entry"><i>n</i> = ([\d, ]+):(.*?)</li>', section, re.S):
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
    # norm(n, p); residue M with mstar.RESIDUE[n] = (hi + 1, a chain ending at M, a sweep); a citation equal to the
    # cited upper value; and hi is the least of all these candidates, the reason the first least in the order odd,
    # two, norm (by p), residue, table2, page (so a checked one wins every tie with a citation).
    _, got = disk()
    for n, (lo, hi, _, why) in enumerate(got['m']['cols'], 1):
        ranked = ([(0, ['odd'])] * (n % 2) + [(mstar.two(n), ['two'])]
                  + [(mstar.norm(n, p), ['norm', p]) for p in mstar.PRIMES if n % p]
                  + [(m - 1, ['residue', ch[-1]]) for k, (m, ch, _) in mstar.RESIDUE.items() if k == n]
                  + [(h, ['table2']) for k, (_, h) in mstar.TABLE2.items() if k == n and h is not None]
                  + [(h, ['page', who]) for k, (_, h, who) in mstar.NEW.items() if k == n and h is not None])
        assert hi == min(h for h, _ in ranked) and why == next(w for h, w in ranked if h == hi), (n, why, ranked)
        k = why[0]
        if k == 'odd': assert n % 2 and hi == 0
        if k == 'two': assert hi == 2 ** v2(n) - 1
        if k == 'norm': assert sp.isprime(why[1]) and n % why[1] and hi == mstar.norm(n, why[1])
        if k == 'residue': assert mstar.RESIDUE[n][0] == hi + 1 and mstar.RESIDUE[n][1][-1] == why[1], n
        if k == 'table2': assert mstar.TABLE2[n][1] == hi
        if k == 'page': assert mstar.NEW[n][1] == hi and mstar.NEW[n][2] == why[1]


def q_page_agrees():
    # Replicata: every entry of Table 2 and of the new-results block with n <= 1000, against mstar.js.
    # Expectata: an exact value v gives lo = hi = v; a range a..b (b open for "≥") contains [lo, hi].
    _, got = disk()
    cs = got['m']['cols']
    for table in (mstar.TABLE2, {n: v[:2] for n, v in mstar.NEW.items()}):
        for n, (a, b) in table.items():
            if n > 1000: continue
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
    # 200 on; every gray column (lo < hi) is among the user's 35 multiples of 16.
    _, got = disk()
    cs = got['m']['cols']
    for n, (lo, hi, _, _) in enumerate(cs, 1):
        if n % 2: assert lo == hi == 0, n
        elif n % 4 == 2: assert lo == hi == 1, n
        elif n % 8 == 4: assert lo == hi == (2 if n == 4 else 3), n
        elif n % 16 == 8: assert lo == hi and (n < 200 or lo == 7), n
        else: assert lo == hi or n in USER_GRAY, n


def q_gray_columns():
    # Replicata (regression): the gray columns of mstar.js.
    # Expectata: the user's 35 less 640, which the residue condition mod 3 settles at 10 (lo 10 from 2 x 320), less
    # 704 and 736, settled at 10 on 2026-10-12 (lo 10 from 2 x 352 and 2 x 368, mstar.FOUND's; hi by mod 3 and mod 9),
    # and less 560, settled at 10 the same day (lo 10 from the page's p560, found by a lattice search; hi by the norm
    # bound mod 3), and less 800, settled at 11 on 2026-10-17 (lo 11 from the page's p800, found by a lattice search;
    # hi by the norm bound mod 3), and less 240, settled at 10 on 2026-10-20 (lo 10 from the paper's Table 5 example; hi
    # by the certified search, overnight_v5.py and then boxsplit.py by 17 and 19, the page's new result).
    _, got = disk()
    gray = tuple(n for n, c in enumerate(got['m']['cols'], 1) if c[0] < c[1])
    assert gray == tuple(n for n in USER_GRAY if n not in (240, 560, 640, 704, 736, 800)), gray
    assert [got['m']['cols'][n - 1][:2] for n in (240, 560, 640, 704, 736, 800)] == [[10, 10]] * 5 + [[11, 11]]
    assert got['m']['cols'][240 - 1][2:] == [['example', 'BGPW Table 5'], ['page', 'Claude alone']]
    assert got['m']['cols'][560 - 1][2] == ['example', 'index.html p560']
    assert got['m']['cols'][800 - 1][2:] == [['example', 'index.html p800'], ['norm', 3]]


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
    # loWhy, but 512's (at order 9 the enumeration mod 27 under Thue-Morse's own vector mod 9 passes 10^8 nodes), and
    # the sequence mstar builds for that column, at order m - 1; (b) every explicit sequence of length at most 32 and
    # order m >= 3, at order m, along every chain and sweep of mstar.RESIDUE.  Each time, the sequence's residue vector
    # at each level of the chain is looked for among the enumeration in the sweep under the sequence's own vector of the
    # level before, stopping when found, at most 2*10^6 nodes per level.
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
    done = 0
    for n, (m, chain, sweep) in mstar.RESIDUE.items():
        lo, hi, why, _ = got['m']['cols'][n - 1]
        if [lo, hi] != [m - 1, m - 1] or why[0] not in EXPLICIT or n == 512: continue
        assert mstar.order(mstar.build(n)) >= m - 1, n
        control(mstar.build(n), m - 1, chain, sweep)
        done += 1
    assert done >= 15, done
    for chain, sweep in sorted(set((chain, sweep) for _, chain, sweep in mstar.RESIDUE.values())):
        for (n, label), a in mstar.explicit().items():
            if n <= 32 and mstar.order(a) >= 3: control(a, mstar.order(a), chain, sweep)


def q_residue_claims():
    # Replicata: every claim (m, chain, sweep) of mstar.RESIDUE at its n, enumerated through its chain to the end with
    # no cap, by mstar.chain_none; and, independently, by overnight_v5.admissible level by level (every vector of each
    # level under every vector of the level before), for every claim but 512's and 784's, both through (3, 9, 27), where
    # v5's sweep, 'natural', runs past 5*10^6 nodes (past 3 CPU-hours at 784): proof512.txt on the page proves 512's by
    # hand, and 784's was re-proved on 2026-10-12 by two other enumerations, scratch/lower24-design/onecell2/full27.py
    # (none of the 1320 admissible vectors mod 9 has a refinement mod 27) and judge/chain784.py.
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
