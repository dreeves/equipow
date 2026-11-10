#!/usr/bin/env python3
"""The chance that a bipartition exists, given none found so far (README [SER], 2026-11-03: "Could the searches show a
live estimate of the probability of finding a bipartition?"; dreeves: "sure, build [SER]"; since 2026-11-06 that alone,
dreeves: "everything here seems useless, kill it unless you have a good argument for salvaging anything. the up-to-date
probability that a bipartition exists is great."): of a witness campaign's target, the search-allocation bandit's model
(scratch/bandit-20261103/bandit.py, as scratch/bandit-20261103b/rerun.py's exists_posterior uses it), fed by the
campaign's own files; of a target an exhaustive search covers, its work model's (work, as formtree_eta.py uses it, with
the time and the work to exhaust the search's tree).  progress.py puts it in its data file for each target of a
campaign it names (its CAMPAIGNS), live or not, and for each target an exhaustive search covers (its EXHAUSTIVE), and the
section "Search progress" draws it.  Quals: python3 -B quals/quals_chance.py

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
  spent       the exposure of the target's search: each plan's own rate times the search CPU-hours of the target's ended
              seeds in it, summed over the campaign's plans: the campaign has found no witness in them (README [CON],
              2026-11-03: "conditional on not having found anything so far").
  prior       of a target, in its campaign's PRIORS: with probability 1 - p_exists no (-1)^m-symmetric sequence exists
              at the cell and theta = 0; otherwise log2 theta is normal with mean and sd.
  exists      of a target: P(a witness exists | none in the exposure spent) under the bandit's model, the prior weighted
              by exp(-theta spent) (exists).  Until 2026-11-06 also the chance of a witness within the next t hours,
              witnesses a Poisson process at theta r per CPU-hour at the CPU-hours per wall-hour of the seeds running
              (cores), of which this was the first factor.
  as of t     of a campaign, as it stood just before time t: its plans begun by then, each with its records from before
              then; a quantity as of t is computed from those alone, with t as now.
  since       of a target, the first start of a plan of its campaign holding it: its history's origin.
  history     of a target, its P(exists) as of each time, every QUARTER seconds from its since, and as of now, at the
              times it was live with a rate in its live plan (so it ends where its search stopped) (README [CON],
              2026-11-03; dreeves: "the curve should fall in light of the conditional probability but it should remain
              historically accurate"): each point from the records before its time alone, so later records never
              change it.
  exhaustive  of a search: one that covers every case, so that it finds a witness exactly when one exists (288:10's
              form trees, searches/formtree), whose P(exists) is its work model's (work).
  odds        of a modeled target, what the page states and draws of it (dreeves, 2026-11-04: "1. probability a
              partition exists, starting from whatever prior and going down as the search proceeds and doesn't find
              one"; 2026-11-06: "after the ETA graph, explicitly state the prior probability a bipartition exists ...
              then show the first probability graph ... then kill everything below that"): its prior P(exists) (prior:
              the campaign's p_exists, or an exhaustive search's), its history's origin (since), and exists, [t,
              P(exists)] at its history's times and at now, now's only once measured there and when the last point is
              not now's (its search stopped).  Until 2026-11-06 it carried its basis (campaign, lindy or work), the
              hours ahead and curves of the chance of a find given existence, and came with the chance of a find within
              t hours and that chance's history, which the page drew in two more graphs.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, math
from functools import lru_cache
import numpy as np

SPAN, STEP = 10.0, 0.01          # exists's grid of log2 theta: mean +- SPAN sd, STEP bits apart (the trapezoid rule on a
                                 # smooth integrand; the prior's mass beyond 10 sd is about 1e-23)
PRIORS = 'chance.json'           # in a campaign's directory: {targets: {N:M: {p_exists, mean, sd}}, sources: {...}}
ARCHIVED = re.compile(r'plan([1-9][0-9]*)')     # an archived plan's directory below its campaign's: planK, K from 1
QUARTER = 900.0                  # seconds between a history's points
# The section "Search progress" claims one coverage for its intervals, and each estimator draws its band at levels of
# its own, set to give that coverage (2026-11-06; dreeves wants "80% that actually means 80%": the levels that
# historically gave it, estimator by estimator); each is set here alone, so that a calibration changes values only.
COVERAGE = 0.8                   # the coverage the page labels its intervals with (the work bar's caption: work_eta's
                                 # coverage), the nominal one of every band since 2026-11-06.  Not checked against
                                 # outcomes: no estimator has enough finished ones, and the misses seen come from the
                                 # models, not their levels (scratch/calibration-20261106/NOTES.md), so the page calls
                                 # it the model's own.  From the stopgap of 2026-10-12 until then 0.9, every band (0.05,
                                 # 0.95): nominal 80% had held the truth 22 of 31 times for the tree estimate in a replay
                                 # of 304@9's two finished passes (its recorded 80% bands held 0.56, that study found).
                                 # ETAs recorded before 2026-11-06 keep their 90% bands.
BANDS = dict(                    # each estimator's lower and upper quantile levels: its band around its median
    tree=(0.1, 0.9),             # progress.py's estimate: an overnight_v5.py pass's hours to go, from subtree costs
    box=(0.1, 0.9),              # progress.py's box_estimate: a boxsplit.py pass's, Kaplan-Meier on its leaves
    urn=(0.1, 0.9),              # progress.py's lindy_urn and lindy_work: Lindy urns of jobs (focus.py's root cases)
    pool=(0.1, 0.9),             # progress.py's pool_estimate: a fanout.py run's, from its pool's random draws
    stages=(0.1, 0.9),           # progress.py's stages_of: each later stage's, and the time to a recordable result
    gott=(0.1, 0.9),             # progress.py's gott: Gott's rule, for a tracked search with no estimate of its own
    work=(0.1, 0.9))             # work: the form-tree work model's to_go and total (and formtree_eta.py's scatter)


def grid(mean, sd, spent):
    """exists's grid of theta and, at each point, the prior's weight times P(no witness in the exposure spent | theta),
    given log2 theta ~ N(mean, sd^2)."""
    z = np.arange(mean - SPAN * sd, mean + SPAN * sd + STEP / 2, STEP)
    w = np.exp(-0.5 * ((z - mean) / sd) ** 2)
    theta = np.exp2(z)
    return theta, w / w.sum() * np.exp(-theta * spent)


def exists(p_exists, mean, sd, spent):
    """P(a witness exists | none in the exposure spent), the prior P(exists) p_exists and log2 theta ~ N(mean, sd^2) if
    it exists: p_exists E[exp(-theta spent)] / (p_exists E[exp(-theta spent)] + 1 - p_exists)."""
    # TODO: error copy; says exists's inputs are out of range, quoting them
    assert 0 <= p_exists <= 1 and 0 < sd < math.inf and math.isfinite(mean) and 0 <= spent < math.inf, f'Claude: "exists({p_exists}, {mean}, {sd}, {spent}) is out of range"'
    _, kept = grid(mean, sd, spent)
    return float(p_exists * kept.sum() / (p_exists * kept.sum() + (1 - p_exists)))


def _quantiles(values, weight):
    """The points at BANDS['work'][0], 50% and BANDS['work'][1] of the law with the masses weight at values: at each
    level, the least value whose cumulative mass, the values in increasing order, reaches it."""
    order = np.argsort(values)
    return values[order][np.searchsorted(np.cumsum(weight[order]), [BANDS['work'][0], 0.5, BANDS['work'][1]], side='left')]


def work(p_exists, total, done, rate, weight):
    """A work model's forecast for a still-open search with no witness so far: P(exists), and the time and the work to
    exhaust its tree.

    total, rate and weight are matching one-dimensional draws: positive total work, positive work per wall-hour,
    and nonnegative weights summing to one. Paired work/rate draws may be dependent. done is checked work in the same
    units, excluding repeated work. The structural draws precede the no-witness update; draws at or below done are
    conditioned out, not clamped. No surviving support is a failed model, not a completed proof.

    The existence prior is p_exists. Work has the same structural distribution under existence and nonexistence;
    if a witness exists, its first discovery is assumed uniform in [0,total]. At work W>done, no-find survival is
    q=(W-done)/W. For normalized structural weights a, A=sum(a*q) and Z=1-p_exists+p_exists*A. The posterior existence
    probability, exists, is p_exists*A/Z. These are conditional modeling assumptions, not empirically calibrated
    existence probabilities.

    to_go, the time to exhaust the tree (every node checked, no witness): the median and band (BANDS['work']) of
    (W-done)/rate under the weights a, in seconds; and total (dreeves, 2026-11-06: "should that progress bar be measuring
    amount of work, not time? ... we can still have a 90% CI for amount of work remaining, right?"), the work then, W,
    under the same weights, in work's units, so that it does not depend on the rates.  Neither depends on p_exists:
    each is the law of a witness's find mixed with the tree's exhaustion at P(exists) 0, since a witness of an
    exhaustive search is found only when the search reaches it (the coordinator's analysis, which dreeves accepted on
    2026-11-06; until then that mixture at the posterior P(exists), so that the prior moved them, with p, found and
    completion, the chances of a find and of the search's end within each hour, beside them).
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
    lo, median, hi = _quantiles(rest, weight) * 3600
    end = done + _quantiles(left, weight)       # the work done when the tree is exhausted: lo, median, hi
    return dict(exists=p_exists * A / Z, to_go=dict(median=float(median), lo=float(lo), hi=float(hi)),
                total=dict(median=float(end[1]), lo=float(end[0]), hi=float(end[2])))


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
    """The target's search in one of the campaign's plans, the one in home with these journal records: (cpu, probes),
    its seeds' search CPU by seed and its finished probe seeds' rounds (X, cpu) by seed, each PREFIX.jsonl read below
    home where its journal names it below the campaign's directory (an archived plan's files moved with it).  (Until
    2026-11-06 also its seeds' starts and ends, for the CPU-hours per wall-hour ahead.)  Asserted: each seed started once
    and ended at most once, after its start, of kind plain or probe, a plain one with its CPU seconds, and each named
    below the campaign's directory."""
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
    return cpu, probes


def rate_of(probes):
    """A plan's rate at a target (see the vocabulary) from its finished probe seeds' rounds, {seed: (X, cpu)}."""
    return sum(X for X, _ in probes.values()) / (sum(c for _, c in probes.values()) / 3600)


def measure(root, campaign, plans, prior, target):
    """P(exists) of the target, whose prior is this, from its campaign's plans (as plans gives them, the live one last,
    or as they stood at a time, as_of): exists at the exposure spent (see the vocabulary); None until a probe seed of
    the target has finished in the live plan, its rate measured there (as before 2026-11-06, when that rate also set
    the chance of a find ahead).  Asserted: every archived plan that searched the target has its rate there."""
    each = [searched(root, campaign, home, records, target) for home, _, records in plans]
    unmeasured = [home for (home, _, _), (c, p) in zip(plans, each[:-1]) if c and not p]
    # TODO: error copy; says these archived plans searched the target with no finished probe seed, so the exposure of their hours there is unknown, naming them
    assert not unmeasured, f'Claude: "{unmeasured} searched {target} without a finished probe seed: the exposure of those hours is unknown"'
    spent = sum(rate_of(p) * (sum(c.values()) / 3600) for c, p in each if p)
    return exists(prior['p_exists'], prior['mean'], prior['sd'], spent) if each[-1][1] else None


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
    """The target's P(exists) (measure) as of each of its history's times (see the vocabulary) at time now: [(t, P),
    ...] in time order."""
    ps = plans(root, campaign)
    prior, first = prior_of(root, campaign, target), began(ps, target)
    then = [(t, as_of(ps, t)) for t in quarters(first, now)]
    chances = [(t, measure(root, campaign, p, prior, target)) for t, p in then if target in live(p[-1][1], p[-1][2])]
    return [(t, P) for t, P in chances if P is not None]


def odds(since, points, now, current, prior):
    """The odds (see the vocabulary) under this prior P(exists), its history's origin since, from a history's points
    [(t, P(exists)), ...] (stood's form) and current, P(exists) as of now (None before it is measured there): exists
    at the points' times and at now, now's only once measured and when the last point is not now's.  (Until 2026-11-04
    now's always, unmeasured or not, and none at all with no points: an IndexError.)"""
    # TODO: error copy; says the odds' prior is not a probability, quoting it
    assert type(prior) in (int, float) and 0 <= prior <= 1, f'Claude: "the prior {prior!r} is no probability"'
    tail = [] if current is None or [t for t, _ in points[-1:]] == [now] else [(now, current)]
    return dict(prior=prior, since=since, exists=[[t, p] for t, p in points + tail])


def reprior(p, old, new):
    """P(exists | the evidence) under the prior P(exists) new, from p, that posterior under the prior old (dreeves,
    2026-11-06, of 288:10's prior 0.01: "that sounds dumb. let's start with an ignorant prior (50%) and let it fall
    naturally as the search progresses"): the evidence's likelihood ratio, P(none found | exists) / P(none found | none
    exists) = p (1 - old) / (old (1 - p)), does not depend on the prior, so the posterior under new is new L / (new L +
    1 - new).  So a chance of a find made under old, P(exists) times a chance given existence, which the prior leaves
    alone, times reprior(p, old, new) / p is the one made under new."""
    # TODO: error copy; says reprior's inputs are out of range, quoting them
    assert 0 <= p < 1 and 0 < old < 1 and 0 <= new <= 1, f'Claude: "reprior({p}, {old}, {new}) is out of range"'
    L = p * (1 - old) / (old * (1 - p))
    return new * L / (new * L + (1 - new))


def shown(root, campaign, target, now):
    """What the page shows of the target at time now, live or not: its odds (odds), from its history (stood), its
    P(exists) now (of) and its campaign's prior, the history's origin its since (began); once its search stops, its
    history kept up to the stop, as the ETA chart keeps its records (dreeves, 2026-11-04: "shouldn't it stay there for
    posterity like the ETA graph does? is this another anti-magic violation?"; until then None once the target was not
    live, and so no chart).  (Until 2026-11-06 also its chance of a witness within each t hours and that chance's
    history.)"""
    return odds(began(plans(root, campaign), target), stood(root, campaign, target, now), now, of(root, campaign, target, now),
                prior_of(root, campaign, target)['p_exists'])


def of(root, campaign, target, now):
    """P(exists) (measure) of the target N:M at time now (epoch seconds), from the campaign in the directory campaign
    (a path from root, the repository's root, where the campaign runs) as of now, live or not: once its search stops,
    its P(exists) as it stood then.  (Until 2026-11-06 the chance of a witness within each t hours, 0 once its search
    stopped, as it counted the seeds running there; until 2026-11-04 None for a target not live.)  Asserted: the
    campaign began before now, and one of its plans holds the target."""
    ps = as_of(plans(root, campaign), now)
    # TODO: error copy; says the campaign had not begun before the time given, naming both
    assert ps, f'Claude: "{campaign} had not begun before {now}"'
    # TODO: error copy; says no plan of the campaign holds the target, naming both
    assert any(target in cells(plan) for _, plan, _ in ps), f'Claude: "no plan of {campaign} holds {target}"'
    return measure(root, campaign, ps, prior_of(root, campaign, target), target)


if __name__ == '__main__':
    # TODO: error copy; says this module holds functions, which progress.py calls
    raise SystemExit('Claude: "chance.py holds functions; progress.py uses them"')
