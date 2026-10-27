#!/usr/bin/env python3
"""Quals for index.html's chart of m*(n) for the even n up to 1024.  Run: python3 -B quals_index.py [name ...]   (no
arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The static quals read index.html and mstar.js (and, for the changelog, index.html's git history and sourcery.html).  The
browser quals load a copy of index.html in headless Chrome (in an iframe of the width each configuration asks for,
since the window cannot be narrower than 500 px), in a temporary directory with a copy of mstar.js (or made-up data)
and of pow2.js (the data of the page's chart of powers of 2), with two scripts added:
EARLY, first in the head, which records errors and every string drawn on a canvas, and
HARNESS, last in the body, which drives the chart with synthetic events and posts what it saw to the host page, which
writes it into the DOM that --dump-dom returns.
The harness locates the chart only by its pixels, reads the view only through the readout (the cell under a
synthetic pointer) and finds the n labels by where their strings were drawn, so the quals hold the chart to what a
reader sees.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, html.parser, math, time, shutil, signal, datetime, zoneinfo, tempfile, threading, traceback, subprocess, contextlib, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
DATA = os.path.join(HERE, 'mstar.js')         # made by mstar.py; the chart's data
POW2 = os.path.join(HERE, 'pow2.js')          # made by pow2.py; the data of the chart of powers of 2, also on the page
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TOKENS = ('--exists', '--open', '--impossible')                    # the chart's three colors, in the order of kind
PROVENANCE = ('--claude', '--stan')
NMAX, MIN_SPAN = 1024, 12                     # 1000 until 2026-10-27, when the chart reached 1024
EVEN = list(range(2, NMAX + 1, 2))            # the chart's columns: an odd n has no partition at any m, so is left out
NCOL = len(EVEN)
STEPS = (2, 10, 20, 50, 100, 200, 500)        # the steps of the n labels: 1, 2, 5, 10, ... without the odd ones
RUNS = {}                                     # browser runs by configuration name, made once per process (see run)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the page

def page(): return open(INDEX, encoding='utf-8').read()


def section():
    """The chart's section: the HTML from <section class="mstar" to its </section>."""
    text = page()
    m = re.search(r'<section class="mstar".*?</section>', text, re.S)
    assert m, 'no <section class="mstar">'
    return m.group(0)


def theme_blocks():
    """The custom properties of the page's one theme block, :root, as a one-item list (dreeves, 2026-10-12: no dark
    mode, so no other theme block)."""
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    ms = list(re.finditer(r'\n:root \{(.*?)\n\s*\}', css, re.S))
    assert len(ms) == 1 and 'prefers-color-scheme' not in page() and 'data-theme' not in page()
    return [dict(re.findall(r'(--[\w-]+):\s*([^;]+);', ms[0].group(1)))]


def mstar_data():
    """MSTAR as the browser sees it: node runs mstar.js and prints MSTAR as JSON."""
    assert os.path.exists(DATA), DATA
    return mstar_of(open(DATA, encoding='utf-8').read())


def mstar_of(src):
    """MSTAR as the browser sees it from src, the text of a version of mstar.js."""
    p = subprocess.run(['node', '-e', src + '\nprocess.stdout.write(JSON.stringify(MSTAR))'], capture_output=True,
                       text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def pow2_data():
    """POW2 as the browser sees it: node runs pow2.js (beside index.html, made by pow2.py) and prints POW2 as JSON."""
    path = os.path.join(HERE, 'pow2.js')
    p = subprocess.run(['node', '-e', open(path, encoding='utf-8').read() + '\nprocess.stdout.write(JSON.stringify(POW2))'],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def table_entries():
    """(n, low, high) for every entry of the page's tables with n <= NMAX: Table 2's blocks and the new results."""
    return entries(re.search(r'<figure>.*?</figure>', page(), re.S).group(0))


def new_results():
    """(n, low, high) for every entry of the new results' table with n <= NMAX, as entries() reads them."""
    return entries(re.search(r'<div class="new-block">.*?</table>', page(), re.S).group(0))


def entries(fragment):
    """(n, low, high) for every entry with n <= NMAX of the tables of class block in fragment, as bounds() reads it."""
    out = []
    for table in re.findall(r'<table class="block">.*?</table>', fragment, re.S):
        ns = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', table, re.S).group(0))
        vs = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', table, re.S).group(0))
        assert len(ns) == len(vs) and ns, table
        for cell, v in zip(ns, vs):
            n = cell_n(cell)
            if n > NMAX: continue
            out.append((n, *bounds(v)))
    return out


def cell_n(cell):
    """The n of a cell of an n row: its digits, or 2^k for 2<sup>k</sup>."""
    m = re.fullmatch(r'(\d+)|2<sup>(\d+)</sup>', cell)
    assert m, cell
    return int(m.group(1)) if m.group(1) else 2 ** int(m.group(2))


def bounds(v):
    """(low, high) for a table's value v: an exact value v gives (v, v); 'a or b' and 'a–b' give (a, b); '≥ a' gives
    (a, inf)."""
    forms = ((r'(\d+)', lambda a: (a, a)), (r'(\d+) or (\d+)', lambda a, b: (a, b)),
             (r'(\d+)–(\d+)', lambda a, b: (a, b)), (r'≥ (\d+)', lambda a: (a, math.inf)))
    hits = [f(*map(int, m.groups())) for p, f in forms for m in [re.fullmatch(p, v)] if m]
    assert len(hits) == 1, v
    return hits[0]


def new_cells(text):
    """{n: (low, high)}, as bounds() reads them, for every entry of the new results' block (div.new-block) in text (a
    version of index.html) that has a provenance class: the rest copy Table 2's entries (2^3 to 2^8 until 2026-10-27,
    and since then every entry of Table 2 that stands, the block subsuming it).  A length the block shows twice, in its
    upper rows and as a power of 2 (since 2026-10-27, 8 to 1024), must be the same cell both times."""
    block = text[text.index('<div class="new-block">'):text.index('</figure>')]
    rows = re.findall(r'<tr class="ns">(.*?)</tr>\s*<tr class="vals">(.*?)</tr>', block, re.S)
    assert rows and len(rows) == block.count('<tr class="ns">') == block.count('<tr class="vals">'), block[:300]
    cells = []
    for ns, vals in rows:
        nn, vv = re.findall(r'<td[^>]*>(.*?)</td>', ns), re.findall(r'<td\b([^>]*)>(.*?)</td>', vals)
        assert nn and len(nn) == len(vv), (nn, vv)
        cells += [(cell_n(n), attrs, v) for n, (attrs, v) in zip(nn, vv)]
    assert all(len({(a, v) for m, a, v in cells if m == n}) == 1 for n, *_ in cells), cells
    return {n: bounds(v) for n, attrs, v in cells if re.search(r'class="\w+"', attrs)}


# The backfill of the changelog (dreeves, 2026-10-26: "can you backfill all the results that are new since the BGPW
# paper?") reaches this commit, the last of its day to change a result (2026-10-26 08:07, "More results, powers of 2").
BACKFILL = 'c496222'


def statement(b, a):
    """How a changelog entry states the change of a new result's bounds from b (None for a new entry) to a: both sides
    for a new entry, an exact one or one whose sides both moved; else the side that moved, None for the other; and an
    unknown side, a low of 0 or a high of inf, as None."""
    lo, hi = a
    one = b is not None and lo != hi and (b[0] == lo) != (b[1] == hi)       # exactly one side moved, and not exact
    return (None if (one and b[0] == lo) or lo == 0 else lo, None if (one and b[1] == hi) or hi == math.inf else hi)


def fold(state, said):
    """state ({n: (low, high)}, 0 and inf for unknown sides) with the statements said made: a side None keeps its bound."""
    old = lambda n: state.get(n, (0, math.inf))
    return state | {n: (old(n)[0] if lo is None else lo, old(n)[1] if hi is None else hi) for n, (lo, hi) in said.items()}


# The new results that the page began with, and 448's upper bound, as the claude.ai chat before the page (2026-10-03 to
# 06, in sourcery.html) first reported them (dreeves, 2026-10-26, dating the chat's first new result in his own entry:
# "2026-10-04: Claude Opus 5.5 gets first new result: m*(2^38) >= 39"): (the PDT day of the exchange's prompt, the
# exchange, words of its prompt or reply that report them, the statements they make).  Stan's list of blocks came in
# a prompt; 576 ∈ L₁₀, which the chat noted (p43), only doubles the paper's 288 ∈ L₉, so it is not among them.
CHAT = (('2026-10-04', 'p4', 'This shows 528 ∈ L₁₀', {528: (10, None)}),
        ('2026-10-04', 'p5', '432 ∈ L₁₁', {432: (11, None)}),
        ('2026-10-04', 'p5', '336 ∈ L₉ and 528 ∈ L₁₀', {336: (9, None)}),
        ('2026-10-04', 'p7', '{320, 9}, {352, 9}, {368, 9}, {400, 9}, {416, 9}, {432, 9}, {464, 9} {496, 9}',
         {n: (9, None) for n in (320, 352, 368, 400, 416, 464, 496)}),
        ('2026-10-04', 'p7', '320 and 352 cannot be in L₁₀', {320: (None, 9), 352: (None, 9)}),
        ('2026-10-04', 'p7', '2²⁴ ∈ L₂₅', {2 ** 24: (25, None)}),
        ('2026-10-05', 'p13', 'No, the order of 2⁹ is not 10, so m*(512) = 9', {512: (9, 9)}),
        ('2026-10-05', 'p15', 'If 3 ∤ n and n < 484, then n ∉ L₁₀; this covers 320, 352, 368, 400, 416, 448, 464',
         {n: (None, 9) for n in (368, 400, 416, 448, 464)}),
        ('2026-10-06', 'p23', 'I found one new positive result: 480 ∈ L₁₂', {480: (12, None)}),
        ('2026-10-06', 'p36', '496 = 9', {496: (None, 9)}))
FIRST = 'bf90205'      # the page's first commit (2026-10-07 11:08, "Initial commit")


def changes(before, after):
    """{n: statement} for the new results whose bounds differ from before to after (each {n: (low, high)})."""
    return {n: statement(before.get(n), a) for n, a in after.items() if before.get(n) != a}


def chat_days():
    """({date: (the bounds before the day, after it)}, the bounds after them all): CHAT's statements made day by day."""
    out, state = {}, {}
    for d in sorted({row[0] for row in CHAT}):
        after = state
        for said in (said for day, _, _, said in CHAT if day == d): after = fold(after, said)
        out[d] = (state, after)
        state = after
    return out, state


def exchanges():
    """{id: (PDT date of its prompt, its prompt and reply as text)} for the claude.ai chat's exchanges in sourcery.html,
    the text with its tags dropped, entities decoded and white space made single spaces."""
    text = open(os.path.join(HERE, 'sourcery.html'), encoding='utf-8').read()
    zone = zoneinfo.ZoneInfo('America/Los_Angeles')
    flat = lambda s: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s)))
    out = {}
    for pid, body in re.findall(r'<article class="exchange claudeai" id="(p\d+)"[^>]*>(.*?)</article>', text, re.S):
        t = datetime.datetime.fromisoformat(re.search(r'<time datetime="(\d{4}-[^"]+)"', body).group(1))
        out[pid] = (t.astimezone(zone).date().isoformat(), flat(body))
    return out


def git(*args): return subprocess.run(['git', '-C', HERE, *args], capture_output=True, text=True, check=True).stdout


def day_states(start, through=BACKFILL):
    """{date: (its last commit, the block's bounds before the day, after it)} for each day with commits of index.html up
    to and including through, the first day's before being start.  No result ever leaves the block."""
    log = git('log', '--reverse', '--format=%h %ad', '--date=format:%Y-%m-%d', through, '--', 'index.html')
    last = dict(reversed(line.split()) for line in log.split('\n') if line)     # date: the day's last commit
    out, before = {}, start
    for d, h in last.items():
        now = new_cells(git('show', f'{h}:index.html'))
        assert set(before) <= set(now), set(before) - set(now)
        out[d] = (h, before, now)
        before = now
    return out


# What the changelog lists (dreeves, 2026-10-26, of its first 112 statements: "if there's an excuse to trim it down, we
# should. it's overwhelming currently"; then "we obviously want 2^17:18 and 2^24:25 in the changelog"): the bounds that
# a new partition of that length, or a proof about that n, established; and each power of 2 whose low sets a threshold
# of Theorem 1, a new smallest k known to beat Thue-Morse by e (firsts()), stated by its low alone, as Theorem 1 states
# it.  Other bounds built from partitions of other lengths, by doubling, joining or multiplying them, are left to the
# table and the charts: a lower bound whose reason in the m*(n) chart is BUILT, along with the upper bound stated with
# it (that entry waits for a partition of its own), and every other power of 2 past NMAX.  The chat's statements (CHAT)
# are its reports of partitions and proofs, made before the chart.
BUILT = ('join', 'product')
FIRST_CHART = '917fe7f'    # mstar.js's first commit (2026-10-11 16:24, "New chart etc"), whose reasons serve the days before


def firsts(cells):
    """{e: the smallest k with low(2^k) - k >= e}, for e from 1 up, over the powers of 2 among cells ({n: (low, high)}):
    the thresholds of Theorem 1 as the block stood."""
    pows = {n.bit_length() - 1: lo for n, (lo, _) in cells.items() if n & (n - 1) == 0}
    top = max((lo - k for k, lo in pows.items()), default=0)
    return {e: min(k for k, lo in pows.items() if lo - k >= e) for e in range(1, top + 1)}


def records(before, after):
    """{2^k: (low, None)}: the powers of 2 whose low in after sets a threshold of Theorem 1 that before's did not."""
    b = firsts(before)
    return {2 ** k: (after[2 ** k][0], None) for e, k in firsts(after).items() if b.get(e) != k}


def listed(before, after, built):
    """The statements of the changes from before to after that the changelog lists: those for n up to NMAX that state
    no lower bound, or one that is not built (built(n) false), and the records() of the powers of 2."""
    return {n: (lo, hi) for n, (lo, hi) in changes(before, after).items()
            if n <= NMAX and (lo is None or not built(n))} | records(before, after)


def chat_listed():
    """{date: statements}: CHAT's days as the changelog lists them, none of their bounds built."""
    return {d: listed(b, a, lambda n: False) for d, (b, a) in chat_days()[0].items()}


def page_days(start, through=BACKFILL):
    """{date: statements}: day_states(start, through) as the changelog lists them, each day's built bounds by the m*(n)
    chart of its last commit, or of FIRST_CHART for the days before that."""
    begun = git('log', '-1', '--format=%ad', '--date=format:%Y-%m-%d', FIRST_CHART).strip()
    chart = lambda h: mstar_of(git('show', f'{h}:mstar.js'))['cols']
    out = {}
    for d, (h, before, after) in day_states(start, through).items():
        cols = chart(h if d >= begun else FIRST_CHART)
        out[d] = listed(before, after, lambda n: cols[n - 1][2][0] in BUILT)
    return out


# Noteworthy results, each an entry of its own though another entry shares its date (dreeves, 2026-10-26: "i think
# m*(2^9)=9 and other noteworthy results should be their own changelog line even though that means duplicating the
# date"), the newest first within a date: (date, n, its statement, why it is noteworthy)
NOTEWORTHY = (('2026-10-04', 2 ** 24, (25, None), 'the first power of 2 known to beat Thue-Morse, down from 2^38'),
              ('2026-10-04', 432, (11, None), 'the smallest length known with order 11, down from 480'),
              ('2026-10-05', 512, (9, 9), '2^9, the first power of 2 past the paper, does not beat Thue-Morse'),
              ('2026-10-06', 480, (12, None), 'the smallest length known with order 12, down from 960'),
              ('2026-10-07', 2 ** 51, (53, None), "beats the paper's Table 2 entry, Stong's m*(2^51) >= 52"),
              ('2026-10-10', 304, (8, 8), "settles the paper's Table 2 entry, 8 or 9"),
              ('2026-10-12', 2 ** 18, (19, None), 'the first power of 2 known to beat Thue-Morse, down from 2^24'),
              ('2026-10-17', 2 ** 17, (18, None), 'the first power of 2 known to beat Thue-Morse, down from 2^18'),
              ('2026-10-20', 384, (10, 10), 'with 240, settles a(10) = 432 of OEIS A323395'),
              ('2026-10-20', 240, (10, 10), "settles the paper's Table 2 entry, 10 or 11, and its open question"),
              ('2026-10-26', 2 ** 10, (11, 11), 'the first power of 2 known to beat Thue-Morse, down from 2^17, and the '
               'first that can, since m*(2^9) = 9'))


# ---------------------------------------------------------------------------------------------------------------------
# Color: the dataviz palette validator's arithmetic (OKLab ΔE ×100, Machado-Oliveira-Fernandes 2009 at severity 1.0)

MACHADO = {'protan': ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
           'deutan': ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881))}


def linear(h):
    assert re.fullmatch(r'#[0-9a-f]{6}', h), h
    return [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
            for c in (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))]


def oklab(rgb):
    r, g, b = rgb
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
                                                              0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
                                                              0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def seen(h, kind):
    rgb = linear(h)
    return rgb if kind == 'normal' else [min(1, max(0, sum(a * c for a, c in zip(row, rgb)))) for row in MACHADO[kind]]


def delta_e(h1, h2, kind='normal'): return 100 * math.dist(oklab(seen(h1, kind)), oklab(seen(h2, kind)))


def worst_cvd(colors):
    """The validator's worst all-pairs CVD pair: (ΔE, kind), the minimum over protan and deutan."""
    return min((delta_e(a, b, k), k) for i, a in enumerate(colors) for b in colors[i + 1:] for k in MACHADO)


def worst_normal(colors): return min(delta_e(a, b) for i, a in enumerate(colors) for b in colors[i + 1:])


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

EARLY = r"""<script>
window.__errors = []; window.__texts = []; window.__fills = [];
addEventListener('error', e => {
  if (e instanceof ErrorEvent) __errors.push('error: ' + e.message);
  else if (e.target && e.target.tagName === 'SCRIPT') __errors.push('script failed to load: ' + e.target.src);
}, true);
addEventListener('unhandledrejection', e => __errors.push('rejection: ' + e.reason));
for (const k of ['error', 'warn']) {
  const f = console[k].bind(console);
  console[k] = (...a) => { __errors.push(k + ': ' + a.map(String).join(' ')); f(...a); };
}
const __fillText = CanvasRenderingContext2D.prototype.fillText;
CanvasRenderingContext2D.prototype.fillText = function (t, x, y, ...rest) {
  __texts.push(String(t)); __fills.push([String(t), x, y]); return __fillText.call(this, t, x, y, ...rest); };
Element.prototype.setPointerCapture = function () {};     // synthetic pointers are never active, so capture would throw
</script>
"""

