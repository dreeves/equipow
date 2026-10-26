"""Quals for fanout.py's tree-only job files (dreeves, 2026-10-25: "for 432:12, that sounds fine to store less"): a job
file keeps its tree, each L token's certificate dropped once its worker has checked it exactly, and assembly checks that
the trees fit together, in place of the splice's replay of certificates.  Run with
PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B -m unittest quals_fanout_tree."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import traceback
import unittest
from unittest.mock import patch

import fanout
import focus
import mstar
import reprove
from quals_fanout import events, finish, real, stopped

FIELDS = {'version', 'case', 'path', 'root', 'tree', 'tree_sha256', 'open', 'seconds', 'witness'}


def digest(tree):
    """The qual's own sha256 of a tree: of its compact JSON."""
    return hashlib.sha256(json.dumps(tree, separators=(',', ':')).encode()).hexdigest()


def files(work):
    """A fanout work directory's job files, read, by job id."""
    return {f.name.split('.')[0]: json.loads(gzip.decompress(f.read_bytes()))
            for f in sorted(Path(work, 'jobs').glob('*.json.gz'))}


def write(work, data):
    """data as the job file of its box, gzipped JSON, replacing any."""
    name = fanout.jid(fanout.key(data['case'], data['path']))
    Path(work, 'jobs', f'{name}.json.gz').write_bytes(gzip.compress(json.dumps(data).encode()))


def rehash(own, name, sha):
    """fanout's journal with each job_end of job name given tree_sha256 sha."""
    records = events(own)
    Path(own).write_text(''.join(json.dumps(dict(r, tree_sha256=sha) if (r['event'], r.get('job')) == ('job_end', name)
                                            else r) + '\n' for r in records))


def assembled(run, work, own, prepared):
    """fanout.assemble on a run as fanout.run calls it: its jobs, in the order it walks them."""
    code = focus.fingerprint()
    return fanout.assemble(run, work, own, prepared, code, fanout.roots(run, work, code), fanout.finished(work))


