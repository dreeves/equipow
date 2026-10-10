#!/usr/bin/env python3
"""N in L_ORDER?  Version 5: the count-vector cube-and-conquer of overnight_v4.py, with certbb (certbb.py), a
certified branch and bound, as the node solver in place of CP-SAT, so that every INFEASIBLE verdict rests on a proof
checked in exact integer arithmetic.

The question, from Buhler, Golan, Pratt and Wagon, Math. Comp. 90 (2021) 1435-1453, Table 2: is there a +-1
sequence a_0..a_{N-1} whose power sums sum_p a_p p^k vanish for k = 0..ORDER-1, that is, of order at least ORDER?

Vocabulary used throughout this file, each term defined once here (certbb.py defines its own: box, rows,
certificate, proof, ...):
  order          the number of leading exponents k = 0, 1, ... whose power sums vanish.
  size(M, r)     the number of positions p in 0..N-1 with p = r (mod M).
  counts mod M   c_r = the number of +1's at positions p = r (mod M), for r = 0..M-1.
  admissible     a count vector mod M with 0 <= c_r <= size(M, r), whose differences d = 2c - size lie in
                 the residue lattice of the order (see lattice_basis), and whose class sums match the counts
                 already fixed modulo any divisor of M.  Every sequence of the given order has admissible
                 counts.
  node           the sequences whose counts mod M lie in V_M for each pair (M, V_M) of a tuple of
                 constraints; a vertex of the search tree.  The top node is the empty tuple.
  pool           the one child of a split holding every vector whose LP relaxation the LP claims is infeasible
                 (perhaps none, perhaps one; see Relaxation), so that a single certbb run can close them all.
                 A pool with more than one member splits into one child per member.
  split          the children of a node with verdict UNKNOWN: a pool's members, as above; otherwise, by the
                 next cascade modulus M, the admissible vectors mod M that pass the exact integer filter,
                 reduced to one per orbit of the node's stabilizer, each with a child of its own unless the LP
                 claims its relaxation is infeasible, and the rest in one pool.  At the bottom of the cascade, none.
  LP failure     an LP solve whose status is neither OPTIMAL nor INFEASIBLE, such as GLOP's ABNORMAL; it claims
                 nothing about a vector (see Relaxation).  Each node's progress line counts those of its split.
  cascade        the moduli used for splitting, in order.
  G              the symmetries of the problem, written (reverse, sign): R reverses positions, F flips
                 signs, phi = RF.  All of them preserve the order.
  stabilizer     the elements of G that map a node onto itself; rep(gs, M, v) is the least image of v
                 under them.
  budget         a node's certbb limit in LP solves (deterministic for a given HiGHS build, and unaffected by other
                 load on the machine): BUDGET[depth], longer at the bottom of the cascade, and for a pool at least
                 POOL_BUDGET per member.
  verdict        certbb's result for a node: INFEASIBLE (closed, on a complete proof that certbb.Check accepted
                 token by token as certbb.solve made it), UNKNOWN (no result within the budget), or FEASIBLE with a
                 sequence.  The journal also records CLOSED for a node whose children's subtrees are all closed,
                 so a resumed run skips it.
  witness        a FEASIBLE sequence whose order, checked with exact power sums, is at least the target.
  open leaf      a node with verdict UNKNOWN and no children.
  control        the startup check that a known example of order ORDER-1 and length N (from EXAMPLES)
                 survives every step of the search at order ORDER-1.

Search: depth-first from the top node, PROCESSES nodes at a time, each in its own process (which solves the
node and, for UNKNOWN, splits it); the main process keeps the tree and the journal.

Soundness: the run shows that no sequence of order at least ORDER exists exactly when it ends with no open
leaf and no witness.  Each node closes by an INFEASIBLE verdict, which stands only on a complete proof whose every
certificate certbb.Check has checked in exact integer arithmetic.  Enumeration, the integer filter and the symmetry
reduction are exact integer arithmetic too; floating point (HiGHS inside certbb, GLOP in split) only guides the
search and groups children.

Changes from overnight_v4.py:
  - solve_node runs certbb on the node, its budget counted in LP solves, and certbb.Check checks the proof as it is
    made, in bounded memory, keeping only a running sha1 of its tokens.
  - SETTINGS[(N, ORDER)] is (CASCADE, BUDGET), the budgets in LP solves; CUTS, the lattice constraints v4 added to
    every CP-SAT model, are gone, as certbb's rows leave them out (see certbb.py).
  - configure() no longer asserts that the moment rows' |coefficients| sum to less than 2^62, which only CP-SAT's
    64-bit integers needed; certbb's arithmetic is exact at any size.
  - The journal and log are overnight_v5_N_ORDER_journal.jsonl and overnight_v5_N_ORDER.log.  A solve's journal
    record adds lps, leaves and proof (see solve_node); the header adds solver, budget_unit and highs (the HiGHS
    build), and drops cuts.
  - CODE fingerprints all of certbb.py as well, and SOURCE holds the sha1 of both files, which work() checks.
  - control() checks certbb's rows (solve_node with the box pinned to the example) where v4 ran CP-SAT on pinned
    models.
  - The ALL NODES CLOSED line says the result rests on certificates checked in exact integer arithmetic.

Run:   python3 overnight_v5.py N ORDER   (resumes from overnight_v5_N_ORDER_journal.jsonl next to this file)
Quals: python3 quals_v5.py
"""
import os, sys, json, time, hashlib, inspect
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from functools import lru_cache
from math import factorial, prod
import numpy as np
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form
from ortools.linear_solver import pywraplp
import certbb

