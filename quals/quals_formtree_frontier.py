#!/usr/bin/env python3
"""Quals for rebasing a form-tree ETA on a frozen unfinished frontier."""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'searchwatch'))


def verdict(name, n, spills=()):
    return dict(start=name, nodes=n, spills=list(spills), ok=True, open=0)


def encoded(rows): return b''.join(json.dumps(r).encode()+b'\n' for r in rows)


def fixture():
    original = dict(kind='formtree', seed=1, log_bias=0., discrepancy_log_sd=1e-9,
                    rate_log_sd=0., root_log_sd=0., root_log_sd_uncertainty=0.,
                    roots=[dict(name='a', blocks=[[1000.]*8]*8)], provenance={}, assumptions='qual')
    prefix = encoded([verdict('a', 12, ['b', 'c'])])
    checkpoint = dict(target='16:4', finished=1, done=10, prefix_bytes=len(prefix),
                      prefix_sha256=hashlib.sha256(prefix).hexdigest(), roots=['a'],
                      groups=[dict(name='g', members=['b', 'c'])])
    model = dict(original, roots=[dict(name='g', blocks=[[1000.]*2]*8)], checkpoint=checkpoint)
    return original, model, prefix


class Frontier(unittest.TestCase):
    # Replicata are the setup in each qual. Expectata are stated below;
    # a failed assertion supplies resultata. All additions are red before implementation.
    def test_original_models_keep_their_accounting(self):
        # An ordinary root model still counts the same prefix, at offset zero.
        import formtree_frontier as f
        original, _, prefix = fixture()
        state = f.observed(original, prefix)
        self.assertEqual(state['offset'], 0)
        self.assertEqual(state['roots'], [dict(name='a', done=10, complete=False)])
        self.assertEqual(set(state['waiting']), {'b', 'c'})

    def test_only_suffix_work_is_assigned_to_new_groups(self):
        # b spills d, c closes: old work10, new group work4+3, d is pending.
        import formtree_frontier as f
        _, model, prefix = fixture()
        state = f.observed(model, prefix+encoded([verdict('b',5,['d']), verdict('c',3)]))
        self.assertEqual(state, dict(offset=10, roots=[dict(name='g',done=7,complete=False)],
                                     waiting=['d'], finished=3))

    def test_group_finishes_only_when_every_member_subtree_finishes(self):
        # One descendant remains under b despite both initial task verdicts existing.
        import formtree_frontier as f
        _, model, prefix = fixture()
        data = prefix+encoded([verdict('b',5,['d']),verdict('c',3),verdict('d',2)])
        state = f.observed(model,data)
        self.assertEqual(state['roots'], [dict(name='g',done=9,complete=True)])
        self.assertEqual(state['waiting'], [])
        self.assertEqual(state['offset']+state['roots'][0]['done'], 19)

    def test_checkpoint_tampering_and_wrong_partition_fail(self):
        # Prefix bytes, node count, and disjoint complete frontier membership are asserted.
        import formtree_frontier as f
        _, model, prefix = fixture()
        for key, value in [('done',11),('finished',2),('prefix_bytes',len(prefix)-1),
                           ('prefix_sha256','0'*64),('roots',['x']),
                           ('groups',[dict(name='g',members=['b'])]),
                           ('groups',[dict(name='g',members=['b','c','c'])])]:
            m=copy.deepcopy(model); m['checkpoint'][key]=value
            with self.assertRaises(AssertionError): f.observed(m,prefix)
        with self.assertRaises(AssertionError): f.observed(model,prefix.replace(b'12',b'13'))

    def test_wrong_suffix_and_bad_verdicts_fail(self):
        # Orphan work or a rejected/open task cannot become ETA progress.
        import formtree_frontier as f
        _, model, prefix = fixture()
        for v in (verdict('x',2),dict(verdict('b',2),ok=False),dict(verdict('b',2),open=1)):
            with self.assertRaises(AssertionError): f.observed(model,prefix+encoded([v]))

    def test_offset_changes_totals_but_not_remaining_work(self):
        # Of a1000-node new forest,400 done, plus100 old nodes:1100 total,500 done,600 left.
        import formtree_eta as eta
        original, _, _ = fixture()
        state=[dict(name='a',done=400,complete=False)]; points=[(0,0),(250,500)]
        e=eta.estimate(original,state,points,.5,1,3,offset=100)
        self.assertEqual(e['done'],500)
        self.assertAlmostEqual(e['rate'],2)
        self.assertAlmostEqual(e['total']['median'],1100,places=3)
        self.assertAlmostEqual(e['to_go']['median'],300,places=3)
        self.assertAlmostEqual(e['exists'],600/1700,places=6)

    def test_completed_rebased_model_reports_exact_original_total(self):
        # Exhausting the frontier also exhausts the original tree, with old work retained.
        import formtree_eta as eta
        original, _, _ = fixture()
        e=eta.estimate(original,[dict(name='a',done=9,complete=True)],[(0,0),(10,19)],.01,0,4,offset=10)
        self.assertEqual(e['total'],dict(lo=19,median=19,hi=19))
        self.assertEqual(e['to_go'],dict(lo=0,median=0,hi=0))
        self.assertEqual((e['done'],e['exists']),(19,0))

    def test_loader_accepts_declared_checkpoint_and_checks_activated_hash(self):
        # An explicit new model is read unchanged; wrong activation hash is refused.
        import formtree_eta as eta
        _,model,_=fixture()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model.json'; p.write_text(json.dumps(model))
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(eta.read_model(p, digest),model)
            with self.assertRaises(AssertionError): eta.read_model(p,'0'*64)
            bad=dict(model, accidental=1); p.write_text(json.dumps(bad))
            with self.assertRaises(AssertionError): eta.read_model(p)

    def test_live_cli_uses_activation_without_rewriting_history(self):
        # The launcher keeps its original model argument; a model event selects the new file.
        # Earlier bytes and original model stay intact, and cumulative work still includes the prefix.
        import quals_formtree_estimator as q
        d=q.sandbox()
        try:
            original,model,prefix=fixture(); root=Path(d)
            (root/'old.json').write_text(json.dumps(original))
            new=root/'new.json'; new.write_text(json.dumps(model))
            (root/'verdicts.jsonl').write_bytes(prefix)
            start=dict(event='start',name='r',search='tree',target='16:4',estimator='old',
                       command='job',cwd=d,found=None,adopted=False,pid=7,tracker=8,time=100.)
            activation=dict(event='model',time=110.,path=str(new),
                            sha256=hashlib.sha256(new.read_bytes()).hexdigest())
            q.write(root/'runs/r.jsonl',[start,activation]); before=(root/'runs/r.jsonl').read_bytes()
            # The optional override permits a red run against the pre-change CLI in an isolated copy.
            override=os.environ.get('FRONTIER_OLD_CLI')
            if override: shutil.copy(override,root/'searchwatch/formtree_eta.py')
            q.inside(d,"""import json, os, runpy, sys, time, track
track.processes=lambda:{7:'S',8:'S'}
time.time=lambda:120.
os.environ[track.RECORD]=os.path.abspath('runs/r.jsonl')
sys.argv=['formtree_eta.py','verdicts.jsonl','old.json','0.5']
runpy.run_path('searchwatch/formtree_eta.py',run_name='__main__')
e=track.checked(track.lines('runs/r.jsonl'))[-1]
assert abs(e['total']['median']-1010)<1e-3,e
assert (e['done'],e['finished'],e['pending'])==(10,1,2),e
print('ok')
""")
            self.assertTrue((root/'runs/r.jsonl').read_bytes().startswith(before))
            self.assertEqual(json.loads((root/'old.json').read_text()),original)
        finally:
            shutil.rmtree(d)

    def test_assembly_keeps_sources_and_validates_every_probe(self):
        # A fully hashed frozen prefix and probe log build a new model, never alter the old one;
        # an altered block or censored observation cannot be published.
        import formtree_frontier as f
        with tempfile.TemporaryDirectory() as d:
            snapshot_path,out,rows,write,original,prefix=sampled_frontier(Path(d))
            root=Path(d)
            blocks=write(); model=f.assemble(snapshot_path,out)
            self.assertEqual(json.loads((root/'original-model.json').read_text()),original)
            self.assertEqual(model['checkpoint']['done'],10)
            self.assertEqual(f.observed(model,prefix)['offset'],10)
            self.assertEqual(model['root_log_sd'],original['root_log_sd'])
            blocks['groups'][0]['blocks'][0][0]=99
            (out/'model-blocks.json').write_text(json.dumps(blocks))
            with self.assertRaises(AssertionError): f.assemble(snapshot_path,out)
            rows[0]['censored']=True; write()
            with self.assertRaises(AssertionError): f.assemble(snapshot_path,out)

    def test_assembly_makes_each_member_its_own_unit(self):
        # Opus 5.5, 2026-11-16 (dreeves: "ok, go ahead and fix", after the live 480:14 frontier's groups of about 40
        # hid 468 finished members from the ETA model: a group counted as finished only when all its members were).
        # Replicata: five frontier members a-e, each probed in 8 rounds, member n's estimate in round i being
        # (i+1)*(1+'abcde'.index(n)).
        # Expectata: the model has one unit per member, in the snapshot's order, its blocks that member's 8 round
        # estimates; the checkpoint's groups are those members one each; nothing is done yet past the offset.
        # Resultata until that day: units were the sampling's process groups, their blocks the groups' sums.
        import formtree_frontier as f
        with tempfile.TemporaryDirectory() as d:
            snapshot_path,out,rows,write,original,prefix=sampled_frontier(Path(d),lambda n,i:(i+1)*(1+'abcde'.index(n)))
            write(); model=f.assemble(snapshot_path,out)
            self.assertEqual([r['name'] for r in model['roots']],list('abcde'))
            for k,r in enumerate(model['roots']):
                self.assertEqual(r['blocks'],[[float((i+1)*(k+1))] for i in range(8)])
            self.assertEqual(model['checkpoint']['groups'],[dict(name=n,members=[n]) for n in 'abcde'])
            state=f.observed(model,prefix)
            self.assertEqual(state['roots'],[dict(name=n,done=0,complete=False) for n in 'abcde'])
            self.assertEqual(state['offset'],10)


