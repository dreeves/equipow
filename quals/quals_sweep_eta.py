#!/usr/bin/env python3
"""Fable 5.2's quals for searchwatch/sweep_eta.py, the estimator of a sweep (searches/tilted/sweep.py), 2026-11-27
(dreeves, of the 528:12 search's box: "i find it hard to believe that this lindy-only ETA is the best we can do").
Run from the repo:
    python3 -B quals/quals_sweep_eta.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Each copies searchwatch's track.py and sweep_eta.py
into a temporary directory and runs the estimator there on made-up logs, as the tracker runs it: on a sweep's
directory, which holds its lists and its model (model.json: the count model's witnesses, its calibration, the
enumeration's recovery).  Until the evening of 2026-11-27 the count and the recovery were arguments.
"""
import sys
sys.dont_write_bytecode = True
import os, json, math, shutil, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PY = sys.executable
LAMBDA, RECOVERY = 2.5, 0.9
MODEL = dict(count=LAMBDA, calibration=1.0, recovery=RECOVERY, why='made up')   # the sweep's model.json (2026-11-27, evening)


def sandbox():
    d = tempfile.mkdtemp(prefix='sweep-eta-quals-')
    os.mkdir(os.path.join(d, 'searchwatch')); os.mkdir(os.path.join(d, 'runs'))
    for name in ('track.py', 'sweep_eta.py'): shutil.copy(os.path.join(HERE, 'searchwatch', name), os.path.join(d, 'searchwatch'))
    return d


def chunk(digest, K, count, first, last, nodes, time, cpu=1.0):
    return dict(digest=digest, K=K, count=count, total=1.0, first=first, last=last, nodes=nodes, capped=0, mass=0.01, cpu_s=cpu, time=time, found=[])


def lay(d, logs, curves, found=(), model=MODEL, plan=()):
    """Makes d's sweep directory anew: the logs (pI.jsonl), their curves (pI.curve.json) and the found file; and a record with its start line.  Returns the estimator's arguments and the record's path."""
    sweep = os.path.join(d, 'sweep')
    shutil.rmtree(sweep, ignore_errors=True); os.mkdir(sweep)
    args = [sweep]
    with open(os.path.join(sweep, 'model.json'), 'w') as f: json.dump(model, f)
    with open(os.path.join(sweep, 'found.jsonl'), 'w') as f: f.write(''.join(json.dumps(x) + '\n' for x in found))
    with open(os.path.join(sweep, 'plan.jsonl'), 'w') as f: f.write(''.join(json.dumps(x) + '\n' for x in plan))   # the lists the sweep is to take (2026-11-28)
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
CA = dict(digest='aa', K=4000, W=190, floor=4, curve=[[500, 0.10], [1000, 0.16], [4000, 0.30]])
CB = dict(digest='bb', K=1000, W=190, floor=4, curve=[[250, 0.02], [500, 0.03], [1000, 0.04]])
SPEED = dict(lo=0.8, median=1.0, hi=1.7)     # what a time to go is multiplied by (2026-11-28): a tenth of the lists' rests took under 0.8 of the time forecast, a tenth over 1.7


