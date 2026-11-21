// The appendix (Opus 5.5, 2026-11-18; dreeves: "how about an appendix section right above Search Progress: Appendix:
// Everything Known About Every Length ... move that section to the appendix, default collapsed, and extend and
// consitent-ify it so that the title of the appendix is true. this means we want an entry for every n from 1 thru 2048,
// plus 2^12 thru 2^72. combine entries for odd n since there's literally no witness for any odd n and the proof that
// m*(n)=0 is exactly the same for all odd n", and "part of the point of having everything fully spelled out in the
// appendix is so that you can grep for anything on the page"), made as the page loads, so that find in page reaches
// every entry: after both charts' scripts have registered their facts (FACTS, page/shared.js), and before page/codes.js
// makes the page's codes and constructions buttons.
//
// Its lengths are every n of the m*(n) chart, each length past it that the page has a sequence of (MSTAR.past, since
// 2026-11-19; dreeves, of the parts p_N past the chart that linked to their codes in the Symmetry section: "yes, full
// anti-magic, add the new entries"), and each 2^k past it to the powers-of-2 chart's last; the chart whose data covers a
// length gives its name, its bounds and its facts (SOURCES: the m*(n) chart's rows, mstarRows, and the powers of 2).  Their entries, in order of their first lengths:
// one entry for each class of CLASSES, its facts stated for any of its lengths at once; the entries written by hand,
// the li of the list, each of the lengths its heading lists (listed); and an entry made here for every other length,
// headed by its length and its bounds, as a column's box is.  Each entry gets, right after its heading, the facts of each
// of its lengths in turn (a class's once), each part marked data-n with its length (a class's key), its Claude's English
// quoted (quoteRuns), and less the copies of codes that the entry holds itself, as a box left them out; then each is
// entered (enter), so that a box can show it.  It throws, showing nothing, on a length of a class whose data the class
// does not bear out, on an entry by hand of a length outside the appendix's or of a class, and (enter) on two entries of
// a length.
(() => {
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what, (_, v) => typeof v === 'bigint' ? `${v}` : v).replace(/"/g, "'")); };
  const list = document.querySelector('section.appendix ul.entries');
  assert(['mstar', 'pow2'].every(c => FACTS[c] !== undefined), 'the facts of each chart', Object.keys(FACTS));   // a chart's script stopped
  const nmax = BigInt(MSTAR.nmax);
  // each length's source, by the data that covers it (a Map since 2026-11-19; a test of n <= nmax until then): the m*(n)
  // chart's for each of its rows, its columns' and past's, and the powers-of-2 chart's for each 2^k past nmax
  const mstar = [...mstarRows()].map(([n, c]) => [BigInt(n), {name: `${n}`, cols: c,
    facts: () => together(FACTS.mstar.witness(n), FACTS.mstar.proof(n), ...FACTS.mstar.ifproofs(n))}]);
  const pow2 = Array.from({length: POW2.kmax}, (_, i) => i + 1).filter(k => 2n ** BigInt(k) > nmax).map(k => [2n ** BigInt(k),
    {name: `2^{${k}}`, cols: POW2.cols[k - 1], facts: () => together(FACTS.pow2.witness(k), FACTS.pow2.proof(k))}]);
  // A length of both charts is a power of 2 past nmax that the page has a sequence of (2^13 since 2026-11-21, Fable 5.2; until then the two lists were
  // asserted to share no length): the powers-of-2 chart is its source, as of every power of 2 past nmax (the later of two entries of a Map stands), its
  // witness there naming the sequence, p_N, whose code the m*(n) chart's row holds.  Its place among the lengths is its size's (the lengths were the two
  // lists in turn until then).
  const SOURCES = new Map([...mstar, ...pow2]);
  const lengths = [...SOURCES.keys()].sort((a, b) => Number(a - b)), source = n => SOURCES.get(n);
  const made = heading => {
    const li = document.createElement('li'), p = Object.assign(document.createElement('p'), {className: 'entry', textContent: heading});
    li.append(p);
    return li;
  };
  const headed = n => {                                            // \(n = N\): and its bounds, as a column's box heads them
    const {name, cols: [lo, hi]} = source(n);
    return `\\(n = ${name}\\):  \\(${lo === hi ? `m^* = ${lo}` : `${lo} \\le m^* \\le ${hi}`}\\)`;
  };

  // The classes of lengths that share one entry, whose facts hold at every length of the class, stated for any n, which
  // every length's data must bear out (holds: its bounds and the kind of its upper bound's reason).  The odd n (dreeves:
  // "combine entries for odd n since there's literally no witness for any odd n and the proof that m*(n)=0 is exactly
  // the same for all odd n"): order 0 and n odd.  The singly even n, n = 2 mod 4 (dreeves, that afternoon: "odd multiples
  // of 2 are all essentially the same: same exact proof that the order is 1 (yes?) and the witness ... is just any
  // bipartition with 2 equal-sized sets"): order 1, its witness alternating signs (the data's own, a join or an example
  // per length, of no more order, gives way to it), and the 2-adic bound at t = 1, n = 2^1 u.
  const CLASSES = [
    {key: 'odd', of: n => n % 2n === 1n, heading: '\\(n \\equiv 1 \\pmod 2\\):  \\(m^* = 0\\)',
     holds: ([lo, hi, lw, hw]) => lo === 0 && hi === 0 && lw[0] === 'none' && hw[0] === 'odd', facts: () => PROOF.odd(1n, 'n', 0).parts},
    {key: 'singly-even', of: n => n % 4n === 2n, heading: '\\(n \\equiv 2 \\pmod 4\\):  \\(m^* = 1\\)',
     holds: ([lo, hi, , hw]) => lo === 1 && hi === 1 && hw[0] === 'two',
     facts: () => [filled('witness-alternating', {bound: bound('n', 'ge', 1)}), twoPart('n', 1, 2n, 'u', 1)]},
  ];
  const byHand = new Map();                                        // each length an entry by hand lists: [its li, its lengths]
  for (const p of list.querySelectorAll(':scope > li > p.entry')) {
    const ns = listed(p);
    ns.forEach(n => assert(lengths.includes(n) && !byHand.has(`${n}`) && !CLASSES.some(c => c.of(n)), 'by hand', n));
    ns.forEach(n => byHand.set(`${n}`, [p.parentElement, ns]));
  }
  // [li, lengths, [[the length's data-n, its facts' parts], ...]], in order of first length
  const order = CLASSES.map(c => {
    const ns = lengths.filter(c.of);
    ns.forEach(n => assert(c.holds(source(n).cols), c.key, n, source(n).cols));
    return [made(c.heading), ns, [[c.key, c.facts()]]];
  });
  for (const n of lengths.filter(n => !CLASSES.some(c => c.of(n)))) {
    const [li, ns] = byHand.get(`${n}`) ?? [made(headed(n)), [n]];
    if (ns[0] === n) order.push([li, ns, ns.map(x => [`${x}`, source(x).facts().parts])]);   // at its first length
  }
  order.sort(([, a], [, b]) => (a[0] > b[0]) - (a[0] < b[0]));
  assert(order.reduce((s, [, ns]) => s + ns.length, 0) === lengths.length, 'each length in one entry');
  for (const [li, ns, facts] of order) {
    const kept = facts.flatMap(([n, parts]) => parts.map(part => {
      part.dataset.n = n;
      return part;
    }));
    dropHeld(kept, new Set([...li.querySelectorAll('code[id]')].map(c => c.id)));   // the entry's own codes once
    quoteRuns(kept);                                               // one quote per run of the entry's facts, as a box's parts had
    li.querySelector(':scope > p.entry').after(...kept);
    list.append(li);
    enter(li, ns);
  }
  // KaTeX draws the entries' math when the appendix first opens (page/math.js), by a click or by find in page
  list.closest('details').addEventListener('toggle', () => renderMathInElement(list, MATH), {once: true});
})();
