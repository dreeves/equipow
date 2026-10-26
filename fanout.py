#!/usr/bin/env python3
"""Claude's fanout (named 2026-10-23, dreeves: "ok"): finishes a stopped focus.py run with WORKERS processes, and
splices the proof back into the run as focus.py's own chunks, so that focus.py, unchanged, replays and checks all of it.
Run from this directory, with focus.py's run of N stopped (its lock is taken here, so fanout refuses a live run):

    PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B fanout.py N

Vocabulary (with focus.py's):
  root      a box of the run's open frontier when fanout first starts, (case, path) as focus.State holds it: path, the
            positions fixed and their values.  roots.json keeps them, so a restart works on the same boxes.
  job       a box to prove: a root, or a box another job left open.  Its worker runs it depth first, as focus.search
            would (focus.step, each token checked as made by certbb.Check on the job's box), for BUDGET LP solves, and
            then on while its next open box lies more than DEEP levels below its own, up to HARD budgets in all: so it
            hands back at most DEEP boxes, the shallow ones, unless it reached HARD budgets (2026-10-23: handing back
            the whole depth-first path, 109 jobs at 672 had left 6,952 open, most of them tiny).  The result is its
            tokens and the boxes still open, in the order focus.State would pop them, which become jobs.  A job's file under jobs/ is the durable record that it is done; a restart reruns no job
            with a file.  Jobs run shallowest first: the biggest boxes are split soonest.
  splice    the last step: focus.replay of the run (whose open boxes must still be the roots), then every job's tokens,
            fed through focus.State in the order a sequential search would have made them (a job's tokens, then its
            open boxes' jobs, last first), committed with focus.commit.  Then focus.search itself, unchanged, replays
            the whole run from disk, finds it excluded and writes its finish to focus.py's journal.
  witness   a job's W token: an exact 0/1 solution of its case's equations, so an example of the order.  It ends the
            fanout at once; it needs no splice, being its own certificate.
  probe     of a case with LP work to do (a job not done), made by the driver at each session's start, before any job,
            and journaled for the progress section's ETA (2026-10-25: random dives put 672:13's tree at >= 1e13 LP
            solves while the page said 17 h to go): PROBE_PATHS random paths from the case's root down to a leaf (Knuth
            1975), at each B token the child a fair coin picks, each node solved by focus.step from its parent's
            post-solve LP state, each path from the root's.  A job gives a box's first child that state, and its second
            the parent's basis, restored.  On certbb.Lp's quiet options, paths taking that state at every node matched
            whole trees grown the job's way node for node on 1,198 of 1,200 paths (four small trees,
            scratch/ideas-20261025/verify/v-floors).  On focus.case_lp's option (2026-10-25) that need not hold: HiGHS
            then draws fresh cost perturbations at every solve from one random stream per LP, so a token can depend on
            every solve its LP made before (a job's, on its worker's earlier jobs too), and each path follows a tree of
            its own, grown the same way, not the run's.  At 432:12, 0 to 9 earlier solves gave the root's children 5
            distinct token pairs, against 1 on quiet options, and the probe means moved by sd 0.14 (B) and 0.25 (A)
            levels across HiGHS seeds 0 to 3, against se 0.23 to 0.25 (scratch/record-20261025/f432/review, history.py
            and repro.jsonl).  A path's leaf depth D, its B tokens, is the depth of the leaf holding a uniformly random
            point of the case's
            box, so the tree has E[2^(D+1)] - 1 nodes (on case_lp's option, in expectation over HiGHS's draws), one LP
            solve each, and by Jensen's inequality at least 2^(E[D]+1) - 1.
            Its record gives the paths, their depths' mean and standard error (se), least, and witnesses: the distinct
            exact solutions (W tokens) its paths ended at.  These do not end the fanout: the jobs' search, being
            complete, must find one too, if perhaps much later (ending it at a probe's would leave 16:4's eight-worker
            control, quals_fanout_eight, without a job).
  least     of a probe: floor(2^(mean - Z se + 1)) - 1, a lower bound, with one-sided 95% confidence, on its case's LP
            solves in all (its tree's under these warm starts, on case_lp's option in expectation over HiGHS's draws;
            the run's own tree was grown partly under focus.search's).
"""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import fcntl
import functools
import gzip
import hashlib
import heapq
import itertools
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import signal
import sys
import time

import certbb
import focus
import reflection

# The inline note describes the original allocation; eight workers now run with 480 paused, as approved.
WORKERS = 8                            # processes proving jobs (principle 4's slots: 480's run takes the sixth)
BUDGET = 20000                         # LP solves a job takes before it may hand back what it left open: ~2 min at 672
DEEP = 8                               # levels below a job's box that it finishes itself past its budget
HARD = 4                               # budgets a job may take in all
CHUNK = 20000                          # records per focus.py chunk the splice commits
PROBE_PATHS = 300                      # paths per probe: at 672, 43 levels deep, 13,221 LP solves in 26 CPU s, per case
Z = 1.645                              # the standard normal's 95th percentile: least's confidence, one-sided


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

