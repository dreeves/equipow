// The pan and zoom of both charts (dreeves's README, 2026-10-30: "[ZOO] For anti-magic/consistency, have the same zoom
// controls on both charts"), the m*(n) chart's own until then.  A chart of ncol() columns (a function since 2026-11-10: the m*(n) chart's change
// with the boxes of its list) shows the view [u0, u0 + span)
// of u, column c (from 0) spanning u from c to c + 1, span from MIN_SPAN columns to all ncol.  el takes the pointer,
// wheel, gesture and key events; plot() gives the plot's left edge and width in CSS px from el's left; targetAt(x, y)
// what is at CSS x, y of el: a cell, [column, row]; the strip of column labels under the plot, [column, null] (every
// row of the column); the strip of row labels left of it, [null, row] (every column of the row); or null, elsewhere;
// readout(column, row) reads a cell out; and draw(u0, span, picked, pinned) draws the view, outlining the cell read
// out, picked (none or one), and the target of the box open, pinned (none or one).  The buttons out and in do what the
// - and + keys do, each grayed out at its limit (with fewer than MIN_SPAN columns the one view is both limits), and each
// button of resets shows every column (the chart of powers of 2 has one; the m*(n) chart none since 2026-11-10, when
// its caps took the reset button's place, dreeves's README, [BOU]).  A tap or a click on a cell reads it
// out, and on a cell or a strip's label calls open(target), which opens its box (chartPanel, below; a column's panel
// on a cell's click since 2026-11-03, and since 2026-11-04 a cell's box, a column's or a row's, dreeves's README
// items [CEL] and [ROC]).  It returns redraw(), which draws the view again, uAt(x), the u at CSS x of el, and
// pin(targets), which outlines targets (none or one) until the next pin.
function panZoom({el, out: zoomOut, in: zoomIn, resets, ncol, plot, targetAt, readout, draw, open}) {
  const MIN_SPAN = 12, TAP = 6;
  let u0 = 0, span = ncol(), picked = [], pinned = [];
  function redraw() {
    zoomIn.disabled = span === clampSpan(0);                       // each zoom button grays out at its limit
    zoomOut.disabled = span === ncol();
    draw(u0, span, picked, pinned);
  }
  const at = e => { const r = el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };   // CSS px
  const uAt = x => { const p = plot(); return u0 + (x - p.left) * span / p.width; };
  function pick(x, y) {                                            // read out the cell at CSS x, y and outline it
    const c = targetAt(x, y);
    if (c === null || c.includes(null) || picked.some(p => p[0] === c[0] && p[1] === c[1])) return;
    picked = [c];
    readout(...c);
    redraw();
  }
  const clampSpan = s => Math.min(Math.max(s, MIN_SPAN), ncol());
  function setView(a, s) {
    span = clampSpan(s);
    u0 = Math.min(Math.max(a, 0), ncol() - span);
    redraw();
  }
  function zoomAbout(x, s) {                                       // to span s, the u at CSS x staying put
    const u = uAt(x), t = clampSpan(s);
    setView(u - (u - u0) * t / span, t);
  }
  // Pointers: the first two drag the view, their midpoint holding the u it had when the set of pointers last changed,
  // and their spread scaling the span.  One pointer has spread 0, so the + 1s leave its span alone: it pans.
  const pointers = new Map();                                      // pointerId: CSS x, y now and when it went down
  let grip = null;
  const firstTwo = () => [...pointers.values()].slice(0, 2);
  const mid = ps => (ps[0].x + ps.at(-1).x) / 2;
  const spread = ps => Math.hypot(ps[0].x - ps.at(-1).x, ps[0].y - ps.at(-1).y);
  const regrip = () => { const ps = firstTwo(); grip = ps.length ? {u: uAt(mid(ps)), span, d: spread(ps)} : null; };
  function follow() {
    const ps = firstTwo(), s = clampSpan(grip.span * (grip.d + 1) / (spread(ps) + 1)), p = plot();
    setView(grip.u - (mid(ps) - p.left) * s / p.width, s);
  }
  el.addEventListener('pointerdown', e => {
    el.setPointerCapture(e.pointerId);
    const [x, y] = at(e);
    pointers.set(e.pointerId, {x, y, x0: x, y0: y});
    regrip();
  });
  el.addEventListener('pointermove', e => {
    const p = pointers.get(e.pointerId), [x, y] = at(e);
    if (p) { Object.assign(p, {x, y}); follow(); }
    if (e.buttons === 0) pick(x, y);                               // hover: a mouse or pen with no button down
  });
  const lift = e => { const p = pointers.get(e.pointerId); pointers.delete(e.pointerId); regrip(); return p; };
  el.addEventListener('pointerup', e => {
    const p = lift(e), [x, y] = at(e);
    if (p && Math.hypot(x - p.x0, y - p.y0) < TAP) {               // a tap or a click: read out its cell, open its box
      pick(x, y);
      const t = targetAt(x, y);
      if (t !== null) open(t);
    }
  });
  el.addEventListener('pointercancel', lift);
  // Wheel: with ctrl or cmd (a trackpad pinch sends ctrl) it zooms about the pointer; mostly sideways, it pans; mostly
  // down or up it is left alone, so the page scrolls.
  el.addEventListener('wheel', e => {
    const p = plot(), px = [1, 16, p.width][e.deltaMode];          // CSS px per unit of delta: pixel, line, page
    if (e.ctrlKey || e.metaKey) {
      zoomAbout(at(e)[0], span * 2 ** (e.deltaY * px / 100));
      e.preventDefault();
    } else if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      setView(u0 + e.deltaX * px * span / p.width, span);
      e.preventDefault();
    }
  }, {passive: false});
  // Safari's trackpad pinch comes as gesture events; with a touch pointer down, the pointers already zoom.
  let gestureSpan = span;
  el.addEventListener('gesturestart', e => { e.preventDefault(); gestureSpan = span; });
  el.addEventListener('gesturechange', e => {
    e.preventDefault();
    if (pointers.size === 0) zoomAbout(at(e)[0], gestureSpan / e.scale);
  });
  const middle = () => { const p = plot(); return p.left + p.width / 2; };
  const KEYS = new Map([['ArrowLeft', () => setView(u0 - span / 8, span)], ['ArrowRight', () => setView(u0 + span / 8, span)],
    ['+', () => zoomAbout(middle(), span / 1.5)], ['=', () => zoomAbout(middle(), span / 1.5)],
    ['-', () => zoomAbout(middle(), span * 1.5)]]);
  el.addEventListener('keydown', e => {
    const f = KEYS.get(e.key);
    if (f && !(e.ctrlKey || e.metaKey || e.altKey)) { f(); e.preventDefault(); }
  });
  zoomIn.addEventListener('click', KEYS.get('+'));                 // the zoom buttons do what the + and - keys do
  zoomOut.addEventListener('click', KEYS.get('-'));
  resets.forEach(b => b.addEventListener('click', () => setView(0, ncol())));
  const pin = ts => { pinned = ts; redraw(); };
  // the chart's columns changed (the m*(n) chart's, with a box of its list): no cell is read out and none pinned, and
  // the view is every column
  const recolumn = () => { picked = []; pinned = []; setView(0, ncol()); };
  return {redraw, uAt, pin, recolumn};
}

