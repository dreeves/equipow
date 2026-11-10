#!/usr/bin/env python3
"""Quals for the stages to a recordable result (progress.py's chain, share and stages, and stages.json; the
coordinator, 2026-10-31, after the page's ETA had covered only the stage running, twice in two days).
Run: python3 -B quals/quals_stages.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata
(the setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened
instead).
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, math, shutil, tempfile, traceback, contextlib, statistics
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'searchwatch'))   # progress.py's directory since 2026-11-10 ([REF]); the root until then
# the engine's modules, in engine/ since [FAC] stage 3b (2026-11-04)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'engine'))
import overnight_v5 as v5
import fanout
import progress

# the commands, as ps shows them, of a worker multiprocessing spawned and of its resource tracker (a child too)
WORKER = 'Python -B -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=5, pipe_handle=7) --multiprocessing-fork'
TRACKER = 'Python -B -c from multiprocessing.resource_tracker import main;main(4)'


def part(per, k, cpu):
    """A made-up part: per a unit, on k processes, costing cpu, with made-up provenance."""
    return dict(per=per, processes=k, cpu=cpu, source='a qual', date='2026-10-31', conditions='made up')


def made_up(run, *later):
    """A made-up STAGES: one chain, the run (program, n, order), then each later stage given as (its name, its parts,
    each (per, processes, cpu)), every part with made-up provenance.  Since 2026-11-01 (the stages of CRAM's reprove.py,
    scratch/stages-cram-20261101) a later stage has phases, not parts: here its parts make one lane of one phase, one
    after another, so each stage costs the sum of its parts as before."""
    return [[dict(stage=run[0], run=list(run))] +
            [dict(stage=name, phases=[[[part(*p) for p in parts]]]) for name, parts in later]]


def phased(run, *later):
    """A made-up STAGES: one chain, the run (program, n, order), then each later stage given as (its name, its phases,
    each a list of lanes, each a list of parts (per, processes, cpu)), every part with made-up provenance."""
    return [[dict(stage=run[0], run=list(run))] +
            [dict(stage=name, phases=[[[part(*p) for p in lane] for lane in phase] for phase in phases])
             for name, phases in later]]


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
    # Spec change, 2026-11-01 (the coordinator, after CRAM's install at 03:5x PST, scratch/stages-cram-20261101): a
    # later stage has phases (one after another), each of lanes (at once), each of parts (one after another).
    # fanout.assemble is one part on one process; reprove.py three phases, its briefs on fanout.WORKERS processes, then
    # its walk (one process: assembly, then the seal) beside its reproofs (fanout.WORKERS processes: the task's read,
    # then the walk), then its seals on one process; 288:10's stages one part each, as before.
    names = [[s['stage'] for s in chain] for chain in progress.STAGES]
    assert names == [['fanout.py', 'fanout.assemble', 'reprove.py'],
                     ['overnight_v5.py', 'boxsplit.py', 'handoff288.py', 'overnight_v5.py']], names
    runs = [[s.get('run') for s in chain] for chain in progress.STAGES]
    assert runs == [[['fanout.py', 432, 12], None, None],
                    [['overnight_v5.py', 288, 10], ['boxsplit.py', 288, 10], None, None]], runs
    shape = [[[[[(p['per'], p['processes']) for p in lane] for lane in phase] for phase in s.get('phases', [])]
              for s in chain] for chain in progress.STAGES]
    W = fanout.WORKERS
    assert shape == [[[], [[[('token', 1)]]],
                      [[[('token', W)]], [[('token', 1), ('token', 1)], [('token', W), ('token', W)]], [[('token', 1)]]]],
                     [[], [[[('open leaf', v5.PROCESSES)]]], [[[('open leaf', 1)]]], [[[('open leaf', v5.PROCESSES)]]]]], shape
    assert all(len(p[k]) > 20 for chain in progress.STAGES for s in chain for phase in s.get('phases', [])
               for lane in phase for p in lane for k in ('source', 'conditions')), progress.STAGES


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


def q_a_later_stage_s_band_comes_from_its_cost_s_measured_band():
    # Replicata: a made-up chain of 672:13's fanout.py run with one later stage, one part per token on 1 process
    # measured at a median of 2 CPU s, 1 at its low end and 8 at its high end (MEASURED, 5% and 95%); stages_of with
    # 3,600 tokens and a share of 1, the run's estimate 0 h in every replicate.  And drawn of that cost, 400,000 draws.
    # Expectata: the stage's median, low and high near the cost law's at 0.5 and at the stages band's levels (chance.BANDS's
    # stages, (0.1, 0.9): 2, 1.165 and 5.890 h; two_piece), the replicates' quantiles, within 10% (2,000 draws), the
    # total the same; the 400,000 draws' quantiles within 1% of 1, 2 and 8: a two-piece log-normal whose 5% and 95%
    # are the measured ones, however lopsided.
    # Spec change (Claude, 2026-11-06): named q_a_later_stage_s_band_is_its_cost_s_measured_band while the band's levels
    # were the measured 5% and 95% (2, 1 and 8 h); the bands are (0.1, 0.9) since the coordinator's calibration study
    # (scratch/calibration-20261106), so the stage's band is the cost law's 10% and 90%.
    run = ('fanout.py', 672, 13)
    cost = dict(median=2.0, lo=1.0, hi=8.0)
    with chains(made_up(run, ('A', [('token', 1, cost)]))):
        got = progress.stages_of(run, 'running', None, np.zeros(progress.REPLICATES), {'token': 3600.0}, 1.0)
    lo, hi = progress.chance.BANDS['stages']
    for k, level in (('median', 0.5), ('lo', lo), ('hi', hi)):
        w = two_piece(cost, statistics.NormalDist().inv_cdf(level))
        assert math.isclose(got['stages'][1]['to_go'][k], w * 3600, rel_tol=0.1), (k, w, got['stages'][1])
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
    # Spec change, 2026-11-01 (scratch/stages-cram-20261101): a later stage's phases in place of its parts (see
    # made_up), so the broken copies reach a part through its phase and lane, a later stage without phases or a first
    # stage with them is broken, and so are a stage with no phase, a phase with no lane, a lane with no part, a lane
    # that is a part, and a later stage with parts as written before 2026-11-01.
    good = {'about': 'a qual', 'chains': made_up(('fanout.py', 672, 13), ('A', [('token', 1, dict(median=2.0, lo=1.0, hi=3.0))]))}
    def broken(f):
        data = json.loads(json.dumps(good))
        f(data)
        return data
    stage = lambda d: d['chains'][0][1]
    part = lambda d: stage(d)['phases'][0][0][0]
    bad = [broken(lambda d: part(d).pop('source')), broken(lambda d: part(d).update(source='')),
           broken(lambda d: part(d).update(date=20261031)), broken(lambda d: part(d).update(per='leaf')),
           broken(lambda d: part(d)['cpu'].update(lo=2.5)), broken(lambda d: part(d)['cpu'].update(lo=0.0, median=0.0)),
           broken(lambda d: part(d).update(processes=0)), broken(lambda d: d['chains'][0][0].pop('run')),
           broken(lambda d: stage(d).pop('phases')), broken(lambda d: d['chains'][0][0].update(phases=[])),
           broken(lambda d: d['chains'][0][0].update(stage='focus.py')),
           broken(lambda d: d['chains'].append([dict(stage='fanout.py', run=['fanout.py', 672, 13])])),
           broken(lambda d: d.update(extra=1)),
           broken(lambda d: stage(d).update(phases=[])), broken(lambda d: stage(d).update(phases=[[]])),
           broken(lambda d: stage(d).update(phases=[[[]]])), broken(lambda d: stage(d).update(phases=[[part(d)]])),
           broken(lambda d: stage(d).update(parts=[part(d)])),
           broken(lambda d: stage(d).update(parts=stage(d).pop('phases')[0][0]))]
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
    # (spec change, Claude, 2026-11-06: progress.quantiles takes the band of the estimator whose draws it summarizes, each
    # estimator's own in chance.BANDS, so that each can be calibrated to the page's one coverage: here stages_of's)
    stages = progress.chance.BANDS['stages']
    assert close(s['stages'][1]['to_go'], progress.to_go_of(progress.quantiles(leaves, stages)), 1e-6), (s['stages'][1], leaves[:5])
    assert close(s['total'], progress.to_go_of(progress.quantiles(s['draws'] + leaves, stages)), 1e-6), s['total']


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
    # (spec change, Claude, 2026-11-06: progress.quantiles takes an estimator's band, here stages_of's, which the growth feeds)
    stages = progress.chance.BANDS['stages']
    assert progress.quantiles(got[0][1], stages) == progress.quantiles(got[1][1], stages), got


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


# ---------- CRAM's stages (2026-11-01: the coordinator, after CRAM's install at 03:5x PST; Astra's constraints of
# 03:54 and 04:19 PST in omg-we-found-other-agents.md; scratch/stages-cram-20261101) ----------

CRAM = {'fanout.py': 'f56e2346b3005dc512678d9ddbcf2f5e283ee5c53df0d89a57b257f103635a55',
        'reprove.py': '631b3fbe5b505116784cdd94326ce568aa8ff4849e09a83409b5e260f7726131'}
# a part's source: measure.py's corrected record (measure2_, its arms each releasing their own results; Astra,
# 2026-11-01 04:43 PST: the first record, measure_, charged one arm's release to the next) and the part's arm
SOURCE = re.compile(r'(scratch/stages-cram-20261101/measure2_\d+_\d+_\d+\.json), arm (\w+) \(measure\.py\)')


def two_piece(cpu, z):
    """The cost cpu, {median, lo, hi}, at the standard normal's z, as progress.drawn defines its draws: a two-piece
    log-normal whose median and MEASURED quantiles are the cost's."""
    side = cpu['hi'] if z > 0 else cpu['lo']
    return cpu['median'] * (side / cpu['median']) ** (z / statistics.NormalDist().inv_cdf(0.95 if z > 0 else 0.05))


