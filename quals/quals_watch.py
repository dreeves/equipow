#!/usr/bin/env python3
"""Fable 5.2's quals for searchwatch/watch.py, the watcher that copies the tracked searches' records into the data file
of index.html's section "Search progress" (2026-11-11; dreeves: "the search progress code seems like a shitshow; can
you revamp it? reread AGENT.md first. anti-magic anti-magic anti-magic. "Find where the watcher decides which searches
get an odds history" is such a red flag. please kill all if-statements.").  Run from the repo:
    python3 -B quals/quals_watch.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  The records are handmade (start, estimate, end, below),
in a temporary directory.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, shutil, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, os.path.join(HERE, 'searchwatch'))
PY = sys.executable


def start(name, search, target, t, pid, found=None):
    return dict(event='start', name=name, search=search, target=target, estimator='est.py', command='job', cwd='/', found=found,
                adopted=False, pid=pid, tracker=1, time=t)


def estimate(t, done, total, to_go, exists=0.4, basis='formtree', unit='nodes', prior=0.5, rate=2.0, pending=None, finished=None):
    """An estimate at time t: done, the total's and to_go's medians (their bands 10% below and 50% above, the total's
    lower end no lower than done)."""
    band = lambda m, floor=0.0: dict(median=m, lo=max(floor, 0.9 * m), hi=1.5 * m)
    return dict(event='estimate', time=t, basis=basis, unit=unit, done=done, rate=rate, total=band(total, done), to_go=band(to_go),
                prior=prior, exists=exists, pending=pending, finished=finished)


def end(t, status=0): return dict(event='end', time=t, status=status)


def write(d, name, lines):
    os.makedirs(os.path.join(d, 'runs'), exist_ok=True)
    with open(os.path.join(d, 'runs', name + '.jsonl'), 'w', encoding='utf-8') as f: f.write(''.join(json.dumps(x) + '\n' for x in lines))


def raises(f):
    try: f()
    except AssertionError: return True
    return False


def q_an_entry_is_its_search_s_records():
    # Replicata: watch.entry of the search tree at 480:14, at now = 3500, with the live processes {77: S}: its runs r1,
    # from 1000 to its end (status 0) at 2000, with estimates at 1100 and 1900, and r2, started at 3000 with pid 77 and
    # no end, with estimates at 3100 and 3400, the last of basis formtree, in nodes, done 700, rate 2, total 5000,
    # to_go 2150, prior 0.5, exists 0.31; and no CPU interval.  Their pending (2026-11-12): 30, 40, none (null), 50.
    # Expectata: the entry holds exactly the fields search, n, order, state, outcome, so_far, to_go, etas, basis, work,
    # odds, runs, statuses, depth, keys, groups, counts, cpu and stale, and each is the records': search tree, n 480,
    # order 14; state running (a run runs) and outcome null; so_far 1500 (r1's 1000 s, then r2's 500 so far); to_go,
    # basis and work (unit, done, rate, total) the last estimate's; etas the four estimates as [time, the search's
    # seconds of running before it, to_go's median, lo, hi]: 100, 900, 1100 and 1400 s of running; odds the last
    # estimate's prior, since 1000 (the search's first start) and [time, exists] of each estimate; runs the counts 2
    # runs, 1 running, 0 frozen, 1 ended, 0 aborted, 0 found; one block of dots, a dot per run in the order they
    # started, "03" in the statuses settled, open, pending, running (ended, aborted, frozen, running), keyed by the
    # target, with those statuses' counts; cpu empty and stale null; pending [time, seconds of running, nodes
    # pending] of each estimate that counts them (dreeves, 2026-11-12: "we used to have number of open nodes as a
    # graph"), [[1100, 100, 30], [1900, 900, 40], [3400, 1400, 50]]; and finished, the same rows of tasks finished
    # (dreeves, that evening: "sure, let's get the count of finished tasks over time"), of the same estimates, which
    # count 4, 9 and 12 of them: [[1100, 100, 4], [1900, 900, 9], [3400, 1400, 12]].  Nothing in it comes from
    # anywhere but the records.
    import watch
    last = estimate(3400, 700, 5000, 2150, exists=0.31, pending=50, finished=12)
    r1 = [start('r1', 'tree', '480:14', 1000, 55), estimate(1100, 100, 4000, 3000, exists=0.49, pending=30, finished=4),
          estimate(1900, 400, 4500, 2500, exists=0.45, pending=40, finished=9), end(2000)]
    r2 = [start('r2', 'tree', '480:14', 3000, 77), estimate(3100, 450, 4800, 2400, exists=0.44), last]
    e = watch.entry(('tree', '480:14'), [r1, r2], {77: 'S'}, 3500, [])
    assert set(e) == {'search', 'n', 'order', 'state', 'outcome', 'so_far', 'to_go', 'etas', 'basis', 'work', 'odds', 'runs', 'statuses',
                      'depth', 'keys', 'groups', 'counts', 'cpu', 'stale', 'pending', 'finished'}, sorted(e)
    assert e['finished'] == [[1100, 100, 4], [1900, 900, 9], [3400, 1400, 12]], e['finished']
    assert (e['search'], e['n'], e['order'], e['state'], e['outcome'], e['so_far'], e['stale'], e['cpu']) == ('tree', 480, 14, 'running', None, 1500, None, []), e
    assert e['to_go'] == last['to_go'] and e['basis'] == 'formtree', e
    assert e['work'] == dict(unit='nodes', done=700, rate=2.0, total=last['total']), e['work']
    assert [row[:2] for row in e['etas']] == [[1100, 100], [1900, 900], [3100, 1100], [3400, 1400]], e['etas']
    assert e['etas'][-1][2:] == [2150, 0.9 * 2150, 1.5 * 2150], e['etas'][-1]
    assert e['odds'] == dict(prior=0.5, since=1000, exists=[[1100, 0.49], [1900, 0.45], [3100, 0.44], [3400, 0.31]]), e['odds']
    assert e['pending'] == [[1100, 100, 30], [1900, 900, 40], [3400, 1400, 50]], e['pending']
    assert e['runs'] == dict(runs=2, running=1, frozen=0, ended=1, aborted=0, found=0), e['runs']
    assert (e['statuses'], e['depth'], e['keys'], e['groups']) == (['settled', 'open', 'pending', 'running'], 0, ['480:14'], ['03']), e
    assert e['counts'] == dict(settled=1, open=0, pending=0, running=1), e['counts']
    json.dumps(e)


def q_a_search_s_state_and_outcome_follow_its_runs():
    # Replicata: watch.entry of searches of one or two runs, each run with an estimate, at now = 5000: (a) two runs
    # ended with status 0 and no found file; (b) the same, both naming a found file of two whole lines and a partial
    # third; (c) the same, naming a found file that does not exist; (d) one run ended with status 0, then one with
    # status 3; (e) one run with no end whose process is stopped (stat T), one ended; (f) one run with no end and no
    # live process, whose last line is early, then one ended with status 0; (g) a run with no end whose process runs,
    # its estimate ten seconds old, and one that found (a found file of one line) and ended; (h) a run that ended
    # with status 1, then one with status -15, then one with status 0: two false starts, then the run that finished.
    # Expectata: (a) ended, outcome none; (b) ended, outcome found, 2 found (each file once, whole lines); (c) ended,
    # outcome none, 0 found; (d) ended, outcome null (the page calls it aborted), 1 ended and 1 aborted; (e) frozen,
    # outcome null; (f) ended, outcome none, 1 aborted; (g) running, outcome found; (h) ended, outcome none.  With
    # nothing found the outcome is the last run's to stop: none if that one ended with status 0 or null, however the
    # runs before it went (2026-11-11: the symmetric-only search of 480:14, which closed its tree in its fourth run,
    # read "aborted" for its three restarts; until then none needed every run to have ended so).  The dots follow the
    # runs: (d) "01", (e) "20", (f) "10", (h) "110".
    import watch
    d = tempfile.mkdtemp(prefix='watch-quals-')
    try:
        two, one = os.path.join(d, 'two'), os.path.join(d, 'one')
        open(two, 'w').write('w1\nw2\npart')
        open(one, 'w').write('w\n')
        run = lambda name, t, pid, close=(), found=None, at=10: [start(name, 'S', '16:4', t, pid, found), estimate(t + at, 5, 50, 100), *close]
        cases = dict(
            a=([run('x', 1000, 1, [end(1500)]), run('y', 2000, 2, [end(2500)])], {}),
            b=([run('x', 1000, 1, [end(1500)], two), run('y', 2000, 2, [end(2500)], two)], {}),
            c=([run('x', 1000, 1, [end(1500)], os.path.join(d, 'none')), run('y', 2000, 2, [end(2500)])], {}),
            d=([run('x', 1000, 1, [end(1500)]), run('y', 2000, 2, [end(2500, 3)])], {}),
            e=([run('x', 1000, 1), run('y', 2000, 2, [end(2500)])], {1: 'T'}),
            f=([run('x', 1000, 1), run('y', 2000, 2, [end(2500)])], {}),
            g=([run('x', 1000, 1, at=3990), run('y', 2000, 2, [end(2500)], one)], {1: 'R+'}),
            h=([run('x', 1000, 1, [end(1500, 1)]), run('y', 2000, 2, [end(2500, -15)]), run('z', 3000, 3, [end(3500)])], {}))
        got = {k: watch.entry(('S', '16:4'), runs, procs, 5000, []) for k, (runs, procs) in cases.items()}
        said = {k: (e['state'], e['outcome'], e['runs']['found'], e['groups']) for k, e in got.items()}
        assert said == dict(a=('ended', 'none', 0, ['00']), b=('ended', 'found', 2, ['00']), c=('ended', 'none', 0, ['00']),
                            d=('ended', None, 0, ['01']), e=('frozen', None, 0, ['20']), f=('ended', 'none', 0, ['10']),
                            g=('running', 'found', 1, ['30']), h=('ended', 'none', 0, ['110'])), said
        assert (got['d']['runs']['ended'], got['d']['runs']['aborted'], got['f']['runs']['aborted']) == (1, 1, 1), (got['d']['runs'], got['f']['runs'])
    finally:
        shutil.rmtree(d)


def q_a_running_search_s_old_estimate_fails_loudly():
    # Replicata: watch.entry of a search whose one run, started at 1000 with no end, has its last estimate at 2000:
    # with its process alive and now 2000 + track.STALE; with now a second later; and, a second later still, with its
    # process gone.
    # Expectata (dreeves, 2026-11-04, of an estimate left standing by a dead or stalled producer: "can we be more
    # anti-postel than that?"): the first gives its entry; the second raises AssertionError (a running search's latest
    # estimate may be at most track.STALE seconds old: the watcher then shows the search's last good entry, marked
    # stale); the third gives its entry again, an aborted search's, whose estimates no one is writing any more.
    import track, watch
    run = [start('x', 'S', '16:4', 1000, 9), estimate(2000, 5, 50, 100)]
    assert watch.entry(('S', '16:4'), [run], {9: 'S'}, 2000 + track.STALE, [])['state'] == 'running'
    assert raises(lambda: watch.entry(('S', '16:4'), [run], {9: 'S'}, 2001 + track.STALE, []))
    assert watch.entry(('S', '16:4'), [run], {}, 2002 + track.STALE, [])['state'] == 'ended'


def q_a_long_history_is_thinned_evenly():
    # Replicata: watch.entry of a search whose one ended run has 1001 estimates, a minute apart from 1060 on, the
    # k-th with done k, exists 1 - k / 2000, 1000 - k pending and k finished.
    # Expectata: etas, the odds' exists, pending and finished each hold at most watch.ETA_POINTS (400) rows, the same estimates' in all:
    # every third estimate from the first, and the last; so the first, the last, and gaps of 3 minutes but for the
    # last's.  The latest estimate's fields (to_go, work) are the last's whatever the thinning.
    import watch
    ests = [estimate(1060 + 60 * k, k, 5000, 100, exists=1 - k / 2000, pending=1000 - k, finished=k) for k in range(1001)]
    e = watch.entry(('S', '16:4'), [[start('x', 'S', '16:4', 1000, 9), *ests, end(70000)]], {}, 80000, [])
    times = [row[0] for row in e['etas']]
    assert len(times) <= watch.ETA_POINTS == 400 and times == [t for t, _ in e['odds']['exists']] == [row[0] for row in e['pending']] == [row[0] for row in e['finished']], len(times)
    assert e['finished'][-1][2] == 1000 and e['finished'][0][2] == 0, (e['finished'][0], e['finished'][-1])
    assert e['pending'][-1][2] == 0 and e['pending'][0][2] == 1000, (e['pending'][0], e['pending'][-1])
    assert times == [1060 + 60 * k for k in list(range(0, 1001, 3)) + [1000]], times[-3:]
    assert e['work']['done'] == 1000 and e['odds']['exists'][-1] == [61060, 0.5], (e['work'], e['odds']['exists'][-1])


def q_a_search_s_cpu_is_its_runs_shares_on_its_running_time():
    # Replicata: watch.cpu_series of the machine's intervals (cpu.py's rows, [t0, t1, idle, {run's name: share}]) for
    # a search whose runs are x and y and whose passes are [1000, 2000] and [3000, 4000]: [1000, 1060] idle 0.2 with
    # x at 0.5; [1060, 1120] idle 0.1 with x at 0.3 and y at 0.4; [1120, 1180] idle 0.9 with z, another search's run,
    # at 0.05; [3000, 3060] idle 0 with y at 1 and z at 0; then the same with watch.CPU_POINTS set to 2 and the rows
    # [1000, 1060] x 0.5, [1060, 1120] x 0.3, [1120, 1180] x 0.1, [1180, 1300] x 0.4 (twice as long), and, after a
    # gap, [3000, 3060] x 1 and [3060, 3120] x 0, each with idle 0.
    # Expectata: first, a row per interval that names a run of the search: [hours of running at its start, at its
    # end, its end's time, the search's share (its runs' summed), other processes' (the rest of the busy share), idle]:
    # [0, 60/3600, 1060, 0.5, 0.3, 0.2], [60/3600, 120/3600, 1120, 0.7, 0.2, 0.1], [1000/3600, 1060/3600, 3060, 1, 0,
    # 0]: the interval that names only z is no row of this search.  Second, with six rows and at most 2 points, rows
    # are merged three at a time, their shares weighted by their durations, but never across a gap: [0, 180/3600, 1180,
    # 0.3, 0.7, 0], [180/3600, 300/3600, 1300, 0.4, 0.6, 0], [1000/3600, 1120/3600, 3120, 0.5, 0.5, 0].
    import watch
    passes, near = [[1000, 2000], [3000, 4000]], lambda a, b: all(abs(x - y) < 1e-4 for x, y in zip(a, b)) and len(a) == len(b)
    rows = [[1000, 1060, 0.2, {'x': 0.5}], [1060, 1120, 0.1, {'x': 0.3, 'y': 0.4}], [1120, 1180, 0.9, {'z': 0.05}], [3000, 3060, 0.0, {'y': 1.0, 'z': 0.0}]]
    got = watch.cpu_series(rows, passes, {'x', 'y'})
    want = [[0, 60 / 3600, 1060, 0.5, 0.3, 0.2], [60 / 3600, 120 / 3600, 1120, 0.7, 0.2, 0.1], [1000 / 3600, 1060 / 3600, 3060, 1, 0, 0]]
    assert len(got) == 3 and all(near(g, w) for g, w in zip(got, want)), got
    points = watch.CPU_POINTS
    watch.CPU_POINTS = 2
    try:
        rows = [[1000, 1060, 0, {'x': 0.5}], [1060, 1120, 0, {'x': 0.3}], [1120, 1180, 0, {'x': 0.1}], [1180, 1300, 0, {'x': 0.4}],
                [3000, 3060, 0, {'x': 1.0}], [3060, 3120, 0, {'x': 0.0}]]
        got = watch.cpu_series(rows, passes, {'x'})
    finally:
        watch.CPU_POINTS = points
    want = [[0, 180 / 3600, 1180, 0.3, 0.7, 0], [180 / 3600, 300 / 3600, 1300, 0.4, 0.6, 0], [1000 / 3600, 1120 / 3600, 3120, 0.5, 0.5, 0]]
    assert len(got) == 3 and all(near(g, w) for g, w in zip(got, want)), got


def q_a_snapshot_lists_each_search_that_has_an_estimate():
    # Replicata: a temporary directory's runs/: of the search tilt at 16:4, an ended run with an estimate; of tree at
    # 16:4, an ended run with an estimate; of tilt at 32:5, a run with no end, a live process (this qual's own) and an
    # estimate as old as now; of bare at 16:4, an ended run with no estimate (its estimator wrote none); of broken at
    # 16:4, an ended run one of whose estimates has its band out of order.  watch.snapshot there, with no CPU file and
    # nothing kept; then again after the tilt 16:4 record gains a line that is no line of a record, the first
    # snapshot's entries kept.
    # Expectata: the first lists three entries, tilt 16:4, tilt 32:5 and tree 16:4, in that order (by label, then
    # target), none stale; bare is not listed (a search shows from its first estimate), nor broken (its record does
    # not hold to the record's form: the watcher reports it and goes on).  The second lists the same three: tilt 16:4
    # as it was in the first, marked stale with the first snapshot's time; the two others fresh, at the second's.
    import watch
    d = tempfile.mkdtemp(prefix='watch-quals-')
    try:
        now = time.time()
        write(d, 'a', [start('a', 'tilt', '16:4', now - 500, 11), estimate(now - 400, 5, 50, 100), end(now - 300)])
        write(d, 'b', [start('b', 'tree', '16:4', now - 500, 12), estimate(now - 400, 5, 50, 100), end(now - 300)])
        write(d, 'c', [start('c', 'tilt', '32:5', now - 500, os.getpid()), estimate(now - 1, 5, 50, 100)])
        write(d, 'e', [start('e', 'bare', '16:4', now - 500, 13), end(now - 300)])
        write(d, 'f', [start('f', 'broken', '16:4', now - 500, 14), dict(estimate(now - 400, 5, 50, 100), to_go=dict(median=1.0, lo=2.0, hi=3.0)), end(now - 300)])
        runs, cpu, kept = os.path.join(d, 'runs'), os.path.join(d, 'runs', 'cpu', 'intervals.jsonl'), {}
        import track
        first = watch.snapshot(runs, cpu, track.processes(), now, kept)
        assert [(e['search'], e['n'], e['order'], e['stale']) for e in first] == [('tilt', 16, 4, None), ('tilt', 32, 5, None), ('tree', 16, 4, None)], first
        with open(os.path.join(runs, 'a.jsonl'), 'a') as f: f.write(json.dumps(dict(event='eta', time=now, median=1, lo=1, hi=1)) + '\n')
        second = watch.snapshot(runs, cpu, track.processes(), now + 60, kept)
        assert [(e['search'], e['n'], e['stale']) for e in second] == [('tilt', 16, int(now)), ('tilt', 32, None), ('tree', 16, None)], second
        assert dict(second[0], stale=None) == first[0] and second[2] == first[2], (second[0], first[0])
    finally:
        shutil.rmtree(d)


def sandbox():
    d = tempfile.mkdtemp(prefix='watch-quals-')
    for sub in ('searchwatch', 'runs', 'pagedata'): os.mkdir(os.path.join(d, sub))
    for name in ('track.py', 'watch.py', 'cpu.py'): shutil.copy(os.path.join(HERE, 'searchwatch', name), os.path.join(d, 'searchwatch'))
    open(os.path.join(d, 'pagedata', 'progress-earlier.json'), 'w').write('[]\n')       # no earlier search, unless a qual writes some
    return d


def data(d):
    text = open(os.path.join(d, 'pagedata', 'progress.js'), encoding='utf-8').read()
    assert text.startswith('progressData(') and text.endswith(');\n'), text[:80]
    return json.loads(text.removeprefix('progressData(').removesuffix(');\n'))


def q_the_watcher_writes_the_data_file_when_a_search_changes():
    # Replicata: a sandbox with a copy of the watcher and, in its runs/, an ended run of the search tilt at 16:4 with
    # an estimate, and its CPU intervals' file with one interval naming that run.  python3 -B searchwatch/watch.py
    # there, once; then once more, a second later; then, after the record of a second run of that search is written (a
    # live process's, this qual's, with an estimate as old as now), once more.
    # Expectata: the first writes pagedata/progress.js, one call progressData({"made", "runs"}); with made the time it
    # ran, in whole seconds, and runs the one entry, tilt 16 4, ended, its cpu the interval's one row.  The second
    # leaves the file as it was, byte for byte (nothing of its runs changed: dreeves, 2026-11-09, "i guess it could be
    # a little smarter and not update a file that's in version control with a new as-of time that isn't meaningful").
    # The third rewrites it: made later, the entry now running with 2 runs.
    d = sandbox()
    try:
        now = time.time()
        write(d, 'a', [start('a', 'tilt', '16:4', now - 500, 11), estimate(now - 400, 5, 50, 100), end(now - 300)])
        os.mkdir(os.path.join(d, 'runs', 'cpu'))
        open(os.path.join(d, 'runs', 'cpu', 'intervals.jsonl'), 'w').write(json.dumps([now - 460, now - 400, 0.25, {'a': 0.5}]) + '\n')
        once = lambda: subprocess.run([PY, '-B', os.path.join('searchwatch', 'watch.py')], cwd=d, capture_output=True, text=True, timeout=60)
        p = once()
        assert p.returncode == 0, p.stderr
        first, text = data(d), open(os.path.join(d, 'pagedata', 'progress.js')).read()
        assert set(first) == {'made', 'runs'} and type(first['made']) is int and abs(first['made'] - now) < 30, first
        [e] = first['runs']
        assert (e['search'], e['n'], e['order'], e['state'], e['runs']['runs']) == ('tilt', 16, 4, 'ended', 1), e
        assert len(e['cpu']) == 1 and e['cpu'][0][3:] == [0.5, 0.25, 0.25], e['cpu']
        time.sleep(1.1)
        assert once().returncode == 0 and open(os.path.join(d, 'pagedata', 'progress.js')).read() == text
        write(d, 'b', [start('b', 'tilt', '16:4', time.time() - 5, os.getpid()), estimate(time.time(), 6, 50, 100)])
        assert once().returncode == 0
        third = data(d)
        assert third['made'] > first['made'] and [(e['state'], e['runs']['runs']) for e in third['runs']] == [('running', 2)], third
    finally:
        shutil.rmtree(d)


def q_one_watcher_at_a_time_keeps_the_file_current():
    # Replicata: a sandbox as above with one ended run's record; the watcher there with --watch, its pause between
    # snapshots set to 0.3 s (watch.REFRESH); once the data file is written, a second watcher started the same way;
    # then the record of a run of another search, tree at 16:4, written (ended, with an estimate).
    # Expectata: the second watcher exits nonzero at once (one watcher at a time: a lock in runs/), and the first goes
    # on: within 10 s the data file lists both searches.
    d, w = sandbox(), None
    try:
        now = time.time()
        write(d, 'a', [start('a', 'tilt', '16:4', now - 500, 11), estimate(now - 400, 5, 50, 100), end(now - 300)])
        code = "import sys, watch; watch.REFRESH = 0.3; watch.main(['--watch'])"
        env = dict(os.environ, PYTHONPATH='searchwatch')
        w = subprocess.Popen([PY, '-B', '-c', code], cwd=d, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        js = os.path.join(d, 'pagedata', 'progress.js')
        t0 = time.time()
        while not os.path.exists(js):
            assert time.time() - t0 < 20 and w.poll() is None, 'no data file'
            time.sleep(0.05)
        second = subprocess.run([PY, '-B', '-c', code], cwd=d, env=env, capture_output=True, text=True, timeout=20)
        assert second.returncode != 0 and w.poll() is None, (second.returncode, second.stderr)
        write(d, 'b', [start('b', 'tree', '16:4', now - 500, 12), estimate(now - 400, 5, 50, 100), end(now - 300)])
        t0 = time.time()
        while [e['search'] for e in data(d)['runs']] != ['tilt', 'tree']:
            assert time.time() - t0 < 10 and w.poll() is None, data(d)
            time.sleep(0.1)
    finally:
        if w is not None:
            w.kill()
            w.wait()
        shutil.rmtree(d)


def q_the_earlier_searches_follow_the_live_ones():
    # Replicata: a sandbox with an ended run's record of the search tilt at 16:4, and in its pagedata/ the file
    # progress-earlier.json holding two made-up entries, in the form the watcher writes (searches of before 2026-11-11,
    # frozen); the watcher there, once.  Then the same sandbox without progress-earlier.json, and without the data
    # file, the watcher once more.
    # Expectata (dreeves, 2026-11-11: "I don't want to spend a lot of effort converting old searches"): the data file's
    # runs are the live search's entry, then the two earlier entries exactly as the file holds them: the watcher adds
    # them to every snapshot and makes nothing of them.  Without the file the watcher exits nonzero and writes no
    # data file: the earlier searches are part of the page's data, and a snapshot without them would drop them.
    d = sandbox()
    try:
        now = time.time()
        write(d, 'a', [start('a', 'tilt', '16:4', now - 500, 11), estimate(now - 400, 5, 50, 100), end(now - 300)])
        earlier = [dict(search='old.py', n=288, order=10, state='ended', outcome='none', anything=[1, 2, {'x': None}]),
                   dict(search='older.py', n=64, order=7, state='ended', outcome=None)]
        json.dump(earlier, open(os.path.join(d, 'pagedata', 'progress-earlier.json'), 'w'))
        once = lambda: subprocess.run([PY, '-B', os.path.join('searchwatch', 'watch.py')], cwd=d, capture_output=True, text=True, timeout=60)
        p = once()
        assert p.returncode == 0, p.stderr
        runs = data(d)['runs']
        assert [e['search'] for e in runs] == ['tilt', 'old.py', 'older.py'] and runs[1:] == earlier, runs
        os.remove(os.path.join(d, 'pagedata', 'progress-earlier.json'))
        os.remove(os.path.join(d, 'pagedata', 'progress.js'))
        p = once()
        assert p.returncode != 0 and not os.path.exists(os.path.join(d, 'pagedata', 'progress.js')), (p.returncode, p.stderr)
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
