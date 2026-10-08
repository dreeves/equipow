#!/usr/bin/env python3
"""Quals for overnight_v5.py and certbb.py.  Run: python3 quals_v5.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the
resultata (what happened instead).  Quals marked "regression" pin numbers found independently earlier, by
v2 and by agent recounts, rather than stating a property.  Most quals are quals_v4.py's, ported to v5 (those that
tested CP-SAT as the node solver now test certbb); the certbb section holds the quals of certbb's builder
(quals_certbb.py) and those for the review's fixes and for streaming verification.  The end-to-end quals run small
configurations whose answers are known from the paper's Table 2, with journals and logs under RUNS.  overnight_v4.py,
overnight_240_v3.py and CP-SAT appear only as independent references.
"""
import sys
sys.dont_write_bytecode = True
import os, time, random, itertools, subprocess, tempfile, traceback, json, inspect, types, math, hashlib
from concurrent.futures import Future
import numpy as np
import sympy as sp
import overnight_v5 as v5
import certbb
import overnight_v4 as v4
import overnight_240_v3 as v3
from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = tempfile.mkdtemp(prefix='v5runs-')
C_STAR = (14, 21, 3, 10, 17, 24, 31)          # v3's representative of the open mod-7 orbit (v2 used its R-image)
TOP4 = ((3, ((40, 40, 40),)), (5, ((24,) * 5,)), (7, (C_STAR,)), (4, ((30,) * 4,)))
# C2: a depth-8 leaf of the 240@11 run that CP-SAT closed in 11 CPU-s and certbb in about 200 LP solves
C2 = TOP4 + ((8, ((21, 17, 17, 21, 9, 13, 13, 9),)), (11, ((11,) * 9 + (5, 16),)),
              (13, ((7, 8, 9, 10, 11, 12, 6, 7, 8, 9, 10, 11, 12),)), (9, ((15, 9, 12, 15, 9, 12, 10, 22, 16),)))
EXAMPLE = v5.from_hex(v5.EXAMPLES[240, 10], 10)
SIGNS_12_3 = '+-+---+++-+-'                   # order 3, f(-1) = 8: found by CP-SAT for these quals
V4_CUTS = (27, 25, 32, 11, 13)                # overnight_v4's cut moduli at 240@11 and 304@9, kept here as test moduli
V3_JOURNAL = os.path.join(HERE, 'overnight_240_v3_journal.jsonl')      # read only
BIG = 10 ** 9                                 # an LP-solve limit no qual's solve reaches


def x01(a): return [(t + 1) // 2 for t in a]
def members(children): return [v for c in children for v in c[-1][1]]
def example_node(Ms): return tuple((M, (v5.counts(EXAMPLE, M),)) for M in Ms)
def choice_of(node): return [(M, V[0]) for M, V in node]


def status_of(md):
    """CP-SAT's status word for a model, solved as overnight_v4 solves a node (an independent reference)."""
    return cp_model.CpSolver().StatusName(v4.solve(md, 120)[1])


def at(n, order):
    """Configure v5 for (n, order) unless it already is."""
    if (v5.N, v5.ORDER) != (n, order): v5.configure(n, order)


def at4(n, order):
    """Configure overnight_v4 (the reference) for (n, order) unless it already is."""
    if (v4.N, v4.ORDER) != (n, order): v4.configure(n, order)


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


class length:
    """A with-block in which v5's N is n, with no cached results from any other N on the way in or out."""
    def __init__(self, n): self.n = n
    def __enter__(self):
        self.saved = v5.N
        v5.N = self.n
        for f in v5.CACHED: f.cache_clear()
    def __exit__(self, *exc):
        v5.N = self.saved
        for f in v5.CACHED: f.cache_clear()


class uncached:
    """A with-block that shares no cached results with the code before or after it."""
    def __enter__(self):
        for f in v5.CACHED: f.cache_clear()
    def __exit__(self, *exc):
        for f in v5.CACHED: f.cache_clear()


def cpsat_enumerate(order, M, fixed):
    """Independent enumeration of admissible count vectors with CP-SAT (v2's method, parent sums generalized)."""
    md = cp_model.CpModel()
    c = [md.NewIntVar(0, v5.size(M, r), f'c{r}') for r in range(M)]
    md.Add(sum(c) == v5.N // 2)
    v4.add_lattice(md, [2 * c[r] - v5.size(M, r) for r in range(M)], v5.lattice_basis(M, order), 'z')
    for P, w in fixed:
        for q in range(P): md.Add(sum(c[r] for r in range(q, M, P)) == w[q])
    out = []
    class Collect(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self): out.append(tuple(self.Value(t) for t in c))
    sv = cp_model.CpSolver(); sv.parameters.enumerate_all_solutions = True; sv.parameters.num_workers = 1
    assert sv.Solve(md, Collect()) == cp_model.OPTIMAL
    return tuple(sorted(set(out)))


def residue_lattice_gens(M, order, plus):
    """Independent generators: the cyclic shifts of (x-1)^order, times x+1 if plus, reduced mod x^M - 1 (sympy)."""
    x = sp.symbols('x')
    p = sp.Poly((x - 1) ** order * (x + 1) ** int(plus), x)
    gens = []
    for k in range(M):
        r = sp.Poly(sp.rem(x ** k * p.as_expr(), x ** M - 1, x), x)
        gens.append([int(r.coeff_monomial(x ** i)) for i in range(M)])
    return gens


def power_sum_solutions(n, m):
    """Every +-1 sequence of even length n whose power sums sum_p a_p p^k vanish for k < m, found without v5:
    meet in the middle on the two halves' power sums (in int64, asserted not to overflow), each solution then
    checked with exact integers."""
    assert n % 2 == 0
    h = n // 2
    def sums(offset):
        """Row i: the power sums over positions offset + p, p < h, with sign + exactly where bit p of i is 1."""
        P = np.array([[(offset + p) ** k for k in range(m)] for p in range(h)], dtype=np.int64)
        assert sum(abs(int(e)) for e in P.flat) < 2 ** 62
        S = np.zeros((1, m), dtype=np.int64)
        for p in range(h): S = np.concatenate([S - P[p], S + P[p]])
        return S
    L, R = sums(0), -sums(h)                        # a solution: row i of L equal to row j of R
    base = np.minimum(L.min(axis=0), R.min(axis=0))
    span = [int(t) + 1 for t in np.maximum(L.max(axis=0), R.max(axis=0)) - base]
    assert math.prod(span) < 2 ** 63
    weight = np.array([math.prod(span[:k]) for k in range(m)], dtype=np.int64)
    kl, kr = (L - base) @ weight, (R - base) @ weight   # mixed radix: equal keys exactly for equal rows
    order = np.argsort(kl, kind='stable')
    lo, hi = np.searchsorted(kl[order], kr, 'left'), np.searchsorted(kl[order], kr, 'right')
    def signs(i): return [2 * (int(i) >> p & 1) - 1 for p in range(h)]
    out = [signs(order[t]) + signs(j) for j in np.flatnonzero(hi > lo) for t in range(lo[j], hi[j])]
    assert all(sum(t * p ** k for p, t in enumerate(a)) == 0 for a in out for k in range(m))
    return out


def run_child(code, *flags, timeout=900):
    """Run code in a fresh Python process (with these interpreter flags), its working directory this one's."""
    path = os.path.join(tempfile.mkdtemp(), 'child.py')
    open(path, 'w').write(code)
    return subprocess.run([sys.executable, '-B', *flags, path], capture_output=True, text=True, timeout=timeout,
                           cwd=HERE)


# ---------- settings and configuration ----------

def q_settings_table():
    # Replicata: SETTINGS and EXAMPLES, against overnight_v4's SETTINGS.
    # Expectata: the same configurations as v4's, each with v4's cascade, so (240, 11) has overnight_240_v3.py's; every
    # entry has one budget per depth plus the bottom, each a positive whole number of LP solves; every entry has its
    # control's examples: one of length N and order ORDER - 1, and at least one of order ORDER.
    assert v5.SETTINGS[240, 11][0] == v3.CASCADE
    assert set(v5.SETTINGS) == set(v4.SETTINGS) and all(v5.SETTINGS[k][0] == v4.SETTINGS[k][0] for k in v4.SETTINGS)
    for (n, order), (cascade, budget) in v5.SETTINGS.items():
        assert len(budget) == len(cascade) + 1 and all(type(b) is int and b >= 1 for b in budget), (n, order)
        assert (n, order - 1) in v5.EXAMPLES, (n, order)
        assert any(m == order for _, m in v5.EXAMPLES), (n, order)
    assert type(v5.POOL_BUDGET) is int and v5.POOL_BUDGET >= 1


def q_examples_exact():
    # Replicata: every code in EXAMPLES, decoded.  Expectata: its key's length and, by exact power sums, its
    # key's exact order.
    for (n, m), h in v5.EXAMPLES.items():
        a = v5.from_hex(h, m)
        assert len(a) == n and v5.exact_order(a) == m, (n, m)


def q_configure():
    # Replicata: configure(304, 9); then configure(240, 12), which SETTINGS lacks.
    # Expectata: N, ORDER, CASCADE and BUDGET from SETTINGS, the journal and log named for v5, N and ORDER next to
    # overnight_v5.py; then AssertionError in configure.
    v5.configure(304, 9)
    assert (v5.N, v5.ORDER, (v5.CASCADE, v5.BUDGET)) == (304, 9, v5.SETTINGS[304, 9])
    assert v5.JOURNAL == os.path.join(HERE, 'overnight_v5_304_9_journal.jsonl')
    assert v5.LOG == os.path.join(HERE, 'overnight_v5_304_9.log')
    expect_assertion(lambda: v5.configure(240, 12), 'configure')


def q_journal_and_log_names_differ_from_v4s():
    # Replicata: every configuration in SETTINGS, configured in v5 and in overnight_v4.
    # Expectata: v5's journal and log paths are never v4's, so a v5 run never touches a v4 run's files.
    for n, order in v5.SETTINGS:
        v5.configure(n, order)
        v4.configure(n, order)
        assert {v5.JOURNAL, v5.LOG}.isdisjoint({v4.JOURNAL, v4.LOG}), (n, order)
        assert len({v5.JOURNAL, v5.LOG, v4.JOURNAL, v4.LOG}) == 4, (n, order)


def q_certbb_is_exact_beyond_64_bits():
    # Replicata: at 432@12, with a SETTINGS entry that exists only for this qual (overnight_v4 refused 432@12: its
    # moment rows' |coefficients| sum to about 9.0e19, beyond CP-SAT's 64-bit integers): configure; then the order-11
    # example of length 432 from EXAMPLES on its own count node mod 3, 5, 4 and 7, the box pinned to it at all but 12
    # random positions, solved at order 11 and at order 12.
    # Expectata: configure passes and some moment row's |coefficients| sum to more than 2^62; at order 11, FEASIBLE with
    # a sequence of the box of exact order at least 11; at order 12, INFEASIBLE (its proof checked by solve_node).
    with patched(v5, SETTINGS=v5.SETTINGS | {(432, 12): ((3, 5, 4, 7), (1,) * 5)}):
        v5.configure(432, 12)
    try:
        assert max(sum(map(abs, row)) for row in v5.moment_rows(12)[0]) > 2 ** 62
        b = v5.from_hex(v5.EXAMPLES[432, 11], 11)
        node = tuple((M, (v5.counts(b, M),)) for M in (3, 5, 4, 7))
        free = random.Random(12).sample(range(432), 12)
        lo = [0 if p in free else t for p, t in enumerate(x01(b))]
        hi = [1 if p in free else t for p, t in enumerate(x01(b))]
        verdict, a, found = v5.solve_node(11, node, BIG, lo, hi)
        assert verdict == 'FEASIBLE' and v5.exact_order(a) >= 11, (verdict, found)
        assert all(l <= t <= u for t, l, u in zip(x01(a), lo, hi))
        verdict, _, found = v5.solve_node(12, node, BIG, lo, hi)
        assert verdict == 'INFEASIBLE' and found['leaves'] >= 1, (verdict, found)
    finally:
        v5.configure(240, 11)


def q_configure_forgets_cached_results():
    # Replicata: moment rows, certbb's moments, a lattice basis and an admissible set computed at 240@11, then again
    # after configure(304, 9), then again after configure(240, 11).
    # Expectata: each answer belongs to the N configured when it was asked for.
    v5.configure(240, 11)
    a = (v5.moment_rows(9), v5.lattice_basis(4, 8), v5.admissible(9, 3, ()), v5.moments(9).N)
    v5.configure(304, 9)
    b = (v5.moment_rows(9), v5.lattice_basis(4, 8), v5.admissible(9, 3, ()), v5.moments(9).N)
    v5.configure(240, 11)
    c = (v5.moment_rows(9), v5.lattice_basis(4, 8), v5.admissible(9, 3, ()), v5.moments(9).N)
    assert len(a[0][0][0]) == 240 and len(b[0][0][0]) == 304 and a == c
    assert a[1] != b[1] and a[2] != b[2] and (a[3], b[3]) == (240, 304)
    assert all(sum(w) == 152 for w in b[2]) and all(sum(w) == 120 for w in a[2])


def q_command_line():
    # Replicata: overnight_v5.py run with no arguments, and with 240 12 (no SETTINGS entry).
    # Expectata: each exits at once with AssertionError (the usage message, then the missing settings), and
    # leaves no journal or log behind.
    for args, words in (([], 'usage'), (['240', '12'], 'no settings for N = 240, order 12')):
        p = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'overnight_v5.py')] + args,
                           capture_output=True, text=True, timeout=300)
        assert p.returncode != 0 and 'AssertionError' in p.stderr and words in p.stderr, p.stderr[-600:]
    assert not any(os.path.exists(os.path.join(HERE, f)) for f in ('overnight_v5_240_12_journal.jsonl', 'overnight_v5_240_12.log'))