# SETTINGS[(N, ORDER)] = (CASCADE, BUDGET), one entry per run this file can make:
#   CASCADE  the split moduli, in order;
#   BUDGET   certbb's LP solves by node depth; the last is for the bottom of the cascade.
# The budgets of the two long runs rest on certbb's LP solves on nodes of the earlier runs (overnight_240_v3.py's
# journal for 240@11, overnight_v4.py's log for 304@9), counted on 2026-10-08 through solve_node's calls, or by
# certbb's builder the day before (marked *; most of those ran on primal simplex, which moves the counts by a few %).
# An LP solve, its certificate and its share of the proof check took 1.55 to 1.82 ms of CPU at 240@11, 1.1 to 1.2 ms
# at 304@9.
#   - Above the bottom, 10000 (about 17 CPU-s at 240@11).  At 240@11, two depth-7 nodes closed in 2227 and 9039, a
#     third was UNKNOWN at 30000 with 0.8% of its tree closed, and three depth-5 nodes were UNKNOWN* at 31407 to 77932
#     with 0.3% to 12% closed.  At 304@9, two depth-5 nodes that CP-SAT closed at budget 40 took 5 and 527; three it
#     left UNKNOWN were UNKNOWN at 20000 with 2.5%, 50% and 75% closed.  Splitting those cost about as much as
#     closing them whole would: v4 split them into 47 leaves (18 left open), 31 and 14 (each also with a pool), the
#     last two worth about 33000 and 15000 at the leaf counts below, against about 40000 and 27000 to close them
#     whole (projected linearly from the share closed).
#   - At the bottom, 2000000 (about an hour of CPU at 240@11, 40 minutes at 304@9).  At 240@11, of 24* leaves CP-SAT
#     closed, the slowest took 19141; of 10 it left open at budget 1200, 8 closed in 4277 to 274663*, and 2 were
#     UNKNOWN* at about 120000 with 18% and 11% closed (projected linearly: 670000 and 1100000).  At 304@9, 10 leaves
#     CP-SAT closed took 9 to 16157 (the four it took 149 to 462 s of wall time on, 6221 to 16157); 4 it left open at
#     1200 were UNKNOWN at 50000 with 9%, 19%, 55% and 80% closed (projected linearly: 534000, 267000, 91000 and
#     63000).  A linear projection is not a reliable estimate of a tree's size.
#   - POOL_BUDGET, 3 per member: pools of 9746* (240@11, depth 7), 350 and 357 members (304@9, depth 6) closed in one
#     LP solve per member.
SETTINGS = {
    (240, 11): ((3, 5, 7, 4, 8, 11, 13, 9), (10000,) * 8 + (2000000,)),       # cascade: overnight_240_v3.py's
    # 304@9.  Splitting to depth 4 with this cascade, the pools not expanded into their members, gives, per level,
    # the children of their own (then the vectors pooled): mod 3, 1 (0); mod 5, 5 (4); mod 4, 17 (68); mod 7, 53
    # (10939).  Expanding the pools as well (their members gave no children of their own) makes those pooled
    # counts 168 at mod 4 and 127707 at mod 7.  The mod-8 splits
    # (given mod 4) of five depth-4 nodes gave 1, 1, 1, 8 and 59 children of their own, with pools of 4991 to
    # 9999 (one of them out of 130321 admissible vectors); one mod-9 split (given mod 3) gave 35 (329).  So, as
    # in v3, the first levels have few children and the last ones many, mostly pooled.  v3's 11 and 13 are left
    # out: at order 9 their lattice indices are only 11^8 and 13^8, against classes of about 28 positions, which
    # leaves some 10^7 admissible vectors each (scaling v3's counts; the enumeration did not finish in 20 s) at
    # every split; 8 and 9 refine 4 and 3 instead.
    (304, 9): ((3, 5, 4, 7, 8, 9), (10000,) * 6 + (10000000,)),
    # Small runs for the end-to-end quals in quals_v5.py, whose answers Table 2 gives (m*(48) = 6 has witnesses;
    # m*(40) = m*(56) = 5 and m*(64) = m*(104) = 6 close).  A budget of 1 above the bottom (3, POOL_BUDGET, for a
    # node of one vector) leaves the upper nodes UNKNOWN, so the tree gets split; at the bottom, the most any of these
    # runs needed was 181.  The cascades are v4's, which avoid the moduli whose residue conditions alone leave no
    # admissible vector (3 and 9 at 40@6; 3, 5 and 9 at 64@7; 8 at 104@7), except for 104@7's last split modulus, 8,
    # which closes that tree by exact enumeration.
    (40, 6): ((4, 7, 8), (1, 1, 1, 100000)),
    (48, 6): ((5, 4), (1, 1, 100000)),
    (56, 6): ((3, 5, 4), (1, 1, 1, 100000)),
    (64, 7): ((4, 7), (1, 1, 100000)),
    (104, 7): ((5, 4, 8), (1, 1, 1, 100000)),
}
POOL_BUDGET = 3                           # a pool's budget is at least this many LP solves per member
PROCESSES = os.cpu_count()                # nodes worked on at once, each in its own process
assert all(len(budget) == len(cascade) + 1 and all(type(b) is int and b >= 1 for b in budget)
           for cascade, budget in SETTINGS.values())
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
    (304, 8): "A9E21ACCB5C96794C56D9C4255B4336DEAD8A4",                       # the paper's Table 5 (arXiv:1912.03491)
    (64, 6): "96696996",                                                      # Thue-Morse, tau_6
    # found with CP-SAT for the end-to-end quals (symmetric or antisymmetric), checked with exact power sums
    (40, 5): "3E136", (48, 5): "5AA5C3", (56, 5): "B219F61", (104, 6): "663C5CB48A5D6",
}
HERE = os.path.dirname(os.path.abspath(__file__))
N = ORDER = CASCADE = BUDGET = JOURNAL = LOG = None     # set by configure()


