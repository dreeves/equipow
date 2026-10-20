#!/usr/bin/env python3
"""How far the certified searches of overnight_v5.py have got: the data file of index.html's section "Search progress"
(dreeves, 2026-10-17, in place of the page progress.html this file used to write).

Run:   python3 -B progress.py            writes progress.js once
       python3 -B progress.py --watch    rewrites it every REFRESH seconds until stopped
Either way the process first lowers its priority to nice NICE.  progress.js, next to this file and index.html, is
replaced atomically (see write_atomic), so a reader never sees half of it.  Quals: python3 -B quals_progress.py

For each run (N, ORDER) in RUNS it reads overnight_v5_N_ORDER_journal.jsonl and overnight_v5_N_ORDER.log (see
overnight_v5.py's docstring for their formats and for node, split, pool, budget, verdict and cascade) and the process
list.  The tree's levels are enumerated with overnight_v5.split itself, each node split at most once: the children's
keys are kept in CACHE, a file git ignores, by run and by overnight_v5.CODE.  Vocabulary, each term defined once here:
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
              range (its draws' QUANTILES), by the snapshot's time, in CACHE (by run and overnight_v5.CODE); the data
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
              subtrees, at their logged cost, and partway ones, at their eventual cost.  Their urn gives the subtree
              cost of each node of kind 'subtree' at that depth, pending or running (a running one's elapsed time, a
              few seconds of solve and split, is ignored).  Depths go from the bottom up, so a partway member's
              eventual cost is drawn before its depth's draws are made.
  items       the remaining work in search()'s order: the running jobs that are not leaves first (their children go
              on top of the stack), then the stack from its top, a resplit node replaced by its children in the order
              search() pops them.  A leaf is a job of one worker; a subtree is fluid, spread over the free workers.
  makespan    list scheduling on the pass's workers: each running leaf's remaining seconds hold its worker; a leaf
              job goes to the worker free first; fluid work fills the earliest-free workers to a common level (water
              filling).  The makespan is when the last worker is free: the remaining time.
  no estimate an empty array: when a node of kind 'subtree' waits at a depth with no population yet (a fresh subtree
              needs a member's job and split), or no fresh leaf solve has been logged yet (no speed, so no gap).  The
              model then has nothing to draw from.
The data file says when the snapshot was made, to the second, and the section keeps its age up to date.  Per run it
gives the state, the hours of running so far and to go, the record of ETAs and the sea (see js_text).
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, bisect, hashlib, itertools, subprocess, collections
import numpy as np
import overnight_v5 as v5
import boxsplit as bx

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, 'progress.js')         # the data file of index.html's section "Search progress" (see the vocabulary)
CACHE = os.path.join(HERE, '.progress_cache.json')
EXTENDED = ((240, 11),)                # the runs whose boxsplit.py pass the section shows after the run (2026-10-17)
RUNS = ((240, 11),)                    # the certified runs, (N, ORDER), in the section's order; 304@9 is settled (2026-10-10)
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


# ---------- reading the runs' files ----------

def files(n, order):
    """The journal and log of the run (n, order), named as overnight_v5.configure names them."""
    v5.configure(n, order)
    return v5.JOURNAL, v5.LOG


def complete_lines(path):
    """The file's complete lines: a last line without its newline is still being written, so it is left out."""
    return open(path, encoding='utf-8').read().split('\n')[:-1]


def read_journal(path):
    """The journal's last record per key, for overnight_v5's current configuration, whose header it must have.
    overnight_v5.Journal.admit checks each record as the run does (made without Journal's __init__, which would
    create a missing journal)."""
    lines = complete_lines(path)
    # TODO: error copy; says the journal at this path was written by another configuration or another version of the code
    assert json.loads(lines[0]) == v5.header(), f'Claude: "the journal {path} belongs to another configuration"'
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
def stamp(text): return time.mktime(time.strptime(text, '%Y-%m-%d %H:%M:%S'))


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
    pass's outcome but the next start line (all asserted)."""
    passes = []
    for line in lines:
        forms = [(kind, m) for kind, form in FORMS.items() if (m := form.match(line))]
        # TODO: error copy; says a line of the log has none of the forms progress.py knows, quoting the line
        assert len(forms) == 1, f'Claude: "a log line of no known form: {line}"'
        kind, m = forms[0]
        t = stamp(m[1])
        if kind == 'start':
            passes.append({'start': t, 'n': int(m[2]), 'order': int(m[3]), 'processes': int(m[4]), 'budgets': ints(m[5]),
                           'pool_budget': int(m[6]), 'highs': m[7], 'moduli': ints(m[8]), 'earlier': int(m[9]),
                           'shuffled': m[10] is not None, 'nodes': [], 'opens': [], 'outcome': None})
        # TODO: error copy; says a line of the log comes before any start line or after its pass's outcome line, quoting it
        assert passes and passes[-1]['outcome'] is None, f'Claude: "a log line out of place: {line}"'
        p = passes[-1]
        p['last'] = t
        if kind == 'node':
            p['nodes'].append({'t': t, 'i': int(m[2]), 'key': m[3], 'verdict': m[4], 'solve': float(m[5]),
                               'split': float(m[6]), 'closed': int(m[7]), 'waiting': int(m[8]), 'running': int(m[9]),
                               'open': int(m[10]), 'failures': int(m[11])})
        if kind == 'open': p['opens'].append(m[2])
        if kind == 'outcome': p['outcome'] = m[2]
    return passes


