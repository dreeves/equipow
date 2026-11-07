#!/usr/bin/env python3
"""Quals for chance.py, a witness campaign's chance of a witness within the next t hours (README [SER], 2026-11-03:
"Could the searches show a live estimate of the probability of finding a bipartition?"; dreeves: "sure, build [SER]").
Run from the repository's root:
    python3 -B quals/quals_chance.py [name ...]   (no arguments: all quals)
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  Most build a made-up campaign in a temporary
directory (campaign()); the bandit's agreement imports scratch/bandit-20261103b/rerun.py, read only.
"""
import sys
sys.dont_write_bytecode = True
import os, json, math, time, shutil, tempfile, traceback
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
sys.path.insert(0, HERE)                                              # for its modules
import chance

BANDIT = os.path.join(HERE, 'scratch', 'bandit-20261103b')            # the bandit's rerun (rerun.py, analysis.py, ranking.json)
CAMPAIGN = os.path.join('scratch', 'beam-campaign-20261103')          # the beam campaign, from the root
PRIOR = dict(p_exists=0.3, mean=-2.24, sd=3.95)                       # a made-up campaign's prior at 528:12 (the bandit's, rounded)
SHOWN = {'cpu_hours', 'rate', 'cores', 'hours', 'p', 'exists', 'found', 'since', 'history', 'odds'}   # chance.shown's keys


def expect_assertion(f, *args):
    try:
        f(*args)
    except AssertionError:
        return
    raise Exception(f'no AssertionError from {f.__name__}')


def close(got, want, rel=1e-12):
    """Whether got and want, numbers or (nested) lists or dicts of numbers alike in shape (or None), agree to rel."""
    if isinstance(want, dict): return isinstance(got, dict) and set(got) == set(want) and all(close(got[k], want[k], rel) for k in want)
    if isinstance(want, (list, tuple)): return isinstance(got, list) and len(got) == len(want) and all(close(a, b, rel) for a, b in zip(got, want))
    if want is None: return got is None
    return abs(got - want) <= rel * max(1.0, abs(want))


def seed(t, kind, k, cpu, cancelled=False, cell='528:12'):
    """A campaign journal's seed_end record, as campaign.py writes it (scratch/beam-campaign-20261103/campaign.py)."""
    n, m = cell.split(':')
    return dict(time=t, event='seed_end', cell=cell, k=k, f=170, slot=0, kind=kind,
                prefix=os.path.join('camp', 'seeds', f'{n}_{m}_s{k}'), status=0, cancelled=cancelled, cpu=cpu, witnesses=[])


def begun(t, kind, k, cell='528:12'):
    """A campaign journal's seed_start record, as campaign.py writes it."""
    n, m = cell.split(':')
    return dict(time=t, event='seed_start', cell=cell, k=k, f=170, slot=0, kind=kind,
                prefix=os.path.join('camp', 'seeds', f'{n}_{m}_s{k}'), wall=6400, tracker=1)


def life(a, b, kind, k, cpu, cancelled=False, cell='528:12'):
    """A seed's seed_start record at a and its seed_end record at b."""
    return [begun(a, kind, k, cell), seed(b, kind, k, cpu, cancelled, cell)]


# A made-up campaign's journal, its times in epoch seconds, in time order: launched at 1000 with two cells, 528:12 and
# 720:13; at 528:12, plain seed 2 from 1000 to 1500 (200 CPU s), probe seed 1 from 1000 to 2800 (its tracker's rusage
# 900 s, its bookkeeping in it), plain seed 3 from 1500 to 2900 (180 s), plain seed 4 from 2800, cancelled at 3000
# after 50 s, probe seed 5 from 2900, cancelled at 3100 with no files at all, and plain seeds 7 and 8 running from 3000
# and 3100; and at 720:13 a plain seed of 999 s from 1000 to 3200.
JOURNAL = sorted([dict(time=1000.0, event='start')] + life(1000.0, 1500.0, 'plain', 2, 200.0) + life(1000.0, 2800.0, 'probe', 1, 900.0)
                 + life(1500.0, 2900.0, 'plain', 3, 180.0) + life(2800.0, 3000.0, 'plain', 4, 50.0, cancelled=True)
                 + life(2900.0, 3100.0, 'probe', 5, 20.0, cancelled=True) + life(1000.0, 3200.0, 'plain', 6, 999.0, cell='720:13')
                 + [begun(3000.0, 'plain', 7), begun(3100.0, 'plain', 8)], key=lambda r: r['time'])
# JOURNAL's campaign stopped at 3500 (a SIGTERM: its driver cancels its running seeds 7 and 8, after 400 and 300 CPU s,
# then ends), and relaunched at 4000 (resuming the journal) with plain seeds 9 and 10 running from then.
STOP = [seed(3500.0, 'plain', 7, 400.0, cancelled=True), seed(3500.0, 'plain', 8, 300.0, cancelled=True),
        dict(time=3500.0, event='end', reason='signal')]
AGAIN = [dict(time=4000.0, event='start', resumed=True), begun(4000.0, 'plain', 9), begun(4000.0, 'plain', 10)]
# probe seed 1's rounds, (X, cpu): 3e-4, 1e-4 and 5e-5 of exposure in 100 CPU s each
ROUNDS = ((3e-4, 100.0), (1e-4, 100.0), (5e-5, 100.0))


def probe_lines(rounds, done=True):
    """A finished probe seed's PREFIX.jsonl lines, as probe_seed.py writes them: its header, its rounds, its done line."""
    head = dict(kind='header', n=528, m=12, f=170, seed=1, beam=20000, cpu=4.8)
    body = [dict(kind='round', round=i + 1, generated=20000, fresh=100, enumerated=100, cpu=c, probe_cpu=2 * c, X=x, Qbest=84.0)
            for i, (x, c) in enumerate(rounds)]
    end = dict(kind='done', rounds=len(rounds), cpu=sum(c for _, c in rounds), probe_cpu=500.0, wall=1700.0, witnesses=0)
    return [head] + body + [end] * done


