"""Synthetic quals for isolated solver imports and temporary progress bindings."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_modules


class ModuleQuals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old, self.new = self.root / 'old', self.root / 'new'
        self.old.mkdir()
        self.new.mkdir()
        for directory, value in ((self.old, 'old'), (self.new, 'new')):
            checker = ''.join(f'def {name}(*args):\n    return {name!r}\n\n' for name in run_modules.CHECKER)
            (directory / 'certbb.py').write_text(f'VALUE = {value!r}\nARITY = {{"L": 1}}\n' + checker)
            geometry = ''.join(f'def {name}(*args):\n    return {name!r}\n\n' for name in run_modules.GEOMETRY)
            (directory / 'overnight_v5.py').write_text('import certbb\nCODE = certbb.VALUE\n' + geometry +
                'def configure(n, order):\n    global N, ORDER\n    N, ORDER = n, order\n' +
                'def header():\n    return dict(code=CODE, N=N, order=ORDER)\n')
            boxes = ''.join(f'def {name}(*args):\n    return {name!r}\n\n' for name in run_modules.BOX_GEOMETRY)
            (directory / 'boxsplit.py').write_text('import certbb\nimport overnight_v5 as v5\n' + boxes)
        self.root_certbb = self.module('qual_root_certbb', self.old / 'certbb.py')
        with patch.dict(sys.modules, {'certbb': self.root_certbb}):
            self.root_v5 = self.module('qual_root_v5', self.old / 'overnight_v5.py')
        with patch.dict(sys.modules, {'certbb': self.root_certbb, 'overnight_v5': self.root_v5}):
            self.root_bx = self.module('qual_root_bx', self.old / 'boxsplit.py')
        self.patch = patch.dict(sys.modules, {'certbb': self.root_certbb, 'overnight_v5': self.root_v5,
                                              'boxsplit': self.root_bx})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def module(self, name, path):
        name += '_' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    def load(self):
        return run_modules.load(self.new, self.root_v5, self.root_bx)

    def test_local_solver_and_box_module_bind_to_the_local_run(self):
        # Replicata: a different local solver beside source-identical replay geometry.
        # Expectata: all local imports bind together, while canonical root modules remain untouched.
        loaded = self.load()
        self.assertEqual(loaded.v5.CODE, 'new')
        self.assertIs(loaded.v5.certbb, loaded.certbb)
        self.assertIs(loaded.bx.certbb, loaded.certbb)
        self.assertIs(loaded.bx.v5, loaded.v5)
        self.assertIs(sys.modules['certbb'], self.root_certbb)
        self.assertIs(sys.modules['overnight_v5'], self.root_v5)
        self.assertIs(sys.modules['boxsplit'], self.root_bx)
        self.assertIs(self.load().v5, loaded.v5)

    def test_import_exception_restores_canonical_modules_and_path(self):
        # Replicata: the local run imports its solver then raises during execution.
        # Expectata: root imports and sys.path are exactly restored, including on the exception path.
        with (self.new / 'overnight_v5.py').open('a') as fh:
            fh.write('raise RuntimeError("qual")\n')
        before = list(sys.path)
        with self.assertRaises(RuntimeError):
            self.load()
        self.assertIs(sys.modules['certbb'], self.root_certbb)
        self.assertIs(sys.modules['overnight_v5'], self.root_v5)
        self.assertEqual(sys.path, before)

    def test_changed_geometry_is_rejected(self):
        # Replicata: a local split function differs from the root replay's function.
        # Expectata: differing geometry cannot be accepted merely because exact proof checking still exists.
        path = self.new / 'overnight_v5.py'
        path.write_text(path.read_text().replace("return 'split'", "return 'different'"))
        with self.assertRaises(AssertionError):
            self.load()
        self.assertIs(sys.modules['certbb'], self.root_certbb)

    def test_changed_source_after_loading_is_rejected(self):
        # Replicata: load a run, then alter its local solver file.
        # Expectata: loading fails rather than silently retaining a stale imported solver.
        self.load()
        with (self.new / 'certbb.py').open('a') as fh:
            fh.write('CHANGED = True\n')
        with self.assertRaises(AssertionError):
            self.load()

    def test_old_run_without_local_solver_uses_the_explicit_root_dependency(self):
        # Replicata: an existing run copy contains v5 and boxsplit but no local certbb.
        # Expectata: both bind to the root solver, as their original ordinary imports did.
        (self.new / 'certbb.py').unlink()
        loaded = self.load()
        self.assertIs(loaded.certbb, self.root_certbb)
        self.assertIs(loaded.v5.certbb, self.root_certbb)
        self.assertIs(loaded.bx.certbb, self.root_certbb)

    def test_changed_exact_checker_is_rejected(self):
        # Replicata: a local solver changes its exact checker while keeping the geometry unchanged.
        # Expectata: a solver optimization cannot silently change the verifier contract.
        path = self.new / 'certbb.py'
        path.write_text(path.read_text().replace("return 'lower_bound'", "return 'changed'"))
        with self.assertRaises(AssertionError):
            self.load()

    def test_changed_token_arities_are_rejected(self):
        # Replicata: a local solver changes the proof token's argument count.
        # Expectata: accepting another token language is refused.
        path = self.new / 'certbb.py'
        path.write_text(path.read_text().replace('"L": 1', '"L": 2'))
        with self.assertRaises(AssertionError):
            self.load()

    def test_root_directory_retains_original_module_identities(self):
        # Replicata: load the root modules' own directory.
        # Expectata: existing standalone root callers retain their configured module instances.
        loaded = run_modules.load(self.old, self.root_v5, self.root_bx)
        self.assertIs(loaded.v5, self.root_v5)
        self.assertIs(loaded.bx, self.root_bx)
        self.assertIs(loaded.certbb, self.root_certbb)

    def test_progress_context_restores_both_bindings_after_success_and_failure(self):
        # Replicata: temporarily survey the local run, normally and through an exception.
        # Expectata: root bindings return in both cases.
        loaded = self.load()
        progress = SimpleNamespace(v5=self.root_v5, bx=self.root_bx)
        with run_modules.context(progress, loaded):
            self.assertIs(progress.v5, loaded.v5)
            self.assertIs(progress.bx, loaded.bx)
        self.assertIs(progress.v5, self.root_v5)
        self.assertIs(progress.bx, self.root_bx)
        with self.assertRaises(RuntimeError):
            with run_modules.context(progress, loaded):
                raise RuntimeError('qual')
        self.assertIs(progress.v5, self.root_v5)
        self.assertIs(progress.bx, self.root_bx)

    def test_header_is_checked_against_the_actual_local_module(self):
        # Replicata: a configured local run receives its own header, then the old code's header.
        # Expectata: only the actual local header is accepted.
        loaded = self.load()
        loaded.v5.configure(288, 10)
        header = loaded.v5.header()
        run_modules.validate_header(loaded.v5, header)
        with self.assertRaises(AssertionError):
            run_modules.validate_header(loaded.v5, dict(header, code='old'))

    def test_legacy_archive_is_verified_and_a_changed_archive_is_rejected(self):
        # Replicata: an explicit legacy header names an exact saved archive, then that archive changes.
        # Expectata: correct provenance passes; later bytes cannot use a cached validation.
        archive = self.root / 'archive.jsonl'
        data = b'{"code":"old"}\n{"key":"one"}\n'
        archive.write_bytes(data)
        legacy = dict(code='old', sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), records=1,
                      archive=str(archive))
        loaded = self.load()
        loaded.v5.configure(288, 10)
        header = dict(loaded.v5.header(), legacy=legacy)
        loaded.v5.header = lambda: header
        run_modules.validate_header(loaded.v5, header)
        archive.write_bytes(data + b'{"key":"two"}\n')
        with self.assertRaises(AssertionError):
            run_modules.validate_header(loaded.v5, header)


if __name__ == '__main__':
    unittest.main()
