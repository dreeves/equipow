#!/usr/bin/env python3
"""Quals for the page's codes and joins as buttons (dreeves's spec [REO] in index.html, item 2, 2026-10-31: "When you
click the hex code, we expand it to an explicit partition and check the arithmetic so show exactly which exponents are
equipowerful"; and later that day, when the section "Claude's examples as sets" left the page: "every bipartition we
give should be presented the same way as an expandable hex code"): each code of index.html (<code id="N:M">, N its
length and M its order, in a code block or in a sentence) and each join of its codes (<span data-join="IDS"
data-order="M">, IDS the codes' ids, its signs theirs one after the other, M its order), clicked, or given Enter or
Space while it has focus, shows below it its partition: the positions with +1 and with -1, and the power sums of both
parts for k = 0 to M, computed exactly in the browser, and the next click hides it.  No part of a bipartition is written
out anywhere else on the page, and every set that the section of sets gave is a part of one of them.  Every box, a
code's or a join's partition or a construction's derivation (quals_derivations), opens right after the block that holds
its button, its nearest p or li, never inside running text, the boxes of one block in the order of their buttons
(the coordinator, 2026-10-31), and the button's aria-controls names it.  Since 2026-11-05 (dreeves's README: "[MAI]
Let's get more things as expandable sections of the main equipow page instead of linking to separate pages. Proofs
currently in txt files for starters"), a text is a button too: <span data-text="NAME">, whose click shows its box, the
page's <pre data-text-box="NAME">, which holds the text as the file it replaces had it; and since the same day (dreeves:
a template "defeats part of the point of bringing the proof inline -- i can't grep the page for things in the proof")
the box is in the page from the start, hidden until found, so that find in page reaches a closed text and opens it.
Run: python3 -B quals/quals_codes.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The quals load copies of index.html, each with page/, mstar.js, pow2.js and the page's icons beside it, in headless
Chrome driven through the DevTools protocol by DRIVER, a Node script: a true viewport of each configuration's width and
pixel ratio, real mouse clicks (touch taps for a phone) at the middle of each code or join, and real key presses.  What
one shows is read from the element its aria-controls names (the element right after it until the boxes left running
text, 2026-10-31).  The numbers the page shows are held to mstar.py's own reading of
the page's codes and joins (page_sources) and its decoding of them (overnight_v5.from_hex, mstar.join), with Python's
exact integers; and the sets the page gave until 2026-10-31 to SETS, the file that keeps them.
"""
import sys
sys.dont_write_bytecode = True
import os, re, html, json, time, shutil, tempfile, traceback, subprocess, urllib.parse
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, os.path.join(HERE, 'pagegen'))   # mstar.py's directory since 2026-11-10 ([REF]); the root until then
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
# The page's texts (2026-11-05, dreeves's README, [MAI]): each a button, <span data-text="NAME">, and its box, the
# page's <pre data-text-box="NAME">, which holds its text (a <template id="NAME"> until dreeves's follow-up that day)

TEXT = re.compile(r'\sdata-text="([^"]*)"')
BOX = re.compile(r'<pre\b([^>]*\sdata-text-box="[^"]*"[^>]*)>\n?(.*?)</pre>', re.S)


def texts(text=None):
    """The names of the texts of index.html (or of text) outside its comments, in page order: each data-text, the name
    of its box."""
    return TEXT.findall(qi.blank_comments(qi.page() if text is None else text))


def text_boxes(text=None):
    """[(name, attributes, its text)] for each text's box of index.html (or of text) outside its comments, in page
    order: each <pre> with data-text-box, its name; its start tag's attributes, as a dict; and its text as the browser
    reads it, its character references resolved and the newline right after the <pre> start tag dropped, as the HTML
    standard's parser drops it ("Newlines at the start of pre blocks are ignored as an authoring convenience")."""
    return [(a['data-text-box'], a, html.unescape(body))
            for a, body in ((dict(re.findall(r'([\w-]+)="([^"]*)"', attrs)), body)
                            for attrs, body in BOX.findall(qi.blank_comments(qi.page() if text is None else text)))]


