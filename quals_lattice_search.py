#!/usr/bin/env python3
"""Quals for lattice_search.wl, the Mathematica version of Claude's lattice search, and for the section of index.html
that explains the search (Stan Wagon asked for both, 2026-10-14).  Run: python3 -B quals_lattice_search.py [name ...]
(no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The quals of the .wl run it with wolframscript, in one kernel for all of them (see run), and check what it returns by
independent routes: exact power sums here, brute force over every sign vector where that is small, and the counts
known from the literature.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, time, shutil, tempfile, itertools, traceback, subprocess
from fractions import Fraction
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
WL = os.path.join(HERE, 'lattice_search.wl')
WL_URL = 'https://raw.githubusercontent.com/dreeves/equipow/main/lattice_search.wl'
# The calls the section lists, in its order, with what each returns: (call, number of sequences, complete).  Why each
# is right:
#   6, 2, 0: order 2 needs 4 | n; here the equations already have no integer solution (with a = 2y - 1 they ask that
#            y_0 + ... + y_5 = 3 and sum_i y_i (2i - 5) = 0, of opposite parities).
#   32, 5, 0: Thue-Morse and its negation (Thue-Morse is the only partition for k <= 5: Roth, Siegel and Vardy 1994;
#            Boyd 1997).
#   48, 6, 1: Table 5's p48 and its negation; q_wl_exhaustive_agrees_with_brute_force checks all 2^24.
#   64, 6, 0: Boyd's 3 partitions (2002), each as a sequence and its negation.
#   112, 7, -1: the order-7 partition of {0, ..., 111} is unique (the page's counts section), and Table 5's is
#            antisymmetric.
#   320, 11, -1: m*(320) = 9 (the new results' table).
#   96, 7, -1 and 144, 8, 1, pruned: one sequence each, as "Want" -> 1 asks (seeded, so the same every run).
CALLS = (('latticeSearch[6, 2, 0]', 0, True),
         ('latticeSearch[32, 5, 0, "Want" -> Infinity]', 2, True),
         ('latticeSearch[48, 6, 1, "Want" -> Infinity]', 2, True),
         ('latticeSearch[64, 6, 0, "Want" -> Infinity]', 6, True),
         ('latticeSearch[112, 7, -1, "Want" -> Infinity, "MaxNodes" -> 10^9]', 2, True),
         ('latticeSearch[320, 11, -1, "Want" -> Infinity]', 0, True),
         ('latticeSearch[96, 7, -1]', 1, False),
         ('latticeSearch[144, 8, 1, "Pruning" -> 0.1]', 1, False))
# Calls only the quals make: the exhaustive runs the brute force checks.
EXTRA = ('latticeSearch[16, 4, 0, "Want" -> Infinity]',)
# Known examples, as hex codes in the paper's Table 5 convention, with (n, order, symmetry): Table 5's p48 and p112, and
# Claude's p320 (index.html's remarks).
KNOWN = (('C27D8C', 48, 6, 1), ('A5994DB29B45A0', 112, 7, -1), ('B24B649ED92CD2C36496CB2DB6295D974138BA41', 320, 9, -1))
# The searches the section describes, with the lattice dimension it states: (length, d, how d comes about).  For a
# direct search d = h - floor(m/2), h = n/2 free signs; 336 has one more equation (the matching); 560's direct search
# would have had 275, and its search with residue sums fixed had 145 free signs under 16 equations; 800's (2026-10-17,
# scratch/est800/t800/go800f.py and mitm9.py) would have had 395 and had 133 free signs under 14 equations.
DIMS = ((144, 68, 72 - 8 // 2), (240, 115, 120 - 10 // 2), (320, 156, 160 - 9 // 2), (336, 163, 168 - 9 // 2 - 1),
        (432, 211, 216 - 11 // 2), (480, 234, 240 - 12 // 2), (560, 275, 280 - 10 // 2), (560, 129, 145 - 16),
        (800, 395, 400 - 11 // 2), (800, 119, 133 - 14))
RUNS = {}                                     # what run() returned, by its code, made once per process


def page(): return open(INDEX, encoding='utf-8').read()


def section():
    """The section's HTML, from <section class="lattice" to its </section>."""
    m = re.search(r'<section class="lattice" aria-labelledby="lattice-title">.*?</section>', page(), re.S)
    assert m, 'no <section class="lattice" aria-labelledby="lattice-title">'
    return m.group(0)