class TreeOnlyQuals(unittest.TestCase):
    def test_20_5_is_excluded_with_tree_only_job_files(self):
        # Replicata: (20, 5), order 5 at length 20, impossible (m*(20) = 3), stopped after 5 LP solves, then fanout with
        # two workers and jobs of at most 4 LP solves.
        # Expectata: excluded, in fanout's finish; every job file of version 2 with exactly FIELDS; every tree token
        # ['B', p] with p an int, or ['L']: no certificate anywhere; each file's tree_sha256 the sha256 of its tree's
        # JSON, and its job_end's; its job_end's LP solves its tree's nodes.
        # Resultata before tree-only storage: version 1 files, each L token with its certificate.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            self.assertEqual((events(own)[-1]['event'], events(own)[-1]['outcome']), ('finish', 'excluded'))
            jobs = files(work)
            ends = {e['job']: e for e in events(own) if e['event'] == 'job_end'}
            self.assertGreater(len(jobs), 2)
            self.assertEqual(set(jobs), set(ends))
            for name, data in jobs.items():
                self.assertEqual((set(data), data['version'], data['witness']), (FIELDS, 2, None))
                self.assertTrue(all(t == ['L'] or (len(t) == 2 and t[0] == 'B' and type(t[1]) is int)
                                    for t in data['tree']), data['tree'])
                self.assertEqual(data['tree_sha256'], digest(data['tree']))
                self.assertEqual((ends[name]['tree_sha256'], ends[name]['lps']),
                                 (data['tree_sha256'], len(data['tree'])))

    def test_16_4_witness_with_tree_only_job_files(self):
        # Replicata: (16, 4), Thue-Morse's order at 16, stopped after 3 LP solves, then fanout.
        # Expectata: a witness, of order at least 4 as signs; the file of the job that found it of version 2, its tree
        # ending ['W', x] with x the witness, every token before it a B or an L, and its witness field x.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(16, 4)
            run, journal = stopped(tmp, prepared, 16, 4, 3)
            outcome, work, own = finish(tmp, run, journal, prepared, 16, 4)
            self.assertEqual(outcome, 'witness')
            x = events(own)[-1]['witness']
            self.assertGreaterEqual(mstar.order([2 * t - 1 for t in x]), 4)
            [data] = [d for d in files(work).values() if d['witness'] is not None]
            self.assertEqual((data['version'], data['witness'], data['tree'][-1]), (2, x, ['W', x]))
            self.assertTrue(all(t == ['L'] or t[0] == 'B' for t in data['tree'][:-1]))
            self.assertEqual(data['tree_sha256'], digest(data['tree']))

    def test_tree_only_job_files_take_under_two_bytes_per_node_at_432(self):
        # Replicata: one fanout job, in this process, on 432:12's case B (focus.prepare(432, 12)), its whole box, jobs
        # of at most 1,000 LP solves (DEEP as in production); its file as fanout.save writes it, and the same job's
        # file as fanout.save wrote it before tree-only storage (version 1, every token with its certificate), from
        # the tokens focus.step made.
        # Expectata: 1,000 to 4,000 nodes; the tree-only file under 2 bytes per node (0.74 on 2026-10-25, 10,000
        # nodes: scratch/record-20261025/launch432/treeonly/encodings.py), and at least 100 times smaller than the
        # version-1 file (294.7 bytes per LP solve: scratch/record-20261025/f432/storage.py).
        prepared = focus.prepare(432, 12)
        made, real_step = [], focus.step
        def step(*args):
            made.append(real_step(*args))
            return made[-1]
        fanout.lp_for.cache_clear()
        fanout.init(prepared, 1000, fanout.DEEP)
        with patch.object(focus, 'step', step):
            result = fanout.work((0, ()))
        fanout.lp_for.cache_clear()
        nodes = len(result['tree'])
        self.assertEqual(nodes, len(made))
        self.assertTrue(1000 <= nodes <= 4000, nodes)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'jobs').mkdir()
            fanout.save(Path(tmp), (0, ()), 0, result)
            [path] = Path(tmp, 'jobs').glob('*.json.gz')
            tree_only = path.stat().st_size
        old = dict(version=1, case=0, path=[], root=0, tokens=made, open=result['open'], seconds=result['seconds'],
                   witness=None)
        full = len(gzip.compress(json.dumps(old, separators=(',', ':')).encode(), mtime=0))
        print(json.dumps(dict(n=432, order=12, nodes=nodes, tree_only_bytes=tree_only, version1_bytes=full,
                              tree_only_per_node=round(tree_only / nodes, 3), version1_per_node=round(full / nodes, 1),
                              ratio=round(full / tree_only, 1))), flush=True)
        self.assertLess(tree_only / nodes, 2)
        self.assertGreater(full / tree_only, 100)

    def test_the_432_path_a_focus_prefix_then_fanout(self):
        # Replicata: focus.search on 432:12 (focus.prepare's cases B and A) for 40 LP solves, then fanout.run with two
        # workers, jobs of at most 200 LP solves and probes of 2 paths, stopped by an error right after its third
        # job_end is journaled.
        # Expectata: the prefix's 40 LP solves replay exactly, their certificates kept in focus.py's chunks; three
        # journaled tree-only job files, each on a root's box or on a box a job left open, its tree leaving open exactly
        # the boxes its job handed back (fanout.frontier), its tree_sha256 its job_end's; and reprove.walk proves every
        # leaf of each again, from scratch, on 432's LPs.
        with tempfile.TemporaryDirectory() as tmp:
            run, journal = Path(tmp, 'run'), Path(tmp, 'focus.jsonl')
            self.assertEqual(focus.search(run, journal, 432, 12, 40, 600), 'budget')
            prepared, code = focus.prepare(432, 12), focus.fingerprint()
            self.assertEqual(focus.replay(run, *prepared, code).lp, 40)
            work, own = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
            real_note = fanout.note
            def note(path, event, **fields):
                real_note(path, event, **fields)
                if [e['event'] for e in events(path)].count('job_end') == 3: raise KeyboardInterrupt
            with patch.multiple(fanout, WORKERS=2, BUDGET=200, PROBE_PATHS=2, note=note), \
                    self.assertRaises(KeyboardInterrupt):
                fanout.run(run, work, own, 432, 12)
            roots = fanout.roots(run, work, code)
            ends = {e['job']: e for e in events(own) if e['event'] == 'job_end'}
            jobs = files(work)
            self.assertEqual(len(ends), 3)
            self.assertLessEqual(set(ends), set(jobs))
            boxes = {fanout.jid(b) for b in roots} | {fanout.jid(fanout.key(d['case'], p)) for d in jobs.values()
                                                      for p in d['open']}
            reprove.init(prepared)
            for name in ends:
                data = jobs[name]
                self.assertEqual(data['version'], 2)
                self.assertIn(name, boxes)
                self.assertEqual(fanout.frontier(432, data['path'], data['tree']), data['open'])
                self.assertEqual(ends[name]['tree_sha256'], digest(data['tree']))
                proof = reprove.walk(fanout.key(data['case'], data['path']), data['tree'])
                self.assertEqual((proof['job'], proof['nodes'], proof['leaves']),
                                 (name, len(data['tree']), sum(t == ['L'] for t in data['tree'])))
                print(json.dumps(dict(depth=len(data['path']), **proof)), flush=True)
            self.assertEqual(focus.replay(run, *prepared, code).lp, 40)