HARNESS = r"""<script>
(() => {
const OPTS = __OPTS__;
function battery(R) {
  const cv = document.getElementById('mstar-chart'), ro = document.getElementById('mstar-readout');
  const reset = document.getElementById('mstar-reset'), rect = () => cv.getBoundingClientRect();
  R.readout0 = ro.textContent;
  R.canvasCss = [rect().width, rect().height];
  R.canvasDev = [cv.width, cv.height];
  R.dpr = devicePixelRatio; R.innerW = innerWidth; R.scrollW = document.documentElement.scrollWidth;
  const main = document.querySelector('main'), ms = getComputedStyle(main);
  R.mainContentW = main.clientWidth - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight);
  R.touchAction = getComputedStyle(cv).touchAction;
  R.nTextBottoms = [...document.querySelectorAll('.new-block tr.ns')].map(tr => [...tr.querySelectorAll('td')].map(td => {
    const t = [...td.childNodes].find(x => x.nodeType === 3 && x.textContent.trim()), r = document.createRange();
    r.selectNodeContents(t); return r.getBoundingClientRect().bottom; }));
  if (cv.height === 0) return;
  const tok = name => getComputedStyle(cv).getPropertyValue(name).trim().toLowerCase();
  const C = {exists: tok('--exists'), open: tok('--open'), impossible: tok('--impossible'), paper: tok('--paper'), ink: tok('--ink'),
             record: tok('--record')};
  R.tokens = C;
  const dpr = devicePixelRatio, ctx = cv.getContext('2d'), T = MSTAR.mtop, cols = MSTAR.cols;
  const colorOf = (n, m) => m <= cols[n - 1][0] ? C.exists : m <= cols[n - 1][1] ? C.open : C.impossible;
  // The cells ringed in gold (dreeves, 2026-10-19): for each order m, the least n known to reach m when no smaller n's
  // upper bound allows m.  A ring spoils the pixels around its cell, in its row and the row above, so the generic
  // checks pass over the columns next to it there, and checkPixels checks the ring itself (RECS, ringChecks, ringBad).
  const least = test => cols.findIndex(test) + 1;
  const RECS = [];
  for (let m = 1; m <= T; m++) { const n = least(c => c[0] >= m); if (n && n === least(c => c[1] >= m)) RECS.push([n, m]); }
  R.records = RECS; R.ringChecks = 0; R.ringBad = []; R.ringed = {}; R.rowOneSkips = 0;
  const nearRing = (j, m) => RECS.some(([n, r]) => Math.abs(j - n / 2) <= 1 && (m === r || m === r + 1));
  let img = null;
  const snap = () => { img = ctx.getImageData(0, 0, cv.width, cv.height); };
  const pix = (X, Y) => { const i = (Y * img.width + X) * 4, d = img.data;
    return '#' + [d[i], d[i + 1], d[i + 2]].map(v => v.toString(16).padStart(2, '0')).join(''); };
  // Layout from pixels: the rows are the runs of non-paper pixels down the middle device column, from the top (the
  // first T of them; the axis may add more below), and the plot spans the run of impossible pixels across row T.
  snap();
  const runs = [];
  for (let Y = 0, s = -1, X = cv.width >> 1; Y <= cv.height; Y++) {
    const on = Y < cv.height && pix(X, Y) !== C.paper;
    if (on && s < 0) s = Y;
    if (!on && s >= 0) { runs.push([s, Y]); s = -1; }
  }
  const rows = runs.slice(0, T);
  R.rows = rows;
  const rowY = m => (rows[T - m][0] + rows[T - m][1]) / 2;        // device px, the middle of row m
  const Yt = Math.floor(rowY(T));
  let PL = 0, PR = cv.width - 1;
  while (pix(PL, Yt) !== C.impossible) PL++;
  while (pix(PR, Yt) !== C.impossible) PR--;
  PR++;
  R.plot = [PL, PR];
  const L = PL / dpr, W = (PR - PL) / dpr, yProbe = rowY(1) / dpr;      // CSS px
  const ptr = (type, x, y, o) => { const r = rect(), e = new PointerEvent(type, {clientX: r.left + x, clientY: r.top + y,
    pointerId: 1, pointerType: 'mouse', buttons: 0, bubbles: true, cancelable: true, ...o}); cv.dispatchEvent(e); return e; };
  const cellOf = t => { const m = t.match(/^n = (\d+), m = (\d+) · /); return m ? [+m[1], +m[2]] : null; };
  // Every hover's readout is counted, and kept if it reports an odd n (no column is an odd n).
  const hover = (x, y) => { ptr('pointermove', x, y, {}); const t = ro.textContent, c = cellOf(t);
    R.readouts++; if (c && c[0] % 2) R.oddReadouts.push(t); return t; };
  // Column j is n = 2j: jAt is the column read out at CSS x in row 1.
  const jAt = x => { const c = cellOf(hover(x, yProbe)); if (!c) throw new Error('no cell read out at ' + x); return c[0] / 2; };
  function view() {        // the visible u-interval [u0, u0 + span), column j spanning u from j - 1 to j
    let a = L + 0.25, b = Math.min(L + 160, L + W - 0.25);
    const j1 = jAt(a);
    if (!(jAt(b) > j1)) throw new Error('no column boundary near the left edge');
    for (let i = 0; i < 26; i++) { const c = (a + b) / 2; if (jAt(c) > j1) b = c; else a = c; }
    const x1 = b;                                   // u = j1 here
    let a2 = Math.max(L + 0.25, L + W - 160), b2 = L + W - 0.25;
    const j2 = jAt(b2);
    if (!(jAt(a2) < j2)) throw new Error('no column boundary near the right edge');
    for (let i = 0; i < 26; i++) { const c = (a2 + b2) / 2; if (jAt(c) < j2) a2 = c; else b2 = c; }
    const x2 = b2;                                  // u = j2 - 1 here
    const slope = (j2 - 1 - j1) / (x2 - x1);        // u per CSS px
    return {u0: j1 - (x1 - L) * slope, span: slope * W};
  }
  const first = v => Math.ceil(v.u0 - 1e-3) + 1, final = v => Math.floor(v.u0 + v.span + 1e-3);   // whole columns in view
  const middleX = (v, j) => L + (j - 0.5 - v.u0) * W / v.span;                                      // CSS px
  function checkPixels(v) {    // every column at least 3 device px wide: its middle pixel has its color in every row,
    const k = v.span / (PR - PL);   // and the pixel just below each row is paper.  The outline of the cell read out
    if (1 / k < 3) return;          // spoils its neighbors, so the view is checked twice: outlining its first column,
    const [a, b] = [first(v), final(v)];   // then its last, and checking the columns 2 or more away from it.
    for (const [o, from, to] of [[a, a + 2, b], [b, a, b - 2]]) {
      hover(middleX(v, o), rowY(T) / dpr);
      snap();
      for (let j = from; j <= to; j++) {
        const X = PL + Math.floor((j - 0.5 - v.u0) / k);
        for (let m = 1; m <= T; m++) {
          if (nearRing(j, m)) continue;
          const want = colorOf(2 * j, m), got = pix(X, Math.floor(rowY(m))), gap = pix(X, rows[T - m][1]);
          R.pixelChecks++;
          if (got !== want || gap !== C.paper) R.pixelBad.push([2 * j, m, want, got, gap]);
        }
        R.pixelColumns[2 * j] = 1;
      }
      for (const [n, r] of RECS) {    // a ringed cell in this pass: gold just outside its left and right, and below it
        const j = n / 2;
        if (j < from || j > to) continue;
        const Y = Math.floor(rowY(r)), x0 = PL + (j - 1 - v.u0) / k, x1 = PL + (j - v.u0) / k;
        const got = [pix(Math.floor(x0 - dpr), Y), pix(Math.floor(x1 + dpr), Y), pix(PL + Math.floor((j - 0.5 - v.u0) / k), rows[T - r][1])];
        R.ringChecks++; R.ringed[n] = 1;
        if (got.some(c => c !== C.record)) R.ringBad.push([n, r, got]);
      }
    }
  }
  // Row 1 is exists in every even column and impossible in every odd one, so with no odd column drawn, even mixed into a
  // pixel, every pixel of row 1 is exists.  The outline of the cell read out goes to row T first.
  function checkRowOne(v, i) {     // but where a ring of row 1 runs, a device px either side (rowOneSkips)
    hover(middleX(v, first(v)), rowY(T) / dpr);
    snap();
    const k = v.span / (PR - PL), bands = RECS.filter(([, r]) => r === 1).flatMap(([n]) => {
      const x0 = PL + (n / 2 - 1 - v.u0) / k, x1 = PL + (n / 2 - v.u0) / k;
      return [[x0 - 2 * dpr - 1, x0 + 1], [x1 - 1, x1 + 2 * dpr + 1]];
    });
    for (let X = PL, Y = Math.floor(rowY(1)); X < PR; X++) {
      if (bands.some(([a, b]) => a <= X && X <= b)) { R.rowOneSkips++; continue; }
      R.rowOneChecks++;
      if (pix(X, Y) !== C.exists) R.rowOneBad.push([i, X, pix(X, Y)]);
    }
  }
  // The n labels of one draw (the one a change of the cell read out makes): the strings drawn below the rows and right
  // of the plot's left edge, as [string, x in device px].
  function labels(v) {
    hover(middleX(v, first(v)), rowY(T) / dpr);
    __fills.length = 0;
    hover(middleX(v, first(v)), rowY(T - 1) / dpr);
    return {v, labels: __fills.filter(([t, x, y]) => y > rows[T - 1][1] && x >= PL - 1).map(([t, x]) => [t, x])};
  }
  function sampleHovers(v, every) {    // hover the middle of cells lo, lo + 1 and hi + 1 of every every-th column
    for (let j = first(v); j <= final(v); j += every) {
      const n = 2 * j, [lo, hi] = cols[n - 1];
      for (const m of new Set([lo, lo + 1, hi + 1])) {
        if (m < 1 || m > T) continue;
        R.hovers.push([n, m, hover(middleX(v, j), rowY(m) / dpr)]);
        const {backgroundColor, boxShadow} = getComputedStyle(ro.querySelector('.swatch'));
        R.swatches.push([n, m, backgroundColor, boxShadow]);
      }
    }
  }
  const key = (k, o) => { const e = new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true, ...o});
    cv.dispatchEvent(e); return e.defaultPrevented; };
  // Chrome makes a synthetic wheel event's clientX a whole number, so wheel returns where the pointer really was, as a
  // fraction of the plot's width, with whether the default was prevented.
  const wheel = (x, o) => { const r = rect(), e = new WheelEvent('wheel', {clientX: r.left + x, clientY: r.top + yProbe,
    deltaMode: 0, bubbles: true, cancelable: true, ...o}); cv.dispatchEvent(e); return [e.defaultPrevented, (e.clientX - r.left - L) / W]; };
  const touch = (type, id, x) => ptr(type, x, yProbe, {pointerId: id, pointerType: 'touch', isPrimary: false,
    buttons: type === 'pointerup' ? 0 : 1});
  const gesture = (type, scale, x) => { const r = rect(), e = new Event(type, {bubbles: true, cancelable: true});
    Object.assign(e, {scale, clientX: r.left + x, clientY: r.top + yProbe}); cv.dispatchEvent(e); return e.defaultPrevented; };
  const step = (name, f) => { const a = view(), x = f(), b = view(); R.steps[name] = {a, b, x, disabled: disabled()}; };

  // The zoom buttons: whether each is disabled (null if it is missing), and how each looks, at load.
  const zin = document.getElementById('mstar-zoom-in'), zout = document.getElementById('mstar-zoom-out');
  const disabled = () => [zin, zout].map(b => b && b.disabled);
  const look = b => b && (({opacity, display, visibility}) => ({opacity: +opacity, display, visibility,
    size: [b.getBoundingClientRect().width, b.getBoundingClientRect().height]}))(getComputedStyle(b));
  R.disabled0 = disabled();
  R.looks0 = [zin, zout].map(look);
  R.readouts = 0; R.oddReadouts = [];
  R.views = [view()];
  R.hovers = []; R.swatches = []; R.pixelChecks = 0; R.pixelBad = []; R.pixelColumns = {}; R.steps = {}; R.rowOneChecks = 0; R.rowOneBad = [];
  R.labelDraws = [labels(R.views[0])];
  checkRowOne(R.views[0], 0);
  // A hover at the middle of every device px across row 1 of the full view: the n read out, left to right, each once.
  R.across = [];
  for (let X = PL; X < PR; X++) { const c = cellOf(hover((X + 0.5) / dpr, yProbe)); R.across.push(c && c[0]); }
  R.across = R.across.filter((n, i, a) => i === 0 || n !== a[i - 1]);
  sampleHovers(R.views[0], OPTS.hoverEvery);
  // Sweep: zoom in, go to the left end, and step right by 3/4 of a view at a time to the right end.
  cv.focus();
  for (let i = 0; i < 7; i++) key('+');
  for (let i = 0; i < 300; i++) key('ArrowLeft');
  for (let guard = 0; guard < 100; guard++) {
    const v = view();
    R.views.push(v);
    sampleHovers(v, OPTS.hoverEvery);
    checkPixels(v);
    checkRowOne(v, R.views.length - 1);
    R.labelDraws.push(labels(v));
    if (v.u0 + v.span > NCOL - 1e-6) break;
    for (let i = 0; i < 6; i++) key('ArrowRight');
  }
  R.pixelColumns = Object.keys(R.pixelColumns).map(Number).sort((a, b) => a - b);
  // The cell read out is outlined in ink, just outside it.
  reset.click();
  for (let i = 0; i < 5; i++) key('+');
  {
    const v = view(), k = v.span / (PR - PL), j = Math.round(v.u0 + v.span / 2), n = 2 * j, m = 2;
    R.outlineText = hover((PL + (j - 0.5 - v.u0) / k) / dpr, rowY(m) / dpr);
    snap();
    R.outline = {n, m, want: colorOf(n, m), ink: C.ink, middle: pix(PL + Math.floor((j - 0.5 - v.u0) / k), Math.floor(rowY(m))),
                 left: pix(Math.floor(PL + (j - 1 - v.u0) / k - dpr), Math.floor(rowY(m))),
                 right: pix(Math.floor(PL + (j - v.u0) / k + dpr), Math.floor(rowY(m)))};
  }
  // Interactions, each from a view zoomed in 3 steps about the middle unless said otherwise.
  const zoomed = () => { reset.click(); for (let i = 0; i < 3; i++) key('+'); };
  zoomed(); step('right', () => key('ArrowRight'));
  zoomed(); step('left', () => key('ArrowLeft'));
  zoomed(); step('plus', () => key('+'));
  zoomed(); step('equals', () => key('='));
  zoomed(); step('minus', () => key('-'));
  zoomed(); step('down', () => key('ArrowDown'));
  zoomed(); step('ctrlPlus', () => key('+', {ctrlKey: true}));
  zoomed(); step('metaRight', () => key('ArrowRight', {metaKey: true}));
  zoomed(); step('ctrlWheel', () => wheel(L + 0.3 * W, {deltaY: -100, ctrlKey: true}));
  zoomed(); step('metaWheel', () => wheel(L + 0.3 * W, {deltaY: 50, metaKey: true}));
  zoomed(); step('lineWheel', () => wheel(L + 0.3 * W, {deltaY: -3, deltaMode: 1, ctrlKey: true}));
  zoomed(); step('sideWheel', () => wheel(L + 0.3 * W, {deltaX: 60, deltaY: 5}));
  zoomed(); step('upWheel', () => wheel(L + 0.3 * W, {deltaY: 100, deltaX: 2}));
  zoomed(); step('drag', () => { ptr('pointerdown', L + 0.6 * W, yProbe, {buttons: 1});
    ptr('pointermove', L + 0.6 * W - 100, yProbe, {buttons: 1}); ptr('pointerup', L + 0.6 * W - 100, yProbe, {}); return 100; });
  zoomed(); step('pinch', () => { touch('pointerdown', 11, L + 0.4 * W); touch('pointerdown', 12, L + 0.6 * W);
    touch('pointermove', 11, L + 0.3 * W); touch('pointermove', 12, L + 0.7 * W);
    touch('pointerup', 11, L + 0.3 * W); touch('pointerup', 12, L + 0.7 * W); return [0.2 * W, 0.4 * W, 0.5 * W]; });
  zoomed(); step('swipe', () => { touch('pointerdown', 13, L + 0.5 * W); touch('pointermove', 13, L + 0.3 * W);
    touch('pointerup', 13, L + 0.3 * W); return 0.2 * W; });
  zoomed(); step('gesture', () => [gesture('gesturestart', 1, L + 0.25 * W), gesture('gesturechange', 2, L + 0.25 * W),
    gesture('gestureend', 2, L + 0.25 * W), 0.25 * W]);
  zoomed(); step('gestureWhileTouching', () => { touch('pointerdown', 21, L + 0.5 * W);
    const p = [gesture('gesturestart', 1, L + 0.25 * W), gesture('gesturechange', 2, L + 0.25 * W)];
    touch('pointerup', 21, L + 0.5 * W); return p; });
  zoomed(); step('reset', () => { key('ArrowRight'); key('+'); reset.click(); });
  zoomed(); step('zoomInFar', () => { for (let i = 0; i < 40; i++) key('+'); });
  R.labelDraws.push(labels(R.steps.zoomInFar.b));
  zoomed(); step('zoomOutFar', () => { for (let i = 0; i < 40; i++) key('-'); });
  zoomed(); step('panFar', () => { for (let i = 0; i < 300; i++) key('ArrowRight'); });
  zoomed(); step('wheelOutFar', () => wheel(L + 0.5 * W, {deltaY: 5000, ctrlKey: true})[0]);
  // A tap reads out the cell under it, and so does a mouse click.
  zoomed();
  {
    const v = view(), x = L + 0.37 * W, k = v.span / W;
    hover(L + 0.8 * W, rowY(5) / dpr);
    touch('pointerdown', 14, x); touch('pointerup', 14, x);
    R.tap = {want: [2 * (Math.floor(v.u0 + (x - L) * k) + 1), 1], text: ro.textContent};
    ptr('pointerup', L + 0.2 * W, yProbe, {pointerId: 99});        // an up with no down: nothing happens
    R.tap.after = ro.textContent;
    const x2 = L + 0.63 * W;
    hover(L + 0.8 * W, rowY(5) / dpr);
    ptr('pointerdown', x2, yProbe, {buttons: 1}); ptr('pointerup', x2, yProbe, {});
    R.click = {want: [2 * (Math.floor(v.u0 + (x2 - L) * k) + 1), 1], text: ro.textContent};
  }
  // The zoom buttons: a click of each from a view zoomed in 3 steps; then, from the full view, clicks of + until it is
  // disabled and then of − until it is disabled, the view measured after each.
  try {
    zoomed(); step('zoomInButton', () => zin.click());
    zoomed(); step('zoomOutButton', () => zout.click());
    reset.click();
    R.clicks = [['start', view(), disabled()]];
    for (const [b, kind] of [[zin, 'in'], [zout, 'out']]) {
      for (let i = 0; i < 40 && !b.disabled; i++) { b.click(); R.clicks.push([kind, view(), disabled()]); }
    }
  } catch (e) { R.buttonsError = String(e && e.stack || e); }
}
const R = {errors: window.__errors, opts: OPTS};
const go = () => {
  try { battery(R); } catch (e) { R.harnessError = String(e && e.stack || e); }
  R.texts = [...new Set(window.__texts)];
  parent.postMessage(JSON.stringify(R), '*');
};
const NCOL = __NCOL__;                                             // the columns: n = 2, 4, ..., NMAX
addEventListener('load', () => document.fonts.ready.then(() => setTimeout(go, 50)));
})();
</script>
"""


# Headless Chrome's window is at least 500 px wide, so the page runs in an iframe as wide as the configuration asks;
# the harness posts its report to this host page, which writes it into its own DOM for --dump-dom.
HOST = """<!doctype html>
<html><head><meta charset="utf-8"></head><body style="margin: 0">
<iframe src="index.html" style="display: block; border: 0; width: __WIDTH__px; height: 1000px"></iframe>
<script>
addEventListener('message', e => {
  const pre = document.createElement('pre'); pre.id = 'harness-out'; pre.textContent = e.data; document.body.append(pre);
});
</script>
</body></html>
"""


def kinds_data(violation=None):
    """Made-up data that follows the contract and uses every kind of reason: odd columns are ["none"] and ["odd"]; an even
    n has lo = 1 from an example and hi = 2^v - 1 ("two") if that is at most 7, else 7 by the residue condition mod 3;
    a few columns use the other kinds.  violation, if given, names the change in VIOLATIONS that breaks it."""
    cols = []
    for n in range(1, NMAX + 1):
        two = (n & -n) - 1
        cols.append([0, 0, ['none'], ['odd']] if n % 2 else
                    [1, two, ['example', 'a made-up label'], ['two']] if two <= 7 else
                    [1, 7, ['example', 'a made-up label'], ['residue', 3]])
    for n, c in ((4, [2, 2, ['product', 2, 2], ['norm', 3]]), (8, [3, 3, ['table2'], ['table2']]),
                 (12, [2, 3, ['join', 4, 8], ['two']]), (16, [4, 4, ['page', 'BGPW'], ['page', 'Claude and BGPW']]),
                 (20, [3, 3, ['page', 'Claude alone'], ['two']]), (24, [4, 5, ['example', 'BGPW Table 5'], ['residue', 9]]),
                 (32, [5, 7, ['product', 16, 2], ['norm', 5]]), (48, [6, 7, ['table2'], ['norm', 7]])):
        cols[n - 1] = c
    data = {'nmax': NMAX, 'mtop': max(c[1] for c in cols) + 1, 'cols': cols}
    VIOLATIONS.get(violation, (lambda data: None,))[0](data)
    return 'const MSTAR = ' + json.dumps(data) + ';\n'


def column(n, entry):
    """A change to made-up data: column n becomes entry."""
    def change(data): data['cols'][n - 1] = entry
    return change


VIOLATIONS = {   # name: (a change that breaks the contract, what the page's error line must quote)
    'lo above hi': (column(100, [5, 3, ['example', 'a made-up label'], ['two']]),
                    "[100,[5,3,['example','a made-up label'],['two']]]"),
    'unknown kind': (column(100, [1, 3, ['guess'], ['two']]), "[100,[1,3,['guess'],['two']]]"),
    'arity': (column(100, [1, 3, ['join', 50], ['two']]), "[100,[1,3,['join',50],['two']]]"),
    'join lengths': (column(100, [1, 3, ['join', 40, 50], ['two']]), "[100,[1,3,['join',40,50],['two']]]"),
    'join order': (column(100, [3, 3, ['join', 50, 50], ['two']]), "[100,[3,3,['join',50,50],['two']]]"),
    'product order': (column(100, [3, 3, ['product', 50, 2], ['two']]), "[100,[3,3,['product',50,2],['two']]]"),
    'two': (column(100, [1, 2, ['example', 'x'], ['two']]), "[100,[1,2,['example','x'],['two']]]"),
    'norm divisor': (column(100, [1, 3, ['example', 'x'], ['norm', 5]]), "[100,[1,3,['example','x'],['norm',5]]]"),
    'norm composite': (column(100, [1, 3, ['example', 'x'], ['norm', 9]]), "[100,[1,3,['example','x'],['norm',9]]]"),
    'table2 n': (column(100, [1, 3, ['table2'], ['two']]), "[100,[1,3,['table2'],['two']]]"),
    'page who': (column(100, [1, 3, ['page', 'Stan'], ['two']]), "[100,[1,3,['page','Stan'],['two']]]"),
    'empty label': (column(100, [1, 3, ['example', ''], ['two']]), "[100,[1,3,['example',''],['two']]]"),
    'none at even n': (column(100, [0, 3, ['none'], ['two']]), "[100,[0,3,['none'],['two']]]"),
    'odd at even n': (column(100, [0, 0, ['none'], ['odd']]), "[100,[0,0,['none'],['odd']]]"),
    'example at odd n': (column(99, [0, 0, ['example', 'x'], ['odd']]), "[99,[0,0,['example','x'],['odd']]]"),
    'five entries': (column(100, [1, 3, ['example', 'x'], ['two'], 0]), "[100,[1,3,['example','x'],['two'],0]]"),
    'hi at mtop': (column(100, [1, 8, ['example', 'x'], ['residue', 3]]), "[100,[1,8,['example','x'],['residue',3]]]"),
    'mtop': (lambda data: data.update(mtop=9), '[9]'),
    'nmax': (lambda data: data.update(nmax=999), '[999,8]'),
}


CONFIGS = {   # name: (mstar.js, window width, device pixel ratio, theme, hover every this many columns)
    'light': ('real', 1280, 2, None, 1),
    'phone': ('real', 390, 3, None, 5),
    'kinds': ('kinds', 1280, 2, None, 1),
    'missing': (None, 1280, 2, None, 1),
} | {f'violates {v}': (v, 1280, 1, None, 1) for v in VIOLATIONS}
SOURCES = {'real': lambda: open(DATA, encoding='utf-8').read(), 'kinds': kinds_data} | {
    v: (lambda v=v: kinds_data(v)) for v in VIOLATIONS}           # mstar.js's text, by CONFIGS's first entry


def run(name):
    """The harness's report for one configuration, made on first use."""
    if name not in RUNS:
        data, width, dpr, theme, every = CONFIGS[name]
        d = tempfile.mkdtemp(prefix='index-quals-')
        text = page()
        assert text.count('<head>\n') == 1 and text.count('</body>') == 1 and text.count('<html lang="en">') == 1
        text = text.replace('<head>\n', '<head>\n' + EARLY).replace('</body>', HARNESS.replace(
            '__OPTS__', json.dumps({'hoverEvery': every})).replace('__NCOL__', str(NCOL)) + '</body>')
        if theme: text = text.replace('<html lang="en">', f'<html lang="en" data-theme="{theme}">')
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
        if data is not None: open(os.path.join(d, 'mstar.js'), 'w', encoding='utf-8').write(SOURCES[data]())
        shutil.copy(POW2, os.path.join(d, 'pow2.js'))
        open(os.path.join(d, 'host.html'), 'w').write(HOST.replace('__WIDTH__', str(width)))
        dom = chrome(d, [f'--window-size={max(width, 500) + 40},1100', f'--force-device-scale-factor={dpr}',
                         '--virtual-time-budget=10000', '--dump-dom', 'file://' + os.path.join(d, 'host.html')])
        m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert m, (name, dom[-3000:])
        RUNS[name] = json.loads(html.unescape(m.group(1)))
        shutil.rmtree(d)
    return RUNS[name]


def chrome(d, args, stderr=subprocess.DEVNULL):
    """Headless Chrome with its own profile in directory d: the DOM it dumps.  This Chrome prints the dump and then
    does not exit, so the dump is read up to </html> and then Chrome's own process group is ended (end_group), all of
    it, before d may go (a watchdog sends it SIGTERM after 600 s, and the dump is then incomplete, which the caller's
    assert reports)."""
    p = subprocess.Popen([CHROME, '--headless=new', f'--user-data-dir={d}/profile', '--no-first-run',
                          '--no-default-browser-check', '--disable-extensions', *args],
                         stdout=subprocess.PIPE, stderr=stderr, text=True, start_new_session=True)
    stop = lambda: os.killpg(p.pid, signal.SIGTERM)
    watchdog = threading.Timer(600, stop)
    watchdog.start()
    out = []
    for line in p.stdout:
        out.append(line)
        if '</html>' in line: break
    watchdog.cancel()
    end_group(p)
    return ''.join(out)


def alive(pgid):
    """Whether any process of the process group pgid remains: EPERM says some do, though none may be signalled, as a
    zombie not yet reaped (macOS)."""
    try: os.killpg(pgid, 0)
    except ProcessLookupError: return False
    except PermissionError: pass
    return True


def gone(pgid, seconds):
    """Whether the process group pgid is gone, waiting up to seconds for it to be."""
    end = time.monotonic() + seconds
    while alive(pgid) and time.monotonic() < end: time.sleep(0.1)
    return not alive(pgid)


def end_group(p, term=10, kill=5):
    """End the process group that p leads, p started in a session of its own: SIGTERM to the whole group, whether or
    not p has exited, since Chrome's helpers can outlive its main process for a moment, writing into the profile the
    caller deletes next (2026-10-26: "Directory not empty", twice); p reaped; then wait until no process of the group
    remains, SIGKILL after term seconds, and fail loudly if any of it outlives that by kill seconds."""
    for sig, seconds in ((signal.SIGTERM, term), (signal.SIGKILL, kill)):
        with contextlib.suppress(ProcessLookupError, PermissionError): os.killpg(p.pid, sig)   # none left, or none signallable
        with contextlib.suppress(subprocess.TimeoutExpired): p.wait(timeout=seconds)
        if gone(p.pid, seconds): return
    raise AssertionError(f'process group {p.pid} outlived SIGKILL')


def console_lines():
    """The lines Chrome logs from the page's console when it loads index.html as is, with the real mstar.js beside it."""
    d = tempfile.mkdtemp(prefix='index-quals-')
    shutil.copy(INDEX, os.path.join(d, 'index.html'))
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    with open(os.path.join(d, 'stderr.txt'), 'w') as f:
        chrome(d, ['--enable-logging=stderr', '--v=0', '--window-size=1280,1000', '--virtual-time-budget=10000',
                   '--dump-dom', 'file://' + os.path.join(d, 'index.html')], stderr=f)
    lines = [line for line in open(os.path.join(d, 'stderr.txt'), errors='replace') if ':CONSOLE' in line]
    shutil.rmtree(d)
    return lines


def valid_run(name):
    """A run on valid data: the harness finished and nothing recorded an error."""
    R = run(name)
    assert 'harnessError' not in R, R['harnessError']
    assert R['errors'] == [], R['errors']
    return R


def close(a, b, tol): return abs(a - b) <= tol


# The section "The smallest length known for each order" (Stan Wagon's suggestion, relayed 2026-10-17: "keep track of a
# table that shows the first n that gives 1,2,3,4,5,…,12"; dreeves: "yeah").  Orders 1 to 11 have their smallest
# lengths proven: OEIS A323395's a(0) to a(8), 240 as a(9), and (2026-10-20) 432 as a(10), after proof384.py.
SMALLEST_PROVEN = (2, 4, 8, 16, 32, 48, 96, 144, 192, 240, 432)


def smallest_rows(cols):
    """The rows the section's script makes from MSTAR's cols, computed here: for each order m from 1 while some n has a
    known sequence of order m (its lower bound at least m), the texts of m, the least such n, a check mark if that n is
    also the least n whose upper bound is at least m (else nothing), and that least n."""
    least = lambda test: next((n for n, c in enumerate(cols, 1) if test(c)), None)
    rows, m = [], 1
    while least(lambda c: c[0] >= m):
        known, possible = least(lambda c: c[0] >= m), least(lambda c: c[1] >= m)
        rows.append([str(m), str(known), '✓' if known == possible else '', str(possible)])
        m += 1
    return rows


def a323395_cells(cols):
    """The cells (n, m) the chart rings in gold (dreeves, 2026-10-19): smallest_rows' proven ones, the terms a(m − 1)
    of OEIS A323395 that the data proves."""
    return [(int(n), int(m)) for m, n, proven, _ in smallest_rows(cols) if proven]


def ring_note(m):
    """The readout's note on a ringed cell of order m (Claude's words, without the Claude: "…")."""
    return f'the least n of order {m}: a({m - 1}) of OEIS A323395'


# ---------------------------------------------------------------------------------------------------------------------
# Static quals

def q_384_proof_is_linked():
    # Replicata: the new-results table and remarks, plus the generated chart's smallest-length rows.
    # Expectata: 384's cell is of Astra's class (a); its remark (li#proof384) links the standalone checker proof384.py
    # and gives m* = 10; and order 11 is now proven to have smallest length 432.
    text = page()
    assert re.search(r'<td class="a"[^>]*>384</td>', text)
    remark = re.search(r'<li class="a" id="proof384">(.*?)</li>', text, re.S)
    assert remark, 'no remark for 384'
    assert 'href="proof384.py"' in remark.group(1) and '<i>m</i><sup>*</sup> = 10' in remark.group(1), remark.group(1)[:300]
    assert smallest_rows(mstar_data()['cols'])[10] == ['11', '432', '✓', '432']


def q_section_follows_table2():
    # Replicata: index.html.
    # Expectata: the page's one <figure> (Table 2) is followed, with only blank lines and comments between, by
    # <section class="mstar" aria-labelledby="mstar-title">, and that by <section class="pow2" (the chart of powers of
    # 2; quals_pow2_page.py holds it to being followed by <section class="remarks">).  In order, the
    # section holds: a paragraph introducing the chart (dreeves's, which replaced the h2 mstar-title by 2026-10-27);
    # a legend whose swatches are exists, open and impossible, then (since
    # 2026-10-19) exists ringed in gold for a(m − 1) of OEIS A323395; the reset
    # button; the canvas mstar-chart (height 0 until drawn, focusable, an image with a label); and the readout
    # paragraph mstar-readout, polite live region.  (dreeves's copyedit dropped the caption paragraph.)
    text = page()
    assert text.count('<figure>') == 1 and text.count('</figure>') == 1
    after = text[text.index('</figure>') + len('</figure>'):]
    filler = r'(?:\s|<!--.*?-->)*'
    m = re.match(filler + r'<section class="mstar" aria-labelledby="mstar-title">.*?</section>', after, re.S)
    assert m, after[:400]
    assert re.match(filler + r'<section class="pow2"', after[m.end():], re.S), after[m.end():m.end() + 400]
    parts = [r'<p>', r'<ul class="legend">', r'<span class="swatch exists" aria-hidden="true">',
             r'<span class="swatch open" aria-hidden="true">', r'<span class="swatch impossible" aria-hidden="true">',
             r'<span class="swatch exists record" aria-hidden="true">',
             r'</ul>', r'<button type="button" id="mstar-reset" ',
             r'<canvas id="mstar-chart" height="0" tabindex="0" role="img" aria-label=',
             r'<p id="mstar-readout" aria-live="polite">']
    assert re.search('.*?'.join(parts), section(), re.S), section()


