"""Integration quals: measured work replaces Lindy consistently in every graph."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import progress
import formtree_work


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

    def survey(self,now=5200.):
        with (patch.object(progress,'HERE',str(self.root)),patch.object(progress,'CAMPAIGNS',{}),
              patch.object(progress,'EXHAUSTIVE',{(288,10):.01}),
              patch.object(formtree_work,'read',return_value=copy.deepcopy(self.work))):
            units=progress.journal_surveys(self.procs,now,self.cache,{}, {})
            return [s for _,thunk in units for s in thunk()][0]

    def test_work_model_replaces_lindy_and_drives_all_three_probability_graphs(self):
        # Replicata: registered frozen samples and exact checked work for a live target.
        # Expectata: a work ETA, with coherent existence/conditional/unconditional charts.
        # Resultata before: the model is ignored and every graph remains Lindy-based.
        s=self.survey();self.assertFalse(s['display']['lindy'])
        self.assertEqual(s['odds']['basis'],'work')
        self.assertNotEqual(s['to_go']['median'],s['so_far'])
        self.assertEqual(s['display']['work_eta']['done'],67)
        self.assertEqual(s['etas']['1600.0'],[1.,.2,3.])
        c=s['chance']
        for hour in (0,1,6,24,72):
            self.assertAlmostEqual(c['p'][c['hours'].index(hour)],c['exists']*c['found'][hour])
        self.assertGreater(len(c['history']),1)
        self.assertTrue(s['odds']['curves'])

    def test_twice_the_measured_speed_halves_the_remaining_time(self):
        # Replicata: identical work evidence, twice the aggregate wall throughput.
        # Expectata: every remaining-time quantile halves, without multiplying cores.
        a=self.survey();self.work['rate']*=2;b=self.survey(5260.)
        for k in ('median','lo','hi'):self.assertAlmostEqual(b['to_go'][k],a['to_go'][k]/2)

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


if __name__=='__main__':unittest.main()
