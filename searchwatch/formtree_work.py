"""Read exact form-tree work and measured throughput without importing the prover or checker."""
import hashlib
import json
import math
from pathlib import Path
import re
import time

MAX_AGE = 1200
TAU = 3 * 3600   # the rate's time constant, s (dreeves, 2026-11-07: "maybe 3 hours at least, or just do an exponentially weighted moving average of rates")
PROGRESS = re.compile(r'^\[(\d+)s\] done (\d+), left (\d+); nodes ([0-9.e+]+),')
HEADER = re.compile(r'^(\d+) start nodes; \d+ tasks to run; (\d+) nodes done$')


def _prefix(path):
    """One captured file-size prefix, ending at its last complete line; never rewrite its source."""
    with path.open('rb') as f:
        import os
        st = os.fstat(f.fileno())
        data = f.read(st.st_size)
    assert len(data) == st.st_size
    cut = data.rfind(b'\n') + 1
    prefix = data[:cut]
    return prefix, dict(path=str(path), bytes=cut, trailing_bytes=len(data)-cut,
                        mtime=st.st_mtime, sha256=hashlib.sha256(prefix).hexdigest())


def _roots(verdicts, roots):
    return walk(verdicts, roots)[0]


def walk(verdicts, roots):
    """(rows, waiting): each root's row, {name, done: its nodes checked, complete: whether every node under it has a
    verdict}, and waiting, the nodes named (a root, or a spill of a node checked) that have no verdict yet: the nodes
    pending, as searches/formtree/ftree.py's remaining() finds them and its log counts them ("left") (the pending count
    since 2026-11-12, Opus 5.5)."""
    assert roots and len(set(roots)) == len(roots) and all(type(n) is str and n for n in roots)
    assert all(v['ok'] is True and type(v['open']) is int and v['open'] == 0 and v.get('py') is not False for v in verdicts)
    assert all(type(v['nodes']) is int and v['nodes'] > len(v['spills']) and
               type(v['spills']) is list and all(type(n) is str and n for n in v['spills']) for v in verdicts)
    have = {v['start']: v for v in verdicts}
    assert len(have) == len(verdicts)
    result = [dict(name=n, done=0, complete=True) for n in roots]
    seen, todo, waiting = set(), [(n, i) for i, n in enumerate(roots)], []
    while todo:
        name, i = todo.pop()
        assert name not in seen
        seen.add(name)
        if name in have:
            v = have[name]
            result[i]['done'] += v['nodes'] - len(v['spills'])
            todo.extend((c, i) for c in v['spills'])
        else:
            result[i]['complete'] = False
            waiting.append(name)
    assert set(have) <= seen
    return result, waiting


def _driver(root):
    """Latest matching track record: identity metadata, not proof that its PID still lives."""
    records = []
    for path in (root/'runs').glob('*.jsonl'):
        data, source = _prefix(path)
        lines = [json.loads(s) for s in data.splitlines()]
        if lines and lines[0].get('program') == 'ftree.py' and lines[0].get('target') == '288:10':
            records.append((lines, source))
    if not records:
        return None
    lines, source = max(records, key=lambda x: x[0][0]['time'])
    start = lines[0]
    return {k: start.get(k) for k in ('pid', 'started', 'time', 'command', 'cwd')} | dict(
        record=source['path'], record_ended=lines[-1]['event'] == 'end')


def read(root, roots, now=None, active=True):
    """Repository root, ordered immutable root names, observation epoch -> exact work and its wall rate, weighted toward the last TAU.

    The log is captured before the verdict prefix so its completed-task counts are available. Log mtime is an
    observation-time proxy, not an exact timestamp of the last progress line or the process start. Driver elapsed
    seconds supply rate intervals. Sources and prefix hashes make the accounting reproducible. A trailing partial
    line is retained in provenance but never parsed. No process liveness is inferred from an adopted track record.
    With now=None, observation time is measured after the frozen reads; an explicit epoch is checked literally.
    An inactive search may have stale observations or zero measured throughput; its work is still checked exactly.
    """
    root = Path(root)
    assert type(active) is bool
    log, logsource = _prefix(root/'scratch/formtree/run288v.log')
    data, vsource = _prefix(root/'scratch/formtree/run288v/verdicts.jsonl')
    verdicts = [json.loads(s) for s in data.splitlines()]
    rows = _roots(verdicts, roots)
    raw, expanded = [0], [0]
    for v in verdicts:
        raw.append(raw[-1] + v['nodes'])
        expanded.append(expanded[-1] + v['nodes'] - len(v['spills']))
    text = log.decode('utf-8')
    segment = text[text.rindex('top of 288:10'):].splitlines()
    header = HEADER.fullmatch(segment[1])
    assert header and int(header[1]) == len(roots)
    retained = int(header[2])
    assert retained in raw
    offset = raw.index(retained)
    points = []
    finished = segment[-1].startswith('finished:')
    body = segment[2:len(segment)-int(finished)]
    for line in body:
        match = PROGRESS.match(line)
        assert match
        errors = [re.search(pattern, line) for pattern in
                  (r'OPEN (\d+)', r'REJECTED (\d+)', r'wrong names (\d+)', r'sampled (\d+) differ')]
        assert all(m and int(m[1]) == 0 for m in errors)
        elapsed, count = int(match[1]), int(match[2]) + offset
        assert count < len(raw) and f'{raw[count]:.4g}' == match[4]
        points.append((elapsed, expanded[count]))
    assert len(points) > 1 and all(b[0] > a[0] and b[1] >= a[1] for a, b in zip(points, points[1:]))
    # the throughput, each interval between progress lines weighted by exp(-age / TAU), its age measured between middles
    # back from the newest interval, whose weight is then exactly 1 (2026-11-07; before, the last hour's aggregate, which
    # swung the ETA whenever other work took the cores)
    pairs = list(zip(points, points[1:]))
    newest = (pairs[-1][0][0] + pairs[-1][1][0]) / 2
    weights = [math.exp(((a[0] + b[0]) / 2 - newest) / TAU) for a, b in pairs]
    rate = (sum(w * (b[1] - a[1]) for w, (a, b) in zip(weights, pairs))
            / sum(w * (b[0] - a[0]) for w, (a, b) in zip(weights, pairs)))
    assert math.isfinite(rate) and rate >= 0 and (not active or rate > 0)
    driver = _driver(root)
    observed_at = time.time() if now is None else now
    assert math.isfinite(observed_at)
    age = observed_at - logsource['mtime']
    complete = all(r['complete'] for r in rows)
    assert age >= 0 and (complete or not active or age <= MAX_AGE)
    assert not finished or complete
    return dict(roots=rows, done=expanded[-1], rate=rate, source_time=logsource['mtime'], source_age=age,
                log_elapsed=points[-1][0], log_done=points[-1][1], retained_verdicts=offset,
                source=dict(log=logsource, verdicts=vsource), driver=driver, finished=finished,
                config_source=driver['command'] if driver else None, observed_at=observed_at)
