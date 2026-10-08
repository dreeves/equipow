#!/usr/bin/env python3
"""N in L_ORDER?  Version 4: the count-vector cube-and-conquer of overnight_240_v3.py, for any length N and order.

The question, from Buhler, Golan, Pratt and Wagon, Math. Comp. 90 (2021) 1435-1453, Table 2: is there a +-1
sequence a_0..a_{N-1} whose power sums sum_p a_p p^k vanish for k = 0..ORDER-1, that is, of order at least ORDER?

Vocabulary used throughout this file, each term defined once here:
  order          the number of leading exponents k = 0, 1, ... whose power sums vanish.
  size(M, r)     the number of positions p in 0..N-1 with p = r (mod M).
  counts mod M   c_r = the number of +1's at positions p = r (mod M), for r = 0..M-1.
  admissible     a count vector mod M with 0 <= c_r <= size(M, r), whose differences d = 2c - size lie in
                 the residue lattice of the order (see lattice_basis), and whose class sums match the counts
                 already fixed modulo any divisor of M.  Every sequence of the given order has admissible
                 counts.
  node           the sequences whose counts mod M lie in V_M for each pair (M, V_M) of a tuple of
                 constraints; a vertex of the search tree.  The top node is the empty tuple.
  pool           the one child of a split holding every vector whose LP relaxation is infeasible (perhaps
                 none, perhaps one), so that a single CP-SAT run can close them all.  A pool with more than
                 one member splits into one child per member.
  split          the children of a node with verdict UNKNOWN: a pool's members, as above; otherwise, by the
                 next cascade modulus M, the admissible vectors mod M that pass the exact integer filter,
                 reduced to one per orbit of the node's stabilizer, each with a child of its own when its LP
                 relaxation is feasible and the rest in one pool.  At the bottom of the cascade, none.
  cascade        the moduli used for splitting, in order.
  G              the symmetries of the problem, written (reverse, sign): R reverses positions, F flips
                 signs, phi = RF.  All of them preserve the order.
  stabilizer     the elements of G that map a node onto itself; rep(gs, M, v) is the least image of v
                 under them.
  budget         a node's CP-SAT limit in deterministic time (CP-SAT's own measure of work, roughly 2.2 per
                 CPU-second here, and unaffected by other load on the machine): BUDGET[depth], longer at the
                 bottom of the cascade, and for a pool at least POOL_BUDGET per member (about what splitting it
                 into members would cost).
  verdict        CP-SAT's result for a node: INFEASIBLE (closed), UNKNOWN (no result within the budget), or
                 FEASIBLE with a sequence.  The journal also records CLOSED for a node whose children's
                 subtrees are all closed, so a resumed run skips it.
  witness        a FEASIBLE sequence whose order, checked with exact power sums, is at least the target.
  open leaf      a node with verdict UNKNOWN and no children.
  control        the startup check that a known example of order ORDER-1 and length N (from EXAMPLES)
                 survives every step of the search at order ORDER-1.

Search: depth-first from the top node, PROCESSES nodes at a time, each in its own process (which solves the
node and, for UNKNOWN, splits it); the main process keeps the tree and the journal.

Soundness: the run shows that no sequence of order at least ORDER exists exactly when it ends with no open
leaf and no witness.  Each node closes by a CP-SAT INFEASIBLE verdict, the one non-exact step.  Enumeration,
the integer filter and the symmetry reduction are exact integer arithmetic; the LP only groups children.

Changes from overnight_240_v3.py, which this file reproduces at N = 240, ORDER = 11 (quals_v4.py checks that the
two build the same CP-SAT models and the same splits there):
  - N and ORDER come from the command line, and CASCADE, CUTS and BUDGET from SETTINGS[(N, ORDER)].
  - The residue lattices keep the factor x+1 only when N < 2^order (lattice_poly).  v3 asserted N < 2^order,
    which fails in the control's walk at ORDER - 1 whenever N >= 2^(ORDER-1), as for 304 at order 8.
  - An LP status other than OPTIMAL or INFEASIBLE, such as GLOP's ABNORMAL, makes no claim about a vector, which
    then gets a child of its own; v3 crashed (see Relaxation).
  - control() takes its examples from EXAMPLES.

Run:   python3 overnight_v4.py N ORDER   (resumes from overnight_N_ORDER_journal.jsonl next to this file)
Quals: python3 quals_v4.py
"""
import os, sys, json, time, hashlib, inspect
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from functools import lru_cache
from math import factorial, prod
import numpy as np
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form
from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp

# SETTINGS[(N, ORDER)] = (CASCADE, CUTS, BUDGET), one entry per run this file can make:
#   CASCADE  the split moduli, in order;
#   CUTS     the residue lattices added to every CP-SAT model as implied constraints;
#   BUDGET   CP-SAT deterministic time by node depth; the last is for the bottom of the cascade.
SETTINGS = {
    (240, 11): ((3, 5, 7, 4, 8, 11, 13, 9), (27, 25, 32, 11, 13), (40,) * 8 + (1200,)),    # overnight_240_v3.py's
    # Small runs for the end-to-end quals in quals_v4.py, whose answers Table 2 gives (m*(48) = 6 and m*(96) = 7
    # have witnesses; m*(40) = m*(56) = 5 and m*(64) = m*(104) = 6 close).  Tiny budgets above the bottom make
    # every node there UNKNOWN, so the tree gets split; cascades and cuts avoid the moduli whose residue
    # conditions alone leave no admissible vector, which would close the tree at its first split.
    (40, 6): ((4, 7, 8), (16,), (0.01, 0.01, 0.01, 5)),
    (48, 6): ((5, 4), (16,), (0.01, 0.01, 5)),
    (56, 6): ((3, 5, 4), (16,), (0.01, 0.01, 0.01, 5)),
    (64, 7): ((4, 7), (16,), (0.01, 0.01, 5)),
    (96, 7): ((5, 4), (16,), (0.01, 0.01, 5)),
    (104, 7): ((5, 7, 4), (16,), (0.01, 0.01, 0.01, 5)),
}
POOL_BUDGET = 0.1                         # a pool's budget is at least this much deterministic time per member
PROCESSES = os.cpu_count()                # nodes worked on at once, each in its own process
WORKERS = 1                               # CP-SAT workers per node: one quick-restart search (see solve)
assert WORKERS >= 1 and all(len(budget) == len(cascade) + 1 for cascade, _, budget in SETTINGS.values())
TOL = 1e-6                                # slack when comparing LP bounds with integer counts
VERDICTS = ('INFEASIBLE', 'UNKNOWN', 'CLOSED')   # the verdicts a journal may hold
SETTLED = ('INFEASIBLE', 'CLOSED')        # the verdicts that close a node's subtree
# Known sequences for control(), by (length, exact order): hex codes in the paper's Table 5 convention (see from_hex).
EXAMPLES = {
    (240, 10): "C394E65AB989457A86B7D0D921636E",                              # the paper's Table 5
    (432, 11): "5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46",      # Claude's p432 (index.html)
    (192, 9): "C1BE1E21CD63D295A7887A59",                                     # p192 (index.html)
    (320, 9): "B24B649ED92CD2C36496CB2DB6295D974138BA41",                      # Claude's p320 (index.html)
    (336, 9): "9C5479E2669C97071E731A62EBC06F28E87B4961DF",                    # Claude's p336 (index.html)
    (48, 6): "C27D8C", (112, 7): "A5994DB29B45A0",                           # the paper's Table 5 (index.html)
    (64, 6): "96696996",                                                      # Thue-Morse, tau_6
    # found with CP-SAT for the end-to-end quals (symmetric or antisymmetric), checked with exact power sums
    (40, 5): "3E136", (48, 5): "5AA5C3", (56, 5): "B219F61", (96, 6): "5C5780DFC30E", (104, 6): "663C5CB48A5D6",
}
HERE = os.path.dirname(os.path.abspath(__file__))
N = ORDER = CASCADE = CUTS = BUDGET = JOURNAL = LOG = None     # set by configure()


SOURCE = hashlib.sha1(open(__file__, 'rb').read()).hexdigest()   # this file, as this process imported it


def configure(n, order):
    """Make this process's run the one for length n and order order: N and ORDER, SETTINGS[(n, order)], the
    journal and log paths, and no results cached for another configuration.  main() calls it, and so does each
    worker process as it starts (see make_executor)."""
    global N, ORDER, CASCADE, CUTS, BUDGET, JOURNAL, LOG
    # TODO: error copy; says SETTINGS has no entry for this length and order
    assert (n, order) in SETTINGS, f'Claude: "no settings for N = {n}, order {order}"'
    N, ORDER = n, order
    CASCADE, CUTS, BUDGET = SETTINGS[n, order]
    JOURNAL = os.path.join(HERE, f'overnight_{n}_{order}_journal.jsonl')
    LOG = os.path.join(HERE, f'overnight_{n}_{order}.log')
    for f in (lattice_basis, moment_rows, integer_system, admissible, moment_basis): f.cache_clear()


