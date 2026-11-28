#!/usr/bin/env python3
"""Fable 5.2's quals for searchwatch/sweep_eta.py, the estimator of a sweep (searches/tilted/sweep.py), 2026-11-27
(dreeves, of the 528:12 search's box: "i find it hard to believe that this lindy-only ETA is the best we can do").
Run from the repo:
    python3 -B quals/quals_sweep_eta.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Each copies searchwatch's track.py and sweep_eta.py
into a temporary directory and runs the estimator there on made-up logs, as the tracker runs it.
"""
import sys
sys.dont_write_bytecode = True
import os, json, math, shutil, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PY = sys.executable
LAMBDA, RECOVERY = 2.5, 0.9


def sandbox():
    d = tempfile.mkdtemp(prefix='sweep-eta-quals-')
    os.mkdir(os.path.join(d, 'searchwatch')); os.mkdir(os.path.join(d, 'runs'))
    for name in ('track.py', 'sweep_eta.py'): shutil.copy(os.path.join(HERE, 'searchwatch', name), os.path.join(d, 'searchwatch'))
    return d


def chunk(digest, K, count, first, last, nodes, time, cpu=1.0):
    return dict(digest=digest, K=K, count=count, total=1.0, first=first, last=last, nodes=nodes, capped=0, mass=0.01, cpu_s=cpu, time=time, found=[])


def lay(d, logs, curves, found=()):
    """Makes d's sweep directory anew: the logs (pI.jsonl), their curves (pI.curve.json) and the found file; and a record with its start line.  Returns the estimator's arguments and the record's path."""
    sweep = os.path.join(d, 'sweep')
    shutil.rmtree(sweep, ignore_errors=True); os.mkdir(sweep)
    args = [str(LAMBDA), str(RECOVERY), sweep]
    with open(os.path.join(sweep, 'found.jsonl'), 'w') as f: f.write(''.join(json.dumps(x) + '\n' for x in found))
    for i, (rows, curve) in enumerate(zip(logs, curves)):
        log, cur = os.path.join(sweep, f'p{i}.jsonl'), os.path.join(sweep, f'p{i}.curve.json')
        with open(log, 'w') as f: f.write(''.join(json.dumps(x) + '\n' for x in rows))
        with open(cur, 'w') as f: json.dump(curve, f)
    rec = os.path.join(d, 'runs', 'job.jsonl')
    with open(rec, 'w') as f:
        f.write(json.dumps(dict(event='start', name='job', search='sweep', target='528:12', estimator='searchwatch/sweep_eta.py', command='job', cwd='/',
                                found=os.path.join(sweep, 'found.jsonl'), adopted=False, pid=1, tracker=1, time=1000.0)) + '\n')
    return args, rec


def estimates(d, args, rec):
    p = subprocess.run([PY, '-B', os.path.join('searchwatch', 'sweep_eta.py'), *args], cwd=d, env=dict(os.environ, TRACK_RECORD=rec, PYTHONPATH='searchwatch'),
                       capture_output=True, text=True, timeout=60)
    return p, [x for x in (json.loads(s) for s in open(rec)) if x['event'] == 'estimate']


def close(a, b, tol=1e-9): return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def to_come(cost, mid, done, count, b):
    """The nodes of the cosets done to count - 1, when a coset at position i costs cost (i / mid)^-b."""
    return cost * mid ** b * (count ** (1 - b) - done ** (1 - b)) / (1 - b)


# Two profiles' logs.  The first has swept 1,000 of 4,000 cosets in four chunks ending at times 1010, 1030, 1070, 1150; the
# second 500 of 1,000 in two chunks ending at 1020 and 1060.  The latest tenth of a log's swept cosets is its last chunk here.
A = [chunk('aa', 4000, 4000, 0, 249, 8000, 1010.0, cpu=9.0), chunk('aa', 4000, 4000, 250, 499, 6000, 1030.0),
     chunk('aa', 4000, 4000, 500, 749, 5000, 1070.0), chunk('aa', 4000, 4000, 750, 999, 4000, 1150.0)]
