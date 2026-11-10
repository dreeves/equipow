"""Integration quals: measured work replaces Lindy consistently in every graph."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'searchwatch'))   # chance.py, formtree_eta.py, formtree_work.py, progress.py's directory since 2026-11-10 ([REF]); the root until then
import progress
import formtree_work
import chance


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'runs/models').mkdir(parents=True)
        (self.root/'source').write_text('frozen')
        self.model=dict(version=1,kind='formtree',target='288:10',seed=28810,log_bias=0.,
            discrepancy_log_sd=.75,root_log_sd=0.,rate_log_sd=.35,samples=32,
            checks={'source':hashlib.sha256(b'frozen').hexdigest()},
            roots=[dict(name='a',blocks=[[10]*8,[30]*8]),dict(name='b',blocks=[[100]*8,[300]*8])])
        # Complete provenance is fixture setup; the behavioral expectations stay unchanged.
        digest=hashlib.sha256(b'frozen').hexdigest()
        self.model.update(alpha=.5,provenance=dict(manifest_sha256=digest,samples_sha256=digest,
            seed_namespace='integration-qual',source='source'),calibration=[],assumptions=dict(
            discrepancy='qual',rate='qual',witness='qual',interval='qual'))
        for r in self.model['roots']:r['input_sha256']=digest
        self.path=self.root/'runs/models/288_10.json';self.path.write_text(json.dumps(self.model))
        self.start=dict(event='start',name='fixture',target='288:10',found=None,program='ftree.py',
            command='python3 ftree.py 288:10',cwd=str(self.root),adopted=True,pid=310,
            started='Wed Nov 4 00:00:00 2026',time=1000.,tracker=311)
        (self.root/'runs/fixture.jsonl').write_text(json.dumps(self.start)+'\n')
        self.work=dict(roots=[dict(name='a',done=17,complete=True),dict(name='b',done=50,complete=False)],
            done=67,rate=10.,source_time=5190.,source_age=10.,observed_at=5200.,finished=False,
            source={},driver={'pid':310})
        self.cache={'track_288_10_1000_etas':{'1600.0':[1.,.2,3.]}}
        self.procs=[(310,1,'S','python3 -B ftree.py 288:10')]

    def survey(self,now=5200.,prior=.01):
        with (patch.object(progress,'HERE',str(self.root)),patch.object(progress,'CAMPAIGNS',{}),
              patch.object(progress,'EXHAUSTIVE',{(288,10):prior}),
              patch.object(formtree_work,'read',return_value=copy.deepcopy(self.work))):
            units=progress.journal_surveys(self.procs,now,self.cache,{}, {})
            return [s for _,thunk in units for s in thunk()][0]

    def test_work_model_replaces_lindy_and_drives_the_p_exists_graph(self):
        # Replicata: registered frozen samples and exact checked work for a live target.
        # Expectata: a work ETA; odds of the prior, the history's origin (the run's start, 1000: a cold start has no
        # points plotted before it) and P(exists), now's alone and below the prior; no chance.
        # Spec change (Claude, 2026-11-06; dreeves: "everything here seems useless, kill it unless you have a good
        # argument for salvaging anything. the up-to-date probability that a bipartition exists is great."; then
        # "show the first probability graph, even though for 288:10 it's uninteresting. then kill everything below
        # that"): until then the model also drove a chance of a find within each hour and curves given existence
        # (chance, and odds' basis and curves), this qual's name ..._drives_all_three_probability_graphs.
        # Resultata before: the model is ignored and every graph remains Lindy-based.
        s=self.survey();self.assertFalse(s['display']['lindy'])
        self.assertNotIn('chance',s)
        self.assertEqual(set(s['odds']),{'prior','since','exists'})
        self.assertEqual((s['odds']['prior'],s['odds']['since']),(.01,1000.))
        self.assertEqual([t for t,_ in s['odds']['exists']],[5200.])
        self.assertLess(s['odds']['exists'][-1][1],.01)
        self.assertNotEqual(s['to_go']['median'],s['so_far'])
        self.assertEqual(s['display']['work_eta']['done'],67)
        self.assertEqual(s['etas']['1600.0'],[1.,.2,3.])

    def test_the_eta_and_the_bar_s_total_do_not_depend_on_the_prior(self):
        # Replicata (dreeves, 2026-11-06: "everything here seems useless, kill it unless you have a good argument for
        # salvaging anything. the up-to-date probability that a bipartition exists is great."; the coordinator's
        # analysis, which dreeves accepted: a witness of the exhaustive 288:10 proof is found only when the search
        # reaches it, so the ETA and the bar's total become the time and the work to exhaust the tree): the live
        # target surveyed under the prior P(exists) 0.01 and, from the same cache, under 0.5.
        # Expectata: the same to_go, the same ETA recorded at 5200 and the same work_eta total under both.
        # Resultata before: each moved with the prior, a witness's find uniform in the work left mixed in.
        cache=copy.deepcopy(self.cache)
        low=self.survey();self.cache=cache;high=self.survey(prior=.5)
        self.assertEqual(low['to_go'],high['to_go'])
        self.assertEqual(low['etas']['5200.0'],high['etas']['5200.0'])
        self.assertEqual(low['display']['work_eta']['total'],high['display']['work_eta']['total'])

    def test_p_exists_follows_the_prior(self):
        # Replicata: the live target surveyed under the prior P(exists) 0.01 and, from the same cache, under 0.5.
        # Expectata (dreeves, 2026-11-06: "the up-to-date probability that a bipartition exists is great"; then "after
        # the ETA graph, explicitly state the prior probability a bipartition exists"): each survey's odds carry its
        # prior; its P(exists) now is below that prior, and the one under 0.5 is the one under 0.01 moved to 0.5 by
        # Bayes's formula (chance.reprior: the likelihood of no find so far does not depend on the prior).
        # Not red first: P(exists) followed the prior before 2026-11-06's change too; this qual keeps it so.
        cache=copy.deepcopy(self.cache)
        low=self.survey()['odds'];self.cache=cache;high=self.survey(prior=.5)['odds']
        self.assertEqual((low['prior'],high['prior']),(.01,.5))
        self.assertLess(low['exists'][-1][1],.01);self.assertLess(high['exists'][-1][1],.5)
        self.assertAlmostEqual(high['exists'][-1][1],chance.reprior(low['exists'][-1][1],.01,.5),delta=1e-12)

    def test_twice_the_measured_speed_halves_the_remaining_time(self):
        # Replicata: identical work evidence, twice the aggregate wall throughput.
        # Expectata: every remaining-time quantile halves, without multiplying cores.
        a=self.survey();self.work['rate']*=2;b=self.survey(5260.)
        for k in ('median','lo','hi'):self.assertAlmostEqual(b['to_go'][k],a['to_go'][k]/2)

    def test_each_root_is_a_block_of_its_nodes(self):
        # Replicata: the live target (one run, running; root a complete at 17 nodes, root b with 50 checked), surveyed
        # with its model, whose prior holds 220 nodes in all (a's blocks' mean 20, b's 200); then with the run's process
        # gone (the search stopped short).
        # Expectata (dreeves, 2026-11-07: "remind me why we aren't doing the sea-of-dots visualization of that kind of
        # thing?", of the ETA's plunge as 288:10's root 8 finished; then "the words you're adding on the page are not
        # helping. it needs to just be clear from the visualization"): the sea holds no runs' dots but a block per root
        # in the model's order, a dot per 0.1 node (the power of 10 nearest 220 / progress.SEA_ROOT_DOTS): a's 170
        # settled; b's 500 settled, then the model's median of its nodes left in pending dots; once the search stopped,
        # b's 500 settled and one open dot. Keys '288:10 0' and '288:10 1'; the counts over every dot.
        # Resultata before: the sea held the runs' dots alone.
        # Spec change (Claude, 2026-11-08; dreeves, of the key that listed 288:10's blocks' "split 0" and "running 0",
        # which no block can be: "is that as dumb and wrong as it sounds?"): the sea names its own statuses, settled and
        # pending, or settled and open once the search stopped, its dots' digits indexing them, and counts them alone;
        # until then it used SEA_STATUSES's digits (pending '3') and counted all five.
        import formtree_eta,numpy as np
        self.assertEqual(progress.SEA_ROOT_DOTS,1000)
        s=self.survey()
        x=formtree_eta.draws(self.model,self.work,count=4096)
        left=x['trees'][:,1]-50;o=np.argsort(left)
        med=float(np.interp(.5,np.cumsum(x['weight'][o]),left[o]));k=round(med/.1)
        self.assertGreater(k,1)
        self.assertEqual(s['sea']['statuses'],['settled','pending'])
        self.assertEqual(s['sea']['groups'],['0'*170,'0'*500+'1'*k])
        self.assertEqual(s['sea']['keys'],['288:10 0','288:10 1'])
        self.assertEqual(s['sea']['counts'],dict(settled=670,pending=k))
        self.assertNotIn('roots',s)
        self.procs=[];stopped=self.survey(5260.)
        self.assertEqual(stopped['state'],'ended')
        self.assertEqual((stopped['sea']['statuses'],stopped['sea']['groups'],stopped['sea']['keys'],stopped['sea']['counts']),
                         (['settled','open'],['0'*170,'0'*500+'1'],['288:10 0','288:10 1'],dict(settled=670,open=1)))

    def test_lost_model_or_changed_frozen_source_fails_loudly(self):
        # Replicata: activate a model, then lose its file; separately alter its pinned source.
        # Expectata: refuse the survey, preserving the watcher's stale-data path, not Lindy.
        self.survey();self.path.unlink()
        with self.assertRaises(AssertionError):self.survey(5260.)
        self.path.write_text(json.dumps(self.model));(self.root/'source').write_text('changed')
        with self.assertRaises(AssertionError):self.survey(5260.)

    def test_failed_survey_does_not_record_an_unpublished_lindy_forecast(self):
        # Replicata: a good work forecast, a source-validation failure, then recovery.
        # Expectata: failure commits neither ETA nor probability history; recovery
        # retains old displayed points and adds only the successful new forecast.
        self.survey();before=copy.deepcopy(self.cache)
        (self.root/'source').write_text('changed')
        with self.assertRaises(AssertionError):self.survey(5260.)
        self.assertEqual(self.cache,before)
        (self.root/'source').write_text('frozen');s=self.survey(5320.)
        self.assertNotIn('5260.0',s['etas'])
        self.assertIn('5200.0',s['etas']);self.assertIn('5320.0',s['etas'])

    def test_288_10_s_prior_is_one_percent(self):
        # Replicata: the live target surveyed with progress.EXHAUSTIVE as configured (no patch), on a fresh copy of the
        # cache; and the same evidence under the prior 0.5 (survey's patch, the configured prior from 2026-11-06 19:47
        # until that night).
        # Expectata (dreeves, 2026-11-06: "after the ETA graph, explicitly state the prior probability a bipartition
        # exists. we can go back to 1% or whatever makes sense for 288:10."): 288:10's prior 0.01, which its odds
        # carry; its P(exists) now below 0.01: the posterior under 0.5 moved to 0.01 by Bayes's formula
        # (chance.reprior), as its stored history was moved back that night.
        # Spec change (the same request; until then this qual was test_the_published_p_exists_history_starts_at_one_half_and_falls,
        # after dreeves, 2026-11-06: "that sounds dumb. let's start with an ignorant prior (50%) and let it fall
        # naturally as the search progresses", of the prior 0.01): the prior 0.01 again, in place of 0.5.
        # Resultata before: the prior 0.5.
        cache=copy.deepcopy(self.cache)
        with (patch.object(progress,'HERE',str(self.root)),patch.object(progress,'CAMPAIGNS',{}),
              patch.object(formtree_work,'read',return_value=copy.deepcopy(self.work))):
            s=[s for _,thunk in progress.journal_surveys(self.procs,5200.,cache,{},{}) for s in thunk()][0]
        half=self.survey(prior=.5)['odds']['exists'][-1][1]
        o=s['odds']
        self.assertEqual((progress.EXHAUSTIVE[(288,10)],o['prior']),(.01,.01))
        self.assertLess(o['exists'][-1][1],.01)
        self.assertAlmostEqual(o['exists'][-1][1],chance.reprior(half,.5,.01),delta=1e-14)


if __name__=='__main__':unittest.main()
