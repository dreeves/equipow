#!/usr/bin/env python3
"""A page showing how far the certified searches of overnight_v5.py have got.

Run:   python3 -B progress.py            writes progress.html once
       python3 -B progress.py --watch    rewrites it every REFRESH seconds until stopped
Either way the process first lowers its priority to nice NICE.  progress.html, next to this file, is one
self-contained page (its only fetches are Google Fonts, as index.html's), reloads itself every REFRESH seconds, and is
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
              which search() writes just after it; a CLOSED record by the line of the record before it (every CLOSED
              record follows a fresh record of its own pass: in a later pass, nothing closes until a re-solved leaf
              settles).  So the journal as of any line is the records dated by it or earlier (see read_run).
  estimate    of a running or frozen run: REPLICATES draws of the current pass's remaining hours of running, from the
              model below; or none, when the model has nothing to draw from.  The page gives their mean (the ETA) and
              their QUANTILES (the band around it).  Provisional (2026-10-09): the survival-analysis
              design of the workflow in scratch/eta-dist/, ported whole, while that workflow's judges are still out.
  ETA         the mean of a snapshot's estimate (dreeves's name for it): E[hours of running until the current pass
              ends], which is when the search ends, unless the pass leaves sub-cases open, as 304@9's first did; no
              estimate foresees a later pass.  Each time the page is made it records its ETA with the estimate's range
              (its draws' QUANTILES), by the snapshot's time, in CACHE (by run and overnight_v5.CODE), and its ETA chart
              draws that record, the range as a shaded band: only ETAs the page actually made, none reconstructed for
              times before the record began (dreeves, 2026-10-09), against the search's elapsed running time, whatever
              its passes (dreeves, 2026-10-10).
The estimate's model, its terms defined once here (overnight_v5.py's search() is the process it models):
  bottom      the depth of the cascade's last level, len(budgets) - 1; a node there is a job of one certbb solve.
  replay      search()'s stack and running jobs as of the state's time t, rebuilt from the current pass's progress
              lines.  Each line says which node finished, and its counts give how many jobs were submitted before it
              (its running + 1 - the previous line's running) and how many children it pushed: the cache's, if the
              node's split is cached; none, if the node cannot split (INFEASIBLE, or at the bottom); else its waiting +
              running - (the previous line's waiting + running) + 1, which holds when no settled node is skipped (a
              first pass skips none; asserted).  A job submitted after line i started at line i's time; the first job
              started at its own end less its duration.  Every line's waiting and running are asserted against the
              replayed stack and running jobs.
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
It says exactly how old the snapshot is: the time it was
made, and a running age that its one script keeps up to date.  For each run it gives this pass's work at the estimate's
level, how the pass ended once it has, its ETA chart (which conveys everything the page once said in words, its
timeline and its density: dreeves, 2026-10-10), and, in a details element, the passes, the levels, two charts and the
open leaves.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, html, math, bisect, itertools, subprocess, collections
import numpy as np
import overnight_v5 as v5

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, 'progress.html')
CACHE = os.path.join(HERE, '.progress_cache.json')
RUNS = ((304, 9), (240, 11))           # the certified runs, (N, ORDER), in the page's order
REFRESH = 60                           # seconds between rewrites under --watch, and between the page's reloads
NICE = 15                              # the niceness the process lowers itself to
# The deepest level enumerated.  Splitting cost the runs themselves (their logs' split seconds, on loaded workers)
# under 4 s per node on average down to depth 5, but 6.4 s at depth 6 of 240@11 (up to 51 s).  Levels 0..6 need
# splits down to depth 5 only; 304@9's bottom is level 6.
DEEPEST = 6
REPLICATES = 2000                      # draws in an estimate: a Monte Carlo precision setting
SEED = 0                               # the estimate's random generator's seed: an estimate is a function of its state
QUANTILES = (0.1, 0.9)                 # the estimate's range, the ETA's band: the middle 80% of its draws
HOUR = 3600                            # seconds
STATUSES = ('settled', 'open', 'split', 'pending')     # the order of the page's columns, bars and legend


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
                        r'\[([\d, ]+)\], (\d+) earlier verdicts"$'),
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
                           'nodes': [], 'opens': [], 'outcome': None})
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


def run_state(procs, n, order, outcome):
    """The run's state (see the vocabulary), from the process list and the current pass's outcome line (or None)."""
    main = [p for p in procs if re.search(rf'(?:^|[\s/])overnight_v5\.py {n} {order}\s*$', p[3])]
    # TODO: error copy; says several processes run this search at once, giving how many, the length and the order
    assert len(main) <= 1, f'Claude: "{len(main)} processes run overnight_v5.py {n} {order}"'
    mine = main + [p for p in procs if p[1] in {q[0] for q in main}]
    return ('ended' if outcome is not None or not main else
            'frozen' if any(p[2].startswith('T') for p in mine) else 'running')


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
    asserted).  The log is read first: each record is written before its line, so every line read has its record in
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
    replayed = object.__new__(v5.Journal)          # made without Journal's __init__, which would create a journal
    replayed.records = {}
    fresh, dates = {}, []

    def admit(line):                               # the next record, dated by this line
        assert line is not None
        replayed.admit(records[len(dates)])
        dates.append(line)

    def closings():                                # the CLOSED records next in the journal, dated by the last record's line
        while len(dates) < len(records) and records[len(dates)]['verdict'] == 'CLOSED': admit(dates[-1] if dates else None)

    for p, indices in zip(passes, node_lines):
        for i, nd in zip(indices, p['nodes']):
            budget = budget_of(nd['key'], p['budgets'])
            prev = replayed.records.get(nd['key'], {'verdict': 'UNKNOWN', 'budget': -1})
            assert prev['verdict'] == 'UNKNOWN', (log, i)                # search() never submits a settled node
            if prev['budget'] >= budget:                                 # split again, with no fresh record
                assert nd['verdict'] == 'UNKNOWN', (log, i)
                continue
            closings()
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
    level counts its sub-cases; a deeper one counts the journal's keys at its depth, its pending count unknown
    (None).  Every journal key at an enumerated depth must be a sub-case of that level (asserted)."""
    keyed = collections.defaultdict(list)
    for k in final: keyed[len(k.split())].append(k)
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
    parent and depth, kids (in split order), state ('pending' in the stack, 'running', 'done' with a progress line, or
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
    w, r, at = 1, 0, None              # the previous line's waiting and running (before the first: the top node, 0)

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
        splits = nd['verdict'] == 'UNKNOWN' and len(nd['key'].split()) < len(budgets) - 1
        kids = cache[nd['key']] if nd['key'] in cache else None
        K = len(kids) if kids is not None else nd['waiting'] + nd['running'] - w - r + 1 if splits else 0
        skip = w - submit + K - nd['waiting']
        # TODO: error copy; says the replay of search() cannot account for a progress line's counts, naming the state and the line
        assert submit >= 0 and K >= 0 and skip >= 0 and (kids is not None or not splits or skip == 0), \
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
        w, r, at = nd['waiting'], nd['running'], nd['t']
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
                node.kids = [Node(c, node, node.depth + 1) for c in state['cache'].get(node.key, [])]
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

def series(passes, end):
    """The page's charts' data: for each pass, its points (x, y) of settled (INFEASIBLE progress lines so far, over
    all passes) and of open (the log's count in that pass), x the seconds of running over all passes, a pass's
    running time running from its start line to its last line (to end, for the current pass); the passes' boundaries;
    and the span of x."""
    settled, offset, out = 0, 0.0, {'settled': [], 'open': [], 'bounds': []}
    for p, e in zip(passes, [q['last'] for q in passes[:-1]] + [end]):
        s_pts, o_pts = [(offset, settled)], [(offset, 0)]
        for nd in p['nodes']:
            settled += nd['verdict'] == 'INFEASIBLE'
            s_pts.append((offset + nd['t'] - p['start'], settled))
            o_pts.append((offset + nd['t'] - p['start'], nd['open']))
        out['settled'].append(s_pts)
        out['open'].append(o_pts)
        out['bounds'].append(offset)
        offset += e - p['start']
    out['bounds'] = out['bounds'][1:]
    out['span'] = offset
    return out


def survey(n, order, journal, log, procs, now, cache, etas):
    """Everything the page shows of the run (n, order), from its journal and log, the process list and the time now
    (epoch seconds); cache holds the run's splits (see children), etas its record of ETAs (see the vocabulary), to
    which this snapshot's is added: [the mean of its draws, then their QUANTILES], None with none (an ended run has
    none), by its time in whole seconds."""
    v5.configure(n, order)
    R = read_run(journal, log)
    passes = R['passes']
    p = passes[-1]
    # TODO: error copy; says the log's last start line names another length, order, cascade or pool budget than overnight_v5's settings for this run
    assert (p['n'], p['order'], p['moduli'], p['pool_budget']) == (n, order, list(v5.CASCADE), v5.POOL_BUDGET), f'Claude: "the log of {n} {order} does not match overnight_v5.py"'
    budgets, bottom = p['budgets'], len(v5.CASCADE)
    assert len(budgets) == bottom + 1
    final = {r['key']: r for r in R['records']}
    state = run_state(procs, n, order, p['outcome'])
    end = now if state == 'running' else p['last']
    levels = enumerate_levels(final, budgets, order, cache, DEEPEST)
    rows = level_rows(levels, final, budgets, bottom)
    for r in rows: r['modulus'] = ([None] + list(v5.CASCADE))[r['depth']]
    stats = {k: status(k, final, budgets) for k in set(final) | set(levels[-1])}
    tally = collections.Counter(stats[k] for k in final)
    last = (p['nodes'] or [{'t': None, 'waiting': None, 'running': None}])[-1]
    opens = sorted(((k, r['budget'], stats[k]) for k, r in final.items() if r['verdict'] == 'UNKNOWN' and leaf(k, bottom)),
                   key=lambda x: parse_key(x[0]))
    spans = [(q['start'], q['last']) for q in passes[:-1]] + [(p['start'], end)]
    draws = estimate(state_at(R, end, cache, f'{n}@{order} at {clock(end)}')) if state != 'ended' else None
    etas[str(int(end))] = [float(draws.mean())] + [float(q) for q in np.quantile(draws, QUANTILES)] if draws is not None and len(draws) else None
    return {'n': n, 'order': order, 'state': state, 'outcome': p['outcome'], 'budgets': budgets,
            'passes': spans,
            'elapsed': end - p['start'], 'last': p['last'],
            'settled': sum(r['verdict'] == 'INFEASIBLE' for r in final.values()), 'open': tally['open'],
            'split': tally['split'], 'line': last['t'], 'waiting': last['waiting'], 'running': last['running'],
            'levels': rows, 'deepest': len(levels) - 1,
            'processes': p['processes'],
            'work': work(levels[-1], len(levels) - 1, stats, p['nodes']) if state != 'ended' else None,
            'draws': draws, 'etas': etas, 'series': series(passes, end), 'open_list': opens}


# ---------- the page ----------

def num(x): return '—' if x is None else f'{x:,}'
def hours(sec): return f'{sec / 3600:.1f}'
def clock(t): return '—' if t is None else time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))
def duration(sec):
    """A length of time as days, hours, minutes and seconds, all four always given; the page's script writes the
    snapshot's age the same way."""
    sec = int(sec)
    return f'{sec // 86400} d {sec % 86400 // 3600} h {sec % 3600 // 60} min {sec % 60} s'
