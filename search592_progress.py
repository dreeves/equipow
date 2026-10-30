"""One progress watcher with the calibrated 592 pilot added after the 288 sweep.

The pilot's survey is one more unit of progress.main's snapshot (see progress.snapshot), after the sweep's, through
sweep288_progress.main, bounded in time like the others, with the single progress.js write. Pilot observations have
their own atomic cache. (Before 2026-10-30 this module and sweep288_progress chained wrappers of progress.js_text.)
"""
import functools
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


def unit(path, header, procs):
    """The pilot's survey with its observations kept in CACHE, read and written around it."""
    cache = progress.load_cache(CACHE)
    key = f'search592_{header["code"]}_{header["time"]}_observations'
    run = survey(path, procs, observations=cache.setdefault(key, {}))
    Path(CACHE).parent.mkdir(parents=True, exist_ok=True)
    progress.save_cache(CACHE, cache)
    return [run]


def units(procs, now):
    """The pilot's unit (see progress.snapshot), if its journal exists."""
    return [(('search592.py', 592, 10), functools.partial(unit, path, header, procs))
            for path, header in progress.headers('search592_journal.jsonl')]


def main(argv):
    sweep288_progress.main(argv, extra=(units,))


if __name__ == '__main__':
    main(sys.argv[1:])
