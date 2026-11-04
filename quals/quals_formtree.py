#!/usr/bin/env python3
"""Quals for form trees: proofs/formtree.py and proofs/fkernel.cpp, the two checkers, and searches/formtree/, the prover and its driver.  Run: python3 -B quals/quals_formtree.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Its comment gives the replicata and the expectata; a failure's message is the resultata.
The code came first here: these quals were written after it, so none was seen red against it unless its comment says so.  The forged proofs are the red cases: each must be refused.
The quals marked "engine" need numpy and g++, and take minutes.  All run under a memory limit.
"""
import sys
sys.dont_write_bytecode = True
import gzip, hashlib, importlib.util, itertools, json, os, random, re, resource, subprocess, tempfile, time, traceback
resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))   # 2026-11-04: an unbounded list in the checker took this process to 13.7 GB.  Nothing here may take the machine down.
from math import gcd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PROVER = os.path.join(ROOT, 'searches', 'formtree')
BUILD = tempfile.mkdtemp(prefix='quals_formtree_')
KERNEL = os.path.join(BUILD, 'fkernel')
subprocess.run(['g++', '-O2', '-std=c++17', '-o', KERNEL, os.path.join(ROOT, 'proofs', 'fkernel.cpp')], check=True)
spec = importlib.util.spec_from_file_location('formtree', os.path.join(ROOT, 'proofs', 'formtree.py')); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
pintree = ft.pintree
FIX = os.path.join(PROVER, 'fixtures')


def fixture(name):
    with open(os.path.join(FIX, name)) as f: return f.read().splitlines()


def tasks_of(lines):
    """A stream's lines, split into tasks."""
    out, cur = [], []
    for line in lines:
        cur.append(line)
        if line.split()[0] == 'E': out.append(cur); cur = []
    assert not cur
    return out


def run_kernel(lines):
    p = subprocess.run([KERNEL], input='\n'.join(lines) + '\n', capture_output=True, text=True, timeout=120)
    return [json.loads(x) for x in p.stdout.splitlines()]


def run_python(lines):
    try: return list(ft.check_stream(lines))
    except ValueError as err: return [dict(ok=False, why=str(err))]
    except MemoryError: raise AssertionError('formtree.py ran out of its memory limit')


def both(lines):
    """The two checkers' verdicts on a stream of one task; they must agree on ok."""
    a, b = run_kernel(lines), run_python(lines)
    assert len(a) == 1 and len(b) == 1, (a, b)
    assert a[0]['ok'] == b[0]['ok'], ('the checkers disagree', a[0], b[0])
    return a[0], b[0]


def refused(lines, what, because=None):
    a, b = both(lines)
    assert not a['ok'], f'{what}: accepted by fkernel'
    assert not b['ok'], f'{what}: accepted by formtree.py'
    if because:
        assert because in a['why'], (what, a['why'])
        assert because in b['why'], (what, b['why'])


def small_task():
    return tasks_of(fixture('small.txt'))[0]


def closing_task():
    return tasks_of(fixture('close.txt'))[0]


def sym_task():
    return tasks_of(fixture('sym.txt'))[0]


def line_index(lines, kind, nth=0):
    hits = [i for i, l in enumerate(lines) if l.split()[0] == kind]
    return hits[nth]


# replicata: the fixtures, real tasks of 288:10.  expectata: both checkers accept, with one and the same verdict: counts, start name, spilled names.
def q_real_tasks_accepted_the_same():
    for name in ('small.txt', 'sym.txt'):
        for t in tasks_of(fixture(name)):
            a, b = both(t)
            assert a['ok'], a['why']
            assert a == b, (a, b)


# replicata: a form's stated step doubled, or its offset moved.  expectata: refused, as the grid does not hold it.
def q_forged_grid():
    t = small_task(); i = line_index(t, 'R'); p = t[i].split()
    u = list(t); q = list(p); q[3] = str(int(p[3]) * 2); u[i] = ' '.join(q)
    refused(u, 'step doubled', 'divisor')
    u = list(t); q = list(p); q[4] = str(int(p[4]) + 1); u[i] = ' '.join(q)
    refused(u, 'offset moved', 'off its grid')


