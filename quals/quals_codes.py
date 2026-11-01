#!/usr/bin/env python3
"""Quals for the page's codes and joins as buttons (dreeves's spec [REO] in index.html, item 2, 2026-10-31: "When you
click the hex code, we expand it to an explicit partition and check the arithmetic so show exactly which exponents are
equipowerful"; and later that day, when the section "Claude's examples as sets" left the page: "every bipartition we
give should be presented the same way as an expandable hex code"): each code of index.html (<code id="N:M">, N its
length and M its order, in a code block or in a sentence) and each join of its codes (<span data-join="IDS"
data-order="M">, IDS the codes' ids, its signs theirs one after the other, M its order), clicked, or given Enter or
Space while it has focus, shows right below it its partition: the positions with +1 and with -1, and the power sums of
both parts for k = 0 to M, computed exactly in the browser, and the next click hides it.  No part of a bipartition is
written out anywhere else on the page, and every set that the section of sets gave is a part of one of them.
Run: python3 -B quals/quals_codes.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The quals load copies of index.html, each with page/, mstar.js, pow2.js and the page's icons beside it, in headless
Chrome driven through the DevTools protocol by DRIVER, a Node script: a true viewport of each configuration's width and
pixel ratio, real mouse clicks (touch taps for a phone) at the middle of each code or join, and real key presses.  What
one shows is read from the element right after it.  The numbers the page shows are held to mstar.py's own reading of
the page's codes and joins (page_sources) and its decoding of them (overnight_v5.from_hex, mstar.join), with Python's
exact integers; and the sets the page gave until 2026-10-31 to SETS, the file that keeps them.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, shutil, tempfile, traceback, subprocess
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, HERE)                                              # for its modules
import mstar
import quals_index as qi                      # read only: page, blank_comments, page_codes, copy_page_dir, CHROME
import quals_pow2_page as qp                  # read only: GROUP_JS (ending Chrome's whole process group) and ICONS

RUNS = {}                                     # DRIVER's reports by configuration name, made once per process (see run)
# The sets of the page's section "Claude's examples as sets", which left the page on 2026-10-31 (dreeves: "kill the
# redundancy of the "Claude's examples as sets" section, being careful not to lose anything"), as it gave them: each
# [name, m, n, its positions], the half of a partition of 0..n-1 that contains 0, in page order, with the sha256 of
# the page they were read from (scratch/sets-20261031/extract_oracle.py)
SETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quals_codes_sets.json')


# ---------------------------------------------------------------------------------------------------------------------
# The page's codes and joins, as mstar.py reads and decodes them

CODE = re.compile(r'<code id="(\d+):(\d+)">([0-9A-F]+)</code>')
JOIN = re.compile(r'<span data-join="([^"]*)" data-order="(\d+)">')


def items(text=None):
    """[(key, n, m, signs)] for each code and join of index.html (or of text), in page order: a code, <code id="N:M"> of
    hex digits wherever it is, keyed by its id, its signs mstar.py's decoding of it (overnight_v5.from_hex) at order M,
    N their number; a join, <span data-join="IDS" data-order="M">, keyed by IDS, the ids of codes of the page separated
    by spaces, its signs theirs one after the other (mstar.join: the page's f ∨ g = f(x) + x^{n_f} g(x)).  The codes of
    the code blocks and the joins are held to mstar.page_sources' reading of them, which mstar.py holds to its own
    copies (PAGE_CODES, PAGE_JOINS); the keys are distinct."""
    text = qi.page() if text is None else text
    blank = qi.blank_comments(text)
    src = mstar.page_sources(text)
    assert [(m, h) for *_, m, _, h in qi.page_codes(blank)] == src['codes'], (qi.page_codes(blank)[:3], src['codes'][:3])
    codes = [(x.start(), f'{x[1]}:{x[2]}', int(x[2]), mstar.v5.from_hex(x[3], int(x[2]))) for x in CODE.finditer(blank)]
    assert all(int(key.split(':')[0]) == len(a) for _, key, _, a in codes), [key for _, key, _, a in codes]
    signs = dict((key, a) for _, key, _, a in codes)
    joins = [(x.start(), x[1], int(x[2]), [t for i in x[1].split(' ') for t in signs[i]]) for x in JOIN.finditer(blank)]
    assert [(m, tuple(key.split(' '))) for _, key, m, _ in joins] == src['joins'], (joins, src['joins'])
    out = [(key, len(a), m, a) for _, key, m, a in sorted(codes + joins)]
    assert len({key for key, *_ in out}) == len(out), [key for key, *_ in out]
    return out


def partition(n, m, a):
    """The partition of the signs a and its power sums: (the positions with +1, the positions with -1, [(sum of i^k over
    the first, over the second) for k = 0..m]), every number a Python int, exact.  It asserts their length n and their
    order m, both by mstar.order and by overnight_v5.exact_order (the witness agents' page_check path): equal sums
    below m, unequal at m."""
    assert len(a) == n and mstar.order(a) == m == mstar.v5.exact_order(a), (n, m)
    plus, minus = [i for i, t in enumerate(a) if t == 1], [i for i, t in enumerate(a) if t == -1]
    sums = [(sum(i ** k for i in plus), sum(i ** k for i in minus)) for k in range(m + 1)]
    assert [x == y for x, y in sums] == [k < m for k in range(m + 1)], (n, m)
    return plus, minus, sums


def numbers(text):
    """The integers of a part as the page writes them, separated by commas (and spaces), and nothing else."""
    assert re.fullmatch(r'\s*\d+(\s*,\s*\d+)*\s*', text), text[:200]
    return [int(x) for x in re.findall(r'\d+', text)]


def former_sets():
    """SETS' sets, [(name, m, n, positions)], positions a list in the page's order; it asserts the file's form: 31 sets,
    each n/2 distinct positions in 0..n-1 in rising order from 0."""
    data = json.load(open(SETS, encoding='utf-8'))
    sets = [(name, m, n, ps) for name, m, n, ps in data['sets']]
    assert len(sets) == 31 and all(ps == sorted(set(ps)) and ps[0] == 0 and ps[-1] < n == 2 * len(ps)
                                   for _, m, n, ps in sets), [s[:3] for s in sets]
    return sets


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

DRIVER = r"""
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
""" + qp.GROUP_JS + r"""
const C = JSON.parse(readFileSync(0, 'utf8'));   // chrome, dir (the page's copy and the profile), viewport, steps
const chrome = spawn(C.chrome, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${C.dir}/profile`,
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars', '--allow-file-access-from-files',
  'about:blank'], {stdio: 'ignore', detached: true});
const watchdog = setTimeout(() => { groupSignal(chrome.pid, 'SIGTERM'); process.exit(3); }, 500000);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// In the page.
const FRAMES = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
// Whether KaTeX drew the page's math, waiting up to 20 s for it
const KATEX = () => new Promise(r => { const t0 = performance.now();
  const t = () => document.querySelector('.katex') || performance.now() - t0 > 20000 ? r(!!document.querySelector('.katex')) : setTimeout(t, 50);
  t(); });
// The page's codes and joins, in page order: each code with an id and each element with data-join; and the key that
// names one, a code's id or a join's data-join.  The functions here run in the page, where DEFINE puts these two as
// qualsItems and qualsKey once it has loaded.
const ITEMS = () => [...document.querySelectorAll('code[id], [data-join]')];
const KEY = e => e.id || e.dataset.join;
// The focus (the key of the focused element), the scroll, the viewport and the page's width, each code and join as
// [key, role, tabIndex, aria-expanded], and how many partitions (class partition) show
const LOOK = () => ({active: document.activeElement && qualsKey(document.activeElement), scrollX, scrollY, innerWidth, innerHeight,
  scrollW: document.documentElement.scrollWidth,
  codes: qualsItems().map(c => [qualsKey(c), c.getAttribute('role'), c.tabIndex, c.getAttribute('aria-expanded')]),
  partitions: [...document.querySelectorAll('.partition')].filter(e => e.checkVisibility()).length});
// Item i and the element right after it: if that is a partition (class partition), whether it shows, its box, its
// parts' numbers with their boxes' heights (client, scroll); its power sums' cells, in page order: the k (data-k), the
// marks (data-relation), and each part's sums (data-sum "+1" and "-1") with the widths of the lines each takes (CSS px,
// to 0.1); and how far any cell of its power sums reaches past its right edge (spill, CSS px; at most 0 when none does)
const READ = i => {
  const code = qualsItems()[i], next = code.nextElementSibling;
  const rect = e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  const box = next && next.classList.contains('partition') ? next : null;
  const part = s => { const e = box.querySelector(`[data-part="${s}"]`);
    return e && [e.textContent, e.parentElement.clientHeight, e.parentElement.scrollHeight]; };
  const cells = s => [...box.querySelectorAll(s)];
  const lines = c => { const r = document.createRange(); r.selectNodeContents(c);
    return [...r.getClientRects()].map(q => Math.round(q.width * 10) / 10); };
  return {id: qualsKey(code), expanded: code.getAttribute('aria-expanded'), code: rect(code), next: next && next.tagName,
    box: box && {shown: box.checkVisibility(), rect: rect(box), parts: [part('+1'), part('-1')],
      ks: cells('[data-k]').map(c => c.textContent), relations: cells('[data-relation]').map(c => c.textContent),
      sums: ['+1', '-1'].map(s => cells(`[data-sum="${s}"]`).map(c => [c.textContent, lines(c)])),
      spill: Math.max(...cells('[data-power-sums] th, [data-power-sums] td').map(c => c.getBoundingClientRect().right)) - rect(box)[2]}};
};
// Item i scrolled to the middle of the viewport
const SHOW = i => { qualsItems()[i].scrollIntoView({block: 'center'}); return 0; };
// The middle of the first line of item i (a code in a sentence may wrap), in CSS px of the viewport, and whether the
// element there is the item or inside it
const MIDDLE = i => { const e = qualsItems()[i], b = e.getClientRects()[0], x = b.left + b.width / 2, y = b.top + b.height / 2;
  return [x, y, e.contains(document.elementFromPoint(x, y))]; };
// The box of the block of item i (its parent element), in CSS px of the page (scroll included)
const BLOCK = i => { const b = qualsItems()[i].parentElement.getBoundingClientRect();
  return [b.left + scrollX, b.top + scrollY, b.width, b.height]; };
// Every code of the page whose text is two or more hex digits and nothing else (a lone digit is a number, as the
// lattice section's seed 3), as [its text, its id, role, aria-expanded]; every element with data-join, as [data-join,
// role, aria-expanded]; and the runs of integers separated by commas in main's text outside the partitions (class
// partition), as the number of integers in each, the five longest
const SCAN = () => {
  const main = document.querySelector('main').cloneNode(true);
  main.querySelectorAll('.partition').forEach(p => p.remove());
  return {hex: [...document.querySelectorAll('code')].filter(c => /^[0-9A-F]{2,}$/.test(c.textContent))
                 .map(c => [c.textContent, c.id, c.getAttribute('role'), c.getAttribute('aria-expanded')]),
          joins: [...document.querySelectorAll('[data-join]')].map(e => [e.dataset.join, e.getAttribute('role'), e.getAttribute('aria-expanded')]),
          runs: (main.textContent.match(/\d+(?:\s*,\s*\d+)+/g) || []).map(r => r.split(',').length).sort((a, b) => b - a).slice(0, 5)};
};

let ws, seq = 0;
const errors = [], pending = new Map(), once = new Map();
const send = (method, params = {}) => new Promise((ok, no) => {
  const id = ++seq;
  pending.set(id, d => d.error ? no(new Error(`${method}: ${JSON.stringify(d.error)}`)) : ok(d.result));
  ws.send(JSON.stringify({id, method, params}));
});
const next = method => new Promise(r => once.set(method, r));       // the next event of the method
const ev = async (f, ...args) => {                                  // the value of f(...args) in the page
  const expression = `(${f})(${args.map(a => JSON.stringify(a)).join(', ')})`;
  const r = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (r.exceptionDetails) throw new Error(`${expression.slice(0, 200)}: ${JSON.stringify(r.exceptionDetails).slice(0, 900)}`);
  return r.result.value;
};
// ITEMS and KEY in the page, as qualsItems and qualsKey
const DEFINE = () => `window.qualsItems = ${ITEMS}; window.qualsKey = ${KEY}; 0`;
const LINES = {                      // the lines that each kind of event logs (none for a log entry below a warning)
  'Runtime.exceptionThrown': ({exceptionDetails: x}) =>
    `exception: ${x.text} ${(x.exception || {description: ''}).description.split('\n')[0]}`,
  'Runtime.consoleAPICalled': p => `console.${p.type}: ${p.args.map(a => a.value ?? a.description).join(' ')}`,
  'Log.entryAdded': ({entry: x}) => ['error', 'warning'].includes(x.level) ? `log ${x.level} ${x.source}: ${x.text} ${x.url || ''}` : null,
};
const KEYS = {Tab: ['Tab', 'Tab', 9, ''], Enter: ['Enter', 'Enter', 13, '\r'], Space: [' ', 'Space', 32, ' ']};
const OPS = {
  // the page loaded, its fonts ready and KaTeX's math drawn: whether it was
  load: async () => {
    const loaded = next('Page.loadEventFired');
    await send('Page.navigate', {url: C.url});
    await loaded;
    await send('Runtime.evaluate', {expression: DEFINE(), returnByValue: true});
    await ev(() => document.fonts.ready.then(() => 0));
    const katex = await ev(KATEX);
    await ev(FRAMES);
    return {katex};
  },
  look: () => ev(LOOK),
  read: i => ev(READ, i),
  scan: () => ev(SCAN),
  // a real click (a phone's touch tap) at the middle of the first line of item i, scrolled to the middle of the
  // viewport: where, and whether the element there just before was the item or inside it
  click: async i => {
    await ev(SHOW, i);
    await ev(FRAMES);
    const [x, y, hit] = await ev(MIDDLE, i);
    if (C.mobile) {
      await send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y}]});
      await send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
    } else {
      for (const type of ['mousePressed', 'mouseReleased']) {
        await send('Input.dispatchMouseEvent', {type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1});
      }
    }
    await sleep(50);
    await ev(FRAMES);
    return [x, y, hit];
  },
  // a real key press, to the element with focus
  key: async name => {
    const [key, code, keyCode, text] = KEYS[name];
    await send('Input.dispatchKeyEvent', {type: text ? 'keyDown' : 'rawKeyDown', key, code, windowsVirtualKeyCode: keyCode, ...(text ? {text} : {})});
    await send('Input.dispatchKeyEvent', {type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode});
    await ev(FRAMES);
    return name;
  },
  // Tab pressed until the element with focus matches selector, at most most times: the presses and its key (null if
  // none)
  tabTo: async (selector, most) => {
    for (let i = 1; i <= most; i++) {
      await OPS.key('Tab');
      if (await ev(s => !!document.activeElement && document.activeElement.matches(s), selector)) return [i, await ev(() => qualsKey(document.activeElement))];
    }
    return [most, null];
  },
  // a screenshot of the block of item i, pad CSS px around it, to path (for the screenshots in scratch/, no qual's):
  // the block scrolled to pad CSS px below the viewport's top, and shot within the viewport (a shot beyond it resizes
  // the viewport for a moment, which the m*(n) chart's script, redrawn at that size, throws on)
  shot: async (path, i, pad) => {
    await ev((j, p) => { scrollBy(0, qualsItems()[j].parentElement.getBoundingClientRect().top - p); return 0; }, i, pad);
    await ev(FRAMES);
    const [x, y, w, h] = await ev(BLOCK, i);
    const {data} = await send('Page.captureScreenshot', {format: 'png',
      clip: {x: Math.max(0, x - pad), y: Math.max(0, y - pad), width: w + 2 * pad, height: h + 2 * pad, scale: 1}});
    writeFileSync(path, Buffer.from(data, 'base64'));
    return path;
  },
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
    const line = LINES[d.method] && LINES[d.method](d.params);
    if (line) errors.push([steps.length, line]);
  };
  for (const m of ['Page.enable', 'Runtime.enable', 'Log.enable']) await send(m);
  await send('Emulation.setDeviceMetricsOverride', {width: C.width, height: C.height, deviceScaleFactor: C.dpr, mobile: C.mobile});
  await send('Emulation.setTouchEmulationEnabled', {enabled: C.mobile, maxTouchPoints: 1});
  for (const [op, ...args] of C.steps) steps.push(await OPS[op](...args));
}

// The report goes to a file, which a pipe's asynchronous writes could cut short at process.exit: each step's result
// and the lines logged, each with the number of steps done before it.  Chrome's whole process group is ended
// (endGroup) before exit, so that run can remove its profile.
const steps = [];
let code = 0;
try { await main(); writeFileSync(`${C.dir}/report.json`, JSON.stringify({steps, errors})); }
catch (e) { writeFileSync(`${C.dir}/report.json`, JSON.stringify({error: String(e && e.stack || e), steps, errors})); code = 1; }
finally { clearTimeout(watchdog); if (ws) ws.close(); }
await endGroup(chrome.pid);
process.exit(code);
"""

DESKTOP = dict(width=1280, height=900, dpr=2, mobile=False)
PHONE = dict(width=390, height=844, dpr=3, mobile=True)


def drive(viewport, steps, text=None):
    """DRIVER's report on a copy of index.html (or of text) in a temporary directory with page/, mstar.js, pow2.js and
    the page's icons beside it, in the viewport given (DESKTOP, PHONE): {'steps': each step's result, 'errors':
    [(the number of steps done, a line logged)]}.  A step is [op, ...args] of DRIVER's OPS."""
    d = tempfile.mkdtemp(prefix='codes-quals-')
    try:
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(qi.page() if text is None else text)
        qi.copy_page_dir(d)
        for f in ('mstar.js', 'pow2.js') + qp.ICONS: shutil.copy(os.path.join(HERE, f), d)
        cfg = viewport | dict(chrome=qi.CHROME, dir=d, url='file://' + os.path.join(d, 'index.html'), steps=steps)
        p = subprocess.run(['node', '--input-type=module', '-e', DRIVER], input=json.dumps(cfg), capture_output=True,
                           text=True, timeout=600)
        path = os.path.join(d, 'report.json')
        report = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'error': p.stderr[-4000:]}
        assert p.returncode == 0 and 'error' not in report, (p.returncode, report.get('error'), report.get('errors'))
        assert len(report['steps']) == len(steps), (len(report['steps']), len(steps))
        return report
    finally:
        shutil.rmtree(d)


def largest():
    """The index of the page's longest code or join (1024:11)."""
    page = items()
    return max(range(len(page)), key=lambda i: page[i][1])


# The page with one code's id changed, for the quals that the page fails loudly: WRONG_ORDER says the first code (352:9,
# BGPW's, of order 9) has order 10; WRONG_LENGTH says it has length 360 (its 44 hex digits make 352).  And the page's
# join changed: JOIN_ORDER says it has order 11 (it has 10), and MISSING names a code the page does not have (336:8
# for q336's 336:9).
FIRST = '352:9'
WRONG_ORDER, WRONG_LENGTH = '352:10', '360:9'
F528 = '<span data-join="192:9 336:9" data-order="10">'
JOIN_ORDER, MISSING = '<span data-join="192:9 336:9" data-order="11">', '<span data-join="192:9 336:8" data-order="10">'


def changed(new):
    """index.html with the first code's id, FIRST, changed to new."""
    text = qi.page()
    assert text.count(f'<code id="{FIRST}">') == 1
    return text.replace(f'<code id="{FIRST}">', f'<code id="{new}">')


def changed_join(new):
    """index.html with the join's tag, F528, changed to new."""
    text = qi.page()
    assert text.count(F528) == 1
    return text.replace(F528, new)


def run(name):
    """DRIVER's report for one configuration, made on first use:
    light: 1280 px wide; at load the codes and joins; then Tab pressed until one has focus, and Enter, Enter, Space and
           Space to it, read after each; then each code and join clicked twice, read after each click; then the page
           scanned.
    phone: 390 px wide, a phone's; the largest code tapped and read, the page looked at; then every other code and join
           tapped and read, and the page looked at.
    order: the page with WRONG_ORDER for FIRST, clicked and read.
    length: the page with WRONG_LENGTH for FIRST, as loaded.
    joinorder: the page with JOIN_ORDER for the join, clicked and read.
    missing: the page with MISSING for the join, as loaded."""
    if name not in RUNS:
        page, big = [key for key, *_ in items()], largest()
        keys = [['tabTo', 'code[id], [data-join]', 400]] + [s for k in ('Enter', 'Enter', 'Space', 'Space')
                                                             for s in (['look'], ['key', k], ['look'], ['read', 0])]
        steps = {                                     # each configuration's (viewport, steps, page), made when run
            'light': lambda: (DESKTOP, [['load'], ['look']] + keys
                              + [s for i in range(len(page)) for s in (['click', i], ['read', i]) * 2] + [['scan']], None),
            'phone': lambda: (PHONE, [['load'], ['click', big], ['read', big], ['look']]
                              + [s for i in range(len(page)) if i != big for s in (['click', i], ['read', i])]
                              + [['look']], None),
            'order': lambda: (DESKTOP, [['load'], ['look'], ['click', page.index(FIRST)], ['read', page.index(FIRST)]],
                              changed(WRONG_ORDER)),
            'length': lambda: (DESKTOP, [['load'], ['look']], changed(WRONG_LENGTH)),
            'joinorder': lambda: (DESKTOP, [['load'], ['look'], ['click', page.index('192:9 336:9')],
                                            ['read', page.index('192:9 336:9')]], changed_join(JOIN_ORDER)),
            'missing': lambda: (DESKTOP, [['load'], ['look']], changed_join(MISSING)),
        }[name]()
        RUNS[name] = drive(steps[0], steps[1], steps[2])
    return RUNS[name]


def shown(R):
    """The light run's reads of open partitions (aria-expanded true), by key."""
    return {s['id']: s for s in R['steps'][2:] if isinstance(s, dict) and s.get('expanded') == 'true'}


# ---------------------------------------------------------------------------------------------------------------------
# Quals

def q_codes_show_their_partitions():
    # Replicata: index.html in headless Chrome, 1280 px wide (the light run): each code and join, in page order, clicked
    # (a real mouse click at the middle of its first line), and the element right after it read: its two parts' numbers
    # ([data-part="+1"], [data-part="-1"]) and its power sums' cells, in page order: the k (data-k), the marks
    # (data-relation) and the sums over each part (data-sum "+1" and "-1").
    # Expectata (dreeves's [REO] item 2: "When you click the hex code, we expand it to an explicit partition and check
    # the arithmetic so show exactly which exponents are equipowerful"; 2026-10-31: "every bipartition we give should be
    # presented the same way as an expandable hex code"): every code (in a code block or in a sentence) and every join
    # is a button, and its click shows, right after it and below it, its partition: the positions with +1 and the
    # positions with -1, as mstar.py decodes the code (overnight_v5.from_hex) or the join's codes one after the other
    # (mstar.join); and for each k = 0, 1, ..., m: k, the sum of i^k over the first part and over the second, each
    # Python's exact integer digit for digit, and = between them for every k < m and ≠ at k = m, which is order m
    # (mstar.order and overnight_v5.exact_order agree on it); and nothing is logged.
    # Resultata before: a click on a code showed nothing: no element of class partition after it.  Then (2026-10-31,
    # until the sets left the page) the two codes in the proof of m*(416) = 9 were no buttons, and the 528 entry's join
    # was no element of its own.
    R = run('light')
    assert R['errors'] == [], R['errors'][:5]
    load = R['steps'][1]
    page = items()
    assert [c[0] for c in load['codes']] == [c[0] for c in page] and len(page) >= 42, (load['codes'][:3], len(page))
    opened = shown(R)
    bad = []
    for i, n, m, a in page:
        plus, minus, sums = partition(n, m, a)
        s = opened.get(i)
        box = s and s['box']
        if not (box and box['shown'] and box['rect'][1] >= s['code'][3] - 0.5):
            bad.append((i, 'no partition below it', s))
            continue
        parts = [numbers(t) for t, *_ in box['parts']]
        got = [box['ks'], [x for x, _ in box['sums'][0]], box['relations'], [y for y, _ in box['sums'][1]]]
        want = [[str(k) for k in range(m + 1)], [str(x) for x, _ in sums], ['=' if x == y else '≠' for x, y in sums],
                [str(y) for _, y in sums]]
        if parts != [plus, minus] or got != want:
            bad.append((i, [p[:8] for p in parts], [g[:2] for g in got], [w[:2] for w in want]))
    assert bad == [], (len(bad), bad[:3])


def q_a_second_click_hides_the_partition():
    # Replicata: the light run: each code and join at load, and after each of its two clicks.
    # Expectata: at load every code and join is a button (role button), in the tab order (tabIndex 0) and collapsed
    # (aria-expanded false), with no partition shown after it; its first click shows its partition and makes it expanded
    # (aria-expanded true); its second click hides the partition again (none shown) and makes it collapsed; and it is
    # under the pointer at each click.
    # Resultata before: no code had a role, a tabIndex of 0 or aria-expanded, and clicks showed nothing.  Then (until
    # the sets left the page) the two codes of the proof of m*(416) = 9 were no buttons.
    R = run('light')
    load = R['steps'][1]
    assert all(c[1:] == ['button', 0, 'false'] for c in load['codes']), [c for c in load['codes'] if c[1:] != ['button', 0, 'false']][:5]
    assert load['partitions'] == 0, load['partitions']
    keys = [c[0] for c in items()]
    clicks = R['steps'][-4 * len(keys) - 1:-1]
    assert len(clicks) == 4 * len(keys)
    bad = []
    for j, i in enumerate(keys):
        first, opened, second, closed = clicks[4 * j:4 * j + 4]
        states = [opened['id'], opened['expanded'], bool(opened['box'] and opened['box']['shown']),
                  closed['expanded'], bool(closed['box'] and closed['box']['shown']), first[2], second[2]]
        if states != [i, 'true', True, 'false', False, True, True]: bad.append((i, states))
    assert bad == [], bad[:5]


def q_codes_take_tab_enter_and_space():
    # Replicata: the light run, as loaded: Tab pressed until a code or join has focus; then, to it, Enter, Enter, Space
    # and Space, real key presses, the page looked at before and after each and the item read after each.
    # Expectata: the button semantics a reader with a keyboard needs: Tab reaches the codes, and the first one it reaches
    # is the page's first; Enter shows its partition, Enter hides it, Space shows it and Space hides it (aria-expanded
    # true, false, true, false); the focus stays on it; and Space does not scroll the page, as a button keeps it from
    # doing.
    # Resultata before: Tab never reached a code (400 presses), not being in the tab order.
    R = run('light')
    first = items()[0][0]
    tabs, reached = R['steps'][2]
    assert reached == first, (tabs, reached)
    presses = [R['steps'][3 + 4 * j:7 + 4 * j] for j in range(4)]           # look, key, look, read
    got = [(key, after['active'], read['expanded'], bool(read['box'] and read['box']['shown']))
           for before, key, after, read in presses]
    assert got == [('Enter', first, 'true', True), ('Enter', first, 'false', False),
                   ('Space', first, 'true', True), ('Space', first, 'false', False)], got
    assert all(before['scrollY'] == after['scrollY'] for before, key, after, read in presses if key == 'Space'), \
        [(before['scrollY'], after['scrollY']) for before, key, after, read in presses]


def q_partitions_fit_a_phone():
    # Replicata: index.html as a phone shows it (390 px wide, 844 tall, 3 device px per CSS px, touch; the phone run):
    # the largest code (the most hex digits, 1024:11) tapped, then every other code and join tapped too, each read after
    # its tap.
    # Expectata (keep it compact; no sideways scroll at phone width): the largest code's partition shows within the
    # viewport's width, with the page no wider than the viewport, and each part's numbers wrap in a box that scrolls
    # (its content taller than it) rather than growing; every partition, the largest's among them, is no taller than
    # the viewport, and no cell of its power sums reaches past its right edge, so that each = or ≠ shows beside its
    # sums, none in a frame scrolled out of view; equal sums wrap alike (the same lines, each as wide as the other's),
    # so that they can be compared digit for digit; with every partition shown, the page is still no wider than the
    # viewport; and nothing is logged.
    # Resultata before: a tap on a code showed nothing.  Then (2026-10-31, the first layout, the sums side by side in a
    # frame that scrolled sideways): the rows of 38 of the 39 partitions reached past the partition's right edge, the
    # largest code's by 312 px, = and ≠ with them.  Then (the second, side by side, each sum wrapping in its column): 104
    # rows of equal sums in 16 codes wrapped differently, 1024:11's at k = 4 on one line in the first column and two in
    # the second (scratch/reo-expander-20261031/red/wrap_alike_side_by_side.log).
    R = run('phone')
    assert R['errors'] == [], R['errors'][:5]
    read, look, last = R['steps'][2], R['steps'][3], R['steps'][-1]
    box = read['box']
    assert read['id'] == items()[largest()][0] and box and box['shown'], read
    left, top, right, bottom = box['rect']
    assert 0 <= left and right <= look['innerWidth'] == 390 and look['scrollW'] <= look['innerWidth'], (box['rect'], look['scrollW'])
    assert all(client < scroll for _, client, scroll in box['parts']), [p[1:] for p in box['parts']]
    reads = [read] + R['steps'][5:-1:2]
    assert sorted(r['id'] for r in reads) == sorted(c[0] for c in items()), [r['id'] for r in reads][:5]
    bad = [(r['id'], r['box'] and (r['box']['shown'], r['box']['rect'], r['box']['spill'])) for r in reads
           if not (r['box'] and r['box']['shown'] and r['box']['spill'] <= 0.5
                   and r['box']['rect'][3] - r['box']['rect'][1] <= look['innerHeight'])]
    assert bad == [], (len(bad), bad[:4])
    unlike = [(r['id'], k, lx, ly) for r in reads for k, ((x, lx), (y, ly)) in enumerate(zip(*r['box']['sums']))
              if x == y and lx != ly]
    assert all(len(r['box']['sums'][0]) == len(r['box']['sums'][1]) >= 2 for r in reads) and unlike == [], (len(unlike), unlike[:4])
    assert last['scrollW'] <= last['innerWidth'] and all(c[3] == 'true' for c in last['codes']), \
        (last['scrollW'], [c for c in last['codes'] if c[3] != 'true'][:3])


def q_a_code_that_is_not_its_id_fails_loudly():
    # Replicata: the page with the id of its first code, 352:9 (BGPW's, of order 9, 44 hex digits), changed: to
    # 352:10, an order its power sums do not have, and the code clicked (the order run); and to 360:9, a length its
    # digits do not make, as loaded (the length run).
    # Expectata (fail loudly, never fix silently): the click on the code said to have order 10 throws an error that names
    # it, and shows no partition, the code staying collapsed; the code said to have length 360 makes the page throw an
    # error that names it as it loads.
    # Resultata before: the clicks did nothing and nothing was thrown, codes being no buttons.
    R = run('order')                          # steps: load, look, click (step 2), read
    assert R['errors'] and all(k == 2 for k, _ in R['errors']) and any(WRONG_ORDER in line for _, line in R['errors']), R['errors']
    read = R['steps'][3]
    assert read['expanded'] == 'false' and not (read['box'] and read['box']['shown']), read
    R = run('length')                         # steps: load (step 0), look
    assert R['errors'] and all(k == 0 for k, _ in R['errors']) and any(WRONG_LENGTH in line for _, line in R['errors']), R['errors']


def q_a_join_that_is_not_its_order_fails_loudly():
    # Replicata: the page with its join, f = p192 ∨ q336 of the 528 entry (data-join "192:9 336:9", data-order 10),
    # changed: to data-order 11, an order its power sums do not have, and the join clicked (the joinorder run); and to
    # data-join "192:9 336:8", an id no code of the page has, as loaded (the missing run).
    # Expectata (fail loudly, never fix silently): the click on the join said to have order 11 throws an error that
    # names it (its data-join) and shows no partition, the join staying collapsed; the join of a code the page lacks
    # makes the page throw an error that names it as it loads.
    # Resultata before (2026-10-31, while the section "Claude's examples as sets" held the join's partition): the page
    # had no join, so neither page could be made.
    R = run('joinorder')                      # steps: load, look, click (step 2), read
    assert R['errors'] and all(k == 2 for k, _ in R['errors']) and any('192:9 336:9' in line for _, line in R['errors']), R['errors']
    read = R['steps'][3]
    assert read['id'] == '192:9 336:9' and read['expanded'] == 'false' and not (read['box'] and read['box']['shown']), read
    R = run('missing')                        # steps: load (step 0), look
    assert R['errors'] and all(k == 0 for k, _ in R['errors']) and any('192:9 336:8' in line for _, line in R['errors']), R['errors']


def q_join_expands_to_the_former_528_set():
    # Replicata: the light run: the join of the 528 entry, f = p192 ∨ q336 (data-join "192:9 336:9", data-order 10),
    # clicked and read; and SETS' SClaude[10][528], the set the section "Claude's examples as sets" gave until
    # 2026-10-31 for that partition.
    # Expectata (dreeves, 2026-10-31: "kill the redundancy of the "Claude's examples as sets" section, being careful not
    # to lose anything ... every bipartition we give should be presented the same way as an expandable hex code"): the
    # join is a button whose partition's first part, the positions with +1, is SClaude[10][528] number for number (0 in
    # it), its second part the rest of 0, ..., 527, with sums equal for k < 10 and unequal at k = 10; and mstar.py's
    # reading of the join is the same sequence.
    # Resultata before: no join; SClaude[10][528] was the page's only source of that partition (its signs are neither
    # symmetric nor antisymmetric, so no code in the paper's form can hold them).
    [S] = [ps for name, m, n, ps in former_sets() if (name, m, n) == ('SClaude', 10, 528)]
    R = run('light')
    s = shown(R).get('192:9 336:9')
    assert s and s['box'] and s['box']['shown'], s
    parts = [numbers(t) for t, *_ in s['box']['parts']]
    assert parts == [S, sorted(set(range(528)) - set(S))], [p[:8] for p in parts]
    assert s['box']['relations'] == ['='] * 10 + ['≠'], s['box']['relations']
    [(key, n, m, a)] = [c for c in items() if c[0] == '192:9 336:9']
    assert (n, m) == (528, 10) and [i for i, t in enumerate(a) if t == 1] == S


def q_former_sets_are_halves_of_expansions():
    # Replicata: the light run: every code and join clicked and read; and SETS, the 31 sets the section "Claude's
    # examples as sets" gave until 2026-10-31 (SClaude[m][n] and SClaudeSym[10][528]).
    # Expectata (dreeves: "being careful not to lose anything"): each set is, number for number, one part of the
    # partition that exactly one code or join of its length n and order m shows, and no two sets are parts of the same
    # one: 30 codes and the join.
    # Resultata before: SClaude[10][528] was a part of no partition shown (the page had no join).
    R = run('light')
    opened, page = shown(R), items()
    hits = [(name, m, n, [key for key, k, o, _ in page if (k, o) == (n, m) and key in opened
                         and ps in [numbers(t) for t, *_ in opened[key]['box']['parts']]])
            for name, m, n, ps in former_sets()]
    assert all(len(keys) == 1 for *_, keys in hits), [h for h in hits if len(h[3]) != 1]
    assert len({keys[0] for *_, keys in hits}) == 31, hits


def q_no_bipartition_outside_expandable_elements():
    # Replicata: the light run, at its end (every code and join clicked twice): every <code> of the page whose text is
    # two or more hex digits and nothing else, every element with data-join, and main's text outside the partitions
    # (class partition).
    # Expectata (dreeves, 2026-10-31: "every bipartition we give should be presented the same way as an expandable hex
    # code"): every such code and every join is a button (role button, aria-expanded false after its two clicks), and
    # main's text outside the partitions has no run of integers separated by commas as long as a part of the shortest
    # code or join (half its length, 24 for 48:6): no part of a bipartition is written out anywhere else.
    # Resultata before: the section "Claude's examples as sets" held 31 such runs, of 160 to 512 integers, and the two
    # codes of the proof of m*(416) = 9 (ids seed416 and witness416) were no buttons.
    R = run('light')
    scan = R['steps'][-1]
    shortest = min(n for _, n, *_ in items()) // 2
    bad = ([('code', c) for c in scan['hex'] if c[2:] != ['button', 'false']]
           + [('join', j) for j in scan['joins'] if j[1:] != ['button', 'false']]
           + [('run', r) for r in scan['runs'] if r >= shortest])
    assert scan['hex'] and bad == [], (len(scan['hex']), shortest, bad)


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
