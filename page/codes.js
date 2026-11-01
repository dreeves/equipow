// The page's codes and joins as buttons (dreeves's spec [REO] in index.html, item 2, 2026-10-31: "When you click the hex
// code, we expand it to an explicit partition and check the arithmetic so show exactly which exponents are
// equipowerful"; and later that day, as the page's sets left it: "every bipartition we give should be presented the
// same way as an expandable hex code"): a click on a code (<code id="N:M">, N its length and M its order, in a code
// block or in a sentence) or on a join of codes (data-join, the ids of codes separated by spaces, and data-order, its
// order M), or Enter or Space while it has the focus, shows its partition right below it, and the next one hides it.
// The partition, from template[data-partition], is the two parts, the positions i with f_i = +1 and with f_i = -1, and
// their power sums, the sum of i^k over each part for k = 0 to M, in BigInt, so exact: for each k two rows, the first
// part's sum over the second's, in one column, so that equal sums line up digit for digit and wrap alike where the
// column is narrow, with k and the mark = or ≠ beside both (cells data-k, data-relation, data-sum "+1" and "-1").  It
// is made at the first click and then kept.  Every word it shows is in the template; this script writes numbers and
// the marks = and ≠.  A code's signs are overnight_v5.from_hex's, as mstar.py reads the page's codes (BGPW's Table 5
// convention): each hex digit's four bits, the most significant first, 1 as +1 and 0 as -1, make the left half, and
// the right half is the left half reversed, times (-1)^M.  A join's signs are its codes' one after the other, as the
// page's join puts them (f ∨ g = f(x) + x^{n_f} g(x)).  It throws, as the page loads, on a code's id other than N:M,
// a code other than hex digits, an N other than 8 times its number of digits, or a join of an id that no code has, and,
// at each click, on power sums other than order exactly M's (equal below M, unequal at M), showing nothing: each is a
// claim of the page.
(() => {
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };
  const template = document.querySelector('template[data-partition]').content.firstElementChild;
  const signs = (hex, m) => {                                      // a code's signs f_0, f_1, ..., +1 or -1
    const left = [...hex].flatMap(d => [...parseInt(d, 16).toString(2).padStart(4, '0')].map(b => 2 * Number(b) - 1));
    return [...left, ...left.toReversed().map(t => (-1) ** m * t)];
  };
  // An element's order and signs: a code's M and its digits' signs; a join's data-order and its codes' signs, one
  // after the other
  function sequence(e) {
    if ('join' in e.dataset) {
      const codes = e.dataset.join.split(' ').map(id => document.querySelector(`code[id="${id}"]`));
      assert(/^\d+$/.test(e.dataset.order) && codes.every(Boolean), e.dataset.join, e.dataset.order);
      return [Number(e.dataset.order), codes.flatMap(c => sequence(c)[1])];
    }
    const [n, m] = e.id.split(':').map(Number);
    assert(/^\d+:\d+$/.test(e.id) && /^[0-9A-F]+$/.test(e.textContent) && n === 8 * e.textContent.length, e.id, e.textContent);
    return [m, signs(e.textContent, m)];
  }
  const cell = (tag, text, data, rowSpan) => {                    // a cell of the power sums
    const c = Object.assign(document.createElement(tag), {textContent: text, rowSpan});
    Object.assign(c.dataset, data);
    return c;
  };
  const sequences = new Map();                                     // each code and join: [its order, its signs]
  const partitions = new Map();                                    // each code and join: its partition, once made
  function partition(e) {                                          // made, hidden, right after e
    const [m, f] = sequences.get(e);
    const parts = [1, -1].map(s => [...f.keys()].filter(i => f[i] === s).map(i => BigInt(i)));
    const sums = Array.from({length: m + 1}, (_, k) => parts.map(p => p.reduce((s, i) => s + i ** BigInt(k), 0n)));
    assert(sums.every(([a, b], k) => (a === b) === (k < m)), e.id, e.dataset.join);
    const box = template.cloneNode(true);
    box.querySelector('[data-part="+1"]').textContent = parts[0].join(', ');
    box.querySelector('[data-part="-1"]').textContent = parts[1].join(', ');
    box.querySelector('[data-power-sums]').append(...sums.flatMap(([a, b], k) => {
      const first = document.createElement('tr'), second = document.createElement('tr');
      first.append(cell('th', k, {k}, 2), cell('td', a === b ? '=' : '≠', {relation: ''}, 2), cell('td', a, {sum: '+1'}, 1));
      second.append(cell('td', b, {sum: '-1'}, 1));
      return [first, second];
    }));
    box.hidden = true;
    e.after(box);
    partitions.set(e, box);
    return box;
  }
  function toggle(e) {
    const box = partitions.get(e) ?? partition(e);
    box.hidden = !box.hidden;
    e.setAttribute('aria-expanded', String(!box.hidden));
  }
  for (const e of document.querySelectorAll('code[id], [data-join]')) {
    sequences.set(e, sequence(e));
    e.setAttribute('role', 'button');
    e.tabIndex = 0;
    e.setAttribute('aria-expanded', 'false');
    e.addEventListener('click', () => toggle(e));
    e.addEventListener('keydown', ev => {                          // Enter and Space, as a button takes them
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      ev.preventDefault();                                         // Space would scroll the page
      toggle(e);
    });
  }
})();
