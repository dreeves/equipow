#!/usr/bin/env python3
"""Quals for the tilted search (searches/tilted/), about 5 minutes on one core.  Run from the repository's root, after `make` in searches/tilted and in searches/pinned:
    python3 -B quals/quals_tilted.py [qual ...]
It needs numpy, mpmath and fpylll.  The tool came before these quals, so they were not seen red against it; the page's quals for its results were."""
import sys
sys.dont_write_bytecode = True
import itertools, json, os, re, subprocess, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILTED = os.path.join(ROOT, 'searches', 'tilted')


def decode(code, n, m):
    """The paper's Table 5 convention: the left half of the signs from the hex, 1 = +1, zero-filled on the left to n / 2 bits, then the rest by (-1)^m symmetry."""
    v, half = int(code, 16), n // 2
    assert v >> half == 0 and 4 * len(code) - half < 4, (n, len(code))
    left = [2 * (v >> (half - 1 - i) & 1) - 1 for i in range(half)]
    return left + [(-1) ** m * t for t in reversed(left)]


def order_div(f):
    """The multiplicity of x - 1 in f, by repeated synthetic division in plain integers."""
    k, c = 0, list(f)
    while not sum(c): c, k = list(itertools.accumulate(c[:-1])), k + 1
    return k


def witness_lines(name):
    return [json.loads(line) for line in open(os.path.join(TILTED, 'witnesses', name), encoding='utf-8')]


def q_witness_files_have_their_orders():
    # Replicata: searches/tilted/witnesses/: the two results of 2026-11-04, 672:13 and 1440:16.
    # Expectata: each code decodes to a balanced sequence of its length, of order exactly m by synthetic division and by power sums, (-1)^m-symmetric; its record names n, m, seed and pins.
    # Resultata before: the results were only in a scratch directory.
    for name, n, m, seed in (('witness_672_13.jsonl', 672, 13, 810), ('witness_1440_16.jsonl', 1440, 16, 1401)):
        lines = witness_lines(name)
        assert len(lines) == 1 and (lines[0]['n'], lines[0]['m'], lines[0]['order'], lines[0]['seed']) == (n, m, m, seed), lines
        f = decode(lines[0]['code'], n, m)
        assert len(f) == n and sum(f) == 0 and order_div(f) == m, (n, m)
        assert all(sum(a * i ** k for i, a in enumerate(f)) == 0 for k in range(m)) and sum(a * i ** m for i, a in enumerate(f)) != 0, (n, m)
        assert all(f[n - 1 - i] == (-1) ** m * f[i] for i in range(n)), (n, m)


def q_the_page_shows_the_witnesses():
    # Replicata: index.html's <code> elements, and the witness files.
    # Expectata: the page's codes 672:13 and 1440:16 are the files' codes.
    # Resultata before: the page had neither.
    page = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    for name, id_ in (('witness_672_13.jsonl', '672:13'), ('witness_1440_16.jsonl', '1440:16')):
        assert re.findall(rf'<code id="{id_}">([0-9A-F]+)</code>', page) == [witness_lines(name)[0]['code']], id_


def rediscovers(n, m, W, qs, sag, seed):
    """Runs the search from an empty directory until its first witness (at most 260 s of search) and returns the witnesses' records, checked here in plain integers."""
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, '-B', '-u', os.path.join(TILTED, 'tilted.py'), str(n), str(m), str(W), '1.1', qs, '300', '260', '--kout', '30', '--stop', '1', '--gumbel', '0',
                            '--field', '0.35', '--floor', '1', '--sag', str(sag), '--seed', str(seed), '--every', '1000', '--maxnodes', '1e8'],
                           cwd=d, capture_output=True, text=True, timeout=600, env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
        assert r.returncode == 0, r.stderr[-2000:]
        path = os.path.join(d, f'found_{n}_{m}.jsonl')
        assert os.path.exists(path), r.stdout[-2000:]
        found = [json.loads(line) for line in open(path, encoding='utf-8')]
    for w in found:
        f = decode(w['code'], n, m)
        assert len(f) == n and sum(f) == 0 and order_div(f) == w['order'] >= m, (n, m, w['code'])
    return found


def q_the_search_finds_1008_13():
    # Replicata: the search at 1008, order 13, an antisymmetric cell, W = 150, pins 8, 5, 7, 11, 13, 17, 19, seed 1, in an empty directory.
    # Expectata: within 260 s of search it writes at least one witness of order at least 13, checked here in plain integers.  (On 2026-11-04, on a loaded machine: 28 s of setup, then under 1 s.)
    # Resultata before: the tool had no control in the repository.
    assert rediscovers(1008, 13, 150, '8,5,7,11,13,17,19', 0.4, 1)


def q_the_search_finds_544_10():
    # Replicata: the search at 544, order 10, a symmetric cell, W = 110, pins 8, 9, 5, 7, 11, 13, 17, 19, seed 3, in an empty directory.
    # Expectata: within 260 s of search it writes at least one witness of order at least 10, checked here in plain integers.  (On 2026-11-04, on a loaded machine: 30 s of setup, then 11 s.)
    # Resultata before: the tool had no control in the repository.
    assert rediscovers(544, 10, 110, '8,9,5,7,11,13,17,19', 0.3, 3)


if __name__ == '__main__':
    # TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
    if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
    names = sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]
    failed = 0
    for name in names:
        t = time.time()
        try:
            globals()[name]()
            print(f'Claude: "PASSED" {name} ({time.time() - t:.1f} s)', flush=True)
        except AssertionError as e:
            failed += 1
            print(f'Claude: "FAILED" {name}: {str(e)[:500]}', flush=True)
    raise SystemExit(1 if failed else 0)
