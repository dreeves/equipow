#!/usr/bin/env python3
"""The chance that a witness campaign finds a witness within the next t hours (README [SER], 2026-11-03: "Could the
searches show a live estimate of the probability of finding a bipartition?"; dreeves: "sure, build [SER]"): the
search-allocation bandit's model (scratch/bandit-20261103/bandit.py, as scratch/bandit-20261103b/rerun.py's
exists_posterior and witness_index_p use it), fed by a campaign's own files.  progress.py puts it in its data file for
each target of a campaign it names (its CAMPAIGNS), live or not, and the section "Search progress" draws it.  Quals:
python3 -B quals/quals_chance.py

Vocabulary, each term defined once here:
  campaign    a witness search run by scratch/beam-campaign-20261103/campaign.py, whose docstring defines its plan, cell,
              seed, kind (plain or probe) and journal: its directory, a path from the repository's root, holds its live
              plan, its archived plans and its priors (PRIORS); a journal names its seeds' files (prefix) by paths from
              the root, below the campaign's directory.
  plan        one launch configuration of a campaign: its plan.json and its journal.jsonl, the live plan's in the
              campaign's directory; each earlier plan archived, the K-th (K = 1, 2, ... without a gap) moved whole into
              planK below that directory (plan.json, journal and seeds' files) when the next one started, its journal
              naming its seeds' files where they were before the move.
  live        of a campaign's cell, a target N:M: in its live plan while it runs (that plan's journal's latest start or end
              record a start), with no witness found at it and no stop of it (no witness or arm_stop record of the cell).
  theta       the bandit's unknown calibration of its model: witnesses come at theta per unit of exposure.
  exposure    the bandit's model count of witnesses in the cosets a search enumerates, at theta = 1
              (scratch/bandit-20261103/probe.py's vocabulary).
  search CPU  a seed's CPU seconds of search: a plain seed's cpu (its tracker's rusage, its setup in it), a finished
              probe seed's rounds' cpu (its setup and its own bookkeeping left out); a cancelled probe seed's none, its
              files perhaps partial or never written, as the campaign's checkpoint.py leaves it out.
  rate (r)    of a plan at a target, its exposure per CPU-hour of search: its finished probe seeds' rounds' summed X
              (exposure) over their summed cpu (probe_seed.py's PREFIX.jsonl), the coordinator's "ΣX over Σcpu"; none
              before a probe seed of the target has finished in the plan.  Plans' pins differ, and with them their rates.
  cpu_hours (H)  the search CPU-hours of the target's ended seeds in all of its campaign's plans: the campaign has found
              no witness in them (README [CON], 2026-11-03: "conditional on not having found anything so far").
  spent       the exposure of those hours: each plan's own rate times its CPU-hours at the target, summed over the plans.
  life        of an ended seed: the seconds from its seed_start record to its seed_end record.
  running     of a plan at a target: its seeds there with a seed_start record and no seed_end record yet; none at an
              end record of the plan's journal (the campaign's driver ends its seeds before it stops).
  cores (c)   the target's search CPU-hours per wall-hour ahead: the live plan's seeds running there times the search
              CPU per second of life of the target's seeds, in any of the campaign's plans, that ended in the WINDOW
              seconds up to the latest of their ends (their search CPU summed over their lives summed); none before the
              live plan's first probe seed has finished, when no chance is computed.  Counted from the latest start
              instead, it began near 0 with each plan or relaunch, before its first seeds ended (README [CON],
              2026-11-03); counted as the search CPU of the seeds that ended in the last WINDOW seconds per second of
              it, it was 0 in the last 45 minutes of each of plan 11's 107-minute batches, whose seeds start and end
              together, and 1.8 times too high in the rest (2026-11-04).
  prior       of a target, in its campaign's PRIORS: with probability 1 - p_exists no (-1)^m-symmetric sequence exists
              at the cell and theta = 0; otherwise log2 theta is normal with mean and sd.
  chance      of a target within t hours: P(a witness within the next t hours | none in H CPU-hours) under the
              bandit's model, witnesses a Poisson process at theta r per CPU-hour, r the live plan's: E[1 - exp(-theta r
              c t)] over the posterior, the prior weighted by exp(-theta spent), which also updates P(exists) (within).
  as of t     of a campaign, as it stood just before time t: its plans begun by then, each with its records from before
              then; a quantity as of t is computed from those alone, with t as now.
  since       of a target, the first start of a plan of its campaign holding it: its history's origin.
  history     of a target, its chance within 6 h and within 24 h as of each time, every QUARTER seconds from its
              since, and as of now, at the times it was live with a rate (so it ends where its search stopped)
              (README [CON], 2026-11-03; dreeves: "the curve should fall in light of the conditional probability but it
              should remain historically accurate"): each point from the records before its time alone, so later
              records never change it.
  exhaustive  of a search: one that covers every case, so that it finds a witness exactly when one exists (288:10's
              form trees, searches/formtree); with no estimate of its own its remaining time follows Lindy's rule, which
              gives its odds and chance (lindy_shown): P(exists) its prior throughout, as nothing measures the fraction
              covered, and no CPU-hours, rate or cores, which that model does not use.
  odds        of a modeled search, what its first two graphs draw (dreeves, 2026-11-04: "1. probability a partition
              exists ... 2. probability of finding a partition by time t *conditional on a partition existing* and also
              conditional on not having found one so far"): its basis (campaign or lindy), ahead (AHEAD), exists, [t,
              P(exists)] at its history's times and at now, and curves, [t, P(a witness within each hour of AHEAD |
              one exists)] at every fourth of those times back from the last, within BACK hours of it, and at now; now's
              only once a rate is measured there and when the last point is not now's (its search stopped).  Its third
              graph is the history, P(exists) times P(found within 24 h | exists) as of each time (dreeves, 2026-11-04:
              "can we get that 3rd chart as well, consistently, after the P(exists) and P(find|exists) charts?").
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, math
from functools import lru_cache
import numpy as np

HOURS = tuple(k / 4 for k in range(4 * 72 + 1))   # the chance's t: every quarter hour from 0 to 72 (the coordinator,
                                                  # 2026-11-03: "for t from 0 to 72")
WINDOW = 3600.0                  # seconds: the span of the latest seeds' ends whose CPU per second of life cores takes
SPAN, STEP = 10.0, 0.01          # within's grid of log2 theta: mean +- SPAN sd, STEP bits apart (the trapezoid rule on a
                                 # smooth integrand; the prior's mass beyond 10 sd is about 1e-23)
PRIORS = 'chance.json'           # in a campaign's directory: {targets: {N:M: {p_exists, mean, sd}}, sources: {...}}
ARCHIVED = re.compile(r'plan([1-9][0-9]*)')     # an archived plan's directory below its campaign's: planK, K from 1
QUARTER = 900.0                  # seconds between a history's points
AHEAD = tuple(range(73))         # hours ahead of each of the odds' curves: every hour from 0 to 72
BACK = 24                        # hours back from the latest curve that the odds keep curves for, one an hour


def grid(mean, sd, spent):
    """within's grid of theta and, at each point, the prior's weight times P(no witness in the exposure spent | theta),
    given log2 theta ~ N(mean, sd^2)."""
    z = np.arange(mean - SPAN * sd, mean + SPAN * sd + STEP / 2, STEP)
    w = np.exp(-0.5 * ((z - mean) / sd) ** 2)
    theta = np.exp2(z)
    return theta, w / w.sum() * np.exp(-theta * spent)


def exists(p_exists, mean, sd, spent):
    """P(a witness exists | none in the exposure spent), the prior P(exists) p_exists and log2 theta ~ N(mean, sd^2) if
    it exists: p_exists E[exp(-theta spent)] / (p_exists E[exp(-theta spent)] + 1 - p_exists); the odds' first factor."""
    # TODO: error copy; says exists's inputs are out of range, quoting them
    assert 0 <= p_exists <= 1 and 0 < sd < math.inf and math.isfinite(mean) and 0 <= spent < math.inf, f'Claude: "exists({p_exists}, {mean}, {sd}, {spent}) is out of range"'
    _, kept = grid(mean, sd, spent)
    return float(p_exists * kept.sum() / (p_exists * kept.sum() + (1 - p_exists)))


