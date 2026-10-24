#!/usr/bin/env python3
"""Claude's fanout (named 2026-10-23, dreeves: "ok"): finishes a stopped focus.py run with WORKERS processes, and
splices the proof back into the run as focus.py's own chunks, so that focus.py, unchanged, replays and checks all of it.
Run from this directory, with focus.py's run of N stopped (its lock is taken here, so fanout refuses a live run):

    PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B fanout.py N

Vocabulary (with focus.py's):
  root      a box of the run's open frontier when fanout first starts, (case, path) as focus.State holds it: path, the
            positions fixed and their values.  roots.json keeps them, so a restart works on the same boxes.
  job       a box to prove: a root, or a box another job left open.  Its worker runs it depth first, as focus.search
            would (focus.step, each token checked as made by certbb.Check on the job's box), for at most BUDGET LP
            solves; the result is its tokens and the boxes still open, in the order focus.State would pop them, which
            become jobs.  A job's file under jobs/ is the durable record that it is done; a restart reruns no job
            with a file.  Jobs run shallowest first: the biggest boxes are split soonest.
  splice    the last step: focus.replay of the run (whose open boxes must still be the roots), then every job's tokens,
            fed through focus.State in the order a sequential search would have made them (a job's tokens, then its
            open boxes' jobs, last first), committed with focus.commit.  Then focus.search itself, unchanged, replays
            the whole run from disk, finds it excluded and writes its finish to focus.py's journal.
  witness   a job's W token: an exact 0/1 solution of its case's equations, so an example of the order.  It ends the
            fanout at once; it needs no splice, being its own certificate.
"""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import fcntl
import functools
import gzip
import hashlib
import heapq
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time

import certbb
import focus

WORKERS = 5                            # processes proving jobs (principle 4's slots: 480's run takes the sixth)
BUDGET = 20000                         # LP solves a job may take before it hands back what it left open: ~10 min at 672
CHUNK = 20000                          # records per focus.py chunk the splice commits


def key(case, path):
    """A box as fanout keeps it: (case, path), path a tuple of (position, value) pairs."""
    return case, tuple(tuple(p) for p in path)


def jid(box):
    """A job's id: the sha1 of its box."""
    return hashlib.sha1(json.dumps([box[0], [list(p) for p in box[1]]]).encode()).hexdigest()


def box(N, path):
    """The 0/1 box of a path: its lower and upper ends."""
    lo, hi = [0] * N, [1] * N
    for p, t in path:
        lo[p] = hi[p] = t
    return lo, hi


