#!/usr/bin/env python3
"""Quals for the page's construction formulas as buttons (2026-10-31; dreeves agreed, "i think so? maybe show me a
before/after screenshot if there's any doubt?", to the proposal that the page's construction formulas be clickable like
codes and expand into their derivation): each formula of index.html written over sequences with # and ∨ is either a join
of codes (data-join, which quals_codes covers) or a construction, <span data-construction="N:M">, N its length and M its
order as the page states them.  A construction, clicked, or given Enter or Space while it has focus, shows right below
it its derivation, and the next click hides it: each part with its length n and order m and where that order comes from
(a code of the page, a link to it; τ_j, Thue–Morse; an example the page does not show, cited from mstar.js; a
construction of the page, a link to it), each product and join with the length and order its rule gives (a product
multiplies lengths and adds orders, a join adds lengths and has the least order of its parts), and the bound m*(N) ≥ M.
Run: python3 -B quals/quals_derivations.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The quals load copies of index.html in headless Chrome through quals_codes' harness (drive, a true viewport, real mouse
clicks or touch taps and real key presses), its items here the page's constructions.  What the page shows is held to
this file's own reading of the constructions' TeX (parse, derive), with Python's exact integers, mstar.js's lower bound
at each length n <= NMAX for p_n (the best known sequence of length n, as the powers-of-2 chart's caption says), pow2.js's
at each power of 2 beyond, and the page's new results (mstar.NEW).
"""
import sys
sys.dont_write_bytecode = True
import os, re, math, time, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, HERE)                                              # for its modules
import mstar
import quals_index as qi                      # read only: page, blank_comments, mstar_data, pow2_data, NMAX, OFF_PAGE
import quals_codes as qc                      # read only: drive, DESKTOP, PHONE and CODE

RUNS = {}                                     # drive's reports by configuration name, made once per process (see run)
CONSTRUCTIONS = '[data-construction]'         # the selector of this file's items: the page's constructions
CONSTRUCTION = re.compile(r'<span data-construction="([^"]*)">\\\((.*?)\\\)</span>', re.S)
# The page's constructions whose orders are less than the lower bounds that the data and the new results give at their
# lengths, by their claims N:M: f, the 2^24 construction of the remarks ("Joint construction", order 25, where the join
# of the 2^20 entry times τ_4 gives 26), and two products of it, f # f at 2^48 (order 50; 54 there) and f # f # τ_3 at
# 2^51 (order 53; 57 there).  Every other construction has exactly the lower bound at its length.
SUPERSEDED = ('16777216:25', '281474976710656:50', '2251799813685248:53')


# ---------------------------------------------------------------------------------------------------------------------
# The constructions' TeX, read here

OPERATOR = {'\\mathbin{\\#}': '#', '\\vee': '∨'}
NAME = re.compile(r'p_\{(\d+)\}|q_\{(\d+)\}|\\tau_(\d)|\\tau_\{(\d+)\}|([a-z])')
TOKEN = re.compile(r'\\mathbin\{\\#\}|\\vee|[()=]|p_\{\d+\}|q_\{\d+\}|\\tau_\d|\\tau_\{\d+\}|[a-z]|\S')


def operands(tex):
    """The operands of tex, a formula of the page without its \\( and \\) and with its links to codes dropped
    (quals_index.unlink), between its operators, its parentheses and its =; or None unless it has # or ∨, two operands
    or more, and every one of them a name: p_{N}, q_{N}, τ_j or a letter.  (The page's definitions of the two,
    f # g = f(x)·g(x^{n_f}) and f ∨ g = f(x) + x^{n_f} g(x), have operands that are not names, and its mentions of
    the symbols alone have none.)"""
    names = [p.strip() for p in re.split(r'\\mathbin\{\\#\}|\\vee|[()=]', tex) if p.strip()]
    return names if any(o in tex for o in OPERATOR) and len(names) >= 2 and all(NAME.fullmatch(p) for p in names) else None


