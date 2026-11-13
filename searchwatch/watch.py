#!/usr/bin/env python3
"""Fable 5.2's watcher (2026-11-11; dreeves: "the search progress code seems like a shitshow; can you revamp it? reread
AGENT.md first. anti-magic anti-magic anti-magic. "Find where the watcher decides which searches get an odds history"
is such a red flag. please kill all if-statements."): it copies the tracked searches' records into the data file of
index.html's section "Search progress".

    python3 -B searchwatch/watch.py            writes the data file once
    python3 -B searchwatch/watch.py --watch    and again every REFRESH seconds; one watcher at a time (a lock in runs/,
                                               runs/watch.lock, which holds the watcher's pid: stop it with kill PID)

It holds no model of any search and no table of searches.  What it writes of a search is in the search's records
(track.py, whose vocabulary this uses: search, record, estimate, estimator, state, span, passes) and in the machine's
CPU intervals (cpu.py): a search's estimator says how far along it is, and this file says it again in the page's form.

  data file  pagedata/progress.js: one call, progressData({"made", "runs"});, made the snapshot's time in whole seconds
             and runs the searches' entries, by label and target, then the earlier searches'.  Rewritten only when an entry changed (dreeves,
             2026-11-09: "i guess it could be a little smarter and not update a file that's in version control with a
             new as-of time that isn't meaningful").
  entry      a search's part of the data file (entry), every search's the same fields:
               search, n, order   its label and its target N:M;
               state              running while a run of it runs, else frozen while one is stopped, else ended;
               outcome            found if its runs' found files hold a line; else none if the last of its runs to
                                  stop ended with status 0 or null, however the runs before it went (a search that
                                  finishes in its fourth run finished); else null (the page calls an ended search with
                                  no outcome aborted);
               so_far             its seconds of running: its passes';
               runs               how many runs it has, and how many running, frozen, ended and aborted, and found, the
                                  lines of its found files (each file once; a file not there yet holds none);
               statuses, depth, keys, groups, counts
                                  its dots, as the page's sea reads them: one block, keyed by the target, a dot per run
                                  in the order they started, its digit the index in statuses of settled (an ended run),
                                  open (aborted), pending (frozen) or running, and the count of each;
               to_go, basis, work its latest estimate's time to go, basis, and unit, done, rate and total;
               etas               its estimates' history, [time, its seconds of running before then, to_go's median,
                                  lo, hi] of each, thinned evenly to at most ETA_POINTS, the last kept;
               odds               {prior: its latest estimate's, since: its first start, exists: [time, P(exists)] of
                                  the same estimates as etas};
               pending            [time, its seconds of running before then, nodes pending] of the same estimates
                                  as etas that count them (2026-11-12, Opus 5.5; dreeves: "we used to have number of
                                  open nodes as a graph"; none for a search that counts none, lindy.py's);
               finished           the same of tasks finished (that evening; dreeves: "sure, let's get the count of
                                  finished tasks over time"; none for a search that counts none, lindy.py's);
               cpu                its CPU series (cpu_series);
               stale              null, or the time of the snapshot its data are from (snapshot).
             A search shows from its first estimate: one whose runs have none yet is in no snapshot.  A running
             search's latest estimate is at most track.STALE seconds old (asserted).
  earlier    the searches of before 2026-11-11 that ran an hour or more, whose records are of another form: their
             entries, in this form, in pagedata/progress-earlier.json, a list, frozen (made once, from the last data
             file of the watcher before this one: scratch/revamp-20261111/convert.py).  The watcher adds them to every
             snapshot after the live searches' and makes nothing of them.

Quals: quals_watch.py
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, glob, fcntl, traceback, collections
import cpu, track

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above searchwatch/
JS = os.path.join(ROOT, 'pagedata', 'progress.js')
EARLIER = os.path.join(ROOT, 'pagedata', 'progress-earlier.json')
REFRESH = 60                    # seconds between snapshots under --watch (the page reloads the data file as often)
NICE = 15                       # the niceness the process lowers itself to
ETA_POINTS = 400                # the most estimates an entry's history carries
CPU_POINTS = 480                # the most rows an entry's CPU series carries: about a pixel of its chart each
STATUSES = ['settled', 'open', 'pending', 'running']                              # a dot's status, by its digit
DIGIT = dict(ended='0', aborted='1', frozen='2', running='3')                     # a run's dot, by its state


def thin(rows, most):
    """rows (one at least), thinned evenly to at most `most` of them or one more: every k-th from the first, k the
    least that leaves at most `most`, and the last."""
    step = -(-len(rows) // most)
    return [rows[i] for i in sorted(set(range(0, len(rows), step)) | {len(rows) - 1})]


def found(runs):
    """The lines of the runs' found files, each file once, whole lines only; a file not there yet holds none."""
    files = sorted({r[0]['found'] for r in runs} - {None})
    return sum(open(f, 'rb').read().count(b'\n') for f in files if os.path.exists(f))


