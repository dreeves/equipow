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

// The entries of the appendix (Opus 5.5, 2026-11-18; dreeves: "Appendix: Everything Known About Every Length"; until
// then the list of the remarks, "Where the new results come from"), each an li of its list that holds a p.entry, its
// heading.  page/appendix.js, as the page loads, puts them in order, makes the entry of every length that no entry by
// hand lists, puts each length's facts in its entry (FACTS, below), and enters each (enter).  An entry by hand lists its
// lengths in its heading's TeX, read before KaTeX draws it, \(n = 320, 352, ...\): or \(n = 2^{11}\): (listed).  Every
// entry gets its lengths in decimal digits as its p.entry's data-lengths, and the id entry-N, N the first of them.
// HOMES keeps each entry's place in the list, a comment right before its li, where the li goes back when a box that
// showed it is done with it (chartPanel, below); ENTRY, the entry of each length, by its digits.  entries(n) gives the
// entry of the length n (a BigInt), a list of one; it throws for a length that has none, as enter does for a length
// entered twice.
const HOMES = new Map(), ENTRY = new Map();
const listed = p => {
  const x = /^\\\(n = (.+?)\\\):/.exec(p.textContent);
  if (x === null || p.parentElement.tagName !== 'LI') throw new Error(`an entry outside the form: ${p.textContent.slice(0, 80)}`);
  return x[1].split(', ').map(s => BigInt(s.replace(/^2\^\{(\d+)\}$/, (_, k) => String(2n ** BigInt(k)))));
};
const enter = (li, ns) => {
  const p = li.querySelector(':scope > p.entry'), home = document.createComment(` the place of entry-${ns[0]} in the list, where it goes back from a box `);
  p.dataset.lengths = ns.join(' ');
  p.id = `entry-${ns[0]}`;
  li.before(home);
  HOMES.set(li, home);
  ns.forEach(n => { if (ENTRY.has(String(n))) throw new Error(`two entries of ${n}`); ENTRY.set(String(n), li); });
};
const entries = n => { const li = ENTRY.get(String(n)); if (li === undefined) throw new Error(`no entry of ${n}`); return [li]; };