def construction_formulas(texs):
    """Those of texs, formulas of the page (without their \\( and \\)), that build sequences of the page with # and ∨:
    every operand a name of one, p_{N}, q_{N}, τ_j or a letter that a formula among texs names (x = ..., f for the
    2^24 construction); each with its links to codes dropped.  A letter that no formula names is a variable, and its
    formula is about sequences in general: the lattice section's p_192 ∨ q, q the piece its search looked for."""
    found = [(tex, names) for tex in map(qi.unlink, texs) for names in [operands(tex)] if names]
    named = {names[0] for tex, names in found if re.match(r'\s*[a-z]\s*=', tex)}
    return [tex for tex, names in found if all(n in named or not re.fullmatch(r'[a-z]', n) for n in names)]


def leaf(token):
    """A name's leaf: ('p', N) for p_{N}, ('tau', j) for τ_j, ('name', x) for a letter x (q_{N} is none: its order is
    not the best known at N, so a construction cannot name it).  It asserts that the token is one of these."""
    x = re.fullmatch(r'p_\{(\d+)\}|\\tau_(\d)|\\tau_\{(\d+)\}|([a-oq-z])', token)
    assert x, token
    return ('p', int(x[1])) if x[1] else ('tau', int(x[2] or x[3])) if x[2] or x[3] else ('name', x[4])


def operation(items, tex):
    """The node of items, alternately operands and operators, as (operator, operands): two operands or more, all
    with the same operator, which must be # or ∨ (no precedence is assumed between the two: a formula that mixes them
    without parentheses is refused)."""
    operands, operators = items[0::2], items[1::2]
    assert (len(operands) == len(operators) + 1 >= 2 and len(set(operators)) == 1 and operators[0] in ('#', '∨')
            and all(type(x) is tuple for x in operands)), (tex, items)
    return (operators[0], operands)


def parse(tex):
    """(lhs, tree) of a construction's TeX: lhs the leaf before =, or None; tree a leaf or (operator, operands), each
    operand a leaf or a parenthesized node.  A stack of open parentheses, each with its items so far."""
    tokens = TOKEN.findall(tex)
    assert ''.join(tokens) == re.sub(r'\s+', '', tex), tex             # every character but spaces is in a token
    lhs = leaf(tokens[0]) if tokens[1:2] == ['='] else None
    levels = [[]]
    for t in tokens[2 if lhs else 0:]:
        if t == '(':
            levels.append([])
        elif t == ')':
            inner = operation(levels.pop(), tex)
            levels[-1].append(inner)
        else:
            levels[-1].append(OPERATOR[t] if t in OPERATOR else leaf(t))
    assert len(levels) == 1, tex
    return lhs, operation(levels[0], tex)


def text_of(node):
    """A node's formula as the derivations write it, in this file's text of math (sub as _, sup as ^): p_112, τ_1, f,
    and an operation's operands joined by its operator, each operation among them in parentheses."""
    kind, x = node
    if kind in ('#', '∨'):
        return f' {kind} '.join(f'({text_of(k)})' if k[0] in ('#', '∨') else text_of(k) for k in x)
    return {'p': f'p_{x}', 'tau': f'τ_{x}', 'name': x}[kind]


def length_text(n):
    """A length as the derivations write it: 2^k for a power of 2 greater than 2 (as the page's formulas write 2^2 and
    2^8, and 2 itself), else its digits."""
    return f'2^{n.bit_length() - 1}' if n > 2 and n & (n - 1) == 0 else str(n)


def constructions(text=None):
    """[(claim, tex, lhs, tree)] for each construction of index.html (or of text) outside its comments, in page order:
    its data-construction and its formula's TeX, parsed."""
    blank = qi.blank_comments(qi.page() if text is None else text)
    return [(claim, tex) + parse(tex) for claim, tex in CONSTRUCTION.findall(blank)]


