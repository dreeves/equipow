"""Quals for tree-work uncertainty and immutable forecast history."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'searchwatch'))   # formtree_eta.py's directory since 2026-11-10 ([REF]); the root until then
import numpy as np
import formtree_eta as eta


def model():
    return dict(seed=28810, log_bias=0.0, discrepancy_log_sd=1.0,
                root_log_sd=0.0, rate_log_sd=0.35, roots=[dict(name='a', blocks=[[10]*8, [30]*8]),
                                        dict(name='b', blocks=[[100]*8, [300]*8])])


def work(a=0, b=0, complete=False):
    return dict(done=a+b, rate=10., roots=[dict(name='a', done=a, complete=complete),
                                          dict(name='b', done=b, complete=False)])


class Model(unittest.TestCase):
    def test_completed_root_updates_shared_normal_and_pending_floor(self):
        # Replicata: one exact root is twice its constant bootstrap base, with
        # prior shared log bias N(0,1) and local log SD 1; another root is censored.
        # Expectata: shared log bias is N(log(2)/2,1/2) before censoring; pending
        # survival uses that posterior, and completed roots draw no local error.
        from scipy.special import ndtr
        m=model();m['root_log_sd']=1.;m['roots'][0]['blocks']=[[10]*8,[10]*8]
        x=eta.draws(m,work(20,200,True),4096)
        mu=np.log(2)/2;sd=np.sqrt(.5)
        np.testing.assert_allclose(x['bias_mean'],mu)
        self.assertAlmostEqual(x['bias_sd'],sd)
        np.testing.assert_array_equal(x['proposal'][:,0],x['base'][:,0])
        survival=ndtr((mu-np.log(200/x['proposal'][:,1]))/sd)
        np.testing.assert_allclose(x['weight'],survival/survival.sum(),rtol=1e-12)
        self.assertTrue(np.all(x['trees'][:,1]>200))

    def test_completed_marginal_likelihood_reweights_bootstrap_rows(self):
        # Replicata: the exact completed root is 20; bootstrap bases 10,20,30
        # have masses1/4,1/2,1/4. Shared and local log variances are each1.
        # Expectata: row masses multiply the N(0,2) density at log(20/base),
        # even without any pending-root floor; fixing totals alone misses this.
        m=model();m['root_log_sd']=1.
        x=eta.draws(m,work(20,0,True),50000)
        base=np.array([10.,20.,30.]);prior=np.array([.25,.5,.25])
        density=np.exp(-np.log(20/base)**2/4)
        expected=prior*density/(prior@density)
        actual=np.array([x['weight'][x['base'][:,0]==b].sum() for b in base])
        np.testing.assert_allclose(actual,expected,atol=.01,rtol=0)
        np.testing.assert_allclose(x['bias_mean'],np.log(20/x['base'][:,0])/2)

    def test_zero_local_noise_one_exact_root_pins_shared_bias(self):
        # Replicata: one completed root and zero local noise; then two exact
        # roots under the same singular observation model.
        # Expectata: the first fixes B=17/base, with normal-prior density weights;
        # multiple zero-noise observations are explicitly unsupported, not jittered.
        m=model();x=eta.draws(m,work(17,0,True),1024)
        y=np.log(17/x['base'][:,0])
        np.testing.assert_allclose(x['trees'][:,1]/x['proposal'][:,1],np.exp(y))
        expected=np.exp(-y*y/2);expected/=expected.sum()
        np.testing.assert_allclose(x['weight'],expected)
        self.assertEqual(x['bias_sd'],0.)
        m['roots'].append(dict(name='c',blocks=[[100]*8,[300]*8]))
        w=dict(done=187,rate=10.,roots=[dict(name='a',done=17,complete=True),
               dict(name='b',done=170,complete=True),dict(name='c',done=0,complete=False)])
        with self.assertRaises(AssertionError):eta.draws(m,w)

    def test_exact_root_is_not_resampled_or_counted_twice(self):
        # Replicata: root a has closed at 17; b remains open.
        # Expectata: every total contains exactly 17 from a, not its sampled size.
        # Resultata: any resampled or duplicated completed work violates equality.
        x=eta.draws(model(), work(17, 50, True), 1024)
        np.testing.assert_array_equal(x['trees'][:,0], np.full(1024,17.))
        np.testing.assert_allclose(x['total'], 17+x['trees'][:,1])
        self.assertTrue(np.all(x['trees'][:,1]>50))

    def test_joint_lower_bounds_condition_shared_discrepancy(self):
        # Replicata: two unfinished roots have large observed lower bounds.
        # Expectata: all draws exceed both; one common factor scales both roots.
        x=eta.draws(model(), work(100, 2000), 2048)
        self.assertTrue(np.all(x['trees']>np.array([100,2000])))
        np.testing.assert_allclose(x['trees'][:,0]/x['base'][:,0],
                                   x['trees'][:,1]/x['base'][:,1])
        self.assertTrue(np.all(x['weight']>=0))
        self.assertAlmostEqual(float(x['weight'].sum()),1.)
        self.assertGreater(np.ptp(x['weight']),0)

    def test_local_discrepancy_allows_root_specific_misses(self):
        # Replicata: independent local log discrepancy .75 plus shared discrepancy,
        # conditioned on lower bounds in two roots.
        # Expectata: local factors vary separately, all lower bounds hold, and the
        # remaining factor is exactly shared. With local SD zero, proposals equal
        # the unchanged block-bootstrap bases.
        m=model();m['root_log_sd']=.75
        x=eta.draws(m,work(100,2000),2048)
        local=x['proposal']/x['base']
        self.assertGreater(np.std(np.log(local[:,0]/local[:,1])),.5)
        np.testing.assert_allclose(x['trees'][:,0]/x['proposal'][:,0],
                                   x['trees'][:,1]/x['proposal'][:,1])
        self.assertTrue(np.all(x['trees']>np.array([100,2000])))
        plain=eta.draws(model(),work(),1024)
        np.testing.assert_array_equal(plain['proposal'],plain['base'])

    def test_bootstrap_resamples_whole_blocks(self):
        # Replicata: two constant blocks, not sixteen independent paths.
        # Expectata: their bootstrap means can only be 10,20,30 (and 10x those).
        x=eta.draws(model(),work(),1024)
        self.assertEqual(set(x['base'][:,0]),{10,20,30})
        self.assertEqual(set(x['base'][:,1]),{100,200,300})

    def test_conditioning_weights_and_factor_cdf_match_exact_mixture(self):
        # Replicata: one pending root, base means 10/20/30 with masses 1/4,1/2,1/4,
        # and observed work 100. Expectata: each mass is weighted by P(B>100/base),
        # and the conditional factor CDF agrees with that exact finite mixture.
        # Resultata: uniform/inverted survival weights or reversed truncation fail.
        from scipy.special import ndtr
        m=model();m['roots']=m['roots'][:1]
        w=dict(done=100,rate=10.,roots=[dict(name='a',done=100,complete=False)])
        x=eta.draws(m,w,50000)
        base=np.array([10.,20.,30.]);prior=np.array([.25,.5,.25])
        threshold=100/base;sf=ndtr(-np.log(threshold))
        expected=prior*sf/(prior@sf)
        observed=np.array([x['weight'][x['base'][:,0]==b].sum() for b in base])
        np.testing.assert_allclose(observed,expected,atol=.01,rtol=0)
        factor=x['trees'][:,0]/x['base'][:,0]
        expected_cdf=float(prior@np.maximum(ndtr(np.log(5))-ndtr(np.log(threshold)),0)/(prior@sf))
        self.assertAlmostEqual(float(x['weight'][factor<=5].sum()),expected_cdf,delta=.01)

    def test_reproducible_draws_keep_rate_units(self):
        # Replicata: repeat an unchanged measurement and then double throughput.
        # Expectata: no random flicker; only rate doubles, in nodes/second.
        a=eta.draws(model(),work(),1024);b=eta.draws(model(),work(),1024)
        for key in a: np.testing.assert_array_equal(a[key],b[key])
        w=work();w['rate']*=2;c=eta.draws(model(),w,1024)
        np.testing.assert_array_equal(a['total'],c['total'])
        np.testing.assert_allclose(c['rate'],2*a['rate'])

    def test_invalid_geometry_or_work_is_refused(self):
        # Replicata: mismatched root order, invalid block, wrong done sum/rate.
        # Expectata: explicit failure; no repaired input or fallback forecast.
        cases=[]
        m=model();m['roots'][0]['name']='x';cases.append((m,work()))
        m=model();m['roots'][0]['blocks'][0][0]=float('nan');cases.append((m,work()))
        w=work();w['done']=1;cases.append((model(),w))
        w=work();w['rate']=0;cases.append((model(),w))
        for m,w in cases:
            with self.subTest(case=(m,w)),self.assertRaises(AssertionError):eta.draws(m,w)

    def test_history_preserves_old_forecasts_and_current_curve(self):
        # Replicata: two old model points and a current estimate within cadence.
        # Expectata: old values stay exact; current is drawn but not committed yet.
        p=[[100.,{'exists':.01}],[1000.,{'exists':.009}]];saved=copy.deepcopy(p)
        current={'exists':.008}
        shown=eta.history(p,current,1100.)
        self.assertEqual(p,saved);self.assertEqual(shown,saved+[[1100.,current]])
        eta.history(p,current,1900.)
        self.assertEqual(p,saved+[[1900.,current]])
        with self.assertRaises(AssertionError):eta.history(p,current,1800.)


class Attachment(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        source=self.root/'source';source.write_bytes(b'fixed input')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        self.model=model() | dict(version=1,kind='formtree',target='288:10',samples=32,alpha=.5,
            checks={'source':digest},provenance=dict(manifest_sha256=digest,samples_sha256=digest,
            seed_namespace='qual',source='source'),calibration=[],assumptions=dict(
            discrepancy='qual',rate='qual',witness='qual',interval='qual'))
        for r in self.model['roots']:r['input_sha256']=digest
        self.path=self.root/'model.json';self.path.write_text(json.dumps(self.model))
        self.s=dict(n=288,order=10,program='ftree.py',state='running',passes=[[1000,2000]],
                    to_go=dict(median=1000,lo=10,hi=19000),etas={'1500.0':[1,2,3],'2000.0':[4,5,6]},
                    display=dict(lindy=True,tracked=True))
        # the page's snapshot, in the odds' form of 2026-11-06 (its chance and curves until then)
        self.old=dict(program='ftree.py',n=288,order=10,odds=dict(prior=.01,since=1000.,exists=[[1500.,.01],[1900.,.009]]))
        (self.root/'pagedata').mkdir()   # the page's data files' directory since 2026-11-10 ([REF])
        (self.root/'pagedata'/'progress.js').write_text('progressData('+json.dumps({'runs':[self.old]})+');\n')
        self.w=work(5,50);self.w.update(source_time=1990.,source_age=10.)

    def test_load_binds_schema_samples_and_sources(self):
        # Replicata: valid stored model, then mismatched count/target/hash/version.
        # Expectata: original loads with its byte hash; each invalid variant fails.
        m,digest=eta.load(self.root,self.path)
        self.assertEqual(m,self.model)
        self.assertEqual(digest,hashlib.sha256(self.path.read_bytes()).hexdigest())
        for field,value in [('samples',33),('target','432:12'),('version',2),('kind','other')]:
            bad=self.model|{field:value};self.path.write_text(json.dumps(bad))
            with self.subTest(field=field),self.assertRaises(AssertionError):eta.load(self.root,self.path)
        self.path.write_text(json.dumps(self.model));(self.root/'source').write_bytes(b'changed')
        with self.assertRaises(AssertionError):eta.load(self.root,self.path)

    def test_attach_keeps_old_arrays_and_only_replaces_current_eta(self):
        # Replicata: actual saved legacy arrays plus two changed model snapshots.
        # Expectata: no retroactive recomputation; only current ETA is replaced.
        # Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good
        # argument for salvaging anything. the up-to-date probability that a bipartition exists is great."): the saved
        # P(exists) points and their origin kept, and no chance or curves beside them, which went with their graphs.
        cache={};old=copy.deepcopy(self.old)
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            got=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,cache)
        self.assertEqual(got['etas']['1500.0'],[1,2,3]);self.assertNotEqual(got['etas']['2000.0'],[4,5,6])
        self.assertFalse(got['display']['lindy'])
        self.assertNotIn('chance',got)
        self.assertEqual(got['odds']['exists'][:2],old['odds']['exists'])
        self.assertEqual((got['odds']['prior'],got['odds']['since']),(.01,old['odds']['since']))
        first=copy.deepcopy(cache['points'])
        (self.root/'pagedata'/'progress.js').write_text('invalid on purpose')
        self.model['log_bias']=.5;self.path.write_text(json.dumps(self.model))
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            again=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2100.,cache)
        self.assertEqual(cache['points'],first)
        self.assertEqual(again['odds']['exists'][:2],old['odds']['exists'])
        # Spec extension, dreeves2026-11-06: learned uncertainty and [BUL] expose
        # the model interval's coverage and actual posterior/sampling diagnostics.
        # Spec extension (Claude, 2026-11-06; dreeves: "should that progress bar be measuring amount of work, not
        # time? ... we can still have a 90% CI for amount of work remaining, right?"): total, the work bar's interval.
        self.assertEqual(set(again['display']['work_eta']),{'source_time','samples','nodes','done','rate',
             'roots_done','roots_total','model','interval','discrepancy_factor','root_discrepancy_factor','rate_log_sd',
             'coverage','root_log_sd_posterior','effective_samples','forecast_samples','total'})

    def test_learned_scatter_schema_and_current_uncertainty_are_published(self):
        # Replicata: a v2 prior over root scatter, retaining frozen search inputs.
        # Expectata: a validated model, normalized posterior summary and explicit
        # central80% interpretation; changing only a version number remains invalid.
        # Spec change (Claude, 2026-11-06): central 80% (chance.COVERAGE 0.8, the work band (0.1, 0.9)) after the
        # coordinator's calibration study (scratch/calibration-20261106); central 90% before.
        self.model.update(version=2,root_log_sd=.75,root_log_sd_uncertainty=.5)
        self.path.write_text(json.dumps(self.model))
        loaded,_=eta.load(self.root,self.path)
        self.assertEqual(loaded,self.model)
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            result=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,{})
        meta=result['display']['work_eta']
        self.assertEqual(meta['coverage'],.8)
        self.assertEqual(meta['forecast_samples'],65536)
        self.assertGreater(meta['effective_samples'],100)
        scatter=meta['root_log_sd_posterior']
        self.assertLess(scatter['lo'],scatter['median'])
        self.assertLess(scatter['median'],scatter['hi'])
        self.assertGreater(scatter['lo'],0)
        for value in (-1.,float('nan'),float('inf')):
            self.model['root_log_sd_uncertainty']=value
            self.path.write_text(json.dumps(self.model))
            with self.subTest(value=value),self.assertRaises(AssertionError):eta.load(self.root,self.path)

    def test_total_work_is_the_forecast_s_and_exact_once_complete(self):
        # Replicata (dreeves, 2026-11-06: "should that progress bar be measuring amount of work, not time? ... we can
        # still have a 90% CI for amount of work remaining, right?"): the live fixture; the same search frozen; then
        # every root complete, the search running and ended.
        # Expectata: work_eta's total, the nodes checked when the tree is exhausted, {median, lo, hi}: while it runs,
        # chance.work's total on the same draws, done at most its lo, lo below median below hi; frozen, none (a stopped
        # search makes no forecast); complete, exactly done at all three, running or ended.
        # Resultata before: work_eta had no total (KeyError).
        # Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good
        # argument for salvaging anything. the up-to-date probability that a bipartition exists is great."; the
        # coordinator's analysis, which dreeves accepted: the ETA and the bar's total are the time and the work to
        # exhaust the tree): chance.work's total is the work then, in place of the work when the search ends, by a
        # witness or with the tree exhausted.
        cache={}
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            live=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,cache)
        x=eta.draws(json.loads(self.path.read_text()),self.w,4096)
        want=eta.chance.work(.01,x['total'],self.w['done'],x['rate']*3600,x['weight'])['total']
        total=live['display']['work_eta']['total']
        self.assertEqual(total,want)
        self.assertLessEqual(self.w['done'],total['lo'])
        self.assertLess(total['lo'],total['median']);self.assertLess(total['median'],total['hi'])
        frozen=copy.deepcopy(self.s);frozen['state']='frozen'
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            self.assertIsNone(eta.attach(frozen,self.root,self.path,.01,2100.,cache)['display']['work_eta']['total'])
        for r in self.w['roots']:r['complete']=True
        for state in ('running','ended'):
            s=copy.deepcopy(self.s);s['state']=state
            with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
                got=eta.attach(s,self.root,self.path,.01,2200.,cache)['display']['work_eta']['total']
            self.assertEqual(got,dict(median=55.,lo=55.,hi=55.))

    def test_numerically_concentrated_posterior_is_not_published(self):
        # Replicata: a v2 importance proposal leaves only one effective draw.
        # Expectata: refuse numerical false precision before committing a forecast.
        self.model.update(version=2,root_log_sd=.75,root_log_sd_uncertainty=.5)
        self.path.write_text(json.dumps(self.model))
        samples=dict(total=np.array([100.,200.]),rate=np.array([10.,10.]),
                     weight=np.array([1.,0.]),root_log_sd=np.array([.5,.8]))
        cache={}
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w), \
             mock.patch.object(eta,'draws',return_value=samples),self.assertRaises(AssertionError):
            eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,cache)
        self.assertNotIn('points',cache)

    def test_proposals_double_until_the_effective_draws_reach_the_floor(self):
        # Replicata: a v2 model whose draws are made up, their effective count 1/80 of the proposals (819 of 65,536);
        # then one whose effective count is 1/10,000 of them.
        # Expectata (dreeves, 2026-11-07, of 288:10's ETA gone stale at 860 effective draws of 65,536: "can-opener
        # question?"): the proposals doubled until the effective draws reach the floor of 1,000, the forecast made from
        # those, 131,072 here; with a floor out of reach by PROPOSALS_CAP (2^20), refused as before, after drawing at
        # 65,536 and each doubling up to the cap.
        # Resultata before: one draw of 65,536, refused at 819.
        self.model.update(version=2,root_log_sd=.75,root_log_sd_uncertainty=.5)
        self.path.write_text(json.dumps(self.model))
        def made(per):
            calls=[]
            def fake(model,work,count):
                calls.append(count);k=count//per;weight=np.zeros(count);weight[:k]=1/k
                return dict(total=np.linspace(100.,200.,count),rate=np.full(count,10.),weight=weight,root_log_sd=np.linspace(.4,.9,count))
            return fake,calls
        fake,calls=made(80)
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w),mock.patch.object(eta,'draws',side_effect=fake):
            meta=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,{})['display']['work_eta']
        self.assertEqual(calls,[65536,131072])
        self.assertEqual((meta['forecast_samples'],round(meta['effective_samples'])),(131072,1638))
        fake,calls=made(10000)
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w),mock.patch.object(eta,'draws',side_effect=fake), \
             self.assertRaises(AssertionError):
            eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,{})
        self.assertEqual(calls,[65536*2**k for k in range(5)])

    def test_paused_preserves_posterior_and_terminal_is_zero_remaining(self):
        # Replicata: active snapshot, paused with no throughput, then all roots closed.
        # Expectata: paused, last posterior/history retained, now's point that posterior;
        # terminal has zero remaining and existence zero, without sampling again.
        # Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good
        # argument for salvaging anything. the up-to-date probability that a bipartition exists is great."): no
        # chance of a future find (zero while paused), which went with its graphs.
        cache={}
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            live=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,cache)
        saved_points=copy.deepcopy(cache['points'])
        self.w['rate']=0;paused=copy.deepcopy(self.s);paused['state']='frozen'
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w),mock.patch.object(eta,'draws',side_effect=AssertionError):
            stopped=eta.attach(paused,self.root,self.path,.01,2100.,cache)
        self.assertIsNone(stopped['to_go']);self.assertEqual(stopped['odds']['exists'][-1],[2100.,live['odds']['exists'][-1][1]])
        self.assertEqual(stopped['odds']['exists'][:-1],live['odds']['exists'])
        for r in self.w['roots']:r['complete']=True
        paused['state']='ended'
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w),mock.patch.object(eta,'draws',side_effect=AssertionError):
            ended=eta.attach(paused,self.root,self.path,.01,3000.,cache)
        # Spec clarification, root 2026-11-04: an inactive terminal survey has no
        # new ETA point beyond its ended pass; its current probability tail is zero.
        self.assertIsNone(ended['to_go'])
        self.assertNotIn('3000.0',ended['etas'])
        self.assertEqual(cache['points'],saved_points)
        self.assertEqual(ended['odds']['exists'][-2][0],2000.)
        self.assertEqual(ended['odds']['exists'][-1],[3000.,0.])

    def test_live_reader_uses_its_observation_clock_and_active_completion_is_zero(self):
        # Replicata: the source may append after the watcher's earlier epoch;
        # then a still-active survey observes all roots complete.
        # Expectata: reader measures time after its frozen reads; zero ETA is
        # recorded only for the active survey, within its still-open pass.
        cache={}
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w) as read:
            eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,cache)
        self.assertIsNone(read.call_args.kwargs.get('now'))
        for r in self.w['roots']:r['complete']=True
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            ended=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2100.,cache)
        self.assertEqual(ended['to_go'],dict(median=0.,lo=0.,hi=0.))
        self.assertEqual(ended['etas']['2100.0'],[0.,0.,0.])

    def test_cold_fixture_has_no_points_before_activation(self):
        # Replicata: no progress.js exists for this fixture.
        # Expectata: no legacy points, as nothing was plotted before; their origin the run's start, 1000; the odds' one
        # point now's, work-based.
        # Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good
        # argument for salvaging anything. the up-to-date probability that a bipartition exists is great."): until
        # then the cold start took Lindy points from before now, from its former Lindy model (chance.lindy_shown, gone
        # with the graphs it drew), and the odds a basis, work; this qual test_cold_fixture_seeds_legacy_only_before_activation.
        (self.root/'pagedata'/'progress.js').unlink();cache={}
        with mock.patch.object(eta.formtree_work,'read',return_value=self.w):
            got=eta.attach(copy.deepcopy(self.s),self.root,self.path,.01,2000.,cache)
        self.assertEqual(cache['legacy'],dict(since=1000,exists=[]))
        self.assertEqual(got['odds']['since'],1000)
        self.assertEqual([t for t,_ in got['odds']['exists']],[2000.])


if __name__=='__main__':unittest.main()
