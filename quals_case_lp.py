"""Quals for focus.case_lp, the LP that proposes the run's tokens, with HiGHS's output flag on and its log going nowhere
(the 'a2' variant, approved 2026-10-25 with the 432:12 run, dreeves: "sounds good on 432:12").  HiGHS 1.12.0, as SciPy
bundles it, perturbs the costs of an all-zero objective only when output_flag is on (upstream PR #3226, unreleased):
scratch/ideas-20261025/verify.txt, critic-6.  Run with PYTHONPATH=scratch/lower24-design/beyond1000/pylib
/opt/homebrew/bin/python3 -B -m unittest quals_case_lp.

The stall quals read the capture scratch/lp672/recent-stall.json (scratch/lp672/stall.py), its seal and model hashes
checked."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import certbb
import fanout
import focus

CAPTURE = Path(__file__).resolve().parent / 'scratch' / 'lp672' / 'recent-stall.json'
OK = certbb.highs.HighsStatus.kOk


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def quiet(equations, choice):
    """certbb.Lp as it stands, quiet: the LP of the runs before 2026-10-25."""
    lp = certbb.Lp(equations, tuple(M for M, _ in choice))
    lp.set_counts(choice)
    return lp


def stall(make):
    """The captured 672:13 stall LP, made by make(equations, choice), solved once from its pre-cap basis: the LP, its
    status, its ray or point, its simplex iterations, and the capture's equations, choice and box."""
    capture = json.loads(CAPTURE.read_text())
    assert digest({k: v for k, v in capture.items() if k != 'capture_sha256'}) == capture['capture_sha256']
    choice = tuple((M, tuple(v)) for M, v in capture['choice'])
    equations = focus.moments(672, 13)
    lp = make(equations, choice)
    assert digest(lp.A.tolist()) == capture['model']['matrix_sha256']
    assert digest(lp.b.tolist()) == capture['model']['rhs_sha256']
    saved = capture['before']['basis']
    basis = certbb.highs.HighsBasis()
    basis.valid = saved['valid']
    basis.col_status = [certbb.highs.HighsBasisStatus(s) for s in saved['col_status']]
    basis.row_status = [certbb.highs.HighsBasisStatus(s) for s in saved['row_status']]
    status, z = lp.solve(capture['lo'], capture['hi'], basis)
    return lp, status, z, lp.H.getInfo().simplex_iteration_count, equations, choice, capture['lo'], capture['hi']


def options(lp):
    """The LP's logging options: output_flag, log_to_console, log_file."""
    return tuple(lp.H.getOptionValue(k) for k in ('output_flag', 'log_to_console', 'log_file'))


