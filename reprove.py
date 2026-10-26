#!/usr/bin/env python3
"""Claude's reprove (name proposed 2026-10-25, awaiting dreeves's approval): rechecks a finished fanout.py run's trees
from scratch, on demand, trusting no check its workers made: assembly again, then every leaf's LP solved again for an
exact certificate, the jobs in parallel worker processes.  The run itself never calls it.  Run from this directory, with
the fanout run of N finished (both its locks are taken here, so neither focus.py nor fanout.py can run meanwhile):

    PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B reprove.py N

Vocabulary (with fanout.py's):
  attempt   how a leaf's LP is solved, in ATTEMPTS's order, until its multipliers make a certificate that
            certbb.lower_bound finds positive on the leaf's box: warm, from its parent's post-solve LP state, as its
            worker solved it; cold, after clearSolver; primal, after clearSolver again, by primal simplex
            (simplex_strategy 4) in place of certbb.Lp's dual (1), restored after.  A leaf that no attempt proves fails
            the recheck: an AssertionError naming its job and its box's path.
  reproof   of a job: its tree walked on its box as fanout.work walked it, each node solved on focus.case_lp's LP for
            its case, a box's first child from its parent's post-solve state and its second from its parent's basis,
            restored; each L's box proven by an attempt; each W's point checked exactly, as focus.State checks one.
            A B's solve only warm-starts its children: its position is the tree's.  Each node is one LP solve (a leaf
            retried, more), as at the job's making: at 432:12, 1.1 CPU ms a node, against 1.7 for the job itself, on
            one job of 10,000 nodes (scratch/record-20261025/launch432/treeonly/reprove_cost.py).
A reflected case has no tree to reprove: it closes with its source (see fanout.py's 'trust').  The run's chunks are
rechecked by focus.replay, within assembly, their certificates being kept.
"""
from concurrent.futures import ProcessPoolExecutor
import contextlib
import fcntl
import functools
import json
import multiprocessing
from pathlib import Path
import sys
import time

import certbb
import fanout
import focus

ATTEMPTS = ('warm', 'cold', 'primal')  # see the vocabulary
OK = certbb.highs.HighsStatus.kOk
PREPARED = None                        # a worker's prepared equations and cases, set by init


def init(prepared):
    """A worker's start: the prepared equations and cases, and no LP made yet."""
    global PREPARED
    PREPARED = prepared
    lp_for.cache_clear()


@functools.lru_cache(maxsize=None)
def lp_for(case):
    """The worker's LP for a case, made once, by focus.case_lp, as fanout's workers make theirs."""
    equations, cases = PREPARED
    return focus.case_lp(equations, cases[case])


def ray(lp, status, z):
    """The LP's multipliers from a solve: its dual ray's, if it ended Infeasible with one, else None."""
    return lp.multipliers(z) if status == 'Infeasible' and z is not None else None


def attempts(lp, lo, hi):
    """Each attempt's multipliers for the box (see 'attempt'), in ATTEMPTS's order, each solved only when asked for."""
    yield ray(lp, *lp.solve(lo, hi))
    assert lp.H.clearSolver() == OK
    yield ray(lp, *lp.solve(lo, hi))
    assert lp.H.clearSolver() == OK and lp.H.setOptionValue('simplex_strategy', 4) == OK
    try:
        yield ray(lp, *lp.solve(lo, hi))
    finally:
        assert lp.H.setOptionValue('simplex_strategy', 1) == OK


def close(lp, rows, lo, hi, where):
    """The index in ATTEMPTS of the first attempt whose certificate proves the box (see 'attempt'); where says which
    box it is, for the error."""
    with contextlib.closing(attempts(lp, lo, hi)) as tried:
        proven = next((i for i, n in enumerate(tried) if n is not None and certbb.lower_bound(rows, lo, hi, n) > 0),
                      None)
    # TODO: error copy; says that no attempt found an exact certificate for a leaf's box, naming the box
    assert proven is not None, f'Claude: "no certificate proves {where}"'
    return proven