def q_changelog_sits_under_the_authors_as_in_freshat():
    # Replicata: index.html's header.
    # Expectata (dreeves, 2026-10-26: "can you add a skeleton of a changelog at the top of the page, modeled after
    # doc.bmndr.co/freshat"): as FreshAt's changelog follows its byline, a <details class="changelog"> follows the
    # authors' line, the title's next, whatever his words there, with only comments between,
    # and has no open attribute, so it starts closed; a summary, and the rest entries, and TODO comments, for entries
    # in Claude's words; each entry a <p> on its own line, "YYYY-MM-DD: what changed" as in FreshAt, a real date,
    # newest first.
    # Resultata before: no changelog.
    dates = [d for d, _ in changelog()]
    assert dates and all(datetime.date.fromisoformat(d).isoformat() == d for d in dates), dates
    assert dates == sorted(dates, reverse=True), dates


def changelog():
    """The changelog's entries, newest first, as (date, the rest after "date: "), the changelog asserted to be of the
    form q_changelog_sits_under_the_authors_as_in_freshat holds it to."""
    head = re.search(r'<header>\n(.*?)\n</header>', page(), re.S)
    assert head, 'no header'
    m = re.match(r'  <h1>[^\n]*</h1>\n  <p class="lede">[^\n]*</p>\n(?:  <!--[^\n]*-->\n)*'
                 r'  <details class="changelog">\n    <summary>[^\n]*</summary>\n(.*?)\n  </details>\n',
                 head.group(1) + '\n', re.S)
    assert m, head.group(1)[:800]
    lines = [l.strip() for l in m.group(1).split('\n') if not re.fullmatch(r'\s*<!-- TODO:.*-->', l)]
    entries = [re.fullmatch(r'<p>(\d{4}-\d{2}-\d{2}): (\S.*)</p>', l) for l in lines]
    assert entries and all(entries), lines
    return [e.groups() for e in entries]


# A statement of a new result's bounds in a changelog entry (dreeves, 2026-10-26: "yes please", to an entry with each
# update of the new results, and "can you backfill all the results that are new since the BGPW paper?"), in math, so
# without a Claude: "…": m*(n) = v, m*(n) ≥ a, m*(n) ≤ b or a ≤ m*(n) ≤ b, n's digits or 2<sup>k</sup>
STATEMENT = r'<span class="nw">(?:(\d+) ≤ )?<i>m</i><sup>\*</sup>\((\d+|2<sup>\d+</sup>)\) (=|≥|≤) (\d+)</span>'


def statements(rest):
    """{n: (low, high)} for an entry's rest: empty for an entry of his words; for one in math, its statements, joined by
    ', ' (nothing else), as statement() makes them: m*(n) = v (v, v), m*(n) ≥ a (a, None), m*(n) ≤ b (None, b) and
    a ≤ m*(n) ≤ b (a, b)."""
    found = re.findall(STATEMENT, rest)
    assert not found or re.fullmatch(f'{STATEMENT}(?:, {STATEMENT})*', rest), rest
    assert all(op == '≤' for lo, _, op, _ in found if lo), rest
    out = {cell_n(n): (int(lo), int(v)) if lo else {'=': (int(v), int(v)), '≥': (int(v), None), '≤': (None, int(v))}[op]
           for lo, n, op, v in found}
    assert len(out) == len(found), rest
    return out


def changelog_by_day():
    """{date: {n: (low, high)}}: the statements of all the changelog's entries of each day, no n twice in a day."""
    out = {}
    for d, rest in changelog():
        said = statements(rest)
        assert not set(said) & set(out.get(d, {})), (d, set(said) & set(out[d]))
        out[d] = out.get(d, {}) | said
    return out


def q_changelog_brings_every_new_result_up_to_date():
    # Replicata: the changelog's statements, day by day, oldest first, starting from no bounds (0 and inf); the block
    # (div.new-block); and the m*(n) chart's reasons for its bounds.
    # Expectata (dreeves, 2026-10-26: "yes please", to a changelog entry with each update of the new results; and, of
    # its first 112 statements, "if there's an excuse to trim it down, we should"): each statement tightens its n's
    # bounds, raising the low, lowering the high, or both, and is still true, the block's bounds for n lying within the
    # statements'; every n stated is in the block; and every entry of the block whose lower bound is a partition of its
    # own length (up to NMAX, not BUILT; past it, a power of 2 whose pow2.js loWhy is the join of one block of length
    # n, since 1024 got its example of order 11 on 2026-10-26) is up to date, its bounds exactly the statements', as
    # is every upper bound proved on the page (reason 'page') and the low of each power of 2 that sets a threshold of
    # Theorem 1 (dreeves, 2026-10-26: "we obviously want 2^17:18 and 2^24:25 in the changelog").
    # Resultata before the trim: the 112 statements also brought every entry built from other partitions up to date.
    # Resultata after it, before the thresholds came back: no power of 2 past 512 had a statement.
    state = {}
    for d, said in sorted(changelog_by_day().items()):
        after = fold(state, said)
        moved = [(n, state.get(n, (0, math.inf)), after[n]) for n in said]
        assert all(a != b and b[0] <= a[0] <= a[1] <= b[1] for _, b, a in moved), (d, moved)
        state = after
    cells, cols = new_cells(page()), mstar_data()['cols']
    assert set(state) <= set(cells), set(state) - set(cells)
    false = {n: (state[n], cells[n]) for n in state if not state[n][0] <= cells[n][0] <= cells[n][1] <= state[n][1]}
    assert not false, false
    pows = pow2_data()['cols']
    own = ({n for n in cells if n <= NMAX and cols[n - 1][2][0] not in BUILT} |
           {n for n in cells if n > NMAX and pows[n.bit_length() - 2][2] == ['joins', [[[n, cells[n][0]]]]]})
    proved = {n for n in cells if n <= NMAX and cols[n - 1][3][0] == 'page'}
    first = {2 ** k for k in firsts(cells).values()}
    stale = sorted({n for n in own if state.get(n) != cells[n]} |
                   {n for n in proved if state.get(n, (0, math.inf))[1] != cells[n][1]} |
                   {n for n in first if state.get(n, (0, math.inf))[0] != cells[n][0]})
    assert not stale, [(n, state.get(n), cells[n]) for n in stale]


def q_changelog_dates_the_page_s_first_results_by_the_chat():
    # Replicata: CHAT; the claude.ai chat's exchanges in sourcery.html; the changelog's statements of the days before
    # the page's first commit (FIRST); and that commit's new results.
    # Expectata (dreeves, 2026-10-26: "can you backfill all the results that are new since the BGPW paper?", having
    # dated the chat's first new result by the chat in his own entry): each row of CHAT has its words in its exchange,
    # whose prompt is of its day; the changelog's days before FIRST's state exactly CHAT's statements as the changelog
    # lists them (chat_listed()); and CHAT's statements leave each new result of FIRST at its bounds there.
    # Resultata before: the changelog had no statements.
    chat = exchanges()
    bad = [row[:3] for row in CHAT if row[1] not in chat or chat[row[1]][0] != row[0] or row[2] not in chat[row[1]][1]]
    assert not bad, bad
    begun = git('log', '-1', '--format=%ad', '--date=format:%Y-%m-%d', FIRST).strip()
    said, days, state = changelog_by_day(), chat_listed(), chat_days()[1]
    wrong = [(d, said.get(d, {}), days.get(d, {})) for d in sorted(set(said) | set(days))
             if d < begun and said.get(d, {}) != days.get(d, {})]
    assert not wrong, wrong
    cells = new_cells(git('show', f'{FIRST}:index.html'))
    assert {n: state.get(n) for n in cells} == cells, (state, cells)


def q_changelog_backfill_matches_the_page_s_history():
    # Replicata: the changelog's statements by day; and page_days(): for each day of index.html's commits through
    # BACKFILL, the new results whose bounds the day changed, the first day's from the bounds the chat had reported
    # (chat_days), as the changelog lists them (listed(), by that day's m*(n) chart).
    # Expectata (dreeves, 2026-10-26: "can you backfill all the results that are new since the BGPW paper?", and of
    # its first 112 statements, "if there's an excuse to trim it down, we should"): each day from the page's first to
    # the one before BACKFILL's states exactly its listed changes, as statement() makes them; BACKFILL's day states its
    # listed changes through BACKFILL, and may state later ones of that day.
    # Resultata before the trim: each day stated all its changes, those built from other partitions too.
    said, days = changelog_by_day(), page_days(chat_days()[1])
    first, last = min(days), max(days)
    wrong = [(d, said.get(d, {}), days.get(d, {})) for d in sorted(set(said) | set(days))
             if first <= d < last and said.get(d, {}) != days.get(d, {})]
    assert not wrong, wrong
    assert days[last].items() <= said.get(last, {}).items(), (days[last], said.get(last))


def q_changelog_gives_noteworthy_results_lines_of_their_own():
    # Replicata: the changelog's entries, and NOTEWORTHY.
    # Expectata (dreeves, 2026-10-26: "i think m*(2^9)=9 and other noteworthy results should be their own changelog
    # line even though that means duplicating the date"): each result of NOTEWORTHY is an entry of its date with no
    # other statement, and no other entry of that date states its n.
    # Resultata before: m*(2^9) = 9 was one statement of six in the entry of 2026-10-05.
    entries = [(d, statements(rest)) for d, rest in changelog()]
    bad = [row[:3] for row in NOTEWORTHY if (row[0], {row[1]: row[2]}) not in entries or
           sum(row[1] in said for d, said in entries if d == row[0]) != 1]
    assert not bad, bad


def q_changelog_keeps_powers_of_2_on_lines_of_their_own():
    # Replicata: the changelog's entries.
    # Expectata (dreeves, 2026-10-26: "how about also always separating the powers-of-2 results onto their own lines,
    # just for readability/organization reasons?"): no entry states both a power of 2 from 512 up (written 2^k, as in
    # the table's rows of powers of 2) and another n.
    # Resultata before: the entry of 2026-10-17 stated m*(800) = 11 and seven powers of 2.
    mixed = [(d, sorted(said)) for d, said in ((d, statements(rest)) for d, rest in changelog())
             if len({n >= 512 and n & (n - 1) == 0 for n in said}) > 1]
    assert not mixed, mixed


# The page in an iframe width px wide (Chrome's window is at least 500 px wide), with harness (a script, which may
# await sleep) run last in it, once the page has had half a second: what the harness posted to the host page, as JSON.
def framed(width, harness):
    d = tempfile.mkdtemp(prefix='index-quals-')
    script = ('<script>\n(async () => {\n  const sleep = ms => new Promise(r => setTimeout(r, ms));\n  await sleep(500);\n'
              + harness + '\n})();\n</script>\n')
    text = page()
    assert text.count('</body>') == 1
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text.replace('</body>', script + '</body>'))
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    open(os.path.join(d, 'host.html'), 'w').write(HOST.replace('__WIDTH__', str(width)))
    dom = chrome(d, [f'--window-size={max(width, 500) + 40},1100', '--virtual-time-budget=5000', '--dump-dom',
                     'file://' + os.path.join(d, 'host.html')])
    shutil.rmtree(d)
    m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
    assert m, dom[-2000:]
    return json.loads(html.unescape(m.group(1)))


def q_changelog_starts_closed_and_fits_a_phone():
    # Replicata: index.html 390 px wide (a phone) and 1000 px, as loaded; then its changelog's summary clicked; then a
    # made-up entry too long for one line added to the changelog.
    # Expectata (dreeves, 2026-10-26, as for q_changelog_sits_under_the_authors_as_in_freshat): as loaded, the
    # changelog's summary shows and none of its entries; its cursor is a pointer, as on FreshAt's; clicked, it opens and
    # every entry shows, in the page's monospace font (--mono), as FreshAt's entries are in a <pre>; the long entry's
    # first line starts at the entry's left edge and each later line under the text after its date (the 13th
    # character, after "YYYY-MM-DD: "); and at each step the page is no wider than the window.
    # Resultata before: no changelog.
    for width in (390, 1000):
        got = framed(width, """
  const box = document.querySelector('header > details.changelog'), summary = box.querySelector('summary');
  const wider = () => document.documentElement.scrollWidth - innerWidth;
  const look = () => ({open: box.open, summary: summary.checkVisibility(), wider: wider(),
    entries: [...box.querySelectorAll('p')].map(p => p.checkVisibility())});
  const closed = look();
  summary.click();
  await sleep(50);
  const opened = look();
  const p = document.createElement('p');
  p.textContent = '2026-10-26: ' + 'made up '.repeat(40);
  box.append(p);
  await sleep(50);
  const text = p.firstChild, at = i => { const r = document.createRange(); r.setStart(text, i); r.setEnd(text, i + 1); return r.getBoundingClientRect().left; };
  const all = document.createRange(); all.selectNodeContents(p);
  const long = {left: p.getBoundingClientRect().left, date: at(12), wider: wider(),
    lines: [...all.getClientRects()].filter(r => r.width > 0).map(r => r.left)};
  parent.postMessage(JSON.stringify({closed, opened, long, font: getComputedStyle(p).fontFamily,
    mono: getComputedStyle(document.documentElement).getPropertyValue('--mono').trim(),
    cursor: getComputedStyle(summary).cursor}), '*');""")
        closed, opened, long = got['closed'], got['opened'], got['long']
        assert (closed['open'], closed['summary']) == (False, True) and closed['entries'] and not any(closed['entries']), (width, got)
        assert opened['open'] and opened['entries'] and all(opened['entries']), (width, got)
        assert got['cursor'] == 'pointer' and got['font'] == got['mono'], (width, got)
        assert len(long['lines']) > 1 and close(long['lines'][0], long['left'], 0.5), (width, long)
        assert all(close(x, long['date'], 0.5) for x in long['lines'][1:]), (width, long)
        assert max(closed['wider'], opened['wider'], long['wider']) <= 0, (width, got)


def q_chrome_s_whole_process_group_ends_before_its_folder_goes():
    # Replicata: two process groups in sessions of their own, as chrome() starts Chrome's: one whose leader exits at
    # once while a member lives on for a second, as Chrome's helpers outlive its main process for a moment; and one
    # whose members all ignore SIGTERM; each ended by end_group, the first with chrome()'s deadlines, the second with
    # short ones; and a group whose only member is its leader, exited but not yet reaped, a zombie.
    # Expectata: each of the first two still has a member once its leader is gone, the race itself; and end_group
    # returns only when no process of the group remains, the second only after its SIGTERM deadline, by SIGKILL.  The
    # zombie, which macOS lets no one signal (EPERM), counts as a member until reaped, and end_group ends it too.
    # Resultata before the zombie's case (2026-10-26, two suites at once): end_group's first version took EPERM, all
    # that remained of a Chrome being some such member, for an error, "Operation not permitted".
    # Resultata before (2026-10-26, quals_pow2_page, twice): "Directory not empty" from rmtree, the temporary folder
    # deleted once Chrome's main process had exited while a helper still wrote into its profile.
    lingers = subprocess.Popen(['sh', '-c', 'sleep 1 & exit 0'], start_new_session=True)
    lingers.wait(timeout=10)
    assert alive(lingers.pid), 'the member did not outlive its leader'
    end_group(lingers)
    assert not alive(lingers.pid)
    stubborn = subprocess.Popen(['sh', '-c', 'trap "" TERM; sleep 30 & wait'], start_new_session=True)
    time.sleep(0.2)
    t0 = time.monotonic()
    end_group(stubborn, term=0.5, kill=5)
    assert not alive(stubborn.pid) and time.monotonic() - t0 >= 0.5, time.monotonic() - t0
    zombie = subprocess.Popen(['sh', '-c', 'exit 0'], start_new_session=True)
    time.sleep(0.3)
    assert alive(zombie.pid), 'a zombie is no member'
    end_group(zombie)
    assert not alive(zombie.pid)


def q_scripts_load_data_then_draw():
    # Replicata: index.html's script tags.
    # Expectata: exactly six, after </main> and before </body>: a classic <script src="mstar.js"> (no type, async or
    # defer, so it also loads from file://) and then one inline script; then the chart of powers of 2's, likewise
    # (quals_pow2_page.py holds those two); then the inline script of the table of smallest lengths, which reads MSTAR
    # (2026-10-17); then the inline script of the section "Search progress", which loads progress.js itself
    # (2026-10-17).
    text = page()
    assert re.findall(r'<script\b[^>]*>', text) == ['<script src="mstar.js">', '<script>', '<script src="pow2.js">', '<script>',
                                                    '<script>', '<script>'], re.findall(r'<script\b[^>]*>', text)
    inline = re.findall(r'<script>\n(.*?)</script>', text, re.S)
    assert '[data-smallest]' in inline[2] and 'progressData' in inline[3], [js[:60] for js in inline]
    assert text.index('</main>') < text.index('<script src="mstar.js"></script>') < text.index('<script>\n') < \
        text.index('</script>\n</body>')


def q_inline_script_passes_node_check():
    # Replicata: the inline script, saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = re.search(r'<script>\n(.*?)</script>', page(), re.S).group(1)
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'chart.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_tokens_in_all_three_theme_blocks():
    # Replicata: the custom properties of index.html's three theme blocks.
    # Expectata: --exists, --open and --impossible are in it, as #rrggbb (one block since 2026-10-12: no dark mode).
    light, = theme_blocks()
    for t in TOKENS:
        assert t in light and re.fullmatch(r'#[0-9a-fA-F]{6}', light[t]), t


def q_palette_reads_for_color_blind_readers():
    # Replicata: the chart's three colors in each mode, with the validator's arithmetic, all pairs (any two touch).
    # Expectata: the worst pair in normal vision is at least the validator's floor 15.  (The colors are dreeves's to tweak
    # since 2026-10-12, so no comment states their numbers.  Until then it also held the color-blind pair to 8, exists
    # and impossible 0.25 apart in lightness, and each of the three 15 from each provenance hue, in a dark mode too.)
    light, = theme_blocks()
    assert worst_normal([light[t].lower() for t in TOKENS]) >= 15, [light[t] for t in TOKENS]


def q_chart_colors_stand_apart():
    # Replicata: the charts' colors and the table's provenance hues in each mode, and the page's CSS (dreeves,
    # 2026-10-12: the charts' gray and green too similar; their red too like the table's orange for Claude alone; "the
    # 'claude and BGPW' color could be a striping of the other two").
    # Expectata: the chart's colors are dreeves's to tweak (2026-10-12: "so i can tweak them myself"), so none is pinned
    # here; Claude and BGPW has no hue of its own (no --joint,
    # anywhere): its cells and legend key are stripes of --claude's and --stan's tints over a striped bar, and its glyph
    # is half in each hue.
    def lch(h):
        L, a, b = oklab(linear(h))
        return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360
    for mode, b in zip(('light',), theme_blocks()):
        assert '--joint' not in b, mode
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    assert '--joint' not in css
    tints = ('repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, '
             'color-mix(in oklab, var(--stan) var(--tint), var(--paper)) 0.3rem 0.6rem)')
    bar = 'repeating-linear-gradient(90deg, var(--claude) 0 0.3rem, var(--stan) 0.3rem 0.6rem) bottom / 100% 3px no-repeat'
    half = 'linear-gradient(90deg, var(--claude) 50%, var(--stan) 50%)'
    assert f'td.j, .key.j {{ background: {tints}; }}' in css
    assert f'tr.vals td.j, .key.j {{ background: {bar}, {tints}; box-shadow: none; }}' in css
    assert (f'tr.ns td.j::before, .key.j > span, .remarks li.j .mk {{ background: {half}; -webkit-background-clip: text; '
            'background-clip: text; color: transparent; }') in css
    assert '<span class="key j" aria-hidden="true"><span>◆●</span></span>' in page()


def q_new_results_n_cells_line_up():
    # Replicata: index.html in the browser (light, desktop): in each n row of the new results' tables, the bottom of the
    # first line of each cell's n (its digits, or the 2 of 2^k).
    # Expectata (dreeves, 2026-10-12: "minor spacing issue (remember anti-magic)"): the nine rows' cells (six until
    # 2026-10-26, when the powers of 2 took a third row; seven until 2026-10-27, when the block took in Table 2 and
    # reached 1024 in six upper rows) line up within half a pixel, the uncolored copies of Table 2's entries among
    # them: every n cell of the new results takes the same room above its n, glyph or no glyph.
    rows = valid_run('light')['nTextBottoms']
    assert len(rows) == 9 and all(len(r) >= 5 for r in rows), rows
    assert all(max(r) - min(r) <= 0.5 for r in rows), rows


