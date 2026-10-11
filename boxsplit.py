#!/usr/bin/env python3
"""Box split: a third pass over the open leaves of an overnight_v5.py run, each split further by the moduli of
EXTENSION inside the count box of its LP relaxation, every piece closed by certbb on a proof checked in exact integer
arithmetic.

overnight_v5.py 304 9 left 8 leaves open at the bottom of its cascade (3, 5, 4, 7, 8, 9), each UNKNOWN at 10M LP
solves (2026-10-10).  Splitting them further by 11 and 13 as overnight_v5.split would is out of reach (some 10^7
admissible vectors per split; see SETTINGS there), but the LP relaxation of a leaf bounds each class's count to a range
of about 15 to 20 of its 28 values, the vectors inside that box are few (4066 for the first leaf by 11), and each
value outside it is excluded by one certificate of its own.  See scratch/strategy/reports/plan.md (step 1) and
verify_split.md: the prototype closed all 8 leaves in 5.8 CPU-minutes, against 63.6 worker-hours the run spent on them
without closing them.

Run:   nice -n 19 python3 -B boxsplit.py N ORDER
       It reads overnight_v5_N_ORDER_journal.jsonl next to this file, the run's journal, and never writes it; its own
       verdicts go to overnight_v5_N_ORDER_boxsplit_journal.jsonl, from which it resumes, and its lines to
       overnight_v5_N_ORDER_boxsplit.log.  overnight_v5.py and certbb.py are imported unchanged.
Quals: nice -n 19 python3 -B quals_boxsplit.py

Vocabulary: overnight_v5.py's terms (order, size, counts mod M, admissible, node, pool, split, cascade, G,
stabilizer, rep, budget, verdict, witness, open leaf) and certbb.py's (moments, rows, certificate, proof, proof
sha1) mean what they mean there; TOL and POOL_BUDGET are overnight_v5's.  Each new term is defined once here:
  driver          this program, which drives certbb over the open leaves' extension trees (dreeves's term, from the
                  plan).
  extension       EXTENSION[(N, ORDER)] = (MODULI, BUDGETS): the moduli that split an open leaf further, in order,
                  below the run's cascade, and certbb's budget in LP solves for an own child at each of them.
  count box       the integer box of a node's LP relaxation (overnight_v5.Relaxation) by M: for each class r mod M,
                  [ceil(lo_r - TOL), floor(hi_r + TOL)] clipped to [0, size(M, r)], lo_r and hi_r being GLOP's least and
                  greatest count in class r, each from an OPTIMAL solve (asserted; see count_box).  Not certbb's box,
                  which is per position.
  box split       a node's split by M restricted to its count box: the admissible vectors inside the box
                  (admissible_box, overnight_v5.admissible with that one more condition), through the same integer filter
                  and orbit reduction as overnight_v5.split, each a child of its own unless the LP claims its relaxation
                  infeasible, the rest in one pool; and one outside node per (class, value) outside the box.
  outside node    for a class r mod M and a value t outside the count box: the node's sequences with count t in class r.
                  certbb takes it as the node with the moments extended by that one count row (outside_moments), so its
                  LP, its certificates and its proof check all carry the row; its budget is POOL_BUDGET, one member's.
  piece           what the driver hands certbb: an own child, a pool, or an outside node.  Each has a record in the
                  driver's journal under its key: an own child's and a pool's as overnight_v5.node_key makes them, an
                  outside node's the node's key followed by M:r=t (outside_key).
  extension tree  of an open leaf: its box split by MODULI[0], each own child's verdict at BUDGETS[0], the box split by
                  MODULI[1] of each own child left UNKNOWN, and so on through MODULI.  It is closed when every pool,
                  every outside node and every own child at the last modulus is INFEASIBLE.  An own child UNKNOWN at
                  the last modulus would need a modulus that is not there: the driver says so and stops (nothing deeper
                  is built).
  control         the startup check.  First the exact checks overnight_v5.control makes at ORDER for the cascade, made
                  for the extension: every column of the moment-and-count matrix passes the integer filter of each
                  extended prefix (cascade + MODULI[:i]), and every generator of each extension modulus's residue
                  lattice, and the residue vector of every example of order ORDER, lies in its basis's span.  Then
                  that the known example of order ORDER - 1 and length N (overnight_v5.EXAMPLES) follows the extension
                  down: at each extension modulus its counts lie in the count box, it lands in an own child of the box
                  split, and for every class the outside node at its count, pinned to it, is FEASIBLE at ORDER - 1 and
                  INFEASIBLE at ORDER; certbb pinned to it says FEASIBLE at ORDER - 1 and INFEASIBLE at ORDER.

Soundness.  The run's journal closes every node but its open leaves (overnight_v5's argument).  For an open leaf the
driver shows that no sequence of order at least ORDER lies in its node, by induction down the extension tree.  A piece
with verdict INFEASIBLE holds no such sequence: certbb's proof, every certificate checked by certbb.Check in exact
integer arithmetic on the piece's exact rows, which for an outside node are the node's rows plus the one count row.
A record taken from the driver's journal on resume is INFEASIBLE or UNKNOWN (asserted in settle): the journal is
trusted as overnight_v5's is, and no other verdict, CLOSED say, is taken for one of certbb's.
For a node split by M, let a be a sequence of order at least ORDER in the node and v its counts mod M.  Some element g
of the node's stabilizer maps a to a sequence of the node, of the same order, whose counts are rep(gs, M, v); so let v
be that representative.  Then v is admissible and passes the integer filter, both necessary conditions, and either v
lies in the count box, so that admissible_box enumerates it (the box only prunes the back substitution: a vector is cut
exactly when one of its classes is outside the box; the quals pin admissible_box to overnight_v5.admissible) and it is
an own child or a pool member, a piece of the tree; or some class value v_r is outside the box, and a satisfies the
rows of the outside node (r, v_r), a piece of the tree.  GLOP's bounds and claims only sort the vectors among the
pieces: a bound that is wrong makes a piece that holds a sequence, which certbb cannot close, so the driver stops
(assert) or finds a witness; TOL only widens the box.  Nothing closes without a certificate.  A FEASIBLE verdict is a
sequence that satisfies the piece's rows exactly, checked by exact power sums: a witness, logged, and the end of the
driver.  So when the driver ends with every extension tree closed, no sequence of order at least ORDER lies in any
open leaf, and with the run's journal, none of length N exists.
"""
import os, sys, json, time, math, hashlib, inspect
from collections import Counter
from ortools.linear_solver import pywraplp
import overnight_v5 as v5
import certbb