// The rows each column raises, for both charts' gold rings and the table of smallest lengths (dreeves's README,
// 2026-10-30, [GLT]): scanning the columns i of cols from the left, a row r is raised by column i in its lower bound
// when a < r <= lo, lo being its lower bound less shift(i) and a the most of that over the columns left of it, so that
// i is the least column known to reach r; likewise its upper bound, the least column not ruled out for r.  It returns
// [known rows, possible rows] per column, each ascending.  No row is special: a row no column is known to reach still
// has its least column not ruled out (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the chart?", then
// "classic anti-magic violation").
function raised(cols, shift) {
  const rows = (a, b) => Array.from({length: Math.max(0, b - a)}, (_, j) => a + 1 + j);    // the rows a + 1 to b
  let a = 0, b = 0;                                                // the most lower and upper bound left of column i
  return cols.map(([lo, hi], i) => {
    const l = lo - shift(i), h = hi - shift(i), out = [rows(a, l), rows(b, h)];
    a = Math.max(a, l);
    b = Math.max(b, h);
    return out;
  });
}

// ---------- the boxes under the charts ----------
// The box under each chart (dreeves's spec [REO] in index.html; Claude's design of 2026-11-03 from precedents, which
// dreeves approved: "those sound like good precedents. go ahead"; and since 2026-11-04 his README items [CEL] and [ROC],
// with his "so many pointless words in the implementation so far ... think through what the user will want to see and
// making the correspondence between the clicked cell and the info box visually obvious").  The charts stay as they
// are, an overview; a tap or a click opens, right under its chart, the box of what it hit: a cell's, about that cell
// alone; a column's, at its label under the plot (n, or k), about that column; a row's, at its label left of the plot
// (m, or δ), about that row.  A box's target is [column, row], null for every column (a row's box) or for every row (a
// column's box).  Its frame and the caret on its top edge are in the color of the cell clicked, the chart's own token
// (data-kind; ink for a column's or a row's box), the caret under the target's column, or its row's label, where the
// chart puts it as it draws (--caret); and the chart outlines the target while its box is open (panZoom's pin).  Its
// heading names the target, a cell's after the cell's own swatch, with the legend's words for that swatch, cloned.
// Its parts come from the templates of the page, one per kind, template[data-panel="NAME"], filled with the column's
// own numbers (filled), as LMFDB's knowls fill one text per kind of invariant; its parts of Claude's English, those of
// a template marked data-claude, in one quote, Opus 5.5: “…” (Claude: “…” until 2026-11-09), the box's one attribution, and a box with none of them
// with none (dreeves, 2026-11-04: "we don't need claude attribution for blurbs without words like these").  Every target has a fragment (#n1024, #m12,
// #n1024m12; #k30, #d5, #k30d5), which the box puts in the page's address as it opens, and the page opens that box when
// it loads with that fragment or moves to it, as the Stacks project's tags name their results.  The box is a
// disclosure, not a dialog: a region with a heading and a close button; its heading takes the focus as it opens, and
// its button or Escape closes it, the focus back on the chart.  Without the boxes the page reads as before.  Since
// [REO] step 2 (the main session's design of 2026-11-03, after dreeves's "how can we reduce the redundancy and clutter?
// we want everything to appear in this box"), a column's box also shows its length's entry of the remarks, and so does
// a cell's box whose bound rests on a proof of the page's own, which is in that entry: the entry itself, moved in, not
// a copy, as its codes' ids must stay unique and their buttons keep working (page/codes.js), and moved back to its
// place in the list when the box closes or shows another target.  The list stays in the page, in a fold closed until
// clicked, which find in page opens.