def derivations(text=None):
    """[(claim, rows, (n, m))] for each construction of index.html (or of text), in page order: rows its derivation's
    steps, each {th, n_text, m_text, n, m, links, kind}, a part's before the product or join that uses it, the last
    the whole formula's; and (n, m) its length and order.  A part p_N has length N and mstar.js's lower bound at N as
    its order, and its source is the page's code N:M (a link to it, links [(#N:M, p_N)]) or else mstar.js's example
    label, cited (an example the page does not show); τ_j has length 2^j and order j, from Thue–Morse; a letter is the
    construction of the page whose formula defines it (x = ...), a link to it, #x.  A product's length is the
    product of its parts', its order the sum; a join's length the sum, its order the least of its parts'."""
    built, cols = constructions(text), qi.mstar_data()['cols']
    blank = qi.blank_comments(qi.page() if text is None else text)
    ids = {f'{x[1]}:{x[2]}' for x in qc.CODE.finditer(blank)}
    defined = {lhs: i for i, (_, _, lhs, _) in enumerate(built) if lhs}
    assert len(defined) == sum(1 for c in built if c[2]), [c[2] for c in built]
    done = {}

    def part(node, rows):
        kind, x = node
        if kind == 'p':
            lo, _, why, _ = cols[x - 1]
            key = f'{x}:{lo}'
            here = key in ids
            assert here or why[0] == 'example', (x, why)
            out = (x, lo, f'p_{x}' if here else f'p_{x} ({why[1]})', [(f'#{key}', f'p_{x}')] * here,
                   'code' if here else 'cited')
        elif kind == 'tau':
            out = (2 ** x, x, f'τ_{x} (Thue–Morse)', [], 'tau')
        else:
            n, m = value(defined[node])
            out = (n, m, x, [(f'#{x}', x)], 'name')
        n, m, th, links, how = out
        rows.append(dict(th=th, n_text=length_text(n), m_text=str(m), n=n, m=m, links=links, kind=how))
        return n, m

    def step(node, rows):
        kind, x = node
        if kind not in ('#', '∨'):
            return part(node, rows)
        values = [step(k, rows) for k in x]
        ns, ms = [v[0] for v in values], [v[1] for v in values]
        n, m = (math.prod(ns), sum(ms)) if kind == '#' else (sum(ns), min(ms))
        n_text = (' · ' if kind == '#' else ' + ').join(map(length_text, ns)) + f' = {length_text(n)}'
        m_text = (' + '.join(map(str, ms)) if kind == '#' else f'min({", ".join(map(str, ms))})') + f' = {m}'
        rows.append(dict(th=text_of(node), n_text=n_text, m_text=m_text, n=n, m=m, links=[], kind=kind))
        return n, m

    def value(i):
        if i not in done:
            done[i] = None                                             # a formula that names itself never ends
            rows = []
            done[i] = (rows, step(built[i][3], rows))
        assert done[i] is not None, built[i]
        return done[i][1]

    for i in range(len(built)): value(i)
    return [(claim, *done[i]) for i, (claim, *_) in enumerate(built)]


def data_lo(n):
    """The data's lower bound on m*(n): mstar.js's at n <= NMAX, pow2.js's at a power of 2 beyond."""
    k = n.bit_length() - 1
    assert n <= qi.NMAX or n == 2 ** k, n
    return qi.mstar_data()['cols'][n - 1][0] if n <= qi.NMAX else qi.pow2_data()['cols'][k - 1][0]


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

# The functions below run in the page, as quals_codes' DRIVER runs them (its op js), after its load has put the
# constructions there as qualsItems.
# The focus (the index of the focused construction, -1 for none), the scroll, the viewport and the page's width, each
# construction as [its data-construction, role, tabIndex, aria-expanded], and how many derivations (class derivation)
# show
LOOK = """() => ({active: qualsItems().indexOf(document.activeElement), scrollX, scrollY, innerWidth, innerHeight,
  scrollW: document.documentElement.scrollWidth,
  items: qualsItems().map(e => [e.dataset.construction, e.getAttribute('role'), e.tabIndex, e.getAttribute('aria-expanded')]),
  shown: [...document.querySelectorAll('.derivation')].filter(e => e.checkVisibility()).length})"""
