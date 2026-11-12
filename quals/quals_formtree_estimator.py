#!/usr/bin/env python3
"""Fable 5.2's quals for searchwatch/formtree_eta.py as an estimator (see track.py's vocabulary): the program the
tracker runs beside a form-tree search (2026-11-11; dreeves, of the bar and the probability graph that 288:10's form
tree alone had: "the search progress code seems like a shitshow; can you revamp it? ... anti-magic anti-magic
anti-magic").  Run from the repo:
    python3 -B quals/quals_formtree_estimator.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Each copies searchwatch's track.py, chance.py,
formtree_work.py and formtree_eta.py into a temporary directory and runs them there.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, shutil, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PY = sys.executable
TRACK, ESTIMATOR = os.path.join('searchwatch', 'track.py'), os.path.join('searchwatch', 'formtree_eta.py')
IMPORTS = dict(os.environ, PYTHONPATH='searchwatch')
# a model whose every dive says each root's tree has 1000 nodes, with next to no spread about that: a tree of two
# roots, a and b
MODEL = dict(kind='formtree', seed=1, log_bias=0.0, discrepancy_log_sd=1e-9, rate_log_sd=0.0, root_log_sd=0.0, root_log_sd_uncertainty=0.0,
             roots=[dict(name='a', blocks=[[1000.0] * 8] * 8), dict(name='b', blocks=[[1000.0] * 8] * 8)],
             provenance='made up for the quals', assumptions='none')


def sandbox():
    d = tempfile.mkdtemp(prefix='formtree-estimator-quals-')
    os.mkdir(os.path.join(d, 'searchwatch'))
    os.mkdir(os.path.join(d, 'runs'))
    for name in ('track.py', 'chance.py', 'formtree_work.py', 'formtree_eta.py'):
        shutil.copy(os.path.join(HERE, 'searchwatch', name), os.path.join(d, 'searchwatch'))
    json.dump(MODEL, open(os.path.join(d, 'model.json'), 'w'))
    return d


def record(d, name):
    return [json.loads(x) for x in open(os.path.join(d, 'runs', name + '.jsonl'), encoding='utf-8').read().splitlines()]


def write(path, lines):
    with open(path, 'w', encoding='utf-8') as f: f.write(''.join(json.dumps(x) + '\n' for x in lines))


def verdict(name, nodes, spills): return dict(ok=True, start=name, nodes=nodes, open=0, spills=spills)


def inside(d, code):
    p = subprocess.run([PY, '-B', '-c', code], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0 and p.stdout.endswith('ok\n'), (p.returncode, p.stdout, p.stderr)
    return p.stdout


def q_the_rate_weighs_recent_running_more():
    # Replicata: formtree_eta.rate on the points (seconds of running, nodes checked by then): (0, 0), (100, 200),
    # (200, 400), a steady pace; then (0, 0), (10800, 1000), (21600, 4000): 1000 nodes in the first three hours and
    # 3000 in the next three; then that with the two stretches' nodes swapped.
    # Expectata (dreeves, 2026-11-07, of the rate: "maybe 3 hours at least, or just do an exponentially weighted moving
    # average of rates"; formtree_work.TAU, 3 h): the steady pace gives exactly 2 nodes a second; the second, each
    # interval weighted by exp(-age / TAU), its age measured between the intervals' middles back from the newest (so
    # the older one weighs 1/e), (3000 + 1000 / e) / (10800 (1 + 1 / e)) = 0.22797 nodes a second, above the plain
    # average 4000 / 21600 = 0.18519; the swapped one (1000 + 3000 / e) / (10800 (1 + 1 / e)) = 0.14240, below it.
    d = sandbox()
    try:
        inside(d, """import math, formtree_eta as eta
