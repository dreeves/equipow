// Claude's chart of m*(n), drawn from MSTAR, which mstar.js defines (mstar.py makes it and states its contract), for n
// up to the cap, the one pressed of the page's caps (dreeves's README, [BOU], 2026-11-10: "Let's try having Figure 1
// go up to 2048. Actually, let's try this: replace the reset-zoom button with "cap:" and then buttons for 2^6, 2^7,
// 2^8, 2^9, 2^10, 2^11"; n up to 1024 until then, which is the cap pressed as the page loads).  Column n is green (exists) in rows m = 1 to lo, gray (open) up to hi and red (impossible) above, up to row
// MSTAR.mtop.  Since 2026-11-11 (dreeves's README, [SYC]: "a different styling on the chart (like striped or half-and-half
// black vs red, split diagonally) for cells for which we know they're red conditional on the Symmetry Conjecture being
// true") a column that MSTAR.ifsym lists has a lower upper bound if BGPW's Symmetry Conjecture holds, and its cells
// above that bound, up to hi, are of a fourth kind, ifsym: open, with the upper right triangle in the red of an
// impossible cell.  The columns are NS: every n up to the cap but those that a checked box of the page's list leaves out (dreeves's
// README, [COM], 2026-11-10: "checkboxes for what's omitted, in terms of the biggest power of two factor").  As the page
// loads its first two boxes are checked, so NS is n = 2 and the multiples of 4 (dreeves, 2026-10-29: "can we make my
// "odd multiple of 2" bullet point be true?"; every even n before): an odd n has no partition at any m, and every
// other n = 2 mod 4 has m*(n) = 1, as the data contract asserts of every box's n.  Pan and zoom (panZoom, which the chart of powers of 2 shares since
// 2026-10-30) act on n only: the view is the interval [u0, u0 + span) of u,
// column c (from 0), n = NS[c], spanning u from c to c + 1.  The rows follow the view (dreeves, 2026-11-10: "however
// the chart is zoomed, make there always be exactly one fully pink row, ie, zoom in the y direction automatically as a
// function of the x zoom"): rows 1 to one more than the largest upper bound among the columns in view, sharing the
// plot's height, so that the top row, and it alone, is impossible in every column of the view.  Each device pixel of the plot mixes the colors of the
// cells it covers, weighted by how much of it each covers, so all the columns (257 as the page loads) can show at once
// even where they are narrower than a pixel.
(() => {
const cv = document.getElementById('mstar-chart'), ro = document.getElementById('mstar-readout');
const fail = e => { ro.textContent = `Error drawing the chart: ${e}`; throw e; };   // loudly: in the readout, and uncaught
try {
  const D = MSTAR;
  // The caps ([BOU]): a click on one makes its n the chart's last column, CAP, and presses it alone.
  const CAPS = [...document.querySelectorAll('#mstar-caps button')].map(button => ({button, cap: +button.dataset.cap}));
  const pressed = () => CAPS.filter(c => c.button.getAttribute('aria-pressed') === 'true').map(c => c.cap);
  let CAP = pressed()[0];
  // A box of the list leaves out, while checked, the odd multiples of its factor from its start on, each of which
  // has m*(n) = the order it states.
  const OMIT = [...document.querySelectorAll('#mstar-omit input')].map(box =>
    ({box, factor: +box.dataset.factor, from: +box.dataset.from, order: +box.dataset.order}));
  const leftOut = (n, {factor, from}) => n >= from && n % (2 * factor) === factor;
  const stated = (n, [lo, hi], o) => !o.box.checked || !leftOut(n, o) || (lo === o.order && hi === o.order);
  const columns = () => Array.from({length: CAP}, (_, i) => i + 1).filter(n => !OMIT.some(o => o.box.checked && leftOut(n, o)));
  let NS = columns();                                             // it changes when a box or the cap does (the end of this file)
  // Layout in CSS px: the m labels left of the plot, room right of it for the last n label, the plot PLOT tall, which
  // its rows share (16 rows of ROW until 2026-11-10, as a view whose largest upper bound is 15 still has them), the
  // tags of the cell read out ROW tall, and the n axis below.
  const LEFT = 44, RIGHT = 16, TOP = 2, ROW = 14, PLOT = 16 * ROW, AXIS = 30;
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };
  const prime = p => { for (let d = 2; d * d <= p; d++) if (p % d === 0) return false; return p >= 2; };
  const sub = k => String(k).replace(/\d/g, d => '₀₁₂₃₄₅₆₇₈₉'[d]);
  const loOf = n => D.cols[n - 1][0];
  // The reasons of the data contract.  ok(n, lo or hi, ...its arguments) checks one; text(n, lo or hi, ...) gives it in
  // Claude's words, starting "order lo" or "order hi + 1"; and witness(n, lo, ...) or proof(n, hi, ...) what a box
  // shows of it (since 2026-11-04, [CEL]; an explanation in the panel of column n from 2026-11-03), from the templates
  // of the page (page/shared.js): an example's label, a join's or a product's construction, which page/codes.js
  // expands into its derivation, and the proof of an upper bound worked out for n.  An odd n has a column only while
  // its box is unchecked, and every cell of it is impossible: "none" shows no witness, and "odd" that n is odd.
  const LO = {
    none: {ok: (n, lo) => lo === 0 && n % 2 === 1, witness: () => shown()},
    example: {
      ok: (n, lo, label) => typeof label === 'string' && label !== '',
      // readout reason; says order lo is known from an example, naming where the example comes from
      text: (n, lo, label) => `order ${lo} from an example (${label})`,
      witness: (n, lo, label) => example(n, lo, label),
    },
    join: {
      ok: (n, lo, a, b) => [a, b].every(Number.isInteger) && a >= 1 && b >= 1 && a + b === n && lo <= Math.min(loOf(a), loOf(b)),
      // readout reason; says order lo is known from the join of the examples of lengths a and b
      text: (n, lo, a, b) => `order ${lo} from the join p${sub(a)}\u00a0∨\u00a0p${sub(b)}`,
      witness: (n, lo, a, b) => construction(BigInt(n), n, lo, `p_{${a}} \\vee p_{${b}}`),
    },
    product: {
      ok: (n, lo, a, b) => [a, b].every(Number.isInteger) && a >= 2 && b >= 2 && a * b === n && lo <= loOf(a) + loOf(b),
      // readout reason; says order lo is known from the expanded product of the examples of lengths a and b
      text: (n, lo, a, b) => `order ${lo} from the product p${sub(a)}\u00a0#\u00a0p${sub(b)}`,
      witness: (n, lo, a, b) => construction(BigInt(n), n, lo, `p_{${a}} \\mathbin{\\#} p_{${b}}`),
    },
    table2: {
      ok: (n, lo) => n % 8 === 0 && n <= 304,
      // readout reason; says order lo is known from BGPW's Table 2
      text: (n, lo) => `order ${lo} from BGPW's Table 2`,
      witness: (n, lo) => shown([filled('witness-table2', {bound: bound(n, 'ge', lo)})]),
    },
    page: {
      ok: (n, lo, who) => credit(who).length === 1,              // who is a class of the new results' cells, which their legend words
      // readout reason; says order lo is known from this page's new results, naming whose they are
      text: (n, lo, who) => `order ${lo} from the new results above (${credit(who)[0]})`,
      witness: (n, lo, who) => shown([filled('witness-page', {bound: bound(n, 'ge', lo), who: credit(who)[0]})], [BigInt(n)]),
    },
  };
  const HI = {
    odd: {
      ok: (n, hi) => hi === 0 && n % 2 === 1,
      // readout reason; says order 1 is ruled out because n is odd
      text: (n, hi) => `order ${hi + 1} ruled out: ${n} is odd`,
      proof: (n, hi) => PROOF.odd(BigInt(n), `${n}`, hi),
    },
    two: {
      ok: (n, hi) => n % 2 === 0 && hi === (n & -n) - 1,
      // readout reason; says order hi + 1 is ruled out because hi + 1 is the largest power of 2 dividing n
      text: (n, hi) => `order ${hi + 1} ruled out: ${hi + 1} is the power of 2 in ${n}`,
      proof: (n, hi) => PROOF.two(BigInt(n), `${n}`, hi),
    },
    norm: {
      ok: (n, hi, p) => Number.isInteger(p) && prime(p) && n % p !== 0,
      // readout reason; says order hi + 1 is ruled out by the norm bound for the prime p
      text: (n, hi, p) => `order ${hi + 1} ruled out by the norm bound for p\u00a0=\u00a0${p}`,
      proof: (n, hi, p) => PROOF.norm(BigInt(n), `${n}`, hi, p),
    },
    residue: {
      ok: (n, hi, M) => Number.isInteger(M) && M >= 2,
      // readout reason; says order hi + 1 is ruled out by the residue condition mod M
      text: (n, hi, M) => `order ${hi + 1} ruled out by the residue condition mod ${M}`,
      proof: (n, hi, M) => PROOF.residue(BigInt(n), `${n}`, hi, 'pagegen/mstar.py', M),
    },
    proof: {
      ok: (n, hi, file) => /^proofs\/[\w.]+\.py$/.test(file),
      // readout reason; says order hi + 1 is ruled out by the proof that the named program of proofs/ checks
      text: (n, hi, file) => `order ${hi + 1} ruled out by ${file}`,
      proof: (n, hi, file) => PROOF.file(BigInt(n), `${n}`, hi, file),
    },
    prop44: {
      // (2026-11-11) hi + 1 is the power of 2 in n less 1, and n is below 2^(hi + 1): BGPW's Proposition 4.4 applies
      ok: (n, hi) => n % 2 === 0 && hi === (n & -n) - 2 && n < 2 ** (hi + 1),
      // TODO: readout reason by Fable 5.2 (2026-11-11); says order hi + 1 is ruled out by BGPW's Proposition 4.4
      text: (n, hi) => `order ${hi + 1} ruled out by BGPW's Proposition 4.4`,
      proof: (n, hi) => PROOF.prop44(BigInt(n), `${n}`, hi),
    },
    table2: {
      ok: (n, hi) => n % 8 === 0 && n <= 304,
      // readout reason; says order hi + 1 is ruled out by BGPW's Table 2
      text: (n, hi) => `order ${hi + 1} ruled out by BGPW's Table 2`,
      proof: (n, hi) => PROOF.table2(BigInt(n), `${n}`, hi),
    },
    page: {
      ok: (n, hi, who) => credit(who).length === 1,
      // readout reason; says order hi + 1 is ruled out in this page's new results, naming whose they are
      text: (n, hi, who) => `order ${hi + 1} ruled out in the new results above (${credit(who)[0]})`,
      proof: (n, hi, who) => PROOF.page(BigInt(n), `${n}`, hi, who),
    },
  };
  assert(OMIT.length > 0, OMIT.length);                           // the page's list has its boxes
  assert(Number.isInteger(D.nmax) && Number.isInteger(D.mtop) && Array.isArray(D.cols) && D.cols.length === D.nmax, D.nmax, D.mtop);
  // the page's caps: integers from 2 to nmax, the largest nmax itself, and one of them pressed
  assert(CAPS.every(c => Number.isInteger(c.cap) && 2 <= c.cap && c.cap <= D.nmax) && Math.max(...CAPS.map(c => c.cap)) === D.nmax
    && pressed().length === 1, CAPS.map(c => c.cap), pressed());
  D.cols.forEach((c, i) => {
    const n = i + 1, [lo, hi, lw, hw] = c;
    assert(c.length === 4 && Number.isInteger(lo) && Number.isInteger(hi) && 0 <= lo && lo <= hi && hi < D.mtop, n, c);
    for (const [K, w, v] of [[LO, lw, lo], [HI, hw, hi]]) {
      assert(Object.hasOwn(K, w[0]) && K[w[0]].ok.length === w.length + 1 && K[w[0]].ok(n, v, ...w.slice(1)), n, c);
    }
    assert((lw[0] === 'none') === (n % 2 === 1) && (hw[0] === 'odd') === (n % 2 === 1), n, c);
    OMIT.forEach(o => assert(stated(n, c, o), n, c));              // why a checked box may leave n out
  });
  assert(D.mtop === Math.max(...D.cols.map(c => c[1])) + 1, D.mtop);
  // ifsym ([SYC], 2026-11-11): [n, hi, file], rising in n: m*(n) <= hi if BGPW's Symmetry Conjecture holds, hi from the
  // column's lower bound to one below its upper bound, by the proofs that the program file, of proofs/, checks
  assert(Array.isArray(D.ifsym), 'ifsym', D.ifsym);
  D.ifsym.forEach((e, i) => assert(Array.isArray(e) && e.length === 3 && Number.isInteger(e[0]) && 1 <= e[0] && e[0] <= D.nmax
    && (i === 0 || D.ifsym[i - 1][0] < e[0]) && Number.isInteger(e[1]) && D.cols[e[0] - 1][0] <= e[1] && e[1] < D.cols[e[0] - 1][1]
    && /^proofs\/[\w.]+\.py$/.test(e[2]), 'ifsym', e));
  // the least n not ruled out at each order from mtop on, past the chart ([LIN], 2026-11-03; a list since 2026-11-04,
  // [M17]), which cannot fall: order m + 1 at n has order m there
  assert(Array.isArray(D.mtopAt) && D.mtopAt.length > 0 && D.mtopAt.every(n => Number.isInteger(n) && n > D.nmax && n % 2 === 0), D.mtopAt);
  assert(D.mtopAt.slice(1).every((n, i) => D.mtopAt[i] <= n), D.mtopAt);
  // the explicit sequences longer than the chart reaches, for the table of smallest lengths (since 2026-11-04: 1440:16)
  assert(Array.isArray(D.past) && D.past.every(([n, m, label]) => Number.isInteger(n) && n > D.nmax && n % 2 === 0 && Number.isInteger(m) && m > 0 && label), D.past);

  const KIND = ['exists', 'open', 'impossible', 'ifsym'];         // the kinds of cell
  const UNDER = ['exists', 'open', 'impossible', 'open'];         // the token of a cell's color, by kind: an ifsym cell is an open one with a triangle over it
  const IFHI = D.cols.map(c => c[1]);                             // each column's upper bound if the Symmetry Conjecture holds: its own, or ifsym's
  D.ifsym.forEach(([n, hi]) => { IFHI[n - 1] = hi; });
  const kindOf = (n, m) => m <= D.cols[n - 1][0] ? 0 : m <= IFHI[n - 1] ? 1 : m <= D.cols[n - 1][1] ? 3 : 2;
  const style = getComputedStyle(cv), token = name => style.getPropertyValue(name).trim();
  const rgb = name => {
    const h = token(name);
    assert(/^#[0-9a-f]{6}$/i.test(h), name, h);
    return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  };
  const T = D.mtop, cssH = TOP + PLOT + AXIS;
  // The cells of the table of smallest lengths below, ringed in gold (dreeves's README, 2026-10-30: "[GLT] ... match the
  // "smallest length known" table: green+gold is the smallest *known* n (resp. 2^k) for a give m (resp. delta) and
  // black+gold is the smallest n (resp. 2^k) not ruled out"; a(m − 1) of OEIS A323395 alone from 2026-10-19, dreeves:
  // "green with gold trim"): each cell (n, m) whose column raises row m (raised): the least n known to reach m, role 1,
  // the least n whose upper bound allows m, role 2, or both, role 3: the least n of order m, proven, a(m − 1), which
  // also gets a gold dot (Claude's proposal for the indicator, 2026-10-30).
  const RINGS = raised(D.cols, () => 0).flatMap(([known, possible], i) => [...new Set([...known, ...possible])]
    .sort((x, y) => x - y).map(m => ({n: i + 1, m, role: known.includes(m) + 2 * possible.includes(m)})));
  const ringed = () => assert(RINGS.every(({n, m}) => (n > CAP || NS.includes(n)) && m <= T), RINGS);   // no box leaves a ringed n out
  ringed();
  // The steps of the n labels: 1, 5, 10, 25, 50, 125, 250 and 500 times the least n all of whose multiples up to the cap
  // are columns (4 for n = 2 and the multiples of 4), those of them that label a column (4, 20, 40, 100, 200, 500 and
  // 1000 there, up to 1024), each with the columns it labels, its multiples, and the least distance between two of
  // them next to each other, in columns (none for a step with one label, which so has room wherever it is: under the
  // cap 64 with the multiples of 8 for columns, a phone has room for no two labels of the step 8, and the step 40 has
  // the one).  Until 2026-11-10 the steps were 1 to 125 times the spacing of the last two columns: with every n a
  // column none of them left room for its labels on a phone, and where few multiples of a step were columns the labels
  // were few (400 and 800 alone, 1280 px wide, with the odd n shown and the other three boxes checked).
  const ladder = () => {
    const shown = new Set(NS);
    const base = NS.find(b => Array.from({length: Math.floor(CAP / b)}, (_, i) => (i + 1) * b).every(n => shown.has(n)));
    assert(base, NS.length);
    return [1, 5, 10, 25, 50, 125, 250, 500].map(x => {
      const at = NS.flatMap((n, c) => n % (x * base) === 0 ? [c] : []);
      return {step: x * base, at, gap: Math.min(...at.slice(1).map((c, i) => c - at[i]))};
    }).filter(r => r.at.length > 0);
  };
  let LADDER = ladder();
  cv.style.height = `${cssH}px`;
  const ctx = cv.getContext('2d'), strip = document.createElement('canvas'), sctx = strip.getContext('2d');
  let geo = null;                                                  // the last draw's layout
  // The boxes under the chart (chartPanel, in page/shared.js; dreeves's README, 2026-11-03, [CEL] and [ROC]): the target
  // [c, m] is the cell of column c, n = NS[c], and row m; [c, null] the column, at its n label; [null, m] the row, at
  // its m label; their fragments nN, mM and nNmM.  A cell's box shows, by its kind, the witness of its column's lower
  // bound (green: "just give the partition (expandable hex code) for the highest green cell in that cell's column"),
  // the proof of its upper bound (red: "show the proof for the lowest red cell"), or both, with the searches of its n
  // and m (black: "maybe just summarize the search efforts so far?"); a column's box, both, and the entry of its n
  // ("both the witness for the highest green cell in the column and the proof for the lowest red cell"); a row's, the
  // row of the order m in the table of smallest lengths, as that table has it (smallestRow), and the term a(m - 1) of
  // OEIS A323395, which is that order's smallest length ("like a row in [the table of smallest lengths], giving the
  // smallest n not ruled out and the smallest known n, mention the A323395 sequence").  A cell's heading leads with its swatch, kind and gold ring
  // alike, and the legend's words for that swatch, the legend's own item cloned; its n and m link to the boxes of its
  // column and its row.
  const panel = document.getElementById('mstar-panel'), legend = [...cv.closest('section').querySelectorAll('.legend li')];
  const witness = n => { const [lo, , lw] = D.cols[n - 1]; return together(LO[lw[0]].witness(n, lo, ...lw.slice(1)), copies(BigInt(n), lo)); };
  const proof = n => { const [, hi, , hw] = D.cols[n - 1]; return HI[hw[0]].proof(n, hi, ...hw.slice(1)); };
  const ifproof = n => PROOF.ifsym(BigInt(n), `${n}`, IFHI[n - 1], D.ifsym.find(e => e[0] === n)[2]);   // of a column that ifsym lists
  const SAYS = {exists: witness, impossible: proof, open: (n, m) => together(witness(n), proof(n), searches(BigInt(n), m)),
                ifsym: (n, m) => together(witness(n), proof(n), ifproof(n), searches(BigInt(n), m)),   // an open cell's, with the bound if the conjecture holds
                column: n => together(witness(n), proof(n), shown([], [BigInt(n)])), row: (n, m) => smallestBox(m)};
  const cell = (n, m) => {
    const [swatch, ...words] = legendItem(legend, KIND[kindOf(n, m)], Math.max(0, ...RINGS.filter(r => r.n === n && r.m === m).map(r => r.role)));
    return [swatch, linked(`#n${n}`, `\\(n = ${n}\\)`), ', ', linked(`#m${m}`, `\\(m = ${m}\\)`), ': ', ...words];
  };
  const HEADINGS = {exists: cell, open: cell, impossible: cell, ifsym: cell, row: (n, m) => [`\\(m = ${m}\\)`], column: n => {
    const [lo, hi] = D.cols[n - 1];
    return [`\\(n = ${n}\\)`, ': ', `\\(${lo === hi ? `m^*(${n}) = ${lo}` : `${lo} \\le m^*(${n}) \\le ${hi}`}\\)`];
  }};
  const open = chartPanel({region: panel, chart: cv, ncol: () => NS.length, nrow: T, pin: ts => view.pin(ts),
    fragment: (c, m) => `${c === null ? '' : `n${NS[c]}`}${m === null ? '' : `m${m}`}`,
    fill: (c, m) => {
      const n = NS[c], kind = c === null ? 'row' : m === null ? 'column' : KIND[kindOf(n, m)];
      return {kind, heading: HEADINGS[kind](n, m), ...SAYS[kind](n, m)};
    }});
  const view = panZoom({el: cv, out: document.getElementById('mstar-zoom-out'), in: document.getElementById('mstar-zoom-in'),
    resets: [], ncol: () => NS.length, plot: () => ({left: geo.L / geo.dpr, width: geo.W / geo.dpr}),
    targetAt, readout, draw, open});

  // the view [u0, u0 + span), the cell read out (picked) and the target of the box open (pinned)
  function draw(u0, span, picked, pinned) {
    const dpr = devicePixelRatio, L = Math.round(LEFT * dpr), R = Math.round(RIGHT * dpr), top = Math.round(TOP * dpr);
    const tall = Math.round(PLOT * dpr), gap = 1;                  // the plot's height; a row's bottom device px is page surface
    const W = Math.round(cv.getBoundingClientRect().width * dpr) - L - R;   // the plot's width in device px
    assert(W > 0, W);
    cv.width = L + W + R;
    cv.height = Math.round(cssH * dpr);
    // The rows of this view, 1 to rows: one more than the largest upper bound among its columns, those it shows any
    // part of.  Row m runs from Y(m) down to Y(m - 1), in device px, Y(0) being the plot's bottom.
    const rows = 1 + Math.max(...NS.slice(Math.floor(u0), Math.ceil(u0 + span)).map(n => D.cols[n - 1][1]));
    const Y = m => top + Math.round((rows - m) * tall / rows);
    const mid = m => (Y(m) + Y(m - 1) - gap) / 2;                  // the middle of row m's colored part
    geo = {dpr, L, W, top, tall, rows};
    // The plot as a strip one device pixel per row, each row then stretched to its height: pixel x covers u from
    // u0 + x k to u0 + (x + 1) k.
    const colors = UNDER.map(t => rgb(`--${t}`)), k = span / W, img = sctx.createImageData(W, rows);
    const mix = new Float64Array(3 * rows);
    for (let x = 0; x < W; x++) {
      const a = u0 + x * k, b = Math.min(a + k, NS.length);
      mix.fill(0);
      for (let c = Math.floor(a); c < b; c++) {                   // u from c to c + 1: column n = NS[c]
        const w = (Math.min(b, c + 1) - Math.max(a, c)) / k;
        for (let m = 1; m <= rows; m++) {
          const col = colors[kindOf(NS[c], m)];
          for (let j = 0; j < 3; j++) mix[3 * (m - 1) + j] += w * col[j];
        }
      }
      for (let m = 1; m <= rows; m++) {
        const i = 4 * ((rows - m) * W + x);
        for (let j = 0; j < 3; j++) img.data[i + j] = Math.round(mix[3 * (m - 1) + j]);
        img.data[i + 3] = 255;
      }
    }
    strip.width = W;
    strip.height = rows;
    sctx.putImageData(img, 0, 0);
    ctx.fillStyle = token('--paper');
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.imageSmoothingEnabled = false;
    for (let m = 1; m <= rows; m++) {
      ctx.drawImage(strip, 0, rows - m, W, 1, L, Y(m), W, Y(m - 1) - Y(m));
      ctx.fillRect(L, Y(m - 1) - gap, W, gap);
    }
    // The ifsym cells ([SYC], 2026-11-11): over each, an open cell in the strip, its upper right triangle in the color
    // of an impossible cell, within the plot: every cell from the column's ifsym bound up to its upper bound, in the
    // view's rows, of the columns shown.
    ctx.save();
    ctx.beginPath();
    ctx.rect(L, top, W, tall);
    ctx.clip();
    ctx.fillStyle = token('--impossible');
    D.ifsym.filter(([n]) => NS.includes(n)).forEach(([n, hi]) => {
      const c = NS.indexOf(n), x0 = L + (c - u0) / k, x1 = L + (c + 1 - u0) / k;
      for (let m = hi + 1; m <= Math.min(D.cols[n - 1][1], rows); m++) {
        ctx.beginPath();
        ctx.moveTo(x0, Y(m));
        ctx.lineTo(x1, Y(m));
        ctx.lineTo(x1, Y(m - 1) - gap);
        ctx.closePath();
        ctx.fill();
      }
    });
    ctx.restore();
    // A hairline grid (dreeves, 2026-10-29: "maybe when zoomed in enough the full grid could become visible", then of
    // the powers-of-2 chart's: "this with hairline grid looks great to me"): with the rows' gaps, a line of page
    // surface one device px wide at each boundary of whole columns, fading in as columns widen from 4 CSS px to 8, so
    // none shows at the full view.
    ctx.globalAlpha = Math.min(Math.max((1 / k / dpr - 4) / 4, 0), 1);
    for (let c = Math.floor(u0) + 1; c < u0 + span; c++) ctx.fillRect(L + Math.floor((c - u0) / k), top, 1, tall);
    ctx.globalAlpha = 1;
    // Axes: every m on the left; below, n under the middle of its column, for the columns of the first step of LADDER
    // that leaves room for each label: 48 CSS px or more between any two of its columns next to each other.
    const serif = token('--serif'), base = top + tall;
    ctx.fillStyle = token('--muted');
    ctx.font = `${12 * dpr}px ${serif}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let m = 1; m <= rows; m++) ctx.fillText(String(m), L - 7 * dpr, mid(m));
    const rung = LADDER.find(r => r.gap / k >= 48 * dpr);
    assert(rung, W, span);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    rung.at.filter(c => u0 <= c + 0.5 && c + 0.5 <= u0 + span).forEach(c => {
      const x = L + (c + 0.5 - u0) / k;
      ctx.fillRect(Math.round(x - dpr / 2), base, dpr, 4 * dpr);
      ctx.fillText(String(NS[c]), x, base + 7 * dpr);
    });
    ctx.fillStyle = token('--ink');
    ctx.font = `italic ${15 * dpr}px ${serif}`;
    ctx.textAlign = 'left';
    ctx.fillText('n', 2 * dpr, base + 6 * dpr);
    ctx.textBaseline = 'middle';
    ctx.fillText('m', 2 * dpr, top + tall / 2);
    // Rings just outside cells, 2 device px wide: each of RINGS in gold, with a gold dot half the cell's smaller side
    // across in each proven the least, then the cell read out in ink, and the target of the box open, its cell, column
    // or row (since 2026-11-04: [c, m], null for every column or every row), each while its row is one of the view's.
    const ring = ([c, m]) => {
      const [c0, c1] = c === null ? [0, NS.length] : [c, c + 1], [m0, m1] = m === null ? [1, rows] : [m, m];
      const x0 = L + (c0 - u0) / k, x1 = L + (c1 - u0) / k;
      ctx.strokeRect(x0 - dpr, Y(m1) - dpr, x1 - x0 + 2 * dpr, Y(m0 - 1) - Y(m1) - gap + 2 * dpr);
    };
    const inRows = ([, m]) => m === null || m <= rows;
    ctx.save();
    ctx.beginPath();
    ctx.rect(L - 2 * dpr, 0, W + 4 * dpr, base);
    ctx.clip();
    ctx.lineWidth = 2 * dpr;
    ctx.strokeStyle = ctx.fillStyle = token('--record');
    const rings = RINGS.filter(r => r.n <= CAP && r.m <= rows);     // those of the columns up to the cap, in the view's rows
    rings.forEach(({n, m}) => ring([NS.indexOf(n), m]));
    rings.filter(r => r.role === 3).forEach(({n, m}) => {
      ctx.beginPath();
      ctx.arc(L + (NS.indexOf(n) + 0.5 - u0) / k, mid(m), Math.min(1 / k, Y(m - 1) - Y(m) - gap) / 4, 0, 2 * Math.PI);
      ctx.fill();
    });
    ctx.strokeStyle = token('--ink');
    picked.filter(inRows).forEach(ring);                           // outline the cell read out, just outside it
    pinned.filter(inRows).forEach(ring);                           // and the target of the box open
    ctx.restore();
    // The box's caret under its target's column's middle, kept within the plot, or under its row's m label (--caret, in
    // CSS px from the box's left edge inside its border)
    const left = cv.getBoundingClientRect().left - panel.getBoundingClientRect().left - panel.clientLeft;
    pinned.forEach(([c]) => panel.style.setProperty('--caret', `${left + (c === null ? LEFT / 2
      : Math.min(Math.max(L + (c + 0.5 - u0) / k, L), L + W) / dpr)}px`));
    // The cell read out on the axes (dreeves's README, 2026-11-02: "[HOV] When hovering/clicking on cells in the charts
    // it'd be nice to highlight the values of m and n (resp., delta and k) on the axes of the chart"): its m and its n,
    // each in paper on a box of ink as tall as the colored part of a row ROW tall and 3 px wider than the number on
    // either side, the m over its row's m label, while its row is one of the view's, and the n on the n labels' line,
    // under its column's middle while that is in view, as a label's must be, over any label there.  The chart of
    // powers of 2 tags its δ and k the same way.
    ctx.font = `${12 * dpr}px ${serif}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const pitch = Math.round(ROW * dpr);
    const tag = (t, x, y) => {                                     // the number t, centered at x, y
      const w = ctx.measureText(t).width + 6 * dpr;
      ctx.fillStyle = token('--ink');
      ctx.fillRect(Math.round(x - w / 2), Math.round(y - (pitch - gap) / 2), Math.round(w), pitch - gap);
      ctx.fillStyle = token('--paper');
      ctx.fillText(t, x, y);
    };
    picked.filter(inRows).forEach(([, m]) => tag(String(m), L - 7 * dpr - ctx.measureText(String(m)).width / 2, mid(m)));
    picked.filter(([c]) => u0 <= c + 0.5 && c + 0.5 <= u0 + span)    // 13 px down: the n labels' middle, 7 + 12 / 2
      .forEach(([c]) => tag(String(NS[c]), L + (c + 0.5 - u0) / k, base + 13 * dpr));
  }

  // What is at CSS x, y (panZoom's targetAt): a cell, [column, m]; the strip of the n labels under the plot, [column,
  // null]; the strip of the m labels left of it, [null, m]; or null: the corner between those strips, the margin right
  // of the plot, the gap above its rows.
  function targetAt(x, y) {
    const X = x * geo.dpr - geo.L, Y = y * geo.dpr - geo.top;
    // the row at Y: as many rows from the top as the view's row boundaries at or above Y, less the plot's top edge
    const m = geo.rows + 1 - Array.from({length: geo.rows + 1}, (_, j) => Math.round(j * geo.tall / geo.rows)).filter(b => b <= Y).length;
    const t = [X < 0 ? null : X < geo.W ? Math.floor(view.uAt(x)) : undefined, Y < 0 ? undefined : m >= 1 ? m : null];
    return t.includes(undefined) || t.every(v => v === null) ? null : t;
  }
  const el = (tag, text) => Object.assign(document.createElement(tag), {textContent: text});
  const nw = (...parts) => { const s = el('span', ''); s.className = 'nw'; s.append(...parts); return s; };   // no wrap
  const swatch = document.createElement('span');
  const NOTES = {                                                  // the readout's note on a ringed cell, by its role
    // Readout note on a green cell ringed in gold; says its n is the least known to reach order m
    1: m => `the smallest n known of order ${m}`,
    // Readout note on a black cell ringed in gold; says its n is the least whose upper bound allows order m
    2: m => `the smallest n not ruled out for order ${m}`,
    // Readout note on a cell ringed in gold; says its n is the least of order m: the term a(m − 1) of OEIS A323395
    3: m => `the smallest n of order ${m}: a(${m - 1}) of OEIS A323395`,
  };
  function readout(c, m) {                                         // read out the cell of column c, n = NS[c], and row m
    const n = NS[c], [lo, hi, lw, hw] = D.cols[n - 1], kind = kindOf(n, m);
    const why = [() => LO[lw[0]].text(n, lo, ...lw.slice(1)), () => HI[hw[0]].text(n, hi, ...hw.slice(1))];
    // TODO: readout reason by Fable 5.2 (2026-11-11, [SYC]), of an ifsym cell; says the order above the column's bound under BGPW's Symmetry Conjecture is ruled out if that conjecture holds, naming the program that checks the proofs
    const ifwhy = () => `order ${IFHI[n - 1] + 1} ruled out if the Symmetry Conjecture holds (${D.ifsym.find(e => e[0] === n)[2]})`;
    const mstar = [el('i', 'm'), el('sup', '*'), `(${n})`];
    const rings = RINGS.filter(r => r.n === n && r.m === m);        // none or one
    swatch.className = `swatch ${KIND[kind]}`;
    swatch.classList.toggle('record', rings.length > 0);
    swatch.classList.toggle('proven', rings.some(r => r.role === 3));
    ro.replaceChildren(swatch, nw(el('i', 'n'), ` = ${n}, `, el('i', 'm'), ` = ${m}`), ' · ',
      nw(...(lo === hi ? [...mstar, ` = ${lo}`] : [`${lo} ≤ `, ...mstar, ` ≤ ${hi}`])), ' · ',
      [[why[0]], why, [why[1]], [...why, ifwhy]][kind].map(f => f()).join(' · '));
    ro.append(...rings.map(r => ` · ${NOTES[r.role](m)}`));
  }
  // The columns changed, with a box of the list ([COM]) or with the cap ([BOU]), at the control clicked: the data must
  // hold what the checked boxes state, as when the page loaded, or the change fails as that does; the box open under
  // the chart, whose target is a column of the columns that were, closes as its close button closes it, the focus
  // staying on the control; then the columns are the new ones, the readout the words it had as the page loaded, and
  // the view every column.  A click on the cap pressed so shows every column again, as the reset button did.
  const hint = [...ro.childNodes];
  const recolumn = control => {
    try {
      D.cols.forEach((c, i) => OMIT.forEach(o => assert(stated(i + 1, c, o), i + 1, c)));
      if (!panel.hidden) { panel.querySelector('[data-panel-close]').click(); control.focus(); }
      NS = columns();
      LADDER = ladder();
      ringed();
      ro.replaceChildren(...hint);
      view.recolumn();
    } catch (e) {
      fail(e);
    }
  };
  OMIT.forEach(({box}) => box.addEventListener('change', () => recolumn(box)));
  CAPS.forEach(({button, cap}) => button.addEventListener('click', () => {
    CAP = cap;
    CAPS.forEach(c => c.button.setAttribute('aria-pressed', String(c.cap === CAP)));
    recolumn(button);
  }));
  view.redraw();
  new ResizeObserver(() => view.redraw()).observe(cv);
  document.fonts.ready.then(() => view.redraw());
} catch (e) {
  fail(e);
}
})();
