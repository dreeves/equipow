#!/usr/bin/env python3
"""Quals for track.py, the launcher every search runs under (2026-10-28; dreeves: "can we rearchitect things so that
always happens easily and automatically?", then "those names are fine, go ahead").  Run from the repo:
    python3 -B quals/quals_track.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Each copies track.py into a temporary directory and
runs it there, so that its records go to that directory's runs/.

Spec change, 2026-11-11 (dreeves, of whether different searches on one cell should show separately: "sounds like
obviously yes"; of the page's bar and probability graph, which one search alone had: "the search progress code seems
like a shitshow; can you revamp it? ... anti-magic anti-magic anti-magic"): a run is launched with the label of its
search and with its estimator, both required, `track.py run NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- COMMAND ...`
and `track.py adopt NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- PID`.  Every launch below names the search S and
the sandbox's estimator (EST), which appends one estimate each time the tracker runs it; so a record holds estimates
between its start and its end, and the quals that read a record's two lines read its first and its last.  The start
names the search and the estimator and no longer a program (the page showed a search under its first run's program).

Spec change (Opus 5.5, 2026-11-12; dreeves: "we used to have number of open nodes as a graph. is there a reason we
can't have that on the currently running 480:14 search?"): an estimate also states pending, the number of pieces of
work its search has named and not yet finished (a form tree's nodes with no verdict yet), or null for a search
that has no such count; the page graphs it.

Spec change (Opus 5.5, 2026-11-12, evening; dreeves: "sure, let's get the count of finished tasks over time"): an
estimate also states finished, the number of pieces of work its search has finished (a form tree's tasks with a
verdict), or null for a search that has no such count; the page graphs it under pending.

Spec change (Fable 5.2, 2026-11-13, night; dreeves, of a finished search whose box kept its last periodic estimate, "0.5 →
0.25" and a projected total above its count: "sure, that sounds cleaner to get exact counts and probability 0 when we
completed a proof"): the tracker runs the estimator once more when the run's process has ended, before it writes the
end, so that a record's last estimate is of the search as it ended; and a run with no end goes on while its process
or, that gone, its tracker lives (the tracker is then taking that last estimate), so that it reads running, its span to
now, until its end is written.  Until then: an estimate at the start and every period while the run went, and a run
whose process was gone with no end read aborted, its span to its last line, whether or not its tracker lived.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, shutil, signal, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PY = sys.executable
TRACK = os.path.join('searchwatch', 'track.py')     # the sandbox's copy, as a command names it from the sandbox
EST = 'est.py'                                      # the sandbox's estimator, as a launch names it from the sandbox
# what an estimator does: appends one estimate to the record TRACK_RECORD names (opened to append, never created)
ESTIMATE = dict(event='estimate', basis='lindy', unit='seconds', done=1.0, rate=1.0, total=dict(median=2.0, lo=1.5, hi=10.0),
                to_go=dict(median=1.0, lo=0.5, hi=9.0), prior=0.5, exists=0.5, pending=None, finished=None)
ESTIMATOR = f'''import json, os, time
fd = os.open(os.environ['TRACK_RECORD'], os.O_WRONLY | os.O_APPEND)
os.write(fd, (json.dumps(dict({ESTIMATE!r}, time=time.time())) + '\\n').encode())
os.close(fd)
'''
IMPORTS = dict(os.environ, PYTHONPATH='searchwatch')   # for a -c script run in the sandbox that imports its track.py


def sandbox():
    d = tempfile.mkdtemp(prefix='track-quals-')
    # track.py keeps its records in runs/ of the directory above its own (the repository's root; in searchwatch/ since
    # 2026-11-10, [REF]), so the copy goes into a searchwatch/ of the sandbox and its records into the sandbox's runs/.
    os.mkdir(os.path.join(d, 'searchwatch'))
    shutil.copy(os.path.join(HERE, 'searchwatch', 'track.py'), os.path.join(d, 'searchwatch'))
    open(os.path.join(d, EST), 'w').write(ESTIMATOR)
    return d


def record(d, name):
    """The record's lines, as JSON."""
    return [json.loads(x) for x in open(os.path.join(d, 'runs', name + '.jsonl'), encoding='utf-8').read().splitlines()]


def until(test, seconds):
    """Waits until test() is true, at most seconds (asserted)."""
    t0 = time.time()
    while not test():
        assert time.time() - t0 < seconds, 'timed out'
        time.sleep(0.05)


def gone(pid):
    """Whether no live process has this pid (ps lists none, or a zombie)."""
    out = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    return out == '' or out.startswith('Z')


def q_run_writes_its_start_and_end():
    # Replicata: track.py run q1 S 16:4 --found F est.py -- python3 -c "import sys; sys.exit(3)", in a temporary
    # directory.
    # Expectata: track.py exits 3, its command's status; runs/q1.jsonl holds the start (event start, name q1, search
    # S, target 16:4, the estimator and the command as a shell would write them, found F's absolute path, adopted
    # false, the command's pid and track.py's own as tracker, a time, and no other field), then the estimator's
    # estimate, as it wrote it (one at least: the tracker runs it when the run starts and lets it finish), and the end
    # (event end, status 3, a time no earlier than the start's).  (2026-11-11: the search, the estimator and the
    # estimate; no program.)
    d = sandbox()
    try:
        cmd = [PY, '-c', 'import sys; sys.exit(3)']
        p = subprocess.run([PY, '-B', TRACK, 'run', 'q1', 'S', '16:4', '--found', 'F', EST, '--', *cmd], cwd=d)
        assert p.returncode == 3, p.returncode
        start, *estimates, end = record(d, 'q1')
        assert {k: v for k, v in start.items() if k not in ('pid', 'tracker', 'time', 'cwd')} == dict(
            event='start', name='q1', search='S', target='16:4', estimator=EST,
            command=f"{PY} -c 'import sys; sys.exit(3)'", found=os.path.join(os.path.realpath(d), 'F'), adopted=False), start
        assert start['pid'] > 0 and start['tracker'] > 0 and start['pid'] != start['tracker'], start
        assert estimates and all(dict(e, time=0) == dict(ESTIMATE, time=0) for e in estimates), estimates
        assert start['time'] <= estimates[0]['time'] <= estimates[-1]['time'] <= end['time'], (start, estimates, end)
        assert end['event'] == 'end' and end['status'] == 3 and end['time'] >= start['time'], end
    finally:
        shutil.rmtree(d)


