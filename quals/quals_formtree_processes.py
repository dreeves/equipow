"""Replicata: mocked ps rows, including Homebrew Python and shell mentions.
Expectata: only live Python script invocations match; a live run prevents saving.
Resultata before: the Mac run is missed, while scripts mentioned as arguments match.
No actual subprocess or signal is used by these quals.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = Path(os.environ.get('FORM_OPS', str(ROOT/'searches/formtree')))
MAC = '/opt/homebrew/Cellar/python@3.13/3.13.6/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python'

class ProcessQuals(unittest.TestCase):
    def setUp(self):
        sys.modules.pop('processes', None)
        self.paths = mock.patch.object(sys, 'path', [str(SOURCE)] + sys.path)
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.addCleanup(lambda: sys.modules.pop('processes', None))

    def ps(self, rows):
        def result(command, **kwargs):
            self.assertEqual(command[0], 'ps')
            self.assertEqual(kwargs, {'capture_output':True, 'text':True, 'check':True})
            columns = command[-1]
            self.assertIn(columns, ('pid=,args=', 'args=', 'pid=,ppid=,stat=,command='))
            formats = {
                'pid=,args=': lambda pid, state, args: f'{pid} {args}',
                'args=': lambda pid, state, args: args,
                'pid=,ppid=,stat=,command=': lambda pid, state, args: f'{pid} 1 {state} {args}',
            }
            return types.SimpleNamespace(stdout='\n'.join(formats[columns](*row) for row in rows)+'\n')
        return result

    def stopped(self, rows, scripts=('ftree.py',)):
        with mock.patch('subprocess.run', side_effect=self.ps(rows)), mock.patch('os.kill') as kill, \
             mock.patch('os.getpid', return_value=99999), mock.patch.object(sys, 'argv', ['stopall.py', *scripts]), \
             contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(SOURCE/'stopall.py'), run_name='__main__')
            return [call.args[0] for call in kill.call_args_list]

    def handoff(self):
        spec = importlib.util.spec_from_file_location('handoff_candidate', SOURCE/'handoff.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def running(self, rows):
        with mock.patch('subprocess.run', side_effect=self.ps(rows)):
            return self.handoff().running()

    def test_interpreter_and_script_forms(self):
        commands = [
            f'{MAC} -B ftree.py 288:10 top.json 10',
            '/usr/bin/python3 -B -u /repo/searches/formtree/ftree.py 288:10',
            'python3.11 -Bu ./ftree.py 288:10',
            'Python ftree.py 288:10',
            'python -W ignore -X dev ftree.py 288:10',
            'python -BWignore -Xdev -- ftree.py 288:10',
            'python --check-hash-based-pycs always ftree.py 288:10',
        ]
        for command in commands:
            for state in ('SN', 'RN', 'TN'):
                with self.subTest(command=command, state=state):
                    rows=[(42,state,command)]
                    self.assertEqual(self.stopped(rows), [42])
                    self.assertTrue(self.running(rows))

    def test_mentions_are_not_running_scripts(self):
        commands = [
            '/bin/bash -c python3 -B ftree.py 288:10',
            '/bin/zsh -c nohup python3 -B ftree.py 288:10',
            'python3 other.py ftree.py',
            'python3 -c ftree.py',
            'python3 -m ftree.py',
            'python3 -c pass ftree.py',
            'python3 -X ftree.py other.py',
            'python3 -W ftree.py other.py',
            'python3 - ftree.py',
            'python3 -V ftree.py',
            'python3 --help ftree.py',
            'python3 notftree.py',
            'python3 ftree.py.bak',
            '/usr/bin/mypython ftree.py',
            '/usr/bin/python-helper ftree.py',
        ]
        for command in commands:
            with self.subTest(command=command):
                rows=[(43,'SN',command)]
                self.assertEqual(self.stopped(rows), [])
                self.assertFalse(self.running(rows))

    def test_zombies_do_not_match(self):
        rows=[(44,'Z','python3 -B ftree.py 288:10')]
        self.assertEqual(self.stopped(rows), [])
        self.assertFalse(self.running(rows))

    def test_selected_scripts_are_unique_and_self_is_not_signaled(self):
        rows=[(45,'SN','python3 ftree.py'),(46,'SN','python3 audit.py'),
              (47,'SN','python3 other.py'),(99999,'SN','python3 stopall.py ftree.py')]
        self.assertEqual(sorted(self.stopped(rows, ('ftree.py','audit.py','ftree.py','stopall.py'))),[45,46])

    def test_snapshot_refuses_a_live_mac_driver_before_reading_state(self):
        handoff=self.handoff()
        with mock.patch('subprocess.run', side_effect=self.ps([(42,'RN',f'{MAC} -B ftree.py 288:10')])), \
             mock.patch.object(handoff.importlib.util,'spec_from_file_location',side_effect=RuntimeError('state access')) as read:
            with self.assertRaisesRegex(AssertionError, 'stop the run first'):
                handoff.save('not-read','not-written.tar.gz','not-written.json')
            read.assert_not_called()

if __name__ == '__main__':
    unittest.main()
