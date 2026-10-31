// Claude's table of the smallest length known for each order (Stan Wagon's suggestion, 2026-10-17), from mstar.js: for
// order m, the least n whose lower bound is at least m (a sequence of order m is known) and the least n whose upper
// bound is (order m is not ruled out), proven smallest when the two agree; orders from 1 to the largest some n up to
// MSTAR.nmax is not ruled out for, — where no length is known (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the
// chart?").
(() => {
  const cell = text => Object.assign(document.createElement('td'), {textContent: text});
  const knownAt = [], possibleAt = [];                             // order m: its least n known, its least n not ruled out
  raised(MSTAR.cols, () => 0).forEach(([known, possible], i) => {
    known.forEach(m => { knownAt[m] = i + 1; });
    possible.forEach(m => { possibleAt[m] = i + 1; });
  });
  const rows = possibleAt.slice(1).map((possible, j) => {
    const m = j + 1, known = knownAt[m] ?? '—', row = document.createElement('tr');   // — where no length is known
    row.append(cell(m), cell(known), cell(known === possible ? '✓' : ''), cell(possible));
    return row;
  });
  document.querySelector('[data-smallest]').replaceChildren(...rows);
})();