// A number as text, its thousands set off by commas, in a span of class big, which may wrap anywhere: a formula cannot
// wrap, and some of these numbers are 90 digits long.
const bigNum = x => Object.assign(document.createElement('span'), {className: 'big', textContent: x.toLocaleString('en-US')});
const linked = (href, ...children) => { const a = document.createElement('a'); a.setAttribute('href', href); a.append(...children); return a; };

// A box's part of one kind, NAME: a div of data-why NAME holding a copy of template[data-panel="NAME"]'s content, each
// of its [data-slot] elements holding values[its slot]: a string (which may hold the page's math, \( ... \), drawn once
// the box opens), a number, a node, or a list of them; and data-claude where the template has it, a part of Claude's
// English.  It throws on a template that is missing or has a slot that values lacks.
function filled(name, values) {
  const t = document.querySelector(`template[data-panel="${name}"]`);
  const slots = t && [...t.content.querySelectorAll('[data-slot]')].map(s => s.dataset.slot);
  if (!t || !slots.every(s => Object.hasOwn(values, s))) throw new Error(`no template ${name} for ${Object.keys(values)}`);
  const box = document.createElement('div');
  box.dataset.why = name;
  box.toggleAttribute('data-claude', t.hasAttribute('data-claude'));
  box.append(t.content.cloneNode(true));
  box.querySelectorAll('[data-slot]').forEach(s => s.replaceChildren(...[values[s.dataset.slot]].flat()
    .map(x => x instanceof Node ? x.cloneNode(true) : String(x))));
  return box;
}

