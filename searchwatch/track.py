#!/usr/bin/env python3
"""The launcher every search runs under, so that the Search progress section on index.html shows it with no code of
its own (dreeves, 2026-10-28: "can we rearchitect things so that always happens easily and automatically?", then,
of the names track.py and runs/<name>.jsonl, "those names are fine, go ahead").  track.py writes the run's record,
which the watcher reads (watch.py); the search itself is not changed.  This file is the one home of the record's form:
the watcher and the estimators read records through its functions (lines, checked, searches, state, span, passes,
running).

Since 2026-11-11 (Fable 5.2; dreeves, of whether different searches on one cell should show separately: "sounds like
obviously yes"; of the bar and the probability graph that one search alone had: "the search progress code seems like a
shitshow; can you revamp it? ... anti-magic anti-magic anti-magic") a launch names its search and its estimator, both
required, and the record carries everything the page shows of the search, so that the watcher holds no model and no
table of searches.

  search    the runs launched under one label at one target: one box of the page.  A label is the launcher's word for
            what is being tried (form-tree, tilted, ...): a restart of a search takes its label, another kind of search
            at the same target another.
  record    runs/NAME.jsonl, JSON lines.  The first, {"event": "start", "name", "search", "target", "estimator",
            "command", "cwd", "found", "adopted", "pid", "tracker", "time"}: search the label; target "N:M", the question
            m*(N) >= M?; estimator and command as a shell would write them; found the absolute path of a file whose
            lines count the search's results (a witness file), or null; pid the run's process and tracker track.py's
            own; time when the run's process began (epoch seconds; for an adopted one, its start time as ps prints it,
            to the second, also kept as "started").  It appears whole (written aside, then linked into place).  A
            run whose process could not be made has pid null.  Then the run's estimates, a line each.  The last, once the run's process ends: {"event": "end", "time", "status"},
            its exit status (a negative one a signal's), or null for an adopted process, whose status track.py cannot
            read.  And, anywhere between the start and the end, at most one {"event": "pause", "time"} (track.py pause):
            the run's stop, then or later, is a pause, not an abort.
  estimate  {"event": "estimate", "time", "basis", "unit", "done", "rate", "total": {"median", "lo", "hi"}, "to_go":
            {"median", "lo", "hi"}, "prior", "exists", "pending", "finished"}: what is known of the run's search as of time (epoch seconds), by
            its estimator: basis, the estimator's key (lindy, formtree), by which the page picks its words about it;
            unit, what the search's work is counted in (seconds, nodes); done, the work done so far, and rate, the work
            a second of running; total, the work done when the search has run its course, and to_go, the seconds of
            running until then, each its median and the ends of its band (chance.COVERAGE's); prior, the probability
            that what is searched for exists, before the search, and exists, that probability given none found so far;
            and pending (Opus 5.5, 2026-11-12; dreeves: "we used to have number of open nodes as a graph"), the number of
            pieces of work the search has named and not yet finished, a whole number (a form tree's: its nodes named, a
            start node or one a task spilled, with no verdict yet, those being checked among them: its driver's "left"),
            or null for a search that counts none (lindy.py's); and finished (Opus 5.5, that evening; dreeves: "sure,
            let's get the count of finished tasks over time"), the number of pieces of work the search has finished, a
            whole number (a form tree's: its tasks with a verdict, each ended with its subtree closed or its unfinished
            branches spilled), or null for a search that counts none (lindy.py's).
  estimator a Python script, named at launch with its arguments: the tracker runs it (python3 -B SCRIPT ARGS ..., in the
            tracker's directory, the record's absolute path in the environment variable TRACK_RECORD) once when the
            run starts, again every PERIOD seconds while it runs, and once more when the run's process has ended
            (Fable 5.2, 2026-11-13; dreeves: "sure, that sounds cleaner to get exact counts and probability 0 when we
            completed a proof"), so that a record's last estimate is of the search as it ended.  Each time it appends
            one estimate to the record, whole, opening it to append without creating it (os.O_APPEND without
            os.O_CREAT), and exits.  One still running when the next is due is killed, and the last one EST_GRACE
            seconds after the run ended, before the end is written.  The estimator's exit status is not read: one that
            fails writes no estimate and says why on the tracker's stderr, and the watcher shows a running search
            whose latest estimate is older than STALE seconds stale (dreeves, 2026-11-04, of an estimate left standing
            by a dead or stalled producer: "can we be more anti-postel than that?").  A run goes on until its end is
            written: with no end in its record, while its process or, that gone, its tracker lives (stat_of), so that
            its last estimate is taken of a run still going.  The command may append estimates too (its record is
            named to it the same way).
            searchwatch/lindy.py is the estimator of a search that knows nothing but its age.
  run       python3 -B searchwatch/track.py run NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- COMMAND ...: starts
            COMMAND, writes the start, runs the estimator while it waits, writes the end and exits with COMMAND's
            status.  A hidden exclusive reservation precedes the launch.  The command owns a new process group, cleaned
            even after a normal exit. SIGTERM, SIGINT and SIGHUP cancel that group and are recorded as negative
            statuses; other launcher failures record status 1.
  pause     python3 -B searchwatch/track.py pause NAME (Opus 5.5, 2026-11-13; dreeves, of the 480:14 form tree stopped
            that morning to free the cores for another search and queued to resume: "should 480:14 formtree say
            "paused" rather than "aborted"?", then "go ahead and generalize track.py to record pause vs abort or
            whatever"): marks the run's stop a pause, its search to go on in a later run from the work it kept, by
            appending the pause line to its record.  It stops nothing: stop the run as ever (SIGTERM to its tracker,
            the start line's tracker), after.  A run's stop is a pause if its record holds a pause and it did not
            finish (status 0): the watcher calls the run, and a search whose last run to stop is one, paused, where it
            would say aborted.  Refuses, writing nothing: no record of that NAME, or one that holds an end or a pause
            already (a run's stop is marked before it ends, so that its end stays its record's last line).
  adopt     python3 -B searchwatch/track.py adopt NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- PID: for a process
            started without track.py: writes the start (its command as ps prints it, and "started", its start time as
            ps prints it, which with its pid identifies it), polls it every POLL seconds, running the estimator as for
            a launched one, and writes the end once no live process has that pid and start time.  A SIGKILL'd or
            crashed tracker writes no end: the watcher then shows the run aborted once its process is gone.
run and adopt refuse, writing nothing: a NAME or a SEARCH of other than letters, digits, '.', '_' and '-'; a NAME whose record
exists (a name is one run); a target not N:M; an ESTIMATOR that is no file; an adopted PID with no live process.
Quals: quals_track.py
"""
import sys
sys.dont_write_bytecode = True
# TODO: error copy; says the script refuses to run under python -O, which would strip its assertions
if not __debug__: raise SystemExit('Claude: "refusing to run without assertions (python -O)"')
import os, re, json, math, time, glob, shlex, signal, contextlib, subprocess
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above searchwatch/ (this file was at the root until 2026-11-10, dreeves's README [REF])
RUNS = os.path.join(HERE, 'runs')
POLL = 10                                              # seconds between an adopted process's checks
GRACE = 2                                             # seconds before killing remaining owned processes
CANCEL = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
RECORD = 'TRACK_RECORD'                               # the environment variable naming the record to its command
PERIOD = 300.0                                        # seconds between a run's estimates
EST_GRACE = 30.0                                      # seconds a run's last estimator has to finish once the run ended
STALE = 1200.0                                        # seconds: the oldest a running search's latest estimate may be
START = {'event', 'name', 'search', 'target', 'estimator', 'command', 'cwd', 'found', 'adopted', 'pid', 'tracker', 'time'}
PAUSE = {'event', 'time'}
ESTIMATE = {'event', 'time', 'basis', 'unit', 'done', 'rate', 'total', 'to_go', 'prior', 'exists', 'pending', 'finished'}
BAND = {'median', 'lo', 'hi'}


def identity(pid):
    """(stat, start time, command) of the live process with this pid, as ps prints them, or None if there is none (a
    zombie is none)."""
    out = subprocess.run(['ps', '-o', 'stat=,lstart=,command=', '-p', str(pid)], capture_output=True, text=True).stdout
    m = re.fullmatch(r'\s*(\S+)\s+(\w{3} \w{3} +\d+ [\d:]+ \d{4})\s+(.*?)\s*', out, re.S)
    return None if m is None or m[1].startswith('Z') else (m[1], m[2], m[3])


def reserve(name, search, target, estimator):
    """Validate and exclusively reserve a name before any command starts. A crash leaves its reservation for review."""
    # TODO: error copy; says the run's name may hold only letters, digits, dots, underscores and hyphens
    assert re.fullmatch(r'[\w.-]+', name), f'Claude: "a run name of letters, digits, ., _ and - only, not {name!r}"'
    # TODO: error copy; says the search's label may hold only letters, digits, dots, underscores and hyphens
    assert re.fullmatch(r'[\w.-]+', search), f'Fable 5.2: "a search label of letters, digits, ., _ and - only, not {search!r}"'
    # TODO: error copy; says the target must be N:M, the question m*(N) >= M?
    assert re.fullmatch(r'\d+:\d+', target), f'Claude: "a target of the form N:M, not {target!r}"'
    # TODO: error copy; says the estimator named at launch is no file, so nothing was launched
    assert os.path.isfile(estimator[0]), f'Fable 5.2: "the estimator {estimator[0]!r} is no file"'
    os.makedirs(RUNS, exist_ok=True)
    path, reservation = os.path.join(RUNS, name + '.jsonl'), os.path.join(RUNS, '.' + name + '.reserved')
    with open(reservation, 'x', encoding='utf-8'): pass
    try:
        # TODO: error copy; the reserved run name already has a record and cannot launch another command
        assert not os.path.exists(path), f'Nomen cursus iam adhibitum: {name}'
    except BaseException:
        os.unlink(reservation)
        raise
    return reservation


def start(name, target, found, fields):
    """Writes the record's start, whole: aside, then linked into place, which fails if a record of that name exists."""
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


def live(pgid):
    """The pids of process group pgid's live members, as ps lists them (a zombie, stat Z, is dead already: only its
    parent's wait takes it out of the group)."""
    out = subprocess.run(['ps', '-A', '-o', 'pid=,pgid=,stat='], capture_output=True, text=True, check=True).stdout
    return [int(p) for p, g, stat in (line.split() for line in out.splitlines()) if int(g) == pgid and not stat.startswith('Z')]


def group_signal(pid, signum):
    """Signal an owned process group.  killpg fails when the group has no live member, and such a group needs no
    cleanup: ESRCH when it has no member at all, and on macOS EPERM when its members are all zombies, dead already and
    awaiting their parents' wait (2026-10-31: a seed's forked CVP child, left a zombie when the seed was killed; six
    trackers died of that EPERM and wrote no end).  That no live member remains is asserted."""
    try:
        os.killpg(pid, signum)
    except (ProcessLookupError, PermissionError):
        members = live(pid)
        # TODO: error copy; says signalling the run's process group failed although it has live members, naming them
        assert not members, f'Claude: "could not signal process group {pid}, whose live members are {members}"'


def cleanup(child, signum=signal.SIGTERM):
    """Forward cancellation, unconditionally kill remaining descendants, and reap the direct child."""
    group_signal(child.pid, signum)
    try:
        child.wait(timeout=GRACE)
    except subprocess.TimeoutExpired:
        pass
    finally:
        group_signal(child.pid, signal.SIGKILL)
        child.wait()


def estimate(estimator, path, ests):
    """Starts the run's estimator on its record at path, and lists its process in ests: with the cancellation signals
    blocked, so that none is started and not listed (it inherits the block; settle kills it with SIGKILL), and in a
    session of its own, so that no signal to the tracker's or the run's group reaches it."""
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, CANCEL)
    ests.append(subprocess.Popen([sys.executable, '-B', *estimator], env=dict(os.environ, **{RECORD: path}), start_new_session=True))
    signal.pthread_sigmask(signal.SIG_SETMASK, mask)


