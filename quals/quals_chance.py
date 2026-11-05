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