// The entries of the remarks below the charts ("Where the new results come from"), each an li of the list there that
// holds a p.entry: each p.entry gets the lengths it lists, in decimal digits, as data-lengths, and the id entry-N, N the
// first of them, from its TeX before KaTeX draws it, \(n = 320, 352, ...\): or \(n = 2^{11}\):.  HOMES keeps each
// entry's place in the list, a comment right before its li, where the li goes back when a box that showed it is done
// with it (chartPanel, below).  entries(n) gives the entry that lists the length n (a BigInt), none or one.
const HOMES = new Map([...document.querySelectorAll('section.remarks p.entry')].map(p => {
  const x = /^\\\(n = (.+?)\\\):/.exec(p.textContent), li = p.parentElement;
  if (x === null || li.tagName !== 'LI') throw new Error(`an entry outside the form: ${p.textContent.slice(0, 80)}`);
  const ns = x[1].split(', ').map(s => BigInt(s.replace(/^2\^\{(\d+)\}$/, (_, k) => String(2n ** BigInt(k)))));
  p.dataset.lengths = ns.join(' ');
  p.id = `entry-${ns[0]}`;
  const home = document.createComment(` the place of ${p.id} in the list, where it goes back from a box `);
  li.before(home);
  return [li, home];
}));
const entries = n => [...HOMES.keys()].filter(li => li.querySelector('p.entry').dataset.lengths.split(' ').includes(String(n)));

// What a box shows (2026-11-04): parts, its parts, in order; and entries, the lengths whose entries of the remarks it
// shows, after them.  together(...xs) shows all of xs, in order.  bound(name, rel, v) is the bound m*(name) ≥ v (rel
// ge) or ≤ v (le), in TeX.
const shown = (parts = [], entries = []) => ({parts, entries});
// The words for a credit of the new results, which the data names only by the class of its cells (c, j, ca, a or s:
// mstar.py's who): the page's own, the label of the item of the new results' legend whose key has that class, in a
// list, empty for a class the legend lacks, which the charts refuse.  No script holds such words (2026-11-09: dreeves
// renamed Claude to Opus 5.5 on the page, the scripts' lists of the old names no longer matched it, and "it seems dumb
// that me tweaking the prose in index.html has yielded this much work from you").
const credit = key => [...document.querySelectorAll('.legend .key')].filter(k => k.classList.contains(key))
  .map(k => [...k.parentNode.childNodes].filter(x => x !== k).map(x => x.textContent).join('').trim());
const together = (...xs) => shown(xs.flatMap(x => x.parts), xs.flatMap(x => x.entries));
const bound = (name, rel, v) => `\\(m^*(${name}) \\${rel} ${v}\\)`;

// The witnesses of the lower bounds, as both charts' boxes show them (dreeves's README, [CEL]: "If the cell is green,
// just give the partition (expandable hex code) for the highest green cell in that cell's column"): its bound, and its
// source as the data has it, a label (example), or a construction of the page's form, tex, of the length N (a BigInt),
// named name, which page/codes.js expands into its derivation (construction); and then copies(N, lo), each code of the
// page of the length N and the order lo, copied, as a join of that one code (data-join its id, data-order its order),
// which page/codes.js expands into its partition as it does the code itself (the code keeps its id, which no other
// element of the page may have; a box that shows the code itself, in an entry, drops its copy: chartPanel).
const example = (name, lo, label) => shown([filled('witness-example', {bound: bound(name, 'ge', lo), label})]);
const construction = (N, name, lo, tex) => {
  const part = filled('witness-construction', {bound: bound(name, 'ge', lo), formula: `\\(${tex}\\)`});
  part.querySelector('[data-construction]').dataset.construction = `${N}:${lo}`;
  return shown([part]);
};
const copies = (N, lo) => shown([...document.querySelectorAll(`code[id="${N}:${lo}"]`)].map(c => {
  const join = document.createElement('span');
  Object.assign(join.dataset, {join: c.id, order: String(lo)});
  join.append(Object.assign(document.createElement('code'), {textContent: c.textContent}));
  const part = filled('witness-code', {code: join});
  part.dataset.copy = c.id;
  return part;
}));

