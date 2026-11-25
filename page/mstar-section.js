// Claude's chart of m*(n), drawn from MSTAR, which mstar.js defines (mstar.py makes it and states its contract), for n
// up to MSTAR.nmax, whose caps show views of it since 2026-11-23 (page/shared.js; until then for n up to the cap, the
// one pressed of the page's caps; dreeves's README, [BOU], 2026-11-10: "Let's try having Figure 1
// go up to 2048. Actually, let's try this: replace the reset-zoom button with "cap:" and then buttons for 2^6, 2^7,
// 2^8, 2^9, 2^10, 2^11"; n up to 1024 until then, which was the cap pressed as the page loads until 2026-11-12, when
// dreeves asked for 2^11: "let's default to all checkboxes checked and cap=2^11 for figure 1").  Column n is green (exists) in rows m = 1 to lo, gray (open) up to hi and red (impossible) above, up to row
// MSTAR.mtop.  Since 2026-11-11 (dreeves's README, [SYC]: "a different styling on the chart (like striped or half-and-half
// black vs red, split diagonally) for cells for which we know they're red conditional on the Symmetry Conjecture being
// true") a column that MSTAR.ifsym lists has a lower upper bound if BGPW's Symmetry Conjecture holds, and its cells
// above that bound, up to hi, are of a fourth kind, ifsym: open, with the upper right triangle in the red of an
// impossible cell.  The columns are NS: every n up to the cap but those that a checked box of the page's list leaves out (dreeves's
// README, [COM], 2026-11-10: "checkboxes for what's omitted, in terms of the biggest power of two factor").  As the page
// loads every box is checked (since 2026-11-12, as above), so NS is n = 2 and 4, the multiples of 8 below 200 and the
// multiples of 16 from 208 on (until then the first two alone, so n = 2 and the multiples of 4, as dreeves asked on
// 2026-10-29: "can we make my "odd multiple of 2" bullet point be true?"; every even n before): an odd n has no
// partition at any m, every other n = 2 mod 4 has m*(n) = 1, and so on, as the data contract asserts of every box's n.  Pan and zoom (panZoom, which the chart of powers of 2 shares since
// 2026-10-30) act on n only: the view is the interval [u0, u0 + span) of u,
// column c (from 0), n = NS[c], spanning u from c to c + 1.  The rows follow the view (dreeves, 2026-11-10: "however
// the chart is zoomed, make there always be exactly one fully pink row, ie, zoom in the y direction automatically as a
// function of the x zoom"): rows 1 to one more than the largest upper bound among the columns in view, sharing the
// plot's height, so that the top row, and it alone, is impossible in every column of the view.  Each device pixel of the plot mixes the colors of the
// cells it covers, weighted by how much of it each covers, so all the columns (142 as the page loads) can show at once
// even where they are narrower than a pixel.  Since 2026-11-23 page/shared.js draws it (gridChart), and Figure 2 the
// same way (dreeves: "please DRY up as much as possible between the 2 figures"): this script holds its data's
// contract, its columns and rows, and what its readout and its boxes say.
(() => {
const cv = document.getElementById('mstar-chart'), ro = document.getElementById('mstar-readout');
const fail = chartFail(ro);                                       // loudly: in the readout, and uncaught
try {
  const D = MSTAR;
  // A box of the list leaves out, while checked, the odd multiples of its factor from its start on, each of which
  // has m*(n) = the order it states.
  const OMIT = [...document.querySelectorAll('#mstar-omit input')].map(box =>
    ({box, factor: +box.dataset.factor, from: +box.dataset.from, order: +box.dataset.order}));
  const leftOut = (n, {factor, from}) => n >= from && n % (2 * factor) === factor;
  const stated = (n, [lo, hi], o) => !o.box.checked || !leftOut(n, o) || (lo === o.order && hi === o.order);
  // The columns, every n up to nmax that no checked box leaves out (up to the cap pressed until caps became views,
  // 2026-11-23), which hold what the checked boxes state, as the page loaded (a check that fails fails loudly then too);
  // they change when a box does (the end of this file)
  const columns = () => {
    D.cols.forEach((c, i) => OMIT.forEach(o => assert(stated(i + 1, c, o), i + 1, c)));
    return Array.from({length: D.nmax}, (_, i) => i + 1).filter(n => !OMIT.some(o => o.box.checked && leftOut(n, o)));
  };
  const loOf = n => ROWS.get(n)[0];                               // a length's lo, by its row (a column's until 2026-11-19)
  const EXPLICIT = new Set(['none', 'example', 'join', 'product']);   // the kinds of lower bound with a sequence behind them (2026-11-18)
  // The reasons of the data contract.  ok(n, lo or hi, ...its arguments) checks one; text(n, lo or hi, ...) gives it in
  // Claude's words, starting "order lo" or "order hi + 1"; and witness(n, lo, ...) or proof(n, hi, ...) what a box
  // shows of it (since 2026-11-04, [CEL]; an explanation in the panel of column n from 2026-11-03), from the templates
  // of the page (page/shared.js): an example's label and its code (since 2026-11-18, mstar.js's codes: coded), a join's
  // or a product's construction, which page/codes.js expands into its derivation, and a copy of each code of the page of
  // the length and the order of a lower bound not an example's (copies); and the proof of an upper bound worked out for n.  An odd n has a column only while
  // its box is unchecked, and every cell of it is impossible: "none" shows no witness, and "odd" that n is odd.
  // (Since 2026-11-18, when every witness came to be (-1)^lo-symmetric, dreeves: "making all witnesses conforming
  // sounds great": a join is of three parts, a, b, a, and a join's or a product's witness shows the code of the
  // sequence it builds (codeOf, columnSigns), as an example's shows its own; its parts are columns with a sequence
  // behind their lower bounds, EXPLICIT, as quals_mstar names them.)
  const LO = {
    none: {ok: (n, lo) => lo === 0 && n % 2 === 1, witness: () => shown()},
    example: {
      ok: (n, lo, label) => typeof label === 'string' && label !== '',
      // readout reason; says order lo is known from an example, naming where the example comes from
      text: (n, lo, label) => `order ${lo} from an example (${label})`,
      witness: (n, lo, label) => example(n, lo, linked(SOURCES.get(n), label), coded(BigInt(n), lo, CODES.get(n))),   // its code and source, the data's (2026-11-18)
    },
    join: {
      ok: (n, lo, a, b, c) => [a, b, c].every(k => Number.isInteger(k) && 1 <= k && EXPLICIT.has(ROWS.get(k)?.[2][0])) && a + b + c === n
        && lo <= Math.min(loOf(a), loOf(b), loOf(c)),
      // readout reason; says order lo is known from the join of the examples of lengths a, b and c
      text: (n, lo, a, b, c) => `order ${lo} from the join p${sub(a)}\u00a0∨\u00a0p${sub(b)}\u00a0∨\u00a0p${sub(c)}`,
      witness: (n, lo, a, b, c) => construction(BigInt(n), n, lo, `p_{${a}} \\vee p_{${b}} \\vee p_{${c}}`, coded(BigInt(n), lo, codeOf(columnSigns(n), lo))),
    },
    product: {
      ok: (n, lo, a, b) => [a, b].every(k => Number.isInteger(k) && 2 <= k && EXPLICIT.has(ROWS.get(k)?.[2][0])) && a * b === n
        && lo <= loOf(a) + loOf(b),
      // readout reason; says order lo is known from the expanded product of the examples of lengths a and b
      text: (n, lo, a, b) => `order ${lo} from the product p${sub(a)}\u00a0#\u00a0p${sub(b)}`,
      witness: (n, lo, a, b) => construction(BigInt(n), n, lo, `p_{${a}} \\mathbin{\\#} p_{${b}}`, coded(BigInt(n), lo, codeOf(columnSigns(n), lo))),
    },
    table2: {
      ok: (n, lo) => n % 8 === 0 && n <= 304,
      // readout reason; says order lo is known from BGPW's Table 2
      text: (n, lo) => `order ${lo} from BGPW's Table 2`,
      witness: (n, lo) => shown([filled('witness-table2', {bound: bound(n, 'ge', lo), codes: copies(BigInt(n), lo)})]),
    },
    page: {
      ok: (n, lo, who) => credit(who).length === 1,              // who is a class of the new results' cells, which their legend words
      // readout reason; says order lo is known from this page's new results, naming whose they are
      text: (n, lo, who) => `order ${lo} from the new results above (${credit(who)[0]})`,
      witness: (n, lo, who) => shown([filled('witness-page', {bound: bound(n, 'ge', lo), who: credit(who)[0], codes: copies(BigInt(n), lo)})], [BigInt(n)]),
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
  // past (since 2026-11-04, for the table of smallest lengths: 1440:16 until 2026-11-10; the Symmetry section's codes
  // longer than nmax since 2026-11-11): [n, lo, hi, loWhy, hiWhy] since 2026-11-19 (Opus 5.5; dreeves: "yes, full
  // anti-magic, add the new entries"), the row of a length past the chart that the page has a sequence of, rising in n,
  // which ROWS gives as it gives a column's ([n, m, label] until then, m the sequence's exact order)
  assert(Array.isArray(D.past) && D.past.every((p, i) => Array.isArray(p) && p.length === 5 && Number.isInteger(p[0]) && p[0] > D.nmax
    && (i === 0 || D.past[i - 1][0] < p[0])), D.past);
  const ROWS = mstarRows();                                       // each length's row, a column's or past's (page/shared.js)
  // each row, a column's or past's, by the same contract: its reasons', and the boxes' statements
  ROWS.forEach((c, n) => {
    const [lo, hi, lw, hw] = c;
    assert(c.length === 4 && Number.isInteger(lo) && Number.isInteger(hi) && 0 <= lo && lo <= hi, n, c);
    for (const [K, w, v] of [[LO, lw, lo], [HI, hw, hi]]) {
      assert(Object.hasOwn(K, w[0]) && K[w[0]].ok.length === w.length + 1 && K[w[0]].ok(n, v, ...w.slice(1)), n, c);
    }
    assert((lw[0] === 'none') === (n % 2 === 1) && (hw[0] === 'odd') === (n % 2 === 1), n, c);
    OMIT.forEach(o => assert(stated(n, c, o), n, c));              // why a checked box may leave n out
  });
  D.cols.forEach((c, i) => assert(c[1] < D.mtop, i + 1, c));      // the chart's top row above every column's upper bound
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
  // examples (2026-11-18; dreeves: "show the expandable hex code for everything"; codes, [n, code], until point 10 of
  // his that night): [n, code, source], rising in n, for exactly the columns whose lower bound is an example, each the
  // code of that example, ceil(n/8) hex digits (page/codes.js checks its bits as it expands it), and where it comes
  // from, a page (https) or, for one of this page, its entry in the appendix (#entry-N), to which its label links; for
  // past's rows too since 2026-11-19, so for every row whose lower bound is an example
  assert(Array.isArray(D.examples) && D.examples.every(([n, code, source], i) => Number.isInteger(n) && (i === 0 || D.examples[i - 1][0] < n)
    && typeof code === 'string' && /^[0-9A-F]+$/.test(code) && code.length === Math.ceil(n / 8)
    && typeof source === 'string' && /^(https:\/\/|#entry-\d+$)/.test(source)), 'examples');
  assert(D.examples.map(([n]) => n).join() === [...ROWS].flatMap(([n, [, , lw]]) => lw[0] === 'example' ? [n] : []).join(), 'examples of the rows');
  const CODES = new Map(D.examples.map(([n, code]) => [n, code])), SOURCES = new Map(D.examples.map(([n, , source]) => [n, source]));

  const IFHI = D.cols.map(c => c[1]);                             // each column's upper bound if the Symmetry Conjecture holds: its own, or ifsym's
  D.ifsym.forEach(([n, hi]) => { IFHI[n - 1] = hi; });
  const rowsOf = n => [D.cols[n - 1][0], IFHI[n - 1], D.cols[n - 1][1]];   // a column's bounds in rows, which are orders m
  const kindOf = (n, m) => cellKind(rowsOf(n), m);
  // The cells of the table of smallest lengths below, ringed in gold (dreeves's README, 2026-10-30: "[GLT] ... match the
  // "smallest length known" table: green+gold is the smallest *known* n (resp. 2^k) for a give m (resp. delta) and
  // black+gold is the smallest n (resp. 2^k) not ruled out"; a(m − 1) of OEIS A323395 alone from 2026-10-19, dreeves:
  // "green with gold trim"): each cell (n, m) whose column raises row m (raised): the least n known to reach m, role 1,
  // the least n whose upper bound allows m, role 2, or both, role 3: the least n of order m, proven, a(m − 1), which
  // also gets a gold dot (Claude's proposal for the indicator, 2026-10-30).
  const RINGS = raised(D.cols, () => 0).flatMap(([known, possible], i) => [...new Set([...known, ...possible])]
    .sort((x, y) => x - y).map(m => ({key: i + 1, r: m, role: known.includes(m) + 2 * possible.includes(m)})));
  const panel = document.getElementById('mstar-panel'), legend = [...cv.closest('section').querySelectorAll('.legend li')];
  const witness = n => { const [lo, , lw] = ROWS.get(n); return LO[lw[0]].witness(n, lo, ...lw.slice(1)); };   // by its row (2026-11-19)
  const proof = n => { const [, hi, , hw] = ROWS.get(n); return HI[hw[0]].proof(n, hi, ...hw.slice(1)); };
  const ifproof = n => PROOF.ifsym(BigInt(n), `${n}`, IFHI[n - 1], D.ifsym.find(e => e[0] === n)[2]);   // of a column that ifsym lists
  FACTS.mstar = {witness, proof, ifproofs: n => D.ifsym.filter(e => e[0] === n).map(() => ifproof(n))};
  // The legend's item of the cell (n, m), by its kind and the role of its gold ring, if any
  const item = (n, m) => legendItem(legend, kindOf(n, m), Math.max(0, ...RINGS.filter(r => r.key === n && r.r === m).map(r => r.role)));
  // A row's open cells (2026-11-18; dreeves: "clicking the m for a whole row in a chart should gather up all the relevant
  // things for that row"): each column shown whose cell of the row is above its lower bound and at or below its upper
  // bound, open or ifsym, in order of n: the legend's item for the cell, and n, linked to the cell's box; keys, the
  // columns shown
  const opened = (m, keys) => shown(keys.filter(n => D.cols[n - 1][0] < m && m <= D.cols[n - 1][1])
    .map(n => filled('row-cell', {item: item(n, m), at: linked(`#n${n}m${m}`, `\\(n = ${n}\\)`)})));
  const SAYS = {exists: witness, impossible: proof, open: (n, m) => together(witness(n), proof(n), searches(BigInt(n), m)),
                ifsym: (n, m) => together(witness(n), proof(n), ifproof(n), searches(BigInt(n), m)),   // an open cell's, with the bound if the conjecture holds
                column: n => shown([], [BigInt(n)]), row: (n, m, keys) => together(smallestBox(m), opened(m, keys))};
  const cell = (n, m) => {
    const [swatch, ...words] = item(n, m);
    return [swatch, linked(`#n${n}`, `\\(n = ${n}\\)`), ', ', linked(`#m${m}`, `\\(m = ${m}\\)`), ': ', ...words];
  };
  const HEADINGS = {exists: cell, open: cell, impossible: cell, ifsym: cell, row: (n, m) => [`\\(m = ${m}\\)`], column: n => {
    const [lo, hi] = D.cols[n - 1];
    return [`\\(n = ${n}\\)`, ': ', `\\(${lo === hi ? `m^*(${n}) = ${lo}` : `${lo} \\le m^*(${n}) \\le ${hi}`}\\)`];
  }};
  const swatch = document.createElement('span');
  const NOTES = {                                                  // the readout's note on a ringed cell, by its role
    // Readout note on a green cell ringed in gold; says its n is the least known to reach order m
    1: m => `the smallest n known of order ${m}`,
    // Readout note on a black cell ringed in gold; says its n is the least whose upper bound allows order m
    2: m => `the smallest n not ruled out for order ${m}`,
    // Readout note on a cell ringed in gold; says its n is the least of order m: the term a(m − 1) of OEIS A323395
    3: m => `the smallest n of order ${m}: a(${m - 1}) of OEIS A323395`,
  };
  const bounds = n => {                                            // m*(n)'s bounds as the readout writes them
    const [lo, hi] = D.cols[n - 1], mstar = [el('i', '', 'm'), el('sup', '', '*'), `(${n})`];
    return nw(...(lo === hi ? [...mstar, ` = ${lo}`] : [`${lo} ≤ `, ...mstar, ` ≤ ${hi}`]));
  };
  function cellOut(n, m) {                                         // the readout of the cell of n and m
    const [lo, hi, lw, hw] = D.cols[n - 1], kind = kindOf(n, m);
    const why = [() => LO[lw[0]].text(n, lo, ...lw.slice(1)), () => HI[hw[0]].text(n, hi, ...hw.slice(1))];
    // TODO: readout reason by Fable 5.2 (2026-11-11, [SYC]), of an ifsym cell; says the order above the column's bound under BGPW's Symmetry Conjecture is ruled out if that conjecture holds, naming the program that checks the proofs
    const ifwhy = () => `order ${IFHI[n - 1] + 1} ruled out if the Symmetry Conjecture holds (${D.ifsym.find(e => e[0] === n)[2]})`;
    const rings = RINGS.filter(r => r.key === n && r.r === m);      // none or one
    swatch.className = `swatch ${kind}`;
    swatch.classList.toggle('record', rings.length > 0);
    swatch.classList.toggle('proven', rings.some(r => r.role === 3));
    return [swatch, nw(el('i', '', 'n'), ` = ${n}, `, el('i', '', 'm'), ` = ${m}`), ' · ', bounds(n), ' · ',
      ...subbed({exists: [why[0]], open: why, impossible: [why[1]], ifsym: [...why, ifwhy]}[kind].map(f => f()).join(' · ')), ...rings.map(r => ` · ${NOTES[r.role](m)}`)];
  }
  // What the readout says of the target read out, by its kind (since 2026-11-19, when a hover on a strip came to read out
  // its column or its row, what a click there opens): a cell's n and m, bounds, reasons and ring's note; a column's n and
  // bounds, and a row's m, as their boxes' headings have them
  const READS = {exists: cellOut, open: cellOut, impossible: cellOut, ifsym: cellOut,
                column: n => [nw(el('i', '', 'n'), ` = ${n}`), ' · ', bounds(n)], row: (n, m) => [nw(el('i', '', 'm'), ` = ${m}`)]};
  // What a box shows: its heading and its parts, by the target's kind, and its length, a row's none (since 2026-11-18)
  const box = (n, m, kind, keys) => ({heading: HEADINGS[kind](n, m), length: kind === 'row' ? null : BigInt(n), ...SAYS[kind](n, m, keys)});
  const chart = gridChart({cv, ro, panel, zoomIn: document.getElementById('mstar-zoom-in'), zoomOut: document.getElementById('mstar-zoom-out'),
    caps: document.querySelectorAll('#mstar-caps button'), last: D.nmax, columns, rowsOf, rings: RINGS, nrow: D.mtop,
    letters: ['n', 'm'], reads: READS, box, fragment: (n, m) => `${n === null ? '' : `n${n}`}${m === null ? '' : `m${m}`}`});
  OMIT.forEach(o => o.box.addEventListener('change', () => chart.recolumn(o.box)));   // a box of the list changes the columns ([COM])
} catch (e) {
  fail(e);
}
})();
