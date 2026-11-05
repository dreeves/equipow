"""Work-based uncertainty model for the checked form-tree search.

The frozen model stores independent eight-dive blocks for each initial root.
A shared multiplicative discrepancy represents errors that more root samples
cannot average away. Remaining roots condition that factor jointly on their
observed work; completed roots contribute their exact sizes. Independent local
log discrepancies allow a root-specific miss without imposing it on every root.
The local and shared variance components are not independently identified by
the small calibration sample; their combined variance is an explicit assumption.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import chance
import formtree_work
import numpy as np
from scipy.special import ndtr, ndtri, log_ndtr, ndtri_exp


def draws(model, work, count=4096):
    """Weighted total-work/rate draws, conditioned on exact and unfinished roots.

    base resamples whole eight-dive blocks independently within each root.
    Independent lognormal local discrepancies first scale the bootstrap bases.
    Completed log ratios update the normal shared log discrepancy analytically;
    their integrated likelihood reweights each bootstrap row. Pending-root lower
    bounds then multiply that weight by the updated shared-factor survival, and
    its conditional inverse CDF samples the remaining uncertainty without rejection.
    With zero local noise, one completed root fixes the shared factor exactly;
    multiple zero-noise completed observations are explicitly unsupported.
    Rates are nodes per wall second, with shared persistent log uncertainty.
    """
    assert isinstance(count,int) and count>0
    assert [r['name'] for r in model['roots']]==[r['name'] for r in work['roots']]
    done=np.array([r['done'] for r in work['roots']],dtype=float)
    pending=np.array([not r['complete'] for r in work['roots']])
    assert pending.any() and np.isfinite(done).all() and (done>=0).all()
    assert work['done']==sum(r['done'] for r in work['roots'])
    assert np.isfinite(work['rate']) and work['rate']>0
    mu,sd,rsd,local_sd=(model[k] for k in ('log_bias','discrepancy_log_sd','rate_log_sd','root_log_sd'))
    assert np.isfinite([mu,sd,rsd,local_sd]).all() and sd>0 and rsd>=0 and local_sd>=0
    rng=np.random.default_rng(model['seed'])
    base=[]
    for root in model['roots']:
        blocks=np.asarray(root['blocks'],dtype=float)
        assert blocks.ndim==2 and min(blocks.shape)>0
        assert np.isfinite(blocks).all() and (blocks>0).all()
        means=blocks.mean(axis=1)
        base.append(means[rng.integers(len(means),size=(count,len(means)))].mean(axis=1))
    base=np.stack(base,axis=1)
    completed=~pending
    bias_mean=np.full(count,mu);bias_sd=sd;log_likelihood=np.zeros(count)
    if completed.any():
        assert (done[completed]>0).all()
        y=np.log(done[completed])-np.log(base[:,completed])
        n=y.shape[1]
        if local_sd==0:
            assert n==1
            bias_mean=y[:,0];bias_sd=0.
            log_likelihood=-.5*((bias_mean-mu)/sd)**2
        else:
            ybar=y.mean(axis=1);den=local_sd**2+n*sd**2
            bias_mean=mu+n*sd**2*(ybar-mu)/den
            bias_sd=sd*local_sd/np.sqrt(den)
            quad=((y-ybar[:,None])**2).sum(axis=1)/local_sd**2+n*(ybar-mu)**2/den
            log_likelihood=-.5*quad
    proposal=base.copy()
    proposal[:,pending]*=np.exp(local_sd*rng.standard_normal((count,int(pending.sum()))))
    assert np.isfinite(proposal).all() and (proposal>0).all()
    threshold=(done[pending]/proposal[:,pending]).max(axis=1)
    if bias_sd==0:
        factor=np.exp(bias_mean);keep=factor>threshold
        assert keep.any()
        base,proposal,bias_mean,log_likelihood,factor=(x[keep] for x in
            (base,proposal,bias_mean,log_likelihood,factor))
        log_weight=log_likelihood
    else:
        with np.errstate(divide='ignore'):
            z=(np.log(threshold)-bias_mean)/bias_sd
        log_survival=log_ndtr(-z)
        u=rng.uniform(np.finfo(float).eps,1.,count)
        factor=np.exp(bias_mean-bias_sd*ndtri_exp(np.log(u)+log_survival))
        log_weight=log_likelihood+log_survival
    assert np.isfinite(log_weight).any() and not np.isnan(log_weight).any()
    weight=np.exp(log_weight-log_weight.max());weight/=weight.sum()
    trees=np.broadcast_to(done,proposal.shape).copy()
    trees[:,pending]=proposal[:,pending]*factor[:,None]
    rate=work['rate']*np.exp(rsd*rng.standard_normal(len(factor)))
    assert np.isfinite(trees).all() and (trees[:,pending]>done[pending]).all()
    assert np.isfinite(rate).all() and (rate>0).all()
    return dict(total=trees.sum(axis=1),rate=rate,weight=weight,trees=trees,base=base,proposal=proposal,
                bias_mean=bias_mean,bias_sd=bias_sd,completed_log_likelihood=log_likelihood)


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
    assert set(model)=={'version','kind','target','seed','roots','checks','log_bias','discrepancy_log_sd',
                        'rate_log_sd','root_log_sd','samples','alpha','provenance','calibration','assumptions'}
    assert type(model['version']) is int and model['version']==1
    assert model['kind']=='formtree' and model['target']==target
    assert type(model['seed']) is int and model['seed']>=0
    assert type(model['samples']) is int and model['samples']>0
    assert all(type(model[k]) in (int,float) and math.isfinite(model[k]) for k in
               ('log_bias','discrepancy_log_sd','rate_log_sd','root_log_sd','alpha'))
    assert model['discrepancy_log_sd']>0 and model['rate_log_sd']>=0 and model['root_log_sd']>=0 and model['alpha']>=0
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


def _legacy(s, root, prior, now):
    """Capture actual plotted arrays once; a cold fixture without a snapshot uses its former Lindy model."""
    path=Path(root)/'progress.js'
    if path.exists():
        text=path.read_text();assert text.startswith('progressData(') and text.rstrip().endswith(');')
        saved=json.loads(text[len('progressData('):].rstrip()[:-2])
        matches=[r for r in saved['runs'] if (r['program'],r['n'],r['order'])==('ftree.py',s['n'],s['order'])]
        assert len(matches)==1
        c,o=matches[0]['chance'],matches[0]['odds']
    else:
        c=chance.lindy_shown(prior,s['passes'][0][0],now);o=c['odds']
        c=dict(c,history=[r for r in c['history'] if r[0]<now])
        o=dict(o,exists=[r for r in o['exists'] if r[0]<now],curves=[r for r in o['curves'] if r[0]<now])
    assert all(row[0]<=now for rows in (c['history'],o['exists'],o['curves']) for row in rows)
    return copy.deepcopy(dict(since=c['since'],history=c['history'],exists=o['exists'],curves=o['curves']))


def attach(s, root, model_path, p_exists, now, cache):
    """Attach one current work forecast and immutable earlier chart points to a tracked survey.

    cache is dedicated to this target. Its legacy arrays are copied once from the actual page snapshot, and points
    retain the model hash, done and rate used when committed. No past prediction is fitted again with new inputs.
    """
    model,digest=load(root,model_path,f'{s["n"]}:{s["order"]}')
    active=s['state']=='running'
    w=formtree_work.read(root,[r['name'] for r in model['roots']],now=None,active=active)
    if 'legacy' not in cache:
        cache['legacy']=_legacy(s,root,p_exists,now)
    legacy=cache['legacy'];complete=all(r['complete'] for r in w['roots'])
    zero=dict(median=0.,lo=0.,hi=0.)
    if complete:
        c=dict(cpu_hours=None,rate=None,cores=None,hours=list(chance.HOURS),exists=0.,
               found=[0.]*len(chance.AHEAD),p=[0.]*len(chance.HOURS))
        to_go=zero if active else None
    elif active:
        samples=draws(model,w)
        forecast=chance.work(p_exists,samples['total'],w['done'],samples['rate']*3600,samples['weight'])
        c={k:forecast[k] for k in ('cpu_hours','rate','cores','hours','exists','found','p')}
        to_go=forecast['to_go']
    else:
        posterior=(cache['last']['chance']['exists'] if 'last' in cache else
                   legacy['exists'][-1][1] if legacy['exists'] else p_exists)
        c=dict(cpu_hours=None,rate=None,cores=None,hours=list(chance.HOURS),exists=posterior,
               found=[0.]*len(chance.AHEAD),p=[0.]*len(chance.HOURS))
        to_go=None
    current=dict(chance=c,model=digest,done=w['done'],rate=w['rate'])
    if active:
        points=history(cache.setdefault('points',[[now,copy.deepcopy(current)]]),copy.deepcopy(current),now)
        cache['shown']=copy.deepcopy(points)
    else:
        points=cache.get('shown',cache.get('points',[]))
    cache['last']=copy.deepcopy(current)
    measured=[(t,x['chance']) for t,x in points]
    odds=chance.odds(measured,now,c,'work')
    odds['exists']=copy.deepcopy(legacy['exists'])+odds['exists']
    odds['curves']=[copy.deepcopy(r) for r in legacy['curves'] if r[0]>=now-3600*chance.BACK]+odds['curves']
    shown=dict(c,since=legacy['since'],history=copy.deepcopy(legacy['history'])+chance.rows(measured))
    metadata=dict(source_time=w['source_time'],samples=model['samples'],
                  nodes=float(sum(np.asarray(r['blocks']).mean() for r in model['roots'])),
                  done=w['done'],rate=w['rate'],roots_done=sum(r['complete'] for r in w['roots']),
                  roots_total=len(w['roots']),model='importance',interval='conditional',
                  discrepancy_factor=math.exp(model['discrepancy_log_sd']),
                  root_discrepancy_factor=math.exp(model['root_log_sd']),rate_log_sd=model['rate_log_sd'])
    if to_go is not None:
        s['etas'][str(float(now))]=[to_go[k]/3600 for k in ('median','lo','hi')]
    return s | dict(to_go=to_go,display=s['display'] | dict(lindy=False,work_eta=metadata),chance=shown,odds=odds)
