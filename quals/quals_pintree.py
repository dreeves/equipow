#!/usr/bin/env python3
"""Quals for pin trees: proofs/pintree.py, proofs/pintree_second.py, the proofs they check, and searches/pintree/pintree_prove.py, which makes them.
Run: python3 -B quals/quals_pintree.py [name ...]   (no arguments: all quals).  About 25 minutes.  The checkers need only the standard library; the rest needs numpy, sympy, ortools (through mstar.py) and, for the prover, scipy and highspy.

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The code came first here: these quals were written after it, in the session that made the proofs, so none was seen red against it but those that a change of the proof must turn red.
"""
import sys
sys.dont_write_bytecode = True
import ast, copy, gzip, itertools, json, math, os, random, re, subprocess, tempfile, time, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PROOFS = os.path.join(HERE, 'proofs')
PROVE = os.path.join(HERE, 'searches', 'pintree', 'pintree_prove.py')
sys.path.insert(0, os.path.join(HERE, 'pagegen')); sys.path.insert(0, PROOFS)   # pagegen/: mstar.py's directory since 2026-11-10 ([REF]); the root until then
# residues, in engine/ since [FAC] stage 3b (2026-11-04)
sys.path.insert(0, os.path.join(HERE, 'engine'))
COUNTS = {(432, 12): {'closed': 7561, 'splits': 101, 'vectors': 7672, 'skipped': 11, 'bounds': 2860, 'certificates': 3119},
          (816, 13): {'closed': 332497, 'splits': 6269, 'vectors': 338958, 'skipped': 193, 'bounds': 166072, 'certificates': 187269}}


def path(n, m): return os.path.join(PROOFS, f'pintree_{n}_{m}.json.gz')


def load(n, m):
    with gzip.open(path(n, m), 'rt', encoding='utf-8') as f: return json.load(f)


def replay(d):
    import pintree
    return pintree.Replay(d['n'], d['m'], d['nodes'], [tuple(c) for c in d['table']], d['tokens'], d['sym_depth']).run()


def order(a):
    """The order of a sequence: how many times x - 1 divides its polynomial, by synthetic division in plain integers."""
    p, k = list(reversed(a)), 0
    while True:
        q, c = [], 0
        for t in p:
            c += t; q.append(c)
        if q.pop(): return k
        p, k = q, k + 1


def sequences():
    """The sequences in hand of order >= 7, as (n, order, signs, whether symmetric or antisymmetric): mstar.py's explicit ones and its built columns, which include asymmetric joins."""
    import mstar
    out, seen = [], set()
    for a in itertools.chain(mstar.explicit().values(), (mstar.build(n) for n in range(96, 1025, 8))):
        a = list(a)
        if len(a) < 96 or len(a) % 8 or tuple(a) in seen: continue
        seen.add(tuple(a))
        o = order(a)
        if o >= 7: out.append((len(a), o, a, a == a[::-1] or a == [-t for t in a[::-1]]))
    return out


def by_division(n, M, m, e):
    """rep(M) of pintree.py's (d), the long way: S = 1 + x + ... + x^(n-1) divided by (x + 1)^(m + e) over F_2, exactly, then multiplied back in the integers.  It shares nothing with pintree.coset_rep's formula."""
    h = [1] * n                                                                 # lowest first
    for _ in range(m + e):                                                      # exact division by x + 1 over F_2, highest first
        q = [0] * (len(h) - 1)
        c = 0
        for i in reversed(range(len(h))):
            c ^= h[i]
            if i: q[i - 1] = c
        assert c == 0, 'x + 1 does not divide'
        h = q
    wrapped = [0] * M
    for i, c in enumerate(h): wrapped[i % M] ^= c
    out = wrapped
    for root, times in ((-1, m), (1, e)):
        for _ in range(times): out = [(out[(r - 1) % M] + root * out[r]) for r in range(M)]
    return out