def settle(proc, seconds):
    """Waits up to seconds for proc to end, then kills it (nothing to kill once it has ended) and reaps it."""
    with contextlib.suppress(subprocess.TimeoutExpired): proc.wait(timeout=seconds)
    proc.kill()
    proc.wait()


def follow(estimator, path, ests, going):
    """A run's estimates: its estimator started now, and again after each going(PERIOD), which waits up to that many
    seconds for the run's end and says whether the run goes on: so every period while it runs, and once more when it
    has ended (2026-11-13; dreeves, of a finished search whose box kept the estimate of 81 s before its end: "sure,
    that sounds cleaner to get exact counts and probability 0 when we completed a proof"): the run's last estimate, of
    the search as it ended, which the caller settles before it writes the end.  The one before, if still running, is
    killed first each time."""
    estimate(estimator, path, ests)
    on = True
    while on:
        on = going(PERIOD)
        settle(ests[-1], 0)
        estimate(estimator, path, ests)


def waited(child, seconds):
    """Whether child ended within seconds."""
    with contextlib.suppress(subprocess.TimeoutExpired): child.wait(timeout=seconds)
    return child.returncode is not None


def lasted(pid, started, seconds):
    """Whether the process pid, started then (as ps prints it), still lives after seconds, polled every POLL seconds;
    said as soon as it is gone."""
    until = time.time() + seconds
    while (alive := (identity(pid) or (None, None))[1] == started) and time.time() < until: time.sleep(min(POLL, seconds))
    return alive


