#!/usr/bin/env python3
"""The chance that a witness campaign finds a witness within the next t hours (README [SER], 2026-11-03: "Could the
searches show a live estimate of the probability of finding a bipartition?"; dreeves: "sure, build [SER]"): the
search-allocation bandit's model (scratch/bandit-20261103/bandit.py, as scratch/bandit-20261103b/rerun.py's
exists_posterior and witness_index_p use it), fed by a campaign's own files.  progress.py puts it in its data file for
each live target of a campaign it names (its CAMPAIGNS), and the section "Search progress" draws it.  Quals:
python3 -B quals/quals_chance.py

Vocabulary, each term defined once here:
  campaign    a witness search run by scratch/beam-campaign-20261103/campaign.py, whose docstring defines its plan, cell,
              seed, kind (plain or probe) and journal: its directory, a path from the repository's root, holds its
              plan.json, its journal.jsonl and its priors (PRIORS); its journal names its seeds' files (prefix) by paths
              from the root.
  live        of a campaign's cell, a target N:M: in its plan while it runs (its journal's latest start or end record a
              start), with no witness found at it and no stop of it (no witness or arm_stop record of the cell).
  theta       the bandit's unknown calibration of its model: witnesses come at theta per unit of exposure.
  exposure    the bandit's model count of witnesses in the cosets a search enumerates, at theta = 1
              (scratch/bandit-20261103/probe.py's vocabulary).
  search CPU  a seed's CPU seconds of search: a plain seed's cpu (its tracker's rusage, its setup in it), a finished
              probe seed's rounds' cpu (its setup and its own bookkeeping left out); a cancelled probe seed's none, its
              files perhaps partial or never written, as the campaign's checkpoint.py leaves it out.
  rate (r)    a target's exposure per CPU-hour of search: its finished probe seeds' rounds' summed X (exposure) over their
              summed cpu (probe_seed.py's PREFIX.jsonl), the coordinator's "ΣX over Σcpu"; none before a probe seed of
              the target has finished.
  cpu_hours (H)  the search CPU-hours of the target's ended seeds: the campaign has found no witness in them.
  cores (c)   the target's recent search CPU-hours per wall-hour: the search CPU of its seeds that ended in the last
              WINDOW seconds, or since the campaign's latest start if that is later, over that span.
  prior       of a target, in its campaign's PRIORS: with probability 1 - p_exists no (-1)^m-symmetric sequence exists
              at the cell and theta = 0; otherwise log2 theta is normal with mean and sd.
  chance      of a live target within t hours: P(a witness within the next t hours | none in H CPU-hours) under the
              bandit's model, witnesses a Poisson process at theta r per CPU-hour: E[1 - exp(-theta r c t)] over the
              posterior, the prior weighted by exp(-theta r H), which also updates P(exists) (within).
"""
import sys
sys.dont_write_bytecode = True
import os, json, math
import numpy as np

HOURS = tuple(k / 4 for k in range(4 * 72 + 1))   # the chance's t: every quarter hour from 0 to 72 (the coordinator,
                                                  # 2026-11-03: "for t from 0 to 72")
WINDOW = 3600.0                  # seconds: cores' span, "the campaign's recent CPU-hours per wall-hour"
SPAN, STEP = 10.0, 0.01          # within's grid of log2 theta: mean +- SPAN sd, STEP bits apart (the trapezoid rule on a
                                 # smooth integrand; the prior's mass beyond 10 sd is about 1e-23)
PRIORS = 'chance.json'           # in a campaign's directory: {targets: {N:M: {p_exists, mean, sd}}, sources: {...}}


def within(p, mean, sd, spent, aheads):
    """The chance of a witness within each exposure of aheads, given none in the exposure spent, the prior P(exists)
    p and log2 theta ~ N(mean, sd^2) if it exists: p E[exp(-theta spent) (1 - exp(-theta b))] / (p E[exp(-theta spent)]
    + 1 - p) for each b, E over that normal, as a list.  The bandit's P(exists | data) times its p_success over its
    posterior given existence (rerun.witness_index_p), on a grid of its own."""
    # TODO: error copy; says within's inputs are out of range, quoting them
    assert (0 <= p <= 1 and 0 < sd < math.inf and math.isfinite(mean) and 0 <= spent < math.inf
            and all(0 <= b < math.inf for b in aheads)), f'Claude: "within({p}, {mean}, {sd}, {spent}, ...) is out of range"'
    z = np.arange(mean - SPAN * sd, mean + SPAN * sd + STEP / 2, STEP)
    w = np.exp(-0.5 * ((z - mean) / sd) ** 2)
    theta = np.exp2(z)
    kept = w / w.sum() * np.exp(-theta * spent)       # the prior's weight times P(no witness in spent | theta)
    return [float(p * (kept @ -np.expm1(-theta * b)) / (p * kept.sum() + (1 - p))) for b in aheads]   # (1 - p) first: 1 - p = 0 exactly
                                                                                                        # when p = 1, not after rounding


def lines(path):
    """The file's complete lines, each parsed as JSON: a last line without its newline is still being written, so it
    is left out (as progress.complete_lines)."""
    return [json.loads(line) for line in open(path, encoding='utf-8').read().split('\n')[:-1]]


