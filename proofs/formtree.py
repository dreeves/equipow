#!/usr/bin/env python3
"""Claude's exact check of a form tree: a proof that no sequence of length n has order m.  Python's standard library only: integers, no floats, no solver.

    python3 -B -I -S proofs/formtree.py check STREAM[.gz]      each task of a stream: one verdict per line, JSON
    python3 -B -I -S proofs/formtree.py top TOP.json.gz        the top of the proof: which start nodes remain
    python3 -B -I -S proofs/formtree.py assemble TOP.json.gz VERDICTS[.gz]    every start node and every spilled node has a verdict, accepted, none open
"form tree" is a name proposed 2026-11-04, awaiting dreeves's approval.

The claim.  No signs a_p in {-1, 1}, p = 0, ..., n-1, have sum_p a_p p^k = 0 for k = 0, ..., m-1.

Suppose some do, and let F(x) = sum_p a_p x^p.  Then (x-1)^m divides F in Z[x].  If n < 2^m then F(-1) = 0 as well, since 2^m divides F(-1) and |F(-1)| <= n.  Put e = 1 then and e = 0 otherwise:
(x-1)^m (x+1)^e divides F.  Then sum_p C(p, t) a_p = 0 for t < m, C being the binomial coefficient, since these are the Taylor coefficients of F at 1.

Vocabulary (with proofs/pintree.py's, which proved 432:12 and 816:13 and whose functions are used here).
  residue sums  D^(M)_r = sum_{p = r mod M} a_p, r = 0, ..., M-1: the coefficients of F mod x^M - 1.
  L(M)          { (x-1)^m (x+1)^e g mod x^M - 1 : g in Z[x] }, the residue lattice.
  form          integer weights w_0, ..., w_{M-1} on the classes mod M, M a prime power; its value on a sequence is f = sum_r w_r D^(M)_r = sum_p w_{p mod M} a_p.
  grid          a step st > 0 and an offset c0 such that every sequence of order m has f = c0 mod st: below.
  pinned row    a form with a value, taken as given or proved.  A node is a set of pinned rows, standing for the sequences with those values.
  certificate   (dd, ss, B_0, ..., B_{m-1}, multipliers c_q on the node's rows): below.
  form tree     a tree of nodes in which every leaf is closed by a certificate.
  task          a subtree written out as a stream; a spilled node ends one task and starts another.

Grids.  For a prime power M, every sequence of order m has
    D^(M) in rep(M) + 2 L(M)
where rep(M) is a fixed vector of L(M).
  M = 2^k: this is the parity coset, (d) in proofs/pintree.py's docstring: mod 2 every sequence is the polynomial (x^n - 1)/(x - 1), so F/((x-1)^m (x+1)^e) is one fixed polynomial h mod 2, and rep(M) is
  (x-1)^m (x+1)^e times h's 0/1 reduction mod x^M - 1.
  M odd: D^(M) lies in L(M), and D^(M)_r = size(M, r) mod 2 since it is a sum of size(M, r) odd numbers.  rep(M) is a vector of L(M) with those parities.  Two such vectors differ by a vector of L(M) with even
  entries.  In a triangular basis of L(M) with odd pivots (checked for each M used), the highest pivot's coefficient of such a difference is even, then the next, and so on, so the difference lies in 2 L(M).
(fkernel.cpp reaches the same fact another way: L(M) has rank M - 1 and its generators keep that rank mod 2, so L(M) meets 2 Z^M only in 2 L(M).)
So with G = the gcd of w.b over a basis b of L(M), a form takes values c + 2 G Z where c = w.rep(M).  A stated grid (st, c0) is accepted when st divides 2 G and st divides c - c0.

Certificates.  With T = 2^(dd+ss) and
    W(p) = sum_t B_t C(p, t) + 2^dd sum_q c_q w_q(p mod M_q),
every sequence of order m with the node's rows has sum_p W(p) a_p = K, where K = 2^dd sum_q c_q v_q, v_q being the rows' values, since sum_p C(p, t) a_p = 0 for t < m.  Then, as |a_p| = 1:
  to close a node: |K| > sum_p |W(p)| contradicts it, so no sequence has the node's rows;
  to bound a form f: for s = +-1, T s f = sum_p (T s w(p) - W(p)) a_p + K <= sum_p |T s w(p) - W(p)| + K, so s f <= floor((that) / T).
The multipliers can be anything: a wrong certificate proves nothing and is refused, a right one proves its claim whatever produced it.

The symmetry.  F -> x^(n-1) F(1/x), reversal, keeps the order.  A node is marked G = 1 only when the set of sequences it stands for is closed under reversal: a start node whose residue sums are reversal
invariant, D_r = D_{(n-1-r) mod M}; a node that only adds a proved fix to such a node, since a proved fix removes no sequence; and the child with value 0 of a symmetric split.  If w_{(n-1-r) mod M} = -w_r for all r the form is
anti-invariant: the reversal of a sequence with f = v has f = -v.  So at a node with G = 1, the values v >= 0 of an anti-invariant form cover every sequence of the node up to reversal, and those are all that a symmetric step
looks at.  A child with v = 0 is again closed under reversal, one with v != 0 is not.

The stream.  One claim to a line, numbers in decimal, row ids being the prover's labels with no meaning here:
    T n m            a task begins
    G g              g = 1: the start node is marked closed under reversal; a task's start is justified by the verdict of the task that spilled it, or by the top
    P id M v w...    a pinned row of the start node
    R id M st c0 w...   a form with its stated grid, tested as above
    B id sym k U D   the certificates U and D bound form id above and below.  The grid values in those bounds, only those >= 0 if sym = 1, are the candidates; there must be k of them.
                     k = 0: the node is closed.  k = 1: the form is pinned in this node at that value, a fix.  k >= 2: the node splits, a child per value in increasing order.
    C dd ss B... r id c ...   closes the node
    V v              the next child of the split begins: its rows are its parent's and the form at v
    S                the node is spilled: another task must close it.  A task may not spill its own start with no row added, which would say only that the node is closed if it is closed.  So rows grow strictly along every chain of tasks, and a proof cannot go in a circle.
    O                the node is left open: the task's verdict counts it, and no proof may have any
    E                the task ends; every node must have been closed, spilled or left open

The name of a node is the first 128 bits, in hex, of the SHA-256 of "n N m M G g\n" and its rows' lines "M v w_0 ... w_{M-1}\n", sorted as strings.  It says what the node claims, whichever prover made it.  A task's verdict gives its start's name and its spilled nodes' names.

The top.  From no pins, every vector of residue sums at M = 3, 5, 7 meeting proofs/pintree.py's (a), (b), (c), (d) is a child (pintree.vectors), one per orbit under F -> -F and reversal: a child is passed over when an image of it has been dealt with.
A child is closed by a certificate or kept as a start node, whose rows are its residue sums, weights the unit vectors.

The proof.  The top lists start nodes.  assemble accepts when each has an accepted verdict with no open node, and so does each node spilled by any task, recursively, with no cycle among them.  Then no sequence has order m.

Two checkers.  This file, and fkernel.cpp, which shares no code with it: its own arithmetic (differences for the moments, checked ranges in 128-bit integers), its own way to rep(M) for odd M (a linear system over F_2) and to the coset fact (a rank mod 2).  They give the same verdicts and names.
"""
import gzip, hashlib, importlib.util, json, os, sys
from math import comb, gcd


