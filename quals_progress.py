#!/usr/bin/env python3
"""Quals for progress.py.  Run: python3 -B quals_progress.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its
replicata (the setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what
happened instead).  Tiny real runs of overnight_v5 (40@6, 48@6 and 64@7, one worker process each, the width test
off, journals and logs in a temporary directory) supply real journal and log lines; synthetic journals on the real
split of 40@6 and 64@7 supply trees whose level counts are known.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, bisect, shutil, tempfile, threading, traceback, subprocess, contextlib, collections
import numpy as np
import overnight_v5 as v5
import progress

HERE = os.path.dirname(os.path.abspath(__file__))
TINY = {}                                     # tiny real runs by name, made once per process (see tiny)

DRIVER = """import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {here!r})
import overnight_v5 as v5, certbb
assert callable(certbb.Guide.width_test)
certbb.Guide.width_test = lambda self, pairs, rows, l, u, emit, stats: False    # off, here and in the workers (see drive)
if __name__ == '__main__':
    v5.configure({n}, {order})
    v5.JOURNAL, v5.LOG, v5.PROCESSES, v5.BUDGET = {journal!r}, {log!r}, 1, {budget!r}
    v5.run()
"""


def drive(n, order, budget, journal, log):
    """One real pass of overnight_v5 at (n, order) with the given budgets and one worker process, appending to the
    journal and log given, with certbb's width test off: it closes these tiny runs outright (64@7 at budgets 1, 1, 1
    included), and the quals need runs that split and leave leaves open as 240@11 does.  The driver script patches it
    at its top level, which the worker processes run again as they start."""
    script = os.path.join(os.path.dirname(journal), f'drive_{n}_{order}.py')
    open(script, 'w').write(DRIVER.format(here=HERE, n=n, order=order, journal=journal, log=log, budget=tuple(budget)))
    p = subprocess.run([sys.executable, '-B', script], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]


def tiny(name):
    """The journal and log paths of a tiny real run, made on first use:
         closed     40@6 with its SETTINGS budgets, run twice on one journal and log (pass 2 settles the top at once);
         open       64@7 with budgets (1, 1, 1): NOT FINISHED, 7 leaves left open at budget 3;
         resolved   open's journal and log, then a second pass with 64@7's SETTINGS budgets, which settles them;
         resolving  open's journal and log, with resolved's second start line appended: a re-solve pass just begun;
         witness    48@6 with its SETTINGS budgets: a witness."""
    if name not in TINY:
        d = tempfile.mkdtemp(prefix='progress-quals-')
        journal, log = os.path.join(d, 'journal.jsonl'), os.path.join(d, 'run.log')
        if name == 'closed':
            for _ in range(2): drive(40, 6, v5.SETTINGS[40, 6][1], journal, log)
        if name == 'open':
            drive(64, 7, (1, 1, 1), journal, log)
        if name == 'resolved':
            for path, src in ((journal, tiny('open')[0]), (log, tiny('open')[1])): shutil.copy(src, path)
            drive(64, 7, v5.SETTINGS[64, 7][1], journal, log)
        if name == 'resolving':
            for path, src in ((journal, tiny('open')[0]), (log, tiny('open')[1])): shutil.copy(src, path)
            start = [l for l in open(tiny('resolved')[1]).read().splitlines() if 'Claude: "start:' in l][1]
            open(log, 'a').write(start + '\n')
        if name == 'witness':
            drive(48, 6, v5.SETTINGS[48, 6][1], journal, log)
        TINY[name] = (journal, log)
    return TINY[name]


def expect_assertion(f, *args):
    try:
        f(*args)
    except AssertionError:
        return
    raise Exception(f'no AssertionError from {f.__name__}')


def write_journal(path, records):
    """A journal for v5's current configuration: its header, then the records."""
    with open(path, 'w') as fh:
        fh.write(json.dumps(v5.header()) + '\n')
        for r in records: fh.write(json.dumps(r) + '\n')


def tree_40_6():
    """The real split of 40@6, by structure: the top's one feasible child A and its empty pool P0; A's feasible
    children B1 < B2 and empty pool P1; B1's feasible children C11 < C12 and pool Q1; B2's feasible child C21 and pool
    Q2.  Asserted, so a change in v5's split shows up here."""
    v5.configure(40, 6)
    kids = lambda node: v5.split(6, node)
    A, P0 = kids(())
    B1, B2, P1 = kids(A)
    C11, C12, Q1 = kids(B1)
    C21, Q2 = kids(B2)
    assert [len(x[-1][1]) for x in (P0, P1, Q1, Q2)] == [0, 0, 4, 5]
    assert all(len(x[-1][1]) == 1 for x in (A, B1, B2, C11, C12, C21))
    return dict(A=A, P0=P0, B1=B1, B2=B2, P1=P1, C11=C11, C12=C12, Q1=Q1, C21=C21, Q2=Q2)


def rec(node, verdict, budget=None):
    """A journal record for a node, at its own budget under v5's SETTINGS unless given."""
    return {'key': v5.node_key(node), 'verdict': verdict, 'budget': v5.node_budget(node) if budget is None else budget}


def scenario_a(t):
    """Every verdict kind on the 40@6 tree: the top and A split; P0, P1, the pools Q1 and Q2 and C21 INFEASIBLE; B2
    UNKNOWN then CLOSED; B1 split; C11 UNKNOWN at the bottom budget (open); C12 never reached (pending)."""
    return ([rec((), 'UNKNOWN'), rec(t['P0'], 'INFEASIBLE'), rec(t['A'], 'UNKNOWN'), rec(t['P1'], 'INFEASIBLE'),
             rec(t['B2'], 'UNKNOWN'), rec(t['Q2'], 'INFEASIBLE'), rec(t['C21'], 'INFEASIBLE'), rec(t['B2'], 'CLOSED'),
             rec(t['B1'], 'UNKNOWN'), rec(t['Q1'], 'INFEASIBLE'), rec(t['C11'], 'UNKNOWN')])


def finals(records):
    return {r['key']: r for r in records}


def counts(row):
    """A level row's counts with the zeros (and an unknown pending count, None) left out, so that expectations read as
    plain dicts."""
    return {k: v for k, v in row['counts'].items() if v}


def node_line(key, verdict, solve, split=0.0, t=0.0):
    return {'t': t, 'i': 0, 'key': key, 'verdict': verdict, 'solve': solve, 'split': split,
            'closed': 0, 'waiting': 0, 'running': 0, 'open': 0, 'failures': 0}


# ---------- reading files ----------

def q_complete_lines_leave_out_a_partial_last_line():
    # Replicata: a file "a\nb\nc" (its last line still being written) and a file "a\nb\nc\n".
    # Expectata: ['a', 'b'] and ['a', 'b', 'c']: a line counts once its newline is written.
    d = tempfile.mkdtemp(prefix='progress-quals-')
    for text, lines in (('a\nb\nc', ['a', 'b']), ('a\nb\nc\n', ['a', 'b', 'c']), ('', [])):
        open(os.path.join(d, 'f'), 'w').write(text)
        assert progress.complete_lines(os.path.join(d, 'f')) == lines, (text, progress.complete_lines(os.path.join(d, 'f')))


def q_log_of_a_closed_run():
    # Replicata: the tiny closed run (40@6, two passes on one journal and log), parsed.
    # Expectata: two passes; the first's start line read in full (n, order, processes, budgets, pool budget, moduli,
    # earlier verdicts), its progress lines numbered 1, 2, ... with the log's own counts, ending ALL NODES CLOSED with
    # the last line's closed count; the second pass, which starts from 11 earlier verdicts (keys), settles the top from
    # the
    # journal, so it has no progress lines, and also ends ALL NODES CLOSED.
    passes = progress.parse_log(tiny('closed')[1])
    assert len(passes) == 2, len(passes)
    p, q = passes
    assert (p['n'], p['order'], p['processes'], p['budgets'], p['pool_budget'], p['moduli'], p['earlier']) == \
        (40, 6, 1, [1, 1, 1, 100000], 3, [4, 7, 8], 0), p
    assert [nd['i'] for nd in p['nodes']] == list(range(1, len(p['nodes']) + 1)) and len(p['nodes']) == 11
    assert p['nodes'][0]['key'] == '' and p['nodes'][0]['verdict'] == 'UNKNOWN'
    assert all(nd['verdict'] in ('INFEASIBLE', 'UNKNOWN') for nd in p['nodes'])
    last = p['nodes'][-1]
    assert (last['closed'], last['waiting'], last['running'], last['open'], last['failures']) == (7, 0, 0, 0, 0), last
    assert p['outcome'].startswith('Claude: "ALL NODES CLOSED (7, 0.0 h): no ±1 sequence of length 40'), p['outcome']
    assert p['start'] <= p['nodes'][0]['t'] <= p['last'] and p['opens'] == []
    assert q['earlier'] == 11 and q['nodes'] == [] and q['outcome'].startswith('Claude: "ALL NODES CLOSED (1, '), q