def parse_log(path):
    """parse_lines of the log's complete lines."""
    return parse_lines(complete_lines(path))


def processes():
    """The machine's processes as (pid, ppid, stat, command), from ps (which prints whole commands to a pipe)."""
    out = subprocess.run(['ps', '-ax', '-o', 'pid=,ppid=,stat=,command='], capture_output=True, text=True, check=True)
    return [(int(a), int(b), c, d) for a, b, c, d in (line.split(None, 3) for line in out.stdout.splitlines())]


def run_state(procs, program, n, order, outcome):
    """The state (see the vocabulary) of program's run (overnight_v5.py's or boxsplit.py's), from the process list and
    the current pass's outcome line (or None): frozen when its main process is stopped; a stopped worker only takes
    capacity away, and the run goes on (dreeves, 2026-10-20: two of 240@11's four boxsplit workers were paused)."""
    main = [p for p in procs if re.search(rf'(?:^|[\s/]){re.escape(program)} {n} {order}\s*$', p[3])]
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
    lines not read yet, and are left out."""
    lines = complete_lines(log)
    texts = complete_lines(journal)
    # TODO: error copy; says the journal at this path was written by another configuration or another version of the code
    assert json.loads(texts[0]) == v5.header(), f'Claude: "the journal {journal} belongs to another configuration"'
    stamps = [stamp(line[:19]) for line in lines]
    # TODO: error copy; says a line of the log at this path is stamped earlier than the line before it
    assert all(a <= b for a, b in zip(stamps, stamps[1:])), f'Claude: "the log {log} goes back in time"'
    passes = parse_lines(lines)
    kinds = [next(kind for kind, form in FORMS.items() if form.match(line)) for line in lines]
    starts = [i for i, kind in enumerate(kinds) if kind == 'start']
    node_lines = [[i for i in range(a, b) if kinds[i] == 'node'] for a, b in zip(starts, starts[1:] + [len(lines)])]
    assert [len(x) for x in node_lines] == [len(p['nodes']) for p in passes]
    records = [json.loads(x) for x in texts[1:]]
    present = {(r['key'], r['verdict'], r['budget']) for r in records}
    replayed = object.__new__(v5.Journal)          # made without Journal's __init__, which would create a journal
    replayed.records = {}
    fresh, dates, last = {}, [], {}                # last: each key's latest progress line read so far

    def admit(line):                               # the next record, dated by this line
        assert line >= 0
        replayed.admit(records[len(dates)])
        dates.append(line)

    def closings():                                # the CLOSED records next in the journal, dated as dating says
        while len(dates) < len(records) and records[len(dates)]['verdict'] == 'CLOSED':
            admit(max(dates[-1:] + [last.get(records[len(dates)]['key'], -1)]))

    for p, indices in zip(passes, node_lines):
        for i, nd in zip(indices, p['nodes']):
            last[nd['key']] = i
            budget = budget_of(nd['key'], p['budgets'])
            prev = replayed.records.get(nd['key'], {'verdict': 'UNKNOWN', 'budget': -1})
            assert prev['verdict'] == 'UNKNOWN', (log, i)                # search() never submits a settled node
            if prev['budget'] >= budget:                                 # split again, with no fresh record
                assert nd['verdict'] == 'UNKNOWN', (log, i)
                continue
            closings()
            if (nd['key'], nd['verdict'], budget) not in present: continue          # dropped by a migration
            # TODO: error copy; says the journal at this path has no record for a progress line that reports a fresh verdict, naming the line
            assert len(dates) < len(records), f'Claude: "the journal {journal} lacks the record of line {i + 1} of its log"'
            r = records[len(dates)]
            assert (r['key'], r['verdict'], r['budget']) == (nd['key'], nd['verdict'], budget), (log, i)
            fresh[i] = len(dates)
            admit(i)
    closings()
    records = records[:len(dates)]
    return {'lines': lines, 'stamps': stamps, 'kinds': kinds, 'passes': passes, 'starts': starts,
            'node_lines': node_lines, 'records': records, 'fresh': fresh, 'dates': dates,
            'bounds': [bisect.bisect_left(dates, s) for s in starts]}


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
    p, k = passes[-1], len(passes)
    return {'t': t, 'label': label, 'passes': passes, 'processes': p['processes'], 'budgets': p['budgets'],
            'final_at_start': {r['key']: r for r in R['records'][:R['bounds'][k - 1]]}, 'records': R['records'],
            'cache': cache}


# ---------- the tree ----------

def members(key):
    """The count vectors in the key's last constraint: none for the top node, a pool's count (M:#count:sha1), or 1."""
    parts = key.split()
    pool = re.fullmatch(r'\d+:#(\d+):[0-9a-f]{40}', parts[-1]) if parts else None
    return 0 if not parts else int(pool[1]) if pool else 1


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


def tree_order(key):
    """The key's place in tree order (see the vocabulary): its constraints compared one by one, a count vector
    M:[a,b,...] as (M, 0, (a, b, ...), '') and a pool M:#c:sha1 as (M, 1, (c,), sha1), so that a node sorts just
    before its descendants."""
    out = []
    for part in key.split():
        M, v = part.split(':', 1)
        if v.startswith('['): out.append((int(M), 0, tuple(int(t) for t in v[1:-1].split(',')), ''))
        else:
            pool = re.fullmatch(r'#(\d+):([0-9a-f]{40})', v)
            assert pool, key
            out.append((int(M), 1, (int(pool[1]),), pool[2]))
    return tuple(out)


def below(key, above):
    """Whether key's node is a proper descendant of above's."""
    return key != above and (above == '' or key.startswith(above + ' '))


def live_keys(final):
    """The journal's keys less those below an INFEASIBLE one (see live in the vocabulary)."""
    keys, cut = set(), None                    # cut: the last INFEASIBLE key kept, in tree order
    for k in sorted(final, key=tree_order):
        if cut is not None and below(k, cut): continue
        keys.add(k)
        cut = k if final[k]['verdict'] == 'INFEASIBLE' else None
    return keys


def sea(final, budgets, cache, running):
    """The sea (see the vocabulary) of the journal's last records final under these budgets, with the splits cached so
    far and the keys running now: {'depth', 'keys' (its groups' sub-cases), 'groups' (each a string of its dots'
    statuses, as indices into SEA_STATUSES), 'counts' (by status)}."""
    bottom = len(budgets) - 1
    depth = min(SEA_DEPTH, bottom - 1)
    assert depth >= 0, budgets
    live = live_keys(final)
    nodes = live | set(running)
    for k in live:
        if status(k, final, budgets) == 'split' and k in cache: nodes.update(cache[k])
    keys = sorted(nodes, key=tree_order)
    front = [k for i, k in enumerate(keys) if not (i + 1 < len(keys) and below(keys[i + 1], k))]
    groups = {}
    for k in front:
        s = 'running' if k in running else status(k, final, budgets)
        groups.setdefault(' '.join(k.split()[:depth]), []).append(str(SEA_STATUSES.index(s)))
    tally = collections.Counter(c for g in groups.values() for c in g)
    return {'depth': depth, 'keys': list(groups), 'groups': [''.join(g) for g in groups.values()],
            'counts': {s: tally[str(i)] for i, s in enumerate(SEA_STATUSES)}}


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


def resplits(R, order, cache):
    """cache, holding the splits of the nodes the run's current pass splits again: UNKNOWN within their budget above
    the bottom when it began.  The replay needs their children (see kind in the vocabulary), which an estimate alone
    asks for: splitting them for an ended run would be work for nothing (240@11's last 88 took 626 s)."""
    budgets = R['passes'][-1]['budgets']
    start = {r['key']: r for r in R['records'][:R['bounds'][-1]]}
    for k in [k for k, r in start.items() if r['verdict'] == 'UNKNOWN' and len(k.split()) < len(budgets) - 1 and r['budget'] >= budget_of(k, budgets)]:
        children(k, order, cache)
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
    unknown (None).  Every live key at an enumerated depth must be a sub-case of that level (asserted)."""
    keyed = collections.defaultdict(list)
    for k in live_keys(final): keyed[len(k.split())].append(k)
    rows = []
    for d in range(bottom + 1):
        known = d < len(levels)
        # TODO: error copy; says the journal holds sub-cases of an enumerated level that the run's split does not give, naming the level
        assert not known or set(keyed[d]) <= set(levels[d]), f'Claude: "the journal has level-{d} sub-cases that split() does not give"'
        c = collections.Counter(status(k, final, budgets) for k in (levels[d] if known else keyed[d]))
        rows.append({'depth': d, 'enumerated': known,
                     'counts': {s: c[s] if known or s != 'pending' else None for s in STATUSES}})
    return rows


# ---------- this pass's work at the estimate's level ----------

def work(level, depth, stats, nodes):
    """This pass's work at the enumerated level at this depth, a list of keys with their statuses in stats, given the
    current pass's progress lines: the counts size (the level's sub-cases), before (settled before this pass), work
    (touched by a line of this pass at or below them, or not settled), and of the work, done (settled or open),
    progress (split) and pending."""
    touched = {' '.join(nd['key'].split()[:depth]) for nd in nodes if len(nd['key'].split()) >= depth}
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
    time), fresh (a done node that certbb solved in this pass, not a resplit)."""
    __slots__ = ('key', 'parent', 'depth', 'kids', 'state', 'cost', 'start', 'fresh')

    def __init__(self, key, parent, depth):
        self.key, self.parent, self.depth = key, parent, depth
        self.kids, self.state, self.cost, self.start, self.fresh = [], 'pending', 0.0, None, False