# this file and certbb.py, as this process imported them
SOURCE = tuple(hashlib.sha1(open(f, 'rb').read()).hexdigest() for f in (__file__, certbb.__file__))


def configure(n, order):
    """Make this process's run the one for length n and order order: N and ORDER, SETTINGS[(n, order)], the
    journal and log paths, and no results cached for another configuration.  main() calls it, and so does each
    worker process as it starts (see make_executor)."""
    global N, ORDER, CASCADE, BUDGET, JOURNAL, LOG
    # TODO: error copy; says SETTINGS has no entry for this length and order
    assert (n, order) in SETTINGS, f'Claude: "no settings for N = {n}, order {order}"'
    N, ORDER = n, order
    CASCADE, BUDGET = SETTINGS[n, order]
    JOURNAL = os.path.join(HERE, f'overnight_v5_{n}_{order}_journal.jsonl')
    LOG = os.path.join(HERE, f'overnight_v5_{n}_{order}.log')
    for f in CACHED: f.cache_clear()


def header():
    """The journal's header: what a recorded verdict depends on, including CODE, so that reusing a journal
    across code revisions takes an explicit edit of this line.  The HiGHS build steers certbb's search, so it
    decides UNKNOWN verdicts (an INFEASIBLE one rests on its checked proof alone)."""
    return {'tag': 'overnight_v5', 'N': N, 'order': ORDER, 'code': CODE, 'solver': 'certbb',
            'budget_unit': 'LP solves', 'highs': certbb.HIGHS}


