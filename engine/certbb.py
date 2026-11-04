"""certbb: certified branch and bound for one node of overnight_v5's search.

A node's 0/1 points are searched by an LP-based branch and bound in floating point (HiGHS), but a box is closed only
by a certificate that exact integer arithmetic checks, so an INFEASIBLE verdict never rests on floating point.  The
search emits a proof, a stream of tokens, which a Check replays from scratch as the tokens come, keeping none of them;
Check shares only node_rows, lower_bound, fixed and cuts with the search.  Every check in the exact part raises ProofError
explicitly, and certbb refuses to be imported under python -O, which would skip the assert statements of the rest.

Vocabulary, each term defined once here:
  moments      the exact moment rows of an order, a Moments built from overnight_v5.moment_rows(order) = (W, rhs):
               W[k] the coefficients of row k at positions 0..N-1, rhs[k] its right-hand side; then any further rows
               given as more (boxsplit's outside node has one, a count row), which every part below takes as one
               more row but the width test, whose directions are those of the moment rows and the count rows.
  box          lo_p <= x_p <= hi_p for each position p, with lo_p, hi_p in {0, 1}: the 0/1 points a branch has left,
               under the cut rows of its path.
  choice       one count vector per constraint (M, V) of a node; a pool (several vectors in V) offers several.
  rows         the exact equations a.x = beta of a choice in the 0/1 variables x: the moment rows, then for each
               pair (M, v), one count row per class r mod M, with beta = v[r].  These are overnight_v4.build_model's
               moment equations and count constraints; its lattice cuts are left out (see the note below).
  cut          ('D', u, c), u a list of N integers and c an integer: splits a box into the side u.x <= c (proved
               first) and the side u.x >= c + 1, which between them hold every integer point of the box; u must take
               a value <= c and a value > c on the box, so that the cut cuts it (cuts(u, c, lo, hi); as a split must
               split a free position).
  path         the cut rows a box lies under, one per cut on the way down to it: (sign, a, beta) with a the nonzero
               (position, coefficient) pairs of u, sign +1 for the side a.x >= beta (beta = c + 1) and -1 for the
               side a.x <= beta (beta = c).
  certificate  integer multipliers n, one per row and then one per path row, whose bound lower_bound(rows + path
               rows, lo, hi, n) is positive: then no x in the box under the path satisfies the rows.  A path row's
               multiplier has the row's sign or is 0, so that m (beta - a.x) <= 0 for every x on that side; the
               rows' terms are 0 for every x satisfying them; so the sum is <= 0 at any such x, against the bound.
  proof        a stream of tokens in depth-first order, for each choice in turn (itertools.product order):
               ('B', p) splits the box on x_p and is followed by the proof for x_p = 0, then the one for x_p = 1;
               ('D', u, c) cuts the box and is followed by the proof for u.x <= c, then the one for u.x >= c + 1;
               ('L', n) closes the box with the certificate n.
  proof sha1   the sha1 of the concatenated bytes repr(token).encode() of a stream's tokens, in order.
  verdict      INFEASIBLE (a complete proof, each certificate checked as it was made), FEASIBLE (with a 0/1 point
               that satisfies every row exactly), or UNKNOWN (a limit came first).
  rule         how a split picks its position among the free ones that the LP point leaves fractional (all free
               ones for 'static'): 'frac' the most fractional; 'ends' the farthest from the middle of 0..N-1, the
               most fractional of those; 'static' the farthest from the middle, then the lowest.
  direction    an integer vector u of width.py, with the float row w and the offset kappa for which u.x = w.x + kappa
               on the choice's moment rows and count rows, and so on any further rows too, which only narrow the LP's
               polytope: the LP sees w.x, which stays small.
  width test   at the root box of a choice whose LP is Optimal, with room in the budget for two more LP solves: for
               each direction in turn, the least and greatest value of w.x over the LP's polytope (two LP solves of
               the Guide's own Lp, with the direction row added), and so of u.x; when no integer lies between them,
               the direction is thin, the two sides' LPs (u.x <= c and u.x >= c + 1, c the integer below) are
               infeasible, and their dual rays, made integer as Lp.multipliers makes the search's, carried from the
               row w to the row u by the direction's exact multipliers, are checked as Check checks them (the sign
               on the cut row, lower_bound), and the cut as Check checks it (cuts); all passing, the cut and the two
               certificates are emitted and the box is closed in 3 tokens.  Otherwise the next direction, and after
               the last the branch and bound exactly as without the test.  Its range solves, and the side solves of
               a thin direction that did not close, are counted in the width stat, not in the LP-solve budget; the
               sides of a cut that closed are the two leaves' solves and count in both lp and leaves.  The test
               costs at most 4 dim LP solves per choice, dim the number of directions: two range solves per
               direction and two side solves per thin direction that did not close, such as one whose range in
               exact arithmetic touches an integer that the float range falls short of (none at the 240@11 nodes
               measured; up to 23 per node at 304@9).

The lattice cuts: overnight_v4.build_model also asks that the residue sums of a = 2x - 1 mod each cut modulus lie in a
lattice.  Every 0/1 point satisfying the moment equations satisfies them (that is how lattice_basis derives them), so
leaving them out changes no node's set of 0/1 solutions; and leaving out constraints could only add points, never
close a box that holds a solution.
"""
# TODO: error copy; says certbb will not be imported under python -O, which would skip its assert statements
if not __debug__: raise ImportError('Claude: "certbb refuses to run under python -O, which skips assert statements"')
import itertools, math, hashlib
from functools import cached_property
from types import MappingProxyType
import numpy as np
import scipy.optimize._highspy._core as highs
import width

