#!/usr/bin/env python3
"""How far the certified searches of overnight_v5.py have got: the data file of index.html's section "Search progress"
(dreeves, 2026-10-17, in place of the page progress.html this file used to write).

Run:   python3 -B progress.py            writes progress.js once
       python3 -B progress.py --watch    rewrites it every REFRESH seconds until stopped
Either way the process first lowers its priority to nice NICE.  progress.js, next to this file and index.html, is
replaced atomically (see write_atomic), so a reader never sees half of it.  Quals: python3 -B quals_progress.py

For each run (N, ORDER) in RUNS it reads overnight_v5_N_ORDER_journal.jsonl and overnight_v5_N_ORDER.log in the run's
directory (DIRS; see
overnight_v5.py's docstring for their formats and for node, split, pool, budget, verdict and cascade) and the process
list.  The tree's levels are enumerated with overnight_v5.split itself, each node split at most once: the children's
keys are kept in CACHE, a directory git ignores (see save_cache), by run and by the run's geometry
(run_modules.geometry: what decides its splits, which a change of its solver leaves as it was).  Vocabulary, each term
defined once here:
  pass        one run of overnight_v5.py on a journal: a start line of the log and the lines after it.  A later pass
              resumes from the journal, perhaps with larger budgets.  The current pass is the log's last.
  sub-case    a node of the search tree.
  level d     the sub-cases at depth d (fixing counts mod the first d moduli of the cascade): the children, from
              overnight_v5.split, of the level d - 1 sub-cases whose verdict was UNKNOWN (later CLOSED or not).
              Level 0 is the top node.
  status      of a sub-case, under the current pass's budgets:
                settled   its verdict is INFEASIBLE (certbb's proof, checked in exact integer arithmetic) or CLOSED
                          (all its children settled);
                open      UNKNOWN within its budget, at the bottom of the cascade: a leaf left open;
                split     UNKNOWN within its budget, with children, not all of them settled yet;
                pending   no verdict within its budget yet: never reached, or UNKNOWN at a smaller budget in an
                          earlier pass, so that this pass solves it again.
  enumerated  the levels 0..D whose sub-cases are all known: D is the first level with a pending sub-case (the
              children of a pending sub-case are unknown until the search splits it), the bottom of the cascade, or
              DEEPEST, whichever comes first.  Deeper levels are counted from the journal alone.  The enumeration
              must hold every journal key of levels 0..D (asserted), which checks it against the run's own splits.
  state       of a run: ended if no process runs overnight_v5.py N ORDER or the current pass has logged its
              outcome; otherwise frozen if that process or one of its workers (its child processes) is stopped, as by
              SIGSTOP; otherwise running.
  cost        of a sub-case in a pass: the worker seconds (solve plus split) of the log's progress lines for it and
              for the sub-cases below it.
  work        of a pass, at the deepest enumerated level: the sub-cases not settled when the pass began, or touched by
              it, each done (settled or open), partway (split), or pending.
  dating      each journal record is dated by a line of the log: a fresh verdict's record by its node's progress line,
              which search() writes just after it; a CLOSED record by the line of the record before it or by its
              node's latest progress line before it, whichever is later: search() closes a node only after the node's
              own line, and a pass after a handoff closes nodes with no fresh record of its own (the watcher died on
              240@11's last pass, 2026-10-20, when those were dated before it), while a handoff's CLOSED records, for
              leaves no later pass submits, stay before the pass.  So the journal as of any line is the records dated
              by it or earlier (see read_run).
  data file   progress.js (JS), next to index.html, whose section "Search progress" (dreeves, 2026-10-17: "make it a
              collapsible section of index.html -- no separate progress page") loads it while the section is open,
              again every minute, and redraws when the snapshot changed: one call, progressData(...);, of each run's
              state, seconds of running so far and to go, and sea (see js_text).
  live        a journal key not below an INFEASIBLE one.  A sub-case split in one pass and re-solved INFEASIBLE in a
              later one (the width test did that to six of 240@11's on 2026-10-11) keeps its old children's
              records, which no longer count: the levels, the tallies, the open leaves and the sea take the live
              keys only (see live_keys).
  tree order  the keys sorted by their constraints, compared one by one (see tree_order): a node just before its
              descendants, siblings by their count vectors.
  sea         one dot per frontier sub-case (dreeves, 2026-10-17: "a sea of dots for subtrees or whatever,
              color-coded for settled, open, split, etc"): the journal's live keys (see live), the running ones, and
              the cached children of the split ones, less every key that another of them extends; each dot's
              status is the key's, or running.  A split dot is a split sub-case whose children are not known here
              (no cached split and none recorded).  The dots are in tree order, grouped by their sub-case at depth
              SEA_DEPTH (or above the bottom, if that is shallower; a shallower dot is its own group).
  estimate    of a running or frozen run: REPLICATES draws of the current pass's remaining hours of running, from the
              model below; or none, when the model has nothing to draw from.  The data file gives their median (the ETA)
              and their QUANTILES (the band around it); their mean until 2026-10-19, when the boxsplit estimate took a
              Lindy tail (lindy_ball), whose mean is infinite.  Provisional (2026-10-09): the survival-analysis
              design of the workflow in scratch/eta-dist/, ported whole, while that workflow's judges are still out.
  ETA         the median of a snapshot's estimate (dreeves's name for it; its mean until 2026-10-19, as the records
              made before then hold): the hours of running until the current pass ends, as likely more as less, which
              is when the search ends, unless the pass leaves sub-cases open, as 304@9's first did; no
              estimate foresees a later pass.  Each time the data file is made it records its ETA with the estimate's
              range (its draws' QUANTILES), by the snapshot's time, in CACHE (by run and its geometry); the data
              file carries that record (see eta_records), and the section's ETA chart draws it, the range as a shaded
              band: only ETAs actually made, none reconstructed for times before the record began (dreeves,
              2026-10-09), against the search's elapsed running time, whatever its passes (dreeves, 2026-10-10).
The estimate's model, its terms defined once here (overnight_v5.py's search() is the process it models):
  bottom      the depth of the cascade's last level, len(budgets) - 1; a node there is a job of one certbb solve.
  replay      search()'s stack and running jobs as of the state's time t, rebuilt from the current pass's progress
              lines.  Each line says which node finished, and its counts give how many jobs were submitted before it
              (its running + 1 - the previous line's running), how many settled nodes were skipped (its closed count's
              rise, less 1 if the line is INFEASIBLE: search() counts a skipped node closed), and so how many children
              its node pushed (the rest of the waiting count's change), the cache's split if it holds one (asserted
              equal), else that many unnamed children, whom no later pop skips, as no journal has them.  A job
              submitted after line i started at line i's time; the first job started at its own end less its duration.
              Every line's waiting and running are asserted against the replayed stack and running jobs.
  kind        what a pending or running node will cost: 'leaf', a certbb solve at the bottom (a fresh node, or a
              re-solve of a leaf left UNKNOWN at a smaller budget); 'subtree', a fresh node above the bottom, whose
              verdict and split are unknown, so that its whole subtree is to come; 'resplit', a node the journal had
              UNKNOWN within its budget when the pass began, which search() only splits again (seconds, counted as
              free), its children known from the cache; 'skip', a node the journal had settled.
  floor       a leaf kind's previous budget: 0 for a fresh leaf, the earlier UNKNOWN record's budget for a re-solve.  A
              leaf's LP solves lie in (floor, budget]: certbb solves at least one LP per node, and a re-solve replays
              its first floor LP solves exactly (certbb is deterministic).
  speed       seconds per LP solve: the solve seconds over the LP solves (journal lps) of every fresh leaf solve the
              log holds, all passes pooled.  It turns the floor and the budget into seconds; nothing else uses it.
  urn         a Polya urn (Blackwell and MacQueen 1973) with one new ball: one ball per member of a population, and
              each draw takes a uniformly chosen ball and adds its value back as a ball.  A member's ball gives the
              member's value; the new ball gives a new value.  With n balls besides the new one, a draw is new with
              probability 1/(n + 1), the weight Hill's (1968) A(n) gives the next of n exchangeable values beyond
              them all; this is the Dirichlet process's urn with concentration 1 (Ferguson 1973).  Its draws are
              exchangeable, from a distribution that is itself random: fewer members, more spread.  The leaf urn's new
              ball is the gap: log-uniform (the scale-invariant density 1/x, Jeffreys 1961) from the largest member (or
              the floor, in seconds) up to the budget in seconds (or that largest member, if larger).  A subtree urn's
              new ball is a fresh subtree: a uniformly chosen member's own job and split (its seconds and its count of
              children), with each child picked from the urn of the depth below (its new ball included), as Knuth's
              (1975) estimate of a tree's size grows a random path.  Every value is a member's, a leaf at most the
              budget's seconds, or a sum of a bounded number of those (the cascade is finite), so every sample is
              bounded and the mean is finite.
  censored    a running leaf: its cost exceeds its elapsed seconds (t less its start).  It is drawn from its urn's
              balls above the elapsed time, the gap ball's included (from the larger of its bottom and the elapsed
              time), the longest-running first, each then a ball: Efron's (1967) redistribution to the right, which
              gives the Kaplan and Meier (1958) estimate, with random weights.
  partway     a fresh node of this pass that has finished its own job and split, but not its subtree.  Its cost so
              far is its subtree's logged seconds plus its running leaves' elapsed seconds; its eventual cost is that
              plus its remaining work, which the draws below it give.
  population  at each depth above the bottom, this pass's fresh nodes that have finished their job there: finished
              subtrees, at their logged cost, and partway ones, at their eventual cost.  At a depth with none yet,
              its nodes the pass has split again stand in for them, at their eventual cost (2026-10-29: 288@10's pass
              at budget 1,000 reached its depths 3 and 4 only through such nodes): each lacks only a fresh node's own
              job, seconds against a subtree's hours, and its chance of closing at once.  Their urn gives the subtree
              cost of each node of kind 'subtree' at that depth, pending or running (a running one's elapsed time, a
              few seconds of solve and split, is ignored).  Depths go from the bottom up, so a partway member's
              eventual cost is drawn before its depth's draws are made.
  history     for a donor subtree's prediction, each job's first logged cost in the contiguous preceding passes
              with the same target, budgets, cascade and pool budget. Historical costs replace repeated-job charges
              in the donor observation only; they never add completed work to the current pass's remaining work.
  items       the remaining work in search()'s order: the running jobs that are not leaves first (their children go
              on top of the stack), then the stack from its top, a resplit node replaced by its children in the order
              search() pops them.  A leaf is a job of one worker; a subtree is fluid, spread over the free workers.
  makespan    list scheduling on the pass's workers: each running leaf's remaining seconds hold its worker; a leaf
              job goes to the worker free first; fluid work fills the earliest-free workers to a common level (water
              filling).  The makespan is when the last worker is free: the remaining time.
  no estimate an empty array: when a node of kind 'subtree' waits at a depth with no population yet, no node of
              the pass done there (a fresh subtree needs a member's job and split), or no fresh leaf solve has been
              logged yet (no speed, so no gap).  The
              model then has nothing to draw from.
  probe       a journal record of fanout.py's (see its vocabulary, 2026-10-25), or of focus.py's in the same form: one
              case's random paths from its root to a leaf, their leaf depths' mean and standard error, least, and the
              exact solutions they ended at.
  least       a probe's lower bound on its case's LP solves in all (95%, one-sided; fanout.least), the latest probe's
              for each case; -inf, no bound, for a case with none.  The Lindy estimates of fanout.py's and focus.py's
              runs draw an open case's work from the urn above its censoring point: the larger of its work so far and
              its least (focus.py's: the running root's only, its least turned into seconds at the run's seconds of
              running per LP solve so far; a pending root counts its probe once it runs).  That is Gott's rule given
              total >= least, P(T > t) = max(age, least) / t.  The work between the case's work so far and its censoring
              point is certain, added to every draw; the censoring point counts as a time seen (lindy_draws's longest
              seen).  A least below the work so far changes nothing.  (2026-10-25: with no case done, Gott's rule alone
              put 672:13's median to go at its work so far, 17 h, when random paths put its tree at >= 1e13 LP solves.)
  pool estimate  the ETA of fanout.py's runs since 2026-10-26 (dreeves: "sure", to an ETA from the pool's random draws,
              in place of Lindy on the cases' work, which knew nothing of the pool).  Its samples: the jobs that recorded
              their open boxes' depths (open_depths), each a uniform random draw from the pool (fanout.py's 'job'):
              (depth, LP solves, open boxes' depths).  The pool now: the latest session's pool record, less the depths
              of its jobs done, plus their open boxes' (its running jobs among the boxes left).  E[T(d)], the expected LP
              solves of a box at depth d and of every box it leaves open, solves E[T(d)] = mean over the samples s of
              d's band (BAND levels) of (s's LP solves + the sum over s's open boxes of E[T(d + their depth - s's)]),
              from depth n down, 0 past n; a band with no sample takes the nearest band's that has one, the deeper on a
              tie.  The estimate: the sum over the pool of E[T(d)], at least the probes' floor (each open case's least
              less its work so far, summed), over the pool's rate; its median and band the median and QUANTILES of BOOT
              replicates, each band's samples resampled (a bootstrap: the uncertainty of the bands' means, not of the
              process itself, whose sum over thousands of boxes varies less).  None until the session has a pool record,
              a sample and a box.
  tracked     a search run under track.py (dreeves, 2026-10-28: "can we rearchitect things so that always happens easily
              and automatically?"): its runs' records, runs/NAME.jsonl (see track.py), are the watcher's only source,
              read whatever program the runs run, the runs of one target N:M one search.  A run is ended with its end
              line; else frozen while its process is stopped (state T), running while it lives, and aborted once it is
              gone (its tracker died before writing the end).  The search shows one dot per run (survey_track).
  reading     the watcher's state of a run's files, kept between snapshots (2026-10-30: it read 288@10's 500 MB of journal
              and log whole every minute, and one snapshot took 90 minutes): the bytes read so far and all parsed, dated
              and derived from them (Reading, with its Tree and Grown; Boxes for a boxsplit pass, Records for focus.py's
              and fanout.py's journals), changed only in atomic blocks, so that a snapshot costs about what the files
              gained.  read_run, sea, estimate and a survey made without one make a new one, which reads the files
              whole: the same values.
  unit        one run's survey in a snapshot (snapshot): bounded by LIMIT seconds, doubled after each overrun of its run
              since the run's last completed survey; a unit that fails or runs past its bound leaves its run's last good
              data in the data file, marked stale, and the other units go on.
  stale       of a run in the data file: null, or the time of the snapshot its data are from, when its survey failed or ran
              past its bound since; the section marks such a run (Claude: "stale").
The data file says when the snapshot was made, to the second, and the section keeps its age up to date.  Per run it
gives the state, the hours of running so far and to go, the record of ETAs and the sea (see js_text).
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, math, time, bisect, itertools, subprocess, collections, glob, functools, shlex, signal, contextlib
import struct, traceback
import numpy as np
import overnight_v5 as v5
import boxsplit as bx
import fanout
import run_modules

ROOT_V5, ROOT_BX = v5, bx

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, 'progress.js')         # the data file of index.html's section "Search progress" (see the vocabulary)
CACHE = os.path.join(HERE, '.progress_cache.json')    # a directory since 2026-10-30 (see save_cache), git-ignored
# The completed 240@11 proof and its boxsplit pass, and the 384@11 search
# superseded by proof384.py, left the live display on 2026-10-20. Their journals remain.  So did the finished 288:10
# symmetric batch (lattice288.py) and 720:11 joined batch (join720.py) on 2026-10-23; their adapters remain.
# 288@10's boxsplit pass (dreeves, 2026-10-27: "ok") is scratch/x288's copy of boxsplit.py, after the search's first pass in
# the same lease; it shows once its driver's log exists.
EXTENDED = ((288, 10),)               # displayed boxsplit runs, (N, ORDER), each shown once its driver's log exists
RUNS = ((288, 10),)                   # displayed overnight_v5 runs, (N, ORDER)
# The directory of a run that a copy of overnight_v5.py makes, relative to HERE; the rest are the repository's own.  288@10
# runs from scratch/x288 (2026-10-27) while the original is frozen for 432:12; its solver may differ only with identical
# geometry, replay functions and exact proof checker (run_modules).
DIRS = {(288, 10): os.path.join('scratch', 'x288')}
REFRESH = 60                           # seconds between rewrites under --watch (the section reloads the data file as often)
NICE = 15                              # the niceness the process lowers itself to
# The deepest level enumerated.  Splitting cost the runs themselves (their logs' split seconds, on loaded workers)
# under 4 s per node on average down to depth 5, but 6.4 s at depth 6 of 240@11 (up to 51 s).  Levels 0..6 need
# splits down to depth 5 only; 304@9's bottom is level 6.
DEEPEST = 6
REPLICATES = 2000                      # draws in an estimate: a Monte Carlo precision setting
SEED = 0                               # the estimate's random generator's seed: an estimate is a function of its state
QUANTILES = (0.05, 0.95)               # the estimate's range, the ETA's band: the middle 90% of its draws (80% was too
                                       # narrow: backtested on 304@9's two finished passes, it held the truth 22 of 31 times)
HOUR = 3600                            # seconds
STATUSES = ('settled', 'open', 'split', 'pending')     # the statuses, in the order of the levels' counts
SEA_DEPTH = 5                          # the sea's groups are the sub-cases at this depth (240@11's 291), or above the bottom
SEA_STATUSES = STATUSES + ('running',)  # a dot's status, by its index in the data file
ETA_POINTS = 400                       # the most recorded ETAs the data file carries per run
LIMIT = 120                            # seconds a run's survey may take in a snapshot, before overruns (see snapshot)
STEP = 20000                           # lines, records or keys a reading takes in one atomic block (see atomic)
DRAWS = 1 << 28                        # the most numbers an urn may hold (see Urn): 2 GiB of float64


# ---------- surveys bounded in time (2026-10-30: one run's 90-minute snapshot froze the whole page) ----------

class Overtime(Exception):
    """A survey that ran past its seconds (see bounded)."""


@contextlib.contextmanager
def atomic():
    """A block no Overtime interrupts: SIGALRM waits until the block ends.  A reading (see the vocabulary) changes
    only in such blocks, so that an Overtime, which falls between them, leaves it whole for the next snapshot."""
    old = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, old)


def bounded(seconds, thunk):
    """thunk(), unless it runs past seconds of wall time: then Overtime, raised by SIGALRM at the first moment outside an
    atomic block.  The timer and the handler are restored however thunk ends."""
    def alarm(signum, frame):
        raise Overtime(f'over {seconds} s')
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return thunk()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


# ---------- reading the runs' files ----------

def run_module(d):
    """The overnight_v5.py of the directory d as a module of its own, loaded once (registered in sys.modules, where
    inspect looks up its classes' source for CODE)."""
    return run_modules.load(d, ROOT_V5, ROOT_BX).v5


def run_context(n, order):
    """Use this run's actual solver and replay modules throughout file resolution and one complete survey."""
    d = os.path.join(HERE, DIRS.get((n, order), ''))
    return run_modules.context(sys.modules[__name__], run_modules.load(d, ROOT_V5, ROOT_BX))


def files(n, order):
    """The journal and log of the run (n, order), named as overnight_v5.configure names them, in the run's directory
    (DIRS, or the repository's own).  run_module checks identical geometry, replay and exact verification before
    accepting a different local solver CODE. Its settings for the run become overnight_v5's (they must agree where
    both have them). Standalone callers retain their root module; run_context binds complete surveys to the copy."""
    d = os.path.join(HERE, DIRS.get((n, order), ''))
    copy = run_module(d)
    # TODO: error copy; says the run's directory holds an overnight_v5.py whose code or settings differ from overnight_v5's
    assert v5.SETTINGS.get((n, order), copy.SETTINGS[n, order]) == copy.SETTINGS[n, order], \
        f'Claude: "{d} holds another overnight_v5.py"'
    v5.SETTINGS[n, order] = copy.SETTINGS[n, order]
    v5.configure(n, order)
    return tuple(os.path.join(d, os.path.basename(f)) for f in (v5.JOURNAL, v5.LOG))


def complete_lines(path):
    """The file's complete lines: a last line without its newline is still being written, so it is left out."""
    return open(path, encoding='utf-8').read().split('\n')[:-1]


class Tail:
    """A file's complete lines (see complete_lines), read as the file grows: each read() gives those completed since
    the last.  The file may only grow: the same file (device and inode), no shorter than what was read, its first line
    unchanged, and no carriage return, which complete_lines would read as a line's end (all asserted).  read() belongs
    in the atomic block that keeps its lines (see atomic): the file is read past them."""

    def __init__(self, path):
        self.path, self.offset, self.ident, self.head = path, 0, None, b''

    def read(self):
        with open(self.path, 'rb') as fh:
            st = os.fstat(fh.fileno())
            # TODO: error copy; says the file was replaced or cut short since the watcher last read it, naming it
            assert (self.ident in (None, (st.st_dev, st.st_ino)) and st.st_size >= self.offset
                    and fh.read(len(self.head)) == self.head), f'Claude: "{self.path} was replaced or cut short"'
            fh.seek(self.offset)
            data = fh.read()
        done = data[:data.rfind(b'\n') + 1]
        # TODO: error copy; says the file holds a carriage return, naming it
        assert b'\r' not in done, f'Claude: "{self.path} holds a carriage return"'
        self.ident, self.offset = (st.st_dev, st.st_ino), self.offset + len(done)
        self.head = self.head or done[:done.find(b'\n') + 1]
        return done.decode('utf-8').split('\n')[:-1]


class Records:
    """A journal of JSON lines, its records parsed as it grows (Tail), each step atomic: [json.loads(line) for line in
    complete_lines(path)], kept (2026-10-30: fanout_432's 9 MB and focus_480's 6 MB, parsed whole each minute)."""

    def __init__(self, path):
        self.path, self.tail, self.lines, self.records = path, Tail(path), collections.deque(), []

    def read(self):
        """The records so far."""
        with atomic(): self.lines += self.tail.read()
        while self.lines:
            with atomic():
                for _ in range(min(STEP, len(self.lines))):
                    self.records.append(json.loads(self.lines[0]))
                    self.lines.popleft()
        return self.records


def read_journal(path):
    """The journal's last record per key, for overnight_v5's current configuration, whose header it must have.
    overnight_v5.Journal.admit checks each record as the run does (made without Journal's __init__, which would
    create a missing journal)."""
    lines = complete_lines(path)
    # TODO: error copy; says the journal at this path was written by another configuration or another version of the code
    assert json.loads(lines[0]) == v5.header(), f'Claude: "the journal {path} belongs to another configuration"'
    run_modules.validate_header(v5, json.loads(lines[0]))
    journal = object.__new__(v5.Journal)
    journal.records = {}
    for r in map(json.loads, lines[1:]): journal.admit(r)
    return journal.records


STAMP = r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) '
FORMS = {                              # the log's line forms, as overnight_v5's run, search and say_* write them
    'start': re.compile(STAMP + r'Claude: "start: n = (\d+), order at least (\d+), (\d+) processes, budgets '
                        r'\[([\d, ]+)\] \(LP solves; a pool at least (\d+) per member\), HiGHS (.+), split moduli '
                        r'\[([\d, ]+)\], (\d+) earlier verdicts(, siblings shuffled)?"$'),
    'control': re.compile(STAMP + r'Claude: "startup control passed: .*"$'),
    'node': re.compile(STAMP + r'\[(\d+)\] \{(.*)\}: (\w+) \((\d+\.\d) \+ (\d+\.\d) s\); Claude: "closed (\d+), '
                       r'waiting (\d+), running (\d+), open (\d+), LP failures (\d+)"$'),
    'open': re.compile(STAMP + r'Claude: "open: \{(.*)\}"$'),
    'witness': re.compile(STAMP + r'Claude: "WITNESS FOUND in \{.*\}, exact order \d+: X = \[[\d, ]*\]"$'),
    'outcome': re.compile(STAMP + r'(Claude: "(?:NOT FINISHED: |ALL NODES CLOSED \(|WITNESS FOUND, exact order ).*")$'),
}


