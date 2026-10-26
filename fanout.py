#!/usr/bin/env python3
"""Claude's fanout (named 2026-10-23, dreeves: "ok"): finishes a stopped focus.py run with WORKERS processes, each
checking every certificate exactly as it makes it, keeps only the proof's tree (2026-10-25, dreeves: "for 432:12, that
sounds fine to store less"), and fits the jobs' trees together by assembly before its finish.
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
            tree and the boxes still open, in the order focus.State would pop them, which become jobs.  A job's file under jobs/ is the durable record that it is done; a restart reruns no job
            with a file.  Jobs run shallowest first: the biggest boxes are split soonest.
  tree      a job's proof as its file keeps it (version 2, 2026-10-25): its tokens in depth-first order, each L token's
            certificate dropped once certbb.Check has passed it, so ['B', p], ['L'] or ['W', x]; and tree_sha256, the
            sha256 of the tree's compact JSON, made by the worker and kept in the job's file and its job_end.  At
            432:12 a job's gzipped file took 0.75 bytes a node at 10,000 nodes and 0.93 at 4,000, against 292 to 295
            with the certificates (quals_fanout_tree, scratch/record-20261025/launch432/treeonly).  A job file of
            version 1, with them, as 672:13's are, is refused, not read.
  assembly  the last step, once no job is left, in place of the splice of certificates into focus.py's chunks
            before 2026-10-25: focus.replay of the run, whose chunks keep their certificates (checked again) and must
            still end at the roots (unmoved); two checks of the journal: every session ran the fanout code that
            assembles (fanout_code, see 'trust'), and no probe found a witness (a case with a solution cannot be
            excluded); then three checks of shape alone: (1) each job's tree, read on its box from the file the walk
            finds for the box, which must hold that box, splits only positions free there and leaves open exactly the
            boxes the job handed back (frontier); (2) the walk from each root through the jobs of the boxes left open
            reaches every job file, once, so the jobs' boxes and the run's closed ones tile the box of each case but a
            reflected one exactly; (3) every job_end in the journal has its job's file, with its tree_sha256 (a job's
            file may lack its job_end, its driver stopped between the two).  Each session's start makes the first
            check and (3) too, before any probe or job, so that a run moved by another writer, or a job file lost
            after its job_end, stops the fanout at once (2026-10-25 review: they were found after the last job).  Then
            the finish, in fanout's journal: focus.py's chunks and journal stay as the stopped run left them.
  trust     so an exclusion rests on focus.replay of the run's chunks, on certbb.Check passing each job's
            certificates on the job's box as its worker made them (once: no file keeps them), and on assembly.  A
            reflected case (see reflections) closes with its source: reversing positions maps its solutions onto its
            source's, the rows checked exactly by reflection.mapping.  reprove.py rechecks a finished run's trees from
            scratch, on demand, solving every leaf's LP again for a certificate; the run never calls it.  The workers'
            and assembly's code is fanout.py, and the reflections' reflection.py, neither among focus.fingerprint's
            sources: fanout_code, the sha256 of the two files' bytes (fingerprint), is in the journal's header and
            each session's record, a session whose fanout_code is not the header's stops at its start, and assembly
            refuses a run any session of which ran other code than its own (2026-10-25 review: nothing recorded
            which fanout.py had made a tree).
  witness   a job's W token: an exact 0/1 solution of its case's equations, so an example of the order.  It ends the
            fanout at once; it needs no assembly, being its own certificate.  Before the finish journals it, the
            driver reads it back from its job's file, as the last token of the job's tree, and checks it exactly on
            the job's box, as work checks one (witnessed): whether a worker of this session made it or an earlier
            session's did (2026-10-25 review: a witness read back from a file was journaled unchecked).
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
            point of the case's box, so the tree has E[2^(D+1)] - 1 nodes (on case_lp's option, in expectation over
            HiGHS's draws), one LP solve each, and by Jensen's inequality at least 2^(E[D]+1) - 1.
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
FIELDS = {'version', 'case', 'path', 'root', 'tree', 'tree_sha256', 'open', 'seconds', 'witness'}   # a job file's keys
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
    # the rename made durable too, so that a job_end, which note fsyncs after it, never outlives its file (2026-10-25)
    directory = os.open(path.parent, os.O_RDONLY)
    os.fsync(directory)
    os.close(directory)


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


def digest(tree):
    """A tree's tree_sha256 (see 'tree'): the sha256 of its compact JSON."""
    return hashlib.sha256(json.dumps(tree, separators=(',', ':')).encode()).hexdigest()