def log_to_file(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a') as fh: fh.write(line + '\n')


# ---------- messages (copy; kept out of CODE so that rewriting them never invalidates a journal) ----------

def say_node(i, key, verdict, t_solve, t_split, closed, waiting, running, left_open, failures):
    # TODO: per-node progress line; says: [node number] {node}: certbb's verdict (its own status word) (solve seconds + split seconds); closed so far, waiting, running, left open, and the LP failures in this node's split (LP solves whose status was neither OPTIMAL nor INFEASIBLE)
    return (f'[{i}] {{{key}}}: {verdict} ({t_solve:.1f} + {t_split:.1f} s); '
            f'Claude: "closed {closed}, waiting {waiting}, running {running}, open {left_open}, LP failures {failures}"')


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


@lru_cache(maxsize=None)
def moments(order):
    """The moment rows of an order in certbb's form."""
    return certbb.Moments(*moment_rows(order))


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


CACHED = (lattice_basis, moment_rows, moments, integer_system, admissible, moment_basis)   # results that depend on N


class Relaxation:
    """The LP relaxation, 0 <= x_p <= 1, of a node's children by counts mod M.  The LP claims a vector's
    relaxation is infeasible by an INFEASIBLE status, or by the vector's lying outside the box of count bounds,
    which only OPTIMAL bound solves set; an LP failure (any other status, GLOP's ABNORMAL, say) makes no claim.
    So a vector joins the pool only when claimed infeasible, and an LP failure costs a child of its own, never a
    crash.  Relaxation.failures counts the LP failures in this process."""
    failures = 0

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
        """The status of minimizing objective, a dict p -> coefficient; an LP failure adds 1 to failures."""
        obj = self.s.Objective()
        obj.Clear()
        for p, c in objective.items(): obj.SetCoefficient(self.x[p], c)
        obj.SetMinimization()
        st = self.s.Solve()
        Relaxation.failures += st not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.INFEASIBLE)
        return st

    def bound(self, r, sign):
        """The least (sign 1) or greatest (sign -1) count in class r, from an OPTIMAL solve; otherwise no bound."""
        st = self.solve({p: sign for p in range(r, N, self.M)})
        return sign * self.s.Objective().Value() if st == pywraplp.Solver.OPTIMAL else -sign * float('inf')

    def check(self, v):
        """Is the relaxation with counts mod M equal to v not claimed infeasible?"""
        for r, ct in enumerate(self.rows): ct.SetBounds(v[r], v[r])
        st = self.solve({})
        for r, ct in enumerate(self.rows): ct.SetBounds(0, size(self.M, r))
        return st != pywraplp.Solver.INFEASIBLE

    def feasible_set(self, vecs):
        """The members of vecs whose relaxation the LP does not claim is infeasible; only those inside the box of LP
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


def solve_node(order, node, budget, lo=None, hi=None):
    """certbb's verdict on a node within the budget (LP solves), the sequence of a FEASIBLE verdict, and the
    journal's fields for this solve: lps, the LP solves made; leaves, the boxes closed; and proof, the sha1 of the
    proof stream (see certbb.Check).  certbb.Check checks the stream token by token as certbb.solve makes it, so no
    proof is held in memory, and an INFEASIBLE verdict stands only once the check has seen the end of a complete
    proof.  lo and hi bound the box, by default all of {0,1}^N; control() pins it to its example."""
    check = certbb.Check(moments(order), node, lo, hi)
    verdict, x, stats = certbb.solve(moments(order), node, budget, check.feed, lo, hi)
    if verdict == 'INFEASIBLE': check.end()                          # raises unless the proof is complete
    found = {'lps': stats['lp'], 'leaves': stats['leaves'], 'proof': check.sha1.hexdigest()}
    return verdict, [2 * t - 1 for t in x] if verdict == 'FEASIBLE' else None, found


def node_budget(node): return max(BUDGET[len(node)], POOL_BUDGET * sum(len(V) for _, V in node[-1:]))


def node_key(node):
    """A node's journal key: each constraint as M:[vector], or as M:#count:sha1 for a pool of any other
    size."""
    def part(M, V):
        if len(V) == 1: return f'{M}:[{",".join(map(str, V[0]))}]'
        return f'{M}:#{len(V)}:{hashlib.sha1(repr(V).encode()).hexdigest()}'
    return ' '.join(part(M, V) for M, V in node)


class Journal:
    """Verdicts by node key: a header line (see header), then one JSON object per verdict with the budget it was
    reached under and, for a solve, its lps, leaves and proof (see solve_node).  A key's later records follow an
    UNKNOWN only: a re-solve with a larger budget, or CLOSED."""
    def __init__(self, path):
        self.path = path
        if not os.path.exists(path):                                 # a fresh run starts the journal
            with open(path, 'w') as fh: fh.write(json.dumps(header()) + '\n')
        lines = open(path).read().splitlines()
        # TODO: error copy; says this journal file was written by a run with a different configuration or code
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

    def put(self, key, verdict, budget, found):
        """Record a verdict; found holds a solve's lps, leaves and proof (see solve_node), and is empty for CLOSED."""
        rec = {'key': key, 'verdict': verdict, 'budget': budget} | found
        self.admit(rec)
        with open(self.path, 'a') as fh:
            fh.write(json.dumps(rec) + '\n')
            fh.flush()
            os.fsync(fh.fileno())