SCALE_BITS = 50              # a dual ray is rounded to integers of about this many bits
FRAC = 1e-9                  # an LP value within this of 0 or 1 counts as integral (only for choosing a split)
ITERATIONS = 20000           # simplex iterations allowed per LP solve (a typical solve takes 25 to 100)
INF = float('inf')           # a free bound of an LP row
ARITY = {'B': 2, 'L': 2, 'D': 3}      # the length of a token of each kind
HIGHS = f'{highs._Highs().version()} ({highs._Highs().githash()})'     # the HiGHS build: version (git hash)


# ---------- the exact part: rows, bounds, and the proof checker ----------

class ProofError(Exception):
    """What the exact part raises for anything an INFEASIBLE verdict could not rest on: a proof that Check does not
    accept, a certificate of solve's own that fails, or rows and multipliers that do not fit together."""


def require(ok, what):
    """Raise ProofError(what) unless ok: an explicit check, which python -O cannot skip as it skips assert."""
    if not ok: raise ProofError(what)


class Moments:
    """The moment rows of one order, exact, then the further rows more = (W', rhs') (see 'moments'): order = len(W),
    W and rhs the moment rows' followed by more's, N = len(W[0]), and sparse, all the rows as (a, beta) pairs with a
    the nonzero (position, coefficient) pairs."""
    def __init__(self, W, rhs, more=((), ())):
        self.order = len(W)
        self.W, self.rhs, self.N = W + more[0], rhs + more[1], len(W[0])
        self.sparse = tuple((tuple((p, c) for p, c in enumerate(w) if c), b) for w, b in zip(self.W, self.rhs, strict=True))


def node_rows(moments, choice):
    """The rows of a choice: (a, beta) pairs, a sparse as (position, coefficient) pairs, all exact integers."""
    rows = list(moments.sparse)
    for M, v in choice:
        # TODO: error copy; says a count vector of the node is not M whole numbers for its modulus M
        require(len(v) == M and all(type(t) is int for t in v), f'Claude: "a count vector is not {M} integers"')
        rows += [([(p, 1) for p in range(r, moments.N, M)], v[r]) for r in range(M)]
    return rows


def lower_bound(rows, lo, hi, n):
    """For every x in the box, sum_i n_i (beta_i - a_i.x) is at least the number returned.  Every x satisfying the
    rows makes that sum 0, so a positive bound shows that no x in the box satisfies them.  Exact integers."""
    # TODO: error copy; says the multipliers and the rows, or the box's two ends, differ in length
    require(len(n) == len(rows) and len(lo) == len(hi), 'Claude: "multipliers, rows and box do not fit together"')
    g = [0] * len(lo)
    beta = 0
    for (a, b), m in zip(rows, n, strict=True):
        beta += m * b
        for p, c in a: g[p] -= m * c
    return beta + sum(min(t * l, t * u) for t, l, u in zip(g, lo, hi, strict=True))


def fixed(lo, hi, p, t):
    """The box with x_p fixed to t."""
    lo, hi = lo[:], hi[:]
    lo[p] = hi[p] = t
    return lo, hi