def ints(text): return [int(t) for t in text.split(', ')]
@functools.lru_cache(maxsize=None)                 # a log's lines share their seconds (288@10's, 2026-10-28: 287,379 lines, 57,602 seconds)
def stamp(text): return time.mktime(time.strptime(text, '%Y-%m-%d %H:%M:%S'))


@functools.lru_cache(maxsize=None)
def meanings(text):
    """The times (epoch seconds) a log line's local stamp can mean, in order: one, or two in the hour that the fall from
    daylight saving time repeats (2026-11-01 01:00 to 01:59 here), where mktime reads some stamps as the first hour's
    and some as the second's, so that a log read by stamp alone goes back in time.  A meaning is a time that
    localtime gives back as the stamp."""
    tt = time.strptime(text, '%Y-%m-%d %H:%M:%S')
    out = sorted({t for t in (time.mktime(tt[:8] + (dst,)) for dst in (0, 1))
                  if time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t)) == text})
    # TODO: error copy; says a stamp names a local time that never happens (one in the hour a spring forward skips)
    assert out, f'Claude: "{text} is no local time"'
    return tuple(out)


def stamp_after(text, before):
    """The time of a log line stamped text that follows a line of time before: the stamp's first meaning (see
    meanings) not earlier than before, else its last (a log going back in time, which read_run refuses).  Outside a
    repeated hour it is stamp(text)."""
    return next((t for t in meanings(text) if t >= before), meanings(text)[-1])


class Log:
    """A log's passes as parse_lines makes them, taking its lines one at a time (see Reading), with what read_run keeps
    of them: the lines, their times (each line's stamp_after the line before it) and kinds (FORMS keys), and the index
    of each pass's start line and of each of its progress lines.  Node keys are interned: a run's journal names each
    key again (288@10's, 2026-10-30: 1.16 million log lines, 768,353 records)."""

    def __init__(self):
        self.lines, self.stamps, self.kinds, self.passes, self.starts, self.node_lines = [], [], [], [], [], []

    def take(self, line):
        """Parse the next line into the passes, or fail (asserted) leaving everything as it was."""
        forms = [(kind, m) for kind, form in FORMS.items() if (m := form.match(line))]
        # TODO: error copy; says a line of the log has none of the forms progress.py knows, quoting the line
        assert len(forms) == 1, f'Claude: "a log line of no known form: {line}"'
        kind, m = forms[0]
        # TODO: error copy; says a line of the log comes before any start line or after its pass's outcome line, quoting it
        assert kind == 'start' or (self.passes and self.passes[-1]['outcome'] is None), f'Claude: "a log line out of place: {line}"'
        t = stamp_after(m[1], self.stamps[-1] if self.stamps else -math.inf)
        i = len(self.lines)
        if kind == 'start':
            self.passes.append({'start': t, 'n': int(m[2]), 'order': int(m[3]), 'processes': int(m[4]), 'budgets': ints(m[5]),
                                'pool_budget': int(m[6]), 'highs': m[7], 'moduli': ints(m[8]), 'earlier': int(m[9]),
                                'shuffled': m[10] is not None, 'nodes': [], 'opens': [], 'outcome': None})
            self.starts.append(i)
            self.node_lines.append([])
        p = self.passes[-1]
        p['last'] = t
        if kind == 'node':
            p['nodes'].append({'t': t, 'i': int(m[2]), 'key': sys.intern(m[3]), 'verdict': m[4], 'solve': float(m[5]),
                               'split': float(m[6]), 'closed': int(m[7]), 'waiting': int(m[8]), 'running': int(m[9]),
                               'open': int(m[10]), 'failures': int(m[11])})
            self.node_lines[-1].append(i)
        if kind == 'open': p['opens'].append(sys.intern(m[2]))
        if kind == 'outcome': p['outcome'] = m[2]
        self.lines.append(line)
        self.stamps.append(t)
        self.kinds.append(kind)


def parse_lines(lines):
    """The passes of the log whose complete lines these are, in order, each a dict:
         start, last     the times (epoch seconds) of its start line and of its last line;
         n, order, processes, budgets, pool_budget, highs, moduli, earlier    its start line's fields;
         shuffled        whether its start line says it shuffles each node's children (overnight_v5.sibling_order,
                         since 2026-10-17), so that its replay pushes them in that order, not the split's;
         nodes           its progress lines, each a dict of t, i, key, verdict, solve and split (seconds), and the
                         log's counts closed, waiting, running, open and failures;
         opens           the keys of its open lines;
         outcome         its last line if that says how the pass ended (NOT FINISHED, ALL NODES CLOSED or the final
                         WITNESS FOUND line), as the log has it, after the time; else None.
    Every line must have exactly one known form, every pass must begin with a start line, and no line may follow a
    pass's outcome but the next start line (all asserted).  The times are each line's stamp_after the line before."""
    log = Log()
    for line in lines: log.take(line)
    return log.passes


def parse_log(path):
    """parse_lines of the log's complete lines."""
    return parse_lines(complete_lines(path))


def processes():
    """The machine's processes as (pid, ppid, stat, command), from ps (which prints whole commands to a pipe)."""
    out = subprocess.run(['ps', '-ax', '-o', 'pid=,ppid=,stat=,command='], capture_output=True, text=True, check=True)
    return [(int(a), int(b), c, d) for a, b, c, d in (line.split(None, 3) for line in out.stdout.splitlines())]


def runs(procs, script, *args):
    """The live processes of procs (not zombies) that run script, by name or path, with args as its first arguments: a
    Python interpreter's, its options before the script (2026-10-23: a shell whose command line merely mentioned
    "fanout.py 672" made the watcher and the shepherd each find two and stop)."""
    tail = ''.join(r'\s+' + re.escape(str(a)) for a in args)
    pattern = rf'^\S*[Pp]ython[\d.]*(?:\s+-\S+)*\s+(?:\S*/)?{re.escape(script)}{tail}(?:\s|$)'
    return [p for p in procs if re.match(pattern, p[3]) and not p[2].startswith('Z')]


def run_state(procs, program, n, order, outcome):
    """The state (see the vocabulary) of program's run (overnight_v5.py's or boxsplit.py's), from the process list and
    the current pass's outcome line (or None): frozen when its main process is stopped; a stopped worker only takes
    capacity away, and the run goes on (dreeves, 2026-10-20: two of 240@11's four boxsplit workers were paused)."""
    main = runs(procs, program, n, order)
    # TODO: error copy; says several processes run this search at once, giving how many, the length and the order
    assert len(main) <= 1, f'Claude: "{len(main)} processes run {program} {n} {order}"'
    return ('ended' if outcome is not None or not main else
            'frozen' if main[0][2].startswith('T') else 'running')


# ---------- the run, dated ----------

def read_run(journal, log):
    """The run's log and journal, read in that order, parsed and dated (see dating in the vocabulary): a dict of
         lines, stamps, kinds   the log's complete lines, their times (never decreasing, asserted) and their forms
                                (FORMS keys);
         passes                 parse_lines of the lines;
         starts, node_lines     the index of each pass's start line, and for each pass the indices of its progress lines;
         records                the journal's records dated by those lines, in order, each admitted as
                                overnight_v5.Journal admits it (the journal's header must be overnight_v5's, asserted);
         fresh                  {index of a progress line: index of its node's fresh record};
         dates                  for each record, the index of the line it is dated by, never decreasing;
         bounds                 for each pass, the index of its first record (len(records) for a pass with none yet).
    A fresh record must be its line's node, verdict and budget, and a line without one must be a node split again (all
    asserted), but for a line whose record is nowhere in the journal: a migration dropped it, so that a later pass
    solves the node again (scratch/width/migrate_now.py dropped those the width test closes), and the line goes undated.  The log is read first: each record is written before its line, so every line read has its record in
    the journal read after it.  The records after the last line's own, but for the CLOSED records it wrote, belong to
    lines not read yet, and are left out.  A Reading of the two files, advanced once (see Reading)."""
    return Reading(journal, log).advance()