def parent_key(key): return ' '.join(key.split()[:-1])


def replay(state):
    """The replay (see the vocabulary) as of state['t']: (root, stack, running), the stack's top last."""
    p, cache, P, budgets = state['passes'][-1], state['cache'], state['processes'], state['budgets']
    settled = {k for k, r in state['final_at_start'].items() if r['verdict'] in v5.SETTLED}
    root = Node('', None, 0)
    stack, running = [root], []
    w, r, c, at = 1, 0, 0, None        # the previous line's waiting, running and closed (before the first: the top node, 0, 0)

    def pop(at):                       # search() pops the top: a settled node it skips, another it submits
        node = stack.pop()
        if node.key in settled:
            node.state = 'skipped'
            return 0
        node.state, node.start = 'running', at
        running.append(node)
        return 1

    for nd in p['nodes']:
        submit = nd['running'] + 1 - r
        skip = nd['closed'] - c - (nd['verdict'] == 'INFEASIBLE')     # search() counts each settled node it skips closed
        K = nd['waiting'] - w + submit + skip                          # so the rest of the waiting count's change is the children
        splits = nd['verdict'] == 'UNKNOWN' and len(nd['key'].split()) < len(budgets) - 1
        kids = cache.get(nd['key'])
        if kids is not None and p['shuffled']: kids = v5.sibling_order(nd['key'], kids)
        # TODO: error copy; says the replay of search() cannot account for a progress line's counts, naming the state and the line
        assert submit >= 0 and skip >= 0 and K >= 0 and (splits or K == 0) and (kids is None or len(kids) == K), \
            f'Claude: "the replay of {state["label"]} cannot account for line [{nd["i"]}]"'
        first = nd['t'] - nd['solve'] - nd['split'] if at is None else at
        while submit or skip:          # the pops between the previous line and this one, as many of each as counted
            took = pop(first)
            submit, skip = submit - took, skip - (1 - took)
            assert submit >= 0 and skip >= 0, (state['label'], nd['i'])
        node = find(running, nd)
        running.remove(node)
        node.key, node.state, node.cost = nd['key'], 'done', nd['solve'] + nd['split']
        rec = state['final_at_start'].get(nd['key'])
        node.fresh = rec is None or rec['budget'] < budget_of(nd['key'], budgets)
        assert K == 0 or (splits and members(nd['key']) <= 1), (state['label'], nd['i'])    # a pool never splits
        node.kids = [Node(c, node, node.depth + 1) for c in kids] if kids is not None else [Node(None, node, node.depth + 1) for _ in range(K)]
        stack.extend(node.kids)
        # TODO: error copy; says the replay of search() disagrees with a progress line's waiting or running count, naming the state and the line
        assert (len(stack), len(running)) == (nd['waiting'], nd['running']), f'Claude: "the replay of {state["label"]} breaks at line [{nd["i"]}]"'
        w, r, c, at = nd['waiting'], nd['running'], nd['closed'], nd['t']
    while p['nodes'] and stack and len(running) < P: pop(at)     # the refill after the last line, as search() makes it
    return root, stack, running


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
    bottom = len(state['budgets']) - 1
    recs = {(r['key'], r['budget']): r for r in state['records'] if r['verdict'] != 'CLOSED'}
    claimed, seconds, lps = set(), 0.0, 0
    for p in state['passes']:
        for nd in p['nodes']:
            k = (nd['key'], budget_of(nd['key'], p['budgets']))
            if len(nd['key'].split()) == bottom and k in recs and k not in claimed:
                claimed.add(k)
                seconds, lps = seconds + nd['solve'], lps + recs[k]['lps']
    return seconds / lps if lps else None