def q_lanes_at_once_take_the_longer_replicate_by_replicate():
    # Replicata: a made-up chain of 672:13's fanout.py run with one later stage of one phase of two lanes, each lane
    # one part per token on 1 process measured at a median of 1 CPU s, 0.5 at its low end and 2 at its high end;
    # stages_of with 3,600 tokens and a share of 1, the run's estimate 0 h in every replicate.  Apart, the quantiles of
    # the larger of two independent draws of that cost: G(q) = F(q)^2 = p, so q is the cost at the standard normal's
    # quantile of p^(1/2) (two_piece).
    # Expectata (Astra, 2026-11-01 03:54 PST: "Any overlap combination belongs on replicate draws before quantiles,
    # not on already-aggregated medians/bands"): the stage's median, low and high those of the larger draw at 0.5 and
    # the stages band's levels (1.258, 0.817 and 1.989 h at (0.1, 0.9)) within 6%: not the larger of the lanes' own
    # quantiles (1, 0.582 and 1.717 h at those levels), which a combination of medians and bands would give; the total
    # the stage's.
    # Spec change (Claude, 2026-11-06): the levels are chance.BANDS's stages, (0.1, 0.9) since the coordinator's
    # calibration study (scratch/calibration-20261106); at (0.05, 0.95) before, the larger draw's were 1.258, 0.726 and
    # 2.279 h and the lanes' own 1, 0.5 and 2 h.
    run = ('fanout.py', 672, 13)
    cost = dict(median=1.0, lo=0.5, hi=2.0)
    with chains(phased(run, ('A', [[[('token', 1, cost)], [('token', 1, cost)]]]))):
        got = progress.stages_of(run, 'running', None, np.zeros(progress.REPLICATES), {'token': 3600.0}, 1.0)
    z = lambda p: statistics.NormalDist().inv_cdf(math.sqrt(p))
    lo, hi = progress.chance.BANDS['stages']
    want = dict(median=two_piece(cost, z(0.5)), lo=two_piece(cost, z(lo)), hi=two_piece(cost, z(hi)))
    assert [round(want[k], 3) for k in ('median', 'lo', 'hi')] == [1.258, 0.817, 1.989], want
    for k in want:
        assert math.isclose(got['stages'][1]['to_go'][k], want[k] * 3600, rel_tol=0.06), (k, got['stages'][1], want)
    assert got['stages'][1]['to_go']['median'] > 1.1 * 3600 and got['stages'][1]['to_go']['lo'] > 0.6 * 3600, got
    assert close(got['total'], got['stages'][1]['to_go']), got