def text(fragment):
    """fragment as a reader gets it: tags removed, entities decoded, white space collapsed."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', fragment))).strip()


def order(f):
    """The order of f: how many of its power sums sum_i f_i i^k, k = 0, 1, ..., vanish, with positions from 0 and
    0^0 = 1, in exact integers."""
    k = 0
    while sum(x * i ** k for i, x in enumerate(f)) == 0: k += 1
    return k


def from_hex(hx, m):
    left = [1 if b == '1' else -1 for b in bin(int(hx, 16))[2:].zfill(4 * len(hx))]
    return left + [(-1) ** m * x for x in reversed(left)]


def script(*lines, timeout=3600):
    """wolframscript's run of a script of these lines (a temporary file, so each line is read only after the one before
    it ran: a single -code string is read whole, before a Get in it, which leaves its names in Global`)."""
    d = tempfile.mkdtemp(prefix='lattice-quals-')
    path = os.path.join(d, 'run.wls')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    p = subprocess.run(['wolframscript', '-file', path], capture_output=True, text=True, timeout=timeout)
    shutil.rmtree(d)
    assert 'not activated' not in p.stdout + p.stderr, seats()
    return p


def seats():
    """Why a kernel may not start: the license allows 6 kernels at once ($MaxLicenseProcesses, 2026-10-14), and every
    open session of an app with the Wolfram MCP server (Claude Code, Claude desktop, Codex) holds one.  The Wolfram
    kernels running, each with the app that started it."""
    ps = subprocess.run(['ps', '-axo', 'pid=,ppid=,lstart=,command='], capture_output=True, text=True).stdout
    rows = [l.split(None, 7) for l in ps.splitlines()]
    cmd = {r[0]: r[7] for r in rows if len(r) == 8}
    kernels = [r for r in rows if len(r) == 8 and re.match(r'/Applications/Wolfram\.app/Contents/MacOS/(wolfram|WolframKernel)\b', r[7])
               and 'playerpass' not in r[7]]
    listing = '\n'.join(f'  pid {r[0]}, started {" ".join(r[2:7])}, by {cmd.get(r[1], "?")[:90]}' for r in kernels)
    # TODO: failure message; says Mathematica would not start, probably because all 6 kernel seats are taken, lists the
    # Wolfram kernels running with the app that started each, and says to stop stale ones or close those apps' sessions
    return ('Claude: "Mathematica would not start: all 6 kernel seats may be taken. Kernels running:"\n' + listing +
            '\nClaude: "Stop stale ones, such as old MCP servers, with kill -KILL, or close their apps\' sessions."')


def run(code):
    """code's result in the Mathematica kernel, after Get[lattice_search.wl], as JSON: code must Print one JSON line
    last.  wolframscript runs once per distinct code."""
    if code not in RUNS:
        p = script(f'Get["{WL}"];', code)
        lines = p.stdout.strip().splitlines()
        assert p.returncode == 0 and lines and lines[-1].startswith(('[', '{')), (p.returncode, p.stdout[-3000:],
                                                                                   p.stderr[-3000:])
        RUNS[code] = json.loads(lines[-1])
    return RUNS[code]


def results():
    """{call: (sequences, sets, complete, dimension as text, trials, nodes, seconds)} for CALLS and EXTRA, from one
    kernel."""
    calls = [c for c, *_ in CALLS] + list(EXTRA)
    body = ', '.join(f'With[{{r = {c}}}, {{r["solutions"], r["sets"], r["complete"], ToString[r["dimension"]], '
                     f'r["trials"], r["nodes"], r["seconds"]}}]' for c in calls)
    out = run(f'Print[ExportString[{{{body}}}, "JSON", "Compact" -> True]]')
    assert len(out) == len(calls), out
    return dict(zip(calls, out))


# ---------------------------------------------------------------------------------------------------------------------
# The section of index.html

def q_section_follows_counts_and_precedes_sets():
    # Replicata: index.html.
    # Expectata: the section on partitions at powers of 2 (<section class="counts">) is followed, with only blank
    # lines and comments between, by <section class="lattice" aria-labelledby="lattice-title">, and that by
    # <section class="sets">; the page has one of each.
    t = page()
    for tag in ('<section class="counts">', '<section class="lattice"', '<section class="sets">'):
        assert t.count(tag) == 1, (tag, t.count(tag))
    filler = r'(?:\s|<!--.*?-->)*'
    assert re.search(r'<section class="counts">.*?</section>' + filler +
                     r'<section class="lattice" aria-labelledby="lattice-title">.*?</section>' + filler +
                     r'<section class="sets">', t, re.S)


def q_section_is_one_claude_quote():
    # Replicata: the section's lines.
    # Expectata: dreeves's form for it (2026-10-14), all its English in a block quote attributed to Claude: inside the
    # section, a <!-- TODO: comment (a recap of the quote, for dreeves), his lead-in (quals_index.QUOTE_LEADIN, "Still
    # Claude:"), and then the quote, from <blockquote class="claude"> to </blockquote>, and nothing else but blank
    # lines; the quote's first line inside is the heading <h2 id="lattice-title"> and its last is the attribution
    # <p class="attrib">— Claude</p>.
    lines = [l.strip() for l in section().splitlines() if l.strip()]
    assert lines[0] == '<section class="lattice" aria-labelledby="lattice-title">' and lines[-1] == '</section>', lines
    assert lines[1].startswith('<!-- TODO:') and lines[1].endswith('-->'), lines[1]
    assert tuple(lines[2:5]) == ('<p>', 'Still Claude:', '</p>'), lines[2:5]
    assert lines[5] == '<blockquote class="claude">' and lines[-2] == '</blockquote>', (lines[5], lines[-2])
    assert lines[6].startswith('<h2 id="lattice-title">') and lines[6].endswith('</h2>'), lines[6]
    assert lines[-3] == '<p class="attrib">— Claude</p>', lines[-3]
    assert section().count('<blockquote') == 1 and 'Claude: "' not in section()


def q_section_links_the_wl():
    # Replicata: the section's links, and the repository's files.
    # Expectata: one link to lattice_search.wl, at its raw GitHub address (as the page links proof512.wl), and the
    # file is in the repository's working directory.
    links = re.findall(r'href="([^"]*lattice_search[^"]*)"', section())
    assert links == [WL_URL], links
    assert os.path.isfile(WL)


def q_section_lists_the_calls_and_their_results():
    # Replicata: the items of the section's list of calls (<ul class="calls">).
    # Expectata: one item per call of CALLS, in order: the call in <code>, then ": complete, " when the run is
    # exhaustive, then the number of sequences ("no sequences", "1 sequence" or "N sequences"), as CALLS has them.
    items = re.findall(r'<li>(.*?)</li>', re.search(r'<ul class="calls">(.*?)</ul>', section(), re.S).group(1), re.S)
    assert len(items) == len(CALLS), items
    for item, (call, count, complete) in zip(items, CALLS):
        m = re.match(r'<code>(.*?)</code>: (complete, )?(no|\d+) sequences?\b', item)
        assert m, item
        assert html.unescape(m.group(1)) == call, (m.group(1), call)
        assert bool(m.group(2)) == complete and (0 if m.group(3) == 'no' else int(m.group(3))) == count, (item, count)


def q_section_states_the_dimensions():
    # Replicata: the items of the section's list of searches (<ul class="searches">), each starting with its length in
    # <b>.
    # Expectata: for each (length, d) of DIMS, an item starting with <b>length</b> says <i>d</i> = d, and each d is the
    # count DIMS gives for it.
    items = re.findall(r'<li>(.*?)</li>', re.search(r'<ul class="searches">(.*?)</ul>', section(), re.S).group(1), re.S)
    for n, d, count in DIMS:
        assert d == count, (n, d, count)
        mine = [it for it in items if it.startswith(f'<b>{n}</b>')]
        assert len(mine) == 1 and f'<i>d</i> = {d}' in mine[0], (n, d, mine)


def q_section_says_when_an_empty_result_proves_none():
    # Replicata: the section's text; and latticeSearch[112, 7, -1, "Want" -> Infinity, "MaxNodes" -> 10^6,
    # "TimeLimit" -> 1], an unpruned search of a tree of 285 million nodes that holds 2 sequences (CALLS), cut off.
    # Expectata: the section says an empty list proves there are none only when "complete" is True, and that a search
    # cut off by "MaxNodes" returns False (Stan Wagon read an empty result at 240, order 10, as "no solution",
    # 2026-10-16); and the cut-off search does: every trial stops at 10^6 nodes, and "complete" is False.
    t = text(section())
    assert 'An empty list of sequences proves there are none only when the result\'s "complete" is True' in t, t
    assert 'a search cut off by "MaxNodes" returns False' in t, t
    call = 'latticeSearch[112, 7, -1, "Want" -> Infinity, "MaxNodes" -> 10^6, "TimeLimit" -> 1]'
    comp, trials, nodes = run(f'With[{{r = {call}}}, Print[ExportString[{{r["complete"], r["trials"], r["nodes"]}}, '
                              f'"JSON", "Compact" -> True]]]')
    assert comp is False and trials >= 1 and nodes == trials * 10 ** 6, (comp, trials, nodes)


# ---------------------------------------------------------------------------------------------------------------------
# lattice_search.wl

def q_wl_says_claude_wrote_it():
    # Replicata: lattice_search.wl's first comment.
    # Expectata: it opens the file, and its first paragraph says Claude wrote the code and every comment, and that no
    # human has reviewed them.
    src = open(WL, encoding='utf-8').read()
    assert src.startswith('(* lattice_search.wl\n'), src[:80]
    first = re.sub(r'\s+', ' ', src[:src.index('\n\n', src.index('Written by'))])
    assert 'Written by Claude (Claude Opus 5.5, an AI model made by Anthropic)' in first, first
    assert "The code and every comment in this file are Claude's; no human has reviewed them." in first, first


def q_wl_calls_return_what_the_section_says():
    # Replicata: each call of CALLS, in one Mathematica kernel.
    # Expectata: as many distinct sequences as CALLS says, "complete" as CALLS says, and the dimension
    # Missing[NoIntegerSolution] exactly for 6, 2, 0, a number for the others; the run at 320 ends after at most 100
    # nodes, as the section says ("after a few nodes"), and the run at 112 after 285 million, rounded (seeded, so the
    # same every run of one Mathematica version).
    R = results()
    assert R['latticeSearch[320, 11, -1, "Want" -> Infinity]'][5] <= 100, R['latticeSearch[320, 11, -1, "Want" -> Infinity]'][5]
    n112 = R['latticeSearch[112, 7, -1, "Want" -> Infinity, "MaxNodes" -> 10^9]'][5]
    assert round(n112 / 10 ** 6) == 285 and '285 million nodes' in section(), n112
    for call, count, complete in CALLS:
        sols, sets, comp, dim, trials, nodes, secs = R[call]
        assert len(sols) == count and len({tuple(f) for f in sols}) == count, (call, len(sols))
        assert comp is complete, (call, comp)
        assert (dim == 'Missing[NoIntegerSolution]') == (call == 'latticeSearch[6, 2, 0]'), (call, dim)
        assert dim == 'Missing[NoIntegerSolution]' or int(dim) >= 1, (call, dim)


def q_wl_sequences_check_out():
    # Replicata: every sequence the calls of CALLS and EXTRA return, and their "sets".
    # Expectata: each is a list of n signs +1 and -1, has the symmetry asked for, and has order at least m by exact
    # power sums here; its set is the half of {0, ..., n - 1} where it has the sign it has at 0; and the set a complete
    # run returns is closed under negation (a sequence and its negation have the same order).
    R = results()
    for call, (sols, sets, comp, *_) in R.items():
        assert sets == [[i for i, x in enumerate(f) if x == f[0]] for f in sols], call
        n, m, s = (int(x) for x in re.match(r'latticeSearch\[(\d+), (\d+), (-?\d+)', call).groups())
        for f in sols:
            assert len(f) == n and set(f) <= {1, -1}, (call, f)
            assert s == 0 or f == [s * x for x in reversed(f)], (call, f)
            assert order(f) >= m, (call, order(f))
        if comp: assert {tuple(-x for x in f) for f in sols} == {tuple(f) for f in sols}, call


def q_wl_exhaustive_agrees_with_brute_force():
    # Replicata: the complete runs at 16, 4, 0 (EXTRA) and 48, 6, 1; and every sign vector of length 16, and every
    # symmetric one of length 48 (2^24 left halves), tested here with exact integer power sums.
    # Expectata: the runs return exactly the sequences of order at least 4 and 6 that the brute force finds: Thue-Morse
    # and its negation at 16; Table 5's p48 and its negation at 48.
    R = results()
    brute16 = {f for f in itertools.product((1, -1), repeat=16) if order(f) >= 4}
    assert {tuple(f) for f in R['latticeSearch[16, 4, 0, "Want" -> Infinity]'][0]} == brute16, brute16
    tm = tuple((-1) ** bin(i).count('1') for i in range(16))
    assert brute16 == {tm, tuple(-x for x in tm)}
    x = np.arange(24, dtype=np.int64)
    Wf = np.stack([x ** k + (47 - x) ** k for k in range(6)])   # f = (a, a reversed): sum_j f_j j^k = a . Wf[k]
    assert int(Wf.max()) < 2 ** 40
    low = ((np.arange(2 ** 12, dtype=np.int64)[:, None] >> np.arange(12)[None, :]) & 1) * 2 - 1
    brute48 = set()
    for high in low:                                            # the 2^24 left halves, 2^12 at a time
        halves = np.concatenate([np.broadcast_to(high, (2 ** 12, 12)), low], axis=1)
        brute48 |= {tuple(a + a[::-1]) for a in halves[np.all(halves @ Wf.T == 0, axis=1)].tolist()}
    assert all(order(f) >= 6 for f in brute48)
    assert {tuple(f) for f in R['latticeSearch[48, 6, 1, "Want" -> Infinity]'][0]} == brute48, len(brute48)
    p48 = tuple(from_hex('C27D8C', 6))
    assert brute48 == {p48, tuple(-v for v in p48)}


def q_wl_known_examples_lie_in_the_coset():
    # Replicata: latticeSystem for each example of KNOWN (n, its order, its symmetry): its P, the basis B of 2K and t.
    # Expectata: the example's free signs a (its first n/2) satisfy P.a == f, and a - t is an integer combination of
    # the rows of B (solved here in exact rationals): the example is one of the vectors the enumeration looks for.
    calls = [f'latticeSystem[{n}, {m}, {s}]' for _, n, m, s in KNOWN]
    body = ', '.join(f'With[{{y = {c}}}, {{y["P"], y["B"], y["t"]}}]' for c in calls)
    out = run(f'Print[ExportString[{{{body}}}, "JSON", "Compact" -> True]]')
    for (hx, n, m, s), (P, B, t) in zip(KNOWN, out):
        f = from_hex(hx, m)
        assert order(f) == m, (n, order(f))
        a = f[:n // 2]
        assert [sum(r * x for r, x in zip(row, a)) for row in P] == f, n
        G = [[Fraction(sum(u * v for u, v in zip(b1, b2))) for b2 in B] for b1 in B]
        rhs = [Fraction(sum(u * (ai - ti) for u, ai, ti in zip(b, a, t))) for b in B]
        c = solve(G, rhs)
        assert all(x.denominator == 1 for x in c), n
        assert [ti + sum(int(ck) * b[j] for ck, b in zip(c, B)) for j, ti in enumerate(t)] == a, n


def solve(G, b):
    """The solution of the square system G.x == b, exactly (Gauss-Jordan over Fractions)."""
    k = len(G)
    A = [row[:] + [y] for row, y in zip(G, b)]
    for c in range(k):
        p = next(i for i in range(c, k) if A[i][c] != 0)
        A[c], A[p] = A[p], A[c]
        A[c] = [x / A[c][c] for x in A[c]]
        for i in range(k):
            if i != c and A[i][c] != 0: A[i] = [x - A[i][c] * y for x, y in zip(A[i], A[c])]
    return [A[i][k] for i in range(k)]


def q_wl_exports_only_its_two_functions():
    # Replicata: Names["LatticeSearch`*"] after Get[lattice_search.wl], and Stan's package's order[A_] defined first.
    # Expectata: the context exports latticeSearch and latticeSystem only, and a Global` order defined before Get still
    # gives its own answer afterwards (the .wl's helpers live in LatticeSearch`Private`).
    p = script('order[A_] := "stan";', f'Get["{WL}"];',
               'Print[ExportString[{Sort[Names["LatticeSearch`*"]], order[{0, 3}]}, "JSON", "Compact" -> True]]',
               timeout=600)
    lines = p.stdout.strip().splitlines()
    assert p.returncode == 0 and lines, (p.returncode, p.stdout[-3000:], p.stderr[-3000:])
    assert json.loads(lines[-1]) == [['latticeSearch', 'latticeSystem'], 'stan'], lines[-1]


def q_wl_fails_loudly():
    # Replicata: latticeSearch[7, 3, 0] (an odd length) in Mathematica, inside CheckAbort.
    # Expectata: it aborts, after the message latticeSearch::fail naming the check that failed, instead of returning
    # anything.
    p = script(f'Get["{WL}"];', 'Print[CheckAbort[latticeSearch[7, 3, 0], "aborted"]]', timeout=600)
    out = re.sub(r'\s+', ' ', p.stdout + p.stderr)
    assert 'latticeSearch::fail: Check failed: n is even, m >= 1, and s is -1, 0 or 1' in out, out
    assert p.stdout.strip().splitlines()[-1] == 'aborted', p.stdout


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
