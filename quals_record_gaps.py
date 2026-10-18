#!/usr/bin/env python3
"""Quals for record_gaps.wl, the Mathematica script that makes the table of Theorem 1's constructions (Stan Wagon asked
for it, extending his table of the first two rows, 2026-10-18), and for its link on index.html.
Run: python3 -B quals_record_gaps.py [name ...] (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The quals of the .wl run it with wolframscript (quals_lattice_search's script and seats) and check what it returns
against pow2.js, the page's data for the chart of powers of 2, formatted here independently.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, shutil, tempfile, itertools, traceback, time
import quals_lattice_search as ls          # read only: script (wolframscript on a temporary file) and seats

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
WL = os.path.join(HERE, 'record_gaps.wl')
WL_URL = 'https://raw.githubusercontent.com/dreeves/equipow/main/record_gaps.wl'
POW2_JS = os.path.join(HERE, 'pow2.js')
HEADER = ['Record gaps', 'The power of 2', 'The order']        # Stan Wagon's, byte for byte
THEOREM_KS = [17, 27, 34, 38, 46, 52, 57, 66]                  # Theorem 1's alternative form on index.html
# Stan Wagon's two rows (his table of 2026-10-18), one product per line (dreeves, 2026-10-18), as text: a superscript
# a^b, SpanFromAbove where the first column's cell spans the lines below it
STAN_ROWS = [['m^*(2^17) ≥ 18', '112·800', '7 + 11 = 18'],
             ['SpanFromAbove', '+ 2·48·432', '1 + 6 + 11 = 18'],
             ['m^*(2^27) ≥ 29', '368^2·800', '2·9 + 11 = 29'],
             ['SpanFromAbove', '+ 192^2·432', '2·9 + 11 = 29'],
             ['SpanFromAbove', '+ 48·432·480', '6 + 11 + 12 = 29']]
# the table as text: each cell, superscripts as a^b and styles dropped, in OutputForm on one line
TEXT = ('text[e_] := ToString[e //. {Superscript[a_, b_] :> Row[{a, "^", b}], Style[x_, ___] :> x}, OutputForm, '
        'PageWidth -> Infinity];')
RUNS = {}


def page(): return open(INDEX, encoding='utf-8').read()


def pow2_cols():
    src = open(POW2_JS, encoding='utf-8').read()
    return json.loads(src[src.index('{'):src.rindex('}') + 1])['cols']


def records():
    """pow2.js's record gaps: for g = 1, 2, ..., [k, products], k the least with lo - k >= g, its loWhy's join."""
    cols, out = pow2_cols(), []
    for g in itertools.count(1):
        ks = [k for k in range(1, len(cols) + 1) if cols[k - 1][0] - k >= g]
        if not ks: return out
        why = cols[ks[0] - 1][2]
        assert why[0] == 'joins', (ks[0], why)
        out.append([ks[0], why[1]])


def rows():
    """The table's rows below its header, formatted here from records(): per record gap g, the bound m*(2^k) >= k + g
    on the first line, then per product a line of its length (its blocks ascending by length, a repeated one as a
    power, a + before all but the first) and its order (its blocks' orders in that order, a repeated one as count·order,
    then = their sum)."""
    out = []
    for g, (k, ps) in enumerate(records(), 1):
        for i, p in enumerate(ps):
            fs = [(n, m, len(list(run))) for (n, m), run in itertools.groupby(sorted(map(tuple, p)))]
            length = '·'.join(f'{n}^{c}' if c > 1 else f'{n}' for n, m, c in fs)
            order = ' + '.join(f'{c}·{m}' if c > 1 else f'{m}' for n, m, c in fs) + f' = {sum(m for _, m in p)}'
            out.append([f'm^*(2^{k}) ≥ {k + g}' if i == 0 else 'SpanFromAbove', ('+ ' if i else '') + length, order])
    return out


def run(code, wl=WL):
    """code's JSON line, printed last, after r = Get[wl] in one wolframscript run (r: what Get returned)."""
    if (code, wl) not in RUNS:
        p = ls.script(TEXT, f'r = CheckAbort[Get["{wl}"], "ABORTED"];', code)
        lines = p.stdout.strip().splitlines()
        assert p.returncode == 0 and lines and lines[-1].startswith(('[', '{', '"')), (p.returncode, p.stdout[-3000:],
                                                                                        p.stderr[-3000:])
        RUNS[code, wl] = (json.loads(lines[-1]), p.stdout)
    return RUNS[code, wl]


# what Get returned: its head, its rows as text and its options, as one JSON line (ExportString gives UTF-8 bytes, which
# FromCharacterCode decodes, so that Print encodes each character once)
TABLE = ('Print[FromCharacterCode[ToCharacterCode[ExportString[<|"head" -> ToString[Head[r]], "rows" -> Map[text, First[r], {2}], '
         '"options" -> KeyMap[ToString, Map[ToString[#, InputForm] &, Association[Rest[List @@ r]]]]|>, "JSON", '
         '"Compact" -> True]], "UTF-8"]]')


