"""Quals for Astra's standalone Wolfram Language proof of m*(384) = 10.

Replicata: run proof384.wl with wolframscript, inspect its exact result, and
damage each certificate, its coverage, and the witness in temporary copies.
Expectata: agreement with the Python proof, a valid shifted order-10 witness,
and loud rejection of every damaged copy without Wolfram evaluation messages.
Resultata before implementation: proof384.wl is absent, so the quals are red.

Run with a licensed local kernel available to wolframscript; WolframKernel may
name that kernel explicitly. Only Python's standard library is needed here.
"""

from functools import lru_cache
from itertools import product
import json
from math import comb
from pathlib import Path
import subprocess
import tempfile
import unittest

import proof384 as proof


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'proof384.wl'
ANCHOR = ('  (* Validate all supplied certificate data before constructing '
          'the moment equations. *)')
MARKER = 'QUALS384='


def mutations():
    """Malformed proof data, with both residue-class pairs exercised."""
    cases = []
    for key in ('{0,3}', '{1,2}'):
        for i in range(1, 5):
            for name, path, value in (
                ('coefficient', f'{{{i},2,1}}', f'certificates[key][[{i},2,1]]+1'),
                ('zero-modulus', f'{{{i},1}}', '0'),
                ('wrong-modulus', f'{{{i},1}}', f'certificates[key][[{i},1]]+1'),
            ):
                expression = (
                    f'With[{{key={key}}}, AssociateTo[certificates, key -> '
                    f'ReplacePart[certificates[key], {path} -> {value}]]];'
                )
                cases.append((f'{key}-{i}-{name}', expression))
        cases.extend((
            (f'{key}-missing', f'KeyDropFrom[certificates, Key[{key}]];'),
            (f'{key}-empty', f'AssociateTo[certificates, {key} -> {{}}];'),
            (f'{key}-incomplete', f'AssociateTo[certificates, {key} -> '
             f'Most[certificates[{key}]]];'),
            (f'{key}-short-coefficients', f'AssociateTo[certificates, {key} -> '
             f'ReplacePart[certificates[{key}], {{1,2}} -> '
             f'Most[certificates[{key}][[1,2]]]]];'),
            (f'{key}-inexact-coefficient', f'AssociateTo[certificates, {key} -> '
             f'ReplacePart[certificates[{key}], {{1,2,1}} -> '
             f'N[certificates[{key}][[1,2,1]]]]];'),
        ))
    cases.append(('witness', 'code = "D" <> StringDrop[code, 1];'))
    return cases


@lru_cache(maxsize=1)
def run_wolfram():
    # Assertions here verify the harness's injection boundary, not proof data.
    # TODO: report that the Wolfram Language proof is absent.
    assert SOURCE.is_file(), f'{SOURCE.name} abest'
    source = SOURCE.read_text()
    # TODO: report that the mutation insertion point is not unique.
    assert source.count(ANCHOR) == 1, 'Locus mutationis non unicus est'
    cases = mutations()
    with tempfile.TemporaryDirectory(prefix='proof384-wl-') as directory:
        temporary = Path(directory)
        damaged = []
        for index, (name, expression) in enumerate(cases):
            path = temporary / f'damaged-{index}.wl'
            path.write_text(source.replace(ANCHOR, expression + '\n' + ANCHOR))
            damaged.append((name, path))
        # A separate working directory checks that the proof is self-contained.
        clean = temporary / 'proof384.wl'
        clean.write_text(source)
        paths = '{' + ','.join(json.dumps(str(p)) for _, p in damaged) + '}'
        harness = temporary / 'qual.wl'
        harness.write_text(
            f'clean = Get[{json.dumps(str(clean))}];\n'
            'damaged = Map[Function[path,\n'
            '  Block[{$Output = {}, $MessageList = {}},\n'
            '    With[{value = CheckAbort[Get[path], $Aborted]},\n'
            '      {value === $Aborted, ToString /@ $MessageList}]]],\n'
            f'  {paths}];\n'
            f'Print["{MARKER}" <> ExportString[\n'
            '  <|"clean" -> clean, "damaged" -> damaged|>, "RawJSON",\n'
            '  "Compact" -> True]];\n'
        )
        completed = subprocess.run(
            ('wolframscript', '-file', str(harness)), cwd=temporary,
            capture_output=True, text=True, timeout=180,
        )
    assert completed.returncode == 0, (completed.returncode, completed.stdout,
                                        completed.stderr)
    assert completed.stderr == '', completed.stderr
    lines = completed.stdout.splitlines()
    payloads = [line[len(MARKER):] for line in lines if line.startswith(MARKER)]
    assert len(payloads) == 1, completed.stdout
    data = json.loads(payloads[0])
    data['stdout'] = [line for line in lines if not line.startswith(MARKER)]
    data['mutation_names'] = [name for name, _ in cases]
    return data