# Construction i and the element its aria-controls names: if that is a derivation (class derivation), whether it shows,
# its box,
# each step of it (each row of [data-steps]: its data-n and data-m, its cells' texts, and its links, each [its href,
# its text, the tag and data-construction of the element whose id the href names]), the text of its bound
# ([data-bound]), and how far any element of it reaches past its right edge (spill, CSS px).  A text is written as
# this file writes math: each sup as ^ and its text, each sub as _ and its text, runs of spaces as one.
READ = """i => {
  const e = qualsItems()[i], next = document.getElementById(e.getAttribute('aria-controls'));
  const rect = x => { const b = x.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  const text = x => { const c = x.cloneNode(true);
    c.querySelectorAll('sup').forEach(s => s.replaceWith('^' + s.textContent));
    c.querySelectorAll('sub').forEach(s => s.replaceWith('_' + s.textContent));
    return c.textContent.replace(/\\s+/g, ' ').trim(); };
  const target = h => { const t = document.getElementById(h.slice(1)); return t && [t.tagName, t.dataset.construction ?? null]; };
  const box = next && next.classList.contains('derivation') ? next : null;
  return {claim: e.dataset.construction, expanded: e.getAttribute('aria-expanded'), rect: rect(e),
    box: box && {shown: box.checkVisibility(), rect: rect(box),
      rows: [...box.querySelectorAll('[data-steps] > tr')].map(r => ({n: r.dataset.n, m: r.dataset.m, cells: [...r.cells].map(text),
        links: [...r.querySelectorAll('a')].map(a => [a.getAttribute('href'), text(a), target(a.getAttribute('href'))])})),
      bound: box.querySelector('[data-bound]') && text(box.querySelector('[data-bound]')),
      spill: Math.max(...[...box.querySelectorAll('*')].map(x => x.getBoundingClientRect().right)) - rect(box)[2]}};
}"""
# Every formula KaTeX drew, as [its TeX (KaTeX's annotation), and of the construction or join it is in, if any: its
# role, and its data-construction or "join " and its data-join]
SCAN = """() => [...document.querySelectorAll('.katex annotation[encoding="application/x-tex"]')].map(a => {
  const b = a.closest('[data-construction], [data-join]');
  return [a.textContent, b && b.getAttribute('role'), b && (b.dataset.construction ?? 'join ' + b.dataset.join)];
})"""

# The page changed, each change with the index of the construction it changes (the 2^17 construction's is 4, f # f #
# τ_3's 9), for the quals that it fails loudly: claim says the 2^17 construction has order 19 (its rules give 18);
# undefined names g, which no construction defines, in dreeves's f # f # τ_3 of the 2^51 entry; mixed drops the
# parentheses around the 2^17 construction's first product, so that # and ∨ meet with no parentheses between them.  And
# for the qual of a join's order: unequal makes the 2^17 construction's second product times τ_2 in place of τ_1, so
# that its two products have orders 18 and 19 (each join of the page joins products of equal orders), its claim the
# least, 172544:18; larger claims the larger, 172544:19.
F17 = '<span data-construction="131072:18">\\((p_{112} \\mathbin{\\#} p_{800}) \\vee'
F51 = '<span data-construction="2251799813685248:53">\\(f \\mathbin{\\#} f'
F17_ALL = F17 + ' (p_{48} \\mathbin{\\#} p_{432} \\mathbin{\\#} \\tau_1)\\)</span>'
CHANGES = {'claim': (F17, F17.replace('131072:18', '131072:19'), 4),
           'undefined': (F51, F51.replace('\\(f \\mathbin', '\\(g \\mathbin'), 9),
           'mixed': (F17, F17.replace('\\((p_{112} \\mathbin{\\#} p_{800})', '\\(p_{112} \\mathbin{\\#} p_{800}'), 4),
           'unequal': (F17_ALL, F17_ALL.replace('131072:18', '172544:18').replace('\\tau_1', '\\tau_2'), 4),
           'larger': (F17_ALL, F17_ALL.replace('131072:18', '172544:19').replace('\\tau_1', '\\tau_2'), 4)}


def changed(name):
    """index.html with the change CHANGES[name] made, its old text found exactly once."""
    old, new, _ = CHANGES[name]
    text = qi.page()
    assert text.count(old) == 1, (name, text.count(old))
    return text.replace(old, new)


def largest():
    """The index of the construction with the most steps in its derivation."""
    sizes = [len(rows) for _, rows, _ in derivations()]
    return sizes.index(max(sizes))


