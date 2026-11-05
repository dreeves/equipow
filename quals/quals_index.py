#!/usr/bin/env python3
"""Quals for index.html's chart of m*(n) for the even n up to 1024.  Run: python3 -B quals/quals_index.py [name ...]
(no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The static quals read index.html, the stylesheet and scripts it links in page/ (inline in it until 2026-10-31) and
mstar.js (and, for the changelog, index.html's git history and sourcery.html).  The browser quals load a copy of
index.html in headless Chrome (in an iframe of the width each configuration asks for, since the window cannot be
narrower than 500 px), in a temporary directory with a copy of page/, of mstar.js (or made-up data) and of pow2.js (the
data of the page's chart of powers of 2), with two scripts added:
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

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
INDEX = os.path.join(HERE, 'index.html')
DATA = os.path.join(HERE, 'mstar.js')         # made by mstar.py; the chart's data
POW2 = os.path.join(HERE, 'pow2.js')          # made by pow2.py; the data of the chart of powers of 2, also on the page
PAGE_DIR = os.path.join(HERE, 'page')         # the page's stylesheet and scripts, which index.html links (2026-10-31)
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TOKENS = ('--exists', '--open', '--impossible')                    # the chart's three colors, in the order of kind
PROVENANCE = ('--claude', '--stan')
NMAX, MIN_SPAN = 1024, 12                     # 1000 until 2026-10-27, when the chart reached 1024
# The chart's columns (dreeves, 2026-10-29: "can we make my "odd multiple of 2" bullet point be true?"): n = 2 and the
# multiples of 4.  An odd n has no partition at any m, and every other n = 2 mod 4 has m*(n) = 1 (the two lemma), so
# those are left out.  (Every even n until 2026-10-29.)
COLUMNS = [2] + list(range(4, NMAX + 1, 4))
NCOL = len(COLUMNS)
STEPS = (4, 20, 40, 100, 200, 500)            # the steps of the n labels: round multiples of 4 (2, 10, 20, 50, ... before)
RUNS = {}                                     # browser runs by configuration name, made once per process (see run)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the page

def page(): return open(INDEX, encoding='utf-8').read()


def page_css():
    """The page's own stylesheet: the one file of page/ that index.html links as a stylesheet, page/style.css (a <style>
    block in index.html until 2026-10-31)."""
    [href] = re.findall(r'<link rel="stylesheet" href="(page/[^"]+)">', page())
    return open(os.path.join(HERE, href), encoding='utf-8').read()


def page_scripts(text):
    """The texts of the page's own scripts in text (index.html or a part of it), in order: each <script src="page/…">,
    read from its file (index.html's inline scripts until 2026-10-31, each the same text but for the newline after
    <script>)."""
    return [open(os.path.join(HERE, src), encoding='utf-8').read()
            for src in re.findall(r'<script src="(page/[^"]+)"></script>', text)]


def copy_page_dir(d):
    """A copy of page/, the page's stylesheet and scripts, in directory d, beside the copy of index.html there."""
    shutil.copytree(PAGE_DIR, os.path.join(d, 'page'))


def the_theorem(text):
    """The text of the powers-of-2 section's theorem in text (index.html), after its label, "Theorem 1." (dreeves's
    README, 2026-11-04: "[THM] Call the theorem in equipow Theorem 1"; it was "Theorem 1." from 819936b, 2026-10-17,
    and "Theorem." from 699517e, 2026-10-27, until then)."""
    [t] = re.findall(r'<p><b>Theorem 1\.</b>(.*?)</p>', text, re.S)
    return t


def section():
    """The chart's section: the HTML from <section class="mstar" to its </section>."""
    text = page()
    m = re.search(r'<section class="mstar".*?</section>', text, re.S)
    assert m, 'no <section class="mstar">'
    return m.group(0)


def theme_blocks():
    """The custom properties of the page's one theme block, :root, as a one-item list (dreeves, 2026-10-12: no dark
    mode, so no other theme block)."""
    css = page_css()
    whole = page() + css + ''.join(page_scripts(page()))           # the page with its stylesheet and scripts
    ms = list(re.finditer(r'\n:root \{(.*?)\n\s*\}', css, re.S))
    assert len(ms) == 1 and 'prefers-color-scheme' not in whole and 'data-theme' not in whole
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
    """The n of a cell of an n row: its digits, or 2^k for \\(2^{k}\\) (LaTeX since 2026-10-28; one digit unbraced) or,
    in the page's versions before that, for 2<sup>k</sup>."""
    m = re.fullmatch(r'(\d+)|\\\(2\^\{?(\d+)\}?\\\)|2<sup>(\d+)</sup>', cell)
    assert m, cell
    return int(m.group(1)) if m.group(1) else 2 ** int(m.group(2) or m.group(3))


def bounds(v):
    """(low, high) for a table's value v: an exact value v gives (v, v); 'a or b' and 'a–b' give (a, b); '\\(\\ge a\\)'
    (LaTeX since 2026-10-28) or, in the page's versions before that, '≥ a' gives (a, inf)."""
    forms = ((r'(\d+)', lambda a: (a, a)), (r'(\d+) or (\d+)', lambda a, b: (a, b)), (r'(\d+)–(\d+)', lambda a, b: (a, b)),
             (r'\\\(\\ge (\d+)\\\)', lambda a: (a, math.inf)), (r'≥ (\d+)', lambda a: (a, math.inf)))
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
# of the theorem, a new smallest k known to beat Thue-Morse by e (firsts()), stated by its low alone, as the theorem states
# it.  Other bounds built from partitions of other lengths, by doubling, joining or multiplying them, are left to the
# table and the charts: a lower bound whose reason in the m*(n) chart is BUILT, along with the upper bound stated with
# it (that entry waits for a partition of its own), and every other power of 2 past NMAX.  The chat's statements (CHAT)
# are its reports of partitions and proofs, made before the chart.
BUILT = ('join', 'product')
FIRST_CHART = '917fe7f'    # mstar.js's first commit (2026-10-11 16:24, "New chart etc"), whose reasons serve the days before


def firsts(cells):
    """{e: the smallest k with low(2^k) - k >= e}, for e from 1 up, over the powers of 2 among cells ({n: (low, high)}):
    the thresholds of the theorem as the block stood."""
    pows = {n.bit_length() - 1: lo for n, (lo, _) in cells.items() if n & (n - 1) == 0}
    top = max((lo - k for k, lo in pows.items()), default=0)
    return {e: min(k for k, lo in pows.items() if lo - k >= e) for e in range(1, top + 1)}


def records(before, after):
    """{2^k: (low, None)}: the powers of 2 whose low in after sets a threshold of the theorem that before's did not."""
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
               'first that can, since m*(2^9) = 9'),
              ('2026-11-03', 432, (11, 11), 'settles a(11) = 480 of OEIS A323395, order 12 being ruled out at 448 and 464 already'),
              ('2026-11-03', 720, (13, None), 'the smallest length known with order 13, down from 912 that morning and 960 '
               'before'),
              ('2026-11-03', 960, (15, 15), 'the smallest length known with order 15, down from 3840, and the first allowed it: '
               'settles a(14) = 960 of OEIS A323395'),
              ('2026-11-04', 672, (13, 13), 'the smallest length known with order 13, down from 720'))


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
  __texts.push(String(t)); __fills.push([String(t), x, y, this.fillStyle]); return __fillText.call(this, t, x, y, ...rest); };
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
  // The fold of the remarks' list ([REO] step 2, 2026-11-03), as the page loads: whether it is there and open, and
  // whether its summary and its list are shown
  const fold = document.querySelector('section.remarks details');
  R.fold = {there: fold !== null, open: fold?.open ?? null, summary: fold?.querySelector(':scope > summary')?.checkVisibility() ?? null,
            list: fold?.querySelector(':scope > ul')?.checkVisibility() ?? null};
  R.canvasCss = [rect().width, rect().height];
  R.canvasDev = [cv.width, cv.height];
  R.dpr = devicePixelRatio; R.innerW = innerWidth; R.scrollW = document.documentElement.scrollWidth;
  const main = document.querySelector('main'), ms = getComputedStyle(main);
  R.mainContentW = main.clientWidth - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight);
  // The running text's right edges (2026-10-29): each p and li of main outside the legends, as [its id, its
  // text-align, its right edge in CSS px from the left of main's content box].
  const mainLeft = main.getBoundingClientRect().left + parseFloat(ms.paddingLeft);
  R.prose = [...main.querySelectorAll('p, li')].filter(e => !e.closest('.legend')).map(e =>
    [e.id, getComputedStyle(e).textAlign, e.getBoundingClientRect().right - mainLeft]);
  // Each section of main (2026-10-30): [its class, the least vertical space in CSS px between two of its children laid
  // out one after the other], null with fewer than two laid out.
  R.sectionGaps = [...main.querySelectorAll(':scope > section')].map(sec => {
    const boxes = [...sec.children].filter(e => e.getClientRects().length > 0).map(e => e.getBoundingClientRect());
    return [sec.className, boxes.length > 1 ? Math.min(...boxes.slice(1).map((b, i) => b.top - boxes[i].bottom)) : null];
  });
  R.touchAction = getComputedStyle(cv).touchAction;
  // each n's first drawn text: its digits, or the 2 of 2^k, which KaTeX draws (since 2026-10-28) in its HTML beside
  // a hidden MathML copy that is skipped
  R.nTextBottoms = [...document.querySelectorAll('.new-block tr.ns')].map(tr => [...tr.querySelectorAll('td')].map(td => {
    const drawn = x => x.textContent.trim() && !x.parentElement.closest('.katex-mathml');
    const t = document.createTreeWalker(td, NodeFilter.SHOW_TEXT,
      {acceptNode: x => drawn(x) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP}).nextNode(), r = document.createRange();
    r.selectNodeContents(t); return r.getBoundingClientRect().bottom; }));
  // The page's math once it loaded (2026-10-30, q_scripts_load_data_then_draw): the formulas KaTeX drew, its error
  // marks, and the texts outside scripts, styles and formulas that still hold a \( or \).
  const raw = [], walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    if (!t.parentElement.closest('script, style, .katex') && /\\[()]/.test(t.data)) raw.push(t.data.slice(0, 80));
  }
  R.math = {formulas: document.querySelectorAll('.katex').length, errors: document.querySelectorAll('.katex-error').length, raw,
            unsupported: document.querySelectorAll('.katex-mathml mstyle[mathcolor="#cc0000"]').length};
  // Where the page shows "index.html" once its scripts ran (dreeves's README, 2026-10-31, [IND]: "we should never refer
  // to "index.html" in user-facing copy"): each text of the body outside scripts and styles that holds it, and each
  // attribute of an element of the body that does, as up to 80 characters of it.
  R.indexHtml = [];
  for (let t = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), x = t.nextNode(); x; x = t.nextNode())
    if (!x.parentElement.closest('script, style') && x.data.includes('index.html')) R.indexHtml.push(x.data.slice(0, 80));
  for (const e of document.body.querySelectorAll('*'))
    for (const a of e.attributes) if (a.value.includes('index.html')) R.indexHtml.push(`${e.tagName} ${a.name}: ${a.value.slice(0, 80)}`);
  // The page's links to its own anchors (2026-10-31, [IND]): for each a[href^="#"] of main, [its href, the tag of the
  // element whose id the href names (null when none has it), whether KaTeX drew it].
  R.anchors = [...document.querySelectorAll('main a[href^="#"]')].map(a => {
    const target = document.getElementById(a.getAttribute('href').slice(1));
    return [a.getAttribute('href'), target && target.tagName, !!a.closest('.katex')];
  });
  if (cv.height === 0) return;
  const tok = name => getComputedStyle(cv).getPropertyValue(name).trim().toLowerCase();
  const C = {exists: tok('--exists'), open: tok('--open'), impossible: tok('--impossible'), paper: tok('--paper'), ink: tok('--ink'),
             record: tok('--record')};
  R.tokens = C;
  const dpr = devicePixelRatio, ctx = cv.getContext('2d'), T = MSTAR.mtop, cols = MSTAR.cols;
  const colorOf = (n, m) => m <= cols[n - 1][0] ? C.exists : m <= cols[n - 1][1] ? C.open : C.impossible;
  // The cells ringed in gold, as the table of smallest lengths has them (dreeves's README, 2026-10-30, [GLT]; the proven
  // ones alone, a(m − 1) of OEIS A323395, since 2026-10-19): for each order m that some n reaches, [n, m, role] for the
  // least n known to reach m and the least n whose upper bound allows m, role 1 known, 2 not ruled out, 3 both (proven
  // the least, also dotted in gold).  A ring spoils the pixels around its cell, in its row and the row above, so the
  // generic checks pass over the columns next to it there, and checkPixels checks the ring itself and its cell's middle
  // (RINGS, ringChecks, ringBad).
  const least = test => cols.findIndex(test) + 1;
  const RINGS = [];
  for (let m = 1; least(c => c[1] >= m); m++) {
    const known = least(c => c[0] >= m), possible = least(c => c[1] >= m);
    for (const n of [...new Set([known, possible])].filter(n => n > 0)) RINGS.push([n, m, (n === known) + 2 * (n === possible)]);
  }
  R.rings = RINGS; R.ringChecks = 0; R.ringBad = []; R.ringed = {}; R.rowOneSkips = 0;
  const colOf = new Map(COLS.map((n, i) => [n, i + 1]));          // the column j of each n with one, from 1
  const nearRing = (j, m) => RINGS.some(([n, r]) => Math.abs(j - colOf.get(n)) <= 1 && (m === r || m === r + 1));
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
  // The tags of the cell read out (dreeves's README, 2026-11-02: "[HOV] When hovering/clicking on cells in the charts
  // it'd be nice to highlight the values of m and n (resp., delta and k) on the axes of the chart"), as the last draw
  // left them (tags): what was written in paper since __fills was last emptied, as [string, x, y] in device px; and
  // the boxes of ink, [X0, X1, Y0, Y1] (inclusive) or null, left of the plot (from 26 device px per CSS px left of it
  // to 3 short of it, where an outline of a cell of the first column may reach) above the n axis, and below the plot
  // (from 25 left of it to the canvas's right edge) on the n axis: there nothing but a tag is ink, the letters m and n
  // lying further left (the italic m's right edge reaches 30 left of it).  R.tags0 is at load, before any hover.
  const axisTop = rows[T - 1][1] + 1;                              // the n axis's top, past row 1's bottom device px of paper
  const inkBox = (X0, X1, Y0, Y1) => {
    let b = null;
    for (let Y = Y0; Y < Y1; Y++) for (let X = X0; X < X1; X++) {
      if (pix(X, Y) === C.ink) b = b ? [Math.min(b[0], X), Math.max(b[1], X), Math.min(b[2], Y), Math.max(b[3], Y)] : [X, X, Y, Y];
    }
    return b;
  };
  const tags = () => { snap(); return {paper: __fills.filter(f => f[3] === C.paper).map(f => f.slice(0, 3)),
    left: inkBox(PL - 26 * dpr, PL - 3 * dpr, 0, axisTop), below: inkBox(PL - 25 * dpr, cv.width, axisTop, cv.height)}; };
  R.axisTop = axisTop;
  R.tags0 = tags();
  const L = PL / dpr, W = (PR - PL) / dpr, yProbe = rowY(1) / dpr;      // CSS px
  const ptr = (type, x, y, o) => { const r = rect(), e = new PointerEvent(type, {clientX: r.left + x, clientY: r.top + y,
    pointerId: 1, pointerType: 'mouse', buttons: 0, bubbles: true, cancelable: true, ...o}); cv.dispatchEvent(e); return e; };
  const cellOf = t => { const m = t.match(/^n = (\d+), m = (\d+) · /); return m ? [+m[1], +m[2]] : null; };
  // Every hover's readout is counted, and kept if it reports an n that has no column (odd, or 2 mod 4 but 2).
  const hover = (x, y) => { ptr('pointermove', x, y, {}); const t = ro.textContent, c = cellOf(t);
    R.readouts++; if (c && !colOf.has(c[0])) R.hiddenReadouts.push(t); return t; };
  // Column j is n = COLS[j - 1]: jAt is the column read out at CSS x in row 1.
  const jAt = x => { const c = cellOf(hover(x, yProbe)); if (!c || !colOf.has(c[0])) throw new Error('no column read out at ' + x);
    return colOf.get(c[0]); };
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
          const want = colorOf(COLS[j - 1], m), got = pix(X, Math.floor(rowY(m))), gap = pix(X, rows[T - m][1]);
          R.pixelChecks++;
          if (got !== want || gap !== C.paper) R.pixelBad.push([COLS[j - 1], m, want, got, gap]);
        }
        R.pixelColumns[COLS[j - 1]] = 1;
      }
      for (const [n, r, role] of RINGS) {   // a ringed cell in this pass: gold just outside its left and right and below
        const j = colOf.get(n);              // it, and at its middle gold where it is proven the least, else its color
        if (j < from || j > to) continue;
        const Y = Math.floor(rowY(r)), x0 = PL + (j - 1 - v.u0) / k, x1 = PL + (j - v.u0) / k, xm = PL + Math.floor((j - 0.5 - v.u0) / k);
        const got = [pix(Math.floor(x0 - dpr), Y), pix(Math.floor(x1 + dpr), Y), pix(xm, rows[T - r][1]), pix(xm, Y)];
        const want = [C.record, C.record, C.record, role === 3 ? C.record : colorOf(n, r)];
        R.ringChecks++; R.ringed[`${n},${r}`] = 1;
        if (got.some((c, i) => c !== want[i])) R.ringBad.push([n, r, role, got, want]);
      }
    }
  }
  // Row 1 is exists in every column and impossible at every odd n, so with no odd n drawn, even mixed into a pixel,
  // every pixel of row 1 is exists.  The outline of the cell read out goes to row T first.  ringBands(v, m): where
  // the rings of row m run in view v, and (since 2026-10-30) the gold dot of a cell of row m proven the least, half the
  // smaller of the column's width and the row's colored height across, each a device px either side.
  const ringBands = (v, m) => { const k = v.span / (PR - PL); return RINGS.filter(([, r]) => r === m).flatMap(([n, , role]) => {
    const x0 = PL + (colOf.get(n) - 1 - v.u0) / k, x1 = PL + (colOf.get(n) - v.u0) / k, d = Math.min(1 / k, rows[0][1] - rows[0][0]) / 4;
    return [[x0 - 2 * dpr - 1, x0 + 1], [x1 - 1, x1 + 2 * dpr + 1]].concat(role === 3 ? [[(x0 + x1) / 2 - d - 1, (x0 + x1) / 2 + d + 1]] : []);
  }); };
  // The column lines of view v (the hairline grid, 2026-10-29): once columns are wider than 4 CSS px, a device px of
  // paper at each boundary of whole columns, over the cells at opacity (w - 4) / 4 up to 1, w a column's CSS px; each
  // as its zone, a device px either side of where it falls, with that opacity.
  const lineZones = v => {
    const k = v.span / (PR - PL), alpha = Math.min(Math.max((1 / (k * dpr) - 4) / 4, 0), 1), zones = [];
    for (let c = Math.floor(v.u0) + 1; alpha > 0 && c < v.u0 + v.span; c++) {
      const X = PL + Math.floor((c - v.u0) / k);
      zones.push([X - 1, X + 1, alpha]);
    }
    return zones;
  };
  const rgbOf = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  // Each zone in row 1 (exists on both sides) inside the plot and away from a ring: exactly one pixel off exists,
  // paper over exists at the zone's opacity, within 3 per channel.
  function checkZones(zones, bands, tag) {
    const Y = Math.floor(rowY(1)), e = rgbOf(C.exists), p = rgbOf(C.paper);
    for (const [a, b, alpha] of zones.filter(([a, b]) => PL <= a && b < PR && !bands.some(([x, y]) => x <= b && a <= y))) {
      const px = []; for (let X = a; X <= b; X++) px.push(pix(X, Y));
      const off = px.filter(c => c !== C.exists), want = e.map((v, j) => v + alpha * (p[j] - v));
      R.lineZones++;
      if (off.length !== 1 || rgbOf(off[0]).some((v, j) => Math.abs(v - want[j]) > 3)) R.lineBad.push([tag, a, px, want]);
    }
  }
  function checkRowOne(v, i) {     // but where a ring of row 1 runs, a device px either side (rowOneSkips), and the
    hover(middleX(v, first(v)), rowY(T) / dpr);   // zones of the column lines (rowOneLines), which checkZones checks
    snap();
    const bands = ringBands(v, 1), zones = lineZones(v);
    for (let X = PL, Y = Math.floor(rowY(1)); X < PR; X++) {
      if (bands.some(([a, b]) => a <= X && X <= b)) { R.rowOneSkips++; continue; }
      if (zones.some(([a, b]) => a <= X && X <= b)) { R.rowOneLines++; continue; }
      R.rowOneChecks++;
      if (pix(X, Y) !== C.exists) R.rowOneBad.push([i, X, pix(X, Y)]);
    }
    checkZones(zones, bands, i);
  }
  // Row 2 is exists in every column but n = 2's and impossible at every n = 2 mod 4, so with no other such n drawn,
  // even mixed into a pixel, every pixel of row 2 right of n = 2's column is exists; but n = 2's column and a device
  // px past it, the ring of row 2 and the zones of the column lines (rowTwoSkips).
  function checkRowTwo(v, i) {
    hover(middleX(v, first(v)), rowY(T) / dpr);
    snap();
    const k = v.span / (PR - PL), bands = ringBands(v, 2), zones = lineZones(v), start = PL + (1 - v.u0) / k + 1;
    for (let X = PL, Y = Math.floor(rowY(2)); X < PR; X++) {
      if (X <= start || [...bands, ...zones].some(([a, b]) => a <= X && X <= b)) { R.rowTwoSkips++; continue; }
      R.rowTwoChecks++;
      if (pix(X, Y) !== C.exists) R.rowTwoBad.push([i, X, pix(X, Y)]);
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
      const n = COLS[j - 1], [lo, hi] = cols[n - 1];
      for (const m of new Set([lo, lo + 1, hi + 1, ...RINGS.filter(([rn]) => rn === n).map(([, rm]) => rm)])) {   // and its ringed cells
        if (m < 1 || m > T) continue;
        R.hovers.push([n, m, hover(middleX(v, j), rowY(m) / dpr)]);
        const {backgroundColor, boxShadow, backgroundImage} = getComputedStyle(ro.querySelector('.swatch'));
        R.swatches.push([n, m, backgroundColor, boxShadow, backgroundImage]);
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
  R.readouts = 0; R.hiddenReadouts = [];
  R.views = [view()];
  R.hovers = []; R.swatches = []; R.pixelChecks = 0; R.pixelBad = []; R.pixelColumns = {}; R.steps = {}; R.rowOneChecks = 0; R.rowOneBad = [];
  R.rowOneLines = 0; R.lineZones = 0; R.lineBad = []; R.rowTwoChecks = 0; R.rowTwoSkips = 0; R.rowTwoBad = [];
  R.labelDraws = [labels(R.views[0])];
  checkRowOne(R.views[0], 0);
  checkRowTwo(R.views[0], 0);
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
    checkRowTwo(v, R.views.length - 1);
    R.labelDraws.push(labels(v));
    if (v.u0 + v.span > NCOL - 1e-6) break;
    for (let i = 0; i < 6; i++) key('ArrowRight');
  }
  R.pixelColumns = Object.keys(R.pixelColumns).map(Number).sort((a, b) => a - b);
  // Zoomed in step by step until columns are wider than 4 CSS px (3 steps at 1280 px, about 6 px wide): the column
  // lines part drawn
  reset.click();
  let mid = view();
  for (let i = 0; i < 12 && (PR - PL) / mid.span / dpr <= 4; i++) { key('+'); mid = view(); }
  { const v = mid, zones = lineZones(v);
    R.midWidth = (PR - PL) / v.span / dpr; R.midZones = zones.length;
    hover(middleX(v, first(v)), rowY(T) / dpr); snap(); checkZones(zones, ringBands(v, 1), 'mid'); }
  // The cell read out is outlined in ink, just outside it.
  reset.click();
  for (let i = 0; i < 5; i++) key('+');
  {
    const v = view(), k = v.span / (PR - PL), j = Math.round(v.u0 + v.span / 2), n = COLS[j - 1], m = 2;
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
    R.tap = {want: [COLS[Math.floor(v.u0 + (x - L) * k)], 1], text: ro.textContent};
    ptr('pointerup', L + 0.2 * W, yProbe, {pointerId: 99});        // an up with no down: nothing happens
    R.tap.after = ro.textContent;
    const x2 = L + 0.63 * W;
    hover(L + 0.8 * W, rowY(5) / dpr);
    ptr('pointerdown', x2, yProbe, {buttons: 1}); ptr('pointerup', x2, yProbe, {});
    R.click = {want: [COLS[Math.floor(v.u0 + (x2 - L) * k)], 1], text: ro.textContent};
    R.clickPanel = panelReport();                                  // the panel the click opened ([REO], 2026-11-03)
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
  // The tags (q_axes_tag_the_cell_read_out), each from the draw of a hover, with the view and the readout then: in the
  // full view, its four corners (its first and last columns, in rows 1 and T) and a cell in the middle; in a view
  // zoomed in 5 steps and panned right an eighth of it, the same at the plot's very ends, where its columns are cut
  // (the first's middle out of view, the last's in), then its first whole column in row 2; then (tagAway) that view
  // panned right by a whole view with the keys alone, from the draw of the last press.
  R.tagHovers = [];
  const tagHover = (v, x, m) => { __fills.length = 0; const text = hover(x, rowY(m) / dpr); R.tagHovers.push({v, text, ...tags()}); };
  const tagCorners = v => [[L + 0.25, 1], [L + 0.25, T], [L + W - 0.25, T], [L + W - 0.25, 1], [L + W / 2, 3]]
    .forEach(([x, m]) => tagHover(v, x, m));
  reset.click();
  tagCorners(view());
  for (let i = 0; i < 5; i++) key('+');
  key('ArrowRight');
  {
    const v = view();
    tagCorners(v);
    tagHover(v, middleX(v, first(v)), 2);
    for (let i = 0; i < 7; i++) key('ArrowRight');
    __fills.length = 0;
    key('ArrowRight');
    const text = ro.textContent, t = tags();
    R.tagAway = {before: R.tagHovers.at(-1).text, text, ...t, v: view()};
  }
}
// The panel of the m*(n) chart's columns ([REO], 2026-11-03), or of the chart of powers of 2's (id), as it stands:
// whether it is hidden, the page's fragment, whether its heading has the focus and which element has it, the kinds of
// its texts (data-why) in order, its generated text with each formula KaTeX drew written back as its TeX, \( ... \),
// its links' hrefs, KaTeX's error marks in it, and the page's width then.  Since [REO] step 2 (2026-11-03) a panel
// also shows the remarks' entry of its length, the li that holds its p.entry, moved in: the generated text and links
// leave out the entries it shows, and the report gives their p.entry ids (entries) and texts (entryText) apart, with
// the ids of the p.entry still in the remarks' list, in order (listed), the ids that two elements of the page share
// (dups), and the fold of the list (fold): whether it is there, open and shown.  Since 2026-11-04 ([CEL], [ROC]) also the
// box's kind (data-kind: the kind of the cell clicked, column or row), its parts as [kind, text, whether it is of
// Claude's English: data-claude] (parts), its copies of
// codes (copies: [data-join, data-order, role, digits]) and its constructions (constructions: [data-construction,
// role, TeX]).
const HELD = 'li:has(> p.entry)';                                  // an entry of the remarks, wherever it is
function panelReport(id = 'mstar-panel') {
  const region = document.getElementById(id), c = region.cloneNode(true);
  c.querySelectorAll('.katex').forEach(k => k.replaceWith(`\\(${k.querySelector('annotation').textContent}\\)`));
  const held = [...c.querySelectorAll(HELD)];
  held.forEach(li => li.remove());
  const ids = [...document.querySelectorAll('[id]')].map(e => e.id), fold = document.querySelector('section.remarks details');
  return {hidden: region.hidden, hash: location.hash, focus: document.activeElement === region.querySelector('h3'),
          active: document.activeElement.id, whys: [...region.querySelectorAll('[data-why]')].map(e => e.dataset.why),
          heading: c.querySelector('h3').textContent, text: c.textContent.replace(/\s+/g, ' ').trim(),
          links: [...region.querySelectorAll('a[href]')].filter(a => !a.closest(HELD)).map(a => a.getAttribute('href')),
          errors: region.querySelectorAll('.katex-error').length, scrollW: document.documentElement.scrollWidth,
          entries: held.map(li => li.querySelector('p.entry').id), entryText: held.map(li => li.textContent.replace(/\s+/g, ' ').trim()),
          listed: [...document.querySelectorAll('section.remarks ul > li > p.entry')].map(p => p.id),
          dups: ids.filter((x, i) => ids.indexOf(x) !== i),
          fold: {there: fold !== null, open: fold?.open ?? null, shown: fold?.checkVisibility() ?? null},
          kind: region.dataset.kind ?? null,
          parts: [...c.querySelectorAll('[data-panel-body] > [data-why]')].map(e => [e.dataset.why, e.textContent.replace(/\s+/g, ' ').trim(),
                                                                                    e.hasAttribute('data-claude')]),
          copies: [...c.querySelectorAll('[data-panel-body] [data-join]')].map(e => [e.dataset.join, e.dataset.order, e.getAttribute('role'), e.textContent]),
          constructions: [...c.querySelectorAll('[data-panel-body] [data-construction]')].map(e => [e.dataset.construction, e.getAttribute('role'),
                                                                                                    e.textContent.trim()])};
}
// Every column's panel, opened by its fragment, nN, in turn (OPTS.panels; the run lifts Chrome's limit of 200 changes
// of a frame's address per 10 s, which these 514 changes pass in about 2 s), then the last one closed by its button
// (after); and the page loaded with a fragment, its panel open at load (OPTS.fragment): its report, then the report
// after Escape in its heading, and after the panel of n = 512 opened by its fragment and closed by its button.  Then
// ([REO] step 2, 2026-11-03) the entries' moves: 1024's panel again (again), a click on its code there (expanded: the
// code's aria-expanded and its box, in the panel or not, shown or not, its rows' k and marks), the powers-of-2 chart's
// panel of k = 10, n = 1024, whose entry is the same (crossed: both panels, and the box), its close button
// (crossClosed: both again), 512's panel and then 1024's while it is open (switched), and Escape (allClosed).
const hashed = h => new Promise(r => { addEventListener('hashchange', () => r(), {once: true}); location.hash = h; });
async function panels(R) {
  history.replaceState(null, '', location.pathname);
  R.innerW = innerWidth;
  R.panels = [];
  for (const n of COLS) { await hashed(`#n${n}`); R.panels.push({n, ...panelReport()}); }
  document.querySelector('#mstar-panel [data-panel-close]').click();
  R.after = panelReport();
}
async function fragment(R) {
  const region = document.getElementById('mstar-panel'), escape = () => new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true});
  const key = escape();
  R.fragment = panelReport();
  region.querySelector('h3').dispatchEvent(key);
  R.escaped = {...panelReport(), prevented: key.defaultPrevented};
  await hashed('#n512');
  R.reopened = panelReport();
  region.querySelector('[data-panel-close]').click();
  R.closed = panelReport();
  await hashed('#n1024');
  R.again = panelReport();
  const code = document.querySelector('code[id="1024:11"]');
  code.click();
  const box = () => document.getElementById(code.getAttribute('aria-controls'));
  const boxReport = () => ({expanded: code.getAttribute('aria-expanded'), inMstar: region.contains(box()),
    inPow2: document.getElementById('pow2-panel').contains(box()), inEntry: code.closest(HELD).contains(box()), shown: box().checkVisibility(),
    ks: [...box().querySelectorAll('[data-k]')].map(c => c.textContent), relations: [...box().querySelectorAll('[data-relation]')].map(c => c.textContent)});
  R.expanded = boxReport();
  await hashed('#k10');
  R.crossed = {mstar: panelReport(), pow2: panelReport('pow2-panel'), box: boxReport()};
  document.querySelector('#pow2-panel [data-panel-close]').click();
  R.crossClosed = {mstar: panelReport(), pow2: panelReport('pow2-panel'), box: boxReport()};
  await hashed('#n512');
  await hashed('#n1024');
  R.switched = panelReport();
  region.querySelector('h3').dispatchEvent(escape());
  R.allClosed = {mstar: panelReport(), pow2: panelReport('pow2-panel'), box: boxReport()};
}
// The boxes under the m*(n) chart (dreeves's README, 2026-11-03, [CEL] and [ROC]; since 2026-11-04, OPTS.boxes): in the
// chart's full view, located by its pixels as battery locates it, a click (pointerdown and pointerup) on each target of
// BOX_TARGETS in turn, [n, m] a cell, [n, null] the strip of the n labels under column n, [null, m] the strip of the m
// labels left of row m; then a hover on cell (4, 1), so that the outline of the cell read out leaves the target; then
// the box's report (boxReport): the panel's (panelReport), its kind (data-kind), its frame's color, its caret's middle
// and the middle there of the target's column (or of the m labels' strip), in CSS px from the viewport's left, its
// heading's swatch (classes, color, ring), its parts' kinds, the text of its parts of the kinds witness-* and proof-*
// (said, its math written back as TeX, Claude's quote with it where there is one), which of its parts are of Claude's
// English (claude: each part's data-claude),
// its copies of codes (data-join) and its constructions (data-construction), the searches' text, and the canvas's
// pixels where the target's outline goes, with the target's own color (its pixel at its middle, three quarters down its
// row, clear of the gold rings of the cells above and below and of its own gold dot).  Then (each with its report): the first
// target's box again, its code copy clicked (expanded: the box of the copy, its rows' k and marks); the box of cell
// (36, 2) and a click on its construction (derived: the derivation's rows and bound); the box of cell (528, 12) once
// its searches have loaded (searched); its close button (closed, with the pixels of its outline then); and the page's
// fragment set to #m16 and then #n1024m12 (hashed).
const BOX_TARGETS = [[1024, 8], [1024, 12], [528, 12], [480, 12], [480, 13], [672, 13], [240, 11], [1020, 4], [56, 6],
                     [36, 2], [80, 3], [1024, null], [null, 12], [null, 13], [null, 16]];
