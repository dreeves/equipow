"""Quals for fanout.py: a stopped focus.py run finished by parallel workers, each checking its certificates exactly as
it makes them, its job files keeping only the trees, which assembly fits together (2026-10-25, in place of splicing
the proof back as focus.py chunks: quals_fanout_tree).  Run with PYTHONPATH=scratch/lower24-design/beyond1000/pylib
/opt/homebrew/bin/python3 -B -m unittest quals_fanout."""
from concurrent.futures import Future
import fcntl
import hashlib
import json
import math
from pathlib import Path
import pickle
import random
import sys
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

import certbb
import focus
import mstar
import fanout
import reprove


def real(n, m):
    """focus.py's own equations for length n and order m, one case with no residue counts."""
    return focus.moments(n, m), ((),)


def unpaired():
    """Two cases of length 20 and order 5, both impossible (m*(20) = 3), neither the other's reflection: plus counts
    (2, 4, 4) and (3, 3, 4) modulo 3."""
    return focus.moments(20, 5), (((3, (2, 4, 4)),), ((3, (3, 3, 4)),))


def tree_lps(prepared, case):
    """The LP solves of case's whole tree, depth first from a fresh LP under fanout.work's warm starts (a box's second
    child restores its parent's basis), a W token a leaf, as an L token is."""
    equations, cases = prepared
    choice = cases[case]
    lp = certbb.Lp(equations, tuple(M for M, _ in choice))
    lp.set_counts(choice)
    stack, lps = [((), None)], 0
    while stack:
        path, basis = stack.pop()
        if basis is not None:
            assert lp.H.setBasis(basis) == certbb.highs.HighsStatus.kOk
        token = focus.step(lp, equations, choice, *fanout.box(equations.N, path))
        lps += 1
        children = [(path + ((token[1], 1),), lp.H.getBasis()), (path + ((token[1], 0),), None)]
        stack += children if token[0] == 'B' else []
    return lps


def proof(work):
    """The sha256 of every job's tree_sha256, by job id: the run's tree, as its job files keep it."""
    trees = {p.name: fanout.read(p)['tree_sha256'] for p in sorted(Path(work, 'jobs').glob('*.json.gz'))}
    return hashlib.sha256(json.dumps(trees).encode()).hexdigest()


def stopped(tmp, prepared, n, m, budget):
    """A focus.py run on prepared, stopped at its budget of LP solves: its directory and journal."""
    run, journal = Path(tmp, 'run'), Path(tmp, 'focus.jsonl')
    with patch.object(focus, 'prepare', return_value=prepared):
        assert focus.search(run, journal, n, m, budget, 600) == 'budget'
    return run, journal


def finish(tmp, run, journal, prepared, n, m, budget=4):
    """fanout.run on the stopped run, with two workers and jobs of at most budget LP solves."""
    work, own = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
    with patch.object(focus, 'prepare', return_value=prepared), patch.multiple(fanout, WORKERS=2, BUDGET=budget):
        return fanout.run(run, work, own, n, m), work, own


def events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def held(x):
    """The bytes of x and of the objects it refers to through dicts' keys and values and lists' and tuples' items, by
    sys.getsizeof, an object counted at each reference (so a small int that two fields share, cached by Python,
    counts twice, as two distinct ints would)."""
    parts = [*x.keys(), *x.values()] if isinstance(x, dict) else x if isinstance(x, (list, tuple)) else []
    return sys.getsizeof(x) + sum(map(held, parts))


def spined(path, n, spines, length, seed):
    """spines * length boxes strictly within the box of path, a tuple of (position, value) pairs at length n, as a job's
    depth-first search leaves them open: down each of spines random paths from path, through length positions free
    there, the sibling of each step; a spine's boxes sharing its prefixes' pairs, as work's paths share them."""
    rng, boxes = random.Random(seed), []
    free = sorted(set(range(n)) - {q for q, _ in path})
    for _ in range(spines):
        p = path
        for q in rng.sample(free, length):
            t = rng.randrange(2)
            boxes.append(p + ((q, 1 - t),))
            p += ((q, t),)
    return boxes