B = [chunk('bb', 1000, 1000, 0, 249, 3000, 1020.0, cpu=5.0), chunk('bb', 1000, 1000, 250, 499, 2000, 1060.0)]
CA = dict(digest='aa', K=4000, curve=[[500, 0.10], [1000, 0.16], [4000, 0.30]])
CB = dict(digest='bb', K=1000, curve=[[250, 0.02], [500, 0.03], [1000, 0.04]])


def q_the_estimate_is_the_logs_work():
    # Replicata: the estimator on the two logs above, with 2.5 witnesses expected before the sweep and recovery 0.9.
    # Expectata: one estimate, in the record's form (track.checked): basis sweep, unit nodes; done the logs' nodes, 28,000;
    # finished the cosets swept, 1,500, and pending those left, 3,500.  A log's nodes to come: its latest chunks' nodes
    # a coset (16 and 8), taken as the cost at their middle position (875 and 375), falling as position^-b down the rest
    # of its list, with b 0.3 for the median and 0.4 and 0.2 for the band (measured at 528:12: 0.28 to 0.35).  total is
    # done plus both logs' nodes to come; to_go the longer of the two logs' times, nodes to come at the wall seconds a
    # node of its latest chunks (80 / 4000 and 40 / 2000); rate the nodes a second of those chunks together, 100.  prior
    # 1 - exp(-2.5); exists 1 - exp(-(2.5 - 0.9 (0.16 + 0.03))), the curves read at the cosets swept.
    d = sandbox()
    try:
        args, rec = lay(d, [A, B], [CA, CB])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        e = ests[0]
        sys.path.insert(0, os.path.join(d, 'searchwatch'))
        import track
        track.checked(track.lines(rec))
        assert (e['basis'], e['unit'], e['done'], e['finished'], e['pending']) == ('sweep', 'nodes', 28000, 1500, 3500), e
        come = {b: (to_come(16.0, 875.0, 1000, 4000, b), to_come(8.0, 375.0, 500, 1000, b)) for b in (0.2, 0.3, 0.4)}
        for key, b in (('lo', 0.4), ('median', 0.3), ('hi', 0.2)):
            assert close(e['total'][key], 28000 + sum(come[b])), (key, e['total'], come[b])
            assert close(e['to_go'][key], max(come[b][0] * 80 / 4000, come[b][1] * 40 / 2000)), (key, e['to_go'], come[b])
        assert e['total']['lo'] < e['total']['median'] < e['total']['hi'] and close(e['rate'], 4000 / 80 + 2000 / 40), e
        assert close(e['prior'], 1 - math.exp(-2.5)) and close(e['exists'], 1 - math.exp(-(2.5 - 0.9 * 0.19))), e
    finally:
        shutil.rmtree(d)


def q_a_finished_sweep_has_nothing_to_go():
    # Replicata: one log that has swept all 500 of its 500 cosets; its curve ends at 0.5 expected witnesses.
    # Expectata: total is done at all three levels, to_go 0 at all three, pending 0, finished 500, rate its last chunk's
    # (2,000 nodes in 20 s: a record's rate is positive), and exists 1 - exp(-(2.5 - 0.9 * 0.5)), below the prior; the
    # record holds to its form (track.checked).
    d = sandbox()
    try:
        rows = [chunk('cc', 500, 500, 0, 249, 3000, 1010.0), chunk('cc', 500, 500, 250, 499, 2000, 1030.0)]
        args, rec = lay(d, [rows], [dict(digest='cc', K=500, curve=[[250, 0.3], [500, 0.5]])])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:])
        e = ests[0]
        assert e['total'] == dict(median=5000, lo=5000, hi=5000) and e['to_go'] == dict(median=0, lo=0, hi=0), e
        assert (e['done'], e['pending'], e['finished'], e['rate']) == (5000, 0, 500, 100), e
        sys.path.insert(0, os.path.join(d, 'searchwatch'))
        import track
        track.checked(track.lines(rec))
        assert close(e['exists'], 1 - math.exp(-(2.5 - 0.45))) and e['exists'] < e['prior'], e
    finally:
        shutil.rmtree(d)


