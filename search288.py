#!/usr/bin/env python3
"""A calibrated, resumable pilot for 288:10 with randomized lattice bases.

Twelve 30-second attempts must independently recover 240:10 before sixteen
288:10 attempts can run. Preparation is outside each attempt's wall limit.
Empty attempts and timeouts prove no exclusion. The historical lattice288
journal is read-only; this experiment has its own journal and work directory.
"""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

import fpylll
import search288_geometry as G
import target288
from lattice288 import atomic_json, valid


ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'scratch' / 'search288'
JOURNAL = ROOT / 'search288_journal.jsonl'
VERSION, CONTROL_TOTAL, TOTAL, SECONDS = 1, 12, 16, 30
SOURCES = ('search288.py', 'search288_geometry.py', 'target288.py', 'join720.py',
           'lattice288.py', 'mstar.py', 'overnight_v5.py', 'certbb.py')
CODE = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in SOURCES)).hexdigest()
INPUT = hashlib.sha256(target288.PREPARED.read_bytes()).hexdigest()
LIBRARIES = dict(fpylll=fpylll.__version__, sympy=G.sp.__version__)
QUESTIONS = dict(calibration=(240, 10), search=(288, 10))


def completed(events, phase):
    return {e['attempt'] for e in events
            if e['event'] == 'attempt_end' and e['phase'] == phase}


def witnessed(events, phase):
    return any(e['event'] == 'attempt_end' and e['phase'] == phase
               and e['outcome'] == 'witness' for e in events)


def read_journal():
    """Reject changed inputs, impossible transitions, and unverified witnesses."""
    data = JOURNAL.read_bytes()
    assert data.endswith(b'\n')
    rows = [json.loads(line) for line in data.splitlines()]
    h = rows[0]
    expected = dict(event='header', version=VERSION, n=288, order=10,
                    control_n=240, control_order=10, total=TOTAL,
                    control_total=CONTROL_TOTAL, seconds=SECONDS,
                    code=CODE, input=INPUT, libraries=LIBRARIES)
    assert all(h[k] == v for k, v in expected.items())
    assert all(a['time'] <= b['time'] for a, b in zip(rows, rows[1:]))
    done = dict(calibration=set(), search=set())
    state = dict(pid=None, phase='preparation', active=None, ended=False,
                 calibration=False, search=False)
    limits = dict(calibration=CONTROL_TOTAL, search=TOTAL)

    def session(r):
        state.update(pid=r['pid'], phase='preparation', active=None, ended=False)

    def phase(r):
        assert r['phase'] in ('preparation', 'calibration', 'search')
        assert state['active'] is None
        assert r['phase'] != 'search' or state['calibration']
        state['phase'] = r['phase']

    def start(r):
        p, i = r['phase'], r['attempt']
        assert p == state['phase'] and p in limits and state['active'] is None
        assert type(i) is int and 0 <= i < limits[p] and i not in done[p]
        state['active'] = (p, i)

    def end(r):
        p, i = r['phase'], r['attempt']
        assert state['active'] == (p, i)
        assert r['outcome'] in ('empty', 'timeout', 'witness') and r['elapsed'] >= 0
        if r['outcome'] == 'witness':
            n, order = QUESTIONS[p]
            seq = r['sequence']
            assert len(seq) == n and seq == seq[::-1] and valid(seq, order)
            state[p] = True
        done[p].add(i)
        state['active'] = None

    def finish(r):
        outcome = r['outcome']
        assert outcome in ('witness', 'budget', 'control_failed', 'failed')
        assert outcome != 'witness' or state['search']
        assert outcome != 'budget' or (state['calibration'] and len(done['search']) == TOTAL)
        assert outcome != 'control_failed' or (not state['calibration'] and
                                              len(done['calibration']) == CONTROL_TOTAL)
        state['ended'] = True

    handlers = dict(session=session, phase=phase, attempt_start=start,
                    attempt_end=end, finish=finish)
    for r in rows[1:]:
        assert r['event'] in handlers and type(r['pid']) is int
        assert r['event'] == 'session' or (r['pid'] == state['pid'] and not state['ended'])
        handlers[r['event']](r)
    return rows


