"""Disposable-process quals for an unbounded fanout lease; no production PID."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import fanout_lease as lease


CHILD = '''import json, os, pathlib, subprocess, sys, time
worker = subprocess.Popen([sys.executable, '-c',
    'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(60)'],
    stdout=subprocess.PIPE, text=True)
assert worker.stdout.readline() == 'ready\\n'
state = subprocess.check_output(['/bin/ps', '-p', sys.argv[1], '-o', 'stat='], text=True).strip()
pathlib.Path(sys.argv[2]).write_text(json.dumps(dict(pids=[os.getpid(),worker.pid], paused=state.startswith('T'))))
result = {'normal': lambda: 0, 'nonzero': lambda: 7, 'wait': lambda: time.sleep(60)}[sys.argv[3]]()
raise SystemExit(result)
'''


def state(pid):
    return subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'stat='],
                          capture_output=True, text=True).stdout.strip()


class FanoutLeaseQuals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.child = self.path / 'child.py'
        self.child.write_text(CHILD)
        self.record, self.journal = self.path / 'pids.json', self.path / 'pauses.jsonl'
        self.focus = subprocess.Popen([sys.executable, '-c',
                                       'import time;print("ready",flush=True);time.sleep(60)'],
                                      stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.focus.stdout.readline(), 'ready\n')
        self.expected = lease.identity(self.focus.pid)[0]

    def tearDown(self):
        self.focus.kill()
        self.focus.wait()
        self.focus.stdout.close()
        self.tmp.cleanup()

    def command(self, mode):
        return [sys.executable, str(self.child), str(self.focus.pid), str(self.record), mode]

    def resumed(self):
        self.assertNotIn(state(self.focus.pid)[:1], ('', 'T', 'Z'))
        records = [json.loads(s) for s in self.journal.read_text().splitlines()]
        self.assertEqual([r['event'] for r in records], ['pause', 'resume'])
        self.assertLessEqual(records[0]['time'], records[1]['time'])
        for r in records:
            self.assertEqual(set(r), {'event', 'time', 'pid', 'start', 'command'})
            self.assertEqual((r['pid'], r['start'], r['command']), (self.focus.pid, *self.expected))

    def cleaned(self):
        self.resumed()
        data = json.loads(self.record.read_text())
        self.assertTrue(data['paused'])
        deadline = time.monotonic() + 3
        live = data['pids']
        while live and time.monotonic() < deadline:
            live = [p for p in live if state(p)[:1] not in ('', 'Z')]
            time.sleep(.01)
        self.assertEqual(live, [])

    def test_normal_and_nonzero_exit(self):
        # Replicata: a child exits, leaving a TERM-ignoring descendant.
        # Expectata: kill the owned group, resume the toy, and record both transitions.
        # Resultata before implementation: no unbounded lease exists.
        for mode, code in (('normal', 0), ('nonzero', 7)):
            with self.subTest(mode=mode):
                self.assertEqual(lease.run(self.focus.pid, self.expected, self.command(mode), self.journal), code)
                self.cleaned()
                self.journal.unlink()

    def test_term_and_int_cleanup(self):
        # Replicata: cancellation while a disposable lease owns a running child group.
        # Expectata: both cancellation signals clean up and resume, with a complete pause pair.
        # Resultata before implementation: no unbounded lease exists.
        code = ('import json,sys;import fanout_lease as f;'
                'f.run(int(sys.argv[1]),tuple(json.loads(sys.argv[2])),sys.argv[4:],sys.argv[3])')
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signum=signum):
                launcher = subprocess.Popen([sys.executable, '-B', '-c', code, str(self.focus.pid),
                                             json.dumps(self.expected), str(self.journal), *self.command('wait')],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic() + 5
                    while not self.record.exists() and launcher.poll() is None and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue(self.record.exists())
                    launcher.send_signal(signum)
                    self.assertNotEqual(launcher.wait(timeout=8), 0)
                    self.cleaned()
                finally:
                    launcher.kill() if launcher.poll() is None else None
                    launcher.wait()
                self.record.unlink()
                self.journal.unlink()

    def test_spawn_exception_resumes(self):
        # Replicata: spawning fails after the toy was stopped.
        # Expectata: the exception propagates after resumption and a paired journal.
        # Resultata before implementation: no unbounded lease exists.
        real_spawn = subprocess.Popen
        def spawn(*args, **kwargs):
            if kwargs.get('start_new_session'):
                raise OSError('qual')
            return real_spawn(*args, **kwargs)
        with patch.object(lease.subprocess, 'Popen', side_effect=spawn):
            with self.assertRaises(OSError):
                lease.run(self.focus.pid, self.expected, self.command('normal'), self.journal)
        self.resumed()

    def test_wrong_identity_and_open_pause_refused(self):
        # Replicata: wrong start identity, or an already-open pause journal.
        # Expectata: rejection precedes signals and journal mutation.
        # Resultata before implementation: no unbounded lease exists.
        with self.assertRaises(AssertionError):
            lease.run(self.focus.pid, ('wrong', self.expected[1]), self.command('normal'), self.journal)
        self.assertFalse(self.journal.exists())
        self.journal.write_text(json.dumps(dict(event='pause', time=time.time(), pid=self.focus.pid,
                                                start=self.expected[0], command=self.expected[1])) + '\n')
        before = self.journal.read_bytes()
        with self.assertRaises(AssertionError):
            lease.run(self.focus.pid, self.expected, self.command('normal'), self.journal)
        self.assertEqual(self.journal.read_bytes(), before)
        self.assertNotIn(state(self.focus.pid)[:1], ('', 'T', 'Z'))


if __name__ == '__main__':
    unittest.main()
