"""Quals for cpu.py, the machine's CPU use as the progress page's CPU charts show it (dreeves, 2026-11-07: "could we get
a nice CPU usage graph on the search page? similar to what activity monitor shows. three colors: one for the search, one
for all other processes on the machine, and one for idle, if any"; "maybe aligned with the ETA graph").
    python3 -B quals/quals_cpu.py [qual ...]"""
import sys
sys.dont_write_bytecode = True
import os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'searchwatch'))   # cpu.py's directory since 2026-11-10 ([REF]); the root until then


def cpu():
    import cpu as module
    return module


def raises(f):
    try:
        f()
    except AssertionError:
        return True
    return False


def q_cputime_reads_ps_s_formats():
    # Replicata: ps's time column as macOS prints it, minutes past 60 not carried into hours ("569:30.85"), and the
    # longer forms with hours and days.  Expectata: seconds, exactly; anything else refused.
    c = cpu()
    assert c.cputime('569:30.85') == 569 * 60 + 30.85
    assert c.cputime('0:00.07') == 0.07
    assert c.cputime('1:02:03.04') == 3600 + 120 + 3.04
    assert c.cputime('2-01:02:03.00') == 2 * 86400 + 3600 + 120 + 3
    assert all(raises(lambda s=s: c.cputime(s)) for s in ('', '12', '1:2:3:4:5', 'a:00.00', '-1:00.00'))


def q_interval_splits_the_capacity():
    # Replicata: two made-up samples a minute apart on 10 cores (HZ ticks a second each): 600 HZ ticks, 150 HZ of them idle;
    # one tracked run's process group, its pid 7 up from 100 to 280 CPU seconds, pid 8 new at 60, pid 9 gone.
    # Expectata: idle 1500/6000; the run's share (180 + 60) CPU seconds of the 600 the cores had; other processes the
    # rest; the times the samples'.
    c = cpu()
    hz = c.HZ
    a = dict(time=1000.0, busy=0, idle=0, groups={'run': {7: 100.0, 9: 50.0}})
    b = dict(time=1060.0, busy=450 * hz, idle=150 * hz, groups={'run': {7: 280.0, 8: 60.0}})
    t0, t1, idle, search = c.interval(a, b)
    assert (t0, t1) == (1000.0, 1060.0) and abs(idle - 0.25) < 1e-12, (t0, t1, idle)
    assert abs(search['run'] - 240 / 600) < 1e-12, search


