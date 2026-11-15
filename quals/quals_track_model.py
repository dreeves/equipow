#!/usr/bin/env python3
"""Quals for explicit, recorded model activation without restarting a search.

Run: python3 -B quals/quals_track_model.py
"""
import sys
sys.dont_write_bytecode = True
import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'searchwatch'))
START = dict(event='start', name='q', search='formtree', target='16:2', estimator='est.py', command='job',
             cwd='/', found=None, adopted=False, pid=123, tracker=124, time=100.0)
EST = dict(event='estimate', time=110.0, basis='formtree', unit='nodes', done=4, rate=2.0,
           total=dict(median=20, lo=10, hi=40), to_go=dict(median=8, lo=3, hi=18),
           prior=.1, exists=.08, pending=2, finished=1)


def activation(t=120.0, path='/model/a.json', digest='a'*64):
    return dict(event='model', time=t, path=path, sha256=digest)


class Model(unittest.TestCase):
    def test_old_records_keep_the_explicit_initial_model(self):
        # Replicata: a record predating model events. Expectata: unchanged record and explicit launch model.
        # Resultata before: model_of is absent.
        import track
        record = [copy.deepcopy(START), copy.deepcopy(EST)]
        before = copy.deepcopy(record)
        self.assertEqual(track.model_of(record, 'initial.json', 115), dict(path='initial.json', sha256=None))
        self.assertEqual(record, before)

    def test_interleaving_does_not_rewrite_earlier_estimates(self):
        # Replicata: an estimate started before activation but appended after it, then a pause/new model/end.
        # Expectata: accept the two independently ordered event streams; original forecasts are untouched.
        # Resultata before: checked rejects every model event.
        import track
        record = [START, EST, activation(), dict(EST, time=115), dict(event='pause', time=125),
                  activation(126, '/model/b.json', 'b'*64), dict(EST, time=127), dict(event='end', time=130, status=-15)]
        before = copy.deepcopy(record)
        self.assertEqual(track.checked(record), before)
        self.assertEqual(record, before)

    def test_model_selection_uses_the_forecast_time(self):
        # Replicata: two explicit activations and forecasts before, at and after each activation.
        # Expectata: later activations never leak into an earlier forecast; ties use the last appended model.
        # Resultata before: model_of is absent.
        import track
        a = activation(); b = activation(130, '/model/b.json', 'b'*64)
        c = activation(130, '/model/c.json', 'c'*64)
        record = [START, EST, a, b, c]
        for t, expected in ((119, dict(path='initial.json', sha256=None)),
                            (120, dict(path=a['path'], sha256=a['sha256'])),
                            (129, dict(path=a['path'], sha256=a['sha256'])),
                            (130, dict(path=c['path'], sha256=c['sha256']))):
            self.assertEqual(track.model_of(record, 'initial.json', t), expected)

    def test_malformed_model_events_are_rejected(self):
        # Replicata: model records with bad schema, time, digest, path or event position.
        # Expectata: fail loudly; model events do not weaken the existing pause/end rules.
        # Resultata before: this positive rejection control already passes because no model is recognized.
        import track
        bad = [activation(99), activation(float('nan')), activation(True), activation(path='relative.json'),
               activation(path=''), activation(digest='z'*64), activation(digest='A'*64),
               activation(digest='a'*63), dict(activation(), extra=1),
               {k:v for k,v in activation().items() if k!='sha256'}]
        for event in bad:
            with self.assertRaises(AssertionError): track.checked([START, event])
        records = [[activation()], [START, activation(), activation(119)],
                   [START, dict(event='end', time=130, status=0), activation()],
                   [START, dict(event='pause', time=115), activation(), dict(event='pause', time=125)]]
        for record in records:
            with self.assertRaises(AssertionError): track.checked(record)

    def test_selection_requires_a_valid_observation_time(self):
        # Replicata: model selection with an invalid clock. Expectata: no silently guessed current time.
        # Resultata before: model_of is absent.
        import track
        for now in (99, float('nan'), float('inf'), True):
            with self.assertRaises(AssertionError): track.model_of([START], 'initial.json', now)

    def test_cli_appends_hash_bound_metadata_only(self):
        # Replicata: activate a local model on an existing non-ended record in an isolated directory.
        # Expectata: old bytes/model bytes remain intact, one absolute-path/digest event is appended.
        # Resultata before: CLI rejects the model command.
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory); (d/'searchwatch').mkdir(); (d/'runs').mkdir()
            shutil.copy2(ROOT/'searchwatch/track.py', d/'searchwatch/track.py')
            record = d/'runs/q.jsonl'; old = ''.join(json.dumps(x)+'\n' for x in (START, EST)).encode()
            record.write_bytes(old); model = d/'new.json'; contents = b'{"parameter":2}\n'; model.write_bytes(contents)
            p = subprocess.run([sys.executable, '-B', 'searchwatch/track.py', 'model', 'q', 'new.json'],
                               cwd=d, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(record.read_bytes().startswith(old))
            rows = [json.loads(x) for x in record.read_text().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual({k:v for k,v in rows[-1].items() if k!='time'},
                             dict(event='model', path=str(model.resolve()), sha256=hashlib.sha256(contents).hexdigest()))
            self.assertGreater(rows[-1]['time'], EST['time'])
            self.assertEqual(model.read_bytes(), contents)

    def test_refused_activation_leaves_every_file_unchanged(self):
        # Replicata: ended/missing run, bad name, missing model or malformed command.
        # Expectata: nonzero exit and no changed record/model bytes or newly created record.
        # Resultata before: these rejection controls already pass.
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory); (d/'searchwatch').mkdir(); (d/'runs').mkdir()
            shutil.copy2(ROOT/'searchwatch/track.py', d/'searchwatch/track.py')
            model = d/'new.json'; model.write_text('{}\n')
            record = d/'runs/q.jsonl'
            old = ''.join(json.dumps(x)+'\n' for x in (START, EST, dict(event='end', time=130, status=0))).encode()
            record.write_bytes(old)
            for args in (['q','new.json'], ['missing','new.json'], ['../q','new.json'], ['q','missing.json'], ['q']):
                p = subprocess.run([sys.executable,'-B','searchwatch/track.py','model',*args], cwd=d, capture_output=True)
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(record.read_bytes(), old)
                self.assertEqual(model.read_text(), '{}\n')
                self.assertEqual(sorted(p.name for p in (d/'runs').iterdir()), ['q.jsonl'])

    def test_watcher_ignores_activation_for_forecast_history(self):
        # Replicata: the same active search, with or without model metadata between its estimates.
        # Expectata: graph values, historical timestamps and work state are identical.
        # Resultata before: checked rejects the new record before the watcher can use it.
        import track, watch
        plain = [START, EST, dict(EST, time=130, done=6)]
        changed = [START, EST, activation(), plain[-1]]
        track.checked(changed)
        a = watch.entry(('formtree','16:2'), [plain], {123:'S',124:'S'}, 140, [])
        b = watch.entry(('formtree','16:2'), [changed], {123:'S',124:'S'}, 140, [])
        self.assertEqual(a,b)

    def test_activation_alone_preserves_readouts_history_and_staleness(self):
        # Replicata: snapshot a live search, append only model metadata, then let its estimate go stale;
        # another model activation precedes a genuinely new estimate.
        # Expectata: activation changes no readout/history and cannot refresh stale estimates; the new estimate
        # updates readouts/history and clears staleness normally. Resultata with the old validator: activation
        # alone makes a fresh entry stale because the watcher rejects the newly extended record.
        import watch
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory); runs, cpu = d/'runs', d/'cpu.jsonl'; runs.mkdir()
            path = runs/'q.jsonl'; procs = {123:'S',124:'S'}; kept = {}
            def write(rows): path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            write([START, EST])
            initial = watch.snapshot(str(runs), str(cpu), procs, 120, kept)
            self.assertEqual(len(initial), 1)
            first_model = activation(119)
            write([START, EST, first_model])
            activated = watch.snapshot(str(runs), str(cpu), procs, 120, kept)
            self.assertEqual(activated, initial)
            second_model = activation(1390, '/model/b.json', 'b'*64)
            write([START, EST, first_model, second_model])
            with contextlib.redirect_stderr(io.StringIO()):
                stale = watch.snapshot(str(runs), str(cpu), procs, 1400, kept)
            self.assertEqual(stale, [initial[0] | dict(stale=120)])
            fresh = dict(EST, time=1410, done=8, rate=4.0, total=dict(median=24,lo=12,hi=48),
                         to_go=dict(median=4,lo=1,hi=10), exists=.06, pending=1, finished=2)
            write([START, EST, first_model, second_model, fresh])
            updated = watch.snapshot(str(runs), str(cpu), procs, 1420, kept)
            expected = watch.entry(('formtree','16:2'), [[START,EST,fresh]], procs, 1420, [])
            self.assertEqual(updated, [expected])
            self.assertIsNone(updated[0]['stale'])
            self.assertEqual(updated[0]['to_go'], fresh['to_go'])
            self.assertEqual(updated[0]['work']['done'], 8)
            self.assertEqual(updated[0]['etas'][:-1], initial[0]['etas'])
            self.assertEqual(updated[0]['etas'][-1], [1410,1310.0,4,1,10])
            self.assertEqual(updated[0]['rates'][-1], [1410,1310.0,4.0])


if __name__ == '__main__': unittest.main()