def work(order, node, budget, known, source):
    """One node's step, run in a worker process: certbb's verdict within the budget (or known, a reusable
    UNKNOWN from the journal) and, for UNKNOWN, the node's children.  source is the main process's SOURCE:
    the worker must run the very files, this one and certbb.py, whose control passed.  Returns (verdict, the
    sequence of a FEASIBLE verdict or None, children, solve seconds, split seconds, the split's LP failures, the
    solve's journal fields or None for known)."""
    assert source == SOURCE
    t0 = time.time()
    verdict, a, found = (known, None, None) if known else solve_node(order, node, budget)
    t1 = time.time()
    failures = Relaxation.failures
    children = split(order, node) if verdict == 'UNKNOWN' else []
    return verdict, a, children, t1 - t0, time.time() - t1, Relaxation.failures - failures, found


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
            if ok: journal.put(node_key(p), 'CLOSED', node_budget(p), {})
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
            verdict, a, children, t_solve, t_split, failures, found = f.result()
            if verdict == 'FEASIBLE':
                eo = exact_order(a)
                assert eo >= order                                   # a certbb solution must pass the exact test
                log(say_witness(node_key(node), eo, a))
                return dict(res, witness=a, exact_order=eo)
            if known is None:                                        # a fresh verdict
                journal.put(node_key(node), verdict, node_budget(node), found)
            res['closed'] += verdict == 'INFEASIBLE'
            res['open'] += [node] * (verdict == 'UNKNOWN' and not children)
            if children:
                pending[node] = len(children)
                for c in children: parent[c] = node
                stack.extend(children)
            else:
                settle(node, verdict == 'INFEASIBLE')
            i += 1
            log(say_node(i, node_key(node), verdict, t_solve, t_split, res['closed'], len(stack), len(running), len(res['open']), failures))
    return res