def rounds(path):
    """(X, cpu) of a finished probe seed, from its PREFIX.jsonl at path: its rounds' summed exposure and summed cpu
    seconds.  Asserted: a header, rounds numbered from 1, and a done line that counts them."""
    ls = lines(path)
    body = ls[1:-1]
    # TODO: error copy; says a finished probe seed's journal is not a header, its rounds in order and a done line counting them, naming it
    assert ([x['kind'] for x in ls] == ['header'] + ['round'] * len(body) + ['done'] and ls[-1]['rounds'] == len(body)
            and [x['round'] for x in body] == list(range(1, len(body) + 1))), f'Claude: "{path} is no finished probe seed\'s"'
    return sum(x['X'] for x in body), sum(x['cpu'] for x in body)


def prior(root, campaign, target):
    """The target's prior, {p_exists, mean, sd}, from the campaign's PRIORS (asserted there and in range)."""
    targets = json.load(open(os.path.join(root, campaign, PRIORS), encoding='utf-8'))['targets']
    # TODO: error copy; says the campaign's priors hold no prior for the target, or one of another form, naming both
    assert target in targets and set(targets[target]) == {'p_exists', 'mean', 'sd'}, f'Claude: "{campaign} has no prior for {target}"'
    x = targets[target]
    # TODO: error copy; says a prior is out of range, quoting it
    assert 0 <= x['p_exists'] <= 1 and math.isfinite(x['mean']) and 0 < x['sd'] < math.inf, f'Claude: "the prior {x} is out of range"'
    return x


def live(plan, records):
    """The live cells (see the vocabulary) of the campaign with this plan and these journal records."""
    running = [r['event'] for r in records if r['event'] in ('start', 'end')][-1] == 'start'
    stopped = {r['cell'] for r in records if r['event'] in ('witness', 'arm_stop')}
    return [f'{c["n"]}:{c["m"]}' for c in plan['cells'] if running and f'{c["n"]}:{c["m"]}' not in stopped]


def measure(root, records, x, target, now):
    """The chance of the target, whose prior is x, from its campaign's journal records at time now (epoch seconds):
    {cpu_hours, rate, cores, hours, p}: H, r and c (see the vocabulary), HOURS, and the chance within each (within, at
    exposure spent r H and ahead r c t); with no rate yet, rate None and p empty."""
    start = max(r['time'] for r in records if r['event'] == 'start')
    # TODO: error copy; says the time given is not after the campaign's latest start, so there is no span to measure its pace over
    assert now > start, f'Claude: "{now} is not after the campaign\'s start, {start}"'
    ends = [r for r in records if r['event'] == 'seed_end' and r['cell'] == target]
    # TODO: error copy; says the target's seeds are not each of kind plain or probe, ended once, a plain one with its CPU seconds
    assert ({e['kind'] for e in ends} <= {'plain', 'probe'} and len({e['k'] for e in ends}) == len(ends)
            and all(type(e['cpu']) in (int, float) and 0 <= e['cpu'] < math.inf for e in ends if e['kind'] == 'plain')), \
        f'Claude: "the seeds of {target} are of kinds {sorted({e["kind"] for e in ends})}, or one ended twice or without its CPU"'
    probes = {e['k']: rounds(os.path.join(root, e['prefix'] + '.jsonl')) for e in ends if e['kind'] == 'probe' and not e['cancelled']}
    cpu = {e['k']: e['cpu'] for e in ends if e['kind'] == 'plain'} | {k: c for k, (_, c) in probes.items()}   # search CPU
    t0 = max(now - WINDOW, start)
    measured = dict(cpu_hours=sum(cpu.values()) / 3600, hours=list(HOURS),
                    cores=sum(cpu[e['k']] for e in ends if e['k'] in cpu and e['time'] > t0) / (now - t0))
    if not probes: return dict(measured, rate=None, p=[])         # no probe seed has finished: no rate measured yet
    rate = sum(X for X, _ in probes.values()) / (sum(c for _, c in probes.values()) / 3600)
    return dict(measured, rate=rate, p=within(x['p_exists'], x['mean'], x['sd'], rate * measured['cpu_hours'],
                                              [rate * measured['cores'] * t for t in HOURS]))


def of(root, campaign, target, now):
    """The chance (measure) of the target N:M at time now (epoch seconds), from the campaign in the directory campaign
    (a path from root, the repository's root, where the campaign runs), while the target is live there; else None.  Its
    plan must say it is in that directory (asserted: its seeds' prefixes are paths from root)."""
    plan = json.load(open(os.path.join(root, campaign, 'plan.json'), encoding='utf-8'))
    # TODO: error copy; says the campaign's plan names another directory than the one it is in, naming both
    assert plan['dir'] == campaign, f'Claude: "{campaign}/plan.json says it is in {plan["dir"]}"'
    records = lines(os.path.join(root, campaign, 'journal.jsonl'))
    # TODO: error copy; says the campaign's journal does not begin with its start record, naming the campaign
    assert records and records[0]['event'] == 'start', f'Claude: "{campaign}/journal.jsonl does not begin with its start"'
    return measure(root, records, prior(root, campaign, target), target, now) if target in live(plan, records) else None


if __name__ == '__main__':
    # TODO: error copy; says this module holds functions, which progress.py calls
    raise SystemExit('Claude: "chance.py holds functions; progress.py uses them"')