def run(name):
    """drive's report for one configuration, made on first use, its items the page's constructions:
    light: 1280 px wide; at load the constructions; then Tab pressed until one has focus, and Enter, Enter, Space and
           Space to it, the page looked at before and after each and the construction read after each; then each
           construction clicked twice, read after each click; then every formula KaTeX drew scanned.
    phone: 390 px wide, a phone's; the largest derivation's construction tapped and read, the page looked at; then every
           other construction tapped and read, and the page looked at.
    claim, undefined, mixed, unequal, larger: the page with CHANGES[name], looked at as loaded, then the construction
           it changes clicked and read."""
    if name not in RUNS:
        assert constructions(), 'no construction on the page'
        n, big = len(constructions()), largest()
        keys = [['tabTo', CONSTRUCTIONS, 800], ['js', LOOK]] + [
            s for k in ('Enter', 'Enter', 'Space', 'Space') for s in (['js', LOOK], ['key', k], ['js', LOOK], ['js', READ, 0])]
        steps = {                                      # each configuration's (viewport, steps, page), made when run
            'light': lambda: (qc.DESKTOP, [['load'], ['js', LOOK]] + keys
                              + [s for i in range(n) for s in (['click', i], ['js', READ, i]) * 2] + [['js', SCAN]], None),
            'phone': lambda: (qc.PHONE, [['load'], ['click', big], ['js', READ, big], ['js', LOOK]]
                              + [s for i in range(n) if i != big for s in (['click', i], ['js', READ, i])]
                              + [['js', LOOK]], None),
        }.get(name, lambda: (qc.DESKTOP, [['load'], ['js', LOOK], ['click', CHANGES[name][2]], ['js', READ, CHANGES[name][2]]],
                             changed(name)))()
        RUNS[name] = qc.drive(steps[0], steps[1], steps[2], items=CONSTRUCTIONS)
    return RUNS[name]


def opened(R):
    """The light run's reads of open derivations (aria-expanded true), by index of their construction, from its clicks."""
    n = len(constructions())
    clicks = R['steps'][-4 * n - 1:-1]
    return {i: clicks[4 * i + 1] for i in range(n)}


# ---------------------------------------------------------------------------------------------------------------------
# Quals

def q_every_construction_formula_is_expandable():
    # Replicata: index.html outside its comments: every formula \( ... \) that builds sequences of the page with # and ∨
    # (construction_formulas); and the light run (1280 px): at load, each construction (data-construction); each
    # clicked twice, read after each click; then every formula KaTeX drew.
    # Expectata (dreeves agreed, 2026-10-31, that "the page's construction formulas should be clickable like codes, and
    # expand into their derivation"): every such formula is the whole of a construction, <span
    # data-construction="N:M">, or of a join of codes (data-join); there is one construction at least; each is a button
    # (role button, in the tab order, collapsed at load, aria-expanded false), under the pointer at each click; its first
    # click shows its derivation below it (after its block, quals_codes' q_boxes_open_after_their_blocks), expanded
    # (aria-expanded true), the derivation the element its aria-controls names, and its second click hides
    # it, collapsed again; after the page loaded, every such formula that KaTeX drew is in such a button, its TeX the
    # TeX of the page's source; and nothing is logged.
    # Resultata before: no construction: the 10 such formulas other than the 528 entry's join were KaTeX text, their
    # names links to codes, and none a button.
    blank = qi.blank_comments(qi.page())
    formulas = construction_formulas(m.group(1) for m in re.finditer(r'\\\((.*?)\\\)', blank, re.S))
    wrapped = ([tex for _, tex in CONSTRUCTION.findall(blank)]
               + re.findall(r'<span data-join="[^"]*" data-order="\d+">\\\((.*?)\\\)</span>', blank, re.S))
    assert sorted(formulas) == sorted(wrapped), ([tex for tex in formulas if tex not in wrapped], wrapped)
    built = constructions()
    assert built, 'no construction'
    R = run('light')
    assert R['errors'] == [], R['errors'][:5]
    load = R['steps'][1]
    assert load['items'] == [[claim, 'button', 0, 'false'] for claim, *_ in built] and load['shown'] == 0, load
    bad = []
    clicks = R['steps'][-4 * len(built) - 1:-1]
    for i, (claim, *_) in enumerate(built):
        first, shown, second, hidden = clicks[4 * i:4 * i + 4]
        box = shown['box']
        states = [shown['claim'], shown['expanded'], bool(box and box['shown'] and box['rect'][1] >= shown['rect'][3] - 0.5),
                  hidden['expanded'], bool(hidden['box'] and hidden['box']['shown']), first[2], second[2]]
        if states != [claim, 'true', True, 'false', False, True, True]: bad.append((i, claim, states))
    assert bad == [], bad
    drawn = construction_formulas(tex for tex, _, _ in R['steps'][-1])
    scan = [s for s in R['steps'][-1] if qi.unlink(s[0]) in drawn]
    assert scan and all(role == 'button' and owner for _, role, owner in scan), [s for s in scan if s[1] != 'button']
    assert ([(owner, tex.strip()) for tex, _, owner in scan if not owner.startswith('join ')]
            == [(claim, tex.strip()) for claim, tex, *_ in built]), (scan, built)