// The proofs of the upper bounds, which both charts' boxes show (since 2026-11-04 the math alone, with the length's own
// numbers and the method's name; [CEL]: "If the cell is red, show the proof for the lowest red cell in that cell's
// column"): for the length n (a BigInt), named name in TeX, and the upper bound hi, what shows the proof of the kind each
// is named for, with its arguments, that order hi + 1 is ruled out, after its bound, m*(n) ≤ hi.  The norm bound is
// worked out in exact integers: the class sizes s_r of 0..n-1 mod p and the sum of their squares; and as the norm of
// f(zeta) is an integer at least p^m and at most (p sum s_r^2 / (p-1))^((p-1)/2), that floor, which p^m at m = hi + 1
// passes.  A proof of the page's own (page) is in the length's entry, which the box shows after it; one that a program
// of proofs/ checks, at a length with no entry (file; since 2026-11-10, 1456's), is that program, linked.  A box shows the
// numbers of a claim, which mstar.py and pow2.py assert as they make the data; it does not decide the claim itself.
const repoFile = path => linked(`https://github.com/dreeves/equipow/blob/main/${path}`, path);   // a file of the repository, by its path in it
const PROOF = {
  odd: (n, name, hi) => shown([filled('proof-odd', {bound: bound(name, 'le', hi), n: `\\(${name} \\equiv 1 \\pmod 2\\)`})]),
  two: (n, name, hi) => {
    const two = n & -n, t = two.toString(2).length - 1, u = n / two;
    return shown([filled('proof-two', {bound: bound(name, 'le', hi), n: `\\(n = 2^{${t}} \\cdot ${u}\\)`,
      f: `\\(f(x) \\equiv (x^{${u}} + 1)^{${two}}/(x + 1)\\)`, once: `\\((x + 1)^2 \\nmid x^{${u}} + 1\\)`,
      m: `\\(m \\le 2^{${t}} - 1 = ${hi}\\)`})]);
  },
  norm: (n, name, hi, p) => {
    const P = BigInt(p), m = hi + 1, sizes = Array.from({length: p}, (_, r) => (n - BigInt(r) + P - 1n) / P);
    const squares = sizes.reduce((s, x) => s + x * x, 0n), h = (P - 1n) / 2n;
    return shown([filled('proof-norm', {bound: bound(name, 'le', hi), p: `\\(p = ${p} \\nmid n\\)`,
      sizes: bigNum(sizes.map(s => s.toLocaleString('en-US')).join(', ')), squares: bigNum(squares), m: `\\(m = ${m}\\)`,
      pm: `\\(p^m = ${p}^{${m}} =\\)`, pmv: bigNum(P ** BigInt(m)), cap: bigNum((P * squares) ** h / (P - 1n) ** h)})]);
  },
  residue: (n, name, hi, source, ...moduli) => shown([filled('proof-residue', {bound: bound(name, 'le', hi),
    M: `\\(M = ${moduli.join(', ')}\\)`, m: `\\(m = ${hi + 1}\\)`, source: repoFile(source)})]),
  file: (n, name, hi, path) => shown([filled('proof-file', {bound: bound(name, 'le', hi), file: repoFile(path)})]),
  // BGPW's Proposition 4.4 (2026-11-11), for the length n = 2^t u, u odd, below 2^(2^t - 1): order m = 2^t - 1, which is
  // hi + 1, would make |f(-1)|, the alternating sum's absolute value, at least 2^m, which is more than n, and |f(-1)| is
  // at most n; the box shows n so factored and that chain of inequalities, the math alone
  prop44: (n, name, hi) => {
    const two = n & -n, t = two.toString(2).length - 1, u = n / two, m = hi + 1;
    const pow = (2n ** BigInt(m)).toLocaleString('en-US').replaceAll(',', '{,}');
    return shown([filled('proof-prop44', {bound: bound(name, 'le', hi), n: `\\(n = 2^{${t}} \\cdot ${u}\\)`,
      f: `\\(m = 2^{${t}} - 1 = ${m} \\Rightarrow |f(-1)| \\ge 2^{${m}} = ${pow} > n \\ge |f(-1)|\\)`})]);
  },
  table2: (n, name, hi) => shown([filled('proof-table2', {bound: bound(name, 'le', hi)})]),
  page: (n, name, hi, who) => shown([filled('proof-page', {bound: bound(name, 'le', hi), who: credit(who)[0]})], [n]),
};

// The legend's item for a cell of the kind (exists, open or impossible) and the role of its gold ring (0, none; 1, the
// least length known for its row; 2, the least not ruled out; 3, both, proven), from the chart's legend, its items
// legend, cloned: [its swatch, which is the cell's own, ...its words].
const ROLES = ['', ' record', ' record', ' record proven'];       // a cell's swatch's classes past its kind, by its role
function legendItem(legend, kind, role) {
  const cls = `swatch ${kind}${ROLES[role]}`, li = legend.find(li => li.querySelector('.swatch').className === cls);
  if (li === undefined) throw new Error(`no legend item ${cls}`);
  return [...li.cloneNode(true).childNodes];
}