class CaseLpQuals(unittest.TestCase):
    def test_the_captured_stall_closes_in_few_iterations(self):
        # Replicata: the 672:13 LP that stalled in production (job 03969368db's box, 263 checked steps in), from its
        # pre-cap basis, on focus.case_lp's LP.
        # Expectata: Infeasible in fewer than 100 simplex iterations (8 on 2026-10-25), its certificate exact.
        # Resultata before the change: production's quiet LP ran to its 20,000-iteration cap, closing nothing.
        lp, status, ray, iterations, equations, choice, lo, hi = stall(focus.case_lp)
        self.assertEqual(status, 'Infeasible')
        self.assertLess(iterations, 100)
        certificate = lp.multipliers(ray)
        self.assertGreater(certbb.lower_bound(certbb.node_rows(equations, choice), lo, hi, certificate), 0)
        certbb.verify(equations, tuple((M, (v,)) for M, v in choice), [('L', certificate)], lo, hi)
        print(json.dumps(dict(status=status, iterations=iterations)), flush=True)

    def test_quiet_options_still_stall(self):
        # Replicata: the same LP and basis on certbb.Lp's own quiet options.
        # Expectata: the 20,000-iteration cap, as on 2026-10-25.  A canary: when this fails, the installed HiGHS
        # perturbs a zero objective's costs while quiet (PR #3226 released into SciPy's copy), and case_lp's option
        # may be redundant.
        lp, status, _, iterations, *_ = stall(quiet)
        self.assertEqual((status, iterations), ('Iteration limit reached', certbb.ITERATIONS))
        self.assertEqual(options(lp)[0], (OK, False))

    def test_case_lp_has_the_option_and_certbb_lp_does_not(self):
        # Replicata: focus.case_lp's LP and certbb.Lp's, for 20:5.
        # Expectata: output_flag on with log_to_console off and no log file for case_lp; certbb.Lp still quiet.
        self.assertEqual(options(focus.case_lp(focus.moments(20, 5), ())), ((OK, True), (OK, False), (OK, '')))
        self.assertEqual(options(quiet(focus.moments(20, 5), ()))[0], (OK, False))

    def test_the_option_writes_nothing(self):
        # Replicata: in an empty working directory, with file descriptors 1 and 2 sent to a file: the stall solve and
        # a complete depth-first proof of 20:5 on case_lp's LPs.
        # Expectata: not a byte written to either descriptor, and no file made.
        saved = os.dup(1), os.dup(2)
        here = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryFile() as sink:
            os.chdir(tmp)
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            try:
                status = stall(focus.case_lp)[1]
                equations = focus.moments(20, 5)
                lp, stack, tokens = focus.case_lp(equations, ()), [()], []
                while stack:
                    path = stack.pop()
                    kind, arg = token = focus.step(lp, equations, (), *fanout.box(20, path))
                    tokens.append(token)
                    stack += [path + ((arg, 1),), path + ((arg, 0),)] if kind == 'B' else []
                made = os.listdir(tmp)
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                os.dup2(saved[0], 1)
                os.dup2(saved[1], 2)
                os.close(saved[0])
                os.close(saved[1])
                os.chdir(here)
            sink.seek(0)
            written = sink.read()
        self.assertEqual((status, written, made), ('Infeasible', b'', []))
        certbb.verify(equations, (), tokens)

    def test_every_producer_s_lp_comes_from_case_lp(self):
        # Replicata: focus.search on 20:5, a fanout worker's LP for a case, and a fanout probe, with focus.case_lp
        # wrapped to record the LPs it makes.
        # Expectata: each makes its LP there, with the option on.
        # Resultata before the change: each made a quiet certbb.Lp of its own.
        made, real = [], focus.case_lp
        def recorder(equations, choice):
            made.append(real(equations, choice))
            return made[-1]
        prepared = focus.moments(20, 5), ((),)
        with tempfile.TemporaryDirectory() as tmp, patch.object(focus, 'case_lp', recorder), \
                patch.object(focus, 'prepare', return_value=prepared):
            self.assertEqual(focus.search(Path(tmp, 'run'), Path(tmp, 'journal'), 20, 5, 5, 60), 'budget')
            self.assertEqual(len(made), 1)
            fanout.lp_for.cache_clear()
            fanout.init(prepared, 10, 8)
            self.assertIs(fanout.lp_for(0), made[-1])
            fanout.lp_for.cache_clear()
            fanout.probe(prepared, 0, 2)
        self.assertEqual(len(made), 3)
        self.assertTrue(all(options(lp) == ((OK, True), (OK, False), (OK, '')) for lp in made))

    def test_focus_search_finds_16_4_and_excludes_20_5_under_the_option(self):
        # Replicata: focus.search, on case_lp's LP, on 16:4 (Thue-Morse's order) and 20:5 (m*(20) = 3), then
        # focus.replay of each run's chunks.
        # Expectata: an exact witness of order at least 4 at 16; a complete, replayed exclusion at 20.
        for n, m, outcome in ((16, 4, 'witness'), (20, 5, 'excluded')):
            prepared = focus.moments(n, m), ((),)
            with self.subTest(n=n), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(focus, 'prepare', return_value=prepared):
                run = Path(tmp, 'run')
                self.assertEqual(focus.search(run, Path(tmp, 'journal'), n, m, 10 ** 5, 600), outcome)
                state = focus.replay(run, *prepared, focus.fingerprint())
                self.assertEqual(state.outcome, outcome)
                self.assertTrue(state.witness is None or all(
                    sum((2 * t - 1) * p ** k for p, t in enumerate(state.witness)) == 0 for k in range(m)))
                self.assertEqual(state.completed, [0] if outcome == 'excluded' else [])


if __name__ == '__main__':
    unittest.main()