class Urn:
    """A Polya urn (see the vocabulary) in each of REPLICATES replicates: one ball per member (members: a 1-d array, the
    same in every replicate, or REPLICATES x m), one per draw made, and one new ball, whose values new(rows, e) gives:
    one value above e for each entry of rows, an index array of replicates that may repeat one."""

    def __init__(self, rng, members, new, room):
        R = REPLICATES
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
def estimate(state, parts=None):
    """REPLICATES samples of the current pass's remaining hours of running (see the vocabulary), or an empty array (no
    estimate).  parts, if a dict, receives the pieces: the tree, the kinds, the draws, the items, the work, the speed."""
    budgets, P, t = state['budgets'], state['processes'], state['t']
    bottom, B = len(budgets) - 1, budgets[-1]
    root, stack, running = replay(state)
    kinds, nodes = {}, []

    def walk(node):                     # every node; the kinds of the pending and running, a resplit one's children made
        nodes.append(node)
        if node.state in ('pending', 'running'):
            kinds[node] = classify(node, state, bottom)
            if kinds[node] == 'resplit' and not node.kids:
                # TODO: error copy; says the cache lacks the split of a node that search() will split again, naming it
                assert node.depth == bottom or node.key in state['cache'], f'Claude: "no cached split for {node.key}"'
                kids = state['cache'].get(node.key, [])
                if state['passes'][-1]['shuffled']: kids = v5.sibling_order(node.key, kids)
                node.kids = [Node(c, node, node.depth + 1) for c in kids]
        for c in node.kids: walk(c)
    walk(root)
    done_leaves = [n for n in nodes if n.state == 'done' and n.fresh and n.depth == bottom]
    censored = sorted((n for n in nodes if n.state == 'running' and kinds[n] == 'leaf'), key=lambda n: n.start)
    waiting = [n for n in nodes if n.state == 'pending' and kinds.get(n) == 'leaf']
    members = np.array([n.cost for n in done_leaves])
    floors = {floor_of(n, state) for n in censored + waiting + done_leaves}
    assert len(floors) <= 1, (state['label'], floors)       # one leaf population per pass
    s = speed(state)
    if parts is not None: parts.update(root=root, stack=stack, running=running, kinds=kinds, nodes=nodes, speed=s, members=members)
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
    sofar, timed = {}, set(censored)

    def total(node):                    # the node's subtree's cost so far in this pass (see partway)
        own = node.cost if node.state == 'done' else t - node.start if node in timed else 0.0
        sofar[node] = own + sum(total(c) for c in node.kids)
        return sofar[node]
    total(root)
    by_depth = collections.defaultdict(list)
    for n in nodes: by_depth[n.depth].append(n)
    zero = np.zeros(REPLICATES)
    for d in range(bottom, -1, -1):
        for n in by_depth[d]:           # a done or resplit node's remaining work is its children's
            if n.state == 'done' or kinds.get(n) == 'resplit':
                below = [rem[c] for c in n.kids if c in rem]
                if below: rem[n] = sum(below, zero)
        if d == bottom: continue
        pop = [n for n in by_depth[d] if n.state == 'done' and n.fresh]
        draws = [n for n in by_depth[d] if kinds.get(n) == 'subtree']
        if draws and not pop: return np.array([])
        if pop:
            eventual = np.tile(np.array([sofar[n] for n in pop]), (REPLICATES, 1))
            for j, n in enumerate(pop):
                if n in rem: eventual[:, j] += rem[n]
            own, kids = np.array([n.cost for n in pop]), np.array([len(n.kids) for n in pop])
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