def _load_pintree():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('pintree', os.path.join(here, 'pintree.py')); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


pintree = _load_pintree()


def size(n, M, r): return len(range(r, n, M))


MAX_VALUES = 1024   # a step listing more values than this is refused: nothing is ever allocated in proportion to a number in the stream
MAX_N, MAX_M = 2047, 64


def grid_count(lo, hi, c0, st):
    """The least value of the grid c0 + st Z at or above lo, and how many lie in [lo, hi], without listing them."""
    first = lo + (c0 - lo) % st
    return first, (hi - first) // st + 1 if hi >= first else 0


class Cell:
    """What holds for every sequence of order m at length n."""
    def __init__(self, n, m):
        if not (type(n) is int and type(m) is int and 0 < m <= MAX_M and 2 * m <= n <= MAX_N): raise ValueError('n and m out of range')
        self.n, self.m, self.e = n, m, 1 if n < 2 ** m else 0
        self.C = [[comb(p, t) for t in range(m)] for p in range(n)]
        self.reps = {}
        self.grids = {}

    def rep(self, M):
        if M not in self.reps: self.reps[M] = self._rep(M)
        return self.reps[M]

    def _rep(self, M):
        p, _ = pintree.prime_power(M)
        if p == 2: return tuple(pintree.coset_rep(self.n, M, self.m, self.e))
        order = pintree.digits_order(M)
        basis = pintree.triangular(M, self.m, self.e)
        for c, v in basis:
            if v[c] % 2 == 0: raise ValueError(f'an even pivot mod {M}')
        d = [0] * M
        for c, v in reversed(basis):
            if (d[c] - size(self.n, M, order[c])) % 2:
                for i in range(M): d[i] += v[i]
        if any((d[i] - size(self.n, M, order[i])) % 2 for i in range(M)): raise ValueError(f'no vector of L({M}) has the parities of the class sizes')
        out = [0] * M
        for i, r in enumerate(order): out[r] = d[i]
        return tuple(out)

    def grid(self, M, w):
        """2 G and c: the form's values lie in c + 2 G Z."""
        key = (M, w)
        if key not in self.grids:
            order = pintree.digits_order(M)
            word = [w[r] for r in order]
            G = 0
            for _, v in pintree.triangular(M, self.m, self.e): G = gcd(G, sum(a * b for a, b in zip(word, v)))
            self.grids[key] = (2 * G, sum(a * b for a, b in zip(w, self.rep(M))))
        return self.grids[key]