def unique_phrase(name):
    """The first run of four or more words of letters alone in the text of the box name (text_boxes) that the page's
    text a reader sees (quals_index.visible_text) holds exactly once: a phrase that only that text has."""
    [t] = [t for n, _, t in text_boxes() if n == name]
    seen = qi.visible_text()
    return next(p for p in re.findall(r'[A-Za-z]+(?: [A-Za-z]+){3,}', t) if seen.count(p) == 1)


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

DRIVER = r"""
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
""" + qp.GROUP_JS + r"""
// chrome, headless (quals_index's HEADLESS, the flags every headless Chrome of the quals starts with; until 2026-11-10
// this list had its own), dir (the page's copy and the profile), viewport, steps
const C = JSON.parse(readFileSync(0, 'utf8'));
const chrome = spawn(C.chrome, [...C.headless, '--remote-debugging-port=0', `--user-data-dir=${C.dir}/profile`,
  '--hide-scrollbars', 'about:blank'], {stdio: 'ignore', detached: true});
const watchdog = setTimeout(() => { groupSignal(chrome.pid, 'SIGTERM'); process.exit(3); }, 500000);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// In the page.
const FRAMES = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
// Whether KaTeX drew the page's math, waiting up to 20 s for it
const KATEX = () => new Promise(r => { const t0 = performance.now();
  const t = () => document.querySelector('.katex') || performance.now() - t0 > 20000 ? r(!!document.querySelector('.katex')) : setTimeout(t, 50);
  t(); });
// The page's items, in page order: the elements that C.items selects (drive's items: by default CODES_AND_JOINS, each
// code with an id and each element with data-join); and the key that names a code or a join, a code's id or a join's
// data-join.  The functions here run in the page, where DEFINE puts these two as qualsItems and qualsKey once it has
// loaded.
const ITEMS = `() => [...document.querySelectorAll(${JSON.stringify(C.items)})]`;
const KEY = e => e.id || e.dataset.join;
// The focus (the key of the focused element), the scroll, the viewport and the page's width, each code and join as
// [key, role, tabIndex, aria-expanded], and how many partitions (class partition) show
const LOOK = () => ({active: document.activeElement && qualsKey(document.activeElement), scrollX, scrollY, innerWidth, innerHeight,
  scrollW: document.documentElement.scrollWidth,
  codes: qualsItems().map(c => [qualsKey(c), c.getAttribute('role'), c.tabIndex, c.getAttribute('aria-expanded')]),
  partitions: [...document.querySelectorAll('.partition')].filter(e => e.checkVisibility()).length});
// Item i and the element its aria-controls names: if that is a partition (class partition), whether it shows, its box, its
// parts' numbers with their boxes' heights (client, scroll); its power sums' cells, in page order: the k (data-k), the
// marks (data-relation), and each part's sums (data-sum "+1" and "-1") with the widths of the lines each takes (CSS px,
// to 0.1); and how far any cell of its power sums reaches past its right edge (spill, CSS px; at most 0 when none does)
const READ = i => {
  const code = qualsItems()[i], next = document.getElementById(code.getAttribute('aria-controls'));
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
// A real click (a phone's touch tap) at the middle of the element that the selector selects, scrolled to the middle of
// the viewport
const press = async selector => {
  await ev(s => { document.querySelector(s).scrollIntoView({block: 'center'}); return 0; }, selector);
  await ev(FRAMES);
  const [x, y] = await ev(s => { const b = document.querySelector(s).getClientRects()[0]; return [b.left + b.width / 2, b.top + b.height / 2]; }, selector);
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
};
const OPS = {
  // the page loaded, its fonts ready and KaTeX's math drawn: whether it was.  Then, since 2026-11-03 ([REO] step 2,
  // when the remarks' list, where the codes are, went into a fold closed until clicked), a real click on the fold's
  // summary, which must open it: the codes can be clicked only once they show.
  load: async () => {
    const loaded = next('Page.loadEventFired');
    await send('Page.navigate', {url: C.url});
    await loaded;
    await send('Runtime.evaluate', {expression: DEFINE(), returnByValue: true});
    await ev(() => document.fonts.ready.then(() => 0));
    const katex = await ev(KATEX);
    await ev(FRAMES);
    await press('section.remarks details:not(.ai) > summary');
    if (!await ev(() => document.querySelector('section.remarks details:not(.ai)').open)) throw new Error('the fold of the remarks did not open');
    // (2026-11-13, when every model's text came to start folded, dreeves: "all ai-generated text should be default
    // collapsed": the Symmetry section's codes among it) a real click on the line of each such fold that holds a code,
    // which must open it, as a reader opens it to reach the codes
    const folds = await ev(() => [...document.querySelectorAll('details.ai')].filter(d => d.querySelector('code[id]')).map((d, i) => (d.querySelector(':scope > summary').dataset.qualsFold = i, i)));
    for (const i of folds) {
      await press(`summary[data-quals-fold="${i}"]`);
      if (!await ev(i => document.querySelector(`summary[data-quals-fold="${i}"]`).parentElement.open, i)) throw new Error(`the fold of a model's text ${i} did not open`);
    }
    // then a real click on the page's title, which moves the start of the tab order back to the top: the click on the
    // summary had moved it there, past the codes above the fold (2026-11-04: since PR 4, 1440:16 beside Table 3)
    await press('h1');
    return {katex};
  },
  // the page loaded at C.url with C.fragment, its fragment (a text fragment, #:~:text=..., among them), its fonts ready
  // and KaTeX's math drawn, and then ms more for what the fragment does (a text fragment scrolls to its text, revealing
  // what hides it); the fold of the remarks is left as the fragment left it (2026-11-05)
  arrive: async ms => {
    const loaded = next('Page.loadEventFired');
    await send('Page.navigate', {url: C.url + C.fragment});
    await loaded;
    await send('Runtime.evaluate', {expression: DEFINE(), returnByValue: true});
    await ev(() => document.fonts.ready.then(() => 0));
    const katex = await ev(KATEX);
    await sleep(ms);
    await ev(FRAMES);
    return {katex};
  },
  look: () => ev(LOOK),
  read: i => ev(READ, i),
  scan: () => ev(SCAN),
  // the value in the page of the function whose source text is src, called with args (for the quals of other files,
  // quals_derivations, which read what they need with functions of their own)
  js: (src, ...args) => ev(src, ...args),
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
CODES_AND_JOINS = 'code[id], [data-join]'     # the selector of the items of this file's quals: the codes and joins
TEXTS = '[data-text]'                         # the selector of the texts' buttons (since 2026-11-05)
# every button of the page: codes, joins, constructions and (since 2026-11-05) texts
BUTTONS = 'code[id], [data-join], [data-construction], [data-text]'
# In the page, after the placed run's clicks: each button, in page order, as [its tag, its key (a code's id, a join's
# data-join, a construction's data-construction, a text's data-text), the index of its block (its nearest p or li)
# among the buttons' blocks, aria-expanded, aria-controls]; each box (class partition, derivation or, a text's,
# verbatim), as [the index of the button whose aria-controls names it (null for none), whether it is inside a p, whether
# it shows]; and for each block, the indexes of the buttons whose boxes come right after it, one after the other (null
# for a button without a block)
PLACE = """() => {
  const buttons = [...document.querySelectorAll('code[id], [data-join], [data-construction], [data-text]')];
  const blocks = [...new Set(buttons.map(b => b.closest('p, li')))];
  const owner = new Map(buttons.map((b, i) => [document.getElementById(b.getAttribute('aria-controls')), i]));
  owner.delete(null);
  const after = bl => { const out = []; for (let x = bl.nextElementSibling; owner.has(x); x = x.nextElementSibling) out.push(owner.get(x)); return out; };
  return {buttons: buttons.map(b => [b.tagName, b.id || b.dataset.join || b.dataset.construction || b.dataset.text,
            blocks.indexOf(b.closest('p, li')), b.getAttribute('aria-expanded'), b.getAttribute('aria-controls')]),
          boxes: [...document.querySelectorAll('.partition, .derivation, .verbatim')].map(x => [owner.get(x) ?? null, !!x.closest('p'), x.checkVisibility()]),
          after: blocks.map(bl => bl && after(bl))};
}"""
# In the page: item i, a text's button (TEXTS), as {name (its data-text), entry (the id of the p.entry of its li, or
# null), role, tab (tabIndex), expanded (aria-expanded), box}: its box, the element its aria-controls names (null for
# none), as {name (its data-text-box), hidden (its hidden property: false, true or "until-found"), shown (whether it
# shows), after (whether it is the next element after the button's block, its nearest p or li), inP (whether it is
# inside a p), text (its textContent), rect (its left, top, right and bottom, CSS px)}
TEXT_READ = """(i) => {
  const e = qualsItems()[i], box = document.getElementById(e.getAttribute('aria-controls')), block = e.closest('p, li');
  const b = box && box.getBoundingClientRect();
  return {name: e.dataset.text, entry: e.closest('li')?.querySelector('p.entry')?.id ?? null, role: e.getAttribute('role'),
          tab: e.tabIndex, expanded: e.getAttribute('aria-expanded'),
          box: box && {name: box.dataset.textBox ?? null, hidden: box.hidden, shown: box.checkVisibility(),
                       after: block.nextElementSibling === box, inP: box.closest('p') !== null, text: box.textContent,
                       rect: [b.left, b.top, b.right, b.bottom]}};
}"""
# In the page: the viewport's width (innerWidth), the page's (scrollW, its root's scrollWidth), and each text's button
# as [its data-text, aria-expanded, its box's hidden property, whether its box shows, its box's left and right edges
# (CSS px)], the last three null without a box
TEXT_LOOK = """() => ({innerWidth, scrollW: document.documentElement.scrollWidth,
  boxes: qualsItems().map(e => { const x = document.getElementById(e.getAttribute('aria-controls')), b = x && x.getBoundingClientRect();
    return [e.dataset.text, e.getAttribute('aria-expanded'), x && x.hidden, x && x.checkVisibility(), b && [b.left, b.right], x && [x.scrollHeight, x.clientHeight]]; })})"""
# In the page: how many of the texts' buttons have a box (aria-controls names an element); and the heights (CSS px) of
# the entries (li) that hold them, with their boxes in them as they are, and with the boxes taken out of the layout for
# a moment (display none), in that order
ROOM = """() => {
  const lis = [...new Set(qualsItems().map(e => e.closest('li')))];
  const boxes = qualsItems().map(e => document.getElementById(e.getAttribute('aria-controls'))).filter(Boolean);
  const heights = () => lis.map(li => li.getBoundingClientRect().height);
  const asTheyAre = heights();
  boxes.forEach(b => { b.style.display = 'none'; });
  const without = heights();
  boxes.forEach(b => { b.style.display = ''; });
  return {boxes: boxes.length, heights: [asTheyAre, without]};
}"""
# In the page: whether the remarks' fold is open
FOLD = """() => document.querySelector('section.remarks details:not(.ai)').open"""


def drive(viewport, steps, text=None, items=CODES_AND_JOINS, fragment=''):
    """DRIVER's report on a copy of index.html (or of text) in a temporary directory with page/, mstar.js, pow2.js and
    the page's icons beside it, in the viewport given (DESKTOP, PHONE): {'steps': each step's result, 'errors':
    [(the number of steps done, a line logged)]}.  A step is [op, ...args] of DRIVER's OPS; an op's item i is the i-th
    element, in page order, that the selector items selects.  The op arrive loads the page with fragment (since
    2026-11-05)."""
    d = tempfile.mkdtemp(prefix='codes-quals-')
    try:
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(qi.page() if text is None else text)
        qi.copy_page_dir(d)
        for f in qp.ICONS: shutil.copy(os.path.join(HERE, f), d)
        for f in (qi.DATA, qi.POW2): shutil.copy(f, qi.data_file(d, os.path.basename(f)))
        cfg = viewport | dict(chrome=qi.CHROME, headless=qi.HEADLESS, dir=d, url='file://' + os.path.join(d, 'index.html'),
                              steps=steps, items=items, fragment=fragment)
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


# The page with its texts changed, for the quals that the page fails loudly (q_texts_and_boxes_pair_one_to_one), each
# as (what it replaces, its replacement, the name its error must name): orphan adds a box that no button names (orphan);
# nowhere, a button that names no box (nowhere); twice, a second box named proof512; plain, proof512_short's box hidden
# plainly, not until found.
SHORT = '<pre class="verbatim" data-text-box="proof512_short" hidden="until-found">'
MUTANTS = {'orphan': (SHORT, '<pre class="verbatim" data-text-box="orphan" hidden="until-found">orphan</pre>\n      ' + SHORT, 'orphan'),
           'nowhere': ('<span data-text="proof512_short">',
                       '<span data-text="nowhere">nowhere</span> <span data-text="proof512_short">', 'nowhere'),
           'twice': (SHORT, '<pre class="verbatim" data-text-box="proof512" hidden="until-found">twice</pre>\n      ' + SHORT, 'proof512'),
           'plain': (SHORT, '<pre class="verbatim" data-text-box="proof512_short" hidden>', 'proof512_short')}


def changed_text(name):
    """index.html with its texts changed as MUTANTS[name] has it: the one place of what it replaces, replaced."""
    old, new, _ = MUTANTS[name]
    text = qi.page()
    assert text.count(old) == 1, (name, text.count(old))
    return text.replace(old, new)


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
    missing: the page with MISSING for the join, as loaded.
    placed: 1280 px wide; every button of the page (BUTTONS: codes, joins, constructions and texts) clicked once, from
           the last to the first; then PLACE.
    forward: the same, the buttons clicked from the first to the last.
    texts: 1280 px wide; at load ROOM, then each text's button (TEXTS) read (TEXT_READ); then each clicked twice, read
           after each click.
    phonetexts: 390 px wide, a phone's; at load ROOM; then each text's button tapped; then TEXT_LOOK.
    found: 1280 px wide; the page loaded with the text fragment #:~:text=PHRASE (arrive), PHRASE the first phrase that
           only proof512_short's text has (unique_phrase), and 2 s for its search; then FOLD, and each text read.
    orphan, nowhere, twice, plain: the page changed as MUTANTS has it, as loaded; then TEXT_LOOK."""
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
            'placed': lambda: (DESKTOP, [['load']] + [['click', i] for i in reversed(range(buttons()))] + [['js', PLACE]],
                               None, BUTTONS),
            'forward': lambda: (DESKTOP, [['load']] + [['click', i] for i in range(buttons())] + [['js', PLACE]],
                                None, BUTTONS),
            'texts': lambda: (DESKTOP, [['load'], ['js', ROOM]] + [['js', TEXT_READ, i] for i in range(len(texts()))]
                              + [s for i in range(len(texts())) for s in (['click', i], ['js', TEXT_READ, i]) * 2], None, TEXTS),
            'phonetexts': lambda: (PHONE, [['load'], ['js', ROOM]] + [['click', i] for i in range(len(texts()))]
                                   + [['js', TEXT_LOOK]], None, TEXTS),
            'found': lambda: (DESKTOP, [['arrive', 2000], ['js', FOLD]] + [['js', TEXT_READ, i] for i in range(len(texts()))],
                              None, TEXTS, '#:~:text=' + urllib.parse.quote(unique_phrase('proof512_short'), safe='')),
            **{m: (lambda m=m: (DESKTOP, [['load'], ['js', TEXT_LOOK]], changed_text(m), TEXTS)) for m in MUTANTS},
        }[name]()
        RUNS[name] = drive(*steps)
    return RUNS[name]