def q_new_results_fit_unscrolled_at_945_px():
    # Replicata: index.html with mstar.js, pow2.js and progress.js beside it, in headless Chrome with a window 945 px
    # wide: the widths of the new results' seven tables and of their sideways-scrolling frame (.new-block .scroll).
    # Expectata (the CSS comment on the new results' side padding: "keeps it in one row, unscrolled, at 945 px"; since
    # 2026-10-25, when the powers of 2 reached 23, their two rows too, and since 2026-10-26, when they reached 35 and
    # took three rows, those three; since 2026-10-27, when the block took in Table 2 and reached 1024, its six upper
    # rows, and since later that day the block's two frames, one for them and one for the powers of 2): no table is
    # wider than its frame, so neither frame scrolls.
    d = tempfile.mkdtemp(prefix='index-quals-')
    try:
        for name in ('mstar.js', 'pow2.js', 'progress.js'): shutil.copy(os.path.join(HERE, name), d)
        script = ("<script>addEventListener('load', () => setTimeout(() => { const p = document.createElement('pre'); p.id = 'fit'; "
                  "p.textContent = JSON.stringify([...document.querySelectorAll('.new-block .scroll')].map(f => ({frame: f.clientWidth, "
                  "scroll: f.scrollWidth, tables: [...f.querySelectorAll('table.block')].map(t => t.getBoundingClientRect().width)}))); "
                  "document.body.append(p); }, 500));</script>\n")
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(page().replace('</body>', script + '</body>'))
        dom = chrome(d, ['--window-size=945,1200', '--virtual-time-budget=4000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    finally:
        shutil.rmtree(d)
    m = re.search(r'<pre id="fit">(.*?)</pre>', dom)
    assert m, dom[-500:]
    R = json.loads(m.group(1))
    assert [len(f['tables']) for f in R] == [6, 3], R
    assert all(f['scroll'] <= f['frame'] and max(f['tables']) <= f['frame'] for f in R), R


def new_frames(text):
    """The HTML inside each sideways-scrolling frame (div.scroll) of the new results' block in text, in page order:
    since 2026-10-27, one for the lengths other than powers of 2 and one for the powers of 2."""
    block = text[text.index('<div class="new-block">'):text.index('</figure>')]
    return re.findall(r'<div class="scroll">(.*?)</div>', block, re.S)


def new_block_cells():
    """The new results' tables, frame by frame (new_frames), each table as a list of (n, its n cell as the page writes
    it, the n cell's attributes, the value cell's attributes, the value), in page order."""
    out = []
    for frame in new_frames(page()):
        out.append([])
        for t in re.findall(r'<table class="block">.*?</table>', frame, re.S):
            ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', t, re.S).group(0))
            vs = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', t, re.S).group(0))
            assert len(ns) == len(vs) and ns, t
            out[-1].append([(cell_n(c), c, a, va, v) for (a, c), (va, v) in zip(ns, vs)])
    return out


def q_new_results_subsume_table2():
    # Replicata: the new results' tables on index.html (each cell's n, attributes and value) and Table 2's entries.
    # Expectata (2026-10-27; dreeves: "how about making our color-coded table totally subsume the BGPW table? The
    # color-coding makes it nice and clear which cells are repeated from that table"; Stan Wagon, by dreeves: the
    # upper part "should include 256, 512, and 1024 for completeness", and "could the table and the chart go up to
    # 1024 as the natural stopping point, instead of 1000?"; dreeves, on the lengths: "multiples of 16 with
    # one-sentence explanation sounds good"; then "can we split the table into the non-powers-of-2 and the
    # powers-of-2 and move the note about multiples of 8 or 16 under the non-power-of-2 table?"): the block has two
    # frames, the first holding the upper rows, their n in digits, and the second the rows of powers of 2, written
    # 2^k, with k rising from 3; the upper rows' lengths are every multiple of 8 up to 304, as in Table 2,
    # then every multiple of 16 up to NMAX; every entry of Table 2 is in the block, as a cell without a provenance
    # class, titled "The published paper (2021)", with exactly Table 2's bounds, or as a classed cell whose bounds lie
    # within Table 2's (240, 304 and 2^51, each improved since); every unclassed cell is such a copy; and a length the
    # block shows twice, in the upper rows and as a power of 2 (8 to 1024), is the same cell both times.
    frames = new_block_cells()
    assert len(frames) == 2, [[[c for _, c, *_ in r] for r in f] for f in frames]
    upper, pows = frames
    rows = upper + pows
    assert all(re.fullmatch(r'\d+', c) for r in upper for _, c, *_ in r) and upper, [[c for _, c, *_ in r] for r in upper]
    assert all(re.fullmatch(r'2<sup>\d+</sup>', c) for r in pows for _, c, *_ in r) and pows, [[c for _, c, *_ in r] for r in pows]
    assert [n for r in upper for n, *_ in r] == list(range(8, 305, 8)) + list(range(320, NMAX + 1, 16))
    ks = [n.bit_length() - 1 for r in pows for n, *_ in r]
    assert ks[0] == 3 and ks == sorted(set(ks)), ks
    t2 = {}                                       # Table 2's entries, 2^51 among them
    for t in re.findall(r'<table class="block">.*?</table>', page()[:page().index('<div class="new-block">')], re.S):
        ns = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', t, re.S).group(0))
        vs = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', t, re.S).group(0))
        t2 |= {cell_n(c): bounds(v) for c, v in zip(ns, vs)}
    assert len(t2) == 39 and 2 ** 51 in t2, sorted(t2)
    cells = [cell for r in rows for cell in r]
    paper = " title='The published paper (2021)'"
    copies = {n: bounds(v) for n, c, a, va, v in cells if a == paper}
    assert all(a == paper and va == '' or re.fullmatch(r' class="(\w+)" title=\'[^\']+\'', a) and va == a.split(' title')[0]
               for n, c, a, va, v in cells), [cell for cell in cells if cell[2] != paper and not cell[3]]
    assert set(copies) <= set(t2) and all(copies[n] == t2[n] for n in copies), {n: (copies[n], t2.get(n)) for n in copies}
    classed = {n: bounds(v) for n, c, a, va, v in cells if a != paper}
    assert set(t2) <= set(copies) | set(classed) and set(t2) - set(copies) == {240, 304, 2 ** 51}, set(t2) - set(copies)
    assert all(t2[n][0] <= classed[n][0] <= classed[n][1] <= t2[n][1] for n in (240, 304, 2 ** 51)), classed
    twice = {n for n, *_ in cells if sum(m == n for m, *_ in cells) > 1}
    assert twice == {2 ** k for k in range(3, 11)}, sorted(twice)
    assert all(len({(a, va, v) for m, c, a, va, v in cells if m == n}) == 1 for n in twice), sorted(twice)


def q_new_results_say_which_lengths():
    # Replicata: the paragraph between the new results' two frames, right under the table of lengths other than
    # powers of 2 (the sentence dreeves asked for on 2026-10-27: "multiples of 16 with one-sentence explanation sounds
    # good", and where he put it: "move the note about multiples of 8 or 16 under the non-power-of-2 table"), its text
    # with tags dropped; the upper rows' lengths; mstar.js's columns.
    # Expectata: the paragraph names, as numbers, what the table and the chart give: 8 and 304, the step of the upper
    # rows up to their last length before the step doubles, 16, the step after, 7, which the two lemma (BGPW's
    # Theorem 4.1, linked) allows an odd multiple of 8 at most, and 200, the least n from which every odd multiple of
    # 8 up to NMAX has lo = hi = 7 in mstar.js (so that none of them, past 304, has anything to show); and it links
    # Theorem 4.1.
    block = page()[page().index('<div class="new-block">'):page().index('</figure>')]
    m = re.search(r'<div class="scroll">(?:(?!</div>).)*</div>\s*(?:<!--(?:(?!-->).)*-->\s*)*<p>((?:(?!</p>).)*)</p>\s*'
                  r'<div class="scroll">', block, re.S)
    assert m, 'no paragraph between the new results\' frames'
    # numbers as words: not part of another word or of a decimal like the 4.1 of Theorem 4.1, but a sentence's final
    # period may follow one (dreeves's rewording of 2026-10-27 ends a sentence with "304.")
    said = {int(t) for t in re.findall(r'(?<![\w.])\d+(?!\w)(?!\.\d)', re.sub(r'<[^>]+>', '', m.group(1)))}
    lengths = [n for r in new_block_cells()[0] for n, *_ in r]
    steps = [b - a for a, b in zip(lengths, lengths[1:])]
    turn = lengths[steps.index(16)]
    assert set(steps) == {8, 16} and steps == sorted(steps), steps
    cols = mstar_data()['cols']
    sevens = [n for n in range(8, NMAX + 1, 16) if cols[n - 1][:2] != [7, 7]]
    least = max(sevens) + 16
    assert (turn, least, (8 & -8) - 1) == (304, 200, 7) and all(cols[n - 1][1] <= 7 for n in range(8, NMAX + 1, 16)), sevens
    assert {8, turn, 16, (8 & -8) - 1, least} <= said, (said, m.group(1))
    assert 'https://arxiv.org/html/1912.03491v1#S4.Thmthm1' in m.group(1), m.group(1)


def q_remarks_name_the_chart_s_constructions():
    # Replicata: each remark sentence of the form Claude: "Order m from examples above, doubled (a = 2·b, ...) or joined
    # (a = b + c, ...); ...", item by item, against mstar.js's loWhy at a.
    # Expectata: every item is the chart's own construction: a = 2·b is ["product", 2, b], a = b + c is ["join", b, c],
    # as their TODOs say ("how the m*(n) chart gets these").  (On 2026-10-12 the example at 560 made the chart's joins
    # 240 + 560, 336 + 560 and 432 + 560 win its ties at 800, 896 and 992, which a remark still called doublings.)
    cols = mstar_data()['cols']
    for s in re.findall(r'Claude: "Order \d+ from examples above, (.*?); order', page()):
        for kind, body in re.findall(r'(doubled|joined) \(([^)]*)\)', s):
            for a, b, c in re.findall(r'(\d+) = (?:2·(\d+)|(\d+ \+ \d+))', body):
                want = ['product', 2, int(b)] if kind == 'doubled' else ['join', *map(int, c.split(' + '))]
                assert (kind == 'doubled') == bool(b), (kind, a, b, c)
                assert cols[int(a) - 1][2] == want, (a, cols[int(a) - 1][2], want)


def q_2_18_shows_its_construction():
    # Replicata: the 2^18 remark on index.html, and certificate_2^18.wl beside it.
    # Expectata (dreeves, 2026-10-12: "for 2^18, index.html should show the proof, right? ... can we also get mathematica
    # code to generate the full list of 2^18/2 integers?"): the remark writes out the construction, (p320 # p560) ∨
    # (p48 # p432 # τ2), links the script; the script decodes the four blocks from hex
    # codes that are exactly codes on the page.
    li = re.search(r'<p class="entry"><i>n</i> = 2<sup>18</sup>: .*?</li>', page(), re.S).group(0)
    assert '<span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span>' in li, li
    assert '<span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>' in li, li
    assert 'certificate_2%5E18.wl"' in li, li
    wl = open(os.path.join(HERE, 'certificate_2^18.wl'), encoding='utf-8').read()
    codes = re.findall(r'(p\d+) = fromHex\["([0-9A-F]+)", \d+\];', wl)
    assert [k for k, _ in codes] == ['p320', 'p560', 'p432', 'p48'], codes
    assert all(f'<code>{h}</code>' in page() for _, h in codes), codes


def q_2_17_shows_its_construction():
    # Replicata: the 2^17 remark on index.html, and certificate_2^17.wl beside it.
    # Expectata (as for 2^18, which dreeves asked for on 2026-10-12; 800's example of order 11, 2026-10-17, moved the
    # first power of 2 that beats Thue-Morse by 1 from 2^18 to 2^17): the remark writes out the construction,
    # (p112 # p800) v (p48 # p432 # tau_1), links the script; the script
    # decodes the four blocks from hex codes that are exactly codes on the page.
    li = re.search(r'<p class="entry"><i>n</i> = 2<sup>17</sup>: .*?</li>', page(), re.S).group(0)
    assert '<span class="nw">(<i>p</i><sub>112</sub> # <i>p</i><sub>800</sub>)</span>' in li, li
    assert '<span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>1</sub>)</span>' in li, li
    assert 'certificate_2%5E17.wl"' in li, li
    wl = open(os.path.join(HERE, 'certificate_2^17.wl'), encoding='utf-8').read()
    codes = re.findall(r'(p\d+) = fromHex\["([0-9A-F]+)", \d+\];', wl)
    assert [k for k, _ in codes] == ['p112', 'p800', 'p48', 'p432'], codes
    assert all(f'<code>{h}</code>' in page() for _, h in codes), codes


def q_chart_agrees_with_tables():
    # Replicata: mstar.js (the chart's data) and the entries of the page's tables with n up to NMAX.
    # Expectata: for each entry (n, low, high): the column's [lo, hi] lies inside [low, high], and an exact entry
    # (low = high) is lo = hi.  304's two entries (8 or 9 in Table 2, 8 since) both hold, and 240's (10 or 11 in
    # Table 2, 10 since 2026-10-20).
    cols = mstar_data()['cols']
    entries = table_entries()
    # Table 2's 38; since 2026-10-27 the new results' 83 upper cells (every multiple of 8 up to 304, then of 16 up to
    # 1024) and their powers of 2 up to 1024, 2^3 to 2^10
    assert len(entries) == 38 + 83 + 8, len(entries)
    for n, low, high in entries:
        lo, hi = cols[n - 1][:2]
        assert low <= lo <= hi <= high, (n, low, high, lo, hi)


def q_new_results_state_what_the_chart_proves():
    # Replicata: the new results' tables on index.html (every n, the powers of 2 included, with each cell's provenance
    # class, none for the copies of Table 2's entries) and the remarks' entries under "Where the new results come from"
    # (each entry's n's, its "m* = v", "≥ v", "∈ {a, b, ...}" or "∈ {a, …, b}", and its <li>'s class);
    # mstar.js's columns for n <= NMAX and pow2.js's for n = 2^k.
    # Expectata: every cell with a provenance class, and every remark, states exactly its chart's [lo, hi] at its n, so
    # no "≥" stands where a chart proves an upper bound (dreeves's report of 2026-10-11: 432's entry said ≥ 11 beside the
    # chart's 11–12; and 2^51's said ≥ 53 beside the powers-of-2 chart's 54–63 until 2026-10-12); the remarks are one
    # each for exactly the classed cells' n, and for uncolored ones they rederive (since 2026-10-27, 288's: "just
    # clarify that that one isn't technically new but is rederived here"); and each remark is marked like its cell,
    # its <li> of the cell's class, or of none.
    cols, pow2 = mstar_data()['cols'], pow2_data()['cols']
    def chart(n):
        k = n.bit_length() - 1
        assert n <= NMAX or n == 2 ** k <= 2 ** pow2_data()['kmax'], n
        return cols[n - 1][:2] if n <= NMAX else pow2[k - 1][:2]
    def n_of(cell):
        m = re.fullmatch(r'(\d+)|2<sup>(\d+)</sup>', cell)
        assert m, cell
        return int(m.group(1)) if m.group(1) else 2 ** int(m.group(2))
    forms = ((r'(\d+)', lambda a: (a, a)), (r'(\d+) or (\d+)', lambda a, b: (a, b)), (r'(\d+)–(\d+)', lambda a, b: (a, b)),
             (r'≥ (\d+)', lambda a: (a, math.inf)), (r'= (\d+)', lambda a: (a, a)),
             (r'∈ \{(\d+)(?:, \d+)*, (\d+)\}', lambda a, b: (a, b)), (r'∈ \{(\d+), …, (\d+)\}', lambda a, b: (a, b)))
    def value(v):
        hits = [f(*map(int, m.groups())) for p, f in forms for m in [re.fullmatch(p, v)] if m]
        assert len(hits) == 1, v
        assert '…' in v or not v.startswith('∈') or [int(t) for t in re.findall(r'\d+', v)] == list(range(hits[0][0], hits[0][1] + 1)), v
        return hits[0]
    table = []
    for t in re.findall(r'<table class="block">.*?</table>', ''.join(new_frames(page())), re.S):
        ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', t, re.S).group(0))
        vs = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', t, re.S).group(0))
        assert len(ns) == len(vs) and ns, t
        table += [(n_of(n), *value(v), re.fullmatch(r'(?: class="(\w+)")? title=\'[^\']*\'', attr).group(1) or '')
                  for (attr, n), v in zip(ns, vs)]    # the cells without a provenance class copy Table 2's entries
    remarks = []
    entry = (r'<li(?: class="(\w+)")?(?: id="\w+")?>\s*<span class="mk" aria-hidden="true">[^<]*</span>\s*'
             r'<p class="entry"><i>n</i> = ([^:]*): &nbsp;<span class="nw"><i>m</i><sup>\*</sup> ([^<]*)</span>')
    for cls, ns, v in re.findall(entry, page()):
        remarks += [(n_of(n), *value(v), cls) for n in ns.split(', ')]
    assert len(re.findall(entry, page())) == page().count('<p class="entry">'), 'an entry outside the form'
    # 512 and 1024 stand twice, in the upper rows and as powers of 2 (since 2026-10-27), as the same cell; each remark once
    cells = {n: c for n, lo, hi, c in table}
    assert len(remarks) == len({n for n, *_ in remarks}), remarks
    assert sorted(n for n, c in cells.items() if c) == sorted(n for n, lo, hi, c in remarks if c), (cells, remarks)
    assert all(cells[n] == c for n, lo, hi, c in remarks), [(n, c, cells.get(n)) for n, lo, hi, c in remarks]
    wrong = [(where, n, lo, hi, chart(n)) for where, got in (('table', [t for t in table if t[3]]), ('remark', remarks))
             for n, lo, hi, c in got if [lo, hi] != chart(n)]
    assert not wrong, wrong


def q_citations_match_the_page():
    # Replicata: mstar.js's reasons that cite the page: ["table2"] and ["page", who], as loWhy or hiWhy; and the new
    # results' cells, their provenance classes and titles.
    # Expectata: a ["table2"] column is one of Table 2's n; a ["page", who] column is one of the new results' n.  As
    # hiWhy, who is its cell's title (whose proof).
    fig = re.search(r'<figure>.*?</figure>', page(), re.S).group(0)
    new = ''.join(new_frames(page()))
    value = lambda cell: int(cell) if cell.isdigit() else 2 ** int(re.fullmatch(r'2<sup>(\d+)</sup>', cell).group(1))
    titled = {value(n): (cls, who) for cls, who, n in
              re.findall(r"<td(?: class=\"(a|c|ca|j|s)\")? title='([^']*)'>([^<]*(?:<sup>\d+</sup>)?)</td>", new)}
    titles = {n: who for n, (cls, who) in titled.items() if cls}      # the rest, unclassed, copy Table 2's powers of 2
    # 240 (since 2026-10-20), the 44 multiples of 16 from 304 to 992 (512 written 2^9) and 25 larger powers of 2,
    # 2^17 to 2^72 (6 until 560 reached order 10 on 2026-10-12, 11 until 800 reached order 11 on 2026-10-17, 18
    # until 592, 608 and 656 reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11 on 2026-10-25, 23
    # until 752 and 784 reached order 10 and 832 order 11 on 2026-10-26); and since 1024 reached order 11, later that
    # day, 2^10, 2^11 and 2^12; and since 2026-10-27, when the block reached 1024, 1008.  The unclassed cells, Table
    # 2's powers of 2 (2^3 to 2^8) until then, copy every entry of Table 2 that stands: up to 304 but 240 and 304.
    assert len(titles) == 1 + 44 + 28 + 1, len(titles)
    assert sorted(n for n in titled if n not in titles) == [n for n in range(8, 305, 8) if n not in (240, 304)], titled
    table2 = {n for n, *_ in table_entries()} - set(titles)
    assert len(table2) == 36, sorted(table2)          # 240 and 304 are in both
    cited = 0
    for n, (lo, hi, lw, hw) in enumerate(mstar_data()['cols'], 1):
        for w in (lw, hw):
            if w[0] == 'table2': assert n in table2 | {304}, (n, w); cited += 1
            if w[0] == 'page': assert n in titles, (n, w); cited += 1
        if hw[0] == 'page': assert titles[n] == hw[1], (n, hw, titles[n])
    assert cited, 'mstar.js cites neither table'


def q_claude_and_astra_is_a_category_like_claude_and_bgpw():
    # Replicata: the page's CSS, its legend, the new results' cells and the remarks' entries of 592, 608, 656, 752 and
    # 784.
    # Expectata (2026-10-25, the main session's ruling on dreeves's "a new 'Claude and Astra' category makes sense to
    # me"): as Claude and BGPW's (q_chart_colors_stand_apart), the class ca has no hue of its own: its cells and legend
    # key are stripes of --claude's and --astra's tints over a striped bar, and its glyph ◆✦ is half in each hue; the
    # legend has its key right after Astra's; the cells titled Claude and Astra are 592, 608,
    # 656 and 752, each of class ca with its value; and each of their remarks is an <li class="ca"> marked ◆✦.  (Since
    # 2026-10-26 also 784, credited for the reason 608 and 656 are, and 752 at 10, both by examples of order 10.)
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    tints = ('repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, '
             'color-mix(in oklab, var(--astra) var(--tint), var(--paper)) 0.3rem 0.6rem)')
    bar = 'repeating-linear-gradient(90deg, var(--claude) 0 0.3rem, var(--astra) 0.3rem 0.6rem) bottom / 100% 3px no-repeat'
    half = 'linear-gradient(90deg, var(--claude) 50%, var(--astra) 50%)'
    assert 'td.ca { --glyph: "◆✦"; }' in css
    assert f'td.ca, .key.ca {{ background: {tints}; }}' in css
    assert f'tr.vals td.ca, .key.ca {{ background: {bar}, {tints}; box-shadow: none; }}' in css
    assert (f'tr.ns td.ca::before, .key.ca > span, .remarks li.ca .mk {{ background: {half}; -webkit-background-clip: text; '
            'background-clip: text; color: transparent; }') in css
    text = page()
    assert re.search(r'<li><span class="key a" aria-hidden="true">✦</span>[^\n]*</li>\n'
                     r'    <li><span class="key ca" aria-hidden="true"><span>◆✦</span></span>[^\n]*</li>\n', text)
    new = ''.join(new_frames(text))
    ca = []
    for t in re.findall(r'<table class="block">.*?</table>', new, re.S):
        ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', t, re.S).group(0))
        vs = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', t, re.S).group(0))
        assert len(ns) == len(vs), t
        for (a, n), (b, v) in zip(ns, vs):
            assert ("title='Claude and Astra'" in a) == (a == ' class="ca" title=\'Claude and Astra\'') == (b == ' class="ca"'), (n, a, b)
            if b == ' class="ca"': ca.append((n, v))
    assert ca == [('592', '10'), ('608', '10'), ('656', '10'), ('752', '10'), ('784', '10')], ca
    for n in (592, 608, 656, 752, 784):
        li = re.search(r'<li class="(\w+)">\n      <span class="mk" aria-hidden="true">([^<]*)</span>\n      <p class="entry"><i>n</i> = '
                       + str(n) + r': ', text)
        assert li and li.groups() == ('ca', '◆✦'), (n, li and li.groups())


def q_examples_of_2026_10_25_have_entries_codes_and_sets():
    # Replicata: the remarks' entries of 592, 608, 656 (order 10) and 848, 880, 896, 928, 944, 976, 992 (order 11),
    # each code in them decoded by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by
    # (-1)^m symmetry), the page's sets SClaude[m][n], and mstar.js's columns.
    # Expectata: each n has an entry of its own, "m* = m", in 800's form: its one code block, p_n of order m, whose
    # signs have order exactly m (synthetic division here), symmetric for even m and antisymmetric for odd; the set
    # SClaude[m][n] is exactly that sequence's +1 positions, 0 among them; and mstar.js's column n is [m, m,
    # ["example", "index.html p" + n], hiWhy].
    text, cols = page(), mstar_data()['cols']
    sets = {(int(m), int(n)): {int(t) for t in body.split(',')}
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', text)}
    def order(a):                                  # (x - 1) divides exactly order(a) times: synthetic division
        c, k = list(a), 0
        while not sum(c): c, k = [sum(c[:i + 1]) for i in range(len(c) - 1)], k + 1
        return k
    for n, m in [(592, 10), (608, 10), (656, 10)] + [(n, 11) for n in (848, 880, 896, 928, 944, 976, 992)]:
        li = re.search(r'<li class="\w+">\n      <span class="mk" aria-hidden="true">[^<]*</span>\n      <p class="entry"><i>n</i> = '
                       + str(n) + r': &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = (\d+)</span></p>\n(.*?)\n    </li>', text, re.S)
        assert li and int(li.group(1)) == m, n
        lo, hi, lw, hw = cols[n - 1]
        assert [lo, hi, lw] == [m, m, ['example', f'index.html p{n}']], (n, cols[n - 1])
        codes = re.findall(r'<p class="code">\n        <span><i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n'
                           r'        <code>([0-9A-F]+)</code>\n      </p>', li.group(2))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(m)), (n, codes)
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and order(a) == m, (n, len(a), order(a))
        assert sets[m, n] == {i for i, s in enumerate(a) if s == 1} and 0 in sets[m, n], n


def q_752_bound_cites_proof752():
    # Replicata: the remarks' entry of 752, mstar.js's column 752, and the repository's files.
    # Expectata (2026-10-25: proof752.py proves m*(752) <= 10, extending Astra's method for 384 with Claude's meet in
    # the middle): the entry links proof752.py at its GitHub address; mstar.js's column 752 has hi 10 and hiWhy
    # ["page", "Claude and Astra"]; and proof752.py is in the working directory.  Since 2026-10-26, when Claude's
    # search found an example of order 10 at 752, the entry is "m* = 10" and the column is [10, 10, ["example",
    # "index.html p752"], …].
    li = re.search(r'<p class="entry"><i>n</i> = 752: &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = 10</span></p>\n(.*?)\n    </li>',
                   page(), re.S)
    assert li, 'no entry for 752 alone'
    assert 'href="https://github.com/dreeves/equipow/blob/main/proof752.py"' in li.group(1), li.group(1)[:600]
    assert mstar_data()['cols'][752 - 1] == [10, 10, ['example', 'index.html p752'], ['page', 'Claude and Astra']]
    assert os.path.isfile(os.path.join(HERE, 'proof752.py'))


def q_288_bound_is_proved_here():
    # Replicata: index.html's figure of Table 2 and its remarks under "Where the new results come from", mstar.js's
    # column 288, and the repository's files.
    # Expectata (2026-10-25: proof288.py proves m*(288) <= 10, Table 2's upper value, so no cell changes; 2026-10-27,
    # dreeves, of the note under Table 2 that said so: "can you put that in the 'where the new results come from'
    # section instead and just clarify that that one isn't technically new but is rederived here?"): the figure no
    # longer mentions proof288.py; the remarks have an entry of 288 alone, "m* ∈ {9, 10}", right after 240's and right
    # before 304's, in an <li> without a class and with an empty marker, as 288's cell in the new results has no
    # provenance class (the paper's value), and it links proof288.py at its GitHub address; mstar.js's column 288
    # cites Table 2, [9, 10, …, ["table2"]]; and proof288.py is in the working directory.
    text = page()
    fig = re.search(r'<figure>.*?</figure>', text, re.S).group(0)
    assert 'proof288' not in fig, fig[:600]
    li = re.search(r'<li>\n      <span class="mk" aria-hidden="true"></span>\n      <p class="entry"><i>n</i> = 288: &nbsp;'
                   r'<span class="nw"><i>m</i><sup>\*</sup> ∈ \{9, 10\}</span></p>\n(.*?)\n    </li>', text, re.S)
    assert li and 'href="https://github.com/dreeves/equipow/blob/main/proof288.py"' in li.group(1), li and li.group(1)
    listed = re.findall(r'<p class="entry"><i>n</i> = ([^:]*): ', text)
    assert listed[listed.index('288') - 1:listed.index('288') + 2] == ['240', '288', '304'], listed
    col = mstar_data()['cols'][288 - 1]
    assert col[:2] == [9, 10] and col[3] == ['table2'], col
    assert os.path.isfile(os.path.join(HERE, 'proof288.py'))


def q_examples_of_2026_10_26_have_entries_codes_and_sets():
    # Replicata: the remarks' entries of 752 and 784 (order 10) and 832 (order 11), each code in them decoded by the
    # paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the page's sets
    # SClaude[m][n], the order of the remarks' entries, and mstar.js's columns.
    # Expectata (2026-10-26, the second recording pass): each n has an entry of its own, "m* = m", in the form of the
    # first pass's (q_examples_of_2026_10_25_have_entries_codes_and_sets): its one code block, p_n of order m,
    # whose signs have order exactly m (synthetic division here), symmetric for even m and antisymmetric for odd; the
    # set SClaude[m][n]
    # is exactly that sequence's +1 positions, 0 among them; mstar.js's column n is [m, m, ["example",
    # "index.html p" + n], hiWhy]; no entry lists n with another n; and the entries run in order of n among the
    # examples': 656's, 752's, 784's, 800's, 832's, 848's.
    text, cols = page(), mstar_data()['cols']
    sets = {(int(m), int(n)): {int(t) for t in body.split(',')}
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', text)}
    def order(a):                                  # (x - 1) divides exactly order(a) times: synthetic division
        c, k = list(a), 0
        while not sum(c): c, k = [sum(c[:i + 1]) for i in range(len(c) - 1)], k + 1
        return k
    for n, m in ((752, 10), (784, 10), (832, 11)):
        li = re.search(r'<li class="\w+">\n      <span class="mk" aria-hidden="true">[^<]*</span>\n      <p class="entry"><i>n</i> = '
                       + str(n) + r': &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = (\d+)</span></p>\n(.*?)\n    </li>', text, re.S)
        assert li and int(li.group(1)) == m, n
        lo, hi, lw, hw = cols[n - 1]
        assert [lo, hi, lw] == [m, m, ['example', f'index.html p{n}']], (n, cols[n - 1])
        codes = re.findall(r'<p class="code">\n        <span><i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n'
                           r'        <code>([0-9A-F]+)</code>\n      </p>', li.group(2))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(m)), (n, codes)
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and order(a) == m, (n, len(a), order(a))
        assert sets[m, n] == {i for i, s in enumerate(a) if s == 1} and 0 in sets[m, n], n
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry"><i>n</i> = ([^:]*): ', text)]
    assert [ns for ns in listed if {'752', '784', '832'} & set(ns)] == [['752'], ['784'], ['832']], listed
    run = [ns[0] for ns in listed if ns[0] in ('656', '752', '784', '800', '832', '848')]
    assert run == ['656', '752', '784', '800', '832', '848'], run


def q_example_at_1024_has_its_entry_code_set_and_cell():
    # Replicata: the remarks' entry of 1024, its code decoded by the paper's Table 5 convention (the left half of the
    # signs, 1 = +1, then the rest by (-1)^m symmetry), the page's set SClaude[11][1024], the new results' cells of the
    # powers of 2, and pow2.js's column 2^10.
    # Expectata (2026-10-26: Claude's lattice search found an example of order 11 at 1024; with m*(2^9) = 9 it makes 2^10
    # the first power of 2 to beat Thue-Morse, and the norm bound for 3 caps it at 11): an entry of its own, "m* = 11",
    # an <li class="c"> marked ◆, in the form of the examples' entries (q_examples_of_2026_10_26_have_entries_codes_and_sets),
    # right after 992's, the last of the examples'; its one code block, p1024 of order 11, whose signs have order
    # exactly 11 (synthetic division here) and are antisymmetric; SClaude[11][1024] exactly their +1 positions, 0
    # among them; the cell 2^10, of class c titled Claude alone, value 11, right after 2^9's; and pow2.js's column
    # 2^10 is [11, 11, ["joins", [[[1024, 11]]]], ["mstar", ["norm", 3]]]: since 2026-10-27, when the m*(n) chart
    # reached 1024, its hi is that chart's column 1024 (before, ["norm", 3] by pow2.py's own norm bound, the same one).
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = '
                   r'1024: &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = 11</span></p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 1024 alone'
    codes = re.findall(r'<p class="code">\n        <span><i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n'
                       r'        <code>([0-9A-F]+)</code>\n      </p>', li.group(1))
    assert len(codes) == 1 and codes[0][:2] == ('1024', '11'), codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + [-s for s in reversed(left)], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 1024 and k == 11 and all(a[1023 - i] == -a[i] for i in range(1024)), (len(a), k)
    sets = {(int(m), int(n)): {int(t) for t in body.split(',')}
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', text)}
    assert sets[11, 1024] == {i for i, s in enumerate(a) if s == 1} and 0 in sets[11, 1024]
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry"><i>n</i> = ([^:]*): ', text)]
    assert listed[listed.index(['992']) + 1] == ['1024'], listed
    row = re.search(r'<td title=\'The published paper \(2021\)\'>2<sup>3</sup></td>.*?</tr>\s*<tr class="vals">.*?</tr>',
                    text, re.S).group(0)
    ns = re.findall(r'<td([^>]*)>2<sup>(\d+)</sup></td>', row)
    vals = re.findall(r'<td([^>]*)>([^<]*)</td>', row.split('<tr class="vals">')[1])
    i = [k for _, k in ns].index('10')
    assert ns[i - 1][1] == '9' and ns[i][0] == ' class="c" title=\'Claude alone\'' and vals[i] == (' class="c"', '11'), (ns, vals)
    assert pow2_data()['cols'][9] == [11, 11, ['joins', [[[1024, 11]]]], ['mstar', ['norm', 3]]], pow2_data()['cols'][9]


def q_symmetric_example_at_528():
    # Replicata: the remarks' entry of 528 and its code blocks, each decoded by the paper's Table 5 convention (the left
    # half of the signs, 1 = +1, then the rest by (-1)^m symmetry), and synthetic division by x - 1.
    # Expectata (2026-10-27, dreeves: "sure", to putting a symmetric 528 example on the page; four were found that day
    # by a lattice search, scratch/sym528): the entry keeps the join's code p192 and adds p528 (m = 10), which decodes
    # to a symmetric sequence of length 528, exact order 10, +1 at 0.
    li = re.search(r'<p class="entry"><i>n</i> = 528: .*?</li>', page(), re.S)
    assert li, 'no entry of 528'
    codes = re.findall(r'<i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n\s*<code>([0-9A-F]+)</code>',
                       li.group(0))
    assert [c[:2] for c in codes] == [('192', '9'), ('528', '10')], codes
    h = codes[1][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + left[::-1], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 528 and k == 10 and a == a[::-1] and a[0] == 1, (len(a), k)


def q_1024_doubled_settles_2_11_and_2_12():
    # Replicata: the new results' cells of the powers of 2, the remarks' entries of 2^11 and 2^12, the changelog's
    # statements of 2026-10-26, and pow2.js's columns 2^11 and 2^12.
    # Expectata (2026-10-26: the example of order 11 at 1024 times τ1 and τ2 has orders 12 and 13, which the residue
    # condition mod 3 allows and no more): pow2.js's columns are [12, 12, ["joins", [[[1024, 11], [2, 1]]]],
    # ["residue", [3]]] and [13, 13, ["joins", [[[1024, 11], [4, 2]]]], ["residue", [3]]]; the cells 2^11 and 2^12, of
    # class c titled Claude alone, values 12 and 13, right after 2^10's; each has an entry of its own, "m* = 12" and
    # "m* = 13", whose Claude: "…" names p1024 # τ1 (τ2) and the residue condition mod 3, right before 2^17's; and the
    # changelog states m*(2^11) = 12 and m*(2^12) = 13 on 2026-10-26, together on a line of their own.
    cols, text = pow2_data()['cols'], page()
    assert cols[10] == [12, 12, ['joins', [[[1024, 11], [2, 1]]]], ['residue', [3]]], cols[10]
    assert cols[11] == [13, 13, ['joins', [[[1024, 11], [4, 2]]]], ['residue', [3]]], cols[11]
    row = re.search(r'<td title=\'The published paper \(2021\)\'>2<sup>3</sup></td>.*?</tr>\s*<tr class="vals">.*?</tr>',
                    text, re.S).group(0)
    ns = re.findall(r'<td([^>]*)>2<sup>(\d+)</sup></td>', row)
    vals = re.findall(r'<td([^>]*)>([^<]*)</td>', row.split('<tr class="vals">')[1])
    i = [k for _, k in ns].index('10')
    assert [k for _, k in ns[i:i + 4]] == ['10', '11', '12', '17'], ns
    assert all(a == ' class="c" title=\'Claude alone\'' for a, _ in ns[i + 1:i + 3]), ns
    assert vals[i + 1:i + 3] == [(' class="c"', '12'), (' class="c"', '13')], vals
    listed = re.findall(r'<p class="entry"><i>n</i> = ([^:]*): ', text)
    j = listed.index('2<sup>11</sup>')
    assert listed[j:j + 3] == ['2<sup>11</sup>', '2<sup>12</sup>', '2<sup>17</sup>'], listed
    for k, m, j in ((11, 12, 1), (12, 13, 2)):
        li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = '
                       rf'2<sup>{k}</sup>: &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = {m}</span></p>\n(.*?)\n    </li>', text, re.S)
        assert li, k
        said = re.search(r'<p>Claude: "(.*?)"</p>', li.group(1)).group(1)
        assert f'<i>p</i><sub>1024</sub> # τ<sub>{j}</sub>' in said and 'residue condition mod 3' in said, said
    entries = [(d, statements(rest)) for d, rest in changelog()]
    assert ('2026-10-26', {2 ** 11: (12, 12), 2 ** 12: (13, 13)}) in entries, entries[:4]


def q_example_at_816_has_its_entry_code_and_set():
    # Replicata: the remarks' entries of 720 and 816, 816's code decoded by the paper's Table 5 convention (the left
    # half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the page's set SClaude[11][816], the new results'
    # cells, and mstar.js's columns 720 and 816.
    # Expectata (2026-10-26: Claude's lattice search found an antisymmetric example of order 11 at 816, which the
    # norm bound for the residue sums mod 5 leaves at 11 to 14): 816 has an entry of its own, "m* ∈ {11, …, 14}", an
    # <li class="c"> marked ◆, right after 800's and before 832's, whose Claude: "…" names the norm bound mod 5; its
    # one code block, p816 of order 11, whose signs have order exactly 11 (synthetic division here) and are
    # antisymmetric; SClaude[11][816] exactly their +1 positions, 0 among them; 720's entry alone, "m* ∈ {10, …, 14}"
    # (it shared one with 816 before); the cell 816 of value 11–14; and mstar.js's column 816 is [11, 14, ["example",
    # "index.html p816"], ["norm", 5]].
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = '
                   r'816: &nbsp;<span class="nw"><i>m</i><sup>\*</sup> ∈ \{11, …, 14\}</span></p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 816 alone'
    assert 'norm bound for the residue sums mod 5' in re.search(r'<p>Claude: "(.*?)"</p>', li.group(1)).group(1), li.group(1)[:300]
    codes = re.findall(r'<p class="code">\n        <span><i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n'
                       r'        <code>([0-9A-F]+)</code>\n      </p>', li.group(1))
    assert len(codes) == 1 and codes[0][:2] == ('816', '11'), codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + [-s for s in reversed(left)], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 816 and k == 11 and all(a[815 - i] == -a[i] for i in range(816)), (len(a), k)
    sets = {(int(m), int(n)): {int(t) for t in body.split(',')}
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', text)}
    assert sets[11, 816] == {i for i, s in enumerate(a) if s == 1} and 0 in sets[11, 816]
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry"><i>n</i> = ([^:]*): ', text)]
    i = listed.index(['816'])
    assert listed[i - 1:i + 2] == [['800'], ['816'], ['832']] and ['720'] in listed, listed
    assert re.search(r'<p class="entry"><i>n</i> = 720: &nbsp;<span class="nw"><i>m</i><sup>\*</sup> ∈ \{10, …, 14\}</span></p>', text)
    assert new_cells(text)[816] == (11, 14), new_cells(text)[816]
    assert mstar_data()['cols'][816 - 1] == [11, 14, ['example', 'index.html p816'], ['norm', 5]], mstar_data()['cols'][816 - 1]


def q_816_moves_excess_5_to_2_41():
    # Replicata: pow2.js's columns 2^40 to 2^47, the new results' cells of 2^41, 2^43 and 2^46 and their remarks'
    # entries.
    # Expectata (2026-10-26: with 816 at order 11 among the blocks, the exhaustive search of scratch/wish2/ finds 2^41
    # = (800^2 # 832 # 848 # τ2) ∨ (432^3 # 816 # τ2) ∨ (480^3 # 784) ∨ (432^2 # 480^2), each product of order 46, and no
    # K <= 40 beating Thue-Morse by 5): pow2.js's lo is k + 4 at 2^40 and k + 5 from 2^41 to 2^47, every column from 41
    # to 47 that join, each product times τ_(k−41); the cells read 2^41 46–50, 2^43 48–53 and 2^46 51–57; 2^41's entry
    # says a join of four products of examples above and Thue–Morse, each of order 46, beats Thue–Morse by 5; and 2^43's
    # and 2^46's each name the 2^41 entry, each product times τ2 and τ5, of orders 48 and 51.
    cols, text = pow2_data()['cols'], page()
    base = cols[40][2]
    assert cols[39][0] == 44 and [c[0] - k for k, c in enumerate(cols[40:47], 41)] == [5] * 7, [c[:2] for c in cols[39:47]]
    assert base[0] == 'joins' and sorted(map(sorted, base[1])) == sorted(map(sorted, [
        [[800, 11], [800, 11], [832, 11], [848, 11], [4, 2]], [[432, 11], [432, 11], [432, 11], [816, 11], [4, 2]],
        [[480, 12], [480, 12], [480, 12], [784, 10]], [[432, 11], [432, 11], [480, 12], [480, 12]]])), base
    cells = new_cells(text)
    assert [cells[2 ** k] for k in (41, 43, 46)] == [(46, 50), (48, 53), (51, 57)], [cells[2 ** k] for k in (41, 43, 46)]
    said = {int(k): re.search(r'<p>Claude: "(.*?)"</p>', body).group(1) for k, body in
            re.findall(r'<p class="entry"><i>n</i> = 2<sup>(\d+)</sup>: [^\n]*\n(.*?)\n    </li>', text, re.S)}
    assert 'A join of four products of examples above and Thue–Morse, each of order 46' in said[41], said[41]
    assert 'That beats Thue–Morse by 5' in said[41], said[41]
    for k, j, m in ((43, 2, 48), (46, 5, 51)):
        assert f'The join of the 2<sup>41</sup> entry, each product times τ<sub>{j}</sub>, has order {m}.' in said[k], said[k]


# ---------------------------------------------------------------------------------------------------------------------
# Browser quals

def q_page_loads_clean():
    # Replicata: index.html with the real mstar.js in headless Chrome, 1280 px wide at 2 device px per CSS px; and the
    # page loaded as is (nothing added), with Chrome logging its console to stderr.
    # Expectata: no errors, console errors or warnings; the canvas is drawn (nonzero height, as wide as main's content);
    # the chart opens showing all NCOL = 512 columns, n = 2 to 1024.  The plain
    # load logs nothing at all to the console.
    assert console_lines() == [], console_lines()
    R = valid_run('light')
    assert R['canvasDev'][1] > 0 and close(R['canvasCss'][0], R['mainContentW'], 1), R
    v = R['views'][0]
    assert close(v['u0'], 0, 0.01) and close(v['span'], NCOL, 0.05), v


def q_drawn_cells_match_data():
    # Replicata: the light and phone runs: the full view, and a sweep of the 512 columns n = 2, 4, …, 1024
    # zoomed in, so every column is at least 3 device px wide.
    # Expectata: every even column is checked, in every row: its middle pixel has its color from mstar.js (exists up
    # to lo, open up to hi, impossible above) as the page's tokens give it, and the pixel below each row is paper.  In
    # the full view and every view of the sweep, every pixel of row 1 is exists, from the plot's left edge to its
    # right: no odd column (impossible in every row, since lo = hi = 0) is drawn, not even mixed into a pixel; but for
    # the ring of a cell of row 1 (q_chart_rings_a323395_terms_in_gold), passed over a device px either side
    # (rowOneSkips), and the cells next to a ring in its row and the row above, which that qual checks instead.
    data = mstar_data()
    assert all(data['cols'][n - 1][0] >= 1 for n in EVEN), 'some even column has no exists cell in row 1'
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['pixelBad'] == [], (name, R['pixelBad'][:10])
        assert R['pixelColumns'] == EVEN, (name, sorted(set(EVEN) ^ set(R['pixelColumns']))[:20])
        assert R['pixelChecks'] >= NCOL * len(R['rows']), (name, R['pixelChecks'])
        assert len(R['rows']) == data['mtop'], (name, len(R['rows']))
        assert R['rowOneBad'] == [], (name, len(R['rowOneBad']), R['rowOneBad'][:10])
        assert R['rowOneChecks'] + R['rowOneSkips'] == len(R['views']) * (R['plot'][1] - R['plot'][0]), (name, R['rowOneChecks'])
        assert R['rowOneSkips'] <= len(R['views']) * (4 * R['dpr'] + 6), (name, R['rowOneSkips'])


def q_chart_rings_a323395_terms_in_gold():
    # Replicata: the light and phone runs: the cells the chart rings (R's records), the ring checks of the sweep, and
    # the token --record.
    # Expectata (dreeves, 2026-10-19: "in the chart can you highlight the known values for a(m-1)? maybe make those
    # green with gold trim or whatever else you think might work visually"): the ringed cells are exactly
    # a323395_cells of mstar.js, today (2, 1), (4, 2), (8, 3), (16, 4), (32, 5), (48, 6), (96, 7), (144, 8), (192, 9)
    # (240, 10) and (432, 11), SMALLEST_PROVEN by order; each is ringed in --record, #ffb300 (the validator's pick against
    # the chart's three colors and the paper), just outside its left and right and below it, in each view of the
    # sweep that checks it, and every one is checked.  (Its readout's note: q_hover_reads_out_cells.)
    want = a323395_cells(mstar_data()['cols'])
    assert want == [(n, m) for m, n in enumerate(SMALLEST_PROVEN, 1)], want
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert [tuple(c) for c in R['records']] == want, (name, R['records'])
        assert R['tokens']['record'] == '#ffb300', (name, R['tokens'])
        assert R['ringChecks'] >= len(want) and R['ringBad'] == [], (name, R['ringChecks'], R['ringBad'][:5])
        assert sorted(map(int, R['ringed'])) == [n for n, _ in want], (name, R['ringed'])


def q_readout_reports_even_n_only():
    # Replicata: the light and phone runs: every hover of the harness (the full view, every view of the sweep, the
    # searches for column edges, which probe within a millionth of a px of them, and the interactions), and a hover at
    # the middle of every device px across row 1 of the full view.
    # Expectata: no readout reports an odd n; across the full view the readout goes through n = 2, 4, …, 1024, each
    # once, in order from left to right.
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['oddReadouts'] == [] and R['readouts'] > 2 * NCOL, (name, R['readouts'], R['oddReadouts'][:5])
        assert R['across'] == EVEN, (name, R['across'][:20])


def q_n_labels_are_even_and_round():
    # Replicata: the n labels (the strings drawn below the rows, right of the plot's left edge) of one draw in each of
    # the full view, every view of the sweep, and the view zoomed in as far as it goes; in the light and phone runs.
    # Expectata: they are the multiples of one step s, from 2, 10, 20, 50, 100, 200, 500 (so every label is an even n),
    # whose columns' middles are in view, in order, each centered on its column's middle to within a device px; s is
    # the first of those steps that puts the labels at least 48 CSS px apart.
    for name in ('light', 'phone'):
        R = valid_run(name)
        (PL, PR), dpr = R['plot'], R['dpr']
        assert len(R['labelDraws']) == len(R['views']) + 1, (name, len(R['labelDraws']))
        for d in R['labelDraws']:
            v, got = d['v'], d['labels']
            s = next(s for s in STEPS if s / 2 * (PR - PL) / dpr / v['span'] >= 48)
            want = [n for n in range(s, NMAX + 1, s) if v['u0'] - 1e-6 <= n / 2 - 0.5 <= v['u0'] + v['span'] + 1e-6]
            assert [t for t, _ in got] == [str(n) for n in want], (name, v, s, got)
            for t, x in got:
                assert close(x, PL + (int(t) / 2 - 0.5 - v['u0']) * (PR - PL) / v['span'], 1), (name, v, t, x)


def q_zoom_buttons_sit_beside_show_all():
    # Replicata: the chart's section.
    # Expectata: right before the reset button, with only blank space and comments between, a zoom-out button labelled
    # − and then a zoom-in button labelled + (math, not English), each with an aria-label.
    s = section()
    tags = {i: re.search(rf'<button type="button" id="{i}"([^>]*)>([^<]*)</button>', s)
            for i in ('mstar-zoom-out', 'mstar-zoom-in', 'mstar-reset')}
    assert all(tags.values()), {i: bool(t) for i, t in tags.items()}
    out, zin, reset = tags.values()
    for a, b in ((out, zin), (zin, reset)):
        assert re.fullmatch(r'(?:\s|<!--.*?-->)*', s[a.end():b.start()], re.S), s[a.end():b.start()]
    for t, label in ((out, '−'), (zin, '+')):
        attrs, text = t.groups()
        assert text == label, (t.group(0), label)
        assert re.search(r"\baria-label='[^']+'", attrs), attrs


def q_zoom_buttons_zoom_about_the_middle():
    # Replicata: the light run: the zoom buttons at load; a click of each from a view zoomed in 3 steps; then, from the
    # full view, clicks of + until it is disabled and then of − until it is disabled, the view measured after each; and
    # the buttons after every interaction step (keys, wheels, drags, pinches, gestures, reset).
    # Expectata: + zooms in by 1.5 and − out by 1.5 about the middle (the u at the middle stays), as the + and − keys do,
    # stopping at 12 and 512 columns: 10 clicks each way.  + is disabled exactly when the view is 12 columns and −
    # exactly when it is all 512: at load (− only), after every click and after every step (so − after the reset
    # button).  A disabled button is grayed out, not hidden: opacity at most 0.5 but displayed, visible and as big as
    # the other, whose opacity is 1.
    R = valid_run('light')
    assert 'buttonsError' not in R, R['buttonsError']
    S = R['steps']
    for name, f in (('zoomInButton', 1 / 1.5), ('zoomOutButton', 1.5)):
        a, b = S[name]['a'], S[name]['b']
        assert close(b['span'], a['span'] * f, 1e-3) and close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (name, S[name])
    clicks = R['clicks']
    assert [k for k, *_ in clicks] == ['start'] + ['in'] * 10 + ['out'] * 10, [k for k, *_ in clicks]
    for (_, a, _), (kind, b, _) in zip(clicks, clicks[1:]):
        want = min(max(a['span'] * (1 / 1.5 if kind == 'in' else 1.5), MIN_SPAN), NCOL)
        assert close(b['span'], want, 1e-3) and close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (a, kind, b)
    states = [(v, d) for _, v, d in clicks] + [(s['b'], s['disabled']) for s in S.values()] + [(R['views'][0], R['disabled0'])]
    for v, d in states:
        assert d == [close(v['span'], MIN_SPAN, 0.01), close(v['span'], NCOL, 0.05)], (v, d)
    zin, zout = R['looks0']
    assert zin['opacity'] == 1 and zout['opacity'] <= 0.5 and zout['display'] != 'none' and zout['visibility'] == 'visible', R['looks0']
    assert all(close(a, b, 2) for a, b in zip(zout['size'], zin['size'])) and min(zout['size']) > 10, R['looks0']


def q_light_run_uses_the_theme_tokens():
    # Replicata: the light run.
    # Expectata: the chart's colors, paper and ink are the theme block's values (the pixel checks of
    # q_drawn_cells_match_data compare against these).  (A dark run did the same for the dark blocks until 2026-10-12.)
    light, = theme_blocks()
    tokens = valid_run('light')['tokens']
    assert all(tokens[t[2:]] == light[t].lower() for t in TOKENS + ('--paper', '--ink')), tokens


def q_hover_reads_out_cells():
    # Replicata: the light run's hovers: the middle of cells lo, lo + 1 and hi + 1 of every column, in the full view
    # and zoomed in; and the kinds run's, on made-up data with every kind of reason.
    # Expectata: each readout is "n = N, m = M · BOUNDS · REASONS" for the hovered cell, BOUNDS being "m*(N) = lo"
    # when lo = hi and "lo ≤ m*(N) ≤ hi" otherwise; REASONS are Claude: "…" strings: for a green cell (m ≤ lo) one
    # that starts "order lo ", for a red cell (m > hi) one that starts "order hi+1 ", for a gray cell both, joined by
    # " · "; and for a cell ringed in gold (a323395_cells, since 2026-10-19) one more, ring_note.  Every column, n = 2,
    # 4, …, 1024, is read out in both runs.
    for name in ('light', 'kinds'):
        R = valid_run(name)
        cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols'] if name == 'kinds' else mstar_data()['cols']
        assert {n for n, _, _ in R['hovers']} == set(EVEN), name
        rings = a323395_cells(cols)
        for n, m, text in R['hovers']:
            lo, hi = cols[n - 1][:2]
            bounds = f'm*({n}) = {lo}' if lo == hi else f'{lo} ≤ m*({n}) ≤ {hi}'
            reasons = [f'order {lo} '] * (m <= hi) + [f'order {hi + 1} '] * (m > lo) + [ring_note(m)] * ((n, m) in rings)
            got = re.fullmatch(r'n = (\d+), m = (\d+) · (.*?) · (Claude: ".*")', text)
            assert got and (int(got[1]), int(got[2]), got[3]) == (n, m, bounds), (name, n, m, text)
            parts = re.findall(r'Claude: "([^"]*)"', got[4])
            assert ' · '.join(f'Claude: "{p}"' for p in parts) == got[4], (name, text)
            assert len(parts) == len(reasons) and all(p.startswith(r) for p, r in zip(parts, reasons)), (name, n, m, text)


def q_hover_swatch_matches_gold_trim():
    # Replicata: the light and kinds runs' hover sweeps, sampling the readout swatch after each cell selection.
    # Expectata: all proven OEIS cells (all 11 in the real data) have a 2 px gold ring on their swatch, every other
    # swatch has no ring, and its fill retains the cell's exists/open/impossible color.  The sweeps include both
    # directions of transition between record and ordinary cells, so a ring cannot persist after leaving a record.
    # Resultata: each assertion reports the hovered cell and its expected and computed CSS values.
    rgb = lambda h: 'rgb(' + ', '.join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5)) + ')'
    assert a323395_cells(mstar_data()['cols']) == [(n, m) for m, n in enumerate(SMALLEST_PROVEN, 1)]
    for name in ('light', 'kinds'):
        R = valid_run(name)
        cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols'] if name == 'kinds' else mstar_data()['cols']
        rings = set(a323395_cells(cols))
        swatches = R['swatches']
        assert rings <= {(n, m) for n, m, _, _ in swatches}, (name, rings, swatches)
        assert {(False, True), (True, False)} <= {
            (tuple(a[:2]) in rings, tuple(b[:2]) in rings) for a, b in zip(swatches, swatches[1:])}, name
        assert {0, 1, 2} == {(m <= cols[n - 1][0]) + (m <= cols[n - 1][1])
                            for n, m, _, _ in swatches if (n, m) not in rings}, name
        shadows = {False: 'none', True: rgb(R['tokens']['record']) + ' 0px 0px 0px 2px'}
        for n, m, fill, shadow in swatches:
            lo, hi = cols[n - 1][:2]
            kind = ('impossible', 'open', 'exists')[(m <= lo) + (m <= hi)]
            want = (rgb(R['tokens'][kind]), shadows[(n, m) in rings])
            assert (fill, shadow) == want, (name, n, m, 'expected', want, 'computed', (fill, shadow))


def q_canvas_draws_only_numbers():
    # Replicata: every string the kinds and light runs drew on the canvas.
    # Expectata: each is a number or the single letter n or m, the axes' names: the chart's words are in its HTML.
    for name in ('kinds', 'light'):
        R = valid_run(name)
        assert R['texts'] and all(re.fullmatch(r'\d+|[nm]', t) for t in R['texts']), (name, R['texts'])


def q_keys_pan_and_zoom():
    # Replicata: from a view zoomed in 3 steps, with the canvas focused: one keydown each of ArrowRight, ArrowLeft, +,
    # =, -, ArrowDown, ctrl and +, cmd and ArrowRight.
    # Expectata: the arrows pan by an eighth of the view (u0 ± span/8) without zooming; + and = zoom in by 1.5 and -
    # out by 1.5, about the middle; those keys' default actions are prevented.  ArrowDown, ctrl + and cmd ArrowRight
    # change nothing and keep their default actions (page scroll, browser zoom, history).
    S = valid_run('light')['steps']
    for name, sign in (('right', 1), ('left', -1)):
        a, b, prevented = S[name]['a'], S[name]['b'], S[name]['x']
        assert prevented and close(b['span'], a['span'], 1e-3) and close(b['u0'] - a['u0'], sign * a['span'] / 8, 1e-3), (name, S[name])
    for name, f in (('plus', 1 / 1.5), ('equals', 1 / 1.5), ('minus', 1.5)):
        a, b, prevented = S[name]['a'], S[name]['b'], S[name]['x']
        assert prevented and close(b['span'], a['span'] * f, 1e-3), (name, S[name])
        assert close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (name, S[name])
    for name in ('down', 'ctrlPlus', 'metaRight'):
        a, b, prevented = S[name]['a'], S[name]['b'], S[name]['x']
        assert not prevented and close(b['u0'], a['u0'], 1e-3) and close(b['span'], a['span'], 1e-3), (name, S[name])


def q_wheel_zooms_and_pans_but_lets_the_page_scroll():
    # Replicata: from a view zoomed in 3 steps, at about 30% of the plot's width (Chrome rounds a synthetic wheel's
    # position to a whole px): ctrl + wheel up 100 px; cmd + wheel down 50 px; ctrl + wheel up 3 lines; a wheel 60 px
    # right and 5 down; a wheel 100 px down and 2 right.
    # Expectata: ctrl and cmd zoom by 2^(delta in px / 100) (a line is 16 px) about the pointer: the u under it stays;
    # the mostly-sideways wheel pans by its 60 px; all four have their default prevented.  The mostly-down wheel changes
    # nothing and is not prevented, so the page scrolls.
    S = valid_run('light')['steps']
    for name, f in (('ctrlWheel', 0.5), ('metaWheel', 2 ** 0.5), ('lineWheel', 2 ** -0.48)):
        a, b, (prevented, x) = S[name]['a'], S[name]['b'], S[name]['x']
        assert prevented and close(b['span'], a['span'] * f, 1e-3) and close(x, 0.3, 0.01), (name, S[name])
        assert close(a['u0'] + x * a['span'], b['u0'] + x * b['span'], 1e-3), (name, S[name])
    a, b, (prevented, _) = S['sideWheel']['a'], S['sideWheel']['b'], S['sideWheel']['x']
    R = valid_run('light')
    W = (R['plot'][1] - R['plot'][0]) / R['dpr']
    assert prevented and close(b['span'], a['span'], 1e-3) and close(b['u0'] - a['u0'], 60 * a['span'] / W, 1e-3), S['sideWheel']
    a, b, (prevented, _) = S['upWheel']['a'], S['upWheel']['b'], S['upWheel']['x']
    assert not prevented and close(b['u0'], a['u0'], 1e-6) and close(b['span'], a['span'], 1e-6), S['upWheel']


def q_drag_and_touch_pan_and_pinch():
    # Replicata: from a view zoomed in 3 steps: a mouse drag 100 px left; a one-finger touch swipe 20% of the plot left;
    # a two-finger pinch from 40% and 60% of the plot's width out to 30% and 70%; then the canvas's touch-action.
    # Expectata: the drag and the swipe pan by their distance (content follows the pointer); the pinch zooms in about
    # the fingers' midpoint by (d0 + 1) / (d + 1), d0 and d the fingers' spread in px before and after, and the u under
    # the midpoint stays; touch-action is pan-y, so vertical swipes still scroll the page.
    R = valid_run('light')
    S, W = R['steps'], (R['plot'][1] - R['plot'][0]) / R['dpr']
    for name in ('drag', 'swipe'):
        a, b, dx = S[name]['a'], S[name]['b'], S[name]['x']
        assert close(b['span'], a['span'], 1e-3) and close(b['u0'] - a['u0'], dx * a['span'] / W, 1e-3), (name, S[name])
    a, b, (d0, d, xm) = S['pinch']['a'], S['pinch']['b'], S['pinch']['x']
    assert close(b['span'], a['span'] * (d0 + 1) / (d + 1), 1e-3), S['pinch']
    assert close(a['u0'] + xm * a['span'] / W, b['u0'] + xm * b['span'] / W, 1e-3), S['pinch']
    assert R['touchAction'] == 'pan-y', R['touchAction']


def q_safari_gestures_zoom_unless_touching():
    # Replicata: from a view zoomed in 3 steps: Safari's gesturestart, gesturechange (scale 2) and gestureend at 25% of
    # the plot's width; then the same while a touch pointer is down.
    # Expectata: the first zooms in by 2 about the pointer, with gesturestart's and gesturechange's defaults prevented;
    # the second changes nothing (the pointer events own a touch pinch), defaults still prevented.
    R = valid_run('light')
    S, W = R['steps'], (R['plot'][1] - R['plot'][0]) / R['dpr']
    a, b, (p1, p2, _, x) = S['gesture']['a'], S['gesture']['b'], S['gesture']['x']
    assert p1 and p2 and close(b['span'], a['span'] / 2, 1e-3), S['gesture']
    assert close(a['u0'] + x * a['span'] / W, b['u0'] + x * b['span'] / W, 1e-3), S['gesture']
    a, b, (p1, p2) = S['gestureWhileTouching']['a'], S['gestureWhileTouching']['b'], S['gestureWhileTouching']['x']
    assert p1 and p2 and close(b['span'], a['span'], 1e-6) and close(b['u0'], a['u0'], 1e-6), S['gestureWhileTouching']


def q_view_stays_within_limits():
    # Replicata: from a view zoomed in 3 steps: 40 presses of +; of -; 300 of ArrowRight; ctrl + wheel down 5000 px;
    # and (separately) ArrowRight, +, then the reset button.
    # Expectata: zooming in stops at 12 columns and out at all 512; panning stops with n = 1024 at the right edge; the
    # reset button shows all 512 columns, n = 2 to 1024.
    S = valid_run('light')['steps']
    assert close(S['zoomInFar']['b']['span'], MIN_SPAN, 0.01), S['zoomInFar']
    for name in ('zoomOutFar', 'wheelOutFar', 'reset'):
        assert close(S[name]['b']['span'], NCOL, 0.05) and close(S[name]['b']['u0'], 0, 0.01), (name, S[name])
    b = S['panFar']['b']
    assert close(b['u0'] + b['span'], NCOL, 0.01), S['panFar']


def q_tap_and_outline():
    # Replicata: in a zoomed view, a touch tap at 37% of the plot's width in row 1 (after hovering elsewhere), then a
    # pointerup with no pointerdown, then a mouse click (down and up, no move) at 63% in row 1 (after hovering
    # elsewhere); and, in a view zoomed in 5 steps, a hover over the middle of the middle column's cell in row 2.
    # Expectata: the tap and the click each read out the cell under them (an even n) and the stray pointerup changes
    # nothing; the hovered cell keeps its color in the middle and is outlined in ink just outside its left and right
    # edges.
    R = valid_run('light')
    n, m = R['tap']['want']
    assert R['tap']['text'].startswith(f'n = {n}, m = {m} · ') and R['tap']['after'] == R['tap']['text'], R['tap']
    n, m = R['click']['want']
    assert R['click']['text'].startswith(f'n = {n}, m = {m} · '), R['click']
    o = R['outline']
    assert R['outlineText'].startswith(f'n = {o["n"]}, m = {o["m"]} · '), R['outlineText']
    assert o['middle'] == o['want'] and o['left'] == o['ink'] and o['right'] == o['ink'], o


def q_phone_has_no_sideways_scroll():
    # Replicata: index.html with the real mstar.js, 390 px wide at 3 device px per CSS px.
    # Expectata: no errors; the page is no wider than the window; the canvas is as wide as main's content.
    R = valid_run('phone')
    assert R['scrollW'] <= R['innerW'] and close(R['canvasCss'][0], R['mainContentW'], 1), R


def q_missing_data_says_so():
    # Replicata: index.html with no mstar.js beside it.
    # Expectata: the canvas stays 0 px tall and the readout gives the error, which names MSTAR; the failed script load
    # and the uncaught error are recorded (the chart fails loudly).
    R = run('missing')
    assert 'harnessError' not in R, R['harnessError']
    assert R['canvasDev'][1] == 0 and R['canvasCss'][1] == 0, R
    assert re.search(r'\bMSTAR\b', R['readout0']), R['readout0']
    assert any('script failed to load' in e for e in R['errors']) and any('MSTAR' in e for e in R['errors']), R['errors']


def q_malformed_data_fails_loudly():
    # Replicata: made-up data whose column 100 has lo = 5 > hi = 3.
    # Expectata: the canvas stays 0 px tall; the readout gives the error, which quotes column 100 as JSON; the error is
    # uncaught (recorded).
    R = run('violates lo above hi')
    assert 'harnessError' not in R, R['harnessError']
    assert R['canvasDev'][1] == 0 and R['canvasCss'][1] == 0, R
    assert '[100,[5,3,' in R['readout0'], R['readout0']
    assert any('[100,[5,3,' in e for e in R['errors']), R['errors']


def q_contract_violations_fail_loudly():
    # Replicata: made-up data broken in one way each (VIOLATIONS): lo above hi; an unknown kind of reason; a reason with too few
    # arguments; a join of lengths that do not add up to n; a join or product claiming more than its parts give; "two"
    # with the wrong hi; "norm" for a prime dividing n, and for a composite; "table2" at an n not in Table 2; "page" for
    # a provenance the page does not use; an example with an empty label; "none" or "odd" at an even n; an example at
    # an odd n; a column of five entries; hi at mtop; mtop above max hi + 1; nmax not 1024.
    # Expectata: in each case the canvas stays 0 px tall and the readout ends with the error, which quotes the
    # offending column as JSON (or mtop, or nmax and mtop), and the error is uncaught.
    for v, (_, quoted) in VIOLATIONS.items():
        R = run(f'violates {v}')
        assert 'harnessError' not in R and R['canvasDev'][1] == 0 and R['canvasCss'][1] == 0, (v, R)
        assert R['readout0'].endswith(f'Error: {quoted}'), (v, R['readout0'])
        assert R['errors'] == [f'error: Uncaught Error: {quoted}'], (v, R['errors'])


def q_made_up_data_draws():
    # Replicata: made-up data that uses every kind of reason (kinds_data).
    # Expectata: no errors; the chart is drawn with one row per m up to mtop.
    R = valid_run('kinds')
    assert R['canvasDev'][1] > 0 and len(R['rows']) == 8, R['rows']


# ---------------------------------------------------------------------------------------------------------------------
# The section "Search progress" (dreeves, 2026-10-17: "make it a collapsible section of index.html -- no separate
# progress page -- and have it do something less crude than reloading the page every minute"), which draws
# progress.py's data file, progress.js (its contract: progress.js_text).

STATUSES = ('settled', 'open', 'split', 'pending', 'running')
# made-up data: one running run, three groups, every status, three recorded ETAs an hour apart
PROGRESS_DATA = {'made': 1792200000, 'runs': [{
    'program': 'overnight_v5.py', 'n': 64, 'order': 7, 'state': 'running', 'outcome': None, 'so_far': 7200.0, 'to_go': {'median': 3600.0, 'lo': 1800.0, 'hi': 10800.0},
    'etas': [[1792192800, 0.0, 10800.0, 7200.0, 14400.0], [1792196400, 3600.0, 7200.0, 3600.0, 10800.0],
             [1792200000, 7200.0, 3600.0, 1800.0, 10800.0]],
    'statuses': list(STATUSES), 'depth': 1, 'keys': ['3:[0,0,3]', '3:[1,1,1]', '3:[2,1,0]'],
    'groups': ['0123', '4', '00110'], 'counts': {'settled': 4, 'open': 3, 'split': 1, 'pending': 1, 'running': 1}}]}
# progress.html's ETA chart case (quals_progress.eta_chart_case): 13.2 h of running, ended, ETAs of [2, 1, 4] h at
# its start and [1, 0.5, 3] h at its end
PROGRESS_ETA_DATA = {'made': 1792200000, 'runs': [dict(PROGRESS_DATA['runs'][0], state='ended', so_far=47520.0, to_go=None,
                                                       etas=[[1792100000, 0.0, 7200.0, 3600.0, 14400.0],
                                                             [1792192160, 47520.0, 3600.0, 1800.0, 10800.0]])]}
# two runs, the second the first as boxsplit.py's pass with no ETA recorded yet (dreeves, 2026-10-17: a second block for
# 240@11's boxsplit pass)
PROGRESS_TWO = {'made': 1792200000, 'runs': [PROGRESS_DATA['runs'][0], dict(PROGRESS_DATA['runs'][0], program='boxsplit.py', to_go=None, etas=[])]}
# two long runs (dreeves, 2026-10-23: "this would be more helpful as days or years when over like 48 or maybe 72h, and
# the parenthetical needs disambiguation when >1week"): 480:14's of that day, 14.2 h so far and 3596.5–56401.4 h to go
# (median 7500 h), its last two ETAs an hour apart; and a run 100 h along with 0.5–3.0 h to go
HOURS = 3600.0
PROGRESS_LONG = {'made': 1792200000, 'runs': [
    dict(PROGRESS_DATA['runs'][0], so_far=14.2 * HOURS, to_go={'median': 7500 * HOURS, 'lo': 3596.5 * HOURS, 'hi': 56401.4 * HOURS},
         etas=[[1792196400, 13.2 * HOURS, 7400 * HOURS, 3550 * HOURS, 55000 * HOURS],
               [1792200000, 14.2 * HOURS, 7500 * HOURS, 3596.5 * HOURS, 56401.4 * HOURS]]),
    dict(PROGRESS_DATA['runs'][0], so_far=100 * HOURS, to_go={'median': 1 * HOURS, 'lo': 0.5 * HOURS, 'hi': 3 * HOURS},
         etas=[[1792196400, 99 * HOURS, 2 * HOURS, 1 * HOURS, 4 * HOURS], [1792200000, 100 * HOURS, 1 * HOURS, 0.5 * HOURS, 3 * HOURS]])]}
# a run whose band stays within the y axis's cap (2026-10-23): 10 h so far and 1.5–2.5 h to go (median 2 h), so the
# projected finish is 12 h and the cap 13.2 h, above elapsed + ETA's band top, 12.5 h
PROGRESS_NARROW = {'made': 1792200000, 'runs': [dict(PROGRESS_DATA['runs'][0], so_far=10 * HOURS,
    to_go={'median': 2 * HOURS, 'lo': 1.5 * HOURS, 'hi': 2.5 * HOURS},
    etas=[[1792196400, 9 * HOURS, 2 * HOURS, 1.5 * HOURS, 2.5 * HOURS], [1792200000, 10 * HOURS, 2 * HOURS, 1.5 * HOURS, 2.5 * HOURS]])]}
PROGRESS_EARLY = '<script>window.PROGRESS_POLL_MS = 1000;</script>\n'      # a 1 s poll, for the quals
# a browser that last left the section open (dreeves, 2026-10-17: "i keep having to re-expand the search progress
# section", Live Server reloading the page as files change), set before the page's scripts run
PROGRESS_REMEMBERED = '<script>localStorage.setItem("progress-open", "1");</script>\n'
NNBSP = '\u202f'                               # the narrow no-break space between a number and its unit h (2026-10-17)
EMSP = '\u2003'                                # the em space after a snapshot line's time (dreeves, 2026-10-17: "some whitespace")


def stamp(t):
    """A time as the section gives a snapshot's: local, YYYY-MM-DD HH:MM:SS."""
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))