// What a box shows (2026-11-04): parts, its parts, in order; and entries, the lengths whose entries it shows (above its
// parts since 2026-11-18: a column's box shows its length's entry, a cell's where its bound shown is the page's own).
// together(...xs) shows all of xs, in order.  bound(name, rel, v) is the bound m*(name) ≥ v (rel ge) or ≤ v (le), in TeX.
const shown = (parts = [], entries = []) => ({parts, entries});
// The facts of a length (Opus 5.5, 2026-11-18; dreeves: "make everything consistent and complete"), by the chart whose
// data covers the length, each registered by its chart's script, as functions that give what shown gives: its witness
// and its proof, FACTS.mstar.witness(n) and .proof(n) for n up to MSTAR's nmax, with .ifproofs(n), the bound that holds
// if BGPW's Symmetry Conjecture does where the data lists one, and FACTS.pow2.witness(k) and .proof(k) for each 2^k past
// it.  page/appendix.js puts them in the lengths' entries; the charts' boxes of cells show them by the cell's kind.
const FACTS = {};
// Claude's English, quoted (2026-11-04; in runs since 2026-11-16): one quote from the first paragraph of the parts of
// Claude's English (data-claude) to the last, in each run of parts between parts that quote someone else (data-quote:
// Stan Wagon's words), so that no quote of Claude's holds another's; parts with no such part are one run.  Since
// 2026-11-18 (dreeves: "so many formatting and other inconsistencies") the quote opens at the words after the first
// part's bound and closes after the last part's words, each template's data-words, so that every part starts with its
// bound, as the parts with no English do, and the bound, the data's, is outside the quote.
const quoteRuns = parts => {
  const runs = [[]];
  parts.forEach(p => p.hasAttribute('data-quote') ? runs.push([]) : runs.at(-1).push(p));
  for (const ws of runs.map(run => run.filter(p => p.hasAttribute('data-claude')).flatMap(e => [...e.querySelectorAll('[data-words]')]))) {
    ws.slice(0, 1).forEach(w => w.prepend('Opus 5.5: “'));   // Opus 5.5 for Claude since dreeves's rename of 2026-11-09, as in the page's own text
    ws.slice(-1).forEach(w => w.append('”'));
  }
};
// The words for a credit of the new results, which the data names only by the class of its cells (c, cf, j, ca, a or s:
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
// named name, which page/codes.js expands into its derivation (construction); and its codes, in its part's slot codes,
// at the end of its line (since 2026-11-18, dreeves's point 10; until then each a part of its own, witness-code, under
// it): copies(N, lo), each code of the page of the length N and the order lo, copied, as a join of that one code
// (data-join its id, data-order its order), which page/codes.js expands into its partition as it does the code itself
// (the code keeps its id, which no other element of the page may have), or an example's own code, coded (below).  An
// entry or a box that holds a code itself, of the page, drops each copy or code of it from its parts (dropHeld).
const example = (name, lo, label, codes) => shown([filled('witness-example', {bound: bound(name, 'ge', lo), label, codes})]);
const construction = (N, name, lo, tex, codes) => {
  const part = filled('witness-construction', {bound: bound(name, 'ge', lo), formula: `\\(${tex}\\)`, codes});
  part.querySelector('[data-construction]').dataset.construction = `${N}:${lo}`;
  return shown([part]);
};
const copies = (N, lo) => [...document.querySelectorAll(`code[id="${N}:${lo}"]`)].map(c => {
  const join = document.createElement('span');
  Object.assign(join.dataset, {join: c.id, order: String(lo), copy: c.id});
  join.append(Object.assign(document.createElement('code'), {textContent: c.textContent}));
  return join;
});
// The code of an example of the length N (a BigInt) and the order lo, hex, as the data give it (since 2026-11-18, every
// example of the m*(n) chart's: mstar.js's codes; dreeves: "there should be no "found here". what does "here" mean?
// totally ambiguous. show the expandable hex code for everything"), for a witness's slot codes: the code itself, its
// N:lo its data-code, which page/codes.js expands as it does a code of the page; and like a copy, data-copy its N:lo,
// so that a box or an entry that holds the page's code of that id drops it.  An example's witness shows its code so, in
// place of a copy (page/mstar-section.js).
const coded = (N, lo, hex) => {
  const code = Object.assign(document.createElement('code'), {textContent: hex});
  Object.assign(code.dataset, {code: `${N}:${lo}`, copy: `${N}:${lo}`});
  return [code];
};
// The code of the sequence behind a join's or a product's lower bound in the m*(n) chart (Opus 5.5, 2026-11-18;
// dreeves: "witnesses are a top-level thing, conceptually", and, of every witness made (-1)^lo-symmetric so that a code
// in BGPW's convention holds it whole: "making all witnesses conforming sounds great"), which its witness shows, coded,
// as an example's shows its own: a code's signs (decode), a column's (columnSigns), and a symmetric sequence's code
// (codeOf).
//
// decode(hex, m, n): f_0 to f_(n-1), +1 or -1, as overnight_v5.from_hex and mstar.py's from_rp read a code: each hex
// digit's four bits, the most significant first, 1 as +1 and 0 as -1, begin the left half, whose n/2 bits they are,
// the code's other bits 0; the right half is the left half reversed, times (-1)^m.  It throws on an odd n, a number of
// digits other than n/8 rounded up, or a padding bit other than 0.
const decode = (hex, m, n) => {
  const bits = [...hex].flatMap(d => [...parseInt(d, 16).toString(2).padStart(4, '0')].map(Number));
  if (!(n % 2 === 0 && hex.length === Math.ceil(n / 8) && bits.slice(n / 2).every(b => b === 0))) throw new Error(JSON.stringify([hex, n]));
  const left = bits.slice(0, n / 2).map(b => 2 * b - 1);
  return [...left, ...left.toReversed().map(t => (-1) ** m * t)];
};
// The join and the expanded product of two sequences, as the page defines them: f ∨ g = f(x) + x^{n_f} g(x), the signs
// of f and then g's; f # g = f(x) g(x^{n_f}), block j f times g_j.
const COMBINE = {'∨': (f, g) => [...f, ...g], '#': (f, g) => g.flatMap(t => f.map(s => s * t))};
// columnSigns(N): the signs of the sequence behind column N's lower bound, as mstar.py's build makes it: an example's,
// its code's (mstar.js's examples); a join's, its parts' joined; a product's, its parts' multiplied; none's, N ones.
// Each column's once.
const SIGNED = new Map();
const columnSigns = N => {
  const [lo, , why] = MSTAR.cols[N - 1];
  const RULE = {none: () => Array(N).fill(1), example: () => decode(MSTAR.examples.find(([n]) => n === N)[1], lo, N),
                join: (...parts) => parts.map(columnSigns).reduce(COMBINE['∨']), product: (a, b) => COMBINE['#'](columnSigns(a), columnSigns(b))};
  if (!SIGNED.has(N)) SIGNED.set(N, RULE[why[0]](...why.slice(1)));
  return SIGNED.get(N);
};
// codeOf(f, m): the bits of f's left half, 1 for +1, padded with 0 to whole hex digits, n/8 of them rounded up; it
// throws unless f is (-1)^m-symmetric, f_(n-1-i) = (-1)^m f_i, so that the code holds f whole.
const codeOf = (f, m) => {
  const n = f.length;
  if (!(n % 2 === 0 && f.every((t, i) => f[n - 1 - i] === (-1) ** m * t))) throw new Error(JSON.stringify([n, m]));
  const bits = f.slice(0, n / 2).map(t => (t + 1) / 2).join('').padEnd(4 * Math.ceil(n / 8), '0');
  return bits.match(/..../g).map(b => parseInt(b, 2).toString(16).toUpperCase()).join('');
};
// The codes that an entry or a box holds itself, of the page, by its id: each copy or code of the data in parts whose
// N:M (data-copy) is one of them goes, a code being shown once (appendix.js and chartPanel).
const dropHeld = (parts, held) => parts.flatMap(p => [...p.querySelectorAll('[data-copy]')]).filter(c => held.has(c.dataset.copy)).forEach(c => c.remove());