def found(mean, sd, spent, aheads):
    """P(a witness within each exposure b of aheads | one exists and none in the exposure spent), log2 theta ~ N(mean,
    sd^2) a priori: E[exp(-theta spent) (1 - exp(-theta b))] / E[exp(-theta spent)], as a list; the odds' second factor,
    so that exists times found is within."""
    # TODO: error copy; says found's inputs are out of range, quoting them
    assert (0 < sd < math.inf and math.isfinite(mean) and 0 <= spent < math.inf
            and all(0 <= b < math.inf for b in aheads)), f'Claude: "found({mean}, {sd}, {spent}, ...) is out of range"'
    theta, kept = grid(mean, sd, spent)
    # TODO: error copy; says the exposure spent leaves no weight on the grid, so the chance given existence is undefined, quoting it
    assert kept.sum() > 0, f'Claude: "no weight left after exposure {spent}"'
    return [float((kept @ -np.expm1(-theta * b)) / kept.sum()) for b in aheads]


def lindy_found(tau, aheads):
    """P(found within each s hours of aheads | a witness exists and none found yet) for an exhaustive search (one that
    finds a witness exactly when one exists) with no estimate of its own, aged tau hours: its remaining time R by Gott's
    rule (P(R > x) = tau / (tau + x)), the witness anywhere in the work left alike, so E[min(1, s / R)] =
    (s / tau) log(1 + tau / s), and 0 with nothing ahead; as a list."""
    # TODO: error copy; says lindy_found's inputs are out of range, quoting them
    assert 0 < tau < math.inf and all(0 <= s < math.inf for s in aheads), f'Claude: "lindy_found({tau}, ...) is out of range"'
    return [s / tau * math.log1p(tau / s) if s else 0.0 for s in aheads]