def buttons():
    """How many buttons index.html has outside its comments: codes with ids, joins, constructions and texts."""
    return len(re.findall(r'<code id="|<span data-join="|<span data-construction="|<span data-text="', qi.blank_comments(qi.page())))


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
    # the second (scratch/reo-expander-20261031/red/wrap_alike_side_by_side.log).  Then (2026-11-03, the codes of order 13 and 15): the partitions of 912:13, 960:15
    # and 1008:13 were 871, 1014 and 871 px tall against the viewport's 844, their power sums growing with the order.
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


def q_boxes_open_after_their_blocks():
    # Replicata: the placed and forward runs: every code, join, construction and (since 2026-11-05) text of the page
    # clicked once, from the last to the first and from the first to the last, so that each opens its box; then each
    # button's block (its nearest p or li), the element its aria-controls names, and the elements right after each block
    # (PLACE).
    # Expectata (the coordinator, 2026-10-31, from the shot of the 2^17 entry with its derivation open: "an expansion
    # opens right after the block element (the nearest p or li ancestor) that holds its button, never inside running
    # text"): every button has a block, is expanded and names a box with aria-controls; every box is a button's, shows,
    # and is inside no p; and right after each block come exactly the boxes of its buttons, in their order, so that each
    # box's previous sibling is its button's block or the box of an earlier button of that block; nothing is logged.
    # Resultata before: a box opened right after its button, inside the button's block: in a sentence, the 2^17 entry's
    # derivation left ", a join of two products ..." below it, as the 416 proof's codes left its quote and period; and no
    # button had aria-controls.
    for name in ('placed', 'forward'):
        R = run(name)
        assert R['errors'] == [], (name, R['errors'][:5])
        scan = R['steps'][-1]
        bad = [b for b in scan['buttons'] if b[3] != 'true' or not b[4]]
        assert scan['buttons'] and bad == [], (name, len(scan['buttons']), bad[:5])
        assert all(owner is not None and not inside and shows for owner, inside, shows in scan['boxes']), (name, scan['boxes'][:5])
        assert sorted(owner for owner, *_ in scan['boxes']) == list(range(len(scan['buttons']))), (name, len(scan['boxes']))
        want = [[i for i, b in enumerate(scan['buttons']) if b[2] == k] for k in range(len(scan['after']))]
        assert scan['after'] == want, (name, [(k, got, w) for k, (got, w) in enumerate(zip(scan['after'], want)) if got != w][:5])