class Quals(unittest.TestCase):
    def test_complete_exact_cover(self):
        result = run_wolfram()['clean']
        expected = proof.verify_all()
        self.assertEqual(result['vectors'], expected['vectors'])
        self.assertEqual(result['cases'], 23716)
        self.assertEqual(result['cases'], expected['cases'])
        self.assertEqual(result['survivors'], expected['survivors'])
        self.assertIs(result['order10Control'], True)
        self.assertEqual(result['levels'], [list(level) for level in expected['levels']])
        self.assertEqual(result['levels'], [[1187, 45, 9, 0]] * 4)

    def test_count_enumeration_is_complete(self):
        sizes = tuple(len(range(r, 384, 5)) for r in range(5))
        choices = tuple(tuple(d for d in range(-s, s + 1, 2) if d % 25 == 0)
                        for s in sizes)
        expected = [
            [(d + s) // 2 for d, s in zip(ds, sizes)]
            for ds in product(*choices)
            if sum(ds) == 0
            and (ds[2] - 4 * ds[0] - 2 * ds[1]) % 125 == 0
            and (ds[3] - 3 * ds[0] - 3 * ds[1]) % 125 == 0
        ]
        self.assertEqual(run_wolfram()['clean']['countVectors'], expected)
        self.assertEqual(expected, [list(v) for v in proof.count_vectors()])

    def test_exact_order10_witness_in_original_positions(self):
        result = run_wolfram()['clean']
        witness = result['witness']
        self.assertEqual(len(witness), 384)
        self.assertEqual(set(witness), {0, 1})
        self.assertTrue(all(type(bit) is int for bit in witness))
        shifted = [sum((2 * bit - 1) * (p + 1) ** k
                       for p, bit in enumerate(witness)) for k in range(11)]
        self.assertEqual(shifted[:10], [0] * 10)
        self.assertNotEqual(shifted[10], 0)
        zero_based = [sum((2 * bit - 1) * p ** k
                          for p, bit in enumerate(witness)) for k in range(11)]
        self.assertEqual(result['moments'], zero_based)
        rows = tuple(tuple(comb(p, k) for p in range(384)) for k in range(11))
        self.assertEqual(witness, list(proof.order10_control(rows)))

    def test_every_damaged_proof_is_rejected(self):
        data = run_wolfram()
        self.assertEqual(len(data['damaged']), 35)
        self.assertEqual(len(data['damaged']), len(data['mutation_names']))
        for name, (aborted, messages) in zip(data['mutation_names'], data['damaged']):
            with self.subTest(mutation=name):
                self.assertIs(aborted, True)
                self.assertEqual(messages, [])

    def test_standalone_verdict_has_no_evaluation_messages(self):
        self.assertEqual(run_wolfram()['stdout'], [
            'Astra: "m*(384) = 10; 4 vectores, 23716 casus, 0 superstites."',
        ])


if __name__ == '__main__':
    unittest.main()
