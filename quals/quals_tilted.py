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


def q_the_repeat_filter_is_exact_and_small():
    # Replicata: tilted.first_sight, fed 200,000 distinct 16-byte sign words (the two 64-bit words of 74 outer signs, as at 528:12 with W = 190), each twice, under tracemalloc.
    # Expectata: True exactly the first time a word is offered, so a repeat within one beam's batch or a later one is dropped and nothing new is; the filter holds under 64 MiB.
    # Resultata before (2026-11-27): a bitmap over 31 bits of a hash, 256 MiB in every process, with collisions. Its pages hold a few set bits each, so the system compressed them, and every lookup could fault: the ten 528:12 solvers ran at 0.21-0.25 of a core each.
    import tracemalloc
    sys.path.insert(0, TILTED)
    import numpy as np
    import tilted
    words = np.random.default_rng(1).integers(0, 1 << 63, size=(200_000, 2), dtype=np.uint64)
    assert len({w.tobytes() for w in words}) == len(words)
    seen = set()
    tracemalloc.start()
    first = [tilted.first_sight(seen, w.tobytes()) for w in words]
    again = [tilted.first_sight(seen, w.tobytes()) for w in words]
    held = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert all(first) and not any(again), (sum(first), sum(again))
    assert held < 64 << 20, held
    batch = [words[0], words[1], words[0], words[2]]
    fresh = set()
    assert [tilted.first_sight(fresh, w.tobytes()) for w in batch] == [True, True, False, True]


def sweeps(d, n, m, W, qs, K, count, cap, floor, sag):
    """Runs sweep.py in the directory d on the least-cost pins and returns its exit status, its log's lines and its found file's."""
    sys.path.insert(0, os.path.join(ROOT, 'searches', 'pinned'))
    import pinned_problem
    prof = os.path.join(d, 'profile.json')
    with open(prof, 'w', encoding='utf-8') as f:
        json.dump({str(q): ds for q, ds in pinned_problem.default_profiles(n, m, [int(q) for q in qs.split(',')], log=lambda *x: None)}, f)
    log, found = os.path.join(d, 'sweep.jsonl'), os.path.join(d, 'found.jsonl')
    r = subprocess.run([sys.executable, '-B', os.path.join(TILTED, 'sweep.py'), str(n), str(m), str(W), qs, prof, str(K), str(count), log, found,
                        '--floor', str(floor), '--sag', str(sag), '--cap', str(cap)],
                       cwd=d, capture_output=True, text=True, timeout=900, env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
    lines = lambda path: [json.loads(line) for line in open(path, encoding='utf-8')] if os.path.exists(path) else []
    return r, lines(log), lines(found)


def q_the_sweep_takes_each_coset_once_and_resumes():
    # Replicata: sweep.py at 480, order 14, a symmetric cell with no symmetric sequence (searches/formtree/cells/480_14_sym), W = 190, pins 8, 9, 5, 7, 11, 13, a list of the 600 best cosets, a node budget of 100,000 each: 250 cosets, then 600 on the same log; and 600 in one run in another directory.
    # Expectata: every run ends with status 0 and no witness. A log's chunks start at 0 and each begins where the last ended, 600 cosets in all; every line names one list (digest, K) and the profile's whole mass, and the masses swept add to less than it. The run that went on from 250 has the one run's chunks, node for node: the list is the same list each time, and nothing is enumerated twice.
    # Resultata before (2026-11-27): the search drew its cosets at random, a visit at a time, and by the ninth visit to a profile 72% of them were cosets it had enumerated before.
    def same(rows): return [(r['first'], r['last'], r['nodes'], r['capped'], r['mass'], r['digest'], r['K'], r['total']) for r in rows]
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        r1, part, f1 = sweeps(a, 480, 14, 190, '8,9,5,7,11,13', 600, 250, 100000, 4, 0.4)
        assert r1.returncode == 0 and [(x['first'], x['last']) for x in part] == [(0, 249)] and not f1, (r1.stderr[-2000:], part)
        r2, resumed, f2 = sweeps(a, 480, 14, 190, '8,9,5,7,11,13', 600, 600, 100000, 4, 0.4)
        r3, whole, f3 = sweeps(b, 480, 14, 190, '8,9,5,7,11,13', 600, 600, 100000, 4, 0.4)
        assert r2.returncode == 0 and r3.returncode == 0 and not f2 and not f3, (r2.stderr[-2000:], r3.stderr[-2000:])
    assert [(x['first'], x['last']) for x in whole] == [(0, 249), (250, 499), (500, 599)], whole
    assert same(resumed) == same(whole) and same(resumed[:1]) == same(part)
    assert len({(x['digest'], x['K'], x['total']) for x in resumed}) == 1 and [x['count'] for x in resumed] == [250, 600, 600], resumed
    assert all(x['nodes'] > 0 and x['mass'] > 0 for x in whole) and 0 < sum(x['mass'] for x in whole) < whole[0]['total']
    assert whole[0]['mass'] > whole[1]['mass'], 'the list is in order of mass'


def q_two_sweeps_cannot_share_a_log():
    # Replicata: sweep.py at 480, order 14 (as above: 250 cosets of the 600 best, 100,000 nodes each) on a log that this process holds locked; then again with the lock let go.
    # Expectata: the first run fails and writes nothing to the log: a sweep holds its log locked while it runs, so a second one started on the same list by mistake stops at once and no coset is enumerated twice or written out of order.  The second run ends with status 0 and the log's one chunk.
    # Resultata before (2026-11-27): nothing stopped it; ten sweeps were restarted by a launcher that could have named a list already running.
    import fcntl
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, 'sweep.jsonl'), 'a') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            r1, log1, _ = sweeps(d, 480, 14, 190, '8,9,5,7,11,13', 600, 250, 100000, 4, 0.4)
        r2, log2, _ = sweeps(d, 480, 14, 190, '8,9,5,7,11,13', 600, 250, 100000, 4, 0.4)
    assert r1.returncode != 0 and not log1, (r1.returncode, log1)
    assert r2.returncode == 0 and [(x['first'], x['last']) for x in log2] == [(0, 249)], (r2.stderr[-2000:], log2)