def q_boxes_of_one_block_keep_their_buttons_order():
    # Replicata: the placed and forward runs (every button clicked once, from the last to the first, so that in a block
    # with two buttons the second opened first, and from the first to the last), their blocks with more than one
    # button: the 448 entry's code block (the
    # construction of its label, p448 = p112 # τ2, and the code 448:9), the 528 entry's (the join p192 ∨ q336 and the
    # code 192:9) and the 2^24 entry's (the codes 112:7 and 48:6).
    # Expectata (the coordinator, 2026-10-31: "both boxes go after the block, in button order whatever the click
    # order"): right after each of these blocks, the boxes of its two buttons, the first button's first.
    # Resultata before: each box opened right after its own button, inside the block, so that the first code's
    # partition stood between the two codes of the 2^24 entry.
    for name in ('placed', 'forward'):
        scan = run(name)['steps'][-1]
        keys = [(tag, key) for tag, key, *_ in scan['buttons']]
        blocks = [[keys[i] for i in range(len(keys)) if scan['buttons'][i][2] == k] for k in range(len(scan['after']))]
        several = [(b, [keys[i] for i in after]) for b, after in zip(blocks, scan['after']) if len(b) > 1]
        assert several == [(b, b) for b in ([('SPAN', '448:9'), ('CODE', '448:9')], [('SPAN', '192:9 336:9'), ('CODE', '192:9')],
                                            [('CODE', '112:7'), ('CODE', '48:6')])], (name, several)