# ---------------------------------------------------------------------------------------------------------------------
# record_gaps.wl
def q_wl_says_claude_wrote_it():
    # Replicata: record_gaps.wl's first comment.
    # Expectata: it opens the file, as lattice_search.wl's does: its first paragraph says Claude wrote the code and
    # every comment, for Stan Wagon at Danny Reeves's request, and that no human has reviewed them; its second says the
    # table's form, header row and first two rows are Stan Wagon's but for one product per line (Danny Reeves's choice).
    src = open(WL, encoding='utf-8').read()
    assert src.startswith('(* record_gaps.wl\n'), src[:80]
    paras = [re.sub(r'\s+', ' ', p) for p in src[:src.index('*)')].split('\n\n')]
    assert 'Written by Claude (Claude Opus 5.5, an AI model made by Anthropic) on 2026-10-18, for Stan Wagon, at Danny ' \
           "Reeves's request." in paras[1], paras[1]
    assert "The code and every comment in this file are Claude's; no human has reviewed them." in paras[1], paras[1]
    assert "Stan Wagon's" in paras[2] and 'one product per line' in paras[2] and "Danny Reeves's choice" in paras[2], paras[2]


def q_wl_records_are_pow2_s():
    # Replicata: the records list in record_gaps.wl, read as text; pow2.js's record gaps (records()).
    # Expectata: the same list, record for record and block for block: for each record gap g, its least k and the
    # join of products that pow2.py found there, the products and their blocks in pow2.js's order; and their k are
    # Theorem 1's (17, 27, 34, 38, 46, 52, 57, 66).
    src = open(WL, encoding='utf-8').read()
    m = re.search(r'^records = (\{.*?\});$', src, re.S | re.M)
    assert m, 'no records = {...}; line'
    got = json.loads(m.group(1).replace('{', '[').replace('}', ']'))
    assert got == records(), (got, records())
    assert [k for k, _ in got] == THEOREM_KS, [k for k, _ in got]


def q_wl_returns_the_table():
    # Replicata: Get["record_gaps.wl"] in wolframscript; its result's rows as text (TEXT) and its options.
    # Expectata: a Grid whose first row is Stan Wagon's header (HEADER), then rows() exactly: Stan Wagon's two rows
    # (STAN_ROWS) first, then the other six record gaps', one product per line; with Stan Wagon's options (BaseStyle
    # Times 14, Background RGBColor[1, 1, .8], Spacings {2, 1}), every vertical divider, and horizontal dividers only
    # above and below the header and below each record gap's last line; columns centered, left, left.
    out, _ = run(TABLE)
    assert out['head'] == 'Grid', out['head']
    assert out['rows'][0] == HEADER and out['rows'][1:] == rows(), (out['rows'][:3], rows()[:3])
    assert out['rows'][1:6] == STAN_ROWS, out['rows'][1:6]
    ends = list(itertools.accumulate(len(ps) for _, ps in records()))
    want = {'Dividers': '{All, {' + ', '.join(f'{i} -> True' for i in [1, 2] + [2 + e for e in ends]) + '}}',
            'Alignment': '{{Center, Left, Left}, Baseline}',
            'BaseStyle': '{FontFamily -> "Times", 14}', 'Background': 'RGBColor[1, 1, 0.8]', 'Spacings': '{2, 1}'}
    assert out['options'] == want, (out['options'], want)


def q_wl_stops_on_a_wrong_row():
    # Replicata: copies of record_gaps.wl with one datum wrong: 2^17's first product 112·801 in place of 112·800 (its
    # lengths no longer sum to 2^17), and 2^27's last block {480, 11} in place of {480, 12} (its least order 28 < 29).
    # Expectata: each prints its error line naming the row and returns no table (it aborts).
    src = open(WL, encoding='utf-8').read()
    d = tempfile.mkdtemp(prefix='record-gaps-quals-')
    try:
        for old, new, says in (('{17, {{{112, 7}, {800, 11}}', '{17, {{{112, 7}, {801, 11}}',
                                "the products' lengths in the row of 2^17 do not sum to 2^17"),
                               ('{432, 11}, {480, 12}}}}', '{432, 11}, {480, 11}}}}',
                                'the least order in the row of 2^27 is 28, not 29')):
            assert src.count(old) == 1, old
            path = os.path.join(d, f'wrong{len(says)}.wl')
            open(path, 'w', encoding='utf-8').write(src.replace(old, new))
            out, stdout = run('Print[ExportString[ToString[r], "JSON"]]', path)
            assert out == 'ABORTED' and f'Claude: "record_gaps.wl stopped: {says}"' in stdout, (out, stdout[-800:])
    finally:
        shutil.rmtree(d)


# ---------------------------------------------------------------------------------------------------------------------
# Its link on index.html
def q_page_links_the_wl():
    # Replicata: index.html's section "Bounds on m*(2^k) − k" (pow2), and the repository's files.
    # Expectata: right after Theorem 1's two paragraphs, a TODO comment, then one paragraph of Claude's copy
    # (Claude: "…") holding the section's only link to record_gaps.wl, at its raw GitHub address (as the page links
    # proof512.wl and lattice_search.wl); the file is in the repository's working directory.
    sec = re.search(r'<section class="pow2".*?</section>', page(), re.S).group(0)
    m = re.search(r'</p>\n  <p>or <b>Theorem 1\.</b>.*?</p>\n  <!-- TODO: [^\n]*-->\n  <p>Claude: "([^\n]*)"</p>\n', sec)
    assert m, sec[:1500]
    assert re.findall(r'href="([^"]*record_gaps[^"]*)"', sec) == [WL_URL] and WL_URL in m.group(1), m.group(1)
    assert os.path.isfile(WL)


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