def record(event, **fields):
    row = dict(event=event, time=time.time(), pid=os.getpid(), **fields)
    text = json.dumps(row, separators=(',', ':'))
    with JOURNAL.open('a') as stream:
        stream.write(text + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(text, flush=True)


def initialize():
    WORK.mkdir(parents=True, exist_ok=True)
    assert not JOURNAL.exists()
    common = dict(time=time.time(), pid=os.getpid())
    rows = [dict(common, event='header', version=VERSION, n=288, order=10,
                 control_n=240, control_order=10, total=TOTAL,
                 control_total=CONTROL_TOTAL, seconds=SECONDS,
                 code=CODE, input=INPUT, libraries=LIBRARIES),
            dict(common, event='session'),
            dict(common, event='phase', phase='preparation')]
    text = ''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in rows)
    temporary = WORK / 'initial.jsonl'
    with temporary.open('w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, JOURNAL)
    print(text, end='', flush=True)


def prepare(phase):
    """Cache exact preparation under this complete source fingerprint."""
    path = WORK / (phase + '.json')
    if path.exists():
        data = json.loads(path.read_text())
        assert data['code'] == CODE and data['input'] == INPUT
        return data['cases']
    factories = dict(calibration=lambda: G.prepare_models(G.calibration_models()),
                     search=lambda: target288.target_cases()[:TOTAL])
    cases = factories[phase]()
    assert cases and all((c['n'], c['order']) == QUESTIONS[phase] for c in cases)
    atomic_json(path, dict(code=CODE, input=INPUT, cases=cases))
    return cases


def bounded(prepared, attempt):
    atomic_json(WORK / 'job.json', dict(code=CODE, input=INPUT, prepared=prepared, attempt=attempt))
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, '-B', __file__, '--worker'],
                              capture_output=True, text=True, timeout=SECONDS)
    except subprocess.TimeoutExpired:
        return dict(outcome='timeout', elapsed=time.monotonic() - start)
    assert proc.returncode == 0 and not proc.stderr, (proc.returncode, proc.stdout, proc.stderr)
    answer = json.loads(proc.stdout)
    answer['elapsed'] = time.monotonic() - start
    return answer


def worker():
    job = json.loads((WORK / 'job.json').read_text())
    assert job['code'] == CODE and job['input'] == INPUT
    resource.setrlimit(resource.RLIMIT_CPU, (SECONDS + 5, SECONDS + 5))
    case = job['attempt'] % len(job['prepared'])
    answer = G.enumerate_job(job['prepared'][case], job['attempt'])
    print(json.dumps(dict(answer, case=case)), flush=True)


def run():
    WORK.mkdir(parents=True, exist_ok=True)
    if JOURNAL.exists():
        events = read_journal()
        if events[-1]['event'] == 'finish' and events[-1]['outcome'] != 'failed':
            return
        record('session')
        record('phase', phase='preparation')
    else:
        initialize()
    events = read_journal()
    try:
        if witnessed(events, 'search'):
            record('finish', outcome='witness')
            return
        for phase, limit in (('calibration', CONTROL_TOTAL), ('search', TOTAL)):
            if phase == 'calibration' and witnessed(events, phase):
                continue
            if phase == 'search' and not witnessed(events, 'calibration'):
                record('finish', outcome='control_failed')
                return
            cases = prepare(phase)
            record('phase', phase=phase)
            for attempt in sorted(set(range(limit)) - completed(events, phase)):
                record('attempt_start', phase=phase, attempt=attempt)
                result = bounded(cases, attempt)
                record('attempt_end', phase=phase, attempt=attempt, **result)
                events = read_journal()
                if result['outcome'] == 'witness':
                    break
            record('phase', phase='preparation')
        outcome = 'witness' if witnessed(events, 'search') else 'budget'
        record('finish', outcome=outcome)
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
    assert shutil.disk_usage(ROOT).free >= 100 << 30
    with lock_run():
        run()


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--worker'])
    {'': main, '--worker': worker}[''.join(sys.argv[1:])]()