WORK = None                            # a worker's (prepared equations and cases, budget, deep), set by init


def init(prepared, budget, deep):
    global WORK
    WORK = (prepared, budget, deep)


@functools.lru_cache(maxsize=None)
def lp_for(case):
    """The worker's LP for a case, made once."""
    (equations, cases), _, _ = WORK
    return focus.case_lp(equations, cases[case])


def work(job):
    """Runs the job (see the vocabulary): its tokens, its open boxes' paths, its seconds and any witness."""
    (equations, cases), budget, deep = WORK
    case, path = job
    choice = cases[case]
    rows = certbb.node_rows(equations, choice)
    check = certbb.Check(equations, tuple((M, (v,)) for M, v in choice), *box(equations.N, path))
    lp = lp_for(case)
    stack, tokens, start = [(path, None)], [], time.monotonic()
    while stack and len(tokens) < HARD * budget and (len(tokens) < budget or len(stack[-1][0]) > len(path) + deep):
        p, basis = stack.pop()
        lo, hi = box(equations.N, p)
        if basis is not None:
            assert lp.H.setBasis(basis) == certbb.highs.HighsStatus.kOk
        token = focus.step(lp, equations, choice, lo, hi)
        tokens.append(token)
        if token[0] == 'W':                # an exact solution, checked as focus.State checks one: the job's end
            x = token[1]
            assert all(type(t) is int and l <= t <= u for t, l, u in zip(x, lo, hi)) and len(x) == equations.N
            assert certbb.point_certificate(rows, x) is None
            return dict(tokens=tokens, open=[], seconds=time.monotonic() - start, witness=x)
        check.feed(token)
        stack += [(p + ((token[1], 1),), lp.H.getBasis()), (p + ((token[1], 0),), None)] if token[0] == 'B' else []
    return dict(tokens=tokens, open=[p for p, _ in stack], seconds=time.monotonic() - start, witness=None)


# ---------- the probes ----------

def least(mean, se):
    """A probe's least (see the vocabulary), from its paths' leaf depths' mean and standard error."""
    return math.floor(2 ** (mean - Z * se + 1)) - 1


def dive(lp, equations, choice, root, rng):
    """One path of a probe (see the vocabulary), from the case's root, whose post-solve basis root is: its leaf's path
    and token."""
    assert lp.H.setBasis(root) == certbb.highs.HighsStatus.kOk
    path = ()
    token = focus.step(lp, equations, choice, *box(equations.N, path))
    while token[0] == 'B':
        path += ((token[1], rng.randrange(2)),)
        token = focus.step(lp, equations, choice, *box(equations.N, path))
    return path, token


def probe(prepared, case, paths):
    """The probe of a case (see the vocabulary) on an LP of its own, its coin seeded by the case: the fields of its
    journal record.  Each witness is checked as a job checks one."""
    assert type(paths) is int and paths >= 2
    equations, cases = prepared
    choice = cases[case]
    lp = focus.case_lp(equations, choice)
    focus.step(lp, equations, choice, *box(equations.N, ()))       # the root's solve, from a fresh LP, as focus.py's
    rng, root = random.Random(case), lp.H.getBasis()
    leaves = [dive(lp, equations, choice, root, rng) for _ in range(paths)]
    depths = [len(path) for path, _ in leaves]
    witnesses = sorted({tuple(token[1]) for _, token in leaves if token[0] == 'W'})
    rows = certbb.node_rows(equations, choice)
    assert all(len(x) == equations.N and set(x) <= {0, 1} and certbb.point_certificate(rows, list(x)) is None
               for x in witnesses)
    mean = sum(depths) / paths
    se = math.sqrt(sum((d - mean) ** 2 for d in depths) / (paths - 1) / paths)
    return dict(paths=paths, mean=mean, se=se, least=least(mean, se), witnesses=[list(x) for x in witnesses])


# ---------- the driver ----------

def reflections(prepared, all_roots):
    """Untouched cases whose full proofs can be reflected from an earlier case.

    A partially searched target is retained. The original roots, including every
    target, remain the contract for the final exact replay.
    """
    equations, cases = prepared
    reversed_cases = tuple(reflection.choice(equations, choice) for choice in cases)
    pairs = [(target, source) for source in sorted({b[0] for b in all_roots})
             for target in range(source + 1, len(cases))
             if (target, ()) in all_roots and reversed_cases[source] == cases[target]]
    assert len(dict(pairs)) == len(pairs)
    assert not set(dict(pairs)) & set(dict(pairs).values())
    for _, source in pairs: reflection.mapping(equations, cases[source])
    return dict(pairs)


