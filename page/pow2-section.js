// Claude's chart of the bounds on m*(2^k) − k for k up to 72, drawn from POW2, which pow2.js defines (pow2.py makes
// it and states its contract).  Column k is n = 2^k; row e is order k + e, an excess of e over Thue–Morse's order k.
// Cell (k, e) is green (exists) when k + e <= lo, gray (open) when lo < k + e <= hi, and red (impossible) above, up to
// row E = POW2.etop.  The plot is one svg with a rect per cell, its viewBox the columns in view (all K until it is
// zoomed) and E * ROW px tall, stretched to the plot's width.  It pans and zooms as the m*(n) chart does, by the same
// code (panZoom, 2026-10-30), and a cell reads itself out on a hover, a tap or a click.  Its grid is hairlines of page
// surface (dreeves, 2026-10-29: "this with hairline grid looks great to me"): the bottom GAP of each row, one device
// pixel, and a line one device pixel wide between every two columns.
(() => {
const chart = document.getElementById('pow2-chart'), ro = document.getElementById('pow2-readout');
try {
  const D = POW2, K = 72, ROW = 14, GAP = 1 / devicePixelRatio, NS = 'http://www.w3.org/2000/svg';
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };
  const prime = p => { for (let d = 2; d * d <= p; d++) if (p % d === 0) return false; return p >= 2; };
  const sub = k => String(k).replace(/\d/g, d => '₀₁₂₃₄₅₆₇₈₉'[d]);
  // The norm lemma's bound at n = 2^k for an odd prime p, in exact integers (mstar.py's norm): the largest m with
  // p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1), size(p, r) the number of i in 0..n-1 with i = r (mod p).
  const normBound = (k, p) => {
    const n = 2n ** BigInt(k), P = BigInt(p), sizes = Array.from({length: p}, (_, r) => (n - BigInt(r) + P - 1n) / P);
    const rhs = (P * sizes.reduce((t, x) => t + x * x, 0n)) ** (P - 1n);
    let m = 0n;
    while (P ** (2n * m + 2n) * (P - 1n) ** (P - 1n) <= rhs) m++;
    return Number(m);
  };
  // A block [n, m] of a join's product: τ_j, Thue–Morse of length 2^j; or p_n, the sequence behind column n <= NMAX of
  // the m*(n) chart, or one of LONG, the examples longer than NMAX in the remarks below, as [n, m] (none since
  // 2026-10-27, when the m*(n) chart reached the one there was, at 1024).  name gives its symbol in the readout, and ''
  // for anything else, which the contract rules out: f, the 2^24 construction of the remarks below, among them since
  // 2026-10-29 (dreeves: "ok", to dropping f, which no reason had used since 2026-10-25).
  const NMAX = MSTAR.nmax;                                          // the m*(n) chart's last n, as its data have it (1024, a number here, until 2026-11-10: 2048 since, [BOU])
  const LONG = [];
  const name = ([n, m]) => n === 2 ** m ? `τ${sub(m)}`
    : n <= NMAX || LONG.some(b => b[0] === n && b[1] === m) ? `p${sub(n)}` : '';
  const isBlock = b => Array.isArray(b) && b.length === 2 && b.every(Number.isInteger) && b[0] >= 1 && b[1] >= 0
    && name(b) !== '';
  const length = p => p.reduce((t, [n]) => t * BigInt(n), 1n), order = p => p.reduce((t, [, m]) => t + m, 0);
  const joined = ps => ps.map(p => `(${p.map(name).join(' # ')})`).join(' ∨ ');     // a join of products, written out
  // The reasons of the data contract.  ok(k, lo or hi, ...its arguments) checks one; text(k, lo or hi, ...) gives it in
  // Claude's words, starting "order lo" or "order hi + 1"; and witness(k, lo, ...) or proof(k, hi, ...) what a box
  // shows of it, as the m*(n) chart's do (page/shared.js; since 2026-11-04, [CEL]): Thue–Morse's signs, or a join's
  // construction, its products in parentheses as the readout writes them, each block τ_j or p_n, which page/codes.js
  // expands into its derivation; and the proof of an upper bound worked out for 2^k.
  const blockTex = ([n, m]) => n === 2 ** m ? `\\tau_{${m}}` : `p_{${n}}`;
  const LO = {
    'thue-morse': {
      ok: (k, lo) => lo === k,
      // readout reason; says order lo, which is k, is known from Thue–Morse, τ_k
      text: (k, lo) => `order ${lo} from Thue–Morse, τ${sub(k)}`,
      witness: (k, lo) => shown([filled('witness-thue-morse', {bound: bound(`2^{${k}}`, 'ge', lo), tau: `\\(\\tau_{${k}}\\)`})]),
    },
    joins: {
      ok: (k, lo, ps) => Array.isArray(ps) && ps.length >= 1 && ps.every(p => Array.isArray(p) && p.length >= 1
        && p.every(isBlock)) && ps.reduce((t, p) => t + length(p), 0n) === 2n ** BigInt(k)
        && lo === Math.min(...ps.map(order)),
      // readout reason; says order lo is known from the join of these expanded products
      text: (k, lo, ps) => `order ${lo} from the join ${joined(ps)}`,
      witness: (k, lo, ps) => construction(2n ** BigInt(k), `2^{${k}}`, lo,
        ps.map(p => `(${p.map(blockTex).join(' \\mathbin{\\#} ')})`).join(' \\vee ')),
    },
  };
  // The m*(n) chart's reasons of an upper bound at an even n, copied line for line from its script: the reasons of
  // ["mstar", why], 2^k <= NMAX.
  const MSTAR_HI = {
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
      ok: (n, hi, who) => credit(who).length === 1,              // who is a class of the new results' cells, which their legend words
      // readout reason; says order hi + 1 is ruled out in this page's new results, naming whose they are
      text: (n, hi, who) => `order ${hi + 1} ruled out in the new results above (${credit(who)[0]})`,
      proof: (n, hi, who) => PROOF.page(BigInt(n), `${n}`, hi, who),
    },
  };
  const HI = {
    mstar: {
      ok: (k, hi, why) => 2 ** k <= NMAX && Array.isArray(why) && Object.hasOwn(MSTAR_HI, why[0])
        && MSTAR_HI[why[0]].ok.length === why.length + 1 && MSTAR_HI[why[0]].ok(2 ** k, hi, ...why.slice(1)),
      text: (k, hi, why) => MSTAR_HI[why[0]].text(2 ** k, hi, ...why.slice(1)),
      proof: (k, hi, why) => MSTAR_HI[why[0]].proof(2 ** k, hi, ...why.slice(1)),
    },
    norm: {
      ok: (k, hi, p) => Number.isInteger(p) && p > 2 && prime(p) && hi === normBound(k, p),
      text: (k, hi, p) => MSTAR_HI.norm.text(2 ** k, hi, p),        // the same lemma, in the same words
      proof: (k, hi, p) => PROOF.norm(2n ** BigInt(k), `2^{${k}}`, hi, p),
    },
    residue: {
      ok: (k, hi, chain) => Array.isArray(chain) && chain.length >= 1 && chain.every(Number.isInteger) && chain[0] >= 2
        && chain.slice(1).every((M, i) => M > chain[i] && M % chain[i] === 0),
      // readout reason; says order hi + 1 is ruled out by the residue conditions mod each modulus of the chain
      text: (k, hi, chain) => `order ${hi + 1} ruled out by the residue conditions mod ${chain.join(', ')}`,
      proof: (k, hi, chain) => PROOF.residue(2n ** BigInt(k), `2^{${k}}`, hi, 'pow2.py', ...chain),
    },
  };
  assert(Object.keys(D).sort().join() === 'cols,etop,kmax', Object.keys(D));
  assert(D.kmax === K && Array.isArray(D.cols) && D.cols.length === K && Number.isInteger(D.etop), D.kmax, D.etop);
  D.cols.forEach((c, i) => {
    const k = i + 1, [lo, hi, lw, hw] = c;
    assert(c.length === 4 && Number.isInteger(lo) && Number.isInteger(hi) && k <= lo && lo <= hi && hi < k + D.etop,
           k, c);
    for (const [R, w, v] of [[LO, lw, lo], [HI, hw, hi]]) {
      assert(Array.isArray(w) && Object.hasOwn(R, w[0]) && R[w[0]].ok.length === w.length + 1
             && R[w[0]].ok(k, v, ...w.slice(1)), k, c);
    }
  });
  assert(D.etop === Math.max(...D.cols.map((c, i) => c[1] - i)), D.etop);   // E = max(hi - k) + 1

  const E = D.etop, KIND = ['exists', 'open', 'impossible'];       // the kinds of cell, by the tokens of their colors
  const kindOf = (k, e) => (k + e > D.cols[k - 1][0]) + (k + e > D.cols[k - 1][1]);
  const MEANING = ['known', 'open', 'impossible'];                 // what a cell of each kind says, in the readout (dreeves's words)
  const el = (tag, cls, text) => Object.assign(document.createElement(tag), {className: cls, textContent: text});
  const at = (node, style) => { Object.assign(node.style, style); return node; };
  const nw = (...parts) => { const s = el('span', 'nw', ''); s.append(...parts); return s; };   // no wrap
  // A text as the readout's nodes: each run of sub's subscript digits becomes a <sub> of plain digits, which the page's
  // font draws; it has no glyphs for U+2080–2089, and the fallback fonts that drew them differed from digit to digit.
  const subbed = s => s.split(/([₀-₉]+)/).map((t, i) => i % 2
    ? el('sub', '', [...t].map(d => '₀₁₂₃₄₅₆₇₈₉'.indexOf(d)).join('')) : t);
  const svg = document.createElementNS(NS, 'svg'), outline = el('div', 'pow2-outline', ''), swatch = el('span', '', '');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.style.height = `${E * ROW}px`;
  // The smallest cells of each row, ringed in gold just outside them as the m*(n) chart rings its own (dreeves's README,
  // 2026-10-28: "[GTR] Gold trim for the powers-of-2 chart to highlight the values in the theorem"; then 2026-10-30:
  // "[GLT] ... match the "smallest length known" table: green+gold is the smallest *known* n (resp. 2^k) for a give m
  // (resp. delta) and black+gold is the smallest n (resp. 2^k) not ruled out"): for each record gap g, [k, g, role] for
  // the least k with lo >= k + g, a bound the theorem states (the table below has the same), and the least k with
  // hi >= k + g, one cell when they agree; role 1 known, 2 not ruled out, 3 both, proven the least, which also gets a
  // gold dot (Claude's proposal for the indicator, 2026-10-30).  The ring is 2 px above and below the cell, over the
  // hairlines there and the neighbors' edges, and 1 px at its sides, where a phone's columns are about 4 px wide; it
  // lies over the grid and under the outline of the cell read out, whose swatch it rings too, with a note (dreeves,
  // 2026-10-28: "don't forget the gold trim on the hover version"), as the m*(n) chart's readout does for its rings.
  const trims = raised(D.cols, j => j + 1).flatMap(([known, possible], j) => [...new Set([...known, ...possible])]
    .sort((x, y) => x - y).map(g => [j + 1, g, known.includes(g) + 2 * possible.includes(g)]));  // [k, δ, role], the rows k raises
  assert(trims.every(([, g]) => g <= E), trims);
  // readout note on a cell ringed in gold; says 2^k is the least power of 2 known to beat Thue–Morse by δ, a bound the theorem below states
  const knownNote = e => `the smallest k known to beat Thue–Morse by ${e} (see theorem below)`;
  const NOTES = {1: [knownNote],                                   // the readout's notes on a ringed cell, by its role
    // Readout note on a black cell ringed in gold; says its k is the least whose upper bound allows beating Thue–Morse by δ
    2: [e => `the smallest k not ruled out to beat Thue–Morse by ${e}`],
    // Readout note on a cell dotted in gold; says no smaller k beats Thue–Morse by δ, as proven
    3: [knownNote, e => `proven as the smallest k to beat Thue–Morse by ${e}`]};
  function readout(c, e) {                                         // read out the cell of column c, k = c + 1, and row e
    const k = c + 1, [lo, hi, lw, hw] = D.cols[k - 1], kind = kindOf(k, e);
    const gold = trims.filter(([tk, te]) => tk === k && te === e);  // none or one
    const why = [() => LO[lw[0]].text(k, lo, ...lw.slice(1)), () => HI[hw[0]].text(k, hi, ...hw.slice(1))];
    const two = () => ['2', el('sup', '', String(k))];           // 2^k
    swatch.className = `swatch ${KIND[kind]}`;
    swatch.classList.toggle('record', gold.length > 0);
    swatch.classList.toggle('proven', gold.some(([, , role]) => role === 3));
    ro.replaceChildren(swatch,
      nw(el('i', '', 'k'), ` = ${k}, `, el('i', '', 'n'), ' = ', ...two(), ', ', el('i', '', 'm'),
         ` = ${k} + ${e} = ${k + e}`),
      ' · ', MEANING[kind], ' · ', nw(`${lo} ≤ `, el('i', '', 'm'), el('sup', '', '*'), '(', ...two(), `) ≤ ${hi}`),
      ' · ', ...subbed([[why[0]], why, [why[1]]][kind].map(f => f()).join(' · ')));
    ro.append(...gold.flatMap(([, , role]) => NOTES[role].map(f => ` · ${f(e)}`)));
  }
  for (let k = 1; k <= K; k++) for (let e = 1; e <= E; e++) {
    const r = document.createElementNS(NS, 'rect');
    const attributes = {x: k - 1, y: (E - e) * ROW, width: 1, height: ROW - GAP, class: KIND[kindOf(k, e)]};
    for (const [a, v] of Object.entries(attributes)) r.setAttribute(a, v);
    svg.append(r);
  }
  for (let k = 1; k < K; k++) {                                    // the lines between columns, over the cells
    const l = document.createElementNS(NS, 'line');
    for (const [a, v] of Object.entries({x1: k, y1: 0, x2: k, y2: E * ROW, 'stroke-width': GAP})) l.setAttribute(a, v);
    svg.append(l);
  }
  // The axes: every e left of the plot, beside the letter δ (dreeves's README, 2026-10-28: "[DLT] Change "excess e" to
  // delta unless e is following precedent from BGPW", and BGPW name no excess); below it, the letter k and every tenth
  // k under its column
  const es = el('div', 'pow2-es', ''), plot = el('div', 'pow2-plot', ''), ks = el('div', 'pow2-ks', '');
  for (let e = 1; e <= E; e++) {                                   // centered on its row's colored part
    es.append(at(el('span', '', String(e)), {top: `${(E - e) * ROW}px`, lineHeight: `${ROW - GAP}px`}));
  }
  // The cell read out on the axes (dreeves's README, 2026-11-02: "[HOV] When hovering/clicking on cells in the charts
  // it'd be nice to highlight the values of m and n (resp., delta and k) on the axes of the chart"), as the m*(n) chart
  // tags its m and n: its δ over its row's δ label (etag) and its k on the k labels' line under its column's middle
  // (ktag, last in ks, over any label there), each in paper on ink, as tall as a row's colored part; both hidden until a
  // cell is read out, and the k also while its column's middle is out of view, as the k labels are (shows).
  const [etag, ktag] = Array.from({length: 2}, () => at(el('span', 'pow2-tag', ''), {lineHeight: `${ROW - GAP}px`}));
  es.append(el('i', '', 'δ'), etag);
  // The rings and the outlines lie in a frame 2 px larger than the plot on every side, which clips them where the view
  // ends, as the m*(n) chart clips its rings.  place(div, [c, e], side, u0, span) puts div around the cells of column
  // c and row e in the view [u0, u0 + span), c null for every column and e for every row (since 2026-11-04, for the
  // target of the box open, pin, outlined as the cell read out is): side px out at its sides, 2 px above and below.
  const frame = el('div', 'pow2-frame', ''), rings = trims.map(() => el('div', 'pow2-trim', ''));
  const proven = trims.filter(([, , role]) => role === 3), dots = proven.map(() => el('div', 'pow2-dot', ''));
  const pin = el('div', 'pow2-outline', ''), panel = document.getElementById('pow2-panel');
  const place = (div, [c, e], side, u0, span) => {
    const [c0, c1] = c === null ? [0, K] : [c, c + 1], [e0, e1] = e === null ? [1, E] : [e, e];
    return at(div, {left: `calc(${(c0 - u0) / span} * (100% - 4px) + ${2 - side}px)`,
      width: `calc(${(c1 - c0) / span} * (100% - 4px) + ${2 * side}px)`, top: `${(E - e1) * ROW}px`, height: `${(e1 - e0 + 1) * ROW - GAP + 4}px`});
  };
  frame.append(...rings, ...dots, outline, pin);
  plot.append(svg, frame);
  chart.append(es, plot, el('i', 'pow2-k', 'k'), ks);
  const TENS = Array.from({length: Math.floor(K / 10)}, (_, i) => 10 * i + 10);     // the k labeled below the plot
  // the view [u0, u0 + span), the cell read out (picked) and the target of the box open (pinned)
  function draw(u0, span, picked, pinned) {
    const shows = k => u0 <= k - 0.5 && k - 0.5 <= u0 + span;      // whether column k's middle is in view
    svg.setAttribute('viewBox', `${u0} 0 ${span} ${E * ROW}`);
    trims.forEach(([k, e], i) => place(rings[i], [k - 1, e], 1, u0, span));
    proven.forEach(([k, e], i) => at(dots[i], {left: `calc(${(k - 0.5 - u0) / span} * (100% - 4px) + 2px)`,   // its middle,
      top: `${(E - e) * ROW + 2 + (ROW - GAP) / 2}px`, width: `min(${0.5 / span} * (100% - 4px), ${(ROW - GAP) / 2}px)`}));
    outline.hidden = etag.hidden = picked.length === 0;
    ktag.hidden = !picked.some(([c]) => shows(c + 1));
    pin.hidden = pinned.length === 0;
    pinned.forEach(t => place(pin, t, 2, u0, span));
    // The box's caret under its target's column's middle, kept within the plot, or under its row's δ label (--caret, in
    // CSS px from the box's left edge inside its border)
    const p = plotBox(), left = chart.getBoundingClientRect().left - panel.getBoundingClientRect().left - panel.clientLeft;
    pinned.forEach(([c]) => panel.style.setProperty('--caret', `${left + (c === null ? p.left / 2
      : p.left + Math.min(Math.max((c + 0.5 - u0) / span, 0), 1) * p.width)}px`));
    picked.forEach(([c, e]) => {
      place(outline, [c, e], 2, u0, span);
      at(etag, {top: `${(E - e) * ROW}px`}).textContent = String(e);
      at(ktag, {left: `${(c + 0.5 - u0) / span * 100}%`}).textContent = String(c + 1);
    });
    ks.replaceChildren(...TENS.filter(shows).flatMap(k => {
      const left = `${(k - 0.5 - u0) / span * 100}%`;              // under the middle of column k
      return [at(el('span', 'pow2-tick', ''), {left}), at(el('span', 'pow2-klabel', String(k)), {left})];
    }), ktag);
  }
  const plotBox = () => { const a = chart.getBoundingClientRect(), b = svg.getBoundingClientRect();
    return {left: b.left - a.left, top: b.top - a.top, width: b.width}; };
  // What is at CSS x, y (panZoom's targetAt): a cell, [column, e]; the strip of the k labels under the plot, [column,
  // null]; the strip of the δ labels left of it, [null, e]; or null: the corner between those strips and the margin
  // right of the plot.
  function targetAt(x, y) {
    const p = plotBox(), e = E - Math.floor((y - p.top) / ROW);
    const t = [x < p.left ? null : x < p.left + p.width ? Math.floor(view.uAt(x)) : undefined, y < p.top ? undefined : e >= 1 ? e : null];
    return t.includes(undefined) || t.every(v => v === null) ? null : t;
  }
  // The boxes under the chart (chartPanel, in page/shared.js), as the m*(n) chart's: the target [c, e] is the cell of
  // column c, k = c + 1, and row e, order k + e; [c, null] the column, at its k label; [null, e] the row, at its δ
  // label; their fragments kK, dD and kKdD.  A cell's box and a column's show what the m*(n) chart's do, the searches
  // at n = 2^k and m = k + e; a row's (e), the legend's words for each gold-ringed cell of the row, with its k, linked to
  // its cell's box: the least k known to beat Thue–Morse by e and the least not ruled out to, or the one cell, proven,
  // where they agree; and, where e is a record gap, its row of the table of record gaps, under that table's own head
  // (recordGaps, below; the main session's design of 2026-11-04 for [ROC], whose rows dreeves named for the m*(n) chart).
  const legend = [...chart.closest('section').querySelectorAll('.legend li')];
  const witness = k => { const [lo, , lw] = D.cols[k - 1]; return together(LO[lw[0]].witness(k, lo, ...lw.slice(1)), copies(2n ** BigInt(k), lo)); };
  const proof = k => { const [, hi, , hw] = D.cols[k - 1]; return HI[hw[0]].proof(k, hi, ...hw.slice(1)); };
  const rowBox = e => shown([...trims.filter(([, te]) => te === e).map(([k, , role]) => filled('row-ring',
    {item: legendItem(legend, ['', 'exists', 'open', 'exists'][role], role), k: linked(`#k${k}d${e}`, `\\(k = ${k}\\)`)})),
    ...recordGaps().slice(e - 1, e).map(body => {
      const part = filled('row-gaps', {});
      part.querySelector('table').append(document.querySelector('[data-record-gaps] thead').cloneNode(true), body);
      return part;
    })]);
  const SAYS = {exists: witness, impossible: proof, open: (k, e) => together(witness(k), proof(k), searches(2n ** BigInt(k), k + e)),
                column: k => together(witness(k), proof(k), shown([], [2n ** BigInt(k)])), row: (k, e) => rowBox(e)};
  const cell = (k, e) => {
    const [swatch, ...words] = legendItem(legend, KIND[kindOf(k, e)], Math.max(0, ...trims.filter(([tk, te]) => tk === k && te === e).map(([, , role]) => role)));
    return [swatch, linked(`#k${k}`, `\\(k = ${k}\\)`), ', ', linked(`#d${e}`, `\\(\\delta = ${e}\\)`), ': ', ...words];
  };
  const HEADINGS = {exists: cell, open: cell, impossible: cell, row: (k, e) => [`\\(\\delta = ${e}\\)`], column: k => {
    const [lo, hi] = D.cols[k - 1];
    return [`\\(k = ${k}\\)`, ', ', `\\(n = 2^{${k}}\\)`, ': ', `\\(${lo === hi ? `m^*(2^{${k}}) = ${lo}` : `${lo} \\le m^*(2^{${k}}) \\le ${hi}`}\\)`];
  }};
  const open = chartPanel({region: panel, chart, ncol: () => K, nrow: E, pin: ts => view.pin(ts),
    fragment: (c, e) => `${c === null ? '' : `k${c + 1}`}${e === null ? '' : `d${e}`}`,
    fill: (c, e) => {
      const k = c + 1, kind = c === null ? 'row' : e === null ? 'column' : KIND[kindOf(k, e)];
      return {kind, heading: HEADINGS[kind](k, e), ...SAYS[kind](k, e)};
    }});
  const view = panZoom({el: chart, out: document.getElementById('pow2-zoom-out'), in: document.getElementById('pow2-zoom-in'),
    resets: [document.getElementById('pow2-reset')], ncol: () => K, plot: plotBox, targetAt, readout, draw, open});
  view.redraw();
} catch (e) {
  ro.textContent = `Error drawing this chart: ${e}`;
  throw e;
}
})();
// Claude's table of the construction behind each inequality of the theorem (Stan Wagon's table, extended, 2026-10-18;
// record_gaps.wl makes the same one in Mathematica), from POW2: for each record gap g = 1, 2, ..., the least k whose lo
// is at least k + g, and its reason as a join of products of blocks (JOIN), each record gap a tbody of its own, which
// recordGaps() gives, in order (since 2026-11-04 a function, as a row's box of the chart above shows one of them).  A
// product is a row: its blocks ascending by length, a repeated one written once, as a power (368²) in the power of 2
// and as count·order (2·9) in the order; a + before every product but the first; the bound's cell spans its rows.
function recordGaps() {
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };
  const at = g => POW2.cols.findIndex((c, i) => c[0] >= i + 1 + g) + 1;      // the least k with lo >= k + g; 0 if none
  const factors = p => {                               // a product's blocks, ascending by length, each with its count
    const b = [...p].sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    return [...new Set(b.map(String))].map(s => [...s.split(',').map(Number), b.filter(x => String(x) === s).length]);
  };
  const sum = p => p.reduce((s, [, m]) => s + m, 0);
  // a lower bound's reason as a join of products of blocks: a join as it is; any other kind has no entry, and its
  // record gap throws (f^{#L} # τ_j, f the 2^24 construction, was a kind until 2026-10-29)
  const JOIN = {joins: ([, ps]) => ps};
  // a product's power of 2 and order in LaTeX, which KaTeX draws once the page is parsed (2026-10-28)
  const length = p => factors(p).map(([n, , c]) => c > 1 ? `${n}^{${c}}` : `${n}`).join(' \\cdot ');
  const order = p => factors(p).map(([, m, c]) => c > 1 ? `${c} \\cdot ${m}` : `${m}`).join(' + ') + ` = ${sum(p)}`;
  const bodies = [];
  for (let g = 1; at(g); g++) {
    const k = at(g), [lo, , why] = POW2.cols[k - 1], join = JOIN[why[0]](why);
    assert(lo === k + g && Math.min(...join.map(sum)) === lo, k, lo);
    assert(join.reduce((s, p) => s + p.reduce((t, [n]) => t * BigInt(n), 1n), 0n) === 2n ** BigInt(k), k);
    const plus = ['', ...join.slice(1).map(() => '+ ')];
    const body = document.createElement('tbody');
    body.innerHTML = join.map((p, i) => `<tr><td>${plus[i]}\\(${length(p)}\\)</td><td>\\(${order(p)}\\)</td></tr>`).join('');
    body.rows[0].insertAdjacentHTML('afterbegin', `<td rowspan="${join.length}">\\(m^*(2^{${k}}) \\ge ${lo}\\)</td>`);
    bodies.push(body);
  }
  return bodies;
}
(() => {
const table = document.querySelector('[data-record-gaps]');
try {
  table.append(...recordGaps());
} catch (e) {
  // Error line, as the table's caption; says this table could not be made, followed by the error
  table.createCaption().textContent = `Error making this table: ${e}`;
  throw e;
}
})();
