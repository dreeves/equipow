// The pan and zoom of both charts (dreeves's README, 2026-10-30: "[ZOO] For anti-magic/consistency, have the same zoom
// controls on both charts"), the m*(n) chart's own until then.  A chart of ncol columns shows the view [u0, u0 + span)
// of u, column c (from 0) spanning u from c to c + 1, span from MIN_SPAN columns to all ncol.  el takes the pointer,
// wheel, gesture and key events; plot() gives the plot's left edge and width in CSS px from el's left; cellAt(x, y)
// the cell at CSS x, y of el as [column, row], or null outside the plot; readout(column, row) reads that cell out; and
// draw(u0, span, picked) draws the view, outlining the cell read out, picked (none or one).  The buttons out and in do
// what the - and + keys do, each grayed out at its limit, and reset shows every column.  It returns redraw(), which
// draws the view again, and uAt(x), the u at CSS x of el.
function panZoom({el, out: zoomOut, in: zoomIn, reset, ncol, plot, cellAt, readout, draw}) {
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
    if (p && Math.hypot(x - p.x0, y - p.y0) < TAP) pick(x, y);     // a tap or a click
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