def unattributed(line):
    """A log line's text without the Claude: \"...\" quotation that overnight_v5.py wraps it in (asserted)."""
    m = re.fullmatch(r'Claude: "(.*)"', line)
    assert m, line
    return m[1]
def sw(kind): return f"<span class='sw {kind}'></span>"   # single quotes, so it can sit inside copy


def thin(points, most=300):
    """At most about most points, evenly picked, the last always kept."""
    return points[::max(1, len(points) // most)] + points[-1:]


def nice_ceiling(y):
    """The least round number (1, 1.5, 2, 2.5, 3, 4, 5, 6 or 8 times a power of 10, or the next power) that is at least
    y and at least 1; y is a whole number, so the result is too."""
    k = 10 ** (len(str(max(1, int(y)))) - 1)
    return next(round(m * k) for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10) if m * k >= y)


def key_html(parts, same=0):
    """A key's constraints, each kept on one line, the first same of them (shared with the key above) faded."""
    return ' '.join(f'<span class="part{" same" if i < same else ""}">{part}</span>' for i, part in enumerate(parts))


def chart(lines, bounds, span, title):
    """An SVG line chart: one polyline per pass, against seconds of running from 0 to span, with the passes'
    boundaries as hairlines, ticks at 0 and the top, and the last value at the line's end."""
    W, H, L, R, T, B = 320, 132, 44, 8, 18, 20
    top = nice_ceiling(max(y for pts in lines for _, y in pts))
    def X(x): return L + (W - L - R) * x / max(span, 1)
    def Y(y): return H - B - (H - T - B) * y / top
    x1, y1 = lines[-1][-1]
    return (f'<figure class="chart"><figcaption>{title}</figcaption><svg viewBox="0 0 {W} {H}">'
            f'<line class="grid" x1="{L}" y1="{Y(top):.1f}" x2="{W - R}" y2="{Y(top):.1f}"/>'
            f'<line class="axis" x1="{L}" y1="{Y(0):.1f}" x2="{W - R}" y2="{Y(0):.1f}"/>'
            + ''.join(f'<line class="pass" x1="{X(b):.1f}" y1="{T}" x2="{X(b):.1f}" y2="{Y(0):.1f}"/>' for b in bounds)
            + ''.join(f'<polyline class="line" points="{" ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in thin(pts))}"/>'
                      for pts in lines)
            + f'<text class="tick" x="{L - 6}" y="{Y(top) + 4:.1f}" text-anchor="end">{top:,}</text>'
            f'<text class="tick" x="{L - 6}" y="{Y(0) + 4:.1f}" text-anchor="end">0</text>'
            f'<text class="tick" x="{L}" y="{H - 4}">0</text>'
            f'<text class="tick" x="{W - R}" y="{H - 4}" text-anchor="end">{hours(span)} h</text>'
            f'<text class="end" x="{X(x1):.1f}" y="{Y(y1) - 6:.1f}" text-anchor="end">{y1:,}</text>'
            '</svg></figure>')


def levels_html(s):
    """The levels: a header of swatches, then per level its number, modulus, counts and (enumerated) bar."""
    def cells(r):
        c = r['counts']
        bar = ''.join(f'<span class="seg {k}" style="flex-grow:{c[k]}"></span>' for k in STATUSES if r['enumerated'] and c[k])
        return (f'<div class="lv{"" if r["enumerated"] else " journal"}"><span class="d">{r["depth"]}</span>'
                f'<span class="m">{num(r["modulus"])}</span>' + ''.join(f'<span class="n">{num(c[k])}</span>' for k in STATUSES)
                + f'<span class="barcell"><span class="bar">{bar}</span></span></div>')
    head = ('<div class="lv head"><span class="d"></span><span class="m"><i>M</i></span>'
            + ''.join(f'<span class="n">{sw(k)}</span>' for k in STATUSES) + '<span class="barcell"></span></div>')
    return f'<div class="levels">{head}<span class="rule"></span>{"".join(cells(r) for r in s["levels"])}</div>'


def work_html(s):
    """This pass's sub-cases at the deepest enumerated level (see work): a bar of the done, partway and pending ones,
    and how many are done; nothing for an ended run."""
    e = s['work']
    if e is None: return ''
    bar = ''.join(f'<span class="seg {k}" style="flex-grow:{n}"></span>'
                  for k, n in (('settled', e['done']), ('split', e['progress']), ('pending', e['pending'])) if n)
    # TODO: how many of this pass's sub-cases at the estimate's level are done, of how many
    return f'<div class="work"><span class="bar">{bar}</span><span class="count">{num(e["done"])} / {num(e["work"])} done</span></div>'


def eta_chart(s):
    """The run's ETA chart (see ETA in the vocabulary), the chart dreeves asked for, which knows nothing of passes:
    against the search's elapsed running time (hours, over all passes), the elapsed time itself (blue, the diagonal),
    the recorded ETAs (red; one with no estimate left out) over the shaded band of their ranges, and elapsed + ETA
    (black, emphasized); at the last ETA, a vertical line across its range and markers on the red and black lines, so
    that a record of one ETA shows too, and the blue line carried on ahead, dashed, to where it is level with the black
    marker (dreeves, 2026-10-10), the x axis reaching that far; a cross line at the last ETA; ticks at 0 and the top of
    each axis; then the readout, the last ETA's numbers, which the page's script changes to those of the ETA nearest
    the pointer (data-points holds every ETA's x and numbers); then a legend in dreeves's words.  A recorded time's
    elapsed running time comes from the passes it falls in, which it must (asserted)."""
    W, H, L, R, T, B = 640, 200, 44, 14, 12, 22
    spans = s['passes']
    starts = [a for a, _ in spans]
    before = list(itertools.accumulate((b - a for a, b in spans), initial=0.0))   # running seconds before each pass
    def elapsed(t):                                               # the running hours before time t, a recorded time
        k = bisect.bisect_right(starts, t) - 1
        # TODO: error copy; says the record of ETAs holds a time when the search was not running
        assert k >= 0 and t <= spans[k][1], f'Claude: "the ETA of {clock(t)} falls when {s["n"]} {s["order"]} was not running"'
        return (before[k] + t - starts[k]) / HOUR
    records = [(t, elapsed(t), *e) for t, e in sorted((float(t), e) for t, e in s['etas'].items()) if e is not None]
    points = [(x, m, lo, hi) for _, x, m, lo, hi in records]
    xtop = max([before[-1] / HOUR] + [x + m for x, m, _, _ in points[-1:]])     # now, or the last ETA's projected finish
    ytop = nice_ceiling(max([xtop] + [max(x + m, hi) for x, m, _, hi in points]))
    def X(x): return L + (W - L - R) * x / max(xtop, 1 / HOUR)           # an axis at least one second long, as chart's
    def Y(y): return H - B - (H - T - B) * y / ytop
    def line(cls, pts): return f'<polyline class="{cls}" points="{" ".join(f"{X(x):.2f},{Y(y):.2f}" for x, y in pts)}"/>'
    band = f'<polygon class="band" points="{" ".join(f"{X(x):.2f},{Y(y):.2f}" for x, y in [(x, hi) for x, _, _, hi in points] + [(x, lo) for x, _, lo, _ in reversed(points)])}"/>'
    ahead = ''.join(f'<line class="ahead" x1="{X(x):.2f}" y1="{Y(x):.2f}" x2="{X(x + m):.2f}" y2="{Y(x + m):.2f}"/>'
                    for x, m, _, _ in points[-1:])
    cross = ''.join(f'<line class="cross" x1="{X(x):.2f}" y1="{Y(ytop):.2f}" x2="{X(x):.2f}" y2="{Y(0):.2f}"/>' for x, _, _, _ in points[-1:])
    # TODO: the numbers of one recorded ETA: when it was made, to the minute; the elapsed time then; the ETA and its range; elapsed + ETA; in hours, labeled in dreeves's words
    entries = [{'x': float(f'{X(x):.2f}'), 'text': f'{time.strftime("%Y-%m-%d %H:%M", time.localtime(t))} · elapsed {x:.1f} h · '
                f'ETA {m:.1f} h ({lo:.1f}–{hi:.1f}) · elapsed + ETA {x + m:.1f} h'} for t, x, m, lo, hi in records]
    readout = ''.join(f'<p class="readout">{html.escape(e["text"], quote=False)}</p>' for e in entries[-1:])
    now = ''.join(f'<line class="range" x1="{X(x):.2f}" y1="{Y(lo):.2f}" x2="{X(x):.2f}" y2="{Y(hi):.2f}"/>'
                  f'<circle class="now togo" cx="{X(x):.2f}" cy="{Y(m):.2f}" r="3.5"/>'
                  f'<circle class="now total" cx="{X(x):.2f}" cy="{Y(x + m):.2f}" r="3.5"/>' for x, m, lo, hi in points[-1:])
    # TODO: the three series' names, dreeves's own words (2026-10-09): elapsed time, ETA, and their sum
    keys = ''.join(f'<span class="k"><span class="key {k}"></span>{label}</span> ' for k, label in
                   (('spent', 'elapsed time'), ('togo', 'ETA'), ('total', 'elapsed + ETA')))
    return (f'<figure class="forecast-fig" data-points="{html.escape(json.dumps(entries, ensure_ascii=False), quote=True)}">'
            f'<svg class="forecast" viewBox="0 0 {W} {H}">'
            f'<line class="grid" x1="{L}" y1="{Y(ytop):.2f}" x2="{W - R}" y2="{Y(ytop):.2f}"/>'
            f'<line class="axis" x1="{L}" y1="{Y(0):.2f}" x2="{W - R}" y2="{Y(0):.2f}"/>'
            + band + line('spent', [(0, 0), (before[-1] / HOUR,) * 2]) + ahead + line('togo', [(x, m) for x, m, _, _ in points])
            + line('total', [(x, x + m) for x, m, _, _ in points])
            + now + cross
            + f'<text class="tick" x="{L - 6}" y="{Y(ytop) + 4:.2f}" text-anchor="end">{ytop:,} h</text>'
            f'<text class="tick" x="{L - 6}" y="{Y(0) + 4:.2f}" text-anchor="end">0</text>'
            f'<text class="tick" x="{L}" y="{H - 4}">0</text>'
            f'<text class="tick" x="{W - R}" y="{H - 4}" text-anchor="end">{hours(xtop * HOUR)} h</text>'
            f'</svg>{readout}<figcaption class="keys">{keys}</figcaption></figure>')


def opens_html(s):
    """The leaves whose last verdict is UNKNOWN, under their parents (the key less its last constraint), each with its
    status's swatch: open, or pending (to be solved again in this pass), in gray."""
    groups = collections.defaultdict(list)
    for key, _, st in s['open_list']: groups[' '.join(key.split()[:-1])].append((key.split()[-1], st))
    items, above = [], []
    for parent, leaves in groups.items():
        parts = parent.split()
        items.append(f'<li><code class="parent">{key_html(parts, len(os.path.commonprefix([parts, above])))}</code><ul>'
                     + ''.join(f'<li class="{st}">{sw(st)} <code>{key_html([last])}</code></li>' for last, st in leaves) + '</ul></li>')
        above = parts
    return f'<ul class="opens">{"".join(items)}</ul>'


def details_html(s):
    """The run's details, shown on request: its passes, its levels, its two charts and its open leaves."""
    # TODO: one line per pass: its number, its start, the end of its running (its last log line, or the snapshot's time while it runs) and its hours
    passes = '<br>'.join(f'pass {i} · {clock(a)} → {clock(b)} · {hours(b - a)}\u00a0h' for i, (a, b) in enumerate(s['passes'], 1))
    # TODO: the statuses' swatches, each with its name: settled, open, split, pending
    legend = ''.join(f'<span>{sw(k)}\u00a0{k}</span>' for k in STATUSES)
    sr = s['series']
    # TODO: title of the chart of sub-cases settled by a certificate, against hours of running over all passes
    c1 = chart(sr['settled'], sr['bounds'], sr['span'], 'settled')
    # TODO: title of the chart of open leaves (the log's count, which starts again at 0 in each pass), against hours of running over all passes
    c2 = chart(sr['open'], sr['bounds'], sr['span'], 'open')
    # TODO: the summary of the details element that holds the rest of what the page knows about the run
    return (f'<details><summary>details</summary><div class="more"><p class="passes">{passes}</p>'
            f'<p class="legend">{legend}</p>{levels_html(s)}<div class="charts">{c1}{c2}</div>{opens_html(s)}</div></details>')


def run_html(s):
    """One run's section: its question and state; this pass's work; how the pass ended, once it has; its ETA chart;
    its details."""
    states = {
        # TODO: state of a run whose process is at work
        'running': 'running',
        # TODO: state of a run whose process, or one of its workers, is stopped (as by SIGSTOP)
        'frozen': 'frozen',
        # TODO: state of a run with no process, or whose current pass has logged how it ended
        'ended': 'ended',
    }
    glyph = {'running': '●', 'frozen': '❚❚', 'ended': '■'}[s['state']]
    outcome = f'<p class="outcome">{html.escape(unattributed(s["outcome"]), quote=False)}</p>' if s['outcome'] else ''
    return (f'<section class="run"><div class="run-head"><h2><i>m</i><sup>*</sup>({s["n"]}) ≥ {s["order"]}?</h2>'
            f'<span class="state {s["state"]}"><span aria-hidden="true">{glyph}</span> {states[s["state"]]}</span></div>'
            f'{work_html(s)}{outcome}{eta_chart(s)}{details_html(s)}</section>')


SCRIPT = """
// The page's one script.  First the snapshot's age, written as duration() in progress.py writes a length of time.
// Clocks that disagree by a moment could make it negative; it is shown as 0 s then.
const age = document.getElementById('age'), made = Number(age.dataset.made);
function tick() {
  const s = Math.max(0, Math.floor((Date.now() - made) / 1000));
  age.textContent = `${Math.floor(s / 86400)} d ${Math.floor(s % 86400 / 3600)} h ${Math.floor(s % 3600 / 60)} min ${s % 60} s`;
}
tick();
setInterval(tick, 1000);
// Then each ETA chart's readout: when a pointer moves or presses (a touch) over the chart, the recorded ETA nearest it
// in elapsed time gets the cross line, and its numbers go under the chart.  A chart with no recorded ETA has none.
for (const fig of document.querySelectorAll('.forecast-fig')) {
  const points = JSON.parse(fig.dataset.points);
  if (!points.length) continue;
  const svg = fig.querySelector('svg'), cross = svg.querySelector('.cross'), out = fig.querySelector('.readout');
  function show(e) {
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * svg.viewBox.baseVal.width;
    const p = points.reduce((a, b) => Math.abs(b.x - x) < Math.abs(a.x - x) ? b : a);
    cross.setAttribute('x1', p.x);
    cross.setAttribute('x2', p.x);
    out.textContent = p.text;
  }
  svg.addEventListener('pointermove', show);
  svg.addEventListener('pointerdown', show);
}
"""


STYLE = """
/* Layout: index.html's journal-page column, its fonts, colors and tokens; one section per run. */
:root {
  --paper: #ffffff;
  --ink: #1b1d22;
  --muted: #596070;
  --rule: #1b1d22;
  --serif: "STIX Two Text", "Times New Roman", Times, serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #16171b;
    --ink: #e9e7e2;
    --muted: #a2a6b0;
    --rule: #c9c7c2;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #16171b;
  --ink: #e9e7e2;
  --muted: #a2a6b0;
  --rule: #c9c7c2;
  color-scheme: dark;
}
/* The statuses, by how finished a sub-case is: one ink ramp, darkest (in dark mode, brightest) for settled. */
:root {
  --settled: var(--ink);
  --open: var(--muted);
  --split: color-mix(in oklab, var(--ink) 38%, var(--paper));
  --pending: color-mix(in oklab, var(--ink) 11%, var(--paper));
  --hair: color-mix(in oklab, var(--rule) 30%, var(--paper));
}

* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 1.0625rem;
  line-height: 1.5;
}
main {
  max-width: 48rem;
  margin: 0 auto;
  padding-block: 2.5rem 3rem;
  padding-inline: max(1rem, env(safe-area-inset-left, 0px));
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 2.25rem;
}
header { display: grid; gap: 0.5rem; max-width: 42rem; }
h1 { margin: 0; font-size: 2rem; font-weight: 600; line-height: 1.15; text-wrap: balance; }
h2 { margin: 0; font-size: 1.5rem; font-weight: 600; }
p { margin: 0; }
sup { line-height: 0; }
b { font-weight: 600; }
code { font-family: var(--mono); font-size: 0.8125rem; overflow-wrap: anywhere; }
.work, .passes, .levels, .charts { font-variant-numeric: tabular-nums lining-nums; }

.run {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.8rem;
  padding-top: 1.75rem;
  border-top: 1px solid var(--hair);
}
.run-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.3rem 1rem; }
.state {
  font-size: 0.875rem;
  padding: 0.05rem 0.6rem;
  border: 1px solid var(--rule);
  border-radius: 999px;
  white-space: nowrap;
}
.state.ended { color: var(--muted); border-color: var(--hair); }
.stale { border-left: 3px solid var(--ink); padding-left: 0.75rem; }
#age { white-space: nowrap; }
.outcome { font-size: 0.9375rem; border-left: 3px solid var(--rule); padding-left: 0.75rem; }
.legend, .passes { font-size: 0.9375rem; }
.legend { display: flex; flex-wrap: wrap; gap: 0.2rem 1.1rem; }

/* The three series of the ETA chart, in the colors dreeves named: the categorical palette's blue and red (the pair
   validated for color-vision deficiency, light and dark), and ink, wider, for the sum he asked to be emphasized. */
:root { --c-spent: #2a78d6; --c-togo: #e34948; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --c-spent: #3987e5; --c-togo: #e66767; } }
:root[data-theme="dark"] { --c-spent: #3987e5; --c-togo: #e66767; }

.work { display: flex; align-items: center; gap: 0.75rem; font-size: 0.9375rem; }
.work .bar { flex: 1 1 auto; }
.count { white-space: nowrap; color: var(--muted); }

/* The ETA chart (class forecast): elapsed time, ETA, and elapsed + ETA, emphasized, against elapsed time. */
.forecast-fig { margin: 0; display: grid; gap: 0.3rem; }
.forecast { display: block; width: 100%; height: auto; overflow: visible; cursor: crosshair; touch-action: pan-y; }
.forecast polyline { fill: none; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.forecast .spent { stroke: var(--c-spent); stroke-width: 1.5; }
.forecast .togo { stroke: var(--c-togo); stroke-width: 1.5; }
.forecast .total { stroke: var(--ink); stroke-width: 3; }
.forecast .band { fill: color-mix(in oklab, var(--c-togo) 16%, var(--paper)); stroke: none; }
.forecast .range { stroke: var(--c-togo); stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast .ahead { stroke: var(--c-spent); stroke-width: 1.5; stroke-dasharray: 5 4; vector-effect: non-scaling-stroke; }
.forecast .cross { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
.readout { font-size: 0.875rem; font-variant-numeric: tabular-nums lining-nums; }
.forecast .now.togo { fill: var(--c-togo); }
.forecast .now.total { fill: var(--ink); }
.forecast .axis, .forecast .grid { stroke: var(--hair); stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast text { font-size: 11px; fill: var(--muted); font-variant-numeric: tabular-nums lining-nums; }
.keys { font-size: 0.875rem; color: var(--muted); display: flex; flex-wrap: wrap; align-items: center; gap: 0.2rem 0.5rem; }
.keys .k { white-space: nowrap; display: inline-flex; align-items: center; gap: 0.35rem; }
.key { display: inline-block; width: 1.4em; border-top: 2px solid var(--k2); vertical-align: middle; }
.key.spent { --k2: var(--c-spent); }
.key.togo { --k2: var(--c-togo); }
.key.total { --k2: var(--ink); border-top-width: 3px; }
/* On a narrow screen the chart's 640 units shrink to about 360 px: its ticks' text, in those units, grows to match. */
@media (max-width: 34rem) { .forecast text { font-size: 19px; } }

details summary { cursor: pointer; width: max-content; color: var(--muted); font-size: 0.9375rem; }
.more { display: grid; gap: 0.9rem; padding-top: 0.75rem; }
.sw {
  display: inline-block;
  width: 0.8em;
  height: 0.8em;
  vertical-align: -0.05em;
  background: var(--k);
  box-shadow: inset 0 0 0 1px var(--hair);
}
.settled { --k: var(--settled); }
.open { --k: var(--open); }
.split { --k: var(--split); }
.pending { --k: var(--pending); }

/* Levels: one grid; each row's cells join it (display: contents), so the columns line up.  On a narrow screen a
   row's bar takes a line of its own. */
.levels {
  display: grid;
  grid-template-columns: 1.4rem 1.9rem repeat(4, minmax(3.6rem, auto)) minmax(6rem, 1fr);
  column-gap: 0.8rem;
  align-items: center;
  font-size: 0.9375rem;
}
.lv { display: contents; }
.lv > * { padding-block: 0.22rem; }
.lv .n { text-align: right; }
.lv .m { text-align: right; color: var(--muted); }
.lv .d { color: var(--muted); }
.lv.head > * { padding-block: 0 0.3rem; }
.levels .rule { grid-column: 1 / -1; height: 1px; background: var(--hair); margin-bottom: 0.15rem; }
.lv.journal > * { color: var(--muted); }
.bar { display: flex; gap: 2px; height: 0.6rem; border-radius: 3px; overflow: hidden; }
.seg { flex-basis: 0; min-width: 2px; background: var(--k); }
@media (max-width: 34rem) {
  .levels { grid-template-columns: 1.2rem 1.7rem repeat(4, minmax(0, 1fr)); column-gap: 0.6rem; }
  .barcell { grid-column: 1 / -1; padding-block: 0 0.45rem; }
  .lv.head .barcell { display: none; }
}

/* Charts: two small multiples, one series each, on a shared x of hours of running. */
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 1rem 1.75rem; }
.chart { margin: 0; display: grid; gap: 0.3rem; }
.chart figcaption { font-size: 0.875rem; color: var(--muted); }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart .line { fill: none; stroke: var(--ink); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.chart .axis, .chart .grid, .chart .pass { stroke: var(--hair); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart text { font-size: 11px; fill: var(--muted); font-variant-numeric: tabular-nums lining-nums; }
.chart .end { fill: var(--ink); }

/* Open sub-cases, under their parents. */
.opens, .opens ul { list-style: none; margin: 0; padding: 0; }
.opens { display: grid; gap: 0.45rem; }
.opens ul { display: flex; flex-wrap: wrap; gap: 0 1.1rem; padding-left: 1rem; }
.opens code { font-size: 0.75rem; line-height: 1.45; }
.opens .part { white-space: nowrap; }
.opens .parent { color: var(--ink); }
.opens .same { color: color-mix(in oklab, var(--muted) 70%, var(--paper)); }
.opens li.pending code { color: var(--muted); }
"""


def page(surveys, now):
    """The whole page, self-contained, for these surveys made at the time now."""
    title = 'Search progress'      # dreeves's wording, 2026-10-09
    # TODO: says exactly how stale the page is: the time it was made, to the second, with its time zone, and its age, which the script fills in and keeps up
    made = f'As of {clock(now)} {time.strftime("%Z", time.localtime(now))} (<b id="age" data-made="{round(now * 1000)}">—</b> ago)'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="refresh" content="{REFRESH}">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=STIX+Two+Text:ital,wght@0,400;0,600;1,400&display=swap">
<style>{STYLE}</style>
</head>
<body>
<main>
<header><h1>{title}</h1><p class="stale">{made}</p></header>
{''.join(run_html(s) for s in surveys)}
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""


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


def load_cache(path): return json.load(open(path)) if os.path.exists(path) else {}
def save_cache(path, cache): write_atomic(path, json.dumps(cache, sort_keys=True))


def main(argv):
    # TODO: error copy; says how to run the script: with no argument to write the page once, or with --watch to keep rewriting it
    assert argv in ([], ['--watch']), 'Claude: "usage: python3 -B progress.py [--watch]"'
    os.nice(max(0, NICE - os.nice(0)))
    while True:
        cache, procs, now = load_cache(CACHE), processes(), time.time()
        surveys = [survey(n, order, *files(n, order), procs, now, cache.setdefault(f'{n}_{order}_{v5.CODE}', {}),
                          cache.setdefault(f'{n}_{order}_{v5.CODE}_etas', {})) for n, order in RUNS]
        write_atomic(PAGE, page(surveys, now))
        save_cache(CACHE, cache)
        if not argv: return
        time.sleep(REFRESH)


if __name__ == '__main__':
    main(sys.argv[1:])
