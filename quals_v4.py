#!/usr/bin/env python3
"""Quals for overnight_v4.py.  Run: python3 quals_v4.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the
resultata (what happened instead).  Quals marked "regression" pin numbers found independently earlier, by
v2 and by agent recounts, rather than stating a property.  Most quals are quals_v3.py's, ported to v4 at
N = 240, ORDER = 11; the end-to-end quals run small configurations whose answers are known from the paper's
Table 2, with journals and logs under RUNS.
"""
import sys
sys.dont_write_bytecode = True
import os, time, random, itertools, subprocess, tempfile, traceback, json, inspect, types
from concurrent.futures import Future
import sympy as sp
import overnight_v4 as v4
import overnight_240_v3 as v3
from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = '/private/tmp/claude-502/-Users-dreeves-lab-powersums/13df408b-e47a-428d-aa1d-b77740929a67/scratchpad/next/v4runs'
C_STAR = (14, 21, 3, 10, 17, 24, 31)          # v3's representative of the open mod-7 orbit (v2 used its R-image)
TOP4 = ((3, ((40, 40, 40),)), (5, ((24,) * 5,)), (7, (C_STAR,)), (4, ((30,) * 4,)))
EXAMPLE = v4.from_hex(v4.EXAMPLES[240, 10], 10)
SIGNS_12_3 = '+-+---+++-+-'                   # order 3, f(-1) = 8: found by CP-SAT for these quals


def x01(a): return [(t + 1) // 2 for t in a]
def members(children): return [v for c in children for v in c[-1][1]]
def status_of(md): return cp_model.CpSolver().StatusName(v4.solve(md, 120)[1])
def example_node(Ms): return tuple((M, (v4.counts(EXAMPLE, M),)) for M in Ms)


def at(n, order):
    """Configure v4 for (n, order) unless it already is."""
    if (v4.N, v4.ORDER) != (n, order): v4.configure(n, order)


def expect_assertion(f, where):
    """Run f; it must raise AssertionError from inside the function named where."""
    try:
        f()
    except AssertionError as e:
        frames = traceback.extract_tb(e.__traceback__)
        assert frames[-1].name == where, frames[-1]
        return
    # TODO: error copy; says the expected assertion did not fire, naming the function where it should have
    raise AssertionError(f'Claude: "the expected assertion did not fire: {where}"')


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
    """A with-block in which v4's N is n, with no cached results from any other N on the way in or out."""
    def __init__(self, n): self.n = n
    def __enter__(self):
        self.saved = v4.N
        v4.N = self.n
        v4.configure.__globals__  # (v4's own namespace; the caches below are its lru_caches)
        for f in (v4.lattice_basis, v4.moment_rows, v4.integer_system, v4.admissible, v4.moment_basis): f.cache_clear()
    def __exit__(self, *exc):
        v4.N = self.saved
        for f in (v4.lattice_basis, v4.moment_rows, v4.integer_system, v4.admissible, v4.moment_basis): f.cache_clear()


def cpsat_enumerate(order, M, fixed):
    """Independent enumeration of admissible count vectors with CP-SAT (v2's method, parent sums generalized)."""
    md = cp_model.CpModel()
    c = [md.NewIntVar(0, v4.size(M, r), f'c{r}') for r in range(M)]
    md.Add(sum(c) == v4.N // 2)
    v4.add_lattice(md, [2 * c[r] - v4.size(M, r) for r in range(M)], v4.lattice_basis(M, order), 'z')
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
    p = sp.Poly((x - 1) ** order * (x + 1) ** plus, x)
    gens = []
    for k in range(M):
        r = sp.Poly(sp.rem(x ** k * p.as_expr(), x ** M - 1, x), x)
        gens.append([int(r.coeff_monomial(x ** i)) for i in range(M)])
    return gens


# ---------- settings and configuration ----------

def q_settings_table():
    # Replicata: SETTINGS and EXAMPLES.
    # Expectata: (240, 11) holds overnight_240_v3.py's exact CASCADE, CUTS and BUDGET; (304, 9) is present; every
    # entry has one budget per depth plus the bottom; every entry has its control's examples: one of length N
    # and order ORDER - 1, and at least one of order ORDER and length below 2^ORDER.
    assert v4.SETTINGS[240, 11] == (v3.CASCADE, v3.CUTS, v3.BUDGET)
    assert (304, 9) in v4.SETTINGS
    for (n, order), (cascade, cuts, budget) in v4.SETTINGS.items():
        assert len(budget) == len(cascade) + 1, (n, order)
        assert (n, order - 1) in v4.EXAMPLES, (n, order)
        assert any(m == order and k < 2 ** order for k, m in v4.EXAMPLES), (n, order)


def q_examples_exact():
    # Replicata: every code in EXAMPLES, decoded.  Expectata: its key's length and, by exact power sums, its
    # key's exact order.
    for (n, m), h in v4.EXAMPLES.items():
        a = v4.from_hex(h, m)
        assert len(a) == n and v4.exact_order(a) == m, (n, m)


def q_configure():
    # Replicata: configure(304, 9); then configure(240, 12), which SETTINGS lacks.
    # Expectata: N, ORDER, CASCADE, CUTS and BUDGET from SETTINGS, the journal and log named for N and ORDER
    # next to overnight_v4.py; then AssertionError in configure.
    v4.configure(304, 9)
    assert (v4.N, v4.ORDER, (v4.CASCADE, v4.CUTS, v4.BUDGET)) == (304, 9, v4.SETTINGS[304, 9])
    assert v4.JOURNAL == os.path.join(HERE, 'overnight_304_9_journal.jsonl')
    assert v4.LOG == os.path.join(HERE, 'overnight_304_9.log')
    expect_assertion(lambda: v4.configure(240, 12), 'configure')


def q_configure_forgets_cached_results():
    # Replicata: moment rows, a lattice basis and an admissible set computed at 240@11, then again after
    # configure(304, 9), then again after configure(240, 11).
    # Expectata: each answer belongs to the N configured when it was asked for.
    v4.configure(240, 11)
    a = (v4.moment_rows(9), v4.lattice_basis(4, 8), v4.admissible(9, 3, ()))
    v4.configure(304, 9)
    b = (v4.moment_rows(9), v4.lattice_basis(4, 8), v4.admissible(9, 3, ()))
    v4.configure(240, 11)
    c = (v4.moment_rows(9), v4.lattice_basis(4, 8), v4.admissible(9, 3, ()))
    assert len(a[0][0][0]) == 240 and len(b[0][0][0]) == 304 and a == c
    assert a[1] != b[1] and a[2] != b[2]
    assert all(sum(w) == 152 for w in b[2]) and all(sum(w) == 120 for w in a[2])


def q_command_line():
    # Replicata: overnight_v4.py run with no arguments, and with 240 12 (no SETTINGS entry).
    # Expectata: each exits at once with AssertionError (the usage message, then the missing settings), and
    # leaves no journal or log behind.
    for args, words in (([], 'usage'), (['240', '12'], 'no settings for N = 240, order 12')):
        p = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'overnight_v4.py')] + args,
                           capture_output=True, text=True, timeout=300)
        assert p.returncode != 0 and 'AssertionError' in p.stderr and words in p.stderr, p.stderr[-600:]
    assert not any(os.path.exists(os.path.join(HERE, f)) for f in ('overnight_240_12_journal.jsonl', 'overnight_240_12.log'))