def q_the_sweep_finds_544_10():
    # Replicata: sweep.py at 544, order 10, a symmetric cell, W = 110, pins 8, 9, 5, 7, 11, 13, 17, 19, the 3,000 best cosets, each to the end of its tree (floor 4, sag 0.4, a budget of 1e9 nodes), in an empty directory.
    # Expectata: status 0, every coset of the list in the log once, none at the cap, and at least one witness: each a different coset's, of order at least 10 in plain integers here, listed in its coset's chunk of the log.  (On 2026-11-27 the 20,000 best held 42 cosets with a witness, 14 of them among the first 2,000; at floor 1 and sag 0.3, the random search's settings here, 4 and 1.)
    # Resultata before (2026-11-27): there was no sweep; the random search finds this cell in 11 to 81 s (README).
    with tempfile.TemporaryDirectory() as d:
        r, log, found = sweeps(d, 544, 10, 110, '8,9,5,7,11,13,17,19', 3000, 3000, 10 ** 9, 4, 0.4)
    assert r.returncode == 0 and found, (r.stderr[-2000:], len(log), found)
    assert [x['first'] for x in log] == [0] + [x['last'] + 1 for x in log[:-1]] and log[-1]['last'] == 2999 and not any(x['capped'] for x in log), log
    assert len({w['coset'] for w in found}) == len(found) == sum(len(x['found']) for x in log)
    for w in found:
        f = decode(w['code'], 544, 10)
        assert len(f) == 544 and sum(f) == 0 and order_div(f) == w['order'] >= 10, w
        assert [w['code'] in x['found'] for x in log if x['first'] <= w['coset'] <= x['last']] == [True], w


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


def q_enumeration_preserves_the_first_witness_and_node_budget():
    # Replicata: six cosets of a triangular integer basis with half-integer centers
    # and nonzero off-diagonal coefficients. The last two coordinates are fixed.
    # Expectata: the original enumerator's exact first witness in each coset,
    # node count, cap status and squared perpendicular lengths at both pruning floors.
    # Resultata before: these outputs, including the mixed capped search, were unpinned.
    from types import SimpleNamespace
    import numpy as np
    sys.path.insert(0, TILTED)
    from tilted import Tilted
    d, f = 8, 10
    b = np.zeros((d, f), dtype=np.int32)
    diag = np.array([4, 1, 2, 1] * 2)
    for i in range(d):
        b[i, i] = diag[i]
        for j in range(i): b[i, j] = (i + 2 * j) % 5 - 2
    shift = np.arange(d) % 3 - 1
    z = np.zeros((6, f), dtype=np.int64)
    z[1] = z[4] = 1
    z[2] = np.arange(f) % 2 + shift @ b
    z[3, :d] = (np.arange(d) ** 2 + 2) % 7
    z[4, -1] = 3
    z[5] = (shift + 1) @ b
    problem = SimpleNamespace(L=6, d=d, f=f, B=b, z0=np.zeros(f, dtype=np.int64), zx=z,
                              mu=np.ascontiguousarray(b[:, :d] / diag), rr=diag.astype(float)**2,
                              Q=np.eye(d, f))
    signs = np.array([[63 ^ (1 << i)] for i in range(6)], dtype=np.uint64)
    expected = {0: '-----+-+--', 1: '+++++-+-++', 2: '++-------+', 3: '+-+-+-+---', 5: '----------'}
    for floor, cap, keep, indices, nodes, truncated in (
            (4, 0, 6, [], 5, 5), (4, 8, 6, [3], 44, 4),
            (4, 100, 6, [0, 1, 2, 3, 5], 74, 0), (4, 100, 2, [0, 1], 74, 0),
            (0.1, 100, 6, [], 25, 0)):
        out, idx, stats, perp = Tilted.enum(problem, signs, floor, cap, maxsol=keep, sag=0.4)
        assert idx.tolist() == indices and stats.tolist() == [6, nodes, 0, truncated]
        assert perp.tolist() == [2, 2, 2, 2, 26, 2]
        assert out.tolist() == [[1 if c == '+' else -1 for c in expected[i]] for i in indices]


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
