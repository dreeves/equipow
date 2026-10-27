"""Quals for fanout.py's tree-only job files (dreeves, 2026-10-25: "for 432:12, that sounds fine to store less"): a job
file keeps its tree, each L token's certificate dropped once its worker has checked it exactly, and assembly checks that
the trees fit together, in place of the splice's replay of certificates.  TrustQuals, from the review of that change
(2026-10-25), qualify what else a verdict rests on.  Run with
PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B -m unittest quals_fanout_tree."""
import contextlib
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import traceback
import unittest
from unittest.mock import patch

import fanout
import focus
import mstar
import reflection
import reprove
from quals_fanout import events, finish, real, stopped

FIELDS = {'version', 'case', 'path', 'root', 'tree', 'tree_sha256', 'open', 'seconds', 'witness'}


def digest(tree):
    """The qual's own sha256 of a tree: of its compact JSON."""
    return hashlib.sha256(json.dumps(tree, separators=(',', ':')).encode()).hexdigest()


def refusal(call):
    """The frames of the AssertionError that call() raises, innermost last, or [] if it raises none."""
    try:
        call()
    except AssertionError as raised:
        return traceback.extract_tb(raised.__traceback__)
    return []


def forging(prepared, budget, deep):
    """A worker's start standing in for an edited fanout.py whose work returns a witness it never checked: fanout.init,
    then fanout.work replaced by one making each job's tree a single W token, at the low end of the job's box."""
    fanout.init(prepared, budget, deep)
    def work(job):
        x = fanout.box(prepared[0].N, job[1])[0]
        return dict(tree=[['W', x]], tree_sha256=digest([['W', x]]), open=[], seconds=0.0, witness=x)
    fanout.work = work


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


@contextlib.contextmanager
def limited(seconds):
    """The block run with seconds of wall time, past which SIGALRM raises TimeoutError in it: a walk that never ends
    fails its qual instead of hanging the suite."""
    def expire(signum, frame):
        raise TimeoutError(f'past {seconds} s')
    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


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
        # Expectata: 1,000 to 4,000 nodes; the tree-only file under 2 bytes per node (0.93 on 2026-10-25, and 0.75 at
        # 10,000 nodes: scratch/record-20261025/launch432/treeonly/reprove_cost.py), and at least 100 times smaller
        # than the version-1 file (294.7 bytes per LP solve: scratch/record-20261025/f432/storage.py).
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

    def test_a_file_of_another_box_under_a_job_s_name_is_refused(self):
        # Replicata: fanout.jid made to give a box A the id of a box B, from here on, a stand-in for a sha1 collision:
        # B a job's box that it closed with at least one B token, A inside it, B with its least free position fixed
        # to 0; then B's file replaced by a file of A, its tree a single L and nothing open, written under B's name;
        # B's job_end given that tree's sha256.
        # Expectata: AssertionError in assemble, at its check that the file the walk reaches for B holds B's own
        # box, not only one of B's sha1.
        # Resultata before (2026-10-25 review, probe A2): assembly accepted every job, 20 there, the part of B outside A
        # proven by no tree.
        def forge(work, own, jobs):
            name, data = self.closed(jobs)
            b = fanout.key(data['case'], data['path'])
            a = fanout.key(data['case'], b[1] + ((min(set(range(20)) - {p for p, _ in b[1]}), 0),))
            real_jid = fanout.jid
            self.enterContext(patch.object(fanout, 'jid', lambda box: real_jid(b if fanout.key(*box) == a else box)))
            self.assertEqual(fanout.jid(a), name)
            write(work, dict(data, path=[list(p) for p in a[1]], tree=[['L']], tree_sha256=digest([['L']]), open=[]))
            rehash(own, name, digest([['L']]))
        self.refused(forge, ('assemble', "key(data['case'], data['path']) == job"))

    def test_a_session_of_other_fanout_code_is_refused(self):
        # Replicata: the journal's session record given another fanout_code, as a session run under an edited
        # fanout.py would have recorded it.
        # Expectata: AssertionError in assemble, at its check that every session ran the fanout code assembling the
        # run, the code beyond focus.fingerprint's sources that the run's exclusion rests on (see fanout.py's
        # 'trust').
        # Resultata before (2026-10-25 review, probe A11): no record named the fanout code, so assembly could not tell
        # trees made under an edited fanout.py from genuine ones.
        def forge(work, own, jobs):
            Path(own).write_text(''.join(json.dumps(dict(r, fanout_code='0' * 64) if r['event'] == 'session' else r)
                                         + '\n' for r in events(own)))
        self.refused(forge, ('assemble', "r['fanout_code']"))


