#!/usr/bin/env python3
"""Astra's bounded, calibrated search for a 720:11 joined witness.

For p of exact order m, find q of order m with the opposite coefficient of
(x-1)^m. Then p(x)+x^len(p)q(x) has order at least m+1. The unknown q has
reflection sign (-1)^m; the whole joined sequence need not have symmetry.
Empty, timed-out, and completed pruned attempts never exclude any solution.
"""
from contextlib import contextmanager
from math import comb
from pathlib import Path
import fcntl
import hashlib
import json
import os
import random
import resource
import subprocess
import sys
import time

import fpylll
from fpylll import IntegerMatrix, LLL, BKZ, GSO, Enumeration, EnumerationError, EvaluatorStrategy, FPLLL
import sympy as sp
import mstar
from lattice288 import IntegerSystem, atomic_json, valid
from overnight_v5 import gbinom

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'scratch' / 'join720'
JOURNAL = ROOT / 'join720_journal.jsonl'
VERSION, TOTAL, CONTROL_TOTAL, SECONDS, SEED = 1, 16, 4, 45, 20261021
FIXED = {'calibration': (mstar.explicit()[192, 'index.html p192'], 336, 9),
         'search': (mstar.build(336), 384, 10)}
CODE = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in
    ('join720.py', 'lattice288.py', 'mstar.py', 'overnight_v5.py', 'certbb.py'))
    + json.dumps(FIXED, sort_keys=True).encode()).hexdigest()
LIBRARIES = dict(fpylll=fpylll.__version__, sympy=sp.__version__)


def join_model(p, q_n, m):
    """Exact equations A*a=c on the first half of q's signs."""
    assert q_n % 2 == 0 and mstar.order(p) == m and set(p) == {-1, 1}
    h, sign = q_n // 2, (-1) ** m
    A = [[gbinom(i - h, k) + sign * gbinom(q_n - 1 - i - h, k)
          for i in range(h)] for k in range(m % 2, m + 1, 2)]
    c = [0] * len(A)
    c[-1] = -sum(a * comb(i, m) for i, a in enumerate(p))
    assert c[-1] != 0 and sp.Matrix(A).rank() == len(A)
    return dict(p=list(p), q_n=q_n, m=m, A=A, c=c)


def model(phase):
    p, q_n, m = FIXED[phase]
    return join_model(p, q_n, m)


def joined(model, half):
    return model['p'] + list(half) + [(-1) ** model['m'] * a for a in reversed(half)]


def verify(model, half):
    return (len(half) == model['q_n'] // 2 and all(a in (-1, 1) for a in half)
            and valid(joined(model, half), model['m'] + 1))


def working_precision(basis, target):
    """MPFR bits: preserve the largest integer input plus 128 guard bits."""
    return max(212, 128 + max(abs(a).bit_length() for row in basis for a in row),
               128 + max(abs(a).bit_length() for a in target))


def recenter(B, target, perpendicular2):
    """An exact lattice-vector shift, with a checked nearest-plane bound."""
    basis = [list(B[i]) for i in range(B.nrows)]
    FPLLL.set_precision(working_precision(basis, target))
    M = GSO.Mat(B, float_type='mpfr')
    assert M.update_gso()
    shift = B.multiply_left(M.babai([-a for a in target]))
    target = [a + b for a, b in zip(target, shift)]
    # Nearest-plane errors contribute at most one quarter of the sum of
    # Gram-Schmidt squared lengths, itself bounded by the basis row norms.
    bound = perpendicular2 + sp.Rational(sum(a * a for row in basis for a in row), 4)
    assert sum(a * a for a in target) <= bound
    return M, target


