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
    # the sleeper's command as ps prints it; track.py exits 0 after the sleeper is gone, its end's status null (an
    # adopted process's status is not track.py's to read).
    d = sandbox()
    try:
        s = subprocess.Popen([PY, '-c', 'import time; time.sleep(2)'])
        ps = subprocess.run(['ps', '-o', 'command=', '-p', str(s.pid)], capture_output=True, text=True).stdout.strip()
        tr = subprocess.Popen([PY, '-B', 'track.py', 'adopt', 'q4', '16:4', str(s.pid), '--found', 'W'], cwd=d)
        s.wait()
        assert tr.wait(timeout=60) == 0
        start, end = record(d, 'q4')
        assert (start['pid'], start['tracker'], start['adopted'], start['found'], start['command']) == (
            s.pid, tr.pid, True, os.path.join(os.path.realpath(d), 'W'), ps), start
        assert end['event'] == 'end' and end['status'] is None and end['time'] >= start['time'], end
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
