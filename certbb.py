"""certbb: certified branch and bound for one node of overnight_v5's search.

A node's 0/1 points are searched by an LP-based branch and bound in floating point (HiGHS), but a box is closed only
by a certificate that exact integer arithmetic checks, so an INFEASIBLE verdict never rests on floating point.  The
search emits a proof, a stream of tokens, which a Check replays from scratch as the tokens come, keeping none of them;
Check shares only node_rows, lower_bound and fixed with the search.  Every check in the exact part raises ProofError
explicitly, and certbb refuses to be imported under python -O, which would skip the assert statements of the rest.

Vocabulary, each term defined once here:
  moments      the exact moment rows of an order, a Moments built from overnight_v5.moment_rows(order) = (W, rhs):
               W[k] the coefficients of row k at positions 0..N-1, rhs[k] its right-hand side.
  box          lo_p <= x_p <= hi_p for each position p, with lo_p, hi_p in {0, 1}: the 0/1 points a branch has left.
  choice       one count vector per constraint (M, V) of a node; a pool (several vectors in V) offers several.
  rows         the exact equations a.x = beta of a choice in the 0/1 variables x: the moment rows, then for each
               pair (M, v), one count row per class r mod M, with beta = v[r].  These are overnight_v4.build_model's
               moment equations and count constraints; its lattice cuts are left out (see the note below).
  certificate  integer multipliers n, one per row, whose bound lower_bound(rows, lo, hi, n) is positive: then no x
               in the box satisfies the rows.
  proof        a stream of tokens in depth-first order, for each choice in turn (itertools.product order):
               ('B', p) splits the box on x_p and is followed by the proof for x_p = 0, then the one for x_p = 1;
               ('L', n) closes the box with the certificate n.
  proof sha1   the sha1 of the concatenated bytes repr(token).encode() of a stream's tokens, in order.
  verdict      INFEASIBLE (a complete proof, each certificate checked as it was made), FEASIBLE (with a 0/1 point
               that satisfies every row exactly), or UNKNOWN (a limit came first).
  rule         how a split picks its position among the free ones that the LP point leaves fractional (all free
               ones for 'static'): 'frac' the most fractional; 'ends' the farthest from the middle of 0..N-1, the
               most fractional of those; 'static' the farthest from the middle, then the lowest.

The lattice cuts: overnight_v4.build_model also asks that the residue sums of a = 2x - 1 mod each cut modulus lie in a
lattice.  Every 0/1 point satisfying the moment equations satisfies them (that is how lattice_basis derives them), so
leaving them out changes no node's set of 0/1 solutions; and leaving out constraints could only add points, never
close a box that holds a solution.
"""
# TODO: error copy; says certbb will not be imported under python -O, which would skip its assert statements
if not __debug__: raise ImportError('Claude: "certbb refuses to run under python -O, which skips assert statements"')
import itertools, math, hashlib
import numpy as np
import scipy.optimize._highspy._core as highs

SCALE_BITS = 50              # a dual ray is rounded to integers of about this many bits
FRAC = 1e-9                  # an LP value within this of 0 or 1 counts as integral (only for choosing a split)
ITERATIONS = 20000           # simplex iterations allowed per LP solve (a typical solve takes 25 to 100)
HIGHS = f'{highs._Highs().version()} ({highs._Highs().githash()})'     # the HiGHS build: version (git hash)


# ---------- the exact part: rows, bounds, and the proof checker ----------

class ProofError(Exception):
    """What the exact part raises for anything an INFEASIBLE verdict could not rest on: a proof that Check does not
    accept, a certificate of solve's own that fails, or rows and multipliers that do not fit together."""


def require(ok, what):
    """Raise ProofError(what) unless ok: an explicit check, which python -O cannot skip as it skips assert."""
    if not ok: raise ProofError(what)


class Moments:
    """The moment rows of one order, exact: W and rhs as given, N = len(W[0]), and sparse, the rows as (a, beta)
    pairs with a the nonzero (position, coefficient) pairs."""
    def __init__(self, W, rhs):
        self.W, self.rhs, self.N = W, rhs, len(W[0])
        self.sparse = tuple((tuple((p, c) for p, c in enumerate(w) if c), b) for w, b in zip(W, rhs, strict=True))


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