def q_v5_is_v4_but_the_node_solver():
    # Replicata: at 240@11, overnight_v4's and overnight_v5's code side by side.
    # Expectata: v5 drops exactly v4's CP-SAT code (add_lattice, build_model, solve, status_with_fix) and adds moments;
    # every other function and class v4 fingerprints into CODE, and the split's helpers, is textually identical, except
    # solve_node (certbb's, see its quals) and work and search, which differ from v4's by exactly the edits below,
    # carrying the solve's journal fields (lps, leaves, proof) to the journal; lattice bases agree for every modulus in
    # play at orders 10 and 11; the first four splits agree.
    at(240, 11)
    at4(240, 11)
    def names(mod): return {k for k, f in vars(mod).items() if callable(f) and getattr(f, '__module__', None) == mod.__name__}
    assert names(v4) - names(v5) == {'add_lattice', 'build_model', 'solve', 'status_with_fix'}, names(v4) - names(v5)
    assert names(v5) - names(v4) == {'moments'}, names(v5) - names(v4)
    same = ('lattice_poly', 'lattice_basis', 'moment_rows', 'count_rows', 'ExactSystem', 'integer_system', 'admissible',
            'act', 'stabilizer', 'rep', 'split', 'node_key', 'node_budget', 'moment_basis', 'Relaxation', 'is_pool',
            'size', 'gbinom', 'from_hex', 'exact_order', 'counts', 'act_seq', 'say_witness', 'log_to_file',
            'make_executor')
    for name in same:
        assert inspect.getsource(getattr(v4, name)) == inspect.getsource(getattr(v5, name)), name
    edits = {'work': (('CP-SAT\'s verdict within the budget', 'certbb\'s verdict within the budget'),
                      ('the worker must run the very file whose control passed.  Returns (verdict, the sequence of a FEASIBLE\n    verdict or None, children, solve seconds, split seconds, the split\'s LP failures)',
                       'the worker must run the very files, this one and certbb.py, whose control passed.  Returns (verdict, the\n    sequence of a FEASIBLE verdict or None, children, solve seconds, split seconds, the split\'s LP failures, the\n    solve\'s journal fields or None for known)'),
                      ('verdict, a = (known, None) if known else', 'verdict, a, found = (known, None, None) if known else'),
                      ('Relaxation.failures - failures\n', 'Relaxation.failures - failures, found\n')),
             'search': (("journal.put(node_key(p), 'CLOSED', node_budget(p))", "journal.put(node_key(p), 'CLOSED', node_budget(p), {})"),
                        ('t_split, failures = f.result()', 't_split, failures, found = f.result()'),
                        ('# a CP-SAT solution must pass', '# a certbb solution must pass'),
                        ('verdict, node_budget(node))\n', 'verdict, node_budget(node), found)\n'))}
    for name, pairs in edits.items():
        text = inspect.getsource(getattr(v4, name))
        for old, new in pairs:
            assert text.count(old) == 1, (name, old)
            text = text.replace(old, new)
        assert text == inspect.getsource(getattr(v5, name)), name
    for order in (10, 11):
        for M in sorted(set(v4.CASCADE + V4_CUTS)):
            assert v4.lattice_basis(M, order) == v5.lattice_basis(M, order), (order, M)
    node = ()
    for M in (3, 5, 7, 4):
        assert v4.split(11, node) == v5.split(11, node), M
        node = TOP4[:len(node) + 1]


# ---------- symmetry ----------

def q_group_action_on_counts():
    # Replicata: 40 random +-1 sequences; every g in G; every modulus in play, and v4's cut moduli.
    # Expectata: the counts of g(a) equal act(g, M, counts of a).
    at(240, 11)
    rng = random.Random(1)
    for _ in range(40):
        a = [rng.choice((1, -1)) for _ in range(v5.N)]
        for g in v5.GROUP:
            for M in sorted(set(v5.CASCADE + V4_CUTS + (2, 16))):
                assert v5.counts(v5.act_seq(g, a), M) == v5.act(g, M, v5.counts(a, M)), (g, M)


