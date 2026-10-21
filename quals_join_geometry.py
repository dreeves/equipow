#!/usr/bin/env python3
"""Replicata: run this file. Expectata: shared exact preparation, complete
residue-case scheduling, and affine-aware pruning. Resultata before the
revision: preparation has one unconditioned case and pruning ignores its tail.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sympy as sp
import join720 as J


class GeometryQuals(unittest.TestCase):
    def test_shared_preparation_preserves_every_exact_coset(self):
        # Replicata: prepare two different affine cosets of the same kernel.
        # Expectata: one integer-system construction, with both exact RHSs kept.
        # Resultata before the revision: no shared preparation operation exists.
        models = [J.join_model(p, 6, 1) for p in ([-1, 1], [1, -1])]
        with patch.object(J, 'IntegerSystem', wraps=J.IntegerSystem) as system:
            prepared = J.prepare_models(models)
        self.assertEqual(system.call_count, 1)
        self.assertEqual(len(prepared), 2)
        self.assertEqual(prepared[0]['basis'], prepared[1]['basis'])
        for model, part in zip(models, prepared):
            A = sp.Matrix(model['A'])
            self.assertEqual(A * sp.Matrix(part['target']), sp.Matrix(model['c']))
            self.assertTrue(all(x % 2 for x in part['target']))
            self.assertEqual(A * sp.Matrix(part['basis']).T, sp.zeros(len(model['A']), 2))
            self.assertEqual(sp.Rational(part['radius2']), sp.Rational(104, 35))

    def test_phase_preparation_keeps_all_residue_cases(self):
        # Replicata: prepare each real search phase without running enumeration.
        # Expectata: all seven/two compatible cases reach exact preparation.
        # Resultata before the revision: only the original moment model is used.
        with tempfile.TemporaryDirectory() as d, patch.object(J, 'WORK', Path(d)), \
                patch.object(J, 'prepare_models', return_value=[{'sentinel': 1}]) as prepare:
            for phase, count in (('calibration', 7), ('search', 2)):
                result = J.prepare(phase)
                models = prepare.call_args.args[0]
                self.assertEqual(len(models), count)
                self.assertTrue(all(len(m['A']) == 12 for m in models))
                self.assertTrue(all(m['A'] == models[0]['A'] for m in models))
                saved = json.loads((Path(d) / (phase + '.json')).read_text())
                self.assertEqual(saved, dict(code=J.CODE, cases=result))

    def test_worker_cycles_through_every_prepared_case(self):
        # Replicata: invoke the worker for more attempts than there are cases.
        # Expectata: deterministic cycling selects every case before repeating.
        # Resultata before the revision: the entire case list is passed as a model.
        with tempfile.TemporaryDirectory() as d, patch.object(J, 'WORK', Path(d)), \
                patch.object(J.resource, 'setrlimit'), \
                patch.object(J, 'enumerate_job', return_value=dict(outcome='empty', nodes=1)) as enum:
            for attempt in range(8):
                cases = [{'case': i} for i in range(3)]
                (Path(d) / 'job.json').write_text(json.dumps(dict(
                    code=J.CODE, prepared=cases, attempt=attempt)))
                with contextlib.redirect_stdout(io.StringIO()):
                    J.worker()
                enum.assert_called_with(cases[attempt % 3], attempt)

    def test_pruning_retains_an_unavoidable_affine_tail_cost(self):
        # Replicata: an orthogonal CVP has an unavoidable last-coordinate cost16.
        # Expectata: its pruning budget admits that cost instead of pruning all points.
        # Resultata at the former0.6 floor: only12 of radius20 survives at that level.
        B = J.IntegerMatrix.from_matrix([[2, 0, 0, 0], [0, 2, 0, 0],
                                        [0, 0, 2, 0], [0, 0, 0, 8]])
        M = J.GSO.Mat(B, float_type='mpfr')
        self.assertTrue(M.update_gso())
        curve = J.pruning_curve(M, M.from_canonical([0, 0, 0, 4]), 20.)
        self.assertEqual(len(curve), 4)
        self.assertEqual(curve[0], 1.)
        self.assertTrue(all(0 < a <= 1 for a in curve))
        self.assertTrue(all(a >= b for a, b in zip(curve, curve[1:])))
        self.assertGreaterEqual(curve[-1] * 20, 16)


if __name__ == '__main__':
    unittest.main()
