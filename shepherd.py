#!/usr/bin/env python3
"""Claude's shepherd (named 2026-10-23, dreeves: "chef's-kiss"): keeps the searches running by the principles dreeves
decided that day (AGENTS.md's scratchpad has them).  Run from this directory, once, in the background:

    PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B shepherd.py

Every REFRESH seconds it reads the process list, each search's journal and data and the free disk, logs each status
it has not logged before, and acts by the floors: it launches every launchable search at or above the floor, stops the
search with the most data below it, and stops every running search below the hard floor.  It never deletes anything
and never launches a stopped search.

Vocabulary:
  search      a registered search (SEARCHES): resumable, its every outcome exactly certified, with green quals and a
              positive control before it joins (principles 1 and 5); its script and arguments, with no budget
              (principle 2), the files it writes and its memory, measured when it joined.
  status      a search's, from the process list and its journal's last complete record: running (a live process runs
              it); done (a finish with outcome excluded or witness: a proof or a witness); launchable (no journal yet,
              or a finish with outcome budget, a pass that ended at its budget, as passes did before 2026-10-23);
              stopped (anything else: a crash, a kill, a reboot or a stop at the floor, which a human looks at first:
              principle 2 never restarts a crash, and the shepherd cannot tell one from the others).
  data        a search's checkpoint directory, and the bytes of the files under it (used).
  floor       FLOOR bytes of free disk (principle 4; dreeves, 2026-10-23: "fine, 2 floors if you're sure").  At or
              above it every launchable search launches.  Below it nothing launches, and the search with the most data
              of those not done stops if it runs.  Stopped, its data still counts, so another stops only by outgrowing
              it; a done search's data, which no longer grows, counts for nothing.  Stopping a search frees no disk:
              the floor stays crossed until a human frees some.
  hard floor  HARD_FLOOR bytes of free disk, below FLOOR: below it every running search stops.
  slots       SLOTS searches at once in MEMORY bytes in all (principle 4), asserted of the searches not done.  A search
              beyond them would need preemption by priority (principle 3), which is not built: with two searches it
              could not happen.  So the shepherd fails loudly instead.
  log         LOG, one JSON object per line: its start, each status as first seen and at each change (with the
              journal's last record and the tail of the error file), and each launch and stop.
"""
from dataclasses import dataclass
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

from progress import processes

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, 'shepherd.log')
LOCK = os.path.join(HERE, 'scratch', 'shepherd.lock')     # held while a shepherd runs: never two at once
PYTHON = '/opt/homebrew/bin/python3'
PYLIB = 'scratch/lower24-design/beyond1000/pylib'          # the searches' PYTHONPATH, relative to HERE
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')   # each set to 1
NICE = 15                              # the searches' niceness, and the shepherd's
REFRESH = 60                           # seconds between looks
SLOTS = 6                              # searches at once: this Mac's 8 performance cores less 2 (principle 4)
MEMORY = 12 << 30                      # bytes in all for the searches not done, of the Mac's 16 GiB (principle 4)
FLOOR = 100 << 30                      # bytes of free disk, as df -h counts its Gi (principle 4)
HARD_FLOOR = 50 << 30                  # bytes of free disk: the hard floor (dreeves, 2026-10-23)
TAIL = 1 << 16                         # bytes read from the end of a journal or an error file
KINDS = {('finish', 'budget'): 'launchable', ('finish', 'excluded'): 'done', ('finish', 'witness'): 'done'}


@dataclass(frozen=True)
class Search:
    """A search (see the vocabulary): its name, n:order; its script and arguments; its journal, output and error
    files and its data directory (relative to HERE, or absolute); and its memory in bytes."""
    name: str
    script: str
    args: tuple
    journal: str
    out: str
    err: str
    data: str
    memory: int

    @property
    def pattern(self):
        """A process command line running it: its script and first argument, as words."""
        return rf'(?:^|[\s/]){re.escape(self.script)} {re.escape(self.args[0])}(?:\s|$)'


UNBOUNDED = ('--seconds', 'inf', '--lp-budget', str(10 ** 18))   # no budget (principle 2): focus.py's flags take a value
SEARCHES = (                           # memory: 56 MB at most measured (2026-10-22 and 23), rounded up
    Search('480:14', 'focus.py', ('480',) + UNBOUNDED, 'focus_480_journal.jsonl', 'focus_480.log',
           'scratch/focus480/run.err', 'scratch/focus480/run', 64 << 20),
    Search('672:13', 'focus.py', ('672',) + UNBOUNDED, 'focus_672_journal.jsonl', 'focus_672.log',
           'scratch/focus672/run.err', 'scratch/focus672/run', 64 << 20),
)


def tail(path):
    """The last TAIL bytes of a file, as text from its first whole line on, and whether they start mid-file; ('', False)
    with no file."""
    full = os.path.join(HERE, path)
    if not os.path.exists(full): return '', False
    with open(full, 'rb') as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - TAIL))
        return f.read().decode('utf-8', errors='replace'), size > TAIL


def last_record(path):
    """The journal's last complete record (a line its newline ends), or None with no file or no such line."""
    text, cut = tail(path)
    lines = text.split('\n')[int(cut):-1]      # a cut first line may be partial, and so may a last without its newline
    return json.loads(lines[-1]) if lines else None


