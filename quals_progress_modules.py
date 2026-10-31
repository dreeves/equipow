"""Quals for progress snapshots using each run's isolated solver and explicit journal provenance."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import progress
import quals_progress


class ProgressModuleQuals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        root = Path(progress.__file__).parent
        for name in ('certbb.py', 'overnight_v5.py', 'boxsplit.py'):
            shutil.copyfile(root / name, self.directory / name)
        with (self.directory / 'certbb.py').open('a') as fh:
            fh.write('\nLOCAL_SOLVER_QUAL = True\n')
        self.old = progress.v5, progress.bx
        self.scopes = ExitStack()
        self.addCleanup(self.scopes.close)
        self.scopes.enter_context(patch.dict(progress.DIRS, {(40, 6): str(self.directory),
                                                           (304, 9): str(self.directory)}))

    def test_local_context_accepts_solver_change_and_restores_root_bindings(self):
        # Replicata: a local solver differs, with byte-identical geometry and exact checker.
        # Expectata: the local CODE is real, files use it inside the context, and root modules return afterward.
        with progress.run_context(304, 9):
            local = progress.v5
            self.assertNotEqual(local.CODE, self.old[0].CODE)
            self.assertIs(progress.bx.v5, local)
            self.assertIs(local.certbb, progress.bx.certbb)
            self.assertEqual(progress.files(304, 9),
                tuple(str(self.directory / ('overnight_v5_304_9' + suffix))
                      for suffix in ('_journal.jsonl', '.log')))
            self.assertIs(sys.modules['overnight_v5'], self.old[0])
            self.assertIs(sys.modules['certbb'], self.old[0].certbb)
        self.assertEqual((progress.v5, progress.bx), self.old)
        with self.assertRaises(RuntimeError):
            with progress.run_context(304, 9):
                raise RuntimeError('qual')
        self.assertEqual((progress.v5, progress.bx), self.old)

    def test_standalone_files_preserves_root_callers(self):
        # Replicata: files is called without a context for a local solver revision.
        # Expectata: it locates the local data and configures root defaults without rebinding either root module.
        paths = progress.files(304, 9)
        self.assertEqual((progress.v5, progress.bx), self.old)
        self.assertEqual((progress.v5.N, progress.v5.ORDER), (304, 9))
        self.assertEqual(Path(paths[0]).parent, self.directory)
        self.assertNotEqual(progress.run_module(str(self.directory)).CODE, progress.v5.CODE)

    def test_surveys_use_local_modules_for_both_cache_keys_and_full_calls(self):
        # Replicata: both overnight and box passes of an isolated solver appear in one snapshot.
        # Expectata: all file resolution and survey calls see local modules; the overnight run's splits and ETAs are
        # cached under its geometry, the repository's own (2026-10-30: under its CODE before, which its solver
        # changes), the box pass's ETAs under its boxsplit CODE.
        seen, cache = [], {}
        (self.directory / 'overnight_v5_304_9_boxsplit.log').touch()
        def observe(kind):
            def call(n, order, *args):
                seen.append((kind, progress.v5, progress.bx, args))
                return {'kind': kind}
            return call
        with patch.object(progress, 'RUNS', ((304, 9),)), patch.object(progress, 'EXTENDED', ((304, 9),)), \
                patch.object(progress, 'survey', observe('main')), patch.object(progress, 'survey_box', observe('box')):
            got = progress.survey_runs([], 0, cache)
        self.assertEqual(got, [{'kind': 'main'}, {'kind': 'box'}])
        local = progress.run_module(str(self.directory))
        self.assertTrue(all(v5 is local and bx.v5 is local for _, v5, bx, _ in seen))
        local.configure(304, 9)
        geometry = progress.run_modules.geometry(local)
        self.assertNotEqual(local.CODE, self.old[0].CODE)
        self.old[0].configure(304, 9)
        self.assertEqual(geometry, progress.run_modules.geometry(self.old[0]))
        self.assertEqual(set(cache), {f'304_9_geometry_{geometry}', f'304_9_geometry_{geometry}_etas',
                                    f'304_9_boxsplit_{seen[1][2].CODE}_etas'})
        self.assertEqual((progress.v5, progress.bx), self.old)

    def test_explicit_legacy_header_replays_identical_record_body(self):
        # Replicata: preserve a tiny old run's full archive and body, changing only its header to local CODE plus provenance.
        # Expectata: normal read_run/read_journal replay gives exactly the old records; a false code or archive fails.
        old_journal, log = quals_progress.tiny('closed')
        progress.v5.configure(40, 6)
        expected = progress.read_run(old_journal, log)
        data = Path(old_journal).read_bytes()
        archive = self.directory / 'legacy.jsonl'
        archive.write_bytes(data)
        legacy = dict(code=json.loads(data.split(b'\n', 1)[0])['code'], sha256=hashlib.sha256(data).hexdigest(),
                      bytes=len(data), records=len(data.splitlines()) - 1, archive=str(archive))
        with (self.directory / 'overnight_v5.py').open('a') as fh:
            fh.write('\n_original_header = header\n' +
                     'def header():\n    return dict(_original_header(), legacy=' + repr(legacy) + ')\n')
        with progress.run_context(40, 6):
            progress.files(40, 6)
            header = progress.v5.header()
            journal = self.directory / 'journal.jsonl'
            body = data.split(b'\n', 1)[1]
            journal.write_bytes(json.dumps(header).encode() + b'\n' + body)
            got = progress.read_run(str(journal), log)
            self.assertEqual(got, expected)
            self.assertEqual(progress.read_journal(str(journal)), {r['key']: r for r in got['records']})
            journal.write_bytes(json.dumps(dict(header, code='wrong')).encode() + b'\n' + body)
            with self.assertRaises(AssertionError):
                progress.read_run(str(journal), log)
            journal.write_bytes(json.dumps(header).encode() + b'\n' + body)
            archive.write_bytes(data + b'{}\n')
            with self.assertRaises(AssertionError):
                progress.read_journal(str(journal))


class GeometryCacheQuals(unittest.TestCase):
    """The split cache under a run's geometry (2026-10-30), on quals_progress.tiny('open') (64@7, which splits), surveyed
    as the watcher surveys a run (survey_runs) from run directories of copies of the repository's sources."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.journal, self.log = quals_progress.tiny('open')

    def run_dir(self, name, edit=lambda text: text, solver=''):
        """A run directory: the root's overnight_v5.py (through edit), certbb.py (with solver appended) and
        boxsplit.py, and tiny('open')'s journal and log under the run's names, the journal's header the run's own (as a
        migration writes it)."""
        d = Path(self.tmp.name) / name
        d.mkdir()
        root = Path(progress.__file__).parent
        for f in ('overnight_v5.py', 'certbb.py', 'boxsplit.py'): shutil.copyfile(root / f, d / f)
        (d / 'overnight_v5.py').write_text(edit((d / 'overnight_v5.py').read_text()))
        with (d / 'certbb.py').open('a') as fh: fh.write(solver)
        local = progress.run_module(str(d))
        local.configure(64, 7)
        body = Path(self.journal).read_text().split('\n', 1)[1]
        (d / 'overnight_v5_64_7_journal.jsonl').write_text(json.dumps(local.header()) + '\n' + body)
        shutil.copyfile(self.log, d / 'overnight_v5_64_7.log')
        return d

    def survey(self, d, cache):
        """survey_runs of 64@7 from the run directory d with this cache, no process running."""
        with patch.dict(progress.DIRS, {(64, 7): str(d)}), patch.object(progress, 'RUNS', ((64, 7),)), \
                patch.object(progress, 'EXTENDED', ()):
            got, = progress.survey_runs([], 0, cache)
        return got

    def test_a_solver_change_reuses_every_split_and_a_geometry_change_does_not(self):
        # Replicata: tiny('open') surveyed with one cache from three run directories in turn: the root's sources;
        # certbb.py with a line added (another solver, so another CODE, the journal's header migrated to it);
        # overnight_v5.py with Relaxation's docstring changed (another geometry, the same CODE).  Before the second
        # survey, the splits' entry is replaced by a dict that records every key set in it (children sets one only for a
        # split it computes).
        # Expectata (2026-10-30): the first survey caches splits under one geometry key; the solver's change keeps that
        # key and computes no split (none set, the entry unchanged); the Relaxation change caches them anew under
        # another key, equal to the first.
        class Recording(dict):
            def __setitem__(self, key, value):
                sets.append(key)
                super().__setitem__(key, value)
        sets, cache = [], {}
        first = self.survey(self.run_dir('root'), cache)
        (splits, etas), = [(k, k + '_etas') for k in cache if not k.endswith('_etas')]
        self.assertTrue(splits.startswith('64_7_geometry_') and set(cache) == {splits, etas} and cache[splits])
        kept = dict(cache[splits])
        cache[splits] = Recording(kept)
        solver = self.run_dir('solver', solver='\nGEOMETRY_QUAL_SOLVER = True\n')
        self.assertNotEqual(progress.run_module(str(solver)).CODE, progress.run_module(str(Path(self.tmp.name) / 'root')).CODE)
        second = self.survey(solver, cache)
        self.assertEqual((sets, set(cache), cache[splits]), ([], {splits, etas}, kept))
        self.assertEqual((second['levels'], second['sea']), (first['levels'], first['sea']))
        relaxation = self.run_dir('relaxation', lambda text: text.replace(
            'The LP relaxation, 0 <= x_p <= 1, of', 'The LP relaxation (geometry qual), 0 <= x_p <= 1, of', 1))
        self.survey(relaxation, cache)
        (other,) = [k for k in cache if not k.endswith('_etas') and k != splits]
        self.assertEqual(dict(cache[other]), kept)


