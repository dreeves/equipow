"""One progress watcher with the full wider-pruning sweep added.

progress.py remains byte-for-byte unchanged because it belongs to the earlier
paired study's fingerprint. The serializer hook appends this survey to its
ordinary snapshot; the original watcher still owns all other surveys and the
single progress.js write. Sweep observations have their own atomic cache.
"""
import glob
import json
from pathlib import Path
import sys

import progress


CACHE = Path(progress.HERE) / 'scratch' / 'sweep288' / 'progress-cache.json'


def survey(path, procs, now=None, observations=None):
    """One independently recovered control, followed by 2,736 pruned target attempts."""
    run, header, done, active, _ = progress.survey_attempts(
        path, procs, now, observations, 'sweep288.py', 288, 10, 'wider-witness')
    assert (header['control_n'], header['control_order'], header['control_total'], header['total']) == (240, 10, 1, 2736)
    assert header['width'] == 0.1
    control = ''.join('1' if i in done['calibration'] else '4' if active == ('calibration', i) else '3'
                      for i in range(header['control_total']))
    run['sea']['keys'].insert(0, '240:10')
    run['sea']['groups'].insert(0, control)
    codes = ''.join(run['sea']['groups'])
    run['sea']['counts'] = {name: codes.count(str(i)) for i, name in enumerate(progress.SEA_STATUSES)}
    run['display']['work'].update(control_empty=list(done['calibration'].values()).count('empty'),
                                   control_timeout=list(done['calibration'].values()).count('timeout'))
    return run


def snapshot(surveys, now, serialize):
    """Add the sweep at serialization, preserving the original list and its later clock."""
    extra = []
    for path in glob.glob(str(Path(progress.HERE) / 'sweep288_journal.jsonl')):
        with open(path, encoding='utf-8') as f: header = json.loads(f.readline())
        cache = progress.load_cache(CACHE)
        key = f'sweep288_{header["code"]}_{header["time"]}_observations'
        extra.append(survey(path, progress.processes(), observations=cache.setdefault(key, {})))
        Path(CACHE).parent.mkdir(parents=True, exist_ok=True)
        progress.save_cache(CACHE, cache)
    return serialize(surveys + extra, max([now] + [run['made'] for run in extra]))


def main(argv):
    serialize = progress.js_text
    progress.js_text = lambda surveys, now: snapshot(surveys, now, serialize)
    try:
        progress.main(argv)
    finally:
        progress.js_text = serialize


if __name__ == '__main__':
    main(sys.argv[1:])