def fingerprint():
    """fanout_code (see 'trust'): the sha256 of fanout.py's bytes followed by reflection.py's."""
    root = Path(__file__).resolve().parent
    return hashlib.sha256(b''.join((root / name).read_bytes() for name in ('fanout.py', 'reflection.py'))).hexdigest()


def save(work_dir, job, root, result):
    """A done job's file, version 2: its box, its root's index, its tree and tree_sha256, its open boxes, its seconds
    and any witness."""
    write_atomic(work_dir / 'jobs' / f'{jid(job)}.json.gz',
                 dict(version=2, case=job[0], path=[list(p) for p in job[1]], root=root, **result))


def load(path):
    """A done job's file, read and checked: version 2 with FIELDS, named for its box, its tree its tree_sha256's."""
    # TODO: error copy; says a job file that assembly needs is not there, naming it
    assert path.exists(), f'Claude: "no job file {path.name}"'
    data = read(path)
    # TODO: error copy; says a job file is not a tree-only one (version 2), so fanout refuses to read it, naming it
    assert data['version'] == 2 and set(data) == FIELDS, f'Claude: "{path.name} is not a tree-only job file"'
    assert path.name == f'{jid(key(data["case"], data["path"]))}.json.gz', path
    # TODO: error copy; says a job file's tree is not the one its own tree_sha256 names, naming the file
    assert digest(data['tree']) == data['tree_sha256'], f'Claude: "the tree of {path.name} fails its sha256"'
    return data


def brief(entry):
    """What the driver keeps of a done job: its open boxes, witness, root and tree_sha256, not its tree (its tokens,
    before tree-only files, were tens of megabytes at 672; assembly reads each tree back from its job's file)."""
    return {k: entry[k] for k in ('open', 'witness', 'root', 'tree_sha256')}


def finished(work_dir):
    """brief of each done job, by id, from the job files, each checked by load."""
    return {f.name.split('.')[0]: brief(load(f)) for f in sorted((Path(work_dir) / 'jobs').glob('*.json.gz'))}


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


def exact(rows, lo, hi, x):
    """x, asserted an exact solution of rows in the 0/1 box from lo to hi, as focus.State checks one: an int for each
    position, within the box, breaking no row."""
    assert len(x) == len(lo) and all(type(t) is int and l <= t <= u for t, l, u in zip(x, lo, hi)), x
    assert certbb.point_certificate(rows, x) is None, x
    return x


def work(job):
    """Runs the job (see the vocabulary): its tree and tree_sha256, its open boxes' paths, its seconds and any
    witness."""
    (equations, cases), budget, deep = WORK
    case, path = job
    choice = cases[case]
    rows = certbb.node_rows(equations, choice)
    check = certbb.Check(equations, tuple((M, (v,)) for M, v in choice), *box(equations.N, path))
    lp = lp_for(case)
    stack, tree, start = [(path, None)], [], time.monotonic()
    while stack and len(tree) < HARD * budget and (len(tree) < budget or len(stack[-1][0]) > len(path) + deep):
        p, basis = stack.pop()
        lo, hi = box(equations.N, p)
        if basis is not None:
            assert lp.H.setBasis(basis) == certbb.highs.HighsStatus.kOk
        token = focus.step(lp, equations, choice, lo, hi)
        tree.append(['L'] if token[0] == 'L' else list(token))       # an L's certificate: checked below, then dropped
        if token[0] == 'W':                # an exact solution, checked as focus.State checks one: the job's end
            return dict(tree=tree, tree_sha256=digest(tree), open=[], seconds=time.monotonic() - start,
                        witness=exact(rows, lo, hi, token[1]))
        check.feed(token)
        stack += [(p + ((token[1], 1),), lp.H.getBasis()), (p + ((token[1], 0),), None)] if token[0] == 'B' else []
    return dict(tree=tree, tree_sha256=digest(tree), open=[p for p, _ in stack], seconds=time.monotonic() - start,
                witness=None)


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


def searched(prepared, all_roots):
    """The roots that jobs prove, with their indices: all but reflected cases' (see reflections)."""
    copies = reflections(prepared, all_roots)
    return [(root, job) for root, job in enumerate(all_roots) if job[0] not in copies]


def witnessed(prepared, work_dir, name):
    """The witness of the job whose file is named name (see 'witness'): read back by load, its tree's last token, and
    checked exactly on the job's box by exact."""
    equations, cases = prepared
    data = load(Path(work_dir) / 'jobs' / f'{name}.json.gz')
    # TODO: error copy; says a job file's witness is not the point its tree ends at, naming the file
    assert data['tree'][-1] == ['W', data['witness']], f'Claude: "the witness of {name} is not its tree\'s"'
    return exact(certbb.node_rows(equations, cases[data['case']]), *box(equations.N, data['path']), data['witness'])