def within(p_exists, mean, sd, spent, aheads):
    """The chance of a witness within each exposure of aheads, given none in the exposure spent, the prior P(exists)
    p_exists and log2 theta ~ N(mean, sd^2) if it exists: p_exists E[exp(-theta spent) (1 - exp(-theta b))] /
    (p_exists E[exp(-theta spent)] + 1 - p_exists) for each b, E over that normal, as a list.  The bandit's
    P(exists | data) times its p_success over its posterior given existence (rerun.witness_index_p), on a grid of its
    own."""
    # TODO: error copy; says within's inputs are out of range, quoting them
    assert (0 <= p_exists <= 1 and 0 < sd < math.inf and math.isfinite(mean) and 0 <= spent < math.inf
            and all(0 <= b < math.inf for b in aheads)), f'Claude: "within({p_exists}, {mean}, {sd}, {spent}, ...) is out of range"'
    theta, kept = grid(mean, sd, spent)               # the prior's weight times P(no witness in spent | theta)
    # (1 - p_exists) added as a whole: 0 exactly when p_exists is 1, where adding 1 and then subtracting p_exists would
    # leave a rounding error as large as the rest of the sum (4e-9 of the chance, 2026-11-03)
    return [float(p_exists * (kept @ -np.expm1(-theta * b)) / (p_exists * kept.sum() + (1 - p_exists))) for b in aheads]


def _work_cdf(rest, absent, present, ahead):
    """Completion CDF at ahead hours: absent masses at rest, present masses uniform on [0, rest]."""
    h = np.asarray(ahead)[:, None]
    return (h >= rest) @ absent + (np.minimum(h, rest) / rest) @ present


def _work_quantiles(rest, absent, present):
    """The 5%, 50%, 95% completion times in hours, inverting its linear pieces and atoms at rest."""
    order = np.argsort(rest)
    t, a, b = rest[order], absent[order], present[order]
    slope = np.cumsum((b / t)[::-1])[::-1]
    before = (np.cumsum(a) - a) + (np.cumsum(b) - b) + t * slope
    after = before + a
    q = np.array([0.05, 0.5, 0.95])
    k = np.searchsorted(after, q, side='left')
    delta = np.divide(np.maximum(before[k] - q, 0), slope[k], out=np.zeros(3), where=slope[k] > 0)
    return t[k] - delta