def node_name(n, m, G, rows):
    """rows: (M, v, w)."""
    lines = sorted(' '.join(map(str, (M, v) + tuple(w))) for M, v, w in rows)
    return hashlib.sha256((f'n {n} m {m} G {G}\n' + ''.join(line + '\n' for line in lines)).encode()).hexdigest()[:32]


class Certificate:
    def __init__(self, numbers, at, m):
        self.dd, self.ss = numbers[at], numbers[at + 1]
        if not (0 <= self.dd <= 64 and 0 <= self.ss <= 64): raise ValueError('a scale out of range')
        at += 2
        self.B = numbers[at:at + m]
        if len(self.B) != m: raise ValueError('a certificate cut short')
        at += m
        k = numbers[at]; at += 1
        if k < 0 or at + 2 * k > len(numbers): raise ValueError('a certificate cut short')
        self.c = [(numbers[at + 2 * i], numbers[at + 2 * i + 1]) for i in range(k)]
        self.end = at + 2 * k


class Task:
    """One task's lines, in order.  feed raises ValueError on anything that does not hold."""
    def __init__(self, cell):
        self.cell = cell
        self.forms = {}    # id: (M, w, st, c0), st = None for a row given at the start
        self.values = {}   # id: value, the rows of the current node
        self.levels = []   # [rows at entry, G, form, sym, values, next]
        self.order = []    # ids of the rows in the current node, in order
        self.G = 0
        self.started = False
        self.awaiting = False
        self.done = False
        self.counts = dict(nodes=0, closed=0, fixes=0, splits=0, certs=0, open=0)
        self.spills = []
        self.start_name = None
        self.start_rows = 0

    def name_here(self, G):
        return node_name(self.cell.n, self.cell.m, G, [(self.forms[i][0], self.values[i], self.forms[i][1]) for i in self.order])

    def begin(self):
        self.started = True
        self.levels.append([0, self.G, None, False, [], 0])
        self.start_rows = len(self.order)
        self.counts['nodes'] = 1
        self.start_name = self.name_here(self.G)

    def define(self, i, M, w, st, c0):
        old = self.forms.get(i)
        if old is not None and old[:2] != (M, w): raise ValueError('a row id defined twice, differently')
        self.forms[i] = (M, w, st, c0)

    def pin(self, i, v):
        if i in self.values:
            if self.values[i] != v: raise ValueError('a row pinned twice, to different values')
            return
        self.values[i] = v
        self.order.append(i)

    def close(self):
        while True:
            top = self.levels.pop()
            while len(self.order) > top[0]: del self.values[self.order.pop()]
            self.counts['closed'] += 1
            if not self.levels:
                self.done = True; self.awaiting = False
                return
            par = self.levels[-1]
            if par[5] < len(par[4]):
                self.awaiting = True
                return

    def weights(self, cert):
        n, C = self.cell.n, self.cell.C
        W = [0] * n
        for t, b in enumerate(cert.B):
            if b:
                for p in range(n): W[p] += b * C[p][t]
        K = 0
        by_modulus = {}
        for i, c in cert.c:
            if i not in self.values: raise ValueError('a certificate weighs a row the node does not have')
            M, w = self.forms[i][:2]
            K += c * self.values[i]
            g = by_modulus.setdefault(M, [0] * M)
            for r in range(M): g[r] += c * w[r]
        D = 1 << cert.dd
        for M, g in by_modulus.items():
            for p in range(n): W[p] += D * g[p % M]
        self.counts['certs'] += 1
        return W, D * K

    def bound(self, cert, M, w, s):
        """The greatest integer that s * form can be under the node's rows, by this certificate."""
        W, K = self.weights(cert)
        T = 1 << (cert.dd + cert.ss)
        total = sum(abs(T * s * w[p % M] - W[p]) for p in range(self.cell.n))
        return (total + K) // T

    def step_ready(self):
        if self.done or self.awaiting: raise ValueError('a step where a child was expected')

    def feed(self, kind, numbers):
        n = self.cell.n
        if kind in ('G', 'P'):
            if self.started: raise ValueError(f'{kind} after the start')
            if kind == 'G':
                if numbers[0] not in (0, 1): raise ValueError('G is 0 or 1')
                self.G = numbers[0]
            else:
                i, M, v, w = numbers[0], numbers[1], numbers[2], tuple(numbers[3:])
                if len(w) != M: raise ValueError('a weight per class')
                self.define(i, M, w, None, None)
                self.pin(i, v)
            return
        if not self.started: self.begin()
        if kind == 'R':
            i, M, st, c0, w = numbers[0], numbers[1], numbers[2], numbers[3], tuple(numbers[4:])
            if len(w) != M: raise ValueError('a weight per class')
            if st <= 0: raise ValueError('a step must be positive')
            two_g, c = self.cell.grid(M, w)
            if two_g % st: raise ValueError("a form's step is not a divisor of its grid")
            if (c - c0) % st: raise ValueError("a form's offset is off its grid")
            self.define(i, M, w, st, c0)
        elif kind == 'B':
            self.step_ready()
            i, sym, k = numbers[0], numbers[1], numbers[2]
            U = Certificate(numbers, 3, self.cell.m)
            D = Certificate(numbers, U.end, self.cell.m)
            if D.end != len(numbers): raise ValueError('numbers left over')
            form = self.forms.get(i)
            if form is None or form[2] is None: raise ValueError('B on a form without a grid')
            if i in self.values: raise ValueError('B on a form the node has pinned')
            M, w, st, c0 = form
            hi = self.bound(U, M, w, 1)
            lo = -self.bound(D, M, w, -1)
            level = self.levels[-1]
            if sym:
                if not level[1]: raise ValueError('a symmetric split where the node has no symmetry')
                if any(w[(n - 1 - r) % M] != -w[r] for r in range(M)): raise ValueError('a symmetric split on a form that is not anti-invariant')
            first, count = grid_count(max(lo, 0) if sym else lo, hi, c0, st)
            if count != k: raise ValueError('the certificates give another number of values')
            if k > MAX_VALUES: raise ValueError('too many values')
            values = [first + st * j for j in range(k)]
            if not values: self.close()
            elif len(values) == 1:
                self.pin(i, values[0])
                self.counts['fixes'] += 1
                if sym and values[0] != 0: level[1] = 0
            else:
                self.counts['splits'] += 1
                level[2], level[3], level[4], level[5] = i, bool(sym), values, 0
                self.awaiting = True
        elif kind == 'V':
            if not self.awaiting: raise ValueError('V where no child is due')
            par = self.levels[-1]
            v = numbers[0]
            if par[4][par[5]] != v: raise ValueError('V: not the value due')
            par[5] += 1
            self.levels.append([len(self.order), par[1] if par[3] and v == 0 else 0, None, False, [], 0])
            self.pin(par[2], v)
            self.awaiting = False
            self.counts['nodes'] += 1
        elif kind == 'C':
            self.step_ready()
            cert = Certificate(numbers, 0, self.cell.m)
            if cert.end != len(numbers): raise ValueError('numbers left over')
            W, K = self.weights(cert)
            if abs(K) <= sum(abs(x) for x in W): raise ValueError('a closing certificate does not close')
            self.close()
        elif kind == 'S':
            self.step_ready()
            if len(self.levels) == 1 and len(self.order) == self.start_rows: raise ValueError('a task spilled its own start')
            self.spills.append(self.name_here(self.levels[-1][1]))
            self.close()
        elif kind == 'O':
            self.step_ready()
            self.counts['open'] += 1
            self.close()
        else:
            raise ValueError(f'unknown line {kind}')


