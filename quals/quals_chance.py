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


# A made-up campaign's journal, its times in epoch seconds: launched at 1000 with two cells, 528:12 and 720:13; at
# 528:12, plain seed 2 ended at 1500 after 200 CPU s, probe seed 1 at 2800 (its tracker's rusage 900 s, its bookkeeping
# in it), plain seed 3 at 2900 after 180 s, plain seed 4 cancelled at 3000 after 50 s, probe seed 5 cancelled at 3100
# with no files at all; and at 720:13 a plain seed of 999 s.
JOURNAL = [dict(time=1000.0, event='start'), seed(1500.0, 'plain', 2, 200.0), seed(2800.0, 'probe', 1, 900.0),
           seed(2900.0, 'plain', 3, 180.0), seed(3000.0, 'plain', 4, 50.0, cancelled=True),
           seed(3100.0, 'probe', 5, 20.0, cancelled=True), seed(3200.0, 'plain', 6, 999.0, cell='720:13')]
# probe seed 1's rounds, (X, cpu): 3e-4, 1e-4 and 5e-5 of exposure in 100 CPU s each
ROUNDS = ((3e-4, 100.0), (1e-4, 100.0), (5e-5, 100.0))


def probe_lines(rounds, done=True):
    """A finished probe seed's PREFIX.jsonl lines, as probe_seed.py writes them: its header, its rounds, its done line."""
    head = dict(kind='header', n=528, m=12, f=170, seed=1, beam=20000, cpu=4.8)
    body = [dict(kind='round', round=i + 1, generated=20000, fresh=100, enumerated=100, cpu=c, probe_cpu=2 * c, X=x, Qbest=84.0)
            for i, (x, c) in enumerate(rounds)]
    end = dict(kind='done', rounds=len(rounds), cpu=sum(c for _, c in rounds), probe_cpu=500.0, wall=1700.0, witnesses=0)
    return [head] + body + [end] * done