def q_derivations_total_the_stated_bounds():
    # Replicata: each construction of index.html, its claim N:M (data-construction: the bound m*(N) ≥ M that the page
    # states with it), the light run's read of its derivation (each construction clicked), this file's derivation of its
    # TeX (derivations: mstar.js's lower bounds for p_N, τ_j, and the page's constructions for their letters), the
    # data's lower bound at N (mstar.js, or pow2.js at a power of 2 beyond 1024) and the page's new results there
    # (mstar.NEW, which mstar.py holds to the page's table of new results).
    # Expectata (the request: "the total, which must equal the bound the page states, or it fails loudly"; "Each
    # derivation's total equals the page's stated bound and the data's"): the derivation shows every step that this
    # file derives, in the same order, each with the same texts (its formula, its length's arithmetic and its order's)
    # and the same exact n and m (data-n, data-m); its last step's n and m are N and M, and its bound reads m^*(N) ≥ M;
    # and M is the data's lower bound at N and the new results' lower bound there, except for SUPERSEDED, where M is less
    # than both.
    # Resultata before: no construction and no derivation.
    R = run('light')
    shown, mine = opened(R), derivations()
    assert mine, 'no construction'
    bad = []
    for i, (claim, rows, (n, m)) in enumerate(mine):
        box = shown[i]['box']
        got = box and [(r['cells'], r['n'], r['m']) for r in box['rows']]
        want = [([r['th'], r['n_text'], r['m_text']], str(r['n']), str(r['m'])) for r in rows]
        if got != want or box['bound'] != f'm^*({length_text(n)}) ≥ {m}' or claim != f'{n}:{m}':
            bad.append((claim, got and got[-1], want[-1], box and box['bound']))
    assert bad == [], bad
    below = [(claim, data_lo(n), mstar.NEW[n][0]) for claim, _, (n, m) in mine if not m == data_lo(n) == mstar.NEW[n][0]]
    assert sorted(claim for claim, *_ in below) == sorted(SUPERSEDED), below
    assert all(int(claim.split(':')[1]) < min(lo, new) for claim, lo, new in below), below