def farm(prepared, all_roots, done, work_dir, journal):
    """Journals a probe of each case with a job not done, then runs every job not done, WORKERS at once, shallowest
    first; the witness found (0/1 list), read back from its job's file and checked by witnessed, else None."""
    heap, order = [], itertools.count()
    def reach(job, root):                  # the jobs not done at or below job
        todo = [job]
        while todo:
            b = todo.pop()
            entry = done.get(jid(b))
            if entry is None: heapq.heappush(heap, (len(b[1]), next(order), b, root))
            else: todo += [key(b[0], p) for p in entry['open']]
    for root, job in searched(prepared, all_roots): reach(job, root)
    found = [name for name, e in done.items() if e['witness'] is not None]
    if found: return witnessed(prepared, work_dir, found[0])
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
                note(journal, 'job_end', job=jid(job), case=job[0], root=root, lps=len(result['tree']),
                     seconds=result['seconds'], open=len(result['open']), tree_sha256=result['tree_sha256'])
                if result['witness'] is not None:
                    pool.shutdown(cancel_futures=True)
                    return witnessed(prepared, work_dir, jid(job))
                for p in result['open']: heapq.heappush(heap, (len(p), next(order), key(job[0], p), root))
    return None


def frontier(N, path, tree):
    """The boxes a job's tree leaves open on the box of path (see 'tree'), as work leaves them, the next to prove last,
    each a list of [position, value] pairs as a job file keeps it.  Asserts that each token is an L, or a B splitting
    a position free in its box, and that a box is left for it."""
    stack = [[list(p) for p in path]]
    for node in tree:
        # TODO: error copy; says a tree has a token after its job's last box was closed
        assert stack, 'Claude: "a tree token after the last box"'
        p = stack.pop()
        # TODO: error copy; says a tree token is neither an L nor a B splitting a position free in its box
        assert node == ['L'] or (len(node) == 2 and node[0] == 'B' and type(node[1]) is int and 0 <= node[1] < N
                                 and all(q != node[1] for q, _ in p)), 'Claude: "a tree token is not an L or a free B"'
        stack += [p + [[node[1], 1]], p + [[node[1], 0]]] if node[0] == 'B' else []
    return stack


def unmoved(run_dir, work_dir, prepared, code, all_roots):
    """Asserts that focus.replay of the run's chunks, their certificates checked again, still ends where fanout took
    its roots: at the roots, after the chunks and LP solves that roots.json records, with no witness.  Assembly's
    first check, made at each session's start too."""
    start, state = taken(run_dir, work_dir, code), focus.replay(run_dir, *prepared, code)
    # TODO: error copy; says the run's open boxes are no longer the ones fanout set out to prove
    assert [key(*b) for b in state.frontier] == all_roots, 'Claude: "the run moved since fanout took its roots"'
    assert (state.chunks, state.lp, state.witness) == (start['chunks'], start['lp'], None)


def assemble(run_dir, work_dir, journal, prepared, code, all_roots, done):
    """Assembly (see the vocabulary), with done as the driver keeps it: the jobs, (case, path) each, in the order its
    walk reaches them."""
    equations, _ = prepared
    unmoved(run_dir, work_dir, prepared, code, all_roots)
    records, current = [json.loads(line) for line in Path(journal).read_text().splitlines()], fingerprint()
    # TODO: error copy; says a session of fanout's run ran other fanout code than the code assembling it
    assert all(r['fanout_code'] == current for r in records if r['event'] in ('header', 'session')), \
        'Claude: "a session of the run ran other fanout code"'
    # TODO: error copy; says a probe of the run found an exact solution, so the run cannot end excluded
    assert not [r for r in records if r['event'] == 'probe' and r['witnesses']], 'Claude: "a probe found a witness"'
    walked, jobs = {}, []                  # each job's tree_sha256 by id, and each job, as the walk reaches them
    for root, job in searched(prepared, all_roots):
        todo = [job]
        while todo:
            job = todo.pop()
            name = jid(job)
            data = load(Path(work_dir) / 'jobs' / f'{name}.json.gz')
            # TODO: error copy; says the file named for a job's box holds another box, naming the job
            assert key(data['case'], data['path']) == job, f'Claude: "the file of {name} is another box\'s"'
            assert name not in walked and data['root'] == root and data['witness'] is None, name
            assert brief(data) == json.loads(json.dumps(done[name])), name
            # TODO: error copy; says a job's tree does not leave open the boxes the job handed back, naming the job
            assert frontier(equations.N, data['path'], data['tree']) == data['open'], f'Claude: "the tree of {name}"'
            walked[name] = data['tree_sha256']
            jobs.append(job)
            todo += [key(job[0], p) for p in data['open']]
    # TODO: error copy; says a job file lies outside the boxes that the walk from the roots reaches
    assert set(walked) == set(done), f'Claude: "job files outside the tiling: {sorted(set(done) - set(walked))}"'
    for r in (r for r in records if r['event'] == 'job_end'):
        # TODO: error copy; says a job_end in fanout's journal has no job file, or one with another tree, naming it
        assert walked.get(r['job']) == r['tree_sha256'], f'Claude: "the job_end of {r["job"]} is not its file\'s"'
    return jobs