def in_coset(D, n, M, m):
    """D in rep(M) + 2 L(M), by by_division and the project's own basis of L(M)."""
    from residues import basis
    e = 1 if n < 2 ** m else 0
    d = [a - b for a, b in zip(D, by_division(n, M, m, e))]
    if any(x % 2 for x in d): return False
    y = [x // 2 for x in d]
    B, piv = basis(M, m, 'natural', bool(e))
    for j in reversed(range(len(piv))):
        t, rem = divmod(y[piv[j]], B[piv[j]][j])
        if rem: return False
        for r in range(M): y[r] -= t * B[r][j]
    return not any(y)


# ---------------------------------------------------------------------------------------------------------------------
# The proofs

def q_the_proofs_replay():
    # Replicata: proofs/pintree.py run on each proof file, with python -I -S, so with nothing but the standard library.
    # Expectata: "VERIFIED: no sequence of length n has order m", exit 0, and the tree's counts as pinned here: 432:12 settles m*(432) = 11, 816:13 settles m*(816) = 12.
    # Resultata before: no such proofs.
    for (n, m), c in COUNTS.items():
        p = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(PROOFS, 'pintree.py'), path(n, m)], capture_output=True, text=True, timeout=1800)
        assert p.returncode == 0, p.stderr[-800:]
        assert f'VERIFIED: no sequence of length {n} has order {m}.' in p.stdout, p.stdout
        want = f"{c['certificates']} certificates in the table; {{'closed by certificate': {c['closed']}, 'splits': {c['splits']}, 'skipped by symmetry': {c['skipped']}, 'vectors': {c['vectors']}, 'bounds': {c['bounds']}}}"
        assert want in p.stdout, (want, p.stdout)


def q_the_second_check_agrees_on_432_12():
    # Replicata: proofs/pintree_second.py on 432:12, 4 processes.  (816:13 takes about an hour on 12: run by hand.  It passed on 2026-11-03, with the counts that COUNTS pins.)
    # Expectata: VERIFIED by the second check, with the same counts as proofs/pintree.py, though it enumerates and evaluates by other routes.
    # Resultata before: no second check.
    c = COUNTS[432, 12]
    p = subprocess.run([sys.executable, '-B', '-S', os.path.join(PROOFS, 'pintree_second.py'), path(432, 12), '4'], capture_output=True, text=True, timeout=1800)
    assert p.returncode == 0, p.stderr[-800:]
    assert 'VERIFIED by the second check: no sequence of length 432 has order 12.' in p.stdout, p.stdout
    want = f"{{'closed': {c['closed']}, 'splits': {c['splits']}, 'vectors': {c['vectors']}, 'skipped': {c['skipped']}, 'bounds': {c['bounds']}}}"
    assert want in p.stdout, (want, p.stdout)


def q_the_checkers_share_no_code_and_need_only_the_standard_library():
    # Replicata: the imports of proofs/pintree.py and proofs/pintree_second.py, read from their source; and their use of floats.
    # Expectata: only standard modules; pintree.py imports no second check; pintree_second.py imports pintree only inside hints(), whose answers it does not trust; neither calls float() or uses a float literal.
    # Resultata before: new.
    allowed = {'gzip', 'json', 'sys', 'functools', 'math', 'fractions', 'os', 'time', 'multiprocessing'}
    for name in ('pintree.py', 'pintree_second.py'):
        tree = ast.parse(open(os.path.join(PROOFS, name), encoding='utf-8').read())
        top, inner = set(), set()
        for node in tree.body:
            if isinstance(node, ast.Import): top |= {a.name.split('.')[0] for a in node.names}
            if isinstance(node, ast.ImportFrom): top.add(node.module.split('.')[0])
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): inner |= {a.name.split('.')[0] for a in node.names}
            if isinstance(node, ast.ImportFrom): inner.add(node.module.split('.')[0])
            assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), (name, node.value)
            assert not (isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'float'), name
        assert top <= allowed, (name, top - allowed)
        assert inner <= allowed | ({'pintree'} if name == 'pintree_second.py' else set()), (name, inner)


def q_a_changed_proof_is_refused():
    # Replicata: the proof of 432:12 changed five ways, each by a seeded random choice: a token removed; m changed; the certificate of a closing token replaced by zeros; every token 'L' pointing at one fixed bound certificate; n changed.
    # Expectata: each is refused, by an exception, every time.  (Changes that leave an inequality true leave a valid proof, so they prove nothing here: pointing a token at the next certificate, or zeroing only the polynomial part, passed 3 and 2
    # times in 10 on 2026-11-03.)
    # Resultata before: new.
    data = load(432, 12)
    replay(data)
    rng = random.Random(2)
    closing = [t[1] for t in data['tokens'] if t[0] == 'L']
    def lose_token(d): d['tokens'].pop(rng.randrange(len(d['tokens'])))
    def change_m(d): d['m'] = 11; d['nodes'] = d['nodes'][:11]
    def zero_certificate(d):
        c = d['table'][rng.choice(closing)]
        c[0] = [0] * len(c[0])
        for M in c[1]: c[1][M] = [0] * len(c[1][M])
    def all_one(d):
        for t in d['tokens']:
            if t[0] == 'L': t[1] = d['tokens'][0][2] or closing[0]
    def change_n(d): d['n'] = 448
    for change in (lose_token, change_m, zero_certificate, all_one, change_n):
        for trial in range(3 if change in (lose_token, zero_certificate) else 1):
            d = copy.deepcopy(data)
            change(d)
            try:
                replay(d)
            except Exception:
                continue
            raise AssertionError(f'{change.__name__} was accepted')