def campaign(journal=JOURNAL, probes=None, priors=None, plan_dir='camp', cells=('528:12', '720:13')):
    """A temporary directory as the repository's root, with a campaign in camp/: its plan.json (dir plan_dir, the cells),
    its journal.jsonl (journal), its probe seeds' PREFIX.jsonl files (probes: {prefix: lines}; by default probe seed 1's
    of ROUNDS) and its chance.json (priors: {target: prior}; by default PRIOR at 528:12 and 720:13)."""
    d = tempfile.mkdtemp(prefix='chance-quals-')
    camp = os.path.join(d, 'camp')
    os.makedirs(os.path.join(camp, 'seeds'))
    plan = dict(name='q', dir=plan_dir, cells=[dict(n=int(c.split(':')[0]), m=int(c.split(':')[1]), fs=[170]) for c in cells])
    json.dump(plan, open(os.path.join(camp, 'plan.json'), 'w'))
    open(os.path.join(camp, 'journal.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in journal))
    probes = {os.path.join('camp', 'seeds', '528_12_s1'): probe_lines(ROUNDS)} if probes is None else probes
    for prefix, lines in probes.items():
        open(os.path.join(d, prefix + '.jsonl'), 'w').write(''.join(json.dumps(x) + '\n' for x in lines))
    priors = {'528:12': PRIOR, '720:13': PRIOR} if priors is None else priors
    json.dump(dict(targets=priors, sources={}), open(os.path.join(camp, 'chance.json'), 'w'))
    return d


def expected(cpu_seconds, recent, span, prior=PRIOR, rounds=ROUNDS):
    """What chance.of gives a live target whose seeds' search CPU is cpu_seconds in all and recent in the last span
    seconds, with probe seed 1's rounds: hours its cpu_hours, rate its rounds' exposure per CPU-hour, cores recent per
    span, and the chance at each hour of chance.HOURS, by chance.within (whose own quals are below)."""
    rate = sum(x for x, _ in rounds) / (sum(c for _, c in rounds) / 3600)
    hours, cores = cpu_seconds / 3600, recent / span
    return dict(cpu_hours=hours, rate=rate, cores=cores, hours=list(chance.HOURS),
                p=chance.within(prior['p_exists'], prior['mean'], prior['sd'], rate * hours, [rate * cores * t for t in chance.HOURS]))


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
    # cancelled ones too, and probe seed 1's rounds': 200 + 300 + 180 + 50 s), 720:13's left out; its cores the search
    # CPU of the seeds that ended in the last hour (after 1600: 300 + 180 + 50 s) per second of it; hours chance.HOURS;
    # and p the chance within each, by chance.within at exposure spent rate x CPU-hours and ahead rate x cores x t.
    d = campaign()
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        assert close(got, expected(730.0, 530.0, 3600.0)), got and {k: v for k, v in got.items() if k != 'p'}
    finally:
        shutil.rmtree(d)


def q_cores_count_from_the_campaign_s_latest_start():
    # Replicata: chance.of(root, 'camp', '528:12', now) for campaign() with JOURNAL's first two records alone (its start
    # at 1000 and plain seed 2's end at 1500 after 200 CPU s) at now 2000, 1000 s after the start; and for JOURNAL with
    # an end at 3500 (a SIGTERM), a second start at 4000 (the relaunch, which resumes the journal) and plain seed 8
    # ending at 4500 after 100 CPU s, at now 5000.
    # Expectata: cores the search CPU of the seeds ended since the latest start, over the seconds since it, when that is
    # less than an hour: 200 s over 1000 s, then 100 s over 1000 s; the CPU-hours every ended seed's, those before the
    # relaunch too (no probe seed has ended in the first: no rate and no chance yet).
    d = campaign(journal=JOURNAL[:2])
    try:
        got = chance.of(d, 'camp', '528:12', 2000.0)
        assert close(got, dict(cpu_hours=200.0 / 3600, rate=None, cores=0.2, hours=list(chance.HOURS), p=[])), got
    finally:
        shutil.rmtree(d)
    journal = JOURNAL + [dict(time=3500.0, event='end', reason='signal'), dict(time=4000.0, event='start', resumed=True),
                         seed(4500.0, 'plain', 8, 100.0)]
    d = campaign(journal=journal)
    try:
        assert close(chance.of(d, 'camp', '528:12', 5000.0), expected(830.0, 100.0, 1000.0))
    finally:
        shutil.rmtree(d)


def q_of_is_none_unless_the_target_is_live():
    # Replicata: chance.of(root, 'camp', target, 5200) for campaign(): at 864:13, which its plan does not hold; at 720:13
    # after a witness and its stop (arm_stop, reason witness); after the witness alone (journaled just before the stop);
    # after a checkpoint's stop; at 528:12 after the campaign's end (reason signal); and after that end and a relaunch.
    # Expectata (the coordinator, 2026-11-03: "for each live witness campaign target"): None, each, but after the
    # relaunch, when 528:12 is live again and its chance as before.
    witness = dict(time=3300.0, event='witness', cell='720:13', k=6, f=170, code='AB', order=13, plus=360)
    stop = lambda reason: dict(time=3301.0, event='arm_stop', cell='720:13', reason=reason)
    end, again = dict(time=3500.0, event='end', reason='signal'), dict(time=4000.0, event='start', resumed=True)
    for journal, target in ((JOURNAL, '864:13'), (JOURNAL + [witness, stop('witness')], '720:13'), (JOURNAL + [witness], '720:13'),
                            (JOURNAL + [stop('checkpoint')], '720:13'), (JOURNAL + [end], '528:12')):
        d = campaign(journal=journal)
        try:
            assert chance.of(d, 'camp', target, 5200.0) is None, (target, journal[-1])
        finally:
            shutil.rmtree(d)
    d = campaign(journal=JOURNAL + [end, again])
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        assert close(got, expected(730.0, 0.0, 1200.0)), got and {k: v for k, v in got.items() if k != 'p'}
    finally:
        shutil.rmtree(d)


def q_without_a_finished_probe_seed_there_is_no_chance_yet():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() with JOURNAL less probe seed 1's end (its probe
    # still running, or not yet begun), and no probe files.
    # Expectata: no rate (None) and no chance (p empty), as nothing has measured the target's exposure yet; its
    # CPU-hours and cores as before, less the probe's (430 s in all, 230 s in the last hour); hours chance.HOURS.
    d = campaign(journal=[r for r in JOURNAL if not (r['event'] == 'seed_end' and r['k'] == 1)], probes={})
    try:
        got = chance.of(d, 'camp', '528:12', 5200.0)
        assert close(got, dict(cpu_hours=430.0 / 3600, rate=None, cores=230.0 / 3600, hours=list(chance.HOURS), p=[])), got
    finally:
        shutil.rmtree(d)


def q_of_refuses_malformed_campaigns():
    # Replicata: chance.of(root, 'camp', '528:12', 5200) for campaign() with: probe seed 1's file without its done line
    # (a finished probe seed has one); its done line counting 2 rounds of 3; its rounds numbered 1, 3, 2; its header
    # missing; a seed_end of a kind other than plain or probe; the plan's dir other than camp (its seeds' prefixes are
    # paths from the root only if it names camp); no prior for 528:12; a prior with P(exists) 1.5, with sd 0, with an
    # extra field, without its sd; and at now 1000, the campaign's start (no span to measure cores over).
    # Expectata: AssertionError, each.
    prefix = os.path.join('camp', 'seeds', '528_12_s1')
    lines = probe_lines(ROUNDS)
    swapped = lines[:2] + [lines[3], lines[2]] + lines[4:]
    bad = [dict(probes={prefix: lines[:-1]}), dict(probes={prefix: lines[:-1] + [dict(lines[-1], rounds=2)]}),
           dict(probes={prefix: swapped}), dict(probes={prefix: lines[1:]}),
           dict(journal=JOURNAL + [dict(seed(3300.0, 'plain', 9, 1.0), kind='odd')]), dict(plan_dir='elsewhere'),
           dict(priors={'720:13': PRIOR}), dict(priors={'528:12': dict(PRIOR, p_exists=1.5)}),
           dict(priors={'528:12': dict(PRIOR, sd=0.0)}), dict(priors={'528:12': dict(PRIOR, extra=1)}),
           dict(priors={'528:12': {k: v for k, v in PRIOR.items() if k != 'sd'}})]
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