def control():
    """Startup control.  Exact checks at ORDER: every column of the moment-and-count matrix passes each
    cascade prefix's integer filter (so the filter accepts every integer solution); every generator of each
    residue lattice lies in its basis's span; and the residue vectors of every example of order ORDER in
    EXAMPLES lie in the lattices (which do not depend on the length when f(-1) = 0, asserted).  Then, at ORDER - 1,
    follow the example of that order and length N down the cascade with the real split: at each split its
    image under the stabilizer must land in a child of its own (so the LP did not claim its relaxation is
    infeasible), and solve_node with the box pinned to it must find it FEASIBLE (so it satisfies certbb's rows of
    that node exactly); at ORDER, solve_node on the final node, pinned to it, must say INFEASIBLE (so it breaks them)."""
    rows, _ = moment_rows(ORDER)
    for i in range(1, len(CASCADE) + 1):
        A = rows + sum((count_rows(M) for M in CASCADE[:i]), ())
        assert all(integer_system(ORDER, CASCADE[:i]).solvable([row[p] for row in A]) for p in range(N))
    bs = [from_hex(h, m) for (n, m), h in EXAMPLES.items() if m == ORDER]
    assert bs and all(exact_order(b) == ORDER and sum(t * (-1) ** p for p, t in enumerate(b)) == 0 for b in bs)
    for M in sorted(set(CASCADE)):
        span = ExactSystem(lattice_basis(M, ORDER))
        poly = lattice_poly(ORDER)
        gens = [[sum(c for t, c in enumerate(poly) if (t + k) % M == r) for r in range(M)] for k in range(M)]
        assert all(span.solvable(g) for g in gens)
        assert all(span.solvable([sum(b[p] for p in range(r, len(b), M)) for r in range(M)]) for b in bs)
    m = ORDER - 1
    # TODO: error copy; says EXAMPLES has no example of length N and order ORDER-1, which the control needs
    assert (N, m) in EXAMPLES, f'Claude: "EXAMPLES has no example of length {N} and order {m}"'
    a, node = from_hex(EXAMPLES[N, m], m), ()
    assert len(a) == N and exact_order(a) == m
    for M in CASCADE:
        gs = stabilizer(node)
        v = rep(gs, M, counts(a, M))
        a = next(act_seq(g, a) for g in gs if act(g, M, counts(a, M)) == v)
        node = node + ((M, (v,)),)
        assert node in split(m, node[:-1])
        x = [(t + 1) // 2 for t in a]
        assert solve_node(m, node, 1, x, x)[:2] == ('FEASIBLE', a)
    assert solve_node(ORDER, node, 1, x, x)[0] == 'INFEASIBLE'


def main():
    # TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
    if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
    # TODO: error copy; says how to run the script: with the length N and the order as its two arguments
    assert len(sys.argv) == 3, 'Claude: "usage: python3 overnight_v5.py N ORDER"'
    configure(int(sys.argv[1]), int(sys.argv[2]))
    run()


def run():
    """The run that configure() set up: the control, the search, and its outcome, all in the log."""
    t0 = time.time()
    journal = Journal(JOURNAL)
    # TODO: start line; says: start: n, order at least, processes, certbb's budgets in LP solves by depth and at least so many per pool member, the HiGHS build, split moduli, and how many verdicts the journal already holds
    log_to_file(f'Claude: "start: n = {N}, order at least {ORDER}, {PROCESSES} processes, budgets {list(BUDGET)} '
                f'(LP solves; a pool at least {POOL_BUDGET} per member), HiGHS {certbb.HIGHS}, split moduli {list(CASCADE)}, '
                f'{len(journal.records)} earlier verdicts"')
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
        # TODO: says every node closed, so no +-1 sequence of length N has order at least ORDER, and that this rests on certificates checked in exact integer arithmetic; with the count of closed nodes and the hours taken
        log_to_file(f'Claude: "ALL NODES CLOSED ({res["closed"]}, {hours:.1f} h): no ±1 sequence of length {N} has order '
                    f'at least {ORDER}; this rests on certificates checked in exact integer arithmetic."')


# A fingerprint of the code that decides verdicts, taken as imported (see header()): this file's functions that do,
# and all of certbb.py.
CODE = hashlib.sha1((''.join(inspect.getsource(f) for f in (
    lattice_poly, lattice_basis, moment_rows, moments, count_rows, ExactSystem, integer_system, admissible, act,
    stabilizer, rep, split, solve_node, node_key, work, search)) + inspect.getsource(certbb)).encode()).hexdigest()


if __name__ == '__main__':
    main()