# replicata: a form with a modulus that is no prime power, whose residue sums the lemma says nothing about.  expectata: refused.
def q_forged_modulus():
    t = small_task(); i = line_index(t, 'R')
    u = list(t); u[i] = f'R 999 6 2 0 1 -1 0 0 0 0'
    a, b = run_kernel(u), run_python(u)
    assert not a[0]['ok'], 'fkernel'
    assert not b[0]['ok'], 'formtree.py'


# replicata: a closing certificate with its row multipliers zeroed, or a moment multiplier changed.  expectata: refused: it no longer closes.
def q_forged_closure():
    t = closing_task(); i = line_index(t, 'C'); p = t[i].split(); m = 10
    k = int(p[3 + m]); q = list(p)
    for j in range(k): q[5 + m + 2 * j] = '0'
    u = list(t); u[i] = ' '.join(q)
    refused(u, 'multipliers zeroed', 'does not close')
    q = list(p); q[3] = str(int(p[3]) + 10 ** 28); u = list(t); u[i] = ' '.join(q)
    refused(u, 'a moment multiplier moved')


# replicata: a bound's certificates swapped for empty ones.  expectata: refused: the trivial bound gives many more values than the claim.
def q_forged_bound():
    t = small_task(); i = line_index(t, 'B'); p = t[i].split(); m = 10
    null = ['50', '24'] + ['0'] * m + ['0']
    u = list(t); u[i] = ' '.join(p[:4] + null + null)
    refused(u, 'empty certificates', 'number of values')


# replicata: the number of values changed on a fix or a split.  expectata: refused.
def q_forged_count():
    t = small_task(); i = line_index(t, 'B'); p = t[i].split()
    for k in (int(p[3]) + 1, int(p[3]) - 1):
        q = list(p); q[3] = str(k); u = list(t); u[i] = ' '.join(q)
        refused(u, f'k = {k}', 'number of values')


# replicata: a certificate that weighs a row the node does not have.  expectata: refused.
def q_forged_row():
    t = closing_task(); i = line_index(t, 'C'); p = t[i].split(); m = 10
    q = list(p); q[4 + m] = '99999'
    u = list(t); u[i] = ' '.join(q)
    refused(u, 'a row the node lacks', 'does not have')


# replicata: a child dropped from a split: from a V to the next V at the same level, or the last lines of the task.  expectata: refused: every value's child must come, every node must close.
def q_forged_coverage():
    t = small_task(); v = [i for i, l in enumerate(t) if l.split()[0] == 'V']
    assert len(v) >= 2
    u = t[:v[0]] + t[v[1]:]
    a, b = both(u); assert not a['ok'] and not b['ok'], 'a child dropped'
    u = t[:v[-1]] + ['E']
    refused(u, 'the last child gone', 'did not close')
    u = list(t); u[v[0]] = f"V {int(t[v[0]].split()[1]) + 1}"
    refused(u, 'V off its value', 'not the value due')
    # a child taken twice
    u = t[:v[1]] + t[v[0]:]
    a, b = both(u); assert not a['ok'] and not b['ok'], 'a child twice'


# replicata: a symmetric step where the node has no symmetry; on a form that is not anti-invariant.  expectata: refused.
def q_forged_symmetry():
    t = small_task(); i = line_index(t, 'B'); p = t[i].split(); q = list(p); q[2] = '1'
    u = list(t); u[i] = ' '.join(q)
    refused(u, 'sym without symmetry', 'no symmetry')
    t = sym_task(); g = line_index(t, 'G'); assert t[g].split()[1] == '1'
    cell = ft.Cell(288, 10); w = tuple(int(r == 0) for r in range(11)); st, c0 = cell.grid(11, w)
    i = next(j for j, l in enumerate(t) if l.split()[0] not in 'TGP')
    null = ' '.join(['50', '24'] + ['0'] * 10 + ['0'])
    u = t[:i] + [f'R 9999 11 {st} {c0} ' + ' '.join(map(str, w)), f'B 9999 1 1 {null} {null}'] + t[i:]
    refused(u, 'sym on a form that is not anti-invariant', 'not anti-invariant')