def q_leaves_resolve():
    # Replicata: the light run's reads of the derivations (each construction clicked), their parts (the steps of a
    # name: p_N, τ_j or a letter), with their links and what each link names; quals_index.OFF_PAGE, the names of
    # examples the page does not show; mstar.js's columns.
    # Expectata (the request: "page codes: show N, M and a jump to the code, where it expands; τ_j: Thue–Morse, length
    # 2^j, order j; any off-page code, such as BGPW's p240 in 2^20's construction (quals_index.OFF_PAGE): its stated
    # order and its source, cited, not expanded"): a part p_N whose code the page shows, <code id="N:M"> with M
    # mstar.js's lower bound at N, has length N and order M and is a link to that code; τ_j has length 2^j and order j,
    # from Thue–Morse, with no link; a part p_N whose code the page does not show has no link, its name is in OFF_PAGE,
    # and it cites mstar.js's example label at N, its order mstar.js's lower bound there; a letter is a link to the
    # construction of the page that defines it; and the parts cited are exactly OFF_PAGE's.
    # Resultata before: no derivation, so no part.
    R = run('light')
    shown, mine = opened(R), derivations()
    cols = qi.mstar_data()['cols']
    defines = {lhs[1]: claim for claim, _, lhs, _ in constructions() if lhs}
    bad, cited = [], set()
    for i, (claim, rows, _) in enumerate(mine):
        for r, got in zip(rows, shown[i]['box']['rows']):
            n, m, how = r['n'], r['m'], r['kind']
            links = [(h, t) for h, t, _ in got['links']]
            targets = [x for _, _, x in got['links']]
            ok = {'code': lambda: links == [(f'#{n}:{m}', f'p_{n}')] and targets == [['CODE', None]] and cols[n - 1][0] == m,
                  'tau': lambda: links == [] and got['cells'][0].endswith('(Thue–Morse)') and n == 2 ** m,
                  'cited': lambda: (links == [] and f'p_{{{n}}}' in qi.OFF_PAGE and cols[n - 1][0] == m
                                    and got['cells'][0] == f'p_{n} ({cols[n - 1][2][1]})'),
                  'name': lambda: links == [(f'#{r["th"]}', r['th'])] and targets == [['SPAN', defines[r['th']]]],
                  }.get(how, lambda: links == [])()
            if not ok: bad.append((claim, r['th'], how, got))
            cited |= {f'p_{{{n}}}'} if how == 'cited' else set()
    assert bad == [], bad
    assert sorted(cited) == sorted(qi.OFF_PAGE), (cited, qi.OFF_PAGE)


def q_constructions_take_tab_enter_and_space():
    # Replicata: the light run, as loaded: Tab pressed until a construction has focus; then, to it, Enter, Enter, Space
    # and Space, real key presses, the page looked at before and after each and the construction read after each.
    # Expectata: the button semantics a reader with a keyboard needs, as the codes have: Tab reaches the constructions,
    # the page's first one first; Enter shows its derivation, Enter hides it, Space shows it and Space hides it
    # (aria-expanded true, false, true, false); the focus stays on it; and Space does not scroll the page.
    # Resultata before: Tab never reached a construction (800 presses): there was none.
    R = run('light')
    tabs, look = R['steps'][2], R['steps'][3]
    assert look['active'] == 0, (tabs, look['active'])
    presses = [R['steps'][4 + 4 * j:8 + 4 * j] for j in range(4)]      # look, key, look, read
    got = [(key, after['active'], read['expanded'], bool(read['box'] and read['box']['shown']))
           for before, key, after, read in presses]
    assert got == [('Enter', 0, 'true', True), ('Enter', 0, 'false', False),
                   ('Space', 0, 'true', True), ('Space', 0, 'false', False)], got
    assert all(before['scrollY'] == after['scrollY'] for before, key, after, read in presses if key == 'Space'), \
        [(before['scrollY'], after['scrollY']) for before, key, after, read in presses]


def q_derivations_fit_a_phone():
    # Replicata: index.html as a phone shows it (390 px wide, 844 tall, 3 device px per CSS px, touch; the phone run):
    # the construction with the largest derivation (the most steps) tapped, then every other construction tapped too,
    # each read after its tap.
    # Expectata (no sideways scroll at phone width): the largest derivation shows within the viewport's width with the
    # page no wider than the viewport; every derivation shows, no element of it reaching past its right edge and none
    # taller than the viewport; with every derivation shown, the page is still no wider than the viewport; and nothing
    # is logged.
    # Resultata before: no construction to tap.
    R = run('phone')
    assert R['errors'] == [], R['errors'][:5]
    read, look, last = R['steps'][2], R['steps'][3], R['steps'][-1]
    box = read['box']
    assert box and box['shown'] and len(box['rows']) == max(len(rows) for _, rows, _ in derivations()), read
    left, top, right, bottom = box['rect']
    assert 0 <= left and right <= look['innerWidth'] == 390 and look['scrollW'] <= look['innerWidth'], (box['rect'], look['scrollW'])
    reads = [read] + R['steps'][5:-1:2]
    assert sorted(r['claim'] for r in reads) == sorted(c[0] for c in constructions()), [r['claim'] for r in reads]
    bad = [(r['claim'], r['box'] and (r['box']['shown'], r['box']['rect'], r['box']['spill'])) for r in reads
           if not (r['box'] and r['box']['shown'] and r['box']['spill'] <= 0.5
                   and r['box']['rect'][3] - r['box']['rect'][1] <= look['innerHeight'])]
    assert bad == [], bad
    assert last['scrollW'] <= last['innerWidth'] and all(c[3] == 'true' for c in last['items']), \
        (last['scrollW'], [c for c in last['items'] if c[3] != 'true'])