# EXTENSION[(N, ORDER)] = (MODULI, BUDGETS), one entry per run this file can extend (see the vocabulary).
#   304@9: 11, then 13.  Both are coprime to the cascade's moduli, as certbb's Lp requires of the count rows it keeps;
#   16, 27 and 32 leave some 10^5 vectors inside the box (scratch/strategy/reports/explore_split.md).  Budgets: in the
#   prototype (verify_split.md), 23 of the 37 mod-11 own children of the 8 leaves closed in 3 to 107 LP solves and the
#   other 14 needed the split by 13, after which their 10 own grandchildren closed in 3 to 67; so a mod-11 child gets
#   10000, the run's budget above its bottom, and a mod-13 child 2000000, the run's first bottom budget.
EXTENSION = {(304, 9): ((11, 13), (10000, 2000000))}
CONTROL_CUT = 2          # the control takes the box split inside the box cut to within this of the example's counts
HERE = os.path.dirname(os.path.abspath(__file__))
MODULI = BUDGETS = JOURNAL = LOG = None       # set by configure()
assert all(len(budgets) == len(moduli) and all(type(b) is int and b >= 1 for b in budgets)
           for moduli, budgets in EXTENSION.values())


def configure(n, order):
    """Make this process's run the one for length n and order order: overnight_v5's configuration (the run's journal
    is its JOURNAL), EXTENSION[(n, order)], and the driver's own journal and log paths."""
    global MODULI, BUDGETS, JOURNAL, LOG
    v5.configure(n, order)
    # TODO: error copy; says EXTENSION has no entry for this length and order
    assert (n, order) in EXTENSION, f'Claude: "no extension for N = {n}, order {order}"'
    MODULI, BUDGETS = EXTENSION[n, order]
    JOURNAL = os.path.join(HERE, f'overnight_v5_{n}_{order}_boxsplit_journal.jsonl')
    LOG = os.path.join(HERE, f'overnight_v5_{n}_{order}_boxsplit.log')


