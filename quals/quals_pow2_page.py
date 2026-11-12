#!/usr/bin/env python3
"""Quals for index.html's chart of the bounds on m*(2^k) - k, the excess over Thue-Morse at the powers of 2, for k up
to 72: the section "pow2" right after the m*(n) chart, drawn from pow2.js.  Run: python3 -B quals/quals_pow2_page.py
[name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The static quals read index.html, its stylesheet and scripts in page/ (inline in it until 2026-10-31) and pow2.js.  The
browser quals load copies of index.html, each with page/ and mstar.js beside it and a pow2.js (the real
one, made-up data, or none), in headless Chrome driven through the DevTools protocol by DRIVER, a Node script: a true
viewport of each configuration's width and pixel ratio, its theme by prefers-color-scheme, real mouse moves, touch taps
and swipes, and screenshots whose pixels are checked against the data.  DRIVER finds the cells by geometry alone: the
plot is the svg in #pow2-chart, K columns of equal width, and rows ROW CSS px apart from the top (row E) down to row 1,
the bottom device pixel of each row and one between every two columns page surface: a hairline grid (since 2026-10-29;
the bottom 2 CSS px before).

Spec changes (dreeves, 2026-11-09: "we need more quals for substantive things and fewer quals enforcing words on the
page", and "i stand by the point about quals enforcing specific prose on the page being pretty useless";
quals_index.py's header has the whole of it): a credit of the new results is the class of its cells, worded by the
page's legend; and no qual here asks for words to be on the page, index.html's or a script's (a readout's sentences).
Where a comment quotes a sentence, the qual holds the sentence's figures, its numbers, math and codes
(quals_index.figures, among).
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, time, shutil, tempfile, traceback, subprocess, itertools
from math import prod, floor
from PIL import Image
import quals_index as qi                      # read only: page_css, page_scripts, copy_page_dir (the page's files, page/)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
INDEX = os.path.join(HERE, 'index.html')
DATA = qi.POW2                                # made by pow2.py; the chart's data (in pagedata/ since 2026-11-10, [REF])
MSTAR = qi.DATA                               # made by mstar.py; the m*(n) chart's data, which the page also loads
ICONS = ('favicon.ico', 'favicon.svg', 'apple-touch-icon.png')   # the page's icons, which it also loads
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
K, ROW = 72, 14                               # columns k = 1..K; rows ROW CSS px apart, the bottom gap() of each surface


def gap(dpr):
    """The hairline between rows and between columns, in CSS px: one device pixel (dreeves, 2026-10-29: "this with
    hairline grid looks great to me")."""
    return 1 / dpr
KINDS = ('exists', 'open', 'impossible')      # the kinds of cell, as the tokens of their colors name them
F = [2 ** 24, 25]                             # f, the 2^24 construction, as [n, m]: a block until 2026-10-29, now none
KLABELS = list(range(10, K + 1, 10))          # the k labels below the plot
OUTLINE = (36, 5)                             # the cell whose outline the screenshots check
# the targets of the boxes' clicks (2026-11-04, [CEL] and [ROC]): cells [k, δ], a column's k label [k, None] and rows' δ
# labels [None, δ]; and the progress.js of the page copies, with no runs (an open cell's box loads it)
BOX_TARGETS = [[30, 2], [30, 8], [30, 5], [10, 1], [9, 1], [20, 2], [13, 2], [30, None], [None, 3], [None, 12]]
NO_RUNS = {'made': 1792200000, 'runs': []}
SWIPE = (29, 8)                               # the cell a phone's swipe starts on, after the outline's tap
MSTAR_LAYOUT = (44, 16, 2, 14)                # the m*(n) chart's plot: left and right gutters, top, row pitch (CSS px)
NMAX = int(re.search(r'"nmax": (\d+)', open(MSTAR, encoding='utf-8').read()).group(1))   # the m*(n) chart's data's last n (2048 since 2026-11-10, [BOU]; 1024 before)
# The m*(n) chart's last n as the page loads, its cap pressed then (1024; the data's last n until 2026-11-10, when the
# caps came, dreeves's README [BOU]), and its columns' n then, since 2026-10-29 (every even n before).
MSTAR_CAP = int(re.search(r'data-cap="(\d+)" aria-pressed="true"', open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()).group(1))
MSTAR_COLUMNS = [2] + list(range(4, MSTAR_CAP + 1, 4))
RUNS = {}                                     # DRIVER's reports by configuration name, made once per process (see run)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the page and the data

def page(): return open(INDEX, encoding='utf-8').read()


def chart_script():
    """This chart's script: the one of the page's own scripts that gets #pow2-chart (page/pow2-section.js since
    2026-10-31; an inline script before, the page's second until 2026-10-30, when an inline script for KaTeX came first
    in the head)."""
    [js] = [s for s in qi.page_scripts(page()) if "getElementById('pow2-chart')" in s]
    return js


def theme_blocks():
    """The custom properties of the page's one theme block, :root, as a one-item list (dreeves, 2026-10-12: no dark
    mode, so no other theme block)."""
    css = qi.page_css()
    whole = page() + css + ''.join(qi.page_scripts(page()))        # the page with its stylesheet and scripts
    ms = list(re.finditer(r'\n:root \{(.*?)\n\s*\}', css, re.S))
    assert len(ms) == 1 and 'prefers-color-scheme' not in whole and 'data-theme' not in whole
    return [dict(re.findall(r'(--[\w-]+):\s*([^;]+);', ms[0].group(1)))]


def pow2_of(js):
    """POW2 as the browser sees it: node runs the text of a pow2.js and prints POW2 as JSON."""
    p = subprocess.run(['node', '-e', js + '\nprocess.stdout.write(JSON.stringify(POW2))'], capture_output=True,
                       text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def real():
    """The text of the real pow2.js."""
    assert os.path.exists(DATA), DATA
    return open(DATA, encoding='utf-8').read()


# ---------------------------------------------------------------------------------------------------------------------
# What the readout writes (the expectations of the readout quals)

def sub(k): return f'_({k})'                  # a subscript, as DRIVER's TEXT writes a <sub>


def block(b):
    """A block of a join's product, as the readout names it: τ_j for Thue-Morse [2^j, j], else p_n (and f for the
    2^24 construction until 2026-10-29)."""
    n, m = b
    return f'τ{sub(m)}' if n == 2 ** m else f'p{sub(n)}'


def join_text(products): return ' ∨ '.join('(' + ' # '.join(map(block, p)) + ')' for p in products)


def reason_math(k, why):
    """What tells a reason apart in the readout: its math, as the readout writes it; for a result of the page's own, its
    credit in parentheses, as the legend words it.  (Until 2026-11-09 a residue condition's was "mod M" and the paper's
    table's "Table 2", words of the readout's sentences; since then their numbers.)"""
    kind, *args = why
    mstar = {'two': lambda: str(2 ** k), 'norm': lambda p: f'p\xa0=\xa0{p}', 'residue': lambda M: str(M),
             'table2': lambda: '2', 'page': lambda who: f'({qi.legend_labels(qi.page())[who]})'}   # a credit, the class of its cells, as the legend words it
    return {'thue-morse': lambda: f'τ{sub(k)}', 'joins': join_text, 'mstar': lambda w: mstar[w[0]](*w[1:]), 'norm': lambda p: f'p\xa0=\xa0{p}',
            'residue': lambda chain: ', '.join(map(str, chain))}[kind](*args)


def reason_holds(p, k, order, why):
    """Whether p, a reason in the readout of column k, names its order first (its first number, after a quotation's
    opening if it has one) and then holds what tells it apart (reason_math): a credit as it stands, anything else by
    its figures (quals_index.among).  (Until 2026-11-09: whether it started "order N" and held the math as written.)"""
    m = re.match(rf'(?:{qi.OPENING})?\D*?(\d+)', p)
    credit = why[0] == 'mstar' and why[1][0] == 'page'
    return bool(m) and int(m.group(1)) == order and (reason_math(k, why) in p if credit else qi.among(reason_math(k, why), p[m.end():]))


# A readout's text, each <sup> written ^(…) and each <sub> _(…): the cell, its meaning, the column's bounds, then the
# reasons.
READOUT = re.compile(r'k = (\d+), n = 2\^\((\d+)\), m = (\d+) \+ (\d+) = (\d+) · ([^·]+) · '
                     r'(\d+) ≤ m\^\(\*\)\(2\^\((\d+)\)\) ≤ (\d+) · (.*)')


def kind_of(col, k, e): return (k + e > col[0]) + (k + e > col[1])     # 0 exists, 1 open, 2 impossible
# (Until 2026-11-09 each kind's word in the readout was asked for: known, open and impossible, dreeves's of 2026-10-12.
# Since then: the cells of a kind say one thing, and the three kinds three things: check_readouts.)


def ring_cells(data):
    """The cells the chart rings in gold (dreeves's README, 2026-10-30, [GLT]), in the page's order: for each δ = e from 1
    while some k <= K is not ruled out to beat Thue-Morse by e, (k, e, role) for the least k known to and for the least
    k whose upper bound allows k + e, one cell when they agree, none for a k not known; role 1 known (a bound the
    theorem states), 2 not ruled out, 3 both, proven the least.  (Until then, the known ones alone; and until dreeves
    asked "why isn't 480:14 highlighted in the chart?", 2026-10-30, only for each e some k was known to reach.)"""
    cols, out = data['cols'], []
    least = lambda i: lambda g: next((k for k, c in enumerate(cols, 1) if c[i] >= k + g), 0)
    for g in range(1, data['etop'] + 1):
        known, possible = least(0)(g), least(1)(g)
        if not possible: break
        out += [(k, g, (k == known) + 2 * (k == possible)) for k in dict.fromkeys((known, possible)) if k]
    return sorted(out)                                            # the page's order: by k, then δ (raised, 2026-10-30)


NOTES = {1: 1, 2: 1, 3: 2}      # the notes a ringed cell's readout adds after its reasons, by role


def check_readouts(data, reads):
    """Assert that reads, [k, e, {text, children}] for every cell, are each that cell's readout (see
    q_hover_reads_out_every_cell)."""
    E, cols, meaning, notes = data['etop'], data['cols'], {}, {}
    assert sorted((k, e) for k, e, _ in reads) == [(k, e) for k in range(1, K + 1) for e in range(1, E + 1)]
    gold = {(k, e): role for k, e, role in ring_cells(data)}      # the smallest cells, ringed in gold, by role
    for k, e, r in reads:
        lo, hi, lw, hw = cols[k - 1]
        kind, role = kind_of(cols[k - 1], k, e), gold.get((k, e), 0)
        g = READOUT.fullmatch(r['text'])
        assert g and [int(g[i]) for i in (1, 2, 3, 4, 5, 7, 8, 9)] == [k, k, k, e, k + e, lo, k, hi], (k, e, r)
        assert r['children'][:1] == [f'swatch {KINDS[kind]}' + ' record' * (role > 0) + ' proven' * (role == 3)], (k, e, r)
        meaning.setdefault(kind, set()).add(g[6])
        parts = g[10].split(' · ')       # each reason names its order and holds its math (pinned as Claude: "order …" until 2026-10-30)
        want = [(lo, lw), (hi + 1, hw)]
        want = [want[:1], want, want[1:]][kind]
        extra = NOTES.get(role, 0)       # a gold cell's notes after its reasons, each naming its δ
        assert len(parts) == len(want) + extra, (k, e, r, want)
        assert all(reason_holds(p, k, o, why) for p, (o, why) in zip(parts, want)), (k, e, r, want)
        assert all(re.search(rf'\b{e}\b', p) for p in parts[len(want):]), (k, e, r)
        if extra: notes.setdefault(role, set()).add(' · '.join(re.sub(r'\d+', '#', p) for p in parts[len(want):]))
    assert all(len(v) == 1 for v in meaning.values()) and len(set.union(*meaning.values())) == len(meaning), meaning
    assert all(len(v) == 1 for v in notes.values()) and len(set.union(*notes.values())) == len(notes), notes


# ---------------------------------------------------------------------------------------------------------------------
# Made-up data

def norm(n, p):
    """mstar.py's norm lemma in exact integers: the largest m with p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1),
    size(p, r) the number of i in 0..n-1 with i = r (mod p)."""
    rhs = (p * sum(((n - r + p - 1) // p) ** 2 for r in range(p))) ** (p - 1)
    m = 0
    while p ** (2 * m + 2) * (p - 1) ** (p - 1) <= rhs: m += 1
    return m


# Joins of products of blocks: the 2^24 construction itself, and Stong's 2^51 (BGPW Theorem 7.1), whose p_16 and
# p_8192 are Thue-Morse's τ_4 and τ_13.
JOIN24 = [[[112, 7], [320, 9], [320, 9]], [[432, 11], [48, 6], [256, 8]]]
STONG = [[[144, 8]] * 2 + [[192, 9]] * 4, [[48, 6]] * 3 + [[112, 7]] + [[192, 9]] * 3,
         [[16, 4], [112, 7], [112, 7], [208, 8], [272, 8], [192, 9], [192, 9]],
         [[112, 7]] + [[208, 8]] * 4 + [[8192, 13]]]


def f_power(L, j):
    """f^{#L} # τ_j written out as a join of products of blocks, f the 2^24 construction JOIN24: by distributivity, one
    product per choice of one of JOIN24's two products for each of the L factors f, times τ_j ([2^j, j]) when j > 0.
    Its lengths sum to 2^(24L + j) and its order is 25L + j."""
    return [sum(choice, []) + [[2 ** j, j]] * (j > 0) for choice in itertools.product(JOIN24, repeat=L)]


def kinds_cols():
    """Made-up columns that follow the contract and use every kind of reason: k <= 9 from Thue-Morse, settled by each
    kind of the m*(n) chart's hiWhy; then lo = k + floor(k / 24) (Thue-Morse, then f^{#L} # τ_j written out as a join,
    f_power) and hi the norm bound for p = 3, but for a few columns with other joins, of τ_j (j above 9) and columns of
    mstar.js (the last, 1024, at order 11, the page's example p_1024), Stong's among them; residue chains; the norm
    bound for p = 5 and 7.  (Until 2026-10-29 those joins of f were the kind power, f^{#L} # τ_j, and two joins had f
    as a block.)"""
    cols = []
    for k in range(1, K + 1):
        L, j = divmod(k, 24)
        cols.append([k + L, norm(2 ** k, 3), ['joins', f_power(L, j)] if L else ['thue-morse'], ['norm', 3]])
    whys = {1: ['two'], 2: ['norm', 3], 3: ['table2'], 4: ['page', 's'], 5: ['residue', 9],
            6: ['page', 'c'], 7: ['residue', 3], 8: ['table2'], 9: ['page', 'j']}
    for k, why in whys.items(): cols[k - 1] = [k, k, ['thue-morse'], ['mstar', why]]
    joins = {34: [p + [[1024, 10]] for p in JOIN24], 35: [[[1024, 11], [2 ** 25, 25]]], 51: STONG}
    for k, ps in joins.items():
        assert sum(prod(n for n, _ in p) for p in ps) == 2 ** k
        cols[k - 1] = [min(sum(m for _, m in p) for p in ps), norm(2 ** k, 3), ['joins', ps], ['norm', 3]]
    cols[9] = [10, 10, ['thue-morse'], ['residue', [3, 9, 27]]]
    cols[10] = [11, 12, ['thue-morse'], ['residue', [5]]]
    cols[11] = [12, norm(2 ** 12, 5), ['thue-morse'], ['norm', 5]]
    cols[12] = [13, norm(2 ** 13, 7), ['thue-morse'], ['norm', 7]]
    return cols


def quoted(*what):
    """An assert's quote of what, as the page writes it: JSON with ' for "."""
    return json.dumps(list(what), ensure_ascii=False, separators=(',', ':')).replace('"', "'")


def column(k, entry):
    """A change to made-up data: column k becomes entry; the error quotes [k, entry]."""
    def change(data): data['cols'][k - 1] = entry
    return change, quoted(k, entry)


C30 = kinds_cols()[29]                        # [31, 37, ['joins', f_power(1, 6)], ['norm', 3]]
VIOLATIONS = {   # name: (a change that breaks the contract, what the page's error line must quote)
    'lo below k': column(30, [29, 37, ['thue-morse'], ['norm', 3]]),
    'lo above hi': column(30, [38, 37, C30[2], ['norm', 3]]),
    'hi at etop': column(30, [31, 49, C30[2], ['norm', 3]]),
    'five entries': column(30, C30 + [0]),
    'unknown lo kind': column(30, [31, 37, ['guess'], ['norm', 3]]),
    'unknown hi kind': column(30, [31, 37, C30[2], ['guess']]),
    'arity': column(30, [30, 37, ['thue-morse', 1], ['norm', 3]]),
    'thue-morse lo': column(30, [31, 37, ['thue-morse'], ['norm', 3]]),
    'power kind': column(30, [31, 37, ['power', 1, 6], ['norm', 3]]),     # f^{#1} # τ_6, a kind until 2026-10-29
    'joins length': column(30, [31, 37, ['joins', [[[2 ** 24, 24], [32, 5]]]], ['norm', 3]]),
    'joins lo': column(30, [32, 37, ['joins', [[[2 ** 24, 24], [64, 6]]]], ['norm', 3]]),
    'joins f': column(30, [31, 37, ['joins', [[F, [64, 6]]]], ['norm', 3]]),       # f, a block until 2026-10-29
    # [4096, 13] since 2026-11-10: [2048, 12], the block here until then, is a column of the m*(n) chart since it reaches 2048 ([BOU])
    'joins block': column(30, [31, 37, ['joins', [[[4096, 13], [262144, 18]]]], ['norm', 3]]),
    'joins empty': column(30, [31, 37, ['joins', []], ['norm', 3]]),
    'mstar above 11': column(12, [12, 12, ['thue-morse'], ['mstar', ['residue', 3]]]),   # above 10, at k = 11, until 2026-11-10 ([BOU])
    'mstar kind': column(5, [5, 5, ['thue-morse'], ['mstar', ['guess']]]),
    'mstar two': column(2, [2, 2, ['thue-morse'], ['mstar', ['two']]]),
    'norm composite': column(30, [31, 37, C30[2], ['norm', 9]]),
    'norm two': column(30, [31, 37, C30[2], ['norm', 2]]),
    'norm bound': column(30, [31, 38, C30[2], ['norm', 3]]),
    'residue chain': column(30, [31, 37, C30[2], ['residue', [9, 3]]]),
    'residue one': column(30, [31, 37, C30[2], ['residue', [1]]]),
    'etop': (lambda data: data.update(etop=data['etop'] + 1), '[20]'),
    'kmax': (lambda data: data.update(kmax=71), '[71,19]'),
    'cols': (lambda data: data.update(cols=data['cols'][:-1]), '[72,19]'),
    'extra key': (lambda data: data.update(note='x'), "[['kmax','etop','cols','note']]"),
}


def kinds_data(violation=None):
    """pow2.js's text for kinds_cols, broken by the change in VIOLATIONS that violation names, if given."""
    cols = kinds_cols()
    data = {'kmax': K, 'etop': max(c[1] - k for k, c in enumerate(cols, 1)) + 1, 'cols': cols}
    assert data['etop'] == 19
    if violation: VIOLATIONS[violation][0](data)
    return 'const POW2 = ' + json.dumps(data, ensure_ascii=False) + ';\n'


SOURCES = {'real': real, 'kinds': kinds_data} | {v: (lambda v=v: kinds_data(v)) for v in VIOLATIONS}


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

# Ending a process group by its leader's pid, as DRIVER ends Chrome's: Chrome's helpers stay in its group and can
# outlive its main process for a moment, writing into the profile that run deletes next (2026-10-26: "Directory not
# empty", twice).  endGroup sends SIGTERM to the whole group, whether or not its leader has exited, waits until no
# process of it remains, sends SIGKILL after term ms, and fails loudly if any of it outlives that by kill ms.  ESRCH
# says none remain; EPERM that some do, though none may be signalled, as a zombie not yet reaped (macOS).
GROUP_JS = r"""
const groupSignal = (pid, sig) => { try { process.kill(-pid, sig); } catch (e) { if (e.code !== 'ESRCH' && e.code !== 'EPERM') throw e; } };
const groupAlive = pid => {
  try { process.kill(-pid, 0); return true; } catch (e) { if (e.code !== 'ESRCH' && e.code !== 'EPERM') throw e; return e.code === 'EPERM'; }
};
const groupGone = async (pid, ms) => {
  for (const end = Date.now() + ms; groupAlive(pid) && Date.now() < end;) await new Promise(r => setTimeout(r, 100));
  return !groupAlive(pid);
};
const endGroup = async (pid, term = 10000, kill = 5000) => {
  for (const [sig, ms] of [['SIGTERM', term], ['SIGKILL', kill]]) { groupSignal(pid, sig); if (await groupGone(pid, ms)) return; }
  throw new Error(`process group ${pid} outlived SIGKILL`);
};
"""

DRIVER = r"""
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
""" + GROUP_JS + r"""
const C = JSON.parse(readFileSync(0, 'utf8'));
// C.headless: quals_index's HEADLESS, the flags every headless Chrome of the quals starts with (2026-11-10; until then
// this list had its own).  Among them --allow-file-access-from-files (2026-10-31): the page's scripts are files of page/,
// and plain file:// gives each file an origin of its own, so an uncaught error thrown in them came through only as text,
// with no exception object; over http(s), where the page is served, they share its origin, as they do here with the flag
// (quals_index's chrome)
const chrome = spawn(C.chrome, [...C.headless, '--remote-debugging-port=0', `--user-data-dir=${C.dir}/profile`,
  '--hide-scrollbars', '--disable-ipc-flooding-protection', 'about:blank'],
  {stdio: 'ignore', detached: true});
const watchdog = setTimeout(() => { groupSignal(chrome.pid, 'SIGTERM'); process.exit(3); }, 400000);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// In the page.  TEXT: an element's text, each <sup> written ^(…) and each <sub> _(…).
const TEXT = el => {
  const c = el.cloneNode(true);
  c.querySelectorAll('sup').forEach(s => s.replaceWith(`^(${s.textContent})`));
  c.querySelectorAll('sub').forEach(s => s.replaceWith(`_(${s.textContent})`));
  return c.textContent;
};
const PROBE = text => {
  const sec = document.querySelector('section.pow2'), chart = document.getElementById('pow2-chart');
  const ro = document.getElementById('pow2-readout'), css = getComputedStyle(document.documentElement);
  const tokens = ['exists', 'open', 'impossible', 'paper', 'ink', 'record', 'rule'].map(t => [t, css.getPropertyValue('--' + t).trim()]);
  const page = document.documentElement;
  const attrs = el => ['aria-label', 'title', 'alt'].filter(a => el.hasAttribute(a)).map(a => el.getAttribute(a));
  return {innerWidth, dpr: devicePixelRatio, dark: matchMedia('(prefers-color-scheme: dark)').matches,
    scrollW: page.scrollWidth, tokens: Object.fromEntries(tokens.map(([t, v]) => [t, v.toLowerCase()])),
    text: sec.innerText, readout: text(ro), live: ro.getAttribute('aria-live'), chartNodes: chart.childNodes.length,
    attrs: [...sec.querySelectorAll('*')].flatMap(attrs),
    canvasH: document.getElementById('mstar-chart').getBoundingClientRect().height};
};
const GEOMETRY = () => {
  const chart = document.getElementById('pow2-chart'), svg = chart.querySelector('svg');
  const box = r => [r.left, r.top, r.width, r.height], texts = [];
  const walk = document.createTreeWalker(chart, NodeFilter.SHOW_TEXT);
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    const r = document.createRange();
    r.selectNodeContents(t);
    texts.push([t.textContent, box(r.getBoundingClientRect())]);
  }
  const trims = [...chart.querySelectorAll('.pow2-trim')].map(el => { const s = getComputedStyle(el);
    return [box(el.getBoundingClientRect()), s.borderTopColor, s.borderTopWidth, s.borderLeftWidth, s.pointerEvents]; });
  const dots = [...chart.querySelectorAll('.pow2-dot')].map(el => { const s = getComputedStyle(el);
    return [box(el.getBoundingClientRect()), s.backgroundColor, s.borderTopLeftRadius, s.pointerEvents]; });
  return {plot: box(svg.getBoundingClientRect()), svgs: chart.querySelectorAll('svg').length,
    rects: svg.querySelectorAll('rect').length, texts, trims, dots, innerWidth, scrollW: document.documentElement.scrollWidth,
    canvas: box(document.getElementById('mstar-chart').getBoundingClientRect())};
};
const DOM = cells => cells.map(([k, e, x, y]) => {
  const el = document.elementFromPoint(x, y);
  return [k, e, el.tagName.toLowerCase(), getComputedStyle(el).fill];
});
const READ = text => {
  const ro = document.getElementById('pow2-readout');
  const children = [...ro.children].map(c => c.className);
  // the tags of the cell read out (2026-11-02, [HOV]): each .pow2-tag in #pow2-chart as [its text, whether it shows,
  // its box, its computed background and color, the id of the image that holds it for assistive technology]
  const tags = [...document.querySelectorAll('#pow2-chart .pow2-tag')].map(t => {
    const r = t.getBoundingClientRect(), s = getComputedStyle(t);
    return [t.textContent, t.checkVisibility(), [r.left, r.top, r.width, r.height], s.backgroundColor, s.color,
            t.closest('[role="img"]')?.id];
  });
  return {text: text(ro), children, scrollW: document.documentElement.scrollWidth, tags};
};
const FRAMES = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
// The panel of the chart's columns ([REO], 2026-11-03), as it stands: whether it is hidden, the page's fragment,
// whether its heading has the focus and which element has it, the kinds of its texts (data-why) in order, its heading
// and text with each formula KaTeX drew written back as its TeX, \( ... \), its links' hrefs, KaTeX's error marks in it,
// and the page's width and the window's then.  (Each panel opens with a change of the page's address, and 72 of them
// and a phone's 1296 taps pass Chrome's limit of 200 such changes per 10 s, which --disable-ipc-flooding-protection
// lifts.)
// Since [REO] step 2 (2026-11-03) a panel also shows the remarks' entry of its length, the li that holds its p.entry,
// moved in: the text and links leave out the entries it shows, and the panel gives their p.entry ids (entries) and texts
// (entryText) apart, with the ids of the p.entry still in the remarks' list, in order (listed), and the ids that two
// elements of the page share (dups), as quals_index's panelReport does.
const PANEL = () => {
  const region = document.getElementById('pow2-panel'), c = region.cloneNode(true), HELD = 'li:has(> p.entry)';
  c.querySelectorAll('.katex').forEach(k => k.replaceWith(`\\(${k.querySelector('annotation').textContent}\\)`));
  const held = [...c.querySelectorAll(HELD)], ids = [...document.querySelectorAll('[id]')].map(e => e.id);
  held.forEach(li => li.remove());
  return {hidden: region.hidden, hash: location.hash, focus: document.activeElement === region.querySelector('h3'),
    active: document.activeElement.id, whys: [...region.querySelectorAll('[data-why]')].map(e => e.dataset.why),
    heading: c.querySelector('h3').textContent, text: c.textContent.replace(/\s+/g, ' ').trim(),
    links: [...region.querySelectorAll('a[href]')].filter(a => !a.closest(HELD)).map(a => a.getAttribute('href')),
    errors: region.querySelectorAll('.katex-error').length, scrollW: document.documentElement.scrollWidth, innerWidth,
    entries: held.map(li => li.querySelector('p.entry').id), entryText: held.map(li => li.textContent.replace(/\s+/g, ' ').trim()),
    listed: [...document.querySelectorAll('section.remarks ul > li > p.entry')].map(p => p.id),
    dups: ids.filter((x, i) => ids.indexOf(x) !== i),
    // since 2026-11-04 ([CEL], [ROC]), as quals_index's panelReport: the box's kind, its parts as [kind, text, whether of
    // Claude's English], its copies of codes and its constructions
    kind: region.dataset.kind ?? null,
    parts: [...c.querySelectorAll('[data-panel-body] > [data-why]')].map(e => [e.dataset.why, e.textContent.replace(/\s+/g, ' ').trim(),
                                                                              e.hasAttribute('data-claude')]),
    copies: [...c.querySelectorAll('[data-panel-body] [data-join]')].map(e => [e.dataset.join, e.dataset.order, e.getAttribute('role'), e.textContent]),
    constructions: [...c.querySelectorAll('[data-panel-body] [data-construction]')].map(e => [e.dataset.construction, e.getAttribute('role'),
                                                                                              e.textContent.trim()])};
};
const HASHED = h => new Promise(r => { addEventListener('hashchange', () => r(), {once: true}); location.hash = h; });
// The boxes of the chart's cells, columns and rows (2026-11-04, dreeves's README items [CEL] and [ROC]).  PLACE(t): where
// the target t is in the full view, in CSS px of the viewport: a cell's middle, [k, e]; for a column, [k, null], 10 px
// under its column's middle; for a row, [null, e], the middle of the δ labels' strip at its row.  BOX(t): the box as it
// stands after a click there (PANEL's report), with its frame's color, its caret's middle and the middle there of the
// target's column (or the δ labels' strip), the box of the outline of its target (pin: the frame's last outline) and
// the box it should have (want: 2 px around the target's cells), the heading's swatch, the fill of the cell under the
// target, the text of its parts of the kinds witness-* and proof-* (said), its searches' text as shown and the cells of
// its tables.  LOADED: until
// the box's searches, if it has any, have loaded (at most 3 s).  DERIVED: a click on each of the box's constructions,
// and each one's claim, its derivation's bound and whether its derivation shows.
const PLACE = ([k, e]) => {
  const c = document.getElementById('pow2-chart').getBoundingClientRect(), s = document.querySelector('#pow2-chart svg').getBoundingClientRect();
  const E = POW2.etop, ROW = 14;
  return [k === null ? c.left + (s.left - c.left) / 2 : s.left + (k - 0.5) * s.width / 72, e === null ? s.bottom + 10 : s.top + (E - e) * ROW + 6.5];
};
const BOX = (t, PLACE, PANEL) => {                 // PLACE and PANEL passed in, as the page knows neither
  const region = document.getElementById('pow2-panel'), body = region.querySelector('[data-panel-body]');
  const hex = rgb => '#' + rgb.match(/\d+/g).slice(0, 3).map(v => (+v).toString(16).padStart(2, '0')).join('');
  const tex = e => { const c = e.cloneNode(true);
    c.querySelectorAll('.katex').forEach(x => x.replaceWith(`\\(${x.querySelector('annotation').textContent}\\)`));
    return c.textContent.replace(/\s+/g, ' ').trim(); };
  const s = document.querySelector('#pow2-chart svg').getBoundingClientRect(), E = POW2.etop, ROW = 14, GAP = 1 / devicePixelRatio;
  const [k, e] = t, [c0, c1] = k === null ? [0, 72] : [k - 1, k], [e0, e1] = e === null ? [1, E] : [e, e];
  const pin = [...document.querySelectorAll('#pow2-chart .pow2-frame > .pow2-outline')].at(-1), p = pin.getBoundingClientRect();
  const before = getComputedStyle(region, '::before'), b = region.getBoundingClientRect(), sw = region.querySelector('h3 .swatch');
  const [x, y] = PLACE(t), under = t.includes(null) ? null : document.elementFromPoint(x, y);
  return {target: t, ...PANEL(), frame: hex(getComputedStyle(region).borderTopColor),
    caret: b.left + region.clientLeft + parseFloat(before.left) + parseFloat(before.borderLeftWidth), column: x,
    pin: [p.left, p.top, p.right, p.bottom], pinHidden: pin.hidden,
    want: [s.left + c0 * s.width / 72 - 2, s.top + (E - e1) * ROW - 2, s.left + c1 * s.width / 72 + 2, s.top + (E - e0) * ROW + ROW - GAP + 2],
    swatch: sw && {cls: sw.className, color: hex(getComputedStyle(sw).backgroundColor), ring: getComputedStyle(sw).boxShadow},
    fill: under && hex(getComputedStyle(under).fill),
    said: [...body.querySelectorAll(':scope > [data-why^="witness"], :scope > [data-why^="proof"]')].map(tex).join(' '),
    searches: [...body.querySelectorAll('[data-why="searches"]')].map(e => e.innerText),
    tables: [...body.querySelectorAll('table')].map(table => [...table.rows].map(tr => [...tr.cells].map(tex)))};
};
const LOADED = () => new Promise(r => { const t0 = Date.now(); const f = () => {
  const d = [...document.querySelectorAll('#pow2-panel [data-why="searches"] > div')];
  if (d.every(x => x.childNodes.length) || Date.now() - t0 > 3000) r(); else setTimeout(f, 50); }; f(); });
const DERIVED = () => [...document.querySelectorAll('#pow2-panel [data-panel-body] [data-construction]')].map(e => {
  e.click();
  const box = document.getElementById(e.getAttribute('aria-controls'));
  return [e.dataset.construction, box.querySelector('[data-bound]').textContent.replace(/\s+/g, ' ').trim(), box.checkVisibility()];
});
// The table of record gaps as the page draws it: its head's and its rows' cells, the math written back as TeX
const GAPS = () => [...document.querySelector('[data-record-gaps]').querySelectorAll('thead tr, tbody tr')].map(tr => [...tr.cells].map(c => {
  const x = c.cloneNode(true); x.querySelectorAll('.katex').forEach(k => k.replaceWith(`\\(${k.querySelector('annotation').textContent}\\)`));
  return x.textContent.replace(/\s+/g, ' ').trim(); }));
// Each zoom button of the two charts, mstar's and pow2's side by side: what of its look its computed style and box give,
// and its text, title and label (2026-10-30).
const LOOKS = () => ['zoom-out', 'zoom-in'].map(b => ['mstar', 'pow2'].map(p => {     // and 'reset' until 2026-11-10, when the m*(n) chart's gave way to its caps ([BOU])
  const e = document.getElementById(`${p}-${b}`), s = getComputedStyle(e), r = e.getBoundingClientRect();
  return [s.fontFamily, s.fontSize, s.color, s.backgroundColor, s.borderTopWidth, s.borderTopStyle, s.borderTopColor,
    s.paddingTop, s.paddingLeft, s.cursor, s.opacity, Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10,
    e.textContent, e.title, e.getAttribute('aria-label')];
}));

const out = C.urls.map(() => ({errors: []}));      // per page; anything logged before the first page goes to it
let ws, seq = 0, current = out[0];
const pending = new Map(), once = new Map();
const send = (method, params = {}) => new Promise((ok, no) => {
  const id = ++seq;
  pending.set(id, d => d.error ? no(new Error(`${method}: ${JSON.stringify(d.error)}`)) : ok(d.result));
  ws.send(JSON.stringify({id, method, params}));
});
const next = method => new Promise(r => once.set(method, r));       // the next event of the method
const ev = async (f, ...args) => {                                  // the value of f(...args) in the page
  const expression = `(${f})(${args.map(a => typeof a === 'function' ? String(a) : JSON.stringify(a)).join(', ')})`;
  const r = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  const thrown = JSON.stringify(r.exceptionDetails);
  if (thrown) throw new Error(`${expression.slice(0, 200)}: ${thrown.slice(0, 900)}`);
  return r.result.value;
};
const errors = {                     // the lines that each kind of event logs (none for a log entry below a warning)
  'Runtime.exceptionThrown': ({exceptionDetails: x}) =>
    `exception: ${x.text} ${(x.exception || {description: ''}).description.split('\n')[0]}`,
  'Runtime.consoleAPICalled': p => `console.${p.type}: ${p.args.map(a => a.value ?? a.description).join(' ')}`,
  'Log.entryAdded': ({entry: x}) => ['error', 'warning'].includes(x.level)
    ? `log ${x.level} ${x.source}: ${x.text} ${x.url || ''}` : null,
};
const shot = async path => {
  const {data} = await send('Page.captureScreenshot', {format: 'png'});
  writeFileSync(path, Buffer.from(data, 'base64'));
};
const settle = async () => {          // until the page's scroll position has held still for 100 ms (at most 5 s)
  let last = null;
  for (let i = 0; i < 50; i++) {
    await sleep(100);
    const now = await ev(() => `${scrollX} ${scrollY}`);
    if (now === last) return;
    last = now;
  }
};
// The platform fonts drawing each <sub> of the readout, and the readout's font-family.  What is logged meanwhile goes to
// log, not to the page's errors: it is DevTools' own (enabling CSS logs that a file: page may not load itself).
const subFonts = async () => {
  const page = current;
  current = {errors: []};
  await send('DOM.enable');
  await send('CSS.enable');
  const {root} = await send('DOM.getDocument', {depth: 0});
  const {nodeIds} = await send('DOM.querySelectorAll', {nodeId: root.nodeId, selector: '#pow2-readout sub'});
  const subs = [];
  for (const nodeId of nodeIds) {
    subs.push((await send('CSS.getPlatformFontsForNode', {nodeId})).fonts.map(f => f.familyName));
  }
  // the platform font of the readout's first family, as DevTools names it (a family's CSS name and its font's own may
  // differ: "Latin Modern" is LMRoman10): what draws digits in a probe of that family alone
  await ev(() => { const s = document.createElement('span'); s.id = 'subfonts-probe'; s.textContent = '0123456789';
                   s.style.fontFamily = getComputedStyle(document.getElementById('pow2-readout')).fontFamily.split(',')[0];
                   document.body.append(s); s.getBoundingClientRect(); });   // laid out before DevTools reads it
  const probe = (await send('DOM.querySelectorAll', {nodeId: root.nodeId, selector: '#subfonts-probe'})).nodeIds;
  const first = (await send('CSS.getPlatformFontsForNode', {nodeId: probe[0]})).fonts.map(f => f.familyName);
  await ev(() => document.getElementById('subfonts-probe').remove());
  await send('CSS.disable');
  await send('DOM.disable');
  const log = current.errors;
  current = page;
  return {subs, log, first, family: await ev(() => getComputedStyle(document.getElementById('pow2-readout')).fontFamily)};
};
const input = {
  mouse: (x, y) => send('Input.dispatchMouseEvent', {type: 'mouseMoved', x, y}),
  touch: async (x, y) => { await send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y}]});
                           await send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []}); },
};

async function main() {
  const portFile = `${C.dir}/profile/DevToolsActivePort`;
  for (let i = 0; i < 300 && !existsSync(portFile); i++) await sleep(100);
  const port = readFileSync(portFile, 'utf8').split('\n')[0];
  const target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t => t.type === 'page');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
    if (once.has(d.method)) { once.get(d.method)(d.params); once.delete(d.method); }
    const line = errors[d.method] && errors[d.method](d.params);
    if (line) current.errors.push(line);
  };
  for (const m of ['Page.enable', 'Runtime.enable', 'Log.enable']) await send(m);
  await send('Emulation.setDeviceMetricsOverride',
             {width: C.width, height: C.height, deviceScaleFactor: C.dpr, mobile: C.mobile});
  await send('Emulation.setTouchEmulationEnabled', {enabled: C.mobile, maxTouchPoints: 1});
  await send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-color-scheme', value: C.theme}]});
  for (const [i, url] of C.urls.entries()) {
    const R = current = out[i];
    const loaded = next('Page.loadEventFired');
    await send('Page.navigate', {url});
    await loaded;
    await ev(() => document.fonts.ready.then(() => 0));
    await ev(FRAMES);
    R.load = await ev(PROBE, TEXT);
    if (C.fragment) {                 // loaded with #k30: its panel, then a real Escape, #k10, and its close button's click
      R.fragment = await ev(PANEL);
      for (const type of ['rawKeyDown', 'keyUp']) {
        await send('Input.dispatchKeyEvent', {type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
      }
      await ev(FRAMES);
      R.escaped = await ev(PANEL);
      await ev(HASHED, '#k10');
      R.reopened = await ev(PANEL);
      const [x, y] = await ev(() => { const b = document.querySelector('#pow2-panel [data-panel-close]');
        b.scrollIntoView({block: 'center'}); const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
      for (const type of ['mousePressed', 'mouseReleased']) {
        await send('Input.dispatchMouseEvent', {type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1});
      }
      await ev(FRAMES);
      R.closed = await ev(PANEL);
    }
    if (!C.drawn) continue;
    await ev(() => document.getElementById('pow2-chart').scrollIntoView({block: 'center'}));
    await ev(FRAMES);
    R.geo = await ev(GEOMETRY);
    R.read0 = await ev(READ, TEXT);
    const [L, T, W] = R.geo.plot, cells = [];
    for (let k = 1; k <= C.K; k++) for (let e = 1; e <= C.E; e++) {
      cells.push([k, e, L + (k - 0.5) * W / C.K, T + (C.E - e) * C.ROW + (C.ROW - C.GAP) / 2]);
    }
    R.dom = await ev(DOM, cells);
    await shot(C.shots[0]);
    R.hovers = [];
    R.taps = [];
    for (const [list, how] of [[R.hovers, C.hover && 'mouse'], [R.taps, C.tap && 'touch']].filter(([, how]) => how)) {
      for (const [k, e, x, y] of cells) { await input[how](x, y); list.push([k, e, await ev(READ, TEXT)]); }
    }
    const [, , x, y] = cells.find(([k, e]) => k === C.outline[0] && e === C.outline[1]);
    await input[C.mobile ? 'touch' : 'mouse'](x, y);
    R.outline = await ev(READ, TEXT);
    R.outlineGeo = await ev(GEOMETRY);
    R.outlineDom = await ev(DOM, [[0, 0, x, y], [0, 0, x - W / C.K / 2 - 1, y]]);   // its middle; 1 px left of it
    R.subFonts = await subFonts();
    await shot(C.shots[1]);
    if (C.swipe) {                    // a finger's swipe up 200 px that starts on cell C.swipeFrom, then the readout
      const [, , sx, sy] = cells.find(([k, e]) => k === C.swipeFrom[0] && e === C.swipeFrom[1]);
      const from = await ev(() => scrollY);
      await send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x: sx, y: sy, id: 1}]});
      for (let i = 1; i <= 10; i++) {
        await send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: sx, y: sy - 20 * i, id: 1}]});
        await sleep(16);
      }
      await send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
      await settle();
      R.swipe = {...await ev(READ, TEXT), from, to: await ev(() => scrollY)};
    }
    R.mstar = [];
    await ev(() => document.getElementById('mstar-chart').scrollIntoView({block: 'center'}));
    await ev(FRAMES);
    const [cl, ct, cw] = (await ev(GEOMETRY)).canvas, T2 = await ev(cols => 1 + Math.max(...cols.map(n => MSTAR.cols[n - 1][1])), C.mstarCols), [ML, MR, MT, MP] = C.mstarLayout;
    for (const [k, m] of C.mstarCells) {        // cell (2^k, m) of the m*(n) chart in its full view of the columns C.mstarCols
      await input.mouse(cl + ML + (C.mstarCols.indexOf(2 ** k) + 0.5) * (cw - ML - MR) / C.mstarCols.length,
                        ct + MT + (T2 - m) * MP + (MP - 2) / 2);
      R.mstar.push([k, m, await ev(() => document.getElementById('mstar-readout').textContent)]);
    }
    if (C.zoom) {                     // each chart's zoom buttons and keys zoom that chart (2026-10-30): R.zoom's steps
      R.zoom = {looks: await ev(LOOKS), steps: []};
      const show = id => ev(i => { document.getElementById(i).scrollIntoView({block: 'center'}); }, id).then(() => ev(FRAMES));
      const click = async (id, at = [0.5, 0.5]) => {     // a real click at element id's middle, or at the fractions at of it
        await show(id);
        const [x, y] = await ev((i, [a, b]) => { const r = document.getElementById(i).getBoundingClientRect();
          return [r.left + a * r.width, r.top + b * r.height]; }, id, at);
        for (const type of ['mousePressed', 'mouseReleased']) {
          await send('Input.dispatchMouseEvent', {type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1});
        }
        await ev(FRAMES);
      };
      // a real click on the chart for the keys: in its bottom left corner, 8 px in from its left edge and 15 px below its
      // plot, by its letter k, so that the click focuses the chart and opens no box (since 2026-11-03 a click on a cell
      // moves the focus to the cell's box; on its δ axis, where this click was until 2026-11-04, a click now opens that
      // row's box)
      const grab = async () => {
        const [w, y] = await ev(() => { const c = document.getElementById('pow2-chart').getBoundingClientRect(),
          s = document.querySelector('#pow2-chart svg').getBoundingClientRect(); return [c.width, (s.bottom + 15 - c.top) / c.height]; });
        await click('pow2-chart', [8 / w, y]);
      };
      const key = async (key, code, keyCode, text) => {      // a real key press, to the focused element
        await send('Input.dispatchKeyEvent', {type: text ? 'keyDown' : 'rawKeyDown', key, code, windowsVirtualKeyCode: keyCode, ...(text ? {text} : {})});
        await send('Input.dispatchKeyEvent', {type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode});
        await ev(FRAMES);
      };
      // The readouts at the left and right ends of each plot's row 1, half a CSS px in, and the four buttons' disabled.
      const edges = async () => {
        await show('pow2-chart');
        const [L, T, W] = (await ev(GEOMETRY)).plot, pow2 = [], pow2Tags = [];
        for (const x of [L + 0.5, L + W - 0.5]) {
          await input.mouse(x, T + (C.E - 1) * C.ROW + (C.ROW - C.GAP) / 2);
          const r = await ev(READ, TEXT);
          pow2.push(r.text);
          pow2Tags.push(r.tags);
        }
        await show('mstar-chart');
        const [cl, ct, cw] = (await ev(GEOMETRY)).canvas, T2 = await ev(cols => 1 + Math.max(...cols.map(n => MSTAR.cols[n - 1][1])), C.mstarCols), [ML, MR, MT, MP] = C.mstarLayout, mstar = [];
        for (const x of [cl + ML + 0.5, cl + cw - MR - 0.5]) {
          await input.mouse(x, ct + MT + (T2 - 1) * MP + (MP - 2) / 2);
          mstar.push(await ev(() => document.getElementById('mstar-readout').textContent));
        }
        const disabled = await ev(() => ['pow2-zoom-in', 'pow2-zoom-out', 'mstar-zoom-in', 'mstar-zoom-out'].map(i => document.getElementById(i).disabled));
        return {pow2, mstar, disabled, pow2Tags, pow2Plot: [L, T, W]};
      };
      const step = async (name, act) => { const x = await act(); R.zoom.steps.push({name, x, ...await edges()}); };
      await step('load', async () => {});
      await step('pow2 +', () => click('pow2-zoom-in'));
      await step('mstar +', () => click('mstar-zoom-in'));
      await step('pow2 + key', async () => { await grab(); await key('+', 'Equal', 187, '+'); });
      await step('pow2 → key', async () => { await grab(); await key('ArrowRight', 'ArrowRight', 39); });
      await step('pow2 − key', async () => { await grab(); await key('-', 'Minus', 189, '-'); });
      await step('pow2 + to its limit', async () => {
        let n = 0;
        while (n < 10 && !await ev(() => document.getElementById('pow2-zoom-in').disabled)) { await click('pow2-zoom-in'); n++; }
        await show('pow2-chart');
        const g = await ev(GEOMETRY), [L, T, W] = g.plot, cells = [];
        for (let k = 1; k <= C.K; k++) for (let e = 1; e <= C.E; e++) {
          cells.push([k, e, L + (k - 0.5 - (C.zoomView[0])) * W / C.zoomView[1], T + (C.E - e) * C.ROW + (C.ROW - C.GAP) / 2]);
        }
        const inView = cells.filter(([, , x]) => x > L && x < L + W);
        return {clicks: n, geo: g, dom: await ev(DOM, inView)};
      });
      await step('pow2 ↺', () => click('pow2-reset'));
      // the m*(n) chart's cap pressed, a click on which shows every column as its ↺ did until 2026-11-10 (dreeves's
      // README, [BOU]: "replace the reset-zoom button with "cap:" and then buttons"); it gets an id here for click
      await ev(() => { document.querySelector('#mstar-caps button[aria-pressed="true"]').id = 'mstar-cap-pressed'; });
      await step('mstar cap', () => click('mstar-cap-pressed'));
      // A corner of a zoomed view read out, then that view panned by the keys alone until the corner's column is out of
      // view (2026-11-02, [HOV], q_axes_tag_the_cell_read_out): a click of this chart's + from the full view that its ↺
      // left, (12, 48); a click on the chart, for the keys; a mouse move to the top-left cell, k = 13 and δ = E; eight
      // presses of ArrowRight, an eighth of the view each, to (24, 48), the end.  Each with the plot then.
      const read = async () => ({...await ev(READ, TEXT), plot: (await ev(GEOMETRY)).plot});
      await click('pow2-zoom-in');
      await grab();
      const plot = (await ev(GEOMETRY)).plot;
      await input.mouse(plot[0] + 0.5, plot[1] + (C.ROW - C.GAP) / 2);
      const corner = await read();
      for (let i = 0; i < 8; i++) await key('ArrowRight', 'ArrowRight', 39);
      R.zoom.away = {corner, away: await read()};
    }
    if (C.panels) {                   // a real click on cell C.outline opens its panel; then every column's, by its fragment
      await ev(() => { document.getElementById('pow2-chart').scrollIntoView({block: 'center'}); });
      await ev(FRAMES);
      await ev(() => document.getElementById('pow2-reset').click());
      const [L, T, W] = (await ev(GEOMETRY)).plot, [k, e] = C.outline;
      const x = L + (k - 0.5) * W / C.K, y = T + (C.E - e) * C.ROW + (C.ROW - C.GAP) / 2;
      for (const type of ['mousePressed', 'mouseReleased']) {
        await send('Input.dispatchMouseEvent', {type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1});
      }
      await ev(FRAMES);
      await ev(LOADED);
      R.clickPanel = await ev(PANEL);
      // the boxes of C.boxes, each by a real click on its target in the full view (2026-11-04, [CEL] and [ROC]), and the
      // table of record gaps
      R.boxes = [];
      for (const t of C.boxes) {
        const [bx, by] = await ev(PLACE, t);
        for (const type of ['mousePressed', 'mouseReleased']) {
          await send('Input.dispatchMouseEvent', {type, x: bx, y: by, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1});
        }
        await ev(FRAMES);
        await ev(LOADED);
        const [ax, ay] = await ev(PLACE, [1, 1]);         // the pointer off to cell (1, 1), so that the cell read out is elsewhere
        await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: ax, y: ay});
        await ev(FRAMES);
        R.boxes.push(await ev(BOX, t, PLACE, PANEL));
      }
      R.gaps = await ev(GAPS);
      R.panels = [];
      R.derived = [];
      await ev(() => history.replaceState(null, '', location.pathname));
      for (let k = 1; k <= C.K; k++) {
        await ev(HASHED, `#k${k}`);
        R.panels.push({k, ...await ev(PANEL)});
        R.derived.push({k, derived: await ev(DERIVED)});    // since 2026-11-04: each column's construction, derived
      }
      await ev(() => { document.querySelector('#pow2-panel [data-panel-close]').click(); });   // the last one closed
      R.after = await ev(PANEL);
    }
  }
  return out;
}

// The report goes to a file, which a pipe's asynchronous writes could cut short at process.exit.  Chrome's whole process
// group is ended (endGroup) before exit, so that run can remove its profile.
let code = 0;
try { writeFileSync(`${C.dir}/report.json`, JSON.stringify({pages: await main()})); }
catch (e) { writeFileSync(`${C.dir}/report.json`, JSON.stringify({error: String(e && e.stack || e)})); code = 1; }
finally { clearTimeout(watchdog); if (ws) ws.close(); }
await endGroup(chrome.pid);
process.exit(code);
"""


# What DRIVER does in each configuration: its pages' pow2.js (by SOURCES; None for none); the viewport, as a phone
# (mobile, with touch) or not; the theme; whether the chart is drawn, and then whether every cell gets a mouse move
# (hover) or a touch tap (tap), whether the m*(n) chart's cells (2^k, hi + 1) are read out too (mstar), and whether a
# swipe follows the outline's tap (swipe), and whether each chart's zoom buttons and keys are tried (zoom).
ZOOM_VIEW = (34, 12)       # the view of the chart of powers of 2 after its + to the limit in DRIVER's zoom steps: [u0, span)
DESKTOP = dict(width=1280, height=900, mobile=False, swipe=False)
PHONE = dict(width=390, height=844, mobile=True, swipe=True)
# Since 2026-11-03 ([REO]) also whether the panels are tried (panels: a real click on a cell, then every column's
# panel by its fragment) and the fragment the page loads with (fragment: its panel, then Escape, another fragment and
# the close button).
CONFIGS = {
    'light': DESKTOP | dict(data=['real'], dpr=2, theme='light', drawn=True, hover=True, tap=False, mstar=True, zoom=True,
                            panels=True),
    'phone': PHONE | dict(data=['real'], dpr=3, theme='light', drawn=True, hover=False, tap=True, mstar=False, zoom=False,
                          panels=True),
    'kinds': DESKTOP | dict(data=['kinds'], dpr=1, theme='light', drawn=True, hover=True, tap=False, mstar=False, zoom=False,
                            panels=True),
    'missing': DESKTOP | dict(data=[None], dpr=1, theme='light', drawn=False, hover=False, tap=False, mstar=False, zoom=False),
    'violations': DESKTOP | dict(data=list(VIOLATIONS), dpr=1, theme='light', drawn=False, hover=False, tap=False,
                                 mstar=False, zoom=False),
    'fragment': DESKTOP | dict(data=['real'], dpr=2, theme='light', drawn=False, hover=False, tap=False, mstar=False,
                               zoom=False, fragment='#k30'),
}
DRAWN = ('light', 'phone')                                   # the configurations on the real data


def run(name):
    """DRIVER's report for one configuration, made on first use: per page, its errors and probe at load, and for a drawn
    chart its geometry, the element at each cell's middle, the readouts of the hovers and taps, the outline's readout
    and the fonts of its <sub>s, the readout after the swipe, the m*(n) chart's readouts of the cells compared, and the
    two screenshots (load, outline) as images."""
    if name not in RUNS:
        c = CONFIGS[name]
        d = tempfile.mkdtemp(prefix='pow2-quals-')
        urls, datas = [], []
        for i, source in enumerate(c['data']):
            p = os.path.join(d, str(i))
            os.mkdir(p)
            for f in (INDEX,) + tuple(os.path.join(HERE, icon) for icon in ICONS): shutil.copy(f, p)
            shutil.copy(MSTAR, qi.data_file(p, 'mstar.js'))
            qi.copy_page_dir(p)
            # a progress.js with no runs (2026-11-04): an open cell's box loads it to show the searches at its cell
            open(qi.data_file(p, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(NO_RUNS) + ');\n')
            js = SOURCES[source]() if source else None
            if js: open(qi.data_file(p, 'pow2.js'), 'w', encoding='utf-8').write(js)
            urls.append('file://' + os.path.join(p, 'index.html') + c.get('fragment', ''))
            datas.append(pow2_of(js) if c['drawn'] else None)
        data = datas[0]
        # the cells (2^k, hi + 1) of the m*(n) chart to read out, for the k whose hiWhy is ["mstar", why]
        mstar = [[k, data['cols'][k - 1][1] + 1] for k in range(1, K + 1)
                 if 2 ** k <= NMAX and c['mstar'] and data['cols'][k - 1][3][0] == 'mstar']
        shots = [os.path.join(d, 'load.png'), os.path.join(d, 'outline.png')]
        cfg = {k: c[k] for k in ('width', 'height', 'dpr', 'mobile', 'theme', 'drawn', 'hover', 'tap', 'swipe', 'zoom')} | dict(
            panels=c.get('panels', False), fragment=c.get('fragment', ''), boxes=BOX_TARGETS,
            zoomView=ZOOM_VIEW,
            chrome=CHROME, headless=qi.HEADLESS, dir=d, urls=urls, K=K, E=data['etop'] if data else 0, ROW=ROW, GAP=gap(c['dpr']), outline=OUTLINE,
            swipeFrom=SWIPE, shots=shots, mstarCells=mstar, mstarLayout=MSTAR_LAYOUT, mstarCols=MSTAR_COLUMNS)
        try:
            p = subprocess.run(['node', '--input-type=module', '-e', DRIVER], input=json.dumps(cfg),
                               capture_output=True, text=True, timeout=600)
            path = os.path.join(d, 'report.json')
            report = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'error': p.stderr[-4000:]}
            assert p.returncode == 0 and 'pages' in report, (name, p.returncode, report.get('error'))
            pages = report['pages']
            assert len(pages) == len(urls), (name, len(pages))
            for R, dd in zip(pages, datas):
                R['data'] = dd
                if c['drawn']: R['images'] = [Image.open(s).convert('RGB') for s in shots]
        finally:
            shutil.rmtree(d)
        RUNS[name] = pages
    return RUNS[name]


def valid(name):
    """The one page of a configuration on valid data, asserted to have loaded with nothing logged."""
    [R] = run(name)
    assert R['errors'] == [], (name, R['errors'])
    return R


def hexrgb(t): return '#%02x%02x%02x' % tuple(t[:3])


def fill(css):
    """A computed fill, rgb(r, g, b), as #rrggbb."""
    m = re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)', css)
    assert m, css
    return hexrgb([int(x) for x in m.groups()])


def pixel(R, image, x, y):
    """The color of the screenshot's device pixel at CSS (x, y) of the viewport."""
    dpr = R['load']['dpr']
    return hexrgb(R['images'][image].getpixel((int(x * dpr), int(y * dpr))))


def cell_box(R, geo, k, e):
    """Cell (k, e)'s colored part in CSS px of the viewport, as (x0, y0, x1, y1), by the plot's geometry."""
    L, T, W, _ = R[geo]['plot']
    E = R['data']['etop']
    return L + (k - 1) * W / K, T + (E - e) * ROW, L + k * W / K, T + (E - e) * ROW + ROW - gap(R['load']['dpr'])


def theorem_cells():
    """The cells (k, e) of the chart whose bounds the theorem on the page states, from its text: m*(2^k) >= v, or = v
    (since dreeves's 6000eaa, 2026-11-04, m*(2^{10}) = 11), as (k, v - k).  Its m*(2^9) = 9 has no cell of its own: the
    chart has no row 0."""
    t = qi.the_theorem(page())   # found by its place since 2026-11-09; labeled "Theorem 1." since 2026-11-04 ([THM])
    pairs = re.findall(r'\(2\^\{?(\d+)\}?\) (?:\\ge|=) (\d+)', t)
    assert pairs, t
    return sorted((int(k), int(v) - int(k)) for k, v in pairs if int(v) > int(k))


def swatch_words(classes):
    """The words of the chart's legend beside the swatch of the classes given, as the page has them."""
    section = re.search(r'<section class="pow2" aria-labelledby="pow2-title">.*?</section>', page(), re.S).group(0)
    [words] = re.findall(rf'<li><span class="{classes}" aria-hidden="true"></span>(.*?)</li>', section, re.S)
    return re.sub(r'<[^>]+>', '', words)


def ringed(R, x, y):
    """Whether CSS point (x, y) lies on the ring of a cell the chart rings (ring_cells; the cells the theorem states
    until 2026-10-30): within 1 px outside it at its sides, within 2 px above or below it (over the hairline gaps there
    and the edges of the cells above and below)."""
    def on(k, e):
        x0, y0, x1, y1 = cell_box(R, 'geo', k, e)
        return x0 - 1 <= x <= x1 + 1 and y0 - 2 <= y <= y1 + 2 and not (x0 <= x <= x1 and y0 <= y <= y1)
    return any(on(k, e) for k, e, _ in ring_cells(R['data']))


# ---------------------------------------------------------------------------------------------------------------------
# Static quals

def q_section_follows_mstar_chart():
    # Replicata: index.html.
    # Expectata: a <section class="pow2" aria-labelledby="pow2-title"> after the m*(n) chart's <section class="mstar"
    # aria-labelledby="mstar-title"> (right after it, then followed by <section class="remarks">, until 2026-10-30, when
    # dreeves put the smallest lengths between and the order stopped being pinned).  The new section holds, in order: the heading, the h2 pow2-title; a paragraph of class
    # pow2-caption; the legend, its swatches exists, open and impossible, as the m*(n) chart's, then exists ringed in
    # gold (record) for the theorem's cells; the zoom buttons −, + and ↺ (the m*(n) chart's, since 2026-10-30:
    # quals_index's q_both_charts_share_one_pan_and_zoom); the div pow2-chart, an image with a label that takes the keys
    # (tabindex 0, since 2026-10-30); the readout paragraph pow2-readout, a polite live region; then the theorem; a link to record_gaps.wl, the script of the table behind
    # the theorem (Stan Wagon's request, 2026-10-18; quals_record_gaps checks it), and that table (dreeves, 2026-10-18),
    # its body filled from pow2.js, in a sideways-scrolling div.  (Since 2026-10-28, dreeves's README: "[CHR] Put the
    # powers-of-2 chart between the normal chart and the theorem statement"; before, the theorem and the table came
    # first.)
    text = page()
    m = re.search(r'<section class="mstar" aria-labelledby="mstar-title">.*?</section>', text, re.S)
    assert m
    s = re.search(r'(<section class="pow2" aria-labelledby="pow2-title">.*?</section>)', text[m.end():], re.S)
    assert s, text[m.end():m.end() + 400]
    parts = [r'<h2 id="pow2-title">', r'<p class="pow2-caption">',
             r'<ul class="legend">', r'<span class="swatch exists" aria-hidden="true">',
             r'<span class="swatch open" aria-hidden="true">', r'<span class="swatch impossible" aria-hidden="true">',
             r'<span class="swatch exists record" aria-hidden="true">', r'</ul>', r'<div class="zoom">',
             r'<button type="button" id="pow2-zoom-out" ', r'<button type="button" id="pow2-zoom-in" ',
             r'<button type="button" id="pow2-reset" ',
             r"<div id=\"pow2-chart\" tabindex=\"0\" role=\"img\" aria-label='[^']+'></div>", r'<p id="pow2-readout" aria-live="polite">',
             r'<p><b>[^<]*</b>', r'href="https://raw\.githubusercontent\.com/dreeves/equipow/main/proofs/record_gaps\.wl"',
             r'<div class="scroll">', r'<table class="pow2-gaps" data-record-gaps>']
    assert re.search('.*?'.join(parts), s.group(1), re.S), s.group(1)


def q_scripts_load_pow2_after_mstar():
    # Replicata: index.html's script tags after its head (KaTeX's two in the head, since 2026-10-28, are
    # quals_index's q_scripts_load_data_then_draw's).
    # Expectata: exactly eight (seven until 2026-10-31), after </main>: the script of the pan and zoom both charts share
    # (2026-10-30; quals_index's q_both_charts_share_one_pan_and_zoom; six scripts before); the m*(n) chart's <script
    # src="mstar.js"> and its script, then a classic <script src="pow2.js"> (no type, async or defer, so it also loads
    # from file://) right after them and this chart's script; then the script of the table of smallest lengths
    # (2026-10-17); then the script of the page's codes (2026-10-31, quals_codes.py); then the script of the section
    # "Search progress" (2026-10-17), the last thing before </body>.  The page's own scripts are files of page/, each a
    # classic <script src> (inline scripts until 2026-10-31).
    text = page()
    tags = re.findall(r'<script\b[^>]*>', text[text.index('</head>'):])
    assert tags == ['<script src="page/shared.js">', '<script src="pagedata/mstar.js">', '<script src="page/mstar-section.js">',
                    '<script src="pagedata/pow2.js">', '<script src="page/pow2-section.js">', '<script src="page/smallest-section.js">',
                    '<script src="page/codes.js">', '<script src="page/progress-section.js">'], tags
    assert text.index('</main>') < text.index('<script src="pagedata/mstar.js"></script>')
    assert text.count('<script src="page/mstar-section.js"></script>\n<script src="pagedata/pow2.js"></script>\n'
                      '<script src="page/pow2-section.js"></script>\n') == 1
    assert text.endswith('</script>\n</body>\n</html>\n')


def q_driver_ends_chrome_s_whole_process_group():
    # Replicata: DRIVER's endGroup (GROUP_JS) in node, on two detached process groups: one whose leader exits at once
    # while a member lives on for a second, as Chrome's helpers outlive its main process for a moment; and one whose
    # members all ignore SIGTERM, with short deadlines; and a group whose only member is a zombie that its parent, this
    # qual, does not reap until node is done, with short deadlines.
    # Expectata: each of the first two still has a member once its leader is gone, the race itself; and endGroup
    # resolves only when no process of the group remains, the second only after its SIGTERM deadline, by SIGKILL.  The
    # zombie, which macOS lets no one signal (EPERM), counts as a member: endGroup fails loudly at its deadline, "process
    # group … outlived SIGKILL", rather than taking EPERM for an error.
    # Resultata before the zombie's case (2026-10-26, two suites at once): DRIVER exited 1 after writing its report,
    # endGroup's first version having thrown EPERM when all that remained of a Chrome was some such member.
    # Resultata before (2026-10-26, twice): "Directory not empty" from run's rmtree, DRIVER having waited only for
    # Chrome's main process, at most 10 s, while a helper still wrote into its profile.
    js = ("import { spawn } from 'node:child_process';\n" + GROUP_JS + """
const start = cmd => spawn('sh', ['-c', cmd], {stdio: 'ignore', detached: true});
const exited = c => new Promise(r => c.exitCode === null ? c.once('exit', r) : r());
const lingers = start('sleep 1 & exit 0');
await exited(lingers);
const raced = groupAlive(lingers.pid);
await endGroup(lingers.pid);
const stubborn = start('trap "" TERM; sleep 30 & wait');
await new Promise(r => setTimeout(r, 200));
const t0 = Date.now();
await endGroup(stubborn.pid, 500, 5000);
console.log(JSON.stringify({raced, lingers: groupAlive(lingers.pid), stubborn: groupAlive(stubborn.pid), ms: Date.now() - t0}));
""")
    p = subprocess.run(['node', '--input-type=module', '-e', js], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    got = json.loads(p.stdout)
    assert got['raced'] and not got['lingers'] and not got['stubborn'] and got['ms'] >= 500, got
    zombie = subprocess.Popen(['sh', '-c', 'exit 0'], start_new_session=True)
    time.sleep(0.3)
    js = GROUP_JS + f"""
console.log(groupAlive({zombie.pid}));
try {{ await endGroup({zombie.pid}, 300, 300); console.log('ended'); }} catch (e) {{ console.log(e.message); }}
"""
    p = subprocess.run(['node', '--input-type=module', '-e', js], capture_output=True, text=True, timeout=60)
    zombie.wait(timeout=10)
    assert p.returncode == 0 and p.stdout.split('\n')[:2] == ['true', f'process group {zombie.pid} outlived SIGKILL'], (p.stdout, p.stderr[-500:])


def q_chart_script_passes_node_check():
    # Replicata: this chart's script (chart_script; inline until 2026-10-31, when this qual was
    # q_inline_script_passes_node_check), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    d = tempfile.mkdtemp(prefix='pow2-quals-')
    path = os.path.join(d, 'chart.js')
    open(path, 'w', encoding='utf-8').write(chart_script())
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_new_css_is_scoped():
    # Replicata: this chart's CSS: the paragraph of the page's stylesheet (its lines between blank lines; page/style.css
    # since 2026-10-31, the style block before) that holds the rule for .pow2, comments removed.
    # Expectata: it is whole rules, and every selector of every rule starts with .pow2 or #pow2 (a class or id of the
    # new section), so this chart's CSS styles nothing of the frozen m*(n) chart or the rest of the page.
    style = qi.page_css()
    block = next(b for b in re.split(r'\n\s*\n', style) if re.search(r'^\.pow2 \{', b, re.M))
    css = re.sub(r'/\*.*?\*/', '', block, flags=re.S)
    rules = re.findall(r'([^{}]+)\{([^{}]*)\}', css)
    assert rules and re.fullmatch(r'\s*', re.sub(r'[^{}]+\{[^{}]*\}', '', css)), css
    selectors = [s.strip() for sel, _ in rules for s in sel.split(',')]
    assert all(re.match(r'[.#]pow2(?![\w])|[.#]pow2-', s) for s in selectors), selectors


def q_caption_defines_readout_symbols():
    # Replicata: the caption (the paragraph pow2-caption), and the reasons of the real pow2.js (as node sees it).
    # Expectata: it names exactly the symbols that the readouts of the real data write for the blocks of their
    # constructions, as the remarks write them (in LaTeX since 2026-10-28): \(\tau_j\) where some block is Thue-Morse
    # (a reason "thue-morse", or a block [2^j, j]), \(p_n\) where some block is a column of the m*(n) chart, and
    # \(p_{N}\) for each N of LONG; and no other: no \(f\) (dreeves, 2026-10-29: "i don't see any f's in those
    # blurbs"; no reason had used f since 2026-10-25), and no other \(p_{N}\) (from 2026-10-26 it named p_1024, beyond
    # that chart's 1000; since 2026-10-27, when that chart reached 1024, LONG is empty).
    m = re.search(r'<p class="pow2-caption">(.*?)</p>', page(), re.S)
    assert m, 'pow2-caption'
    whys = [c[2] for c in pow2_of(real())['cols']]
    blocks = [tuple(b) for w in whys if w[0] == 'joins' for p in w[1] for b in p]
    tau = any(w[0] == 'thue-morse' for w in whys) or any(n == 2 ** k for n, k in blocks)
    columns = any(n <= NMAX and n != 2 ** k for n, k in blocks)
    symbols = ['\\(\\tau_j\\)'] * tau + ['\\(p_n\\)'] * columns + [f'\\(p_{{{n}}}\\)' for n, _ in long_blocks()]
    missing = [s for s in symbols if s not in m[1]]
    named = [int(n) for n in re.findall(r'\\\(p_\{(\d+)\}\\\)', m[1])]
    assert tau and columns and not missing and '\\(f\\)' not in m[1], (missing, m[1])
    assert sorted(set(named)) == sorted(n for n, _ in long_blocks()), (named, long_blocks())


def long_blocks():
    """The chart script's LONG, the examples longer than NMAX that its blocks may use, as [[n, m], ...] (JSON)."""
    m = re.search(r'\n  const LONG = (\[[^\n;]*\]);', chart_script())
    assert m, 'no const LONG in the chart script'
    return json.loads(m.group(1))


def q_long_blocks_are_the_remarks_examples():
    # Replicata: the chart script's LONG; the remarks' code blocks, each p_n of order m alone, decoded by the paper's
    # Table 5 convention (the left half of the signs, 1 = +1, then the rest by (-1)^m symmetry); and pow2.js's blocks.
    # Expectata (2026-10-26: Claude's example of order 11 at 1024, beyond the m*(n) chart's 1000): LONG is exactly the
    # remarks' examples of length n > NMAX, as [n, m], in page order, each decoding to length n and order exactly m
    # (synthetic division); and every block of pow2.js's joins longer than NMAX, other than f and τ_j, is in LONG.
    # Since 2026-10-27, when the m*(n) chart reached 1024, there are none: LONG is [].
    # Since 2026-11-04 the page has one such example, 1440:16, beside the table of smallest lengths.  No join of pow2.js uses it, so LONG, the
    # examples longer than NMAX that the chart's blocks may use, stays [] (and the caption names no p_1440: q_caption_defines_readout_symbols).
    codes = re.findall(r'\\\(p_\{(\d+)\}\\\) \\\(\(m = (\d+)\)\\\):</span>\n\s*<code id="\d+:\d+">([0-9A-F]+)</code>',
                       page())
    long = [(int(n), int(m), h) for n, m, h in codes if int(n) > NMAX]
    # Since 2026-11-10 the m*(n) chart's data reach 2048 ([BOU]), so 1440 is one of its columns and no example is longer.
    assert long_blocks() == [] and [[n, m] for n, m, _ in long] == [], (long_blocks(), long)
    assert NMAX == 2048 and [n for n, *_ in codes].count('1024') == 1, (NMAX, [n for n, *_ in codes])
    for n, m, h in long:
        left = [2 * int(b) - 1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        c, k = left + [(-1) ** m * s for s in reversed(left)], 0
        assert len(c) == n, (n, len(c))
        while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
        assert k == m, (n, m, k)
    used = {tuple(b) for c in pow2_of(real())['cols'] if c[2][0] == 'joins' for p in c[2][1] for b in p
            if b[0] > NMAX and b[0] != 2 ** b[1]}
    assert used <= {tuple(b) for b in long_blocks()}, used


# ---------------------------------------------------------------------------------------------------------------------
# Browser quals

def q_page_loads_clean():
    # Replicata: index.html with the real mstar.js and pow2.js beside it, in each of the two drawn configurations (1280
    # px wide and 390 px wide).
    # Expectata: no exception, no console message at all, and no logged error or warning; the m*(n) chart above is
    # drawn (its canvas taller than 0); the new chart is one svg of K * E rects, E = POW2.etop; the readout is a polite
    # live region.
    for name in DRAWN:
        R = valid(name)
        assert R['load']['canvasH'] > 0, (name, R['load'])
        assert R['geo']['svgs'] == 1 and R['geo']['rects'] == K * R['data']['etop'], (name, R['geo']['rects'])
        assert R['load']['live'] == 'polite', R['load']


def q_drawn_cells_match_data():
    # Replicata: the four drawn configurations, before any hover or tap: a screenshot of the viewport with the chart in
    # view, and document.elementFromPoint at the middle of each cell (k, e), k = 1..K, e = 1..E.
    # Expectata: the pixel at each cell's middle has the color of its kind as the page's tokens give it in that theme
    # (exists when k + e <= lo, open when lo < k + e <= hi, impossible above), or the record token's gold where it
    # lies on the ring of a cell the chart rings (ringed: within 2 px outside that cell; since 2026-10-28, the theorem's
    # cells, and since 2026-10-30 ring_cells, q_gold_trim_rings_the_smallest_cells), and gold at the middle of a cell
    # proven the least, its dot; the element at each cell's middle is an svg rect whose computed fill is
    # that color.  The grid is hairlines of paper (dreeves, 2026-10-29: "this with hairline grid looks great to me"),
    # each found within 2 device px of where the plot's box puts it, since the browser snaps the svg to device pixels:
    # down a column of device pixels through the middle of a cell above row 1, of the 5 nearest the cell's bottom edge
    # exactly one is paper and the others have the color of the cell or of the one below it; across a row of device
    # pixels through the middle of a cell left of one of its own kind, the 5 nearest their boundary blend paper over
    # that color by fractions summing to one device pixel, within 0.1 (the svg antialiases these lines, as in the grid
    # dreeves saw).  A hairline's 5 pixels are passed over where one of them lies on a ring.
    for name in DRAWN:
        R = valid(name)
        cols, tok, dpr = R['data']['cols'], R['load']['tokens'], R['load']['dpr']
        proven = [c for c in ring_cells(R['data']) if c[2] == 3]
        rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
        near = lambda d: [(floor(d) + j + 0.5) / dpr for j in range(-2, 3)]   # CSS middles of 5 device px about d
        bad = []
        for k, e, tag, f in R['dom']:
            want = tok[KINDS[kind_of(cols[k - 1], k, e)]]
            x0, y0, x1, y1 = cell_box(R, 'geo', k, e)
            xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
            middle = tok['record'] if ringed(R, xm, ym) or (k, e, 3) in proven else want   # a proven cell's middle: its dot
            if (pixel(R, 0, xm, ym), tag, fill(f)) != (middle, 'rect', want):
                bad.append((k, e, want, (pixel(R, 0, xm, ym), tag, fill(f))))
            column = [(xm, y) for y in near(y1 * dpr)]
            if e > 1 and not any(ringed(R, x, y) for x, y in column):
                below, px = tok[KINDS[kind_of(cols[k - 1], k, e - 1)]], [pixel(R, 0, x, y) for x, y in column]
                if px.count(tok['paper']) != 1 or not set(px) <= {want, below, tok['paper']}:
                    bad.append((k, e, 'row line', px))
            row = [(x, ym) for x in near(x1 * dpr)]
            if k < K and kind_of(cols[k], k + 1, e) == kind_of(cols[k - 1], k, e) and not any(ringed(R, x, y) for x, y in row):
                c, p = rgb(want), rgb(tok['paper'])
                cover = [sum(v - a for v, a in zip(rgb(pixel(R, 0, x, y)), c)) / sum(b - a for a, b in zip(c, p)) for x, y in row]
                if abs(sum(cover) - 1) > 0.1 or min(cover) < -0.02 or max(cover) > 1.02:
                    bad.append((k, e, 'column line', [round(v, 3) for v in cover]))
        assert len(R['dom']) == K * R['data']['etop'] and not bad, (name, len(bad), bad[:10])


def q_hover_reads_out_every_cell():
    # Replicata: the 1280 px light configuration: a real mouse move to the middle of every cell, column by column.
    # Expectata: after each, the readout is that cell's: its first child is a swatch of the cell's kind, and its text
    # (each <sup> written ^(…)) is "k = K, n = 2^(K), m = K + E = M · MEANING · lo ≤ m^(*)(2^(K)) ≤ hi · REASONS":
    # MEANING the word for the cell's kind (dreeves's known, open and impossible; since 2026-11-09 any one word per
    # kind, the three different); REASONS the
    # Claude: "…" of lo's reason for a green cell, of hi's for a red one and both for a gray one, joined by " · ", lo's
    # naming order lo first and hi's order hi + 1, each holding its reason's math (reason_holds).  A cell ringed in
    # gold (ring_cells, q_gold_trim_rings_the_smallest_cells) has its swatch ringed too (swatch … record, and … proven
    # with its dot where it is proven the least) and notes after its reasons, as the m*(n) chart's readout does for its
    # rings (dreeves, 2026-10-28: "don't forget the gold trim on the hover version"): NOTES of them by its role, each
    # naming its δ, the notes of each role the same for every δ but for their numbers, and different from role to role.
    R = valid('light')
    check_readouts(R['data'], R['hovers'])


def q_tap_reads_out_every_cell():
    # Replicata: the 390 px light configuration (a phone: touch emulation, 3 device px per CSS px): a real touch tap at
    # the middle of every cell, column by column.
    # Expectata: after each, the readout is that cell's, as in q_hover_reads_out_every_cell.
    R = valid('phone')
    check_readouts(R['data'], R['taps'])


def q_swipe_scrolls_and_keeps_readout():
    # Replicata: the 390 px configuration: after the tap on cell OUTLINE, a real touch swipe up 200 px
    # (touchStart, ten touchMoves 20 px apart, touchEnd) that starts on cell SWIPE, then the page left to settle.
    # Expectata: the page scrolled down, and not sideways; the readout is still OUTLINE's, word for word, since a swipe
    # reads out nothing (a tap or a hover does).
    for name in ('phone',):
        R = valid(name)
        s = R['swipe']
        assert s['to'] > s['from'] and s['scrollW'] <= R['load']['innerWidth'], (name, s['from'], s['to'], s['scrollW'])
        assert (s['text'], s['children']) == (R['outline']['text'], R['outline']['children']), (name, s['text'][:60])


def q_readout_subscripts_in_page_font():
    # Replicata: in each drawn configuration, the readout of cell OUTLINE, whose lo is a join of products of blocks,
    # after its mouse move or tap; and the platform fonts that draw each <sub> in it (DevTools'
    # CSS.getPlatformFontsForNode).
    # Expectata: the readout holds no Unicode subscript digit (U+2080-2089: the page's fonts have none, so fallback
    # fonts drew them, two different ones side by side); each subscript it writes is a <sub> (as many <sub>s as TEXT
    # writes _(…), at least one per block of the join); and each <sub> is drawn in one font, the first of the
    # readout's font-family, as DevTools names it: the one font that draws digits in a probe of that family alone
    # (since 2026-10-29 that family is "Latin Modern", whose font calls itself LMRoman10).  (While DevTools reads the
    # fonts it logs only that a file: page may not load itself.)
    k, e = OUTLINE
    for name in DRAWN:
        R = valid(name)
        text, fonts, (lo, hi, lw, hw) = R['outline']['text'], R['subFonts'], R['data']['cols'][k - 1]
        first = fonts['first']
        assert len(first) == 1, (name, fonts['family'], first)
        assert all(x.startswith('log error security: Unsafe attempt to load URL file:') for x in fonts['log']), fonts
        assert lw[0] == 'joins' and not re.search('[₀-₉]', text), (name, lw[0], text)
        assert len(fonts['subs']) == text.count('_(') >= sum(map(len, lw[1])), (name, text, fonts)
        assert all(f == first for f in fonts['subs']), (name, first, fonts['subs'])


def q_outline_marks_the_cell():
    # Replicata: in each drawn configuration, after the hovers or taps, a mouse move (a tap on the phone) to the middle
    # of cell OUTLINE, then a screenshot.
    # Expectata: the readout is OUTLINE's; the pixels 1 CSS px outside its left and right edges (level with its middle)
    # and its top and bottom edges (level with its middle column) are ink, and its middle keeps its kind's color; the
    # outline takes no pointer: the element at the cell's middle is still its rect, and 1 px left of the cell, under the
    # outline, the rect of the cell to its left.
    k, e = OUTLINE
    for name in DRAWN:
        R = valid(name)
        g = READOUT.fullmatch(R['outline']['text'])
        assert g and (int(g[1]), int(g[4])) == (k, e), (name, R['outline'])
        x0, y0, x1, y1 = cell_box(R, 'outlineGeo', k, e)
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        cols, tok = R['data']['cols'], R['load']['tokens']
        got = [pixel(R, 1, x, y) for x, y in ((x0 - 1, ym), (x1 + 1, ym), (xm, y0 - 1), (xm, y1 + 1), (xm, ym))]
        want = [tok['ink']] * 4 + [tok[KINDS[kind_of(cols[k - 1], k, e)]]]
        assert got == want, (name, got, want)
        hits = [(tag, fill(f)) for _, _, tag, f in R['outlineDom']]
        assert hits == [('rect', want[4]), ('rect', tok[KINDS[kind_of(cols[k - 2], k - 1, e)]])], (name, hits)


def check_tags(R, read, plot, view, k, e):
    """Assert that the tags READ found (read's) show cell (k, e), the cell read out, in the view [u0, u0 + span) of the
    plot at (plot[0], plot[1]) in the viewport, plot[2] CSS px wide, as q_axes_tag_the_cell_read_out says; return
    whether k's column's middle is in view."""
    (L, T, W), (u0, span) = plot[:3], view
    E, tok, g = R['data']['etop'], R['load']['tokens'], gap(R['load']['dpr'])
    tags = read['tags']
    assert len(tags) == 2 and all(t[5] == 'pow2-chart' for t in tags), tags
    shown = [t for t in tags if t[1]]
    assert all((fill(t[3]), fill(t[4])) == (tok['ink'], tok['paper']) for t in shown), shown
    left = [t for t in shown if t[2][0] + t[2][2] <= L + 0.5]
    below = [t for t in shown if t[2][1] >= T + E * ROW - 0.5]
    in_view = u0 <= k - 0.5 <= u0 + span
    assert len(left) == 1 and len(below) == in_view and len(shown) == 1 + in_view, (k, e, view, tags)
    L0, T0 = R['geo']['plot'][:2]                                  # where the plot was when the δ labels were measured
    [(lx, ly, lw, lh)] = [(b[0] - L0 + L, b[1] - T0 + T, b[2], b[3]) for t, b in R['geo']['texts']
                          if t == str(e) and b[0] + b[2] <= L0]
    text, _, (x, y, w, h), *_ = left[0]
    top = T + (E - e) * ROW                                        # row e's colored part: from top to top + ROW - g
    assert text == str(e) and top - 0.5 <= y and y + h <= top + ROW - g + 0.5, (k, e, left, top)
    assert x <= lx + 0.5 and lx + lw <= x + w + 0.5 and y <= ly + lh / 2 <= y + h, (k, e, left, (lx, ly, lw, lh))
    for text, _, (x, y, w, h), *_ in below:
        assert text == str(k) and abs(x + w / 2 - (L + (k - 0.5 - u0) * W / span)) <= 1, (k, e, view, below)
        assert y + h <= T + E * ROW + 30, (k, e, below)
    return in_view


def q_axes_tag_the_cell_read_out():
    # Replicata: the drawn configurations: the chart at load; then after the mouse move to every cell (1280 px) or the
    # tap on every cell (390 px), column by column, its four corners among them; in the 1280 px configuration, after
    # each mouse move to an end of row 1 in DRIVER's zoom steps (views zoomed, panned and zoomed to 12 columns among
    # them); and after a mouse move to the top-left cell of the view a click of + makes, (12, 48), and then that view
    # panned by eight presses of ArrowRight, the keys alone, to (24, 48): the elements of class pow2-tag in #pow2-chart,
    # with the readout and the plot.
    # Expectata (dreeves's README, 2026-11-02: "[HOV] When hovering/clicking on cells in the charts it'd be nice to
    # highlight the values of m and n (resp., delta and k) on the axes of the chart"; quals_index's
    # q_axes_tag_the_cell_read_out is the same for the m*(n) chart): the chart always holds two tags, inside its image,
    # which assistive technology knows by its label alone (the readout states the cell); at load neither shows; once a
    # cell (k, δ) is read out, as the readout names it, its δ is tagged over its row's δ label, the tag's box holding
    # that label's and lying within the row's colored part, left of the plot, so no other row's label is touched; and
    # its k on the k axis, below the plot, the tag's box centered on its column's middle to within 1 px, while that
    # middle is in view, as a k label's must be, and no k tag shows otherwise; each tag that shows is in paper on ink
    # (the outline's ink).  Panning with the keys alone keeps the cell read out, as the readout keeps it.
    # Resultata before: no tags.
    for name in DRAWN:
        R = valid(name)
        E, tags0 = R['data']['etop'], R['read0']['tags']
        assert len(tags0) == 2 and not any(t[1] for t in tags0), (name, tags0)
        reads = R['hovers'] + R['taps']
        assert {(1, 1), (1, E), (K, 1), (K, E)} <= {(k, e) for k, e, _ in reads}, name
        for k, e, r in reads:
            g = READOUT.fullmatch(r['text'])
            assert g and (int(g[1]), int(g[4])) == (k, e), (name, k, e, r['text'])
            assert check_tags(R, r, R['geo']['plot'], (0, K), k, e), (name, k, e)
    R = valid('light')
    for s in R['zoom']['steps']:
        ends = [(int(g[1]), int(g[4])) for g in map(READOUT.fullmatch, s['pow2'])]
        view = (ends[0][0] - 1, ends[1][0] - ends[0][0] + 1)          # whole columns, from the k at each end
        for (k, e), tags in zip(ends, s['pow2Tags']):
            assert check_tags(R, {'tags': tags}, s['pow2Plot'], view, k, e), (s['name'], view, k, e)
    a, b = R['zoom']['away']['corner'], R['zoom']['away']['away']
    g = READOUT.fullmatch(a['text'])
    assert (int(g[1]), int(g[4])) == (13, R['data']['etop']) and b['text'] == a['text'], (a['text'], b['text'])
    assert check_tags(R, a, a['plot'], (12, 48), 13, R['data']['etop']), a
    assert not check_tags(R, b, b['plot'], (24, 48), 13, R['data']['etop']), b


def q_labels_mark_every_delta_and_round_k():
    # Replicata: the text nodes in #pow2-chart and their boxes, in the 1280 px and 390 px light configurations.
    # Expectata: they are exactly: the numbers 1..E left of the plot, number e's box centered on row e's colored part
    # (within 1 px), all with one right edge (within 0.5 px) at most 10 px left of the plot; the numbers 10, 20, ..., 70
    # below the plot, each centered on its column's middle (within 1 px); the letter δ left of the plot, within its
    # height (the letter e until 2026-10-28, dreeves's README: "[DLT] Change "excess e" to delta unless e is following
    # precedent from BGPW", and BGPW name no excess); and the letter k below the plot, left of it.
    for name in ('light', 'phone'):
        R = valid(name)
        L, T, W, H = R['geo']['plot']
        E, texts = R['data']['etop'], R['geo']['texts']
        left = sorted((t, b) for t, b in texts if b[0] + b[2] <= L and b[1] < T + H)
        below = sorted((t, b) for t, b in texts if b[1] >= T + H)
        assert len(left) + len(below) == len(texts), (name, texts)
        es = {int(t): b for t, b in left if t.isdigit()}
        assert sorted(es) == list(range(1, E + 1)) and len(left) == E + 1, (name, left)
        for e, (x, y, w, h) in es.items():
            assert abs(y + h / 2 - (T + (E - e) * ROW + (ROW - gap(R['load']['dpr'])) / 2)) <= 1, (name, e, y, h)
        rights = [x + w for x, y, w, h in es.values()]
        assert max(rights) - min(rights) <= 0.5 and 0 <= L - max(rights) <= 10, (name, rights, L)
        letters = [b for t, b in left if t == 'δ']
        assert len(letters) == 1 and T <= letters[0][1] + letters[0][3] / 2 <= T + H, (name, left)
        ks = {int(t): b for t, b in below if t.isdigit()}
        assert sorted(ks) == KLABELS and len(below) == len(KLABELS) + 1, (name, below)
        for k, (x, y, w, h) in ks.items(): assert abs(x + w / 2 - (L + (k - 0.5) * W / K)) <= 1, (name, k, x, w)
        letters = [b for t, b in below if t == 'k']
        assert len(letters) == 1 and letters[0][0] + letters[0][2] <= L, (name, below)


def q_gold_trim_rings_the_smallest_cells():
    # Replicata: the drawn configurations: the elements of class pow2-trim in #pow2-chart (their boxes, computed border
    # colors and widths and pointer-events) and of class pow2-dot (their boxes, colors, corner radii and
    # pointer-events); the cells the chart rings (ring_cells) and the cells the theorem states (theorem_cells); and the
    # data's kinds there.
    # Expectata (dreeves's README, 2026-10-28: "[GTR] Gold trim for the powers-of-2 chart to highlight the values in the
    # theorem"; then, 2026-10-30, "[GLT] ... match the "smallest length known" table: green+gold is the smallest *known*
    # n (resp. 2^k) for a give m (resp. delta) and black+gold is the smallest n (resp. 2^k) not ruled out. but then
    # maybe we want an additional visual indicator for when those coincide"): one ring per cell of ring_cells and no
    # other, in its order: for each δ the least k known to beat Thue-Morse by δ, a green cell, these being the cells the
    # theorem states; and the least k not ruled out, an open cell, where it is another.  Each ring is a border in the
    # record token's gold (the m*(n) chart's ring) just outside its cell, 2 px above and below it (the gaps between
    # rows) and 1 px at its sides (a phone's columns are about 4 px wide, and its neighbors' middles stay theirs), its box
    # the cell's grown accordingly (within 0.5 px), taking no pointer (the cell under it still reads out).  And one dot
    # per cell where the two agree (role 3, proven the least; today (10, 1) alone; Claude's proposal for the indicator),
    # gold, round, centered on its cell and half as wide as the cell's smaller side (within 0.5 px), taking no pointer.
    # Resultata before: rings at the theorem's cells alone, and no dots.
    for name in DRAWN:
        R = valid(name)
        cols, tok, trims, dots = R['data']['cols'], R['load']['tokens'], R['geo']['trims'], R['geo']['dots']
        rings = ring_cells(R['data'])
        assert sorted((k, e) for k, e, role in rings if role & 1) == theorem_cells(), (name, rings)
        assert len(trims) == len(rings), (name, len(trims), rings)
        for (k, e, role), (box, color, top, side, pointer) in zip(rings, trims):
            x0, y0, x1, y1 = cell_box(R, 'geo', k, e)
            want = (x0 - 1, y0 - 2, x1 - x0 + 2, y1 - y0 + 4)
            assert all(abs(a - b) <= 0.5 for a, b in zip(box, want)), (name, k, e, box, want)
            assert (fill(color), top, side, pointer) == (tok['record'], '2px', '1px', 'none'), (name, k, e, color, top, side, pointer)
            assert kind_of(cols[k - 1], k, e) == (None, 0, 1, 0)[role], (name, k, e, role)
        proven = [(k, e) for k, e, role in rings if role == 3]
        assert proven and len(dots) == len(proven), (name, proven, dots)
        for (k, e), (box, color, radius, pointer) in zip(proven, dots):
            x0, y0, x1, y1 = cell_box(R, 'geo', k, e)
            d = min(x1 - x0, y1 - y0) / 2
            want = ((x0 + x1 - d) / 2, (y0 + y1 - d) / 2, d, d)
            assert all(abs(a - b) <= 0.5 for a, b in zip(box, want)), (name, k, e, box, want)
            assert (fill(color), radius, pointer) == (tok['record'], '50%', 'none'), (name, k, e, color, radius, pointer)



def q_zoom_controls_zoom_their_own_chart():
    # Replicata: the 1280 px light configuration, after its other steps (DRIVER's zoom steps): the two charts' zoom
    # buttons side by side (their computed look, box, text, title and label); then, each step followed by the readouts
    # at the left and right ends of row 1 of each plot (half a CSS px in) and the four buttons' disabled: nothing; a real
    # click of this chart's +; of the m*(n) chart's +; a click on this chart and the key +; a click and ArrowRight; a
    # click and −; clicks of this chart's + until it is disabled, and then the element at the middle of each cell in
    # view and the rings' boxes; this chart's ↺; the m*(n) chart's ↺.
    # Expectata (dreeves's README, 2026-10-30: "[ZOO] For anti-magic/consistency, have the same zoom controls on both
    # charts"): each pair of buttons looks the same; each control zooms or pans its own chart as the m*(n) chart's always
    # did (+ and − by 1.5 about the middle, an arrow by an eighth of the view, from 12 columns to all) and leaves the
    # other chart's view as it was: this chart's k at its ends 1 and 72, 13 and 60 twice, 21 and 52, 25 and 56, 17 and
    # 64, 35 and 46 after 4 clicks (ZOOM_VIEW), 1 and 72 twice; the m*(n) chart's n 2 and 1024, then 168 and 856 until
    # the click on its cap pressed (its ↺ until 2026-11-10, [BOU]); a + is disabled exactly at 12 columns and a − exactly at all; in that view of 12 columns each cell in view is
    # its rect, of its kind's color; and each ring (ring_cells, since 2026-10-30) is around its cell, as at the full
    # view, where that cell is in view, and wholly beyond the plot's ends, which clip it, where it is not (no ringed
    # cell was next to that view, where a ring shows its edge, as the m*(n) chart's rings do, until 2026-11-03, when (47, 6) became one, around its cell there too).
    # Resultata before: this chart had no zoom buttons.
    R = valid('light')
    Z, cols, tok = R['zoom'], R['data']['cols'], R['load']['tokens']
    assert all(a == b for a, b in Z['looks']), Z['looks']
    names = ['load', 'pow2 +', 'mstar +', 'pow2 + key', 'pow2 → key', 'pow2 − key', 'pow2 + to its limit', 'pow2 ↺', 'mstar cap']
    ks = [(1, 72), (13, 60), (13, 60), (21, 52), (25, 56), (17, 64), (35, 46), (1, 72), (1, 72)]
    ns = [(2, 1024)] * 2 + [(168, 856)] * 6 + [(2, 1024)]
    disabled = [[False, True, False, True], [False, False, False, True]] + [[False] * 4] * 4 + [
        [True, False, False, False], [False, True, False, False], [False, True, False, True]]
    got = [(s['name'], tuple(int(re.match(r'k = (\d+),', t)[1]) for t in s['pow2']),
            tuple(int(re.match(r'n = (\d+),', t)[1]) for t in s['mstar']), s['disabled']) for s in Z['steps']]
    assert got == list(zip(names, ks, ns, disabled)), got
    limit = Z['steps'][6]['x']
    assert limit['clicks'] == 4, limit['clicks']
    u0, span = ZOOM_VIEW
    L, T, W, _ = limit['geo']['plot']
    E = R['data']['etop']
    seen = sorted({(k, e) for k, e, _, _ in limit['dom']})
    assert seen == [(k, e) for k in range(u0 + 1, u0 + span + 1) for e in range(1, E + 1)], seen
    bad = [(k, e, tag, f) for k, e, tag, f in limit['dom'] if (tag, fill(f)) != ('rect', tok[KINDS[kind_of(cols[k - 1], k, e)]])]
    assert bad == [], bad[:5]
    for (k, e, _), (box, *_) in zip(ring_cells(R['data']), limit['geo']['trims']):
        x0, x1 = L + (k - 1 - u0) * W / span, L + (k - u0) * W / span
        want = (x0 - 1, T + (E - e) * ROW - 2, x1 - x0 + 2, ROW - gap(R['load']['dpr']) + 4)
        inside = u0 <= k <= u0 + span + 1
        assert (all(abs(a - b) <= 0.5 for a, b in zip(box, want)) if inside
                else box[0] + box[2] <= L - 2 or box[0] >= L + W + 2), (k, e, box, want)


def q_phone_has_no_sideways_scroll():
    # Replicata: the 390 px configuration: at load, and after every tap.
    # Expectata: the viewport is 390 px; the page is never wider than it (scrollWidth <= innerWidth).
    for name in ('phone',):
        R = valid(name)
        widths = [R['load']['scrollW'], R['geo']['scrollW'], R['outline']['scrollW']]
        widths += [r['scrollW'] for _, _, r in R['taps']]
        assert R['load']['innerWidth'] == 390 and max(widths) <= 390, (name, max(widths))


def q_plot_lines_up_with_mstar_chart():
    # Replicata: the four drawn configurations: the new plot's box and the m*(n) chart's canvas.
    # Expectata: the plot runs from 44 CSS px right of the canvas's left edge to 16 px left of its right edge, where the
    # m*(n) chart's own plot runs (within 0.5 px), so the two plots line up.
    for name in DRAWN:
        R = valid(name)
        (L, _, W, _), (cl, _, cw, _) = R['geo']['plot'], R['geo']['canvas']
        left, right = MSTAR_LAYOUT[:2]
        assert abs(L - (cl + left)) <= 0.5 and abs(L + W - (cl + cw - right)) <= 0.5, (name, L, W, cl, cw)


def q_drawn_runs_use_the_theme_tokens():
    # Replicata: the drawn configurations (light only since 2026-10-12: no dark mode).
    # Expectata: the tokens the page resolves are the theme block's values (the
    # pixel checks compare against these).
    light, = theme_blocks()
    for name in DRAWN:
        R = valid(name)
        assert all(R['load']['tokens'][t] == light[f'--{t}'].lower() for t in KINDS + ('paper', 'ink', 'record')), (name, R['load']['tokens'])


def q_made_up_data_reads_every_kind():
    # Replicata: made-up data that uses every kind of reason (kinds_cols), 1280 px light: a real mouse move to the
    # middle of every cell.
    # Expectata: nothing logged; every kind of loWhy and hiWhy and of the m*(n) chart's hiWhy is in the data; every
    # readout as in q_hover_reads_out_every_cell.
    R = valid('kinds')
    cols = R['data']['cols']
    assert {c[2][0] for c in cols} == {'thue-morse', 'joins'}
    assert {c[3][0] for c in cols} == {'mstar', 'norm', 'residue'}
    assert {c[3][1][0] for c in cols if c[3][0] == 'mstar'} == {'two', 'norm', 'residue', 'table2', 'page'}
    check_readouts(R['data'], R['hovers'])


# ---------------------------------------------------------------------------------------------------------------------
# The panels of the chart's columns (dreeves's spec [REO]; Claude's design of 2026-11-03, which dreeves approved: "those
# sound like good precedents. go ahead"): a click or a tap on a cell, or the page's fragment kK, opens under the chart
# the full explanation of column k, from the same templates as the m*(n) chart's panels.

def pow2_whys(data, k, rows=()):
    """The kinds of the parts of the box of column k, in order, or of its cell (k, e) for rows [e], as
    quals_index.box_parts has the m*(n) chart's: its witness (Thue–Morse, or a join's construction, then a copy of the
    page's code of the length 2^k and the order lo, where the page has one, unless the box shows the entry that holds
    that code), for a green cell, a black one and a column; its proof (the m*(n) chart's kind, for a reason mstar), for a
    red cell, a black one and a column; and a black cell's searches.  Spec change (2026-11-04, dreeves's README items
    [CEL] and [ROC]): until then the kinds of text of the column's one panel: a status per cell clicked, its lower
    bound's reason, and its upper bound's (and its entry's link, the template "entry", until [REO] step 2, 2026-11-03,
    which moved the entry itself into the panel: quals_index.panel_entries)."""
    lo, hi, lw, hw = data['cols'][k - 1]
    kind = KINDS[kind_of(data['cols'][k - 1], k, rows[0])] if rows else None
    witness, proof = qi.SHOWS[kind]
    upper, code = hw[1][0] if hw[0] == 'mstar' else hw[0], f'{2 ** k}:{lo}'
    entry = kind is None or (proof and upper == 'page')
    copy = code in qi.code_ids() and not (entry and code in qi.entry_codes(2 ** k))
    return (([{'thue-morse': 'witness-thue-morse', 'joins': 'witness-construction'}[lw[0]]] + ['witness-code'] * copy) * witness
            + [f'proof-{upper}'] * proof + ['searches'] * (kind == 'open'))


def pow2_says(data, k, P):
    """What the box of column k, P, must say, by its reasons' arguments, as [(what, found)].  Spec change (2026-11-04,
    [CEL]; dreeves: "so many pointless words in the implementation so far"): its bounds as math, each leading its part
    (an upper bound of the m*(n) chart's, a reason mstar, naming 2^k in digits, as that chart's reasons do); a join's
    construction, a button claiming 2^k:lo, its products in parentheses, as the readout writes them, each block τ_j or
    p_n; Thue–Morse's τ_k; each proof's numbers.  Until then the sentences of 2026-11-03: each product with its blocks'
    lengths multiplied out and its orders added, each block linked to its column's panel, the lengths' total 2^k in
    digits, the least order."""
    lo, hi, lw, hw = data['cols'][k - 1]
    t = P['text']
    bounds = f'm^*(2^{{{k}}}) = {lo}' if lo == hi else f'{lo} \\le m^*(2^{{{k}}}) \\le {hi}'
    kind, args = (hw[1][0], hw[1][1:]) if hw[0] == 'mstar' else (hw[0], hw[1:])
    # the generator a residue panel links, by its path in the repository (pagegen/ since 2026-11-10, [REF]; the panels
    # still linked the root's mstar.py and pow2.py, which were no more, until that evening)
    source, name = ('pagegen/mstar.py', f'{2 ** k}') if hw[0] == 'mstar' else ('pagegen/pow2.py', f'2^{{{k}}}')
    assert os.path.isfile(os.path.join(HERE, source)), source
    says = [('heading', P['heading'] == f'\\(k = {k}\\), \\(n = 2^{{{k}}}\\): \\({bounds}\\)'),
            ('lower', f'\\(m^*(2^{{{k}}}) \\ge {lo}\\):' in t), ('upper', f'\\(m^*({name}) \\le {hi}\\):' in t)]
    if lw[0] == 'joins':
        tex = ' \\vee '.join('(' + ' \\mathbin{\\#} '.join(f'\\tau_{{{m}}}' if n == 2 ** m else f'p_{{{n}}}' for n, m in p) + ')' for p in lw[1])
        says += [('construction', [f'{2 ** k}:{lo}', 'button', f'\\({tex}\\)'] in P['constructions'])]
    else:
        says += [('tau', f'\\(\\tau_{{{k}}}\\)' in t)]
    moduli = ', '.join(map(str, args[0] if args and isinstance(args[0], list) else args))
    says += {'two': [('t', f'\\(n = 2^{{{k}}} \\cdot 1\\)' in t)],
             'norm': [('p', f'\\(p = {args and args[0]} \\nmid n\\)' in t)],
             'residue': [('M', f'\\(M = {moduli}\\)' in t and source in t)],
             'table2': [('cited', qi.TABLE2 in P['links'])], 'page': [('who', qi.legend_labels(qi.page()).get(str(args and args[0]), '\0') in t)]}[kind]
    says += [('entry', P['entries'] == qi.panel_entries(2 ** k))]   # the entry itself since [REO] step 2 (2026-11-03), not its link
    return says


def q_panels_show_exactly_each_column_s_reasons():
    # Replicata: the light run: the panel of each of the 72 columns, opened in turn by its fragment, kK.
    # Expectata: each opens (not hidden, its own fragment, the focus on its heading), with no KaTeX error mark; it shows
    # exactly the data's reasons, the kinds of its texts in order (pow2_whys); its heading gives k, 2^k and the bounds;
    # its texts name their reasons' arguments (pow2_says): each product of a join with its blocks' lengths multiplied
    # out and its orders added, the blocks linked to their columns' panels in the m*(n) chart but τ_j, the lengths'
    # total 2^k in digits and the least order; the prime of a norm bound; the moduli of a residue claim and the script
    # that repeats it; and the remarks' entry itself where one lists 2^k (its link until [REO] step 2, 2026-11-03).
    # Resultata before: no panel.
    R = valid('light')
    assert [P['k'] for P in R['panels']] == list(range(1, K + 1)), [P['k'] for P in R['panels']][:5]
    for P in R['panels']:
        k = P['k']
        assert not P['hidden'] and P['hash'] == f'#k{k}' and P['focus'] and P['errors'] == 0, (k, P)
        assert P['whys'] == pow2_whys(R['data'], k), (k, P['whys'], pow2_whys(R['data'], k))
        bad = [what for what, found in pow2_says(R['data'], k, P) if not found]
        assert bad == [], (k, bad, P['text'])
        assert all(qi.panel_link_lands(href) for href in P['links']), (k, P['links'])


def q_norm_panels_hold_at_powers_of_2():
    # Replicata: the light run: the panel of each column whose upper bound is the norm bound for a prime p, at
    # n = 2^k, up to 2^72, so in numbers of up to 90 digits.
    # Expectata: at m = hi + 1, p^m is more than the floor of (p sum s_r^2 / (p - 1))^((p - 1)/2); the box gives both
    # in digits, and the class sizes s_r and their squares' sum, exactly as Python's integers have them.  Spec change
    # (2026-11-04, [CEL]): until then also both sides of p^(2m) (p - 1)^(p - 1) <= (p sum s_r^2)^(p - 1), the same
    # inequality squared, the left more than the right.
    R = valid('light')
    found = 0
    for P in R['panels']:
        k = P['k']
        lo, hi, lw, hw = R['data']['cols'][k - 1]
        why = hw[1] if hw[0] == 'mstar' else hw
        if why[0] != 'norm': continue
        n, p, m = 2 ** k, why[1], hi + 1
        sizes = [(n - r + p - 1) // p for r in range(p)]
        S = sum(x * x for x in sizes)
        cap = (p * S) ** ((p - 1) // 2) // (p - 1) ** ((p - 1) // 2)
        assert p ** m > cap, (k, p, m)
        for said in ('= ' + ', '.join(f'{x:,}' for x in sizes) + ' and', f'\\(\\sum s_r^2 =\\) {S:,};',
                     f'\\(p^m = {p}^{{{m}}} =\\) {p ** m:,} \\(>\\) {cap:,}'):
            assert qi.among(said, P['text']), (k, said, P['text'])
        found += 1
    assert found > 30, found


def q_click_opens_its_cell_s_box():
    # Replicata: the light run: a real mouse click on cell OUTLINE (k = 36, δ = 5), in the full view.
    # Expectata: the box of the cell opens, its fragment k36d5 set and its heading focused, a black cell's (its kind
    # open), the heading the cell's k and δ and the legend's word for its swatch, open; its parts its column's witness
    # and proof, and the searches at n = 2^36 and m = 41 (pow2_whys).
    # Spec change (2026-11-04, [CEL]: "the info box for a cell should focus on that cell"; until then
    # q_click_opens_its_column_s_panel): the panel of column 36 opened, its fragment k36, starting with the cell's
    # status: "The cell clicked, order 41, is open".
    R = valid('light')
    P, (k, e) = R['clickPanel'], OUTLINE
    assert not P['hidden'] and P['hash'] == f'#k{k}d{e}' and P['focus'] and P['kind'] == 'open', P
    assert P['heading'] == f'\\(k = {k}\\), \\(\\delta = {e}\\): ' + swatch_words('swatch open'), P['heading']
    assert P['whys'] == pow2_whys(R['data'], k, [e]), P['whys']


def q_fragment_opens_its_panel_and_focus_comes_back():
    # Replicata: the page loaded with the fragment #k30; then a real Escape key; then the fragment #k10; then a real
    # click on the panel's close button.
    # Expectata (the design of 2026-11-03: "Loading the page with such a fragment opens that panel"; "On open, focus
    # moves to the panel's heading; close or Escape returns focus to the chart"): nothing logged; the panel of k = 30
    # is open at load, its heading focused; Escape hides it, the fragment gone and the focus on the chart; #k10 opens
    # 10's panel; its close button hides it, the fragment gone, the focus on the chart.
    [R] = run('fragment')
    assert R['errors'] == [], R['errors']
    F, E, O, C = R['fragment'], R['escaped'], R['reopened'], R['closed']
    assert not F['hidden'] and F['hash'] == '#k30' and F['focus'] and F['heading'].startswith('\\(k = 30\\)'), F
    assert E['hidden'] and E['hash'] == '' and E['active'] == 'pow2-chart', E
    assert not O['hidden'] and O['hash'] == '#k10' and O['focus'] and O['heading'].startswith('\\(k = 10\\)'), O
    assert C['hidden'] and C['hash'] == '' and C['active'] == 'pow2-chart', C


def q_panels_fit_a_phone():
    # Replicata: the phone run, 390 px wide: every column's panel opened in turn, after a tap on every cell.
    # Expectata: nothing logged; with each panel open, the page is no wider than the window.
    # (A phone's innerWidth is its visual viewport's, which widens to show a page wider than the window, so the page's
    # width is compared with the window's, PHONE's 390 px, as q_phone_has_no_sideways_scroll compares it.)
    R = valid('phone')
    wide = [(P['k'], P['scrollW']) for P in R['panels'] if P['scrollW'] > PHONE['width']]
    assert len(R['panels']) == K and wide == [], wide[:5]


def q_made_up_panels_use_every_kind():
    # Replicata: made-up data that uses every kind of reason (kinds_cols): every column's panel opened in turn.
    # Expectata: nothing logged; each panel opens and shows exactly its data's reasons; between them they use every
    # kind of lower and upper bound of the data contract, the m*(n) chart's kinds among them.
    R = valid('kinds')
    for P in R['panels']:
        assert not P['hidden'] and P['errors'] == 0 and P['whys'] == pow2_whys(R['data'], P['k']), (P['k'], P)
        bad = [what for what, found in pow2_says(R['data'], P['k'], P) if not found]
        assert bad == [], (P['k'], bad, P['text'])
    kinds = {w for P in R['panels'] for w in P['whys']}
    # (spec change, 2026-11-04, [CEL]: the parts' kinds are a witness's and a proof's, lo-KIND and hi-KIND until then)
    assert {'witness-thue-morse', 'witness-construction', 'proof-two', 'proof-norm', 'proof-residue', 'proof-table2', 'proof-page'} <= kinds, kinds


def q_panels_show_their_entries_and_give_them_back():
    # Replicata: the light and phone runs: every column's panel by its fragment in turn, then the last closed by its
    # button; and the fragment run: the page loaded with #k30; a real Escape; #k10; its close button.
    # Expectata ([REO] step 2, the main session's design of 2026-11-03: "When a column panel opens, its length's remarks
    # entry ... is moved into the panel, below the generated reasons. It is not cloned ... When the panel closes, or
    # another column's panel opens, the entry goes back to its exact place in the list"; and dreeves's "the box shouldn't
    # ever refer to "remarks below""): each open panel shows exactly the entry that lists its 2^k, if any
    # (quals_index.panel_entries), with no id on two elements of the page, while the list holds the others in their
    # order (quals_index.entry_order); with the panel closed the list is whole, in order; and no panel's text, the
    # entry's included, says "remarks below".
    # Resultata before: the panels linked their entries ("Its entry in the remarks below"), which stayed in the list.
    order = qi.entry_order()
    for name in ('light', 'phone'):
        R = valid(name)
        for P in R['panels']:
            assert P['entries'] == qi.panel_entries(2 ** P['k']) and P['listed'] == qi.held(order, *P['entries']), (name, P['k'], P['entries'])
            assert P['dups'] == [] and 'remarks below' not in ' '.join([P['text'], *P['entryText']]), (name, P['k'], P['dups'])
        assert R['after']['hidden'] and R['after']['entries'] == [] and R['after']['listed'] == order, (name, R['after']['entries'])
        assert sum(1 for P in R['panels'] if P['entries']) >= 30, name    # 36 on 2026-11-03: 2^9, 2^10 and 34 entries of their own
    [R] = run('fragment')
    assert R['errors'] == [], R['errors']
    for step, want in (('fragment', ['entry-1073741824']), ('escaped', []), ('reopened', ['entry-1024']), ('closed', [])):
        assert R[step]['entries'] == want and R[step]['listed'] == qi.held(order, *want) and R[step]['dups'] == [], (step, R[step]['entries'])


# ---------------------------------------------------------------------------------------------------------------------
# The boxes of the chart's cells, columns and rows (dreeves's README, 2026-11-03, items [CEL] and [ROC]; the main
# session's design of 2026-11-04), as quals_index's boxes quals have the m*(n) chart's: a real click on a cell, on the
# strip of the k labels or on the strip of the δ labels opens that cell's, column's or row's box under the chart.

def pow2_boxes():
    """The light run, with its boxes by their targets."""
    R = valid('light')
    return R, {tuple(B['target']): B for B in R['boxes']}


def q_cell_boxes_take_their_cell_s_color():
    # Replicata: the light run (1280 px): real clicks on the cells of BOX_TARGETS in the full view; on the strip of the k
    # labels under column 30, 10 px below the plot; and on the strip of the δ labels at rows 3 and 12.
    # Expectata ([CEL]: "color-code it to match the cell"; the design of 2026-11-04: "the box's frame or header band in
    # the clicked cell's own color (use the charts' own CSS tokens, not new colors), with a swatch identical to the cell
    # (gold ring included when the cell is ringed)"): each cell's box open, its fragment kKdD, its kind the cell's, its
    # frame the very fill of the cell under the click, its heading led by a swatch of that color, ringed in gold where
    # the cell is (record; proven where it is the least: ring_cells), every role among them; a column's and a row's box
    # framed in --rule, its heading without a swatch.
    # Resultata before: each click on a cell opened its column's panel, framed in --rule whatever the cell, with no
    # swatch; a click on a strip opened nothing.
    R, B = pow2_boxes()
    cols, tok = R['data']['cols'], R['load']['tokens']
    rings = {(k, e): role for k, e, role in ring_cells(R['data'])}
    cells = [t for t in B if None not in t]
    for k, e in cells:
        P, kind, role = B[(k, e)], KINDS[kind_of(cols[k - 1], k, e)], rings.get((k, e), 0)
        assert not P['hidden'] and P['hash'] == f'#k{k}d{e}' and P['kind'] == kind, (k, e, P['hidden'], P['hash'], P['kind'])
        assert P['fill'] == tok[kind] == P['frame'] == P['swatch']['color'], (k, e, P['fill'], P['frame'], P['swatch'])
        assert P['swatch']['cls'] == f"swatch {kind}{['', ' record', ' record', ' record proven'][role]}", (k, e, P['swatch'])
    assert {rings.get(t, 0) for t in cells} == {0, 1, 2, 3}, 'not every role of ring among the cells clicked'
    for t in [t for t in B if None in t]:
        assert not B[t]['hidden'] and B[t]['kind'] == ('row' if t[0] is None else 'column'), (t, B[t]['kind'])
        assert B[t]['frame'] == tok['rule'] and B[t]['swatch'] is None, (t, B[t]['frame'], B[t]['swatch'])


def q_box_outline_and_caret_mark_the_target():
    # Replicata: the light run's boxes of BOX_TARGETS, each after its click and the pointer then moved off to cell (1, 1).
    # Expectata (the design of 2026-11-04: "the clicked cell keeps an outline while its box is open; ... Column box: the
    # column is outlined; row box: the row"; "a caret on the box's top edge at the clicked column's x (clamped)"): while
    # each box is open, the chart's outline of its target shows, 2 px outside the target's cells, within 1 px (a cell's,
    # a column's every row, a row's every column); and the middle of the caret on the box's top edge is within 2 px of
    # the middle of the target's column, or of the δ labels' strip for a row.
    # Resultata before: only the cell read out was outlined, and there was no caret.
    R, B = pow2_boxes()
    bad = [(t, P['pin'], P['want']) for t, P in B.items() if P['pinHidden'] or max(abs(a - b) for a, b in zip(P['pin'], P['want'])) > 1]
    assert bad == [], bad
    bad = [(t, P['caret'], P['column']) for t, P in B.items() if P['caret'] is None or abs(P['caret'] - P['column']) > 2]   # None: no caret
    assert bad == [], bad


def q_pow2_boxes_show_witness_proof_and_searches_by_kind():
    # Replicata: the light run's boxes of the cells (30, 2), (20, 2) and (10, 1), green; (30, 8) and (9, 1), red; and
    # (30, 5) and (13, 2), black; with a progress.js of no runs.
    # Expectata ([CEL]): each shows, by its kind, its column's witness, its proof, or both and its searches
    # (pow2_whys), each led by its bound: a join's construction, a button claiming 2^k:lo, its products in parentheses
    # as the readout writes them (for k = 10 the one block p_1024), with a copy of the page's code of 1024 and order 11
    # where the column is 10; a residue proof by the chain mod 3 (pow2.py) at 30, by the m*(n) chart's residue condition
    # mod 27 at 2^9 = 512 (mstar.py); for a black cell, under the Search progress section's heading, a dash: no run.
    # Resultata before: a click opened the column's panel: the cell's status sentence and both bounds' sentences.
    R, B = pow2_boxes()
    cols = R['data']['cols']
    for t in ((30, 2), (20, 2), (10, 1), (30, 8), (9, 1), (30, 5), (13, 2)):
        assert B[t]['whys'] == pow2_whys(R['data'], *t[:1], [t[1]]), (t, B[t]['whys'], pow2_whys(R['data'], t[0], [t[1]]))
    assert B[(10, 1)]['constructions'] == [['1024:11', 'button', '\\((p_{1024})\\)']], B[(10, 1)]['constructions']
    assert B[(10, 1)]['copies'] == [['1024:11', '11', 'button', qi.code_digits('1024:11')]], B[(10, 1)]['copies']
    # Since 2026-11-11 the join at 2^30 is the base of excess 4, of order 34 (pow2.BASES[30]; dreeves, of recording it: "go ahead"); until then the lift of the base
    # at 2^28, a button claiming '1073741824:33' with (p_960 # p_768 # tau_7) v (p_576 # p_576 # p_48 # tau_3) v (p_800 # p_832 # p_320 # tau_2)
    assert B[(30, 2)]['constructions'] == [['1073741824:34', 'button', '\\((p_{1504} \\mathbin{\\#} p_{800} \\mathbin{\\#} p_{800}) \\vee '
                                            '(p_{1488} \\mathbin{\\#} p_{1440} \\mathbin{\\#} \\tau_{5}) \\vee '
                                            '(p_{1632} \\mathbin{\\#} p_{1632} \\mathbin{\\#} \\tau_{4})\\)']], B[(30, 2)]['constructions']
    assert cols[29][3] == ['residue', [3]] and '\\(M = 3\\)' in B[(30, 8)]['said'] and 'pow2.py' in B[(30, 8)]['said'], B[(30, 8)]['said']
    assert re.match(qi.OPENING + re.escape('\\(m^*(2^{30}) \\le 36\\):'), B[(30, 8)]['said']), B[(30, 8)]['said']
    assert cols[8][3] == ['mstar', ['residue', 27]] and re.match(qi.OPENING + re.escape('\\(m^*(512) \\le 9\\):'), B[(9, 1)]['said']), B[(9, 1)]['said']
    assert '\\(M = 27\\)' in B[(9, 1)]['said'], B[(9, 1)]['said']
    for t in ((30, 5), (13, 2)):          # a dash under the section's heading, whatever the heading says (2026-11-09)
        assert [qi.figures(x) for x in B[t]['searches']] == ['—'], (t, B[t].get('searches'))


def q_column_and_row_boxes_open_from_their_labels():
    # Replicata: the light run: real clicks on the strip of the k labels under column 30, and on the strip of the δ labels
    # at rows 3 and 12; and the page's table of record gaps as drawn.
    # Expectata ([ROC]; the main session's design of 2026-11-04 for this chart's rows: "for the powers of 2: Table 4's row
    # for that δ (the record-gaps table)"): column 30's box, its fragment k30, its heading k, 2^k and the bounds, its
    # parts its witness and proof (pow2_whys); row 3's, its fragment d3, its heading δ = 3: a line per gold-ringed cell
    # of the row, the legend's swatch and words for it and its k, linked to its cell's box (the least k known to beat
    # Thue–Morse by 3, 28, and the least not ruled out, 16), then that row of the table of record gaps under its head,
    # as the page's table has them; row 12's, its one ringed cell, the least k not ruled out, and no table, 12 being no
    # record gap.
    # Resultata before: nothing opened.
    R, B = pow2_boxes()
    C = B[(30, None)]
    assert not C['hidden'] and C['hash'] == '#k30' and C['kind'] == 'column' and C['whys'] == pow2_whys(R['data'], 30), (C['hash'], C['whys'])
    rings = ring_cells(R['data'])
    for e in (3, 12):
        P, mine = B[(None, e)], [(k, role) for k, g, role in rings if g == e]
        assert not P['hidden'] and P['hash'] == f'#d{e}' and P['kind'] == 'row' and P['heading'] == f'\\(\\delta = {e}\\)', (e, P['hash'], P['heading'])
        assert P['whys'] == ['row-ring'] * len(mine) + ['row-gaps'] * (e == 3), (e, P['whys'])
        assert [f'#k{k}d{e}' for k, _ in mine] == [h for h in P['links'] if h.startswith('#k')], (e, P['links'])
        assert all(f'\\(k = {k}\\)' in P['text'] for k, _ in mine), (e, P['text'])
    assert [k for k, g, _ in rings if g == 3] == [16, 28], rings
    gaps = R['gaps']
    i = [j for j, row in enumerate(gaps) if row[0].startswith('\\(m^*(2^{28}) \\ge 31\\)')][0]
    assert B[(None, 3)]['tables'] == [[gaps[0]] + gaps[i:i + 3]], (B[(None, 3)]['tables'], gaps[i:i + 3])


def q_every_column_s_construction_derives_its_bound():
    # Replicata: the light run: the box of each of the 72 columns, opened by its fragment, and a click on each of its
    # constructions.
    # Expectata (page/codes.js, since 2026-11-04 also for the constructions the boxes make: "a derivation whose length
    # and order are not N:M" throws): each column whose lower bound is a join has one construction, claiming 2^k:lo, and
    # its derivation shows, its bound m*(2^k) >= lo; a column of Thue–Morse has none; so pow2.js's blocks agree with
    # mstar.js's orders.
    # Resultata before: no construction in the panels.
    R = valid('light')
    cols = R['data']['cols']
    for D in R['derived']:
        k, (lo, _, lw, _) = D['k'], cols[D['k'] - 1]
        want = [[f'{2 ** k}:{lo}', f'm*(2{k}) ≥ {lo}' if k > 1 else f'm*(2) ≥ {lo}', True]] if lw[0] == 'joins' else []
        assert D['derived'] == want, (k, D['derived'], want)
    assert sum(1 for D in R['derived'] if D['derived']) == sum(1 for c in cols if c[2][0] == 'joins') > 50


def q_pow2_cell_boxes_are_brief_and_quote_claude_right():
    # Replicata: the light run's box of each column (its witness's and its proof's parts), and its boxes of cells.
    # Expectata (as quals_index's q_cell_box_words_stay_within_budget and q_box_quotes_claude_around_its_english_alone
    # have the m*(n) chart's; dreeves, 2026-11-03: "so many pointless words", and 2026-11-04: "we don't need claude
    # attribution for blurbs without words like these"; spec, Claude's proposal of 2026-11-04): a cell's box, which
    # shows its column's witness, proof or both, has at most quals_index.BOX_WORDS words outside its math, codes and
    # numbers; no box says below, above, this page, paragraph or remarks; each box quotes Claude once around its parts of
    # Claude's English, and not at all without any.
    # Resultata before: the panel of 2^30 alone had over 100 words, "at the top of this page" among them.
    R = valid('light')
    cols, top, most, elsewhere = R['data']['cols'], R['data']['etop'], [], re.compile(r'\b(?:below|above|this page|paragraph|remarks)\b', re.I)
    for P in R['panels']:
        k, parts = P['k'], P['parts']
        lo, hi = cols[k - 1][:2]
        text = {w: ' '.join(qi.unquoted(t) for why, t, _ in parts if why.startswith(w)) for w in ('witness', 'proof')}
        claude = {w: any(c for why, _, c in parts if why.startswith(w)) for w in ('witness', 'proof')}
        for kind in [x for x, present in (('exists', lo > k), ('open', hi > lo), ('impossible', hi < k + top)) if present]:
            shows = qi.SHOWS[kind]
            most.append((((claude['witness'] and shows[0]) or (claude['proof'] and shows[1])) + len(qi.words(text['witness'])) * shows[0]
                         + len(qi.words(text['proof'])) * shows[1], k, kind))
        assert not elsewhere.search(text['witness'] + text['proof']) and qi.quoted_right(parts), (k, parts)
    most += [(len(qi.words(' '.join(text for why, text, _ in P['parts'] if why != 'searches'))), tuple(P['target']), 'clicked')
             for P in R['boxes'] if None not in P['target']]
    assert max(c for c, *_ in most) <= qi.BOX_WORDS, sorted(most, key=lambda x: x[0])[-5:]
    assert all(qi.quoted_right(P['parts']) for P in R['boxes']), [P['target'] for P in R['boxes'] if not qi.quoted_right(P['parts'])]


def q_missing_data_fails_loudly():
    # Replicata: index.html with mstar.js but no pow2.js beside it.
    # Expectata: #pow2-chart stays empty; the readout ends with the error, which names POW2; the failed load of pow2.js
    # and that uncaught error are logged, and nothing else; the m*(n) chart still draws.
    [R] = run('missing')
    error = next(e[len('exception: Uncaught '):] for e in R['errors'] if e.startswith('exception: Uncaught '))
    assert R['load']['chartNodes'] == 0 and 'POW2' in error and R['load']['readout'].endswith(error), R['load']
    assert len(R['errors']) == 2, R['errors']
    assert [x for x in R['errors'] if x.startswith('log error network: ') and x.endswith('/pow2.js')], R['errors']
    assert R['load']['canvasH'] > 0, R['load']


def q_contract_violations_fail_loudly():
    # Replicata: made-up data broken in one way each (VIOLATIONS): a lo below k or above hi; hi at etop; a column of
    # five entries; an unknown kind of loWhy or hiWhy, or one of the wrong arity; Thue-Morse not at lo = k; a power
    # whose 24 L + j is not k, or whose lo is not k + L; joins whose lengths do not add up to 2^k, whose lo is not the
    # least product's order, with a block that is none of f, τ_j and a column n <= NMAX ([4096, 13]; [2048, 12] until
    # 2026-11-10, when the m*(n) chart reached 2048; until 2026-10-27, when it reached 1024, also [1024, 12], beside
    # the page's example of order 11 at 1024), or with no product; an "mstar" hiWhy above k = 11 (k = 10 until
    # 2026-11-10, k = 9 until 2026-10-27), of an unknown kind, or breaking its own rule; a norm
    # bound for a composite p, for
    # p = 2, or not the bound; a residue chain whose moduli do not divide in turn, or with a modulus below 2; an etop
    # above max(hi - k) + 1; kmax not 72; 71 columns; a key beyond kmax, etop and cols.
    # Expectata: in each case #pow2-chart stays empty, the readout ends with "Error: " and the quote (the column [k,
    # [lo, hi, loWhy, hiWhy]] as JSON with ' for "; or [etop]; or [kmax, etop]; or the keys), and the only thing
    # logged is that error, uncaught.
    for v, R in zip(VIOLATIONS, run('violations')):
        q = VIOLATIONS[v][1]
        assert R['load']['chartNodes'] == 0 and R['load']['readout'].endswith(f'Error: {q}'), (v, R['load']['readout'])
        assert R['errors'] == [f'exception: Uncaught Error: {q}'], (v, R['errors'])


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