# replicata: numbers past what 128 bits hold, chosen so that a wrapped sum would close a node.  expectata: fkernel refuses them for size; formtree.py, with exact integers, for not closing.
def q_forged_overflow():
    t = closing_task(); i = line_index(t, 'C'); p = t[i].split(); m = 10
    for big in (2 ** 100, 2 ** 110, 2 ** 120, 2 ** 126):
        q = list(p); q[5 + m] = str(big); u = list(t); u[i] = ' '.join(q)
        a, b = both(u); assert not a['ok'] and not b['ok'], big
    q = list(p); q[5 + m] = str(2 ** 200); u = list(t); u[i] = ' '.join(q)
    a, b = both(u); assert not a['ok'] and not b['ok'], 'past 128 bits'


# replicata: certificates that claim absurdly wide bounds, with k small and with k enormous, and absurd sizes of everything the stream states.  expectata: refused at once, in little memory.  Seen red, 2026-11-04: formtree.py listed the grid values of such a bound and reached 13.7 GB before it was killed.
def q_forged_sizes_cost_nothing():
    t = small_task(); i = line_index(t, 'B'); p = t[i].split(); m = 10
    for big in (10 ** 29, 10 ** 60):
        for k in ('1', str(10 ** 18), str(10 ** 40)):
            q = list(p); q[3] = k; q[6] = str(big); u = list(t); u[i] = ' '.join(q)
            t0 = time.time(); a, b = run_kernel(u), run_python(u)
            assert not a[0]['ok'] and not b[0]['ok'], (big, k)
            assert time.time() - t0 < 20, 'too slow'
    # sizes
    for what, line in (('M', 'R 7 2000000000 2 0 1'), ('id', 'R 2000000000 3 2 0 1 0 0'), ('huge id', f'R {10 ** 30} 3 2 0 1 0 0'), ('P M', 'P 7 2000000000 0 1')):
        u = t[:2] + [line] + t[2:]
        for run in (run_kernel, run_python):
            r = run(u)
            assert r and not r[0]['ok'], (what, run.__name__, r)
    # the number of a certificate's rows
    q = list(p); q[4 + 2 + m] = '2000000000'; u = list(t); u[i] = ' '.join(q)
    for run in (run_kernel, run_python):
        r = run(u)
        assert r and not r[0]['ok'], ('rows', run.__name__)
    # the length and order of the cell
    for head in (f'T {10 ** 9} 10', f'T 288 {10 ** 6}', f'T {10 ** 40} 10'):
        u = [head] + t[1:]
        for run in (run_kernel, run_python):
            r = run(u)
            assert r and not r[0]['ok'], (head, run.__name__)


# replicata: a task that spills its own start, which would claim its node closed if its node is closed.  expectata: refused by both checkers; and a verdict record that goes in a circle, by whatever means, is refused by assemble.  Seen red, 2026-11-04: both checkers and assemble accepted it, a hole found by reading the argument.
def q_forged_circular():
    head = small_task()[:line_index(small_task(), 'R')]
    refused(head + ['S', 'E'], 'a task spilled its own start', 'its own start')
    v = dict(ok=True, why='', nodes=1, closed=1, fixes=0, splits=0, certs=1, open=0)
    for bad in ([dict(v, start='a', spills=['a'])], [dict(v, start='a', spills=['b']), dict(v, start='b', spills=['a'])], [dict(v, start='a', spills=['b', 'c']), dict(v, start='b', spills=[]), dict(v, start='c', spills=['d']), dict(v, start='d', spills=['a'])]):
        try: ft.assemble(['a'], bad); raise AssertionError('a circle accepted')
        except ValueError as err: assert 'cycle' in str(err), err
    # a node reached twice is no circle
    assert ft.assemble(['a'], [dict(v, start='a', spills=['b', 'c']), dict(v, start='b', spills=['d']), dict(v, start='c', spills=['d']), dict(v, start='d', spills=[])])['tasks'] == 4


