// The pan and zoom of both charts (dreeves's README, 2026-10-30: "[ZOO] For anti-magic/consistency, have the same zoom
// controls on both charts"), the m*(n) chart's own until then.  A chart of ncol columns shows the view [u0, u0 + span)
// of u, column c (from 0) spanning u from c to c + 1, span from MIN_SPAN columns to all ncol.  el takes the pointer,
// wheel, gesture and key events; plot() gives the plot's left edge and width in CSS px from el's left; cellAt(x, y)
// the cell at CSS x, y of el as [column, row], or null outside the plot; readout(column, row) reads that cell out; and
// draw(u0, span, picked) draws the view, outlining the cell read out, picked (none or one).  The buttons out and in do
// what the - and + keys do, each grayed out at its limit, and reset shows every column.  A tap or a click on a cell
// also calls open(column, row), which opens the panel of its column (columnPanel, below; since 2026-11-03).  It
// returns redraw(), which draws the view again, and uAt(x), the u at CSS x of el.
function panZoom({el, out: zoomOut, in: zoomIn, reset, ncol, plot, cellAt, readout, draw, open}) {
  const MIN_SPAN = 12, TAP = 6;
  let u0 = 0, span = ncol, picked = [];
  function redraw() {
    zoomIn.disabled = span === MIN_SPAN;                           // each zoom button grays out at its limit
    zoomOut.disabled = span === ncol;
    draw(u0, span, picked);
  }
  const at = e => { const r = el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };   // CSS px
  const uAt = x => { const p = plot(); return u0 + (x - p.left) * span / p.width; };
  function pick(x, y) {                                            // read out the cell at CSS x, y and outline it
    const c = cellAt(x, y);
    if (c === null || picked.some(p => p[0] === c[0] && p[1] === c[1])) return;
    picked = [c];
    readout(...c);
    redraw();
  }
  const clampSpan = s => Math.min(Math.max(s, MIN_SPAN), ncol);
  function setView(a, s) {
    span = clampSpan(s);
    u0 = Math.min(Math.max(a, 0), ncol - span);
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
    if (p && Math.hypot(x - p.x0, y - p.y0) < TAP) {               // a tap or a click: read out and open its cell
      pick(x, y);
      const c = cellAt(x, y);
      if (c !== null) open(...c);
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
  reset.addEventListener('click', () => setView(0, ncol));
  return {redraw, uAt};
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

// ---------- the panels of the charts' columns ----------
// The panel under each chart (dreeves's spec [REO] in index.html; Claude's design of 2026-11-03 from precedents, which
// dreeves approved: "those sound like good precedents. go ahead").  The charts stay as they are, an overview, and a
// tap or a click on a cell opens the details of its column right under its chart: its bounds, the cell's own status
// when a cell was clicked, and one explanation per reason, each from a template of the page for its kind,
// template[data-panel="NAME"], filled with the column's own numbers (filled), as LMFDB's knowls fill one text per kind
// of invariant.  A column has a fragment (#n1024, #k30) that the panel puts in the page's address as it opens, and the
// page opens that column's panel when it loads with it or moves to it, as the Stacks project's tags name their
// results.  The panel is a disclosure, not a dialog: a region with a heading and a close button; its heading takes the
// focus as it opens, and its button or Escape closes it, the focus back on the chart.  Without the panels the page
// reads as before.  Since [REO] step 2 (the main session's design of 2026-11-03, after dreeves's "how can we reduce the
// redundancy and clutter? we want everything to appear in this box"), a panel also shows its length's entry of the
// remarks, below its explanations: the entry itself, moved in, not a copy, as its codes' ids must stay unique and their
// buttons keep working (page/codes.js), and moved back to its place in the list when the panel closes or opens
// another column.  The list stays in the page, in a fold closed until clicked, which find in page opens.

// A number as text, its thousands set off by commas, in a span of class big, which may wrap anywhere: a formula cannot
// wrap, and some of these numbers are 90 digits long.
const bigNum = x => Object.assign(document.createElement('span'), {className: 'big', textContent: x.toLocaleString('en-US')});
const linked = (href, ...children) => { const a = document.createElement('a'); a.setAttribute('href', href); a.append(...children); return a; };

// The panel's text of one kind, NAME: a div of data-why NAME holding a copy of template[data-panel="NAME"]'s content,
// each of its [data-slot] elements holding values[its slot]: a string (which may hold the page's math, \( ... \), drawn
// once the panel opens), a number, a node, or a list of them.  It throws on a template that is missing or has a slot
// that values lacks.
function filled(name, values) {
  const t = document.querySelector(`template[data-panel="${name}"]`);
  const slots = t && [...t.content.querySelectorAll('[data-slot]')].map(s => s.dataset.slot);
  if (!t || !slots.every(s => Object.hasOwn(values, s))) throw new Error(`no template ${name} for ${Object.keys(values)}`);
  const box = document.createElement('div');
  box.dataset.why = name;
  box.append(t.content.cloneNode(true));
  box.querySelectorAll('[data-slot]').forEach(s => s.replaceChildren(...[values[s.dataset.slot]].flat()
    .map(x => x instanceof Node ? x.cloneNode(true) : String(x))));
  return box;
}

// The entries of the remarks below the charts ("Where the new results come from"), each an li of the list there that
// holds a p.entry: each p.entry gets the lengths it lists, in decimal digits, as data-lengths, and the id entry-N, N the
// first of them, from its TeX before KaTeX draws it, \(n = 320, 352, ...\): or \(n = 2^{11}\):.  HOMES keeps each
// entry's place in the list, a comment right before its li, where the li goes back when a panel that showed it is done
// with it (columnPanel, below).  entries(n) gives the entry that lists the length n (a BigInt), none or one.
const HOMES = new Map([...document.querySelectorAll('section.remarks p.entry')].map(p => {
  const x = /^\\\(n = (.+?)\\\):/.exec(p.textContent), li = p.parentElement;
  if (x === null || li.tagName !== 'LI') throw new Error(`an entry outside the form: ${p.textContent.slice(0, 80)}`);
  const ns = x[1].split(', ').map(s => BigInt(s.replace(/^2\^\{(\d+)\}$/, (_, k) => String(2n ** BigInt(k)))));
  p.dataset.lengths = ns.join(' ');
  p.id = `entry-${ns[0]}`;
  const home = document.createComment(` the place of ${p.id} in the list, where it goes back from a panel `);
  li.before(home);
  return [li, home];
}));
const entries = n => [...HOMES.keys()].filter(li => li.querySelector('p.entry').dataset.lengths.split(' ').includes(String(n)));

// The explanations of the upper bounds, which both charts use: for the length n (a BigInt), named name in TeX, and the
// upper bound hi, a reason of the kind each is named for, with its arguments.  The norm bound is worked out in exact
// integers: the class sizes s_r of 0..n-1 mod p, the sum of their squares, and both sides of p^(2m) (p-1)^(p-1) <=
// (p sum s_r^2)^(p-1) at m = hi + 1; and, as the norm of f(zeta) is an integer at least p^m and at most
// (p sum s_r^2 / (p-1))^((p-1)/2), that floor and how far p^m passes it.  The panel shows the numbers of the claim, which
// mstar.py and pow2.py assert as they make the data; it does not decide the claim itself.
const WHY_HI = {
  two: (n, name, hi) => {
    const two = n & -n, t = two.toString(2).length - 1;
    return filled('hi-two', {m: hi + 1, hi, n: `\\(n = ${name} = 2^{${t}} \\cdot ${n / two}\\)`, t: `\\(t = ${t}\\)`,
                             f: `\\((x^{${n / two}} + 1)^{${two}}/(x + 1)\\)`});
  },
  norm: (n, name, hi, p) => {
    const P = BigInt(p), m = hi + 1, sizes = Array.from({length: p}, (_, r) => (n - BigInt(r) + P - 1n) / P);
    const squares = sizes.reduce((s, x) => s + x * x, 0n), base = P * squares, h = (P - 1n) / 2n;
    const lhs = P ** BigInt(2 * m) * (P - 1n) ** (P - 1n), rhs = base ** (P - 1n), ratio = Number(lhs * 10n ** 15n / rhs) / 1e15;
    return filled('hi-norm', {m, p: `\\(p = ${p}\\)`, n: `\\(n = ${name}\\)`, pp: p,
      sizes: bigNum(sizes.map(s => s.toLocaleString('en-US')).join(', ')), squares: bigNum(squares),
      atm: `\\(m = ${m}\\)`, left: `\\(${p}^{${2 * m}} \\cdot ${p - 1}^{${p - 1}}\\)`, lhs: bigNum(lhs), base: bigNum(base),
      power: `\\(p - 1 = ${p - 1}\\)`, rhs: bigNum(rhs), pm: `\\(p^m = ${p}^{${m}} =\\)`, pmv: bigNum(P ** BigInt(m)),
      cap: bigNum(base ** h / (P - 1n) ** h), pct: Number((100 * (Math.sqrt(ratio) - 1)).toPrecision(2)).toLocaleString('en-US')});
  },
  residue: (n, name, hi, source, ...moduli) => filled('hi-residue', {m: hi + 1, mod: moduli.join(', '),
    source: linked(`https://github.com/dreeves/equipow/blob/main/${source}`, source)}),
  table2: (n, name, hi) => filled('hi-table2', {m: hi + 1}),
  page: (n, name, hi, who) => filled('hi-page', {m: hi + 1, who}),
};

// The panel of a chart: region, its element (hidden until it opens); chart, the chart's element, which gets the focus
// back; ncol columns; fragment(c), column c's fragment; length(c), column c's length, a BigInt; and fill(c, rows),
// column c's heading and parts, the rows those of the cells clicked, none or one.  Below the parts, in its
// [data-panel-entries], it shows the entry that lists column c's length, if any, moved there from wherever it is: its
// place in the list or the other chart's panel, which then shows none.  It returns open(c, rows), which opens the
// panel of column c, as panZoom's open does on a tap or a click.
function columnPanel({region, chart, ncol, fragment, length, fill}) {
  const title = region.querySelector('[data-panel-title]'), body = region.querySelector('[data-panel-body]');
  const shelf = region.querySelector('[data-panel-entries]');
  const back = () => [...shelf.children].forEach(li => HOMES.get(li).after(li));   // its entries, each back in its place
  let shown = 0;                                                   // the column shown last
  function open(c, rows) {
    const {heading, parts} = fill(c, rows);
    back();
    title.replaceChildren(...heading);
    body.replaceChildren(...parts);
    shelf.append(...entries(length(c)));
    region.hidden = false;
    shown = c;
    history.replaceState(null, '', `#${fragment(c)}`);
    [title, body].forEach(e => renderMathInElement(e, MATH));      // KaTeX draws its math, with the page's options
    title.focus({preventScroll: true});
  }
  function close() {
    back();
    region.hidden = true;
    if (location.hash === `#${fragment(shown)}`) history.replaceState(null, '', location.pathname + location.search);
    chart.focus();
  }
  region.querySelector('[data-panel-close]').addEventListener('click', close);
  region.addEventListener('keydown', e => {                        // Escape, anywhere in the panel, closes it
    if (e.key !== 'Escape') return;
    e.preventDefault();
    close();
  });
  // The fragment of the page's address, as it loads (once KaTeX is there) and as it changes: the panel of the column
  // that it names, if any, opens and shows.
  const visit = () => Array.from({length: ncol}, (_, c) => c).filter(c => location.hash === `#${fragment(c)}`)
    .forEach(c => { open(c, []); region.scrollIntoView(); });
  addEventListener('hashchange', visit);
  addEventListener('DOMContentLoaded', visit);
  return open;
}