def sampled_frontier(root,estimate=lambda n,i:2.):
    """A frozen frontier of five members a-e under one root, its source-hashed snapshot, an original model, and a
    sampling directory whose probe rows have these estimates; returns (snapshot path, sampling directory, rows, write,
    original model, verdict prefix), write() (re)writing the probe log and blocks from rows."""
    import frontier_sample as sampling
    from quals_frontier_sample import fixture as sampling_fixture
    snapshot_path=sampling_fixture(root)
    snapshot=json.loads(snapshot_path.read_text())
    original,_,_=fixture(); original['roots'][0]['name']='root'
    prefix=encoded([verdict('root',15,list('abcde'))])
    (root/'verdicts.prefix').write_bytes(prefix)
    (root/'original-model.json').write_text(json.dumps(original))
    for name in ('verdicts.prefix','original-model.json'):
        snapshot['sources'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    snapshot['original_model']='original-model.json'
    snapshot['base']=dict(finished=1,done=10,prefix_bytes=len(prefix),
        prefix_sha256=hashlib.sha256(prefix).hexdigest(),roots=['root'],verdicts='unused-live-path')
    snapshot_path.write_text(json.dumps(snapshot))
    groups=sampling.groups(list('abcde'))
    rows=[dict(name=n,round=i,seed=sampling.seed('16:2',n,i),rc=0,open=0,censored=False,
               estimate=float(estimate(n,i)),weighted_wall_cost=.1,engine_wall=.1,cpu=.1,wall=.1)
          for i in range(8) for n in 'abcde']
    out=root/'sampled'; out.mkdir()
    (out/'sampler.py').write_bytes(b'frozen sampler')
    def write():
        (out/'draws.jsonl').write_bytes(encoded(rows))
        blocks=dict(snapshot_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                    protocol='fresh-group-round-v1',
                    sampler_sha256=hashlib.sha256((out/'sampler.py').read_bytes()).hexdigest(),
                    draws_sha256=hashlib.sha256((out/'draws.jsonl').read_bytes()).hexdigest(),
                    rounds=8,groups=sampling.blocks(groups,rows))
        (out/'model-blocks.json').write_text(json.dumps(blocks)); return blocks
    return snapshot_path,out,rows,write,original,prefix


if __name__ == '__main__': unittest.main()