def prepare_model(model):
    A, c = model['A'], model['c']
    assert all((v + sum(row)) % 2 == 0 for row, v in zip(A, c))
    system = IntegerSystem(A)
    b = [(v + sum(row)) // 2 for row, v in zip(A, c)]
    target = [2 * a - 1 for a in system.particular(b)]
    radius = system.radius2(c)
    assert 0 < radius < model['q_n'] // 2
    basis = [[2 * a for a in row] for row in system.kernel]
    return dict(model=model, basis=basis, target=target, radius2=str(radius))


def prepare(phase):
    prepared = prepare_model(model(phase))
    atomic_json(WORK / (phase + '.json'), dict(code=CODE, **prepared))
    return prepared


def enumerate_job(prepared, attempt):
    """One randomized BKZ/pruned CVP attempt, independently checked exactly."""
    model = prepared['model']
    seed = SEED + attempt
    FPLLL.set_random_seed(seed)
    FPLLL.set_precision(212)
    rng = random.Random(seed)
    rows = [list(row) for row in prepared['basis']]
    rng.shuffle(rows)
    d = len(rows)
    for i in range(d):
        j = (i + 1 + rng.randrange(d - 1)) % d
        sign = rng.choice((-1, 1))
        rows[i] = [a + sign * b for a, b in zip(rows[i], rows[j])]
    B = IntegerMatrix.from_matrix(rows)
    LLL.reduction(B)
    BKZ.reduction(B, BKZ.Param(block_size=min(20, d), max_loops=8,
                              flags=BKZ.AUTO_ABORT | BKZ.MAX_LOOPS))
    radius2 = sp.Rational(prepared['radius2'])
    M, target = recenter(B, prepared['target'], model['q_n'] // 2 - radius2)
    tau = M.from_canonical([-a for a in target])
    # Enumeration measures only the projection onto the kernel span. Every
    # affine solution has the same nonzero perpendicular component, removed
    # exactly by radius2 = h - c^T (A A^T)^(-1) c.
    radius = float(radius2) + 0.5
    floor = (0.3, 0.4, 0.5, 0.6)[attempt % 4]
    pruning = [max(floor, min(1.0, 1.25 * (1 - i / d) ** 1.5)) for i in range(d)]
    pruning[0] = 1.0
    assert all(0 < a <= 1 for a in pruning)
    assert all(a >= b for a, b in zip(pruning, pruning[1:]))
    # Every point inside this radius has odd coordinates and squared norm at
    # most h+1/2, hence consists entirely of signs. Stop at the first one.
    enum = Enumeration(M, nr_solutions=1, strategy=EvaluatorStrategy.FIRST_N_SOLUTIONS)
    try:
        solutions = enum.enumerate(0, d, radius, 0, target=tau, pruning=pruning)
    except EnumerationError as error:
        assert str(error) == 'No solution found.', str(error)
        solutions = []
    answer = dict(outcome='empty', nodes=enum.get_nodes())
    for distance, coefficients in solutions:
        assert all(abs(a - round(a)) < 1e-6 for a in coefficients)
        v = B.multiply_left([round(a) for a in coefficients])
        half = [a + b for a, b in zip(target, v)]
        assert verify(model, half), (distance, half)
        answer.update(outcome='witness', sequence=joined(model, half))
    return answer


def completed(events, phase):
    return {e['attempt'] for e in events if e['event'] == 'attempt_end' and e['phase'] == phase}


def calibrated(events):
    return any(e['event'] == 'attempt_end' and e['phase'] == 'calibration'
               and e['outcome'] == 'witness' for e in events)


def read_journal(path):
    data = path.read_bytes()
    assert data.endswith(b'\n'), path
    events = [json.loads(line) for line in data.splitlines()]
    h = events[0]
    assert h['event'] == 'header'
    assert (h['version'], h['n'], h['order'], h['total'], h['control_total'], h['seconds']) == (
        VERSION, 720, 11, TOTAL, CONTROL_TOTAL, SECONDS)
    assert h['code'] == CODE and h['libraries'] == LIBRARIES
    assert all(a['time'] <= b['time'] for a, b in zip(events, events[1:]))
    done = {'calibration': set(), 'search': set()}
    phase, active, pid, ended, control, witness = None, None, None, False, False, False
    models = {p: model(p) for p in done}
    for e in events[1:]:
        kind = e['event']
        if kind == 'session':
            phase, active, pid, ended = None, None, e['pid'], False
            continue
        assert e['pid'] == pid and not ended
        if kind == 'phase':
            assert active is None and e['phase'] in ('preparation', 'calibration', 'search')
            phase = e['phase']
            assert phase != 'search' or control
        elif kind == 'attempt_start':
            assert e['phase'] == phase and phase in done and active is None
            a = e['attempt']
            limit = {'calibration': CONTROL_TOTAL, 'search': TOTAL}[phase]
            assert type(a) is int and 0 <= a < limit and a not in done[phase]
            active = a
        elif kind == 'attempt_end':
            assert e['phase'] == phase and e['attempt'] == active and active is not None
            assert e['outcome'] in ('empty', 'timeout', 'witness') and e['elapsed'] >= 0
            if e['outcome'] == 'witness':
                seq, mod = e['sequence'], models[phase]
                assert len(seq) == len(mod['p']) + mod['q_n']
                assert seq[:len(mod['p'])] == mod['p']
                half = seq[len(mod['p']):len(mod['p']) + mod['q_n'] // 2]
                assert seq == joined(mod, half) and verify(mod, half)
                control |= phase == 'calibration'
                witness |= phase == 'search'
            done[phase].add(active)
            active = None
        elif kind == 'finish':
            assert e['outcome'] in ('witness', 'budget', 'control_failed', 'failed')
            assert e['outcome'] != 'witness' or witness
            assert e['outcome'] != 'budget' or (control and len(done['search']) == TOTAL)
            assert e['outcome'] != 'control_failed' or (not control and len(done['calibration']) == CONTROL_TOTAL)
            ended = True
        else:
            assert False, kind
    return events


def record(event, **fields):
    row = dict(event=event, time=time.time(), pid=os.getpid(), **fields)
    with JOURNAL.open('a') as f:
        f.write(json.dumps(row, separators=(',', ':')) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(row, separators=(',', ':')), flush=True)


def bounded(prepared, attempt):
    atomic_json(WORK / 'job.json', dict(code=CODE, prepared=prepared, attempt=attempt))
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, '-B', __file__, '--worker'],
                              capture_output=True, text=True, timeout=SECONDS)
    except subprocess.TimeoutExpired:
        return dict(outcome='timeout', elapsed=time.monotonic() - start)
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert not proc.stderr, proc.stderr
    result = json.loads(proc.stdout)
    result['elapsed'] = time.monotonic() - start
    return result


def worker():
    job = json.loads((WORK / 'job.json').read_text())
    assert job['code'] == CODE
    resource.setrlimit(resource.RLIMIT_CPU, (SECONDS + 5, SECONDS + 5))
    print(json.dumps(enumerate_job(job['prepared'], job['attempt'])), flush=True)


def run():
    WORK.mkdir(parents=True, exist_ok=True)
    if not JOURNAL.exists():
        rows = [dict(event='header', version=VERSION, n=720, order=11, total=TOTAL,
                     control_total=CONTROL_TOTAL, seconds=SECONDS, code=CODE,
                     libraries=LIBRARIES, time=time.time(), pid=os.getpid()),
                dict(event='session', time=time.time(), pid=os.getpid()),
                dict(event='phase', phase='preparation', time=time.time(), pid=os.getpid())]
        tmp = JOURNAL.with_suffix('.jsonl.tmp')
        tmp.write_text(''.join(json.dumps(e, separators=(',', ':')) + '\n' for e in rows))
        tmp.replace(JOURNAL)
    else:
        read_journal(JOURNAL)
        record('session')
        record('phase', phase='preparation')
    events = read_journal(JOURNAL)
    try:
        if any(e['event'] == 'attempt_end' and e['phase'] == 'search'
               and e['outcome'] == 'witness' for e in events):
            record('finish', outcome='witness')
            return
        for phase, limit in (('calibration', CONTROL_TOTAL), ('search', TOTAL)):
            done = completed(events, phase)
            if phase == 'calibration' and calibrated(events):
                continue
            if phase == 'search' and not calibrated(events):
                record('finish', outcome='control_failed')
                return
            prepared = prepare(phase)
            record('phase', phase=phase)
            for attempt in range(limit):
                if attempt in done:
                    continue
                record('attempt_start', phase=phase, attempt=attempt)
                result = bounded(prepared, attempt)
                record('attempt_end', phase=phase, attempt=attempt, **result)
                events = read_journal(JOURNAL)
                if result['outcome'] == 'witness':
                    break
            if phase == 'search' and any(e['event'] == 'attempt_end' and e['phase'] == phase
                                        and e['outcome'] == 'witness' for e in events):
                record('finish', outcome='witness')
                return
            record('phase', phase='preparation')
        record('finish', outcome='budget')
    except BaseException:
        record('finish', outcome='failed')
        raise


@contextmanager
def lock_run():
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    with lock_run():
        run()


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--worker'])
    {'--worker': worker, '': main}[''.join(sys.argv[1:])]()
