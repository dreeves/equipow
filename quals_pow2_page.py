#!/usr/bin/env python3
"""Quals for index.html's chart of the bounds on m*(2^k) - k, the excess over Thue-Morse at the powers of 2, for k up
to 72: the section "pow2" right after the m*(n) chart, drawn from pow2.js.  Run: python3 -B quals_pow2_page.py
[name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The static quals read index.html and pow2.js.  The browser quals load copies of index.html, each with mstar.js beside it and a pow2.js (the real
one, made-up data, or none), in headless Chrome driven through the DevTools protocol by DRIVER, a Node script: a true
viewport of each configuration's width and pixel ratio, its theme by prefers-color-scheme, real mouse moves, touch taps
and swipes, and screenshots whose pixels are checked against the data.  DRIVER finds the cells by geometry alone: the
plot is the svg in #pow2-chart, K columns of equal width, and rows ROW CSS px apart from the top (row E) down to row 1,
the bottom GAP px of each row page surface.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, time, shutil, tempfile, traceback, subprocess, itertools
from math import prod
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
DATA = os.path.join(HERE, 'pow2.js')          # made by pow2.py; the chart's data
MSTAR = os.path.join(HERE, 'mstar.js')        # made by mstar.py; the m*(n) chart's data, which the page also loads
ICONS = ('favicon.ico', 'favicon.svg', 'apple-touch-icon.png')   # the page's icons, which it also loads
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
K, ROW, GAP = 72, 14, 2                       # columns k = 1..K; rows ROW CSS px apart, the bottom GAP of each surface
KINDS = ('exists', 'open', 'impossible')      # the kinds of cell, as the tokens of their colors name them
F = [2 ** 24, 25]                             # f, the construction of length 2^24 and order 25, as a block [n, m]
KLABELS = list(range(10, K + 1, 10))          # the k labels below the plot
OUTLINE = (36, 5)                             # the cell whose outline the screenshots check
SWIPE = (29, 8)                               # the cell a phone's swipe starts on, after the outline's tap
MSTAR_LAYOUT = (44, 16, 2, 14)                # the m*(n) chart's plot: left and right gutters, top, row pitch (CSS px)
WHO = ('BGPW', 'Claude alone', 'Claude and BGPW', 'Astra alone', 'Claude and Astra')   # provenance labels of the page's new results
RUNS = {}                                     # DRIVER's reports by configuration name, made once per process (see run)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the page and the data

def page(): return open(INDEX, encoding='utf-8').read()


def scripts():
    """The page's inline scripts, in order: the m*(n) chart's, then this chart's, then the table of smallest lengths'
    (2026-10-17), then the section "Search progress"'s (2026-10-17)."""
    return re.findall(r'<script>\n(.*?)</script>', page(), re.S)


def theme_blocks():
    """The custom properties of the page's one theme block, :root, as a one-item list (dreeves, 2026-10-12: no dark
    mode, so no other theme block)."""
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    ms = list(re.finditer(r'\n:root \{(.*?)\n\s*\}', css, re.S))
    assert len(ms) == 1 and 'prefers-color-scheme' not in page() and 'data-theme' not in page()
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
    """A block of a join's product, as the readout names it: f, τ_j for Thue-Morse [2^j, j], else p_n."""
    n, m = b
    return 'f' if b == F else f'τ{sub(m)}' if n == 2 ** m else f'p{sub(n)}'


def join_text(products): return ' ∨ '.join('(' + ' # '.join(map(block, p)) + ')' for p in products)


def reason_math(k, why):
    """The math that a reason's Claude: "…" must hold: what tells that reason apart, as the readout writes it."""
    kind, *args = why
    mstar = {'two': lambda: str(2 ** k), 'norm': lambda p: f'p\xa0=\xa0{p}', 'residue': lambda M: f'mod {M}',
             'table2': lambda: 'Table 2', 'page': lambda who: f'({who})'}
    return {'thue-morse': lambda: f'τ{sub(k)}', 'power': lambda L, j: 'f # ' * L + f'τ{sub(j)}',
            'joins': join_text, 'mstar': lambda w: mstar[w[0]](*w[1:]), 'norm': lambda p: f'p\xa0=\xa0{p}',
            'residue': lambda chain: 'mod ' + ', '.join(map(str, chain))}[kind](*args)


