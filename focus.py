"""Astra's focused, certified proof searches for 480:14 and 672:13.

The numerical guide receives exact orthogonal polynomial moments. The degree-k
row has nonzero leading coefficient, so the first m rows span precisely the
polynomials of degree below m. All exclusions are checked with integer rows.
"""
from fractions import Fraction
from functools import reduce
from math import gcd, lcm

import certbb


def orthogonal(n, m):
    """Integer polynomial rows orthogonal on the positions 0,...,n-1.

    With x=2p-n+1, the monic discrete orthogonal polynomials obey
    P[k+1]=x P[k]-k^2(n^2-k^2)/(4k^2-1) P[k-1]. Clearing denominators and
    dividing each row's gcd preserve its degree and rational span.
    """
    assert 1 <= m <= n
    x = tuple(2 * p - n + 1 for p in range(n))
    previous, current = (Fraction(1),) * n, tuple(map(Fraction, x))
    rows = [previous, current]
    for k in range(1, m - 1):
        beta = Fraction(k * k * (n * n - k * k), 4 * k * k - 1)
        previous, current = current, tuple(t * a - beta * b for t, a, b in zip(x, current, previous))
        rows.append(current)
    out = []
    for row in rows[:m]:
        den = lcm(*(a.denominator for a in row))
        values = tuple(int(a * den) for a in row)
        factor = reduce(gcd, values)
        out.append(tuple(a // factor for a in values))
    assert all(sum(a * b for a, b in zip(out[i], out[j])) == 0
               for i in range(m) for j in range(i))
    return tuple(out)


def moments(n, m):
    """The sign equations in 0/1 variables x=(a+1)/2, for certbb."""
    rows = orthogonal(n, m)
    assert all(sum(row) % 2 == 0 for row in rows)
    return certbb.Moments(rows, tuple(sum(row) // 2 for row in rows))


import argparse
import fcntl
import gzip
import hashlib
import itertools
import json
import os
import time
from pathlib import Path

import mstar


def prime_prepare(n, m):
    """All necessary count profiles; no assumption of symmetric signs."""
    assert n % 4 == 0 and n < 2 ** m
    profiles = []
    for M in (2, 3, 5, 7):
        ds = tuple(mstar.residue_vectors(n, M, m, None, mstar.Budget(10 ** 6), 'natural'))
        profiles.append(tuple((M, tuple((d + len(range(r, n, M))) // 2 for r, d in enumerate(D))) for D in ds))
    assert profiles[0] == ((2, (n // 4, n // 4)),)
    return moments(n, m), tuple(itertools.product(*profiles))


def prepare(n, m):
    """Complete case reductions, checked before the first search node."""
    from focus480 import prepare as prepare480
    from focus672 import prepare as prepare672
    assert (n, m) in ((480, 14), (672, 13))
    return {480: prepare480, 672: prepare672}[n]()


def fingerprint():
    """Only proof-generation/checking sources enter the continuation identity."""
    root = Path(__file__).resolve().parent
    return hashlib.sha256(b''.join((root / name).read_bytes()
                                  for name in ('focus.py', 'focus480.py', 'focus672.py',
                                               'focus480_certificates.json.gz', 'certbb.py',
                                               'mstar.py', 'overnight_v5.py'))).hexdigest()


class State:
    """A checked proof prefix; frontier paths are reconstructed from its tokens."""
    def __init__(self, equations, cases):
        self.equations, self.cases = equations, cases
        self.frontier = [(c, ()) for c in reversed(range(len(cases)))]
        self.completed, self.lp, self.closed, self.split = [], 0, 0, 0
        self.witness, self.outcome, self.chunks = None, None, 0
        self.check = self.checker()

    @property
    def case(self):
        return self.frontier[-1][0] if self.frontier else None

    def checker(self):
        if self.case is None:
            return None
        return certbb.Check(self.equations, tuple((M, (v,)) for M, v in self.cases[self.case]))

    def box(self):
        lo, hi = [0] * self.equations.N, [1] * self.equations.N
        for p, t in self.frontier[-1][1]:
            assert lo[p] == 0 and hi[p] == 1 and t in (0, 1)
            lo[p] = hi[p] = t
        return lo, hi

    def feed(self, record):
        assert set(record) == {'case', 'token'} and record['case'] == self.case
        token = tuple(record['token'])
        assert len(token) == 2 and token[0] in ('B', 'L', 'W')
        case, path = self.frontier[-1]
        self.lp += 1
        if token[0] == 'W':
            x = token[1]
            lo, hi = self.box()
            assert len(x) == len(lo) and all(type(t) is int and l <= t <= u for t, l, u in zip(x, lo, hi))
            assert certbb.point_certificate(certbb.node_rows(self.equations, self.cases[case]), x) is None
            self.witness, self.outcome = x, 'witness'
            return
        self.check.feed(token)
        self.frontier.pop()
        if token[0] == 'B':
            self.split += 1
            self.frontier += [(case, path + ((token[1], 1),)), (case, path + ((token[1], 0),))]
        else:
            self.closed += 1
        if self.case != case:
            self.check.end()
            self.completed.append(case)
            self.check = self.checker()

    def snapshot(self):
        return dict(lp=self.lp, closed=self.closed, split=self.split, pending=len(self.frontier),
                    case=self.case, completed=self.completed, frontier=self.frontier,
                    witness=self.witness, outcome=self.outcome)


def replay(directory, equations, cases, code):
    """Replay every committed chunk; a prefix may stop only at a token boundary."""
    state = State(equations, cases)
    for i, path in enumerate(sorted(Path(directory).glob('chunk-*.json.gz'))):
        assert path.name == f'chunk-{i:08d}.json.gz'
        assert state.outcome not in ('excluded', 'witness')
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            chunk = json.load(stream)
        assert set(chunk) == {'version', 'index', 'code', 'n', 'order', 'records', 'checkpoint'}
        assert (chunk['version'], chunk['index'], chunk['code'], chunk['n'], chunk['order']) == (
            1, i, code, equations.N, equations.order)
        state.outcome = None
        for record in chunk['records']:
            assert state.outcome != 'witness'
            state.feed(record)
        outcome = chunk['checkpoint']['outcome']
        assert outcome in (None, 'budget', 'excluded', 'witness')
        assert (outcome != 'excluded' or not state.frontier) and (outcome != 'witness' or state.witness is not None)
        assert (state.witness is None) == (outcome != 'witness')
        state.outcome = outcome
        assert json.loads(json.dumps(state.snapshot())) == chunk['checkpoint']
        state.chunks += 1
    return state


def commit(directory, state, records, code):
    """Atomic gzip rename commits proof records and their checkpoint together."""
    path = Path(directory) / f'chunk-{state.chunks:08d}.json.gz'
    assert not path.exists()
    temporary = path.with_suffix('.tmp')
    chunk = dict(version=1, index=state.chunks, code=code, n=state.equations.N,
                 order=state.equations.order, records=records, checkpoint=state.snapshot())
    with open(temporary, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as zipped:
            zipped.write(json.dumps(chunk, separators=(',', ':')).encode())
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(temporary, path)
    state.chunks += 1


def step(lp, equations, choice, lo, hi):
    """One numerical solve proposes a token; exact arithmetic decides its meaning."""
    rows = certbb.node_rows(equations, choice)
    status, z = lp.solve(lo, hi)
    if status == 'Optimal':
        x = [round(t) for t in z]
        if all(l <= t <= u for t, l, u in zip(x, lo, hi)) and certbb.point_certificate(rows, x) is None:
            return ('W', x)
    if status == 'Infeasible' and z is not None:
        certificate = lp.multipliers(z)
        if certbb.lower_bound(rows, lo, hi, certificate) > 0:
            return ('L', certificate)
    if lo == hi:
        certificate = certbb.point_certificate(rows, lo)
        return ('W', lo) if certificate is None else ('L', certificate)
    return ('B', certbb.choose(z if status == 'Optimal' else None, lo, hi, 'ends'))


def search(directory, journal, n, m, lp_budget=10 ** 6, seconds=3600):
    """One resumable pass. A budget outcome leaves every remaining box open."""
    directory, journal = Path(directory), Path(journal)
    directory.mkdir(parents=True, exist_ok=True)
    assert type(lp_budget) is int and lp_budget > 0 and seconds > 0
    with open(directory / 'run.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        equations, cases = prepare(n, m)
        code = fingerprint()
        state = replay(directory, equations, cases, code)
        header = dict(event='header', version=1, n=n, order=m, total=len(cases), code=code)
        previous = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
        def event_record(event, **fields):
            return dict(event=event, time=time.time(), pid=os.getpid(), **fields)
        def view(event):
            snapshot = state.snapshot()
            return event_record(event, **{k: v for k, v in snapshot.items() if k not in ('frontier', 'witness')})
        def write_journal(path, mode, records):
            with path.open(mode) as stream:
                stream.write(''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in records))
                stream.flush()
                os.fsync(stream.fileno())
        def progress(event):
            write_journal(journal, 'a', [view(event)])
        terminal = state.outcome in ('excluded', 'witness')
        state.outcome = state.outcome if terminal else None
        header_record = event_record('header', **{k: v for k, v in header.items() if k != 'event'})
        initial = [event_record('session'), view('finish' if terminal else 'update')]
        if previous:
            assert {k: previous[0][k] for k in header} == header
            write_journal(journal, 'a', initial)
        else:
            temporary = journal.with_suffix(journal.suffix + '.tmp')
            initial.insert(0, header_record)
            write_journal(temporary, 'w', initial)
            os.replace(temporary, journal)
        if terminal:
            return state.outcome
        started, checkpoint = time.monotonic(), time.monotonic()
        initial_lp, records, current, lp = state.lp, [], None, None
        while state.frontier and state.witness is None and state.lp - initial_lp < lp_budget and time.monotonic() - started < seconds:
            if state.case != current:
                current = state.case
                choice = cases[current]
                lp = certbb.Lp(equations, tuple(M for M, _ in choice))
                lp.set_counts(choice)
            record = dict(case=current, token=step(lp, equations, choice, *state.box()))
            state.feed(record)
            records.append(record)
            if time.monotonic() - checkpoint >= 5 and state.frontier and state.witness is None:
                commit(directory, state, records, code)
                records = []
                progress('update')
                checkpoint = time.monotonic()
        state.outcome = 'witness' if state.witness is not None else ('excluded' if not state.frontier else 'budget')
        commit(directory, state, records, code)
        progress('finish')
        return state.outcome


def main():
    # TODO: command help; bounded, resumable searches with exact proof checks.
    parser = argparse.ArgumentParser(description='Quaestiones finitae, resumendae, probationibus exactis.')
    parser.add_argument('n', type=int, choices=(480, 672))
    parser.add_argument('--lp-budget', type=int, default=10 ** 6)
    parser.add_argument('--seconds', type=float, default=3600)
    args = parser.parse_args()
    m = {480: 14, 672: 13}[args.n]
    outcome = search(Path(f'scratch/focus{args.n}/run'), Path(f'focus_{args.n}_journal.jsonl'),
                     args.n, m, args.lp_budget, args.seconds)
    print(json.dumps(dict(n=args.n, order=m, outcome=outcome)), flush=True)


if __name__ == '__main__':
    main()