def q_a_construction_that_is_not_its_claim_fails_loudly():
    # Replicata: the page changed three ways (CHANGES), each loaded, then the construction it changes clicked: the 2^17
    # construction said to have order 19 (claim); g, which no construction defines, in place of the first f of
    # f # f # τ_3 (undefined); and the 2^17 construction's first product without its parentheses, # and ∨ meeting
    # (mixed).
    # Expectata (fail loudly, never fix silently; as a code's, a construction's form is checked as the page loads and its
    # arithmetic, which reads mstar.js, at its click): the claim's and the undefined name's pages load with every
    # construction a button, and the click throws an error that names the construction (its data-construction) and
    # shows no derivation, the construction staying collapsed (nothing logged before the click: the error may be logged
    # as the next step begins, the browser reporting it on its own time); the mixed formula's page throws as it loads,
    # naming the construction, and no construction is a button.
    # Resultata before: no construction, so none of the three changes could be made.  Then (2026-10-31, the arithmetic
    # checked as the page loaded) quals_index's charts, drawn from made-up data, failed on the constructions' errors.
    for name, claim in (('claim', '131072:19'), ('undefined', '2251799813685248:53')):
        R = run(name)                         # steps: load, look, click (step 2), read
        assert R['errors'] and all(k >= 2 for k, _ in R['errors']) and any(claim in line for _, line in R['errors']), (name, R['errors'])
        assert all(c[1] == 'button' for c in R['steps'][1]['items']), (name, R['steps'][1]['items'])
        read = R['steps'][3]
        assert read['claim'] == claim and read['expanded'] == 'false' and read['box'] is None, (name, read)
    R = run('mixed')                          # steps: load (step 0), look, click, read
    assert R['errors'] and all(k == 0 for k, _ in R['errors']) and any('131072:18' in line for _, line in R['errors']), R['errors']
    assert all(c[1] is None for c in R['steps'][1]['items']), R['steps'][1]['items']


def q_a_join_has_the_least_order_of_its_parts():
    # Replicata: the page with the 2^17 construction's second product times τ_2 in place of τ_1 (CHANGES), so that its
    # two products have orders 18 and 19: claimed as 172544:18, the lesser, loaded and the construction clicked
    # (unequal); and claimed as 172544:19, the larger, loaded (larger).
    # Expectata (the request: "a join has at least the smaller order of its parts"; and "Check whether any join inside a
    # construction claims more than the smaller order of its parts"): the derivation's join has min(18, 19) = 18, and its
    # bound reads m^*(172544) ≥ 18, nothing logged; the claim of the larger order throws at the click, naming it, and
    # shows no derivation.
    # Resultata before: the page's joins all join products of equal orders, so that no qual above tells the least
    # order from the greatest: a page script that gave a join the greater of its parts' orders passed them all
    # (scratch/derive-20261031/mutants.log), and failed this qual (scratch/derive-20261031/red/).
    R = run('unequal')
    assert R['errors'] == [], R['errors'][:5]
    read = R['steps'][3]
    assert read['claim'] == '172544:18' and read['box'] and read['box']['shown'], read
    rows = read['box']['rows']
    assert rows[-1]['cells'][1:] == ['89600 + 82944 = 172544', 'min(18, 19) = 18'] and rows[-1]['m'] == '18', rows[-1]
    assert read['box']['bound'] == 'm^*(172544) ≥ 18', read['box']['bound']
    R = run('larger')                         # steps: load, look, click (step 2), read
    assert R['errors'] and all(k >= 2 for k, _ in R['errors']) and any('172544:19' in line for _, line in R['errors']), R['errors']
    assert R['steps'][3]['expanded'] == 'false' and R['steps'][3]['box'] is None, R['steps'][3]


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0, c0 = time.time(), time.process_time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds and this process's CPU seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds and this process's CPU seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