def q_phases_follow_one_another_and_each_lasts_its_longest_lane():
    # Replicata: a made-up chain of 672:13's fanout.py run, its estimate 1 h in every replicate, then stage R in three
    # phases: one lane per token on 8 processes at 0.8 CPU s; then two lanes, one on 1 process (0.1, then 0.2 CPU s a
    # token), the other on 8 (4, then 4); then one lane on 1 process at 0.05; then stage S, one part on 1 process at
    # 0.25; stages_of with 3,600 tokens and a share of 0.5.  Then the same with the 1-process lane of R's second phase
    # at 3, then 1 CPU s a token.
    # Expectata (Astra, 2026-11-01 03:54 PST: the outer chain sequential; inside reprove, briefs before the streaming
    # walk with its reproofs, then the final seals after the drain; never one max over the whole of reprove): R's
    # phases summed, each its longest lane, its lanes' parts summed: 3600 x 0.8 / (8 x 0.5) = 720 s, then max(3600 x
    # 0.3 / 0.5, 3600 x 8 / (8 x 0.5)) = 7,200 s, then 3600 x 0.05 / 0.5 = 360 s: R 8,280 s; S 3600 x 0.25 / 0.5 =
    # 1,800 s; the total 3,600 + 8,280 + 1,800 s.  With the 1-process lane the longer, max(28,800, 7,200): R 29,880 s
    # and the total 3,600 + 29,880 + 1,800 s.
    run = ('fanout.py', 672, 13)
    for a, b, R in ((0.1, 0.2, 8280.0), (3.0, 1.0, 29880.0)):
        made = phased(run, ('R', [[[('token', 8, point(0.8))]],
                                  [[('token', 1, point(a)), ('token', 1, point(b))], [('token', 8, point(4.0)), ('token', 8, point(4.0))]],
                                  [[('token', 1, point(0.05))]]]),
                      ('S', [[[('token', 1, point(0.25))]]]))
        with chains(made):
            got = progress.stages_of(run, 'running', None, np.ones(progress.REPLICATES), {'token': 3600.0}, 0.5)
        assert [s['name'] for s in got['stages']] == ['fanout.py', 'R', 'S'], got
        assert close(got['stages'][1]['to_go'], dict(median=R, lo=R, hi=R)), (a, b, got['stages'][1])
        assert close(got['stages'][2]['to_go'], dict(median=1800.0, lo=1800.0, hi=1800.0)), got['stages'][2]
        assert close(got['total'], {k: 3600 + R + 1800.0 for k in ('median', 'lo', 'hi')}), (a, b, got['total'])