# replicata: a real closing certificate with all its numbers multiplied by 2^s, up to where the moment multipliers alone, taken without their cancellation, pass 2^114.  expectata: still accepted by both, as W(p) itself stays small: the finer scale a prover retries at must not be refused.  Then with a moment multiplier wrong by a tiny amount at that scale: refused.
def q_scaled_certificates_accepted():
    t = closing_task(); i = line_index(t, 'C'); p = t[i].split(); m = 10
    for s in (8, 16, 24, 30):
        step = min(s, 14)
        q = list(p); q[1] = str(int(p[1]) + step)
        for j in range(3, 3 + m): q[j] = str(int(p[j]) << s)
        k = int(p[3 + m])
        for j in range(k): q[5 + m + 2 * j] = str(int(p[5 + m + 2 * j]) << (s - step))
        u = list(t); u[i] = ' '.join(q)
        a, b = both(u)
        assert a['ok'] and b['ok'], (s, a['why'], b['why'])
        q[3] = str(int(q[3]) + 10 ** 40 if s == 30 else int(q[3]) + 10 ** 36); u[i] = ' '.join(q)
        a, b = both(u)
        assert not a['ok'] and not b['ok'], ('moved', s)


# replicata: a pinned value changed or G flipped at the start.  expectata: the verdict names another node, or the tree no longer closes: it cannot stand for the node it was made for.
def q_forged_start():
    t = small_task(); base = run_kernel(t)[0]
    i = line_index(t, 'P'); p = t[i].split(); q = list(p); q[3] = str(int(p[3]) + 2); u = list(t); u[i] = ' '.join(q)
    a, b = both(u); assert a['start'] != base['start'] and b['start'] != base['start'], 'a value changed, same name'
    i = line_index(t, 'G'); u = list(t); u[i] = 'G 1'
    a, b = both(u); assert a['start'] != base['start'] and b['start'] != base['start'], 'G flipped, same name'


# replicata: a number of a real task's lines changed at random, 400 times.  expectata: each result is refused, or names another node, or changes nothing a verdict claims; never accepted with a different claim by one checker only.
def q_random_corruption():
    t = small_task(); rng = random.Random(1)
    for trial in range(400):
        u = list(t); i = rng.randrange(1, len(u) - 1); p = u[i].split()
        if len(p) < 2: continue
        j = rng.randrange(1, len(p)); x = int(p[j]); p[j] = str(x + rng.choice([-2, -1, 1, 2, 10 ** rng.randrange(1, 30)])); u[i] = ' '.join(p)
        a, b = run_kernel(u), run_python(u)
        assert len(a) == 1 and len(b) == 1, (a, b)
        if a[0]['ok'] and b[0]['ok']: assert a[0] == b[0], (u[i][:80], a[0], b[0])
        elif a[0]['ok'] != b[0]['ok']:
            # the only admissible difference: fkernel refuses a number for its size
            assert not a[0]['ok'] and ('large' in a[0]['why'] or 'out of range' in a[0]['why']), (u[i][:80], a[0], b[0])