def cuts(u, c, lo, hi):
    """Does the cut (u, c) cut the box: does u.x take a value <= c and a value > c on it (see 'cut').  Exact integers."""
    return (sum(min(t * l, t * h) for t, l, h in zip(u, lo, hi, strict=True)) <= c
            < sum(max(t * l, t * h) for t, l, h in zip(u, lo, hi, strict=True)))


class Check:
    """A proof checked as it is made: feed(token) for each token in turn, as solve emits them, then end().  Each raises
    ProofError at the first sign that the tokens are not a proof that no 0/1 point of the box (by default all of
    {0,1}^N) satisfies any choice of the node's rows: a token that is wrong, an end that comes too early, a token
    after the last box.  It keeps no token, only the current choice's rows, the boxes still open for it with their
    paths (at most one more than the depth of the proof tree), and sha1, a running hashlib.sha1 of the tokens (see
    'proof sha1').  This, node_rows, lower_bound, fixed and cuts are all an INFEASIBLE verdict rests on."""
    def __init__(self, moments, node, lo=None, hi=None):
        self.sha1 = hashlib.sha1()
        self.steps = self.replay(moments, node, lo, hi)
        next(self.steps)                                      # run up to the first token

    def replay(self, moments, node, lo, hi):
        """The checker proper: a generator that takes the tokens one at a time by send, then None for the end, and
        after the end of a complete proof waits at one more yield, so that end() returns."""
        N = moments.N
        for choice in itertools.product(*(V for _, V in node)):
            rows = node_rows(moments, [(M, v) for (M, _), v in zip(node, choice, strict=True)])
            boxes = [(list(lo or [0] * N), list(hi or [1] * N), [])]      # (lo, hi, path)
            # TODO: error copy; says the box to check is not made of zeros and ones with each lower end at most its upper end
            require(all(type(l) is int and type(u) is int and 0 <= l <= u <= 1 for l, u in zip(*boxes[0][:2], strict=True)),
                    'Claude: "the box is not a 0/1 box"')
            while boxes:                                      # depth first, x_p = 0 before x_p = 1, u.x <= c before u.x >= c + 1
                l, u, path = boxes.pop()
                token = yield
                # TODO: error copy; says the proof stopped before every box was closed
                require(token is not None, 'Claude: "the proof ends early"')
                # TODO: error copy; says a token of the proof is not a tuple starting with B, L or D and of that kind's length
                require(type(token) is tuple and len(token) >= 2 and type(token[0]) is str and len(token) == ARITY.get(token[0]),
                        'Claude: "a token is not a B, L or D token of its length"')
                kind, arg = token[0], token[1]
                if kind == 'L':
                    # TODO: error copy; says a certificate is not a list of whole numbers, one per row and per path row
                    require(type(arg) is list and len(arg) == len(rows) + len(path) and all(type(m) is int for m in arg),
                            'Claude: "a certificate is not one integer per row"')
                    # TODO: error copy; says a multiplier on a cut row has the wrong sign for that row's side
                    require(all(s * m >= 0 for m, (s, _, _) in zip(arg[len(rows):], path, strict=True)),
                            'Claude: "a path multiplier has the wrong sign"')
                    # TODO: error copy; says a certificate's exact bound is not positive, so it closes nothing
                    require(lower_bound(rows + [(a, beta) for _, a, beta in path], l, u, arg) > 0, 'Claude: "a certificate fails"')
                elif kind == 'B':
                    # TODO: error copy; says a split token does not split a position still free
                    require(type(arg) is int and 0 <= arg < N and l[arg] == 0 and u[arg] == 1,
                            'Claude: "a split does not split a free position"')
                    boxes += [fixed(l, u, arg, 1) + (path,), fixed(l, u, arg, 0) + (path,)]
                else:
                    c = token[2]
                    # TODO: error copy; says a cut token is not a list of N whole numbers and a whole number
                    require(type(arg) is list and len(arg) == N and all(type(t) is int for t in arg) and type(c) is int,
                            f'Claude: "a cut is not {N} integers and an integer"')
                    # TODO: error copy; says a cut leaves one of its sides without a point of the box, so it cuts nothing
                    require(cuts(arg, c, l, u), 'Claude: "a cut does not cut the box"')
                    a = [(p, t) for p, t in enumerate(arg) if t]
                    boxes += [(l, u, path + [(1, a, c + 1)]), (l, u, path + [(-1, a, c)])]
        # TODO: error copy; says the proof has tokens after its last box was closed
        require((yield) is None, 'Claude: "the proof goes on after the last box"')
        yield

    def feed(self, token):
        """Check the next token."""
        self.sha1.update(repr(token).encode())
        self.steps.send(token)

    def end(self):
        """Raise ProofError unless the tokens fed so far make a complete proof."""
        self.steps.send(None)