def check_stream(lines):
    """Yields each task's verdict."""
    task = None; cell = None; why = ''
    for line in lines:
        parts = line.split()
        if not parts: continue
        kind = parts[0]
        if kind == 'T':
            if task is not None: raise ValueError('T inside a task')
            n, m = int(parts[1]), int(parts[2])
            if cell is None or (cell.n, cell.m) != (n, m): cell = Cell(n, m)
            task = Task(cell); why = ''
        elif kind == 'E':
            if task is None: raise ValueError('E outside a task')
            if not why:
                try:
                    if not task.started: task.begin(); raise ValueError('a task without a step')
                    if not task.done: raise ValueError('the tree did not close')
                except ValueError as err: why = str(err)
            if task.start_name is None: task.begin()
            yield dict(ok=not why, start=task.start_name, why=why, spills=task.spills, **task.counts)
            task = None
        else:
            if task is None: raise ValueError('a line outside a task')
            if why: continue
            try: task.feed(kind, [int(x) for x in parts[1:]])
            except ValueError as err: why = str(err)
    if task is not None: raise ValueError('the stream ended inside a task')


# ---- the top
def start_rows(pins):
    return [(M, D[r], tuple(int(i == r) for i in range(M))) for M, D in sorted(pins.items()) for r in range(M)]