def q_texts_show_their_boxes():
    # Replicata: index.html outside its comments: its texts' names (texts: each data-text), its texts' boxes (text_boxes:
    # each <pre> with data-text-box, its text as the HTML parser reads it); and the texts run (1280 px
    # wide): at load (after ROOM) each text's button and its box read (TEXT_READ), then each button clicked twice (a real
    # mouse click at the middle of its first line) and read after each click.
    # Expectata (dreeves's README, 2026-11-05: "[MAI] Let's get more things as expandable sections of the main equipow
    # page instead of linking to separate pages. Proofs currently in txt files for starters"): the 512 entry's two
    # proofs, proof512 and proof512_short, are texts; at load each text is a button
    # (role button, in the tab order, aria-expanded false) whose aria-controls names its box, the <pre> whose
    # data-text-box is its name, right after its block (its nearest p or li), inside no p, and closed; its first click
    # shows the box (aria-expanded true); the box's text is, character for character, the text index.html holds in it,
    # which is not empty; its second click closes it (aria-expanded false); and nothing is logged.  Spec change,
    # 2026-11-05 (dreeves, of the template design: "defeats part of the point of bringing the proof inline -- i can't grep
    # the page for things in the proof"): the box is in the page from the start, made as the page loads, and closed means
    # hidden until found (hidden "until-found"), at load and again after a click closes it, so that find in page reaches
    # it (q_find_in_page_reaches_a_closed_text); until then the box was a copy of a template made at the first click,
    # and a closed box was plainly hidden.
    # Resultata before: no element with data-text; the 512 entry linked its proofs as files, proofs/proof512.txt and
    # proofs/proof512_short.txt.  Then (the template design) no box existed before the first click.
    # Cut, 2026-11-10: this qual also asked that the page link no .txt file, which turned it red on a link made on
    # purpose, to a recorded stream (searches/formtree/fixtures/small.txt).  dreeves: "what's the problem with linking
    # to .txt files? ... are we clear on what the point of quals is? it's to prevent regressions that could happen
    # accidentally. if we link to a .txt then ipso facto we did it on purpose, right?"  A link is made on purpose; what
    # could go wrong by accident here, the two proofs' texts and their boxes, the rest of this qual holds.
    names, R = texts(), run('texts')
    assert R['errors'] == [], R['errors'][:5]
    assert {'proof512', 'proof512_short'} <= set(names), names
    text = {name: t for name, _, t in text_boxes()}
    loads, clicks = R['steps'][2:2 + len(names)], R['steps'][2 + len(names):]
    assert [s['name'] for s in loads] == names and len(clicks) == 4 * len(names), ([s['name'] for s in loads], len(clicks))
    assert [s['entry'] for s in loads if s['name'] in ('proof512', 'proof512_short')] == ['entry-512'] * 2, loads
    look = lambda s: (s['role'], s['tab'], s['expanded'], s['box'] and (s['box']['name'], s['box']['hidden'], s['box']['after'], s['box']['inP']))
    bad = [(s['name'], look(s)) for s in loads if look(s) != ('button', 0, 'false', (s['name'], 'until-found', True, False))]
    assert bad == [], bad
    for j, name in enumerate(names):
        _, opened, _, closed = clicks[4 * j:4 * j + 4]
        box = opened['box']
        assert (opened['expanded'], box['hidden'], box['shown'], box['after'], box['inP']) == ('true', False, True, True, False), \
            (name, opened['expanded'], {k: v for k, v in box.items() if k != 'text'})
        assert text[name] and box['text'] == text[name], (name, len(box['text']), len(text[name]))
        assert (closed['expanded'], closed['box']['hidden']) == ('false', 'until-found'), (name, closed['expanded'], closed['box']['hidden'])