def q_log_of_an_open_run():
    # Replicata: the tiny open run (64@7 with budgets 1, 1, 1), parsed.
    # Expectata: one pass ending 'NOT FINISHED: 7 nodes left open, 3 closed'; its seven open lines name the seven
    # progress lines whose open count went up; the last progress line's counts are closed 3 and open 7.
    passes = progress.parse_log(tiny('open')[1])
    assert len(passes) == 1
    p = passes[0]
    assert p['outcome'].startswith('Claude: "NOT FINISHED: 7 nodes left open, 3 closed'), p['outcome']
    went_up = [nd['key'] for a, nd in zip([{'open': 0}] + p['nodes'], p['nodes']) if nd['open'] > a['open']]
    assert sorted(p['opens']) == sorted(went_up) and len(went_up) == 7, (p['opens'], went_up)
    assert (p['nodes'][-1]['closed'], p['nodes'][-1]['open']) == (3, 7)


def q_log_of_a_witness_run():
    # Replicata: the tiny witness run (48@6), parsed.
    # Expectata: one pass whose outcome is the final witness line, with the witness's X; the earlier 'WITNESS FOUND
    # in {...}' line is read without becoming the outcome.
    p, = progress.parse_log(tiny('witness')[1])
    assert p['outcome'].startswith('Claude: "WITNESS FOUND, exact order 6: X = [') and p['outcome'].endswith(']"')



def q_start_line_says_whether_siblings_are_shuffled():
    # Replicata: parse_lines of two one-line logs: a start line as overnight_v5 writes it since 2026-10-17, ending
    # ", siblings shuffled", and one as it wrote before.
    # Expectata: both parse, the first pass shuffled, the second not (its replay keeps the split's order).
    head = ('2026-10-17 05:00:00 Claude: "start: n = 64, order at least 7, 1 processes, budgets [1, 1, 3] (LP solves; a '
            'pool at least 3 per member), HiGHS 1.12.0 (4f96ee8), split moduli [3, 5], 0 earlier verdicts')
    new, = progress.parse_lines([head + ', siblings shuffled"'])
    old, = progress.parse_lines([head + '"'])
    assert (new['shuffled'], old['shuffled']) == (True, False), (new, old)
    assert {k: v for k, v in new.items() if k != 'shuffled'} == {k: v for k, v in old.items() if k != 'shuffled'}


def q_replay_pushes_a_shuffled_pass_s_children_in_sibling_order():
    # Replicata: progress.replay of a made-up pass of one worker: the top node UNKNOWN, split (cached) into three
    # children, which then finish INFEASIBLE in the order search() pops them when it shuffles (the reverse of
    # overnight_v5.sibling_order of the split), each progress line's counts as search() logs them; once with the pass
    # marked shuffled, once not.
    # Expectata: shuffled, the replay accounts for every line (each finished node is the running one it popped) and
    # ends with nothing waiting or running; not shuffled, it pops the children in the split's order, so the second
    # line's node is not the one running, and it fails.
    kids = ['3:[0,1,2]', '3:[1,1,1]', '3:[2,1,0]']
    order = v5.sibling_order('', kids)[::-1]
    assert order != kids[::-1], order                       # the shuffle changes the order here
    lines = [{'t': 1.0, 'i': 1, 'key': '', 'verdict': 'UNKNOWN', 'solve': 0.5, 'split': 0.1, 'closed': 0, 'waiting': 3,
              'running': 0, 'open': 0, 'failures': 0}]
    lines += [{'t': 2.0 + j, 'i': 2 + j, 'key': k, 'verdict': 'INFEASIBLE', 'solve': 0.5, 'split': 0.0, 'closed': j + 1,
               'waiting': 2 - j, 'running': 0, 'open': 0, 'failures': 0} for j, k in enumerate(order)]
    def state(shuffled):
        p = {'start': 0.0, 'last': 4.0, 'shuffled': shuffled, 'nodes': lines, 'opens': [], 'outcome': None}
        return {'t': 4.0, 'label': 'a made-up pass', 'passes': [p], 'cache': {'': kids}, 'processes': 1,
                'budgets': [10, 10, 10], 'final_at_start': {}}
    root, stack, running = progress.replay(state(True))
    assert (stack, running) == ([], []) and [n.key for n in root.kids] == v5.sibling_order('', kids), (stack, running)
    expect_assertion(progress.replay, state(False))

def q_log_with_an_unknown_line_fails():
    # Replicata: the tiny closed run's log with one made-up line appended.
    # Expectata: AssertionError: a line of no known form is never skipped.
    d = tempfile.mkdtemp(prefix='progress-quals-')
    log = os.path.join(d, 'run.log')
    shutil.copy(tiny('closed')[1], log)
    open(log, 'a').write('2026-10-09 18:00:00 something else\n')
    expect_assertion(progress.parse_log, log)


def q_journal_reads_last_record_per_key():
    # Replicata: the tiny closed run's journal, read with v5 configured for 40@6; then the same journal with a
    # partial last line; then with another configuration's header (v5 configured for 64@7).
    # Expectata: one record per key, the last (so the top is CLOSED): 11 keys from 15 records, 7 of them INFEASIBLE;
    # the partial line is left out; the
    # other configuration fails with AssertionError.
    v5.configure(40, 6)
    final = progress.read_journal(tiny('closed')[0])
    lines = open(tiny('closed')[0]).read().splitlines()
    assert len(final) == 11 and len(lines) == 16 and final['']['verdict'] == 'CLOSED', (len(final), final[''])
    assert sum(json.loads(l)['verdict'] == 'INFEASIBLE' for l in lines[1:]) == \
        sum(r['verdict'] == 'INFEASIBLE' for r in final.values()) == 7
    d = tempfile.mkdtemp(prefix='progress-quals-')
    path = os.path.join(d, 'j.jsonl')
    open(path, 'w').write('\n'.join(lines[:5]) + '\n' + lines[5][:20])
    assert len(progress.read_journal(path)) == 4
    v5.configure(64, 7)
    expect_assertion(progress.read_journal, tiny('closed')[0])


# ---------- keys, budgets and statuses ----------

def all_nodes(order):
    """Every node of v5's current configuration's tree with every node split (the empty pools are not split)."""
    out, level = [], [()]
    while level:
        out += level
        level = [c for x in level if not (x and len(x[-1][1]) == 0) for c in v5.split(order, x)]
    return out


def q_budget_and_leaf_agree_with_v5():
    # Replicata: every node of the fully split trees of 40@6 and 64@7 (pools and empty pools included).
    # Expectata: budget_of(key) is v5.node_budget(node) under the SETTINGS budgets; leaf(key) holds exactly when
    # v5.split gives no children (for the nodes split accepts: all but the empty pools, which are never split).
    for n, order in ((40, 6), (64, 7)):
        v5.configure(n, order)
        nodes = all_nodes(order)
        assert any(v5.is_pool(x) for x in nodes) and any(x and len(x[-1][1]) == 0 for x in nodes)
        for x in nodes:
            key = v5.node_key(x)
            assert progress.budget_of(key, v5.BUDGET) == v5.node_budget(x), key
            if not (x and len(x[-1][1]) == 0):
                assert progress.leaf(key, len(v5.CASCADE)) == (v5.split(order, x) == []), key


def q_parse_key_inverts_node_key():
    # Replicata: every single-vector node of 64@7's fully split tree, and its pools.
    # Expectata: parse_key(node_key(node)) == node for the first; AssertionError for a pool, whose key does not
    # hold its members.
    v5.configure(64, 7)
    nodes = all_nodes(7)
    for x in nodes:
        if not any(len(V) != 1 for _, V in x): assert progress.parse_key(v5.node_key(x)) == x, x
    for x in nodes:
        if v5.is_pool(x): expect_assertion(progress.parse_key, v5.node_key(x))


def q_status():
    # Replicata: statuses at 40@6 under its SETTINGS budgets, for the top, a split node, a bottom leaf and a pool.
    # Expectata: no record -> pending; INFEASIBLE or CLOSED -> settled; UNKNOWN at its budget -> split for a node with
    # children, open for a leaf; UNKNOWN at a smaller budget -> pending (it is solved again in this pass).
    t = tree_40_6()
    budgets = v5.BUDGET
    for node, kind in (((), 'split'), (t['B1'], 'split'), (t['C11'], 'open'), (t['Q1'], 'split')):
        key = v5.node_key(node)
        assert progress.status(key, {}, budgets) == 'pending'
        for verdict in ('INFEASIBLE', 'CLOSED'):
            assert progress.status(key, finals([rec(node, verdict)]), budgets) == 'settled'
        assert progress.status(key, finals([rec(node, 'UNKNOWN')]), budgets) == kind, key
        assert progress.status(key, finals([rec(node, 'UNKNOWN', v5.node_budget(node) - 1)]), budgets) == 'pending'


# ---------- levels ----------

def q_levels_of_a_synthetic_journal():
    # Replicata: the real split of 40@6 and scenario_a's verdicts (every kind at the bottom level), enumerated as
    # deep as possible.
    # Expectata: four levels, all enumerated: level 0 split 1; level 1 settled 1 (P0), split 1 (A); level 2 settled 2
    # (P1 and the CLOSED B2), split 1 (B1); level 3 settled 3 (Q1, Q2, C21), open 1 (C11), pending 1 (C12).
    t = tree_40_6()
    final = finals(scenario_a(t))
    levels = progress.enumerate_levels(final, v5.BUDGET, 6, {}, progress.DEEPEST)
    assert [sorted(l) for l in levels] == [
        [''], sorted(v5.node_key(t[k]) for k in ('A', 'P0')), sorted(v5.node_key(t[k]) for k in ('B1', 'B2', 'P1')),
        sorted(v5.node_key(t[k]) for k in ('C11', 'C12', 'Q1', 'C21', 'Q2'))], levels
    rows = progress.level_rows(levels, final, v5.BUDGET, 3)
    assert [counts(r) for r in rows] == [{'split': 1}, {'settled': 1, 'split': 1}, {'settled': 2, 'split': 1},
                                         {'settled': 3, 'open': 1, 'pending': 1}], rows
    assert all(r['enumerated'] for r in rows) and [r['depth'] for r in rows] == [0, 1, 2, 3]