// The proofs of the upper bounds, which both charts' boxes show (since 2026-11-04 the math alone, with the length's own
// numbers and the method's name; [CEL]: "If the cell is red, show the proof for the lowest red cell in that cell's
// column"): for the length n (a BigInt), named name in TeX, and the upper bound hi, what shows the proof of the kind each
// is named for, with its arguments, that order hi + 1 is ruled out, after its bound, m*(n) ≤ hi.  The norm bound is
// worked out in exact integers: the class sizes s_r of 0..n-1 mod p and the sum of their squares; and as the norm of
// f(zeta) is an integer at least p^m and at most (p sum s_r^2 / (p-1))^((p-1)/2), that floor, which p^m at m = hi + 1
// passes.  A proof of the page's own (page) is in the length's entry, which the box shows after it; one that a program
// of proofs/ checks, at a length with no entry (file; since 2026-11-10, 1456's), is that program, linked.  A box shows the
// numbers of a claim, which mstar.py and pow2.py assert as they make the data; it does not decide the claim itself.
const repoURL = path => `https://github.com/dreeves/equipow/blob/main/${path}`;   // where a file of the repository is, by its path in it
const repoFile = path => linked(repoURL(path), path);             // a link to it, worded by its path
// The class sizes s_r of 0..n-1 mod M, r = 0..M-1, for a BigInt n: BigInts.
const classSizes = (n, M) => Array.from({length: M}, (_, r) => (n - BigInt(r) + BigInt(M) - 1n) / BigInt(M));
// A template's content filled, without filled's frame: words that end one part differently by case, for a slot of
// another template, kept in the page's templates as every part's words are (2026-11-16).
const phrase = (name, values) => [...filled(name, values).childNodes];
// A residue box's part, by its chain's moduli, joined.  A chain with no closed form gets the residue template with its
// end check-search: an exhaustive search, by the program that made the claim, linked (searchedPart).  The single
// modulus 3 has a closed form (Fable 5.2, 2026-11-16; dreeves: "yes to mod-3 boxes"), so that its box can be checked by
// hand, as the norm bound's can: (x - 1)^m divides sum D_r x^r mod x^3 - 1 exactly when D_0 + D_1 + D_2 = 0,
// D_0 = D_1 = D_2 mod 3^a and 3^b divides each D_r, for a = floor(m/2) and b = floor((m - 1)/2).  (From (x - 1)^2 =
// (1 + x + x^2) - 3x: mod x^3 - 1 the first term times x - 1 is 0, so each factor (x - 1)^2 past the first is a
// factor -3x; quals_mstar's q_residue_condition_mod_3_has_its_closed_form holds the two to each other.)  At the
// length n and the order m its box gets sizes, the three class sizes in digits, and closed, in parentheses, that
// closed form with its exponents, then each power of 3 once in digits (a = b at an odd m); and since that evening
// (Opus 5.5; dreeves: "are you still referring to "an exhaustive search" and linking to a python program when you
// could instead give a couple lines of mathematica like stan did?", then "ok go") its end check-mathematica, a line of
// Mathematica that tries every triple the closed form allows, in place of the search (closedPart).  Where Stan
// Wagon's argument rules that order out (stanHolds), the box is his words instead (stanPart): the one branch the lines
// and his words added, besides this table's.  Each gives its box's parts, a list.
const RESIDUE_PART = {3: (n, name, hi) => (stanHolds(n, hi + 1) ? stanPart : closedPart)(n, name, hi)};
const residueSlots = (name, hi, moduli) => ({bound: bound(name, 'le', hi), M: `\\(M = ${moduli.join(', ')}\\)`, m: `\\(m = ${hi + 1}\\)`});
const searchedPart = (n, name, hi, source, moduli) => [filled('proof-residue', {...residueSlots(name, hi, moduli), sizes: '', closed: '',
  check: phrase('check-search', {source: repoFile(source)})})];