def q_closed_texts_take_no_room():
    # Replicata: the texts run (1280 px wide) and the phonetexts run (390 px, a phone's), each as loaded, the remarks'
    # fold open and every text closed: each entry (li) that holds a text's button, its height with its texts' boxes in it
    # as they are, and with the boxes taken out of the layout for a moment (ROOM).
    # Expectata (the main session, 2026-11-05: a closed until-found element "is still displayed with
    # content-visibility: hidden, so it would add a gap row. Take it out of the flow while closed"): every text has its
    # box from the start, and at both widths each entry is exactly as tall with its closed boxes as without them, as it
    # was with the proofs' links (HEAD's 512 entry).
    # Resultata before: (the template design) no box existed before a click.
    for name in ('texts', 'phonetexts'):
        R = run(name)
        room = R['steps'][1]
        assert room['boxes'] == len(texts()) >= 2, (name, room)
        assert room['heights'][0] == room['heights'][1], (name, room)


def q_texts_and_boxes_pair_one_to_one():
    # Replicata: index.html outside its comments: its texts' names (texts) and its texts' boxes (text_boxes: each <pre>
    # with data-text-box, its name and attributes); and four pages made from it (MUTANTS), each loaded and its texts'
    # buttons looked at (TEXT_LOOK): orphan, with a box that no button names (orphan); nowhere, with a button that names
    # no box (nowhere); twice, with a second box named proof512; and plain, with proof512_short's box hidden plainly, not
    # until found.
    # Expectata (the main session's design, 2026-11-05: "asserting exactly one template per button and no template
    # without a button (fail loudly, rule 12)"): on the page, the texts' names are distinct, they are exactly its boxes'
    # names, one box for each, and each box is hidden until found (hidden="until-found"); each of the four pages throws
    # as it loads, with an error that names its name (orphan, nowhere, proof512, proof512_short), and no text there
    # becomes a button (aria-expanded none).  Spec change, 2026-11-05 (dreeves: the template design "defeats part of the
    # point of bringing the proof inline -- i can't grep the page for things in the proof"): boxes in place of
    # templates, each hidden until found as the page loads (until then: templates with ids, each holding one element).
    # Resultata before: no texts and no boxes; the four pages could not be made.
    names, held = texts(), text_boxes()
    assert names and len(set(names)) == len(names) and sorted(names) == sorted(n for n, _, _ in held), (names, held)
    assert all(a.get('hidden') == 'until-found' for _, a, _ in held), [(n, a) for n, a, _ in held]
    for name, (*_, said) in MUTANTS.items():
        R = run(name)                             # steps: load (step 0), TEXT_LOOK
        assert R['errors'] and all(k == 0 for k, _ in R['errors']) and any(said in line for _, line in R['errors']), (name, R['errors'])
        assert R['steps'][1]['boxes'] and all(b[1] is None for b in R['steps'][1]['boxes']), (name, R['steps'][1]['boxes'])


