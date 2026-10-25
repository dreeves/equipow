"""One progress watcher with the calibrated 592 pilot added after the 288 sweep.

The two older progress modules remain byte-for-byte unchanged for historical
replay. This serializer hook chains through sweep288_progress.main, preserving
all older surveys and the single progress.js write. Pilot observations have
their own atomic cache.
"""
import glob
import json
from pathlib import Path
import sys

import progress
import sweep288_progress


CACHE = Path(progress.HERE) / 'scratch' / 'search592' / 'progress-cache.json'


def survey(path, procs, now=None, observations=None):
    """A freshly recovered 560:10 control gates the header's 592:10 target attempts."""
    run, header, done, active, _ = progress.survey_attempts(
        path, procs, now, observations, 'search592.py', 592, 10, 'calibrated-witness')
    assert (header['control_n'], header['control_order']) == (560, 10)
    control = ''.join('1' if i in done['calibration'] else '4' if active == ('calibration', i) else '3'
                      for i in range(header['control_total']))
    run['sea']['keys'].insert(0, '560:10')
    run['sea']['groups'].insert(0, control)
    codes = ''.join(run['sea']['groups'])
    run['sea']['counts'] = {name: codes.count(str(i)) for i, name in enumerate(progress.SEA_STATUSES)}
    run['display']['work'].update(control_empty=list(done['calibration'].values()).count('empty'),
                                   control_timeout=list(done['calibration'].values()).count('timeout'))
    return run


def snapshot(surveys, now, serialize):
    """Append the pilot without mutating older surveys or backdating its snapshot."""
    extra = []
    for path in glob.glob(str(Path(progress.HERE) / 'search592_journal.jsonl')):
        with open(path, encoding='utf-8') as f: header = json.loads(f.readline())
        cache = progress.load_cache(CACHE)
        key = f'search592_{header["code"]}_{header["time"]}_observations'
        extra.append(survey(path, progress.processes(), observations=cache.setdefault(key, {})))
        Path(CACHE).parent.mkdir(parents=True, exist_ok=True)
        progress.save_cache(CACHE, cache)
    return serialize(surveys + extra, max([now] + [run['made'] for run in extra]))


def main(argv):
    serialize = progress.js_text
    progress.js_text = lambda surveys, now: snapshot(surveys, now, serialize)
    try:
        sweep288_progress.main(argv)
    finally:
        progress.js_text = serialize


if __name__ == '__main__':
    main(sys.argv[1:])
