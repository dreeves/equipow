"""Replicata: second checker CLI, a two-token proof, serial versus two processes.
Expectata: both accept no 40:6 with identical counts: two splits, one vector.
Resultata before: macOS spawn workers receive DATA=None and parallel replay crashes.
"""
import gzip
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
CHECKER = Path(os.environ.get('PIN_CHECKER', str(HERE.parent / 'proofs/pintree_second.py')))
DATA = {'n': 40, 'm': 6, 'nodes': list(range(6)), 'table': [],
        'tokens': [['S', 5, None], ['S', 3, None]], 'sym_depth': 1}
COUNTS = "{'closed': 0, 'splits': 2, 'vectors': 1, 'skipped': 0, 'bounds': 0}"

class CliSpawnQuals(unittest.TestCase):
    def test_serial_and_parallel_counts(self):
        self.assertEqual(multiprocessing.get_start_method(), 'spawn')
        with tempfile.TemporaryDirectory(dir=HERE) as work:
            proof = Path(work) / 'proof.json.gz'
            with gzip.open(proof, 'wt') as f:
                json.dump(DATA, f)
            for procs in (1, 2):
                with self.subTest(procs=procs):
                    p = subprocess.run([sys.executable, '-B', '-S', str(CHECKER), str(proof), str(procs)],
                                       capture_output=True, text=True, timeout=15,
                                       env={**os.environ, 'PYTHONPATH': str(HERE.parent / 'proofs')})
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('VERIFIED by the second check: no sequence of length 40 has order 6.', p.stdout)
                    self.assertIn(COUNTS, p.stdout)

if __name__ == '__main__':
    unittest.main()
