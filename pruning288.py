#!/usr/bin/env python3
"""Paired baseline/wider pruning on one control and seven frozen 288 cases.

Both 240:10 controls must be recovered before target work. Sixteen attempts
have 30-second wall limits; freezing geometry is separate. Empty pruned runs
and timeouts establish no exclusion. The completed earlier pilot is read-only.
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

import progress
import pruning288_geometry as G
import search288 as S
from lattice288 import atomic_json, valid


ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'scratch' / 'pruning288'
JOURNAL = ROOT / 'pruning288_journal.jsonl'
WIDTHS, SECONDS = (0, .1), 30
INDICES = dict(calibration=[2], search=list(range(7)))
SCHEDULE = {phase: [(case, width) for case in cases for width in WIDTHS]
            for phase, cases in INDICES.items()}
SOURCES = ('pruning288.py', 'pruning288_geometry.py', 'progress.py') + S.SOURCES
CODE = hashlib.sha256(b''.join((ROOT / name).read_bytes() for name in SOURCES)).hexdigest()
INPUT_PATHS = ('search288_journal.jsonl', 'scratch/search288/calibration.json',
               'scratch/search288/search.json', '.lattice288_prepared.json')
INPUT = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUT_PATHS}


def completed(rows, phase):
    return {r['attempt'] for r in rows if r['event'] == 'attempt_end' and r['phase'] == phase}


def witnesses(rows, phase):
    return sum(r['event'] == 'attempt_end' and r['phase'] == phase and r['outcome'] == 'witness'
               for r in rows)


def header():
    return dict(event='header', version=1, n=288, order=10, control_n=240, control_order=10,
                total=14, control_total=2, seconds=SECONDS, widths=list(WIDTHS),
                cases=INDICES['search'], control_case=2, control_seed=S.G.SEED+2,
                code=CODE, input=INPUT, libraries=S.LIBRARIES)


def metadata(frozen, width):
    return dict(seed_attempt=frozen['attempt'], seed=frozen['seed'], width=width,
                basis_hash=frozen['basis_hash'], geometry_hash=frozen['geometry_hash'],
                curve=G.curve(frozen, width))


def read_journal():
    """Reuse the progress protocol, then check paired identities and exact witnesses."""
    data = JOURNAL.read_bytes()
    assert data.endswith(b'\n')
    rows = [json.loads(line) for line in data.splitlines()]
    assert all(rows[0][k] == v for k, v in header().items())
    progress.survey_pruning288(JOURNAL, [])
    geometry, curves, starts = {}, {}, {}
    for row in rows:
        if row['event'] in ('attempt_start', 'attempt_end'):
            p, i = row['phase'], row['attempt']
            case, width = SCHEDULE[p][i]
            assert (row['case'], row['width'], row['seed_attempt'], row['seed']) == (case, width, case, S.G.SEED+case)
            identity = (row['basis_hash'], row['geometry_hash'], row['seed'])
            assert geometry.setdefault((p, case), identity) == identity
            assert row['curve'] and all(0 <= x <= 1 for x in row['curve'])
            assert curves.setdefault((p, case, width), row['curve']) == row['curve']
            assert width == 0 or row['curve'] == [.1 + .9*x for x in curves[p, case, 0]]
            fields = {k: row[k] for k in ('case', 'seed_attempt', 'seed', 'width', 'basis_hash', 'geometry_hash', 'curve')}
            assert starts.setdefault((p, i), fields) == fields
        if row['event'] == 'attempt_end' and row['outcome'] == 'witness':
            n, order = S.QUESTIONS[row['phase']]
            sequence = row['sequence']
            assert len(sequence) == n and sequence == sequence[::-1] and valid(sequence, order)
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
    assert not JOURNAL.exists()
    common = dict(time=time.time(), pid=os.getpid())
    rows = [dict(header(), **common), dict(common, event='session'),
            dict(common, event='phase', phase='preparation')]
    text = ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows)
    temporary = WORK / 'initial.jsonl'
    with temporary.open('w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, JOURNAL)
    print(text, end='', flush=True)


def prepare(phase):
    path = WORK / (phase + '.json')
    if path.exists():
        data = json.loads(path.read_text())
        assert data['code'] == CODE and data['input'] == INPUT
        return data['frozen']
    original = S.prepare(phase)
    frozen = [G.freeze(original[i], i) for i in INDICES[phase]]
    assert [f['attempt'] for f in frozen] == INDICES[phase]
    atomic_json(path, dict(code=CODE, input=INPUT, frozen=frozen))
    return frozen


def bounded(frozen, width):
    atomic_json(WORK / 'job.json', dict(code=CODE, input=INPUT, frozen=frozen, width=width))
    start = time.monotonic()
    try:
        child = subprocess.run([sys.executable, '-B', __file__, '--worker'],
                               capture_output=True, text=True, timeout=SECONDS)
    except subprocess.TimeoutExpired:
        return dict(outcome='timeout', elapsed=time.monotonic()-start,
                    enumeration_seconds=None, nodes=None)
    assert child.returncode == 0 and not child.stderr, (child.returncode, child.stdout, child.stderr)
    result = json.loads(child.stdout)
    expected = metadata(frozen, width)
    assert all(result.pop(k) == v for k, v in expected.items())
    result['elapsed'] = time.monotonic()-start
    return result


def worker():
    job = json.loads((WORK / 'job.json').read_text())
    assert job['code'] == CODE and job['input'] == INPUT
    resource.setrlimit(resource.RLIMIT_CPU, (SECONDS+5, SECONDS+5))
    print(json.dumps(G.enumerate_frozen(job['frozen'], job['width'])), flush=True)


def run():
    WORK.mkdir(parents=True, exist_ok=True)
    if JOURNAL.exists():
        rows = read_journal()
        if rows[-1]['event'] == 'finish' and rows[-1]['outcome'] != 'failed':
            return
        record('session')
        record('phase', phase='preparation')
    else:
        initialize()
    rows = read_journal()
    try:
        if witnesses(rows, 'search'):
            record('finish', outcome='witness')
            return
        for phase in ('calibration', 'search'):
            if phase == 'search' and witnesses(rows, 'calibration') != 2:
                record('finish', outcome='control_failed')
                return
            frozen = dict(zip(INDICES[phase], prepare(phase), strict=True))
            record('phase', phase=phase)
            for attempt in sorted(set(range(len(SCHEDULE[phase]))) - completed(rows, phase)):
                case, width = SCHEDULE[phase][attempt]
                fields = dict(case=case, **metadata(frozen[case], width))
                record('attempt_start', phase=phase, attempt=attempt, **fields)
                result = bounded(frozen[case], width)
                record('attempt_end', phase=phase, attempt=attempt, **fields, **result)
                rows = read_journal()
                if phase == 'search' and result['outcome'] == 'witness':
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
    with (WORK/'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    assert shutil.disk_usage(ROOT).free >= 100 << 30
    previous = S.read_journal()
    assert previous[-1]['event'] == 'finish'
    assert any(r['event'] == 'attempt_end' and r['phase'] == 'calibration' and
               r['attempt'] == 2 and r['outcome'] == 'witness' for r in previous)
    with lock_run():
        run()


if __name__ == '__main__':
    assert sys.argv[1:] in ([], ['--worker'])
    {'': main, '--worker': worker}[''.join(sys.argv[1:])]()
