#!/usr/bin/env python3
"""Replay saved ETA forecasts against completed form-tree searches; never fit or run a model.

    python3 -B searchwatch/eta_replay.py MANIFEST.json > REPORT.json

Manifest version 1: {runs: [{name, target, unit: "nodes", roots, verdicts, forecasts,
spans: [[start, end], ...], expected_total, source_hashes: {path: sha256},
model_sources: {sha256: path}, band_quantiles: [lo, hi] | null, notes}], version: 1}.
Paths are relative to the repository root, or absolute. Verdicts and forecasts are
JSONL. Every input file, including those two, must occur in source_hashes.

A forecast has time (epoch seconds), done (accounted nodes), rate (nodes/s),
total (a {median, lo, hi} band or null), and to_go (a band, in seconds). Optional
finished identifies its exact verdict prefix; model_sha256 identifies a retained
model. A run's optional expected_finished asserts its final task count. Other
recorded fields are preserved unchanged. band_quantiles is provenance
only: unknown historical levels stay null. See README.md for archive preparation.

Work means expanded nodes in the completed verdict graph, subtracting spilled
roots counted again by child tasks. Remaining work is final work minus *reported*
done: it includes work already spent in tasks without verdicts at that snapshot.
Time means the union of recorded run spans through the last recorded end. That end
includes tracking/cleanup, and is not an independent last-node timestamp. The
future accounted-work rate is descriptive, not instantaneous solver throughput.

Each search is summarized separately; correlated snapshots are not independent
calibration trials. Exact terminal observations remain in rows but not summaries.
Separate marginal work/time quantiles need not obey time = work / recorded rate.
"""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import json
from itertools import accumulate
from pathlib import Path
import re
from statistics import median

import formtree_work
from track import band, number, passes

ROOT = Path(__file__).resolve().parents[1]


def active_seconds(spans, t):
    """Active wall seconds at or after t; overlaps count once and pauses not at all."""
    assert number(t) and spans
    assert all(len(s) == 2 and all(number(v) for v in s) and s[0] <= s[1] for s in spans)
    return sum(max(0, b - max(a, t)) for a, b in passes(spans))


def exact_total(verdicts, roots):
    """Accept only a complete, consistent graph of successful checker verdicts."""
    rows, waiting = formtree_work.walk(verdicts, roots)
    assert not waiting and all(r['complete'] for r in rows)
    return sum(r['done'] for r in rows)


def ratio(numerator, denominator):
    """No invented epsilon at zero: an undefined ratio is JSON null."""
    return numerator / denominator if denominator else None


def errors(b, actual):
    """Signed median error, multiplicative error, inclusive interval hit and width."""
    return dict(error=b['median'] - actual, factor=ratio(b['median'], actual),
                hit=b['lo'] <= actual <= b['hi'], width=b['hi'] - b['lo'])


def score(forecast, total, spans):
    """Pure scoring: outcome truth is separate from an unchanged copy of the forecast."""
    f = forecast
    assert type(total) is int and total > 0
    assert 'unit' not in f or f['unit'] == 'nodes'
    assert all(number(f[k]) for k in ('time', 'done', 'rate'))
    assert type(f['done']) is int and 0 <= f['done'] <= total and f['rate'] > 0
    seconds = active_seconds(spans, f['time'])
    assert min(a for a, _ in spans) <= f['time'] <= max(b for _, b in spans)
    assert band(f['to_go'])
    assert f['total'] is None or (band(f['total']) and f['total']['lo'] >= f['done'])
    remaining = total - f['done']
    assert seconds > 0 or remaining == 0
    actual_rate = ratio(remaining, seconds)
    work, total_error = None, None
    if f['total'] is not None:
        work = errors({k: v - f['done'] for k, v in f['total'].items()}, remaining)
        total_error = errors(f['total'], total)
    rate = None
    if actual_rate is not None:
        rate = dict(error=f['rate'] - actual_rate, factor=ratio(f['rate'], actual_rate))
    return dict(forecast=copy.deepcopy(f), actual=dict(work=remaining, seconds=seconds, rate=actual_rate),
                total=total_error, work=work, seconds=errors(f['to_go'], seconds), rate=rate)


def summarize(rows):
    """Describe one search's recorded nonterminal forecasts, without pooling searches."""
    forecasts = [r for r in rows if r['actual']['work'] > 0]
    out = dict(forecasts=len(forecasts))
    for key in ('total', 'work', 'seconds'):
        values = [r[key] for r in forecasts if r[key] is not None]
        out[key] = None
        if values:
            out[key] = dict(count=len(values), median_error=median(v['error'] for v in values),
                            median_absolute_error=median(abs(v['error']) for v in values),
                            median_factor=median(v['factor'] for v in values),
                            band_hits=sum(v['hit'] for v in values),
                            median_band_width=median(v['width'] for v in values))
    return out


def replay(manifest, root=ROOT):
    """Verify frozen source hashes, complete outcomes and verdict prefixes, then score."""
    assert __debug__ and manifest['version'] == 1 and manifest['runs']
    assert len({r['name'] for r in manifest['runs']}) == len(manifest['runs'])
    root, results = Path(root), []
    for run in manifest['runs']:
        assert run['unit'] == 'nodes' and re.fullmatch(r'[1-9]\d*:[1-9]\d*', run['target'])
        levels = run['band_quantiles']
        assert levels is None or (len(levels) == 2 and all(number(x) for x in levels) and 0 < levels[0] < levels[1] < 1)
        sources = {p: (root / p).read_bytes() for p in run['source_hashes']}
        assert all(hashlib.sha256(data).hexdigest() == run['source_hashes'][p] for p, data in sources.items())
        assert all(run['source_hashes'][p] == h for h, p in run['model_sources'].items())
        verdicts = [json.loads(line) for line in sources[run['verdicts']].splitlines()]
        forecasts = [json.loads(line) for line in sources[run['forecasts']].splitlines()]
        total = exact_total(verdicts, run['roots'])
        assert total == run['expected_total']
        assert 'expected_finished' not in run or run['expected_finished'] == len(verdicts)
        prefix = list(accumulate((v['nodes'] - len(v['spills']) for v in verdicts), initial=0))
        assert forecasts and all(a['time'] < b['time'] and a['done'] <= b['done'] for a, b in zip(forecasts, forecasts[1:]))
        for f in forecasts:
            assert 'target' not in f or f['target'] == run['target']
            finished, model = f.get('finished'), f.get('model_sha256')
            assert finished is None or (type(finished) is int and 0 <= finished < len(prefix) and prefix[finished] == f['done'])
            assert model is None or model in run['model_sources']
        rows = [score(f, total, run['spans']) for f in forecasts]
        results.append(dict(archive=copy.deepcopy(run), total=total, tasks=len(verdicts),
                            active_seconds=active_seconds(run['spans'], min(a for a, _ in run['spans'])),
                            rows=rows, summary=summarize(rows)))
    return dict(version=1, runs=results)


def main(argv):
    # TODO: usage: provide exactly one replay manifest; assertions must be enabled.
    assert __debug__ and len(argv) == 1, 'Usus: python3 -B searchwatch/eta_replay.py MANIFEST.json; assertiones requiruntur.'
    manifest = json.loads(Path(argv[0]).read_text())
    print(json.dumps(replay(manifest), indent=2, allow_nan=False))


if __name__ == '__main__': main(sys.argv[1:])