def verify(moments, node, proof, lo=None, hi=None):
    """Raise ProofError unless proof, any iterable of tokens, is a complete proof for the node and the box (see Check);
    returns its proof sha1."""
    check = Check(moments, node, lo, hi)
    for token in proof: check.feed(token)
    check.end()
    return check.sha1.hexdigest()


# ---------- the floating-point guide: the LP ----------

def moment_transform(W):
    """An integer matrix T and shifts s with rows (T[k].W) / 2^s[k] close to orthonormal, so the LP sees well-scaled
    rows that are exact integer combinations of the moment rows W, scaled by powers of 2."""
    Wf = np.array([[float(c) for c in w] for w in W])
    norms = np.linalg.norm(Wf, axis=1)
    _, R = np.linalg.qr((Wf / norms[:, None]).T)
    Tf = np.linalg.inv(R).T / norms[None, :]
    s = [52 - math.frexp(float(np.abs(row).max()))[1] for row in Tf]
    T = [[round(math.ldexp(float(t), sk)) for t in row] for row, sk in zip(Tf, s, strict=True)]
    return T, s


class Lp:
    """HiGHS's LP for the choices of a node, with linearly independent rows: the moment rows and any further rows (all
    of moments.W) as moment_transform gives them, then the count rows of each modulus that divides no other modulus of
    the node, all classes but the last (the moment row of degree 0 already says the counts sum to N/2), their
    right-hand sides set per choice by set_counts.
    row[i] is the index in node_rows of the i-th count row, and slot[i] its (constraint, class) pair.
    The box goes in as column bounds.  Dual simplex, no presolve, one thread, warm-started, at most ITERATIONS simplex
    iterations per solve (a solve that stops there closes nothing, so its box is split).  Primal simplex used about
    20% less CPU per LP on leaves L2 and L6, but on another leaf one primal solve ran for minutes.
    For the width test (the Guide's own Lp), direction adds the direction row w.x after the rows above, free; extremes
    minimizes and maximizes it, side bounds it and solves."""
    def __init__(self, moments, moduli):
        W, rhs, N = moments.W, moments.rhs, moments.N
        T, s = moment_transform(W)
        self.T, self.s, self.smax, self.k = T, s, max(s), len(W)
        A, b = [], []
        for Tk, sk in zip(T, s, strict=True):
            row = [sum(t * w[p] for t, w in zip(Tk, W)) for p in range(N)]
            A.append([math.ldexp(float(c), -sk) for c in row])
            b.append(math.ldexp(float(sum(t * r for t, r in zip(Tk, rhs))), -sk))
        self.row, self.slot, self.moduli, i = [], [], tuple(moduli), self.k
        for j, M in enumerate(moduli):
            kept = range(M - 1) if all(P % M or P == M for P in moduli) else ()
            for r in kept:
                A.append([float(p % M == r) for p in range(N)])
                b.append(0.0)
                self.row.append(i + r)
                self.slot.append((j, r))
            i += M
        self.rows_total = i
        self.A, self.b = np.array(A), np.array(b)
        assert np.linalg.matrix_rank(self.A) == len(b), 'the LP rows are not independent'
        H = self.H = highs._Highs()
        H.setOptionValue('output_flag', False)
        H.setOptionValue('presolve', 'off')
        H.setOptionValue('threads', 1)
        H.setOptionValue('simplex_strategy', 1)
        H.setOptionValue('simplex_iteration_limit', ITERATIONS)
        lp = highs.HighsLp()
        lp.num_col_, lp.num_row_ = N, len(b)
        lp.col_cost_ = np.zeros(N)
        lp.col_lower_, lp.col_upper_ = np.zeros(N), np.ones(N)
        lp.row_lower_, lp.row_upper_ = self.b.copy(), self.b.copy()
        cols = [np.nonzero(self.A[:, j])[0] for j in range(N)]
        lp.a_matrix_.format_ = highs.MatrixFormat.kColwise
        lp.a_matrix_.start_ = np.cumsum([0] + [len(c) for c in cols]).astype(np.int32)
        lp.a_matrix_.index_ = np.concatenate(cols).astype(np.int32)
        lp.a_matrix_.value_ = np.concatenate([self.A[c, j] for j, c in enumerate(cols)])
        lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = N, len(b)
        assert H.passModel(lp) == highs.HighsStatus.kOk
        self.lo, self.hi = np.zeros(N), np.ones(N)
        self.N, self.cols, self.w = N, np.arange(N, dtype=np.int32), None      # w: the direction row's coefficients

    def set_counts(self, choice):
        """Make the count rows say choice's counts; choice's moduli must be this LP's."""
        assert tuple(M for M, _ in choice) == self.moduli
        for i, (j, r) in enumerate(self.slot, self.k):
            t = float(choice[j][1][r])
            self.H.changeRowBounds(i, t, t)

    def solve(self, lo, hi, basis=None):
        """HiGHS's status word for the box ('Optimal', 'Infeasible', or another), with the LP point or the dual ray,
        warm-started from basis when given, else from the last solve."""
        lo, hi = np.array(lo, float), np.array(hi, float)
        idx = np.nonzero((lo != self.lo) | (hi != self.hi))[0].astype(np.int32)
        if len(idx):
            self.H.changeColsBounds(len(idx), idx, lo[idx], hi[idx])
        self.lo, self.hi = lo, hi
        if basis is not None:
            self.H.setBasis(basis)
        self.H.run()
        status = self.H.modelStatusToString(self.H.getModelStatus())
        if status == 'Optimal':
            return status, np.array(self.H.getSolution().col_value)
        if status == 'Infeasible':
            _, has, ray = self.H.getDualRay()
            return status, np.array(ray) if has else None
        return status, None

    def multipliers(self, y):
        """Integer multipliers on the exact rows (node_rows order) for the dual ray y of the LP rows: y rounded to
        SCALE_BITS-bit integers, carried through T, all scaled by 2^smax, 0 on rows the LP leaves out.  Any integers
        would be sound; these make the exact combination match the floating one."""
        return self.carry(self.scaled(y))

    def scaled(self, y):
        """y as SCALE_BITS-bit integers, the largest entry 2^SCALE_BITS."""
        top = float(np.abs(y).max())
        assert 0 < top < float('inf'), top                    # HiGHS said it has a ray
        return [round(math.ldexp(t / top, SCALE_BITS)) for t in y]

    def carry(self, Y):
        """Integer multipliers on the exact rows (node_rows order) for integer multipliers Y on the LP rows above
        (the moment rows carried through T, all scaled by 2^smax; 0 on rows the LP leaves out)."""
        k = self.k
        n = [sum(Y[i] * self.T[i][j] << (self.smax - self.s[i]) for i in range(k)) for j in range(k)]
        n += [0] * (self.rows_total - k)
        for i, t in zip(self.row, Y[k:], strict=True):
            n[i] = t << self.smax
        return n

    def direction(self, w):
        """Make the direction row w.x, free: the row after the rows above, replacing the last direction's."""
        base = len(self.b)
        assert self.H.getNumRow() == base + (self.w is not None)
        if self.w is not None:
            self.H.deleteRows(1, np.array([base], dtype=np.int32))
        self.H.addRows(1, np.array([-INF]), np.array([INF]), self.N, np.array([0], dtype=np.int32), self.cols, w)
        self.w = w

    def extremes(self, lo, hi):
        """The least and greatest value of the direction row over the box, from two Optimal solves; None when a
        solve ended otherwise (it claims nothing, and the direction is skipped)."""
        out = []
        for sign in (1.0, -1.0):
            self.H.changeColsCost(self.N, self.cols, sign * self.w)
            status, x = self.solve(lo, hi)
            out.append((status, x))
        self.H.changeColsCost(self.N, self.cols, np.zeros(self.N))
        return None if any(st != 'Optimal' for st, _ in out) else (float(self.w @ out[0][1]), float(self.w @ out[1][1]))

    def side(self, lo_w, hi_w, lo, hi):
        """solve with the direction row bounded by lo_w <= w.x <= hi_w (the objective 0)."""
        self.H.changeRowBounds(len(self.b), lo_w, hi_w)
        return self.solve(lo, hi)