def survey(n, order, journal, log, procs, now, cache, etas):
    """The run (n, order) as its journal and log, the process list and the time now (epoch seconds) show it: what the
    data file needs of it, and more; cache holds the run's splits (see children), etas its record of ETAs (see the
    vocabulary), to which this snapshot's is added: [the median of its draws, then their QUANTILES], None with none (an
    ended run has none), by its time in whole seconds."""
    v5.configure(n, order)
    R = read_run(journal, log)
    passes = R['passes']
    p = passes[-1]
    # TODO: error copy; says the log's last start line names another length, order, cascade or pool budget than overnight_v5's settings for this run
    assert (p['n'], p['order'], p['moduli'], p['pool_budget']) == (n, order, list(v5.CASCADE), v5.POOL_BUDGET), f'Claude: "the log of {n} {order} does not match overnight_v5.py"'
    budgets, bottom = p['budgets'], len(v5.CASCADE)
    assert len(budgets) == bottom + 1
    final = {r['key']: r for r in R['records']}
    state = run_state(procs, 'overnight_v5.py', n, order, p['outcome'])
    end = now if state == 'running' else max([p['last'], *map(float, etas)])   # every ETA is recorded while it runs
    levels = enumerate_levels(final, budgets, order, cache, DEEPEST)
    rows = level_rows(levels, final, budgets, bottom)
    for r in rows: r['modulus'] = ([None] + list(v5.CASCADE))[r['depth']]
    live = live_keys(final)
    stats = {k: status(k, final, budgets) for k in live | set(levels[-1])}
    tally = collections.Counter(stats[k] for k in live)
    last = (p['nodes'] or [{'t': None, 'waiting': None, 'running': None}])[-1]
    opens = sorted(((k, final[k]['budget'], stats[k]) for k in live if final[k]['verdict'] == 'UNKNOWN' and leaf(k, bottom)),
                   key=lambda x: parse_key(x[0]))
    spans = [(q['start'], q['last']) for q in passes[:-1]] + [(p['start'], end)]
    parts = {}
    draws = estimate(state_at(R, end, resplits(R, order, cache), f'{n}@{order} at {clock(end)}'), parts) if state != 'ended' else None
    etas.setdefault(str(int(end)), [float(np.median(draws))] + [float(q) for q in np.quantile(draws, QUANTILES)] if draws is not None and len(draws) else None)   # a record made stands
    running = {nd.key for nd in parts.get('nodes', []) if nd.state == 'running' and nd.key is not None}
    to_go = ({'median': float(np.median(draws)) * HOUR} | dict(zip(('lo', 'hi'), (float(q) * HOUR for q in np.quantile(draws, QUANTILES))))
             if draws is not None and len(draws) else None)
    return {'program': 'overnight_v5.py', 'n': n, 'order': order, 'state': state, 'outcome': p['outcome'], 'budgets': budgets,
            'sea': sea(final, budgets, cache, running), 'so_far': sum(b - a for a, b in spans), 'to_go': to_go,
            'passes': spans,
            'elapsed': end - p['start'], 'last': p['last'],
            'settled': sum(final[k]['verdict'] == 'INFEASIBLE' for k in live), 'open': tally['open'],
            'split': tally['split'], 'line': last['t'], 'waiting': last['waiting'], 'running': last['running'],
            'levels': rows, 'deepest': len(levels) - 1,
            'processes': p['processes'],
            'work': work(levels[-1], len(levels) - 1, stats, p['nodes']) if state != 'ended' else None,
            'draws': draws, 'etas': etas, 'open_list': opens}