class Cancelled(BaseException):
    """A cancellation signal, handled after the owned group has been cleaned."""


def cancel(signum, frame):
    raise Cancelled(signum)


def run(name, search, target, found, estimator, cmd):
    reservation = reserve(name, search, target, estimator)
    fields = dict(search=search, estimator=shlex.join(estimator), command=shlex.join(cmd), cwd=os.getcwd(), adopted=False,
                  pid=None, time=time.time())
    child, path, status, signum, ests = None, None, 1, signal.SIGTERM, []
    handlers = {s: signal.getsignal(s) for s in CANCEL}
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, CANCEL)
    try:
        for s in CANCEL: signal.signal(s, cancel)
        # Restore the inherited mask in the child before exec; cancellation stays blocked until the parent owns it.
        wrapper = ('import os,signal,sys;signal.pthread_sigmask(signal.SIG_SETMASK,'
                   + repr([int(s) for s in mask]) + ');os.execvp(sys.argv[1],sys.argv[1:])')
        child = subprocess.Popen([sys.executable, '-c', wrapper, *cmd], start_new_session=True,
                                 env=dict(os.environ, **{RECORD: os.path.join(RUNS, name + '.jsonl')}))
        fields['pid'] = child.pid
        path = start(name, target, found, fields)
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        follow(estimator, path, ests, lambda seconds: not waited(child, seconds))
        status = child.returncode
    except Cancelled as exc:
        signum = exc.args[0]
        status = -signum
    finally:
        # Repeated cancellation must not interrupt cleanup, recording, or releasing the reservation.
        for s in CANCEL: signal.signal(s, signal.SIG_IGN)
        try:
            if child is not None: cleanup(child, signum)
            if path is None: path = start(name, target, found, fields)
            for est in ests[-1:]: settle(est, EST_GRACE)       # the last estimator, if any, before the end is written
            end(path, status)
            os.unlink(reservation)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            for s, handler in handlers.items(): signal.signal(s, handler)
    raise SystemExit(status)