def farm(prepared, all_roots, done, work_dir, journal):
    """Journals a probe of each case with a job not done, then runs every job not done, WORKERS at once, shallowest
    first; the witness found (0/1 list), else None."""
    heap, order = [], itertools.count()
    def reach(job, root):                  # the jobs not done at or below job
        todo = [job]
        while todo:
            b = todo.pop()
            entry = done.get(jid(b))
            if entry is None: heapq.heappush(heap, (len(b[1]), next(order), b, root))
            else: todo += [key(b[0], p) for p in entry['open']]
    copies = reflections(prepared, all_roots)
    for root, job in enumerate(all_roots):
        if job[0] not in copies: reach(job, root)
    found = [e['witness'] for e in done.values() if e['witness'] is not None]
    if found: return found[0]
    for case in sorted({b[0] for _, _, b, _ in heap}):
        note(journal, 'probe', case=case, **probe(prepared, case, PROBE_PATHS))
    with ProcessPoolExecutor(WORKERS, mp_context=multiprocessing.get_context('spawn'), initializer=init,
                             initargs=(prepared, BUDGET, DEEP)) as pool:
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


def job_tokens(work_dir, done, jobs):
    """Saved job tokens in depth-first order, including each unfinished child's job."""
    todo = list(jobs)
    while todo:
        job = todo.pop()
        data = read(work_dir / 'jobs' / f'{jid(job)}.json.gz')
        assert key(data['case'], data['path']) == job
        assert brief(data) == json.loads(json.dumps(done[jid(job)]))
        yield from map(tuple, data['tokens'])
        todo += [key(job[0], p) for p in data['open']]


def continuation(work_dir, prepared, all_roots, done, prefix):
    """Proof records after the original prefix, including full reflected proofs."""
    equations, cases = prepared
    copies = reflections(prepared, all_roots)
    def remaining(case):
        return job_tokens(work_dir, done, [b for b in all_roots if b[0] == case])
    def original(case):
        for path in prefix:
            yield from (tuple(r['token']) for r in read(path)['records'] if r['case'] == case)
    for case in sorted({b[0] for b in all_roots}):
        if case in copies:
            source = copies[case]
            values = itertools.chain(original(source), remaining(source))
            yield from (dict(case=case, token=reflection.token(equations, cases[source], t)) for t in values)
        else:
            yield from (dict(case=case, token=t) for t in remaining(case))


def splice(run_dir, work_dir, prepared, code, all_roots, done):
    """The splice (see the vocabulary): every job's tokens, read from its file, fed through focus.State and committed
    as chunks."""
    state = focus.replay(run_dir, *prepared, code)
    start = taken(run_dir, work_dir, code)
    chunks = sorted(Path(run_dir).glob('chunk-*.json.gz'))
    prefix = chunks[:start['chunks']]
    initial = read(prefix[-1])['checkpoint']
    # TODO: error copy; says the run's open boxes are no longer the ones fanout set out to prove
    assert [key(*b) for b in initial['frontier']] == all_roots, 'Claude: "the run moved since fanout took its roots"'
    assert initial['lp'] == start['lp']
    stream = continuation(work_dir, prepared, all_roots, done, prefix)
    # A restart must reproduce the already committed splice, not merely skip
    # the same number of records from a potentially different proof.
    consumed = 0
    for path in chunks[start['chunks']:]:
        for saved in read(path)['records']:
            expected = next(stream)
            assert saved == dict(case=expected['case'], token=list(expected['token']))
            consumed += 1
    assert state.lp == start['lp'] + consumed
    records = []
    for record in stream:
        state.feed(record)
        records.append(record)
        if len(records) >= CHUNK:
            focus.commit(run_dir, state, records, code)
            records = []
    assert not state.frontier and state.witness is None
    if records or state.outcome != 'excluded':
        state.outcome = 'excluded'
        focus.commit(run_dir, state, records, code)


def stop(signum, frame):
    """SIGTERM's handler: terminates the workers, then exits (2026-10-23: a SIGTERM to the driver alone left its
    workers running, orphaned; the shepherd stops searches below its floor with SIGTERM).  Their jobs' files are not
    written, so a restart reruns them."""
    for child in multiprocessing.active_children(): child.terminate()
    # TODO: error copy; says fanout was stopped by the signal, naming it
    raise SystemExit(f'Claude: "fanout stopped by signal {signum}"')


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
        head = dict(version=1, n=n, order=m, workers=WORKERS, budget=BUDGET, deep=DEEP, roots=len(all_roots),
                    root_cases=[c for c, _ in all_roots], root_depths=[len(path) for _, path in all_roots],
                    prefix_lp=start['lp'], prefix_case=start['case'], code=code)
        if not journal.exists(): note(journal, 'header', **head)
        assert {k: json.loads(journal.read_text().splitlines()[0])[k] for k in ('n', 'order', 'code')} == \
               {k: head[k] for k in ('n', 'order', 'code')}
        note(journal, 'session', workers=WORKERS, reflections=reflections(prepared, all_roots))
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
    signal.signal(signal.SIGTERM, stop)
    outcome = run(Path(f'scratch/focus{n}/run'), Path(f'focus_{n}_journal.jsonl'), Path(f'scratch/fanout{n}'),
                  Path(f'fanout_{n}_journal.jsonl'), n, m)
    print(json.dumps(dict(n=n, order=m, outcome=outcome)), flush=True)


if __name__ == '__main__':
    main()