# replicata: every form of 288:10's configuration, stated with the grid formtree.py computes.  expectata: fkernel, by its own way to rep(M), accepts each; with a doubled step it refuses each.
def q_grids_agree():
    cell = ft.Cell(288, 10); rng = random.Random(2); lines = ['T 288 10', 'G 0', 'P 0 3 0 1 0 0']; bad = ['T 288 10', 'G 0', 'P 0 3 0 1 0 0']
    forms = []
    for M in (3, 4, 5, 7, 8, 9, 11, 13, 16, 17, 19, 23, 25, 27, 29, 31, 37, 32, 49, 64, 81):
        for _ in range(8):
            w = tuple(rng.randrange(-40, 41) for _ in range(M))
            two_g, c = cell.grid(M, w)
            if two_g: forms.append((M, w, two_g, c % two_g))
    for i, (M, w, st, c) in enumerate(forms):
        t = ['T 288 10', 'G 0', 'P 0 3 0 1 0 0', f'R {i + 1} {M} {st} {c} ' + ' '.join(map(str, w)), 'O', 'E']
        v = run_kernel(t)[0]
        assert v['ok'], (M, w, st, c, v['why'])
        t[3] = f'R {i + 1} {M} {2 * st} {c} ' + ' '.join(map(str, w))
        v = run_kernel(t)[0]
        assert not v['ok'], (M, w, st, c)


# replicata: all sequences of length 16 and 24 with order >= 3 and >= 4, by brute force.  expectata: every form's value lies on the grid the lemma gives, for forms at every prime power: the lemma against the truth, mostly asymmetric sequences.
def q_grids_hold_on_all_small_sequences():
    def solutions(n, m):
        # by moments, half the signs fixed by negation
        out = []
        pw = [[pow(p, k) for p in range(n)] for k in range(m)]
        for bits in range(2 ** (n - 1)):
            a = [1 if bits >> p & 1 else -1 for p in range(n - 1)] + [1]
            if all(sum(x * y for x, y in zip(a, pw[k])) == 0 for k in range(m)): out.append(a)
        return out
    rng = random.Random(3)
    for n, m in ((16, 3), (24, 4)):
        if n == 24:
            # 2^23 is long in Python: the even-sum half, by a meet in the middle on the first moments
            sols = meet_solutions(n, m)
        else:
            sols = solutions(n, m)
        assert sols, (n, m)
        cell = ft.Cell(n, m)
        for M in (3, 4, 5, 7, 8, 9, 11, 13):
            for _ in range(60):
                w = tuple(rng.randrange(-9, 10) for _ in range(M))
                two_g, c = cell.grid(M, w)
                for a in sols:
                    f = sum(a[p] * w[p % M] for p in range(n))
                    assert (f - c) % two_g == 0 if two_g else f == c, (n, m, M, w, f, c, two_g)


def meet_solutions(n, m):
    half = n // 2; left = {}
    for bits in range(2 ** half):
        a = [1 if bits >> p & 1 else -1 for p in range(half)]
        left.setdefault(tuple(sum(a[p] * p ** k for p in range(half)) for k in range(m)), []).append(a)
    out = []
    for bits in range(2 ** (n - half)):
        b = [1 if bits >> p & 1 else -1 for p in range(n - half)]
        key = tuple(-sum(b[p] * (p + half) ** k for p in range(n - half)) for k in range(m))
        for a in left.get(key, ()): out.append(a + b)
    return out


# replicata: the two node names of the same rows, written in a different order.  expectata: one name; another value or modulus or G: another name.
def q_names():
    r = [(3, 0, (1, 0, 0)), (5, -50, (0, 1, 0, 0, 0)), (17, 34, tuple(range(17)))]
    a = ft.node_name(288, 10, 0, r)
    assert a == ft.node_name(288, 10, 0, list(reversed(r)))
    assert a != ft.node_name(288, 10, 1, r)
    assert a != ft.node_name(288, 11, 0, r)
    assert a != ft.node_name(288, 10, 0, r[:2] + [(17, 36, tuple(range(17)))])
    lines = ['T 288 10', 'G 0'] + [f'P {i} {M} {v} ' + ' '.join(map(str, w)) for i, (M, v, w) in enumerate(r)] + ['O', 'E']
    assert run_kernel(lines)[0]['start'] == a and run_python(lines)[0]['start'] == a