const closedPart = (n, name, hi) => {
  const m = hi + 1, a = Math.floor(m / 2), b = Math.floor((m - 1) / 2), sizes = classSizes(n, 3);
  return [filled('proof-residue', {...residueSlots(name, hi, [3]),
    sizes: [' = ', bigNum(sizes.map(s => s.toLocaleString('en-US')).join(', '))],
    closed: [` (\\(\\Leftrightarrow D_0 + D_1 + D_2 = 0\\), \\(D_0 \\equiv D_1 \\equiv D_2 \\pmod{3^{${a}}}\\), \\(3^{${b}} \\mid D_r\\); `,
      ...[...new Set([a, b])].flatMap((e, i) => [`${i ? ', ' : ''}\\(3^{${e}} =\\) `, bigNum(3n ** BigInt(e))]), ')'],
    check: phrase('check-mathematica', {line: mod3Line(sizes, a, b)})})];
};
// The line of Mathematica for the class sizes mod 3, sizes (BigInts), and the exponents a and b: the multiples of 3^b
// within each size, every triple of them, and of those the ones of zero sum, each of its size's parity, all congruent
// to the first mod 3^a: the closed form's triples (quals_index's mod3_line, whose quals run it: {} at each box's order,
// and one order lower the sums Python finds).
const mod3Line = (sizes, a, b) => `s = {${sizes.join(', ')}}; Select[Tuples[3^${b} Range[-Quotient[s, 3^${b}], Quotient[s, 3^${b}]]], ` +
  `Total[#] == 0 && Mod[# - s, 2] == {0, 0, 0} && Mod[# - #[[1]], 3^${a}] == {0, 0, 0} &]`;