# ---------- the search ----------

def point_certificate(rows, x):
    """For a box holding the single point x, which breaks some row: n = +-1 on the first row it breaks."""
    for i, (a, b) in enumerate(rows):
        d = b - sum(c * x[p] for p, c in a)
        if d:
            return [0] * i + [1 if d > 0 else -1] + [0] * (len(rows) - i - 1)
    return None


def choose(x, lo, hi, rule):
    """The position to split on (see 'rule'); positions the LP point x leaves fractional come first."""
    lo, hi = np.array(lo), np.array(hi)
    free = lo < hi
    frac = free & (x > FRAC) & (x < 1 - FRAC) if x is not None and rule != 'static' else free
    cand = np.nonzero(frac if frac.any() else free)[0]
    xs = x[cand] if x is not None else np.full(len(cand), 0.5)
    out = np.abs(cand - (len(lo) - 1) / 2)
    key = {'frac': (cand, np.abs(xs - 0.5)), 'ends': (np.abs(xs - 0.5), -out), 'static': (cand, -out)}[rule]   # last key sorts first
    return int(cand[np.lexsort(key)[0]])


class Guide:
    """The width test's instruments for the choices of one solve call: its own Lp (so that the search's keeps its
    state and warm starts untouched, and the branch and bound runs exactly as without the test) and the directions
    of width.py for the LP's exact moment rows and count rows A (keep: their node_rows indices; a further row is in
    the Lp and its certificates, not in A), both made at the first test (cached properties), the directions cached
    per process by width.directions."""
    def __init__(self, moments, lp):
        self.moments, self.moduli, self.keep = moments, lp.moduli, list(range(moments.order)) + list(lp.row)
        rows, A = node_rows(moments, [(M, (0,) * M) for M in lp.moduli]), []     # the coefficients: any choice's
        for i in self.keep:
            a, _ = rows[i]
            row = [0] * moments.N
            for p, c in a: row[p] = c
            A.append(tuple(row))
        self.A = tuple(A)

    @cached_property
    def lp(self): return Lp(self.moments, self.moduli)

    @cached_property
    def dirs(self): return width.directions(self.moments.order, self.moduli, self.A)

    def certificate(self, y, d):
        """Integer multipliers on the exact rows and then the direction row u of d, for the dual ray y of the Lp with
        d's row w: y scaled and carried as multipliers does, the row w's multiplier m carried to the row u by d's exact
        multipliers (w = u - A^T num / den, so m (beta - w.x) = m (beta' - u.x) + (m / den) sum num_i (A_i x - b_i)
        for beta = beta' - kappa), everything scaled by den."""
        Y = self.lp.scaled(y)
        n = [d.den * t for t in self.lp.carry(Y[:-1])]
        m = Y[-1] << self.lp.smax
        for i, z in zip(self.keep, d.num, strict=True): n[i] -= m * z
        return n + [d.den * m]

    def width_test(self, pairs, rows, l, u, emit, stats):
        """The width test (see the vocabulary) on the box, for the choice (its (M, v) pairs and its rows): the cut and
        its two certificates emitted and True when a thin direction closes the box, else False."""
        b = [rows[i][1] for i in self.keep]
        self.lp.set_counts(pairs)
        for d in self.dirs:
            self.lp.direction(d.w)
            span = self.lp.extremes(l, u)
            stats['width'] += 2
            if span is None:
                stats['width_other'] += 1
                continue
            kfloor, kfrac = width.offset(d, b)
            c = math.floor(span[1] + kfrac)
            if c < span[0] + kfrac:                                   # thin: no integer in [lo + kfrac, hi + kfrac]
                C = kfloor + c                                        # the cut: u.x <= C or u.x >= C + 1
                sparse = [(p, t) for p, t in enumerate(d.u) if t]
                certs = []
                for sign, bounds, beta in ((-1, (-INF, c - kfrac), C), (1, (c + 1 - kfrac, INF), C + 1)):
                    status, y = self.lp.side(*bounds, l, u)
                    n = self.certificate(y, d) if status == 'Infeasible' and y is not None else None
                    # Check's own conditions on a certificate (the sign could only be wrong if HiGHS's ray or extremes were)
                    certs.append(n if n is not None and sign * n[-1] >= 0 and lower_bound(rows + [(sparse, beta)], l, u, n) > 0 else None)
                if all(n is not None for n in certs) and cuts(d.u, C, l, u):      # Check's conditions on the three tokens
                    emit(('D', list(d.u), C))
                    for n in certs: emit(('L', n))
                    stats['lp'] += 2
                    stats['leaves'] += 2
                    stats['cuts'] += 1
                    return True
                stats['width'] += 2
                stats['cut_fail'] += 1
        return False