def arms(stage):
    """Each part of a stage of the real stages.json as (its measurement file, its arm), read from its source, shaped
    as the stage's phases and lanes."""
    named = lambda p: SOURCE.fullmatch(p['source']).groups()
    return [[[named(p) for p in lane] for lane in phase] for phase in stage['phases']]


def q_cram_reprove_walks_beside_its_reproofs_between_its_briefs_and_its_seals():
    # Replicata: 432:12's chain in progress.STAGES, the repository's stages.json; each part's measured code path, the
    # arm its source names in scratch/stages-cram-20261101's measurement (measure.py).
    # Expectata (the coordinator and Astra, 2026-11-01, of CRAM's reprove.py: reprove.briefs, then fanout.assemble's
    # walk with each job's reproof released as assemble passes it, then the seals after the drain): fanout.assemble
    # one part, assemble's per-job work; reprove.py's first phase briefed (its workers' briefs), its second the walk
    # (assemble's per-job work, then the seal passed takes) beside the reproofs (the task's read, then the walk), its
    # third the seals; every part from one measurement file.
    chain = next(c for c in progress.STAGES if c[0].get('run') == ['fanout.py', 432, 12])
    got = [arms(s) for s in chain[1:]]
    files = {f for stage in got for phase in stage for lane in phase for f, _ in lane}
    assert len(files) == 1, files
    assert [[[[a for _, a in lane] for lane in phase] for phase in stage] for stage in got] == [
        [[['assemble']]],
        [[['briefed']], [['assemble', 'sealed'], ['read', 'walk']], [['sealed']]]], got


