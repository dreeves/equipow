"""Actual eight-worker controls; run only after the old compute pool stops.

Replicata: continue tiny stopped focus runs with WORKERS explicitly set to 8.
Expectata: an exact 16:4 witness and a completely assembled 20:5 exclusion
(before tree-only storage, 2026-10-25: completely replayed),
with eight workers recorded in both the fanout header and session.
Resultata to qualify: existing actual controls exercise a two-worker pool.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import certbb
import fanout
import focus
from quals_fanout import events, real, stopped


def finish_eight(tmp, run, journal, prepared, n, order):
    work, own = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
    with patch.object(focus, 'prepare', return_value=prepared), \
            patch.multiple(fanout, WORKERS=8, BUDGET=4):
        outcome = fanout.run(run, work, own, n, order)
    return outcome, work, own


class EightWorkerQuals(unittest.TestCase):
    def check_session(self, own, n, order, outcome):
        log = events(own)
        self.assertEqual((log[0]['event'], log[0]['n'], log[0]['order'], log[0]['workers']),
                         ('header', n, order, 8))
        sessions = [e for e in log if e['event'] == 'session']
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['workers'], 8)
        self.assertEqual((log[-1]['event'], log[-1]['outcome']), ('finish', outcome))
        self.assertTrue(any(e['event'] == 'job_end' for e in log))
        return log

    def test_eight_workers_recover_an_exact_16_order4_witness(self):
        source = hashlib.sha256(Path(fanout.__file__).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(16, 4)
            run, journal = stopped(tmp, prepared, 16, 4, 3)
            outcome, _, own = finish_eight(tmp, run, journal, prepared, 16, 4)
            self.assertEqual(outcome, 'witness')
            log = self.check_session(own, 16, 4, outcome)
            witness = log[-1]['witness']
            self.assertEqual(len(witness), 16)
            self.assertTrue(all(type(x) is int and x in (0, 1) for x in witness))
            self.assertEqual([sum((2 * x - 1) * p ** k for p, x in enumerate(witness))
                              for k in range(4)], [0] * 4)
            self.assertIsNone(certbb.point_certificate(certbb.node_rows(prepared[0], ()), witness))
            prefix = focus.replay(run, *prepared, focus.fingerprint())
            self.assertEqual(prefix.lp, 3)
            self.assertTrue(prefix.frontier)
        self.assertEqual(hashlib.sha256(Path(fanout.__file__).read_bytes()).hexdigest(), source)
        print(json.dumps(dict(n=16, order=4, workers=8, outcome=outcome,
                              witness=witness, fanout_sha256=source)), flush=True)

    def test_eight_workers_complete_20_order5_with_exact_assembly(self):
        # Before tree-only storage (2026-10-25) this qual was
        # test_eight_workers_complete_20_order5_with_exact_full_replay: focus.replay of the spliced chunks found case 0
        # completed, and focus.py's journal ended excluded.  Now the chunks stay the stopped run's 5 LP solves, and
        # assembly walks every job fanout's journal ended.
        source = hashlib.sha256(Path(fanout.__file__).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish_eight(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            log = self.check_session(own, 20, 5, outcome)
            code = focus.fingerprint()
            prefix = focus.replay(run, *prepared, code)
            roots = fanout.roots(run, work, code)
            self.assertEqual((prefix.lp, prefix.outcome, [fanout.key(*b) for b in prefix.frontier]),
                             (5, 'budget', roots))
            walked = fanout.assemble(run, work, own, prepared, code, roots, fanout.finished(work))
            ends = [e for e in log if e['event'] == 'job_end']
            self.assertEqual(sorted(map(fanout.jid, walked)), sorted(e['job'] for e in ends))
            lps = sum(e['lps'] for e in ends)
            self.assertGreater(lps, 0)
            self.assertEqual((events(journal)[-1]['event'], events(journal)[-1]['outcome']), ('finish', 'budget'))
        self.assertEqual(hashlib.sha256(Path(fanout.__file__).read_bytes()).hexdigest(), source)
        print(json.dumps(dict(n=20, order=5, workers=8, outcome=outcome,
                              lp=prefix.lp + lps, jobs=len(walked), fanout_sha256=source)), flush=True)


if __name__ == '__main__':
    unittest.main()
