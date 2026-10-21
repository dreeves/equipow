"""Quals for the exact proof stream and resumable focused searches."""
import gzip,json,tempfile,unittest,itertools,fcntl
from pathlib import Path
from unittest.mock import patch
import focus,certbb,mstar

class FocusQuals(unittest.TestCase):
    def test_production_uses_the_verified_stronger_cases(self):
        # Replicata: prepare the two production proof searches.
        # Expectata: 480 uses the 195 mod-8 representatives and derivative
        # equation; 672 uses both parents with the forced balanced mod-4 row.
        a, cases480 = focus.prepare(480, 14)
        b, cases672 = focus.prepare(672, 13)
        self.assertEqual((len(cases480), len(cases672)), (195, 2))
        self.assertEqual((a.order, len(a.W), b.order), (14, 15, 13))
        self.assertTrue(all(dict(c)[8] for c in cases480))
        self.assertTrue(all(dict(c)[4] == (84,) * 4 for c in cases672))

    def test_profiles_cover_both_targets(self):
        # Replicata: generate necessary profiles without assuming symmetry.
        # Expectata: both full sign problems have the two documented cases.
        for n,m in ((480,14),(672,13)):
            moments,cases=focus.prime_prepare(n,m)
            self.assertEqual(len(cases),2)
            self.assertEqual([M for M,_ in cases[0]],[2,3,5,7])
            self.assertEqual(cases[0][0][1],(n//4,n//4))
    def test_known_witnesses_survive_exact_rows_and_lp(self):
        # Replicata: checked constructions at both target lengths.
        # Expectata: all exact equations hold and the relaxation accepts them.
        for n,m in ((480,12),(672,11)):
            a=mstar.build(n);self.assertEqual(mstar.order(a),m)
            moments=focus.moments(n,m)
            x=[(s+1)//2 for s in a]
            choice=tuple((M,tuple(sum(x[r::M])for r in range(M)))for M in (2,3,5,7))
            self.assertIsNone(certbb.point_certificate(certbb.node_rows(moments,choice),x))
            lp=certbb.Lp(moments,(2,3,5,7));lp.set_counts(choice)
            self.assertEqual(lp.solve([0]*n,[1]*n)[0],'Optimal')
    def test_budget_resume_replays_binary_proof(self):
        # Replicata: 2x0+2x1=1, one LP allowed before a resumed pass.
        # Expectata: budget leaves an open frontier; exact replay then proves exclusion.
        toy=(certbb.Moments(((2,2),),(1,)),((),))
        with tempfile.TemporaryDirectory()as tmp,patch.object(focus,'prepare',return_value=toy):
            path=Path(tmp)
            self.assertEqual(focus.search(path,path/'journal',2,1,1,30),'budget')
            first=focus.replay(path,*toy,focus.fingerprint())
            self.assertGreater(len(first.frontier),0)
            self.assertEqual(focus.search(path,path/'journal',2,1,100,30),'excluded')
            done=focus.replay(path,*toy,focus.fingerprint())
            self.assertEqual(done.completed,[0]);self.assertEqual(done.frontier,[])
            self.assertGreater(done.split,0);self.assertGreater(done.closed,0)
            self.assertEqual(focus.search(path,path/'journal',2,1,100,30),'excluded')
            events=[json.loads(line)for line in (path/'journal').read_text().splitlines()]
            self.assertTrue(all(e.get('outcome')is None for e in events if e['event']=='update'))
            self.assertEqual([e['event']for e in events[-2:]],['session','finish'])
            self.assertEqual(done.lp,done.split+done.closed)
    def test_saved_witness_is_checked_on_replay(self):
        # Replicata: x0+x1=1 has an immediate exact 0/1 witness.
        # Expectata: the saved witness is checked independently on replay.
        toy=(certbb.Moments(((1,1),),(1,)),((),))
        with tempfile.TemporaryDirectory()as tmp,patch.object(focus,'prepare',return_value=toy):
            path=Path(tmp)
            self.assertEqual(focus.search(path,path/'journal',2,1,10,30),'witness')
            result=focus.replay(path,*toy,focus.fingerprint())
            self.assertEqual(sum(result.witness),1)
    def test_corrupt_committed_chunk_fails_loudly(self):
        # Replicata: truncate an atomically committed proof chunk.
        # Expectata: replay raises; it never treats the damaged proof as progress.
        toy=(certbb.Moments(((2,2),),(1,)),((),))
        with tempfile.TemporaryDirectory()as tmp,patch.object(focus,'prepare',return_value=toy):
            path=Path(tmp);focus.search(path,path/'journal',2,1,1,30)
            chunk=next(path.glob('chunk-*.json.gz'));chunk.write_bytes(chunk.read_bytes()[:12])
            with self.assertRaises((EOFError,OSError)):focus.replay(path,*toy,focus.fingerprint())
    def test_witness_at_checkpoint_boundary_is_committed_once(self):
        toy=(certbb.Moments(((1,1),),(1,)),((),))
        clock=itertools.count(0,6)
        with tempfile.TemporaryDirectory()as tmp,patch.object(focus,'prepare',return_value=toy),patch.object(focus.time,'monotonic',side_effect=lambda:next(clock)):
            path=Path(tmp)
            self.assertEqual(focus.search(path,path/'journal',2,1,10,1000),'witness')
            self.assertEqual(len(list(path.glob('chunk-*.json.gz'))),1)
            self.assertIsNotNone(focus.replay(path,*toy,focus.fingerprint()).witness)
    def test_duplicate_runner_is_rejected(self):
        with tempfile.TemporaryDirectory()as tmp:
            path=Path(tmp)
            with open(path/'run.lock','a')as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):focus.search(path,path/'journal',480,14,1,1)
    def test_forged_certificate_fails_exact_replay(self):
        toy=(certbb.Moments(((2,2),),(1,)),((),))
        with tempfile.TemporaryDirectory()as tmp,patch.object(focus,'prepare',return_value=toy):
            path=Path(tmp);focus.search(path,path/'journal',2,1,100,30)
            chunk=next(path.glob('chunk-*.json.gz'))
            with gzip.open(chunk,'rt')as stream:data=json.load(stream)
            leaf=next(r for r in data['records']if r['token'][0]=='L')
            leaf['token'][1]=[0]*len(leaf['token'][1])
            with gzip.open(chunk,'wt')as stream:json.dump(data,stream)
            with self.assertRaises(certbb.ProofError):focus.replay(path,*toy,focus.fingerprint())
    def test_changed_code_fails_loudly(self):
        toy=(certbb.Moments(((2,2),),(1,)),((),))
        with tempfile.TemporaryDirectory()as tmp,patch.object(focus,'prepare',return_value=toy):
            path=Path(tmp);focus.search(path,path/'journal',2,1,1,30)
            with self.assertRaises(AssertionError):focus.replay(path,*toy,'wrong')

if __name__=='__main__':unittest.main()
