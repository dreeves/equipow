#!/usr/bin/env python3
"""Astra's bounded, pruned symmetric witness search for 288:10.

Run with Python containing fpylll, sympy, numpy, and highspy. The JSONL journal
is append-only and resumes completed attempts. An empty or timed-out attempt
does not exclude its case. Even an exhaustive symmetric search would not
exclude a nonsymmetric witness.

The common integer kernel is obtained with a unimodular LLL transformation.
The 2,736 cases survive exact column-lattice checks and exactly verified LP
separations of the other symmetric mod-7 profiles and rare-pair placements.
Only the common basis is reduced; right-hand sides change between attempts.
"""
from itertools import combinations
from contextlib import contextmanager
from math import ldexp
from pathlib import Path
import hashlib
import fcntl
import json
import os
import resource
import subprocess
import sys
import time

import sympy as sp
import fpylll
from fpylll import IntegerMatrix, LLL, BKZ, GSO, Enumeration, EnumerationError, FPLLL
import certbb
import overnight_v5 as ov

VERSION = 1
SECONDS = 30
SEED = 20261020
ROOT = Path(__file__).resolve().parent
JOURNAL = ROOT / 'lattice288_journal.jsonl'
PREPARED = ROOT / '.lattice288_prepared.json'
WORK = ROOT / '.lattice288_work'
CODE = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in
                              ('lattice288.py', 'overnight_v5.py', 'certbb.py'))).hexdigest()
LIBRARIES = dict(fpylll=fpylll.__version__, sympy=sp.__version__, highs=certbb.HIGHS)