def header():
    """The journal's header: what a recorded verdict depends on, including CODE, so that reusing a journal
    across code revisions takes an explicit edit of this line."""
    return {'tag': 'overnight_v4', 'N': N, 'order': ORDER, 'cuts': list(CUTS), 'code': CODE}


def log_to_file(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a') as fh: fh.write(line + '\n')


# ---------- messages (copy; kept out of CODE so that rewriting them never invalidates a journal) ----------

def say_node(i, key, verdict, t_solve, t_split, closed, waiting, running, left_open):
    # TODO: per-node progress line; says: [node number] {node}: CP-SAT verdict (its own status word) (solve seconds + split seconds); closed so far, waiting, running, left open
    return (f'[{i}] {{{key}}}: {verdict} ({t_solve:.1f} + {t_split:.1f} s); '
            f'Claude: "closed {closed}, waiting {waiting}, running {running}, open {left_open}"')


def say_witness(key, eo, a):
    # TODO: says a witness was found at once, before anything else: its node, its exact order, and X, the set of 1-based positions of +1
    return f'Claude: "WITNESS FOUND in {{{key}}}, exact order {eo}: X = {[p + 1 for p in range(N) if a[p] == 1]}"'


def size(M, r): return len(range(r, N, M))
def gbinom(q, k): return prod(range(q - k + 1, q + 1)) // factorial(k)      # C(q, k) for any integer q


def from_hex(h, m):
    """The paper's Table 5 code: the hex digits give the left half of the signs (1 -> +1), the rest follows
    by (-1)^m symmetry."""
    left = [2 * int(ch) - 1 for ch in bin(int(h, 16))[2:].zfill(4 * len(h))]
    return left + [(-1) ** m * t for t in reversed(left)]


def exact_order(a):
    k = 0
    while sum(t * p ** k for p, t in enumerate(a)) == 0: k += 1
    return k


def counts(a, M): return tuple(sum((a[p] + 1) // 2 for p in range(r, N, M)) for r in range(M))


# ---------- the symmetry group G ----------

GROUP = ((0, 1), (1, 1), (0, -1), (1, -1))      # (reverse, sign): id, R, F, phi = RF


def act_seq(g, a):
    rev, sign = g
    return [sign * a[(N - 1 - p) * rev + p * (1 - rev)] for p in range(N)]


def act(g, M, v):
    """The counts mod M of g(a), given the counts v of a."""
    rev, sign = g
    w = [v[((N - 1 - r) * rev + r * (1 - rev)) % M] for r in range(M)]
    return tuple(size(M, r) * (1 - sign) // 2 + sign * w[r] for r in range(M))


def stabilizer(node):
    return [g for g in GROUP if all(tuple(sorted(act(g, M, v) for v in V)) == V for M, V in node)]


def rep(gs, M, v): return min(act(g, M, v) for g in gs)


# ---------- residue lattices and the moment equations ----------

def lattice_poly(order):
    """The coefficients, lowest first, of (x-1)^order, times x+1 when N < 2^order: a sequence of that order has
    f(x) = (x-1)^order h(x), so f(-1) is a multiple of 2^order, and |f(-1)| <= N < 2^order then forces f(-1) = 0."""
    poly = [1]
    for root in [1] * order + [-1] * (N < 2 ** order):
        poly = [a - root * b for a, b in zip([0] + poly, poly + [0])]
    return poly


@lru_cache(maxsize=None)
def lattice_basis(M, order):
    """Columns spanning the residue lattice mod M: the coefficient vectors of p(x) g(x) reduced mod x^M - 1,
    for p = lattice_poly(order)."""
    poly = lattice_poly(order)
    G = [[0] * M for _ in range(M)]
    for k in range(M):
        for t, c in enumerate(poly): G[k][(t + k) % M] += c
    H = hermite_normal_form(sp.Matrix(G).T)
    return tuple(tuple(int(H[r, j]) for j in range(H.shape[1])) for r in range(M))


def add_lattice(md, dvec, B, tag):
    """Constrain the integer expressions dvec to the lattice spanned by the columns of B."""
    M, K = len(B), len(B[0])
    assert K >= 1
    zb = (2 ** 58) // (max(abs(e) for row in B for e in row) * M * 4)
    z = [md.NewIntVar(-zb, zb, f'{tag}_{j}') for j in range(K)]
    for r in range(M): md.Add(dvec[r] == sum(B[r][j] * z[j] for j in range(K)))


@lru_cache(maxsize=None)
def moment_rows(order):
    """Rows and right-hand sides of sum_p C(p - N/2, k) a_p = 0, for k < order, in the 0/1 variables
    x_p = (a_p + 1)/2."""
    rows, rhs = [], []
    for k in range(order):
        w = [gbinom(p - N // 2, k) for p in range(N)]
        rows.append(tuple(2 * t for t in w))
        rhs.append(sum(w))
    return tuple(rows), tuple(rhs)


def count_rows(M): return tuple(tuple(int(p % M == r) for p in range(N)) for r in range(M))


class ExactSystem:
    """Exact test whether A y = b has an integer solution y, for fixed A and varying b.  With H an HNF basis
    of A's column lattice, I a set of rank-many independent rows of H, and K = H_rest H_I^-1:
        b in L(A)  <=>  b_rest = K b_I  and  H_I^-1 b_I is integral.
    Both conditions are linear in b and are kept as integer rows: F (integral after division by den) and E
    (equal to 0)."""
    def __init__(self, A):
        H = hermite_normal_form(sp.Matrix(A))
        m, k = H.shape
        I = list(H.T.rref()[1])
        assert len(I) == k
        inv = H.extract(I, list(range(k))).inv()
        rest = [i for i in range(m) if i not in I]
        K = H.extract(rest, list(range(k))) * inv
        den = int(sp.ilcm(1, 1, *[e.q for e in inv]))
        denK = int(sp.ilcm(1, 1, *[e.q for e in K]))
        self.F = [[0] * m for _ in range(k)]
        for j in range(k):
            for t, i in enumerate(I): self.F[j][i] = int(inv[j, t] * den)
        self.E = [[0] * m for _ in rest]
        for e, i0 in enumerate(rest):
            self.E[e][i0] = -denK
            for t, i in enumerate(I): self.E[e][i] += int(K[e, t] * denK)
        self.den, self.m = den, m

    def fiber(self, head):
        """The test for b = head + v as a function of v alone, with head's contributions precomputed."""
        h, den = len(head), self.den
        F = [(sum(c * x for c, x in zip(row[:h], head, strict=True)), row[h:]) for row in self.F]
        E = [(sum(c * x for c, x in zip(row[:h], head, strict=True)), row[h:]) for row in self.E]
        def ok(v):
            return (all((f + sum(c * x for c, x in zip(row, v, strict=True))) % den == 0 for f, row in F)
                    and all(e + sum(c * x for c, x in zip(row, v, strict=True)) == 0 for e, row in E))
        return ok

    def solvable(self, b): return self.fiber(())(b)


@lru_cache(maxsize=None)
def integer_system(order, moduli):
    rows, _ = moment_rows(order)
    return ExactSystem(rows + sum((count_rows(M) for M in moduli), ()))


@lru_cache(maxsize=None)
def admissible(order, M, fixed):
    """Every admissible count vector mod M, sorted; fixed holds pairs (P, w), P | M, whose class sums must
    hold.  Exact enumeration by back substitution: column j of the HNF basis B has its last nonzero entry
    B[piv_j][j] > 0, with piv increasing (asserted), so going up the rows each pivot row brings one new
    coefficient z_j and every other row is determined by the coefficients already chosen."""
    B = lattice_basis(M, order)
    K = len(B[0])
    piv = [max(r for r in range(M) if B[r][j]) for j in range(K)]
    assert piv == sorted(set(piv)) and all(B[piv[j]][j] > 0 for j in range(K))
    # room[i][r]: the room left, after row r, in r's class mod the i-th fixed modulus (rows still to place
    # there have smaller indices); part[i][q]: the counts placed so far in class q of that modulus
    room = [[sum(size(M, t) for t in range(r % P, r, P)) for r in range(M)] for P, _ in fixed]
    part = [[0] * P for P, _ in fixed]
    z, d, out = [0] * K, [0] * M, []

    def place(r, j, dr):                     # set d_r = dr if it fits, then continue upward
        s = size(M, r)
        c = (dr + s) // 2
        fits = abs(dr) <= s and (dr + s) % 2 == 0 and all(
            part[i][r % P] + c <= w[r % P] <= part[i][r % P] + c + room[i][r] for i, (P, w) in enumerate(fixed))
        if fits:
            d[r] = dr
            for i, (P, _) in enumerate(fixed): part[i][r % P] += c
            climb(r - 1, j)
            for i, (P, _) in enumerate(fixed): part[i][r % P] -= c

    def climb(r, j):                         # rows below r are placed; columns after j are chosen
        if r < 0:
            c = tuple((d[q] + size(M, q)) // 2 for q in range(M))
            assert sum(c) == N // 2
            out.append(c)
            return
        base = sum(B[r][i] * z[i] for i in range(j + 1, K))
        if j >= 0 and piv[j] == r:           # a pivot row: choose the coefficient z_j
            h, s = B[r][j], size(M, r)
            for t in range(-((s + base) // h), (s - base) // h + 1):
                z[j] = t
                place(r, j - 1, base + h * t)
        else:                                # a row determined by the coefficients already chosen
            place(r, j, base)

    climb(M - 1, K - 1)
    return tuple(sorted(out))


# ---------- LP relaxation (groups children; never closes anything) ----------

@lru_cache(maxsize=None)
def moment_basis(order):
    """An orthonormal basis (columns) of the polynomials of degree < order on the positions, so the LP
    sees well-scaled moment rows spanning the same space as the exact ones."""
    t = (np.arange(N) - (N - 1) / 2) / (N / 2)
    return np.linalg.qr(np.vander(t, order, increasing=True))[0]


class Relaxation:
    """The LP relaxation, 0 <= x_p <= 1, of a node's children by counts mod M.  The LP proves a vector's
    relaxation infeasible by an INFEASIBLE status, or by the vector's lying outside the box of count bounds,
    which only OPTIMAL bound solves set; any other status (GLOP's ABNORMAL, say) makes no claim.  So a vector
    joins the pool only when proven infeasible, and a solver failure costs a child of its own, never a crash."""
    def __init__(self, order, node, M):
        s = self.s = pywraplp.Solver.CreateSolver('GLOP')
        # Presolve with warm starts gave ABNORMAL statuses at order 10; without it GLOP matched HiGHS and
        # cold starts on all 2730 sampled mod-13 checks.
        assert s.SetSolverSpecificParametersAsString('use_preprocessing: false')
        x = self.x = [s.NumVar(0, 1, f'x{p}') for p in range(N)]
        Q = moment_basis(order)
        for k in range(order):
            half = float(Q[:, k].sum()) / 2
            ct = s.RowConstraint(half, half, '')
            for p in range(N): ct.SetCoefficient(x[p], float(Q[p, k]))
        for P, V in node:
            assert len(V) == 1
            for r in range(P):
                ct = s.RowConstraint(V[0][r], V[0][r], '')
                for p in range(r, N, P): ct.SetCoefficient(x[p], 1)
        self.rows = [s.RowConstraint(0, size(M, r), '') for r in range(M)]
        for r, ct in enumerate(self.rows):
            for p in range(r, N, M): ct.SetCoefficient(x[p], 1)
        self.M = M

    def solve(self, objective):
        """The status of minimizing objective, a dict p -> coefficient."""
        obj = self.s.Objective()
        obj.Clear()
        for p, c in objective.items(): obj.SetCoefficient(self.x[p], c)
        obj.SetMinimization()
        return self.s.Solve()

    def bound(self, r, sign):
        """The least (sign 1) or greatest (sign -1) count in class r, from an OPTIMAL solve; otherwise no bound."""
        st = self.solve({p: sign for p in range(r, N, self.M)})
        return sign * self.s.Objective().Value() if st == pywraplp.Solver.OPTIMAL else -sign * float('inf')

    def check(self, v):
        """Is the relaxation with counts mod M equal to v not proven infeasible?"""
        for r, ct in enumerate(self.rows): ct.SetBounds(v[r], v[r])
        st = self.solve({})
        for r, ct in enumerate(self.rows): ct.SetBounds(0, size(self.M, r))
        return st != pywraplp.Solver.INFEASIBLE

    def feasible_set(self, vecs):
        """The members of vecs whose relaxation the LP does not prove infeasible; only those inside the box of LP
        count bounds are tested one by one."""
        if self.solve({}) == pywraplp.Solver.INFEASIBLE:             # the node's own relaxation is infeasible
            return []
        lo = [self.bound(r, 1) for r in range(self.M)]
        hi = [self.bound(r, -1) for r in range(self.M)]
        inside = [v for v in vecs if all(lo[r] - TOL <= v[r] <= hi[r] + TOL for r in range(self.M))]
        return [v for v in inside if self.check(v)]


# ---------- the search tree ----------

def is_pool(node): return any(len(V) > 1 for _, V in node[-1:])


def split(order, node):
    """The children of a node with verdict UNKNOWN (see 'split' in the vocabulary)."""
    if is_pool(node):                                                # one child per member
        M, V = node[-1]
        return [node[:-1] + ((M, (v,)),) for v in V]
    if len(node) == len(CASCADE):                                    # the bottom of the cascade
        return []
    assert all(len(V) == 1 for _, V in node)
    M = CASCADE[len(node)]
    fixed = tuple((P, V[0]) for P, V in node if M % P == 0)
    rhs = moment_rows(order)[1] + tuple(t for _, V in node for t in V[0])
    ok = integer_system(order, tuple(P for P, _ in node) + (M,)).fiber(rhs)
    gs = stabilizer(node)
    vecs = [v for v in admissible(order, M, fixed) if ok(v) and v == rep(gs, M, v)]
    feasible = Relaxation(order, node, M).feasible_set(vecs)
    pool = tuple(sorted(set(vecs) - set(feasible)))
    return [node + ((M, (v,)),) for v in feasible] + [node + ((M, pool),)]


def build_model(order, node, fix=()):
    """The CP-SAT model of a node: the moment equations, the node's count constraints and the lattice cuts;
    fix pins the 0/1 variables (for controls)."""
    md = cp_model.CpModel()
    x = [md.NewBoolVar(f'x{p}') for p in range(N)]
    rows, rhs = moment_rows(order)
    for w, r in zip(rows, rhs): md.Add(sum(c * x[p] for p, c in enumerate(w)) == r)
    for M, V in node:
        c = [md.NewIntVar(0, size(M, r), f'c{M}_{r}') for r in range(M)]
        for r in range(M): md.Add(c[r] == sum(x[p] for p in range(r, N, M)))
        md.AddAllowedAssignments(c, V)
    for M in CUTS:
        add_lattice(md, [sum(2 * x[p] for p in range(r, N, M)) - size(M, r) for r in range(M)],
                    lattice_basis(M, order), f'cut{M}')
    for p, t in enumerate(fix): md.Add(x[p] == t)
    return md, x


def solve(md, budget):
    """CP-SAT with WORKERS threads running quick-restart search, limited by deterministic time.  On the hard
    leaves one such worker needed about 3.5x less CPU than CP-SAT's default, and a second default worker only
    runs heuristics that look for solutions.  Ctrl-C reaches a solve only once it returns, so a worker process
    records nothing partial; the main process stops waiting at once and its executor then lets the solves
    finish."""
    sv = cp_model.CpSolver()
    sv.parameters.max_deterministic_time = budget
    sv.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH
    sv.parameters.num_workers = WORKERS
    sv.parameters.catch_sigint_signal = False
    return sv, sv.Solve(md)


def solve_node(order, node, budget):
    """CP-SAT's verdict on a node within the budget, and the sequence of a FEASIBLE verdict."""
    md, x = build_model(order, node)
    sv, st = solve(md, budget)
    verdict = {cp_model.OPTIMAL: 'FEASIBLE', cp_model.FEASIBLE: 'FEASIBLE',
               cp_model.INFEASIBLE: 'INFEASIBLE', cp_model.UNKNOWN: 'UNKNOWN'}[st]
    return verdict, [2 * sv.Value(t) - 1 for t in x] if verdict == 'FEASIBLE' else None


def node_budget(node): return max(BUDGET[len(node)], POOL_BUDGET * sum(len(V) for _, V in node[-1:]))


def node_key(node):
    """A node's journal key: each constraint as M:[vector], or as M:#count:sha1 for a pool of any other
    size."""
    def part(M, V):
        if len(V) == 1: return f'{M}:[{",".join(map(str, V[0]))}]'
        return f'{M}:#{len(V)}:{hashlib.sha1(repr(V).encode()).hexdigest()}'
    return ' '.join(part(M, V) for M, V in node)


class Journal:
    """Verdicts by node key: a header line (tag, order, cuts), then one JSON object per verdict with the
    budget it was reached under.  A key's later records follow an UNKNOWN only: a re-solve with a larger
    budget, or CLOSED."""
    def __init__(self, path):
        self.path = path
        if not os.path.exists(path):                                 # a fresh run starts the journal
            with open(path, 'w') as fh: fh.write(json.dumps(header()) + '\n')
        lines = open(path).read().splitlines()
        # TODO: error copy; says this journal file was written by a run with a different order or cut list
        assert json.loads(lines[0]) == header(), f'Claude: "the journal {path} belongs to another configuration"'
        self.records = {}
        for rec in map(json.loads, lines[1:]): self.admit(rec)

    def admit(self, rec):
        prev = self.records.get(rec['key'], {'verdict': 'UNKNOWN', 'budget': -1})
        assert rec['verdict'] in VERDICTS and prev['verdict'] == 'UNKNOWN'
        assert rec['verdict'] == 'CLOSED' or prev['budget'] < rec['budget']
        self.records[rec['key']] = rec

    def reuse(self, key, budget):
        """The recorded verdict if it still holds: INFEASIBLE or CLOSED always, UNKNOWN only if it was reached
        with at least this budget; else None."""
        rec = self.records.get(key, {'verdict': None, 'budget': -1})
        return rec['verdict'] if rec['verdict'] in SETTLED or rec['budget'] >= budget else None

    def put(self, key, verdict, budget):
        rec = {'key': key, 'verdict': verdict, 'budget': budget}
        self.admit(rec)
        with open(self.path, 'a') as fh:
            fh.write(json.dumps(rec) + '\n')
            fh.flush()
            os.fsync(fh.fileno())


def work(order, node, budget, known, source):
    """One node's step, run in a worker process: CP-SAT's verdict within the budget (or known, a reusable
    UNKNOWN from the journal) and, for UNKNOWN, the node's children.  source is the main process's SOURCE:
    the worker must run the very file whose control passed.  Returns (verdict, the sequence of a FEASIBLE
    verdict or None, children, solve seconds, split seconds)."""
    assert source == SOURCE
    t0 = time.time()
    verdict, a = (known, None) if known else solve_node(order, node, budget)
    t1 = time.time()
    children = split(order, node) if verdict == 'UNKNOWN' else []
    return verdict, a, children, t1 - t0, time.time() - t1


def make_executor():
    """PROCESSES worker processes, each configured for this run as it starts."""
    return ProcessPoolExecutor(PROCESSES, initializer=configure, initargs=(N, ORDER))


def search(order, journal, log, executor):
    """Close the tree from the top node depth-first, PROCESSES nodes at a time.  A subtree is closed when its
    node is INFEASIBLE or all its children's subtrees are closed; each closed subtree with children is
    journaled CLOSED.  Returns {'closed', 'open', 'witness', 'exact_order'}, where closed counts the nodes
    closed by a fresh INFEASIBLE verdict or settled from the journal; a witness ends the search."""
    res = {'closed': 0, 'open': [], 'witness': None, 'exact_order': None}
    stack, running, parent, pending, spoiled, i = [()], {}, {}, {}, set(), 0

    def settle(node, ok):                    # node's subtree is finished, closed if ok: tell its ancestors
        while node in parent:
            p = parent.pop(node)
            pending[p] -= 1
            if not ok: spoiled.add(p)
            if pending[p]: return
            del pending[p]
            ok = p not in spoiled
            if ok: journal.put(node_key(p), 'CLOSED', node_budget(p))
            node = p

    while stack or running:
        while stack and len(running) < PROCESSES:
            node = stack.pop()
            known = journal.reuse(node_key(node), node_budget(node))
            if known in SETTLED:                                     # closed by an earlier run
                res['closed'] += 1
                settle(node, True)
                continue
            running[executor.submit(work, order, node, node_budget(node), known, SOURCE)] = (node, known)
        done, _ = wait(running, return_when=FIRST_COMPLETED)
        for f in done:
            node, known = running.pop(f)
            verdict, a, children, t_solve, t_split = f.result()
            if verdict == 'FEASIBLE':
                eo = exact_order(a)
                assert eo >= order                                   # a CP-SAT solution must pass the exact test
                log(say_witness(node_key(node), eo, a))
                return dict(res, witness=a, exact_order=eo)
            if known is None:                                        # a fresh verdict
                journal.put(node_key(node), verdict, node_budget(node))
            res['closed'] += verdict == 'INFEASIBLE'
            res['open'] += [node] * (verdict == 'UNKNOWN' and not children)
            if children:
                pending[node] = len(children)
                for c in children: parent[c] = node
                stack.extend(children)
            else:
                settle(node, verdict == 'INFEASIBLE')
            i += 1
            log(say_node(i, node_key(node), verdict, t_solve, t_split, res['closed'], len(stack), len(running), len(res['open'])))
    return res


def status_with_fix(order, node, a):
    md, _ = build_model(order, node, fix=[(t + 1) // 2 for t in a])
    return solve(md, 120)[1]


def control():
    """Startup control.  Exact checks at ORDER: every column of the moment-and-count matrix passes each
    cascade prefix's integer filter (so the filter accepts every integer solution); every generator of each
    residue lattice lies in its basis's span; and the residue vectors of every example of order ORDER in
    EXAMPLES lie in the lattices (which do not depend on the length when f(-1) = 0, asserted).  Then, at ORDER - 1,
    follow the example of that order and length N down the cascade with the real split: at each split its
    image under the stabilizer must land in a child of its own (so its LP relaxation was not proven
    infeasible) whose CP-SAT model accepts it; at ORDER the final node's model must reject it."""
    rows, _ = moment_rows(ORDER)
    for i in range(1, len(CASCADE) + 1):
        A = rows + sum((count_rows(M) for M in CASCADE[:i]), ())
        assert all(integer_system(ORDER, CASCADE[:i]).solvable([row[p] for row in A]) for p in range(N))
    bs = [from_hex(h, m) for (n, m), h in EXAMPLES.items() if m == ORDER]
    assert bs and all(exact_order(b) == ORDER and sum(t * (-1) ** p for p, t in enumerate(b)) == 0 for b in bs)
    for M in sorted(set(CASCADE + CUTS)):
        span = ExactSystem(lattice_basis(M, ORDER))
        poly = lattice_poly(ORDER)
        gens = [[sum(c for t, c in enumerate(poly) if (t + k) % M == r) for r in range(M)] for k in range(M)]
        assert all(span.solvable(g) for g in gens)
        assert all(span.solvable([sum(b[p] for p in range(r, len(b), M)) for r in range(M)]) for b in bs)
    m = ORDER - 1
    a, node = from_hex(EXAMPLES[N, m], m), ()
    assert len(a) == N and exact_order(a) == m
    for M in CASCADE:
        gs = stabilizer(node)
        v = rep(gs, M, counts(a, M))
        a = next(act_seq(g, a) for g in gs if act(g, M, counts(a, M)) == v)
        node = node + ((M, (v,)),)
        assert node in split(m, node[:-1])
        assert status_with_fix(m, node, a) == cp_model.OPTIMAL
    assert status_with_fix(ORDER, node, a) == cp_model.INFEASIBLE


def main():
    # TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
    if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
    # TODO: error copy; says how to run the script: with the length N and the order as its two arguments
    assert len(sys.argv) == 3, 'Claude: "usage: python3 overnight_v4.py N ORDER"'
    configure(int(sys.argv[1]), int(sys.argv[2]))
    run()


def run():
    """The run that configure() set up: the control, the search, and its outcome, all in the log."""
    t0 = time.time()
    journal = Journal(JOURNAL)
    # TODO: start line; says: start: n, order at least, processes times CP-SAT workers each, budgets in deterministic time by depth, split moduli, cut moduli, and how many verdicts the journal already holds
    log_to_file(f'Claude: "start: n = {N}, order at least {ORDER}, {PROCESSES} processes × {WORKERS} workers, budgets {list(BUDGET)} (deterministic time), '
                f'split moduli {list(CASCADE)}, cuts {list(CUTS)}, {len(journal.records)} earlier verdicts"')
    control()
    # TODO: says the startup control passed: the example of order ORDER-1 and length N survived every split, and order ORDER rejects it
    log_to_file(f'Claude: "startup control passed: the order-{ORDER - 1} example of length {N} survived every split, and order {ORDER} rejects it"')
    with make_executor() as executor:
        res = search(ORDER, journal, log_to_file, executor)
    hours = (time.time() - t0) / 3600
    for node in res['open']:
        # TODO: names one node left open
        log_to_file(f'Claude: "open: {{{node_key(node)}}}"')
    if res['witness'] is not None:
        X = [p + 1 for p in range(N) if res['witness'][p] == 1]
        # TODO: says a witness was found: its exact order, and X, the set of 1-based positions of +1
        log_to_file(f'Claude: "WITNESS FOUND, exact order {res["exact_order"]}: X = {X}"')
    elif res['open']:
        # TODO: says the search is not finished: how many nodes were left open, how many closed, and the hours taken
        log_to_file(f'Claude: "NOT FINISHED: {len(res["open"])} nodes left open, {res["closed"]} closed ({hours:.1f} h)"')
    else:
        # TODO: says every node closed, so no +-1 sequence of length N has order at least ORDER, which rests on the CP-SAT solver's INFEASIBLE verdicts; with the count of closed nodes and the hours taken
        log_to_file(f'Claude: "ALL NODES CLOSED ({res["closed"]}, {hours:.1f} h): no ±1 sequence of length {N} has order '
                    f'at least {ORDER}; this rests on the CP-SAT solver\'s INFEASIBLE verdicts."')


# A fingerprint of the code that decides verdicts, taken as imported (see header()).
CODE = hashlib.sha1(''.join(inspect.getsource(f) for f in (
    lattice_poly, lattice_basis, add_lattice, moment_rows, count_rows, ExactSystem, integer_system, admissible, act,
    stabilizer, rep, split, build_model, solve, solve_node, node_key, work, search)).encode()).hexdigest()


if __name__ == '__main__':
    main()