# A readout's text, each <sup> written ^(…) and each <sub> _(…): the cell, its meaning, the column's bounds, then the
# reasons.
READOUT = re.compile(r'k = (\d+), n = 2\^\((\d+)\), m = (\d+) \+ (\d+) = (\d+) · (known|open|impossible) · '
                     r'(\d+) ≤ m\^\(\*\)\(2\^\((\d+)\)\) ≤ (\d+) · (.*)')


def kind_of(col, k, e): return (k + e > col[0]) + (k + e > col[1])     # 0 exists, 1 open, 2 impossible
MEANINGS = ('known', 'open', 'impossible')    # each kind's word in the readout, dreeves's (approved 2026-10-12)


def check_readouts(data, reads):
    """Assert that reads, [k, e, {text, children}] for every cell, are each that cell's readout (see
    q_hover_reads_out_every_cell)."""
    E, cols, meaning = data['etop'], data['cols'], {}
    assert sorted((k, e) for k, e, _ in reads) == [(k, e) for k in range(1, K + 1) for e in range(1, E + 1)]
    for k, e, r in reads:
        lo, hi, lw, hw = cols[k - 1]
        kind = kind_of(cols[k - 1], k, e)
        g = READOUT.fullmatch(r['text'])
        assert g and [int(g[i]) for i in (1, 2, 3, 4, 5, 7, 8, 9)] == [k, k, k, e, k + e, lo, k, hi], (k, e, r)
        assert r['children'][:1] == [f'swatch {KINDS[kind]}'], (k, e, r)
        assert g[6] == MEANINGS[kind], (k, e, r)
        meaning.setdefault(kind, set()).add(g[6])
        parts = re.findall(r'Claude: "[^"]*"', g[10])
        assert ' · '.join(parts) == g[10], (k, e, r)
        want = [(f'Claude: "order {lo} ', reason_math(k, lw)), (f'Claude: "order {hi + 1} ', reason_math(k, hw))]
        want = [want[:1], want, want[1:]][kind]
        assert len(parts) == len(want) and all(p.startswith(a) and b in p for p, (a, b) in zip(parts, want)), \
            (k, e, r, want)
    assert all(len(v) == 1 for v in meaning.values()) and len(set.union(*meaning.values())) == len(meaning), meaning


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


def kinds_cols():
    """Made-up columns that follow the contract and use every kind of reason: k <= 9 from Thue-Morse, settled by each
    kind of the m*(n) chart's hiWhy; then lo = k + floor(k / 24) (Thue-Morse, then f^{#L} # τ_j) and hi the norm bound
    for p = 3, but for a few columns with the other kinds: joins with f, τ_j (j above 9), columns of mstar.js and the
    page's example at 1024 (p_1024, order 11); residue chains; the norm bound for p = 5 and 7."""
    cols = []
    for k in range(1, K + 1):
        L, j = divmod(k, 24)
        cols.append([k + L, norm(2 ** k, 3), ['power', L, j] if L else ['thue-morse'], ['norm', 3]])
    whys = {1: ['two'], 2: ['norm', 3], 3: ['table2'], 4: ['page', 'BGPW'], 5: ['residue', 9],
            6: ['page', 'Claude alone'], 7: ['residue', 3], 8: ['table2'], 9: ['page', 'Claude and BGPW']}
    for k, why in whys.items(): cols[k - 1] = [k, k, ['thue-morse'], ['mstar', why]]
    joins = {24: JOIN24, 25: [[F, [2, 1]]], 34: [[[1024, 10], F]], 35: [[[1024, 11], [2 ** 25, 25]]], 51: STONG}
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