def moment_rows(n, order):
    assert n % 2 == 0 and order % 2 == 0
    return [[ov.gbinom(p - n // 2, k) + ov.gbinom(n // 2 - 1 - p, k)
             for p in range(n // 2)] for k in range(0, order, 2)]


def count_rows(n, modulus):
    return [[int(p % modulus == r) + int((n - 1 - p) % modulus == r)
             for p in range(n // 2)] for r in range(modulus)]


def valid(sequence, order):
    return (len(sequence) > 0 and set(sequence) == {-1, 1}
            and all(sum(a * p ** k for p, a in enumerate(sequence)) == 0
                    for k in range(order)))


class IntegerSystem:
    """Exact cosets for A*y=b; kernel rows span every integer null vector."""
    def __init__(self, A):
        self.A = sp.Matrix(A)
        r, d = self.A.shape
        assert self.A.rank() == r and r < d
        B = IntegerMatrix.from_matrix([list(map(int, row)) for row in self.A.T.tolist()])
        U = IntegerMatrix.identity(d)
        LLL.reduction(B, U=U)
        H = sp.Matrix([list(B[i]) for i in range(d)])
        T = sp.Matrix([list(U[i]) for i in range(d)])
        assert T * self.A.T == H and abs(T.det()) == 1
        assert H[:d-r, :] == sp.zeros(d-r, r)
        assert H[d-r:, :].det() != 0
        self.kernel = [list(map(int, row)) for row in T[:d-r, :].tolist()]
        self.lift = T[d-r:, :].T * H[d-r:, :].T.inv()
        self.gram_inverse = (self.A * self.A.T).inv()
        assert self.A * sp.Matrix(self.kernel).T == sp.zeros(r, d-r)

    def particular(self, b):
        y = self.lift * sp.Matrix(b)
        assert all(t.q == 1 for t in y), b
        assert self.A * y == sp.Matrix(b)
        return list(map(int, y))

    def radius2(self, c):
        c = sp.Matrix(c)
        return self.A.cols - (c.T * self.gram_inverse * c)[0]

    def reduced(self):
        FPLLL.set_random_seed(SEED)
        B = IntegerMatrix.from_matrix([[2 * x for x in row] for row in self.kernel])
        LLL.reduction(B)
        BKZ.reduction(B, BKZ.Param(block_size=min(20, B.nrows), max_loops=8,
                                  flags=BKZ.AUTO_ABORT | BKZ.MAX_LOOPS))
        return [list(B[i]) for i in range(B.nrows)]


def enumerate_case(basis, target, radius2, n, order, free, fixed, seed):
    """One pruned attempt; any returned witness is checked in exact integers."""
    assert len(target) == len(free) and set(free).isdisjoint(fixed)
    assert set(free) | set(fixed) == set(range(n // 2))
    assert radius2 >= 0 and all(x % 2 for x in target)
    FPLLL.set_random_seed(seed)
    FPLLL.set_precision(212)
    B = IntegerMatrix.from_matrix(basis)
    M = GSO.Mat(B, float_type='mpfr')
    assert M.update_gso()
    # Removing a lattice vector keeps the coset and avoids large CVP targets.
    shift = B.multiply_left(M.babai([-x for x in target]))
    target = [x + y for x, y in zip(target, shift)]
    tau = M.from_canonical([-x for x in target])
    d = B.nrows
    rr = [M.get_r(i, i) for i in range(d)]
    radius = float(radius2) + 0.5
    # A nearest-plane estimate of the tail's contribution relaxes pruning.
    # These coordinates are heuristic choices, not forced integer values.
    tail = d
    while tail > 0 and rr[tail - 1] > radius:
        tail -= 1
    x, delta = [0] * d, 0.0
    for j in range(d - 1, tail - 1, -1):
        center = tau[j] - sum(x[k] * M.get_mu(k, j) for k in range(j + 1, d))
        x[j] = round(center)
        delta += (x[j] - center) ** 2 * rr[j]
    # The estimated tail contribution sets a floor for a relaxed linear bound.
    # This is a heuristic search, never a certificate of absence.
    assert 0 <= tail <= d
    floor = min(1.0, delta / radius + 0.15)
    pruning = [min(1.0, floor + (d - i) / d) for i in range(d)]
    enum = Enumeration(M, nr_solutions=1)
    try:
        solutions = enum.enumerate(0, d, radius, 0, target=tau, pruning=pruning)
    except EnumerationError as error:
        assert str(error) == 'No solution found.', str(error)
        solutions = []
    answer = dict(outcome='empty', nodes=enum.get_nodes())
    for distance, coefficients in solutions:
        assert all(abs(t - round(t)) < 1e-6 for t in coefficients)
        v = B.multiply_left([round(t) for t in coefficients])
        signs = [t + z for t, z in zip(target, v)]
        assert all(abs(t) == 1 for t in signs), (distance, signs)
        half = dict(fixed) | dict(zip(free, signs))
        sequence = [half[i] for i in range(n // 2)]
        sequence += sequence[::-1]
        assert valid(sequence, order)
        answer.update(outcome='witness', sequence=sequence)
    return answer


def prepare():
    """Regenerate all candidates; every omitted LP case has an exact separator."""
    ov.SETTINGS[288, 10] = ((3, 5, 7), (1, 1, 1, 1000))
    ov.configure(288, 10)
    rows = moment_rows(288, 10) + sum((count_rows(288, m) for m in (5, 3, 7)), [])
    head = [sum(row) // 2 for row in rows[:5]] + [29, 4, 29, 41, 41] + [48] * 3
    fixed = list(range(1, 144, 5))
    free = [p for p in range(144) if p not in fixed]
    A = [[row[p] for p in free] for row in rows]
    exact = ov.ExactSystem(A)
    keep = list(sp.Matrix(A).T.rref()[1])
    W = tuple(tuple(A[i]) for i in keep)
    system = IntegerSystem(W)
    assert len(free) == 115 and len(keep) == 10 and len(system.kernel) == 105
    lp = certbb.Lp(certbb.Moments(W, (0,) * len(W)), ())
    lo, hi = [0] * len(free), [1] * len(free)
    profiles = [c for c in ov.admissible(10, 7, ())
                if all(c[r] == c[(287 - r) % 7] for r in range(7))]
    assert len(profiles) == 14
    cases = []
    for profile in profiles:
        for pair in combinations(fixed, 2):
            b = [t - sum(row[p] for p in pair) for row, t in zip(rows, head + list(profile))]
            assert exact.solvable(b)
            beta = tuple(b[i] for i in keep)
            for k, (tk, sk) in enumerate(zip(lp.T, lp.s)):
                v = ldexp(float(sum(t * r for t, r in zip(tk, beta))), -sk)
                lp.H.changeRowBounds(k, v, v)
            assert lp.H.clearSolver() == certbb.highs.HighsStatus.kOk
            status, result = lp.solve(lo, hi)
            assert status in ('Optimal', 'Infeasible'), status
            if status == 'Infeasible':
                certificate = lp.multipliers(result)
                assert certbb.lower_bound(certbb.Moments(W, beta).sparse,
                                          lo, hi, certificate) > 0
                continue
            target = [2 * x - 1 for x in system.particular(beta)]
            c = [2 * t - sum(row) for row, t in zip(W, beta)]
            radius = system.radius2(c)
            assert radius >= 0
            cases.append(dict(profile=list(profile), pair=list(pair),
                              target=target, radius=str(radius)))
    assert len(cases) == 2736
    # Try promising placements within every surviving profile before moving
    # to its next placement; a short pilot therefore covers all seven profiles.
    groups = [[c for c in cases if c['profile'] == list(p)] for p in profiles]
    for group in groups:
        group.sort(key=lambda c: (-sp.Rational(c['radius']), c['pair']))
    cases = [group[i] for i in range(max(map(len, groups))) for group in groups if i < len(group)]
    return dict(code=CODE, basis=system.reduced(), free=free, fixed=fixed, cases=cases)


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, separators=(',', ':')) + '\n')
    tmp.replace(path)


def read_journal(path):
    data = path.read_bytes()
    assert data.endswith(b'\n'), path
    events = [json.loads(line) for line in data.splitlines()]
    assert events and events[0]['event'] == 'header'
    h = events[0]
    assert (h['version'], h['n'], h['order'], h['total'], h['seconds'], h['seed']) == (
        VERSION, 288, 10, 2736, SECONDS, SEED)
    assert all(a['time'] <= b['time'] for a, b in zip(events, events[1:]))
    done, active, phase, ended, pid, witnessed = set(), None, None, False, None, False
    for e in events[1:]:
        kind = e['event']
        if kind == 'session':
            active, phase, ended, pid = None, None, False, e['pid']
            continue
        assert e['pid'] == pid and not ended
        if kind == 'phase':
            assert active is None and e['phase'] in ('preparation', 'calibration', 'search')
            phase = e['phase']
        elif kind == 'case_start':
            i = e['case']
            assert type(i) is int and 0 <= i < h['total']
            assert phase == 'search' and active is None and i not in done
            active = i
        elif kind == 'case_end':
            assert type(e['case']) is int and e['case'] == active and active is not None
            assert e['outcome'] in ('empty', 'timeout', 'witness') and e['elapsed'] >= 0
            assert e['outcome'] != 'witness' or (len(e['sequence']) == 288 and valid(e['sequence'], 10))
            witnessed |= e['outcome'] == 'witness'
            assert active not in done
            done.add(active)
            active = None
        elif kind == 'finish':
            assert e['outcome'] in ('exhausted', 'witness', 'failed')
            assert e['outcome'] != 'exhausted' or len(done) == h['total']
            assert e['outcome'] != 'witness' or witnessed
            ended = True
        else:
            assert False, kind
    return events


def completed(events):
    return {e['case'] for e in events if e['event'] == 'case_end'}


def record(event, **fields):
    row = dict(event=event, time=time.time(), pid=os.getpid(), **fields)
    with JOURNAL.open('a') as f:
        f.write(json.dumps(row, separators=(',', ':')) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(row, separators=(',', ':')), flush=True)


def bounded(job, seconds):
    WORK.mkdir(exist_ok=True)
    atomic_json(WORK / 'job.json', dict(code=CODE, **job))
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, '-B', __file__, '--worker'],
                              capture_output=True, text=True, timeout=seconds)
    except subprocess.TimeoutExpired:
        return dict(outcome='timeout', elapsed=time.monotonic() - start)
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert not proc.stderr, proc.stderr
    result = json.loads(proc.stdout)
    result['elapsed'] = time.monotonic() - start
    return result


def worker():
    job = json.loads((WORK / 'job.json').read_text())
    assert job.pop('code') == CODE
    # The parent enforces wall time. This hard CPU limit also bounds an orphan
    # if the parent itself is killed during a native enumeration call.
    resource.setrlimit(resource.RLIMIT_CPU, (SECONDS + 5, SECONDS + 5))
    job['radius2'] = sp.Rational(job['radius2'])
    job['fixed'] = {int(k): v for k, v in job['fixed'].items()}
    print(json.dumps(enumerate_case(**job)), flush=True)


def calibration_job():
    # Discover a control without supplying any coordinates or residue counts.
    A = moment_rows(144, 8)
    b = [sum(row) // 2 for row in A]
    system = IntegerSystem(A)
    target = [2 * x - 1 for x in system.particular(b)]
    c = [2 * t - sum(row) for row, t in zip(A, b)]
    return dict(basis=system.reduced(), target=target, radius2=str(system.radius2(c)),
                n=144, order=8, free=list(range(72)), fixed={}, seed=SEED)


def run():
    fresh = not JOURNAL.exists()
    if fresh:
        rows = [dict(event='header', version=VERSION, n=288, order=10, total=2736,
                     seconds=SECONDS, seed=SEED, code=CODE, libraries=LIBRARIES,
                     budget_unit='wall seconds',
                     time=time.time(), pid=os.getpid()),
                dict(event='session', time=time.time(), pid=os.getpid())]
        tmp = JOURNAL.with_suffix('.jsonl.tmp')
        tmp.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        tmp.replace(JOURNAL)
    events = read_journal(JOURNAL)
    assert events[0]['code'] == CODE and events[0]['libraries'] == LIBRARIES
    assert not any(e['event'] == 'finish' and e['outcome'] in ('witness', 'exhausted') for e in events)
    if not fresh:
        record('session')
    try:
        record('phase', phase='calibration')
        control = bounded(calibration_job(), SECONDS)
        record('phase', phase='calibration', n=144, order=8, **control)
        assert control['outcome'] == 'witness' and valid(control['sequence'], 8), control
        record('phase', phase='preparation')
        prepared = prepare()
        # This is an inspection artifact, regenerated with exact checks on
        # each resume; it is not trusted as an unchecked cache.
        atomic_json(PREPARED, prepared)
        record('phase', phase='search')
        done = completed(events)
        for i, case in enumerate(prepared['cases']):
            if i in done:
                continue
            record('case_start', case=i, profile=case['profile'], pair=case['pair'])
            fixed = {p: 2 * int(p in case['pair']) - 1 for p in prepared['fixed']}
            result = bounded(dict(basis=prepared['basis'], target=case['target'],
                                  radius2=case['radius'], n=288, order=10,
                                  free=prepared['free'], fixed=fixed, seed=SEED + i), SECONDS)
            record('case_end', case=i, **result)
            if result['outcome'] == 'witness':
                assert valid(result['sequence'], 10)
                record('finish', outcome='witness')
                return
        record('finish', outcome='exhausted')
    except BaseException:
        record('finish', outcome='failed')
        raise


@contextmanager
def lock_run():
    WORK.mkdir(exist_ok=True)
    with (WORK / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    with lock_run():
        run()


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--worker'])
    {'--worker': worker, '': main}[''.join(sys.argv[1:])] ()