# ---------- a run's boxsplit pass (boxsplit.py over its open leaves; dreeves, 2026-10-17) ----------

def box_files(n, order):
    """The driver's log of the run (n, order) and the run's journal, named as boxsplit.configure names them."""
    bx.configure(n, order)
    return bx.LOG, v5.JOURNAL


BOX_FORMS = {                          # the driver's log line forms, as boxsplit's run, drive and say_* write them
    'start': re.compile(STAMP + r'Claude: "start: n = (\d+), order at least (\d+), open leaves (\d+) of .+ \((\d+) closed '
                        r'on record\), extension moduli \[[\d, ]+\] with budgets \[[\d, ]+\] \(LP solves; a pool or an '
                        r'outside node \d+ per member\), (\d+) processes, HiGHS .+, \d+ earlier verdicts"$'),
    'control': re.compile(STAMP + r'Claude: "startup control passed: .*"$'),
    'leaf': re.compile(STAMP + r'Claude: "leaf (\d+): \{.*\}"$'),
    'split': re.compile(STAMP + r'\{.*\} by \d+: Claude: "box widths .*"$'),
    'outside': re.compile(STAMP + r'\{.*\} by \d+: Claude: "\d+ outside nodes INFEASIBLE .*"$'),
    'piece': re.compile(STAMP + r'\{.*\}: (?:INFEASIBLE|UNKNOWN); Claude: "\d+ LP solves \(\d+\.\d s\)"$'),
    'open': re.compile(STAMP + r'Claude: "open: \{.*\}"$'),
    'done': re.compile(STAMP + r'Claude: "leaf (\d+) \{.*\}: extension tree (closed|not closed)[:,] .*"$'),
    'outcome': re.compile(STAMP + r'(Claude: "(?:ALL \d+ LEAVES CLOSED \(|NOT FINISHED: |WITNESS FOUND in ).*")$'),
}