def q_levels_stop_above_a_pending_sub_case():
    # Replicata: scenario_a without B1's and its children's records, so B1 (level 2) is pending.
    # Expectata: levels 0 to 2 enumerated, level 2 with settled 2 and pending 1; level 3 counted from the journal
    # alone (not enumerated): settled 2 (Q2 and C21), its pending count unknown (None).
    t = tree_40_6()
    drop = {v5.node_key(t[k]) for k in ('B1', 'Q1', 'C11')}
    final = finals([r for r in scenario_a(t) if r['key'] not in drop])
    levels = progress.enumerate_levels(final, v5.BUDGET, 6, {}, progress.DEEPEST)
    assert len(levels) == 3, levels
    rows = progress.level_rows(levels, final, v5.BUDGET, 3)
    assert [r['enumerated'] for r in rows] == [True, True, True, False]
    assert counts(rows[2]) == {'settled': 2, 'pending': 1} and rows[3]['counts'] == \
        {'settled': 2, 'split': 0, 'open': 0, 'pending': None}, rows


def q_levels_stop_at_the_deepest_enumerated_level():
    # Replicata: scenario_a's journal enumerated with deepest 1, then 0.
    # Expectata: levels 0 and 1, then level 0 alone; the levels below are counted from the journal alone.
    t = tree_40_6()
    final = finals(scenario_a(t))
    for deepest in (1, 0):
        levels = progress.enumerate_levels(final, v5.BUDGET, 6, {}, deepest)
        assert len(levels) == deepest + 1, levels
        rows = progress.level_rows(levels, final, v5.BUDGET, 3)
        assert [r['enumerated'] for r in rows] == [d <= deepest for d in range(4)]
    assert counts(rows[3]) == {'settled': 3, 'open': 1} and rows[3]['counts']['pending'] is None, rows[3]


def q_levels_with_an_old_budget_leaf():
    # Replicata: scenario_a with C11 UNKNOWN at budget 2, below the bottom budget 100000 (as after a pass that raised
    # it).
    # Expectata: level 3 has pending 2 (C11 and C12) and open 0.
    t = tree_40_6()
    final = finals([r if r['key'] != v5.node_key(t['C11']) else rec(t['C11'], 'UNKNOWN', 2) for r in scenario_a(t)])
    levels = progress.enumerate_levels(final, v5.BUDGET, 6, {}, progress.DEEPEST)
    assert counts(progress.level_rows(levels, final, v5.BUDGET, 3)[3]) == {'settled': 3, 'pending': 2}


def q_levels_fail_on_a_journal_key_split_does_not_give():
    # Replicata: scenario_a plus a made-up level-1 key 4:[9,9,1,1] INFEASIBLE, which no split gives.
    # Expectata: AssertionError: the journal and the enumeration must agree on every enumerated level.
    t = tree_40_6()
    final = finals(scenario_a(t) + [{'key': '4:[9,9,1,1]', 'verdict': 'INFEASIBLE', 'budget': 3}])
    expect_assertion(lambda: progress.level_rows(progress.enumerate_levels(final, v5.BUDGET, 6, {}, progress.DEEPEST),
                                                 final, v5.BUDGET, 3))


def q_levels_fail_on_a_pool_that_came_back_unknown():
    # Replicata: 64@7, the top UNKNOWN and its pool child (a pool of several members) UNKNOWN.
    # Expectata: AssertionError, since a pool's key does not hold its members, so progress.py cannot split it.
    v5.configure(64, 7)
    kids = v5.split(7, ())
    pool = kids[-1]
    assert v5.is_pool(pool)
    final = finals([rec((), 'UNKNOWN'), rec(pool, 'UNKNOWN')] + [rec(k, 'INFEASIBLE') for k in kids[:-1]])
    expect_assertion(progress.enumerate_levels, final, v5.BUDGET, 7, {}, progress.DEEPEST)


def q_split_runs_once_per_node():
    # Replicata: scenario_a enumerated twice with one cache dict, v5.split counted; then the cache saved to a file and
    # loaded back.
    # Expectata: the second enumeration splits nothing, and the first splits each node at most once; the cache holds
    # the children keys of the top, A, B1 and B2 (bottom nodes are never split), and survives the file.
    t = tree_40_6()
    final = finals(scenario_a(t))
    calls, real = [], v5.split
    def counting(order, node):
        calls.append(v5.node_key(node))
        return real(order, node)
    cache = {}
    v5.split = counting
    try:
        first = progress.enumerate_levels(final, v5.BUDGET, 6, cache, progress.DEEPEST)
        n1 = len(calls)
        second = progress.enumerate_levels(final, v5.BUDGET, 6, cache, progress.DEEPEST)
    finally:
        v5.split = real
    assert first == second and len(calls) == n1 == len(set(calls)), calls
    assert set(cache) == {v5.node_key(x) for x in ((), t['A'], t['B1'], t['B2'])}, sorted(cache)
    assert cache[v5.node_key(t['A'])] == [v5.node_key(x) for x in (t['B1'], t['B2'], t['P1'])]
    d = tempfile.mkdtemp(prefix='progress-quals-')
    path = os.path.join(d, 'cache.json')
    progress.save_cache(path, {'40_6': cache})
    assert progress.load_cache(path) == {'40_6': cache}
    assert progress.load_cache(os.path.join(d, 'none.json')) == {}


# ---------- run state ----------

def q_run_state():
    # Replicata: process lists as (pid, ppid, stat, command), for the run 240@11.
    # Expectata: no process of the run -> ended (whatever runs for other lengths); the run's process and workers all
    # unstopped -> running; the main process or any one worker stopped (stat T) -> frozen; an outcome line in the
    # current pass -> ended even while the process exits; two main processes of the run -> AssertionError.
    py = '/opt/homebrew/bin/Python'
    main = (100, 1, 'SN', f'{py} -u -B overnight_v5.py 240 11')
    workers = [(101, 100, 'RN', f'{py} -B -c from multiprocessing.spawn import spawn_main'), (102, 100, 'RN', 'x')]
    other = [(200, 1, 'TN', f'{py} -u -B overnight_v5.py 304 9'), (300, 1, 'S', f'{py} overnight_v5.py 240 111'),
             (400, 1, 'T', f'{py} -u -B overnight_240_v3.py'), (500, 100, 'S', 'not a worker? yes, a child')]
    assert progress.run_state(other[:4], 240, 11, None) == 'ended'
    assert progress.run_state([main] + workers + other[:4], 240, 11, None) == 'running'
    assert progress.run_state([(100, 1, 'TN', main[3])] + workers, 240, 11, None) == 'frozen'
    assert progress.run_state([main, workers[0], (102, 100, 'T', 'x')], 240, 11, None) == 'frozen'
    assert progress.run_state([main] + workers, 240, 11, 'Claude: "NOT FINISHED: ..."') == 'ended'
    assert progress.run_state([(7, 1, 'S', 'python3 /a/b/overnight_v5.py 240 11')], 240, 11, None) == 'running'
    expect_assertion(progress.run_state, [main, (103, 1, 'S', main[3])], 240, 11, None)


def q_processes_lists_this_process():
    # Replicata: progress.processes() on this machine.
    # Expectata: a list of (pid, ppid, stat, command) that holds this process, with its parent and its command line.
    me = [p for p in progress.processes() if p[0] == os.getpid()]
    assert len(me) == 1 and me[0][1] == os.getppid() and 'quals_progress.py' in me[0][3] and me[0][2][0] in 'RS', me


# ---------- this pass's work at the estimate's level ----------

def work_case():
    """A level of 12 keys at depth 1: k0, k1 settled before this pass (no lines); k2..k7 finished in this pass (k2..k6
    settled, k7 open); k8 split (partway); k9..k11 pending.  The touched ones (k2..k8) each have a progress line, k2's
    split between itself and a child; a line above the level too."""
    keys = [f'9:[{i}]' for i in range(12)]
    stats = dict(zip(keys, ['settled'] * 7 + ['open', 'split'] + ['pending'] * 3))
    lines = [node_line('', 'UNKNOWN', 50.0), node_line(keys[2], 'UNKNOWN', 99.0), node_line(keys[2] + ' 3:[1]', 'INFEASIBLE', 1.0)]
    lines += [node_line(keys[i], 'UNKNOWN', 100.0) for i in range(3, 9)]
    return keys, stats, lines


def q_work_counts():
    # Replicata: work_case.
    # Expectata: 10 sub-cases are this pass's work (all but k0 and k1, settled before it with no line), 6 of them
    # finished, 1 partway, 3 pending; with no lines at all, the work is the 5 not settled (k7 open, so done; k8 split;
    # k9..k11 pending).
    keys, stats, lines = work_case()
    w = progress.work(keys, 1, stats, lines)
    assert (w['size'], w['before'], w['work'], w['done'], w['progress'], w['pending']) == (12, 2, 10, 6, 1, 3), w
    w = progress.work(keys, 1, stats, [])
    assert (w['work'], w['done'], w['progress'], w['pending']) == (5, 1, 1, 3), w