def q_the_estimate_is_the_logs_work():
    # Replicata: the estimator on the two logs above, with 2.5 witnesses expected before the sweep and recovery 0.9.
    # Expectata: one estimate, in the record's form (track.checked): basis sweep, unit nodes; done the logs' nodes, 28,000;
    # finished the cosets swept, 1,500, and pending those left, 3,500.  A log's nodes to come: its latest chunks' nodes
    # a coset (16 and 8), taken as the cost at their middle position (875 and 375), falling as position^-b down the rest
    # of its list, with b 0.3 for the median and 0.4 and 0.2 for the band (measured at 528:12: 0.28 to 0.35).  total is
    # done plus both logs' nodes to come; to_go the longer of the two logs' times, nodes to come at the wall seconds a
    # node of its latest chunks (80 / 4000 and 40 / 2000); rate the nodes a second of those chunks together, 100.  prior
    # 1 - exp(-2.5); exists 1 - exp(-(2.5 - 0.9 (0.16 + 0.03))), the curves read at the cosets swept; and (2026-11-27;
    # dreeves: the chance that the search itself finds a witness "should also be shown on the page") finds
    # 1 - exp(-0.9 (0.30 + 0.04 - 0.19)), from the witnesses expected in the cosets the lists have left.
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
            # (times SPEED since 2026-11-28: the band of a time to go holds the speed's spread too; a spec change with the estimator's)
            assert close(e['to_go'][key], SPEED[key] * max(come[b][0] * 80 / 4000, come[b][1] * 40 / 2000)), (key, e['to_go'], come[b])
        assert e['total']['lo'] < e['total']['median'] < e['total']['hi'] and close(e['rate'], 4000 / 80 + 2000 / 40), e
        assert close(e['prior'], 1 - math.exp(-2.5)) and close(e['exists'], 1 - math.exp(-(2.5 - 0.9 * 0.19))), e
        assert close(e['finds'], 1 - math.exp(-0.9 * (0.30 + 0.04 - 0.19))), e
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
        args, rec = lay(d, [rows], [dict(digest='cc', K=500, W=190, floor=4, curve=[[250, 0.3], [500, 0.5]])])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:])
        e = ests[0]
        assert e['total'] == dict(median=5000, lo=5000, hi=5000) and e['to_go'] == dict(median=0, lo=0, hi=0), e
        assert (e['done'], e['pending'], e['finished'], e['rate']) == (5000, 0, 500, 100), e
        sys.path.insert(0, os.path.join(d, 'searchwatch'))
        import track
        track.checked(track.lines(rec))
        assert close(e['exists'], 1 - math.exp(-(2.5 - 0.45))) and e['exists'] < e['prior'], e
        assert e['finds'] == 0, e   # 2026-11-27: nothing is left in which to find one
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
            assert close(e['finds'], 1 - math.exp(-0.9 * (0.30 - c))), (e, c)   # 2026-11-27: the list's 0.30, less what is swept
        assert seen[0]['exists'] > seen[1]['exists'] > seen[2]['exists'] and seen[0]['finds'] > seen[1]['finds'] > seen[2]['finds']
        args, rec = lay(d, [A], [CA], found=[dict(code='0F', order=12)])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and ests[0]['exists'] == 1 and ests[0]['finds'] == 1 and close(ests[0]['prior'], 1 - math.exp(-2.5)), (p.stderr[-2000:], ests)
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
        with open(os.path.join(args[0], 'p2.jsonl'), 'w') as f: f.write(json.dumps(chunk('dd', 500, 500, 0, 249, 900, 1015.0)) + '\n')
        p, three = estimates(d, args, rec)
        assert p.returncode == 0 and [len(x) for x in (one, two, three)] == [1, 1, 2], (p.stderr[-2000:], one, two, three)
        assert (one[0]['finished'], two[0]['finished'], three[1]['finished']) == (1000, 1500, 1500)
        assert {k: v for k, v in three[1].items() if k != 'time'} == {k: v for k, v in two[0].items() if k != 'time'}
    finally:
        shutil.rmtree(d)


def q_the_model_is_the_directory_s_and_its_calibration_scales_every_count():
    # Replicata: the two logs of the first qual, with a model.json of count 2.5, recovery 0.9 and calibration 0.8 (a
    # control's witnesses found over those the count model predicted); then with a model.json that lacks its
    # calibration, and with one that has a field more.
    # Expectata (dreeves, 2026-11-27, asked whether the box should use the count as calibrated on the one cell where it
    # could be counted: "can-opener question"): the model is a file of the sweep's directory, read at every estimate,
    # so that a revised model needs no relaunch; every count of the model is taken at 0.8 of its value: prior
    # 1 - exp(-0.8 * 2.5), exists 1 - exp(-0.8 (2.5 - 0.9 * 0.19)), finds 1 - exp(-0.8 * 0.9 (0.34 - 0.19)); the work
    # and the time to go are as with any calibration.  A model.json without a field, or with one more, stops the
    # estimator, which then appends nothing.
    # Resultata before: the count and the recovery were arguments of each launch, so the ten runs already going kept
    # the count they were started with.
    d = sandbox()
    try:
        args, rec = lay(d, [A, B], [CA, CB])
        _, plain = estimates(d, args, rec)
        args, rec = lay(d, [A, B], [CA, CB], model=dict(MODEL, calibration=0.8))
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:])
        e = ests[0]
        assert close(e['prior'], 1 - math.exp(-0.8 * 2.5)) and close(e['exists'], 1 - math.exp(-0.8 * (2.5 - 0.9 * 0.19))), e
        assert close(e['finds'], 1 - math.exp(-0.8 * 0.9 * (0.34 - 0.19))), e
        assert all(e[k] == plain[0][k] for k in ('done', 'total', 'to_go', 'rate', 'pending', 'finished')), (e, plain[0])
        for model in ({k: v for k, v in MODEL.items() if k != 'calibration'}, dict(MODEL, more=1)):
            args, rec = lay(d, [A, B], [CA, CB], model=model)
            p, ests = estimates(d, args, rec)
            assert p.returncode != 0 and not ests, (model, p.returncode, ests)
    finally:
        shutil.rmtree(d)