def campaign(journal=JOURNAL, probes=None, priors=None, plan_dir='camp', cells=('528:12', '720:13'), archives=()):
    """A temporary directory as the repository's root, with a campaign in camp/: its plan.json (dir plan_dir, the cells),
    its journal.jsonl (journal), its probe seeds' PREFIX.jsonl files (probes: {prefix: lines}; by default probe seed 1's
    of ROUNDS), its chance.json (priors: {target: prior}; by default PRIOR at 528:12 and 720:13), and its archived plans
    (archives: (name, {cells, journal, probes, dir}) each, name planK and dir camp by default), each written as a plan is
    archived, moved whole below camp/name: its plan.json, its journal and its probe seeds' files, which its journal names
    where they were before the move (camp/seeds/...)."""
    d = tempfile.mkdtemp(prefix='chance-quals-')
    camp = os.path.join(d, 'camp')
    os.makedirs(os.path.join(camp, 'seeds'))
    plan_of = lambda cells, where: dict(name='q', dir=where, cells=[dict(n=int(c.split(':')[0]), m=int(c.split(':')[1]), fs=[170]) for c in cells])
    json.dump(plan_of(cells, plan_dir), open(os.path.join(camp, 'plan.json'), 'w'))
    open(os.path.join(camp, 'journal.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in journal))
    probes = {os.path.join('camp', 'seeds', '528_12_s1'): probe_lines(ROUNDS)} if probes is None else probes
    for prefix, lines in probes.items():
        open(os.path.join(d, prefix + '.jsonl'), 'w').write(''.join(json.dumps(x) + '\n' for x in lines))
    for name, a in archives:
        home = os.path.join(camp, name)
        os.makedirs(os.path.join(home, 'seeds'))
        json.dump(plan_of(a['cells'], a.get('dir', 'camp')), open(os.path.join(home, 'plan.json'), 'w'))
        open(os.path.join(home, 'journal.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in a['journal']))
        for prefix, lines in a['probes'].items():
            open(os.path.join(home, os.path.relpath(prefix, 'camp') + '.jsonl'), 'w').write(''.join(json.dumps(x) + '\n' for x in lines))
    priors = {'528:12': PRIOR, '720:13': PRIOR} if priors is None else priors
    json.dump(dict(targets=priors, sources={}), open(os.path.join(camp, 'chance.json'), 'w'))
    return d


# Two made-up archived plans, run before JOURNAL's: plan1 at 528:12 (launched at 100; plain seed 1 from 100 to 400,
# 1000 CPU s, probe seed 2 from 100 to 500, its rounds EARLY; ended at 600) and plan2 at 768:13 (launched at 700; a
# plain seed of 5000 CPU s from 700 to 800; ended at 900).  EARLY: 2e-4 and 1e-4 of exposure in 100 and 200 CPU s,
# 3.6e-3 per CPU-hour.
EARLY = ((2e-4, 100.0), (1e-4, 200.0))
PLAN1 = dict(cells=('528:12',), probes={os.path.join('camp', 'seeds', '528_12_s2'): probe_lines(EARLY)},
             journal=[dict(time=100.0, event='start'), begun(100.0, 'plain', 1), begun(100.0, 'probe', 2),
                      seed(400.0, 'plain', 1, 1000.0), seed(500.0, 'probe', 2, 2000.0), dict(time=600.0, event='end', reason='signal')])
PLAN2 = dict(cells=('768:13',), probes={},
             journal=[dict(time=700.0, event='start')] + life(700.0, 800.0, 'plain', 1, 5000.0, cell='768:13')
                     + [dict(time=900.0, event='end', reason='signal')])


def expected(cpu_seconds, cores, prior=PRIOR, rounds=ROUNDS):
    """What chance.of gives a live target whose ended seeds' search CPU is cpu_seconds in all, with these cores and
    probe seed 1's rounds: hours its cpu_hours, rate its rounds' exposure per CPU-hour, and the chance at each hour of
    chance.HOURS, by chance.within (whose own quals are below); P(exists) by chance.exists and the chance within each
    hour of chance.AHEAD given existence by chance.found (spec change, dreeves, 2026-11-04, of two graphs, "probability
    a partition exists" and "probability of finding a partition by time t *conditional on a partition existing*": until
    then no exists or found)."""
    rate = sum(x for x, _ in rounds) / (sum(c for _, c in rounds) / 3600)
    hours = cpu_seconds / 3600
    return dict(cpu_hours=hours, rate=rate, cores=cores, hours=list(chance.HOURS),
                p=chance.within(prior['p_exists'], prior['mean'], prior['sd'], rate * hours, [rate * cores * t for t in chance.HOURS]),
                exists=chance.exists(prior['p_exists'], prior['mean'], prior['sd'], rate * hours),
                found=chance.found(prior['mean'], prior['sd'], rate * hours, [rate * cores * t for t in chance.AHEAD]))


# ---------- the model ----------

def q_hours_run_every_quarter_hour_to_72():
    # Replicata: chance.HOURS.
    # Expectata (the coordinator, 2026-11-03: "for t from 0 to 72, with the values at 6 h and 24 h marked and stated"):
    # every quarter hour from 0 to 72, 6 and 24 among them, in order.
    assert list(chance.HOURS) == [k / 4 for k in range(289)] and 6 in chance.HOURS and 24 in chance.HOURS, chance.HOURS[:5]


def q_within_agrees_with_a_simulation_of_the_model():
    # Replicata: chance.within against a Monte Carlo of the model itself, 2,000,000 draws (seeded): with probability
    # p_exists a sequence exists and log2 theta ~ N(mean, sd^2), else theta = 0; the first witness comes after
    # T ~ Exp(theta r) CPU-hours; the draws with T > H kept (no witness in H CPU-hours), the share of them with
    # T <= H + c t.  Two cases: the 528:12 prior with r 1, c 2 and H 0.5 (exposure spent 0.5), and with H 200 (a
    # posterior far from the prior); t 1, 6 and 24 hours.
    # Expectata: within(p_exists, mean, sd, r H, [r c t]) within 5 standard errors of each simulated share.
    rng = np.random.default_rng(20261103)
    N, r, c = 2_000_000, 1.0, 2.0
    exists = rng.random(N) < PRIOR['p_exists']
    theta = np.where(exists, np.exp2(rng.normal(PRIOR['mean'], PRIOR['sd'], N)), 0.0)
    with np.errstate(divide='ignore'):
        T = rng.exponential(1.0, N) / (theta * r)                     # inf where theta = 0: no witness ever
    for H in (0.5, 200.0):
        kept = T > H
        for t in (1.0, 6.0, 24.0):
            share = float(np.mean(T[kept] <= H + c * t))
            se = math.sqrt(share * (1 - share) / kept.sum())
            got = chance.within(PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd'], r * H, [r * c * t])[0]
            assert abs(got - share) <= 5 * se, (H, t, got, share, se)


def q_within_without_exposure_is_the_prior_predictive():
    # Replicata: chance.within with no exposure spent, for the 528:12 prior and for (0.7, 1.5, 0.8), at exposures ahead
    # 0.01, 1, 30 and 1e6; and scipy.integrate.quad's p_exists E[1 - exp(-theta b)], log2 theta ~ N(mean, sd^2).
    # Expectata: the prior predictive chance: the two agree to 1e-10.
    from scipy.integrate import quad
    for p, mean, sd in ((PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd']), (0.7, 1.5, 0.8)):
        lo, hi = mean - 12 * sd, mean + 12 * sd
        for b in (0.01, 1.0, 30.0, 1e6):
            f = lambda z: -math.expm1(-2.0 ** z * b) * math.exp(-0.5 * ((z - mean) / sd) ** 2) / (sd * math.sqrt(2 * math.pi))
            points = [x for x in (mean, -math.log2(b)) if lo < x < hi]    # the density's peak and the step's middle
            want = p * quad(f, lo, hi, points=points, limit=400, epsabs=1e-14)[0]
            got = chance.within(p, mean, sd, 0.0, [b])[0]
            assert abs(got - want) <= 1e-10, (p, mean, sd, b, got, want)


def q_exists_and_found_factor_within():
    # Replicata: chance.exists and chance.found for the 528:12 prior and for priors of P(exists) 0, 0.01 and 1, after
    # exposures 0, 0.002 and 0.2, at exposures ahead 0 to 0.2.
    # Expectata (dreeves, 2026-11-04: two graphs, "probability a partition exists ... going down as the search proceeds
    # and doesn't find one" and "probability of finding a partition by time t conditional on a partition existing and
    # also conditional on not having found one so far"): their product is within's chance, to 12 digits; exists falls as
    # the exposure spent grows (strictly, where P(exists) is strictly between 0 and 1), and is the prior with none spent;
    # found is 0 with nothing ahead, never falls as the exposure ahead grows, and stays at most 1.
    # Resultata before: neither function.
    ahead = [k * 0.0005 for k in range(401)]
    for p in (PRIOR['p_exists'], 0.0, 0.01, 1.0):
        es = [chance.exists(p, PRIOR['mean'], PRIOR['sd'], a) for a in (0.0, 0.002, 0.2)]
        assert abs(es[0] - p) <= 1e-12 and (es[0] > es[1] > es[2] if 0 < p < 1 else es[0] == es[1] == es[2] == p), (p, es)
        for a in (0.0, 0.002, 0.2):
            f = chance.found(PRIOR['mean'], PRIOR['sd'], a, ahead)
            w = chance.within(p, PRIOR['mean'], PRIOR['sd'], a, ahead)
            e = chance.exists(p, PRIOR['mean'], PRIOR['sd'], a)
            assert f[0] == 0.0 and all(x <= y for x, y in zip(f, f[1:])) and f[-1] <= 1.0, (p, a, f[:3], f[-1])
            assert all(abs(e * x - y) <= 1e-12 * max(1e-300, abs(y)) + 1e-300 for x, y in zip(f, w)), (p, a)


def q_lindy_found_is_gotts_expected_coverage():
    # Replicata: chance.lindy_found at an age of 3 h, 0 to 72 h ahead; and E[min(1, s / R)] by scipy.integrate.quad,
    # R the remaining time by Gott's rule on that age, P(R > x) = 3 / (3 + x), its density 3 / (3 + x)^2.
    # Expectata: an exhaustive search with no estimate of its own (it finds a witness exactly when one exists, one
    # anywhere in the work left alike) finds it within s hours with chance E[min(1, s / R)] = (s / 3) log(1 + 3 / s):
    # equal to the integral to 1e-9; 0 with nothing ahead; rising; below 1, and within 0.03 of it 72 h ahead.
    from scipy.integrate import quad
    tau, ahead = 3.0, list(range(73))
    got = chance.lindy_found(tau, ahead)
    want = [0.0] + [s / (tau + s) + quad(lambda x: s / x * tau / (tau + x) ** 2, s, math.inf)[0] for s in ahead[1:]]
    assert all(abs(g - w) <= 1e-9 for g, w in zip(got, want)), [(s, g, w) for s, g, w in zip(ahead, got, want) if abs(g - w) > 1e-9][:3]
    assert got[0] == 0.0 and all(x < y for x, y in zip(got, got[1:])) and 0.97 < got[-1] < 1, (got[:3], got[-1])


def q_within_rises_with_t_to_the_posterior_chance_of_existence():
    # Replicata: chance.within for the 528:12 prior after exposure 0.002 (about 528:12's at 18:50 PST), at exposures
    # ahead 0 to 0.2 every 0.0005, and at 1e12; P(exists | no witness) = p_exists L / (p_exists L + 1 - p_exists),
    # L = E[exp(-theta 0.002)] by scipy.integrate.quad.
    # Expectata: 0 with nothing ahead; never falling as the exposure ahead grows; below that posterior, and at it to
    # 1e-9 far ahead (every theta > 0 has found its witness by then).
    from scipy.integrate import quad
    p, mean, sd, a = PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd'], 0.002
    ahead = [k * 0.0005 for k in range(401)]
    P = chance.within(p, mean, sd, a, ahead)
    f = lambda z: math.exp(-2.0 ** z * a) * math.exp(-0.5 * ((z - mean) / sd) ** 2) / (sd * math.sqrt(2 * math.pi))
    L = quad(f, mean - 12 * sd, mean + 12 * sd, points=[mean, -math.log2(a)], limit=400, epsabs=1e-14)[0]
    post = p * L / (p * L + 1 - p)
    assert P[0] == 0.0 and all(x <= y for x, y in zip(P, P[1:])) and P[-1] < post, (P[:3], P[-1], post)
    assert abs(chance.within(p, mean, sd, a, [1e12])[0] - post) <= 1e-9, post


def q_within_matches_the_bandit():
    # Replicata: chance.within and the bandit's own P(a witness within its core-hours) (scratch/bandit-20261103b/rerun.py's
    # witness_index_p, over scratch/bandit-20261103/bandit.py's grid, normal_logprior, no failed coset and no witness,
    # spent exposure r H), for the same inputs: 528:12's prior (the bandit's refit, scratch/bandit-20261103b/ranking.json)
    # with 528:12's measures at 18:50 PST (r 9.15e-4, H 2.14 CPU-hours, c 3.2 cores) and t 6, 24 and 72 hours; the
    # 768:13 campaign's (P(exists) 0.97, r 0.155, H 30, c 6.36) under a made-up N(-4.5, 3^2) and t 6; no exposure spent;
    # and P(exists) 1.
    # Expectata: the same chance, to a relative 1e-12 (it agreed to 1e-15 on 2026-11-03, once within's denominator added
    # 1 - p last no more: with P(exists) 1 its rounding had cost 4e-9).
    sys.path.insert(0, BANDIT)
    import rerun                       # puts scratch/bandit-20261103 on sys.path and imports its bandit
    bandit = rerun.bandit
    refit = json.load(open(os.path.join(BANDIT, 'ranking.json')))['refit']
    cases = [(0.3, refit['mu'], refit['sigma'], 9.15e-4, 2.14, 3.2, t) for t in (6.0, 24.0, 72.0)] + [
        (0.97, -4.5, 3.0, 0.155, 30.0, 6.36, 6.0), (0.7, 0.0, 1.0, 1.0, 0.0, 1.0, 24.0), (1.0, 2.0, 0.5, 0.01, 1000.0, 8.0, 72.0)]
    for p, mean, sd, r, H, c, t in cases:
        want = rerun.witness_index_p(p, bandit.normal_logprior(mean, sd), bandit.EMPTY, [], r * H, r, c * t)[1]
        got = chance.within(p, mean, sd, r * H, [r * c * t])[0]
        assert close(got, want, 1e-12) and want > 0, (p, mean, sd, r, H, c, t, got, want)


def q_within_refuses_bad_inputs():
    # Replicata: chance.within with P(exists) below 0 or above 1, an sd of 0 or below, a negative or infinite exposure
    # spent, an exposure ahead that is negative or NaN.
    # Expectata: AssertionError, each.
    good = (0.3, -2.24, 3.95, 0.5, [1.0])
    for i, bad in ((0, -0.1), (0, 1.1), (2, 0.0), (2, -1.0), (3, -1.0), (3, math.inf), (4, [-1.0]), (4, [math.nan])):
        args = list(good)
        args[i] = bad
        expect_assertion(chance.within, *args)


# ---------- a campaign's files ----------

def q_of_reads_a_live_target_s_campaign():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() (JOURNAL, probe seed 1's ROUNDS, PRIOR).
    # Expectata (the coordinator, 2026-11-03): its rate the probe seeds' round lines' summed X over their summed cpu
    # (4.5e-4 in 300 CPU s: 0.0054 per CPU-hour; the probe's rusage, 900 s, its bookkeeping in it, and the cancelled
    # probe seed 5, which has no files, left out); its CPU-hours every ended seed's search CPU (plain seeds' cpu,
    # cancelled ones too, and probe seed 1's rounds': 200 + 300 + 180 + 50 s), 720:13's left out; its cores the seeds
    # running there (7 and 8) times the search CPU per second of life of the seeds that ended in the hour up to the
    # latest end, 3000 (seeds 2, 1, 3 and 4: 730 s over 500 + 1800 + 1400 + 200 s; probe seed 5 has no search CPU);
    # hours chance.HOURS; and p the chance within each, by chance.within at exposure spent rate x CPU-hours and ahead
    # rate x cores x t.
    # Spec change (2026-11-04): until then its cores the search CPU of the seeds that ended in the last hour (after
    # 1600: 300 + 180 + 50 s) per second of it (see q_cores_are_the_seeds_running_times_their_cpu_share).
    d = campaign()
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        assert close(got, expected(730.0, 2 * 730.0 / 3900.0)), got and {k: v for k, v in got.items() if k != 'p'}
    finally:
        shutil.rmtree(d)


def q_cores_continue_across_relaunches():
    # Replicata: chance.of(root, 'camp', '528:12', now) for campaign() with JOURNAL, then STOP (its seeds 7 and 8
    # cancelled at 3500 after 400 and 300 CPU s, and its end) and AGAIN (its relaunch at 4000, which resumes the
    # journal, with plain seeds 9 and 10 running from then), at now 4001 and 5200.
    # Expectata: at both, cores the relaunched seeds running (9 and 10) times the search CPU per second of life of the
    # seeds that ended in the hour up to the latest end, those before the relaunch: 730 + 400 + 300 s over 3900 + 500 +
    # 400 s; the CPU-hours every ended seed's, those before the relaunch too.
    # Spec change (README [CON], 2026-11-03; dreeves: "i guess just apply common sense here too"): until then this qual
    # expected cores counted from the latest start; counted so, they began near 0 with each plan or relaunch, before its
    # first seeds ended, and the chance rose over its first hour.  Spec change (2026-11-04): until then cores the search
    # CPU of the seeds ended in the last hour over the seconds of it in which the campaign ran (see
    # q_cores_are_the_seeds_running_times_their_cpu_share), and this qual's name q_cores_count_the_last_hour_s_search_across_relaunches.
    d = campaign(journal=JOURNAL + STOP + AGAIN)
    try:
        for now in (4001.0, 5200.0):
            assert close(chance.of(d, 'camp', '528:12', now), expected(1430.0, 2 * 1430.0 / 4800.0)), now
    finally:
        shutil.rmtree(d)


def q_of_gives_the_chance_now_once_the_target_is_not_live():
    # Replicata: chance.of(root, 'camp', target, 5200) for campaign(): at 864:13, which no plan holds; at 720:13 after a
    # witness and its stop (arm_stop, reason witness); after the witness alone (journaled just before the stop); after
    # a checkpoint's stop; at 528:12 after the campaign's end (STOP); and after that end and a relaunch (AGAIN).
    # Expectata: AssertionError at 864:13; at 720:13, each, its cpu_hours (seed 6's 999 s) and no rate, cores or chance
    # (None, None and p empty), as no probe seed there measured its exposure; at 528:12 after the end its chance as of
    # 5200 with nothing running there: cores 0, so the chance within each t 0; and after the relaunch, when 528:12 is
    # live again, its chance as in q_cores_continue_across_relaunches.
    # Spec change (dreeves, 2026-11-04: "why did the probability graph disappear for the 528:12 search just because the
    # search was aborted? shouldn't it stay there for posterity like the ETA graph does? is this another anti-magic
    # violation?"): until then None for every target not live (q_of_is_none_unless_the_target_is_live, after the
    # coordinator, 2026-11-03: "for each live witness campaign target"), and so no chance chart once a search stopped.
    # Spec change (README [CON], 2026-11-03; dreeves: "i guess just apply common sense here too"): until then cores 0 s
    # over the 1200 s since the relaunch.  Spec change (2026-11-04): until then cores the search CPU of the seeds ended
    # in the last hour over the seconds of it in which the campaign ran (see q_cores_are_the_seeds_running_times_their_cpu_share).
    witness = dict(time=3300.0, event='witness', cell='720:13', k=6, f=170, code='AB', order=13, plus=360)
    stop = lambda reason: dict(time=3301.0, event='arm_stop', cell='720:13', reason=reason)
    d = campaign()
    try:
        expect_assertion(chance.of, d, 'camp', '864:13', 5200.0)
    finally:
        shutil.rmtree(d)
    unmeasured = dict(cpu_hours=999.0 / 3600, rate=None, cores=None, hours=list(chance.HOURS), p=[], exists=None, found=[])
    for journal, target, want in ((JOURNAL + [witness, stop('witness')], '720:13', unmeasured), (JOURNAL + [witness], '720:13', unmeasured),
                                  (JOURNAL + [stop('checkpoint')], '720:13', unmeasured), (JOURNAL + STOP, '528:12', expected(1430.0, 0.0))):
        d = campaign(journal=journal)
        try:
            got = chance.of(d, 'camp', target, 5200.0)
            assert close(got, want), (target, journal[-1], got and {k: v for k, v in got.items() if k != 'p'})
        finally:
            shutil.rmtree(d)
    assert set(expected(1430.0, 0.0)['p']) == {0.0}
    d = campaign(journal=JOURNAL + STOP + AGAIN)
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        assert close(got, expected(1430.0, 2 * 1430.0 / 4800.0)), got and {k: v for k, v in got.items() if k != 'p'}
    finally:
        shutil.rmtree(d)


def q_without_a_finished_probe_seed_there_is_no_chance_yet():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() with JOURNAL less probe seed 1's end (its probe
    # still running), and no probe files.
    # Expectata: no rate, no cores (None, each) and no chance (p empty), as nothing has measured the target's exposure
    # yet; its CPU-hours as before, less the probe's (430 s); hours chance.HOURS.
    # Spec change (2026-11-04): until then cores 230 s over the last hour's 3600 s, the seeds' search CPU that ended in it.
    d = campaign(journal=[r for r in JOURNAL if not (r['event'] == 'seed_end' and r['k'] == 1)], probes={})
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        assert close(got, dict(cpu_hours=430.0 / 3600, rate=None, cores=None, hours=list(chance.HOURS), p=[], exists=None, found=[])), got
    finally:
        shutil.rmtree(d)


def q_earlier_plans_hours_without_a_witness_count():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() with the archived plans plan1 (PLAN1, at 528:12)
    # and plan2 (PLAN2, at 768:13), as the campaign archives a plan when it starts the next.
    # Expectata (README [CON], 2026-11-03: "Shouldn't the probability generally go down, conditional on not having found
    # anything so far?"): the chance given no witness in any of the campaign's plans at the target: its CPU-hours every
    # plan's (730 s in the live one, and plan1's 1000 + 300 s: its plain seed's and its probe's rounds'), 768:13's left
    # out; the exposure spent each plan's own rate times its CPU-hours there (their pins, and so their rates, differ:
    # 0.0054 per CPU-hour in the live plan, 3.6e-3 in plan1); the rate the live plan's, as before; the cores its seeds
    # running (7 and 8) times the search CPU per second of life of the seeds that ended in the hour up to the latest end,
    # plan1's among them: 730 + 1000 + 300 s over 3900 + 300 + 400 s.
    # Resultata before: the archived plans left out, so each new plan forgot the hours searched before it (its CPU-hours
    # 730 s, its exposure 0.0054 x 730 / 3600).
    # Spec change (2026-11-04): until then cores 530 s over the last hour's 3600 s, the search CPU of the seeds ended in
    # it (see q_cores_are_the_seeds_running_times_their_cpu_share).
    d = campaign(archives=(('plan1', PLAN1), ('plan2', PLAN2)))
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        rate, early = 4.5e-4 / (300.0 / 3600), 3e-4 / (300.0 / 3600)
        spent, cores = rate * 730.0 / 3600 + early * 1300.0 / 3600, 2 * 2030.0 / 4600.0
        want = dict(cpu_hours=2030.0 / 3600, rate=rate, cores=cores, hours=list(chance.HOURS),
                    p=chance.within(PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd'], spent, [rate * cores * t for t in chance.HOURS]),
                    exists=chance.exists(PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd'], spent),
                    found=chance.found(PRIOR['mean'], PRIOR['sd'], spent, [rate * cores * t for t in chance.AHEAD]))
        assert close(got, want), got and {k: v for k, v in got.items() if k != 'p'}
    finally:
        shutil.rmtree(d)


def q_cores_continue_across_a_plan_switch():
    # Replicata: chance.of(root, 'camp', '528:12', 1300) for a campaign whose live plan was launched at 1000, its probe
    # seed 1 (ROUNDS) from 1000 to 1200 and plain seeds 2 and 3 running from 1000, with two archived plans: plan1 at
    # 768:13 (launched at 100; a plain seed of 5000 CPU s from 100 to 300; ended at 390) and plan2 at 528:12 (launched at
    # 400; plain seed 1 from 400 to 950, 400 CPU s; probe seed 2 from 400 to 960, its rounds EARLY; ended at 990).
    # Expectata (README [CON], 2026-11-03): cores the live plan's seeds running (2 and 3) times the search CPU per second
    # of life of the seeds at 528:12 that ended in the hour up to the latest end, plan2's among them: 300 + 400 + 300 s
    # over 200 + 550 + 560 s, plan1's seed at 768:13 left out; CPU-hours 1000 s; the rate the live plan's (ROUNDS), the
    # exposure spent each plan's rate times its CPU-hours there.
    # Resultata before: cores 0, as nothing had ended since the live plan's start.
    # Spec change (2026-11-04): until then the live plan had no probe seed and cores 700 s over the seconds of the last
    # hour in which a plan ran at 528:12, and a second case stopped 528:12 in plan2 at 600, cutting that span (see
    # q_cores_are_the_seeds_running_times_their_cpu_share).
    other = dict(cells=('768:13',), probes={},
                 journal=[dict(time=100.0, event='start')] + life(100.0, 300.0, 'plain', 1, 5000.0, cell='768:13') + [dict(time=390.0, event='end', reason='signal')])
    early = ([dict(time=400.0, event='start'), begun(400.0, 'plain', 1), begun(400.0, 'probe', 2), seed(950.0, 'plain', 1, 400.0),
              seed(960.0, 'probe', 2, 2000.0), dict(time=990.0, event='end', reason='signal')])
    journal = [dict(time=1000.0, event='start'), begun(1000.0, 'probe', 1), begun(1000.0, 'plain', 2), begun(1000.0, 'plain', 3),
               seed(1200.0, 'probe', 1, 900.0)]
    d = campaign(journal=journal, archives=(('plan1', other),
                 ('plan2', dict(cells=('528:12',), probes={os.path.join('camp', 'seeds', '528_12_s2'): probe_lines(EARLY)}, journal=early))))
    try:
        got = chance.of(d, 'camp', '528:12', 1300.0)
        rate, cores = 4.5e-4 / (300.0 / 3600), 2 * 1000.0 / 1310.0
        spent = rate * 300.0 / 3600 + 3e-4 / (300.0 / 3600) * 700.0 / 3600
        want = dict(cpu_hours=1000.0 / 3600, rate=rate, cores=cores, hours=list(chance.HOURS),
                    p=chance.within(PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd'], spent, [rate * cores * t for t in chance.HOURS]),
                    exists=chance.exists(PRIOR['p_exists'], PRIOR['mean'], PRIOR['sd'], spent),
                    found=chance.found(PRIOR['mean'], PRIOR['sd'], spent, [rate * cores * t for t in chance.AHEAD]))
        assert close(got, want), got and {k: v for k, v in got.items() if k != 'p'}
    finally:
        shutil.rmtree(d)


def q_cores_are_the_seeds_running_times_their_cpu_share():
    # Replicata: chance.of(root, 'camp', '528:12', now) for a made-up campaign run as plan 11 runs, in batches of 8
    # seeds that start together and end 6400 s later: launched at 1000; the first batch, seeds 1 to 8 (seed 1 a probe,
    # its rounds ROUNDS, 300 CPU s of search; the others plain, 3000 CPU s each), from 1000 to 7400; the second, seeds
    # 9 to 16 (plain, 6000 CPU s each), from 7400 to 13800; and the third, seeds 17 to 24, running from 13800; at now
    # 14400 (10 minutes into the third batch) and 17500 (more than an hour into it).
    # Expectata (2026-11-04): at both times, cores the 8 seeds running times the search CPU per second of life of the
    # seeds that ended in the hour up to the latest end, the second batch's (48000 s over 51200 s): 7.5; the first
    # batch's left out, ended 6400 s before.
    # Resultata before: 8 x 6000 / 3600 = 13.3 at 14400 (the second batch's whole CPU in the last hour's 3600 s) and 0
    # at 17500 (no seed ended in its last hour), as in plan 11, whose chance chart read 0 in the last 45 minutes of each
    # 107-minute batch.
    journal = ([dict(time=1000.0, event='start')] + life(1000.0, 7400.0, 'probe', 1, 900.0)
               + [x for k in range(2, 9) for x in life(1000.0, 7400.0, 'plain', k, 3000.0)]
               + [x for k in range(9, 17) for x in life(7400.0, 13800.0, 'plain', k, 6000.0)]
               + [begun(13800.0, 'plain', k) for k in range(17, 25)])
    d = campaign(journal=journal, cells=('528:12',))
    try:
        for now in (14400.0, 17500.0):
            got = chance.of(d, 'camp', '528:12', now)
            assert close(got, expected(300.0 + 7 * 3000.0 + 8 * 6000.0, 7.5)), (now, got and {k: v for k, v in got.items() if k != 'p'})
    finally:
        shutil.rmtree(d)


def as_it_stood(t, journal=JOURNAL, archives=(('plan1', PLAN1),)):
    """campaign()'s arguments for the made-up campaign as it stood just before time t: its plans begun by then, each
    with its records from before then (its files all kept: a seed's files are read only once its end is a record)."""
    return dict(journal=[r for r in journal if r['time'] < t],
                archives=tuple((name, dict(a, journal=[r for r in a['journal'] if r['time'] < t])) for name, a in archives if a['journal'][0]['time'] < t))


def q_history_gives_the_chance_as_it_stood():
    # Replicata: chance.history(root, 'camp', '528:12', 5200) for campaign() with PLAN1 archived (plan1, at 528:12,
    # from 100 to 600) before JOURNAL (from 1000); and, for each time t it gives, chance.of(root_t, 'camp', '528:12', t)
    # for the campaign as it stood just before t (as_it_stood).
    # Expectata (README [CON], 2026-11-03; dreeves: "the curve should fall in light of the conditional probability but
    # it should remain historically accurate, yes?"): a point every 900 s from plan1's start, at 1000, 1900, 2800, 3700
    # and 4600, and one at now, 5200, each [t, p6, p24] with p6 and p24 chance.of's chance within 6 and 24 h as of t,
    # kept where 528:12 was live with a rate: 3700, 4600 and 5200 (at 1000 nothing ran just before; at 1900 and 2800
    # the live plan's probe seed had not ended, so chance.of then gave no chance); and shown, what the page reads,
    # chance.of's chance now with since, plan1's start (100), and this history added.
    d = campaign(archives=(('plan1', PLAN1),))
    try:
        got = chance.history(d, 'camp', '528:12', 5200.0)
        want = []
        for t in (3700.0, 4600.0, 5200.0):
            e = campaign(**as_it_stood(t))
            try:
                c = chance.of(e, 'camp', '528:12', t)
                want.append([t, c['p'][chance.HOURS.index(6)], c['p'][chance.HOURS.index(24)]])
            finally:
                shutil.rmtree(e)
        assert close(got, want), (got, want)
        for t in (1900.0, 2800.0):
            e = campaign(**as_it_stood(t))
            try:
                assert (chance.of(e, 'camp', '528:12', t) or {}).get('p', []) == [], t
            finally:
                shutil.rmtree(e)
        # its odds (since 2026-11-04, the two graphs dreeves asked for) are q_shown_carries_the_odds's
        assert {k: v for k, v in chance.shown(d, 'camp', '528:12', 5200.0).items() if k != 'odds'} == dict(chance.of(d, 'camp', '528:12', 5200.0), since=100.0, history=got)
    finally:
        shutil.rmtree(d)


def q_history_falls_while_nothing_is_found():
    # Replicata: chance.history(root, 'camp', '528:12', now) for a made-up campaign launched at 1000 whose probe seed 1
    # (ROUNDS, 300 CPU s of search) ran from 1100 to 1400, then plain seeds 2 to 63 one after another, 300 s and 300 CPU
    # s each, the last running at now 20000, without a witness: one seed running at a time, at a share of 1.
    # Expectata: the chance within 6 h and within 24 h never rises from a point to the next, and is lower at the last
    # point than at the first: the same search, more hours without a find.
    # Spec change (2026-11-04): until then the seeds' starts were not journaled and the qual held from 4600 on, once the
    # cores' hour was full (see q_cores_are_the_seeds_running_times_their_cpu_share).
    journal = ([dict(time=1000.0, event='start')] + life(1100.0, 1400.0, 'probe', 1, 900.0)
               + [x for k in range(2, 64) for x in life(1400.0 + 300.0 * (k - 2), 1400.0 + 300.0 * (k - 1), 'plain', k, 300.0)])
    d = campaign(journal=journal, cells=('528:12',))
    try:
        got = chance.history(d, 'camp', '528:12', 20000.0)
        assert len(got) > 10 and all(b[1] <= a[1] and b[2] <= a[2] for a, b in zip(got, got[1:])), got
        assert got[-1][1] < got[0][1] and got[-1][2] < got[0][2], got
    finally:
        shutil.rmtree(d)


def q_shown_keeps_the_history_once_the_search_stops():
    # Replicata: chance.shown(root, 'camp', '528:12', 20000) for q_history_falls_while_nothing_is_found's campaign,
    # stopped at 10300 (a SIGTERM: its driver cancels seed 31, running since 10100, after 200 CPU s, then ends), and
    # chance.history at the stop, 10300.
    # Expectata (dreeves, 2026-11-04: "shouldn't it stay there for posterity like the ETA graph does?"): what the page
    # reads, not None: chance.of's chance as of 20000 with since (the launch, 1000) and the history added; that chance's
    # cpu_hours the probe's 300 s of rounds, seeds 2 to 30's 300 s each and seed 31's 200 s, its rate probe seed 1's,
    # its cores 0 and so its chance within each t 0, nothing running there after the stop; and its history the one at
    # the stop less that one's last point (its now, 10300): every quarter hour while the search ran, none after it.
    # Resultata before: None, and so no chart, once the search stopped.
    journal = ([dict(time=1000.0, event='start')] + life(1100.0, 1400.0, 'probe', 1, 900.0)
               + [x for k in range(2, 31) for x in life(1400.0 + 300.0 * (k - 2), 1400.0 + 300.0 * (k - 1), 'plain', k, 300.0)]
               + [begun(10100.0, 'plain', 31), seed(10300.0, 'plain', 31, 200.0, cancelled=True), dict(time=10300.0, event='end', reason='signal')])
    d = campaign(journal=journal, cells=('528:12',))
    try:
        got = chance.shown(d, 'camp', '528:12', 20000.0)
        at_stop = chance.history(d, 'camp', '528:12', 10300.0)
        assert got is not None, got
        assert close({k: v for k, v in got.items() if k not in ('since', 'history', 'odds')}, expected(300.0 + 29 * 300.0 + 200.0, 0.0)), got   # odds: q_shown_carries_the_odds (2026-11-04)
        assert got['since'] == 1000.0 and len(at_stop) > 10 and at_stop[-1][0] == 10300.0, (got['since'], at_stop[-1:])
        assert got['history'] == at_stop[:-1] and got['history'][-1][0] == 10000.0, (got['history'][-2:], at_stop[-2:])
    finally:
        shutil.rmtree(d)


def q_shown_carries_the_odds():
    # Replicata: chance.shown(root, 'camp', '528:12', 20000) for q_history_falls_while_nothing_is_found's campaign (one
    # seed running at a time from 1400 on, the last at 20000) and for q_shown_keeps_the_history_once_the_search_stops's
    # (stopped at 10300), read at 20000.
    # Expectata (dreeves, 2026-11-04: "1. probability a partition exists ... a simple monotone decreasing time series. 2.
    # probability of finding a partition by time t *conditional on a partition existing* and also conditional on not
    # having found one so far ... every timestep we'd draw a new version of the graph that starts going up from zero
    # starting now ... draw the current one bolded and the previous ones ... more and more faded"): odds, with basis
    # 'campaign', ahead chance.AHEAD; exists, [t, P(exists)] at the history's times and at now, never rising, each
    # chance.exists as the campaign stood then; curves, [t, P(found within each hour of AHEAD | exists)], one at every
    # fourth of the history's points back from its last, within chance.BACK hours of it, and one at now, each starting
    # at 0 and never falling, now's the last.  Running, now's curve rises; stopped, nothing runs, so now's is 0 throughout.
    # Resultata before: no odds.
    seeds = lambda last: [x for k in range(2, last) for x in life(1400.0 + 300.0 * (k - 2), 1400.0 + 300.0 * (k - 1), 'plain', k, 300.0)]
    running = [dict(time=1000.0, event='start')] + life(1100.0, 1400.0, 'probe', 1, 900.0) + seeds(64)
    stopped = ([dict(time=1000.0, event='start')] + life(1100.0, 1400.0, 'probe', 1, 900.0) + seeds(31)
               + [begun(10100.0, 'plain', 31), seed(10300.0, 'plain', 31, 200.0, cancelled=True), dict(time=10300.0, event='end', reason='signal')])
    for journal, live in ((running, True), (stopped, False)):
        d = campaign(journal=journal, cells=('528:12',))
        try:
            got = chance.shown(d, 'camp', '528:12', 20000.0)
            o = got['odds']
            assert set(got) == SHOWN, sorted(got)
            assert o['basis'] == 'campaign' and o['ahead'] == list(chance.AHEAD), o.keys()
            times = [t for t, _, _ in got['history']]
            assert [t for t, _ in o['exists']] == times + [20000.0] * (times[-1] != 20000.0), ([t for t, _ in o['exists']][-3:], times[-3:])
            assert all(b[1] <= a[1] for a, b in zip(o['exists'], o['exists'][1:])), o['exists']
            assert o['exists'][-1][1] == got['exists'], (o['exists'][-1], got['exists'])
            starts = [t for t, _ in o['curves']]
            want = [t for t in times[::-1][::4] if t >= times[-1] - 3600 * chance.BACK][::-1]
            assert starts == want + [20000.0] * (want[-1] != 20000.0), (starts, want)
            assert all(c[0] == 0.0 and all(x <= y for x, y in zip(c, c[1:])) and len(c) == len(chance.AHEAD) for _, c in o['curves']), o['curves'][:1]
            assert (o['curves'][-1][1][-1] > 0) == live and (live or set(o['curves'][-1][1]) == {0.0}), (live, o['curves'][-1][1][:3])
        finally:
            shutil.rmtree(d)


def q_lindy_shown_is_shown_s_form():
    # Replicata: chance.lindy_shown(0.01, 1000, 1000 + 30 h + 100 s): an exhaustive search begun at 1000 s with P(exists)
    # 0.01 and no estimate of its own, 30 h and 100 s along.
    # Expectata (dreeves, 2026-11-04: "can we get that 3rd chart as well, consistently, after the P(exists) and
    # P(find|exists) charts?"): shown's form (its keys SHOWN), so that every modeled search draws the same three graphs:
    # no CPU-hours, rate or cores, which its model does not use; hours chance.HOURS and p its chance within each, the
    # prior times chance.lindy_found on its age; exists the prior and found lindy_found over chance.AHEAD; since its
    # start; its history [t, p6, p24] at each quarter hour from its start and at now, each the prior times lindy_found on
    # its age then; its odds with basis 'lindy', ahead chance.AHEAD, exists the prior at the history's times, and curves
    # at every fourth of those times back from now, within chance.BACK hours of it, each lindy_found on its age then,
    # now's last.
    # Spec change (the same request): until then chance.lindy gave an exhaustive search's odds alone, exists the prior
    # at its start and at now and curves at each whole hour back from now, and it had no chance, so no third graph.
    # Resultata before: no chance.lindy_shown (AttributeError).
    t0, now = 1000.0, 1000.0 + 30 * 3600 + 100
    got = chance.lindy_shown(0.01, t0, now)
    tau = (now - t0) / 3600
    assert set(got) == SHOWN and got['since'] == t0, (sorted(got), got.get('since'))
    assert got['cpu_hours'] is None and got['rate'] is None and got['cores'] is None, (got['cpu_hours'], got['rate'], got['cores'])
    assert got['hours'] == list(chance.HOURS) and close(got['p'], [0.01 * x for x in chance.lindy_found(tau, chance.HOURS)]), got['p'][:3]
    assert got['exists'] == 0.01 and close(got['found'], chance.lindy_found(tau, chance.AHEAD)), got['exists']
    times = [t0 + 900.0 * k for k in range(1, 121)] + [now]
    at = lambda t, s: 0.01 * chance.lindy_found((t - t0) / 3600, [s])[0]
    assert close(got['history'], [[t, at(t, 6), at(t, 24)] for t in times]), got['history'][:2]
    o = got['odds']
    assert o['basis'] == 'lindy' and o['ahead'] == list(chance.AHEAD) and o['exists'] == [[t, 0.01] for t in times], o['exists'][:2]
    want = [t for t in times[::-1][::4] if t >= now - 3600 * chance.BACK][::-1]
    assert [t for t, _ in o['curves']] == want and want[-1] == now, ([t for t, _ in o['curves']][-3:], want[-3:])
    assert all(close(c, chance.lindy_found((t - t0) / 3600, chance.AHEAD)) for t, c in o['curves']), o['curves'][:1]


def q_odds_wait_for_a_measured_rate():
    # Replicata: chance.shown(root, 'camp', '528:12', 5200) for q_without_a_finished_probe_seed_there_is_no_chance_yet's
    # campaign (its probe seed still running, so no rate measured anywhere); and for a campaign whose archived plan1
    # searched 528:12 from 100 to 2000 (probe seed 1 from 100 to 400, rounds EARLY; plain seed 2 from 100 to 2000, 1700
    # CPU s), its live plan from 3000 with probe seed 3 and plain seed 4 running.
    # Expectata (dreeves, 2026-11-04, of the three graphs laid out "consistently"): shown's form, its odds drawn from
    # measured points alone, as its history is: in the first, no history and odds whose exists and curves are empty, so
    # that each graph shows its axes alone; in the second, the history plan1's two points while it ran (1000 and
    # 1900), exists at those and the curve at 1900 alone, with nothing at now, where the live plan has no rate yet.
    # Resultata before: IndexError (chance.odds read the last of no points); and in the second, exists and curves ended
    # with now's unmeasured chance, None and [].
    first = campaign(journal=[r for r in JOURNAL if not (r['event'] == 'seed_end' and r['k'] == 1)], probes={})
    plan1 = dict(cells=('528:12',), probes={os.path.join('camp', 'seeds', '528_12_s1'): probe_lines(EARLY)},
                 journal=[dict(time=100.0, event='start'), begun(100.0, 'probe', 1), begun(100.0, 'plain', 2), seed(400.0, 'probe', 1, 900.0),
                          seed(2000.0, 'plain', 2, 1700.0), dict(time=2000.0, event='end', reason='signal')])
    second = campaign(journal=[dict(time=3000.0, event='start'), begun(3000.0, 'probe', 3), begun(3000.0, 'plain', 4)],
                      probes={}, cells=('528:12',), archives=(('plan1', plan1),))
    try:
        got = chance.shown(first, 'camp', '528:12', 5200.0)
        assert set(got) == SHOWN and got['history'] == [], (sorted(got), got['history'])
        assert got['odds'] == dict(basis='campaign', ahead=list(chance.AHEAD), exists=[], curves=[]), got['odds']
        got = chance.shown(second, 'camp', '528:12', 5200.0)
        assert set(got) == SHOWN and [t for t, _, _ in got['history']] == [1000.0, 1900.0], got['history']
        assert [t for t, _ in got['odds']['exists']] == [1000.0, 1900.0], got['odds']['exists']
        assert all(isinstance(p, float) for _, p in got['odds']['exists']) and [t for t, _ in got['odds']['curves']] == [1900.0], got['odds']
    finally:
        shutil.rmtree(first)
        shutil.rmtree(second)


def q_of_refuses_malformed_archives():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() with: PLAN1 archived as plan2 with no plan1 (a
    # gap in the numbering); PLAN1 archived as plan1 naming another directory; PLAN1 archived with its journal less its
    # start; and PLAN1 archived without its probe seed's end and files, so that nothing measured the exposure of its
    # 1000 CPU s at 528:12.
    # Expectata: AssertionError, each: the last because the chance cannot be conditioned on hours of unknown exposure.
    for archives in ((('plan2', PLAN1),), (('plan1', dict(PLAN1, dir='elsewhere')),), (('plan1', dict(PLAN1, journal=PLAN1['journal'][1:])),),
                     (('plan1', dict(PLAN1, probes={}, journal=[r for r in PLAN1['journal'] if r.get('k') != 2])),)):
        d = campaign(archives=archives)
        try:
            expect_assertion(chance.of, d, 'camp', '528:12', 5200.0)
        finally:
            shutil.rmtree(d)


def q_of_refuses_malformed_campaigns():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() with: probe seed 1's file without its done line
    # (a finished probe seed has one); its done line counting 2 rounds of 3; its rounds numbered 1, 3, 2; its header
    # missing; a seed_end of a kind other than plain or probe; the plan's dir other than camp (its seeds' prefixes are
    # paths from the root only if it names camp); no prior for 528:12; a prior with P(exists) 1.5, with sd 0, with an
    # extra field, without its sd; a prior with P(exists) 1.5 before any probe seed has finished (so that no chance is
    # computed with it yet); a seed_end without its seed_start; a seed started twice; a seed ending at its start; an
    # end record while seeds 7 and 8 run; a second start without an end before it; and at now 1000, before which the
    # campaign had not begun.
    # Expectata: AssertionError, each: a malformed prior fails at once, not at the first probe seed's end.
    # Spec change (2026-11-04): the seeds' starts, the runs at an end and the alternation of starts and ends checked
    # (see q_cores_are_the_seeds_running_times_their_cpu_share); until then the reason for the last was that at the
    # campaign's start there was no span to measure cores over.
    prefix = os.path.join('camp', 'seeds', '528_12_s1')
    lines = probe_lines(ROUNDS)
    swapped = lines[:2] + [lines[3], lines[2]] + lines[4:]
    bad = [dict(probes={prefix: lines[:-1]}), dict(probes={prefix: lines[:-1] + [dict(lines[-1], rounds=2)]}),
           dict(probes={prefix: swapped}), dict(probes={prefix: lines[1:]}),
           dict(journal=JOURNAL + [begun(3250.0, 'odd', 9), dict(seed(3300.0, 'plain', 9, 1.0), kind='odd')]), dict(plan_dir='elsewhere'),
           dict(priors={'720:13': PRIOR}), dict(priors={'528:12': dict(PRIOR, p_exists=1.5)}),
           dict(priors={'528:12': dict(PRIOR, sd=0.0)}), dict(priors={'528:12': dict(PRIOR, extra=1)}),
           dict(priors={'528:12': {k: v for k, v in PRIOR.items() if k != 'sd'}}),
           dict(priors={'528:12': dict(PRIOR, p_exists=1.5)}, probes={},
                journal=[r for r in JOURNAL if not (r['event'] == 'seed_end' and r['k'] == 1)]),
           dict(journal=JOURNAL + [seed(3300.0, 'plain', 9, 1.0)]), dict(journal=JOURNAL + [begun(3300.0, 'plain', 7)]),
           dict(journal=JOURNAL + life(3300.0, 3300.0, 'plain', 9, 1.0)),
           dict(journal=JOURNAL + [dict(time=3500.0, event='end', reason='signal')]),
           dict(journal=JOURNAL + [dict(time=3500.0, event='start', resumed=True)])]
    for kw in bad:
        d = campaign(**kw)
        try:
            expect_assertion(chance.of, d, 'camp', '528:12', 5200.0)
        finally:
            shutil.rmtree(d)
    d = campaign()
    try:
        expect_assertion(chance.of, d, 'camp', '528:12', 1000.0)
    finally:
        shutil.rmtree(d)


def q_the_beam_campaign_s_priors_are_the_bandit_s():
    # Replicata: the beam campaign's chance.json (scratch/beam-campaign-20261103), and the bandit's rerun of 2026-11-03:
    # analysis.py's P_EXISTS (its stated P(exists) per open cell, central values) and ranking.json's refit (the
    # pinned-beam family's mean and spread of log2 theta, refitted with 768:13 and 720:13).
    # Expectata (the coordinator, 2026-11-03: "528:12's P(exists) is the bandit's stated assumption, 0.3. Put the
    # per-target prior parameters in a small data file in the campaign directory, with their sources"): a prior per
    # target the bandit lists as open and a beam campaign could search (P_EXISTS's cells less 768:13, settled at 13 on
    # 2026-11-03, and 288:10, where BGPW's ILP excludes the symmetric sequences the beam makes): each P(exists) the
    # bandit's, 528:12's 0.3, and each mean and sd the refit's; and sources, each a non-empty statement naming a file
    # that exists.
    sys.path.insert(0, BANDIT)
    import analysis                    # its constants; it runs nothing on import
    doc = json.load(open(os.path.join(HERE, CAMPAIGN, 'chance.json')))
    refit = json.load(open(os.path.join(BANDIT, 'ranking.json')))['refit']
    cells = sorted(set(analysis.P_EXISTS) - {'768:13', '288:10'})
    assert sorted(doc['targets']) == cells and doc['targets']['528:12']['p_exists'] == 0.3, sorted(doc['targets'])
    assert all(doc['targets'][c] == dict(p_exists=analysis.P_EXISTS[c][0], mean=refit['mu'], sd=refit['sigma']) for c in cells), doc
    names = [w for s in doc['sources'].values() for w in s.split() if w.startswith('scratch/')]
    assert doc['sources'] and all(isinstance(s, str) and s for s in doc['sources'].values()) and names, doc['sources']
    assert all(os.path.exists(os.path.join(HERE, w.rstrip(',.;:)'))) for w in names), names


def q_work_point_mass_has_exact_bayesian_probabilities_and_eta():
    # Replicata: total work 100, done 20, rate 10/hour, prior existence 1/5.
    # Expectata: no-find survival 4/5 gives posterior existence 1/6; conditional
    # find time is uniform on the next 8 hours. Completion has that uniform mass
    # 1/6 and a mass 5/6 at 8 hours, so its 10%, 50%, 90% times are 4.8, 8, 8 h.
    # Spec change (Claude, 2026-11-06): every band (0.1, 0.9) since the coordinator's calibration study for dreeves
    # (scratch/calibration-20261106: "80% that actually means 80%"); the quantiles here moved with it (5%, 50%, 95% at 2.4, 8, 8 h before).
    got = chance.work(0.2, [100], 20, [10], [1])
    assert close(got['exists'], 1 / 6), got
    assert close(got['found'], [min(h / 8, 1) for h in chance.AHEAD]), got['found']
    assert close(got['p'], [min(h / 8, 1) / 6 for h in chance.HOURS]), got['p']
    assert close(got['completion'], [h / 48 if h < 8 else 1 for h in chance.HOURS]), got['completion']
    assert close(got['to_go'], dict(median=8 * 3600, lo=4.8 * 3600, hi=8 * 3600)), got['to_go']
    assert got['hours'] == list(chance.HOURS) and all(got[k] is None for k in ('cpu_hours', 'rate', 'cores')), got


def q_work_prior_endpoints_and_no_find_progress():
    # Replicata: the same known total/rate with prior zero and one; then prior
    # 1/5 at 0, 20 and 90 units done without a witness.
    # Expectata: zero prior keeps chance zero with exhaustion in 8 h; one prior
    # has a uniform find/completion time with quantiles .8,4,7.2 h. Increasing
    # checked work lowers existence for this fixed total; at zero work it is 1/5.
    # Spec change (Claude, 2026-11-06): every band (0.1, 0.9) since the coordinator's calibration study for dreeves
    # (scratch/calibration-20261106: "80% that actually means 80%"); the quantiles here moved with it (.4, 4, 7.6 h at 5%, 50%, 95% before).
    absent = chance.work(0, [100], 20, [10], [1])
    present = chance.work(1, [100], 20, [10], [1])
    assert absent['exists'] == 0 and absent['p'] == [0] * len(chance.HOURS), absent
    assert close(absent['to_go'], dict(median=28800, lo=28800, hi=28800)), absent['to_go']
    assert present['exists'] == 1 and close(present['p'], present['completion']), present
    assert close(present['to_go'], dict(median=14400, lo=2880, hi=25920)), present['to_go']
    values = [chance.work(0.2, [100], d, [10], [1])['exists'] for d in (0, 20, 90)]
    assert close(values[0], 0.2) and values[0] > values[1] > values[2], values


def q_work_irregular_weights_keep_total_rate_pairs():
    # Replicata: work totals 100 and 200, done 50, rates 10 and 50/hour,
    # weights 1/4 and 3/4, existence prior 2/5; also permute their paired rows.
    # Expectata: survival A=11/16, normalizer 7/8, posterior existence 11/35.
    # At 1 h find mass is 17/175, conditional find 17/55. At 3 h completion
    # is 141/175; the median and upper quantile are at the 3 h and 5 h atoms, the
    # lower 35/34 h, where the two spread masses, 17/175 an hour, reach 10%.
    # Spec change (Claude, 2026-11-06): every band (0.1, 0.9) since the coordinator's calibration study for dreeves
    # (scratch/calibration-20261106: "80% that actually means 80%"); the quantiles here moved with it (the lower at 35/68 h, its 5%, before).
    got = chance.work(0.4, [100, 200], 50, [10, 50], [0.25, 0.75])
    other = chance.work(0.4, [200, 100], 50, [50, 10], [0.75, 0.25])
    assert close(got, other), (got, other)
    assert close(got['exists'], 11 / 35), got['exists']
    assert close(got['found'][1], 17 / 55), got['found'][1]
    assert close(got['p'][chance.HOURS.index(1)], 17 / 175), got['p']
    assert close(got['completion'][chance.HOURS.index(3)], 141 / 175), got['completion']
    assert close(got['to_go'], dict(median=3 * 3600, lo=(35 / 34) * 3600, hi=5 * 3600)), got['to_go']


def q_work_conditions_structural_support_once():
    # Replicata: a work prior has 80% mass at 10 and 20% at 100, after 20 is
    # checked with the run still open. A zero-weight enormous draw is also added.
    # Expectata: the impossible short draw is conditioned out, not clamped to
    # immediate completion; result equals a single surviving 100-unit draw.
    got = chance.work(0.2, [10, 100, 1e100], 20, [1, 10, 1], [0.8, 0.2, 0])
    want = chance.work(0.2, [100], 20, [10], [1])
    assert close(got, want), (got, want)


def q_work_curves_factor_are_monotone_and_have_endpoints():
    # Replicata: irregular work/rate draws whose residual times are at most 20 h.
    # Expectata: all curves start at zero, rise within [0,1], and by 72 h reach
    # existence, one, one respectively; p is exists times found at shared hours.
    got = chance.work(0.3, [50, 120, 400], 20, [10, 20, 19], [0.1, 0.6, 0.3])
    for key in ('p', 'found', 'completion'):
        xs = got[key]
        assert xs[0] == 0 and all(0 <= x <= 1 + 1e-14 for x in xs), (key, xs)
        assert all(a <= b + 1e-14 for a, b in zip(xs, xs[1:])), (key, xs)
    assert close([got['p'][-1], got['found'][-1], got['completion'][-1]], [got['exists'], 1, 1]), got
    assert close([got['p'][chance.HOURS.index(h)] for h in chance.AHEAD],
                 [got['exists'] * f for f in got['found']]), got


def q_work_completion_quantiles_handle_ties_and_large_scale_ratios():
    # Replicata: no existence, residual times 1 and 1e40 hours with weights .85,.15;
    # then a guaranteed witness and two identical 8-hour residual times.
    # Expectata: exact weighted atoms give 1,1,1e40 h quantiles without a linear
    # bisection losing the small scale; duplicate rows remain one uniform law.
    # Spec change (Claude, 2026-11-06): every band (0.1, 0.9) since the coordinator's calibration study for dreeves
    # (scratch/calibration-20261106: "80% that actually means 80%"); the quantiles here moved with it (weights .9, .1 before, whose 1 h atom now holds the 90% point exactly, and the uniform law .4, 4, 7.6 h).
    atoms = chance.work(0, [1, 1e40], 0, [1, 1], [0.85, 0.15])
    assert close(atoms['to_go'], dict(median=3600, lo=3600, hi=1e40 * 3600)), atoms['to_go']
    ties = chance.work(1, [100, 180], 20, [10, 20], [0.3, 0.7])
    assert close(ties['to_go'], dict(median=14400, lo=2880, hi=25920)), ties['to_go']


def q_work_refuses_invalid_inputs_and_exhausted_support():
    # Replicata: invalid priors/done, mismatched or empty arrays, nonnumbers,
    # nonfinite/nonpositive totals and rates, invalid or unnormalized weights,
    # and work draws all already passed by the still-running search.
    # Expectata: assertion before returning a forecast; no silent repair or
    # fallback to a different model.
    good = (0.2, [100, 200], 20, [10, 20], [0.3, 0.7])
    bad = [(p, *good[1:]) for p in (-0.1, 1.1, True, float('nan'), float('inf'))]
    bad += [(good[0], good[1], d, good[3], good[4]) for d in (-1, True, float('nan'), float('inf'), 200)]
    bad += [(good[0], t, good[2], good[3], good[4]) for t in ([], [100], [[100, 200]], [0, 200],
             [-1, 200], [float('nan'), 200], [float('inf'), 200], ['100', '200'], [True, False])]
    bad += [(good[0], good[1], good[2], r, good[4]) for r in ([10], [0, 20], [-1, 20],
             [float('nan'), 20], [float('inf'), 20], ['10', '20'])]
    bad += [(*good[:4], w) for w in ([1], [0, 0], [-0.3, 1.3], [0.3, 0.6],
             [float('nan'), 0.7], [float('inf'), 0.7], [True, False])]
    for args in bad: expect_assertion(chance.work, *args)


def end_masses(p, total, done, weight):
    """Brute force's view of chance.work's posterior, from its docstring alone: the draws at or below done and those of
    weight 0 dropped and the rest's weights w renormalized; each draw W then carries the mass (1 - p) w at its end (no
    witness: the whole tree checked) and p w (W - done) / W spread evenly over the work from done to W (a witness,
    uniform in the tree's work, not in the work done), both over their sum.  As (W, at its end, spread) rows."""
    rows = [(W, w) for W, w in zip(total, weight) if W > done and w > 0]
    s = math.fsum(w for _, w in rows)
    rows = [(W, w / s, (W - done) / W) for W, w in rows]
    Z = math.fsum(w * ((1 - p) + p * q) for _, w, q in rows)
    return [(W, (1 - p) * w / Z, p * w * q / Z) for W, w, q in rows]


def mixture_quantile(rows, level):
    """The least x at which F(x) = sum of a [r <= x] + b min(1, x / r) over rows (r, a, b) reaches level: masses a at
    r and b spread evenly over [0, r]; by bisection on that exact CDF, to the floats' resolution."""
    F = lambda x: math.fsum(a * (r <= x) + b * min(1.0, x / r) for r, a, b in rows)
    lo, hi = 0.0, max(r for r, _, _ in rows)          # F(0) = 0 < level <= F(hi) = 1
    while lo < (lo + hi) / 2 < hi:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if F(mid) >= level else (mid, hi)
    return hi


def weighted_quantile(values, weights, level):
    """The least value whose cumulative weight, the values in increasing order, reaches level."""
    acc = 0.0
    for v, w in sorted(zip(values, weights)):
        acc += w
        if acc >= level: return v


def brute_work(p, total, done, rate, weight, quantiles):
    """chance.work's to_go (seconds) and total (work), {median, lo, hi}, by brute force (end_masses, mixture_quantile)
    at 0.5 and quantiles, a (lo, hi) pair."""
    rows = end_masses(p, total, done, weight)
    rates = {W: r for W, r, w in zip(total, rate, weight) if W > done and w > 0}
    levels = dict(median=0.5, lo=quantiles[0], hi=quantiles[1])
    return dict(to_go={k: 3600 * mixture_quantile([((W - done) / rates[W], a, b) for W, a, b in rows], q) for k, q in levels.items()},
                total={k: done + mixture_quantile([(W - done, a, b) for W, a, b in rows], q) for k, q in levels.items()})


# six draws of total work for done 20 (q_work_total_quantiles_match_brute_force): 15, at or below done, conditioned out;
# 1e4, of weight 0; and four survivors, 120, 300, 250 and 80, with weights renormalized from 0.8 to 1, 0.1625, 0.3875,
# 0.1375 and 0.3125, so that in increasing order their cumulative weights are 0.3125, 0.475, 0.6125 and 1
WORK_DRAWS = dict(total=[120, 15, 300, 250, 80, 1e4], done=20, rate=[7, 3, 11, 5, 2, 13], weight=[0.13, 0.2, 0.31, 0.11, 0.25, 0.0])


def q_work_total_quantiles_match_brute_force():
    # Replicata (dreeves, 2026-11-06: "should that progress bar be measuring amount of work, not time? ... we can still
    # have a 90% CI for amount of work remaining, right?"): chance.work on WORK_DRAWS with existence priors 0, 0.3 and 1;
    # the same draws at other rates, and at one rate for all; and the point mass of
    # q_work_point_mass_has_exact_bayesian_probabilities_and_eta.
    # Expectata: its total, the work done when the search ends, {median, lo, hi} at 0.5 and the work model's band
    # (chance.BANDS's work), from the same posterior weights as its to_go: with prior 0 (no witness: the whole tree),
    # the weighted quantiles of the survivors' totals, their weights renormalized: 80, 250 and 300; at every prior,
    # total and to_go the brute force's (brute_work: bisection on the exact CDF of masses from work's docstring alone);
    # total unchanged at other rates; at one rate r for all, done + r to_go; and 68, 100 and 100 for the point mass
    # (20 + 10/h x 4.8 h for its 10%; 44 at its 5% before the bands became (0.1, 0.9), 2026-11-06).
    # Resultata before: work returned no total (KeyError).
    d, band = WORK_DRAWS, chance.BANDS['work']
    got = chance.work(0, d['total'], d['done'], d['rate'], d['weight'])['total']
    survivors = [(W, w) for W, w in zip(d['total'], d['weight']) if W > d['done'] and w > 0]
    want = {k: weighted_quantile([W for W, _ in survivors], [w / 0.8 for _, w in survivors], q) for k, q in (('median', 0.5), ('lo', band[0]), ('hi', band[1]))}
    assert got == want == dict(median=250, lo=80, hi=300), (got, want)
    for p in (0, 0.3, 1):
        got = chance.work(p, d['total'], d['done'], d['rate'], d['weight'])
        want = brute_work(p, d['total'], d['done'], d['rate'], d['weight'], band)
        assert close(got['total'], want['total'], 1e-9) and close(got['to_go'], want['to_go'], 1e-9), (p, got['total'], got['to_go'], want)
        other = chance.work(p, d['total'], d['done'], [1, 2, 3, 4, 5, 6], d['weight'])
        assert other['total'] == got['total'], (p, other['total'], got['total'])
        one = chance.work(p, d['total'], d['done'], [10] * 6, d['weight'])
        assert close(one['total'], {k: d['done'] + 10 * v / 3600 for k, v in one['to_go'].items()}), (p, one)
    assert close(chance.work(0.2, [100], 20, [10], [1])['total'], dict(median=100, lo=68, hi=100)), chance.work(0.2, [100], 20, [10], [1])


# A fresh Python, given the directory of a copy of chance.py, the repository's root and WORK_DRAWS, prints as JSON what
# each estimator and the page's label make of that copy (q_each_band_and_the_coverage_are_set_in_one_place): chance's
# COVERAGE and BANDS; progress.ZS; progress.gott of 4 hours; the levels each of progress's other estimators asks
# numpy.quantile for (asked: lindy_urn, box_estimate, pool_estimate, stages_of on a made-up chain, and survey's tree
# estimate on quals_progress's tiny resolving run); chance.work on WORK_DRAWS at prior 0.3; and formtree_eta.attach's
# work_eta on the made-up live search of quals_formtree_eta's Attachment (a version-2 model), beside chance.work's
# total and the root scatter's quantiles at the work band on the same draws.
BAND_PROBE = r"""
import sys, os, json, copy, hashlib, pathlib, tempfile
from unittest import mock
sys.path[:0] = sys.argv[1:3]
import numpy as np
import chance, progress, formtree_eta
assert pathlib.Path(chance.__file__).parent == pathlib.Path(sys.argv[1]), chance.__file__
d = json.loads(sys.argv[3])
asked, real = [], np.quantile
def spy(a, q, *args, **kw):
    asked.append([float(v) for v in np.atleast_1d(q)])
    return real(a, q, *args, **kw)
np.quantile = spy
def levels(f):                                    # the levels f asks numpy.quantile for, call by call
    del asked[:]
    f()
    return [list(x) for x in asked]
progress.STAGES = [[dict(stage='own', run=['fanout.py', 672, 13]),
                    dict(stage='A', phases=[[[dict(per='token', processes=1, cpu=dict(median=2.0, lo=1.0, hi=8.0))]]])]]
sys.path.insert(0, os.path.join(sys.argv[2], 'quals'))
import quals_progress
journal, log = quals_progress.tiny('resolving')
start = progress.parse_log(log)[-1]['start']
asks = dict(urn=levels(lambda: progress.lindy_urn([3600.0, 7200.0], [600.0], 2, 2)),
            box=levels(lambda: progress.box_estimate([100.0] * 20, [10.0], 5, 2)),
            pool=levels(lambda: progress.pool_estimate([(0, 100, [1]), (1, 50, [])], {0: 2, 1: 3}, 1, 10.0, 0)),
            stages=levels(lambda: progress.stages_of(('fanout.py', 672, 13), 'running', None, np.zeros(progress.REPLICATES),
                                                     {'token': 3600.0}, 1.0)),
            tree=levels(lambda: progress.survey(64, 7, journal, log, [(1, 0, 'S', 'python3 overnight_v5.py 64 7')], start + 30, {}, {})))
root = pathlib.Path(tempfile.mkdtemp(prefix='band-probe-'))
(root / 'source').write_bytes(b'fixed input')
digest = hashlib.sha256(b'fixed input').hexdigest()
model = dict(version=2, kind='formtree', target='288:10', seed=28810, log_bias=0.0, discrepancy_log_sd=1.0, root_log_sd=.75,
             root_log_sd_uncertainty=.5, rate_log_sd=.35, samples=32, alpha=.5, checks={'source': digest},
             roots=[dict(name='a', blocks=[[10] * 8, [30] * 8], input_sha256=digest), dict(name='b', blocks=[[100] * 8, [300] * 8], input_sha256=digest)],
             provenance=dict(manifest_sha256=digest, samples_sha256=digest, seed_namespace='qual', source='source'), calibration=[],
             assumptions=dict(discrepancy='qual', rate='qual', witness='qual', interval='qual'))
(root / 'model.json').write_text(json.dumps(model))
old = dict(program='ftree.py', n=288, order=10, chance=dict(since=1000., history=[[1500., .003, .005]]),
           odds=dict(exists=[[1500., .01]], curves=[[1500., [0.] * 73]]))
(root / 'progress.js').write_text('progressData(' + json.dumps({'runs': [old]}) + ');\n')
s = dict(n=288, order=10, program='ftree.py', state='running', passes=[[1000, 2000]], to_go=dict(median=1000, lo=10, hi=19000),
         etas={}, display=dict(lindy=True, tracked=True))
w = dict(done=55, rate=10., roots=[dict(name='a', done=5, complete=False), dict(name='b', done=50, complete=False)], source_time=1990., source_age=10.)
with mock.patch.object(formtree_eta.formtree_work, 'read', return_value=w):
    meta = formtree_eta.attach(copy.deepcopy(s), root, root / 'model.json', .01, 2000., {})['display']['work_eta']
x = formtree_eta.draws(json.loads((root / 'model.json').read_text()), w, 65536)
order = np.argsort(x['root_log_sd'])
lo, hi = chance.BANDS['work']
scatter = np.interp([lo, .5, hi], np.cumsum(x['weight'][order]), x['root_log_sd'][order])
print(json.dumps(dict(COVERAGE=chance.COVERAGE, BANDS=chance.BANDS, ZS=progress.ZS, gott=progress.gott(4 * 3600), asked=asks,
                      work=chance.work(.3, d['total'], d['done'], d['rate'], d['weight']), coverage=meta['coverage'],
                      total=meta['total'], forecast=chance.work(.01, x['total'], w['done'], x['rate'] * 3600, x['weight'])['total'],
                      scatter=meta['root_log_sd_posterior'], quantiled=dict(zip(('lo', 'median', 'hi'), scatter.tolist())))))
"""
# a calibration's kind of change (q_each_band_and_the_coverage_are_set_in_one_place): another coverage for the page, and
# each estimator a band of its own, none of them today's (0.1, 0.9)
CALIBRATED = dict(coverage=0.7, bands=dict(tree=(0.11, 0.89), box=(0.12, 0.88), urn=(0.13, 0.87), pool=(0.14, 0.86),
                                           stages=(0.15, 0.85), gott=(0.16, 0.84), work=(0.17, 0.83)))


def q_each_band_and_the_coverage_are_set_in_one_place():
    # Replicata (the coordinator, 2026-11-06, for dreeves, who wants "80% that actually means 80%": the page labels its
    # intervals with one coverage, and each estimator draws its band at levels of its own, calibrated to give it; each
    # set in one place, so that the calibration changes values, not structure): chance.py, which must hold exactly one
    # COVERAGE line and one BANDS entry for each of the estimators tree, box, urn, pool, stages, gott and work, every band
    # (0.1, 0.9) and COVERAGE 0.8 (the coordinator, 2026-11-06, after scratch/calibration-20261106; (0.05, 0.95) and 0.9
    # before); a copy of it as it is, then one with CALIBRATED's values in those lines alone;
    # for each, BAND_PROBE in a fresh Python with that copy first on its path.
    # Expectata: chance.COVERAGE and chance.BANDS are the copy's; Gott's rule's band at gott's levels (a q / (1 - q) at
    # each); lindy_urn, box_estimate, pool_estimate, stages_of (for each later stage and for the total) and survey's tree
    # estimate ask numpy.quantile for their own entry's levels and no other; chance.work's to_go and total are
    # brute_work's at work's band; formtree_eta's work_eta has the coverage COVERAGE (the page's label), the total
    # chance.work's on its draws and root scatter quantiles at work's band; and progress.ZS, which reads stages.json's cpu
    # bands, stays at the standard normal's 5% and 95%, the quantiles those bands were measured at (stages.json's about),
    # whatever the bands are.
    # Resultata before: there was no COVERAGE or BANDS: one level set every band and the label (chance.LEVEL, earlier on
    # 2026-11-06), and before that progress.py, chance.py and formtree_eta.py each wrote 0.05, 0.95 and 0.9.
    import re, subprocess, statistics
    source = open(os.path.join(HERE, 'chance.py'), encoding='utf-8').read()
    names = list(CALIBRATED['bands'])
    assert re.findall(r'^COVERAGE = (\S+) ', source, re.M) == ['0.8'], re.findall(r'^COVERAGE = .*', source, re.M)
    assert all(len(re.findall(rf'^ +{name}=\(0\.1, 0\.9\)', source, re.M)) == 1 for name in names), names
    calibrated = re.sub(r'^COVERAGE = 0\.8 ', f'COVERAGE = {CALIBRATED["coverage"]} ', source, flags=re.M)
    for name, (lo, hi) in CALIBRATED['bands'].items():
        calibrated = re.sub(rf'^( +{name}=)\(0\.1, 0\.9\)', rf'\g<1>({lo}, {hi})', calibrated, flags=re.M)
    nominal = dict(coverage=0.8, bands={name: (0.1, 0.9) for name in names})
    for text, want in ((source, nominal), (calibrated, CALIBRATED)):
        d = tempfile.mkdtemp(prefix='band-quals-')
        open(os.path.join(d, 'chance.py'), 'w', encoding='utf-8').write(text)
        p = subprocess.run([sys.executable, '-B', '-c', BAND_PROBE, d, HERE, json.dumps(WORK_DRAWS)], capture_output=True, text=True, cwd=d, timeout=600)
        shutil.rmtree(d)
        assert p.returncode == 0, p.stderr[-3000:]
        got = json.loads(p.stdout)
        bands = want['bands']
        assert got['COVERAGE'] == want['coverage'] and {k: tuple(v) for k, v in got['BANDS'].items()} == bands, (got['COVERAGE'], got['BANDS'])
        a = 4 * 3600
        assert close(got['gott'], [a / 3600] + [a * q / (1 - q) / 3600 for q in bands['gott']]), (want, got['gott'])
        for name, asks in got['asked'].items():
            assert asks and all(tuple(levels) == bands[name] for levels in asks), (name, asks, bands[name])
        assert len(got['asked']['stages']) == 2, got['asked']['stages']          # its one later stage, then the total
        d0 = WORK_DRAWS
        brute = brute_work(.3, d0['total'], d0['done'], d0['rate'], d0['weight'], bands['work'])
        assert close(got['work']['total'], brute['total'], 1e-9) and close(got['work']['to_go'], brute['to_go'], 1e-9), (want, got['work'], brute)
        assert got['coverage'] == want['coverage'] and got['total'] == got['forecast'], (want, got['coverage'], got['total'], got['forecast'])
        assert close(got['scatter'], got['quantiled']), (want, got['scatter'], got['quantiled'])
        normal = statistics.NormalDist()
        assert close(got['ZS'], [normal.inv_cdf(0.05), normal.inv_cdf(0.95)]), (want, got['ZS'])


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0 = time.time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