# ---------- the run, dated ----------

def q_dating_finds_each_pass_journal():
    # Replicata: read_run of the tiny resolved run (64@7: pass 1 at budgets (1, 1, 1), the open run's whole journal and
    # log, then pass 2 at its SETTINGS budgets) and of the tiny open run alone.
    # Expectata: pass 2's first record (bounds[1]) is where the open run's journal ends, the records before it are the
    # open run's; every record is dated by a line at or before its pass's last, dates never decrease, and each fresh
    # record is dated by the progress line of its node.
    v5.configure(64, 7)
    R, O = progress.read_run(*tiny('resolved')), progress.read_run(*tiny('open'))
    assert R['bounds'][0] == 0 and R['bounds'][1] == len(O['records']) and R['records'][:R['bounds'][1]] == O['records'], R['bounds']
    assert R['dates'] == sorted(R['dates']) and len(R['dates']) == len(R['records'])
    for i, j in R['fresh'].items():
        nd_key = re.search(r'\] \{(.*)\}: ', R['lines'][i])[1]
        assert R['records'][j]['key'] == nd_key and R['dates'][j] == i, (i, j)


def q_dating_leaves_out_records_whose_lines_are_unread():
    # Replicata: the tiny resolved run's journal whole, but its log cut before its last 3 progress lines (as if the log
    # had been read just before the journal, with those nodes finishing in between).
    # Expectata: read_run fails on nothing; it keeps exactly the records dated by the lines kept (their fresh records
    # and the CLOSED records after them) and leaves out the rest, which belong to the unread lines.
    journal, log = tiny('resolved')
    lines = progress.complete_lines(log)
    cut = [i for i, line in enumerate(lines) if progress.FORMS['node'].match(line)][-3]
    d = tempfile.mkdtemp(prefix='progress-quals-')
    short = os.path.join(d, 'short.log')
    open(short, 'w').write(''.join(line + '\n' for line in lines[:cut]))
    v5.configure(64, 7)
    whole, part = progress.read_run(journal, log), progress.read_run(journal, short)
    keep = sum(1 for j in range(len(whole['records'])) if whole['dates'][j] < cut)
    assert part['records'] == whole['records'][:keep] and keep < len(whole['records']), (keep, len(part['records']))


def q_dating_skips_lines_whose_records_a_migration_dropped():
    # Replicata: the tiny resolved run's journal with one fresh UNKNOWN record of its pass 1 removed, as
    # scratch/width/migrate_now.py removed the records of nodes the width test closes so that a later pass solves them
    # again; then, instead, the journal with two fresh records of pass 1 swapped.
    # Expectata: the first is read: the line of the removed record has no fresh record, every other line keeps its own,
    # and the bounds move down by one from pass 2 on; the second fails with AssertionError, since a record that exists
    # but out of order is no migration's doing.
    journal, log = tiny('resolved')
    v5.configure(64, 7)
    R = progress.read_run(journal, log)
    i, j = sorted(R['fresh'].items())[0]
    assert R['records'][j]['verdict'] == 'UNKNOWN' and R['bounds'][1] > j, (R['records'][j], R['bounds'])
    texts = progress.complete_lines(journal)
    d = tempfile.mkdtemp(prefix='progress-quals-')
    cut = os.path.join(d, 'cut.jsonl')
    open(cut, 'w').write(''.join(x + '\n' for k, x in enumerate(texts) if k != j + 1))
    C = progress.read_run(cut, log)
    assert i not in C['fresh'] and len(C['records']) == len(R['records']) - 1, (sorted(C['fresh'])[:5], len(C['records']))
    assert all(C['fresh'][k] == (v if v < j else v - 1) for k, v in R['fresh'].items() if k != i)
    assert C['bounds'] == [R['bounds'][0]] + [b - 1 for b in R['bounds'][1:]], (C['bounds'], R['bounds'])
    k1, k2 = sorted(R['fresh'].values())[:2]
    swapped = list(texts)
    swapped[k1 + 1], swapped[k2 + 1] = swapped[k2 + 1], swapped[k1 + 1]
    bad = os.path.join(d, 'swapped.jsonl')
    open(bad, 'w').write(''.join(x + '\n' for x in swapped))
    expect_assertion(progress.read_run, bad, log)


def q_passes_at_cut_the_log():
    # Replicata: the tiny resolved run, read whole; its log cut after each of its lines in turn, parsed afresh.
    # Expectata: passes_at(R, k) equals parse_log of the first k lines, for every k from the first start line on.
    journal, log = tiny('resolved')
    v5.configure(64, 7)
    R = progress.read_run(journal, log)
    for k in range(1, len(R['lines']) + 1):
        assert progress.passes_at(R, k) == progress.parse_lines(R['lines'][:k]), k


# ---------- the estimate ----------

def q_makespan_hand_cases():
    # Replicata: makespan on one replicate's worth of hand cases, 3 workers.
    # Expectata: loads [3, 0, 0] then jobs 2, 2, 2 -> 4 (two go to the idle workers, the third to one of them at 2);
    # loads [3, 0, 0] then fluid 6 -> 3 (fills both idle workers to 3); fluid 1 then job 5 on [0, 0, 0] -> 1/3 + 5;
    # no items -> the largest load; fluid items in a row fill as one; fluid 9 on [1, 2, 3] -> 5.
    R = progress.REPLICATES
    def one(v): return np.full(R, float(v))
    def run(loads, items): return progress.makespan(np.tile(np.array(loads, float), (R, 1)), [(k, one(x)) for k, x in items])
    assert np.allclose(run([3, 0, 0], [('job', 2)] * 3), 4)
    assert np.allclose(run([3, 0, 0], [('fluid', 6)]), 3)
    assert np.allclose(run([0, 0, 0], [('fluid', 1), ('job', 5)]), 1 / 3 + 5)
    assert np.allclose(run([7, 1, 0], []), 7)
    assert np.allclose(run([3, 0, 0], [('fluid', 2), ('fluid', 4)]), run([3, 0, 0], [('fluid', 6)]))
    assert np.allclose(run([1, 2, 3], [('fluid', 9)]), 5)


def leaf_urn(seed, members, lo, hi, room):
    rng = np.random.default_rng(seed)
    return progress.Urn(rng, np.array(members, float), progress.gap_ball(rng, lo, hi), room)


def q_urn_draws_balls_and_the_gap():
    # Replicata: a leaf urn with members 1, 2, 3 and a gap (10, 20): one censored draw above 2.5, then 50 plain draws;
    # a subtree urn whose members differ by replicate, with a fresh ball over that leaf urn; the first leaf urn again,
    # from the same seed.
    # Expectata: the censored draw exceeds 2.5 (the member 3, or the gap); every plain draw is a member, the censored
    # draw, an earlier draw or in [10, 20]; a subtree draw is its replicate's member or a fresh subtree (own 5 plus
    # 2 leaf picks, so at least 7); the same seed gives the same draws.
    u = leaf_urn(1, [1, 2, 3], 10., 20., 51)
    c = u.draw(2.5)
    assert ((c == 3) | ((c >= 10) & (c <= 20))).all()
    d = np.stack([u.draw() for _ in range(50)], axis=1)
    assert (np.isin(d, [1., 2., 3.]) | ((d >= 10) & (d <= 20))).all()
    R = progress.REPLICATES
    mem = (np.arange(R)[:, None] + 100.0)
    sub = progress.Urn(np.random.default_rng(2), mem, progress.fresh_ball(np.random.default_rng(3), np.array([5.]), np.array([2]), u), 20)
    v = np.stack([sub.draw() for _ in range(20)], axis=1)
    assert ((v == mem) | (v >= 7)).all() and (v != mem).any()
    a, b = leaf_urn(5, [1, 2], 3., 4., 3), leaf_urn(5, [1, 2], 3., 4., 3)
    assert all((a.draw(e) == b.draw(e)).all() for e in (1.5, -np.inf, -np.inf))


def q_urn_new_ball_has_hills_probability():
    # Replicata: a leaf urn of n = 9 members (1..9) and a gap (100, 200); one plain draw per replicate.
    # Expectata: the share of draws from the gap is 1/(n + 1) = 0.1, within 4 standard errors.
    d = leaf_urn(2, np.arange(1., 10.), 100., 200., 1).draw()
    share, se = (d >= 100).mean(), np.sqrt(0.1 * 0.9 / progress.REPLICATES)
    assert abs(share - 0.1) < 4 * se, share