class NativeTrackQuals(unittest.TestCase):
    def record(self, target='288:10', end=0, command=None, cwd=None):
        steps = (('overnight_v5.py', '288', '10'), ('boxsplit.py', '288', '10'),
                 ('handoff288.py',), ('overnight_v5.py', '288', '10'))
        script = ' && '.join(shlex.join(['/opt/homebrew/bin/python3', '-B', *step]) for step in steps)
        lines = quals_progress.track_record('native', 987, end, None, 1000)
        lines[0].update(target=target, program='sh', command=command or shlex.join(['/bin/sh', '-c', script]),
                        cwd=cwd or str(Path(progress.HERE) / progress.DIRS[288, 10]))
        return lines

    def test_native_chain_is_recognized_after_exit_and_while_running(self):
        # Replicata: the exact tracked native chain, with and without its durable end record.
        # Expectata: identity comes from its recorded command and cwd, independent of live process ancestry.
        for end in (None, 0, -15):
            self.assertTrue(progress.native288(self.record(end=end)[0]))

    def test_other_commands_targets_and_directories_remain_visible(self):
        # Replicata: another same-target heuristic, another target, another cwd, or another shell program.
        # Expectata: none is mistaken for the configured native chain, including unrelated inner shell quoting.
        for record in (self.record(command='python3 -B heuristic.py 288 10'), self.record(target='432:12'),
                       self.record(cwd='/tmp'), self.record(command=shlex.join(['/bin/sh', '-c', "printf '"])),
                       self.record(command=shlex.join(['/bin/sh', '-c', 'python3 -B other.py 288 10']))):
            self.assertFalse(progress.native288(record[0]))
        with patch.object(progress, 'RUNS', ()):
            self.assertFalse(progress.native288(self.record()[0]))

    def test_snapshot_filters_individual_native_records_before_grouping(self):
        # Replicata: native and heuristic 288 records plus a 432 record appear in the same snapshot.
        # Expectata: only the native duplicate is removed; both unrelated records retain their normal surveys.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'runs').mkdir()
            captured = []
            with patch.object(progress, 'HERE', d):
                native = self.record()
                heuristic = self.record(command='python3 -B heuristic.py 288 10')
                other = self.record(target='432:12')
                for name, lines in (('native', native), ('heuristic', heuristic), ('other', other)):
                    lines[0]['name'] = name
                    (root / 'runs' / (name + '.jsonl')).write_text(''.join(json.dumps(line) + '\n' for line in lines))
                def observe(target, records, procs, now):
                    captured.append((target, [lines[0]['name'] for lines in records]))
                    return {'program': 'qual'}
                with patch.object(progress, 'CACHE', str(root / 'cache.json')), \
                        patch.object(progress, 'processes', lambda: []), patch.object(progress.os, 'nice', lambda n: 0), \
                        patch.object(progress, 'survey_runs', lambda *args: []), \
                        patch.object(progress, 'survey_track', observe), patch.object(progress, 'js_text', lambda *args: ''), \
                        patch.object(progress, 'write_atomic', lambda *args: None):
                    progress.main([])
            self.assertEqual(captured, [('288:10', ['heuristic']), ('432:12', ['other'])])


if __name__ == '__main__':
    unittest.main()
