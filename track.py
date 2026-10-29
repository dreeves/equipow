#!/usr/bin/env python3
"""The launcher every search runs under, so that the Search progress section on index.html shows it with no code of
its own (dreeves, 2026-10-28: "can we rearchitect things so that always happens easily and automatically?", then,
of the names track.py and runs/<name>.jsonl, "those names are fine, go ahead").  track.py writes the run's record,
which progress.py's watcher reads (survey_track); the search itself is not changed.

  record   runs/NAME.jsonl, JSON lines.  The first, {"event": "start", "name", "target", "program", "command", "cwd",
           "found", "adopted", "pid", "tracker", "time"}: target "N:M", the question m*(N) >= M?; program the
           command's script (its first argument ending in .py, else its first word's name); command as a shell would
           write it; found the absolute path of a file whose lines count the search's results (a witness file), or
           null; pid the run's process and tracker track.py's own; time when the run's process began (epoch seconds;
           for an adopted one, its start time as ps prints it, to the second).  It appears whole (written aside, then
           linked into place).  The last, once the run's process ends: {"event": "end", "time", "status"}, its exit status (a
           negative one a signal's), or null for an adopted process, whose status track.py cannot read.
  run      python3 -B track.py run NAME N:M [--found FILE] -- COMMAND ...: starts COMMAND, writes the start, waits,
           writes the end and exits with COMMAND's status.  SIGTERM, SIGINT and SIGHUP to track.py are passed on to
           COMMAND, whose end is then written as usual.
  adopt    python3 -B track.py adopt NAME N:M PID [--found FILE]: for a process started without track.py: writes the
           start (its command as ps prints it, and "started", its start time as ps prints it, which with its pid
           identifies it), polls it every POLL seconds and writes the end once no live process has that pid and
           start time.  A SIGKILL'd or crashed tracker writes no end: the watcher then shows the run aborted once its
           process is gone.
Refuses, writing nothing: a NAME of other than letters, digits, '.', '_' and '-'; a NAME whose record exists (a name
is one run); a target not N:M; an adopted PID with no live process.
Quals: quals_track.py
"""
import sys
sys.dont_write_bytecode = True
# TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
import os, re, json, time, shlex, signal, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, 'runs')
POLL = 10                                              # seconds between an adopted process's checks


def program(cmd):
    """The command's script: its first argument ending in .py, else its first word's name."""
    return os.path.basename(next((a for a in cmd if a.endswith('.py')), cmd[0]))


def identity(pid):
    """(stat, start time, command) of the live process with this pid, as ps prints them, or None if there is none (a
    zombie is none)."""
    out = subprocess.run(['ps', '-o', 'stat=,lstart=,command=', '-p', str(pid)], capture_output=True, text=True).stdout
    m = re.fullmatch(r'\s*(\S+)\s+(\w{3} \w{3} +\d+ [\d:]+ \d{4})\s+(.*?)\s*', out, re.S)
    return None if m is None or m[1].startswith('Z') else (m[1], m[2], m[3])


def start(name, target, found, fields):
    """Writes the record's start, whole: aside, then linked into place, which fails if a record of that name exists."""
    # TODO: error copy; says the run's name may hold only letters, digits, dots, underscores and hyphens
    assert re.fullmatch(r'[\w.-]+', name), f'Claude: "a run name of letters, digits, ., _ and - only, not {name!r}"'
    # TODO: error copy; says the target must be N:M, the question m*(N) >= M?
    assert re.fullmatch(r'\d+:\d+', target), f'Claude: "a target of the form N:M, not {target!r}"'
    os.makedirs(RUNS, exist_ok=True)
    path, aside = os.path.join(RUNS, name + '.jsonl'), os.path.join(RUNS, f'.{name}.{os.getpid()}.tmp')
    rec = dict(event='start', name=name, target=target, found=None if found is None else os.path.abspath(found),
               **fields, tracker=os.getpid())
    with open(aside, 'x', encoding='utf-8') as f: f.write(json.dumps(rec) + '\n')
    try:
        # TODO: error copy; says a run of this name has a record already, so nothing was written
        assert not os.path.exists(path), f'Claude: "the run {name} has a record already: {path}"'
        os.link(aside, path)
    finally:
        os.unlink(aside)
    return path


def end(path, status):
    with open(path, 'a', encoding='utf-8') as f: f.write(json.dumps(dict(event='end', time=time.time(), status=status)) + '\n')


def run(name, target, found, cmd):
    child = subprocess.Popen(cmd)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP): signal.signal(s, lambda signum, frame: child.send_signal(signum))
    path = start(name, target, found, dict(program=program(cmd), command=shlex.join(cmd), cwd=os.getcwd(),
                                           adopted=False, pid=child.pid, time=time.time()))
    status = child.wait()
    end(path, status)
    raise SystemExit(status)


def adopt(name, target, found, pid):
    me = identity(pid)
    # TODO: error copy; says no live process has this pid, so nothing was written
    assert me is not None, f'Claude: "no live process {pid}"'
    cmd = me[2]
    began = time.mktime(time.strptime(me[1], '%a %b %d %H:%M:%S %Y'))
    path = start(name, target, found, dict(program=program(shlex.split(cmd)), command=cmd, cwd=os.getcwd(),
                                           adopted=True, pid=pid, started=me[1], time=began))
    while (identity(pid) or (None, None))[1] == me[1]: time.sleep(POLL)
    end(path, None)


def main(argv):
    # TODO: error copy; says how to run the script, in its two modes
    usage = 'Claude: "usage: track.py run NAME N:M [--found FILE] -- COMMAND ...  |  track.py adopt NAME N:M PID [--found FILE]"'
    assert len(argv) >= 3 and argv[0] in ('run', 'adopt'), usage
    mode, name, target, rest = argv[0], argv[1], argv[2], argv[3:]
    if mode == 'run':
        assert '--' in rest, usage
        opts, cmd = rest[:rest.index('--')], rest[rest.index('--') + 1:]
        assert cmd and len(opts) in (0, 2) and opts[:1] in ([], ['--found']), usage
        run(name, target, opts[1] if opts else None, cmd)
    assert len(rest) in (1, 3) and rest[0].isdigit() and rest[1:2] in ([], ['--found']), usage
    adopt(name, target, rest[2] if len(rest) == 3 else None, int(rest[0]))


if __name__ == '__main__':
    main(sys.argv[1:])