# replicata: the top of 288:10, then with a kept node closed by no certificate, a closing certificate dropped, a vector passed over without an image.  expectata: 16 start nodes, each with a name; each change is refused or changes what remains.
def q_top():
    path = os.path.join(PROVER, 'top_288_10.json.gz')
    n, m, starts, stats = ft.check_top(path)
    assert (n, m) == (288, 10) and len(starts) == 16 and stats['kept'] == 16
    data = ft.read_json(path); tokens = data['tokens']
    i = next(j for j, t in enumerate(tokens) if t[0] == 'C')
    forged = tokens[:i] + tokens[i + 1:]
    try:
        r = ft.Top(n, m, forged).run()
    except (ValueError, StopIteration, KeyError, TypeError):
        r = None
    assert r is None or len(r[0]) != 16, 'a token dropped went unnoticed'
    forged = [list(t) for t in tokens]; c = json.loads(json.dumps(forged[i])); c[1]['rows'] = [[M, r, 0] for M, r, x in c[1]['rows']]; forged[i] = c
    try:
        ft.Top(n, m, forged).run(); raise AssertionError('a certificate zeroed went unnoticed')
    except ValueError: pass
    # a closed vector kept and a kept vector closed by nothing
    j = next(j for j, t in enumerate(tokens) if t[0] == 'K')
    forged = [list(t) for t in tokens]; forged[j] = ['C', forged[i][1]]
    try:
        ft.Top(n, m, forged).run(); raise AssertionError("another node's certificate closed a kept node")
    except (ValueError, KeyError): pass


# replicata: a proof with a task missing, a task rejected, an open node, a spilled node with no verdict.  expectata: assemble refuses each, and accepts the whole.
def q_assemble():
    good = [dict(ok=True, start='a', why='', spills=['b', 'c'], nodes=3, closed=3, fixes=0, splits=1, certs=4, open=0), dict(ok=True, start='b', why='', spills=[], nodes=1, closed=1, fixes=0, splits=0, certs=1, open=0), dict(ok=True, start='c', why='', spills=[], nodes=1, closed=1, fixes=0, splits=0, certs=1, open=0)]
    assert ft.assemble(['a'], good)['tasks'] == 3
    for bad, why in ((good[:2], 'no verdict'), ([good[0], good[1], {**good[2], 'ok': False, 'why': 'x'}], 'rejected'), ([good[0], good[1], {**good[2], 'open': 1}], 'open')):
        try: ft.assemble(['a'], bad); raise AssertionError(why)
        except ValueError as err: assert why in str(err), (why, err)
    try: ft.assemble(['a', 'z'], good); raise AssertionError('a start with no verdict')
    except ValueError: pass


def _follow(cell, lines, witness):
    """Replays a task's lines with a real sequence alongside: every claim the checker accepts must hold on it.  Reversal is applied where a symmetric step sends the sequence's mirror on instead."""
    class Follower(ft.Task):
        a = list(witness)
        def form_value(self, i):
            M, w = self.forms[i][:2]
            return sum(self.a[p] * w[p % M] for p in range(cell.n))
        def holds(self):
            return all(self.form_value(i) == self.values[i] for i in self.order)
        def feed(self, kind, numbers):
            if kind == 'R':
                i, M, st, c0, w = numbers[0], numbers[1], numbers[2], numbers[3], tuple(numbers[4:])
                super().feed(kind, numbers)
                v = self.form_value(i)
                assert (v - c0) % st == 0, f'the grid of form {i} misses a real sequence'
                self.stats['grids'] += 1
                return
            if kind == 'C':
                assert not self.holds(), 'a node holding a real sequence was closed'
            if kind == 'B':
                i, sym, k = numbers[0], numbers[1], numbers[2]
                hold = self.holds()
                if hold:
                    v = self.form_value(i)
                    if sym and v < 0:
                        self.a = list(reversed(self.a)); v = self.form_value(i)
                        assert self.holds(), 'the mirror left a node marked closed under reversal'
                    assert k > 0, 'a node holding a real sequence was closed'
                super().feed(kind, numbers)
                if hold:
                    self.stats['followed'] += 1
                    level = self.levels[-1]
                    assert (k == 1 and self.values[i] == v) or (k >= 2 and v in level[4]), f'a value of a real sequence left out: {v}'
                return
            super().feed(kind, numbers)
    t = Follower(cell); t.stats = dict(grids=0, followed=0)
    for line in lines:
        p = line.split()
        if p[0] in 'TE': continue
        t.feed(p[0], [int(x) for x in p[1:]])
    return t.stats