assert eta.rate([(0, 0), (100, 200), (200, 400)]) == 2
up, down, e = eta.rate([(0, 0), (10800, 1000), (21600, 4000)]), eta.rate([(0, 0), (10800, 3000), (21600, 4000)]), math.e
assert abs(up - (3000 + 1000 / e) / (10800 * (1 + 1 / e))) < 1e-12 and abs(up - 0.22797) < 1e-5, up
assert abs(down - (1000 + 3000 / e) / (10800 * (1 + 1 / e))) < 1e-12 and abs(down - 0.14240) < 1e-5, down
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_a_tree_two_fifths_checked_has_its_estimate():
    # Replicata: formtree_eta.estimate with MODEL made of one root (its dives all say 1000 nodes, next to no spread),
    # that root with 400 nodes checked and not complete, the points (0, 0), (100, 200), (200, 400), and the prior 0.5.
    # Expectata: basis formtree, unit nodes, done 400, rate 2 nodes a second; the total 1000 nodes and the time to go
    # (1000 - 400) / 2 = 300 s, each band at its median (the model has no spread); the prior 0.5, and P(exists | none
    # found) 0.375: a witness is as likely anywhere in the tree (chance.work), so with 3/5 of the tree unsearched
    # 0.5 (3/5) / (0.5 + 0.5 (3/5)).  With the prior 0.01: 0.006 / (0.99 + 0.006).  The line holds to the record's form.
    d = sandbox()
    try:
        inside(d, f"""import formtree_eta as eta, track
model = dict({MODEL!r}, roots={MODEL['roots'][:1]!r})
roots, points = [dict(name='a', done=400, complete=False)], [(0, 0), (100, 200), (200, 400)]
e = eta.estimate(model, roots, points, 0.5)
near = lambda a, b: abs(a - b) <= 1e-3 * b
assert (e['event'], e['basis'], e['unit'], e['done'], e['rate'], e['prior']) == ('estimate', 'formtree', 'nodes', 400, 2, 0.5), e
assert all(near(e['total'][k], 1000) and near(e['to_go'][k], 300) for k in ('median', 'lo', 'hi')), e
assert near(e['exists'], 0.375), e
assert near(eta.estimate(model, roots, points, 0.01)['exists'], 0.006 / 0.996)
start = dict(event='start', name='r', search='S', target='16:4', estimator='e', command='job', cwd='/', found=None, adopted=False, pid=7, tracker=8, time=100.0)
track.checked([start, dict(e, time=300.0)])
print('ok')
""")
    finally:
        shutil.rmtree(d)


def start(name, t, pid):
    return dict(event='start', name=name, search='tree', target='16:4', estimator=ESTIMATOR, command='job', cwd='/', found=None,
                adopted=False, pid=pid, tracker=1, time=t)