def q_urn_less_data_wider():
    # Replicata: n members drawn at random from 304@9 pass 1's leaf costs (n = 0, 1, 5, 20, 100, 1000), 40 times each, in
    # a leaf urn whose gap runs, as estimate() makes it, from the larger of one LP solve and the largest member to
    # 2,000,000 LP solves, at 2.18 ms each (pass 1's speed); per replicate, the mean of 100 plain draws.
    # Expectata: the spread of that mean (standard deviation over replicates), averaged over the 40 samples, falls as n
    # grows; one member gives a spread (no point mass), wider than 20 members do.
    R, _ = live(304, 9)
    pop = np.array([nd['solve'] + nd['split'] for nd in R['passes'][0]['nodes'] if len(nd['key'].split()) == 6])
    s, src = 2.18e-3, np.random.default_rng(11)
    spread = {}
    for n in (0, 1, 5, 20, 100, 1000):
        sp = []
        for rep in range(40):
            m = src.choice(pop, n)
            lo = max(s, m.max() if n else 0.0)
            u = leaf_urn(rep, m, lo, max(2_000_000 * s, lo), 100)
            sp.append(np.stack([u.draw() for _ in range(100)], axis=1).mean(axis=1).std())
        spread[n] = np.mean(sp)
    assert spread[0] > spread[5] > spread[20] > spread[100] > spread[1000] > 0 and spread[1] > spread[20], spread


def q_one_member_still_spreads():
    # Replicata: a subtree urn with a single member (value 1000 in every replicate; its own job 10 s, 3 children) over a
    # leaf urn of members 1..5 with a gap (5, 50); one plain draw per replicate.
    # Expectata: about half the draws are the member (1/(1 + 1)), the rest fresh subtrees: 10 s plus three leaf picks,
    # so between 13 and 160; the draws are not all one value.
    R = progress.REPLICATES
    leaves = leaf_urn(6, np.arange(1., 6.), 5., 50., 0)
    sub = progress.Urn(np.random.default_rng(7), np.full((R, 1), 1000.), progress.fresh_ball(np.random.default_rng(8), np.array([10.]), np.array([3]), leaves), 1)
    v = sub.draw()
    share, se = (v == 1000).mean(), np.sqrt(0.25 / R)
    assert abs(share - 0.5) < 4 * se, share
    assert ((v == 1000) | ((v >= 13) & (v <= 160))).all() and len(np.unique(v)) > 2


def q_censored_draws_go_longest_first():
    # Replicata: a leaf urn of members 1..5 and a gap (5, 100); censored draws above 30, then above 20 (longest first).
    # Expectata: each censored draw exceeds its value; the second sometimes takes the first one's ball, never a member.
    u = leaf_urn(4, np.arange(1., 6.), 5., 100., 2)
    c1, c2 = u.draw(30.), u.draw(20.)
    assert (c1 > 30).all() and (c2 > 20).all() and (c2 == c1).any()


# The live runs as fixtures, at times now past, so fixed: every line and record up to such a time is written for good.
# 304@9: its whole pass 1 and its pass 2 up to the design workflow's frozen copy; 240@11: its pass 1 up to its freeze.
CUTS = {(304, 9): '2026-10-09 20:42:02', (240, 11): '2026-10-09 17:54:56'}
LIVE = {}


@contextlib.contextmanager
def as_written(n, order):
    """overnight_v5 configured for (n, order) with its CODE the one in that run's journal header, the code that wrote
    it, so that a run's files stay fixtures as the code changes (304@9's header keeps the code its run had); CODE is
    restored after."""
    v5.configure(n, order)
    saved = v5.CODE
    v5.CODE = json.loads(open(v5.JOURNAL).readline())['code']
    try: yield
    finally: v5.CODE = saved


def live(n, order):
    """read_run of the live run (n, order) and its cached splits (progress.CACHE, which progress.py keeps; asserted
    present), both as_written, made once."""
    if (n, order) not in LIVE:
        with as_written(n, order):
            cache = progress.load_cache(progress.CACHE)[f'{n}_{order}_{v5.CODE}']
            LIVE[n, order] = (progress.read_run(v5.JOURNAL, v5.LOG), cache)
    return LIVE[n, order]


STATES = []


def states():
    """The estimate's states of the live runs every half hour of running in each pass up to CUTS, and at CUTS, made
    once: 304@9 pass 1 (25 states, its end known: 23:10:13), pass 2 (7), 240@11 pass 1 (39); a pass begun after
    CUTS (304@9's later passes, 240@11's pass 2) has none."""
    if not STATES:
        for (n, order), cut in CUTS.items():
            R, cache = live(n, order)
            end = progress.stamp(cut)
            begun = R['passes'][:bisect.bisect_right([p['start'] for p in R['passes']], end)]
            for k, p in enumerate(begun, 1):
                stop = min(end, p['last'])
                times = [p['start'] + h for h in range(0, int(stop - p['start']) + 1, 1800)] + [stop]
                for t in times:
                    STATES.append(progress.state_at(R, t, cache, f'{n}@{order} p{k} +{(t - p["start"]) / 3600:.1f}h'))
    return STATES


def q_replay_runs_what_ran():
    # Replicata: every state of states(); the replay's running nodes; from the whole live log, each later line.
    # Expectata: a running node with a key has a later line with that key, which began within 2 s of the replay's
    # start for it (stamps are whole seconds, durations tenths), unless no later line has its key yet and its pass has
    # not ended (it may still run); a running node without a key (240's depths below the cache) has a later line under
    # its parent that began within 2 s of its start, with the same exception; every later line that began before t - 2
    # was running in the replay, so the replay misses no job; at most the pass's processes run.
    for s in states():
        R, _ = live(int(s['label'].split('@')[0]), int(s['label'].split('@')[1].split()[0]))
        k = int(s['label'].split(' p')[1].split()[0])
        p = R['passes'][k - 1]
        later = [(nd['t'], nd['t'] - nd['solve'] - nd['split'], nd['key']) for nd in p['nodes'] if nd['t'] > s['t']]
        _, _, running = progress.replay(s)
        assert len(running) <= s['processes'], s['label']
        for node in running:
            if node.key is not None:
                hit = [x for x in later if x[2] == node.key]
                assert (hit and abs(hit[0][1] - node.start) <= 2) or (not hit and p['outcome'] is None), (s['label'], node.key)
            else:
                up = node.parent.key
                hit = [x for x in later if progress.parent_key(x[2]) == up and abs(x[1] - node.start) <= 2]
                assert hit or p['outcome'] is None, (s['label'], up)
        keyed = {node.key for node in running}
        unkeyed = {node.parent.key for node in running if node.key is None}
        for end, start, key in later:
            assert start >= s['t'] - 2 or key in keyed or progress.parent_key(key) in unkeyed, (s['label'], key)


def q_contract_and_determinism():
    # Replicata: estimate() on every state, twice.
    # Expectata: a 1-d float array, empty or REPLICATES long, finite and nonnegative; the same both times.
    for s in states():
        x, y = progress.estimate(s), progress.estimate(s)
        assert type(x) is np.ndarray and x.ndim == 1 and len(x) in (0, progress.REPLICATES), s['label']
        assert np.isfinite(x).all() and (x >= 0).all() and (x == y).all(), s['label']


def q_no_estimate_exactly_where_nothing_is_known():
    # Replicata: estimate() on every state.
    # Expectata: empty only at the starts of 304@9 pass 1 and 240@11 pass 1 (the top node pending, no population at
    # depth 0, no leaf solved); 304@9 pass 2 has an estimate from its start (its 24 re-solves, from the gap ball and
    # pass 1's speed).
    empty = [s['label'] for s in states() if not len(progress.estimate(s))]
    assert empty == ['304@9 p1 +0.0h', '240@11 p1 +0.0h'], empty


def q_parts_add_up():
    # Replicata: estimate() with parts on every state that has an estimate.
    # Expectata: the loads and items sum to the top node's remaining work (also asserted inside); the makespan is at
    # least the work over the workers and at least the largest load, and at most that share plus the largest load or
    # job (Graham 1966); every leaf's drawn cost lies at or below the largest of the gap's top, the largest member and
    # the longest elapsed time of a running leaf, and a running leaf's at or above its own elapsed time.
    for s in states():
        parts = {}
        x = progress.estimate(s, parts)
        if not len(x): continue
        span, work, loads = x * 3600, parts['work'], parts['loads']
        P = s['processes']
        assert (span >= work / P - 1e-6).all() and (span >= loads.max(axis=1) - 1e-6).all(), s['label']
        biggest = np.max([loads.max(axis=1)] + [v for k, v in parts['items'] if k == 'job'], axis=0)
        assert (span <= work / P + biggest + 1e-6).all(), s['label']
        longest = max([s['t'] - n.start for n, k in parts['kinds'].items() if k == 'leaf' and n.state == 'running'], default=0)
        top = max(parts['gap'][1], parts['members'].max() if len(parts['members']) else 0, longest)
        for node, kind in parts['kinds'].items():
            if kind == 'leaf':
                ran = s['t'] - node.start if node.state == 'running' else 0
                v = parts['rem'][node] + ran
                assert (v <= top + 1e-6).all() and (v >= ran - 1e-6).all(), (s['label'], node.key)


def q_pass2_leaves_keep_their_bracket():
    # Replicata: 304@9 pass 2's states.
    # Expectata: the leaf floor is pass 1's bottom budget, 2,000,000; every member (a re-solve finished in this pass)
    # exceeds the floor's seconds at the speed, (2,000,000 + 1) x speed; every pending re-solve's draw is at least that;
    # every running one's remaining work is nonnegative.
    for s in states():
        if not s['label'].startswith('304@9 p2'): continue
        parts = {}
        progress.estimate(s, parts)
        assert parts['floor'] == 2_000_000, parts['floor']
        low = (2_000_000 + 1) * parts['speed']
        assert (parts['members'] > low).all(), s['label']
        for node, kind in parts['kinds'].items():
            if kind != 'leaf': continue
            v = parts['rem'][node]
            assert (v >= 0).all() if node.state == 'running' else (v >= low - 1e-6).all(), (s['label'], node.key)


