// Claude's chart of the bounds on m*(2^k) − k for k up to K = POW2.kmax (72 until 2026-11-23), drawn from POW2, which pow2.js defines (pow2.py makes
// it and states its contract).  Column k is n = 2^k; row e is order k + e, an excess of e over Thue–Morse's order k.
// Cell (k, e) is green (exists) when k + e <= lo, gray (open) when lo < k + e <= hi, and red (impossible) above; its rows
// follow the view, up to row E = POW2.etop at the full view.  page/shared.js draws it as it draws the m*(n) chart
// (gridChart, since 2026-11-23; dreeves: "please DRY up as much as possible between the 2 figures", and "figure 2
// loses the automatic y-axis zooming that figure 1 has"; until then one svg with a rect per cell, E rows of 14 px, and
// its own rings, labels and tags): this script holds its data's contract, its columns and rows, and what its readout
// and its boxes say.
(() => {
const cv = document.getElementById('pow2-chart'), ro = document.getElementById('pow2-readout');
const fail = chartFail(ro);                                       // loudly: in the readout, and uncaught
try {
  const D = POW2, K = D.kmax;                                     // K a constant 72 until 2026-11-23 (dreeves: "it never made sense to hard-code 72")
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
  // the m*(n) chart, or one of LONG, the sequences past the chart, as [n, m]: mstar.js's past, the Symmetry section's
  // codes longer than NMAX (Opus 5.5, 2026-11-19, when joins first used them, 2096, 2528 and 2608; an empty list here
  // from 2026-10-27, when the m*(n) chart reached the one example there was, at 1024).  name gives its symbol in the
  // readout, and '' for anything else, which the contract rules out: f, the 2^24 construction of the remarks below,
  // among them since 2026-10-29 (dreeves: "ok", to dropping f, which no reason had used since 2026-10-25).
  const NMAX = MSTAR.nmax;                                          // the m*(n) chart's last n, as its data have it (1024, a number here, until 2026-11-10: 2048 since, [BOU])
  const LONG = MSTAR.past.map(([n, m]) => [n, m]);
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
  // expands into its derivation; and the proof of an upper bound worked out for 2^k, of each reason that can stand past
  // the m*(n) chart's last n (a box of a 2^k up to it shows that chart's facts: mstar has no proof here).
  const blockTex = ([n, m]) => n === 2 ** m ? `\\tau_{${m}}` : `p_{${n}}`;
  const LO = {
    'thue-morse': {
      ok: (k, lo) => lo === k,
      // readout reason; says order lo, which is k, is known from Thue–Morse, τ_k
      text: (k, lo) => `order ${lo} from Thue–Morse, τ${sub(k)}`,
      witness: (k, lo) => shown([filled('witness-thue-morse', {bound: bound(`2^{${k}}`, 'ge', lo), tau: `\\(\\tau_{${k}}\\)`, codes: copies(2n ** BigInt(k), lo)})]),
    },
    joins: {
      ok: (k, lo, ps) => Array.isArray(ps) && ps.length >= 1 && ps.every(p => Array.isArray(p) && p.length >= 1
        && p.every(isBlock)) && ps.reduce((t, p) => t + length(p), 0n) === 2n ** BigInt(k)
        && lo === Math.min(...ps.map(order)),
      // readout reason; says order lo is known from the join of these expanded products
      text: (k, lo, ps) => `order ${lo} from the join ${joined(ps)}`,
      witness: (k, lo, ps) => construction(2n ** BigInt(k), `2^{${k}}`, lo,
        ps.map(p => `(${p.map(blockTex).join(' \\mathbin{\\#} ')})`).join(' \\vee '), copies(2n ** BigInt(k), lo)),
    },
  };
  // The m*(n) chart's reasons of an upper bound at an even n, copied from its script, each its check and its words for
  // the readout: the reasons of ["mstar", why], 2^k <= NMAX.  No proof: a box of such a 2^k shows the m*(n) chart's
  // facts (FACTS.mstar, below), since 2026-11-18.
  const MSTAR_HI = {
    two: {
      ok: (n, hi) => n % 2 === 0 && hi === (n & -n) - 1,
      // readout reason; says order hi + 1 is ruled out because hi + 1 is the largest power of 2 dividing n
      text: (n, hi) => `order ${hi + 1} ruled out: ${hi + 1} is the power of 2 in ${n}`,
    },
    norm: {
      ok: (n, hi, p) => Number.isInteger(p) && prime(p) && n % p !== 0,
      // readout reason; says order hi + 1 is ruled out by the norm bound for the prime p
      text: (n, hi, p) => `order ${hi + 1} ruled out by the norm bound for p\u00a0=\u00a0${p}`,
    },
    residue: {
      ok: (n, hi, M) => Number.isInteger(M) && M >= 2,
      // readout reason; says order hi + 1 is ruled out by the residue condition mod M
      text: (n, hi, M) => `order ${hi + 1} ruled out by the residue condition mod ${M}`,
    },
    table2: {
      ok: (n, hi) => n % 8 === 0 && n <= 304,
      // readout reason; says order hi + 1 is ruled out by BGPW's Table 2
      text: (n, hi) => `order ${hi + 1} ruled out by BGPW's Table 2`,
    },
    page: {
      ok: (n, hi, who) => credit(who).length === 1,              // who is a class of the new results' cells, which their legend words
      // readout reason; says order hi + 1 is ruled out in this page's new results, naming whose they are
      text: (n, hi, who) => `order ${hi + 1} ruled out in the new results above (${credit(who)[0]})`,
    },
  };
  const HI = {
    mstar: {
      ok: (k, hi, why) => 2 ** k <= NMAX && Array.isArray(why) && Object.hasOwn(MSTAR_HI, why[0])
        && MSTAR_HI[why[0]].ok.length === why.length + 1 && MSTAR_HI[why[0]].ok(2 ** k, hi, ...why.slice(1)),
      text: (k, hi, why) => MSTAR_HI[why[0]].text(2 ** k, hi, ...why.slice(1)),
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
      proof: (k, hi, chain) => PROOF.residue(2n ** BigInt(k), `2^{${k}}`, hi, 'pagegen/pow2.py', ...chain),
    },
  };
  assert(Object.keys(D).sort().join() === 'cols,etop,kmax', Object.keys(D));
  assert(Number.isInteger(K) && K >= 1 && Array.isArray(D.cols) && D.cols.length === K && Number.isInteger(D.etop), D.kmax, D.etop);
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

  const E = D.etop;
  const rowsOf = k => [D.cols[k - 1][0] - k, D.cols[k - 1][1] - k, D.cols[k - 1][1] - k];   // a column's bounds in rows, which are excesses δ = m − k
  const kindOf = (k, e) => cellKind(rowsOf(k), e);
  const MEANING = {exists: 'known', open: 'open', impossible: 'impossible'};   // what a cell of each kind says, in the readout (dreeves's words)
  const swatch = el('span', '', '');
  // The smallest cells of each row, ringed in gold just outside them as the m*(n) chart rings its own (dreeves's README,
  // 2026-10-28: "[GTR] Gold trim for the powers-of-2 chart to highlight the values in the theorem"; then 2026-10-30:
  // "[GLT] ... match the "smallest length known" table: green+gold is the smallest *known* n (resp. 2^k) for a give m
  // (resp. delta) and black+gold is the smallest n (resp. 2^k) not ruled out"): for each record gap g, [k, g, role] for
  // the least k with lo >= k + g, a bound the theorem states (the table below has the same), and the least k with
  // hi >= k + g, one cell when they agree; role 1 known, 2 not ruled out, 3 both, proven the least, which also gets a
  // gold dot (Claude's proposal for the indicator, 2026-10-30); a ringed cell's swatch in the readout is ringed too, with a
  // note (dreeves, 2026-10-28: "don't forget the gold trim on the hover version"), as the m*(n) chart's readout does.
  const RINGS = raised(D.cols, j => j + 1).flatMap(([known, possible], j) => [...new Set([...known, ...possible])]
    .sort((x, y) => x - y).map(g => ({key: j + 1, r: g, role: known.includes(g) + 2 * possible.includes(g)})));   // the rows k raises
  // readout note on a cell ringed in gold; says 2^k is the least power of 2 known to beat Thue–Morse by δ, a bound the theorem below states
  const knownNote = e => `the smallest k known to beat Thue–Morse by ${e} (see theorem below)`;
  const NOTES = {1: [knownNote],                                   // the readout's notes on a ringed cell, by its role
    // Readout note on a black cell ringed in gold; says its k is the least whose upper bound allows beating Thue–Morse by δ
    2: [e => `the smallest k not ruled out to beat Thue–Morse by ${e}`],
    // Readout note on a cell dotted in gold; says no smaller k beats Thue–Morse by δ, as proven
    3: [knownNote, e => `proven as the smallest k to beat Thue–Morse by ${e}`]};
  const two = k => ['2', el('sup', '', String(k))];                // 2^k
  const kn = k => [el('i', '', 'k'), ` = ${k}, `, el('i', '', 'n'), ' = ', ...two(k)];   // k = K, n = 2^K
  const bounds = k => { const [lo, hi] = D.cols[k - 1]; return nw(`${lo} ≤ `, el('i', '', 'm'), el('sup', '', '*'), '(', ...two(k), `) ≤ ${hi}`); };
  function cellOut(k, e) {                                         // the readout of the cell of k and e
    const [lo, hi, lw, hw] = D.cols[k - 1], kind = kindOf(k, e);
    const gold = RINGS.filter(r => r.key === k && r.r === e);       // none or one
    const why = [() => LO[lw[0]].text(k, lo, ...lw.slice(1)), () => HI[hw[0]].text(k, hi, ...hw.slice(1))];
    swatch.className = `swatch ${kind}`;
    swatch.classList.toggle('record', gold.length > 0);
    swatch.classList.toggle('proven', gold.some(r => r.role === 3));
    return [swatch, nw(...kn(k), ', ', el('i', '', 'm'), ` = ${k} + ${e} = ${k + e}`), ' · ', MEANING[kind], ' · ', bounds(k),
      ' · ', ...subbed({exists: [why[0]], open: why, impossible: [why[1]]}[kind].map(f => f()).join(' · ')), ...gold.flatMap(r => NOTES[r.role].map(f => ` · ${f(e)}`))];
  }
  // What the readout says of the target read out, by its kind (since 2026-11-19, when a hover on a strip came to read out
  // its column or its row, what a click there opens): a cell's k, n and m, meaning, bounds, reasons and ring's notes; a
  // column's k, n and bounds, and a row's δ, as their boxes' headings have them
  const READS = {exists: cellOut, open: cellOut, impossible: cellOut,
                column: k => [nw(...kn(k)), ' · ', bounds(k)], row: (k, e) => [nw(el('i', '', 'δ'), ` = ${e}`)]};
  // The boxes under the chart (chartPanel, in page/shared.js), as the m*(n) chart's: the target [c, e] is the cell of
  // column c, k = c + 1, and row e, order k + e; [c, null] the column, at its k label; [null, e] the row, at its δ
  // label; their fragments kK, dD and kKdD.  A cell's box and a column's show what the m*(n) chart's do: a cell's its
  // facts by its kind, with the searches at n = 2^k and m = k + e for a black one; a column's the entry of n = 2^k in the
  // appendix (since 2026-11-18); the facts the m*(n) chart's up to its last n (FACTS.mstar) and this chart's past it
  // (FACTS.pow2, below); a row's (e), the legend's words for each gold-ringed cell of the row, with its k, linked to
  // its cell's box: the least k known to beat Thue–Morse by e and the least not ruled out to, or the one cell, proven,
  // where they agree; and, where e is a record gap, its row of the table of record gaps, under that table's own head
  // (recordGaps, below; the main session's design of 2026-11-04 for [ROC], whose rows dreeves named for the m*(n) chart).
  const legend = [...cv.closest('section').querySelectorAll('.legend li')];
  const witness = k => { const [lo, , lw] = D.cols[k - 1]; return LO[lw[0]].witness(k, lo, ...lw.slice(1)); };
  const proof = k => { const [, hi, , hw] = D.cols[k - 1]; return HI[hw[0]].proof(k, hi, ...hw.slice(1)); };
  const rowBox = e => shown([...RINGS.filter(r => r.r === e).map(({key: k, role}) => filled('row-cell',
    {item: legendItem(legend, ['', 'exists', 'open', 'exists'][role], role), at: linked(`#k${k}d${e}`, `\\(k = ${k}\\)`)})),
    ...recordGaps().slice(e - 1, e).map(body => {
      const part = filled('row-gaps', {});
      part.querySelector('table').append(document.querySelector('[data-record-gaps] thead').cloneNode(true), body);
      return part;
    })]);
  FACTS.pow2 = {witness, proof};
  // a cell's facts are those of the length 2^k: the m*(n) chart's up to its last n, this chart's past it, as the
  // appendix's entries have them (page/appendix.js)
  const facts = k => 2 ** k <= MSTAR.nmax ? [FACTS.mstar, 2 ** k] : [FACTS.pow2, k];
  const factWitness = k => { const [F, x] = facts(k); return F.witness(x); }, factProof = k => { const [F, x] = facts(k); return F.proof(x); };
  const SAYS = {exists: factWitness, impossible: factProof, open: (k, e) => together(factWitness(k), factProof(k), searches(2n ** BigInt(k), k + e)),
                column: k => shown([], [2n ** BigInt(k)]), row: (k, e) => rowBox(e)};
  const cell = (k, e) => {
    const [swatch, ...words] = legendItem(legend, kindOf(k, e), Math.max(0, ...RINGS.filter(r => r.key === k && r.r === e).map(r => r.role)));
    return [swatch, linked(`#k${k}`, `\\(k = ${k}\\)`), ', ', linked(`#d${e}`, `\\(\\delta = ${e}\\)`), ': ', ...words];
  };
  const HEADINGS = {exists: cell, open: cell, impossible: cell, row: (k, e) => [`\\(\\delta = ${e}\\)`], column: k => {
    const [lo, hi] = D.cols[k - 1];
    return [`\\(k = ${k}\\)`, ', ', `\\(n = 2^{${k}}\\)`, ': ', `\\(${lo === hi ? `m^*(2^{${k}}) = ${lo}` : `${lo} \\le m^*(2^{${k}}) \\le ${hi}`}\\)`];
  }};
  // What a box shows: its heading and its parts, by the target's kind, and its length, a row's none (since 2026-11-18)
  const box = (k, e, kind) => ({heading: HEADINGS[kind](k, e), length: kind === 'row' ? null : 2n ** BigInt(k), ...SAYS[kind](k, e)});
  gridChart({cv, ro, panel: document.getElementById('pow2-panel'), zoomIn: document.getElementById('pow2-zoom-in'),
    zoomOut: document.getElementById('pow2-zoom-out'), caps: document.querySelectorAll('#pow2-caps button'), last: K,
    columns: cap => Array.from({length: cap}, (_, i) => i + 1), rowsOf, rings: RINGS, nrow: E, letters: ['k', 'δ'], reads: READS, box,
    fragment: (k, e) => `${k === null ? '' : `k${k}`}${e === null ? '' : `d${e}`}`});
} catch (e) {
  fail(e);
}
})();
// Claude's table of the construction behind each inequality of the theorem (Stan Wagon's table, extended, 2026-10-18;
// record_gaps.wl makes the same one in Mathematica), from POW2: for each record gap g = 1, 2, ..., the least k whose lo
// is at least k + g, and its reason as a join of products of blocks (JOIN), each record gap a tbody of its own, which
// recordGaps() gives, in order (since 2026-11-04 a function, as a row's box of the chart above shows one of them).  A
// product is a row: its blocks ascending by length, a repeated one written once, as a power (368²) in the power of 2
// and as count·order (2·9) in the order; a + before every product but the first; the bound's cell spans its rows.
function recordGaps() {
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