C30 = kinds_cols()[29]                        # [31, 37, ['power', 1, 6], ['norm', 3]]
VIOLATIONS = {   # name: (a change that breaks the contract, what the page's error line must quote)
    'lo below k': column(30, [29, 37, ['thue-morse'], ['norm', 3]]),
    'lo above hi': column(30, [38, 37, ['power', 1, 6], ['norm', 3]]),
    'hi at etop': column(30, [31, 49, ['power', 1, 6], ['norm', 3]]),
    'five entries': column(30, C30 + [0]),
    'unknown lo kind': column(30, [31, 37, ['guess'], ['norm', 3]]),
    'unknown hi kind': column(30, [31, 37, ['power', 1, 6], ['guess']]),
    'arity': column(30, [31, 37, ['power', 1], ['norm', 3]]),
    'thue-morse lo': column(30, [31, 37, ['thue-morse'], ['norm', 3]]),
    'power sum': column(30, [31, 37, ['power', 1, 5], ['norm', 3]]),
    'power lo': column(30, [32, 37, ['power', 1, 6], ['norm', 3]]),
    'joins length': column(30, [31, 37, ['joins', [[F, [32, 5]]]], ['norm', 3]]),
    'joins lo': column(30, [32, 37, ['joins', [[F, [64, 6]]]], ['norm', 3]]),
    'joins block': column(30, [31, 37, ['joins', [[[2048, 12], [524288, 19]]]], ['norm', 3]]),
    'joins long block': column(30, [32, 37, ['joins', [[[1024, 12], [2 ** 20, 20]]]], ['norm', 3]]),
    'joins empty': column(30, [31, 37, ['joins', []], ['norm', 3]]),
    'mstar above 9': column(10, [10, 10, ['thue-morse'], ['mstar', ['residue', 3]]]),
    'mstar kind': column(5, [5, 5, ['thue-morse'], ['mstar', ['guess']]]),
    'mstar two': column(2, [2, 2, ['thue-morse'], ['mstar', ['two']]]),
    'norm composite': column(30, [31, 37, ['power', 1, 6], ['norm', 9]]),
    'norm two': column(30, [31, 37, ['power', 1, 6], ['norm', 2]]),
    'norm bound': column(30, [31, 38, ['power', 1, 6], ['norm', 3]]),
    'residue chain': column(30, [31, 37, ['power', 1, 6], ['residue', [9, 3]]]),
    'residue one': column(30, [31, 37, ['power', 1, 6], ['residue', [1]]]),
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
const chrome = spawn(C.chrome, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${C.dir}/profile`,
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars', 'about:blank'],
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
  const tokens = ['exists', 'open', 'impossible', 'paper', 'ink'].map(t => [t, css.getPropertyValue('--' + t).trim()]);
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
  return {plot: box(svg.getBoundingClientRect()), svgs: chart.querySelectorAll('svg').length,
    rects: svg.querySelectorAll('rect').length, texts, innerWidth, scrollW: document.documentElement.scrollWidth,
    canvas: box(document.getElementById('mstar-chart').getBoundingClientRect())};
};
const DOM = cells => cells.map(([k, e, x, y]) => {
  const el = document.elementFromPoint(x, y);
  return [k, e, el.tagName.toLowerCase(), getComputedStyle(el).fill];
});
const READ = text => {
  const ro = document.getElementById('pow2-readout');
  const children = [...ro.children].map(c => c.className);
  return {text: text(ro), children, scrollW: document.documentElement.scrollWidth};
};
const FRAMES = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

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
  await send('CSS.disable');
  await send('DOM.disable');
  const log = current.errors;
  current = page;
  return {subs, log, family: await ev(() => getComputedStyle(document.getElementById('pow2-readout')).fontFamily)};
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
    if (!C.drawn) continue;
    await ev(() => document.getElementById('pow2-chart').scrollIntoView({block: 'center'}));
    await ev(FRAMES);
    R.geo = await ev(GEOMETRY);
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
    const [cl, ct, cw] = (await ev(GEOMETRY)).canvas, T2 = await ev(() => MSTAR.mtop), [ML, MR, MT, MP] = C.mstarLayout;
    for (const [k, m] of C.mstarCells) {        // cell (2^k, m) of the m*(n) chart in its full view of the 500 even n
      await input.mouse(cl + ML + (2 ** k / 2 - 0.5) * (cw - ML - MR) / 500, ct + MT + (T2 - m) * MP + (MP - 2) / 2);
      R.mstar.push([k, m, await ev(() => document.getElementById('mstar-readout').textContent)]);
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
# swipe follows the outline's tap (swipe).
DESKTOP = dict(width=1280, height=900, mobile=False, swipe=False)
PHONE = dict(width=390, height=844, mobile=True, swipe=True)
CONFIGS = {
    'light': DESKTOP | dict(data=['real'], dpr=2, theme='light', drawn=True, hover=True, tap=False, mstar=True),
    'phone': PHONE | dict(data=['real'], dpr=3, theme='light', drawn=True, hover=False, tap=True, mstar=False),
    'kinds': DESKTOP | dict(data=['kinds'], dpr=1, theme='light', drawn=True, hover=True, tap=False, mstar=False),
    'missing': DESKTOP | dict(data=[None], dpr=1, theme='light', drawn=False, hover=False, tap=False, mstar=False),
    'violations': DESKTOP | dict(data=list(VIOLATIONS), dpr=1, theme='light', drawn=False, hover=False, tap=False,
                                 mstar=False),
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
            for f in (INDEX, MSTAR) + tuple(os.path.join(HERE, icon) for icon in ICONS): shutil.copy(f, p)
            js = SOURCES[source]() if source else None
            if js: open(os.path.join(p, 'pow2.js'), 'w', encoding='utf-8').write(js)
            urls.append('file://' + os.path.join(p, 'index.html'))
            datas.append(pow2_of(js) if c['drawn'] else None)
        data = datas[0]
        # the cells (2^k, hi + 1) of the m*(n) chart to read out, for the k whose hiWhy is ["mstar", why]
        mstar = [[k, data['cols'][k - 1][1] + 1] for k in range(1, 10)
                 if c['mstar'] and data['cols'][k - 1][3][0] == 'mstar']
        shots = [os.path.join(d, 'load.png'), os.path.join(d, 'outline.png')]
        cfg = {k: c[k] for k in ('width', 'height', 'dpr', 'mobile', 'theme', 'drawn', 'hover', 'tap', 'swipe')} | dict(
            chrome=CHROME, dir=d, urls=urls, K=K, E=data['etop'] if data else 0, ROW=ROW, GAP=GAP, outline=OUTLINE,
            swipeFrom=SWIPE, shots=shots, mstarCells=mstar, mstarLayout=MSTAR_LAYOUT)
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
    return L + (k - 1) * W / K, T + (E - e) * ROW, L + k * W / K, T + (E - e) * ROW + ROW - GAP


# ---------------------------------------------------------------------------------------------------------------------
# Static quals

def q_section_follows_mstar_chart():
    # Replicata: index.html.
    # Expectata: the m*(n) chart's <section class="mstar" aria-labelledby="mstar-title"> is followed, with only blank
    # lines and comments between, by <section class="pow2" aria-labelledby="pow2-title">, and that by <section
    # class="remarks">.  The new section holds, in order: the heading, the h2 pow2-title; a link to record_gaps.wl,
    # the script of the table behind Theorem 1 (Stan Wagon's request, 2026-10-18; quals_record_gaps checks it), and
    # that table (dreeves, 2026-10-18), its body filled from pow2.js, in a sideways-scrolling div; a paragraph of class
    # pow2-caption; the legend, its swatches exists, open and impossible, as the m*(n) chart's; the div pow2-chart, an
    # image with a label; and the readout paragraph pow2-readout, a polite live region.
    text, filler = page(), r'(?:\s|<!--.*?-->)*'
    m = re.search(r'<section class="mstar" aria-labelledby="mstar-title">.*?</section>', text, re.S)
    assert m
    s = re.match(filler + r'(<section class="pow2" aria-labelledby="pow2-title">.*?</section>)', text[m.end():], re.S)
    assert s, text[m.end():m.end() + 400]
    rest = text[m.end() + s.end():]
    assert re.match(filler + r'<section class="remarks">', rest, re.S), rest[:400]
    parts = [r'<h2 id="pow2-title">', r'href="https://raw\.githubusercontent\.com/dreeves/equipow/main/record_gaps\.wl"',
             r'<div class="scroll">', r'<table class="pow2-gaps" data-record-gaps>', r'<p class="pow2-caption">',
             r'<ul class="legend">', r'<span class="swatch exists" aria-hidden="true">',
             r'<span class="swatch open" aria-hidden="true">', r'<span class="swatch impossible" aria-hidden="true">', r'</ul>',
             r"<div id=\"pow2-chart\" role=\"img\" aria-label='[^']+'></div>", r'<p id="pow2-readout" aria-live="polite">']
    assert re.search('.*?'.join(parts), s.group(1), re.S), s.group(1)


def q_scripts_load_pow2_after_mstar():
    # Replicata: index.html's script tags.
    # Expectata: exactly six, after </main>: the m*(n) chart's <script src="mstar.js"> and its inline script, then a
    # classic <script src="pow2.js"> (no type, async or defer, so it also loads from file://) right after them and one
    # inline script; then the inline script of the table of smallest lengths (2026-10-17); then the inline script of
    # the section "Search progress" (2026-10-17), the last thing before </body>.
    text = page()
    tags = re.findall(r'<script\b[^>]*>', text)
    assert tags == ['<script src="mstar.js">', '<script>', '<script src="pow2.js">', '<script>', '<script>', '<script>'], tags
    assert text.index('</main>') < text.index('<script src="mstar.js"></script>')
    assert text.count('</script>\n<script src="pow2.js"></script>\n<script>\n') == 1
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


def q_inline_script_passes_node_check():
    # Replicata: this chart's inline script (the page's second), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    d = tempfile.mkdtemp(prefix='pow2-quals-')
    path = os.path.join(d, 'chart.js')
    open(path, 'w', encoding='utf-8').write(scripts()[1])
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_new_css_is_scoped():
    # Replicata: this chart's CSS: the paragraph of the style block (its lines between blank lines) that holds the
    # rule for .pow2, comments removed.
    # Expectata: it is whole rules, and every selector of every rule starts with .pow2 or #pow2 (a class or id of the
    # new section), so this chart's CSS styles nothing of the frozen m*(n) chart or the rest of the page.
    style = re.search(r'<style>\n(.*?)</style>', page(), re.S).group(1)
    block = next(b for b in re.split(r'\n\s*\n', style) if re.search(r'^\.pow2 \{', b, re.M))
    css = re.sub(r'/\*.*?\*/', '', block, flags=re.S)
    rules = re.findall(r'([^{}]+)\{([^{}]*)\}', css)
    assert rules and re.fullmatch(r'\s*', re.sub(r'[^{}]+\{[^{}]*\}', '', css)), css
    selectors = [s.strip() for sel, _ in rules for s in sel.split(',')]
    assert all(re.match(r'[.#]pow2(?![\w])|[.#]pow2-', s) for s in selectors), selectors


def q_caption_defines_readout_symbols():
    # Replicata: the caption (the paragraph pow2-caption).
    # Expectata: it names each symbol that the readout writes for a block of a construction: f, τ_j (Thue-Morse), p_n
    # (from a column of the m*(n) chart) and, since 2026-10-26, each of the page's examples longer than 1000 (LONG:
    # p_1024), each as the remarks write it: <i>f</i>, τ<sub><i>j</i></sub>, <i>p</i><sub><i>n</i></sub> and
    # <i>p</i><sub>1024</sub>.
    m = re.search(r'<p class="pow2-caption">(.*?)</p>', page(), re.S)
    assert m, 'pow2-caption'
    symbols = ['<i>f</i>', 'τ<sub><i>j</i></sub>', '<i>p</i><sub><i>n</i></sub>'] + [f'<i>p</i><sub>{n}</sub>' for n, _ in long_blocks()]
    missing = [s for s in symbols if s not in m[1]]
    assert not missing and long_blocks(), (missing, long_blocks())


def long_blocks():
    """The chart script's LONG, the examples longer than 1000 that its blocks may use, as [[n, m], ...] (JSON)."""
    m = re.search(r'\n  const LONG = (\[[^\n;]*\]);', scripts()[1])
    assert m, 'no const LONG in the chart script'
    return json.loads(m.group(1))


def q_long_blocks_are_the_remarks_examples():
    # Replicata: the chart script's LONG; the remarks' code blocks, each p_n of order m alone, decoded by the paper's
    # Table 5 convention (the left half of the signs, 1 = +1, then the rest by (-1)^m symmetry); and pow2.js's blocks.
    # Expectata (2026-10-26: Claude's example of order 11 at 1024, beyond the m*(n) chart's 1000): LONG is exactly the
    # remarks' examples of length n > 1000, as [n, m], in page order, each decoding to length n and order exactly m
    # (synthetic division); and every block of pow2.js's joins longer than 1000, other than f and τ_j, is in LONG.
    codes = re.findall(r'<i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n\s*<code>([0-9A-F]+)</code>',
                       page())
    long = [(int(n), int(m), h) for n, m, h in codes if int(n) > 1000]
    assert long_blocks() == [[n, m] for n, m, _ in long] == [[1024, 11]], (long_blocks(), long)
    for n, m, h in long:
        left = [2 * int(b) - 1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        c, k = left + [(-1) ** m * s for s in reversed(left)], 0
        assert len(c) == n, (n, len(c))
        while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
        assert k == m, (n, m, k)
    used = {tuple(b) for c in pow2_of(real())['cols'] if c[2][0] == 'joins' for p in c[2][1] for b in p
            if b[0] > 1000 and b != F and b[0] != 2 ** b[1]}
    assert used <= {tuple(b) for b in long_blocks()} and used, used


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
    # (exists when k + e <= lo, open when lo < k + e <= hi, impossible above); the pixel in the middle of the gap below
    # each cell is paper; the element at each cell's middle is an svg rect whose computed fill is that color.
    for name in DRAWN:
        R = valid(name)
        cols, tok = R['data']['cols'], R['load']['tokens']
        bad = []
        for k, e, tag, f in R['dom']:
            want = tok[KINDS[kind_of(cols[k - 1], k, e)]]
            x0, y0, x1, y1 = cell_box(R, 'geo', k, e)
            got = (pixel(R, 0, (x0 + x1) / 2, (y0 + y1) / 2), pixel(R, 0, (x0 + x1) / 2, y1 + GAP / 2), tag, fill(f))
            if got != (want, tok['paper'], 'rect', want): bad.append((k, e, want, got))
        assert len(R['dom']) == K * R['data']['etop'] and not bad, (name, len(bad), bad[:10])


def q_hover_reads_out_every_cell():
    # Replicata: the 1280 px light configuration: a real mouse move to the middle of every cell, column by column.
    # Expectata: after each, the readout is that cell's: its first child is a swatch of the cell's kind, and its text
    # (each <sup> written ^(…)) is "k = K, n = 2^(K), m = K + E = M · MEANING · lo ≤ m^(*)(2^(K)) ≤ hi · REASONS":
    # MEANING dreeves's word for the cell's kind (MEANINGS: known, open, impossible); REASONS the
    # Claude: "…" of lo's reason for a green cell, of hi's for a red one and both for a gray one, joined by " · ", lo's
    # starting "order lo " and hi's "order hi + 1 ", each holding its reason's math (reason_math).
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
    # readout's font-family.  (While DevTools reads the fonts it logs only that a file: page may not load itself.)
    k, e = OUTLINE
    for name in DRAWN:
        R = valid(name)
        text, fonts, (lo, hi, lw, hw) = R['outline']['text'], R['subFonts'], R['data']['cols'][k - 1]
        family = fonts['family'].split(',')[0].strip().strip('"')
        assert all(x.startswith('log error security: Unsafe attempt to load URL file:') for x in fonts['log']), fonts
        assert lw[0] == 'joins' and not re.search('[₀-₉]', text), (name, lw[0], text)
        assert len(fonts['subs']) == text.count('_(') >= sum(map(len, lw[1])), (name, text, fonts)
        assert all(f == [family] for f in fonts['subs']), (name, family, fonts['subs'])


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


def q_labels_mark_every_e_and_round_k():
    # Replicata: the text nodes in #pow2-chart and their boxes, in the 1280 px and 390 px light configurations.
    # Expectata: they are exactly: the numbers 1..E left of the plot, number e's box centered on row e's colored part
    # (within 1 px), all with one right edge (within 0.5 px) at most 10 px left of the plot; the numbers 10, 20, ..., 70
    # below the plot, each centered on its column's middle (within 1 px); the letter e left of the plot, within its
    # height; and the letter k below the plot, left of it.
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
            assert abs(y + h / 2 - (T + (E - e) * ROW + (ROW - GAP) / 2)) <= 1, (name, e, y, h)
        rights = [x + w for x, y, w, h in es.values()]
        assert max(rights) - min(rights) <= 0.5 and 0 <= L - max(rights) <= 10, (name, rights, L)
        letters = [b for t, b in left if t == 'e']
        assert len(letters) == 1 and T <= letters[0][1] + letters[0][3] / 2 <= T + H, (name, left)
        ks = {int(t): b for t, b in below if t.isdigit()}
        assert sorted(ks) == KLABELS and len(below) == len(KLABELS) + 1, (name, below)
        for k, (x, y, w, h) in ks.items(): assert abs(x + w / 2 - (L + (k - 0.5) * W / K)) <= 1, (name, k, x, w)
        letters = [b for t, b in below if t == 'k']
        assert len(letters) == 1 and letters[0][0] + letters[0][2] <= L, (name, below)


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
        assert all(R['load']['tokens'][t] == light[f'--{t}'].lower() for t in KINDS + ('paper', 'ink')), (name, R['load']['tokens'])


def q_made_up_data_reads_every_kind():
    # Replicata: made-up data that uses every kind of reason (kinds_cols), 1280 px light: a real mouse move to the
    # middle of every cell.
    # Expectata: nothing logged; every kind of loWhy and hiWhy and of the m*(n) chart's hiWhy is in the data; every
    # readout as in q_hover_reads_out_every_cell.
    R = valid('kinds')
    cols = R['data']['cols']
    assert {c[2][0] for c in cols} == {'thue-morse', 'power', 'joins'}
    assert {c[3][0] for c in cols} == {'mstar', 'norm', 'residue'}
    assert {c[3][1][0] for c in cols if c[3][0] == 'mstar'} == {'two', 'norm', 'residue', 'table2', 'page'}
    check_readouts(R['data'], R['hovers'])


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
    # least product's order, with a block that is none of f, τ_j, a column n <= 1000 and the page's example of order
    # 11 at 1024 ([2048, 12]; [1024, 12]), or with no product; an
    # "mstar" hiWhy above k = 9, of an unknown kind, or breaking its own rule; a norm bound for a composite p, for
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