def header():
    """The driver's journal header: overnight_v5's (its code fingerprint included: a record rests on its verdict code
    and certbb) under the tag boxsplit, plus boxsplit, a fingerprint of the driver's own verdict code (CODE)."""
    return v5.header() | {'tag': 'boxsplit', 'boxsplit': CODE}


def log_to_file(msg):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a') as fh: fh.write(line + '\n')


# ---------- messages (copy; kept out of CODE so that rewriting them never invalidates a journal) ----------

def say_split(key, M, box, own, pool, outside, failures, secs):
    # TODO: box-split line; says: {node} by M: the count box's widths per class, how many vectors inside it passed the filter and the orbit reduction, how many of them are own children, the pool's size, the number of outside nodes, the LP failures (GLOP solves whose status was neither OPTIMAL nor INFEASIBLE), and the seconds
    lo, hi = box
    return (f'{{{key}}} by {M}: Claude: "box widths {[h - l + 1 for l, h in zip(lo, hi)]}, {len(own) + len(pool)} vectors inside, '
            f'{len(own)} own children, pool {len(pool)}, {len(outside)} outside nodes, LP failures {failures} ({secs:.1f} s)"')


def say_outside(key, M, n, lps, secs):
    # TODO: says: {node} by M: all its outside nodes are INFEASIBLE, with their LP solves in all and the seconds
    return f'{{{key}}} by {M}: Claude: "{n} outside nodes INFEASIBLE ({lps} LP solves, {secs:.1f} s)"'


def say_piece(rec, secs):
    # TODO: per-piece line; says: {piece}: certbb's verdict (its own status word), its LP solves, and the seconds (none when the record was reused)
    return f'{{{rec["key"]}}}: {rec["verdict"]}; Claude: "{rec["lps"]} LP solves ({secs:.1f} s)"'


def say_not_closed(rec):
    # TODO: error copy; says a pool or an outside node, which the design expects to close, came back with another verdict
    return f'Claude: "{{{rec["key"]}}}: {rec["verdict"]}, not closed"'


def say_leaf(i, key):
    # TODO: says which open leaf (its number and node) the driver starts on
    return f'Claude: "leaf {i}: {{{key}}}"'


def say_leaf_closed(i, key, tally):
    # TODO: per-leaf summary line; says: leaf number and node: its extension tree closed, with its box splits, own children, pool members, outside nodes, certbb's LP solves, GLOP's solves and CPU seconds
    return (f'Claude: "leaf {i} {{{key}}}: extension tree closed: {tally["splits"]} box splits, {tally["own"]} own children, '
            f'{tally["pool"]} pool members, {tally["outside"]} outside nodes, {tally["lps"]} certbb LP solves, '
            f'{tally["glop"]} GLOP solves, {tally["cpu"]:.0f} CPU s"')


# ---------- the run's journal: its open leaves ----------

def parse_key(key):
    """The node of a journal key of one vector per modulus: the inverse of overnight_v5.node_key there, asserted by
    the round trip (a pool's key, M:#count:sha1, is no such key: ValueError)."""
    node = tuple((int(M), (tuple(int(t) for t in v[1:-1].split(',')),))
                 for M, v in (part.split(':') for part in key.split()))
    assert v5.node_key(node) == key
    return node


def open_leaves(journal):
    """The open leaves of the run's journal (an overnight_v5.Journal), as nodes: the keys whose latest verdict is
    UNKNOWN at the bottom of the cascade with one vector per modulus (a node there has no children, and a pool there
    is split into its members, which are such keys), in the order of their latest records, which is that of the run's
    'open:' log lines."""
    recs = [json.loads(line) for line in open(journal.path).read().splitlines()[1:]]
    latest = {rec['key']: i for i, rec in enumerate(recs)}
    keys = [k for k, rec in journal.records.items()
            if rec['verdict'] == 'UNKNOWN' and len(k.split()) == len(v5.CASCADE) and '#' not in k]
    return [parse_key(k) for k in sorted(keys, key=latest.get)]


class Journal(v5.Journal):
    """overnight_v5's Journal, its records, admit, reuse and put as they are, under the driver's header."""
    def __init__(self, path):
        self.path = path
        if not os.path.exists(path):                                 # a fresh run starts the journal
            with open(path, 'w') as fh: fh.write(json.dumps(header()) + '\n')
        lines = open(path).read().splitlines()
        # TODO: error copy; says this journal file was written by a run with a different configuration or code
        assert json.loads(lines[0]) == header(), f'Claude: "the journal {path} belongs to another configuration"'
        self.records = {}
        for rec in map(json.loads, lines[1:]): self.admit(rec)


