#!/usr/bin/env python3
"""Quals for the stages to a recordable result (progress.py's chain, share and stages, and stages.json; the
coordinator, 2026-10-31, after the page's ETA had covered only the stage running, twice in two days).
Run: python3 -B quals_stages.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata
(the setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened
instead).
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, math, shutil, tempfile, traceback, contextlib
import numpy as np
import overnight_v5 as v5
import fanout
import progress

# the commands, as ps shows them, of a worker multiprocessing spawned and of its resource tracker (a child too)
WORKER = 'Python -B -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=5, pipe_handle=7) --multiprocessing-fork'
TRACKER = 'Python -B -c from multiprocessing.resource_tracker import main;main(4)'


def made_up(run, *later):
    """A made-up STAGES: one chain, the run (program, n, order), then each later stage given as (its name, its parts,
    each (per, processes, cpu)), every part with made-up provenance."""
    return [[dict(stage=run[0], run=list(run))] +
            [dict(stage=name, parts=[dict(per=per, processes=k, cpu=cpu, source='a qual', date='2026-10-31',
                                          conditions='made up') for per, k, cpu in parts]) for name, parts in later]]


def point(c):
    """A cost known exactly: its median, low and high ends c."""
    return dict(median=c, lo=c, hi=c)


@contextlib.contextmanager
def chains(made):
    """progress.STAGES set to made, restored after."""
    saved = progress.STAGES
    progress.STAGES = made
    try: yield
    finally: progress.STAGES = saved


def close(a, b, rel=1e-9):
    """Whether two to_go dicts (or None) agree to rel."""
    return (a is None) == (b is None) and (a is None or (set(a) == set(b) and all(math.isclose(a[k], b[k], rel_tol=rel) for k in a)))


def q_stages_file_names_each_search_s_chain():
    # Replicata: progress.STAGES, the repository's stages.json as progress.py loads it.
    # Expectata (the coordinator, 2026-10-31): two chains, 432:12's (fanout.py's run, then fanout.assemble, then
    # reprove.py) and 288:10's (overnight_v5.py's run, then boxsplit.py, a run of its own too, then handoff288.py, then
    # overnight_v5.py's final pass); 432:12's parts per token, 288:10's per open leaf; reprove.py's reproofs on
    # fanout.WORKERS processes and its assembly on one, as fanout.assemble's; boxsplit.py's and the final pass's on
    # overnight_v5's PROCESSES (the machine's cores), handoff288.py on one; every part's provenance written out.
    names = [[s['stage'] for s in chain] for chain in progress.STAGES]
    assert names == [['fanout.py', 'fanout.assemble', 'reprove.py'],
                     ['overnight_v5.py', 'boxsplit.py', 'handoff288.py', 'overnight_v5.py']], names
    runs = [[s.get('run') for s in chain] for chain in progress.STAGES]
    assert runs == [[['fanout.py', 432, 12], None, None],
                    [['overnight_v5.py', 288, 10], ['boxsplit.py', 288, 10], None, None]], runs
    shape = [[[(p['per'], p['processes']) for p in s.get('parts', [])] for s in chain] for chain in progress.STAGES]
    assert shape == [[[], [('token', 1)], [('token', 1), ('token', fanout.WORKERS)]],
                     [[], [('open leaf', v5.PROCESSES)], [('open leaf', 1)], [('open leaf', v5.PROCESSES)]]], shape
    assert all(len(p[k]) > 20 for chain in progress.STAGES for s in chain for p in s.get('parts', [])
               for k in ('source', 'conditions')), progress.STAGES


def q_a_later_stage_is_its_counts_times_its_cpu_over_processes_and_share():
    # Replicata: a made-up chain of 672:13's fanout.py run, then stage A (one part per token: 2 processes, 0.5 CPU s a
    # token) and stage B (two parts per token: 1 process at 0.001 CPU s, 4 at 0.002); stages_of for the run running,
    # its own to_go 3 h, its estimate 3 h in every replicate, 7,200 tokens in every replicate, a share of 0.5.
    # Expectata: stages, the run's own first (fanout.py, its to_go as given), then A, 7200 x 0.5 / (2 x 0.5) s = 1 h,
    # then B, 7200 x 0.001 / (1 x 0.5) + 7200 x 0.002 / (4 x 0.5) = 21.6 s, each its median, low and high alike; the
    # total 3 h + 1 h + 21.6 s.
    run = ('fanout.py', 672, 13)
    own = dict(median=3 * 3600.0, lo=3 * 3600.0, hi=3 * 3600.0)
    hours = np.full(progress.REPLICATES, 3.0)
    with chains(made_up(run, ('A', [('token', 2, point(0.5))]), ('B', [('token', 1, point(0.001)), ('token', 4, point(0.002))]))):
        got = progress.stages_of(run, 'running', own, hours, {'token': np.full(progress.REPLICATES, 7200.0)}, 0.5)
    assert [s['name'] for s in got['stages']] == ['fanout.py', 'A', 'B'] and got['stages'][0]['to_go'] is own, got
    want = [3600.0, 21.6]
    for s, w in zip(got['stages'][1:], want):
        assert close(s['to_go'], dict(median=w, lo=w, hi=w)), (s, w)
    assert close(got['total'], {k: 3 * 3600.0 + sum(want) for k in ('median', 'lo', 'hi')}), got['total']


def q_a_later_stage_s_band_is_its_cost_s_measured_band():
    # Replicata: a made-up chain of 672:13's fanout.py run with one later stage, one part per token on 1 process
    # measured at a median of 2 CPU s, 1 at its low end and 8 at its high end (QUANTILES' 5% and 95%); stages_of with
    # 3,600 tokens and a share of 1, the run's estimate 0 h in every replicate.  And drawn of that cost, 400,000 draws.
    # Expectata: the stage's median, low and high near 2, 1 and 8 h (the replicates' quantiles, within 10%: 2,000
    # draws), the total the same; the 400,000 draws' quantiles within 1% of 1, 2 and 8: a two-piece log-normal whose
    # quantiles are the measured ones, however lopsided.
    run = ('fanout.py', 672, 13)
    with chains(made_up(run, ('A', [('token', 1, dict(median=2.0, lo=1.0, hi=8.0))]))):
        got = progress.stages_of(run, 'running', None, np.zeros(progress.REPLICATES), {'token': 3600.0}, 1.0)
    for k, w in (('median', 2.0), ('lo', 1.0), ('hi', 8.0)):
        assert math.isclose(got['stages'][1]['to_go'][k], w * 3600, rel_tol=0.1), (k, got['stages'][1])
    assert close(got['total'], got['stages'][1]['to_go']), got
    q = np.quantile(progress.drawn(np.random.default_rng(1), dict(median=2.0, lo=1.0, hi=8.0), 400000), (0.05, 0.5, 0.95))
    assert np.allclose(q, (1.0, 2.0, 8.0), rtol=0.01), q


def q_a_run_ended_or_in_no_chain_has_no_stages():
    # Replicata: stages_of for 672:13's fanout.py run in a made-up chain, ended; and for a run in no chain, running.
    # Expectata: {} for both: the data file gets no stages, and the page shows nothing more for a run of one stage.
    run = ('fanout.py', 672, 13)
    with chains(made_up(run, ('A', [('token', 1, point(1.0))]))):
        assert progress.stages_of(run, 'ended', None, None, {'token': None}, None) == {}
        assert progress.stages_of(('fanout.py', 480, 14), 'running', None, np.zeros(3), {'token': 1.0}, 1.0) == {}


def q_no_estimate_without_hours_or_a_share():
    # Replicata: stages_of for 672:13's fanout.py run in a made-up chain of two later stages, paused with no estimate
    # (no hours, no count); then running, its estimate and count given but no share (no live worker).
    # Expectata: the stages named, each later one with no estimate (to_go None), and no total; the run's own to_go as
    # given (None, then 1 h).
    run = ('fanout.py', 672, 13)
    own = dict(median=3600.0, lo=1800.0, hi=7200.0)
    with chains(made_up(run, ('A', [('token', 1, point(1.0))]), ('B', [('token', 1, point(1.0))]))):
        a = progress.stages_of(run, 'paused', None, None, {'token': None}, 0.5)
        b = progress.stages_of(run, 'running', own, np.ones(3), {'token': np.ones(3)}, None)
    assert a == {'stages': [dict(name='fanout.py', to_go=None), dict(name='A', to_go=None), dict(name='B', to_go=None)],
                 'total': None}, a
    assert b == {'stages': [dict(name='fanout.py', to_go=own), dict(name='A', to_go=None), dict(name='B', to_go=None)],
                 'total': None}, b


def q_a_count_the_chain_needs_must_be_given():
    # Replicata: stages_of for a run whose made-up chain's part is per open leaf, given only a count of tokens; and one
    # given the count None with an estimate.
    # Expectata: AssertionError, each: a later stage cannot be estimated from a count the run does not give.
    run = ('fanout.py', 672, 13)
    with chains(made_up(run, ('A', [('open leaf', 1, point(1.0))]))):
        for counts in ({'token': np.ones(3)}, {'open leaf': None}):
            try:
                progress.stages_of(run, 'running', None, np.ones(3), counts, 1.0)
            except AssertionError:
                continue
            raise AssertionError(f'no failure with {counts}')


def q_malformed_stages_files_fail_loudly():
    # Replicata: load_stages of a well-formed made-up file, then of copies each broken one way: a part without its
    # source, with an empty one, or with a date not text; a part per an unknown unit; a cost with lo above its median;
    # with a median of 0; 0 processes; a chain whose first stage is not a run; a later stage without parts; a first
    # stage with parts; a run whose program is not its stage's name; a run in two chains; a field the file does not
    # have.
    # Expectata: the well-formed file loads as written; every broken copy fails with an AssertionError.
    good = {'about': 'a qual', 'chains': made_up(('fanout.py', 672, 13), ('A', [('token', 1, dict(median=2.0, lo=1.0, hi=3.0))]))}
    def broken(f):
        data = json.loads(json.dumps(good))
        f(data)
        return data
    part = lambda d: d['chains'][0][1]['parts'][0]
    bad = [broken(lambda d: part(d).pop('source')), broken(lambda d: part(d).update(source='')),
           broken(lambda d: part(d).update(date=20261031)), broken(lambda d: part(d).update(per='leaf')),
           broken(lambda d: part(d)['cpu'].update(lo=2.5)), broken(lambda d: part(d)['cpu'].update(lo=0.0, median=0.0)),
           broken(lambda d: part(d).update(processes=0)), broken(lambda d: d['chains'][0][0].pop('run')),
           broken(lambda d: d['chains'][0][1].pop('parts')), broken(lambda d: d['chains'][0][0].update(parts=[])),
           broken(lambda d: d['chains'][0][0].update(stage='focus.py')),
           broken(lambda d: d['chains'].append([dict(stage='fanout.py', run=['fanout.py', 672, 13])])),
           broken(lambda d: d.update(extra=1))]
    d = tempfile.mkdtemp(prefix='stages-quals-')
    try:
        path = os.path.join(d, 'stages.json')
        open(path, 'w').write(json.dumps(good))
        assert progress.load_stages(path) == good['chains']
        for i, data in enumerate(bad):
            open(path, 'w').write(json.dumps(data))
            try:
                progress.load_stages(path)
            except AssertionError:
                continue
            raise AssertionError(f'broken file {i} loaded')
    finally:
        shutil.rmtree(d)


def q_share_is_the_workers_cpu_over_their_running():
    # Replicata: share_of for a main process 10 whose children are workers 11 and 12 (multiprocessing spawned them), a
    # resource tracker 13, and a worker 14 that is a zombie; process 20 a worker of another main; ps's times: 11 at 30
    # CPU minutes in an hour, 12 at 15 CPU minutes in 50 minutes, 13 at none in an hour, 14 and 20 an hour each; a
    # pause of the run from 1,000 s to 400 s before now.  Then the same with worker 12 gone from ps's times, with no
    # main process, and with times as ps wrote them for this process.
    # Expectata: (1800 + 900) / ((3600 - 600) + (3000 - 600)) = 0.5: the workers' CPU over their running, the pause
    # left out, the tracker, the zombie and the other run's worker left out; with 12 gone, 1800 / 3000 = 0.6; with no
    # main, None; and a real reading of ps parses.
    now = 1792200000.0
    procs = [(10, 1, 'SN', 'python3 -B fanout.py 672'), (11, 10, 'SN', WORKER), (12, 10, 'RN', WORKER),
             (13, 10, 'SN', TRACKER), (14, 10, 'Z', WORKER), (20, 19, 'SN', WORKER)]
    times = {11: ('30:00.00', '01:00:00'), 12: ('15:00.00', '50:00'), 13: ('0:00.05', '01:00:00'),
             14: ('60:00.00', '01:00:00'), 20: ('60:00.00', '01:00:00')}
    pauses = [(now - 1000, now - 400)]
    main = [procs[0]]
    assert math.isclose(progress.share_of(procs, main, pauses, now, lambda: times), 0.5), progress.share_of(procs, main, pauses, now, lambda: times)
    gone = {k: v for k, v in times.items() if k != 12}
    assert math.isclose(progress.share_of(procs, main, pauses, now, lambda: gone), 0.6)
    assert progress.share_of(procs, [], pauses, now, lambda: times) is None
    mine = progress.cpu_times()[os.getpid()]
    assert all(progress.ps_seconds(t) >= 0 for t in mine), mine


def q_ps_times_parse_and_odd_ones_fail_loudly():
    # Replicata: ps_seconds of TIME as macOS's ps writes it (minutes past 59 and hundredths: 105:40.23, 0:10.80) and of
    # ETIME (28-12:26:59, 13:04:21, 09:36); then of '-', '1:2:3:4' and '12'.
    # Expectata: 6340.23, 10.8, 2464019, 47061 and 576 s; an AssertionError for each odd one.
    for text, want in (('105:40.23', 6340.23), ('0:10.80', 10.8), ('28-12:26:59', 2464019), ('13:04:21', 47061), ('09:36', 576)):
        assert math.isclose(progress.ps_seconds(text), want), (text, progress.ps_seconds(text))
    for text in ('-', '1:2:3:4', '12'):
        try:
            progress.ps_seconds(text)
        except AssertionError:
            continue
        raise AssertionError(f'{text} parsed')


def fanout_journal(d):
    """quals_fanout_progress.drawn()'s journal of 672:13 in the directory d: 15 LP solves done (jobs a and b), the
    pool estimate 45 to go in every replicate, at 4 LP solves a second."""
    import quals_fanout_progress
    path = os.path.join(d, 'fanout_672_journal.jsonl')
    open(path, 'w').write(''.join(json.dumps(r) + '\n' for r in quals_fanout_progress.drawn()))
    return path


def q_a_fanout_s_stages_count_its_tokens():
    # Replicata: survey_fanout of quals_fanout_progress.drawn()'s journal of 672:13 at 300 s, its driver 41 alive with a
    # worker 42 that ps says used 30 CPU minutes in an hour (a share of 0.5), in a made-up chain: fanout.py's run, then
    # stage A (per token, 1 process, 0.25 CPU s) and stage B (per token, 2 processes at 0.5 CPU s, and 1 at 0.1).
    # Expectata: its stages fanout.py (its to_go, 11.25 s: 45 LP solves to go at 4 a second), A and B, its tokens 15
    # done + 45 to go = 60 in every replicate: A 60 x 0.25 / (1 x 0.5) = 30 s, B 60 x 0.5 / (2 x 0.5) + 60 x 0.1 /
    # (1 x 0.5) = 42 s; the total 83.25 s; and the run's entry in the data file carries both.
    run = ('fanout.py', 672, 13)
    procs = [(41, 1, 'SN', '/opt/homebrew/bin/python3 -B fanout.py 672'), (42, 41, 'SN', WORKER)]
    d = tempfile.mkdtemp(prefix='stages-quals-')
    try:
        with chains(made_up(run, ('A', [('token', 1, point(0.25))]), ('B', [('token', 2, point(0.5)), ('token', 1, point(0.1))]))):
            s = progress.survey_fanout(fanout_journal(d), procs, 300, {}, {}, times=lambda: {42: ('30:00.00', '01:00:00')})
    finally:
        shutil.rmtree(d)
    assert [x['name'] for x in s['stages']] == ['fanout.py', 'A', 'B'], s['stages']
    assert close(s['stages'][0]['to_go'], dict(median=11.25, lo=11.25, hi=11.25)) and s['stages'][0]['to_go'] == s['to_go'], s
    assert close(s['stages'][1]['to_go'], dict(median=30.0, lo=30.0, hi=30.0)), s['stages'][1]
    assert close(s['stages'][2]['to_go'], dict(median=42.0, lo=42.0, hi=42.0)), s['stages'][2]
    assert close(s['total'], dict(median=83.25, lo=83.25, hi=83.25)), s['total']
    entry = progress.run_data(s)
    assert (entry['stages'], entry['total']) == (s['stages'], s['total']), entry


def q_a_pass_s_stages_count_its_open_leaves_at_its_end():
    # Replicata: the tiny open run (64@7, one pass, one worker) cut at the first of its lines at which its survey,
    # running, has an estimate, open leaves and work logged (a running leaf's age: its lines log 0.0 s), surveyed a
    # second after that line, its main process 1 alive with a worker 2 that ps says used 1 CPU s in an hour (a share
    # of 1/3600), in a made-up chain: overnight_v5.py's run, then stage A per open leaf on 1 process at 1 CPU s.  The
    # growth computed apart, as the vocabulary defines it, from the estimate (progress.estimate) of the survey's own
    # reading: 1 + its work to go over its root's cost so far and history.
    # Expectata: stages overnight_v5.py (its to_go) then A, whose hours are the open leaves at the pass's end, one a
    # replicate: the survey's open leaves times the growth; the total the run's estimate plus those; and the growth at
    # least 1 in every replicate.
    import quals_progress
    journal_src, log_src = quals_progress.tiny('open')
    v5.configure(64, 7)
    R = progress.read_run(journal_src, log_src)
    records = open(journal_src).read().splitlines(keepends=True)
    lines = [l + '\n' for l in R['lines']]
    run = ('overnight_v5.py', 64, 7)
    procs = [(1, 0, 'S', 'python3 overnight_v5.py 64 7'), (2, 1, 'S', WORKER)]
    times = lambda: {2: ('0:01.00', '01:00:00')}
    d = tempfile.mkdtemp(prefix='stages-quals-')
    try:
        with chains(made_up(run, ('A', [('open leaf', 1, point(1.0))]))):
            for c in range(R['starts'][0] + 3, len(lines)):
                journal, log = os.path.join(d, f'{c}.jsonl'), os.path.join(d, f'{c}.log')
                open(journal, 'w').write(''.join(records[:1 + sum(1 for x in R['dates'] if x < c)]))
                open(log, 'w').write(''.join(lines[:c]))
                reading = progress.Reading(journal, log)
                s = progress.survey(64, 7, journal, log, procs, R['stamps'][c - 1] + 1, {}, {}, reading, (), times)
                if s['stages'][1]['to_go'] is not None and s['open'] > 0: break
            else:
                raise AssertionError('no cut of the tiny open run has an estimate and open leaves')
            g = reading.grown[0]
            parts = {}
            draws = progress.estimate(g.state, parts, g)
    finally:
        shutil.rmtree(d)
    growth = 1 + parts['work'] / (parts['sofar'][g.root] + g.history()[1].get('', 0.0))
    assert np.array_equal(draws, s['draws']) and (growth >= 1).all(), growth
    leaves = s['open'] * growth
    assert [x['name'] for x in s['stages']] == ['overnight_v5.py', 'A'] and s['stages'][0]['to_go'] == s['to_go'], s['stages']
    assert close(s['stages'][1]['to_go'], progress.to_go_of(progress.quantiles(leaves)), 1e-6), (s['stages'][1], leaves[:5])
    assert close(s['total'], progress.to_go_of(progress.quantiles(s['draws'] + leaves)), 1e-6), s['total']


def q_a_restart_s_replay_leaves_the_span_s_work_as_it_was():
    # Replicata: quals_progress_history's fixture of 100 donor subtrees, each a job of 10 s and its child's of 100 s,
    # done in one pass; and the same donors done in an earlier pass of the same kind and replayed at no cost in the
    # current one (a restart); estimate of each (its replay and speed stood in for), then span_work of its parts.
    # Expectata: 11,000 worker seconds both times (100 x (10 + 100)): the restart's history counts the first pass's
    # work once, and its replay adds none; so the growth of the open leaves at the pass's end has the same median, low
    # and high (quals_progress_history: the estimate's work does).
    import quals_progress_history as h
    got = []
    for restarted in (False, True):
        state, tree, _, _ = h.fixture(restarted)
        draws, parts = h.estimate(state, tree)
        view = progress.Walk(state, *tree)
        got.append((progress.span_work(parts, view), 1 + parts['work'] / progress.span_work(parts, view)))
    assert math.isclose(got[0][0], 11000.0) and math.isclose(got[1][0], 11000.0), got
    assert progress.quantiles(got[0][1]) == progress.quantiles(got[1][1]), got


def q_a_boxsplit_pass_s_stages_count_its_leaves():
    # Replicata: survey_box of quals_progress.made_up_box's pass of 304@9 (4 open leaves) at its start + 152 s, its
    # driver 900 running with a worker 901 that ps says used a CPU minute in two (a share of 0.5), in a made-up chain:
    # boxsplit.py's run, then stage A per open leaf on 1 process at 2 CPU s.
    # Expectata: stages boxsplit.py (its to_go, box_estimate's) then A, 4 x 2 / (1 x 0.5) = 16 s in every replicate;
    # the total the run's estimate 16 s later at its median, low and high (a constant added to every replicate).
    import quals_progress
    t0 = 1792200000.0
    journal, log, main = quals_progress.made_up_box(t0)
    run = ('boxsplit.py', 304, 9)
    procs = [(900, 1, 'SN', 'python3 -u -B boxsplit.py 304 9'), (901, 900, 'SN', WORKER)]
    with chains(made_up(run, ('A', [('open leaf', 1, point(2.0))]))):
        s = progress.survey_box(304, 9, log, main, procs, t0 + 152, {}, times=lambda: {901: ('1:00.00', '02:00')})
    assert [x['name'] for x in s['stages']] == ['boxsplit.py', 'A'] and s['stages'][0]['to_go'] == s['to_go'], s['stages']
    assert close(s['stages'][1]['to_go'], dict(median=16.0, lo=16.0, hi=16.0)), s['stages'][1]
    assert close(s['total'], {k: v + 16.0 for k, v in s['to_go'].items()}), (s['total'], s['to_go'])


def q_an_idle_run_keeps_its_stages_and_a_run_of_one_stage_has_none():
    # Replicata: light and run_data of a survey with stages and total; run_data of one without (a run of one stage).
    # Expectata: light keeps stages and total (an idle run's survey stands for later snapshots: see idle) and the data
    # file's entry carries them; the entry of a run of one stage has neither key.
    s = dict(program='fanout.py', n=672, order=13, state='running', outcome=None, so_far=1.0, to_go=None, etas={},
             passes=[[0.0, 1.0]], sea=dict(depth=0, keys=['0:0'], groups=['4'], counts=dict(running=1)),
             stages=[dict(name='fanout.py', to_go=None), dict(name='A', to_go=None)], total=None)
    assert {'stages', 'total'} <= set(progress.light(s)), progress.light(s)
    entry = progress.run_data(s)
    assert (entry['stages'], entry['total']) == (s['stages'], None), entry
    one = progress.run_data({k: v for k, v in s.items() if k not in ('stages', 'total')})
    assert not {'stages', 'total'} & set(one), one


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