def q_group_preserves_order():
    # Replicata: the published example (a palindrome), and a non-palindromic sequence of order >= 4: a
    # Thue-Morse block of length 16 times a random +-1 pattern of length 15.
    # Expectata: every g in G preserves each one's exact order.
    at(240, 11)
    rng = random.Random(2)
    tm = [(-1) ** bin(i).count('1') for i in range(16)]
    h = [rng.choice((1, -1)) for _ in range(15)]
    u = [tm[i % 16] * h[i // 16] for i in range(v5.N)]
    assert u != u[::-1] and u != [-t for t in u[::-1]]
    assert v5.exact_order(EXAMPLE) == 10 and v5.exact_order(u) >= 4
    for a in (EXAMPLE, u):
        for g in v5.GROUP: assert v5.exact_order(v5.act_seq(g, a)) == v5.exact_order(a), g


def q_stabilizers():
    # Replicata: the top node; the open mod-4 node; that node with another mod-4 vector.
    # Expectata: all of G; id and phi (reverse and flip); id alone.
    at(240, 11)
    assert v5.stabilizer(()) == list(v5.GROUP)
    assert v5.stabilizer(TOP4) == [(0, 1), (1, -1)]
    assert v5.stabilizer(TOP4[:3] + ((4, ((14, 30, 46, 30),)),)) == [(0, 1)]


# ---------- residue lattices and admissible count vectors ----------

def q_lattice_basis_spans_generators():
    # Replicata: every modulus in the cascade and v4's cut moduli, at 240 (orders 10 and 11, where 240 < 2^order) and
    # at 304 (order 8, where 304 >= 2^8, and order 9).  Generators: the cyclic shifts of (x-1)^order, times x+1
    # exactly when N < 2^order, reduced mod x^M - 1, built independently with sympy polynomials.
    # Expectata: the generators and lattice_basis's columns span the same lattice (each in the other's
    # span, tested with v2's independently written IntegerSystem).
    import overnight_240_v2 as v2
    for n, target in ((240, 11), (304, 9)):
        at(n, target)
        for order, M in itertools.product((target - 1, target), sorted(set(v5.CASCADE + V4_CUTS))):
            gens = residue_lattice_gens(M, order, n < 2 ** order)
            B = v5.lattice_basis(M, order)
            in_basis = v2.IntegerSystem([list(row) for row in B])
            in_gens = v2.IntegerSystem([[g[r] for g in gens] for r in range(M)])
            assert all(in_basis.solvable(g) for g in gens), (n, order, M)
            assert all(in_gens.solvable([B[r][j] for r in range(M)]) for j in range(len(B[0]))), (n, order, M)


def q_lattice_rule():
    # Replicata: the sequence SIGNS_12_3 of length 12, order 3 and f(-1) = 8, so 12 >= 2^3 and its
    # f(x) = (x-1)^3 h(x) has h(-1) = -1; v5 at N = 12, then at N = 7.
    # Expectata: at N = 12 its residue vectors mod every M up to 16 lie in lattice_basis(M, 3), and for some M
    # they lie outside the lattice of (x-1)^3 (x+1), which v3 would have used; at N = 7 < 2^3, lattice_basis(M, 3)
    # spans the (x-1)^3 (x+1) lattice.
    import overnight_240_v2 as v2
    a = [1 if ch == '+' else -1 for ch in SIGNS_12_3]
    assert v5.exact_order(a) == 3 and sum((-1) ** p * t for p, t in enumerate(a)) == 8
    outside = []
    with length(12):
        for M in range(2, 17):
            d = [sum(a[p] for p in range(r, 12, M)) for r in range(M)]
            assert v5.ExactSystem(v5.lattice_basis(M, 3)).solvable(d), M
            gens = residue_lattice_gens(M, 3, 1)
            outside += [M] * (not v2.IntegerSystem([[g[r] for g in gens] for r in range(M)]).solvable(d))
    assert outside, outside
    with length(7):
        for M in range(2, 17):
            gens = residue_lattice_gens(M, 3, 1)
            B = v5.lattice_basis(M, 3)
            assert all(v5.ExactSystem(B).solvable(g) for g in gens), M
            assert all(v2.IntegerSystem([[g[r] for g in gens] for r in range(M)]).solvable([B[r][j] for r in range(M)])
                       for j in range(len(B[0]))), M


def q_forced_counts():
    # Replicata: order 11, moduli 3 and 5.  Expectata: one admissible vector each, the balanced one.
    at(240, 11)
    assert v5.admissible(11, 3, ()) == ((40, 40, 40),)
    assert v5.admissible(11, 5, ()) == ((24,) * 5,)


def q_admissible_sizes():
    # Regression: the counts found by v2 and by three independent agent recounts.
    at(240, 11)
    assert len(v5.admissible(11, 7, ())) == 4
    assert len(v5.admissible(11, 4, ())) == 9
    assert len(v5.admissible(11, 8, ((4, (30,) * 4),))) == 12769
    assert len(v5.admissible(11, 11, ())) == 12092
    assert len(v5.admissible(11, 13, ())) == 9748
    assert len(v5.admissible(11, 9, ((3, (40, 40, 40)),))) == 4626


def q_admissible_mod11_closed_form():
    # Replicata: order 11, modulus 11, against an independent characterization: (x-1)^11 = x^11 - 1
    # (mod 11) makes every d_r a multiple of 11; also 0 <= c_r <= size and the counts total 120.
    # Expectata: the same set as the enumerator's.
    at(240, 11)
    sizes = [v5.size(11, r) for r in range(11)]
    choices = [[c for c in range(s + 1) if (2 * c - s) % 11 == 0] for s in sizes]
    closed = tuple(sorted(c for c in itertools.product(*choices) if sum(c) == v5.N // 2))
    assert closed == v5.admissible(11, 11, ())


def q_admissible_matches_cpsat():
    # Replicata: several (N, order, modulus, class sums), enumerated by CP-SAT as well, including 304 at order
    # 8, where the lattice has no factor x+1.  Expectata: equal sets.
    at(240, 11)
    for order, M, fixed in ((11, 7, ()), (11, 4, ()), (11, 8, ((4, (30,) * 4),)), (11, 9, ((3, (40, 40, 40)),)),
                            (10, 7, ()), (10, 4, ()), (10, 8, ((4, (30,) * 4),))):
        assert v5.admissible(order, M, fixed) == cpsat_enumerate(order, M, fixed), (order, M, fixed)
    at(304, 9)
    for order, M, fixed in ((9, 3, ()), (9, 5, ()), (9, 4, ()), (9, 7, ()), (8, 3, ()), (8, 5, ()), (8, 4, ()),
                            (8, 7, ())):
        assert v5.admissible(order, M, fixed) == cpsat_enumerate(order, M, fixed), (order, M, fixed)


def q_published_counts_admissible_order10():
    # Replicata: the published order-10 example.  Expectata: its counts are admissible at order 10 for
    # every cascade modulus, given its own counts modulo the earlier divisors.
    at(240, 11)
    for i, M in enumerate(v5.CASCADE):
        fixed = tuple((P, v5.counts(EXAMPLE, P)) for P in v5.CASCADE[:i] if M % P == 0)
        assert v5.counts(EXAMPLE, M) in v5.admissible(10, M, fixed), M


# ---------- the exact integer filter ----------

def q_exact_system_matches_v2():
    # Replicata: v2's two systems ((c4, c7) and (c7, c8)) and their count vectors.
    # Expectata: v5's ExactSystem, and its fiber shortcut, agree with v2's IntegerSystem on every vector,
    # with both answers occurring.
    import overnight_240_v2 as v2
    at(240, 11)
    rows, rhs = v5.moment_rows(11)
    A = rows + v5.count_rows(4) + v5.count_rows(7)
    old, new = v2.IntegerSystem(A), v5.ExactSystem(A)
    for c4 in v5.admissible(11, 4, ()):
        for c7 in v5.admissible(11, 7, ()):
            b = list(rhs) + list(c4) + list(c7)
            assert old.solvable(b) == new.solvable(b), (c4, c7)
    A = rows + v5.count_rows(7) + v5.count_rows(8)
    old, new = v2.IntegerSystem(A), v5.ExactSystem(A)
    head = list(rhs) + [21, 14, 31, 24, 17, 10, 3]
    ok = new.fiber(head)
    verdicts = []
    for c8 in v5.admissible(11, 8, ((4, (30,) * 4),))[::7]:
        verdicts.append(old.solvable(head + list(c8)))
        assert verdicts[-1] == new.solvable(head + list(c8)) == ok(c8), c8
    assert True in verdicts and False in verdicts


def q_fiber_rejects_wrong_length():
    # Replicata: the order-11 system with counts mod 3; vectors of length 4 and 2 instead of 3.
    # Expectata: ValueError from zip's strict check, not a silent answer.
    at(240, 11)
    ok = v5.integer_system(11, (3,)).fiber(v5.moment_rows(11)[1])
    assert ok((40, 40, 40))
    for bad in ((40, 40, 40, 99), (40, 40)):
        try:
            ok(bad)
        except ValueError:
            continue
        # TODO: error copy; says a vector of the wrong length was accepted by the integer filter
        raise AssertionError(f'Claude: "a vector of the wrong length was accepted: {bad}"')


def q_v2_case_numbers():
    # Regression: v2's exact filters recomputed with v5's machinery: 2 of the 18 (c4, c7) pairs survive;
    # 1024 of the 12769 mod-8 refinements survive for v2's open case.
    at(240, 11)
    rows, rhs = v5.moment_rows(11)
    S1 = v5.ExactSystem(rows + v5.count_rows(4) + v5.count_rows(7))
    c7s = [c for c in v5.admissible(11, 7, ()) if 2 * c[0] - v5.size(7, 0) >= 0]
    live = [(c4, c7) for c7 in c7s for c4 in v5.admissible(11, 4, ()) if S1.solvable(list(rhs) + list(c4) + list(c7))]
    assert len(c7s) * 9 == 18 and len(live) == 2 and all(c4 == (30,) * 4 for c4, _ in live)
    S2 = v5.ExactSystem(rows + v5.count_rows(7) + v5.count_rows(8))
    keep = [c8 for c8 in v5.admissible(11, 8, ((4, (30,) * 4),)) if S2.solvable(list(rhs) + [21, 14, 31, 24, 17, 10, 3] + list(c8))]
    assert len(keep) == 1024


# ---------- splitting ----------

def q_split_top_levels():
    # Replicata: the first four splits at order 11.
    # Expectata: mod 3 and mod 5 leave only the balanced vector (plus an empty pool); mod 7 leaves the two
    # orbit representatives; mod 4 leaves only (30, 30, 30, 30).
    at(240, 11)
    kids = v5.split(11, ())
    assert kids == [((3, ((40, 40, 40),)),), ((3, ()),)]
    kids = v5.split(11, kids[0])
    assert kids == [TOP4[:1] + ((5, ((24,) * 5,)),), TOP4[:1] + ((5, ()),)]
    kids = v5.split(11, kids[0])
    assert sorted(members(kids)) == [(0, 0, 24, 24, 24, 24, 24), C_STAR]
    kids = v5.split(11, TOP4[:3])
    assert members(kids) == [(30,) * 4]


def q_split_c8_level():
    # Replicata: the mod-8 split of the open node.
    # Expectata: 528 distinct vectors in all, each the representative under {id, phi} of one of the 1024
    # survivors of the exact filter; children of their own exactly for the LP-feasible ones, then one pool
    # of LP-infeasible ones.
    at(240, 11)
    kids = v5.split(11, TOP4)
    got = members(kids)
    assert len(got) == len(set(got)) == 528
    assert all(len(k[-1][1]) == 1 for k in kids[:-1])
    rows, rhs = v5.moment_rows(11)
    S = v5.ExactSystem(rows + sum((v5.count_rows(M) for M in (3, 5, 7, 4, 8)), ()))
    head = list(rhs) + [t for _, V in TOP4 for t in V[0]]
    full = [c8 for c8 in v5.admissible(11, 8, ((4, (30,) * 4),)) if S.solvable(head + list(c8))]
    assert len(full) == 1024
    gs = v5.stabilizer(TOP4)
    assert {v5.rep(gs, 8, c8) for c8 in full} == set(got)
    lp = v5.Relaxation(11, TOP4, 8)
    singles = [k[-1][1][0] for k in kids[:-1]]
    assert all(lp.check(v) for v in singles) and not any(lp.check(v) for v in kids[-1][-1][1])


def q_box_prefilter_keeps_feasible():
    # Replicata: 256 sampled mod-8 vectors of the open node.  Expectata: the box prefilter drops none of
    # the LP-feasible ones.
    at(240, 11)
    lp = v5.Relaxation(11, TOP4, 8)
    vecs = list(v5.admissible(11, 8, ((4, (30,) * 4),)))[::50]
    assert lp.feasible_set(vecs) == [v for v in vecs if lp.check(v)]


def q_feasible_set_early_return():
    # Replicata: a node whose own relaxation is infeasible: the open node plus one member of its mod-8 pool.
    # Expectata: feasible_set returns [] for all 12092 admissible mod-11 vectors.
    at(240, 11)
    v = v5.split(11, TOP4)[-1][-1][1][0]
    node = TOP4 + ((8, (v,)),)
    assert v5.Relaxation(11, node, 11).feasible_set(list(v5.admissible(11, 11, ()))) == []


class FakeGlop:
    """GLOP, except that Solve returns ABNORMAL whenever abnormal(i, status) holds for the i-th solve (from 0)
    and the status GLOP itself returned; after such a solve, Objective().Value() is NaN."""
    def __init__(self, abnormal):
        self.real, self.abnormal, self.calls, self.faked = pywraplp.Solver.CreateSolver('GLOP'), abnormal, 0, 0
        self.last = False                            # whether the latest solve's status was faked
    def __getattr__(self, name): return getattr(self.real, name)
    def Solve(self):
        st = self.real.Solve()
        i, self.calls = self.calls, self.calls + 1
        self.last = bool(self.abnormal(i, st))
        self.faked += self.last
        return pywraplp.Solver.ABNORMAL if self.last else st
    def Objective(self): return FakeObjective(self)


class FakeObjective:
    """A FakeGlop's objective: GLOP's own, except that Value() is NaN after a faked status."""
    def __init__(self, glop): self.glop = glop
    def __getattr__(self, name): return getattr(self.glop.real.Objective(), name)
    def Value(self): return float('nan') if self.glop.last else self.glop.real.Objective().Value()


def fake_pywraplp(abnormal, made):
    """A stand-in for the pywraplp module whose GLOP solvers are FakeGlops (each appended to made)."""
    def create(name):
        assert name == 'GLOP'
        made.append(FakeGlop(abnormal))
        return made[-1]
    solver = types.SimpleNamespace(CreateSolver=create, OPTIMAL=pywraplp.Solver.OPTIMAL,
                                   INFEASIBLE=pywraplp.Solver.INFEASIBLE, ABNORMAL=pywraplp.Solver.ABNORMAL)
    return types.SimpleNamespace(Solver=solver)


def q_fake_glop():
    # Replicata: a FakeGlop that fakes its second solve, minimizing x over 1 <= x <= 2, solved three times.
    # Expectata: OPTIMAL with objective value 1, then ABNORMAL with NaN, then OPTIMAL with 1 again.
    s = FakeGlop(lambda i, st: i == 1)
    x = s.NumVar(1, 2, 'x')
    s.Objective().SetCoefficient(x, 1)
    s.Objective().SetMinimization()
    got = [(s.Solve(), s.Objective().Value()) for _ in range(3)]
    assert got[0] == got[2] == (pywraplp.Solver.OPTIMAL, 1.0) and got[1][0] == pywraplp.Solver.ABNORMAL, got
    assert math.isnan(got[1][1]) and s.faked == 1, got


def q_lp_status_policy():
    # Replicata: the mod-8 split of the open node at 240@11 (528 vectors), with GLOP replaced by a fake that
    # returns ABNORMAL for (a) every solve, (b) the 16 bound solves, (c) every check GLOP itself found
    # INFEASIBLE, (d) the node's own solve; and v3's split under fake (a).
    # Expectata: a vector goes into the pool only if the LP claimed it infeasible, by an INFEASIBLE status or by
    # lying outside the box of bounds that OPTIMAL bound solves set; any other status makes no claim, and the
    # vector gets its own child.  So (a) every vector has its own child and the pool is empty; (b) and (d)
    # give the real split; (c) gives own children exactly to the vectors inside the real box; every fake
    # actually returned ABNORMAL; and v3's split fails its status assertion in Relaxation.solve.
    at(240, 11)
    node, M = TOP4, 8
    real = v5.split(11, node)
    singles, pool = [k[-1][1][0] for k in real[:-1]], real[-1][-1][1]
    vecs = sorted(singles + list(pool))
    assert singles and pool
    lp = v5.Relaxation(11, node, M)
    assert lp.solve({}) == pywraplp.Solver.OPTIMAL
    lo = [lp.bound(r, 1) for r in range(M)]
    hi = [lp.bound(r, -1) for r in range(M)]
    inside = [v for v in vecs if all(lo[r] - v5.TOL <= v[r] <= hi[r] + v5.TOL for r in range(M))]
    assert len(singles) < len(inside) < len(vecs)
    def run(abnormal):
        made = []
        with patched(v5, pywraplp=fake_pywraplp(abnormal, made)):
            kids = v5.split(11, node)
        assert sum(s.faked for s in made) > 0
        return [k[-1][1][0] for k in kids[:-1]], kids[-1][-1][1]
    own, rest = run(lambda i, st: True)
    assert sorted(own) == vecs and rest == ()
    assert run(lambda i, st: 1 <= i <= 2 * M) == (singles, pool)
    own, rest = run(lambda i, st: i > 2 * M and st == pywraplp.Solver.INFEASIBLE)
    assert own == [v for v in inside if v in own] and sorted(own) == sorted(inside)
    assert set(rest) == set(vecs) - set(inside)
    assert run(lambda i, st: i == 0) == (singles, pool)
    with patched(v3, pywraplp=fake_pywraplp(lambda i, st: True, [])):
        expect_assertion(lambda: v3.split(11, node), 'solve')


def q_pool_splits_into_members():
    # Replicata: a pool of three mod-8 vectors.  Expectata: three children, one per member, in order.
    at(240, 11)
    a, b, c = (1, 1, 5, 5, 29, 29, 25, 25), (1, 1, 5, 13, 29, 29, 25, 17), (1, 1, 5, 21, 29, 29, 25, 9)
    assert v5.split(11, TOP4 + ((8, (a, b, c)),)) == [TOP4 + ((8, (v,)),) for v in (a, b, c)]


def q_split_bottom():
    # Replicata: (a) a node with one vector per cascade modulus; (b) with the cascade cut to (3,), a pool
    # at the bottom.  Expectata: (a) no children; (b) still one child per member.
    at(240, 11)
    assert v5.split(10, example_node(v5.CASCADE)) == []
    pool = ((3, ((39, 41, 40), (40, 40, 40))),)
    with patched(v5, CASCADE=(3,)):
        assert v5.split(11, pool) == [((3, ((39, 41, 40),)),), ((3, ((40, 40, 40),)),)]


# ---------- the node solver: solve_node (certbb in place of v4's CP-SAT models) ----------

def q_empty_pool_is_infeasible():
    # Replicata: the open node plus an empty mod-8 pool.  (v4: its CP-SAT model was INFEASIBLE.)
    # Expectata: INFEASIBLE with no LP solve and no leaf, on the empty proof (its sha1 that of no bytes).
    at(240, 11)
    verdict, a, found = v5.solve_node(11, TOP4 + ((8, ()),), 20)
    assert (verdict, a, found) == ('INFEASIBLE', None, {'lps': 0, 'leaves': 0, 'proof': hashlib.sha1(b'').hexdigest()})


def q_pool_solve_admits_every_member():
    # Replicata: order 10; the published example's own counts for 3, 5, 7, 4, 8, 11 and 13, then a mod-9 pool whose
    # second member is the example's counts; the box pinned to the example.  (v4: CP-SAT's model of the pool, with x
    # pinned to the example, was OPTIMAL.)
    # Expectata: FEASIBLE with the example; with the first member alone, INFEASIBLE, so a solve admitting only a pool's
    # first member would have said INFEASIBLE.
    at(240, 11)
    true9 = v5.counts(EXAMPLE, 9)
    other = v5.admissible(10, 9, ((3, v5.counts(EXAMPLE, 3)),))[0]
    assert other < true9
    base = example_node((3, 5, 7, 4, 8, 11, 13))
    x = x01(EXAMPLE)
    assert v5.solve_node(10, base + ((9, (other, true9)),), 2, x, x)[:2] == ('FEASIBLE', EXAMPLE)
    assert v5.solve_node(10, base + ((9, (other,)),), 1, x, x)[0] == 'INFEASIBLE'


def q_solve_node_accepts_example_at_order10_and_rejects_it_at_order11():
    # Replicata: the box pinned to the published example.  (v4: CP-SAT's models with x pinned to it.)
    # Expectata: its full count node at order 10 is FEASIBLE with the example; the top node at order 11 is INFEASIBLE
    # with one leaf.
    at(240, 11)
    x = x01(EXAMPLE)
    assert v5.solve_node(10, example_node(v5.CASCADE), 1, x, x)[:2] == ('FEASIBLE', EXAMPLE)
    verdict, _, found = v5.solve_node(11, (), 1, x, x)
    assert verdict == 'INFEASIBLE' and found['leaves'] == 1, (verdict, found)


def q_solve_node_verdicts():
    # Replicata: (a) the top node at order 11 with a budget of 1 LP solve; (b) an empty pool; (c) the top node at order
    # 10 with the box pinned to the published example.
    # Expectata: (a) UNKNOWN after 1 LP solve, no box closed; (b) INFEASIBLE; (c) FEASIBLE with the example as its
    # sequence.
    at(240, 11)
    verdict, a, found = v5.solve_node(11, (), 1)
    assert (verdict, a, found['lps'], found['leaves']) == ('UNKNOWN', None, 1, 0), (verdict, found)
    assert v5.solve_node(11, TOP4 + ((8, ()),), 20)[0] == 'INFEASIBLE'
    x = x01(EXAMPLE)
    assert v5.solve_node(10, (), 1, x, x)[:2] == ('FEASIBLE', EXAMPLE)


def q_budget():
    # Replicata: the top node, a node at the bottom of the cascade, a pool of 12000 members.
    # Expectata: BUDGET by depth, with the bottom entry for the bottom, and POOL_BUDGET per pool member.
    at(240, 11)
    assert len(v5.BUDGET) == len(v5.CASCADE) + 1
    assert v5.node_budget(()) == v5.BUDGET[0]
    assert v5.node_budget(example_node(v5.CASCADE)) == v5.BUDGET[-1]
    pool = TOP4 + ((8, tuple((i,) * 8 for i in range(12000))),)
    assert v5.node_budget(pool) == max(v5.BUDGET[5], 12000 * v5.POOL_BUDGET)


def q_control():
    # Replicata: the startup control at 240@11.  Expectata: it returns.
    at(240, 11)
    v5.control()


def q_control_304_9():
    # Replicata: the startup control at 304@9, whose walk runs at order 8 with 304 >= 2^8.  Expectata: it returns.
    at(304, 9)
    v5.control()


def q_control_checks_example_lattices():
    # Replicata: the startup control at 40@6, with lattice_poly given one more factor x-1 at ORDER only (at
    # ORDER - 1, where the control walks its example down the cascade, it is the real one), and no results cached
    # from before or after.
    # Expectata: AssertionError at the control's check that the residue vectors of the examples of order ORDER lie
    # in the lattices (mod 7, none of the three does).  Without that check the control would pass: its walk uses
    # the real lattices, and the finer one at ORDER only makes the final solve stricter.
    at(40, 6)
    real = v5.lattice_poly
    def finer(order):                                # lattice_poly(order), times x - 1 at ORDER
        poly = real(order)
        return [a - b for a, b in zip([0] + poly, poly + [0])] if order == v5.ORDER else poly
    with patched(v5, lattice_poly=finer), uncached():
        frame = expect_assertion(v5.control, 'control')
    assert 'for b in bs' in frame.line, frame.line


def q_control_checks_certbb_rows():
    # Replicata: the startup control at 40@6, with certbb's rows broken in two ways: (a) certbb.node_rows giving each
    # count row the count of the next class (v[(r + 1) % M] for v[r]); (b) v5.moments handing certbb the moment rows of
    # the order below, so that the rows of an order are those of the order below.
    # Expectata: AssertionError in control, (a) at the walk's check that solve_node finds the example FEASIBLE, (b) at
    # the final check that order ORDER rejects it; with the real rows the control returns.
    at(40, 6)
    real = certbb.node_rows
    def rotated(moments, choice): return real(moments, [(M, tuple(v[(r + 1) % M] for r in range(M))) for M, v in choice])
    def short(order): return certbb.Moments(*v5.moment_rows(order - 1))
    with patched(certbb, node_rows=rotated):
        frame = expect_assertion(v5.control, 'control')
    assert "('FEASIBLE', a)" in frame.line, frame.line
    with patched(v5, moments=short):
        frame = expect_assertion(v5.control, 'control')
    assert "solve_node(ORDER, node, 1, x, x)[0] == 'INFEASIBLE'" in frame.line, frame.line
    v5.control()


# ---------- journal and keys ----------

def q_node_keys():
    # Replicata: the open node, two pools differing in one member, the top node.
    # Expectata: readable single-vector keys; pools keyed by size and full hash, distinct; '' for the top.
    at(240, 11)
    k1 = v5.node_key(TOP4)
    assert k1 == '3:[40,40,40] 5:[24,24,24,24,24] 7:[14,21,3,10,17,24,31] 4:[30,30,30,30]'
    k2 = v5.node_key(TOP4 + ((8, ((1,) * 8, (2,) * 8)),))
    k3 = v5.node_key(TOP4 + ((8, ((1,) * 8, (3,) * 8)),))
    assert k2.startswith(k1 + ' 8:#2:') and len(k2.split(':')[-1]) == 40 and k2 != k3
    assert v5.node_key(()) == ''


def journal_with(lines):
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'j.jsonl')
    with open(path, 'w') as fh:
        fh.write('\n'.join(json.dumps(x) for x in [v5.header()] + lines) + '\n')
    return path


def q_journal_header():
    # Replicata: (a) a journal written at order 11, reopened while the module's order is 10; (b) a journal
    # whose header carries another code fingerprint; (c) the header itself at 240@11 and at 304@9; (d) a 240@11
    # journal reopened at 304@9; (e) overnight_v4's header and overnight_240_v3.py's.
    # Expectata: (a), (b), (d), (e) AssertionError from Journal's header check; (c) it pins the tag, N, the order, a
    # 40-digit fingerprint, the solver (certbb), the budget unit (LP solves) and the HiGHS build (its version, as HiGHS
    # reports it, then its git hash), and has no cuts.
    at(240, 11)
    path = journal_with([])
    with patched(v5, ORDER=10):
        expect_assertion(lambda: v5.Journal(path), '__init__')
    d = tempfile.mkdtemp()
    other = os.path.join(d, 'j.jsonl')
    open(other, 'w').write(json.dumps(dict(v5.header(), code='0' * 40)) + '\n')
    expect_assertion(lambda: v5.Journal(other), '__init__')
    h = v5.header()
    H = certbb.highs._Highs()
    assert set(h) == {'tag', 'N', 'order', 'code', 'solver', 'budget_unit', 'highs'}, h
    assert (h['tag'], h['N'], h['order'], len(h['code'])) == ('overnight_v5', 240, 11, 40)
    assert (h['solver'], h['budget_unit'], h['highs']) == ('certbb', 'LP solves', f'{H.version()} ({H.githash()})'), h
    at4(240, 11)
    for old_header in (v3.header(), v4.header()):
        old = os.path.join(tempfile.mkdtemp(), 'j.jsonl')
        open(old, 'w').write(json.dumps(old_header) + '\n')
        expect_assertion(lambda: v5.Journal(old), '__init__')
    at(304, 9)
    h = v5.header()
    assert (h['tag'], h['N'], h['order']) == ('overnight_v5', 304, 9)
    expect_assertion(lambda: v5.Journal(path), '__init__')


def q_journal_rejects_unknown_verdict_words():
    # Replicata: journals holding the verdict words OPTIMAL, FEASIBLE and a misspelling.
    # Expectata: AssertionError at load, so no such record can make a node vanish from the search.
    at(240, 11)
    for word in ('OPTIMAL', 'FEASIBLE', 'INFEASABLE'):
        path = journal_with([{'key': '', 'verdict': word, 'budget': 20}])
        expect_assertion(lambda: v5.Journal(path), 'admit')


def q_journal_supersession():
    # Replicata: two records for one key.
    # Expectata: after an UNKNOWN, a re-solve with a larger budget or a CLOSED is accepted (the later record
    # wins); a record after an INFEASIBLE or a CLOSED, or an UNKNOWN re-solve without a larger budget, is not.
    at(240, 11)
    for first, second in ((('UNKNOWN', 20), ('INFEASIBLE', 60)), (('UNKNOWN', 20), ('CLOSED', 20))):
        j = v5.Journal(journal_with([{'key': 'k', 'verdict': first[0], 'budget': first[1]},
                                     {'key': 'k', 'verdict': second[0], 'budget': second[1]}]))
        assert j.records['k']['verdict'] == second[0]
    for first, second in ((('INFEASIBLE', 20), ('UNKNOWN', 60)), (('CLOSED', 20), ('UNKNOWN', 60)),
                          (('UNKNOWN', 20), ('UNKNOWN', 20)), (('INFEASIBLE', 20), ('CLOSED', 20))):
        path = journal_with([{'key': 'k', 'verdict': first[0], 'budget': first[1]},
                             {'key': 'k', 'verdict': second[0], 'budget': second[1]}])
        expect_assertion(lambda: v5.Journal(path), 'admit')


def q_journal_reuse_rule():
    # Replicata: an UNKNOWN reached with budget 10, an INFEASIBLE with 5, a CLOSED.
    # Expectata: under a budget of 20 only INFEASIBLE and CLOSED are reused; under 10 all three are.
    at(240, 11)
    j = v5.Journal(journal_with([{'key': 'u', 'verdict': 'UNKNOWN', 'budget': 10},
                                 {'key': 'i', 'verdict': 'INFEASIBLE', 'budget': 5},
                                 {'key': 'c', 'verdict': 'CLOSED', 'budget': 1}]))
    assert (j.reuse('u', 20), j.reuse('i', 20), j.reuse('c', 20), j.reuse('new', 20)) == (None, 'INFEASIBLE', 'CLOSED', None)
    assert (j.reuse('u', 10), j.reuse('i', 10), j.reuse('c', 10)) == ('UNKNOWN', 'INFEASIBLE', 'CLOSED')


def q_journal_put_records_the_solve():
    # Replicata: put a solve's verdict with its lps, leaves and proof, then a CLOSED with no solve fields; reopen.
    # Expectata: the file's records are exactly {key, verdict, budget, lps, leaves, proof} and {key, verdict, budget},
    # and the reopened journal holds the later one.
    at(240, 11)
    path = journal_with([])
    j = v5.Journal(path)
    found = {'lps': 17, 'leaves': 9, 'proof': hashlib.sha1(b'x').hexdigest()}
    j.put('k', 'UNKNOWN', 20, found)
    j.put('k', 'CLOSED', 20, {})
    recs = [json.loads(line) for line in open(path).read().splitlines()[1:]]
    assert recs == [{'key': 'k', 'verdict': 'UNKNOWN', 'budget': 20} | found, {'key': 'k', 'verdict': 'CLOSED', 'budget': 20}], recs
    assert v5.Journal(path).records['k']['verdict'] == 'CLOSED'


# ---------- the search, with a fake worker ----------

FOUND = {'lps': 1, 'leaves': 0, 'proof': hashlib.sha1(b'').hexdigest()}      # a fake solve's journal fields


class SyncExecutor:
    """An executor that runs each task at once, in this process."""
    def submit(self, fn, *args):
        f = Future()
        f.set_result(fn(*args))
        return f


def fake_world(verdicts, splits):
    """A fake work(): verdicts[node] when solving, splits[node] (else the real split) for UNKNOWN's children.
    Returns the list of nodes it solved, and the patch."""
    calls, real = [], v5.split
    def work(order, node, budget, known, source):
        if known is None: calls.append(node)
        verdict = known or verdicts[node]
        children = (splits[node] if node in splits else real(order, node)) if verdict == 'UNKNOWN' else []
        return verdict, None, children, 0.0, 0.0, 0, None if known else FOUND
    return calls, dict(work=work)


def search(path, order=11):
    return v5.search(order, v5.Journal(path), lambda s: None, SyncExecutor())


def q_search_closes_tree_and_journals_it():
    # Replicata: the top node is UNKNOWN and splits into two INFEASIBLE children; then the same search again.
    # Expectata: 2 closed, nothing open, no witness, each node solved once (depth-first: the last child
    # first), the top journaled CLOSED, each solve's record carrying its journal fields; the second search solves and
    # splits nothing, settling the top from the journal (1 closed).
    at(240, 11)
    a, b = ((3, ((1,),)),), ((3, ((2,),)),)
    calls, fake = fake_world({(): 'UNKNOWN', a: 'INFEASIBLE', b: 'INFEASIBLE'}, {(): [a, b]})
    path = journal_with([])
    with patched(v5, CASCADE=(3, 5), BUDGET=(20, 20, 60), **fake):
        assert search(path) == {'closed': 2, 'open': [], 'witness': None, 'exact_order': None}
        assert calls == [(), b, a] and v5.Journal(path).records['']['verdict'] == 'CLOSED'
        recs = [json.loads(line) for line in open(path).read().splitlines()[1:]]
        assert [r['verdict'] for r in recs] == ['UNKNOWN', 'INFEASIBLE', 'INFEASIBLE', 'CLOSED']
        assert all(r == {'key': r['key'], 'verdict': r['verdict'], 'budget': r['budget']} | FOUND for r in recs[:3])
        calls.clear()
        assert search(path) == {'closed': 1, 'open': [], 'witness': None, 'exact_order': None} and calls == []


def q_search_reports_open_leaves_and_reuses_journal():
    # Replicata: cascade (3, 5); an UNKNOWN chain down to the bottom, with one INFEASIBLE sibling; then the
    # same search again on the same journal.
    # Expectata: the bottom node is the one open leaf, nothing is journaled CLOSED; the second search solves
    # nothing and reports the same.
    at(240, 11)
    a = ((3, ((1,),)),)
    aa, ab = a + ((5, ((7,),)),), a + ((5, ((8,),)),)
    calls, fake = fake_world({(): 'UNKNOWN', a: 'UNKNOWN', aa: 'UNKNOWN', ab: 'INFEASIBLE'}, {(): [a], a: [aa, ab], aa: []})
    path = journal_with([])
    with patched(v5, CASCADE=(3, 5), BUDGET=(20, 20, 60), **fake):
        res = search(path)
        assert res == {'closed': 1, 'open': [aa], 'witness': None, 'exact_order': None}
        assert 'CLOSED' not in [r['verdict'] for r in v5.Journal(path).records.values()]
        calls.clear()
        assert search(path) == res and calls == []


def q_search_splits_pool_at_bottom():
    # Replicata: cascade (3,); the top node is UNKNOWN and (fake) splits into a two-member pool that is
    # UNKNOWN; the real split then gives its members, both INFEASIBLE.
    # Expectata: 2 closed, nothing open: a pool at the bottom is not an open leaf.
    at(240, 11)
    va, vb = (39, 41, 40), (40, 40, 40)
    pool = ((3, (va, vb)),)
    calls, fake = fake_world({(): 'UNKNOWN', pool: 'UNKNOWN', ((3, (va,)),): 'INFEASIBLE', ((3, (vb,)),): 'INFEASIBLE'},
                             {(): [pool]})
    with patched(v5, CASCADE=(3,), BUDGET=(20, 60), **fake):
        assert search(journal_with([])) == {'closed': 2, 'open': [], 'witness': None, 'exact_order': None}


def q_search_witness_is_checked_exactly():
    # Replicata: a fake worker whose first verdict is FEASIBLE with the published order-10 example.
    # Expectata: at order 10 the search logs it at once and returns it as a witness of exact order 10,
    # journaling nothing; at order 11 the exact check in search() fails.
    at(240, 11)
    fake = dict(work=lambda order, node, budget, known, source: ('FEASIBLE', EXAMPLE, [], 0.0, 0.0, 0, FOUND))
    path = journal_with([])
    lines = []
    with patched(v5, **fake):
        res = v5.search(10, v5.Journal(path), lines.append, SyncExecutor())
        assert res['witness'] == EXAMPLE and res['exact_order'] == 10
        assert len(lines) == 1 and lines[0].startswith('Claude: "WITNESS FOUND') and 'exact order 10' in lines[0]
        assert len(open(path).read().splitlines()) == 1
        expect_assertion(lambda: search(journal_with([]), order=11), 'search')


def q_work_requires_the_same_source():
    # Replicata: SOURCE; work() told that the main process ran a different overnight_v5.py, a different certbb.py,
    # or neither in the form of SOURCE.
    # Expectata: SOURCE is the sha1 of the bytes of overnight_v5.py and of certbb.py; each call fails with
    # AssertionError in work.
    at(240, 11)
    assert v5.SOURCE == tuple(hashlib.sha1(open(os.path.join(HERE, f), 'rb').read()).hexdigest()
                              for f in ('overnight_v5.py', 'certbb.py'))
    for source in ('another file', (v5.SOURCE[0], '0' * 40), ('0' * 40, v5.SOURCE[1])):
        expect_assertion(lambda: v5.work(11, (), 1, 'UNKNOWN', source), 'work')


def q_code_and_source_cover_certbb():
    # Replicata: fresh processes importing overnight_v5 from copies of overnight_v5.py and certbb.py in a scratch
    # directory, first unchanged, then with one comment line added to the copy of certbb.py.
    # Expectata: unchanged, CODE and SOURCE equal this process's; with the comment, CODE and SOURCE's certbb.py
    # entry differ while SOURCE's overnight_v5.py entry is the same, so a change to certbb.py alone gives a fresh
    # journal header and is caught by every worker.
    d = tempfile.mkdtemp()
    for f in ('overnight_v5.py', 'certbb.py'):
        open(os.path.join(d, f), 'w').write(open(os.path.join(HERE, f)).read())
    probe = (f"import sys, json; sys.dont_write_bytecode = True; sys.path.insert(0, {d!r})\n"
             f"import overnight_v5 as v5\n"
             f"assert v5.__file__.startswith({d!r}) and v5.certbb.__file__.startswith({d!r})\n"
             f"print(json.dumps([v5.CODE, list(v5.SOURCE)]))\n")
    def ask():
        p = run_child(probe)
        assert p.returncode == 0, p.stderr[-2000:]
        code, source = json.loads(p.stdout)
        return code, tuple(source)
    assert ask() == (v5.CODE, v5.SOURCE)
    open(os.path.join(d, 'certbb.py'), 'a').write('# one more line\n')
    code, source = ask()
    assert code != v5.CODE and source[0] == v5.SOURCE[0] and source[1] != v5.SOURCE[1]


def q_lp_failures_reach_the_progress_line():
    # Replicata: at 240@11, work() on the open node with a known UNKNOWN, so that it only splits the node (by mod
    # 8), with GLOP faked to return ABNORMAL for every third LP solve, then with the real GLOP; then search() with
    # a fake worker whose split of the top node had 4321 LP failures.
    # Expectata: work() reports as many LP failures as the fake returned ABNORMAL statuses (some), and none with
    # the real GLOP; the top node's progress line shows 4321, and its two INFEASIBLE children's lines do not.
    at(240, 11)
    made = []
    with patched(v5, pywraplp=fake_pywraplp(lambda i, st: i % 3 == 0, made)):
        res = v5.work(11, TOP4, 1, 'UNKNOWN', v5.SOURCE)
    assert len(res) == 7, len(res)
    assert res[5] == sum(s.faked for s in made) > 0, (res[5], [s.faked for s in made])
    assert v5.work(11, TOP4, 1, 'UNKNOWN', v5.SOURCE)[5] == 0
    a, b = ((3, ((1,),)),), ((3, ((2,),)),)
    def work(order, node, budget, known, source):
        return ('UNKNOWN', None, [a, b], 0.0, 0.0, 4321, FOUND) if node == () else ('INFEASIBLE', None, [], 0.0, 0.0, 0, FOUND)
    lines = []
    with patched(v5, work=work):
        v5.search(11, v5.Journal(journal_with([])), lines.append, SyncExecutor())
    assert len(lines) == 3 and '4321' in lines[0] and not any('4321' in t for t in lines[1:]), lines


def q_workers_are_configured():
    # Replicata: at 48@6, the real process pool that run() uses, with one process; work() on the top node with
    # a known UNKNOWN.
    # Expectata: the worker process splits the top node exactly as this process does (a worker left
    # unconfigured has N = None and fails).
    at(48, 6)
    with patched(v5, PROCESSES=1):
        with v5.make_executor() as ex:
            res = ex.submit(v5.work, 6, (), 1, 'UNKNOWN', v5.SOURCE).result()
    assert res[0] == 'UNKNOWN' and res[2] == v5.split(6, ())


def q_run_outcomes():
    # Replicata: run() with the control, journal, executor and search faked, for each kind of result.
    # Expectata: the closure line appears exactly when nothing is open and there is no witness, and it names exact
    # integer arithmetic, not CP-SAT, as what the result rests on.
    at(240, 11)
    shapes = {'closed': {'closed': 5, 'open': [], 'witness': None, 'exact_order': None},
              'open': {'closed': 4, 'open': [((3, ((1,),)),)], 'witness': None, 'exact_order': None},
              'witness': {'closed': 0, 'open': [], 'witness': EXAMPLE, 'exact_order': 12}}
    class FakeJournal:
        records = {}
        def __init__(self, path): pass
    class FakeExecutor:
        def __enter__(self): return self
        def __exit__(self, *exc): pass
    for kind, res in shapes.items():
        lines = []
        with patched(v5, control=lambda: None, Journal=FakeJournal, make_executor=FakeExecutor,
                     search=lambda order, journal, log, executor: res, log_to_file=lines.append):
            v5.run()
        text = '\n'.join(lines)
        assert ('ALL NODES CLOSED' in text) == (kind == 'closed'), (kind, text)
        assert ('NOT FINISHED' in text) == (kind == 'open'), (kind, text)
        assert ('WITNESS FOUND' in text) == (kind == 'witness'), (kind, text)
        assert ('exact integer arithmetic' in text) == (kind == 'closed') and 'CP-SAT' not in text, (kind, text)


def q_sigint_stops_at_once_and_records_nothing():
    # Replicata: a child process runs the real search at 240@11 with one worker process and a budget of 10^6 LP solves
    # per node (many minutes for the top node); once the search has started, SIGINT goes to the whole process group 5 s
    # later, as Ctrl-C in a terminal does.  (v4's CP-SAT solve could not be interrupted and ran its full budget;
    # certbb's search is Python, which a signal interrupts between two LP solves.)
    # Expectata: KeyboardInterrupt ends the run within 60 s of the signal, and the journal holds only its header line.
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'j.jsonl')
    code = (f"import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {HERE!r})\n"
            f"import overnight_v5 as v5\n"
            f"if __name__ == '__main__':\n"
            f"    v5.configure(240, 11)\n"
            f"    v5.BUDGET = (10 ** 6,) * len(v5.BUDGET); v5.PROCESSES = 1\n"
            f"    journal = v5.Journal({path!r})\n"
            f"    with v5.make_executor() as ex:\n"
            f"        print('SEARCHING', flush=True)\n"
            f"        v5.search(11, journal, print, ex)\n")
    script = os.path.join(d, 'child.py')
    open(script, 'w').write(code)
    p = subprocess.Popen([sys.executable, script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True)
    assert p.stdout.readline().strip() == 'SEARCHING'
    time.sleep(5)
    t0 = time.time()
    os.killpg(p.pid, 2)
    out, err = p.communicate(timeout=600)
    assert p.returncode != 0 and 'KeyboardInterrupt' in err, (p.returncode, err[-800:])
    assert time.time() - t0 < 60, time.time() - t0
    assert len(open(path).read().splitlines()) == 1


# ---------- completeness: every solution of a small configuration ----------

def q_every_solution_reaches_an_accepting_leaf_40_4():
    # Replicata: v5 at 40@4 (40 >= 2^4, so its lattices lack the factor x+1), with a SETTINGS entry that exists
    # only for this qual: cascade (3, 5, 4, 7, 8).  All 4414 sequences of length 40 and order at least 4, from
    # power_sum_solutions.  Each walks v5's real tree from the top node: at a node, for each g in its stabilizer, g of
    # the sequence goes to the child of the node's split holding its counts, if any (a pool child splits into its
    # members in turn), down to a node without children, a leaf.
    # Expectata: every solution reaches a leaf where solve_node, with the box pinned to the image of the solution there,
    # says FEASIBLE with that image.  So no split, filter, symmetry reduction or certbb row loses a solution of 40@4.
    # (All 4414 have f(-1) = 0, so this qual cannot tell whether the lattices drop x+1; q_lattice_rule does.)
    with patched(v5, SETTINGS=v5.SETTINGS | {(40, 4): ((3, 5, 4, 7, 8), (1,) * 6)}):
        v5.configure(40, 4)
    sols = power_sum_solutions(40, 4)
    assert len(sols) == len(set(map(tuple, sols))) == 4414
    kids, holder = {}, {}                            # a node's children, and the child holding each split vector
    def reaches(node, a):
        if node not in kids:
            kids[node] = v5.split(4, node)
            holder[node] = {v: c for c in kids[node] for v in c[-1][1]}
        if not kids[node]:
            return v5.solve_node(4, node, 1, x01(a), x01(a))[:2] == ('FEASIBLE', a)
        M = kids[node][0][-1][0]
        for g in v5.stabilizer(node):
            b = v5.act_seq(g, a)
            c = holder[node].get(v5.counts(b, M))
            if c is not None and reaches(c, b): return True
        return False
    lost = [a for a in sols if not reaches((), a)]
    assert not lost, (len(lost), lost[:2])


# ---------- certbb: the exact part ----------

def solved(order, node, lps=BIG, **kw):
    """certbb.solve at v5's configuration, with its proof collected: (verdict, x, stats, tokens)."""
    tokens = []
    verdict, x, stats = certbb.solve(v5.moments(order), node, lps, tokens.append, **kw)
    return verdict, x, stats, tokens


def pinned_box(a, positions):
    lo, hi = [0] * v5.N, [1] * v5.N
    for p in positions: lo[p] = hi[p] = x01(a)[p]
    return lo, hi


def token_boxes(node, tokens, lo=None, hi=None):
    """The box at each token of a proof, replaying its splits (independently of certbb's checker), as far as the
    tokens go (a FEASIBLE or UNKNOWN run's proof stops part way)."""
    out, it = [], iter(tokens)
    for _ in itertools.product(*(V for _, V in node)):
        stack = [(list(lo or [0] * v5.N), list(hi or [1] * v5.N))]
        while stack:
            l, u = stack.pop()
            token = next(it, None)
            if token is None: return out
            out.append((l, u))
            if token[0] == 'B':
                p = token[1]
                stack += [(l[:p] + [1] + l[p + 1:], u[:p] + [1] + u[p + 1:]), (l[:p] + [0] + l[p + 1:], u[:p] + [0] + u[p + 1:])]
    return out


def leaf_boxes(node, tokens, lo=None, hi=None):
    """The box of every leaf token."""
    return [b for b, t in zip(token_boxes(node, tokens, lo, hi), tokens) if t[0] == 'L']


def q_lower_bound_by_hand():
    # Replicata: at N = 48, the single row x0 + x1 = 3, then x0 + x1 = 1; boxes [0,1]^48 and x0 = 0.
    # Expectata: for x0 + x1 = 3, multiplier 1 bounds 3 - 2 = 1 > 0 on the full box and 3 - 1 = 2 with x0 = 0, and
    # multiplier -1 bounds -3; for x0 + x1 = 1, which (1, 0, 0, ...) satisfies, no multiplier from -5 to 5 bounds
    # above 0.
    at(48, 6)
    full = ([0] * 48, [1] * 48)
    lo, hi = certbb.fixed(*full, 0, 0)
    rows = [([(0, 1), (1, 1)], 3)]
    assert certbb.lower_bound(rows, *full, [1]) == 1
    assert certbb.lower_bound(rows, lo, hi, [1]) == 2
    assert certbb.lower_bound(rows, *full, [-1]) == -3
    assert all(certbb.lower_bound([([(0, 1), (1, 1)], 1)], *full, [m]) <= 0 for m in range(-5, 6))


def q_rows_are_build_models():
    # Replicata: at 240@11, node C2 (one vector per modulus) and the published order-10 example's own count node,
    # against overnight_v4.build_model's CP-SAT models of the same nodes.
    # Expectata: node_rows' first rows are v5.moment_rows exactly, and its linear equations are, coefficient for
    # coefficient, the moment equations in v4.build_model's CP-SAT model; then one row per class with the node's
    # count; the example satisfies every row of its node at order 10 and breaks some moment row at order 11, as
    # build_model's models say (OPTIMAL, INFEASIBLE with the example pinned).
    at(240, 11)
    at4(240, 11)
    for order, node in ((11, C2), (10, example_node(v5.CASCADE))):
        rows = certbb.node_rows(v5.moments(order), choice_of(node))
        dense = [([0] * v5.N, b) for _, b in rows]
        for (a, _), (d, _) in zip(rows, dense):
            for p, c in a: d[p] = c
        W, rhs = v5.moment_rows(order)
        assert [d for d, _ in dense[:order]] == [list(w) for w in W] and [b for _, b in dense[:order]] == list(rhs)
        proto = v4.build_model(order, node)[0].Proto()
        lin = [ct.linear for ct in proto.constraints if ct.has_linear()][:order]
        for (d, b), ct in zip(dense[:order], lin):
            got = [0] * v5.N
            for var, c in zip(ct.vars, ct.coeffs): got[var] = c
            assert got == d and list(ct.domain) == [b, b]
        i = order
        for M, v in choice_of(node):
            for r in range(M):
                assert dense[i] == ([int(p % M == r) for p in range(v5.N)], v[r])
                i += 1
        assert i == len(rows)
    a = x01(EXAMPLE)
    node = example_node(v5.CASCADE)
    assert certbb.point_certificate(certbb.node_rows(v5.moments(10), choice_of(node)), a) is None
    assert certbb.point_certificate(certbb.node_rows(v5.moments(11), choice_of(node)), a) is not None
    assert status_of(v4.build_model(10, node, fix=a)[0]) == 'OPTIMAL'
    assert status_of(v4.build_model(11, node, fix=a)[0]) == 'INFEASIBLE'


def q_lattice_cuts_are_implied():
    # Replicata: all 4414 sequences of length 40 and order at least 4 (found by power_sum_solutions, without v5),
    # against v5's residue lattices at 40@4 for the moduli 9, 16, 25, 27, 32; and at 240@11, the order-11 example of
    # length 432 against the lattices of v4's cut moduli, which do not depend on the length.
    # Expectata: every residue vector lies in its lattice, so leaving out overnight_v4's lattice cuts (certbb's rows
    # do) drops no solution of these.
    with patched(v5, SETTINGS=v5.SETTINGS | {(40, 4): ((3, 5, 4, 7, 8), (1,) * 6)}):
        v5.configure(40, 4)
    sols = power_sum_solutions(40, 4)
    assert len(sols) == 4414
    for M in (9, 16, 25, 27, 32):
        S = v5.ExactSystem(v5.lattice_basis(M, 4))
        assert all(S.solvable([sum(a[p] for p in range(r, 40, M)) for r in range(M)]) for a in sols), M
    at(240, 11)
    b = v5.from_hex(v5.EXAMPLES[432, 11], 11)
    for M in V4_CUTS:
        assert v5.ExactSystem(v5.lattice_basis(M, 11)).solvable([sum(b[p] for p in range(r, 432, M)) for r in range(M)])


def q_verify_rejects_corrupted_proofs():
    # Replicata: certbb's proof for node C2 at 240@11 (INFEASIBLE), then copies with one defect each: a leaf's
    # multipliers negated; a leaf's multipliers all 0; the last token dropped; a token appended; a split on a position
    # already fixed; a leaf with one multiplier too many; a split with two leaf children replaced by the first child's
    # leaf (its certificate needs the split's fixing: checked); the proof checked against another node; a 'B' token
    # whose position is out of range; a token that is not a pair; with x_0 pinned to 0, a split on x_0 followed by
    # valid proofs for x_0 = 0 and x_0 = 1 (sound, as the two boxes cover the pinned one, but not a proof verify
    # accepts: a split must split a free position).
    # Expectata: the proof verifies; every copy raises ProofError in verify.
    at(240, 11)
    m = v5.moments(11)
    verdict, _, _, tokens = solved(11, C2)
    assert verdict == 'INFEASIBLE'
    certbb.verify(m, C2, tokens)
    leaves = [i for i, t in enumerate(tokens) if t[0] == 'L']
    i = leaves[len(leaves) // 2]
    bad = []
    bad.append(tokens[:i] + [('L', [-c for c in tokens[i][1]])] + tokens[i + 1:])
    bad.append(tokens[:i] + [('L', [0] * len(tokens[i][1]))] + tokens[i + 1:])
    bad.append(tokens[:-1])
    bad.append(tokens + [tokens[-1]])
    first_split = tokens[0][1]
    j = next(k for k, t in enumerate(tokens[1:], 1) if t[0] == 'B')
    bad.append(tokens[:j] + [('B', first_split)] + tokens[j + 1:])
    bad.append(tokens[:i] + [('L', tokens[i][1] + [0])] + tokens[i + 1:])
    k = next(k for k in range(len(tokens) - 2)
             if tokens[k][0] == 'B' and tokens[k + 1][0] == 'L' and tokens[k + 2][0] == 'L')
    lifted = tokens[:k] + [tokens[k + 1]] + tokens[k + 3:]
    box = token_boxes(C2, lifted)[k]
    rows = certbb.node_rows(m, choice_of(C2))
    assert certbb.lower_bound(rows, *box, tokens[k + 1][1]) <= 0          # so the lifted copy is really invalid
    bad.append(lifted)
    bad.append([('B', v5.N)] + tokens[1:])
    bad.append(tokens[:i] + [('L',)] + tokens[i + 1:])
    for proof in bad:
        expect_proof_error(lambda: certbb.verify(m, C2, proof))
    other = C2[:-1] + ((9, ((12, 9, 6, 12, 18, 15, 16, 13, 19),)),)
    expect_proof_error(lambda: certbb.verify(m, other, tokens))
    full = ([0] * v5.N, [1] * v5.N)
    (lo0, hi0), (lo1, hi1) = certbb.fixed(*full, 0, 0), certbb.fixed(*full, 0, 1)
    proof0, proof1 = solved(11, C2, lo=lo0, hi=hi0)[3], solved(11, C2, lo=lo1, hi=hi1)[3]
    certbb.verify(m, C2, proof0, lo0, hi0)
    certbb.verify(m, C2, proof1, lo1, hi1)
    expect_proof_error(lambda: certbb.verify(m, C2, [('B', 0)] + proof0 + proof1, lo0, hi0))


def q_verify_rejects_float_multipliers():
    # Replicata (the review's gaps.py): certbb's proof for node C2 at 240@11; for a random leaf and row, the shift of
    # that row's multiplier just past the edge of validity, so that the exact bound (computed here independently of
    # certbb) is 0 or less, chosen so that the same multipliers as floats get a positive bound from certbb.lower_bound
    # in float64 arithmetic; the proof with that leaf's multipliers replaced by the floats, and by the shifted
    # integers.
    # Expectata: the floats' float64 bound is positive and their exact bound is not, so only the check that every
    # multiplier is an int stands between them and acceptance; verify raises ProofError for both copies, the float
    # one at the integer check.  (Red: certbb without that check accepts the float copy, as the review found.)
    at(240, 11)
    m = v5.moments(11)
    verdict, _, _, tokens = solved(11, C2)
    assert verdict == 'INFEASIBLE'
    rows = certbb.node_rows(m, choice_of(C2))
    dense = [([0] * v5.N, b) for _, b in rows]
    for (a, _), (d, _) in zip(rows, dense):
        for p, c in a: d[p] += c
    boxes = token_boxes(C2, tokens)
    leaves = [i for i, t in enumerate(tokens) if t[0] == 'L']
    rng = random.Random(3)
    found = None
    for _ in range(200):
        i = rng.choice(leaves); n = tokens[i][1]; j = rng.randrange(len(n)); l, u = boxes[i]
        beta = sum(c * b for c, (_, b) in zip(n, dense))
        g = [-sum(c * d[p] for c, (d, _) in zip(n, dense)) for p in range(v5.N)]
        aj, bj = dense[j]
        def L(s):                                  # the exact bound with n_j shifted by s
            return beta + s * bj + sum(min((t - s * aj[p]) * l[p], (t - s * aj[p]) * u[p]) for p, t in enumerate(g))
        assert L(0) > 0
        for sign in (1, -1):
            hi = 1
            while L(sign * hi) > 0 and hi < 2 ** 400: hi *= 2
            if L(sign * hi) > 0: continue
            lo_ = 0
            while hi - lo_ > 1:
                mid = (lo_ + hi) // 2
                if L(sign * mid) > 0: lo_ = mid
                else: hi = mid
            for s in range(sign * hi, sign * hi + sign * 64, sign):        # just past the edge: exact bound <= 0
                shifted = n[:j] + [n[j] + s] + n[j + 1:]
                if L(s) <= 0 and certbb.lower_bound(rows, l, u, [float(c) for c in shifted]) > 0:
                    found = (i, shifted)
                    break
            break
        if found: break
    assert found, 'no certificate fools float64'
    i, shifted = found
    message = expect_proof_error(lambda: certbb.verify(m, C2, tokens[:i] + [('L', [float(c) for c in shifted])] + tokens[i + 1:]))
    assert 'integer' in message, message
    expect_proof_error(lambda: certbb.verify(m, C2, tokens[:i] + [('L', shifted)] + tokens[i + 1:]))


class GiveUp(certbb.Lp):
    """certbb's Lp, except that every solve stops at its iteration limit: no point, no ray."""
    def solve(self, lo, hi, basis=None): return 'Iteration limit reached', None


def point_setup():
    """The review's gaps.py setup: at 240@11, order 11, the published order-10 example's own count node, and the box
    pinned to the example at all but 8 random positions."""
    at(240, 11)
    node = example_node(v5.CASCADE)
    free = random.Random(4).sample(range(v5.N), 8)
    x = x01(EXAMPLE)
    lo = [0 if p in free else x[p] for p in range(v5.N)]
    hi = [1 if p in free else x[p] for p in range(v5.N)]
    return node, lo, hi


def q_verify_accepts_point_certificates():
    # Replicata: point_setup, with an LP that always gives up (GiveUp), so that a box closes only once a single point is
    # left, by a point certificate (+-1 on the first row the point breaks); the proof then through certbb.verify.
    # Expectata: INFEASIBLE with 256 leaves, the full depth-8 tree of the free positions, every leaf box a single point
    # and every certificate a single +-1; verify accepts the proof.  (Red: with point_certificate's sign flipped, the
    # review's surviving mutant, verify rejects it.)
    node, lo, hi = point_setup()
    with patched(certbb, Lp=GiveUp):
        verdict, _, stats, tokens = solved(11, node, lo=lo, hi=hi)
    assert verdict == 'INFEASIBLE' and stats['leaves'] == 256 and stats['splits'] == 255, (verdict, stats)
    for (l, u), (kind, n) in zip(token_boxes(node, tokens, lo, hi), tokens):
        assert kind == 'B' or (l == u and sorted(map(abs, n)) == [0] * (len(n) - 1) + [1])
    certbb.verify(v5.moments(11), node, tokens, lo, hi)


def q_solve_checks_point_certificates():
    # Replicata: the setup of q_verify_accepts_point_certificates, with certbb.point_certificate replaced by one whose
    # sign is flipped (-1 where the point's defect is positive, +1 where negative: the review's surviving mutant).
    # Expectata: certbb.solve raises ProofError at the first single-point box, having emitted only the 8 splits down to
    # it, so no unchecked certificate leaves solve.
    node, lo, hi = point_setup()
    real = certbb.point_certificate
    def flipped(rows, x):
        n = real(rows, x)
        return None if n is None else [-c for c in n]
    tokens = []
    with patched(certbb, Lp=GiveUp, point_certificate=flipped):
        expect_proof_error(lambda: certbb.solve(v5.moments(11), node, BIG, tokens.append, lo, hi))
    assert [t[0] for t in tokens] == ['B'] * 8, tokens[:10]


def q_certbb_refuses_python_O():
    # Replicata: a fresh python -O importing certbb; another running overnight_v5.py 40 6 under -O.
    # Expectata: both fail with certbb's ImportError naming python -O, and no journal or log for 40@6 appears.
    p = run_child(f'import sys; sys.path.insert(0, {HERE!r})\nimport certbb\n', '-O')
    assert p.returncode != 0 and 'ImportError' in p.stderr and 'python -O' in p.stderr, p.stderr[-600:]
    names = [os.path.join(HERE, f) for f in ('overnight_v5_40_6_journal.jsonl', 'overnight_v5_40_6.log')]
    assert not any(map(os.path.exists, names))
    p = subprocess.run([sys.executable, '-B', '-O', os.path.join(HERE, 'overnight_v5.py'), '40', '6'],
                       capture_output=True, text=True, timeout=300, cwd=HERE)
    assert p.returncode != 0 and 'ImportError' in p.stderr and 'python -O' in p.stderr, p.stderr[-600:]
    assert not any(map(os.path.exists, names))


def q_verify_holds_under_python_O():
    # Replicata: a fresh python -O (__debug__ False, so every assert is skipped) that loads certbb.py with its import
    # guard (the line that raises under -O) removed, then checks at 240@11 (a) the all-zero certificate for the top
    # mod-3 node, (b) the same with a float 0.5 in place of one 0, (c) a proof for it that ends early, (d) a proof
    # that goes on after its last box, (e) a split of an already fixed position, (f) a certificate with one multiplier
    # too many; and, as a control, (g) a proof of an empty pool, which is empty and valid.
    # Expectata: __debug__ is False there and (a) to (f) each raise ProofError, (g) none: verify's checks do not rest
    # on assert.  (Red: certbb with assert-based checks accepts (a) under -O, as the review found.)
    path = os.path.join(HERE, 'certbb.py')
    code = f"""import sys, json, types; sys.dont_write_bytecode = True; sys.path.insert(0, {HERE!r})
src = open({path!r}).read()
guard = [line for line in src.splitlines(True) if line.startswith('if not __debug__:')]
# TODO: error copy; says certbb.py does not have exactly one import guard line (this child runs under -O, so no assert)
if len(guard) != 1 or src.count(guard[0]) != 1: raise SystemExit('Claude: "certbb.py has no single import guard line"')
mod = types.ModuleType('certbb'); mod.__file__ = {path!r}
exec(compile(src.replace(guard[0], ''), {path!r}, 'exec'), mod.__dict__)
sys.modules['certbb'] = mod
import overnight_v5 as v5
v5.configure(240, 11)
m = v5.moments(11)
node = ((3, ((40, 40, 40),)),)
zero = [0] * 14
out = {{'debug': __debug__}}
def outcome(name, proof, node=node):
    try:
        mod.verify(m, node, proof)
        out[name] = 'accepted'
    except Exception as e:
        out[name] = type(e).__name__
outcome('a', [('L', zero)])
outcome('b', [('L', zero[:-1] + [0.5])])
outcome('c', [('B', 0), ('L', zero)])
outcome('d', [('L', zero), ('L', zero)])
outcome('e', [('B', 0), ('B', 0)])
outcome('f', [('L', zero + [0])])
outcome('g', [], node + ((5, ()),))
print(json.dumps(out))
"""
    p = run_child(code, '-O')
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout)
    assert out == {'debug': False, 'a': 'ProofError', 'b': 'ProofError', 'c': 'ProofError', 'd': 'ProofError',
                   'e': 'ProofError', 'f': 'ProofError', 'g': 'accepted'}, out


# ---------- certbb: streaming verification in solve_node ----------

def q_check_streams_a_long_proof_in_bounded_memory():
    # Replicata: in a fresh process at 40@6, the node ((4, ((0, 0, 0, 0),)),), whose counts total 0 where the moment row
    # of degree 0 says 20, so that n0 = (1 on that row, -2 on each count row, 0 elsewhere) closes every box with bound
    # 40; a synthetic proof the size of L5's (274,663 tokens, 254.6 million decimal digits): splits on positions 0 to
    # 16 down to all 131,072 boxes of depth 17, each closed by its own certificate (K + j) n0, K = 2^1290, j the leaf's
    # number; the proof made token by token by a fake certbb.solve inside v5.solve_node, which says INFEASIBLE.  The
    # process's peak resident memory (getrusage's ru_maxrss, bytes on macOS) before and after; then the same tokens
    # counted and hashed without being kept, and then kept in a list, as a solve_node holding its proof would.
    # Expectata: INFEASIBLE with 131,072 leaves, and the proof sha1 is the sha1 of the tokens' reprs; the stream holds
    # more than 100 MB of tokens and more than 250 million digits, yet the peak grows by less than 20 MB while
    # solve_node checks it; keeping the tokens raises the peak by more than 100 MB (so the measurement sees a kept proof).
    assert sys.platform == 'darwin', sys.platform              # ru_maxrss is in bytes on macOS (kilobytes on Linux)
    code = f"""import sys, json, resource, hashlib; sys.dont_write_bytecode = True; sys.path.insert(0, {HERE!r})
import overnight_v5 as v5, certbb
def peak(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
v5.configure(40, 6)
node = ((4, ((0, 0, 0, 0),)),)
n0 = [1] + [0] * 5 + [-2] * 4
assert certbb.lower_bound(certbb.node_rows(v5.moments(6), [(4, (0, 0, 0, 0))]), [0] * 40, [1] * 40, n0) == 40
DEPTH, K = 17, 2 ** 1290
def stream():
    j = 0
    def tree(d):
        nonlocal j
        if d == DEPTH:
            j += 1
            yield ('L', [(K + j) * c for c in n0])
            return
        yield ('B', d)
        yield from tree(d + 1)
        yield from tree(d + 1)
    yield from tree(0)
def fake_solve(moments, node, lps, emit, lo=None, hi=None):
    leaves = 0
    for token in stream():
        emit(token)
        leaves += token[0] == 'L'
    return 'INFEASIBLE', None, {{'lp': 0, 'leaves': leaves}}
certbb.solve = fake_solve
p0 = peak()
verdict, _, found = v5.solve_node(6, node, 1)
p1 = peak()
sha, tokens, digits, size = hashlib.sha1(), 0, 0, 0
for t in stream():
    sha.update(repr(t).encode())
    tokens += 1
    digits += sum(len(str(abs(c))) for c in t[1]) if t[0] == 'L' else 0
    size += sys.getsizeof(t) + (sys.getsizeof(t[1]) + sum(map(sys.getsizeof, t[1])) if t[0] == 'L' else 0)
p2 = peak()
kept = list(stream())
p3 = peak()
print(json.dumps(dict(verdict=verdict, found=found, sha1=sha.hexdigest(), tokens=tokens, digits=digits, size=size,
                      p0=p0, p1=p1, p2=p2, p3=p3, kept=len(kept))))
"""
    p = run_child(code)
    assert p.returncode == 0, p.stderr[-2000:]
    r = json.loads(p.stdout)
    MB = 2 ** 20
    assert r['verdict'] == 'INFEASIBLE' and r['found']['leaves'] == 2 ** 17 and r['tokens'] == 2 ** 18 - 1, r
    assert r['found']['proof'] == r['sha1'], r
    assert r['size'] > 100 * MB and r['digits'] > 250 * 10 ** 6, r
    assert r['p1'] - r['p0'] < 20 * MB, r
    assert r['p3'] - r['p2'] > 100 * MB, r


def proof_of(order, node):
    """certbb's real proof of an INFEASIBLE node, collected (for the fakes below)."""
    verdict, _, stats, tokens = solved(order, node)
    assert verdict == 'INFEASIBLE'
    return tokens, stats


def fake_solve(tokens, emitted):
    """A stand-in for certbb.solve that emits tokens one at a time, counting them in emitted, and says INFEASIBLE."""
    def solve(moments, node, lps, emit, lo=None, hi=None):
        for t in tokens:
            emit(t)
            emitted[0] += 1
        return 'INFEASIBLE', None, {'lp': 0, 'leaves': sum(t[0] == 'L' for t in tokens)}
    return solve


def q_solve_node_checks_each_token_as_it_comes():
    # Replicata: at 240@11, solve_node on node C2 with certbb.solve replaced by a fake that emits C2's real proof with
    # its 10th leaf's certificate negated, counting the tokens emit took, then says INFEASIBLE.
    # Expectata: ProofError from inside emit at the negated certificate: the fake got exactly the tokens before it out,
    # none after.  (Red: a solve_node that collects the proof and checks it afterwards lets the fake run to its end.)
    at(240, 11)
    tokens, _ = proof_of(11, C2)
    i = [k for k, t in enumerate(tokens) if t[0] == 'L'][9]
    bad = tokens[:i] + [('L', [-c for c in tokens[i][1]])] + tokens[i + 1:]
    emitted = [0]
    with patched(certbb, solve=fake_solve(bad, emitted)):
        expect_proof_error(lambda: v5.solve_node(11, C2, BIG))
    assert emitted[0] == i, (emitted[0], i)


def q_solve_node_infeasible_needs_a_complete_proof():
    # Replicata: at 240@11, solve_node on node C2 with certbb.solve replaced by fakes that say INFEASIBLE after emitting
    # (a) nothing, (b) C2's real proof but its last token, (c) C2's real proof and then its first token again, (d) C2's
    # real proof.
    # Expectata: ProofError for (a), (b) and (c); for (d), INFEASIBLE, with the leaves the fake reported and the sha1
    # of the proof's token reprs; solve_node on C2 with the real certbb gives that same sha1 and leaves.
    at(240, 11)
    tokens, stats = proof_of(11, C2)
    for proof in ([], tokens[:-1], tokens + tokens[:1]):
        with patched(certbb, solve=fake_solve(proof, [0])):
            expect_proof_error(lambda: v5.solve_node(11, C2, BIG))
    sha = hashlib.sha1()
    for t in tokens: sha.update(repr(t).encode())
    with patched(certbb, solve=fake_solve(tokens, [0])):
        verdict, _, found = v5.solve_node(11, C2, BIG)
    assert verdict == 'INFEASIBLE' and found['proof'] == sha.hexdigest() and found['leaves'] == stats['leaves'], found
    verdict, _, found = v5.solve_node(11, C2, BIG)
    assert verdict == 'INFEASIBLE' and found == {'lps': stats['lp'], 'leaves': stats['leaves'], 'proof': sha.hexdigest()}, found


def q_lp_budget_counts_lp_solves():
    # Replicata: at 240@11, solve_node on node C2 with no limit, then with budgets of one LP solve fewer than it used,
    # and of exactly as many.
    # Expectata: one fewer gives UNKNOWN after exactly that many LP solves; exactly as many gives the same INFEASIBLE
    # verdict and proof sha1 as no limit: the budget counts LP solves, deterministically.
    at(240, 11)
    verdict, _, found = v5.solve_node(11, C2, BIG)
    assert verdict == 'INFEASIBLE', found
    short = v5.solve_node(11, C2, found['lps'] - 1)
    assert short[0] == 'UNKNOWN' and short[2]['lps'] == found['lps'] - 1, short
    assert v5.solve_node(11, C2, found['lps']) == (verdict, None, found)


# ---------- certbb: the search, where floating point only guides ----------

def q_planted_point_never_pruned():
    # Replicata: at 240@11, order 10, the published order-10 example's own count node; for each of 150, 100, 60 and
    # 30 random positions pinned to the example (the box), the search for at most 4000 LP solves.
    # Expectata: FEASIBLE or UNKNOWN, never INFEASIBLE; a FEASIBLE point satisfies every row exactly, lies in the
    # box, and has exact order at least 10; no leaf token of any proof has a box holding the example; and the
    # proofs close more than 1000 boxes in all, so this is no empty test.
    at(240, 11)
    a = EXAMPLE
    node = example_node(v5.CASCADE)
    closed = 0
    for seed, pins in ((1, 150), (2, 100), (3, 60), (4, 30)):
        lo, hi = pinned_box(a, random.Random(seed).sample(range(v5.N), pins))
        verdict, x, stats, tokens = solved(10, node, 4000, lo=lo, hi=hi)
        assert verdict in ('FEASIBLE', 'UNKNOWN'), (seed, verdict, stats)
        if verdict == 'FEASIBLE':
            assert certbb.point_certificate(certbb.node_rows(v5.moments(10), choice_of(node)), x) is None
            assert all(l <= t <= u for t, l, u in zip(x, lo, hi))
            assert v5.exact_order([2 * t - 1 for t in x]) >= 10
        boxes = leaf_boxes(node, tokens, lo, hi)
        assert len(boxes) == stats['leaves'], (len(boxes), stats)
        assert not any(all(l <= t <= u for t, l, u in zip(x01(a), l2, u2)) for l2, u2 in boxes), seed
        closed += len(boxes)
    assert closed > 1000, closed


def q_pinned_order11_agrees_with_cpsat():
    # Replicata: at 240@11, order 11, the example's own count node with 100 random positions pinned to the example
    # (which has exact order 10); certbb, then CP-SAT on overnight_v4.build_model's model with the same pins.
    # Expectata: both INFEASIBLE, and certbb's proof, which closes more than one box, verifies.
    at(240, 11)
    at4(240, 11)
    node = example_node(v5.CASCADE)
    positions = random.Random(4).sample(range(v5.N), 100)
    lo, hi = pinned_box(EXAMPLE, positions)
    verdict, _, stats, tokens = solved(11, node, lo=lo, hi=hi)
    assert verdict == 'INFEASIBLE' and stats['leaves'] > 1, (verdict, stats)
    certbb.verify(v5.moments(11), node, tokens, lo, hi)
    md, x = v4.build_model(11, node)
    for p in positions: md.Add(x[p] == x01(EXAMPLE)[p])
    assert status_of(md) == 'INFEASIBLE'


class FakeLp(certbb.Lp):
    """certbb's Lp, except that solve answers with fake(lp, lo, hi) instead of HiGHS."""
    fake = None
    def solve(self, lo, hi, basis=None): return FakeLp.fake(self, lo, hi)


def q_lp_that_lies_about_infeasibility_closes_nothing():
    # Replicata: at 240@11, order 10, the example's own count node (feasible: the example is in it) with 150
    # positions pinned; an LP that says 'Infeasible' at every box, with a random dual ray; 300 LP solves at most.
    # Expectata: UNKNOWN (never INFEASIBLE); no closed box holds the example (some deep boxes do close: a random
    # ray, checked exactly, can be a valid certificate for a small box with no solution); some rays fail.
    at(240, 11)
    node = example_node(v5.CASCADE)
    lo, hi = pinned_box(EXAMPLE, random.Random(5).sample(range(v5.N), 150))
    rng = np.random.default_rng(6)
    with patched(certbb, Lp=FakeLp), patched(FakeLp, fake=lambda lp, lo, hi: ('Infeasible', rng.normal(size=len(lp.b)))):
        verdict, _, stats, tokens = solved(10, node, 300, lo=lo, hi=hi)
    assert verdict == 'UNKNOWN' and stats['lp'] == 300 and stats['cert_fail'] > 0, (verdict, stats)
    assert not any(all(l <= t <= u for t, l, u in zip(x01(EXAMPLE), l2, u2)) for l2, u2 in leaf_boxes(node, tokens, lo, hi))


def q_lp_that_gives_up_closes_nothing():
    # Replicata: at 240@11, order 10, the example's own count node with 150 positions pinned; an LP whose every solve
    # stops at its iteration limit (HiGHS's status 'Iteration limit reached', no point, no ray); 300 LP solves at most.
    # Expectata: UNKNOWN; every solve counted in lp_other; no closed box holds the example (boxes close only where a
    # single point remains and breaks a row).
    at(240, 11)
    node = example_node(v5.CASCADE)
    lo, hi = pinned_box(EXAMPLE, random.Random(9).sample(range(v5.N), 150))
    with patched(certbb, Lp=GiveUp):
        verdict, _, stats, tokens = solved(10, node, 300, lo=lo, hi=hi)
    assert verdict == 'UNKNOWN' and stats['lp_other'] == stats['lp'] == 300, (verdict, stats)
    assert not any(all(l <= t <= u for t, l, u in zip(x01(EXAMPLE), l2, u2)) for l2, u2 in leaf_boxes(node, tokens, lo, hi))


def q_lp_that_lies_about_a_solution_finds_nothing():
    # Replicata: at 240@11, order 11, the example's own count node; an LP that says 'Optimal' at every box with the
    # example itself (exact order 10) as its point, 0/1 valued; 300 LP solves at most.
    # Expectata: UNKNOWN (never FEASIBLE): an integral LP point is a witness only if it satisfies every row exactly.
    at(240, 11)
    point = np.array(x01(EXAMPLE), float)
    with patched(certbb, Lp=FakeLp), patched(FakeLp, fake=lambda lp, lo, hi: ('Optimal', point)):
        verdict, x, stats, _ = solved(11, example_node(v5.CASCADE), 300)
    assert verdict == 'UNKNOWN' and x is None, (verdict, stats)


def q_pools():
    # Replicata: at 240@11, (a) the open mod-4 node with an empty mod-8 pool; (b) the first three members of the real
    # mod-8 pool of that node, as one pool; (c) order 10, the example's counts for 3, 5, 7, 4, 8, 11, 13 and a mod-9
    # pool whose second member is the example's own, with the example pinned at all but 20 positions.
    # Expectata: (a) INFEASIBLE with an empty proof, which verifies; (b) INFEASIBLE, three choices, and the proof
    # verifies; (c) FEASIBLE with the example's mod-9 counts (a search over the first member alone ends INFEASIBLE,
    # verified).
    at(240, 11)
    node = TOP4 + ((8, ()),)
    verdict, _, stats, tokens = solved(11, node)
    assert verdict == 'INFEASIBLE' and tokens == [] and stats['choices'] == 0
    certbb.verify(v5.moments(11), node, tokens)
    pool = v5.split(11, TOP4)[-1][-1][1]
    node = TOP4 + ((8, pool[:3]),)
    verdict, _, stats, tokens = solved(11, node)
    assert verdict == 'INFEASIBLE' and stats['choices'] == 3, (verdict, stats)
    certbb.verify(v5.moments(11), node, tokens)
    true9 = v5.counts(EXAMPLE, 9)
    other = v5.admissible(10, 9, ((3, v5.counts(EXAMPLE, 3)),))[0]
    lo, hi = pinned_box(EXAMPLE, random.Random(7).sample(range(v5.N), 220))
    base = example_node((3, 5, 7, 4, 8, 11, 13))
    verdict, x, _, _ = solved(10, base + ((9, (other, true9)),), lo=lo, hi=hi)
    assert verdict == 'FEASIBLE' and v5.counts([2 * t - 1 for t in x], 9) == true9
    verdict, _, _, tokens = solved(10, base + ((9, (other,)),), lo=lo, hi=hi)
    assert verdict == 'INFEASIBLE'
    certbb.verify(v5.moments(10), base + ((9, (other,)),), tokens, lo, hi)


def journal_leaves(verdict, k, seed):
    """k random depth-8 single-vector nodes overnight_240_v3's journal holds with this verdict at budget 120 (closed
    within 120 s of wall-clock time, in the run before quick-restart search); read only."""
    keys = []
    with open(V3_JOURNAL) as fh:
        next(fh)
        for line in fh:
            r = json.loads(line)
            parts = r['key'].split()
            if r['verdict'] == verdict and r['budget'] == 120 and len(parts) == 8 and '#' not in r['key']:
                keys.append(r['key'])
    keys = sorted(set(keys))
    return [tuple((int(M), (tuple(int(t) for t in v.strip('[]').split(',')),))
                  for M, v in (part.split(':') for part in key.split()))
            for key in random.Random(seed).sample(keys, k)]


def q_agrees_with_cpsat_on_settled_leaves():
    # Replicata: at 240@11, 12 random depth-8 nodes that overnight_240_v3's journal records INFEASIBLE (CP-SAT) at
    # budget 120, each through solve_node with the bottom budget.
    # Expectata: INFEASIBLE for each, so each proof was checked as it was made.
    at(240, 11)
    for node in journal_leaves('INFEASIBLE', 12, 8):
        verdict, _, found = v5.solve_node(11, node, v5.BUDGET[-1])
        assert verdict == 'INFEASIBLE', (v5.node_key(node), verdict, found)


# ---------- end to end: small configurations with answers known from Table 2 ----------

DRIVER = """import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {here!r})
import overnight_v5 as v5
if __name__ == '__main__':
    v5.configure({n}, {order})
    v5.JOURNAL, v5.LOG, v5.PROCESSES = {journal!r}, {log!r}, 2
    v5.run()
"""


def end_to_end(n, order):
    """A fresh run of overnight_v5 at (n, order) in a child process with two worker processes, its journal and
    log under RUNS; then a second run on the same journal.  Returns both logs' text and the journal's records."""
    journal, log = os.path.join(RUNS, f'overnight_v5_{n}_{order}_journal.jsonl'), os.path.join(RUNS, f'overnight_v5_{n}_{order}.log')
    for path in (journal, log):
        if os.path.exists(path): os.remove(path)
    script = os.path.join(RUNS, f'drive_{n}_{order}.py')
    open(script, 'w').write(DRIVER.format(here=HERE, n=n, order=order, journal=journal, log=log))
    texts = []
    for _ in range(2):
        p = subprocess.run([sys.executable, '-B', script], capture_output=True, text=True, timeout=3600)
        assert p.returncode == 0, p.stderr[-2000:]
        texts.append(open(log).read())
        os.rename(log, log + f'.{len(texts)}')
    records = [json.loads(line) for line in open(journal).read().splitlines()]
    return texts, records


def check_records(records, n, order):
    """The journal's header is v5's for (n, order); every solve's record has whole lps and leaves within its budget and
    a 40-digit proof sha1, and every CLOSED record has none of them."""
    assert (records[0]['tag'], records[0]['N'], records[0]['order']) == ('overnight_v5', n, order), records[0]
    for r in records[1:]:
        solve = {'lps', 'leaves', 'proof'} & set(r)
        assert solve == (set() if r['verdict'] == 'CLOSED' else {'lps', 'leaves', 'proof'}), r
        assert r['verdict'] == 'CLOSED' or (0 <= r['leaves'] <= r['lps'] <= r['budget'] and len(r['proof']) == 40), r


def check_witness_run(n, order):
    texts, records = end_to_end(n, order)
    for text in texts:
        assert f'startup control passed: the order-{order - 1} example of length {n}' in text, text[-2000:]
        assert 'NOT FINISHED' not in text and 'ALL NODES CLOSED' not in text, text[-2000:]
        line = [t for t in text.splitlines() if 'Claude: "WITNESS FOUND, exact order' in t]
        assert len(line) == 1, text[-2000:]
        X = set(json.loads(line[0].split('X = ')[1].rstrip('"')))
        a = [1 if p + 1 in X else -1 for p in range(n)]
        assert v5.exact_order(a) == order, line
    check_records(records, n, order)


def check_closed_run(n, order):
    texts, records = end_to_end(n, order)
    for text in texts:
        assert f'startup control passed: the order-{order - 1} example of length {n}' in text, text[-2000:]
        assert 'ALL NODES CLOSED' in text and 'NOT FINISHED' not in text and 'WITNESS' not in text, text[-2000:]
    top = [r['verdict'] for r in records[1:] if r['key'] == '']
    assert top == ['UNKNOWN', 'CLOSED'], top
    assert '[1] {}: UNKNOWN' in texts[0] and '] {' not in texts[1]
    check_records(records, n, order)
    return [r['leaves'] for r in records[1:] if r['verdict'] == 'INFEASIBLE']


def q_end_to_end_48_6_finds_a_witness():
    # Replicata: overnight_v5 at 48@6 (m*(48) = 6 in Table 2), its SETTINGS budgets, run twice.
    # Expectata: each run passes its control and logs one witness whose X has exact order 6.
    check_witness_run(48, 6)


def q_end_to_end_40_6_closes():
    # Replicata: overnight_v5 at 40@6 (m*(40) = 5), run twice on one journal.
    # Expectata: each run passes its control and ends ALL NODES CLOSED; the top node was split (UNKNOWN, then
    # CLOSED in the journal); every solve's record has its lps, leaves and proof; some node closed INFEASIBLE on a
    # proof of at least one leaf, so certbb closed boxes; the second run solves no node, settling the top from the
    # journal.
    assert max(check_closed_run(40, 6)) > 0


def q_end_to_end_56_6_closes():
    # Replicata: overnight_v5 at 56@6 (m*(56) = 5), run twice.  Expectata: as for 40@6.
    assert max(check_closed_run(56, 6)) > 0


def q_end_to_end_64_7_closes():
    # Replicata: overnight_v5 at 64@7 (m*(64) = 6; its control walks Thue-Morse at order 6, with 64 = 2^6),
    # run twice.  Expectata: as for 40@6.
    assert max(check_closed_run(64, 7)) > 0


def q_end_to_end_104_7_closes():
    # Replicata: overnight_v5 at 104@7 (m*(104) = 6), run twice.
    # Expectata: as for 40@6, except that no INFEASIBLE verdict needed a leaf: the mod-8 splits leave no admissible
    # vector, so that tree closes by exact enumeration (see SETTINGS), and its INFEASIBLE nodes are empty pools.
    assert set(check_closed_run(104, 7)) == {0}


# ---------- runner ----------

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