def cpu_series(rows, passes, names):
    """A search's CPU series (dreeves, 2026-11-07: "could we get a nice CPU usage graph on the search page? similar to
    what activity monitor shows. three colors: one for the search, one for all other processes on the machine, and one
    for idle, if any", then "maybe aligned with the ETA graph"): of rows, the machine's intervals (cpu.py's), those that
    name one of names, its runs' (the sampler followed them), each as [the search's hours of running at its start and
    at its end (the ETA chart's x), its end's time, the search's share (its runs' summed), other processes' (the rest
    of the busy share), idle]; with more than CPU_POINTS, consecutive ones merged k at a time (k the least that leaves
    at most CPU_POINTS), their shares weighted by their durations, but never across a gap (an interval that does not
    start where the last ended)."""
    mine = [(a, b, idle, sum(share[name] for name in names & set(share))) for a, b, idle, share in rows if names & set(share)]
    k = -(-len(mine) // CPU_POINTS)
    starts = [i for i, row in enumerate(mine) if i == 0 or mine[i - 1][1] != row[0]]     # where a stretch with no gap starts
    chunks = [mine[j:min(j + k, e)] for i, e in zip(starts, starts[1:] + [len(mine)]) for j in range(i, e, k)]

    def merged(chunk):
        seconds = sum(b - a for a, b, _, _ in chunk)
        idle, search = (sum(row[i] * (row[1] - row[0]) for row in chunk) / seconds for i in (2, 3))
        return [round(track.running(passes, chunk[0][0]) / 3600, 5), round(track.running(passes, chunk[-1][1]) / 3600, 5),
                int(chunk[-1][1]), round(search, 4), round(1 - idle - search, 4), round(idle, 4)]
    return [merged(chunk) for chunk in chunks]


def entry(key, runs, procs, now, rows):
    """The entry (see the docstring) of the search key, (label, target), whose runs' records are runs (one estimate
    among them at least), as the live processes procs (track.processes) show it at time now, with the machine's CPU
    intervals rows."""
    runs = [track.checked(r) for r in runs]
    states, spans = [track.state(r, procs) for r in runs], [track.span(r, procs, now) for r in runs]
    passes, last = track.passes(spans), max(zip(spans, states), key=lambda x: x[0][1])[1]      # last: the state of the last run to stop
    estimates = sorted((x for r in runs for x in r if x['event'] == 'estimate'), key=lambda x: x['time'])
    latest, history = estimates[-1], thin(estimates, ETA_POINTS)
    state = next((s for s in ('running', 'frozen') if s in states), 'ended')
    # TODO: error copy; says a running search's latest estimate is older than its estimator promised (track.py's STALE), naming the search and the estimate's time
    assert state != 'running' or now - latest['time'] <= track.STALE, \
        f'Fable 5.2: "the latest estimate of {" ".join(key)}, made at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest["time"]))}, is more than {track.STALE:.0f} s old"'
    hits, dots = found(runs), ''.join(DIGIT[s] for s in states)
    n, order = map(int, key[1].split(':'))
    return dict(
        search=key[0], n=n, order=order, state=state,
        outcome='found' if hits else 'none' if last == 'ended' else None,
        so_far=track.running(passes, now),
        runs=dict(runs=len(runs), **{s: states.count(s) for s in ('running', 'frozen', 'ended', 'aborted')}, found=hits),
        statuses=STATUSES, depth=0, keys=[key[1]], groups=[dots], counts={s: dots.count(str(i)) for i, s in enumerate(STATUSES)},
        to_go=latest['to_go'], basis=latest['basis'], work={k: latest[k] for k in ('unit', 'done', 'rate', 'total')},
        etas=[[int(x['time']), round(track.running(passes, x['time']), 1)] + [round(x['to_go'][k], 1) for k in ('median', 'lo', 'hi')] for x in history],
        odds=dict(prior=latest['prior'], since=runs[0][0]['time'], exists=[[int(x['time']), x['exists']] for x in history]),
        **{k: [[int(x['time']), round(track.running(passes, x['time']), 1), x[k]] for x in history if x[k] is not None] for k in ('pending', 'finished')},
        cpu=cpu_series(rows, passes, {r[0]['name'] for r in runs}), stale=None)


def report(what):
    """Write what went wrong to the watcher's log (stderr), stamped, with the traceback of the exception being handled."""
    print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} Fable 5.2: "{what}"', file=sys.stderr, flush=True)
    traceback.print_exc()