def parse_box_lines(lines):
    """The passes of a driver's log whose complete lines these are, in order, each a dict: start and last, the times of
    its start line and its last line; n, order, leaves (the run's open leaves), on_record (those the driver's journal
    held closed) and processes, from its start line; starts, the time each leaf (by its index into the open leaves)
    started; dones, (the time, whether its tree closed) of each leaf done; outcome, its final line (ALL ... LEAVES
    CLOSED, NOT FINISHED or a witness), as the log has it, after the time, else None.  Every line must have exactly
    one known form, every pass must begin with a start line, no line may follow its outcome but the next start line,
    and a leaf is done only after it started in the pass (all asserted)."""
    passes = []
    for line in lines:
        forms = [(kind, m) for kind, form in BOX_FORMS.items() if (m := form.match(line))]
        # TODO: error copy; says a line of the driver's log has none of the forms progress.py knows, quoting the line
        assert len(forms) == 1, f'Claude: "a boxsplit log line of no known form: {line}"'
        kind, m = forms[0]
        t = stamp(m[1])
        if kind == 'start':
            passes.append({'start': t, 'n': int(m[2]), 'order': int(m[3]), 'leaves': int(m[4]), 'on_record': int(m[5]),
                           'processes': int(m[6]), 'starts': {}, 'dones': {}, 'outcome': None})
        # TODO: error copy; says a line of the driver's log comes before any start line or after its pass's outcome line, quoting it
        assert passes and passes[-1]['outcome'] is None, f'Claude: "a boxsplit log line out of place: {line}"'
        p = passes[-1]
        p['last'] = t
        if kind == 'leaf': p['starts'][int(m[2])] = t
        if kind == 'done':
            assert int(m[2]) in p['starts'], line
            p['dones'][int(m[2])] = (t, m[3] == 'closed')
        if kind == 'outcome': p['outcome'] = m[2]
    return passes


def driver_leaves(main):
    """The leaves boxsplit.py's driver works for the run whose journal is main, as nodes, in the driver's order: the
    run's open leaves (boxsplit.open_leaves': the keys at the cascade's bottom, one vector per modulus, whose latest
    verdict is UNKNOWN) and those a handoff has closed since (CLOSED there, which overnight_v5 never writes at the
    bottom: its CLOSED records are for nodes with children), in the order of their latest records, which a handoff
    keeps (scratch/boxsplit-240/handoff.py appends them in the open leaves' order).  dreeves, 2026-10-20: 240@11's
    handoff closed its 606 leaves, and the watcher, taking the open ones alone, found none for the driver's log."""
    journal = v5.Journal(main)
    latest = {json.loads(line)['key']: i for i, line in enumerate(open(main).read().splitlines()[1:])}
    keys = [k for k, rec in journal.records.items()
            if rec['verdict'] in ('UNKNOWN', 'CLOSED') and len(k.split()) == len(v5.CASCADE) and '#' not in k]
    return [bx.parse_key(k) for k in sorted(keys, key=latest.get)]


def survey_box(n, order, log, main, procs, now, etas):
    """The boxsplit pass of the run (n, order) as the driver's log, the run's journal (main, whose open leaves the
    driver works), the process list and the time now show it, in survey's shape: program boxsplit.py, its state, its
    seconds of running (its passes'), its estimate (to_go; see below) and record of ETAs (etas, to which this snapshot's
    goes, as survey's), and its sea: one dot per open leaf, grouped and ordered as survey's sea, running if it started
    in the current pass of a running driver and is not done in it, else settled or open as its latest line saying it is
    done says its tree closed or not, else pending.  The log alone says all this, every pass's lines kept; the driver's
    journal is not read: the driver writes a leaf's done line and then its CLOSED record, so a reader of both could see
    the one without the other (the watcher's crash of 2026-10-17 16:03).
    The estimate: an urn (see the vocabulary) of the wall seconds, start to done, of every leaf done in the current
    pass (an earlier pass did other work: 240@11's second pass split by 19 the nodes its first left open by 17), its new
    ball lindy_ball's Lindy tail above the longest time seen in the pass, done or still running (a leaf's tree has no
    budget to bound it); each running leaf drawn above its elapsed seconds (censored, the longest-running first),
    holding its worker for the rest; each pending leaf a job in the driver's order (its key's sha1); makespan on the
    pass's workers.  With no leaf of the pass done, every draw is the new ball: Gott's rule.  None when the driver is not
    running or no leaf of the pass has begun."""
    bx.configure(n, order)
    saved = v5.JOURNAL
    v5.JOURNAL = main
    try:
        leaves = [v5.node_key(nd) for nd in driver_leaves(main)]
    finally:
        v5.JOURNAL = saved
    passes = parse_box_lines(complete_lines(log))
    p = passes[-1]
    # TODO: error copy; says the driver's log's last start line names another length, order or count of open leaves than the run's journal
    assert (p['n'], p['order'], p['leaves']) == (n, order, len(leaves)), f'Claude: "the boxsplit log of {n} {order} does not match its run"'
    state = run_state(procs, 'boxsplit.py', n, order, p['outcome'])
    end = now if state == 'running' else max([p['last'], *map(float, etas)])   # every ETA is recorded while it runs
    spans = [(q['start'], q['last']) for q in passes[:-1]] + [(p['start'], end)]
    done = {i: ok for q in passes for i, (_, ok) in q['dones'].items()}    # each leaf's latest: did its tree close
    running = {i: t for i, t in p['starts'].items() if i not in p['dones'] and state == 'running'}

    def status(i):
        if i in running: return 'running'
        if i in done: return 'settled' if done[i] else 'open'
        return 'pending'

    groups = {}
    for i in sorted(range(len(leaves)), key=lambda i: tree_order(leaves[i])):
        groups.setdefault(' '.join(leaves[i].split()[:SEA_DEPTH]), []).append(str(SEA_STATUSES.index(status(i))))
    tally = collections.Counter(c for g in groups.values() for c in g)
    sea = {'depth': SEA_DEPTH, 'keys': list(groups), 'groups': [''.join(g) for g in groups.values()],
           'counts': {s: tally[str(i)] for i, s in enumerate(SEA_STATUSES)}}
    walls = np.array([t - p['starts'][i] for i, (t, _) in p['dones'].items()], dtype=float)   # the pass's done leaves
    ages = sorted((now - t for t in running.values()), reverse=True)  # its running leaves', the longest-running first
    top = max([*walls, *ages], default=0.0)                          # the longest time seen in the pass
    draws = None
    if state == 'running' and top > 0:
        rng = np.random.default_rng(SEED)
        todo = sorted((i for i in range(len(leaves)) if status(i) == 'pending'),
                      key=lambda i: hashlib.sha1(leaves[i].encode()).hexdigest())
        urn = Urn(rng, walls, lindy_ball(rng, top), len(running) + len(todo))
        loads = np.zeros((REPLICATES, p['processes']))
        for j, e in enumerate(ages):
            loads[:, j] = urn.draw(e) - e
        draws = makespan(loads, [('job', urn.draw()) for _ in todo]) / HOUR
    etas.setdefault(str(int(end)), [float(np.median(draws))] + [float(q) for q in np.quantile(draws, QUANTILES)] if draws is not None else None)   # a record made stands
    to_go = ({'median': float(np.median(draws)) * HOUR} | dict(zip(('lo', 'hi'), (float(q) * HOUR for q in np.quantile(draws, QUANTILES))))
             if draws is not None else None)
    return {'program': 'boxsplit.py', 'n': n, 'order': order, 'state': state, 'outcome': p['outcome'],
            'so_far': sum(b - a for a, b in spans), 'to_go': to_go, 'passes': spans, 'etas': etas, 'sea': sea}


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


