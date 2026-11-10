"""Replicata: frozen verdict/log fixtures. Expectata: exact expanded work and wall-rate provenance."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'searchwatch'))   # formtree_work.py's directory since 2026-11-10 ([REF]); the root until then
import formtree_work as fw

def verdict(name,nodes,spills):
    return dict(start=name,nodes=nodes,spills=spills,ok=True,open=0)

def line(t,done,nodes,rejected=0):
    return (f'[{t}s] done {done}, left 1; nodes {nodes:.4g}, closed {nodes:.4g}, OPEN 0, LPs 10, CPU 1.0 h, '
            f'certificates 10, REJECTED {rejected}, wrong names 0, python 0 sampled 0 differ, free 100.0 GB, overdue 0')

class Quals(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.state=self.root/'scratch/formtree/run288v';self.state.mkdir(parents=True)
        self.path=self.state/'verdicts.jsonl';self.log=self.state.parent/'run288v.log'
        self.rows=[verdict('a',3,['c']),verdict('c',4,[]),verdict('b',10,[])]
        self.names=['a','b'];self.progress=[line(100,1,7),line(200,2,17)]
        self.write()
    def write(self):
        self.path.write_text(''.join(json.dumps(v)+'\n' for v in self.rows))
        self.log.write_text('top of 288:10: {}\n'+f'{len(self.names)} start nodes; 1 tasks to run; 3 nodes done\n'+'\n'.join(self.progress)+'\n')
        os.utime(self.path,(1001,1001));os.utime(self.log,(1000,1000))
    def test_exact_resumed_work_and_wall_rate(self):
        r=fw.read(self.root,self.names,1100)
        self.assertEqual(r['roots'],[dict(name='a',done=6,complete=True),dict(name='b',done=10,complete=True)])
        self.assertEqual((r['done'],r['rate'],r['retained_verdicts'],r['log_done']),(16,.1,1,16))
        self.assertEqual((r['source_time'],r['source_age'],r['log_elapsed']),(1000,100,200))
    def test_rate_weights_recent_hours_exponentially(self):
        # Spec (dreeves, 2026-11-07, of the ETA's spikes whenever other work borrowed the search's cores for an hour:
        # "maybe 3 hours at least, or just do an exponentially weighted moving average of rates or whatever seems
        # elegant"): the rate is the throughput over the current driver's whole log, each interval between progress
        # lines weighted by exp(-age / 3 h), its age from the last line to the interval's middle.  Here an hour without
        # progress, then 10 nodes in the next hour.  Before: the last hour's aggregate, 10 / 3600.
        self.progress=[line(100,1,7),line(3700,1,7),line(7300,2,17)];self.write()
        r=fw.read(self.root,self.names,1100)
        older,newer=math.exp(-5400/10800),math.exp(-1800/10800)
        self.assertAlmostEqual(r['rate'],10*newer/(3600*(older+newer)),places=12)
    def test_partial_verdict_tail_is_retained_as_provenance(self):
        with self.path.open('ab') as f:f.write(b'{"start":')
        r=fw.read(self.root,self.names,1100)
        self.assertEqual(r['done'],16)
        self.assertEqual(r['source']['verdicts']['trailing_bytes'],9)
    def test_pending_root_is_not_exact_zero(self):
        self.names.append('d');self.write();r=fw.read(self.root,self.names,1100)
        self.assertEqual(r['roots'][-1],dict(name='d',done=0,complete=False))
    def test_duplicate_rejected_or_open_refused(self):
        for changed in ('duplicate','rejected','open','python'):
            with self.subTest(changed=changed):
                self.rows=[verdict('a',3,['c']),verdict('c',4,[]),verdict('b',10,[])]
                if changed=='duplicate':self.rows.append(self.rows[0])
                if changed=='rejected':self.rows[0]['ok']=False
                if changed=='open':self.rows[0]['open']=1
                if changed=='python':self.rows[0]['py']=False
                self.write()
                with self.assertRaises(AssertionError):fw.read(self.root,self.names,1100)
    def test_orphan_or_shared_child_refused(self):
        self.rows.append(verdict('orphan',1,[]));self.write()
        with self.assertRaises(AssertionError):fw.read(self.root,self.names,1100)
        self.rows=self.rows[:-1];self.rows[-1]['spills']=['c'];self.write()
        with self.assertRaises(AssertionError):fw.read(self.root,self.names,1100)
    def test_stale_running_source_refused(self):
        self.names.append('d');self.write()
        with self.assertRaises(AssertionError):fw.read(self.root,self.names,2201)
    def test_completed_source_can_be_old(self):
        self.assertEqual(fw.read(self.root,self.names,3000)['done'],16)
    def test_wrong_logged_count_or_rejection_refused(self):
        for bad in (line(200,2,18),line(200,2,17,1)):
            self.progress=[line(100,1,7),bad];self.write()
            with self.assertRaises(AssertionError):fw.read(self.root,self.names,1100)
    def test_nonmonotone_log_or_missing_rate_refused(self):
        for progress in ([line(200,2,17),line(100,1,7)],[line(100,1,7)]):
            self.progress=progress;self.write()
            with self.assertRaises(AssertionError):fw.read(self.root,self.names,1100)
    def test_current_driver_record_is_metadata_not_liveness(self):
        d=self.root/'runs';d.mkdir();rec=dict(event='start',program='ftree.py',target='288:10',pid=123,time=500,started='example',command='python ftree.py',cwd=str(self.root))
        (d/'one.jsonl').write_text(json.dumps(rec)+'\n')
        r=fw.read(self.root,self.names,1100)
        self.assertEqual(r['driver']['pid'],123);self.assertFalse(r['driver']['record_ended'])
    def test_live_observation_time_follows_frozen_source_reads(self):
        original=fw._prefix;seen=[]
        def capture(path):
            result=original(path);seen.append(path);return result
        def clock():
            self.assertGreaterEqual(len(seen),2)
            return 1100
        with patch.object(fw,'_prefix',capture),patch('time.time',clock):
            r=fw.read(self.root,self.names,now=None)
        self.assertEqual((r['observed_at'],r['source_age']),(1100,100))
    def test_explicit_future_source_time_is_rejected(self):
        with self.assertRaises(AssertionError):fw.read(self.root,self.names,900)
    def test_inactive_zero_rate_and_stale_work_are_readable(self):
        self.names.append('d');self.progress=[line(100,1,7),line(200,1,7)];self.write()
        r=fw.read(self.root,self.names,3000,active=False)
        self.assertEqual((r['done'],r['rate'],r['source_age']),(16,0,2000))
        self.assertFalse(r['roots'][-1]['complete'])
    def test_active_zero_rate_remains_rejected(self):
        self.progress=[line(100,1,7),line(200,1,7)];self.write()
        with self.assertRaises(AssertionError):fw.read(self.root,self.names,1100)
    def test_inactive_still_rejects_future_source_time(self):
        with self.assertRaises(AssertionError):fw.read(self.root,self.names,900,active=False)

if __name__=='__main__':unittest.main()