# ---------------------------------------------------------------------------------------------------------------------
# The lemma and the enumeration

def q_the_coset_holds_by_brute_force():
    # Replicata: every sign vector with a_0 = 1 of length 16 and 24 that has order >= 3 and >= 4, found by brute force over all of them; most are asymmetric.  Each one's residue sums mod 4, 8, 16 and 32.
    # Expectata: every vector lies in rep + 2 L(M) (in_coset, the long way), and pintree.vectors lists it.
    # Resultata before: the proof searches took only D in L(M) with the right parities.
    import numpy as np
    import pintree
    asym = 0
    for n, m in ((16, 3), (16, 4), (24, 3), (24, 4)):
        N = 2 ** (n - 1)
        bits = ((np.arange(N, dtype=np.int64)[:, None] >> np.arange(n - 1)) & 1) * 2 - 1
        bits = np.concatenate([np.ones((N, 1), dtype=np.int64), bits], axis=1)
        keep = np.ones(N, dtype=bool)
        for k in range(m): keep &= bits @ np.array([math.comb(i, k) for i in range(n)], dtype=np.int64) == 0
        sols = bits[keep].tolist()
        assert sols, (n, m)
        for a in sols:
            asym += a != a[::-1] and a != [-t for t in a[::-1]]
            for M in (4, 8, 16, 32):
                D = tuple(sum(a[r::M]) for r in range(M))
                assert in_coset(D, n, M, m), (n, m, M, a)
                assert D in pintree.vectors(n, m, M, {}, [x - 2 for x in D], [x + 2 for x in D]), (n, m, M, a)
    assert asym >= 200, asym


def q_the_coset_holds_on_every_sequence_in_hand():
    # Replicata: every sequence that mstar.py holds of length a multiple of 8 from 96 and order >= 7, at its own order and one below; residue sums mod 4, 8, 16 and 32.
    # Expectata: more than 100 sequences, more than 30 of them neither symmetric nor antisymmetric; every vector in rep + 2 L(M).
    # Resultata before: new.
    seqs = sequences()
    assert len(seqs) > 100 and sum(not s for *_, s in seqs) > 30, (len(seqs), sum(not s for *_, s in seqs))
    for n, o, a, _ in seqs:
        t = (n & -n)
        for m in (o, o - 1):
            if t - 1 < m + (n < 2 ** m): continue
            for M in (4, 8, 16, 32):
                assert in_coset(tuple(sum(a[r::M]) for r in range(M)), n, M, m), (n, o, m, M)