def stop(signum, frame):
    """SIGTERM's handler: terminates the workers, then exits (2026-10-23: a SIGTERM to the driver alone left its
    workers running, orphaned; the shepherd stops searches below its floor with SIGTERM).  Their jobs' files are not
    written, so a restart reruns them."""
    for child in multiprocessing.active_children(): child.terminate()
    # TODO: error copy; says fanout was stopped by the signal, naming it
    raise SystemExit(f'Claude: "fanout stopped by signal {signum}"')


def run(run_dir, work_dir, journal, n, m):
    """Finishes focus.py's stopped run of (n, m) in run_dir: excluded, once assembled, or witness.  Each session
    starts, before any probe or job, with assembly's first check (unmoved), a check that the journal's header is
    this session's run's and code's, and assembly's check (3) of the job files done (2026-10-25 review: a run moved,
    a fanout.py edited or a job file lost was found only by assembly, after the last job, or not at all)."""
    run_dir, work_dir, journal = Path(run_dir), Path(work_dir), Path(journal)
    prepared, code = focus.prepare(n, m), focus.fingerprint()
    (work_dir / 'jobs').mkdir(parents=True, exist_ok=True)
    with open(run_dir / 'run.lock', 'a') as theirs, open(work_dir / 'lock', 'a') as ours:
        fcntl.flock(theirs, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(ours, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = taken(run_dir, work_dir, code)
        all_roots = [key(*b) for b in start['frontier']]
        unmoved(run_dir, work_dir, prepared, code, all_roots)
        head = dict(version=1, n=n, order=m, workers=WORKERS, budget=BUDGET, deep=DEEP, roots=len(all_roots),
                    root_cases=[c for c, _ in all_roots], root_depths=[len(path) for _, path in all_roots],
                    prefix_lp=start['lp'], prefix_case=start['case'], code=code, fanout_code=fingerprint())
        if not journal.exists(): note(journal, 'header', **head)
        same = ('n', 'order', 'code', 'fanout_code')       # what each session shares with the journal's header
        # TODO: error copy; says fanout's journal began with another run, or under other code, than this session's
        assert {k: json.loads(journal.read_text().splitlines()[0])[k] for k in same} == {k: head[k] for k in same}, \
            'Claude: "the journal began with another run or under other code"'
        note(journal, 'session', workers=WORKERS, reflections=reflections(prepared, all_roots),
             fanout_code=head['fanout_code'])
        done = finished(work_dir)
        for r in (r for r in map(json.loads, journal.read_text().splitlines()) if r['event'] == 'job_end'):
            # TODO: error copy; says a job_end in fanout's journal has no job file, or one with another tree, naming it
            assert done.get(r['job'], {}).get('tree_sha256') == r['tree_sha256'], \
                f'Claude: "the job_end of {r["job"]} is not its file\'s"'
        witness = farm(prepared, all_roots, done, work_dir, journal)
        if witness is None: assemble(run_dir, work_dir, journal, prepared, code, all_roots, done)
        outcome = 'witness' if witness is not None else 'excluded'
        note(journal, 'finish', outcome=outcome, witness=witness)
    return outcome


def main():
    # TODO: error copy; says how to run fanout: with the length of a stopped focus.py run, 432, 480 or 672
    assert len(sys.argv) == 2 and sys.argv[1] in ('432', '480', '672'), \
        'Claude: "usage: python3 -B fanout.py 432|480|672"'
    n = int(sys.argv[1])
    m = {432: 12, 480: 14, 672: 13}[n]
    signal.signal(signal.SIGTERM, stop)
    outcome = run(Path(f'scratch/focus{n}/run'), Path(f'scratch/fanout{n}'), Path(f'fanout_{n}_journal.jsonl'), n, m)
    print(json.dumps(dict(n=n, order=m, outcome=outcome)), flush=True)


if __name__ == '__main__':
    main()