def sequences(own):
    """A fanout journal's job_starts, [job, case, depth, root] each, and job_ends, [job, tree_sha256] each, in its
    order: how many of each, and the sha256 of each list's JSON."""
    log, sha = events(own), lambda x: hashlib.sha256(json.dumps(x).encode()).hexdigest()
    starts = [[r['job'], r['case'], r['depth'], r['root']] for r in log if r['event'] == 'job_start']
    ends = [[r['job'], r['tree_sha256']] for r in log if r['event'] == 'job_end']
    return dict(starts=len(starts), starts_sha256=sha(starts), ends=len(ends), ends_sha256=sha(ends))


class Inline:
    """A stand-in for farm's ProcessPoolExecutor: each job submitted done at once, in this process, its result
    hand(job)'s, or hand's error raised."""
    def __init__(self, hand):
        self.hand = hand

    def __enter__(self):
        return self

    def __exit__(self, *raised):
        return False

    def submit(self, fn, job):
        future = Future()
        future.set_result(self.hand(job))
        return future


class FanoutQuals(unittest.TestCase):
    def test_roots_are_the_frontier_of_the_run_s_last_chunk(self):
        # Replicata: (20, 5) stopped after 5 LP solves.
        # Expectata: fanout's roots are the open boxes the run's exact replay leaves, in the same order.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, _ = stopped(tmp, prepared, 20, 5, 5)
            replayed = focus.replay(run, *prepared, focus.fingerprint())
            roots = fanout.roots(run, Path(tmp, 'fanout'), focus.fingerprint())
            self.assertEqual(roots, [fanout.key(*b) for b in replayed.frontier])
            self.assertGreater(len(roots), 1)

    def test_a_stopped_run_is_finished_and_assembled(self):
        # Replicata: (20, 5), order 5 at length 20, impossible (m*(20) = 3), stopped after 5 LP solves, then fanout
        # with two workers and jobs of at most 4 LP solves.
        # Expectata: excluded; jobs handed back open boxes (several jobs, some with open children); the run's chunks
        # untouched, their replay still the 5 LP solves ending at fanout's roots; assembly's walk from the roots
        # reaching every job fanout's journal ended; and the finish, excluded, in fanout's journal only, focus.py's
        # still ending at its own budget finish.
        # Resultata before tree-only storage (2026-10-25, this qual then named
        # test_a_stopped_run_is_finished_as_chunks_focus_replays): the splice appended the jobs' proofs as chunks, and
        # focus.search's replay of them wrote an excluded finish to focus.py's journal.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            code = focus.fingerprint()
            done = focus.replay(run, *prepared, code)
            roots = fanout.roots(run, work, code)
            self.assertEqual((done.lp, done.outcome, [fanout.key(*b) for b in done.frontier]), (5, 'budget', roots))
            ends = [e for e in events(own) if e['event'] == 'job_end']
            self.assertGreater(len(ends), 2)
            self.assertTrue(all(e['lps'] <= 4 for e in ends))
            self.assertTrue(any(e['open'] for e in ends))
            walked = fanout.assemble(run, work, own, prepared, code, roots, fanout.finished(work))
            self.assertEqual(sorted(map(fanout.jid, walked)), sorted(e['job'] for e in ends))
            self.assertEqual((events(journal)[-1]['event'], events(journal)[-1]['outcome']), ('finish', 'budget'))
            self.assertEqual((events(own)[-1]['event'], events(own)[-1]['outcome']), ('finish', 'excluded'))

    def test_a_witness_stops_the_fanout_and_is_exact(self):
        # Replicata: (16, 4), Thue-Morse's order at 16, stopped after 3 LP solves, then fanout.
        # Expectata: a witness, logged with fanout's finish; as signs it has order at least 4.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(16, 4)
            run, journal = stopped(tmp, prepared, 16, 4, 3)
            outcome, work, own = finish(tmp, run, journal, prepared, 16, 4)
            self.assertEqual(outcome, 'witness')
            x = events(own)[-1]['witness']
            self.assertGreaterEqual(mstar.order([2 * t - 1 for t in x]), 4)

    def test_a_restart_reuses_finished_jobs(self):
        # Replicata: fanout on (20, 5) stopped by an error right after its third job's file is saved, then run again.
        # Expectata: three job files; excluded; the second session starts none of those three jobs.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            real_save, saves = fanout.save, []
            def save(*args):
                real_save(*args)
                saves.append(1)
                if len(saves) == 3: raise KeyboardInterrupt
            with patch.object(fanout, 'save', save), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            saved = {f.name.split('.')[0] for f in Path(tmp, 'fanout', 'jobs').glob('*.json.gz')}
            self.assertEqual(len(saved), 3)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            log = events(own)
            second = max(i for i, e in enumerate(log) if e['event'] == 'session')
            self.assertFalse(saved & {e['job'] for e in log[second:] if e['event'] == 'job_start'})

    def test_a_running_focus_run_is_refused(self):
        # Replicata: focus.py's lock on the run held, as by a live focus.py, then fanout on the run.
        # Expectata: BlockingIOError: never two writers of one proof.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with open(run / 'run.lock', 'a') as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    finish(tmp, run, journal, prepared, 20, 5)

    def test_a_forged_certificate_fails_at_its_worker(self):
        # Replicata: fanout.work, in this process, on (20, 5)'s whole box, with focus.step wrapped so that the first L
        # token it makes has its certificate zeroed.
        # Expectata: certbb.ProofError: a worker checks every token exactly, by certbb.Check on its job's box, as it
        # makes it, so a certificate that fails stops its job (in a pool, the driver too, at future.result()), before
        # the job file that would keep only its tree.
        # Resultata before tree-only storage (2026-10-25, this qual then named test_a_forged_job_fails_the_splice):
        # a certificate zeroed in a saved job file failed the splice, which fed every saved token through focus.py's
        # exact checker; no job file keeps a certificate now.
        prepared, real_step, forged = real(20, 5), focus.step, []
        def step(*args):
            token = real_step(*args)
            zeroed = ('L', [0] * len(token[1])) if token[0] == 'L' and not any(forged) else token
            forged.append(zeroed is not token)
            return zeroed
        fanout.lp_for.cache_clear()
        fanout.init(prepared, 10000, 8)
        with patch.object(focus, 'step', step), self.assertRaises(certbb.ProofError):
            fanout.work((0, ()))
        fanout.lp_for.cache_clear()
        self.assertEqual(forged.count(True), 1)

    def test_the_driver_keeps_no_tokens_in_memory(self):
        # Replicata: fanout on (20, 5), its assembly replaced by a recorder of what it is given.
        # Expectata: the driver's record of done jobs holds each job's open boxes, witness and root, but no tokens and
        # no tree: at 672 a job's tokens were tens of megabytes, and assembly reads the trees back from the job files
        # one at a time.
        # Resultata before tree-only storage (2026-10-25): the same, with the splice in assembly's place.
        # Since 2026-10-26 a record holds its open boxes' count, not the boxes, which farm reads back from the job's
        # file (test_the_driver_keeps_a_bounded_record_of_each_done_job).
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            given = []
            def assemble(*args):
                given.append(args)
                raise KeyboardInterrupt
            with patch.object(fanout, 'assemble', assemble), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            done = next(a for a in given[0] if isinstance(a, dict))
            self.assertGreater(len(done), 2)
            self.assertTrue(all('tokens' not in e and 'tree' not in e and {'open', 'witness', 'root'} <= set(e)
                                for e in done.values()))

    def test_the_driver_keeps_a_bounded_record_of_each_done_job(self):
        # Replicata: fanout on (20, 5) after its 5-solve stop, jobs of at most 4 LP solves, stopped by an error right
        # after its third job's file is saved and run again, its assembly then replaced by a recorder of what it is
        # given; the bytes of each done job's record there, over every object it holds (held), against the open boxes
        # its job file hands back.
        # Expectata (2026-10-26 launch review: rebuilt from their files at a session's start, the records of two
        # 432:12 jobs of 80,000 LP solves took 124,155 and 111,839 bytes, about 110 bytes a fixed position of the boxes
        # they handed back, or 1.4 to 1.6 GB per 1e9 LP solves, past the 2 GiB reservation within a run of 1e9 to
        # 3e10): the same bytes for every record, under 1 KiB, whether its job handed back no box or deep ones, the
        # records loaded at the restart and those of the second session alike; and every job has its record.
        # Resultata before: each record held its job's open boxes' paths, its bytes growing with them.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            real_save, saves = fanout.save, []
            def save(*args):
                real_save(*args)
                saves.append(1)
                if len(saves) == 3: raise KeyboardInterrupt
            with patch.object(fanout, 'save', save), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            given = []
            def assemble(*args):
                given.append(args)
                raise KeyboardInterrupt
            with patch.object(fanout, 'assemble', assemble), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            done = next(a for a in given[0] if isinstance(a, dict))
            files = {f.name.split('.')[0]: fanout.load(f) for f in Path(tmp, 'fanout', 'jobs').glob('*.json.gz')}
            self.assertEqual(set(done), set(files))
            fixed = sorted(sum(map(len, d['open'])) for d in files.values())
            self.assertEqual(fixed[0], 0)
            self.assertGreaterEqual(fixed[-1], 10, fixed)
            sizes = {name: held(e) for name, e in done.items()}
            self.assertEqual(len(set(sizes.values())), 1, sizes)
            self.assertLess(max(sizes.values()), 1024)

    def test_a_job_finishes_its_deep_boxes_and_hands_back_only_shallow_ones(self):
        # Replicata: fanout on (20, 5) with jobs of at most 4 LP solves and DEEP 1, after its 5-solve stop.
        # Expectata (2026-10-23: at 672, 109 jobs had left 6,952 open, each handing back its whole depth-first path):
        # past its budget a job goes on depth first while its next open box lies more than DEEP levels below its own,
        # up to 4 budgets, so it hands back at most DEEP boxes unless it reached 4 budgets; and still excluded.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with patch.object(fanout, 'DEEP', 1):
                outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            ends = [e for e in events(own) if e['event'] == 'job_end']
            self.assertTrue(all(e['open'] <= 1 or e['lps'] >= 16 for e in ends), ends)
            self.assertTrue(any(e['lps'] > 4 for e in ends), ends)

    def test_a_stop_signal_takes_the_workers_down_too(self):
        # Replicata: a child process of this one (a stand-in for a worker), then fanout's handler of SIGTERM called as
        # the signal would call it.
        # Expectata (2026-10-23: a SIGTERM to the driver left its five workers running, orphaned, and the shepherd stops
        # searches below its floor with SIGTERM): the child terminated, and SystemExit raised, so the driver exits.
        import multiprocessing, signal, time
        child = multiprocessing.get_context('spawn').Process(target=time.sleep, args=(60,))
        child.start()
        with self.assertRaises(SystemExit):
            fanout.stop(signal.SIGTERM, None)
        child.join(10)
        self.assertFalse(child.is_alive())

    def test_journal_has_a_header_sessions_jobs_and_a_finish(self):
        # Replicata: fanout on (16, 5) stopped after 2 LP solves.
        # Expectata: its journal, one JSON object per line: a header (version 1, n, order, workers, budget, the roots'
        # count, cases and depths, the run's LP solves and case when stopped, the code), a session, then each job's start (its id, case,
        # depth and root) and end (with its LP solves, seconds and open boxes), and a finish.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(16, 5)
            run, journal = stopped(tmp, prepared, 16, 5, 2)
            outcome, work, own = finish(tmp, run, journal, prepared, 16, 5)
            log = events(own)
            head = log[0]
            self.assertEqual((head['event'], head['version'], head['n'], head['order'], head['workers'], head['budget']),
                             ('header', 1, 16, 5, 2, 4))
            self.assertEqual((head['prefix_lp'], head['prefix_case'], head['code']), (2, 0, focus.fingerprint()))
            all_roots = fanout.roots(run, Path(tmp, 'fanout'), focus.fingerprint())
            self.assertEqual(head['roots'], len(all_roots))
            self.assertEqual((head['root_cases'], head['root_depths']),
                             ([c for c, _ in all_roots], [len(path) for _, path in all_roots]))
            self.assertEqual(log[1]['event'], 'session')
            starts = {e['job']: e for e in log if e['event'] == 'job_start'}
            ends = {e['job']: e for e in log if e['event'] == 'job_end'}
            self.assertEqual(set(starts), set(ends))
            self.assertTrue(all({'case', 'depth', 'root'} <= set(e) for e in starts.values()))
            self.assertTrue(all({'lps', 'seconds', 'open', 'case', 'root'} <= set(e) for e in ends.values()))
            self.assertEqual((log[-1]['event'], log[-1]['outcome']), ('finish', 'excluded'))

    def test_a_session_journals_one_probe_per_case_before_its_first_job(self):
        # Replicata: unpaired()'s two cases, stopped after 1 LP solve, so that both have LP work to do, then fanout.
        # Expectata (2026-10-25: random dives put 672:13 at >= 1e13 LP solves when the page's ETA said 17 h): between
        # the session record and the first job_start, one probe record per case, 0 then 1, each with its event, time,
        # the driver's pid, case, PROBE_PATHS paths, the mean and standard error of their leaf depths (a standard error
        # above 0, the depths differing), least = floor(2^(mean - 1.645 se + 1)) - 1, and witnesses, none for these
        # impossible cases; and still excluded.
        # Resultata before probes: no probe record.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = unpaired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            self.assertEqual({c for c, _ in fanout.roots(run, Path(tmp, 'fanout'), focus.fingerprint())}, {0, 1})
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            log = events(own)
            session = [e['event'] for e in log].index('session')
            first = [e['event'] for e in log].index('job_start')
            probes = log[session + 1:first]
            self.assertEqual([p['case'] for p in probes], [0, 1])
            for p in probes:
                self.assertEqual(set(p), {'event', 'time', 'pid', 'case', 'paths', 'mean', 'se', 'least', 'witnesses'})
                self.assertEqual((p['event'], p['pid'], p['paths'], p['witnesses']),
                                 ('probe', log[session]['pid'], fanout.PROBE_PATHS, []))
                self.assertTrue(0 <= p['mean'] <= 20 and 0 < p['se'] < p['mean'], p)
                self.assertEqual(p['least'], math.floor(2 ** (p['mean'] - 1.645 * p['se'] + 1)) - 1)
            self.assertEqual([e['event'] for e in log].count('probe'), 2)

    def test_every_probe_s_least_is_at_most_its_case_s_lp_solves(self):
        # Replicata: fanout on (20, 5) stopped after 5 LP solves, and on (16, 4) stopped after 3; each has one case.
        # Expectata: the probe's least at most the case's LP solves in all, which it bounds below (95%, one-sided):
        # (20, 5)'s, the run's own (focus.py's 5, in its chunks, and every job's, in fanout's journal: 2026-10-25,
        # tree-only storage left the jobs' out of the chunks) and its whole tree's under fanout's warm starts
        # (tree_lps); (16, 4)'s whole tree's, whose depth first search the witness cut short.
        for n, m, budget in ((20, 5, 5), (16, 4, 3)):
            with self.subTest(n=n, m=m), tempfile.TemporaryDirectory() as tmp:
                prepared = real(n, m)
                run, journal = stopped(tmp, prepared, n, m, budget)
                outcome, work, own = finish(tmp, run, journal, prepared, n, m)
                [p] = [e for e in events(own) if e['event'] == 'probe']
                total = tree_lps(prepared, 0)
                self.assertGreater(p['least'], 0)
                self.assertLessEqual(p['least'], total)
                spent = focus.replay(run, *prepared, focus.fingerprint()).lp + sum(
                    e['lps'] for e in events(own) if e['event'] == 'job_end')
                self.assertTrue(outcome == 'witness' or p['least'] <= spent, (p, spent))
                for x in p['witnesses']:              # a path's exact solution, journaled: as signs, of order m
                    self.assertEqual([sum((2 * t - 1) * i ** k for i, t in enumerate(x)) for k in range(m)], [0] * m)
                print(json.dumps(dict(n=n, order=m, outcome=outcome, mean=p['mean'], se=p['se'], least=p['least'],
                                      tree_lps=total, run_lps=spent)), flush=True)

    def test_probes_do_not_change_the_proof(self):
        # Replicata: (20, 5) stopped after 5 LP solves, then fanout with one worker, twice: as it is, and with its probe
        # replaced by a stand-in that solves no LP.
        # Expectata: the same proof, by the sha256 of every job's tree_sha256 (before tree-only storage, 2026-10-25:
        # of every chunk's records): a probe solves its LPs in the driver, on an LP of its own, and no worker's LP
        # state depends on it.  (With more workers two runs can differ, probes or not: which worker takes which job,
        # and so the LP state a job's first solve starts from, depends on timing.)
        def once(probe):
            with tempfile.TemporaryDirectory() as tmp:
                prepared = real(20, 5)
                run, journal = stopped(tmp, prepared, 20, 5, 5)
                with patch.object(focus, 'prepare', return_value=prepared), \
                        patch.multiple(fanout, WORKERS=1, BUDGET=4, probe=probe):
                    outcome = fanout.run(run, Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl'), 20, 5)
                self.assertEqual(outcome, 'excluded')
                return proof(Path(tmp, 'fanout')), [e['least'] for e in events(Path(tmp, 'fanout.jsonl'))
                                                    if e['event'] == 'probe']
        stand_in = dict(paths=2, mean=0.0, se=0.0, least=1, witnesses=[])
        probed, (least,) = once(fanout.probe)
        unprobed, leasts = once(lambda prepared, case, paths: stand_in)
        self.assertEqual(probed, unprobed)
        self.assertGreater(least, 1)
        self.assertEqual(leasts, [1])

    def test_a_pending_box_takes_2_bytes_a_fixed_position_plus_a_constant(self):
        # Replicata: 432:12's equations (real: one case, no residue counts) stopped after 1 LP solve, at two roots of
        # depth 1; then fanout with one worker and probes that solve no LP, tracemalloc tracing, its pool a stand-in
        # (Inline) under which the first job hands back 4,096 boxes strictly within its own, the siblings along 64
        # random spines 64 positions deep (spined), its result pickled and unpickled as from a worker, and the next
        # submit stops the session by an error; then fanout again, the start of its pool stopping it.  The bytes
        # tracemalloc counts in session from that job's job_end to the next submit, the heap then holding the 4,096
        # boxes; and after the restart from the session record to the pool's start, the heap then holding them and the
        # other root, rebuilt from the job's file.
        # Expectata (2026-10-26 launch review: at 432:12's production shapes a pending box took 632 to 702 bytes in
        # session and 2,540 to 2,937 when a session's start rebuilt it from its job file, about 1 GB per 1e9 LP solves
        # after a restart if every handed-back box stays pending): at most 2 bytes a fixed position plus 160 bytes a
        # box, in session and after the restart alike.
        # Resultata before (scratch/record-20261025/pack/heap/logs/red2.log): 466.7 bytes a box in session, without the
        # pairs it shares with the worker's result, and 2,640.4 after the restart: a box was key's (case, path), its
        # path a tuple of (position, value) tuples, rebuilt one tuple a pair from the job file at a restart.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(432, 12)
            run, journal = stopped(tmp, prepared, 432, 12, 1)
            work, own = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
            roots = fanout.roots(run, work, focus.fingerprint())
            self.assertEqual([len(path) for _, path in roots], [1, 1])
            boxes = spined(roots[0][1], 432, 64, 64, 20261026)
            result = pickle.loads(pickle.dumps(dict(tree=[['L']], tree_sha256=fanout.digest([['L']]), open=boxes,
                                                    seconds=0.0, witness=None)))
            real_note, marks, held = fanout.note, {}, []
            def note(path, event, **fields):
                real_note(path, event, **fields)
                marks[event] = tracemalloc.get_traced_memory()[0]
            def stop(since):               # the bytes traced since the last note of event since; then an error
                held.append(tracemalloc.get_traced_memory()[0] - marks[since])
                raise KeyboardInterrupt
            hands = [lambda: result, lambda: stop('job_end')]
            stand_in = dict(paths=2, mean=0.0, se=0.0, least=1, witnesses=[])
            tracemalloc.start()
            try:
                with patch.object(focus, 'prepare', return_value=prepared), \
                        patch.multiple(fanout, WORKERS=1, note=note, probe=lambda *args: stand_in):
                    with patch.object(fanout, 'ProcessPoolExecutor', lambda *args, **kwargs: Inline(
                            lambda job: hands.pop(0)())), self.assertRaises(KeyboardInterrupt):
                        fanout.run(run, work, own, 432, 12)
                    with patch.object(fanout, 'ProcessPoolExecutor', lambda *args, **kwargs: stop('session')), \
                            self.assertRaises(KeyboardInterrupt):
                        fanout.run(run, work, own, 432, 12)
            finally:
                tracemalloc.stop()
            fixed = sum(map(len, boxes))
            pending = {'in session': (len(boxes), fixed), 'after a restart': (len(boxes) + 1, fixed + 1)}
            self.assertEqual(len(held), 2)
            for (when, (count, positions)), size in zip(pending.items(), held):
                print(json.dumps(dict(when=when, boxes=count, fixed=positions, bytes=size,
                                      per_box=round(size / count, 1),
                                      per_box_less_2_a_position=round((size - 2 * positions) / count, 1))), flush=True)
            for (when, (count, positions)), size in zip(pending.items(), held):
                self.assertLessEqual(size, 2 * positions + 160 * count, when)

    def test_pack_takes_2_bytes_a_position_and_refuses_what_does_not_fit(self):
        # Replicata: fanout.pack of a path as a worker's result holds it (tuples) and as a job file holds it (lists),
        # positions up to 2^15 - 1; then of each path holding a pair that does not fit: position 2^15, position -1,
        # value 2, value True, position 3.0, a pair of three.
        # Expectata (2026-10-26, the driver's pending boxes packed): 2 bytes a fixed position, unpack giving back key's
        # tuple of (int, int) pairs, so the same job id; each pair that does not fit refused with an error (the
        # three-item pair's by its unpacking), none packed.
        path = ((431, 1), (0, 0), (2 ** 15 - 1, 1), (256, 0))
        for given in (path, [list(p) for p in path]):
            packed = fanout.pack(given)
            self.assertEqual((type(packed), len(packed)), (bytes, 2 * len(path)))
            self.assertEqual(fanout.unpack(packed), fanout.key(7, given)[1])
            self.assertTrue(all(type(t) is int for p in fanout.unpack(packed) for t in p))
            self.assertEqual(fanout.jid((7, fanout.unpack(packed))), fanout.jid(fanout.key(7, given)))
        self.assertEqual((fanout.pack(()), fanout.unpack(b'')), (b'', ()))
        for pair in ((2 ** 15, 0), (-1, 0), (3, 2), (3, True), (3.0, 1), (3, 1, 0)):
            with self.subTest(pair=pair), self.assertRaises((AssertionError, ValueError)):
                fanout.pack(path + (pair,))

    def resumed(self, tmp, prepared, n, m, budget, ends):
        """focus.py's run on prepared stopped after budget LP solves, then fanout with one worker, so that its code
        alone decides the order in which jobs end and each job's LP state (its worker's), and jobs of at most 4 LP
        solves: stopped by an error right after its ends-th job_end, then run again to its finish.  The outcome, the
        run's directory, and fanout's work directory and journal."""
        run, journal = stopped(tmp, prepared, n, m, budget)
        work, own, real_note = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl'), fanout.note
        def note(path, event, **fields):
            real_note(path, event, **fields)
            if [e['event'] for e in events(path)].count('job_end') == ends: raise KeyboardInterrupt
        with patch.object(focus, 'prepare', return_value=prepared), patch.multiple(fanout, WORKERS=1, BUDGET=4):
            with patch.object(fanout, 'note', note), self.assertRaises(KeyboardInterrupt):
                fanout.run(run, work, own, n, m)
            return fanout.run(run, work, own, n, m), run, work, own

    def test_one_worker_s_job_starts_and_trees_are_the_ones_before_the_boxes_were_packed(self):
        # Replicata: resumed on (20, 5), stopped after 5 LP solves, fanout stopped after its 3rd job_end, then
        # reprove.run with one worker; and on (16, 4), stopped after 3 LP solves, fanout stopped after its 2nd job_end.
        # Expectata (2026-10-26, the driver's pending boxes packed: fanout.pack): as the code before made them, recorded
        # 2026-10-26 with HiGHS 1.12.0 as SciPy 1.17.1 bundles it (sequences): the job_starts' [job, case, depth, root]
        # and the job_ends' [job, tree_sha256], each in the journal's order, both sessions'; (20, 5) excluded, so
        # assembled, then reproven from scratch, with the counts below; (16, 4) a witness, Thue-Morse.
        # Green before the change too, as recorded from it, and red under a farm whose ties go the other way, the last
        # of equally deep boxes put on the heap going first (scratch/record-20261025/pack/heap/mutant.py).  With 2
        # workers, timing decides which worker takes which job, so two runs of the same code can differ
        # (scratch/record-20261025/pack/heap/logs/determinism.log).
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            outcome, run, work, own = self.resumed(tmp, prepared, 20, 5, 5, 3)
            with patch.object(focus, 'prepare', return_value=prepared):
                total = reprove.run(run, work, own, 20, 5, 1)
            made = dict(outcome=outcome, **sequences(own),
                        reproven={k: total[k] for k in ('jobs', 'nodes', 'leaves', 'attempts')})
            print(json.dumps(dict(n=20, order=5, **made)), flush=True)
            self.assertEqual(made, dict(
                outcome='excluded', starts=19, ends=19,
                starts_sha256='af560130d2c9970be74fd958642a948d53d93ba43def2371362b49964440504b',
                ends_sha256='c27b80d7e541b115984be9fec16e1a383f51da5bd6a8391edbb695fc43b16e7c',
                reproven=dict(jobs=19, nodes=46, leaves=24, attempts=dict(warm=24, cold=0, primal=0))))
        with tempfile.TemporaryDirectory() as tmp:
            outcome, run, work, own = self.resumed(tmp, real(16, 4), 16, 4, 3, 2)
            made = dict(outcome=outcome, **sequences(own), witness=events(own)[-1]['witness'])
            print(json.dumps(dict(n=16, order=4, **made)), flush=True)
            self.assertEqual(made, dict(
                outcome='witness', starts=10, ends=10,
                starts_sha256='5792115425923a89eb2b1ab1c14ef2d07cc8c88bf0f2be4017732f936cdf1fcf',
                ends_sha256='b8b30e7d2696922e8977c870290ebd2e0b7b375818a105af1c0c6cecb936f9fd',
                witness=[p.bit_count() % 2 for p in range(16)]))      # Thue-Morse, 0110100110010110

    def test_assembly_s_memory_does_not_grow_with_the_journal(self):
        # Replicata: fanout on (20, 5) to its finish after its 5-solve stop; fanout.assemble on it, as fanout.run calls
        # it, under tracemalloc; then its journal given 100 more copies of each of its job_start and job_end records,
        # in its order (a long run's journal holds about two records a job), and assembly again.  The peak bytes that
        # tracemalloc counts in each, from fanout.finished's read of the job files to assembly's return.
        # Expectata (2026-10-26 pack review: assembly parsed the whole journal into a list of dicts and kept it through
        # its walk, at 432:12 1,856 bytes a job, or 0.70 GB at 3e10 LP solves, with the journal's text and lines while
        # it parsed them): the same jobs, in the same order, and the second peak at most 64 KiB above the first, the
        # journal read one record at a time.
        # Resultata before (scratch/record-20261025/pack/fix/logs/red.log): with 3,800 records more, the second peak
        # 4,237,175 bytes above the first, 1,115.0 bytes a record: assembly kept a list of every record.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            code = focus.fingerprint()
            roots = fanout.roots(run, work, code)
            padding = [r for r in events(own) if r['event'] in ('job_start', 'job_end')] * 100
            peaks, walks = [], []
            for extra in ([], padding):
                with open(own, 'a', encoding='utf-8') as f:
                    f.write(''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in extra))
                tracemalloc.start()
                try:
                    walks.append(fanout.assemble(run, work, own, prepared, code, roots, fanout.finished(work)))
                    peaks.append(tracemalloc.get_traced_memory()[1])
                finally:
                    tracemalloc.stop()
            print(json.dumps(dict(records=len(padding), peaks=peaks, growth=peaks[1] - peaks[0],
                                  per_record=round((peaks[1] - peaks[0]) / len(padding), 1))), flush=True)
            self.assertGreater(len(padding), 2000)
            self.assertEqual(walks[0], walks[1])
            self.assertLessEqual(peaks[1] - peaks[0], 64 << 10)


if __name__ == '__main__':
    unittest.main()
