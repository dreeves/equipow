#!/usr/bin/env python3
"""Quals for boxsplit.py.  Run: nice -n 19 python3 -B quals_boxsplit.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata
(the setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened
instead).  Quals marked "regression" pin numbers found independently earlier, by the split and verify-split angles of
scratch/strategy (2026-10-10), rather than stating a property; those that name an angle of scratch/boxsplit (the
soundness, recheck and mutants verifications of the first build, 2026-10-10) are the quals that angle asked for.  The
quals read the 304@9 run's journal as written (as_written: under the code its header names) and never write it (the
last qual checks that); the driver's journals and logs
they make go under scratch/boxsplit/quals/, wiped at the start.  About 3 CPU-minutes in all (plus q_run_on_one_leaf's
two runs in child processes), 5 minutes of wall time beside a loaded machine; the leaf-0 tree and the two coverage
quals are the slow ones.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, random, shutil, hashlib, inspect, traceback, subprocess, contextlib
from collections import Counter
from concurrent.futures import Future
import numpy as np
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form
from ortools.linear_solver import pywraplp
import overnight_v5 as v5
import certbb
import boxsplit as bx

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, 'scratch', 'boxsplit', 'quals')       # the quals' journals and logs
MAIN = (os.path.join(HERE, 'overnight_v5_304_9_journal.jsonl'), os.path.join(HERE, 'overnight_v5_304_9.log'))  # read only
UNTOUCHED = tuple(hashlib.sha1(open(f, 'rb').read()).hexdigest() for f in MAIN)   # as the quals began
# The 8 open leaves of the 304@9 journal after its second pass, in the order of the log's 'open:' lines of
# 2026-10-10 05:08:01 (the split angle's OPEN8).
OPEN8 = (
    "3:[51,10,91] 5:[18,18,43,43,30] 4:[38,38,38,38] 7:[29,22,15,18,18,25,25] 8:[21,17,17,21,17,21,21,17] 9:[17,2,29,17,5,32,17,3,30]",
    "3:[51,10,91] 5:[18,18,43,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[21,21,21,21,17,17,17,17] 9:[17,2,29,17,5,32,17,3,30]",
    "3:[51,10,91] 5:[18,18,43,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[21,17,21,21,17,21,17,17] 9:[17,2,29,17,5,32,17,3,30]",
    "3:[51,10,91] 5:[18,18,43,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[17,21,21,21,21,17,17,17] 9:[17,2,29,17,5,32,17,3,30]",
    "3:[51,10,91] 5:[18,18,43,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[17,21,21,17,21,17,17,21] 9:[17,2,29,17,5,32,17,3,30]",
    "3:[51,10,91] 5:[18,43,18,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[21,21,21,21,17,17,17,17] 9:[14,5,32,17,2,29,20,3,30]",
    "3:[51,10,91] 5:[18,43,18,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[21,21,21,21,17,17,17,17] 9:[17,2,29,17,5,32,17,3,30]",
    "3:[51,10,91] 5:[18,18,43,43,30] 4:[38,38,38,38] 7:[29,22,15,18,18,25,25] 8:[17,17,17,21,21,21,21,17] 9:[17,2,29,17,5,32,17,3,30]",
)
# The 304@9 journal's lines before the handoff (2026-10-10 17:25), which appended the CLOSED records of OPEN8's leaves
# that the driver closed, in OPEN8's order, before overnight_v5.py's last pass closed their ancestors (regression: the
# copy scratch/boxsplit/overnight_v5_304_9_journal.before_handoff.jsonl has these lines).
HANDOFF = 8932
# An open leaf of 240@11 that the width test closes by a cut in 3 LP solves (quals_width.py's THIN[0]).
THIN240 = ('3:[40,40,40] 5:[24,24,24,24,24] 7:[14,21,3,10,17,24,31] 4:[30,30,30,30] 8:[17,17,13,21,13,13,17,9] '
           '11:[11,11,11,11,11,11,11,11,11,5,16] 13:[12,11,10,9,8,7,12,11,10,9,8,7,6] 9:[15,12,18,15,12,9,10,16,13]')
# A bottom leaf the journal records INFEASIBLE at 13499 LP solves (the verify-split angle's ground truth).
TRUTH = "3:[51,10,91] 5:[18,43,18,43,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[17,21,17,21,21,17,21,17] 9:[17,2,29,17,5,32,17,3,30]"
RAMP = (17, 16, 15, 14, 13, 12, 11, 15, 14, 13, 12)       # leaf 0's two own children by 11 (regression)
OTHER = (15, 11, 18, 14, 10, 17, 13, 14, 10, 17, 13)
LEAF0_BOX = ((5, 6, 9, 7, 5, 6, 4, 6, 6, 5, 5), (24, 22, 23, 21, 19, 22, 23, 22, 22, 21, 21))   # its count box by 11
# Leaf 0's extension tree as the run's log tallied it (regression: the leaf-0 summary line of the run of 2026-10-10,
# 14294 certbb LP solves and 4043 GLOP solves), with carry since 2026-10-17: every pool member carried, so the pools'
# 3991 LP solves and GLOP checks are gone (10303 = 14294 - 3991; 52 = the count boxes' 23 + 27 and the 2 own vectors').
LEAF0_TALLY = {'splits': 2, 'own': 2, 'pool': 3991, 'carried': 3991, 'outside': 290, 'lps': 10303, 'glop': 52}


def at(n, order):
    """Configure boxsplit (and so overnight_v5) for (n, order) unless it already is."""
    if (v5.N, v5.ORDER) != (n, order) or bx.MODULI is None: bx.configure(n, order)


def leaf(i): return bx.parse_key(OPEN8[i])


@contextlib.contextmanager
def as_written():
    """boxsplit configured for 304@9 with overnight_v5's CODE the one in the run's journal header, the code that wrote
    it, so that the run's files stay fixtures as the code changes (quals_progress.as_written's way); CODE is restored
    after."""
    at(304, 9)
    saved = v5.CODE
    v5.CODE = json.loads(open(v5.JOURNAL).readline())['code']
    try: yield
    finally: v5.CODE = saved


def paths(name):
    """A fresh journal and log path for a qual's driver run."""
    return os.path.join(RUNS, f'{name}_journal.jsonl'), os.path.join(RUNS, f'{name}.log')


def quiet(lines):
    """A log function that keeps the lines in a list."""
    return lines.append


def expect_assertion(f, where):
    """Run f; it must raise AssertionError from inside the function named where.  Returns that frame of the
    traceback, whose line is the failed assertion's source."""
    try:
        f()
    except AssertionError as e:
        frames = traceback.extract_tb(e.__traceback__)
        assert frames[-1].name == where, frames[-1]
        return frames[-1]
    # TODO: error copy; says the expected assertion did not fire, naming the function where it should have
    raise AssertionError(f'Claude: "the expected assertion did not fire: {where}"')


def expect_proof_error(f):
    """Run f; it must raise certbb.ProofError.  Returns its message."""
    try:
        f()
    except certbb.ProofError as e:
        return str(e)
    # TODO: error copy; says the expected ProofError did not come
    raise AssertionError('Claude: "the expected ProofError did not come"')


def patched(mod, **kw):
    """Patch a module's globals for the duration of a with-block."""
    class P:
        def __enter__(self):
            self.saved = {k: getattr(mod, k) for k in kw}
            for k, val in kw.items(): setattr(mod, k, val)
        def __exit__(self, *exc):
            for k, val in self.saved.items(): setattr(mod, k, val)
    return P()


class SyncExecutor:
    """An executor that runs each task at once, in this process (quals_v5's), as a context manager like
    ProcessPoolExecutor, so that module patches reach the work."""
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def submit(self, fn, *args):
        f = Future()
        f.set_result(fn(*args))
        return f