def work(p_exists, total, done, rate, weight):
    """A work model's current chance and completion ETA, conditional on no witness and a still-open search.

    total, rate and weight are matching one-dimensional draws: positive total work, positive work per wall-hour,
    and nonnegative weights summing to one. Paired work/rate draws may be dependent. done is checked work in the same
    units, excluding repeated work. The structural draws precede the no-witness update; draws at or below done are
    conditioned out, not clamped. No surviving support is a failed model, not a completed proof.

    The existence prior is p_exists. Work has the same structural distribution under existence and nonexistence;
    if a witness exists, its first discovery is assumed uniform in [0,total]. At work W>done, no-find survival is
    q=(W-done)/W. For normalized structural weights a, A=sum(a*q) and Z=1-p_exists+p_exists*A. The posterior existence
    probability is p_exists*A/Z. A further x work finds it with conditional probability sum(a*min(x,W-done)/W)/A.
    These are conditional modeling assumptions, not empirically calibrated existence probabilities.

    Returns measure's fields, with CPU-hours/rate/cores null because those fields denote campaign exposure units;
    p is the unconditional find CDF on HOURS, found the existence-conditional CDF on AHEAD. Also completion, the CDF
    on HOURS of a witness or accepted exhaustion, and to_go, its median/5%/95% in seconds. Completion mixes a mass
    at (W-done)/rate when absent with a uniform time on that interval when present, using their joint posterior
    weights. At a zero existence prior, found remains the model's counterfactual conditional-on-existence curve.
    No terminal verdict is inferred here; a caller supplies actual proof/witness status separately.
    """
    assert type(p_exists) in (int, float) and 0 <= p_exists <= 1
    assert type(done) in (int, float) and math.isfinite(done) and done >= 0
    total, rate, weight = (np.asarray(x) for x in (total, rate, weight))
    assert all(x.ndim == 1 and x.dtype.kind in 'iuf' for x in (total, rate, weight))
    assert len(total) == len(rate) == len(weight) > 0
    total, rate, weight = (x.astype(float) for x in (total, rate, weight))
    assert all(np.all(np.isfinite(x)) for x in (total, rate, weight))
    assert np.all(total > 0) and np.all(rate > 0) and np.all(weight >= 0)
    assert math.isclose(float(weight.sum()), 1.0, rel_tol=1e-12, abs_tol=0)
    keep = (total > done) & (weight > 0)
    assert np.any(keep)
    total, rate, weight = total[keep], rate[keep], weight[keep]
    weight = weight / weight.sum()
    left = total - done
    rest, q = left / rate, left / total
    assert np.all(np.isfinite(rest)) and np.all(rest > 0)
    A = float(weight @ q)
    Z = 1 - p_exists + p_exists * A
    absent, present = (1 - p_exists) * weight / Z, p_exists * weight * q / Z
    conditional = weight * q / A
    found = _work_cdf(rest, np.zeros(len(rest)), conditional, AHEAD)
    p = p_exists * A / Z
    within = p * _work_cdf(rest, np.zeros(len(rest)), conditional, HOURS)
    lo, median, hi = _work_quantiles(rest, absent, present) * 3600
    return dict(cpu_hours=None, rate=None, cores=None, hours=list(HOURS), exists=p, found=found.tolist(),
                p=within.tolist(), completion=_work_cdf(rest, absent, present, HOURS).tolist(),
                to_go=dict(median=float(median), lo=float(lo), hi=float(hi)))


def lines(path):
    """The file's complete lines, each parsed as JSON: a last line without its newline is still being written, so it
    is left out (as progress.complete_lines)."""
    return [json.loads(line) for line in open(path, encoding='utf-8').read().split('\n')[:-1]]


def rounds(path):
    """(X, cpu) of a finished probe seed, from its PREFIX.jsonl at path: its rounds' summed exposure and summed cpu
    seconds.  Asserted: a header, rounds numbered from 1, and a done line that counts them.  Read once per size and
    modification time of the file (a history reads each probe seed's file at many times)."""
    st = os.stat(path)
    return read_rounds(path, st.st_size, st.st_mtime_ns)


@lru_cache(maxsize=None)
def read_rounds(path, size, mtime):
    """rounds' reading of the file at path, whose size and modification time are these."""
    ls = lines(path)
    body = ls[1:-1]
    # TODO: error copy; says a finished probe seed's journal is not a header, its rounds in order and a done line counting them, naming it
    assert ([x['kind'] for x in ls] == ['header'] + ['round'] * len(body) + ['done'] and ls[-1]['rounds'] == len(body)
            and [x['round'] for x in body] == list(range(1, len(body) + 1))), f'Claude: "{path} is no finished probe seed\'s"'
    return sum(x['X'] for x in body), sum(x['cpu'] for x in body)