def walk(job, tree):
    """The reproof (see the vocabulary) of tree on the box of job, (case, path), its case's LP warm from the worker's
    last solve: the job's id, its nodes, its leaves, how many of them each attempt proved, and its seconds."""
    equations, cases = PREPARED
    case, path = job
    rows = certbb.node_rows(equations, cases[case])
    lp = lp_for(case)
    stack, proved, start = [(tuple(map(tuple, path)), None)], [0] * len(ATTEMPTS), time.monotonic()
    def split(p, lo, hi, position):
        assert type(position) is int and lo[position] < hi[position], p           # a free position, as frontier asks
        lp.solve(lo, hi)
        stack.extend([(p + ((position, 1),), lp.H.getBasis()), (p + ((position, 0),), None)])
    def leaf(p, lo, hi):
        proved[close(lp, rows, lo, hi, f'job {fanout.jid(job)}, box {json.dumps(p)}')] += 1
    def point(p, lo, hi, x):           # an exact solution, checked as focus.State checks one
        assert len(x) == equations.N and all(type(t) is int and l <= t <= u for t, l, u in zip(x, lo, hi)), p
        assert certbb.point_certificate(rows, x) is None, p
    actions = dict(B=split, L=leaf, W=point)
    for node in tree:
        p, basis = stack.pop()
        lo, hi = fanout.box(equations.N, p)
        if basis is not None:
            assert lp.H.setBasis(basis) == OK
        actions[node[0]](p, lo, hi, *node[1:])
    return dict(job=fanout.jid(job), nodes=len(tree), leaves=sum(proved), attempts=dict(zip(ATTEMPTS, proved)),
                seconds=time.monotonic() - start)


def task(work_dir, job):
    """A worker's task: the reproof of the job's tree, read from its file by fanout.load."""
    return walk(job, fanout.load(Path(work_dir) / 'jobs' / f'{fanout.jid(job)}.json.gz')['tree'])


def run(run_dir, work_dir, journal, n, m, workers):
    """Rechecks the finished fanout run of (n, m): fanout.assemble, then every job's reproof, workers at once.  Its
    totals: jobs, nodes, leaves, leaves proven by each attempt, and the reproofs' seconds."""
    run_dir, work_dir, journal = Path(run_dir), Path(work_dir), Path(journal)
    prepared, code = focus.prepare(n, m), focus.fingerprint()
    with open(run_dir / 'run.lock', 'a') as theirs, open(work_dir / 'lock', 'a') as ours:
        fcntl.flock(theirs, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(ours, fcntl.LOCK_EX | fcntl.LOCK_NB)
        jobs = fanout.assemble(run_dir, work_dir, journal, prepared, code, fanout.roots(run_dir, work_dir, code),
                               fanout.finished(work_dir))
        pool = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn'), initializer=init,
                                   initargs=(prepared,))
        try:
            proofs = list(pool.map(functools.partial(task, work_dir), jobs))
        finally:
            pool.shutdown(cancel_futures=True)              # a failed reproof cancels the jobs not yet begun
    return dict(jobs=len(proofs), nodes=sum(p['nodes'] for p in proofs), leaves=sum(p['leaves'] for p in proofs),
                attempts={a: sum(p['attempts'][a] for p in proofs) for a in ATTEMPTS},
                seconds=sum(p['seconds'] for p in proofs))


def main():
    # TODO: error copy; says how to run reprove: with the length of a finished fanout run
    assert len(sys.argv) == 2 and sys.argv[1].isdigit(), 'Claude: "usage: python3 -B reprove.py N"'
    n = int(sys.argv[1])
    journal = Path(f'fanout_{n}_journal.jsonl')        # fanout.main's paths for n
    head = json.loads(journal.read_text().splitlines()[0])
    assert (head['event'], head['n']) == ('header', n), head
    total = run(Path(f'scratch/focus{n}/run'), Path(f'scratch/fanout{n}'), journal, n, head['order'], fanout.WORKERS)
    print(json.dumps(dict(n=n, order=head['order'], **total)), flush=True)


if __name__ == '__main__':
    main()