def ampm(t):
    """A time as the section's status line gives it: local 12-hour hours without a leading zero, minutes, am or pm."""
    lt = time.localtime(t)
    return f'{lt.tm_hour % 12 or 12}:{lt.tm_min:02d}{"am" if lt.tm_hour < 12 else "pm"}'


WEEK = 7 * 86400                               # seconds; a finish time a week or more on is a date (dreeves, 2026-10-23)


def finish(t, t1, t2):
    """The status line's finish times, of a snapshot at t: the first's weekday, the first, a spaced en dash, the second's
    weekday only when its date differs, the second; but an end a week or more after t as its local date, YYYY-MM-DD
    (dreeves, 2026-10-23: "the parenthetical needs disambiguation when >1week")."""
    day = lambda s: time.strftime('%a', time.localtime(s))
    date = lambda s: time.strftime('%Y-%m-%d', time.localtime(s))
    first = f'{day(t1)} {ampm(t1)}' if t1 - t < WEEK else date(t1)
    second = f'{"" if date(t1) == date(t2) else day(t2) + " "}{ampm(t2)}' if t2 - t < WEEK else date(t2)
    return f'{first} – {second}'
# The harness: notes what has loaded, opens the section, waits 3.5 s, reads each dot's middle pixel, the key's counts,
# the state line and the times, the time bar's parts, the subtrees' blocks and the ETA chart (its markup at rest), hovers over the third
# group's first dot and over the ETA chart's second record, gives progressData a changed snapshot (one dot running ->
# open), then closes the section and waits 3.5 s more; its report goes into <pre id="harness-out">.
PROGRESS_HARNESS = """<script>
(async () => {
  const out = {};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const section = document.querySelector('section.progress'), details = section.querySelector('details');
  const view = () => window.progressView;
  const pixel = (gi, j) => {
    const [x, y, size] = view().layouts[0].place(gi, j);
    const p = section.querySelector('canvas').getContext('2d').getImageData(x + (size >> 1), y + (size >> 1), 1, 1).data;
    return [p[0], p[1], p[2]];
  };
  const counts = () => Object.fromEntries([...section.querySelectorAll('[data-count]')].map(e => [e.dataset.count, e.textContent]));
  try {
    window.harnessMarker = 'kept';
    out.before = {open: details.open, loads: view().loads, renders: view().renders,
                  scripts: [...document.scripts].filter(s => /progress[.]js/.test(s.getAttribute('src') || '')).length};
    out.stored = {before: localStorage.getItem('progress-open')};
    details.open = true;
    await sleep(3500);
    out.opened = {loads: view().loads, renders: view().renders};
    out.stored.opened = localStorage.getItem('progress-open');
    const run = view().data.runs[0];
    out.dots = run.groups.flatMap((g, gi) => [...g].map((c, j) => [+c, pixel(gi, j)]));
    const css = getComputedStyle(section);
    out.colors = run.statuses.map(s => css.getPropertyValue('--progress-' + s).trim());
    out.counts = counts();
    const squeeze = t => t.replace(/[ \\t\\n\\r]+/g, ' ').trim();       // ASCII whitespace only: U+202F, before a unit, is text
    out.state = [...section.querySelectorAll('[data-state]')].filter(e => !e.hidden).map(e => squeeze(e.textContent));
    out.made = section.querySelector('[data-made]').textContent;
    out.heads = [...section.querySelectorAll('.progress-runs h3')].map(h => h.textContent.replace(/\\s+/g, ' ').trim());
    out.etaDisplays = [...section.querySelectorAll('.progress-runs .progress-eta')].map(e => getComputedStyle(e).display);
    out.age = section.querySelector('[data-age]').textContent;
    const canvas = section.querySelector('canvas'), L = view().layouts[0], [hx, hy] = L.place(2, 0);
    const box = canvas.getBoundingClientRect(), dpr = canvas.width / box.width;
    canvas.dispatchEvent(new MouseEvent('mousemove', {clientX: box.left + (hx + L.size / 2) / dpr, clientY: box.top + (hy + L.size / 2) / dpr, bubbles: true}));
    out.readout = section.querySelector('[data-readout]').textContent.replace(/\\s+/g, ' ').trim();
    out.bar = Object.fromEntries([...section.querySelectorAll('[data-bar]')].map(e => [e.dataset.bar, e.style.width || e.style.left]));
    out.blocks = {rects: L.rects, cols: L.cols, rows: L.rows};
    const fig = section.querySelector('.progress-eta'), svg = fig.querySelector('svg');
    const text = sel => squeeze(fig.querySelector(sel).textContent);
    out.eta = {hidden: fig.hidden, widths: [svg.getBoundingClientRect().width, section.querySelector('canvas').getBoundingClientRect().width],
               togo: fig.querySelector('[data-togo]').getAttribute('points').trim().split(/\\s+/).length,
               labels: svg.querySelectorAll('text.label').length};
    out.etaSvg = svg.outerHTML;
    out.etaTextStrokes = [...svg.querySelectorAll('text')].map(t => [t.getAttribute('class'), t.textContent, getComputedStyle(t).stroke, getComputedStyle(t).paintOrder]);
    const status = section.querySelector('.progress-run [data-state]').parentElement, shown = [...status.children].find(e => !e.hidden);
    out.status = {afterChart: !fig.contains(status) && !!(fig.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING),
                  colors: [...shown.querySelectorAll('.spent, .togo, .total')].map(e => [e.className, getComputedStyle(e).color]),
                  ink: getComputedStyle(shown).color,
                  when: getComputedStyle(section.querySelector('.progress-run [data-state="running"] [data-when]')).color,
                  legends: section.querySelectorAll('.progress-eta-keys').length};
    const tipEl = fig.querySelector('[data-tip]');
    out.tipRest = {visibility: getComputedStyle(tipEl).visibility, height: tipEl.getBoundingClientRect().height};
    const top0 = status.getBoundingClientRect().top;
    const sb = svg.getBoundingClientRect();
    svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + L.etaXs[1] * sb.width / 640, clientY: sb.top + sb.height / 2, bubbles: true}));
    out.eta.tip = getComputedStyle(tipEl).visibility === 'visible' ? text('[data-tip]') : null;
    out.jump = status.getBoundingClientRect().top - top0;
    svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + L.etaXs[L.etaXs.length - 1] * sb.width / 640, clientY: sb.top + sb.height / 2, bubbles: true}));
    out.eta.tipLast = text('[data-tip]');
    out.eta.sameMarkup = tipEl.innerHTML === status.querySelector('[data-state="running"]').innerHTML;
    out.eta.projectedAtRecord = tipEl.classList.contains('projected');
    const xAt = h => L.etaXs[0] + h * (L.etaXs[1] - L.etaXs[0]);      // viewBox x at h hours: PROGRESS_DATA's records sit at 0, 1, 2 h
    svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + xAt(2.5) * sb.width / 640, clientY: sb.top + sb.height / 2, bubbles: true}));
    out.eta.tipAhead = text('[data-tip]');
    out.eta.ahead = {projected: tipEl.classList.contains('projected'), style: getComputedStyle(tipEl).fontStyle,
                     cross: Number(fig.querySelector('[data-cross]').getAttribute('x1')), want: xAt(2.5)};
    out.jumpAhead = status.getBoundingClientRect().top - top0;
    const d2 = JSON.parse(JSON.stringify(view().data));
    d2.made += 60; d2.runs[0].groups[1] = '1'; d2.runs[0].counts.running -= 1; d2.runs[0].counts.open += 1;
    window.progressData(d2);
    out.changed = {renders: view().renders, pixel: pixel(1, 0), counts: counts(), marker: window.harnessMarker};
    details.open = false;
    await sleep(100);
    const atClose = view().loads;
    await sleep(3500);
    out.closed = {atClose, loads: view().loads};
    out.stored.closed = localStorage.getItem('progress-open');
  } catch (e) { out.harnessError = String(e && e.stack || e); }
  const pre = document.createElement('pre');
  pre.id = 'harness-out';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
})();
</script>
"""
PROGRESS_RUNS = {}                             # progress_run's reports, by case, made once per process


