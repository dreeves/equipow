"""Replicata: a mocked checker disagrees or returns a mismatched task verdict.
Expectata: fail before deleting the sampled stream or moving child tasks.
Resultata: the current driver admits the verdict and discards the evidence.
No native prover/checker or real search process is executed by these quals.
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FTREE_IMPL', ROOT / 'searches/formtree/ftree.py'))
NAME = '0' * 32
CHILD = '1' * 32


class DriverQuals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / 'pending').mkdir()
        (self.d / 'spill').mkdir()
        (self.d / 'pending' / NAME).write_text('parent')
        self.v = dict(ok=True, start=NAME, spills=[CHILD])
        self.r = dict(spilled=1)
        self.fd = None
        self.prefix = self.d / 'spill' / str(os.getpid())
        self.stream = Path(str(self.prefix) + '.stream')

        def certfd(fd):
            if self.fd is not None: os.close(self.fd)
            self.fd = fd

        def run_file(*args):
            self.prefix = Path(args[3])
            self.stream = Path(str(self.prefix) + '.stream')
            os.write(self.fd, b'fixture stream\n')
            Path(str(self.prefix) + '_0').write_text('child')
            return self.r

        fake_pe = SimpleNamespace(lib=SimpleNamespace(pe_certfd=certfd), run_file=run_file)
        self.argv = ['ftree.py', '288:10', 'top', '1', '1', '3', '3', str(self.d)]
        with patch.dict(sys.modules, pex=fake_pe), patch.object(sys, 'argv', self.argv):
            spec = importlib.util.spec_from_file_location('ftree_driver_qual', SOURCE)
            self.ft = importlib.util.module_from_spec(spec)
            self.ft.__file__ = str(ROOT / 'searches/formtree/ftree.py')
            exec(compile(SOURCE.read_text(), str(SOURCE), 'exec'), self.ft.__dict__)
        self.ft.PY_SAMPLE = 1
        self.ft.K = SimpleNamespace(stdin=tempfile.TemporaryFile(), stdout=None)
        self.addCleanup(self.ft.K.stdin.close)
        self.addCleanup(lambda: self.fd is None or os.close(self.fd))

    def run_job(self, *, code=0, agrees=True, name=NAME):
        self.ft.K.stdout = io.BytesIO((json.dumps(self.v) + '\n').encode())
        python_v = self.v if agrees else {**self.v, 'start': '2' * 32}
        p = SimpleNamespace(returncode=code, stdout=json.dumps(python_v) + '\n')
        with patch.object(self.ft.subprocess, 'run', return_value=p):
            return self.ft.job((name, 1, str(self.d / 'open.log')))

    def preserved_on_failure(self, **kw):
        with self.assertRaises(AssertionError): self.run_job(**kw)
        self.assertTrue(self.stream.exists())
        self.assertTrue(Path(str(self.prefix) + '_0').exists())
        self.assertFalse((self.d / 'pending' / CHILD).exists())
        self.assertEqual((self.d / 'pending' / NAME).read_text(), 'parent')

    def test_python_disagreement_preserves_evidence(self):
        self.preserved_on_failure(agrees=False)

    def test_matching_stdout_with_failed_python_exit_preserves_evidence(self):
        self.preserved_on_failure(code=1)

    def test_wrong_task_name_preserves_evidence(self):
        self.v['start'] = '2' * 32
        self.preserved_on_failure()

    def test_wrong_spill_count_preserves_evidence(self):
        self.r['spilled'] = 2
        self.preserved_on_failure()

    def test_rejected_verdict_preserves_evidence(self):
        self.v['ok'] = False
        self.preserved_on_failure()

    def test_agreement_moves_children_and_removes_sample(self):
        name, r, v, py, text = self.run_job()
        self.assertEqual((name, py), (NAME, True))
        self.assertEqual(v, self.v)
        self.assertFalse(self.stream.exists())
        self.assertEqual((self.d / 'pending' / CHILD).read_text(), 'child')

    def test_restart_refuses_recorded_disagreement(self):
        with self.assertRaises(AssertionError):
            self.ft.remaining([dict(name=NAME)], [{**self.v, 'py': False}])

    def test_restart_accepts_unsampled_and_matching_records(self):
        for py in (None, True):
            v = {**self.v, 'py': py}
            todo, used = self.ft.remaining([dict(name=NAME)], [v])
            self.assertEqual(todo, {CHILD: 0})
            self.assertEqual(used, [v])

    def test_next_queued_job_preserves_failed_sample(self):
        with self.assertRaises(AssertionError): self.run_job(agrees=False)
        failed_stream = self.stream
        failed_child = Path(str(self.prefix) + '_0')
        other = '0' * 31 + '1'
        (self.d / 'pending' / other).write_text('other parent')
        self.v['start'] = other
        self.run_job(name=other)
        self.assertEqual(failed_stream.read_text(), 'fixture stream\n')
        self.assertEqual(failed_child.read_text(), 'child')


if __name__ == '__main__': unittest.main()