class Check:
    """A proof checked as it is made: feed(token) for each token in turn, as solve emits them, then end().  Each raises
    ProofError at the first sign that the tokens are not a proof that no 0/1 point of the box (by default all of
    {0,1}^N) satisfies any choice of the node's rows: a token that is wrong, an end that comes too early, a token
    after the last box.  It keeps no token, only the current choice's rows, the boxes still open for it (at most one
    more than the depth of the proof tree), and sha1, a running hashlib.sha1 of the tokens (see 'proof sha1').  This,
    node_rows, lower_bound and fixed are all an INFEASIBLE verdict rests on."""
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
            boxes = [(list(lo or [0] * N), list(hi or [1] * N))]
            # TODO: error copy; says the box to check is not made of zeros and ones with each lower end at most its upper end
            require(all(type(l) is int and type(u) is int and 0 <= l <= u <= 1 for l, u in zip(*boxes[0], strict=True)),
                    'Claude: "the box is not a 0/1 box"')
            while boxes:                                      # depth first, x_p = 0 before x_p = 1
                l, u = boxes.pop()
                token = yield
                # TODO: error copy; says the proof stopped before every box was closed
                require(token is not None, 'Claude: "the proof ends early"')
                # TODO: error copy; says a token of the proof is not a pair (kind, argument)
                require(type(token) is tuple and len(token) == 2, 'Claude: "a token is not a pair"')
                kind, arg = token
                if kind == 'L':
                    # TODO: error copy; says a certificate is not a list of whole numbers, one per row
                    require(type(arg) is list and len(arg) == len(rows) and all(type(m) is int for m in arg),
                            'Claude: "a certificate is not one integer per row"')
                    # TODO: error copy; says a certificate's exact bound is not positive, so it closes nothing
                    require(lower_bound(rows, l, u, arg) > 0, 'Claude: "a certificate fails"')
                else:
                    # TODO: error copy; says a token neither closes the box nor splits it on a position still free
                    require(kind == 'B' and type(arg) is int and 0 <= arg < N and l[arg] == 0 and u[arg] == 1,
                            'Claude: "a split does not split a free position"')
                    boxes += [fixed(l, u, arg, 1), fixed(l, u, arg, 0)]
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
    """HiGHS's LP for the choices of a node, with linearly independent rows: the moment rows as moment_transform gives
    them, then the count rows of each modulus that divides no other modulus of the node, all classes but the last (the
    moment row of degree 0 already says the counts sum to N/2), their right-hand sides set per choice by set_counts.
    row[i] is the index in node_rows of the i-th count row, and slot[i] its (constraint, class) pair.
    The box goes in as column bounds.  Dual simplex, no presolve, one thread, warm-started, at most ITERATIONS simplex
    iterations per solve (a solve that stops there closes nothing, so its box is split).  Primal simplex used about
    20% less CPU per LP on leaves L2 and L6, but on another leaf one primal solve ran for minutes."""
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
        top = float(np.abs(y).max())
        assert 0 < top < float('inf'), top                    # HiGHS said it has a ray
        Y = [round(math.ldexp(t / top, SCALE_BITS)) for t in y]
        k = self.k
        n = [sum(Y[i] * self.T[i][j] << (self.smax - self.s[i]) for i in range(k)) for j in range(k)]
        n += [0] * (self.rows_total - k)
        for i, t in zip(self.row, Y[k:], strict=True):
            n[i] = t << self.smax
        return n


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


def solve(moments, node, lps, emit, lo=None, hi=None, rule='ends'):
    """The verdict on a node within lps LP solves, and the 0/1 point of a FEASIBLE verdict.  Each proof token goes to
    emit as it is made, and only after lower_bound has found its certificate's bound positive, so no unchecked
    certificate leaves solve.  Returns (verdict, x, stats)."""
    N = moments.N
    stats = dict(lp=0, leaves=0, splits=0, cert_fail=0, lp_other=0, max_depth=0, explored=0.0, choices=0)
    lp = Lp(moments, [M for M, _ in node])
    for choice in itertools.product(*(V for _, V in node)):
        stats['choices'] += 1
        pairs = [(M, v) for (M, _), v in zip(node, choice, strict=True)]
        rows = node_rows(moments, pairs)
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
            p = choose(x, l, u, rule)
            emit(('B', p))
            stats['splits'] += 1
            stack += [fixed(l, u, p, 1) + (depth + 1, lp.H.getBasis()), fixed(l, u, p, 0) + (depth + 1, None)]
    return 'INFEASIBLE', None, stats
