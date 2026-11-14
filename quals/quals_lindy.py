#!/usr/bin/env python3
"""Fable 5.2's quals for searchwatch/lindy.py, the estimator of a search that knows nothing but its age (2026-11-11;
dreeves, of the bar and the probability graph that one search alone had: "the search progress code seems like a
shitshow; can you revamp it? ... anti-magic anti-magic anti-magic").  Run from the repo:
    python3 -B quals/quals_lindy.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Each copies searchwatch's track.py, lindy.py and
chance.py into a temporary directory and runs them there, so that the records are that directory's runs/.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, shutil, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PY = sys.executable
TRACK, LINDY = os.path.join('searchwatch', 'track.py'), os.path.join('searchwatch', 'lindy.py')
IMPORTS = dict(os.environ, PYTHONPATH='searchwatch')


def sandbox():
    d = tempfile.mkdtemp(prefix='lindy-quals-')
    os.mkdir(os.path.join(d, 'searchwatch'))
    os.mkdir(os.path.join(d, 'runs'))
    for name in ('track.py', 'lindy.py', 'chance.py'): shutil.copy(os.path.join(HERE, 'searchwatch', name), os.path.join(d, 'searchwatch'))
    return d


def record(d, name):
    return [json.loads(x) for x in open(os.path.join(d, 'runs', name + '.jsonl'), encoding='utf-8').read().splitlines()]


def write(d, name, lines):
    with open(os.path.join(d, 'runs', name + '.jsonl'), 'w', encoding='utf-8') as f: f.write(''.join(json.dumps(x) + '\n' for x in lines))


def start(name, search, target, t, pid, tracker=1):
    return dict(event='start', name=name, search=search, target=target, estimator=LINDY, command='job', cwd='/', found=None,
                adopted=False, pid=pid, tracker=tracker, time=t)


def inside(d, code):
    p = subprocess.run([PY, '-B', '-c', code], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.endswith('ok\n'), (p.returncode, p.stdout, p.stderr)
    return p.stdout


def close(a, b, tol=1e-9): return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def q_an_hour_old_search_has_gott_s_estimate():
    # Replicata: lindy.estimate(3600), the estimate of a search that has run for an hour.
    # Expectata: Gott's rule, whose q quantile of the time to go is the age times q / (1 - q): to_go's median 3600 s
    # (the page's "remaining time = elapsed time"), its band from a 9th of the age to 9 times it (the levels 0.1 and
    # 0.9, chance.BANDS's gott), 400 to 32400 s; the work is the time: unit seconds, done 3600, rate 1 a second, and
    # the total the age more than to_go, 7200 (4000 to 36000); the prior that what is searched for exists and that
    # probability now both 0.5, lindy.IGNORANT (dreeves, 2026-11-06: "go with 50% as the ignorant prior when there's no
    # model or whatever"), since a search that knows only its age learns nothing of it; basis lindy; nothing pending
    # that it can count (null; 2026-11-12), nor finished (null; that evening, dreeves: "sure, let's get the count of
    # finished tasks over time"); and with a time the line holds to the record's form (track.checked).
    d = sandbox()
    try:
        inside(d, """import lindy, track