def q_a_list_swept_in_part_counts_its_part():
    # Replicata: the estimator on a list of 4,000 cosets of which the sweep takes the first 1,000 (its log's count),
    # 500 of them swept; the list's curve, to its 4,000.
    # Expectata (Fable 5.2, 2026-11-27, for lists at width 210, long ones swept a part at a time: sweep.py's "a larger
    # COUNT extends it"): the sweep is the part it takes.  pending the cosets left of the part, 500; finds
    # 1 - exp(-0.9 (0.16 - 0.10)), the witnesses expected in the part's cosets not yet swept, the curve read at the
    # count; exists as for any list, 1 - exp(-(2.5 - 0.9 0.10)).
    # Resultata before: finds counted the whole list's witnesses, 1 - exp(-0.9 (0.30 - 0.10)), which the sweep would
    # never reach.
    d = sandbox()
    try:
        part = [chunk('aa', 4000, 1000, 0, 249, 8000, 1010.0, cpu=9.0), chunk('aa', 4000, 1000, 250, 499, 6000, 1030.0)]
        args, rec = lay(d, [part], [CA])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        e = ests[0]
        assert (e['finished'], e['pending']) == (500, 500), e
        assert close(e['finds'], 1 - math.exp(-0.9 * (0.16 - 0.10))), e
        assert close(e['exists'], 1 - math.exp(-(2.5 - 0.9 * 0.10))), e
    finally:
        shutil.rmtree(d)


# A list of 1,000 cosets swept whole, 10,000 nodes, its last chunk at time 960; and a list of 100,000 swept whole in two
# chunks, a million nodes.
F = [chunk('ff', 1000, 1000, 0, 249, 4000, 900.0, cpu=5.0), chunk('ff', 1000, 1000, 250, 499, 3000, 920.0),
     chunk('ff', 1000, 1000, 500, 749, 2000, 940.0), chunk('ff', 1000, 1000, 750, 999, 1000, 960.0)]
CF = dict(digest='ff', K=1000, W=190, floor=4, curve=[[500, 0.02], [1000, 0.03]])
G = [chunk('gg', 100000, 100000, 0, 49999, 600000, 900.0, cpu=50.0), chunk('gg', 100000, 100000, 50000, 99999, 400000, 950.0)]
CG = dict(digest='gg', K=100000, W=190, floor=4, curve=[[50000, 0.2], [100000, 0.3]])
LIST = dict(W=190, floor=4, count=1000)


def q_planned_lists_count_before_they_start():
    # Replicata: a sweep directory with the finished list F, the second log above (500 of its 1,000 cosets swept) and a
    # plan that names those two and two more lists of their kind (width 190, floor 4, 1,000 cosets) with no curve yet.
    # Expectata (dreeves, 2026-11-28, of the sweep's ETA chart, whose time to go had jumped at every list a launcher
    # started: "these ETAs sure don't look calibrated"): the sweep is its plan.  A planned list not yet begun takes
    # what the finished lists of its kind took, 10,000 nodes: total is the nodes done, the running list's to come and
    # 20,000; pending the running list's 500 cosets and the two lists' 2,000.  The time to go is the nodes to come over
    # the nodes a second of the lists running (one, 2,000 nodes in 40 s), since the planned lists wait for them, or
    # the running list's own time where that is longer; times SPEED.  rate is the running list's, 50: a finished list
    # adds none.
    # Resultata before: the estimator read the lists begun alone, so the two planned lists added nothing until each
    # began, and rate summed every list's last, the finished one's too.
    d = sandbox()
    try:
        plan = [dict(LIST, name='p0'), dict(LIST, name='p1'), dict(LIST, name='q0'), dict(LIST, name='q1')]
        args, rec = lay(d, [F, B], [CF, CB], plan=plan)
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        e = ests[0]
        assert (e['done'], e['finished'], e['pending'], e['rate']) == (15000, 1500, 2500, 50), e
        for key, b in (('lo', 0.4), ('median', 0.3), ('hi', 0.2)):
            mine = to_come(8.0, 375.0, 500, 1000, b)
            assert close(e['total'][key], 15000 + mine + 20000), (key, e['total'], mine)
            assert close(e['to_go'][key], SPEED[key] * max(mine * 40 / 2000, (mine + 20000) / 50)), (key, e['to_go'], mine)
        sys.path.insert(0, os.path.join(d, 'searchwatch'))
        import track
        track.checked(track.lines(rec))
    finally:
        shutil.rmtree(d)