def q_the_estimator_appends_the_search_s_estimate():
    # Replicata: in a sandbox, MODEL's tree of two roots, a and b; a verdicts file in which a's task checked 600 nodes
    # and spilled the node c, c's checked 401 with no spill, and b's checked 250 and spilled the node d, which has no
    # verdict; two records of the search tree at 16:4, with now the qual's time: an ended run from now - 1000 to now -
    # 600, whose one estimate, of basis formtree at now - 800, has done 200, and a run started at now - 400 with no
    # end whose pid is this qual's own; then formtree_eta.py run as the tracker runs it, with the verdicts file, the
    # model's file and the prior 0.5 as its arguments and TRACK_RECORD naming the living run's record.
    # Expectata: it appends one estimate to that record alone, of basis formtree and unit nodes, that holds to the
    # record's form.  Its done is 1249, exact: a's 600 - 1 + 401, complete, and b's 250 - 1, not complete (a spilled
    # node is counted where it is checked).  Its points are (0, 0), (200, 200) and (800, 1249) in seconds of running
    # (the first run's 400 s, then the second's 400 so far), so its rate is the weighted (1049 + 200 w) / (600 + 200
    # w), w = exp(-400 / 10800): 1.566 nodes a second (within 2%).  a is done at 1000 nodes, as its dives said (so
    # the model's shared factor is 1), and b's tree is the model's 1000, so the total is 2000 nodes, the time to go
    # (2000 - 1249) / rate, and P(exists | none found), as a witness is as likely anywhere in the tree, 0.5 q / (0.5 +
    # 0.5 q) with q = 751 / 2000: 0.273.
    d = sandbox()
    try:
        now = time.time()
        write(os.path.join(d, 'verdicts.jsonl'), [verdict('a', 600, ['c']), verdict('c', 401, []), verdict('b', 250, ['d'])])
        old = dict(event='estimate', time=now - 800, basis='formtree', unit='nodes', done=200, rate=1.0, total=dict(median=2000.0, lo=2000.0, hi=2000.0),
                   to_go=dict(median=1800.0, lo=1800.0, hi=1800.0), prior=0.5, exists=0.47)
        write(os.path.join(d, 'runs', 't1.jsonl'), [start('t1', now - 1000, 11), old, dict(event='end', time=now - 600, status=0)])
        write(os.path.join(d, 'runs', 't2.jsonl'), [start('t2', now - 400, os.getpid())])
        before = record(d, 't1')
        p = subprocess.run([PY, '-B', ESTIMATOR, 'verdicts.jsonl', 'model.json', '0.5'], cwd=d,
                           env=dict(os.environ, TRACK_RECORD=os.path.join(d, 'runs', 't2.jsonl')), capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stderr
        assert record(d, 't1') == before
        first, e = record(d, 't2')
        import math
        w = math.exp(-400 / 10800)
        rate, near = (1049 + 200 * w) / (600 + 200 * w), lambda a, b, tol=0.02: abs(a - b) <= tol * b
        assert (e['event'], e['basis'], e['unit'], e['done'], e['prior']) == ('estimate', 'formtree', 'nodes', 1249, 0.5) and abs(e['time'] - now) < 30, e
        assert near(e['rate'], rate), (e['rate'], rate)
        assert all(near(e['total'][k], 2000, 1e-3) and near(e['to_go'][k], 751 / e['rate'], 1e-3) for k in ('median', 'lo', 'hi')), e
        q = 751 / 2000
        assert near(e['exists'], 0.5 * q / (0.5 + 0.5 * q), 1e-3), e
        inside(d, "import track\ntrack.checked(track.lines('runs/t2.jsonl'))\nprint('ok')\n")
    finally:
        shutil.rmtree(d)


def q_no_estimate_before_any_work_or_with_an_open_node():
    # Replicata: as the qual above, the search's one record a living run started at now - 400, with three verdicts
    # files in turn: an empty one (no task has ended yet); one whose only verdict, a's, left 1 node open; one in
    # which every root is complete (a's 300 nodes and b's 250, no spill).
    # Expectata: each time the estimator exits nonzero, says why on its stderr and leaves the record as it was: with
    # no work done there is no rate yet; an open node is no checked work but a find to look at; and a finished tree
    # has no forecast (its tracker writes the end).  The tracker reads no status, so the run goes on either way
    # (quals_track's q_an_estimator_that_fails_or_hangs_leaves_the_run_alone).
    d = sandbox()
    try:
        now = time.time()
        write(os.path.join(d, 'runs', 't2.jsonl'), [start('t2', now - 400, os.getpid())])
        before = record(d, 't2')
        for verdicts in ([], [dict(verdict('a', 300, []), open=1)], [verdict('a', 300, []), verdict('b', 250, [])]):
            write(os.path.join(d, 'verdicts.jsonl'), verdicts)
            p = subprocess.run([PY, '-B', ESTIMATOR, 'verdicts.jsonl', 'model.json', '0.5'], cwd=d,
                               env=dict(os.environ, TRACK_RECORD=os.path.join(d, 'runs', 't2.jsonl')), capture_output=True, text=True, timeout=120)
            assert p.returncode != 0 and 'AssertionError' in p.stderr and record(d, 't2') == before, (verdicts, p.returncode, p.stderr)
    finally:
        shutil.rmtree(d)


SEARCH = '''import json, time
for i in range(8):
    time.sleep(0.4)
    with open('verdicts.jsonl', 'a') as f: f.write(json.dumps(dict(ok=True, start='ab'[i % 2] + str(i), nodes=50, open=0, spills=[])) + '\\n')
'''


def q_the_tracker_runs_it_beside_a_search():
    # Replicata: in a sandbox, a made-up search (SEARCH) that every 0.4 s, eight times, appends to verdicts.jsonl the
    # verdict of a task of 50 nodes (none of them a root of MODEL's tree: the roots a and b stay incomplete), run by
    # the tracker with its period set to 0.5 s: run t1 tree 16:4 searchwatch/formtree_eta.py verdicts.jsonl model.json
    # 0.01 -- python3 -c SEARCH, after writing verdicts.jsonl with the roots' own verdicts, a's and b's, 10 nodes each,
    # spilling the eight tasks' nodes (a0, b1, a2, ...).
    # Expectata: the tracker exits 0; the record is the start, estimates, and the end, and holds to the record's form;
    # there are three estimates at least, all of basis formtree with prior 0.01, their done never falling and the
    # last's at least 200 above the first's; each one's P(exists | none found) is below the prior, and falls as the
    # work goes on (the last below the first).
    d = sandbox()
    try:
        write(os.path.join(d, 'verdicts.jsonl'), [verdict('a', 10, ['a0', 'a2', 'a4', 'a6']), verdict('b', 10, ['b1', 'b3', 'b5', 'b7'])])
        periodic = "import sys, track; track.PERIOD = 0.5; track.main(sys.argv[1:])"
        p = subprocess.run([PY, '-B', '-c', periodic, 'run', 't1', 'tree', '16:4', ESTIMATOR, 'verdicts.jsonl', 'model.json', '0.01', '--',
                            PY, '-c', SEARCH], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stderr
        first, *estimates, end = record(d, 't1')
        assert (first['event'], end['event'], end['status']) == ('start', 'end', 0), (first, end)
        assert len(estimates) >= 3 and all((e['basis'], e['unit'], e['prior']) == ('formtree', 'nodes', 0.01) for e in estimates), (estimates, p.stderr)
        done, exists = [e['done'] for e in estimates], [e['exists'] for e in estimates]
        assert done == sorted(done) and done[-1] >= done[0] + 200, done
        assert all(x < 0.01 for x in exists) and exists[-1] < exists[0], exists
        inside(d, "import track\ntrack.checked(track.lines('runs/t1.jsonl'))\nprint('ok')\n")
    finally:
        shutil.rmtree(d)


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0 = time.time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