def reversal_invariant(pins, n):
    return all(D[(n - 1 - r) % M] == D[r] for M, D in pins.items() for r in range(M))


class Top:
    """Replays the top's tokens: ['S', M], ['C', cert], ['K'] (kept as a start node)."""
    def __init__(self, n, m, tokens):
        self.cell = Cell(n, m); self.tokens = iter(tokens); self.dealt = set(); self.starts = []
        self.stats = dict(vectors=0, passed_over=0, closed=0, kept=0)

    def node(self, pins, depth=0):
        token = next(self.tokens)
        if token[0] == 'C':
            self.close(pins, token[1])
            self.stats['closed'] += 1
        elif token[0] == 'K':
            G = 1 if reversal_invariant(pins, self.cell.n) else 0
            self.starts.append(dict(name=node_name(self.cell.n, self.cell.m, G, start_rows(pins)), G=G, pins={str(M): list(D) for M, D in pins.items()}))
            self.stats['kept'] += 1
        elif token[0] == 'S':
            M = token[1]
            assert type(M) is int and M > 1
            if M in pins: raise ValueError(f'{M} is pinned already')
            for v in pintree.vectors(self.cell.n, self.cell.m, M, pins):
                self.stats['vectors'] += 1
                child = {**pins, M: v}
                if any(i in self.dealt for i in pintree.images(child, self.cell.n)):
                    self.stats['passed_over'] += 1
                    continue
                self.node(child, depth + 1)
        else:
            raise ValueError(f'unknown token {token[0]}')
        self.dealt.add(pintree.freeze(pins))

    def close(self, pins, numbers):
        cert = Certificate(numbers['cert'], 0, self.cell.m)
        task = Task(self.cell)
        i = 0
        for M, v, w in start_rows(pins):
            task.define(i, M, w, None, None); task.pin(i, v); i += 1
        task.begin()
        by_key = {}
        for j, (M, v, w) in enumerate(start_rows(pins)): by_key[(M, w.index(1))] = j
        cert.c = [(by_key[(M, r)], c) for M, r, c in numbers['rows']]
        W, K = task.weights(cert)
        if abs(K) <= sum(abs(x) for x in W): raise ValueError(f'a certificate does not close {pins}')

    def run(self):
        self.node({})
        if next(self.tokens, None) is not None: raise ValueError('tokens left over')
        return self.starts, self.stats


