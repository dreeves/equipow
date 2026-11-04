"""Replicata: a completed task has the Python checker disagreement flag.
Expectata: assembly refuses to certify it. Resultata: it is currently accepted.
The other cases retain the existing complete/missing/open/cycle contracts.
"""
import copy
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('formtree_review', os.environ.get('FORMTREE_IMPL', ROOT / 'proofs/formtree.py'))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)


def verdict(start, spills=(), **extra):
    return dict(ok=True, start=start, why='', spills=list(spills), nodes=1,
                closed=1, fixes=0, splits=0, certs=1, open=0, **extra)


class AssemblyQuals(unittest.TestCase):
    def test_complete_dag_with_shared_child_is_accepted(self):
        rows = [verdict('a', ['b', 'c']), verdict('b', ['d']),
                verdict('c', ['d']), verdict('d')]
        self.assertEqual(ft.assemble(['a'], rows)['tasks'], 4)

    def test_missing_open_rejected_and_circular_tasks_fail(self):
        good = [verdict('a', ['b']), verdict('b')]
        bad = [good[:1], [good[0], {**good[1], 'open': 1}],
               [good[0], {**good[1], 'ok': False, 'why': 'x'}],
               [good[0], verdict('b', ['a'])]]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                ft.assemble(['a'], rows)

    def test_matching_or_unsampled_python_verdicts_remain_valid(self):
        for metadata in ({}, {'py': None}, {'py': True}):
            self.assertEqual(ft.assemble(['a'], [verdict('a', **metadata)])['tasks'], 1)

    def test_python_disagreement_blocks_assembly(self):
        with self.assertRaises(ValueError):
            ft.assemble(['a'], [verdict('a', py=False)])


if __name__ == '__main__': unittest.main()