def progress_run(case='main'):
    """The harness's report on index.html with the case's data (main: PROGRESS_DATA; eta: PROGRESS_ETA_DATA; two:
    PROGRESS_TWO; long: PROGRESS_LONG; narrow: PROGRESS_NARROW; remembered: PROGRESS_DATA, with PROGRESS_REMEMBERED's stored state) as progress.js
    beside it, made on first use."""
    if case not in PROGRESS_RUNS:
        data = {'main': PROGRESS_DATA, 'eta': PROGRESS_ETA_DATA, 'two': PROGRESS_TWO, 'long': PROGRESS_LONG,
                'narrow': PROGRESS_NARROW, 'remembered': PROGRESS_DATA}[case]
        early = PROGRESS_EARLY + (PROGRESS_REMEMBERED if case == 'remembered' else '')
        d = tempfile.mkdtemp(prefix='index-quals-')
        text = page()
        assert text.count('<head>\n') == 1 and text.count('</body>') == 1
        text = text.replace('<head>\n', '<head>\n' + early).replace('</body>', PROGRESS_HARNESS + '</body>')
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
        open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(data) + ');\n')
        shutil.copy(DATA, os.path.join(d, 'mstar.js'))
        shutil.copy(POW2, os.path.join(d, 'pow2.js'))
        dom = chrome(d, ['--window-size=1000,1100', '--force-device-scale-factor=2', '--virtual-time-budget=20000',
                         '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
        m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert m, dom[-3000:]
        PROGRESS_RUNS[case] = json.loads(html.unescape(m.group(1)))
        shutil.rmtree(d)
    R = PROGRESS_RUNS[case]
    assert 'harnessError' not in R, R['harnessError']
    return R


def rgb(hexcolor): return [int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)]


def q_theorem_states_pow2_s_thresholds():
    # Replicata: the powers-of-2 section's theorem, its first paragraph stating bounds m*(2^k) ≥ v, and its alternative
    # form, the first paragraph saying "1, 2, …, E", their numbers read off; and pow2.js (pow2_data).
    # Expectata: the theorem's bounds are m*(2^k) ≥ k + e for e = 1, …, E in turn, E the most any power reaches in pow2.js (8 until
    # 2026-10-25, 9 since: dreeves, 2026-10-25: "yes please"), each k the least power whose known lower bound
    # reaches k + e in pow2.js, so that a new result that moves a threshold fails here until the theorem changes with
    # it; then m*(2^9) = 9, pow2.js's bounds at 2^9 both 9; and the alternative form's count is E and its values are
    # those same ks.
    sec = re.search(r'<section class="pow2".*?</section>', page(), re.S).group(0)
    paras = re.findall(r'<p>.*?</p>', sec, re.S)
    theorem = next(p for p in paras if re.search(r'\(2<sup>\d+</sup>\) ≥ \d+', p))
    alt = next(p for p in paras if '1, 2, …, ' in p)
    bounds = [(int(k), op, int(v)) for k, op, v in re.findall(r'\(2<sup>(\d+)</sup>\) (≥|=) (\d+)', theorem)]
    cols = pow2_data()['cols']
    E = max(c[0] - k for k, c in enumerate(cols, 1))
    firsts = [next(k for k in range(1, len(cols) + 1) if cols[k - 1][0] - k >= e) for e in range(1, E + 1)]
    assert bounds[:E] == [(k, '≥', k + e) for e, k in enumerate(firsts, 1)], (bounds, firsts)
    assert bounds[E:] == [(9, '=', 9)] and cols[8][:2] == [9, 9], (bounds[E:], cols[8][:2])
    assert f'1, 2, …, {E}' in alt and ', '.join(map(str, firsts)) in alt, (alt, firsts)


def q_smallest_section_sits_between_the_remarks_and_the_counts():
    # Replicata: index.html's section "The smallest length known for each order".
    # Expectata: a <section class="smallest" aria-labelledby="smallest-title"> right after the remarks' section and
    # right before the counts' section (only blank lines and comments between), holding its heading, a link to OEIS
    # A323395, and a table whose body is empty in the HTML: the script fills it from mstar.js; and not of class block,
    # so that the page keeps the twelve tables of that class that mstar.py reads as Table 2's and the new results'
    # (their count asserted there until 2026-10-27, which a tenth broke on 2026-10-17; nine until 2026-10-26, when the
    # powers of 2 took a third row, and ten until 2026-10-27, when the new results took in Table 2 and reached 1024 in
    # six upper rows).
    text = page()
    filler = r'(?:\s|<!--.*?-->)*'
    m = re.search(r'<section class="remarks">.*?</section>\n' + filler +
                  r'(<section class="smallest" aria-labelledby="smallest-title">\n.*?\n</section>)\n' + filler +
                  r'<section class="counts">', text, re.S)
    assert m, 'no section "smallest" between the remarks and the counts'
    body = m.group(1)
    assert '<h2 id="smallest-title">' in body, body[:300]
    assert 'href="https://oeis.org/A323395"' in body, body
    assert '<table>' in body and '<tbody data-smallest></tbody>' in body, body
    assert text.count('<table class="block">') == 12, text.count('<table class="block">')


def q_smallest_table_matches_mstar():
    # Replicata: index.html in headless Chrome beside mstar.js and pow2.js, its DOM dumped once its scripts ran; and
    # smallest_rows of MSTAR (mstar_data), computed here.
    # Expectata: the table's body holds exactly smallest_rows' rows, in order; the first eleven orders' smallest
    # lengths are SMALLEST_PROVEN, each marked proven (432 added on 2026-10-20 after proof384.py).
    d = tempfile.mkdtemp(prefix='index-quals-')
    for src, name in ((INDEX, 'index.html'), (DATA, 'mstar.js'), (POW2, 'pow2.js')): shutil.copy(src, os.path.join(d, name))
    dom = chrome(d, ['--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    shutil.rmtree(d)
    body = re.search(r'<tbody data-smallest="">(.*?)</tbody>', dom, re.S)
    assert body, dom[-2000:]
    got = [[html.unescape(re.sub(r'<[^>]+>', '', c)) for c in re.findall(r'<td>(.*?)</td>', tr, re.S)]
           for tr in re.findall(r'<tr>(.*?)</tr>', body.group(1), re.S)]
    want = smallest_rows(mstar_data()['cols'])
    assert got == want, (got, want)
    proven = got[:len(SMALLEST_PROVEN)]
    assert [r[1] for r in proven] == [str(n) for n in SMALLEST_PROVEN] and all(r[2] == '✓' for r in proven), proven


def q_smallest_script_passes_node_check():
    # Replicata: the inline script that fills the table of smallest lengths, saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = next(js for js in re.findall(r'<script>\n(.*?)</script>', page(), re.S) if '[data-smallest]' in js)
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'smallest.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_progress_section_starts_closed():
    # Replicata: index.html's section "Search progress".
    # Expectata: a <section class="progress" aria-labelledby="progress-title"> after the sets' section and before the
    # footer: after any comments, a <details> without open, so it starts closed, whose <summary> is the heading
    # progress-title, with a key of the five statuses; and in its run template one more <details>, also without open,
    # each run's fold (dreeves, 2026-10-23; since 2026-10-25 each stays as this browser left it); no <script> on the
    # page names progress.js, which the section's script loads only once it is opened.
    text = page()
    sec = re.search(r'<section class="progress" aria-labelledby="progress-title">\n(.*?)\n</section>\n', text, re.S)
    assert sec and text.index('<section class="sets">') < sec.start() < text.index('<footer>'), sec
    body = sec.group(1)
    assert re.match(r'(?:\s*<!--.*?-->)*\s*<details>', body, re.S), body[:300]
    assert '<details open' not in body and body.count('</details>') == 2, body[:300]
    run = re.search(r'<template class="progress-run">(.*?)</template>', body, re.S).group(1)
    assert run.count('<details>') == 1 and run.count('</details>') == 1, run[:300]
    assert '<summary><h2 id="progress-title">' in body
    assert [s for s in re.findall(r'data-count="(\w+)"', body)] == list(STATUSES)
    assert not re.search(r'<script[^>]*progress', text)


def q_progress_classes_meet_only_its_own_css():
    # Replicata: the classes the section "Search progress" uses, and the page's CSS rules whose selectors start neither
    # with its own classes (.progress, .progress-*) nor with another section's class or a chart's id (they match only
    # inside that section).
    # Expectata: no such rule names one of the section's classes but nw (the page's no-wrap span, used on purpose).
    # (2026-10-17: the ETA chart's legend took the page's legend rule for .key, which drew its line swatches as
    # boxes.)
    text = page()
    sec = re.search(r'<section class="progress".*?</section>', text, re.S).group(0)
    classes = {c for attr in re.findall(r'\bclass="([^"]*)"', sec) for c in attr.split()} - {'nw'}
    others = set(re.findall(r'<section class="([\w-]+)"', text)) - {'progress'}
    style = re.sub(r'/\*.*?\*/', '', text[text.index('<style>'):text.index('</style>')], flags=re.S)
    selectors = [s.strip() for sel in re.findall(r'([^{}]+)\{', style) for s in sel.split(',')]
    scoped = r'(\.progress(-[\w-]+)?|\.(' + '|'.join(map(re.escape, others)) + r')|#(pow2|mstar)[\w-]*)(?![\w-])'
    foreign = [s for s in selectors if not re.match(scoped, s)]
    bad = [(s, c) for s in foreign for c in classes if re.search(rf'\.{re.escape(c)}(?![\w-])', s)]
    assert classes and not bad, bad


def q_progress_css_names_only_what_the_section_has():
    # Replicata: the page's CSS rules whose selectors start with the section's classes (.progress, .progress-*); the
    # section's markup with its script (the page's fifth, which makes the chart's and the tip's marks).
    # Expectata: every class and element such a selector names occurs in them, so no rule of the section's matches
    # nothing.  (2026-10-17: dreeves took the section out of its block quote, which left .progress blockquote and
    # .progress .attrib matching nothing.)
    text = page()
    sec = re.search(r'<section class="progress".*?</section>', text, re.S).group(0)
    js = re.findall(r'<script>\n(.*?)</script>', text, re.S)[-1]
    style = re.sub(r'/\*.*?\*/', '', text[text.index('<style>'):text.index('</style>')], flags=re.S)
    selectors = [s.strip() for sel in re.findall(r'([^{}]+)\{', style) for s in sel.split(',')]
    ours = [re.sub(r'\[[^\]]*\]|::?[\w-]+(\([^)]*\))?', '', s) for s in selectors
            if re.match(r'\.progress(-[\w-]+)?(?![\w-])', s)]
    named = {(kind, name) for s in ours for kind, name in re.findall(r'(\.|(?:^|(?<=[\s>+~])))([a-z][\w-]*)', s)}
    def present(kind, name):
        if kind == '.':
            return re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', sec + js)
        return re.search(rf'<{name}\b', sec) or re.search(rf"""['"]{name}['"]""", js)
    missing = sorted((kind or '<') + name for kind, name in named if not present(kind, name))
    assert len(ours) > 40 and ('.', 'progress') in named and ('', 'canvas') in named and not missing, missing


def q_progress_script_passes_node_check():
    # Replicata: the section's inline script (the page's fifth), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = re.findall(r'<script>\n(.*?)</script>', page(), re.S)[-1]
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'progress-section.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert 'progressData' in js and p.returncode == 0, p.stderr


def q_progress_loads_only_while_open():
    # Replicata: progress_run: index.html in headless Chrome with PROGRESS_DATA as progress.js, the poll 1 s.
    # Expectata: closed at load, with nothing loaded or drawn and no script naming progress.js; opened, it loads
    # progress.js, again each second (at least 3 loads in 3.5 s), and draws once, since the snapshot did not change;
    # closed again, it loads nothing more.
    R = progress_run()
    assert R['before'] == {'open': False, 'loads': 0, 'renders': 0, 'scripts': 0}, R['before']
    assert R['opened']['loads'] >= 3 and R['opened']['renders'] == 1, R['opened']
    assert R['closed']['loads'] == R['closed']['atClose'], R['closed']


def q_progress_eta_text_is_not_outlined():
    # Replicata: progress_run's ETA chart (PROGRESS_DATA's run), the computed stroke of each of its text elements.
    # Expectata: none for the tick labels; for the three labels at the record's end (ETA, total, elapsed), which share
    # their lines' classes (togo, total, spent), only the page's paper color painted under the letters (paint-order
    # stroke first), a halo that hides the lines behind a label (the red dotted line runs from the red marker through
    # its label) and draws no outline.  The lines' rules outranked the text rule until 2026-10-17 and outlined the
    # labels in their lines' colors (dreeves: "the messed up font/bolding").  Since 2026-10-17 (dreeves: "comment it out
    # for now") the labels are commented out, so there are only ticks; the labels' checks stay for their return.
    R = progress_run()
    strokes = R['etaTextStrokes']
    labels = [s for s in strokes if s[0].split()[0] == 'label']
    ticks = [s for s in strokes if s[0] in ('ytick', 'xtick')]
    assert len(labels) == 0 and len(ticks) == len(strokes), strokes
    # With the labels (until 2026-10-17; back with them):
    # assert len(labels) == 3 and len(labels) + len(ticks) == len(strokes), strokes
    assert all(stroke == 'rgb(255, 255, 255)' and order.startswith('stroke') for _, _, stroke, order in labels), labels
    assert all(stroke == 'none' for _, _, stroke, _ in ticks), ticks


def q_progress_remembers_it_was_left_open():
    # Replicata: progress_run with no stored state (main), and with this browser's stored state saying it last left the
    # section open (remembered, PROGRESS_REMEMBERED); in each, the stored state as the harness begins, after it opens
    # the section and after it closes it.
    # Expectata (dreeves, 2026-10-17: reloads kept closing the section; "2": remember it in the browser): main starts
    # closed with nothing stored, stores "1" once opened and nothing once closed; remembered starts open, its data
    # loading already (a progress.js script and at least one load before the harness touched it), then the same.
    main, kept = progress_run(), progress_run('remembered')
    assert main['before']['open'] is False and main['stored'] == {'before': None, 'opened': '1', 'closed': None}, main['stored']
    assert kept['before']['open'] is True and kept['before']['loads'] >= 1 and kept['before']['scripts'] >= 1, kept['before']
    assert kept['stored'] == {'before': '1', 'opened': '1', 'closed': None}, kept['stored']


def q_progress_draws_each_dot_in_its_status_color():
    # Replicata: progress_run, the middle pixel of every dot after opening, and the CSS custom properties
    # --progress-<status> (STATUSES).
    # Expectata: one dot per status digit of the data, in its order, each pixel exactly its status's color; the key's
    # counts are the data's.
    R = progress_run()
    want = [(int(c), STATUSES[int(c)]) for g in PROGRESS_DATA['runs'][0]['groups'] for c in g]
    assert [s for s, _ in R['dots']] == [s for s, _ in want], R['dots']
    assert all(len(c) == 7 and c.startswith('#') for c in R['colors']), R['colors']
    assert all(px == rgb(R['colors'][s]) for s, px in R['dots']), (R['dots'], R['colors'])
    assert R['counts'] == {s: str(PROGRESS_DATA['runs'][0]['counts'][s]) for s in STATUSES}, R['counts']


def q_progress_states_times_and_hours():
    # Replicata: progress_run's state line, snapshot time and age after opening.
    # Expectata: only the running state's line shows, in dreeves's form of 2026-10-17 ("Running: 11.4 h so far +
    # 34.2–50.6 h to go = 45–62 h (Mon 6:27am – 10:58pm)", then for "Running:" his '"@2026-10-17 20:40:59" (in black)
    # and then some whitespace, no colon'): an @ and the snapshot's time (the data's made: stamp), in the page's ink, an
    # em space, then 2.0 h so far + a 0.5–3.0 h band to go (PROGRESS_DATA's so_far and to_go) = 2.5–5.0 h in all, each
    # number and its h apart by a narrow no-break space (his "thin space"), then in parentheses the local times that
    # band ends between (finish: the weekday once unless the dates differ, 12-hour times with am or pm), no period; the
    # snapshot time above the runs is the data's made in
    # local time (YYYY-MM-DD HH:MM:SS), and its age a duration in digits.  And since dreeves's request of 2026-10-17, the
    # status line sits below the ETA chart, where its legend was, outside the chart's box (so that it shows when the
    # chart has no record), its parts in the chart's colors: the hours so far blue (spent), the hours to go red (togo),
    # the hours in all and the clock times purple (total: #7b1fa2 since dreeves's "blue+red=purple", 2026-10-17; the
    # page's ink before).
    R = progress_run()
    made, go, h = PROGRESS_DATA['made'], PROGRESS_DATA['runs'][0]['to_go'], NNBSP + 'h'
    want = f'@{stamp(made)}{EMSP}2.0{h} so far + 0.5–3.0{h} to go = 2.5–5.0{h} ({finish(made, made + go["lo"], made + go["hi"])})'
    assert R['state'] == [want], (R['state'], want)
    at = lambda d, hh, mm: time.mktime((2026, 10, d, hh, mm, 0, 0, 0, -1))        # local times; 2026-10-19 is a Monday
    assert finish(at(19, 6, 0), at(19, 6, 27), at(19, 17, 38)) == 'Mon 6:27am – 5:38pm', finish(at(19, 6, 0), at(19, 6, 27), at(19, 17, 38))
    assert finish(at(19, 6, 0), at(19, 6, 27), at(20, 0, 18)) == 'Mon 6:27am – Tue 12:18am', finish(at(19, 6, 0), at(19, 6, 27), at(20, 0, 18))
    # a week on, a weekday is ambiguous: a date (dreeves, 2026-10-23; 'Mon 12:05pm – Mon 12:05pm' until then)
    assert finish(at(19, 12, 5), at(19, 12, 5), at(26, 12, 5)) == 'Mon 12:05pm – 2026-10-26'
    want = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(PROGRESS_DATA['made']))
    assert R['made'] == want, (R['made'], want)
    assert re.fullmatch(r'(\d+ d )?\d+:\d\d:\d\d', R['age']), R['age']
    assert R['status']['afterChart'] is True, R['status']
    assert R['status']['colors'] == [['spent', 'rgb(42, 120, 214)'], ['togo', 'rgb(227, 73, 72)'], ['total', 'rgb(123, 31, 162)']], R['status']
    assert R['status']['ink'] == R['status']['when'] == 'rgb(27, 29, 34)', R['status']


def q_progress_writes_days_and_years_past_72_h_and_dates_past_a_week():
    # Replicata: progress_run('long'): PROGRESS_LONG's two running runs.
    # Expectata (dreeves, 2026-10-23: "this would be more helpful as days or years when over like 48 or maybe 72h, and
    # the parenthetical needs disambiguation when >1week"): each duration in hours below 72 h, in days below a year of
    # 365.25 d, in years from there, as before a tenth so far and to go and in all a tenth below 10 and whole from 10,
    # each with its own unit but a range's unit once when its ends share it: 14.2 h so far + 149.9 d–6.4 y to go =
    # 150 d–6.4 y, then 4.2 d so far + 0.5–3.0 h to go = 4.2–4.3 d; each finish time a week or more after the snapshot
    # as its local date, both of the first run's, YYYY-MM-DD; and the first run's ETA chart's axes each in the unit of
    # its largest value, hours of running in days, 0 to 400 d, and hours in all in days too, 0 to 300 d, as the y axis
    # stops a bit above the projected finish (dreeves, 2026-10-23; q_progress_caps_the_y_axis_above_the_projected_finish).
    R = progress_run('long')
    made, (a, b) = PROGRESS_LONG['made'], [r['to_go'] for r in PROGRESS_LONG['runs']]
    h, d, y = NNBSP + 'h', NNBSP + 'd', NNBSP + 'y'
    date = lambda s: time.strftime('%Y-%m-%d', time.localtime(s))
    want = [f'@{stamp(made)}{EMSP}14.2{h} so far + 149.9{d}–6.4{y} to go = 150{d}–6.4{y} ({date(made + a["lo"])} – {date(made + a["hi"])})',
            f'@{stamp(made)}{EMSP}4.2{d} so far + 0.5–3.0{h} to go = 4.2–4.3{d} ({finish(made, made + b["lo"], made + b["hi"])})']
    assert R['state'] == want, (R['state'], want)
    parts = SvgParts()
    parts.feed(R['etaSvg'])
    ticks = lambda k: [text for tag, at, text in parts.items if at.get('class') == k]
    assert ticks('xtick') == ['0', '100', '200', '300', f'400{d}'], ticks('xtick')
    assert ticks('ytick') == ['0', '100', '200', f'300{d}', '6', f'8{y}'], ticks('ytick')   # then the top panel's


def q_progress_breaks_the_y_axis_above_the_projected_finish():
    # Replicata: the ETA charts of progress_run('long') (480:14's bands, thousands of hours above its projected
    # finish), of progress_run('eta') (its purple band's top 0.6 h above the cap) and of progress_run('narrow') (bands
    # within the cap), as markup.
    # Expectata (dreeves, 2026-10-23: "truncate the y-axis a bit above the horizontal purple dashed line ... and
    # indicate visually in some way (no words) when the confidence bands go above the y-axis cap", then "can you do
    # something more canonical for the y-axis break? maybe something like this?", a two-panel plot with slashes at the
    # break): the main panel stops at the cap, 10% above the projected finish, the purple guide's level, its top edge a
    # cap line; anything above the cap, as long's and eta's band tops, gets a top panel 40 units tall, 10 above the
    # main one, linear from the round tick of its unit at or below the least such value (but no lower than the cap) to
    # the round tick at or above the greatest, labeled at the round ticks at its ends, the last with its unit (four
    # labels crowded 480's 40 units); no line at either panel's edge (dreeves, 2026-10-23: "why does this look so bad?
    # the excess horizontal lines": the edges sat a few units from gridlines), so no two horizontal lines within 4
    # units; the 10 units between clipped away; a y axis line at
    # the plot's left (dreeves, 2026-10-23: "i think we need a visible y-axis line for that to look reasonable"), up
    # from the x axis to the main panel's top and from the top panel's bottom to its top, broken at the gap, with a
    # slash across each end of the break (none at the right, where no line is); every band vertex in one panel or on an
    # edge of the gap; and narrow has one panel: its y axis whole, its slashes hidden, nothing clipped.
    for case, over, labels in (('long', True, ['6', '8\u202fy']), ('eta', True, ['20\u202fh']), ('narrow', False, [])):
        parts = SvgParts()
        parts.feed(progress_run(case)['etaSvg'])
        pts = lambda a: [tuple(map(float, xy.split(','))) for xy in a['points'].split()]
        seg = lambda a: tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2'))
        [axis] = [float(a['y1']) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'axis']
        [guide] = [pts(a) for tag, a, _ in parts.items if tag == 'polyline' and a.get('class') == 'guide']
        rects = [tuple(float(a[k]) for k in ('x', 'y', 'width', 'height')) for tag, a, _ in parts.items if tag == 'rect']
        yt, yb = rects[0][3], rects[1][1]                     # the top panel's bottom edge, the main panel's top
        assert abs((axis - yb) - 1.1 * (axis - guide[0][1])) < 0.05, (case, axis, yb, guide[0])
        assert not [a for tag, a, _ in parts.items if a.get('class') == 'cap'], case
        rows = sorted({round(seg(a)[1], 2) for tag, a, _ in parts.items if tag == 'line' and a.get('class') in ('grid', 'axis')})
        assert all(b - a >= 4 for a, b in zip(rows, rows[1:])), (case, rows)
        assert (yt, yb) == ((54.0, 64.0) if over else (14.0, 14.0)), (case, yt, yb)
        breaks = [(seg(a), a.get('visibility')) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'break']
        assert sorted(s for s, _ in breaks) == sorted((48 - 4, y + 4, 48 + 4, y - 4) for y in (yt, yb)), (case, breaks)
        spine = sorted(seg(a) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'yaxis')
        assert spine == sorted([(48, axis, 48, yb), (48, yt, 48, 14)]), (case, spine)
        assert all(v == ('visible' if over else 'hidden') for _, v in breaks), (case, breaks)
        top = [(float(a['y']) - 4, t) for tag, a, t in parts.items if tag == 'text' and a.get('class') == 'ytick' and float(a['y']) - 4 < yb - 0.05]
        assert [t for _, t in top] == labels and all(14 - 0.05 <= y <= yt + 0.05 for y, _ in top), (case, top)
        assert rects == [(0, 0, 640, yt), (0, yb, 640, 240 - yb)], (case, rects)
        bands = [y for tag, a, _ in parts.items if tag == 'polygon' for _, y in pts(a)]
        assert all(14 - 0.05 <= y <= yt + 0.05 or yb - 0.05 <= y for y in bands), (case, sorted(bands))
        assert any(y < yb - 0.05 for y in bands) == over, case


def from_oklab(lab):
    """An OKLab color as #rrggbb, its sRGB clipped: the inverse of oklab(linear(h))."""
    L, a, b = lab
    l, m, s = [(L + x * a + y * b) ** 3 for x, y in ((0.3963377774, 0.2158037573), (-0.1055613458, -0.0638541728), (-0.0894841775, -1.2914855480))]
    lin = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    enc = [12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in (min(1, max(0, c)) for c in lin)]
    return '#' + ''.join(f'{round(255 * v):02x}' for v in enc)


def q_progress_bands_overlap_visibly():
    # Replicata: the page's CSS: the ETA's band and elapsed + ETA's, each color-mix(in oklab, its color N%, the paper),
    # multiplied onto what is under them; so the three regions they make on the paper: the ETA's band alone, elapsed +
    # ETA's alone, and both.
    # Expectata (dreeves, 2026-10-23: "shouldn't we be able to visually distinguish between a region that both red and
    # purple confidence bands cover vs just the purple confidence band covering it?"; at 16% and 16% that pair was ΔE
    # 6.1, OKLab x 100): both at least ΔE 13 from purple alone and 11 from red alone, and red alone 7 from purple alone.
    style = page()[page().index('<style>'):page().index('</style>')]
    color = lambda name: re.search(rf'--{name}: (#[0-9a-f]{{6}});', style).group(1)
    pct = lambda name: int(re.search(rf'\.progress-eta \.band\.{name} \{{ fill: color-mix\(in oklab, var\(--progress-{name}\) (\d+)%, var\(--paper\)\); \}}', style).group(1)) / 100
    paper = oklab(linear(color('paper')))
    def wash(name):
        c = oklab(linear(color(f'progress-{name}')))
        return from_oklab([pct(name) * x + (1 - pct(name)) * y for x, y in zip(c, paper)])
    red, purple = wash('togo'), wash('total')
    rgb = lambda h: [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    both = '#' + ''.join(f'{round(255 * x * y):02x}' for x, y in zip(rgb(red), rgb(purple)))   # multiply, as the blend does
    got = (delta_e(purple, both), delta_e(red, both), delta_e(red, purple))
    assert got[0] >= 13 and got[1] >= 11 and got[2] >= 7, got


def q_progress_reloads_on_returning_to_the_tab():
    # Replicata: index.html with PROGRESS_DATA as progress.js, the section left open (PROGRESS_REMEMBERED) and the
    # minute's poll; after its first load, a visibilitychange event, as when the tab comes back into view.
    # Expectata (dreeves, 2026-10-23: "did you break auto-refresh yet again?", the page having polled nothing while its
    # tab was hidden): a load at once, not up to a minute later.
    d = tempfile.mkdtemp(prefix='index-quals-')
    harness = """<script>
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(1500);
  const before = window.progressView.loads;
  document.dispatchEvent(new Event('visibilitychange'));
  await sleep(50);
  const pre = document.createElement('pre'); pre.id = 'harness-out';
  pre.textContent = JSON.stringify({before, after: window.progressView.loads}); document.body.appendChild(pre);
})();
</script>
"""
    text = page().replace('<head>\n', '<head>\n' + PROGRESS_REMEMBERED).replace('</body>', harness + '</body>')
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
    open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(PROGRESS_DATA) + ');\n')
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    dom = chrome(d, ['--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    shutil.rmtree(d)
    m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
    assert m, dom[-2000:]
    got = json.loads(html.unescape(m.group(1)))
    assert got['before'] >= 1 and got['after'] == got['before'] + 1, got


FOLD = 'progress-fold '         # localStorage: "1" under this prefix and a run's program, n and order while its fold is open
# two runs whose folds have names of their own: PROGRESS_DATA's running one and PROGRESS_ETA_DATA's ended one as
# boxsplit.py's, with no outcome
PROGRESS_FOLDS = {'made': PROGRESS_DATA['made'],
                  'runs': [PROGRESS_DATA['runs'][0], dict(PROGRESS_ETA_DATA['runs'][0], program='boxsplit.py')]}
# The page with data as progress.js and harness (a script) run in it, the section open and before (a script) run before
# the page's own: what the harness put in <pre id="harness-out">, as JSON.
FOLD_LOOK = """
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const runs = () => [...document.querySelectorAll('.progress-runs .progress-run')];
  const look = () => runs().map(r => ({state: r.dataset.runState, open: r.querySelector('details').open,
    summary: !!r.querySelector('summary h3'), color: getComputedStyle(r.querySelector('summary')).color,
    status: r.querySelector('.progress-status').checkVisibility(), canvas: r.querySelector('canvas').width,
    label: [...r.querySelectorAll('summary [data-label]')].filter(e => e.checkVisibility()).map(e => e.dataset.label)}));
  const out = x => { const pre = document.createElement('pre'); pre.id = 'harness-out'; pre.textContent = JSON.stringify(x); document.body.appendChild(pre); };
"""


def progress_harness(data, harness, before=''):
    d = tempfile.mkdtemp(prefix='index-quals-')
    script = '<script>\n(async () => {' + FOLD_LOOK + '  await sleep(1500);\n' + harness + '\n})();\n</script>\n'
    text = page().replace('<head>\n', '<head>\n' + PROGRESS_REMEMBERED + before).replace('</body>', script + '</body>')
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
    open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(data) + ');\n')
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    dom = chrome(d, ['--window-size=1000,1100', '--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    shutil.rmtree(d)
    m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
    assert m, dom[-2000:]
    return json.loads(html.unescape(m.group(1)))


def q_progress_folds_stay_as_left():
    # Replicata: index.html with PROGRESS_FOLDS as progress.js, the section open and no fold stored; then the running
    # run opened by hand, as by a click; a snapshot in which it has ended; then it closed by hand.
    # Expectata (dreeves, 2026-10-25: "i think there's some anti-magic violation with the collapsed/expanded state.
    # probably they should just remember in localstorage what their state is and just always stay that way until
    # explicitly clicked"): both runs listed, each folded under its heading (a summary) whatever its state, its status
    # line folded with its charts, its dots sized to the section's width though folded, the run not running grayed;
    # opened by hand, a run's fold is stored, "1" under FOLD and its program, n and order, and stays open across the
    # snapshot that ends the run; closed by hand, its stored fold is gone.
    # Resultata before (2026-10-23's design): the running run's fold opened by itself and the ended one's folded, and
    # a fold opened or closed by hand was kept in memory only, so a reload forgot it.
    got = progress_harness(PROGRESS_FOLDS, """
  const name = 'progress-fold overnight_v5.py 64 7', first = look();
  runs()[0].querySelector('details').open = true;
  await sleep(50);
  const stored = localStorage.getItem(name);
  const d2 = JSON.parse(JSON.stringify(window.progressView.data)); d2.made += 60; d2.runs[0].state = 'ended'; d2.runs[0].to_go = null;
  window.progressData(d2);
  await sleep(50);
  const after = look();
  runs()[0].querySelector('details').open = false;
  await sleep(50);
  out({first, stored, after, cleared: localStorage.getItem(name)});""")
    first, after = got['first'], got['after']
    assert [(r['state'], r['open'], r['summary'], r['status']) for r in first] == [('running', False, True, False), ('ended', False, True, False)], first
    assert first[1]['color'] != first[0]['color'], first                 # grayed: not the running heading's color
    assert first[1]['canvas'] == first[0]['canvas'] > 100, first        # sized to the section, folded or not
    assert got['stored'] == '1', got
    assert [(r['state'], r['open'], r['status']) for r in after] == [('ended', True, True), ('ended', False, False)], after
    assert got['cleared'] is None, got


def q_progress_folds_are_remembered_across_loads():
    # Replicata: index.html with PROGRESS_FOLDS as progress.js, the section open, and this browser having left the
    # ended run's fold open (stored before the page's scripts run) and the running run's never opened.
    # Expectata (dreeves, 2026-10-25, as for q_progress_folds_stay_as_left): the ended run open and the running run
    # folded, each as this browser left it, whatever its state.
    got = progress_harness(PROGRESS_FOLDS, '  out(look());',
                           before='<script>localStorage.setItem("progress-fold boxsplit.py 64 7", "1");</script>\n')
    assert [(r['state'], r['open'], r['status']) for r in got] == [('running', False, False), ('ended', True, True)], got


def q_progress_redraw_keeps_the_scroll_position():
    # Replicata: index.html with three runs as progress.js (PROGRESS_FOLDS's two and a third at n 72), the section
    # and every run's fold open, scroll anchoring off (overflow-anchor: none, as in a browser without it, like Safari),
    # the page scrolled to its bottom, where the section sits; then a new snapshot of the same runs, which redraws them.
    # Expectata (dreeves, 2026-10-26: "Every time the graph updates the page scrolls itself"): the redraw leaves the
    # page where it was, the scroll position and the page's height the same before and after.
    # Resultata before the fix: 715 px up. render emptied the runs and rebuilt them one by one, and each run's sea
    # measured the runs' width (runsBox.clientWidth), a layout of the page with only the runs rebuilt so far, shorter,
    # so the browser pulled the scroll position up to fit it, and there it stayed (Chrome's scroll anchoring put it
    # back, when its anchor survived the rebuild).
    data = {'made': PROGRESS_FOLDS['made'], 'runs': PROGRESS_FOLDS['runs'] + [dict(PROGRESS_FOLDS['runs'][0], n=72)]}
    opened = ''.join(f'localStorage.setItem("progress-fold {r["program"]} {r["n"]} {r["order"]}", "1");' for r in data['runs'])
    got = progress_harness(data, """
  window.scrollTo(0, document.documentElement.scrollHeight);
  await sleep(50);
  const before = {y: window.scrollY, h: document.documentElement.scrollHeight, open: look().map(r => r.open)};
  const d2 = JSON.parse(JSON.stringify(window.progressView.data)); d2.made += 60; window.progressData(d2);
  await sleep(50);
  out({before, after: {y: window.scrollY, h: document.documentElement.scrollHeight, renders: window.progressView.renders}});""",
                           before=f'<script>{opened}</script>\n<style>* {{ overflow-anchor: none; }}</style>\n')
    assert got['before']['open'] == [True, True, True], got
    assert got['before']['y'] > 0 and got['after']['renders'] == 2, got
    assert (got['after']['y'], got['after']['h']) == (got['before']['y'], got['before']['h']), got


def q_progress_summary_names_each_run_s_state():
    # Replicata: index.html with five runs as progress.js, the section open, every fold folded: running, paused,
    # frozen, ended with an outcome (excluded) and ended with none (its process gone without a finish, as a stopped or
    # crashed run).
    # Expectata (dreeves, 2026-10-25: "can these be clearer when collapsed about what's paused/completed/aborted/
    # running?"): each run's summary, folded, shows the label of its state, running, paused, frozen, completed or
    # aborted (data-label), and no other.
    # Resultata before: no word; a run not running was only grayed.
    base = dict(PROGRESS_DATA['runs'][0], to_go=None)
    runs = [dict(base, n=64 + 8 * i, state=state, outcome=outcome) for i, (state, outcome) in
            enumerate([('running', None), ('paused', None), ('frozen', None), ('ended', 'excluded'), ('ended', None)])]
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': runs}, '  out(look());')
    assert [(r['state'], r['open'], r['label']) for r in got] == [
        ('running', False, ['running']), ('paused', False, ['paused']), ('frozen', False, ['frozen']),
        ('ended', False, ['completed']), ('ended', False, ['aborted'])], got


def q_progress_status_line_names_an_ended_run_s_outcome():
    # Replicata: index.html with the five runs of q_progress_summary_names_each_run_s_state as progress.js: running,
    # paused, frozen, ended with an outcome (excluded) and ended with none.
    # Expectata (dreeves, 2026-10-26: "for the ended/aborted searches, they say either "completed" or "aborted" in the
    # collapsed version but the last line of the expanded version always just says "ended". can you change those
    # instances of "ended" to "aborted" or "completed" as appropriate?"): each run's status line, under its charts,
    # shows the one part (data-state) of the state its summary names: running, paused, frozen, completed, aborted.
    # Resultata before: both ended runs' status lines showed the part for "ended", which said "Ended after running for".
    base = dict(PROGRESS_DATA['runs'][0], to_go=None)
    runs = [dict(base, n=64 + 8 * i, state=state, outcome=outcome) for i, (state, outcome) in
            enumerate([('running', None), ('paused', None), ('frozen', None), ('ended', 'excluded'), ('ended', None)])]
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': runs}, """
  out(runs().map(r => [...r.querySelectorAll('.progress-status > [data-state]')].filter(e => !e.hidden)
    .map(e => e.dataset.state)));""")
    assert got == [['running'], ['paused'], ['frozen'], ['completed'], ['aborted']], got


def q_progress_names_each_run_s_program():
    # Replicata: progress_run with two runs: PROGRESS_DATA's, then the same as boxsplit.py's pass (PROGRESS_TWO).
    # Expectata: two headings, in the data's order, each the run's question and its program, overnight_v5.py then
    # boxsplit.py (dreeves, 2026-10-17: a second block for the boxsplit pass over 240@11's open cases); both runs' ETA
    # charts show, the second's with no ETA recorded too (dreeves, 2026-10-23: "the search progress section should
    # always be clear about what's been running for how long"; hidden with no ETA from 2026-10-17 until then).
    R = progress_run('two')
    assert R['heads'] == ['m*(64) ≥ 7? overnight_v5.py', 'm*(64) ≥ 7? boxsplit.py'], R['heads']
    assert R['etaDisplays'] == ['grid', 'grid'], R['etaDisplays']


def q_progress_redraws_in_place_and_reads_out_a_subtree():
    # Replicata: progress_run: a hover over the third group's first dot; then progressData given a changed snapshot
    # (one minute later, the running dot open).
    # Expectata: the readout holds the third group's key; after the call the section has drawn again in the same
    # document (the harness's marker survives: no reload), that dot is open's color and the key counts it.
    R = progress_run()
    assert R['readout'].startswith(PROGRESS_DATA['runs'][0]['keys'][2]), R['readout']
    c = R['changed']
    assert c['marker'] == 'kept' and c['renders'] == 2, c
    assert c['pixel'] == rgb(R['colors'][STATUSES.index('open')]), (c['pixel'], R['colors'])
    assert c['counts']['open'] == '4' and c['counts']['running'] == '0', c['counts']



def q_progress_draws_time_to_scale():
    # Replicata: progress_run's time bar: its parts' widths and the median's mark, as the section sets them.
    # Expectata (dreeves, 2026-10-09: "lead with time so far and time to go, to scale"): out of so far + the band's
    # top (2 h + 3 h), so far 40%, the band's bottom 10% after it, the rest of the band 50%, and the median's mark at
    # 60% (the mean's until 2026-10-19, when the boxsplit estimate's Lindy tail made means useless).
    R = progress_run()
    assert {k: float(v.rstrip('%')) for k, v in R['bar'].items()} == {'so-far': 40.0, 'lo': 10.0, 'band': 50.0, 'median': 60.0}, R['bar']


def q_progress_lays_out_each_subtree_as_a_block():
    # Replicata: progress_run's layout of the sea: a rectangle of cells per group (x, y, w, h), in a grid cols wide.
    # Expectata: each group's rectangle holds its dots (w h at least its count) inside the grid; no two rectangles
    # touch (a cell's gap at least between them); and they come in reading order, as the groups do.
    B = progress_run()['blocks']
    rects, sizes = B['rects'], [len(g) for g in PROGRESS_DATA['runs'][0]['groups']]
    assert len(rects) == len(sizes) and all(r['w'] * r['h'] >= n for r, n in zip(rects, sizes)), (rects, sizes)
    assert all(r['x'] >= 0 and r['y'] >= 0 and r['x'] + r['w'] <= B['cols'] and r['y'] + r['h'] <= B['rows'] for r in rects), B
    apart = lambda a, b: a['x'] + a['w'] < b['x'] or b['x'] + b['w'] < a['x'] or a['y'] + a['h'] < b['y'] or b['y'] + b['h'] < a['y']
    assert all(apart(a, b) for i, a in enumerate(rects) for b in rects[i + 1:]), rects
    assert [(r['y'], r['x']) for r in rects] == sorted((r['y'], r['x']) for r in rects), rects


def q_progress_draws_the_eta_chart():
    # Replicata: progress_run's ETA chart (progress.html's, ported: dreeves, 2026-10-09 and 10-10), from
    # PROGRESS_DATA's three recorded ETAs; a hover over the second, then over the last.
    # Expectata: shown, as wide as the sea (2026-10-17: as a figure, the page's figure rule shrank it to its content); the
    # ETA's line has a point per record; no direct labels at the last record (they gave its ranges and the elapsed time
    # until dreeves's "comment it out for now", 2026-10-17: the status line below says the same, in the same colors), so
    # no x tick gives way to the elapsed time's label: 0, 1, 2 and 3 h; the tip, laid out but invisible at rest (a line
    # of its own, so that showing it moves nothing: the page jumped on hover until 2026-10-17), is the status line's
    # running form for the record under the pointer (dreeves, 2026-10-17: "the same as the line below, just an earlier
    # snapshot thereof and with the datetimestamp prefix"): over the second record, an @ and its time, an em space, 1.0 h
    # so far + 1.0–3.0 h to go = 2.0–4.0 h, and in parentheses the local times its band ends between; over the last (the
    # snapshot's own), the status line exactly, markup and all; and the hover moved the status line not at all.
    R = progress_run()
    E = R['eta']
    assert not E['hidden'] and E['togo'] == 3 and abs(E['widths'][0] - E['widths'][1]) <= 1, E
    h = NNBSP + 'h'
    assert E['labels'] == 0, E
    # With the labels (until 2026-10-17; back with them):
    # assert (E['labelTogo'], E['labelTotal'], E['labelSpent']) == (f'0.5–3.0{h}', f'2.5–5.0{h}', f'2.0{h}'), E
    parts = SvgParts()
    parts.feed(R['etaSvg'])
    assert [text for tag, a, text in parts.items if a.get('class') == 'xtick'] == ['0', '1', '2', f'3{h}'], R['etaSvg']
    t = PROGRESS_DATA['runs'][0]['etas'][1][0]
    assert E['tip'] == f'@{stamp(t)}{EMSP}1.0{h} so far + 1.0–3.0{h} to go = 2.0–4.0{h} ({finish(t, t + 3600, t + 10800)})', E['tip']
    assert E['tipLast'] == R['state'][0] and E['sameMarkup'] is True, (E['tipLast'], R['state'], E['sameMarkup'])
    assert R['tipRest']['visibility'] == 'hidden' and R['tipRest']['height'] > 0 and R['jump'] == 0, (R['tipRest'], R['jump'])


def q_progress_tip_projects_past_the_last_record():
    # Replicata: progress_run: hovers over the ETA chart's records, then at 2.5 h of running, half an hour past its last
    # record (PROGRESS_DATA's, at 2 h: 0.5–3.0 h to go).
    # Expectata (dreeves, 2026-10-18: "the hover feature of showing the historical ETA might as well work for the whole
    # graph, right? i guess what we'd need is a way to make the distinction clear between historical vs projected"):
    # there the tip is the last record's line carried on half an hour, in italics (class projected): the clock and the
    # hours so far half an hour on, 2.5 h so far, the band half an hour lower and no lower than 0, 0.0–2.5 h to go, so
    # 2.5–5.0 h in all and the status line's finish times; the cross line at the pointer; over a record, no italics;
    # and the status line below the chart did not move.
    R = progress_run()
    E, h = R['eta'], NNBSP + 'h'
    t = PROGRESS_DATA['made'] + 1800
    want = f'@{stamp(t)}{EMSP}2.5{h} so far + 0.0–2.5{h} to go = 2.5–5.0{h} ({finish(t, t, t + 9000)})'
    assert E['tipAhead'] == want, (E['tipAhead'], want)
    A = E['ahead']
    assert A['projected'] is True and A['style'] == 'italic' and abs(A['cross'] - A['want']) < 0.05, A
    assert E['projectedAtRecord'] is False and R['jumpAhead'] == 0, (E['projectedAtRecord'], R['jumpAhead'])


class SvgParts(html.parser.HTMLParser):
    """An svg's elements in document order, each [tag, attributes, text], an element's text with its children's."""
    def __init__(self):
        super().__init__()
        self.items, self.open = [], []
    def handle_starttag(self, tag, attrs):
        item = [tag, dict(attrs), '']
        self.items.append(item)
        self.open.append(item)
    def handle_endtag(self, tag):
        while self.open and self.open.pop()[0] != tag: pass
    def handle_data(self, data):
        for item in self.open: item[2] += data


def q_progress_eta_chart_keeps_progress_html_s_spec():
    # Replicata: progress_run('eta'): the section's ETA chart of PROGRESS_ETA_DATA, progress.html's case (13.2 h of
    # running; ETAs [2, 1, 4] h at 0 h and [1, 0.5, 3] h at 13.2 h), as markup; and the section's CSS.
    # Expectata, progress.html's (quals_progress's q_page_draws_the_eta_chart until 2026-10-17, when index.html's
    # section took the chart over): it knows nothing of passes (dreeves, 2026-10-10); round ticks every 5 h from 0 to
    # 15 h on both axes, labeled, the top one with its unit, a gridline at each y tick but 0, which is the axis; the
    # diagonal of elapsed time (spent) from (0, 0) to (13.2, 13.2) h, carried on ahead, dashed, to (14.2, 14.2); the
    # band along the ETAs' tops left to right and their bottoms back; the ETA (togo) and elapsed + ETA (total) with a
    # point per ETA; at the last, a vertical range line across its band, markers on both lines, and dreeves's direct
    # labels (2026-10-10; ranges since 2026-10-12): "ETA 0.5–3.0 h" just right of the red marker, "14–16 h" just right
    # of the black one, and "13 h" in blue on the x axis under it; a cross line hidden at rest; no other line; the
    # black stroke the widest; the palette's blue (#2a78d6) and red (#e34948) and the page's ink; the legend in
    # dreeves's words: elapsed time, ETA, elapsed + ETA.  And since 2026-10-17 (dreeves: "1. yes"), the projected finish
    # marked: a hollow marker (finish) where the dashed elapsed time meets elapsed + ETA, at (14.2, 14.2) h, and a guide
    # from the black marker across to it and down to the x axis, (13.2, 14.2), (14.2, 14.2), (14.2, 0) h.  Then, at
    # dreeves's request (2026-10-17): the ETA's ideal course, a red dotted line (ideal) from the red marker down to the x
    # axis at the finish, (13.2, 1) to (14.2, 0) h; the red label without its "ETA", "0.5–3.0 h"; and no legend: the
    # status line below the chart says what each color is (q_progress_states_times_and_hours); and, since dreeves's
    # "comment it out for now" (2026-10-17), no direct labels, nor their rules among the live CSS.  Then, at dreeves's
    # request (2026-10-17: "1. shouldn't the black line also have a confidence band? 2. shouldn't there be a blue dot for
    # consistency? 3. ooh, how about purple instead of black, because blue+red=purple?"): elapsed + ETA's band too, the
    # ETAs' band raised by each record's elapsed time, (0, 4), (13.2, 16.2), (13.2, 13.7), (0, 1) h, with its own range
    # line at the last, (13.2, 13.7) to (13.2, 16.2) h; a blue marker at the last record's elapsed time, (13.2, 13.2) h,
    # where the dashed elapsed time starts; elapsed + ETA purple, #7b1fa2 (the validator's numbers are in the CSS), in
    # its line, band, range line, marker, label and the finish marker's ring, the black ink no more; and the y axis
    # taller, to the top of elapsed + ETA's band (16.2 h), so its ticks run from 0 to 20 h.  The two bands can overlap,
    # and so can the two range lines (not here; in boxsplit.py's chart of 2026-10-17, from 46 to 51 h), so both bands
    # and both range lines multiply onto what is under them: neither hides the other (the purple range line hid the red
    # one's top until they did, 2026-10-17).  And the guide purple too, as it carries elapsed + ETA's level across to the
    # finish and down to it on the x axis (dreeves, 2026-10-18: "that looks black and should be purple"; the page's
    # muted gray before).  And no finish marker since 2026-10-18 (dreeves: "remove the hollow purple dot at the upper
    # right; that might look cleaner"): the guide alone marks the projected finish.  And since 2026-10-23 (dreeves:
    # "truncate the y-axis a bit above the horizontal purple dashed line ... and indicate visually in some way (no words)
    # when the confidence bands go above the y-axis cap", then "can you do something more canonical for the y-axis
    # break?"), the main panel stops 10% above the projected finish, at 15.62 h, in place of 20 h: its gridlines at 5, 10
    # and 15 h and its top edge at 15.62 h; and elapsed + ETA's band top (16.2 h) and range line's go to a top panel,
    # 15.62 to 20 h, labeled 20 h (q_progress_breaks_the_y_axis_above_the_projected_finish).
    R = progress_run('eta')
    parts = SvgParts()
    parts.feed(R['etaSvg'])
    els = [(tag, a, re.sub(r'[ \t\n\r]+', ' ', text).strip()) for tag, a, text in parts.items]   # U+202F stays: it is text
    def pts(text): return [tuple(map(float, xy.split(','))) for xy in text.split()]
    polys = {a['class']: pts(a['points']) for tag, a, _ in els if tag == 'polyline'}
    assert sorted(polys) == ['guide', 'spent', 'togo', 'total'], polys.keys()
    (x0, y0), (x1, y1) = polys['spent'][0], polys['spent'][-1]          # blue at 0 h and at 13.2 h
    def X(h): return x0 + (x1 - x0) * h / 13.2
    def Y(h): return y0 + (y1 - y0) * h / 13.2
    def near(p, q): return abs(p[0] - q[0]) < 0.05 and abs(p[1] - q[1]) < 0.05
    cap, lo2, hi2 = 1.1 * 14.2, 1.1 * 14.2, 20                          # the main panel's cap; the top panel's ends, h
    YB = Y(cap)                                                          # the main panel's top edge; the top panel's
    YT = YB - 10                                                         # bottom edge, 10 units above, its top 40 above that
    def Ys(h): return Y(min(h, cap)) - 10 * (h > cap) - 40 * min(1, max(0, (h - lo2) / (hi2 - lo2)))
    def check(got, want, what): assert len(got) == len(want) and all(near(g, (X(a), Ys(b))) for g, (a, b) in zip(got, want)), (what, got, [(X(a), Ys(b)) for a, b in want])
    for k, w in (('spent', [(0, 0), (13.2, 13.2)]), ('togo', [(0, 2), (13.2, 1)]), ('total', [(0, 2), (13.2, 14.2)]),
                 ('guide', [(13.2, 14.2), (14.2, 14.2), (14.2, 0)])): check(polys[k], w, k)
    bands = {a['class']: pts(a['points']) for tag, a, _ in els if tag == 'polygon'}
    assert sorted(bands) == ['band togo', 'band total'], bands.keys()
    check(bands['band togo'], [(0, 4), (13.2, 3), (13.2, 0.5), (0, 1)], 'band togo')
    # elapsed + ETA's band crosses the break twice, so it gets each crossing on both edges of the gap (2026-10-23)
    xc = 13.2 * (cap - 4) / (16.2 - 4)
    want = [(X(0), Ys(4)), (X(xc), YB), (X(xc), YT), (X(13.2), Ys(16.2)), (X(13.2), YT), (X(13.2), YB), (X(13.2), Ys(13.7)), (X(0), Ys(1))]
    assert len(bands['band total']) == len(want) and all(near(g, w) for g, w in zip(bands['band total'], want)), (bands['band total'], want)
    lines = [(a['class'], tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2')), a) for tag, a, _ in els if tag == 'line']
    assert sorted(c for c, _, _ in lines) == sorted(['axis', 'ahead', 'ideal', 'range togo', 'range total', 'cross'] + ['grid'] * 4 + ['break'] * 2 + ['yaxis'] * 2), [c for c, _, _ in lines]
    seg = {c: s for c, s, _ in lines if c not in ('grid', 'break', 'yaxis')}
    check([seg['ahead'][:2], seg['ahead'][2:]], [(13.2, 13.2), (14.2, 14.2)], 'ahead')
    check([seg['ideal'][:2], seg['ideal'][2:]], [(13.2, 1), (14.2, 0)], 'ideal')
    check([seg['range togo'][:2], seg['range togo'][2:]], [(13.2, 0.5), (13.2, 3)], 'range togo')
    check([seg['range total'][:2], seg['range total'][2:]], [(13.2, 13.7), (13.2, 16.2)], 'range total')
    assert abs(seg['axis'][1] - Y(0)) < 0.05 and seg['axis'][1] == seg['axis'][3], seg['axis']
    grid = [s for c, s, _ in lines if c == 'grid' and s[1] > YB]       # the main panel's
    hours = sorted((y0 - g[1]) / (y0 - Y(1)) for g in grid)              # to 0.01 h: positions are written to 0.01 units
    assert len(hours) == 3 and all(abs(h - t) < 0.01 for h, t in zip(hours, (5, 10, 15))) and all(g[1] == g[3] for g in grid), grid
    assert [s[1] for c, s, _ in lines if c == 'grid' and s[1] < YB] == [14], lines     # the top panel's, at 20 h, its top
    assert sorted(round(y, 2) for c, s, _ in lines if c == 'yaxis' for y in (s[1], s[3])) == sorted([round(YT, 2), round(YB, 2), 14, round(Y(0), 2)]), lines   # its y axis's ends at the break
    cross = next(a for c, _, a in lines if c == 'cross')
    assert cross.get('visibility') == 'hidden', cross
    yt = [(float(a['y']), text) for tag, a, text in els if tag == 'text' and a.get('class') == 'ytick']
    assert [v for _, v in yt] == ['0', '5', '10', '15\u202fh', '20\u202fh'] and all(abs(y - 4 - Ys(int(v.split()[0]))) < 0.05 for y, v in yt), yt   # up to the cap, 15.62 h, then the top panel's (2026-10-23; to 20 h before)
    xt = [(float(a['x']), text) for tag, a, text in els if tag == 'text' and a.get('class') == 'xtick']
    assert [v for _, v in xt] == ['0', '5', '10', '15\u202fh'] and all(abs(x - X(int(v.split()[0]))) < 0.05 for x, v in xt), xt
    now = {a['class'].split()[1]: (float(a['cx']), float(a['cy'])) for tag, a, _ in els if tag == 'circle'}
    assert sorted(now) == ['spent', 'togo', 'total'], now
    check([now['spent'], now['togo'], now['total']], [(13.2, 13.2), (13.2, 1), (13.2, 14.2)], 'now')
    labels = {a['class'].split()[1]: (float(a['x']), float(a['y']), text) for tag, a, text in els
              if tag == 'text' and a.get('class', '').startswith('label ')}
    assert labels == {}, labels
    # With the labels (until 2026-10-17; back with them):
    # assert {k: v for k, (_, _, v) in labels.items()} == {'togo': '0.5–3.0\u202fh', 'total': '14–16\u202fh', 'spent': '13\u202fh'}, labels
    # for k, h in (('togo', 1), ('total', 14.2)):
    #     x, y, _ = labels[k]
    #     assert X(13.2) < x < X(13.2) + 20 and abs(y - Y(h)) < 16, (k, labels[k], X(13.2), Y(h))
    # x, y, _ = labels['spent']
    # assert abs(x - X(13.2)) < 0.05 and y > Y(0), (labels['spent'], X(13.2), Y(0))
    style = re.sub(r'/\*.*?\*/', '', page()[page().index('<style>'):page().index('</style>')], flags=re.S)   # live rules only
    assert re.search(r'--progress-spent: #2a78d6;', style) and re.search(r'--progress-togo: #e34948;', style) and re.search(r'--progress-total: #7b1fa2;', style)
    widths = {k: float(w) for k, w in re.findall(r'\.progress-eta \.(spent|togo|total) \{[^}]*stroke-width: ([\d.]+)', style)}
    assert set(widths) == {'spent', 'togo', 'total'} and widths['total'] > max(widths['spent'], widths['togo']), widths
    fills = dict(re.findall(r'\.progress-eta \.label\.(togo|total|spent) \{ fill: var\(--([\w-]+)\); \}', style))
    assert fills == {}, fills
    # With the labels (until 2026-10-17; back with them):
    # assert fills == {'togo': 'progress-togo', 'total': 'progress-total', 'spent': 'progress-spent'}, fills
    tints = {(b, s): c for b, s, c in re.findall(r'\.progress-eta \.(band|range)\.(togo|total) \{ [\w-]+: color-mix\(in oklab, var\(--progress-(togo|total)\) \d+%', style)}
    assert tints == {(b, s): s for b in ('band', 'range') for s in ('togo', 'total')}, tints
    dots = dict(re.findall(r'\.progress-eta \.now\.(spent|togo|total) \{ fill: var\(--progress-([\w-]+)\);', style))
    assert dots == {'spent': 'spent', 'togo': 'togo', 'total': 'total'}, dots
    assert not re.search(r'\.finish\b', style), 'a rule for the finish marker'
    assert re.search(r'\.progress-eta \.guide \{ stroke: var\(--progress-total\);', style), 'the guide not purple'
    assert all(re.search(rf'\.progress-eta \.{k} \{{[^}}]*mix-blend-mode: multiply;', style) for k in ('band', 'range')), 'an overlap hidden'
    assert R['status']['legends'] == 0, R['status']

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