def read_json(path):
    def reject(_): raise ValueError('a float')
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f: return json.load(f, parse_float=reject, parse_constant=reject)


def check_top(path):
    data = read_json(path)
    sys.setrecursionlimit(100000)
    return data['n'], data['m'], *Top(data['n'], data['m'], data['tokens']).run()


def assemble(starts, verdicts):
    """Every start node, and every node spilled on the way, has an accepted verdict with no open node.  Returns the totals over the tasks the proof uses."""
    by_name, refused = {}, {}
    for v in verdicts:
        # TODO: says the independent checkers disagree, so this run cannot be assembled.
        if v.get('py') is False: raise ValueError(f'Examinatores dissentiunt: {v["start"]}')
        if v['ok']: by_name.setdefault(v['start'], v)
        else: refused[v['start']] = v['why']
    total = dict(tasks=0, nodes=0, closed=0, fixes=0, splits=0, certs=0)
    colour = {}   # 1: on the walk's path, 2: finished

    def enter(name, path):
        v = by_name.get(name)
        if v is None: raise ValueError(f'a rejected task: {name}: {refused[name]}' if name in refused else f'no verdict for node {name}')
        if v['open']: raise ValueError(f'an open node under {name}')
        total['tasks'] += 1
        for k in ('nodes', 'closed', 'fixes', 'splits', 'certs'): total[k] += v[k]
        colour[name] = 1
        path.append((name, iter(v['spills'])))

    for start in starts:
        if start in colour: continue
        path = []
        enter(start, path)
        while path:
            name, children = path[-1]
            child = next(children, None)
            if child is None:
                colour[name] = 2
                path.pop()
            elif colour.get(child) == 1: raise ValueError(f'a cycle of tasks through {child}')
            elif child not in colour: enter(child, path)
    return total


def open_text(path):
    return gzip.open(path, 'rt', encoding='ascii') if path.endswith('.gz') else open(path, encoding='ascii')


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'check':
        with open_text(sys.argv[2]) as f:
            for verdict in check_stream(f): print(json.dumps(verdict, sort_keys=True), flush=True)
    elif what == 'top':
        n, m, starts, stats = check_top(sys.argv[2])
        print(f'Claude: "TOP OF {n}:{m} CHECKED: {len(starts)} start nodes remain; {stats}"')
        for s in starts: print(s['name'], s['G'], json.dumps(s['pins']))
    elif what == 'assemble':
        n, m, starts, stats = check_top(sys.argv[2])
        with open_text(sys.argv[3]) as f: verdicts = [json.loads(line) for line in f if line.strip()]
        total = assemble([s['name'] for s in starts], verdicts)
        print(f'Claude: "VERIFIED: no sequence of length {n} has order {m}.  Top {stats}; tasks {total}"')
    else:
        raise ValueError(what)
