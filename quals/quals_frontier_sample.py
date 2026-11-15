#!/usr/bin/env python3
"""Quals for frozen-frontier sampling. Run: python3 -B quals/quals_frontier_sample.py."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'searchwatch'))

FAKE = '''
import os
RUN_INIT = {}
def init(*args, **kwargs):
    assert 'PEX_FOLD' not in os.environ or os.environ['PEX_FOLD'] in ('-1','1')
def run_settings(): pass
class Library:
    def pe_fold(self): return int(os.environ.get('PEX_FOLD','0'))
    def pe_certfd(self, fd): pass
    def pe_import(self, alpha): pass
    def pe_dive_file(self, path, limit, seed, stats):
        value = int(open(path.decode()).read())
        stats[0], stats[1], stats[2], stats[3] = value, value/10, .01, 0
        return 0
lib = Library()
'''


def fixture(path):
    files = {'pex.py': FAKE, 'libpex.so': 'library', 'sample.cfg': 'configuration',
             'sample.cfg.Q.npy': 'basis', **{f'nodes/{n}': str(i+1) for i, n in enumerate('abcde')}}
    for name, data in files.items():
        p = path/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(data)
    snapshot = dict(version=1, target='16:2', engine=dict(library='libpex.so', wrapper='pex.py',
                    config='sample.cfg', mods=[3,4,5], want=[4,3,5], fold=0, alpha=.25, wall_limit=30),
                    nodes={n: f'nodes/{n}' for n in 'abcde'},
                    sources={n: hashlib.sha256((path/n).read_bytes()).hexdigest() for n in files})
    p = path/'snapshot.json'; p.write_text(json.dumps(snapshot)); return p


class Sampling(unittest.TestCase):
    # Replicata and expectata appear with each qual; assertion output supplies resultata.
    def test_groups_cover_the_frontier_once_and_do_not_depend_on_input_order(self):
        # Forty-three nodes in arbitrary order: at most16 balanced, deterministic disjoint groups.
        import frontier_sample as f
        names = [str(i) for i in range(43)]
        a = f.groups(names); b = f.groups(names[::-1])
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)
        self.assertEqual(sorted(n for g in a for n in g['members']), sorted(names))
        self.assertLessEqual(max(len(g['members']) for g in a)-min(len(g['members']) for g in a), 1)
        self.assertEqual(len({g['name'] for g in a}), len(a))

    def test_blocks_are_full_stratified_group_estimates(self):
        # Each round observes every member; averaging scaled observations equals their sum.
        import frontier_sample as f
        groups = [dict(name='g0', members=['a','b']), dict(name='g1', members=['c'])]
        rows = [dict(name=n, round=r, estimate=(r+1)*v) for r in range(8) for n,v in [('a',2),('b',5),('c',11)]]
        result = f.blocks(groups, rows[::-1])
        self.assertEqual(result[0]['blocks'], [[4*(r+1),10*(r+1)] for r in range(8)])
        self.assertEqual(result[1]['blocks'], [[11*(r+1)] for r in range(8)])
        self.assertEqual([sum(b)/len(b) for b in result[0]['blocks']], [7*(r+1) for r in range(8)])

    def test_missing_duplicate_and_unknown_probes_fail(self):
        # A partial/colliding/foreign probe set cannot produce a seemingly complete model.
        import frontier_sample as f
        groups = [dict(name='g0',members=['a'])]
        rows = [dict(name='a',round=i,estimate=1) for i in range(8)]
        for invalid in (rows[:-1], rows+[rows[0]], rows+[dict(name='b',round=0,estimate=1)]):
            with self.assertRaises(AssertionError): f.blocks(groups, invalid)

    def test_censored_open_invalid_and_failed_dives_are_refused(self):
        # A timed-out or OPEN dive must never be silently dropped or accepted as a short tree.
        import frontier_sample as f
        row = dict(rc=0, estimate=3, weighted_wall_cost=.1, engine_wall=.2, open=0, cpu=.1, wall=.2, censored=False)
        f.checked(row, 30)
        for change in (dict(rc=-1),dict(estimate=0),dict(estimate=float('nan')),dict(open=1),
                       dict(engine_wall=30,censored=True),dict(censored=True),dict(cpu=-1)):
            with self.assertRaises(AssertionError): f.checked(row | change, 30)

    def test_seeds_are_stable_and_distinguish_target_node_and_round(self):
        # Seed namespace identifies the independent probe, regardless of scheduling order.
        import frontier_sample as f
        a = f.seed('16:2','a',0)
        self.assertEqual(a, f.seed('16:2','a',0))
        self.assertEqual(len({a,f.seed('16:2','a',1),f.seed('16:2','b',0),f.seed('32:2','a',0)}),4)
        self.assertTrue(0 <= a < 2**64)

    def test_sources_and_snapshot_schema_are_checked_before_work(self):
        # A frozen source changed or missing from provenance: fail before invoking its wrapper.
        import frontier_sample as f
        with tempfile.TemporaryDirectory() as d:
            p = fixture(Path(d)); snapshot, paths, digest = f.read_snapshot(p)
            self.assertEqual(set(paths),set(snapshot['sources']))
            self.assertEqual(digest,hashlib.sha256(p.read_bytes()).hexdigest())
            (Path(d)/'nodes/a').write_text('100')
            with self.assertRaises(AssertionError): f.read_snapshot(p)
            snapshot['sources'].pop('nodes/a'); p.write_text(json.dumps(snapshot))
            with self.assertRaises(AssertionError): f.read_snapshot(p)

    def test_cli_samples_all_frozen_nodes_and_preserves_sources(self):
        # Two worker processes, five frozen inputs: all40 probes, immutable inputs, complete output.
        import frontier_sample
        with tempfile.TemporaryDirectory() as d:
            p = fixture(Path(d)); before={q: q.read_bytes() for q in Path(d).rglob('*') if q.is_file()}
            out=Path(d)/'result'
            result=subprocess.run([sys.executable,'-B',str(ROOT/'searchwatch/frontier_sample.py'),str(p),str(out),'2'],
                                  capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            rows=[json.loads(s) for s in (out/'draws.jsonl').read_text().splitlines()]
            self.assertEqual({(r['name'],r['round']) for r in rows},{(n,i) for n in 'abcde' for i in range(8)})
            self.assertEqual(len(rows),40)
            output=json.loads((out/'model-blocks.json').read_text())
            self.assertEqual(output['rounds'],8)
            self.assertEqual(len(output['groups']),5)
            self.assertTrue(all(q.read_bytes()==data for q,data in before.items()))
            again=subprocess.run([sys.executable,'-B',str(ROOT/'searchwatch/frontier_sample.py'),str(p),str(out),'2'],
                                 capture_output=True,text=True,timeout=30)
            self.assertNotEqual(again.returncode,0)

    def test_initializer_failure_is_refused_before_pool_creation(self):
        # An invalid native/wrapper initializer must fail once, not respawn workers forever.
        import frontier_sample as f
        with tempfile.TemporaryDirectory() as d:
            p=fixture(Path(d)); snapshot=json.loads(p.read_text())
            wrapper=Path(d)/'pex.py'
            wrapper.write_text(FAKE.replace('def init(*args, **kwargs):', 'def init(*args, **kwargs):\n    raise RuntimeError()'))
            snapshot['sources']['pex.py']=hashlib.sha256(wrapper.read_bytes()).hexdigest(); p.write_text(json.dumps(snapshot))
            snapshot,paths,_=f.read_snapshot(p)
            with self.assertRaises(AssertionError): f.preflight(snapshot,paths)

    def test_unfolded_engine_requires_unset_environment(self):
        # The real engine rejects PEX_FOLD=0; zero in snapshot means an absent variable.
        import frontier_sample as f
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'PEX_FOLD':'-1'}):
            p=fixture(Path(d)); snapshot,paths,_=f.read_snapshot(p)
            f.worker_init(snapshot,paths)
            self.assertNotIn('PEX_FOLD',os.environ)
            for sign in (-1,1):
                snapshot['engine']['fold']=sign; f.worker_init(snapshot,paths)
                self.assertEqual(os.environ['PEX_FOLD'],str(sign))

    def test_native_state_is_fresh_for_every_group_round(self):
        # A stateful fake engine adds its call count; each group-round must start at one.
        # This is independent of worker assignment, and catches cross-block pool carryover.
        import frontier_sample
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); p=fixture(home); s=json.loads(p.read_text())
            wrapper=home/'pex.py'
            wrapper.write_text(FAKE.replace('value = int(open(path.decode()).read())',
                               "self.calls = getattr(self,'calls',0)+1\n        value = int(open(path.decode()).read())+self.calls"))
            s['sources']['pex.py']=hashlib.sha256(wrapper.read_bytes()).hexdigest()
            s['nodes']={f'n{i}':f'nodes/n{i}' for i in range(43)}
            for i,(name,rel) in enumerate(s['nodes'].items()):
                (home/rel).write_text(str(i+1)); s['sources'][rel]=hashlib.sha256((home/rel).read_bytes()).hexdigest()
            p.write_text(json.dumps(s)); out=home/'result'
            result=subprocess.run([sys.executable,'-B',str(ROOT/'searchwatch/frontier_sample.py'),str(p),str(out),'2'],
                                  capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            rows=[json.loads(line) for line in (out/'draws.jsonl').read_text().splitlines()]
            by={(r['name'],r['round']):r['estimate'] for r in rows}
            for g in json.loads((out/'model-blocks.json').read_text())['groups']:
                for position,name in enumerate(g['members'],1):
                    expected=int((home/s['nodes'][name]).read_text())+position
                    self.assertEqual([by[name,i] for i in range(8)],[expected]*8)


if __name__ == '__main__': unittest.main()