def q_exists_falls_with_the_cosets_swept_and_is_1_at_a_witness():
    # Replicata: the first log above cut after one, two and four chunks, each a run of the estimator; then four chunks
    # with a line in the found file.
    # Expectata: exists falls from run to run while nothing is found (the curve read at 250, 500 and 1,000 cosets, the
    # first by a straight line from 0), every one below the prior; with a witness it is 1.
    d = sandbox()
    try:
        seen = []
        for n in (1, 2, 4):
            args, rec = lay(d, [A[:n]], [CA])
            p, ests = estimates(d, args, rec)
            assert p.returncode == 0 and len(ests) == 1, (n, p.stderr[-2000:])
            seen.append(ests[0])
        for e, c in zip(seen, (0.05, 0.10, 0.16)):
            assert close(e['exists'], 1 - math.exp(-(2.5 - 0.9 * c))) and e['exists'] < e['prior'], (e, c)
        assert seen[0]['exists'] > seen[1]['exists'] > seen[2]['exists']
        args, rec = lay(d, [A], [CA], found=[dict(code='0F', order=12)])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and ests[0]['exists'] == 1 and close(ests[0]['prior'], 1 - math.exp(-2.5)), (p.stderr[-2000:], ests)
    finally:
        shutil.rmtree(d)


def q_the_sweep_is_its_directory_s_lists():
    # Replicata: the directory with the first log and its curve alone; then with the second list's too; then with a
    # third list's log that has no curve yet (a sweep just started).
    # Expectata: the estimator takes no list by name: a list is a curve X.curve.json with its log X.jsonl.  The
    # first estimate is of the one list (1,000 cosets finished), the second of both (1,500), and the third is the
    # second again: a log is counted from the moment its curve is there.
    d = sandbox()
    try:
        args, rec = lay(d, [A], [CA])
        _, one = estimates(d, args, rec)
        args, rec = lay(d, [A, B], [CA, CB])
        _, two = estimates(d, args, rec)
        with open(os.path.join(args[2], 'p2.jsonl'), 'w') as f: f.write(json.dumps(chunk('dd', 500, 500, 0, 249, 900, 1015.0)) + '\n')
        p, three = estimates(d, args, rec)
        assert p.returncode == 0 and [len(x) for x in (one, two, three)] == [1, 1, 2], (p.stderr[-2000:], one, two, three)
        assert (one[0]['finished'], two[0]['finished'], three[1]['finished']) == (1000, 1500, 1500)
        assert {k: v for k, v in three[1].items() if k != 'time'} == {k: v for k, v in two[0].items() if k != 'time'}
    finally:
        shutil.rmtree(d)


def q_a_curve_of_another_list_stops_it():
    # Replicata: the first log above with a curve whose digest is another list's; then with a curve that ends before
    # the list does.
    # Expectata: each time the estimator fails and appends nothing: an estimate from a curve that is not the list's
    # would be a wrong P(exists).
    d = sandbox()
    try:
        for curve in (dict(CA, digest='zz'), dict(CA, curve=CA['curve'][:2])):
            args, rec = lay(d, [A], [curve])
            p, ests = estimates(d, args, rec)
            assert p.returncode != 0 and not ests, (curve, p.returncode, ests)
    finally:
        shutil.rmtree(d)


if __name__ == '__main__':
    # TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
    if not __debug__: raise SystemExit('Fable 5.2: "nolo sine assertionibus currere (python -O)"')
    names = sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]
    failed = 0
    for name in names:
        try:
            globals()[name]()
            print(f'PASSED {name}', flush=True)
        except Exception:
            failed += 1
            print(f'FAILED {name}:\n{traceback.format_exc()[-1500:]}', flush=True)
    raise SystemExit(1 if failed else 0)
