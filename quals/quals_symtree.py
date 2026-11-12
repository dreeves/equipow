#!/usr/bin/env python3
"""Quals for proofs/symtree.py (Fable 5.2, 2026-11-11; dreeves's README, [SYC]: "cells for which we know they're red
conditional on the Symmetry Conjecture being true, i.e., we've proven there's no symmetric or antisymmetric
bipartition"): the check of a symmetric-only form tree, a proof that no s-symmetric sequence of length n has order m.
Run: python3 -B quals/quals_symtree.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).

Vocabulary, each term defined once here (proofs/symtree.py's docstring states the argument):
  sequence      a_0..a_(n-1), each +1 or -1; its order is the largest k with sum_p a_p p^e = 0 for every e < k.
  s-symmetric   a_(n-1-p) = s a_p for every p: symmetric for s = 1, antisymmetric for s = -1.
  residue sums  D_r = the sum of the a_p with p = r mod M, r = 0..M-1; sigma(r) = (n-1-r) mod M, the class of the mirror
                of a position of class r.  An s-symmetric sequence has D_sigma(r) = s D_r.
  row           (M, value, weights): the form sum_r weights_r D_r pinned at value (proofs/formtree.py's pinned row).
  start node    a set of rows; a symmetric-only proof's start nodes pin an s-symmetric vector of residue sums at each
                modulus of the chain (3, 5, 7) and, at further moduli, symmetry's own rows at 0: e_r - s e_sigma(r)
                where sigma(r) != r, and e_r where sigma(r) = r and s = -1.
  kept proof    a directory: nodes.json ({"cell": "N:M", "s": s, "nodes": [{"name", "rows"}]}) and verdicts.jsonl, the
                verdicts of fkernel on the tasks under those start nodes, as proofs/formtree.py's assemble reads them.
  fixture       searches/formtree/fixtures/sym_432_12: a whole kept proof, 6 start nodes, 10 nodes, made 2026-11-11 by
                scratch/s480-20261111 (no symmetric sequence of length 432 has order 12; none at all has, m*(432) = 11);
                and antisym_480_13: the two start nodes of the antisymmetric search at 480:13, with no verdicts.

History: red against a missing proofs/symtree.py on 2026-11-11, then green."""
import copy, importlib.util, json, os, shutil, subprocess, sys, tempfile, time, traceback
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'searches' / 'formtree' / 'fixtures'
SYM, ANTI = FIX / 'sym_432_12', FIX / 'antisym_480_13'
sys.path.insert(0, str(ROOT / 'pagegen')); sys.path.insert(0, str(ROOT / 'engine'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def symtree(): return load('symtree', ROOT / 'proofs' / 'symtree.py')


def damaged(directory, change):
    """A copy of a kept proof with change(nodes.json's data, the verdicts' list) applied, in a new temporary directory."""
    d = Path(tempfile.mkdtemp(prefix='symtree-quals-'))
    data = json.loads((directory / 'nodes.json').read_text())
    verdicts = [json.loads(line) for line in open(directory / 'verdicts.jsonl')] if (directory / 'verdicts.jsonl').exists() else []
    change(data, verdicts)
    (d / 'nodes.json').write_text(json.dumps(data))
    (d / 'verdicts.jsonl').write_text(''.join(json.dumps(v) + '\n' for v in verdicts))
    return d


def refused(directory, change):
    """symtree.check's error on the damaged copy; an accepted one fails the qual."""
    d = damaged(directory, change)
    try:
        symtree().check(str(d))
    except (ValueError, AssertionError, KeyError) as e:
        return f'{type(e).__name__}: {e}'
    finally:
        shutil.rmtree(d)
    raise AssertionError('a damaged proof was accepted')


def sigma(n, M, r): return (n - 1 - r) % M


def q_the_fixture_proof_is_accepted():
    # Replicata: symtree.check on the fixture sym_432_12, a whole kept proof.
    # Expectata: it returns the cell, the symmetry and assemble's totals: 432, 12, s = 1; 6 tasks, 10 nodes, all closed.
    n, m, s, total = symtree().check(str(SYM))
    assert (n, m, s) == (432, 12, 1), (n, m, s)
    assert (total['tasks'], total['nodes'], total['closed']) == (6, 10, 10), total


def q_isolated_checker_runs():
    # Replicata: python3 -B -I -S proofs/symtree.py on the fixture: no site packages, no environment.
    # Expectata: exit 0 and one line that names the claim's length, order and symmetry.
    r = subprocess.run([sys.executable, '-B', '-I', '-S', str(ROOT / 'proofs' / 'symtree.py'), str(SYM)], text=True, capture_output=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.count('\n') == 1 and 'VERIFIED' in r.stdout and '432' in r.stdout and '12' in r.stdout, r.stdout


def q_start_nodes_are_what_symmetry_gives():
    # Replicata: each fixture's start nodes; the chart's own enumerator of residue sums (engine/residues.py, which
    # proofs/symtree.py does not use: it uses proofs/pintree.py's) at 3, 5 and 7.
    # Expectata: the s-symmetric vectors at 3, 5, 7 that the chart's enumerator lists are, up to sign, exactly the
    # chain vectors of the start nodes, one node per pair; and every other row of a node is one of symmetry's rows.
    import residues
    for directory, count in ((SYM, 6), (ANTI, 2)):
        data = json.loads((directory / 'nodes.json').read_text()); n, m = map(int, data['cell'].split(':')); s = data['s']
        assert s == (1 if m % 2 == 0 else -1) and len(data['nodes']) == count, (data['cell'], s, len(data['nodes']))
        sym = {M: [v for v in residues.residue_vectors(n, M, m, None, residues.Budget(10 ** 7), 'natural')
                   if all(v[sigma(n, M, r)] == s * v[r] for r in range(M))] for M in (3, 5, 7)}
        triples = {(a, b, c) for a in sym[3] for b in sym[5] for c in sym[7]}
        neg = lambda t: tuple(tuple(-x for x in v) for v in t)
        assert all(neg(t) in triples for t in triples)
        got = []
        for node in data['nodes']:
            vec = {M: [None] * M for M in (3, 5, 7)}
            for M, value, w in node['rows']:
                if M in vec:
                    assert sorted(w) == [0] * (M - 1) + [1], (M, w)
                    vec[M][w.index(1)] = value
                else:
                    nz = [r for r in range(M) if w[r]]
                    pair = len(nz) == 2 and sigma(n, M, nz[0]) == nz[1] and w[nz[0]] * w[nz[1]] == -s and abs(w[nz[0]]) == 1
                    fixed = len(nz) == 1 and sigma(n, M, nz[0]) == nz[0] and s == -1 and abs(w[nz[0]]) == 1
                    assert value == 0 and (pair or fixed), (data['cell'], M, value, w)
            got.append(tuple(tuple(vec[M]) for M in (3, 5, 7)))
        assert all(t in triples for t in got) and len(set(got)) == len(got), got
        assert {frozenset((t, neg(t))) for t in got} == {frozenset((t, neg(t))) for t in triples}, (data['cell'], len(got), len(triples))


def q_symmetric_sequences_meet_symmetry_s_rows():
    # Replicata: the page's sequences (pagegen/mstar.py's build) at 480, 672, 432, 288, 240, 528, 720 and 1008, each
    # (-1)^m-symmetric for its exact order m; symtree's own test of a row (symmetric_row).
    # Expectata: for every modulus M from 2 to 40, each of symmetry's rows, as the checker recognizes them, is 0 on the
    # sequence (the lemma's first step, on real sequences); and a row the checker must not take for one is not 0 on
    # some of them: e_r - s e_t with t another class than sigma(r).
    import mstar
    st = symtree(); bad = 0
    for N in (480, 672, 432, 288, 240, 528, 720, 1008):
        a = list(mstar.build(N)); m = mstar.order(a); s = 1 if m % 2 == 0 else -1
        assert a == [s * x for x in reversed(a)], N
        for M in range(2, 41):
            D = [sum(a[r::M]) for r in range(M)]
            for r in range(M):
                t = sigma(N, M, r)
                # symmetry's row of the class r: e_r - s e_t where t is another class, e_r where t = r and s = -1, none where t = r and s = 1
                rows = [[int(c == r) - s * int(c == t) for c in range(M)]] * (t != r) + [[int(c == r) for c in range(M)]] * (t == r and s == -1)
                for w in rows:
                    assert st.symmetric_row(N, s, M, tuple(w)) and st.symmetric_row(N, s, M, tuple(-x for x in w)), (N, M, r, w)
                    assert sum(x * y for x, y in zip(w, D)) == 0, (N, M, r)
                u = (t + 1) % M                                        # another class than the mirror's
                w = [int(c == r) - s * int(c == u) for c in range(M)]
                assert not st.symmetric_row(N, s, M, tuple(w)), (N, M, r, u, w)
                bad += sum(x * y for x, y in zip(w, D)) != 0
            assert not st.symmetric_row(N, s, M, (0,) * M) and not st.symmetric_row(N, s, M, (2,) + (0,) * (M - 1)), (N, M)
    assert bad > 100, bad


def q_a_missing_start_node_is_refused():
    # Replicata: the fixture with its last start node left out; and with its verdict left out too.
    # Expectata: refused both times: a symmetric vector of the chain has no start node.
    def drop(data, verdicts): data['nodes'].pop()
    def drop_both(data, verdicts):
        name = data['nodes'].pop()['name']; verdicts[:] = [v for v in verdicts if v['start'] != name]
    for change in (drop, drop_both):
        assert 'start node' in refused(SYM, change), refused(SYM, change)


def q_a_row_that_symmetry_does_not_give_is_refused():
    # Replicata: the fixture with one row of its first start node changed: (a) a symmetry row's value 1 for 0; (b) its
    # second class moved to a class that is not the mirror's; (c) a unit row at a class that is not its own mirror; (d)
    # a chain value changed; (e) the name of the node left as it was while a row was dropped.
    # Expectata: each refused.
    def at(i, f):
        def change(data, verdicts):
            rows = data['nodes'][0]['rows']; k = next(j for j, r in enumerate(rows) if r[0] == 11) + i; rows[k] = f(rows[k])
        return change
    def moved(row):
        M, v, w = row; w = list(w); j = max(r for r in range(M) if w[r]); x = w[j]; w[j] = 0; w[(j + 1) % M if w[(j + 1) % M] == 0 else (j + 2) % M] = x
        return [M, v, w]
    def chain(data, verdicts): data['nodes'][0]['rows'][3][1] += 2
    def dropped(data, verdicts): data['nodes'][0]['rows'].pop()
    for change in (at(0, lambda r: [r[0], 1, r[2]]), at(1, moved), at(2, lambda r: [r[0], 0, [1] + [0] * (r[0] - 1)]), chain, dropped):
        refused(SYM, change)


def q_verdicts_that_do_not_close_are_refused():
    # Replicata: the fixture with (a) a verdict left out; (b) a verdict's open count 1; (c) a verdict refused (ok false);
    # (d) no verdicts at all; and the fixture antisym_480_13, which has none.
    # Expectata: each refused: the start nodes are right and nothing shows them closed.
    def out(data, verdicts): verdicts.pop()
    def opened(data, verdicts): verdicts[0]['open'] = 1
    def bad(data, verdicts): verdicts[0]['ok'] = False; verdicts[0]['why'] = 'made up'
    def none(data, verdicts): verdicts.clear()
    for change in (out, opened, bad, none):
        refused(SYM, change)
    assert 'verdict' in refused(ANTI, lambda data, verdicts: None)


def q_the_wrong_symmetry_or_cell_is_refused():
    # Replicata: the fixture with (a) s = -1 for 1; (b) the cell 432:13 for 432:12; (c) the cell 480:12.
    # Expectata: each refused: s is (-1)^m, and the start nodes are those of the cell stated.
    def sign(data, verdicts): data['s'] = -1
    def order(data, verdicts): data['cell'] = '432:13'
    def length(data, verdicts): data['cell'] = '480:12'
    for change in (sign, order, length):
        refused(SYM, change)


def q_two_nodes_of_one_pair_are_refused():
    # Replicata: the fixture with a copy of its first start node negated at 3, 5 and 7 added (its name made right, its
    # verdict a copy too).
    # Expectata: refused: one start node per pair v, -v.
    st = symtree()
    def twice(data, verdicts):
        node = copy.deepcopy(data['nodes'][0])
        for row in node['rows']:
            if row[0] in (3, 5, 7): row[1] = -row[1]
        n, m = map(int, data['cell'].split(':'))
        node['name'] = st.ft.node_name(n, m, 0, [(M, v, tuple(w)) for M, v, w in node['rows']])
        data['nodes'].append(node)
        verdicts.append(dict(next(v for v in verdicts if v['start'] == data['nodes'][0]['name']), start=node['name']))
    assert 'pair' in refused(SYM, twice), refused(SYM, twice)


def q_every_kept_proof_is_accepted_and_named():
    # Replicata: symtree.TREES, the kept proofs the program lists, and the directories under searches/formtree/cells
    # whose names end in _sym or _antisym.
    # Expectata: they are the same directories, each named N_M_sym or N_M_antisym for its own cell and symmetry, and
    # symtree.check accepts each with no open node.
    st = symtree()
    cells = ROOT / 'searches' / 'formtree' / 'cells'
    there = sorted(str(p.relative_to(ROOT)) for p in cells.iterdir() if p.name.endswith(('_sym', '_antisym')))
    assert sorted(st.TREES) == there, (st.TREES, there)
    for d in st.TREES:
        n, m, s, total = st.check(str(ROOT / d))
        assert Path(d).name == f'{n}_{m}_{"sym" if s == 1 else "antisym"}', (d, n, m, s)
        assert total['tasks'] > 0 and total['nodes'] == total['closed'] > 0, total


def main():
    names = sys.argv[1:] or [k for k in globals() if k.startswith('q_')]
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
