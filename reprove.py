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
  reproof   of a job: its tree, the one assembly checked (by its tree_sha256, read again from the job's file), walked
            on its box as fanout.work walked it, each node solved on focus.case_lp's LP for
            its case, a box's first child from its parent's post-solve state and its second from its parent's basis,
            restored; each L's box proven by an attempt; each W's point checked exactly, as focus.State checks one.
            Below a tree's lex cut ['D'] (fanout.py's 'lex', only on a mixed box of a case closed under the reversal),
            an L's box that is dead is proven without a solve by the cut's certificate, 0 on every row and -1 on the
            cut's row, checked by certbb.lower_bound with the cut's row; any other L's by an attempt, whose
            certificate holds below the cut too (the cut's row taking 0).
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
import hashlib
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
    lp, lex = lp_for(case), fanout.Lex(equations.N)
    cut, second = [], object()             # the cut's row once the tree's ['D'] is read; its second side's marker
    stack, proved, start = [(tuple(map(tuple, path)), None)], [0] * len(ATTEMPTS), time.monotonic()
    def split(p, lo, hi, position):
        assert type(position) is int and 0 <= position < len(lo) and lo[position] < hi[position], p   # a free one
        lp.solve(lo, hi)
        stack.extend([(p + ((position, 1),), lp.H.getBasis()), (p + ((position, 0),), None)])
    def leaf(p, lo, hi):
        if cut and lex.status(lo, hi) == 'dead':                  # below the cut: proven by the cut's row alone
            # TODO: error copy; says the lex cut's certificate fails to prove a dead box below the cut, naming the box
            assert certbb.lower_bound(rows + cut, lo, hi, [0] * len(rows) + [-1]) > 0, \
                f'Claude: "the cut does not prove {json.dumps(p)}"'
            dead_leaves[0] += 1
            return
        proved[close(lp, rows, lo, hi, f'job {fanout.jid(job)}, box {json.dumps(p)}')] += 1
    def lexcut(p, lo, hi):                 # the tree's first token, on the job's own box (assembly checked it mixed)
        assert not cut and p == tuple(map(tuple, path)) and fanout.Lex(equations.N).status(lo, hi) == 'mixed', p
        cut.append((lex.sparse, 0))
        stack.extend([(second, None), (p, None)])
    def point(p, lo, hi, x):           # an exact solution, checked as focus.State checks one
        assert len(x) == equations.N and all(type(t) is int and l <= t <= u for t, l, u in zip(x, lo, hi)), p
        assert certbb.point_certificate(rows, x) is None, p
    actions, dead_leaves = dict(B=split, L=leaf, W=point, D=lexcut), [0]
    for node in tree:
        p, basis = stack.pop()
        # TODO: error copy; says a tree token falls on the lex cut's second side, which no tree proves
        assert p is not second, 'Claude: "a tree token on the cut\'s second side"'
        lo, hi = fanout.box(equations.N, p)
        if basis is not None:
            assert lp.H.setBasis(basis) == OK
        actions[node[0]](p, lo, hi, *node[1:])
    return dict(job=fanout.jid(job), nodes=len(tree), leaves=sum(proved) + dead_leaves[0],
                attempts=dict(zip(ATTEMPTS, proved)), dead=dead_leaves[0], seconds=time.monotonic() - start)


def task(work_dir, job, sha):
    """A worker's task: the reproof of the job's tree, read from its file by fanout.load, which must still hold the
    tree that assembly checked, whose tree_sha256 is sha (2026-10-25 review: a file changed after assembly was
    reproven as it then was)."""
    data = fanout.load(Path(work_dir) / 'jobs' / f'{fanout.jid(job)}.json.gz')
    # TODO: error copy; says a job's file changed after assembly checked it, naming the job
    assert data['tree_sha256'] == sha, f'Claude: "the file of job {fanout.jid(job)} changed after assembly"'
    return walk(job, data['tree'])


def codes():
    """The code a recheck runs, as its totals name it (2026-10-26 launch review: they named none, and reprove.py is
    in neither fingerprint): code, focus.fingerprint, and fanout_code, fanout.fingerprint, both the run's, which
    assembly checks against fanout's journal; and reprove_code, the sha256 of reprove.py's bytes."""
    return dict(code=focus.fingerprint(), fanout_code=fanout.fingerprint(),
                reprove_code=hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest())


def run(run_dir, work_dir, journal, n, m, workers):
    """Rechecks the finished fanout run of (n, m): fanout.assemble, then every job's reproof, workers at once.  Its
    totals: jobs, nodes, leaves, leaves proven by each attempt, dead leaves proven by the lex cut, the reproofs'
    seconds, and the code that ran (codes), asserted the same after the reproofs as before assembly."""
    run_dir, work_dir, journal = Path(run_dir), Path(work_dir), Path(journal)
    prepared, named = focus.prepare(n, m), codes()
    code = named['code']
    with open(run_dir / 'run.lock', 'a') as theirs, open(work_dir / 'lock', 'a') as ours:
        fcntl.flock(theirs, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(ours, fcntl.LOCK_EX | fcntl.LOCK_NB)
        done = fanout.finished(work_dir)
        jobs = fanout.assemble(run_dir, work_dir, journal, prepared, code, fanout.roots(run_dir, work_dir, code), done)
        pool = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn'), initializer=init,
                                   initargs=(prepared,))
        try:
            proofs = list(pool.map(functools.partial(task, work_dir), jobs,
                                   [done[fanout.jid(job)]['tree_sha256'] for job in jobs]))
        finally:
            pool.shutdown(cancel_futures=True)              # a failed reproof cancels the jobs not yet begun
        # TODO: error copy; says the code changed while the recheck ran, so its totals cannot name the code that ran
        assert codes() == named, 'Claude: "the code changed during the recheck"'
    return dict(jobs=len(proofs), nodes=sum(p['nodes'] for p in proofs), leaves=sum(p['leaves'] for p in proofs),
                attempts={a: sum(p['attempts'][a] for p in proofs) for a in ATTEMPTS},
                dead=sum(p['dead'] for p in proofs), seconds=sum(p['seconds'] for p in proofs), **named)


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