def adopt(name, search, target, found, estimator, pid):
    me = identity(pid)
    # TODO: error copy; says no live process has this pid, so nothing was written
    assert me is not None, f'Claude: "no live process {pid}"'
    reservation = reserve(name, search, target, estimator)
    cmd = me[2]
    began = time.mktime(time.strptime(me[1], '%a %b %d %H:%M:%S %Y'))
    path = start(name, target, found, dict(search=search, estimator=shlex.join(estimator), command=cmd, cwd=os.getcwd(),
                                           adopted=True, pid=pid, started=me[1], time=began))
    os.unlink(reservation)
    ests = []
    follow(estimator, path, ests, lambda seconds: lasted(pid, me[1], seconds))
    settle(ests[-1], EST_GRACE)
    end(path, None)


def pause(name):
    """Marks the run name's stop a pause (see the docstring): appends {"event": "pause", "time"} to its record, which
    holds no end and no pause yet, whole and never creating it (append).  A run that ends as it is marked would leave
    the pause after its end: the record is checked again after, and fails loudly then."""
    # TODO: error copy; says the run's name may hold only letters, digits, dots, underscores and hyphens
    assert re.fullmatch(r'[\w.-]+', name), f'Opus 5.5: "a run name of letters, digits, ., _ and - only, not {name!r}"'
    path = os.path.join(RUNS, name + '.jsonl')
    # TODO: error copy; says there is no run of that name to mark paused
    assert os.path.isfile(path), f'Opus 5.5: "no run {name}: no record {path}"'
    events = [x['event'] for x in checked(lines(path))]
    # TODO: error copy; says the run has ended or is marked paused already, so it cannot be marked paused now
    assert 'end' not in events and 'pause' not in events, f'Opus 5.5: "the run {name} has ended or is paused already: {events[-3:]}"'
    append(path, dict(event='pause', time=time.time()))
    checked(lines(path))