def build_engine():
    lib = os.path.join(BUILD, 'libpex.so')
    if not os.path.exists(lib):
        subprocess.run(['g++', '-O3', '-march=native', '-funroll-loops', '-fassociative-math', '-fno-signed-zeros', '-fno-trapping-math', '-std=c++17', '-shared', '-fPIC', '-o', lib, os.path.join(PROVER, 'pex.cpp')], check=True)
    return lib


def order(a):
    """How many times x - 1 divides a sequence's polynomial, by synthetic division in plain integers."""
    p, k = list(reversed(a)), 0
    while True:
        q, c = [], 0
        for t in p:
            c += t; q.append(c)
        if q.pop(): return k
        p, k = q, k + 1


def sequences(nmax):
    """mstar.py's sequences of order >= 7 and length at most nmax."""
    sys.path.insert(0, ROOT)
    import mstar
    out, seen = [], set()
    for a in itertools.chain(mstar.explicit().values(), (mstar.build(n) for n in range(96, nmax + 1, 8))):
        a = list(a)
        if len(a) < 96 or len(a) > nmax or len(a) % 8 or tuple(a) in seen: continue
        seen.add(tuple(a))
        if order(a) >= 7: out.append((len(a), order(a), a))
    return out


# replicata (engine): a child process with the prover: for each known sequence of length at most 300, its residue sums mod 3, 5, 7 as the start, a few seconds with the stream on, spilling what is left.  expectata: the checkers accept with one verdict, every grid holds on the sequence, every bound holds, no node holding it is closed: the lemma against real sequences at their own order, on the prover's own streams.
def q_engine_real_sequences():
    if importlib.util.find_spec('numpy') is None: print('  skipped: this python has no numpy'); return
    done = 0; tot = dict(grids=0, followed=0)
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, PE_LIB=build_engine(), PYTHONPATH=PROVER, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', WORK=d)
        seqs = sequences(300)
        json.dump(seqs, open(os.path.join(d, 'seqs.json'), 'w'))
        # configurations for these cells are made by tools outside the repository: the qual uses those in FORMTREE_CFG when given, and otherwise only the cells at hand
        cfgs = os.environ.get('FORMTREE_CFG')
        if not cfgs: print('  skipped: set FORMTREE_CFG to a directory of pex2_n_m.cfg files'); return
        code = """
import json, os, sys
import pex as pe
d, cfgs = os.environ['WORK'], os.environ['FORMTREE_CFG']
for i, (n, m, a) in enumerate(json.load(open(d + '/seqs.json'))):
    path = f'{cfgs}/pex2_{n}_{m}.cfg'
    if not os.path.exists(path): continue
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0); continue
    pe.init(n, m, [3, 4, 5, 7, 8, 9, 11, 13, 17, 19], [11, 8, 13, 4, 9, 17, 19], path=path, **pe.RUN_INIT); pe.run_settings()
    pins = {str(M): [sum(a[r::M]) for r in range(M)] for M in (3, 5, 7)}
    s, f = f'{d}/stream_{i}', f'{d}/t_{i}'
    pe.start_file(pins, f)
    pe.lib.pe_certfd(os.open(s, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644))
    pe.run_file(f, 2.0, None, f + 's'); pe.lib.pe_certfd(-1)
    os._exit(0)
"""
        subprocess.run([sys.executable, '-B', '-c', code], env=env, check=True, cwd=PROVER)
        for i, (n, m, a) in enumerate(seqs):
            s = os.path.join(d, f'stream_{i}')
            if not os.path.exists(s): continue
            lines = open(s).read().splitlines()
            a_, b_ = both(lines)
            assert a_['ok'], (n, m, a_['why'])
            assert a_ == b_, (n, m)
            st = _follow(ft.Cell(n, m), lines, a)
            for k in tot: tot[k] += st[k]
            done += 1
    print(f'  {done} sequences; on them {tot["grids"]} grids and {tot["followed"]} bounds held')
    assert done >= 15 and tot['followed'] > 100