async function boxes(R) {
  const cv = document.getElementById('mstar-chart'), region = document.getElementById('mstar-panel');
  const tok = name => getComputedStyle(cv).getPropertyValue(name).trim().toLowerCase();
  const C = {exists: tok('--exists'), open: tok('--open'), impossible: tok('--impossible'), paper: tok('--paper'), ink: tok('--ink'),
             rule: tok('--rule')};
  R.tokens = C;
  const dpr = devicePixelRatio, ctx = cv.getContext('2d'), T = MSTAR.mtop;
  let img = null;
  const snap = () => { img = ctx.getImageData(0, 0, cv.width, cv.height); };
  const pix = (X, Y) => { const i = (Math.floor(Y) * img.width + Math.floor(X)) * 4, d = img.data;
    return '#' + [d[i], d[i + 1], d[i + 2]].map(v => v.toString(16).padStart(2, '0')).join(''); };
  const hex = rgb => '#' + rgb.match(/\d+/g).slice(0, 3).map(v => (+v).toString(16).padStart(2, '0')).join('');
  snap();
  const runs = [];                                 // the rows: runs of pixels not paper down the middle device column
  for (let Y = 0, s = -1, X = cv.width >> 1; Y <= cv.height; Y++) {
    const on = Y < cv.height && pix(X, Y) !== C.paper;
    if (on && s < 0) s = Y;
    if (!on && s >= 0) { runs.push([s, Y]); s = -1; }
  }
  const rows = runs.slice(0, T), rowY = m => (rows[T - m][0] + rows[T - m][1]) / 2;   // device px
  let PL = 0, PR = cv.width - 1;                   // the plot: the run of impossible pixels across row T
  while (pix(PL, rowY(T)) !== C.impossible) PL++;
  while (pix(PR, rowY(T)) !== C.impossible) PR--;
  PR++;
  const k = NCOL / (PR - PL), colOf = n => COLS.indexOf(n) + 1;     // columns per device px; column j from 1
  const x0 = j => PL + (j - 1) / k, x1 = j => PL + j / k;
  // where a target is, in device px of the canvas: a cell's middle; under column n, 10 CSS px below the plot; left of
  // row m, the middle of the strip left of the plot
  const placeOf = ([n, m]) => [n === null ? PL / 2 : (x0(colOf(n)) + x1(colOf(n))) / 2, m === null ? rows[T - 1][1] + 10 * dpr : rowY(m)];
  const ptr = (type, X, Y, o) => { const r = cv.getBoundingClientRect();
    cv.dispatchEvent(new PointerEvent(type, {clientX: r.left + X / dpr, clientY: r.top + Y / dpr, pointerId: 1, pointerType: 'mouse',
      buttons: 0, bubbles: true, cancelable: true, ...o})); };
  const click = t => { const [X, Y] = placeOf(t); ptr('pointerdown', X, Y, {buttons: 1}); ptr('pointerup', X, Y, {}); };
  const away = () => { const [X, Y] = placeOf([4, 1]); ptr('pointermove', X, Y, {}); };
  const tex = e => { const c = e.cloneNode(true);
    c.querySelectorAll('.katex').forEach(x => x.replaceWith(`\\(${x.querySelector('annotation').textContent}\\)`));
    return c.textContent.replace(/\s+/g, ' ').trim(); };
  // the pixels where target t's outline goes, just outside its cells: for a cell, left and right of it in its row;
  // for a column, left of it in rows 1 and T; for a row, above it at the plot's middle and a quarter of the way in
  const outlinePixels = ([n, m]) => { snap(); return n === null
    ? [pix((PL + PR) / 2, rows[T - m][0] - dpr), pix(PL + (PR - PL) / 4, rows[T - m][0] - dpr)]
    : m === null ? [pix(x0(colOf(n)) - dpr, rowY(1)), pix(x0(colOf(n)) - dpr, rowY(T))]
    : [pix(x0(colOf(n)) - dpr, rowY(m)), pix(x1(colOf(n)) + dpr, rowY(m))]; };
  const body = () => region.querySelector('[data-panel-body]');
  function boxReport(t) {
    const before = getComputedStyle(region, '::before'), b = region.getBoundingClientRect(), r = cv.getBoundingClientRect();
    const sw = region.querySelector('h3 .swatch'), said = [...body().querySelectorAll(':scope > [data-why^="witness"], :scope > [data-why^="proof"]')];
    snap();
    return {target: t, ...panelReport(), frame: hex(getComputedStyle(region).borderTopColor),
      caret: b.left + region.clientLeft + parseFloat(before.left) + parseFloat(before.borderLeftWidth),
      column: r.left + placeOf(t)[0] / dpr,
      own: t.includes(null) ? null : pix(placeOf(t)[0], rows[T - t[1]][0] + (rows[T - t[1]][1] - rows[T - t[1]][0]) * 3 / 4),   // clear of rings and dots
      swatch: sw && {cls: sw.className, color: hex(getComputedStyle(sw).backgroundColor), ring: getComputedStyle(sw).boxShadow},
      said: said.map(tex).join(' '),
      claude: [...body().children].map(e => e.hasAttribute('data-claude')),
      copies: [...body().querySelectorAll('[data-join]')].map(e => [e.dataset.join, e.dataset.order, e.getAttribute('role'), e.textContent]),
      constructions: [...body().querySelectorAll('[data-construction]')].map(e => [e.dataset.construction, e.getAttribute('role'), tex(e)]),
      searches: [...body().querySelectorAll('[data-why="searches"]')].map(e => e.innerText),
      tables: [...body().querySelectorAll('table')].map(table => [...table.rows].map(tr => [...tr.cells].map(tex))),
      outline: outlinePixels(t)};
  }
  R.table3 = [...document.querySelector('section.smallest table').rows].map(tr => [...tr.cells].map(tex));
  R.table4 = [...document.querySelector('[data-record-gaps]').querySelectorAll('thead tr, tbody tr')].map(tr => [...tr.cells].map(tex));
  // until the box's searches, if it has any, have loaded (at most 5 s)
  const loaded = async () => { for (let i = 0; i < 100 && [...body().querySelectorAll('[data-why="searches"] > div')].some(d => !d.childNodes.length); i++) await new Promise(r => setTimeout(r, 50)); };
  R.boxes = [];
  for (const t of BOX_TARGETS) {
    click(t);
    await loaded();
    away();
    R.boxes.push(boxReport(t));
  }
  // the first target's code copy, expanded (each of these two reports null where the box has no such button)
  click(BOX_TARGETS[0]);
  R.expanded = [...body().querySelectorAll('[data-join]')].slice(0, 1).map(copy => {
    copy.click();
    const shown = document.getElementById(copy.getAttribute('aria-controls'));
    return {expanded: copy.getAttribute('aria-expanded'), inBox: region.contains(shown), shown: shown.checkVisibility(),
            ks: [...shown.querySelectorAll('[data-k]')].map(c => c.textContent),
            relations: [...shown.querySelectorAll('[data-relation]')].map(c => c.textContent)};
  })[0] ?? null;
  // a construction's derivation
  click([36, 2]);
  R.derived = [...body().querySelectorAll('[data-construction]')].slice(0, 1).map(built => {
    built.click();
    const steps = document.getElementById(built.getAttribute('aria-controls'));
    return {expanded: built.getAttribute('aria-expanded'), inBox: region.contains(steps), shown: steps.checkVisibility(),
            rows: [...steps.querySelectorAll('[data-steps] tr')].map(tr => [tr.dataset.n, tr.dataset.m]),
            bound: steps.querySelector('[data-bound]').textContent.replace(/\s+/g, ' ').trim()};
  })[0] ?? null;
  // the searches of an open cell, once loaded
  click([528, 12]);
  await loaded();
  away();
  R.searched = boxReport([528, 12]);
  region.querySelector('[data-panel-close]').click();
  R.closed = {...panelReport(), outline: outlinePixels([528, 12])};
  await hashed('#m16');
  R.hashed = [boxReport([null, 16])];
  await hashed('#n1024m12');
  R.hashed.push(boxReport([1024, 12]));
}
// The page loaded with a box's fragment (OPTS.boxFragment, 2026-11-04): its box as the page shows it then.
async function boxFragment(R) {
  R.atLoad = {...panelReport(), kind: document.getElementById('mstar-panel').dataset.kind};
}
const R = {errors: window.__errors, opts: OPTS};
const go = async () => {
  try {
    if (OPTS.fragment) await fragment(R);
    else if (OPTS.panels) await panels(R);
    else if (OPTS.boxes) await boxes(R);
    else if (OPTS.boxFragment) await boxFragment(R);
    else battery(R);
  } catch (e) { R.harnessError = String(e && e.stack || e); }
  R.texts = [...new Set(window.__texts)];
  parent.postMessage(JSON.stringify(R), '*');
};
const NCOL = __NCOL__, COLS = __COLUMNS__;                         // the columns' n: 2, then the multiples of 4 to NMAX
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
    data = {'nmax': NMAX, 'mtop': max(c[1] for c in cols) + 1, 'mtopAt': [NMAX + 2], 'past': [], 'cols': cols}
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
    'mtopAt': (lambda data: data.update(mtopAt=[NMAX]), f'[[{NMAX}]]'),   # not past the chart (since 2026-11-03, [LIN])
    # since 2026-11-04 ([M17]) a list, one n per order from mtop on, which cannot fall: order m + 1 at n has order m there
    'mtopAt falls': (lambda data: data.update(mtopAt=[NMAX + 4, NMAX + 2]), f'[[{NMAX + 4},{NMAX + 2}]]'),
    'past': (lambda data: data.update(past=[[NMAX, 3, 'x']]), f"[[[{NMAX},3,'x']]]"),   # an example not past the chart (since 2026-11-04)
}


CONFIGS = {   # name: (mstar.js, window width, device pixel ratio, theme, hover every this many columns)
    'light': ('real', 1280, 2, None, 1),
    'phone': ('real', 390, 3, None, 5),
    'kinds': ('kinds', 1280, 2, None, 1),
    'missing': (None, 1280, 2, None, 1),
    'fragment': ('real', 1280, 2, None, 1),
    'phone fragment': ('real', 390, 3, None, 5),
    'panels': ('real', 1280, 2, None, 1),
    'phone panels': ('real', 390, 3, None, 5),
    'kinds panels': ('kinds', 1280, 2, None, 1),
    'boxes': ('real', 1280, 2, None, 1),
    'phone boxes': ('real', 390, 3, None, 5),
    'box fragment': ('real', 1280, 2, None, 1),
} | {f'violates {v}': (v, 1280, 1, None, 1) for v in VIOLATIONS}
PANELS = ('panels', 'phone panels', 'kinds panels')   # the configurations that open every column's panel in turn ([REO], 2026-11-03)
FRAGMENTS = {'fragment': '#n1024', 'phone fragment': '#n1024'}   # the configurations that load the page with a fragment
# the configurations that click the boxes' targets (the harness's boxes) and that load the page with a cell's fragment,
# each beside a made-up progress.js, BOX_PROGRESS (2026-11-04, [CEL] and [ROC])
BOXES, BOX_LOADS = ('boxes', 'phone boxes'), {'box fragment': '#n1024m12'}
SOURCES = {'real': lambda: open(DATA, encoding='utf-8').read(), 'kinds': kinds_data} | {
    v: (lambda v=v: kinds_data(v)) for v in VIOLATIONS}           # mstar.js's text, by CONFIGS's first entry


