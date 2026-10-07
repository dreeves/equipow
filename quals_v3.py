#!/usr/bin/env python3
"""Quals for overnight_240_v3.py.  Run: python3 quals_v3.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the
resultata (what happened instead).  Quals marked "regression" pin numbers found independently earlier, by
v2 and by agent recounts, rather than stating a property.
"""
import sys
sys.dont_write_bytecode = True
import os, time, random, itertools, subprocess, tempfile, traceback, json
from concurrent.futures import Future
import sympy as sp
import overnight_240_v3 as v3
from ortools.sat.python import cp_model

HERE = os.path.dirname(os.path.abspath(__file__))
C_STAR = (14, 21, 3, 10, 17, 24, 31)          # v3's representative of the open mod-7 orbit (v2 used its R-image)
TOP4 = ((3, ((40, 40, 40),)), (5, ((24,) * 5,)), (7, (C_STAR,)), (4, ((30,) * 4,)))
EXAMPLE = v3.from_hex(v3.PUBLISHED_240_10, 10)


def x01(a): return [(t + 1) // 2 for t in a]
def members(children): return [v for c in children for v in c[-1][1]]
def status_of(md): return cp_model.CpSolver().StatusName(v3.solve(md, 120)[1])
def example_node(Ms): return tuple((M, (v3.counts(EXAMPLE, M),)) for M in Ms)


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


def patched(**kw):
    """Patch v3's globals for the duration of a with-block."""
    class P:
        def __enter__(self):
            self.saved = {k: getattr(v3, k) for k in kw}
            for k, val in kw.items(): setattr(v3, k, val)
        def __exit__(self, *exc):
            for k, val in self.saved.items(): setattr(v3, k, val)
    return P()


def cpsat_enumerate(order, M, fixed):
    """Independent enumeration of admissible count vectors with CP-SAT (v2's method, parent sums generalized)."""
    md = cp_model.CpModel()
    c = [md.NewIntVar(0, v3.size(M, r), f'c{r}') for r in range(M)]
    md.Add(sum(c) == v3.N // 2)
    v3.add_lattice(md, [2 * c[r] - v3.size(M, r) for r in range(M)], v3.lattice_basis(M, order), 'z')
    for P, w in fixed:
        for q in range(P): md.Add(sum(c[r] for r in range(q, M, P)) == w[q])
    out = []
    class Collect(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self): out.append(tuple(self.Value(t) for t in c))
    sv = cp_model.CpSolver(); sv.parameters.enumerate_all_solutions = True; sv.parameters.num_workers = 1
    assert sv.Solve(md, Collect()) == cp_model.OPTIMAL
    return tuple(sorted(set(out)))


# ---------- symmetry ----------

def q_group_action_on_counts():
    # Replicata: 40 random +-1 sequences; every g in G; every modulus in play.
    # Expectata: the counts of g(a) equal act(g, M, counts of a).
    rng = random.Random(1)
    for _ in range(40):
        a = [rng.choice((1, -1)) for _ in range(v3.N)]
        for g in v3.GROUP:
            for M in sorted(set(v3.CASCADE + v3.CUTS + (2, 16))):
                assert v3.counts(v3.act_seq(g, a), M) == v3.act(g, M, v3.counts(a, M)), (g, M)


def q_group_preserves_order():
    # Replicata: the published example (a palindrome), and a non-palindromic sequence of order >= 4: a
    # Thue-Morse block of length 16 times a random +-1 pattern of length 15.
    # Expectata: every g in G preserves each one's exact order.
    rng = random.Random(2)
    tm = [(-1) ** bin(i).count('1') for i in range(16)]
    h = [rng.choice((1, -1)) for _ in range(15)]
    u = [tm[i % 16] * h[i // 16] for i in range(v3.N)]
    assert u != u[::-1] and u != [-t for t in u[::-1]]
    assert v3.exact_order(EXAMPLE) == 10 and v3.exact_order(u) >= 4
    for a in (EXAMPLE, u):
        for g in v3.GROUP: assert v3.exact_order(v3.act_seq(g, a)) == v3.exact_order(a), g


def q_stabilizers():
    # Replicata: the top node; the open mod-4 node; that node with another mod-4 vector.
    # Expectata: all of G; id and phi (reverse and flip); id alone.
    assert v3.stabilizer(()) == list(v3.GROUP)
    assert v3.stabilizer(TOP4) == [(0, 1), (1, -1)]
    assert v3.stabilizer(TOP4[:3] + ((4, ((14, 30, 46, 30),)),)) == [(0, 1)]


# ---------- residue lattices and admissible count vectors ----------

def q_lattice_basis_spans_generators():
    # Replicata: every modulus in the cascade and the cuts, at orders 10 and 11.  Generators: the cyclic
    # shifts of (x-1)^order (x+1) reduced mod x^M - 1, built independently with sympy polynomials.
    # Expectata: the generators and lattice_basis's columns span the same lattice (each in the other's
    # span, tested with v2's independently written IntegerSystem).
    import overnight_240_v2 as v2
    x = sp.symbols('x')
    for order in (10, 11):
        for M in sorted(set(v3.CASCADE + v3.CUTS)):
            p = sp.Poly((x - 1) ** order * (x + 1), x)
            gens = []
            for k in range(M):
                r = sp.Poly(sp.rem(x ** k * p.as_expr(), x ** M - 1, x), x)
                gens.append([int(r.coeff_monomial(x ** i)) for i in range(M)])
            B = v3.lattice_basis(M, order)
            in_basis = v2.IntegerSystem([list(row) for row in B])
            in_gens = v2.IntegerSystem([[g[r] for g in gens] for r in range(M)])
            assert all(in_basis.solvable(g) for g in gens), (order, M)
            assert all(in_gens.solvable([B[r][j] for r in range(M)]) for j in range(len(B[0]))), (order, M)


def q_forced_counts():
    # Replicata: order 11, moduli 3 and 5.  Expectata: one admissible vector each, the balanced one.
    assert v3.admissible(11, 3, ()) == ((40, 40, 40),)
    assert v3.admissible(11, 5, ()) == ((24,) * 5,)


def q_admissible_sizes():
    # Regression: the counts found by v2 and by three independent agent recounts.
    assert len(v3.admissible(11, 7, ())) == 4
    assert len(v3.admissible(11, 4, ())) == 9
    assert len(v3.admissible(11, 8, ((4, (30,) * 4),))) == 12769
    assert len(v3.admissible(11, 11, ())) == 12092
    assert len(v3.admissible(11, 13, ())) == 9748
    assert len(v3.admissible(11, 9, ((3, (40, 40, 40)),))) == 4626


def q_admissible_mod11_closed_form():
    # Replicata: order 11, modulus 11, against an independent characterization: (x-1)^11 = x^11 - 1
    # (mod 11) makes every d_r a multiple of 11; also 0 <= c_r <= size and the counts total 120.
    # Expectata: the same set as the enumerator's.
    sizes = [v3.size(11, r) for r in range(11)]
    choices = [[c for c in range(s + 1) if (2 * c - s) % 11 == 0] for s in sizes]
    closed = tuple(sorted(c for c in itertools.product(*choices) if sum(c) == v3.N // 2))
    assert closed == v3.admissible(11, 11, ())


def q_admissible_matches_cpsat():
    # Replicata: several (order, modulus, class sums), enumerated by CP-SAT as well.  Expectata: equal sets.
    for order, M, fixed in ((11, 7, ()), (11, 4, ()), (11, 8, ((4, (30,) * 4),)), (11, 9, ((3, (40, 40, 40)),)),
                            (10, 7, ()), (10, 4, ()), (10, 8, ((4, (30,) * 4),))):
        assert v3.admissible(order, M, fixed) == cpsat_enumerate(order, M, fixed), (order, M, fixed)


def q_published_counts_admissible_order10():
    # Replicata: the published order-10 example.  Expectata: its counts are admissible at order 10 for
    # every cascade modulus, given its own counts modulo the earlier divisors.
    for i, M in enumerate(v3.CASCADE):
        fixed = tuple((P, v3.counts(EXAMPLE, P)) for P in v3.CASCADE[:i] if M % P == 0)
        assert v3.counts(EXAMPLE, M) in v3.admissible(10, M, fixed), M


# ---------- the exact integer filter ----------

def q_exact_system_matches_v2():
    # Replicata: v2's two systems ((c4, c7) and (c7, c8)) and their count vectors.
    # Expectata: v3's ExactSystem, and its fiber shortcut, agree with v2's IntegerSystem on every vector,
    # with both answers occurring.
    import overnight_240_v2 as v2
    rows, rhs = v3.moment_rows(11)
    A = rows + v3.count_rows(4) + v3.count_rows(7)
    old, new = v2.IntegerSystem(A), v3.ExactSystem(A)
    for c4 in v3.admissible(11, 4, ()):
        for c7 in v3.admissible(11, 7, ()):
            b = list(rhs) + list(c4) + list(c7)
            assert old.solvable(b) == new.solvable(b), (c4, c7)
    A = rows + v3.count_rows(7) + v3.count_rows(8)
    old, new = v2.IntegerSystem(A), v3.ExactSystem(A)
    head = list(rhs) + [21, 14, 31, 24, 17, 10, 3]
    ok = new.fiber(head)
    verdicts = []
    for c8 in v3.admissible(11, 8, ((4, (30,) * 4),))[::7]:
        verdicts.append(old.solvable(head + list(c8)))
        assert verdicts[-1] == new.solvable(head + list(c8)) == ok(c8), c8
    assert True in verdicts and False in verdicts


def q_fiber_rejects_wrong_length():
    # Replicata: the order-11 system with counts mod 3; vectors of length 4 and 2 instead of 3.
    # Expectata: ValueError from zip's strict check, not a silent answer.
    ok = v3.integer_system(11, (3,)).fiber(v3.moment_rows(11)[1])
    assert ok((40, 40, 40))
    for bad in ((40, 40, 40, 99), (40, 40)):
        try:
            ok(bad)
        except ValueError:
            continue
        # TODO: error copy; says a vector of the wrong length was accepted by the integer filter
        raise AssertionError(f'Claude: "a vector of the wrong length was accepted: {bad}"')


def q_v2_case_numbers():
    # Regression: v2's exact filters recomputed with v3's machinery: 2 of the 18 (c4, c7) pairs survive;
    # 1024 of the 12769 mod-8 refinements survive for v2's open case.
    rows, rhs = v3.moment_rows(11)
    S1 = v3.ExactSystem(rows + v3.count_rows(4) + v3.count_rows(7))
    c7s = [c for c in v3.admissible(11, 7, ()) if 2 * c[0] - v3.size(7, 0) >= 0]
    live = [(c4, c7) for c7 in c7s for c4 in v3.admissible(11, 4, ()) if S1.solvable(list(rhs) + list(c4) + list(c7))]
    assert len(c7s) * 9 == 18 and len(live) == 2 and all(c4 == (30,) * 4 for c4, _ in live)
    S2 = v3.ExactSystem(rows + v3.count_rows(7) + v3.count_rows(8))
    keep = [c8 for c8 in v3.admissible(11, 8, ((4, (30,) * 4),)) if S2.solvable(list(rhs) + [21, 14, 31, 24, 17, 10, 3] + list(c8))]
    assert len(keep) == 1024


# ---------- splitting ----------

def q_split_top_levels():
    # Replicata: the first four splits at order 11.
    # Expectata: mod 3 and mod 5 leave only the balanced vector (plus an empty pool); mod 7 leaves the two
    # orbit representatives; mod 4 leaves only (30, 30, 30, 30).
    kids = v3.split(11, ())
    assert kids == [((3, ((40, 40, 40),)),), ((3, ()),)]
    kids = v3.split(11, kids[0])
    assert kids == [TOP4[:1] + ((5, ((24,) * 5,)),), TOP4[:1] + ((5, ()),)]
    kids = v3.split(11, kids[0])
    assert sorted(members(kids)) == [(0, 0, 24, 24, 24, 24, 24), C_STAR]
    kids = v3.split(11, TOP4[:3])
    assert members(kids) == [(30,) * 4]


def q_split_c8_level():
    # Replicata: the mod-8 split of the open node.
    # Expectata: 528 distinct vectors in all, each the representative under {id, phi} of one of the 1024
    # survivors of the exact filter; children of their own exactly for the LP-feasible ones, then one pool
    # of LP-infeasible ones.
    kids = v3.split(11, TOP4)
    got = members(kids)
    assert len(got) == len(set(got)) == 528
    assert all(len(k[-1][1]) == 1 for k in kids[:-1])
    rows, rhs = v3.moment_rows(11)
    S = v3.ExactSystem(rows + sum((v3.count_rows(M) for M in (3, 5, 7, 4, 8)), ()))
    head = list(rhs) + [t for _, V in TOP4 for t in V[0]]
    full = [c8 for c8 in v3.admissible(11, 8, ((4, (30,) * 4),)) if S.solvable(head + list(c8))]
    assert len(full) == 1024
    gs = v3.stabilizer(TOP4)
    assert {v3.rep(gs, 8, c8) for c8 in full} == set(got)
    lp = v3.Relaxation(11, TOP4, 8)
    singles = [k[-1][1][0] for k in kids[:-1]]
    assert all(lp.check(v) for v in singles) and not any(lp.check(v) for v in kids[-1][-1][1])


def q_box_prefilter_keeps_feasible():
    # Replicata: 256 sampled mod-8 vectors of the open node.  Expectata: the box prefilter drops none of
    # the LP-feasible ones.
    lp = v3.Relaxation(11, TOP4, 8)
    vecs = list(v3.admissible(11, 8, ((4, (30,) * 4),)))[::50]
    assert lp.feasible_set(vecs) == [v for v in vecs if lp.check(v)]


def q_feasible_set_early_return():
    # Replicata: a node whose own relaxation is infeasible: the open node plus one member of its mod-8 pool.
    # Expectata: feasible_set returns [] for all 12092 admissible mod-11 vectors.
    v = v3.split(11, TOP4)[-1][-1][1][0]
    node = TOP4 + ((8, (v,)),)
    assert v3.Relaxation(11, node, 11).feasible_set(list(v3.admissible(11, 11, ()))) == []


def q_pool_splits_into_members():
    # Replicata: a pool of three mod-8 vectors.  Expectata: three children, one per member, in order.
    a, b, c = (1, 1, 5, 5, 29, 29, 25, 25), (1, 1, 5, 13, 29, 29, 25, 17), (1, 1, 5, 21, 29, 29, 25, 9)
    assert v3.split(11, TOP4 + ((8, (a, b, c)),)) == [TOP4 + ((8, (v,)),) for v in (a, b, c)]


def q_split_bottom():
    # Replicata: (a) a node with one vector per cascade modulus; (b) with the cascade cut to (3,), a pool
    # at the bottom.  Expectata: (a) no children; (b) still one child per member.
    assert v3.split(10, example_node(v3.CASCADE)) == []
    pool = ((3, ((39, 41, 40), (40, 40, 40))),)
    with patched(CASCADE=(3,)):
        assert v3.split(11, pool) == [((3, ((39, 41, 40),)),), ((3, ((40, 40, 40),)),)]


# ---------- CP-SAT models ----------

def q_empty_pool_is_infeasible():
    # Replicata: the open node plus an empty mod-8 pool.  Expectata: INFEASIBLE.
    md, _ = v3.build_model(11, TOP4 + ((8, ()),))
    assert status_of(md) == 'INFEASIBLE'


def q_pool_model_admits_every_member():
    # Replicata: order 10; the published example's own counts for 3, 5, 7, 4, 8, 11 and 13, then a mod-9
    # pool whose second member is the example's counts; x pinned to the example.
    # Expectata: OPTIMAL (a model admitting only a pool's first member would say INFEASIBLE).
    true9 = v3.counts(EXAMPLE, 9)
    other = v3.admissible(10, 9, ((3, v3.counts(EXAMPLE, 3)),))[0]
    assert other < true9
    node = example_node((3, 5, 7, 4, 8, 11, 13)) + ((9, (other, true9)),)
    md, _ = v3.build_model(10, node, fix=x01(EXAMPLE))
    assert status_of(md) == 'OPTIMAL'


def q_models_accept_example_at_order10_and_reject_it_at_order11():
    # Replicata: x pinned to the published example.  Expectata: its full count node at order 10 is
    # OPTIMAL; the top node at order 11 is INFEASIBLE.
    md, _ = v3.build_model(10, example_node(v3.CASCADE), fix=x01(EXAMPLE))
    assert status_of(md) == 'OPTIMAL'
    md, _ = v3.build_model(11, (), fix=x01(EXAMPLE))
    assert status_of(md) == 'INFEASIBLE'


def q_solve_node_verdicts():
    # Replicata: (a) the top node at order 11 with a budget of 1; (b) an empty pool; (c) the top node at order 10 with
    # the model pinned to the published example.
    # Expectata: (a) UNKNOWN; (b) INFEASIBLE; (c) FEASIBLE with the example as its sequence.
    assert v3.solve_node(11, (), 1)[0] == 'UNKNOWN'
    assert v3.solve_node(11, TOP4 + ((8, ()),), 20)[0] == 'INFEASIBLE'
    real = v3.build_model
    with patched(build_model=lambda order, node, fix=(): real(order, node, fix=x01(EXAMPLE))):
        assert v3.solve_node(10, (), 20) == ('FEASIBLE', EXAMPLE)


def q_budget():
    # Replicata: the top node, a node at the bottom of the cascade, a pool of 12000 members.
    # Expectata: BUDGET by depth, with the bottom entry for the bottom, and POOL_BUDGET per pool member.
    assert len(v3.BUDGET) == len(v3.CASCADE) + 1
    assert v3.node_budget(()) == v3.BUDGET[0]
    assert v3.node_budget(example_node(v3.CASCADE)) == v3.BUDGET[-1]
    pool = TOP4 + ((8, tuple((i,) * 8 for i in range(12000))),)
    assert v3.node_budget(pool) == max(v3.BUDGET[5], 12000 * v3.POOL_BUDGET)


def q_control():
    # Replicata: the startup control.  Expectata: it returns.
    v3.control()


# ---------- journal and keys ----------

def q_node_keys():
    # Replicata: the open node, two pools differing in one member, the top node.
    # Expectata: readable single-vector keys; pools keyed by size and full hash, distinct; '' for the top.
    k1 = v3.node_key(TOP4)
    assert k1 == '3:[40,40,40] 5:[24,24,24,24,24] 7:[14,21,3,10,17,24,31] 4:[30,30,30,30]'
    k2 = v3.node_key(TOP4 + ((8, ((1,) * 8, (2,) * 8)),))
    k3 = v3.node_key(TOP4 + ((8, ((1,) * 8, (3,) * 8)),))
    assert k2.startswith(k1 + ' 8:#2:') and len(k2.split(':')[-1]) == 40 and k2 != k3
    assert v3.node_key(()) == ''


def journal_with(lines):
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'j.jsonl')
    with open(path, 'w') as fh:
        fh.write('\n'.join(json.dumps(x) for x in [v3.header()] + lines) + '\n')
    return path


def q_journal_header():
    # Replicata: (a) a journal written at order 11, reopened while the module's order is 10; (b) a journal
    # whose header carries another code fingerprint; (c) the header itself.
    # Expectata: (a), (b) AssertionError from Journal's header check; (c) it pins N, the order, the cuts and
    # a 40-digit fingerprint.
    path = journal_with([])
    with patched(ORDER=10):
        expect_assertion(lambda: v3.Journal(path), '__init__')
    d = tempfile.mkdtemp()
    other = os.path.join(d, 'j.jsonl')
    open(other, 'w').write(json.dumps(dict(v3.header(), code='0' * 40)) + '\n')
    expect_assertion(lambda: v3.Journal(other), '__init__')
    h = v3.header()
    assert (h['N'], h['order'], h['cuts'], len(h['code'])) == (240, 11, [27, 25, 32, 11, 13], 40)


def q_journal_rejects_unknown_verdict_words():
    # Replicata: journals holding the verdict words OPTIMAL, FEASIBLE and a misspelling.
    # Expectata: AssertionError at load, so no such record can make a node vanish from the search.
    for word in ('OPTIMAL', 'FEASIBLE', 'INFEASABLE'):
        path = journal_with([{'key': '', 'verdict': word, 'budget': 20}])
        expect_assertion(lambda: v3.Journal(path), 'admit')


def q_journal_supersession():
    # Replicata: two records for one key.
    # Expectata: after an UNKNOWN, a re-solve with a larger budget or a CLOSED is accepted (the later record
    # wins); a record after an INFEASIBLE or a CLOSED, or an UNKNOWN re-solve without a larger budget, is not.
    for first, second in ((('UNKNOWN', 20), ('INFEASIBLE', 60)), (('UNKNOWN', 20), ('CLOSED', 20))):
        j = v3.Journal(journal_with([{'key': 'k', 'verdict': first[0], 'budget': first[1]},
                                     {'key': 'k', 'verdict': second[0], 'budget': second[1]}]))
        assert j.records['k']['verdict'] == second[0]
    for first, second in ((('INFEASIBLE', 20), ('UNKNOWN', 60)), (('CLOSED', 20), ('UNKNOWN', 60)),
                          (('UNKNOWN', 20), ('UNKNOWN', 20)), (('INFEASIBLE', 20), ('CLOSED', 20))):
        path = journal_with([{'key': 'k', 'verdict': first[0], 'budget': first[1]},
                             {'key': 'k', 'verdict': second[0], 'budget': second[1]}])
        expect_assertion(lambda: v3.Journal(path), 'admit')


def q_journal_reuse_rule():
    # Replicata: an UNKNOWN reached with budget 10, an INFEASIBLE with 5, a CLOSED.
    # Expectata: under a budget of 20 only INFEASIBLE and CLOSED are reused; under 10 all three are.
    j = v3.Journal(journal_with([{'key': 'u', 'verdict': 'UNKNOWN', 'budget': 10},
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
    calls, real = [], v3.split
    def work(order, node, budget, known, source):
        if known is None: calls.append(node)
        verdict = known or verdicts[node]
        children = (splits[node] if node in splits else real(order, node)) if verdict == 'UNKNOWN' else []
        return verdict, None, children, 0.0, 0.0
    return calls, dict(work=work)


def search(path, order=11):
    return v3.search(order, v3.Journal(path), lambda s: None, SyncExecutor())


def q_search_closes_tree_and_journals_it():
    # Replicata: the top node is UNKNOWN and splits into two INFEASIBLE children; then the same search again.
    # Expectata: 2 closed, nothing open, no witness, each node solved once (depth-first: the last child
    # first), the top journaled CLOSED; the second search solves and splits nothing, settling the top
    # from the journal (1 closed).
    a, b = ((3, ((1,),)),), ((3, ((2,),)),)
    calls, fake = fake_world({(): 'UNKNOWN', a: 'INFEASIBLE', b: 'INFEASIBLE'}, {(): [a, b]})
    path = journal_with([])
    with patched(CASCADE=(3, 5), BUDGET=(20, 20, 60), **fake):
        assert search(path) == {'closed': 2, 'open': [], 'witness': None, 'exact_order': None}
        assert calls == [(), b, a] and v3.Journal(path).records['']['verdict'] == 'CLOSED'
        calls.clear()
        assert search(path) == {'closed': 1, 'open': [], 'witness': None, 'exact_order': None} and calls == []


def q_search_reports_open_leaves_and_reuses_journal():
    # Replicata: cascade (3, 5); an UNKNOWN chain down to the bottom, with one INFEASIBLE sibling; then the
    # same search again on the same journal.
    # Expectata: the bottom node is the one open leaf, nothing is journaled CLOSED; the second search solves
    # nothing and reports the same.
    a = ((3, ((1,),)),)
    aa, ab = a + ((5, ((7,),)),), a + ((5, ((8,),)),)
    calls, fake = fake_world({(): 'UNKNOWN', a: 'UNKNOWN', aa: 'UNKNOWN', ab: 'INFEASIBLE'}, {(): [a], a: [aa, ab], aa: []})
    path = journal_with([])
    with patched(CASCADE=(3, 5), BUDGET=(20, 20, 60), **fake):
        res = search(path)
        assert res == {'closed': 1, 'open': [aa], 'witness': None, 'exact_order': None}
        assert 'CLOSED' not in [r['verdict'] for r in v3.Journal(path).records.values()]
        calls.clear()
        assert search(path) == res and calls == []


def q_search_splits_pool_at_bottom():
    # Replicata: cascade (3,); the top node is UNKNOWN and (fake) splits into a two-member pool that is
    # UNKNOWN; the real split then gives its members, both INFEASIBLE.
    # Expectata: 2 closed, nothing open: a pool at the bottom is not an open leaf.
    va, vb = (39, 41, 40), (40, 40, 40)
    pool = ((3, (va, vb)),)
    calls, fake = fake_world({(): 'UNKNOWN', pool: 'UNKNOWN', ((3, (va,)),): 'INFEASIBLE', ((3, (vb,)),): 'INFEASIBLE'},
                             {(): [pool]})
    with patched(CASCADE=(3,), BUDGET=(20, 60), **fake):
        assert search(journal_with([])) == {'closed': 2, 'open': [], 'witness': None, 'exact_order': None}


def q_search_witness_is_checked_exactly():
    # Replicata: a fake worker whose first verdict is FEASIBLE with the published order-10 example.
    # Expectata: at order 10 the search logs it at once and returns it as a witness of exact order 10,
    # journaling nothing; at order 11 the exact check in search() fails.
    fake = dict(work=lambda order, node, budget, known, source: ('FEASIBLE', EXAMPLE, [], 0.0, 0.0))
    path = journal_with([])
    lines = []
    with patched(**fake):
        res = v3.search(10, v3.Journal(path), lines.append, SyncExecutor())
        assert res['witness'] == EXAMPLE and res['exact_order'] == 10
        assert len(lines) == 1 and lines[0].startswith('Claude: "WITNESS FOUND') and 'exact order 10' in lines[0]
        assert len(open(path).read().splitlines()) == 1
        expect_assertion(lambda: search(journal_with([]), order=11), 'search')


def q_work_requires_the_same_source():
    # Replicata: work() told that the main process ran a different file.  Expectata: AssertionError in work.
    expect_assertion(lambda: v3.work(11, (), 1, 'UNKNOWN', 'another file'), 'work')


def q_main_outcomes():
    # Replicata: main() with the control, journal, executor and search faked, for each kind of result.
    # Expectata: the closure line appears exactly when nothing is open and there is no witness.
    shapes = {'closed': {'closed': 5, 'open': [], 'witness': None, 'exact_order': None},
              'open': {'closed': 4, 'open': [((3, ((1,),)),)], 'witness': None, 'exact_order': None},
              'witness': {'closed': 0, 'open': [], 'witness': EXAMPLE, 'exact_order': 12}}
    class FakeJournal:
        records = {}
        def __init__(self, path): pass
    class FakeExecutor:
        def __init__(self, n): pass
        def __enter__(self): return self
        def __exit__(self, *exc): pass
    for kind, res in shapes.items():
        lines = []
        with patched(control=lambda: None, Journal=FakeJournal, ProcessPoolExecutor=FakeExecutor,
                     search=lambda order, journal, log, executor: res, log_to_file=lines.append):
            v3.main()
        text = '\n'.join(lines)
        assert ('ALL NODES CLOSED' in text) == (kind == 'closed'), (kind, text)
        assert ('NOT FINISHED' in text) == (kind == 'open'), (kind, text)
        assert ('WITNESS FOUND' in text) == (kind == 'witness'), (kind, text)


def q_sigint_finishes_solve_and_records_nothing():
    # Replicata: a child process runs the real search with one worker process and a budget of 100
    # deterministic-time units (tens of seconds); once the search has started, SIGINT goes to the whole
    # process group 5 s later, as Ctrl-C in a terminal does.
    # Expectata: the worker's solve still runs its full budget, KeyboardInterrupt ends the run, and the
    # journal holds only its header line.
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'j.jsonl')
    code = (f"import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {HERE!r})\n"
            f"import overnight_240_v3 as v3\n"
            f"from concurrent.futures import ProcessPoolExecutor\n"
            f"if __name__ == '__main__':\n"
            f"    v3.BUDGET = (100,) * len(v3.BUDGET); v3.PROCESSES = 1\n"
            f"    journal = v3.Journal({path!r})\n"
            f"    with ProcessPoolExecutor(1) as ex:\n"
            f"        print('SEARCHING', flush=True)\n"
            f"        v3.search(11, journal, print, ex)\n")
    script = os.path.join(d, 'child.py')
    open(script, 'w').write(code)
    p = subprocess.Popen([sys.executable, script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True)
    assert p.stdout.readline().strip() == 'SEARCHING'
    t0 = time.time()
    time.sleep(5)
    os.killpg(p.pid, 2)
    out, err = p.communicate(timeout=180)
    assert p.returncode != 0 and 'KeyboardInterrupt' in err, (p.returncode, err[-800:])
    assert time.time() - t0 >= 15, time.time() - t0
    assert len(open(path).read().splitlines()) == 1


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