// Whether Stan Wagon's argument (his note of 2026-11-16, that m*(1024) <= 11) rules out the order m at the length n, a
// BigInt: m even, so that BGPW's Proposition 4.3 (r = 0) makes the three class sums congruent mod 3^(m/2); the classes
// 0 and 2 of sizes of different parities, so of sums of different parities; and those sizes adding to less than
// 3^(m/2), the most the two sums can differ by, so that the congruence makes them equal (quals_index's stan_holds).
const stanHolds = (n, m) => { const [s0, , s2] = classSizes(n, 3); return m % 2 === 0 && (s0 + s2) % 2n === 1n && s0 + s2 < 3n ** BigInt(m / 2); };
// His words, the template proof-stan, with the length's numbers where his hold 1024's (dreeves, of his first version:
// "could you use stan's exact words (mutatis mutandis)", then "ok go"; since 2026-11-18 his shorter version: "For web
// page.  Here it is, shorter now. No need for any Mathematica code."): m*(n) >= m supposed, s = m/2, the congruence of
// the classes 0 and j mod 3^s, the range [0, n - 1], the two classes' sizes, and class 0's, the largest, as the bound
// on every |d_3,i|.  His j is 1 at 1024; here it is n mod 3 (1 there, 2 where n = 2 mod 3, whose classes 0 and 1
// have sizes of one parity), so that his own words come out at 1024 with no branch.  His numbers are digits, as his
// are, with no commas.  His part is marked data-quote, a quotation of someone else's, where the box's quote of Claude
// stops (chartPanel).  Until that day his note of 2026-11-16, and after it a line of Mathematica (proof-pairs,
// stanLine) that checked every pair of sums, which his bound now does in words.
const stanPart = (n, name, hi) => {
  const m = hi + 1, s = m / 2, sizes = classSizes(n, 3), j = Number(n % 3n), digits = x => bigNum(String(x));
  const his = filled('proof-stan', {bound: bound(name, 'le', hi), suppose: `\\(m^*(${name}) \\ge ${m}\\)`, s: `\\(s = ${s}\\)`,
    congruence: `\\(d_{3,0} \\equiv d_{3,${j}}\\)`, mod: digits(3n ** BigInt(s)), j: String(j), last: digits(n - 1n),
    size0: digits(sizes[0]), sizej: digits(sizes[j]), dj: `\\(d_{3,${j}}\\)`});
  his.toggleAttribute('data-quote', true);
  return [his];
};
// The 2-adic bound's part for n = 2^t u, u odd, two = 2^t (a BigInt): mod 2 f(x) is (x^u + 1)^two/(x + 1), and
// (x + 1)^2 does not divide x^u + 1, so (x - 1)^m divides f only for m up to 2^t - 1.  u may be a name, for a class of
// lengths (page/appendix.js, the singly even n: t = 1, u the name u).
const twoPart = (name, t, two, u, hi) => filled('proof-two', {bound: bound(name, 'le', hi), n: `\\(n = 2^{${t}} \\cdot ${u}\\)`,
  f: `\\(f(x) \\equiv (x^{${u}} + 1)^{${two}}/(x + 1)\\)`, once: `\\((x + 1)^2 \\nmid x^{${u}} + 1\\)`, m: `\\(m \\le 2^{${t}} - 1 = ${hi}\\)`});