def q_interval_refuses_a_search_above_the_busy_share():
    # Replicata: samples whose run used more CPU than the cores were busy, beyond the skew between reading the ticks
    # and reading ps.  Expectata: refused (anti-Postel), as are negative ticks and a process whose time went down.
    c = cpu()
    hz = c.HZ
    a = dict(time=0.0, busy=0, idle=0, groups={'run': {7: 0.0}})
    over = dict(time=60.0, busy=100 * hz // 100, idle=500 * hz // 100, groups={'run': {7: 120.0}})
    assert raises(lambda: c.interval(a, over))
    back = dict(time=60.0, busy=500 * hz // 100, idle=100 * hz // 100, groups={'run': {7: -1.0}})
    assert raises(lambda: c.interval(a, back))
    neg = dict(time=60.0, busy=-1, idle=600 * hz // 100, groups={'run': {}})
    assert raises(lambda: c.interval(a, neg))


def q_the_machine_s_ticks_add_up():
    # Replicata: this machine, two samples a second apart, no tracked run.  Expectata: the cores' ticks over the second are
    # about HZ per core (within 20%: the sleep is not exact), and idle a fraction in [0, 1].
    c = cpu()
    a = c.sample({})
    time.sleep(1)
    b = c.sample({})
    t0, t1, idle, search = c.interval(a, b)
    cores = os.cpu_count()
    total = (b['busy'] - a['busy']) + (b['idle'] - a['idle'])
    assert abs(total / (c.HZ * cores * (t1 - t0)) - 1) < 0.2, (total, cores, t1 - t0)
    assert 0 <= idle <= 1 and search == {}, (idle, search)


def q_a_sample_follows_each_run_s_process_group():
    # Replicata: this process as a tracked run's pid, and a pid with no process.  Expectata: the first's group holds this
    # process, with its CPU seconds; the second is left out (its run not running: a gap in its chart, not 0%).
    c = cpu()
    s = c.sample({'me': os.getpid(), 'gone': 999999})
    assert os.getpid() in s['groups']['me'] and s['groups']['me'][os.getpid()] >= 0 and 'gone' not in s['groups'], s['groups']


def q_groups_are_the_tracked_runs_not_ended():
    # Replicata: cpu.groups of a made-up root: runs/r0.jsonl (a start line and no end), runs/r1.jsonl (a start and an
    # end), runs/r2.jsonl (a start, then a half-written line), and runs/cpu/intervals.jsonl, not a record.
    # Expectata: {name: pid} of the records with no end line, r0's and r2's, each from its start line.
    import json, tempfile, shutil
    c = cpu()
    d = tempfile.mkdtemp(prefix='cpu-quals-')
    try:
        os.makedirs(os.path.join(d, 'runs', 'cpu'))
        start = lambda name, pid: json.dumps(dict(event='start', name=name, pid=pid, target='768:12', time=1000)) + '\n'
        open(os.path.join(d, 'runs', 'r0.jsonl'), 'w').write(start('r0', 300))
        open(os.path.join(d, 'runs', 'r1.jsonl'), 'w').write(start('r1', 301) + json.dumps(dict(event='end', time=2000, status=0)) + '\n')
        open(os.path.join(d, 'runs', 'r2.jsonl'), 'w').write(start('r2', 302) + '{"event": "eta"')
        open(os.path.join(d, 'runs', 'cpu', 'intervals.jsonl'), 'w').write('[1,2,0.5,{}]\n')
        assert c.groups(d) == {'r0': 300, 'r2': 302}, c.groups(d)
    finally:
        shutil.rmtree(d)


def q_the_sampler_appends_intervals_and_survives_a_failure():
    # Replicata: cpu.watch of a made-up root with cpu.sample made up (two samples, a failure, two more) and time.sleep
    # stopping it at its fifth call.  Expectata: the file holds the first two samples' interval and the last two's, none
    # across the failure (the sample after it starts afresh: a gap); the failure reported, not raised.
    import json, tempfile, shutil, contextlib, io
    c = cpu()
    d = tempfile.mkdtemp(prefix='cpu-quals-')
    path, real_sample, real_sleep = os.path.join(d, 'runs', 'cpu', 'intervals.jsonl'), c.sample, c.time.sleep
    hz = c.HZ
    made = iter([dict(time=0.0, busy=0, idle=0, groups={}), dict(time=60.0, busy=300 * hz, idle=300 * hz, groups={}), None,
                 dict(time=180.0, busy=600 * hz, idle=600 * hz, groups={}), dict(time=240.0, busy=900 * hz, idle=900 * hz, groups={})])
    class Stop(Exception): pass
    calls = []
    def sample(groups):
        s = next(made)
        assert s is not None, 'made-up failure'
        return s
    def sleep(s):
        calls.append(s)
        if len(calls) == 5: raise Stop
    try:
        os.makedirs(os.path.join(d, 'runs'))
        c.sample, c.time.sleep = sample, sleep
        with contextlib.redirect_stderr(io.StringIO()) as err:
            try:
                c.watch(d, path, 60)
            except Stop:
                pass
        assert [json.loads(line) for line in open(path)] == [[0.0, 60.0, 0.5, {}], [180.0, 240.0, 0.5, {}]], open(path).read()
        assert calls == [60] * 5 and 'the CPU sample failed' in err.getvalue(), (calls, err.getvalue()[:200])
    finally:
        c.sample, c.time.sleep = real_sample, real_sleep
        shutil.rmtree(d)


def q_one_sampler_at_a_time():
    # Replicata: cpu.watch of a made-up root while another holds its lock.  Expectata: refused at once (BlockingIOError).
    import tempfile, shutil, fcntl
    c = cpu()
    d = tempfile.mkdtemp(prefix='cpu-quals-')
    try:
        path = os.path.join(d, 'runs', 'cpu', 'intervals.jsonl')
        os.makedirs(os.path.dirname(path))
        held = open(os.path.join(os.path.dirname(path), 'lock'), 'w')
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            c.watch(d, path, 60)
        except BlockingIOError:
            pass
        else:
            raise AssertionError('a second sampler ran')
    finally:
        shutil.rmtree(d)


if __name__ == '__main__':
    names = sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]
    bad = 0
    for name in names:
        try:
            globals()[name]()
            print('PASSED', name, flush=True)
        except Exception as e:
            bad += 1
            print('FAILED', name, type(e).__name__, str(e)[:200], flush=True)
    print(f'{len(names) - bad} of {len(names)} passed')
