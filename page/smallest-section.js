// Claude's table of the smallest length known for each order (Stan Wagon's suggestion, 2026-10-17), from mstar.js: for
// order m, the least length known to reach m, best[m], and the least n whose upper bound is at least m (order m is not
// ruled out), proven smallest when the two agree; orders from 1 to the largest some n up to MSTAR.nmax is not ruled out
// for (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the chart?").  best[m] is the least n whose lower bound is
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
  const best = [];                                                 // Infinity stands for knownAt's missing n, the least of none
  possibleAt.forEach((_, m) => { best[m] = Math.min(knownAt[m] ?? Infinity, ...best.slice(1, m).map((b, j) => b * best[m - 1 - j])); });
  if (!best.slice(1).every(Number.isFinite)) throw new Error(JSON.stringify(best));   // best[1] is 2 (the data contract's m*(2) = 1)
  const rows = possibleAt.slice(1).map((possible, j) => {
    const m = j + 1, row = document.createElement('tr');
    row.append(cell(m), cell(best[m]), cell(best[m] === possible ? '✓' : ''), cell(possible));
    return row;
  });
  document.querySelector('[data-smallest]').replaceChildren(...rows);
})();