# replicata (engine): the whole road on 432:12, which proofs/pintree_432_12.json.gz proves another way: the top checked, the driver run with a short limit so that tasks spill and with every task's stream also given to the Python checker, killed outright at random moments and resumed.  expectata: formtree.py assemble accepts the verdicts; before the end it refuses them; no rejection, no disagreement.
def q_engine_whole_proof_through_kills():
    if importlib.util.find_spec('numpy') is None: print('  skipped: this python has no numpy'); return
    import signal
    lib = build_engine(); W = '11,8,13,4,9,17,19,23,16,25,27,29,31,37'; Mo = '3,4,5,7,8,9,11,13,16,17,19,23,25,27,29,31,37'
    rng = random.Random(4); top = 'top_432_12.json.gz'
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, PE_LIB=lib, FKERNEL=KERNEL, PYTHONPATH=PROVER, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PY_SAMPLE='1')
        cmd = [sys.executable, '-B', '-u', 'ftree.py', '432:12', top, '2', '0.03', W, Mo, os.path.join(d, 'run')]
        kills = 0
        for attempt in range(40):
            with open(os.path.join(d, 'log'), 'a') as log:
                p = subprocess.Popen(cmd, env=env, cwd=PROVER, stdout=log, stderr=log, start_new_session=True)
                try:
                    p.wait(timeout=rng.uniform(0.6, 2.5) if kills < 6 else 240)
                    assert p.returncode == 0, open(os.path.join(d, 'log')).read()[-800:]
                    break
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait(); kills += 1
                    v = os.path.join(d, 'run', 'verdicts.jsonl')
                    if kills == 3 and os.path.exists(v):
                        r = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(ROOT, 'proofs', 'formtree.py'), 'assemble', os.path.join(PROVER, top), v], capture_output=True, text=True)
                        assert r.returncode != 0, 'assemble accepted an unfinished run'
        else:
            raise AssertionError('never finished')
        assert kills >= 3, kills
        text = open(os.path.join(d, 'log')).read()
        assert 'finished:' in text and 'REJECTED' not in text.replace('REJECTED 0', '') and 'PYTHON DISAGREES' not in text, text[-800:]
        r = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(ROOT, 'proofs', 'formtree.py'), 'assemble', os.path.join(PROVER, top), os.path.join(d, 'run', 'verdicts.jsonl')], capture_output=True, text=True)
        assert r.returncode == 0 and 'VERIFIED: no sequence of length 432 has order 12' in r.stdout, (r.stdout, r.stderr)
        print(f'  {kills} kills; {r.stdout.strip()[:150]}')


if __name__ == '__main__':
    names = sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]
    bad = 0
    for k in names:
        t0 = time.time()
        try:
            globals()[k](); print(f'ok   {k} ({time.time() - t0:.1f}s)', flush=True)
        except Exception:
            bad += 1; print(f'FAIL {k}\n{traceback.format_exc()}', flush=True)
    print('all quals pass' if not bad else f'{bad} failed')
    sys.exit(1 if bad else 0)
