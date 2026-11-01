// The page's codes, joins and constructions as buttons (dreeves's spec [REO] in index.html, item 2, 2026-10-31: "When
// you click the hex code, we expand it to an explicit partition and check the arithmetic so show exactly which exponents
// are equipowerful"; later that day, as the page's sets left it: "every bipartition we give should be presented the
// same way as an expandable hex code"; and then, agreeing that the page's construction formulas be clickable like codes
// and expand into their derivation: "i think so? maybe show me a before/after screenshot if there's any doubt?"): a
// click on one, or Enter or Space while it has the focus, shows its box below it, right after the block that holds it
// (the buttons, below), and the next one hides it.  The box is made at the first click and then kept.  Every word a box shows is in its template, but the label of an example
// that a derivation cites, which is mstar.js's; this script writes names, numbers and the signs of arithmetic.  Each
// throws, showing nothing, on a claim of the page that it finds false.
//
// A code is <code id="N:M">, N its length and M its order, in a code block or in a sentence; a join of codes is
// data-join, the ids of codes separated by spaces, with data-order, its order M.  Its box, from
// template[data-partition], is its partition: the two parts, the positions i with f_i = +1 and with f_i = -1, and their
// power sums, the sum of i^k over each part for k = 0 to M, in BigInt, so exact: for each k two rows, the first part's
// sum over the second's, in one column, so that equal sums line up digit for digit and wrap alike where the column is
// narrow, with k and the mark = or ≠ beside both (cells data-k, data-relation, data-sum "+1" and "-1").  A code's signs
// are overnight_v5.from_hex's, as mstar.py reads the page's codes (BGPW's Table 5 convention): each hex digit's four
// bits, the most significant first, 1 as +1 and 0 as -1, make the left half, and the right half is the left half
// reversed, times (-1)^M.  A join's signs are its codes' one after the other, as the page's join puts them
// (f ∨ g = f(x) + x^{n_f} g(x)).  It throws, as the page loads, on a code's id other than N:M, a code other than hex
// digits, an N other than 8 times its number of digits, or a join of an id that no code has, and, at a click, on power
// sums other than order exactly M's (equal below M, unequal at M).
//
// A construction is data-construction, "N:M", the length N and the order M that the page states for its formula, a
// formula over sequences in the page's math: names joined by # (\mathbin{\#}) or ∨ (\vee), one of the two in each pair
// of parentheses, and, in front, a name and = or nothing (the name names it).  Its box, from template[data-derivation], is its
// derivation: a row per step, each part and then the product or join that uses it, with its length n and order m
// (rows data-n and data-m), the whole formula last, and below them the bound m*(N) ≥ M.  A part p_N is the best known
// sequence of length N, as the powers-of-2 chart's caption says: its order is mstar.js's lower bound at N, and its row
// links to its code on the page, <code id="N:M">, or, when the page does not show that code, cites mstar.js's label of
// the example; τ_j is Thue–Morse, of length 2^j and order j; a letter is the construction of the page that names it,
// whose row links to it (the construction takes the letter as its id).  A product multiplies its parts' lengths and adds
// their orders; a join adds the lengths and has the least of the orders (its order is at least that: (x - 1)^m divides
// f ∨ g when it divides f and g).  It throws, as the page loads, on a formula outside that form or a letter that two
// constructions name, and, at a click, on a name it cannot resolve, a construction that depends on itself, and a
// derivation whose length and order are not N:M.  As a code's, a construction's form is checked as the page loads
// (its TeX is read then, before KaTeX draws it) and its arithmetic at its first click, which reads mstar.js.
(() => {
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };
  const el = (tag, ...children) => { const x = document.createElement(tag); x.append(...children); return x; };

  // ---------- codes and joins ----------
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
  function partition(e, [m, f]) {                                  // e's box: its partition
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
    return box;
  }

  // ---------- constructions ----------
  const steps = document.querySelector('template[data-derivation]').content;
  const THUE_MORSE = steps.querySelector('[data-thue-morse]').textContent;     // what a part τ_j cites
  const OPERATORS = {'\\mathbin{\\#}': '#', '\\vee': '∨'};
  // A token that names a sequence, as a part: [p, N] for p_{N} (N a BigInt), [tau, j] for \tau_j, [name, x] for a
  // letter x (not p)
  const named = (t, claim) => {
    const x = /^(?:p_\{(\d+)\}|\\tau_(\d)|\\tau_\{(\d+)\}|([a-oq-z]))$/.exec(t);
    assert(x !== null, claim, t);
    return x[1] ? ['p', BigInt(x[1])] : x[4] ? ['name', x[4]] : ['tau', Number(x[2] ?? x[3])];
  };
  // A construction's formula, parsed: [the token of the name before =, or null; its tree], the tree an operation,
  // [# or ∨, its operands], each operand a part or an operation in parentheses
  function parse(e) {
    const claim = e.dataset.construction, tex = /^\\\((.*)\\\)$/s.exec(e.textContent)?.[1];
    assert(/^\d+:\d+$/.test(claim) && tex !== undefined, claim, e.textContent);
    const ts = tex.match(/\\mathbin\{\\#\}|\\vee|[()=]|p_\{\d+\}|\\tau_\d|\\tau_\{\d+\}|[a-oq-z]|\S/g) ?? [];
    assert(ts.join('') === tex.replace(/\s+/g, ''), claim, tex);
    let i = ts[1] === '=' ? 2 : 0;
    const operand = () => {
      const t = ts[i++];
      if (t !== '(') return named(t, claim);
      const inner = operation();
      assert(ts[i++] === ')', claim, tex);
      return inner;
    };
    const operation = () => {                                      // operands joined by one operator, # or ∨
      const kids = [operand()], op = OPERATORS[ts[i]];
      while (i < ts.length && ts[i] !== ')') {
        assert(OPERATORS[ts[i++]] === op, claim, tex);             // # and ∨ meet only across parentheses
        kids.push(operand());
      }
      assert(op !== undefined && kids.length >= 2, claim, tex);
      return [op, kids];
    };
    const lhs = i ? (named(ts[0], claim), ts[0]) : null;           // the name before =, as written, checked as a name
    const tree = operation();
    assert(i === ts.length, claim, tex);
    return [lhs, tree];
  }
  // The rules: a product's length and order, and a join's, from their parts', and how a step writes them (a no-break
  // space after the commas of min and after =, so that a narrow column wraps before = and not inside min)
  const RULES = {
    '#': {n: ns => ns.reduce((a, b) => a * b), m: ms => ms.reduce((a, b) => a + b), ns: ' · ', ms: ms => ms.join(' + ')},
    '∨': {n: ns => ns.reduce((a, b) => a + b), m: ms => Math.min(...ms), ns: ' + ', ms: ms => `min(${ms.join(',\u00a0')})`},
  };
  const built = [...document.querySelectorAll('[data-construction]')];
  const parsed = new Map(built.map(e => [e, parse(e)]));          // as the page loads, before KaTeX draws them
  const naming = built.filter(e => parsed.get(e)[0] !== null);     // the constructions with a name before an =
  const defined = new Map(naming.map(e => [parsed.get(e)[0], e])); // each such name: its construction
  assert(defined.size === naming.length, naming.map(e => parsed.get(e)[0]));
  const sequences = new Map([...document.querySelectorAll('code[id], [data-join]')].map(e => [e, sequence(e)]));
  // The parts, by kind: their length n, order m, link (the href of the code or construction they are, or null) and
  // citation (the source they cite, or null)
  const PARTS = {
    p: (N, claim) => {                                             // the best known sequence of length N
      assert(1n <= N && N <= BigInt(MSTAR.nmax), claim, String(N));
      const [lo, , why] = MSTAR.cols[Number(N) - 1], code = document.getElementById(`${N}:${lo}`);
      assert(code === null ? why[0] === 'example' : sequences.has(code), claim, String(N), why);
      return {n: N, m: lo, link: code && `#${code.id}`, cite: code ? null : why[1]};
    },
    tau: j => ({n: 2n ** BigInt(j), m: j, link: null, cite: THUE_MORSE}),
    name: (x, claim) => {                                          // a construction of the page, which x names
      const e = defined.get(x), other = document.getElementById(x);
      assert(e !== undefined && (other === null || other === e), claim, x);
      e.id = x;
      const {n, m} = derived(e);
      return {n, m, link: `#${x}`, cite: null};
    },
  };
  function step(node, claim) {                                     // a part's step, or an operation's, with its parts'
    const [kind, x] = node;
    if (!(kind in RULES)) return {node, ...PARTS[kind](x, claim)};
    const kids = x.map(k => step(k, claim));
    return {node, kids, n: RULES[kind].n(kids.map(k => k.n)), m: RULES[kind].m(kids.map(k => k.m))};
  }
  const derivations = new Map();                                   // each construction: its last step, once derived
  function derived(e) {                                            // at its first click, or a click on one naming it
    const claim = e.dataset.construction;
    if (!derivations.has(e)) {
      derivations.set(e, null);                                    // while it is derived: a construction that names itself
      const last = step(parsed.get(e)[1], claim);
      assert(`${last.n}:${last.m}` === claim, claim, `${last.n}:${last.m}`);
      derivations.set(e, last);
    }
    assert(derivations.get(e) !== null, claim);
    return derivations.get(e);
  }
  // How a derivation writes a part's name, a step's formula and a length (2^k for a power of 2 greater than 2, as the
  // page's formulas write 2^2 and 2^8 but 2), as nodes
  const NAMES = {p: N => [el('i', 'p'), el('sub', String(N))], tau: j => ['τ', el('sub', String(j))], name: x => [el('i', x)]};
  const formula = ([kind, x]) => kind in RULES
    ? x.flatMap((k, i) => [...(i ? [` ${kind} `] : []), ...(k[0] in RULES ? ['(', ...formula(k), ')'] : formula(k))])
    : NAMES[kind](x);
  const length = n => n > 2n && (n & (n - 1n)) === 0n ? ['2', el('sup', String(n.toString(2).length - 1))] : [String(n)];
  const rows = s => [...(s.kids ?? []).flatMap(rows), s];         // a step's, its parts' first
  function row(s) {
    const name = s.link ? [Object.assign(el('a', ...formula(s.node)), {href: s.link})] : formula(s.node);
    const cite = s.cite ? [' ', Object.assign(el('span', `(${s.cite})`), {className: 'nw'})] : [];    // kept on one line
    const tr = el('tr', el('th', ...name, ...cite));
    const rule = RULES[s.node[0]];
    tr.append(el('td', ...(rule ? [...s.kids.flatMap((k, i) => [...(i ? [rule.ns] : []), ...length(k.n)]), ' =\u00a0'] : []), ...length(s.n)),
              el('td', ...(rule ? [`${rule.ms(s.kids.map(k => k.m))} =\u00a0`] : []), String(s.m)));
    Object.assign(tr.dataset, {n: s.n, m: s.m});
    return tr;
  }
  function derivation(e) {                                         // e's box: its derivation
    const last = derived(e), box = steps.querySelector('.derivation').cloneNode(true);
    box.querySelector('[data-steps]').append(...rows(last).map(row));
    box.querySelector('[data-bound-n]').append(...length(last.n));
    box.querySelector('[data-bound-m]').textContent = last.m;
    return box;
  }

  // ---------- the buttons ----------
  // A button's box opens right after the block that holds the button, its nearest p or li, never inside running text
  // (the coordinator, 2026-10-31: "an expansion opens right after the block element (the nearest p or li ancestor) that
  // holds its button, never inside running text"), the boxes of one block in the order of its buttons, whatever order
  // they were made in.  A box's id is expansion-K, K its button's place among the page's buttons, and its button's
  // aria-controls names it once it is made.
  const buttons = [...document.querySelectorAll('code[id], [data-join], [data-construction]')];
  const outside = buttons.filter(e => e.closest('p, li') === null);
  assert(outside.length === 0, outside.map(e => e.outerHTML.slice(0, 80)));
  const blocks = Map.groupBy(buttons, e => e.closest('p, li'));   // each block: its buttons, in page order
  const boxes = new Map();                                         // each code, join and construction: its box, once made
  function button(e, make) {                                       // e shows and hides make()'s box, after e's block
    const block = e.closest('p, li');
    const toggle = () => {
      const box = boxes.get(e) ?? made();
      box.hidden = !box.hidden;
      e.setAttribute('aria-expanded', String(!box.hidden));
    };
    const made = () => {
      const box = Object.assign(make(), {hidden: true, id: `expansion-${buttons.indexOf(e) + 1}`});
      boxes.set(e, box);
      block.after(...blocks.get(block).filter(b => boxes.has(b)).map(b => boxes.get(b)));    // its block's, in order
      e.setAttribute('aria-controls', box.id);
      return box;
    };
    e.setAttribute('role', 'button');
    e.tabIndex = 0;
    e.setAttribute('aria-expanded', 'false');
    e.addEventListener('click', toggle);
    e.addEventListener('keydown', ev => {                          // Enter and Space, as a button takes them
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      ev.preventDefault();                                         // Space would scroll the page
      toggle();
    });
  }
  sequences.forEach((s, e) => button(e, () => partition(e, s)));
  built.forEach(e => button(e, () => derivation(e)));
})();