// The smallest length of each order, as the table of smallest lengths (Claude's table, Stan Wagon's suggestion,
// 2026-10-17; page/smallest-section.js) has it and a row's box of the m*(n) chart shows it (since 2026-11-04, [ROC]),
// from mstar.js: smallest() gives for each order m, from 1, [m, the least n whose upper bound is at least m (order m is
// not ruled out), the least length known to reach m, best]; and smallestRow(row) its row of the table: m, those two,
// and ✓ where they agree, the order's smallest length proven.  The orders run from 1 to the largest some n up to
// MSTAR.nmax is not ruled out for (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the chart?"), and those past
// it, each with its least n not ruled out in MSTAR.mtopAt (one more from 2026-11-03, [LIN]; through order 17 since
// 2026-11-04, [M17]; since 2026-11-10, when the data came to reach 2048 and its orders 18, the one more alone, 19).  best[m] is the least n whose lower bound is at least m, or the product of two lesser orders' best
// lengths where that is less, since f(x) g(x^n), n the length of f, has order at least the sum of theirs (dreeves's
// README, 2026-10-31: "[MIN] In the "smallest length known for each order" table, we currently have no entries for the
// smallest known n for orders 14 and 15"; the table showed — where no n up to MSTAR.nmax was known to reach m).  An
// example longer than the chart counts as well (MSTAR.past).
function smallest() {
  const knownAt = [], possibleAt = [];                             // order m: its least n known, its least n not ruled out
  raised(MSTAR.cols, () => 0).forEach(([known, possible], i) => {
    known.forEach(m => { knownAt[m] = i + 1; });
    possible.forEach(m => { possibleAt[m] = i + 1; });
  });
  // The orders past the largest some n up to MSTAR.nmax allows, each not ruled out first at its n of MSTAR.mtopAt, the
  // least n past the chart that its own tests leave open (dreeves's README, 2026-11-03: "[LIN] Add one more line for
  // m=16 to the "smallest length known for each order" table", then "yes, 1440 instead of ">1024" if that's all we know
  // so far"; and 2026-11-04: "[M17] Let's add m=17 to the "smallest length known" table").
  possibleAt.push(...MSTAR.mtopAt);
  // An example past the chart reaches its order at its own length (mstar.js's past; since 2026-11-04, 1440:16).
  MSTAR.past.forEach(([n, m]) => { knownAt[m] = Math.min(knownAt[m] ?? Infinity, n); });
  const best = [];                                                 // Infinity stands for knownAt's missing n, the least of none
  possibleAt.forEach((_, m) => { best[m] = Math.min(knownAt[m] ?? Infinity, ...best.slice(1, m).map((b, j) => b * best[m - 1 - j])); });
  if (!best.slice(1).every(Number.isFinite)) throw new Error(JSON.stringify(best));   // best[1] is 2 (the data contract's m*(2) = 1)
  return possibleAt.slice(1).map((possible, j) => [j + 1, possible, best[j + 1]]);
}
// in the chart's order, the n not ruled out before the n known, the check mark last (dreeves's README, 2026-10-31:
// "[FLP] I think the smallest-known and smallest-not-ruled-out columns should be swapped, so the numbers in that table
// are in the same order they're in in the chart. And then I think the checkmarks should be the last column")
function smallestRow([m, possible, best]) {
  const row = document.createElement('tr');
  row.append(...[m, possible, best, best === possible ? '✓' : ''].map(text => Object.assign(document.createElement('td'), {textContent: text})));
  return row;
}
// A row's box of the m*(n) chart: its row of the table of smallest lengths, under that table's own head, and the term
// a(m - 1) of OEIS A323395, the smallest length of order m: that length where it is proven, else between the two.
const smallestBox = m => shown(smallest().filter(([r]) => r === m).map(([r, possible, best]) => {
  const part = filled('row-smallest', {row: smallestRow([r, possible, best]),
    term: `\\(${possible === best ? `a(${r - 1}) = ${best}` : `${possible} \\le a(${r - 1}) \\le ${best}`}\\)`});
  part.querySelector('table').prepend(document.querySelector('section.smallest thead').cloneNode(true));
  return part;
}));

