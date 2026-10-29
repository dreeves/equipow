#!/usr/bin/env python3
"""Quals for track.py, the launcher every search runs under (2026-10-28; dreeves: "can we rearchitect things so that
always happens easily and automatically?", then "those names are fine, go ahead").  Run from the repo:
    python3 -B quals_track.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Each copies track.py into a temporary directory and
runs it there, so that its records go to that directory's runs/.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, shutil, signal, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sandbox():
    d = tempfile.mkdtemp(prefix='track-quals-')
    shutil.copy(os.path.join(HERE, 'track.py'), d)
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
    # Replicata: track.py run q1 16:4 --found F -- python3 -c "import sys; sys.exit(3)", in a temporary directory.
    # Expectata: track.py exits 3, its command's status; runs/q1.jsonl holds two lines: the start (event start, name
    # q1, target 16:4, program the interpreter's name (no argument ends in .py), the command as a shell would write it,
    # found F's absolute path, adopted false, the command's pid and track.py's own as tracker, a time) and the end
    # (event end, status 3, a time no earlier than the start's).
    d = sandbox()
    try:
        cmd = [PY, '-c', 'import sys; sys.exit(3)']
        p = subprocess.run([PY, '-B', 'track.py', 'run', 'q1', '16:4', '--found', 'F', '--', *cmd], cwd=d)
        assert p.returncode == 3, p.returncode
        start, end = record(d, 'q1')
        assert {k: start[k] for k in ('event', 'name', 'target', 'program', 'command', 'found', 'adopted')} == dict(
            event='start', name='q1', target='16:4', program=os.path.basename(PY),
            command=f"{PY} -c 'import sys; sys.exit(3)'", found=os.path.join(os.path.realpath(d), 'F'), adopted=False), start
        assert start['pid'] > 0 and start['tracker'] > 0 and start['pid'] != start['tracker'], start
        assert end['event'] == 'end' and end['status'] == 3 and end['time'] >= start['time'], end
    finally:
        shutil.rmtree(d)


def q_run_names_the_script_as_its_program():
    # Replicata: track.py run q2 16:4 -- python3 -B job.py, job.py exiting 0, in a temporary directory.
    # Expectata: the start's program is job.py (the command's first argument ending in .py) and its found null; the
    # end's status 0.
    d = sandbox()
    try:
        open(os.path.join(d, 'job.py'), 'w').write('pass\n')
        assert subprocess.run([PY, '-B', 'track.py', 'run', 'q2', '16:4', '--', PY, '-B', 'job.py'], cwd=d).returncode == 0
        start, end = record(d, 'q2')
        assert (start['program'], start['found'], end['status']) == ('job.py', None, 0), (start, end)
    finally:
        shutil.rmtree(d)


def q_run_passes_sigterm_to_its_command():
    # Replicata: track.py run q3 16:4 -- python3 -c "import time; time.sleep(60)"; once its start is written,
    # SIGTERM to track.py.
    # Expectata: the command gets the signal and ends; the record's end says status -15 (SIGTERM); the command's
    # process is gone.
    d = sandbox()
    try:
        tr = subprocess.Popen([PY, '-B', 'track.py', 'run', 'q3', '16:4', '--', PY, '-c', 'import time; time.sleep(60)'], cwd=d)
        until(lambda: os.path.exists(os.path.join(d, 'runs', 'q3.jsonl')), 20)
        tr.send_signal(signal.SIGTERM)
        tr.wait(timeout=30)
        start, end = record(d, 'q3')
        assert end['status'] == -signal.SIGTERM, end
        assert gone(start['pid']), start
    finally:
        shutil.rmtree(d)


def q_adopt_writes_the_end_when_the_process_is_gone():
    # Replicata: a process sleeping 2 s, started here; track.py adopt q4 16:4 PID --found W; the sleeper reaped here
    # once it exits.
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
        tr = subprocess.Popen([PY, '-B', 'track.py', 'adopt', 'q4', '16:4', str(s.pid), '--found', 'W'], cwd=d)
        s.wait()
        s.stdout.close()
        assert tr.wait(timeout=60) == 0
        start, end = record(d, 'q4')
        assert (start['pid'], start['tracker'], start['adopted'], start['found'], start['command']) == (
            s.pid, tr.pid, True, os.path.join(os.path.realpath(d), 'W'), ps), start
        assert end['event'] == 'end' and end['status'] is None and end['time'] >= start['time'], end
        assert start['time'] == began, (start['time'], began)
    finally:
        shutil.rmtree(d)


def q_refuses_a_name_used_before_a_bad_target_and_a_dead_pid():
    # Replicata: track.py run q5 16:4 -- python3 -c pass, twice; track.py run q6 16 -- ...; track.py adopt q7 16:4
    # with the pid of a process already reaped.
    # Expectata: the first run ends with status 0; the second exits nonzero, naming q5, and leaves q5's record as it
    # was (two lines); the bad target and the dead pid each exit nonzero and write no record.
    d = sandbox()
    try:
        cmd = [PY, '-B', 'track.py', 'run', 'q5', '16:4', '--', PY, '-c', 'pass']
        assert subprocess.run(cmd, cwd=d).returncode == 0
        again = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
        assert again.returncode != 0 and 'q5' in again.stderr, again
        assert len(record(d, 'q5')) == 2
        bad = subprocess.run([PY, '-B', 'track.py', 'run', 'q6', '16', '--', PY, '-c', 'pass'], cwd=d, capture_output=True, text=True)
        assert bad.returncode != 0 and not os.path.exists(os.path.join(d, 'runs', 'q6.jsonl')), bad
        s = subprocess.Popen([PY, '-c', 'pass'])
        s.wait()
        dead = subprocess.run([PY, '-B', 'track.py', 'adopt', 'q7', '16:4', str(s.pid)], cwd=d, capture_output=True, text=True)
        assert dead.returncode != 0 and not os.path.exists(os.path.join(d, 'runs', 'q7.jsonl')), dead
    finally:
        shutil.rmtree(d)


def q_refusal_never_launches_the_command():
    # Replicata: rejected names and targets, and two concurrent launchers using the same fresh name; each command
    # appends to a marker. Expectata: rejected commands append nothing; exactly one concurrent command starts.
    d = sandbox()
    try:
        cmd = [PY, '-c', "open('launched', 'a').write('x'); import time; time.sleep(.1)"]
        base = [PY, '-B', 'track.py', 'run']
        assert subprocess.run([*base, 'used', '16:4', '--', PY, '-c', 'pass'], cwd=d).returncode == 0
        for name, target in [('used', '16:4'), ('bad', '16'), ('bad/name', '16:4')]:
            p = subprocess.run([*base, name, target, '--', *cmd], cwd=d, capture_output=True, timeout=10)
            assert p.returncode != 0
        time.sleep(.3)
        assert not os.path.exists(os.path.join(d, 'launched')), 'a rejected command ran'
        contenders = [subprocess.Popen([*base, 'race', '16:4', '--', *cmd], cwd=d,
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
            tr = subprocess.Popen([PY, '-B', 'track.py', 'run', 'family', '16:4', '--', PY, 'family.py', delay,
                                   str(max(code, 0))], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            marker = os.path.join(d, 'family')
            until(lambda: os.path.exists(marker) and os.path.getsize(marker) > 0, 10)
            grand = int(open(marker).read())
            if cancel:
                tr.send_signal(signal.SIGTERM)
                time.sleep(.02)
                if tr.poll() is None: tr.send_signal(signal.SIGTERM)
            tr.wait(timeout=10)
            start, end = record(d, 'family')
            until(lambda: gone(grand), 2)
            assert gone(start['pid']) and end['status'] == code, (start, end)
        finally:
            for pid in [grand, None if tr is None or tr.poll() is not None else tr.pid]:
                if pid is not None:
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
            if tr is not None: tr.wait(timeout=5)
            shutil.rmtree(d)


def q_spawn_failure_preserves_a_failure_record():
    # Replicata: launch a nonexistent command. Expectata: no command runs, the tracker fails, and its reserved name
    # has a terminal failure record, so another launch cannot silently reuse it.
    d = sandbox()
    try:
        p = subprocess.run([PY, '-B', 'track.py', 'run', 'missing', '16:4', '--', './no-such-command'], cwd=d,
                           capture_output=True, timeout=10)
        assert p.returncode != 0
        start, end = record(d, 'missing')
        assert end['status'] != 0, (start, end)
        code = '''import track
def failed_spawn(*a, **kw): raise OSError('injected spawn failure')
track.subprocess.Popen = failed_spawn
track.run('nospawn', '16:4', None, ['unused'])
'''
        p = subprocess.run([PY, '-B', '-c', code], cwd=d, capture_output=True, timeout=10)
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
        tr = subprocess.Popen([PY, '-B', 'track.py', 'run', 'hup', '16:4', '--', PY, '-c', code], cwd=d)
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
track.run('writefail', '16:4', None, [sys.executable, 'family.py', '60', '0'])
'''
        tr = subprocess.Popen([PY, '-B', '-c', code], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