def write_atomic(path, data):
    temporary = path.with_suffix('.tmp')
    with open(temporary, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as zipped:
            zipped.write(json.dumps(data, separators=(',', ':')).encode())
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(temporary, path)


def read(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def taken(run_dir, work_dir, code):
    """roots.json: the run's last chunk's frontier, LP solves and case when fanout first starts (written then)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / 'roots.json.gz'
    if not path.exists():
        chunks = sorted(Path(run_dir).glob('chunk-*.json.gz'))
        last = read(chunks[-1])
        # TODO: error copy; says the run's chunks were made by other code than fanout's focus.py
        assert last['code'] == code, 'Claude: "the run belongs to other code"'
        # TODO: error copy; says the run is already decided, so there is nothing to finish
        assert last['checkpoint']['outcome'] in (None, 'budget'), 'Claude: "the run is already decided"'
        point = last['checkpoint']
        write_atomic(path, dict(code=code, chunks=len(chunks), lp=point['lp'], case=point['case'],
                                frontier=point['frontier']))
    data = read(path)
    assert data['code'] == code, data['code']
    return data


def roots(run_dir, work_dir, code):
    return [key(*b) for b in taken(run_dir, work_dir, code)['frontier']]


def save(work_dir, job, root, result):
    """A done job's file: its box, its root's index, its tokens, its open boxes, its seconds and any witness."""
    write_atomic(work_dir / 'jobs' / f'{jid(job)}.json.gz',
                 dict(version=1, case=job[0], path=[list(p) for p in job[1]], root=root, **result))


def brief(entry):
    """What the driver keeps of a done job: its open boxes, witness and root, not its tokens (tens of megabytes at
    672; the splice reads them back from the job's file)."""
    return {k: entry[k] for k in ('open', 'witness', 'root')}


def note(journal, event, **fields):
    with open(journal, 'a', encoding='utf-8') as f:
        f.write(json.dumps(dict(event=event, time=time.time(), pid=os.getpid(), **fields), separators=(',', ':')) + '\n')
        f.flush()
        os.fsync(f.fileno())


# ---------- the workers ----------

WORK = None                            # a worker's (prepared equations and cases, budget), set by init


def init(prepared, budget):
    global WORK
    WORK = (prepared, budget)


@functools.lru_cache(maxsize=None)
def lp_for(case):
    """The worker's LP for a case, made once."""
    (equations, cases), _ = WORK
    lp = certbb.Lp(equations, tuple(M for M, _ in cases[case]))
    lp.set_counts(cases[case])
    return lp


def work(job):
    """Runs the job (see the vocabulary): its tokens, its open boxes' paths, its seconds and any witness."""
    (equations, cases), budget = WORK
    case, path = job
    choice = cases[case]
    rows = certbb.node_rows(equations, choice)
    check = certbb.Check(equations, tuple((M, (v,)) for M, v in choice), *box(equations.N, path))
    stack, tokens, start = [path], [], time.monotonic()
    while stack and len(tokens) < budget:
        p = stack.pop()
        lo, hi = box(equations.N, p)
        token = focus.step(lp_for(case), equations, choice, lo, hi)
        tokens.append(token)
        if token[0] == 'W':                # an exact solution, checked as focus.State checks one: the job's end
            x = token[1]
            assert all(type(t) is int and l <= t <= u for t, l, u in zip(x, lo, hi)) and len(x) == equations.N
            assert certbb.point_certificate(rows, x) is None
            return dict(tokens=tokens, open=[], seconds=time.monotonic() - start, witness=x)
        check.feed(token)
        stack += [p + ((token[1], 1),), p + ((token[1], 0),)] if token[0] == 'B' else []
    return dict(tokens=tokens, open=stack, seconds=time.monotonic() - start, witness=None)


# ---------- the driver ----------

def farm(prepared, all_roots, done, work_dir, journal):
    """Runs every job not done, WORKERS at once, shallowest first; the witness found (0/1 list), else None."""
    heap, order = [], itertools.count()
    def reach(job, root):                  # the jobs not done at or below job
        todo = [job]
        while todo:
            b = todo.pop()
            entry = done.get(jid(b))
            if entry is None: heapq.heappush(heap, (len(b[1]), next(order), b, root))
            else: todo += [key(b[0], p) for p in entry['open']]
    for root, job in enumerate(all_roots): reach(job, root)
    found = [e['witness'] for e in done.values() if e['witness'] is not None]
    if found: return found[0]
    with ProcessPoolExecutor(WORKERS, mp_context=multiprocessing.get_context('spawn'), initializer=init,
                             initargs=(prepared, BUDGET)) as pool:
        running = {}
        while heap or running:
            while heap and len(running) < WORKERS:
                _, _, job, root = heapq.heappop(heap)
                running[pool.submit(work, job)] = (job, root)
                note(journal, 'job_start', job=jid(job), case=job[0], depth=len(job[1]), root=root)
            ready, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in ready:
                job, root = running.pop(future)
                result = future.result()
                save(work_dir, job, root, result)
                done[jid(job)] = brief(dict(result, root=root))
                note(journal, 'job_end', job=jid(job), case=job[0], root=root, lps=len(result['tokens']),
                     seconds=result['seconds'], open=len(result['open']))
                if result['witness'] is not None:
                    pool.shutdown(cancel_futures=True)
                    return result['witness']
                for p in result['open']: heapq.heappush(heap, (len(p), next(order), key(job[0], p), root))
    return None


def splice(run_dir, work_dir, prepared, code, all_roots, done):
    """The splice (see the vocabulary): every job's tokens, read from its file, fed through focus.State and committed
    as chunks."""
    state = focus.replay(run_dir, *prepared, code)
    # TODO: error copy; says the run's open boxes are no longer the ones fanout set out to prove
    assert [key(*b) for b in state.frontier] == all_roots, 'Claude: "the run moved since fanout took its roots"'
    state.outcome, todo, records = None, list(all_roots), []
    while todo:
        job = todo.pop()
        assert key(*state.frontier[-1]) == job, (state.frontier[-1], job)
        entry = done[jid(job)]
        for token in read(work_dir / 'jobs' / f'{jid(job)}.json.gz')['tokens']:
            record = dict(case=job[0], token=token)
            state.feed(record)
            records.append(record)
        todo += [key(job[0], p) for p in entry['open']]
        if len(records) >= CHUNK:
            focus.commit(run_dir, state, records, code)
            records = []
    assert not state.frontier and state.witness is None
    state.outcome = 'excluded'
    focus.commit(run_dir, state, records, code)


def run(run_dir, focus_journal, work_dir, journal, n, m):
    """Finishes focus.py's stopped run of (n, m) in run_dir: excluded or witness."""
    run_dir, work_dir, journal = Path(run_dir), Path(work_dir), Path(journal)
    prepared, code = focus.prepare(n, m), focus.fingerprint()
    (work_dir / 'jobs').mkdir(parents=True, exist_ok=True)
    with open(run_dir / 'run.lock', 'a') as theirs, open(work_dir / 'lock', 'a') as ours:
        fcntl.flock(theirs, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(ours, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = taken(run_dir, work_dir, code)
        all_roots = [key(*b) for b in start['frontier']]
        head = dict(version=1, n=n, order=m, workers=WORKERS, budget=BUDGET, roots=len(all_roots),
                    root_cases=[c for c, _ in all_roots], root_depths=[len(path) for _, path in all_roots],
                    prefix_lp=start['lp'], prefix_case=start['case'], code=code)
        if not journal.exists(): note(journal, 'header', **head)
        assert {k: json.loads(journal.read_text().splitlines()[0])[k] for k in ('n', 'order', 'code')} == \
               {k: head[k] for k in ('n', 'order', 'code')}
        note(journal, 'session')
        done = {f.name.split('.')[0]: brief(read(f)) for f in (work_dir / 'jobs').glob('*.json.gz')}
        witness = farm(prepared, all_roots, done, work_dir, journal)
        if witness is None: splice(run_dir, work_dir, prepared, code, all_roots, done)
    # focus.py itself, unchanged and with the run's lock free again, replays the whole run from disk
    outcome = 'witness' if witness is not None else focus.search(run_dir, focus_journal, n, m, 1, 1)
    # TODO: error copy; says focus.py's replay of the spliced run did not find it decided
    assert outcome in ('excluded', 'witness'), f'Claude: "focus.py replays the spliced run as {outcome}"'
    note(journal, 'finish', outcome=outcome, witness=witness)
    return outcome


def main():
    # TODO: error copy; says how to run fanout: with the length of a stopped focus.py run, 480 or 672
    assert len(sys.argv) == 2 and sys.argv[1] in ('480', '672'), 'Claude: "usage: python3 -B fanout.py 480|672"'
    n = int(sys.argv[1])
    m = {480: 14, 672: 13}[n]
    outcome = run(Path(f'scratch/focus{n}/run'), Path(f'focus_{n}_journal.jsonl'), Path(f'scratch/fanout{n}'),
                  Path(f'fanout_{n}_journal.jsonl'), n, m)
    print(json.dumps(dict(n=n, order=m, outcome=outcome)), flush=True)


if __name__ == '__main__':
    main()
