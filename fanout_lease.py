"""Hold 480 in memory while an unbounded 672 fanout runs; resume after group cleanup."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
LEASE = HERE / 'scratch/search288/lease.py'
assert hashlib.sha256(LEASE.read_bytes()).hexdigest() == '15081e570df339105a52600e63c7adcf814b8aea09cc5c52d31308bd153df285'
spec = importlib.util.spec_from_file_location('qualified_lease', LEASE)
qualified = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualified)
identity, state = qualified.identity, qualified.state


def append(path, event, pid, original):
    """One append and fsync per complete transition, for progress's pause accounting."""
    record = dict(event=event, time=time.time(), pid=pid, start=original[0], command=original[1])
    data = (json.dumps(record, separators=(',', ':')) + '\n').encode()
    with open(path, 'ab', buffering=0) as stream:
        assert stream.write(data) == len(data)
        os.fsync(stream.fileno())


def wait_state(pid, original, paused):
    """Bound signal acknowledgement, never the search itself."""
    deadline = time.monotonic() + 10
    while state(pid, original).startswith('T') != paused:
        assert time.monotonic() < deadline
        time.sleep(.01)


def run(pid, original, command, journal):
    """Own a new child process group, with no search time limit and paired pause records."""
    original = tuple(original)
    assert identity(pid)[0] == original
    assert state(pid, original)[:1] not in ('T', 'Z')
    assert command and all(type(a) is str for a in command)
    # Opening a missing journal is explicit; an unfinished prior lease is refused.
    with open(journal, 'a+') as stream:
        stream.seek(0)
        records = [json.loads(line) for line in stream]
    assert len(records) % 2 == 0
    assert all(r['event'] == ('pause', 'resume')[i % 2] for i, r in enumerate(records))
    child, recorded = None, False
    blocked = {signal.SIGTERM, signal.SIGINT}
    handlers = {s: signal.getsignal(s) for s in blocked}
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
    try:
        for s in blocked:
            signal.signal(s, qualified.interrupted)
        assert identity(pid)[0] == original
        os.kill(pid, signal.SIGSTOP)
        wait_state(pid, original, True)
        append(journal, 'pause', pid, original)
        recorded = True
        # The exec wrapper unblocks signals only after the parent owns the child.
        wrapper = ('import os,signal,sys;signal.pthread_sigmask(signal.SIG_SETMASK,'
                   + repr([int(s) for s in mask]) + ');os.execvp(sys.argv[1],sys.argv[1:])')
        child = subprocess.Popen([sys.executable, '-B', '-c', wrapper, *command], start_new_session=True)
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        return child.wait()
    finally:
        signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
        try:
            if child is not None:
                qualified.cleanup(child, time.monotonic() + qualified.GRACE)
        finally:
            try:
                assert identity(pid)[0] == original
                os.kill(pid, signal.SIGCONT)
                wait_state(pid, original, False)
                if recorded:
                    append(journal, 'resume', pid, original)
            finally:
                for s, handler in handlers.items():
                    signal.signal(s, handler)
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)


def main():
    """Execute the explicit, locally reviewed allocation intent, once."""
    import fanout
    import progress
    import shepherd
    os.chdir(HERE)
    intent = json.loads((HERE / 'scratch/allocate672/intent.json').read_text())
    assert set(intent) == {'pid', 'start', 'command', 'child', 'sources'}
    assert intent['child'] == [shepherd.PYTHON, '-B', 'fanout.py', '672']
    assert fanout.WORKERS == shepherd.SLOTS == 8
    assert shutil.disk_usage(HERE).free >= shepherd.FLOOR
    assert all(hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
               for name, digest in intent['sources'].items())
    assert all(os.environ[name] == '1' for name in shepherd.THREADS)
    os.nice(max(0, shepherd.NICE - os.nice(0)))
    with open(HERE / 'scratch/allocate672/lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        procs = progress.processes()
        assert not progress.runs(procs, 'fanout.py', '672')
        matches = progress.runs(procs, 'focus.py', '480')
        assert len(matches) == 1 and matches[0][0] == intent['pid']
        with open(HERE / 'scratch/allocate672/lease.json', 'x') as record:
            json.dump(dict(pid=os.getpid(), time=time.time(), intent=intent), record, indent=2)
        return run(intent['pid'], (intent['start'], intent['command']), intent['child'],
                   HERE / 'focus_480_pauses.jsonl')


if __name__ == '__main__':
    raise SystemExit(main())