def q_run_names_its_search_and_its_estimator():
    # Replicata: track.py run q2 form-tree.2 16:4 est.py --prior 0.5 -- python3 -B job.py, job.py exiting 0, in a
    # temporary directory; est.py there writes its arguments to the file args before its estimate.
    # Expectata (2026-11-11, in place of the start's program, the command's script): the start's search is
    # form-tree.2, its estimator "est.py --prior 0.5", as a shell would write it, and its found null; the tracker ran
    # the estimator with those arguments (args holds --prior 0.5); the end's status 0.
    d = sandbox()
    try:
        open(os.path.join(d, 'job.py'), 'w').write('pass\n')
        open(os.path.join(d, EST), 'w').write("import sys\nopen('args', 'w').write(' '.join(sys.argv[1:]))\n" + ESTIMATOR)
        assert subprocess.run([PY, '-B', TRACK, 'run', 'q2', 'form-tree.2', '16:4', EST, '--prior', '0.5', '--', PY, '-B', 'job.py'],
                              cwd=d).returncode == 0
        start, *_, end = record(d, 'q2')
        assert (start['search'], start['estimator'], start['found'], end['status']) == ('form-tree.2', 'est.py --prior 0.5', None, 0), (start, end)
        assert open(os.path.join(d, 'args')).read() == '--prior 0.5'
    finally:
        shutil.rmtree(d)


ETA = '''import json, os, sys, time
path = os.environ['TRACK_RECORD']
until = time.time() + 20                  # the record is linked into place just after this process is started
while not os.path.exists(path):
    assert time.time() < until, path
    time.sleep(0.01)
fd = os.open(path, os.O_WRONLY | os.O_APPEND)      # appended to, never created
os.write(fd, (json.dumps(dict(event='estimate', time=time.time(), basis='own', unit='seconds', done=60.0, rate=1.0,
                              total=dict(median=120.0, lo=66.0, hi=660.0), to_go=dict(median=60.0, lo=6.0, hi=600.0),
                              prior=0.5, exists=0.5, pending=7, finished=3)) + '\\n').encode())
os.close(fd)
print(path, flush=True)
'''