class TrustQuals(unittest.TestCase):
    """What a fanout verdict rests on beyond the trees' shape (from the 2026-10-25 review of tree-only storage,
    scratch/record-20261025/launch432/treeonly-review): which fanout code ran, the witness a finish journals, a probe's
    witness, and the checks each session makes at its start, before any job; each refused at the check the qual
    names."""
    def refused_at(self, call, where):
        """call() must raise AssertionError in fanout's function where[0], at a line holding where[1]."""
        frames = refusal(call)
        self.assertTrue(frames)                                             # refused
        self.assertEqual((Path(frames[-1].filename).name, frames[-1].name), ('fanout.py', where[0]))
        self.assertIn(where[1], frames[-1].line)

    def interrupted(self, tmp, run, journal, prepared, n, m, ends):
        """fanout on the stopped run, as finish runs it, stopped by an error right after its ends-th job_end: the text
        of its journal then."""
        real_note = fanout.note
        def note(path, event, **fields):
            real_note(path, event, **fields)
            if [e['event'] for e in events(path)].count('job_end') == ends: raise KeyboardInterrupt
        with patch.object(fanout, 'note', note), self.assertRaises(KeyboardInterrupt):
            finish(tmp, run, journal, prepared, n, m)
        return Path(tmp, 'fanout.jsonl').read_text()

    def test_the_journal_names_the_fanout_code_of_its_session(self):
        # Replicata: (20, 5) stopped after 5 LP solves, then fanout to its finish.
        # Expectata: excluded; fanout's header and its session record each with fanout_code, the sha256 of fanout.py's
        # bytes followed by reflection.py's: the code its workers and its assembly ran, beyond focus.fingerprint's
        # sources, which its exclusion rests on (see fanout.py's 'trust').
        # Resultata before (2026-10-25 review, probe A11): no header or session field named that code, so a session
        # under an edited fanout.py left no trace in the journal.
        source = hashlib.sha256(Path(fanout.__file__).read_bytes() + Path(reflection.__file__).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            self.assertEqual([(e['event'], e.get('fanout_code')) for e in events(own)
                              if e['event'] in ('header', 'session')], [('header', source), ('session', source)])

    def test_a_session_under_other_fanout_code_is_refused_at_its_start(self):
        # Replicata: copies of fanout.py and reflection.py, fanout.__file__ pointed at the copy of fanout.py (as
        # quals_focus432 points focus.__file__ at copies of its sources); (20, 5) stopped after 5 LP solves; fanout
        # stopped by an error right after its second job_end; the copy of fanout.py changed by a byte, as by an edit
        # in mid-run; then fanout again.
        # Expectata: AssertionError in run, at its check of the journal's header, and fanout's journal as the first
        # session left it: no session, probe, job or finish record added.
        # Resultata before (2026-10-25 review, probe A11): nothing recorded or compared the fanout code, so the second
        # session ran the jobs left under the changed code and finished excluded.
        with tempfile.TemporaryDirectory() as tmp:
            for module in (fanout, reflection):
                shutil.copyfile(module.__file__, Path(tmp, Path(module.__file__).name))
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with patch.object(fanout, '__file__', str(Path(tmp, 'fanout.py'))):
                before = self.interrupted(tmp, run, journal, prepared, 20, 5, 2)
                copy = Path(tmp, 'fanout.py')
                copy.write_bytes(copy.read_bytes() + b'\n')
                self.refused_at(lambda: finish(tmp, run, journal, prepared, 20, 5), ('run', 'for k in same'))
            self.assertEqual(Path(tmp, 'fanout.jsonl').read_text(), before)

    @contextlib.contextmanager
    def copied(self, tmp):
        """Copies of fanout.py and reflection.py in tmp, fanout.__file__ pointed at the copy of fanout.py (as
        test_a_session_under_other_fanout_code_is_refused_at_its_start does): the copy's path."""
        for module in (fanout, reflection):
            shutil.copyfile(module.__file__, Path(tmp, Path(module.__file__).name))
        with patch.object(fanout, '__file__', str(Path(tmp, 'fanout.py'))):
            yield Path(tmp, 'fanout.py')

    def switched(self, tmp, n, m, stop, ends):
        """Under copied: focus.py's run of (n, m) stopped after stop LP solves; fanout stopped by an error right after
        its ends-th job_end; the copy of fanout.py changed by a byte; fanout.switch on the run; then fanout to its
        finish.  Its outcome, journal path and the fanout code before and after the change."""
        prepared = real(n, m)
        run, journal = stopped(tmp, prepared, n, m, stop)
        with self.copied(tmp) as copy:
            before = fanout.fingerprint()
            self.interrupted(tmp, run, journal, prepared, n, m, ends)
            copy.write_bytes(copy.read_bytes() + b'\n')
            fanout.switch(Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl'))
            outcome = finish(tmp, run, journal, prepared, n, m)[0]
            return outcome, Path(tmp, 'fanout.jsonl'), before, fanout.fingerprint()

    def test_a_recorded_switch_lets_the_run_go_on_under_the_new_code(self):
        # Replicata: switched on (20, 5), stopped after 5 LP solves and after fanout's second job_end; and on (16, 4),
        # stopped after 3 LP solves and after its first job_end (its witness may end a job as early as its second).
        # Expectata (dreeves, 2026-10-26: "ok, good, yeah", to switching 432:12 to a random job order without losing the
        # jobs done): (20, 5) excluded, and assembled under the code after; (16, 4) a witness, Thue-Morse or its
        # negation (Thue-Morse is the only partition of order 4 at 16, BGPW); each journal
        # with its header and first session under the code before, then one switch record from it to the code after
        # (from, to), then a session under the code after, which starts none of the jobs the first session finished.
        # Resultata before: no switch existed, so the second session was refused at its start, as an edit with no switch
        # still is (test_a_session_under_other_fanout_code_is_refused_at_its_start).
        for n, m, stop, ends, want in ((20, 5, 5, 2, 'excluded'), (16, 4, 3, 1, 'witness')):
            with self.subTest(n=n), tempfile.TemporaryDirectory() as tmp:
                outcome, own, before, after = self.switched(tmp, n, m, stop, ends)
                self.assertEqual(outcome, want)
                self.assertNotEqual(before, after)
                log = events(own)
                marks = [(e['event'], e.get('fanout_code'), e.get('from'), e.get('to')) for e in log
                         if e['event'] in ('header', 'session', 'switch')]
                self.assertEqual(marks, [('header', before, None, None), ('session', before, None, None),
                                         ('switch', None, before, after), ('session', after, None, None)])
                cut = [e['event'] for e in log].index('switch')
                done = {e['job'] for e in log[:cut] if e['event'] == 'job_end'}
                self.assertEqual(len(done), ends)
                self.assertFalse(done & {e['job'] for e in log[cut:] if e['event'] == 'job_start'})
                self.assertEqual(log[-1]['event'], 'finish')
                tm = [p.bit_count() % 2 for p in range(16)]          # order 4 at 16: Thue-Morse or its negation only
                if want == 'witness': self.assertIn(log[-1]['witness'], (tm, [1 - t for t in tm]))

    def test_a_switch_from_other_code_than_the_run_s_is_refused_at_the_next_start(self):
        # Replicata: as switched on (20, 5), but the switch record's from made another code's before fanout runs again
        # (a forged switch, or one made for another run).
        # Expectata: AssertionError in stands, at its check of each switch's from, and no record added.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with self.copied(tmp) as copy:
                self.interrupted(tmp, run, journal, prepared, 20, 5, 2)
                copy.write_bytes(copy.read_bytes() + b'\n')
                own = Path(tmp, 'fanout.jsonl')
                fanout.switch(Path(tmp, 'fanout'), own)
                own.write_text(''.join(json.dumps(dict(r, **{'from': '0' * 64}) if r['event'] == 'switch' else r) + '\n'
                                       for r in events(own)))
                before = own.read_text()
                self.refused_at(lambda: finish(tmp, run, journal, prepared, 20, 5), ('stands', "r['from'] == code"))
            self.assertEqual(own.read_text(), before)

    def test_a_switch_to_the_code_in_force_is_refused(self):
        # Replicata: (20, 5) stopped after 5 LP solves, fanout stopped after its second job_end; then fanout.switch with
        # fanout.py unchanged.
        # Expectata: AssertionError in switch (a switch to the code in force would record no change), and the journal
        # unchanged.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            self.interrupted(tmp, run, journal, prepared, 20, 5, 2)
            own = Path(tmp, 'fanout.jsonl')
            before = own.read_text()
            self.refused_at(lambda: fanout.switch(Path(tmp, 'fanout'), own), ('switch', 'before != code'))
            self.assertEqual(own.read_text(), before)

    def test_a_switch_waits_for_no_session(self):
        # Replicata: (20, 5) stopped after 5 LP solves, fanout stopped after its second job_end, the copy of fanout.py
        # changed by a byte; then fanout.switch while this process holds the work directory's lock, as a session does.
        # Expectata: BlockingIOError (the lock refused: no switch under a running session), and the journal unchanged.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with self.copied(tmp) as copy:
                self.interrupted(tmp, run, journal, prepared, 20, 5, 2)
                copy.write_bytes(copy.read_bytes() + b'\n')
                own = Path(tmp, 'fanout.jsonl')
                before = own.read_text()
                with open(Path(tmp, 'fanout', 'lock'), 'a') as held:
                    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with self.assertRaises(BlockingIOError):
                        fanout.switch(Path(tmp, 'fanout'), own)
            self.assertEqual(own.read_text(), before)

    def test_a_session_claiming_the_code_after_a_switch_before_it_is_refused_by_assembly(self):
        # Replicata: switched on (20, 5), excluded; then its first session's record given the code after the switch, as
        # if the first session had run it.
        # Expectata: AssertionError in assemble, at its check that each session ran the code in force at its place in
        # the journal ("r['fanout_code']"): a session before a switch ran the code the switch is from.
        with tempfile.TemporaryDirectory() as tmp:
            outcome, own, before, after = self.switched(tmp, 20, 5, 5, 2)
            self.assertEqual(outcome, 'excluded')
            log = events(own)
            first = [e['event'] for e in log].index('session')
            own.write_text(''.join(json.dumps(dict(r, fanout_code=after) if i == first else r) + '\n'
                                   for i, r in enumerate(log)))
            with self.copied(tmp):
                Path(tmp, 'fanout.py').write_bytes(Path(tmp, 'fanout.py').read_bytes() + b'\n')
                self.assertEqual(fanout.fingerprint(), after)
                self.refused_at(lambda: assembled(Path(tmp, 'run'), Path(tmp, 'fanout'), own, real(20, 5)),
                                ('assemble', "r['fanout_code']"))

    def test_a_witness_file_is_checked_exactly_before_the_finish(self):
        # Replicata: (20, 5), impossible (m*(20) = 3), stopped after 5 LP solves; a job file on its first root, as
        # fanout.save writes one, of tree ['W', x], witness x and nothing open, x the low end of the root's box; then
        # fanout.
        # Expectata: AssertionError in exact, the witness read back from its file and checked exactly on its job's
        # box, as fanout.work and focus.State check one; and no finish in fanout's journal: x breaks a row.
        # Resultata before (2026-10-25 review, probe A1): fanout returned 'witness' and journaled finish witness x.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            work = Path(tmp, 'fanout')
            (work / 'jobs').mkdir(parents=True)
            root = fanout.roots(run, work, focus.fingerprint())[0]
            x = fanout.box(20, root[1])[0]
            fanout.save(work, root, 0, dict(tree=[['W', x]], tree_sha256=digest([['W', x]]), open=[], seconds=0.0,
                                            witness=x))
            self.refused_at(lambda: finish(tmp, run, journal, prepared, 20, 5), ('exact', 'point_certificate'))
            self.assertNotIn('finish', [e['event'] for e in events(Path(tmp, 'fanout.jsonl'))])

    def test_a_witness_unlike_its_tree_s_is_refused(self):
        # Replicata: (16, 4) stopped after 3 LP solves and finished by fanout, with a witness x; then the job file that
        # holds it given witness all 0s, its tree, which ends ['W', x], and its tree_sha256 kept; then fanout again.
        # Expectata: AssertionError in witnessed, a witness being its tree's last token; one finish in fanout's
        # journal, the first, of witness x.
        # Resultata before (2026-10-25 review, probe A1b): the second session journaled finish witness all 0s.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(16, 4)
            run, journal = stopped(tmp, prepared, 16, 4, 3)
            outcome, work, own = finish(tmp, run, journal, prepared, 16, 4)
            self.assertEqual(outcome, 'witness')
            x = events(own)[-1]['witness']
            [data] = [d for d in files(work).values() if d['witness'] is not None]
            write(work, dict(data, witness=[0] * 16))
            self.refused_at(lambda: finish(tmp, run, journal, prepared, 16, 4), ('witnessed', "['W', data['witness']]"))
            self.assertEqual([e['witness'] for e in events(own) if e['event'] == 'finish'], [x])

    def test_a_witness_a_worker_returns_is_checked_again_by_the_driver(self):
        # Replicata: (20, 5), impossible, stopped after 5 LP solves; then fanout with its workers started by forging,
        # a stand-in for an edited fanout.py whose work returns, for each job, tree ['W', x] and witness x, x the low
        # end of the job's box, unchecked.
        # Expectata: AssertionError in exact, in the driver, which reads the witness back from its job's file and
        # checks it exactly before any finish; no finish in fanout's journal.
        # Resultata before: fanout returned 'witness' and journaled finish witness x, trusting the worker's check.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with patch.object(fanout, 'init', forging):
                self.refused_at(lambda: finish(tmp, run, journal, prepared, 20, 5), ('exact', 'point_certificate'))
            self.assertNotIn('finish', [e['event'] for e in events(Path(tmp, 'fanout.jsonl'))])

    def test_an_exact_probe_witness_stops_an_exclusion(self):
        # Replicata: 16:4 with plus counts (0, 4, 4) mod 3, which only Thue-Morse meets (quals_reprove), its root split
        # on position 0 by hand; the box with position 0 at 0, which holds Thue-Morse, given a forged complete job
        # file and no job_end: a tree grown as fanout.work grows one, its W token closed as an L, as quals_reprove's
        # forger grows one; the other box left to the workers; then fanout.
        # Expectata: the session's probe journals Thue-Morse as a witness, checked exactly in probe; then
        # AssertionError in assemble, at its check of the probes, and no finish: a case with a solution cannot be
        # excluded.
        # Resultata before (2026-10-25 review, probe A3): finish excluded, a false exclusion, which the probe's witness
        # in the same journal contradicted.
        from quals_reprove import THUE_MORSE, grown, split_once
        with tempfile.TemporaryDirectory() as tmp:
            prepared = focus.moments(16, 4), (((3, (0, 4, 4)),),)
            run = split_once(tmp, prepared, 0)
            work, own = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
            (work / 'jobs').mkdir(parents=True)
            [(i, root)] = [(i, r) for i, r in enumerate(fanout.roots(run, work, focus.fingerprint()))
                           if r[1] == ((0, 0),)]
            tree, faked = grown(prepared, *root)
            self.assertEqual(len(faked), 1)
            fanout.save(work, root, i, dict(tree=tree, tree_sha256=digest(tree), open=[], seconds=0.0, witness=None))
            self.refused_at(lambda: finish(tmp, run, None, prepared, 16, 4), ('assemble', "'probe'"))
            log = events(own)
            self.assertIn(THUE_MORSE, [x for e in log if e['event'] == 'probe' for x in e['witnesses']])
            self.assertNotIn('finish', [e['event'] for e in log])

    def test_a_moved_run_is_refused_at_the_session_start(self):
        # Replicata: (20, 5) stopped after 5 LP solves; fanout stopped by an error right after its second job_end;
        # focus.search then 3 more LP solves on the same run, as a relaunch of the budget-finished prefix (by the
        # shepherd, say) would make; then fanout again.
        # Expectata: AssertionError in unmoved, at its check that the run's replay still ends at the roots, before any
        # record of the second session: fanout's journal as the first session left it.
        # Resultata before (2026-10-25 review, probe A8): the second session ran 18 more jobs, its job_ends from 2 to
        # 20, and only assembly refused, after the last.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            before = self.interrupted(tmp, run, journal, prepared, 20, 5, 2)
            with patch.object(focus, 'prepare', return_value=prepared):
                self.assertEqual(focus.search(run, journal, 20, 5, 3, 600), 'budget')
            self.refused_at(lambda: finish(tmp, run, journal, prepared, 20, 5), ('unmoved', 'state.frontier'))
            self.assertEqual(Path(tmp, 'fanout.jsonl').read_text(), before)

    def test_a_lost_job_file_is_refused_at_the_session_start(self):
        # Replicata: (20, 5) stopped after 5 LP solves; fanout stopped by an error right after its third job_end; the
        # file of the job that ended first deleted, as by a disk fault; then fanout again.
        # Expectata: AssertionError in run, at its check that every job_end in the journal has its job's file with its
        # tree_sha256, made at the session's start; after the first session's records, the second session's alone.
        # Resultata before (2026-10-25 review, probe A4): the second session ran that job again, journaling a second
        # job_end of it, and finished excluded.  At 432:12, where a job's tree depends on its worker's LP history, the
        # second job_end's tree_sha256 would differ, and assembly would refuse after the last job.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            self.interrupted(tmp, run, journal, prepared, 20, 5, 3)
            before = events(Path(tmp, 'fanout.jsonl'))
            first = next(e['job'] for e in before if e['event'] == 'job_end')
            Path(tmp, 'fanout', 'jobs', f'{first}.json.gz').unlink()
            self.refused_at(lambda: finish(tmp, run, journal, prepared, 20, 5), ('run', "r['tree_sha256']"))
            self.assertEqual([e['event'] for e in events(Path(tmp, 'fanout.jsonl'))[len(before):]], ['session'])

    def test_a_job_file_handing_back_a_box_not_strictly_within_its_own_is_refused_at_the_session_start(self):
        # Replicata: (20, 5) stopped after 5 LP solves; fanout stopped by an error right after its third job_end, when a
        # child job (one whose box another job, its parent, handed back) and its parent both have their files; then,
        # in a copy of that state for each, the child's file given one more open box, its tree and tree_sha256 kept so
        # that load's other checks pass: (a) the child's own box; (b) its parent's box; (c) a box outside its own, its
        # path with its first value flipped and one more position fixed; then fanout again, allowed 20 s.
        # Expectata (2026-10-26 launch review): AssertionError in load, at its check that a job file hands back only
        # boxes strictly within its own, its path and at least one position more; after the first session's records,
        # the second session's alone, before any probe or job.
        # Resultata before: (a) and (b) kept the session start's walk going round its cycle past the 20 s
        # (TimeoutError); (c) was proven as a job, and only assembly refused it, after the last job.
        with tempfile.TemporaryDirectory() as first:
            prepared = real(20, 5)
            run, journal = stopped(first, prepared, 20, 5, 5)
            self.interrupted(first, run, journal, prepared, 20, 5, 3)
            jobs = files(Path(first, 'fanout'))
            child, parent = next((d, e) for d in jobs.values() for e in jobs.values()
                                 if d['case'] == e['case'] and d['path'] in e['open'])
            (q, v), free = child['path'][0], min(set(range(20)) - {p for p, _ in child['path']})
            outside = [[q, 1 - v]] + child['path'][1:] + [[free, 0]]
            for label, extra in (('own', child['path']), ('parent', parent['path']), ('outside', outside)):
                with self.subTest(box=label), tempfile.TemporaryDirectory() as tmp:
                    shutil.copytree(first, tmp, dirs_exist_ok=True)
                    write(Path(tmp, 'fanout'), dict(child, open=child['open'] + [extra]))
                    before = events(Path(tmp, 'fanout.jsonl'))
                    with limited(20):
                        self.refused_at(lambda: finish(tmp, Path(tmp, 'run'), Path(tmp, 'focus.jsonl'), prepared,
                                                       20, 5), ('load', "p[:len(data['path'])]"))
                    self.assertEqual([e['event'] for e in events(Path(tmp, 'fanout.jsonl'))[len(before):]],
                                     ['session'])

    def test_a_job_file_s_rename_is_made_durable(self):
        # Replicata: fanout.write_atomic of a small object to a file in a fresh directory, os.open, os.fsync and
        # os.replace recorded as they are called.
        # Expectata: after the replace, an fsync of a descriptor that os.open opened on the file's directory: a job's
        # file must survive a power loss once its job_end, which note fsyncs after it, is journaled.
        # Resultata before (2026-10-25 review): the temporary file was fsynced and then replaced, and no directory was
        # fsynced.
        calls, real_open, real_fsync, real_replace = [], os.open, os.fsync, os.replace
        def opened(path, flags, *args, **kwargs):
            calls.append(('open', Path(path), real_open(path, flags, *args, **kwargs)))
            return calls[-1][2]
        def synced(fd):
            calls.append(('fsync', None, fd))
            return real_fsync(fd)
        def replaced(source, target):
            calls.append(('replace', Path(target), None))
            return real_replace(source, target)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(os, 'open', opened), patch.object(os, 'fsync', synced), \
                    patch.object(os, 'replace', replaced):
                fanout.write_atomic(Path(tmp, 'job.json.gz'), dict(tree=[['L']]))
            self.assertEqual(fanout.read(Path(tmp, 'job.json.gz')), dict(tree=[['L']]))
        after = calls[[kind for kind, _, _ in calls].index('replace'):]
        directories = {fd for kind, path, fd in after if kind == 'open' and path == Path(tmp)}
        self.assertTrue(directories & {fd for kind, _, fd in after if kind == 'fsync'}, calls)


if __name__ == '__main__':
    unittest.main()