def q_find_in_page_reaches_a_closed_text():
    # Replicata: the found run: index.html loaded (1280 px wide) with the text fragment #:~:text=PHRASE, PHRASE the first
    # phrase that only proof512_short's text has (unique_phrase), the remarks' fold and every text closed; 2 s later, the
    # fold (FOLD) and each text's button and box read (TEXT_READ).  (Chrome's find bar has no headless form; a text
    # fragment is Chrome's other search of a page's text, and it reveals what it finds as find in page does, by the same
    # ancestor revealing algorithm of the HTML standard: it opens a closed details and removes hidden="until-found",
    # firing beforematch, as q_find_in_page_opens_the_fold of quals_index has it do for the fold.)
    # Expectata (dreeves, 2026-11-05, of the template design: "defeats part of the point of bringing the proof inline --
    # i can't grep the page for things in the proof"): the search reaches the closed text and opens it: the remarks'
    # fold is open; proof512_short's box shows (hidden false) and its button says so (aria-expanded true); proof512's box
    # stays closed (hidden until found, aria-expanded false); and nothing is logged.
    # Resultata before: (the template design) the phrase was in no element of the page, only in a template's inert
    # content; no text had a box (the run could not find its phrase in a box: text_boxes found none).
    R = run('found')
    assert R['errors'] == [], R['errors'][:5]
    fold, reads = R['steps'][1], {s['name']: s for s in R['steps'][2:]}
    assert fold is True, fold
    states = {name: (s['expanded'], s['box'] and (s['box']['name'], s['box']['hidden'])) for name, s in reads.items()}
    assert states['proof512_short'] == ('true', ('proof512_short', False)), states
    assert states['proof512'] == ('false', ('proof512', 'until-found')), states


