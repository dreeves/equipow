"""Quals for shepherd.py, which keeps the searches running by dreeves's principles of 2026-10-23."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import shepherd

UNBOUNDED = ('--seconds', 'inf', '--lp-budget', '1000000000000000000')


def search(directory, name='480:14', n='480', memory=64 << 20, processes=1):
    d = Path(directory)
    return shepherd.Search(name, 'focus.py', (n,) + UNBOUNDED, str(d / f'focus_{n}_journal.jsonl'),
                           str(d / f'focus_{n}.log'), str(d / f'run{n}.err'), str(d / f'run{n}'), memory, processes)


def proc(pid, command, stat='SN'):
    return (pid, 1, stat, command)


def write(path, *records):
    Path(path).write_text(''.join(json.dumps(r) + '\n' for r in records))


SESSION = dict(event='session', time=100, pid=7)
UPDATE = dict(event='update', time=105, pid=7, lp=1, closed=0, split=1, pending=2, case=0, completed=[], outcome=None)


def finish(outcome):
    return dict(UPDATE, event='finish', time=110, outcome=outcome)


class ShepherdQuals(unittest.TestCase):
    def test_status_comes_from_the_process_list_and_the_journal(self):
        # Replicata: one search's journal missing, then ending in each kind of record, with no process; then a process.
        # Expectata: no journal or a budget finish: launchable; an excluded or witness finish: done; anything else (a
        # session or an update last: a crash, a kill, a reboot or a stop): stopped; a process running it: running,
        # with its pid, whatever its journal says; a zombie runs nothing.
        with tempfile.TemporaryDirectory() as d:
            s = search(d)
            self.assertEqual(shepherd.status(s, []), ('launchable', None))
            for last, want in ((finish('budget'), 'launchable'), (finish('excluded'), 'done'),
                               (finish('witness'), 'done'), (UPDATE, 'stopped'), (SESSION, 'stopped')):
                write(s.journal, dict(event='header', version=1), SESSION, last)
                self.assertEqual(shepherd.status(s, []), (want, None), last)
            running = proc(42, '/opt/homebrew/bin/python3 -B focus.py 480 --seconds inf --lp-budget 1000000000000000000')
            self.assertEqual(shepherd.status(s, [running]), ('running', 42))
            self.assertEqual(shepherd.status(s, [proc(43, 'python3 -B focus.py 480', 'Z')]), ('stopped', None))
            self.assertEqual(shepherd.status(s, [proc(44, 'python3 -B focus.py 4800')]), ('stopped', None))

    def test_a_shell_mentioning_the_command_runs_nothing(self):
        # Replicata: a live focus.py 480, and a shell whose command line launched it.
        # Expectata (2026-10-23: such a shell crashed the shepherd, "2 processes run 672:13 fanout"): running, the
        # Python process's pid.
        with tempfile.TemporaryDirectory() as d:
            procs = [proc(42, '/opt/homebrew/bin/python3 -B focus.py 480 --seconds inf'),
                     proc(43, "/bin/bash -c 'nohup nice -n 15 /opt/homebrew/bin/python3 -B focus.py 480 >> focus_480.log &'")]
            self.assertEqual(shepherd.status(search(d), procs), ('running', 42))

    def test_paused_interpreter_retains_identity_without_running_or_launching(self):
        # Replicata: an in-memory pause, with and without an existing journal.
        # Expectata: paused with the same pid; no launch or stop at either disk floor.
        with tempfile.TemporaryDirectory() as d:
            s = search(d)
            paused = proc(42, 'python3 -B focus.py 480', 'TN')
            for records in ((), (SESSION, UPDATE)):
                write(s.journal, *records)
                self.assertEqual(shepherd.status(s, [paused]), ('paused', 42))
                for free in (shepherd.FLOOR, shepherd.FLOOR - 1, shepherd.HARD_FLOOR - 1):
                    self.assertEqual(shepherd.decide({s.name: 'paused'}, {s.name: 9}, free), [])

    def test_paused_data_does_not_hide_running_search_from_disk_floor(self):
        # Replicata: paused 480 has more stored data than running 672.
        # Expectata: both disk floors stop only 672; resumed 480 follows the ordinary policy.
        statuses, data = {'480': 'paused', '672': 'running'}, {'480': 9, '672': 5}
        for free in (shepherd.FLOOR - 1, shepherd.HARD_FLOOR - 1):
            self.assertEqual(shepherd.decide(statuses, data, free), [('stop', '672')])
        self.assertEqual(shepherd.decide({'480': 'running', '672': 'stopped'}, data,
                                        shepherd.FLOOR - 1), [('stop', '480')])

    def test_a_partial_last_line_is_not_a_record(self):
        # Replicata: a journal whose last line was cut off mid-write after a finish.
        # Expectata: the complete lines decide: the finish before it.
        with tempfile.TemporaryDirectory() as d:
            s = search(d)
            Path(s.journal).write_text(json.dumps(finish('excluded')) + '\n{"event":"upd')
            self.assertEqual(shepherd.status(s, []), ('done', None))

    def test_two_processes_for_one_search_fail_loudly(self):
        # Replicata: two live processes both running focus.py 480.
        # Expectata: AssertionError: one search, one process.
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AssertionError):
                shepherd.status(search(d), [proc(1, 'python3 -B focus.py 480'), proc(2, 'python3 -B focus.py 480')])

    def test_two_floors(self):
        # Replicata: five searches, launchable a, running b and c, stopped d and done e, holding 0, 5, 1, 3 and 9
        # bytes of data, at free disk of the floor, a byte below it, and a byte below the hard floor; then b stopped,
        # then c grown to 6 bytes.
        # Expectata (dreeves, 2026-10-23: "fine, 2 floors if you're sure"): at the floor or above, launch each
        # launchable search and nothing else; below it, launch nothing and stop the search with the most data of
        # those not done, b, if it runs: once b is stopped, c runs on, until it holds more than b; below the hard
        # floor, stop every running search.  A done search's data counts for nothing: it no longer grows.  A stopped
        # or done search is never launched (principle 2).
        statuses = {'a': 'launchable', 'b': 'running', 'c': 'running', 'd': 'stopped', 'e': 'done'}
        data = {'a': 0, 'b': 5, 'c': 1, 'd': 3, 'e': 9}
        self.assertEqual(shepherd.decide(statuses, data, shepherd.FLOOR), [('launch', 'a')])
        self.assertEqual(shepherd.decide(statuses, data, shepherd.FLOOR - 1), [('stop', 'b')])
        self.assertEqual(shepherd.decide(statuses, data, shepherd.HARD_FLOOR - 1), [('stop', 'b'), ('stop', 'c')])
        stopped = dict(statuses, b='stopped')
        self.assertEqual(shepherd.decide(stopped, data, shepherd.FLOOR - 1), [])
        self.assertEqual(shepherd.decide(stopped, dict(data, c=6), shepherd.FLOOR - 1), [('stop', 'c')])
        self.assertEqual(shepherd.decide({'e': 'done'}, {'e': 9}, shepherd.FLOOR - 1), [])
        self.assertLess(shepherd.HARD_FLOOR, shepherd.FLOOR)

    def test_a_search_s_data_is_its_directory_s_bytes(self):
        # Replicata: a data directory holding files of 3 and 4 bytes, one in a subdirectory; no directory; and a
        # listing naming a file that is gone.
        # Expectata: 7 bytes; 0 bytes for none; 0 for the gone file.
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'run', 'sub').mkdir(parents=True)
            Path(d, 'run', 'a').write_bytes(b'abc')
            Path(d, 'run', 'sub', 'b').write_bytes(b'abcd')
            self.assertEqual(shepherd.used(str(Path(d, 'run'))), 7)
            self.assertEqual(shepherd.used(str(Path(d, 'none'))), 0)
            # a file listed, then renamed away before it is measured, as focus.py renames its checkpoints into place
            with patch.object(shepherd.os, 'walk', return_value=[(d, [], ['gone.tmp'])]):
                self.assertEqual(shepherd.used(d), 0)

    def test_slots_and_memory_are_asserted_of_searches_not_done(self):
        # Replicata: SLOTS + 1 one-process searches, then the same with one done, and with one stopped; then two whose
        # memory exceeds MEMORY; then two searches of SLOTS - 1 processes and 2 processes.
        # Expectata: a search beyond the slots or the memory fails loudly (preemption, principle 3, is not built);
        # only running and launchable searches take them: a done or stopped one runs no process (2026-10-23: 672's
        # focus.py run, stopped while fanout.py finishes it); slots count processes (fanout.py runs several).
        with tempfile.TemporaryDirectory() as d:
            many = [search(d, f'{n}:1', str(n)) for n in range(shepherd.SLOTS + 1)]
            with self.assertRaises(AssertionError):
                shepherd.admit(many, {s.name: 'running' for s in many})
            shepherd.admit(many, {s.name: 'done' if s is many[0] else 'running' for s in many})
            shepherd.admit(many, {s.name: 'stopped' if s is many[0] else 'launchable' for s in many})
            big = [search(d, f'{n}:1', str(n), shepherd.MEMORY // 2 + 1) for n in range(2)]
            with self.assertRaises(AssertionError):
                shepherd.admit(big, {s.name: 'launchable' for s in big})
            wide = [search(d, 'a:1', '1', processes=shepherd.SLOTS - 1), search(d, 'b:1', '2', processes=2)]
            with self.assertRaises(AssertionError):
                shepherd.admit(wide, {s.name: 'running' for s in wide})
            shepherd.admit(wide[:1] + [search(d, 'b:1', '2')], {'a:1': 'running', 'b:1': 'running'})

    def test_a_launch_runs_unbounded_single_threaded_at_nice_15(self):
        # Replicata: launch the 480:14 search with subprocess.Popen replaced by a recorder.
        # Expectata: Homebrew's Python with -B, the script and its unbounded arguments, at the shepherd's own niceness,
        # NICE, which it inherits (2026-10-23: a nice -n 15 on top made fanout.py's workers 20); the repo as cwd; the
        # pylib path and single-threaded BLAS in the environment; no stdin; output and errors appended to its files; a
        # session of its own, so that it outlives the shepherd.
        calls = []
        class Recorder:
            def __init__(self, argv, **kw):
                calls.append((argv, kw))
                self.pid = 99
        with tempfile.TemporaryDirectory() as d, patch.object(shepherd.subprocess, 'Popen', Recorder):
            s = search(d)
            child = shepherd.launch(s)
            [(argv, kw)] = calls
            self.assertEqual(child.pid, 99)
            self.assertEqual(argv, [shepherd.PYTHON, '-B', 'focus.py', '480', *UNBOUNDED])
            self.assertEqual(kw['cwd'], shepherd.HERE)
            self.assertEqual(kw['env']['PYTHONPATH'], shepherd.PYLIB)
            for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
                self.assertEqual(kw['env'][k], '1')
            self.assertIs(kw['stdin'], shepherd.subprocess.DEVNULL)
            self.assertEqual((kw['stdout'].name, kw['stdout'].mode), (s.out, 'a'))
            self.assertEqual((kw['stderr'].name, kw['stderr'].mode), (s.err, 'a'))
            self.assertIs(kw['start_new_session'], True)

    def test_eight_workers_fit_with_paused_480_but_not_with_running_480(self):
        # Replicata: the approved eight-worker allocation with 480 paused in memory.
        # Expectata: eight slots admitted; resuming 480 while those workers live fails loudly.
        self.assertEqual(shepherd.SLOTS, 8)
        statuses = {'480:14': 'paused', '672:13': 'stopped', '672:13 fanout': 'running'}
        shepherd.admit(shepherd.SEARCHES, statuses)
        with self.assertRaises(AssertionError):
            shepherd.admit(shepherd.SEARCHES, dict(statuses, **{'480:14': 'running'}))

    def test_paused_memory_still_counts_toward_the_memory_limit(self):
        # Replicata: a paused search retains the memory budget and an active search needs one byte more.
        # Expectata: resident memory remains counted despite the zero compute-slot cost.
        with tempfile.TemporaryDirectory() as d:
            searches = [search(d, 'paused', memory=shepherd.MEMORY), search(d, 'active', memory=1)]
            with self.assertRaises(AssertionError):
                shepherd.admit(searches, {'paused': 'paused', 'active': 'running'})

    def test_registry_is_today_s_searches(self):
        # Historical specification (2026-10-23):
        # Replicata: shepherd.SEARCHES, and the command lines of the two focus searches running on 2026-10-23.
        # Expectata: 480:14 and 672:13, each focus.py with no budget, its journal, log, error file and checkpoint
        # directory, 64 MiB of memory (56 MB at most measured) and one process, each matching its own running command
        # line only; and fanout.py 672 (dreeves, 2026-10-23: "ok" to finishing 672:13 in parallel), its 5 workers,
        # 1 GiB in all.
        # The approved allocation now assigns eight workers and a 2 GiB reservation to fanout.
        self.assertEqual([(s.name, s.script, s.args) for s in shepherd.SEARCHES],
                         [('480:14', 'focus.py', ('480',) + UNBOUNDED), ('672:13', 'focus.py', ('672',) + UNBOUNDED),
                          ('672:13 fanout', 'fanout.py', ('672',))])
        self.assertEqual([(s.journal, s.out, s.err, s.data, s.memory, s.processes) for s in shepherd.SEARCHES],
                         [('focus_480_journal.jsonl', 'focus_480.log', 'scratch/focus480/run.err', 'scratch/focus480/run', 64 << 20, 1),
                          ('focus_672_journal.jsonl', 'focus_672.log', 'scratch/focus672/run.err', 'scratch/focus672/run', 64 << 20, 1),
                          ('fanout_672_journal.jsonl', 'fanout_672.log', 'scratch/fanout672/run.err', 'scratch/fanout672', 2 << 30, 8)])
        command = '/opt/homebrew/Cellar/python@3.13/3.13.6/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python -B focus.py {} --seconds inf --lp-budget 1000000000000000000'
        procs = [proc(1, command.format(480)), proc(2, command.format(672))]
        with patch.object(shepherd, 'last_record', return_value=None):
            self.assertEqual([shepherd.status(s, procs) for s in shepherd.SEARCHES[:2]], [('running', 1), ('running', 2)])
            self.assertEqual(shepherd.status(shepherd.SEARCHES[2], procs), ('launchable', None))

    def test_a_watch_logs_each_change_once_and_acts(self):
        # Replicata: three loops of main over a launchable search and a running one: the launched one's process
        # listed from the second, the running one gone in the third (its journal last an update, its error file a
        # traceback), with Popen and the clock stubbed; free disk at the floor.
        # Expectata: the log, one JSON object per line: a start; each search's status once when first seen and again
        # only when it changes; the launch, with its pid; the launched search as running; the gone search as stopped,
        # with its journal's last record and its error file's tail; and nothing relaunched.
        with tempfile.TemporaryDirectory() as d:
            a, b = search(d, '480:14', '480'), search(d, '672:13', '672')
            write(b.journal, dict(event='header', version=1), SESSION, UPDATE)
            Path(b.err).write_text('Traceback (most recent call last):\nAssertionError\n')
            listings = iter([[proc(5, 'python3 -B focus.py 672')],
                             [proc(5, 'python3 -B focus.py 672'), proc(77, 'python3 -B focus.py 480')],
                             [proc(77, 'python3 -B focus.py 480')]])
            class Stop(Exception): pass
            sleeps = []
            def sleep(s):
                sleeps.append(s)
                if len(sleeps) == 3: raise Stop
            class Child:
                def __init__(self, argv, **kw): self.pid = 77
                def poll(self): return None
            log = Path(d, 'shepherd.log')
            with patch.multiple(shepherd, SEARCHES=(a, b), LOG=str(log), LOCK=str(Path(d, 'lock')), HERE=d), \
                 patch.object(shepherd.subprocess, 'Popen', Child), \
                 patch.object(shepherd, 'processes', lambda: next(listings)), \
                 patch.object(shepherd, 'free_disk', lambda: shepherd.FLOOR), \
                 patch.object(shepherd.os, 'nice', return_value=15), \
                 patch.object(shepherd.time, 'sleep', sleep), self.assertRaises(Stop):
                shepherd.main([])
            events = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([(e['event'], e.get('search'), e.get('status')) for e in events],
                             [('start', None, None), ('status', '480:14', 'launchable'), ('status', '672:13', 'running'),
                              ('launch', '480:14', None), ('status', '480:14', 'running'), ('status', '672:13', 'stopped')])
            self.assertEqual((events[3]['pid'], events[4]['pid']), (77, 77))
            self.assertEqual(events[5]['last'], UPDATE)
            self.assertIn('AssertionError', events[5]['err'])
            self.assertEqual(sleeps, [shepherd.REFRESH] * 3)

    def test_below_the_floor_main_stops_the_running_search_and_never_relaunches_it(self):
        # Replicata: main over one running search (pid 5) with free disk a byte below the floor; then its process gone
        # (its journal last an update) with the floor met again; os.kill recorded, Popen forbidden.
        # Expectata: SIGTERM to pid 5, logged as a stop with the free disk; then the search stopped, and no launch:
        # a stopped search waits for a human (principle 2), whatever the disk.
        with tempfile.TemporaryDirectory() as d:
            s = search(d)
            write(s.journal, dict(event='header', version=1), SESSION, UPDATE)
            listings = iter([[proc(5, 'python3 -B focus.py 480')], []])
            frees = iter([shepherd.FLOOR - 1, shepherd.FLOOR])
            kills = []
            class Stop(Exception): pass
            sleeps = []
            def sleep(t):
                sleeps.append(t)
                if len(sleeps) == 2: raise Stop
            def popen(*a, **kw): raise AssertionError('no launch')
            log = Path(d, 'shepherd.log')
            with patch.multiple(shepherd, SEARCHES=(s,), LOG=str(log), LOCK=str(Path(d, 'lock')), HERE=d), \
                 patch.object(shepherd.subprocess, 'Popen', popen), \
                 patch.object(shepherd.os, 'kill', lambda pid, sig: kills.append((pid, sig))), \
                 patch.object(shepherd, 'processes', lambda: next(listings)), \
                 patch.object(shepherd, 'free_disk', lambda: next(frees)), \
                 patch.object(shepherd.os, 'nice', return_value=15), \
                 patch.object(shepherd.time, 'sleep', sleep), self.assertRaises(Stop):
                shepherd.main([])
            self.assertEqual(kills, [(5, shepherd.signal.SIGTERM)])
            events = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([(e['event'], e.get('status'), e.get('pid'), e.get('free')) for e in events],
                             [('start', None, os.getpid(), None), ('status', 'running', 5, None),
                              ('stop', None, 5, shepherd.FLOOR - 1), ('status', 'stopped', None, None)])

    def test_floor_transition_preserves_paused_480_and_does_not_restart_the_fanout(self):
        # Replicata: eight workers below the floor with 480 paused; then the guardian resumes 480 after they stop.
        # Expectata: only the running search receives SIGTERM in each phase; restored disk launches neither search.
        with tempfile.TemporaryDirectory() as d:
            a = search(d)
            b = shepherd.Search('672:13 fanout', 'fanout.py', ('672',), str(Path(d, 'fanout_journal.jsonl')),
                                str(Path(d, 'fanout.log')), str(Path(d, 'fanout.err')),
                                str(Path(d, 'fanout')), 2 << 30, 8)
            for s in (a, b): write(s.journal, SESSION, UPDATE)
            listings = iter([[proc(5, 'python3 -B focus.py 480', 'TN'), proc(6, 'python3 -B fanout.py 672')],
                             [proc(5, 'python3 -B focus.py 480')], [], []])
            frees = iter([shepherd.FLOOR - 1] * 3 + [shepherd.FLOOR])
            kills = []
            log = Path(d, 'shepherd.log')
            with open(Path(d, 'lock'), 'a') as held, \
                 patch.multiple(shepherd, SEARCHES=(a, b), LOG=str(log), HERE=d), \
                 patch.object(shepherd, 'lock', return_value=held), \
                 patch.object(shepherd, 'used', side_effect=lambda path: {a.data: 9, b.data: 5}[path]), \
                 patch.object(shepherd.subprocess, 'Popen', side_effect=AssertionError('no launch')), \
                 patch.object(shepherd.os, 'kill', side_effect=lambda pid, sig: kills.append((pid, sig))), \
                 patch.object(shepherd, 'processes', side_effect=lambda: next(listings)), \
                 patch.object(shepherd, 'free_disk', side_effect=lambda: next(frees)), \
                 patch.object(shepherd.os, 'nice', return_value=15), \
                 patch.object(shepherd.time, 'sleep', side_effect=[None, None, None, StopIteration]), \
                 self.assertRaises(StopIteration):
                shepherd.main([])
            self.assertEqual(kills, [(6, shepherd.signal.SIGTERM), (5, shepherd.signal.SIGTERM)])
            events = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([(e['search'], e['status'], e['pid']) for e in events if e['event'] == 'status'],
                             [(a.name, 'paused', 5), (b.name, 'running', 6), (a.name, 'running', 5),
                              (b.name, 'stopped', None), (a.name, 'stopped', None)])

    def test_a_second_shepherd_fails_loudly(self):
        # Replicata: the shepherd's lock taken, then taken again from another open file, as a second process would.
        # Expectata: the second fails (BlockingIOError), so that two shepherds never act at once.
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d, 'lock'))
            first = shepherd.lock(path)
            with self.assertRaises(BlockingIOError):
                shepherd.lock(path)
            first.close()


if __name__ == '__main__':
    unittest.main()
