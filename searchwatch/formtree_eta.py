"""Work-based uncertainty model for the checked form-tree search.

Since 2026-11-11 (Fable 5.2) also the estimator (see track.py's vocabulary) of a form-tree search, which the tracker
runs beside it:

    python3 -B searchwatch/track.py run NAME SEARCH N:M searchwatch/formtree_eta.py VERDICTS MODEL PRIOR -- COMMAND ...

VERDICTS is the search's verdicts.jsonl (the driver's, searches/formtree/ftree.py), MODEL the file of its work model
(read_model) and PRIOR the probability, before the search, that what it searches for exists.  Each time it is run it
appends one estimate (estimate, below) to the record that TRACK_RECORD names, of that record's search; with no work
done yet or with an open node among the verdicts it fails and appends nothing.  With every root complete its estimate
is exact (2026-11-13; the tracker runs it once more when the search has ended): the tree is exhausted.

The frozen model stores independent eight-dive blocks for each initial root.
A shared multiplicative discrepancy represents errors that more root samples
cannot average away. Remaining roots condition that factor jointly on their
observed work; completed roots contribute their exact sizes. Independent local
log discrepancies allow a root-specific miss without imposing it on every root.
Version 1 fixes the local scatter. Version 2 gives it a lognormal prior and
learns it from exact completions and unfinished-root survival together.
The shared-bias prior and exchangeability across roots remain assumptions.

Since 2026-11-15, a model may carry an explicit frozen-frontier checkpoint.
Its roots are groups of unfinished subtrees; each bootstrap block is a complete
stratified sampling round, and its mean estimates that group's total work.
The older eight-dive block representation remains unchanged. Model activations
are recorded by path/hash in the run; earlier forecasts retain their old values.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import chance
import formtree_work
import track
import numpy as np
from scipy.special import ndtr, ndtri, log_ndtr, ndtri_exp


PROPOSALS_CAP=2**20   # the most proposals attach draws to reach a model's floor of effective draws (2026-11-07)


# (2026-11-16) the floats in each draws x units array (64 MB); a bounded unit's bootstrap means per draw and the pool
# they come from; the floats each pass over the draws holds; the points of the grid of the local sd's posterior
BUDGET, CANDIDATES, POOL, CELLS, GRID = 2**23, 64, 2**14, 2**20, 8001


def draws(model, work, count=4096):
    """Weighted total-work/rate draws, conditioned on exact and unfinished units (the model's roots).

    A unit's total is its blocks' bootstrap mean (base) times a shared factor F and a local factor L of its own: log F
    is normal (log_bias, discrepancy_log_sd), log L normal with sd s = root_log_sd exp(root_log_sd_uncertainty
    N(0, 1)), one s per draw (version 2 learns it; version 1 fixes it).  Since 2026-11-16 (Opus 5.5; dreeves, of the
    live 480:14 ETA, whose 16 frontier groups had let one member's 8.5x overrun set a 4.4x floor under every group:
    "ok, go ahead and fix"), the draws are made this way:
    - a complete unit's exact size updates log F's normal against its point base, the mean of its block means, and s is
      drawn from its posterior given the complete units, on a grid of GRID points.  Until then s came from its prior
      and each row's bootstrap draw of every complete unit entered the row's weight, and the product over hundreds of
      complete units left about one effective draw;
    - log F is drawn from that normal, half the time truncated below at a, the least value at which every bounded
      unit could reach its work with no local noise, and the mixture's density is divided out of the weight, so that
      zero local noise still works;
    - a bounded unit (unfinished, with work done) weights its draw by the probability that it reaches that work,
      averaged over CANDIDATES bootstrap means drawn from a POOL of its own, takes one of them in proportion to that
      probability, and draws its local noise from its prior truncated at what reaching the work requires.  Its overrun
      raises its own total, and F only as far as that probability does.  Until then F had to exceed every unit's
      work over its base and local noise, which set a floor under F for every unit;
    - an unfinished unit with nothing done keeps its row's bootstrap mean and an untruncated local noise; a complete
      unit's base is its point base.
    proposal is base times L, so trees = proposal F for an unfinished unit; root_log_sd is each draw's s.  With zero
    local noise, one completed unit fixes F exactly; multiple zero-noise completed units are unsupported.  Rates are
    nodes per wall second, with shared persistent log uncertainty.
    """
    assert isinstance(count, int) and count > 0
    assert [r['name'] for r in model['roots']] == [r['name'] for r in work['roots']]
    done = np.array([r['done'] for r in work['roots']], dtype=float)
    pending = np.array([not r['complete'] for r in work['roots']])
    assert pending.any() and np.isfinite(done).all() and (done >= 0).all()
    assert work['done'] == sum(r['done'] for r in work['roots'])
    assert np.isfinite(work['rate']) and work['rate'] > 0
    mu, sd, rsd, local_sd = (model[k] for k in ('log_bias', 'discrepancy_log_sd', 'rate_log_sd', 'root_log_sd'))
    assert np.isfinite([mu, sd, rsd, local_sd]).all() and sd > 0 and rsd >= 0 and local_sd >= 0
    scatter_uncertainty = model.get('root_log_sd_uncertainty', 0.)
    assert np.isfinite(scatter_uncertainty) and scatter_uncertainty >= 0
    assert scatter_uncertainty == 0 or local_sd > 0
    units = len(model['roots'])
    assert count * units <= BUDGET, (count, units)
    rng = np.random.default_rng(model['seed'])
    means = [np.asarray(root['blocks'], dtype=float) for root in model['roots']]
    assert all(b.ndim == 2 and min(b.shape) > 0 and np.isfinite(b).all() and (b > 0).all() for b in means)
    means = [b.mean(axis=1) for b in means]                  # each block's mean, the unit's bootstrap resamples blocks
    boot = lambda m, size: m[rng.integers(len(m), size=(size, len(m)))].mean(axis=1)
    point = np.array([m.mean() for m in means])              # a unit's point base: the mean of its block means
    base = np.tile(point, (count, 1))
    for j in np.flatnonzero(pending):
        base[:, j] = boot(means[j], count)
    completed = ~pending
    y = np.log(done[completed]) - np.log(point[completed])
    n = len(y)
    grid = np.linspace(-8., 8., GRID)                        # z, s = root_log_sd exp(root_log_sd_uncertainty z)
    log_post = -.5 * grid**2
    bias_mean, bias_sd = np.full(count, float(mu)), np.full(count, float(sd))
    def likelihood(local):
        # the complete units' marginal likelihood given the local sd: det(sigma^2 I + sd^2 11') varies with sigma and
        # must not disappear from it
        den = local**2 + n * sd**2
        quad = ((y - y.mean())**2).sum() / local**2 + n * (y.mean() - mu)**2 / den
        return -.5 * quad - .5 * ((n - 1) * np.log(local**2) + np.log(den)), den
    if completed.any():
        if local_sd == 0:
            assert n == 1
            bias_mean, bias_sd = np.full(count, y[0]), np.zeros(count)
        else:
            log_post = log_post + likelihood(local_sd * np.exp(scatter_uncertainty * grid))[0]
    cdf = np.cumsum(np.exp(log_post - log_post.max())); cdf /= cdf[-1]
    local = local_sd * np.exp(scatter_uncertainty * np.interp(rng.uniform(size=count), cdf, grid))
    log_likelihood = np.zeros(count)
    if completed.any() and local_sd > 0:
        log_likelihood, den = likelihood(local)
        bias_mean = mu + n * sd**2 * (y.mean() - mu) / den
        bias_sd = sd * local / np.sqrt(den)
    bounded = np.flatnonzero(pending & (done > 0))
    pools = np.array([boot(means[j], POOL) for j in bounded]).reshape(len(bounded), POOL).T
    a = (np.log(done[bounded]) - np.log(pools)).min(axis=0).max(initial=-np.inf)
    with np.errstate(divide='ignore', invalid='ignore'):
        log_tail = log_ndtr((bias_mean - a) / bias_sd)        # log P(log F > a) under the normal
        truncated = bias_mean - bias_sd * ndtri_exp(np.log(rng.uniform(np.finfo(float).eps, 1., count)) + log_tail)
    free = bias_mean + bias_sd * rng.standard_normal(count)
    logf = np.where((rng.uniform(size=count) < .5) & np.isfinite(log_tail), truncated, free)
    log_weight = -np.log(.5) - np.logaddexp(0., np.where(logf > a, -log_tail, -np.inf))
    noise = np.zeros((count, units))
    noise[:, pending] = rng.standard_normal((count, int(pending.sum())))
    rows = max(1, CELLS // (CANDIDATES * max(len(bounded), 1)))
    for lo in range(0, count, rows):
        r = slice(lo, min(lo + rows, count))
        cand = pools[rng.integers(POOL, size=(r.stop - r.start, CANDIDATES, len(bounded))), np.arange(len(bounded))]
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (np.log(done[bounded]) - np.log(cand) - logf[r, None, None]) / local[r, None, None]
        log_s = log_ndtr(-np.where(np.isnan(t), -np.inf, t))   # log P(local noise reaches the work), per candidate
        log_weight[r] += (np.logaddexp.reduce(log_s, axis=1) - np.log(CANDIDATES)).sum(axis=1)
        choice = (log_s + rng.gumbel(size=log_s.shape)).argmax(axis=1)[:, None]   # one in proportion to it
        taken = np.take_along_axis(log_s, choice, axis=1)[:, 0]
        base[r, bounded] = np.take_along_axis(cand, choice, axis=1)[:, 0]
        noise[r, bounded] = -ndtri_exp(np.log(rng.uniform(np.finfo(float).eps, 1., taken.shape)) + taken)
    with np.errstate(invalid='ignore', over='ignore'):
        proposal = np.where(pending, base * np.exp(local[:, None] * noise), base)
        trees = np.where(pending, proposal * np.exp(logf)[:, None], done)
    rate = work['rate'] * np.exp(rsd * rng.standard_normal(count))
    keep = np.isfinite(log_weight)
    assert keep.any()
    weight = np.exp(log_weight[keep] - log_weight[keep].max()); weight /= weight.sum()
    trees, proposal, base = trees[keep], proposal[keep], base[keep]
    assert np.isfinite(trees).all() and (trees[:, pending] > done[pending]).all()
    assert np.isfinite(rate).all() and (rate > 0).all()
    return dict(total=trees.sum(axis=1), rate=rate[keep], weight=weight, trees=trees, base=base, proposal=proposal,
                factor=np.exp(logf[keep]), bias_mean=bias_mean[keep], bias_sd=bias_sd[keep],
                completed_log_likelihood=log_likelihood[keep], root_log_sd=local[keep])


def rate(points):
    """A search's nodes checked a second of running, from points, [(seconds of running, nodes checked by then), ...]
    in order from (0, 0): each interval between them weighted by exp(-age / formtree_work.TAU), its age measured
    between middles back from the newest interval, whose weight is then exactly 1 (as formtree_work.read's of a log's
    intervals; dreeves, 2026-11-07: "maybe 3 hours at least, or just do an exponentially weighted moving average of
    rates")."""
    pairs = list(zip(points, points[1:]))
    newest = (pairs[-1][0][0] + pairs[-1][1][0]) / 2
    weights = [math.exp(((a[0] + b[0]) / 2 - newest) / formtree_work.TAU) for a, b in pairs]
    return (sum(w * (b[1] - a[1]) for w, (a, b) in zip(weights, pairs))
            / sum(w * (b[0] - a[0]) for w, (a, b) in zip(weights, pairs)))


FLOOR, DRAWS = 1000, 16384      # the effective draws a forecast needs, and the proposals it starts with (65536, attach's
                                # for a version-2 model, until 2026-11-16, when the local sd's draw from its posterior left
                                # half the draws or more effective and each draw grew dearer)


def sampled(model, work):
    """draws of the model given the work, the proposals doubled from DRAWS until their effective draws reach FLOOR, at
    most PROPOSALS_CAP of them (asserted: a concentrated proposal must not publish an apparently precise forecast).
    Since 2026-11-16 both bounds are also at most the greatest power of 2 that keeps a draws x units array within
    BUDGET: 8192 for the live 480:14 frontier's 626 members, on a Mac with 16 GB."""
    most = min(PROPOSALS_CAP, 1 << (BUDGET // len(model['roots'])).bit_length() - 1)
    count = min(DRAWS, most)
    samples = draws(model, work, count=count)
    while float(1 / (samples['weight'] @ samples['weight'])) < FLOOR and count < most:
        count *= 2
        samples = draws(model, work, count=count)
    assert float(1 / (samples['weight'] @ samples['weight'])) >= FLOOR, count
    return samples


MODEL = {'kind', 'seed', 'roots', 'log_bias', 'discrepancy_log_sd', 'rate_log_sd', 'root_log_sd', 'root_log_sd_uncertainty',
         'provenance', 'assumptions'}


def read_model(path, expected_sha256=None):
    """The work model in the file at path, as draws reads it: {kind: formtree, seed, roots: [{name, blocks}, ...] (each
    root's dive estimates of its tree's nodes, in blocks of eight), log_bias, discrepancy_log_sd, rate_log_sd,
    root_log_sd, root_log_sd_uncertainty (draws's docstring), and provenance and assumptions, which say in words where
    the dives and the parameters came from and what is assumed of them}.
    An optional checkpoint uses formtree_frontier's explicit prefix/group contract.
    Its blocks contain scaled member probes; their means are complete group-round
    estimates. An activation's expected_sha256 binds the exact bytes read here."""
    data = Path(path).read_bytes()
    assert expected_sha256 is None or hashlib.sha256(data).hexdigest() == expected_sha256
    model = json.loads(data)
    assert set(model) - {'checkpoint'} == MODEL and model['kind'] == 'formtree', sorted(model)
    assert model['roots'] and all(set(r) == {'name', 'blocks'} for r in model['roots']), path
    return model


def estimate(model, roots, points, prior, pending, finished, offset=0):
    """A form-tree search's estimate (track.py's vocabulary), without its time: of basis formtree, in nodes; done the
    nodes checked (roots, formtree_work._roots's rows: each root's exact count and whether it is complete), their rate
    by points (rate); the total nodes when the tree is exhausted and the seconds of running until then, and
    P(exists | none found so far) from the prior, by the model's draws given that work (sampled) and chance.work;
    pending, the nodes named with no verdict yet (formtree_work.walk's), as given; and finished, the tasks with a
    verdict, as given (2026-11-12).
    A tree whose every root is complete is exhausted with nothing found (walk has asserted that no verdict left a node
    open), which is no forecast: the total is the nodes checked, exactly, nothing is to go, and P(exists | none found)
    is 0 whatever the prior (Fable 5.2, 2026-11-13; dreeves: "sure, that sounds cleaner to get exact counts and
    probability 0 when we completed a proof").  chance.work infers no such verdict (its caller supplies it), and the
    model's draws need a root not complete: so the one branch here.
    offset is the exact accounted work before a frozen frontier. Posterior roots
    describe only the suffix; offset is added once to total and done. Rate points
    remain the original search's cumulative counts and running-time coordinates."""
    assert type(offset) is int and offset >= 0
    work = dict(roots=roots, done=sum(r['done'] for r in roots), rate=rate(points))
    done = offset + work['done']
    if all(r['complete'] for r in roots):
        forecast = dict(exists=0.0, to_go=dict(median=0.0, lo=0.0, hi=0.0), total=dict(median=done, lo=done, hi=done))
    else:
        samples = sampled(model, work)
        forecast = chance.work(prior, offset + samples['total'], done, samples['rate'] * 3600, samples['weight'])
    return dict(event='estimate', basis='formtree', unit='nodes', done=done, rate=work['rate'], total=forecast['total'],
                to_go=forecast['to_go'], prior=prior, exists=forecast['exists'], finds=forecast['exists'], pending=pending, finished=finished)


def history(points, current, now, period=900):
    """Keep committed predictions unchanged; draw the current one between saves.

    The one cadence branch commits a new point only once its interval elapsed.
    Old records never acquire numbers from a newly fitted model.
    """
    assert points and now>=points[-1][0] and period>0
    if now-points[-1][0]>=period:
        points.append([now,current])
    return points if points[-1][0]==now else points+[[now,current]]


def load(root, path, target='288:10'):
    """Read a versioned model, validate its schema and input hashes, and return it with its byte hash."""
    root=Path(root);path=root/path
    data=path.read_bytes();model=json.loads(data)
    assert type(model['version']) is int and model['version'] in (1,2)
    extra={1:set(),2:{'root_log_sd_uncertainty'}}[model['version']]
    assert set(model)=={'version','kind','target','seed','roots','checks','log_bias','discrepancy_log_sd',
                        'rate_log_sd','root_log_sd','samples','alpha','provenance','calibration','assumptions'} | extra
    assert model['kind']=='formtree' and model['target']==target
    assert type(model['seed']) is int and model['seed']>=0
    assert type(model['samples']) is int and model['samples']>0
    assert all(type(model[k]) in (int,float) and math.isfinite(model[k]) for k in
               ('log_bias','discrepancy_log_sd','rate_log_sd','root_log_sd','alpha'))
    assert model['discrepancy_log_sd']>0 and model['rate_log_sd']>=0 and model['root_log_sd']>=0 and model['alpha']>=0
    uncertainty=model.get('root_log_sd_uncertainty',0.)
    assert type(uncertainty) in (int,float) and math.isfinite(uncertainty) and uncertainty>=0
    assert model['version']==1 or uncertainty>0 and model['root_log_sd']>0
    roots=model['roots'];assert type(roots) is list and roots
    names=[];samples=0
    for row in roots:
        assert set(row)=={'name','input_sha256','blocks'}
        assert type(row['name']) is str and row['name']
        assert type(row['input_sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['input_sha256'])
        names.append(row['name'])
        blocks=row['blocks'];assert type(blocks) is list and blocks
        assert all(type(b) is list and len(b)==8 for b in blocks)
        assert all(type(v) in (int,float) and math.isfinite(v) and v>0 for b in blocks for v in b)
        samples+=sum(map(len,blocks))
    assert len(set(names))==len(names) and samples==model['samples']
    checks=model['checks'];assert type(checks) is dict and checks
    for name,digest in checks.items():
        assert type(name) is str and name and not Path(name).is_absolute() and '..' not in Path(name).parts
        assert type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest)
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,(name,digest)
    provenance=model['provenance']
    assert set(provenance)=={'manifest_sha256','samples_sha256','seed_namespace','source'}
    assert all(type(v) is str and v for v in provenance.values())
    assert all(re.fullmatch('[0-9a-f]{64}',provenance[k]) for k in ('manifest_sha256','samples_sha256'))
    assert type(model['calibration']) is list
    assert all(set(c)=={'name','truth','complete_mean'} and type(c['name']) is str and c['name'] and
               type(c['truth']) is int and c['truth']>0 and type(c['complete_mean']) in (int,float) and
               math.isfinite(c['complete_mean']) and c['complete_mean']>0 for c in model['calibration'])
    assert set(model['assumptions'])=={'discrepancy','rate','witness','interval'}
    assert all(type(v) is str and v for v in model['assumptions'].values())
    return model,hashlib.sha256(data).hexdigest()


def _legacy(s, root, now):
    """Capture the actually plotted P(exists) once, from the page's snapshot (progress.js: its run's odds), its history's
    origin and its points; a cold start without a snapshot has plotted none, its origin the run's start.  (Until
    2026-11-06 it captured the chance's history and the curves too, and a cold start took its former Lindy model's.)"""
    path=Path(root)/'pagedata'/'progress.js'
    if path.exists():
        text=path.read_text();assert text.startswith('progressData(') and text.rstrip().endswith(');')
        saved=json.loads(text[len('progressData('):].rstrip()[:-2])
        matches=[r for r in saved['runs'] if (r['program'],r['n'],r['order'])==('ftree.py',s['n'],s['order'])]
        assert len(matches)==1 and set(matches[0]['odds'])=={'prior','since','exists'}
        since,exists=matches[0]['odds']['since'],matches[0]['odds']['exists']
    else:
        since,exists=s['passes'][0][0],[]
    assert all(t<=now for t,_ in exists)
    return copy.deepcopy(dict(since=since,exists=exists))


def attach(s, root, model_path, p_exists, now, cache):
    """Attach one current work forecast and immutable earlier chart points to a tracked survey.

    cache is dedicated to this target. Its legacy points are copied once from the actual page snapshot, and points
    retain the model hash, done and rate used when committed. No past prediction is fitted again with new inputs.
    Since 2026-11-06 (dreeves: "everything here seems useless, kill it unless you have a good argument for salvaging
    anything. the up-to-date probability that a bipartition exists is great.") each keeps P(exists) alone (exists), and
    the odds carry the prior p_exists, the history's origin (legacy's since) and P(exists) at the legacy points, at each
    committed point and at now (chance.odds).
    to_go and work_eta's total (2026-11-06, for the page's work bar) are the time and the work to exhaust the tree,
    chance.work's: their median and band (chance.BANDS['work']) while the search runs, which the prior does not move;
    exactly done, and no time to go, once every root is complete; none for a search stopped short of that, which makes
    no forecast. Its coverage, the page's label for its interval, is chance.COVERAGE.
    """
    model,digest=load(root,model_path,f'{s["n"]}:{s["order"]}')
    active=s['state']=='running'
    w=formtree_work.read(root,[r['name'] for r in model['roots']],now=None,active=active)
    if 'legacy' not in cache:
        cache['legacy']=_legacy(s,root,now)
    legacy=cache['legacy'];complete=all(r['complete'] for r in w['roots'])
    assert set(legacy)=={'since','exists'},set(legacy)
    zero=dict(median=0.,lo=0.,hi=0.)
    uncertainty=dict(root_log_sd_posterior=None,effective_samples=None,forecast_samples=0)
    samples=None   # the weighted draws, while the model forecasts
    if complete:
        exists=0.
        to_go=zero if active else None
        total=dict(median=float(w['done']),lo=float(w['done']),hi=float(w['done']))
    elif active:
        # The proposals doubled until their effective draws reach the floor below, at most PROPOSALS_CAP: the floor is the
        # requirement, the count only what meets it (Claude, 2026-11-07; dreeves, of 288:10's ETA stale since its posterior
        # narrowed to 860 effective draws of 65,536: "can-opener question?").  A version-1 model has no floor.
        floor,count={1:0,2:1000}[model['version']],{1:4096,2:65536}[model['version']]
        samples=draws(model,w,count=count)
        while float(1/(samples['weight']@samples['weight']))<floor and count<PROPOSALS_CAP:
            count*=2
            samples=draws(model,w,count=count)
        order=np.argsort(samples['root_log_sd'])
        lo,hi=chance.BANDS['work']
        quantiles=np.interp([lo,.5,hi],np.cumsum(samples['weight'][order]),samples['root_log_sd'][order])
        uncertainty=dict(root_log_sd_posterior=dict(zip(('lo','median','hi'),quantiles.tolist())),
                         effective_samples=float(1/(samples['weight']@samples['weight'])),
                         forecast_samples=len(samples['weight']))
        # Numerical adequacy for coarse tail quantiles; not a coverage guarantee.
        # A concentrated proposal must not publish an apparently precise forecast.
        assert uncertainty['effective_samples']>=floor, uncertainty
        forecast=chance.work(p_exists,samples['total'],w['done'],samples['rate']*3600,samples['weight'])
        exists=forecast['exists']
        to_go=forecast['to_go']
        total=forecast['total']
    else:
        exists=(cache['last']['exists'] if 'last' in cache else
                legacy['exists'][-1][1] if legacy['exists'] else p_exists)
        to_go=None
        total=None
    current=dict(exists=exists,model=digest,done=w['done'],rate=w['rate'],uncertainty=uncertainty)
    if active:
        points=history(cache.setdefault('points',[[now,copy.deepcopy(current)]]),copy.deepcopy(current),now)
        cache['shown']=copy.deepcopy(points)
    else:
        points=cache.get('shown',cache.get('points',[]))
    cache['last']=copy.deepcopy(current)
    odds=chance.odds(legacy['since'],legacy['exists']+[[t,x['exists']] for t,x in points],now,exists,p_exists)
    # The discrepancy-factor fields describe frozen priors; the learned root
    # scatter is reported separately in root_log_sd_posterior.
    metadata=dict(source_time=w['source_time'],samples=model['samples'],
                  nodes=float(sum(np.asarray(r['blocks']).mean() for r in model['roots'])),
                  done=w['done'],rate=w['rate'],roots_done=sum(r['complete'] for r in w['roots']),
                  roots_total=len(w['roots']),model='importance',interval='conditional',
                  discrepancy_factor=math.exp(model['discrepancy_log_sd']),
                  root_discrepancy_factor=math.exp(model['root_log_sd']),rate_log_sd=model['rate_log_sd'],
                  coverage=chance.COVERAGE,total=total,**uncertainty)
    if to_go is not None:
        s['etas'][str(float(now))]=[to_go[k]/3600 for k in ('median','lo','hi')]
    # roots and posterior (2026-11-07), for the sea's blocks of the roots (progress.rooted): each root's name, nodes
    # checked and whether complete, and the weighted draws (draws's) while the model forecasts, else None
    return s | dict(to_go=to_go,display=s['display'] | dict(lindy=False,work_eta=metadata),odds=odds,roots=w['roots'],
                    posterior=samples)


if __name__ == '__main__':
    import formtree_frontier
    verdicts, initial_model, prior = sys.argv[1], sys.argv[2], float(sys.argv[3])
    path, now = os.environ[track.RECORD], time.time()
    runs, passes = track.search_of(path, now)
    record = track.checked(track.lines(path))
    selected = track.model_of(record, initial_model, now)
    model = read_model(selected['path'], selected['sha256'])
    assert 'checkpoint' not in model or model['checkpoint']['target'] == record[0]['target']
    state = formtree_frontier.observed(model, formtree_work._prefix(Path(verdicts))[0])
    roots, waiting = state['roots'], state['waiting']
    done = state['offset'] + sum(r['done'] for r in roots)
    # the search's nodes checked against its seconds of running: none at its start, then as each of its estimates of
    # this basis found them, then now
    before = sorted((x['time'], x['done']) for r in runs for x in r if x['event'] == 'estimate' and x['basis'] == 'formtree')
    points = [(0.0, 0)] + [(track.running(passes, t), done) for t, done in before] + [(track.running(passes, now), done)]
    track.append(path, dict(estimate(model, roots, points, prior, len(waiting), state['finished'], state['offset']), time=now))