def coset(order, node, M, box):
    """An independent enumerator of a node's count vectors mod M inside box = (lo, hi), ported from
    scratch/strategy/split/fiber.py (the split angle's; checked there against overnight_v5.split on three splits and,
    by the verify-split angle, against a box-restricted admissible on 22): the vectors v with (v, head) in the column
    lattice of A = [the count rows mod M; the moment rows; the node's count rows], head = (the moment right-hand
    sides, the node's vectors), form a coset v0 + Lambda, Lambda spanned by the columns of A's HNF whose pivots lie in
    the first M rows; its members with lo[r] <= v_r <= hi[r] are yielded by back substitution.  Every sequence of the
    order in the node has its counts mod M in the coset (its y = (a + 1)/2 solves the rows); the residue lattice
    condition of admissible is not imposed."""
    rows = list(v5.count_rows(M)) + list(v5.moment_rows(order)[0])
    head = list(v5.moment_rows(order)[1])
    for P, V in node:
        rows += list(v5.count_rows(P))
        head += list(V[0])
    H = hermite_normal_form(sp.Matrix(rows))
    m, K = H.shape
    H = [[int(H[r, j]) for j in range(K)] for r in range(m)]
    piv = [max(r for r in range(m) if H[r][j]) for j in range(K)]
    assert piv == sorted(set(piv)) and all(H[piv[j]][j] > 0 for j in range(K))
    lam = [j for j in range(K) if piv[j] < M]
    z, target = {}, [0] * M + head
    for j in reversed([j for j in range(K) if j not in lam]):      # the head's coefficients, bottom row up
        r = piv[j]
        rest = target[r] - sum(H[r][i] * z[i] for i in z)
        assert rest % H[r][j] == 0, 'head not in the lattice'
        z[j] = rest // H[r][j]
    assert all(sum(H[r][i] * z[i] for i in z) == target[r] for r in range(M, m))
    v0 = [sum(H[r][i] * z[i] for i in z) for r in range(M)]
    Lam = [[H[r][j] for j in lam] for r in range(M)]
    pivs = [piv[j] for j in lam]
    lo, hi = box
    k = len(lam)
    zz, c = [0] * k, [0] * M

    def climb(r, j):
        if r < 0:
            yield tuple(c)
            return
        base = v0[r] + sum(Lam[r][i] * zz[i] for i in range(j + 1, k))
        if j >= 0 and pivs[j] == r:
            h = Lam[r][j]
            for t in range(-((base - lo[r]) // h), (hi[r] - base) // h + 1):
                zz[j], c[r] = t, base + h * t
                yield from climb(r - 1, j - 1)
        elif lo[r] <= base <= hi[r]:
            c[r] = base
            yield from climb(r - 1, j)

    yield from climb(M - 1, k - 1)


def full_box(M):
    """The box [0, size] of every class mod M."""
    return (0,) * M, tuple(v5.size(M, r) for r in range(M))


def split_filter(order, node, M):
    """overnight_v5.split's integer filter and orbit reduction for the children of node by M, as a predicate."""
    rhs = v5.moment_rows(order)[1] + tuple(t for _, V in node for t in V[0])
    ok = v5.integer_system(order, tuple(P for P, _ in node) + (M,)).fiber(rhs)
    gs = v5.stabilizer(node)
    return lambda v: ok(v) and v == v5.rep(gs, M, v)


def example_node(order, depth):
    """The example of length 304 and the given order (overnight_v5.EXAMPLES) followed down the first depth moduli of
    the cascade as the control follows it; returns (node, the example's image)."""
    a, node = v5.from_hex(v5.EXAMPLES[v5.N, order], order), ()
    for M in v5.CASCADE[:depth]: node, a = bx.follow(node, a, M)
    return node, a


def made_up_main(keys=(TRUTH,)):
    """A made-up run journal under RUNS: the run's header and the keys (TRUTH by default) as its open leaves, each
    UNKNOWN at the bottom budget.  Returns its path."""
    main = os.path.join(RUNS, 'main_journal.jsonl')
    with open(main, 'w') as fh:
        fh.write(json.dumps(v5.header()) + '\n')
        for key in keys:
            fh.write(json.dumps({'key': key, 'verdict': 'UNKNOWN', 'budget': 10000000, 'lps': 10000000, 'leaves': 0,
                                 'proof': '0' * 40}) + '\n')
    return main


def named(key):
    """What a driver record's key says it proves, parsed without boxsplit: (moment rows W, right-hand sides, the key
    of the node).  An outside key (last part M:r=t) adds the count row of class r mod M with right-hand side t."""
    parts = key.split()
    W, rhs = v5.moment_rows(v5.ORDER)
    if '=' in parts[-1]:
        M, rt = parts.pop().split(':')
        M, (r, t) = int(M), map(int, rt.split('='))
        W, rhs = W + (tuple(int(p % M == r) for p in range(v5.N)),), rhs + (t,)
    return W, rhs, ' '.join(parts)


def pieces(node, M):
    """The keys of the pieces of node's box split by M at ORDER, recomputed here, and its own children as nodes."""
    rel = v5.Relaxation(v5.ORDER, node, M)
    lo, hi = box = bx.count_box(rel)
    own, pool, _, _ = bx.box_split(v5.ORDER, node, M, rel, box)
    keys = {f'{v5.node_key(node)} {M}:{r}={t}' for r in range(M) for t in range(v5.size(M, r) + 1) if not lo[r] <= t <= hi[r]}
    keys |= {v5.node_key(node + ((M, pool),))} | {v5.node_key(node + ((M, (v,)),)) for v in own}
    return keys, [node + ((M, (v,)),) for v in own]


def real_sequences(n, order):
    """All ±1 sequences of length n whose power sums vanish for k < order, by meet in the middle (exact int64; the
    soundness angle's mitm.py)."""
    h = n // 2

    def half(offset, m):
        signs = (1 - 2 * ((np.arange(2 ** m)[:, None] >> np.arange(m)[None, :]) & 1)).astype(np.int64)
        P = np.array([[(offset + p) ** k for k in range(order)] for p in range(m)], dtype=np.int64)
        return signs, signs @ P

    sl, ml = half(0, h)
    sr, mr = half(h, n - h)
    d = {}
    for i, row in enumerate(map(tuple, ml.tolist())): d.setdefault(row, []).append(i)
    return [tuple(sl[i].tolist()) + tuple(sr[j].tolist())
            for j, row in enumerate(map(tuple, (-mr).tolist())) for i in d.get(row, ())]


def oracle_pieces(order, node, i, realin, shrink, rng):
    """Every piece of node's extension tree from MODULI[i] on, as close_tree makes them but each solved on its own
    (solve_piece at the driver's budgets) and, with shrink, inside the count box cut by up to 2 at each end of each
    class (rng); yields (kind, the sequences of realin the piece holds, certbb's verdict), going down into an own child
    left UNKNOWN as close_tree does (the soundness angle's smalln2.py)."""
    M = bx.MODULI[i]
    rel = v5.Relaxation(order, node, M)
    lo, hi = bx.count_box(rel)
    if shrink:
        lo = tuple(l + rng.randint(0, 2) for l in lo)
        hi = tuple(h - rng.randint(0, 2) for h in hi)
    own, pool, outside, _ = bx.box_split(order, node, M, rel, (lo, hi))
    cnt = {b: v5.counts(list(b), M) for b in realin}
    for r, t in outside:
        yield ('outside', [b for b in realin if cnt[b][r] == t],
               bx.solve_piece(bx.outside_moments(order, M, r, t), node, v5.POOL_BUDGET)[0])
    yield ('pool', [b for b in realin if cnt[b] in set(pool)],
           bx.solve_piece(v5.moments(order), node + ((M, pool),), v5.POOL_BUDGET * len(pool))[0])
    for v in own:
        child = node + ((M, (v,)),)
        held = [b for b in realin if cnt[b] == v]
        verdict = bx.solve_piece(v5.moments(order), child, bx.BUDGETS[i])[0]
        if verdict == 'UNKNOWN' and i + 1 < len(bx.MODULI):
            yield from oracle_pieces(order, child, i + 1, held, shrink, rng)
        else:
            yield 'own', held, verdict


# ---------- configuration, the run's journal, keys ----------

def q_configure():
    # Replicata: configure(304, 9); configure(240, 11); configure(48, 6); the extension table.
    # Expectata: the first configures overnight_v5 for 304@9, takes the extension moduli (11, 13) with budgets
    # (10000, 2000000), and names the driver's journal and log overnight_v5_304_9_boxsplit_journal.jsonl and
    # overnight_v5_304_9_boxsplit.log next to boxsplit.py, neither of them the run's; the second likewise for 240@11,
    # its cascade (3, 5, 7, 4, 8, 11, 13, 9), the extension moduli 17 and 19, each with budget 2000000 (19 since
    # 2026-10-19, when the pass by 17 left 4 own children of 4 leaves UNKNOWN at 2000000; dreeves: "sure", to splitting
    # them by 19 as 304@9's were by 13), and the names
    # overnight_v5_240_11_boxsplit_journal.jsonl and overnight_v5_240_11_boxsplit.log; the third, a run overnight_v5
    # has settings for and the driver no extension: AssertionError in configure; every extension has one budget per
    # modulus, whole and positive.
    bx.configure(304, 9)
    assert (v5.N, v5.ORDER, v5.CASCADE) == (304, 9, (3, 5, 4, 7, 8, 9))
    assert (bx.MODULI, bx.BUDGETS) == ((11, 13), (10000, 2000000))
    assert bx.JOURNAL == os.path.join(HERE, 'overnight_v5_304_9_boxsplit_journal.jsonl') != v5.JOURNAL
    assert bx.LOG == os.path.join(HERE, 'overnight_v5_304_9_boxsplit.log') != v5.LOG
    bx.configure(240, 11)
    assert (v5.N, v5.ORDER, v5.CASCADE) == (240, 11, (3, 5, 7, 4, 8, 11, 13, 9))
    assert (bx.MODULI, bx.BUDGETS) == ((17, 19), (2000000, 2000000))
    assert bx.JOURNAL == os.path.join(HERE, 'overnight_v5_240_11_boxsplit_journal.jsonl') != v5.JOURNAL
    assert bx.LOG == os.path.join(HERE, 'overnight_v5_240_11_boxsplit.log') != v5.LOG
    assert (48, 6) in v5.SETTINGS and (48, 6) not in bx.EXTENSION
    expect_assertion(lambda: bx.configure(48, 6), 'configure')
    assert all(len(b) == len(m) and all(type(t) is int and t >= 1 for t in b) for m, b in bx.EXTENSION.values())
    bx.configure(304, 9)


def q_open_leaves():
    # Replicata: the 304@9 run's journal cut before the handoff (its first HANDOFF lines, copied under RUNS) and the
    # whole journal, each read through overnight_v5.Journal as written (under the code its header names), then
    # open_leaves.
    # Expectata (regression): before the handoff, exactly the 8 leaves of OPEN8, in that order (the order of the run's
    # 'open:' lines), each a depth-6 node of one vector per cascade modulus; parse_key round-trips each key through
    # node_key; a pool key is not a node of vectors: parse_key raises ValueError.  The whole journal: the cut's lines,
    # then the 8 leaves' CLOSED records in OPEN8's order, and no open leaf.
    cut = os.path.join(RUNS, 'before_handoff_journal.jsonl')
    with as_written():
        lines = open(v5.JOURNAL).read().splitlines()
        open(cut, 'w').write(''.join(line + '\n' for line in lines[:HANDOFF]))
        journal, whole = v5.Journal(cut), v5.Journal(v5.JOURNAL)
    assert [json.loads(line) for line in lines[HANDOFF:HANDOFF + 8]] == [
        {'key': k, 'verdict': 'CLOSED', 'budget': v5.node_budget(bx.parse_key(k))} for k in OPEN8]
    assert bx.open_leaves(whole) == []
    leaves = bx.open_leaves(journal)
    assert [v5.node_key(n) for n in leaves] == list(OPEN8), [v5.node_key(n) for n in leaves]
    for n in leaves:
        assert len(n) == 6 and all((M, len(V)) == (P, 1) for (M, V), P in zip(n, v5.CASCADE, strict=True))
        assert bx.parse_key(v5.node_key(n)) == n
    pool = next(k for k in journal.records if '#' in k)
    try:
        bx.parse_key(pool)
    except ValueError:
        return
    raise AssertionError(pool)


# ---------- the box-restricted enumeration ----------

def q_admissible_box_pins_to_admissible():
    # Replicata: at 304@9, the depth-5 parents of open leaves 0 and 5 split by 9 (fixed: their mod-3 vector) and the
    # depth-4 parent of leaf 0 split by 8 (fixed: its mod-4 vector), through admissible_box with the full box
    # [0, size], with the parent's count box, and with the box within 1 of admissible's middle vector; and through
    # overnight_v5.admissible.
    # Expectata: with the full box, exactly admissible's vectors, and after split's integer filter and orbit reduction
    # 193, 193 and 5050 of them (regression: the split angle's qual_matches_split); with a smaller box, exactly
    # admissible's vectors inside it, for the last box some but not all of them.
    at(304, 9)
    for i, M, depth, want in ((0, 9, 5, 193), (5, 9, 5, 193), (0, 8, 4, 5050)):
        parent = leaf(i)[:depth]
        fixed = tuple((P, V[0]) for P, V in parent if M % P == 0)
        theirs = v5.admissible(9, M, fixed)
        assert bx.admissible_box(9, M, fixed, full_box(M)) == theirs
        keep = split_filter(9, parent, M)
        assert len([v for v in theirs if keep(v)]) == want
        mid = theirs[len(theirs) // 2]
        near = ([max(0, t - 1) for t in mid], [min(v5.size(M, r), t + 1) for r, t in enumerate(mid)])
        for lo, hi in (bx.count_box(v5.Relaxation(9, parent, M)), near):
            inside = [v for v in theirs if all(lo[r] <= v[r] <= hi[r] for r in range(M))]
            assert bx.admissible_box(9, M, fixed, (lo, hi)) == tuple(inside)
        assert 0 < len(inside) < len(theirs)


def q_admissible_box_pins_to_admissible_at_11_and_13():
    # Replicata: the small configurations of overnight_v5.SETTINGS (48@6, 40@6, 56@6, 64@7, 104@7), at M = 11 and 13
    # with fixed = () (the run's case: no cascade modulus divides an extension modulus, which the qual above does not
    # cover), through admissible_box on the full box and on 20 random sub-boxes each (seeded), and through
    # overnight_v5.admissible.
    # Expectata (the soundness angle's pin_small.py): on the full box, exactly admissible's vectors, and some; on each
    # sub-box, exactly admissible's vectors inside it.
    rng = random.Random(1)
    for n, order in ((48, 6), (40, 6), (56, 6), (64, 7), (104, 7)):
        v5.configure(n, order)
        for M in (11, 13):
            theirs = v5.admissible(order, M, ())
            assert theirs and bx.admissible_box(order, M, (), full_box(M)) == theirs, (n, order, M)
            for _ in range(20):
                lo = [rng.randint(0, v5.size(M, r)) for r in range(M)]
                hi = [min(v5.size(M, r), l + rng.randint(0, 4)) for r, l in enumerate(lo)]
                want = tuple(v for v in theirs if all(lo[r] <= v[r] <= hi[r] for r in range(M)))
                assert bx.admissible_box(order, M, (), (lo, hi)) == want, (n, order, M, lo, hi)
    at(304, 9)


def q_count_box():
    # Replicata: leaf 0's relaxation by 11 at order 9; the relaxation by 13 of leaf 0 extended by a mod-11 vector whose
    # sum is not 152, which no sequence has (the LP is infeasible).
    # Expectata: the count box LEAF0_BOX (regression: widths 20, 17, 15, 15, 15, 17, 20, 17, 17, 17, 17, as the
    # verify-split angle printed), within [0, size]; the infeasible one: AssertionError in count_box, not a wider box.
    at(304, 9)
    rel = v5.Relaxation(9, leaf(0), 11)
    lo, hi = bx.count_box(rel)
    assert (lo, hi) == LEAF0_BOX, (lo, hi)
    assert all(0 <= l <= h <= v5.size(11, r) for r, (l, h) in enumerate(zip(lo, hi)))
    bad = leaf(0) + ((11, ((14,) * 11,)),)
    expect_assertion(lambda: bx.count_box(v5.Relaxation(9, bad, 13)), 'count_box')


def q_count_box_refuses_a_failed_relaxation():
    # Replicata: count_box on leaf 0's relaxation by 11 with its own solve (the empty objective) faked to report
    # ABNORMAL, every bound solve left as it is (OPTIMAL).
    # Expectata (the mutants angle): AssertionError in count_box, from its OPTIMAL assert (the plan: an LP failure
    # must crash), not a box.
    at(304, 9)
    rel = v5.Relaxation(9, leaf(0), 11)
    real = rel.solve
    rel.solve = lambda objective: pywraplp.Solver.ABNORMAL if objective == {} else real(objective)
    frame = expect_assertion(lambda: bx.count_box(rel), 'count_box')
    assert 'OPTIMAL' in frame.line, frame.line


def q_box_split_regression():
    # Replicata: leaf 0's box split by 11; the ramp child's box split by 13.
    # Expectata (regression: verify-split's close_leaf0.txt): leaf 0's own children are exactly OTHER and RAMP (in
    # admissible's sorted order), its pool holds 2083 vectors and its outside nodes are 128 (the sizes less the widths,
    # summed); the ramp child has no own child, a pool of 1908 and 162 outside nodes.  Each outside node lies outside
    # the box, each own child and pool member inside it.
    at(304, 9)
    for node, M, own, pool, outside in ((leaf(0), 11, [OTHER, RAMP], 2083, 128),
                                        (leaf(0) + ((11, (RAMP,)),), 13, [], 1908, 162)):
        rel = v5.Relaxation(9, node, M)
        lo, hi = box = bx.count_box(rel)
        got = bx.box_split(9, node, M, rel, box)
        assert (got[0], len(got[1]), len(got[2])) == (own, pool, outside), (got[0], len(got[1]), len(got[2]))
        assert len(got[2]) == sum(v5.size(M, r) + 1 - (hi[r] - lo[r] + 1) for r in range(M))
        assert all(not lo[r] <= t <= hi[r] for r, t in got[2])
        assert all(all(lo[r] <= v[r] <= hi[r] for r in range(M)) for v in got[0] + list(got[1]))


def q_box_split_filters_like_split():
    # Replicata: the depth-4 parent of open leaf 0 by 8 (fixed: its mod-4 vector) and the depth-5 parent of open leaf 2
    # by 9 (its stabilizer is {id}, its own parent's {id, phi}), each through box_split on the full box with a stand-in
    # relaxation whose check claims nothing and carry patched to give no certificate, so that every vector comes back
    # as an own child.
    # Expectata (the mutants angle): exactly overnight_v5.split's vectors before its LP, in admissible's order:
    # admissible, then the integer filter (which keeps 10000 of the 130321 admissible vectors by 8), then the orbit
    # reduction by the node's own stabilizer (5050 and 364 vectors; the parent's stabilizer would leave 193 of the
    # 364); no pool, no outside node.
    at(304, 9)

    class ClaimsNothing:
        def check(self, v): return True

    for i, depth, want in ((0, 4, 5050), (2, 5, 364)):
        X = leaf(i)[:depth]
        M = v5.CASCADE[depth]
        keep = split_filter(9, X, M)
        theirs = [v for v in v5.admissible(9, M, tuple((P, V[0]) for P, V in X if M % P == 0)) if keep(v)]
        with patched(bx, carry=lambda *args: {}):
            got = bx.box_split(9, X, M, ClaimsNothing(), full_box(M))
        assert len(theirs) == want and got == (theirs, (), [], {}), (i, len(got[0]), len(theirs))
    assert v5.stabilizer(leaf(2)[:5]) == [(0, 1)] and v5.stabilizer(leaf(2)[:4]) == [(0, 1), (1, -1)]


def leaf0_vectors():
    """Leaf 0's vectors by 11 inside its count box, as box_split makes them (admissible_box, the integer filter and
    the orbit reduction), and its relaxation by 11."""
    node = leaf(0)
    rel = v5.Relaxation(9, node, 11)
    keep = split_filter(9, node, 11)
    return [v for v in bx.admissible_box(9, 11, (), bx.count_box(rel)) if keep(v)], rel


def q_carry_gives_only_certificates_that_close():
    # Replicata: at 304@9, leaf 0's vectors by 11 inside its count box through carry; each vector GLOP's
    # Relaxation.check claims feasible.
    # Expectata: a dict from some of those vectors to certificates, each a list of integers whose bound lower_bound
    # finds positive on that vector's own rows (node_rows of the leaf and the vector) and the root box, recomputed
    # here rather than taken from carry's arithmetic; none of them a vector GLOP claims feasible; and at least ten
    # carried vectors per certificate made.
    at(304, 9)
    vecs, rel = leaf0_vectors()
    given = bx.carry(9, leaf(0), 11, vecs)
    assert given and set(given) <= set(vecs), len(given)
    mom, zero, one = v5.moments(9), [0] * v5.N, [1] * v5.N
    for v, n in given.items():
        assert type(n) is list and all(type(m) is int for m in n), v
        rows = certbb.node_rows(mom, [(P, V[0]) for P, V in leaf(0)] + [(11, v)])
        assert certbb.lower_bound(rows, zero, one, n) > 0, v
    assert not any(rel.check(v) for v in given)
    made = {tuple(n) for n in given.values()}
    assert 10 * len(made) <= len(given), (len(made), len(given))


def q_box_split_carries_its_pool():
    # Replicata: leaf 0's box split by 11 (q_box_split_regression's first), carry on the vectors inside its count box,
    # and the pooled node (the leaf with the pool by 11) through certbb.solve at POOL_BUDGET per member, given those
    # certificates for its members' choices.
    # Expectata: box_split's fourth value is carry's dict, every key a pool member; its own, pool and outside are
    # q_box_split_regression's (carrying moves no vector across: GLOP sorts only the vectors carry gives nothing, and
    # a carried vector's relaxation is infeasible); the pooled node is INFEASIBLE, its given count the dict's size and
    # its LP solves one per member not carried, and certbb.verify accepts its tokens.
    at(304, 9)
    node = leaf(0)
    vecs, rel = leaf0_vectors()
    own, pool, outside, given = bx.box_split(9, node, 11, rel, bx.count_box(rel))
    assert given == bx.carry(9, node, 11, vecs) and set(given) <= set(pool), len(given)
    assert (own, len(pool), len(outside)) == ([OTHER, RAMP], 2083, 128), (own, len(pool), len(outside))
    pooled = node + ((11, pool),)
    head = tuple(V[0] for _, V in node)
    tokens = []
    verdict, _, stats = certbb.solve(v5.moments(9), pooled, v5.POOL_BUDGET * len(pool), tokens.append,
                                     certificates={head + (v,): n for v, n in given.items()})
    assert (verdict, stats['given'], stats['lp']) == ('INFEASIBLE', len(given), len(pool) - len(given)), (verdict, stats)
    certbb.verify(v5.moments(9), pooled, tokens)


def q_coverage_leaf0_by_11():
    # Replicata: leaf 0 by 11: its count box and box split (own children, pool, outside nodes); independently, every
    # count vector mod 11 of the leaf's integer system, by coset on the full box.
    # Expectata: the coset holds 725216 vectors (regression: the split angle's count); the count box is symmetric under
    # the leaf's stabilizer; every coset vector with no class value in the outside list passes split's integer filter;
    # and every coset vector that lies in the residue lattice (admissible's condition, necessary for a sequence of
    # order 9) is either orbit-equivalent, under the stabilizer, to an own child or a pool member, or has a class
    # value, or its representative has one, that is in box_split's outside list (not merely outside the count box:
    # the mutants angle): no count vector escapes the extension tree.
    at(304, 9)
    node = leaf(0)
    rel = v5.Relaxation(9, node, 11)
    lo, hi = box = bx.count_box(rel)
    own, pool, outside, _ = bx.box_split(9, node, 11, rel, box)
    gs = v5.stabilizer(node)
    assert all(sorted([v5.act(g, 11, lo), v5.act(g, 11, hi)]) == sorted([lo, hi]) for g in gs)
    enumerated, covered = set(own) | set(pool), set(outside)
    assert len(enumerated) == len(own) + len(pool) == 2085
    rhs = v5.moment_rows(9)[1] + tuple(t for _, V in node for t in V[0])
    ok = v5.integer_system(9, tuple(P for P, _ in node) + (11,)).fiber(rhs)
    span = v5.ExactSystem(v5.lattice_basis(11, 9)).fiber(())
    test = lambda c: span([2 * t - v5.size(11, r) for r, t in enumerate(c)])
    n = inside = covered_outside = 0
    for c in coset(9, node, 11, full_box(11)):
        n += 1
        v = v5.rep(gs, 11, c)
        out = any((r, c[r]) in covered or (r, v[r]) in covered for r in range(11))
        inside += not out
        assert out or ok(c), c
        assert out or v in enumerated or not test(c), c
        covered_outside += out
    assert n == 725216, n
    assert inside + covered_outside == n and inside >= len(enumerated) and covered_outside > 0


def q_coverage_ramp_by_13():
    # Replicata: leaf 0's ramp child by 13: its count box and box split; independently, the count vectors mod 13 of
    # the child's integer system inside the box, by coset.
    # Expectata (the mutants angle: a property at 13, where q_box_split_regression pins counts only): the outside
    # nodes are exactly the (class, value) pairs outside the box; the coset holds at least the 1908 enumerated vectors;
    # every coset vector in the residue lattice of order 9 has an orbit representative (under the child's stabilizer)
    # that is an own child or a pool member or lies outside the box (so an outside node covers it).
    at(304, 9)
    node = leaf(0) + ((11, (RAMP,)),)
    rel = v5.Relaxation(9, node, 13)
    lo, hi = box = bx.count_box(rel)
    own, pool, outside, _ = bx.box_split(9, node, 13, rel, box)
    assert sorted(outside) == [(r, t) for r in range(13) for t in range(v5.size(13, r) + 1) if not lo[r] <= t <= hi[r]]
    enumerated = set(own) | set(pool)
    gs = v5.stabilizer(node)
    span = v5.ExactSystem(v5.lattice_basis(13, 9)).fiber(())
    n = 0
    for c in coset(9, node, 13, box):
        n += 1
        v = v5.rep(gs, 13, c)
        assert (not span([2 * t - v5.size(13, r) for r, t in enumerate(c)]) or v in enumerated
                or any(not lo[r] <= v[r] <= hi[r] for r in range(13))), c
    assert n >= len(enumerated) == 1908, (n, len(enumerated))


# ---------- outside nodes ----------

def q_outside_nodes_of_leaf0():
    # Replicata: every outside node of leaf 0 by 11 (128) through solve_piece with its outside_moments at POOL_BUDGET;
    # for class 0's lowest value, certbb's tokens collected and checked by certbb.verify on the outside node's moments
    # and node, then forged: the multipliers negated; all zero; the extra row's multiplier zeroed (what is left is a
    # certificate for the node itself, which has LP points); the proof emptied; its token doubled; and the genuine proof
    # checked against the value next to it inside the box.
    # Expectata: each outside node is INFEASIBLE with 1 LP solve and 1 leaf (the root's certificate), its key the
    # node's then 11:r=t; the collected proof's sha1 is the record's and verify accepts it; every forgery raises
    # ProofError.
    at(304, 9)
    node = leaf(0)
    rel = v5.Relaxation(9, node, 11)
    lo, hi = box = bx.count_box(rel)
    outside = bx.box_split(9, node, 11, rel, box)[2]
    assert len(outside) == 128
    for r, t in outside:
        verdict, a, found = bx.solve_piece(bx.outside_moments(9, 11, r, t), node, v5.POOL_BUDGET)
        assert (verdict, a, found['lps'], found['leaves']) == ('INFEASIBLE', None, 1, 1), (r, t, verdict, found)
        assert bx.outside_key(node, 11, r, t) == f'{OPEN8[0]} 11:{r}={t}'
    r, t = 0, lo[0] - 1
    mom = bx.outside_moments(9, 11, r, t)
    tokens = []
    assert certbb.solve(mom, node, v5.POOL_BUDGET, tokens.append)[0] == 'INFEASIBLE'
    assert len(tokens) == 1 and tokens[0][0] == 'L'
    assert certbb.verify(mom, node, tokens) == bx.solve_piece(mom, node, v5.POOL_BUDGET)[2]['proof']
    n = tokens[0][1]
    assert len(n) == 10 + sum(P for P, _ in node) and n[9] != 0
    for proof in ([('L', [-c for c in n])], [('L', [0] * len(n))], [('L', n[:9] + [0] + n[10:])], [], tokens * 2):
        expect_proof_error(lambda: certbb.verify(mom, node, proof))
    expect_proof_error(lambda: certbb.verify(bx.outside_moments(9, 11, r, lo[0]), node, tokens))


def q_negative_control_at_order_8():
    # Replicata: at order 8, where the example of length 304 exists, its depth-6 node (the example followed down the
    # cascade as the control follows it), by 11, then its depth-7 node (followed down 11 too), by 13; at each, for
    # every element g of the node's stabilizer, the image g(a) of the example and its counts w mod M, and for each
    # class r the outside node (r, w[r]) at order 8 through solve_piece, at POOL_BUDGET and pinned to g(a); the count
    # box at order 8 and, for each class, the outside nodes at the values just outside it (lo - 1 and hi + 1 when in
    # [0, size]), their proofs collected.
    # Expectata (extended to 13 and to every stabilizer element at the soundness angle's asking): each stabilizer has
    # two elements; no (r, w[r]) node is INFEASIBLE (its LP has g(a)); pinned, each is FEASIBLE with g(a); the
    # just-outside nodes (22 by 11, 26 by 13) are INFEASIBLE in 1 LP solve each, and each one's proof raises
    # ProofError when checked against (r, w[r])'s moments: a certificate for one value closes no value the example
    # has.
    at(304, 9)
    node, a = example_node(8, 6)
    checked = 0
    for M in (11, 13):
        gs = v5.stabilizer(node)
        assert len(gs) == 2, gs
        for g in gs:
            ag = v5.act_seq(g, a)
            w = v5.counts(ag, M)
            x = [(t + 1) // 2 for t in ag]
            for r in range(M):
                mom = bx.outside_moments(8, M, r, w[r])
                assert bx.solve_piece(mom, node, v5.POOL_BUDGET)[0] != 'INFEASIBLE', (M, g, r)
                assert bx.solve_piece(mom, node, 1, x, x)[:2] == ('FEASIBLE', ag), (M, g, r)
        w = v5.counts(a, M)
        lo, hi = bx.count_box(v5.Relaxation(8, node, M))
        assert all(lo[r] <= w[r] <= hi[r] for r in range(M))
        for r in range(M):
            for t in (lo[r] - 1, hi[r] + 1):
                if 0 <= t <= v5.size(M, r):
                    mom = bx.outside_moments(8, M, r, t)
                    tokens = []
                    assert certbb.solve(mom, node, v5.POOL_BUDGET, tokens.append)[0] == 'INFEASIBLE' and len(tokens) == 1, (M, r, t)
                    expect_proof_error(lambda: certbb.verify(bx.outside_moments(8, M, r, w[r]), node, tokens))
                    checked += 1
        node, a = bx.follow(node, a, M)
    assert checked == 22 + 26, checked


def q_outside_node_takes_the_width_test():
    # Replicata: at 240@11, where the width test closes nodes, the leaf THIN240 through certbb.solve at POOL_BUDGET,
    # its tokens collected; then the node outside_moments(11, 17, 0, t) on it, t the middle of class 0's count box by
    # 17 (so that its LP is feasible, as an outside node's is where HiGHS and GLOP disagree at the box's edge), through
    # certbb.solve and solve_piece at POOL_BUDGET; the Guides that certbb.solve makes for the two, watched.
    # Expectata: the outside node's Guide has the leaf's rows A, and its keep is the leaf's with the count rows'
    # node_rows indices one higher: it skips the further row (index 11, moments.order); both are INFEASIBLE in 3 LP
    # solves, 2 leaves and 1 cut, on the tokens D, L, L; the outside node's cut is the leaf's own (the further row only
    # narrows the LP's polytope, so the thin direction stays thin) and its certificates are one entry longer (the
    # further row's); certbb.verify accepts the outside node's tokens on its moments, with solve_piece's proof sha1,
    # and refuses them on the leaf's moments (ProofError).
    v5.configure(240, 11)
    node = bx.parse_key(THIN240)
    lo, hi = bx.count_box(v5.Relaxation(11, node, 17))
    mom = bx.outside_moments(11, 17, 0, (lo[0] + hi[0]) // 2)
    guides, tokens = [], ([], [])

    class Guide(certbb.Guide):
        def __init__(self, moments, lp):
            super().__init__(moments, lp)
            guides.append(self)

    with patched(certbb, Guide=Guide):
        got = [certbb.solve(m, node, v5.POOL_BUDGET, out.append) for m, out in ((v5.moments(11), tokens[0]), (mom, tokens[1]))]
    leaf, outside = guides
    assert mom.order == 11 and len(mom.W) == len(mom.rhs) == len(mom.sparse) == 12
    assert outside.A == leaf.A and outside.keep == leaf.keep[:11] + [i + 1 for i in leaf.keep[11:]] and 11 not in outside.keep
    for (verdict, _, stats), out in zip(got, tokens, strict=True):
        assert (verdict, stats['lp'], stats['leaves'], stats['cuts']) == ('INFEASIBLE', 3, 2, 1), (verdict, stats)
        assert [t[0] for t in out] == ['D', 'L', 'L'], [t[0] for t in out]
    assert tokens[1][0] == tokens[0][0] and all(len(b[1]) == len(a[1]) + 1 for a, b in zip(tokens[0][1:], tokens[1][1:]))
    assert certbb.verify(mom, node, tokens[1]) == bx.solve_piece(mom, node, v5.POOL_BUDGET)[2]['proof']
    expect_proof_error(lambda: certbb.verify(v5.moments(11), node, tokens[1]))
    at(304, 9)


def q_small_n_oracle():
    # Replicata: the configuration 24@4 (cascade (3, 4), budgets (1, 1, 1); extension (5, 7), budgets (50, 1000))
    # patched into overnight_v5.SETTINGS and boxsplit.EXTENSION; all ±1 sequences of length 24 with vanishing power
    # sums for k < 4 (16, by meet in the middle), each followed down the cascade as the control follows the example
    # (2 nodes); for each node, every piece of its extension tree as close_tree makes them, each solved on its own, on
    # the real count box and on two boxes cut at random by up to 2 at each end (seeded).
    # Expectata (the soundness angle's smalln2.py at 24@4): no piece that holds a sequence of the node (an outside
    # node: count t in class r; a pool: counts among its members; an own child: those counts) is INFEASIBLE; and every
    # sequence of the node has an image under the node's stabilizer that some piece holds.
    with patched(v5, SETTINGS=v5.SETTINGS | {(24, 4): ((3, 4), (1, 1, 1))}), \
         patched(bx, EXTENSION=bx.EXTENSION | {(24, 4): ((5, 7), (50, 1000))}):
        bx.configure(24, 4)
        real = real_sequences(24, 4)
        assert len(real) == 16 and all(v5.exact_order(list(b)) >= 4 for b in real)
        nodes = set()
        for a in real:
            node, b = (), list(a)
            for M in v5.CASCADE: node, b = bx.follow(node, b, M)
            nodes.add(node)
        assert len(nodes) == 2, nodes
        rng, n = random.Random(7), 0
        for node in sorted(nodes):
            realin = [b for b in real if all(v5.counts(list(b), P) == V[0] for P, V in node)]
            gs = v5.stabilizer(node)
            for shrink in (False, True, True):
                held_all = set()
                for kind, held, verdict in oracle_pieces(4, node, 0, realin, shrink, rng):
                    n += 1
                    assert not (held and verdict == 'INFEASIBLE'), (node, kind, verdict, len(held))
                    held_all |= set(held)
                for b in realin:
                    assert any(tuple(v5.act_seq(g, list(b))) in held_all for g in gs), (node, b)
        assert n > 0
    at(304, 9)


# ---------- the startup control and solve_piece ----------

def q_startup_control():
    # Replicata: control() at 304@9; control() with box_split faked to make no own child.
    # Expectata: the first returns, so the order-8 example of length 304, followed down the cascade and the extension,
    # lands in an own child at 11 and at 13 and certbb pinned to it says FEASIBLE at order 8 and INFEASIBLE at order 9;
    # the second: AssertionError in control.
    at(304, 9)
    bx.control()
    with patched(bx, box_split=lambda *args: ([], (), [], {})):
        expect_assertion(bx.control, 'control')


def q_control_checks_order_and_moduli():
    # Replicata: control() with box_split watched; control() with solve_piece faked to say FEASIBLE on the moments of
    # ORDER.
    # Expectata (the mutants angle): the control's box splits are at order 8 by 11, then by 13 (every extension
    # modulus, in order), each inside the count box cut to within CONTROL_CUT of the example; the faked one:
    # AssertionError in control.
    at(304, 9)
    seen, real_split, real_piece = [], bx.box_split, bx.solve_piece

    def spy(order, node, M, rel, box):
        seen.append((order, M, max(h - l for l, h in zip(*box))))
        return real_split(order, node, M, rel, box)

    with patched(bx, box_split=spy):
        bx.control()
    assert [s[:2] for s in seen] == [(8, 11), (8, 13)] and all(s[2] <= 2 * bx.CONTROL_CUT for s in seen), seen
    assert bx.CONTROL_CUT == 2

    def lenient(moments, node, budget, lo=None, hi=None):
        got = real_piece(moments, node, budget, lo, hi)
        return ('FEASIBLE',) + got[1:] if moments is v5.moments(v5.ORDER) else got

    with patched(bx, solve_piece=lenient):
        expect_assertion(bx.control, 'control')


def q_control_checks_the_extension_at_order():
    # Replicata: control() four times, each with one thing faked at ORDER (9) alone, where the order-8 example cannot
    # see it: (a) overnight_v5.lattice_basis giving, for an extension modulus at ORDER, the basis of ORDER + 1 (a
    # proper sublattice, which misses generators of ORDER's lattice); (b) overnight_v5.integer_system giving, for a
    # prefix of moduli that ends in an extension modulus, the system of the same rows but the last count row doubled
    # (its lattice holds no column with a 1 in that row); (c) outside_moments taking the count row of the class after
    # r; (d) outside_moments taking the moment rows of order 8 whatever order is asked.
    # Expectata (the soundness angle: overnight_v5.control's exact checks at ORDER, made for the extension, and a
    # pinned outside node per extension modulus): AssertionError in control each time, from (a) the generators'
    # check, (b) the columns' check, (c) the pinned outside node's FEASIBLE check, (d) its INFEASIBLE check.
    at(304, 9)
    basis, system, moments = v5.lattice_basis, v5.integer_system, bx.outside_moments

    def sub(M, order):
        return basis(M, order + 1) if order == v5.ORDER and M in bx.MODULI else basis(M, order)

    def doubled(order, moduli):
        if order != v5.ORDER or moduli[-1] not in bx.MODULI: return system(order, moduli)
        rows = v5.moment_rows(order)[0] + sum((v5.count_rows(M) for M in moduli), ())
        return v5.ExactSystem(rows[:-1] + (tuple(2 * t for t in rows[-1]),))

    with patched(v5, lattice_basis=sub):
        assert 'gens' in expect_assertion(bx.control, 'control').line
    with patched(v5, integer_system=doubled):
        assert 'solvable' in expect_assertion(bx.control, 'control').line
    with patched(bx, outside_moments=lambda order, M, r, t: moments(order, M, (r + 1) % M, t)):
        assert "'FEASIBLE'" in expect_assertion(bx.control, 'control').line
    with patched(bx, outside_moments=lambda order, M, r, t: moments(8, M, r, t)):
        assert "'INFEASIBLE'" in expect_assertion(bx.control, 'control').line


def q_solve_piece_pins_to_solve_node():
    # Replicata: at 304@9, the bottom leaf the journal (read as written) records INFEASIBLE in the fewest LP solves, at
    # that budget plus 10; leaf 0 at budget 5 (UNKNOWN); the order-8 example's depth-6 node pinned to the example at
    # orders 8 and 9; each through solve_piece with moments(order) and through overnight_v5.solve_node.
    # Expectata: identical (verdict, sequence, {lps, leaves, proof}) each time, so solve_piece is solve_node but for
    # taking the moments as a parameter.
    with as_written():
        journal = v5.Journal(v5.JOURNAL)
    cheapest = min((r['lps'], k) for k, r in journal.records.items()
                   if r['verdict'] == 'INFEASIBLE' and '#' not in k and len(k.split()) == 6)
    node8, a = example_node(8, 6)
    x = [(t + 1) // 2 for t in a]
    for order, node, budget, lo, hi in ((9, bx.parse_key(cheapest[1]), cheapest[0] + 10, None, None),
                                        (9, leaf(0), 5, None, None), (8, node8, 1, x, x), (9, node8, 1, x, x)):
        mine = bx.solve_piece(v5.moments(order), node, budget, lo, hi)
        theirs = v5.solve_node(order, node, budget, lo, hi)
        assert mine == theirs, (mine, theirs)
    assert bx.solve_piece(v5.moments(8), node8, 1, x, x)[0] == 'FEASIBLE'
    assert bx.solve_piece(v5.moments(9), leaf(0), 5)[0] == 'UNKNOWN'


def q_solve_piece_checks_the_end():
    # Replicata: solve_piece with certbb.solve faked to say INFEASIBLE after one split token and no certificate, and
    # after no token at all.
    # Expectata (the mutants angle): ProofError both times (an INFEASIBLE verdict stands only on a complete proof).
    at(304, 9)

    def short(moments, node, lps, emit, lo=None, hi=None, certificates=None):
        emit(('B', 0))
        return 'INFEASIBLE', None, {'lp': 1, 'leaves': 0}

    def silent(moments, node, lps, emit, lo=None, hi=None, certificates=None):
        return 'INFEASIBLE', None, {'lp': 0, 'leaves': 0}

    for fake in (short, silent):
        with patched(certbb, solve=fake):
            expect_proof_error(lambda: bx.solve_piece(v5.moments(9), leaf(0), 3))


# ---------- the driver's journal, pieces and trees ----------

def q_journal():
    # Replicata: the driver's header at 304@9; a fresh Journal under RUNS, a put, the file reopened; a path holding
    # overnight_v5's header; the driver's journal opened through overnight_v5.Journal.
    # Expectata: the header is overnight_v5.header() but for the tag, boxsplit, plus boxsplit, a 40-digit fingerprint
    # of the driver's verdict code; the fresh journal writes it and reopening admits the record (the records agree);
    # overnight_v5's header is refused (AssertionError in __init__), and so is the driver's by overnight_v5.Journal.
    at(304, 9)
    h = bx.header()
    assert h == v5.header() | {'tag': 'boxsplit', 'boxsplit': bx.CODE} and len(bx.CODE) == 40 and bx.CODE != v5.CODE
    path, _ = paths('journal')
    j = bx.Journal(path)
    assert json.loads(open(path).read().splitlines()[0]) == h
    found = {'lps': 1, 'leaves': 1, 'proof': hashlib.sha1(b'x').hexdigest()}
    j.put('k 11:0=4', 'INFEASIBLE', 3, found)
    assert bx.Journal(path).records == {'k 11:0=4': {'key': 'k 11:0=4', 'verdict': 'INFEASIBLE', 'budget': 3} | found}
    expect_assertion(lambda: v5.Journal(path), '__init__')
    other, _ = paths('v5header')
    open(other, 'w').write(json.dumps(v5.header()) + '\n')
    expect_assertion(lambda: bx.Journal(other), '__init__')


def q_settle_refuses_a_verdict_the_driver_never_writes():
    # Replicata: a fresh driver journal under RUNS holding, for the one own child of TRUTH by 11, a CLOSED record as
    # overnight_v5's search() writes one for a node whose children's subtrees are all closed (a verdict the driver
    # never writes, which overnight_v5.Journal admits after UNKNOWN or nothing and reuse() returns at any budget);
    # settle on that child at BUDGETS[0] with that journal; then close_tree on TRUTH with it.
    # Expectata (the soundness angle's closed_forgery.py): AssertionError in settle both times, so the record closes
    # nothing: the child is neither re-solved (its record stays the CLOSED one) nor taken as closed (close_tree does
    # not return).
    at(304, 9)
    node = bx.parse_key(TRUTH)
    rel = v5.Relaxation(9, node, 11)
    own = bx.box_split(9, node, 11, rel, bx.count_box(rel))[0]
    assert len(own) == 1, own
    child = node + ((11, (own[0],)),)
    key = v5.node_key(child)
    path, _ = paths('closed')
    journal = bx.Journal(path)
    journal.put(key, 'CLOSED', bx.BUDGETS[0], {})
    assert journal.reuse(key, bx.BUDGETS[0]) == 'CLOSED'
    expect_assertion(lambda: bx.settle(v5.moments(9), child, key, bx.BUDGETS[0], journal, quiet([])), 'settle')
    expect_assertion(lambda: bx.close_tree(9, node, 0, journal, quiet([])), 'settle')
    assert journal.records[key] == {'key': key, 'verdict': 'CLOSED', 'budget': bx.BUDGETS[0]}


def q_ground_truth_leaf_closes():
    # Replicata: the journaled INFEASIBLE leaf TRUTH (13499 LP solves in the run's journal, read as written) through
    # close_tree at order 9 with the extension, into a fresh journal under RUNS; the journal reread.
    # Expectata: close_tree returns (every piece closed) with a tally of 1 box split, 1 own child, 96 pool members and
    # 186 outside nodes (regression: verify-split's bench_B13499.txt), c of the members carried, c the size of the box
    # split's carried dict (regression, 2026-10-17: all 96); every record is INFEASIBLE, under the leaf's key, within
    # its budget, with a 40-digit proof sha1: the own child's 67 LP solves, the pool's 96 - c (one per member not
    # carried; 96 before carrying) and the outside nodes' 1 each, each record's leaves at most its LP solves but the
    # pool's, whose carried members close without one; GLOP's solves are the count box's 23 and one per vector not
    # carried; the reread journal holds the same records.
    with as_written():
        assert v5.Journal(v5.JOURNAL).records[TRUTH]['lps'] == 13499
    node = bx.parse_key(TRUTH)
    path, _ = paths('truth')
    journal, lines = bx.Journal(path), []
    tally = bx.close_tree(9, node, 0, journal, quiet(lines))
    rel = v5.Relaxation(9, node, 11)
    c = len(bx.box_split(9, node, 11, rel, bx.count_box(rel))[3])
    assert c == 96, c
    assert dict(tally) == {'splits': 1, 'own': 1, 'pool': 96, 'outside': 186, 'carried': c, 'lps': 67 + 96 - c + 186,
                           'glop': 1 + 22 + 97 - c}, dict(tally)
    recs = journal.records
    assert len(recs) == 188 and all(k.startswith(TRUTH + ' 11:') for k in recs)
    for r in recs.values():
        assert r['verdict'] == 'INFEASIBLE' and 0 <= r['lps'] <= r['budget'] and len(r['proof']) == 40, r
        assert 0 <= r['leaves'] <= r['lps'] + c * ('#' in r['key'].split()[-1]), r
    assert sorted(r['lps'] for r in recs.values()) == sorted([1] * 186 + [67, 96 - c])
    assert {r['budget'] for k, r in recs.items() if '=' in k} == {v5.POOL_BUDGET}
    assert bx.Journal(path).records == recs
    assert len(lines) == 4 and lines[0].startswith('{' + TRUTH + '} by 11')


def q_leaf0_tree():
    # Replicata: leaf 0 through close_tree at 304@9 with the run's extension (11, 13), budgets (10000, 2000000), into a
    # fresh journal under RUNS, with certbb.solve and certbb.Check watched and the journal's put watched.
    # Expectata (the mutants angle; the one qual whose tree goes down to 13 for real: the ramp child is UNKNOWN at
    # 10000): (a) each record rests on exactly one certbb.solve and one certbb.Check, both on the statement its key
    # names (the order's moment rows, plus the count row M:r=t for an outside key; the node of the key's other parts;
    # no pinned box); (b) at call time, an outside node's budget is POOL_BUDGET, a pool's POOL_BUDGET per member, an
    # own child's BUDGETS[depth - 7]; (c) the records are exactly the pieces of leaf 0's box split by 11 and of the box
    # split by 13 of each own child left UNKNOWN, recomputed here; (d) every outside node, pool and mod-13 own child is
    # INFEASIBLE, an own child UNKNOWN only with lps == budget; (e) regression: the tally is LEAF0_TALLY.
    at(304, 9)
    path, _ = paths('leaf0')
    journal, lines = bx.Journal(path), []
    solves, checks, seen = [], [], []
    real_solve, real_check, real_put = certbb.solve, certbb.Check, journal.put

    def budget_for(key, node):
        last = key.split()[-1]
        if '=' in last: return v5.POOL_BUDGET
        if '#' in last: return v5.POOL_BUDGET * len(node[-1][1])
        return bx.BUDGETS[len(node) - len(v5.CASCADE) - 1]

    def solve(moments, node, lps, emit, lo=None, hi=None, **kw):
        # at call time: never above the extension's budget for the node's depth (or a pool's per-member budget)
        assert lps <= max(bx.BUDGETS[len(node) - len(v5.CASCADE) - 1], v5.POOL_BUDGET * len(node[-1][1])), lps
        got = real_solve(moments, node, lps, emit, lo, hi, **kw)
        solves.append((moments.W, moments.rhs, v5.node_key(node), lo, hi, lps, node, got[0], got[2]['lp']))
        return got

    class Check(real_check):
        def __init__(self, moments, node, lo=None, hi=None):
            checks.append((moments.W, moments.rhs, v5.node_key(node), lo, hi))
            super().__init__(moments, node, lo, hi)

    def put(key, verdict, budget, found):
        assert len(solves) == len(checks) == len(seen) + 1, (key, len(solves), len(checks), len(seen))
        W, rhs, nkey, lo, hi, lps, node, said, used = solves[-1]
        assert checks[-1] == (W, rhs, nkey, lo, hi) and (W, rhs, nkey) == named(key) and lo is hi is None, key
        assert lps == budget == budget_for(key, node), (key, lps, budget)
        assert (verdict, found['lps']) == (said, used), (key, verdict, said, found['lps'], used)
        seen.append(key)
        real_put(key, verdict, budget, found)

    journal.put = put
    with patched(certbb, solve=solve, Check=Check):
        tally = bx.close_tree(v5.ORDER, leaf(0), 0, journal, quiet(lines))
    recs = journal.records
    assert sorted(seen) == sorted(recs)
    want, own = pieces(leaf(0), 11)
    assert want <= set(recs), sorted(want - set(recs))[:3]
    split = [c for c in own if recs[v5.node_key(c)]['verdict'] == 'UNKNOWN']
    for c in split:
        more, grand = pieces(c, 13)
        want |= more
        assert all(recs[v5.node_key(g)]['verdict'] == 'INFEASIBLE' for g in grand)
    assert set(recs) == want, (len(recs), len(want), sorted(set(recs) ^ want)[:5])
    for k, r in recs.items():
        own_child = not ('=' in k.split()[-1] or '#' in k.split()[-1])
        assert r['verdict'] == 'INFEASIBLE' or (own_child and r['verdict'] == 'UNKNOWN' and r['lps'] == r['budget']), r
    assert {v5.node_key(c) for c in split} == {k for k, r in recs.items() if r['verdict'] == 'UNKNOWN'}
    assert dict(tally) == LEAF0_TALLY, dict(tally)


def q_pool_unknown_stops_the_driver():
    # Replicata: close_tree on TRUTH with settle faked: outside nodes and own children INFEASIBLE, the pool UNKNOWN.
    # Expectata (the mutants angle): AssertionError in close_tree right after the pool's settle (186 outside nodes,
    # then the pool, and no own child settled).
    at(304, 9)
    calls = []

    def fake(moments, node, key, budget, journal, log, certificates=None):
        calls.append(key)
        verdict = 'UNKNOWN' if '#' in key.split()[-1] else 'INFEASIBLE'
        return {'key': key, 'verdict': verdict, 'budget': budget, 'lps': budget, 'leaves': 0, 'proof': '0' * 40}

    with patched(bx, settle=fake):
        expect_assertion(lambda: bx.close_tree(9, bx.parse_key(TRUTH), 0, None, quiet([])), 'close_tree')
    assert len(calls) == 187 and '#' in calls[-1].split()[-1] and all('=' in k.split()[-1] for k in calls[:-1]), calls[-3:]


def q_witness_and_failures_stop_the_driver():
    # Replicata: settle with solve_piece faked FEASIBLE with the order-8 example, at ORDER 8 (a witness) and at ORDER 9
    # (it fails the exact order check); close_tree with settle faked UNKNOWN; the journal after each.
    # Expectata: a witness is logged (its exact order and X) and SystemExit follows; at ORDER 9, AssertionError in
    # settle; an UNKNOWN outside node stops close_tree at once (AssertionError in close_tree, one settle made); nothing
    # is journaled in any case.  (Past the last modulus, close_tree stopped with an AssertionError until 2026-10-17,
    # when dreeves agreed that such a node be left open: q_a_node_past_the_last_modulus_stays_open.)
    at(304, 9)
    path, _ = paths('stop')
    journal, lines = bx.Journal(path), []
    a = v5.from_hex(v5.EXAMPLES[304, 8], 8)
    fake = lambda *args, **kw: ('FEASIBLE', a, {'lps': 1, 'leaves': 0, 'proof': '0' * 40})
    with patched(bx, solve_piece=fake), patched(v5, ORDER=8):
        try:
            bx.settle(v5.moments(9), leaf(0), 'k', 3, journal, quiet(lines))
        except SystemExit:
            pass
        else:
            raise AssertionError('no SystemExit')
    assert len(lines) == 1 and 'WITNESS FOUND in {k}, exact order 8: X = [' in lines[0], lines
    with patched(bx, solve_piece=fake):
        expect_assertion(lambda: bx.settle(v5.moments(9), leaf(0), 'k', 3, journal, quiet(lines)), 'settle')
    calls = []
    def unknown(moments, node, key, budget, journal, log, certificates=None):
        calls.append(key)
        return {'key': key, 'verdict': 'UNKNOWN', 'budget': budget, 'lps': budget, 'leaves': 0, 'proof': '0' * 40}
    with patched(bx, settle=unknown):
        expect_assertion(lambda: bx.close_tree(9, leaf(0), 0, journal, quiet(lines)), 'close_tree')
    assert len(calls) == 1 and calls[0].endswith(' 11:0=0'), calls
    assert journal.records == {} and open(path).read().count('\n') == 1


def q_a_node_past_the_last_modulus_stays_open():
    # Replicata: close_tree on TRUTH with the extension cut to its first modulus, 11 (budget 10000), and settle faked:
    # outside nodes and the pool INFEASIBLE, the own child UNKNOWN; then close_tree on leaf 0 at i = 2, past the last of
    # the extension's two moduli.
    # Expectata (dreeves, 2026-10-17: an own vector still open at its budget is recorded as open, and the run goes on):
    # no assertion; the first returns a tally whose open counts the one own child, its log's last line naming the
    # child open; the second returns a tally of one open node and no split, one line naming leaf 0 open; nothing is
    # journaled.
    at(304, 9)
    node = bx.parse_key(TRUTH)
    path, _ = paths('open')
    journal = bx.Journal(path)

    def fake(moments, node, key, budget, journal, log, certificates=None):
        verdict = 'UNKNOWN' if ':[' in key.split()[-1] else 'INFEASIBLE'
        return {'key': key, 'verdict': verdict, 'budget': budget, 'lps': budget, 'leaves': 0, 'proof': '0' * 40}

    lines = []
    with patched(bx, settle=fake, MODULI=(11,), BUDGETS=(10000,)):
        tally = bx.close_tree(9, node, 0, journal, quiet(lines))
    child = node + ((11, (bx.box_split(9, node, 11, v5.Relaxation(9, node, 11), bx.count_box(v5.Relaxation(9, node, 11)))[0][0],)),)
    assert tally['open'] == 1 and tally['own'] == 1, dict(tally)
    assert v5.node_key(child) in lines[-1] and 'open' in lines[-1], lines[-1]
    lines = []
    tally = bx.close_tree(9, leaf(0), 2, journal, quiet(lines))
    assert dict(tally) == {'open': 1} and len(lines) == 1 and OPEN8[0] in lines[0] and 'open' in lines[0], (dict(tally), lines)
    assert journal.records == {} and open(path).read().count('\n') == 1


SCRIPT = """import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {here!r})
import overnight_v5 as v5, boxsplit as bx
if __name__ == '__main__':
    bx.configure(304, 9)
    v5.JOURNAL, bx.JOURNAL, bx.LOG = {main!r}, {journal!r}, {log!r}
    bx.run()
"""


def q_run_on_one_leaf():
    # Replicata: the driver's run() in a child process on a made-up overnight_v5 journal under RUNS that holds the run's
    # header and the leaf TRUTH as UNKNOWN at the bottom budget, the driver's journal and log under RUNS too; then a
    # second run on the same files.
    # Expectata: each run's log holds the start line (1 open leaf), the control line and the final ALL 1 LEAVES CLOSED
    # line; the first also the leaf's start line, its box-split line and its summary line saying its extension tree
    # closed, and its journal the leaf's CLOSED record after the 188 pieces' records; the second skips the leaf, whose
    # CLOSED record it finds (since 2026-10-17; before, it reused every piece's record): no leaf line, nothing solved,
    # the journal unchanged; the made-up journal is unchanged too.
    at(304, 9)
    main = made_up_main()
    before = open(main).read()
    journal, log = paths('run')
    script = os.path.join(RUNS, 'run.py')
    open(script, 'w').write(SCRIPT.format(here=HERE, main=main, journal=journal, log=log))
    texts, records = [], []
    for _ in range(2):
        p = subprocess.run([sys.executable, '-B', script], capture_output=True, text=True, timeout=1800)
        assert p.returncode == 0, p.stderr[-3000:]
        texts.append(open(log).read())
        records.append(open(journal).read())
        os.rename(log, log + f'.{len(texts)}')
    for text in texts:
        assert 'start: n = 304, order at least 9, open leaves 1' in text, text
        assert 'startup control passed' in text and 'ALL 1 LEAVES CLOSED' in text and 'WITNESS' not in text, text
    assert f'leaf 0: {{{TRUTH}}}' in texts[0] and f'{{{TRUTH}}} by 11:' in texts[0], texts[0]
    assert f'leaf 0 {{{TRUTH}}}: extension tree closed' in texts[0], texts[0]
    assert TRUTH not in texts[1] and texts[0].count('INFEASIBLE') > 1 and texts[1].count('INFEASIBLE') == 1, texts[1]
    lines = records[0].splitlines()
    assert records[0] == records[1] and len(lines) == 190, len(lines)
    assert json.loads(lines[-1]) == {'key': TRUTH, 'verdict': 'CLOSED', 'budget': v5.node_budget(bx.parse_key(TRUTH))}
    assert open(main).read() == before


def q_run_works_leaves_in_parallel():
    # Replicata: the driver's run() in a child process, with its worker processes, on a made-up run journal holding
    # TRUTH and open leaf 2 (OPEN8[2]); then a second run on the same files.
    # Expectata (dreeves, 2026-10-17: the cases in parallel, in shuffled order): the first log holds the start line (2
    # open leaves), the control line, each leaf's start line in the order of their keys' sha1, each leaf's summary line
    # saying its tree closed, and ALL 2 LEAVES CLOSED; the driver's journal holds each leaf's CLOSED record; the second
    # run skips both leaves (no leaf line), writes no record and also ends ALL 2 LEAVES CLOSED.
    at(304, 9)
    keys = (TRUTH, OPEN8[2])
    main = made_up_main(keys)
    journal, log = paths('parallel')
    script = os.path.join(RUNS, 'parallel.py')
    open(script, 'w').write(SCRIPT.format(here=HERE, main=main, journal=journal, log=log))
    texts, records = [], []
    for _ in range(2):
        p = subprocess.run([sys.executable, '-B', script], capture_output=True, text=True, timeout=1800)
        assert p.returncode == 0, p.stderr[-3000:]
        texts.append(open(log).read())
        records.append(open(journal).read())
        os.rename(log, log + f'.{len(texts)}')
    first = texts[0]
    assert 'start: n = 304, order at least 9, open leaves 2' in first and 'startup control passed' in first, first
    order = sorted(keys, key=lambda k: hashlib.sha1(k.encode()).hexdigest())
    starts = [first.index(f'leaf {keys.index(k)}: {{{k}}}') for k in order]
    assert starts == sorted(starts), starts
    for i, k in enumerate(keys):
        assert f'leaf {i} {{{k}}}: extension tree closed' in first, (i, first)
    assert 'ALL 2 LEAVES CLOSED' in first and 'ALL 2 LEAVES CLOSED' in texts[1], texts[1]
    closed = [json.loads(line)['key'] for line in records[0].splitlines()[1:] if json.loads(line)['verdict'] == 'CLOSED']
    assert sorted(closed) == sorted(keys) and records[1] == records[0], closed
    assert not any(k in texts[1] for k in keys), texts[1]


def q_a_witness_in_a_worker_reaches_the_log():
    # Replicata: drive() on leaf 0 with SyncExecutor, a fresh driver journal and a list for its lines, at ORDER 8 with
    # solve_piece faked FEASIBLE with the order-8 example of length 304.
    # Expectata: SystemExit, after the leaf's start line and the worker's witness line (its exact order and X) are
    # written; the journal holds its header only.
    at(304, 9)
    path, _ = paths('witness')
    journal, lines = bx.Journal(path), []
    a = v5.from_hex(v5.EXAMPLES[304, 8], 8)
    fake = lambda *args, **kw: ('FEASIBLE', a, {'lps': 1, 'leaves': 0, 'proof': '0' * 40})
    with patched(bx, solve_piece=fake), patched(v5, ORDER=8):
        try:
            bx.drive([leaf(0)], journal, lines.append, SyncExecutor())
        except SystemExit:
            pass
        else:
            raise AssertionError('no SystemExit')
    assert f'leaf 0: {{{OPEN8[0]}}}' in lines[0] and any('WITNESS FOUND' in l and 'exact order 8' in l for l in lines), lines
    assert open(path).read().count('\n') == 1


def q_leaves_go_in_a_fixed_shuffle():
    # Replicata: drive() on the eight open leaves of OPEN8 with SyncExecutor and work_leaf faked to close each at once
    # (no record, an empty tally); then again with leaf 3's CLOSED record in the journal.
    # Expectata: the leaves' start lines come in the order of their keys' sha1, each followed by its summary line; each
    # leaf gets a CLOSED record; the second drive skips leaf 3, closed on record, and starts the other seven again in
    # the same order.
    at(304, 9)
    leaves = [leaf(i) for i in range(8)]
    order = sorted(range(8), key=lambda i: hashlib.sha1(OPEN8[i].encode()).hexdigest())
    fake = lambda node, known, source: ([], [], Counter(open=0, cpu=0.0))
    for skip in (None, 3):
        path, _ = paths(f'shuffle{skip}')
        journal, lines = bx.Journal(path), []
        if skip is not None: journal.put(OPEN8[skip], 'CLOSED', v5.node_budget(leaves[skip]), {})
        with patched(bx, work_leaf=fake):
            bx.drive(leaves, journal, lines.append, SyncExecutor())
        want = [i for i in order if i != skip]
        assert [l for l in lines if f'leaf {want[0]}: ' in l], lines
        got = [int(l.split('Claude: "leaf ')[1].split(':')[0]) for l in lines if ': {' in l and 'extension tree' not in l]
        assert got == want, (got, want)
        assert {k for k, r in bx.Journal(path).records.items() if r['verdict'] == 'CLOSED'} == {OPEN8[i] for i in range(8)}


def q_run_calls_the_control():
    # Replicata: run() in this process on a made-up run journal with TRUTH open, the order-8 example of length 304
    # replaced by another sequence (its last hex digit changed).
    # Expectata (the mutants angle): AssertionError in control; the driver's journal holds its header only; the log
    # has the start line and no control line.
    at(304, 9)
    journal, log = paths('control')
    bad = dict(v5.EXAMPLES)
    bad[304, 8] = bad[304, 8][:-1] + ('5' if bad[304, 8][-1] != '5' else '6')
    with patched(v5, JOURNAL=made_up_main(), EXAMPLES=bad), patched(bx, JOURNAL=journal, LOG=log):
        expect_assertion(bx.run, 'control')
    assert open(journal).read().count('\n') == 1
    text = open(log).read()
    assert 'start:' in text and 'startup control passed' not in text, text


def q_run_stops_when_a_leaf_does_not_close():
    # Replicata: run() in this process on a made-up run journal with TRUTH open, POOL_BUDGET 0 (every outside node
    # UNKNOWN at once), its leaves' work done in this process (SyncExecutor in place of the worker processes).
    # Expectata (the mutants angle): AssertionError out of close_tree through run(); the log has the control line and
    # no line saying a tree or all leaves closed.
    at(304, 9)
    journal, log = paths('fail')
    with patched(v5, JOURNAL=made_up_main(), POOL_BUDGET=0), patched(bx, JOURNAL=journal, LOG=log, make_executor=SyncExecutor):
        expect_assertion(bx.run, 'close_tree')
    text = open(log).read()
    assert 'startup control passed' in text and 'extension tree closed' not in text and 'LEAVES CLOSED' not in text, text


def q_code_covers_the_verdict_functions():
    # Replicata: boxsplit.CODE, and the sha1 of the source texts of the driver's verdict functions in the order the
    # vocabulary names them (carry since 2026-10-17: it decides which vectors GLOP sorts, and the pool's certificates).
    # Expectata (the mutants angle): equal.
    names = ('parse_key', 'open_leaves', 'admissible_box', 'count_box', 'carry', 'box_split', 'outside_moments',
             'outside_key', 'solve_piece', 'settle', 'close_tree')
    assert bx.CODE == hashlib.sha1(''.join(inspect.getsource(getattr(bx, n)) for n in names).encode()).hexdigest()


def q_run_journal_untouched():
    # Replicata: the 304@9 run's journal and log, hashed as the quals began and now.
    # Expectata: the same hashes: nothing here wrote them.
    assert tuple(hashlib.sha1(open(f, 'rb').read()).hexdigest() for f in MAIN) == UNTOUCHED


# ---------- runner ----------

def main():
    shutil.rmtree(RUNS, ignore_errors=True)
    os.makedirs(RUNS)
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