def q_run_names_its_record_to_its_command():
    # Replicata: track.py run q8 S 16:4 est.py -- python3 -c ETA, in a temporary directory: ETA waits for the record
    # named by the environment variable TRACK_RECORD, appends to it (opened without creating it) an estimate of basis
    # "own", as a search may append an estimate of its own, and prints the record's name.
    # Expectata (the coordinator, 2026-10-31: track.py exports its record path to the command through an environment
    # variable, so that a search may append lines; 2026-11-11: an estimate, in place of the eta line the watcher
    # preferred to Gott's rule): the name printed is runs/q8.jsonl's absolute path; the record holds the start, the
    # command's line as it wrote it among the estimator's, and the end, with status 0, in that order.
    d = sandbox()
    try:
        p = subprocess.run([PY, '-B', TRACK, 'run', 'q8', 'S', '16:4', EST, '--', PY, '-c', ETA], cwd=d, capture_output=True,
                           text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        assert p.stdout.strip() == os.path.join(os.path.realpath(d), 'runs', 'q8.jsonl'), p.stdout
        start, *between, end = record(d, 'q8')
        assert (start['event'], end['event'], end['status']) == ('start', 'end', 0), (start, end)
        [eta] = [x for x in between if x['basis'] == 'own']
        assert (eta['event'], eta['to_go']) == ('estimate', dict(median=60.0, lo=6.0, hi=600.0)), eta
        assert start['time'] <= eta['time'] <= end['time'], (start, eta, end)
    finally:
        shutil.rmtree(d)


def q_run_passes_sigterm_to_its_command():
    # Replicata: track.py run q3 16:4 -- python3 -c "import time; time.sleep(60)"; once its start is written,
    # SIGTERM to track.py.
    # Expectata: the command gets the signal and ends; the record's end says status -15 (SIGTERM); the command's
    # process is gone.
    d = sandbox()
    try:
        tr = subprocess.Popen([PY, '-B', TRACK, 'run', 'q3', 'S', '16:4', EST, '--', PY, '-c', 'import time; time.sleep(60)'], cwd=d)
        until(lambda: os.path.exists(os.path.join(d, 'runs', 'q3.jsonl')), 20)
        tr.send_signal(signal.SIGTERM)
        tr.wait(timeout=30)
        start, *_, end = record(d, 'q3')
        assert end['status'] == -signal.SIGTERM, end
        assert gone(start['pid']), start
    finally:
        shutil.rmtree(d)


def q_adopt_writes_the_end_when_the_process_is_gone():
    # Replicata: a process sleeping 2 s, started here; track.py adopt q4 S 16:4 --found W est.py -- PID; the sleeper
    # reaped here once it exits.
    # Expectata: the start names the sleeper's pid, track.py's own as tracker, adopted true, found W's absolute path and
    # the sleeper's command as ps prints it, and as its time the sleeper's own start (ps's start time, to the second:
    # the run began then, not when track.py adopted it); track.py exits 0 after the sleeper is gone, its end's status
    # null (an adopted process's status is not track.py's to read).
    d = sandbox()
    try:
        s = subprocess.Popen([PY, '-c', 'import time; print("ready", flush=True); time.sleep(3)'],
                             stdout=subprocess.PIPE, text=True)
        assert s.stdout.readline() == 'ready\n'           # inspect the interpreter after its launcher has exec'd
        ps = subprocess.run(['ps', '-o', 'command=', '-p', str(s.pid)], capture_output=True, text=True).stdout.strip()
        began = time.mktime(time.strptime(subprocess.run(['ps', '-o', 'lstart=', '-p', str(s.pid)], capture_output=True,
                                                         text=True).stdout.strip(), '%a %b %d %H:%M:%S %Y'))
        time.sleep(1.5)
        tr = subprocess.Popen([PY, '-B', TRACK, 'adopt', 'q4', 'S', '16:4', '--found', 'W', EST, '--', str(s.pid)], cwd=d)
        s.wait()
        s.stdout.close()
        assert tr.wait(timeout=60) == 0
        start, *_, end = record(d, 'q4')
        assert (start['pid'], start['tracker'], start['adopted'], start['found'], start['command']) == (
            s.pid, tr.pid, True, os.path.join(os.path.realpath(d), 'W'), ps), start
        assert end['event'] == 'end' and end['status'] is None and end['time'] >= start['time'], end
        assert start['time'] == began, (start['time'], began)
    finally:
        shutil.rmtree(d)


def q_refuses_a_name_used_before_a_bad_target_and_a_dead_pid():
    # Replicata: track.py run q5 S 16:4 est.py -- python3 -c pass, twice; track.py run q6 S 16 est.py -- ...;
    # track.py adopt q7 S 16:4 est.py -- with the pid of a process already reaped.
    # Expectata: the first run ends with status 0; the second exits nonzero, naming q5, and leaves q5's record as it
    # was; the bad target and the dead pid each exit nonzero and write no record.
    d = sandbox()
    try:
        cmd = [PY, '-B', TRACK, 'run', 'q5', 'S', '16:4', EST, '--', PY, '-c', 'pass']
        assert subprocess.run(cmd, cwd=d).returncode == 0
        before = record(d, 'q5')
        again = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
        assert again.returncode != 0 and 'q5' in again.stderr, again
        assert record(d, 'q5') == before and before[-1]['event'] == 'end'
        bad = subprocess.run([PY, '-B', TRACK, 'run', 'q6', 'S', '16', EST, '--', PY, '-c', 'pass'], cwd=d, capture_output=True, text=True)
        assert bad.returncode != 0 and not os.path.exists(os.path.join(d, 'runs', 'q6.jsonl')), bad
        s = subprocess.Popen([PY, '-c', 'pass'])
        s.wait()
        dead = subprocess.run([PY, '-B', TRACK, 'adopt', 'q7', 'S', '16:4', EST, '--', str(s.pid)], cwd=d, capture_output=True, text=True)
        assert dead.returncode != 0 and not os.path.exists(os.path.join(d, 'runs', 'q7.jsonl')), dead
    finally:
        shutil.rmtree(d)


def q_refusal_never_launches_the_command():
    # Replicata: rejected names and targets, and (2026-11-11) a rejected search label and an estimator that is no
    # file, and two concurrent launchers using the same fresh name; each command appends to a marker. Expectata:
    # rejected commands append nothing and leave no record; exactly one concurrent command starts.
    d = sandbox()
    try:
        cmd = [PY, '-c', "open('launched', 'a').write('x'); import time; time.sleep(.1)"]
        base = [PY, '-B', TRACK, 'run']
        assert subprocess.run([*base, 'used', 'S', '16:4', EST, '--', PY, '-c', 'pass'], cwd=d).returncode == 0
        for name, search, target, estimator in [('used', 'S', '16:4', EST), ('bad', 'S', '16', EST), ('bad/name', 'S', '16:4', EST),
                                                ('label', 'a b', '16:4', EST), ('noest', 'S', '16:4', 'no-such-estimator.py')]:
            p = subprocess.run([*base, name, search, target, estimator, '--', *cmd], cwd=d, capture_output=True, timeout=10)
            assert p.returncode != 0
        time.sleep(.3)
        assert sorted(os.listdir(os.path.join(d, 'runs'))) == ['used.jsonl'], os.listdir(os.path.join(d, 'runs'))
        assert not os.path.exists(os.path.join(d, 'launched')), 'a rejected command ran'
        contenders = [subprocess.Popen([*base, 'race', 'S', '16:4', EST, '--', *cmd], cwd=d,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
        codes = [p.wait(timeout=10) for p in contenders]
        assert codes.count(0) == 1 and open(os.path.join(d, 'launched')).read() == 'x', codes
    finally:
        shutil.rmtree(d)


FAMILY = '''import os, subprocess, sys, time
g = subprocess.Popen([sys.executable, '-c', 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(60)'], stdout=subprocess.PIPE, text=True)
assert g.stdout.readline() == 'ready\\n'
open('family', 'w').write(str(g.pid))
open('parent', 'w').write(str(os.getpid()))
time.sleep(float(sys.argv[1]))
raise SystemExit(int(sys.argv[2]))
'''


def q_owned_descendants_end_on_exit_and_signal():
    # Replicata: a command leaves a TERM-ignoring grandchild, then exits 0, exits 3, or waits while its tracker gets
    # TERM twice. Expectata: the child and grandchild are gone before the tracker exits; its end records the outcome.
    for delay, code, cancel in [('0', 0, False), ('0', 3, False), ('60', -15, True)]:
        d, tr, grand = sandbox(), None, None
        try:
            open(os.path.join(d, 'family.py'), 'w').write(FAMILY)
            tr = subprocess.Popen([PY, '-B', TRACK, 'run', 'family', 'S', '16:4', EST, '--', PY, 'family.py', delay,
                                   str(max(code, 0))], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            marker = os.path.join(d, 'family')
            until(lambda: os.path.exists(marker) and os.path.getsize(marker) > 0, 10)
            grand = int(open(marker).read())
            if cancel:
                tr.send_signal(signal.SIGTERM)
                time.sleep(.02)
                if tr.poll() is None: tr.send_signal(signal.SIGTERM)
            tr.wait(timeout=10)
            start, *_, end = record(d, 'family')
            until(lambda: gone(grand), 2)
            assert gone(start['pid']) and end['status'] == code, (start, end)
        finally:
            for pid in [grand, None if tr is None or tr.poll() is not None else tr.pid]:
                if pid is not None:
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
            if tr is not None: tr.wait(timeout=5)
            shutil.rmtree(d)


ZOMBIE = '''import os, subprocess, sys, time
C = os.fork()
if C == 0:
    D = os.fork()
    if D == 0: os._exit(0)
    os.setsid()
    while not subprocess.run(['ps', '-o', 'stat=', '-p', str(D)], capture_output=True, text=True).stdout.strip().startswith('Z'):
        time.sleep(0.01)
    open('zombie.tmp', 'w').write(f'{os.getpid()} {D}')
    os.rename('zombie.tmp', 'zombie')
    time.sleep(60)
    os._exit(0)
while not os.path.exists('zombie'): time.sleep(0.01)
time.sleep(float(sys.argv[1]))
raise SystemExit(int(sys.argv[2]))
'''


def q_cleanup_passes_over_a_group_of_zombies():
    # Replicata: the command (ZOMBIE) forks C, C forks D, still in the command's process group, and leaves the group
    # by setsid; D exits at once and stays a zombie of C, which lives on outside the group.  Then the command exits 0,
    # or waits while its tracker gets TERM.  Either way the tracker's cleanup finds in the group only D, a zombie, and
    # on macOS killpg of such a group fails with EPERM.  (2026-10-31: six seed trackers of 624:11 and 576:11 died so,
    # cancelled while a forked CVP child was a zombie, and wrote no end.)
    # Expectata: as with no zombie: the tracker exits with the command's status (0), or -15 when cancelled (241 as an
    # exit code); its record ends with that status; its reservation is gone; D is still a zombie when it is checked.
    for delay, code, cancel in [('0', 0, False), ('60', -15, True)]:
        d, tr, c = sandbox(), None, None
        try:
            open(os.path.join(d, 'zombie.py'), 'w').write(ZOMBIE)
            with open(os.path.join(d, 'tracker.err'), 'w') as log:      # C keeps a pipe's write end open
                tr = subprocess.Popen([PY, '-B', TRACK, 'run', 'zombie', 'S', '16:4', EST, '--', PY, 'zombie.py', delay,
                                       str(max(code, 0))], cwd=d, stdout=subprocess.DEVNULL, stderr=log)
            marker = os.path.join(d, 'zombie')
            until(lambda: os.path.exists(marker) and os.path.exists(os.path.join(d, 'runs', 'zombie.jsonl')), 10)
            c, z = map(int, open(marker).read().split())
            if cancel: tr.send_signal(signal.SIGTERM)
            tr.wait(timeout=10)
            err = open(os.path.join(d, 'tracker.err')).read()
            stat = subprocess.run(['ps', '-o', 'stat=', '-p', str(z)], capture_output=True, text=True).stdout.strip()
            assert stat.startswith('Z'), (z, stat)
            assert tr.returncode == code & 0xFF, (tr.returncode, err)
            assert record(d, 'zombie')[-1]['status'] == code, (record(d, 'zombie'), err)
            assert not os.path.exists(os.path.join(d, 'runs', '.zombie.reserved')), err
        finally:
            for pid in [c, None if tr is None or tr.poll() is not None else tr.pid]:
                if pid is not None:
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
            if tr is not None: tr.wait(timeout=5)
            shutil.rmtree(d)


def q_group_signal_fails_loudly_while_a_member_lives():
    # Replicata: a process sleeping in a process group of its own; track.group_signal on that group, with os.killpg
    # made to raise PermissionError, then ProcessLookupError (as it would for a live member it may not signal, which
    # no qual can make without root); then group_signal unpatched, with SIGKILL.
    # Expectata: both patched calls raise AssertionError naming the sleeper's pid (a failed killpg is passed over
    # only when no live member remains); the unpatched call kills the sleeper.
    d = sandbox()
    try:
        code = '''import os, signal, subprocess, sys, time, track
s = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
time.sleep(0.3)
real = os.killpg
for exc in (PermissionError, ProcessLookupError):
    def fails(pgid, signum, exc=exc): raise exc(1, 'injected')
    os.killpg = fails
    try:
        track.group_signal(s.pid, signal.SIGTERM)
        raise SystemExit('no assertion for ' + exc.__name__)
    except AssertionError as e:
        assert str(s.pid) in str(e), e
os.killpg = real
track.group_signal(s.pid, signal.SIGKILL)
assert s.wait(timeout=10) == -signal.SIGKILL
print('ok', flush=True)
'''
        p = subprocess.run([PY, '-B', '-c', code], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=30)
        assert p.returncode == 0 and p.stdout == 'ok\n', (p.returncode, p.stdout, p.stderr)
    finally:
        shutil.rmtree(d)


def q_spawn_failure_preserves_a_failure_record():
    # Replicata: launch a nonexistent command. Expectata: no command runs, the tracker fails, and its reserved name
    # has a terminal failure record, so another launch cannot silently reuse it.  Then a launch whose process cannot
    # be made at all (subprocess.Popen raising): its record is its start, with pid null, and its end, status 1, with no
    # estimate between them (2026-11-11: the estimator runs for a run that has a process).
    d = sandbox()
    try:
        p = subprocess.run([PY, '-B', TRACK, 'run', 'missing', 'S', '16:4', EST, '--', './no-such-command'], cwd=d,
                           capture_output=True, timeout=10)
        assert p.returncode != 0
        start, *_, end = record(d, 'missing')
        assert end['status'] != 0, (start, end)
        code = '''import track
def failed_spawn(*a, **kw): raise OSError('injected spawn failure')
track.subprocess.Popen = failed_spawn
track.run('nospawn', 'S', '16:4', None, ['est.py'], ['unused'])
'''
        p = subprocess.run([PY, '-B', '-c', code], cwd=d, env=IMPORTS, capture_output=True, timeout=10)
        start, end = record(d, 'nospawn')
        assert p.returncode != 0 and start['pid'] is None and end['status'] == 1, (start, end)
    finally:
        shutil.rmtree(d)


def q_sighup_is_forwarded_before_cleanup():
    # Replicata: a command handles HUP by writing a marker and exiting. Expectata: its handler runs; its tracker
    # records HUP cancellation, rather than replacing the signal with TERM or reporting success.
    d, tr = sandbox(), None
    try:
        code = "import signal,time;signal.signal(signal.SIGHUP,lambda *a:(open('hup','w').write('yes'),exit(0)));open('ready','w').write('yes');time.sleep(60)"
        tr = subprocess.Popen([PY, '-B', TRACK, 'run', 'hup', 'S', '16:4', EST, '--', PY, '-c', code], cwd=d)
        until(lambda: os.path.exists(os.path.join(d, 'ready')), 10)
        tr.send_signal(signal.SIGHUP)
        tr.wait(timeout=10)
        assert open(os.path.join(d, 'hup')).read() == 'yes'
        assert record(d, 'hup')[-1]['status'] == -signal.SIGHUP
    finally:
        if tr is not None and tr.poll() is None: tr.kill()
        if tr is not None: tr.wait(timeout=5)
        shutil.rmtree(d)


def q_record_write_failure_cleans_owned_group():
    # Replicata: after a child and TERM-ignoring grandchild start, writing the start record raises. Expectata: both
    # are cleaned despite the write failure, and a reservation remains to prevent automatic retry of an unrecorded run.
    d, tr = sandbox(), None
    try:
        open(os.path.join(d, 'family.py'), 'w').write(FAMILY)
        code = '''import os,sys,time,track
def broken(*a,**kw):
    while not os.path.exists('parent'): time.sleep(.01)
    raise OSError('injected record write failure')
track.start = broken
track.run('writefail', 'S', '16:4', None, ['est.py'], [sys.executable, 'family.py', '60', '0'])
'''
        tr = subprocess.Popen([PY, '-B', '-c', code], cwd=d, env=IMPORTS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tr.wait(timeout=10)
        pids = [int(open(os.path.join(d, name)).read()) for name in ('family', 'parent')]
        until(lambda: all(gone(pid) for pid in pids), 2)
        assert tr.returncode != 0 and os.path.exists(os.path.join(d, 'runs', '.writefail.reserved'))
    finally:
        for name in ('family', 'parent'):
            path = os.path.join(d, name)
            if os.path.exists(path):
                try: os.kill(int(open(path).read()), signal.SIGKILL)
                except ProcessLookupError: pass
        if tr is not None and tr.poll() is None: tr.kill()
        if tr is not None: tr.wait(timeout=5)
        shutil.rmtree(d)


PERIODIC = "import sys, track; track.PERIOD, track.EST_GRACE = 0.3, 0.5; track.main(sys.argv[1:])"   # the tracker, its estimates 0.3 s apart


def q_run_estimates_at_once_and_every_period():
    # Replicata: in a sandbox, the tracker with its period set to 0.3 s (PERIODIC), run p1 S 16:4 est.py -- python3 -c
    # "import time; time.sleep(2)".
    # Expectata (2026-11-11; dreeves, of the bar and the probability graph that one search alone had: "can you revamp
    # it?"): the record holds the start, then the estimator's estimates, one written when the run started (within the
    # run's first second) and one more each period (4 at least in the 2 s, in time order), then the end, status 0:
    # every run gets its estimates from its launch, with no code of the search's own.
    d = sandbox()
    try:
        p = subprocess.run([PY, '-B', '-c', PERIODIC, 'run', 'p1', 'S', '16:4', EST, '--', PY, '-c', 'import time; time.sleep(2)'],
                           cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        start, *estimates, end = record(d, 'p1')
        assert (start['event'], end['event'], end['status']) == ('start', 'end', 0), (start, end)
        assert len(estimates) >= 4 and all(e['event'] == 'estimate' for e in estimates), estimates
        times = [e['time'] for e in estimates]
        assert times == sorted(times) and start['time'] <= times[0] < start['time'] + 1 and times[-1] <= end['time'], (start, times, end)
    finally:
        shutil.rmtree(d)


def q_an_estimator_that_fails_or_hangs_leaves_the_run_alone():
    # Replicata: in a sandbox, the tracker with its period set to 0.3 s and its last estimator given 0.5 s (PERIODIC),
    # run NAME S 16:4 ESTIMATOR -- python3 -c "import time, sys; time.sleep(1.5); sys.exit(3)", with two estimators:
    # fail.py, which exits 1 at once, and hang.py, which appends its pid to the file hung and sleeps a minute.
    # Expectata: each tracker exits 3, its command's status, within 10 s; each record is the start and the end, status
    # 3, with no estimate; hang.py ran more than once (one a period), and none of its processes is left: one still
    # running when the next is due, or when the run has ended, is killed.  An estimator's trouble is its own.
    d = sandbox()
    try:
        open(os.path.join(d, 'fail.py'), 'w').write('raise SystemExit(1)\n')
        open(os.path.join(d, 'hang.py'), 'w').write("import os, time\nopen('hung', 'a').write(f'{os.getpid()}\\n')\ntime.sleep(60)\n")
        for name, estimator in [('fails', 'fail.py'), ('hangs', 'hang.py')]:
            t0 = time.time()
            p = subprocess.run([PY, '-B', '-c', PERIODIC, 'run', name, 'S', '16:4', estimator, '--', PY, '-c',
                                'import time, sys; time.sleep(1.5); sys.exit(3)'], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=60)
            assert p.returncode == 3 and time.time() - t0 < 10, (p.returncode, time.time() - t0, p.stderr)
            start, end = record(d, name)
            assert (start['event'], end['event'], end['status']) == ('start', 'end', 3), (start, end)
        pids = [int(x) for x in open(os.path.join(d, 'hung')).read().split()]
        assert len(pids) >= 2, pids
        until(lambda: all(gone(pid) for pid in pids), 5)
    finally:
        shutil.rmtree(d)


def q_adopt_estimates_while_its_process_lives():
    # Replicata: a process sleeping 3 s, started here; in a sandbox, the tracker with its period set to 0.3 s
    # (PERIODIC), adopt a1 S 16:4 est.py -- PID; the sleeper reaped here once it exits.
    # Expectata: the record holds the start (adopted true), then 3 estimates at least, then the end, status null: an
    # adopted process gets its estimates as a launched one does.
    d = sandbox()
    try:
        s = subprocess.Popen([PY, '-c', 'import time; print("ready", flush=True); time.sleep(3)'], stdout=subprocess.PIPE, text=True)
        assert s.stdout.readline() == 'ready\n'
        tr = subprocess.Popen([PY, '-B', '-c', PERIODIC, 'adopt', 'a1', 'S', '16:4', EST, '--', str(s.pid)], cwd=d, env=IMPORTS)
        s.wait()
        s.stdout.close()
        assert tr.wait(timeout=60) == 0
        start, *estimates, end = record(d, 'a1')
        assert (start['adopted'], end['event'], end['status']) == (True, 'end', None), (start, end)
        assert len(estimates) >= 3 and all(e['event'] == 'estimate' for e in estimates), estimates
    finally:
        shutil.rmtree(d)


# the tracker with its periodic estimates a minute apart, so that a run of a second or two gets none of them, and an
# adopted process's checks 0.2 s apart
LASTLY = "import sys, track; track.PERIOD, track.POLL = 60.0, 0.2; track.main(sys.argv[1:])"
# an estimator that says in its estimate's done whether the file over is there: 1.0, or 0.0
SEES = f'''import json, os, time
fd = os.open(os.environ['TRACK_RECORD'], os.O_WRONLY | os.O_APPEND)
os.write(fd, (json.dumps(dict({ESTIMATE!r}, done=float(os.path.exists('over')), time=time.time())) + '\\n').encode())
os.close(fd)
'''


def q_a_run_s_last_estimate_is_taken_once_its_process_has_ended():
    # Replicata: in a sandbox, sees.py (SEES), an estimator whose estimate's done is 1.0 if the file over is in the
    # sandbox and 0.0 if not; the tracker with its period set to a minute (LASTLY), run l1 S 16:4 sees.py -- python3 -c
    # "import time; time.sleep(1); open('over', 'w').close()", a command whose last act writes that file.  Then, in a
    # second sandbox, a process doing the same, started here, and the same tracker's adopt l2 S 16:4 sees.py -- PID.
    # Expectata (dreeves, 2026-11-13, of a finished search whose box kept the estimate of 81 s before its end: "sure,
    # that sounds cleaner to get exact counts and probability 0 when we completed a proof"): each record is its start,
    # two estimates and its end (status 0; null for the adopted one): the first estimate, taken as the run started,
    # found no file (done 0.0); the second found it (done 1.0), so it was taken once the process had ended, and its
    # time is no later than the end's.  A record's last estimate is of the search as it ended.
    # Resultata before: one estimate, the start's: the tracker ran the estimator at the start and every period while
    # the run went, never at its end.
    for mode in ('run', 'adopt'):
        d, s, tr = sandbox(), None, None
        try:
            open(os.path.join(d, 'sees.py'), 'w').write(SEES)
            job = [PY, '-c', "import time; time.sleep(1); open('over', 'w').close()"]
            if mode == 'run':
                p = subprocess.run([PY, '-B', '-c', LASTLY, 'run', 'l1', 'S', '16:4', 'sees.py', '--', *job], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=60)
                assert p.returncode == 0, p.stderr
            else:
                s = subprocess.Popen(job, cwd=d)
                tr = subprocess.Popen([PY, '-B', '-c', LASTLY, 'adopt', 'l2', 'S', '16:4', 'sees.py', '--', str(s.pid)], cwd=d, env=IMPORTS)
                s.wait()
                assert tr.wait(timeout=60) == 0
            start, first, last, end = record(d, dict(run='l1', adopt='l2')[mode])
            assert (start['event'], first['event'], last['event'], end['event'], end['status']) == ('start', 'estimate', 'estimate', 'end', dict(run=0, adopt=None)[mode]), (mode, start, end)
            assert (first['done'], last['done']) == (0.0, 1.0) and first['time'] <= last['time'] <= end['time'], (mode, first, last, end)
            inside(d, f"import track\ntrack.checked(track.lines('runs/{dict(run='l1', adopt='l2')[mode]}.jsonl'))\nprint('ok')\n")
        finally:
            if s is not None and s.poll() is None: s.kill()
            if tr is not None and tr.poll() is None: tr.kill()
            shutil.rmtree(d)


def inside(d, code):
    """Runs code in the sandbox d with its track.py importable; its output, which must end with ok."""
    p = subprocess.run([PY, '-B', '-c', code], cwd=d, env=IMPORTS, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.endswith('ok\n'), (p.returncode, p.stdout, p.stderr)
    return p.stdout


RECORD = f"""import json, track
START = dict(event='start', name='r', search='S', target='16:4', estimator='est.py', command='job', cwd='/', found=None,
             adopted=False, pid=7, tracker=8, time=100.0)
EST = dict({ESTIMATE!r}, time=110.0)
END = dict(event='end', time=120.0, status=0)
def refused(record):
    try: track.checked(record)
    except AssertionError: return True
    return False
"""


def q_a_record_holds_to_its_form():
    # Replicata: track.checked on handmade records: a start alone; a start, two estimates in time order and an end;
    # an adopted run's start (with its started field); then, each a change of the second: a line of another event
    # between; an estimate after the end; an estimate dated before the start; estimates out of time order; an estimate
    # missing its prior, and one with a field more; a band out of order (to_go's lo above its median; total's median
    # above its hi); a total's lo below the work done; a rate of 0; a P(exists) above 1; a negative work done; a to_go
    # that is no number; a start missing its search, and one with a field more; no start; and (2026-11-12) an estimate
    # with 12 pending, one with 0, then, refused, one missing its pending, one with -1, 1.5 and '3' pending; and (that
    # evening) one with 40 finished, one with 0, then, refused, one missing its finished, one with -1, 2.5 and '4'.
    # Expectata: the first three, and those with a count pending or finished, come back as given; each of the others is refused
    # (an AssertionError): the watcher and the estimators read a record through this one check, so a malformed line
    # fails loudly where it is read.
    d = sandbox()
    try:
        inside(d, RECORD + """
good = [START, EST, dict(EST, time=115.0), END]
assert track.checked([START]) == [START] and track.checked(good) == good
adopted = [dict(START, adopted=True, started='Wed Nov 11 10:00:00 2026'), EST]
assert track.checked(adopted) == adopted
counted = [START, dict(EST, pending=12), dict(EST, time=115.0, pending=0), END]
assert track.checked(counted) == counted
tallied = [START, dict(EST, finished=40), dict(EST, time=115.0, finished=0), END]
assert track.checked(tallied) == tallied
bad = dict(
    other=[START, EST, dict(event='eta', time=112.0, median=1.0, lo=0.5, hi=2.0), END],
    after=[START, EST, END, dict(EST, time=130.0)],
    early=[START, dict(EST, time=99.0), END],
    order=[START, dict(EST, time=115.0), EST, END],
    missing=[START, {k: v for k, v in EST.items() if k != 'prior'}, END],
    extra=[START, dict(EST, more=1), END],
    togo=[START, dict(EST, to_go=dict(median=1.0, lo=2.0, hi=9.0)), END],
    total=[START, dict(EST, total=dict(median=20.0, lo=1.5, hi=10.0)), END],
    below=[START, dict(EST, total=dict(median=2.0, lo=0.5, hi=10.0)), END],
    rate=[START, dict(EST, rate=0.0), END],
    exists=[START, dict(EST, exists=1.5), END],
    done=[START, dict(EST, done=-1.0), END],
    number=[START, dict(EST, to_go=dict(median='1', lo=0.5, hi=9.0)), END],
    nosearch=[{k: v for k, v in START.items() if k != 'search'}, EST, END],
    startmore=[dict(START, program='job.py'), EST, END],
    nostart=[EST, END],
    nopending=[START, {k: v for k, v in EST.items() if k != 'pending'}, END],
    negative=[START, dict(EST, pending=-1), END],
    fraction=[START, dict(EST, pending=1.5), END],
    text=[START, dict(EST, pending='3'), END],
    nofinished=[START, {k: v for k, v in EST.items() if k != 'finished'}, END],
    unfinished=[START, dict(EST, finished=-1), END],
    halved=[START, dict(EST, finished=2.5), END],
    written=[START, dict(EST, finished='4'), END])
kept = [name for name, record in bad.items() if not refused(record)]
assert not kept, kept
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_a_run_s_state_and_span_follow_its_record_and_its_process():
    # Replicata: track.state and track.span on handmade records, with the live processes given as {pid: ps's stat}
    # and now 500: a run with an end of status 0 at 120; one with an end of status null (an adopted run's); one with an
    # end of status 3; one with an end of status -15; one with no end, its last line an estimate at 110, and its pid
    # among the processes as S; the same with its pid's stat T (stopped); the same with its pid not among them.
    # Expectata: ended, ended, aborted, aborted, running, frozen, aborted; and their spans [100, 120] for the four
    # with an end, [100, 500] (to now) for the two whose process lives, and [100, 110] (to its last line) for the one
    # whose process is gone with no end written.
    # Spec change (Fable 5.2, 2026-11-13, the docstring's last): one more, with no end, its process (7) gone and its
    # tracker (8) among the processes: running, its span to now, since that tracker has yet to write the end (it is
    # taking the run's last estimate); and the same with the tracker stopped (T): frozen.  The seventh case, aborted,
    # has neither among them.
    d = sandbox()
    try:
        inside(d, RECORD + """
cases = [([START, EST, END], {}, 'ended', [100.0, 120.0]),
         ([START, EST, dict(END, status=None)], {}, 'ended', [100.0, 120.0]),
         ([START, EST, dict(END, status=3)], {}, 'aborted', [100.0, 120.0]),
         ([START, EST, dict(END, status=-15)], {7: 'S'}, 'aborted', [100.0, 120.0]),
         ([START, EST], {7: 'S'}, 'running', [100.0, 500.0]),
         ([START, EST], {7: 'T+'}, 'frozen', [100.0, 500.0]),
         ([START, EST], {9: 'S'}, 'aborted', [100.0, 110.0]),
         ([START, EST], {8: 'S'}, 'running', [100.0, 500.0]),
         ([START, EST], {8: 'T'}, 'frozen', [100.0, 500.0])]
got = [(track.state(r, procs), track.span(r, procs, 500.0)) for r, procs, _, _ in cases]
assert got == [(s, span) for _, _, s, span in cases], got
print('ok')
""")
    finally:
        shutil.rmtree(d)


PAUSED = """
PAUSE = dict(event='pause', time=115.0)
"""


def q_a_record_may_hold_one_pause_before_its_end():
    # Replicata: track.checked on handmade records: a start, an estimate, a pause, an end; a start, a pause, then an
    # estimate (the estimator still running after the mark) and an end; a start, an estimate and a pause (marked, not
    # yet stopped); then, refused: a pause after the end; two pauses; a pause dated before the start; a pause with a
    # field more; a pause whose time is no number; a pause with no start.
    # Expectata (dreeves, 2026-11-13: "go ahead and generalize track.py to record pause vs abort or whatever"): a record
    # may hold one pause, anywhere after its start and before its end, which stays its last line (every reader of a run's
    # end reads its last line); the first three come back as given, and each of the others is refused.
    d = sandbox()
    try:
        inside(d, RECORD + PAUSED + """
good = [[START, EST, PAUSE, END], [START, dict(PAUSE, time=105.0), EST, END], [START, EST, PAUSE]]
assert [track.checked(r) for r in good] == good
bad = dict(after=[START, EST, END, dict(PAUSE, time=130.0)], twice=[START, PAUSE, dict(PAUSE, time=116.0), END],
           early=[START, dict(PAUSE, time=99.0), END], more=[START, dict(PAUSE, why='x'), END],
           number=[START, dict(PAUSE, time='115'), END], nostart=[PAUSE, END])
kept = [name for name, record in bad.items() if not refused(record)]
assert not kept, kept
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_a_paused_run_reads_paused_once_it_stops():
    # Replicata: track.state and track.span, now 500, on records that hold a pause at 115: with an end of status -15 at
    # 120; with an end of status null (an adopted run's); with an end of status 3; with an end of status 0; with no
    # end and the pid among the live processes as S; the same as T (stopped); the same with the pid gone.
    # Expectata (dreeves, 2026-11-13, as above; of the 480:14 form tree stopped at 09:29 that day to free the cores and
    # queued to resume: "should 480:14 formtree say "paused" rather than "aborted"?"): a run stopped short of finishing
    # whose record holds a pause is paused, not aborted, whatever its status: paused, paused, paused; one that ended
    # with status 0 finished, so ended; while its process lives it is running, or frozen while stopped; once gone with
    # no end, paused.  Spans as ever: [100, 120] with an end, to now while the process lives, to the last line (the
    # pause) once gone.
    # Spec change (Fable 5.2, 2026-11-13, night, the docstring's last): with no end, the process gone and the tracker
    # (8) living, running, its span to now: a marked run too goes on until its tracker has written its end.
    d = sandbox()
    try:
        inside(d, RECORD + PAUSED + """
cases = [([START, EST, PAUSE, dict(END, status=-15)], {}, 'paused', [100.0, 120.0]),
         ([START, EST, PAUSE, dict(END, status=None)], {}, 'paused', [100.0, 120.0]),
         ([START, EST, PAUSE, dict(END, status=3)], {}, 'paused', [100.0, 120.0]),
         ([START, EST, PAUSE, END], {}, 'ended', [100.0, 120.0]),
         ([START, EST, PAUSE], {7: 'S'}, 'running', [100.0, 500.0]),
         ([START, EST, PAUSE], {7: 'T+'}, 'frozen', [100.0, 500.0]),
         ([START, EST, PAUSE], {9: 'S'}, 'paused', [100.0, 115.0]),
         ([START, EST, PAUSE], {8: 'S'}, 'running', [100.0, 500.0])]
got = [(track.state(r, procs), track.span(r, procs, 500.0)) for r, procs, _, _ in cases]
assert got == [(s, span) for _, _, s, span in cases], got
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_pause_marks_a_live_run_and_refuses_the_rest():
    # Replicata: in a sandbox, track.py run q11 S 16:4 est.py -- a command that sleeps 30 s, in the background; once its
    # start is written, track.py pause q11; then track.py pause q11 again; then SIGTERM to its tracker; then track.py
    # pause q11 once more; and track.py pause q12, of which there is no record, and track.py pause with a bad name.
    # Expectata (dreeves, 2026-11-13, as above): the first pause exits 0 and appends one line, {"event": "pause",
    # "time"}, its time that moment's (an estimate may follow it); it stops nothing (the command still runs).  The second is refused (exit nonzero),
    # the record as it was: one pause a run.  Stopped, the run's record ends with its end (status -15) after the pause,
    # and track.state reads it paused.  Pausing it then is refused: a run's stop is marked before it ends, so that its
    # end stays its record's last line.  No record, no pause: refused, no file made; a bad name refused.
    d = sandbox()
    try:
        tracker = subprocess.Popen([PY, '-B', TRACK, 'run', 'q11', 'S', '16:4', EST, '--', PY, '-c', 'import time; time.sleep(30)'], cwd=d)
        until(lambda: os.path.exists(os.path.join(d, 'runs', 'q11.jsonl')), 10)
        t0 = time.time()
        first = subprocess.run([PY, '-B', TRACK, 'pause', 'q11'], cwd=d, capture_output=True, text=True)
        assert first.returncode == 0, first
        lines = record(d, 'q11')
        pauses = [x for x in lines if x['event'] == 'pause']          # an estimate may come after it: the estimator runs on
        assert len(pauses) == 1 and set(pauses[0]) == {'event', 'time'} and t0 <= pauses[0]['time'] <= time.time(), lines
        assert tracker.poll() is None and not gone(lines[0]['pid'])                       # it stops nothing
        again = subprocess.run([PY, '-B', TRACK, 'pause', 'q11'], cwd=d, capture_output=True, text=True)
        assert again.returncode != 0 and [x['event'] for x in record(d, 'q11')].count('pause') == 1, again
        tracker.send_signal(signal.SIGTERM)
        tracker.wait(timeout=30)
        lines = record(d, 'q11')
        events = [x['event'] for x in lines]
        assert events[-1] == 'end' and events.count('pause') == 1 and lines[-1]['status'] == -signal.SIGTERM, events
        inside(d, f"import track; r = track.checked(track.lines('runs/q11.jsonl')); assert track.state(r, track.processes()) == 'paused', r; print('ok')")
        late = subprocess.run([PY, '-B', TRACK, 'pause', 'q11'], cwd=d, capture_output=True, text=True)
        assert late.returncode != 0 and record(d, 'q11') == lines, late
        none = subprocess.run([PY, '-B', TRACK, 'pause', 'q12'], cwd=d, capture_output=True, text=True)
        assert none.returncode != 0 and not os.path.exists(os.path.join(d, 'runs', 'q12.jsonl')), none
        bad = subprocess.run([PY, '-B', TRACK, 'pause', '../q11'], cwd=d, capture_output=True, text=True)
        assert bad.returncode != 0 and record(d, 'q11') == lines, bad
    finally:
        shutil.rmtree(d)


def q_passes_join_the_spans_and_running_counts_their_seconds():
    # Replicata: track.passes on the spans [30, 40], [0, 10], [5, 20], [20, 25] and [32, 35], and track.running on its
    # result at the times -5, 0, 7, 25, 28, 35 and 100; then both on no span at all.
    # Expectata: the passes are [0, 25] and [30, 40], the stretches during which some run was going, in order (spans
    # that overlap or touch are one stretch); the seconds of running before those times are 0, 0, 7, 25, 25, 30 and
    # 35; with no span, no pass and 0 seconds.
    d = sandbox()
    try:
        inside(d, """import track
p = track.passes([[30, 40], [0, 10], [5, 20], [20, 25], [32, 35]])
assert p == [[0, 25], [30, 40]], p
got = [track.running(p, t) for t in (-5, 0, 7, 25, 28, 35, 100)]
assert got == [0, 0, 7, 25, 25, 30, 35], got
assert track.passes([]) == [] and track.running([], 50) == 0
print('ok')
""")
    finally:
        shutil.rmtree(d)


def q_searches_gather_the_runs_of_a_label_at_a_target():
    # Replicata: in a sandbox, six runs launched in turn, the first five python3 -c pass: a1 and a2 of the search tilt
    # at 16:4, b1 of the search tree at 16:4, c1 of tilt at 32:5, a3 of tilt at 16:4, and bad of tilt at 16:4, a
    # command that does not exist; then a file runs/notes.txt and a directory runs/cpu; then track.searches() there.
    # Expectata (dreeves, 2026-11-11, of different searches on one cell: "sounds like obviously yes, that we want to
    # see different searches on the same cell separately"): three searches, keyed (label, target): (tilt, 16:4) with
    # the records of a1, a2, a3 and bad in the order they started (a run whose command failed is a run of its search
    # like any other), (tree, 16:4) with b1's and (tilt, 32:5) with c1's, each record its lines as track.checked
    # returns them; the other files are in none.
    d = sandbox()
    try:
        for name, search, target in [('a1', 'tilt', '16:4'), ('a2', 'tilt', '16:4'), ('b1', 'tree', '16:4'), ('c1', 'tilt', '32:5'),
                                     ('a3', 'tilt', '16:4')]:
            assert subprocess.run([PY, '-B', TRACK, 'run', name, search, target, EST, '--', PY, '-c', 'pass'], cwd=d).returncode == 0
        assert subprocess.run([PY, '-B', TRACK, 'run', 'bad', 'tilt', '16:4', EST, '--', './no-such-command'], cwd=d,
                              capture_output=True).returncode != 0
        open(os.path.join(d, 'runs', 'notes.txt'), 'w').write('x\n')
        os.mkdir(os.path.join(d, 'runs', 'cpu'))
        out = inside(d, """import json, track
found = track.searches()
print(json.dumps([[list(key), [r[0]['name'] for r in runs], all(track.checked(r) == r for r in runs)] for key, runs in sorted(found.items())]))
print('ok')
""")
        got = json.loads(out.splitlines()[0])
        assert got == [[['tilt', '16:4'], ['a1', 'a2', 'a3', 'bad'], True], [['tilt', '32:5'], ['c1'], True], [['tree', '16:4'], ['b1'], True]], got
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
