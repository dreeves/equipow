#!/usr/bin/env python3
"""A calibrated wider-pruning sweep with one persistent compute worker.

Every attempt has a 30-second wall limit after worker preparation. Empty
attempts and timeouts establish no exclusion. Earlier searches are read-only.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

import overnight_v5 as ov
import pruning288_geometry as G
import search288 as prior
import target288
from lattice288 import valid


ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'scratch' / 'sweep288'
JOURNAL = ROOT / 'sweep288_journal.jsonl'
TOTAL, SECONDS, WIDTH = 2736, 30, .1
QUESTIONS = dict(calibration=(240, 10), search=(288, 10))
SOURCES = ('sweep288.py', 'pruning288_geometry.py') + prior.SOURCES
CODE = hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in SOURCES)).hexdigest()
INPUT_PATHS = ('search288_journal.jsonl', 'scratch/search288/calibration.json',
               'scratch/search288/search.json', '.lattice288_prepared.json',
               'pruning288_journal.jsonl')
INPUT = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUT_PATHS}


def header():
    return dict(event='header', version=1, n=288, order=10, control_n=240,
                control_order=10, total=TOTAL, control_total=1, seconds=SECONDS,
                width=WIDTH, code=CODE, input=INPUT, libraries=prior.LIBRARIES)


def metadata(phase, attempt):
    case = dict(calibration=2, search=attempt)[phase]
    return dict(case=case, seed_attempt=case, seed=prior.G.SEED+case, width=WIDTH)


def completed(rows, phase):
    return {r['attempt'] for r in rows if r['event'] == 'attempt_end' and r['phase'] == phase}


def witnessed(rows, phase):
    return any(r['event'] == 'attempt_end' and r['phase'] == phase and r['outcome'] == 'witness'
               for r in rows)


def check_answer(phase, attempt, answer):
    assert all(answer[k] == v for k, v in metadata(phase, attempt).items())
    assert answer['outcome'] in ('empty', 'timeout', 'witness')
    assert answer['elapsed'] >= 0
    if answer['outcome'] == 'timeout':
        assert all(answer[k] is None for k in ('nodes', 'enumeration_seconds', 'basis_hash', 'geometry_hash'))
    else:
        assert type(answer['nodes']) is int and answer['nodes'] >= 0
        assert 0 <= answer['enumeration_seconds'] <= answer['elapsed']
        assert all(len(answer[k]) == 64 and all(c in '0123456789abcdef' for c in answer[k])
                   for k in ('basis_hash', 'geometry_hash'))
    if answer['outcome'] == 'witness':
        n, order = QUESTIONS[phase]
        sequence = answer['sequence']
        assert all(type(a) is int and a in (-1, 1) for a in sequence)
        assert len(sequence) == n and sequence == sequence[::-1] and valid(sequence, order)


def read_journal():
    """Replay every transition once before resuming, checking exact witnesses."""
    data = JOURNAL.read_bytes()
    assert data.endswith(b'\n')
    rows = [json.loads(line) for line in data.splitlines()]
    assert all(rows[0][k] == v for k, v in header().items())
    assert all(a['time'] <= b['time'] for a, b in zip(rows, rows[1:]))
    done = dict(calibration=set(), search=set())
    state = dict(pid=None, phase='preparation', active=None, finish=None,
                 calibration=False, search=False)
    limits = dict(calibration=1, search=TOTAL)

    def session(row):
        assert state['finish'] in (None, 'failed')
        state.update(pid=row['pid'], phase='preparation', active=None, finish=None)

    def phase(row):
        p = row['phase']
        assert p in ('preparation', 'calibration', 'search') and state['active'] is None
        assert p != 'search' or state['calibration']
        state['phase'] = p

    def start(row):
        p, i = row['phase'], row['attempt']
        assert p == state['phase'] and p in limits and state['active'] is None
        assert type(i) is int and 0 <= i < limits[p] and i not in done[p]
        assert all(row[k] == v for k, v in metadata(p, i).items())
        state['active'] = (p, i)

    def end(row):
        p, i = row['phase'], row['attempt']
        assert state['active'] == (p, i)
        check_answer(p, i, row)
        state[p] |= row['outcome'] == 'witness'
        done[p].add(i)
        state['active'] = None

    def finish(row):
        outcome = row['outcome']
        assert outcome in ('witness', 'budget', 'control_failed', 'failed')
        assert outcome != 'witness' or state['search']
        assert outcome != 'budget' or (state['calibration'] and len(done['search']) == TOTAL)
        assert outcome != 'control_failed' or (not state['calibration'] and len(done['calibration']) == 1)
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


def ready_message():
    return dict(event='ready', code=CODE, input=INPUT)


class Worker:
    """One JSON-lines child; only a timed-out attempt permits replacement."""
    def __init__(self, command=(sys.executable, '-B', __file__, '--worker')):
        self.command = command
        self.process = None
        self.selector = None
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

    def ready(self):
        if self.process is None:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            bufsize=0)
            self.selector = selectors.DefaultSelector()
            self.selector.register(self.process.stdout, selectors.EVENT_READ, 'stdout')
            self.selector.register(self.process.stderr, selectors.EVENT_READ, 'stderr')
            assert self.receive(time.monotonic()+SECONDS) == ready_message()
        assert self.process.poll() is None

    def execute(self, phase, attempt):
        assert self.process is not None and self.process.poll() is None
        started = time.monotonic()
        job = dict(phase=phase, attempt=attempt)
        self.process.stdin.write((json.dumps(job)+'\n').encode())
        self.process.stdin.flush()
        try:
            result = self.receive(started+SECONDS)
        except TimeoutError:
            self.close()
            return dict(metadata(phase, attempt), outcome='timeout',
                        elapsed=time.monotonic()-started, nodes=None,
                        enumeration_seconds=None, basis_hash=None, geometry_hash=None)
        assert result['code'] == CODE and result['input'] == INPUT
        assert (result['phase'], result['attempt']) == (phase, attempt)
        answer = result['answer']
        assert answer['outcome'] != 'timeout'
        answer['elapsed'] = time.monotonic()-started
        check_answer(phase, attempt, answer)
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
        self.process = None
        self.selector = None
        self.buffer = b''


def load_cases():
    """Read prior checked preparations without rewriting or duplicating them."""
    calibration = json.loads((ROOT/'scratch/search288/calibration.json').read_text())
    assert calibration['code'] == prior.CODE and calibration['input'] == prior.INPUT
    assert len(calibration['cases']) == 6
    targets = target288.target_cases()
    assert len(targets) == TOTAL
    return dict(calibration=calibration['cases'], search=targets)


def references():
    rows = [json.loads(line) for line in (ROOT/'pruning288_journal.jsonl').read_text().splitlines()]
    assert rows[-1]['event'] == 'finish' and rows[-1]['outcome'] == 'budget'
    kept = [r for r in rows if r['event'] == 'attempt_end' and r['phase'] == 'search' and r['width'] == WIDTH]
    assert len(kept) == 7 and {r['case'] for r in kept} == set(range(7))
    assert all(r['outcome'] == 'empty' for r in kept)
    return {('search', r['case']): {k: r[k] for k in ('outcome', 'nodes', 'basis_hash', 'geometry_hash')}
            for r in kept}


def worker():
    cases, reference = load_cases(), references()
    print(json.dumps(ready_message()), flush=True)
    for line in sys.stdin:
        job = json.loads(line)
        assert set(job) == {'phase', 'attempt'}
        phase, attempt = job['phase'], job['attempt']
        assert phase in QUESTIONS and type(attempt) is int
        assert 0 <= attempt < dict(calibration=1, search=TOTAL)[phase]
        fields = metadata(phase, attempt)
        model = cases[phase][fields['case']]
        assert (model['n'], model['order']) == QUESTIONS[phase]
        frozen = G.freeze(model, fields['seed_attempt'])
        answer = G.enumerate_frozen(frozen, WIDTH)
        answer.pop('curve')
        answer['case'] = fields['case']
        assert all(answer[k] == v for k, v in fields.items())
        if (phase, fields['case']) in reference:
            assert all(answer[k] == v for k, v in reference[phase, fields['case']].items())
        print(json.dumps(dict(code=CODE, input=INPUT, **job, answer=answer)), flush=True)


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
    control = witnessed(rows, 'calibration')
    child = Worker()
    try:
        if witnessed(rows, 'search'):
            record('finish', outcome='witness')
            return
        for phase, limit in (('calibration', 1), ('search', TOTAL)):
            if phase == 'search' and not control:
                record('finish', outcome='control_failed')
                return
            record('phase', phase=phase)
            for attempt in sorted(set(range(limit))-done[phase]):
                assert shutil.disk_usage(ROOT).free >= 100 << 30
                child.ready()
                record('attempt_start', phase=phase, attempt=attempt, **metadata(phase, attempt))
                answer = child.execute(phase, attempt)
                check_answer(phase, attempt, answer)
                record('attempt_end', phase=phase, attempt=attempt, **answer)
                done[phase].add(attempt)
                control |= phase == 'calibration' and answer['outcome'] == 'witness'
                if phase == 'search' and answer['outcome'] == 'witness':
                    record('finish', outcome='witness')
                    return
            record('phase', phase='preparation')
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
    previous = prior.read_journal()
    assert previous[-1]['event'] == 'finish' and prior.witnessed(previous, 'calibration')
    with lock_run():
        run()


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--worker'])
    {'': main, '--worker': worker}[''.join(sys.argv[1:])]()