def q_a_list_just_begun_is_forecast_by_its_kind():
    # Replicata: the finished list G (100,000 cosets, a million nodes) and a list of its kind with 500 cosets swept,
    # 80,000 nodes, its top cosets the dearest; then that list alone.
    # Expectata (2026-11-28): a list under a fiftieth swept says little of its own cost (a width-220 list's forecast
    # from its first 4,500 cosets was 2.3 times what its positions measured before gave), so beside a finished list of
    # its kind it is forecast by that one: a million nodes in all, 920,000 to come at all three levels.  Alone, it is
    # forecast by its own cost as any list, the three levels apart.
    # Resultata before: its own cost alone, which puts 2.1 to 4.9 million nodes on it here.
    d = sandbox()
    try:
        J = [chunk('jj', 100000, 100000, 0, 249, 50000, 1100.0, cpu=5.0), chunk('jj', 100000, 100000, 250, 499, 30000, 1120.0)]
        CJ = dict(digest='jj', K=100000, W=190, floor=4, curve=[[50000, 0.2], [100000, 0.3]])
        args, rec = lay(d, [G, J], [CG, CJ])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        e = ests[0]
        assert all(close(e['total'][key], 1000000 + 1000000) for key in ('lo', 'median', 'hi')) and e['pending'] == 99500, e
        assert all(close(e['to_go'][key], SPEED[key] * 920000 * 20 / 30000) for key in ('lo', 'median', 'hi')), e
        args, rec = lay(d, [J], [CJ])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        alone = ests[0]
        assert 2e6 < alone['total']['lo'] < alone['total']['median'] < alone['total']['hi'], alone
    finally:
        shutil.rmtree(d)


def q_a_kind_is_measured_by_its_latest_lists():
    # Replicata: seven finished lists of one kind, two that took 10,000 nodes and ended first, then five that took 2,000
    # each; the running second log above; and a plan with one more list of the kind.
    # Expectata (2026-11-28): lists run in the order of their profiles' ranks and a later rank's list is cheaper (at
    # 528:12, 3.5e11 nodes at rank 0 and 3e10 at rank 30), so the planned list takes what the five latest to end took,
    # 2,000 nodes, not the 10,000 of the first two.
    d = sandbox()
    try:
        ended = lambda i, nodes, t: [chunk(f'e{i}', 1000, 1000, 0, 999, nodes, t, cpu=5.0)]
        logs = [ended(i, 10000, 100.0 + i) for i in range(2)] + [ended(i, 2000, 200.0 + i) for i in range(2, 7)] + [B]
        curves = [dict(CF, digest=f'e{i}') for i in range(7)] + [CB]
        args, rec = lay(d, logs, curves, plan=[dict(LIST, name=f'p{i}') for i in range(8)] + [dict(LIST, name='q0')])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        e = ests[0]
        done = 2 * 10000 + 5 * 2000 + 5000
        assert e['done'] == done and close(e['total']['median'], done + to_come(8.0, 375.0, 500, 1000, 0.3) + 2000), e
    finally:
        shutil.rmtree(d)


def q_a_cut_list_is_no_measure_of_its_kind():
    # Replicata: the list F cut after 500 of its 1,000 cosets (its last line's count 500, was 1,000), the running
    # second log above, and a plan with one more list of 1,000 cosets.
    # Expectata (2026-11-28): the cut list is done (nothing pending for it) but is no whole list of the planned one's
    # kind, so the planned list takes what the running list of its kind is forecast to take in all, by its own cost
    # at the median: 5,000 and its nodes to come.
    # Resultata before: no planned list counted at all.
    d = sandbox()
    try:
        cut = F[:1] + [dict(F[1], count=500, was=1000)]
        args, rec = lay(d, [cut, B], [CF, CB], plan=[dict(LIST, name='p0'), dict(LIST, name='p1'), dict(LIST, name='q0')])
        p, ests = estimates(d, args, rec)
        assert p.returncode == 0 and len(ests) == 1, (p.returncode, p.stderr[-2000:], ests)
        e = ests[0]
        whole = 5000 + to_come(8.0, 375.0, 500, 1000, 0.3)
        assert (e['done'], e['pending'], e['rate']) == (12000, 1500, 50), e
        for key, b in (('lo', 0.4), ('median', 0.3), ('hi', 0.2)):
            assert close(e['total'][key], 12000 + to_come(8.0, 375.0, 500, 1000, b) + whole), (key, e['total'], whole)
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