# ---------- the data file ----------

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
    seconds) and, per run, program (overnight_v5.py or boxsplit.py), n, order, state, so_far (its passes' seconds of running), to_go ({median, lo, hi}, seconds of
    running: the estimate's median and QUANTILES; null without one), etas (its record of ETAs, eta_records, as [time,
    running seconds before it, median (mean before 2026-10-19), lo, hi], the time in whole seconds and the rest in seconds to a tenth, evenly thinned to at most ETA_POINTS, the last kept), statuses
    (SEA_STATUSES) and its sea (depth, keys, groups, counts)."""
    def etas(s):
        rs = eta_records(s)
        keep = sorted(set(range(0, len(rs), max(1, -(-len(rs) // ETA_POINTS)))) | {len(rs) - 1}) if rs else []
        return [[int(rs[i][0])] + [round(HOUR * v, 1) for v in rs[i][1:]] for i in keep]
    runs = [{'program': s['program'], 'n': s['n'], 'order': s['order'], 'state': s['state'], 'so_far': s['so_far'], 'to_go': s['to_go'],
             'etas': etas(s), 'statuses': list(SEA_STATUSES)} | s['sea'] for s in surveys]
    return 'progressData(' + json.dumps({'made': int(now), 'runs': runs}, separators=(',', ':'), ensure_ascii=False) + ');\n'


def load_cache(path): return json.load(open(path)) if os.path.exists(path) else {}
def save_cache(path, cache): write_atomic(path, json.dumps(cache, sort_keys=True))


def main(argv):
    # TODO: error copy; says how to run the script: with no argument to write the data file once, or with --watch to keep rewriting it
    assert argv in ([], ['--watch']), 'Claude: "usage: python3 -B progress.py [--watch]"'
    os.nice(max(0, NICE - os.nice(0)))
    while True:
        cache, procs, now = load_cache(CACHE), processes(), time.time()
        surveys = [survey(n, order, *files(n, order), procs, now, cache.setdefault(f'{n}_{order}_{v5.CODE}', {}),
                          cache.setdefault(f'{n}_{order}_{v5.CODE}_etas', {})) for n, order in RUNS]
        surveys += [survey_box(n, order, *box_files(n, order), procs, now,
                               cache.setdefault(f'{n}_{order}_boxsplit_{bx.CODE}_etas', {})) for n, order in EXTENDED]
        write_atomic(JS, js_text(surveys, now))
        save_cache(CACHE, cache)
        if not argv: return
        time.sleep(REFRESH)


if __name__ == '__main__':
    main(sys.argv[1:])
