// Claude's chart of m*(n) for n up to 1024, drawn from MSTAR, which mstar.js defines (mstar.py makes it and states its
// contract).  Column n is green (exists) in rows m = 1 to lo, gray (open) up to hi and red (impossible) above, up to row
// MSTAR.mtop.  The columns are NS, n = 2 and the multiples of 4 (dreeves, 2026-10-29: "can we make my "odd multiple of
// 2" bullet point be true?"; every even n before): an odd n has no partition at any m, and every other n = 2 mod 4 has
// m*(n) = 1, as the data contract asserts.  Pan and zoom (panZoom, which the chart of powers of 2 shares since
// 2026-10-30) act on n only: the view is the interval [u0, u0 + span) of u,
// column c (from 0), n = NS[c], spanning u from c to c + 1.  Each device pixel of the plot mixes the colors of the
// cells it covers, weighted by how much of it each covers, so all NCOL = 257 columns can show at once even where they
// are narrower than a pixel.
(() => {
const cv = document.getElementById('mstar-chart'), ro = document.getElementById('mstar-readout');
try {
  const D = MSTAR, NMAX = 1024;
  const NS = [2, ...Array.from({length: NMAX / 4}, (_, i) => 4 * i + 4)], NCOL = NS.length;
  // Layout in CSS px: the m labels left of the plot, room right of it for the last n label, rows ROW tall, and the n
  // axis below.
  const LEFT = 44, RIGHT = 16, TOP = 2, ROW = 14, AXIS = 30;
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };
  const WHO = ['BGPW', 'Claude alone', 'Claude and BGPW', 'Astra alone', 'Claude and Astra'];         // the provenance labels of the new results above
  const prime = p => { for (let d = 2; d * d <= p; d++) if (p % d === 0) return false; return p >= 2; };
  const sub = k => String(k).replace(/\d/g, d => '₀₁₂₃₄₅₆₇₈₉'[d]);
  const loOf = n => D.cols[n - 1][0];
  // The reasons of the data contract.  ok(n, lo or hi, ...its arguments) checks one; text(n, lo or hi, ...) gives it in
  // Claude's words, starting "order lo" or "order hi + 1"; and witness(n, lo, ...) or proof(n, hi, ...) what a box
  // shows of it (since 2026-11-04, [CEL]; an explanation in the panel of column n from 2026-11-03), from the templates
  // of the page (page/shared.js): an example's label, a join's or a product's construction, which page/codes.js
  // expands into its derivation, and the proof of an upper bound worked out for n.  Odd n get no column, so "none" and
  // "odd" have no text and no box.
  const LO = {
    none: {ok: (n, lo) => lo === 0 && n % 2 === 1},
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
      ok: (n, lo, who) => WHO.includes(who),
      // readout reason; says order lo is known from this page's new results, naming whose they are
      text: (n, lo, who) => `order ${lo} from the new results above (${who})`,
      witness: (n, lo, who) => shown([filled('witness-page', {bound: bound(n, 'ge', lo), who})], [], [BigInt(n)]),
    },
  };
  const HI = {
    odd: {ok: (n, hi) => hi === 0 && n % 2 === 1},
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
      proof: (n, hi, M) => PROOF.residue(BigInt(n), `${n}`, hi, 'mstar.py', M),
    },
    table2: {
      ok: (n, hi) => n % 8 === 0 && n <= 304,
      // readout reason; says order hi + 1 is ruled out by BGPW's Table 2
      text: (n, hi) => `order ${hi + 1} ruled out by BGPW's Table 2`,
      proof: (n, hi) => PROOF.table2(BigInt(n), `${n}`, hi),
    },
    page: {
      ok: (n, hi, who) => WHO.includes(who),
      // readout reason; says order hi + 1 is ruled out in this page's new results, naming whose they are
      text: (n, hi, who) => `order ${hi + 1} ruled out in the new results above (${who})`,
      proof: (n, hi, who) => PROOF.page(BigInt(n), `${n}`, hi, who),
    },
  };
  assert(D.nmax === NMAX && Number.isInteger(D.mtop) && Array.isArray(D.cols) && D.cols.length === NMAX, D.nmax, D.mtop);
  D.cols.forEach((c, i) => {
    const n = i + 1, [lo, hi, lw, hw] = c;
    assert(c.length === 4 && Number.isInteger(lo) && Number.isInteger(hi) && 0 <= lo && lo <= hi && hi < D.mtop, n, c);
    for (const [K, w, v] of [[LO, lw, lo], [HI, hw, hi]]) {
      assert(Object.hasOwn(K, w[0]) && K[w[0]].ok.length === w.length + 1 && K[w[0]].ok(n, v, ...w.slice(1)), n, c);
    }
    assert((lw[0] === 'none') === (n % 2 === 1) && (hw[0] === 'odd') === (n % 2 === 1), n, c);
    assert(n % 4 !== 2 || (lo === 1 && hi === 1), n, c);           // why such n, but 2, need no column
  });
  assert(D.mtop === Math.max(...D.cols.map(c => c[1])) + 1, D.mtop);
  assert(Number.isInteger(D.mtopAt) && D.mtopAt > D.nmax && D.mtopAt % 2 === 0, D.mtopAt);   // past the chart ([LIN])

  const KIND = ['exists', 'open', 'impossible'];                  // the colors' tokens, by kind of cell
  const kindOf = (n, m) => m <= D.cols[n - 1][0] ? 0 : m <= D.cols[n - 1][1] ? 1 : 2;
  const style = getComputedStyle(cv), token = name => style.getPropertyValue(name).trim();
  const rgb = name => {
    const h = token(name);
    assert(/^#[0-9a-f]{6}$/i.test(h), name, h);
    return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  };
  const T = D.mtop, cssH = TOP + T * ROW + AXIS;
  // The cells of the table of smallest lengths below, ringed in gold (dreeves's README, 2026-10-30: "[GLT] ... match the
  // "smallest length known" table: green+gold is the smallest *known* n (resp. 2^k) for a give m (resp. delta) and
  // black+gold is the smallest n (resp. 2^k) not ruled out"; a(m − 1) of OEIS A323395 alone from 2026-10-19, dreeves:
  // "green with gold trim"): each cell (n, m) whose column raises row m (raised): the least n known to reach m, role 1,
  // the least n whose upper bound allows m, role 2, or both, role 3: the least n of order m, proven, a(m − 1), which
  // also gets a gold dot (Claude's proposal for the indicator, 2026-10-30).
  const RINGS = raised(D.cols, () => 0).flatMap(([known, possible], i) => [...new Set([...known, ...possible])]
    .sort((x, y) => x - y).map(m => ({n: i + 1, m, role: known.includes(m) + 2 * possible.includes(m)})));
  assert(RINGS.every(({n, m}) => NS.includes(n) && m <= T), RINGS);
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
  const SAYS = {exists: witness, impossible: proof, open: (n, m) => together(witness(n), proof(n), searches(BigInt(n), m)),
                column: n => together(witness(n), proof(n), shown([], [], [BigInt(n)])), row: (n, m) => smallestBox(m)};
  const cell = (n, m) => {
    const [swatch, ...words] = legendItem(legend, KIND[kindOf(n, m)], Math.max(0, ...RINGS.filter(r => r.n === n && r.m === m).map(r => r.role)));
    return [swatch, linked(`#n${n}`, `\\(n = ${n}\\)`), ', ', linked(`#m${m}`, `\\(m = ${m}\\)`), ': ', ...words];
  };
  const HEADINGS = {exists: cell, open: cell, impossible: cell, row: (n, m) => [`\\(m = ${m}\\)`], column: n => {
    const [lo, hi] = D.cols[n - 1];
    return [`\\(n = ${n}\\)`, ': ', `\\(${lo === hi ? `m^*(${n}) = ${lo}` : `${lo} \\le m^*(${n}) \\le ${hi}`}\\)`];
  }};
  const open = chartPanel({region: panel, chart: cv, ncol: NCOL, nrow: T, pin: ts => view.pin(ts),
    fragment: (c, m) => `${c === null ? '' : `n${NS[c]}`}${m === null ? '' : `m${m}`}`,
    fill: (c, m) => {
      const n = NS[c], kind = c === null ? 'row' : m === null ? 'column' : KIND[kindOf(n, m)];
      return {kind, heading: HEADINGS[kind](n, m), ...SAYS[kind](n, m)};
    }});
  const view = panZoom({el: cv, out: document.getElementById('mstar-zoom-out'), in: document.getElementById('mstar-zoom-in'),
    reset: document.getElementById('mstar-reset'), ncol: NCOL, plot: () => ({left: geo.L / geo.dpr, width: geo.W / geo.dpr}),
    targetAt, readout, draw, open});

  // the view [u0, u0 + span), the cell read out (picked) and the target of the box open (pinned)
  function draw(u0, span, picked, pinned) {
    const dpr = devicePixelRatio, L = Math.round(LEFT * dpr), R = Math.round(RIGHT * dpr), top = Math.round(TOP * dpr);
    const pitch = Math.round(ROW * dpr), gap = 1;                  // a row's bottom device px is page surface
    const W = Math.round(cv.getBoundingClientRect().width * dpr) - L - R;   // the plot's width in device px
    assert(W > 0, W);
    cv.width = L + W + R;
    cv.height = Math.round(cssH * dpr);
    geo = {dpr, L, W, top, pitch};
    // The plot as a strip one device pixel per row, then stretched to the rows' height: pixel x covers u from u0 + x k
    // to u0 + (x + 1) k.
    const colors = KIND.map(t => rgb(`--${t}`)), k = span / W, img = sctx.createImageData(W, T);
    const mix = new Float64Array(3 * T);
    for (let x = 0; x < W; x++) {
      const a = u0 + x * k, b = Math.min(a + k, NCOL);
      mix.fill(0);
      for (let c = Math.floor(a); c < b; c++) {                   // u from c to c + 1: column n = NS[c]
        const w = (Math.min(b, c + 1) - Math.max(a, c)) / k;
        for (let m = 1; m <= T; m++) {
          const col = colors[kindOf(NS[c], m)];
          for (let j = 0; j < 3; j++) mix[3 * (m - 1) + j] += w * col[j];
        }
      }
      for (let m = 1; m <= T; m++) {
        const i = 4 * ((T - m) * W + x);
        for (let j = 0; j < 3; j++) img.data[i + j] = Math.round(mix[3 * (m - 1) + j]);
        img.data[i + 3] = 255;
      }
    }
    strip.width = W;
    strip.height = T;
    sctx.putImageData(img, 0, 0);
    ctx.fillStyle = token('--paper');
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(strip, 0, 0, W, T, L, top, W, T * pitch);
    for (let r = 1; r <= T; r++) ctx.fillRect(L, top + r * pitch - gap, W, gap);
    // A hairline grid (dreeves, 2026-10-29: "maybe when zoomed in enough the full grid could become visible", then of
    // the powers-of-2 chart's: "this with hairline grid looks great to me"): with the rows' gaps, a line of page
    // surface one device px wide at each boundary of whole columns, fading in as columns widen from 4 CSS px to 8, so
    // none shows at the full view.
    ctx.globalAlpha = Math.min(Math.max((1 / k / dpr - 4) / 4, 0), 1);
    for (let c = Math.floor(u0) + 1; c < u0 + span; c++) ctx.fillRect(L + Math.floor((c - u0) / k), top, 1, T * pitch);
    ctx.globalAlpha = 1;
    // Axes: every m on the left; below, n under the middle of its column, at the first of 4, 20, 40, 100, 200, 500 (the
    // round multiples of 4, so every label has a column, n / 4) that leaves room for each label.
    const serif = token('--serif'), base = top + T * pitch;
    ctx.fillStyle = token('--muted');
    ctx.font = `${12 * dpr}px ${serif}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let m = 1; m <= T; m++) ctx.fillText(String(m), L - 7 * dpr, top + (T - m) * pitch + (pitch - gap) / 2);
    const step = [4, 20, 40, 100, 200, 500].find(s => s / 4 / k >= 48 * dpr);
    assert(step, W, span);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let n = Math.max(step, Math.ceil((4 * u0 - 2) / step) * step); n / 4 + 0.5 <= u0 + span; n += step) {
      const x = L + (n / 4 + 0.5 - u0) / k;
      ctx.fillRect(Math.round(x - dpr / 2), base, dpr, 4 * dpr);
      ctx.fillText(String(n), x, base + 7 * dpr);
    }
    ctx.fillStyle = token('--ink');
    ctx.font = `italic ${15 * dpr}px ${serif}`;
    ctx.textAlign = 'left';
    ctx.fillText('n', 2 * dpr, base + 6 * dpr);
    ctx.textBaseline = 'middle';
    ctx.fillText('m', 2 * dpr, top + T * pitch / 2);
    // Rings just outside cells, 2 device px wide: each of RINGS in gold, with a gold dot half the cell's smaller side
    // across in each proven the least, then the cell read out in ink, and the target of the box open, its cell, column
    // or row (since 2026-11-04: [c, m], null for every column or every row).
    const ring = ([c, m]) => {
      const [c0, c1] = c === null ? [0, NCOL] : [c, c + 1], [m0, m1] = m === null ? [1, T] : [m, m];
      const x0 = L + (c0 - u0) / k, x1 = L + (c1 - u0) / k, y0 = top + (T - m1) * pitch;
      ctx.strokeRect(x0 - dpr, y0 - dpr, x1 - x0 + 2 * dpr, (m1 - m0 + 1) * pitch - gap + 2 * dpr);
    };
    ctx.save();
    ctx.beginPath();
    ctx.rect(L - 2 * dpr, 0, W + 4 * dpr, base);
    ctx.clip();
    ctx.lineWidth = 2 * dpr;
    ctx.strokeStyle = ctx.fillStyle = token('--record');
    RINGS.forEach(({n, m}) => ring([NS.indexOf(n), m]));
    RINGS.filter(r => r.role === 3).forEach(({n, m}) => {
      ctx.beginPath();
      ctx.arc(L + (NS.indexOf(n) + 0.5 - u0) / k, top + (T - m) * pitch + (pitch - gap) / 2, Math.min(1 / k, pitch - gap) / 4, 0, 2 * Math.PI);
      ctx.fill();
    });
    ctx.strokeStyle = token('--ink');
    picked.forEach(ring);                                          // outline the cell read out, just outside it
    pinned.forEach(ring);                                          // and the target of the box open
    ctx.restore();
    // The box's caret under its target's column's middle, kept within the plot, or under its row's m label (--caret, in
    // CSS px from the box's left edge inside its border)
    const left = cv.getBoundingClientRect().left - panel.getBoundingClientRect().left - panel.clientLeft;
    pinned.forEach(([c]) => panel.style.setProperty('--caret', `${left + (c === null ? LEFT / 2
      : Math.min(Math.max(L + (c + 0.5 - u0) / k, L), L + W) / dpr)}px`));
    // The cell read out on the axes (dreeves's README, 2026-11-02: "[HOV] When hovering/clicking on cells in the charts
    // it'd be nice to highlight the values of m and n (resp., delta and k) on the axes of the chart"): its m and its n,
    // each in paper on a box of ink as tall as a row's colored part and 3 px wider than the number on either side, the
    // m over its row's m label and the n on the n labels' line, under its column's middle while that is in view, as a
    // label's must be, over any label there.  The chart of powers of 2 tags its δ and k the same way.
    ctx.font = `${12 * dpr}px ${serif}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const tag = (t, x, y) => {                                     // the number t, centered at x, y
      const w = ctx.measureText(t).width + 6 * dpr;
      ctx.fillStyle = token('--ink');
      ctx.fillRect(Math.round(x - w / 2), Math.round(y - (pitch - gap) / 2), Math.round(w), pitch - gap);
      ctx.fillStyle = token('--paper');
      ctx.fillText(t, x, y);
    };
    picked.forEach(([, m]) => tag(String(m), L - 7 * dpr - ctx.measureText(String(m)).width / 2,
      top + (T - m) * pitch + (pitch - gap) / 2));
    picked.filter(([c]) => u0 <= c + 0.5 && c + 0.5 <= u0 + span)    // 13 px down: the n labels' middle, 7 + 12 / 2
      .forEach(([c]) => tag(String(NS[c]), L + (c + 0.5 - u0) / k, base + 13 * dpr));
  }

  // What is at CSS x, y (panZoom's targetAt): a cell, [column, m]; the strip of the n labels under the plot, [column,
  // null]; the strip of the m labels left of it, [null, m]; or null: the corner between those strips, the margin right
  // of the plot, the gap above its rows.
  function targetAt(x, y) {
    const X = x * geo.dpr - geo.L, Y = y * geo.dpr - geo.top, m = T - Math.floor(Y / geo.pitch);
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
    const mstar = [el('i', 'm'), el('sup', '*'), `(${n})`];
    const rings = RINGS.filter(r => r.n === n && r.m === m);        // none or one
    swatch.className = `swatch ${KIND[kind]}`;
    swatch.classList.toggle('record', rings.length > 0);
    swatch.classList.toggle('proven', rings.some(r => r.role === 3));
    ro.replaceChildren(swatch, nw(el('i', 'n'), ` = ${n}, `, el('i', 'm'), ` = ${m}`), ' · ',
      nw(...(lo === hi ? [...mstar, ` = ${lo}`] : [`${lo} ≤ `, ...mstar, ` ≤ ${hi}`])), ' · ',
      [[why[0]], why, [why[1]]][kind].map(f => f()).join(' · '));
    ro.append(...rings.map(r => ` · ${NOTES[r.role](m)}`));
  }
  view.redraw();
  new ResizeObserver(() => view.redraw()).observe(cv);
  document.fonts.ready.then(() => view.redraw());
} catch (e) {
  ro.textContent = `Error drawing the chart: ${e}`;
  throw e;
}
})();