def q_cram_coefficients_are_cpu_measured_on_cram():
    # Replicata: each part of 432:12's later stages in progress.STAGES, and the measurement file and arm its source
    # names (scratch/stages-cram-20261101/measure.py's output: a row a job file, each arm's CPU nanoseconds summed over
    # its timings, by time.process_time_ns, and its tokens).
    # Expectata (Astra, 2026-11-01 03:54 PST: "Coefficients must be CPU per unit measured as CPU"; the coordinator:
    # each coefficient's provenance): the file measured the installed CRAM files (fanout.py f56e2346..., reprove.py
    # 631b3fbe...) at nice 19 with single-threaded BLAS; each part's median its arm's CPU seconds a token, the arm's
    # nanoseconds over its tokens times its timings, summed over the files that ran it (Astra, 04:36 PST: a
    # token-weighted rate); its low and high ends around it; its conditions naming both files' sha256 prefixes; no part
    # citing the measurements of N3Q3's code (measure_q3.json, assembly_files_1_300.json) that CRAM replaced.
    chain = next(c for c in progress.STAGES if c[0].get('run') == ['fanout.py', 432, 12])
    parts = [p for s in chain[1:] for phase in s['phases'] for lane in phase for p in lane]
    assert parts and all(SOURCE.fullmatch(p['source']) for p in parts), [p['source'] for p in parts]
    assert not [p for p in parts if 'measure_q3' in p['source'] + p['conditions'] or 'assembly_files' in p['source']], parts
    for p in parts:
        path, arm = SOURCE.fullmatch(p['source']).groups()
        m = json.load(open(os.path.join(progress.HERE, path)))
        assert m['identity']['files'] == CRAM and m['nice'] == 19 and set(m['threads'].values()) == {'1'}, m['identity']
        rows = [r for r in m['rows'] if arm in r['ns']]
        per = sum(r['ns'][arm] for r in rows) / sum(r['tokens'] * r['timings'][arm] for r in rows) / 1e9
        assert rows and math.isclose(p['cpu']['median'], per, rel_tol=1e-12), (arm, p['cpu'], per)
        assert p['cpu']['lo'] < per < p['cpu']['hi'], (arm, p['cpu'])
        assert p['per'] == 'token' and CRAM['fanout.py'][:8] in p['conditions'] and CRAM['reprove.py'][:8] in p['conditions'], p


def journal432(d):
    """quals_fanout_progress.drawn()'s journal, as 432:12's, in the directory d: 15 LP solves done (jobs a and b), the
    pool estimate 45 to go in every replicate, at 4 LP solves a second."""
    import quals_fanout_progress
    records = quals_fanout_progress.drawn()
    assert records[0]['event'] == 'header'
    path = os.path.join(d, 'fanout_432_journal.jsonl')
    open(path, 'w').write(''.join(json.dumps(r) + '\n' for r in [dict(records[0], n=432, order=12)] + records[1:]))
    return path


