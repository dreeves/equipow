// Claude's table of the smallest length known for each order (Stan Wagon's suggestion, 2026-10-17), from mstar.js: for
// order m, the least length known to reach m, best[m], and the least n whose upper bound is at least m (order m is not
// ruled out), proven smallest when the two agree; orders from 1 to the largest some n up to MSTAR.nmax is not ruled out
// for (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the chart?"), and one more (2026-11-03, [LIN]).  best[m] is the least n whose lower bound is
// at least m, or the product of two lesser orders' best lengths where that is less, since f(x) g(x^n), n the length of
// f, has order at least the sum of theirs (dreeves's README, 2026-10-31: "[MIN] In the "smallest length known for each
// order" table, we currently have no entries for the smallest known n for orders 14 and 15"; the table showed — where
// no n up to MSTAR.nmax was known to reach m).
(() => {
  const cell = text => Object.assign(document.createElement('td'), {textContent: text});
  const knownAt = [], possibleAt = [];                             // order m: its least n known, its least n not ruled out
  raised(MSTAR.cols, () => 0).forEach(([known, possible], i) => {
    known.forEach(m => { knownAt[m] = i + 1; });
    possible.forEach(m => { possibleAt[m] = i + 1; });
  });
  // One order more than the largest some n up to MSTAR.nmax allows, which only an n past the chart can reach (dreeves's
  // README, 2026-11-03: "[LIN] Add one more line for m=16 to the "smallest length known for each order" table").
  const best = [];                                                 // Infinity stands for knownAt's missing n, the least of none
  for (let m = 1; m <= possibleAt.length; m++) best[m] = Math.min(knownAt[m] ?? Infinity, ...best.slice(1, m).map((b, j) => b * best[m - 1 - j]));
  if (!best.slice(1).every(Number.isFinite)) throw new Error(JSON.stringify(best));   // best[1] is 2 (the data contract's m*(2) = 1)
  const rows = best.slice(1).map((known, j) => {
    const m = j + 1, row = document.createElement('tr');
    // in the chart's order, the n not ruled out before the n known, the check mark last (dreeves's README, 2026-10-31:
    // "[FLP] I think the smallest-known and smallest-not-ruled-out columns should be swapped, so the numbers in that
    // table are in the same order they're in in the chart. And then I think the checkmarks should be the last column")
    row.append(cell(m), cell(possibleAt[m] ?? `> ${MSTAR.nmax}`), cell(known), cell(known === possibleAt[m] ? '✓' : ''));
    return row;
  });
  document.querySelector('[data-smallest]').replaceChildren(...rows);
})();