class Reading:
    """read_run of a run's journal and log kept by the watcher and brought up to date with what the files gained (see
    reading in the vocabulary).  Its state is read_run's: what the files held up to their last complete lines, read
    (Tail), parsed (Log, and each record as JSON) and dated, with the latest dated record per key (final, the journal
    replayed: overnight_v5.Journal, made without its __init__, which would create a journal).  A record whose triple
    (key, verdict, budget) is a line's that dating took for dropped by a migration must not come later: read_run of
    the files as they are then would date that line by it (asserted)."""

    def __init__(self, journal, log):
        self.journal, self.log = journal, log
        self.tails = (Tail(log), Tail(journal))
        self.lines, self.texts = collections.deque(), collections.deque()   # read, not yet parsed
        self.parsed, self.header = Log(), None
        self.records, self.present, self.dropped = [], set(), set()
        self.dated, self.dates, self.fresh, self.last = [], [], {}, {}
        self.final = object.__new__(v5.Journal)
        self.final.records = {}
        self.cursor = (0, 0)              # the next progress line to date: (its pass, its index among the pass's)
        self.grove, self.planted = None, 0                # the Tree of final (see tree), and the dated records it holds
        self.touching, self.touches = None, {}            # the pass whose touched sub-cases are kept (see touched)
        self.dropped_lines = set()                        # the progress lines dating took for dropped by a migration
        self.start_pass, self.start_final, self.start_bound = None, {}, 0   # see starting
        self.speed_at, self.seconds, self.lps, self.claims = (0, 0), 0.0, 0, set()   # see speed
        self.wanted_pass, self.wanted_bound, self.wanted, self.checked = None, None, set(), 0   # see resplits
        self.grown = None                                 # (Grown, History, start_bound) of the current pass
        self.R = None                                     # read_run's dict, as the last advance made it

    def advance(self):
        """Read what the files gained and parse and date it, each step an atomic block (see atomic) of at most STEP
        lines or records; read_run's dict of all so far.  The journal is read, then the log, then the journal again:
        every line read has its record in the second read, and the CLOSED records left after the last dated one are
        dated only up to the first read's end, whose records were written before the log was read and so before
        their nodes' lines were read (a CLOSED record dated without its node's latest line would stay dated before its
        pass: read_run's race at a pass's start, 2026-10-20, which a reading kept for good would keep)."""
        with atomic(): self.texts += self.tails[1].read()
        while self.texts:
            with atomic(): self.parse(STEP)
        safe = len(self.records)
        with atomic(): self.lines += self.tails[0].read()
        while self.lines:
            with atomic(): self.take(STEP)
        with atomic(): self.texts += self.tails[1].read()
        while self.texts:
            with atomic(): self.parse(STEP)
        while self.behind():
            with atomic(): self.date(STEP)
        with atomic(): self.closings(safe)
        # TODO: error copy; says the journal at this path has no header line yet
        assert self.header is not None, f'Claude: "the journal {self.journal} has no header"'
        L = self.parsed
        self.R = {'lines': L.lines, 'stamps': L.stamps, 'kinds': L.kinds, 'passes': L.passes, 'starts': L.starts,
                  'node_lines': L.node_lines, 'records': self.dated, 'fresh': self.fresh, 'dates': self.dates,
                  'bounds': [bisect.bisect_left(self.dates, s) for s in L.starts]}
        return self.R

    def take(self, n):
        """Parse up to n lines read (Log.take), each stamped no earlier than the line before it (asserted)."""
        stamps = self.parsed.stamps
        for _ in range(min(n, len(self.lines))):
            line = self.lines[0]
            before = stamps[-1] if stamps else -math.inf
            # TODO: error copy; says a line of the log at this path is stamped earlier than the line before it
            assert stamp_after(line[:19], before) >= before, f'Claude: "the log {self.log} goes back in time"'
            self.parsed.take(line)
            self.lines.popleft()

    def parse(self, n):
        """Parse up to n of the journal's lines read: its header first, which must be overnight_v5's (asserted)."""
        for _ in range(min(n, len(self.texts))):
            r = json.loads(self.texts[0])
            if self.header is None:
                # TODO: error copy; says the journal at this path was written by another configuration or another version of the code
                assert r == v5.header(), f'Claude: "the journal {self.journal} belongs to another configuration"'
                run_modules.validate_header(v5, r)
                self.header = r
            else:
                r['key'] = sys.intern(r['key'])
                triple = (r['key'], r['verdict'], r['budget'])
                # TODO: error copy; says the journal gained the record of a progress line that was read as dropped by a migration, naming the record
                assert triple not in self.dropped, f'Claude: "the journal {self.journal} gained the record of a dropped line: {triple}"'
                self.records.append(r)
                self.present.add(triple)
            self.texts.popleft()

    def behind(self):
        """Whether a progress line parsed is not dated yet."""
        k, j = self.cursor
        P = self.parsed.passes
        return k < len(P) and (j < len(P[k]['nodes']) or k + 1 < len(P))

    def date(self, n):
        """Date up to n more progress lines (see dating in the vocabulary), each whole."""
        P, L = self.parsed.passes, self.parsed.node_lines
        while n and self.behind():
            k, j = self.cursor
            if j == len(P[k]['nodes']):
                self.cursor = (k + 1, 0)
                continue
            self.date_line(P[k], P[k]['nodes'][j], L[k][j])
            self.cursor, n = (k, j + 1), n - 1

    def date_line(self, p, nd, i):
        """Date the progress line i (nd, of pass p): read_run's dating, line by line."""
        self.last[nd['key']] = i                                    # each key's latest progress line so far
        budget = budget_of(nd['key'], p['budgets'])
        prev = self.final.records.get(nd['key'], {'verdict': 'UNKNOWN', 'budget': -1})
        assert prev['verdict'] == 'UNKNOWN', (self.log, i)          # search() never submits a settled node
        if prev['budget'] >= budget:                                # split again, with no fresh record
            assert nd['verdict'] == 'UNKNOWN', (self.log, i)
            return
        self.closings()
        triple = (nd['key'], nd['verdict'], budget)
        if triple not in self.present:                              # dropped by a migration
            self.dropped.add(triple)
            self.dropped_lines.add(i)
            return
        # TODO: error copy; says the journal at this path has no record for a progress line that reports a fresh verdict, naming the line
        assert len(self.dates) < len(self.records), f'Claude: "the journal {self.journal} lacks the record of line {i + 1} of its log"'
        r = self.records[len(self.dates)]
        assert (r['key'], r['verdict'], r['budget']) == triple, (self.log, i)
        self.fresh[i] = len(self.dates)
        self.admit(i)

    def admit(self, line):
        """Date the next record by this line."""
        assert line >= 0
        r = self.records[len(self.dates)]
        self.final.admit(r)
        self.dates.append(line)
        self.dated.append(r)

    def closings(self, safe=math.inf):
        """Date the CLOSED records next in the journal, as dating says, of the first safe records."""
        while len(self.dates) < min(safe, len(self.records)) and self.records[len(self.dates)]['verdict'] == 'CLOSED':
            self.admit(max(self.dates[-1:] + [self.last.get(self.records[len(self.dates)]['key'], -1)]))

    def tree(self, budgets, cache):
        """The Tree of final under these budgets and this cache (see Tree), with every dated record applied, the splits
        cached since taken in and every group drawn, each step atomic; begun anew for other budgets or another cache."""
        if self.grove is None or self.grove.budgets != list(budgets) or self.grove.cache is not cache:
            with atomic(): self.grove, self.planted = Tree(self.final.records, budgets, cache), 0
        while self.planted < len(self.dated):
            with atomic():
                end = min(len(self.dated), self.planted + STEP)
                for r in self.dated[self.planted:end]: self.grove.apply(r['key'])
                self.planted = end
        with atomic(): self.grove.expand()
        while self.grove.dirty:
            with atomic(): self.grove.redraw(STEP // 100)
        return self.grove

    def touched(self, depth):
        """touched_at of the current pass's progress lines at this depth (see work), kept up to date."""
        p = self.parsed.passes[-1]
        if self.touching is not p:
            with atomic(): self.touching, self.touches = p, {}
        kept = self.touches.setdefault(depth, [0, set()])          # [the pass's lines taken, the sub-cases]
        while kept[0] < len(p['nodes']):
            with atomic():
                end = min(len(p['nodes']), kept[0] + STEP)
                kept[1].update(touched_at(p['nodes'][kept[0]:end], depth))
                kept[0] = end
        return kept[1]

    def starting(self, k):
        """state_at's final_at_start of pass k, the current one: the latest record per key dated before its first line,
        kept as one dict, which gains the records dated before the pass since (start_bound counts them)."""
        bound = bisect.bisect_left(self.dates, self.parsed.starts[k - 1])
        with atomic():
            if self.start_pass != k: self.start_pass, self.start_final, self.start_bound = k, {}, 0
            for r in self.dated[self.start_bound:bound]: self.start_final[r['key']] = r
            self.start_bound = bound
        return self.start_final

    def speed(self, state):
        """speed(state) kept up to date (see speed): the fresh leaf solves' seconds and LP solves summed in log order, as
        speed sums them, over state's lines (cut at its time, and so never fewer than before: asserted), in one atomic
        block; but should a fresh leaf's record have the key and budget of a line before it that dating took for
        dropped (a claim speed gives that earlier line), speed_sums sums everything again."""
        bottom = len(state['budgets']) - 1
        P, L = state['passes'], self.parsed.node_lines
        # TODO: error copy; says the speed kept for a run was asked for at an earlier time than before, naming the state
        assert self.speed_at <= (len(P) - 1, len(P[-1]['nodes'])), f'Claude: "the speed of {state["label"]} goes back in time"'
        again = False
        with atomic():
            k, j = self.speed_at
            while k < len(P) and (j < len(P[k]['nodes']) or k + 1 < len(P)):
                if j == len(P[k]['nodes']):
                    k, j = k + 1, 0
                    continue
                nd, i = P[k]['nodes'][j], L[k][j]
                kb = (nd['key'], budget_of(nd['key'], P[k]['budgets']))
                if len(nd['key'].split()) == bottom and i in self.fresh:
                    again |= kb in self.claims
                    self.seconds, self.lps = self.seconds + nd['solve'], self.lps + self.dated[self.fresh[i]]['lps']
                if len(nd['key'].split()) == bottom and i in self.dropped_lines: self.claims.add(kb)
                j += 1
            self.speed_at = (k, j)
            if again: self.seconds, self.lps = speed_sums(state)
        return self.seconds / self.lps if self.lps else None

    def resplits(self, order, cache):
        """resplits(R, order, cache) kept for the current pass: once (and again should more records be dated before the
        pass), its nodes to split again (wanted) recovered (recover_splits) or split, each split stored whole; after that,
        each new progress line of the pass checked against the cache, as recover_splits checks its lines: a wanted
        node's verdict is UNKNOWN and its key holds no pool, and a child of a wanted node is among its cached children."""
        p = self.parsed.passes[-1]
        start = self.starting(len(self.parsed.passes))
        if self.wanted_pass is not p or self.wanted_bound != self.start_bound:
            budgets = p['budgets']
            wanted = {k for k, r in start.items() if r['verdict'] == 'UNKNOWN'
                      and len(k.split()) < len(budgets) - 1 and r['budget'] >= budget_of(k, budgets)}
            recover_splits(self.R, wanted, cache)
            with atomic(): self.wanted_pass, self.wanted_bound, self.wanted, self.checked = p, self.start_bound, wanted, len(p['nodes'])
        for k in sorted(self.wanted): children(k, order, cache)
        with atomic():
            for nd in p['nodes'][self.checked:]:
                key, up = nd['key'], parent_key(nd['key'])
                assert key not in self.wanted or (nd['verdict'] == 'UNKNOWN' and '#' not in key), (self.log, nd['i'])
                assert not key or up not in self.wanted or key in cache[up], (self.log, nd['i'])
            self.checked = len(p['nodes'])
        return cache

    def estimating(self, order, cache, t, label):
        """estimate's view of the run as of t (see estimate): the pass's resplit nodes split first (resplits), state_at's
        state, the log cut at t, with its final_at_start kept (starting), and the kept Grown and History grown to it
        (t never earlier than before: the lines a survey reads after its now wait for the next); both begun anew for
        another pass, more records dated before the pass, another cache, or a split cached for a node the Grown left
        with unnamed kids (see Grown)."""
        R = self.R
        self.resplits(order, cache)
        passes = passes_at(R, bisect.bisect_right(R['stamps'], t))
        state = state_from(R, t, cache, label, passes, self.starting(len(passes)))
        g, h, bound = self.grown or (None, None, None)
        if (g is None or g.start != passes[-1]['start'] or bound != self.start_bound or g.cache is not cache
                or any(k in cache for k in g.unnamed)):
            g, h = Grown(state), History(state)
            with atomic(): self.grown = (g, h, self.start_bound)
        return g.view(state, self.speed(state), h.credit(state))


def passes_at(R, lines):
    """parse_lines of the run's first so many log lines (at least through its first start line), from read_run's R: the
    passes begun by then, the last cut short there."""
    k = bisect.bisect_right(R['starts'], lines - 1)
    assert k >= 1, lines
    p, first = R['passes'][k - 1], R['starts'][k - 1]
    m = bisect.bisect_left(R['node_lines'][k - 1], lines)            # its progress lines among the first lines
    ended = R['kinds'][lines - 1] == 'outcome'
    return R['passes'][:k - 1] + [dict(p, nodes=p['nodes'][:m], opens=p['opens'][:R['kinds'][first:lines].count('open')],
                                       last=R['stamps'][lines - 1], outcome=p['outcome'] if ended else None)]


def state_at(R, t, cache, label):
    """What estimate() needs of the run as of time t (epoch seconds, at or after its first start line), from read_run's
    R and the run's cached splits (see children): a dict of t, label (naming the state in errors), the passes as of t
    (passes_at, the current pass last), that pass's processes and budgets, final_at_start (the last record per key
    before the pass's first record), records (all of R's: estimate() uses only those that lines before t claim), and
    cache.  Only the log is cut at t: every other input is the same at any time in the pass, so the state as of a
    past time comes from the files as they are now (the quals' backtests rest on this)."""
    lines = bisect.bisect_right(R['stamps'], t)
    passes = passes_at(R, lines)
    return state_from(R, t, cache, label, passes, {r['key']: r for r in R['records'][:R['bounds'][len(passes) - 1]]})


def state_from(R, t, cache, label, passes, final_at_start):
    """state_at's state of these passes as of t (passes_at) with this final_at_start."""
    p = passes[-1]
    return {'t': t, 'label': label, 'passes': passes, 'processes': p['processes'], 'budgets': p['budgets'],
            'final_at_start': final_at_start, 'records': R['records'], 'cache': cache}


# ---------- the tree ----------

POOL = re.compile(r'\d+:#(\d+):[0-9a-f]{40}')   # a pool's constraint, M:#count:sha1


def members(key):
    """The count vectors in the key's last constraint: none for the top node, a pool's count (M:#count:sha1), or 1."""
    last = key[key.rfind(' ') + 1:]
    pool = POOL.fullmatch(last) if '#' in last else None   # a constraint without # is no pool
    return 0 if not key else int(pool[1]) if pool else 1


def budget_of(key, budgets):
    """overnight_v5.node_budget of the key's node, under these budgets (by depth)."""
    return max(budgets[len(key.split())], v5.POOL_BUDGET * members(key))


def leaf(key, bottom):
    """Whether overnight_v5.split gives the key's node no children: a node at the bottom of the cascade (depth
    bottom) that is not a pool of several members."""
    return len(key.split()) == bottom and members(key) <= 1


def status(key, final, budgets):
    """The key's status (see the vocabulary), from the journal's last records and the current pass's budgets."""
    r = final.get(key, {'verdict': 'UNKNOWN', 'budget': -1})
    if r['verdict'] in v5.SETTLED: return 'settled'
    if r['budget'] < budget_of(key, budgets): return 'pending'
    return 'open' if leaf(key, len(budgets) - 1) else 'split'


@functools.lru_cache(maxsize=1 << 18)
def tree_order(key):
    """The key's place in tree order (see the vocabulary), as bytes that compare as its constraints compared one by
    one: a count vector M:[a,b,...] as M, 0, a + 1, b + 1, ..., 0 and a pool M:#c:sha1 as M, 1, c + 1, 0, sha1, each
    number in two bytes, big-endian (struct fails on one that does not fit), so that a node sorts just before its
    descendants, siblings by their count vectors and a pool after them.  Bytes compare in C (2026-10-30: sorting
    288@10's 770,000 keys as tuples of tuples, as before, took a minute).  Cached, up to 2^18 keys."""
    out = []
    for part in key.split():
        M, v = part.split(':', 1)
        if v.startswith('['): kind, nums, sha = 0, [int(t) for t in v[1:-1].split(',')], ''
        else:
            pool = re.fullmatch(r'#(\d+):([0-9a-f]{40})', v)
            assert pool, key
            kind, nums, sha = 1, [int(pool[1])], pool[2]
        out.append(struct.pack(f'>HB{len(nums) + 1}H', int(M), kind, *(t + 1 for t in nums), 0) + sha.encode())
    return b''.join(out)


def below(key, above):
    """Whether key's node is a proper descendant of above's."""
    return key != above and (above == '' or key.startswith(above + ' '))


def prefixes(key):
    """The keys of the node's ancestors, the top node's '' first."""
    parts = key.split()
    return [' '.join(parts[:i]) for i in range(len(parts))]


def infeasible_above(key, final):
    """Whether an ancestor of the key's node is INFEASIBLE in the journal's last records final."""
    return any(final.get(a, {}).get('verdict') == 'INFEASIBLE' for a in prefixes(key))


def live_keys(final):
    """The journal's keys less those below an INFEASIBLE one (see live in the vocabulary): those with no INFEASIBLE
    ancestor (in tree order an INFEASIBLE key's descendants follow it, so this is the old sort's cut)."""
    return {k for k in final if not infeasible_above(k, final)}


def sea(final, budgets, cache, running, unnamed=()):
    """The sea (see the vocabulary) of the journal's last records final under these budgets, with the splits cached so
    far and the keys running now: {'depth', 'keys' (its groups' sub-cases), 'groups' (each a string of its dots'
    statuses, as indices into SEA_STATUSES), 'counts' (by status)}.  unnamed holds (its parent's key, its status) for each
    running or queued node whose own key is not known here (its parent's split is not cached, and a progress line names a
    node only when it is done): each is a dot of that status in its parent's group, after that group's other dots, in
    unnamed's order (2026-10-27: before, the 288@10 page drew none of its 9 running nodes and 3106 of its 3113 queued
    ones, so that it looked mostly settled beside an ETA of months).  A Tree of final, drawn (see Tree)."""
    return grown_tree(final, budgets, cache).sea_of(set(running), unnamed)


STATES = {}                                 # a Tree key's states, each kept once


def grown_tree(final, budgets, cache):
    """A Tree of the journal's last records final, every key applied and every group drawn."""
    tree = Tree(final, budgets, cache)
    for k in final: tree.apply(k)
    tree.redraw(math.inf)
    return tree


class Tree:
    """The journal's keys under one pass's budgets, kept up to date key by key (see Reading.tree): each key's liveness
    (see live), status and whether its cached split is drawn; the live keys by depth, with their counts by depth and
    status and how many are INFEASIBLE; and the sea's static nodes, the live keys and the cached children of the live
    split ones (each counted once per source), by group (the sub-case at the sea's depth, or a shallower key itself),
    each group drawn (see sea: its nodes with no node below them, in tree order) with its open leaves.  Applying a key
    costs about its depth, but for an INFEASIBLE key above others, which scans the keys for them (the width test's
    case, 2026-10-11); a group is drawn again only after it changed.  sea_of adds a snapshot's running keys and
    unnamed nodes."""

    def __init__(self, final, budgets, cache):
        self.final, self.budgets, self.cache = final, list(budgets), cache
        self.bottom = len(budgets) - 1
        self.depth = min(SEA_DEPTH, self.bottom - 1)
        self.state = {}                         # key -> (live, status or None, its cached split drawn, live INFEASIBLE)
        self.counts = collections.Counter()     # (depth, status) of the live keys
        self.infeasible = 0                     # the live INFEASIBLE keys
        self.by_depth = collections.defaultdict(set)    # the live keys, by depth
        self.below = collections.Counter()      # the keys applied strictly below each key
        self.waiting = set()                    # the live split keys whose splits are not cached yet
        self.refs = collections.Counter()       # the sea's static nodes, each with its count of sources
        self.members = collections.defaultdict(set)     # the static nodes, by group
        self.under = collections.Counter()      # the static nodes strictly below each key
        self.dirty = set()                      # the groups changed since drawn
        self.drawn, self.opens = {}, {}         # each group's dots and open leaves, where it has any

    def group(self, key): return ' '.join(key.split()[:self.depth])

    def apply(self, key):
        """Bring the key, new or with a new record in final, up to its record."""
        if key not in self.state:
            for a in prefixes(key): self.below[a] += 1
        self.refresh(key, not infeasible_above(key, self.final))
        if self.final[key]['verdict'] == 'INFEASIBLE' and self.below[key]:     # its keys below are live no more
            for k in [k for k in self.state if below(k, key)]: self.refresh(k, False)

    def refresh(self, key, live):
        """Bring the key's state to its record, live or not, with everything kept of it.  A live UNKNOWN leaf is one of
        the open leaves, whose key must hold no pool (parse_key asserts it)."""
        r = self.final[key]
        st = status(key, self.final, self.budgets) if live else None
        drawn = st == 'split' and key in self.cache
        new = (live, st, drawn, live and r['verdict'] == 'INFEASIBLE')
        new = STATES.setdefault(new, new)           # one tuple per distinct state, however many keys share it
        old = self.state.get(key, (False, None, False, False))
        if new == old: return
        if live and r['verdict'] == 'UNKNOWN' and leaf(key, self.bottom): parse_key(key)
        self.state[key] = new
        d = len(key.split())
        self.counts[d, old[1]] -= old[0]
        self.counts[d, st] += live
        (self.by_depth[d].add if live else self.by_depth[d].discard)(key)
        self.infeasible += new[3] - old[3]
        (self.waiting.add if st == 'split' and not drawn else self.waiting.discard)(key)
        if live != old[0]: self.node(key, 1 if live else -1)
        for c in self.cache[key] if drawn != old[2] else (): self.node(c, 1 if drawn else -1)
        self.dirty.add(self.group(key))

    def node(self, key, delta):
        """One more (delta 1) or one fewer (-1) source of key among the sea's static nodes."""
        before = self.refs[key]
        assert before + delta >= 0, key
        self.refs[key] = before + delta
        if self.refs[key] == 0: del self.refs[key]
        if (before > 0) == (before + delta > 0): return
        g = self.group(key)
        (self.members[g].add if delta > 0 else self.members[g].discard)(key)
        self.dirty.add(g)
        for a in prefixes(key):
            self.under[a] += delta
            if self.under[a] == (1 if delta > 0 else 0): self.dirty.add(self.group(a))   # a's own dot needs nothing below it

    def expand(self):
        """Take in the splits cached since: their live split keys' children join the static nodes."""
        for key in [k for k in self.waiting if k in self.cache]: self.refresh(key, True)

    def redraw(self, n):
        """Draw up to n changed groups again."""
        while n and self.dirty:
            g = next(iter(self.dirty))
            self.draw(g)
            self.dirty.discard(g)
            n -= 1

    def draw(self, g):
        """Draw group g: its dots, and its open leaves as open_list gives them."""
        keys = sorted(self.members.get(g, ()), key=tree_order)
        dots = ''.join(str(SEA_STATUSES.index(status(k, self.final, self.budgets))) for k in keys if not self.under[k])
        opens = [(k, self.final[k]['budget'], self.state[k][1]) for k in keys
                 if self.state.get(k, (False,))[0] and self.final[k]['verdict'] == 'UNKNOWN' and leaf(k, self.bottom)]
        for kept, value in ((self.drawn, dots), (self.opens, opens)):
            kept[g] = value
            if not value: del kept[g]

    def sea_of(self, running, unnamed):
        """sea's value: the drawn groups, the running keys (a set) among the nodes with their dots running, and each
        unnamed node's dot at the end of its parent's group (see sea)."""
        assert self.depth >= 0, self.budgets
        extra = {k for k in running if k not in self.refs}
        lifted = collections.Counter(a for k in extra for a in prefixes(k))
        out = dict(self.drawn)
        for g in {self.group(k) for k in running} | {self.group(a) for a in lifted}:
            keys = sorted(self.members.get(g, set()) | {k for k in extra if self.group(k) == g}, key=tree_order)
            out[g] = ''.join(str(SEA_STATUSES.index('running' if k in running else status(k, self.final, self.budgets)))
                             for k in keys if not self.under[k] + lifted[k])
        for k, s in unnamed:
            out[self.group(k)] = out.get(self.group(k), '') + str(SEA_STATUSES.index(s))
        keys = sorted((g for g in out if out[g]), key=tree_order)
        groups = [out[g] for g in keys]
        text = ''.join(groups)
        return {'depth': self.depth, 'keys': keys, 'groups': groups,
                'counts': {s: text.count(str(i)) for i, s in enumerate(SEA_STATUSES)}}

    def rows(self, levels, bottom):
        """level_rows of these levels: an enumerated level counted from its sub-cases, a deeper one from the live keys'
        counts."""
        rows = []
        for d in range(bottom + 1):
            known = d < len(levels)
            # TODO: error copy; says the journal holds sub-cases of an enumerated level that the run's split does not give, naming the level
            assert not known or self.by_depth[d] <= set(levels[d]), f'Claude: "the journal has level-{d} sub-cases that split() does not give"'
            c = (collections.Counter(status(k, self.final, self.budgets) for k in levels[d]) if known else
                 {s: self.counts[d, s] for s in STATUSES})
            rows.append({'depth': d, 'enumerated': known,
                         'counts': {s: c[s] if known or s != 'pending' else None for s in STATUSES}})
        return rows

    def tally(self):
        """The live keys' counts by status."""
        return collections.Counter({s: sum(self.counts[d, s] for d in range(self.bottom + 1)) for s in STATUSES})

    def open_list(self):
        """survey's open_list: each live UNKNOWN leaf (key, its budget, its status), in tree order, as drawn."""
        return list(itertools.chain.from_iterable(self.opens[g] for g in sorted(self.opens, key=tree_order)))


def parse_key(key):
    """The node whose overnight_v5.node_key is key (asserted).  A pool's key holds a count and a hash, not its
    members, so it has no node here (asserted)."""
    pairs = [part.split(':', 1) for part in key.split()]
    # TODO: error copy; says a pool came back UNKNOWN, and its key does not hold the vectors progress.py would need to split it
    assert all(v.startswith('[') for _, v in pairs), f'Claude: "the pool {key} came back UNKNOWN; its key does not hold its members"'
    node = tuple((int(M), (tuple(int(t) for t in v[1:-1].split(',')),)) for M, v in pairs)
    assert v5.node_key(node) == key, key
    return node


def children(key, order, cache):
    """overnight_v5.split's children of the key's node, as keys, kept in cache by key so each node is split once."""
    if key not in cache: cache[key] = [v5.node_key(c) for c in v5.split(order, parse_key(key))]
    return cache[key]


def recover_splits(R, wanted, cache):
    """Use one pass's complete children, with an explicit closed pool, in split's original order."""
    latest = R['passes'][-1]
    identity = lambda p: (p['n'], p['order'], p['moduli'], p['pool_budget'])
    counts, found = {}, {}
    seen = collections.defaultdict(set)
    for p in R['passes']:
        if identity(p) != identity(latest): continue
        sizes, observed = {}, collections.defaultdict(dict)
        w, r, c = 1, 0, 0
        for nd in p['nodes']:
            key = nd['key']
            submit = nd['running'] + 1 - r
            skip = nd['closed'] - c - (nd['verdict'] == 'INFEASIBLE')
            K = nd['waiting'] - w + submit + skip
            if key in wanted:
                assert nd['verdict'] == 'UNKNOWN' and '#' not in key
                assert submit >= 0 and skip >= 0 and K >= 0
                assert sizes.get(key, K) == K and counts.get(key, K) == K
                sizes[key] = counts[key] = K
            up = parent_key(key)
            if key and up in wanted:
                assert observed[up].get(key, nd['verdict']) == nd['verdict']
                observed[up][key] = nd['verdict']
                seen[up].add(key)
            w, r, c = nd['waiting'], nd['running'], nd['closed']
        for key, K in sizes.items():
            kids = observed[key]
            pools = [k for k in kids if '#' in k.split()[-1]]
            if len(kids) == K and len(pools) == 1 and kids[pools[0]] == 'INFEASIBLE':
                ordered = sorted((k for k in kids if k != pools[0]),
                                 key=lambda k: json.loads(k.split()[-1].split(':', 1)[1])) + pools
                assert found.get(key, ordered) == ordered
                found[key] = ordered
    for key, kids in found.items():
        assert seen[key] <= set(kids) and counts[key] == len(kids)
        assert cache.get(key, kids) == kids
    cache.update(found)
    return cache



def resplits(R, order, cache):
    """cache, holding the splits of the nodes the run's current pass splits again: UNKNOWN within their budget above
    the bottom when it began.  The replay needs their children (see kind in the vocabulary), which an estimate alone
    asks for: splitting them for an ended run would be work for nothing (240@11's last 88 took 626 s)."""
    budgets = R['passes'][-1]['budgets']
    start = {r['key']: r for r in R['records'][:R['bounds'][-1]]}
    wanted = {k for k, r in start.items() if r['verdict'] == 'UNKNOWN'
              and len(k.split()) < len(budgets) - 1 and r['budget'] >= budget_of(k, budgets)}
    recover_splits(R, wanted, cache)
    for k in sorted(wanted): children(k, order, cache)
    return cache


def enumerate_levels(final, budgets, order, cache, deepest):
    """The enumerated levels (see the vocabulary), each a list of keys; overnight_v5 must be configured for the run."""
    levels = [['']]
    for d in range(min(deepest, len(budgets) - 1)):
        if any(status(k, final, budgets) == 'pending' for k in levels[d]): break
        levels.append([c for k in levels[d] if final.get(k, {}).get('verdict') in ('UNKNOWN', 'CLOSED')
                       for c in children(k, order, cache)])
    return levels


def level_rows(levels, final, budgets, bottom):
    """One row per depth 0..bottom: its depth, whether it is enumerated, and its counts by status.  An enumerated
    level counts its sub-cases; a deeper one counts the journal's live keys (see live) at its depth, its pending count
    unknown (None).  Every live key at an enumerated depth must be a sub-case of that level (asserted).  Tree.rows of
    a Tree of final."""
    tree = Tree(final, budgets, {})
    for k in final: tree.apply(k)
    return tree.rows(levels, bottom)


# ---------- this pass's work at the estimate's level ----------

def work(level, depth, stats, nodes):
    """This pass's work at the enumerated level at this depth, a list of keys with their statuses in stats, given the
    current pass's progress lines: the counts size (the level's sub-cases), before (settled before this pass), work
    (touched by a line of this pass at or below them, or not settled), and of the work, done (settled or open),
    progress (split) and pending."""
    return work_of(level, stats, touched_at(nodes, depth))


def touched_at(nodes, depth):
    """The sub-cases at this depth that these progress lines touched: their nodes' ancestors there, or themselves."""
    return {' '.join(nd['key'].split()[:depth]) for nd in nodes if len(nd['key'].split()) >= depth}


def work_of(level, stats, touched):
    """work's counts of the level, given the sub-cases its pass touched there."""
    work = [k for k in level if k in touched or stats[k] != 'settled']
    return {'size': len(level), 'before': len(level) - len(work), 'work': len(work),
            'done': sum(stats[k] in ('settled', 'open') for k in work), 'progress': sum(stats[k] == 'split' for k in work),
            'pending': sum(stats[k] == 'pending' for k in work)}


# ---------- the estimate ----------

class Node:
    """A node of the current pass's tree as the replay knows it: key (None while a split that is not cached hides it),
    parent and depth, kids (in the order search() pushes them: overnight_v5.sibling_order's in a pass that shuffles,
    the split's before), state ('pending' in the stack, 'running', 'done' with a progress line, or
    'skipped', settled before the pass), cost (a done node's solve + split seconds), start (a running node's start
    time), fresh (a done node that certbb solved in this pass, not a resplit); and index, its place among its parent's
    kids, and tot, its subtree's cost so far as a Grown tree last summed it (see Grown.sofar)."""
    __slots__ = ('key', 'parent', 'depth', 'kids', 'state', 'cost', 'start', 'fresh', 'index', 'tot')

    def __init__(self, key, parent, depth, index=0):
        self.key, self.parent, self.depth, self.index = key, parent, depth, index
        self.kids, self.state, self.cost, self.start, self.fresh, self.tot = [], 'pending', 0.0, None, False, 0.0


def parent_key(key): return ' '.join(key.split()[:-1])


def path(node):
    """The node's place in tree order: the indices of it and its ancestors among their parents' kids, from the top."""
    out = []
    while node.parent is not None:
        out.append(node.index)
        node = node.parent
    return out[::-1]


def replay(state):
    """The replay (see the vocabulary) as of state['t']: (root, stack, running), the stack's top last.  A Grown of the
    state's pass, grown by all its lines."""
    g = Grown(state).grow(state)
    return g.root, g.stack, g.running


class Grown:
    """replay()'s tree of a run's current pass, kept by the watcher's reading (see reading in the vocabulary) and grown
    line by line, with what estimate() reads of it (its view, see estimate) kept as it grows, so that an estimate costs
    about the pass's pending work, not its history: the done nodes above the bottom by depth, the fresh ones apart, each
    list in tree order (by path); the done fresh leaves' costs and floors; and each node's tot, summed again only for the
    nodes changed since and their ancestors.  The refill after the last line is undone before more lines are replayed.
    Its view's pending and running nodes are made from its stack and running jobs in tree order, a resplit one given
    its children as Walk gives them.  A Grown holds one pass with its records at the start: a split cached after its
    node was done with unnamed children would have replay() name them, so that a reading then grows another (see
    Reading.estimating)."""

    def __init__(self, state):
        p = state['passes'][-1]
        self.start, self.budgets, self.P, self.shuffled = p['start'], list(state['budgets']), state['processes'], p['shuffled']
        self.cache, self.fas = state['cache'], state['final_at_start']
        self.settled = {k for k, r in self.fas.items() if r['verdict'] in v5.SETTLED}
        self.bottom = len(self.budgets) - 1
        self.root = Node('', None, 0)
        self.stack, self.running, self.refilled = [self.root], [], []
        self.w, self.r, self.c, self.at = 1, 0, 0, None     # the previous line's waiting, running and closed (see replay)
        self.seen, self.last = 0, None                         # the pass's lines replayed, the last of them
        self.done_all, self.done_fresh = collections.defaultdict(list), collections.defaultdict(list)
        self.leaf_costs, self.leaf_floors = [], set()
        self.changed = {self.root}                             # nodes whose own cost or kids changed since summed
        self.unnamed = set()                                   # keys of done nodes with unnamed kids
        self.kinds_of, self.expanded = {}, set()               # the region's kinds (see view) and its resplit nodes given kids

    def grow(self, state):
        """Replay state's lines not replayed yet, between undoing the last refill and refilling (see replay), each step
        atomic."""
        p = state['passes'][-1]
        # TODO: error copy; says the replay kept for a pass was given a state of another pass, or one that does not continue what it replayed, naming the state
        assert ((p['start'], list(state['budgets']), state['processes'], p['shuffled']) == (self.start, self.budgets, self.P, self.shuffled)
                and state['cache'] is self.cache and state['final_at_start'] is self.fas and self.seen <= len(p['nodes'])
                and (not self.seen or p['nodes'][self.seen - 1] is self.last)), f'Claude: "the kept replay does not lead to {state["label"]}"'
        with atomic(): self.unfill()
        while self.seen < len(p['nodes']):
            with atomic():
                for nd in p['nodes'][self.seen:self.seen + STEP]:
                    self.line(nd, state['label'])
                    self.seen, self.last = self.seen + 1, nd
        with atomic(): self.refill(p)
        return self

    def pop(self, at):
        """search() pops the top: a settled node it skips, another it submits."""
        node = self.stack.pop()
        if node.key in self.settled:
            node.state = 'skipped'
            return 0
        node.state, node.start = 'running', at
        self.running.append(node)
        return 1

    def line(self, nd, label):
        """Replay one progress line nd (replay's step), and keep what estimate reads of its node."""
        submit = nd['running'] + 1 - self.r
        skip = nd['closed'] - self.c - (nd['verdict'] == 'INFEASIBLE')   # search() counts each settled node it skips closed
        K = nd['waiting'] - self.w + submit + skip                     # so the rest of the waiting count's change is the children
        splits = nd['verdict'] == 'UNKNOWN' and len(nd['key'].split()) < self.bottom
        kids = self.cache.get(nd['key'])
        if kids is not None and self.shuffled: kids = v5.sibling_order(nd['key'], kids)
        # TODO: error copy; says the replay of search() cannot account for a progress line's counts, naming the state and the line
        assert submit >= 0 and skip >= 0 and K >= 0 and (splits or K == 0) and (kids is None or len(kids) == K), \
            f'Claude: "the replay of {label} cannot account for line [{nd["i"]}]"'
        first = nd['t'] - nd['solve'] - nd['split'] if self.at is None else self.at
        while submit or skip:          # the pops between the previous line and this one, as many of each as counted
            took = self.pop(first)
            submit, skip = submit - took, skip - (1 - took)
            assert submit >= 0 and skip >= 0, (label, nd['i'])
        node = find(self.running, nd)
        self.running.remove(node)
        node.key, node.state, node.cost = nd['key'], 'done', nd['solve'] + nd['split']
        rec = self.fas.get(nd['key'])
        node.fresh = rec is None or rec['budget'] < budget_of(nd['key'], self.budgets)
        assert K == 0 or (splits and members(nd['key']) <= 1), (label, nd['i'])    # a pool never splits
        gone = list(node.kids)                                         # an expansion (see view), the line's kids replace
        while gone:
            n = gone.pop()
            self.kinds_of.pop(n, None)
            self.expanded.discard(n)
            gone += n.kids
        node.kids = ([Node(c, node, node.depth + 1, i) for i, c in enumerate(kids)] if kids is not None else
                     [Node(None, node, node.depth + 1, i) for i in range(K)])
        self.stack.extend(node.kids)
        # TODO: error copy; says the replay of search() disagrees with a progress line's waiting or running count, naming the state and the line
        assert (len(self.stack), len(self.running)) == (nd['waiting'], nd['running']), f'Claude: "the replay of {label} breaks at line [{nd["i"]}]"'
        self.w, self.r, self.c, self.at = nd['waiting'], nd['running'], nd['closed'], nd['t']
        self.changed.add(node)
        self.kinds_of.pop(node, None)                                  # done, it leaves the region
        self.expanded.discard(node)
        (self.unnamed.add if kids is None and K else self.unnamed.discard)(nd['key'])
        if node.depth < self.bottom:                                   # a member of its depth's population (pop_at)
            bisect.insort(self.done_all[node.depth], node, key=path)
        if node.depth < self.bottom and node.fresh:
            bisect.insort(self.done_fresh[node.depth], node, key=path)
        if node.depth == self.bottom and node.fresh:                   # a member of the leaf urn
            self.leaf_costs.append(node.cost)
            self.leaf_floors.add(0 if rec is None else rec['budget'])     # floor_of

    def refill(self, p):
        """The refill after the last line, as search() makes it, each pop kept to be undone."""
        while p['nodes'] and self.stack and len(self.running) < self.P:
            self.refilled.append(self.stack[-1])
            self.pop(self.at)

    def unfill(self):
        """Undo the refill: its nodes back on the stack, pending, the last popped first."""
        while self.refilled:
            node = self.refilled.pop()
            if node.state == 'running':
                top = self.running.pop()
                assert top is node, node.key
            node.state, node.start = 'pending', None
            self.stack.append(node)
            self.changed.add(node)

    def view(self, state, speed, history):
        """estimate's view of the tree as of state (see estimate): grown to it; its pending and running nodes, the region,
        in tree order with their kinds (a resplit one given its kids, as Walk does, in one atomic block); the speed and
        the history given.  A region node's kind and kids are kept while it stays pending or running: they depend on its
        key, depth and the records at the pass's start alone."""
        self.grow(state)
        self.state, self.measured, self.histories = state, speed, history
        self.kinds, self.region = {}, []

        def visit(node):
            self.region.append(node)
            if node not in self.kinds_of: self.kinds_of[node] = classify(node, state, self.bottom)
            self.kinds[node] = self.kinds_of[node]
            if self.kinds[node] == 'resplit' and node not in self.expanded:
                expand_resplit(node, state)
                self.expanded.add(node)
                self.changed.add(node)
            for c in node.kids: visit(c)
        with atomic():
            for node in sorted(self.stack + self.running, key=path): visit(node)
        return self

    def pop_at(self, d):
        """The population at depth d (see the vocabulary): its fresh nodes done in this pass, else all done there."""
        return self.done_fresh[d] or self.done_all[d]

    def sofar(self, t, timed):
        """Each node's cost so far in this pass (see partway), as estimate's total gives it: tot summed again for the
        nodes changed since the last sum, the running ones (a running leaf's own cost grows with t) and their ancestors,
        the deepest first.  The mapping of a node to its tot (TOTS)."""
        todo = set()
        for n in itertools.chain(self.changed, self.running):
            while n is not None and n not in todo:
                todo.add(n)
                n = n.parent
        for n in sorted(todo, key=lambda n: -n.depth):
            own = n.cost if n.state == 'done' else t - n.start if n in timed else 0.0
            n.tot = own + sum(c.tot for c in n.kids)
        self.changed = set()
        return TOTS

    def speed(self): return self.measured
    def history(self): return self.histories

    def nodes(self):
        """Every node, in tree order."""
        out = []

        def walk(node):
            out.append(node)
            for c in node.kids: walk(c)
        walk(self.root)
        return out


class Tots:
    """The mapping of each node of a Grown tree to its cost so far, tot (see Grown.sofar)."""
    def __getitem__(self, node): return node.tot


TOTS = Tots()


def expand_resplit(node, state):
    """Give a pending or running resplit node its children from the cache, in the order search() will push them, each
    pending: the replay knows them only once the node is done."""
    # TODO: error copy; says the cache lacks the split of a node that search() will split again, naming it
    assert node.depth == len(state['budgets']) - 1 or node.key in state['cache'], f'Claude: "no cached split for {node.key}"'
    kids = state['cache'].get(node.key, [])
    if state['passes'][-1]['shuffled']: kids = v5.sibling_order(node.key, kids)
    node.kids = [Node(c, node, node.depth + 1, i) for i, c in enumerate(kids)]


class Walk:
    """replay()'s tree as estimate() reads it (its view, see estimate), made by walking every node, the pending and
    running ones classified and a resplit one given its kids (expand_resplit)."""

    def __init__(self, state, root, stack, running):
        self.state, self.root, self.stack, self.running = state, root, stack, running
        bottom = len(state['budgets']) - 1
        self.kinds, self.all = {}, []

        def walk(node):                 # every node; the kinds of the pending and running, a resplit one's children made
            self.all.append(node)
            if node.state in ('pending', 'running'):
                self.kinds[node] = classify(node, state, bottom)
                if self.kinds[node] == 'resplit' and not node.kids: expand_resplit(node, state)
            for c in node.kids: walk(c)
        walk(root)
        self.region = [n for n in self.all if n in self.kinds]
        leaves = [n for n in self.all if n.state == 'done' and n.fresh and n.depth == bottom]
        self.leaf_costs, self.leaf_floors = [n.cost for n in leaves], {floor_of(n, state) for n in leaves}
        self.by_depth = collections.defaultdict(list)
        for n in self.all: self.by_depth[n.depth].append(n)

    def pop_at(self, d):
        """The population at depth d (see the vocabulary): its fresh nodes done in this pass, else all done there."""
        return ([n for n in self.by_depth[d] if n.state == 'done' and n.fresh] or
                [n for n in self.by_depth[d] if n.state == 'done'])

    def sofar(self, t, timed):
        """Each node's cost so far in this pass (see partway): its own (a done node's cost, a running leaf's elapsed
        time) and its kids'."""
        sofar = {}

        def total(node):
            own = node.cost if node.state == 'done' else t - node.start if node in timed else 0.0
            sofar[node] = own + sum(total(c) for c in node.kids)
            return sofar[node]
        total(self.root)
        return sofar

    def speed(self): return speed(self.state)
    def history(self): return history_costs(self.state)
    def nodes(self): return self.all


def find(running, nd):
    """The running node that the progress line nd reports: the one with its key, else (its parent's split not cached)
    the one of its parent's unnamed children whose start is nearest the line's time less its duration."""
    named = [n for n in running if n.key == nd['key']]
    if named: return named[0]
    up = parent_key(nd['key'])
    unnamed = [n for n in running if n.key is None and n.parent.key == up]
    # TODO: error copy; says a progress line reports a node the replay never started, naming the line
    assert unnamed, f'Claude: "line [{nd["i"]}] reports a node the replay never started"'
    began = nd['t'] - nd['solve'] - nd['split']
    return min(unnamed, key=lambda n: abs(n.start - began))


def classify(node, state, bottom):
    """The node's kind (see the vocabulary), from the journal as the pass found it."""
    rec = None if node.key is None else state['final_at_start'].get(node.key)
    if rec is None: return 'leaf' if node.depth == bottom else 'subtree'
    if rec['verdict'] in v5.SETTLED: return 'skip'
    if rec['budget'] >= budget_of(node.key, state['budgets']): return 'resplit'
    # TODO: error copy; says a node above the bottom is to be solved again at a larger budget, which this estimate does not model, naming it
    assert node.depth == bottom, f'Claude: "{node.key} is solved again above the bottom: not modeled"'
    return 'leaf'


def floor_of(node, state):
    """A leaf kind's floor (see the vocabulary)."""
    rec = None if node.key is None else state['final_at_start'].get(node.key)
    return 0 if rec is None else rec['budget']


def speed(state):
    """Seconds per LP solve over every fresh leaf solve the log holds (see the vocabulary), or None if there is none:
    each bottom record (key, budget) of the journal is claimed by the first progress line that solved it."""
    seconds, lps = speed_sums(state)
    return seconds / lps if lps else None


def speed_sums(state):
    """speed's sums: the claiming lines' solve seconds and their records' LP solves, added in log order."""
    bottom = len(state['budgets']) - 1
    recs = {(r['key'], r['budget']): r for r in state['records'] if r['verdict'] != 'CLOSED'}
    claimed, seconds, lps = set(), 0.0, 0
    for p in state['passes']:
        for nd in p['nodes']:
            k = (nd['key'], budget_of(nd['key'], p['budgets']))
            if len(nd['key'].split()) == bottom and k in recs and k not in claimed:
                claimed.add(k)
                seconds, lps = seconds + nd['solve'], lps + recs[k]['lps']
    return seconds, lps


class Urn:
    """A Polya urn (see the vocabulary) in each of REPLICATES replicates: one ball per member (members: a 1-d array, the
    same in every replicate, or REPLICATES x m), one per draw made, and one new ball, whose values new(rows, e) gives:
    one value above e for each entry of rows, an index array of replicates that may repeat one.  Its balls may number
    at most DRAWS (asserted): 288@10's boxsplit pass would begin with 431,256 pending leaves, 2000 draws of each, 6.9 GB
    (2026-10-30)."""

    def __init__(self, rng, members, new, room):
        R = REPLICATES
        # TODO: error copy; says an urn would hold more numbers than the watcher allows, giving how many
        assert R * (room + 1) <= DRAWS, f'Claude: "an urn of {R * (room + 1):,} balls is more than {DRAWS:,}"'
        self.rng, self.new, self.fixed, self.m = rng, new, members.ndim == 1, members.shape[-1]
        # the members (sorted if fixed), with one more column so that indexing never fails (a pick never takes it)
        self.M = np.append(np.sort(members), 0.0) if self.fixed else np.concatenate([members, np.zeros((R, 1))], axis=1)
        self.balls = np.zeros((R, room + 1))            # the draws' balls, in order
        self.k, self.plain = 0, False                   # how many draws; whether one was plain (censored ones go first)

    def pick(self, rows, e=-np.inf):
        """One value for each entry of rows: a ball above e (a member, or an earlier draw: in a censored pick, every one
        of those exceeds e, as censored draws go longest first and before plain ones), or the new ball's value."""
        assert e == -np.inf or (self.fixed and not self.plain)      # only a leaf urn has censored draws
        a = self.m - np.searchsorted(self.M[:self.m], e, side='right') if self.fixed else self.m
        u = np.floor(self.rng.random(len(rows)) * (a + self.k + 1)).astype(int)
        out = np.empty(len(rows))
        mem, old, new = u < a, (u >= a) & (u < a + self.k), u == a + self.k
        j = np.minimum(self.m - a + u[mem], self.m)
        out[mem] = self.M[j] if self.fixed else self.M[rows[mem], j]
        out[old] = self.balls[rows[old], u[old] - a]
        out[new] = self.new(rows[new], e)
        return out

    def draw(self, e=-np.inf):
        """One value per replicate, as pick gives, then a ball of the urn."""
        v = self.pick(np.arange(REPLICATES), e)
        self.plain |= e == -np.inf
        self.balls[:, self.k] = v
        self.k += 1
        return v


def gap_ball(rng, lo, hi):
    """The leaf urn's new ball (see urn in the vocabulary): log-uniform from the larger of lo and e up to the larger of hi
    and that.  Both ends are 0 only at speed 0 (every leaf solve the log holds took under its resolution, a tenth of a
    second), where the ball is 0: a log-uniform between two equal ends is that end."""
    def new(rows, e):
        b = max(lo, e)
        return b * (max(hi, b) / b) ** rng.random(len(rows)) if b else np.zeros(len(rows))
    return new


def lindy_ball(rng, top):
    """The boxsplit leaf urn's new ball (see urn in the vocabulary; dreeves, 2026-10-19, the Lindy effect in Gott's
    form): a time not seen yet, s / U above s, the larger of top (the longest time seen in the pass) and e, with U
    uniform on (0, 1]: the scale-free tail P(T > t) = s / t, so that a leaf that has outrun every time seen is expected
    to run on in proportion to its age, where a ceiling at the longest seen had it about to finish.  Its mean is
    infinite, so the estimate's center is its median (see estimate)."""
    def new(rows, e):
        return max(top, e) / (1.0 - rng.random(len(rows)))           # 1 - U is uniform on (0, 1]: never s / 0
    return new


def fresh_ball(rng, own, kids, below):
    """A subtree urn's new ball (see urn in the vocabulary): a fresh subtree, a uniformly chosen member's own job (own,
    its seconds) and split (kids, its count of children), its children each picked from the urn below."""
    def new(rows, e):
        j = rng.integers(0, len(own), len(rows))
        k = kids[j]
        # TODO: error copy; says a fresh subtree needs the urn of the depth below, which has no member
        assert below is not None or not k.any(), 'Claude: "no urn below a fresh subtree"'
        under = below.pick(np.repeat(rows, k)) if k.any() else np.zeros(0)
        return own[j] + np.bincount(np.repeat(np.arange(len(rows)), k), weights=under, minlength=len(rows))
    return new


def makespan(loads, items):
    """List scheduling (see the vocabulary): loads, REPLICATES x workers, the seconds each worker is busy at first;
    items, in order, each ('job', seconds) or ('fluid', seconds), the seconds REPLICATES-long arrays.  Returns when the
    last worker is free, per replicate."""
    a = loads.copy()
    rows, P = np.arange(a.shape[0]), a.shape[1]
    merged = []
    for kind, x in items:               # consecutive fluid items fill as one
        if kind == 'fluid' and merged and merged[-1][0] == 'fluid': merged[-1] = ('fluid', merged[-1][1] + x)
        else: merged.append((kind, x))
    for kind, x in merged:
        if kind == 'job':
            i = a.argmin(axis=1)
            a[rows, i] += x
        else:                           # the level T with sum over workers of max(0, T - a) = x
            s = np.sort(a, axis=1)
            T = (x[:, None] + np.cumsum(s, axis=1)) / np.arange(1, P + 1)
            nxt = np.concatenate([s[:, 1:], np.full((a.shape[0], 1), np.inf)], axis=1)
            level = T[rows, (T <= nxt).argmax(axis=1)]
            a = np.maximum(a, level[:, None])
    return a.max(axis=1)


# KNOWN FLAW, recorded at dreeves's request on 2026-10-12: this is not a calibrated Bayesian ETA.  In his words:
# "seemingly there's no attempt to make an actual bayesian estimate of the ETA but rather a best-case estimate if no
# more splits or whatever happen, which we know they will."  It does draw a pending subtree's cost from its depth's
# completed or partly completed subtrees.  A backtest on the only passes that ended on their own, 304@9's first two
# (every half hour, scratch-free: quals_progress.states()), found it noisy rather than one-sided: in pass 1 the mean ran
# 2-3x too high for most of the pass, in pass 2 about 1.3x too low, and the middle-80% band held the truth 22 of 31
# times.  240@11's pass 3 swung from about 6 h (2026-10-11 22:54) to about 118 h (2026-10-12 12:52).  The stopgap
# (2026-10-12): the ETA chart labels the ETA and the total with their bands' ranges, not the mean, and the band is the
# middle 90%.  A real fix would model the total remaining work's posterior (heavy-tailed subtree sizes, queue growth
# from splits) and be backtested on more finished passes.
# A likely cause, found 2026-10-13: search() takes siblings in an order whose cost grows (240@11's first 25 depth-5
# subtrees took about 0.2 worker-hours each, later ones 169 and 282+), so finished subtrees are no fair sample of the
# waiting ones.  The planned fix, before the next search: shuffled sibling order (the note above overnight_v5.search).
def history_costs(state):
    """Historical own costs and credits from preceding contiguous compatible passes.

    Maps retain only above-bottom donor keys. Historical leaf costs aggregate into
    their ancestors; a set of keys prevents repeat resplits becoming observations.
    Credits subtract this pass's repeated-job charges, already present in sofar,
    so a donor represents each job's first observation once, even after restarts.
    These values belong only in donor populations, never in remaining work.
    Geometry compatibility across source revisions is checked by run_modules.
    A History of the state, credited with its pass's lines.
    """
    return History(state).credit(state)


class History:
    """history_costs of one pass, kept as its lines come: the preceding passes' part made once, this pass's credits made
    line by line (each as history_costs makes it, in the same order)."""

    def __init__(self, state):
        def signature(p):
            return (p['n'], p['order'], tuple(p['budgets']), tuple(p['moduli']), p['pool_budget'])

        current = signature(state['passes'][-1])
        prior = []
        for p in reversed(state['passes'][:-1]):
            if signature(p) != current: break
            prior.append(p)
        self.own, self.totals, self.seen = {}, collections.defaultdict(float), set()
        self.bottom, self.credited = len(state['budgets']) - 1, 0
        for p in reversed(prior):
            for nd in p['nodes']:
                key = nd['key']
                if key in self.seen: continue
                self.seen.add(key)
                parts = key.split()
                cost = nd['solve'] + nd['split']
                if len(parts) < self.bottom: self.own[key] = cost
                for depth in range(min(len(parts) + 1, self.bottom)):
                    self.totals[' '.join(parts[:depth])] += cost

    def credit(self, state):
        """Credit this pass's lines not credited yet, in one atomic block; history_costs' value."""
        nodes = state['passes'][-1]['nodes']
        # TODO: error copy; says the history kept for a pass was asked for at an earlier time than before
        assert self.credited <= len(nodes), 'Claude: "a kept history goes back in time"'
        with atomic():
            for nd in nodes[self.credited:]:
                key = nd['key']
                if key not in self.seen: continue
                self.seen.remove(key)
                parts = key.split()
                cost = nd['solve'] + nd['split']
                for depth in range(min(len(parts) + 1, self.bottom)):
                    ancestor = ' '.join(parts[:depth])
                    self.totals[ancestor] = math.fsum((self.totals[ancestor], -cost))
            self.credited = len(nodes)
        return self.own, dict(self.totals)


def estimate(state, parts=None, view=None):
    """REPLICATES samples of the current pass's remaining hours of running (see the vocabulary), or an empty array (no
    estimate).  parts, if a dict, receives the pieces: the tree, the kinds, the draws, the items, the work, the speed.
    view is the replay's tree as the estimate reads it: its root, stack and running jobs, its pending and running
    nodes in tree order (region) with their kinds, the done fresh leaves' costs and floors, each depth's population
    (pop_at), the nodes' costs so far (sofar), the speed and the history (history_costs); by default a Walk of
    replay(state); a survey gives its reading's Grown (Reading.estimating), the same tree grown line by line."""
    budgets, P, t = state['budgets'], state['processes'], state['t']
    bottom, B = len(budgets) - 1, budgets[-1]
    view = Walk(state, *replay(state)) if view is None else view
    root, stack, running, kinds, region = view.root, view.stack, view.running, view.kinds, view.region
    censored = sorted((n for n in region if n.state == 'running' and kinds[n] == 'leaf'), key=lambda n: n.start)
    waiting = [n for n in region if n.state == 'pending' and kinds[n] == 'leaf']
    members = np.array(view.leaf_costs, dtype=float)
    floors = view.leaf_floors | {floor_of(n, state) for n in censored + waiting}
    assert len(floors) <= 1, (state['label'], floors)       # one leaf population per pass
    s = view.speed()
    if parts is not None: parts.update(root=root, stack=stack, running=running, kinds=kinds, nodes=view.nodes(), speed=s, members=members)
    if s is None: return np.array([])
    rng = np.random.default_rng(SEED)
    floor = max(floors, default=0)       # no leaf known yet: a first pass's, whose leaves are fresh
    lo = max((floor + 1) * s, members.max() if len(members) else 0.0)
    gap = (lo, max(B * s, lo))
    urns = {bottom: Urn(rng, members, gap_ball(rng, *gap), len(censored) + len(waiting))}
    if parts is not None: parts.update(gap=gap, floor=floor, urns=urns)
    rem = {}                            # node -> its remaining seconds of work, REPLICATES-long (absent: none)
    for n in censored: rem[n] = urns[bottom].draw(t - n.start) - (t - n.start)
    for n in waiting: rem[n] = urns[bottom].draw()
    sofar = view.sofar(t, set(censored))
    historical_own, historical_total = view.history()
    above, marked = collections.defaultdict(list), set()     # by depth, the region's done or resplit ancestors
    for n in region:
        a = n.parent
        while a is not None and a not in marked:
            marked.add(a)
            above[a.depth].append(a)
            a = a.parent
    subtrees = collections.defaultdict(list)                  # by depth, the region's nodes of kind 'subtree', in tree order
    for n in region:
        if kinds[n] == 'subtree': subtrees[n.depth].append(n)
    zero = np.zeros(REPLICATES)
    for d in range(bottom, -1, -1):
        for n in above[d]:              # a done or resplit node's remaining work is its children's
            assert n.state == 'done' or kinds.get(n) == 'resplit', (state['label'], n.key)
            below = [rem[c] for c in n.kids if c in rem]
            if below: rem[n] = sum(below, zero)
        if d == bottom: continue
        # the population: the depth's fresh nodes done in this pass, or with none its nodes split again
        pop = view.pop_at(d)
        draws = subtrees[d]
        if draws and not pop: return np.array([])
        if pop:
            eventual = np.tile(np.array([math.fsum((sofar[n], historical_total.get(n.key, 0.0))) for n in pop]), (REPLICATES, 1))
            for j, n in enumerate(pop):
                if n in rem: eventual[:, j] += rem[n]
            own, kids = np.array([historical_own.get(n.key, n.cost) for n in pop]), np.array([len(n.kids) for n in pop])
            urns[d] = Urn(rng, eventual, fresh_ball(rng, own, kids, urns.get(d + 1)), len(draws))
        for n in draws: rem[n] = urns[d].draw()
    items = []

    def expand(node):                   # a node's items, in the order search() reaches them
        k = kinds[node]
        if k == 'leaf': items.append(('job', rem[node]))
        elif k == 'subtree': items.append(('fluid', rem[node]))
        elif k == 'resplit':
            for c in reversed(node.kids): expand(c)
    for n in running:
        if kinds[n] != 'leaf': expand(n)
    for n in reversed(stack): expand(n)
    assert len(running) <= P, state['label']
    loads = np.zeros((REPLICATES, P))
    for j, n in enumerate(n for n in running if kinds[n] == 'leaf'): loads[:, j] = rem[n]
    work = loads.sum(axis=1) + sum((x for _, x in items), zero)
    assert np.allclose(work, rem.get(root, zero)), state['label']     # the items and loads are all the remaining work
    span = makespan(loads, items)
    if parts is not None: parts.update(rem=rem, items=items, loads=loads, work=work, sofar=sofar)
    return span / HOUR


# ---------- one run ----------


def survey(n, order, journal, log, procs, now, cache, etas, reading=None):
    """The run (n, order) as its journal and log, the process list and the time now (epoch seconds) show it: what the
    data file needs of it, and more; cache holds the run's splits (see children), etas its record of ETAs (see the
    vocabulary), to which this snapshot's is added: [the median of its draws, then their QUANTILES], None with none (an
    ended run has none), by its time in whole seconds.  reading is the watcher's Reading of the run, kept between
    snapshots; by default a new one, which reads the files whole: the same survey."""
    v5.configure(n, order)
    reading = Reading(journal, log) if reading is None else reading
    # TODO: error copy; says the watcher's reading of a run was handed another run's files, naming both
    assert (reading.journal, reading.log) == (journal, log), f'Claude: "a reading of {reading.journal} given {journal}"'
    R = reading.advance()
    passes = R['passes']
    p = passes[-1]
    # TODO: error copy; says the log's last start line names another length, order, cascade or pool budget than overnight_v5's settings for this run
    assert (p['n'], p['order'], p['moduli'], p['pool_budget']) == (n, order, list(v5.CASCADE), v5.POOL_BUDGET), f'Claude: "the log of {n} {order} does not match overnight_v5.py"'
    budgets, bottom = p['budgets'], len(v5.CASCADE)
    assert len(budgets) == bottom + 1
    final = reading.final.records
    state = run_state(procs, 'overnight_v5.py', n, order, p['outcome'])
    end = now if state == 'running' else max([p['last'], *map(float, etas)])   # every ETA is recorded while it runs
    levels = enumerate_levels(final, budgets, order, cache, DEEPEST)
    tree = reading.tree(budgets, cache)
    rows = tree.rows(levels, bottom)
    for r in rows: r['modulus'] = ([None] + list(v5.CASCADE))[r['depth']]
    stats = {k: status(k, final, budgets) for k in levels[-1]}
    tally = tree.tally()
    last = (p['nodes'] or [{'t': None, 'waiting': None, 'running': None}])[-1]
    opens = tree.open_list()
    spans = [(q['start'], q['last']) for q in passes[:-1]] + [(p['start'], end)]
    view = reading.estimating(order, cache, end, f'{n}@{order} at {clock(end)}') if state != 'ended' else None
    draws = estimate(view.state, view=view) if view is not None else None
    etas.setdefault(str(int(end)), [float(np.median(draws))] + [float(q) for q in np.quantile(draws, QUANTILES)] if draws is not None and len(draws) else None)   # a record made stands
    region, stack = (view.region, view.stack) if view is not None else ([], [])
    moving = [nd for nd in region if nd.state == 'running']      # in tree order
    running = {nd.key for nd in moving if nd.key is not None}
    unnamed = ([(nd.parent.key, 'running') for nd in moving if nd.key is None]
               + [(nd.parent.key, 'pending') for nd in stack if nd.key is None])
    assert all(k is not None for k, _ in unnamed), unnamed      # a node's parent is done, so its line named it
    to_go = ({'median': float(np.median(draws)) * HOUR} | dict(zip(('lo', 'hi'), (float(q) * HOUR for q in np.quantile(draws, QUANTILES))))
             if draws is not None and len(draws) else None)
    tree = reading.tree(budgets, cache)                         # with the splits cached since by the levels and resplits
    return {'program': 'overnight_v5.py', 'n': n, 'order': order, 'state': state, 'outcome': p['outcome'], 'budgets': budgets,
            'sea': tree.sea_of(running, unnamed), 'so_far': sum(b - a for a, b in spans), 'to_go': to_go,
            'passes': spans,
            'elapsed': end - p['start'], 'last': p['last'],
            'settled': tree.infeasible, 'open': tally['open'],
            'split': tally['split'], 'line': last['t'], 'waiting': last['waiting'], 'running': last['running'],
            'levels': rows, 'deepest': len(levels) - 1,
            'processes': p['processes'],
            'work': work_of(levels[-1], stats, reading.touched(len(levels) - 1)) if state != 'ended' else None,
            'draws': draws, 'etas': etas, 'open_list': opens}


# ---------- a run's boxsplit pass (boxsplit.py over its open leaves; dreeves, 2026-10-17) ----------

def box_files(n, order):
    """The driver's log of the run (n, order) and the run's journal, named as boxsplit.configure names them, in the run's
    directory (files: a run made by a copy of overnight_v5.py has its copy of boxsplit.py next to it)."""
    journal, _ = files(n, order)
    return os.path.join(os.path.dirname(journal), f'overnight_v5_{n}_{order}_boxsplit.log'), journal


def said(head, tail):
    """The pattern of the rest of a driver's log line after its stamp and any node, a message of boxsplit's: whose first
    letter is head (in lower case; '' for none that changes), the rest tail.  Written two ways, matched alike: in
    Claude's quotes, its first letter in lower case, as before 2026-10-29 (scratch/x288's copy of boxsplit.py, and
    the logs before, still write it so), and since then plain, the letter in upper case (dreeves's a6481ff, "Remove some
    TODOs").  The quote opening it, q, decides the letter's case and the closing quote."""
    return rf'(?P<q>Claude: ")?(?(q){head}|{head.upper()}){tail}(?(q)")$'


BOX_FORMS = {                          # the driver's log line forms, as boxsplit's run, drive and say_* write them
    'start': re.compile(STAMP + said('s', r'tart: n = (?P<n>\d+), order at least (?P<order>\d+), open leaves (?P<leaves>\d+) '
                                          r'of .+ \((?P<on_record>\d+) closed on record\), extension moduli \[[\d, ]+\] with '
                                          r'budgets \[[\d, ]+\] \(LP solves; a pool or an outside node \d+ per member\), '
                                          r'(?P<processes>\d+) processes, HiGHS .+, \d+ earlier verdicts')),
    'control': re.compile(STAMP + said('s', r'tartup control passed: .*')),
    'leaf': re.compile(STAMP + said('l', r'eaf (?P<leaf>\d+): \{.*\}')),
    'split': re.compile(STAMP + r'\{.*\} by \d+: ' + said('b', r'ox widths .*')),
    'outside': re.compile(STAMP + r'\{.*\} by \d+: ' + said('', r'\d+ outside nodes INFEASIBLE .*')),
    'piece': re.compile(STAMP + r'\{.*\}: (?:INFEASIBLE|UNKNOWN); ' + said('', r'\d+ LP solves \(\d+\.\d s\)')),
    'open': re.compile(STAMP + said('o', r'pen: \{.*\}')),
    'done': re.compile(STAMP + said('l', r'eaf (?P<leaf>\d+) \{.*\}: extension tree (?P<tree>closed|not closed)[:,] .*')),
    'outcome': re.compile(STAMP + '(?P<outcome>' + said('', r'(?:ALL \d+ LEAVES CLOSED \(|NOT FINISHED: |WITNESS FOUND in ).*') + ')'),
}


class BoxLog:
    """parse_box_lines kept line by line: a driver's log's passes, each line taken whole or not at all, and the leaves
    each line starts or ends (events), in order."""

    def __init__(self):
        self.passes, self.events, self.stamped = [], [], -math.inf

    def take(self, line):
        """Parse the next line into the passes, or fail (asserted) leaving everything as it was."""
        forms = [(kind, m) for kind, form in BOX_FORMS.items() if (m := form.match(line))]
        # TODO: error copy; says a line of the driver's log has none of the forms progress.py knows, quoting the line
        assert len(forms) == 1, f'Claude: "a boxsplit log line of no known form: {line}"'
        kind, m = forms[0]
        # TODO: error copy; says a line of the driver's log comes before any start line or after its pass's outcome line, quoting it
        assert kind == 'start' or (self.passes and self.passes[-1]['outcome'] is None), f'Claude: "a boxsplit log line out of place: {line}"'
        assert kind != 'done' or int(m['leaf']) in self.passes[-1]['starts'], line
        assert kind != 'leaf' or int(m['leaf']) not in self.passes[-1]['starts'], line     # a leaf starts once a pass,
        assert kind != 'done' or int(m['leaf']) not in self.passes[-1]['dones'], line      # and is done once
        t = stamp_after(m[1], self.stamped)
        if kind == 'start':
            self.passes.append({'start': t, 'n': int(m['n']), 'order': int(m['order']), 'leaves': int(m['leaves']),
                                'on_record': int(m['on_record']), 'processes': int(m['processes']), 'starts': {},
                                'dones': {}, 'outcome': None})
        p = self.passes[-1]
        p['last'] = self.stamped = t
        if kind == 'leaf': p['starts'][int(m['leaf'])] = t
        if kind == 'done': p['dones'][int(m['leaf'])] = (t, m['tree'] == 'closed')
        if kind == 'outcome': p['outcome'] = m['outcome']
        if kind in ('start', 'leaf', 'done'): self.events.append((kind, int(m['leaf']) if kind != 'start' else None, p))


def parse_box_lines(lines):
    """The passes of a driver's log whose complete lines these are, in order, each a dict: start and last, the times of
    its start line and its last line; n, order, leaves (the run's open leaves), on_record (those the driver's journal
    held closed) and processes, from its start line; starts, the time each leaf (by its index into the open leaves)
    started; dones, (the time, whether its tree closed) of each leaf done; outcome, its final line (ALL ... LEAVES
    CLOSED, NOT FINISHED or a witness), as the log has it, after the time, else None.  Every line must have exactly
    one known form, every pass must begin with a start line, no line may follow its outcome but the next start line,
    and a leaf is done only after it started in the pass, and starts and is done at most once in it (all asserted).  The
    times are each line's stamp_after the line before."""
    log = BoxLog()
    for line in lines: log.take(line)
    return log.passes


def driver_leaves(main):
    """The leaves boxsplit.py's driver works for the run whose journal is main, as nodes, in the driver's order: the
    run's open leaves (boxsplit.open_leaves': the keys at the cascade's bottom, one vector per modulus, whose latest
    verdict is UNKNOWN) and those a handoff has closed since (CLOSED there, which overnight_v5 never writes at the
    bottom: its CLOSED records are for nodes with children), in the order of their latest records, which a handoff
    keeps (scratch/boxsplit-240/handoff.py appends them in the open leaves' order).  dreeves, 2026-10-20: 240@11's
    handoff closed its 606 leaves, and the watcher, taking the open ones alone, found none for the driver's log."""
    with open(main, encoding='utf-8') as fh:
        run_modules.validate_header(v5, json.loads(fh.readline()))
    journal = v5.Journal(main)
    latest = {json.loads(line)['key']: i for i, line in enumerate(open(main).read().splitlines()[1:])}
    keys = [k for k, rec in journal.records.items()
            if rec['verdict'] in ('UNKNOWN', 'CLOSED') and len(k.split()) == len(v5.CASCADE) and '#' not in k]
    return [bx.parse_key(k) for k in sorted(keys, key=latest.get)]


def lindy_draws(walls, ages, pending):
    """The urn estimate's draws (dreeves, 2026-10-19, boxsplit's leaves; 2026-10-23, every search's jobs), in walls'
    units: an urn (see the vocabulary) of walls, the jobs done, its new ball lindy_ball's Lindy tail above the longest
    seen, done or running; REPLICATES draws of each running job's rest above its age (ages, the longest-running first)
    and of each of the pending jobs' size.  With no job done, every draw is the new ball: Gott's rule, so that the
    estimate grows in proportion to the age until a job is done."""
    assert ages == sorted(ages, reverse=True) and pending >= 0
    top = max([*walls, *ages], default=0.0)                          # the longest seen
    assert top > 0
    rng = np.random.default_rng(SEED)
    urn = Urn(rng, np.array(walls, dtype=float), lindy_ball(rng, top), len(ages) + pending)
    return [urn.draw(e) - e for e in ages], [urn.draw() for _ in range(pending)]


def quantiles(hours):
    """REPLICATES draws of hours as a recorded ETA: [median, lo, hi] (QUANTILES)."""
    return [float(np.median(hours))] + [float(q) for q in np.quantile(hours, QUANTILES)]


def lindy_urn(walls, ages, pending, workers):
    """The [median, lo, hi] hours to go of a batch of jobs on its workers (walls and ages in seconds): each running job
    holding its worker for its rest, each pending one a job for makespan."""
    assert len(ages) <= workers
    rests, sizes = lindy_draws(walls, ages, pending)
    loads = np.zeros((REPLICATES, workers))
    for j, rest in enumerate(rests):
        loads[:, j] = rest
    return quantiles(makespan(loads, [('job', size) for size in sizes]) / HOUR)


def lindy_work(walls, ages, pending, rate):
    """The [median, lo, hi] hours to go of work shared by a pool (fanout.py's cases, 2026-10-23): walls and ages in any
    unit of work, the pool doing rate of it a second; the rests and sizes summed, as the pool works on every job at once."""
    rests, sizes = lindy_draws(walls, ages, pending)
    return quantiles(sum(rests + sizes) / rate / HOUR)


BAND = 4                               # depth levels in a band of the pool estimate's samples (see the vocabulary)
BOOT = 200                             # its bootstrap replicates, and those of the boxsplit estimate (box_estimate)


def pool_estimate(samples, pool, n, rate, floor):
    """The pool estimate (see the vocabulary) as [median, lo, hi] hours to go: samples [(depth, LP solves, open boxes'
    depths)], pool {depth: boxes}, n the deepest a box can be, rate the pool's LP solves a second, floor the LP solves
    every draw is at least."""
    assert samples and pool and max(pool) <= n and rate > 0
    rng = np.random.default_rng(SEED)
    bands = sorted({d // BAND for d, _, _ in samples})
    near = [min(bands, key=lambda b: (abs(b - d // BAND), -b)) for d in range(n + 1)]   # the deeper on a tie
    width = 1 + max([o - d for d, _, opened in samples for o in opened], default=0)
    means = {}                          # each band's BOOT replicates of its mean LP solves and open boxes per depth below
    for b in bands:
        own = [(d, c, opened) for d, c, opened in samples if d // BAND == b]
        below = np.zeros((len(own), width))
        for i, (d, _, opened) in enumerate(own):
            np.add.at(below[i], [o - d for o in opened], 1)
        weights = rng.multinomial(len(own), np.full(len(own), 1 / len(own)), size=BOOT) / len(own)
        means[b] = (weights @ np.array([c for _, c, _ in own], dtype=float), weights @ below)
    T = np.zeros((BOOT, n + 1 + width))                 # T[:, d]: E[T(d)] in each replicate; 0 past n
    for d in range(n, -1, -1):
        cost, below = means[near[d]]
        T[:, d] = cost + (below * T[:, d:d + width]).sum(axis=1)
    total = sum(count * T[:, d] for d, count in pool.items())
    return quantiles(np.maximum(total, floor) / rate / HOUR)


def box_work(u, d, c, at, pending):
    """The worker seconds a boxsplit pass has to go by Kaplan-Meier (1958) on its started leaves (see survey_box), and
    whether its mean is restricted: u, the distinct seconds seen, ascending; d and c, how many done leaves (events) and
    running ones (censored at their seconds so far) were seen at each; at, each running leaf's place in u; pending, the
    leaves to start.  The survival S steps down at each u by the done leaves there over those at risk, seen there or
    later (a done leaf before a running one at the same seconds).  tau is the longest time seen; the mean is the area
    under S up to it, and each running leaf seen at t has its area past t over S(t) to go.  Past tau nothing is known:
    where it is a running leaf's, S(tau) > 0 and the area stops at tau all the same, a floor (restricted; Efron's 1967
    tail, tau taken as an event).  The worker seconds are pending times the mean plus the running leaves' rests."""
    seen = d + c
    S = np.cumprod(1 - d / np.maximum(np.cumsum(seen[::-1])[::-1], 1))
    tau = np.flatnonzero(seen)[-1]
    area = np.cumsum(np.r_[1.0, S[:-1]] * np.diff(np.minimum(np.r_[0.0, u], u[tau])))      # under S to each u (and tau)
    rest = area[-1] - area[at]
    return pending * area[-1] + np.divide(rest, S[at], out=np.zeros(len(at)), where=rest > 0).sum(), bool(S[tau] > 0)


def box_estimate(walls, ages, pending, workers):
    """A boxsplit pass's estimate (see survey_box): ([median, lo, hi] hours to go, whether restricted), box_work of its
    started leaves (walls, the seconds of the done ones; ages, those so far of the running ones) over its workers, the
    median and QUANTILES of BOOT bootstrap replicates, the started leaves drawn again with replacement (as counts over
    the distinct (seconds, done or running) cells: memory and time by those cells); restricted, the started leaves'
    own (box_work)."""
    # TODO: error copy; says a boxsplit estimate needs a started leaf, ages and pending not below 0, and a worker
    assert walls + ages and min(ages, default=0) >= 0 <= pending and workers > 0, 'Claude: "no estimate of these"'
    u, place = np.unique(np.array(walls + ages, dtype=float), return_inverse=True)
    d = np.bincount(place[:len(walls)], minlength=len(u)).astype(float)
    c = np.bincount(place[len(walls):], minlength=len(u)).astype(float)
    at, n = place[len(walls):], len(place)
    rng = np.random.default_rng(SEED)
    hours = [box_work(u, *np.split(rng.multinomial(n, np.r_[d, c] / n).astype(float), 2), at, pending)[0]
             for _ in range(BOOT)]
    return quantiles(np.array(hours) / workers / HOUR), box_work(u, d, c, at, pending)[1]


def to_go_of(eta):
    """A recorded ETA ([median, lo, hi] hours, or None) as the data file's to_go ({median, lo, hi} seconds, or None)."""
    return None if eta is None else dict(zip(('median', 'lo', 'hi'), (h * HOUR for h in eta)))


PROBE = {'event', 'time', 'pid', 'case', 'paths', 'mean', 'se', 'least', 'witnesses'}   # a probe record's fields


def depths_fit(r):
    """Whether a probe record's depths (fanout.py's since 2026-10-26) are an int from 0 up for each of its paths, whose
    mean and standard error, computed as fanout.probe computes them, are the record's."""
    d = r['depths']
    shaped = type(d) is list and len(d) == r['paths'] and all(type(x) is int and x >= 0 for x in d)
    return shaped and r['mean'] == sum(d) / len(d) and r['se'] == math.sqrt(
        sum((x - sum(d) / len(d)) ** 2 for x in d) / (len(d) - 1) / len(d))


def probe_least(r, cases, n):
    """A probe record's least (see the vocabulary), its fields checked: its case one of cases, at least 2 paths, its
    leaf depths' mean and standard error finite and not negative, least as fanout.least makes it from them, and each
    witness a 0/1 list of length n; and since 2026-10-26 its depths, if it has them (fanout.py's probes record each
    path's), one int from 0 up for each path, whose mean and standard error, computed as fanout.probe computes them, are
    the record's."""
    assert set(r) in (PROBE, PROBE | {'depths'}), r
    assert type(r['case']) is int and r['case'] in cases, r
    assert type(r['paths']) is int and r['paths'] >= 2, r
    assert all(type(r[k]) in (int, float) and 0 <= r[k] < np.inf for k in ('mean', 'se')), r
    assert type(r['least']) is int and r['least'] == fanout.least(r['mean'], r['se']), r
    assert type(r['witnesses']) is list, r
    assert all(type(x) is list and len(x) == n and all(type(t) is int and t in (0, 1) for t in x)
               for x in r['witnesses']), r
    assert 'depths' not in r or depths_fit(r), r
    return r['least']


def censored(jobs):
    """Open jobs, each (its work so far, its least), as their censoring points (see least in the vocabulary), the
    largest first, and the work certain to come below those points, summed."""
    return sorted((max(a, l) for a, l in jobs), reverse=True), sum(max(a, l) - a for a, l in jobs)


def survey_box(n, order, log, main, procs, now, etas, box=None):
    """The boxsplit pass of the run (n, order) as the driver's log, the run's journal (main, whose open leaves the
    driver works), the process list and the time now show it, in survey's shape: program boxsplit.py, its state, its
    seconds of running (its passes'), its estimate (to_go; see below) and record of ETAs (etas, to which this snapshot's
    goes, as survey's), and its sea: one dot per open leaf, grouped and ordered as survey's sea, running if it started
    in the current pass of a running driver and is not done in it, else settled or open as its latest line saying it is
    done says its tree closed or not, else pending.  The log alone says all this, every pass's lines kept; the driver's
    journal is not read: the driver writes a leaf's done line and then its CLOSED record, so a reader of both could see
    the one without the other (the watcher's crash of 2026-10-17 16:03).
    The estimate (2026-10-30, in place of an urn of Lindy draws, whose balls for 288@10's 431,256 leaves would have
    held 6.9 GB): Kaplan-Meier (1958) on the current pass's started leaves (an earlier pass did other work: 240@11's
    second split by 19 the nodes its first left open by 17), box_estimate.  The driver starts leaves in the order of
    their keys' sha1, an order that knows nothing of their cost, so the started ones are a random sample of the pass's
    leaves: each done leaf an event at its wall seconds, start line to the line saying it is done, each running one
    censored at its seconds so far.  The worker seconds to go are the pending leaves (the pass's leaves less those
    closed on record and those started) times the mean, plus each running leaf's expected rest beyond its seconds so
    far, over the pass's workers; the median and band of BOOT bootstrap replicates of the started leaves.  The band is
    the mean's uncertainty, not that of the sum of the pending leaves' seconds, which varies less over many leaves
    (nor of the end of a pass with fewer leaves left than workers, which the division by the workers puts early).
    Where the longest time seen is a running leaf's, nothing is known past it: the mean is restricted to it, a floor
    (restricted).  None when the driver is not running or no leaf of the pass has begun.  box is the watcher's Boxes of
    the pass, kept between snapshots; by default a new one, which reads the files whole: the same survey."""
    files(n, order)                     # overnight_v5 configured for the run, with its copy's settings if it has one
    box = Boxes(log) if box is None else box
    # TODO: error copy; says the watcher's reading of a boxsplit pass was handed another driver's log, naming both
    assert box.log == log, f'Claude: "a reading of {box.log} given {log}"'
    leaves, passes = box.advance(main)
    p = passes[-1]
    # TODO: error copy; says the driver's log's last start line names another length, order or count of open leaves than the run's journal
    assert (p['n'], p['order'], p['leaves']) == (n, order, len(leaves)), f'Claude: "the boxsplit log of {n} {order} does not match its run"'
    state = run_state(procs, 'boxsplit.py', n, order, p['outcome'])
    end = now if state == 'running' else max([p['last'], *map(float, etas)])   # every ETA is recorded while it runs
    spans = [(q['start'], q['last']) for q in passes[:-1]] + [(p['start'], end)]
    running = {i: p['starts'][i] for i in box.active} if state == 'running' else {}
    sea = box.sea(running)
    assert len(box.walls) + len(box.active) == len(p['starts']), log  # each leaf started in the pass done or at work
    walls = box.walls                                                # the pass's done leaves' wall seconds
    ages = sorted(now - t for t in running.values())                 # its running leaves' seconds so far
    pending = p['leaves'] - p['on_record'] - len(p['starts'])        # its leaves the driver has yet to start
    assert pending >= 0, log
    eta, restricted = (box_estimate(walls, ages, pending, p['processes']) if state == 'running' and walls + ages
                       else (None, None))
    etas.setdefault(str(int(end)), eta)   # a record made stands
    to_go = to_go_of(eta)
    return {'program': 'boxsplit.py', 'n': n, 'order': order, 'state': state, 'outcome': p['outcome'],
            'so_far': sum(b - a for a, b in spans), 'to_go': to_go, 'restricted': restricted, 'passes': spans,
            'etas': etas, 'sea': sea}


class Boxes:
    """survey_box's reading of a run's boxsplit pass, kept by the watcher between snapshots: the driver's log parsed as it
    grows (Tail, BoxLog); the run's leaves (driver_leaves, as keys), made again only when the run's journal is another
    file or changed (its device, inode, size or modification time), with each leaf's place in tree order and each sea
    group's span of places; each leaf's latest done verdict; the current pass's leaves started and not done (active)
    and its done leaves' wall seconds (walls); and each leaf's dot (see survey_box), by place (codes)."""

    def __init__(self, log):
        self.log, self.tail, self.parsed, self.lines = log, Tail(log), BoxLog(), collections.deque()
        self.sig, self.leaves, self.rank, self.spans, self.codes = None, [], {}, [], bytearray()
        self.done, self.active, self.walls = {}, set(), []
        self.used, self.moved, self.shown = 0, set(), set()   # events taken; leaves moved since drawn; drawn running

    def advance(self, main):
        """Take what the driver's log gained and the run's leaves, each step atomic: (the leaves, the passes)."""
        with atomic(): self.lines += self.tail.read()
        while self.lines:
            with atomic():
                for _ in range(min(STEP, len(self.lines))):
                    self.parsed.take(self.lines[0])
                    self.lines.popleft()
        st = os.stat(main)
        sig = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        if sig != self.sig:                                         # the run's journal is another or changed
            saved = v5.JOURNAL
            v5.JOURNAL = main
            try:
                leaves = [v5.node_key(nd) for nd in driver_leaves(main)]
            finally:
                v5.JOURNAL = saved
            places = sorted(range(len(leaves)), key=lambda i: tree_order(leaves[i]))
            spans, place = [], 0                                    # a group's leaves are consecutive in tree order
            for g, run in itertools.groupby(places, key=lambda i: ' '.join(leaves[i].split()[:SEA_DEPTH])):
                size = sum(1 for _ in run)
                spans.append((g, place, place + size))
                place += size
            with atomic():
                self.sig, self.leaves, self.spans = sig, leaves, spans
                self.rank = {i: place for place, i in enumerate(places)}
                self.codes, self.moved = bytearray(len(leaves)), set(range(len(leaves)))
        with atomic():
            for kind, i, p in self.parsed.events[self.used:]:
                if kind == 'start': self.active, self.walls = set(), []    # a pass begins
                if kind == 'leaf': self.active.add(i)
                if kind == 'done':
                    self.active.discard(i)
                    t, self.done[i] = p['dones'][i]
                    self.walls.append(t - p['starts'][i])
                self.moved.add(i)
            self.used = len(self.parsed.events)
        return self.leaves, self.parsed.passes

    def sea(self, running):
        """survey_box's sea: the dots of the leaves moved since drawn, or running now or then, drawn again (atomic)."""
        with atomic():
            for i in [i for i in self.moved | self.shown | set(running) if i in self.rank]:
                s = 'running' if i in running else ('settled' if self.done[i] else 'open') if i in self.done else 'pending'
                self.codes[self.rank[i]] = ord(str(SEA_STATUSES.index(s)))
            self.moved, self.shown = set(), set(running)
        return {'depth': SEA_DEPTH, 'keys': [g for g, _, _ in self.spans],
                'groups': [self.codes[a:b].decode() for _, a, b in self.spans],
                'counts': {s: self.codes.count(str(i).encode()) for i, s in enumerate(SEA_STATUSES)}}


# ---------- files and the command line ----------

def write_atomic(path, text):
    """Write text to path through a temporary file next to it, renamed over path: a reader opens the old file or the
    new one, whole, never part of one."""
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


# ---------- the symmetric lattice witness run ----------

def lattice_estimate(durations, total, done, age, cap, phase, outcome):
    """Seconds to finish the planned batch, using only completed, wall-time-capped attempts. The point estimate
    extrapolates their cumulative mean; the existing chart schema calls that field 'median', but it is not a
    posterior median. The band is a scenario range: zero through every remaining attempt taking the greater of
    the configured cap and the longest observed duration. It is neither a confidence interval nor a hard bound:
    the search order can change the duration distribution, and pauses or overhead can exceed the cap scenario.
    Two completions are required before extrapolating. A running attempt uses the mean remaining duration among
    observations longer than its current age; beyond all observations, the cap scenario supplies its remainder.
    A failed/stopped batch still has work left. A witness or exhaustion finishes this batch, not a general proof."""
    if outcome in ('witness', 'exhausted'): return dict(median=0, lo=0, hi=0)
    if len(durations) < 2 or (phase != 'search' and outcome != 'failed'): return None
    bound = max(cap, *durations)
    left = total - done - int(age is not None)
    assert left >= 0 and all(d >= 0 for d in durations), (left, durations)
    remainder = ceiling = 0
    if age is not None:
        assert age >= 0, age
        longer = [d - age for d in durations if d > age]
        ceiling = max(0, bound - age)
        remainder = sum(longer) / len(longer) if longer else ceiling
    return dict(median=left * sum(durations) / len(durations) + remainder, lo=0, hi=left * bound + ceiling)


def survey_lattice(path, procs, now=None, etas=None):
    """Read lattice288.py's version-1 event journal. Completed attempts stay open: pruning or a timeout proves
    no exclusion. An interrupted attempt becomes pending on restart. Sessions separate launches, so time between
    launches is excluded; a stopped or vanished process is timed through its last event or observed running
    snapshot. The caller's etas dict records actual snapshots only, never reconstructed estimates. The journal's
    first header is installed atomically by its writer."""
    records = list(map(json.loads, complete_lines(path)))
    now = time.time() if now is None else now
    etas = {} if etas is None else etas
    assert records, path
    header = records[0]
    assert (header['event'], header['version'], header['n'], header['order'], header['total']) == \
           ('header', 1, 288, 10, 2736), header
    assert header['seconds'] > 0 and header['time'] <= now, header
    state = dict(pid=None, phase='preparation', outcome=None, started=None)
    spans, done, active, durations = [], set(), set(), []

    def session(r):
        active.clear()
        state.update(pid=r['pid'], phase='preparation', outcome=None, started=None)
        spans.append([r['time'], r['time']])

    def phase(r):
        assert r['phase'] in ('preparation', 'calibration', 'search'), r
        state['phase'] = r['phase']

    def case_start(r):
        assert state['phase'] == 'search' and not active, r
        assert type(r['case']) is int and 0 <= r['case'] < header['total'] and r['case'] not in done, r
        assert len(r['profile']) == 7 and len(r['pair']) == 2, r
        active.add(r['case'])
        state['started'] = r['time']

    def case_end(r):
        assert active == {r['case']} and r['outcome'] in ('timeout', 'empty', 'witness') and r['elapsed'] >= 0, r
        active.clear()
        done.add(r['case'])
        durations.append(r['elapsed'])

    def finish(r):
        assert r['outcome'] in ('exhausted', 'witness', 'failed'), r
        state['outcome'] = r['outcome']
        active.clear()

    handlers = dict(session=session, phase=phase, case_start=case_start, case_end=case_end, finish=finish)
    previous = header['time']
    for r in records[1:]:
        assert r['event'] in handlers and previous <= r['time'] <= now and type(r['pid']) is int, r
        assert r['event'] == 'session' or (spans and r['pid'] == state['pid'] and state['outcome'] is None), r
        handlers[r['event']](r)
        spans[-1][1] = previous = r['time']
    assert spans, path
    main = [p for p in runs(procs, 'lattice288.py') if p[0] == state['pid']]
    assert len(main) <= 1, main
    status = ('ended' if state['outcome'] is not None or not main else
              'frozen' if main[0][2].startswith('T') else 'running')
    observed = list(map(float, etas))
    assert all(spans[0][0] <= t <= now for t in observed), observed
    for span, stop in zip(spans, [a for a, _ in spans[1:]] + [now + 1]):
        span[1] = max([span[1]] + [t for t in observed if span[0] <= t < stop])
    spans[-1][1] = now if status == 'running' else spans[-1][1]
    running = active if status == 'running' else set()
    codes = ''.join(str(SEA_STATUSES.index('open' if i in done else 'running' if i in running else 'pending'))
                    for i in range(header['total']))
    counts = {name: codes.count(str(i)) for i, name in enumerate(SEA_STATUSES)}
    end = spans[-1][1]
    age = end - state['started'] if active and status != 'ended' else None
    to_go = lattice_estimate(durations, header['total'], len(done), age, header['seconds'], state['phase'], state['outcome'])
    if status == 'running':
        etas.setdefault(str(float(end)), [to_go[k] / HOUR for k in ('median', 'lo', 'hi')] if to_go is not None else None)
    return dict(program='lattice288.py', n=288, order=10, made=now, outcome=state['outcome'],
                display=dict(scope='symmetric-witness', phase=state['phase'], outcome=state['outcome']),
                state=status, so_far=sum(b - a for a, b in spans), to_go=to_go,
                passes=spans, etas=etas, sea=dict(depth=0, keys=['288:10'], groups=[codes], counts=counts))


# ---------- the data file ----------

def sight(main, launches, now):
    """Records the sighting of a run's live process, main (at most one), in launches: [first, last] by pid."""
    for p in main: launches.setdefault(str(p[0]), [now, now])[1] = now
    assert all(len(v) == 2 and v[0] <= v[1] <= now for v in launches.values()), launches


def started_at(r, launches):
    """A journal record's time, but a session's: its process's first sighting, if that came before the record."""
    return min(r['time'], launches.get(str(r['pid']), [r['time']])[0]) if r['event'] == 'session' else r['time']


def spans_of(spans, pids, main, launches, observations, now, decided):
    """A run's spans of running and state, from its sessions' spans and pids (in journal order), its live process main,
    the sightings, the recorded observations and whether its journal says it is decided (survey_focus's docstring):
    each pid's latest session runs to its last sighting, a sighted pid never journaled is a span of its own, the spans
    are in order and disjoint (asserted), each runs on to the observations within it, and the last to now while
    running."""
    for pid, i in {pid: i for i, pid in enumerate(pids)}.items():      # each pid's latest session
        spans[i][1] = max(spans[i][1], launches.get(pid, spans[i])[1])
    spans += [list(v) for pid, v in launches.items() if pid not in pids]   # seen, never journaled
    spans.sort()
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), spans
    live = bool(main) and (str(main[0][0]) not in pids or not decided)
    status = 'ended' if not live else 'frozen' if main[0][2].startswith('T') else 'running'
    observed = list(map(float, observations))
    assert all(spans[0][0] <= t <= now for t in observed)
    for span, stop in zip(spans, [a for a, _ in spans[1:]] + [now + 1]):
        span[1] = max([span[1]] + [t for t in observed if span[0] <= t < stop])
    spans[-1][1] = now if status == 'running' else spans[-1][1]
    return spans, status


def focus_pauses(records, now, n):
    """Recorded STOP/CONT intervals; the guardian keeps each process's pid, start time and exact command."""
    for i, r in enumerate(records):
        assert set(r) == {'event', 'time', 'pid', 'start', 'command'}, r
        assert r['event'] == ('pause', 'resume')[i % 2], r
        assert type(r['time']) in (int, float) and 0 <= r['time'] <= now, r
        assert type(r['pid']) is int and r['pid'] > 0, r
        assert type(r['start']) is str and r['start'], r
        assert type(r['command']) is str and runs([(r['pid'], 1, 'T', r['command'])], 'focus.py', n), r
    assert all(a['time'] <= b['time'] for a, b in zip(records, records[1:])), records
    assert all(all(a[k] == b[k] for k in ('pid', 'start', 'command'))
               for a, b in zip(records[::2], records[1::2])), records
    return [(a['time'], b) for a, b in zip(records[::2], [r['time'] for r in records[1::2]] + [now])]


def without_pauses(spans, pauses):
    """Subtract recorded pauses, retaining zero-length endpoints for observations sampled during a signal race."""
    for c, d in pauses:
        start, end = spans[0][0], spans[-1][1]
        spans = [[start, start]] + [[x, y] for a, b in spans for x, y in ((a, min(b, c)), (max(a, d), b))
                                    if x < y] + [[end, end]]
    return spans


def survey_focus(path, procs, now=None, observations=None, launches=None, pauses=(), journal=None):
    """Focused proof journals: root-case coverage, and while running an ETA, lindy_urn's on the root cases (one
    worker), recorded in observations (dreeves, 2026-10-23: with no root done, Lindy).

    A budget stop leaves cases open. Only a completed proof settles a root.
    Observation timestamps retain elapsed time if a process disappears.
    The run's process is the one focus.py process for its n.  launches holds each such process's first and last
    sightings, [first, last] by pid: it runs from the first to the last (dreeves, 2026-10-23: "always be clear about
    what's been running for how long"), though it writes its session record only after replaying its certificates
    (an hour and more at 4 GB), and whether or not it lives to write it.  A session runs from its process's first
    sighting, if that came before its record, to the later of its last record and its process's last sighting (the
    latest session of that pid's).  A root case runs from the record before the first naming it to the record
    completing it (or the record before that, if never named), its age the running time between, gaps between
    launches excluded.  The running root is drawn above its latest probe's least (see the vocabulary), turned into
    seconds at the run's seconds of running per LP solve so far: a probe with no LP solve on record fails (asserted).
    journal is the watcher's Records of the path, kept between snapshots; by default a new one, which reads it whole.
    """
    records = (Records(path) if journal is None else journal).read()
    now = time.time() if now is None else now
    observations = {} if observations is None else observations
    launches = {} if launches is None else launches
    header = records[0]
    assert (header['event'], header['version']) == ('header', 1)
    assert (header['n'], header['order']) in ((432, 12), (480, 14), (672, 13))
    assert type(header['total']) is int and header['total'] > 0
    total = header['total']
    main = runs(procs, 'focus.py', header['n'])
    assert len(main) <= 1
    sight(main, launches, now)
    state = dict(pid=None, outcome=None, time=header['time'])
    spans, pids = [], []                # the sessions' spans and pids, in journal order
    snap = dict(lp=0, closed=0, split=0, pending=total, case=None, completed=[])
    begun, ended = {}, {}               # each root case's start and completion times (see the docstring)
    leasts = {}                         # each probed root case's latest least, LP solves

    def session(r, t):
        state.update(pid=r['pid'], outcome=None)
        spans.append([t, t])
        pids.append(str(r['pid']))

    def probe(r, t):
        assert spans and r['pid'] == state['pid'] and state['outcome'] is None, r
        leasts[r['case']] = probe_least(r, range(total), header['n'])

    def update(r, t):
        assert spans and r['pid'] == state['pid'] and state['outcome'] is None
        assert all(type(r[k]) is int and r[k] >= snap[k] for k in ('lp', 'closed', 'split'))
        assert type(r['pending']) is int and r['pending'] >= 0
        assert len(r['completed']) == len(set(r['completed']))
        assert set(snap['completed']) <= set(r['completed']) <= set(range(total))
        assert r['case'] is None or (type(r['case']) is int and
                                    0 <= r['case'] < total and r['case'] not in r['completed'])
        outcome = r.get('outcome')
        assert (r['event'] == 'finish') == (outcome in ('excluded', 'witness', 'budget'))
        assert outcome != 'excluded' or (len(r['completed']) == total and r['pending'] == 0)
        for c in [r['case'], *r['completed']]: begun.setdefault(c, state['time'])   # a root can begin and end between
        for c in r['completed']: ended.setdefault(c, r['time'])                     # two records, never named running
        snap.update({k: r[k] for k in snap})
        state['outcome'] = outcome

    handlers = dict(session=session, update=update, finish=update, probe=probe)
    for r in records[1:]:
        assert r['event'] in handlers and type(r['pid']) is int
        t = started_at(r, launches)
        assert state['time'] <= t <= r['time'] <= now
        handlers[r['event']](r, t)
        spans[-1][1] = r['time']
        state['time'] = t
    assert spans
    spans, status = spans_of(spans, pids, main, launches, observations, now, state['outcome'] is not None)
    spans = without_pauses(spans, focus_pauses(pauses, now, header['n']))
    status = 'paused' if status == 'frozen' else status
    def running(t): return sum(max(0.0, min(t, b) - a) for a, b in spans)   # seconds of running before t
    active = snap['case'] if status == 'running' else None
    assert set(snap['completed']) <= set(begun) & set(ended)
    walls = [running(ended[c]) - running(begun[c]) for c in snap['completed']]
    ages = [] if active is None else [running(now) - running(begun[active])]
    def as_seconds(lps):                # LP solves as seconds of running, at the run's own rate so far
        assert snap['lp'] > 0, snap
        return lps * running(now) / snap['lp']
    least = {c: -np.inf for c in range(total)} | {c: as_seconds(lps) for c, lps in leasts.items()}
    points, certain = censored([(a, least[active]) for a in ages])
    eta = ([h + certain / HOUR for h in lindy_urn(walls, points, total - len(walls) - len(ages), 1)]
           if status == 'running' and max([*walls, *ages], default=0.0) > 0 else None)
    if status == 'running':
        observations[str(float(now))] = eta
    codes = ''.join('0' if i in snap['completed'] else '4' if i == active else
                    '1' if status == 'ended' else '3' for i in range(total))
    counts = {name: codes.count(str(i)) for i, name in enumerate(SEA_STATUSES)}
    return dict(program='focus.py', n=header['n'], order=header['order'], made=now,
                state=status, outcome=state['outcome'], so_far=sum(b - a for a, b in spans), to_go=to_go_of(eta),
                etas=observations, passes=spans,
                sea=dict(depth=0, keys=[f'{header["n"]}:{header["order"]}'], groups=[codes], counts=counts))


def survey_fanout(path, procs, now=None, observations=None, launches=None, journal=None):
    """fanout.py's journal (see fanout.py's vocabulary): its spans of running as survey_focus's; a dot per job, grouped
    by root (keyed case:depth): split (done, leaving boxes open), settled (done, none open), running, then pending (a
    root not started, a box left open and not started, or a job whose driver is gone); and while running, an ETA: the
    pool estimate (see the vocabulary), at the pool's rate, a worker's LP solves a second over the jobs done times the
    workers (dreeves, 2026-10-23: "Can we throw more compute at 672:13?"); its floor each open case's latest probe's
    least less the case's work so far (the run's own before fanout counted to its case; a case done when every dot of
    its roots is).  journal is the watcher's Records of the path, kept between snapshots; by default a new one, which
    reads it whole."""
    records = (Records(path) if journal is None else journal).read()
    now = time.time() if now is None else now
    observations = {} if observations is None else observations
    launches = {} if launches is None else launches
    header = records[0]
    assert (header['event'], header['version']) == ('header', 1)
    roots, cases_of = header['roots'], header['root_cases']
    assert len(cases_of) == len(header['root_depths']) == roots and header['workers'] > 0
    main = runs(procs, 'fanout.py', header['n'])
    assert len(main) <= 1
    sight(main, launches, now)
    spans, pids, starts, ends, finish, reflections, worker_counts = [], [], {}, {}, [], {}, []
    leasts = {}                         # each probed case's latest least, LP solves
    sessions = []                       # each session's seed, pool record (depths, by depth) and jobs done, in order

    def session(r, t):
        # Legacy sessions use the header count; every new session records its own allocation.
        workers = r.get('workers', header['workers'])
        assert type(workers) is int and workers > 0, workers
        worker_counts.append(workers)
        # A legacy session has no reflected cases; each new session supplies its own mapping.
        mapping = r.get('reflections', {})
        assert type(mapping) is dict
        assert all(target in {str(c) for c in cases_of} and type(source) is int and source in cases_of
                   and source < int(target) for target, source in mapping.items())
        reflections.clear()
        reflections.update({int(target): source for target, source in mapping.items()})
        assert not set(reflections) & set(reflections.values())
        spans.append([t, t])
        pids.append(str(r['pid']))
        sessions.append(dict(seed=r.get('seed'), pool=None, ends=[]))

    def job_start(r, t):
        assert 0 <= r['root'] < roots and cases_of[r['root']] == r['case'], r
        starts[r['job']] = r

    def job_end(r, t):
        assert starts.get(r['job'], {}).get('root') == r['root'] and r['lps'] >= 0 and r['open'] >= 0, r
        # open_depths (fanout.py's since 2026-10-26) only in a session that drew at random, each box deeper than its job's
        assert 'open_depths' not in r or (type(sessions[-1]['seed']) is int and type(r['open_depths']) is list
                                          and len(r['open_depths']) == r['open'] and all(
                                              type(o) is int and o > starts[r['job']]['depth'] for o in r['open_depths'])), r
        ends[r['job']] = r
        sessions[-1]['ends'].append(r)

    def probe(r, t):
        assert str(r['pid']) == pids[-1], r                     # its session's driver's
        leasts[r['case']] = probe_least(r, cases_of, header['n'])

    def pool(r, t):                        # fanout.py's pool record (since 2026-10-26): its session's, once
        assert str(r['pid']) == pids[-1] and sessions[-1]['pool'] is None and set(r) == {'event', 'time', 'pid', 'depths'}, r
        d = r['depths']
        assert type(d) is list and all(type(x) is list and len(x) == 2 and all(type(v) is int for v in x) and x[0] >= 0
                                       and x[1] >= 1 for x in d) and [x[0] for x in d] == sorted({x[0] for x in d}), r
        sessions[-1]['pool'] = collections.Counter(dict(map(tuple, d)))

    def switch(r, t):                      # fanout.py's switch, between sessions: a span of no length, its writer's
        assert set(r) == {'event', 'time', 'pid', 'from', 'to'}, r
        spans.append([t, t])
        pids.append(str(r['pid']))

    handlers = dict(session=session, job_start=job_start, job_end=job_end, probe=probe, switch=switch, pool=pool,
                    finish=lambda r, t: finish.append(r))
    previous = header['time']
    for r in records[1:]:
        assert r['event'] in handlers and not finish, r
        t = started_at(r, launches)
        assert previous <= t <= r['time'] <= now, r
        handlers[r['event']](r, t)
        spans[-1][1] = previous = r['time']
    assert spans
    spans, status = spans_of(spans, pids, main, launches, observations, now, bool(finish))
    # only the latest session's driver runs jobs; one an earlier driver left unended is pending again
    running = {j for j in starts if j not in ends and str(starts[j]['pid']) == pids[-1]
               and starts[j]['case'] not in reflections} if status == 'running' else set()
    groups = []
    for root in range(roots):
        done = [e for e in ends.values() if e['root'] == root]
        split, live = sum(e['open'] > 0 for e in done), sum(starts[j]['root'] == root for j in running)
        pending = 1 + sum(e['open'] for e in done) - len(done) - live
        assert pending >= 0, (root, pending)
        # A reflected target remains open until the final checked exclusion, including during proof replay.
        reflected = '0' if finish and finish[0]['outcome'] == 'excluded' else '1'
        waiting = reflected if cases_of[root] in reflections else '3'
        groups.append('2' * split + '0' * (len(done) - split) + '4' * live + waiting * pending)
    counts = {name: sum(g.count(str(i)) for g in groups) for i, name in enumerate(SEA_STATUSES)}
    cases = sorted(set(cases_of) - set(reflections))
    work = {c: header['prefix_lp'] * (c == header['prefix_case']) + sum(e['lps'] for e in ends.values() if e['case'] == c)
            for c in cases}
    complete = {c for c in cases if all(set(g) <= {'0', '2'} for g, k in zip(groups, cases_of) if k == c)}
    floor = sum(max(0, leasts.get(c, 0) - work[c]) for c in cases if c not in complete)
    samples = [(starts[e['job']]['depth'], e['lps'], e['open_depths']) for e in ends.values() if 'open_depths' in e]
    latest = sessions[-1] if sessions else dict(pool=None, ends=[])
    held = collections.Counter(latest['pool'] or {})
    for e in latest['ends']:                # the latest session's jobs done: each its box out, its open boxes in
        held[starts[e['job']]['depth']] -= 1
        held.update(e.get('open_depths', []))
    # TODO: error copy; says the pool of fanout's run would hold fewer than no boxes at some depth, giving the counts
    assert latest['pool'] is None or min(held.values(), default=0) >= 0, f'Claude: "a pool count below 0: {dict(held)}"'
    held = {d: c for d, c in sorted(held.items()) if c}
    seconds = sum(e['seconds'] for e in ends.values())
    eta = (pool_estimate(samples, held, header['n'], sum(e['lps'] for e in ends.values()) / seconds * worker_counts[-1],
                         floor)
           if status == 'running' and latest['pool'] is not None and samples and held and seconds > 0 else None)
    if status == 'running':
        observations[str(float(now))] = eta
    return dict(program='fanout.py', n=header['n'], order=header['order'], made=now, state=status, workers=worker_counts[-1],
                outcome=finish[0]['outcome'] if finish else None, so_far=sum(b - a for a, b in spans),
                to_go=to_go_of(eta), etas=observations, passes=spans,
                sea=dict(depth=0, keys=[f'{c}:{d}' for c, d in zip(cases_of, header['root_depths'])], groups=groups,
                         counts=counts))


def survey_attempts(path, procs, now, observations, program, n, order, scope, control_required=1):
    """Joined witness attempts, with calibration separate from target work.

    Completed attempts remain open: neither pruning nor a wall-time limit
    proves an exclusion. Observation timestamps preserve elapsed time across
    disappearance and resumption, without extrapolating a completion time.
    """
    records = [json.loads(line) for line in complete_lines(path)]
    now = time.time() if now is None else now
    observations = {} if observations is None else observations
    header = records[0]
    assert (header['event'], header['version'], header['n'], header['order']) == ('header', 1, n, order)
    assert all(type(header[k]) is int and header[k] > 0 for k in ('total', 'control_total'))
    assert type(header['seconds']) in (int, float) and 0 < header['seconds'] < float('inf')
    assert header['time'] <= now
    limits = dict(calibration=header['control_total'], search=header['total'])
    done = {phase: {} for phase in limits}
    seconds = {phase: {} for phase in limits}
    state = dict(pid=None, phase='preparation', outcome=None, active=None, time=header['time'])
    spans = []
    calibrated = lambda: list(done['calibration'].values()).count('witness') >= control_required

    def session(r):
        state.update(pid=r['pid'], phase='preparation', outcome=None, active=None)
        spans.append([r['time'], r['time']])

    def phase(r):
        assert r['phase'] in ('preparation', 'calibration', 'search') and state['active'] is None
        assert r['phase'] != 'search' or calibrated()
        state['phase'] = r['phase']

    def attempt_start(r):
        p, i = r['phase'], r['attempt']
        assert p in limits and p == state['phase'] and state['active'] is None
        assert type(i) is int and 0 <= i < limits[p] and i not in done[p]
        state['active'] = (p, i)

    def attempt_end(r):
        p, i = r['phase'], r['attempt']
        assert state['active'] == (p, i)
        assert r['outcome'] in ('empty', 'timeout', 'witness') and r['elapsed'] >= 0
        done[p][i] = r['outcome']
        seconds[p][i] = r['elapsed']
        state['active'] = None

    def finish(r):
        assert r['outcome'] in ('witness', 'budget', 'control_failed', 'failed')
        assert r['outcome'] != 'witness' or 'witness' in done['search'].values()
        assert r['outcome'] != 'budget' or (calibrated() and
                                           len(done['search']) == header['total'])
        assert r['outcome'] != 'control_failed' or (not calibrated() and
                                                   len(done['calibration']) == header['control_total'])
        state.update(outcome=r['outcome'], active=None)

    handlers = dict(session=session, phase=phase, attempt_start=attempt_start,
                    attempt_end=attempt_end, finish=finish)
    for r in records[1:]:
        assert r['event'] in handlers and type(r['pid']) is int
        assert state['time'] <= r['time'] <= now
        assert r['event'] == 'session' or (spans and r['pid'] == state['pid'] and state['outcome'] is None)
        handlers[r['event']](r)
        spans[-1][1] = state['time'] = r['time']
    assert spans
    main = [p for p in runs(procs, program) if p[0] == state['pid']]
    assert len(main) <= 1
    status = ('ended' if state['outcome'] is not None or not main else
              'frozen' if main[0][2].startswith('T') else 'running')
    observed = list(map(float, observations))
    assert all(spans[0][0] <= t <= now for t in observed)
    for span, stop in zip(spans, [a for a, _ in spans[1:]] + [now + 1]):
        span[1] = max([span[1]] + [t for t in observed if span[0] <= t < stop])
    if status == 'running':
        spans[-1][1] = now
        observations[str(float(now))] = None
    active = state['active'] if status == 'running' else None
    codes = ''.join('1' if i in done['search'] else '4' if active == ('search', i) else '3'
                    for i in range(header['total']))
    counts = {name: codes.count(str(i)) for i, name in enumerate(SEA_STATUSES)}
    elapsed = sum(b - a for a, b in spans)
    work = dict(control_attempted=len(done['calibration']), control_total=header['control_total'],
                control_witnesses=list(done['calibration'].values()).count('witness'),
                attempted=len(done['search']), total=header['total'],
                empty=list(done['search'].values()).count('empty'),
                timeout=list(done['search'].values()).count('timeout'), elapsed=int(elapsed))
    run = dict(program=program, n=n, order=order, made=now, state=status, outcome=state['outcome'],
                so_far=elapsed, to_go=None, etas={}, passes=spans,
                display=dict(scope=scope, phase=state['phase'], outcome=state['outcome'], work=work),
                sea=dict(depth=0, keys=[f'{n}:{order}'], groups=[codes], counts=counts))
    return run, header, done, active, seconds


def survey_join(path, procs, now=None, observations=None):
    return survey_attempts(path, procs, now, observations, 'join720.py', 720, 11, 'joined-witness')[0]


def survey_search288(path, procs, now=None, observations=None):
    """The revised search's calibration and target attempts, as separate dot blocks."""
    run, header, done, active, _ = survey_attempts(path, procs, now, observations,
                                               'search288.py', 288, 10, 'calibrated-witness')
    assert (header['control_n'], header['control_order']) == (240, 10)
    control = ''.join('1' if i in done['calibration'] else '4' if active == ('calibration', i) else '3'
                      for i in range(header['control_total']))
    run['sea']['keys'].insert(0, '240:10')
    run['sea']['groups'].insert(0, control)
    codes = ''.join(run['sea']['groups'])
    run['sea']['counts'] = {name: codes.count(str(i)) for i, name in enumerate(SEA_STATUSES)}
    run['display']['work'].update(control_empty=list(done['calibration'].values()).count('empty'),
                                   control_timeout=list(done['calibration'].values()).count('timeout'))
    return run


def survey_pruning288(path, procs, now=None, observations=None):
    """Paired pruning widths: separate control and target blocks for each variant."""
    run, header, done, active, seconds = survey_attempts(path, procs, now, observations,
                             'pruning288.py', 288, 10, 'paired-pruning', control_required=2)
    assert (header['control_n'], header['control_order'], header['control_total'], header['total']) == (240, 10, 2, 14)
    assert header['widths'] == [0, 0.1] and header['cases'] == list(range(7))
    groups = [''.join('1' if i in done[phase] else '4' if active == (phase, i) else '3'
                       for i in range(variant, total, 2))
              for phase, total in (('calibration', 2), ('search', 14)) for variant in range(2)]
    codes = ''.join(groups)
    run['sea'].update(keys=['240:10 baseline', '240:10 wider', '288:10 baseline', '288:10 wider'],
                       groups=groups, counts={name: codes.count(str(i)) for i, name in enumerate(SEA_STATUSES)})
    work = run['display']['work']
    work['variant_total'] = 7
    for variant, name in enumerate(('baseline', 'wider')):
        outcomes = [outcome for i, outcome in done['search'].items() if i % 2 == variant]
        work.update({name + '_attempted': len(outcomes),
                     name + '_control_witnesses': int(done['calibration'].get(variant) == 'witness'),
                     name + '_seconds': sum(t for i, t in seconds['search'].items() if i % 2 == variant)})
        work.update({name + '_' + field: outcomes.count(outcome)
                     for field, outcome in (('empty', 'empty'), ('timeout', 'timeout'), ('witnesses', 'witness'))})
    return run


def survey_track(target, records, procs, now):
    """The tracked search (see the vocabulary) of target N:M whose runs' records are records (each its lines, as JSON),
    as the process list procs shows it at time now (epoch seconds): what the data file needs of it.  Its state is
    running while a run runs, frozen while none runs and one is frozen, and ended once none is either; its outcome,
    once none is active, 'found' if the found files of their starts hold a line in all, 'none' if no result and every
    run ended with status 0 or null, else null (the page shows an ended search with no outcome as aborted).  Its time so far runs from its first
    start to now, or to its last line once it ended.  One dot per run in record order, in the colors of settled for
    ended, running for running, pending for frozen and open for aborted.  work counts the runs by state and the found
    files' lines (a missing file holds none), each file once."""
    n, order = map(int, target.split(':'))
    live = {pid: stat for pid, _, stat, _ in procs if not stat.startswith('Z')}
    states = [(('ended' if r[-1]['status'] in (0, None) else 'aborted') if r[-1]['event'] == 'end' else
               'aborted' if r[0]['pid'] not in live else
               'frozen' if live[r[0]['pid']].startswith('T') else 'running') for r in records]
    files = sorted({r[0]['found'] for r in records} - {None})
    found = sum(len(complete_lines(f)) if os.path.exists(f) else 0 for f in files)
    state = 'running' if 'running' in states else 'frozen' if 'frozen' in states else 'ended'
    outcome = ('found' if found else 'none') if state == 'ended' and (found or set(states) == {'ended'}) else None
    t0 = min(r[0]['time'] for r in records)
    t1 = now if state != 'ended' else max(r[-1]['time'] for r in records)
    dots = {'ended': 'settled', 'running': 'running', 'frozen': 'pending', 'aborted': 'open'}
    codes = ''.join(str(SEA_STATUSES.index(dots[st])) for st in states)
    work = dict(runs=len(states), **{st: states.count(st) for st in ('running', 'frozen', 'ended', 'aborted')}, found=found)
    return dict(program=records[0][0]['program'], n=n, order=order, made=now, state=state, outcome=outcome,
                so_far=t1 - t0, to_go=None, etas={}, passes=[[t0, t1]], display=dict(tracked=True, work=work),
                sea=dict(depth=0, keys=[target], groups=[codes],
                         counts={name: codes.count(str(i)) for i, name in enumerate(SEA_STATUSES)}))


def clock(t): return '—' if t is None else time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))


def eta_records(s):
    """The run's record of ETAs (see ETA in the vocabulary) with an estimate, in time order, as (time, running hours
    before it, median (mean before 2026-10-19), lo, hi), hours.  A recorded time's running hours come from the passes: one after a pass's last
    line (its process ran on, or was stopped, unlogged) counts as that pass's end, the log's clock being the only one;
    it must fall between the first pass's start and the snapshot (asserted)."""
    spans = s['passes']
    starts = [a for a, _ in spans]
    before = list(itertools.accumulate((b - a for a, b in spans), initial=0.0))   # running seconds before each pass
    def elapsed(t):
        k = bisect.bisect_right(starts, t) - 1
        # TODO: error copy; says the record of ETAs holds a time before the search began or after the snapshot
        assert k >= 0 and t <= spans[-1][1], f'Claude: "the ETA of {clock(t)} falls outside the running of {s["n"]} {s["order"]}"'
        return (before[k] + min(t, spans[k][1]) - starts[k]) / HOUR
    return [(t, elapsed(t), *e) for t, e in sorted(((float(t), e) for t, e in s['etas'].items()), key=lambda te: te[0])
            if e is not None]


def js_text(surveys, now):
    """The data file (see the vocabulary): one call, progressData(...);, of the snapshot's JSON: made (now, in whole
    seconds) and, per run, program (overnight_v5.py or boxsplit.py), n, order, state, outcome (its finish's, null without
    one; dreeves, 2026-10-25: the section names a run's state, an ended one completed or aborted by it), so_far (its passes' seconds of running), to_go ({median, lo, hi}, seconds of
    running: the estimate's median and QUANTILES; null without one), etas (its record of ETAs, eta_records, as [time,
    running seconds before it, median (mean before 2026-10-19), lo, hi], the time in whole seconds and the rest in seconds to a tenth, evenly thinned to at most ETA_POINTS, the last kept), statuses
    (SEA_STATUSES), its sea (depth, keys, groups, counts), and stale: null, or for a run whose survey failed or ran past
    LIMIT the time (whole seconds) of the snapshot its data are from (see snapshot; 2026-10-30)."""
    return data_text([run_data(s) for s in surveys], now)


def run_data(s):
    """A run's entry in the data file (see js_text) from its survey, its data this snapshot's (stale null)."""
    def etas(s):
        rs = eta_records(s)
        keep = sorted(set(range(0, len(rs), max(1, -(-len(rs) // ETA_POINTS)))) | {len(rs) - 1}) if rs else []
        return [[int(rs[i][0])] + [round(HOUR * v, 1) for v in rs[i][1:]] for i in keep]
    return ({'program': s['program'], 'n': s['n'], 'order': s['order'], 'state': s['state'], 'outcome': s['outcome'],
             'so_far': s['so_far'], 'to_go': s['to_go'],
             'etas': etas(s), 'statuses': list(SEA_STATUSES)} | s['sea'] | s.get('display', {}) |
            {k: s[k] for k in ('workers',) if k in s} | {'stale': None})


def data_text(runs, now):
    """The data file's text: one call, progressData(...);, of made (now, in whole seconds) and the runs' entries."""
    return 'progressData(' + json.dumps({'made': int(now), 'runs': runs}, separators=(',', ':'), ensure_ascii=False) + ');\n'


def read_data(path):
    """The data file at path, as JSON (asserted to be one progressData(...); call)."""
    text = open(path, encoding='utf-8').read()
    # TODO: error copy; says the data file is not one progressData(...); call, naming it
    assert text.startswith('progressData(') and text.endswith(');\n'), f'Claude: "{path} is no data file"'
    return json.loads(text.removeprefix('progressData(').removesuffix(');\n'))


def seeded(path):
    """The last good data (see snapshot) of each run in the data file at path, if there is one: {(program, n, order):
    ([its entry], the time of its data, its stale time or else the file's made)}.  A file made before 2026-10-30 has no
    stale field: its data are its own made time's."""
    data = read_data(path) if os.path.exists(path) else {'made': None, 'runs': []}
    kept = {}
    for r in data['runs']:
        # TODO: error copy; says the data file holds two runs of the same program, length and order, naming them
        assert (r['program'], r['n'], r['order']) not in kept, f'Claude: "{path} holds {r["program"]} {r["n"]} {r["order"]} twice"'
        kept[r['program'], r['n'], r['order']] = ([r], r.get('stale') or data['made'])
    return kept


def snapshot(units, kept, readings, now, overruns):
    """The data file's runs and the time it is made, from units, each (its run's identity, (program, n, order), and a
    thunk making its surveys, one or none): each thunk bounded by LIMIT seconds times 2 to the number of its run's
    overruns since its last completed survey (overruns, by identity; bounded), so that one run's slow or failing survey
    leaves the others theirs (2026-10-30: 288@10's 90-minute snapshot froze every run), and a step of a survey that
    starts over whenever it is cut off (outside atomic blocks) still finishes within a few snapshots.  A run whose
    survey failed or ran past its limit keeps its last good data from kept (this watcher's earlier snapshots, or the
    data file it found at its start), marked stale with that data's time, and the watcher's log gets the traceback; a
    failure (not Overtime) also drops its reading (readings), begun anew the next time.  made is now, or the latest
    time a survey says it was made at."""
    runs, made, fresh = [], now, []
    for identity, thunk in units:
        try:
            surveys = bounded(LIMIT * 2 ** overruns.get(identity, 0), thunk)
            data = [run_data(s) for s in surveys]
            # TODO: error copy; says a survey's runs are not the one its unit names, naming both
            assert all((r['program'], r['n'], r['order']) == identity for r in data), f'Claude: "{identity} surveyed as another"'
            made = max([made] + [s['made'] for s in surveys if 'made' in s])
            runs += data
            fresh.append((identity, data))
            overruns[identity] = 0
        except Overtime:
            runs += stale(identity, kept, f'ran past {LIMIT * 2 ** overruns.get(identity, 0)} s')
            overruns[identity] = overruns.get(identity, 0) + 1
        except Exception:
            readings.pop(identity, None)
            runs += stale(identity, kept, 'failed')
    for identity, data in fresh: kept[identity] = (data, int(made))
    return runs, made


def stale(identity, kept, why):
    """The last good data of the run whose identity this is, marked stale (see snapshot), after writing why to the log."""
    data, t = kept.get(identity, ([], None))
    # TODO: log line; says this run's survey failed or ran past its limit (why), so the data file shows its data of that time, marked stale
    report(f'{" ".join(map(str, identity))} {why}: its data of {clock(t)} stand, marked stale')
    return [dict(r, stale=t) for r in data]


def report(what):
    """Write what went wrong to the watcher's log (stderr), stamped, with the traceback of the exception being handled."""
    print(f'{clock(time.time())} Claude: "{what}"', file=sys.stderr, flush=True)
    traceback.print_exc()


def tried(what, f):
    """[f()], or [] once report has written that what failed: a journal or record the watcher cannot read is left out of
    the snapshot, whose other runs go on."""
    try:
        return [f()]
    except Exception:
        # TODO: log line; says reading this journal or record failed, so the snapshot leaves it out
        report(f'{what} failed; this snapshot leaves it out')
        return []


# A cache (CACHE, and each wrapper's own) is a directory of files, one per top-level key, KEY.json holding the entry's
# JSON (2026-10-30: the one 106 MB file, 99 MB of it 288@10's splits, was rewritten at every snapshot, about 150 GB a
# day, when one record of ETAs had changed).
STORED = {}                                 # (a cache's directory, a key) -> what this process last loaded from or
                                            # wrote to that key's file there, as stored() makes it (see save_cache)
BIG = 1000                                  # an entry's items from which save_cache tells a change by object and length


def stored(v):
    """What STORED keeps of an entry v: v and its length for an entry of BIG items or more, which is only ever added to
    (a run's splits, by children and recover_splits; its records of ETAs and observations, by time), so that the same
    object of the same length is the same entry; else its JSON, since a small entry may change in place (a run's
    launches: each [first, last] pair's last)."""
    return (v, len(v)) if len(v) >= BIG else json.dumps(v, sort_keys=True)


def entry_file(path, key):
    """The file of the cache in the directory path that holds the entry key: KEY.json, the key a name of letters,
    digits, '_', '.' and '-' not beginning with '.' or '-' (asserted)."""
    # TODO: error copy; says this cache key can be no file's name, quoting it
    assert re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', key), f'Claude: "the cache key {key!r} names no file"'
    return os.path.join(path, key + '.json')


def load_cache(path):
    """The cache in the directory path ({} if there is none): each KEY.json's entry under its key, each noted in
    STORED as loaded.  A file a write left half made has another name (write_atomic's), which this leaves out.  path
    must be a directory or nothing (asserted: a cache file of the single-file form before 2026-10-30 is converted
    once, not read as empty)."""
    path = os.path.abspath(path)
    # TODO: error copy; says the cache at this path is a file, not a directory of entries, naming it
    assert os.path.isdir(path) or not os.path.exists(path), f'Claude: "the cache {path} is no directory"'
    cache = {}
    for name in sorted(glob.glob(os.path.join(glob.escape(path), '*.json'))):
        key = os.path.basename(name).removesuffix('.json')
        with open(name, encoding='utf-8') as fh: cache[key] = json.load(fh)
        STORED[path, key] = stored(cache[key])
    return cache


def save_cache(path, cache):
    """Keep cache in the directory path (made if missing): each entry's JSON, json.dumps(entry, sort_keys=True), in its
    own file (entry_file), written (write_atomic) only when the entry is not what this process last loaded from or wrote
    to that file (STORED; see stored).  Every key loaded or written there must still be in cache (asserted: its file
    would bring it back at the next load)."""
    path = os.path.abspath(path)
    # TODO: error copy; says a cache no longer holds a key whose file its directory has, naming the directory
    assert {k for p, k in STORED if p == path} <= set(cache), f'Claude: "the cache {path} lost a key"'
    os.makedirs(path, exist_ok=True)
    for key in sorted(cache):
        mark = stored(cache[key])
        if mark != STORED.get((path, key)):
            write_atomic(entry_file(path, key), json.dumps(cache[key], sort_keys=True))
            STORED[path, key] = mark


def native288(start):
    """The exact tracked x288 chain already represented by its native overnight and box surveys.

    Compare the durable start record, including its directory and complete shell program, so ended runs remain
    recognized while unrelated heuristics for the same target keep their separate tracker records.
    """
    if not (start['target'] == '288:10' and (288, 10) in RUNS and start['adopted'] is False
            and os.path.realpath(start['cwd']) == os.path.realpath(os.path.join(HERE, DIRS[288, 10]))):
        return False
    command = shlex.split(start['command'])
    match = (len(command) == 3 and command[:2] == ['/bin/sh', '-c']
             and re.match(r'(\S+) -B ', command[2]))
    steps = (('overnight_v5.py', '288', '10'), ('boxsplit.py', '288', '10'),
             ('handoff288.py',), ('overnight_v5.py', '288', '10'))
    return bool(match and re.fullmatch(r'Python|python[\d.]*', os.path.basename(match[1]))
                and command[2] == ' && '.join(shlex.join([match[1], '-B', *step]) for step in steps))


def run_surveys(procs, now, cache, readings):
    """The units (see snapshot) of the overnight and boxsplit passes, each surveyed with its run's actual modules,
    headers and cache fingerprints (run_context), its reading kept in readings by its identity.  An overnight run's
    splits and record of ETAs are kept in cache under its geometry (run_modules.geometry), which a change of its solver
    leaves as it was (2026-10-30; under overnight_v5.CODE before, so that each solver change began them anew)."""
    def overnight(n, order):
        with run_context(n, order):
            journal, log = files(n, order)
            reading = readings.setdefault(('overnight_v5.py', n, order), Reading(journal, log))
            v5.configure(n, order)                                       # the geometry reads the run's configuration
            key = f'{n}_{order}_geometry_{run_modules.geometry(v5)}'
            return [survey(n, order, journal, log, procs, now, cache.setdefault(key, {}),
                           cache.setdefault(key + '_etas', {}), reading)]

    def boxes(n, order):                # none until the driver's log exists
        with run_context(n, order):
            log, main = box_files(n, order)
            box = readings.setdefault(('boxsplit.py', n, order), Boxes(log))
            return ([survey_box(n, order, log, main, procs, now, cache.setdefault(f'{n}_{order}_boxsplit_{bx.CODE}_etas', {}),
                                box)] if os.path.exists(log) else [])
    return ([(('overnight_v5.py', n, order), functools.partial(overnight, n, order)) for n, order in RUNS] +
            [(('boxsplit.py', n, order), functools.partial(boxes, n, order)) for n, order in EXTENDED])


def survey_runs(procs, now, cache):
    """Survey overnight and box passes with each run's actual modules, headers and cache fingerprints: run_surveys'
    surveys, made at once, each with a reading of its own."""
    return [s for _, thunk in run_surveys(procs, now, cache, {}) for s in thunk()]


def first_line(path):
    """The file's first line, as bytes, its newline included if it has one."""
    with open(path, 'rb') as f: return f.readline()


def headers(pattern):
    """(path, header) of each journal matching pattern in HERE whose first line is whole (a journal being begun has no
    run yet), sorted by path; one that cannot be read is left out (tried)."""
    firsts = [(path, first) for path in sorted(glob.glob(os.path.join(HERE, pattern)))
              for first in tried(f'the first line of {path}', functools.partial(first_line, path))]
    return [(path, h) for path, first in firsts if first.endswith(b'\n')
            for h in tried(f'the header of {path}', functools.partial(json.loads, first))]


def journal_surveys(procs, now, cache, readings):
    """The units (see snapshot) of the searches surveyed from their journals and records: focus.py's and fanout.py's
    runs, the 288 attempt batches, then the tracked searches (see the vocabulary), one per target, in that order."""
    def focus(identity, path, key, pause_path):
        pauses = [json.loads(line) for line in complete_lines(pause_path)] if os.path.exists(pause_path) else []
        return [survey_focus(path, procs, observations=cache.setdefault(key + '_observations', {}),
                             launches=cache.setdefault(key + '_launches', {}), pauses=pauses,
                             journal=readings.setdefault(identity, Records(path)))]

    def fanned(identity, path, key):
        return [survey_fanout(path, procs, observations=cache.setdefault(key + '_observations', {}),
                              launches=cache.setdefault(key + '_launches', {}),
                              journal=readings.setdefault(identity, Records(path)))]

    def attempts(survey_of, path, key):
        return [survey_of(path, procs, observations=cache.setdefault(key + '_observations', {}))]

    units = [(('focus.py', h['n'], h['order']),
              functools.partial(focus, ('focus.py', h['n'], h['order']), path, f'focus_{h["n"]}_{h["code"]}_{h["time"]}',
                                os.path.join(HERE, f'focus_{h["n"]}_pauses.jsonl')))
             for path, h in headers('focus_*_journal.jsonl')]
    units += [(('fanout.py', h['n'], h['order']),
               functools.partial(fanned, ('fanout.py', h['n'], h['order']), path, f'fanout_{h["n"]}_{h["code"]}_{h["time"]}'))
              for path, h in headers('fanout_*_journal.jsonl')]
    units += [((name + '.py', 288, 10), functools.partial(attempts, survey_of, path, f'{name}_{h["code"]}_{h["time"]}'))
              for name, survey_of in (('search288', survey_search288), ('pruning288', survey_pruning288))
              for path, h in headers(name + '_journal.jsonl')]
    def recorded(path):                 # a tracked run's records, whether native288's, its target's identity
        lines = [json.loads(line) for line in complete_lines(path)]
        return lines, native288(lines[0]), lines[0]['target'], (lines[0]['program'], *map(int, lines[0]['target'].split(':')))

    tracked, identities = collections.defaultdict(list), {}
    for path in sorted(glob.glob(os.path.join(HERE, 'runs', '*.jsonl'))):
        for lines, native, target, identity in tried(f'the records of {path}', functools.partial(recorded, path)):
            if not native:
                tracked[target].append(lines)
                identities.setdefault(target, identity)
    def track(target, records): return [survey_track(target, records, procs, now)]
    return units + [(identities[target], functools.partial(track, target, records)) for target, records in sorted(tracked.items())]


def main(argv, extra=()):
    """The watcher: write the data file once, or with --watch again every REFRESH seconds, keeping the cache, each run's
    reading and its last good data between snapshots (see snapshot).  extra holds more makers of units, each called
    with (procs, now) for its units after progress.py's own (the wrappers sweep288_progress and search592_progress)."""
    # TODO: error copy; says how to run the script: with no argument to write the data file once, or with --watch to keep rewriting it
    assert argv in ([], ['--watch']), 'Claude: "usage: python3 -B progress.py [--watch]"'
    os.nice(max(0, NICE - os.nice(0)))
    cache, kept, readings, overruns = load_cache(CACHE), seeded(JS), {}, {}
    while True:
        try:
            procs, now = processes(), time.time()
            units = (run_surveys(procs, now, cache, readings) + journal_surveys(procs, now, cache, readings)
                     + [u for make in extra for u in make(procs, now)])
            runs, made = snapshot(units, kept, readings, now, overruns)
            write_atomic(JS, data_text(runs, made))
            save_cache(CACHE, cache)
        except Exception:               # outside every run's survey: the watcher goes on, its data file as last written
            # TODO: log line; says this snapshot failed outside any run's survey, so the data file stays as last written
            report('the snapshot failed; the data file stays as it was')
            if not argv: raise
        if not argv: return
        time.sleep(REFRESH)


if __name__ == '__main__':
    main(sys.argv[1:])