// The runs at a box's target, for an open cell's box ([CEL]: "If the cell is black... maybe just summarize the search
// efforts so far?"): the heading of the Search progress section, and under it that section's runs of the order m at
// the length n as it puts them, once progress.js has loaded (page/progress-section.js's want).
const searches = (n, m) => {
  const part = document.createElement('div'), title = document.createElement('p'), runs = document.createElement('div');
  part.dataset.why = 'searches';
  title.append(Object.assign(document.createElement('b'), {textContent: document.getElementById('progress-title').textContent}));
  part.append(title, runs);
  progressView.want(n, m, nodes => runs.replaceChildren(...nodes));
  return shown([part]);
};

// The box of a chart: region, its element (hidden until it opens); chart, the chart's element, which gets the focus
// back; ncol() columns and nrow rows; fragment(column, row), a target's fragment; fill(column, row), what its box shows:
// {kind, heading, parts, entries}; and pin(targets), which has the chart outline the targets, none or one.  The
// entries it shows go below its parts, in its [data-panel-entries], each moved there from wherever it is: its place in
// the list or the other chart's box, which then shows none; a copy of a code goes when the box shows the code itself,
// in an entry; and its quote of Claude opens at its first part of Claude's English and closes at its last.  It returns
// open(target), which opens the box of the target, as panZoom's open does.
function chartPanel({region, chart, ncol, nrow, fragment, fill, pin}) {
  const title = region.querySelector('[data-panel-title]'), body = region.querySelector('[data-panel-body]');
  const shelf = region.querySelector('[data-panel-entries]');
  const back = () => [...shelf.children].forEach(li => HOMES.get(li).after(li));   // its entries, each back in its place
  let last = null;                                                 // the target shown last
  function open(t) {
    const {kind, heading, parts, entries: lengths} = fill(...t);
    back();
    shelf.append(...lengths.flatMap(entries));
    const held = [...shelf.querySelectorAll('code[id]')].map(c => c.id), kept = parts.filter(p => !held.includes(p.dataset.copy));
    const ps = kept.filter(p => p.hasAttribute('data-claude')).flatMap(e => [...e.querySelectorAll('p')]);   // Claude's English, quoted
    ps.slice(0, 1).forEach(p => p.prepend('Opus 5.5: “'));   // Opus 5.5 for Claude since dreeves's rename of 2026-11-09, as in the page's own text
    ps.slice(-1).forEach(p => p.append('”'));
    region.dataset.kind = kind;
    title.replaceChildren(...heading);
    body.replaceChildren(...kept);
    body.querySelectorAll('[data-join]').forEach(e => expandable.partition(e));       // its copies of codes, and its
    body.querySelectorAll('[data-construction]').forEach(e => expandable.derivation(e));   // constructions, buttons
    region.hidden = false;
    last = t;
    history.replaceState(null, '', `#${fragment(...t)}`);
    [title, body].forEach(e => renderMathInElement(e, MATH));      // KaTeX draws its math, with the page's options
    pin([t]);
    title.focus({preventScroll: true});
  }
  function close() {
    back();
    region.hidden = true;
    pin([]);
    if (location.hash === `#${fragment(...last)}`) history.replaceState(null, '', location.pathname + location.search);
    chart.focus();
  }
  region.querySelector('[data-panel-close]').addEventListener('click', close);
  region.addEventListener('keydown', e => {                        // Escape, anywhere in the box, closes it
    if (e.key !== 'Escape') return;
    e.preventDefault();
    close();
  });
  // The fragment of the page's address, as it loads (once KaTeX is there) and as it changes: the box of the target that
  // it names, if any, opens and shows.  The targets: every cell, every column (row null) and every row (column null).
  const all = (k, from) => [null, ...Array.from({length: k}, (_, i) => i + from)];
  const targets = () => all(ncol(), 0).flatMap(c => all(nrow, 1).map(r => [c, r])).filter(t => !t.every(x => x === null));
  const visit = () => targets().filter(t => location.hash === `#${fragment(...t)}`).forEach(t => { open(t); region.scrollIntoView(); });
  addEventListener('hashchange', visit);
  addEventListener('DOMContentLoaded', visit);
  return open;
}

// The contents links use each main section's first heading, before deferred KaTeX renders its math. Nested proof
// headings stay within their section. The labels have one source, and navigation uses the browser's native anchors.
for (const section of document.querySelectorAll('main > section')) {
  const heading = section.querySelector('h2'), item = document.createElement('li'), link = document.createElement('a');
  link.href = `#${heading.id}`;
  link.innerHTML = heading.innerHTML;
  item.append(link);
  document.querySelector('.contents ol').append(item);
}