def prior_of(root, campaign, target):
    """The target's prior, {p_exists, mean, sd}, from the campaign's PRIORS (asserted there and in range)."""
    targets = json.load(open(os.path.join(root, campaign, PRIORS), encoding='utf-8'))['targets']
    # TODO: error copy; says the campaign's priors hold no prior for the target, or one of another form, naming both
    assert target in targets and set(targets[target]) == {'p_exists', 'mean', 'sd'}, f'Claude: "{campaign} has no prior for {target}"'
    x = targets[target]
    # TODO: error copy; says a prior is out of range, quoting it
    assert 0 <= x['p_exists'] <= 1 and math.isfinite(x['mean']) and 0 < x['sd'] < math.inf, f'Claude: "the prior {x} is out of range"'
    return x


def cells(plan):
    """The plan's cells, as targets N:M."""
    return [f'{c["n"]}:{c["m"]}' for c in plan['cells']]


def live(plan, records):
    """The live cells (see the vocabulary) of the campaign whose live plan is this, with these journal records."""
    running = [r['event'] for r in records if r['event'] in ('start', 'end')][-1] == 'start'
    stopped = {r['cell'] for r in records if r['event'] in ('witness', 'arm_stop')}
    return [c for c in cells(plan) if running and c not in stopped]


def plans(root, campaign):
    """The campaign's plans (see the vocabulary), its archived ones in order and its live one last, as (home, plan,
    records): its directory (a path from root), its plan.json and its journal's records.  Asserted: the archived plans
    numbered from 1 without a gap, and each plan naming the campaign's directory (its seeds' prefixes are paths from
    root only if it does) and its journal beginning with its start record, its start and end records alternating in
    time order, and no seed running at an end record."""
    ks = sorted(int(m[1]) for m in map(ARCHIVED.fullmatch, os.listdir(os.path.join(root, campaign))) if m)
    # TODO: error copy; says the campaign's archived plans are not numbered 1, 2, ... without a gap, listing their numbers
    assert ks == list(range(1, len(ks) + 1)), f'Claude: "the archived plans of {campaign} are numbered {ks}"'
    out = []
    for home in [os.path.join(campaign, f'plan{k}') for k in ks] + [campaign]:
        plan = json.load(open(os.path.join(root, home, 'plan.json'), encoding='utf-8'))
        # TODO: error copy; says a plan of the campaign names another directory than the campaign's, naming both
        assert plan['dir'] == campaign, f'Claude: "{home}/plan.json says it is in {plan["dir"]}"'
        records = lines(os.path.join(root, home, 'journal.jsonl'))
        marks = [(r['event'], r['time']) for r in records if r['event'] in ('start', 'end')]
        idle = all({(x['cell'], x['k']) for x in records[:i] if x['event'] == 'seed_start'}
                   == {(x['cell'], x['k']) for x in records[:i] if x['event'] == 'seed_end'} for i, r in enumerate(records) if r['event'] == 'end')
        # TODO: error copy; says a plan's journal does not begin with its start record, its start and end records do not alternate in time order, or a seed was running at an end record, naming the plan's directory
        assert (records and records[0]['event'] == 'start' and [t for _, t in marks] == sorted(t for _, t in marks)
                and [e for e, _ in marks] == ['start', 'end'] * (len(marks) // 2) + ['start'] * (len(marks) % 2) and idle), \
            f'Claude: "{home}/journal.jsonl does not begin with its start, its starts and ends do not alternate in time order, or a seed ran at an end"'
        out.append((home, plan, records))
    return out


def searched(root, campaign, home, records, target):
    """The target's search in one of the campaign's plans, the one in home with these journal records: (starts, ends,
    cpu, probes), its seeds' seed_start times by seed, their seed_end records, their search CPU by seed and its finished
    probe seeds' rounds (X, cpu) by seed, each PREFIX.jsonl read below home where its journal names it below the
    campaign's directory (an archived plan's files moved with it).  Asserted: each seed started once and ended at most
    once, after its start, of kind plain or probe, a plain one with its CPU seconds, and each named below the
    campaign's directory."""
    begun = [r for r in records if r['event'] == 'seed_start' and r['cell'] == target]
    starts = {r['k']: r['time'] for r in begun}
    ends = [r for r in records if r['event'] == 'seed_end' and r['cell'] == target]
    # TODO: error copy; says the target's seeds are not each started once and ended at most once, after its start, of kind plain or probe, a plain one with its CPU seconds and each named below the campaign's directory
    assert (len(starts) == len(begun) and all(e['k'] in starts and starts[e['k']] < e['time'] for e in ends)
            and {e['kind'] for e in ends} <= {'plain', 'probe'} and len({e['k'] for e in ends}) == len(ends)
            and all(type(e['cpu']) in (int, float) and 0 <= e['cpu'] < math.inf for e in ends if e['kind'] == 'plain')
            and all(e['prefix'].startswith(campaign + os.sep) for e in ends)), \
        f'Claude: "the seeds of {target} in {home} are of kinds {sorted({e["kind"] for e in ends})}, or one started twice, ended twice, before its start or without its CPU, or outside {campaign}"'
    probes = {e['k']: rounds(os.path.join(root, home, os.path.relpath(e['prefix'], campaign) + '.jsonl'))
              for e in ends if e['kind'] == 'probe' and not e['cancelled']}
    cpu = {e['k']: e['cpu'] for e in ends if e['kind'] == 'plain'} | {k: c for k, (_, c) in probes.items()}   # search CPU
    return starts, ends, cpu, probes


def rate_of(probes):
    """A plan's rate at a target (see the vocabulary) from its finished probe seeds' rounds, {seed: (X, cpu)}."""
    return sum(X for X, _ in probes.values()) / (sum(c for _, c in probes.values()) / 3600)


def measure(root, campaign, plans, prior, target):
    """The chance of the target, whose prior is this, from its campaign's plans (as plans gives them, the live one last,
    or as they stood at a time, as_of): {cpu_hours, rate, cores, hours, p, exists, found}: H (every plan's), the live
    plan's r, c (see the vocabulary), HOURS, and the chance within each (within, at exposure spent and ahead r c t);
    P(exists) (exists, at spent) and the chance within each hour of AHEAD given existence (found, ahead r c t); with no
    rate yet in the live plan, rate, cores and exists None and p and found empty.  Asserted: every archived plan that
    searched the target has its rate there."""
    each = [searched(root, campaign, home, records, target) for home, _, records in plans]
    *earlier, (starts, ends, _, probes) = each
    unmeasured = [home for (home, _, _), (_, _, c, p) in zip(plans, earlier) if c and not p]
    # TODO: error copy; says these archived plans searched the target with no finished probe seed, so the exposure of their hours there is unknown, naming them
    assert not unmeasured, f'Claude: "{unmeasured} searched {target} without a finished probe seed: the exposure of those hours is unknown"'
    measured = dict(cpu_hours=sum(sum(c.values()) for _, _, c, _ in each) / 3600, hours=list(HOURS))
    if not probes: return dict(measured, rate=None, cores=None, p=[], exists=None, found=[])   # no probe seed has finished: no rate measured yet
    rate = rate_of(probes)
    spent = sum(rate_of(p) * (sum(c.values()) / 3600) for _, _, c, p in each if p)
    lives = [(e['time'], e['time'] - s[e['k']], c[e['k']]) for s, seeds, c, _ in each for e in seeds if e['k'] in c]
    last = max(t for t, _, _ in lives)                            # a finished probe seed's end among them
    recent = [(life, cpu) for t, life, cpu in lives if t > last - WINDOW]
    cores = len(set(starts) - {e['k'] for e in ends}) * sum(cpu for _, cpu in recent) / sum(life for life, _ in recent)
    return dict(measured, rate=rate, cores=cores, p=within(prior['p_exists'], prior['mean'], prior['sd'], spent,
                                                         [rate * cores * t for t in HOURS]),
                exists=exists(prior['p_exists'], prior['mean'], prior['sd'], spent),
                found=found(prior['mean'], prior['sd'], spent, [rate * cores * t for t in AHEAD]))


def as_of(plans, t):
    """The campaign's plans (as plans gives them) as of time t (see the vocabulary)."""
    return [(home, plan, [r for r in records if r['time'] < t]) for home, plan, records in plans if records[0]['time'] < t]


def began(plans, target):
    """The target's since (see the vocabulary), from its campaign's plans (as plans gives them)."""
    return min(records[0]['time'] for _, plan, records in plans if target in cells(plan))


def quarters(since, now):
    """A history's times (see the vocabulary) from since to now: every QUARTER seconds after since, then now."""
    return [since + QUARTER * k for k in range(1, math.ceil((now - since) / QUARTER))] + [now]


def stood(root, campaign, target, now):
    """The target's chance (measure) as of each of its history's times (see the vocabulary) at time now: [(t, chance),
    ...] in time order."""
    ps = plans(root, campaign)
    prior, first = prior_of(root, campaign, target), began(ps, target)
    then = [(t, as_of(ps, t)) for t in quarters(first, now)]
    chances = [(t, measure(root, campaign, p, prior, target)) for t, p in then if target in live(p[-1][1], p[-1][2])]
    return [(t, c) for t, c in chances if c['p']]


def rows(points):
    """A history's rows (see the vocabulary), [[t, p6, p24], ...], from stood points."""
    return [[t, c['p'][HOURS.index(6)], c['p'][HOURS.index(24)]] for t, c in points]


def history(root, campaign, target, now):
    """The target's history (see the vocabulary) at time now, from the campaign in the directory campaign (as of):
    [[t, p6, p24], ...] in time order."""
    return rows(stood(root, campaign, target, now))


def odds(points, now, c, basis):
    """The odds (see the vocabulary) on this basis from a history's points (stood's form) and the chance c as of now:
    exists at the points' times and at now, curves at every fourth point back from the last, within BACK hours of it,
    and at now; now's only once a rate is measured there (c's exists not None; until then, with no points either,
    neither) and when the last point is not now's.  (Until 2026-11-04 now's always, unmeasured or not, and none at all
    with no points: an IndexError.)"""
    picked = [(t, x) for t, x in points[::-1][::4] if t >= points[-1][0] - 3600 * BACK][::-1]
    # now's chance, unless unmeasured or already the last point (the target still live)
    tail = [] if c['exists'] is None or [t for t, _ in points[-1:]] == [now] else [(now, c)]
    return dict(basis=basis, ahead=list(AHEAD), exists=[[t, x['exists']] for t, x in points + tail],
                curves=[[t, x['found']] for t, x in picked + tail])


def lindy_shown(p_exists, t0, now):
    """What the page shows (shown's form) of an exhaustive search (see the vocabulary) begun at t0, with prior
    P(exists) p_exists and no estimate of its own, at time now: as of each of its history's times from t0, its chance
    in measure's form, P(exists) its prior and the chance within each of AHEAD hours given existence lindy_found on its
    age then, within each of HOURS their product, and no CPU-hours, rate or cores; with since t0, its history (rows) and
    its odds (odds) from those points, now's the last."""
    def at(t):                                         # its chance as of t, in measure's form
        tau = (t - t0) / 3600
        return dict(cpu_hours=None, rate=None, cores=None, hours=list(HOURS), exists=p_exists, found=lindy_found(tau, AHEAD),
                    p=[p_exists * x for x in lindy_found(tau, HOURS)])
    points = [(t, at(t)) for t in quarters(t0, now)]
    return dict(points[-1][1], since=t0, history=rows(points), odds=odds(points, now, points[-1][1], 'lindy'))


def shown(root, campaign, target, now):
    """What the page shows of the target at time now: its chance (of) with its since, its history (history) and its
    odds (odds) added, live or not: once its search stops, its history kept up to the stop, as the ETA chart keeps its
    records (dreeves, 2026-11-04: "shouldn't it stay there for posterity like the ETA graph does? is this another
    anti-magic violation?"; until then None once the target was not live, and so no chart)."""
    c, points = of(root, campaign, target, now), stood(root, campaign, target, now)
    return dict(c, since=began(plans(root, campaign), target), history=rows(points), odds=odds(points, now, c, 'campaign'))


def of(root, campaign, target, now):
    """The chance (measure) of the target N:M at time now (epoch seconds), from the campaign in the directory campaign
    (a path from root, the repository's root, where the campaign runs) as of now, live or not: its cores count the
    seeds running there, so once its search stops its chance within each t is 0 (2026-11-04; until then None for a
    target not live).  Asserted: the campaign began before now, and one of its plans holds the target."""
    ps = as_of(plans(root, campaign), now)
    # TODO: error copy; says the campaign had not begun before the time given, naming both
    assert ps, f'Claude: "{campaign} had not begun before {now}"'
    # TODO: error copy; says no plan of the campaign holds the target, naming both
    assert any(target in cells(plan) for _, plan, _ in ps), f'Claude: "no plan of {campaign} holds {target}"'
    return measure(root, campaign, ps, prior_of(root, campaign, target), target)


if __name__ == '__main__':
    # TODO: error copy; says this module holds functions, which progress.py calls
    raise SystemExit('Claude: "chance.py holds functions; progress.py uses them"')