def q_texts_fit_a_phone():
    # Replicata: index.html as a phone shows it (390 px wide, 844 tall, 3 device px per CSS px, touch; the phonetexts
    # run): each text's button tapped, so that every text shows at once; then the page and the texts' boxes looked at
    # (TEXT_LOOK).
    # Expectata (the main session's design, 2026-11-05: "readable at 1280 px and on a 390 px phone with no page-level
    # sideways scroll (the box may scroll within itself)"): every text's box shows (aria-expanded true, hidden false),
    # within the viewport's width (its left edge at 0 px or more, its right at 390 px or less), and the page is no wider
    # than the viewport; nothing is logged.
    # Resultata before: the page had no texts to tap; the proofs were files that the page linked.
    R = run('phonetexts')
    assert R['errors'] == [], R['errors'][:5]
    look = R['steps'][-1]
    assert sorted(b[0] for b in look['boxes']) == sorted(texts()) and {'proof512', 'proof512_short'} <= set(texts()), look['boxes']
    bad = [b for b in look['boxes'] if not (b[1:4] == ['true', False, True] and 0 <= b[4][0] and b[4][1] <= look['innerWidth'])]
    assert bad == [] and look['innerWidth'] == 390, (bad, look['innerWidth'])
    assert look['scrollW'] <= look['innerWidth'], (look['scrollW'], look['innerWidth'])
    # Spec change (2026-11-06, the coordinator's decision after predicting dreeves's answer: his [MAI] "get more things
    # as expandable sections of the main equipow page", and his 2026-11-05 report of spurious scroll bars as a bug): an
    # open text shows all of itself inline, with no scrolling inside its box, as the typeset proof above it does.
    tall = [b[0] for b in look['boxes'] if b[5][0] > b[5][1] + 1]
    assert tall == [], (tall, [b[5] for b in look['boxes']])


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