def status(s, procs):
    """The search's status (see the vocabulary) and the pid of its process, None unless running."""
    pids = [p[0] for p in procs if re.search(s.pattern, p[3]) and not p[2].startswith('Z')]
    # TODO: error copy; says several live processes run this search, naming it and the pids
    assert len(pids) <= 1, f'Claude: "{len(pids)} processes run {s.name}: {pids}"'
    last = last_record(s.journal)
    kind = 'launchable' if last is None else KINDS.get((last['event'], last.get('outcome')), 'stopped')
    return ('running' if pids else kind), (pids + [None])[0]


def size(path):
    """A file's bytes; 0 for one gone since it was listed (a checkpoint's temporary file, renamed into place)."""
    try:
        return os.stat(path).st_size
    except FileNotFoundError:
        return 0


def used(path):
    """The bytes of the files under a directory (relative to HERE, or absolute): a search's data; 0 with none."""
    return sum(size(os.path.join(root, f)) for root, _, files in os.walk(os.path.join(HERE, path)) for f in files)


def decide(statuses, data, free):
    """The actions, as (act, name), for the searches' statuses ({name: status}) and data ({name: bytes}) at free
    bytes of disk, by the floors (see the vocabulary)."""
    biggest = max((name for name, st in statuses.items() if st != 'done'), key=lambda name: data[name], default=None)
    return ([('launch', name) for name, st in statuses.items() if st == 'launchable' and free >= FLOOR] +
            [('stop', name) for name, st in statuses.items()
             if st == 'running' and (free < HARD_FLOOR or (free < FLOOR and name == biggest))])


def admit(searches, statuses):
    """Asserts that the searches not done fit the slots and the memory (see the vocabulary)."""
    live = [s for s in searches if statuses[s.name] != 'done']
    # TODO: error copy; says more searches wait than there are slots, which needs preemption, not yet built
    assert len(live) <= SLOTS, f'Claude: "{len(live)} searches for {SLOTS} slots: preemption (principle 3) is not built"'
    # TODO: error copy; says the searches' memory exceeds the limit, giving both in bytes
    assert sum(s.memory for s in live) <= MEMORY, f'Claude: "{sum(s.memory for s in live)} bytes of searches for {MEMORY}"'


def launch(s):
    """Starts the search: nice -n NICE, PYTHON -B, its script and arguments, in HERE with PYLIB and single-threaded
    BLAS, no stdin, its output and errors appended to its files, in a session of its own (it outlives the shepherd)."""
    env = dict(os.environ, PYTHONPATH=PYLIB, **{k: '1' for k in THREADS})
    with open(os.path.join(HERE, s.out), 'a') as out, open(os.path.join(HERE, s.err), 'a') as err:
        return subprocess.Popen(['nice', '-n', str(NICE), PYTHON, '-B', s.script, *s.args], cwd=HERE, env=env,
                                stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)


def spawn(s, pid, children):
    """Launches the search, keeping its child to reap; the child's pid."""
    child = launch(s)
    children[child.pid] = child
    return child.pid


def stop(s, pid, children):
    """Stops the search's process, pid, with SIGTERM: its checkpoints are atomic, so it resumes from the last; pid."""
    os.kill(pid, signal.SIGTERM)
    return pid


ACTS = {'launch': spawn, 'stop': stop}


def free_disk():
    return shutil.disk_usage(HERE).free


def note(event, **fields):
    """Appends a log record: the time, the event and its fields."""
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(dict(time=time.time(), event=event, **fields), separators=(',', ':'), ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def lock(path):
    """The lock file, open and exclusively locked; BlockingIOError if another holds it."""
    f = open(path, 'a')
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return f


def main(argv):
    # TODO: error copy; says how to run the shepherd: with no arguments
    assert argv == [], 'Claude: "usage: python3 -B shepherd.py"'
    held = lock(LOCK)
    os.nice(max(0, NICE - os.nice(0)))
    named = {s.name: s for s in SEARCHES}
    assert len(named) == len(SEARCHES), SEARCHES
    note('start', pid=os.getpid(), searches=list(named))
    seen, children = {}, {}
    while True:
        for child in children.values(): child.poll()       # reaps a child that ended: no zombie stays listed
        procs, free = processes(), free_disk()
        statuses = {s.name: status(s, procs) for s in SEARCHES}
        admit(SEARCHES, {name: st for name, (st, _) in statuses.items()})
        for s in [s for s in SEARCHES if seen.get(s.name) != statuses[s.name][0]]:
            note('status', search=s.name, status=statuses[s.name][0], pid=statuses[s.name][1],
                 last=last_record(s.journal), err=tail(s.err)[0][-2000:])
        data = {s.name: used(s.data) for s in SEARCHES}
        for act, name in decide({name: st for name, (st, _) in statuses.items()}, data, free):
            note(act, search=name, pid=ACTS[act](named[name], statuses[name][1], children), free=free)
        seen = {name: st for name, (st, _) in statuses.items()}
        time.sleep(REFRESH)


if __name__ == '__main__':
    main(sys.argv[1:])