def q_rep_is_the_long_way_s():
    # Replicata: pintree.coset_rep, by its formula, and by_division, which divides S by (x + 1)^(m + e) over F_2 and multiplies back, at the open cells' n and m, M = 4, 8, 16, 32.
    # Expectata: equal, up to 2 L(M): their difference halved lies in L(M).
    # Resultata before: new.
    import pintree
    from residues import basis
    for n, m in ((288, 10), (432, 12), (480, 14), (528, 12), (672, 13), (720, 14), (768, 13), (816, 14), (864, 14)):
        e = 1 if n < 2 ** m else 0
        for M in (4, 8, 16, 32):
            y = [a - b for a, b in zip(pintree.coset_rep(n, M, m, e), by_division(n, M, m, e))]
            assert not any(x % 2 for x in y), (n, m, M)
            y = [x // 2 for x in y]
            B, piv = basis(M, m, 'natural', bool(e))
            for j in reversed(range(len(piv))):
                t, rem = divmod(y[piv[j]], B[piv[j]][j])
                assert rem == 0, (n, m, M, j)
                for r in range(M): y[r] -= t * B[r][j]
            assert not any(y), (n, m, M)


def q_vectors_are_the_residue_vectors_in_the_coset():
    # Replicata: pintree.vectors, and residues.residue_vectors (the proof searches' own enumeration, sympy's Hermite form) filtered by in_coset at powers of 2, at 432:12, 816:14 and 288:10, moduli 3, 5, 7, 4, under up to three parents 8.
    # Expectata: the same lists: pintree.vectors loses nothing and adds nothing.
    # Resultata before: new.
    import pintree
    from residues import residue_vectors, Budget
    for n, m in ((432, 12), (816, 14), (288, 10)):
        level = {}
        for M, P in ((3, None), (5, None), (7, None), (4, None), (8, 4)):
            parents = [{}] if P is None else [{P: v} for v in level[P][:3]]
            level[M] = []
            for pins in parents:
                mine = pintree.vectors(n, m, M, pins)
                theirs = sorted(residue_vectors(n, M, m, None if P is None else (P, pins[P]), Budget(4 * 10 ** 7), 'digits'))
                if M in (4, 8): theirs = [v for v in theirs if in_coset(v, n, M, m)]
                assert mine == theirs, (n, m, M, len(mine), len(theirs))
                level[M] += mine


def q_the_second_check_enumerates_the_same():
    # Replicata: pintree.vectors and pintree_second's Check.admissible, at 432:12 and 816:14, moduli 3, 5, 7, 4, 8, 9, 11, 13 under a first parent, inside bounds of plus or minus 6 around a vector of each.
    # Expectata: the same lists, by the two checkers' separate row reductions and walks.
    # Resultata before: new.
    import pintree, pintree_second
    for n, m in ((432, 12), (816, 14)):
        C = pintree_second.Check({'n': n, 'm': m, 'nodes': list(range(m)), 'table': [], 'tokens': [], 'sym_depth': 0})
        pins = {}
        for M in (3, 5, 7, 4, 8):
            vs = pintree.vectors(n, m, M, pins)
            assert C.admissible(M, pins, None, None) == vs, (n, m, M)
            pins[M] = vs[len(vs) // 2]
        for M in (9, 11, 13):
            P = {3: pins[3]} if M == 9 else {}
            mid = pintree.vectors(n, m, M, P, limit=10 ** 7)[:1] if M == 9 else None
            base = mid[0] if mid else [0] * M
            lo, hi = [x - 6 for x in base], [x + 6 for x in base]
            assert C.admissible(M, P, lo, hi) == pintree.vectors(n, m, M, P, lo, hi), (n, m, M)


def q_the_coset_is_stricter_than_the_lattice():
    # Replicata: at 432:12, the vectors mod 4 and mod 8 under the old conditions (D in L(M) with the right parities, residues.residue_vectors) and with the coset (pintree.vectors).
    # Expectata: 25 against 5 mod 4; 186,309 against 5,450 mod 8.
    # Resultata before: the proof searches used 25 mod 4 at 432:12 (focus432.py's docstring).
    import pintree
    from residues import residue_vectors, Budget
    assert len(list(residue_vectors(432, 4, 12, None, Budget(10 ** 7), 'digits'))) == 25
    assert len(pintree.vectors(432, 12, 4, {})) == 5
    assert len(list(residue_vectors(432, 8, 12, None, Budget(4 * 10 ** 7), 'digits'))) == 186309
    assert sum(len(pintree.vectors(432, 12, 8, {4: v})) for v in pintree.vectors(432, 12, 4, {})) == 5450


def q_certificates_hold_on_real_sequences():
    # Replicata: 25 sequences in hand, each at its own order with its own residue sums pinned mod 3, 5, 7 and 8, under random integer certificates.
    # Expectata: the identity behind the proof holds exactly, sum_p w(p) a_p = Den K; no certificate closes the sequence's own pins; every bound at moduli 9, 11, 16 holds for the sequence.
    # Resultata before: new.
    import pintree
    rng = random.Random(1)
    for n, o, a, _ in rng.sample(sequences(), 25):
        pins = {M: tuple(sum(a[r::M]) for r in range(M)) for M in (3, 5, 7, 8)}
        xs = tuple(range(0, 3 * o, 3))
        for trial in range(4):
            cert = ([rng.randint(-10 ** 6, 10 ** 6) for _ in range(o)], {str(M): [rng.randint(-10 ** 4, 10 ** 4) for _ in range(M)] for M in pins}, 2 ** 20)
            W = pintree.Weights(n, xs, cert)
            assert sum(v * t for v, t in zip(W.w, a)) == W.Den * W.K(pins), (n, o)
            assert not W.closes(pins), (n, o)
            for M in (9, 11, 16):
                r = rng.randrange(M)
                d = sum(a[r::M])
                assert d <= W.bound(pins, M, r, 1) and -d <= W.bound(pins, M, r, -1), (n, o, M, r)


# ---------------------------------------------------------------------------------------------------------------------
# The prover (each run in a process of its own: on Linux, ortools, which mstar.py imports, and highspy clash in one)

FOLLOW = r'''
import json, sys
sys.path.insert(0, sys.argv[2])
from multiprocessing import Pool
import pintree_prove as pp
from pintree import vectors, Weights
def follow(job):
    n, o, a = job
    xs = pp.chebyshev_nodes(n, o)
    P = pp.Prover(n, o, xs, pp.CAP, 0)
    pins, bad, steps = {}, [], 0
    for M in pp.CHAIN:
        D = tuple(sum(a[r::M]) for r in range(M))
        if D not in vectors(n, o, M, pins, [x - 2 for x in D], [x + 2 for x in D]): bad.append(('top', M))
        pins[M] = D
        if P.close(pins) is not None: bad.append(('closed', M))
        steps += 1
    while True:
        ch = P.split_choice(pins)
        if ch is None: break
        M, vs, refs = ch
        D = tuple(sum(a[r::M]) for r in range(M))
        for r, (ca, cb) in enumerate(refs):
            if not (D[r] <= Weights(n, xs, cb).bound(pins, M, r, 1) and -D[r] <= Weights(n, xs, ca).bound(pins, M, r, -1)): bad.append(('bound', M, r))
        if D not in vs:
            bad.append(('split', M)); break
        pins = {**pins, M: D}
        if P.close(pins) is not None:
            bad.append(('closed', M)); break
        steps += 1
    return n, o, steps, bad
if __name__ == '__main__':
    with Pool(6) as pool: print(json.dumps(pool.map(follow, [tuple(j) for j in json.load(open(sys.argv[1]))], chunksize=1)))
'''


def q_the_prover_keeps_real_sequences():
    # Replicata: 18 sequences in hand of order >= 9, the asymmetric ones first, each followed down the tree by the prover's own code: at every step the residue vector among the vectors, inside the class bounds its certificates prove, and its pins closed by no certificate.
    # Expectata: no sequence lost, at least 5 steps each.  A loss would make the proofs unsound.
    # Resultata before: new.  (The same ran on 56 sequences on 2026-11-03, with none lost.)
    seqs = [s for s in sequences() if s[0] >= 192 and s[1] >= 9]
    seqs.sort(key=lambda s: (s[3], s[0]))
    jobs = [s[:3] for s in seqs[:9] + seqs[-9:]]
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f: json.dump(jobs, f)
    # FOLLOW runs from a file of its own, not from -c (Fable 5.2, 2026-11-10; the qual asks what it asked).  Where processes are spawned, as on macOS, a pool's workers import the main module anew to find follow(), and a -c script has no file to
    # import: each worker died on "Can't get attribute 'follow'" and the pool waited for ever.  On Linux, which forks, -c worked.
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as g: g.write(FOLLOW)
    p = subprocess.run([sys.executable, '-B', g.name, f.name, os.path.dirname(PROVE)], capture_output=True, text=True, timeout=3000,
                       env=dict(os.environ, PYTHONPATH=os.pathsep.join([PROOFS, HERE]), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
    os.unlink(f.name); os.unlink(g.name)
    assert p.returncode == 0, p.stderr[-1500:]
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert len(out) == 18 and all(r[3] == [] and r[2] >= 5 for r in out), out


def q_the_prover_makes_a_proof_of_432_12():
    # Replicata: pintree_prove.py prove 432:12 on 4 processes, in a working directory of its own, from nothing; then both checks of what it writes.
    # Expectata: nothing open, a proof that proofs/pintree.py verifies.  Its tree need not equal the committed one's: an LP in floating point suggests it.
    # Resultata before: new.
    import shutil
    work = os.path.join(HERE, 'scratch', 'pintree', '432_12')
    shutil.rmtree(work, ignore_errors=True)
    made = os.path.join(HERE, 'scratch', 'pintree', 'pintree_432_12.json.gz')
    p = subprocess.run([sys.executable, '-B', PROVE, 'prove', '432:12', '4'], capture_output=True, text=True, timeout=3000, env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
    assert p.returncode == 0, p.stderr[-1500:]
    assert f'wrote {made}' in p.stdout, p.stdout[-800:]
    q = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(PROOFS, 'pintree.py'), made], capture_output=True, text=True, timeout=600)
    assert q.returncode == 0 and 'VERIFIED: no sequence of length 432 has order 12.' in q.stdout, (q.stdout, q.stderr[-500:])


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0 = time.time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