def solve(moments, node, lps, emit, lo=None, hi=None, rule='ends', certificates=MappingProxyType({})):
    """The verdict on a node within lps LP solves, and the 0/1 point of a FEASIBLE verdict.  Each proof token goes to
    emit as it is made, and only after lower_bound has found its certificate's bound positive, so no unchecked
    certificate leaves solve.  certificates maps a choice (one vector per constraint, as itertools.product gives them)
    to a certificate for its root box, made elsewhere (boxsplit's box split carries one over to the vectors it also
    rules out): it must close that box, a list of integers whose bound lower_bound finds positive (else ProofError),
    and it does so without an LP solve.  Returns (verdict, x, stats): lp counts the LP solves of boxes (the budget's:
    the search's, and the two sides of a cut that closed), given the choices closed by a given certificate, width the
    width test's other LP solves (see 'width test'), cuts the cuts emitted, cut_fail the thin directions whose sides
    did not both certify, width_other the range solves that ended neither Optimal nor otherwise usable."""
    N = moments.N
    stats = dict(lp=0, leaves=0, splits=0, cert_fail=0, lp_other=0, max_depth=0, explored=0.0, choices=0,
                 given=0, width=0, cuts=0, cut_fail=0, width_other=0)
    lp = Lp(moments, [M for M, _ in node])
    guide = Guide(moments, lp)
    for choice in itertools.product(*(V for _, V in node)):
        stats['choices'] += 1
        pairs = [(M, v) for (M, _), v in zip(node, choice, strict=True)]
        rows = node_rows(moments, pairs)
        if choice in certificates:
            n = certificates[choice]
            # TODO: error copy; says a certificate given for a choice is not integers whose bound closes its root box
            require(type(n) is list and all(type(m) is int for m in n)
                    and lower_bound(rows, list(lo or [0] * N), list(hi or [1] * N), n) > 0, 'Claude: "a given certificate fails"')
            emit(('L', n))
            stats['given'] += 1
            stats['leaves'] += 1
            stats['explored'] += 1.0
            continue
        lp.set_counts(pairs)
        stack = [(list(lo or [0] * N), list(hi or [1] * N), 0, None)]
        while stack:
            if stats['lp'] >= lps:
                return 'UNKNOWN', None, stats
            l, u, depth, basis = stack.pop()
            stats['max_depth'] = max(stats['max_depth'], depth)
            status, z = lp.solve(l, u, basis)
            stats['lp'] += 1
            n = None
            if status == 'Infeasible' and z is not None:
                n = lp.multipliers(z)
                n = n if lower_bound(rows, l, u, n) > 0 else None
                stats['cert_fail'] += n is None
            stats['lp_other'] += status not in ('Infeasible', 'Optimal')
            x = z if status == 'Optimal' else None
            if x is not None and all(t <= FRAC or t >= 1 - FRAC for t in x):
                xi = [round(t) for t in x]
                if point_certificate(rows, xi) is None:
                    return 'FEASIBLE', xi, stats
            if n is None and l == u:
                n = point_certificate(rows, l)
                if n is None:
                    return 'FEASIBLE', l, stats
                # TODO: error copy; says a certificate that solve made for a single point fails the exact check
                require(lower_bound(rows, l, u, n) > 0, 'Claude: "a point certificate fails"')
            if n is not None:
                emit(('L', n))
                stats['leaves'] += 1
                stats['explored'] += 2.0 ** -depth
                continue
            if depth == 0 and x is not None and stats['lp'] + 2 <= lps and guide.width_test(pairs, rows, l, u, emit, stats):
                stats['explored'] += 1.0
                continue
            p = choose(x, l, u, rule)
            emit(('B', p))
            stats['splits'] += 1
            stack += [fixed(l, u, p, 1) + (depth + 1, lp.H.getBasis()), fixed(l, u, p, 0) + (depth + 1, None)]
    return 'INFEASIBLE', None, stats