def q_mean_is_finite_and_samples_bounded():
    # Replicata: estimate() on every state with one.
    # Expectata: a finite mean; no sample above the remaining work all on one worker.
    for s in states():
        parts = {}
        x = progress.estimate(s, parts)
        if len(x): assert np.isfinite(x.mean()) and (x * 3600 <= parts['work'] + 1e-6).all(), s['label']


def q_past_points_need_only_the_log_cut_at_t():
    # Replicata: every state of 304@9; the same state built from the run's files as they were at its time (the log's
    # lines up to it, the records dated by them), so that a forecast as of a past time can be made from today's files.
    # Expectata: the same samples.
    R, cache = live(304, 9)
    for s in states():
        if not s['label'].startswith('304@9'): continue
        lines = bisect.bisect_right(R['stamps'], s['t'])
        J = sum(1 for d in R['dates'] if d < lines)
        then = dict(R, lines=R['lines'][:lines], stamps=R['stamps'][:lines], kinds=R['kinds'][:lines],
                    records=R['records'][:J], dates=R['dates'][:J])
        assert (progress.estimate(progress.state_at(then, s['t'], cache, s['label'])) == progress.estimate(s)).all(), s['label']


def q_runtime_fits_the_refresh_loop():
    # Replicata: estimate() on the last state of each live run, at this process's niceness.
    # Expectata: under 2 s of CPU each.
    for prefix in ('304@9 p2', '240@11 p1'):
        s = [x for x in states() if x['label'].startswith(prefix)][-1]
        c0 = time.process_time()
        progress.estimate(s)
        assert time.process_time() - c0 < 2, (s['label'], time.process_time() - c0)


# ---------- surveys of the tiny runs ----------

def q_survey_of_an_ended_open_run():
    # Replicata: the tiny open run (64@7, ended NOT FINISHED), with no process running.
    # Expectata: ended, with the log's outcome; 3 settled (the log's closed count), 7 open, and the open list the
    # seven keys of the log's open lines, each at budget 3; every level enumerated; no estimate and no work counts.
    journal, log = tiny('open')
    s = progress.survey(64, 7, journal, log, [], time.time(), {}, {})
    p, = progress.parse_log(log)
    assert s['state'] == 'ended' and s['outcome'] == p['outcome'] and s['draws'] is None and s['work'] is None
    assert (s['settled'], s['open']) == (3, 7) and sorted(k for k, _, _ in s['open_list']) == sorted(p['opens'])
    assert {(b, st) for _, b, st in s['open_list']} == {(3, 'open')}
    assert all(r['enumerated'] for r in s['levels']) and s['deepest'] == 2
    assert sum(r['counts']['open'] for r in s['levels']) == 7


def q_survey_of_a_resolving_run():
    # Replicata: the tiny open run's files plus the start line of a pass with bottom budget 100000, the process
    # running, 30 s after that start line.
    # Expectata: running, no outcome; the seven leaves left open at budget 3 are now pending (solved again in this
    # pass), so 0 open; the open list still names them, each pending; the bottom level is the deepest enumerated, with
    # 7 pending; this pass's work is those 7, none done; the estimate draws all 7 from the gap, each between one LP
    # solve past the floor (3) and the bottom budget (100000), at pass 1's speed, one after another on the one worker.
    journal, log = tiny('resolving')
    passes = progress.parse_log(log)
    procs = [(1, 0, 'S', 'python3 overnight_v5.py 64 7')]
    cache = {}
    s = progress.survey(64, 7, journal, log, procs, passes[-1]['start'] + 30, cache, {})
    assert s['state'] == 'running' and s['outcome'] is None and s['open'] == 0, s
    assert len(s['open_list']) == 7 and {st for _, _, st in s['open_list']} == {'pending'}
    assert s['deepest'] == 2 and s['levels'][2]['counts']['pending'] == 7
    assert (s['work']['work'], s['work']['done']) == (7, 0), s['work']
    assert s['elapsed'] == 30 and s['waiting'] is None
    speed = progress.speed(progress.state_at(progress.read_run(journal, log), passes[-1]['start'] + 30, cache, 'resolving'))
    assert len(s['draws']) == progress.REPLICATES and passes[-1]['budgets'][-1] == 100000, (len(s['draws']), passes[-1]['budgets'])
    assert (s['draws'] * 3600 >= 7 * 4 * speed - 1e-9).all() and (s['draws'] * 3600 <= 7 * 100000 * speed + 1e-9).all()


def q_survey_records_its_eta():
    # Replicata: the tiny resolving run (64@7, running, its pass 2 just begun) surveyed 30 s and then 40 s into that
    # pass, with one record (a dict); the tiny open run (ended) surveyed with another, empty.
    # Expectata: the first record holds exactly the two snapshots' ETAs, each [its survey's mean draw, then the
    # draws' QUANTILES], by its time in whole seconds, and is the surveys' etas; the ended run's holds one None, by its
    # last line's time (an ended run has no estimate).
    journal, log = tiny('resolving')
    start = progress.parse_log(log)[-1]['start']
    procs = [(1, 0, 'S', 'python3 overnight_v5.py 64 7')]
    etas = {}
    a = progress.survey(64, 7, journal, log, procs, start + 30, {}, etas)
    b = progress.survey(64, 7, journal, log, procs, start + 40, {}, etas)
    def eta(d): return [float(d.mean())] + [float(q) for q in np.quantile(d, progress.QUANTILES)]
    assert etas == {str(int(start + 30)): eta(a['draws']), str(int(start + 40)): eta(b['draws'])}, etas
    assert a['etas'] is etas and b['etas'] is etas
    journal, log = tiny('open')
    ended = {}
    progress.survey(64, 7, journal, log, [], time.time(), {}, ended)
    assert ended == {str(int(progress.parse_log(log)[-1]['last'])): None}, ended


PASS2 = {}                                    # 240@11's pass 2 survey, made once per process (see pass2)
PASS2_AT = '2026-10-10 22:40:10'              # a time in 240@11's pass 2 (begun 22:27:36), now past, so fixed


def pass2():
    """240@11 surveyed at PASS2_AT, running, from its files as they were then (the log's lines up to it and the records
    dated by them, written to a temporary directory: survey takes the files' last pass for the current one, and the
    run has had later passes) and its cached splits minus those of every node the journal had UNKNOWN within its
    budget above the bottom when pass 2 began (the resplit nodes), with DEEPEST 0, so that the survey must make them;
    made once (it splits nodes as deep as level 7, several CPU-minutes), as_written.  Returns the survey, the resplit
    keys, the cache the survey filled, and read_run's R of the files as they were."""
    if not PASS2:
        with as_written(240, 11):
            t = progress.stamp(PASS2_AT)
            now = progress.read_run(v5.JOURNAL, v5.LOG)
            lines = bisect.bisect_right(now['stamps'], t)
            d = tempfile.mkdtemp(prefix='progress-quals-')
            journal, log = os.path.join(d, 'journal.jsonl'), os.path.join(d, 'run.log')
            open(log, 'w').write(''.join(line + '\n' for line in now['lines'][:lines]))
            records = now['records'][:sum(1 for x in now['dates'] if x < lines)]
            open(journal, 'w').write(''.join(json.dumps(r) + '\n' for r in [v5.header()] + records))
            R = progress.read_run(journal, log)
            assert len(R['records']) == len(records)
            assert len(R['passes']) == 2 and R['passes'][1]['start'] <= t
            budgets = R['passes'][1]['budgets']
            start = {r['key']: r for r in R['records'][:R['bounds'][1]]}
            resplit = sorted(key for key, r in start.items() if r['verdict'] == 'UNKNOWN' and len(key.split()) < len(budgets) - 1
                             and r['budget'] >= progress.budget_of(key, budgets))
            cache = {key: c for key, c in progress.load_cache(progress.CACHE)[f'240_11_{v5.CODE}'].items() if key not in resplit}
            procs = [(1, 0, 'S', 'python3 overnight_v5.py 240 11')]
            saved = progress.DEEPEST
            progress.DEEPEST = 0
            try:
                s = progress.survey(240, 11, journal, log, procs, t, cache, {})
            finally:
                progress.DEEPEST = saved
        PASS2.update(s=s, resplit=resplit, cache=cache, R=R)
    return PASS2['s'], PASS2['resplit'], PASS2['cache'], PASS2['R']


def q_survey_splits_a_later_pass_s_resplit_nodes_first():
    # Replicata: pass2(): the live 240@11 run surveyed in its pass 2 with the splits of its resplit nodes taken out of
    # the cache and DEEPEST 0.
    # Expectata: the survey made and cached the split of every resplit node, each equal to overnight_v5.split's, and
    # gave an estimate (draws) without failing.
    s, resplit, cache, R = pass2()
    assert resplit and all(key in cache for key in resplit), [key for key in resplit if key not in cache][:3]
    for key in resplit[:3]:
        assert cache[key] == [v5.node_key(c) for c in v5.split(11, progress.parse_key(key))], key
    assert s['draws'] is not None, s['state']