def q_the_fanout_stage_is_the_journal_s_rate_with_no_factor():
    # Replicata: survey_fanout of quals_fanout_progress.drawn()'s journal as 432:12's (journal432) at 300 s, its driver
    # 41 alive with a worker 42 that ps says used 30 CPU minutes in an hour (a share of 0.5), under the repository's
    # stages.json; and stages_of of 432:12's run with its estimate 0 h, the same 60 tokens and share, in as many
    # replicates as the pool estimate's (BOOT: pool_draws).
    # Expectata (Astra, 2026-11-01 04:19 PST: "the running search's observed throughput already reflects installed
    # worker behavior, so its estimate must not also be multiplied by the 3.743% benchmark reduction"; the
    # coordinator: the fanout stage's rate comes from the journal, with no extra factor): fanout.py's own stage the
    # pool estimate at the journal's rate exactly, 45 LP solves at 4 a second, 11.25 s at its median, low and high,
    # as the survey's to_go; the later stages fanout.assemble and reprove.py; the total 11.25 s more than the later
    # stages' alone at their median, low and high: the run's replicates added unscaled to theirs, from 15 + 45 tokens.
    procs = [(41, 1, 'SN', '/opt/homebrew/bin/python3 -B fanout.py 432'), (42, 41, 'SN', WORKER)]
    times = lambda: {42: ('30:00.00', '01:00:00')}
    d = tempfile.mkdtemp(prefix='stages-quals-')
    try:
        s = progress.survey_fanout(journal432(d), procs, 300, {}, {}, times=times)
    finally:
        shutil.rmtree(d)
    assert [x['name'] for x in s['stages']] == ['fanout.py', 'fanout.assemble', 'reprove.py'], s['stages']
    assert close(s['stages'][0]['to_go'], dict(median=11.25, lo=11.25, hi=11.25)) and s['stages'][0]['to_go'] == s['to_go'], s
    alone = progress.stages_of(('fanout.py', 432, 12), 'running', None, np.zeros(progress.BOOT),
                               {'token': np.full(progress.BOOT, 60.0)}, 0.5)
    assert [x['to_go'] for x in alone['stages'][1:]] == [x['to_go'] for x in s['stages'][1:]], (alone, s['stages'])
    assert close(s['total'], {k: 11.25 + v for k, v in alone['total'].items()}), (s['total'], alone['total'])


def q_the_288_chain_sums_its_stages_as_before():
    # Replicata: stages_of of 288:10's overnight_v5.py run and of its boxsplit.py run under the repository's
    # stages.json, running, each with its estimate drawn at random (REPLICATES replicates), open leaves at random
    # (one a replicate) and a share of 0.43; apart, the arithmetic of stages_of before 2026-11-01: each later stage
    # the sum of its parts, a part its count times its cost drawn (drawn, from SEED's first spawned stream, part after
    # part in the chain's order) over its processes times the share, and the total the run's replicates plus each
    # stage's.
    # Expectata (Astra, 2026-11-01 03:54 PST: "Existing sequential-addition behavior and the 288 chain should remain
    # qualified"): every stage's to_go and the total exactly that arithmetic's, so that 288:10's line is unchanged.
    # (spec change, Claude, 2026-11-06: progress.quantiles takes the band of the estimator whose draws it summarizes,
    # chance.BANDS's: stages_of's for the later stages and the total; the run's own to_go, which stages_of passes through,
    # at that band too)
    rng, stages = np.random.default_rng(7), progress.chance.BANDS['stages']
    for run in (('overnight_v5.py', 288, 10), ('boxsplit.py', 288, 10)):
        hours = rng.gamma(2.0, 30.0, progress.REPLICATES)
        leaves = rng.uniform(1e6, 2e6, progress.REPLICATES)
        got = progress.stages_of(run, 'running', progress.to_go_of(progress.quantiles(hours, stages)), hours, {'open leaf': leaves}, 0.43)
        later = progress.later_of(run)
        assert later and all(len(s['phases']) == 1 and len(s['phases'][0]) == 1 for s in later), later
        stream = np.random.default_rng(np.random.SeedSequence(progress.SEED).spawn(1)[0])
        before = [sum(leaves * progress.drawn(stream, p['cpu'], len(hours)) / (p['processes'] * 0.43 * progress.HOUR)
                      for p in s['phases'][0][0]) for s in later]
        assert [x['to_go'] for x in got['stages'][1:]] == [progress.to_go_of(progress.quantiles(h, stages)) for h in before], run
        assert got['total'] == progress.to_go_of(progress.quantiles(hours + sum(before), stages)), run


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