class AssemblyQuals(unittest.TestCase):
    """Forged trees refused by fanout.assemble, each on a copy of one genuine finished run: (20, 5) stopped after 5 LP
    solves, then fanout with two workers and jobs of at most 4 LP solves.  Each forgery keeps every hash consistent but
    the one it is about, so assembly must refuse it at the check the qual names, not a later one."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.prepared = real(20, 5)
        run, journal = stopped(cls.tmp.name, cls.prepared, 20, 5, 5)
        assert finish(cls.tmp.name, run, journal, cls.prepared, 20, 5)[0] == 'excluded'

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def refused(self, forge, where):
        """forge(work, own, jobs) on a copy of the genuine run, jobs its job files read; then fanout.assemble must fail
        with an AssertionError in fanout's function where[0], at a line holding where[1]."""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(self.tmp.name, tmp, dirs_exist_ok=True)
            run, work, own = Path(tmp, 'run'), Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
            self.assertGreater(len(assembled(run, work, own, self.prepared)), 2)    # the copy assembles, unforged
            forge(work, own, files(work))
            frames = []
            try:
                assembled(run, work, own, self.prepared)
            except AssertionError as raised:
                frames = traceback.extract_tb(raised.__traceback__)
            self.assertTrue(frames)                                             # assembly refused it
            self.assertEqual((Path(frames[-1].filename).name, frames[-1].name), ('fanout.py', where[0]))
            self.assertIn(where[1], frames[-1].line)

    def closed(self, jobs):
        """The id and file of a job that left no box open, with at least one B token."""
        return next((name, d) for name, d in sorted(jobs.items()) if not d['open'] and d['tree'][0][0] == 'B')

    def test_a_missing_leaf_is_refused(self):
        # Replicata: a job that left no box open loses its last token, an L; its file's and its job_end's
        # tree_sha256 made the new tree's.
        # Expectata: AssertionError in assemble, at check (1): the tree leaves a box open that its job did not hand
        # back.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            self.assertEqual(data['tree'][-1], ['L'])
            data['tree'] = data['tree'][:-1]
            data['tree_sha256'] = digest(data['tree'])
            write(work, data)
            rehash(own, name, data['tree_sha256'])
        self.refused(forge, ('assemble', 'frontier('))

    def test_an_extra_node_is_refused(self):
        # Replicata: a job that left no box open gains one more token, an L, after its last; hashes made the new
        # tree's.
        # Expectata: AssertionError in frontier: a token after the last box.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            data['tree'] = data['tree'] + [['L']]
            data['tree_sha256'] = digest(data['tree'])
            write(work, data)
            rehash(own, name, data['tree_sha256'])
        self.refused(forge, ('frontier', 'assert stack'))

    def test_a_split_on_a_fixed_position_is_refused(self):
        # Replicata: a job's first token, a B, made to split a position its box already fixes; hashes made the new
        # tree's.
        # Expectata: AssertionError in frontier: not a B on a free position.
        def forge(work, own, jobs):
            name, data = next((n, d) for n, d in sorted(jobs.items()) if d['path'] and d['tree'][0][0] == 'B')
            data['tree'][0] = ['B', data['path'][0][0]]
            data['tree_sha256'] = digest(data['tree'])
            write(work, data)
            rehash(own, name, data['tree_sha256'])
        self.refused(forge, ('frontier', "node == ['L']"))

    def test_an_overlapping_job_box_is_refused(self):
        # Replicata: one more job file, journaled with a job_end of its tree's sha256, on a box inside a box that a job
        # closed: that job's box with one more position fixed, its tree a single L and nothing open.
        # Expectata: AssertionError in assemble, at check (2): a job file that the walk from the roots does not reach,
        # so the jobs' boxes do not tile the case's box exactly.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            fixed = {p for p, _ in data['path']}
            q = min(set(range(20)) - fixed)
            extra = dict(data, path=data['path'] + [[q, 0]], tree=[['L']], tree_sha256=digest([['L']]), open=[])
            write(work, extra)
            fanout.note(own, 'job_end', job=fanout.jid(fanout.key(extra['case'], extra['path'])), case=extra['case'],
                        root=extra['root'], lps=1, seconds=0.0, open=0, tree_sha256=extra['tree_sha256'])
        self.refused(forge, ('assemble', 'set(done)'))

    def test_a_tree_unlike_its_own_hash_is_refused(self):
        # Replicata: a job's tree loses its last token, its file's tree_sha256 kept.
        # Expectata: AssertionError in load: the tree does not match its file's tree_sha256.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            data['tree'] = data['tree'][:-1]
            write(work, data)
        self.refused(forge, ('load', 'digest('))

    def test_a_tree_unlike_its_journaled_hash_is_refused(self):
        # Replicata: a job that left no box open has its first B moved to a position free in its box and split nowhere
        # in its tree, so that its tree is still complete, and its file's tree_sha256 made the new tree's; its
        # job_end's kept.
        # Expectata: AssertionError in assemble, at check (3): the journal's tree_sha256 is not the file's.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            used = {p for p, _ in data['path']} | {t[1] for t in data['tree'] if t[0] == 'B'}
            data['tree'][0] = ['B', min(set(range(20)) - used)]
            self.assertEqual(fanout.frontier(20, data['path'], data['tree']), [])
            data['tree_sha256'] = digest(data['tree'])
            write(work, data)
        self.refused(forge, ('assemble', "r['tree_sha256']"))

    def test_a_job_end_with_no_job_is_refused(self):
        # Replicata: one more job_end in fanout's journal, for a job id that is no job's.
        # Expectata: AssertionError in assemble, at check (3): every job_end must have its job's file.
        def forge(work, own, jobs):
            fanout.note(own, 'job_end', job='0' * 40, case=0, root=0, lps=1, seconds=0.0, open=0,
                        tree_sha256=digest([['L']]))
        self.refused(forge, ('assemble', "r['tree_sha256']"))

    def test_a_missing_job_file_is_refused(self):
        # Replicata: the file of a job whose box another job left open, deleted.
        # Expectata: AssertionError in load: the walk reaches that box and finds no file.
        def forge(work, own, jobs):
            opened = {fanout.jid(fanout.key(d['case'], p)) for d in jobs.values() for p in d['open']}
            Path(work, 'jobs', f'{min(opened)}.json.gz').unlink()
        self.refused(forge, ('load', '.exists()'))

    def test_a_version_1_job_file_is_refused(self):
        # Replicata: a job's file rewritten as fanout.save wrote it before tree-only storage, version 1, with tokens
        # in place of its tree and no tree_sha256, as 672:13's job files are.
        # Expectata: AssertionError in load, when fanout reads the job files: such a file is refused, not read.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            old = {k: v for k, v in data.items() if k not in ('tree', 'tree_sha256')}
            write(work, dict(old, version=1, tokens=[t + [[1]] if t == ['L'] else t for t in data['tree']]))
        self.refused(forge, ('load', "data['version'] == 2"))


if __name__ == '__main__':
    unittest.main()