def q_replay_counts_skips_by_the_closed_count():
    # Replicata: pass2()'s run as of PASS2_AT, whose pass 2 splits nodes new to the journal (their splits not cached)
    # while it skips the nodes the journal already settles.
    # Expectata: the replay accounts for every progress line: the skips between two lines are the rise of the log's
    # closed count less one for the line's own INFEASIBLE, and a line's children the rest of its waiting count's
    # change; at least one line splits a node whose split is not cached, and at least one pop is a skip; every line's
    # waiting and running match (asserted inside), and at most the pass's processes run.
    s, resplit, cache, R = pass2()
    state = progress.state_at(R, progress.stamp(PASS2_AT), cache, '240@11 p2')
    nodes = state['passes'][-1]['nodes']
    assert any(nd['verdict'] == 'UNKNOWN' and len(nd['key'].split()) < 8 and nd['key'] not in cache for nd in nodes), 'no uncached split'
    root, stack, running = progress.replay(state)
    def walk(n): return [n] + [m for c in n.kids for m in walk(c)]
    assert any(n.state == 'skipped' for n in walk(root)) and len(running) <= state['processes'], len(running)


# ---------- the record of ETAs ----------

def eta_chart_case():
    """The tiny resolved run (64@7: two passes, ended) surveyed, its passes set to 11.6 h and 1.6 h of running (from 0
    and from 86400 s) and its record of ETAs to three: [2, 1, 4] h (mean, then the band's ends) at 0 s (pass 1's
    start), none (None) at pass 1's end, and [1, 0.5, 3] h at pass 2's end (the case of the ETA chart of progress.html,
    which index.html's section "Search progress" took over on 2026-10-17)."""
    journal, log = tiny('resolved')
    s = progress.survey(64, 7, journal, log, [], time.time(), {}, {})
    return dict(s, passes=[(0.0, 11.6 * 3600), (86400.0, 86400 + 1.6 * 3600)],
                etas={'0': [2.0, 1.0, 4.0], str(int(11.6 * 3600)): None, str(int(86400 + 1.6 * 3600)): [1.0, 0.5, 3.0]})


def q_eta_records_put_a_record_after_a_pass_s_last_line_at_its_end():
    # Replicata: eta_chart_case() with one more ETA, [3, 2, 5] h, recorded 1000 s after pass 1's last line (as the
    # watcher records one while a pass's process runs on past its last line, or after it is stopped); then the same
    # with a record after the snapshot's time instead.
    # Expectata: progress.eta_records gives the first at pass 1's end (11.6 h of running), between the records before
    # and after it in time, the None left out; the second fails with AssertionError (no ETA can be made after the
    # snapshot).  (Until 2026-10-17, progress.html's ETA chart drew it there.)
    s = eta_chart_case()
    late = dict(s, etas=dict(s['etas'], **{str(int(11.6 * 3600 + 1000)): [3.0, 2.0, 5.0]}))
    got = [(round(x, 6), m, lo, hi) for _, x, m, lo, hi in progress.eta_records(late)]
    assert got == [(0.0, 2.0, 1.0, 4.0), (11.6, 3.0, 2.0, 5.0), (13.2, 1.0, 0.5, 3.0)], got
    after = dict(s, etas=dict(s['etas'], **{str(int(86400 + 1.6 * 3600 + 60)): [1.0, 0.5, 3.0]}))
    expect_assertion(progress.eta_records, after)


# ---------- writing ----------

def q_write_atomic():
    # Replicata: a 4 MB page written 20 times with write_atomic, alternating two contents, while another thread
    # reads the file as fast as it can.
    # Expectata: every read is one content or the other, whole; after each write the file is a new inode (a rename,
    # not a rewrite in place) holding the content; no temporary file is left behind.
    d = tempfile.mkdtemp(prefix='progress-quals-')
    path = os.path.join(d, 'page.html')
    texts = ['a' * 4_000_000 + '\n', 'b' * 4_000_000 + '\n']
    progress.write_atomic(path, texts[1])
    seen, stop = collections.Counter(), threading.Event()
    def reader():
        while not stop.is_set():
            t = open(path).read()
            seen['whole' if t in texts else 'partial'] += 1
    th = threading.Thread(target=reader)
    th.start()
    try:
        for i in range(20):
            before = os.stat(path).st_ino
            progress.write_atomic(path, texts[i % 2])
            assert os.stat(path).st_ino != before and open(path).read() == texts[i % 2]
    finally:
        stop.set()
        th.join()
    assert seen['partial'] == 0 and seen['whole'] > 0, seen
    assert os.listdir(d) == ['page.html'], os.listdir(d)


def q_watch_rewrites_and_sleeps():
    # Replicata: progress.main(['--watch']) with the tiny closed run as its only run, its data file (progress.js) and
    # cache in a temporary directory, and time.sleep replaced by a stub that stops the loop at its second call; then
    # main(['--bogus']).
    # Expectata: the data file is written twice with the run in it (2026-10-17: index.html's section reads it, in place
    # of the page progress.html), the stub sees 60 s each time, the cache
    # file holds the run's splits and its record of ETAs, and this process now runs at nice 15 or more; a bad
    # argument fails with AssertionError.
    d = tempfile.mkdtemp(prefix='progress-quals-')
    saved = (progress.RUNS, progress.JS, progress.CACHE, progress.files, time.sleep)
    sleeps, writes = [], []
    class Stop(Exception): pass
    def stub(s):
        sleeps.append(s)
        writes.append(os.stat(progress.JS).st_mtime_ns)
        if len(sleeps) == 2: raise Stop
    progress.RUNS, progress.JS, progress.CACHE = ((40, 6),), os.path.join(d, 'p.js'), os.path.join(d, 'c.json')
    progress.files = lambda n, order: tiny('closed')
    time.sleep = stub
    try:
        progress.main(['--watch'])
    except Stop:
        pass
    finally:
        progress.RUNS, progress.JS, progress.CACHE, progress.files, time.sleep = saved
    assert sleeps == [60, 60] and len(writes) == 2, (sleeps, writes)
    assert [r['n'] for r in progress_data(open(os.path.join(d, 'p.js')).read())['runs']] == [40]
    assert sorted(os.listdir(d)) == ['c.json', 'p.js'], os.listdir(d)
    assert list(json.load(open(os.path.join(d, 'c.json')))) == [f'40_6_{v5.CODE}', f'40_6_{v5.CODE}_etas']
    assert os.nice(0) >= 15
    expect_assertion(progress.main, ['--bogus'])


# ---------- the data file of index.html's section "Search progress" (dreeves, 2026-10-17) ----------

def tree_tokens(key):
    """A key's constraints as comparable tuples, an order made here apart from progress.py's: a count vector
    M:[a,b,...] as (M, 0, (a, b, ...), ''), a pool M:#c:sha1 as (M, 1, (c,), sha1).  Parents sort before children."""
    out = []
    for t in key.split():
        M, v = t.split(':', 1)
        out.append((int(M), 0, tuple(int(x) for x in v[1:-1].split(',')), '') if v.startswith('[') else
                   (int(M), 1, (int(v.split(':')[0][1:]),), v.split(':')[1]))
    return tuple(out)


def frontier_sea(final, depth):
    """The sea of an ended run, made here apart from progress.sea: the journal's keys, less those below an INFEASIBLE
    key, that no other key extends (none of its constraints a prefix of another's), a settled dot per INFEASIBLE one and
    an open dot per UNKNOWN one, grouped by their first depth constraints (a shallower key its own group), groups and
    dots in tree_tokens order: (group keys, strings of status indices)."""
    infeasible = [k for k, r in final.items() if r['verdict'] == 'INFEASIBLE']
    under = lambda k, a: k != a and (a == '' or k.startswith(a + ' '))
    tops = {k for k in infeasible if not any(under(k, ' '.join(k.split()[:i])) for i in range(len(k.split()))
                                              if ' '.join(k.split()[:i]) in final and final[' '.join(k.split()[:i])]['verdict'] == 'INFEASIBLE')}
    keys = sorted((k for k in final if not any(' '.join(k.split()[:i]) in tops for i in range(len(k.split())))), key=tree_tokens)
    front = [k for i, k in enumerate(keys) if not (i + 1 < len(keys) and (k == '' or keys[i + 1].startswith(k + ' ')))]
    groups = collections.OrderedDict()
    for k in front:
        g = ' '.join(k.split()[:depth])
        assert final[k]['verdict'] in ('INFEASIBLE', 'UNKNOWN'), (k, final[k])
        groups.setdefault(g, []).append(str(progress.SEA_STATUSES.index('settled' if final[k]['verdict'] == 'INFEASIBLE' else 'open')))
    return list(groups), [''.join(s) for s in groups.values()]


def progress_data(text):
    """The JSON of a data file's one call, progressData(...);, asserted to be all of the text."""
    m = re.fullmatch(r'progressData\((.*)\);\n', text, re.S)
    assert m, text[:200]
    return json.loads(m.group(1))