const PROOF = {
  odd: (n, name, hi) => shown([filled('proof-odd', {bound: bound(name, 'le', hi), n: `\\(${name} \\equiv 1 \\pmod 2\\)`})]),
  two: (n, name, hi) => {
    const two = n & -n;
    return shown([twoPart(name, two.toString(2).length - 1, two, n / two, hi)]);
  },
  norm: (n, name, hi, p) => {
    const P = BigInt(p), m = hi + 1, sizes = classSizes(n, p);
    const squares = sizes.reduce((s, x) => s + x * x, 0n), h = (P - 1n) / 2n;
    return shown([filled('proof-norm', {bound: bound(name, 'le', hi), p: `\\(p = ${p} \\nmid n\\)`,
      sizes: bigNum(sizes.map(s => s.toLocaleString('en-US')).join(', ')), squares: bigNum(squares), m: `\\(m = ${m}\\)`,
      pm: `\\(p^m = ${p}^{${m}} =\\)`, pmv: bigNum(P ** BigInt(m)), cap: bigNum((P * squares) ** h / (P - 1n) ** h)})]);
  },
  residue: (n, name, hi, source, ...moduli) => shown((RESIDUE_PART[moduli.join()] ?? searchedPart)(n, name, hi, source, moduli)),
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
  // The bound that holds if BGPW's Symmetry Conjecture does (2026-11-11; dreeves's README, [SYC]), for a length that
  // mstar.js's ifsym lists: m*(n) <= hi then, by the proofs that the program path checks, to which the bound itself is
  // the link (the program's path as the link's words would take a black cell's box past its budget of words)
  ifsym: (n, name, hi, path) => shown([filled('proof-ifsym', {bound: linked(repoURL(path), bound(name, 'le', hi))})]),
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
// from mstar.js: smallest(cols) gives for each order m, from 1, [m, the least n whose upper bound is at least m (order m
// is not ruled out), the least length known to reach m, best], by the chart's columns cols, [lo, hi] each (MSTAR.cols,
// or since 2026-11-18 ifsymCols, below); and smallestRow(row) its row of the table: m, those two,
// and ✓ where they agree, the order's smallest length proven.  The orders run from 1 to the largest some n up to
// MSTAR.nmax is not ruled out for (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the chart?"), and those past
// it, each with its least n not ruled out in MSTAR.mtopAt (one more from 2026-11-03, [LIN]; through order 17 since
// 2026-11-04, [M17]; since 2026-11-10, when the data came to reach 2048 and its orders 18, the one more alone, 19).  best[m] is the least n whose lower bound is at least m, or the product of two lesser orders' best
// lengths where that is less, since f(x) g(x^n), n the length of f, has order at least the sum of theirs (dreeves's
// README, 2026-10-31: "[MIN] In the "smallest length known for each order" table, we currently have no entries for the
// smallest known n for orders 14 and 15"; the table showed — where no n up to MSTAR.nmax was known to reach m).  An
// example longer than the chart counts as well (MSTAR.past).
function smallest(cols) {
  const knownAt = [], possibleAt = [];                             // order m: its least n known, its least n not ruled out
  raised(cols, () => 0).forEach(([known, possible], i) => {
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
// The m*(n) chart's columns if BGPW's Symmetry Conjecture holds (2026-11-18): each upper bound that mstar.js's ifsym
// lowers, lowered.
const ifsymCols = () => MSTAR.cols.map(([lo, hi], i) => [lo, Math.min(hi, ...MSTAR.ifsym.filter(([n]) => n === i + 1).map(([, h]) => h))]);
// The term a(r - 1) of OEIS A323395, the smallest length of order r, by the least length not ruled out and the least
// known: that length where they agree, else between the two.
const term = (r, possible, best) => `\\(${possible === best ? `a(${r - 1}) = ${best}` : `${possible} \\le a(${r - 1}) \\le ${best}`}\\)`;
// The row of the order m of a table of rows of orders, rows (smallest's, or ifsymCols's), which has exactly one.
const orderRow = (rows, m) => {
  const mine = rows.filter(([r]) => r === m);
  if (mine.length !== 1) throw new Error(`the rows of order ${m}: ${mine.length}`);
  return mine[0];
};
// From which length the Symmetry Conjecture holds at the order m, by the row of the order m of Table 5, the Symmetry
// section's (for each order, the least N known from which it holds at every length): the last of its rows whose
// first order, the first number of its first cell, is at most m; its N, cloned, in dreeves's sentence (row-symmetry),
// whose "proven" links to the proof that the row names (data-proof, an id of the page).  It throws unless the rows'
// first orders rise from 1, or where the row's proof is no element of the page.  (Until later on 2026-11-18 the row
// itself, under Table 5's head; dreeves: "i think the above sentence can be instead of that".)
const symmetryRow = m => {
  const table = document.getElementById('symmetry-table').closest('table'), rows = [...table.tBodies[0].rows];
  const firsts = rows.map(r => Number(/\d+/.exec(r.cells[0].textContent)[0]));
  if (firsts[0] !== 1 || !firsts.every((x, i) => i === 0 || x > firsts[i - 1])) throw new Error(`Table 5's orders: ${firsts}`);
  const row = rows.filter((_, i) => firsts[i] <= m).at(-1);
  if (document.getElementById(row.dataset.proof ?? '') === null) throw new Error(`Table 5's row ${m}: no proof ${row.dataset.proof}`);
  const part = filled('row-symmetry', {from: [...row.cells[1].cloneNode(true).childNodes]});
  part.querySelector('[data-proven]').setAttribute('href', `#${row.dataset.proof}`);
  return part;
};
// A row's box of the m*(n) chart: its row of the table of smallest lengths, under that table's own head, and the term
// a(m - 1) of OEIS A323395; then (Opus 5.5, 2026-11-18; dreeves: "clicking the m for a whole row in a chart should
// gather up all the relevant things for that row, including what we know conditional on the symmetry conjecture being
// true") that term if BGPW's Symmetry Conjecture holds (ifsymCols), and its order's row of Table 5 (symmetryRow).  The
// chart's script adds the row's open cells (page/mstar-section.js).
const smallestBox = m => {
  const [r, possible, best] = orderRow(smallest(MSTAR.cols), m), [, ifPossible] = orderRow(smallest(ifsymCols()), m);
  const part = filled('row-smallest', {row: smallestRow([r, possible, best]), term: term(r, possible, best)});
  part.querySelector('table').prepend(document.querySelector('section.smallest thead').cloneNode(true));
  return shown([part, filled('row-ifsym', {term: term(r, ifPossible, best)}), symmetryRow(m)]);
};

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
// entries it shows go in its [data-panel-entries], above its parts since 2026-11-18 (below them until then), each moved
// there from wherever it is: its place in the appendix's list or the other chart's box, which then shows none; a copy
// of a code goes when the box shows the code itself, in an entry; and its parts' Claude's English is quoted
// (quoteRuns).  It returns open(target), which opens the box of the target, as panZoom's open does.
function chartPanel({region, chart, ncol, nrow, fragment, fill, pin}) {
  const title = region.querySelector('[data-panel-title]'), body = region.querySelector('[data-panel-body]');
  const shelf = region.querySelector('[data-panel-entries]');
  const back = () => [...shelf.children].forEach(li => HOMES.get(li).after(li));   // its entries, each back in its place
  let last = null;                                                 // the target shown last
  function open(t) {
    const {kind, heading, parts, entries: lengths} = fill(...t);
    back();
    shelf.append(...lengths.flatMap(entries));
    const kept = parts;
    dropHeld(kept, new Set([...shelf.querySelectorAll('code[id]')].map(c => c.id)));
    quoteRuns(kept);                                               // the entry's facts were quoted as the page loaded
    region.dataset.kind = kind;
    title.replaceChildren(...heading);
    body.replaceChildren(...kept);
    body.querySelectorAll('[data-join], code[data-code]').forEach(e => expandable.partition(e));   // its copies of codes and codes, and its
    body.querySelectorAll('[data-construction]').forEach(e => expandable.derivation(e));   // constructions, buttons
    region.hidden = false;
    last = t;
    history.replaceState(null, '', `#${fragment(...t)}`);
    [title, shelf, body].forEach(e => renderMathInElement(e, MATH));   // KaTeX draws its math, with the page's options (its entry's too, since 2026-11-18: page/math.js)
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
