#!/usr/bin/env python3
"""A bounded 592 witness pilot, gated by an independent 560 recovery.

One worker prepares a shared lattice and a deterministic placement plan per
phase. Empty pruned attempts and timeouts establish no exclusion.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

import fpylll
import numpy
import residue592 as R
import search592_geometry as G
from lattice288 import valid


ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'scratch' / 'search592'
JOURNAL = ROOT / 'search592_journal.jsonl'
CONTROL_TOTAL, TOTAL, SECONDS, PREP_SECONDS = 32, 32, 30, 600
QUESTIONS = dict(calibration=(560, 10), search=(592, 10))
SETTINGS = dict(calibration=dict(seed=6, slice_index=2, nslices=4),
                search=dict(seed=20261025, slice_index=0, nslices=1))
PROFILES = {p: R.profile(n) for p, (n, _) in QUESTIONS.items()}
INPUT = {p: G.digest(profile) for p, profile in PROFILES.items()}
SOURCES = ('search592.py', 'residue592.py') + G.SOURCES
CODE = hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in SOURCES)).hexdigest()
LIBRARIES = dict(fpylll=fpylll.__version__, sympy=G.sp.__version__, numpy=numpy.__version__)
IDENTITY = ('basis_hash', 'profile_hash', 'plan_hash')
FIELDS = ('case', 'seed', 'slice_index', 'nslices', *IDENTITY, 'placement', 'shape')


def limits():
    return dict(calibration=CONTROL_TOTAL, search=TOTAL)


def header():
    return dict(event='header', version=1, n=592, order=10, control_n=560,
                control_order=10, total=TOTAL, control_total=CONTROL_TOTAL,
                seconds=SECONDS, preparation_seconds=PREP_SECONDS, settings=SETTINGS,
                shape=list(G.SHAPE), code=CODE, input=INPUT, libraries=LIBRARIES)


def completed(rows, phase):
    return {r['attempt'] for r in rows if r['event'] == 'attempt_end' and r['phase'] == phase}


def witnessed(rows, phase):
    return any(r['event'] == 'attempt_end' and r['phase'] == phase and r['outcome'] == 'witness'
               for r in rows)


def check_fields(phase, attempt, fields):
    assert type(attempt) is int and 0 <= attempt < limits()[phase]
    assert fields['case'] == attempt and fields['shape'] == list(G.SHAPE)
    assert all(fields[k] == v for k, v in SETTINGS[phase].items())
    assert all(type(fields[k]) is str and len(fields[k]) == 64 and
               all(c in '0123456789abcdef' for c in fields[k]) for k in IDENTITY)
    assert fields['profile_hash'] == INPUT[phase]
    placement = fields['placement']
    assert set(placement) == {'prefix', 'choices', 'cursor'}
    assert type(placement['prefix']) is int and placement['prefix'] >= 0
    assert type(placement['choices']) is list and placement['choices']
    assert type(placement['cursor']) is list and len(placement['cursor']) == 2
    assert all(type(x) is int and x >= 0 for x in placement['choices'] + placement['cursor'])
    assert placement['cursor'][0] % fields['nslices'] == fields['slice_index']


def check_answer(phase, attempt, answer, expected_fields=None):
    check_fields(phase, attempt, answer)
    assert all(answer[k] == v for k, v in (expected_fields or {}).items())
    assert answer['outcome'] in ('empty', 'timeout', 'witness')
    assert math.isfinite(answer['elapsed']) and answer['elapsed'] >= 0
    if answer['outcome'] == 'timeout':
        assert all(answer[k] is None for k in ('nodes', 'enumeration_seconds', 'geometry_hash', 'radius2'))
    else:
        assert math.isfinite(answer['enumeration_seconds'])
        assert 0 <= answer['enumeration_seconds'] <= answer['elapsed']
        assert type(answer['geometry_hash']) is str and len(answer['geometry_hash']) == 64
        assert all(c in '0123456789abcdef' for c in answer['geometry_hash'])
        assert type(answer['radius2']) is str and G.sp.Rational(answer['radius2']).is_Rational
        assert type(answer['raw_nodes']) is int and 0 <= answer['raw_nodes'] < 2**64
        assert all(type(x) is int and 0 <= x < 2**64 for x in answer['node_levels'])
        missing = 2**64 - 1 in answer['node_levels']
        assert (answer['nodes'] is None) == missing
        assert missing or (type(answer['nodes']) is int and answer['nodes'] == answer['raw_nodes'])
        assert not missing or answer['outcome'] == 'empty'
    if answer['outcome'] == 'witness':
        n, order = QUESTIONS[phase]
        sequence = answer['sequence']
        assert all(type(a) is int and a in (-1, 1) for a in sequence)
        assert len(sequence) == n and sequence == sequence[::-1] and valid(sequence, order)


def read_journal():
    """Replay all transitions and exact witnesses once before resuming."""
    data = JOURNAL.read_bytes()
    assert data.endswith(b'\n')
    rows = [json.loads(line) for line in data.splitlines()]
    assert all(rows[0][k] == v for k, v in header().items())
    assert all(a['time'] <= b['time'] for a, b in zip(rows, rows[1:]))
    done = {p: set() for p in QUESTIONS}
    identities = {}
    state = dict(pid=None, phase='preparation', active=None, finish=None,
                 calibration=False, search=False)

    def session(row):
        assert state['finish'] in (None, 'failed')
        state.update(pid=row['pid'], phase='preparation', active=None, finish=None)

    def phase(row):
        p = row['phase']
        assert p in ('preparation', 'calibration', 'search') and state['active'] is None
        assert p != 'search' or state['calibration']
        if p != 'preparation':
            identity = {k: row[k] for k in IDENTITY}
            assert identities.setdefault(p, identity) == identity
        state['phase'] = p

    def start(row):
        p, i = row['phase'], row['attempt']
        assert p == state['phase'] and p in QUESTIONS and state['active'] is None
        assert i not in done[p] and not state[p]
        check_fields(p, i, row)
        assert all(row[k] == v for k, v in identities[p].items())
        state['active'] = row

    def end(row):
        p, i = row['phase'], row['attempt']
        assert state['active'] is not None
        start = state['active']
        assert (p, i) == (start['phase'], start['attempt'])
        check_answer(p, i, row, {k: start[k] for k in FIELDS})
        state[p] |= row['outcome'] == 'witness'
        done[p].add(i)
        state['active'] = None

    def finish(row):
        outcome = row['outcome']
        assert outcome in ('witness', 'budget', 'control_failed', 'failed')
        assert outcome == 'failed' or state['active'] is None
        assert outcome != 'witness' or state['search']
        assert outcome != 'budget' or (state['calibration'] and len(done['search']) == TOTAL)
        assert outcome != 'control_failed' or (not state['calibration'] and len(done['calibration']) == CONTROL_TOTAL)
        state['finish'] = outcome

    handlers = dict(session=session, phase=phase, attempt_start=start, attempt_end=end, finish=finish)
    for row in rows[1:]:
        assert row['event'] in handlers and type(row['pid']) is int
        assert row['event'] == 'session' or (row['pid'] == state['pid'] and state['finish'] is None)
        handlers[row['event']](row)
    return rows


def record(event, **fields):
    row = dict(event=event, time=time.time(), pid=os.getpid(), **fields)
    text = json.dumps(row, separators=(',', ':'))
    with JOURNAL.open('a') as stream:
        stream.write(text+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(text, flush=True)
    return row


def initialize():
    WORK.mkdir(parents=True, exist_ok=True)
    assert not JOURNAL.exists()
    common = dict(time=time.time(), pid=os.getpid())
    rows = [dict(header(), **common), dict(common, event='session'),
            dict(common, event='phase', phase='preparation')]
    text = ''.join(json.dumps(r, separators=(',', ':'))+'\n' for r in rows)
    temporary = WORK/'initial.jsonl'
    with temporary.open('w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, JOURNAL)
    print(text, end='', flush=True)
    return rows


class Worker:
    """One JSON-lines child; timeouts kill and reap it before replacement."""
    def __init__(self, command=(sys.executable, '-B', __file__, '--worker')):
        self.command = command
        self.process = self.selector = self.prepared = self.phase = None
        self.buffer = b''

    def receive(self, deadline):
        while b'\n' not in self.buffer:
            events = self.selector.select(max(0, deadline-time.monotonic()))
            if not events:
                raise TimeoutError
            for key, _ in events:
                chunk = os.read(key.fileobj.fileno(), 65536)
                assert key.data == 'stdout' and chunk, (key.data, chunk, self.process.poll())
                self.buffer += chunk
        line, _, self.buffer = self.buffer.partition(b'\n')
        return json.loads(line)

    def ready(self, phase):
        if self.process is None:
            self.phase = phase
            self.process = subprocess.Popen([*self.command, phase], stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            self.selector = selectors.DefaultSelector()
            self.selector.register(self.process.stdout, selectors.EVENT_READ, 'stdout')
            self.selector.register(self.process.stderr, selectors.EVENT_READ, 'stderr')
            self.prepared = self.receive(time.monotonic()+PREP_SECONDS)
            assert self.prepared['event'] == 'ready'
            assert self.prepared['code'] == CODE and self.prepared['input'] == INPUT
            assert self.prepared['phase'] == phase
            plan = self.prepared['plan']
            assert len(plan) == limits()[phase]
            assert len({G.digest(p['case']) for p in plan}) == len(plan)
            assert self.prepared['plan_hash'] == G.digest(plan)
            summary = self.prepared['summary']
            assert summary['profile_hash'] == INPUT[phase]
            assert (summary['n'], summary['order']) == QUESTIONS[phase]
            assert all(summary[k] == v for k, v in SETTINGS[phase].items())
            for i in range(limits()[phase]):
                check_fields(phase, i, self.fields(phase, i))
        assert self.phase == phase and self.process.poll() is None
        return {k: self.fields(phase, 0)[k] for k in IDENTITY}

    def fields(self, phase, attempt):
        assert self.phase == phase and self.prepared is not None
        summary = self.prepared['summary']
        return dict(case=attempt, **SETTINGS[phase], shape=list(G.SHAPE),
                    basis_hash=summary['basis_hash'], profile_hash=summary['profile_hash'],
                    plan_hash=self.prepared['plan_hash'], placement=self.prepared['plan'][attempt]['case'])

    def execute(self, phase, attempt):
        assert self.process is not None and self.process.poll() is None
        fields = self.fields(phase, attempt)
        started = time.monotonic()
        self.process.stdin.write((json.dumps(dict(attempt=attempt))+'\n').encode())
        self.process.stdin.flush()
        try:
            result = self.receive(started+SECONDS)
        except TimeoutError:
            self.close()
            return dict(fields, outcome='timeout', elapsed=time.monotonic()-started,
                        nodes=None, enumeration_seconds=None, geometry_hash=None, radius2=None)
        assert result['code'] == CODE and result['input'] == INPUT
        assert (result['phase'], result['attempt'], result['plan_hash']) == (phase, attempt, fields['plan_hash'])
        answer = result['answer']
        assert answer['outcome'] != 'timeout'
        assert all(answer[k] == fields[k] for k in ('seed', 'shape', 'basis_hash'))
        answer.update(fields, elapsed=time.monotonic()-started)
        check_answer(phase, attempt, answer, fields)
        return answer

    def close(self):
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.selector.close()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()
        self.process = self.selector = self.prepared = self.phase = None
        self.buffer = b''


def worker(phase):
    instance = G.Instance(PROFILES[phase], **SETTINGS[phase])
    plan, cursor = [], [SETTINGS[phase]['slice_index'], 0]
    for _ in range(limits()[phase]):
        item = instance.next_case(cursor)
        assert item is not None
        plan.append(item)
        cursor = item['next_cursor']
    plan_hash = G.digest(plan)
    print(json.dumps(dict(event='ready', phase=phase, code=CODE, input=INPUT,
                          summary=instance.summary(), plan=plan, plan_hash=plan_hash)), flush=True)
    for line in sys.stdin:
        job = json.loads(line)
        assert set(job) == {'attempt'} and type(job['attempt']) is int
        attempt = job['attempt']
        assert 0 <= attempt < limits()[phase]
        answer = instance.enumerate_case(plan[attempt]['case'])
        answer.pop('curve')
        print(json.dumps(dict(code=CODE, input=INPUT, phase=phase, attempt=attempt,
                              plan_hash=plan_hash, answer=answer)), flush=True)


def run():
    WORK.mkdir(parents=True, exist_ok=True)
    if JOURNAL.exists():
        rows = read_journal()
        if rows[-1]['event'] == 'finish' and rows[-1]['outcome'] != 'failed':
            return
        record('session')
        record('phase', phase='preparation')
    else:
        rows = initialize()
    done = {p: completed(rows, p) for p in QUESTIONS}
    identities = {r['phase']: {k: r[k] for k in IDENTITY} for r in rows
                  if r['event'] == 'phase' and r['phase'] != 'preparation'}
    control = witnessed(rows, 'calibration')
    child = Worker()
    try:
        if witnessed(rows, 'search'):
            record('finish', outcome='witness')
            return
        for phase, limit in limits().items():
            if phase == 'calibration' and control:
                continue
            if phase == 'search' and not control:
                record('finish', outcome='control_failed')
                return
            for attempt in sorted(set(range(limit))-done[phase]):
                assert shutil.disk_usage(ROOT).free >= 100 << 30
                record('phase', phase='preparation')
                identity = child.ready(phase)
                assert identities.setdefault(phase, identity) == identity
                record('phase', phase=phase, **identity)
                fields = child.fields(phase, attempt)
                check_fields(phase, attempt, fields)
                record('attempt_start', phase=phase, attempt=attempt, **fields)
                answer = child.execute(phase, attempt)
                check_answer(phase, attempt, answer, fields)
                record('attempt_end', phase=phase, attempt=attempt, **answer)
                done[phase].add(attempt)
                control |= phase == 'calibration' and answer['outcome'] == 'witness'
                if phase == 'search' and answer['outcome'] == 'witness':
                    record('finish', outcome='witness')
                    return
                if phase == 'calibration' and control:
                    break
            child.close()
        record('finish', outcome='budget')
    except BaseException:
        record('finish', outcome='failed')
        raise
    finally:
        child.close()


@contextmanager
def lock_run():
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK/'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    assert shutil.disk_usage(ROOT).free >= 100 << 30
    with lock_run():
        run()


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--worker', 'calibration'], ['--worker', 'search'])
    if sys.argv[1:]:
        worker(sys.argv[2])
    else:
        main()