def snapshot(runs, intervals, procs, now, kept):
    """The entries of the searches whose records are in the directory runs and have an estimate, by label and target,
    as of time now, with the CPU intervals of the file intervals.  A search whose entry cannot be made (a record that
    does not hold to its form; a running search's estimate too old) is reported and leaves the others theirs: it keeps
    its last good entry from kept, {key: ([entry], the time of its snapshot)}, marked stale with that time, or is
    left out with none; kept takes each entry made."""
    searches, rows, out = track.searches(runs), cpu.read(intervals), []
    owner = {r[0]['name']: key for key, records in searches.items() for r in records}
    mine = collections.defaultdict(list)                 # each search's intervals, by its runs' names
    for row in rows:
        for key in {owner[name] for name in row[3] if name in owner}: mine[key].append(row)
    shown = {key: records for key, records in searches.items() if any(x['event'] == 'estimate' for r in records for x in r)}
    for key, records in shown.items():
        try:
            kept[key] = ([entry(key, records, procs, now, mine[key])], int(now))
            out += kept[key][0]
        except Exception:
            # TODO: log line; says this search's entry could not be made, so the data file shows its last good one, marked stale, or none
            report(f'{" ".join(key)} failed: its last good entry stands, marked stale')
            last, t = kept.get(key, ([], None))
            out += [dict(e, stale=t) for e in last]
    return out


def write_atomic(path, text):
    """Write text to path through a temporary file next to it, renamed over path: a reader opens the old file or the
    new one, whole, never part of one."""
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def text_of(entries): return json.dumps(entries, separators=(',', ':'), ensure_ascii=False)


def read(path):
    """The data file at path, as JSON (asserted to be one progressData(...); call)."""
    text = open(path, encoding='utf-8').read()
    assert text.startswith('progressData(') and text.endswith(');\n'), path
    return json.loads(text.removeprefix('progressData(').removesuffix(');\n'))


def once(js, runs, intervals, earlier, kept, said):
    """One snapshot: the data file at js rewritten if its entries, the live searches' and then the earlier ones, are
    no longer those last written, whose text said is; returns the entries' text."""
    now = time.time()
    text = text_of(snapshot(runs, intervals, track.processes(), now, kept) + earlier)
    if text != said: write_atomic(js, f'progressData({{"made":{int(now)},"runs":{text}}});\n')
    return text


def main(argv):
    # TODO: error copy; says how to run the watcher: with no argument to write the data file once, or with --watch to keep rewriting it
    assert argv in ([], ['--watch']), 'Fable 5.2: "usage: python3 -B searchwatch/watch.py [--watch]"'
    os.nice(max(0, NICE - os.nice(0)))
    lock = open(os.path.join(track.RUNS, 'watch.lock'), 'a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)             # one watcher at a time: refused at once if another holds it
    lock.truncate(0)
    print(os.getpid(), file=lock, flush=True)                    # the lock file names its holder: stop the watcher by that pid
    earlier = json.load(open(EARLIER, encoding='utf-8'))        # the earlier searches' entries: the file is part of the page's data
    was = [read(path) for path in glob.glob(JS)]                 # the data file as it stands, if there is one
    kept = {(e['search'], f'{e["n"]}:{e["order"]}'): ([dict(e, stale=None)], e['stale'] or data['made']) for data in was for e in data['runs']}
    said = once(JS, track.RUNS, cpu.FILE, earlier, kept, ''.join(text_of(data['runs']) for data in was))   # a first snapshot that fails says so and ends the watcher
    while argv:
        time.sleep(REFRESH)
        try:
            said = once(JS, track.RUNS, cpu.FILE, earlier, kept, said)
        except Exception:               # outside every search's entry: the watcher goes on, its data file as last written
            # TODO: log line; says this snapshot failed outside any search's entry, so the data file stays as last written
            report('the snapshot failed; the data file stays as it was')


if __name__ == '__main__':
    main(sys.argv[1:])