def append(path, line):
    """Appends line, a JSON object, to the record at path, whole (one write), never creating the record: as an
    estimator writes its estimate."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try: os.write(fd, (json.dumps(line) + '\n').encode())
    finally: os.close(fd)


def lines(path):
    """The record at path: its whole lines, as JSON (a last line still being written left out)."""
    with open(path, 'rb') as f: data = f.read()
    return [json.loads(x) for x in data[:data.rfind(b'\n') + 1].splitlines()]


def number(x): return type(x) in (int, float) and math.isfinite(x)


def band(b):
    """Whether b is an estimate's median and band: {median, lo, hi}, numbers, 0 <= lo <= median <= hi."""
    return type(b) is dict and set(b) == BAND and all(number(v) for v in b.values()) and 0 <= b['lo'] <= b['median'] <= b['hi']


def checked(record):
    """record, a record's lines, once they hold to the record's form (see the docstring; asserted): its start, then
    its estimates in time order, none before the start, then at most its end; and between the start and the end at
    most one pause, not before the start."""
    events = [x.get('event') for x in record]
    # TODO: error copy; says a record holds other than its start, then estimates and at most one pause, then at most its end, giving its lines' events
    assert re.fullmatch(r'start(,estimate)*(,pause)?(,estimate)*(,end)?', ','.join(map(str, events))), f'Fable 5.2: "a record runs {events}"'
    first, estimates = record[0], [x for x in record if x['event'] == 'estimate']
    for x in record[1:]:
        assert x['event'] != 'pause' or (set(x) == PAUSE and number(x['time']) and x['time'] >= first['time']), x
    assert set(first) - {'started'} == START and ('started' in first) == first['adopted'], first
    assert type(first['search']) is str and re.fullmatch(r'\d+:\d+', first['target']) and number(first['time']), first
    for x in estimates:
        assert set(x) == ESTIMATE and type(x['basis']) is str and type(x['unit']) is str, x
        assert all(number(x[k]) for k in ('time', 'done', 'rate', 'prior', 'exists')) and band(x['total']) and band(x['to_go']), x
        assert 0 <= x['done'] <= x['total']['lo'] and x['rate'] > 0 and 0 <= x['prior'] <= 1 and 0 <= x['exists'] <= 1, x
        assert all(x[k] is None or (type(x[k]) is int and x[k] >= 0) for k in ('pending', 'finished')), x
    times = [first['time']] + [x['time'] for x in estimates]
    assert times == sorted(times), times
    return record


def searches(runs=RUNS):
    """The searches of the directory runs: {(label, target): its runs' records, in the order the runs started}, of
    every record there, by their start lines alone: whoever reads a search checks its records (checked), so that a
    record that does not hold to its form fails its own search and no other."""
    records = sorted((lines(path) for path in glob.glob(os.path.join(runs, '*.jsonl'))), key=lambda r: (r[0]['time'], r[0]['name']))
    return {key: [r for r in records if (r[0]['search'], r[0]['target']) == key]
            for key in sorted({(r[0]['search'], r[0]['target']) for r in records})}