def run(name):
    """The harness's report for one configuration, made on first use."""
    if name not in RUNS:
        data, width, dpr, theme, every = CONFIGS[name]
        d = tempfile.mkdtemp(prefix='index-quals-')
        text = page()
        assert text.count('<head>\n') == 1 and text.count('</body>') == 1 and text.count('<html lang="en">') == 1
        opts = {'hoverEvery': every, 'panels': name in PANELS, 'fragment': name in FRAGMENTS, 'boxes': name in BOXES,
                'boxFragment': name in BOX_LOADS}
        text = text.replace('<head>\n', '<head>\n' + EARLY).replace('</body>', HARNESS.replace(
            '__OPTS__', json.dumps(opts)).replace('__NCOL__', str(NCOL)).replace('__COLUMNS__', json.dumps(COLUMNS)) + '</body>')
        if theme: text = text.replace('<html lang="en">', f'<html lang="en" data-theme="{theme}">')
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
        copy_page_dir(d)
        if data is not None: open(os.path.join(d, 'mstar.js'), 'w', encoding='utf-8').write(SOURCES[data]())
        shutil.copy(POW2, os.path.join(d, 'pow2.js'))
        if name in BOXES or name in BOX_LOADS:
            open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(BOX_PROGRESS) + ');\n')
        open(os.path.join(d, 'host.html'), 'w').write(HOST.replace('__WIDTH__', str(width)).replace(
            'src="index.html"', f'src="index.html{(FRAGMENTS | BOX_LOADS).get(name, "")}"'))
        dom = chrome(d, ['--disable-ipc-flooding-protection'] * (name in PANELS) + [f'--window-size={max(width, 500) + 40},1100', f'--force-device-scale-factor={dpr}',
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
    assert reports).  It lets file URLs read file URLs (--allow-file-access-from-files, since 2026-10-31, when the page's
    scripts left index.html for page/): plain file:// gives each file an origin of its own, so an uncaught error thrown
    in page/ reached the page's error listeners only as "Script error.", with no error object; over http(s), where the
    page is served, its files share its origin and the error comes through whole, as it does here with the flag."""
    p = subprocess.Popen([CHROME, '--headless=new', f'--user-data-dir={d}/profile', '--no-first-run',
                          '--no-default-browser-check', '--disable-extensions', '--allow-file-access-from-files', *args],
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
    """The lines Chrome logs from the page's console when it loads index.html as is, with page/ and the real mstar.js
    beside it."""
    d = tempfile.mkdtemp(prefix='index-quals-')
    shutil.copy(INDEX, os.path.join(d, 'index.html'))
    copy_page_dir(d)
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
# lengths proven: OEIS A323395's a(0) to a(8), 240 as a(9), and (2026-10-20) 432 as a(10), after proof384.py; and order 12 too, since 2026-11-03: 480 as a(11), after the pin tree of 432:12.
SMALLEST_PROVEN = (2, 4, 8, 16, 32, 48, 96, 144, 192, 240, 432, 480)
PROVEN_CELLS = [(n, m) for m, n in enumerate(SMALLEST_PROVEN, 1)] + [(960, 15)]   # the cells (n, m) proven least: (960, 15) since 2026-11-03


def smallest_rows(data):
    """The rows the section's script makes from MSTAR's cols, computed here: for each order m from 1 while some n's upper
    bound allows m (least_columns), the texts of m, the least length known to reach m, a check mark if that is also the
    least n whose upper bound is at least m (else nothing), and that least n.  (dreeves, 2026-10-30: "why isn't 480:14
    highlighted in the chart?"; until then the rows stopped at the largest order known at some n.)  The least length
    known is best[m] = min(the least n whose lower bound is at least m, best[a] best[m - a] for 0 < a < m), a product
    f(x) g(x^n), n the length of f, having order at least the sum of theirs (dreeves's README, 2026-10-31, [MIN]; until
    then — where no n up to NMAX was known to reach m).  Then a row for each order past the chart, from mtop, the order
    no n up to NMAX allows, each not ruled out first at its n of mtopAt, the least n past NMAX that the chart's own
    tests leave open at that order (mstar.mtop_at), and reached first at its least product (dreeves's README,
    2026-11-03: "[LIN] Add one more line for m=16 to the "smallest length known for each order" table", then "yes, 1440
    instead of ">1024" if that's all we know so far"; and 2026-11-04: "[M17] Let's add m=17 to the "smallest length
    known" table"; until 2026-11-03 the rows stopped at the largest order allowed, and until 2026-11-04 at mtop).  An
    example past the chart (mstar.js's past, since 2026-11-04) reaches its order at its own length, as a known n does,
    and so its length goes into the products of later orders (2880 = 1440 · 2 at order 17)."""
    cols, top, at = data['cols'], data['mtop'], data['mtopAt']
    rows = [(m, possible) for m, _, possible in least_columns(cols)] + [(top + i, n) for i, n in enumerate(at)]
    assert [m for m, _ in rows] == list(range(1, len(rows) + 1)), rows
    known = {m: n for m, n, _ in least_columns(cols) if n is not None}
    for n, m, _ in data['past']: known[m] = min(known.get(m, math.inf), n)
    best = {}
    for m, _ in rows: best[m] = min([known.get(m, math.inf)] + [best[a] * best[m - a] for a in range(1, m)])
    assert all(type(b) is int for b in best.values()), best
    # in the chart's order, the n not ruled out before the n known, the check mark last ([FLP], 2026-10-31)
    return [[str(m), str(possible), str(best[m]), '✓' if best[m] == possible else ''] for m, possible in rows]


def a323395_cells(cols):
    """The cells (n, m) the chart rings in gold and dots (dreeves, 2026-10-19), the proven ones of least_columns, whose
    least n known to reach m is also the least not ruled out: the terms a(m − 1) of OEIS A323395 that the data proves."""
    return [(known, m) for m, known, possible in least_columns(cols) if known == possible]


def smallest_rings(cols):
    """The cells the m*(n) chart rings in gold (dreeves's README, 2026-10-30, [GLT]), the chart's own least columns
    (least_columns), the table of smallest lengths' cells up to NMAX (its lengths from products beyond the chart, since
    2026-10-31, have no column): {(n, m): role} for the least n known of each order m and the least n not ruled out for
    it, one cell when they agree; role 1 known, 2 not ruled out, 3 both, proven the least (a323395_cells)."""
    out = {}
    for m, known, possible in least_columns(cols):
        for n in {known, possible} - {None}: out[(n, m)] = (n == known) + 2 * (n == possible)
    return out


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
    assert 'href="proof384.py"' in remark.group(1) and '\\(m^* = 10\\)' in remark.group(1), remark.group(1)[:300]
    assert smallest_rows(mstar_data())[10] == ['11', '432', '432', '✓']


def q_section_follows_table2():
    # Replicata: index.html.
    # Expectata: the page's one <figure> (Table 2) is followed, with only blank lines and comments between, by
    # <section class="mstar" aria-labelledby="mstar-title"> (and that by <section class="pow2" until 2026-10-30, when
    # dreeves put the smallest lengths between).  In order, the
    # section holds: a paragraph introducing the chart (dreeves's, which replaced the h2 mstar-title by 2026-10-27,
    # and since 2026-10-29 follows his h2 of that id and leads his list of the n left out);
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
    # byline, the lede lines next after the title, whatever his words there (one or more since 2026-10-29, dreeves:
    # "yes to allowing 2 lines for the byline"), with only comments between,
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
    m = re.match(r'  <h1>[^\n]*</h1>\n(?:  <p class="lede">[^\n]*</p>\n)+(?:  <!--[^\n]*-->\n)*'
                 r'  <details class="changelog">\n    <summary>[^\n]*</summary>\n(.*?)\n  </details>\n',
                 head.group(1) + '\n', re.S)
    assert m, head.group(1)[:800]
    lines = [l.strip() for l in m.group(1).split('\n') if not re.fullmatch(r'\s*<!-- TODO:.*-->', l)]
    entries = [re.fullmatch(r'<p>(\d{4}-\d{2}-\d{2}): (\S.*)</p>', l) for l in lines]
    assert entries and all(entries), lines
    return [e.groups() for e in entries]


# A statement of a new result's bounds in a changelog entry (dreeves, 2026-10-26: "yes please", to an entry with each
# update of the new results, and "can you backfill all the results that are new since the BGPW paper?"), in math, so
# without a Claude: "…": m*(n) = v, m*(n) ≥ a, m*(n) ≤ b or a ≤ m*(n) ≤ b, n's digits or 2^{k}, in LaTeX since 2026-10-28
STATEMENT = r'\\\((?:(\d+) \\le )?m\^\*\((\d+|2\^\{?\d+\}?)\) (=|\\ge|\\le) (\d+)\\\)'


def statements(rest):
    """{n: (low, high)} for an entry's rest: empty for an entry of his words; for one in math, its statements, joined by
    ', ' (nothing else), as statement() makes them: m*(n) = v (v, v), m*(n) ≥ a (a, None), m*(n) ≤ b (None, b) and
    a ≤ m*(n) ≤ b (a, b)."""
    found = re.findall(STATEMENT, rest)
    assert not found or re.fullmatch(f'{STATEMENT}(?:, {STATEMENT})*', rest), rest
    assert all(op == '\\le' for lo, _, op, _ in found if lo), rest
    out = {cell_n(n if n.isdigit() else f'\\({n}\\)'): (int(lo), int(v)) if lo else
           {'=': (int(v), int(v)), '\\ge': (int(v), None), '\\le': (None, int(v))}[op]
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
    # the theorem (dreeves, 2026-10-26: "we obviously want 2^17:18 and 2^24:25 in the changelog").
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
    copy_page_dir(d)
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


def q_page_links_its_stylesheet_after_katex_s():
    # Replicata: index.html; and the page 1280 px wide (framed): every formula KaTeX drew, and the element holding it.
    # Expectata (dreeves's README, 2026-10-30: "[FAC] ... getting css and javascript out of index.html"): no <style>
    # block; the page's own stylesheet is a file, page/style.css, linked once, in the head, right after KaTeX's
    # stylesheet and before any script, where the style block stood, so that the page's rules still come after KaTeX's
    # in the cascade and win where both match at equal specificity: every formula's font size is that of the element
    # holding it (.katex at 1em), not KaTeX's 1.21em.
    # Resultata before: the page's CSS was a <style> block in that place.
    text = page()
    head = text[:text.index('</head>')]
    assert '<style' not in text and text.count('href="page/style.css"') == 1, 'a style block, or not one link'
    assert re.search(r'\n<link rel="stylesheet" href="https://cdn\.jsdelivr\.net/npm/katex@0\.16\.47/dist/katex\.min\.css" '
                     r'[^>\n]*>\n<link rel="stylesheet" href="page/style\.css">\n', head), head[-1500:]
    assert head.index('href="page/style.css"') < head.index('<script'), 'a script before the stylesheet'
    got = framed(1280, """
  parent.postMessage(JSON.stringify([...document.querySelectorAll('.katex')].map(k =>
    [getComputedStyle(k).fontSize, getComputedStyle(k.parentElement).fontSize])), '*');""")
    assert len(got) > 800 and all(a == b for a, b in got), (len(got), [s for s in got if s[0] != s[1]][:5])


def q_page_dir_holds_what_index_links():
    # Replicata: the files in page/, and the files of page/ that index.html links, as its stylesheet or as scripts.
    # Expectata (dreeves's README, 2026-10-30: "[FAC] ... getting css and javascript out of index.html"): page/ holds
    # exactly those files, hidden files aside (as Finder's .DS_Store, which git ignores), each linked once: none is
    # missing and none unused.
    # Resultata before: no page/; the page's CSS and scripts were inline.
    linked = [a or b for a, b in re.findall(r'<link rel="stylesheet" href="page/([^"]+)">|<script src="page/([^"]+)"></script>',
                                            page())]
    there = sorted(n for n in os.listdir(PAGE_DIR) if not n.startswith('.'))
    assert linked and len(linked) == len(set(linked)) and sorted(linked) == there, (linked, there)


def q_scripts_load_data_then_draw():
    # Replicata: index.html's script tags and the files of the page's own scripts (in page/ since 2026-10-31: inline
    # scripts before, each the same text); and the light run's look at the page's math once it loaded (R's math).
    # Expectata: in the head, three: page/math.js, which defines a function, and then KaTeX's two (since 2026-10-28;
    # dreeves: "could you convert all the math on the page to latex"), deferred, from jsDelivr at version 0.16.47, each
    # with its SHA-256 integrity, auto-render's onload only a call of that function, with no & in any script tag of the
    # head (dreeves's README, 2026-10-30: "[VSC] VS Code isn't happy about the "&amp;&amp;" in one of the jsdelivr
    # lines for KaTeX"); then exactly eight (seven until 2026-10-31), after </main> and before </body>: the script of
    # the pan and zoom both charts share (2026-10-30, q_both_charts_share_one_pan_and_zoom; six scripts before),
    # page/shared.js; a classic <script src="mstar.js"> (no type, async or defer, so it also loads from file://) and
    # then the m*(n) chart's, page/mstar-section.js; then the chart of powers of 2's, likewise (quals_pow2_page.py holds
    # those two); then the script of the table of smallest lengths, which reads MSTAR (2026-10-17),
    # page/smallest-section.js; then the script of the page's codes, which makes each code a button that shows its
    # partition (2026-10-31, dreeves's [REO] item 2; quals_codes.py), page/codes.js; then the script of the section
    # "Search progress", which loads progress.js itself (2026-10-17), page/progress-section.js.  Each of the page's own
    # scripts is a classic <script src> of its file in page/ (dreeves's README, [FAC]: "getting css and
    # javascript out of index.html"), so that each runs where it stands, in order, as when it was inline, and loads
    # from file://.  Once the page has loaded, its math is drawn: KaTeX drew formulas, none of them an error, and no text
    # outside scripts, styles and formulas still holds a \( or \).  (Until 2026-10-30 this pinned onload's code,
    # character for character, and said that it also wrapped each formula and the text glued to it in an nw span
    # (2026-10-29); that code has never glued anything, auto-render putting each formula alone in a span of its own, so
    # the gluing is not expected here: scratch/readme-20261030/NOTES.md.)
    text = page()
    head, body = text[:text.index('</head>')], text[text.index('</head>'):]
    katex = re.search(r'\n<script src="(page/math\.js)"></script>\n'
                      r'<script defer src="https://cdn\.jsdelivr\.net/npm/katex@0\.16\.47/dist/katex\.min\.js" '
                      r'integrity="sha256-[A-Za-z0-9+/]{43}=" crossorigin="anonymous"></script>\n'
                      r'<script defer src="https://cdn\.jsdelivr\.net/npm/katex@0\.16\.47/dist/contrib/auto-render\.min\.js" '
                      r'integrity="sha256-[A-Za-z0-9+/]{43}=" crossorigin="anonymous" onload="(\w+)\(\)"></script>\n', head, re.S)
    tags = re.findall(r'<script\b[^>]*>', head)
    assert katex and len(tags) == 3 and not any('&' in t for t in tags), tags
    [math_js] = page_scripts(katex[0])
    assert re.search(rf'^function {katex[2]}\(\) \{{$', math_js, re.M), math_js[:300]
    assert re.findall(r'<script\b[^>]*>', body) == [
        '<script src="page/shared.js">', '<script src="mstar.js">', '<script src="page/mstar-section.js">',
        '<script src="pow2.js">', '<script src="page/pow2-section.js">', '<script src="page/smallest-section.js">',
        '<script src="page/codes.js">', '<script src="page/progress-section.js">'], re.findall(r'<script\b[^>]*>', body)
    own = page_scripts(body)
    assert 'function panZoom(' in own[0] and '[data-smallest]' in own[3] and 'template[data-partition]' in own[4] \
        and 'progressData' in own[5], [js[:60] for js in own]
    assert text.index('</main>') < text.index('<script src="page/shared.js">', len(head)) < text.index('<script src="mstar.js"></script>') < \
        text.index('</script>\n</body>')
    math = valid_run('light')['math']
    assert math['formulas'] > 800 and math['errors'] == 0 and math['raw'] == [], math


def q_chart_script_passes_node_check():
    # Replicata: the chart's script, the one that gets #mstar-chart (page/mstar-section.js since 2026-10-31, when this
    # qual was q_inline_script_passes_node_check; an inline script before, the page's first until 2026-10-30, when an
    # inline script for KaTeX came first in the head), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    [js] = [s for s in page_scripts(page()) if "getElementById('mstar-chart')" in s]
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
    css = page_css()
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
    # Replicata: index.html with page/, mstar.js, pow2.js and progress.js beside it, in headless Chrome with a window
    # 945 px wide: the widths of the new results' seven tables and of their sideways-scrolling frame (.new-block .scroll).
    # Expectata (the CSS comment on the new results' side padding: "keeps it in one row, unscrolled, at 945 px"; since
    # 2026-10-25, when the powers of 2 reached 23, their two rows too, and since 2026-10-26, when they reached 35 and
    # took three rows, those three; since 2026-10-27, when the block took in Table 2 and reached 1024, its six upper
    # rows, and since later that day the block's two frames, one for them and one for the powers of 2): no table is
    # wider than its frame, so neither frame scrolls.
    d = tempfile.mkdtemp(prefix='index-quals-')
    try:
        for name in ('mstar.js', 'pow2.js', 'progress.js'): shutil.copy(os.path.join(HERE, name), d)
        copy_page_dir(d)
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
    assert all(re.fullmatch(r'\\\(2\^\{?\d+\}?\\\)', c) for r in pows for _, c, *_ in r) and pows, [[c for _, c, *_ in r] for r in pows]
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
    # (Since 2026-11-03 the powers-of-2 frame has its own caption, Table 2, between this paragraph and it: README [NUM].)
    m = re.search(r'<div class="scroll">(?:(?!</div>).)*</div>\s*(?:<!--(?:(?!-->).)*-->\s*)*<p>((?:(?!</p>).)*)</p>\s*'
                  r'<p class="float-caption"><span class="sc">Table 2\.</span>[^\n]*</p>\s*<div class="scroll">', block, re.S)   # its words: d66ad09
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
    # Replicata: each remark sentence of the form Claude: “Order m from examples above, doubled (a = 2·b, ...) or joined
    # (a = b + c, ...); ...”, item by item, against mstar.js's loWhy at a (curly quotes since 2026-10-30, [CUR]).
    # Expectata: every item is the chart's own construction: a = 2·b is ["product", 2, b], a = b + c is ["join", b, c],
    # as their TODOs say ("how the m*(n) chart gets these").  (On 2026-10-12 the example at 560 made the chart's joins
    # 240 + 560, 336 + 560 and 432 + 560 win its ties at 800, 896 and 992, which a remark still called doublings.)
    cols = mstar_data()['cols']
    for s in re.findall(r'Claude: “Order \d+ from examples above, (.*?); order', page()):
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
    # codes that are exactly codes on the page.  (Since 2026-10-31 each name links to its code, \href{#N:M}{...}, which
    # the comparison drops, unlink: q_codes_are_anchors_and_names_link_to_them.)
    li = re.search(r'<p class="entry">\\\(n = 2\^\{18\}\\\): .*?</li>', page(), re.S).group(0)
    assert '\\((p_{320} \\mathbin{\\#} p_{560}) \\vee (p_{48} \\mathbin{\\#} p_{432} \\mathbin{\\#} \\tau_2)\\)' in unlink(li), li
    assert 'certificate_2%5E18.wl"' in li, li
    wl = open(os.path.join(HERE, 'proofs', 'certificate_2^18.wl'), encoding='utf-8').read()   # proofs/: [FAC] 3a
    codes = re.findall(r'(p\d+) = fromHex\["([0-9A-F]+)", \d+\];', wl)
    assert [k for k, _ in codes] == ['p320', 'p560', 'p432', 'p48'], codes
    assert all(re.search(rf'<code id="\d+:\d+">{h}</code>', page()) for _, h in codes), codes


def q_2_17_shows_its_construction():
    # Replicata: the 2^17 remark on index.html, and certificate_2^17.wl beside it.
    # Expectata (as for 2^18, which dreeves asked for on 2026-10-12; 800's example of order 11, 2026-10-17, moved the
    # first power of 2 that beats Thue-Morse by 1 from 2^18 to 2^17): the remark writes out the construction,
    # (p112 # p800) v (p48 # p432 # tau_1), links the script; the script
    # decodes the four blocks from hex codes that are exactly codes on the page.  (Since 2026-10-31 each name links to
    # its code, \href{#N:M}{...}, which the comparison drops, unlink: q_codes_are_anchors_and_names_link_to_them.)
    li = re.search(r'<p class="entry">\\\(n = 2\^\{17\}\\\): .*?</li>', page(), re.S).group(0)
    assert '\\((p_{112} \\mathbin{\\#} p_{800}) \\vee (p_{48} \\mathbin{\\#} p_{432} \\mathbin{\\#} \\tau_1)\\)' in unlink(li), li
    assert 'certificate_2%5E17.wl"' in li, li
    wl = open(os.path.join(HERE, 'proofs', 'certificate_2^17.wl'), encoding='utf-8').read()   # proofs/: [FAC] 3a
    codes = re.findall(r'(p\d+) = fromHex\["([0-9A-F]+)", \d+\];', wl)
    assert [k for k, _ in codes] == ['p112', 'p800', 'p48', 'p432'], codes
    assert all(re.search(rf'<code id="\d+:\d+">{h}</code>', page()) for _, h in codes), codes


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
        m = re.fullmatch(r'(\d+)|\\\(2\^\{?(\d+)\}?\\\)', cell)
        assert m, cell
        return int(m.group(1)) if m.group(1) else 2 ** int(m.group(2))
    forms = ((r'(\d+)', lambda a: (a, a)), (r'(\d+) or (\d+)', lambda a, b: (a, b)), (r'(\d+)–(\d+)', lambda a, b: (a, b)),
             (r'(?:\\\()?\\ge (\d+)(?:\\\))?', lambda a: (a, math.inf)), (r'= (\d+)', lambda a: (a, a)),
             (r'\\in \\\{(\d+)(?:, \d+)*, (\d+)\\\}', lambda a, b: (a, b)), (r'\\in \\\{(\d+), \\ldots, (\d+)\\\}', lambda a, b: (a, b)))
    def value(v):
        hits = [f(*map(int, m.groups())) for p, f in forms for m in [re.fullmatch(p, v)] if m]
        assert len(hits) == 1, v
        assert '\\ldots' in v or not v.startswith('\\in') or [int(t) for t in re.findall(r'\d+', v)] == list(range(hits[0][0], hits[0][1] + 1)), v
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
             r'<p class="entry">\\\(n = ([^:]*?)\\\): &nbsp;\\\(m\^\* (.*?)\\\)</p>')
    for cls, ns, v in re.findall(entry, page()):
        remarks += [(n_of(n if n.isdigit() else f'\\({n}\\)'), *value(v), cls) for n in ns.split(', ')]
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
    value = lambda cell: int(cell) if cell.isdigit() else 2 ** int(re.fullmatch(r'\\\(2\^\{?(\d+)\}?\\\)', cell).group(1))
    titled = {value(n): (cls, who) for cls, who, n in
              re.findall(r"<td(?: class=\"(a|c|ca|j|s)\")? title='([^']*)'>([^<]*)</td>", new)}
    titles = {n: who for n, (cls, who) in titled.items() if cls}      # the rest, unclassed, copy Table 2's powers of 2
    # 240 (since 2026-10-20), the 44 multiples of 16 from 304 to 992 (512 written 2^9) and 32 larger powers of 2,
    # 2^17 to 2^72 (6 until 560 reached order 10 on 2026-10-12, 11 until 800 reached order 11 on 2026-10-17, 18
    # until 592, 608 and 656 reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11 on 2026-10-25, 23
    # until 752 and 784 reached order 10 and 832 order 11 on 2026-10-26, 25 until 912 reached order 12 on 2026-10-28,
    # when 2^29 joined them, 26 until 768 reached order 12 that evening, when 2^39 joined them, 27 until 2026-11-03, when 2^28, 2^36 and 2^47 joined them, 30
    # until later that day, when 2^56 and 2^58 joined them); and since 1024 reached
    # order 11, later that
    # day, 2^10, 2^11 and 2^12; and since 2026-10-27, when the block reached 1024, 1008.  The unclassed cells, Table
    # 2's powers of 2 (2^3 to 2^8) until then, copy every entry of Table 2 that stands: up to 304 but 240 and 304.
    assert len(titles) == 1 + 44 + 35 + 1, len(titles)    # 1 + 44 + 33 + 1 until 2^56 and 2^58 joined them, later on 2026-11-03
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
    css = page_css()
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
        li = re.search(r'<li class="(\w+)">\n      <span class="mk" aria-hidden="true">([^<]*)</span>\n      <p class="entry">\\\(n = '
                       + str(n) + r'\\\): ', text)
        assert li and li.groups() == ('ca', '◆✦'), (n, li and li.groups())


def q_examples_of_2026_10_25_have_entries_and_codes():
    # Replicata: the remarks' entries of 592, 608, 656 (order 10) and 848, 880, 896, 928, 944, 976, 992 (order 11),
    # each code in them decoded by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by
    # (-1)^m symmetry), and mstar.js's columns.
    # Expectata: each n has an entry of its own, "m* = m", in 800's form: its one code block, p_n of order m, whose
    # signs have order exactly m (synthetic division here), symmetric for even m and antisymmetric for odd; and
    # mstar.js's column n is [m, m, ["example", "equipow p" + n], hiWhy].  (Its set SClaude[m][n], those signs' +1
    # positions, left the page on 2026-10-31: quals_codes.q_former_sets_are_halves_of_expansions keeps it.)
    text, cols = page(), mstar_data()['cols']
    def order(a):                                  # (x - 1) divides exactly order(a) times: synthetic division
        c, k = list(a), 0
        while not sum(c): c, k = [sum(c[:i + 1]) for i in range(len(c) - 1)], k + 1
        return k
    for n, m in [(592, 10), (608, 10), (656, 10)] + [(n, 11) for n in (848, 880, 896, 928, 944, 976, 992)]:
        li = re.search(r'<li class="\w+">\n      <span class="mk" aria-hidden="true">[^<]*</span>\n      <p class="entry">\\\(n = '
                       + str(n) + r'\\\): &nbsp;\\\(m\^\* = (\d+)\\\)</p>\n(.*?)\n    </li>', text, re.S)
        assert li and int(li.group(1)) == m, n
        lo, hi, lw, hw = cols[n - 1]
        assert [lo, hi, lw] == [m, m, ['example', f'equipow p{n}']], (n, cols[n - 1])
        codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                           r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(2))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(m)), (n, codes)
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and order(a) == m, (n, len(a), order(a))


def q_752_bound_cites_proof752():
    # Replicata: the remarks' entry of 752, mstar.js's column 752, and the repository's files.
    # Expectata (2026-10-25: proof752.py proves m*(752) <= 10, extending Astra's method for 384 with Claude's meet in
    # the middle): the entry links proof752.py at its GitHub address; mstar.js's column 752 has hi 10 and hiWhy
    # ["page", "Claude and Astra"]; and proof752.py is in the working directory.  Since 2026-10-26, when Claude's
    # search found an example of order 10 at 752, the entry is "m* = 10" and the column is [10, 10, ["example",
    # "equipow p752"], …].
    li = re.search(r'<p class="entry">\\\(n = 752\\\): &nbsp;\\\(m\^\* = 10\\\)</p>\n(.*?)\n    </li>',
                   page(), re.S)
    assert li, 'no entry for 752 alone'
    assert 'href="https://github.com/dreeves/equipow/blob/main/proofs/proof752.py"' in li.group(1), li.group(1)[:600]
    assert mstar_data()['cols'][752 - 1] == [10, 10, ['example', 'equipow p752'], ['page', 'Claude and Astra']]
    assert os.path.isfile(os.path.join(HERE, 'proofs', 'proof752.py'))       # in proofs/ since [FAC] stage 3a


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
    li = re.search(r'<li>\n      <span class="mk" aria-hidden="true"></span>\n      <p class="entry">\\\(n = 288\\\): &nbsp;'
                   r'\\\(m\^\* \\in \\\{9, 10\\\}\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li and 'href="https://github.com/dreeves/equipow/blob/main/proofs/proof288.py"' in li.group(1), li and li.group(1)
    listed = re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)
    assert listed[listed.index('288') - 1:listed.index('288') + 2] == ['240', '288', '304'], listed
    col = mstar_data()['cols'][288 - 1]
    assert col[:2] == [9, 10] and col[3] == ['table2'], col
    assert os.path.isfile(os.path.join(HERE, 'proofs', 'proof288.py'))       # in proofs/ since [FAC] stage 3a


def q_examples_of_2026_10_26_have_entries_and_codes():
    # Replicata: the remarks' entries of 752 and 784 (order 10) and 832 (order 11), each code in them decoded by the
    # paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the order of
    # the remarks' entries, and mstar.js's columns.
    # Expectata (2026-10-26, the second recording pass): each n has an entry of its own, "m* = m", in the form of the
    # first pass's (q_examples_of_2026_10_25_have_entries_and_codes): its one code block, p_n of order m, whose signs
    # have order exactly m (synthetic division here), symmetric for even m and antisymmetric for odd; mstar.js's column
    # n is [m, m, ["example", "equipow p" + n], hiWhy]; no entry lists n with another n; and the entries run in order
    # of n among the examples': 656's, 752's, 784's, 800's, 832's, 848's.  (Its set SClaude[m][n] left the page on
    # 2026-10-31: quals_codes.q_former_sets_are_halves_of_expansions keeps it.)
    text, cols = page(), mstar_data()['cols']
    def order(a):                                  # (x - 1) divides exactly order(a) times: synthetic division
        c, k = list(a), 0
        while not sum(c): c, k = [sum(c[:i + 1]) for i in range(len(c) - 1)], k + 1
        return k
    for n, m in ((752, 10), (784, 10), (832, 11)):
        li = re.search(r'<li class="\w+">\n      <span class="mk" aria-hidden="true">[^<]*</span>\n      <p class="entry">\\\(n = '
                       + str(n) + r'\\\): &nbsp;\\\(m\^\* = (\d+)\\\)</p>\n(.*?)\n    </li>', text, re.S)
        assert li and int(li.group(1)) == m, n
        lo, hi, lw, hw = cols[n - 1]
        assert [lo, hi, lw] == [m, m, ['example', f'equipow p{n}']], (n, cols[n - 1])
        codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                           r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(2))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(m)), (n, codes)
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and order(a) == m, (n, len(a), order(a))
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    assert [ns for ns in listed if {'752', '784', '832'} & set(ns)] == [['752'], ['784'], ['832']], listed
    run = [ns[0] for ns in listed if ns[0] in ('656', '752', '784', '800', '832', '848')]
    assert run == ['656', '752', '784', '800', '832', '848'], run


def q_example_at_1024_has_its_entry_code_and_cell():
    # Replicata: the remarks' entry of 1024, its code decoded by the paper's Table 5 convention (the left half of the
    # signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cells of the powers of 2, and pow2.js's column
    # 2^10.
    # Expectata (2026-10-26: Claude's lattice search found an example of order 11 at 1024; with m*(2^9) = 9 it makes 2^10
    # the first power of 2 to beat Thue-Morse, and the norm bound for 3 caps it at 11): an entry of its own, "m* = 11",
    # an <li class="c"> marked ◆, in the form of the examples' entries (q_examples_of_2026_10_26_have_entries_and_codes),
    # right after 992's, the last of the examples' until 1008's came between them (2026-10-27 night,
    # q_examples_at_720_and_1008_have_their_entries_and_codes); its one code block, p1024 of order 11, whose signs have order
    # exactly 11 (synthetic division here) and are antisymmetric (its set SClaude[11][1024], their +1 positions, left
    # the page on 2026-10-31); the cell 2^10, of class c titled Claude alone, value 11, right after 2^9's; and
    # pow2.js's column 2^10 is [11, 11, ["joins", [[[1024, 11]]]], ["mstar", ["norm", 3]]]: since 2026-10-27, when the
    # m*(n) chart reached 1024, its hi is that chart's column 1024 (before, ["norm", 3] by pow2.py's own norm bound,
    # the same one).
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                   r'1024\\\): &nbsp;\\\(m\^\* = 11\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 1024 alone'
    codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                       r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(1))
    assert len(codes) == 1 and codes[0][:2] == ('1024', '11'), codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + [-s for s in reversed(left)], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 1024 and k == 11 and all(a[1023 - i] == -a[i] for i in range(1024)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    assert listed[listed.index(['992']) + 1:listed.index(['992']) + 3] == [['1008'], ['1024']], listed
    row = re.search(r'<td title=\'The published paper \(2021\)\'>\\\(2\^3\\\)</td>.*?</tr>\s*<tr class="vals">.*?</tr>',
                    text, re.S).group(0)
    ns = re.findall(r'<td([^>]*)>\\\(2\^\{?(\d+)\}?\\\)</td>', row)
    vals = re.findall(r'<td([^>]*)>([^<]*)</td>', row.split('<tr class="vals">')[1])
    i = [k for _, k in ns].index('10')
    assert ns[i - 1][1] == '9' and ns[i][0] == ' class="c" title=\'Claude alone\'' and vals[i] == (' class="c"', '11'), (ns, vals)
    assert pow2_data()['cols'][9] == [11, 11, ['joins', [[[1024, 11]]]], ['mstar', ['norm', 3]]], pow2_data()['cols'][9]


def q_symmetric_example_at_528():
    # Replicata: the remarks' entry of 528 and its code blocks, each decoded by the paper's Table 5 convention (the left
    # half of the signs, 1 = +1, then the rest by (-1)^m symmetry), and synthetic division by x - 1.
    # Expectata (2026-10-27, dreeves: "sure", to putting a symmetric 528 example on the page; four were found that day
    # by a lattice search, scratch/sym528): the entry keeps the join's code p192 and adds p528 (m = 10), which decodes
    # to a symmetric sequence of length 528, exact order 10, +1 at 0; since 2026-10-31 a third code follows them, p528
    # (m = 11) (q_example_at_528_has_its_entry_and_code).  (Its set SClaudeSym[10][528], beside the join's
    # SClaude[10][528], left the page on 2026-10-31: quals_codes.q_former_sets_are_halves_of_expansions keeps both.)
    li = re.search(r'<p class="entry">\\\(n = 528\\\): .*?</li>', page(), re.S)
    assert li, 'no entry of 528'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="\d+:\d+">([0-9A-F]+)</code>',
                       li.group(0))
    assert [c[:2] for c in codes] == [('192', '9'), ('528', '10'), ('528', '11')], codes
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
    # "m* = 13", right before 2^17's (its wording unpinned since 2026-10-30); and the
    # changelog states m*(2^11) = 12 and m*(2^12) = 13 on 2026-10-26, together on a line of their own.
    cols, text = pow2_data()['cols'], page()
    assert cols[10] == [12, 12, ['joins', [[[1024, 11], [2, 1]]]], ['residue', [3]]], cols[10]
    assert cols[11] == [13, 13, ['joins', [[[1024, 11], [4, 2]]]], ['residue', [3]]], cols[11]
    row = re.search(r'<td title=\'The published paper \(2021\)\'>\\\(2\^3\\\)</td>.*?</tr>\s*<tr class="vals">.*?</tr>',
                    text, re.S).group(0)
    ns = re.findall(r'<td([^>]*)>\\\(2\^\{?(\d+)\}?\\\)</td>', row)
    vals = re.findall(r'<td([^>]*)>([^<]*)</td>', row.split('<tr class="vals">')[1])
    i = [k for _, k in ns].index('10')
    assert [k for _, k in ns[i:i + 4]] == ['10', '11', '12', '17'], ns
    assert all(a == ' class="c" title=\'Claude alone\'' for a, _ in ns[i + 1:i + 3]), ns
    assert vals[i + 1:i + 3] == [(' class="c"', '12'), (' class="c"', '13')], vals
    listed = re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)
    j = listed.index('2^{11}')
    assert listed[j:j + 3] == ['2^{11}', '2^{12}', '2^{17}'], listed
    for k, m in ((11, 12), (12, 13)):
        li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                       rf'2\^\{{{k}\}}\\\): &nbsp;\\\(m\^\* = {m}\\\)</p>\n(.*?)\n    </li>', text, re.S)
        assert li, k
    entries = [(d, statements(rest)) for d, rest in changelog()]
    assert ('2026-10-26', {2 ** 11: (12, 12), 2 ** 12: (13, 13)}) in entries, entries[:4]


def q_example_at_816_has_its_entry_and_code():
    # Replicata: the remarks' entries of 720 and 816, 816's code decoded by the paper's Table 5 convention (the left
    # half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cells, and mstar.js's columns 720
    # and 816.
    # Expectata (2026-10-26: Claude's lattice search found an antisymmetric example of order 11 at 816, which the
    # norm bound for the residue sums mod 5 leaves at 11 to 14; 2026-10-28: w12.py found a symmetric example of order
    # 12 there, which replaced it and its code; 2026-11-03: a pin tree rules order 13 out): 816 has an entry of its own, "m* = 12" ("m* ∈ {12, 13, 14}" until 2026-11-03), an
    # <li class="c"> marked ◆, right after 800's and before 832's (its wording unpinned since 2026-10-30); its
    # one code block, p816 of order 12, whose signs have order exactly 12 (synthetic division here) and are
    # symmetric (its set SClaude[12][816] left the page on 2026-10-31); 720's entry alone
    # (it shared one with 816 before; its own example since 2026-10-27,
    # q_examples_at_720_and_1008_have_their_entries_and_codes); the cell 816 of value 12 (12–14 until 2026-11-03); and mstar.js's
    # column 816 is [12, 12, ["example", "equipow p816"], ["page", "Claude alone"]] ([12, 14, ["example", "equipow p816"], ["norm", 5]] until 2026-11-03).
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                   r'816\\\): &nbsp;\\\(m\^\* = 12\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 816 alone'
    codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                       r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(1))
    assert len(codes) == 1 and codes[0][:2] == ('816', '12'), codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + list(reversed(left)), 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 816 and k == 12 and all(a[815 - i] == a[i] for i in range(816)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['816'])
    assert listed[i - 1:i + 2] == [['800'], ['816'], ['832']] and ['720'] in listed, listed
    assert new_cells(text)[816] == (12, 12), new_cells(text)[816]
    assert mstar_data()['cols'][816 - 1] == [12, 12, ['example', 'equipow p816'], ['page', 'Claude alone']], mstar_data()['cols'][816 - 1]


def q_examples_at_720_and_1008_have_their_entries_and_codes():
    # Replicata: the remarks' entries of 720 and 1008, their codes decoded by the paper's Table 5 convention (the left
    # half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cells, and mstar.js's columns 720
    # and 1008.
    # Expectata (2026-10-27: Claude's lattice search, w11.py at 720 and at 1008, found antisymmetric examples of order
    # 11 there; 2026-10-28: w12.py found a symmetric example of order 12 at 1008, which replaced its order-11 example
    # and code, and that evening Astra's faster w12 found one at 720, which did the same): each has an entry of its
    # own, an <li class="c"> marked ◆ among the examples in order of n, 720's "m* ∈ {13, 14}" ("m* ∈ {12, 13, 14}" until 2026-11-03) between 688's (656's
    # until 2026-11-01, when 672's and then 688's example entries came between them) and 752's, and 1008's "m* = 13" ("m* ∈ {12, 13}" until 2026-11-03) between 992's and 1024's (its wording unpinned since 2026-10-30); each a code block of its
    # order m (11 at 720, 12 at 1008), whose signs have order exactly m (synthetic division here) and are
    # antisymmetric at 720 and symmetric at 1008 (their sets SClaude[m][n] left the page on 2026-10-31), each followed by that of order 13
    # (since 2026-11-03: q_results_of_2026_11_03_have_entries_and_codes at 1008, and at 720 q_example_at_720_has_its_code_of_order_13,
    # the beam campaign's; 720's was its only one until then); no other
    # entry names 720 or 1008 (their joins' entries are gone); the cells 13–14 and 13 (12–14 and 12–13 until 2026-11-03);
    # and mstar.js's columns [13, 14, ["example", "equipow p720"], ["residue", 16]] and [13, 13, ["example",
    # "equipow p1008"], ["residue", 5]].
    text = page()
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    for n, m, values, before, after, cell, more in ((720, 12, '\\\\in \\\\\\{13, 14\\\\\\}', '688', '752', (13, 14), ('13',)),
                                                    (1008, 12, '= 13', '992', '1024', (13, 13), ('13',))):
        li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                       rf'{n}\\\): &nbsp;\\\(m\^\* {values}\\\)</p>\n(.*?)\n    </li>', text, re.S)
        assert li, f'no entry of {n} alone'
        codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                           r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(1))
        assert [c[:2] for c in codes] == [(str(n), o) for o in (str(m),) + more], codes
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a, k = left + [(-1) ** m * s for s in reversed(left)], 0
        c = a
        while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
        assert len(a) == n and k == m and all(a[n - 1 - i] == (-1) ** m * a[i] for i in range(n)), (n, len(a), k)
        i = listed.index([str(n)])
        assert listed[i - 1:i + 2] == [[before], [str(n)], [after]], listed[i - 1:i + 2]
        assert sum(str(n) in ns for ns in listed) == 1, (n, [ns for ns in listed if str(n) in ns])
        assert new_cells(text)[n] == cell, new_cells(text)[n]
    cols = mstar_data()['cols']
    assert cols[720 - 1] == [13, 14, ['example', 'equipow p720'], ['residue', 16]], cols[720 - 1]
    assert cols[1008 - 1] == [13, 13, ['example', 'equipow p1008'], ['residue', 5]], cols[1008 - 1]


def q_example_at_912_has_its_entry_and_code():
    # Replicata: the remarks' entries naming 912, its code decoded by the paper's Table 5 convention (the left half of
    # the signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cell, and mstar.js's column 912.
    # Expectata (2026-10-28: Claude's lattice search w12.py found a symmetric example of order 12 at 912): an entry of
    # its own, an <li class="c"> marked ◆, "m* = 13" ("m* ∈ {12, 13}" until 2026-11-03), between 896's and 928's (its wording unpinned since 2026-10-30); a code block, p912 of order 12, whose signs have order exactly 12 (synthetic
    # division here) and are symmetric (its set SClaude[12][912] left the page on 2026-10-31), followed since 2026-11-03 by that of order 13
    # (q_results_of_2026_11_03_have_entries_and_codes); the built entry of
    # 672 and 768 no longer names 912; the cell 13 (12–13 until 2026-11-03); mstar.js's column [13, 13, ["example", "equipow p912"],
    # ["residue", 5]].
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                   r'912\\\): &nbsp;\\\(m\^\* = 13\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 912 alone'
    codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                       r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(1))
    assert [c[:2] for c in codes] == [('912', '12'), ('912', '13')], codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + list(reversed(left)), 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 912 and k == 12 and all(a[911 - i] == a[i] for i in range(912)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['912'])
    assert listed[i - 1:i + 2] == [['896'], ['912'], ['928']], listed[i - 1:i + 2]
    assert sum('912' in ns for ns in listed) == 1 and ['672'] in listed, [ns for ns in listed if '672' in ns]   # 672 and 768 until 768's example
    assert new_cells(text)[912] == (13, 13), new_cells(text)[912]
    assert mstar_data()['cols'][912 - 1] == [13, 13, ['example', 'equipow p912'], ['residue', 5]], mstar_data()['cols'][912 - 1]


def q_example_at_768_has_its_entry_and_code():
    # Replicata: the remarks' entries naming 768, its code decoded by the paper's Table 5 convention (the left half of
    # the signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cell, and mstar.js's column 768.
    # Expectata (2026-10-28 evening: Claude's lattice search w12.py found symmetric examples of order 12 at 768): an
    # entry of its own, an <li class="c"> marked ◆, "m* ∈ {12, 13}", between 752's and 784's (its wording unpinned since 2026-10-30); its one code block, p768 of order 12, whose signs have order exactly 12 (synthetic
    # division here) and are symmetric (its set SClaude[12][768] left the page on 2026-10-31); the built entry it
    # shared with 672 now names 672 alone; the cell 12–13; mstar.js's column [12, 13, ["example", "equipow p768"],
    # ["residue", 5]].
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                   r'768\\\): &nbsp;\\\(m\^\* = 13\\\)</p>\n(.*?)\n    </li>', text, re.S)   # "m* ∈ {12, 13}" until 2026-11-03
    assert li, 'no entry of 768 alone'
    codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                       r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(1))
    # Since 2026-11-03 the entry also has the beam campaign's code of order 13 after it (q_example_at_768_has_its_code_of_order_13).
    assert [c[:2] for c in codes] == [('768', '12'), ('768', '13')], codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + list(reversed(left)), 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 768 and k == 12 and all(a[767 - i] == a[i] for i in range(768)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['768'])
    assert listed[i - 1:i + 2] == [['752'], ['768'], ['784']], listed[i - 1:i + 2]
    assert sum('768' in ns for ns in listed) == 1 and ['672'] in listed, [ns for ns in listed if '672' in ns or '768' in ns]
    assert new_cells(text)[768] == (13, 13), new_cells(text)[768]                                   # 12–13 until 2026-11-03
    assert mstar_data()['cols'][768 - 1] == [13, 13, ['example', 'equipow p768'], ['residue', 5]], mstar_data()['cols'][768 - 1]


def q_examples_at_576_and_624_have_their_entries_and_codes():
    # Replicata: the remarks' entries naming 576 and 624, their codes decoded by the paper's Table 5 convention (the left
    # half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cells, the changelog's statements
    # of 2026-10-31, and mstar.js's columns.
    # Expectata (2026-10-31: Claude's lattice search scratch/w11-624-576/w11.py found antisymmetric examples of order
    # 11 at 576 and 624): each n has an entry of its own, an <li class="c"> marked ◆, "m* = 12" ("m* ∈ {11, 12}" until 2026-11-03), among the
    # examples in order of n (576 between 560 and 592, 624 between 608 and 656; its wording unpinned); a code block, p_n of order 11, whose
    # signs have order exactly 11 (synthetic division here) and are antisymmetric (its set SClaude[11][n] left the page
    # on 2026-10-31), followed since 2026-11-03 by that of order 12 (q_results_of_2026_11_03_have_entries_and_codes); no other entry names n (its old entry is gone); the cell 12 (11–12 until 2026-11-03); the changelog states
    # 11 ≤ m*(n) ≤ 12 on 2026-10-31; and mstar.js's column [12, 12, ["example", "equipow p<n>"], ["residue", M]], M the
    # modulus of n's residue condition at order 13.
    # Resultata before: 576 was 10 to 12, its lo the join 240 + 336, 624 was 10 to 12, its lo the join 240 + 384; no example of order 11 at 576 and 624.
    text = page()
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    said = changelog_by_day().get('2026-10-31', {})
    for n, before, after, M in ((576, 560, 592, 5), (624, 608, 656, 25)):
        li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = '
                       + str(n) + r'\\\): &nbsp;\\\(m\^\* = 12\\\)</p>\n(.*?)\n    </li>', text, re.S)
        assert li, f'no entry of {n} alone'
        codes = re.findall(r'<p class="code">\n        <span>\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n'
                           r'        <code id="\d+:\d+">([0-9A-F]+)</code>\n      </p>', li.group(1))
        assert [c[:2] for c in codes] == [(str(n), '11'), (str(n), '12')], codes
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a, k = left + [-s for s in reversed(left)], 0
        c = a
        while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
        assert len(a) == n and k == 11 and all(a[n - 1 - i] == -a[i] for i in range(n)), (n, len(a), k)
        i = listed.index([str(n)])
        assert listed[i - 1:i + 2] == [[str(before)], [str(n)], [str(after)]], listed[i - 1:i + 2]
        assert sum(str(n) in ns for ns in listed) == 1, (n, [ns for ns in listed if str(n) in ns])
        assert new_cells(text)[n] == (12, 12), new_cells(text)[n]
        assert said.get(n) == (11, 12), (n, said.get(n))
        assert mstar_data()['cols'][n - 1] == [12, 12, ['example', f'equipow p{n}'], ['residue', M]], mstar_data()['cols'][n - 1]


def q_example_at_528_has_its_entry_and_code():
    # Replicata: the remarks' entry of 528, its code blocks decoded by the paper's Table 5 convention (the left half
    # of the signs, 1 = +1, then the rest by (-1)^m symmetry), the new results' cell of 528, the changelog's statements
    # of 2026-10-31, and mstar.js's column.
    # Expectata (2026-10-31: Claude's lattice search scratch/w11-624-576/w11.py found antisymmetric examples of order
    # 11 at 528): the entry, an <li class="c"> marked ◆ (Claude alone: both bounds are Claude's now), says
    # "m* ∈ {11, 12}"; its last code is p528 (m = 11), whose signs have order exactly 11 (synthetic division here),
    # are antisymmetric and have +1 at 0 (its set SClaude[11][528], the page's last, left the page later that day);
    # no other entry names 528; the cell is 11–12; the changelog states m*(528) ≥ 11 on 2026-10-31 (only its low
    # moved: 2026-10-04 said ≥ 10 and 2026-10-11 ≤ 12); and mstar.js's column is [11, 12, ["example",
    # "equipow p528"], ["residue", 5]].
    # Resultata before: 528 was 10 to 12, Claude and BGPW, with no example of order 11.
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = 528'
                   r'\\\): &nbsp;\\\(m\^\* \\in \\\{11, 12\\\}\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 528 alone, class c, m* in {11, 12}'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="\d+:\d+">([0-9A-F]+)</code>', li.group(1))
    assert codes and codes[-1][:2] == ('528', '11'), codes
    h = codes[-1][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + [-s for s in reversed(left)], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 528 and k == 11 and all(a[527 - i] == -a[i] for i in range(528)) and a[0] == 1, (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    assert sum('528' in ns for ns in listed) == 1, [ns for ns in listed if '528' in ns]
    assert new_cells(text)[528] == (11, 12), new_cells(text)[528]
    assert changelog_by_day().get('2026-10-31', {}).get(528) == (11, None), changelog_by_day().get('2026-10-31')
    assert mstar_data()['cols'][527] == [11, 12, ['example', 'equipow p528'], ['residue', 5]], mstar_data()['cols'][527]


def q_example_at_672_has_its_entry_and_code():
    # Replicata: the remarks' entry naming 672, its code decoded by the paper's Table 5 convention, the new results'
    # cell of 672, the changelog's statements of 2026-11-01, and mstar.js's column.
    # Expectata (2026-11-01: Claude's lattice search scratch/w11-624-576/w12/w12.py found a symmetric example of order
    # 12 at 672): 672 has an entry of its own, an <li class="c"> marked ◆, "m* ∈ {12, 13}", between 656's and 688's
    # (720's until 688's example entry came between them, also on 2026-11-01);
    # its one code, p672 (m = 12), has signs of order exactly 12 (synthetic division here), symmetric, +1 at 0;
    # its code is <code id="672:12"> (the page's sets left it on 2026-10-31); no other entry names 672; the cell is
    # 12–13; the changelog states 12 ≤ m*(672) ≤ 13 on 2026-11-01; mstar.js's column is [12, 13, ["example",
    # "equipow p672"], ["residue", 5]].
    # Resultata before: 672 was 11 to 13 (built: 2 * 336), with no example of order 12.
    # Since 2026-11-04 m* = 13, the cell 13 and the column [13, 13, ...]: q_example_at_672_has_its_code_of_order_13.  Its code of order 12 stays.
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = 672'
                   r'\\\): &nbsp;\\\(m\^\* = 13\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 672 alone, m* = 13'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="672:12">([0-9A-F]+)</code>', li.group(1))
    assert len(codes) == 1 and codes[0][:2] == ('672', '12'), codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + left[::-1], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 672 and k == 12 and a == a[::-1] and a[0] == 1, (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['672'])
    assert listed[i - 1:i + 2] == [['656'], ['672'], ['688']], listed[i - 1:i + 2]
    assert sum('672' in ns for ns in listed) == 1, [ns for ns in listed if '672' in ns]
    assert new_cells(text)[672] == (13, 13), new_cells(text)[672]
    assert changelog_by_day().get('2026-11-01', {}).get(672) == (12, 13), changelog_by_day().get('2026-11-01')
    assert mstar_data()['cols'][671] == [13, 13, ['example', 'equipow p672'], ['residue', 5]], mstar_data()['cols'][671]


def q_example_at_688_has_its_entry_and_code():
    # Replicata: the remarks' entries naming 688 and 544, 688's code decoded by the paper's Table 5 convention, the new
    # results' cells of 688 and 544, the changelog's statements of 2026-11-01, and mstar.js's column.
    # Expectata (2026-11-01: Claude's lattice search scratch/w11-624-576/w10s/w10s.py found a symmetric example of order
    # 10 at 688): 688 has an entry of its own, an <li class="c"> marked ◆, "m* = 10", between 672's and 720's; its one
    # code, p688 (m = 10), has signs of order exactly 10 (synthetic division here), symmetric, +1 at 0; its code is
    # <code id="688:10">; the entry it shared with 544 names 544 alone; no other entry names 688; the cells are 10 and,
    # at 544, 9–10; the changelog states m*(688) = 10 on 2026-11-01; mstar.js's column is [10, 10, ["example",
    # "equipow p688"], ["residue", 3]].
    # Resultata before: 688 was 9 to 10 (built: the join 192 + 496), in one entry with 544.
    text = page()
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = 688'
                   r'\\\): &nbsp;\\\(m\^\* = 10\\\)</p>\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 688 alone, m* = 10'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="688:10">([0-9A-F]+)</code>', li.group(1))
    assert len(codes) == 1 and codes[0][:2] == ('688', '10'), codes
    h = codes[0][2]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a, k = left + left[::-1], 0
    c = a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 688 and k == 10 and a == a[::-1] and a[0] == 1, (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['688'])
    assert listed[i - 1:i + 2] == [['672'], ['688'], ['720']], listed[i - 1:i + 2]
    assert sum('688' in ns for ns in listed) == 1, [ns for ns in listed if '688' in ns]
    assert ['544'] in listed, [ns for ns in listed if '544' in ns]
    assert (new_cells(text)[688], new_cells(text)[544]) == ((10, 10), (10, 10)), (new_cells(text)[688], new_cells(text)[544])   # 544 9 to 10 until 2026-11-03
    assert changelog_by_day().get('2026-11-01', {}).get(688) == (10, 10), changelog_by_day().get('2026-11-01')
    assert mstar_data()['cols'][687] == [10, 10, ['example', 'equipow p688'], ['residue', 3]], mstar_data()['cols'][687]


def q_results_of_2026_11_03_have_entries_and_codes():
    # Replicata: the remarks' entries of 2026-11-03's examples, their codes decoded by the paper's Table 5 convention, the new results' cells, the changelog's
    # statements of that day, and mstar.js's columns.
    # Expectata: each n has one entry, an <li class="c"> marked ◆, "m* = M", among the examples in order of n; one code p_n (m = M), <code id="n:M">, has signs of
    # order exactly M (synthetic division here), (-1)^M-symmetric, +1 at 0; no other entry names n; the cell is M; the changelog states m*(n) = M on 2026-11-03.
    # And 960's entry says that it settles a(14) = 960 of A323395: no length below 960 allows order 15 (hi < 15 in mstar.js).  The codes of order M - 1 at 576, 624, 912 and
    # 1008 stay, before the new ones, as 528 keeps its code of order 10 (q_former_sets_are_halves_of_expansions: dreeves, "being careful not to lose anything").
    # Resultata before: 544's and 960's entries gave only joins or doubling, and 576's, 624's, 912's and 1008's codes had order one less.
    text = page()
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    for n, M, before, after in ((544, 10, '528', '560'), (576, 12, '560', '592'), (624, 12, '608', '656'), (912, 13, '896', '928'),
                                (960, 15, '944', '976'), (1008, 13, '992', '1024')):
        li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = %d\\\): &nbsp;\\\(m\^\* = %d\\\)</p>\n(.*?)\n    </li>' % (n, M), text, re.S)
        assert li, f'no entry of {n} alone, m* = {M}'
        codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="%d:%d">([0-9A-F]+)</code>' % (n, M), li.group(1))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(M)), codes
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** M * t for t in reversed(left)]
        k, c = 0, a
        while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
        assert len(a) == n and k == M and a[0] == 1, (n, len(a), k)
        i = listed.index([str(n)])
        assert listed[i - 1:i + 2] == [[before], [str(n)], [after]], listed[i - 1:i + 2]
        assert sum(str(n) in ns for ns in listed) == 1, [ns for ns in listed if str(n) in ns]
        assert new_cells(text)[n] == (M, M), new_cells(text)[n]
        assert changelog_by_day().get('2026-11-03', {}).get(n) == (M, M), changelog_by_day().get('2026-11-03')
        assert mstar_data()['cols'][n - 1][:3] == [M, M, ['example', f'equipow p{n}']], mstar_data()['cols'][n - 1]
    cols = mstar_data()['cols']
    assert next(n for n, c in enumerate(cols, 1) if c[1] >= 15) == 960 and cols[959][0] == 15
    li = re.search(r'<p class="entry">\\\(n = 960\\\): .*?</li>', text, re.S).group(0)
    assert 'a(14) = 960' in li and 'A323395' in li, li


def first_entry(cols, text, k, lo, hi):
    """Asserts what q_firsts_of_2026_11_03 asks of each new first 2^k (and q_firsts_move_to_2_56_and_2_58, which shares
    it since later that day): pow2.js's [lo, hi] at 2^k, its column before at lo - 2, its cell, and its entry writing out
    its join, as pow2.js has it (each product's blocks in order, a run of one length as a power, tau_j as 2 or 2^j), with
    its products' orders, the least of them lo."""
    assert cols[k - 1][:2] == [lo, hi] and cols[k - 2][0] == lo - 2, cols[k - 2:k]
    assert new_cells(text)[2 ** k] == (lo, hi), new_cells(text).get(2 ** k)
    li = re.search(r'<p class="entry">\\\(n = 2\^\{%d\}\\\): .*?</li>' % k, text, re.S).group(0)
    products = cols[k - 1][2][1]
    def factors(p):
        runs = [(n, len(list(g))) for n, g in itertools.groupby(n for n, m in p)]
        power = {2 ** m: m for n, m in p if n == 2 ** m}
        return '\\cdot '.join(('2' if power[n] == 1 else f'2^{power[n]}') if n in power else f'{n}' if c == 1 else f'{n}^{c}' for n, c in runs)
    assert f'\\(2^{{{k}}} = ' + ' + '.join(factors(p) for p in products) + '\\)' in li, li
    orders = [sum(m for n, m in p) for p in products]
    assert min(orders) == lo and f'of orders {", ".join(map(str, orders[:-1]))} and {orders[-1]}.' in li, (orders, li)


def names_base(text, k, base, t, order):
    """Asserts that 2^k's entry names the 2^base entry, each product times tau_t, and order."""
    li = re.search(r'<p class="entry">\\\(n = 2\^\{%d\}\\\): .*?</li>' % k, text, re.S).group(0)
    assert f'\\(2^{{{base}}}\\) entry' in li and f'\\tau_{t}\\)' in li and f'order {order}' in li, li


def q_firsts_of_2026_11_03():
    # Replicata: pow2.js's columns, the new results' cells of the powers of 2, the remarks' entries, and the theorem's statement and its list of firsts.
    # Expectata (coins, searches/pinned/, with the blocks of 2026-11-03): excess 3 first at 2^28, excess 4 at 2^36 and excess 6 at 2^47, each a join whose products have
    # order at least k + e, one of order exactly k + e: lo is 31 at 2^28, 40 at 2^36 and 53 at 2^47, one more than each column before it had; the cells read 2^28 31–34, 2^36 40–44
    # and 2^47 53–58, 2^29 32–35, 2^37 41–45 and 2^48 54–59 as before; each new entry writes its join out, as pow2.js has it, with its products' orders; the entries that named the
    # bases at 2^29, 2^37 and 2^48 name the new ones; the theorem states m*(2^28) >= 31, m*(2^36) >= 40 and m*(2^47) >= 53 in place of 2^29's, 2^37's and 2^48's, and
    # its list of firsts is 10, 20, 28, 36, 39, 47, 57, 65, 68.  (Since later on 2026-11-03, q_firsts_move_to_2_56_and_2_58, the list ends 56, 58, 68; what stands
    # of it here: its first six, 10, 20, 28, 36, 39, 47.)
    # Resultata before: the firsts were 10, 20, 29, 37, 39, 48, 57, 65, 68.
    cols, text = pow2_data()['cols'], page()
    for k, lo, hi in ((28, 31, 34), (36, 40, 44), (47, 53, 58)): first_entry(cols, text, k, lo, hi)
    cells = new_cells(text)
    assert [cells[2 ** k] for k in (29, 37, 48)] == [(32, 35), (41, 45), (54, 59)]
    theorem = the_theorem(text)
    for k, lo in ((28, 31), (36, 40), (47, 53)): assert f'(2^{{{k}}}) \\ge {lo}' in theorem, theorem
    for k in (29, 37, 48): assert f'(2^{{{k}}})' not in theorem, theorem
    assert ' are 10, 20, 28, 36, 39, 47, ' in text      # ' are 10, 20, 28, 36, 39, 47, 57, 65, 68.</p>' until later on 2026-11-03
    for k, base, t, order in ((29, 28, 1, 32), (30, 28, 2, 33), (33, 28, 5, 36), (34, 28, 6, 37), (37, 36, 1, 41), (38, 36, 2, 42), (48, 47, 1, 54), (49, 47, 2, 55), (52, 47, 5, 58)):
        names_base(text, k, base, t, order)


def q_firsts_move_to_2_56_and_2_58():
    # Replicata: pow2.js's columns, the new results' cells of the powers of 2, the remarks' entries, and the theorem's statement and its list of firsts.
    # Expectata (later on 2026-11-03: scratch/w11-624-576/firsts_now.py, the exhaustive search of scratch/wish5 over the blocks of that day, rerun with 1008 at its order
    # 13 in scratch/firsts-56-58/): excess 7 first at 2^56 and excess 8 at 2^58, each a join whose products have order at least k + e, one of order exactly k + e: lo is 63
    # at 2^56 and 66 at 2^58, one more than each column before it had (BASES[47] lifted gave 62 at 2^56, BASES[57] lifted 65 at 2^58); the cells read 2^56 63–69
    # and 2^58 66–71, 2^57 64–70 and 2^65 73–81 as before, and 2^61 69–75, its low one more than before; each new entry writes its join out, as pow2.js has it,
    # with its products' orders; the entries that named the bases at 2^57 and 2^65, and 2^65's at 2^66 and 2^67, name the new ones, each product times τ1 at 2^57
    # and τ3, τ7, τ8 and τ9 at 2^61, 2^65, 2^66 and 2^67; the theorem states m*(2^56) >= 63 and m*(2^58) >= 66 in place of 2^57's and 2^65's, and its list of
    # firsts is 10, 20, 28, 36, 39, 47, 56, 58, 68.  And as searches/pinned/README.md says, its coins had left 2^56 (excess 7) and 2^58, 2^60 and 2^62 (excess 8)
    # undecided at its time limit: the new entries say so, each linking searches/pinned and naming those powers (main session, 2026-11-03: "Say so on the page in
    # the same way the README does"; their wording unpinned).
    # Resultata before: the firsts were 10, 20, 28, 36, 39, 47, 57, 65, 68, and the cell of 2^61 read 68–75.
    cols, text = pow2_data()['cols'], page()
    for k, lo, hi in ((56, 63, 69), (58, 66, 71)): first_entry(cols, text, k, lo, hi)
    for k, ks in ((56, (56,)), (58, (58, 60, 62))):
        li = re.search(r'<p class="entry">\\\(n = 2\^\{%d\}\\\): .*?</li>' % k, text, re.S).group(0)
        assert 'href="https://github.com/dreeves/equipow/tree/main/searches/pinned"' in li and all(f'\\(2^{{{j}}}\\)' in li for j in ks), li
    cells = new_cells(text)
    assert [cells[2 ** k] for k in (57, 61, 65)] == [(64, 70), (69, 75), (73, 81)], [cells.get(2 ** k) for k in (57, 61, 65)]
    theorem = the_theorem(text)
    for k, lo in ((56, 63), (58, 66)): assert f'(2^{{{k}}}) \\ge {lo}' in theorem, theorem
    for k in (57, 65): assert f'(2^{{{k}}})' not in theorem, theorem
    assert ' are 10, 20, 28, 36, 39, 47, 56, 58, 68.</p>' in text
    for k, base, t, order in ((57, 56, 1, 64), (61, 58, 3, 69), (65, 58, 7, 73), (66, 58, 8, 74), (67, 58, 9, 75)):
        names_base(text, k, base, t, order)


def q_example_at_720_has_its_code_of_order_13():
    # Replicata: the remarks' entry naming 720, its codes decoded by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the
    # rest by (-1)^m symmetry), the new results' cell of 720, the changelog's statements of 2026-11-03, and mstar.js's column.
    # Expectata (2026-11-03: the beam campaign's lattice search, scratch/beam-campaign-20261103/, found an antisymmetric example of order 13 at 720):
    # 720's entry, an <li class="c"> marked ◆, its statement of m* \(m^* \in \{13, 14\}\), between 688's and 752's; its codes p720 (m = 12) and
    # p720 (m = 13), in that order, the second <code id="720:13">, its signs of order exactly 13 (synthetic division here), antisymmetric, +1 at
    # 0; no other entry names 720; the cell 13 to 14; the changelog's statement of 720 on 2026-11-03 is (13, None) (quals_index's statement()); mstar.js's column
    # [13, 14, ["example", "equipow p720"], ['residue', 16]].
    # Resultata before: 720 was 12 to 14, with one code, of order 12.
    text = page()
    entry = '<p class="entry">\\(n = 720\\): &nbsp;\\(m^* \\in \\{13, 14\\}\\)</p>'
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      ' + re.escape(entry) + r'\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 720 alone with its new statement'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="(\d+:\d+)">([0-9A-F]+)</code>', li.group(1))
    assert [c[:3] for c in codes] == [('720', '12', '720:12'), ('720', '13', '720:13')], codes
    h = codes[1][3]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a = left + [-t for t in reversed(left)]
    k, c = 0, a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 720 and k == 13 and a[0] == 1 and all(a[720 - 1 - i] == -a[i] for i in range(720)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['720'])
    assert listed[i - 1:i + 2] == [['688'], ['720'], ['752']], listed[i - 1:i + 2]
    assert sum('720' in ns for ns in listed) == 1, [ns for ns in listed if '720' in ns]
    assert new_cells(text)[720] == (13, 14), new_cells(text)[720]
    assert changelog_by_day().get('2026-11-03', {}).get(720) == (13, None), changelog_by_day().get('2026-11-03')
    assert mstar_data()['cols'][720 - 1] == [13, 14, ['example', 'equipow p720'], ['residue', 16]], mstar_data()['cols'][720 - 1]


def q_pin_trees_are_on_the_page():
    # Replicata: the remarks' entries of 432 and 816, the new results' cells, the changelog's statements of 2026-11-03, the section of the pin trees, the OEIS note on A323395, the table of smallest lengths, and mstar.js.
    # Expectata (the user, 2026-11-03: "let's add them to the github, including an explanation of how the new stuff works"): 432's entry says m* = 11 and 816's m* = 12, each with its code still there and a Claude paragraph linking its proof file; the cells read 11 and 12;
    # the changelog states m*(432) = 11 and m*(816) = 12 on that day; a section explains the method (a <section class="pintree"> with its h2 and a Claude block quote), states each proof's certificates, and links both checkers, both proofs and searches/pintree;
    # A323395's note says this page proves a(11) = 480; the table's row for order 12 is 480, 480, proven.
    # Resultata before: 432 was 11 to 12 and 816 was 12 to 14; A323395's note said a(11) is 432 or 480.
    text = page()
    GH = 'https://github.com/dreeves/equipow/blob/main/'
    for n, M, proof in ((432, 11, 'pintree_432_12.json.gz'), (816, 12, 'pintree_816_13.json.gz')):
        li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry">\\\(n = %d\\\): &nbsp;\\\(m\^\* = %d\\\)</p>\n(.*?)\n    </li>' % (n, M), text, re.S)
        assert li, f'no entry of {n} alone, m* = {M}'
        assert f'<code id="{n}:{M}">' in li.group(1), n
        assert f'{GH}proofs/{proof}' in li.group(1) and 'Claude: “' in li.group(1), li.group(1)[:400]
        assert new_cells(text)[n] == (M, M), new_cells(text)[n]
        assert changelog_by_day().get('2026-11-03', {}).get(n) == (M, M), changelog_by_day().get('2026-11-03')
    sec = re.search(r'<section class="pintree" aria-labelledby="pintree-title">(.*?)</section>', text, re.S)
    assert sec, 'no section of the pin trees'
    body = sec.group(1)
    assert '<blockquote class="claude">' in body and '<h2 id="pintree-title">' in body, body[:300]
    for link in ('proofs/pintree.py', 'proofs/pintree_second.py', 'proofs/pintree_432_12.json.gz', 'proofs/pintree_816_13.json.gz'): assert f'{GH}{link}' in body, link
    assert 'https://github.com/dreeves/equipow/tree/main/searches/pintree' in body
    assert '3,119' in body and '187,269' in body, body[:300]
    oeis = re.search(r'<section class="oeis" aria-labelledby="oeis-title">.*?</section>', text, re.S).group(0)
    note = dict(zip(OEIS, re.findall(r'<li>(.*?)</li>', re.search(r'<ul>(.*?)</ul>', oeis, re.S).group(1), re.S)))['A323395']
    assert 'a(11) = 480' in note and 'is 432 or 480' not in note, note
    assert smallest_table()[11] == ['12', '480', '480', '✓'], smallest_table()[11]


def q_example_at_768_has_its_code_of_order_13():
    # Replicata: the remarks' entry naming 768, its codes decoded by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the
    # rest by (-1)^m symmetry), the new results' cell of 768, the changelog's statements of 2026-11-03, and mstar.js's column.
    # Expectata (2026-11-03: the beam campaign's lattice search, scratch/beam-campaign-20261103/, found an antisymmetric example of order 13 at 768):
    # 768's entry, an <li class="c"> marked ◆, its statement of m* \(m^* = 13\), between 752's and 784's; its codes p768 (m = 12) and
    # p768 (m = 13), in that order, the second <code id="768:13">, its signs of order exactly 13 (synthetic division here), antisymmetric, +1 at
    # 0; no other entry names 768; the cell 13 to 13; the changelog's statement of 768 on 2026-11-03 is (13, 13) (quals_index's statement()); mstar.js's column
    # [13, 13, ["example", "equipow p768"], ['residue', 5]].
    # Resultata before: 768 was 12 to 13, with one code, of order 12.
    text = page()
    entry = '<p class="entry">\\(n = 768\\): &nbsp;\\(m^* = 13\\)</p>'
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      ' + re.escape(entry) + r'\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 768 alone with its new statement'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="(\d+:\d+)">([0-9A-F]+)</code>', li.group(1))
    assert [c[:3] for c in codes] == [('768', '12', '768:12'), ('768', '13', '768:13')], codes
    h = codes[1][3]
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a = left + [-t for t in reversed(left)]
    k, c = 0, a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 768 and k == 13 and a[0] == 1 and all(a[768 - 1 - i] == -a[i] for i in range(768)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['768'])
    assert listed[i - 1:i + 2] == [['752'], ['768'], ['784']], listed[i - 1:i + 2]
    assert sum('768' in ns for ns in listed) == 1, [ns for ns in listed if '768' in ns]
    assert new_cells(text)[768] == (13, 13), new_cells(text)[768]
    assert changelog_by_day().get('2026-11-03', {}).get(768) == (13, 13), changelog_by_day().get('2026-11-03')
    assert mstar_data()['cols'][768 - 1] == [13, 13, ['example', 'equipow p768'], ['residue', 5]], mstar_data()['cols'][768 - 1]


def q_example_at_672_has_its_code_of_order_13():
    # Replicata: the remarks' entry naming 672, its codes decoded by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the
    # rest by (-1)^m symmetry), the new results' cell of 672, the changelog's statements of 2026-11-04, the table of smallest lengths, and mstar.js's column.
    # Expectata (2026-11-04: the tilted search, searches/tilted/, found an antisymmetric example of order 13 at 672):
    # 672's entry, an <li class="c"> marked ◆, its statement of m* \\(m^* = 13\\), between 656's and 688's; its codes p672 (m = 12) and
    # p672 (m = 13), in that order, the second <code id="672:13">, its signs of order exactly 13 (synthetic division here), antisymmetric, +1 at
    # 0; no other entry names 672; the cell 13 to 13; the changelog's statement of 672 on 2026-11-04 is (13, 13) (quals_index's statement()), on a line of its own
    # (NOTEWORTHY: the smallest length known with order 13); order 13's row reads 480, 672, unproven; mstar.js's column [13, 13, ["example", "equipow p672"], ['residue', 5]].
    # Resultata before: 672 was 12 to 13, with one code, of order 12, and order 13's least known length was 720.
    text = page()
    entry = '<p class="entry">\\(n = 672\\): &nbsp;\\(m^* = 13\\)</p>'
    li = re.search(r'<li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      ' + re.escape(entry) + r'\n(.*?)\n    </li>', text, re.S)
    assert li, 'no entry of 672 alone with its new statement'
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="(\d+:\d+)">([0-9A-F]+)</code>', li.group(1))
    assert [c[:3] for c in codes] == [('672', '12', '672:12'), ('672', '13', '672:13')], codes
    h = codes[1][3]
    assert h == '94E71B4AB0A5E5785A33AC2F58C2778C2D699A17D467584AD5B4297A4EB48D2BCAD2B3C5255AE612A567', h
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a = left + [-t for t in reversed(left)]
    k, c = 0, a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 672 and k == 13 and a[0] == 1 and all(a[672 - 1 - i] == -a[i] for i in range(672)), (len(a), k)
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    i = listed.index(['672'])
    assert listed[i - 1:i + 2] == [['656'], ['672'], ['688']], listed[i - 1:i + 2]
    assert sum('672' in ns for ns in listed) == 1, [ns for ns in listed if '672' in ns]
    assert new_cells(text)[672] == (13, 13), new_cells(text)[672]
    assert changelog_by_day().get('2026-11-04', {}).get(672) == (13, 13), changelog_by_day().get('2026-11-04')
    assert smallest_table()[12] == ['13', '480', '672', ''], smallest_table()[12]
    assert mstar_data()['cols'][672 - 1] == [13, 13, ['example', 'equipow p672'], ['residue', 5]], mstar_data()['cols'][672 - 1]


def q_example_at_1440_settles_a_15():
    # Replicata: the section of the table of smallest lengths, its code decoded by the paper's Table 5 convention, the table as the page draws it, the
    # changelog's entries, the OEIS section's note on A323395, and mstar.js.
    # Expectata (2026-11-04: the tilted search, searches/tilted/, found a symmetric example of order 16 at 1440): the section holds one code, <code id="1440:16">, its signs of
    # order exactly 16 (synthetic division here), symmetric, +1 at 0, and says m* is 16 or 17; 1440 has no remark, Table 1 having no cell for it
    # (q_new_results_state_what_the_chart_proves); order 16's row of the table reads 1440, 1440, proven, since mstar.js's mtopAt is 1440; the changelog has an entry of 2026-11-04
    # stating a(15) = 1440 (no m*(1440) statement, for the same reason: q_changelog_brings_every_new_result_up_to_date); and the OEIS note on A323395 states a(15) = 1440.
    # Resultata before: order 16's row read 1440, 1920, not proven, and no example of order 16 was known below 1920.
    text = page()
    section = re.search(r'<section class="smallest".*?</section>', text, re.S).group(0)
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="(\d+:\d+)">([0-9A-F]+)</code>', section)
    assert [c[:3] for c in codes] == [('1440', '16', '1440:16')], codes
    h = codes[0][3]
    assert h == '9E21C6F54B340E3CAF46C59F362A518761CD3896A8DAB346DC58D731D72B46AC9A3630DAA94E91D235364CD316F68A7B8AF8E336A449B12CD9E0D6D51AA55C49AC65CCCB90F2D5EA2A166DB9936D0369D05CF5A95CA006EF87B2', h
    left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
    a = left + left[::-1]
    k, c = 0, a
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    assert len(a) == 1440 and k == 16 and a[0] == 1 and a == a[::-1], (len(a), k)
    assert '\\(m^*(1440) \\in \\{16, 17\\}\\)' in section, 'the bounds at 1440'
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', text)]
    assert not any('1440' in ns for ns in listed) and 1440 not in new_cells(text), listed
    assert smallest_table()[15] == ['16', '1440', '1440', '✓'], smallest_table()[15]
    # (mtopAt is a list since 2026-11-04, [M17], order 16's n first)
    assert mstar_data()['mtopAt'][0] == 1440 and mstar_data()['past'] == [[1440, 16, 'equipow p1440']], mstar_data()['past']
    assert any(d == '2026-11-04' and '\\(a(15) = 1440\\)' in rest for d, rest in changelog()), changelog()[:3]
    body = re.search(r'<section class="oeis" aria-labelledby="oeis-title">.*?</section>', text, re.S).group(0)
    assert '\\(a(15) = 1440\\)' in re.search(r'<li>(.*?)</li>', body, re.S).group(1), 'the note on A323395'


OEIS = ('A323395', 'A306248', 'A323610', 'A323629', 'A323614')                # the OEIS section's entries on this problem
RELATED = ('A382832', 'A382833', 'A362039', 'A010060', 'A106400', 'A001969', 'A000069', 'A140047')   # and related ones


def q_oeis_section_links_the_family():
    # Replicata: index.html: the section after the table of smallest lengths.
    # Expectata (dreeves, 2026-10-28: "can you make a section that links to all the relevant OEIS entries and notes any
    # discrepancies?"): a <section class="oeis" aria-labelledby="oeis-title"> with its h2 oeis-title (its place, a
    # TODO comment, a block quote by Claude and its attribution "— Claude" were pinned too until 2026-10-30, when
    # dreeves's edits took them out), with two lists: one item per entry on this problem (OEIS:
    # A323395, A306248, A323610, A323629, A323614), then one per related entry (RELATED: A382832, A382833, A362039,
    # A010060, A106400, A001969, A000069, A140047), each in that order and each linking https://oeis.org/ and its
    # number, once, and no other entry.
    sec = re.search(r'<section class="oeis" aria-labelledby="oeis-title">.*?</section>', page(), re.S)
    assert sec, 'no section "oeis"'
    body = sec.group(0)
    assert '<h2 id="oeis-title">' in body, body[:400]
    lists = [re.findall(r'<li>(.*?)</li>', ul, re.S) for ul in re.findall(r'<ul>(.*?)</ul>', body, re.S)]
    links = [[re.findall(r'href="https://oeis\.org/(A\d{6})"', li) for li in items] for items in lists]
    assert links == [[[a] for a in OEIS], [[a] for a in RELATED]], links


def q_oeis_notes_hold_on_the_chart():
    # Replicata: the OEIS section's first list, and mstar.js.
    # Expectata: what each note says of this page holds in the chart's data (OEIS's k-powerful is order k + 1 here):
    # A323395's: a(10) = 432 proven (the least n known to reach order 11 is the least n allowed it); a(11) = 480 proven, since 2026-11-03 (order 12 ruled out at 432, 448 and 464, known at 480;
    # until then a(11) was 432 or 480, order 12 open at 432); order 12 known at 864, and since 2026-11-03 order 15 at 960 (lo),
    # 672 the least n known to reach order 13 (so a(12) <= 672, since 2026-11-04; 720 from the beam campaign's 720:13 on 2026-11-03, 912 that morning), a(14) = 960 proven (the
    # least n known to reach order 15 is the least n allowed it), and a(15) = 1440 proven (since 2026-11-04: q_example_at_1440_settles_a_15);
    # (until 2026-11-03: order 13 at 960, the least n known to reach it, so a(12) <= 960, doubling 960 giving 1920); A306248's: m*(2n) settled
    # (lo = hi) for every n up to 143 and open at 288, 48 more terms than OEIS's 95; A323610's and A323614's: their
    # comments' descriptions of L6 (48 and the multiples of 8 from 64) and L8 (144 and the multiples of 16 from 192)
    # are exactly the chart's lengths of order 6 and 8 through 1024, every other length ruled out; A323629's: 112 in
    # L7 (m*(112) = 7, A306248's a(56)), and its comment's description with 112 added (96, 112, 128, 144, 160, 176
    # and the multiples of 8 from 192) the chart's L7 through 1024.  Each note states its numbers.  (OEIS's side,
    # fetched on 2026-10-28, is in scratch/oeis/: its JSON, b-files and compare.py.)
    text = page()
    body = re.search(r'<section class="oeis" aria-labelledby="oeis-title">.*?</section>', text, re.S).group(0)
    notes = dict(zip(OEIS, re.findall(r'<li>(.*?)</li>', re.search(r'<ul>(.*?)</ul>', body, re.S).group(1), re.S)))
    cols = mstar_data()['cols']
    lo, hi = (lambda n: cols[n - 1][0]), (lambda n: cols[n - 1][1])
    known = lambda m: next(n for n in range(2, NMAX + 1, 2) if lo(n) >= m)
    allowed = lambda m: next(n for n in range(2, NMAX + 1, 2) if hi(n) >= m)
    assert known(11) == allowed(11) == 432 and (lo(864), lo(960)) == (12, 15) and known(13) == 672 and known(15) == allowed(15) == 960
    assert max(hi(432), hi(448), hi(464)) < 12 <= lo(480) and known(12) == allowed(12) == 480
    assert all(w in notes['A323395'] for w in ('432', '448', '464', '480', '672', '864', '960', '1440')), notes['A323395']
    assert all(lo(2 * n) == hi(2 * n) for n in range(1, 144)) and lo(288) < hi(288)
    assert all(w in notes['A306248'] for w in ('95', '48', '143', '286', '288')), notes['A306248']
    rules = {'A323610': (6, lambda n: n == 48 or (n % 8 == 0 and n >= 64)),
             'A323629': (7, lambda n: n in (96, 112, 128, 144, 160, 176) or (n % 8 == 0 and n >= 192)),
             'A323614': (8, lambda n: n == 144 or (n % 16 == 0 and n >= 192))}
    for a, (m, rule) in rules.items():
        assert all((lo(n) >= m) == rule(n) and (hi(n) >= m) == rule(n) for n in range(2, NMAX + 1, 2)), a
        assert NMAX == 1024 and '1024' in notes[a], notes[a]
    assert lo(112) == hi(112) == 7 and all(w in notes['A323629'] for w in ('112', '56')), notes['A323629']


# A323629's generating function as OEIS gives it (Alois P. Heinz's, fetched 2026-10-28), and as it is with 112, each
# with the coefficients of its numerator over (1 - x)^2: -8x(x^6 + 2x^2 + 8x - 12) = 96x - 64x^2 - 16x^3 - 8x^7, and
# 8x(12 - 10x - x^7) = 96x - 80x^2 - 8x^8.
L7_GF_OEIS = (r'\(-8x(x^6 + 2x^2 + 8x - 12)/(x - 1)^2\)', {1: 96, 2: -64, 3: -16, 7: -8})
L7_GF = (r'\(8x(12 - 10x - x^7)/(1 - x)^2\)', {1: 96, 2: -80, 8: -8})


def gf_terms(numerator, nmax):
    """The coefficients of x, x^2, ... in numerator/(1 - x)^2 up to the last that is at most nmax, numerator as {power:
    coefficient} with no constant term, its series rising: 1/(1 - x)^2 is the sum of (i + 1) x^i."""
    terms = []
    for n in itertools.count(1):
        c = sum(a * (n - j + 1) for j, a in numerator.items() if j <= n)
        if c > nmax: return terms
        terms.append(c)


def q_oeis_errors_say_how_to_fix_them():
    # Replicata: the OEIS section's first list, and mstar.js.
    # Expectata (dreeves, 2026-10-29: "can you make sure the errors in OEIS are made clear on the page? then we don't
    # need suggested_edits.txt"): the note on the entry with an error, A323629, and no other, marks it with a bold "Error:"
    # and gives the fix.  A323395's comment (a(12) ≤ 864, a(13) ≤ 960) holds since 2026-11-03, by the beam campaign's example of order 13
    # at 720, the least n known to reach order 13 (12-powerful), and the example of order 15 at 960, the least n known to reach order 14, though
    # not by the doublings: its note marks no error and says that a(12) ≤ 720.  (Until 2026-11-03 both bounds were wrong, and should have read
    # a(12) ≤ 960 and a(13) ≤ 1920; that morning, before 720:13, its a(12) ≤ 864 was still wrong, and should have read a(12) ≤ 912.)
    # Since 2026-11-04 the least n known to reach order 13 is 672 (q_example_at_672_has_its_code_of_order_13), and the note says that a(12) ≤ 672.
    # A323629's generating function, L7_GF_OEIS, should be L7_GF: through 1024, L7_GF's series is
    # the chart's L7 (every n with m*(n) ≥ 7) and L7_GF_OEIS's is L7 without 112.
    # Resultata before: the A323395 note said its bounds "look one order too high", and the A323629 note gave no
    # generating function; scratch/oeis/suggested_edits.txt held the fixes.
    body = re.search(r'<section class="oeis" aria-labelledby="oeis-title">.*?</section>', page(), re.S).group(0)
    notes = dict(zip(OEIS, re.findall(r'<li>(.*?)</li>', re.search(r'<ul>(.*?)</ul>', body, re.S).group(1), re.S)))
    assert [a for a in OEIS if '<b>Error:</b>' in notes[a]] == ['A323629'] and notes['A323629'].count('<b>Error:</b>') == 1, notes
    lo = lambda n: mstar_data()['cols'][n - 1][0]
    assert next(n for n in range(2, NMAX + 1, 2) if lo(n) >= 13) == 672 and next(n for n in range(2, NMAX + 1, 2) if lo(n) >= 14) == 960
    assert all(t in notes['A323395'] for t in (r'\(a(12) \le 864\)', r'\(a(13) \le 960\)', r'\(a(12) \le 672\)')), notes['A323395']
    L7 = [n for n in range(2, NMAX + 1, 2) if lo(n) >= 7]
    assert gf_terms(L7_GF[1], NMAX) == L7 and gf_terms(L7_GF_OEIS[1], NMAX) == [n for n in L7 if n != 112]
    after = notes['A323629'].split('<b>Error:</b>')[1]
    assert L7_GF_OEIS[0] in after and L7_GF[0] in after and after.index(L7_GF_OEIS[0]) < after.index(L7_GF[0]), after


def q_912_moves_excess_3_to_2_29():
    # Replicata: pow2.js's columns 2^28 to 2^35, the new results' cells of 2^29, 2^30, 2^33 and 2^34 and their remarks'
    # entries, and the theorem's statement and its list of firsts.
    # Expectata (2026-10-28: with 912 at order 12 among the blocks, the exhaustive search of scratch/wish4 finds 2^29 =
    # (608 # 800^2) ∨ (336^2 # 912) ∨ (240 # 432^2), each product of order 32, and no K <= 28 beating Thue-Morse by 3):
    # pow2.js's lo is k + 2 at 2^28 and k + 3 from 2^29 to 2^35, column 29 that join; the cells read 2^29 32–35, 2^30
    # 33–36, 2^33 36–40 and 2^34 37–41; 2^29's entry gives 2^29 = 608·800² + 336²·912 + 240·432², a join of three
    # products of examples above, each of order 32, that beats Thue–Morse by 3; 2^30's, 2^33's and 2^34's each name the
    # 2^29 entry, each product times τ1, τ4 and τ5, of orders 33, 36 and 37; the theorem states m*(2^29) ≥ 32 in place
    # of m*(2^30) ≥ 33, and its list of firsts is 10, 20, 29, 37, 41, 48, 57, 65, 68.  Since 2026-11-03 (q_firsts_of_2026_11_03) excess 3 is first at 2^28 and column 29 is
    # that join's lift; what stands of this qual: lo is k + 3 from 2^29 to 2^35, those cells, and no K below 2^28 beating Thue-Morse by 3.
    cols, text = pow2_data()['cols'], page()
    assert cols[26][0] == 29 and [c[0] - k for k, c in enumerate(cols[28:35], 29)] == [3] * 7, [c[:2] for c in cols[26:35]]
    cells = new_cells(text)
    assert [cells[2 ** k] for k in (29, 30, 33, 34)] == [(32, 35), (33, 36), (36, 40), (37, 41)], [cells.get(2 ** k) for k in (29, 30, 33, 34)]
    theorem = the_theorem(text)
    assert '(2^{29})' not in theorem and '(2^{30})' not in theorem, theorem   # 2^29's bound in it until 2026-11-03


def q_768_moves_excess_5_to_2_39():
    # Replicata: pow2.js's columns 2^38 to 2^47, the new results' cells of 2^39, 2^41, 2^43 and 2^46 and their remarks'
    # entries, and the theorem's statement and its list of firsts.
    # Expectata (2026-10-28 evening: with 768 at order 12 among the blocks, the exhaustive search of scratch/wish5 finds
    # 2^39 = (800 # 832^3) ∨ (192 # 432^2 # 768 # τ1) ∨ (48 # 480^2 # 768 # τ2), each product of order 44, and no K <=
    # 38 beating Thue-Morse by 5): pow2.js's lo is k + 4 at 2^38 and k + 5 from 2^39 to 2^47, column 39 that join; the
    # cells read 2^39 44–47, 2^41 46–50, 2^43 48–53 and 2^46 51–57; 2^39's entry says a join of three products of
    # examples above and Thue–Morse, each of order 44, beats Thue–Morse by 5; 2^41's, 2^43's and 2^46's each name the
    # 2^39 entry, each product times τ2, τ4 and τ7, of orders 46, 48 and 51; the theorem states m*(2^39) ≥ 44 in place
    # of m*(2^41) ≥ 46.  (From 2026-10-26, when 816's example of order 11 moved it from 2^43, until then, excess 5's
    # first was 2^41 = (800^2 # 832 # 848 # τ2) ∨ (432^3 # 816 # τ2) ∨ (480^3 # 784) ∨ (432^2 # 480^2), each product
    # of order 46, 816's of order 47 after 816's example of order 12 that afternoon: q_816_moves_excess_5_to_2_41.)  (Since 2026-11-03, q_firsts_of_2026_11_03: k + 5 from
    # 2^39 to 2^46, 2^47 at k + 6.)
    cols, text = pow2_data()['cols'], page()
    base = cols[38][2]
    assert cols[37][0] == 42 and [c[0] - k for k, c in enumerate(cols[38:46], 39)] == [5] * 8, [c[:2] for c in cols[37:46]]
    # 768 is a block of order 13 since 2026-11-03 (the beam campaign's plan 6; 12 before): the two products holding it
    # have order 45, and the join stays 44, the first product's.
    assert base[0] == 'joins' and sorted(map(sorted, base[1])) == sorted(map(sorted, [
        [[800, 11], [832, 11], [832, 11], [832, 11]], [[192, 9], [432, 11], [432, 11], [768, 13], [2, 1]],
        [[48, 6], [480, 12], [480, 12], [768, 13], [4, 2]]])), base
    cells = new_cells(text)
    assert [cells[2 ** k] for k in (39, 41, 43, 46)] == [(44, 47), (46, 50), (48, 53), (51, 57)], [cells.get(2 ** k) for k in (39, 41, 43, 46)]
    # the entries' wording unpinned since 2026-10-30
    theorem = the_theorem(text)
    assert '(2^{39}) \\ge 44' in theorem and '(2^{41})' not in theorem, theorem


# ---------------------------------------------------------------------------------------------------------------------
# Browser quals

QUOTED = r'(?:Claude|Astra): ["“”]'          # Claude: or Astra: and then a quotation mark: a quotation of its words


def visible_text():
    """index.html's text a reader sees, with every comment, script, style and tag (attribute values with it) blanked out
    character for character, so positions are the file's."""
    text = page()
    for pat in (r'<!--.*?-->', r'<script\b[^>]*>.*?</script>', r'<style>.*?</style>', r'<[^>]*>'):
        text = re.sub(pat, lambda m: re.sub(r'[^\n]', '\0', m.group(0)), text, flags=re.S)
    return text


def q_quotes_of_claude_and_astra_are_curly():
    # Replicata: index.html's text a reader sees (visible_text), its tags' attribute values and its scripts (in page/
    # since 2026-10-31, inline before); and the light run's readouts of the m*(n) chart's cells ringed in gold.
    # Expectata (dreeves's README, 2026-10-30: "[CUR] Curly quotes for quoting Claude and Astra"): each quotation of
    # Claude's or Astra's words (QUOTED) opens with “ and closes with ”, the next quotation mark after it, in the text
    # and in an attribute value (as the zoom buttons' titles); no Claude: or Astra: in a script is followed by a straight
    # ", the scripts' strings that write such quotations into the page (the m*(n) readout's note on a ringed cell, the
    # record-gaps table's error line, the labels of a paired study's dots) among them; and a ringed cell's readout
    # quotes Claude with “ and ”.  HTML comments keep straight quotes.
    # Resultata before: 55 quotations in the text, 2 in titles and 3 in scripts, all with straight quotes.
    text = visible_text()
    html = re.sub(r'(<(script|style)\b[^>]*>).*?(</\2>)', r'\1\3', re.sub(r'<!--.*?-->', '', page(), flags=re.S), flags=re.S)
    tags = [v for t in re.findall(r'<[a-zA-Z][^>]*>', html) for v in re.findall(r"""=(?:'([^']*)'|"([^"]*)")""", t)
            for v in v if v]
    quotes = [(s, m) for s in [text] + tags for m in re.finditer(QUOTED, s)]
    assert quotes, 'no quotation of Claude or Astra'
    bad = [s[m.start():m.end() + 60].replace('\0', '') for s, m in quotes
           if m.group(0)[-1] != '“' or (re.compile(r'["“”]').search(s, m.end()) or [''])[0] != '”']
    assert bad == [], (len(bad), bad[:5])
    scripts = page_scripts(page())
    assert not any(re.search(r'(?:Claude|Astra): "', js) for js in scripts), [re.findall(r'.{30}(?:Claude|Astra): ".{30}', js) for js in scripts]
    R = valid_run('light')
    rings = set(a323395_cells(mstar_data()['cols']))
    notes = [t for n, m, t in R['hovers'] if (n, m) in rings]
    # A note may or may not quote Claude (dreeves's 6220ea2, 2026-10-30, dropped Claude: “…” from the m*(n) chart's
    # ring notes); one that does uses “ and ”.
    assert notes and all('Claude: "' not in t and t.count('“') == t.count('”') for t in notes), notes[:3]


# The page's codes as anchors, and no "index.html" for its readers (dreeves's README, 2026-10-31: "[IND] Find a better
# way to refer to things like "index.html p320" -- we should never refer to "index.html" in user-facing copy. How about
# just drop the "index.html" and make the "p320" or whatever be a hyperlink / anchor link? If that doesn't work for
# hovertext, we could just say "equipow p320" instead of "index.html p320".")

# The names in the page's math of sequences whose codes the page does not show, so that a name there has no code to link
# to: BGPW's example of order 10 at 240 (the published paper's Table 5), a factor of 2^20's construction.  Since
# 2026-10-31 each is a part of a construction (data-construction), whose derivation cites mstar.js's source of it.
OFF_PAGE = ('p_{240}',)


def blank_comments(text):
    """text with each HTML comment blanked out character for character, so that positions are text's."""
    return re.sub(r'<!--.*?-->', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)


def unlink(text):
    """text with each link of a name to its code, \\href{#N:M}{name} (2026-10-31, [IND]), written as the name alone."""
    return re.sub(r'\\href\{#\d+:\d+\}\{([pq]_\{\d+\})\}', r'\1', text)


def page_codes(text):
    """[(start, end, n, m, attributes, hex)] for each code of the code blocks (<p class="code">) of text, a version of
    index.html with its comments blanked: its block's span in text; its order m, the (m = M) of its block's labels in
    order, one for each code and each join of codes (<span data-join="IDS" data-order="M">, since 2026-10-31) of the
    block; its length n, by the paper's Table 5 convention (the hex digits give the left half of the signs, the rest
    follows by (-1)^m symmetry); and its <code> tag's attributes."""
    out = []
    for b in re.finditer(r'<p class="code">(.*?)</p>', text, re.S):
        ms = [int(x) for x in re.findall(r'\\\(\(m = (\d+)\)\\\)', b.group(1))]
        tags = re.findall(r'<code([^>]*)>([0-9A-F]+)</code>|<span data-join="[^"]*" data-order="\d+">', b.group(1))
        assert len(ms) == len(tags) == b.group(1).count('<code') + b.group(1).count(' data-join=') >= 1, b.group(1)
        out += [(b.start(), b.end(), 8 * len(h), m, attrs, h) for m, (attrs, h) in zip(ms, tags) if h]
    return out


def q_codes_are_anchors_and_names_link_to_them():
    # Replicata: index.html outside its comments: the codes of its code blocks (page_codes) and the names p_{N} and
    # q_{N} in its math; and the light run's links to anchors of the page (R's anchors) and its math.
    # Expectata ([IND]: "make the "p320" or whatever be a hyperlink / anchor link"): each code is <code id="N:M">, N its
    # length and M its order, the ids distinct; a name in a code's own block with that code's length is the code's own
    # name (p_{448} in its label, p_{192} in its and in the join beside it); a name inside a join of codes (<span
    # data-join="IDS">, since 2026-10-31: a button, which holds no link) stands for the code that IDS lists at its
    # place, and is that code's own name; a name p_{N} inside a construction (<span data-construction="N:M">, since
    # 2026-10-31: a button too, whose derivation's rows link to the codes instead, which quals_derivations'
    # q_leaves_resolve checks) stands for the best known sequence of length N, the code N:L with L mstar.js's lower
    # bound at N, and is that code's own name, or else it is one of OFF_PAGE, which no code carries, each of which is
    # such a part; every other name is \href{#N:M}{name}, a link to the one code whose own names include it; every
    # \href of the page is such a link; and in the light run each is an <a> that KaTeX drew, to the <code> of its id,
    # and KaTeX drew no command in its error color (an \href it does not trust, it draws as its name in red).
    # Resultata before: no code had an id, and no name was a link.  Then (2026-10-31, the constructions made buttons,
    # their names no longer links) this qual, which knew no constructions, found 9 names unlinked besides OFF_PAGE's.
    text = blank_comments(page())
    codes = page_codes(text)
    ids = [f'{n}:{m}' for _, _, n, m, _, _ in codes]
    assert [a for *_, a, _ in codes] == [f' id="{i}"' for i in ids] and len(set(ids)) == len(ids), \
        [(i, a) for i, (*_, a, _) in zip(ids, codes) if a != f' id="{i}"'][:5]
    names = [(f.start(1) + x.start(), x.group(0), int(x.group(1)))         # (position, name, N)
             for f in re.finditer(r'\\\((.*?)\\\)', text, re.S) for x in re.finditer(r'\b[pq]_\{(\d+)\}', f.group(1))]
    own = lambda i, n: [f'{c[2]}:{c[3]}' for c in codes if c[0] <= i < c[1] and c[2] == n]
    owners = {}                                                             # name: the ids of the codes it is an own name of
    for i, name, n in names:
        for c in own(i, n): owners.setdefault(name, set()).add(c)
    links = {x.start(2): (x.group(1), x.group(2)) for x in re.finditer(r'\\href\{#([^}]*)\}\{([pq]_\{\d+\})\}', text)}
    parts = {}                                                              # a name inside a join: the id it stands for
    for x in re.finditer(r'<span data-join="([^"]*)" data-order="\d+">(.*?)</span>', text, re.S):
        inside = [i for i, name, n in names if x.start(2) <= i < x.end(2)]
        assert len(inside) == len(x.group(1).split(' ')), (inside, x.group(1))
        parts.update(zip(inside, x.group(1).split(' ')))
    assert [(name, parts[i]) for i, name, n in names if i in parts and owners.get(name) != {parts[i]}] == [], parts
    cols = mstar_data()['cols']
    built = {}                                                              # a name inside a construction: the id it stands for
    for x in re.finditer(r'<span data-construction="[^"]*">(.*?)</span>', text, re.S):
        built.update((i, f'{n}:{cols[n - 1][0]}') for i, name, n in names if x.start(1) <= i < x.end(1) and not own(i, n))
    assert [(name, built[i]) for i, name, n in names if i in built and owners.get(name, set()) != {built[i]}
            and not (name in OFF_PAGE and name not in owners)] == [], built
    assert sorted({name for i, name, n in names if i in built and name in OFF_PAGE}) == sorted(OFF_PAGE), built
    others = [(i, name) for i, name, n in names if not own(i, n) and i not in parts and i not in built]
    assert text.count('\\href') == len(links) == sum(i in links for i, _ in others), (text.count('\\href'), len(links))
    unlinked = sorted({name for i, name in others if i not in links})
    assert unlinked == [] and not owners.keys() & set(OFF_PAGE), unlinked
    bad = [(name, links[i]) for i, name in others if i in links and (links[i][1] != name or owners.get(name) != {links[i][0]})]
    assert bad == [], bad
    R = valid_run('light')
    assert sorted(R['anchors']) == sorted([f'#{t}', 'CODE', True] for t, _ in links.values()), (R['anchors'][:5], len(links))
    assert R['math']['unsupported'] == 0, R['math']


def q_readers_never_see_index_html():
    # Replicata: index.html outside its comments; page/'s stylesheet and scripts outside their comments (/* ... */, and in
    # a script a // at a line's start or after a space, to the line's end); mstar.js's and pow2.js's data as node sees
    # it (their reasons, not their first lines' comments); and the light run: the page's text and attribute values once
    # its scripts ran (R's indexHtml) and the readouts of its hovers.
    # Expectata ([IND]: "we should never refer to "index.html" in user-facing copy ... If that doesn't work for
    # hovertext, we could just say "equipow p320" instead of "index.html p320""): none of them holds "index.html"; and
    # the readout of a cell that an example of the page settles names it as equipow and its name: 320's, "(equipow
    # p320)", and 352's, "(equipow BGPW 352)".
    # Resultata before: 34 of mstar.js's example labels ("index.html p320", "index.html BGPW 352", ...), and so the
    # light run's readouts of their columns.
    assert 'index.html' not in blank_comments(page())
    for name in sorted(os.listdir(PAGE_DIR)):
        src = re.sub(r'/\*.*?\*/', '', open(os.path.join(PAGE_DIR, name), encoding='utf-8').read(), flags=re.S)
        code = re.sub(r'(^|(?<=\s))//[^\n]*', '', src, flags=re.M) if name.endswith('.js') else src
        assert 'index.html' not in code, (name, re.findall(r'.{0,40}index\.html.{0,20}', code)[:3])
    for data in (mstar_data(), pow2_data()):
        text = json.dumps(data, ensure_ascii=False)
        assert 'index.html' not in text, re.findall(r'.{30}index\.html.{20}', text)[:5]
    R = valid_run('light')
    assert R['indexHtml'] == [], R['indexHtml'][:5]
    shown = [t for n, m, t in R['hovers'] if 'index.html' in t]
    assert shown == [], (len(shown), shown[:3])
    for n, label in ((320, 'equipow p320'), (352, 'equipow BGPW 352')):
        assert any(f'({label})' in t for k, m, t in R['hovers'] if k == n), [t for k, m, t in R['hovers'] if k == n]


def q_page_loads_clean():
    # Replicata: index.html with the real mstar.js in headless Chrome, 1280 px wide at 2 device px per CSS px; and the
    # page loaded as is (nothing added), with Chrome logging its console to stderr.
    # Expectata: no errors, console errors or warnings; the canvas is drawn (nonzero height, as wide as main's content);
    # the chart opens showing all NCOL = 257 columns, n = 2 and the multiples of 4 up to 1024.  The plain
    # load logs nothing at all to the console.
    assert console_lines() == [], console_lines()
    R = valid_run('light')
    assert R['canvasDev'][1] > 0 and close(R['canvasCss'][0], R['mainContentW'], 1), R
    v = R['views'][0]
    assert close(v['u0'], 0, 0.01) and close(v['span'], NCOL, 0.05), v


def q_sections_space_their_parts():
    # Replicata: the light run: each section of main, and the space between each two of its children laid out one after
    # the other (the least per section).
    # Expectata (dreeves, 2026-10-30: "what's up with the spacing here?", of the smallest lengths' heading, paragraph and
    # table, flush once his edit took them out of the block quote whose grid had spaced them): at least 12 px, as every
    # section with two or more parts has, in each of the page's 8 sections (9 until the section of sets left the page
    # on 2026-10-31).
    # Resultata before: 0 px in the sections smallest, oeis and lattice.
    R = valid_run('light')
    tight = [(c, g) for c, g in R['sectionGaps'] if g is not None and g < 12]
    assert len(R['sectionGaps']) >= 8 and not tight, (tight, R['sectionGaps'])


def q_prose_has_one_measure():
    # Replicata: the light run (1280 px wide, main's content box 960 px): every p and li of main outside the legends.
    # Expectata (dreeves, 2026-10-29, of the paragraph above the m*(n) chart, which ran the column's full width, and the
    # powers-of-2 chart's caption, 46rem: "the right margin seems to be inconsistent here"): the running text has one
    # measure, the 46rem of the text sections, so each justified p or li ends 736 px from the left of main's content
    # box (within 0.5 px), while tables and charts may span the column.  The charts' readouts are their charts': as
    # wide as the column, and ragged (text-align start), as their text changes under the pointer.
    # Resultata before: justified text ended 672 px (the header's 42rem), 736 and 960 px from it.
    R = valid_run('light')
    assert close(R['mainContentW'], 960, 0.5), R['mainContentW']
    ends = sorted({round(right, 1) for _, align, right in R['prose'] if align == 'justify'})
    assert len(ends) == 1 and close(ends[0], 736, 0.5), ends
    readouts = {i: (align, round(right, 1)) for i, align, right in R['prose'] if i in ('mstar-readout', 'pow2-readout')}
    assert readouts == {'mstar-readout': ('start', 960.0), 'pow2-readout': ('start', 960.0)}, readouts


def q_drawn_cells_match_data():
    # Replicata: the light and phone runs: the full view, and a sweep of the 257 columns, n = 2, 4, 8, 12, …, 1024,
    # zoomed in, so every column is at least 3 device px wide.
    # Expectata: every column is checked, in every row: its middle pixel has its color from mstar.js (exists up
    # to lo, open up to hi, impossible above) as the page's tokens give it, and the pixel below each row is paper.  In
    # the full view and every view of the sweep, every pixel of row 1 is exists, from the plot's left edge to its
    # right: no odd column (impossible in every row, since lo = hi = 0) is drawn, not even mixed into a pixel; but for
    # the ring of a cell of row 1 (q_chart_rings_the_smallest_lengths_in_gold), and since 2026-10-30 the gold dot of a
    # cell of row 1 proven the least, passed over a device px either side (rowOneSkips), the cells next to a ring in its
    # row and the row above, which that qual checks instead, and the column lines of the zoomed views (rowOneLines),
    # which q_mstar_grid_lines_come_with_zoom checks.
    data = mstar_data()
    assert all(data['cols'][n - 1][0] >= 1 for n in COLUMNS), 'some column has no exists cell in row 1'
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['pixelBad'] == [], (name, R['pixelBad'][:10])
        assert R['pixelColumns'] == COLUMNS, (name, sorted(set(COLUMNS) ^ set(R['pixelColumns']))[:20])
        assert R['pixelChecks'] >= NCOL * len(R['rows']), (name, R['pixelChecks'])
        assert len(R['rows']) == data['mtop'], (name, len(R['rows']))
        assert R['rowOneBad'] == [], (name, len(R['rowOneBad']), R['rowOneBad'][:10])
        assert R['rowOneChecks'] + R['rowOneSkips'] + R['rowOneLines'] == len(R['views']) * (R['plot'][1] - R['plot'][0]), (name, R['rowOneChecks'])
        assert R['rowOneSkips'] <= len(R['views']) * (4 * R['dpr'] + 6), (name, R['rowOneSkips'])


def q_aria_labelledby_names_an_element():
    # Replicata: index.html: each aria-labelledby attribute and each id.
    # Expectata: each id an aria-labelledby names is an element's, so a screen reader announces each section by its
    # heading.
    # Resultata before (2026-10-29): the m*(n) chart's section named mstar-title, which no element had had since
    # dreeves's paragraph replaced its h2 on 2026-10-27; his new h2 had the id pow-title.
    text = page()
    ids = set(re.findall(r'\bid="([^"]+)"', text))
    names = [i for n in re.findall(r'\baria-labelledby="([^"]+)"', text) for i in n.split()]
    assert names and [i for i in names if i not in ids] == [], [i for i in names if i not in ids]


def q_no_block_opens_inside_a_paragraph():
    # Replicata: index.html, its tags in order (html.parser), with the <p> elements open at each.
    # Expectata (dreeves, 2026-10-29: "what's up with the spacing of my <ul> list there?", a list written inside a <p>):
    # no block element (p, ul, ol, li outside a list, table, div, blockquote, figure, section, details, pre, h1-h6)
    # starts while a <p> is open.  An HTML parser closes the <p> there instead, and its </p> then makes an empty
    # paragraph, which the section's grid spaces like any other.
    # Resultata before: the list of exceptions above the m*(n) chart started inside its paragraph, after a <br>.
    BLOCK = {'p', 'ul', 'ol', 'table', 'div', 'blockquote', 'figure', 'section', 'details', 'pre',
             'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    class Paragraphs(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.open, self.bad = 0, []
        def handle_starttag(self, tag, attrs):
            if tag in BLOCK and self.open: self.bad.append((self.getpos(), tag))
            self.open += tag == 'p'
        def handle_endtag(self, tag):
            self.open -= tag == 'p' and self.open > 0
    parser = Paragraphs()
    parser.feed(page())
    assert parser.bad == [], parser.bad


def q_mstar_leaves_out_odd_multiples_of_2():
    # Replicata: mstar.js; the light and phone runs: row 2 of the full view and of every view of the sweep.
    # Expectata (dreeves, 2026-10-29: "can we make my "odd multiple of 2" bullet point be true?", of his "Odd multiples
    # of 2 except 2 itself are left out; for all n=4k+2 for some k ≥ 0, m*(4k+2) = 1"): every n = 2 mod 4 has lo = hi =
    # 1 in mstar.js and every multiple of 4 lo >= 2; the chart's columns are n = 2 and the multiples of 4, NCOL = 257
    # (q_page_loads_clean measures the full view's); and row 2, impossible at every n = 2 mod 4, is exists in every pixel
    # right of n = 2's column, so no other n = 2 mod 4 is drawn, not even mixed into a pixel: but for a device px past
    # n = 2's column, the ring of row 2 and its gold dot (since 2026-10-30: (4, 2) is proven the least) and the zones of
    # the column lines (rowTwoSkips), at most a fifth of the pixels.
    cols = mstar_data()['cols']
    assert all(cols[n - 1][:2] == [1, 1] for n in range(2, NMAX + 1, 4)) and all(cols[n - 1][0] >= 2 for n in COLUMNS[1:])
    assert COLUMNS[:4] == [2, 4, 8, 12] and NCOL == 257
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['rowTwoBad'] == [], (name, len(R['rowTwoBad']), R['rowTwoBad'][:10])
        total = len(R['views']) * (R['plot'][1] - R['plot'][0])
        assert R['rowTwoChecks'] + R['rowTwoSkips'] == total and R['rowTwoSkips'] <= total / 5, (name, R['rowTwoSkips'], total)


def q_mstar_grid_lines_come_with_zoom():
    # Replicata: the light and phone runs: row 1 (exists in every column) of the full view, of every view of the
    # sweep (columns about 30 CSS px wide at 1280 px) and of the first view, zooming in from the full view step by
    # step, whose columns are wider than 4 CSS px (3 steps in at 1280 px, about 6).
    # Expectata (dreeves, 2026-10-29, of a full grid on this chart: "maybe when zoomed in enough the full grid could
    # become visible", then of the powers-of-2 chart's: "this with hairline grid looks great to me"): a line of paper one
    # device px wide at each boundary of whole columns, over the cells at opacity (w - 4) / 4 from 0 up to 1, w a
    # column's width in CSS px: none at the full view (columns under 2 px wide), part at 3 steps in, solid in the sweep.
    # Each line's zone, a device px either side, holds exactly one pixel off exists, that blend of paper over exists
    # within 3 per channel; zones under a ring are the ring's (q_chart_rings_the_smallest_lengths_in_gold), and zones
    # crossing the plot's left or right edge reach into its margins, so they are passed over.
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['lineBad'] == [], (name, len(R['lineBad']), R['lineBad'][:5])
        assert 4 < R['midWidth'] < 8 and R['midZones'] > 0, (name, R['midWidth'], R['midZones'])
        sweep = sum(len(range(math.floor(v['u0']) + 1, math.ceil(v['u0'] + v['span']))) for v in R['views'][1:])
        assert R['lineZones'] >= sweep + R['midZones'] - 4 * len(R['views']), (name, R['lineZones'], sweep, R['midZones'])
        assert R['rowOneLines'] >= 3 * (sweep - 4 * len(R['views'])), (name, R['rowOneLines'], sweep)


def q_chart_rings_the_smallest_lengths_in_gold():
    # Replicata: the light and phone runs: the cells the chart rings, with their roles (R's rings), the ring checks of
    # the sweep, and the token --record.
    # Expectata (dreeves's README, 2026-10-30: "[GLT] ... Or, better: match the "smallest length known" table:
    # green+gold is the smallest *known* n (resp. 2^k) for a give m (resp. delta) and black+gold is the smallest n (resp.
    # 2^k) not ruled out. but then maybe we want an additional visual indicator for when those coincide (the smallest
    # known is proven to be the smallest)?"; from 2026-10-19 until then, dreeves: "in the chart can you highlight the
    # known values for a(m-1)? maybe make those green with gold trim", the proven ones alone): the ringed cells are
    # exactly smallest_rings of mstar.js, the chart's own least columns, the cells of the table of smallest lengths up to
    # 1024 (from 2026-10-31 until 2026-11-03 its rows 14 and 15 gave products beyond the chart, 1920 and 3840): today the proven ones, (2, 1), (4,
    # 2), …, (432, 11), (480, 12), SMALLEST_PROVEN by order ((480, 12) known and (432, 12) not ruled out until 2026-11-03), and (960, 15); then (912, 13) known and
    # (480, 13) not ruled out; (960, 14) known and (480, 14) not ruled out (until 2026-11-03, with no length known (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the
    # chart?"), (480, 14) and (960, 15) not ruled out).  Each is ringed in --record, #ffb300 (the validator's pick against the chart's three
    # colors and the paper), just outside its left and right and below it, in each view of the sweep that checks it,
    # and every one is checked; at its middle a proven one is gold, a dot (Claude's proposal for when the two coincide),
    # and the others keep their cell's color.  (Their readouts' notes: q_hover_reads_out_cells.)
    # Resultata before: only the 11 proven cells were ringed.
    cols = mstar_data()['cols']
    want = smallest_rings(cols)
    assert [c for c, role in want.items() if role == 3] == a323395_cells(cols) == PROVEN_CELLS, want
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert {(n, m): role for n, m, role in R['rings']} == want, (name, R['rings'])
        assert R['tokens']['record'] == '#ffb300', (name, R['tokens'])
        assert R['ringChecks'] >= len(want) and R['ringBad'] == [], (name, R['ringChecks'], R['ringBad'][:5])
        assert sorted(tuple(map(int, c.split(','))) for c in R['ringed']) == sorted(want), (name, R['ringed'])


def q_readout_reports_columns_only():
    # Replicata: the light and phone runs: every hover of the harness (the full view, every view of the sweep, the
    # searches for column edges, which probe within a millionth of a px of them, and the interactions), and a hover at
    # the middle of every device px across row 1 of the full view.
    # Expectata: no readout reports an n without a column (odd, or 2 mod 4 but 2; only odd before 2026-10-29); across
    # the full view the readout goes through n = 2, 4, 8, 12, …, 1024, each once, in order from left to right.
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['hiddenReadouts'] == [] and R['readouts'] > 2 * NCOL, (name, R['readouts'], R['hiddenReadouts'][:5])
        assert R['across'] == COLUMNS, (name, R['across'][:20])


def q_n_labels_are_round_multiples_of_4():
    # Replicata: the strings drawn below the rows, right of the plot's left edge, in one draw in each of the full view,
    # every view of the sweep, and the view zoomed in as far as it goes: the draw of a hover over the first whole
    # column in view; in the light and phone runs.
    # Expectata: the n labels, and then (since 2026-11-02, dreeves's README: "[HOV] ...") the tag of the cell read out,
    # the n of that first column, centered on its middle to within a device px (q_axes_tag_the_cell_read_out).  The
    # labels are the multiples of one step s, from 4, 20, 40, 100, 200, 500 (so every label is an n with a column, n / 4
    # from 1 on; until 2026-10-29 the steps were 2, 10, 20, 50, ... and every even n had a column), whose columns'
    # middles are in view, in order, each centered on its column's middle to within a device px; s is the first of
    # those steps that puts the labels at least 48 CSS px apart.
    for name in ('light', 'phone'):
        R = valid_run(name)
        (PL, PR), dpr = R['plot'], R['dpr']
        assert len(R['labelDraws']) == len(R['views']) + 1, (name, len(R['labelDraws']))
        for d in R['labelDraws']:
            v, (*got, tag) = d['v'], d['labels']
            s = next(s for s in STEPS if s / 4 * (PR - PL) / dpr / v['span'] >= 48)
            want = [n for n in range(s, NMAX + 1, s) if v['u0'] - 1e-6 <= n / 4 + 0.5 <= v['u0'] + v['span'] + 1e-6]
            assert [t for t, _ in got] == [str(n) for n in want], (name, v, s, got)
            for t, x in got:
                assert close(x, PL + (int(t) / 4 + 0.5 - v['u0']) * (PR - PL) / v['span'], 1), (name, v, t, x)
            j = math.ceil(v['u0'] - 1e-3) + 1                      # the first whole column in view, the harness's first(v)
            assert tag[0] == str(COLUMNS[j - 1]) and close(tag[1], PL + (j - 0.5 - v['u0']) * (PR - PL) / v['span'], 1), (name, v, tag)


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


def q_both_charts_share_one_pan_and_zoom():
    # Replicata: index.html: its scripts, the sections of the two charts (mstar and pow2) and its stylesheet (the
    # scripts and the stylesheet files in page/ since 2026-10-31, inline before).
    # Expectata (dreeves's README, 2026-10-30: "[ZOO] For anti-magic/consistency, have the same zoom controls on both
    # charts"): one script, the first after </main>, defines function panZoom, the pan and zoom of both charts,
    # and nothing else; each chart's script calls it once, with its own chart (#mstar-chart, #pow2-chart) and its own
    # buttons; each section holds a div of class zoom with the same three buttons, −, + and ↺, the same but for their
    # ids' prefixes (mstar- and pow2-); one rule styles those buttons, .zoom button (and one their grayed-out look); and
    # each chart takes the keys (tabindex 0).  Which of the two charts each zooms is quals_pow2_page's
    # q_zoom_controls_zoom_their_own_chart; how the m*(n) chart pans and zooms is the browser quals here.
    # Resultata before: only the m*(n) chart could zoom, from code of its own.
    text = page()
    body = text[text.index('</main>'):]
    own = page_scripts(body)
    shared = re.fullmatch(r'(?://[^\n]*\n)*function panZoom\(\{[^\n]*\}\) \{\n.*\n\}\n', own[0], re.S)
    assert shared and sum('function panZoom(' in js for js in own) == 1, own[0][:400]
    for chart, prefix in (('mstar-chart', 'mstar'), ('pow2-chart', 'pow2')):
        [js] = [s for s in own if f"getElementById('{chart}')" in s]
        calls = re.findall(r'panZoom\(\{el: (\w+), out: document\.getElementById\(\'([\w-]+)\'\), in: document\.getElementById\(\'([\w-]+)\'\),\s*'
                           r'reset: document\.getElementById\(\'([\w-]+)\'\)', js)
        assert js.count('panZoom(') == 1 and len(calls) == 1, (chart, calls)
        assert calls[0][1:] == (f'{prefix}-zoom-out', f'{prefix}-zoom-in', f'{prefix}-reset'), (chart, calls)
        assert re.search(rf'\b{calls[0][0]} = document\.getElementById\(\'{chart}\'\)', js), (chart, calls)
    groups = []
    for prefix in ('mstar', 'pow2'):
        sec = re.search(rf'<section class="{prefix}" .*?</section>', text, re.S).group(0)
        [z] = re.findall(r'<div class="zoom">(.*?)</div>', sec, re.S)
        z = ' '.join(re.sub(r'<!--.*?-->', '', z, flags=re.S).split()).replace(f'id="{prefix}-', 'id="')
        assert re.findall(r'<button type="button" id="([\w-]+)"[^>]*>([^<]*)</button>', z) == [
            ('zoom-out', '−'), ('zoom-in', '+'), ('reset', '↺')], (prefix, z)
        groups.append(z)
        assert re.search(rf'<(?:canvas|div) id="{prefix}-chart"[^>]* tabindex="0"', sec), prefix
    assert groups[0] == groups[1], groups
    style = re.sub(r'/\*.*?\*/', '', page_css(), flags=re.S)
    selectors = [s.strip() for sel in re.findall(r'([^{}]+)\{', style) for s in sel.split(',')]
    assert [s for s in selectors if re.search(r'\bbutton\b', s)] == ['.zoom button', '.zoom button:disabled'], selectors


def q_zoom_buttons_zoom_about_the_middle():
    # Replicata: the light run: the zoom buttons at load; a click of each from a view zoomed in 3 steps; then, from the
    # full view, clicks of + until it is disabled and then of − until it is disabled, the view measured after each; and
    # the buttons after every interaction step (keys, wheels, drags, pinches, gestures, reset).
    # Expectata: + zooms in by 1.5 and − out by 1.5 about the middle (the u at the middle stays), as the + and − keys do,
    # stopping at 12 and 257 columns: 8 clicks each way (10 with 512 columns, before 2026-10-29).  + is disabled
    # exactly when the view is 12 columns and − exactly when it is all 257: at load (− only), after every click and after every step (so − after the reset
    # button).  A disabled button is grayed out, not hidden: opacity at most 0.5 but displayed, visible and as big as
    # the other, whose opacity is 1.
    R = valid_run('light')
    assert 'buttonsError' not in R, R['buttonsError']
    S = R['steps']
    for name, f in (('zoomInButton', 1 / 1.5), ('zoomOutButton', 1.5)):
        a, b = S[name]['a'], S[name]['b']
        assert close(b['span'], a['span'] * f, 1e-3) and close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (name, S[name])
    clicks = R['clicks']
    assert [k for k, *_ in clicks] == ['start'] + ['in'] * 8 + ['out'] * 8, [k for k, *_ in clicks]
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
    # when lo = hi and "lo ≤ m*(N) ≤ hi" otherwise; REASONS, joined by " · ": for a green cell (m ≤ lo) one that
    # names order lo, for a red cell (m > hi) one that names order hi + 1, for a gray cell both; and for a cell ringed
    # in gold one more, a note naming order m: a proven one's (a323395_cells, since 2026-10-19) naming a(m − 1) too, a
    # known one's and a not-ruled-out one's (smallest_rings, since 2026-10-30) each the same for every m but for its
    # numbers, and the three notes different.  (Until 2026-10-30 each was pinned as a Claude: "…" string starting
    # "order …", and the gold one as ring_note.)  Every column, n = 2, 4, 8, 12, …, 1024, is read out in both runs.
    for name in ('kinds', 'light'):                                 # light last: its notes are checked after the loop
        R = valid_run(name)
        cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols'] if name == 'kinds' else mstar_data()['cols']
        assert {n for n, _, _ in R['hovers']} == set(COLUMNS), name
        rings, notes = smallest_rings(cols), {}
        for n, m, text in R['hovers']:
            lo, hi = cols[n - 1][:2]
            bounds = f'm*({n}) = {lo}' if lo == hi else f'{lo} ≤ m*({n}) ≤ {hi}'
            note = {1: rf'\border {m}\b', 2: rf'\border {m}\b', 3: rf'\border {m}\b.*{re.escape(f"a({m - 1})")}'}
            reasons = ([rf'\border {lo}\b'] * (m <= hi) + [rf'\border {hi + 1}\b'] * (m > lo)
                       + [note[r] for r in [rings.get((n, m), 0)] if r])
            got = re.fullmatch(r'n = (\d+), m = (\d+) · (.*?) · (.*)', text)
            assert got and (int(got[1]), int(got[2]), got[3]) == (n, m, bounds), (name, n, m, text)
            parts = got[4].split(' · ')
            assert len(parts) == len(reasons) and all(re.search(r, p, re.I) for p, r in zip(parts, reasons)), (name, n, m, text)
            if (n, m) in rings: notes.setdefault(rings[(n, m)], set()).add(re.sub(r'\d+', '#', parts[-1]))
        assert all(len(v) == 1 for v in notes.values()) and len(set.union(*notes.values())) == len(notes), (name, notes)
    assert set(notes) == {1, 2, 3}, notes                           # the light run reads out all three


def q_hover_swatch_matches_gold_trim():
    # Replicata: the light and kinds runs' hover sweeps, sampling the readout swatch after each cell selection.
    # Expectata: every ringed cell (smallest_rings, since 2026-10-30; the 11 proven ones alone before) has a 2 px gold
    # ring on its swatch, and a proven one also a gold dot at its middle (a radial gradient of --record; Claude's
    # proposal, 2026-10-30), every other swatch has neither, and its fill retains the cell's exists/open/impossible
    # color.  The sweeps include both directions of transition between ringed and ordinary cells, so a ring cannot
    # persist after leaving one.
    # Resultata: each assertion reports the hovered cell and its expected and computed CSS values.
    rgb = lambda h: 'rgb(' + ', '.join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5)) + ')'
    assert a323395_cells(mstar_data()['cols']) == PROVEN_CELLS
    for name in ('light', 'kinds'):
        R = valid_run(name)
        cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols'] if name == 'kinds' else mstar_data()['cols']
        rings = smallest_rings(cols)
        swatches = R['swatches']
        assert set(rings) <= {(n, m) for n, m, *_ in swatches}, (name, rings, swatches)
        assert {(False, True), (True, False)} <= {
            (tuple(a[:2]) in rings, tuple(b[:2]) in rings) for a, b in zip(swatches, swatches[1:])}, name
        assert {0, 1, 2} == {(m <= cols[n - 1][0]) + (m <= cols[n - 1][1])
                            for n, m, *_ in swatches if (n, m) not in rings}, name
        shadows = {False: 'none', True: rgb(R['tokens']['record']) + ' 0px 0px 0px 2px'}
        for n, m, fill, shadow, image in swatches:
            lo, hi = cols[n - 1][:2]
            kind = ('impossible', 'open', 'exists')[(m <= lo) + (m <= hi)]
            dot = rings.get((n, m)) == 3
            want = (rgb(R['tokens'][kind]), shadows[(n, m) in rings], dot)
            got = (fill, shadow, image.startswith('radial-gradient(') and rgb(R['tokens']['record']) in image)
            assert got == want and (dot or image == 'none'), (name, n, m, 'expected', want, 'computed', (fill, shadow, image))


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
    # Expectata: zooming in stops at 12 columns and out at all 257; panning stops with n = 1024 at the right edge; the
    # reset button shows all 257 columns, n = 2 to 1024.
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


def q_axes_tag_the_cell_read_out():
    # Replicata: the light and phone runs: the canvas at load; then hovers, each with the draw it makes: in the full
    # view, its four corners (n = 2 and 1024, in rows 1 and T) and a cell in the middle; in a view zoomed in 5 steps and
    # panned right an eighth of it, its corners at the plot's very ends, where its columns are cut (the first's middle
    # out of view, the last's in), a cell in the middle and its first whole column in row 2; then that view panned
    # right by a whole view with the keys alone, the last press's draw.
    # Expectata (dreeves's README, 2026-11-02: "[HOV] When hovering/clicking on cells in the charts it'd be nice to
    # highlight the values of m and n (resp., delta and k) on the axes of the chart"): the cell read out, as the readout
    # names it, is tagged on both axes in paper on ink (the outline's ink), each draw writing nothing else in paper: its
    # m over its row's m label, left of the plot, the ink exactly that row's colored part and reaching past the label's
    # right end, so no other row's label is touched; and its n on the n axis, below the plot, written on its column's
    # middle to within a device px and the ink centered there to within 2, while that middle is in view, as an n
    # label's must be, and no ink there otherwise.  At load, before any cell is read out, nothing is tagged: no ink in
    # either place, nothing written in paper.  Panning with the keys alone keeps the cell read out, as the readout keeps
    # it: its m stays tagged and its n goes with its column's middle.  (quals_pow2_page's q_axes_tag_the_cell_read_out
    # is the same for the chart of powers of 2.)
    # Resultata before: no tags.
    for name in ('light', 'phone'):
        R = valid_run(name)
        (PL, PR), dpr, rows = R['plot'], R['dpr'], R['rows']
        T = len(rows)
        assert R['tags0'] == {'paper': [], 'left': None, 'below': None}, (name, R['tags0'])
        seen = []
        for s in R['tagHovers'] + [R['tagAway']]:
            n, m = map(int, re.match(r'n = (\d+), m = (\d+) · ', s['text']).groups())
            v, j = s['v'], COLUMNS.index(n) + 1
            mid = PL + (j - 0.5 - v['u0']) * (PR - PL) / v['span']
            shown = v['u0'] - 1e-6 <= j - 0.5 <= v['u0'] + v['span'] + 1e-6
            seen.append((n, m, shown))
            top, bottom = rows[T - m]                              # row m's colored part, in device px: [top, bottom)
            ms = [(t, x, y) for t, x, y in s['paper'] if y < R['axisTop']]
            ns = [(t, x, y) for t, x, y in s['paper'] if y >= R['axisTop']]
            assert [t for t, _, _ in ms] == [str(m)] and ms[0][1] < PL and close(ms[0][2], (top + bottom) / 2, 1), (name, n, m, s['paper'])
            assert [t for t, _, _ in ns] == [str(n)] * shown and all(close(x, mid, 1) for _, x, _ in ns), (name, n, m, mid, s['paper'])
            assert s['left'] is not None, (name, n, m, s['left'])
            X0, X1, Y0, Y1 = s['left']
            assert (Y0, Y1 + 1) == (top, bottom) and PL - 7 * dpr <= X1, (name, n, m, s['left'], top, bottom)
            assert (s['below'] is not None) == shown, (name, n, m, shown, s['below'])
            assert not shown or close((s['below'][0] + s['below'][1] + 1) / 2, mid, 2), (name, n, m, mid, s['below'])
        corners = {(2, 1, True), (2, T, True), (COLUMNS[-1], T, True), (COLUMNS[-1], 1, True)}
        assert corners <= set(seen) and {True, False} <= {shown for *_, shown in seen[5:-1]}, (name, seen)
        away = R['tagAway']
        assert away['text'] == away['before'] and not seen[-1][2], (name, away['text'], away['before'], seen[-1])


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
    # an odd n; a column of five entries; hi at mtop; mtop above max hi + 1; nmax not 1024; mtopAt not past nmax, or falling
    # (since 2026-11-04); a row of past not past nmax.
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
# The panels of the charts' columns (dreeves's spec [REO]; Claude's design of 2026-11-03, which dreeves approved: "those
# sound like good precedents. go ahead"): a click or a tap on a cell, or the page's fragment nN, opens under the m*(n)
# chart the full explanation of column n, one template per kind of reason filled with the column's numbers.

def entry_lengths():
    """{n: the id the page's script gives the remarks entry that lists n}: each p.entry's lengths, its TeX's n = ...,
    with 2^{k} as its digits, and the id entry-N, N the first of them."""
    out = {}
    for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', page()):
        lengths = [2 ** int(x[3:-1]) if x.startswith('2^{') else int(x) for x in ns.split(', ')]
        out.update({n: f'entry-{lengths[0]}' for n in lengths})
    return out


def code_ids():
    """The ids N:M of the page's codes."""
    return set(re.findall(r'<code id="(\d+:\d+)">', page()))


def entry_order():
    """The ids of the remarks' entries in the page's order, as the page's script names them (entry-N, N the first length
    each lists): the order of the list, to which every entry a panel showed goes back ([REO] step 2, 2026-11-03)."""
    return [f'entry-{2 ** int(x[3:-1]) if x.startswith("2^{") else int(x)}'
            for x in (ns.split(', ')[0] for ns in re.findall(r'<p class="entry">\\\(n = (.*?)\\\): ', page()))]


def panel_whys(cols, n, rows=()):
    """The kinds of the parts of the box of the m*(n) chart's column n, in order, or of its cell (n, m) for rows [m]
    (box_parts).  Spec change (2026-11-04, dreeves's README items [CEL] and [ROC]): until then the kinds of text of the
    column's one panel, for the cells clicked in rows: a status per cell, its lower bound's reason and, for an example,
    its code where the page shows it, and its upper bound's (and its entry's link, the template "entry", until [REO]
    step 2, 2026-11-03, which moved the entry itself into the panel: panel_entries)."""
    return box_parts(cols, n, *rows)


def panel_entries(n):
    """The ids of the remarks' entries that the panel of the length n shows ([REO] step 2, 2026-11-03): the entry that
    lists n, if any."""
    return [e for e in [entry_lengths().get(n)] if e]


def panel_says(cols, n, P):
    """What the box of the m*(n) chart's column n, P, must say, by its reasons' arguments, as [(what, found)].  Spec change
    (2026-11-04, [CEL]; dreeves: "so many pointless words in the implementation so far"): its bounds as math, each
    leading its part; an example's label; a join's or a product's construction, a button claiming n:lo; each proof's
    numbers; and the copy of the page's code of the length n and the order lo, unless its entry, which the box shows,
    holds that code.  Until then: the sentences of 2026-11-03, each part linked to its own column's panel and an
    example to its code."""
    lo, hi, lw, hw = cols[n - 1]
    t = P['text']
    says = [('heading', P['heading'] == (f'\\(n = {n}\\): \\(m^*({n}) = {lo}\\)' if lo == hi else
                                          f'\\(n = {n}\\): \\({lo} \\le m^*({n}) \\le {hi}\\)')),
            ('lower', f'\\(m^*({n}) \\ge {lo}\\):' in t), ('upper', f'\\(m^*({n}) \\le {hi}\\):' in t)]
    a, b = (lw + [0, 0])[1:3]
    arg, harg = (lw + [None])[1], (hw + [None])[1]                  # the first argument of each reason, if any
    built = lambda tex: [f'{n}:{lo}', 'button', f'\\({tex}\\)'] in P['constructions']
    says += {'example': [('label', f'\\(m^*({n}) \\ge {lo}\\): {arg}' in t)],
             'join': [('construction', built(f'p_{{{a}}} \\vee p_{{{b}}}'))],
             'product': [('construction', built(f'p_{{{a}}} \\mathbin{{\\#}} p_{{{b}}}'))],
             'table2': [('cited', f'\\(m^*({n}) \\ge {lo}\\): BGPW, Table 2' in t)], 'page': [('who', f'found by {arg}' in t)]}[lw[0]]
    t2 = (n & -n).bit_length() - 1
    says += {'two': [('t', f'\\(n = 2^{{{t2}}} \\cdot {n >> t2}\\)' in t and f'\\(m \\le 2^{{{t2}}} - 1 = {hi}\\)' in t)],
             'norm': [('p', f'\\(p = {harg} \\nmid n\\)' in t)],
             'residue': [('M', f'residue condition mod \\(M = {harg}\\)' in t and 'mstar.py' in t)],
             'table2': [('cited', f'\\(m^*({n}) \\le {hi}\\): BGPW, Table 2' in t)], 'page': [('who', f'proven by {harg}' in t)]}[hw[0]]
    copies = [[c, str(lo), 'button', code_digits(c)] for c in [f'{n}:{lo}'] if c in code_ids() and c not in entry_codes(n)]
    says += [('copy', P['copies'] == copies)]
    says += [('entry', P['entries'] == panel_entries(n))]      # the entry itself since [REO] step 2 (2026-11-03), not its link
    return says


def panel_link_lands(href):
    """Whether a panel's link lands: on a column's panel (#nN, N a column of the m*(n) chart), a code (#N:M), an entry
    of the remarks (#entry-N, as the page's script names them) or a page outside (https)."""
    return (href.startswith('https://') or href[1:] in code_ids() or href[1:] in set(entry_lengths().values())
            or re.fullmatch(r'#n(\d+)', href) is not None and int(href[2:]) in COLUMNS)


def q_panel_works_out_the_norm_bound_at_1024():
    # Replicata: the page loaded with the fragment #n1024, which opens the panel of n = 1024; its upper bound is the norm
    # bound for p = 3 (mstar.js: [11, 11, ["example", "equipow p1024"], ["norm", 3]]).
    # Expectata (the coordinator's spec, 2026-11-03: "For n = 1024, p = 3, a qual must find classes 342, 341, 341,
    # 3^12 = 531,441 and the cap 524,289 (= 2^19 + 1), so order 12 fails by 1.4%"): the box gives the class sizes mod
    # 3, 342, 341 and 341, and their squares' sum, 349,526; and at m = 12 the norm's floor 3^12 = 531,441, more than its
    # cap 524,289.
    # Spec change (2026-11-04, [CEL]; dreeves: "so many pointless words in the implementation so far"): the box shows the
    # norm bound's one inequality, p^m <= the cap, with these numbers; until then it also gave both sides of
    # 3^(2m) 2^2 <= (3 sum s_r^2)^2 at m = 12, the same inequality squared, 1,129,718,145,924 = 3^24 * 4 and
    # 1,099,515,822,084 = 1,048,578^2, and that 3^12 exceeds the cap by 1.4%.
    # Resultata before: no panel.
    R = valid_run('fragment')
    t = R['fragment']['text']
    assert 342 ** 2 + 2 * 341 ** 2 == 349526 and 3 * 349526 // 2 == 524289 == 2 ** 19 + 1 and 3 ** 12 == 531441
    for said in ('\\(p = 3 \\nmid n\\)', '= 342, 341, 341 and \\(\\sum s_r^2 =\\) 349,526;',
                 'at \\(m = 12\\), \\(p^m = 3^{12} =\\) 531,441 \\(>\\) 524,289'):
        assert said in t, (said, t)


def q_every_column_s_panel_shows_exactly_its_reasons():
    # Replicata: the panel of each of the m*(n) chart's 257 columns, opened in turn by its fragment, nN (the panels run).
    # Expectata: each opens (not hidden, the fragment its own, the focus on its heading) with no error and no KaTeX
    # error mark; it shows exactly the data's reasons, the kinds of its texts in order (panel_whys: the lower bound's,
    # the code's where the page shows the example's code, the upper bound's; the entry's link where the remarks list n
    # until [REO] step 2, 2026-11-03, which moved the entry itself in); its heading gives n and the bounds; and each
    # text names its reason's arguments (panel_says), with links to the parts' own panels and the example's code, and
    # the entry that lists n shown (q_panel_shows_its_entry_and_gives_it_back).
    # Resultata before: no panel.
    R = valid_run('panels')
    cols = mstar_data()['cols']
    assert [P['n'] for P in R['panels']] == COLUMNS, [P['n'] for P in R['panels']][:5]
    for P in R['panels']:
        n = P['n']
        assert not P['hidden'] and P['hash'] == f'#n{n}' and P['focus'] and P['errors'] == 0, (n, P)
        assert P['whys'] == panel_whys(cols, n), (n, P['whys'], panel_whys(cols, n))
        bad = [what for what, found in panel_says(cols, n, P) if not found]
        assert bad == [], (n, bad, P['text'])
        assert all(panel_link_lands(href) for href in P['links']), (n, P['links'])
    kinds = {w for P in R['panels'] for w in P['whys']}
    # Spec change (2026-11-04, [CEL] and [ROC]): the parts' kinds are a witness's and a proof's; until then the
    # explanations lo-example, lo-code, lo-join, lo-product, hi-two, hi-norm, hi-residue, hi-table2 and hi-page (and
    # 'entry', the link to the remarks' entry, until [REO] step 2, 2026-11-03, when the entry moved into the panel)
    assert {'witness-example', 'witness-construction', 'proof-two', 'proof-norm', 'proof-residue', 'proof-table2',
            'proof-page'} <= kinds <= {*WITNESSES.values(), 'witness-code', 'proof-two', 'proof-norm', 'proof-residue',
                                      'proof-table2', 'proof-page'}, kinds


def q_norm_panels_hold_their_claims():
    # Replicata: the panels run: the panel of each column whose upper bound is the norm bound for a prime p.
    # Expectata: at m = hi + 1, p^m, in digits, is more than the cap, in digits, each the exact integer its formula says
    # (Python's own arithmetic), and so are the class sizes and their squares' sum.  Spec change (2026-11-04, [CEL]): until
    # then also both sides of p^(2m) (p - 1)^(p - 1) <= (p sum s_r^2)^(p - 1), the left more than the right.
    R = valid_run('panels')
    cols = mstar_data()['cols']
    found = 0
    for P in R['panels']:
        n = P['n']
        lo, hi, lw, hw = cols[n - 1]
        if hw[0] != 'norm': continue
        p, m = hw[1], hi + 1
        sizes = [len(range(r, n, p)) for r in range(p)]
        S = sum(x * x for x in sizes)
        cap = (p * S) ** ((p - 1) // 2) // (p - 1) ** ((p - 1) // 2)
        assert p ** m > cap, (n, p, m)
        for said in ('= ' + ', '.join(f'{x:,}' for x in sizes) + ' and', f'\\(\\sum s_r^2 =\\) {S:,};',
                     f'\\(p^m = {p}^{{{m}}} =\\) {p ** m:,} \\(>\\) {cap:,}'):
            assert said in P['text'], (n, said, P['text'])
        found += 1
    assert found == sum(1 for n in COLUMNS if cols[n - 1][3][0] == 'norm') > 10, found


def q_tap_opens_its_cell_s_box():
    # Replicata: the light run's mouse click on a cell of row 1 (R.click), in a view zoomed in 3 steps.
    # Expectata: the box of the clicked cell opens, its fragment nNm1 set and its heading focused, a green cell's (its
    # kind exists), the heading the cell's n and m and the legend's words for its swatch, m <= m*(n); its parts its
    # column's witness alone (panel_whys).
    # Spec change (2026-11-04, [CEL]: "the info box for a cell should focus on that cell"; until then
    # q_tap_opens_its_column_s_panel): the panel of the cell's column opened, its fragment nN, starting with the cell's
    # status: "The cell clicked, order 1, is known".
    R = valid_run('light')
    P, n = R['clickPanel'], R['click']['want'][0]
    assert not P['hidden'] and P['hash'] == f'#n{n}m1' and P['focus'] and P['kind'] == 'exists', P
    assert P['heading'] == f'\\(n = {n}\\), \\(m = 1\\): \\(m \\le m^*(n)\\)', P['heading']
    assert P['whys'] == panel_whys(mstar_data()['cols'], n, [1]), P['whys']


def q_fragment_opens_its_panel_and_focus_comes_back():
    # Replicata: the page loaded with the fragment #n1024; then Escape in the panel's heading; then the fragment #n512;
    # then a click on the panel's close button.
    # Expectata (the design of 2026-11-03: "Loading the page with such a fragment opens that panel"; "On open, focus
    # moves to the panel's heading; close or Escape returns focus to the chart"): the panel of n = 1024 is open at load,
    # its heading focused; Escape hides it, its default prevented, the fragment gone and the focus on the chart; #n512
    # opens 512's panel; its close button hides it, the fragment gone, the focus on the chart.
    R = valid_run('fragment')
    F, E, O, C = R['fragment'], R['escaped'], R['reopened'], R['closed']
    assert not F['hidden'] and F['hash'] == '#n1024' and F['focus'] and F['heading'].startswith('\\(n = 1024\\)'), F
    assert E['hidden'] and E['prevented'] and E['hash'] == '' and E['active'] == 'mstar-chart', E
    assert not O['hidden'] and O['hash'] == '#n512' and O['focus'] and O['heading'].startswith('\\(n = 512\\)'), O
    assert C['hidden'] and C['hash'] == '' and C['active'] == 'mstar-chart', C


def q_panels_fit_a_phone():
    # Replicata: 390 px wide: every column's panel opened in turn (the phone panels run); and the page loaded there
    # with #n1024.
    # Expectata: with each panel open, the page is no wider than the window.
    R = valid_run('phone panels')
    wide = [(P['n'], P['scrollW']) for P in R['panels'] if P['scrollW'] > R['innerW']]
    assert R['innerW'] == 390 and wide == [] and len(R['panels']) == NCOL, wide[:5]
    F = valid_run('phone fragment')
    assert not F['fragment']['hidden'] and F['fragment']['scrollW'] <= 390, F['fragment']
    # and (since 2026-11-04, [CEL] and [ROC]) the boxes of the phone boxes run, each target's box opened by a click there
    B = valid_run('phone boxes')['boxes']
    assert len(B) >= 15 and [(P['target'], P['scrollW']) for P in B if P['hidden'] or P['scrollW'] > 390] == [], [(P['target'], P['scrollW']) for P in B]


def q_made_up_data_opens_every_kind_of_panel():
    # Replicata: made-up data that uses every kind of reason (kinds_data): every column's panel opened in turn.
    # Expectata: no errors; each panel opens and shows exactly its data's reasons; between them they use every kind of
    # lower and upper bound of the data contract (but none and odd, which odd n have, with no column).
    R = valid_run('kinds panels')
    cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols']
    assert len(R['panels']) == NCOL, len(R['panels'])
    for P in R['panels']:
        assert not P['hidden'] and P['errors'] == 0 and P['whys'] == panel_whys(cols, P['n']), (P['n'], P)
    kinds = {w for P in R['panels'] for w in P['whys']}
    # (spec change, 2026-11-04, [CEL]: the parts' kinds are a witness's and a proof's, lo-KIND and hi-KIND until then)
    assert set(WITNESSES.values()) | {f'proof-{k}' for k in ('two', 'norm', 'residue', 'table2', 'page')} <= kinds, kinds


# ---------------------------------------------------------------------------------------------------------------------
# The remarks' entries in the panels ([REO] step 2; dreeves, 2026-11-03: "how can we reduce the redundancy and clutter?
# we want everything to appear in this box -- the box shouldn't ever refer to "remarks below". but also it would be
# nice to be able to grep the page and find everything?", and the main session's design of that day): a column's panel
# shows the remarks' entry of its length, the entry itself moved in, not a copy, and it goes back to its place in the
# list when the panel closes or opens another column; the list, the entries' source text, stays in the page in one
# fold, closed until clicked, which find in page opens; and no entry repeats a sentence of its panel's generated text.

def held(order, *gone):
    """The list's order with the entries gone shown elsewhere."""
    return [e for e in order if e not in gone]


def q_panel_shows_its_entry_and_gives_it_back():
    # Replicata: the fragment runs (1280 and 390 px): the page loaded with #n1024; Escape; #n512; its close button;
    # #n1024 again; the powers-of-2 chart's #k10 (n = 1024 there too); that panel's close button; #n512, then #n1024
    # while it is open; Escape.  And the panels runs: every column's panel by its fragment in turn, then the last closed.
    # Expectata (the design, 2026-11-03: "When a column panel opens, its length's remarks entry ... is moved into the
    # panel, below the generated reasons. It is not cloned ... When the panel closes, or another column's panel opens,
    # the entry goes back to its exact place in the list"; "If an entry lists several lengths (e.g. 320 and 352), it
    # moves into whichever of their panels opens"; "A column with no entry shows its generated reasons only"): each
    # open panel shows exactly the entry that lists its length, if any (panel_entries), and the list holds the others in
    # their order (entry_order); the powers-of-2 chart's panel of 2^10 takes 1024's entry from the m*(n) chart's, which
    # stays open, showing none; once a panel closes or switches, every entry it showed is back in its place, and with
    # both panels closed the list is whole, in order.
    # Resultata before: panels linked their entries ("Its entry in the remarks below"), which stayed in the list.
    order = entry_order()
    assert len(order) == len(set(order)) > 70 and 'entry-1024' in order and 'entry-512' in order, order
    for name in ('fragment', 'phone fragment'):
        R = valid_run(name)
        steps = [('fragment', R['fragment'], ['entry-1024']), ('escaped', R['escaped'], []), ('reopened', R['reopened'], ['entry-512']),
                 ('closed', R['closed'], []), ('again', R['again'], ['entry-1024']),
                 ('crossed mstar', R['crossed']['mstar'], []), ('crossed pow2', R['crossed']['pow2'], ['entry-1024']),
                 ('crossClosed mstar', R['crossClosed']['mstar'], []), ('crossClosed pow2', R['crossClosed']['pow2'], []),
                 ('switched', R['switched'], ['entry-1024']), ('allClosed', R['allClosed']['mstar'], [])]
        for step, P, want in steps:
            assert P['entries'] == want, (name, step, P['entries'], want)
        shown = {'fragment': ['entry-1024'], 'escaped': [], 'reopened': ['entry-512'], 'closed': [], 'again': ['entry-1024'],
                 'crossed mstar': ['entry-1024'], 'crossed pow2': ['entry-1024'], 'crossClosed mstar': [], 'crossClosed pow2': [],
                 'switched': ['entry-1024'], 'allClosed': []}
        for step, P, _ in steps:
            assert P['listed'] == held(order, *shown[step]), (name, step, sorted(set(order) ^ set(P['listed'])))
        assert not R['crossed']['mstar']['hidden'] and not R['crossed']['pow2']['hidden'], R['crossed']
        assert R['crossClosed']['pow2']['hidden'] and not R['crossClosed']['mstar']['hidden'], R['crossClosed']
        assert R['allClosed']['mstar']['hidden'] and R['allClosed']['pow2']['hidden'], R['allClosed']
    for name in ('panels', 'phone panels'):
        R = valid_run(name)
        for P in R['panels']:
            assert P['entries'] == panel_entries(P['n']) and P['listed'] == held(order, *P['entries']), (name, P['n'], P['entries'])
        assert R['after']['hidden'] and R['after']['entries'] == [] and R['after']['listed'] == order, (name, R['after']['entries'])
    assert {P['n'] for P in valid_run('panels')['panels'] if P['entries']} >= {320, 352, 416, 512, 1024}


def q_entry_ids_stay_unique_and_codes_expand_in_a_panel():
    # Replicata: the fragment runs: 1024's panel opened by its fragment, a click on its code there, 1024:11, then the
    # powers-of-2 chart's panel of 2^10, which takes the entry, then both closed; and the panels runs, each column's
    # panel in turn.
    # Expectata (the design, 2026-11-03: "It is not cloned: the entry holds ids (codes' N:M ids) that must stay unique,
    # and codes.js's expanders must keep working"): no id is on two elements of the page at any step; the click expands
    # the code in the panel (aria-expanded true), its box right there, shown, inside the entry: the power sums for k = 0
    # to 11, equal below 11 and unequal at 11; the box moves with the entry into the other panel, still shown, and back
    # into the list with it.
    # Resultata before: the code was in the list, and its box opened there, outside the panel.
    for name in ('fragment', 'phone fragment'):
        R = valid_run(name)
        reports = [R[k] for k in ('fragment', 'escaped', 'reopened', 'closed', 'again', 'switched')] + [
            R[k][c] for k in ('crossed', 'crossClosed', 'allClosed') for c in ('mstar', 'pow2')]
        assert all(P['dups'] == [] for P in reports), (name, [P['dups'] for P in reports])
        want = {'expanded': 'true', 'inEntry': True, 'ks': [str(k) for k in range(12)], 'relations': ['='] * 11 + ['≠']}
        for step, at in (('expanded', {'inMstar': True, 'inPow2': False, 'shown': True}),
                         ('crossed', {'inMstar': False, 'inPow2': True, 'shown': True}),
                         ('allClosed', {'inMstar': False, 'inPow2': False})):
            B = R[step] if step == 'expanded' else R[step]['box']
            assert {k: B[k] for k in [*want, *at]} == want | at, (name, step, B)
    for name in ('panels', 'phone panels'):
        assert all(P['dups'] == [] for P in valid_run(name)['panels']), name


def q_no_panel_mentions_the_remarks_below():
    # Replicata: the panels runs, every column's panel of the m*(n) chart, its generated text and the entry it shows;
    # and the panel templates of index.html.
    # Expectata (dreeves, 2026-11-03: "we want everything to appear in this box -- the box shouldn't ever refer to
    # "remarks below""): no panel's text says "remarks below", and no template says it; the template "entry" ("Its
    # entry in the remarks below") is gone.
    # Resultata before: every panel of a length with an entry ended "Its entry in the remarks below: ...".
    for name in ('panels', 'phone panels'):
        said = [P['n'] for P in valid_run(name)['panels'] if 'remarks below' in ' '.join([P['text'], *P['entryText']])]
        assert said == [], (name, said[:10])
    # (spec change, 2026-11-04, [CEL]: the boxes' 14 templates, some marked data-claude, in place of 2026-11-03's 16)
    templates = re.findall(r'<template data-panel="([^"]+)"[^>]*>(.*?)</template>', page(), re.S)
    assert len(templates) >= 14 and 'entry' not in {t for t, _ in templates}, [t for t, _ in templates]
    assert not [t for t, body in templates if 'remarks below' in body], [t for t, body in templates if 'remarks below' in body]


def remarks_fold():
    """The remarks section's fold, from index.html: (the section's text before it, its summary's text, the text it
    holds after the summary, the section's text after it), asserting it is one <details> without open whose first
    element is a <summary> (comments may come before it: its TODO recap)."""
    section = re.search(r'<section class="remarks">(.*?)</section>', page(), re.S)[1]
    folds = re.findall(r'<details([^>]*)>\s*(?:<!--.*?-->\s*)*<summary>(.*?)</summary>(.*?)</details>', section, re.S)
    assert len(folds) == 1 == section.count('<details') and 'open' not in folds[0][0], folds and folds[0][0]
    before, after = section.split('<details', 1)[0], section.split('</details>', 1)[1]
    return before, folds[0][1], folds[0][2], after


def q_remarks_list_folds_closed_under_its_summary():
    # Replicata: index.html's section "Where the new results come from"; and the light run, as the page loads.
    # Expectata (the design, 2026-11-03: "The remarks list ... stays in the HTML exactly as written, as the source text.
    # Fold it into one closed <details> with a summary line ... styled like the Search progress section's folds";
    # "Keep the section's introduction (the paragraphs that explain the upper-bound methods: the residue condition and
    # the norm bound) visible above the fold"; "Without JavaScript the page reads as before, with the list foldable"):
    # the list of entries, every <p class="entry"> of the page with it, is in one <details> without open, after its
    # <summary>, which has words; the paragraphs on how the upper bounds are proven and on the norm bound come before it,
    # outside (the panels' templates cite them by those words); nothing but the closing of the section follows it.  As
    # the page loads the fold is closed, its summary shown
    # and its list not.  A summary is a pointer in the stylesheet, as the Search progress section's are.
    # Resultata before: the list stood open, with no fold.
    before, summary, inside, after = remarks_fold()
    assert re.sub(r'<[^>]+>|\s+', ' ', summary).strip(), summary
    assert re.fullmatch(r'\s*<ul>\n.*\n  </ul>\s*', inside, re.S) and inside.count('<p class="entry">') == page().count('<p class="entry">'), inside[:300]
    assert 'How the upper bounds are proven.' in before and 'The norm bound for a prime' in before, before[:300]
    assert after.strip() == '', after
    assert '.remarks summary { cursor: pointer; }' in page_css(), 'no pointer on the summary'
    assert valid_run('light')['fold'] == {'there': True, 'open': False, 'summary': True, 'list': False}, valid_run('light')['fold']


def panel_reasons(n, cols, pcols):
    """[lo, hi, loWhy, hiWhy] of each panel that shows the length n, by the columns cols of mstar.js and pcols of
    pow2.js: the m*(n) chart's column n, if it has one, and the powers-of-2 chart's column k for n = 2^k, its hiWhy
    ["mstar", why] read as why."""
    k = n.bit_length() - 1
    return ([cols[n - 1] for _ in [0] if n in COLUMNS]
            + [[lo, hi, lw, hw[1] if hw[0] == 'mstar' else hw] for lo, hi, lw, hw in pcols[k - 1:k] if n == 2 ** k])


def repeated_reasons(reasons, n):
    """The sentences that would repeat, in a panel of the length n with the reasons [lo, hi, loWhy, hiWhy], what its
    generated text states, in the forms the remarks used for them, as regexes over an entry's HTML: the upper bound's
    reason, the residue condition mod M (a chain's last modulus) or the norm bound for the residue sums mod p, as the
    entries of the m*(n) chart's lengths said it and as those of the powers of 2 did ("as in the powers-of-2 chart
    above"); Thue–Morse's order, where Thue–Morse is the lower bound's reason; and a doubling with the upper bound's
    reason, where those are the panel's two reasons."""
    lo, hi, lw, hw = reasons
    M = hw[1][-1] if isinstance((hw + [None])[1], list) else (hw + [None])[1]
    said = {'residue': f'the residue condition mod {M}', 'norm': f'the norm bound for the residue sums mod {M}'}.get(hw[0])
    forms = ([rf'Order {hi + 1} is ruled out by {said}\.', rf'The upper bound is {said}, as in the powers-of-2 chart above\.'] * bool(said)
             + [rf'The Thue–Morse polynomial \\\(\\tau_\{{?{lo}\}}?\\\) has order {lo}\.'] * (lw in (['thue-morse'], ['example', 'Thue–Morse']))
             + [rf'Order {lo} from examples above, doubled \(\\\({n} = 2\\cdot {lw[-1]}\\\)\); order {hi + 1} is ruled out by {said}\.']
             * (lw[:2] == ['product', 2] and bool(said)))
    return [re.compile(f) for f in forms]


def entry_lis():
    """[(the lengths it lists, its HTML with comments blanked)] for each entry, an li of the remarks' list, in page
    order."""
    section = blank_comments(re.search(r'<section class="remarks">(.*?)</section>', page(), re.S)[1])
    lis = re.findall(r'<li[ >].*?</li>', section, re.S)
    lengths = [re.search(r'<p class="entry">\\\(n = (.*?)\\\): ', li)[1].split(', ') for li in lis]
    return [([2 ** int(x[3:-1]) if x.startswith('2^{') else int(x) for x in ns], li) for ns, li in zip(lengths, lis)]


def q_no_entry_repeats_its_panel_s_reasons():
    # Replicata: each entry of the remarks' list and, for each length it lists, the reasons of every panel that shows
    # that length (panel_reasons: the m*(n) chart's column, and the powers-of-2 chart's at a power of 2).
    # Expectata (the design, 2026-11-03: "No sentence shown twice. Delete from the entries each sentence that a
    # generated reason now states with the same content, for example "Order 12 is ruled out by the norm bound for the
    # residue sums mod 3." and "Order 13 is ruled out by the residue condition mod 5." Keep everything the templates do
    # not say: provenance, credit ..., history, methods, links and codes"; "Delete them only where the generated text
    # says exactly the same thing"): no entry has a sentence in the forms that state one of those panels' reasons
    # (repeated_reasons), which the panel's generated text states; a sentence that says more (a credit, a chain of
    # moduli, several lengths' reasons) is not in those forms.  The forms catch sentences of the entries as they stood
    # (controls).
    # Resultata before: 544's entry said "Order 11 is ruled out by the norm bound for the residue sums mod 3.", as its
    # panel's norm bound worked out does, and so did 63 other sentences, one in each of 63 other entries.
    reasons, cols, pcols = {}, mstar_data()['cols'], pow2_data()['cols']
    lis = entry_lis()
    assert len(lis) == len(entry_order()), len(lis)
    found = []
    for lengths, li in lis:
        for n in lengths:
            reasons.setdefault(n, panel_reasons(n, cols, pcols))
            found += [(n, f.pattern) for r in reasons[n] for f in repeated_reasons(r, n) if f.search(li)]
    assert found == [], (len(found), found[:8])
    assert all(reasons[n] for n in reasons), [n for n in reasons if not reasons[n]]
    controls = {544: 'Claude: “A symmetric example of order 10, found by a lattice search. Order 11 is ruled out by the norm bound for the residue sums mod 3.”',
                864: 'Order 12 from examples above, doubled (\\(864 = 2\\cdot 432\\)); order 15 is ruled out by the residue condition mod 5.',
                512: 'The Thue–Morse polynomial \\(\\tau_9\\) has order 9.',
                2 ** 30: 'That beats Thue–Morse by 3. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above.'}
    for n, said in controls.items():      # sentences of the entries as they stood, which the forms must catch
        assert [n for r in panel_reasons(n, cols, pcols) for f in repeated_reasons(r, n) if f.search(said)], (n, said)


def q_find_in_page_opens_the_fold():
    # Replicata: index.html loaded on its own (not in the harness's frame) with the text fragment #:~:text=Berend and
    # Golan, words of 432's entry, and then with the fragment #lemma432, an element of that entry, in the closed fold.
    # Expectata (the design, 2026-11-03: "Browser find-in-page opens a closed <details> on a match; check that the find
    # still works"): Chrome opens the fold to show the match, as the HTML standard's ancestor revealing algorithm has
    # it for find in page, text fragments and fragments: each load ends with the fold open and the entry's lemma shown.
    # (Chrome's find bar has no headless form; a text fragment is Chrome's other text search that reveals what it finds.
    # window.find finds the words in the fold but opens nothing: scratch/reo-step2-20261103/findprobe/.)
    # Resultata before: no fold.
    for frag in ('#:~:text=Berend%20and%20Golan', '#lemma432'):
        d = tempfile.mkdtemp(prefix='index-quals-')
        probe = ('<script>addEventListener("load", () => setTimeout(() => { const f = document.querySelector("section.remarks details"),'
                 ' t = document.getElementById("lemma432"); document.documentElement.dataset.fold = JSON.stringify({there: f !== null,'
                 ' open: f?.open ?? null, shown: t.checkVisibility()}); }, 1500));</script>')
        text = page()
        assert text.count('</body>') == 1
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text.replace('</body>', probe + '</body>'))
        copy_page_dir(d)
        shutil.copy(DATA, os.path.join(d, 'mstar.js'))
        shutil.copy(POW2, os.path.join(d, 'pow2.js'))
        dom = chrome(d, ['--window-size=1280,1000', '--virtual-time-budget=10000', '--dump-dom', 'file://' + os.path.join(d, 'index.html') + frag])
        shutil.rmtree(d)
        m = re.search(r'<html[^>]* data-fold="([^"]*)"', dom)
        assert m, (frag, dom[:300])
        assert json.loads(html.unescape(m[1])) == {'there': True, 'open': True, 'shown': True}, (frag, m[1])


# ---------------------------------------------------------------------------------------------------------------------
# The boxes of the charts' cells, columns and rows (dreeves's README, 2026-11-03: "[CEL] For the info box you see when
# clicking a cell, color-code it to match the cell. And the info box for a cell should focus on that cell. If the cell
# is green, just give the partition (expandable hex code) for the highest green cell in that cell's column. If the cell
# is red, show the proof for the lowest red cell in that cell's column. If the cell is black... maybe just summarize the
# search efforts so far?", and "[ROC] Only if it's straightforward and if it makes sense and isn't a nighmare to make it
# anti-magic and DRY: in addition to clicking individual cells, allow clicking the column number or the row number";
# in chat: "so many pointless words in the implementation so far ... think through what the user will want to see and
# making the correspondence between the clicked cell and the info box visually obvious"; the main session's design of
# 2026-11-04): a click on a cell of the m*(n) chart, on the strip of its n labels or on the strip of its m labels opens,
# under the chart, the box of that cell, column or row (the boxes runs, the harness's boxes).

WITNESSES = {'example': 'witness-example', 'join': 'witness-construction', 'product': 'witness-construction',
             'table2': 'witness-table2', 'page': 'witness-page'}    # a box's part of a lower bound, by its reason's kind
SHOWS = {'exists': (True, False), 'open': (True, True), 'impossible': (False, True), None: (True, True)}   # (witness, proof),
# by the kind of cell of a box, None for a column's
BOX_WORDS = 24    # a cell's box's words of Claude's English, at most (q_cell_box_words_stay_within_budget)
# The boxes' templates of Claude's English (dreeves, 2026-11-04: "we don't need claude attribution for blurbs without
# words like these"): the others hold math, codes, the data's labels and citations alone
CLAUDE_TEMPLATES = {'witness-page', 'witness-thue-morse', 'proof-two', 'proof-norm', 'proof-residue', 'proof-page'}


def entry_codes(n):
    """The ids of the codes that the remarks' entry that lists the length n holds (none if no entry lists n)."""
    return {c for lengths, li in entry_lis() if n in lengths for c in re.findall(r'<code id="(\d+:\d+)">', li)}


def code_digits(id_):
    """The hex digits of the page's code of the id N:M."""
    return re.search(rf'<code id="{id_}">([0-9A-F]+)</code>', page()).group(1)


def kind_of(cols, n, m):
    """The kind of the m*(n) chart's cell (n, m): exists, open or impossible."""
    lo, hi = cols[n - 1][:2]
    return 'exists' if m <= lo else 'open' if m <= hi else 'impossible'


def box_parts(cols, n, m=None):
    """The kinds of the parts of the box of the m*(n) chart's cell (n, m), or of its column n's (m None), in order (since
    2026-11-04): of its column's lower bound, its witness (WITNESSES, then a copy of the page's code of the length n and
    the order lo, where the page has one: witness-code), for a green cell, a black one and a column; of its upper bound,
    its proof (proof-KIND), for a red cell, a black one and a column; and a black cell's searches.  A copy goes where the
    box shows the code itself, in the entry that lists n, which a column's box shows, and a cell's whose bound shown is
    one of the page's own (page)."""
    lo, hi, lw, hw = cols[n - 1]
    kind = None if m is None else kind_of(cols, n, m)
    witness, proof = SHOWS[kind]
    entry = kind is None or (witness and lw[0] == 'page') or (proof and hw[0] == 'page')
    copy = f'{n}:{lo}' in code_ids() and not (entry and f'{n}:{lo}' in entry_codes(n))
    return ([WITNESSES[lw[0]]] + ['witness-code'] * copy) * witness + [f'proof-{hw[0]}'] * proof + ['searches'] * (kind == 'open')


def words(text):
    """The words of a box's text outside its math, its codes and its numbers: its runs of letters."""
    return re.findall(r'[A-Za-z]+', re.sub(r'[0-9A-F]{16,}', ' ', re.sub(r'\\\(.*?\\\)', ' ', text)))


def boxes_run(name='boxes'):
    """The boxes run (or another configuration's), with each box's report by its target, as a tuple."""
    R = valid_run(name)
    return R, {tuple(B['target']): B for B in R['boxes']}


def q_cell_box_takes_its_cell_s_color():
    # Replicata: the boxes run (1280 px): a click on each cell of BOX_TARGETS in the m*(n) chart's full view, the pointer
    # then moved off to cell (4, 1); and on the strip of the n labels under column 1024, and on the strip of the m labels
    # left of rows 12, 13 and 16.
    # Expectata ([CEL]: "color-code it to match the cell"; the design of 2026-11-04: "the box's frame or header band in
    # the clicked cell's own color (use the charts' own CSS tokens, not new colors), with a swatch identical to the cell
    # (gold ring included when the cell is ringed)"): each cell's box open, its fragment nNmM, its kind the cell's, its
    # frame the very color of the cell's pixels, its heading led by a swatch of that color, ringed in gold where the
    # cell is ringed (record), and dotted where it is proven the least of its order (proven, a(m − 1)), the swatch of the
    # legend's item whose words follow it; a column's and a row's box framed in ink, its heading without a swatch.
    # Resultata before: each click on a cell opened its column's panel, in a frame of ink whatever the cell, with no
    # swatch; a click on a strip opened nothing.
    R, B = boxes_run()
    cols, rings = mstar_data()['cols'], smallest_rings(mstar_data()['cols'])
    cells = [t for t in B if None not in t]
    assert len(cells) >= 10, cells
    for n, m in cells:
        P, kind, role = B[(n, m)], kind_of(cols, n, m), rings.get((n, m), 0)
        assert not P['hidden'] and P['hash'] == f'#n{n}m{m}' and P['kind'] == kind, (n, m, P['hidden'], P['hash'], P['kind'])
        assert P['own'] == R['tokens'][kind] and P['frame'] == P['own'] and P['swatch']['color'] == P['own'], (n, m, P['own'], P['frame'], P['swatch'])
        assert P['swatch']['cls'] == f"swatch {kind}{['', ' record', ' record', ' record proven'][role]}", (n, m, P['swatch'])
        assert (P['swatch']['ring'] != 'none') == (role > 0), (n, m, P['swatch'])
    assert {rings.get(t, 0) for t in cells} == {0, 1, 2, 3}, 'not every role of ring among the cells clicked'
    for t in [t for t in B if None in t]:
        P = B[t]
        assert not P['hidden'] and P['kind'] == ('row' if t[0] is None else 'column') and P['frame'] == R['tokens']['rule'], (t, P['kind'], P['frame'])
        assert P['swatch'] is None, (t, P['swatch'])


def q_box_outline_stays_while_open_and_goes_with_it():
    # Replicata: the boxes run: each target's box opened by its click, then the pointer moved off to cell (4, 1), so that
    # the cell read out, outlined in ink, is elsewhere; and the box of cell (528, 12), opened again, then closed by its
    # button.
    # Expectata (the design of 2026-11-04: "the clicked cell keeps an outline while its box is open ... Column box: the
    # column is outlined; row box: the row"): while a box is open, the chart's pixels just outside its target are ink: a
    # cell's left and right of it in its row, a column's left of it in rows 1 and 16, a row's above it at the plot's
    # middle and a quarter of the way in; once the box is closed, none of them is.
    # Resultata before: only the cell read out was outlined, so with the pointer off at (4, 1) no target was.
    R, B = boxes_run()
    ink = R['tokens']['ink']
    bad = [(t, P['outline']) for t, P in B.items() if P['outline'] != [ink, ink]]
    assert bad == [], bad
    assert R['closed']['hidden'] and ink not in R['closed']['outline'], R['closed']


def q_box_caret_points_at_its_target():
    # Replicata: the boxes run, each target's box.
    # Expectata (the design of 2026-11-04: "a caret on the box's top edge at the clicked column's x (clamped)"): the
    # middle of the caret on the box's top edge (its ::before, a triangle) within 2 CSS px of the middle of the target's
    # column, for a cell's box and a column's, or of the strip of the m labels, for a row's.
    # Resultata before: no caret.
    R, B = boxes_run()
    bad = [(t, P['caret'], P['column']) for t, P in B.items() if P['caret'] is None or abs(P['caret'] - P['column']) > 2]   # None: no caret
    assert bad == [], bad


def q_green_box_gives_the_witness_and_its_code():
    # Replicata: the boxes run: the boxes of the green cells (1024, 8), (672, 13), (480, 12), (36, 2) and (80, 3); then the
    # box of (1024, 8) again and a click on its code, and the box of (36, 2) and a click on its construction.
    # Expectata ([CEL]: "If the cell is green, just give the partition (expandable hex code) for the highest green cell
    # in that cell's column"): each shows its column's witness alone (box_parts), led by the bound m*(n) >= lo; an
    # example's with its label and a copy of the page's code of length n and order lo (data-join its id, data-order lo),
    # a button with the code's digits, which, clicked, opens in the box the code's partition, its power sums for k = 0
    # to 11, equal below 11 and unequal at 11; a join's or a product's with its construction, a button claiming n:lo,
    # whose derivation, clicked, opens in the box: p_8 and p_28, then the join of length 36 and order 3.
    # Resultata before: a click opened the column's panel: the cell's status, both bounds' sentences, and a link to the
    # code, in the list below.
    R, B = boxes_run()
    cols = mstar_data()['cols']
    for t in ((1024, 8), (672, 13), (480, 12), (36, 2), (80, 3)):
        n, m = t
        P, (lo, hi, lw, hw) = B[t], cols[n - 1]
        assert kind_of(cols, n, m) == 'exists' and P['whys'] == box_parts(cols, n, m), (t, P['whys'], box_parts(cols, n, m))
        assert P['said'].startswith(f'\\(m^*({n}) \\ge {lo}\\):') and 'Claude' not in P['said'], (t, P['said'])   # no English to attribute
        copies = [[c, str(lo), 'button', code_digits(c)] for c in [f'{n}:{lo}'] if c in code_ids()]
        assert P['copies'] == copies, (t, P['copies'])
    assert B[(1024, 8)]['said'].startswith('\\(m^*(1024) \\ge 11\\): equipow p1024'), B[(1024, 8)]['said']
    assert R['expanded'] == {'expanded': 'true', 'inBox': True, 'shown': True, 'ks': [str(k) for k in range(12)],
                             'relations': ['='] * 11 + ['≠']}, R['expanded']
    assert B[(36, 2)]['constructions'] == [['36:3', 'button', '\\(p_{8} \\vee p_{28}\\)']], B[(36, 2)]['constructions']
    assert B[(80, 3)]['constructions'] == [['80:6', 'button', '\\(p_{2} \\mathbin{\\#} p_{40}\\)']], B[(80, 3)]['constructions']
    assert R['derived'] == {'expanded': 'true', 'inBox': True, 'shown': True, 'rows': [['8', '3'], ['28', '3'], ['36', '3']],
                            'bound': 'm*(36) ≥ 3'}, R['derived']


def q_red_box_works_out_the_proof():
    # Replicata: the boxes run: the boxes of the red cells (1024, 12), a norm bound for p = 3; (1020, 4), the 2-adic
    # bound; (56, 6), BGPW's Table 2; and (240, 11), a proof of the page's own.
    # Expectata ([CEL]: "If the cell is red, show the proof for the lowest red cell in that cell's column"): each shows
    # its column's proof alone (box_parts), its bound m*(n) <= hi, worked out with n's numbers: for 1024, p = 3, the
    # class sizes 342, 341 and 341 and their squares' sum 349,526, and at m = 12, p^m = 3^12 = 531,441, more than the
    # floor 524,289; for 1020 = 2^2 * 255, m <= 2^2 - 1 = 3, with BGPW's Theorem 4.1 linked; for 56, BGPW's Table 2,
    # linked; for 240, who proved it, and the remarks' entry of 240 shown in the box, which holds the proof; no witness
    # and no searches.
    # Resultata before: the column's panel, its status sentence, both bounds' sentences and the norm bound's paragraph
    # "below".
    R, B = boxes_run()
    cols = mstar_data()['cols']
    for t, quote in (((1024, 12), 'Claude: “'), ((1020, 4), 'Claude: “'), ((56, 6), ''), ((240, 11), 'Claude: “')):   # BGPW's, cited, no English
        assert kind_of(cols, *t) == 'impossible' and B[t]['whys'] == box_parts(cols, *t), (t, B[t]['whys'])
        assert B[t]['said'].startswith(f'{quote}\\(m^*({t[0]}) \\le {cols[t[0] - 1][1]}\\):'), (t, B[t]['said'])
    assert 3 ** 12 == 531441 > 3 * (342 ** 2 + 2 * 341 ** 2) // 2 == 524289 and 342 ** 2 + 2 * 341 ** 2 == 349526
    for said in ('\\(p = 3 \\nmid n\\)', '= 342, 341, 341 and \\(\\sum s_r^2 =\\) 349,526;',
                 'at \\(m = 12\\), \\(p^m = 3^{12} =\\) 531,441 \\(>\\) 524,289'):
        assert said in B[(1024, 12)]['said'], (said, B[(1024, 12)]['said'])
    assert '\\(n = 2^{2} \\cdot 255\\)' in B[(1020, 4)]['said'] and '\\(m \\le 2^{2} - 1 = 3\\)' in B[(1020, 4)]['said'], B[(1020, 4)]['said']
    assert 'https://arxiv.org/html/1912.03491v1#S4.Thmthm1' in B[(1020, 4)]['links'], B[(1020, 4)]['links']
    assert 'BGPW, Table 2' in B[(56, 6)]['said'] and 'https://arxiv.org/html/1912.03491v1#S3.T2' in B[(56, 6)]['links'], B[(56, 6)]
    assert 'proven by Claude alone' in B[(240, 11)]['said'] and B[(240, 11)]['entries'] == ['entry-240'], B[(240, 11)]
    assert all(B[t]['entries'] == [] for t in ((1024, 12), (1020, 4), (56, 6))), [B[t]['entries'] for t in B]


def q_black_box_shows_both_bounds_and_the_searches():
    # Replicata: the boxes run, with BOX_PROGRESS as progress.js: two runs at 528:12, PROGRESS_CHANCE, a tracked search
    # that a campaign runs, with its chance, and an overnight_v5.py run, aborted; and one at 64:7.  The box of the black
    # cell (528, 12), once its searches had loaded (searched); and the boxes of the black cells (480, 13).
    # Expectata ([CEL]: "If the cell is black... maybe just summarize the search efforts so far?"; the design of
    # 2026-11-04: "the two bracketing facts in compact form (the order-lo witness, the order hi + 1 proof), plus the
    # search efforts"): each shows its column's witness and proof (box_parts) and then its searches: the heading of the
    # Search progress section, and below it each run of that section at the cell's n and m, its question, program and
    # state as that section's fold names them, with its time so far, and for the campaign its chance line as that
    # section states it (within 6 h 0.91%, within 24 h 2.8%, 2.1 CPU-hours); nothing of 64:7; for (480, 13), with no run,
    # a dash.
    # Resultata before: the column's panel, with its status sentence and no searches.
    R, B = boxes_run()
    cols = mstar_data()['cols']
    S = R['searched']
    assert S['whys'] == box_parts(cols, 528, 12) == ['witness-example', 'witness-code', 'proof-residue', 'searches'], S['whys']
    assert S['said'].startswith('\\(m^*(528) \\ge 11\\): equipow p528') and S['said'].endswith('finds none”'), S['said']
    assert 'Claude: “\\(m^*(528) \\le 12\\): residue condition mod \\(M = 5\\)' in S['said'], S['said']
    flat = lambda t: ' '.join(t.split())                         # its spaces, the narrow no-break ones before a unit among them, as one
    assert [flat(t) for t in S['searches']] == ['Search progress m*(528) ≥ 12? probe_seed.py running 0.2 h Probability of finding a '
                                                'bipartition within 6 h: 0.91%; within 24 h: 2.8%; 2.1 CPU-hours so far. m*(528) ≥ 12? '
                                                'overnight_v5.py aborted 2.0 h'], S['searches']
    assert B[(480, 13)]['whys'] == box_parts(cols, 480, 13) and [flat(t) for t in B[(480, 13)]['searches']] == ['Search progress —'], B[(480, 13)]


def q_column_box_opens_from_its_n_label():
    # Replicata: the boxes run: a click on the strip of the n labels under column 1024, 10 CSS px below the plot.
    # Expectata ([ROC]: "allow clicking the column number ... For a column, the info box would explain the known bounds
    # for that value of n -- both the witness for the highest green cell in the column and the proof for the lowest red
    # cell"): the box of the column opens, its fragment n1024, its heading n and m*(1024) = 11, its parts the witness and
    # the proof (box_parts: no copy of 1024:11, whose own code its entry shows) and the remarks' entry of 1024.
    # Resultata before: nothing opened.
    R, B = boxes_run()
    P = B[(1024, None)]
    assert not P['hidden'] and P['hash'] == '#n1024' and P['focus'] and P['kind'] == 'column', P
    assert P['heading'] == '\\(n = 1024\\): \\(m^*(1024) = 11\\)' and P['whys'] == box_parts(mstar_data()['cols'], 1024), (P['heading'], P['whys'])
    assert P['entries'] == ['entry-1024'] and P['copies'] == [], (P['entries'], P['copies'])


def q_row_box_is_its_row_of_the_smallest_lengths():
    # Replicata: the boxes run: clicks on the strip of the m labels, left of the plot, at rows 12, 13 and 16; and the
    # page's own table of smallest lengths as drawn.
    # Expectata ([ROC]: "For a row, it would be like a row in [the table of smallest lengths], giving the smallest n not
    # ruled out and the smallest known n, mention the A323395 sequence"): the box of the row opens, its fragment mM,
    # its heading m = M; its one part a table, that table's head and its row for the order M, as the page's table
    # has them, and the term a(M − 1) of OEIS A323395, linked, the order's smallest length: a(11) = 480, proven; 480 <=
    # a(12) <= 672; a(15) = 1440, proven.
    # Resultata before: nothing opened.
    R, B = boxes_run()
    table = R['table3']
    for m, term in ((12, '\\(a(11) = 480\\)'), (13, '\\(480 \\le a(12) \\le 672\\)'), (16, '\\(a(15) = 1440\\)')):
        P = B[(None, m)]
        assert not P['hidden'] and P['hash'] == f'#m{m}' and P['kind'] == 'row' and P['heading'] == f'\\(m = {m}\\)', (m, P)
        assert P['whys'] == ['row-smallest'] and P['tables'] == [[table[0], table[m]]], (m, P['tables'], table[0], table[m])
        assert P['links'] == ['https://oeis.org/A323395'] and P['text'].endswith(f'OEIS A323395: {term}'), (m, P['links'], P['text'])


def q_box_fragments_name_cells_and_rows():
    # Replicata: the page loaded with the fragment #n1024m12 (the box fragment run); and, in the boxes run, the fragment
    # set to #m16 and then to #n1024m12.
    # Expectata (the design of 2026-11-04, as of 2026-11-03 for a column's: every box has a fragment, which opens it as
    # the page loads or moves to it): the box of cell (1024, 12) open at load, its heading focused, red, its proof; the
    # box of row 16 after #m16; the box of cell (1024, 12) again after #n1024m12.
    # Resultata before: only a column's fragment opened anything.
    F = valid_run('box fragment')['atLoad']
    assert not F['hidden'] and F['hash'] == '#n1024m12' and F['focus'] and F['kind'] == 'impossible' and F['whys'] == ['proof-norm'], F
    R, _ = boxes_run()
    row, cell = R['hashed']
    assert not row['hidden'] and row['kind'] == 'row' and row['heading'] == '\\(m = 16\\)', row
    assert not cell['hidden'] and cell['kind'] == 'impossible' and cell['whys'] == ['proof-norm'] and cell['hash'] == '#n1024m12', cell


def q_boxes_say_nothing_about_elsewhere():
    # Replicata: the boxes' templates in index.html, and the parts of Claude's words in every box of the boxes run and
    # in every column's box of the panels run.
    # Expectata (dreeves, 2026-11-03: "we want everything to appear in this box -- the box shouldn't ever refer to
    # "remarks below""; the design of 2026-11-04: "No box refers to anything outside itself ("below", "above", "on this
    # page", "the paragraph on ...")"): none of them says below, above, this page, paragraph or remarks.
    # Resultata before: the norm bound's sentence said "the paragraph on the norm bound below derives it", and others
    # "at the top of this page" and "the new results above".
    elsewhere = re.compile(r'\b(?:below|above|this page|paragraph|remarks)\b', re.I)
    templates = re.findall(r'<template data-panel="([^"]+)"[^>]*>(.*?)</template>', page(), re.S)
    assert len(templates) >= 14 and [t for t, body in templates if elsewhere.search(body)] == [], templates
    said = [(P['target'], P['said']) for P in valid_run('boxes')['boxes']]
    said += [(P['n'], text) for P in valid_run('panels')['panels'] for why, text, _ in P['parts'] if why.startswith(('witness', 'proof'))]
    assert [(t, s) for t, s in said if elsewhere.search(s)] == [], [(t, s) for t, s in said if elsewhere.search(s)][:3]


def quoted_right(parts):
    """Whether a box's parts, [(kind, text, whether of Claude's English)], quote Claude once around its parts of Claude's
    English, from the start of the first to the end of the last, and not at all without any.  Spec change (Claude,
    2026-11-05): a box's searches, its copy of the Search progress section's runs, are left out, since they carry that
    section's own quotations (Astra's in the chance line since 2026-11-05), as the word budget leaves them out."""
    parts = [p for p in parts if p[0] != 'searches']
    claude, text = [i for i, (_, _, c) in enumerate(parts) if c], ''.join(t for _, t, _ in parts)
    return (text.count('Claude: “') == text.count('”') == min(1, len(claude))
            and all(parts[i][1].startswith('Claude: “') for i in claude[:1]) and all(parts[i][1].endswith('”') for i in claude[-1:]))


def q_box_quotes_claude_around_its_english_alone():
    # Replicata: index.html's boxes' templates; every box of the boxes run, and every column's box of the panels run.
    # Expectata (dreeves, 2026-11-04, of «Claude: “m*(480) ≥ 12: equipow p480 <code>”»: "we don't need claude
    # attribution for blurbs without words like these"; the design of 2026-11-04: "every generated English word sits
    # under one Claude attribution per box ... with a TODO comment above each template giving a recap of what the copy
    # conveys"): the templates marked data-claude are exactly CLAUDE_TEMPLATES, each with a TODO recap right above it,
    # and no other template has a TODO recap; a box's parts of those (data-claude) sit in one quote, its Claude: “ at
    # the start of the first and its ” at the end of the last, where it has any, and a box with none has no quote.
    # Resultata before: every box had Claude: “ … ” around all of its witness's and its proof's parts, those of math,
    # codes and labels alone too, such as 480's “m*(480) ≥ 12: equipow p480 <code>”.
    templates = re.findall(r'(<!--(?:(?!-->).)*-->)\n  <template data-panel="([^"]+)"( data-claude)?>', page(), re.S)
    assert len(templates) == len(re.findall(r'<template data-panel=', page())) >= 14, len(templates)
    assert {name for _, name, claude in templates if claude} == CLAUDE_TEMPLATES, [(name, claude) for _, name, claude in templates]
    assert all(comment.startswith('<!-- TODO: ') == bool(claude) for comment, _, claude in templates), [(c[:30], n) for c, n, _ in templates]
    boxes = [(P['target'], P['parts']) for P in valid_run('boxes')['boxes']] + [(P['n'], P['parts']) for P in valid_run('panels')['panels']]
    bad = [(t, parts) for t, parts in boxes if not quoted_right(parts)]
    assert bad == [], bad[:3]
    assert {bool(sum(c for _, _, c in parts)) for _, parts in boxes} == {True, False}, 'boxes with and without English'


def q_cell_box_words_stay_within_budget():
    # Replicata: the boxes run's boxes of cells, the text of their parts but their searches (which are the Search
    # progress section's); and every column's box of the m*(n) chart (the panels run), its witness's and its proof's
    # parts, a cell's box of its column showing its witness, its proof, or both (a black cell's).
    # Expectata (dreeves, 2026-11-03: "so many pointless words in the implementation so far"; spec, Claude's proposal of
    # 2026-11-04 for dreeves to review): a cell's box has at most BOX_WORDS, 24, words outside its math, codes and
    # numbers (words), the attribution "Claude", where it has one, and the data's labels among them; the most on
    # 2026-11-04, 19, is a black cell's at 480, 528 and 720, an example's label and the residue condition's proof.
    # Resultata before: the panel that a click on (1024, 12) opened had 121 such words (scratch/reo-step3-20261103/red/).
    cols, most = mstar_data()['cols'], []
    for P in valid_run('panels')['panels']:
        n, parts = P['n'], P['parts']
        lo, hi = cols[n - 1][:2]
        text = {k: ' '.join(t for why, t, _ in parts if why.startswith(k)).replace('Claude: “', '').replace('”', '') for k in ('witness', 'proof')}
        claude = {k: any(c for why, _, c in parts if why.startswith(k)) for k in ('witness', 'proof')}
        for kind in [k for k, present in (('exists', lo >= 1), ('open', hi > lo), ('impossible', hi < mstar_data()['mtop'])) if present]:
            shows = SHOWS[kind]                    # the attribution, Claude, is a word where the box has one
            count = ((claude['witness'] and shows[0]) or (claude['proof'] and shows[1])) + len(words(text['witness'])) * shows[0] + len(words(text['proof'])) * shows[1]
            most.append((count, n, kind))
    most += [(len(words(' '.join(text for why, text, _ in P['parts'] if why != 'searches'))), tuple(P['target']), 'clicked')
             for P in valid_run('boxes')['boxes'] if None not in P['target']]
    assert max(c for c, *_ in most) <= BOX_WORDS, sorted(most, key=lambda x: x[0])[-5:]


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


def moment(t, t1):
    """A finish time of a snapshot at t: its weekday and its 12-hour time; but a week or more after t its local date,
    YYYY-MM-DD (dreeves, 2026-10-23: "the parenthetical needs disambiguation when >1week")."""
    return f'{time.strftime("%a", time.localtime(t1))} {ampm(t1)}' if t1 - t < WEEK else time.strftime('%Y-%m-%d', time.localtime(t1))


def finish(t, t1, t2):
    """The status line's finish times, of a snapshot at t: the first (moment), a spaced en dash, the second's weekday
    only when its date differs, the second; but an end a week or more after t as its local date."""
    day = lambda s: time.strftime('%a', time.localtime(s))
    date = lambda s: time.strftime('%Y-%m-%d', time.localtime(s))
    second = f'{"" if date(t1) == date(t2) else day(t2) + " "}{ampm(t2)}' if t2 - t < WEEK else date(t2)
    return f'{moment(t, t1)} – {second}'
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
        copy_page_dir(d)
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
    theorem = next(p for p in paras if re.search(r'\(2\^\{?\d+\}?\) \\ge \d+', p))
    alt = next(p for p in paras if '1, 2, \\ldots, ' in p)
    bounds = [(int(k), op, int(v)) for k, op, v in re.findall(r'\(2\^\{?(\d+)\}?\) (\\ge|=) (\d+)', theorem)]
    cols = pow2_data()['cols']
    E = max(c[0] - k for k, c in enumerate(cols, 1))
    firsts = [next(k for k in range(1, len(cols) + 1) if cols[k - 1][0] - k >= e) for e in range(1, E + 1)]
    # Spec change (Claude, 2026-11-05): dreeves's 6000eaa (2026-11-04) puts m*(2^9) = 9 first and states m*(2^{10}) = 11
    # as an equality, which pow2.js settles; so the bounds are compared as a set, and a bound may say = where pow2.js's
    # two bounds there are equal.
    assert sorted((k, v) for k, _, v in bounds) == sorted([(9, 9)] + [(k, k + e) for e, k in enumerate(firsts, 1)]), (bounds, firsts)
    assert all(op == '\\ge' or cols[k - 1][:2] == [v, v] for k, op, v in bounds), [(b, cols[b[0] - 1][:2]) for b in bounds]
    assert (9, '=', 9) in bounds and cols[8][:2] == [9, 9], (bounds, cols[8][:2])
    assert f'1, 2, \\ldots, {E}' in alt and ', '.join(map(str, firsts)) in alt, (alt, firsts)


def q_smallest_section_sits_between_the_remarks_and_the_counts():
    # Replicata: index.html's section "The smallest length known for each order".
    # Expectata: a <section class="smallest" aria-labelledby="smallest-title"> (anywhere since 2026-10-30, when
    # dreeves moved it after the m*(n) chart; between the remarks and the counts before), holding its heading, a link to OEIS
    # A323395, and a table whose body is empty in the HTML: the script fills it from mstar.js; and not of class block,
    # so that the page keeps the twelve tables of that class that mstar.py reads as Table 2's and the new results'
    # (their count asserted there until 2026-10-27, which a tenth broke on 2026-10-17; nine until 2026-10-26, when the
    # powers of 2 took a third row, and ten until 2026-10-27, when the new results took in Table 2 and reached 1024 in
    # six upper rows).
    text = page()
    filler = r'(?:\s|<!--.*?-->)*'
    m = re.search(r'(<section class="smallest" aria-labelledby="smallest-title">\n.*?\n</section>)', text, re.S)
    assert m, 'no section "smallest"'
    body = m.group(1)
    assert '<h2 id="smallest-title">' in body, body[:300]
    assert 'href="https://oeis.org/A323395"' in body, body
    assert '<table>' in body and '<tbody data-smallest></tbody>' in body, body
    assert text.count('<table class="block">') == 12, text.count('<table class="block">')


SMALLEST_TABLE = []    # the table of smallest lengths as the page draws it, made once per process (smallest_table)


def smallest_table():
    """The rows of the table of smallest lengths, each as the texts of its cells: index.html in headless Chrome beside
    page/, mstar.js and pow2.js, its DOM dumped once its scripts ran; made once per process."""
    if not SMALLEST_TABLE:
        d = tempfile.mkdtemp(prefix='index-quals-')
        for src, name in ((INDEX, 'index.html'), (DATA, 'mstar.js'), (POW2, 'pow2.js')): shutil.copy(src, os.path.join(d, name))
        copy_page_dir(d)
        dom = chrome(d, ['--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
        shutil.rmtree(d)
        body = re.search(r'<tbody data-smallest="">(.*?)</tbody>', dom, re.S)
        assert body, dom[-2000:]
        SMALLEST_TABLE.extend([html.unescape(re.sub(r'<[^>]+>', '', c)) for c in re.findall(r'<td>(.*?)</td>', tr, re.S)]
                              for tr in re.findall(r'<tr>(.*?)</tr>', body.group(1), re.S))
    return SMALLEST_TABLE


def q_smallest_table_matches_mstar():
    # Replicata: the table of smallest lengths as the page draws it (smallest_table); and smallest_rows of MSTAR
    # (mstar_data), computed here.
    # Expectata: the table's body holds exactly smallest_rows' rows, in order, through the largest order some n's upper
    # bound allows (since 2026-10-30) and the orders past the chart through mstar.MMAX (one more since 2026-11-03, [LIN]; through 17 since 2026-11-04, [M17]),
    # with a product of lesser orders' lengths where that is less than the chart's, as
    # beyond the chart (since 2026-10-31, [MIN]; until then — where no n up to NMAX was known to reach m); the first
    # twelve orders' smallest lengths are SMALLEST_PROVEN, each marked proven (480 added on 2026-11-03 after the pin tree of 432:12; 432 added on 2026-10-20 after
    # proof384.py).
    got = smallest_table()
    want = smallest_rows(mstar_data())
    assert got == want, (got, want)
    proven = got[:len(SMALLEST_PROVEN)]
    assert [r[2] for r in proven] == [str(n) for n in SMALLEST_PROVEN] and all(r[3] == '✓' for r in proven), proven


# The smallest lengths past the chart (dreeves's README, 2026-10-31: "[MIN] In the "smallest length known for each
# order" table, we currently have no entries for the smallest known n for orders 14 and 15. But we know from Thue-Morse
# that 2^14 has order at least 14 and in fact from the chart below the table, we know 2^13 has order 14. Similarly for
# 2^14 having order at least 15.").

def least_columns(cols):
    """[(m, the least n whose lower bound is at least m, or None, the least n whose upper bound is)] for each order m from
    1 while some n's upper bound allows m: the chart's own least n known to reach m and least n not ruled out."""
    least = lambda test: next((n for n, c in enumerate(cols, 1) if test(c)), None)
    out, m = [], 1
    while least(lambda c: c[1] >= m):
        out.append((m, least(lambda c: c[0] >= m), least(lambda c: c[1] >= m)))
        m += 1
    return out


def products_least(cols, m, past=()):
    """By brute force over the chart's data: the least product n_1 n_2 ... n_k (k >= 1) of lengths of the chart, and of
    the examples past it in past (mstar.js's past, [n, order, label]; since 2026-11-04), whose lower bounds sum to at
    least m, a product f(x) g(x^n) (f of length n) having order at least the sum of its factors'.  A depth-first search
    over the multisets of lengths with a lower bound of at least 1, in rising order, cut off where the product already
    exceeds the least found."""
    lengths = sorted([(n, c[0]) for n, c in enumerate(cols, 1) if c[0] >= 1] + [(n, k) for n, k, _ in past])
    best = math.inf
    def go(start, product, order):
        nonlocal best
        if order >= m:
            best = min(best, product)
            return
        for j in range(start, len(lengths)):
            n, lo = lengths[j]
            if product * n > best: break
            go(j, product * n, order + lo)
    go(0, 1, 0)
    return best


def q_smallest_lengths_go_past_the_chart():
    # Replicata: the table of smallest lengths as the page draws it (smallest_table).
    # Expectata ([MIN]): every order has a smallest known length, a number; orders 14 and 15 are reached at 960 by its example of order 15 (2026-11-03), 960 proven least at
    # order 15, the least n not ruled out being 480 and 960.  (From 2026-10-31 until then no n up to 1024 was known to reach them, and they had products: 1920 = 960 · 2
    # (960 = 480 · 2, the chart's least n of order 13, and 480 of order 12) and 3840 = 1920 · 2, each less than [MIN]'s 2^13 and 2^14, and neither proven least.)
    # Resultata before: — at orders 14 and 15.
    # And since 2026-11-03 ([LIN]: "Add one more line for m=16", then "yes, 1440 instead of ">1024" if that's all we
    # know so far"), order 16, which no n up to 1024 allows: not ruled out first at 1440 (mstar.js's mtopAt), and
    # reached at 1920 = 960 · 2, its example of order 15 times Thue–Morse's of order 1 at 2, until 2026-11-04, when the example of order 16 at 1440 reached
    # it at the least n not ruled out (q_example_at_1440_settles_a_15).
    # And since 2026-11-04 (dreeves's README: "[M17] Let's add m=17 to the "smallest length known" table; no need for much
    # search, just whatever bounds we can find quickly"), order 17: not ruled out first at 1440 either (mstar.js's
    # mtopAt; quals_mstar's q_order_17_is_open_first_at_1440), and reached at 2880 = 1440 · 2, the example of order 16
    # times Thue–Morse's of order 1 at 2, not proven least.  (Resultata before: the table stopped at order 16.)
    rows = smallest_table()
    assert all(re.fullmatch(r'\d+', r[2]) for r in rows), rows
    assert rows[13:] == [['14', '480', '960', ''], ['15', '960', '960', '✓'], ['16', '1440', '1440', '✓'],
                         ['17', '1440', '2880', '']], rows[13:]


def q_smallest_known_is_the_least_product_of_the_chart_s_lengths():
    # Replicata: the table of smallest lengths as the page draws it (smallest_table), and mstar.js's columns.
    # Expectata ([MIN]): each order m's smallest known length is products_least(cols, m), the least product of lengths
    # of the chart whose lower bounds sum to at least m, found by brute force.
    # Resultata before: — at orders 14 and 15, whose least products are 1920 and 3840.
    # Since 2026-11-04 an example past the chart (mstar.js's past) competes with them: order 16's 1440 against its least product, 1920.
    # Since 2026-11-04 ([M17]) its length is a factor too: order 17's 2880 = 1440 · 2 against the chart's own 3840 = 960 · 4.
    cols, past = mstar_data()['cols'], mstar_data()['past']
    rows = smallest_table()
    assert [products_least(cols, m, p) for m in (16, 17) for p in ((), past)] == [1920, 1440, 3840, 2880]
    assert [r[2] for r in rows] == [str(products_least(cols, m, past)) for m in range(1, len(rows) + 1)], rows


def q_smallest_rows_the_chart_decides_are_unchanged():
    # Replicata: the table of smallest lengths as the page draws it (smallest_table), mstar.js's columns, and as a
    # control a table made by a wrong rule, 2^m (Thue–Morse) at every order.
    # Expectata ([MIN]): products fill only rows that the chart does not decide: at each order m that some n up to 1024
    # is known to reach (today 1 to 13), the row is the chart's own, as before 2026-10-31: m, the least n whose lower
    # bound is at least m, ✓ when that is also the least n whose upper bound is, and that n (least_columns); and the
    # control fails this.
    # Resultata before: (none: this holds before and after, as it must; the control is what fails.)
    cols = mstar_data()['cols']
    def check(rows):
        want = [[str(m), str(p), str(k), '✓' if k == p else ''] for m, k, p in least_columns(cols) if k is not None]
        assert len(want) >= 13 and rows[:len(want)] == want, (rows[:len(want)], want)
    check(smallest_table())
    wrong = [[str(m), str(p), str(2 ** m), '✓' if 2 ** m == p else ''] for m, k, p in least_columns(cols)]
    try: check(wrong)
    except AssertionError: return
    # TODO: error copy; says the check passed a table made by a wrong rule
    raise AssertionError('Claude: "the check passed the wrong table"')


def q_smallest_columns_follow_the_chart():
    # Replicata: the table of smallest lengths: its header in index.html, and its rows as the page draws them
    # (smallest_table).
    # Expectata (dreeves's README, 2026-10-31: "[FLP] I think the smallest-known and smallest-not-ruled-out columns
    # should be swapped, so the numbers in that table are in the same order they're in in the chart. And then I think
    # the checkmarks should be the last column"): the columns are the order, the smallest n not ruled out, the smallest
    # known n, then whether that is proven smallest; so in every row the n not ruled out is at most the n known, as
    # they stand left to right in the chart, and the check mark stands last, exactly where the two agree.
    # Resultata before: the smallest known n second, the check mark third, the n not ruled out last.
    head = re.search(r'<section class="smallest".*?<thead><tr>(.*?)</tr></thead>', page(), re.S)
    assert head, 'no header for the table of smallest lengths'
    assert re.findall(r'<th>(.*?)</th>', head.group(1)) == [
        'order \\(m\\)', 'smallest \\(n\\) not ruled out', 'smallest known \\(n\\)', 'proven smallest'], head.group(1)
    rows = smallest_table()
    assert all(int(r[1]) <= int(r[2]) and r[3] == ('✓' if r[1] == r[2] else '') for r in rows), rows


def q_tables_and_figures_are_numbered():
    # Replicata: index.html: the labels of its own tables and charts, and every mention of a numbered table or figure
    # in its visible text, its tags' attribute values, its scripts (page/) and mstar.js's hover labels.
    # Expectata (dreeves's README, 2026-11-03: "[NUM] Number the tables and charts for easier reference. To avoid
    # confusion with BGPW's Table 2 I guess we could just omit "Table 1" and start with our extended results as "Table
    # 3"?", then "alternatively we could just always be clear about the BGPW prefix and have our own tables/figures/charts
    # numbered normally from 1", then "can you do this more like latex does it? the numbers don't belong in the section
    # headers", and "the powers-of-two table should have it's own number, right? if there's prose in between two tables
    # that's not a caption, they can't be considered the same table"): the page's own tables and charts are numbered from
    # 1 in page order, each by a small-caps label in its caption, as in LaTeX and as BGPW's Table 2 above them is: a
    # table's caption above it, a figure's below it. Table 1 the extended results other than powers of 2 (a caption above
    # them, with dreeves's words "Extended results since BGPW"), Table 2 the powers of 2 (a caption right above their
    # frame), Figure 1 the m*(n) chart (a caption after its readout), Table 3 the smallest lengths (its caption), Figure 2
    # the powers-of-2 chart (a caption after its readout), Table 4 the record gaps (its caption); no section heading holds
    # a label; each label once; and every other numbered table or figure the
    # page names is the paper's, named as such just before it ("BGPW" or "paper's" among the 40 visible characters
    # before it) or right after it ("of BGPW", "of the paper", as in dreeves's "Table 2 of the paper by Buhler, ...").
    # Resultata before: no labels; and Claude's "the upper value in Table 2's entry for 288" named BGPW's Table 2 bare.
    text, seen = page(), visible_text()
    LABELS = (('Table 1', r'<div class="new-block">\s*<p class="float-caption"><span class="sc">'),
              ('Table 2', r'<p class="float-caption"><span class="sc">'),
              ('Figure 1', r'<p id="mstar-readout" aria-live="polite">[^\n]*</p>\n  <p class="float-caption"><span class="sc">'),
              ('Table 3', r'<h2 id="smallest-title">[^\n]*</h2>.*?<table>\s*<caption><span class="sc">'),
              ('Figure 2', r'<p id="pow2-readout" aria-live="polite">[^\n]*</p>\n  <p class="float-caption"><span class="sc">'),
              ('Table 4', r'<table class="pow2-gaps" data-record-gaps>\s*<caption><span class="sc">'))
    at = []
    assert not re.search(r'<h2[^>]*>[^\n]*<span class="sc">(?:Table|Figure)', text), 'a label in a section heading'
    for label, lead in LABELS:
        m = re.search(lead + re.escape(label) + r'\.</span>', text, re.S)
        assert m, label
        at.append(m.end() - len(label + '.</span>'))
    assert at == sorted(at), at
    # (A caption may go on past its label, as Table 1's does and, since dreeves's d66ad09, Table 2's.)
    assert re.search(r'<p class="float-caption"><span class="sc">Table 2\.</span>[^\n]*</p>\s*<div class="scroll">\s*<table class="block">\s*'
                     r'<tr class="ns"><th scope="row">\\\(n\\\)</th><td[^>]*>\\\(2\^', text), 'Table 2 is not right above the powers of 2'
    assert re.findall(r'<span class="sc">((?:Table|Figure) \d+)\.</span>', text) == [label for label, _ in LABELS]
    mention, after = r'\b(?:Tables?|Figures?) \d+', r' of (?:BGPW|the paper)\b'
    bare = [seen[m.start():m.end()] for m in re.finditer(mention, seen) if m.start() not in at
            and not re.search(r"BGPW|paper's", seen[:m.start()].replace('\0', '')[-40:])
            and not re.match(after, seen[m.end():].replace('\0', ''))]
    tags = [v for t in re.findall(r'<[a-zA-Z][^>]*>', text) for v in re.findall(r"""=(?:'([^']*)'|"([^"]*)")""", t) for v in v if v]
    others = tags + page_scripts(text) + [open(DATA, encoding='utf-8').read()]
    bare += [o[max(0, m.start() - 40):m.end()] for o in others for m in re.finditer(mention, o)
             if not re.search(r"BGPW|paper's", o[max(0, m.start() - 40):m.start()]) and not re.match(after, o[m.end():])]
    assert not bare, bare


def q_smallest_script_passes_node_check():
    # Replicata: the script that fills the table of smallest lengths (page/smallest-section.js since 2026-10-31, an
    # inline script before), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = next(js for js in page_scripts(page()) if '[data-smallest]' in js)
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'smallest.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_progress_section_starts_closed():
    # Replicata: index.html's section "Search progress".
    # Expectata: a <section class="progress" aria-labelledby="progress-title"> after the lattice section (after the
    # sets' section, until it left the page on 2026-10-31) and before the
    # footer: after any comments, a <details> without open, so it starts closed, whose <summary> is the heading
    # progress-title, with a key of the five statuses; and in its run template one more <details>, also without open,
    # each run's fold (dreeves, 2026-10-23; since 2026-10-25 each stays as this browser left it); no <script> on the
    # page names progress.js, which the section's script (page/progress-section.js since 2026-10-31) loads only once it
    # is opened.
    text = page()
    sec = re.search(r'<section class="progress" aria-labelledby="progress-title">\n(.*?)\n</section>\n', text, re.S)
    assert sec and text.index('<section class="lattice"') < sec.start() < text.index('<footer>'), sec
    body = sec.group(1)
    assert re.match(r'(?:\s*<!--.*?-->)*\s*<details>', body, re.S), body[:300]
    assert '<details open' not in body and body.count('</details>') == 2, body[:300]
    run = re.search(r'<template class="progress-run">(.*?)</template>', body, re.S).group(1)
    assert run.count('<details>') == 1 and run.count('</details>') == 1, run[:300]
    assert '<summary><h2 id="progress-title">' in body
    assert [s for s in re.findall(r'data-count="(\w+)"', body)] == list(STATUSES)
    assert not re.search(r'<script[^>]*progress\.js', text)


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
    style = re.sub(r'/\*.*?\*/', '', page_css(), flags=re.S)
    selectors = [s.strip() for sel in re.findall(r'([^{}]+)\{', style) for s in sel.split(',')]
    scoped = r'(\.progress(-[\w-]+)?|\.(' + '|'.join(map(re.escape, others)) + r')|#(pow2|mstar)[\w-]*)(?![\w-])'
    foreign = [s for s in selectors if not re.match(scoped, s)]
    bad = [(s, c) for s in foreign for c in classes if re.search(rf'\.{re.escape(c)}(?![\w-])', s)]
    assert classes and not bad, bad


def q_progress_css_names_only_what_the_section_has():
    # Replicata: the page's CSS rules whose selectors start with the section's classes (.progress, .progress-*); the
    # section's markup with its script (the page's last, page/progress-section.js since 2026-10-31, which makes the
    # chart's and the tip's marks).
    # Expectata: every class and element such a selector names occurs in them, so no rule of the section's matches
    # nothing.  (2026-10-17: dreeves took the section out of its block quote, which left .progress blockquote and
    # .progress .attrib matching nothing.)
    text = page()
    sec = re.search(r'<section class="progress".*?</section>', text, re.S).group(0)
    js = page_scripts(text)[-1]
    style = re.sub(r'/\*.*?\*/', '', page_css(), flags=re.S)
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
    # Replicata: the section's script (the page's last, page/progress-section.js since 2026-10-31, an inline script
    # before), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = page_scripts(page())[-1]
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
    # Spec change (dreeves, 2026-11-04, of a break whose band top sat just above the cap: "does the y-axis break in this
    # particular graph make sense?", then of a break only where it gives the main panel a larger scale than one axis up
    # to the tallest value would: "sounds like your principled fix should work. updating the quals is fine."): eta's
    # tallest value, its band top at 16.2 h, is 1.04 times the cap, under the 196/146 = 1.34 at which a break gains room,
    # so eta has one panel, up to that top, 16.2/14.2 times the projected finish; long's, 6.8 times, still breaks.
    # Until then eta's band top went to a top panel from 15.62 h to 20 h, labeled 20 h.
    for case, over, labels, ratio in (('long', True, ['6', '8\u202fy'], 1.1), ('eta', False, [], 16.2 / 14.2), ('narrow', False, [], 1.1)):
        parts = SvgParts()
        parts.feed(progress_run(case)['etaSvg'])
        pts = lambda a: [tuple(map(float, xy.split(','))) for xy in a['points'].split()]
        seg = lambda a: tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2'))
        [axis] = [float(a['y1']) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'axis']
        [guide] = [pts(a) for tag, a, _ in parts.items if tag == 'polyline' and a.get('class') == 'guide']
        rects = [tuple(float(a[k]) for k in ('x', 'y', 'width', 'height')) for tag, a, _ in parts.items if tag == 'rect']
        yt, yb = rects[0][3], rects[1][1]                     # the top panel's bottom edge, the main panel's top
        assert abs((axis - yb) - ratio * (axis - guide[0][1])) < 0.05, (case, axis, yb, guide[0])
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
    style = page_css()
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
    copy_page_dir(d)
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
    copy_page_dir(d)
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


def q_progress_says_when_an_eta_is_lindy():
    # Replicata: index.html with three runs of 768:12 as progress.js: a tracked search running on Gott's rule alone
    # (lindy true), the same with its own estimate (lindy false), and an untracked run (no lindy field).
    # Expectata (dreeves, 2026-11-04: "i think the graph should say if it's just using lindy"): the first run's note
    # below its ETA chart shown, and not empty; the other two runs' notes hidden.  Its words are not pinned (dreeves
    # wrote his own the same day, and no qual pins wording since 2026-10-26).
    # Resultata before: no such note on the page.
    base, made = PROGRESS_DATA['runs'][0], PROGRESS_DATA['made']
    plain = dict(program='w12.py', n=768, order=12, state='running', outcome=None, so_far=600,
                 to_go=dict(median=600, lo=600 / 19, hi=19 * 600),
                 etas=[[made - 60, 540.0, 540.0, 28.4, 10260.0], [made, 600.0, 600.0, 31.6, 11400.0]],
                 statuses=base['statuses'], depth=0, keys=['768:12'], groups=['4'],
                 counts=dict(settled=0, open=0, split=0, pending=0, running=1), stale=None)
    work = dict(runs=1, running=1, frozen=0, ended=0, aborted=0, found=0)
    lindy, own = dict(plain, tracked=True, work=work, lindy=True), dict(plain, tracked=True, work=work, lindy=False)
    got = progress_harness({'made': made, 'runs': [lindy, own, plain]}, """
  const notes = runs().map(box => box.querySelector('[data-lindy]'));
  out(notes.map(e => e && {hidden: e.hidden, text: e.textContent.trim()}));""")
    assert all(got) and [n['hidden'] for n in got] == [False, True, True] and got[0]['text'], got


def q_progress_shows_a_tracked_search():
    # Replicata: index.html with two runs of 768:12 by w12.py as progress.js, alike but for the second being a tracked
    # search's (tracked, its runs' work: 4 runs, 3 running, 1 ended, none found; dots running, running, running,
    # settled), each in the form progress.js_text gives survey_track's survey since 2026-10-31: running, 600 s so far,
    # to go by Gott's rule (600 s at the median, from a 19th of it to 19 times it), and two recorded ETAs, at 540 s and
    # 600 s of running.
    # Expectata (dreeves, 2026-10-28: "can we rearchitect things so that always happens easily and automatically?"; the
    # coordinator, 2026-10-31: "Every run gets an ETA graph", tracked searches drawing the same ETA figure and status
    # line as every other run): its heading asks m*(768) ≥ 12? and names w12.py, its summary says running; its ETA chart
    # shown and drawn as the other run's (the same figure, but for its clip path's id); its status line the other's,
    # then its counts (template progress-track: 4 runs, 3 running, 0 frozen, 1 ended, 0 aborted, 0 found) with its
    # elapsed time filled in; its readout the tracked hint (template progress-track-hint); its key hidden.
    # Resultata before (2026-10-28's tracked view): its ETA chart hidden and its status line its counts alone.
    base, made = PROGRESS_DATA['runs'][0], PROGRESS_DATA['made']
    plain = dict(program='w12.py', n=768, order=12, state='running', outcome=None, so_far=600,
                 to_go=dict(median=600, lo=600 / 19, hi=19 * 600),
                 etas=[[made - 60, 540.0, 540.0, 28.4, 10260.0], [made, 600.0, 600.0, 31.6, 11400.0]],
                 statuses=base['statuses'], depth=0, keys=['768:12'], groups=['4440'],
                 counts=dict(settled=1, open=0, split=0, pending=0, running=3), stale=None)
    tracked = dict(plain, tracked=True, work=dict(runs=4, running=3, frozen=0, ended=1, aborted=0, found=0))
    got = progress_harness({'made': made, 'runs': [plain, tracked]}, """
  const [plain, r] = runs();
  const tpl = name => document.querySelector('template.' + name);
  const fig = box => box.querySelector('.progress-eta');
  const drawn = box => fig(box).innerHTML.replace(/progress-clip-\\d+/g, 'progress-clip');
  const line = box => [...box.querySelectorAll('.progress-status [data-state]')].filter(e => !e.hidden).map(e => e.textContent);
  out({head: r.querySelector('h3').textContent,
       label: [...r.querySelectorAll('[data-label]')].filter(e => !e.hidden).map(e => e.dataset.label),
       hidden: [fig(plain).hidden, fig(r).hidden], same: drawn(plain) === drawn(r), drawn: drawn(r).length,
       lines: [line(plain), line(r)],
       counts: Object.fromEntries([...r.querySelectorAll('.progress-status [data-attempt-count]')].map(e => [e.dataset.attemptCount, e.textContent])),
       elapsed: (r.querySelector('.progress-status [data-elapsed]') || {}).textContent || '',
       readout: r.querySelector('[data-readout]').textContent.trim(),
       hint: tpl('progress-track-hint') ? tpl('progress-track-hint').content.textContent.trim() : null,
       key: r.querySelector('.progress-key').hidden});""")
    assert got['head'] == 'm*(768) ≥ 12? w12.py' and got['label'] == ['running'], got
    assert got['hidden'] == [False, False] and got['same'] is True and got['drawn'] > 0, got
    assert got['lines'][0] == got['lines'][1] and len(got['lines'][1]) == 1 and got['lines'][1][0].strip(), got
    assert got['counts'] == dict(runs='4', running='3', frozen='0', ended='1', aborted='0', found='0'), got
    assert got['elapsed'] != '' and got['hint'] is not None and got['readout'] == got['hint'] and got['key'] is True, got


STAGES_LOOK = """
  out(runs().map(r => {
    const p = r.querySelector('[data-stages]'), text = sel => (p.querySelector(sel) || {}).textContent;
    return {shown: !p.hidden, now: text('[data-stage-now]'), total: text('[data-stages-total]'),
            later: [...p.querySelectorAll('[data-stages-later] > span')].map(s =>
              [s.querySelector('[data-stage-name]').textContent, s.querySelector('[data-stage-to-go]').textContent]),
            after: !!(r.querySelector('.progress-status').compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING)};
  }));"""


def q_progress_names_a_run_s_later_stages():
    # Replicata: index.html with two runs of 432:12 by fanout.py as progress.js, each in the form progress.js_text gives
    # a run in a chain (2026-10-31): the first with one later stage, reprove.py, 7 to 9 days to go (median 8), and in
    # all 10 to 14 days to a recordable result (median 12); the second with two, fanout.assemble with no estimate and
    # then reprove.py as the first's, and no total.
    # Expectata (the coordinator, 2026-10-31, after the page's ETA had covered only the stage running, twice in two
    # days: "the current stage's ETA chart stays as it is, labeled as that stage's; under it, one compact line naming
    # the later stages with their estimates, and the total to a recordable result"): below each run's status line, its
    # line of stages shown, naming the program its chart covers (fanout.py), each later stage in order with the range
    # of its time to go, 7.0–9.0 d, or — with no estimate, and the range to a recordable result, 10.0–14.0 d, or —.
    # Resultata before: no line of stages; the ETA chart's stage alone, unnamed as one stage of more.
    base, d = dict(PROGRESS_DATA['runs'][0], program='fanout.py', n=432, order=12), 86400.0
    reprove = dict(name='reprove.py', to_go=dict(median=8 * d, lo=7 * d, hi=9 * d))
    one = dict(base, stages=[dict(name='fanout.py', to_go=base['to_go']), reprove],
               total=dict(median=12 * d, lo=10 * d, hi=14 * d))
    two = dict(base, stages=[dict(name='fanout.py', to_go=base['to_go']), dict(name='fanout.assemble', to_go=None), reprove],
               total=None)
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': [one, two]}, STAGES_LOOK)
    days = '7.0–9.0' + NNBSP + 'd'
    assert got == [dict(shown=True, now='fanout.py', total='10.0–14.0' + NNBSP + 'd', later=[['reprove.py', days]], after=True),
                   dict(shown=True, now='fanout.py', total='—', later=[['fanout.assemble', '—'], ['reprove.py', days]],
                        after=True)], got


def q_progress_shows_no_stages_for_a_run_of_one_stage():
    # Replicata: index.html with two runs as progress.js: PROGRESS_DATA's (no stages, as progress.js_text gives a run in
    # no chain, or as a data file written before 2026-10-31 has none), and the same with stages its own alone.
    # Expectata (the coordinator, 2026-10-31: "Runs with a single stage show nothing extra"): neither shows a line of
    # stages.
    base = PROGRESS_DATA['runs'][0]
    alone = dict(base, stages=[dict(name=base['program'], to_go=base['to_go'])], total=base['to_go'])
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': [base, alone]}, STAGES_LOOK)
    assert [r['shown'] for r in got] == [False, False], got


# A running fanout run with a pool series, in the form progress.js_text gives it (progress.pool_series; dreeves,
# 2026-11-03, README [TRE]): 4 h of running in 100 stretches of 144 s; six points, [time, seconds of running, boxes
# pending or running, stretch]: a pool record's 30,000 boxes at 0.5 h, then 100,000 at 1 h, 180,000 at 2 h, a drop to
# 90,000 at 2.03 h (as the lex cut's), 150,000 at 3 h and 210,000 at 3.89 h; and four stretches with jobs ended, [jobs,
# net change], whose net change per job is +0.5, +0.2, +0.1 and -0.05.
POOL_POINTS = [[PROGRESS_DATA['made'] - 14400 + x, float(x), c, b] for x, c, b in
               ((1800, 30000, 12), (3600, 100000, 25), (7200, 180000, 50), (7300, 90000, 50), (10800, 150000, 75),
                (14000, 210000, 97))]
POOL_JOBS = {25: [1000, 500], 50: [2000, 400], 75: [3000, 300], 97: [4000, -200]}
PROGRESS_POOL = dict(PROGRESS_DATA['runs'][0], program='fanout.py', n=432, order=12, so_far=4 * HOURS,
                     pool=dict(points=POOL_POINTS, buckets=[POOL_JOBS.get(b, [0, 0]) for b in range(100)]))
POOL_LOOK = """
  const all = runs(), [r, other, empty] = all;
  r.querySelector('details').open = true;            // laid out, so that the pointer has somewhere to be
  await sleep(50);
  const fig = box => box.querySelector('.progress-pool');
  const f = fig(r), svg = f.querySelector('svg'), cross = svg.querySelector('[data-pool-cross]');
  const vertices = (box, sel) => (fig(box).querySelector(sel).getAttribute('points') || '').trim().split(/\\s+/)
    .filter(Boolean).map(p => p.split(',').map(Number));
  const ticks = (box, which) => [...fig(box).querySelectorAll(`[data-pool-ticks="${which}"] text`)]
    .map(t => [t.textContent, +t.getAttribute('x'), +t.getAttribute('y')]);
  const tip = box => fig(box).querySelector('[data-pool-tip]').textContent.replace(/[ \\t\\n\\r]+/g, ' ').trim();
  const L = window.progressView.layouts[0], sb = svg.getBoundingClientRect();
  const hover = k => svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + L.poolXs[k] * sb.width / 640,
                                                                    clientY: sb.top + sb.height / 2, bubbles: true}));
  const rest = tip(r);
  hover(2);
  const third = tip(r), crossAt = [cross.getAttribute('visibility'), +cross.getAttribute('x1'), L.poolXs[2]];
  hover(0);
  const first = tip(r);
  svg.dispatchEvent(new MouseEvent('mouseleave'));
  out({hidden: all.map(b => fig(b).hidden),
       after: !!(r.querySelector('[data-stages]').compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING),
       count: vertices(r, '[data-pool-line="count"]'), wash: vertices(r, '[data-pool-wash]'),
       net: vertices(r, '[data-pool-line="net"]'), zero: [...f.querySelectorAll('line.zero')].map(l => +l.getAttribute('y1')),
       xticks: ticks(r, 'x'), counts: ticks(r, 'count'), nets: ticks(r, 'net'),
       titles: [...f.querySelectorAll('[data-pool-title]')].map(t => t.textContent),
       rest, third, first, left: tip(r), crossAt, crossLeft: cross.getAttribute('visibility'),
       empty: {lines: [vertices(empty, '[data-pool-line="count"]').length, vertices(empty, '[data-pool-line="net"]').length],
               tip: tip(empty), xticks: ticks(empty, 'x').map(t => t[0])}});"""


def q_progress_draws_a_fanout_run_s_pool():
    # Replicata: index.html with three runs as progress.js: PROGRESS_POOL, a fanout run with a pool series; PROGRESS_DATA's
    # overnight_v5.py run, whose entry has no pool; and PROGRESS_POOL with a pool of no point and no job (a fanout run
    # before its first pool record).  The first run's fold opened, its pool chart hovered at its third point, then at
    # its first, then left.
    # Expectata (dreeves, 2026-11-03, README [TRE]: "Could we see a time series of the number of pending nodes? If we
    # could see the growth of that slow down, or when it starts to actually go down, we can better infer the ETA."):
    # the first and third runs' pool charts shown, after the line of stages, and the second's hidden.  The first's
    # upper line a vertex per point, at its seconds of running on the x ticks' scale (0 to 4 h, labeled 0, 1, 2, 3, 4 h)
    # and its boxes on the count ticks' (0 to 250K by 50K), over a wash down to 0 at its ends; its lower line a vertex
    # per stretch with jobs, at the stretch's middle and its net change per job ended, on the net ticks' scale (−0.5, 0,
    # +0.5), with a line at 0; the panels' titles; the tip at rest the latest point's line: @ its time, an em space, 3.9 h
    # so far: 210,000 boxes pending or running, net −0.05 per job ended; over the third point the third's (2.0 h,
    # 180,000, +0.20), the cross at it; over the first the first's (0.5 h, 30,000, and — for its stretch, whose only
    # point is a pool record); and after the pointer leaves, the latest's again, the cross hidden.  The third run's
    # chart its axes alone, with no line and no tip.
    # Resultata before: no pool chart.
    empty = dict(PROGRESS_POOL, n=480, pool=dict(points=[], buckets=[[0, 0]] * 100))
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': [PROGRESS_POOL, PROGRESS_DATA['runs'][0], empty]}, POOL_LOOK)
    assert got['hidden'] == [False, True, False] and got['after'] is True, got
    h = NNBSP + 'h'
    assert [t[0] for t in got['xticks']] == ['0', '1', '2', '3', f'4{h}'], got['xticks']
    assert [t[0] for t in got['counts']] == ['0', '50K', '100K', '150K', '200K', '250K'], got['counts']
    assert [t[0] for t in got['nets']] == ['−0.5', '0', '+0.5'], got['nets']
    x0, x4 = got['xticks'][0][1], got['xticks'][-1][1]
    def X(s): return x0 + (x4 - x0) * s / 14400
    def scale(ticks, lo, hi):                     # the y of a value on a panel's scale, from its end ticks' (4 below)
        (_, _, ya), (_, _, yb) = ticks[0], ticks[-1]
        return lambda v: ya - 4 + (yb - ya) * (v - lo) / (hi - lo)
    Y1, Y2 = scale(got['counts'], 0, 250000), scale(got['nets'], -0.5, 0.5)
    def near(got_pts, want): return len(got_pts) == len(want) and all(abs(a - c) < 0.05 and abs(b - d) < 0.05 for (a, b), (c, d) in zip(got_pts, want))
    line = [(X(x), Y1(c)) for _, x, c, _ in POOL_POINTS]
    assert near(got['count'], line), (got['count'], line)
    assert near(got['wash'], [(line[0][0], Y1(0))] + line + [(line[-1][0], Y1(0))]), got['wash']
    nets = [(X(14400 * (b + 0.5) / 100), net / jobs) for b, (jobs, net) in sorted(POOL_JOBS.items())]
    assert near(got['net'], [(x, Y2(v)) for x, v in nets]), (got['net'], nets)
    assert len(got['zero']) == 1 and abs(got['zero'][0] - Y2(0)) < 0.05, got['zero']
    assert got['titles'] == ['boxes pending or running', 'net change per job ended'], got['titles']
    def said(k, net):
        t, x = POOL_POINTS[k][0], POOL_POINTS[k][1]
        return f'@{stamp(t)}{EMSP}{x / 3600:.1f}{h} so far: {POOL_POINTS[k][2]:,} boxes pending or running, net {net} per job ended'
    assert got['rest'] == said(5, '−0.05') and got['left'] == got['rest'], (got['rest'], got['left'])
    assert got['third'] == said(2, '+0.20') and got['first'] == said(0, '—'), (got['third'], got['first'])
    assert got['crossAt'][0] == 'visible' and abs(got['crossAt'][1] - got['crossAt'][2]) < 0.05, got['crossAt']
    assert got['crossLeft'] == 'hidden', got['crossLeft']
    assert got['empty'] == dict(lines=[0, 0], tip='', xticks=['0', '1', '2', '3', f'4{h}']), got['empty']


# A tracked target a campaign searches, in the form progress.js_text gives it with its chance (chance.shown; README
# [SER] and [CON], 2026-11-03): a made-up chance of a find within each quarter hour t up to 72 h, 0.05 (1 - exp(-t /
# 30)), after 2.14 CPU-hours searched; since 6 h before the data was made; and its history, 24 points a quarter hour
# apart from then, the k-th's chance within 24 h 0.05 exp(-k / 12) and within 6 h 0.02 exp(-k / 12).
CHANCE_HOURS = [k / 4 for k in range(289)]
CHANCE_SINCE = PROGRESS_DATA['made'] - 6 * 3600
CHANCE_HISTORY = [[CHANCE_SINCE + 900 * k, 0.02 * math.exp(-k / 12), 0.05 * math.exp(-k / 12)] for k in range(1, 25)]
CHANCE = dict(cpu_hours=2.14, rate=9.15e-4, cores=3.2, hours=CHANCE_HOURS, p=[-0.05 * math.expm1(-t / 30) for t in CHANCE_HOURS],
              since=CHANCE_SINCE, history=CHANCE_HISTORY)
# A modeled search's odds as progress.js carries them (chance.lindy_shown and chance.odds, 2026-11-04): an exhaustive
# search on Lindy's rule begun 30 h before the data was made, P(exists) its prior 0.01 at each quarter hour from then and
# a curve an hour back over a day, each chance.lindy_found on its age then; a campaign target's, P(exists) falling over 8
# quarter hours from 0.3 and four curves, now's flat at 0 (its search stopped); and a campaign target's before any rate
# is measured, with neither.
def lindy_at(tau, aheads): return [s / tau * math.log1p(tau / s) if s else 0.0 for s in aheads]
def lindy_curve(tau): return lindy_at(tau, range(73))
ODDS_T0 = PROGRESS_DATA['made'] - 30 * 3600
ODDS_LINDY = dict(basis='lindy', ahead=list(range(73)), exists=[[ODDS_T0 + 900 * k, 0.01] for k in range(1, 121)],
                  curves=[[PROGRESS_DATA['made'] - 3600 * k, lindy_curve(30 - k)] for k in range(24, -1, -1)])
ODDS_CAMPAIGN = dict(basis='campaign', ahead=list(range(73)),
                     exists=[[PROGRESS_DATA['made'] - 900 * (8 - k), 0.3 * math.exp(-k / 20)] for k in range(9)],
                     curves=[[PROGRESS_DATA['made'] - 3600 * (3 - k), [0.0] + [0.6 * (1 - math.exp(-s / 12)) for s in range(1, 73)]] for k in range(3)]
                            + [[PROGRESS_DATA['made'], [0.0] * 73]])
ODDS_NONE = dict(basis='campaign', ahead=list(range(73)), exists=[], curves=[])
# That exhaustive search's chance as progress.js carries it (chance.lindy_shown): no CPU-hours, rate or cores, which its
# model does not use; its chance within each quarter hour t up to 72 h, the prior times Lindy's rule on its 30 h; and its
# history at each quarter hour from its start, the prior times Lindy's rule on its age then.
LINDY_CHANCE = dict(cpu_hours=None, rate=None, cores=None, hours=CHANCE_HOURS, p=[0.01 * x for x in lindy_at(30, CHANCE_HOURS)],
                    exists=0.01, found=lindy_curve(30), since=ODDS_T0,
                    history=[[ODDS_T0 + 900 * k, *(0.01 * x for x in lindy_at(k / 4, (6, 24)))] for k in range(1, 121)])
# PROGRESS_CHANCE carries its odds beside its chance, as every run with a chance does (2026-11-04: progress.py gives the
# two together, and the chance chart is the third of their graphs).
PROGRESS_CHANCE = dict(program='probe_seed.py', n=528, order=12, state='running', outcome=None, so_far=600,
                       to_go=dict(median=600, lo=600 / 19, hi=19 * 600), etas=[[PROGRESS_DATA['made'], 600.0, 600.0, 31.6, 11400.0]],
                       statuses=list(STATUSES), depth=0, keys=['528:12'], groups=['4440'],
                       counts=dict(settled=1, open=0, split=0, pending=0, running=3), stale=None, tracked=True,
                       work=dict(runs=4, running=3, frozen=0, ended=1, aborted=0, found=0), chance=CHANCE, odds=ODDS_CAMPAIGN)
# The boxes runs' progress.js (2026-11-04, [CEL]: a black cell's box summarizes the searches at its cell): two runs at
# 528:12, PROGRESS_CHANCE and an overnight_v5.py run that ended with no outcome (aborted), and one at 64:7.
BOX_PROGRESS = {'made': PROGRESS_DATA['made'], 'runs': [PROGRESS_CHANCE, dict(PROGRESS_DATA['runs'][0], n=528, order=12, state='ended',
                                                                              to_go=None), PROGRESS_DATA['runs'][0]]}
CHANCE_LOOK = """
  const all = runs(), [r, other, empty, none, unrated] = all;
  for (const b of [r, empty, unrated]) b.querySelector('details').open = true;   // laid out, so that the pointer has somewhere to be
  await sleep(50);
  const fig = box => box.querySelector('.progress-chance');
  const f = fig(r), svg = f.querySelector('svg'), cross = svg.querySelector('[data-chance-cross]'), tip = f.querySelector('[data-chance-tip]');
  const vertices = (box, sel) => (fig(box).querySelector(sel).getAttribute('points') || '').trim().split(/\\s+/)
    .filter(Boolean).map(p => p.split(',').map(Number));
  const ticks = (box, which) => [...fig(box).querySelectorAll(`[data-chance-ticks="${which}"] text`)]
    .map(t => [t.textContent, +t.getAttribute('x'), +t.getAttribute('y')]);
  const stated = box => Object.fromEntries([...fig(box).querySelectorAll('[data-chance-at]')].map(e => [e.dataset.chanceAt, e.textContent]));
  const read = box => [...fig(box).querySelectorAll('[data-chance-tip] > span, [data-chance-tip] [data-chance-hours], [data-chance-tip] [data-chance-p]')]
    .map(e => e.textContent);
  const L = window.progressView.layouts[0], sb = svg.getBoundingClientRect();
  const hover = k => svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + L.chanceXs[k] * sb.width / 640,
                                                                    clientY: sb.top + sb.height / 2, bubbles: true}));
  const rest = [getComputedStyle(tip).visibility, read(r)];
  hover(10);
  const hovered = [getComputedStyle(tip).visibility, read(r), cross.getAttribute('visibility'), +cross.getAttribute('x1'), L.chanceXs[10]];
  svg.dispatchEvent(new MouseEvent('mouseleave'));
  out({hidden: all.map(b => fig(b).hidden), eta: all.map(b => b.querySelector('.progress-eta').hidden), xs: L.chanceXs.length,
       after: !!(r.querySelector('.progress-pool').compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING),
       folded: r.querySelector('details').contains(f),
       line: vertices(r, '[data-chance-line]'), wash: vertices(r, '[data-chance-wash]'),
       marks: [...f.querySelectorAll('[data-chance-marks] circle')].map(c => [+c.getAttribute('cx'), +c.getAttribute('cy')]),
       pticks: ticks(r, 'p'), tticks: ticks(r, 't'), stated: stated(r), spent: f.querySelector('[data-chance-spent]').textContent,
       rest, hovered, left: [getComputedStyle(tip).visibility, cross.getAttribute('visibility')],
       empty: {line: vertices(empty, '[data-chance-line]').length, marks: fig(empty).querySelectorAll('[data-chance-marks] circle').length,
               stated: stated(empty), spent: fig(empty).querySelector('[data-chance-spent]').textContent, tip: read(empty),
               pticks: ticks(empty, 'p').map(t => t[0]), tticks: ticks(empty, 't').map(t => t[0])},
       unrated: {line: vertices(unrated, '[data-chance-line]').length, marks: fig(unrated).querySelectorAll('[data-chance-marks] circle').length,
                 stated: stated(unrated), tip: read(unrated)}});"""


def q_progress_draws_a_search_s_odds():
    # Replicata: index.html with three runs as progress.js: an exhaustive search on Lindy's rule (288:10, LINDY_CHANCE
    # and ODDS_LINDY), PROGRESS_CHANCE (ODDS_CAMPAIGN), and PROGRESS_DATA's overnight_v5.py run, with no odds; the first
    # two folds opened.  (Until 2026-11-04's third graph the first was PROGRESS_CHANCE's run with ODDS_LINDY, its chance
    # a campaign's.)
    # Expectata (dreeves, 2026-11-04: "what if we had 2 probability graphs: 1. probability a partition exists, starting
    # from whatever prior and going down as the search proceeds and doesn't find one ... 2. probability of finding a
    # partition by time t *conditional on a partition existing* and also conditional on not having found one so far ...
    # every timestep we'd draw a new version of the graph that starts going up from zero starting now, for every "now".
    # so maybe we just draw the current one bolded and the previous ones stay visible but are more and more faded?", then
    # "graphs first, then refine the estimates"): each of the first two runs' odds shown: P(exists) a line with a vertex
    # per point and a dot on its last; P(found by t | exists) a curve per entry, each with a vertex per hour ahead, the
    # last bold (class now) and fully opaque, the others fainter the older they are; the note of its own basis shown and
    # the other's hidden.  The third run's odds hidden.
    # Resultata before: no such graphs.
    lindy, campaign = dict(PROGRESS_CHANCE, n=288, order=10, chance=LINDY_CHANCE, odds=ODDS_LINDY), dict(PROGRESS_CHANCE, n=720, order=13)
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': [lindy, campaign, PROGRESS_DATA['runs'][0]]}, """
  const all = runs();
  for (const b of all.slice(0, 2)) b.querySelector('details').open = true;
  await sleep(50);
  const fig = box => box.querySelector('.progress-odds');
  const pts = e => (e.getAttribute('points') || '').trim().split(/\\s+/).filter(Boolean).length;
  const view = box => ({                              // not look: the harness's prelude declares that
    line: pts(fig(box).querySelector('[data-exists-line]')), marks: fig(box).querySelectorAll('[data-exists-marks] circle').length,
    curves: [...fig(box).querySelectorAll('[data-found-curves] polyline')].map(c => [pts(c), c.getAttribute('class'), +(c.getAttribute('opacity') ?? 1)]),
    bases: Object.fromEntries([...fig(box).querySelectorAll('[data-odds-basis]')].map(e => [e.dataset.oddsBasis, e.hidden]))});
  out({hidden: all.map(b => fig(b).hidden), lindy: view(all[0]), campaign: view(all[1])});""")
    assert got['hidden'] == [False, False, True], got['hidden']
    for name, odds in (('lindy', ODDS_LINDY), ('campaign', ODDS_CAMPAIGN)):
        g = got[name]
        assert g['line'] == len(odds['exists']) and g['marks'] == 1, (name, g['line'], g['marks'])
        assert [c[0] for c in g['curves']] == [73] * len(odds['curves']), (name, g['curves'])
        assert [c[1] for c in g['curves']] == ['old'] * (len(odds['curves']) - 1) + ['now'] and g['curves'][-1][2] == 1, (name, g['curves'][-3:])
        assert all(a[2] < b[2] for a, b in zip(g['curves'], g['curves'][1:])), (name, [c[2] for c in g['curves']])
        # Spec change (Claude, 2026-11-05): Astra's work model (installed 2026-11-04 23:00, committed in 6000eaa) added a
        # third basis note, work, hidden for both of these runs.
        assert g['bases'] == {b: name != b for b in ('lindy', 'campaign', 'work')}, (name, g['bases'])


def q_progress_draws_the_chance_after_the_odds():
    # Replicata: index.html with four runs as progress.js: an exhaustive search on Lindy's rule (288:10, LINDY_CHANCE
    # and ODDS_LINDY), PROGRESS_CHANCE (a campaign target, CHANCE and ODDS_CAMPAIGN), PROGRESS_CHANCE with no rate
    # measured yet (its chance's rate and cores null, p and history empty; ODDS_NONE), and PROGRESS_CHANCE stopped
    # halfway (its history CHANCE_HISTORY's first 12 points, to 3 h, its odds' P(exists) still to now, 6 h); their folds
    # opened.
    # Expectata (dreeves, 2026-11-04: "can we get that 3rd chart as well, consistently, after the P(exists) and
    # P(find|exists) charts? maybe we'll see a way to combine them but let's start with everything laid out"): in each
    # run, three graphs in its odds' figure, in this order, each under a title of its own: P(exists), P(found by t |
    # exists), then the chance chart, the history of the chance within 24 h; then the note on its basis.  The first and
    # the third on one time axis, hours since the chance's since, to the latest time either has: the same hour ticks at
    # the same places, the stopped search's 0 to 6 h, its history's line ending halfway along.  The exhaustive
    # search's chance chart a vertex per point of its history, its chances within 6 h and 24 h stated as LINDY_CHANCE's,
    # and — for its CPU-hours, which its model does not count; the campaign target's 2.1 CPU-hours.  With no rate
    # measured yet, every graph's axes alone: no line, curve, dot or now line.
    # Resultata before: the chance chart before the odds' figure, outside it, with no title; the first graph's hours
    # counted from its own first point; and with no rate measured yet, no graphs at all (a TypeError at its first point).
    lindy = dict(PROGRESS_CHANCE, n=288, order=10, chance=LINDY_CHANCE, odds=ODDS_LINDY)
    unmeasured = dict(PROGRESS_CHANCE, n=672, order=13, chance=dict(CHANCE, rate=None, cores=None, p=[], history=[]), odds=ODDS_NONE)
    stopped = dict(PROGRESS_CHANCE, n=720, order=13, chance=dict(CHANCE, history=CHANCE_HISTORY[:12]))
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': [lindy, PROGRESS_CHANCE, unmeasured, stopped]}, """
  const all = runs();
  for (const b of all) b.querySelector('details').open = true;
  await sleep(50);
  const pts = e => (e.getAttribute('points') || '').trim().split(/\\s+/).filter(Boolean).length;
  const ticks = (box, sel) => [...box.querySelectorAll(`${sel} text`)].map(t => [t.textContent, +t.getAttribute('x')]);
  const kind = s => ['exists-line', 'found-curves', 'chance-line'].find(k => s.querySelector(`[data-${k}]`));
  const titled = s => {                                // the nearest title before the graph, among its siblings
    let e = s.previousElementSibling;
    while (e && !e.matches('.progress-odds-title')) e = e.previousElementSibling;
    return !!e && e.textContent.trim().length > 0;
  };
  out(all.map(box => {
    const f = box.querySelector('.progress-odds'), chance = box.querySelector('.progress-chance'), svgs = [...f.querySelectorAll('svg')];
    return {hidden: f.hidden, inside: f.contains(chance), chanceHidden: chance.hidden, svgs: svgs.map(kind),
            shown: svgs.map(s => s.getBoundingClientRect().height > 0), titled: svgs.map(titled),
            beforeNotes: [...f.querySelectorAll('[data-odds-basis]')].every(n => !!(chance.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)),
            existsTicks: ticks(f, '[data-exists-ticks="t"]'), chanceTicks: ticks(box, '[data-chance-ticks="t"]'),
            existsLine: pts(f.querySelector('[data-exists-line]')), line: pts(box.querySelector('[data-chance-line]')),
            curves: f.querySelectorAll('[data-found-curves] polyline').length, nows: f.querySelectorAll('[data-found-now] line').length,
            marks: [f.querySelectorAll('[data-exists-marks] circle').length, box.querySelectorAll('[data-chance-marks] circle').length],
            stated: Object.fromEntries([...box.querySelectorAll('[data-chance-at]')].map(e => [e.dataset.chanceAt, e.textContent])),
            spent: box.querySelector('[data-chance-spent]').textContent,
            lastX: (box.querySelector('[data-chance-line]').getAttribute('points') || '').trim().split(/\\s+/).filter(Boolean).map(p => +p.split(',')[0]).pop() ?? null};
  }));""")
    assert len(got) == 4, got
    for g in got:
        assert g['hidden'] is False and g['inside'] is True and g['chanceHidden'] is False, g
        assert g['svgs'] == ['exists-line', 'found-curves', 'chance-line'] and g['shown'] == [True] * 3 and g['titled'] == [True] * 3, g
        assert g['beforeNotes'] is True and g['existsTicks'] == g['chanceTicks'] and g['chanceTicks'], (g['existsTicks'], g['chanceTicks'])
    pct = lambda v: f'{float(f"{100 * v:.2g}"):g}%'               # as the page writes a chance: 2 significant digits
    lin, camp, none, stop = got
    assert lin['existsLine'] == 120 and lin['line'] == 120 and lin['curves'] == 25 and lin['nows'] == 1 and lin['marks'] == [1, 1], lin
    want = {str(t): pct(LINDY_CHANCE['p'][CHANCE_HOURS.index(t)]) for t in (6, 24)}
    assert lin['stated'] == want == {'6': '0.36%', '24': '0.65%'} and lin['spent'] == '—', (lin['stated'], lin['spent'])
    assert camp['line'] == 24 and camp['spent'] == '2.1' and [t[0] for t in camp['chanceTicks']] == ['0', '2', '4', f'6{NNBSP}h'], camp
    assert none['existsLine'] == 0 and none['line'] == 0 and none['curves'] == 0 and none['nows'] == 0 and none['marks'] == [0, 0], none
    ticks = stop['chanceTicks']
    assert [t[0] for t in ticks] == ['0', '2', '4', f'6{NNBSP}h'] and stop['line'] == 12, (ticks, stop['line'])
    assert abs(stop['lastX'] - (ticks[0][1] + (ticks[-1][1] - ticks[0][1]) / 2)) < 0.05, (stop['lastX'], ticks)   # its 3 h of 6


def q_progress_draws_a_campaign_target_s_chance():
    # Replicata: index.html with five runs as progress.js: PROGRESS_CHANCE, a tracked target a campaign searches, with
    # its chance; PROGRESS_DATA's overnight_v5.py run, whose entry has none; PROGRESS_CHANCE with no rate measured yet
    # and no history (rate null, p and history empty); with its chance null (not live: found, stopped, or its campaign
    # ended); and with no rate measured yet in its live plan but its history kept (rate null, p empty).  The folds of
    # the first, third and fifth opened, the first's chance chart hovered at its eleventh point, then left.
    # Expectata (README [SER], 2026-11-03: "Could the searches show a live estimate of the probability of finding a
    # bipartition?"; README [CON] and dreeves, 2026-11-03: "the curve should fall in light of the conditional
    # probability but it should remain historically accurate, yes? does this end up making it kind of redundant with the
    # ETA graph? ... what's actually most useful to see during a search"): the chance charts of the first, third and
    # fifth shown, in their folds, after the pool chart, and the second's and fourth's hidden; every run's ETA chart
    # shown, the chance charts below theirs.  The first's line a vertex per point of its
    # history, at its hours since its since on the hour ticks' scale (0 to 6, every 2, the last 6 h) and its chance
    # within 24 h on the percent ticks' (0 to 5%, every 1, the last 5%), over a wash down to 0 at its ends; a dot on its
    # last point; the chance within 6 h and within 24 h now stated as percents to 2 significant digits, 0.91% and 2.8%,
    # and the CPU-hours searched, 2.1; its tip at rest hidden, laid out as the last point's (its local time, 24 h and
    # 0.68%); over the eleventh point shown with its time, 24 h and 2%, the cross at it; hidden again, with the cross,
    # once the pointer leaves.  The third's: its axes alone (hours 0 to 0.25, every 0.05; percent 0 to 1%, every 0.2),
    # no line, dot or tip, — for its chances and its CPU-hours stated.  The fifth's: its history's line and dot, its tip
    # laid out, — for its chances now.
    # Spec change (README [CON], 2026-11-03; dreeves: "i guess just apply common sense here too"): until then the chart
    # was the chance within the next t hours for t up to 72, every quarter hour, with dots at 6 and 24 h, beside the ETA
    # chart; it is now the history of the chance within 24 h, in the ETA chart's place.  Spec change (dreeves,
    # 2026-11-04: "shouldn't there always be an ETA graph, even when it's just based on the lindy effect? death to
    # if-statements, remember?"): the ETA charts of the first, third and fifth shown, as every run's; until then hidden.
    # Fixture change (2026-11-04, the chance chart the third of the odds' graphs, in their figure): each run with a chance
    # carries its odds, as progress.js gives the two together, the third ODDS_NONE; the fourth neither.
    # Resultata before: the forward curve (289 vertices on a 72-h axis) beside the ETA chart.
    empty = dict(PROGRESS_CHANCE, n=672, order=13, chance=dict(CHANCE, rate=None, p=[], history=[]), odds=ODDS_NONE)
    none = dict(PROGRESS_CHANCE, n=864, order=13, chance=None, odds=None)
    unrated = dict(PROGRESS_CHANCE, n=720, order=13, chance=dict(CHANCE, rate=None, p=[]))
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': [PROGRESS_CHANCE, PROGRESS_DATA['runs'][0], empty, none, unrated]}, CHANCE_LOOK)
    assert got['hidden'] == [False, True, False, True, False] and got['after'] is True and got['folded'] is True, got['hidden']
    assert got['eta'] == [False] * 5, got['eta']
    h = NNBSP + 'h'
    assert [t[0] for t in got['tticks']] == ['0', '2', '4', f'6{h}'], got['tticks']
    assert [t[0] for t in got['pticks']] == ['0', '1', '2', '3', '4', '5%'], got['pticks']
    x0, x6 = got['tticks'][0][1], got['tticks'][-1][1]
    (_, _, y0), (_, _, y5) = got['pticks'][0], got['pticks'][-1]
    X = lambda hours: x0 + (x6 - x0) * hours / 6
    Y = lambda v: y0 - 4 + (y5 - y0) * v / 0.05                  # a tick label sits 4 below its value's line
    near = lambda pts, want: len(pts) == len(want) and all(abs(a - c) < 0.05 and abs(b - d) < 0.05 for (a, b), (c, d) in zip(pts, want))
    line = [(X((t - CHANCE_SINCE) / 3600), Y(p24)) for t, _, p24 in CHANCE_HISTORY]
    assert got['xs'] == 24 and near(got['line'], line), (got['xs'], got['line'][:3], line[:3])
    assert near(got['wash'], [(line[0][0], Y(0))] + line + [(line[-1][0], Y(0))]), got['wash'][:3]
    assert near(got['marks'], [line[-1]]), got['marks']
    pct = lambda v: f'{float(f"{100 * v:.2g}"):g}%'               # as the page writes a chance: 2 significant digits
    clock = lambda t: time.strftime('%Y-%m-%d %H:%M', time.localtime(t))   # as the page writes a time (its local)
    p6, p24 = (CHANCE['p'][CHANCE_HOURS.index(t)] for t in (6, 24))
    assert got['stated'] == {'6': pct(p6), '24': pct(p24)} == {'6': '0.91%', '24': '2.8%'} and got['spent'] == '2.1', got['stated']
    (t24, _, last), (t11, _, eleventh) = CHANCE_HISTORY[-1], CHANCE_HISTORY[10]
    assert got['rest'] == ['hidden', [clock(t24), f'24{h}', pct(last)]] and pct(last) == '0.68%', got['rest']
    assert got['hovered'][:3] == ['visible', [clock(t11), f'24{h}', pct(eleventh)], 'visible'] and pct(eleventh) == '2%', got['hovered']
    assert abs(got['hovered'][3] - got['hovered'][4]) < 0.05 and got['left'] == ['hidden', 'hidden'], (got['hovered'], got['left'])
    assert got['empty'] == dict(line=0, marks=0, stated={'6': '—', '24': '—'}, spent='2.1', tip=[],
                                pticks=['0', '0.2', '0.4', '0.6', '0.8', '1%'], tticks=['0', '0.05', '0.1', '0.15', '0.2', f'0.25{h}']), got['empty']
    assert got['unrated'] == dict(line=24, marks=1, stated={'6': '—', '24': '—'}, tip=[clock(t24), f'24{h}', '0.68%']), got['unrated']


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
    # graph, right? i guess what we'd need is a way to make the distinction clear between historical vs projected";
    # then 2026-10-30: "maybe when showing the italicized hovertext for hovering over future points, that blurb should
    # have just the median, not ranges?"): past its last record the chart draws the median's course alone, the dashed
    # ideal line down to the projected finish, and no band, so there the tip reads out that course, in italics (class
    # projected): the clock and the hours so far half an hour on, 2.5 h so far, the median half an hour lower and no
    # lower than 0, 0.5 h to go, so 3.0 h in all and the median's finish time, the record's time plus its median
    # (moment); the cross line at the pointer; over a record, no italics; and the status line below the chart did not
    # move.  (From 2026-10-18 until then the band, carried on the same way.)
    R = progress_run()
    E, h = R['eta'], NNBSP + 'h'
    t = PROGRESS_DATA['made'] + 1800
    want = f'@{stamp(t)}{EMSP}2.5{h} so far + 0.5{h} to go = 3.0{h} ({moment(t, t + 1800)})'
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
    # 15.62 to 20 h, labeled 20 h (q_progress_breaks_the_y_axis_above_the_projected_finish).  And since 2026-11-04
    # (dreeves, of a break only where it gives the main panel a larger scale than one axis up to the tallest value
    # would: "sounds like your principled fix should work. updating the quals is fine."), no break here: the band top,
    # 16.2 h, is only 1.04 times that cap, so one axis runs up to it, gridlines at 5, 10 and 15 h, labeled to 15 h, its top
    # edge at 16.2 h, with nothing in a top panel, the slashes hidden and the y axis's line whole.
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
    cap = 16.2                                                           # the one panel's cap, h: the tallest value
    YB = YT = Y(cap)                                                     # its top edge, the plot's: no top panel
    def Ys(h): return Y(h)
    def check(got, want, what): assert len(got) == len(want) and all(near(g, (X(a), Ys(b))) for g, (a, b) in zip(got, want)), (what, got, [(X(a), Ys(b)) for a, b in want])
    for k, w in (('spent', [(0, 0), (13.2, 13.2)]), ('togo', [(0, 2), (13.2, 1)]), ('total', [(0, 2), (13.2, 14.2)]),
                 ('guide', [(13.2, 14.2), (14.2, 14.2), (14.2, 0)])): check(polys[k], w, k)
    bands = {a['class']: pts(a['points']) for tag, a, _ in els if tag == 'polygon'}
    assert sorted(bands) == ['band togo', 'band total'], bands.keys()
    check(bands['band togo'], [(0, 4), (13.2, 3), (13.2, 0.5), (0, 1)], 'band togo')
    check(bands['band total'], [(0, 4), (13.2, 16.2), (13.2, 13.7), (0, 1)], 'band total')   # within the one panel (2026-11-04)
    lines = [(a['class'], tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2')), a) for tag, a, _ in els if tag == 'line']
    assert sorted(c for c, _, _ in lines) == sorted(['axis', 'ahead', 'ideal', 'range togo', 'range total', 'cross'] + ['grid'] * 3 + ['break'] * 2 + ['yaxis'] * 2), [c for c, _, _ in lines]
    assert all(a.get('visibility') == 'hidden' for c, _, a in lines if c == 'break'), lines
    seg = {c: s for c, s, _ in lines if c not in ('grid', 'break', 'yaxis')}
    check([seg['ahead'][:2], seg['ahead'][2:]], [(13.2, 13.2), (14.2, 14.2)], 'ahead')
    check([seg['ideal'][:2], seg['ideal'][2:]], [(13.2, 1), (14.2, 0)], 'ideal')
    check([seg['range togo'][:2], seg['range togo'][2:]], [(13.2, 0.5), (13.2, 3)], 'range togo')
    check([seg['range total'][:2], seg['range total'][2:]], [(13.2, 13.7), (13.2, 16.2)], 'range total')
    assert abs(seg['axis'][1] - Y(0)) < 0.05 and seg['axis'][1] == seg['axis'][3], seg['axis']
    grid = [s for c, s, _ in lines if c == 'grid' and s[1] > YB]       # the main panel's
    hours = sorted((y0 - g[1]) / (y0 - Y(1)) for g in grid)              # to 0.01 h: positions are written to 0.01 units
    assert len(hours) == 3 and all(abs(h - t) < 0.01 for h, t in zip(hours, (5, 10, 15))) and all(g[1] == g[3] for g in grid), grid
    assert [s[1] for c, s, _ in lines if c == 'grid' and s[1] < YB] == [], lines       # no top panel (2026-11-04)
    assert sorted(round(y, 2) for c, s, _ in lines if c == 'yaxis' for y in (s[1], s[3])) == sorted([round(YT, 2), round(YB, 2), 14, round(Y(0), 2)]), lines   # its y axis's ends at the break
    cross = next(a for c, _, a in lines if c == 'cross')
    assert cross.get('visibility') == 'hidden', cross
    yt = [(float(a['y']), text) for tag, a, text in els if tag == 'text' and a.get('class') == 'ytick']
    assert [v for _, v in yt] == ['0', '5', '10', '15\u202fh'] and all(abs(y - 4 - Ys(int(v.split()[0]))) < 0.05 for y, v in yt), yt   # up to the cap, 16.2 h (2026-11-04; to the cap 15.62 h, then the top panel's 20 h, from 2026-10-23; to 20 h before)
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
    style = re.sub(r'/\*.*?\*/', '', page_css(), flags=re.S)   # live rules only
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