def q_v4_builds_v3_models_at_240_11():
    # Replicata: at 240@11, v3's and v4's code side by side.
    # Expectata: every function v3 fingerprints into CODE is textually identical in v4 except lattice_basis
    # (see q_lattice_rule); lattice bases agree for every modulus in play at orders 10 and 11; the CP-SAT models
    # of the top node, the open node, a pool node and a full count node are identical protos; the first four
    # splits agree.
    at(240, 11)
    names = ('add_lattice', 'moment_rows', 'count_rows', 'ExactSystem', 'integer_system', 'admissible', 'act',
             'stabilizer', 'rep', 'split', 'build_model', 'solve', 'solve_node', 'node_key', 'work', 'search')
    for name in names:
        assert inspect.getsource(getattr(v3, name)) == inspect.getsource(getattr(v4, name)), name
    for order in (10, 11):
        for M in sorted(set(v3.CASCADE + v3.CUTS)):
            assert v3.lattice_basis(M, order) == v4.lattice_basis(M, order), (order, M)
    pool = TOP4 + ((8, ((1, 1, 5, 5, 29, 29, 25, 25), (1, 1, 5, 13, 29, 29, 25, 17))),)
    for order, node in ((11, ()), (11, TOP4), (11, pool), (10, example_node(v3.CASCADE))):
        assert v3.build_model(order, node)[0].Proto() == v4.build_model(order, node)[0].Proto(), node
    node = ()
    for M in (3, 5, 7, 4):
        assert v3.split(11, node) == v4.split(11, node), M
        node = TOP4[:len(node) + 1]


# ---------- symmetry ----------

def q_group_action_on_counts():
    # Replicata: 40 random +-1 sequences; every g in G; every modulus in play.
    # Expectata: the counts of g(a) equal act(g, M, counts of a).
    at(240, 11)
    rng = random.Random(1)
    for _ in range(40):
        a = [rng.choice((1, -1)) for _ in range(v4.N)]
        for g in v4.GROUP:
            for M in sorted(set(v4.CASCADE + v4.CUTS + (2, 16))):
                assert v4.counts(v4.act_seq(g, a), M) == v4.act(g, M, v4.counts(a, M)), (g, M)