# ---------- the box split ----------

def admissible_box(order, M, fixed, box):
    """overnight_v5.admissible inside the count box box = (lo, hi): the admissible count vectors mod M with
    lo[r] <= c_r <= hi[r] for every class r, sorted.  Its text is admissible's with one more condition in place(),
    which cuts a vector exactly when one of its classes is outside the box and prunes the back substitution there;
    quals_boxsplit pins it to admissible on the full box and on smaller ones."""
    lo, hi = box
    B = v5.lattice_basis(M, order)
    size = v5.size
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
        fits = abs(dr) <= s and (dr + s) % 2 == 0 and lo[r] <= c <= hi[r] and all(
            part[i][r % P] + c <= w[r % P] <= part[i][r % P] + c + room[i][r] for i, (P, w) in enumerate(fixed))
        if fits:
            d[r] = dr
            for i, (P, _) in enumerate(fixed): part[i][r % P] += c
            climb(r - 1, j)
            for i, (P, _) in enumerate(fixed): part[i][r % P] -= c

    def climb(r, j):                         # rows below r are placed; columns after j are chosen
        if r < 0:
            c = tuple((d[q] + size(M, q)) // 2 for q in range(M))
            assert sum(c) == v5.N // 2
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


def count_box(rel):
    """The count box (see the vocabulary) of rel, a node's overnight_v5.Relaxation by its M.  The node's relaxation
    and every bound solve must be OPTIMAL (asserted): an LP failure would leave a class its full range, sound but
    not this design, and an infeasible relaxation belongs to a node certbb closes at its root."""
    M = rel.M
    # TODO: error copy; says GLOP did not solve the node's own relaxation to optimality, so there is no count box
    assert rel.solve({}) == pywraplp.Solver.OPTIMAL, 'Claude: "the relaxation of the node is not OPTIMAL"'
    lo = [rel.bound(r, 1) for r in range(M)]
    hi = [rel.bound(r, -1) for r in range(M)]
    # TODO: error copy; says a bound solve of the relaxation failed, so some class has no count bound
    assert all(math.isfinite(t) for t in lo + hi), 'Claude: "a count bound of the relaxation is missing"'
    return (tuple(max(0, math.ceil(t - v5.TOL)) for t in lo),
            tuple(min(v5.size(M, r), math.floor(t + v5.TOL)) for r, t in enumerate(hi)))


def box_split(order, node, M, rel, box):
    """The box split (see the vocabulary) of node by M inside box, rel being the node's Relaxation by M, whose claims
    sort the vectors: (own, pool, outside), own the vectors with a child of their own in admissible's order, pool the
    rest as a sorted tuple, outside the (class, value) pairs outside the box in class order.  The vectors are
    overnight_v5.split's cut to the box: admissible_box in place of admissible, then its integer filter and orbit
    reduction, then Relaxation.check on each (feasible_set's test of the vectors inside the box)."""
    lo, hi = box
    fixed = tuple((P, V[0]) for P, V in node if M % P == 0)
    rhs = v5.moment_rows(order)[1] + tuple(t for _, V in node for t in V[0])
    ok = v5.integer_system(order, tuple(P for P, _ in node) + (M,)).fiber(rhs)
    gs = v5.stabilizer(node)
    vecs = [v for v in admissible_box(order, M, fixed, box) if ok(v) and v == v5.rep(gs, M, v)]
    own = [v for v in vecs if rel.check(v)]
    pool = tuple(sorted(set(vecs) - set(own)))
    outside = [(r, t) for r in range(M) for t in range(v5.size(M, r) + 1) if not lo[r] <= t <= hi[r]]
    return own, pool, outside


# ---------- pieces: certbb's verdicts, journaled ----------

def outside_moments(order, M, r, t):
    """certbb's Moments for the outside node (r, t) mod M: the moment rows of the order and one more row, the count
    row of class r mod M with right-hand side t.  certbb takes them for the moments, so its Lp carries the row (its
    rows stay independent: a count row is no combination of polynomial rows), and node_rows, lower_bound and Check
    check every certificate on it."""
    W, rhs = v5.moment_rows(order)
    return certbb.Moments(W + (v5.count_rows(M)[r],), rhs + (t,))


def outside_key(node, M, r, t):
    """The journal key of an outside node: the node's key, then M:r=t."""
    return f'{v5.node_key(node)} {M}:{r}={t}'


def solve_piece(moments, node, budget, lo=None, hi=None):
    """overnight_v5.solve_node with the moments as a parameter, so that an outside node (outside_moments) goes through
    the same certbb.solve and certbb.Check as any node: certbb's verdict within the budget, the sequence of a FEASIBLE
    verdict, and the journal's fields lps, leaves and proof.  quals_boxsplit pins it to solve_node."""
    check = certbb.Check(moments, node, lo, hi)
    verdict, x, stats = certbb.solve(moments, node, budget, check.feed, lo, hi)
    if verdict == 'INFEASIBLE': check.end()                          # raises unless the proof is complete
    found = {'lps': stats['lp'], 'leaves': stats['leaves'], 'proof': check.sha1.hexdigest()}
    return verdict, [2 * t - 1 for t in x] if verdict == 'FEASIBLE' else None, found


def settle(moments, node, key, budget, journal, log):
    """A piece's journal record, INFEASIBLE or UNKNOWN: the one on record if it holds within the budget (see
    overnight_v5.Journal.reuse), else certbb's fresh verdict through solve_piece, journaled.  A FEASIBLE verdict is a
    witness, checked by exact power sums (asserted), logged, and the end of the driver.  The record's verdict is
    asserted to be one of those two: the journal is trusted on resume as overnight_v5's is, but a record of any other
    verdict (CLOSED, which overnight_v5's Journal admits and reuses at any budget, and which the driver never writes)
    is no verdict of certbb's on the piece."""
    if journal.reuse(key, budget) is None:
        verdict, a, found = solve_piece(moments, node, budget)
        if verdict == 'FEASIBLE':
            eo = v5.exact_order(a)
            assert eo >= v5.ORDER                                    # a certbb solution must pass the exact test
            log(v5.say_witness(key, eo, a))
            raise SystemExit(1)
        journal.put(key, verdict, budget, found)
    rec = journal.records[key]
    # TODO: error copy; says the journal's record of this piece carries a verdict the driver never writes, so it is no verdict of certbb's on the piece
    assert rec['verdict'] in ('INFEASIBLE', 'UNKNOWN'), f'Claude: "{{{key}}}: {rec["verdict"]} on record, which is no verdict of certbb\'s"'
    return rec


def close_tree(order, node, i, journal, log):
    """Close the extension tree under node, an UNKNOWN node at depth len(CASCADE) + i, from MODULI[i] on (see
    'extension tree'); returns its tally: box splits, own children, pool members, outside nodes, certbb's LP solves and
    GLOP's solves.  Every outside node and every pool must come back INFEASIBLE (asserted); an own child left UNKNOWN
    is split by the next modulus, and there must be one (asserted)."""
    key = v5.node_key(node)
    # TODO: error copy; says this node is UNKNOWN at the last extension modulus, and a split by a further modulus is not built
    assert i < len(MODULI), f'Claude: "{{{key}}} is UNKNOWN at the last extension modulus; no further split is built"'
    M, t0, failures = MODULI[i], time.time(), v5.Relaxation.failures
    rel = v5.Relaxation(order, node, M)
    box = count_box(rel)
    own, pool, outside = box_split(order, node, M, rel, box)
    log(say_split(key, M, box, own, pool, outside, v5.Relaxation.failures - failures, time.time() - t0))
    tally = Counter(splits=1, own=len(own), pool=len(pool), outside=len(outside), glop=1 + 2 * M + len(own) + len(pool))
    t0 = time.time()
    for r, t in outside:
        rec = settle(outside_moments(order, M, r, t), node, outside_key(node, M, r, t), v5.POOL_BUDGET, journal, log)
        assert rec['verdict'] == 'INFEASIBLE', say_not_closed(rec)
        tally['lps'] += rec['lps']
    log(say_outside(key, M, len(outside), tally['lps'], time.time() - t0))
    t0 = time.time()
    pooled = node + ((M, pool),)
    rec = settle(v5.moments(order), pooled, v5.node_key(pooled), v5.POOL_BUDGET * len(pool), journal, log)
    assert rec['verdict'] == 'INFEASIBLE', say_not_closed(rec)
    tally['lps'] += rec['lps']
    log(say_piece(rec, time.time() - t0))
    for v in own:
        t0 = time.time()
        child = node + ((M, (v,)),)
        rec = settle(v5.moments(order), child, v5.node_key(child), BUDGETS[i], journal, log)
        tally['lps'] += rec['lps']
        log(say_piece(rec, time.time() - t0))
        if rec['verdict'] == 'UNKNOWN':
            tally.update(close_tree(order, child, i + 1, journal, log))
    return tally


# ---------- the control and the run ----------

def follow(node, a, M):
    """The example a taken down one split by M, as overnight_v5.control takes it: its image under the element of the
    node's stabilizer whose counts mod M are the orbit's representative, and the node extended by those counts."""
    gs = v5.stabilizer(node)
    v = v5.rep(gs, M, v5.counts(a, M))
    a = next(v5.act_seq(g, a) for g in gs if v5.act(g, M, v5.counts(a, M)) == v)
    return node + ((M, (v,)),), a


def control():
    """Startup control (see the vocabulary).  First the exact checks overnight_v5.control makes at ORDER, made here for
    the extension, which that control cannot cover: its moduli are not in the cascade, and the residue lattice of
    ORDER is not the one the example of ORDER - 1 is followed through (lattice_poly's factor x + 1 is there at ORDER
    when N < 2^ORDER and not at ORDER - 1: 304 is below 2^9 and not below 2^8).  Then the example of ORDER - 1 is
    followed down.  At each extension modulus its representative must lie in the count box and be an own child of the
    box split taken inside the box cut to within CONTROL_CUT of its counts: that split's own children are the full
    split's that lie in the cut-down box (the box only prunes the enumeration; the filter, the stabilizer and the LP
    claims are the node's), and the full box's split at ORDER - 1 is too large for a startup check (159812 vectors by
    11 and over 400000 by 13 at 304@8: minutes of GLOP solves).  And for every class, the outside node at the
    example's count, pinned to the example, must be FEASIBLE at ORDER - 1 (the count row is that class's) and
    INFEASIBLE at ORDER (the moment rows are ORDER's)."""
    rows, _ = v5.moment_rows(v5.ORDER)
    for i in range(1, len(MODULI) + 1):          # every column passes each extended prefix's integer filter
        moduli = v5.CASCADE + MODULI[:i]
        A = rows + sum((v5.count_rows(M) for M in moduli), ())
        assert all(v5.integer_system(v5.ORDER, moduli).solvable([row[p] for row in A]) for p in range(v5.N))
    bs = [v5.from_hex(h, m) for (n, m), h in v5.EXAMPLES.items() if m == v5.ORDER]
    assert bs and all(v5.exact_order(b) == v5.ORDER and sum(t * (-1) ** p for p, t in enumerate(b)) == 0 for b in bs)
    for M in MODULI:                             # the lattice's generators and the examples' residues lie in its basis's span
        span = v5.ExactSystem(v5.lattice_basis(M, v5.ORDER))
        poly = v5.lattice_poly(v5.ORDER)
        gens = [[sum(c for t, c in enumerate(poly) if (t + k) % M == r) for r in range(M)] for k in range(M)]
        assert all(span.solvable(g) for g in gens)
        assert all(span.solvable([sum(b[p] for p in range(r, len(b), M)) for r in range(M)]) for b in bs)
    m = v5.ORDER - 1
    # TODO: error copy; says EXAMPLES has no example of length N and order ORDER-1, which the control needs
    assert (v5.N, m) in v5.EXAMPLES, f'Claude: "EXAMPLES has no example of length {v5.N} and order {m}"'
    a, node = v5.from_hex(v5.EXAMPLES[v5.N, m], m), ()
    assert len(a) == v5.N and v5.exact_order(a) == m
    for M in v5.CASCADE: node, a = follow(node, a, M)
    for M in MODULI:
        rel = v5.Relaxation(m, node, M)
        lo, hi = count_box(rel)
        node, a = follow(node, a, M)
        v = node[-1][1][0]
        assert all(l <= t <= h for l, t, h in zip(lo, v, hi, strict=True)), (M, v, lo, hi)
        cut = (tuple(max(l, t - CONTROL_CUT) for l, t in zip(lo, v)), tuple(min(h, t + CONTROL_CUT) for h, t in zip(hi, v)))
        assert v in box_split(m, node[:-1], M, rel, cut)[0], (M, v)
        x = [(t + 1) // 2 for t in a]
        for r in range(M):
            assert solve_piece(outside_moments(m, M, r, v[r]), node[:-1], 1, x, x)[:2] == ('FEASIBLE', a), (M, r)
            assert solve_piece(outside_moments(v5.ORDER, M, r, v[r]), node[:-1], 1, x, x)[0] == 'INFEASIBLE', (M, r)
    x = [(t + 1) // 2 for t in a]
    assert solve_piece(v5.moments(m), node, 1, x, x)[:2] == ('FEASIBLE', a)
    assert solve_piece(v5.moments(v5.ORDER), node, 1, x, x)[0] == 'INFEASIBLE'


def run():
    """The run that configure() set up: the run's open leaves, the control, each leaf's extension tree, and the
    outcome, all in the log."""
    t0 = time.time()
    # TODO: error copy; says the run's journal, which the driver takes its open leaves from, is not there
    assert os.path.exists(v5.JOURNAL), f'Claude: "no journal {v5.JOURNAL} to take the open leaves from"'
    leaves = open_leaves(v5.Journal(v5.JOURNAL))                     # read, never written
    journal = Journal(JOURNAL)
    # TODO: start line; says: start: n, order at least, how many open leaves the run's journal holds, the extension moduli and certbb's budgets for their own children in LP solves (a pool or an outside node getting so many per member), the HiGHS build, and how many verdicts the driver's journal already holds
    log_to_file(f'Claude: "start: n = {v5.N}, order at least {v5.ORDER}, open leaves {len(leaves)} of {v5.JOURNAL}, '
                f'extension moduli {list(MODULI)} with budgets {list(BUDGETS)} (LP solves; a pool or an outside node '
                f'{v5.POOL_BUDGET} per member), HiGHS {certbb.HIGHS}, {len(journal.records)} earlier verdicts"')
    control()
    # TODO: says the startup control passed: the example of order ORDER-1 and length N lands in an own child at every extension modulus, and order ORDER rejects it
    log_to_file(f'Claude: "startup control passed: the order-{v5.ORDER - 1} example of length {v5.N} lands in an own '
                f'child at each of {list(MODULI)}, and order {v5.ORDER} rejects it"')
    tallies = []
    for i, leaf in enumerate(leaves):
        log_to_file(say_leaf(i, v5.node_key(leaf)))
        c0 = time.process_time()
        tallies.append(dict(close_tree(v5.ORDER, leaf, 0, journal, log_to_file), cpu=time.process_time() - c0))
    for i, (leaf, tally) in enumerate(zip(leaves, tallies, strict=True)):
        log_to_file(say_leaf_closed(i, v5.node_key(leaf), tally))
    hours = (time.time() - t0) / 3600
    # TODO: final line; says every open leaf's extension tree closed, with their count and the hours taken: every piece is INFEASIBLE on a certificate checked in exact integer arithmetic, so no sequence of order at least ORDER lies in any of them
    log_to_file(f'Claude: "ALL {len(leaves)} LEAVES CLOSED ({hours:.2f} h): every piece of every extension tree is '
                f'INFEASIBLE on a certificate checked in exact integer arithmetic, so no ±1 sequence of length {v5.N} '
                f'and order at least {v5.ORDER} lies in any open leaf of the run."')


def main():
    # TODO: error copy; says how to run the driver: with the length N and the order as its two arguments
    assert len(sys.argv) == 3, 'Claude: "usage: python3 boxsplit.py N ORDER"'
    configure(int(sys.argv[1]), int(sys.argv[2]))
    run()


# A fingerprint of the driver's code that decides verdicts, taken as imported (see header()); overnight_v5's and
# certbb's are in the header's code field.
CODE = hashlib.sha1(''.join(inspect.getsource(f) for f in (
    parse_key, open_leaves, admissible_box, count_box, box_split, outside_moments, outside_key, solve_piece, settle,
    close_tree)).encode()).hexdigest()


if __name__ == '__main__':
    main()