e = lindy.estimate(3600.0)
close = lambda a, b: abs(a - b) < 1e-6
assert (e['event'], e['basis'], e['unit'], e['done'], e['rate'], e['prior'], e['exists'], lindy.IGNORANT) == ('estimate', 'lindy', 'seconds', 3600.0, 1.0, 0.5, 0.5, 0.5), e
assert e['pending'] is None and e['finished'] is None, e
assert all(close(e['to_go'][k], v) for k, v in dict(median=3600, lo=400, hi=32400).items()), e['to_go']
assert all(close(e['total'][k], v) for k, v in dict(median=7200, lo=4000, hi=36000).items()), e['total']
start = dict(event='start', name='r', search='S', target='16:4', estimator='lindy.py', command='job', cwd='/', found=None, adopted=False, pid=7, tracker=8, time=100.0)
track.checked([start, dict(e, time=3700.0)])
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_a_search_of_no_age_has_a_valid_estimate():
    # Replicata: lindy.estimate(0.0), a search at the moment it starts, as a line of a record (track.checked).
    # Expectata: done 0, to_go and the total all 0, rate 1, the probabilities 0.5: Gott's rule at age 0, and a line
    # the record's form accepts, so that a run's first estimate, written as it starts, is one.
    d = sandbox()
    try:
        inside(d, """import lindy, track
e = lindy.estimate(0.0)
zero = dict(median=0.0, lo=0.0, hi=0.0)
assert (e['done'], e['to_go'], e['total'], e['rate'], e['exists']) == (0.0, zero, zero, 1.0, 0.5), e
start = dict(event='start', name='r', search='S', target='16:4', estimator='lindy.py', command='job', cwd='/', found=None, adopted=False, pid=7, tracker=8, time=100.0)
track.checked([start, dict(e, time=100.0)])
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_the_age_is_the_search_s_seconds_of_running():
    # Replicata: in a sandbox's runs/, handmade records, with now the time of the qual: of the search tilt at 16:4,
    # an ended run from now - 5000 to now - 4000, an ended run from now - 4500 to now - 3000 (they overlap), a run
    # started at now - 1000 with no end whose pid is this qual's own process (it lives), and a run started at now -
    # 2500 with no end whose pid is no process's and whose last line is its start (its tracker died); of the search
    # tree at 16:4, a run from now - 9000 to now - 100; of tilt at 32:5, one from now - 9000 to now - 100.  Then
    # lindy.py run as the tracker runs it, TRACK_RECORD naming the living run's record.
    # Expectata: it appends one line to that record and to no other: an estimate whose time is now (within 30 s)
    # and whose done is the seconds some run of ITS search was going, 2000 + 1000 (the two overlapping runs' stretch,
    # then the living run's; the dead run, with no end and no later line, adds nothing; the other searches' runs are
    # none of its) within 30 s; and to_go's median equals its done.
    # Since 2026-11-13 (Fable 5.2; quals_track's docstring, its last spec change: a run with no end goes on while its
    # process or, that gone, its tracker lives) the dead run's tracker is a pid of no live process too, as its
    # replicata always said ("its tracker died"); until then every record here named the tracker 1, a live process.
    d = sandbox()
    try:
        now = time.time()
        gone = subprocess.Popen([PY, '-c', 'pass']); gone.wait()             # a pid of no live process
        dead = subprocess.Popen([PY, '-c', 'pass']); dead.wait()             # another: the dead run's tracker
        end = lambda t: dict(event='end', time=t, status=0)
        write(d, 'a1', [start('a1', 'tilt', '16:4', now - 5000, 11), end(now - 4000)])
        write(d, 'a2', [start('a2', 'tilt', '16:4', now - 4500, 12), end(now - 3000)])
        write(d, 'a3', [start('a3', 'tilt', '16:4', now - 1000, os.getpid())])
        write(d, 'a4', [start('a4', 'tilt', '16:4', now - 2500, gone.pid, dead.pid)])
        write(d, 'b1', [start('b1', 'tree', '16:4', now - 9000, 13), end(now - 100)])
        write(d, 'c1', [start('c1', 'tilt', '32:5', now - 9000, 14), end(now - 100)])
        before = {name: record(d, name) for name in ('a1', 'a2', 'a4', 'b1', 'c1')}
        p = subprocess.run([PY, '-B', LINDY], cwd=d, env=dict(os.environ, TRACK_RECORD=os.path.join(d, 'runs', 'a3.jsonl')),
                           capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        assert {name: record(d, name) for name in before} == before
        first, e = record(d, 'a3')
        assert e['event'] == 'estimate' and abs(e['time'] - now) < 30, e
        assert abs(e['done'] - 3000) < 30 and close(e['to_go']['median'], e['done']), e
    finally:
        shutil.rmtree(d)


def q_a_restarted_search_keeps_its_age():
    # Replicata: in a sandbox, the tracker's own runs: track.py run r1 tilt 16:4 searchwatch/lindy.py -- python3 -c
    # "import time; time.sleep(1.5)"; then the same as r2; then r3 of the search tree at the same target.
    # Expectata: each record holds its start, an estimate at least, and its end, and holds to the record's form; r1's
    # first estimate, written as the run started, has done below 1 s; r2's first has done at least 1.5 s, r1's seconds
    # of running: a restart of a search goes on from its age, as its box on the page does; r3's first has done below
    # 1 s again: another search at the same target starts at no age.
    d = sandbox()
    try:
        for name, search in [('r1', 'tilt'), ('r2', 'tilt'), ('r3', 'tree')]:
            p = subprocess.run([PY, '-B', TRACK, 'run', name, search, '16:4', LINDY, '--', PY, '-c', 'import time; time.sleep(1.5)'],
                               cwd=d, capture_output=True, text=True, timeout=60)
            assert p.returncode == 0, p.stderr
        firsts = {name: record(d, name)[1] for name in ('r1', 'r2', 'r3')}
        assert all(e['event'] == 'estimate' and e['basis'] == 'lindy' for e in firsts.values()), firsts
        assert firsts['r1']['done'] < 1 and firsts['r2']['done'] >= 1.5 and firsts['r3']['done'] < 1, firsts
        inside(d, "import glob, track\nfor path in glob.glob('runs/*.jsonl'): track.checked(track.lines(path))\nprint('ok')\n")
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