def q_group_preserves_order():
    # Replicata: the published example (a palindrome), and a non-palindromic sequence of order >= 4: a
    # Thue-Morse block of length 16 times a random +-1 pattern of length 15.
    # Expectata: every g in G preserves each one's exact order.
    at(240, 11)
    rng = random.Random(2)
    tm = [(-1) ** bin(i).count('1') for i in range(16)]
    h = [rng.choice((1, -1)) for _ in range(15)]
    u = [tm[i % 16] * h[i // 16] for i in range(v4.N)]
    assert u != u[::-1] and u != [-t for t in u[::-1]]
    assert v4.exact_order(EXAMPLE) == 10 and v4.exact_order(u) >= 4
    for a in (EXAMPLE, u):
        for g in v4.GROUP: assert v4.exact_order(v4.act_seq(g, a)) == v4.exact_order(a), g


def q_stabilizers():
    # Replicata: the top node; the open mod-4 node; that node with another mod-4 vector.
    # Expectata: all of G; id and phi (reverse and flip); id alone.
    at(240, 11)
    assert v4.stabilizer(()) == list(v4.GROUP)
    assert v4.stabilizer(TOP4) == [(0, 1), (1, -1)]
    assert v4.stabilizer(TOP4[:3] + ((4, ((14, 30, 46, 30),)),)) == [(0, 1)]


# ---------- residue lattices and admissible count vectors ----------

def q_lattice_basis_spans_generators():
    # Replicata: every modulus in the cascade and the cuts, at 240 (orders 10 and 11, both above log2 240) and at
    # 304 (order 8, where 304 >= 2^8, and order 9).  Generators: the cyclic shifts of (x-1)^order, times x+1
    # exactly when N < 2^order, reduced mod x^M - 1, built independently with sympy polynomials.
    # Expectata: the generators and lattice_basis's columns span the same lattice (each in the other's
    # span, tested with v2's independently written IntegerSystem).
    import overnight_240_v2 as v2
    for n, order in ((240, 10), (240, 11), (304, 8), (304, 9)):
        at(n, order + (n == 304 and order == 8))
        for M in sorted(set(v4.CASCADE + v4.CUTS)):
            gens = residue_lattice_gens(M, order, n < 2 ** order)
            B = v4.lattice_basis(M, order)
            in_basis = v2.IntegerSystem([list(row) for row in B])
            in_gens = v2.IntegerSystem([[g[r] for g in gens] for r in range(M)])
            assert all(in_basis.solvable(g) for g in gens), (n, order, M)
            assert all(in_gens.solvable([B[r][j] for r in range(M)]) for j in range(len(B[0]))), (n, order, M)


def q_lattice_rule():
    # Replicata: the sequence SIGNS_12_3 of length 12 = 3 * 4, order 3 and f(-1) = 8, so 12 >= 2^3 and its
    # f(x) = (x-1)^3 h(x) has h(-1) = -1; v4 at N = 12, then at N = 7.
    # Expectata: at N = 12 its residue vectors mod every M up to 16 lie in lattice_basis(M, 3), and for some M
    # they lie outside the lattice of (x-1)^3 (x+1), which v3 would have used; at N = 7 < 2^3, lattice_basis(M, 3)
    # spans the (x-1)^3 (x+1) lattice.
    import overnight_240_v2 as v2
    a = [1 if ch == '+' else -1 for ch in SIGNS_12_3]
    assert v4.exact_order(a) == 3 and sum((-1) ** p * t for p, t in enumerate(a)) == 8
    outside = []
    with length(12):
        for M in range(2, 17):
            d = [sum(a[p] for p in range(r, 12, M)) for r in range(M)]
            assert v4.ExactSystem(v4.lattice_basis(M, 3)).solvable(d), M
            gens = residue_lattice_gens(M, 3, 1)
            outside += [M] * (not v2.IntegerSystem([[g[r] for g in gens] for r in range(M)]).solvable(d))
    assert outside, outside
    with length(7):
        for M in range(2, 17):
            gens = residue_lattice_gens(M, 3, 1)
            B = v4.lattice_basis(M, 3)
            assert all(v4.ExactSystem(B).solvable(g) for g in gens), M
            assert all(v2.IntegerSystem([[g[r] for g in gens] for r in range(M)]).solvable([B[r][j] for r in range(M)])
                       for j in range(len(B[0]))), M


def q_forced_counts():
    # Replicata: order 11, moduli 3 and 5.  Expectata: one admissible vector each, the balanced one.
    at(240, 11)
    assert v4.admissible(11, 3, ()) == ((40, 40, 40),)
    assert v4.admissible(11, 5, ()) == ((24,) * 5,)


def q_admissible_sizes():
    # Regression: the counts found by v2 and by three independent agent recounts.
    at(240, 11)
    assert len(v4.admissible(11, 7, ())) == 4
    assert len(v4.admissible(11, 4, ())) == 9
    assert len(v4.admissible(11, 8, ((4, (30,) * 4),))) == 12769
    assert len(v4.admissible(11, 11, ())) == 12092
    assert len(v4.admissible(11, 13, ())) == 9748
    assert len(v4.admissible(11, 9, ((3, (40, 40, 40)),))) == 4626


def q_admissible_mod11_closed_form():
    # Replicata: order 11, modulus 11, against an independent characterization: (x-1)^11 = x^11 - 1
    # (mod 11) makes every d_r a multiple of 11; also 0 <= c_r <= size and the counts total 120.
    # Expectata: the same set as the enumerator's.
    at(240, 11)
    sizes = [v4.size(11, r) for r in range(11)]
    choices = [[c for c in range(s + 1) if (2 * c - s) % 11 == 0] for s in sizes]
    closed = tuple(sorted(c for c in itertools.product(*choices) if sum(c) == v4.N // 2))
    assert closed == v4.admissible(11, 11, ())


def q_admissible_matches_cpsat():
    # Replicata: several (N, order, modulus, class sums), enumerated by CP-SAT as well, including 304 at order
    # 8, where the lattice has no factor x+1.  Expectata: equal sets.
    at(240, 11)
    for order, M, fixed in ((11, 7, ()), (11, 4, ()), (11, 8, ((4, (30,) * 4),)), (11, 9, ((3, (40, 40, 40)),)),
                            (10, 7, ()), (10, 4, ()), (10, 8, ((4, (30,) * 4),))):
        assert v4.admissible(order, M, fixed) == cpsat_enumerate(order, M, fixed), (order, M, fixed)
    at(304, 9)
    for order, M, fixed in ((9, 3, ()), (9, 5, ()), (9, 4, ()), (9, 7, ()), (8, 3, ()), (8, 5, ()), (8, 4, ()),
                            (8, 8, ((4, (38,) * 4),))):
        assert v4.admissible(order, M, fixed) == cpsat_enumerate(order, M, fixed), (order, M, fixed)


def q_published_counts_admissible_order10():
    # Replicata: the published order-10 example.  Expectata: its counts are admissible at order 10 for
    # every cascade modulus, given its own counts modulo the earlier divisors.
    at(240, 11)
    for i, M in enumerate(v4.CASCADE):
        fixed = tuple((P, v4.counts(EXAMPLE, P)) for P in v4.CASCADE[:i] if M % P == 0)
        assert v4.counts(EXAMPLE, M) in v4.admissible(10, M, fixed), M


# ---------- the exact integer filter ----------

def q_exact_system_matches_v2():
    # Replicata: v2's two systems ((c4, c7) and (c7, c8)) and their count vectors.
    # Expectata: v4's ExactSystem, and its fiber shortcut, agree with v2's IntegerSystem on every vector,
    # with both answers occurring.
    import overnight_240_v2 as v2
    at(240, 11)
    rows, rhs = v4.moment_rows(11)
    A = rows + v4.count_rows(4) + v4.count_rows(7)
    old, new = v2.IntegerSystem(A), v4.ExactSystem(A)
    for c4 in v4.admissible(11, 4, ()):
        for c7 in v4.admissible(11, 7, ()):
            b = list(rhs) + list(c4) + list(c7)
            assert old.solvable(b) == new.solvable(b), (c4, c7)
    A = rows + v4.count_rows(7) + v4.count_rows(8)
    old, new = v2.IntegerSystem(A), v4.ExactSystem(A)
    head = list(rhs) + [21, 14, 31, 24, 17, 10, 3]
    ok = new.fiber(head)
    verdicts = []
    for c8 in v4.admissible(11, 8, ((4, (30,) * 4),))[::7]:
        verdicts.append(old.solvable(head + list(c8)))
        assert verdicts[-1] == new.solvable(head + list(c8)) == ok(c8), c8
    assert True in verdicts and False in verdicts


def q_fiber_rejects_wrong_length():
    # Replicata: the order-11 system with counts mod 3; vectors of length 4 and 2 instead of 3.
    # Expectata: ValueError from zip's strict check, not a silent answer.
    at(240, 11)
    ok = v4.integer_system(11, (3,)).fiber(v4.moment_rows(11)[1])
    assert ok((40, 40, 40))
    for bad in ((40, 40, 40, 99), (40, 40)):
        try:
            ok(bad)
        except ValueError:
            continue
        # TODO: error copy; says a vector of the wrong length was accepted by the integer filter
        raise AssertionError(f'Claude: "a vector of the wrong length was accepted: {bad}"')


def q_v2_case_numbers():
    # Regression: v2's exact filters recomputed with v4's machinery: 2 of the 18 (c4, c7) pairs survive;
    # 1024 of the 12769 mod-8 refinements survive for v2's open case.
    at(240, 11)
    rows, rhs = v4.moment_rows(11)
    S1 = v4.ExactSystem(rows + v4.count_rows(4) + v4.count_rows(7))
    c7s = [c for c in v4.admissible(11, 7, ()) if 2 * c[0] - v4.size(7, 0) >= 0]
    live = [(c4, c7) for c7 in c7s for c4 in v4.admissible(11, 4, ()) if S1.solvable(list(rhs) + list(c4) + list(c7))]
    assert len(c7s) * 9 == 18 and len(live) == 2 and all(c4 == (30,) * 4 for c4, _ in live)
    S2 = v4.ExactSystem(rows + v4.count_rows(7) + v4.count_rows(8))
    keep = [c8 for c8 in v4.admissible(11, 8, ((4, (30,) * 4),)) if S2.solvable(list(rhs) + [21, 14, 31, 24, 17, 10, 3] + list(c8))]
    assert len(keep) == 1024


# ---------- splitting ----------

def q_split_top_levels():
    # Replicata: the first four splits at order 11.
    # Expectata: mod 3 and mod 5 leave only the balanced vector (plus an empty pool); mod 7 leaves the two
    # orbit representatives; mod 4 leaves only (30, 30, 30, 30).
    at(240, 11)
    kids = v4.split(11, ())
    assert kids == [((3, ((40, 40, 40),)),), ((3, ()),)]
    kids = v4.split(11, kids[0])
    assert kids == [TOP4[:1] + ((5, ((24,) * 5,)),), TOP4[:1] + ((5, ()),)]
    kids = v4.split(11, kids[0])
    assert sorted(members(kids)) == [(0, 0, 24, 24, 24, 24, 24), C_STAR]
    kids = v4.split(11, TOP4[:3])
    assert members(kids) == [(30,) * 4]


def q_split_c8_level():
    # Replicata: the mod-8 split of the open node.
    # Expectata: 528 distinct vectors in all, each the representative under {id, phi} of one of the 1024
    # survivors of the exact filter; children of their own exactly for the LP-feasible ones, then one pool
    # of LP-infeasible ones.
    at(240, 11)
    kids = v4.split(11, TOP4)
    got = members(kids)
    assert len(got) == len(set(got)) == 528
    assert all(len(k[-1][1]) == 1 for k in kids[:-1])
    rows, rhs = v4.moment_rows(11)
    S = v4.ExactSystem(rows + sum((v4.count_rows(M) for M in (3, 5, 7, 4, 8)), ()))
    head = list(rhs) + [t for _, V in TOP4 for t in V[0]]
    full = [c8 for c8 in v4.admissible(11, 8, ((4, (30,) * 4),)) if S.solvable(head + list(c8))]
    assert len(full) == 1024
    gs = v4.stabilizer(TOP4)
    assert {v4.rep(gs, 8, c8) for c8 in full} == set(got)
    lp = v4.Relaxation(11, TOP4, 8)
    singles = [k[-1][1][0] for k in kids[:-1]]
    assert all(lp.check(v) for v in singles) and not any(lp.check(v) for v in kids[-1][-1][1])


def q_box_prefilter_keeps_feasible():
    # Replicata: 256 sampled mod-8 vectors of the open node.  Expectata: the box prefilter drops none of
    # the LP-feasible ones.
    at(240, 11)
    lp = v4.Relaxation(11, TOP4, 8)
    vecs = list(v4.admissible(11, 8, ((4, (30,) * 4),)))[::50]
    assert lp.feasible_set(vecs) == [v for v in vecs if lp.check(v)]


def q_feasible_set_early_return():
    # Replicata: a node whose own relaxation is infeasible: the open node plus one member of its mod-8 pool.
    # Expectata: feasible_set returns [] for all 12092 admissible mod-11 vectors.
    at(240, 11)
    v = v4.split(11, TOP4)[-1][-1][1][0]
    node = TOP4 + ((8, (v,)),)
    assert v4.Relaxation(11, node, 11).feasible_set(list(v4.admissible(11, 11, ()))) == []


class FakeGlop:
    """GLOP, except that Solve returns ABNORMAL whenever abnormal(i, status) holds for the i-th solve (from 0)
    and the status GLOP itself returned."""
    def __init__(self, abnormal):
        self.real, self.abnormal, self.calls, self.faked = pywraplp.Solver.CreateSolver('GLOP'), abnormal, 0, 0
    def __getattr__(self, name): return getattr(self.real, name)
    def Solve(self):
        st = self.real.Solve()
        i, self.calls = self.calls, self.calls + 1
        self.faked += bool(self.abnormal(i, st))
        return pywraplp.Solver.ABNORMAL if self.abnormal(i, st) else st


def fake_pywraplp(abnormal, made):
    """A stand-in for the pywraplp module whose GLOP solvers are FakeGlops (each appended to made)."""
    def create(name):
        assert name == 'GLOP'
        made.append(FakeGlop(abnormal))
        return made[-1]
    solver = types.SimpleNamespace(CreateSolver=create, OPTIMAL=pywraplp.Solver.OPTIMAL,
                                   INFEASIBLE=pywraplp.Solver.INFEASIBLE, ABNORMAL=pywraplp.Solver.ABNORMAL)
    return types.SimpleNamespace(Solver=solver)


LP_NODE = TOP4[:3]          # 240@11: the node whose mod-4 split the LP policy quals use (set below)


def q_lp_status_policy():
    # Replicata: the mod-8 split of the open node at 240@11 (528 vectors), with GLOP replaced by a fake that
    # returns ABNORMAL for (a) every solve, (b) the 16 bound solves, (c) every check GLOP itself found
    # INFEASIBLE, (d) the node's own solve; and v3's split under fake (a).
    # Expectata: a vector goes into the pool only if the LP proved it infeasible, by an INFEASIBLE status or by
    # lying outside the box of bounds that OPTIMAL bound solves set; any other status makes no claim, and the
    # vector gets its own child.  So (a) every vector has its own child and the pool is empty; (b) and (d)
    # give the real split; (c) gives own children exactly to the vectors inside the real box; every fake
    # actually returned ABNORMAL; and v3's split fails its status assertion in Relaxation.solve.
    at(240, 11)
    node, M = TOP4, 8
    real = v4.split(11, node)
    singles, pool = [k[-1][1][0] for k in real[:-1]], real[-1][-1][1]
    vecs = sorted(singles + list(pool))
    assert singles and pool
    lp = v4.Relaxation(11, node, M)
    assert lp.solve({}) == pywraplp.Solver.OPTIMAL
    lo = [lp.bound(r, 1) for r in range(M)]
    hi = [lp.bound(r, -1) for r in range(M)]
    inside = [v for v in vecs if all(lo[r] - v4.TOL <= v[r] <= hi[r] + v4.TOL for r in range(M))]
    assert len(singles) < len(inside) < len(vecs)
    def run(abnormal):
        made = []
        with patched(v4, pywraplp=fake_pywraplp(abnormal, made)):
            kids = v4.split(11, node)
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
    assert v4.split(11, TOP4 + ((8, (a, b, c)),)) == [TOP4 + ((8, (v,)),) for v in (a, b, c)]


def q_split_bottom():
    # Replicata: (a) a node with one vector per cascade modulus; (b) with the cascade cut to (3,), a pool
    # at the bottom.  Expectata: (a) no children; (b) still one child per member.
    at(240, 11)
    assert v4.split(10, example_node(v4.CASCADE)) == []
    pool = ((3, ((39, 41, 40), (40, 40, 40))),)
    with patched(v4, CASCADE=(3,)):
        assert v4.split(11, pool) == [((3, ((39, 41, 40),)),), ((3, ((40, 40, 40),)),)]


# ---------- CP-SAT models ----------

def q_empty_pool_is_infeasible():
    # Replicata: the open node plus an empty mod-8 pool.  Expectata: INFEASIBLE.
    at(240, 11)
    md, _ = v4.build_model(11, TOP4 + ((8, ()),))
    assert status_of(md) == 'INFEASIBLE'


def q_pool_model_admits_every_member():
    # Replicata: order 10; the published example's own counts for 3, 5, 7, 4, 8, 11 and 13, then a mod-9
    # pool whose second member is the example's counts; x pinned to the example.
    # Expectata: OPTIMAL (a model admitting only a pool's first member would say INFEASIBLE).
    at(240, 11)
    true9 = v4.counts(EXAMPLE, 9)
    other = v4.admissible(10, 9, ((3, v4.counts(EXAMPLE, 3)),))[0]
    assert other < true9
    node = example_node((3, 5, 7, 4, 8, 11, 13)) + ((9, (other, true9)),)
    md, _ = v4.build_model(10, node, fix=x01(EXAMPLE))
    assert status_of(md) == 'OPTIMAL'


def q_models_accept_example_at_order10_and_reject_it_at_order11():
    # Replicata: x pinned to the published example.  Expectata: its full count node at order 10 is
    # OPTIMAL; the top node at order 11 is INFEASIBLE.
    at(240, 11)
    md, _ = v4.build_model(10, example_node(v4.CASCADE), fix=x01(EXAMPLE))
    assert status_of(md) == 'OPTIMAL'
    md, _ = v4.build_model(11, (), fix=x01(EXAMPLE))
    assert status_of(md) == 'INFEASIBLE'


def q_solve_node_verdicts():
    # Replicata: (a) the top node at order 11 with a budget of 1; (b) an empty pool; (c) the top node at order 10 with
    # the model pinned to the published example.
    # Expectata: (a) UNKNOWN; (b) INFEASIBLE; (c) FEASIBLE with the example as its sequence.
    at(240, 11)
    assert v4.solve_node(11, (), 1)[0] == 'UNKNOWN'
    assert v4.solve_node(11, TOP4 + ((8, ()),), 20)[0] == 'INFEASIBLE'
    real = v4.build_model
    with patched(v4, build_model=lambda order, node, fix=(): real(order, node, fix=x01(EXAMPLE))):
        assert v4.solve_node(10, (), 20) == ('FEASIBLE', EXAMPLE)


def q_budget():
    # Replicata: the top node, a node at the bottom of the cascade, a pool of 12000 members.
    # Expectata: BUDGET by depth, with the bottom entry for the bottom, and POOL_BUDGET per pool member.
    at(240, 11)
    assert len(v4.BUDGET) == len(v4.CASCADE) + 1
    assert v4.node_budget(()) == v4.BUDGET[0]
    assert v4.node_budget(example_node(v4.CASCADE)) == v4.BUDGET[-1]
    pool = TOP4 + ((8, tuple((i,) * 8 for i in range(12000))),)
    assert v4.node_budget(pool) == max(v4.BUDGET[5], 12000 * v4.POOL_BUDGET)


def q_control():
    # Replicata: the startup control at 240@11.  Expectata: it returns.
    at(240, 11)
    v4.control()


def q_control_304_9():
    # Replicata: the startup control at 304@9, whose walk runs at order 8 with 304 >= 2^8.  Expectata: it returns.
    at(304, 9)
    v4.control()


# ---------- journal and keys ----------

def q_node_keys():
    # Replicata: the open node, two pools differing in one member, the top node.
    # Expectata: readable single-vector keys; pools keyed by size and full hash, distinct; '' for the top.
    at(240, 11)
    k1 = v4.node_key(TOP4)
    assert k1 == '3:[40,40,40] 5:[24,24,24,24,24] 7:[14,21,3,10,17,24,31] 4:[30,30,30,30]'
    k2 = v4.node_key(TOP4 + ((8, ((1,) * 8, (2,) * 8)),))
    k3 = v4.node_key(TOP4 + ((8, ((1,) * 8, (3,) * 8)),))
    assert k2.startswith(k1 + ' 8:#2:') and len(k2.split(':')[-1]) == 40 and k2 != k3
    assert v4.node_key(()) == ''


def journal_with(lines):
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'j.jsonl')
    with open(path, 'w') as fh:
        fh.write('\n'.join(json.dumps(x) for x in [v4.header()] + lines) + '\n')
    return path


def q_journal_header():
    # Replicata: (a) a journal written at order 11, reopened while the module's order is 10; (b) a journal
    # whose header carries another code fingerprint; (c) the header itself at 240@11 and at 304@9; (d) a 240@11
    # journal reopened at 304@9; (e) overnight_240_v3.py's own header.
    # Expectata: (a), (b), (d), (e) AssertionError from Journal's header check; (c) it pins the tag, N, the
    # order, the cuts and a 40-digit fingerprint.
    at(240, 11)
    path = journal_with([])
    with patched(v4, ORDER=10):
        expect_assertion(lambda: v4.Journal(path), '__init__')
    d = tempfile.mkdtemp()
    other = os.path.join(d, 'j.jsonl')
    open(other, 'w').write(json.dumps(dict(v4.header(), code='0' * 40)) + '\n')
    expect_assertion(lambda: v4.Journal(other), '__init__')
    h = v4.header()
    assert (h['tag'], h['N'], h['order'], h['cuts'], len(h['code'])) == ('overnight_v4', 240, 11, [27, 25, 32, 11, 13], 40)
    old = os.path.join(tempfile.mkdtemp(), 'j.jsonl')
    open(old, 'w').write(json.dumps(v3.header()) + '\n')
    expect_assertion(lambda: v4.Journal(old), '__init__')
    at(304, 9)
    h = v4.header()
    assert (h['tag'], h['N'], h['order'], h['cuts']) == ('overnight_v4', 304, 9, list(v4.SETTINGS[304, 9][1]))
    expect_assertion(lambda: v4.Journal(path), '__init__')


def q_journal_rejects_unknown_verdict_words():
    # Replicata: journals holding the verdict words OPTIMAL, FEASIBLE and a misspelling.
    # Expectata: AssertionError at load, so no such record can make a node vanish from the search.
    at(240, 11)
    for word in ('OPTIMAL', 'FEASIBLE', 'INFEASABLE'):
        path = journal_with([{'key': '', 'verdict': word, 'budget': 20}])
        expect_assertion(lambda: v4.Journal(path), 'admit')


def q_journal_supersession():
    # Replicata: two records for one key.
    # Expectata: after an UNKNOWN, a re-solve with a larger budget or a CLOSED is accepted (the later record
    # wins); a record after an INFEASIBLE or a CLOSED, or an UNKNOWN re-solve without a larger budget, is not.
    at(240, 11)
    for first, second in ((('UNKNOWN', 20), ('INFEASIBLE', 60)), (('UNKNOWN', 20), ('CLOSED', 20))):
        j = v4.Journal(journal_with([{'key': 'k', 'verdict': first[0], 'budget': first[1]},
                                     {'key': 'k', 'verdict': second[0], 'budget': second[1]}]))
        assert j.records['k']['verdict'] == second[0]
    for first, second in ((('INFEASIBLE', 20), ('UNKNOWN', 60)), (('CLOSED', 20), ('UNKNOWN', 60)),
                          (('UNKNOWN', 20), ('UNKNOWN', 20)), (('INFEASIBLE', 20), ('CLOSED', 20))):
        path = journal_with([{'key': 'k', 'verdict': first[0], 'budget': first[1]},
                             {'key': 'k', 'verdict': second[0], 'budget': second[1]}])
        expect_assertion(lambda: v4.Journal(path), 'admit')


def q_journal_reuse_rule():
    # Replicata: an UNKNOWN reached with budget 10, an INFEASIBLE with 5, a CLOSED.
    # Expectata: under a budget of 20 only INFEASIBLE and CLOSED are reused; under 10 all three are.
    at(240, 11)
    j = v4.Journal(journal_with([{'key': 'u', 'verdict': 'UNKNOWN', 'budget': 10},
                                 {'key': 'i', 'verdict': 'INFEASIBLE', 'budget': 5},
                                 {'key': 'c', 'verdict': 'CLOSED', 'budget': 1}]))
    assert (j.reuse('u', 20), j.reuse('i', 20), j.reuse('c', 20), j.reuse('new', 20)) == (None, 'INFEASIBLE', 'CLOSED', None)
    assert (j.reuse('u', 10), j.reuse('i', 10), j.reuse('c', 10)) == ('UNKNOWN', 'INFEASIBLE', 'CLOSED')


# ---------- the search, with a fake worker ----------

class SyncExecutor:
    """An executor that runs each task at once, in this process."""
    def submit(self, fn, *args):
        f = Future()
        f.set_result(fn(*args))
        return f


def fake_world(verdicts, splits):
    """A fake work(): verdicts[node] when solving, splits[node] (else the real split) for UNKNOWN's children.
    Returns the list of nodes it solved, and the patch."""
    calls, real = [], v4.split
    def work(order, node, budget, known, source):
        if known is None: calls.append(node)
        verdict = known or verdicts[node]
        children = (splits[node] if node in splits else real(order, node)) if verdict == 'UNKNOWN' else []
        return verdict, None, children, 0.0, 0.0
    return calls, dict(work=work)


def search(path, order=11):
    return v4.search(order, v4.Journal(path), lambda s: None, SyncExecutor())


def q_search_closes_tree_and_journals_it():
    # Replicata: the top node is UNKNOWN and splits into two INFEASIBLE children; then the same search again.
    # Expectata: 2 closed, nothing open, no witness, each node solved once (depth-first: the last child
    # first), the top journaled CLOSED; the second search solves and splits nothing, settling the top
    # from the journal (1 closed).
    at(240, 11)
    a, b = ((3, ((1,),)),), ((3, ((2,),)),)
    calls, fake = fake_world({(): 'UNKNOWN', a: 'INFEASIBLE', b: 'INFEASIBLE'}, {(): [a, b]})
    path = journal_with([])
    with patched(v4, CASCADE=(3, 5), BUDGET=(20, 20, 60), **fake):
        assert search(path) == {'closed': 2, 'open': [], 'witness': None, 'exact_order': None}
        assert calls == [(), b, a] and v4.Journal(path).records['']['verdict'] == 'CLOSED'
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
    with patched(v4, CASCADE=(3, 5), BUDGET=(20, 20, 60), **fake):
        res = search(path)
        assert res == {'closed': 1, 'open': [aa], 'witness': None, 'exact_order': None}
        assert 'CLOSED' not in [r['verdict'] for r in v4.Journal(path).records.values()]
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
    with patched(v4, CASCADE=(3,), BUDGET=(20, 60), **fake):
        assert search(journal_with([])) == {'closed': 2, 'open': [], 'witness': None, 'exact_order': None}


def q_search_witness_is_checked_exactly():
    # Replicata: a fake worker whose first verdict is FEASIBLE with the published order-10 example.
    # Expectata: at order 10 the search logs it at once and returns it as a witness of exact order 10,
    # journaling nothing; at order 11 the exact check in search() fails.
    at(240, 11)
    fake = dict(work=lambda order, node, budget, known, source: ('FEASIBLE', EXAMPLE, [], 0.0, 0.0))
    path = journal_with([])
    lines = []
    with patched(v4, **fake):
        res = v4.search(10, v4.Journal(path), lines.append, SyncExecutor())
        assert res['witness'] == EXAMPLE and res['exact_order'] == 10
        assert len(lines) == 1 and lines[0].startswith('Claude: "WITNESS FOUND') and 'exact order 10' in lines[0]
        assert len(open(path).read().splitlines()) == 1
        expect_assertion(lambda: search(journal_with([]), order=11), 'search')


def q_work_requires_the_same_source():
    # Replicata: work() told that the main process ran a different file.  Expectata: AssertionError in work.
    at(240, 11)
    expect_assertion(lambda: v4.work(11, (), 1, 'UNKNOWN', 'another file'), 'work')


def q_workers_are_configured():
    # Replicata: at 48@6, the real process pool that run() uses, with one process; work() on the top node with
    # a known UNKNOWN.
    # Expectata: the worker process splits the top node exactly as this process does (a worker left
    # unconfigured has N = None and fails).
    at(48, 6)
    with patched(v4, PROCESSES=1):
        with v4.make_executor() as ex:
            res = ex.submit(v4.work, 6, (), 1, 'UNKNOWN', v4.SOURCE).result()
    assert res[0] == 'UNKNOWN' and res[2] == v4.split(6, ())


def q_run_outcomes():
    # Replicata: run() with the control, journal, executor and search faked, for each kind of result.
    # Expectata: the closure line appears exactly when nothing is open and there is no witness.
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
        with patched(v4, control=lambda: None, Journal=FakeJournal, make_executor=FakeExecutor,
                     search=lambda order, journal, log, executor: res, log_to_file=lines.append):
            v4.run()
        text = '\n'.join(lines)
        assert ('ALL NODES CLOSED' in text) == (kind == 'closed'), (kind, text)
        assert ('NOT FINISHED' in text) == (kind == 'open'), (kind, text)
        assert ('WITNESS FOUND' in text) == (kind == 'witness'), (kind, text)


def q_sigint_finishes_solve_and_records_nothing():
    # Replicata: a child process runs the real search at 240@11 with one worker process and a budget of 100
    # deterministic-time units (tens of seconds); once the search has started, SIGINT goes to the whole
    # process group 5 s later, as Ctrl-C in a terminal does.
    # Expectata: the worker's solve still runs its full budget, KeyboardInterrupt ends the run, and the
    # journal holds only its header line.
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'j.jsonl')
    code = (f"import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {HERE!r})\n"
            f"import overnight_v4 as v4\n"
            f"if __name__ == '__main__':\n"
            f"    v4.configure(240, 11)\n"
            f"    v4.BUDGET = (100,) * len(v4.BUDGET); v4.PROCESSES = 1\n"
            f"    journal = v4.Journal({path!r})\n"
            f"    with v4.make_executor() as ex:\n"
            f"        print('SEARCHING', flush=True)\n"
            f"        v4.search(11, journal, print, ex)\n")
    script = os.path.join(d, 'child.py')
    open(script, 'w').write(code)
    p = subprocess.Popen([sys.executable, script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True)
    assert p.stdout.readline().strip() == 'SEARCHING'
    t0 = time.time()
    time.sleep(5)
    os.killpg(p.pid, 2)
    out, err = p.communicate(timeout=600)
    assert p.returncode != 0 and 'KeyboardInterrupt' in err, (p.returncode, err[-800:])
    assert time.time() - t0 >= 15, time.time() - t0
    assert len(open(path).read().splitlines()) == 1


# ---------- end to end: small configurations with answers known from Table 2 ----------

DRIVER = """import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {here!r})
import overnight_v4 as v4
if __name__ == '__main__':
    v4.configure({n}, {order})
    v4.JOURNAL, v4.LOG, v4.PROCESSES = {journal!r}, {log!r}, 2
    v4.run()
"""


def end_to_end(n, order):
    """A fresh run of overnight_v4 at (n, order) in a child process with two worker processes, its journal and
    log under RUNS; then a second run on the same journal.  Returns both logs' text and the journal's records."""
    os.makedirs(RUNS, exist_ok=True)
    journal, log = os.path.join(RUNS, f'overnight_{n}_{order}_journal.jsonl'), os.path.join(RUNS, f'overnight_{n}_{order}.log')
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


def check_witness_run(n, order):
    texts, records = end_to_end(n, order)
    for text in texts:
        assert f'startup control passed: the order-{order - 1} example of length {n}' in text, text[-2000:]
        assert 'NOT FINISHED' not in text and 'ALL NODES CLOSED' not in text, text[-2000:]
        line = [t for t in text.splitlines() if 'Claude: "WITNESS FOUND, exact order' in t]
        assert len(line) == 1, text[-2000:]
        X = set(json.loads(line[0].split('X = ')[1].rstrip('"')))
        a = [1 if p + 1 in X else -1 for p in range(n)]
        assert v4.exact_order(a) == order, line
    assert records[0]['N'] == n and records[0]['order'] == order


def check_closed_run(n, order):
    texts, records = end_to_end(n, order)
    for text in texts:
        assert f'startup control passed: the order-{order - 1} example of length {n}' in text, text[-2000:]
        assert 'ALL NODES CLOSED' in text and 'NOT FINISHED' not in text and 'WITNESS' not in text, text[-2000:]
    top = [r['verdict'] for r in records[1:] if r['key'] == '']
    assert top == ['UNKNOWN', 'CLOSED'], top
    assert '[1] {}: UNKNOWN' in texts[0] and '[' not in texts[1].split('startup control passed')[1].split('ALL NODES')[0]


def q_end_to_end_48_6_finds_a_witness():
    # Replicata: overnight_v4 at 48@6 (m*(48) = 6 in Table 2), its tiny SETTINGS budgets, run twice.
    # Expectata: each run passes its control and logs one witness whose X has exact order 6.
    check_witness_run(48, 6)


def q_end_to_end_96_7_finds_a_witness():
    # Replicata: overnight_v4 at 96@7 (m*(96) = 7), run twice.  Expectata: as for 48@6, exact order 7.
    check_witness_run(96, 7)


def q_end_to_end_40_6_closes():
    # Replicata: overnight_v4 at 40@6 (m*(40) = 5), run twice on one journal.
    # Expectata: each run passes its control and ends ALL NODES CLOSED; the top node was split (UNKNOWN, then
    # CLOSED in the journal); the second run solves no node, settling the top from the journal.
    check_closed_run(40, 6)


def q_end_to_end_56_6_closes():
    # Replicata: overnight_v4 at 56@6 (m*(56) = 5), run twice.  Expectata: as for 40@6.
    check_closed_run(56, 6)


def q_end_to_end_64_7_closes():
    # Replicata: overnight_v4 at 64@7 (m*(64) = 6; its control walks Thue-Morse at order 6, with 64 = 2^6),
    # run twice.  Expectata: as for 40@6.
    check_closed_run(64, 7)


def q_end_to_end_104_7_closes():
    # Replicata: overnight_v4 at 104@7 (m*(104) = 6), run twice.  Expectata: as for 40@6.
    check_closed_run(104, 7)


# ---------- runner ----------

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