def search_of(path, now):
    """The search of the record at path, as an estimator reads it at time now: (its runs' records, by the records
    beside that one, and its passes then)."""
    first, procs = lines(path)[0], processes()
    runs = [checked(r) for r in searches(os.path.dirname(path))[first['search'], first['target']]]
    return runs, passes([span(r, procs, now) for r in runs])


def processes():
    """{pid: its stat as ps prints it} of the live processes, zombies left out."""
    out = subprocess.run(['ps', '-A', '-o', 'pid=,stat='], capture_output=True, text=True, check=True).stdout
    return {int(pid): stat for pid, stat in (line.split() for line in out.splitlines()) if not stat.startswith('Z')}


def stat_of(record, procs):
    """How a run stands among the live processes procs (processes): its process's stat as ps prints it; that gone, its
    tracker's, which outlives the run's process by its closing steps (the run's last estimate, then the end;
    2026-11-13); 'gone' with neither, the tracker dead before it wrote the end."""
    return procs.get(record[0]['pid']) or procs.get(record[0]['tracker'], 'gone')


def state(record, procs):
    """A run's state by its record and the live processes (processes): with an end, ended if its status is 0, else
    paused if the record holds a pause, else ended if its status is null (an adopted run's, not known), else aborted;
    with none, by stat_of: running while its process or, that gone, its tracker lives, frozen while that one is
    stopped (stat T), and once both are gone (its tracker died before writing the end) paused if the record holds a
    pause, else aborted."""
    last, stat = record[-1], stat_of(record, procs)
    stopped = 'paused' if any(x['event'] == 'pause' for x in record) else 'aborted'   # a stop short of finishing, by the record
    closed = 'ended' if last.get('status') == 0 or (last.get('status') is None and stopped == 'aborted') else stopped
    open_ = stopped if stat == 'gone' else 'frozen' if stat.startswith('T') else 'running'
    return closed if last['event'] == 'end' else open_


def span(record, procs, now):
    """[when the run started, when it stopped]: at its end's time; with no end, now while its process or, that gone,
    its tracker lives (stat_of), else at its last line's time."""
    going = record[-1]['event'] != 'end' and stat_of(record, procs) != 'gone'
    return [record[0]['time'], now if going else record[-1]['time']]


def passes(spans):
    """The stretches during which some run was going: the spans' union, as disjoint [start, end]s in order (spans that
    overlap or touch are one stretch)."""
    out = []
    for a, b in sorted(spans):
        out += [[a, b]] * (not out or a > out[-1][1])           # a new stretch, unless this span starts within the last
        out[-1][1] = max(out[-1][1], b)
    return out


def running(passes, t):
    """The seconds of running before time t: the passes' seconds before it."""
    return sum(max(0, min(b, t) - a) for a, b in passes)


def main(argv):
    # TODO: error copy; says how to run the script, in its two modes: run and adopt, each with the run's name, its search's label, its target, an optional file of results, the estimator and its arguments, then -- and the command or the process's pid
    usage = ('Fable 5.2: "usage: track.py run NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- COMMAND ...  |  '
             'track.py adopt NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- PID  |  track.py pause NAME"')
    if argv[:1] == ['pause']:
        assert len(argv) == 2, usage
        return pause(argv[1])
    assert len(argv) >= 7 and argv[0] in ('run', 'adopt') and '--' in argv[4:], usage
    (mode, name, search, target), cut = argv[:4], argv.index('--', 4)
    opts, subject = argv[4:cut], argv[cut + 1:]
    k = 2 * (opts[:1] == ['--found'])                  # the words of --found FILE, if given
    found, estimator = (opts[1:k] + [None])[0], opts[k:]
    assert estimator and subject, usage
    assert mode == 'run' or (len(subject) == 1 and subject[0].isdigit()), usage
    {'run': lambda: run(name, search, target, found, estimator, subject),
     'adopt': lambda: adopt(name, search, target, found, estimator, int(subject[0]))}[mode]()


if __name__ == '__main__':
    main(sys.argv[1:])
