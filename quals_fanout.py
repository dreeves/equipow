"""Quals for fanout.py: a stopped focus.py run finished by parallel workers, its proof spliced back as focus.py chunks
that focus.py itself, unchanged, replays and checks.  Run with PYTHONPATH=scratch/lower24-design/beyond1000/pylib
/opt/homebrew/bin/python3 -B -m unittest quals_fanout."""
import fcntl
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import certbb
import focus
import mstar
import fanout


def real(n, m):
    """focus.py's own equations for length n and order m, one case with no residue counts."""
    return focus.moments(n, m), ((),)


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
        return fanout.run(run, journal, work, own, n, m), work, own


def events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


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

    def test_a_stopped_run_is_finished_as_chunks_focus_replays(self):
        # Replicata: (20, 5), order 5 at length 20, impossible (m*(20) = 3), stopped after 5 LP solves, then fanout
        # with two workers and jobs of at most 4 LP solves.
        # Expectata: excluded; jobs handed back open boxes (several jobs, some with open children); focus.replay of the
        # run's chunks, the spliced ones with them, finds case 0 completed and nothing open; and fanout's last act was
        # focus.search itself, which wrote its finish, excluded, to focus.py's journal.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            done = focus.replay(run, *prepared, focus.fingerprint())
            self.assertEqual((done.completed, done.frontier, done.outcome), ([0], [], 'excluded'))
            self.assertEqual(done.lp, done.split + done.closed)
            ends = [e for e in events(own) if e['event'] == 'job_end']
            self.assertGreater(len(ends), 2)
            self.assertTrue(all(e['lps'] <= 4 for e in ends))
            self.assertTrue(any(e['open'] for e in ends))
            self.assertEqual(events(journal)[-1]['event'], 'finish')
            self.assertEqual(events(journal)[-1]['outcome'], 'excluded')
            self.assertEqual(events(own)[-1]['outcome'], 'excluded')

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

    def test_a_forged_job_fails_the_splice(self):
        # Replicata: fanout on (20, 5) with its splice stubbed out, one saved job's certificate zeroed, then fanout
        # again.
        # Expectata: certbb.ProofError: the splice feeds every token through focus.py's exact checker.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            with patch.object(fanout, 'splice', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            for f in sorted(Path(tmp, 'fanout', 'jobs').glob('*.json.gz')):
                with gzip.open(f, 'rt') as stream: job = json.load(stream)
                leaves = [t for t in job['tokens'] if t[0] == 'L']
                if leaves:
                    leaves[0][1] = [0] * len(leaves[0][1])
                    with gzip.open(f, 'wt') as stream: json.dump(job, stream)
                    break
            with self.assertRaises(certbb.ProofError):
                finish(tmp, run, journal, prepared, 20, 5)

    def test_the_driver_keeps_no_tokens_in_memory(self):
        # Replicata: fanout on (20, 5), its splice replaced by a recorder of what it is given.
        # Expectata: the driver's record of done jobs holds each job's open boxes, witness and root, but no tokens:
        # at 672 a job's tokens are tens of megabytes, and the splice reads them back from the job files one at a time.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            given = []
            def splice(*args):
                given.append(args)
                raise KeyboardInterrupt
            with patch.object(fanout, 'splice', splice), self.assertRaises(KeyboardInterrupt):
                finish(tmp, run, journal, prepared, 20, 5)
            done = next(a for a in given[0] if isinstance(a, dict))
            self.assertGreater(len(done), 2)
            self.assertTrue(all('tokens' not in e and {'open', 'witness', 'root'} <= set(e) for e in done.values()))

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


if __name__ == '__main__':
    unittest.main()