def q_levels_skip_records_below_an_infeasible_sub_case():
    # Replicata: a made-up journal with budgets 10 at every depth (bottom 2): the top node UNKNOWN at 10, split (cached)
    # into A and B; A split once (its child A1 INFEASIBLE at 10) and re-solved INFEASIBLE at 20 since, as the width
    # test did to six of 240@11's sub-cases on 2026-10-11, so A1's record is stale; B UNKNOWN at 10, split (cached) into
    # B1, an UNKNOWN leaf at 10; progress.enumerate_levels and level_rows on it, and progress.live_keys.
    # Expectata: the live keys are all but A1; level 2 is B1 alone, A1 left out (240@11's ended run had made level_rows
    # fail its assertion that every journal key of an enumerated level is a sub-case of it, the watcher's end on
    # 2026-10-16); level 1 counts A settled and B split, level 2 B1 open.
    A, B = '3:[1,1,1]', '3:[2,1,0]'
    A1, B1 = A + ' 5:[1,0,0,0,0]', B + ' 5:[0,1,0,0,0]'
    rec = lambda verdict, budget: {'verdict': verdict, 'budget': budget}
    final = {'': rec('UNKNOWN', 10), A: rec('INFEASIBLE', 20), A1: rec('INFEASIBLE', 10), B: rec('UNKNOWN', 10),
             B1: rec('UNKNOWN', 10)}
    budgets = [10, 10, 10]
    assert progress.live_keys(final) == {'', A, B, B1}, progress.live_keys(final)
    levels = progress.enumerate_levels(final, budgets, 7, {'': [A, B], B: [B1]}, 6)
    assert levels == [[''], [A, B], [B1]], levels
    rows = progress.level_rows(levels, final, budgets, 2)
    assert [r['counts'] for r in rows] == [{'settled': 0, 'open': 0, 'split': 1, 'pending': 0},
                                           {'settled': 1, 'open': 0, 'split': 1, 'pending': 0},
                                           {'settled': 0, 'open': 1, 'split': 0, 'pending': 0}], rows


def q_sea_of_an_ended_open_run():
    # Replicata: the tiny open run (64@7, ended NOT FINISHED), surveyed with no process running.
    # Expectata: its sea (progress.sea, the dots of index.html's section) is frontier_sea of its journal at the sea's
    # depth (progress.SEA_DEPTH, or the depth above the bottom if that is shallower): one dot per sub-case the search
    # left without children, a settled one per INFEASIBLE record and an open one per open leaf, none split, pending or
    # running, in tree order and grouped by their sub-case at that depth; and the counts are those dots'.
    journal, log = tiny('open')
    s = progress.survey(64, 7, journal, log, [], time.time(), {}, {})
    final = progress.read_journal(journal)
    sea = s['sea']
    assert sea['depth'] == min(progress.SEA_DEPTH, len(v5.CASCADE) - 1), sea['depth']
    assert (sea['keys'], sea['groups']) == frontier_sea(final, sea['depth']), sea
    assert sea['counts'] == {'settled': sum(r['verdict'] == 'INFEASIBLE' for r in final.values()), 'open': 7, 'split': 0,
                             'pending': 0, 'running': 0}, sea['counts']


def q_sea_marks_split_pending_and_running():
    # Replicata: progress.sea on a made-up journal with budgets 10 at every depth (bottom 2, so its depth is 1): the top
    # node UNKNOWN at 10, its cached children A..E; A INFEASIBLE; B UNKNOWN at 10, its cached children B1 (UNKNOWN at
    # 10, a leaf) and B2 (no record); C UNKNOWN at 10 with no cached split and no recorded children; D no record and
    # running; E UNKNOWN at 5, an earlier budget.
    # Expectata: groups in tree order E, C, A, B, D: E pending (its budget is old), C split (children unknown), A
    # settled, B its two children B2 pending and B1 open, D running; counts 1 settled, 1 open, 1 split, 2 pending,
    # 1 running.
    A, B, C, D, E = '3:[1,1,1]', '3:[2,1,0]', '3:[0,1,2]', '3:[3,0,0]', '3:[0,0,3]'
    B1, B2 = B + ' 5:[1,0,0,0,0]', B + ' 5:[0,1,0,0,0]'
    rec = lambda verdict, budget: {'verdict': verdict, 'budget': budget}
    final = {'': rec('UNKNOWN', 10), A: rec('INFEASIBLE', 10), B: rec('UNKNOWN', 10), B1: rec('UNKNOWN', 10),
             C: rec('UNKNOWN', 10), E: rec('UNKNOWN', 5)}
    cache = {'': [A, B, C, D, E], B: [B1, B2]}
    sea = progress.sea(final, [10, 10, 10], cache, {D})
    i = lambda *names: ''.join(str(progress.SEA_STATUSES.index(n)) for n in names)
    assert sea['depth'] == 1 and sea['keys'] == [E, C, A, B, D], sea
    assert sea['groups'] == [i('pending'), i('split'), i('settled'), i('pending', 'open'), i('running')], sea['groups']
    assert sea['counts'] == {'settled': 1, 'open': 1, 'split': 1, 'pending': 2, 'running': 1}, sea['counts']


def q_sea_of_240_at_11():
    # Replicata (regression): progress.sea of 240@11's journal as its run ended (2026-10-16 23:59, NOT FINISHED: 606
    # nodes left open), under its last pass's budgets, no cache, nothing running.
    # Expectata: frontier_sea of the journal at depth 5: 71494 settled dots (its 73185 INFEASIBLE records less the
    # 1691 below six sub-cases that a pass split and a later one re-solved INFEASIBLE, in 3 LP solves each, once the
    # width test came in on 2026-10-11) and 606 open (its open leaves), in 296 groups (its 291 sub-cases at depth 5
    # and 5 settled above them).
    v5.configure(240, 11)
    final = progress.read_journal(v5.JOURNAL)
    budgets = progress.parse_log(v5.LOG)[-1]['budgets']
    sea = progress.sea(final, budgets, {}, set())
    assert sea['depth'] == 5 and (sea['keys'], sea['groups']) == frontier_sea(final, 5)
    assert sea['counts'] == {'settled': 73185 - 1691, 'open': 606, 'split': 0, 'pending': 0, 'running': 0}, sea['counts']
    assert len(sea['groups']) == 296, len(sea['groups'])


def q_js_is_one_progress_data_call():
    # Replicata: progress.js_text for the surveys of the tiny open and closed runs at a fixed time.
    # Expectata: one call, progressData(...);, of JSON with made (the time, in whole seconds) and runs, each with n,
    # order, state, so_far (its passes' seconds of running), to_go (null: no estimate for an ended run), etas (none
    # recorded here) and its sea (depth, keys, groups, counts, as progress.sea gives it) with the statuses' names, and
    # nothing else.
    now = 1792200000.25
    surveys = [progress.survey(n, order, *tiny(name), [], now, {}, {}) for n, order, name in ((64, 7, 'open'), (40, 6, 'closed'))]
    data = progress_data(progress.js_text(surveys, now))
    assert set(data) == {'made', 'runs'} and data['made'] == 1792200000, data.keys()
    for r, s in zip(data['runs'], surveys):
        assert set(r) == {'n', 'order', 'state', 'so_far', 'to_go', 'etas', 'statuses', 'depth', 'keys', 'groups', 'counts'}, set(r)
        assert (r['n'], r['order'], r['state'], r['to_go'], r['etas']) == (s['n'], s['order'], 'ended', None, []), r
        assert r['so_far'] == sum(b - a for a, b in s['passes']) > 0, (r['so_far'], s['passes'])
        assert r['statuses'] == list(progress.SEA_STATUSES)
        assert {k: r[k] for k in ('depth', 'keys', 'groups', 'counts')} == s['sea'], r
        assert sum(r['counts'].values()) == sum(map(len, r['groups']))



def q_js_etas_are_the_record_on_running_time():
    # Replicata: the tiny closed run (40@6, two passes, the second of no length) surveyed with a made-up record of ETAs
    # (hours: mean, lo, hi) at 600 times of its first pass, one of them with no estimate, and progress.js_text of it.
    # Expectata: the run's etas are the record's estimates in time order, the one with none left out (and the survey's
    # own record of its snapshot, none for an ended run), as [the time, seconds of running before it, mean, lo, hi], the
    # time in whole seconds and the rest to a tenth, thinned to at most progress.ETA_POINTS without repeats, the last always kept; a time's running
    # seconds are its time less the first pass's start.
    journal, log = tiny('closed')
    passes = progress.parse_log(log)
    a, b = passes[0]['start'], passes[0]['last']
    assert b > a, passes
    times = [a + (b - a) * i / 599 for i in range(600)]
    etas = {repr(t): [1.0 + i, 0.5 + i, 2.0 + i] for i, t in enumerate(times)}
    etas[repr(times[300])] = None
    s = progress.survey(40, 6, journal, log, [], passes[-1]['last'] + 5, {}, etas)
    got = progress_data(progress.js_text([s], passes[-1]['last'] + 5))['runs'][0]['etas']
    want = sorted((int(float(t)), float(t) - a, *(3600 * v for v in e)) for t, e in etas.items() if e is not None)
    near = lambda g, w: all(abs(x - y) <= 0.051 for x, y in zip(g, w))          # seconds to a tenth
    assert len(got) <= progress.ETA_POINTS and near(got[-1], want[-1]), (len(got), got[-1:], want[-1:])
    assert all(any(near(g, w) for w in want) for g in got), got[:5]
    assert [g[1] for g in got] == sorted(g[1] for g in got) and len({tuple(g) for g in got}) == len(got), got[:5]

# ---------- runner ----------

def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0, c0 = time.time(), time.process_time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds and this process's CPU seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds and this process's CPU seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
